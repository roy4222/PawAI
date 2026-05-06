# 姿勢辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 不能做

- 不要改 fallen 主守門條件（trunk > 60° AND 0 ≤ vertical_ratio < 0.4 AND torso vis ≥ 0.5）除非有完整測試
- bbox_ratio 不再是 fallen 必要條件（5/6 改）— 只當 confidence bonus，避免漏掉蜷曲跌倒
- 不要預設用 RTMPose（GPU 91-99%，主線是 MediaPipe CPU 0%）
- 不要動 COCO 17-point keypoint 索引
- 改 `_is_akimbo` / `_is_knee_kneel` 前先看社群依據（README 5/6 升級備註）— 不要回退到 wrist-near-hip 那套

## 改之前先看

- `vision_perception/vision_perception/pose_classifier.py`
- `docs/pawai-brain/perception/pose/README.md`
- `/home/roy422/.claude/plans/pose-validated-harp.md`（5/6 演算法升級設計）

## 常見陷阱

- hip_angle 計算依賴 shoulder-hip-knee 三點，任一缺失就判不了
- standing 與 bending 的分界在 trunk_angle 30°（5/6 從 35° 放寬）
- sitting 與 crouching 在角度法下重疊嚴重 — 必須先 sitting（y-geometry）再 crouching
- MediaPipe Pose 在 awkward viewpoint 偶會 hallucinate（shoulder.y > hip.y），新 fallen gate 用 `vertical_ratio >= 0` 攔截
- akimbo 不要依賴 wrist 位置 — 社群（BleedAI / MediaPipe issue #4462）通報 wrist drift，主訊號改用 elbow 往外彎
- knee_kneel 區分 kneel vs lunge 用「kneel-side ankle.y ≈ knee.y」（社群 yoga-pose 規則）
- RTMPose balanced mode 會把 GPU 吃滿，跟 Whisper CUDA 衝突

## 驗證指令

```bash
python3 -m pytest vision_perception/test/test_pose_classifier.py -v
```
