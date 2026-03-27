# 語音互動系統

> Status: current

> 中文語音對話：聽懂 → 理解意圖 → LLM 回應 → 說出來。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | Demo ready |
| 版本/決策 | Whisper small (CUDA) + edge-tts + Cloud Qwen2.5-7B |
| 完成度 | 80% |
| 最後驗證 | 2026-03-25 |
| 入口檔案 | `speech_processor/speech_processor/stt_intent_node.py` |
| 測試 | `python3 -m pytest speech_processor/test/ -v` |

## 啟動方式

```bash
# 一鍵啟動（推薦）
bash scripts/start_llm_e2e_tmux.sh

# 全離線模式
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh
```

## 核心流程

```
USB 麥克風 (UACDemoV1.0, 48kHz mono)
    |
stt_intent_node（Energy VAD -> Whisper small CUDA float16 -> Intent 分類）
    | /event/speech_intent_recognized
llm_bridge_node（Cloud Qwen2.5-7B -> Ollama 1.5B -> RuleBrain 三級 fallback）
    | /tts
tts_node（edge-tts 雲端主線 / Piper 本地 fallback）
    |
USB 喇叭 local playback（Megaphone DataChannel 備用）
    |
echo gate 阻止 ASR 自激（total 1.5s）
```

**Intent fast path**：stop/greet 等高頻 intent 跳過 LLM，直接 RuleBrain（~0ms）。
**LLM timeout > 2s** 自動 fallback。

## 輸入/輸出

| Topic | 方向 | 說明 |
|-------|:----:|------|
| `/event/speech_intent_recognized` | 輸出 | Intent 事件 JSON |
| `/state/interaction/speech` | 輸出 | 語音管線狀態 5Hz |
| `/state/tts_playing` | 輸出 | TTS 播放中 flag |
| `/tts` | 輸入 | 要說的文字 |
| `/asr_result` | 輸出 | 原始 ASR 文字 |

## 已知問題

- VAD 斷句延遲 2-10s 是最大瓶頸（不是 LLM）
- USB 麥克風收音弱，需靠近或加 mic_gain
- Whisper 幻覺：靜音/噪音被誤解為假文字
- USB device index 重開機後可能漂移
- MeloTTS 和 ElevenLabs 已棄用（3/26 決議）

## 下一步

- Sprint B-prime Day 1：baseline 穩定化
- Sprint Day 4-5：整合進 executive v0
- system prompt 調整（intent 映射偏差）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 語音 pipeline 分析報告 |
| archive/ | Jetson MVP 測試記錄（73K） |
