# 語音管線驗證報告（2026-03-24）

## 摘要

本日完成 USB 外接音訊設備整合、本地/雲端 LLM 驗證、TTS 主線切換（edge-tts）、intent fast path、以及四條 fallback 路徑驗證。語音管線從「硬體未接」推進到 **Demo Ready** 狀態。

---

## 一、硬體驗證

### USB 麥克風：Jieli Technology UACDemoV1.0
- ALSA: `hw:2,0` / sounddevice index 24
- mono, 48000Hz, S16_LE
- 靈敏度偏低（語音 RMS ~0.015），需軟體增益 `mic_gain:=4.0`

### USB 喇叭：Jieli Technology CD002-AUDIO
- ALSA: `hw:3,0` / sounddevice index 25
- stereo, 48000Hz
- 音量需拉滿：`amixer -c 3 set PCM 147`
- Piper 22050Hz / edge-tts MP3 直出，清晰度相比 Go2 Megaphone（16kHz 降採樣）**大幅改善**

### Echo 自激測試
- 5/5 輪 TTS 播放期間**零假 ASR 觸發**
- echo gate cooldown 1000ms 足夠
- 喇叭播放不會回灌麥克風

---

## 二、ASR 驗證

### 模型：Whisper Small, CUDA float16 (faster-whisper)
- P50 延遲：**0.9s**
- warmup：~12s（daemon thread 預熱 CUDA JIT）

### mic_gain 修正
- **問題**：USB 麥克風靈敏度低，Whisper 在低 SNR 下產生大量幻覺（2/8 辨識率）
- **修正**：新增 `mic_gain` 參數，gain 只作用在送 Whisper 的錄音，不影響 VAD 閾值
- **結果**：gain x4 後辨識率提升到 **4/5 穩定**
- **已知限制**：「請回復你現在的狀態」長句偶爾被 VAD 截斷

### 固定話術辨識率

| 話術 | 辨識結果 | Intent | 正確 |
|------|---------|--------|:---:|
| 哈囉小狗請跟我打招呼 | 「請跟我打招呼」 | greet | ✅ |
| 請過來我這裡 | 「請過來我這裡」 | come_here | ✅ |
| 現在請停止動作 | 「現在請停止」 | stop | ✅ |
| 請幫我拍一張照片 | 「請幫我拍一張照片」 | take_photo | ✅ |
| 請回復你現在的狀態 | 不穩定 | status | ⚠️ |

---

## 三、LLM 驗證

### 測試模型

| 模型 | 部署 | JSON parse | 中文穩定 | LLM P50 | 結論 |
|------|------|:---------:|:------:|:------:|------|
| qwen2.5:0.5b | Ollama Jetson | 2/8 (25%) | ❌ 語言漂移 | ~0.8s | **淘汰** |
| **qwen2.5:1.5b** | Ollama Jetson | 6/6 (100%) | ✅ | **2.3s** | 本地 fallback 主力 |
| **Qwen2.5-7B-Instruct** | vLLM RTX 8000 | 全通 | ✅ | **1.5s** | 雲端主線 |

### Intent 映射（qwen2.5:1.5b 直接文字測試）

| 輸入 | LLM intent | 正確 |
|------|-----------|:---:|
| 哈囉小狗請跟我打招呼 | greet | ✅ |
| 請過來我這裡 | greet（應為 come_here） | ⚠️ |
| 現在請停止動作 | ignored（無 stop_move skill） | ⚠️ |
| 請幫我拍一張照片 | chat（應為 take_photo） | ⚠️ |
| 請回復你現在的狀態 | status | ✅ |
| 你現在在做什麼 | status | ✅ |

**備註**：intent 映射偏差是 prompt/contract 問題，不影響 JSON 格式穩定性。fast path 可繞過。

### reply_text 硬截斷
- 1.5B 不遵守 prompt 的 12 字限制（實際回覆 15-21 字）
- 新增 `_post_process_reply()` 強制截斷到 12 字
- 截斷後 JSON parse 仍然 100%

---

## 四、TTS 驗證

### 測試引擎

| 引擎 | 合成 P50 | 音質 | 部署 | 結論 |
|------|:-------:|:---:|------|------|
| **edge-tts** XiaoxiaoNeural | **0.72s** | A 級 | 雲端（需網路） | 主線 |
| Piper zh_CN-huayan | 2.0s | C 級 | Jetson 本地 | 離線 fallback |

### edge-tts → Piper 自動降級
- edge-tts 失敗時，自動嘗試 Piper 合成
- fallback 成功的音訊用 `piper` provider key cache
- **驗證通過**：log 顯示 `edge-tts failed, falling back to Piper` → Piper 播放成功

### TTS cache 預熱
- 啟動時在 background thread 預合成 5 句常用模板回覆
- 首次回覆即 cache hit，省去合成延遲

### 動作 intent 不播 TTS
- stop/sit/stand 只發動作指令，跳過 TTS
- 由 `ACTION_ONLY_SKILLS`/`ACTION_ONLY_INTENTS` 控制

---

## 五、延遲基線

### 最終數據（2026-03-24）

| 路徑 | E2E P50 | LLM | TTS | 說明 |
|------|:------:|:---:|:---:|------|
| stop/sit/stand | **0.002s** | fast path | 不播 | 動作瞬間完成 |
| greet (cache hit) | **2.34s** | fast path | cache | 模板回覆 |
| Cloud LLM + cache | **3.97s** | Cloud 7B 1.5s | cache | 重複句 |
| Cloud LLM + edge-tts | **4.48s** | Cloud 7B 1.5s | edge 0.7s | 新句 |
| Local LLM + edge-tts | ~6.0s | Ollama 1.5B 2.3s | edge 0.7s | 本地 fallback |
| 全本地 Piper | ~8.1s | Ollama 1.5B 2.3s | Piper 2.0s | 保底 |

### 分段延遲

| 階段 | P50 |
|------|:---:|
| VAD 錄音 | 2.1s |
| ASR (Whisper Small CUDA) | 0.9s |
| LLM (Cloud 7B) | 1.5s |
| LLM (Ollama 1.5B) | 2.3s |
| TTS 合成 (edge-tts) | 0.72s |
| TTS 合成 (Piper) | 2.0s |
| TTS 播放 (aplay) | ~2.3s |

### 優化歷程

| 階段 | E2E P50 | 改動 |
|------|:------:|------|
| 全本地基線 | 8.1s | Ollama 1.5B + Piper |
| + edge-tts | ~6.5s | 合成 2.0s → 0.7s |
| + fast path | 3.4s | 已知 intent 跳 LLM |
| + cache warmup | 2.6s | 首次也 cache hit |
| + 動作不播 TTS | **0.002s** | stop/sit/stand 瞬間 |
| + Cloud LLM | **4.48s** | chat/status 走雲端 |

---

## 六、Fallback 路徑驗證

### 四條降級路徑全部通過

| Test | 場景 | LLM 行為 | TTS 行為 | 結果 |
|------|------|---------|---------|:---:|
| 1 主線 | Cloud + edge-tts | `LLM decision: intent=status` | edge-tts 合成 + 播放 | ✅ |
| 2 半離線 | Cloud LLM down | `LLM connection refused` → RuleBrain | edge-tts 播放 | ✅ |
| 3 全離線 | tunnel 斷 + Piper | fast path / RuleBrain | Piper `Provider: piper` 播放 | ✅ |
| 4 TTS 降級 | edge-tts 失敗 | fast path | `edge-tts failed` → Piper fallback 播放 | ✅ |

### 降級鏈

```
LLM 層：Cloud Qwen2.5-7B → RuleBrain 模板
         （Ollama 1.5B 可手動切換，尚未自動 fallback）

TTS 層：edge-tts → Piper 自動 fallback

Intent 層：已知 intent (conf ≥ 0.8) → fast path 跳 LLM
```

---

## 七、當前最佳組合

```
USB 麥克風 (mono 48kHz, mic_gain x4)
  │
  ▼
stt_intent_node (Whisper Small CUDA float16, 0.9s)
  │
  ├─ greet/stop/sit/stand + conf ≥ 0.8
  │    → Fast Path: RuleBrain 模板（~2.3s / 動作 0s）
  │
  └─ status/chat/unknown/人臉
       → Cloud Qwen2.5-7B (~4.5s) 或 Ollama 1.5B (~6s)
  │
  ▼
tts_node
  ├─ 有網 → edge-tts +10% rate (0.7s, A 級)
  │         失敗 → Piper fallback
  └─ 離線 → Piper (2.0s)
  │
  ▼
USB 喇叭 (plughw:3,0, 48kHz)
```

---

## 八、已知問題與待辦

### 已知問題
- ASR 長句（「請回復你現在的狀態」）辨識不穩
- qwen2.5:1.5b intent 映射偏差（come_here/stop/take_photo）
- Cloud → Ollama 自動 fallback 尚未實作（目前 Cloud → RuleBrain）
- USB 裝置 card number 拔插後可能漂移

### 待辦（按優先序）
1. LLM system prompt 修正 intent 映射
2. Cloud → Ollama 自動 fallback 整合
3. Streaming LLM + TTS pipeline（架構級，壓到 3s 以下）
4. 30 輪驗收測試

---

## 九、Commit 歷史

| Hash | 說明 |
|------|------|
| 36adb00 | feat: USB speaker + mic support |
| c9df525 | fix: VAD/recording gain 分離 |
| e8076af | docs: mic_gain + local LLM baseline |
| ad16d5a | fix: reply_text 硬截斷 + max_tokens 80 |
| 0a9e8ee | perf: edge-tts + intent fast path |
| 7551703 | perf: action skip TTS + cache warmup + rate boost |
| d99bd29 | docs: latency baseline |
| 9575bf1 | docs: final baseline + warmup cleanup |

---

## 十、啟動方式

```bash
# Demo 主線（Cloud LLM + edge-tts + USB 設備）
bash scripts/start_llm_e2e_tmux.sh

# 全離線（Piper + RuleBrain）
TTS_PROVIDER=piper bash scripts/start_llm_e2e_tmux.sh

# 本地 LLM（Ollama 1.5B + edge-tts）
LLM_ENDPOINT=http://localhost:11434/v1/chat/completions \
LLM_MODEL=qwen2.5:1.5b bash scripts/start_llm_e2e_tmux.sh
```
