# 人臉辨識（YuNet + SFace）

本文件只保留目前有效流程與最新排障結果。

- 主線目標：先把 `YuNet + SFace` 在 Jetson 上穩定跑通、可監看、可量測。
- 目前狀態：可用（多人偵測 + identity + Foxglove 監看）。
- 已暫停：Go2 互動控制 MVP（本輪未成功，相關內容先移除，後續另開章節）。

---

## 目前有效架構

資料流：

1. RealSense RGB topic：`/camera/camera/color/image_raw`
2. 偵測/辨識：`scripts/face_identity_infer_cv.py`
3. 輸出 topic：
   - `/face_identity/debug_image`
   - `/face_identity/compare_image`（可關閉）
4. 監看：`foxglove_bridge` + Foxglove App

模型：

- YuNet：`/home/jetson/face_models/face_detection_yunet_legacy.onnx`
- SFace：`/home/jetson/face_models/face_recognition_sface_2021dec.onnx`

> 註：本專案在 Jetson OpenCV 4.5.4 上，`2023mar` YuNet 會有相容性問題，已改用 `legacy` 版本。

---

## 2026-03-08 今日遇到問題與解法

### 1) 啟動辨識按鈕沒反應

現象：前端按下 `Start Recognition` 無效果。

根因：

- 前端舊版硬寫 API 位址（跨 IP 情境會 `Failed to fetch`）。
- infer 程式啟動後因 YuNet 模型相容性直接崩潰。

解法：

- 前端改同源 `/api/*` 代理。
- 後端固定改用 `face_detection_yunet_legacy.onnx`。

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

## 標準啟動（Jetson，建議）

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
  --yunet-model /home/jetson/face_models/face_detection_yunet_legacy.onnx \
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

## 後續（下一輪）

- 再整理成 `start_face_identity.sh` / `stop_face_identity.sh`（一鍵啟停與自動清場）。
- 針對不同場景建立 threshold preset（白天/夜間/逆光）。
- Go2 互動控制另開文件與驗收計畫（本輪先不納入本 README）。
