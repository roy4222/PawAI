# 鄔雨彤 — 手勢辨識互動設計

> **目標**：決定每個手勢偵測成功後，Go2 做什麼動作 + 說什麼話。用自己電腦+鏡頭測試手勢辨識率。

---

## 你的任務

1. 用自己的鏡頭跑 MediaPipe Gesture Recognizer，測試每種手勢的辨識率
2. 填好「手勢→動作映射表」交給 Roy
3. 前端 Studio `/studio/gesture` 頁面也要一起刻好（見 [Studio 分工](../pawai-studio/gesture-assignment.md)）

---

## 模型資訊

| 項目 | 值 |
|------|---|
| 模型 | **MediaPipe Gesture Recognizer** |
| Python 套件 | `mediapipe` (pip install) |
| 版本 | 0.10.14（你的筆電）/ 0.10.18（Jetson） |
| 運算 | **純 CPU**，不需要 GPU |
| 內建手勢 | 7 種（見下表） |
| 有效距離 | ~2 公尺 |
| 限制 | 僅單人，多人會混亂 |

### MediaPipe 內建支援的 7 種手勢

| 手勢 | MediaPipe 名稱 | 說明 |
|------|---------------|------|
| 讚 | Thumb_Up | 大拇指朝上 |
| 倒讚 | Thumb_Down | 大拇指朝下 |
| 張開手掌 | Open_Palm | 五指張開（我們用作 stop） |
| 握拳 | Closed_Fist | 握拳 |
| 勝利/剪刀 | Victory | ✌️ |
| 指向上方 | Pointing_Up | 食指朝上 |
| 我愛你 | ILoveYou | 🤟 |

---

## 本機復現步驟

### 環境安裝

```bash
# Python 3.9+
pip install mediapipe opencv-python
```

### 測試腳本

建一個 `test_gesture.py`：

```python
"""手勢辨識測試 — 用你的鏡頭即時辨識手勢"""
import cv2
import mediapipe as mp

# 初始化
BaseOptions = mp.tasks.BaseOptions
GestureRecognizer = mp.tasks.vision.GestureRecognizer
GestureRecognizerOptions = mp.tasks.vision.GestureRecognizerOptions
VisionRunningMode = mp.tasks.vision.RunningMode

# 下載模型（第一次跑會自動下載，或手動下載放同目錄）
# https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task
import urllib.request, os
MODEL_PATH = "gesture_recognizer.task"
if not os.path.exists(MODEL_PATH):
    print("下載模型中...")
    urllib.request.urlretrieve(
        "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task",
        MODEL_PATH
    )

options = GestureRecognizerOptions(
    base_options=BaseOptions(model_asset_path=MODEL_PATH),
    running_mode=VisionRunningMode.IMAGE,
    num_hands=2,
    min_hand_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)

recognizer = GestureRecognizer.create_from_options(options)
cap = cv2.VideoCapture(0)

print("按 q 離開。試試看比出各種手勢！")
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 轉換格式
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    # 辨識
    result = recognizer.recognize(mp_image)

    # 顯示結果
    if result.gestures:
        for i, gesture_list in enumerate(result.gestures):
            gesture_name = gesture_list[0].category_name
            confidence = gesture_list[0].score
            hand = result.handedness[i][0].category_name  # Left/Right

            text = f"{gesture_name} ({confidence:.0%}) [{hand}]"
            cv2.putText(frame, text, (10, 40 + i * 40),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            print(f"  {hand}: {gesture_name} ({confidence:.0%})")

    cv2.imshow("Gesture Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 測試要點

- 鏡頭放桌上，高度約 **30cm**（模擬 Go2 視角）
- 站在鏡頭前 **1-2 公尺**
- 每種手勢試 10 次，記錄成功率
- 注意哪些手勢容易互相混淆

---

## 參考程式碼（Jetson 上的實際程式）

| 檔案 | 說明 |
|------|------|
| `vision_perception/vision_perception/gesture_recognizer_backend.py` | Gesture Recognizer 後端（146 行） |
| `vision_perception/vision_perception/gesture_classifier.py` | 手勢分類邏輯（100 行） |
| `vision_perception/vision_perception/event_action_bridge.py` | 手勢→Go2 動作映射 |
| `vision_perception/vision_perception/interaction_rules.py` | 手勢白名單 |

---

## 目前的映射（只有 3 個，太少了）

| 手勢 | Go2 動作 | TTS 語音 | 冷卻 |
|------|---------|---------|:----:|
| stop (Open_Palm) | StopMove(1003) | — | 無 |
| ok (Closed_Fist) | Content(1020) | — | 3s |
| thumbs_up (Thumb_Up) | Content(1020) | 「收到！」 | 3s |

wave / point / Victory / Thumb_Down / ILoveYou 目前**什麼都不做**。

---

## 請填這個映射表（交給 Roy）

Go2 可用動作請參考 [interaction-design.md](interaction-design.md) 的 API 表。

| 手勢 | MediaPipe 名稱 | Go2 動作 (api_id) | TTS 語音（Go2 要說什麼） | 冷卻時間 |
|------|---------------|-------------------|----------------------|:--------:|
| 停止 | Open_Palm | StopMove(1003) | （要說話嗎？） | ? |
| 讚 | Thumb_Up | ?（Content? Dance1? WiggleHips?） | ?（「謝謝！」?） | ? |
| 倒讚 | Thumb_Down | ?（Sit? StandDown?） | ? | ? |
| 握拳 | Closed_Fist | ? | ? | ? |
| 勝利 | Victory | ?（Dance1? FingerHeart?） | ? | ? |
| 指上 | Pointing_Up | ? | ? | ? |
| 我愛你 | ILoveYou | ?（FingerHeart? Content?） | ? | ? |
| 揮手 | _(自定義，非內建)_ | ?（Hello?） | ? | ? |

---

## 已知限制

- **有效距離約 2m**，超過辨識率急降
- **僅支援單人**，多人同時出現會混亂
- 鏡頭高度 ~1.5m 距離才看得到上半身
- Open_Palm 和 Pointing_Up 有時會搞混
- 快速切換手勢時有延遲（投票 buffer）

---

## 交付方式

1. 測試結果：每種手勢的辨識率（10 次中幾次成功）
2. 填好的映射表
3. Studio `/studio/gesture` 頁面 PR

**deadline**：4/13 前映射表 + Studio 頁面
