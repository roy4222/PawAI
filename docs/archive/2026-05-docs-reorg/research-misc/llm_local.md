# 本地 LLM Fallback 模型選型調查

> 最後更新：2026-03-21

## 目標效果
- 雲端 LLM（Qwen2.5-7B on RTX 8000）斷線時的本地保底
- 中文對話回覆 ≤25 字
- 與 RTMPose（GPU 91-99%）+ Whisper（CUDA）+ YuNet（CPU）共存
- RAM 預算：≤ 1.0GB（保留 ≥0.8GB 安全餘量）

## 候選模型

| # | 模型 | 量化 | 模型大小 | 運行 RAM | Installability | Runtime viability | GPU 路徑 | 社群性能參考 | 納入原因 | 預期淘汰條件 |
|---|------|------|:-------:|:-------:|:-:|:-:|:-:|---|---|---|
| 1 | **Qwen2.5-0.5B-Instruct** | Q4_K_M GGUF | 491MB | ~0.6-0.8GB | likely | unknown | cpu（推薦）/ cuda | 30-55 tok/s (GPU), 10-15 tok/s (CPU) | RAM 最小、速度夠、中文良好 | 中文品質不足 |
| 2 | Qwen2.5-1.5B-Instruct | Q4_K_M GGUF | 1.12GB | ~1.2-1.5GB | likely | unknown | cpu / cuda | 15-30 tok/s (GPU) | 中文品質更好 | RAM 超額導致 OOM |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| SmolLM2-360M/1.7B | 不支援中文（僅 6 種歐洲語言） | community_only |
| Phi-3.5-mini (3.8B) | INT4 需 ~2.5GB，超出預算；中文中等 | community_only |
| TinyLlama-1.1B | 中文能力基礎級 | community_only |
| Qwen2.5-3B | INT4 需 ~2.1GB，超出預算 | community_only |
| Qwen3.5-0.8B | Ollama GGUF 不相容（多模態 mmproj 問題）；待修復 | repo_issue |

## 推理框架

| 框架 | Jetson ARM64 CUDA | 安裝難度 | 推薦 |
|------|:-:|:-:|:-:|
| **Ollama** | ✅ 確認可用 | 極簡 | **首選（開發驗證）** |
| llama.cpp | 需自行編譯 | 中等 | 生產部署 |
| MLC-LLM | 需 jetson-containers | 較複雜 | NVIDIA 官方路線 |

## GPU 共存策略

**推薦：CPU 模式推理**（`CUDA_VISIBLE_DEVICES="" ollama run qwen2.5:0.5b`）
- 不搶 GPU，RTMPose / Whisper 不受影響
- CPU 推理 10-15 tok/s → 25 字回覆 ~2-3s（可接受的 fallback 延遲）
- GPU 模式只在「RTMPose 未運行」時啟用（0.5-0.8s）

## 預估延遲

| 模式 | 首 token | 25 字生成 | E2E |
|------|:--------:|:--------:|:---:|
| GPU | 0.1-0.3s | 0.5-0.8s | ~0.6-1.1s |
| **CPU（推薦）** | 0.3-0.5s | 1.7-2.5s | **~2.0-3.0s** |

## Benchmark 結果（3/21 Jetson 實測，Ollama API）

| 模型 | E2E P50 | E2E P95 | tok/s | RAM 增量 | 成功率 |
|------|:-------:|:-------:|:-----:|:--------:|:------:|
| **qwen2.5:0.5b** | **0.8s** | 3.0s | 40 | **139MB** | 10/10 |
| qwen2.5:1.5b | 1.0s | 3.4s | 29 | 966MB | 10/10 |

## 決策（3/21 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| **Qwen2.5-0.5B** | **JETSON_LOCAL** | jetson | 0.8s P50、139MB RAM、40 tok/s，唯一能安全與其他模型同跑 |
| Qwen2.5-1.5B | HYBRID | jetson（RTMPose 未跑時） | 品質更好但 966MB RAM，全模型同跑時有 OOM 風險 |
| SmolLM2 | REJECTED | — | 不支援中文 |
| Qwen3.5-0.8B | REJECTED | — | Ollama GGUF 不相容，待修復 |
