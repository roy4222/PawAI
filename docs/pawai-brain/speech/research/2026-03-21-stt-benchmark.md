# STT 語音辨識模型選型調查

> 最後更新：2026-03-21

## 目標效果
- Jetson 上即時中文語音轉文字
- RTF < 0.5（即 1 秒音訊用 < 0.5 秒推理）
- 與 RTMPose（CUDA）+ YuNet（CPU）共存

## 候選模型

| # | 模型 | 框架 | Installability | Runtime viability | GPU 路徑 | 實測性能 | 納入原因 | 預期淘汰條件 |
|---|------|------|:-:|:-:|:-:|---|---|---|
| 1 | **Whisper small** | faster-whisper (CTranslate2) | verified | verified | cuda float16 | **2.6 FPS / RTF 0.13** | 現有主線，精度優先 | — |
| 2 | Whisper tiny | faster-whisper (CTranslate2) | verified | verified | cuda float16 | **10.4 FPS / RTF 0.03** | 更快更輕 | 中文 WER 明顯惡化 |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| Sherpa-onnx Whisper | 待測，P2 | — |

## Benchmark 結果（3/21 Jetson 實測）

| 模型 | FPS | RTF | Latency (3s audio) | GPU | Gate |
|------|:---:|:---:|:------------------:|:---:|:----:|
| **whisper_small** | 2.6 | **0.13** | 390ms | CUDA | PASS |
| **whisper_tiny** | 10.4 | **0.03** | 96ms | CUDA | PASS |

### L2 共存
| Target | Companion | FPS | vs L1 |
|--------|-----------|:---:|:-----:|
| pose_lw | whisper_small (CUDA) | 14.1 | -20% |

## 已知環境問題
- faster-whisper 安裝會拉入 onnxruntime CPU 版，覆蓋 GPU 版 → 每次裝完要 `pip3 uninstall onnxruntime` + 重裝 GPU 版
- CTranslate2 需要 `LD_LIBRARY_PATH=/home/jetson/.local/ctranslate2-cuda/lib`
- numpy 必須 < 2（onnxruntime-gpu 1.23.0 不相容）

## 決策（3/21 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| **Whisper small** | **JETSON_LOCAL** | jetson（精度優先主線） | RTF 0.13，中文精度最佳 |
| Whisper tiny | JETSON_LOCAL | jetson（資源/延遲壓力時降級） | RTF 0.03 快 4 倍，但中文 WER 待驗 |
