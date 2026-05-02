# 人臉辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。`.claude/rules/` 中的對應檔案只是薄橋接。

## 不能做

- 不要升級 OpenCV 版本（Jetson 4.5.4 限制）
- 不要改 hysteresis 閾值（upper=0.35, lower=0.25）除非有完整測試
- 不要動 face_db 格式（影響已訓練的人臉資料）

## 改之前先看

- `face_perception/face_perception/face_identity_node.py`（680 行，核心）
- `face_perception/config/face_perception.yaml`
- `docs/pawai-brain/perception/face/README.md`

## 常見陷阱

- `to_bbox()` 回傳 np.int32，發 JSON 前必須轉 Python int
- 模型路徑硬編碼 `/home/jetson/face_models/`
- QoS 是 BEST_EFFORT（3/23 改的）

## 驗證指令

```bash
python3 -m pytest face_perception/test/ -v
colcon build --packages-select face_perception
```
