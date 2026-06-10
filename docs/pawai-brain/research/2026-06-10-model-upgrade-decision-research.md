# 2026-06-10 模型升級決策研究（object / pose / D435 曝光）

> 來源：deep-research workflow（104 agents；**對抗驗證階段因 session 限額中斷**——
> 除特別標註外，以下 claim 為「已從一手來源抽取、未完成 3 票對抗驗證」，
> 引用時自行斟酌。最終決策一律以 Jetson 實機 A/B 為準。

## 1. Object：YOLO26n@640 → 候選升級

**已驗證（3-0）**：YOLO26 全系列預設 end-to-end NMS-free，`model.export(format="onnx")`
不需額外旗標即得 NMS-free ONNX；`end2end=False` 可切回傳統 NMS 路徑。
（docs.ultralytics.com/guides/end2end-detection）

**未驗證但一手來源**：
- YOLO26n TRT FP16 在 **Orin Nano Super** Devkit 約 4.57ms/img @640（mAP50-95 0.480，
  FP16 不掉精度）。注意是 Super（67 TOPS）非我們的原版 Orin Nano 8GB → 我們會更慢。
- n→s 升級代價：YOLO26n ~39.8% mAP / YOLO26s ~47.2% mAP（**+7.4 mAP**），CPU 延遲
  ~2.2 倍；T4 TRT 參考 1.7ms vs 2.5ms（GPU 上代價較小）。
- YOLO26 STAL（small-target-aware label assignment）宣稱提升小目標 recall，無量化數字。
- ONNX export 預設 fixed shape（dynamic=False、imgsz=640）→ **imgsz=960 必須重新匯出**，
  與現有 640 ONNX 不相容（репo 已知坑一致）。
- 已知坑：`half=True` + end2end 匯出時 output0 刻意保留 FP32（FP16 表示不了 >2048 的
  整數）。我們匯 FP32 ONNX + TRT EP runtime FP16，不受影響。

**今日已備妥的 A/B 候選**（WSL 匯出 + onnxruntime 驗證 shape 全過）：

| 檔案（`.tmp/yolo_export/out/`） | input | output | 大小 | 假設 |
|---|---|---|---|---|
| `yolo26s_640.onnx` | 640 | (1,300,6) | 38.3MB | 模型容量換 recall |
| `yolo26n_960.onnx` | 960 | (1,300,6) | 10.2MB | 像素換 recall（杯子 @1-1.5m 約 1.5x 像素）|
| `yolo26s_960.onnx` | 960 | (1,300,6) | 38.5MB | 兩者都要（FPS 風險最高）|
| `yolo26n-pose_640.onnx` | 640 | (1,300,57) | 12.1MB | pose 備選（COCO-17 kpts）|

部署 + 切換見 `object_perception/launch/object_perception.launch.py` 的
`OBJECT_MODEL` / `OBJECT_INPUT_SIZE` env（TRT cache 已按模型 stem 分目錄）。

## 2. Pose：sitting 偵測 backend

- 規則式（關節角度/距離）sit/stand 二分類在靜態影像可達 ~95% 準確率（IEEE 8346407）
  → **先修規則 + two-class 映射（已做），不必急著換模型**。
- 桌椅場景下半身常被遮擋 → 膝角規則不穩時優先靠「上半身 + 髖膝相對位置」；
  LSP-YOLO 論文用 11 個上半身 keypoints 做坐姿。
- YOLOv11-Pose 與 RTMO 的 keypoint mAP 相近；坐姿分類精度差距主要在下游分類器，
  非 keypoint 品質 → **換 pose 模型的預期收益有限，分類規則才是槓桿**。
- RTMPose 系列邊緣延遲參考（Snapdragon 865 ncnn FP16）：t 9ms / s 13.9ms / m 26.4ms。
- 實機 A/B 工具：`scripts/pose_backend_probe.py`（同幀並排 MediaPipe vs
  yolo26n-pose，同一顆 classify_pose 分類，印 raw/two-class/延遲）。

## 3. D435 RGB 曝光鎖定 SOP（demo 錄影前）

- canonical 參數：`rgb_camera.enable_auto_exposure`（rs_launch.py 有、預設 true）。
- `rgb_camera.exposure` / `gain` / `auto_exposure_priority` / `power_line_frequency`
  **不是 launch CLI 參數** → 只能 runtime `ros2 param set /camera/camera ...`
  或 config yaml；精確參數名上機後用 `ros2 param list /camera/camera | grep rgb` 確認。
- 「先自動收斂再鎖定」流程：
  ```bash
  # 1. 對準 demo 場景讓 AE/AWB 收斂 ~5s，然後：
  ros2 param set /camera/camera rgb_camera.enable_auto_exposure false
  # 2. （可選）固定頻閃：power_line_frequency 設 60（台灣 60Hz）
  # 3. 驗證：object debug image 亮度不再隨人移動漂移
  ```

## 4. Verdict（今日軟體面已備、上機定案）

1. **object**：先跑 `yolo26n_960` vs 現行 `yolo26n@640` 的 cup @1.0/1.5m 矩陣
   （Codex lane 的 `scripts/object_model_ab.py` 產 capture 指令）；FPS 掉太多再退
   `yolo26s_640`。鎖定條件：cup ≥1m 5/5 + debug image ≥4Hz + 溫度正常。
2. **pose**：先驗今天的 two-class + 放寬門檻修法（`pose_two_class:=true`）；
   還是不穩才用 `pose_backend_probe.py` 對比 yolo26n-pose，數據說話。
3. **camera**：錄影前一律跑曝光鎖定 SOP。
