# Speech ASR and VAD

這份文件深挖 `stt_intent_node.py`：USB mic、echo gate、energy VAD、ASR fallback，以及為什麼語音延遲會飄。

## 1. Mic input

入口：

```text
speech_processor/speech_processor/stt_intent_node.py
```

它用 `sounddevice.InputStream` 直接開 mic，不走 ROS `/audio/*` topic。

config 預設：

```yaml
sample_rate: 16000
capture_sample_rate: 16000
frame_samples: 512
channels: 1
input_device: -1
alsa_device: ""
mic_gain: 1.0
```

code 預設 channels 是 2，但 yaml 覆蓋成 1。若換 USB mic，先看實際 device 是否只支援 48k 或 stereo。

## 2. Echo gate

`stt_intent_node` 訂閱：

```text
/state/tts_playing
```

TTS 播放中或播放結束 cooldown 期間，audio callback 直接丟 frame：

```text
if _is_echo_gated():
    return
```

目前 cooldown：

```yaml
tts_echo_cooldown_ms: 1000
```

實際閉鎖時間約：

```text
TTS synthesis 開始前即 True
+ playback duration
+ Megaphone cooldown 0.5s
+ echo cooldown 1.0s
```

這能防止 PawAI 聽到自己的聲音，但也會造成一個副作用：如果使用者在 PawAI 剛講完後立刻接話，前 1 秒可能被丟掉。

## 3. Energy VAD

Energy VAD 在 `stt_intent_node.py` 內建，不是 Silero。

config：

```yaml
energy_vad.enabled: true
energy_vad.start_threshold: 0.015
energy_vad.stop_threshold: 0.01
energy_vad.silence_duration_ms: 800
energy_vad.min_speech_ms: 300
energy_vad.adaptive: false
```

流程：

```text
rms >= start_threshold -> speech_start
rms < stop_threshold 持續 silence_duration_ms -> speech_end
```

延遲主要來自：

| 來源 | 影響 |
| --- | --- |
| `silence_duration_ms=800` | 使用者講完後至少等 0.8s 才判定結束 |
| `speech_end_grace_ms=500` | speech_end 後再收 0.5s |
| ASR provider latency | cloud/local/whisper 不同 |
| Brain LLM latency | 另算 |
| TTS synthesis/playback | 另算 |

所以「VAD -> ASR -> LLM -> TTS」裡，VAD 不是唯一延遲，但它是最固定的一段尾巴。

## 4. ASR provider chain

provider order：

```yaml
provider_order: ["qwen_cloud", "sensevoice_local", "whisper_local"]
```

build provider 時的實際行為：

- `qwen_cloud` 永遠會被建立，但如果 `base_url` 空或服務不可用，transcribe 時 fail。
- `sensevoice_local` 只有在 `sherpa_onnx` import 成功且 model/tokens 存在時才加入。
- `whisper_local` 永遠會建立，作為最後 fallback。

provider：

| provider | 實作 | 風險 |
| --- | --- | --- |
| `qwen_cloud` | HTTP POST 到 SenseVoice endpoint | tunnel/server 掛就 fallback |
| `sensevoice_local` | sherpa-onnx SenseVoice int8 CPU | model path / tokens / package 缺失就跳過 |
| `whisper_local` | faster-whisper 或 openai-whisper | 慢、中文準確率低、靜音幻覺 |

## 5. ASR output

STT 發兩個主要 topic：

```text
/asr_result
/event/speech_intent_recognized
```

`/asr_result`：

```json
{
  "session_id": "...",
  "text": "你好",
  "provider": "qwen_cloud",
  "latency_ms": 380.5,
  "degraded": false,
  "reason": "speech_end"
}
```

`/event/speech_intent_recognized`：

```json
{
  "event": "speech_intent_recognized",
  "session_id": "...",
  "intent": "greet",
  "confidence": 1.0,
  "matched_keywords": ["你好"],
  "text": "你好",
  "source": "audio",
  "provider": "qwen_cloud",
  "latency_ms": 380.5,
  "degraded": false
}
```

## 6. Hallucination filter

Whisper 常見靜音幻覺會被黑名單擋掉，例如：

```text
字幕by
謝謝大家
請訂閱
thank you for watching
subtitles
```

命中時仍會 publish intent：

```text
intent = hallucination
degraded = true
```

這讓 observer 可以記錄 miss，而不是整段語音消失。

## 7. 目前語音輸入最可能的痛點

1. PawAI 講話和使用者說話混在一起：echo gate 擋得住自激，但使用者插話會被丟。
2. VAD end 太慢：`800ms + 500ms` 讓短問答尾巴偏長。
3. cloud ASR tunnel 不穩：會 fallback，但延遲會突然變長。
4. Whisper fallback 幻覺：已有黑名單，但不會完全消失。
5. `enable_vad=true` 同時開 `vad_node`，而 `stt_intent_node` 自己也有 energy VAD：要避免外部 VAD event 和 internal VAD 重複 start/end 造成 session reset。

最後一點要現場確認：如果出現 `Received speech_start while recording; resetting session`，代表雙 VAD 路徑可能互相干擾。

