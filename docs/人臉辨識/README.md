# 人臉辨識（YuNet 2023mar + SFace）

本文件只保留目前有效流程與最新排障結果。

- 主線目標：`YuNet 2023mar + SFace` 在 Jetson 上穩定跑通、可監看、可量測。
- 目前狀態：**USABLE** — Jetson smoke passed（2026-03-18），QoS 修正（2026-03-23），YuNet 升級 2023mar（2026-03-25）。
- **Benchmark 決策**：YuNet 2023mar CPU 71.3 FPS（JETSON_LOCAL），備援 SCRFD-500M（JETSON_LOCAL）。
- 已暫停：Go2 互動控制 MVP（本輪未成功，相關內容先移除，後續另開章節）。

---

## 目前有效架構

資料流：

1. RealSense RGB + Depth topic：`/camera/camera/color/image_raw` + `aligned_depth_to_color`
2. 偵測/辨識/追蹤：`face_perception/face_perception/face_identity_node.py`（ROS2 package）或 `scripts/face_identity_infer_cv.py`（fallback）
3. 輸出 topic：
   - `/face_identity/debug_image` — debug 影像（帶框）
   - `/face_identity/compare_image`（可關閉）
   - **`/state/perception/face`** — 結構化狀態 JSON（2026-03-16 新增）
   - **`/event/face_identity`** — 身份事件 JSON（2026-03-16 新增）
4. 監看：`foxglove_bridge` + Foxglove App，或 `ros2 topic echo`

### ROS2 Topic 發布（2026-03-16 新增）

`face_identity_infer_cv.py` 現在發布兩個標準 topic（對齊 `interaction_contract.md` v2.0）：

**`/state/perception/face`**（每 tick 發布，`std_msgs/String` JSON）：
```json
{"stamp": 1773926400.0, "face_count": 2, "tracks": [
  {"track_id": 1, "stable_name": "Roy", "sim": 0.42, "distance_m": 1.25, "bbox": [100,150,200,280], "mode": "stable"},
  {"track_id": 2, "stable_name": "unknown", "sim": 0.18, "distance_m": 2.1, "bbox": [300,180,380,300], "mode": "hold"}
]}
```

**`/event/face_identity`**（狀態變化時觸發）：
- `track_started` — 新 track 出現
- `identity_stable` — 身份穩定化通過（unknown → 具名）
- `identity_changed` — 身份變更
- `track_lost` — track 消失

這些 topic 被 `llm_bridge_node` 訂閱，用於 LLM context 和人臉觸發互動。

模型：

- YuNet：`/home/jetson/face_models/face_detection_yunet_2023mar.onnx`（**2023mar 版本，CPU 71.3 FPS**）
- SFace：`/home/jetson/face_models/face_recognition_sface_2021dec.onnx`

> **2026-03-25 更新**：經 Benchmark 實測（見 `benchmarks/results/archive/`），主線已升級為 **YuNet 2023mar**。先前 legacy 版本因 OpenCV 相容性問題使用，現已解決。備援為 SCRFD-500M（JETSON_LOCAL）。

---

## 2026-03-08 今日遇到問題與解法

### 1) 啟動辨識按鈕沒反應

現象：前端按下 `Start Recognition` 無效果。

根因：

- 前端舊版硬寫 API 位址（跨 IP 情境會 `Failed to fetch`）。
- infer 程式啟動後因 YuNet 模型相容性直接崩潰。

解法：

- 前端改同源 `/api/*` 代理。
- 後端固定改用 `face_detection_yunet_2023mar.onnx`（原為 legacy，3/25 升級）。

---

### 2) 只能辨識一人

現象：同畫面多人時只認一張臉。

根因：舊邏輯只取最大臉（single-face path）。

解法：

- `scripts/face_identity_infer_cv.py` 已改為多臉處理 + track。
- 新增參數：
  - `--max-faces`
  - `--track-iou-threshold`
  - `--track-max-misses`

---

### 3) Foxglove 延遲很大（到分鐘級）

現象：影像明顯累積延遲，操作像卡住。

根因：

- 重複啟動多個流程（多個 `realsense2_camera_node` / `infer` / `bridge`）。
- 同時發布與訂閱高頻大圖（尤其 compare 拼接圖）。

解法：

- 嚴格單例：`1x camera + 1x infer + 1x bridge`。
- 降載：
  - `--publish-fps 8`
  - `--no-publish-compare-image`
- Foxglove 先只看 `/face_identity/debug_image`。

---

### 4) Foxglove 顯示 topic 不存在 / 黑畫面

常見根因與解法：

- 選錯 topic：
  - 人臉辨識請看 `/face_identity/debug_image`
  - 不要看 `/face_look_at/debug_image`（那是另一支腳本）
- Image panel 設錯：Calibration 填到 image topic。
  - `Calibration` 清空
  - `Rectify` 關閉
- `foxglove_bridge` bind error：8765 已被佔用。
  - 直接沿用既有 bridge，或換 port（如 8766）

---

### 5) ROS2 指令失效（`ros2: command not found`）

根因：zsh 環境被污染（`COLCON_CURRENT_PREFIX` 指到錯誤路徑）。

解法：

```bash
bash
unset COLCON_CURRENT_PREFIX COLCON_PREFIX_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH
source /opt/ros/humble/setup.bash
```

---

### 6) 相機色彩流消失（`/camera/camera/color/image_raw` publisher=0）

根因：RealSense 程序重複或裝置忙碌（`Device or resource busy`）。

解法：

- 先清掉所有重複 realsense 程序再啟動單一實例。

---

## ROS2 Package 啟動（推薦）

```bash
# 前提：已 colcon build --packages-select face_perception && source install/setup.zsh

# 一鍵啟動（camera + node + foxglove_bridge）
bash scripts/start_face_identity_tmux.sh

# 或手動 launch（需另外啟動 camera 和 foxglove_bridge）
ros2 launch face_perception face_perception.launch.py

# 自訂 config
ros2 launch face_perception face_perception.launch.py \
  config_file:=/path/to/custom.yaml

# 單獨啟動 node（不用 launch file）
ros2 run face_perception face_identity_node --ros-args \
  -p det_score_threshold:=0.35 \
  -p headless:=true
```

清場：

```bash
bash scripts/clean_face_env.sh --all
```

> **Fallback**：若 ROS2 package 有問題，原始 script 仍可用（見下方「手動啟動」章節）。

---

## 手動啟動（Fallback / 舊方式）

先清場：

```bash
bash
unset COLCON_CURRENT_PREFIX COLCON_PREFIX_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH
source /opt/ros/humble/setup.bash

pkill -f face_identity_infer_cv.py || true
pkill -f realsense2_camera_node || true
pkill -f "ros2 launch realsense2_camera rs_launch.py" || true
pkill -x foxglove_bridge || true
pkill -f "ros2 launch foxglove_bridge foxglove_bridge_launch.xml" || true
```

Terminal A（相機）：

```bash
bash
unset COLCON_CURRENT_PREFIX COLCON_PREFIX_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH
source /opt/ros/humble/setup.bash
ros2 launch realsense2_camera rs_launch.py \
  depth_module.profile:=640x480x30 \
  rgb_camera.profile:=640x480x30 \
  align_depth.enable:=true
```

Terminal B（人臉辨識）：

```bash
bash
unset COLCON_CURRENT_PREFIX COLCON_PREFIX_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH
source /opt/ros/humble/setup.bash
python3 /home/jetson/elder_and_dog/scripts/face_identity_infer_cv.py \
  --db-dir /home/jetson/face_db \
  --model-path /home/jetson/face_db/model_sface.pkl \
  --yunet-model /home/jetson/face_models/face_detection_yunet_2023mar.onnx \
  --sface-model /home/jetson/face_models/face_recognition_sface_2021dec.onnx \
  --det-score-threshold 0.35 \
  --min-face-area-ratio 0.001 \
  --max-faces 5 \
  --publish-fps 8 \
  --no-publish-compare-image \
  --headless
```

Terminal C（Foxglove bridge）：

```bash
bash
unset COLCON_CURRENT_PREFIX COLCON_PREFIX_PATH AMENT_PREFIX_PATH CMAKE_PREFIX_PATH
source /opt/ros/humble/setup.bash
ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765
```

---

## Foxglove 監看設定

- 連線：`ws://<jetson-ip>:8765`
- 先開一個 `Image` 面板：`/face_identity/debug_image`
- 再視需要加：`/camera/camera/color/image_raw`
- 不建議同時開太多 image/depth 面板

---

## 驗收指標（每次測試都跑）

```bash
source /opt/ros/humble/setup.bash
ros2 topic hz /camera/camera/color/image_raw
ros2 topic hz /face_identity/debug_image
ros2 topic bw /face_identity/debug_image
ps -eo pid,pcpu,pmem,cmd --sort=-pcpu | head -n 15
```

通過標準（建議）：

- `/face_identity/debug_image` 穩定 > 6 Hz
- 無重複核心流程（camera/infer/bridge 各 1）
- Foxglove 延遲維持秒級內

---

## 已修復問題（2026-03-18 ~ 03-23）

- **np.int32 JSON 序列化 crash**：`to_bbox()` 回傳 `np.int32`，`json.dumps` 無法序列化。修復：bbox 座標轉 Python `int()`。（commit `ca1547d`）
- **Jetson smoke 通過**：D435 + face_identity_node + foxglove_bridge 同時跑穩定，`/face_identity/debug_image` ~6.6 Hz，`/state/perception/face` ~20 Hz。
- **face_db 已更新**：alice 30 張、grama 30 張（自動 retrain）
- **QoS 修正（2026-03-23）**：D435 camera image subscription 從 `RELIABLE` 改為 `BEST_EFFORT`。RealSense ROS2 driver 預設發布 `BEST_EFFORT`，若 subscriber 用 `RELIABLE` 會導致收不到影像（QoS incompatible）。
- **YuNet 升級至 2023mar**（2026-03-25）：經 Benchmark 實測 CPU 71.3 FPS，取代先前的 legacy 版本。

---

## 後續（下一輪）

- ~~再整理成 `start_face_identity.sh` / `stop_face_identity.sh`~~ → ✅ 已完成（`scripts/start_face_identity_tmux.sh` + `scripts/clean_face_env.sh`）
- 針對不同場景建立 threshold preset（白天/夜間/逆光）。
- Go2 互動控制另開文件與驗收計畫（本輪先不納入本 README）。
- 與語音模組整合測試（Level 2 → Level 3）。

---

## ROS2 Package 結構

```
face_perception/
├── face_perception/
│   ├── __init__.py
│   └── face_identity_node.py    # 核心 node（from face_identity_infer_cv.py）
├── launch/
│   └── face_perception.launch.py
├── config/
│   └── face_perception.yaml     # Jetson operational defaults
├── test/
│   └── test_utilities.py        # 純函式 unit tests (13 cases)
├── setup.py
└── package.xml
```

參數完整對照表見 [implementation plan](../superpowers/plans/2026-03-17-face-perception-package.md)。
