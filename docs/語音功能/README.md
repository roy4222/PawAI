# 語音互動系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + 5×RTX 8000

## 目標效果

- 人說話機器聽得懂，機器回話自然流暢
- **連續對話**（記得上下文）+ **上下文理解**（記得人名、地點、偏好）
- 可以執行任務導向的互動（不只是閒聊）

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

## 雲端端 (5×RTX 8000) - 核心推理

### 中文 ASR

| 方案 | 特點 | VRAM |
|------|------|------|
| **Whisper large-v3** | 品質高、泛化強、multilingual | ~10GB |
| **WeNet** | production-ready、中文社群常用 | 中等 |
| **FunASR** | 工具箱化、Paraformer 高效率 | 中等 |

**容量評估**：單卡 48GB 可跑多路 Whisper large 並行

### NLU/對話 LLM

**部署引擎**：
- **vLLM**：高吞吐、PagedAttention、支援量化 (GPTQ/AWQ)

**模型選擇**：

| 類型 | 延遲 | 品質 | 建議 |
|------|------|------|------|
| **70B 量化** | 較高 | 推理強 | 長對話一致性佳 |
| **34B 全精度** | 中等 | 細節好 | 需跨卡並行 |
| **較小模型** | 低 | 夠用 | 配合工具調用 |

**建議**：1-2 張卡固定給 NLU，其餘給 ASR/TTS/視覺

### TTS (文字轉語音)

| 方案 | 特點 | 中文 | 情感 |
|------|------|------|------|
| **MeloTTS** | 工程落地、MIT 授權 | ✅ 中英混讀 | 基礎 |
| **StyleTTS2** | 風格 diffusion、接近 human-level | 需微調 | ✅ 可控 |
| **Bark** | 多語言、非語言聲音 (笑聲/嘆氣) | ✅ | ✅ 互動感強 |

**48GB 策略**：充足顯存做 batch 與低延遲，而非塞超大模型

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

## 斷網降級策略

### 三層架構

| 層級 | 功能 | 觸發條件 |
|------|------|----------|
| **第一層** | VAD + Wake Word + 固定指令 | 永遠可用 |
| **第二層** | Whisper tiny/base + 規則 NLU | 網路不穩 |
| **第三層** | 雲端 ASR/LLM/TTS | 網路恢復 |

### 開源語音助手框架

| 專案 | 特點 |
|------|------|
| **Rhasspy** | Fully offline 語音助手 |
| **Open Voice OS** | Plugin 架構、可換 STT/TTS/Wake Word |

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
