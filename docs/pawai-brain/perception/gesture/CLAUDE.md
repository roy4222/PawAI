# 手勢辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 不能做

- 不要改 gesture enum（v2.0 凍結）
- 不要切換回 MediaPipe Hands backend（已確認 Gesture Recognizer 更好）
- 不要移除 GESTURE_COMPAT_MAP（fist→ok 的 v2.0 相容層）

## 改之前先看

- `vision_perception/vision_perception/gesture_classifier.py`（100 行）
- `vision_perception/vision_perception/gesture_recognizer_backend.py`（146 行）
- `docs/pawai-brain/perception/gesture/README.md`

## 常見陷阱

- `_EXTEND_RATIO=1.8`、`_CURL_RATIO=0.8` — 手指伸縮判定閾值
- `_MIN_SCORE=0.2` — 關鍵點置信度
- 時序分析幀數 buffer 未參數化（hard-coded）

## 驗證指令

```bash
python3 -m pytest vision_perception/test/test_gesture_classifier.py -v
python3 -m pytest vision_perception/test/test_gesture_recognizer_backend.py -v
```
