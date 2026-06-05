# PINTO_model_zoo 完整解析（19 類 × 482 模型 × Jetson Orin Nano SUPER 8GB 部署判定）

> 🔬 **RESEARCH-ONLY — research-not-truth**。全 zoo 部署可行性解析，四級標記為架構/格式/footprint 推定（僅 24 個經 convert_script 硬驗證為地面真值）。**不是**實作 backlog、**不是**能力 pass 真相。能力是否 pass 以 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) 為準；能不能講連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。索引見 [`README.md`](README.md)。
> 🏷️ **Tier**：`FUTURE_RESEARCH`。不把任何「可/很可能」預設變成 6/18 backlog。

> 產出日期：2026-06-04 Asia/Taipei
> 來源：`github.com/PINTO0309/PINTO_model_zoo` @ commit `870b2b8`（partial clone，本地 `.tmp/PINTO_model_zoo`）
> 目標板：**NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB**（JetPack 6.2 / CUDA 12.6 / TensorRT 10.3）
> 對應 PawAI 文件：[`2026-06-02-model-candidate-registry.md`](2026-06-02-model-candidate-registry.md)、[`../specs/2026-06-18-capability-baseline-spec.md`](../specs/2026-06-18-capability-baseline-spec.md)
> 姊妹文件（精簡清單）：[`2026-06-04-pinto-jetson-deployable-models.md`](2026-06-04-pinto-jetson-deployable-models.md)

---

## 0. 摘要

PINTO_model_zoo 是一個**跨框架模型「轉換」zoo**（不是訓練 zoo）——把同一個模型在 TensorFlow / PyTorch / ONNX / OpenVINO / TFLite / EdgeTPU / CoreML / TFJS / TF-TRT 之間互轉並預先量化。整庫規模：

- **19 種功能類別**（本文件 §1–§19）
- **482 個個別模型**（483 個編號資料夾扣除 `999_media` 素材夾）
- **9 框架家族 / 11 格式變體**（每個模型都互轉成這些）

**對 Jetson Orin Nano SUPER 8GB 的部署真相只卡兩道門檻：**

1. **格式**：板子是 ARM64 + NVIDIA Ampere，**只有 `ONNX → onnxruntime-gpu(jp6/cu126) + TensorRT-EP FP16` 是實證主線**。`EdgeTPU`(Coral 專用)、`CoreML`(Apple)、`OpenVINO`(Intel)、`TFJS`(瀏覽器) **物理上跑不起來**——但因為 PINTO 幾乎每個模型都附 ONNX，格式很少是真正的阻擋點。
2. **8GB UNIFIED 記憶體**（CPU+GPU+D435 共用一池，可用 ~7.6GB）：小型 CNN/embedder 沒問題；ViT / transformer / 多 GB 模型會把預算吃爆。判定要對「正在跑的 stack」算，不是空板。

**最容易部署的類別**：§1 影像分類、§2 物件偵測（n/t 小變體）、§4 人臉、§5/§6 手部姿態（小模型）。
**最該避開的類別**：§11 超解析、§7 深度（大型 ViT）、§16 Inpainting、§17 GAN、§19 多數——多為大型生成/transformer 模型。

> 本文件每個模型的「Jetson 8GB」欄使用四級標記：**可** / **很可能**（ONNX 對、footprint 合理但未上機量過）/ **風險**（transformer/大型，恐爆 8GB）/ **不可**（錯誤晶片格式或多 GB）。其中與 PawAI 直接相關的 24 個候選經過實讀 `convert_script.txt` 硬驗證，標記為地面真值。

---

## 1. 全域速覽

| # | 類別 | 模型數 |
|--:|------|------:|
| 1 | Image Classification | 46 |
| 2 | 2D Object Detection | 89 |
| 3 | 3D Object Detection | 6 |
| 4 | 2D/3D Face Detection | 41 |
| 5 | 2D/3D Hand Detection | 6 |
| 6 | 2D/3D Human/Animal Pose Estimation | 27 |
| 7 | Depth Estimation (Monocular/Stereo) | 54 |
| 8 | Semantic Segmentation | 44 |
| 9 | Anomaly Detection | 2 |
| 10 | Artistic | 11 |
| 11 | Super Resolution | 82 |
| 12 | Sound Classifier | 8 |
| 13 | Natural Language Processing | 3 |
| 14 | Text Recognition | 3 |
| 15 | Action Recognition | 3 |
| 16 | Inpainting | 4 |
| 17 | GAN | 2 |
| 18 | Transformer | 1 |
| 19 | Others | 52 |
| | **合計** | **484** |

### 格式維度（每個模型都互轉成這些 → 在本板的可用性）

| 格式 | Jetson 8GB | 說明 |
|------|:---------:|------|
| **ONNX** | ✅ 主線 | onnxruntime-gpu(jp6/cu126 wheel) + TensorRT-EP FP16 / CUDA EP。PawAI 已用此路徑跑 YOLO26n + RTMPose-lw |
| **PyTorch** | ✅ 重 | 走 NVIDIA torch wheel（非 PyPI）。**切勿 `pip install ultralytics`** 會破壞 Jetson torch wheel |
| **TF saved_model** | ⚠️ 來源用 | TF runtime 笨重、版本脆弱；只當轉換來源，部署改 ONNX→TRT |
| **TFLite** | ⚠️ CPU-only | 只在 A78AE CPU(XNNPACK) 跑，無對應 Ampere 的 GPU delegate。小模型可、無法 GPU offload |
| **TF-TRT** | ⚠️ 重 | 技術可行但拖整個 TF runtime 上 8GB 板，footprint 比純 ONNX→TRT 差 |
| **EdgeTPU** | ❌ | 只給 Google Coral ASIC，板上無此矽晶 |
| **CoreML** | ❌ | Apple 專用，Linux ARM64 無 runtime |
| **OpenVINO** | ❌ | Intel 專用，無 NVIDIA GPU backend |
| **TFJS** | ❌ | 瀏覽器/Node WebGL，錯誤執行環境 |

---

## 目錄

- [1. Image Classification](#1-image-classification)
- [2. 2D Object Detection](#2-2d-object-detection)
- [3. 3D Object Detection](#3-3d-object-detection)
- [4. 2D/3D Face Detection](#4-2d3d-face-detection)
- [5. 2D/3D Hand Detection](#5-2d3d-hand-detection)
- [6. 2D/3D Human/Animal Pose Estimation](#6-2d3d-humananimal-pose-estimation)
- [7. Depth Estimation (Monocular/Stereo)](#7-depth-estimation-monocularstereo)
- [8. Semantic Segmentation](#8-semantic-segmentation)
- [9. Anomaly Detection](#9-anomaly-detection)
- [10. Artistic](#10-artistic)
- [11. Super Resolution](#11-super-resolution)
- [12. Sound Classifier](#12-sound-classifier)
- [13. Natural Language Processing](#13-natural-language-processing)
- [14. Text Recognition](#14-text-recognition)
- [15. Action Recognition](#15-action-recognition)
- [16. Inpainting](#16-inpainting)
- [17. GAN](#17-gan)
- [18. Transformer](#18-transformer)
- [19. Others](#19-others)

---

## 1. Image Classification

本類共 46 個資料夾，是 PINTO_model_zoo 中對 Jetson Orin Nano SUPER 8GB 最友善的一類——README 的 ONNX 欄幾乎全數標記 ⚫，且絕大多數為輸入 32x32~224x224 的小型 CNN 分類器或臉部/行人 embedder，模型檔多落在 1~50MB 量級。部署路徑統一走 onnxruntime-gpu (jp6/cu126) + TensorRT-EP FP16，與已上機驗證的 256_SFace、YuNet 同級，記憶體佔用低、可與 D435+人臉+ASR+TTS+ROS2 共存。風險集中在少數 ViT/大型 backbone 模型（175 ResNet100、483/484 ViT 臉部 embedder、462/474 Gaze-LLE DINOv2/v3）；419_MobileViT 本 repo 僅有 README 無實際匯出檔，列不可。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:---------:|------|
| EfficientNet | 004_efficientnet | ImageNet 影像分類（B0~B7） | B0 ImageNet top-1 ~77%，B0 ONNX 走 GPU 可達數百 FPS | 可 | B0/B1 小，B4+ 偏大；選 B0 最穩 |
| MobileNetV3 | 010_mobilenetv3 | 行動端影像分類 | Large top-1 ~75%，Small ~67%；極輕 | 可 | 經典輕量 CNN，TRT FP16 順 |
| MobileNetV2 | 011_mobilenetv2 | 行動端影像分類 | ImageNet top-1 ~72%，~3.5M params | 可 | 標竿輕量網路，已含 INT8 量化 |
| EfficientNet-lite | 016_EfficientNet-lite | 行動端友善 EfficientNet（無 SE/swish） | lite0 top-1 ~75%；對量化友善 | 可 | 設計即為 edge 量化，最適合本機 |
| age-gender-recognition | 070_age-gender-recognition | 臉部年齡+性別辨識 | OpenVINO MZ 模型，62x62 輸入，極小 | 可 | 多任務輕量頭，毫秒級 |
| Person_Reidentification | 083_Person_Reidentification | 行人 ReID 特徵嵌入 | OMZ reid 系列，rank-1 ~90%+（Market）；輸入小 | 可 | 多變體(248~300)，皆小型 embedder |
| DeepSort | 087_DeepSort | 多目標追蹤外觀特徵 (ReID) | MARS embedder 128-d，輸入 64x128，極輕 | 可 | 配合偵測器做 tracking，CPU/GPU 皆順 |
| person-attributes-0230 | 124_person-attributes-recognition-crossroad-0230 | 行人屬性多標籤分類 | OMZ，160x80 輸入，~0.7M params | 可 | 多標籤 sigmoid 頭，極快 |
| person-attributes-0234 | 125_person-attributes-recognition-crossroad-0234 | 行人屬性多標籤分類 | OMZ 改版，含量化匯出 | 可 | 同 0230 系列，輕量 |
| person-attributes-0238 | 126_person-attributes-recognition-crossroad-0238 | 行人屬性多標籤分類 | OMZ 最新版，輕量 | 可 | 同系列，差異在屬性集 |
| arcface-resnet100 | 175_face-recognition-resnet100-arcface-onnx | 臉部辨識嵌入（512-d） | LFW TAR ~99.7%；ResNet100 backbone，ONNX ~250MB | 風險 | backbone 最重，FP16 仍吃顯存；要高精度才用，否則改 SFace/AdaFace |
| vehicle-attributes-0039 | 187_vehicle-attributes-recognition-barrier-0039 | 車輛顏色+類型分類 | OMZ，72x72 輸入，極小 | 可 | 多輸出頭，毫秒級 |
| vehicle-attributes-0042 | 188_vehicle-attributes-recognition-barrier-0042 | 車輛顏色+類型分類 | OMZ 改版，72x72，極小 | 可 | 同上系列 |
| anti-spoof-mn3 | 191_anti-spoof-mn3 | 臉部活體/防偽（spoof）分類 | MobileNetV3 backbone，128x128 輸入 | 可 | 二元活體分類，輕量 |
| open-closed-eye-0001 | 192_open-closed-eye-0001 | 開閉眼分類 | OMZ，32x32 輸入，極微 | 可 | 疲勞偵測常用，幾乎零成本 |
| face_recognizer_fast | 194_face_recognizer_fast | 快速臉部辨識嵌入 | 112x112 輸入；OpenCV Zoo SFace 系變體 | 可 | 與 256 同級小 embedder |
| person_reid_youtu | 195_person_reid_youtu | 行人 ReID 特徵嵌入 | OpenCV Zoo reid，256x128 輸入 | 可 | 輕量 ReID backbone |
| NSFW | 199_NSFW | 不雅內容分類 | open_nsfw，224x224；ResNet 系（由 tflite 轉） | 可 | 由 tflite2tensorflow 轉得 ONNX，輕量 |
| FINNger | 244_FINNger | 手指數量計數分類 | 自訂小 CNN，96x96 輸入；無公開大型基準 | 可 | 玩具級小模型，極輕 |
| SFace | 256_SFace | 臉部辨識嵌入（cosine 相似度） | LFW ~99.6%；~24M params / ONNX ~37MB；112x112 | 可 | 已上機驗證等級（CONFIRMED），主線臉部 embedder |
| PiCANet | 257_PiCANet | 顯著性/駕駛注意力估測（SAGENet） | 224x224 輸入；attention 顯著圖；無統一公開基準 | 很可能 | 含 PiCANet attention 模組，ONNX 不大但屬注意力結構，未實測 |
| Emotion_FERPlus | 259_Emotion_FERPlus | 臉部情緒分類（8 類） | FERPlus，64x64 輸入；準確率約 84%（FER+ test） | 可 | 經典小 CNN，極輕 |
| AdaFace | 290_AdaFace | 臉部辨識嵌入（品質自適應） | IJB-C TAR@FAR1e-4 ~96%；112x112；backbone 視變體 | 可 | OMZ 變體輕量；若用 IR-100 變體則偏重，預設可 |
| MobileOne | 317_MobileOne | 重參數化行動端分類 backbone | s0 top-1 ~71%，推論時融合分支極快；224x224 | 可 | 推論期單分支結構，TRT FP16 非常適合 |
| facial_expression_mobilefacenet | 346_facial_expression_recognition_mobilefacenet | 臉部表情分類 | OpenCV Zoo，112x112；MobileFaceNet backbone | 可 | 輕量臉部任務，毫秒級 |
| PP-LCNetV2 | 379_PP-LCNetV2 | PaddleClas 行動端分類 backbone | ImageNet top-1 ~77%（base）；224x224；CPU 友善 | 可 | 為 Intel CPU 設計但 ONNX 可走 GPU，輕量 |
| MobileViT_v1_v2 | 419_MobileViT_v1_v2 | 行動端 ViT-CNN 混合分類 | XS/S top-1 ~74~78%；本 repo 僅 README、無匯出檔 | 不可 | 此資料夾無實際 ONNX/腳本產物（僅 README），無法部署；如需可自源頭轉 |
| OSNet | 429_OSNet | 行人 ReID 特徵嵌入 | Market rank-1 ~94%；256x128；~2.2M params | 很可能 | 小型 ReID backbone，ONNX 不大但未實測 |
| FastReID | 430_FastReID | 行人 ReID 特徵嵌入 | Market mAP ~86%+；384x128；backbone 視變體(R50 偏重) | 很可能 | R50 版偏大走風險，輕量 backbone 版可；未實測 |
| NITEC | 431_NITEC | 眼神接觸/凝視估測 | 224x224；ResNet 系 gaze backbone；無統一公開基準 | 很可能 | gaze 估測 backbone，ONNX 中量級，未實測 |
| face-reidentification-retail-0095 | 432_face-reidentification-retail-0095 | 臉部 ReID 嵌入（256-d） | OMZ，128x128 輸入，輕量 | 可 | 小型臉部 embedder |
| DAN | 451_DAN | 臉部表情辨識（Distract-Attention） | RAF-DB acc ~89%；224x224；ResNet-18 backbone | 很可能 | ResNet18 + 注意力頭，ONNX 中量級，FP16 應可，未實測 |
| FairFace | 452_FairFace | 臉部屬性（種族/性別/年齡） | FairFace acc ~高；224x224；ResNet-34 backbone | 可 | ResNet34 不算大，FP16 順；偏中量級 |
| FairDAN | 453_FairDAN | 臉部屬性 + 表情多任務 | 224x224；DAN+FairFace 融合，雙 ResNet backbone | 很可能 | 結合兩網，較重，FP16 應可但顯存較高，未實測 |
| Gaze-LLE | 462_Gaze-LLE | 凝視目標估測（attention 熱圖） | 448x448 輸入；DINOv2 ViT backbone | 風險 | ViT backbone + 大輸入，FP16 可載但吃顯存/算力，建議單獨跑 |
| Gaze-LLE-DINOv3 | 474_Gaze-LLE-DINOv3 | 凝視目標估測（DINOv3 backbone） | 320~640 輸入；DINOv3 ViT backbone | 風險 | 更新 DINOv3，transformer 大型，8GB 邊緣可行但需保留 headroom |
| VSDLM | 475_VSDLM | 唇動/說話狀態分類 | 30x48 輸入，極微小 CNN；無公開基準 | 可 | 微型分類器，幾乎零成本 |
| OCEC | 476_OCEC | 眨眼/眨眼狀態分類（Wink/Blink） | 24x40 輸入，極微小；無公開基準 | 可 | 微型分類器，極輕 |
| PGC | 477_PGC | 指向手勢分類（Pointing） | L 變體 = 6.4MB ONNX（最大），S=49KB；32x32 | 可 | 已評估等級（CONFIRMED），全變體皆小 |
| SC | 478_SC | 坐姿分類（Sitting） | 模型檔 115KB~875KB（最大為 C 變體）；32x24 | 可 | 已評估等級（CONFIRMED），微型 |
| PUC | 479_PUC | 手機使用分類（Phone Usage） | 32x24 輸入，微型 CNN；無公開基準 | 可 | 與 SC 同級微型分類器 |
| HSC | 480_HSC | 微笑/開心表情分類 | 48x48 輸入，微型 CNN；無公開基準 | 可 | 微型分類器，極輕 |
| WHC | 481_WHC | 揮手手勢分類（時序堆疊幀） | 每變體 ~1.1MB ONNX；4/6/8x32x32 多幀輸入 | 可 | 已評估等級（CONFIRMED），輕量時序分類 |
| LVFace | 483_LVFace | 臉部辨識嵌入（ViT，cosine） | Nx3x112x112；ViT backbone（ByteDance LVFace） | 風險 | ViT 臉部 embedder，FP16 可載但比 SFace 重，較大變體需注意顯存 |
| TransFace | 484_TransFace | 臉部辨識嵌入（Transformer） | IJB-C 高 TAR；Nx3x112x112；ViT backbone | 風險 | Transformer 臉部 embedder，較重，需保留 headroom |
| MWC | 486_MWC | 口罩配戴分類 | Nx3x48x48 輸入，微型 CNN；無公開基準 | 可 | 微型二/多元分類器，極輕 |

**建議硬體**：本類絕大多數（小型 CNN 分類器/embedder，32x32~224x224，1~50MB）皆「可」直接在 Jetson Orin Nano SUPER 8GB 走 ONNX→TensorRT FP16，與已上機的 SFace 同級；唯 175(ResNet100)、462/474(Gaze-LLE ViT)、483/484(ViT 臉部 embedder) 列風險需保留 ≥0.8GB headroom 且建議單獨跑，419(MobileViT) 本 repo 無匯出檔列不可。

---

## 2. 2D Object Detection

本類別共 89 個資料夾，是整個 zoo 中最龐大也最貼近 PawAI「居家互動機器狗」需求的一類（人/手/頭/物體偵測直接餵 Brain 的 Policy 層）。涵蓋三條技術脈絡：(1) 行動端單階段 CNN（SSD/MobileNet、NanoDet、PicoDet、FastestDet、YOLOX-nano/tiny、YOLOv6/7/9-n 系列），這類 ONNX 多為 2–10MB，FP16→TensorRT 後與板上已驗證的 YOLO26n 同級，是最安全的部署選擇；(2) 中量級 YOLO（s/m、YOLOR、DAMO-YOLO、Gold-YOLO、EdgeYOLO），單跑可行但與 face+ASR+TTS 共存時要看變體大小；(3) Transformer 偵測器（DETR、RT-DETR、RT-DETRv2、DEIM/DEIMv2、含 DINOv3-ViT backbone 的 Wholebody40/49），記憶體與算力風險高。**PINTO 作者本人的 Wholebody / Body-Head-Hand 系列（422–488）特別有價值**——它們把「身體/頭/手/臉/腳/輪椅/拐杖」一次偵測，幾乎是 PawAI 互動感知的現成 superset，且絕大多數提供 n/t 小變體。表格內凡標 EdgeTPU/OpenVINO/CoreML/TFJS 的來源，只要 ONNX 欄有提供（本類幾乎都有），即可走 onnxruntime-gpu + TensorRT-EP 路徑，不受原始矽晶片限制。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|---|---|---|---|---|---|
| MobileNetV3-SSD | 002_mobilenetv3-ssd | COCO 通用物件偵測 | ~22 mAP，行動端即時 | 可 | 輕量 SSD，ONNX 小，FP16 輕鬆 |
| MobileNetV2-SSDLite | 006_mobilenetv2-ssdlite | COCO 通用偵測 | ~22 mAP@COCO | 可 | 經典 edge baseline，~4–6MB |
| Mask R-CNN InceptionV2 | 008_mask_rcnn_inceptionv2 | 實例分割+偵測 | ~33 box mAP，慢（兩階段） | 風險 | 兩階段+mask head，重、ROIAlign 對 TRT 不友善 |
| EfficientDet | 018_EfficientDet | COCO 偵測(D0–D7) | D0 ~34 mAP / D7 ~53 mAP | 風險 | 僅 D0/lite 可考慮；高 D 變體大且 BiFPN 慢 |
| YOLOv3-nano | 023_yolov3-nano | 通用偵測 | 依變體而定，輕量 | 可 | 極小 Darknet，ONNX 小 |
| YOLOv3-lite | 024_yolov3-lite | 通用偵測 | 依變體而定 | 可 | 輕量 YOLOv3，FP16 OK |
| YOLOv4 | 031_yolov4 | COCO 偵測 | ~43 mAP@608，中量級 | 很可能 | 608 全尺寸 CSPDarknet53，單跑可、共存吃緊 |
| SSD-MobileNetV2-MnasFPN | 034_ssd_mobilenet_v2_mnasfpn_shared_box_predictor | 行動端偵測 | ~26 mAP@COCO | 可 | MnasFPN 行動最佳化，ONNX 小 |
| SSDLite-MobileDet-EdgeTPU | 038_ssdlite_mobiledet_edgetpu | 行動端偵測 | ~25 mAP，EdgeTPU 最佳化 | 很可能 | 原為 EdgeTPU，有 ONNX 走 GPU 即可 |
| SSDLite-MobileDet-CPU | 039_ssdlite_mobiledet_cpu | 行動端偵測 | ~24 mAP@COCO | 可 | CPU-friendly backbone，ONNX 小 |
| CenterNet | 042_centernet | anchor-free 偵測 | backbone 而定，~28–40 mAP | 很可能 | DLA/Hourglass 變體差異大，取小 backbone |
| SSD-MobileNetV2-OID-v4 | 045_ssd_mobilenet_v2_oid_v4 | Open Images 600 類偵測 | OID mAP（類多） | 可 | 600 類但 backbone 輕，ONNX 小 |
| YOLOv4-tiny | 046_yolov4-tiny | 通用偵測 | ~40 mAP@416(tiny)，極快 | 可 | tiny Darknet，板上輕鬆即時 |
| SpineNetMB-49 | 047_SpineNetMB_49 | Mobile RetinaNet 偵測 | mobile RetinaNet，輕量 | 可 | 320x320 行動 RetinaNet，ONNX 小 |
| EAST Text Detection | 051_East_Text_Detection | 場景文字偵測 | ICDAR F~0.80 | 可 | 全卷積文字框，輸入中等、FP16 OK |
| KNIFT | 054_KNIFT | MediaPipe 特徵點/模板匹配 | 特徵描述子，無 mAP 概念 | 可 | MediaPipe 小模型，CPU/GPU 皆可 |
| TextBoxes++ | 056_TextBoxes++ | 場景文字偵測 | ICDAR F~0.82 | 很可能 | SSD-style 文字框，輸入較大 |
| keras-retinanet | 058_keras-retinanet | COCO 偵測(ResNet50) | ~35 mAP@320，ResNet50 FPN | 很可能 | 320x320，ResNet50 單跑可、共存吃緊 |
| NanoDet | 072_NanoDet | 超輕量通用偵測 | nanodet_m ~20 mAP，ONNX ~3–4MB | 可 | nanodet_m ~0.95M params，板上首選級別 |
| RetinaNet | 073_RetinaNet | 通用偵測 | ~35–37 mAP，backbone 而定 | 很可能 | ResNet+FPN，取小 backbone 較穩 |
| Yolact | 074_Yolact | 即時實例分割 | ~29 mask mAP@550，ResNet | 很可能 | 即時實例分割，proto+mask 中量級 |
| Yolact-Edge | 085_Yolact_Edge | 即時實例分割(行動) | MobileNetV2 550x550，邊緣最佳化 | 很可能 | 專為 Jetson 設計，MobileNetV2 版較輕 |
| DETR | 089_DETR | Transformer 偵測 | ~42 mAP(原版)，此處 256x256 | 風險 | Transformer decoder，256x256 小但注意力慢 |
| EfficientDet-lite | 103_EfficientDet_lite | 行動端偵測(lite0-4) | lite0 ~26 / lite4 ~44 mAP | 很可能 | lite0/1 可上板，lite3/4 較吃力 |
| DroNet | 116_DroNet | 無人機視角偵測 | 依變體而定/無公開基準 | 很可能 | Darknet/YOLOv2-v3 衍生卷積 backbone |
| YOLOR | 123_YOLOR | COCO 偵測 | ~52 mAP@640(主模型) | 風險 | 320–1280 多尺寸，大尺寸與大模型吃 RAM |
| YOLOX | 132_YOLOX | anchor-free 偵測 | nano ~25 / s ~40 / x ~51 mAP | 可 | nano ~0.9M(~3MB)、tiny ~5M；小變體首選 |
| RAPiD | 143_RAPiD | 魚眼俯視人體偵測 | 旋轉框，魚眼專用 | 很可能 | 608/1024 魚眼，輸入大但 CNN 結構 |
| text_detection_db | 145_text_detection_db | 場景文字偵測(DBNet) | ICDAR F~0.82 | 可 | DBNet，480x640 輕量分割式文字框 |
| mobile_object_localizer | 151_object_detection_mobile_object_localizer | 通用前景物件框 | class-agnostic，192x192 | 可 | 極小 192x192，板上極快 |
| spaghettinet_edgetpu | 169_spaghettinet_edgetpu | 行動端偵測(NAS) | ~25 mAP，EdgeTPU NAS | 很可能 | 原 EdgeTPU，有 ONNX 走 GPU |
| PP-PicoDet | 174_PP-PicoDet | 超輕量通用偵測 | picodet_s ~30 mAP，~2-3MB(INT8) | 可 | picodet_s ~1.2M params，板上首選級別 |
| vehicle-detection-0200 | 178_vehicle-detection-0200 | 車輛偵測 | Intel SSD，256x256 | 可 | OpenVINO 來源，ONNX 小 MobileNet-SSD |
| person-detection-0202 | 179_person-detection-0202 | 行人偵測 | Intel SSD，512x512 | 可 | OpenVINO 來源，行人專用輕量 |
| pedestrian-detection-adas-0002 | 183_pedestrian-detection-adas-0002 | ADAS 行人偵測 | Intel，384x672 | 可 | OpenVINO 來源，ONNX 走 GPU |
| pedestrian-and-vehicle-adas-0001 | 184_pedestrian-and-vehicle-detector-adas-0001 | 行人+車輛偵測 | Intel，384x672 | 可 | OpenVINO 來源，輕量 SSD |
| person-vehicle-bike-crossroad-0078 | 185_person-vehicle-bike-detection-crossroad-0078 | 路口多類偵測 | Intel，1024x1024 | 很可能 | 輸入 1024 較大，但 backbone 輕 |
| person-vehicle-bike-crossroad-1016 | 186_person-vehicle-bike-detection-crossroad-1016 | 路口多類偵測 | Intel，512x512 | 可 | OpenVINO 來源，ONNX 小 |
| vehicle-license-plate-barrier-0106 | 189_vehicle-license-plate-detection-barrier-0106 | 車牌偵測 | Intel，300x300 | 可 | OpenVINO 來源，極小 SSD |
| person-detection-asl-0001 | 190_person-detection-asl-0001 | 人物偵測 | Intel，320x320 | 可 | OpenVINO 來源，輕量 |
| yolact-resnet50-fpn | 197_yolact-resnet50-fpn | 即時實例分割 | ~28 mask mAP@550，ResNet50 | 很可能 | ResNet50-FPN，單跑可、共存吃緊 |
| YOLOF | 198_YOLOF | 單層特徵偵測 | ~37 mAP@608(ResNet50) | 風險 | ResNet50 backbone+608，較重 |
| YOLACT-PyTorch | 221_YOLACT-PyTorch | 即時實例分割 | ~29 mask mAP，多尺寸 | 很可能 | 取小尺寸(180x320)較穩，大尺寸吃緊 |
| CascadeTableNet | 226_CascadeTableNet | 表格結構偵測 | Cascade R-CNN，320x320 | 風險 | Cascade R-CNN 多階段，重 |
| ByteTrack | 262_ByteTrack | 多目標追蹤(偵測器) | YOLOX backbone，MOT17 | 可 | 偵測部分用 YOLOX，取 nano/tiny 即可 |
| object_localization_network | 264_object_localization_network | class-agnostic 物件框 | OLN，開放世界框 | 風險 | 基於 Faster/Mask R-CNN mmdet，較重 |
| YOLOv7 | 307_YOLOv7 | COCO 偵測 | tiny ~38 / 全模型 ~51 mAP | 很可能 | tiny 可上板，全模型共存吃緊 |
| FastestDet | 308_FastestDet | 超輕量偵測 | 極小單錨點，<1M params | 可 | 比 NanoDet 更小，板上極快 |
| YOLOX-PAI | 329_YOLOX-PAI | 改良 YOLOX 偵測 | YOLOX 改良，mAP 略升 | 可 | YOLOX 系，取小變體 |
| CrowdDet | 332_CrowdDet | 擁擠人群偵測 | EMD head，密集人群佳 | 風險 | 多為 RCNN/FPN backbone，較重 |
| DAMO-YOLO | 334_DAMO-YOLO | COCO 偵測 | tiny ~42 / s ~46 mAP | 很可能 | NAS backbone，tiny/s 可上板 |
| PP-YOLOE-Plus | 336_PP-YOLOE-Plus | COCO 偵測 | s ~43 / l ~53 mAP | 很可能 | anchor-free，取 s 變體較穩 |
| FreeYOLO | 337_FreeYOLO | COCO 偵測 | nano/tiny 可即時 | 很可能 | 取 nano/tiny 變體上板 |
| YOLOv6 | 341_YOLOv6 | COCO 偵測 | n ~37 / s ~45 mAP | 可 | YOLOv6n/s ONNX 小，板上即時 |
| EdgeYOLO | 356_EdgeYOLO | 邊緣裝置偵測 | tiny ~33 mAP，邊緣最佳化 | 可 | 專為邊緣設計，tiny 變體適合板 |
| RT-DETR | 376_RT-DETR | 即時 Transformer 偵測 | R50 ~53 mAP，~108 FPS(T4) | 風險 | ResNet50/101/HGNetv2，Transformer decoder 吃 RAM |
| naruto_handsign_detection | 386_naruto_handsign_detection | 火影手印偵測(玩具) | 自訂資料集，無公開基準 | 可 | 小型自訂 YOLOX 風格，輕量 |
| Gold-YOLO-Head-Hand | 422_Gold-YOLO-Head-Hand | 頭+手偵測 | Gold-YOLO，取小變體即時 | 可 | PINTO 作者系列，n 變體小 |
| Gold-YOLO-Body | 424_Gold-YOLO-Body | 人體偵測 | Gold-YOLO，依變體而定 | 可 | 取 n/s 變體上板 |
| Gold-YOLO-Body-Head-Hand | 425_Gold-YOLO-Body-Head-Hand | 身體+頭+手偵測 | Gold-YOLO，互動感知用 | 可 | PawAI 互動高度相關，取小變體 |
| YOLOX-Body-Head-Hand | 426_YOLOX-Body-Head-Hand | 身體+頭+手偵測 | YOLOX，tflite FP16 ARMv8.2 加速 | 可 | YOLOX 小變體，PawAI 高度相關 |
| YOLOX-Body-Head-Hand-Face | 434_YOLOX-Body-Head-Hand-Face | 身體+頭+手+臉偵測 | YOLOX 四類，互動感知 | 可 | 取 n/t 變體，PawAI 高度相關 |
| YOLOX-Body-Head-Hand-Face-Dist | 441_YOLOX-Body-Head-Hand-Face-Dist | 四類+畸變強化偵測 | YOLOX，抗複雜畸變 | 可 | 廣角/魚眼場景強化，取小變體 |
| YOLOX-Body-Head-Face-HandLR-Dist | 442_YOLOX-Body-Head-Face-HandLR-Dist | 含左右手分類偵測 | YOLOX，左右手區分 | 可 | 多左右手類別，取小變體 |
| YOLOX-Foot-Dist | 444_YOLOX-Foot-Dist | 腳部偵測 | YOLOX 單類腳部 | 可 | 輕量單類，板上極快 |
| YOLOX-Body-Head-Face-HandLR-Foot-Dist | 445_YOLOX-Body-Head-Face-HandLR-Foot-Dist | 多部位偵測 | YOLOX 多類，含腳 | 可 | 取小變體，PawAI 相關 |
| YOLOX-Body-With-Wheelchair | 446_YOLOX-Body-With-Wheelchair | 人體+輪椅偵測 | YOLOX，含輪椅類 | 可 | 居家無障礙場景，取小變體 |
| YOLOX-Wholebody-with-Wheelchair | 447_YOLOX-Wholebody-with-Wheelchair | 全身+輪椅偵測 | YOLOX 全身，含輪椅 | 可 | 取 n/t 變體上板 |
| YOLOX-Eye-Nose-Mouth-Ear | 448_YOLOX-Eye-Nose-Mouth-Ear | 五官偵測 | YOLOX 臉部部位 | 可 | 輕量臉部部位偵測 |
| YOLOX-WholeBody12 | 449_YOLOX-WholeBody12 | 12 類全身偵測 | YOLOX，12 部位類別 | 可 | 取小變體，PawAI 高度相關 |
| YOLOv9-Wholebody-with-Wheelchair | 450_YOLOv9-Wholebody-with-Wheelchair | 全身+輪椅偵測 | YOLOv9，依變體而定 | 可 | 取 t/n 變體，YOLOv9 系小模型小 |
| YOLOv9-Wholebody13 | 454_YOLOv9-Wholebody13 | 13 類全身偵測 | YOLOv9，13 部位 | 可 | 取 t/n 變體上板 |
| YOLOv9-Gender | 455_YOLOv9-Gender | 人體+性別偵測 | YOLOv9，body/male/female | 可 | 輕量 3 類，取小變體 |
| YOLOv9-Wholebody15 | 456_YOLOv9-Wholebody15 | 15 類全身偵測 | YOLOv9，15 部位 | 可 | 取 t/n 變體，PawAI 相關 |
| YOLOv9-Wholebody17 | 457_YOLOv9-Wholebody17 | 17 類全身偵測 | YOLOv9，含年齡分類 | 可 | 取 t/n 變體上板 |
| YOLOv9-Discrete-HeadPose-Yaw | 458_YOLOv9-Discrete-HeadPose-Yaw | 頭部離散朝向偵測 | N 變體 ~2.4MB 模型檔 | 可 | N 變體極小，朝向 8 向分類 |
| YOLOv9-Wholebody25 | 459_YOLOv9-Wholebody25 | 25 類全身偵測 | YOLOv9，25 細部位 | 可 | 取 t/n 變體，PawAI 高度相關 superset |
| RT-DETRv2-Wholebody25 | 460_RT-DETRv2-Wholebody25 | Transformer 全身偵測 | RT-DETRv2，25 部位 | 風險 | Transformer decoder，較重、共存風險 |
| YOLOv9-Phone | 461_YOLOv9-Phone | 手機偵測 | YOLOv9 單類手機 | 可 | 輕量單類，取小變體 |
| YOLOv9-Shoulder-Elbow-Knee | 463_YOLOv9-Shoulder-Elbow-Knee | 肩肘膝偵測 | YOLOv9 3 類關節 | 可 | 輕量關節框偵測 |
| YOLOv9-Wholebody28 | 464_YOLOv9-Wholebody28 | 28 類全身偵測 | n/t ~ YOLO26n 級別 | 很可能 | 變體相依，n/t 可上板、大變體吃緊 |
| DEIM-Wholebody28 | 465_DEIM-Wholebody28 | DETR 式全身偵測 | DEIM，28 部位 | 風險 | DETR-based decoder，Transformer 較重 |
| YOLOv9-Wholebody28-Refine | 468_YOLOv9-Wholebody28-Refine | 28 類全身偵測(精修) | YOLOv9，精修版 28 類 | 很可能 | 變體相依，取 t/n 變體上板 |
| YOLO-Wholebody34 | 471_YOLO-Wholebody34 | 34 類全身偵測 | N 變體 ~2.4MB(FP32 ONNX) | 可 | N 變體極小，最完整骨架 superset |
| DEIMv2-Wholebody34 | 472_DEIMv2-Wholebody34 | DETR 式 34 類偵測 | DEIMv2，34 部位 | 風險 | DEIMv2 Transformer，視 backbone 而定 |
| HISDF | 473_HISDF | 偵測×深度×姿勢×分割多任務 | 多任務一體，無單一基準 | 風險 | 多 head 多任務，計算與 RAM 負擔重 |
| UHD | 482_UHD | 超小人體/物件偵測 | 64x64 極小輸入 | 可 | 64x64 微型模型，板上極快 |
| DEIMv2-Wholebody40 | 485_DEIMv2-Wholebody40 | DETR 式 40 類偵測 | DINOv3-X ViT backbone+DETR decoder(80) | 風險 | ViT backbone，記憶體與算力高、可能爆 8GB |
| DEIMv2-Wholebody49 | 488_DEIMv2-Wholebody49 | DETR 式 49 類偵測 | DINOv3-X ViT backbone+DETR decoder(12) | 風險 | ViT backbone，最重變體、8GB 共存風險最高 |

**建議硬體**：互動主線優先取 PINTO 自家 Wholebody / Body-Head-Hand 的 n/t 小變體（132 YOLOX-nano、459/464/471 YOLOv9-t、174 PicoDet、072 NanoDet、308 FastestDet），ONNX→TensorRT FP16 與板上已驗證的 YOLO26n+RTMPose-lw 同級，可與 face+ASR+TTS+ROS2 共存；避免 ViT/DETR 系（485/488/460/465/472/376/089）與兩階段 R-CNN（008/226/264/332）在 8GB 上與其他模型並跑。

---

## 3. 3D Object Detection

本類別涵蓋從單張影像、裁切後車輛框、或 LiDAR 點雲推估「物體 3D 框 / 姿態 / 朝向」的模型，應用集中在自駕（KITTI 車輛 3D 框）與機器人抓取（6DoF 物件姿態）。對 PawAI 而言，這些多半屬「研究展示」性質——多數需要前置 2D 偵測器、相機內參或 3D LiDAR 點雲，且公開基準幾乎都跑在桌面 GPU 上，Jetson 上實測數據缺乏。整體部署可行性看格式（六者皆有 ONNX）多於看模型大小：純 CNN 回歸頭可上板，但 LiDAR/單目自駕 pipeline 的「輸入需求」才是真正的落地門檻，而非算力。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| Objectron | 036_Objectron | MediaPipe 單/雙階段日常物件 3D 邊框（cup/chair/sneakers/camera）+ ssd_mobilenetv2 偵測 | 無公開 mAP；MediaPipe 行動端輕量模型（~224 輸入），原生 CPU/行動 GPU 可即時 | 可 | TFLite 出身、ONNX 已導出，屬小型 CNN（與已上板 BlazePose/YOLO26n 同級）。類別固定為少數家居物件，PawAI 互動最相關的一支 |
| 3D BBox estimation (autonomous driving) | 063_3d-bounding-box-estimation-for-autonomous-driving | 自駕：對 2D 偵測裁切框回歸 3D 尺寸/朝向（Deep3DBox 風格） | 依變體而定/無公開基準（KITTI 車輛朝向）；backbone 為輕量 CNN 回歸頭 | 很可能 | 僅 ONNX，無量化變體；需上游 2D 車輛偵測器供框。車輛場景與居家無關，僅技術展示用 |
| SFA3D | 107_SFA3D | LiDAR 點雲 BEV 鳥瞰圖 anchor-free 3D 物件偵測（Car/Ped/Cyclist） | KITTI 上 FPN-ResNet18，作者宣稱「super fast」桌面 GPU 可即時；無 Jetson 公開數字 | 風險 | ONNX(608×608) 格式 OK，但**輸入是 3D LiDAR 點雲 BEV**——Go2 僅 RPLIDAR 2D 雷達，無法供應此輸入；中型 CNN 算力可承受但 pipeline 不成立 |
| EgoNet | 263_EgoNet | 自駕：兩階段車輛 3D 朝向（heatmap 256×256 → FC 66 維） | 無公開 mAP（KITTI 朝向）；heatmap 階段 batch=偵測到的車數，量大時線性放大 | 很可能 | ONNX 已導出（heatmap_Nx3x256x256 + fc_Nx66 兩檔串接），需先用 YOLO/SSD 偵測車輛框。中型 CNN，但需自備偵測器與相機標定 |
| DID-M3D | 321_DID-M3D | 單目影像 3D 物件偵測（instance depth 解耦為視覺深度+屬性深度，ECCV 2022） | KITTI Car 單目 SOTA 級（論文宣稱新 SOTA）；DLA-34 backbone，桌面 GPU 推理 | 風險 | zoo 中**僅 ONNX、無任何量化/FP16 變體**；DLA-34 較重、含可變形/解耦深度頭，8GB 上未實測，記憶體與 TRT 轉換風險偏高 |
| YOLO-6D-Pose | 363_YOLO-6D-Pose | 物件 6DoF 姿態估計（YCB-Video，TI edgeai 版＋PINTO 特化版） | 無公開 Jetson 基準；YOLOX-based，TI 為 edge 推理設計，桌面/嵌入式可達互動級 FPS | 很可能 | ONNX 已導出（TI edgeai-modelzoo 出身，本就針對 edge 最佳化）。6DoF 物件姿態對機械手抓取有用，但 PawAI 無抓取需求 |

**建議硬體**：六者皆有 ONNX → onnxruntime-gpu(jp6/cu126)+TensorRT-EP FP16 可走；036 Objectron 屬小型 CNN 確定可上板，063/263/363 為中型 CNN 很可能可行但需自備上游偵測器與標定，107 SFA3D 受限於「需 3D LiDAR 點雲」與 Go2 的 2D RPLIDAR 不相容、321 DID-M3D 因 DLA-34 偏重且零量化變體列風險；整體與居家互動主軸關聯低，僅 036 具實質導入價值。

---

## 4. 2D/3D Face Detection

本類 41 個資料夾橫跨四個子任務：**2D 人臉偵測**（YuNet/SCRFD/RetinaFace/BlazeFace 等）、**人臉對齊/landmark**（FaceMesh、PIPNet、STAR、MobileFaceNet 等）、**頭部姿態 head pose**（6DRepNet、WHENet、DirectMHP、Opal23 等）以及兩個**人頭（非人臉）偵測器**（YOLOv7_Head、Gold-YOLO-Head）。對 PawAI 而言這是「互動感知」的核心倉庫——人臉偵測決定有沒有人、頭部姿態判斷朝不朝向機器狗、對齊提供識別所需的對齊基準。好消息是 README 顯示**每一格都產出 ONNX**，沒有任何模型卡在 EdgeTPU/CoreML/TFJS 死路，主流走 onnxruntime-gpu + TensorRT-EP FP16 即可；多數為 <50MB 的輕量 CNN，與專案現役 YuNet+SFace 同級、已在板上實證。風險僅集中在少數 Transformer（SLPT）、VGG 重骨幹（DSFD_vgg）與 YOLO 全圖偵測器（高解析度、同跑時吃 8GB 餘量）。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:---:|------|
| Head Pose Estimation | 025_head_pose_estimation | 經典 3-angle 頭部姿態回歸 | 依變體而定，AFLW2000 yaw/pitch/roll MAE 通常 5-7° | 很可能 | 小型 CNN(64x64 級)，ONNX 直跑；無公開統一基準 |
| BlazeFace | 030_BlazeFace | MediaPipe 輕量人臉偵測（SSD-like） | mobile GPU <10ms 全管線；近距 6-landmark | 可 | MobileNetV1/V2 骨幹、極小模型，CPU 即可，與現役同級 |
| FaceMesh | 032_FaceMesh | MediaPipe 468 點 3D 臉網格 | 行動裝置 即時(<10ms)，逐點 regress | 可 | TFLite 來源已轉 ONNX，輕量；專案已用 mediapipe |
| DSFD_vgg | 040_DSFD_vgg | Dual Shot Face Detector（VGG 骨幹） | WIDER hard AP ~0.90，但 VGG 重 | 風險 | VGG16 骨幹參數多、高解析度，8GB 同跑會吃餘量，需單測 |
| DBFace | 041_DBFace | anchor-free 人臉偵測+5 landmark | WIDER hard AP ~0.83(MobileNet 版) | 很可能 | MobileNetV2/V3，320~800 多解析度；中型未實測 |
| Face Landmark | 043_face_landmark | 基礎人臉 landmark 回歸 | 依變體而定/無公開基準 | 可 | 輕量 CNN，ONNX 小檔，CPU 級 |
| Iris Landmark | 049_iris_landmark | MediaPipe 虹膜/眼周 landmark | 行動即時，眼周精細點 | 可 | MediaPipe 極小模型，做注視/眨眼可選 |
| CenterFace | 095_centerface | anchor-free 人臉偵測+landmark | WIDER hard AP ~0.816，~7MB | 可 | MobileNetV2 anchor-free，小且快，適合即時 |
| RetinaFace | 096_RetinaFace | 單階人臉偵測+5 landmark | WIDER hard AP ~0.91(R50)/~0.82(MNet) | 可 | MobileNet0.25 版極輕；ResNet50 版偏重，選輕版 |
| WHENet | 106_WHENet | 全範圍 wide-range 頭部姿態 | AFLW2000 MAE ~4.4°，BIWI ~3.5° | 很可能 | EfficientNet 級骨幹 224x224，ONNX；中型未實測 |
| SCRFD | 129_SCRFD | SOTA 高效人臉偵測+landmark | SCRFD-500M WIDER hard AP ~0.68-0.77 級，全難度最佳 | 可 | **GROUND TRUTH**：~0.57M 參數，ONNX ~2MB，與現役同級 |
| head-pose-estimation-adas-0001 | 134_head-pose-estimation-adas-0001 | OpenVINO 車用頭部姿態(yaw/pitch/roll) | 60x60 輸入，車用級精度 | 可 | 輸入極小、模型輕，已轉 ONNX 可直跑 |
| YuNet | 144_YuNet | 毫秒級超輕量人臉偵測 | WIDER 競賽級 AP，<1MB | 可 | **GROUND TRUTH**：~75-90K 參數，ONNX <1MB，專案現役 |
| face-detection-adas-0001 | 227_face-detection-adas-0001 | OpenVINO 車用人臉偵測(SSD) | 384x672，MobileNet-SSD 車用級 | 可 | PriorBox 需配 0.npy；MobileNet SSD 輕量 |
| Face-Mask-Detection | 250_Face-Mask-Detection | 口罩配戴偵測(SSD) | 偵測 mask/no-mask，SSD 級 | 可 | PriorBox 需 0.npy；輕量 SSD，COVID 期模型 |
| face_landmark_with_attention | 282_face_landmark_with_attention | MediaPipe 含注意力的精細 landmark | 192x192，唇/眼/虹膜加密 | 很可能 | MediaPipe attention 版，比基礎 FaceMesh 重但仍中小 |
| face-detection-0100 | 289_face-detection-0100 | OpenVINO 輕量人臉偵測 | 256x256，PriorBoxClustered | 可 | 小輸入 MobileNet SSD，需 0.npy 配 anchor |
| Lightweight-Head-Pose-Estimation | 293_Lightweight-Head-Pose-Estimation | 輕量頭部姿態 | 224x224，輕量 CNN | 可 | 設計即為 lightweight，ONNX 小檔 |
| 6DRepNet | 300_6DRepNet | 6D 旋轉表示頭部姿態 | AFLW2000 MAE ~3.63°，BIWI ~4.91°（SOTA 級） | 很可能 | RepVGG 級骨幹 224x224，~10-30MB ONNX；中型未實測 |
| YOLOv4_Face | 301_YOLOv4_Face | YOLOv4 全圖人臉偵測 | 480x640，YOLOv4 級 mAP | 很可能 | YOLOv4 骨幹偏重、高解析度，同跑需測 RAM |
| SLPT | 302_SLPT | Sparse Local Patch Transformer 對齊 | WFLW NME ~4.1%(SOTA 級對齊) | 風險 | **Transformer** decoder 6/12 層 256x256，8GB 有膨脹風險 |
| FAN | 303_FAN | Face Alignment Network(2D/3D) | 128/256，hourglass，2D-FAN 經典 | 很可能 | stacked hourglass 中量級，ONNX；256 版偏重 |
| SynergyNet | 304_SynergyNet | 3DMM 協同頭部姿態+3D 臉 | 224x224，3D 臉+姿態多任務 | 很可能 | MobileNet 級骨幹回歸 3DMM，中型未實測 |
| DMHead | 305_DMHead | 多模型融合 6D 頭部姿態 | 224x224，PINTO 自製融合模型 | 很可能 | 融合多分支可能較重，ONNX 可跑但需單測 |
| HHP-Net | 311_HHP-Net | 由 keypoint 推 6D 頭部姿態 | 無 LICENSE，依 keypoint 輸入 | 很可能 | 輕量回歸頭，需上游 keypoint；授權不明慎用 |
| ACR-Loss | 319_ACR-Loss | ACR-Loss 訓練的人臉對齊 | 300W/WFLW NME 競賽級 | 很可能 | 輕量對齊 CNN，ONNX；以 loss 創新為主 |
| YOLOv7_Head | 322_YOLOv7_Head | YOLOv7 人頭偵測（非人臉） | 全圖人頭 mAP，PINTO 自製 | 很可能 | YOLOv7 偏重、高解析度，多人計數可用，需測餘量 |
| DirectMHP | 383_DirectMHP | 一階多人全範圍頭部姿態(MPHPE) | AGORA/CMU-Panoptic 全範圍角度 mAP | 風險 | YOLOv5 級全圖網路，解析度大、同跑會壓 8GB 餘量 |
| YuNetV2 | 387_YuNetV2 | YuNet 第二版人臉偵測 | 640x640，WIDER 競賽級 | 可 | **GROUND TRUTH**：~85-100K 參數，ONNX ~227KB，極輕 |
| BlendshapeV2 | 390_BlendshapeV2 | 由 landmark 推 52 blendshape 表情係數 | 1/N x146x2 輸入，MediaPipe | 可 | 極小 MLP，吃 landmark 出表情權重，輕量 |
| RetinaFace_MobileNetv2 | 399_RetinaFace_MobileNetv2 | RetinaFace（MobileNetV2 版） | WIDER hard AP ~0.82-0.88 級 | 可 | MobileNetV2 骨幹輕量，比 ResNet 版省 |
| FaceMeshV2 | 410_FaceMeshV2 | MediaPipe FaceMesh 第二版 468 點 | 行動即時，精度優於 V1 | 可 | MediaPipe 輕量，與現役 mediapipe 路線一致 |
| STAR | 414_STAR | STAR loss 人臉對齊 | WFLW/300W NME 競賽級(量化誤差修正) | 很可能 | 中小型對齊 CNN，ONNX；以 loss 創新為主 |
| Gold-YOLO-Head | 421_Gold-YOLO-Head | Gold-YOLO 人頭偵測（非人臉） | 全圖人頭 mAP，Gold-YOLO 級 | 很可能 | GD-mechanism YOLO 偏重，多人計數可用，需測餘量 |
| 6DRepNet360 | 423_6DRepNet360 | 全範圍(360°) 6D 頭部姿態 | full-range，6DRepNet 全旋轉版 | 很可能 | **GROUND TRUTH**：RepVGG 級 224x224，~10-30MB ONNX |
| FaceBoxes.PyTorch | 433_FaceBoxes.PyTorch | CPU 即時 2D 人臉偵測 | WIDER 級 AP，設計即 CPU 即時 | 可 | RDCL+MSCL 輕量骨幹，極省，ONNX 小檔 |
| MobileFaceNet | 435_MobileFaceNet | 輕量人臉對齊/embedding | 112x112，MobileFaceNet 級 | 可 | 與現役 SFace 同量級的 MobileNet 嵌入，極輕 |
| Peppa_Pig_Face_Landmark | 436_Peppa_Pig_Face_Landmark | 輕量人臉 landmark | 128/256，shufflenet 級 | 可 | ShuffleNet 級輕量對齊，ONNX 小檔 |
| PIPNet | 437_PIPNet | 高效人臉 landmark(熱圖+回歸) | 300W NME ~2.6%；ResNet18 CPU 35.7FPS/GPU 200FPS | 可 | ResNet18 版輕量、CPU 即時，對齊首選之一 |
| Opal23_HeadPose | 443_Opal23_HeadPose | 全範圍 6D 頭部姿態 | 128x128 full-range | 很可能 | 小輸入回歸頭，ONNX；中型未實測 |

**建議硬體**：人臉偵測直接沿用現役 YuNet/YuNetV2/SCRFD（ONNX<1MB，可），頭部姿態挑 6DRepNet/WHENet、對齊挑 PIPNet/MobileFaceNet（皆「可」）；唯獨 SLPT(Transformer)、DSFD_vgg(VGG)、DirectMHP/YOLOv4/v7/Gold-YOLO 全圖偵測器列「風險/很可能」，上板前須單跑量 RAM 並與 D435+ASR+TTS+ROS2 錯峰，GPU 走 TensorRT-EP FP16 免校正。

---

## 5. 2D/3D Hand Detection

本類別涵蓋 6 個手部偵測／追蹤／3D 姿態模型，橫跨三條技術路線：(a) MediaPipe 系列輕量手部 pipeline（033 掌心偵測 + 21 點 landmark、094 holistic re-crop 輔助模型），架構與已上機驗證的 BlazePose/MediaPipe Hands 同級，CPU 即可即時；(b) 純偵測器 420 Gold-YOLO-Hand（YOLOv6-class，輸出手部 bbox，有公開 COCO-Hand mAP）；(c) 3D／關鍵點姿態估計（027 minimal-hand 的 DetNet+IKNet 2D+3D+MANO、403 trt_pose_hand 的 ResNet18 attention 21 點 + SVM 手勢、438 PeCLR 自監督 3D 手姿）。全部 PINTO 皆提供 ONNX 匯出，無一是純 EdgeTPU/CoreML 鎖死格式，因此在 Jetson Orin Nano SUPER 8GB 上走 onnxruntime-gpu + TensorRT-EP FP16 路徑普遍可行；風險集中在記憶體佔用而非格式。對本專案（手勢互動 70% 主軸）033/403/420 最具實戰價值。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:---:|------|
| Minimal-Hand | 027_minimal-hand | 單目 RGB → 2D+3D 手關節 + 逆運動學關節角（DetNet ResNet50 + IKNet → MANO 手部動作捕捉） | 作者宣稱桌面 GPU >100 fps；3D PCK 依資料集（無 Jetson 公開基準），輸入 128×128 | 很可能 | ONNX 全格式齊。DetNet 為 ResNet50 級偵測網，比 MediaPipe 重；Orin FP16 推估數十 fps，但 DetNet+IKNet 兩段需各自轉 TRT。記憶體中等，互動場用單手 motion-capture 才划算 |
| Hand_Detection_and_Tracking | 033_Hand_Detection_and_Tracking | MediaPipe 手部 pipeline：BlazePalm 掌心偵測 + Hand Landmark 21 點 + 手勢/手語辨識 | 與已上機 MediaPipe Hands 同級，CPU 即時（單手 ~15-30 fps）；輸入 palm 128/192、landmark 224 | 可 | 全格式匯出（含 ONNX/TFLite）。最貼合本專案手勢主線，等同現役 Gesture Recognizer 路線；CPU 跑即可、GPU 0%，與 face+ASR+TTS 共存無壓力 |
| hand_recrop | 094_hand_recrop | MediaPipe Holistic 的手部 re-crop 輔助回歸模型（從粗略 ROI 精修手部裁切框，餵給後段 landmark） | 極小輔助模型、無獨立精度指標（依 holistic pipeline 而定），輸入 256×256 | 可 | 純輔助件，不單獨產生偵測結果，需搭 033/holistic 全套才有意義。ONNX 全格式；體積小、負載可忽略 |
| trt_pose_hand | 403_trt_pose_hand | 即時手部姿態（ResNet18 attention，21 keypoint）+ SVM 手勢分類（6 類：fist/pan/stop/fine/peace/no-hand） | NVIDIA 官方稱可於 Jetson Xavier NX 即時；輸入 224×224，Orin SUPER 推估更高 fps（無本機實測），SVM 分類負載可忽略 | 可 | 原生為 Jetson 設計、proven-class。ONNX 匯出後走 TRT FP16；ResNet18 體積小、記憶體安全。手勢 6 類與本專案互動動作高度對位，值得實測 |
| Gold-YOLO-Hand | 420_Gold-YOLO-Hand | 純手部偵測器（Gold-YOLO / YOLOv6-class，Gather-and-Distribute neck），輸出手 bbox | COCO-Hand mAP@0.5 N=69.2 / S=72.5 / M=77.3 / L=78.3；mAP@0.50:0.95 40.4-48.4。輸入 480×640，N/S 體積小可即時 | 可 | ONNX 含 NMS 後處理融合（`1x3x480x640`）。N/S 與已上機 YOLO26n 同量級，TRT FP16 GPU 高佔用但 <8GB；只給 bbox，需配 033/403 才有 21 點手勢 |
| PeCLR | 438_PeCLR | 自監督對比學習 3D 手姿估計（單目 RGB → 2D+3D 手關節，ResNet backbone） | FreiHAND 等 3D PCK 依變體而定（無 Jetson 公開基準）；輸入 224×224。README 註明僅右手偵測正確 | 很可能 | 僅 ONNX（無多格式）。ResNet 級 backbone、單手 3D；Orin FP16 推估可即時但未實測，記憶體中等。右手限制 + 學術 3D 取向，互動主線實用度低於 033/403 |

**建議硬體**：手勢互動主線優先 033（MediaPipe 21 點，CPU 即時、與現役 face/ASR/TTS 共存零壓力）或 403_trt_pose_hand（ResNet18+TRT FP16，原生 Jetson、附 6 類手勢）；需手 bbox 框選時加 420 Gold-YOLO-Hand N/S（TRT FP16）；027/438 屬 3D motion-capture 進階用途，可跑但記憶體/雙段轉換成本較高，非互動主線首選。

---

## 6. 2D/3D Human/Animal Pose Estimation

本類別共 27 個資料夾，涵蓋人體/動物/手部的 2D 與 3D 姿態估計，是 PawAI 互動主線（姿勢觸發動作、跌倒偵測）最直接相關的一節。架構橫跨四代：早期 MobileNet/CMU heatmap（PoseNet、tf_pose、mobilenetv2/v3）、現代輕量 top-down（MoveNet、RTMPose、Lite-HRNet）、高精度 CNN（HRNet、Higher-HRNet、CPN）、以及 2D→3D lifting transformer（P-STMO、MHFormer、HTNet、STCFormer、PoseAug）。幾乎所有資料夾都提供 ONNX 匯出，這正是 Orin Nano 上已驗證可走 TensorRT-EP FP16 的路徑；主要變數在「模型大小 vs 8GB 統一記憶體餘量」與「lifting 模型需另接上游 2D 偵測器」。專案目前主線已用 MediaPipe Pose（=053 BlazePose 同源）+ RTMPose-lw，本節其餘多為同級或可替換方案。

| 模型 | folder | 功能 | 表現（代表性指標） | Jetson 8GB | 備註 |
|---|---|---|---|:---:|---|
| Posenet | 003_posenet | 單/多人 2D 17-keypoint（MobileNet/ResNet backbone） | COCO 約 65-70% AP；行動端 30+ FPS | 可 | 老模型，ONNX 小 CNN；精度低於 MoveNet，留作 baseline |
| Mobilenetv2 Pose | 007_mobilenetv2-poseestimation | MobileNetV2 + CPM/PAF heatmap 2D 姿態 | 依變體而定，輕量級約 60% AP | 可 | ONNX 小型，純 CNN，CPU/GPU 皆可 |
| Human Pose 3D 0001 | 029_human-pose-estimation-3d-0001 | OpenVINO OMZ 單人 3D 姿態（RGB→19 點 3D） | 無公開 COCO AP；論文級即時 | 可 | 多解析（180x320~720x1280）ONNX；原為 OpenVINO 但本 zoo 有 ONNX 匯出 |
| BlazePose | 053_BlazePose | MediaPipe 全身 33-keypoint（含 2.5D z） | lite ~2-3MB / full ~6MB；行動端 30+ FPS | 可 | 已在本板實測（CPU tiny），即專案 pose 主線同源 |
| ThreeDPose Unity Barracuda | 065_ThreeDPoseUnityBarracuda | 單人全身 3D 姿態（Unity Barracuda 用） | 無公開基準；展示級即時 | 很可能 | ONNX 中型，未量測；3D 輸出 z 軸穩定度依距離 |
| tf_pose_estimation | 080_tf_pose_estimation | OpenPose CMU PAF 多人 2D 姿態 | COCO 約 58-62% AP；CPU 慢 | 可 | ONNX 可走 GPU；多人 bottom-up，後處理較重 |
| EfficientPose | 084_EfficientPose | EfficientNet backbone 單人 2D 姿態 | MPII 約 88-91% PCKh（RT 變體）；輕量 | 可 | SinglePose；ONNX 小型，效率取向 |
| Mobilenetv3 Pose | 088_mobilenetv3-poseestimation | MobileNetV3 + multi-person PAF 2D 姿態 | 依變體而定，輕量約 60% AP | 可 | ONNX 小 CNN，比 v2 略快 |
| MoveNet | 115_MoveNet | 單人 2D 17-keypoint（lightning/thunder） | 單人 COCO 子集 Lightning 75.1% / Thunder 80.6% mAP；行動端 30+ FPS（Lightning <7ms） | 可 | ONNX 小型，邊緣首選；可直接替換現行 pose |
| MoveNet MultiPose | 137_MoveNet_MultiPose | 多人 2D（最多 6 人，lightning） | 多人即時；精度略低於單人版 | 可 | 小尺寸（192~320）優先；1280x1920 FLOPs 暴增需避開 |
| MobileHumanPose | 156_MobileHumanPose | 單人 3D 姿態（MobileNet backbone，root-relative） | Human3.6M 約 50-56mm MPJPE 等級；輕量 | 可 | ONNX 小型 3D；需搭配人物 bbox 偵測 |
| 3DMPPE POSENET | 157_3DMPPE_POSENET | 多人 3D 姿態（top-down RootNet+PoseNet） | Human3.6M 約 53mm MPJPE | 很可能 | ResNet backbone ONNX 中型，未量測；多解析可選小尺寸 |
| PoseAug | 265_PoseAug | 2D→3D lifting（GCN/MLP/STGCN/VideoPose） | Human3.6M 約 50-58mm MPJPE | 可 | 輸入 Nx16x2 關鍵點，極小 ONNX；須先接 2D 偵測器 |
| Lite-HRNet | 268_Lite-HRNet | 輕量高解析 top-down 2D 姿態 | COCO 約 64-70% AP；參數/FLOPs 為小 HRNet 一半 | 可 | ONNX 小 CNN，邊緣友善，COCO/MPII |
| Higher-HRNet | 269_Higher-HRNet | 高解析 bottom-up 多人 2D 姿態 | COCO test-dev 約 70.5% AP | 很可能 | ONNX 中型；輸入 192x320~736x1280，高解析會吃滿 GPU，選小尺寸 |
| HRNet | 271_HRNet | 高解析 top-down 2D 姿態（W32/W48） | COCO 約 75-77% AP（W48@384） | 很可能 | 本 folder 僅 ONNX 匯出；W48 較重，建議 W32@256x192 |
| E2Pose | 333_E2Pose | 端到端單階段多人 2D 姿態 | COCO/CrowdPose 約 65-70% AP；即時 | 可 | ONNX，end-to-end 免 NMS/heatmap 後處理，部署簡潔 |
| P-STMO | 350_P-STMO | 2D→3D lifting（時序自監督，in-the-wild） | Human3.6M 約 42-44mm MPJPE | 可 | 本 folder 僅 ONNX；輸入為 2D 關鍵點序列，模型小但需上游 2D |
| MHFormer | 355_MHFormer | 2D→3D lifting（multi-hypothesis transformer） | Human3.6M 約 43mm MPJPE | 很可能 | transformer 但作用於關鍵點序列非影像，FLOPs 中等；ONNX 已匯出 |
| HTNet | 365_HTNet | 2D→3D lifting（hierarchical transformer） | Human3.6M 約 47mm MPJPE | 可 | 小型 lifting transformer（Nx17x2 輸入），ONNX 輕 |
| STCFormer | 392_STCFormer | 2D→3D lifting（spatio-temporal transformer） | Human3.6M 約 40-44mm MPJPE | 很可能 | 時序窗口越長 FLOPs 越高；ONNX 已匯出，選短窗口 |
| RTMPose WholeBody | 393_RTMPose_WholeBody | 全身 133-keypoint 2D（臉+手+身+腳） | RTMPose-m COCO 75.8% AP；GTX1660Ti 430+ FPS / i7 90+ FPS（CPU） | 很可能 | m@256x192 權重數十 MB ONNX，FP16；WholeBody 後處理較重，未在板量測 |
| RTMPose Animal | 394_RTMPose_Animal | 動物 2D 姿態（AP-10K 等） | AP-10K 約 70%+ AP（m 級） | 可 | ONNX 小型，與身體版同架構；守護/互動可選用 |
| trt_pose | 402_trt_pose | NVIDIA 邊緣即時多人 2D 姿態（PAF） | 為 Jetson 原生設計；Nano 級即時 | 可 | 本就針對 Jetson 最佳化，ONNX 走 TRT 最對味 |
| pytorch_cpn | 412_pytorch_cpn | Cascaded Pyramid Network top-down 2D 姿態 | COCO 約 72-73% AP | 可 | ResNet backbone ONNX 中小型；需人物 bbox |
| RTMPose Hand | 427_RTMPose_Hand | 手部 21-keypoint 2D 姿態 | ~5-6M params / ~2.58 GFLOPs；即時 | 可 | ONNX 小型 FP16，與專案 gesture 互補，已驗證可行 |
| ViTPose | 440_ViTPose | ViT backbone top-down 2D 姿態（S/B/L/H） | COCO test S/B ~75.8 AP、L 78.3 AP、G 80.9+ AP（944 FPS@S） | 風險 | FP16 ONNX：S ~48MB / B ~170MB / L ~600MB；B/L 在 8GB 共存下吃緊，僅 S 較可控 |

**建議硬體**：互動 pose 主線維持 BlazePose（已實測）或可平替 MoveNet Lightning / RTMPose-m（ONNX→TRT FP16）；需要全身/手部時用 393/427 RTMPose；3D 走 156 MobileHumanPose 或「MoveNet 2D + P-STMO/HTNet lifting」組合（lifting 模型本身極小）；ViTPose 只在離線標註用 S 版，B/L 不建議在 8GB 與 D435+face+ASR+TTS+ROS2 共存時上線。

---

## 7. Depth Estimation (Monocular/Stereo)

本類別共 54 個資料夾，涵蓋三大子族：**單目深度（Monocular）**（MiDaS / Monodepth2 / PackNet / Lite-Mono / Depth-Anything 等，輸出相對或度量深度）、**雙目立體匹配（Stereo Matching）**（HITNET / CREStereo / IGEV / ACVNet 等，需左右兩張影像算視差）、與**深度補全（Depth Completion）**（msg_chn / EMDC，RGB+稀疏深度補密）。評估指標單目慣用 **AbsRel / δ1**（越低/越高越好），立體慣用 **EPE（end-point-error，px）與 D1 誤匹配率**。對 Jetson 而言關鍵分水嶺有三：(1) **ViT/Transformer backbone**（DPT、NeWCRFs、ZoeDepth、Depth-Anything、GLPDepth）記憶體與算力吃緊；(2) **3D cost-volume 立體網路**（PSMNet 系、CasStereoNet、ACVNet、IGEV）算力極重；(3) 多數中小 CNN（MiDaS-small、Monodepth2、PyDNet、FastDepth、Lite-Mono、CGI-Stereo、Fast-ACVNet）走 ONNX→TensorRT FP16 都很可行。**全部都有 ONNX 匯出**，無只限 EdgeTPU/CoreML 的死路項目，主要風險是高解析下的 RAM 與延遲。實務上機器狗已有 D435 主動式立體深度可直接讀，這些網路多屬「研究/備援」性質。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| BTS (Local Planar Guidance) | 009_multi-scale_local_planar_guidance_for_monocular_depth_estimation | 單目度量深度 (DenseNet/ResNet enc + LPG) | KITTI AbsRel ~0.059 / δ1 ~0.956；DenseNet161 重 | 風險 | 僅 FP32 匯出；DenseNet161 backbone 大、高解析吃 RAM；ResNet50 變體較可控 |
| Monodepth2 | 014_tf-monodepth2 | 自監督單目深度 (ResNet18 enc-dec) | KITTI AbsRel ~0.115 / δ1 ~0.877；ResNet18 輕 | 很可能 | ONNX 齊全、ResNet18 小網；FP16 TRT 即時可期 |
| struct2depth | 028_struct2depth | 自監督單目深度+egomotion | KITTI AbsRel ~0.108（mono）；輸入低解析 | 很可能 | 輕量 CNN；ONNX OK；舊 TF1 來源 |
| DenseDepth | 064_Dense_Depth | 單目深度 (DenseNet169 enc + upsample) | NYU AbsRel ~0.123 / δ1 ~0.846；DenseNet169 偏重 | 風險 | 全格式齊全但 DenseNet169 編碼器大，480x640 易吃 2GB+ |
| Footprints | 066_footprints | 單目「可走地面/隱藏地面」深度 | 無單一公開 AbsRel（任務特化）/依變體而定 | 很可能 | ResNet enc 中小型；ONNX OK |
| MiDaS (v2.1) | 067_MiDaS | 單目相對深度 (ResNet/EfficientNet enc) | 零樣本泛化佳；small 變體即時、large 重 | 很可能 | small/ResNet 版可即時；large 版偏風險，選輕變體 |
| MiDaS v2 (small) | 081_MiDaS_v2 | 單目相對深度 (MiDaS-small) | MiDaS-small ~21MB、行動裝置級即時 | 可 | 有 EdgeTPU 全量化證明其輕量；ONNX→TRT FP16 上機穩 |
| CoEx | 135_CoEx | 即時雙目立體匹配 (GCE cost volume) | SceneFlow EPE ~0.69；原生即時(~27 FPS GPU) | 很可能 | WIP，僅 ONNX/OpenVINO；輕量 cost-volume，FP16 可期 |
| HITNET | 142_HITNET | 高效雙目立體 (分層 tile + 迭代細化) | KITTI D1 ~1.98%；設計為即時 | 很可能 | WIP/有 OpenVINO issue；中低解析(240x320)較穩，高解析吃力 |
| FastDepth | 146_FastDepth | 即時單目深度 (MobileNet enc + NNConv5) | NYU AbsRel ~0.165；~3.9M 參數、MCU/邊緣級即時 | 很可能 | ~3.9M 參數(MobileNet enc ~3.3M + NNConv decoder)；ONNX→TRT FP16 即時 |
| PackNet-SfM | 147_PackNet-SfM | 自監督單目度量深度 (3D packing) | DDAD/KITTI AbsRel ~0.07（重模型）；本 zoo 僅 ResNet18 backbone | 很可能 | 僅轉 ResNet18 變體（packing 3D 太重未轉）；ResNet18 版可上機 |
| LapDepth | 148_LapDepth | 單目深度 (拉普拉斯金字塔殘差) | KITTI AbsRel ~0.059 / NYU ~0.105；ResNeXt enc 偏重 | 風險 | ResNeXt101 backbone 大；高解析(720x1280)會爆 RAM，低解析可試 |
| depth_estimation (DenseDepth-lite) | 149_depth_estimation | 單目深度 (輕量 enc-dec) | NYU 級、依變體而定/無統一基準 | 很可能 | 多解析度匯出齊全、有 EdgeTPU 證明輕量；ONNX OK |
| MobileStereoNet | 150_MobileStereoNet | 行動級雙目立體 (2D/3D MobileNet cost) | SceneFlow EPE ~1.14（2D 版）；設計為輕量 | 風險 | WIP，僅轉換腳本（無現成 ONNX）；2D 版上機可期、3D 版重 |
| MegaDepth | 153_MegaDepth | 單目相對深度 (hourglass，野外場景) | 相對深度泛化佳；無 AbsRel 主指標 | 很可能 | hourglass CNN 中型；192x256/384x512 ONNX OK |
| HR-Depth | 158_HR-Depth | 高解析自監督單目深度 | KITTI AbsRel ~0.109 / δ1 ~0.883；輕量化 Monodepth2 改進 | 很可能 | 輕量 enc-dec；ONNX 齊全、FP16 即時可期 |
| EPCDepth | 159_EPCDepth | 自監督單目深度 (data grafting) | KITTI AbsRel ~0.091 / δ1 ~0.907；ResNet50 enc | 很可能 | ResNet50 中型；中解析穩，720x1280 偏風險 |
| msg_chn_wacv20 | 160_msg_chn_wacv20 | 深度補全 (RGB+稀疏→密集深度) | KITTI DC RMSE ~0.76m；多階段 CNN 輕量 | 很可能 | 需稀疏深度輸入（如 LiDAR/D435）；輕量、ONNX 多解析齊全 |
| PyDNet | 162_PyDNet | 超輕量金字塔單目深度 | KITTI AbsRel ~0.146；~2M 參數、CPU 即時 | 可 | 極輕(~2M 參)，原設計就跑 CPU/嵌入式；ONNX→TRT FP16 餘裕大 |
| MADNet | 164_MADNet | 即時自適應雙目立體 (推論模式) | KITTI D1 ~4-8%（自適應）；即時設計 | 很可能 | 僅推論(無 backprop)；輕量 cost-volume，中解析 FP16 可期 |
| RealtimeStereo | 165_RealtimeStereo | 即時雙目立體匹配 | KITTI 即時(~30+ FPS 桌面 GPU)/依變體而定 | 很可能 | 輕量化設計、多解析匯出；180x320 上機穩 |
| Insta-DM | 166_Insta-DM | 動態場景自監督單目深度+物件運動 | KITTI 級、任務特化/依變體而定 | 很可能 | ResNet enc 中小；ONNX 多解析齊全 |
| DPT (hybrid) | 167_DPT (168_DPT) | 單目深度 (ViT-hybrid Transformer enc) | NYU AbsRel ~0.110；ViT 推論重 | 風險 | ViT backbone；480x640 記憶體/延遲吃緊，需 FP16 並限解析 |
| MVDepthNet | 173_MVDepthNet | 多視角單目深度 (cost volume + enc-dec) | ScanNet 級/依變體而定；256x320 | 很可能 | 僅 OpenVINO/ONNX；中型 CNN，固定低解析可上機 |
| stereoDNN | 202_stereoDNN | NVIDIA 雙目立體 (NVSmall/NVTiny/ResNet18) | KITTI 即時(原為 DriveWorks)；Tiny 版極輕 | 很可能 | NVTiny_161x513 輕；大解析(321x1025) ResNet18 偏重 |
| SRHNet | 203_SRHNet | 階層式雙目立體精修 (maxdisp192) | KITTI/SceneFlow 中高精度；cost-volume 偏重 | 風險 | 僅 ONNX；分層 cost-volume 算力重，480x640 延遲高 |
| SC_Depth_pl | 210_SC_Depth_pl | 尺度一致自監督單目深度 | KITTI AbsRel ~0.118 / NYU ~0.123；ResNet18 enc | 很可能 | ResNet18 輕；多解析 ONNX 齊全，FP16 即時可期 |
| Lac-GwcNet | 211_Lac-GwcNet | 雙目立體 (local affinity + GwcNet) | KITTI D1 ~1.8%；3D cost-volume 重 | 風險 | 僅 ONNX；3D 聚合算力大，高解析易爆 8GB |
| StereoNet | 219_StereoNet | 即時雙目立體 (低解析 cost + 精修) | SceneFlow EPE ~1.1；設計為即時邊緣 | 很可能 | 輕量化立體，180x320 上機穩；高解析偏風險 |
| W-Stereo-Disp | 235_W-Stereo-Disp | 偽光達/雙目視差→3D (深度補全式) | KITTI 3D 偵測輔助；pipeline 偏重 | 風險 | 僅 ONNX；屬重型立體+偽點雲，記憶體與延遲吃力 |
| A-TVSNet | 236_A-TVSNet | 多視角立體 (aggregated cost volume) | DTU/MVS 級/依變體而定；cost-volume 重 | 風險 | 3D cost-volume MVS 重型，480x640 偏爆界 |
| CasStereoNet | 239_CasStereoNet | 級聯雙目立體 (coarse-to-fine 3D) | KITTI D1 ~1.7%；3D cost-volume 極重 | 風險 | 僅 ONNX；級聯 3D 卷積算力極大，高解析必爆 |
| GLPDepth | 245_GLPDepth | 單目深度 (Transformer enc + 輕量 decoder) | NYU AbsRel ~0.098 / KITTI ~0.057；MiT(SegFormer)enc | 風險 | 僅 ONNX、非商用授權；Transformer enc 偏重，限解析+FP16 |
| TinyHITNet | 258_TinyHITNet | 輕量化雙目立體 (HITNet 精簡) | KITTI 級、輕量即時/依變體而定 | 很可能 | 比 HITNet 更輕；180x320 上機穩 |
| ACVNet | 266_ACVNet | 雙目立體 (attention concat volume) | KITTI D1 ~1.65% / SceneFlow EPE ~0.48；3D 重 | 風險 | 僅 ONNX；3D cost-volume 算力大，高解析爆界 |
| GASDA | 280_GASDA | 域自適應單目深度 (合成→真實 GAN) | KITTI AbsRel ~0.149；推論為生成器 CNN | 很可能 | 無 LICENSE；推論端為中型 CNN，ONNX 可上機 |
| CREStereo | 284_CREStereo | 高精度雙目立體 (遞迴級聯 + 迭代) | Middlebury/ETH3D SOTA 級；ITER 數正比延遲 | 風險 | 僅 ONNX；ITER20 極慢，ITER2/低解析可勉強，迭代越多越爆 |
| Graft-PSMNet | 292_Graft-PSMNet | 雙目立體 (特徵嫁接 + PSMNet) | KITTI D1 ~1.9%；PSMNet 系 3D cost-volume 重 | 風險 | 僅 ONNX；3D 卷積算力大，高解析爆 8GB |
| FSRE-Depth | 294_FSRE-Depth | 自監督單目深度 (特徵-語義互助) | KITTI AbsRel ~0.105 / δ1 ~0.889；ResNet enc | 很可能 | 僅 ONNX；中小 CNN，多解析可控 |
| MGNet | 296_MGNet | 單目幾何 (深度+全景分割多工，即時) | Cityscapes 即時設計；多工輸出 | 很可能 | 即時導向、輕量；ONNX 多解析齊全，FP16 可期 |
| NeWCRFs | 312_NeWCRFs | 單目深度 (Swin Transformer + neural CRF) | KITTI AbsRel ~0.052 / NYU ~0.095；Swin enc 重 | 風險 | 僅 ONNX；Swin-Large backbone，記憶體吃緊需限解析+FP16 |
| IS-Net (DIS) | 313_IS-Net | 高精度二類影像分割 (非深度，DIS 顯著物分割) | DIS5K maxFβ ~0.79；中型 enc-dec | 很可能 | 注意：此資料夾實為 DIS 分割模型(xuebinqin/DIS)非深度；ONNX 中型可上機 |
| PyDNet2 | 314_PyDNet2 | 超輕量金字塔單目深度 (PyDNet 升級) | KITTI AbsRel ~0.146；極輕 CNN、即時 | 可 | 全格式齊全含 EdgeTPU 證明極輕；ONNX→TRT FP16 餘裕大 |
| EMDC | 327_EMDC | 深度補全 (RGB+稀疏深度，高效多分支) | NYU/KITTI DC 級、輕量設計/依變體而定 | 很可能 | 需稀疏深度輸入；僅 ONNX，輕量多分支 CNN 可上機 |
| Fast-ACVNet | 338_Fast-ACVNet | 即時雙目立體 (ACVNet 加速版) | KITTI D1 ~1.7%、~45 FPS(桌面 GPU)；即時導向 | 很可能 | 僅 ONNX；專為即時設計，grid_sample(opset16)/無 grid_sample(opset11) 兩版，FP16 中解析可期 |
| CGI-Stereo | 358_CGI-Stereo | 即時雙目立體 (context-guided, 即時 SOTA) | KITTI D1 ~1.6%、~30+ FPS；輕量即時 | 很可能 | 有 FP32/FP16/ONNX；即時導向，立體類上機首選之一 |
| ZoeDepth | 362_ZoeDepth | 單目度量深度 (MiDaS-BEiT enc + metric bins) | NYU AbsRel ~0.075；BEiT-Large backbone 重 | 風險 | 僅 ONNX；BEiT/ViT-Large 編碼器，記憶體與延遲吃緊 |
| IGEV-Stereo | 364_IGEV | 雙目立體 (幾何編碼體 + 迭代 GRU) | KITTI D1 ~1.6% / SceneFlow EPE ~0.47；3D+迭代重 | 風險 | 僅 ONNX；幾何 cost-volume + 迭代，算力大、高解析爆界 |
| Lite-Mono | 371_Lite-Mono | 輕量單目深度 (CNN+Transformer 混合) | KITTI AbsRel ~0.107 / δ1 ~0.888；~3M 參數輕量 | 很可能 | 僅 ONNX；輕量混合 backbone(~3M 參)，FP16 即時可期 |
| TCMonoDepth | 384_TCMonoDepth | 影片時間一致單目深度 | 一致性導向、無單一 AbsRel/依變體而定 | 很可能 | 僅 ONNX；輕量 enc-dec，影片用途，中解析可上機 |
| MiDaS v3.1 | 397_MiDaSv3.1 | 單目相對深度 (DPT/Swin/BEiT 多 backbone) | 零樣本 SOTA；backbone 從 small(輕)到 BEiT-Large(重)皆有 | 風險 | 僅 ONNX；選 small/efficientnet 變體可上機，ViT-Large 變體爆界 |
| High-freq Stereo Matching Net | 415_High-frequency-Stereo-Matching-Network | 雙目立體 (高頻細節保留) | KITTI/ETH3D 高精度；cost-volume 偏重 | 風險 | 僅 ONNX；重型立體匹配，高解析延遲與 RAM 吃力 |
| Depth-Anything | 439_Depth-Anything | 基礎模型單目相對深度 (DINOv2 ViT enc) | 零樣本泛化 SOTA；vits14 ~25M 參 / ~50MB FP16 | 風險 | vits14 ~25M 參(~50MB FP16 權重)；ViT 推論重，FP16+限解析可勉強，vitb/vitl 爆界 |

**建議硬體**：機器狗已有 D435 主動式立體可直讀深度，故此類多屬研究/備援；若要上機**首選輕量單目**（081_MiDaS_v2-small、162_PyDNet、314_PyDNet2、146_FastDepth、371_Lite-Mono、014_Monodepth2）或**即時立體**（358_CGI-Stereo、338_Fast-ACVNet、142/258_TinyHITNet），全走 ONNX→TensorRT FP16；**避開** ViT/Swin/BEiT 系（167_DPT、312_NeWCRFs、362_ZoeDepth、439_Depth-Anything、397 large 變體）與 3D cost-volume 重型立體（211/239/266/292/364），在 8GB 統一記憶體（與 D435+face+ASR+TTS+ROS2 共用、需留 ≥0.8GB headroom）下高解析易爆界。

---

## 8. Semantic Segmentation

本類別共 44 個資料夾，涵蓋語意分割（Cityscapes/ADE20K 道路場景）、人像/自拍分割、影像去背 matting、髮絲/皮膚/耳朵等部位分割、顯著物偵測（saliency）、水下分割、LiDAR 點雲分割，以及 Segment Anything（SAM）類提示式分割。對 Jetson Orin Nano SUPER 8GB 的可部署性差異極大：PINTO 的人像/自拍/髮絲分割多為 MobileNet 級輕量 CNN（如 Selfie/Meet/BodyPix/PPHumanSeg），這些有 ONNX 匯出的小模型走 onnxruntime-gpu + TensorRT-EP FP16 幾乎都可上板；而 transformer 系（TopFormer、SparseInst、CityscapesSOTA HRNet、RGBX、SAM）與 4K matting 變體屬於記憶體與算力風險區。需特別注意：001/015/020/021 等早期資料夾在 zoo 中沒有 ONNX 匯出（只有 FP32/OpenVINO/EdgeTPU），須自行從原始碼重建 ONNX 才能上 Jetson；EdgeTPU/CoreML/TFJS/OpenVINO 格式本身在 Jetson 無效。分割輸出解析度直接決定顯存佔用，高解析（720p↑/4K）變體請降階使用。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| deeplabv3 | 001_deeplabv3 | 通用語意分割（PASCAL VOC 21 類） | DeepLabv3 VOC mIoU ~82–86%；MobileNet 骨幹 CPU 慢 | 風險 | zoo 內僅 FP32/OpenVINO，**無 ONNX 匯出**，須自行重建 ONNX 才可上 TRT |
| Faster-Grad-CAM | 015_Faster-Grad-CAM | 弱監督定位/類別熱圖（非真分割） | 無公開分割基準，屬可視化方法 | 風險 | 僅 FP32/INT8/OV，**無 ONNX**；用途偏可解釋性而非分割 |
| EdgeTPU-Deeplab | 020_edgetpu-deeplab | 邊緣端 DeepLab 語意分割 | 為 EdgeTPU 調優之 MobileNet-DeepLab，mIoU 中等 | 風險 | 有 FP16 但**無 ONNX/TFLite-GPU**；EdgeTPU 權重在 Jetson 須重轉 ONNX |
| EdgeTPU-Deeplab-slim | 021_edgetpu-deeplab-slim | 更輕的 EdgeTPU DeepLab | 比 020 更快、精度略降，無獨立公開基準 | 風險 | 同 020，缺 ONNX 直匯出，須源碼重建 |
| Mobile-Deeplabv3-plus | 026_mobile-deeplabv3-plus | 行動端 DeepLabV3+ 語意分割 | MobileNetV2 骨幹，VOC mIoU ~70–75% | 很可能 | 有 ONNX，輕量 CNN，FP16 上 TRT 應順暢 |
| BodyPix | 035_BodyPix | 人體分割 + 24 部位 parsing | MobileNet0.5/0.75/1.0 與 ResNet50；輕量版 30+FPS 級 | 很可能 | 選 MobileNet0.5/0.75 版本，ONNX→TRT FP16 可即時 |
| BiSeNetV2 | 057_BiSeNetV2 | 即時語意分割（雙路徑） | Cityscapes mIoU ~72–73%，GPU 即時級 | 很可能 | 中型 CNN，有 ONNX；FP16 上板可即時，視解析度 |
| Hair Segmentation | 060_hair_segmentation | MediaPipe 髮絲分割 | 二值髮絲遮罩，MediaPipe 行動端即時 | 很可能 | WIP；ONNX 小模型，但 zoo 僅 FP32（須確認 ONNX 完整度） |
| U^2-Net | 061_U-2-Net | 顯著物偵測/去背遮罩 | 全版 176MB 30FPS@1080Ti；輕量版 u2netp 4.7MB | 很可能 | **用 u2netp 輕量版**=可；全版 176MB 偏重屬風險邊緣 |
| ENet | 069_ENet | 即時道路語意分割 | Cityscapes mIoU ~58%，極輕量 | 很可能 | 512x1024，小型 CNN，ONNX→TRT FP16 可 |
| ERFNet | 075_ERFNet | 即時道路語意分割 | Cityscapes mIoU ~68–72% | 很可能 | 多解析度（256x512→512x1024），降解析後上板輕鬆 |
| MODNet | 078_MODNet | 人像去背 matting（無 trimap） | 即時人像 alpha matte；輕量骨幹 | 很可能 | 128–512 解析度，選 256 以下=可；512 較吃顯存 |
| MediaPipe_Meet_Segmentation | 082_MediaPipe_Meet_Segmentation | 視訊會議背景分割 | 96x160/128x128 超輕量，行動端即時 | 可 | 極小輸入 CNN，ONNX→TRT FP16，幾乎零負擔 |
| DeeplabV3-plus | 104_DeeplabV3-plus | Cityscapes 語意分割 | Cityscapes mIoU ~78–80%（高解析變體） | 風險 | 800x1600 變體顯存大；用 200x400 小解析才安全 |
| Selfie_Segmentation | 109_Selfie_Segmentation | 自拍人像分割 | 256x256 MediaPipe，行動端即時 | 可 | 已驗證類別（同 BlazePose 級輕量），ONNX→TRT FP16 |
| road-segmentation-adas-0001 | 136_road-segmentation-adas-0001 | ADAS 道路四類分割 | OpenVINO 模型，512x896 等，即時級 | 很可能 | 有 ONNX，中小型 CNN，FP16 可 |
| BackgroundMattingV2 | 138_BackgroundMattingV2 | 高解析背景去背 matting | 4K/HD 即時（需參考背景圖） | 風險 | 720x1280=很可能；2160x4096 變體顯存爆，限低解析 |
| edgetpu_seg_default_argmax | 181_models_edgetpu_..._default_argmax | EdgeTPU 語意分割（default argmax） | MobileNet-DeepLab 級，無獨立公開基準 | 很可能 | 雖標 EdgeTPU，但 zoo 含 ONNX，可走 TRT FP16 |
| edgetpu_seg_fused_argmax | 182_models_edgetpu_..._fused_argmax | EdgeTPU 語意分割（fused argmax） | 同 181，融合 argmax 降延遲 | 很可能 | 含 ONNX，FP16 上板可；fused argmax 利於延遲 |
| human_segmentation_pphumanseg | 196_human_segmentation_pphumanseg | PaddleSeg 人像分割 | PP-HumanSeg 192x192 輕量，行動端即時 | 可 | OpenCV Zoo 同款小模型，ONNX→TRT FP16，極輕 |
| CityscapesSOTA | 201_CityscapesSOTA | Cityscapes SOTA 語意分割（HMSA/HRNet 級） | Cityscapes mIoU ~85%+，重模型 | 風險 | SOTA 重骨幹；僅低解析（180x320）勉強，高解析顯存爆 |
| Matting | 206_Matting | PaddleSeg MODNet matting（多骨幹） | modnet_mobilenetv2 輕、resnet50_vd 重 | 很可能 | 選 mobilenetv2 + 256/384=可；resnet50/hrnet 變體偏重 |
| Fast-SCNN | 228_Fast-SCNN | 即時語意分割（極輕） | Cityscapes mIoU ~68%，設計目標即時 | 很可能 | 輕量 CNN，多解析度；192x384 上板輕鬆 |
| SUIM-Net | 238_SUIM-Net | 水下影像語意分割 | SUIM 8 類，RSB/VGG 骨幹，即時級 | 很可能 | RSB 版輕；ONNX→TRT FP16，選低解析 |
| RobustVideoMatting | 242_RobustVideoMatting | 即時影片去背 matting（時序） | MbNv3 版 HD 104FPS@1080Ti；ResNet50 版重 | 很可能 | **MbNv3 + 480x640 以下=可**；ResNet50 與 4K 變體屬風險 |
| SqueezeSegV3 | 246_SqueezeSegV3 | LiDAR 點雲語意分割（球面投影） | SemanticKITTI mIoU ~55–56%（SSGV3-53） | 很可能 | 投影成 2D 後是 CNN；21 版輕、53 版較重，FP16 可 |
| LIOT | 267_LIOT | 曲線/血管結構分割（醫療式） | 細長結構分割，無通用場景公開基準 | 很可能 | 多解析度小 CNN，ONNX→TRT FP16，輕量 |
| Topformer | 287_Topformer | 行動端 transformer 語意分割 | ADE20K 比 MobileNetV3 高 ~5% mIoU；Snapdragon 即時 | 風險 | Token Pyramid Transformer；Tiny 版較可行但 ViT 系上 TRT 需驗證 |
| SparseInst | 295_SparseInst | 即時實例分割（稀疏實例） | COCO instance AP ~37（r50_giam），GPU 即時 | 風險 | ResNet50 + 較大解析；instance head 較重，視顯存 |
| DGNet | 299_DGNet | 偽裝物偵測分割（camouflage） | COD10K 等偽裝資料集 Sα/Fβ 指標 | 很可能 | EfficientNet 級骨幹小 CNN，有 ONNX，FP16 可 |
| IS-Net | 313_IS-Net | 高精度去背/二值分割（DIS） | DIS5K 高品質遮罩；多達 4K 解析變體 | 很可能 | 低/中解析=可；2160x4096 變體顯存爆屬風險 |
| MOSAIC | 330_MOSAIC | 行動端語意分割（解碼聚合） | TF Official MOSAIC，行動端即時，含 fused argmax | 很可能 | zoo 已示範 Jetson Nano TRT 路徑；ONNX 可上板 |
| PIDNet | 335_PIDNet | 即時語意分割（三分支 PID） | Cityscapes mIoU ~78–80%（PIDNet-S/M/L） | 很可能 | PIDNet-S 即時輕量，動態尺寸 ONNX，FP16 可；L 版較重 |
| PP-MattingV2 | 343_PP-MattingV2 | 人像去背 matting（PaddleSeg） | HumanSeg 即時 matting，輕量設計 | 很可能 | 有 ONNX，人像 matting 小模型，FP16 上板可 |
| RGBX_Semantic_Segmentation | 347_RGBX_Semantic_Segmentation | RGB+X 多模態語意分割（CMX） | NYUDv2/Cityscapes，SegFormer/MiT 骨幹 | 風險 | transformer 多模態重模型，顯存高且需雙輸入，上板風險大 |
| Segment_Anything | 369_Segment_Anything | 提示式通用分割（SAM） | ViT-B encoder 91M 參數；M1 Pro 6.2s/張@1024 | 風險 | ViT encoder 重；mask decoder 輕但 image encoder 顯存/延遲大，非即時 |
| Skin-Clothes-Hair-Seg-SMP | 380_Skin-Clothes-Hair-Segmentation-using-SMP | 皮膚/衣物/髮絲多類分割（SMP） | 4 類人體屬性分割，SMP UNet 級 | 很可能 | UNet/SMP 中小 CNN，有 ONNX，FP16 可 |
| MagicTouch | 391_MagicTouch | MediaPipe 互動式分割（提示點） | Interactive Segmenter，行動端即時 | 很可能 | MediaPipe 小模型，ONNX→TRT FP16，輕量 |
| Ear_Segmentation | 405_Ear_Segmentation | 耳朵分割 | 耳朵二值遮罩，無大型公開基準 | 很可能 | 小型分割 CNN，ONNX，FP16 上板輕 |
| PopNet | 417_PopNet | 顯著物偵測（source-free depth 輔助） | SOD 顯著物遮罩，depth-aware | 風險 | 含 depth 分支較重，僅 ONNX 無小變體標註，顯存待驗證 |
| People_Segmentation | 466_People_Segmentation | 人像/人群分割 | UNet 二值人像遮罩，即時級 | 很可能 | UNet 中小 CNN，有 ONNX，FP16 上板可 |
| Human_Parsing | 467_Human_Parsing | 人體部位 parsing（多類） | LIP/ATR 級多類人體解析 mIoU ~50–60% | 很可能 | 視骨幹；多數人體 parsing 為中型 CNN，FP16 可，須驗解析度 |
| RHIS | 470_RHIS | 輕量 ROI 階層式人體實例分割 | 蒸餾自 EfficientNet teacher，輸入解析可自由縮放 | 很可能 | 兩階段輕量設計，解析度可降，ONNX→TRT FP16 可即時 |

**建議硬體**：本類別主力選人像/自拍/髮絲/部位分割的 MobileNet 級小模型（082 Meet、109 Selfie、196 PPHumanSeg、035 BodyPix、343 PP-MattingV2、078 MODNet、466 People_Seg、470 RHIS），ONNX→TensorRT-EP FP16，顯存 <1GB 即時可上 Jetson Orin Nano SUPER 8GB；transformer 系（287 TopFormer、295 SparseInst、347 RGBX、201 CityscapesSOTA HRNet、369 SAM）與 4K matting/IS-Net 變體屬 8GB 顯存風險區，僅低解析或離線使用；001/015/020/021 缺 ONNX 須先自原始碼重建。

---

## 9. Anomaly Detection

本類別涵蓋 2 個「視覺異常偵測」模型，皆走工業/製造缺陷檢測脈絡（MVTec AD 類資料集），共同特性是「只用正常樣本訓練、推論時找出偏離分佈的異常」。兩者皆以小型 CNN 當特徵抽取器，差別在輸出形式（影像級分類 vs. 像素級熱圖分割）與部署格式可用性。對 PawAI 居家互動機器狗而言，此類非主線需求，但若要做「環境異常/物品損壞」輔助偵測，099 是唯一在 Jetson 上直接可跑的選項。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| One_Class_Anomaly_Detection | 005_one_class_anomaly_detection | 單類別(只用正常樣本)異常偵測 — DOC 深度單類分類，MobileNetV2 特徵 + LOF 離群分類器 | 影像級異常 AUROC 依資料集而定/無此 folder 公開基準；原專案宣稱 RasPi3 上 5–150 FPS（DOC+MobileNetV2 比 DOC+VGG16 的 370ms/張快很多） | 風險 | 此 folder 只導出 FP32 / EdgeTPU(TPU) / WeightQuant / OpenVINO 欄位 — **無 ONNX、無 TF-TRT、無 TFLite-float**，主要 deployable 是 OpenVINO/Movidius blob/EdgeTPU（皆錯誤晶片）。MobileNetV2 backbone 本身極小可在 Jetson 跑，但需自行從 Keras 重新導出 ONNX；LOF 分類器是 scikit-learn CPU 端。直接拿 zoo 產物落地不可行，需重建 pipeline 才算「可」 |
| Efficientnet_Anomaly_Detection_Segmentation | 099_efficientnet_anomaly_detection_segmentation | 異常偵測 + 像素級分割熱圖 — EfficientNet-B0 特徵抽取 + 異常區域 segmentation（Grad-CAM 風格定位） | 像素/影像級 AUROC 依訓練資料而定/無此 folder 公開基準；同類 EfficientNet-based 法在 MVTec AD 多落在 image-AUROC 95%+ 區間（非此模型官方數據）。EfficientNet-B0 ~5.3M 參數、~20MB ONNX、224×224 輸入 | 可 | 全格式覆蓋含 **ONNX(opset 13)、FP16、INT8、TF-TRT、OpenVINO、CoreML、TFJS**。走 ONNX(onnxruntime-gpu + TensorRT-EP FP16) 是 board-proven 路徑，小型 CNN 記憶體占用低（遠在 8GB 預算內）。EfficientNet 含 SiLU/squeeze-excite，TRT FP16 支援良好，可直接落地 |

**建議硬體**：099(EfficientNet-B0, ONNX→TRT FP16) 在 Jetson Orin Nano 8GB 直接可跑且記憶體寬裕，為此類唯一即用選項；005 因 folder 僅導出 OpenVINO/EdgeTPU 而非 ONNX，需自 Keras 原始碼重新導出 ONNX + 重建 LOF/CPU 後處理才能上板，現成產物不建議。

---

## 10. Artistic

本類別收錄 11 個藝術化生成模型,涵蓋風格轉換(neural style transfer)、卡通/動漫化(cartoonization / anime)、灰階上色(colorization)、線稿生成(sketch)四種 image-to-image 任務,本質都是 GAN 或 encoder-decoder CNN。它們屬於「離線趣味濾鏡」,對 PawAI 的互動(手勢/語音/姿勢)與守護(陌生人/巡邏)主線沒有功能必要性。生成式模型不報 mAP/top-1 這類準確度,品質以 FID/感知評估,且 PINTO zoo 變體無公開基準;延遲隨輸入解析度(256~720)平方放大。Jetson 可部署性主要取決於 zoo 是否匯出 ONNX —— 有 ONNX 者走 onnxruntime-gpu + TensorRT-EP FP16 可上板;只有 TFLite/TF/OpenVINO/CoreML/TFJS 者在 Jetson 只能 CPU 慢跑或回原始碼自行轉檔。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|-------------------|:----------:|------|
| Artistic-Style-Transfer | 017_Artistic-Style-Transfer | TF-Lite Magenta 風格轉換(predict+transform 雙模型) | 無公開基準(風格轉換以感知品質/FID 衡量) | 風險 | zoo 僅匯出 TFLite/TF/OV/CoreML/TFJS,**無 ONNX**;Jetson 只能 TFLite-CPU 慢跑或回 source 自轉,不建議直接部署 |
| White-box-Cartoonization | 019_White-box-Cartoonization | 照片→卡通(白盒分解表面/結構/紋理的 GAN) | 無公開基準(720×720 I/O) | 很可能 | 有 ONNX + demo 腳本;U-Net 級生成器走 TRT FP16 可上板,但 720² 解析度延遲偏高,建議離線批次 |
| First_Neural_Style_Transfer | 037_First_Neural_Style_Transfer | 快速前饋風格轉換(Johnson fast-neural-style,每種風格一個 net) | 無公開基準;ONNX 模型小(每風格約數 MB) | 可 | 來自 onnx/models,FP32/ONNX/OV;輕量 CNN encoder-decoder,onnxruntime-gpu+TRT FP16 穩;每換風格需換 net |
| selfie2anime | 044_selfie2anime | 自拍→動漫臉(U-GAT-IT 注意力 GAN,256×256) | 無公開基準(重注意力 GAN) | 風險 | zoo 僅 TFLite/TF/OV/CoreML(**無 ONNX**);U-GAT-IT 參數重、顯存吃緊,Jetson 須回 source 轉檔,風險高 |
| AnimeGANv2 | 050_AnimeGANv2 | 風景照→動漫風(輕量 GAN 生成器) | 生成器約 8.6MB;原生 GPU 約 5 FPS / 200ms (依解析度) | 風險 | 模型本身極輕(可),但 zoo **無 ONNX**(只 TF/TFLite/OV/CoreML);需回原始碼自轉 ONNX 才能用 TRT,否則只 CPU |
| facial_cartoonization | 062_facial_cartoonization | 人臉卡通化(小型 CNN) | 無公開基準;小型 CNN,延遲低 | 可 | 有 ONNX(連 EdgeTPU 量化都出),CNN 體積小;onnxruntime-gpu+TRT FP16 可順跑 |
| Colorful_Image_Colorization | 068_Colorful_Image_Colorization | 灰階→彩色自動上色(Zhang VGG 式上色網) | 無公開基準(experimental 標記;原論文以 AMT 騙過率/PSNR 評) | 很可能 | 有 ONNX 但 zoo 標 experimental;VGG 骨幹中等偏重,TRT FP16 應可跑,需實測顯存 |
| arbitrary_image_stylization | 101_arbitrary_image_stylization | 任意風格轉換(Magenta v1-256,風格圖+內容圖) | 無公開基準(256×256;單一網吃任意風格) | 很可能 | 有 ONNX(magenta);predict+transform 兩段、雙輸入,256² 中等負載,TRT FP16 可上板待測 |
| Anime2Sketch | 113_Anime2Sketch | 動漫圖→線稿(UnetGenerator,512×512) | 無公開基準(512×512) | 很可能 | 有 ONNX(anime2sketch_512x512);U-Net 生成器中等,512² 延遲偏高,離線用 OK |
| EigenGAN-Tensorflow | 161_EigenGAN-Tensorflow | 可控屬性生成(多 z latent 生成器,Anime/CelebA) | 無公開基準(純生成,非 image-in) | 風險 | 多 latent 輸入生成器;zoo **無 ONNX**(只 TFLite/TF/OV/CoreML/TFJS),需回 source 自轉,且純生成對本專案無用途 |
| CoCosNet | 193_CoCosNet | 範例引導的跨域影像翻譯(correspondence + SPADE,3 輸入,256×256) | 無公開基準(ADE20k 8×V100 預訓練;v2 報 FID) | 風險 | 有 ONNX(256×256 RGB,三輸入 seg/ref/ref_seg);correspondence+SPADE 為本類最重,顯存風險最高,須嚴格 headroom 實測 |

**建議硬體**:全類別對 PawAI 主線無功能必要,優先序最低;若僅作離線趣味效果,挑有 ONNX 的 037/062(輕量,可)或 068/101/113/019(中等,很可能)在 Jetson 用 onnxruntime-gpu + TensorRT-EP FP16 單獨批次跑,務必避開與 D435+face+ASR+TTS+ROS2 同佔 8GB 統一記憶體;017/044/050/161 因 zoo 無 ONNX、193 因模型過重,均不建議在板上即時部署。

---

## 11. Super Resolution

> 注意：本節雖名為 "Super Resolution"，但 82 個資料夾實際是 PINTO 把所有「影像復原 / 增強」(image restoration / enhancement) 全部歸在這一類，包含超解析(SR)、低光增強(LLIE)、去模糊(deblur)、去霧(dehaze)、去雨/雪/雨滴(derain/desnow)、去噪(denoise)、陰影/去焦/HDR、水下/白平衡等子任務。

**類別概述**：這 82 個模型全部都有 ONNX 匯出（README 每列 ONNX 欄皆 ⚫），所以沒有任何一個因「矽晶片不對」(EdgeTPU/CoreML/OpenVINO/TFJS-only) 而直接判不可。真正決定 Jetson 8GB 可行性的是「架構類別 × 輸入解析度」：影像復原是**密集 pixel-to-pixel** 任務，模型以**完整 HxW** 跑（不像偵測會降採樣），算力與顯存隨解析度平方成長，720×1280 的 dense U-Net 比 256×256 重十倍以上。對 PawAI（居家互動機器狗）而言，這類「畫質美化」模型**幾乎都不在主線需求上**——機器狗不需要替畫面去霧/超解析；唯一有邊際價值的是低光增強(LLIE)可在夜間替 D435 影像提亮、改善人臉/手勢辨識，但這仍是 optional pre-processing，且 8GB 已被 face+ASR+TTS+ROS2 佔滿，能塞下的只剩**curve-based 微型 CNN**(Zero-DCE/SCI 等 ~10–80K params)。輕量 CNN(<~50MB ONNX)=可/很可能；Transformer(LFT/IAT/Stripformer/DehazeFormer/MAXIM…)=風險；diffusion(418)=不可。下表逐一列出全部 82 個。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| FALSR | 012_Fast_Accurate_and_Lightweight_Super-Resolution | 輕量 x2 超解析(NAS 搜出) | DIV2K x2 PSNR ~37.6dB；極輕 | 可 | 小 CNN，僅 x2、小輸入；ONNX→TRT FP16 順 |
| SMOID | 022_Learning_to_See_Moving_Objects_in_the_Dark | 極暗環境動態物體還原(raw video) | 無公開即時基準；依輸入 | 風險 | raw 多幀 3D-conv，顯存重；非主線 |
| Noise2Noise | 071_Noise2Noise | 自監督去噪(srresnet/clear only) | 依噪聲；srresnet 中等 | 很可能 | 中型 CNN，僅 clear 變體已轉 |
| Deep White Balance | 076_Deep_White_Balance | 深度白平衡校正 | 依資料集；無單一基準 | 很可能 | 多分支 U-Net，中等；小輸入可 |
| ESRGAN | 077_ESRGAN | x4 通用超解析(RRDB GAN) | Set14 x4 PSNR ~26–28dB | 風險 | RRDB ~16M params；50/100px 小 tile→很可能，大圖風險 |
| MIRNet | 079_MIRNet | 低光增強/復原(多尺度殘差) | LOL PSNR ~24.7dB | 風險 | 重 multi-scale，720×1280 變體會爆顯存；小輸入很可能 |
| Defocus Deblur (Dual-Pixel) | 086_defocus-deblurring-dual-pixel | 雙像素去焦模糊 | DPDD PSNR ~25.1dB | 很可能 | U-Net 256×256，雙輸入；中量 |
| Ghost-free Shadow Removal | 090_Ghost-free_Shadow_Removal | 去陰影(GAN) | ISTD RMSE ~5–6 | 很可能 | 256×256 固定，中型 CNN |
| SRN-Deblur | 111_SRN-Deblur | 多尺度遞迴去模糊 | GoPro PSNR ~30.1dB | 風險 | 遞迴 + 大輸入(到 1024×1280)；小輸入很可能 |
| DeblurGANv2 | 112_DeblurGANv2 | 去模糊(GAN，mobilenetv2/inception) | GoPro PSNR ~29.5dB | 很可能 | mobilenetv2 backbone 256–480 輸入可；inception+大圖風險 |
| Two-branch dehazing | 114_Two-branch-dehazing | 去霧(雙分支) | 依資料集；無統一基準 | 很可能 | 中型 CNN，240–720 解析度 |
| Real-ESRGAN | 133_Real-ESRGAN | 真實退化 x4 超解析(RRDB) | 臉 PSNR ~25dB；RRDB 16–20M，>9 TFLOPs@960×540 | 風險 | 16×16–128×128 小 tile→很可能；240×320↑大圖風險爆 8GB |
| DeepLPF | 152_DeepLPF | 可學習濾鏡影像增強 | MIT-Adobe PSNR ~23.9dB | 很可能 | 中型，參數化濾鏡；中等 |
| Learning-to-See-in-the-Dark | 170_Learning-to-See-in-the-Dark | 極暗 raw→RGB(SID U-Net) | SID PSNR ~28.9dB | 風險 | 大 U-Net + 大輸入；小輸入很可能 |
| Fast-SRGAN | 171_Fast-SRGAN | 即時 x4 超解析(輕量 GAN) | 偏速度非 PSNR；輕 | 可 | 輕量 generator，小輸入；ONNX→TRT 順 |
| Real-Time Super-Resolution | 172_Real-Time-Super-Resolution | 即時超解析(輕量) | 重即時性，PSNR 中 | 可 | 設計即為即時，64–256 小輸入 |
| StableLLVE | 176_StableLLVE | 低光影像/影片增強(時序穩定) | 無統一基準；中等 | 很可能 | 中型 U-Net，180–720；大圖偏風險 |
| AGLLNet | 200_AGLLNet | 注意力導引低光增強 | LOL 類；無統一基準 | 風險 | 大輸入到 768×1280，注意力重；小輸入很可能 |
| HINet | 204_HINet | 去模糊/去噪/去雨(Half-Instance-Norm) | GoPro deblur PSNR ~32.7dB | 風險 | 大 U-Net；256–480 中輸入很可能，大圖風險 |
| MBLLEN | 205_MBLLEN | 低光增強(多分支) | LOL 類；中等 | 很可能 | 中型多分支 CNN，180–720 |
| GLADNet | 207_GLADNet | 低光增強(全域光照感知) | LOL 類；中等 | 很可能 | 中型 CNN(No-LICENSE)，180–720 |
| SAPNet | 208_SAPNet | 去雨(合成感知注意力) | Rain100 類；中等 | 很可能 | 中型 CNN，180–720 |
| MSBDN-DFF | 209_MSBDN-DFF | 去霧(多尺度 boosted dense) | RESIDE 類 PSNR ~33dB | 風險 | dense + 大輸入重(No-LICENSE)；小輸入很可能 |
| GFN | 212_GFN | 去模糊+超解析(門控融合 x4) | 任務組合；中等 | 風險 | deblur+SR x4 雙負擔；64–256 小輸入很可能 |
| TBEFN | 213_TBEFN | 低光增強(雙分支邊緣融合) | LOL 類；中等 | 很可能 | 中型 CNN，180–720 |
| EnlightenGAN | 214_EnlightenGAN | 非配對低光增強(GAN) | LOL NIQE 改善明顯 | 很可能 | 中型 U-Net generator，192–720；大圖偏風險 |
| AOD-Net | 215_AOD-Net | 去霧(極輕量，全卷積) | SOTS PSNR ~19–20dB | 可 | 史上最輕去霧網(僅幾層 conv)，任意輸入皆順 |
| Zero-DCE-TF | 216_Zero-DCE-TF | 低光增強(零參考曲線估計) | DCE-Net ~79K params，2080Ti 500FPS@1200×900 | 可 | 微型 CNN，Jetson 上幾乎零負擔；LLIE 首選 |
| RUAS | 217_RUAS | 低光增強(Retinex 展開 NAS) | LOL 類；極輕 | 可 | NAS 搜出的微型架構(No-LICENSE)，輕 |
| DSLR | 218_DSLR | 低光/畫質增強(拉普拉斯金字塔) | 無統一基準；中等 | 很可能 | 中型 CNN，256–768 輸入 |
| HEP | 220_HEP | 低光增強(無監督直方圖均衡先驗) | LOL 類；中等 | 很可能 | 中型 CNN，180–480 |
| LFT | 222_LFT | 光場影像超解析(Transformer 2x/4x) | 光場 SR，PSNR 高 | 風險 | Transformer，僅 ONNX 轉成功；ViT 類顯存風險 |
| DA_dehazing | 223_DA_dahazing | 去霧(域適應) | RESIDE 類；中等 | 很可能 | 中型 CNN(No-LICENSE)，192–720；大圖偏風險 |
| Y-net | 224_Y-net | 去霧(Y 形小波融合) | 無統一基準；中等 | 很可能 | 中型 CNN，192–720 |
| DRBL / NTIRE2021 Two-branch | 225_NTIRE-2021-Dehazing-Two-branch | 去霧(NTIRE2021 雙分支) | NTIRE2021 賽用；重 | 風險 | 雙分支大模型；小輸入很可能 |
| HDCWNet | 230_Single-Image-Desnowing-HDCWNet | 去雪(階層雙樹小波) | CSD 去雪 PSNR ~32dB | 風險 | 固定 512×672 大輸入 + 小波分支，偏重 |
| DRBL | 231_DRBL | 低光增強(雙階段帶頻段學習) | LOL 類；中等 | 很可能 | 中型 CNN(No-LICENSE)，180–720 |
| MIMO-UNet | 232_MIMO-UNet | 去模糊(多輸入多輸出 U-Net) | GoPro PSNR ~31.7dB(MIMO-UNet+) | 風險 | 多尺度 U-Net + 大輸入(No-LICENSE)；小輸入很可能 |
| FBCNN | 234_FBCNN | 可控 JPEG 去噪/去壓縮假影 | 依 QF；PSNR 高 | 風險 | 大 U-Net，180–720；小輸入很可能 |
| BSRGAN | 240_BSRGAN | 真實退化 x2/x4 超解析(RRDB) | 盲 SR，感知佳 PSNR 中 | 風險 | RRDB 大(No-LICENSE)；64–180 小 tile 很可能，大圖風險 |
| SCL-LLE | 241_SCL-LLE | 低光增強(語意對比學習) | LOL 類；中等 | 很可能 | 中型 CNN(No-LICENSE)，180–720 |
| Zero-DCE-improved | 243_Zero-DCE-improved | 低光增強(改良零參考曲線) | 同 Zero-DCE 級，~79K params | 可 | 微型 CNN(academic-only)，極輕 |
| Real-CUGAN | 249_Real-CUGAN | 動漫向 2x/3x/4x 超解析(UNet GAN) | 動漫 SR 感知佳 | 風險 | UNet-GAN 中大，多倍率；64–128 小 tile 很可能，大圖風險 |
| AU-GAN | 251_AU-GAN | 低光/惡劣光照增強(非對稱 GAN) | 夜→日；無統一基準 | 風險 | GAN，輸入到 720×1280；小輸入很可能 |
| TransWeather | 253_TransWeather | 統一惡劣天氣去除(去雨/霧/雪 Transformer) | All-weather 統一 SOTA | 風險 | Transformer encoder-decoder，僅 ONNX 轉成功；顯存風險 |
| EfficientDerain | 261_EfficientDerain | 高效去雨(pixel-wise dilation) | Rain100H 速度快 | 很可能 | 設計即高效，中型 CNN；大圖(736×1280)偏風險 |
| HWMNet | 270_HWMNet | 低光增強(半小波注意力 U-Net) | LOL PSNR ~24.2dB | 風險 | 小波 + 注意力 U-Net；小輸入很可能 |
| FD-GAN | 275_FD-GAN | 去霧(頻率域 GAN) | RESIDE 類；中等 | 風險 | GAN 到 1080×1920(No-LICENSE)；小輸入很可能 |
| EDN-GTM | 277_EDN-GTM | 去霧(編碼解碼 + 引導傳輸圖) | RESIDE 類 PSNR 高 | 風險 | 大 U-Net 到 1088×1920；小輸入很可能 |
| IMDN | 281_IMDN | 輕量 x4 超解析(資訊多重蒸餾) | Set5 x4 PSNR ~32.2dB，僅 ~0.7M params | 可 | AIM2019 冠軍輕量 SR；64–256 小輸入順，大圖很可能 |
| UIE-WD | 283_UIE-WD | 水下影像增強(小波擴散) | WIP(issue #97)；無基準 | 很可能 | 中型 CNN，192–1080；標註 WIP 需驗證 |
| Decoupled-LLIE | 285_Decoupled-Low-light-Image-Enhancement | 低光增強(解耦光照/反射) | LOL 類；中等 | 很可能 | 中型 CNN，180–720 |
| SCI | 286_SCI | 低光增強(自校準光照，極輕) | LOL 類；推論極快 | 可 | 自校準權重共享微型網，Jetson 上極輕；LLIE 首選之一 |
| IAT | 315_Illumination-Adaptive-Transformer | 低光增強(光照自適應 Transformer) | LOL PSNR ~23.4dB，輕量 ViT | 風險 | Transformer(僅 ONNX 轉成功)；參數小但 attention 顯存風險 |
| night_enhancement | 316_night_enhancement | 夜間影像增強(高頻先驗) | 無統一基準；中等 | 風險 | 僅 ONNX 轉成功，架構偏重；小輸入很可能 |
| Dehamer | 320_Dehamer | 去霧(CNN-Transformer 混合) | SOTS PSNR ~36.6dB | 風險 | CNN+Transformer 混合(僅 ONNX)；顯存風險 |
| Stripformer | 323_Stripformer | 去模糊(條狀注意力 Transformer) | GoPro PSNR ~33.1dB | 風險 | Transformer(僅 ONNX)；大圖顯存風險 |
| DehazeFormer | 325_DehazeFormer | 去霧(Swin 類 Transformer) | SOTS PSNR ~40dB(large) | 風險 | Swin-style Transformer(僅 ONNX)；large 變體爆 8GB |
| XYDeblur | 344_XYDeblur | 去模糊(單編碼雙解碼) | GoPro 類；中等 | 風險 | 僅 ONNX 轉成功，大輸入偏重；小輸入很可能 |
| Bread | 348_Bread | 低光增強(亮度/色彩解耦) | LOL 類；輕量 | 很可能 | 輕到中型 CNN(僅 ONNX)；偏可 |
| PMN | 349_PMN | 去噪 + 低光(配對噪聲建模 raw) | SID raw 去噪 PSNR 高 | 風險 | raw 大 U-Net(僅 ONNX)；顯存重 |
| RFDN | 351_RFDN | 輕量 x4 超解析(殘差特徵蒸餾) | Set5 x4 PSNR ~32.2dB，AIM2020 冠軍輕量 | 可 | IMDN 後繼極輕 SR(僅 ONNX)；小輸入順 |
| MAXIM | 352_MAXIM | 多軸 MLP 通用復原(此處 dehaze only) | 多任務 SOTA；模型大 | 風險 | 多軸 MLP 大模型(dehaze only 已轉)；顯存風險 |
| ShadowFormer | 353_ShadowFormer | 去陰影(Transformer) | ISTD+ PSNR ~32dB | 風險 | Transformer(僅 ONNX)；顯存風險 |
| DEA-Net | 354_DEA-Net | 去霧(細節增強注意力) | SOTS PSNR ~41dB(SOTA) | 風險 | 注意力 CNN(FP16/FP32 已轉)；小輸入很可能，大圖風險 |
| MSPFN | 359_MSPFN | 去雨(多尺度漸進融合) | Rain100 類；重 | 風險 | 多尺度大網(FP16/FP32 已轉)；小輸入很可能 |
| KBNet | 361_KBNet | 真實影像去噪(核基底注意力) | SIDD PSNR ~40dB | 風險 | 注意力 U-Net(僅 ONNX)；小輸入很可能 |
| FLW-Net | 367_FLW-Net | 低光增強(快速輕量，全域感知) | LOL 類；極輕快 | 可 | 設計即快又輕(僅 ONNX)；Jetson 上順 |
| C2PNet | 368_C2PNet | 去霧(對比正則 + 物理感知) | SOTS PSNR ~42dB(SOTA) | 風險 | 物理感知大網(僅 ONNX)；小輸入很可能 |
| Semantic-Guided LLIE | 370_Semantic-Guided-Low-Light-Image-Enhancement | 低光增強(語意導引) | LOL 類；輕量 | 很可能 | 輕到中型 CNN(僅 ONNX) |
| URetinex-Net | 372_URetinex-Net | 低光增強(Retinex 展開最佳化) | LOL PSNR ~21.3dB | 很可能 | 展開式中型網(僅 ONNX) |
| SCANet | 375_SCANet | 去霧(空間-通道注意力，非均勻霧) | NH-HAZE 類；中等 | 風險 | 注意力 CNN(僅 ONNX)；小輸入很可能 |
| DRSformer | 377_DRSformer | 去雨(稀疏 Transformer) | Rain SOTA | 風險 | 稀疏 Transformer(僅 ONNX)；顯存風險 |
| PairLIE | 385_PairLIE | 低光增強(配對影像學習) | LOL PSNR ~19–23dB | 很可能 | 輕到中型 CNN(僅 ONNX) |
| WGWS-Net | 389_WGWS-Net | 統一多天氣去除(雨/雨滴/霧/雪) | All-weather；中大 | 風險 | 多天氣統一網(僅 ONNX)；小輸入很可能 |
| MixDehazeNet | 396_MixDehazeNet | 去霧(混合結構區塊) | SOTS PSNR ~高 | 風險 | 大注意力 CNN(僅 ONNX)；small 變體很可能 |
| CSRNet | 400_CSRNet | 影像增強/色調調整(條件序列重打光) | MIT-Adobe；極輕 | 可 | 極輕條件 MLP/conv(僅 ONNX)；Jetson 上順 |
| HDR-Transformer | 404_HDR-Transformer | 多曝光 HDR 重建(Transformer) | HDR 去鬼影 SOTA | 風險 | Transformer 多幀(僅 ONNX)；顯存風險 |
| nighttime_dehaze | 409_nighttime_dehaze | 夜間去霧(含輝光抑制) | 無統一基準；中等 | 風險 | 僅 ONNX 轉成功，架構偏重；小輸入很可能 |
| UDR-S2Former | 411_UDR-S2Former_deraining | 去雨滴(不確定性導引 Transformer) | RainDrop SOTA | 風險 | 稀疏 Transformer(僅 ONNX)；顯存風險 |
| Diffusion-Low-Light | 418_Diffusion-Low-Light | 低光增強(擴散模型) | LOL-v2 PSNR ~高，但多步取樣 | 不可 | 擴散需多步迭代取樣 + UNet 顯存重，無法即時，8GB 不切實際 |
| Face Deblurring | 469_Face_Deblurring | 人臉去模糊(64×64 小輸入) | 無公開基準；小模型 | 可 | 64×64 微型輸入(僅 ONNX)；極輕，可塞 |

**建議硬體**：這 82 個影像復原模型對 PawAI 多屬「畫質美化」非主線需求；唯一邊際有用的是低光增強(LLIE)夜間替 D435 提亮——優先選 curve-based 微型網 **Zero-DCE-TF(216) / Zero-DCE-improved(243) / SCI(286) / FLW-Net(367)**（皆 ~10–80K params，CONFIRMED 可，Jetson 上近零負擔，ONNX→TRT FP16 直跑）；輕量 SR 若需要選 **IMDN(281) / RFDN(351) / Fast-SRGAN(171)**；其餘 Transformer/擴散/大 U-Net 在 8GB 已被 face+ASR+TTS+ROS2 佔滿下不建議，務必鎖小輸入(≤256×256)+FP16 並驗 headroom ≥0.8GB，diffusion(418) 直接放棄。

---

## 12. Sound Classifier

本類別涵蓋 8 個音訊模型，任務橫跨環境音/事件分類（YAMNet、ml-sound-classifier、BirdNET-Lite）、語音表徵嵌入（FRILL）、音高估計（SPICE）、語音降噪增強（Speech-enhancement）、語音情緒辨識（Light-SERNet）與語音辨識 ASR（Whisper）。除 Whisper 為 Transformer 編碼/解碼結構外，其餘多半是輕量 CNN（MobileNet 系列）或全卷積網路，對 Jetson Orin Nano 8GB 而言主要落在「可」與「很可能」。輸入幾乎統一為 16kHz mono 波形或其 log-mel/MFCC 頻譜，**特徵前處理（mel/MFCC）通常落在 CPU 端，需自行銜接**，這是部署這類模型時最容易被忽略的成本。整體對話/守護場景中最實用的是 YAMNet（環境事件偵測）與 Whisper（ASR，本專案語音主線已在用 faster-whisper）。

| 模型 | folder | 功能 | 表現（代表性指標） | Jetson 8GB | 備註 |
|------|--------|------|---------------------|:----------:|------|
| ml-sound-classifier | 013_ml-sound-classifier | 通用音訊事件標註（Freesound FSDKaggle2018 41 類即時分類） | MobileNetV2 backbone，FSDKaggle2018 賽近競爭力；無權威 mAP 數字（依訓練變體而定），CPU 即可即時 | 可 | 提供完整 ONNX/TF-TRT 量化鏈；模型極小（MobileNetV2），ONNX→TRT FP16 屬已驗證輕量 CNN 類；mel 前處理需自行接 |
| YAMNet | 097_YAMNet | AudioSet 521 類聲音事件分類（環境音/人聲/動物） | balanced mAP 0.306、d-prime 2.318（AudioSet Eval 20366 段）；MobileNetV1 depthwise-sep，僅約 VGGish 1/20 大小，0.96s 窗 / 0.48s hop | 可 | 全格式齊備含 ONNX；輕量 MobileNetV1，ONNX→TRT FP16 穩；本專案守護場景（玻璃破碎/警報/吠叫偵測）最實用候選 |
| SPICE | 098_SPICE | 自監督音高估計（單音 pitch，含 voicing 信心） | MIR-1k Raw Pitch Accuracy 90.7%（與全監督 CREPE 同級，無標註訓練）；極小模型，行動端即時 | 可 | TFLite 來源轉出含 ONNX；模型很小、純卷積，ONNX→TRT FP16 無壓力；與本專案互動主軸關聯低（音樂/音高用途） |
| Speech-enhancement | 118_Speech-enhancement | 語音降噪增強（spectrogram U-Net 去噪，輸出乾淨頻譜） | vbelz U-Net 頻譜去噪；無統一公開 PSNR/PESQ 基準（依資料集而定），參數量中等 | 很可能 | convert_script 有 ONNX(opset11) 輸出但標 WIP；中型 U-Net 未在板上實測，ONNX→TRT FP16 可期；可作 ASR 前端降噪改善風扇噪音辨識率 |
| FRILL | 120_FRILL | 非語意語音表徵嵌入（paralinguistic embedding，供下游情緒/說話人等任務） | 較 TRILL 平均僅降 2% 準確度、速度 32×、體積 40%；Pixel1 延遲 8.5ms，TFLite 38.5MB（MobileNetV3 蒸餾） | 可 | nofrontend 變體（需自備 log-mel 前端）；MobileNetV3 backbone，ONNX→TRT FP16 屬輕量類；輸出為嵌入向量，需自接分類頭 |
| BirdNET-Lite | 177_BirdNET-Lite | 鳥種聲音辨識（全球 6000+ 種，BirdNET 6K GLOBAL） | 大規模鳥種辨識，無單一 top-1 數字（多標籤、地域/季節加權）；TFLite 非 flex 版，邊緣即時 | 很可能 | non-flex 版才可轉；TF-TRT 路徑為主，ONNX 欄未標（需從 TFLite 自行導出）；模型中型、純 CNN，板上未實測但格式可行；與本專案無關聯 |
| Whisper | 381_Whisper | 多語語音辨識 ASR（OpenAI Whisper） | WER 與速度高度依 size-tier（tiny/base/small/medium/large），folder 未宣告變體；本專案實測 small CUDA float16 約 1.0s/句 | 很可能 | ONNX-only（float32/float16/int8 變體於 onnx/ 路徑）；tiny~small 可穩跑、medium 以上吃滿 8GB 屬風險；本專案語音主線已採 faster-whisper small |
| Light-SERNet | 382_Light-SERNet | 語音情緒辨識 SER（全卷積，MFCC 三路並行） | IEMOCAP speaker-dependent 89.16% / speaker-independent 52.14%；參數量極少、可上 IoT/嵌入式 | 很可能 | onnx2tf 流程（ONNX 為來源格式，README 僅標 TFLite 欄）；全卷積極輕量，導出 ONNX→TRT FP16 應順；可疊在 ASR 之上補情緒線索 |

**建議硬體**：8 模型在 Orin Nano 8GB 多數無壓力——YAMNet/SPICE/FRILL/ml-sound-classifier 走 ONNX→TensorRT FP16 屬已驗證輕量 CNN 類（可），Speech-enhancement/BirdNET-Lite/Light-SERNet 格式可行但未實測（很可能）；唯 Whisper 須鎖 tiny~small 變體（medium 以上易撐爆 8GB 統一記憶體），且所有模型的 mel/MFCC 前處理需自行在 CPU 端銜接、保留 ≥0.8GB headroom。

---

## 13. Natural Language Processing

本類別收錄 3 個經典 Transformer NLP 模型，全部由 HuggingFace `tflite-android-transformers`（行動端量化版）透過 `tflite2tensorflow` 反向轉出 TF/ONNX/TFLite/CoreML/OpenVINO/TFJS。功能集中在**抽取式問答（SQuAD QA）**與**因果語言生成（GPT-2 文本生成）**。三者皆有 ONNX 匯出（opset 11），屬輕中量級 Transformer（25M–124M 參數），技術上可在 Jetson Orin Nano 8GB 跑，但都帶兩個結構性限制：**序列長度被轉檔時固定死**（GPT2-64 = 64 token、DistilBERT-384、MobileBERT 多為 384），以及 **TFLite-origin 圖在 TensorRT 上算子覆蓋常不完整**（部分回退 CUDA/CPU）。更重要的是這三者與 PawAI 主線（視覺/語音感知 + 雲端 LLM 對話）方向不重疊——本專案的對話智能走的是雲端 `gpt-5.4-mini`，本地僅保留 Qwen2.5-0.5B 作 fallback，這些 2020 年代英文 QA/生成小模型並非候選。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|------------|------|
| Mobile_BERT | 048_mobile_bert | 抽取式問答（SQuAD v1.1，task-agnostic 壓縮 BERT，輸入多為 384 token） | SQuAD v1.1 dev F1 90.3（最小變體 ~25M 參數 F1 84.3），近 BERT-base 品質而體積小 4 倍；行動端 CPU 推理數十至上百 ms/seq | 很可能 | ONNX 可用但屬 Transformer 類；25M 參數 FP16 ~50MB，記憶體無壓力。風險在 opset 11 + TFLite-origin 圖的 TRT 算子覆蓋、固定 seq len。未在板上實測，且非 PawAI 主線 |
| GPT2/DistillGPT2 | 121_GPT2_DistillGPT2 | 因果語言模型 / 英文文本生成（轉檔鎖定 seq len = 64） | DistilGPT2 82M 參數、WikiText-103 PPL 21.1；GPT2-base 124M PPL ~16.3。seq=64 限制 → 僅短文續寫，無對話/長上下文能力 | 風險 | ONNX/TF-TRT 皆有；124M 參數 FP16 ~250MB 記憶體可容。但 64-token 固定窗 + 純英文 + 老 opset，實用價值極低，且自回歸生成在 TFLite-origin 圖上效率差。非候選 |
| DistillBert | 122_DistillBert | 抽取式問答（SQuAD v1.1，distilled BERT，輸入 384 token） | SQuAD v1.1 dev F1 85.1 / EM 76.5（66M 參數，保留 BERT 97% 效能、體積減 40%、速度快 ~60%） | 很可能 | ONNX 可用；66M 參數 FP16 ~130MB，記憶體安全。與 048 同屬問答 Transformer，同樣受 opset 11 + 固定 seq len + TRT 覆蓋不全限制，未板上實測。非 PawAI 主線 |

**建議硬體**：三者皆 ONNX 可載、體積落在 50–250MB（記憶體完全在 8GB 預算內），onnxruntime-gpu (jp6/cu126) + TensorRT-EP FP16 技術上可跑；但全為固定 seq len 的英文 QA/生成 Transformer，TFLite-origin 圖 + opset 11 在 TRT 上算子覆蓋不確定、需逐一驗證，且與 PawAI 雲端 LLM 對話路線無交集，僅列為「可部署但非候選」。

---

## 14. Text Recognition

本類別收錄 3 個離線手寫／印刷文字辨識（OCR）模型，皆為「CNN 視覺骨幹 + 序列建模（RNN/LSTM 或 U-Net 偵測）+ CTC/分類」的傳統 OCR 架構，**全部都有 ONNX 匯出**（PINTO 從 SimpleHTR、Intel OMZ、tanreinama 三個來源轉出）。其中 052 為英文手寫單字、055/093 為日文手寫／印刷辨識。對 PawAI「居家互動機器狗」而言這三者偏離核心場景（手勢／語音／物體辨識），OCR 並非互動主軸需求；此處僅就 Jetson Orin Nano SUPER 8GB 的可部署性做評估。三者皆非 LLM/diffusion 等多 GB 巨物，記憶體足跡可控，但 055/093 解析度偏大（96×2000、512×512）需留意延遲與顯存。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| SimpleHTR | 052_Handwritten_Text_Recognition | 英文手寫**單字**離線辨識（IAM 資料集），輸出文字字串 | 5×CNN+2×LSTM+CTC，輸入 128×32 灰階；IAM 驗證集 word accuracy ~74–84%、CER ~8–10%（githubharald 官方數據）；模型極小（數 MB 級），CPU 即可即時 | 很可能 | ONNX 已匯出且為小型 CNN+RNN，FP16→TensorRT-EP 應流暢；唯只認英文單字、需上游字串切分，與本專案場景無關 |
| handwritten-japanese-recognition-0001 | 055_Handwritten_Japanese_Recognition | 日文手寫**文本行**離線辨識（Kondate/Nakayosi），輸出日文字串 | VGG16-like 骨幹 + reshape + BiLSTM/FC + CTC，輸入 1×1×96×2000 灰階；指標為 label/character error rate（OpenVINO OMZ，未公開精確 %）；屬中型 CNN+RNN（約數十 MB 級） | 很可能 | 來源是 OpenVINO 模型但 PINTO 已轉出 ONNX（可走 onnxruntime-gpu+TRT-EP）；96×2000 寬輸入使單次推理偏重，延遲依文本行長度而定，非即時串流場景尚可 |
| OCR_Japanease (DetectionNet+ClassifierNet) | 093_ocr_japanese | 日文**印刷／一般**OCR，兩階段：字元偵測 + 字元分類，輸出版面字串 | DetectionNet=U-Net+ResNet block，512×512→256×256×4（字元/句/寬/高機率）；ClassifierNet 256×256；README 標註輸入 120×160；無公開 mAP/accuracy 基準（依變體而定） | 風險 | 兩個網路串接（U-Net+ResNet 偵測較重）+ NMS 後處理，合併足跡與延遲高於 052/055；ONNX 已匯出可跑，但屬本類別最重者，8GB 與 D435/face/ASR 共存時需實測顯存與 FPS |

**建議硬體**：三者皆 ONNX 可在 Jetson Orin Nano SUPER 8GB 以 onnxruntime-gpu(jp6/cu126)+TensorRT-EP FP16 部署，052/055「很可能可」、093（兩階段 U-Net+ResNet）「風險」需實測；但 OCR 不在 PawAI 互動主軸，建議僅作研究備查、不納入 Demo runtime。

---

## 15. Action Recognition

本類別收錄 3 個動作辨識模型，分屬兩條技術路線：一是 Intel OpenVINO Open Model Zoo 的工業影像分類器（焊接氣孔偵測），二是 mmaction2 / 學術界的「骨架式動作辨識」（skeleton-based）模型 PoseC3D 與 MS-G3D。後兩者不直接吃 RGB 影像，而是先用外部姿勢估計器（如 HRNet / RTMPose）抽出人體關節點，再對「多幀骨架序列」做時序分類，因此實際部署需串接一條 pose 上游管線。對 PawAI 而言，這條「骨架 → 動作」路徑與既有的 RTMPose 姿勢模組天然契合，理論上可擴展為跌倒 / 揮手 / 蹲下等連續動作判讀，但本表三者都缺 Jetson 實測數據，且兩個 skeleton 模型的輸入張量維度高、3D 卷積/多尺度 GCN 運算量不小，須謹慎評估記憶體與延遲。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| weld-porosity-detection-0001 | 092_weld-porosity-detection-0001 | 焊接氣孔/缺陷影像二元分類（工業檢測，序列影格輸入） | 無公開 top-1（Intel OMZ 僅標 ~3.6M 參數、~3.3 GFLOPs 等級的小型 CNN）；屬輕量分類器 | 可 | ONNX 已提供，小型 CNN，ONNX→TRT FP16 envelope 內可跑。但為焊接產線專用模型，與 PawAI 居家互動完全無關，僅格式上可行 |
| PoseC3D | 247_PoseC3D | 骨架式動作辨識：將關節點轉成 3D 熱圖體積，用 SlowOnly R50 3D-CNN 分類（FineGYM / NTU60 / NTU120 / UCF101 / HMDB51） | NTU60 X-Sub top-1 ~93–94%、NTU120 X-Sub ~86%（mmaction2 官方 zoo 量級）；3D-CNN 推理偏重，未見 Jetson 基準 | 風險 | ONNX 已提供但輸入為 1×20×17×48×64×64 六維張量（20 clip × 17 關節 × 48 幀熱圖 × 64×64），3D 卷積中介 activation 巨大、易爆 8GB 統一記憶體；需先跑 pose 上游再餵，延遲與顯存皆未實測。可考慮降 clip 數/解析度後再評 |
| MS-G3D | 248_MS-G3D | 骨架式動作辨識：多尺度時空圖卷積（G3D operator），吃關節座標序列（Kinetics-Skeleton / NTU60 / NTU120） | NTU60 X-Sub top-1 ~91.5%、NTU120 X-Sub ~88–89%、Kinetics-Skeleton top-1 ~38%（CVPR2020 原論文量級）；未見 Jetson 基準 | 很可能 | ONNX 已提供，輸入 1×3×T×25×2（座標而非影像，極小），GCN 模型本體與 activation 都遠輕於 PoseC3D，envelope 內合理但未量測，故列「很可能」。同樣需 RTMPose 之類上游抽骨架；雙流（joint+bone）會翻倍成本 |

**建議硬體**：三者皆有 ONNX，可走 onnxruntime-gpu + TensorRT-EP FP16；MS-G3D（小輸入 GCN）最務實、可直接接 PawAI 既有 RTMPose 骨架做動作辨識實驗，PoseC3D 的 6D 大張量 + 3D-CNN 須先壓低 clip/解析度並監看顯存以免吃滿 8GB，weld-porosity 雖可跑但與本專案無關不建議納入。

---

## 16. Inpainting

影像修補（Inpainting）模型負責填補遮罩區域（去除物件、補洞、修復破損），輸入為「原圖 + 二值遮罩」、輸出為填補後的完整影像。這一類在 PawAI 居家互動機器狗主線（人臉/語音/手勢/姿勢/物體 → 動作）中**沒有任何角色**，純屬離線影像編輯工具，列出僅供轉換能力盤點。四個資料夾都偏研究級生成模型：HiFill 與 DeepFillv2 走 GAN/閘控卷積、結構相對輕量且有現成 ONNX，最適合在 Jetson 上嘗試；MST 含結構 transformer、OPN 為參考導向（reference-guided）多階段網路，較重且公開基準稀少。所有變體都是 GPU 路徑（ONNX→TensorRT FP16）或 PyTorch，TFLite/OpenVINO/TF-TRT 僅為轉換中間產物，不影響 Jetson 部署判定。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| HiFill | 100_HiFill | 超高解析度影像修補（CRA 上下文殘差聚合，低解析網路 + 殘差升採樣，可達 8K 大洞） | 無公開逐項 PSNR；論文重點是 2K 影像在 GTX 1080 Ti 近即時、512×512 訓練→高解析推論 | 可（很可能） | CVPR2020；ONNX opset13（img+mask→inpainted）。核心推論網路在低解析（512）跑，CNN 結構輕，ONNX→TRT FP16 應落 8GB 內；殘差聚合的高解析 upsample 主要吃頻寬非顯存。屬 OpenVINO 源頭轉出但 zoo 直接給 ONNX |
| MST_inpainting | 163_MST_inpainting | 人造場景線稿張量空間修補（結構 transformer 預測線/邊 → texture 補全；P2C/P2M/shanghaitech 三變體） | 依變體而定／無統一公開基準（ICCV2021 MST，在 man-made scenes 報 SSIM/FID 為主，非單一 PSNR） | 風險 | encoder/decoder 拆兩段 ONNX，256×256 與 512×512 兩解析；含結構 transformer 與 `dot`/matmul 算子（轉檔需手 patch torch symbolic）。transformer + 多段 pipeline，512 解析下顯存與算子相容性風險高，需逐段測 TRT FP16 |
| OPN（Onion-Peel Networks） | 273_OPN | 參考導向（reference-guided）洋蔥剝皮式逐層修補，原為影片物件移除/補洞 | 無公開單值基準（ICCV2019，質性結果為主，依參考幀數量與洞大小變動） | 風險 | zoo 僅標 ONNX、無 convert_script（純既成 ONNX）。多階段非對稱注意力比對「參考幀↔目標」，記憶體與算子隨參考數成長；單張 ONNX 可試跑但 TRT 轉換與多輸入動態 shape 風險偏高，無小體積保證 |
| DeepFillv2 | 274_DeepFillv2 | 自由形狀（free-form）影像修補，閘控卷積（gated conv）+ SN-PatchGAN | Places2 ~PSNR 22–23 dB（256×256，第三方 reimpl 報值）；CelebA-HQ 較高，主觀品質佳 | 可（很可能） | ICCV2019 oral；ONNX opset11，celeba_hq 小解析（192×320 / 240×320）。閘控卷積為純 CNN、解析度低、輸入固定，ONNX→TRT FP16 在 8GB 內最穩的一個。OpenVINO 為來源轉檔，部署直接走 ONNX |

**建議硬體**：四者皆為離線影像編輯、與機器狗即時主線無關；若要在 Jetson 上玩，優先 DeepFillv2（小解析固定輸入、純閘控 CNN，可）與 HiFill（低解析核心網路，可），各自 ONNX→TensorRT FP16 單跑、避免與 D435+人臉+ASR+TTS 同時占顯存；MST（結構 transformer 多段）與 OPN（參考導向多階段）列為風險，需逐段量測顯存與算子相容性後再定，切勿排進 Demo 即時迴圈。

Sources: [HiFill / CRA (arXiv 2005.09704)](https://arxiv.org/abs/2005.09704)、[DeepFillv2 (ICCV 2019, generative_inpainting)](https://github.com/JiahuiYu/generative_inpainting)、[MST_inpainting (ewrfcas)](https://github.com/ewrfcas/MST_inpainting)、[OPN demo (seoungwugoh)](https://github.com/seoungwugoh/opn-demo)

---

## 17. GAN

本類別含 2 個生成對抗網路（GAN）資料夾，皆為「生成 / 影像復原」用途，與 PawAI 即時感知（人臉/手勢/姿勢/物體/語音）主線無直接關聯。105 為 StyleGAN2 蒸餾的輕量人臉影像生成器（離線合成 1024×1024 人臉），310 為單張影像雨滴去除（CVPR2018 attentive GAN 生成器）。兩者均有 ONNX 匯出，理論上可走 onnxruntime-gpu + TensorRT-EP FP16 在板上單獨執行，但都屬生成型 decoder，記憶體佔用隨輸出解析度上升，且非感知任務、對本專案無實用落點，故僅作技術可行性記錄。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| MobileStyleGAN | 105_MobileStyleGAN | StyleGAN2 蒸餾人臉影像「生成」（mapping mnet + synthesis snet 兩段，輸出 1024×1024） | FFHQ FID 7.75；synthesis 8.01M 參數 / 15.09 GMAC（較 StyleGAN2 少 3.5× 參數、少 9.5× 算量）；速度依後端而定，原作僅在 CPU/OpenVINO 量測，無 Jetson 公開基準 | 很可能 | ONNX 可用→TRT FP16；屬生成型大 decoder，1024² activation 記憶體偏高，與 D435+face+ASR+TTS 同住 8GB 有爆量風險。對 PawAI 互動主線無用途，純離線人臉合成 |
| attentive-gan-derainnet | 310_attentive-gan-derainnet | 單張影像雨滴去除（recurrent attentive autoencoder GAN 生成器，DeRain） | 指標為 PSNR / SSIM（Raindrop/Rain100 等資料集，數值隨資料集與解析度而異，無單一公開定值）；ONNX 提供 180×320、240×320、240×360、320×480、360×640、480×640、720×1280 | 很可能 | ONNX 可用→TRT FP16；低解析（180×320）為輕量 CNN 可跑，720×1280 偏重、risk 隨解析度上升。室外去雨用途，與本專案居家互動場景無關 |

**建議硬體**：兩者皆 ONNX CNN 生成器、Jetson Orin Nano SUPER 8GB 單跑「很可能」可行（低解析優先、FP16），但屬離線生成/復原任務，與 PawAI 感知主線無關，不建議與 D435+face+ASR+TTS+ROS2 同住共用 8GB 統一記憶體。

---

## 18. Transformer

本類別僅收錄一個資料夾 `127_dino`，即 Facebook Research 的 **DINO**（《Emerging Properties in Self-Supervised Vision Transformers》, ICCV 2021）自監督 Vision Transformer 骨幹。注意：此為「自監督表徵學習 DINO」（DeiT-Small/ViT backbone），**並非** 後來做物件偵測的 DINO/DETR 變體。PINTO 在 README 已標註 `experimental`，僅釋出 `dino_deits8`（patch 8）與 `dino_deits16`（patch 16）兩個 DeiT-Small ViT 變體，輸出為影像 embedding／patch attention，需自行接下游 head（分類、kNN、分割等）才有實際用途。ONNX 路徑可用，但本質是 ViT，屬 Jetson 8GB 上需謹慎評估的 transformer。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:----------:|------|
| DINO ViT-S/8、ViT-S/16 (DeiT-Small self-supervised) | `127_dino` | 自監督 ViT 影像特徵抽取（image/patch embedding + self-attention map），下游可接 kNN 分類、線性探針、無監督分割 | DeiT-Small ViT 自監督表徵：ImageNet linear probe top-1 約 77~80%、kNN 約 74~78%（/8 patch 較 /16 高但慢得多）。ViT-S 約 21M 參數；/16 在桌面 GPU 數十~百餘 FPS，/8 因序列長度暴增（patch 數約 4 倍、attention O(N²)）大幅變慢。Jetson 上無實測，為「依變體而定」 | 風險 | ONNX 可走 onnxruntime-gpu + TensorRT-EP FP16，TF-TRT 欄空、EdgeTPU(TPU 欄空)/OpenVINO/CoreML/TFJS 皆不適用此晶片。ViT 注意力對 8GB 統一記憶體與延遲是主要風險：`/16` 變體最有機會跑（參數量中等、序列短），`/8` 因長序列 self-attention 記憶體與算力放大，與 D435+face+ASR+TTS+ROS2 並存時恐吃緊。屬研究性質，需自備下游 head 才有產品意義 |

**建議硬體**：先以 `dino_deits16` 走 ONNX→TensorRT-EP FP16 單獨量測 VRAM 與延遲（很可能可跑但未驗證）；`dino_deits8` 長序列注意力風險高，並存場景建議避開或離線特徵抽取為主，不要排進即時互動主線。

---

## 19. Others

本類別是 PINTO_model_zoo 的「雜項」收容區，共 52 個資料夾，橫跨車道偵測、光流/立體深度、線段偵測、邊緣偵測、視線估計、影像復原（去霧/去陰影/去反光/影像融合）、特徵點偵測與匹配、場景文字辨識、人群計數、Person ReID、語音降噪、鋼琴轉譜、甚至 Stable Diffusion。**全部資料夾都提供 ONNX**（README 每列 ONNX 欄皆 ⚫），所以部署格式上 Jetson 都走得通；真正的分水嶺是「規模與架構」：標準輕量 CNN（車道/邊緣/視線/去霧）→ 可；迭代式光流（RAFT 系）與高解析 Transformer 匹配器（LightGlue/DeDoDe/PARSeq）→ 風險；多 GB 的擴散模型（Stable Diffusion）→ 不可。對「老人與狗」專題而言，本類別僅 **L2CS-Net / GazeNet / gaze-estimation-adas（視線注意力）** 與 **PARSeq / CRNN（場景文字）** 偶有互動價值，其餘多為與本專題無關的研究型參考。下表逐一列出全部 52 個。

| 模型 | folder | 功能 | 表現(代表性指標) | Jetson 8GB | 備註 |
|------|--------|------|------------------|:---------:|------|
| gaze-estimation-adas-0002 | 091_gaze-estimation-adas-0002 | 視線方向估計(Intel OMZ ADAS) | 輕量 CNN，眼+頭姿輸入；無公開 angular error | 可 | ONNX 小模型；源於 OpenVINO 但已轉 ONNX；可做注意力線索 |
| Coconet | 102_Coconet | Magenta 音樂補全(複音作曲) | 音樂生成無單一準確率指標 | 很可能 | ONNX，TF/Magenta 系；與本專題無關 |
| HAWP | 108_HAWP | Holistic 線段(wireframe)解析 | sAP 線段偵測指標；WIP | 很可能 | ONNX(WIP)；結構性線段，研究用 |
| L-CNN | 110_L-CNN | Wireframe 線段解析 | sAP@10 ~58(原論文);WIP | 很可能 | ONNX(WIP)；中型 CNN |
| DTLN | 117_DTLN | 即時語音降噪(雙訊號 LSTM) | ~1M 參數，極輕，即時可跑;PESQ 提升 | 可 | ONNX 極小；可惜本專題降噪走雲端 ASR |
| M-LSD | 119_M-LSD | 即時線段偵測 | tiny 版 ~0.6M 參數，行動端即時 | 可 | ONNX 極輕；常用於文件/平面偵測 |
| CFNet | 131_CFNet | 立體匹配深度(cascade) | KITTI D1 ~1.7%;256x256/512x768 | 風險 | ONNX；cost-volume 立體網偏重，記憶體吃緊 |
| PSD-Dehazing | 139_PSD-Principled-Synthetic-to-Real-Dehazing-Guided-by-Physical-Priors | 真實場景去霧 | 去霧 PSNR/SSIM(依資料集);無統一基準 | 很可能 | ONNX；中型影像復原 CNN |
| Ultra-Fast-Lane-Detection | 140_Ultra-Fast-Lane-Detection | 車道線偵測(分類式) | TuSimple acc ~95.8%, >300FPS(原桌機);288x800 | 可 | ONNX，ResNet18 backbone 輕量 |
| lanenet-lane-detection | 141_lanenet-lane-detection | 車道線分割+嵌入 | TuSimple acc ~96%;256x512 | 可 | ONNX，ENet/分割式中小型 |
| driver-action-recog-encoder | 154_driver-action-recognition-adas-0002-encoder | 駕駛動作辨識-影像 encoder | MobileNetV2 backbone，輕量 | 可 | ONNX；需搭 155 decoder 用 |
| driver-action-recog-decoder | 155_driver-action-recognition-adas-0002-decoder | 駕駛動作辨識-時序 decoder | 小型 RNN decoder | 可 | ONNX；極小，配 154 |
| LSTR | 167_LSTR | 車道線(Transformer 回歸) | TuSimple ~96.2%, ~420FPS(原);多解析 | 很可能 | ONNX；輕量 transformer，small 解析可跑 |
| DexiNed | 229_DexiNed | 密集邊緣偵測 | ODS ~0.86(BIPED);多解析至 720x1280 | 可 | ONNX，CNN；低解析輕、高解析吃記憶體 |
| HRNet-Fashion-Landmark | 233_HRNet-for-Fashion-Landmark-Estimation | 服飾關鍵點估計 | HRNet-W48 高精度但偏重;多解析 | 風險 | ONNX；HRNet 大 backbone，高解析爆 8GB 風險 |
| piano_transcription | 237_piano_transcription | 鋼琴音訊轉譜(MIDI) | note F1 ~96%(MAESTRO);1x160000 樣本 | 很可能 | ONNX；CRNN 音訊，長序列記憶體需注意 |
| RAFT | 252_RAFT | 光流估計(迭代式) | Sintel EPE ~1.6;iters=10/20;240x320~480x640 | 風險 | ONNX；GRU 迭代 + 4D cost volume，記憶體重 |
| FullSubNet-plus | 254_FullSubNet-plus | 語音增強/降噪 | DNS PESQ 提升;1x1x257xT 頻譜 | 很可能 | ONNX；長序列頻譜，T 大時記憶體上升 |
| FILM | 255_FILM | 影格內插(frame interpolation) | Vimeo90K PSNR ~36;至 1080x1920 | 風險 | ONNX；多尺度金字塔，高解析(1080p)易爆 |
| KP2D | 260_KP2D | 自監督特徵點偵測+描述 | ResNet backbone;HPatches MMA;多解析 | 很可能 | ONNX；中型 CNN，512x1280 解析偏重 |
| CSFlow | 272_CSFlow | 光流估計(cross strip) | KITTI/things;iters=10/20;迭代式 | 風險 | ONNX；RAFT 系迭代光流，記憶體重 |
| HybridNets | 276_HybridNets | 全景駕駛感知(偵測+車道+可行區) | BDD100K mAP/mIoU;多解析至 1152x1920 | 風險 | ONNX；EfficientNet 多任務頭，高解析吃滿 |
| DWARF | 278_DWARF | 立體深度+光流聯合 | StereoDepth+OpticalFlow;多解析 | 風險 | ONNX(TF 源)；雙任務迭代，記憶體高 |
| F-Clip | 279_F-Clip | 快速線段(wireframe)解析 | sAP ~64, 73FPS(原);多解析 | 很可能 | ONNX；HG backbone 中型 |
| perceptual-reflection-removal | 288_perceptual-reflection-removal | 影像去反光 | 去反光 PSNR/SSIM;多解析至 720x1280 | 風險 | ONNX；VGG 感知損失大 backbone，高解析重 |
| SeAFusion | 291_SeAFusion | 紅外+可見光影像融合 | 融合 EN/SD/SCD;多解析 | 很可能 | ONNX；輕中型融合 CNN |
| GazeNet | 297_GazeNet | 遠距 3D 視線估計(時序) | 1x7x3x256x192 序列輸入;angular error | 很可能 | ONNX；多幀時序輸入，中型 |
| DEQ-Flow | 298_DEQ-Flow | 光流(深度平衡 DEQ) | Sintel/KITTI EPE;隱式不動點求解 | 風險 | ONNX(AGPL-3.0)；DEQ 迭代求解，記憶體與延遲高 |
| GMFlowNet | 306_GMFlowNet | 光流(全域匹配) | Sintel EPE;多解析至 720x1280 | 風險 | ONNX；global matching attention，高解析重 |
| ImageForensicsOSN | 309_ImageForensicsOSN | 社群圖竄改/偽造偵測 | forgery F1/AUC;多解析 | 很可能 | ONNX；中型分割式 CNN |
| pips | 318_pips | 持續點追蹤(Persistent Independent Particles) | 點軌跡 ATE;時序視窗 | 風險 | ONNX；多幀時序追蹤，記憶體高 |
| Ultra-Fast-Lane-Detection-v2 | 324_Ultra-Fast-Lane-Detection-v2 | 車道線偵測 v2 | CULane F1 ~76;高 FPS | 可 | ONNX，ResNet backbone 輕量 |
| YOLOPv2 | 326_YOLOPv2 | 全景駕駛(車輛偵測+車道+可行區) | BDD100K mAP/mIoU, ~91FPS(原);384/736x1280 | 很可能 | ONNX；E-ELAN 多任務，384x1280 可，高解析偏重 |
| Stable_Diffusion | 328_Stable_Diffusion | 文生圖擴散模型 | FID;UNet+VAE+text encoder 數 GB | 不可 | ONNX 但多 GB，8GB 統一記憶體放不下且與專題無關 |
| DeepLSD | 339_DeepLSD | 深度線段偵測(結合古典) | 線段 repeatability;CNN+細化 | 很可能 | ONNX；中型 CNN |
| ALIKE | 342_ALIKE | 輕量特徵點偵測+描述 | HPatches MMA;極輕量(亞毫秒級) | 可 | ONNX 小 CNN；SLAM/匹配前端佳 |
| Unimatch | 357_Unimatch | 統一光流/立體/深度(GMFlow) | Sintel/KITTI;Transformer 匹配 | 風險 | ONNX；transformer 統一架構，高解析記憶體重 |
| PARSeq | 360_PARSeq | 場景文字辨識(permuted AR) | 文字 acc ~95%+(常見基準) | 風險 | ONNX；ViT-ish 自回歸解碼，偏重 |
| text_recognition_CRNN | 366_text_recognition_CRNN | 場景文字辨識(CRNN, 中/英) | word acc(依資料集);輕量 CRNN | 可 | ONNX 小模型；CN/CH/EN |
| LiteTrack | 373_LiteTrack | 單目標視覺追蹤(輕量 transformer) | LaSOT AUC;即時導向 | 很可能 | ONNX；輕量 transformer tracker |
| LaneSOD | 374_LaneSOD | 車道顯著性分割 | 車道 IoU/F;分割式 | 可 | ONNX；輕中型分割 CNN |
| P2PNet_tfkeras | 378_P2PNet_tfkeras | 人群計數(點預測) | ShanghaiTech MAE ~52(SHA);19.2M params VGG16 | 很可能 | ONNX；VGG16 backbone 中型，可跑但偏重 |
| LightGlue | 388_LightGlue | 特徵點匹配(自適應 transformer) | ~22FPS/pair(原), 13.7M params;ONNX→TRT 已驗 | 風險 | ONNX；attention 匹配器，ONNX/TRT 社群佳但 8GB+其他模型同跑吃緊 |
| L2CS-Net | 398_L2CS-Net | 視線方向估計(pitch/yaw) | Gaze360 角度誤差 ~10°;448x448 ResNet50 | 很可能 | ONNX；ResNet50 backbone 中型，本專題注意力可用 |
| CLRerNet | 401_CLRerNet | 車道線偵測(SOTA) | CULane F1 ~81;DLA/ResNet | 很可能 | ONNX；中型，精度高於 UFLD |
| DeDoDe | 406_DeDoDe | 特徵點偵測/描述/匹配 | MegaDepth 匹配 AUC;偏重 | 風險 | ONNX；解耦偵測+描述，大 backbone |
| Generalizing_Gaze_Estimation | 407_Generalizing_Gaze_Estimation | 跨域泛化視線估計 | 角度誤差;160x160 小輸入 | 可 | ONNX 小輸入 CNN；本專題注意力可用 |
| UAED | 408_UAED | 不確定性感知邊緣偵測 | ODS ~0.83+(BSDS);中型 | 很可能 | ONNX；邊緣偵測 CNN |
| DocShadow | 413_DocShadow | 文件陰影去除 | 去陰影 PSNR/RMSE;僅 FP32 列⚫ | 很可能 | ONNX(僅 FP32 標註)；GPU 仍可走 FP16 EP |
| GeoNet | 416_GeoNet | 無監督單目深度+相機姿態+光流 | KITTI AbsRel ~0.15;多任務 | 很可能 | ONNX(僅 FP32 列)；中型多任務 CNN |
| ISR | 428_ISR | 行人重識別(Person ReID, ICCV23) | Market-1501 mAP/Rank-1;embedder | 很可能 | ONNX；ReID embedder，中型 backbone |
| DDN | 487_DDN | 邊緣偵測 | 邊緣 ODS;無統一基準 | 很可能 | ONNX；邊緣偵測 CNN |

**建議硬體**：本類別大多 ONNX→TensorRT FP16 即可上 Jetson Orin Nano SUPER 8GB——車道/邊緣/視線/輕量匹配（UFLD、DexiNed、M-LSD、ALIKE、CRNN、gaze 系列）屬「可」放心跑；迭代式光流（RAFT/CSFlow/DEQ-Flow/GMFlowNet/Unimatch/pips）、高解析多任務（HybridNets、HRNet-Fashion）、ViT 匹配/辨識（LightGlue、DeDoDe、PARSeq）需控制輸入解析並避免與 D435+人臉+ASR+TTS 同跑，屬「風險」；唯一「不可」是 328 Stable Diffusion（多 GB 擴散，超出 8GB 統一記憶體且與專題無關）。實務上對「老人與狗」專題僅 gaze（091/297/398/407）與文字辨識（360/366）有潛在互動價值，其餘建議僅作研究參考。

---

## 建議硬體配置

本章把前 19 類的逐類部署備註，收斂成一份「在 PawAI 現役硬體上、面對 PINTO model zoo 任一資料夾，要不要部署、用什麼配置」的決策依據。所有判定的硬體前提是專案實際在用的這一塊板子。

### 1. 基準板：Jetson Orin Nano SUPER 8GB 規格與供電/散熱

| 項目 | 規格 | 對部署的含意 |
|------|------|--------------|
| GPU | Ampere 1024 CUDA + 32 Tensor cores | 唯一的加速器，所有重模型都靠它 |
| DLA | **無** | 不能像 AGX/NX 把第二條推理 lane 卸到 DLA，多模型只能搶同一顆 GPU |
| 算力 | ~67 INT8 TOPS（SUPER / MAXN 模式） | INT8 才到 67 TOPS；FP16 約其半，仍是主力精度 |
| 記憶體 | LPDDR5 8GB 統一記憶體，~102 GB/s | CPU 與 GPU 共用同一池，模型權重 + activation + D435 影像 + ROS2 全擠在這 8GB |
| 軟體棧 | JetPack 6.2 / CUDA 12.6 / TensorRT 10.3 | onnxruntime-gpu 必須用 `jp6/cu126` wheel，TRT-EP 對應 TRT 10.3 |

**功耗模式（直接決定 demo 穩定度）**：

- **15W**：省電/被動散熱情境。GPU 降頻，跑滿載模型（RTMPose-lw、YOLO26n）會掉 FPS，不建議 demo。
- **25W**：日常開發與多感知共存的安全檔。三感知壓測（3/23）即在此區間，實測 18.9W、66°C。
- **MAXN（SUPER）**：解鎖 ~67 TOPS 全速，benchmark 與單模型壓榨用。長時間跑必須配主動散熱，否則撞溫度牆降頻。

**硬體前置（沿用專案現況）**：
- **主動散熱必裝**：RTMPose-lw 滿載時 GPU 91-99%、66°C，已逼近舒適上限；MAXN 長跑沒風扇會 throttle。
- **NVMe 給 TensorRT engine cache**：TRT-EP 首次把 ONNX 編成 engine 要 3-10 分鐘（YOLO26n 實測），cache 寫在 `/home/jetson/trt_cache/`。放 SD card 會讓每次冷啟動都重編、I/O 卡住。**每換一個新模型就多一份 engine cache，磁碟空間要留。**
- **供電**：專案 XL4015 降壓在 Go2 運行中反覆斷電，20V 已是安全極限 — 任何把板子推上 MAXN 的測試，先確認供電穩定，否則掉電比爆顯存更先發生。

### 2. 部署格式與精度：FP16 預設 vs GPU-INT8 校正

板子只認兩條真正能加速的路徑，其餘格式即使 zoo 有勾選，也是給別的矽晶片的，在 Jetson 無效：

| 格式 | 在 Orin Nano 上 | 說明 |
|------|----------------|------|
| **ONNX**（onnxruntime-gpu `jp6/cu126` + TensorRT-EP FP16） | **主路徑，已上機驗證** | YOLO26n + RTMPose-lw 即走此路 |
| **PyTorch**（NVIDIA wheel） | 可，但重 | 啟動慢、佔記憶體多，能轉 ONNX 就轉 |
| **TFLite** | 只能 CPU | 沒有 GPU delegate，僅小模型或臨時驗證用 |
| **TF / TF-TRT** | 僅來源轉檔 | 當作「轉成 ONNX 的中間產物」，不直接部署 |
| **EdgeTPU / CoreML / OpenVINO / TFJS** | **不可** | 錯的矽晶片（Coral / Apple / Intel / 瀏覽器），有勾也忽略，一律改走 ONNX |

**精度規則（這是判定可行性的關鍵）**：
- **FP16 是 GPU 預設，免校正資料**：TRT-EP 直接把 ONNX 降成 FP16 跑，零額外工序。本報告所有「可 / 很可能」判定都以 FP16 為基準。
- **GPU-INT8 需要 calibration**：要再快、再省顯存才上 INT8，但必須準備代表性校正資料集做 PTQ。沒有 DLA，INT8 仍跑在同一顆 GPU 上，只省記憶體頻寬與顯存、不開新 lane。互動主線模型體積已夠小，**多數情況不必動 INT8**，把它留給「想壓 ViT/大偵測器顯存」的少數場景。

### 3. 決策表：model class → 建議配置

把任一 PINTO 資料夾先歸進下面其中一格，就知道怎麼配：

| Model class（典型代表） | 路徑判定 | 建議配置 |
|------|------|----------|
| **CPU lane — 微型 CNN / MediaPipe 系**（YuNet、SFace、BlazePose、BlazeFace、MobileFaceNet、Objectron、MediaPipe Hands、YAMNet、curve-based LLIE 如 Zero-DCE/SCI） | CONFIRMED | 跑 CPU 即可，**不佔 GPU**，與 face+ASR+TTS+ROS2 零壓力共存。這是專案現役 face pipeline 的等級 |
| **GPU-FP16 — 小型單階段 CNN**（YOLOX-nano/tiny、NanoDet、PicoDet、FastestDet、YOLOv6n、YOLOv9-t、Wholebody n 變體、Gold-YOLO-Hand N/S、RTMPose-lw、MS-G3D、輕量分割/SR/單目深度、MobileBERT/DistilBERT、輕量 OCR） | CONFIRMED / LIKELY | **主力配置**：ONNX → onnxruntime-gpu `jp6/cu126` → TRT-EP FP16。與 YOLO26n+RTMPose-lw 同級，可上機。LIKELY 者格式對但未實測，單跑優先、共存需驗 headroom |
| **GPU-FP16 吃緊 — 中量級 / 高解析 CNN**（中量 YOLO/RetinaNet/YOLACT、bottom-up 高解析 pose 如 HigherHRNet/MoveNet MultiPose、中型立體深度、512+ OCR DetectionNet、雨滴/風格 GAN 高解析變體） | LIKELY → RISKY | 可上 GPU-FP16，但**鎖小輸入解析度 + 取小變體**，且原則上**單跑**。要共存先量單跑 RAM 並排程錯開 |
| **需 Orin NX 16GB — Transformer / 大 backbone（單跑勉強、共存爆界）**（DETR/RT-DETR/RT-DETRv2/DEIM、ViTPose-L/B、DINO ViT、DPT/ZoeDepth/Depth-Anything、SAM ViT、TopFormer、SLPT、DSFD-vgg、arcface-resnet100、LVFace/TransFace、PoseC3D、SR Transformer 群、LightGlue/DeDoDe） | RISKY | FP16 仍可載入，但 8GB 統一記憶體在 D435+face+ASR+TTS+ROS2 共存下**會爆**。要把它當常駐能力 → 升 **Orin NX 16GB**（多一倍記憶體 + 兩條 DLA 可分流）。在本板只能離線單跑驗證 |
| **需 AGX — 兩階段 / 重型 cost-volume / 多 GB**（Mask R-CNN、CascadeTableNet、CrowdDet、CREStereo/IGEV/ACVNet 高解析、4K matting、CoCosNet） | RISKY → NO | 算力與顯存遠超 Nano。要實用化請上 **AGX Orin 32/64GB** |
| **不上 Jetson — 矽晶片錯 or 多 GB 生成式**（EdgeTPU/CoreML/OpenVINO/TFJS-only 資料夾如部分 Artistic、無 ONNX 產物如 MobileViT/005 DOC、Stable Diffusion 328、Diffusion-Low-Light 418） | NO | 矽晶片不對 → 必須自原始碼重建 ONNX 才談得上；多 GB 擴散模型超出 8GB 且非即時，與本專題無關，**不納入 runtime** |
| **pipeline 不成立**（SFA3D 需 3D LiDAR 點雲 BEV、2D→3D lifting 需先接上游 2D 偵測器、skeleton action 需先跑 pose 抽關節） | 視上游而定 | 格式可行不代表能跑：Go2 只有 RPLIDAR 2D + D435，缺上游就是死路。先確認資料來源 |

### 4. 8GB 統一記憶體共存預算 vs PawAI live stack

8GB（實際可用 ~7.6GB）必須同時養活 PawAI 的常駐 live stack：**D435 + 人臉（YuNet/SFace）+ ASR + TTS + ROS2**。鐵律是任何時刻保留 **≥0.8GB headroom**。

- **已驗證的 co-residency 上限**：RTMPose-lw 單模型滿載時 RAM 5.0/7.6GB（GPU 91-99%）。換言之，**一個 GPU-FP16 主力模型 + live stack 已接近天花板**，再塞第二個 GPU 模型前必須先量。
- **多感知實測甜蜜點**：face(CPU)+pose(CPU)+gesture(CPU) 三感知壓測 RAM 僅 1.2GB、GPU 0% — **能下放 CPU 的就下放**，把 GPU 完整留給一個重模型。
- **L2 共存衰減參考**：face(CPU)+pose(CUDA) −6%、SCRFD(GPU)+pose −10%、whisper(CUDA)+pose −20%。**兩個 GPU 模型搶同一顆 Ampere 必然互相拖慢**（沒 DLA 可分流），規劃時把第二個 GPU 模型的 FPS 預期打 8-9 折。
- **加任一 PINTO 模型前的檢查**：(1) 能不能走 CPU lane？能就不佔預算；(2) 走 GPU-FP16 後單跑 RAM 多少？(3) 加進 live stack 後 headroom 是否仍 ≥0.8GB？三題有一題不過，就降解析、改小變體、或挪到離線批次跑，**別跟 live stack 同框**。

### 5. 何時該換板（升級訊號）

留在 Orin Nano SUPER 8GB 的條件：目標模型落在前表「CPU lane / GPU-FP16」兩格，且加進 live stack 後 headroom ≥0.8GB。出現以下任一訊號，就不是調參能解決，而是該升板：

- **想常駐一個 Transformer / 大 backbone**（RT-DETR、ViTPose-L、Depth-Anything、SAM…）並與 live stack 同跑 → 8GB 撐不住，**升 Orin NX 16GB**（記憶體翻倍，且有 2× DLA 可把第二條 lane 從 GPU 卸開，正好補上 Nano 無 DLA 的痛點）。
- **要同時跑兩個以上 GPU 重模型**（例如重型偵測 + 重型 pose 並行）→ 單顆 Ampere + 無 DLA 是硬牆，**升 NX 16GB 或 AGX**。
- **目標是兩階段偵測 / 重型 cost-volume 立體 / 4K matting / 多 GB 生成式** → 直接規劃 **AGX Orin 32/64GB**，Nano 連單跑都吃力。
- **反過來：若全部需求都在 CPU lane + 單一 GPU-FP16 小模型**（PawAI 互動主線正是如此 — 132 YOLOX-nano / 072 NanoDet / 459-471 YOLOv9 Wholebody + RTMPose-lw + 033/403 手勢 + YuNet/SFace），**現有 Orin Nano SUPER 8GB 已足夠，不需升板**，把預算花在主動散熱與穩定供電上更划算。

---

## 附錄 A：數量對帳

- 編號資料夾 483 個（001→488，非連續有跳號）− `999_media`（素材夾）= **482 個真實模型**。
- README「List of pre-quantized models」巨表 row 加總約 456，少於 482，原因：①7 個最新模型（如 `488_DEIMv2-Wholebody49`、`419_MobileViT`）尚未收進 README 表；②部分 row 把多個 folder 變體（Wholebody / RTMPose / Gold-YOLO 家族）併成一行。**權威數字以資料夾為準：482。**
- 本文件各類 dir 數加總 = 484（含 `167_LSTR`、`313_IS-Net` 等跨類重複列各 +1）。

## 附錄 B：PawAI registry 對映（哪些已被我們 shortlist）

| PawAI 模組 | PINTO folder | 類別 | Tier（依 capability-baseline-spec） |
|---|---|---|---|
| 人臉偵測 主線/備援 | `144_YuNet`、`387_YuNetV2`、`129_SCRFD` | §4 | BASELINE_NOW |
| 人臉識別 embedding | `256_SFace` | §1 | BASELINE_NOW |
| 姿勢 主線/備援 | `053_BlazePose`、`393/427_RTMPose`、`440_ViTPose` | §6 | BASELINE_NOW |
| ASR fallback | `381_Whisper` | §12 | SPIKE_AFTER_FAIL |
| 物件 fallback | `132_YOLOX`、`174_PicoDet`、`072_NanoDet` | §2 | SPIKE_AFTER_FAIL |
| 手勢 | `481_WHC`(揮手, go/no-go 2026-06-06)、`477_PGC`(指向) | §1 | SPIKE_AFTER_FAIL |
| 導航視覺 | `146_FastDepth`、`439_Depth-Anything`、`116_DroNet` | §7/§2 | FUTURE_RESEARCH |

## 附錄 C：方法與信心

- 結構（19 類 / 482 folder）：直接從 commit `870b2b8` 的 git tree 抽，100% 確定。
- 每個模型功能/表現：由 19 個並行 agent 讀 README 對應段落 + WebSearch 知名架構基準產出；冷門模型標「無公開基準/依變體而定」而非杜撰。
- Jetson 判定：以已建立的部署封套（SUPER 8GB 規格 + 格式 + 記憶體預算）為準則；與 PawAI 直接相關的 24 個候選另經實讀 `convert_script.txt` 驗證 ONNX + 解析度 + footprint。
- **未實機跑過**的模型一律最高給「很可能」，不給「可」——「可」保留給 PawAI 已上機證明或同架構同 footprint 的等級。
