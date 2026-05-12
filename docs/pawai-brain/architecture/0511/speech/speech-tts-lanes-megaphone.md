# Speech TTS Lanes and Megaphone

這份文件深挖 `tts_node.py`：dual-route、audio tag、provider fallback、cache、Go2 Megaphone 播放。

## 1. TTS input

TTS node 訂閱：

```text
/tts
```

支援兩種 payload：

純文字：

```text
[curious] 你好呀
```

JSON envelope：

```json
{
  "text": "[curious] 你好呀",
  "input_origin": "studio_text",
  "source": "chat_reply"
}
```

`interaction_executive_node` 只有在 SAY step 有 `input_origin` 或 `source` 時才會包 envelope；其他 legacy publisher 仍可能直接發純文字。

## 2. Dual-route lane

lane 判斷在：

```text
speech_processor/speech_processor/tts_node.py::_should_use_fast_lane()
```

優先序：

1. 有安全關鍵字：fast lane。
2. 有 quality audio tag：quality lane。
3. effective length > threshold：quality lane。
4. 否則 fast lane。

目前 threshold：

```text
FAST_LANE_THRESHOLD = 12
```

quality audio tags：

```text
excited, curious, playful, worried, whispers, laughs,
sighs, thinking, gentle, happy, sad, shy
```

## 3. Provider chains

如果 primary 是 `openrouter_gemini`：

```text
quality/default:
openrouter_gemini -> edge_tts -> piper

fast:
edge_tts -> piper
```

如果 primary 是 `edge_tts`：

```text
edge_tts -> piper
```

Studio chain 在有 `OPENROUTER_KEY` 時會預先建：

```text
gemini -> default primary -> fallback
```

## 4. Audio tag handling

每個 provider 都有：

```text
supports_audio_tags
```

| provider | supports_audio_tags | 行為 |
| --- | --- | --- |
| `openrouter_gemini` | true | 保留 `[curious]` 等 tag |
| `edge_tts` | false | 呼叫前 strip tag |
| `piper` | false | 呼叫前 strip tag |

這代表 fallback 到 edge/piper 時，情緒 tag 不會被念出來，但也不會保留情緒效果。

## 5. Gemini chunking 現況

舊文件可能寫：

```text
CHUNK_MAX_CHARS=40
MIN_SPLIT_CHARS=30
```

目前程式碼在 `tts_split.py` 是：

```text
CHUNK_MAX_CHARS=60
MIN_SPLIT_CHARS=45
```

原因：太短的 chunk 會造成長句有明顯斷點；60 還低於約 80 字 tail-drop 風險。

如果開頭有 audio tag，會複製到每個 chunk：

```text
[curious] 第一段...
[curious] 第二段...
```

多 chunk 是 all-or-nothing：任一 chunk 失敗，整個 Gemini provider return None，走 edge/piper fallback。

## 6. Cache

cache key：

```text
text + voice + provider
```

不同 provider voice space 不同，所以 Gemini Despina 和 edge Xiaoxiao 不共用 cache。

cache hit 後會依 provider 的 `output_format` 解碼，避免 fallback 後用錯格式。

## 7. Go2 Megaphone DataChannel

TTS 播放到 Go2 時走：

```text
/webrtc_req -> rt/api/audiohub/request
```

DataChannel 流程：

```text
4001 ENTER_MEGAPHONE
4003 UPLOAD_MEGAPHONE x N chunks
4002 EXIT_MEGAPHONE
```

播放前會轉成：

```text
16kHz / 16bit / mono WAV
```

再做：

```text
+16 dB gain
base64 chunk size 4096
chunk interval 70ms
playback wait duration + tail
cooldown 0.5s
```

`EXIT 4002` 在 finally 裡保證送出。這很重要，否則 Go2 Megaphone 可能卡在 ENTER 狀態，後面變無聲。

## 8. /state/tts_playing

`tts_node` 在收到 `/tts` 後，合成前就 publish：

```text
/state/tts_playing = true
```

播完、EXIT、cooldown 後才：

```text
/state/tts_playing = false
```

這個 topic 同時被：

- `stt_intent_node` 用作 echo gate。
- `interaction_executive` 用作不要插嘴的 gate。
- Brain world state 也會看到。

## 9. 目前最可能的 TTS 問題

| 症狀 | 先查 |
| --- | --- |
| 有 `/tts` 但沒聲音 | `/webrtc_req` 是否有 4001/4003/4002 |
| 第一次 TTS 很慢 | Gemini / edge / piper cache cold start |
| 長句斷裂 | Gemini chunking / silence trim |
| 情緒 tag 沒效果 | fallback 到 edge/piper，tag 被 strip |
| PawAI 自己講話被 ASR 收到 | `/state/tts_playing` QoS 或 echo gate |
| Go2 後續都無聲 | tts_node mid-session 重啟或 EXIT 沒送，需重啟 Go2 driver/tts |

