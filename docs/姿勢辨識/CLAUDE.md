# 姿勢辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 不能做

- 不要改 fallen 判定閾值（bbox_ratio > 1.0 AND trunk_angle > 60° AND vertical_ratio < 0.4）除非有完整測試
- 不要預設用 RTMPose（GPU 91-99%，主線是 MediaPipe CPU 0%）
- 不要動 COCO 17-point keypoint 索引

## 改之前先看

- `vision_perception/vision_perception/pose_classifier.py`（114 行）
- `docs/姿勢辨識/README.md`

## 常見陷阱

- hip_angle 計算依賴 shoulder-hip-knee 三點，任一缺失就判不了
- standing 和 bending 的分界在 trunk_angle 35°
- RTMPose balanced mode 會把 GPU 吃滿，跟 Whisper CUDA 衝突

## 驗證指令

```bash
python3 -m pytest vision_perception/test/test_pose_classifier.py -v
```
