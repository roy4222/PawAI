# 陳如恩 — 語音功能互動設計（互動機器狗的「聲音表達」）

> **目標**：設計互動機器狗的「聲音個性」—— 它怎麼打招呼、怎麼警告、怎麼陪伴聊天。
> PawAI 不是聊天機器人，語音是守護行為的一部分。

---

## 跟 盧柏宇 的分工邊界

你和 盧柏宇 都會碰到 `llm_bridge_node.py` 這個檔案，但負責的部分不同：

| | 陳如恩負責 | 盧柏宇 負責 |
|---|---|---|
| **SYSTEM_PROMPT** | 互動機器狗個性、語氣、措辭風格（「怎麼說話」） | prompt 裡的 skill schema / tool definition / JSON 格式（「怎麼選動作」） |
| **Plan B 台詞** | 寫 20 組場景化問答的**內容** | 把內容整合進 RuleBrain fallback **程式碼** |
| **Groq 測試** | 測延遲、品質、免費額度是否夠 Demo | 切 API endpoint + function calling 實作 |
| **max_tokens** | 建議放寬到多少（測試不同長度的品質） | 改程式碼裡的參數 |
| **reply_text** | 決定「說什麼」的品質與風格 | 決定「什麼時候說、說完做什麼」（Guardian Policy） |

**簡單記法**：你決定互動機器狗「怎麼說話」，盧柏宇 決定互動機器狗「什麼時候說、說完做什麼」。

**注意**：盧柏宇 會在 SYSTEM_PROMPT 裡加一段 tool/skill definition（JSON schema），**不要動那段**。你只改「個性描述 + 語氣指引」的部分。如果不確定哪段是你的，問 盧柏宇。

---

## 你的任務

1. SSH 連上 RTX 8000 server，設計**互動機器狗個性 prompt**（不只是放寬長度，要有角色設定）
2. 設計**場景化 Plan B 固定台詞**（GPU 斷線時備案，至少 20 組，分場景）
3. 測試 edge-tts 語音合成效果（找最適合互動機器狗的語音）
4. **Groq API 測試**（盧柏宇 可能會把 LLM 從 vLLM 切到 Groq 免費 API，需要你測品質）

---

## 整體語音架構

```
使用者說話（筆電麥克風 via Studio）
    │
    ▼
┌─────────────────────────────────┐
│  ASR 語音辨識                     │
│  SenseVoice Cloud (FunASR)       │
│  模型: iic/SenseVoiceSmall       │
│  位置: RTX 8000 server :8001     │
│  延遲: ~430ms                    │
└──────────┬──────────────────────┘
           │ 文字
           ▼
┌─────────────────────────────────┐
│  Intent 分類                      │
│  高信心（greet/stop/sit/stand）    │
│  → fast path 跳過 LLM            │
│  低信心 → 送 LLM                  │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│  LLM 大語言模型                    │
│  Qwen2.5-7B-Instruct (vLLM)     │
│  位置: RTX 8000 server :8000     │
│  API: OpenAI 相容格式             │
│  延遲: ~1.5s (Prefix Cache)     │
└──────────┬──────────────────────┘
           │ JSON {intent, reply_text, selected_skill}
           ▼
┌─────────────────────────────────┐
│  TTS 語音合成                      │
│  edge-tts (微軟雲端)              │
│  延遲: P50 ~0.72s               │
│  安裝: pip install edge-tts      │
└──────────┬──────────────────────┘
           │ WAV 音訊
           ▼
    USB 外接喇叭播放
    + Studio Chat AI bubble 顯示
```

**E2E 總延遲**：~2 秒（ASR 0.4s + LLM 1.5s + TTS 0.7s）

---

## 模型資訊

| 模組 | 模型 | 位置 | 連線方式 |
|------|------|------|---------|
| ASR | **SenseVoice Small** (FunASR) | RTX 8000 `140.136.155.5:8001` | SSH tunnel + HTTP POST |
| LLM | **Qwen2.5-7B-Instruct** (vLLM) | RTX 8000 `140.136.155.5:8000` | SSH tunnel + OpenAI API |
| TTS | **edge-tts** (微軟) | 雲端，不需 server | `pip install edge-tts` 本機直接用 |

---

## 本機復現步驟

### 1. SSH Tunnel 連上 GPU Server

```bash
# 開兩個 tunnel（ASR + LLM）
ssh -f -N -L 8001:localhost:8001 -L 8000:localhost:8000 你的帳號@140.136.155.5
```

Tunnel 開好後，你本機的 `localhost:8000` 就是 LLM，`localhost:8001` 就是 ASR。

### 2. 測試 LLM（OpenAI 相容 API）

```bash
# 安裝
pip install openai

# 測試（確認 tunnel 有通）
curl http://localhost:8000/v1/models
```

```python
"""測試 LLM 回覆"""
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy",  # vLLM 不需要真的 key
)

# 目前的 system prompt（見下方「目前的 prompt」段落）
SYSTEM_PROMPT = """你是 PawAI，一隻友善的機器狗助手..."""  # 完整版見程式碼

response = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "你好，你叫什麼名字？"},
    ],
    max_tokens=80,
    temperature=0.2,
)
print(response.choices[0].message.content)
```

### 3. 測試 ASR

```python
"""測試 SenseVoice ASR"""
import requests

# 錄音或用現有 wav 檔
with open("test.wav", "rb") as f:
    resp = requests.post(
        "http://localhost:8001/asr",
        files={"audio": ("test.wav", f, "audio/wav")},
    )
print(resp.json())  # {"text": "你好", "language": "zh", ...}
```

### 4. 測試 TTS（本機，不需 tunnel）

```bash
pip install edge-tts

# 命令列測試
edge-tts --voice zh-CN-XiaoxiaoNeural --text "你好，我是PawAI！" --write-media test_tts.mp3

# 播放
# Windows: start test_tts.mp3
# Mac: afplay test_tts.mp3
# Linux: mpv test_tts.mp3
```

```python
"""Python 版 TTS 測試"""
import asyncio
import edge_tts

async def test_tts():
    communicate = edge_tts.Communicate("你好，我是 PawAI，很高興認識你！", "zh-CN-XiaoxiaoNeural")
    await communicate.save("output.mp3")
    print("已存為 output.mp3")

asyncio.run(test_tts())
```

可用的中文語音（選你覺得最適合機器狗的）：
- `zh-CN-XiaoxiaoNeural`（女聲，活潑）
- `zh-CN-YunxiNeural`（男聲，年輕）
- `zh-CN-XiaoyiNeural`（女聲，溫柔）
- `zh-TW-HsiaoChenNeural`（台灣女聲）
- `zh-TW-YunJheNeural`（台灣男聲）

---

## 參考程式碼（Jetson 上的實際程式）

| 檔案 | 說明 | 你最該看的 |
|------|------|:--------:|
| `speech_processor/speech_processor/llm_bridge_node.py` | LLM 整合節點（624 行） | **看 SYSTEM_PROMPT（行 68-94）** |
| `speech_processor/speech_processor/llm_contract.py` | P0 技能 + BANNED 動作 | **看 SKILL_TO_CMD** |
| `speech_processor/speech_processor/stt_intent_node.py` | ASR + Intent 分類（1078 行） | 參考 |
| `speech_processor/speech_processor/tts_node.py` | TTS 合成+播放（787 行） | 參考 |
| `scripts/sensevoice_server.py` | ASR server（RTX 8000 上跑的） | 參考 |

### 目前的 System Prompt（行 68-94）

```
你是 PawAI，一隻友善的機器狗助手，搭載在 Unitree Go2 Pro 上。
你能看見人（透過攝影機人臉辨識）、聽懂中文（透過語音辨識）、做出動作。

你只能輸出單一 JSON object：
{intent, reply_text, selected_skill, reasoning, confidence}

規則：
- reply_text 不超過 12 字  ← ⚠️ 這就是為什麼回答太短
- greet/chat/status 的 reply_text 必須非空
```

### 你可以改的東西（只改個性和語氣，不碰 JSON schema）

1. **放寬 reply_text 長度限制**：12 字 → 50 字或更多
2. **加入互動機器狗個性**（這是你最重要的任務）：
   - PawAI 是一隻居家互動機器狗，不是聊天機器人
   - 它忠誠、會撒嬌、遇到陌生人會警戒
   - 熟人回家語氣要溫暖開心：「你回來了！今天過得好嗎？」
   - 陌生人警戒語氣要嚴肅：「偵測到不認識的人，已通知家人。」
   - 日常陪伴語氣輕鬆：「你坐很久了，要不要動一動？」
3. **加入自我介紹能力**：「我叫 PawAI，是你的居家互動機器狗！」
4. **max_tokens**：目前 80，建議測試 150-200 的品質（但注意延遲會增加）

**不要碰的**：prompt 裡的 JSON output schema（`{intent, reply_text, selected_skill, ...}`），那段 盧柏宇 會改成 function calling 格式。

---

## Plan B 固定台詞設計（GPU 斷線時的備案）

Plan B 跑在本地，不需要 GPU。ASR 判斷意圖後直接匹配固定回答，**回應速度 ~0.x 秒**。

**重要**：Plan B 台詞要**分場景設計**，不是一個扁平列表。互動機器狗在不同場景下說話的語氣不同。

**請設計以下問答**（至少 20 組，分三個場景）：

### 場景 A：熟人回家（語氣：溫暖開心）

| # | 觸發 | Go2 回答 | Go2 動作 |
|---|------|---------|---------|
| 1 | 人臉辨識到熟人 | ?（「[名字]，你回來了！」） | Hello(1016) |
| 2 | 熟人說「你好」 | ? | ? |
| 3 | 熟人說「我回來了」 | ? | WiggleHips(1033)? |

### 場景 B：使用者召喚互動（語氣：活潑友善）

> **特別注意 4.5**：這是 Demo 開場的 **Wow Moment**。盧柏宇 會把它接到 `self_introduce` skill sequence（Guardian Brain 自主規劃 6 個動作）。你只需要設計**每個動作之間的銜接台詞**（6 句短台詞，對應 Hello / Sit / Stand / Content / BalanceStand / WiggleHips），不用擔心動作排程。盧柏宇 會整合。

| # | 使用者說的 | Go2 回答 | Go2 動作 |
|---|-----------|---------|---------|
| 4 | 你叫什麼名字 | ?（「我叫 PawAI，是你的互動機器狗！」） | ? |
| **4.5** | **介紹自己 / 介紹一下 / 你會做什麼** | **（self_introduce 觸發，6 句銜接台詞由你設計）** | **Queue: Hello→Sit→Stand→Content→BalanceStand→WiggleHips** |
| 5 | 你有什麼功能 | ? | ? |
| 6 | 坐下 | ? | Sit(1009) |
| 7 | 站起來 | ? | StandUp(1004) |
| 8 | 跳舞 | ? | Dance1(1022) |
| 9 | 你幾歲 | ? | ? |
| 10 | 你好可愛 | ? | Content(1020)? |
| 11 | 搖屁股 | ? | WiggleHips(1033) |
| 12 | 打滾 | ? | Wallow(1021) |
| 13 | 停 | （不說話） | StopMove(1003) |
| 14 | 再見 | ? | Hello(1016) |

### 場景 C：陌生人警戒 + 異常（語氣：嚴肅警戒）

| # | 觸發 | Go2 回答 | Go2 動作 |
|---|------|---------|---------|
| 15 | 人臉辨識到陌生人 | ?（「偵測到不認識的人，已通知家人。」） | BalanceStand(1002) |
| 16 | 陌生人嘗試互動 | ?（「我現在處於警戒模式。」） | 不做 |
| 17 | 跌倒偵測觸發 | ?（「偵測到異常！你還好嗎？已通知家人。」） | StopMove(1003) |
| 18 | 久坐提醒 | ?（「坐很久了，要不要起來動一動？」） | ? |

### 場景 D：日常 / 通用

| # | 使用者說的 | Go2 回答 | Go2 動作 |
|---|-----------|---------|---------|
| 19 | 你在做什麼 | ? | ? |
| 20 | （聽不懂的話） | ?（「抱歉，我沒聽清楚」） | ? |
| ... | 你想加的 | ? | ? |

---

## 已知限制

- **本地 ASR 不可用**：Whisper 上機後噪音干擾嚴重，長句辨識失敗
- **本地 LLM 不可用**：Qwen 0.8B 智商極低，胡言亂語
- **全雲端依賴**：ASR + LLM 都需要 GPU server，斷線就只剩 Plan B
- **GPU 不穩**：昨天斷線 2 次，Plan B 必備
- Studio 顯示連線狀態燈號，可即時判斷是否切換

---

## 交付方式

### 4/13 前必交
1. 互動機器狗個性 SYSTEM_PROMPT（放寬長度 + 三種語氣：溫暖/活潑/嚴肅）
2. 場景化 Plan B 固定台詞表（至少 20 組，分四個場景）

### 4/13 後持續
3. Groq API 測試報告（延遲、品質、免費額度消耗速度）
4. edge-tts 語音推薦（哪個最像互動機器狗）
5. LLM 回覆品質測試截圖（不同 max_tokens 的對比）

**交付方式**：PR 或直接給 盧柏宇 文字都可以。
