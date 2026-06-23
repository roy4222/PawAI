# ASR / LLM / TTS 模型選擇路徑整理

> 🔬 **RESEARCH-ONLY — research-not-truth**。本檔整理選型路徑與淘汰原因，**不是**新實作規格、**不是**換現役 pass 模型的指令。語音三段現役主線見 `speech/README.md`；能不能講連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。索引見 [`README.md`](README.md)。
> 🏷️ **Tier**：`BASELINE_NOW`（語音三段為 6/18 主線；`voice.command` 現 pass 窄版、`voice.stop` 現 fail，以 baseline-evidence 為準）。

> Drafted: 2026-06-03  
> Purpose: 整理目前語音三段模型的採用路徑、測試結果、淘汰原因，供文件網站與既有淘汰模型資料合併。  
> Scope: ASR、LLM、TTS 三段互動語音管線。  

## 先讀這段

本文件整理的是「目前展示主線 + 歷史選型路徑」，不是新的實作規格。

專案文件裡有幾個不同時期的主線：

| 時期 | ASR | LLM | TTS |
|---|---|---|---|
| 2026-03-21 benchmark | Whisper small / tiny | 尚未進入新版 Brain A/B | Piper / edge-tts 比較 |
| 2026-03-24 Demo Ready | Whisper Small | Qwen2.5-7B cloud + Ollama 1.5B fallback | edge-tts + Piper fallback |
| 2026-05-04 Brain eval | 不變 | Gemini 3 Flash 主線，DeepSeek fallback | edge-tts / Piper |
| 2026-05-12 brain-freeze-v2 | SenseVoice cloud 主線 | `openai/gpt-5.4-mini` 主線，Gemini fallback | Gemini TTS quality lane + edge-tts/Piper fallback |

因此文件網站若要寫「目前最後為何使用這三個模型」，應以 **5/12 brain-freeze-v2** 和 `speech/README.md` 為主；3 月資料用來說明歷史比較與淘汰路徑。

## 最終採用摘要

| 模組 | 目前主線 | 備援 / fallback | 採用理由 |
|---|---|---|---|
| ASR | SenseVoice Cloud, FunASR on RTX 8000 | SenseVoice Local, sherpa-onnx int8 on Jetson CPU -> Whisper Local | 中文短句與 Go2 噪音環境準確率明顯高於 Whisper；local fallback 不占 GPU |
| LLM | `openai/gpt-5.4-mini` via OpenRouter | `google/gemini-3-flash-preview` -> RuleBrain | 8-model A/B 中速度、成本、自然度、JSON 穩定度綜合最佳 |
| TTS | Gemini 3.1 Flash TTS Preview, voice `Despina`, via OpenRouter quality lane | edge-tts fast lane -> Piper / local WAV fallback | Despina 中文自然度與 audio tag 表現最好；短句/安全句走 edge-tts 降延遲；Piper 保底離線 |

## 共通選型標準

1. 中文與繁體互動可用：優先處理中文短句、Demo 指令、繁中輸出。
2. 延遲可接受：使用者不應長時間等待機器狗回應。
3. Jetson 8GB 可共存：不得搶占物體辨識與視覺模組需要的 CPU/GPU/RAM。
4. Demo 可靠度：雲端模型可提升品質，但必須有本地或規則 fallback。
5. 格式穩定：LLM 必須穩定輸出 JSON 或至少不破壞後續管線。
6. 展示效果：TTS 音色與角色感比純速度更重要，但安全/短句要走快路徑。

---

## ASR 選擇路徑

### 需求

ASR 要把中文語音轉成文字，並支撐固定指令意圖分類。展示時需要：

- 中文短句辨識穩定。
- Go2 噪音環境下仍可用。
- `stop` 等安全指令不能大量漏辨。
- 雲端不可用時仍有降級路徑。

### 候選與結果

| 候選 | Runtime | 來源 / 模型資料 | 測試結果 | 決策 |
|---|---|---|---|---|
| SenseVoice Cloud | RTX 8000, FunASR, FastAPI server | FunAudioLLM SenseVoice: https://github.com/FunAudioLLM/SenseVoice | 25 筆 Go2 噪音 A/B：正確+部分 92%、Intent 96%、幻覺/亂碼 0、延遲約 600ms | 主線 |
| SenseVoice Local | Jetson CPU, sherpa-onnx int8 | local model: `~/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17/model.int8.onnx` | 25 筆 Go2 噪音 A/B：正確+部分 92%、Intent 92%、延遲約 400ms、離線可用 | 本地 fallback |
| Whisper Local | Jetson CUDA float16 through faster-whisper | faster-whisper: https://github.com/SYSTRAN/faster-whisper | 25 筆 Go2 噪音 A/B：正確+部分 52%、Intent 56%、幻覺/亂碼 8%、延遲約 3000ms | 最終保底，不當主線 |
| Whisper small | Jetson CUDA float16 | 同上 | 3/21 isolated benchmark：RTF 0.13，3s audio latency 約 390ms | 歷史主線；被 SenseVoice 取代 |
| Whisper tiny | Jetson CUDA float16 | 同上 | 3/21 isolated benchmark：RTF 0.03，3s audio latency 約 96ms；中文品質待驗 | 資源壓力候選，不當品質主線 |

### 關鍵轉折

早期 Whisper isolated benchmark 的速度是可用的，但真機 Go2 噪音環境暴露出準確率瓶頸。Noisy Profile v1 對 mic gain、VAD threshold、Whisper hallucination blacklist 做過調整，最佳仍只有約 64% 正確+部分，後續 SenseVoice A/B 到 92%，因此主線改為 SenseVoice。

目前 Demo 主線走 Studio push-to-talk，Gateway 直接呼叫 SenseVoice Cloud；舊的機身 USB 麥克風路徑保留在 `stt_intent_node`，但 Go2 風扇噪音使機身麥克風實測辨識率約 20%，不再作為展示入口。

### ASR 為何最後用 SenseVoice

SenseVoice Cloud / Local 在同一組 Go2 噪音環境測試下，準確率、intent 命中率、幻覺控制都明顯優於 Whisper。Local 版本用 CPU int8，不占 Jetson GPU，符合多模組共存需求。Whisper 因為中文短句與低 SNR 場景表現不足，改為最後備援。

---

## LLM 選擇路徑

### 需求

LLM 負責生成自然回覆與部分高階語意判斷，但不能直接繞過 Brain / Executive 控制機器狗。展示要求：

- 回覆要像 PawAI，不像客服模板。
- 速度要能支撐現場互動。
- JSON 或 schema 輸出不能常壞。
- 不能亂編不存在的 skill。
- 成本不能因 demo 多輪互動失控。

### 歷史路徑

#### 2026-03-24：Qwen 雲端 / 本地 fallback 基線

| 模型 | 部署 | 測試結果 | 決策 |
|---|---|---|---|
| Qwen2.5-7B-Instruct | vLLM on RTX 8000 | JSON parse 全通、中文穩定、LLM P50 約 1.5s | 當時雲端主線 |
| qwen2.5:1.5b | Ollama on Jetson | JSON 6/6，P50 約 2.3s，但 intent 映射有偏差 | 當時本地 fallback |
| qwen2.5:0.5b | Ollama on Jetson | JSON parse 2/8，中文漂移 | 淘汰 |

#### 2026-05-04：Gemini / DeepSeek / Qwen 線上 Brain eval

| 模型 | Avg latency | Skill score | 問題 | 決策 |
|---|---:|---:|---|---|
| `google/gemini-3-flash-preview` | 1.61s | 4.52 | 唯一穩定小於 2s | 當時線上主線 |
| `deepseek/deepseek-v4-flash` | 4.82s | 4.52 | reasoning 慢、length truncate | 當時 fallback 候選 |
| `qwen/qwen3.6-flash` | 14.33s | 4.92 | 太慢，max latency 有極端離群 | 離線/nightly 評估 |
| `qwen/qwen3.6-plus` | 22.89s sample avg | 未進主線 | 會必定 timeout | 淘汰線上主線 |

#### 2026-05-12：8-model demo-focused A/B

| 模型 | P50 | P95 | Cost / 12 calls | 觀察 | 決策 |
|---|---:|---:|---:|---|---|
| `openai/gpt-5.4-mini` | 1.16s | 2.74s | $0.018 | 速度、成本、自然度、JSON 穩定度綜合最佳 | 最終主線 |
| `google/gemini-3-flash-preview` | 1.89s | 3.10s | $0.040 | 便宜穩定，但較容易 rote / context 弱 | fallback |
| `anthropic/claude-opus-4.7` | 1.59s | 3.44s | $1.445 | 質量好，但成本約 gpt-mini 80x | 高品質離線稿，不上 live |
| `deepseek/deepseek-v4-flash` | 3.64s | 34.22s | $0.009 | reasoning 慢尾，demo 風險高 | 淘汰 |
| `anthropic/claude-haiku-4.5` | 1.51s | 2.73s | $0.090 | markdown fence 包 JSON | 淘汰 |
| `anthropic/claude-sonnet-4.6` | 2.93s | 7.59s | $0.268 | 慢、貴、沒有明顯勝出 | 淘汰 |
| `openai/gpt-5.4-nano` | 1.11s | 3.32s | $0.004 | 漏 audio tag，TTS 角色感受損 | 淘汰 |
| `openai/gpt-5.5` | 3.88s | 6.17s | $0.361 | 品質可用但太慢/太貴 | 離線文案產生 |

### LLM 為何最後用 `openai/gpt-5.4-mini`

8-model A/B 之後，`gpt-5.4-mini` 是唯一同時滿足速度、成本、格式穩定與角色自然度的模型。Opus 品質好但成本過高；Gemini 便宜穩定但自然度與 context awareness 較弱；DeepSeek/Sonnet/Haiku/Nano 各有 demo 殺手問題。

目前設計上，LLM 主要負責回覆文字與展示語氣，不應直接控制 motion/nav。安全與能力 gating 由 RuleBrain、Brain、Interaction Executive 與 capability scoreboard 決定。

---

## TTS 選擇路徑

### 需求

TTS 要把 LLM 或規則回覆變成語音。展示時需要：

- 中文自然，符合 PawAI 角色感。
- 安全/短句要快。
- 長句與情緒句要能表現 audio tag。
- 雲端 TTS 失敗時要能 fallback。
- 不搶 Jetson GPU，不增加大量 RAM。

### 2026-03-21：TTS 候選模型比較

| 候選 | 類型 | 測試 / 評估結果 | 決策 |
|---|---|---|---|
| edge-tts | Microsoft Edge Neural TTS client, online | P50 1.13s、P95 1.74s、成功率 10/10、音質 A、RAM 約 0 | 當時 cloud 主線 |
| Piper huayan | VITS / ONNX, local CPU | P50 2.03s、P95 2.14s、成功率 10/10、離線穩定 | 本地 fallback |
| Piper chaowen / xiao_ya | Piper new voices | Hugging Face voice files 已列 A/B 下載路徑，但未成主線 | 候選 A/B |
| MeloTTS | VITS / PyTorch | ARM64 mecab 風險、PyTorch 依賴、RAM 估 500-800MB、Jetson 無案例 | 待測後棄用 |
| Kokoro-82M | StyleTTS2 | 中文品質評級 D，英文好但不符合需求 | 不建議 benchmark |
| Spark-TTS-0.5B | LLM-based TTS | 模型約 3.95GB，Jetson 8GB 無法共存 | 排除 |
| XTTS v2 | GPT + VITS | 模型約 1.8GB，runtime 另需 2-3GB RAM | 排除 |
| ChatTTS | GPT-style | 需 4GB+ GPU VRAM，官方穩定性問題 | 排除 |
| Bark | GPT-style | 完整模型約 12GB VRAM，小模型也約 8GB | 排除 |
| F5-TTS | Diffusion Transformer | 需要 GPU，Jetson 無驗證，主要快在 L20 GPU | 排除 |

Piper voice source:

```text
https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/zh_CN-chaowen-medium.onnx
https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium/zh_CN-xiao_ya-medium.onnx
```

### 2026-05-05：Gemini TTS quality lane 決策

後續為了提升 PawAI 角色感，新增 OpenRouter TTS 候選實測。

| 候選 | Format | HTTP | 延遲 | 結果 |
|---|---|---:|---:|---|
| Gemini TTS `mp3` | mp3 | 400 | 1.15s | OpenRouter/Gemini TTS 只支援 `response_format="pcm"`，不可用 |
| Gemini TTS `pcm` | raw PCM | 200 | 4.75s | 可用，24kHz mono，需要自包 WAV header |
| OpenAI TTS `mp3` | mp3 | 200 | 2.17s | 可用，但未充分驗證 audio tag |

Voice A/B 後，`Gemini Despina` 中文自然度優於 `Gemini Achird` 與 `OpenAI alloy`。Gemini 對 `[excited]`、`[laughs]`、`[curious]` 等 audio tag 原生渲染較好，因此選為 quality lane。

### 2026-05-09：Dual-route routing

目前 TTS 不再只有一條路，而是依句子類型分流：

| 路徑 | 觸發條件 | Chain | 理由 |
|---|---|---|---|
| Fast lane | safety keyword、短句、無 emotional tag | edge-tts -> Piper | 首音小於約 2s，適合停止/警告/短句 |
| Quality lane | 有 emotional audio tag、長句、故事/角色感句子 | OpenRouter Gemini TTS -> edge-tts -> Piper | 音色與情緒表現較好 |
| Offline / failure | OpenRouter key 缺失或 provider 失敗 | edge-tts -> Piper 或 local WAV | demo-safe fallback |

### TTS 為何最後用 Gemini TTS + edge-tts/Piper

Gemini Despina 犧牲約 2.4 秒延遲，但中文音色與情緒標籤渲染明顯更適合 PawAI 展示。edge-tts 速度快、音質 A、資源成本低，因此保留為短句/安全句 fast lane。Piper 離線、CPU-only、RAM 小，是最後保底。

ElevenLabs 曾作為 quality lane spike 候選，但不是目前主線；MeloTTS、Spark-TTS、XTTS、ChatTTS、Bark、F5-TTS 主要因 Jetson 資源、安裝風險、穩定性或中文品質被淘汰。

---

## 給文件網站的簡版敘述

本系統最後採用「雲端品質 + 本地保底」的分層策略。ASR 主線使用 SenseVoice Cloud，因為它在 Go2 噪音環境下達到 92% 正確+部分辨識率與 96% intent 正確率，明顯優於 Whisper；雲端不可用時切到 Jetson CPU 上的 SenseVoice Local，最後才退回 Whisper。LLM 經過 8 個 OpenRouter 模型 A/B 測試後，選擇 `openai/gpt-5.4-mini` 作為主線，因為它在速度、成本、JSON 穩定度與 PawAI 角色自然度之間取得最佳平衡。TTS 則採雙路徑：長句與情緒句走 Gemini 3.1 Flash TTS Preview 的 Despina voice，以取得較好的角色音色與 audio tag 表現；短句與安全句走 edge-tts 降低延遲，失敗時再退到 Piper 或 local WAV 保底。

## 來源文件

- ASR / speech current truth: [`docs/pawai-brain/speech/README.md`](../speech/README.md)
- STT benchmark: [`docs/pawai-brain/speech/research/2026-03-21-stt-benchmark.md`](../speech/research/2026-03-21-stt-benchmark.md)
- STT raw benchmark: [`benchmarks/results/archive/stt/20260321/raw.jsonl`](../../../benchmarks/results/archive/stt/20260321/raw.jsonl)
- Speech pipeline report: [`docs/pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md`](../speech/research/2026-03-24-speech-pipeline-report.md)
- TTS benchmark: [`docs/pawai-brain/speech/research/2026-03-21-tts-benchmark.md`](../speech/research/2026-03-21-tts-benchmark.md)
- TTS rewrite result: [`docs/pawai-brain/specs/2026-05-05-tts-rewrite-result.md`](../specs/2026-05-05-tts-rewrite-result.md)
- LLM 5/04 eval: [`docs/pawai-brain/specs/2026-05-04-llm-eval-result.md`](../specs/2026-05-04-llm-eval-result.md)
- LLM 5/12 A/B eval: [`docs/archive/pawai-brain-legacy/dev-logs/2026-05-12-llm-naturalness-ab-eval.md`](../dev-logs/2026-05-12-llm-naturalness-ab-eval.md)
- LLM raw results round 1: [`tools/llm_eval/results/2026-05-12-demo-focused-ab.json`](../../../tools/llm_eval/results/2026-05-12-demo-focused-ab.json)
- LLM raw results round 2: [`tools/llm_eval/results/2026-05-12-demo-focused-ab-round2-small.json`](../../../tools/llm_eval/results/2026-05-12-demo-focused-ab-round2-small.json)
- Model candidate registry: [`docs/archive/pawai-brain-legacy/research/2026-06-02-model-candidate-registry.md`](2026-06-02-model-candidate-registry.md)
