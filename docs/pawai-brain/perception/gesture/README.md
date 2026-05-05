# 手勢辨識

> Status: current

> MediaPipe Gesture Recognizer 辨識手勢，觸發 Go2 動作。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **上機驗收 5/5 PASS** |
| 版本/決策 | MediaPipe Gesture Recognizer (CPU 7.2 FPS) |
| 完成度 | 90% |
| 最後驗證 | 2026-04-04（stop/thumbs_up/非白名單/距離/dedup 全 PASS） |
| 入口檔案 | `vision_perception/vision_perception/gesture_classifier.py` |
| 測試 | `python3 -m pytest vision_perception/test/test_gesture_classifier.py -v` |

## 啟動方式

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  gesture_backend:=recognizer max_hands:=2
```

## 核心流程

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Gesture Recognizer（CPU, 21 手部關鍵點）
    ↓
gesture_classifier.py（靜態：stop/point/fist, 時序：wave）
    ↓
/event/gesture_detected（JSON: gesture, confidence, hand_label）
    ↓
interaction_executive_node → Go2 動作
```

## 支援手勢（MOC 9 種，分 3 組）

### 一、系統控制 System Control（4 種）

| 手勢 | 標籤 | 模式 | 觸發 Skill | 說明 |
|:---:|:---|:---|:---|:---|
| 🖐️ | Palm | Pause | `system_pause` | 全面暫停 — 停止當前所有動作與移動 |
| 👊 | Fist | Mute | `enter_mute_mode`（Hidden）| 機器狗坐下、關閉語音輸出 |
| ☝️ | Index | Listen | `enter_listen_mode`（Hidden）| 機器狗站立、開啟語音識別 |
| 👌 | OK | Confirm | （gate，不直觸 skill）| **二次確認動作**：所有指令後的二階段執行確認 |

### 二、互動情感 Interaction & Emotion（2 種）

| 手勢 | 標籤 | 模式 | 觸發 Skill | Go2 ID | 動作 |
|:---:|:---|:---|:---|:---:|:---|
| 👍 | Thumb | Happy | `wiggle` | 1033 | 搖屁股 (Wiggle) |
| ✌️ | Peace | Relax | `stretch` | 1017 | 伸懶腰 (Stretch) |

### 三、動態軌跡 Dynamic（3 種，需偵測移動軌跡）

| 手勢 | 標籤 | 模式 | 觸發 Skill | Go2 ID | 判定方式 |
|:---:|:---|:---|:---|:---:|:---|
| 👋 | Wave | Greeting | `wave_hello` | 1016 | 左右來回揮動，速度反轉計數 ≥ 2 |
| 🫴 | ComeHere | Follow | `follow_me`（Future）| 1018 | 手掌向內撥動（進階模式）|
| 🔄 | Circle | Dance | `dance`（Future）| — | 畫圓軌跡 |

> **Active**（5/12 demo 啟用，5/5 已實作）：Palm、OK、Thumb、Peace、Wave
> **Hidden**（registry 內、Studio grayed-out，enum 已實作但未綁 skill）：Fist、Index
> **Future**（軌跡 detector 未實作）：ComeHere、Circle
> 對應 sprint design §4 Skill Registry 26+1 條目。

## 觸發規則

依 MOC 規格 + sprint design §4.2:

1. **0.5 秒穩定維持**：手勢需穩定維持 **0.5 秒**以上方可觸發（temporal dedup，避免揮過去的偽觸發）
2. **OK 二次確認**：高風險動作（motion / state-change）識別後，必須再做 👌 OK 手勢進行「最終確認」才會執行；low-risk social skill（如 wave_hello）可直觸不需 OK
   - 高風險（必過 OK）：`wiggle`、`stretch`、`enter_mute_mode`、`enter_listen_mode`、`follow_me`、`dance`
   - low-risk（直觸）：`wave_hello`（揮手回應）、`system_pause`（安全 immediate）
3. **操作流程範例**：
   - 步驟 A：對著相機做 ✌️（Peace）持續 0.5 秒
   - 步驟 B：系統鎖定後，做出 👌（OK）持續 0.5 秒
   - 執行：Go2 執行動作 1017（伸懶腰）

## 5/5 實作落地（Active enum）

實際發出的 enum（對齊 MOC 命名）：

| 規則來源 | 落地手勢 | 程式 |
|---|---|---|
| MediaPipe Recognizer label remap | palm / fist / index / thumb / peace | `gesture_recognizer_backend.py:_GESTURE_MAP` |
| 自製幾何規則 override | **ok**（拇指尖↔食指尖距離 < hand_width × 0.3 + 中/無/小指未全屈）| `gesture_classifier.py:detect_ok_circle` |
| 時序軌跡 override | **wave**（1.5s 窗內 wrist X 速度反轉 ≥ 2 + 振幅 > 50px）| `dynamic_gesture_detector.py:WaveDetector` |

**未落地（仍為 Future）**：ComeHere、Circle — 軌跡 loop 需更長 buffer + 形狀比對，post-demo 評估。

**5/5 移除**：`GESTURE_COMPAT_MAP={"fist":"ok"}` 實際轉換（語意衝突，MOC 的 Fist=Mute ≠ OK=Confirm）；常數保留為空 dict 以免下游 import 壞。

## 0.5s 穩定 gate（已實作，可參數化）

`vision_perception_node` 加 ROS param `gesture_stable_s`（default 0.5）：
- 同一手勢需穩定維持 0.5 秒才會發 `/event/gesture_detected`
- 設 `0.0` 可即時 bypass（debug 用）：
  ```bash
  ros2 param set /vision_perception_node gesture_stable_s 0.0
  ```

## 操作限制與已知問題

- **有效範圍**：D435 前方約 **2m** 以內（4/8 會議確認，距離過遠不精準）
- **僅支援單人操作**：多人同時出現時可能混淆
- point 手勢不穩定（MediaPipe backend）→ 5/5 已從 enum 移除（不再對應 MOC）
- 快速切換手勢時可能有延遲（投票 buffer 5 幀 + 0.5s gate）
- Wave detector reset 後需 ~6 frames 才再次觸發（min_samples）

## Event Schema（v2.0 凍結）

```json
{
  "stamp":       1710000000.123,
  "event_type":  "gesture_detected",
  "gesture":     "wave",
  "confidence":  0.87,
  "hand":        "right"
}
```

## Gesture → Skill Mapping（5/12 Sprint）

| 手勢 | Brain 觸發 | OK 二次確認 | Go2 ID | TTS / 反饋 | Cooldown |
|---|---|:---:|:---:|---|:---:|
| Palm | `system_pause` | ❌ 直觸（安全 immediate）| StopMove (1003) | — | **無** |
| Fist | `enter_mute_mode`（Hidden）| ✅ | 坐下 + mute | — | 3s |
| Index | `enter_listen_mode`（Hidden）| ✅ | 站立 + ASR on | — | 3s |
| OK | gate only — 不直觸 skill | — | — | — | — |
| Thumb | `wiggle` | ✅ | 1033（搖屁股）| 「收到！」 | 3s |
| Peace | `stretch` | ✅ | 1017（伸懶腰）| — | 3s |
| Wave | `wave_hello` | ❌ 直觸（low-risk social）| 1016 | 「Hi！」 | 3s |
| ComeHere | `follow_me`（Future）| ✅ | 1018 | — | — |
| Circle | `dance`（Future）| ✅ | — | — | — |

> 5/12 demo Active 5 個（Palm/OK/Thumb/Peace/Wave）— 即「stop / 確認 / 開心 / 放鬆 / 打招呼」5 場手勢互動。Hidden/Future 7 條 keep registry 但 Studio button grayed-out。

## 下一步

- [ ] **B4-2 Wave 動態軌跡判定**（速度反轉計數 ≥ 2 鎖定 wave_hello）
- [ ] **B4-3 Palm Pause / Fist Mute 規則聯動**（system_pause / enter_mute_mode 上線）
- [ ] **0.5s 穩定 dedup logic**：在 `gesture_classifier.py` 加 sliding window，連續 0.5s 同手勢才發 event
- [ ] **OK 二次確認 gate**：在 `interaction_executive` 加 confirmation state machine — 鎖定 pending skill → OK 觸發 → 執行
- [ ] ComeHere / Circle 手勢 detector（post-demo, Future bucket）
- [ ] point 手勢穩定化（目前 MediaPipe backend 不穩，sprint design 已退場）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs 自定義）、benchmark 比較、社群回饋 |
