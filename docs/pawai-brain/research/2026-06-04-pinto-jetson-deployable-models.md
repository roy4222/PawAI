# 目前確定可在 Jetson 上使用的模型清單（PINTO_model_zoo → Orin Nano SUPER 8GB）

> 🔬 **RESEARCH-ONLY — research-not-truth**。本檔是「可部署性」研究，**不是**實作 backlog、**不是**能力 pass 真相。除已實機 5 個錨點外其餘 tier 為推定。能力是否 pass 以 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) 為準；能不能講連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。索引見 [`README.md`](README.md)。
> 🏷️ **Tier**：`FUTURE_RESEARCH`（除 5 個已實機錨點為地面真值外）。不把清單預設變成 6/18 backlog。

> 產出日期：2026-06-04 Asia/Taipei
> 來源：`PINTO0309/PINTO_model_zoo` @ `870b2b8` ｜ 目標板：Jetson Orin Nano SUPER 8GB（JetPack 6.2）
> 完整 19 類解析見姊妹文件：[`2026-06-04-pinto-model-zoo-full-analysis.md`](2026-06-04-pinto-model-zoo-full-analysis.md)
> 本清單的「✅ 已實機證明」以 PawAI 在這塊板上的實測為地面真值；其餘 tier 為架構+格式+footprint 推定。

---

## (a) 一句話結論 + 兩道門檻

**一句話結論**：能「確定」上機的，是 **ONNX 格式 + 小尺寸（CNN / tiny 嵌入器 / 微型分類器）** 這一類——PawAI 已經在這台 Orin Nano SUPER 8GB 上實機跑過好幾個同架構、同 footprint 的模型（人臉 YuNet/SFace、pose MediaPipe 走 CPU；YOLO26n + RTMPose-lw 走 GPU-FP16，實測 5.0/7.6GB）。凡是同格式、同 runtime、footprint 相同或更小、且已在「同一塊板」上跑過的，就是真確定，不是樂觀推測。

任何模型要進「確定可用」清單，必須**同時**通過兩道門檻：

| 門檻 | 內容 | 不過就出局 |
|------|------|-----------|
| **門檻 1：格式正確** | 必須能走 `ONNX → onnxruntime-gpu(jp6/cu126 wheel) + TensorRT-EP FP16`（或 CUDA EP / CPU XNNPACK）這條 PawAI 唯一實證主線。PyTorch 走 NVIDIA torch wheel 可行但重。 | EdgeTPU / CoreML / OpenVINO / TFJS 全屬**錯誤晶片**，在 ARM64 + Ampere 上物理上無法執行；TFLite 只能 CPU；TF saved_model / TF-TRT 只當轉換來源勿上機。 |
| **門檻 2：塞得進 8GB UNIFIED** | 8GB 是 CPU+GPU+D435 buffer 共用一池（無獨立 VRAM），可用約 7.6GB。CLAUDE.md 硬規則：D435+face+ASR+TTS+ROS2 共存時必須保留 **≥0.8GB headroom**。每個 GPU 模型的 weights + TensorRT engine + CUDA context（光 context ~0.6-1GB）都要塞進 live stack 剩下的空間。 | transformer / ViT / 多 GB 權重的大模型在 FP16 下仍會撐爆預算（FP16 是 PawAI 預設、無解；GPU-INT8 需校正且 PawAI 未在 CUDA 路徑採用）。 |

> 板規（Envelope）：Ampere 1024 CUDA + 32 Tensor cores、**無 DLA**、~67 INT8 TOPS（SUPER/MAXN）、LPDDR5 ~102GB/s、15W/25W/MAXN。JetPack 6.2 / CUDA 12.6 / TensorRT 10.3。GPU 預設 FP16（不需校正）。

---

## (b) 已實機證明（PawAI 現在正在跑）— 黃金標準

這 5 個（含 YOLO26n + RTMPose-lw 一組 GPU lane）是**唯一有實測數字**的，其他所有判定都以它們為基準錨點。

| 模型 / lane | 功能 | 解析度 | footprint（實測 / 推算） | runtime 路徑 | 實測狀態 |
|------------|------|--------|------------------------|-------------|---------|
| **YuNet 2023mar**（=144_YuNet）| 人臉偵測（主線）| 120×160 | ONNX <1MB，~85K params | **CPU**（OpenCV DNN，A78AE）| **71.3 FPS**，JETSON_LOCAL，3/21 決策定案 |
| **SFace 2021dec**（=256_SFace）| 人臉識別（主線）| 112×112 | ONNX ~37MB，~24M params | **CPU**（OpenCV DNN）| 生產中，GPU 0% |
| **MediaPipe Pose**（=053_BlazePose 同類）| 姿勢估測（主線）| 256×256 landmark | lite ~2-3MB | **CPU**（XNNPACK）| **18.5 FPS**，GPU 0% |
| **YOLO26n** | 物件偵測（主線，COCO）| 640×640 | ONNX **9.5MB**，output (1,300,6) | **ONNX→TRT FP16**，onnxruntime-gpu 1.23.0 | 跑中，TRT cache 首建 3-10 分鐘 |
| **RTMPose-lw**（=427 同 CSPNeXt+SimCC 家族）| 姿勢（GPU 備援）| 256×192 | ONNX ~13-15MB | **ONNX→TRT FP16** | **GPU 91-99%**、66°C、18.9W、**RAM 5.0/7.6GB**（與上面同跑）|

> 三感知 CPU 壓測（face+pose+gesture 同跑 60s）實測僅 **~1.2GB** total、52°C、GPU 0%。這是 CPU-tiny 類模型的真實基線。

---

## (c) CONFIRMED — 可直接從 PINTO 拉、確定可用

判定 = **ONNX + 小尺寸 + 與已實證模型同架構/同或更小 footprint**。共 17 個（含上面 5 個本體）。下載一律：`git show HEAD:<folder>/download*.sh` → curl Wasabi `resources.tar.gz`。

| folder | 功能 | 解析度 | footprint | runtime 路徑 | 下載 |
|--------|------|--------|-----------|-------------|------|
| **144_YuNet** | 人臉偵測（PawAI 主線本體）| 120×160 | ONNX <1MB / ~85K params | CPU（OpenCV DNN）71.3 FPS | `144_YuNet/download.sh` |
| **387_YuNetV2** | 人臉偵測（同 opencv_zoo V2 打包）| 640×640（dynamic，可 320/160）| ONNX ~227KB fp / ~340KB int8 | CPU（ort）優先；可選 GPU-FP16 | `387_YuNetV2/download.sh` |
| **129_SCRFD** | 人臉偵測（PawAI 已選備援 500m）| 480×640（可 240×320 求快）| ONNX ~2.5MB / 0.57M params / 0.5 GFLOPs | ONNX→TRT FP16 或 CPU | `129_SCRFD/download.sh` |
| **256_SFace** | 人臉識別（PawAI 主線本體）| 112×112 | ONNX ~37MB / ~24M params | CPU（OpenCV DNN）GPU 0% | `256_SFace/download.sh` |
| **053_BlazePose** | 姿勢估測（PawAI pose 主線同類）| det 128×128 / landmark 256×256 | lite ~2-3MB / heavy ~26MB | CPU（XNNPACK）18.5 FPS | `053_BlazePose/download.sh` |
| **427_RTMPose_Hand** | 手部 21 keypoint（手勢備援）| 256×256 | ONNX ~13-15MB / ~2.58 GFLOPs | ONNX→TRT FP16（**需上游手偵測**）| `427_RTMPose_Hand/download.sh` |
| **072_NanoDet** | 物件偵測（COCO，比 YOLO26n 更小）| 320×320 / 416×416 | ONNX ~3-4MB / ~0.95M params | ONNX→TRT FP16（drop-in object lane）| `072_NanoDet/download.sh` |
| **132_YOLOX**（僅 nano/tiny）| 物件偵測（COCO）| 320×320 / 416×416 | nano ~3MB / tiny ~20MB | ONNX→TRT FP16（**僅 n/t**）| `132_YOLOX/download.sh` |
| **174_PP-PicoDet**（s/m）| 物件偵測（COCO-80）| 320×320 / 416×416 | picodet_s ~5MB / m ~8MB | ONNX→TRT FP16（paddle2onnx）| `174_PP-PicoDet/download.sh` |
| **471_YOLO-Wholebody34**（僅 N/T/S）| 全身 34-class 偵測（多任務）| 480×640（可 240×320）| N 變體 **2.4MB** | ONNX→TRT FP16（內嵌後處理）| `471_YOLO-Wholebody34/download.sh` |
| **458_YOLOv9-Discrete-HeadPose-Yaw**（僅 N/T/S）| 頭姿 yaw 偵測 | 480×640（可 240×320）| N 變體 **2.4MB** | ONNX→TRT FP16（內嵌 NMS）| `458_YOLOv9-Discrete-HeadPose-Yaw/download.sh` |
| **481_WHC** | 揮手分類器（gesture-cls）| 3×{4/6/8}×32×32 | ONNX **~1.1MB** | ONNX→TRT/CUDA EP，或 CPU 0.3-0.8ms | `481_WHC/download.sh` |
| **477_PGC** | 指向手勢分類器 | 32×32 | S 494KB / L 6.4MB | CPU 0.43-0.78ms 或 TRT/CUDA EP | `477_PGC/download.sh` |
| **478_SC** | 全身姿態狀態分類器（sitting 等）| 32×24 | 115KB ~ 875KB | **CPU 0.13-0.47ms**，GPU 0% | `478_SC/download.sh` |

> **同類延伸（同樣 CONFIRMED，整批可直接拉）**：分類/屬性類 `004_efficientnet`、`010/011_mobilenetv*`、`016_EfficientNet-lite`、`317_MobileOne`、`379_PP-LCNetV2`、`191_anti-spoof-mn3`、`290_AdaFace`、`435_MobileFaceNet`、`452_FairFace`、`259_Emotion_FERPlus`、`346_..._mobilefacenet`；偵測/追蹤類 `308_FastestDet`、`341_YOLOv6`、`356_EdgeYOLO`、`262_ByteTrack`、`087_DeepSort`、`420_Gold-YOLO-Hand`、`422_Gold-YOLO-Head-Hand`、`424/425/426_..._Body-Head-Hand`、`449_YOLOX-WholeBody12`、`454/456/457_YOLOv9-Wholebody*`；人臉 `030_BlazeFace`、`095_centerface`、`096_RetinaFace`、`399_RetinaFace_MobileNetv2`、`032/410_FaceMesh`、`043_face_landmark`；pose `115_MoveNet`、`268_Lite-HRNet`、`333_E2Pose`、`007/088_mobilenetv*-poseestimation`。判定理由相同：ONNX + tiny CNN + 同 proven 架構帶。

---

## (d) LIKELY — 格式對、footprint 可能塞得下，但**需上機量一次**才能升 CONFIRMED

判定 = ONNX 確定、推算可行、但**從未在這塊板上量測過**（或 size tier 未宣告）。共識：先做一次性 live-stack RAM + 冷 TRT-build 探針即可定案。

| folder | 功能 | 解析度 | footprint | runtime 路徑 | 為何只是 LIKELY / 要量什麼 | 下載 |
|--------|------|--------|-----------|-------------|--------------------------|------|
| **393_RTMPose_WholeBody** | 全身 133-keypoint pose | 256×192（m）/ 384×288（l/x）| m 數十 MB ONNX，比 lw 重 | ONNX→TRT FP16 | RTMPose 家族確定，但只有 m/l/x（無 nano/tiny），比已測 lw 重；m@256×192 可能可共存但未量。**先量 m 變體**，l/x 別用 | `393_RTMPose_WholeBody/download.sh` |
| **381_Whisper** | ASR（語音）| 80-mel × 3000-frame | tiny ~75MB → large ~3GB（tier **未宣告**）| ORT CUDA EP FP16（非乾淨 TRT）| size tier 沒寫；非 PawAI 在跑的 faster-whisper；autoregressive enc-dec 不吃乾淨 TRT。**先確認 tarball 是哪個 tier**，tiny/base/small FP16 可能可，medium/large→降 RISKY | `381_Whisper/download.sh` |
| **423_6DRepNet360** | 頭姿 6D（gazing）| 224×224 | RepVGG-class CNN ~10-30MB ONNX | ONNX→TRT FP16 | footprint band 同 YOLO26n，但未量測且需**上游 Gold-YOLO 頭偵測雙引擎共存**。量雙引擎 RAM + 冷建 | `423_6DRepNet360/download.sh` |
| **146_FastDepth** | 單目深度（depth-nav）| 224×224 / 256×320 | ~3.9M params，FP16 ~8MB ONNX | ONNX→TRT FP16 | MobileNet-class 格式 footprint 安全，但 PawAI **從未跑過任何 depth 模型**，depth-nav 不在 live stack。量一次即可升 CONFIRMED | `146_FastDepth/download.sh` |
| **464_YOLOv9-Wholebody28**（n/t/s）| 全身 28-class 偵測 | 256×320 ~ 480×640 | n/t ~YOLO26n class | ONNX→TRT FP16 | n/t/s 同 YOLO 偵測帶，但 28-class head + 480×640 比 YOLO26n 重；c/e→RISKY/NO。量 n/t 共存 | `464_YOLOv9-Wholebody28/download.sh` |
| **116_DroNet** | 物件偵測（車/人，conv backbone）| 608×608 | 真實檔案大小未知（opaque tarball）| ONNX(opset11)→TRT FP16 | 純 conv 無 transformer，但 608² activation 重、檔案大小未知、從未上機。量 live-stack RAM + 冷 TRT。注意：是**偵測器非碰撞機率網**，nav lane 需重訓 | `116_DroNet/download.sh` |

> **同類延伸（同樣 LIKELY，可挑一個上機量）**：reID/追蹤 `429_OSNet`、`430_FastReID`；頭姿/landmark `300_6DRepNet`、`421_Gold-YOLO-Head`、`437_PIPNet`、`340_Dense-Head-Pose`；偵測 `307_YOLOv7`、`334_DAMO-YOLO`、`336_PP-YOLOE-Plus`、`337_FreeYOLO`、`042_centernet`、`103_EfficientDet_lite`；深度一整類 `067_MiDaS`、`081_MiDaS_v2`、`371_Lite-Mono`、`162/314_PyDNet*`、`338_Fast-ACVNet`、`358_CGI-Stereo`、`384_TCMonoDepth`；分割 `057_BiSeNetV2`、`061_U-2-Net`、`078_MODNet`、`228_Fast-SCNN`、`335_PIDNet`、`196_pphumanseg`、`242_RobustVideoMatting`。共同邏輯：ONNX 有、footprint 推算可行、**未在這塊板量測過**。

---

## (e) RISKY 與不可（NO）— 簡列 + 原因

### RISKY（格式對但 8GB 共存可能爆，不可說「確定可部署」）

| folder | 功能 | 原因（為何不 CONFIRMED 也不 NO）|
|--------|------|------------------------------|
| **440_ViTPose** | ViT pose | ViT backbone。僅 S(~24M/~48MB)勉強候選且仍 ~5x YOLO26n、需上游人偵測；B/L/H(170MB~1.2GB)在 8GB unified **必破 0.8GB headroom**，FP16 無解需 INT8 校正（未採用）。PawAI 無任何 ViT pose 跑過 |
| **485_DEIMv2-Wholebody40** | 全身 40-class（含 seg）| DINOv3-X ViT + DETR(800 query) + 256×3 mask head。**唯一變體即最大**；數百 MB-class 權重，FP16 共存幾乎破 headroom，ViT+DETR 冷建可能 **>10 分鐘**，README 自評 experimental/incomplete |
| **488_DEIMv2-Wholebody49** | 全身 49-class（含 seg）| DINOv3-X ViT+DETR(1240 query)+maskhead，**推薦權重即 X**（S/N 作者自棄），作者明言 **FP16 顯著劣化 mask 品質**——剛好踩 PawAI FP16 GPU 路徑。footprint + 冷建 + 精度三重未驗 |
| **439_Depth-Anything** | 單目深度 | DINOv2 ViT + DPT。僅 vits14(~25M/~50MB FP16)勉強候選但 480×640 ViT attention 共存 headroom 未證；vitb/vitl(~97M/~335M，vitl ~1.3GB) 直接 NO |

> 同類 RISKY 邏輯延伸：凡 transformer/ViT/DETR backbone 的大變體（`455` 以上的重型 wholebody、`MHFormer`/`STCFormer` 類 transformer pose、大尺寸 stereo/seg）一律先做探針，別預設可用。

### NO（錯誤晶片格式，物理上不能在 Ampere 執行）

| 格式 | 為何 DOA |
|------|---------|
| **EdgeTPU**（`.tflite-edgetpu` blob）| 僅 Coral Edge TPU ASIC，Jetson 無此矽 |
| **CoreML** | Apple ANE/Metal 專屬，Linux ARM64 無 runtime |
| **OpenVINO** | Intel CPU/iGPU/VPU/NPU 專屬，無 NVIDIA-GPU backend |
| **TFJS** | 瀏覽器/Node WebGL-WASM 目標，對 ROS2 perception node 為錯誤執行環境 |

> 注意：**候選層級沒有整顆 NO 的模型**——上述四種只是「匯出選項」，同一個 folder 通常也提供 ONNX。最重的 DEIMv2/ViTPose 大變體歸 RISKY（ONNX-FP16 在 Ampere 物理上可跑，只是 8GB 共存爆預算），不是 NO。真正 NO 的是「只剩這四種格式」的那條輸出路徑。

---

## (f) 8GB 記憶體共存鐵律

1. **8GB 是 UNIFIED**：CPU + GPU + D435 buffer 共用一池，**無獨立 VRAM**，可用實際約 **7.6GB**（kernel/display 吃掉其餘）。
2. **硬規則：≥0.8GB headroom**。D435+face+ASR+TTS+ROS2 共存時必須保留，否則 OOM/swap。
3. **預算對「正在跑的 stack」算，不是空板**。實證基線：RTMPose-lw 單獨即坐 **5.0/7.6GB**（GPU 91-99% GPU-bound）；3-perception CPU 壓測僅 **~1.2GB**。
4. **每個新 GPU 模型 = weights + TensorRT engine + CUDA context**。光 CUDA context 就 ~0.6-1GB，要塞進 live stack 剩下的空間。
5. **不能把 CONFIRMED 全開**。任一個可舒服地**單跑或替換現有 lane**，但不能同時全載。
6. **FP16 是 GPU 預設**（不需校正）；GPU-INT8 需校正且 PawAI 未在 CUDA 路徑採用。CPU-tiny 類（YuNet/SFace/478/477）幾乎不吃 headroom，可疊。
7. **Demo 模式關 RViz/Foxglove/Nav2/SLAM** 回收記憶體，再給 GPU 模型騰空間。
8. **首跑成本**：每個新 ONNX→TRT 模型首次冷建引擎 **3-10 分鐘**（cache 到 `/home/jetson/trt_cache/`）；transformer 冷建可能 >10 分鐘（RISKY 觸發條件）。

---

## (g) 最安全的 3 個建議（go 為真，零或近零新風險）

1. **129_SCRFD（scrfd_500m）— 補人臉備援 lane**
   直接補 PawAI 3/21 已選定的人臉備援（SCRFD-500M → JETSON_LOCAL）。~2.5MB ONNX，CPU 或 GPU-FP16 皆可，與已跑的 YuNet 同 lane 同 runtime，**零新風險**。

2. **072_NanoDet（或 132_YOLOX-nano）— 物件 lane 更輕量備援**
   ~3MB，比現役 YOLO26n（9.5MB）更省，drop-in 進現有 `object_perception` 的 `ONNX→TRT FP16` 路徑，同 COCO 偵測架構帶。

3. **481_WHC（或 477_PGC）— 揮手/指向手勢分類器**
   sub-1.1MB tiny CNN，直接對口 gesture-cls lane 與 6/6 wave-classifier spike。CPU 0.3-0.8ms 近乎免費（GPU 0%），**go 判定為真**；唯一整合工作是接上游 hand/body crop feeder，非部署阻礙。
