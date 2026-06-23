# 手勢辨識

[English](./README.md) | **中文**

> **Scope**：vision_perception 手勢子系統設計真相（MediaPipe Gesture Recognizer + 自製幾何/時序 detector）｜**Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception ｜ **能力 claim 真相源**：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `gesture.wave`
> **能力 grade 證據（最終事實）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（gesture.wave = 🔴 **fail**；caveats 凌駕本頁敘事）
> **維護子檔**：`CLAUDE.md`（工作規則）｜`AGENT.md`（topic 介面契約）｜`research/`（research-only，非真相）
> **這頁不是什麼**：不是能力 pass/fail 的裁定（看 baseline-evidence）。⚠️ **gesture.wave 現為 fail**；下方「5/5 PASS」是 4/04 開發期單測/局部觀察，**非 6/04 trusted baseline**。靜態手勢（thumbs_up/ok/palm）是 fallback/demo-only，**非** wave 能力。

> MediaPipe Gesture Recognizer 辨識手勢。**camera 動態 wave 6/04 量測為 fail**；靜態手勢可用作 fallback。

## 能力卡（canonical 8 欄位 → 連結 claim matrix，勿在本頁重複整份散文）

> 完整 8 欄位散文見 [claim matrix `gesture.wave`](../../../mission/2026-06-18-capability-claim-matrix.md#gesturewave)。本表為速查。

| 欄位 | 值 |
|---|---|
| **Current Claim** | 揮手（camera 動態 wave）6/04 量到 **fail**；改用靜態 palm / 舉手或只在 Studio gesture panel 顯示 event |
| **Claim Level** | DO_NOT_CLAIM（fail，需 fallback） |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（n=9, recall=0.0, 6/6 positive 全 none, wave_pub=False 全程） |
| **Pass/Degraded/Fail/Insufficient** | 🔴 fail — 根因 = 1.5m hand detection 間歇 + WaveDetector 門檻過嚴 |
| **Fallback** | camera 動態 wave 不演（已知 fail 非現場故障）；退靜態 palm / 舉手，或語音 `wave_hello(1016)`（**另一條路徑**），或只在 Studio 顯示並標 fail |
| **Non-Claims** | 「揮手可觸發打招呼」 / 把 wave 演成可靠互動 / 手勢觸發 Go2 motion / 把 `wave_hello` 語音路徑混為 camera wave 已 pass |
| **Model Candidates** | SPIKE_AFTER_FAIL（不是換模型；調 gesture_min_score / min_amplitude_px / vote_frames） |
| **Next Retest** | HITL 調 gesture_min_score 0.1→0.05、min_amplitude_px 50→35、vote_frames/stable_s revert 後重測；否則腳本改 palm fallback |

> **靜態手勢（palm / fist / index / thumbs_up / peace / ok）** 在 6/04 屬可用 fallback / demo-only，**不是 gesture.wave 能力**，也未經 trusted baseline 量測——除非重跑 baseline，不得宣稱靜態手勢「已 pass」。

## 狀態卡

> **狀態卡 caveat（6/04 收斂）**：下表「4/04 5/5 PASS」是**靜態手勢開發期局部觀察**，**不是 gesture.wave 能力的 trusted baseline**。6/04 trusted 量測 **gesture.wave = 🔴 fail**（見上方能力卡）。完成度為模組開發進度，非能力 pass。

| 項目 | 值 |
|------|---|
| 狀態 | **gesture.wave = 🔴 fail（6/04 trusted）**；靜態手勢為 fallback/demo-only |
| 版本/決策 | MediaPipe Gesture Recognizer (CPU 7.2 FPS) |
| 完成度 | 90%（模組開發進度，非能力 pass — 見上方 caveat） |
| 最後驗證 | gesture.wave 最新 trusted = 2026-06-04 HITL（**fail**）；4/04 5/5 PASS 僅靜態手勢開發期局部觀察 |
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

> **Active**（5/12 sprint 標記，**enum/skill 接線存在 ≠ 能力 pass**）：Palm、OK、Thumb、Peace、Wave
> ⚠️ **Wave（camera 動態）6/04 trusted = 🔴 fail**（見能力卡）；6/18 demo 不演 camera 動態 wave，退靜態 palm/舉手或語音 `wave_hello`。其餘靜態手勢為 demo-only fallback，未經 trusted baseline 量測。
> **Hidden**（registry 內、Studio grayed-out，enum 已實作但未綁 skill）：Fist、Index
> **Future**（軌跡 detector 未實作）：ComeHere、Circle
> 對應 sprint design §4 Skill Registry 26+1 條目。

## 觸發規則

依 MOC 規格 + sprint design §4.2:

1. **0.5 秒穩定維持**：手勢需穩定維持 **0.5 秒**以上方可觸發（temporal dedup，避免揮過去的偽觸發）
2. **OK 二次確認**：高風險動作（motion / state-change）識別後，必須再做 👌 OK 手勢進行「最終確認」才會執行；low-risk social skill（如 wave_hello）可直觸不需 OK
   - 高風險（必過 OK）：`wiggle`、`stretch`、`follow_me`、`dance`
   - low-risk（直觸）：`wave_hello`（揮手回應）、`system_pause`（palm，安全 immediate）、`enter_mute_mode`（fist，5/12 改 direct fire — mode switch 視為低風險）、`enter_listen_mode`（index，5/12 改 direct fire 同理）

   > **5/12 變更**：`enter_mute_mode` / `enter_listen_mode` 由「必過 OK」改為「direct fire」。原因：mode switch 是顯性使用者意圖，且不涉及 motion 安全性；過 OK 反而拖慢 demo 節奏。實作見 `interaction_executive/interaction_executive/brain_node.py:_GESTURE_DIRECT`。
3. **操作流程範例**：
   - 步驟 A：對著相機做 ✌️（Peace）持續 0.5 秒
   - 步驟 B：系統鎖定後，做出 👌（OK）持續 0.5 秒
   - 執行：Go2 執行動作 1017（伸懶腰）

## 5/5 實作落地（Active enum）

實際發出的 enum（對齊 MOC 命名）：

| 規則來源 | 落地手勢 | 程式 |
|---|---|---|
| MediaPipe Recognizer label remap | palm / fist / index / **thumbs_up** / peace | `gesture_recognizer_backend.py:_GESTURE_MAP`（5/8 commit `efda3c0`：`thumb` → `thumbs_up` 對齊 contract enum，否則 `brain_node._GESTURE_CONFIRM` 收不到 thumbs_up→wiggle）|
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
| Fist | `enter_mute_mode` | ❌ 直觸（5/12 改）| 坐下 + mute | — | 3s |
| Index | `enter_listen_mode` | ❌ 直觸（5/12 改）| 站立 + ASR on | — | 3s |
| OK | gate only — 不直觸 skill | — | — | — | — |
| Thumb | `wiggle` | ✅ | 1033（搖屁股）| 「收到！」 | 3s |
| Peace | `stretch` | ✅ | 1017（伸懶腰）| — | 3s |
| Wave | `wave_hello` | ❌ 直觸（low-risk social）| 1016 | 「Hi！」 | 3s |
| ComeHere | `follow_me`（Future）| ✅ | 1018 | — | — |
| Circle | `dance`（Future）| ✅ | — | — | — |

> 5/12 demo Active 7 個（Palm/Fist/Index/OK/Thumb/Peace/Wave）— 即「stop / 靜音 / 監聽 / 確認 / 開心 / 放鬆 / 打招呼」7 場手勢互動（5/12 補 Fist+Index direct fire）。Future 2 條（ComeHere/Circle）keep registry 但 Studio button grayed-out。

## 下一步

- [x] **B4-2 Wave 動態軌跡判定** — 5/5 落地（commit `95982d6`，`dynamic_gesture_detector.WaveDetector` + bypass 5/12 fix）；**實機效果待驗證**，且需注意 wave 走獨立 publish path（不進靜態 stable gate，避免被相鄰 palm/peace 投票蓋掉）
- [ ] **B4-3 Palm Pause / Fist Mute 規則聯動**（system_pause / enter_mute_mode 上線）— enum 已實作，skill 觸發鏈未接
- [x] **0.5s 穩定 dedup gate** — 5/5 落地在 `vision_perception/vision_perception/vision_perception_node.py`（commit `4f638ae`），ros param `gesture_stable_s`（default 0.5，可設 0.0 bypass）；**僅作用於靜態手勢**，wave 不走此 gate
- [ ] **OK 二次確認 gate**：在 `interaction_executive` 加 confirmation state machine — 鎖定 pending skill → OK 觸發 → 執行（Stretch P1）
- [ ] ComeHere / Circle 手勢 detector（post-demo, Future bucket）
- [ ] point 手勢穩定化（目前 MediaPipe backend 不穩，sprint design 已退場）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs 自定義）、benchmark 比較、社群回饋 |
