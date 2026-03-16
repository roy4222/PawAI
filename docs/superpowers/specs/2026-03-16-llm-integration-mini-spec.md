# LLM Integration Mini Spec — 三路並行實作契約

**版本**：v2.0
**日期**：2026-03-16
**目的**：凍結三路並行開發的接縫，確保 GPU Server / 本機 / Jetson 三路產出能無痛整合
**有效期**：今天（2026-03-16）的衝刺開發
**前置文件**：[interaction_contract.md](../../architecture/interaction_contract.md) v2.0、[brain-adapter.md](../../Pawai-studio/brain-adapter.md) v1.0

---

## 0. 今日目標與優先序

| 優先 | 目標 | 驗收 | 依賴 |
|:----:|------|------|------|
| **1** | 語音 → Cloud LLM → TTS → Go2 說話 | 對狗說「你好」→ LLM 生成回覆 → Go2 播放 | vLLM on RTX 8000 |
| **2** | 人臉 identity_stable → LLM → 念名字 | Roy 走近 → Go2 說「Roy 你好」 | Goal 1 + face event |
| **3** | 人臉 → 念名字 + 揮手 | Roy 走近 → Go2 說「Roy 你好」→ 揮手 | Goal 2 |
| **4** | PawAI Studio 現況確認 | Mock Server 可跑、隊友能 demo | 無 |

**開發節奏**：
- 先用假事件 (`ros2 topic pub`) 驗證 LLM 鏈路，不要一開始就被硬體卡住
- 鏈路通了再上 Jetson 跑真麥克風 + 真 Go2

**今天 P0 的 intent 範圍**：只有 `greet | stop | status`
**今天 P0 的 skill 範圍**：只有 `hello | stop_move | null`

`come_here`、`take_photo`、`sit`、`stand`、`content` — 留接口但今天不做驗收。

---

## 1. Cloud LLM API Contract

### 1.1 Endpoint

```
POST http://140.136.155.5:8000/v1/chat/completions
```

**標準 OpenAI-compatible API**（vLLM 原生提供），不需要自己寫 FastAPI wrapper。

### 1.2 Model

目標模型：`Qwen/Qwen3.5-9B`（HuggingFace: https://huggingface.co/Qwen/Qwen3.5-9B）

**Fallback 策略**：若 `Qwen/Qwen3.5-9B` 在 HuggingFace 拉不到（repo 名稱不對、未公開等），
按此順序嘗試：
1. `Qwen/Qwen3.5-9B-Instruct`
2. `Qwen/Qwen2.5-14B-Instruct`
3. `Qwen/Qwen2.5-7B-Instruct`

不要在模型名卡死，拉得到就用、先跑通鏈路。

**Roadmap**：9B → 27B（https://huggingface.co/Qwen/Qwen3.5-27B）

### 1.3 Request 格式

```json
{
  "model": "<實際成功載入的模型名>",
  "messages": [
    {"role": "system", "content": "<system prompt — 見 §1.5>"},
    {"role": "user", "content": "<構造的 prompt — 見 §1.6>"}
  ],
  "temperature": 0.2,
  "max_tokens": 180,
  "response_format": {"type": "json_object"}
}
```

**注意**：`temperature: 0.2` — 今天目標是穩定 JSON 輸出，不是自然聊天。

### 1.4 Response 要求（LLM 必須回傳的 JSON）

```json
{
  "intent": "greet",
  "reply_text": "Roy 你好！好久不見。",
  "selected_skill": "hello",
  "reasoning": "偵測到熟人 Roy，距離 1.4m，適合打招呼",
  "confidence": 0.92
}
```

| 欄位 | 型別 | 值域（今天 P0） | 說明 |
|------|------|:---------------:|------|
| `intent` | string | `"greet"` `"stop"` `"status"` `"chat"` `"ignored"` | 判定的意圖 |
| `reply_text` | string | 中文，≤50 字 | 給 TTS 的回覆（空字串 = 不說話） |
| `selected_skill` | string 或 JSON null | `"hello"` `"stop_move"` 或 `null`（不是字串 `"null"`） | Go2 動作（§3） |
| `reasoning` | string | ≤20 字 | 一句話決策摘要（不要輸出思考過程） |
| `confidence` | float | 0.0-1.0 | 決策信心度 |

### 1.5 System Prompt

```
你是 PawAI，一隻友善的機器狗助手，搭載在 Unitree Go2 Pro 上。你能看見人（透過攝影機人臉辨識）、聽懂中文（透過語音辨識）、做出動作。

你可能被兩種事件觸發：
1. 語音事件：使用者對你說話
2. 人臉事件：攝影機辨識到認識的人（此時沒有語音輸入）

你只能輸出單一 JSON object，不要輸出任何其他文字。
JSON 必須包含以下五個欄位：

intent — 只能是以下字串之一：greet, stop, status, chat, ignored
reply_text — 你要說的中文回覆（簡短自然，15-40字。人臉事件時要叫出對方名字）
selected_skill — 只能是 "hello"、"stop_move"、或 JSON null（不是字串 "null"）
reasoning — 一句話決策摘要，不超過 20 字，不要輸出思考過程
confidence — 0.0 到 1.0

規則：
- 看到認識的人（人臉事件）：intent="greet"，reply_text 要包含對方名字，selected_skill 可以是 "hello" 或 null
- 聽到打招呼：intent="greet"，reply_text 友善回應
- 聽到「停」或「stop」：intent="stop"，selected_skill 必須是 "stop_move"，reply_text 可以是空字串
- 聽到問狀態：intent="status"，selected_skill=null
- 不確定時：intent="chat"，selected_skill=null
- reply_text 不超過 50 字
- 除了 JSON 不要輸出任何文字
```

### 1.6 User Message 構造

**語音觸發（speech trigger）**：
```
[觸發來源] 語音
[語音輸入] 使用者說：「{asr_text}」
[語音意圖] 本地分類：{local_intent}（信心度 {confidence}）
[人臉狀態] {face_context}
[時間] {timestamp}
```

**人臉觸發（face trigger）**：
```
[觸發來源] 人臉辨識
[人臉事件] 辨識到 {stable_name}（相似度 {sim}，距離 {distance_m}m）
[時間] {timestamp}
```

範例（語音觸發）：
```
[觸發來源] 語音
[語音輸入] 使用者說：「你好啊」
[語音意圖] 本地分類：greet（信心度 0.95）
[人臉狀態] 看到 1 人：Roy（穩定，距離 1.4m）
[時間] 2026-03-16 14:30:05
```

範例（人臉觸發）：
```
[觸發來源] 人臉辨識
[人臉事件] 辨識到 Roy（相似度 0.42，距離 1.4m）
[時間] 2026-03-16 14:30:05
```

### 1.7 Timeout 與 Fallback

| 階段 | 超時 | 行為 |
|------|------|------|
| HTTP 連線 | 2 秒 | fallback 到 RuleBrain |
| 首 token | 5 秒 | fallback 到 RuleBrain |
| 總回應 | 8 秒 | 截斷，用已收到的部分 |
| JSON 解析失敗 | — | fallback 到 RuleBrain |

**RuleBrain fallback**：就是現有 `intent_tts_bridge_node` 的模板回覆邏輯。

---

## 2. llm_bridge_node Contract

### 2.1 定位

取代 `intent_tts_bridge_node`。訂閱語音事件 + 人臉事件 + 人臉狀態，呼叫 LLM，發布 TTS + Go2 動作。

### 2.2 訂閱的 Topic

| Topic | 型別 | 用途 |
|-------|------|------|
| `/event/speech_intent_recognized` | Trigger | 語音意圖事件 → 觸發 LLM 呼叫 |
| `/event/face_identity` | Trigger | 人臉身份事件 → `identity_stable` 時觸發 LLM 呼叫 |
| `/state/perception/face` | Context | 人臉狀態 → 作為語音觸發時的附加 context |

### 2.3 發布的 Topic

| Topic | 用途 | Message Type |
|-------|------|-------------|
| `/tts` | TTS 回覆文字 | `std_msgs/String` |
| `/webrtc_req` | Go2 動作指令 | `go2_interfaces/WebRtcReq` |
| `/state/interaction/llm_bridge` | Bridge 狀態 | `std_msgs/String` (JSON) |

### 2.4 Trigger Semantics（兩種觸發路徑）

**Path A：語音觸發**
```
/event/speech_intent_recognized 到達
  ├─ 檢查 session_id 去重
  ├─ 過濾 hallucination intent
  ├─ 讀取最新 /state/perception/face 快取（附加 context）
  ├─ 組裝 user message（語音格式，§1.6）
  ├─ 呼叫 Cloud LLM
  │   ├─ 成功 → 解析 JSON → 發 /tts + /webrtc_req
  │   └─ 失敗 → RuleBrain fallback
  └─ 更新 /state/interaction/llm_bridge
```

**Path B：人臉觸發**
```
/event/face_identity 到達
  ├─ 只處理 event_type == "identity_stable"，其餘忽略
  ├─ 只處理 stable_name != "unknown"（具名人臉）
  ├─ 去重：同 (track_id, stable_name) 60 秒內不重複
  ├─ 組裝 user message（人臉格式，§1.6）
  ├─ 呼叫 Cloud LLM
  │   ├─ 成功 → 解析 JSON → 發 /tts + /webrtc_req
  │   └─ 失敗 → RuleBrain fallback（"你好！"）
  └─ 更新 /state/interaction/llm_bridge
```

### 2.5 ROS2 Parameters

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `llm_endpoint` | `http://140.136.155.5:8000/v1/chat/completions` | LLM API URL |
| `llm_model` | `Qwen/Qwen3.5-9B` | Model 名稱（會被實際載入的模型覆蓋） |
| `llm_timeout` | `5.0` | HTTP 超時秒數 |
| `llm_temperature` | `0.2` | LLM temperature |
| `intent_event_topic` | `/event/speech_intent_recognized` | 語音事件 topic |
| `face_event_topic` | `/event/face_identity` | 人臉事件 topic |
| `face_state_topic` | `/state/perception/face` | 人臉狀態 topic |
| `tts_topic` | `/tts` | TTS 輸出 topic |
| `enable_actions` | `true` | 是否發 Go2 動作 |
| `enable_fallback` | `true` | LLM 失敗時是否用模板回覆 |
| `face_greet_cooldown_s` | `60.0` | 同人臉 greet 冷卻秒數 |
| `action_delay_s` | `0.5` | TTS 發出後延遲多久再發動作 |

### 2.6 關鍵設計決策

1. **兩種 trigger source**：語音事件和人臉事件都能獨立觸發 LLM
2. **直接發 `/webrtc_req`**，不經過中間 dispatcher — 今天求快，未來有 Interaction Executive 再拆
3. **session_id 去重**（語音）/ **(track_id, name) + cooldown 去重**（人臉）
4. **先 TTS 再動作** — `/tts` 先發，延遲 `action_delay_s` 後才發 `/webrtc_req`（避免動作打斷語音）。**例外：`stop_move` 立即發 `/webrtc_req`，不等 TTS**（安全優先，`reply_text` 可為空字串）
5. **人臉 trigger 只處理具名 identity_stable** — unknown 不觸發、track_started/track_lost 不觸發

---

## 3. Action Mapping（Skill → Go2 指令）

### 3.1 今日 P0 凍結映射

| LLM `selected_skill` | Go2 `api_id` | `ROBOT_CMD` | 說明 |
|----------------------|-------------|-------------|------|
| `hello` | 1016 | `Hello` | 揮手 |
| `stop_move` | 1003 | `StopMove` | 停止 |
| `null` | — | — | 不做動作 |

**只有這三個值合法。** LLM 回傳其他值 → 忽略動作、只做 TTS。

### 3.2 預留映射（今天不驗收，程式碼可先寫）

| `selected_skill` | `api_id` | 說明 |
|-----------------|----------|------|
| `sit` | 1009 | 坐下 |
| `stand` | 1002 | 站立 |
| `content` | 1020 | 開心 |

### 3.3 WebRtcReq 構造

```python
from go2_interfaces.msg import WebRtcReq

SKILL_TO_CMD = {
    "hello":     {"api_id": 1016, "parameter": "1016"},
    "stop_move": {"api_id": 1003, "parameter": "1003"},
    "sit":       {"api_id": 1009, "parameter": "1009"},
    "stand":     {"api_id": 1002, "parameter": "1002"},
    "content":   {"api_id": 1020, "parameter": "1020"},
}

def make_webrtc_req(skill: str) -> WebRtcReq | None:
    cmd = SKILL_TO_CMD.get(skill)
    if cmd is None:
        return None
    msg = WebRtcReq()
    msg.id = 0
    msg.topic = "rt/api/sport/request"
    msg.api_id = cmd["api_id"]
    msg.parameter = cmd["parameter"]
    msg.priority = 1 if skill == "stop_move" else 0
    return msg
```

### 3.4 安全規則

- `stop_move` 永遠 priority=1
- 禁止的 api_id：1030 (FrontFlip), 1031 (FrontJump), 1301 (Handstand)
- LLM 回傳不在 SKILL_TO_CMD 內的 skill → 忽略動作、只做 TTS

---

## 4. Face Event Semantics

### 4.1 Topic Schema（照 interaction_contract.md v2.0）

**`/state/perception/face`** — `std_msgs/String` (JSON), 10Hz

```json
{
  "stamp": 1773926400.123,
  "face_count": 1,
  "tracks": [
    {
      "track_id": 1,
      "stable_name": "Roy",
      "sim": 0.42,
      "distance_m": 1.25,
      "bbox": [100, 150, 200, 280],
      "mode": "stable"
    }
  ]
}
```

**`/event/face_identity`** — `std_msgs/String` (JSON), 觸發式

```json
{
  "stamp": 1773926400.123,
  "event_type": "identity_stable",
  "track_id": 1,
  "stable_name": "Roy",
  "sim": 0.42,
  "distance_m": 1.25
}
```

### 4.2 事件語義與 llm_bridge_node 行為

| event_type | 觸發條件 | llm_bridge_node 行為 |
|-----------|----------|---------------------|
| `track_started` | 新 track 出現 | **不觸發 LLM**。更新內部 face context |
| `identity_stable` | Hysteresis 穩定化通過 | **觸發 LLM**（§2.4 Path B）→ 念名字 + 可選動作 |
| `identity_changed` | 同 track 身份變更 | 更新內部 face context（不觸發 LLM） |
| `track_lost` | track 消失 | 清除該 track 的 context（不觸發 LLM） |

### 4.3 Face Trigger 去重

```python
# dict: (track_id, stable_name) -> last_trigger_timestamp
_face_greet_history: dict[tuple[int, str], float] = {}

def should_trigger_face_greet(track_id: int, name: str, cooldown: float = 60.0) -> bool:
    if name == "unknown":
        return False
    key = (track_id, name)
    now = time.time()
    last = _face_greet_history.get(key, 0.0)
    if now - last < cooldown:
        return False
    _face_greet_history[key] = now
    return True
```

---

## 5. 三路任務分派

### 🔴 路線 A：RTX 8000 Server（Claude Code #2）

見附錄 A — copy-paste ready 任務指令。

### 🟢 路線 B：人臉 Event 發布（Claude Code #3）

見附錄 B — copy-paste ready 任務指令。

### 🔵 路線 C：本機（Claude Code #1 = 我）

1. 新建 `speech_processor/speech_processor/llm_bridge_node.py`
2. 實作 §2 的兩種 trigger path
3. 呼叫 Cloud LLM（§1）
4. 發布 TTS + Go2 action（§3）
5. 內建 RuleBrain fallback
6. 更新 `setup.py` entry_points
7. 更新 `clean_speech_env.sh` + 啟動腳本

---

## 6. 整合驗證（分段驗收）

### Phase 1：假事件驗證（本機，不需硬體）

```bash
# 啟動 llm_bridge_node
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_endpoint:="http://140.136.155.5:8000/v1/chat/completions"

# 測試 1: 語音 → LLM → TTS
# 注意：payload 格式對齊 stt_intent_node 真實輸出（見 stt_intent_node.py:1066-1078）
ros2 topic pub --once /event/speech_intent_recognized std_msgs/msg/String \
  "{data: '{\"event\":\"speech_intent_recognized\",\"session_id\":\"test-001\",\"intent\":\"greet\",\"confidence\":0.95,\"matched_keywords\":[\"你好\"],\"text\":\"你好\",\"source\":\"audio\",\"provider\":\"whisper_local\",\"latency_ms\":600.0,\"degraded\":false,\"timestamp\":\"2026-03-16T14:30:05\"}'}"
# 驗收：ros2 topic echo /tts 收到 LLM 生成的中文回覆

# 測試 2: 人臉 → LLM → TTS + 動作
ros2 topic pub --once /event/face_identity std_msgs/msg/String \
  "{data: '{\"stamp\":1773926400.0,\"event_type\":\"identity_stable\",\"track_id\":1,\"stable_name\":\"Roy\",\"sim\":0.42,\"distance_m\":1.4}'}"
# 驗收：ros2 topic echo /tts 收到包含「Roy」的回覆
# 驗收：ros2 topic echo /webrtc_req 收到 api_id=1016 (hello)

# 測試 3: stop 立即生效
ros2 topic pub --once /event/speech_intent_recognized std_msgs/msg/String \
  "{data: '{\"event\":\"speech_intent_recognized\",\"session_id\":\"test-002\",\"intent\":\"stop\",\"confidence\":0.98,\"matched_keywords\":[\"停\"],\"text\":\"停\",\"source\":\"audio\",\"provider\":\"whisper_local\",\"latency_ms\":500.0,\"degraded\":false,\"timestamp\":\"2026-03-16T14:30:10\"}'}"
# 驗收：ros2 topic echo /webrtc_req 立即收到 api_id=1003 (stop_move)，不等 TTS

# 測試 4: Fallback（斷網）
# 停掉 RTX 8000 vLLM → 重發測試 1 → /tts 應收到模板回覆「哈囉，我在這裡。」
```

**stt_intent_node 真實 `/event/speech_intent_recognized` JSON 欄位**（供參照）：
```json
{
  "event": "speech_intent_recognized",
  "session_id": "ev-20260316-143005-a1b2",
  "intent": "greet",
  "confidence": 0.95,
  "matched_keywords": ["你好"],
  "text": "你好",
  "source": "audio",
  "provider": "whisper_local",
  "latency_ms": 600.0,
  "degraded": false,
  "timestamp": "2026-03-16T14:30:05"
}
```

### Phase 2：Jetson 端到端（需硬體）

```bash
# stt_intent_node → llm_bridge_node → tts_node → Go2
# 對麥克風說「你好」→ LLM 生成回覆 → Go2 說話

# face_identity_infer_cv.py 看到人 → identity_stable → llm_bridge_node → Go2 說「Roy 你好」→ 揮手
```

---

## 7. 架構願景：Skills-Driven Platform

> 參考：Asimov DIY 人形機器人 + OpenClaw Skills 架構

**核心類比**：
```
OpenClaw 控制瀏覽器           PawAI 控制 Go2
─────────────────────────────────────────────
Skills = 模擬點擊              Skills = Go2 動作指令
Memory = MEMORY.md             Memory = 人物/場景/偏好記憶
Agent = LLM 決策               Agent = Brain Adapter
Multi-Agent = 分工              Multi-Agent = 感知/規劃/對話分離
```

**今天建立的是第一版 Skills 層**：`SKILL_TO_CMD` 映射 = LLM 說「hello」→ Go2 揮手。
未來擴充就是加 Skill（跟隨、巡邏、拍照），不改架構。

**四層擴充路線**：
1. **Skills 直接驅動**（今天）：LLM → Skill ID → Go2 指令
2. **視覺感知 + 決策**（Phase 2）：D435 影像 → LLM context → 情境動作
3. **Multi-Agent 分工**（Phase 3）：感知 Agent + 規劃 Agent + 對話 Agent
4. **Memory + 持續學習**（Phase 3）：記住人、場景、偏好，跨 session 累積

**設計原則**：
- 每個 Skill 是獨立、可測試、可組合的單元
- LLM 不直接控制低階硬體，只選 Skill
- Safety Guard 永遠有最終否決權
- 平台可持續擴充：加 Skill = 加能力，不改核心

---

*最後更新：2026-03-16*
*維護者：System Architect*
*版本：v2.0（修正 face trigger、P0 scope、temperature、model fallback）*
