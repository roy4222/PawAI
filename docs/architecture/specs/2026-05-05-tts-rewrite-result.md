# B1 Plan D — TTS Provider 換血結果

**完成日期**：2026-05-04 evening（22:00 收尾）
**Plan 來源**：`/home/roy422/.claude/plans/jetson-kind-book.md`
**前置條件**：commit `3c3a933`（A+B：audio tag strip hack + OpenRouter timeout default 提升 + CLAUDE.md 修正）

---

## TL;DR

從「strip audio tag hack」升級成「provider-aware tag rendering + 3-step fallback chain」。Demo 第一句話現在能用 **Gemini 3.1 Flash TTS Preview / voice=Despina** 自然渲染 `[excited]` `[laughs]` `[curious]` 等情緒，網路抖時自動 fallback `edge_tts → Piper`。

| Stage | 目的 | Commit |
|---|---|---|
| 1 | 三條 curl 路徑實測 + 中文耳朵聽 + 決策 | (no commit; data here) |
| 2 | 抽 `TTSProviderBase` Protocol，純 refactor 不改行為 | `1df3afe` |
| 3 | `TTSProvider_OpenRouterGemini` class + 6 unit tests | `4f6da89` |
| 4 | Fallback chain + per-provider cache + log cosmetic fix | `54c68d0` |
| 5 | 本文件 + project-status 更新 | (this commit) |

---

## Stage 1：路徑決策（耳朵驗收）

### OpenRouter `/api/v1/models?output_modalities=speech` 真實清單

```
google/gemini-3.1-flash-tts-preview     ← 選定
zyphra/zonos-v0.1-transformer
zyphra/zonos-v0.1-hybrid
sesame/csm-1b
canopylabs/orpheus-3b-0.1-ft
hexgrad/kokoro-82m
mistralai/voxtral-mini-tts-2603
openai/gpt-4o-mini-tts-2025-12-15        ← 對照組
```

OpenRouter 確實代理 Gemini TTS（user 假設正確）。同把 `OPENROUTER_KEY`，不需另申請 Google AI Studio key。

### 三條 curl 結果（Jetson `plughw:2,0` USB 喇叭實聽）

| 候選 | format | HTTP | 延遲 | 備註 |
|---|---|---|---|---|
| Gemini `mp3` | ❌ | 400 | 1.15s | `Gemini TTS only supports response_format="pcm"`（OpenRouter 端強制） |
| Gemini `pcm` | ✅ | 200 | 4.75s | `audio/pcm;rate=24000;channels=1`，自包 WAV header 後 5.2s 音檔 |
| OpenAI `mp3` | ✅ | 200 | 2.17s | `MPEG ADTS layer III v2 128kbps 24kHz Monaural` |

### 候選比較（user 耳朵判定）

| 維度 | Gemini Achird | Gemini Despina | OpenAI alloy |
|---|---|---|---|
| 中文音質 | OK | **自然多了** ← user 選 | OK |
| `[excited]` 興奮渲染 | ✓ | ✓ | ? (未細測) |
| `[laughs]` 笑聲 | ✓ | ✓ | ? |
| `[curious]` 好奇 | ✓ | ✓ | ? |
| 延遲 | ~4.6s | ~4.6s | ~2.2s |

**最終決策**：`google/gemini-3.1-flash-tts-preview` + voice=`Despina`
**犧牲**：延遲多 2.4s，但音質贏 + tag 渲染贏，user 接受

### Audio contract（Stage 1 實測確認）

| 項 | 值 |
|---|---|
| Endpoint | `POST https://openrouter.ai/api/v1/audio/speech` |
| Auth | `Authorization: Bearer $OPENROUTER_KEY` |
| Required body | `{model, input, voice, response_format: "pcm"}` |
| Response | raw PCM bytes（不是 WAV 容器）|
| 採樣 | 24000 Hz / 16-bit / mono（content-type 明寫 `rate=24000;channels=1`） |
| 須自處理 | 用 stdlib `wave` 包 RIFF header 才能進 pydub / cache |

---

## Stage 2：Protocol 抽出（純 refactor）

新檔 `speech_processor/speech_processor/tts_provider.py`：

```python
@runtime_checkable
class TTSProviderBase(Protocol):
    name: str
    sample_rate: int
    supports_audio_tags: bool
    def synthesize(self, text: str) -> Optional[bytes]: ...
```

既有 4 class 加 class attribute，**未改邏輯**：

| Class | name | sample_rate | supports_audio_tags |
|---|---|---|---|
| ElevenLabs | `elevenlabs` | 22050 | False |
| MeloTTS | `melotts` | 0（dynamic） | False |
| Piper | `piper` | 22050 | False |
| EdgeTTS | `edge_tts` | 24000 | False |

`tts_callback` 加守門：`if not provider.supports_audio_tags: text = strip_audio_tags(...)`。全 False → 與 Stage 2 前完全等價。

驗證：edge_tts smoke `[excited] 你好 Stage 2` 仍 log `→ stripped "你好 Stage 2"`，行為不變。

---

## Stage 3：Gemini Provider 落地

新增 class `TTSProvider_OpenRouterGemini`：
- `name="openrouter_gemini"`, `sample_rate=24000`, **`supports_audio_tags=True`**
- 讀 `OPENROUTER_KEY` from env（不入 ROS introspection）
- timeout default 6.0s（Stage 1 baseline 4.6s + ~30% headroom）
- 包 WAV header（`wave.open(...)` setnchannels=1 / setsampwidth=2 / setframerate=24000）
- 失敗 return None → Stage 4 chain 接手

新 ROS params + env：
- `openrouter_gemini_voice` (default `Despina`)
- `openrouter_gemini_model` (default `google/gemini-3.1-flash-tts-preview`)
- `openrouter_gemini_timeout_s` (default `6.0`)

6 unit tests（mock `requests.post`）：happy path / 401 / timeout / missing key / JSON body drift / protocol attrs。

Live smoke 3 句：
```
[excited] 你好，我是 PawAI！      gen 2.2s + play 2.8s
[laughs] 哈哈，今天天氣真好         gen 5.9s + play 3.3s
[curious] 你今天過得好嗎？          gen 1.9s + play 2.0s
```
User 聽了確認情緒 + 音質都到位。重播 cache hit 全綠。

---

## Stage 4：Fallback Chain + Log Cosmetic Fix

`_build_fallback_chain()`：

| Main | Fallback chain |
|---|---|
| `openrouter_gemini` | `[edge_tts, piper]` |
| `edge_tts` | `[piper]` |（legacy 行為保留）
| 其他 | `[]` |

`tts_callback` 重寫成單一 chain 迭代：每個 provider 用自己的 cache key、自己決定 strip。Per-provider supports_audio_tags 守門 → fallback 走 edge_tts/Piper 時自動 strip。

Cosmetic log 修：
- 舊：`🎤 TTS Request: "..." (voice: XrExE9yKIg1WjnnlVkGX)` ← 一律顯示 ElevenLabs voice ID
- 新：`🎤 [openrouter_gemini] "..." (voice: Despina)` / `🎤 [edge_tts] "..." (voice: zh-CN-XiaoxiaoNeural)`

5 unit tests（chain composition / voice resolution per provider）。Smoke 雙路徑驗證：Gemini main 帶 tag 通過、edge_tts main 仍 strip。

---

## 不做（明確排除，Plan 既定）

- ❌ 不重寫 Megaphone DataChannel chunking
- ❌ 不改 cache key schema（已 provider-specific）
- ❌ 不刪 edge-tts / Piper（保留為 fallback 鏈成員）
- ❌ 不動 `audio_tag.py` 純函數（只在 tts_node 加 supports_audio_tags 守門）
- ❌ 不做 streaming TTS / LLMProvider adapter 化（B1 另一條）

---

## Known Limitations

1. **Gemini 3.1 Flash TTS 是 preview 階段**，可能有 rate limit / 廢棄風險。Demo 前一週要再 curl 一次確認 model 還在 OpenRouter 清單
2. **延遲 4.6s 偏高**：對話間延遲可感。streaming TTS 是出路但需 LLM+TTS 管線重寫，不在本 plan
3. **Audio tag 集合未官方公開**：目前驗證可用 `[excited] [laughs] [curious]`，其他（`[sighs]` `[whispers]` `[playful]` 等）未實測，可能被讀為文字。Skill Registry 預埋的 21 條 say_template 含 `[sighs]` `[worried]` 需另跑一輪驗收
4. **OpenRouter 端只接 PCM**（不是 mp3/wav，不像 OpenAI gpt-4o-mini-tts），改 provider 時須修 request body
5. **Provider chain 沒有時間預算總控**：第一個 Gemini 4.6s + 第二個 edge_tts 1-2s + Piper 1s = 最壞 ~7s 才回，但本 demo 沒上 streaming，可接受

---

## Follow-up（不在這個 plan，留給後續）

- LLMProvider 4 介面 adapter 化（B1 另一條）
- Skill Registry 21 條 say_template 的 audio tag 全套渲染驗收
- Streaming TTS（管線化 LLM+TTS）
- B4 感知模組擴 / B5 Studio Brain trace / B6 PR port / B7 60min 壓測
- Megaphone 路徑 Despina 24kHz → 16kHz resample 端到端驗收（目前只跑 USB local，Go2 內建喇叭路徑沒在這輪驗）
