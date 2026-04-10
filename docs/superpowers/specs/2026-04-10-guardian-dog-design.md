# PawAI 居家守護犬 — 系統設計規格

> Status: current
> Date: 2026-04-10
> Author: Roy
> Scope: 產品願景 + Guardian Brain 架構 + Demo 計畫 + 實作指引

---

## 1. 願景與定位

### 一句話定位

> **PawAI 是一隻能在家中主動感知、主動回應，並在需要時主動靠近人的居家守護犬。**

### 展開定位

PawAI 不是一台會聊天的機器狗，也不是固定監視器，而是一個有在場感的家庭守護實體。平常安靜待命；看見家人時主動辨識與互動；看見陌生人、異常情況或收到召喚時，用聲音、動作、警示與靠近行為做出回應。

### 定位邊界

PawAI 的核心價值不是聊天，而是作為一個具有在場感、感知能力與實體反應能力的家庭守護實體。

| PawAI 是 | PawAI 不是 |
|---------|-----------|
| 居家守護犬 | 長照醫療設備 |
| 情境感知的守護實體 | 通用聊天機器人 |
| 有實體反應能力的 agent | 固定監視器 |
| 可降級的穩健系統 | 把成敗綁在 LLM 上的 demo |

### 敘事定位

從「長照」退到「居家互動守護」，避開弱勢族群審查強度。跌倒偵測定位為「安全輔助功能」而非核心賣點。

答辯句：「PawAI 的定位是居家互動守護，不是醫療照護設備。」

---

## 2. 為什麼非 Go2 不可

評審一定會問。我們的回答不是「機器狗比較酷」，而是：

> 如果我們只想做辨識和通知，用攝影機就夠了。但我們要做的是一個會認人、會回應、必要時會靠近人的守護實體，所以才需要 Go2。

具體論點：

| 能力 | 攝影機 | 音箱 | 手機 | Go2 |
|------|:-----:|:---:|:---:|:---:|
| 看見人 | ✅ | ❌ | ❌ | ✅ |
| 認出人 | ✅ | ❌ | ❌ | ✅ |
| 主動靠近 | ❌ | ❌ | ❌ | ✅ |
| 實體動作回應 | ❌ | ❌ | ❌ | ✅ |
| 在場陪伴感 | ❌ | ❌ | ❌ | ✅ |
| 語音互動 | ❌ | ✅ | ✅ | ✅ |
| 警示通知 | ✅ | ✅ | ✅ | ✅ |

**非 Go2 不可的地方，不是 AI，而是 embodied presence + active response + physical approach。**

---

## 3. 無雷達 / 有雷達雙版本

### 主案：無雷達版（定點守護犬）

不依賴導航，現有模組已撐得住。

| 能力 | 說明 | 狀態 |
|------|------|:----:|
| 熟人辨識 + 個人化打招呼 | YuNet + SFace | ✅ 已驗證 |
| 陌生人警戒反應 | identity_stable == unknown | 🔄 邏輯待實作 |
| 語音 / 手勢互動 | ASR + LLM + TTS / Gesture Recognizer | ✅ 閉環通過 |
| 特定姿勢 / 物體提醒 | MediaPipe Pose / YOLO26n | ✅ 已驗證 |
| Studio 遠端觀測 | Next.js + WebSocket | ✅ 閉環通過 |
| 簡單朝向反應 | 原地轉向目標 | 🔄 待實作 |

### 升級案：有雷達版（短距主動守護犬）

RPLIDAR 到貨 + odom 品質驗證通過才啟動。**不是另一個產品，是同一隻守護犬的能力升級。**

| 新增能力 | 說明 | 前提 |
|---------|------|------|
| 短距安全靠近 | 看到人 → 前進 1-2m → 停在安全距離 | RPLIDAR + collision_monitor |
| 預設短路線移動 | 固定 waypoint 巡守 | odom 品質 OK |
| 到點查看 | 收到事件後移動到指定位置 | SLAM 可行 |
| 360° 反應式避障 | RPLIDAR scan → safety stop | RPLIDAR 驅動正常 |

**正確 framing**：買雷達 = 補足安全移動能力，不是買雷達 = 導航完成。

**風險**：Go2 四足 odom 漂移可能導致 SLAM 失敗。Day 1 驗證：錄 30 秒 odom + scan bag，漂移 > 0.3m/10s → SLAM NO-GO，但避障仍可用。

---

## 4. 五個 Guardian 場景

所有功能都服務於以下五個場景。不是功能拼盤，而是守護犬在家裡會做的事。

### 場景 1：熟人回家（P0）

```
觸發：人臉辨識到已註冊的家人
守護犬反應：辨識身份 → 個人化問候 → 動作回應
像什麼：你家的狗聽到你開門，跑過來搖尾巴迎接你
```

- 人臉：辨識身份（「這是奶奶」）
- 語音：個人化問候（「奶奶回來了！」）
- 手勢：揮手 → 回應揮手
- Go2：Hello(1016) → Content(1020)
- Studio：顯示 identity + guardian mode 切換

### 場景 2：使用者召喚（P0）

```
觸發：手勢（招手/揮手）或語音（「過來」「PawAI」）
守護犬反應：回應召喚 → 等待指令 → 語音互動
像什麼：你叫你家的狗，它抬頭看你、回應你的聲音
```

- 手勢：wave = 「我在這裡」、stop = 「停」、thumbs_up = 正面回饋
- 語音：自由對話（LLM）或固定台詞（Plan B）
- 姿勢：人坐著 → Go2 調整回應方式
- 物體：看到杯子 →「要喝水嗎？」
- **無雷達版**：回應召喚並朝向使用者（語音 + 動作 + 轉向）
- **有雷達版**：短距安全靠近後等待指令

### 場景 3：陌生人警戒（P0）

```
觸發：人臉辨識到未註冊的臉（經穩定性確認）
守護犬反應：保持距離 → 警戒姿態 → 語音提醒 → Studio 推播
像什麼：家裡的狗看到陌生人，站起來盯著看、低吼
```

- 人臉：辨識結果 unknown，**且**滿足 anti-false-positive policy（見下）
- 語音：「偵測到不認識的人，已通知家人」
- 手勢：警戒模式下不回應手勢指令（守護犬不聽陌生人的話）
- Go2：BalanceStand(1002)（站穩、注視）
- Studio：即時推播截圖 + 時間戳

**Anti-false-positive policy**（防誤警）：
unknown 不可直接等於警戒。觸發陌生人警戒必須同時滿足：
1. `identity_stable == "unknown"` 穩定持續 ≥ 3 秒（排除短暫誤判）
2. `face_count > 0`（確認有人臉存在，排除無人幻覺）
3. `not recently_alerted`（同一 track 30 秒內不重複警戒）
4. 低光/逆光環境下可降級為「觀察模式」而非直接警戒（避免誤報翻車）

### 場景 4：異常偵測（P1）

```
觸發：姿勢辨識到跌倒 / 久坐不動
守護犬反應：語音關懷 → Studio 推播
```

- 姿勢：fallen = 警報、久坐 = 溫和提醒
- 語音：跌倒 →「偵測到異常！已通知家人」
- 人臉：確認是誰（通知附上身份）
- **注意**：跌倒偵測幻覺率仍高，Demo 可關閉（`enable_fallen` 參數）

### 場景 5：日常待命（P1）

```
觸發：無人互動時的預設狀態
守護犬反應：定點待命 / 持續感知
```

- 無雷達版：坐著待命，感知不停
- 有雷達版：固定路線巡守
- Go2：Sit(1009)，偶爾 Stretch(1017)
- Demo 用途：開場 10-20 秒自然帶出，不獨立成段

---

## 5. Guardian Brain 三層架構

### 核心定義

> PawAI Guardian Brain 是面向家庭守護場景的高階決策引擎。它接收來自人臉、語音、手勢、姿勢、物體與機器人狀態的多模態事件，形成 guardian context，並在安全規則約束下選擇最合適的守護技能與回應方式。

### Brain / Executive 關係（必須明確）

```
Guardian Brain：高階決策與表達層 — 決定「該做什麼、該說什麼」
Executive：唯一動作出口與仲裁層 — 決定「能不能做、怎麼做」
Safety Layer：Executive 內的最高優先 deterministic guard — 決定「必須阻擋什麼」
```

**Brain 不直接執行，Executive 才執行。** Brain 提建議，Executive 做仲裁，Safety 做硬阻擋。這確保系統永遠不會變成「LLM 控狗」。

### 三層架構

```
┌─────────────────────────────────────────┐
│  Layer C: Expression Layer              │
│  reply_text / tone / wording / style    │
│  bark vs warning vs reassurance         │
│  Studio trace narration                 │
│  ← LLM 語言能力在這裡                    │
└──────────────┬──────────────────────────┘
               │ selected_skill + reply_text
┌──────────────▼──────────────────────────┐
│  Layer B: Guardian Policy Layer         │
│  guardian context formation             │
│  意圖判斷 → skill selection             │
│  guardian memory (per-person)           │
│  policy override (deterministic rules)  │
│  ← 守護犬大腦核心在這裡                   │
│  ※ LLM function calling 僅作為 skill    │
│    selection 的實作機制之一，不代表       │
│    LLM 擁有最終動作決策權。              │
│    Policy override 永遠可以覆蓋 LLM。   │
└──────────────┬──────────────────────────┘
               │ skill_contract + action
┌──────────────▼──────────────────────────┐
│  Layer A: Safety Layer                  │
│  stop / obstacle / emergency            │
│  banned_api gate                        │
│  pre-action validation                  │
│  ← 永遠 deterministic，不經 LLM          │
│  ← Executive 內最高優先                   │
└─────────────────────────────────────────┘
               │
          Go2 動作執行
```

### 降級路徑

```
正常：Brain(Policy+Expression) → Executive(Safety) → Go2
LLM 掛：Policy 繼續，Expression 降級為固定台詞 → Executive → Go2
Groq 掛：Policy 降級為 RuleBrain → Executive → Go2
全掛：Safety Layer 仍能 stop/emergency → Go2
```

這確保系統在任何一層掛掉時都能 graceful degrade。

### Guardian Skills（本期）

| Skill | 說明 | 場景 |
|-------|------|------|
| `greet_known_person` | 個人化打招呼 | 熟人回家 |
| `alert_unknown_person` | 警戒反應 | 陌生人 |
| `respond_to_call` | 回應召喚 | 使用者召喚 |
| `acknowledge_gesture` | 手勢回應 | 互動中 |
| `issue_reminder` | 物品/姿勢提醒 | 日常陪伴 |
| `approach_short` | 短距安全靠近 | 有雷達版 |
| `stop_now` | 立即停止 | 任何場景（Safety） |
| `self_introduce` | 自主介紹自己（meta skill，內部呼叫 skill queue 執行 sequence） | Demo 開場 |

### Action Sequencing（Skill Queue 機制）

Guardian Brain 支援呼叫**多個 skill 組成的行為序列**，不只是單一動作。這是展示 embodied agent orchestration 的核心機制。

```
使用者輸入：「PawAI，介紹你自己」
  ↓
Expression Layer：生成 narration 串接每個 skill
  ↓
Policy Layer：透過 function calling 規劃 skill sequence
  ↓
Executive Skill Queue：依序執行，每個 skill 仍走完整 pre-action validation
  ↓
Safety Layer：任何時候 stop / emergency 可打斷整個 queue
```

**執行規則**：
- Queue 內每個 skill 仍須通過 Safety Layer 驗證
- Safety event（stop/emergency/fallen）會**立即清空 queue**
- 每個 skill 之間有 narration（TTS 銜接語）
- Queue 有 timeout（例如 2 分鐘），超時自動終止
- Queue 執行期間 guardian_state 顯示 `active_sequence` 讓 Studio 可觀測

**`self_introduce` 預設 sequence**（Demo 開場用）：

```python
self_introduce = [
    ("hello",       "我是 PawAI，你的居家守護犬"),
    ("sit",         "平常我會坐著待命，感知周遭"),
    ("stand",       "看到家人回來我會主動打招呼"),
    ("content",     "你可以用手勢或聲音召喚我"),
    ("balance_stand", "遇到陌生人我會進入警戒模式"),
    ("wiggle_hips", "今天也請多多指教"),
]
```

**為什麼這重要**：單一動作是 trigger-response，sequence 是 agent orchestration。評審看到的是「它在自主規劃」而不是「它在反應」。

**重要的架構定性（答辯時要能講清楚）**：

> `self_introduce` 不是自由規劃 agent，而是 **safety-gated scripted orchestration**。

具體意思：
- sequence **可由 Brain 觸發**（透過語音、手勢、或 function calling）
- 但 sequence **內容仍在白名單 skill 內**（不會突然叫出 BANNED api）
- **每一步都經 Executive + Safety Layer 驗證**（pre-action validation 不跳過）
- **任何時候可被 stop 中斷**（safety event 立即清空 queue）

這樣評審聽到「自主」時，你不會把話說太滿；聽到「scripted」時，你也可以強調這是**刻意的安全設計**，不是能力不足。這正是 harness-oriented design 的核心論述——**能力受環境約束，才是可靠的 embodied agent**。

### Skill Contract 格式

每個 skill 都有明確的執行契約：

```
skill: approach_short
  preconditions: [lidar_ok, obstacle_clear, not_emergency]
  expected_outcome: robot_closer_to_target
  fallback_skill: stop_now
```

### Guardian Memory（本期）

不是聊天記憶，是守護記憶：

| 記憶項 | 說明 | 用途 |
|--------|------|------|
| person_profile | 誰是誰（name, face_id） | 個人化問候 |
| greeting_cooldown | 上次打招呼時間 | 避免重複 greeting |
| recent_incidents | 最近的異常事件 | 通知內容 |
| last_interaction_state | 上次互動狀態 | 連續性 |
| session_context | 本次 session 已見到誰 | 短期記憶 |

重啟清空，不做持久化（對 Demo 夠用）。

### Guardian State Artifact

結構化狀態，發布到 `/state/guardian`：

```json
{
  "timestamp": 1744000000.0,
  "executive_state": "conversing",
  "active_user": "alice",
  "last_skill": "greet_known_person",
  "last_skill_outcome": "greeting_done",
  "interaction_count": 3,
  "safety_flags": {
    "emergency": false,
    "obstacle": false,
    "tts_playing": false
  },
  "known_users_seen": ["alice"],
  "fallback_active": false
}
```

設計原則：
- `safety_flags` 是 Safety Layer 的 read-only 狀態
- `last_skill + outcome` 讓 Policy Layer 有 working memory
- `active_user` 從最近的 `identity_stable` event 填入
- Studio 訂閱此 topic 顯示 guardian mode

### 借鑑概念

| 借什麼 | 從哪借 | 用在哪層 |
|--------|--------|---------|
| `beforeToolCall` safety gate | pi-mono | Layer A: pre-action validation |
| ROS2 tool abstraction | rosclaw | Layer B: skill → tool → robot action |
| per-person memory profile | hermes-agent | Layer B: guardian memory |
| skill → tool → action 形態 | dimos | Layer B → Executive dispatch |

**不整包導入任何框架。** 只借概念，用自己的 ROS2 架構實作。

### Harness-Oriented Design

> PawAI Guardian Brain 採用 harness-oriented design：不是讓單一模型直接控制機器狗，而是透過 safety rules、guardian policy、skills、tool abstraction、memory 與 observability，構建一個能穩定產生守護行為的執行環境。

---

## 6. 八模組在守護犬中的角色

| 模組 | 角色 | 定位 | 現狀 |
|------|------|------|:----:|
| 人臉辨識 | 核心支柱 | 認人能力：熟人/陌生人區分 | ✅ 穩定，缺陌生人警戒邏輯 |
| 語音功能 | 輔助互動層 | 問候、簡答、警示、Plan B | ✅ 閉環，缺個性和記憶 |
| 手勢辨識 | 互動控制層 | wave=過來、stop=停、讚=回饋 | ✅ 穩定，缺 wave/point 映射 |
| 姿勢辨識 | 狀態感知層 | 次要警示，不押跌倒當主賣點 | ✅ 穩定，跌倒幻覺風險 |
| 物體辨識 | 場景強化器 | 少量白名單日常提醒 | ✅ 大物件 OK，小物件弱 |
| AI 大腦 | 系統核心 | Guardian Brain 三層決策引擎 | 🔄 從規則機升級 |
| Studio | 控制台 | 遠端觀測 + 互動入口 | ✅ 閉環通過 |
| 導航避障 | 候選升級能力 | 短距安全移動，4/14 定案 | 🔄 RPLIDAR 評估中 |

---

## 7. Demo 計畫

### P0 Demo 劇本（3 分鐘，5/16 省夜 Demo）

Demo 不是展示功能數量，而是用三個場景讓評審相信這真的是一隻居家守護犬。

```
0:00 - 0:10  開場：日常待命（自然帶出）
  Go2 安靜待命，Studio 顯示 guardian mode = idle

0:10 - 0:45  ★ Wow Moment：Agent-Generated Self Demo
  主持人：「PawAI，介紹你自己」
  → Guardian Brain 呼叫 self_introduce skill
  → Executive 啟動 skill queue
  → Go2 自主執行 sequence：
     1. Hello + 「我是 PawAI，你的居家守護犬」
     2. Sit + 「平常我會坐著待命」
     3. Stand + 「看到家人我會主動打招呼」
     4. Content + 「你可以召喚我」
     5. BalanceStand + 「遇到陌生人我會警戒」
     6. WiggleHips + 「今天也請多多指教」
  → Studio 同步顯示 active_sequence + 每個 skill 的執行狀態
  回答：它不是觸發反應系統，而是會自主規劃行為的 agent

0:45 - 1:15  場景 1：熟人回家
  Roy 走進畫面 → 人臉辨識 →「Roy 你好！歡迎回來」
  → Go2 站起 + Hello 動作
  → Studio 同步顯示 identity / state / trace
  回答：它認得你，會主動回應

1:15 - 1:50  場景 2：使用者召喚
  使用者用語音或手勢召喚
  → Go2 語音回應 + 動作
  → 無雷達版：語音 + 動作 + 朝向反應
  → 有雷達版：短距安全靠近
  回答：它會回應需求，不是聊天 bot

1:50 - 2:30  場景 3：陌生人警戒
  換一個未註冊的人進場
  → Go2 不用 greeting，改成警戒姿態 + 語音提醒
  → Studio 顯示 guardian mode 切換 + event 推播
  回答：為什麼是守護犬，不是陪聊狗

2:30 - 3:00  收尾
  口頭補：可延伸到異常事件提醒與遠端觀測
  Studio 畫面切 event timeline / health / mode
  如果有雷達：「可支援短距主動靠近與到點查看」
```

**開場的 Wow Moment 設計原則**：
- **可排練性**：sequence 是預設的，Demo 當天不會亂講（vs. VLM 每次輸出都不同）
- **安全性**：每個 skill 仍走 Safety Layer，stop 手勢可隨時打斷
- **可觀測性**：Studio 即時顯示 skill queue 進度，評審看得見「大腦在規劃」
- **答辯價值**：可以直接講「我們做的是 embodied agent orchestration」，這詞在研究所和面試都有份量

### P0 / P1 場景表

| 優先級 | 場景 | Demo 呈現 |
|:------:|------|-----------|
| P0 | 熟人回家 | 完整演出 |
| P0 | 使用者召喚 | 完整演出 |
| P0 | 陌生人警戒 | 完整演出 |
| P1 | 異常偵測 | 口頭帶過（跌倒幻覺風險） |
| P1 | 日常待命 | 開場自然帶出 |
| P1 | 物件提醒 | 可穿插在場景 2 |
| P1 | 有雷達短距靠近 | 視 RPLIDAR 結果 |
| P1 | 預設路線巡守 | 視 SLAM 結果 |

### Plan B（GPU 斷線版）

語音改走 Plan B 固定台詞（需擴充至 15+ 組），其他場景不變（人臉/手勢/姿勢/物體都是本地模型）。

---

## 8. 降級策略

| 故障 | 影響 | 降級方式 |
|------|------|---------|
| Groq API 斷線 | Expression + Policy 部分失能 | Policy 降級為 RuleBrain 規則樹，Expression 降級為固定台詞 |
| Cloud ASR/LLM 主線失效 | 雲端語音鏈路中斷 | 降級為本地最小意圖路徑（Energy VAD + Intent fast path + RuleBrain + Piper TTS），最差情況為 Plan B 固定台詞模式 |
| D435 斷線 | 人臉 + 深度 失能 | 純語音 + 手勢互動 |
| Jetson 供電斷電 | 全系統失能 | Go2 自己站穩（韌體層） |
| RPLIDAR 失敗 | 導航不可用 | 回退到無雷達版（主案不受影響） |
| 跌倒偵測誤報 | 假警報 | `enable_fallen=false` 關閉 |

---

## 9. 本期不做

| 項目 | 原因 |
|------|------|
| 通用 autonomous agent | Go2 必要性會變弱 |
| 自我進化 skill learning | 需要 deterministic guardian behavior |
| 大型 persistent memory system | Demo 不需要跨 session 記憶 |
| LLM 直接控制馬達 | Brain 不直接執行，Executive 才執行 |
| 整包導入外部框架 | dimos/openclaw/hermes 太重，只借概念 |
| 全屋自主導航 | odom 漂移風險，不承諾 |
| 聲音複製 / AI 訂外賣 | 與 Go2 必要性太弱 |

---

## 10. Implementation Notes

### 改動概覽

預估為小幅增量修改，集中於 5 個核心檔案，全部向後相容，不破壞現有邏輯。

| 檔案 | 改動內容 |
|------|---------|
| `llm_contract.py` | skill contract 欄位 + tool schema 定義 |
| `state_machine.py` | SkillContract dataclass + guardian_state 擴展 |
| `interaction_executive_node.py` | pre-action validation + `/state/guardian` publisher |
| `llm_bridge_node.py` | policy_override + guardian_memory + function calling 分支 |
| `event_action_bridge.py` | safety_alert publisher（最低優先，可延後） |

### 建議執行順序

1. `llm_contract.py`（純資料，無 ROS2 依賴，最安全）
2. `state_machine.py`（純 Python，有既有測試覆蓋）
3. `interaction_executive_node.py`（pre-action validation 是最高價值改動）
4. `llm_bridge_node.py`（policy_override + function calling）
5. `event_action_bridge.py`（最低優先，可跳過）

> 具體行數和 patch 範圍在 implementation plan 中定義，不在本 spec 鎖死。

### 關鍵改動摘要

**Pre-action Validation**（interaction_executive_node.py）：
在 `_execute_result()` 前插入 `_validate_preconditions()`，檢查 skill contract 的 preconditions。驗證失敗時執行 fallback_skill。

**Policy Override**（llm_bridge_node.py）：
在 `_dispatch()` 前加 `_policy_override()`，讓 Policy Layer 可以覆蓋 LLM 的 skill selection。LLM 決定語言（reply_text），Policy 決定動作（selected_skill）。

**Guardian Memory**（llm_bridge_node.py）：
擴充現有 `_face_greet_history` 為 `_guardian_memory` dict，存 per-person profile + session context。不持久化，重啟清空。

**Guardian State Topic**（interaction_executive_node.py）：
新增 `/state/guardian` topic（TRANSIENT_LOCAL QoS），發布結構化 guardian_state artifact，供 Studio 和其他 node 訂閱。

---

## 11. 代表作論述角度

這個專案不只是「串了很多 AI API」，而是一個完整的系統作品：

| 面向 | 論述 |
|------|------|
| System Architecture | 三層架構（Driver → Perception → Executive），事件驅動，單一控制權 |
| Agent Design | Guardian Brain 三層（Safety → Policy → Expression），harness-oriented |
| HRI | 五種感知模態 × 五種場景 = 情境式互動設計 |
| Edge/Cloud Tradeoff | 每個模組都有本地 + 雲端 fallback，四級降級策略 |
| Robotics Productization | 從感知到動作的完整 pipeline，skill contract，pre-action validation |
| Reliability | Plan B 固定台詞、enable_fallen 開關、供電風險管理、guardian_state 可觀測 |
| Observability | PawAI Studio 即時影像 + 狀態面板 + guardian mode + event timeline |

答辯可講：多模態感知、embodied guardian brain、harness-oriented design、skill contract、graceful degradation、產品故事與風險控管。

---

## 12. 與現有文件的關係

- **本文件**：系統設計規格（architecture + product vision + implementation notes）
- **`docs/mission/README.md`**：專案管理入口（時程、分工、交付），需同步更新定位段
- **`pawai-studio/docs/0410assignments/`**：四人分工執行細節，場景框架需同步
- **`references/project-status.md`**：每日狀態更新，需反映新方向

---

## 附錄 A：方向收斂歷程

4/9 外部會議後到 4/10 定案之間，考慮過的五個產品方向。保留在此作為決策脈絡，避免未來重新繞回已被排除的路線。

| # | 方向 | 一句話 | 為何不選 |
|:-:|------|-------|---------|
| 1 | **看門犬**（已採納） | 熟人辨識 + 陌生人警戒 + 異常通知 | **✅ 最終選擇**：能用現有模組撐起、回答「為什麼非 Go2 不可」、風險可控 |
| 2 | 長照機器狗 | 陪伴長者 + 跌倒偵測 + 用藥提醒 | 弱勢族群評審嚴格、跌倒偵測幻覺率高、不想把勝負押在單一高風險功能 |
| 3 | 打熊狗 / 護院犬 | 驅趕入侵者、大型動物警示 | 需要導航 + 主動追蹤，4/14 LiDAR 才定案，技術風險太高 |
| 4 | R2-D2 式情緒互動狗 | 用動作+聲音表達情緒，不靠 LLM | 互動深度不足、缺乏主故事、Demo 容易變成「會動的玩具」 |
| 5 | AI 助理狗 | 訂外賣、查天氣、控制家電、CLI/API 串接 | Go2 必要性最弱，做這個不如用手機+音箱 |

### 收斂原則

最終採用方向 1（看門犬/守護犬），加上方向 4 的部分元素（R2-D2 風格的實體反應 + 語氣設計），捨棄方向 2（長照）避開弱勢族群評審，捨棄方向 3（打熊狗）避免導航風險綁主線，捨棄方向 5（AI 助理）因為失去 Go2 必要性。

**關鍵決策句**：
> 「如果我們只想做辨識和通知，用攝影機就夠了。但我們要做的是一個會認人、會回應、必要時會靠近人的守護實體，所以才需要 Go2。」

方向 2、3、5 都無法穩定回答這個問題，只有方向 1（輔以方向 4 的風格）能同時撐住產品故事與技術可行性。
