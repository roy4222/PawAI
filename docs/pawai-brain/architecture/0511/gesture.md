# 手勢辨識（gesture）— 架構詳述

**版本**：2026-05-11 freeze 快照（N7 fist vote 收緊）
**位置**：`vision_perception/`（與 pose 同住）
**入口**：`vision_perception/vision_perception/vision_perception_node.py`（orchestrator）
**狀態**：5/12 demo 90% 完成，5/5 上機驗收 PASS

---

## 1. 模組定位

手勢辨識和姿勢、物體一起住在 `vision_perception` 套件裡，由 `vision_perception_node` 統一 orchestrate。手勢的角色是 **「身體語言觸發層」**：把鏡頭裡的手部動作轉成離散事件，餵給 Brain（語境融合）與 Executive（技能觸發）。

**核心設計**：
- **三種 backend**：MediaPipe Gesture Recognizer（主線）/ MediaPipe Hands + classifier（備援）/ RTMPose（拒用）
- **CPU only**：保護 GPU 給 pose / object
- 動態 + 靜態雙軌：wave 走 temporal motion 旁路；其他走 vote + stable gate
- 與 pose / object 共用同一個 orchestrator node + tick loop

**對外介面**：
- 訂閱：D435 RGB（與 pose 共用相機）
- 發佈：`/event/gesture_detected`（事件觸發）

**效能**：
- 與 pose 同跑：7.2 FPS
- 單跑：21 FPS
- 上機驗收（5/5）：stop / thumbs_up / wave / ok / palm / peace / index 全綠

---

## 2. Pipeline 全貌（6 stage）

```
┌──────────────────────────────────────────────────────────────────────┐
│              D435 RGB  (/camera/camera/color/image_raw, 640×480)     │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│        VisionPerceptionNode  (tick=0.05s = 20Hz, single-thread)      │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 1: Hand Landmark Extraction（雙 backend）                  │ │
│  │  ┌────────────────────────┐   ┌────────────────────────┐        │ │
│  │  │ Path A: Recognizer     │   │ Path B: MP Hands       │        │ │
│  │  │ (gesture_backend=      │   │ (gesture_backend=      │        │ │
│  │  │  recognizer，主線)     │   │  mediapipe，備援)       │        │ │
│  │  │                        │   │                        │        │ │
│  │  │ gesture_recognizer.task│   │ MediaPipe Hands 0.10.18│        │ │
│  │  │ ~/face_models/         │   │ (內建 pip pkg)         │        │ │
│  │  │ (8.4MB, float16)       │   │                        │        │ │
│  │  │ 每 tick 跑（21 FPS）    │   │ 每 N tick 跑（n=3）    │        │ │
│  │  └────────────────────────┘   └────────────────────────┘        │ │
│  │           │                              │                      │ │
│  │           └──────────────┬───────────────┘                      │ │
│  │                          ▼                                      │ │
│  │              21 個 hand kp + scores (左/右手)                   │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 2: 靜態手勢分類                                            │ │
│  │  Recognizer 路徑：內建分類器（canonical emit value 在右側）      │ │
│  │    Open_Palm   → "palm"                                          │ │
│  │    Closed_Fist → "fist"                                          │ │
│  │    Pointing_Up → "index"                                         │ │
│  │    Thumb_Up    → "thumbs_up"  (5/8 fix: 之前錯標為 thumb)        │ │
│  │    Victory     → "peace"                                         │ │
│  │    Thumb_Down / ILoveYou → 丟棄（不在 MOC 9-gesture 內）         │ │
│  │    ★ stop / point / victory 是 legacy alias，主線不 emit ★      │ │
│  │                                                                  │ │
│  │  MP Hands 路徑：gesture_classifier.py（純規則）                  │ │
│  │    _finger_extended: tip_dist / mcp_dist > 1.8                   │ │
│  │    _finger_curled:   tip_dist / mcp_dist < 0.8                   │ │
│  │    stop  = 4+ 指外伸（含拇指）                                   │ │
│  │    point = 食指外伸 + 中無小至少 2 個彎曲                        │ │
│  │    fist  = 3+ 指彎曲，無外伸                                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 3: OK 幾何覆蓋（detect_ok_circle，最高優先）              │ │
│  │   thumb_tip ↔ index_tip 距離 ≤ 0.30 × hand_width                │ │
│  │   AND 中無小不全彎曲（避免 fist+thumb 誤判）                     │ │
│  │   → ("ok", 1.0 - touch_ratio/0.30) 覆蓋上一階段結果              │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 4: 動態手勢（WaveDetector，旁路）                          │ │
│  │   每 tick 餵 wrist KP (idx=0)                                    │ │
│  │   window=1.5s, min_reversals=2, min_amplitude=50px               │ │
│  │   → True → 直接發 /event/gesture_detected (wave)                 │ │
│  │   → 旁路 vote buffer + stable gate（避免被均勻化掉）             │ │
│  │   → cooldown 2.5s                                                │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 5: 時間投票（gesture_buffer, maxlen=5  ★N7 從 3→5★）      │ │
│  │   deque 滑動視窗（5 frames @ 20Hz = 250ms）                      │ │
│  │   _majority() 取最多出現的非 None label                         │ │
│  │   confidence = vote_count / buffer_len（vote 比率，非原始分數）  │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 6: 穩定 gate（gesture_stable_s=0.3s  ★N7 從 0.5→0.3★）    │ │
│  │   label 改變 → 重置 hold timer                                   │ │
│  │   持續 ≥ 0.3s 且 != last_gesture → 觸發發佈                      │ │
│  │   同一手勢只發一次（沿用 last_gesture 抑制）                     │ │
│  │   總延遲 = 250ms(投票) + 300ms(hold) = 550ms                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  /event/gesture_detected （事件觸發，非週期）                        │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Stable Gate 狀態機（Stage 6 細節）

```
┌─────────────────────────────────────────────────────────────┐
│ 1. gesture_vote=None                                        │
│    _gesture_hold_label ← None                              │
│    last_gesture ← None                                      │
│                                                             │
│ 2. NEW: gesture_vote="fist" 第一次進 buffer                 │
│    gesture_vote ≠ _gesture_hold_label                       │
│    → _gesture_hold_label = "fist"                           │
│      _gesture_hold_ts = now                                 │
│      (start hold timer)                                     │
│                                                             │
│ 3. HOLDING: gesture_vote="fist" 持續                        │
│    held_long_enough = (now - hold_ts) ≥ 0.3                 │
│    若 held_long_enough AND vote != last_gesture             │
│    → PUBLISH event                                          │
│      last_gesture = "fist"                                  │
│                                                             │
│ 4. HELD: 已發過，gesture_vote 仍是 "fist"                   │
│    NO PUBLISH（同手勢只發一次）                             │
│                                                             │
│ 5. TRANSITION: gesture_vote="palm" 翻盤                     │
│    重置 _gesture_hold_label = "palm"                        │
│    重新計時                                                  │
└─────────────────────────────────────────────────────────────┘
```

關鍵：hold timer 從 **label 改變**開始計，不是從 buffer 開始填。投票翻盤會重置計時器。

---

## 4. Topic Schema（v2.0 凍結）

### `/event/gesture_detected`

```json
{
  "stamp": 1773561601.500,
  "event_type": "gesture_detected",
  "gesture": "fist",        // enum, 9 種，見下
  "confidence": 0.8,        // ★vote 比率 (count/5)，非原始分類分數
  "hand": "right"           // "left" | "right"
}
```

**QoS**：Reliable, Volatile, depth=10
**頻率**：事件觸發（非週期），onset 後 ~550ms 才發
**Builder**：`event_builder.build_gesture_event()`，`GESTURE_COMPAT_MAP` 已清空（5/5 移除 fist→ok 映射）

### Canonical event enum（`/event/gesture_detected.gesture` 實際發出的值）

主線（Recognizer backend）emits 以下 canonical labels — 這些是 `interaction_executive` 與 Brain 認可的鍵：

| Gesture | 分類 | 來源 | 對應技能 | 風險 | 5/12 |
|---------|------|------|---------|:----:|:----:|
| `palm` | 系統控制 | Recognizer Open_Palm | `system_pause` | **SAFETY**（always）| ✅ |
| `fist` | 系統控制 | Recognizer Closed_Fist | `enter_mute_mode` | LOW（5/12 改直發）| ✅ |
| `index` | 系統控制 | Recognizer Pointing_Up | `enter_listen_mode` | LOW（5/12 改直發）| ✅ |
| `ok` | 系統控制 | 幾何規則（detect_ok_circle）| confirm gate | — | ✅ |
| `thumbs_up` | 互動情緒 | Recognizer Thumb_Up | `wiggle`（需 OK 確認）| HIGH | ✅ |
| `peace` | 互動情緒 | Recognizer Victory | `stretch`（需 OK 確認）| HIGH | ✅ |
| `wave` | 動態 | WaveDetector X 反轉 | `wave_hello`（直發）| — | ✅ |

### Legacy / Alias（不要在 frozen contract 主表用）

下列名稱出現在較舊文件 / MP Hands classifier 內部，但 **Recognizer 主線不會 publish 這些值**，下游也不依賴：

| Legacy name | 主線對應 | 來源 | 備註 |
|-------------|---------|------|------|
| `stop` | `palm` | MP Hands + classifier rule | 老 enum，已被 `palm` 取代 |
| `point` | `index` | MP Hands + classifier rule | 同上，5/5 後 MOC 下架（MP backend 不穩）|
| `victory` | `peace` | 舊 alias | Recognizer 已正名為 `peace` |
| `thumbs_down` / `i_love_you` | — | Recognizer 內部 | 不在 MOC 9-gesture 內，event_builder drop 不發 |

---

## 5. 消費者拓撲

```
                     vision_perception_node
                              │
                              ▼
                   /event/gesture_detected
                              │
   ┌───────────┬──────────────┬──────────────┬──────────────┐
   │           │              │              │              │
   ▼           ▼              ▼              ▼              ▼
┌──────┐   ┌──────────┐   ┌───────────┐   ┌────────┐   ┌─────────┐
│Brain │   │Executive │   │interaction│   │event_  │   │Studio   │
│      │   │brain_node│   │_router    │   │action_ │   │gateway  │
└──────┘   └──────────┘   └───────────┘   │bridge  │   └─────────┘
   │           │              │           └────────┘        │
   │           │              ▼                │            ▼
   │           │   /event/interaction/         │       前端「gesture」
   │           │     gesture_command           │         channel
   │           │   (附 face name)              │
   │           │              │                ▼
   │           │              └──► event_action_bridge
   │           │                   ├─ stop→Go2 StopMove(1003)
   │           │                   ├─ ok→Go2 Content(1020)
   │           │                   ├─ thumbs_up→Go2 + TTS"謝謝！"
   │           │                   └─ wave→TTS "Hi！" (demo bridge)
   │           │
   │           │   ★ 生產主路徑 ★
   │           ├─ 重置 idle clock
   │           ├─ 快取 current_gesture
   │           ├─ Conversation-active gate：
   │           │    30s 內 chat / TTS playing → 抑制 wave/fist/index
   │           │    palm 例外（safety always）
   │           ├─ Direct skills:
   │           │    wave→wave_hello
   │           │    palm→system_pause
   │           │    fist→enter_mute
   │           │    index→enter_listen
   │           └─ Confirm skills:
   │                thumbs_up→wiggle (待 OK 確認)
   │                peace→stretch     (待 OK 確認)
   │
   ▼  pawai_brain._on_gesture_detected
   ├─ payload["gesture"] → self._recent_gesture = (name, ts)
   ├─ world_state_builder：stale 門檻 5s（gesture 是 transient event）
   └─ Prompt 注入 [最近手勢] 揮手（3 秒前）
       └─ 透過 _GESTURE_ZH 翻譯（wave→揮手, fist→握拳...）
       └─ scene_query 模式：與 face+pose+objects 一起 grounded 場景敘述
```

**重點分工**：
- **Brain**：只取語境（最近手勢），不觸發動作
- **Executive `brain_node`**：生產級技能路由 + Conversation gate + OK 確認狀態機
- **router + bridge**：demo / 安全旁路（legacy + 5/12 demo TTS bridge）

---

## 6. N7 收緊（5/11 commit 717a24a + 8d81dd9）

針對「fist 辨識率低 + 太慢」做的兩個參數調整：

| 參數 | 之前 | N7 | 影響 |
|------|:----:|:----:|------|
| `gesture_vote_frames` | 3 | **5** | 投票視窗 250ms，要 3/5 多數才贏（噪音容忍度 33%→80%）|
| `gesture_stable_s` | 0.5 | **0.3** | hold gate 縮短 200ms |
| **總延遲** | 750ms | **550ms** | 250ms 投票 + 300ms hold |

**vote_frames 3→5 的數學**：
- buffer=3：1 frame 雜訊就翻盤（容忍度 33%）
- buffer=5：要 3/5 才贏，1 frame 不會推翻（容忍度 60%）

附帶（同 commit）：`pose_classifier` 跌倒敏感度放寬，見 pose.md。

---

## 7. 模型選型（3/21 benchmark）

| 模型 | FPS (Jetson) | GPU | 決策 | 原因 |
|------|:----:|:----:|:----:|------|
| **MediaPipe Gesture Recognizer** | 7.2（與 pose 共跑）/ 21（單跑） | CPU 0% | **主線** | 端到端分類，原生 8 手勢符合 MOC，CPU 不搶 GPU |
| MediaPipe Hands + classifier | 16.8（單跑） | CPU 0% | 備援 | hand kp only，需手寫 stop/point/fist 規則 |
| RTMPose wholebody hand | 9.3 | GPU 80% | **拒用** | 正常距離 hand kp 散到臉部，無法用 |

---

## 8. 關鍵設定（vision_perception.yaml）

```yaml
vision_perception_node:
  ros__parameters:
    tick_period: 0.05              # 20Hz 內部處理
    publish_fps: 8.0               # debug image 頻率（解耦）
    
    # 手勢主參數
    gesture_backend: "rtmpose"     # 或 "mediapipe" / "recognizer"
    gesture_every_n_ticks: 3       # MP Hands 路徑跑頻（recognizer 忽略）
    gesture_vote_frames: 5         # ★ N7 ★
    gesture_stable_s: 0.3          # ★ N7 ★
    gesture_min_score: 0.1         # hand kp avg 信心門檻
    max_hands: 1                   # 1=快, 2=雙手（launch 可覆寫）
    hands_complexity: 0            # MP Hands 模型版本：0=lite
    
    # 模型路徑
    gesture_recognizer_model: "~/face_models/gesture_recognizer.task"
```

---

## 9. WaveDetector 動態手勢偵測

```python
class WaveDetector:
    window_s: float = 1.5
    min_reversals: int = 2
    min_amplitude_px: float = 50.0
    min_samples: int = 6
    
    def detect(self) -> bool:
        if len(samples) < 6: return False
        xs = [s.x for s in samples]
        if (max(xs) - min(xs)) < 50: return False  # 幅度太小
        
        reversals = 0
        last_sign = 0
        for prev, cur in zip(samples, samples[1:]):
            dx = cur.x - prev.x
            if abs(dx) < 1.0: continue  # 忽略 sub-pixel 抖動
            sign = 1 if dx > 0 else -1
            if last_sign != 0 and sign != last_sign:
                reversals += 1
            last_sign = sign
        
        return reversals >= 2
```

**為什麼旁路 vote + gate**：wave 過程中 hand 形狀會被 classifier 標成各種雜訊（palm / peace / fist），如果走 vote 會被均勻化掉。所以 wave 一旦偵測到就直接發，並用 2.5s cooldown 防重複觸發。

---

## 10. OK 幾何覆蓋（detect_ok_circle）

```python
def detect_ok_circle(hand_kps, scores, min_score):
    # Check 1: 拇指尖 + 食指尖距離 ≤ 30% hand_width
    touch_dist = distance(hand_kps[4], hand_kps[8])
    hand_width = distance(hand_kps[0], hand_kps[9])  # wrist → middle MCP
    touch_ratio = touch_dist / hand_width
    if touch_ratio > 0.30: return False, 0.0
    
    # Check 2: 中無小不全彎曲（避免 fist+thumb 誤判）
    n_other_curled = sum(curled(middle, ring, pinky))
    if n_other_curled >= 3: return False, 0.0
    
    # 信心：越貼近越高
    conf = 1.0 - touch_ratio / 0.30
    return True, min(avg_score, conf)
```

OK **覆蓋**前一階段的靜態分類結果（最高優先）。
**不映射 fist→ok**：5/5 後 GESTURE_COMPAT_MAP 清空，MOC §3 明定 fist=Mute / ok=Confirm 是對立語義。

---

## 11. 測試與運維

### 單元測試
- `test_gesture_classifier.py`：6 case（stop/point/fist/曖昧/零kp/低分）
- `test_gesture_recognizer_backend.py`：標籤映射（_GESTURE_MAP）+ 過濾驗證
- `test_event_builder.py`：事件 schema + GESTURE_COMPAT_MAP 空驗證

### 半自動 e2e
```bash
bash scripts/run_vision_case.sh stop 10
# 錄 10 秒 /event/gesture_detected，自動判 PASS/FAIL
```
case: stop | fist | point | wave | none

### Debug 全環境
```bash
bash scripts/start_vision_debug_tmux.sh
# 4 windows: camera + vision + status + foxglove
```

### 壓力測試
```bash
bash scripts/start_stress_test_tmux.sh 60
# face + vision + camera 同跑 60s（驗證 GPU/RAM 共存）
```

---

## 12. 已知問題（5/12 凍結項）

| # | 問題 | 處置 |
|---|------|------|
| 1 | `point` MediaPipe 不穩 | 5/5 後從 MOC enum 中下架（仍在 contract enum 但不主推） |
| 2 | 有效距離 ~2m，>2.5m kp 精度掉 | 無 distance guard，靠 kp 信心抑制 |
| 3 | 多人同框可能互擾 | 文件級 known issue，單人 demo |
| 4 | OK 幾何規則對遮擋敏感（半藏手） | touch ratio 門檻已調 |
| 5 | wave reset 後最小 6 frames 才能再觸發 | 為去重故意設計 |
| 6 | `ComeHere` / `Circle` 動態手勢 | Future bucket，未實作 |

---

## 13. Recent commits（手勢相關）

| Hash | 日期 | 內容 |
|------|------|------|
| 717a24a | 5/11 | feat(vision): N7 fist vote frames + fallen sensitivity（3→5, 0.5→0.3）|
| 8d81dd9 | 5/11 | feat: N7 fist vote + fallen threshold loosen + lane self-heal |
| 320d4d0 | 5/9 | feat(brain+vision): cover demo gesture and fall-alert painpoints |
| 95982d6 | 4/28 | feat(perception): Wave 動態手勢 + demo bridge gesture→/tts |
| efda3c0 | 5/8 | fix: thumb→thumbs_up enum align（critical: unblocks brain confirm flow）|
| 6a92e23 | 3/22 | feat(vision): integrate Gesture Recognizer Task API backend |
| eb422e9 | 5/11 | fix(brain): N6.1 — gesture_gate trace observability + test correctness |
| 44a8a73 | — | fix(executive): repair OK-confirm flow and survive gesture event sparsity |

---

## 14. 關鍵設計決策（給寫計畫書的參考）

1. **三 backend 策略**（CPU 主備 + GPU 拒用）：用 3/21 benchmark 表佐證 GPU 預算保護
2. **延遲設計**：250ms 投票 + 300ms hold = 550ms — 解釋為什麼要犧牲反應速度換穩定度（N7 commit 故事）
3. **動態 vs 靜態雙軌**：wave 旁路（temporal motion）vs 其他穩定 gate（label voting）
4. **多消費者拓撲**：raw event publish-once，Brain 取語境、Executive 觸發技能、router/bridge demo 旁路
5. **MOC §3 9-gesture enum**（系統控制 + 互動情緒 + 動態）：列出風險分級 + 直發 vs 確認
6. **fist ↔ ok 不映射**：MOC 語義對立，5/5 移除 compat map
7. **Conversation-active gate**（Executive 端）：30s 內 chat / TTS 中 → 抑制社交手勢，避免打斷對話流

---

## 15. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| Orchestrator | `vision_perception/vision_perception/vision_perception_node.py` |
| Recognizer backend | `vision_perception/vision_perception/gesture_recognizer_backend.py` |
| MP Hands backend | `vision_perception/vision_perception/mediapipe_hands.py` + `gesture_classifier.py` |
| WaveDetector | `vision_perception/vision_perception/dynamic_gesture_detector.py` |
| Event builder | `vision_perception/vision_perception/event_builder.py` |
| Downstream router | `vision_perception/vision_perception/interaction_router.py` |
| Demo bridge | `vision_perception/vision_perception/event_action_bridge.py` |
| Executive 路由 | `interaction_executive/interaction_executive/brain_node.py::_on_gesture` |
| Brain handler | `pawai_brain/pawai_brain/conversation_graph_node.py::_on_gesture_detected` |
| 設定 | `vision_perception/config/vision_perception.yaml` |
| Contract schema | `docs/contracts/interaction_contract.md` §4.3 |
| 模組文件 | `docs/pawai-brain/perception/gesture/README.md` + `AGENT.md` + `CLAUDE.md` |
| Benchmark 決策 | `docs/pawai-brain/perception/gesture/research/2026-03-21-benchmark-decision.md` |
