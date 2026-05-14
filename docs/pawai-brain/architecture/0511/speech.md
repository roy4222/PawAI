# 語音（speech_processor）

語音文件已拆到 [`speech/`](speech/) 目錄。這條線橫跨 USB mic、VAD、ASR、Brain、Executive、TTS provider chain、Go2 Megaphone，debug 時必須分段看。

- [speech/speech.md](speech/speech.md)：5/12 brain-freeze-v2 原始總覽與拆分索引。
- [speech/speech-runtime-flow.md](speech/speech-runtime-flow.md)：端到端 runtime 架構、topic、launch 邊界。
- [speech/speech-asr-vad.md](speech/speech-asr-vad.md)：mic、echo gate、energy VAD、ASR 三層 fallback。
- [speech/speech-tts-lanes-megaphone.md](speech/speech-tts-lanes-megaphone.md)：TTS dual-route、audio tag、provider chain、Go2 Megaphone。
- [speech/speech-brain-executive-integration.md](speech/speech-brain-executive-integration.md)：Speech event 如何進 Brain/Executive，以及 legacy bridge 風險。
- [speech/speech-debug-runbook.md](speech/speech-debug-runbook.md)：明天到學校現場 debug checklist。
