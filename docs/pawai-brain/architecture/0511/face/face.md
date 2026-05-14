# 人臉辨識（face_perception）— 架構詳述

**版本**：2026-05-11 freeze 快照
**位置**：`face_perception/`
**入口**：`face_perception/face_perception/face_identity_node.py`（單體 ~680 行）
**狀態**：5/12 demo 95% 完成（greeting 可靠，multi-person tracking 仍有噪音）

---

## 1. 模組定位

人臉辨識是 PawAI 的**身份感知層**：把 D435 看到的人臉轉成「誰在說話」這個資訊，餵給 Brain（語境 grounding）和 Executive（迎接 / 跌倒警告身份注入）。

**核心設計**：
- 偵測 + 識別 + 追蹤都在**同一個 ROS2 node** 裡，無子模組
- **CPU only**（YuNet + SFace 都跑 OpenCV DNN CPU）— 留 GPU 給 pose / vision
- 雙軌發佈：State topic（連續快照供 LLM 語境）+ Event topic（離散事件供 Executive 仲裁）
- 單一 `threading.Lock` 保護 frame buffer，OpenCV 推理本身 thread-safe

**對外介面**：
- 訂閱：`/camera/camera/color/image_raw` + `/camera/camera/aligned_depth_to_color/image_raw`
- 發佈：`/state/perception/face`（8Hz）+ `/event/face_identity`（事件）+ `/face_identity/debug_image`

---

## 2. Pipeline 全貌（6 stage）

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Intel RealSense D435                             │
│       /camera/camera/color/image_raw      (BGR 640×480 30Hz)        │
│       /camera/camera/aligned_depth_to_color/image_raw  (深度)       │
└─────────────────────────────────────────────────────────────────────┘
                              │  BEST_EFFORT, depth=1
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│           face_identity_node  (20Hz tick, single-thread)            │
│                                                                     │
│   ┌─────────────────┐                                               │
│ 1 │ YuNet 偵測      │  /home/jetson/face_models/                    │
│   │ FaceDetectorYN  │     face_detection_yunet_2023mar.onnx         │
│   └─────────────────┘  det_score=0.35, top_k=5000, max_faces=5      │
│            │                                                        │
│            ▼  bbox + 5 landmarks                                    │
│   ┌─────────────────┐                                               │
│ 2 │ SFace 對齊+嵌入 │  /home/jetson/face_models/                    │
│   │ FaceRecognizerSF│     face_recognition_sface_2021dec.onnx       │
│   └─────────────────┘  alignCrop → 112×112 → 128-D embedding        │
│            │                                                        │
│            ▼  embedding (np.float32, 128維)                         │
│   ┌─────────────────┐                                               │
│ 3 │ Cosine 比對     │  /home/jetson/face_db/model_sface.pkl         │
│   │ predict_name()  │  max(sim) over per-person samples             │
│   └─────────────────┘  upper=0.40 (5/8 收緊), lower=0.22 (5/4 放寬)│
│            │                                                        │
│            ▼  raw_name + raw_sim                                    │
│   ┌─────────────────┐                                               │
│ 4 │ IOU 追蹤        │  track_iou=0.15, max_misses=20 frames (~1s)   │
│   │ assign_tracks() │  → track_id（per-session 遞增，無 re-ID）    │
│   └─────────────────┘                                               │
│            │                                                        │
│            ▼  track_id ↔ detection 配對                             │
│   ┌─────────────────┐                                               │
│ 5 │ 身份穩定化      │  stable_hits=2, unknown_grace_s=2.5           │
│   │decide_stable_   │  upper 帶 → propose name                      │
│   │  name()         │  lower 帶 → propose "unknown"                 │
│   └─────────────────┘  中間帶 → hold 前一個穩定值                   │
│            │                                                        │
│            ▼  stable_name (locked) + mode (stable|hold)             │
│   ┌─────────────────┐                                               │
│ 6 │ 深度估距        │  median(roi depth) × 0.001 → distance_m       │
│   └─────────────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌────────────────────────────────────────────────────────────┐    │
│   │ 雙軌發佈                                                   │    │
│   │  State (8Hz throttle):  /state/perception/face             │    │
│   │  Event (transitions):   /event/face_identity               │    │
│   │  Debug image (8Hz):     /face_identity/debug_image         │    │
│   └────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. 各 Stage 細節

### Stage 1：YuNet 偵測
- **Model**：OpenCV `FaceDetectorYN`（ONNX backend）
- **檔案**：`/home/jetson/face_models/face_detection_yunet_2023mar.onnx`
- **重要**：必須 2023mar 版（legacy 版本 OpenCV 4.13 dynamic shape 不相容會崩潰）
- **輸入尺寸**：`detector.setInputSize((w, h))` 自動跟 frame 走
- **輸出**：`[x, y, w, h, conf, landmark_5_pts]` per face
- **過濾**：top-K by area，最多 `max_faces=5`，最小面積 `(w*h) / frame_area ≥ min_face_area_ratio`

### Stage 2：SFace 對齊 + 嵌入
- **Model**：OpenCV `FaceRecognizerSF`（ONNX backend）
- **檔案**：`/home/jetson/face_models/face_recognition_sface_2021dec.onnx`
- **輸出**：128-D float32 embedding（L2 normalized）
- **流程**：
  1. `recognizer.alignCrop(image_bgr, face_row)` → 112×112 對齊裁切
  2. `recognizer.feature(aligned)` → 128-D embedding
- **加速**：預註冊的 112×112 圖檔直接抽特徵，跳過 alignCrop

### Stage 3：Cosine 比對（predict_name）
- **DB 格式**：`/home/jetson/face_db/model_sface.pkl`
  ```python
  {
    "embeddings": {"roy": [emb1, emb2, ...], "grama": [...]},
    "centroids":  {"roy": mean_emb, "grama": mean_emb},
    "counts":     {"roy": 30, "grama": 25}
  }
  ```
- **比對算法**：
  ```python
  for name in DB:
      if len(samples) > 1:
          sim = max(cosine_similarity(emb_frame, sample_i) for sample_i in samples)
      else:
          sim = cosine_similarity(emb_frame, centroid)
  winner = argmax(sim)
  ```
- **閾值**：
  - `sim ≥ sim_threshold_upper (0.40)` → 確定識別
  - `sim < sim_threshold_lower (0.22)` → 確定 unknown
  - 中間帶 → 沿用前一個 stable_name

### Stage 4：IOU 追蹤
- **算法**：frame-to-frame IOU 配對
- **track_state**：`{bbox, misses}`
- **生命週期**：
  ```
  新偵測 + IOU ≥ 0.15 with existing track → 更新該 track（misses=0）
  新偵測 + 無 match → 建立新 track（next_track_id += 1）
  舊 track + 無 match → misses += 1
  misses > 20（~1s @ 20Hz）→ 刪除 track，發 track_lost
  ```
- **無 re-ID**：人離開再回來會拿新 track_id（per-session 遞增）

### Stage 5：身份穩定化（hysteresis）
- **State per track**：
  ```python
  candidate_name, candidate_hits, last_stable_name, last_stable_sim, last_known_ts
  ```
- **邏輯**：
  ```
  1. propose:
     raw_sim ≥ upper → proposed = raw_name
     raw_sim < lower → proposed = "unknown"
     else           → proposed = last_stable_name（hold）
  
  2. accumulate:
     proposed == candidate_name → candidate_hits += 1
     else → 重置 candidate_name, hits=1
  
  3. lock:
     candidate_hits ≥ stable_hits (2) → last_stable_name = candidate_name
  
  4. grace period:
     若 last_stable_name 是已知人，但現在 proposed="unknown"
     而且距離上次已知 < unknown_grace_s (2.5)
     → 維持已知身份（mode="hold"）
  ```

### Stage 6：深度估距
- **算法**：
  ```python
  roi = depth_aligned[y1:y2, x1:x2]
  valid = roi[(roi > 0) & (roi < 10000)]   # mm，10m 上限
  distance_m = median(valid) * 0.001        # mm → m
  ```
- 無有效深度時 `distance_m = null`

---

## 4. Topic Schema（v2.5 凍結）

### `/state/perception/face`（8Hz 連續快照）

```json
{
  "stamp": 1773561600.789,
  "face_count": 2,
  "tracks": [
    {
      "track_id": 1,
      "stable_name": "roy",         // 或 "unknown"
      "sim": 0.42,                  // cosine similarity 原值
      "distance_m": 1.25,           // 或 null
      "bbox": [x1, y1, x2, y2],     // Python int（不是 np.int32！）
      "mode": "stable"              // "stable" 已鎖 / "hold" 寬限期
    }
  ]
}
```

### `/event/face_identity`（事件觸發，非週期）

```json
{
  "stamp": 1773561600.789,
  "event_type": "identity_stable",  // track_started | identity_stable
                                     // identity_changed | track_lost
  "track_id": 1,
  "stable_name": "roy",
  "sim": 0.42,
  "distance_m": 1.25
}
```

**事件觸發規則**：
- `track_started`：新 track_id 出現
- `identity_stable`：unknown → 已鎖身份
- `identity_changed`：已鎖身份切換
- `track_lost`：track 連續未匹配 `track_max_misses` 幀

---

## 5. 消費者拓撲

```
                    face_identity_node
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
/state/perception/face   /event/face_identity   /face_identity/debug_image
        │                 │                          │
   ┌────┼─────────────┐   ├─────────────┐            ▼
   │    │             │   │             │       Foxglove
   ▼    ▼             ▼   ▼             ▼      (人工驗證)
┌─────┐ ┌──────────┐ ┌─────────┐ ┌────────────────────────┐
│Brain│ │vision_   │ │studio_  │ │interaction_executive   │
│     │ │perception│ │gateway  │ │  brain_node            │
└─────┘ └──────────┘ └─────────┘ │  ├─ 維護 attention     │
   │    └─ interaction_router    │  │  (face 可見/距離)   │
   │       (welcome 防抖)         │  ├─ 跌倒警告身份注入   │
   │    └─ event_action_bridge   │  │  (fallen_alert name) │
   │       (手勢 TTS {name}      │  └─ welcome 仲裁       │
   │        套版)                 └────────────────────────┘
   ▼
conversation_graph_node._on_face_state
   ├─ 抽 tracks[0..n].stable_name != "unknown" → 第一個 hit
   ├─ 更新 _recent_face_identity = (name, ts)
   ├─ 受 _speaker_suppress_until 抑制（reset_context 後 5s 不寫入）
   └─ world_state_builder 讀取 → state.world_state.current_speaker
       └─ 注入 LLM prompt [眼前的人] 段
```

**重點**：Brain 只訂 state topic（語境用），Executive 只訂 event topic（互動觸發用），完全分工。

### Brain 端整合（pawai_brain）

```python
# conversation_graph_node._on_face_state
def _on_face_state(self, msg: String) -> None:
    payload = json.loads(msg.data)
    if time.time() < self._speaker_suppress_until:
        return  # P1-2：reset_context 後 5s 抑制
    for track in payload.get("tracks", []):
        name = track.get("stable_name") or "unknown"
        if name != "unknown":
            self._recent_face_identity = (name, time.time())
            return
```

Brain 端不對 stable_name 做進一步篩選；穩定化已在 face_identity_node 端完成。

---

## 6. Face DB 管理

### 結構
```
/home/jetson/face_db/
├── roy/
│   ├── 0001.png   (任意尺寸，自動 alignCrop)
│   ├── 0002.png   或預先切好 112×112（跳過對齊加速）
│   └── ...        (典型 30 張)
├── grama/
│   └── ...        (典型 25 張)
└── model_sface.pkl
```

### 自動同步機制
node 啟動時：
1. 計算磁碟上每個 person 資料夾的 PNG 數量
2. 與 `model_sface.pkl` 內的 `counts` 比對
3. 不一致 → 重訓並覆寫 `.pkl`（重新抽取所有 embedding）

### 註冊腳本
```bash
python3 scripts/face_identity_enroll_cv.py \
  --person-name roy --samples 30 \
  --output-dir /home/jetson/face_db
```
工作流程：訂 `/camera/camera/color/image_raw` → 每 0.25s 偵測最大臉並存 PNG → 達 N 張退出 → 重啟 node 觸發重訓。

**5/12 Demo 政策**：不開放現場註冊，只用既有 face_db（roy + grama）。

---

## 7. 模型選型（3/21 benchmark 決策）

| 角色 | 主線 | FPS (Jetson) | 備援 | 拒用 |
|------|------|:----:|------|------|
| 偵測 | **YuNet 2023mar** | 71.3 (CPU) | SCRFD-500M (34.7, GPU) | YuNet legacy（OpenCV 4.13 動態 shape 崩潰）|
| 識別 | **SFace 2021dec** | — | — | — |

### 為什麼是 YuNet 而非 SCRFD
- YuNet CPU-only → **不搶 GPU 預算**（pose / gesture / object 需要 GPU）
- 2.05× FPS 領先（71.3 vs 34.7）
- OpenCV Zoo 原生支援，無需額外推理框架

### 3/21 benchmark 細節
- YuNet 2023mar：71.3 FPS, RAM 866MB, **GPU 0%**, 9.66W, lat p99 33.9ms
- YuNet legacy：crash（OpenCV 動態 shape）
- SCRFD-500M：34.7 FPS, RAM 1771MB, **GPU 85.7%**, 7.43W, lat p99 34ms

---

## 8. 執行緒模型 / 同步

```
ROS2 default executor (single-thread)
   ├─ cb_color   ── lock ── self.color  (~1ms 拷貝)
   ├─ cb_depth   ── lock ── self.depth
   └─ tick (20Hz)─ lock ─ copy color/depth → 釋放鎖 → 執行 detect/recog/track
```

- **單一 `threading.Lock`**，只保護 frame buffer
- **不保護 OpenCV detector**（inference thread-safe）
- **無 frame queue**：QoS depth=1，舊 frame 直接被覆蓋（demand-pull）
- **無 deadlock 風險**：鎖永不嵌套

---

## 9. 關鍵參數（程式預設 vs Jetson YAML 實機）

| 參數 | 程式預設 | Jetson YAML | 用途 |
|------|:----:|:----:|------|
| `det_score_threshold` | 0.90 | **0.35** | YuNet 偵測信心（放寬以應對真實噪訊） |
| `min_face_area_ratio` | 0.02 | **0.001** | 最小臉佔比（放寬以接受遠距人臉） |
| `max_faces` | 5 | 5 | 每幀最多處理 |
| `sim_threshold_upper` | 0.35 | **0.40** | ≥ 此值直接鎖（5/8 收緊，抑制陌生人誤判）|
| `sim_threshold_lower` | 0.25 | **0.22** | < 此值直接歸 unknown（5/4 放寬，加快熟臉解析）|
| `stable_hits` | 3 | **2** | 鎖身份需連續一致幀數 |
| `unknown_grace_s` | 1.2 | **2.5** | 熟臉短暫掉信心的寬限期 |
| `track_iou_threshold` | 0.30 | **0.15** | IOU 配對門檻（放寬以應對快速移動）|
| `track_max_misses` | 10 | **20** | 連續未匹配多少幀後判定 track 死亡 |
| `publish_fps` | 8.0 | 8.0 | state topic 發佈頻率（內部 20Hz tick）|
| `tick_period` | 0.05 | 0.05 | 內部處理週期（20Hz）|
| `publish_compare_image` | True | **false** | side-by-side debug 圖（省頻寬）|
| `headless` | auto | **true** | 不顯示 OpenCV 視窗 |

---

## 10. Topic / Hardware 配置

### Input
- `/camera/camera/color/image_raw` — BGR 640×480 @30Hz
- `/camera/camera/aligned_depth_to_color/image_raw` — 對齊到 RGB 的深度

### Output
| Topic | 型別 | QoS | 頻率 | 內容 |
|-------|------|------|------|------|
| `/state/perception/face` | String JSON | depth=10 | ~8Hz（throttle）| 當前 face 狀態快照 |
| `/event/face_identity` | String JSON | depth=10 | 事件觸發 | track 轉換事件 |
| `/face_identity/debug_image` | Image bgr8 | depth=10 | ~8Hz | bbox + 標籤 |
| `/face_identity/compare_image` | Image bgr8 | depth=10 | ~8Hz | raw \| annotated（預設關）|

---

## 11. 已知問題（5/12 Demo 前凍結項）

| # | 問題 | 嚴重度 | 處置 |
|---|------|--------|------|
| 1 | Track 抖動 45 次/2min（目標 ≤5）| 中 | YuNet 偵測穩定性，Demo 後重構 |
| 2 | 低光環境誤識別 | 中 | 文件級 known issue |
| 3 | 空畫面偶發假人臉 | 低 | sim_threshold 0.40 抑制 |
| 4 | 多人同框 bbox 互竄 | 中 | 3+ 人不保證 |
| 5 | Model path 寫死 `/home/jetson/face_models/` | 低 | 後續 Clean Architecture 重構 |
| 6 | OpenCV 鎖 4.5.4（Jetson 限制）| 低 | 不升級 |
| 7 | `to_bbox()` 回傳 np.int32（JSON 不認）| 已修 | 強制轉 Python int |

---

## 12. 啟動 / 清理

```bash
# 一鍵啟動（推薦）— D435 + face_identity + foxglove
bash scripts/start_face_identity_tmux.sh

# 或手動
ros2 launch face_perception face_perception.launch.py

# 環境清理
bash scripts/clean_face_env.sh --all

# 壓力測試（3 感知共跑 60s）
bash scripts/start_stress_test_tmux.sh 60
```

---

## 13. 測試覆蓋

`face_perception/test/test_utilities.py`：
- `TestCosineSimilarity`（4）：identical / orthogonal / opposite / zero
- `TestBboxIou`（4）：identical / no overlap / partial / contained
- `TestToBbox`（4）：normal / edge / zero-size / out-of-frame

**整合 smoke test**（2026-04-06）：2 分鐘 21 次 identity_stable for "roy"，零誤判。

---

## 14. 關鍵設計決策（給寫計畫書的參考）

1. **CPU only 策略**：YuNet + SFace 都跑 CPU，保護 GPU 給 pose / vision / object 三大 GPU 模組
2. **雙軌 Topic 設計**：State 連續快照供 LLM 語境；Event 離散事件供 Executive 仲裁 — 同一資料兩種消費型態
3. **Hysteresis 穩定化**：upper/lower 雙閾值 + stable_hits + unknown_grace — 處理真實 noise 比單閾值好
4. **IOU 追蹤無 re-ID**：人離開再回來拿新 track_id，是 demo 範圍取捨（人臉 DB 已能提供身份延續）
5. **Folder-per-person + 自動 retrain**：DB schema 對非工程使用者友善（拖照片進資料夾就行）
6. **Brain 抑制窗（P1-2）**：reset_context 後 5s 不寫 speaker，「新對話」感的工程實作

---

## 15. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| 核心邏輯 | `face_perception/face_perception/face_identity_node.py` |
| 設定 | `face_perception/config/face_perception.yaml` |
| 啟動 | `face_perception/launch/face_perception.launch.py` |
| 模組文件 | `docs/pawai-brain/perception/face/README.md` + `CLAUDE.md` + `AGENT.md` |
| Benchmark 決策 | `docs/pawai-brain/perception/face/research/2026-03-21-benchmark-decision.md` |
| Contract schema | `docs/contracts/interaction_contract.md` §4.2 + §4.7 |
| 啟動腳本 | `scripts/start_face_identity_tmux.sh` |
