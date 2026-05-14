# 人臉辨識（face_perception）

## 這個模組是什麼

Layer 2 感知模組，負責人臉偵測（YuNet）、識別（SFace cosine）、IOU 追蹤、深度估計。
它是 PawAI 的「眼」— 決定誰在畫面裡，讓 Brain 的 world_state_builder 知道當前說話者是誰（`current_speaker`）。
10Hz 持續發布 `/state/perception/face`，觸發式發布 `/event/face_identity`（4 種 event_type）。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/face/face.md` | 主總覽 + 架構圖 + 0511 freeze 快照 |
| `docs/pawai-brain/architecture/0511/face/face-recognition-tracking.md` | YuNet + SFace pipeline + IOU tracker 細節 |
| `docs/pawai-brain/architecture/0511/face/face-runtime-flow.md` | D435 → YuNet → SFace → 追蹤 → ROS2 publish 完整 flow |
| `docs/pawai-brain/architecture/0511/face/face-brain-executive-integration.md` | 與 Brain world_state_builder 的整合（current_speaker 注入）|
| `docs/pawai-brain/architecture/0511/face/face-registration-debug-runbook.md` | 人臉註冊流程 + 現場 debug checklist |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `face_perception/face_perception/face_identity_node.py` | 主 ROS2 節點（YuNet + SFace + IOU tracker + publish）|
| `face_perception/config/face_perception.yaml` | 模型路徑、閾值、Jetson 路徑設定 |
| `face_perception/launch/face_perception.launch.py` | 一鍵 launch（含 D435 camera）|
| `scripts/start_face_identity_tmux.sh` | tmux 一鍵啟動（D435 + face_identity_node + foxglove）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/state/perception/face` | face_identity_node → | 10Hz JSON，face_count + tracks[]（FaceState）|
| `/event/face_identity` | face_identity_node → | 觸發式 4 種 event_type（track_started / identity_stable / identity_changed / track_lost）|
| `/face_identity/debug_image` | face_identity_node → | 可視化 debug image（Foxglove Image panel, ~6.6Hz）|

## 已知陷阱

- **YuNet 版本**：必須用 2023mar（`face_detection_yunet_2023mar.onnx`），legacy 版本在 Jetson OpenCV 4.5.4 崩潰
- **人臉資料庫路徑**：`/home/jetson/face_db/{name}/*.png`，SFace embeddings pickle 需事先建立
- **距離估計 null**：D435 深度超出範圍時 `distance_m` 為 null，不要假設一定有值
- **不可並行多個 instance**：`face_identity_infer_cv.py` 或 node 搶占 D435 相機資源
- **QoS 設定**：D435 camera 用 BEST_EFFORT，state/event publish 用 RELIABLE VOLATILE（3/23 已修）
- **int32 序列化 bug**：`to_bbox()` 回傳 np.int32，json.dumps 不認識 → 必須轉 Python int（3/18 修）

## 開發入口

```bash
# 一鍵啟動（推薦）
bash scripts/start_face_identity_tmux.sh

# 手動啟動
ros2 launch face_perception face_perception.launch.py

# 驗證
ros2 topic echo /state/perception/face     # 10Hz JSON
ros2 topic echo /event/face_identity       # 走近 → track_started → identity_stable

# 清理
bash scripts/clean_face_env.sh --all
```
