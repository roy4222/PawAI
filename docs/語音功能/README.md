# 語音互動系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + 5×RTX 8000

## 目標效果

- 人說話機器聽得懂，機器回話自然流暢
- **連續對話**（記得上下文）+ **上下文理解**（記得人名、地點、偏好）
- 可以執行任務導向的互動（不只是閒聊）

---

## 目前進度（2026-03-17 更新）

### E2E 已驗證通過

```
使用者說「你好」
  → stt_intent_node (Whisper Small CUDA, Energy VAD)
  → llm_bridge_node (Qwen3.5-9B, thinking mode off)
  → tts_node (Piper, +16dB gain)
  → Megaphone DataChannel (4001/4003/4002)
  → Go2 說話 + 揮手動作
  → echo gate 阻止 ASR 自激
```

**正式播放主線**：Megaphone DataChannel（不是 audio track）
**echo gate**：tts_playing(True) 在收到 /tts 時立刻開，cooldown 1s
**LLM**：Qwen3.5-9B，disable thinking，timeout 15s，max_tokens 300

### 快速驗證

```bash
# 一鍵啟動
bash scripts/start_llm_e2e_tmux.sh

# 5 輪 smoke test
bash scripts/smoke_test_e2e.sh 5

# 單句測試
ros2 topic pub --once /tts std_msgs/msg/String '{data: "你好，我是PawAI機器狗"}'
```

### 核心檔案

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/stt_intent_node.py` | ASR + Intent 分類（Energy VAD + faster-whisper + IntentClassifier） |
| `speech_processor/speech_processor/llm_bridge_node.py` | **新** — 取代 intent_tts_bridge_node，呼叫 Cloud LLM（Qwen3.5-9B） |
| `speech_processor/speech_processor/tts_node.py` | TTS 合成 + Go2 Megaphone DataChannel 播放 |
| `go2_robot_sdk/.../webrtc/tts_audio_track.py` | **新** — 自訂 AudioStreamTrack，WAV→48kHz resample→RTP/Opus |
| `speech_processor/speech_processor/intent_tts_bridge_node.py` | 舊版模板回覆（已被 llm_bridge_node 取代，保留作 fallback） |

### llm_bridge_node 架構

兩種觸發路徑：

**Path A（語音觸發）**：`/event/speech_intent_recognized` → 組裝 user message（含人臉 context）→ Cloud LLM → `/tts` + `/webrtc_req`

**Path B（人臉觸發）**：`/event/face_identity`（identity_stable + 具名）→ Cloud LLM → `/tts` + `/webrtc_req`（Go2 叫名字 + 揮手）

LLM 失敗時 fallback 到 RuleBrain（模板回覆）。`stop_move` 立即發動作，不等 TTS。

### Cloud LLM

- **模型**：Qwen3.5-9B on RTX 8000（140.136.155.5:8000，需 SSH tunnel）
- **API**：OpenAI-compatible（vLLM 原生）
- **延遲**：~2-3 秒（預熱後）
- **Spec**：`docs/superpowers/specs/2026-03-16-llm-integration-mini-spec.md`

### 啟動方式

```bash
# 先開 SSH tunnel 到 RTX 8000
ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5

# 啟動 llm_bridge_node（取代 intent_tts_bridge_node）
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_endpoint:="http://localhost:8000/v1/chat/completions"
```

---

## Go2 音訊播放（2026-03-17 更新）

### 主線方案：Megaphone DataChannel（已驗證可用）

Go2 透過 DataChannel 的 Megaphone API（4001/4003/4002）播放 TTS 音訊。

> **2026-03-17 修正**：之前判定「Megaphone 在 v1.1.7 失效」是錯誤結論。
> 失敗原因是 payload 格式不對（chunk size 錯、缺少欄位、DataChannel msg type 錯）。
> 對齊社群 [go2_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) 的格式後，確認可正常播放。

**播放流程**：
```
tts_node 生成 WAV（16kHz mono 16bit）
  → base64 encode → 4096-byte chunks
  → ENTER_MEGAPHONE(4001) → UPLOAD_MEGAPHONE(4003) × N → EXIT_MEGAPHONE(4002)
  → /webrtc_req topic → go2_driver_node → DataChannel → Go2 speaker
```

**Megaphone 協議格式**（4003 payload 必須包含）：
```json
{
  "current_block_size": 4096,
  "block_content": "<base64 chunk>",
  "current_block_index": 1,
  "total_block_number": 25
}
```

**關鍵實作細節**：
- chunk_size = **4096** base64 字元（不是 16384）
- DataChannel 訊息 type 必須是 `"req"`（不是 `"msg"`，audiohub 限定）
- chunks 之間間隔 **100ms**（對齊社群）
- WAV 格式：16kHz mono 16bit（由 `AudioProcessor.convert_to_wav()` 轉換）
- Debug WAV 自動存檔至 `/tmp/megaphone_debug_*.wav` 供離線分析

**啟動方式**：

```bash
# tts_node 預設使用 datachannel (Megaphone) 模式
ros2 run speech_processor tts_node --ros-args \
  -p provider:=piper \
  -p piper_model_path:=/home/jetson/models/piper/zh_CN-huayan-medium.onnx \
  -p playback_method:=datachannel

# 如需切到 WebRTC audio track 模式（實驗性，尚未在 Go2 上成功播放）
-p playback_method:=audio_track
```

### 備選方案：WebRTC Audio Track（研究分支）

WebRTC audio track (sendonly) 的 SDP negotiation、RTP 封包發送均正常，但 Go2 不播放收到的音訊。可能需要對齊社群的 `MediaPlayer` + `addTrack` 模式。暫不作為 demo 主線。

### 已知問題

- 音質待優化：16kHz 採樣率丟失高頻（社群用 44100Hz），音量偏小
- Echo loop：Go2 播放時 ASR 可能聽到自己的聲音，需調 echo gate
- Go2 OTA 自動更新可能改變行為 — 建議 Ethernet 直連鎖住韌體版本

### Postmortem：Megaphone「失效」誤判（2026-03-16 → 03-17）

**事件**：2026-03-16 判定 Go2 v1.1.7 不再支援 Megaphone API，全面切換至 WebRTC audio track。2026-03-17 經深度調查後推翻此結論。

**錯誤結論**：「Go2 韌體 v1.1.7 不再處理 Megaphone API（4001/4003/4002）」

**正確結論**：v1.1.7 仍支援 Megaphone，但對 payload 格式敏感。先前失敗的三個具體原因：
1. chunk_size 用 16384（應為 4096）
2. 4003 payload 缺少 `current_block_size` 欄位
3. DataChannel 訊息 type 用 `"msg"`（audiohub 要求 `"req"`）

**誤判過程**：送出格式不對的 4001/4003/4002 → Go2 silently ignore → `play_state` 永遠 `not_in_use` → 得出「API 被韌體砍掉」結論 → 花一天建 WebRTC audio track 替代方案

**修正過程**：
1. 發現社群 [go2_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) 有成功的 Megaphone 範例
2. 比對 payload 格式差異（chunk size、欄位、msg type）
3. 用 `test_megaphone_v2.py` 對齊社群格式後驗證成功

**排除的假根因**（調查並非白費）：
- DataChannel / ICE / DTLS / SCTP 均正常
- Go2 確實能接收音訊（不是硬體或韌體鎖死）
- WebRTC audio track 的 RTP 確實有送出（aiortc sender stats 確認），但 Go2 不播放（可能是 sender 細節與 Go2 預期不一致）

**教訓**：Go2 對音訊 API 的錯誤不回報（silent ignore），容易把「格式錯」誤判為「API 不支援」。未來遇到類似情況應先對照社群已驗證的實作。

---

## Jetson 麥克風注意事項

- **HyperX SoloCast（4P5P8AA）** 硬體只支援 **stereo（2ch）** 錄音
- `stt_intent_node` 必須用 `channels:=2`，callback 內手動取左聲道做 mono downmix
- 不要用 `channels:=1`，Jetson PortAudio ALSA backend 的 auto-downmix 會撞 `-9985` / `-9998`
- 驗證方式：`arecord -D hw:0,0 --dump-hw-params /dev/null 2>&1 | grep CHANNELS`

> 詳見 `docs/語音功能/jetson-MVP測試.md` §15.5

---

## 邊緣端 (Jetson 8GB) - 前端處理

### VAD (語音活動檢測)

| 方案 | 特點 | 延遲 |
|------|------|------|
| **WebRTC VAD** | 經典低負載 | sub-ms |
| **Silero VAD** | 輕量、快速、單 CPU 執行緒 | sub-ms |

**建議**：Silero VAD 適合常駐

### 喚醒詞 (Wake Word)

| 方案 | 特點 | 中文支援 |
|------|------|----------|
| **openWakeWord** | 預訓練模型、可訓練新詞 | 可訓練 |
| **Mycroft Precise** | 需收集樣本訓練 | 需自行訓練 |
| **Porcupine** | 純邊緣、資源占用極低 | 支援多喚醒詞 |

**現實**：中文喚醒詞開源資源較少，通常需自行訓練/調參

### 輕量 ASR (離線降級用)

**Whisper 模型選擇**：

| 模型 | 參數量 | VRAM | 延遲 | 適用 |
|------|--------|------|------|------|
| **tiny** | ~39M | ~1GB | 80-120ms | 喚醒詞、簡單指令 |
| **base** | ~74M | ~1GB | - | 日常對話 |
| **small** | ~244M | ~2GB | 300-500ms | 一般對話 |
| **medium** | ~769M | ~5GB | 1.2-2s | 複雜場景 |

**Jetson 8GB 建議**：tiny/base/small 較合理，medium 需看視覺負載

**加速方案**：
- **faster-whisper** (CTranslate2)：更高吞吐/更低延遲

---

## 邊緣 LLM 選項與限制

### 實測可行模型清單

| 模型 | 量化格式 | 記憶體占用 | 首 token 延遲 | 吞吐量 | 中文能力 | 推薦場景 |
|:---|:---|:---|:---|:---|:---|:---|
| **Qwen2.5-1.5B** | **INT4 (GGUF)** | **~1.2 GB** | **0.8-1.2 s** | **8-12 token/s** | **優秀** | **日常對話、家庭互動（推薦首選）** |
| Qwen2.5-0.5B | INT4 (GGUF) | ~0.6 GB | 0.3-0.5 s | 15-20 token/s | 良好 | 極簡指令、喚醒回應 |
| Qwen2.5-3B | INT4 (GGUF) | ~2.1 GB | 1.5-2.5 s | 5-8 token/s | 優秀 | 複雜推理、長回應 |
| Phi-3-mini-3.8B | INT4 (GGUF) | ~2.5 GB | 1.2-2.0 s | 6-10 token/s | 良好 | 推理任務、多語言 |
| TinyLlama-1.1B | INT8 (GGUF) | ~0.8 GB | 0.5-0.8 s | 15-20 token/s | 基礎 | 英文為主、快速反應 |

**實測環境**：Jetson Orin Nano 8GB，JetPack 5.1+，llama.cpp 推理引擎

### 推理框架比較

| 框架 | 適用模型格式 | Jetson 支援 | 易用性 | 效能 | 社群活躍度 |
|:---|:---|:---|:---|:---|:---|
| **llama.cpp** | **GGUF** | **優秀（CUDA/Metal）** | **中等** | **最佳** | **極高** |
| **Ollama** | 多種（自動轉換） | 良好 | **極佳** | 良好 | 高 |
| TensorRT-LLM | TensorRT engine | 官方支援 | 複雜 | 最佳（特定模型）| 中等 |
| ONNX Runtime | ONNX | 良好 | 中等 | 中等 | 高 |

**綜合建議**：
- 開發階段：使用 **Ollama** 快速驗證
- 生產部署：遷移至 **llama.cpp** 獲得更精細控制
- 追求極致效能：評估 **TensorRT-LLM**（需模型支援）

### 量化策略影響

| 量化格式 | 相對速度 | 相對記憶體 | 準確度損失 | 適用情境 |
|:---|:---|:---|:---|:---|
| FP16 (基準) | 1.0× | 1.0× | 0% | 開發調試 |
| INT8 | 1.5-2.0× | 0.5× | 2-5% | 平衡效能與品質 |
| **INT4 (GPTQ/AWQ)** | **2.5-4.0×** | **0.25×** | **5-15%** | **極致邊緣部署（推薦）** |

**llama.cpp 推薦格式**：Q4_K_M（K-quant，品質與速度平衡）

---

## 雲端端 (5×RTX 8000) - 核心推理

### 中文 ASR

| 方案 | 特點 | 延遲 (10秒語音) | 中文 WER | 推薦度 |
|:---|:---|:---|:---|:---|
| Whisper-tiny | 品質一般 | 1.5-2.5 s | 18-25% | ⭐⭐ |
| Whisper-base | 品質中等 | 3-5 s | 12-18% | ⭐⭐ |
| Faster-Whisper-small | 加速版 | 2-3 s | 10-15% | ⭐⭐⭐⭐ |
| **Qwen3-ASR-1.7B** | **中文專門優化** | **0.8-1.5 s** | **8-12%** | **⭐⭐⭐⭐⭐（推薦首選）** |
| NVIDIA Riva (ASR) | 企業級 | <1 s | 10-15% | 需授權 |

**推薦**：以中文互動為主的應用，**Qwen3-ASR 是首選方案**

### NLU/對話 LLM

**部署引擎**：
- **vLLM**：高吞吐、PagedAttention、支援量化 (GPTQ/AWQ)

**模型選擇**：

| 類型 | 延遲 | 品質 | 建議 |
|------|------|------|------|
| **70B 量化** | 較高 | 推理強 | 長對話一致性佳 |
| **34B 全精度** | 中等 | 細節好 | 需跨卡並行 |
| **較小模型** | 低 | 夠用 | 配合工具調用 |

**5×RTX 8000 分工建議**：

| 節點 | GPU 配置 | 部署模型 | 功能 |
|:---|:---|:---|:---|
| 節點 1-2 | 各 1×RTX 8000 | **Qwen2.5-72B-INT4** | 高品質對話 LLM |
| 節點 3 | 1×RTX 8000 | Qwen2.5-32B-INT8 + Qwen3-ASR-1.7B | 對話 + ASR 混合 |
| 節點 4-5 | 各 1×RTX 8000 | Qwen3-TTS-1.7B + 備援 LLM | TTS 服務 + 容錯 |

### TTS (文字轉語音)

| TTS 方案 | 模型大小 | 優化後延遲 (Jetson) | 記憶體占用 | MOS 音質 | 中文自然度 | 核心優勢 |
|:---|:---|:---|:---|:---|:---|:---|
| **Piper** | 50-200 MB | 0.2-0.5 s | ~300 MB | 3.0-3.5 | 可接受 | 極輕量、易部署 |
| **MeloTTS** | 300-800 MB | 0.4-0.8 s (TensorRT) | 0.8-1.2 GB | 3.8-4.2 | 良好 | 中文優化、語調自然 |
| **Qwen3-TTS-1.7B (INT4)** | ~3.2 GB | **1.3-1.7 s** | **2.1-3.2 GB** | **4.2-4.5** | **優秀** | **情感豐富、VoiceDesign** |
| **F5-TTS (TensorRT-LLM)** | ~2.5-3.5 GB | **0.04-0.08 s** | **2.5-3.5 GB** | **4.0-4.3** | 良好 | **延遲極低、流匹配架構** |
| XTTS-v2 | >1.5 GB | >3 s (推估) | >4 GB | 4.3-4.6 | 優秀 | 語音克隆（不適合邊緣）|

**選型建議**：
- 功能提示音：**Piper**（延遲最低）
- 日常對話：**MeloTTS**（中文自然度佳）
- 情感互動：**Qwen3-TTS**（支援 Voice Design）
- 極低延遲：**F5-TTS**（TensorRT-LLM 優化後）

---

## 多卡並行與故障切換

### 服務化部署

| 工具 | 用途 |
|------|------|
| **Triton Inference Server** | 通用模型伺服器、多框架後端、動態批次 |
| **vLLM** | LLM 專用引擎 |
| **Ray Serve** | Python 原生、多模型組合推理 |

### 避免顯存碎片化

**問題**：各自起 Python process → 權重重複載入 → 顯存切碎

**解法**：
- Triton 集中管理多模型
- vLLM 專用引擎
- Ray Serve 資源排程

### 故障切換

**Kubernetes + NVIDIA device plugin**：
- Deployment/Replica 形式
- 健康狀態檢查
- 自動重啟/換節點

---

## 對話深度與記憶

### 記憶層級

| 層級 | 範圍 | 技術 |
|------|------|------|
| **工作記憶** | 當前對話 | LLM context window |
| **短期記憶** | 今日對話 | 滑動窗口 + 摘要 |
| **長期記憶** | 歷史偏好 | 向量資料庫 (ChromaDB/Milvus) |
| **程式記憶** | 技能策略 | LoRA/微調 |

### 實體記憶

- 記得「人名、地點、物品位置」
- 向量資料庫儲存對話嵌入
- 語義檢索相關歷史

---

## 雲端優先 + 離線備援架構

### 三層架構

| 層級 | 功能 | 觸發條件 |
|------|------|----------|
| **第一層** | VAD + Wake Word + 固定指令 | 永遠可用 |
| **第二層** | Whisper tiny/base + 規則 NLU | 網路不穩 |
| **第三層** | 雲端 ASR/LLM/TTS | 網路恢復 |

### 網路偵測與自動切換

**多層次偵測機制**：

| 層級 | 檢測內容 | 頻率 | 失敗閾值 |
|:---|:---|:---|:---|
| 第一層：連線層 | ping 預設閘道器 | 5 秒 | 連續 3 次 |
| 第二層：DNS 層 | 解析公共 DNS | 10 秒 | 連續 2 次 |
| 第三層：服務層 | HTTP 健康檢查雲端 API | 30 秒 | 連續 2 次 |

**切換策略**：進入 OFFLINE 後，需**持續 30 秒穩定連線**才回切 ONLINE，防止震盪。

### 開源語音助手框架

| 專案 | 特點 |
|------|------|
| **Rhasspy** | Fully offline 語音助手 |
| **Open Voice OS** | Plugin 架構、可換 STT/TTS/Wake Word |
| **Home Assistant Voice** | 支援雲端與本地多種後端、可配置降級策略 |

**推薦參考**：Open Voice OS 的容器化架構與 K3s 編排方式

---

## 語音互動 UX

### 關鍵延遲預算

| 階段 | 目標延遲 |
|------|----------|
| 語音喚醒 | <200ms |
| ASR | 200-500ms |
| LLM 規劃 | 500-1500ms |
| TTS | 200-500ms |
| **總計** | **<2s** |

### 打斷處理

- 人說話時機器人正在說
- 如何優雅切換？
- 常見：VAD 檢測到新語音 → 暫停 TTS → 切換聆聽模式

---

## 30 輪驗收工具（2026-03-14 新增）

Phase 1-4 各自通過後，需要端到端可重複驗證。以下工具用於 30 輪統計測試。

### 檔案索引

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/speech_test_observer.py` | Observer node：訂閱 topic、聚合 RoundRecord、輸出 CSV/JSON |
| `speech_processor/test/test_speech_test_observer.py` | 單元測試（20 tests） |
| `test_scripts/speech_30round.yaml` | 測試定義（15 固定句 + 15 自由句） |
| `scripts/clean_speech_env.sh` | 環境清理（kill tmux sessions + speech nodes） |
| `scripts/run_speech_test.sh` | 一鍵 orchestration（clean → build → launch → observe → report） |

### 快速使用

```bash
# 完整流程（含 build + driver 啟動）
bash scripts/run_speech_test.sh

# 跳過 build，假設 driver 已在跑
bash scripts/run_speech_test.sh --skip-driver --skip-build

# 指定不同 YAML
bash scripts/run_speech_test.sh --yaml=test_scripts/custom.yaml
```

### 輸出

- `test_results/speech_test_YYYYMMDD_HHMMSS.csv` — 逐輪原始紀錄
- `test_results/speech_test_YYYYMMDD_HHMMSS_summary.json` — 摘要統計 + PASS/MARGINAL/FAIL 評分

### 通過門檻（來源：jetson-MVP 測試手冊 §14.1）

| 指標 | 門檻 |
|------|------|
| Fixed round 命中率 | ≥ 80% |
| E2E 中位數延遲 | ≤ 3500ms |
| E2E 最差延遲 | ≤ 6000ms |
| Go2 播放成功率 | ≥ 80% |

> 詳細設計見 `docs/superpowers/specs/2026-03-14-speech-30round-validation-design.md`

---

## 參考資源

- [Whisper](https://github.com/openai/whisper)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [WeNet](https://github.com/wenet-e2e/wenet)
- [FunASR](https://github.com/alibaba-damo-academy/FunASR)
- [vLLM](https://github.com/vllm-project/vllm)
- [MeloTTS](https://github.com/myshell-ai/MeloTTS)
- [StyleTTS2](https://github.com/yl4579/StyleTTS2)
- [Bark](https://github.com/suno-ai/bark)
- [openWakeWord](https://github.com/dscripka/openWakeWord)
- [Silero VAD](https://github.com/snakers4/silero-vad)
- [Qwen3-ASR](https://github.com/QwenLM/Qwen3-ASR)
- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [F5-TTS](https://github.com/SWivid/F5-TTS)
