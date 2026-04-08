# 楊沛蓁 — 姿勢辨識互動設計

> **目標**：決定每個姿勢偵測成功後，Go2 做什麼動作 + 說什麼話。用自己電腦+鏡頭測試姿勢辨識。

---

## 你的任務

1. 用自己的鏡頭跑 MediaPipe Pose，觀察各姿勢的辨識效果
2. 填好「姿勢→動作映射表」交給 Roy
3. 前端 Studio `/studio/pose` 頁面也要一起刻好（見 [Studio 分工](../pawai-studio/pose-assignment.md)）

---

## 模型資訊

| 項目 | 值 |
|------|---|
| 模型 | **MediaPipe Pose** |
| Python 套件 | `mediapipe` (pip install) |
| 版本 | 0.10.14（你的筆電）/ 0.10.18（Jetson） |
| 運算 | **純 CPU**，不需要 GPU |
| 關鍵點 | 33 個身體關鍵點（COCO format 17 + 手指等） |
| 支援姿勢 | standing / sitting / crouching / fallen / bending |
| 限制 | 僅單人追蹤，多人只追蹤一人 |

### 姿勢判定邏輯（pose_classifier.py）

| 姿勢 | 判定規則 | 說明 |
|------|---------|------|
| standing | hip_angle > 155° | 站直 |
| sitting | 100° < hip < 150°, trunk < 35° | 坐在椅子上 |
| crouching | hip < 145°, knee < 145°, trunk > 10° | 蹲下 |
| fallen | bbox_ratio > 1.0 AND trunk > 60° AND vertical_ratio < 0.4 | 跌倒（橫向） |
| bending | trunk > 35°, hip < 140°, knee > 130° | 彎腰 |

---

## 本機復現步驟

### 環境安裝

```bash
# Python 3.9+
pip install mediapipe opencv-python numpy
```

### 測試腳本

建一個 `test_pose.py`：

```python
"""姿勢辨識測試 — 用你的鏡頭即時辨識姿勢"""
import cv2
import mediapipe as mp
import numpy as np
import math

mp_pose = mp.solutions.pose
mp_draw = mp.solutions.drawing_utils

def angle_between(a, b, c):
    """計算三點夾角（度）"""
    ba = np.array([a.x - b.x, a.y - b.y])
    bc = np.array([c.x - b.x, c.y - b.y])
    cos_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    return math.degrees(math.acos(np.clip(cos_angle, -1, 1)))

def classify_pose(landmarks):
    """簡化版姿勢分類（參考 pose_classifier.py）"""
    lm = landmarks.landmark

    # 關鍵點索引（COCO）
    L_SHOULDER, R_SHOULDER = 11, 12
    L_HIP, R_HIP = 23, 24
    L_KNEE, R_KNEE = 25, 26

    # hip angle (shoulder-hip-knee)
    hip_angle = (
        angle_between(lm[L_SHOULDER], lm[L_HIP], lm[L_KNEE]) +
        angle_between(lm[R_SHOULDER], lm[R_HIP], lm[R_KNEE])
    ) / 2

    # knee angle (hip-knee-ankle)
    L_ANKLE, R_ANKLE = 27, 28
    knee_angle = (
        angle_between(lm[L_HIP], lm[L_KNEE], lm[L_ANKLE]) +
        angle_between(lm[R_HIP], lm[R_KNEE], lm[R_ANKLE])
    ) / 2

    # trunk angle (與垂直線的夾角)
    mid_shoulder = np.array([(lm[L_SHOULDER].x + lm[R_SHOULDER].x)/2,
                             (lm[L_SHOULDER].y + lm[R_SHOULDER].y)/2])
    mid_hip = np.array([(lm[L_HIP].x + lm[R_HIP].x)/2,
                        (lm[L_HIP].y + lm[R_HIP].y)/2])
    trunk_vec = mid_shoulder - mid_hip
    vertical = np.array([0, -1])
    cos_trunk = np.dot(trunk_vec, vertical) / (np.linalg.norm(trunk_vec) + 1e-6)
    trunk_angle = math.degrees(math.acos(np.clip(cos_trunk, -1, 1)))

    # 分類
    if trunk_angle > 60:
        return "fallen", hip_angle, knee_angle, trunk_angle
    elif hip_angle > 155:
        return "standing", hip_angle, knee_angle, trunk_angle
    elif trunk_angle > 35 and hip_angle < 140 and knee_angle > 130:
        return "bending", hip_angle, knee_angle, trunk_angle
    elif hip_angle < 145 and knee_angle < 145:
        return "crouching", hip_angle, knee_angle, trunk_angle
    elif 100 < hip_angle < 150 and trunk_angle < 35:
        return "sitting", hip_angle, knee_angle, trunk_angle
    else:
        return "unknown", hip_angle, knee_angle, trunk_angle

# 啟動
pose = mp_pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)
cap = cv2.VideoCapture(0)

print("按 q 離開。試試看站/坐/蹲/躺！")
while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = pose.process(rgb)

    if result.pose_landmarks:
        mp_draw.draw_landmarks(frame, result.pose_landmarks, mp_pose.POSE_CONNECTIONS)
        pose_name, hip, knee, trunk = classify_pose(result.pose_landmarks)

        color = (0, 0, 255) if pose_name == "fallen" else (0, 255, 0)
        cv2.putText(frame, f"{pose_name}", (10, 40),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, color, 3)
        cv2.putText(frame, f"hip={hip:.0f} knee={knee:.0f} trunk={trunk:.0f}",
                   (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    cv2.imshow("Pose Test", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 測試要點

- 鏡頭放桌上或地上，高度約 **30cm**（模擬 Go2 視角）
- 站在鏡頭前 **1.5-3 公尺**（需要看到全身）
- 依序測試：站立 → 坐下 → 蹲下 → 躺下（模擬跌倒）
- 記錄每種姿勢的辨識結果和角度數值
- 注意：**無人時有沒有誤判**（幻覺問題）

---

## 參考程式碼（Jetson 上的實際程式）

| 檔案 | 說明 |
|------|------|
| `vision_perception/vision_perception/pose_classifier.py` | 姿勢分類核心邏輯（114 行）**建議直接看** |
| `vision_perception/vision_perception/event_action_bridge.py` | 姿勢→Go2 動作映射 |
| `vision_perception/vision_perception/vision_perception_node.py` | 主節點（整合手勢+姿勢） |

---

## 目前的映射（只有 1 個，太少了）

| 姿勢 | Go2 動作 | TTS 語音 | 冷卻 |
|------|---------|---------|:----:|
| fallen（跌倒） | — | 「偵測到跌倒！請注意安全」 | 10s |
| standing / sitting / crouching / bending | **什麼都不做** | **什麼都不說** | — |

---

## 請填這個映射表（交給 Roy）

Go2 可用動作請參考 [interaction-design.md](interaction-design.md) 的 API 表。

| 姿勢 | Go2 動作 (api_id) | TTS 語音（Go2 要說什麼） | 冷卻時間 | 備註 |
|------|-------------------|----------------------|:--------:|------|
| standing | ?（StandUp? BalanceStand? 不做?） | ? | ? | 最常見的狀態 |
| sitting | ?（Sit? Go2 也坐下?） | ?（「你坐下了呢」?） | ? | |
| crouching | ?（StandDown 降低身高?） | ? | ? | |
| bending | ?（不做?） | ? | ? | 彎腰撿東西 |
| fallen | StopMove(1003) | 「偵測到跌倒！請注意安全」 | 10s | Demo 可關閉 |
| ＿＿（組合場景） | ? | ? | ? | 例：站→蹲→站 |

---

## 已知限制

- **僅支援單人追蹤**：多人時 MediaPipe 只追蹤一人
- **幻覺問題嚴重**：無人時偶爾誤判有人（鎖定衣架、椅子等物體判為 fallen）
- 鏡頭高度 **~1.5m 距離**才看得到全身
- 側面坐姿判定不準，Demo 建議正面面向攝影機
- `enable_fallen` 參數可關閉跌倒偵測（Demo 避免誤報）
- 跌倒偵測因專題已不以老人照護為主題，**可考慮弱化**

---

## 交付方式

1. 測試結果：每種姿勢的辨識率 + 角度截圖
2. 填好的映射表
3. Studio `/studio/pose` 頁面 PR

**deadline**：4/13 前映射表 + Studio 頁面
