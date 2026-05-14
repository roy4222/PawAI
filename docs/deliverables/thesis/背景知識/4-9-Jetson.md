# 4-9 NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB

## 平台定位

NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB 是本專題所有本地感知與即時推理運算的核心邊緣運算平台,負責運行人臉辨識、語音辨識、手勢辨識、姿勢辨識、物體偵測、語音合成與 ROS2 節點等全部本地端軟體堆疊,同時透過 WebRTC DataChannel 與 Unitree Go2 Pro 機器狗進行雙向通訊、透過 USB 介面連接 Intel RealSense D435 深度攝影機與外接音訊裝置。Jetson 是 NVIDIA 專為 AI 邊緣推理設計的嵌入式運算模組產品線,從早期的 Jetson TK1(2014)、TX1、TX2、Xavier NX,至 2023 年發布的 Orin 系列(Orin Nano / Orin NX / AGX Orin),逐代提升算力與能效。其中 Orin Nano 系列是最小、最便宜、最適合入門開發者與學術研究的型號。

## Super 升級的背景

本專題所使用的是 2024 年 12 月 17 日 NVIDIA 發布的 **Jetson Orin Nano SUPER Developer Kit**,這是前代 Jetson Orin Nano Developer Kit 的軟體升級版本——透過 JetPack 6.1 新增的 MAXN 極致效能模式,將原本 40 TOPS 的 AI 推理能力提升至 **67 INT8 TOPS**(提升幅度 1.7 倍),記憶體頻寬從 68 GB/s 提升至 **102 GB/s**(提升 50%)。值得注意的是,「Super」升級並非硬體更動——所有現有的 Jetson Orin Nano Developer Kit 使用者都可以透過 NVIDIA SDK Manager 或直接燒錄新版 SD Card Image 取得此性能升級,無需更換任何實體元件。同時 NVIDIA 也將新版套件的建議售價從原本的 499 美元大幅調降至 **249 美元**,明確瞄準機器人、生成式 AI、Transformer 類模型等邊緣 AI 應用,定位為「人人可負擔的 Gen AI 超級電腦」。此升級對本專題是關鍵利多,讓原本預算有限的學術專題得以取得能執行 LLM、Vision Transformer 等較重推理任務的運算能力。

## 硬體規格

| 規格項目 | 數值 |
|---|---|
| **AI 運算能力** | 67 TOPS(INT8 稀疏),Super MAXN 模式 |
| **GPU 架構** | NVIDIA Ampere |
| **CUDA 核心數** | 1024 顆 |
| **Tensor 核心數** | 32 顆(第三代) |
| **CPU** | 6 核心 Arm Cortex-A78AE v8.2 64 位元 |
| **CPU 時脈** | 最高 1.7 GHz |
| **CPU 快取** | 1.5 MB L2 + 4 MB L3 |
| **記憶體** | 8 GB 128-bit LPDDR5 統一記憶體 |
| **記憶體頻寬** | 102 GB/s |
| **儲存** | 支援 microSD 卡與外接 NVMe SSD |
| **功耗模式** | 7 W / 15 W / 25 W(MAXN 模式,本專題使用) |
| **影片編解碼** | 1× 4K60 / 3× 4K30 / 多路 1080p H.264 / H.265 編解碼硬體加速 |
| **I/O 介面** | 4× USB 3.2 Gen2、1× USB-C(刷機用)、Gigabit Ethernet、DisplayPort、40-pin GPIO header、M.2 Key M(NVMe)、M.2 Key E(Wi-Fi) |
| **載板尺寸** | 100 × 79 公釐 |
| **建議售價** | $249 美元 |

## Ampere GPU 架構與統一記憶體

Jetson Orin Nano SUPER 的 GPU 採用 NVIDIA **Ampere 架構**,與桌上型 RTX 30 系列顯示卡相同世代(CUDA 計算能力 8.7),支援 FP32、FP16、BF16、INT8 等多種精度的張量運算。第三代 Tensor 核心特別針對深度學習推理最佳化,支援結構化稀疏(Structured Sparsity)加速——即模型權重若滿足 2:4 稀疏模式(每 4 個權重中有 2 個為 0),推理速度可額外加倍。這也是 NVIDIA 標榜 67 TOPS 的數據依據(INT8 稀疏模式),密集模式下約為 33 TOPS。

**統一記憶體架構(Unified Memory Architecture)** 是 Jetson 系列相較於桌上型 GPU 系統最重要的架構特色。桌上型 GPU 透過 PCIe 介面與主記憶體(RAM)分離,資料需在 CPU RAM 與 GPU VRAM 之間透過 PCIe 匯流排複製,此複製成本是高頻寬應用的主要瓶頸。Jetson 則將 8 GB LPDDR5 記憶體設計為 CPU 與 GPU 共享,任何資料只需存在實體記憶體一次,CPU 與 GPU 可直接存取同一份資料而無需複製,大幅降低延遲並簡化記憶體管理。對本專題這類多模組並行(人臉、手勢、姿勢、物體、ASR/LLM 皆需讀取相同的相機影像或中間張量)的場景特別有利。此設計同時也是資源競爭的來源——CPU 的記憶體使用與 GPU 的推理工作互相擠壓同一個 8 GB 空間,本專題的 RAM 預算管理因此需要極度謹慎(詳見下文資源分配段)。

## 軟體堆疊:JetPack 6

本專題使用 NVIDIA **JetPack 6.1+** 作為 Jetson 的作業系統與 SDK 套件。JetPack 是 NVIDIA 為 Jetson 系列提供的完整嵌入式 Linux 開發套件,基於 **Ubuntu 22.04 LTS** 客製化,預裝 NVIDIA 的全部 AI 推理軟體堆疊,包含:

- **Linux for Tegra(L4T)核心**:針對 Jetson 硬體最佳化的 Ubuntu Linux 發行版。
- **CUDA Toolkit 12.6**:NVIDIA 的並行運算平台,提供在 GPU 上執行通用運算的 API。
- **cuDNN 9.x**:深度神經網路基礎運算函式庫,為 CNN 等常見層提供最佳化核心。
- **TensorRT 10.x**:NVIDIA 的高效能推理引擎,透過 layer fusion、kernel auto-tuning、FP16 / INT8 量化等技術將 ONNX 或 PyTorch 模型編譯為高度最佳化的推理 engine,本專題的 YOLO26n 物體辨識即透過 TensorRT 加速。
- **VPI(Vision Programming Interface)**:電腦視覺運算函式庫,提供加速的影像前處理運算(如 resize、warp、濾波)。
- **Multimedia API**:支援硬體加速的 H.264 / H.265 影片編解碼。
- **DeepStream SDK**:高階視訊分析管線框架(本專題未使用)。
- **Jetson Platform Services**:系統監控與效能管理服務。

JetPack 6.1 的重要新增功能為 **MAXN 極致效能模式**——這是驅動 Orin Nano 升級為 Super 的核心軟體改動,透過放寬動態電壓頻率調整(DVFS)策略讓 GPU 與 CPU 能持續運行於更高的時脈,進而解鎖硬體原本就具備但先前韌體未釋放的 67 TOPS 能力。本專題透過 `sudo nvpmodel -m 0 && sudo jetson_clocks` 兩道指令啟用 MAXN 模式並鎖定最高時脈,確保推理效能穩定可重現。

## 為何選擇此平台

本專題評估邊緣運算平台時曾考量多個候選方案,包含 Jetson Orin Nano 8GB、Jetson Orin NX 16GB、x86 mini PC(Intel NUC 或同級)、Raspberry Pi 5 等。最終選擇 Jetson Orin Nano SUPER 8GB 的理由綜合如下:

- **AI 推理原生加速**:相較於 x86 mini PC 需額外採購 USB 加速棒或 PCIe 加速卡才能取得硬體 AI 推理能力,Jetson 直接內建 1024 CUDA + 32 Tensor 核心,且 CUDA / cuDNN / TensorRT 軟體堆疊完整整合,無需額外驅動程式或套件安裝問題。
- **ROS2 生態成熟度**:Jetson 在 ROS2 機器人社群中有最多實機部署案例與教學資源,相容性與除錯便利度遠勝其他平台。
- **記憶體與算力平衡**:8 GB 統一記憶體足以同時運行六個感知模組,67 TOPS 算力足以即時處理多路視覺推理。
- **體積與功耗**:載板尺寸僅 100 × 79 公釐、重量輕、功耗 25 瓦以下,可直接安裝於 Go2 Pro 機身上作為外掛運算模組,由 Go2 電池經 XL4015 降壓模組供電。
- **採購成本**:$249 美元的 Jetson Orin Nano SUPER 是目前市場上最具性價比的嵌入式 AI 運算平台,指導老師提供的 Jetson 讓本專題無需額外採購即可開始開發。
- **社群參考案例豐富**:NVIDIA 官方 Jetson AI Lab、Ultralytics、Unitree 社群(如 abizovnuralem/go2_ros2_sdk)均提供針對 Jetson Orin Nano 的部署教學與踩坑紀錄,降低本專題遭遇未知技術問題的機率。

## 本專題的 Jetson 資源分配

本專題於 Jetson Orin Nano SUPER 8GB 上運行的軟體堆疊包含下列模組,其實測資源佔用(於人臉、手勢、姿勢、物體、語音五大感知模組同時運行時)如下。**以下數據取自 Demo 部署主線(`start_full_demo_tmux.sh`)的覆寫配置**,即 gesture_backend=recognizer、pose_backend=mediapipe(Lite)、TTS=edge-tts、ASR=SenseVoice Cloud;程式碼原始預設配置會走 RTMPose pose/gesture backend 與舊本地麥克風路徑,資源分布會有所不同:

| 模組 | RAM | CPU | GPU | 備註 |
|---|:---:|:---:|:---:|---|
| ROS2 runtime + Go2 driver | 1.5–2.0 GB | ~20% | 0% | 基礎通訊層 |
| D435 camera driver | 0.6–1.0 GB | ~10% | 0% | RGB + Depth 串流 |
| 人臉辨識(YuNet + SFace) | ~0.3 GB | ~40% | 0% | CPU-only |
| 手勢辨識(MediaPipe Hands) | ~0.2 GB | ~45% | 0% | CPU-only |
| 姿勢辨識(MediaPipe Pose) | ~0.25 GB | ~50% | 0% | CPU-only |
| 物體辨識(YOLO26n TensorRT) | ~1.0 GB | ~40% | 使用中 | TensorRT FP16 |
| 語音(edge-tts / Cloud ASR) | ~0.1 GB | ~10% | 0% | 雲端主線 |
| **總計** | **~4.0–5.5 GB** | **~215%(六核共 600%)** | 部分佔用 | 餘 2.5–4 GB 安全邊界 |

此資源分配策略的核心原則為:**GPU 獨佔給 YOLO26n 的 TensorRT 推理,所有其他感知模組走 CPU 以避免資源競爭**。這也是本專題選擇 MediaPipe 而非 RTMPose(後者會佔滿 GPU 91 至 99%)、選擇 YuNet 而非 SCRFD(後者需 GPU)、選擇 CPU 模式的 Qwen2.5-1.5B 本地 LLM 備援的根本理由。整體架構在資源邊界內達成穩定運行,但餘量有限,任何新增模組都需謹慎評估資源衝擊。

## 已知限制

- **統一記憶體為雙面刃**:CPU 與 GPU 共享同一 8 GB 空間,任何一方的記憶體洩漏都會影響另一方,記憶體壓力需嚴密監控。
- **散熱管理**:MAXN 模式下 Jetson 核心溫度通常維持於 50 至 65 °C,配備主動風扇時可長時間穩定運行;若無風扇或進風口被遮擋,可能觸發 thermal throttling 自動降頻。本專題於 Go2 機身上安裝 Jetson 時已確保進風口暢通。
- **供電穩定性**:如第五章所述,Jetson 透過外接 XL4015 降壓模組從 Go2 電池取電,高負載時段電壓不穩定為 Demo 期間的已知風險。
- **ARM 生態碎片化**:部分 Python 套件(如 ultralytics、PyTorch 某些版本)的 ARM wheel 與 JetPack 6 CUDA 版本不相容,需避免直接 `pip install` 破壞預裝環境。
