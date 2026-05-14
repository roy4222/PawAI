# TTS 模型選型調查

> 最後更新：2026-03-21

## 目標效果
- 在 Jetson Orin Nano 8GB 上即時合成中文語音（25 字以內回覆）
- 首句延遲 < 2s（含合成 + 播放啟動），目前 Piper 新句子 ~2.4s
- 音質自然、清晰，適合陪伴型互動
- 支援外接 USB 喇叭（22050Hz+ 原生播放）與 Go2 Megaphone fallback（16kHz）
- 與 ASR（Whisper Small）、人臉（YuNet）、姿勢（RTMPose）共存，總 RAM < 7GB

## 系統約束
- **Jetson Orin Nano 8GB**：統一記憶體，GPU 已被 RTMPose 佔 91-99%
- **當前 GPU 剩餘**：接近 0%（RTMPose balanced mode 滿載）
- **RAM 預算**：已用 ~5.0GB（D435+YuNet+ASR+ROS2），餘 ~2.6GB
- **TTS RAM 增量目標**：< 500MB（理想），< 1GB（可接受）
- **播放路徑**：USB 喇叭（`playback_method=local`）或 Megaphone DataChannel（16kHz）
- **回覆長度**：LLM 限制 25 字（max_tokens 120 JSON），典型 15-25 字

---

## 候選模型總覽

### 比較表

| # | 模型 | 類型 | 中文支援 | 原生取樣率 | 模型大小 | RAM 增量(估) | GPU 需求 | 首句延遲(估) | Jetson ARM64 | 現況 |
|---|------|------|:-------:|:---------:|:-------:|:-----------:|:-------:|:-----------:|:------------:|------|
| 1 | **Piper** (huayan-medium) | VITS/ONNX | zh_CN 1聲 | 22050 Hz | 63 MB | ~200 MB | CPU-only(可選CUDA) | ~2.4s (實測) | **已驗證** | 現行主線 |
| 2 | **MeloTTS** | VITS | zh_CN+EN混合 | 44100 Hz | ~200 MB | ~800 MB | CPU 可即時; CUDA 更快 | ~1.5-3s (估) | 未驗證(風險中) | 已整合未測 |
| 3 | **edge-tts** | 雲端(MS Edge) | zh-CN/zh-TW 多聲 | 48000 Hz(MP3) | 0 MB | ~50 MB | 不需要 | ~0.3-0.8s (估) | **相容**(純Python) | 未整合 |
| 4 | **Kokoro-82M** | StyleTTS2 | zh 8聲(品質D) | 24000 Hz | 327 MB(PTH) | ~600-800 MB | 需要GPU | ~1-2s (估) | 部分(有容器) | 未整合 |
| 5 | **Spark-TTS-0.5B** | LLM-based | 中英雙語 | 未知 | 3.95 GB | >3 GB | 需要GPU | >5s (估) | 有容器(RAM不足) | **排除** |
| 6 | **XTTS v2** (Coqui) | GPT+VITS | 16語言含中 | 24000 Hz | ~1.8 GB | ~2-3 GB | 需要GPU | <0.2s(串流) | 有容器(RAM不足) | **排除** |
| 7 | **ChatTTS** | GPT-style | 中英 | 24000 Hz | 未知 | >4 GB GPU | 需要GPU | RTF~0.3 | 未驗證 | **排除** |
| 8 | **Bark** | GPT-style | zh | 24000 Hz | ~5 GB | >8 GB | 需要GPU | >10s | 不可行 | **排除** |
| 9 | **F5-TTS** | DiT | 中文(資料集) | 未知 | 未知 | 未知 | 需要GPU | RTF 0.04(L20) | 未驗證 | **排除** |
| 10 | **Piper** (chaowen/xiao_ya) | VITS/ONNX | zh_CN | 22050 Hz | ~63 MB | ~200 MB | CPU-only | ~2.4s (估) | **已驗證** | 待A/B測試 |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| Spark-TTS-0.5B | 模型 3.95GB，Jetson 8GB 不可能與其他模型共存 | verified |
| XTTS v2 | 模型 ~1.8GB + runtime ~2-3GB RAM，超出預算；Jetson 容器 7.5GB | verified |
| ChatTTS | 需 4GB+ GPU VRAM，30s 音訊需 4GB GPU。穩定性差（官方承認） | community_only |
| Bark | 完整模型需 12GB VRAM（小模型 8GB），遠超 Jetson 預算 | verified |
| F5-TTS | 需 GPU，Jetson 上無驗證案例，依賴 TensorRT-LLM 才快 | community_only |

---

## 候選模型詳細分析

### 1. Piper TTS（現行主線）

**狀態**：已驗證，穩定運行

**架構**：VITS（Variational Inference TTS），ONNX 格式推理
- CPU 推理（預設），也支援 CUDA
- CLI 模式：`piper` 二進位，接收 stdin 文字，輸出 WAV

**中文聲音**（全部 zh_CN，均 ~63MB ONNX）：
| 聲音 | 品質等級 | 備註 |
|------|---------|------|
| huayan | x_low, **medium** | 現行使用 medium |
| chaowen | medium | **新增**，2個月前上傳，待A/B比較 |
| xiao_ya | medium | **新增**，2個月前上傳，待A/B比較 |

**已知問題**：
- 原生 22050Hz → Megaphone 16kHz 降採樣造成品質損失（USB 喇叭可繞過）
- 中文自然度一般（開源 VITS 限制）
- 專案已 archived（2025-10-06），新版 piper1-gpl 由 OHF 維護但缺人手
- 只有 CPU 推理被廣泛測試，CUDA 模式在 Jetson 上未確認穩定性

**優勢**：
- 極低 RAM（~200MB 增量）
- 純 CPU 不搶 GPU
- ONNX 格式，部署簡單
- 已有 cache 機制（重複句子 0ms）
- `tts_node.py` 已整合

**Jetson 實測數據**：
- 新句子（25 字）：~2.4s
- Cache hit：~0ms
- RAM 增量：~200MB

---

### 2. MeloTTS

**狀態**：程式碼已整合（`TTSProvider_MeloTTS` 在 `tts_node.py`），但 Jetson 上未實測

**架構**：VITS（SynthesizerTrn），PyTorch 推理
- 支援 CPU / CUDA / MPS
- 官方聲稱 "CPU real-time inference"
- 原生 **44100 Hz** 輸出（比 Piper 高一倍）

**中文支援**：
- zh_CN + EN 混合語句
- 256 speaker 支援（但中文只有有限 speaker ID）

**依賴風險**：
- 需要 PyTorch + torchaudio（Jetson 已有）
- 需要 mecab-python3（ARM64 有 wheel 衝突問題，issue #121 未解）
- 需要 librosa, pypinyin, jieba, cn2an 等中文處理庫
- transformers==4.27.4（版本鎖定，可能與其他模組衝突）

**RAM 估計**：
- PyTorch model（~200MB 模型 + PyTorch runtime overhead）
- 估計增量 ~600-800MB（含 PyTorch CUDA context if GPU）
- CPU-only 可能 ~400-500MB

**風險**：
- ARM64 mecab 安裝問題（已知 unresolved issue）
- CPU 推理速度未知（"real-time" 可能指 x86）
- 44100Hz 對 16kHz Megaphone 降採樣比 Piper 的 22050Hz 更多（但 USB 喇叭受益）
- 無 ONNX 版本（PR #276 進行中但未合併）
- 無社群 Jetson 部署案例

**音質預期**：
- 44100Hz 原生取樣率比 Piper 22050Hz 高，理論上更清晰
- VITS 架構相近，差異主要在訓練資料和 vocoder 品質
- 中英混合能力是加分項（LLM 回覆偶有英文詞）

---

### 3. edge-tts（Microsoft Edge 雲端 TTS）

**狀態**：未整合，但技術上最簡單

**架構**：雲端 API（利用 Microsoft Edge 免費 TTS 服務）
- 純 Python，`pip install edge-tts`
- 不需 GPU、不需模型檔案
- 輸出 MP3 格式

**中文聲音**（Microsoft Neural Voices，免費，高品質）：
| 聲音 | 性別 | 特色 |
|------|------|------|
| zh-CN-XiaoxiaoNeural | 女 | 最自然，多場景 |
| zh-CN-YunxiNeural | 男 | 敘述風格 |
| zh-CN-XiaoyiNeural | 女 | 溫暖親切 |
| zh-CN-YunjianNeural | 男 | 運動風格 |
| zh-TW-HsiaoChenNeural | 女 | **繁體中文** |
| zh-TW-YunJheNeural | 男 | **繁體中文** |
| ...還有多個 | | |

**優勢**：
- **音質最佳**：Microsoft Neural TTS 是業界頂級
- **RAM 幾乎為零**：純網路請求
- **延遲低**：估計 0.3-0.8s（含網路往返）
- **繁體中文支援**：唯一有 zh-TW 的選項
- 部署極簡，ARM64 無障礙
- 支援語速/音高/音量調整

**風險**：
- **需要網路**：離線不可用（Go2 Ethernet 模式無外網）
- **服務穩定性**：已有 "No audio received" 的 issue 報告（#443, #432, #447）
- **速率限制**：未明確記載，但 Microsoft 可能封鎖大量請求
- **SSML 限制**：不支援自訂 SSML
- **SSL 連線延遲**：每次連線多 ~250ms（issue #465）
- **不是正式 API**：利用 Edge 瀏覽器的免費端點，隨時可能被封

**整合方式**：
```python
# 新增 TTSProvider_EdgeTTS 類別
import edge_tts
import asyncio

async def synthesize(text, voice="zh-CN-XiaoxiaoNeural"):
    communicate = edge_tts.Communicate(text, voice)
    audio_data = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data += chunk["data"]
    return audio_data
```

**適用場景**：
- 展示/Demo 時接 Wi-Fi（音質加分）
- 作為 Piper 的 cloud fallback（類似 LLM 的雲端+本地策略）
- 搭配 Piper 離線 fallback = 最佳組合

---

### 4. Kokoro-82M

**狀態**：未整合，Jetson 容器存在但未測試

**架構**：StyleTTS2，82M 參數
- 支援 ONNX（非官方，kokoro-onnx ~300MB，量化 ~80MB）
- 需要 PyTorch + espeak-ng + misaki[zh]

**中文聲音品質**：
- 8 個中文聲音（4 女 4 男）
- **全部評級 D**（訓練時數 "MM" = 10-100 分鐘）
- Target quality: C，Overall grade: D
- **中文品質明確不足**，不推薦用於中文專案

**其他問題**：
- ONNX 導出有已知問題（RuntimeError, 性能下降）
- 24000Hz 輸出（對 USB 喇叭好，但 16kHz 降採樣比 22050Hz 更多）
- 327MB PTH + voice files，RAM 增量估計 600-800MB

**結論**：中文品質 D 級，**不建議 benchmark**。英文很好但不是我們的需求。

---

### 5-8. 已排除模型

| 模型 | 核心排除原因 |
|------|------------|
| **Spark-TTS-0.5B** | 3.95GB 模型，0.5B 參數 LLM-based，Jetson 上無法與其他模型共存 |
| **XTTS v2** | ~1.8GB 模型 + 2-3GB runtime，Jetson 容器 7.5GB 已說明重量級。串流 <200ms 很好但吃太多 RAM |
| **ChatTTS** | 需 4GB GPU VRAM，官方承認穩定性差，多說話人和音質問題 |
| **Bark** | 12GB VRAM（小模型 8GB），完全超出 Jetson 預算。速度也慢 |
| **F5-TTS** | Diffusion Transformer，需 GPU，RTF 0.04 很快但只在 L20 GPU 上。Jetson 無驗證 |

---

## Piper 中文新聲音 A/B 測試計畫

Piper 新增了 **chaowen** 和 **xiao_ya** 兩個 zh_CN medium 聲音（2 個月前上傳），值得與 huayan 比較：

```bash
# 下載新聲音
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/zh_CN-chaowen-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/chaowen/medium/zh_CN-chaowen-medium.onnx.json
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium/zh_CN-xiao_ya-medium.onnx
wget https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/xiao_ya/medium/zh_CN-xiao_ya-medium.onnx.json

# A/B 測試：同一句話三個聲音比較
for voice in huayan chaowen xiao_ya; do
  piper -m zh_CN-${voice}-medium.onnx -f /tmp/tts_${voice}.wav <<< "你好，我是PawAI機器狗，很高興認識你"
done
```

---

## 推薦 Benchmark 候選（Top 3）

### Tier 1（強烈推薦 benchmark）

#### 1. edge-tts（雲端 fallback）
- **理由**：音質最佳、延遲最低、RAM 零成本、部署最簡
- **定位**：雲端主力（有網路時使用），完美搭配 Piper 離線 fallback
- **Benchmark 重點**：延遲實測、穩定性（100 輪）、斷網 fallback 速度
- **風險**：網路依賴、服務封鎖可能性

#### 2. Piper 新聲音（chaowen + xiao_ya）
- **理由**：零成本切換、已驗證平台、2 個月前新增可能改善品質
- **定位**：離線主力的品質提升探索
- **Benchmark 重點**：A/B 聽感比較、延遲差異、降採樣品質

### Tier 2（值得嘗試但風險較高）

#### 3. MeloTTS
- **理由**：44100Hz 高取樣率、中英混合、已有程式碼整合
- **定位**：如果音質明顯優於 Piper，可作為離線替代
- **Benchmark 重點**：ARM64 安裝是否成功、CPU 推理延遲、RAM 增量
- **風險**：mecab ARM64 安裝問題、PyTorch 依賴衝突、無社群 Jetson 案例
- **前提**：先在 Jetson 上嘗試安裝，如果 mecab 失敗則直接淘汰

---

## 推薦架構：雲端+本地雙軌

與 LLM 的雲端+本地 fallback 策略一致：

```
edge-tts (雲端，音質最佳)
  ├─ 有網路 → edge-tts (zh-CN-XiaoxiaoNeural, ~0.5s)
  └─ 無網路 → Piper (最佳聲音 from A/B test, ~2.4s)
```

**優勢**：
1. Demo 展示走 edge-tts（音質驚艷）
2. 實際部署走 Piper（穩定離線）
3. RAM 增量幾乎為零（edge-tts 不佔資源）
4. 不搶 GPU（兩者都是 CPU/雲端）
5. 與現有 tts_node.py 的 provider 架構完美契合

**實作成本**：
- 新增 `TTSProvider_EdgeTTS` 類別（~50 行 Python）
- 新增 `TTSProvider` enum 值
- 新增 ROS2 參數：`edge_tts_voice`
- 在 tts_node 加 fallback 邏輯（edge-tts 失敗 → Piper）

---

## 社群調查摘要

- **Piper**：Jetson 上最多部署案例，jetson-containers 有官方容器（piper1-tts）。專案已 archived 轉 OHF 維護。中文只有 3 個聲音（huayan/chaowen/xiao_ya），品質一般。
- **MeloTTS**：號稱 CPU real-time，但無 Jetson 實測報告。ARM64 有 mecab 依賴問題（open issue）。ONNX 加速 PR 進行中但未合併。44100Hz 取樣率是亮點。
- **edge-tts**：大量使用者，但偶有 "No audio received" 報告。非官方 API，長期穩定性不確定。中文聲音品質與 Azure TTS 同等級（Microsoft Neural）。
- **Kokoro**：英文頂級但中文評級 D，不適合本專案。ONNX 導出有已知問題。
- **sherpa-onnx**：整合框架，支援 Piper + Matcha + Kokoro 模型在 Jetson 上。如需更多 TTS 模型的統一管理可考慮。

## Jetson 資源約束決策矩陣

| TTS 方案 | RAM 增量 | GPU 影響 | 離線 | 音質 | 部署難度 | 總分 |
|----------|:-------:|:------:|:---:|:---:|:------:|:---:|
| Piper (現行) | 200MB | 0% | YES | C | 已完成 | 基準 |
| Piper (新聲音) | 200MB | 0% | YES | C~B? | 換模型檔 | +0.5 |
| edge-tts | ~50MB | 0% | NO | A | 50行程式 | +2 (有網) |
| MeloTTS | 500-800MB | 0~10% | YES | B? | 高風險 | +0~-1 |
| edge-tts + Piper | ~250MB | 0% | YES(fallback) | A/C | 中等 | **+2.5** |

**結論**：**edge-tts + Piper 雙軌** 是最佳方案。

## Benchmark 結果（3/21 Jetson 實測）

| 模型 | P50 延遲 | P95 延遲 | RAM 增量 | 成功率 | 備註 |
|------|:--------:|:--------:|:--------:|:------:|------|
| **edge-tts** zh-TW | **1.13s** | 1.74s | ~0MB | 10/10 | 雲端 Microsoft Neural，音質 A |
| **Piper** huayan | 2.03s | 2.14s | ~3MB | 10/10 | 本地 ONNX，穩定離線 |

edge-tts 比 Piper 快 44%（1.13 vs 2.03s），RAM 零成本。

## 決策（3/21 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| **edge-tts** | **CLOUD** | cloud（主線） | P50 1.13s、A 級音質、RAM 零成本 |
| **Piper huayan** | **JETSON_LOCAL** | jetson（fallback） | P50 2.03s、離線穩定、已驗證 |
| MeloTTS | PENDING | 待測 | ARM64 安裝風險（mecab），需先嘗試安裝 |
