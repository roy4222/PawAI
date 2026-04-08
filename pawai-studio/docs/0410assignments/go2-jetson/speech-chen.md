# 陳若恩 — 語音功能互動設計

> **目標**：讓 Go2 的語音回答更聰明、更有互動性。連上 GPU 雲端調整 LLM，並設計 Plan B 固定台詞。

---

## 你的任務

1. SSH 連上 RTX 8000 server，調整 LLM prompt（放寬回答長度、加入個性）
2. 設計 Plan B 固定台詞腳本（10-15 組問答）
3. 測試 edge-tts 語音合成效果（本機可跑）
4. 前端 Studio 語音相關頁面也要看情況改善

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

### 你可以改的東西

1. **放寬 reply_text 長度限制**：12 字 → 50 字或更多
2. **加入個性**：讓 PawAI 更像一隻狗（興奮、忠誠、會撒嬌）
3. **加入自我介紹能力**：「我叫 PawAI，我會辨識人臉、聽懂你說話...」
4. **多輪對話 memory**：目前每次都是獨立回答，需要加 conversation history
5. **max_tokens**：目前 80，可以增加（但注意延遲會增加）

---

## Plan B 固定台詞設計（GPU 斷線時的備案）

Plan B 跑在本地，不需要 GPU。ASR 判斷意圖後直接匹配固定回答，**回應速度 ~0.x 秒**。

**請設計以下問答**（至少 10-15 組）：

| # | 使用者可能說的（關鍵字） | Go2 回答 | Go2 動作 (api_id) |
|---|----------------------|---------|-------------------|
| 1 | 你好 / 嗨 / hello | ? | Hello(1016) |
| 2 | 你叫什麼名字 | ? | ? |
| 3 | 你有什麼功能 / 你會做什麼 | ? | ? |
| 4 | 坐下 | ? | Sit(1009) |
| 5 | 站起來 / 起來 | ? | StandUp(1004) |
| 6 | 跳舞 / 跳一個 | ? | Dance1(1022)? Dance2(1023)? |
| 7 | 你幾歲 / 多大了 | ? | ? |
| 8 | 再見 / 掰掰 | ? | Hello(1016)? |
| 9 | 伸懶腰 / 伸展 | ? | Stretch(1017) |
| 10 | 打滾 / 翻身 | ? | Wallow(1021) |
| 11 | 你好可愛 / 好棒 | ? | Content(1020)? WiggleHips(1033)? |
| 12 | 搖屁股 | ? | WiggleHips(1033) |
| 13 | 停 / stop | （不說話） | StopMove(1003) |
| 14 | 你在做什麼 / 狀態 | ? | ? |
| 15 | ＿＿（你想加的） | ? | ? |

---

## 已知限制

- **本地 ASR 不可用**：Whisper 上機後噪音干擾嚴重，長句辨識失敗
- **本地 LLM 不可用**：Qwen 0.8B 智商極低，胡言亂語
- **全雲端依賴**：ASR + LLM 都需要 GPU server，斷線就只剩 Plan B
- **GPU 不穩**：昨天斷線 2 次，Plan B 必備
- Studio 顯示連線狀態燈號，可即時判斷是否切換

---

## 交付方式

1. 改好的 SYSTEM_PROMPT（放寬長度 + 加入個性 + 自我介紹）
2. Plan B 固定台詞表（至少 15 組）
3. 測試紀錄（LLM 回覆品質截圖）
4. PR 或直接給 Roy 文字

**deadline**：4/13 前 prompt + Plan B 台詞
