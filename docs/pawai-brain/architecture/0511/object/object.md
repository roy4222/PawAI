# 物體辨識（object_perception）— 架構詳述

**版本**：2026-05-11 freeze 快照
**位置**：`object_perception/`（獨立套件）
**入口**：`object_perception/object_perception/object_perception_node.py`
**狀態**：5/12 demo 85% 完成（5/6 全鏈路驗證 PASS：12 色 + 中文 + brain TTS）

> 這份是 5/11 freeze 的原始總覽。5/12 後續開發請搭配同資料夾拆分文件閱讀，因為 object 的問題會同時出現在 YOLO 偵測、HSV 顏色、Brain cache、Executive 主動插話策略。

## 0. 拆分文件索引

- [object-runtime-flow.md](object-runtime-flow.md)：物體 runtime 架構、topic、ONNX/TensorRT provider、event schema。
- [object-color-and-detection.md](object-color-and-detection.md)：YOLO26n 後處理、COCO 80、HSV 12 色、顏色與小物件限制。
- [object-brain-executive-integration.md](object-brain-executive-integration.md)：`/event/object_detected` 如何進 Brain recent object cache 與 Executive `object_remark`。
- [object-debug-runbook.md](object-debug-runbook.md)：明天到學校現場排查順序。

---

## 1. 模組定位

物體辨識是 PawAI **環境感知層**的最後一塊，與 face（誰）/ pose（狀態）/ gesture（意圖）並列。它的工作是把鏡頭裡的 80 種 COCO 物件 + 12 種顏色轉成事件，餵給 Brain（語境 `[最近看到]`）與 Executive（規則式 TTS remark）。

**核心設計**：
- **獨立 ROS2 套件**（不混在 vision_perception 裡）
- **YOLO26n ONNX**（NMS-free 架構，9.5MB）on TensorRT EP FP16
- **HSV 12 色 bucket** 分類（非 K-means、非 ML）
- **無 tracking、無深度、無 DB**（與 face_identity 結構性不同 — 純偵測）
- **雙軌消費**：Brain 取語境（30s 視窗）+ Executive 規則 TTS（60s 去重）

**對外介面**：
- 訂閱：`/camera/camera/color/image_raw`（不訂深度）
- 發佈：`/event/object_detected`（事件觸發）+ `/perception/object/debug_image`

**效能**：~15 FPS 穩定（4/4 Phase B 70s 零掉幀，+1GB RAM, 56°C, 8.9W）

---

## 2. Pipeline 全貌（6 stage）

```
┌──────────────────────────────────────────────────────────────────────┐
│      D435 RGB only  (/camera/camera/color/image_raw) — 不訂深度!     │
└──────────────────────────────────────────────────────────────────────┘
                                  │  BEST_EFFORT
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│       ObjectPerceptionNode  (tick=0.067s ≈ 15Hz, single-thread)      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 1: Letterbox 預處理                                        │ │
│  │   (H,W,3) BGR uint8                                              │ │
│  │   → letterbox 至 640×640（中心 + 灰色 padding=114）              │ │
│  │   → / 255.0 → float32                                            │ │
│  │   → transpose CHW → (1, 3, 640, 640)                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 2: YOLO26n ONNX 推理                                       │ │
│  │   Model:  /home/jetson/models/yolo26n.onnx (9.5MB)               │ │
│  │   Providers fallback chain:                                      │ │
│  │     TensorrtEP (FP16 + cache) → CUDAEP → CPUEP                   │ │
│  │   Cache:  /home/jetson/trt_cache/                                │ │
│  │   First launch: 3-10 分鐘編譯；後續即時                          │ │
│  │   Output: (1, 300, 6) ★NMS-free★                                 │ │
│  │           [x1, y1, x2, y2, conf, class_id] × 300                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 3: 後處理 + 過濾                                            │ │
│  │   conf ≥ confidence_threshold (0.5)                              │ │
│  │   class_id ∈ allowed_classes（whitelist 或全 80）                │ │
│  │   bbox: letterbox-space → original 像素座標（rescale_bbox）      │ │
│  │   x2 > x1 AND y2 > y1（非零驗證）                                │ │
│  │   ★ bbox 強制 int()（避免 np.int32 JSON 不認）★                 │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 4: HSV 12 色分類（analyze_bbox_color）                     │ │
│  │   crop = image[y1:y2, x1:x2] → cvtColor BGR2HSV                 │ │
│  │   priority masks（互斥）:                                        │ │
│  │     1. black:  V < 50                                            │ │
│  │     2. white:  S < 40 AND V ≥ 200                                │ │
│  │     3. gray:   S < 40 AND 50 ≤ V < 200                           │ │
│  │     4. brown:  chromatic + H∈[5,25] + V<130（暖色暗）            │ │
│  │     5. pink:   chromatic + 紅/品紅側 + 高 V 低 S                 │ │
│  │     6-12. red / orange / yellow / green / cyan / blue / purple   │ │
│  │   counts per mask → peak / total = ratio                         │ │
│  │   IF ratio < 0.25: return ("Unknown", 0.0)                       │ │
│  │   ELSE: return (peak_name, ratio)                                │ │
│  │   ★ 沒有深度估距 — 純 RGB（與 face 不同！）★                    │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 5: Per-class cooldown（class_cooldown_sec=5.0）            │ │
│  │   self._cooldowns[class_name] = ts                               │ │
│  │   IF now - last < 5.0: skip 該物體                               │ │
│  │   strip class_id（內部用）                                       │ │
│  │   color 條件加入：只有 color != "Unknown" 才放                   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 6: 雙軌發佈                                                │ │
│  │   /event/object_detected  (JSON)  — 事件觸發                     │ │
│  │   /perception/object/debug_image  (8 Hz 限頻，bbox + 中文標籤)   │ │
│  │   ★ 沒有 /state/perception/object（與 face 不同！）★            │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. HSV 12 色分類細節

**設計**：純規則 priority gates（V/S 優先於 hue），互斥 mask，return (peak, ratio)。

| # | Label | 規則 | 為什麼特殊 |
|---|-------|------|------|
| 1 | black | V < 50 | 純亮度 gate（最暗）|
| 2 | white | S < 40 AND V ≥ 200 | 低彩度 + 高亮度 |
| 3 | gray | S < 40 AND 50 ≤ V < 200 | 低彩度 + 中亮度 |
| 4 | brown | chromatic + H ∈ [5,25] + V < 130 | 暖色 + 暗（咖啡色椅子）|
| 5 | pink | (H ≥ 160 OR H ≤ 5 + S < 150 + V ≥ 180) OR (150 < H < 165) | 紅/品紅側 + 高 V 低 S |
| 6 | red | H ≤ 8 OR H ≥ 165 | 純紅（已排除 brown / pink）|
| 7 | orange | 8 < H ≤ 22 | 暖色帶 |
| 8 | yellow | 22 < H ≤ 35 | 黃色帶 |
| 9 | green | 35 < H ≤ 85 | 綠色（範圍大）|
| 10 | cyan | 85 < H ≤ 100 | 青色帶 |
| 11 | blue | 100 < H ≤ 130 | 藍色帶 |
| 12 | purple | 130 < H ≤ 150 | 紫色帶 |

**回傳 Unknown 條件**：peak / total < 0.25（太破碎，多色表面）。

**為什麼 V/S 先於 hue**：
- 橘色 hue 在 [5,25]，但咖啡色 V 要 < 130 才能分出來（不然會被誤判為橘）
- 粉紅在紅/品紅側，但 S 必須低才能與純紅分開

---

## 4. Topic Schema（v2.5 凍結）

### `/event/object_detected`

```json
{
  "stamp": 1715425123.4567,
  "event_type": "object_detected",
  "objects": [
    {
      "class_name": "cup",            // COCO underscored（dining_table 不是 "dining table"）
      "confidence": 0.894,             // YOLO 偵測信心
      "bbox": [123, 456, 234, 567],   // Python int!
      "color": "red",                  // 12 色 enum；★Unknown 時欄位省略★
      "color_confidence": 0.75         // 配對欄位，省略也一起
    },
    {
      "class_name": "person",
      "confidence": 0.921,
      "bbox": [50, 100, 400, 600]
                                       // 沒 color 因為低於 0.25
    }
  ]
}
```

**QoS**：Reliable, Volatile, depth=10
**頻率**：事件觸發 + per-class 5s cooldown（防止 spam）
**沒有 `/state/perception/object`**：純事件流，狀態快取在下游 Brain 端做

---

## 5. 與 face 模組的對照（結構性差異）

| 面向 | object_perception | face_identity |
|------|-------------------|---------------|
| 模型 | YOLO26n（單一） | YuNet + SFace（雙模型）|
| Tracking | **無**（每幀獨立偵測）| IOU + track_id 持續 |
| DB / 識別 | **無**（class enum）| embedding pickle 比對 |
| 深度估距 | **無**（只訂 color topic）| median ROI depth |
| State topic | **無** | `/state/perception/face`（8Hz）|
| 去重 | per-class 5s cooldown（時間）| per-track IOU 配對（空間）|
| 顏色分析 | **HSV 12 色 bucket** | 無 |
| Tick rate | 15 Hz | 20 Hz |
| GPU 用量 | TensorRT FP16（GPU）| CPU only（YuNet）|

---

## 6. 消費者拓撲

```
                  object_perception_node
                           │
                           ▼
                 /event/object_detected
                           │
   ┌───────────────────────┼─────────────────────┐
   │                       │                     │
   ▼                       ▼                     ▼
┌──────┐         ┌──────────────────┐      ┌──────────┐
│Brain │         │Executive         │      │Studio    │
│      │         │brain_node._on_   │      │gateway   │
└──────┘         │object()          │      └──────────┘
   │             └──────────────────┘            │
   │                       │                     ▼
   │             ★ 規則式 TTS（非 LLM）★    PawAIEvent
   │             D-3 emit gate（全條件 AND）:    source="object"
   │              ├ AttentionState == ENGAGED   event_type=
   │              ├ 沒有 active skill            "object_detected"
   │              ├ 沒有 pending confirm        → 前端
   │              └ TTS 沒在播                    Perception panel
   │             build_object_tts(class, color)
   │              └ TTS 白名單 ~32 類           
   │              └ 「看到{COLOR_ZH}的{class_zh}了」
   │             per-(class,) 60s dedup
   │              ★ color 不進 key（吸收 YOLO 顏色抖動）★
   │             ★ person 直接 return（避免與 face/stranger 撞）★
   │             → emit_with_cooldown("object_remark")
   │
   ▼  pawai_brain._on_object_detected
   self._world_snapshot.apply_object_detected_json(msg.data)
       │
       ▼
   WorldStateSnapshot 兩層過濾（N5-A）:
     1. exclude_classes = ("person",)  ← face_identity 擁有人
     2. color_confidence < 0.6 → 丟掉 color（精度 > 豐富度）
     3. 每 class 保留最新一筆（latest-wins，deque maxlen=8）
       │
       ▼
   world_state_builder.get_recent_objects(window_s=30.0)
     讀取時計算 age_s = now - ts
     filter: age_s ≤ 30s
       │
       ▼
   _format_recent_objects():
     翻譯：_OBJECT_CLASS_ZH (cup→杯子, chair→椅子...)
            _OBJECT_COLOR_ZH (red→紅色, brown→咖啡色...)
     未知 class → 靜默跳過（不漏 raw English）
     格式：「紅色的杯子（5 秒前）」/「杯子（5 秒前）」
     ★ 上限 3 筆（多了是噪音）★
       │
       ▼
   LLM Prompt 注入 [最近看到] 紅色的杯子（5 秒前）、藍色的椅子（18 秒前）
     ★ 在所有 mode 都注入（chat/capability/identity/scene_query）★
```

**重點**：
- **Brain 取語境** → 30s 滑動視窗、per-class 最新、color 0.6 信心門檻、person 排除
- **Executive 規則 TTS** → AttentionState gate + 60s dedup + 32 類 TTS 白名單
- **沒有 vision_perception interaction_router**（v2.2 後 deprecated，object 不走那路）

---

## 7. Brain 端三類感知層的語意對照（N3-A / N5-B / N5-C）

| 層 | 語意 | 快取策略 | 過期 |
|------|------|---------|------|
| **Object** (N3-A) | 持續觀察的證據 | 30s 視窗 + per-class 最新 | window 過 → 看不到 |
| **Pose** (N5-B) | 持續狀態 | 單筆 + age_s | 不過期（state-like）|
| **Gesture** (N5-B) | 一次性事件 | 8s 視窗 + (gesture, hand) 5s 內去重 | window 過 → 看不到 |

設計動機：
- pose 不能 30s 過期 → 否則人坐著不動 5 分鐘 LLM 會說「沒看到姿勢」
- gesture 必須短期 → 舊手勢當作目前狀態會誤導
- object 用 window 是因為連續偵測，需要吸收雜訊

完整 spec：`docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md`

---

## 8. Executive 端規則 TTS（brain_node._on_object）

完整條件 AND（D-3 emit gate）：

```python
def _on_object(self, msg: String) -> None:
    # Emit 條件（必須全過）
    if self._attention_state_snapshot() != AttentionState.ENGAGED:
        return  # 人沒停下來
    if self._has_active_skill_or_sequence():
        return
    if self._pending_confirm.state == ConfirmState.PENDING:
        return
    if snap.tts_playing:
        return  # 不打斷 PawAI 自己說話
    
    objects = payload.get("objects")
    det = objects[0]  # 只取第一個
    class_name = det.get("class_name")
    color = det.get("color")
    
    # 取 TTS 文字（白名單 + 模板）
    text = build_object_tts(class_name, color)
    if text is None:
        return  # 不在 ~32 類白名單
    
    # 60s 去重（key 不含 color，吸收 YOLO 顏色抖動）
    seen_key = (class_name,)
    if now - self._object_remark_seen.get(seen_key, 0) < 60:
        return
    self._object_remark_seen[seen_key] = now
    
    self._emit_with_cooldown(
        "object_remark",
        args={"text": text, "label": class_name, "color": color},
        source="rule:object_detected",
    )
```

**為什麼 dedup key 不含 color**：YOLO 顏色抖動嚴重（brown_chair → coffee_chair 在幾秒內切換），若 key 含 color 會繞過 60s dedup 連發。

**為什麼 person 排除**：5/7 commit `e1363c8` 修了「看到黑色的人了」這種尷尬句子，避免與 face_identity 的 stranger_alert 路徑撞。

---

## 9. Face DB 管理 / Class Whitelist

### 原始 P0 6 類（4/13）
```python
class_whitelist: [0, 16, 39, 41, 56, 60]  # person, dog, bottle, cup, chair, dining_table
```
聚焦居家核心物件（人 / 寵物 / 家具 / 小物件）。

### 目前（v0.2，4/14 onwards）
```yaml
class_whitelist: []   # 全 80 類
```
- **UI 顯示**：Foxglove / Studio panel 全 80（最大可見性）
- **Brain TTS 白名單**：~32 類（cup/bottle/book/person/dog/cat/chair/couch/bed/dining_table/tv/laptop/cell_phone/remote/keyboard/mouse/backpack/handbag/umbrella/clock/vase/potted_plant/teddy_bear/scissors/wine_glass/fork/knife/spoon/bowl/banana/apple/orange）
- 拒絕的 48 類：frisbee/skis/baseball_bat 之類室外物件 → 避免「碎念飛盤」

---

## 10. 模型選型（YOLO26n 主線，YOLO26s 候選）

| 模型 | 參數量 | mAP | T4 TRT (ms) | 大小 | 決策 |
|------|:----:|:----:|:----:|:----:|:----:|
| **YOLO26n** | 2.4M | 40.1% | 1.4 | 9.5MB | **主線（5/12 demo）**|
| YOLO26s | 9.7M | 47.1% (**+6.3%**) | 2.1 | ~20MB | post-demo 候選 |
| YOLO11n | 2.6M | 39.5% | 1.5 | — | 拒用（mAP 輸）|
| YOLO11s | 9.4M | 47.0% | 2.5 | — | 拒用（同等精度但慢）|

**為什麼 YOLO26 而非 YOLO11**：NMS-free 架構（end-to-end TensorRT 編譯，固定延遲，無 anchor boxes）。
**為什麼 nano 而非 small**：5/12 demo 時間壓力，nano 已驗 15 FPS 穩定；YOLO26s 留作 post-demo 升級（目標小物件 cup/book/bottle 改善）。

---

## 11. 關鍵設定（object_perception.yaml）

```yaml
object_perception_node:
  ros__parameters:
    model_path: "/home/jetson/models/yolo26n.onnx"
    trt_cache_dir: "/home/jetson/trt_cache/"
    color_topic: "/camera/camera/color/image_raw"
    confidence_threshold: 0.5         # YOLO 信心門檻
    input_size: 640                   # letterbox 邊長
    tick_period: 0.067                # ~15 Hz
    publish_fps: 8.0                  # debug image 限頻
    class_cooldown_sec: 5.0           # publisher 端 per-class 去重
    # class_whitelist: [0, 16, 39, 41, 56, 60]  # 預設 [] = 全 80
```

下游消費者參數：
```python
# pawai_brain world_snapshot.py
_OBJECT_RECENT_MAXLEN = 8          # 快取上限
_OBJECT_WINDOW_S      = 30.0       # 視窗秒數
_COLOR_CONFIDENCE_MIN = 0.6        # color 信心門檻
_OBJECT_EXCLUDE_CLASSES = ("person",)

# interaction_executive brain_node.py
OBJECT_REMARK_DEDUP_S = 60         # 60s per-class TTS 去重
```

---

## 12. CLAUDE.md 強制規則（已知陷阱）

1. **絕對不要 `pip install ultralytics`** — 會破壞 Jetson torch wheel（4/4 環境救援過）
2. **TensorRT provider 值必須是 `"True"` / `"False"` 字串**，不是 `True` / `"1"` — 錯了會 silent fallback 到 CPU
3. **`class_whitelist: []` 必須用 `ParameterDescriptor(INTEGER_ARRAY)`** — 否則 rclpy 推不出型別
4. **bbox 必須 `int()` 轉 Python int** — JSON 不認 np.int32（face_identity 踩過同樣坑）
5. **letterbox 必須做反變換** — YOLO 輸出在 640×640 letterboxed 空間，須 inverse pad + scale
6. **TRT cache 首次 3-10 分鐘** — 後續即時，node 會 log 警告
7. **模型路徑凍結** `/home/jetson/models/yolo26n.onnx`
8. **不要還原 12→4 色** — brown/pink/black/gray/white 在 5/6 demo 全部 shipped
9. **跨套件不要 import `coco_classes`** — 三份同步字典：
   - `object_perception/coco_classes.py` — `COCO_CLASSES_ZH` + `COLOR_ZH`
   - `interaction_executive/brain_node.py` — `OBJECT_CLASS_ZH` + `OBJECT_COLOR_ZH`
   - `pawai-studio/frontend/object-config.ts` — `COLOR_ZH`
10. **person class 在 Brain TTS 端要 mute** — 避免與 face / stranger_alert 路徑碰撞

---

## 13. Demo Silence 雙重關閉（與 fallen 類似的設計）

| 路徑 | 狀態 | 原因 |
|------|------|------|
| object_perception_node 發 person | 仍發 | UI 可顯示 |
| Brain world_snapshot 過濾 person | **排除**（N5-A）| face_identity 擁有人 |
| Executive brain_node._on_object person | **靜默**（commit e1363c8 fix）| 與 stranger_alert 路徑撞 |

避免「看到黑色的人」這種尷尬句子。

---

## 14. 測試覆蓋

`object_perception/test/test_object_perception.py` — **37 個測試 PASS**

| Class | Tests | 涵蓋 |
|------|:----:|------|
| TestCocoClasses | 6 | 80 類連續、underscore 命名、P0 子集驗證 |
| TestClassColor | 4 | 顏色 BGR 決定性、tuple、80 類無 crash |
| TestLetterbox | 6 | 形狀（方/非方）、scale（橫/直）、padding 色、內容保留 |
| TestRescaleBbox | 4 | 恆等、scale+padding、clamp、Python int 返回 |
| TestRoundtrip | 1 | letterbox→rescale 來回 ±1px |
| TestDedup | 4 | 新類發、cooldown 內擋、跨類發、過期重發 |
| TestEventSchema | 2 | 結構、bbox int |
| TestZhLookup | 3 | 80 類中文、未知 fallback "物件" |
| TestColorEventGate | 3 | Unknown 省欄位、已知放欄位、class_id 不外露 |

### Brain 端測試
- `test_world_snapshot.py`（11 測試）：class 去重 / color gate / person filter / window 過濾
- `test_user_message_builder.py`（9 測試）：prompt 注入 / 未知 class 跳過 / 顏色翻譯 / N5-A filters

---

## 15. Demo 整合

`scripts/start_full_demo_tmux.sh` window 9：
```bash
tmux send-keys -t "$SESSION:object" \
  "$ROS_SETUP && ros2 launch object_perception object_perception.launch.py" Enter
```

`scripts/clean_full_demo.sh` 同步清理。

---

## 16. 近期重要 commit

| Hash | 日期 | 內容 |
|------|------|------|
| 561d6ab | 5/11 | N3 demo-host harness — recent_objects JIT 注入 |
| e1363c8 | 5/7 | **A-class fix**：person class TTS 靜默（避免 stranger 碰撞）|
| 685c97d | 5/7 | **A-class fix**：per-(class,) 60s dedup（吸收顏色抖動）|
| d7e29c5 | 5/6 | 文件同步：12 色 + zh + brain TTS 全鏈路 |
| 545cd33 | 5/5 | event schema v2.5：color + color_confidence 加入 |
| 4694fb9 | 4/19 | Executive 整合 — cup/bottle/book 3 類 TTS |
| 4c0e026 | 4/14 | 擴充至 COCO 80 + class_whitelist 參數 |
| 37f06c0 | 4/13 | Phase C：Jetson 5 分鐘穩定性 PASS |

---

## 17. 未來工作

**Post-demo 路線**：
- [ ] **yolo26s 升級評估** — benchmark mAP / size / Jetson FPS / 小物件偵測率
- [ ] **Input size 640 → 960 A/B** — 解小物件問題
- [ ] **室內 dataset fine-tuning** — OpenImages / Objects365 微調
- [ ] **Flat object handling**（書 / 手機平放） — 光學 + 角度 + 閾值調整
- [ ] **Tracking + 3D depth** — D435 深度整合（目前 design 有但未接）

---

## 18. 關鍵設計決策（給寫計畫書的參考）

1. **YOLO26 選型故事**：NMS-free 架構 + TensorRT FP16 + nano vs small 的 demo 妥協
2. **完整 6-stage pipeline**（第二節圖）
3. **HSV 12 色設計**（第三節）：為什麼是 12 色而非 RGB / K-means — 解釋 V/S 優先順序的設計
4. **與 face 模組的對照表**（第五節）：說明「為什麼 face 有 tracking + DB + depth，object 都沒有」是 demo 範圍取捨
5. **N3-A / N5-A 設計**（第七節）：30s 視窗 + per-class 最新 + 0.6 color gate + person 排除 — 四層過濾保護 LLM 不被噪音灌爆
6. **雙軌消費**（第六節圖）：Brain 取語境 vs Executive 規則 TTS — 同一事件兩種用法不衝突
7. **TTS 白名單 vs UI 全顯示**：32 vs 80 的分工（demo 不希望機器人碎念飛盤）
8. **Demo silence person**（第十三節）：與 fallen demo silence 是同樣設計哲學
9. **十大 CLAUDE.md 陷阱**（第十二節）：寫進「Jetson 環境硬規則」一節

---

## 19. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| Node 主檔 | `object_perception/object_perception/object_perception_node.py` |
| COCO 80 + 中文 | `object_perception/object_perception/coco_classes.py` |
| Brain handler | `pawai_brain/pawai_brain/conversation_graph_node.py::_on_object_detected` |
| Brain 快照 N3-A/N5-A | `pawai_brain/pawai_brain/capability/world_snapshot.py` |
| Executive 路由 | `interaction_executive/interaction_executive/brain_node.py::_on_object` |
| 設定 | `object_perception/config/object_perception.yaml` |
| 啟動 | `object_perception/launch/object_perception.launch.py` |
| Contract schema | `docs/contracts/interaction_contract.md` §4.8 |
| 模組文件 | `docs/pawai-brain/perception/object/README.md` + `CLAUDE.md` |
| 選型研究 | `docs/pawai-brain/perception/object/research/2026-03-25-object-detection-feasibility.md` |
| N5 scene spec | `docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md` |
