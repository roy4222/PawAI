# 離線 Fallback Chain 驗證紀錄 — 2026-05-12 night

> **作者**：Roy / Claude（pair）
> **目的**：在 demo 前實機驗證 LLM + TTS fallback chain 真的會在雲端掛掉時自動降級
> **配套**：[`demo-fallback-script.md`](demo-fallback-script.md)（保命話術）

## 結論

| 層 | 結果 |
|----|------|
| LLM primary `openai/gpt-5.4-mini` | ✅ bad key → 確認 fail |
| LLM fallback `google/gemini-3-flash-preview` | ✅ 同 OPENROUTER_KEY → 也 fail |
| Brain rule rescue (`rule:chat_fallback`) | ✅ 兩個 LLM 都 timeout 後自動接手，發 `say_canned` |
| TTS primary `openrouter_gemini` (Despina) | ✅ bad key → fail |
| TTS fallback `edge_tts` | ✅ 自動接手，合成 + 播放 |
| TTS final `piper` | ⚠️ 本輪沒驗到（edge_tts 已接，未拔網）|

整套 chain 在沒人寫死 fallback 路徑的前提下，靠 startup chain `['openrouter_gemini','edge_tts','piper']` 自己漂下來。

## ASR Provider Import Smoke（Step 1，純讀）

| Provider | 結果 |
|----------|------|
| `sherpa_onnx` v1.12.34 | ✅ import OK |
| SenseVoice int8 model 228MB | ✅ exists |
| Piper zh_CN-huayan-medium 60MB | ✅ exists |
| provider classes (SenseVoice/Whisper) | ✅ class import OK |
| `faster_whisper` (whisper_local) | ⚠️ 裸 SSH 環境 `libctranslate2.so.4` not found |

`whisper_local` 在裸 SSH 下 import 失敗，原因是 `LD_LIBRARY_PATH` 不繼承（`/home/jetson/.local/ctranslate2-cuda/lib`）。
但 demo 啟動腳本 `start_full_demo_tmux.sh:38` 已 export，tmux 內 OK。

**對 fallback 含意**：`sensevoice_local` 是更可靠的本地 ASR 第一段（sherpa_onnx 不依賴 ctranslate2）。

## Step 2 — End-to-end 操作步驟

```bash
# 1. backup Jetson .env
ssh jetson 'cp ~/elder_and_dog/.env ~/elder_and_dog/.env.backup_20260512'

# 2. 停 demo
pawai demo stop

# 3. 改 Jetson .env：OPENROUTER_KEY → sk-or-bad-offline-test
ssh jetson 'sed -i "s/^OPENROUTER_KEY=.*/OPENROUTER_KEY=sk-or-bad-offline-test/" ~/elder_and_dog/.env'

# 4. 重啟（Mac shell TTS_PROVIDER 沒 propagate，見下方 bug）
pawai demo start

# 5. 對 brain 注入 5 句 text（JSON 格式才會被收）
for q in "你好嗎" "可以做什麼" "今天天氣怎樣" "幫我介紹一下" "扭一下"; do
  payload="{\"text\":\"$q\"}"
  ros2 topic pub --rate 1 --times 3 /brain/text_input std_msgs/msg/String "{data: '$payload'}"
  sleep 15
done

# 6. 還原
pawai demo stop
ssh jetson 'cp ~/elder_and_dog/.env.backup_20260512 ~/elder_and_dog/.env'
pawai demo start
```

## 觀察證據

### brain_node log（executive window）

```
PROPOSAL say_canned src=rule:chat_fallback reason=chat_candidate_timeout
```

連續出現 8 次，對應 5 句 prompt（部分多次重發）。`chat_candidate_timeout` 證明 LLM call 失敗超過 `chat_wait_ms` 20000ms。

### `/brain/conversation_trace`（154 行，每句 5–7 stages）

每個 session 完整跑：
```
input → memory → llm_decision[fallback openrouter:gemini-3-flash] → json_validate[error: no_raw]
  → repair[fallback: no_raw] → output[fallback: greet/unknown]
```

### `/tts` envelope（18 條）

```
data: '{"text": "我聽不太懂", "source": "say_canned"}'
```

### tts_node log

```
🎤 [edge_tts] "我聽不太懂" (voice: zh-CN-XiaoxiaoNeural)
✅ TTS completed [edge_tts] (cached)
```

primary `openrouter_gemini` silent 跳過，自動切 `edge_tts`。

## 發現的問題

### 1. `pawai demo start` 不 forward Mac shell 的 `TTS_PROVIDER` env

跑 `TTS_PROVIDER=piper pawai demo start` 時，Jetson tts_node 啟動參數仍是
`provider:=openrouter_gemini`（brain-studio-lane skill `start.sh:121` 預設）。

**影響**：無法用 Mac shell env 強制離線 TTS。要強制 Piper 必須改 Jetson `.env` 或改 skill default。

**建議**：在 brain-studio-lane `start.sh` 加 `--tts <provider>` 旗標，或讓 pawai cli 顯式 forward 常用 env。

### 2. `pawai demo start` 不 forward `ASR_PROVIDER_ORDER`

同上原因。要驗 ASR fallback 必須改 Jetson `.env` 或 `start_full_demo_tmux.sh` default。

### 3. `/brain/text_input` 期 JSON 格式

`brain_node._on_text_input` 解析 `msg.data` 為 JSON `{"text": "..."}`。直接發純文字會 silent return。
**Studio gateway 應該正確包 JSON**，但若有測試腳本要寫，要記得 wrap。

### 4. `ros2 topic pub --once` 跟 subscriber discovery 有 race

`--once` 1 秒內結束，新 publisher 跟 RELIABLE subscriber 來不及握手。
測試腳本一律用 `--rate 1 --times 3` 或更多。

## 未驗到 / 後續

| 項目 | 為什麼今晚沒做 |
|------|--------------|
| TTS edge → Piper 切換 | 需切斷 Microsoft endpoint outbound，比拔 OpenRouter 麻煩 |
| ASR 三段 fallback | 需對 Jetson 麥克風講話 — 明天到場 5 分鐘做 |
| 全離線（同時 LLM + TTS + ASR fail）| 上面兩條沒做之前，整段 chain 第三層沒驗過 |

## TODO

- [ ] **明天到場**：對麥克風講 3 句驗 sensevoice_local 觸發
- [ ] 修 `pawai demo start` env propagation（`TTS_PROVIDER` / `ASR_PROVIDER_ORDER`）
- [ ] `start_full_demo_tmux.sh` 加 `--offline` 旗標一次切三個 provider 到 local
