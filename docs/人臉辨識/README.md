# 人臉辨識

> Status: current

> YuNet 偵測 + SFace 識別 + IOU 追蹤，即時辨認已知人物並觸發互動。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | 整合測試通過 |
| 版本/決策 | YuNet 2023mar (CPU 71.3 FPS) + SFace 2021dec |
| 完成度 | 95% |
| 最後驗證 | 2026-03-25 |
| 入口檔案 | `face_perception/face_perception/face_identity_node.py` |
| 測試 | `python3 -m pytest face_perception/test/ -v` |

## 啟動方式

```bash
# 一鍵啟動（推薦）
bash scripts/start_face_identity_tmux.sh

# 或手動
ros2 launch face_perception face_perception.launch.py
```

## 核心流程

```
RealSense D435 RGB + Depth
    |
face_identity_node（YuNet 偵測 -> SFace embedding -> IOU 追蹤）
    |
/state/perception/face（10Hz JSON：face_count, tracks[{track_id, stable_name, sim, distance_m, bbox}]）
/event/face_identity（觸發式：track_started / identity_stable / identity_changed / track_lost）
    |
interaction_executive_node 訂閱 -> WELCOME 觸發 -> TTS 問候
```

**Hysteresis 穩定化**（4/6 Jetson 調參）：
- `sim_threshold_upper`: 0.35 → **0.30**，`sim_threshold_lower`: 0.25 → **0.22**
- `track_iou_threshold`: **0.15**，`track_max_misses`: **20**，`stable_hits`: **2**，`unknown_grace_s`: **2.5**
- 調參後 2 分鐘 smoke test：`identity_stable: roy` 21 次（調前 1-3 次），零誤認
- **已知限制**：track 抖動仍在（45 tracks/2min，目標 ≤5），根因是 YuNet 偵測不穩定

**face_db**：`/home/jetson/face_db/`，目前有 roy、grama 兩人。

## 輸入/輸出

| Topic | 方向 | 說明 |
|-------|:----:|------|
| `/state/perception/face` | 輸出 | 人臉狀態 10Hz JSON |
| `/event/face_identity` | 輸出 | 身份事件（觸發式） |
| `/face_identity/debug_image` | 輸出 | Debug 影像 ~6.6Hz |

## 模型路徑（Jetson）

- YuNet：`/home/jetson/face_models/face_detection_yunet_2023mar.onnx`
- SFace：`/home/jetson/face_models/face_recognition_sface_2021dec.onnx`

## 已知問題

- 模型路徑硬編碼 `/home/jetson/face_models/`
- face_db 只有 2 人，Demo 可能需擴充
- OpenCV 版本限制（Jetson 4.5.4）

## 下一步

- Sprint B-prime Day 1-3：上機驗證 + baseline 穩定化
- Sprint Day 4-5：整合進 executive v0
- Clean Architecture 重構（4/13 後，詳見 `docs/research/2026-03-25-go2-sdk-capability-and-architecture.md` S5.4）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 模型選型研究（YuNet vs ArcFace vs SCRFD） |
| archive/ | 初階開發者分工指南（3/8，已無人使用） |
