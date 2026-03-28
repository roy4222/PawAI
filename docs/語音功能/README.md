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

## Noisy Profile v1（2026-03-28）

Go2 伺服噪音環境下的 ASR 參數調校結果。

**啟動方式：**
```bash
ENABLE_ACTIONS=false bash scripts/start_full_demo_tmux.sh
```

**參數（寫在 start_full_demo_tmux.sh 的 launch arg）：**
- `mic_gain=8.0`（預設，v1 甜蜜點。gain 10/12 測試過，噪音放大更嚴重）
- `energy_vad.start_threshold=0.02`（原 0.015，避免 Go2 噪音誤觸發）
- `energy_vad.stop_threshold=0.015`
- `energy_vad.silence_duration_ms=1000`
- `energy_vad.min_speech_ms=500`

**Whisper 改善（寫在 stt_intent_node.py）：**
- `vad_filter=True`（啟用 silero VAD，過濾非語音段）
- `no_speech_threshold=0.6`（拒絕低信心結果）
- `log_prob_threshold=-1.0`
- 幻覺黑名單 6→22 pattern + 短文字（< 2 字）過濾

**安全門：** `ENABLE_ACTIONS` 環境變數
- `true`（預設）：llm_bridge 和 event_action_bridge 正常發布 `/webrtc_req`
- `false`：兩條動作路徑都關閉，Go2 不會因垃圾 intent 做危險動作

**A/B 測試結果（固定音檔 controlled test）：**

| 組別 | gain | 正確+部分 | 備註 |
|:----:|:----:|:---------:|------|
| v1 | 8.0 | **64%** | 甜蜜點 |
| v2 | 10.0 | 43% | 觸發暴增但品質下降 |
| v5 | 12.0 | 62% | 無改善，出現幻覺 |

**結論：** Whisper Small 在中文短句+機器噪音場景已到上限，下一步評估替代 ASR（SenseVoice）。

## 已知問題

- **Whisper Small 中文短句辨識差**：「哈囉小狗」幾乎全錯，「拍一張照片」穩定正確。短句+噪音是模型極限
- USB 麥克風收音弱，需靠近（< 80cm）+ mic_gain 8.0
- USB device index 重開機後漂移 → 用 `source scripts/device_detect.sh`
- MeloTTS 和 ElevenLabs 已棄用（3/26 決議）

## 下一步

- **替代 ASR 研究**：SenseVoice（中文+噪音專精，比 Whisper 快）
- Sprint Day 4-5：整合進 executive v0
- system prompt 調整（intent 映射偏差）

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 語音 pipeline 分析報告 |
| archive/ | Jetson MVP 測試記錄（73K） |
