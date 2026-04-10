# PawAI 居家互動機器狗 — 系統設計規格

> **Status: current**
> Date: 2026-04-11
> Author: 盧柏宇
> Scope: 產品願景 + PawAI Brain 架構 + Demo 計畫 + 四人分工原則 + 實作指引
> Supersedes: [`2026-04-10-guardian-dog-design.md`](2026-04-10-guardian-dog-design.md)

---

## 關於本 Spec 與 4/10 Spec 的關係

**繼承 4/10 spec 的部分**（90% 技術設計）：
- 三層架構（Safety / Policy / Expression Layer）
- Skill Contract 格式（preconditions / expected_outcome / fallback_skill）
- Skill Queue / Action Sequencing 機制
- `self_introduce` meta skill（sequence 台詞重寫）
- Pre-action Validation 設計
- 借鑑概念（pi-mono beforeToolCall / rosclaw tool abstraction / hermes per-person memory / dimos skill→tool）
- Harness-Oriented Design 論述
- Privacy-by-Design 設計原則

**取代 4/10 spec 的部分**：
- 產品定位：居家守護犬 → 居家互動機器狗（兼具守護能力）
- 互動/守護比例：守護為主 → **互動 70% / 守護 30%**
- 命名體系：Guardian Brain → **PawAI Brain**（守護相關術語保留在子域，見 §5.1）
- Demo 三場景：三場守護戲 → 互動為主 + 陌生人警告為輔
- 八模組角色：全部從守護角度重寫為互動角度
- `self_introduce` sequence 台詞：改為互動主體 + 守護一句帶過

---

## 1. 願景與定位

### 一句話定位

> **PawAI 是一隻以居家互動為核心，並具備守護能力的家庭機器狗。**

### 展開定位

PawAI 不是聊天機器人，也不是固定監視器，而是一個有在場感、會多模態感知、能實體回應的家庭機器狗。它的主要工作是**透過手勢、姿勢、語音、物體辨識與使用者互動**，並在偵測到陌生人、異常情況時提供守護提醒。

### 核心論述句

> **PawAI 的設計不是把 AI 裝到機器狗上，而是把感知、決策、安全與實體互動整合成一個可在家庭場景中可靠運作的 embodied interaction system。**

### 定位邊界

| PawAI 是 | PawAI 不是 |
|---------|-----------|
| 居家互動機器狗 | 純聊天機器人 |
| 多模態感知 + 實體反應 | 固定監視器 |
| 可降級的穩健系統 | 把成敗綁在 LLM 上的 demo |
| 以互動為核心，守護為輔 | 長照醫療設備 |

### 互動 / 守護比例

- **互動 70%**：手勢 / 姿勢 / 語音 / 物體辨識 → 觸發動作 or 移動（Demo 主秀）
- **守護 30%**：陌生人警告 + 巡邏（視雷達時程）+ 跟隨（目標假設，文件級）

守護不是獨立產品線，而是**價值增強器**——它回答了「為什麼不是平板/音箱/攝影機」。

### 敘事定位

從「長照機器狗」退到「居家互動守護」，避開弱勢族群審查強度。跌倒偵測定位為「安全輔助功能」而非核心賣點。

**答辯句**：「PawAI 的定位是居家互動守護，不是醫療照護設備。」

---

## 2. 為什麼非 Go2 不可

評審一定會問。回答不是「機器狗比較酷」，而是：

> 如果我們只想做辨識和通知，用攝影機就夠了。如果我們只想做語音互動，用音箱就夠了。但我們要做的是一個**會看、會聽、會動、會回應你身體語言**的互動實體——embodied presence + active response + physical approach，這需要實體機器狗。

| 能力 | 攝影機 | 音箱 | 平板 | Go2 |
|------|:-----:|:---:|:---:|:---:|
| 看見人 | ✅ | ❌ | ✅ | ✅ |
| 認出人 | ✅ | ❌ | ✅ | ✅ |
| 聽懂手勢 | ✅ | ❌ | ✅ | ✅ |
| 聽懂姿勢 | ✅ | ❌ | ✅ | ✅ |
| 實體動作回應 | ❌ | ❌ | ❌ | ✅ |
| 主動移動 | ❌ | ❌ | ❌ | ✅ |
| 在場陪伴感 | ❌ | ❌ | ❌ | ✅ |
| 警示威懾 | ❌ | ❌ | ❌ | ✅ |

**非 Go2 不可的地方，是 embodied presence + active response + physical approach。**

### 為什麼選四足而不是人形或輪型

四足機器人是**現階段穩定性、移動能力、量產可行性最平衡的 embodied 載體**。

**業界觀點（2026-04 輔大遞固科技演講 / NVIDIA GTC 2026）**：
- 四足機器人：最穩定、控制難度最低、2025-2026 全球大量產
- 輪型機器人：穩定性中等，受限於地形
- 人形機器人：雙足行走穩定性不足，預估 2029 才量產
- 黃仁勳：「具身智能是下一個黃金十年」

**對 PawAI 的意義**：選 Go2 不是因為「手邊有」，而是因為**在 2026 年這個時間點，四足是唯一同時成熟、可用、可量產的具身智能載體**。

---

## 3. 無雷達 / 有雷達雙版本

### 主案：無雷達版（定點互動機器狗）

不依賴導航，現有模組已撐得住。互動能力 100%、守護能力僅限陌生人警告。

| 能力 | 說明 | 狀態 |
|------|------|:----:|
| 手勢辨識 → 動作 / 模式切換 | MediaPipe Gesture Recognizer | ✅ 基礎完成，模式切換設計待定（4/15） |
| 姿勢辨識 → 狀態感知 | MediaPipe Pose | ✅ 已驗證 |
| 語音互動 | ASR + LLM + TTS 閉環 | ✅ 閉環通過 |
| 物體辨識 → 情境回應 | YOLO26n | ✅ 已整合 |
| 熟人辨識 + 個人化打招呼 | YuNet + SFace | ✅ 已驗證 |
| 陌生人警告 | unknown + anti-false-positive | 🔄 邏輯待實作 |
| Studio 遠端觀測 | Next.js + WebSocket | ✅ 閉環通過 |

### 升級案：有雷達版（+ 巡邏 + 短距靠近）

雷達確定採購（老師需跑國科會流程），到貨時程未定。

| 新增能力 | 說明 | 前提 |
|---------|------|------|
| 定點巡邏 | 固定 waypoint 路線 | RPLIDAR + odom 驗證 |
| 短距安全靠近 | 看到人 → 前進 1-2m → 停 | RPLIDAR + collision_monitor |
| 360° 反應式避障 | RPLIDAR scan → safety stop | RPLIDAR 驅動正常 |
| 跟隨（目標假設） | YOLO 人體追蹤 + 導航 | 難度極高，文件級 future work |

**正確 framing**：買雷達 = 補足安全移動能力，不是買雷達 = 導航完成。

---

## 4. PawAI 核心能力場景

### 互動場景（P0，Demo 主秀 — 下週細節待定）

> **TBD by 2026-04-15**：黃旭將在 4/12-4/14 設計手勢模式切換機制後補齊細節。本節先列出高階結構，下週會議後細化。

#### 互動場景 A：多模態觸發（手勢 / 姿勢 / 語音 / 物體）

核心機制：**感知事件 → PawAI Skills → 動作 or 移動**

初步方向（4/15 前定案）：
- **手勢模式切換**（黃旭提出，細節 TBD）：比「1」→ 聊天模式、比「2」→ 聽故事模式、比 stop → 待機
- **語音互動**：LLM 自由對話 + Plan B 固定台詞
- **姿勢狀態感知**：久坐提醒、跌倒警示（選擇性開啟）
- **物體情境回應**：看到杯子 →「要喝水嗎？」、看到書 →「在看書呀」
- **新互動 idea（待定）**：顏色辨識（紅色牌 = Yes）、跳舞互動（參考凱比）

#### 互動場景 B：熟人辨識 + 個人化問候

```
觸發：人臉辨識到已註冊的家人
反應：辨識身份 → 個人化問候 → 動作回應
像什麼：你家的狗聽到你開門，跑過來搖尾巴迎接你
```

### 守護場景（P1，Demo 30% 時間）

#### 守護場景 1：陌生人警告（P0 實演）

```
觸發：人臉辨識到未註冊的臉（經 anti-false-positive 穩定性確認）
反應：保持距離 → 警戒姿態 → 語音提醒 → Studio 推播
```

- 人臉：辨識結果 unknown，**且**滿足 anti-false-positive policy
- 語音：「偵測到不認識的人，已通知家人」
- PawAI Skills：不回應手勢指令（警戒模式下鎖定互動）
- Go2：`BalanceStand(1002)`
- Studio：即時推播截圖 + 時間戳

**Anti-false-positive policy**（防誤警）：
1. `identity_stable == "unknown"` 穩定持續 ≥ 3 秒
2. `face_count > 0`（排除無人幻覺）
3. `not recently_alerted`（同一 track 30 秒內不重複）
4. 低光/逆光環境下降級為「觀察模式」而非警戒

#### 守護場景 2：巡邏（P1，雷達到貨後實演 or 錄影）

```
觸發：進入巡邏模式（手勢或預設排程）
反應：按固定 waypoint 移動 + 360° 感知
```

- 前提：RPLIDAR 到貨且 odom 品質驗證通過
- 無雷達版：不做巡邏，改用定點待機 + 感知
- Demo 策略：雷達到貨 → 實演；來不及 → 錄影帶過

#### 守護場景 3：跟隨（目標假設，文件級）

- 會議共識：**難度極高，不列必做，文件上作為目標假設**
- 需要 YOLO 人體追蹤 + 導航避障整合
- Spec 定位：**future work**，不做實作、不排進 Demo
- 寫進 4/13 專題文件的「未來發展」章節

---

## 5. PawAI Brain 三層架構

### 核心定義

> PawAI Brain 是面向家庭互動與守護場景的高階決策引擎。它接收來自人臉、語音、手勢、姿勢、物體與機器人狀態的多模態事件，形成互動上下文，並在安全規則約束下選擇最合適的技能與回應方式。

### 5.1 命名體系（4/11 定案）

| 層級 | 名稱 | 說明 |
|------|------|------|
| **系統總名** | **PawAI Brain** | 對外、對內一致 |
| **三層架構** | Safety Layer / Policy Layer / Expression Layer | 去掉 Guardian 前綴 |
| **技能集合** | **PawAI Skills** | 含 interaction / chat / guardian_alert / approach 等子類 |
| **記憶集合** | **PawAI Memory** | 含 `person_profiles` / `guardian_incidents` / `session_context` |
| **狀態 topic** | **`/state/pawai_brain`** | 結構化 artifact 發布 |
| **守護子域** | `guardian_mode` / `guardian_alert` / `guardian_behavior` / `guardian_incident` | **保留在子域，不消失** |

**命名原則**：主架構去 guardian 化（因為不再是守護犬主軸），但守護相關術語保留在子域（因為它仍是價值錨點，最能回答「為什麼不是攝影機」）。

### 5.2 Brain / Executive 關係

```
PawAI Brain：高階決策與表達層 — 決定「該做什麼、該說什麼」
Executive：唯一動作出口與仲裁層 — 決定「能不能做、怎麼做」
Safety Layer：Executive 內的最高優先 deterministic guard — 決定「必須阻擋什麼」
```

**Brain 不直接執行，Executive 才執行。** Brain 提建議，Executive 做仲裁，Safety 做硬阻擋。這確保系統永遠不會變成「LLM 控狗」。

### 5.3 三層架構

```
┌─────────────────────────────────────────┐
│  Layer C: Expression Layer              │
│  reply_text / tone / wording / style    │
│  互動語氣 vs 警戒語氣 vs 陪伴語氣        │
│  Studio trace narration                 │
│  ← LLM 語言能力在這裡                    │
└──────────────┬──────────────────────────┘
               │ selected_skill + reply_text
┌──────────────▼──────────────────────────┐
│  Layer B: Policy Layer                  │
│  互動上下文 formation                    │
│  意圖判斷 → PawAI Skills selection      │
│  PawAI Memory (per-person)              │
│  policy override (deterministic rules)  │
│  ← 互動決策核心在這裡                    │
│  ※ LLM function calling 僅作為 skill    │
│    selection 的實作機制之一              │
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

### 5.4 降級路徑

```
正常：Brain(Policy+Expression) → Executive(Safety) → Go2
LLM 掛：Policy 繼續，Expression 降級為固定台詞 → Executive → Go2
Groq 掛：Policy 降級為 RuleBrain → Executive → Go2
全掛：Safety Layer 仍能 stop/emergency → Go2
```

### 5.5 PawAI Skills（本期）

| Skill | 說明 | 場景分類 |
|-------|------|---------|
| `self_introduce` | 自主介紹（meta skill，觸發 skill queue） | Demo 開場 |
| `greet_known_person` | 個人化打招呼 | interaction |
| `acknowledge_gesture` | 手勢回應 | interaction |
| `respond_to_call` | 回應召喚 | interaction |
| `issue_reminder` | 物品 / 姿勢提醒 | interaction |
| `chat_response` | 語音自由對話 | interaction |
| `alert_unknown_person` | 陌生人警戒反應 | guardian_behavior |
| `approach_short` | 短距安全靠近（需雷達） | interaction / guardian |
| `patrol` | 定點巡邏（需雷達） | guardian_behavior |
| `stop_now` | 立即停止 | safety |

**手勢模式切換相關 skills**：🔄 TBD by 2026-04-15

### 5.6 Action Sequencing（Skill Queue 機制）

PawAI Brain 支援呼叫**多個 skill 組成的行為序列**，不只是單一動作。這是展示 embodied agent orchestration 的核心機制。

**執行規則**：
- Queue 內每個 skill 仍須通過 Safety Layer 驗證
- Safety event（stop/emergency/fallen）會**立即清空 queue**
- 每個 skill 之間有 narration（TTS 銜接語）
- Queue 有 timeout（例如 2 分鐘），超時自動終止
- Queue 執行期間 `/state/pawai_brain` 顯示 `active_sequence` 讓 Studio 可觀測

### 5.7 `self_introduce` 預設 Sequence（互動主軸版本）

```python
self_introduce = [
    ("hello",         "我是 PawAI，你的居家互動機器狗"),
    ("sit",           "平常我會待在你身邊，等你叫我"),
    ("wiggle_hips",   "你可以用聲音、手勢，或直接跟我互動"),
    ("dance1",        "開心的時候，我也會用動作回應你"),
    ("stand",         "我也會注意周圍發生的事情"),
    ("balance_stand", "如果看到陌生人，我會提醒你提高注意"),
]
```

**設計原則**：6 步中 5 步是互動展示，最後 1 步才帶出守護。語氣像「有角色的機器狗」，不是「功能列表」。

### 5.8 架構定性（答辯護身符）

> `self_introduce` 不是自由規劃 agent，而是 **safety-gated scripted orchestration**。

- sequence **可由 Brain 觸發**（透過語音、手勢、或 function calling）
- 但 sequence **內容仍在白名單 skill 內**（不會突然叫出 BANNED api）
- **每一步都經 Executive + Safety Layer 驗證**
- **任何時候可被 stop 中斷**

這正是 harness-oriented design 的核心論述——**能力受環境約束，才是可靠的 embodied agent**。

### 5.9 PawAI Memory

不是聊天記憶，是結構化互動與守護記憶：

| 記憶項 | 類別 | 說明 |
|--------|------|------|
| `person_profiles` | interaction | 誰是誰（name, face_id, 偏好語氣） |
| `greeting_cooldown` | interaction | 上次打招呼時間，避免重複 |
| `last_interaction_state` | interaction | 上次互動狀態，連續性 |
| `session_context` | interaction | 本次 session 已見到誰 |
| `guardian_incidents` | guardian | 最近的警戒/異常事件 |

重啟清空，不做持久化（對 Demo 夠用）。

### 5.10 Guardian State Artifact

結構化狀態，發布到 `/state/pawai_brain`：

```json
{
  "timestamp": 1744000000.0,
  "executive_state": "interacting",
  "active_user": "alice",
  "active_skill": "greet_known_person",
  "active_sequence": null,
  "interaction_count": 3,
  "guardian_mode": "normal",
  "safety_flags": {
    "emergency": false,
    "obstacle": false,
    "tts_playing": false
  },
  "known_users_seen": ["alice"],
  "fallback_active": false
}
```

### 5.11 Harness-Oriented Design

> PawAI Brain 採用 harness-oriented design：不是讓單一模型直接控制機器狗，而是透過 safety rules、policy、skills、tool abstraction、memory 與 observability，構建一個能穩定產生互動與守護行為的執行環境。

### 5.12 家庭場景的可靠性設計（Reliability, Safety, Privacy）

家庭場景中的機器人不只要聰明，還要**可控、可停、可降級、可信任**。

| 面向 | 設計 | 在哪實作 |
|------|------|---------|
| **Safety** | LLM 不直接控狗，所有動作必須通過 Executive 仲裁 | Brain/Executive 分離 |
| **Controllability** | Executive 仲裁 + BANNED_API gate + stop 可打斷任何 sequence | Layer A Safety Layer |
| **Graceful Degradation** | 四級降級：LLM → RuleBrain → fixed script → Safety-only | Layer B + Layer C fallback 鏈 |
| **Privacy-by-Design** | 感知模組 local-first，不上雲 | 感知層實作 |
| **Security Mindset** | Safety event 立即清空 skill queue，最後防線永遠可用 | Layer A + Skill Queue |

#### Privacy-by-Design：讓 AI 看懂行為，而不是懂個人身份

| 模組 | 執行位置 | 資料離機？ |
|------|:------:|:---------:|
| 人臉辨識（YuNet + SFace） | Jetson 本地 | ❌ 不離機 |
| 人臉資料庫（face_db） | Jetson 本地檔案 | ❌ 不離機 |
| 手勢辨識（MediaPipe） | Jetson 本地 | ❌ 不離機 |
| 姿勢辨識（MediaPipe） | Jetson 本地 | ❌ 不離機 |
| 物體辨識（YOLO26n） | Jetson 本地 | ❌ 不離機 |
| 語音 ASR/LLM | 雲端（主線）/ 本地（fallback） | ⚠️ 語音上雲，**可降級本地** |

**核心哲學**（借鑑輔大遞固科技周博士演講）：
> 「讓 AI 看懂行為，而不是懂個人身份。」

### 5.13 借鑑概念

| 借什麼 | 從哪借 | 用在哪層 |
|--------|--------|---------|
| `beforeToolCall` safety gate | pi-mono | Layer A: pre-action validation |
| ROS2 tool abstraction | rosclaw | Layer B: skill → tool → robot action |
| per-person memory profile | hermes-agent | Layer B: PawAI Memory |
| skill → tool → action 形態 | dimos | Layer B → Executive dispatch |

**不整包導入任何框架。** 只借概念，用自己的 ROS2 架構實作。

---

## 6. 八模組在互動機器狗中的角色

| 模組 | 角色 | 定位 | 現狀 |
|------|------|------|:----:|
| 人臉辨識 | 身份識別層 | 熟人個人化問候 + 陌生人警戒觸發 | ✅ 穩定，缺陌生人邏輯 |
| 語音功能 | **互動主軸 A** | ASR + LLM + TTS，自由對話 + Plan B | ✅ 閉環，缺個性和記憶 |
| 手勢辨識 | **互動主軸 B** | 模式切換 + 指令觸發（下週設計） | ✅ 穩定，需擴充映射 |
| 姿勢辨識 | 狀態感知層 | 久坐提醒、次要警示 | ✅ 穩定，跌倒幻覺風險 |
| 物體辨識 | 情境強化層 | 日常物品提醒、情境式互動 | ✅ 大物件 OK，小物件弱 |
| PawAI Brain | **系統核心** | 三層決策引擎 | 🔄 從規則機升級中 |
| PawAI Studio | 控制台 | 遠端觀測 + 互動入口 | ✅ 閉環通過 |
| 導航避障 | 升級能力 | 巡邏 + 短距靠近，雷達到貨後 | 🔄 確定採購，時程未定 |

---

## 7. Demo 計畫

### P0 Demo 劇本（3 分鐘，5/16 省夜 Demo）

互動 70% / 守護 30%。Demo 地點：**1003 第三廳**（講桌在邊邊，中間有空地適合機器狗活動）。

```
0:00 - 0:10  開場：PawAI 安靜待命
  Go2 坐在場地中央，Studio 大螢幕顯示 guardian_mode = idle

0:10 - 0:45  ★ Wow Moment：Self Introduce（互動主軸版）
  主持人：「PawAI，介紹你自己」
  → PawAI Brain 呼叫 self_introduce meta skill
  → Executive 啟動 skill queue
  → 自主執行 6-step sequence：
     1. Hello + 「我是 PawAI，你的居家互動機器狗」
     2. Sit + 「平常我會待在你身邊，等你叫我」
     3. WiggleHips + 「你可以用聲音、手勢，或直接跟我互動」
     4. Dance1 + 「開心的時候，我也會用動作回應你」
     5. Stand + 「我也會注意周圍發生的事情」
     6. BalanceStand + 「如果看到陌生人，我會提醒你提高注意」
  → Studio 同步顯示 active_sequence + 每個 skill 的執行狀態

0:45 - 2:30  互動主秀（1 分 45 秒）
  🔄 TBD by 2026-04-15：下週黃旭的手勢模式切換設計 + 四人 mapping 回報後細化
  初步方向：
  - 手勢模式切換展示（比 1/2/3 切不同模式）
  - 語音自由對話
  - 物體情境互動
  - 熟人個人化問候
  - 姿勢狀態感知

2:30 - 3:00  守護亮點 + 收尾（30 秒）
  - 陌生人警告場景（未註冊人進場 → 警戒姿態 + 語音提醒 + Studio 推播）
  - 口頭補：「具備巡邏能力（若雷達到貨）、跟隨為未來發展方向」
```

### P0 / P1 場景表

| 優先級 | 場景 | Demo 呈現 |
|:------:|------|-----------|
| P0 | Self Introduce 開場 | 完整演出（Wow Moment）|
| P0 | 互動主秀（細節 TBD） | 完整演出 |
| P0 | 陌生人警告 | 30 秒帶過 |
| P1 | 巡邏 | 雷達到貨 → 實演；否則錄影 |
| P1 | 異常偵測 | 口頭帶過（跌倒幻覺風險）|
| P2 | 跟隨 | **不做實演**，寫進文件 future work |
| P2 | 預設路線多點巡邏 | 視 SLAM 結果 |

### Plan B（GPU 斷線版）

語音改走 Plan B 固定台詞（擴充至 15-20 組），其他場景不變（人臉/手勢/姿勢/物體都是本地模型）。

---

## 8. 降級策略

| 故障 | 影響 | 降級方式 |
|------|------|---------|
| Groq API 斷線 | Expression + Policy 部分失能 | Policy 降級為 RuleBrain，Expression 降級為固定台詞 |
| Cloud ASR/LLM 主線失效 | 雲端語音鏈路中斷 | 降級為本地最小意圖路徑（Energy VAD + Intent fast path + RuleBrain + Piper TTS），最差為 Plan B 固定台詞 |
| D435 斷線 | 人臉 + 深度失能 | 純語音 + 手勢互動 |
| Jetson 供電斷電 | 全系統失能 | Go2 自己站穩（韌體層） |
| RPLIDAR 失敗 | 巡邏不可用 | 回退到無雷達版（主案不受影響） |
| 跌倒偵測誤報 | 假警報 | `enable_fallen=false` 關閉 |

---

## 9. 本期不做

| 項目 | 原因 |
|------|------|
| 通用 autonomous agent | Go2 必要性會變弱 |
| 自我進化 skill learning | 需要 deterministic 行為 |
| 大型 persistent memory system | Demo 不需要跨 session 記憶 |
| LLM 直接控制馬達 | Brain 不直接執行，Executive 才執行 |
| 整包導入外部框架 | dimos/openclaw/hermes 太重，只借概念 |
| 全屋自主導航 | odom 漂移風險，不承諾 |
| 跟隨功能實作 | 會議共識：難度極高，不列必做 |
| AI 訂外賣 / 聲音複製 | 與 Go2 必要性太弱 |

---

## 10. 四人分工原則（4/11 會議定案）

### 團隊成員與正式姓名

| 姓名 | 角色 | 本期負責 |
|------|------|---------|
| **盧柏宇**（Roy） | 系統架構 / 整合 | PawAI Brain 三層落地、陌生人警戒、導航整合、全系統整合 |
| **黃旭** | 感知 / 互動設計 | **手勢辨識**（從物體換過來）+ 手勢模式切換設計 |
| **鄔雨彤** | 感知 / 互動設計 | **物體辨識**（從手勢換過來）+ 居家常見物測試 |
| **楊沛蓁** | 感知 / 互動設計 | 姿勢辨識擴充 + 久坐提醒邏輯 |
| **陳如恩** | 語音 / LLM | 語音模組：prompt + 記憶 + 雲端 API fallback |

### 分工變動（vs 4/9 原版）

- **黃旭 ↔ 鄔雨彤 交換**：黃旭做手勢、鄔雨彤做物體
- **楊沛蓁**：從「同時做姿勢 + 前端」收斂為「專注姿勢擴充」
- **陳如恩**：加入「雲端 API fallback 測試」（Groq / Gemini）和「記憶功能」

### 文件命名統一

**所有文件只用正式姓名**。會議紀錄裡的口語/誤記名字（博宇 / 雨彤 / 佩珍 / 盧恩 / 成文）**不再使用**，統一改為：
- 博宇 → **盧柏宇**
- 雨彤 → **鄔雨彤**
- 佩珍 → **楊沛蓁**
- 盧恩 / 成文 → **陳如恩**（誤記，視為同一人）

---

## 11. 時程

### 關鍵日期（2026-04-11 更新）

| 日期 | 里程碑 |
|------|------|
| **4/13（週日晚間）** | 專題文件初版交老師（目標 70+ 頁，目前 ~50 頁）|
| **4/14（週一）** | 雷達規格確認（盧柏宇 × 林傑）+ 週一正式繳交 |
| **4/15** | 四人互動設計回報 → Spec 補齊 §4 互動場景細節 |
| **4/20 左右** | 老師完成國科會計畫變更流程（採購雷達） |
| **雷達到貨後** | Day 1 odom 驗證 → 是否 SLAM 可行 |
| **5/11 前** | 教室實地預演（Demo 場地 1003）|
| **5/16** | **省夜 Demo** |
| **5/18** | **正式展示** |
| **6 月** | 口頭報告答辯 |

### 4/13 文件分工

| 章節 | 負責人 |
|------|------|
| 第一章（背景、動機、目的、系統範圍）| 盧柏宇 |
| 硬體介紹（Go2 / Jetson / RealSense / 喇叭 / XL4015）| 盧柏宇 |
| 手勢模組章節 | 黃旭 |
| 物體模組章節 | 鄔雨彤 |
| 姿勢模組章節 | 楊沛蓁 |
| 語音模組章節 | 陳如恩 |
| PawAI Brain 架構章節 | 盧柏宇 |

**注意事項**：
- 新增內容用註解標記，盧柏宇最後統一排版樣式
- 共編一次一人避免版面亂跑
- UI 畫面需補上（對應 User Story 格式）
- 目標 70+ 頁

---

## 12. Implementation Notes

### 改動概覽

預估為小幅增量修改，集中於 5 個核心檔案，全部向後相容。

| 檔案 | 改動內容 |
|------|---------|
| `llm_contract.py` | PawAI Skills contract 欄位 + tool schema 定義 |
| `state_machine.py` | SkillContract dataclass + `pawai_brain_state` 擴展 |
| `interaction_executive_node.py` | pre-action validation + `/state/pawai_brain` publisher |
| `llm_bridge_node.py` | policy_override + PawAI Memory + function calling 分支 |
| `event_action_bridge.py` | safety_alert publisher（最低優先）|

### 建議執行順序

1. `llm_contract.py`（純資料，無 ROS2 依賴）
2. `state_machine.py`（純 Python，有既有測試覆蓋）
3. `interaction_executive_node.py`（pre-action validation 是最高價值改動）
4. `llm_bridge_node.py`（policy_override + function calling）
5. `event_action_bridge.py`（最低優先）

> 具體行數和 patch 範圍在 implementation plan 中定義，不在本 spec 鎖死。

### 關鍵改動

- **Skill Queue**：`state_machine.py` 加 `skill_queue: deque[SkillContract]` + `self_introduce` meta skill
- **Pre-action Validation**：`interaction_executive_node.py` 在 `_execute_result()` 前插入 `_validate_preconditions()`
- **Policy Override**：`llm_bridge_node.py` 在 `_dispatch()` 前加 `_policy_override()`
- **PawAI Memory**：`llm_bridge_node.py` 擴充 `_face_greet_history` 為 `_pawai_memory`
- **Guardian State Topic**：新增 `/state/pawai_brain`（TRANSIENT_LOCAL QoS）

---

## 13. 代表作論述角度

這個專案不只是「串了很多 AI API」，而是一個完整的系統作品：

| 面向 | 論述 |
|------|------|
| System Architecture | 三層架構（Driver → Perception → Executive），事件驅動，單一控制權 |
| Agent Design | PawAI Brain 三層（Safety → Policy → Expression），harness-oriented |
| HRI | 多模態感知 × 互動+守護場景 = 情境式互動設計 |
| Edge/Cloud Tradeoff | 每個模組都有本地 + 雲端 fallback，四級降級策略 |
| Robotics Productization | 從感知到動作的完整 pipeline，skill contract，pre-action validation |
| Reliability | Plan B 固定台詞、enable_fallen 開關、供電風險管理、pawai_brain_state 可觀測 |
| **Privacy-by-Design** | 感知模組全本地執行、face_db 不離機、讓 AI 看懂行為不懂身份 |
| **Security Mindset** | Safety Layer 永遠可用、BANNED_API 硬擋、最後防線不經 LLM |
| Observability | PawAI Studio 即時影像 + 狀態面板 + guardian mode + event timeline |

答辯可講：**embodied interaction system、PawAI Brain、harness-oriented design、skill contract、graceful degradation、privacy-by-design、產品故事與風險控管**。

### 未來研究方向

基於現有專案基礎，以下三條延伸線與產業趨勢對齊：

| 方向 | 現有基礎 | 延伸目標 |
|------|---------|---------|
| **1. Embodied Interaction Brain / Harness Design** | 三層架構 + skill contract + pre-action validation | 擴展為通用 embodied agent 執行框架 |
| **2. Visual Navigation / Short-range Approach** | D435 深度 + RPLIDAR | 四足 odom 漂移補償 + 短距反應式避障 + 人體追蹤靠近 |
| **3. Robot Safety / Controlled Autonomy** | Safety Layer + BANNED_API | 對抗 prompt injection、可驗證的 controlled autonomy 機制 |

---

## 14. 與現有文件的關係

- **本文件**：current 系統設計規格
- **`2026-04-10-guardian-dog-design.md`**：superseded，保留作為設計演化歷程
- **`docs/mission/README.md`**：專案管理入口（時程、分工、交付）
- **`pawai-studio/docs/0410assignments/`**：四人分工執行細節
- **`references/project-status.md`**：每日狀態更新

---

## 附錄 A：方向收斂歷程

### 4/9 → 4/10 → 4/11 三階段演化

| 階段 | 主軸 | 為何調整 |
|------|------|---------|
| 4/9 前 | 多功能 AI 機器狗 | Perry 老師指出缺主軸 |
| 4/10 | **居家守護犬** | 為了回答「為什麼非 Go2 不可」，收斂成守護敘事 |
| **4/11** | **居家互動機器狗（兼具守護能力）** | **4/11 小組會議定案**：互動 70 / 守護 30，保留 Go2 必要性但不被守護單一敘事綁死 |

### 考慮過但未採用的方向

| # | 方向 | 為何不選 |
|:-:|------|---------|
| 1 | 看門犬（純守護） | 範圍太大、容易被質疑 |
| 2 | 長照機器狗 | 弱勢族群評審嚴格、跌倒偵測幻覺 |
| 3 | 打熊狗 / 護院犬 | 需要導航 + 主動追蹤，風險太高 |
| 4 | R2-D2 式情緒互動狗 | 互動深度不足、缺主故事（元素吸收進互動主軸）|
| 5 | AI 助理狗（訂外賣）| Go2 必要性最弱 |

### 4/11 收斂原則

最終採用**互動為主（70%）+ 守護為輔（30%）**：
- 互動能回答「它能做什麼」
- 守護能回答「為什麼要用 Go2 不用攝影機」
- 兩者缺一不可

**關鍵決策句**：
> 如果我們只想做辨識和通知，用攝影機就夠了。如果我們只想做語音互動，用音箱就夠了。但我們要做的是一個會看、會聽、會動、會回應你身體語言的互動實體——這需要實體機器狗。
