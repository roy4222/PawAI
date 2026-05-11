# 語音（speech_processor）— 架構詳述

**版本**：2026-05-12 brain-freeze-v2 快照
**位置**：`speech_processor/`
**主要入口**：`speech_processor/speech_processor/stt_intent_node.py`（單體式：mic + VAD + ASR + intent）
**TTS 入口**：`speech_processor/speech_processor/tts_node.py`
**狀態**：5/12 brain-freeze-v2，95% 完成（60s self-intro ×5 PASS，replies 自然）

---

## 1. 模組定位

語音是 PawAI **互動 70%** 的核心入口，端到端覆蓋「使用者開口 → PawAI 回應播放」整個閉環。技術上分成三大子系統：

- **ASR 輸入端**（多 provider fallback）
- **LLM 決策端**（Brain 接管，舊 bridge 為 fallback）
- **TTS 輸出端**（雙 lane 路由 + Go2 Megaphone 播放）

**5/12 brain-freeze-v2 主線**：
- **LLM**：`openai/gpt-5.4-mini`（P50 1.16s）→ `gemini-3-flash`（fallback）
- **TTS**：dual-route — gemini Despina（quality）+ edge_tts（fast）+ piper（local）
- **ASR**：`qwen_cloud`（RTX 8000 SenseVoice endpoint）→ `sensevoice_local`（sherpa-onnx int8）→ `whisper_local`（faster-whisper, CPU int8 default）

---

## 2. 整體 Pipeline（11-stage 端到端）

```
┌─────────────────────────────────────────────────────────────────────┐
│  USB mic (UACDemoV1.0 mono 48kHz)                                   │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼ sounddevice 回呼 → Queue(512)
┌─────────────────────────────────────────────────────────────────────┐
│            stt_intent_node  (單體式：mic→VAD→ASR→intent)            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 1: Echo Gate（subscribe /state/tts_playing）              ││
│  │   IF tts_playing OR (now < gate_open_time): 丟掉 frame          ││
│  │   cooldown 1.0s（防 TTS 自激）                                  ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 2: Resample 48k → 16k + mic_gain 軟體增益                 ││
│  │   numpy.interp 線性內插（不用 scipy）                            ││
│  │   stereo → mono downmix（HyperX SoloCast legacy 路徑）          ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 3: Energy VAD（in-process，非 Silero）                     ││
│  │   rms = sqrt(mean(frame²))                                       ││
│  │   start_threshold=0.015, stop_threshold=0.01                     ││
│  │   silence_duration_ms=800, min_speech_ms=300                     ││
│  │   adaptive_noise_floor (alpha=0.02, 預設 off)                    ││
│  │   ★ 已知瓶頸：2-10s 不穩，最大 e2e 延遲源 ★                     ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 4: ASR Provider Chain（3-level fallback）                  ││
│  │                                                                  ││
│  │   provider_order = [                                             ││
│  │     "qwen_cloud",         ← SenseVoice endpoint, RTX 8000 :8001  ││
│  │     "sensevoice_local",   ← sherpa-onnx int8, Jetson CPU         ││
│  │     "whisper_local"       ← faster-whisper, CPU int8 (default)   ││
│  │   ]                                                              ││
│  │                                                                  ││
│  │   fallback 觸發：timeout / empty / Exception                    ││
│  │   非主線 → result.degraded = True                                ││
│  │   ★ ASR warmup（daemon thread, ~12s）防第一次 CUDA JIT 延遲 ★  ││
│  │   ★ self._lock 序列化 warmup vs 正式推理 ★                     ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 5: OpenCC s2twp（簡轉繁台灣化）                            ││
│  │   "字幕by索兰娅" 之類幻覺 → 黑名單擋掉                          ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 6: Intent Classifier（純規則，無 ML）                      ││
│  │   keyword match（停/坐下/站/你好/狀態...）                       ││
│  │   confidence = score / len(matched)                              ││
│  │   7 intents: greet / come_here / stop / sit / stand /            ││
│  │              take_photo / status                                 ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  發佈 /event/speech_intent_recognized                                │
│      /asr_result, /intent, /state/interaction/speech                 │
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
              ┌──────────────────────────────────┐
              │  ★ Brain 主線（5/12 freeze）★   │
              │  pawai_brain conversation_graph  │
              │  _on_speech_event → 12-node LG   │
              │  → /brain/chat_candidate         │
              │  → interaction_executive 仲裁    │
              │  → /tts（含 [audio_tag]）        │
              └──────────────────────────────────┘
                              │
                              │  (legacy 旁路：llm_bridge_node
                              │   還在，作為 Brain 失靈 fallback；
                              │   intent_tts_bridge_node 純 template
                              │   fallback)
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│             tts_node  (dual-route + Megaphone 播放)                  │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 7: Lane Selection (_should_use_fast_lane)                  ││
│  │   priority:                                                      ││
│  │     1. SAFETY 關鍵字（停/危險/stop）→ fast lane（always）        ││
│  │     2. quality lane audio tag（[excited]/[laughs]/[whispers]）   ││
│  │        → quality lane                                            ││
│  │     3. effective_length > 12 字 → quality lane                   ││
│  │     4. default → fast lane                                       ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 8: Provider Chain                                          ││
│  │                                                                  ││
│  │   Quality lane:                                                  ││
│  │     OpenRouter Gemini 3.1 Flash TTS (Despina, audio tag native)  ││
│  │     → edge_tts → piper                                           ││
│  │                                                                  ││
│  │   Fast lane:                                                     ││
│  │     edge_tts (zh-CN-XiaoxiaoNeural) → piper                      ││
│  │                                                                  ││
│  │   audio tag 處理：                                               ││
│  │     supports_audio_tags=True (gemini)  → 保留 [excited]          ││
│  │     supports_audio_tags=False (其他)   → strip_audio_tags()      ││
│  │                                                                  ││
│  │   chunk 平行合成（gemini）：                                     ││
│  │     CHUNK_MAX_CHARS=40, MIN_SPLIT_CHARS=30                       ││
│  │     ThreadPoolExecutor max_workers=8                             ││
│  │     all-or-nothing：任一 chunk 失敗 → 整鏈 fallback              ││
│  │     ★ 每 chunk 重貼 leading audio tag 保持語氣 ★                ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 9: Cache lookup（MD5 key = text+voice+provider）           ││
│  │   命中 → 0ms（Piper 重複句子常見）                               ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 10: AudioProcessor.convert_to_wav                          ││
│  │   normalize: MP3/OGG → WAV 16kHz/16bit/mono                      ││
│  │   ★ +16dB gain boost（Go2 喇叭天生小聲，speech 用可接受 clip）★ ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                  │                                   │
│                                  ▼                                   │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │ Stage 11: Go2 Megaphone DataChannel                              ││
│  │   1. ENTER  api_id=4001, param={}            sleep 0.1s          ││
│  │   2. UPLOAD api_id=4003 × N chunks  (chunk_size=4096 base64)     ││
│  │      param 含 current_block_size + block_content +               ││
│  │             current_block_index + total_block_number             ││
│  │      sleep 0.07s 間隔                                            ││
│  │   3. WAIT  sleep(duration + 0.5s tail)                           ││
│  │   4. EXIT   api_id=4002, param={}    ★ 永遠送（即使 except）★  ││
│  │   5. COOLDOWN sleep 0.5s（state machine reset）                  ││
│  │                                                                  ││
│  │   ★ msg type 必須 "req" 不是 "msg" ★                            ││
│  │   ★ /state/tts_playing=True 全程鎖死，最後才 False ★            ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
                          Go2 喇叭 (16kHz)
```

---

## 3. ASR Provider 三層 Fallback

```python
provider_order = ["qwen_cloud", "sensevoice_local", "whisper_local"]
```

| Provider | 部署 | 模型 | 延遲 | 準確率 | 備註 |
|----------|------|------|------|:----:|------|
| **qwen_cloud** | RTX 8000 | FunASR SenseVoiceSmall | ~350-400ms | 92% | FastAPI :8001（OpenAI 相容 `/v1/audio/transcriptions`），需 SSH tunnel。Provider key 叫 `qwen_cloud` 是 legacy 命名，實際打的是 SenseVoice endpoint |
| **sensevoice_local** | Jetson CPU | sherpa-onnx int8（zh-en-ja-ko-yue）| ~400ms | 92% | 4 threads，model.int8.onnx |
| **whisper_local** | Jetson CPU（default）| faster-whisper tiny/small（CTranslate2）| ~3.0s | 52% | yaml 預設 `device: cpu` + `compute_type: int8`。若 demo 啟動腳本改 CUDA，**`compute_type` 必須 float16**（CUDA int8 在 Jetson silent fail）。`LD_LIBRARY_PATH` 必含 `/home/jetson/.local/ctranslate2-cuda/lib` |

### Fallback 觸發
```python
def _transcribe_with_fallback(audio_bytes):
    for provider_name in self.provider_order:
        try:
            result = provider.transcribe(audio_bytes, sample_rate, language)
            if result.text.strip():
                if provider_name != self.provider_order[0]:
                    result.degraded = True
                return result
        except Exception:
            continue
    return None
```

- timeout / empty transcript / Exception → 進下一層
- 非主線 → `result.degraded = True` 一路傳到 chat_candidate

### ASR Warmup（daemon thread）
node 啟動時跑一次空音訊（~12s 觸發 CUDA JIT），避免第一次真實語音被卡：
```python
def _do_warmup(self):
    silent_pcm = np.zeros(self.sample_rate, dtype=np.float32)
    wav_bytes = self._encode_wav(silent_pcm)
    whisper.transcribe(wav_bytes, sample_rate, language)
    self._warmup_done = True
```

`self._lock` 序列化 warmup vs 正式推理。第一次真實語音可能等 warmup 結束。

### 已知幻覺
Whisper 在靜音/噪音被誤解為「字幕by索兰娅」等假文字 → 黑名單擋掉，發 `intent=hallucination`。

---

## 4. LLM 路徑：Brain 主線 vs Legacy Bridge

```
                  /event/speech_intent_recognized
                              │
              ┌───────────────┼────────────────┐
              │               │                │
              ▼               ▼                ▼
       ┌──────────┐   ┌──────────────┐  ┌──────────────┐
       │ pawai_   │   │ llm_bridge_  │  │ intent_tts_  │
       │ brain    │   │ node         │  │ bridge_node  │
       │ (5/12    │   │ (legacy)     │  │ (純 template)│
       │  freeze) │   │              │  │              │
       │ ★主線★  │   │ Brain 失靈   │  │ 最後 fallback│
       │          │   │ 才走         │  │              │
       └──────────┘   └──────────────┘  └──────────────┘
              │               │                │
              ▼               ▼                ▼
       12-node LangGraph   OpenRouter →    template:
       → ChatCandidate     Cloud Qwen2.5-7B   "哈囉，我在這裡"
       → /brain/chat_      → Ollama 1.5B      "好的，停止動作"
         candidate         → RuleBrain         ...
              │
              ▼
        interaction_executive 仲裁
              │
              ▼
            /tts
```

### LLM Contract（llm_contract.py）

```python
LLM_REQUIRED_FIELDS = {
  "intent",          # greet|stop|sit|stand|status|chat|ignored
  "reply_text",      # 中文 reply（5/5 起 max_tokens 放寬到 2000）
  "selected_skill",  # hello|stop_move|sit|stand|null（P0 only）
  "reasoning",       # 20 字決策摘要
  "confidence"       # 0.0-1.0
}
```

Bridge 只接 P0 4 skills；其他富 skill 由 Brain `skill_policy_gate` 接管。

### OpenRouter 雙模型 fallback chain（Phase B B1）
```python
def _try_openrouter_chain(user_message):
    deadline = now + 5.0  # 總預算
    
    # Primary: gpt-5.4-mini
    first = _call_openrouter(gpt_mini_model, user_message, timeout=4.0)
    if first.ok: return first.result
    
    # Conditional fallback: gemini-3-flash
    if first.error == "timeout": return None  # 用光預算
    remaining = deadline - now
    if remaining <= 0.3: return None
    
    fallback = _call_openrouter(gemini_model, message, min(remaining, 4.0))
    return fallback.result if fallback.ok else None
```

Key params：`request_timeout = 4.0s`（5/4 從 2.0s 拉高給 urllib3 overhead）、`overall_budget = 5.0s`。

---

## 5. TTS 雙路由（5/9 dual-route）

| Lane | 觸發條件 | Provider Chain | 用途 | 延遲 |
|------|---------|---------------|------|:----:|
| **Fast** | 安全字 / ≤12 字 / 無 audio tag | edge_tts → piper | 短答、停止指令 | ~1.5s |
| **Quality** | audio tag / >12 字 | **Gemini Despina** → edge_tts → piper | 故事性、情緒 | ~6.5s |

### Lane Selection 邏輯
```python
def _should_use_fast_lane(text, threshold=12):
    # priority 1: SAFETY 關鍵字（停|stop|危險|警告...）→ fast lane（always）
    if SAFETY_KEYWORDS.search(text): return True
    # priority 2: quality lane audio tag（[excited] etc）→ quality lane
    if _has_quality_lane_audio_tag(text): return False
    # priority 3: 長度 > 12 → quality lane
    return _compute_effective_length(text) <= threshold
```

### Provider 細節

| Provider | name | rate | audio_tag | output | 備註 |
|----------|------|:----:|:--------:|:------:|------|
| **OpenRouter Gemini 3.1 Flash TTS** | `openrouter_gemini` | 24kHz | ✅ | WAV | Despina 聲線，平行 chunk |
| **edge_tts** | `edge_tts` | 24kHz | ❌（strip）| MP3 | zh-CN-XiaoxiaoNeural |
| **piper** | `piper` | 22050Hz | ❌（strip）| WAV | zh_CN-huayan-medium.onnx |

### Gemini 平行 chunk 合成
```python
def synthesize(text):
    chunks = self._split_for_tts(text)  # CHUNK_MAX_CHARS=40
    
    if len(chunks) == 1:
        return self._wrap_pcm_to_wav(self._synthesize_chunk(chunks[0]))
    
    with ThreadPoolExecutor(max_workers=min(len(chunks), 8)) as pool:
        results = [None] * len(chunks)
        for fut, idx in submit_all(chunks, pool):
            results[idx] = fut.result()
    
    # all-or-nothing：任一 None → return None → 鏈 fallback
    if any(p is None for p in results): return None
    return self._wrap_pcm_to_wav(b"".join(results))
```

每 chunk 重貼 leading audio tag 保持語氣一致（避免中段突然「無情緒」）。

### 已淘汰
- **MeloTTS**（3/26 confirmed deprecated）
- **ElevenLabs**（3/26 deprecated，5/9 dual-route 後完全沒位置）
- 程式碼留著但不在 production chain。

---

## 6. Audio Tag 系統

```python
QUALITY_LANE_AUDIO_TAGS = {
  "excited", "curious", "playful", "worried",
  "whispers", "laughs", "sighs", "thinking",
  "gentle", "happy", "sad", "shy"
}

_AUDIO_TAG_RE = re.compile(r"\[[a-zA-Z_]+\]\s*")
```

**支援矩陣**：

| Provider | 行為 |
|----------|------|
| Gemini | 直接渲染情緒/SFX，`[excited]` → 興奮語氣，`[laughs]` → 加笑聲 |
| edge_tts / piper | `strip_audio_tags()` 強制移除，純文字合成 |

**Normalize unstable tags**：N6 邏輯有兩層：
1. **Brain validator 端**（`pawai_brain/validator.py::normalize_audio_tags()`）：在 LLM reply publish 前掃描，把 `[whispers]` / `[sighs]` 改為 `[curious]`（這兩個 tag 會讓 openrouter_gemini TTS 鎖整句變 whisper 音色）。這是主動防線。
2. **Persona OUTPUT.md** 也已從合法 tag 清單裡移除 `[whispers]` / `[sighs]`（被動防線，引導 LLM 不要生）。
3. **TTS boundary**：`supports_audio_tags=False` 的 provider（edge_tts / piper）仍會 `strip_audio_tags()` 強制移除所有 tag，純文字合成。

**為什麼這樣設計**：Gemini 3.1 是目前 OpenRouter 上唯一原生支援 audio tag 的 TTS，所以 quality lane 走 Gemini；fast lane 不在乎情緒，可以 strip。

---

## 7. Go2 Megaphone 播放協議

**完整序列**（tts_node._play_on_robot_datachannel）：

```python
1. ENTER:    POST /webrtc_req {api_id: 4001, param: "{}"}
             sleep 0.1s（state machine settle）

2. UPLOAD:   for chunk in chunks:
               POST /webrtc_req {
                 api_id: 4003,
                 param: {
                   "current_block_size": len(b64_chunk),
                   "block_content": base64,
                   "current_block_index": idx,
                   "total_block_number": N
                 }
               }
               sleep 0.07s

3. WAIT:     sleep(duration_s + 0.5s tail)

4. EXIT:     POST /webrtc_req {api_id: 4002, param: "{}"}
             ★ 即使 except 也要送，防 state machine 卡住 ★

5. COOLDOWN: sleep 0.5s
             /state/tts_playing 在這段時間維持 True
             之後才 False，加 1.0s echo_cooldown 共 1.5s
```

**規格**：
- `chunk_size = 4096`（base64 字元，非 bytes）
- `msg.type = "req"`（不是 "msg"）
- WAV: **16kHz / 16bit / mono**（Megaphone 硬體限制）
- **+16dB gain boost**（Go2 喇叭天生小聲）
- chunk 間隔 `0.07s`（70ms）

**為什麼 EXIT 永遠送**：若 ENTER 後沒 EXIT，Megaphone state machine 會卡在 ENTER 狀態，下次 ENTER 會 silent fail。所以即使 chunk upload 中 except 也必須 EXIT。

---

## 8. Echo Gate（防 TTS 自激）

```python
/state/tts_playing (Bool, TRANSIENT_LOCAL latched)
    │
    ▼
stt_intent_node._on_tts_playing:
    msg.data=True  → _tts_playing=True, 立即關 gate
    msg.data=False → _tts_playing=False, 設 cooldown 1.0s 後才開

audio_callback:
    IF _is_echo_gated(): return  # 丟整個 frame
```

**總關閉時間**：synthesis（可變）+ playback（可變）+ Megaphone cooldown 0.5s + echo_cooldown 1.0s = **最少 1.5s**。

**為什麼是 magic number 1.5s**：Go2 喇叭發聲的 acoustic delay + 麥克風捕捉延遲，1.5s 是 5/4 實機調出來的最低安全值。動之前要全套 e2e 測。

---

## 9. e2e 延遲現況（5/12）

```
使用者說完話
    │
    ▼ VAD 偵測 speech_end       ★ 2-10s（最大瓶頸）★
    │
    ▼ ASR transcribe             ~400ms (SenseVoice)
    │
    ▼ Brain LangGraph + LLM     1.16s (gpt-5.4-mini P50)
    │
    ▼ TTS synthesize             ~1.5s (fast) / ~6.5s (quality)
    │
    ▼ Megaphone upload + tail   ~1.0s
    │
    ▼ Go2 喇叭發聲
   
3/18 E2E：5.7-14.5s（VAD 是大頭）
5/12 E2E：~5-8s（LLM 從 4s 砍到 1.16s）
```

**VAD 是唯一沒解決的瓶頸**（從 3/18 起 known issue）。3/18 換掉 LLM、5/8 加 prefix cache、5/12 換 gpt-mini 都繞過 VAD。徹底解決需換 Silero VAD 或外部 frontend。

---

## 10. 5/12 brain-freeze-v2（與 4/x baseline 對照）

| Layer | 4/x baseline | 5/12 freeze-v2 | 動機 |
|-------|--------------|----------------|------|
| LLM primary | gemini-3-flash (1.89s P50) | **gpt-5.4-mini (1.16s P50, -39%)** | 8-model A/B：gpt-mini 完勝 |
| LLM fallback | — | gemini-3-flash | OpenRouter 韌性 |
| TTS primary | piper local only | **dual-route gemini + edge_tts** | 5/9 PR #55/#57 |
| audio tag | gemini 3.0 不支援 | **gemini 3.1 native** [excited]/[laughs] | persona v3 情緒渲染 |
| max_tokens | 120（限 40 字 reply）| **2000，不限長度** | 5/5 evening：放開敘事，memory deque(10) |
| ASR 後處理 | 無簡轉繁 | **OpenCC s2twp 注入** | 5/9 issue 6 |

### 8-model A/B 結論
- ✅ **gpt-5.4-mini**：P50 1.16s, $0.018/12-call, 質量 4.5/5。理解 emoji 上下文，提案能力強
- gemini-3-flash：P50 1.89s，做 fallback
- ❌ DeepSeek V4 Flash：P95 34s reasoning tail（不可用）
- ❌ Claude Haiku：JSON 4/12 包 markdown fence
- ❌ Claude Sonnet：2× 慢 + 貴 + 無優勢
- ❌ GPT-5.5 / Opus：太貴
- ❌ GPT Nano：漏 audio tag（情緒沒了）

---

## 11. 設定參數（speech_processor.yaml）

```yaml
stt_intent_node:
  ros__parameters:
    # 音訊
    sample_rate: 16000           # ASR 目標
    capture_sample_rate: 16000   # 0 = 自動偵測
    frame_samples: 512
    channels: 1                  # mono（HyperX 用 2）
    input_device: -1             # -1 = 預設
    mic_gain: 1.0
    alsa_device: ""              # 或 "plughw:0,0"
    
    # 錄音 + VAD
    max_record_seconds: 6.0
    speech_end_grace_ms: 500
    pre_roll_ms: 500
    
    # Provider 鏈（注意 cloud provider key 叫 qwen_cloud，legacy 命名）
    provider_order: ["qwen_cloud", "sensevoice_local", "whisper_local"]
    
    # Cloud SenseVoice（透過 qwen_asr.* 參數設定）
    qwen_asr.base_url: "http://127.0.0.1:8001/v1/audio/transcriptions"
    qwen_asr.timeout_sec: 5.0
    qwen_asr.model_name: "sensevoice"
    
    # Local SenseVoice
    sensevoice_local.model_path: "/home/jetson/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx"
    sensevoice_local.num_threads: 4
    
    # Whisper（yaml 預設走 CPU int8）
    whisper_local.model_name: "tiny"
    whisper_local.device: "cpu"           # 預設 cpu；若改 "cuda" 必須同步改 compute_type
    whisper_local.compute_type: "int8"    # CPU 用 int8；★ CUDA 必須改 float16（int8 silent fail）★
    
    # Energy VAD
    energy_vad.start_threshold: 0.015
    energy_vad.stop_threshold: 0.01
    energy_vad.silence_duration_ms: 800
    energy_vad.min_speech_ms: 300
    energy_vad.adaptive: false
    
    # 其他
    language: "zh"
    enable_s2twp: true               # OpenCC 簡轉繁
    tts_echo_cooldown_ms: 1000

# TTS 在 tts_node._declare_parameters() 內，不在 yaml（env 為主）
```

### TTS env 覆蓋
```bash
PAWAI_LLM_MODEL=openai/gpt-5.4-mini
PAWAI_LLM_FALLBACK=google/gemini-3-flash-preview
TTS_PROVIDER=edge_tts  # 或 openrouter_gemini
OPENROUTER_GEMINI_VOICE=Despina
OPENROUTER_KEY=...
ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'
```

---

## 12. Demo / 測試 / Ops

### 啟動腳本
| 腳本 | 用途 | 主要 env |
|------|------|---------|
| `start_full_demo_tmux.sh` | 13-window 全功能 demo | `PAWAI_LLM_MODEL`, `TTS_PROVIDER` |
| `start_llm_e2e_tmux.sh` | 純語音 e2e（無 perception/Go2）| `LLM_ENDPOINT`, `OPENROUTER_KEY` |
| `start_pawai_brain_tmux.sh` | Brain MVS conversation | `output_mode:=brain` |

### 測試
- `smoke_test_e2e.sh` — 5 輪快測，pre-demo sanity
- `run_speech_test.sh` — 30 輪驗收（15 fixed + 15 free）
- `test_scripts/speech_30round.yaml` — 完整定義

### Speech Test Observer
`speech_test_observer.py`：
- 監聽 `/state/interaction/speech` 狀態機切換（LISTENING→RECORDING→TRANSCRIBING）
- session_id + 5s 時窗關聯 TTS / WebRTC
- 計算 e2e_latency_ms、accuracy、hallucination_rate
- 與 Jetson MVP baseline 對照 PASS/MARGINAL/FAIL

### 雲端基礎設施
```bash
# RTX 8000 上跑
python scripts/sensevoice_server.py --port 8001 --device cuda:0

# Jetson 端建 SSH tunnel
ssh -f -N -L 8001:localhost:8001 roy422@RTX_SERVER_IP
```

---

## 13. 已知陷阱 / CLAUDE.md 強制規則

### 硬體
1. USB mic device index 重開機會漂（24→0），必先 `source scripts/device_detect.sh`
2. HyperX SoloCast stereo-only，channels=2 + 手動 downmix。主線改用 UACDemoV1.0 mono
3. USB speaker `plughw:N,0` card index 漂移 → 同上自動偵測

### 軟體
4. **Whisper 預設 CPU + int8**（與 `speech_processor.yaml` 一致）；若切 CUDA 必須 float16，**CUDA + int8 在 Jetson 會 silent fail**
5. `LD_LIBRARY_PATH` 必含 `/home/jetson/.local/ctranslate2-cuda/lib`
6. zsh array 字串外要單引號裹雙引號：`'["whisper_local"]'`
7. 改 Python 必 `colcon build --packages-select speech_processor` + `source install/setup.zsh`
8. **tts_node mid-session 重啟會 Megaphone silent fail** → 必須連 Go2 driver 一起重啟（甚至 Go2 重開機）
9. echo gate 1.5s 是 magic number，動之前要全套 e2e 測

### Provider
10. **MeloTTS / ElevenLabs 已棄用（3/26）** — 程式碼留著但不要重啟用，要 spike 改 `tools/tts_spike/`
11. OpenRouter API key 必須 `.strip()`（5/12 hotfix：CRLF 換行字元會 500 "Invalid return character"）
12. OpenRouter request timeout 4.0s（5/4 從 2.0s 拉高，給 urllib3 overhead）

### 模型
13. Go2 Megaphone **16kHz 硬體限制**，TTS 高頻會糊（清晰度問題，無解）
14. Piper +16dB gain 可能輕微爆音（speech 可接受）

---

## 14. 執行緒模型

### 主要執行緒
1. **ROS2 executor**（rclpy.spin）
   - subscribers: `_on_tts_playing`, `_on_text_input`, `_on_vad_event`
   - timers: `_drain_audio_queue` (20ms), `_check_recording_timeout` (100ms), `_publish_state` (200ms)

2. **Sounddevice audio callback**（高優先，獨立執行緒）
   - 每 32ms 一個 frame（512 samples @ 16kHz）
   - 非 blocking：enqueue 到 `_audio_queue (maxsize=512)`

3. **ASR executor**（ThreadPoolExecutor, max_workers=1）
   - 單一長任務 `_process_audio_session`
   - 持有 `_processing_lock` + provider-level lock

4. **Warmup thread**（daemon，非 blocking）
   - 啟動時跑空音訊預熱
   - 與 ASR executor 競爭 `WhisperLocalProvider._lock`

### Lock Hierarchy
```
_record_lock (RLock 風格 main guard)
    └─ 保護 _recorder_state, _speech_end_deadline
       _handle_speech_start / _handle_speech_end / _finalize_recording_locked

_processing_lock (per-session, non-blocking acquire)
    └─ 保護 ongoing ASR transcription
       忙碌時 drop overlapping speech

Provider locks (WhisperLocalProvider._lock, SenseVoiceLocalProvider._lock)
    └─ 序列化模型推理
       warmup + first real ASR 都會競爭
```

---

## 15. Session 追蹤

格式：`{prefix}-YYYYMMDD-HHMMSS-{random_hex(2)}`

| Prefix | 來源 |
|------|------|
| `sp-` | speech（energy VAD）|
| `txt-` | text fallback |
| `ev-` | external VAD event |

生命週期：
1. 偵測語音 → 新 session_id
2. finalize recording → ASR queued
3. publish intent event with session_id
4. 下次語音 → reset

---

## 16. 關鍵設計決策（給寫計畫書的參考）

1. **互動 70% 入口**：語音是 PawAI 最關鍵的人機介面，端到端覆蓋使用者意圖到實體回應
2. **完整 11-stage pipeline**（第二節圖）：從 mic 到 Go2 喇叭的完整鏈路
3. **三層 ASR fallback**（第三節）：cloud + local + Whisper，每層獨立失靈策略
4. **Brain 主線 vs Legacy bridge**（第四節）：架構演進故事 — 從規則 template 到 LangGraph 大腦
5. **TTS dual-route 設計**（第五節）：speed vs quality 不是二選一，是按 context 動態路由
6. **Audio tag 革命**（第六節）：persona v3 情緒渲染靠 Gemini 3.1 原生支援
7. **Go2 Megaphone 協議**（第七節）：踩過很多坑才確認的 4001/4003/4002 序列 + cooldown
8. **Echo gate 防自激**（第八節）：1.5s magic number 的工程妥協
9. **5/12 brain-freeze 故事**（第十節）：8 模型 A/B → gpt-mini 完勝 → 凍結為 demo 主線
10. **30-round 驗收框架**（第十二節）：可量化的 e2e 品質基準
11. **VAD 是唯一未解瓶頸**（第九節）：誠實承認 2-10s 是最大延遲源，靠繞過維持可用

---

## 17. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| STT/Intent 主檔（單體）| `speech_processor/speech_processor/stt_intent_node.py` |
| TTS node | `speech_processor/speech_processor/tts_node.py` |
| TTS provider 實作 | `speech_processor/speech_processor/tts_provider.py` |
| Intent classifier | `speech_processor/speech_processor/intent_classifier.py` |
| Audio tag | `speech_processor/speech_processor/audio_tag.py` |
| TTS split | `speech_processor/speech_processor/tts_split.py` |
| Text normalization | `speech_processor/speech_processor/text_normalization.py` |
| LLM bridge (legacy) | `speech_processor/speech_processor/llm_bridge_node.py` |
| LLM contract | `speech_processor/speech_processor/llm_contract.py` |
| 設定 | `speech_processor/config/speech_processor.yaml` |
| 雲端伺服器 | `scripts/sensevoice_server.py`（RTX 8000）|
| 啟動腳本 | `scripts/start_full_demo_tmux.sh` / `start_llm_e2e_tmux.sh` |
| 30 輪測試框架 | `test_scripts/speech_30round.yaml` + `speech_test_observer.py` |
| 模組文件 | `docs/pawai-brain/speech/README.md` + `CLAUDE.md` + `AGENT.md` |
| 5/12 freeze 紀錄 | `docs/pawai-brain/dev-logs/2026-05-12-llm-naturalness-ab-eval.md` |
| Benchmark 決策 | `docs/pawai-brain/speech/research/2026-03-21-stt-benchmark.md` + `2026-03-21-tts-benchmark.md` |
| Contract schema | `docs/contracts/interaction_contract.md` §4.1 |
