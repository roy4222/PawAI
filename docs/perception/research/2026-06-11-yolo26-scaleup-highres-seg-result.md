# YOLO26 規模升級 + 高解析輸入 + seg 變體 研究結果（cup 遠距主攻線）

> **日期**：2026-06-11
> **對應 goal**：`docs/perception/research/goals/2026-06-11-yolo26-scaleup-highres-seg-goal.md`
> **Verdict**：**GO_BENCH_MATRIX**（§5 附 ≤4 配置上機矩陣：配置／預估FPS／預估RAM／pass-fail 門檻／WSL 前置動作）
> **本研究為 read-only**：未改 code、未 commit、未安裝任何東西。
> 引用格式：`file:line`（本 repo 絕對相對路徑）或 URL；**外推數字一律標明假設與來源世代**。

---

## TL;DR

1. **YOLO26s@640 才是第一刀，不是 n@1280**——兩者 GFLOPs 幾乎相等（20.7 vs 21.6），但 s@640 有官方 trained-at-640 的 **+7.7 mAP**（40.9→48.6）背書，n@1280 的「推理時放大」沒有任何官方數字、社區證據混雜，而且**現役相機只餵 640x480**，餵 1280 模型等於純插值放大。⚠️ 此結論**修正 PINTO 報告 §5a 的「第一刀 = re-export imgsz=1280」**（見 §4）。
2. **PawAI 的 6-8Hz 根本不是模型瓶頸**：官方 Orin Nano Super 上 YOLO26n TRT FP16 純推理只要 **4.57ms（~219 FPS）**；6-8Hz 是 `publish_fps: 8` 上限 + tick 0.067s + Python 前後處理（HSV 12 色、PIL CJK overlay）的合成結果。換 s 級模型對 node Hz 的衝擊是次線性的——預估只掉 1-2Hz，遠在 S3 事件驅動可接受下限（≥3Hz）之上。
3. **seg 變體對 cup recall 是純虧損**：YOLO26s-seg box mAP 47.3 **低於** s 偵測版 48.6，GFLOPs 卻 +65%（34.2 vs 20.7），mask 後處理還要吃 CPU。本矩陣剔除 seg，輪廓/顏色需求留給 goal 3 另案。
4. **RAM 大致放得下**（s@640 / n@960 預估 delta +100~250MB），唯 s@960 邊緣（+300~600MB 估）；**真正的 RAM 殺手是上機日現燒 TRT engine**（workspace 上限預設 1GB）——SOP 必須「前一晚單獨燒 engine、demo stack 不同時跑」。
5. 基礎建設**已經就位**：launch 已有 `OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env 一行切換 + TRT cache 按 model stem 分目錄（6/10 model A/B 準備），上機日只缺 WSL 匯出的 3 個 ONNX 檔。

---

## §1 Findings（≥30 條，附引用）

### A. YOLO26 家族規格（官方）

- **F1** YOLO26 偵測版全家族官方規格：n = **2.4M params / 5.4 GFLOPs / mAP 40.9（e2e 40.1）/ T4 TRT 1.7ms**；s = **9.5M / 20.7 / 48.6（47.8）/ 2.5ms**；m = **20.4M / 68.2 / 53.1（52.5）/ 4.7ms**；l = 24.8M/86.4/55.0；x = 55.7M/193.9/57.5。（https://docs.ultralytics.com/models/yolo26/ 效能表）
- **F2** s 對 n 的整體 mAP 增益 = **+7.7**（48.6 vs 40.9；e2e 口徑 +7.7：47.8 vs 40.1），代價 3.83x GFLOPs。官方表**沒有單獨列 AP-small**（見 Q1 的處理）。（同上）
- **F3** YOLO26 官方有 **六個 task 變體**：detect / **-seg**（instance）/ -sem（semantic）/ -pose / -obb / -cls，全部五個尺度（n-x），inference/val/train/export 全 ✅，無 “coming soon” 標記。（https://docs.ultralytics.com/models/yolo26/ Supported Tasks 表）
- **F4** seg 變體官方數字：**YOLO26n-seg = 2.7M / 9.1 GFLOPs / box mAP 39.6 / mask mAP 33.9 / T4 TRT 2.1ms**；**YOLO26s-seg = 10.4M / 34.2 GFLOPs / box 47.3 / mask 40.0 / 3.3ms**。（https://docs.ultralytics.com/tasks/segment/ 效能表）
- **F5**（推導自 F1+F4）**s-seg 的 box mAP（47.3）比 s 偵測版（48.6）低 1.3，GFLOPs 卻多 65%**（34.2 vs 20.7）——對「cup 看得到/看不到」這個 box-recall 問題，seg 變體是嚴格劣勢配置。
- **F6** seg 對 YOLO11 的增益宣稱：「up to +2.5 box AP and +3.7 mask AP on COCO instance segmentation」；pose「up to +7.2 AP」。（https://docs.ultralytics.com/models/yolo26/）
- **F7** 小物件機制：YOLO26 引入 **ProgLoss + STAL**——「STAL improves positive label coverage for small objects」「STAL prioritizes assignment for tiny or occluded instances, improving recall under clutter, foliage, or motion blur」；並移除 DFL 簡化 head。注意：這是 n 與 s **都有**的家族級特性，不構成 n/s 之間的差異。（https://docs.ultralytics.com/models/yolo26/；arXiv 2509.25164 https://arxiv.org/abs/2509.25164）

### B. 輸出格式 / export 行為

- **F8** e2e 輸出格式：one-to-one head（預設部署）輸出 **`(N, 300, 6)`**，`[x1,y1,x2,y2,conf,class_id]` xyxy；備用 one-to-many head 輸出 `(N, nc+4, 8400)` 需傳統 NMS。（https://docs.ultralytics.com/guides/end2end-detection 表格；https://docs.ultralytics.com/models/yolo26/）
- **F9** **`(1,300,6)` 的 300 = `max_det`，與 imgsz 無關**：「the output is shaped like `(batch_size, max_detections, 6)`…With the default `max_det=300`, this is commonly `(batch_size, 300, 6)`」。imgsz 改 1280 後 shape 不變，只有 bbox 座標域變成 1280-letterbox 空間。（https://docs.ultralytics.com/modes/export/）
- **F10** **`max_det` 可在 export 時調**：`model.export(format="onnx", max_det=500)`；但官方警告「the default YOLO26 checkpoints were trained with `max_det=300`…detections beyond that limit may be lower quality」。（https://docs.ultralytics.com/guides/end2end-detection）
- **F11** export `imgsz` 支援 int（方形）或 `(h,w)` tuple（如 `(720,1280)`）；ONNX export 參數含 `dynamic`（預設 False）、`half`、`simplify`（預設 True）、`opset`、`nms`（預設 False）、`batch=1`。（https://docs.ultralytics.com/modes/export/ Arguments 表）
- **F12** seg 變體 ONNX 輸出 = 偵測 tensor + prototype tensor 兩個輸出；**proto 解析度 = stride-8 特徵圖再一次 ×2 上採樣 = 輸入的 1/4**（maintainer 原文：「the first segmentation feature map is the stride-8 map, so for a 256 input it is 32×32; one ×2 upsample makes the raw proto tensor 64×64」→ 640 輸入 proto 為 160×160）。mask 合成 = 係數 × proto 線性組合 + sigmoid + per-instance resize，**全在模型外的 CPU 後處理**。（https://github.com/ultralytics/ultralytics/issues/23820）
- **F13** **seg export 是否同樣 e2e NMS-free，官方文件沒有明文**（只確認偵測版 dual-head）；採 seg 前需在 WSL 實際 export 檢查輸出 shape——又一個不選 seg 進本輪矩陣的理由。（https://docs.ultralytics.com/models/yolo26/；https://docs.ultralytics.com/tasks/segment/ 均無 seg e2e 輸出 shape 說明）

### C. Jetson / Orin Nano 實測錨點

- **F14** **官方 Jetson 錨點（本研究最重要單一數字）**：Jetson **Orin Nano Super** Dev Kit（JP6.1, Ultralytics 8.4.33, imgsz=640，不含前後處理）：**YOLO26n TensorRT FP16 = 4.57 ms/im（≈219 FPS）, mAP50-95 0.4800**；FP32 7.53ms；INT8 3.80ms（mAP 掉到 0.449）；ONNX(ORT) 15.76ms；PyTorch 15.60ms。（https://docs.ultralytics.com/guides/nvidia-jetson/）
- **F15** 官方 Jetson 指南**只有 YOLO26n 一個尺寸的數據**——表頭列了 n/s/m/l/x 但實際數據行只有 n；s 級必須靠社區錨點外推。（同上，二次確認）
- **F16** 官方表內 **AGX Orin (64GB) 的 TRT FP32/FP16 行 mAP 只有 0.045**（INT8 反而 0.464；8.4.32 跑的）——不論是文件 bug 還是該版 export 迴歸，都證明 **TRT engine 燒完必須做 mAP/偵測 sanity check**，不能假設轉換無損。（https://docs.ultralytics.com/guides/nvidia-jetson/ AGX Orin 表）
- **F17** **s 級錨點 ①（純 engine）**：NVIDIA 官方論壇實測 **YOLOv8s TensorRT C++ FP16 在 Orin Nano 8GB = 103 qps（≈9.7ms）**、INT8 157 qps（世代：YOLOv8s = 28.6 GFLOPs，比 YOLO26s 的 20.7 重 38%）。（https://forums.developer.nvidia.com/t/jetson-orin-nano-fp16-int8-performance/326723）
- **F18** **s 級錨點 ②（端到端 pipeline）**：arXiv 2502.15737（drone 邊緣部署效能分析，受測含 Jetson Orin Nano）：**YOLOv8s FP16 ≈26 FPS（1558 inferences/min, 7.836W）**、YOLOv8s INT8 28.25ms（≈35 FPS）——這是含前後處理的 Ultralytics pipeline 口徑，與 F17 的純 engine 口徑相差 ~4x，正好框出「engine 快、Python pipeline 慢」的範圍。⚠️ RAM 變體/功耗模式論文摘要未載明，引用時標不確定。（https://arxiv.org/abs/2502.15737；FPS/W 數字出自該文結果表，經 WebSearch 摘錄）
- **F19** **比例交叉驗證**：Stereolabs 在 AGX Orin 32GB 實測 YOLOv8s TRT8.4 FP16 @640 = **260 FPS**（3.85ms）。**「AGX Orin ≈ Orin Nano 算力 2.5-3x」的出處與口徑**（NVIDIA 官方規格）：AGX Orin 32GB = **200 INT8 TOPS / 1792 CUDA cores / 56 Tensor cores**；Orin Nano 8GB = **67 TOPS（Super 模式；原版 40）/ 1024 CUDA cores / 32 Tensor cores**——TOPS 口徑 200/67 ≈ **3.0x**（INT8 sparse），CUDA core 數口徑 1792/1024 = **1.75x**（AGX 32GB GPU clock 較原版 Orin Nano 高再放大），原版 40 TOPS 口徑 = 5x 為上限；FP16 dense 工作負載取 **2.5-3x** 工作區間。推回 Orin Nano ≈ 87-104 FPS，與 F17 的 103 qps 吻合（實測比 260/103 = **2.52x**，落在區間內），錨點可信。（https://www.stereolabs.com/blog/performance-of-yolo-v5-v7-and-v8；https://developer.nvidia.com/embedded/jetson-modules；https://www.nvidia.com/content/dam/en-zz/Solutions/gtcf21/jetson-orin/nvidia-jetson-agx-orin-technical-brief.pdf）
- **F20** **Python pipeline 開銷錨點 ①**：NVIDIA 論壇案例——yolov8n 在 Orin Nano 8GB 用 Ultralytics Python+TRT 只有 **10 FPS**，但 trtexec 純推理 ~12ms（>80 qps）；版主結論「Usually, the bottleneck comes from data read/write」與後處理。（https://forums.developer.nvidia.com/t/slow-fps-on-orin-nano-8-gb-yolov8/280071）
- **F21** **Python pipeline 開銷錨點 ②**：ultralytics issue #22479——YOLO11n 在 Orin Nano Super（25W、JP6.2、有 warmup、千次平均）Python 量測 TRT FP16 = **16ms vs 官方 4.53ms，3.5x 差距**，至今未解。官方 benchmark 數字不能直接當 node 內延遲預期。（https://github.com/ultralytics/ultralytics/issues/22479）
- **F22** **Orin Nano「Super」= 同硬體韌體升級**：JetPack 6.x 後原 Orin Nano 8GB devkit 可解鎖 25W / MAXN SUPER 模式，NVIDIA 宣稱 AI 效能 1.7x（67 TOPS）。官方 F14 數字是 Super 模式 + `nvpmodel -m 0` + `jetson_clocks` 跑的；**PawAI Jetson（JP6/cu126）當前 nvpmodel 模式未驗證**——若仍在舊 15W 檔，全部官方/外推數字要再除 1.4-1.7。`benchmarks/scripts/prepare_env.sh` 已有 nvpmodel+jetson_clocks 鎖定流程，上機日必跑。（https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/；https://docs.ultralytics.com/guides/nvidia-jetson/；CLAUDE.md「模型選型 Benchmark」節）
- **F23** **YOLO26 在 TRT 的精度風險訊號（社區，單一來源弱證據）**：Hackster 專案實測 YOLOv8 vs YOLO26 on Orin Nano（C++/TensorRT, JP6.x），報告「YOLOv26 exhibited bounding box drift and inaccurate confidence scores in C++」並回退 YOLOv8n 為預設——可能是自製 decode 的鍋，但與 F16 合起來支持「每顆 engine 上線前先過已知場景 sanity」。（https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267）

### D. GFLOPs / FPS / RAM 推算（標明假設）

- **F24**（計算）**解析度縮放 GFLOPs**（假設：FLOPs ∝ 輸入像素數，同模型）：n@960 = 5.4×2.25 = **12.2**；n@1280 = 5.4×4 = **21.6**；s@960 = 20.7×2.25 = **46.6**；s@1280 = 82.8（不考慮）。**n@1280（21.6）≈ s@640（20.7）的算力等值點**是本研究的支點。（基數出自 F1）
- **F25**（外推，標 ±）**Orin Nano（Super MAXN）純 TRT FP16 推理估算**——用兩個縮放模型夾出區間：(a) compute-linear（按 GFLOPs 線性外推 F14 的 4.57ms）為上界；(b) T4 比例（s/n = 2.5/1.7 = 1.47x，overhead 分攤）為下界，並用 F17（v8s 9.7ms ÷ 28.6 GFLOPs ≈ 0.34ms/GFLOP）交叉校驗：**s@640 ≈ 7-18ms；n@960 ≈ 9-11ms；n@1280 ≈ 14-18ms；s@960 ≈ 25-40ms**。全部仍 ≥25 FPS 理論值——**純推理不會是任何候選配置的瓶頸**。（假設：YOLO26 與 YOLOv8 的 per-GFLOP 效率同量級；Orin Nano 比 T4 更接近 compute-bound）
- **F26** **現役 6-8Hz 的真相**：`/perception/object/debug_image` 被 `publish_fps: 8.0` 硬性限流（`object_perception/config/object_perception.yaml` publish_fps 行；`object_perception/object_perception/object_perception_node.py:422-424` rate limit），tick 上限 15Hz（`tick_period: 0.067`），相機本身只有 15fps（F30）。CLAUDE.md 的「~6-8 Hz」是 debug topic hz，不是模型吞吐。node 每 tick 的成本大頭是 Python 端：letterbox+blob（:365-372）、HSV 12 色逐 bbox 分析（:401, :83-137）、PIL CJK overlay（:488-501）。→ **換大模型的 Hz 衝擊是「+10~35ms 推理」加在一個本來就 ~60-160ms 的 Python 迴圈上，次線性**。
- **F27**（估算，標假設）**RAM delta 預算表**（相對現役 n@640 已付的 CUDA context + ORT 基線；假設：FP16 權重 ≈ 2 bytes/param、activation/buffer ∝ 輸入像素 × 通道寬度、單顆 YOLO 級 TRT engine+execution context 全包 ~200-400MB——後者為**經驗值，無單一公開來源，上機 `tegrastats` 實測為準**。可引的最接近公開錨點是 Xavier NX 世代 NVIDIA 論壇案例：staff 載明 cuDNN/TRT 函式庫載入「at least 600 MB」、ORT+TRT EP 整 process 實測 ≥2GB、engine cache 可省 ~700MB——量級上支持「context/函式庫固定成本 >> 權重檔」，但該案例是整 process 口徑、Xavier 非 Orin、非 YOLO 模型，只能當量級錨不能當 delta；https://forums.developer.nvidia.com/t/high-ram-consumption-with-cuda-and-tensorrt-on-jetson-xavier-nx/183109）：**s@640 ≈ +100~250MB（PASS 預期）；n@960 ≈ +100~200MB（PASS 預期）；n@1280 ≈ +200~400MB（邊緣，需實測）；s@960 ≈ +300~600MB（最可能違反 0.8GB 紀律，需實測）**。引擎檔本體都很小（n FP16 engine 8.1MB，F14 表；s 估 ~20-30MB），不是問題。
- **F28** **真正的 RAM 風險是 build 階段**：ORT TensorRT EP `trt_max_workspace_size` 預設 **1073741824（1GB）**；engine rebuild 觸發條件 = 模型拓撲變更或輸入 shape 超出 cached profile。在 full demo stack 跑著的時候現燒 engine = workspace 峰值 + 統一記憶體 = OOM 風險。另有 `trt_timing_cache_enable` 可跨 build 重用 kernel timing 省 build 時間（現役 code 未開，列為 future option，本研究不改 code）。（https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html）
- **F29** **TRT build 時間**：現役已知 n@640 首次 build 3-10 分鐘（CLAUDE.md「物體辨識 pipeline」節；`docs/pawai-brain/perception/object/CLAUDE.md` 模型路徑節）。按模型大小/解析度放大估算（假設 build 時間隨 layer 數與 tactic 搜尋空間增長 1-2x）：**3 顆新 engine 上機日現燒 ≈ 30-60 分鐘**——必須前一晚預燒（矩陣 SOP，§5）。trt_cache 容量無虞（每顆 engine 10-40MB）。

### E. 相機 / 整合面（本地 code 查證）

- **F30** **現役 demo 相機只餵 640x480@15fps**：`scripts/start_full_demo_tmux.sh:144-145` = `depth_module.depth_profile:=640x480x15`、`rgb_camera.color_profile:=640x480x15`。→ **n@1280 在不動相機的前提下 = 把 640x480 插值放大 2x 餵模型，沒有任何新像素**。
- **F31** realsense-ros 切高解析的參數已確認：`rgb_camera.color_profile:=1280x720x30`（官方 README 範例原文）。D435 RGB 感光元件支援 1280x720（goal 文件 :44 亦載明）。（https://github.com/IntelRealSense/realsense-ros README）
- **F32**（計算，標假設）**cup 像素帳**（假設：cup 直徑 ~8cm、D435 RGB HFOV ≈69°、水平像素 = 解析度寬）：1.5m 處場景寬 = 2×1.5×tan(34.5°) ≈ 2.06m → cup 在 **640 寬 ≈ 25px、1280 寬 ≈ 50px**；2.0m 處 ≈ 19px / 37px。COCO 定義 small <32²、medium <96² → **640 capture 下 1.5m 的 cup 已落在 small 物件域（YOLO 最弱區），720p capture 直接抬進 medium 域**。這是「高解析路線」的理論依據，但前提是真像素（F30）。
- **F33** **node 已是解析度無關**：`letterbox()`（`object_perception_node.py:322-332`）與 `rescale_bbox()`（:337-343）全參數化；`input_size` 是 declared param（:160）。換 1280/960 模型 = 換 ONNX 檔 + 改 `input_size` 參數，**零 code 改動**。唯 fixed-shape 陷阱在案：餵錯 input_size 直接 inference fail（`docs/pawai-brain/perception/object/CLAUDE.md` 坑 #6，2026-05-23 踩過）。
- **F34** **A/B 基礎建設已就位（6/10 準備）**：launch 已有 `OBJECT_MODEL` / `OBJECT_INPUT_SIZE` env 一行切換，註解明列候選 `yolo26s_640.onnx@640 / yolo26n_960.onnx@960 / yolo26s_960.onnx@960`（`object_perception/launch/object_perception.launch.py:19-34`）；TRT cache 按 model stem 分子目錄避免互踩（`object_perception_node.py:271-274`，註解「2026-06-10 model A/B」）。**注意：repo 自己準備的高解析候選是 960，不是 goal 問的 1280**（見 §4 矛盾標注）。
- **F35** **conf threshold 現況 = 0.35 非 0.5**：launch default 0.35（`launch.py:39`，註解明載 0.5 默默蓋掉 yaml 的歷史教訓）；yaml 0.35（`object_perception/config/object_perception.yaml` confidence_threshold 行，註解「0.5→0.35: 召回率 +5-10%」）。goal 文件 :16 寫 `confidence_threshold=0.5` 是**過時 context**（b1f5058 已改）。且 `confidence_threshold` 不是 runtime param，改門檻必須重啟 node（`docs/pawai-brain/perception/object/CLAUDE.md` 坑 #9）。
- **F36** **class_whitelist 現役 = 家用 7 類含 cup(41)**（yaml `[39, 41, 45, 56, 63, 67, 73]`，2026-06-08 VIS-1）；runtime 可切（VIS-2 callback `object_perception_node.py:250-261`）。bench 矩陣量測時 whitelist 條件要固定，避免吃到 VIS-2 切換污染。
- **F37** **相機升 720p 的漣漪面**：(a) `face_identity_node` 與 `pawai face enroll` 共用同一 color topic（CLAUDE.md VIS-4 節）→ YuNet 前處理 CPU 變 2.25x 像素；(b) `/event/object_detected` 的 bbox 是原圖像素座標（`object_perception_node.py:395-398` rescale 到 orig_w/h）→ 任何下游假設 640x480 座標域的消費者（Studio overlay 縮放、bbox 面積閾值）要先 audit；(c) USB 頻寬與 RealSense node CPU 上升。→ 矩陣裡「需要動相機」的配置（C/D）排在「不動相機」的 B 之後。

### F. 三條路線交叉比較 + SAHI + 追蹤

- **F38** **推理 imgsz > 訓練 imgsz 的證據是混的**：官方立場「Best inference results are obtained at the same image size as the training was run at」（https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results ；discussion 14182 同義）；VisDrone 案例：train@1280 提升小物件 mAP，但同一使用者 inference imgsz 不匹配時反而漏掉容易的目標（https://github.com/ultralytics/ultralytics/issues/18849）。**n@1280（640-trained 權重直接 re-export）沒有官方增益數字**——這正是要上機量的原因，但證據強度上輸給 s@640。
- **F39**（推導）**每 GFLOP 換到的證據量排序**：① conf 0.35→0.3 + 時序確認 = **0 GFLOPs**（supervision §7a spike，BYTE 設計本來就用低信心框維持 track）；② s@640 = +15.3 GFLOPs 換官方 +7.7 mAP（含 STAL 家族級小物件增益）；③ n@1280 = +16.2 GFLOPs 換「無官方數字 + 需要動相機才有真像素」。→ 矩陣排序 control → s@640 → 高解析。（supervision 報告 §3.3 📍`tracker/byte_tracker/core.py:50-70`、§7a）
- **F40** **SAHI 官方指引沒有給任何精度/延遲數字**：只有範例參數 `slice_height/width=256`、`overlap_ratio=0.2`，無 AP 表、無 overhead 討論。（https://docs.ultralytics.com/guides/sahi-tiled-inference/）
- **F41** SAHI 論文數字：inference-only 切片對 FCOS/VFNet/TOOD **+6.8/5.1/5.3 AP**，加 fine-tuning 到 +12.7/13.4/14.5（VisDrone/xView 域）；延遲 ∝ 切片數（典型 4-15 片），後續研究指出 fixed-slice SAHI overhead 顯著（adaptive 版省 20-25% 才可用）。**換算 PawAI：4 片 + 全圖 ≈ 5x 推理 → node 從 6-8Hz 掉到 ~1.5-2Hz → runtime 直接出局**，只配離線/replay 用（supervision 報告 §3.9 InferenceSlicer 同結論）。（https://arxiv.org/abs/2202.06934；https://arxiv.org/html/2604.19233）
- **F42** **追蹤（>1m 物體追蹤）不在本 goal 解**：supervision 報告 §6 已排好 ByteTrack offline spike（WSL、一個下午、對 S3 錄影），與本矩陣的 recall 量測互補不重疊——本矩陣只量「各配置 cup@distance 單幀 recall + Hz + RAM」，時序確認的 FP 抑制歸 supervision spike 量。（`docs/perception/research/2026-06-11-supervision-pawai-fit-report.md` §6、§8）
- **F43** **S3 可接受 Hz 下限**：cup 是事件驅動（`class_cooldown_sec: 5.0`，yaml）、demo 流程是「拿出 cup → brain 講一句」（goal :8、6/9 錄影腳本）；首次偵測延遲 ≤1s 即可 → **偵測迴圈 ≥2Hz 已夠用，矩陣 pass 門檻取 ≥3Hz 留裕度**。相機 15fps（F30）才是事件新鮮度的真上限。
- **F44** **INT8 不是免費午餐**：官方表 YOLO26n INT8 在 Orin Nano Super 只比 FP16 快 17%（3.80 vs 4.57ms）但 mAP 掉 3.1 點（0.449 vs 0.480）——對「recall 不夠」的問題方向相反，本輪不考慮 INT8。（https://docs.ultralytics.com/guides/nvidia-jetson/）
- **F45** **官方 ONNX(ORT CPU/CUDA) 路徑 15.76ms vs TRT EP 4.57ms（3.4x）**——PawAI 走 ORT+TRT EP 介於兩者之間（TRT engine + ORT session 開銷）。bench 矩陣量到的「node 內推理 ms」預期落在 6-20ms 區間（n@640），若量出 >30ms 先懷疑 TRT EP fallback 到 CUDA/CPU provider（已知坑：provider 參數值必須 `"True"` 字串，`docs/pawai-brain/perception/object/CLAUDE.md` 坑 #1）。（https://docs.ultralytics.com/guides/nvidia-jetson/）

---

## §2 Q1-Q10 逐題回答

### Q1：YOLO26s 的 params/GFLOPs/mAP？相對 n 的 mAP-small 增益？

**9.5M params / 20.7 GFLOPs / mAP50-95 48.6（e2e 口徑 47.8）**，對 n（2.4M/5.4/40.9）整體 **+7.7 mAP**（F1, F2；https://docs.ultralytics.com/models/yolo26/）。
**官方表沒有拆出 AP-small**；可引的最接近證據：(a) STAL/ProgLoss 是家族級小物件機制（F7），n/s 都有，不構成差異；(b) COCO 慣例上 AP-small 隨模型容量的增幅 ≥ 整體 mAP 增幅（小物件是 nano 級模型最弱項）——此句為**推論非引用**，正是矩陣要量的東西。誠實結論：**+7.7 整體 mAP 是硬數字，cup@1.5m recall 的實際增益必須上機量**。

### Q2：YOLO26 有沒有官方 `-seg`？輸出格式？TRT FP16 已知精度問題？

**有**，n-x 全尺度（F3）。數字：n-seg 2.7M/9.1/box 39.6/mask 33.9；s-seg 10.4M/34.2/box 47.3/mask 40.0（F4；https://docs.ultralytics.com/tasks/segment/）。
輸出 = 偵測 tensor + proto tensor（輸入 1/4 解析度，640→160×160；F12；https://github.com/ultralytics/ultralytics/issues/23820），mask 合成是 CPU 後處理；**seg export 是否 e2e NMS-free 官方未明文**（F13）。
TRT FP16 精度問題：seg 專屬的沒查到；但偵測版有兩個訊號——官方 AGX Orin 表 TRT FP32/FP16 行 mAP 0.045 異常（F16）與 Hackster 的 C++ TRT bbox drift 報告（F23，弱證據）→ **不管選哪個配置，engine 燒完必過 sanity check**。
**本矩陣裁定 seg 出局**：box mAP 更低 + GFLOPs +65% + CPU mask 後處理 + 輸出契約不明（F5, F12, F13）。輪廓/mask 對顏色辨識的價值留給 goal 3（mask 內做 HSV 確實比 bbox 內乾淨——bbox 含背景像素是現役 `analyze_bbox_color` 的已知噪音源，`object_perception_node.py:83-137`——但那是顏色線的 ROI 問題，不是 cup recall 問題）。

### Q3：imgsz=1280 後輸出仍 `(1,300,6)`？300 夠不夠？可調嗎？

**仍是 `(1,300,6)`**——300 = `max_det`，與 imgsz 無關（F9；https://docs.ultralytics.com/modes/export/）。**可調**：`model.export(format="onnx", max_det=500)`，但超過 300 的偵測品質官方警告會降（checkpoint 以 max_det=300 訓練；F10）。**居家場景 + 7 類 whitelist（F36）下 300 上限綽綽有餘**，不需要動。高解析下唯一變化是 bbox 座標域 → 現役 `rescale_bbox` 已參數化處理（F33）。

### Q4：Orin Nano 8GB 上 s 級 TRT FP16 社區實測？

兩個獨立來源 + 一個比例驗證（皆 **YOLOv8 世代**，28.6 GFLOPs，比 YOLO26s 重 38%——外推時 YOLO26s 應同等或更快）：
1. **103 qps（≈9.7ms）**，TensorRT C++，Orin Nano 8GB（F17；https://forums.developer.nvidia.com/t/jetson-orin-nano-fp16-int8-performance/326723）
2. **≈26 FPS 端到端**（1558 inf/min, 7.836W），Ultralytics pipeline，Orin Nano（F18；https://arxiv.org/abs/2502.15737；功耗模式未載明，標不確定）
3. 比例驗證：AGX Orin 260 FPS ÷ 2.5-3x ≈ 87-104 FPS，吻合 #1（F19；https://www.stereolabs.com/blog/performance-of-yolo-v5-v7-and-v8）
**外推（假設標明）**：YOLO26s@640 TRT FP16 純推理在 Orin Nano（Super MAXN）≈ **7-18ms**（F25）；**node 實際 Hz 由 Python 開銷主導**（F20, F21, F26），預估 5-7Hz。

### Q5：n@1280 與 s@640 的 GFLOPs？哪個 AP-small 證據強？

**n@1280 = 21.6、s@640 = 20.7——算力等值**（F24）。證據強度**一面倒向 s@640**：官方 trained-at-640 表格給 +7.7 mAP（F2）；n@1280 是「640-trained 權重推理時放大」，官方零數字、社區證據混雜（官方建議推理尺寸=訓練尺寸；VisDrone 個案漲跌互見；F38），且**現役相機 640x480 讓 n@1280 退化成插值放大**（F30）。n@高解析仍值得保一格在矩陣（小物件相對 stride 網格變大的機制是真的——SAHI 的增益就是這個機制，F41），但要配 720p 相機才測得有意義（F31, F32），並建議用 **n@960**（repo 6/10 已內定的候選名，F34）取代 1280：GFLOPs 12.2 vs 21.6，Hz/RAM 風險減半，720p 下 cup@1.5m 已進 medium 域（F32）。

### Q6：四個候選配置 RAM 估算？哪些違反 0.8GB 紀律？

（F27 估算，假設見該條；全部需上機 `tegrastats` 實測確認）

| 配置 | 權重 FP16 | activation/buffer 倍率 | 預估 delta vs 現役 | 0.8GB 紀律 |
|------|----------|----------------------|-------------------|-----------|
| n@640（現役） | 4.8MB | 1x | 0（基線） | PASS（現況成立） |
| s@640 | ~19MB | ~1-2x（通道變寬） | **+100~250MB** | PASS 預期 |
| n@960 | 4.8MB | 2.25x（像素） | **+100~200MB** | PASS 預期 |
| n@1280 | 4.8MB | 4x | +200~400MB | 邊緣，需實測 |
| s@960 | ~19MB | ~3-4x 複合 | **+300~600MB** | **最可能 FAIL，必實測** |
| s-seg@640 | ~21MB | ~1.7x + proto 輸出 + CPU mask | +150~300MB | （已因 Q2 出局） |

**直接違反**：紙面上沒有一個「確定」違反，但 s@960 在 full demo stack（語音+人臉+手勢姿勢同跑）下最接近紅線。**比穩態 RAM 更危險的是現燒 engine 的 1GB workspace 峰值（F28）**——SOP：前一晚單獨預燒（§5）。

### Q7：D435 要不要改 1280x720？letterbox/座標改動量？

**分配置**：s@640 **不用動相機**（這是它排第一的理由之一）；n@960/s@960（或任何高解析模型）**必須動**，否則是插值自欺（F30, F32）。改法一行：`rgb_camera.color_profile:=1280x720x30`（F31），改 `scripts/start_full_demo_tmux.sh:145`（bench 時可先只在獨立 launch 改）。
**程式面零改動**：`letterbox`/`rescale_bbox`/`input_size` 全參數化（F33），`(1,300,6)` parse 不變（F9）。
**漣漪要 audit**（F37）：face pipeline 共用 topic 的 CPU 漲幅、下游 bbox 座標域假設、USB 頻寬。建議 bench 日 C/D 配置量測時同跑 face node 看 CPU 變化。

### Q8：conf 0.3 + 時序確認路線 vs 換模型路線的成本效益？

**成本 = 0 GFLOPs、0 RAM、0 build 時間**——成本效益無敵，但**天花板有限**：它只能把「模型偶爾看得到的弱偵測」變穩定（supervision 報告 §7a 原話：「只能在『模型偶爾看得到』的前提下把偶爾變穩定」），對「根本沒看到」無效。BYTE 的機制是低信心框維持既有 track（📍supervision clone `tracker/byte_tracker/core.py:50-70`，`minimum_consecutive_frames` 防假 track）。文獻上低 threshold + 時序關聯是 BYTE 對 MOT 的核心貢獻，但**沒有「cup@1.5m recall」這種單類距離 recall 的現成數字**——所以矩陣把它列為 **A1 零成本 control arm**（同場量、與 supervision spike 分工：本矩陣量 recall@distance，supervision spike 量 FP 抑制與 track 穩定，F42）。若 A1 就讓 cup@1.5m 達標，B/C/D 全省。注意 conf 改動需重啟 node（F35 坑 #9）。

### Q9：SAHI 延遲倍率？6-8Hz 基線下 tiling 是否出局？

官方指引**零數字**（F40）。論文/社區：精度 +6.8~14.5 AP（小物件域資料集），**延遲 ∝ 切片數（4-15 片）**（F41）。PawAI 換算：最便宜的 4 片 + 全圖 ≈ 5x 推理成本 → 1.5-2Hz——**runtime 直接出局**（連 ≥3Hz 門檻都過不了，何況它還要疊 Python NMS 合併）。合法用途：WSL 離線對 S3 錄影 replay 量「tiling 能撈回多少遠距 cup」當 upper-bound 參考（supervision 報告 §3.9 InferenceSlicer 同結論，NEEDS_BENCHMARK 維持）。

### Q10：上機矩陣排哪 ≤4 個配置？pass/fail 門檻？

見 §5 verdict 表。摘要：**A（n@640 基線 + conf0.3 control）→ B（s@640）→ C（n@960 + 720p 相機）→ D（s@960 + 720p 相機）**；seg 出局（Q2）、SAHI 出局（Q9）、1280 由 960 取代（Q5）。門檻：**cup@1.5m 靜置 30s recall ≥80%（2.0m ≥50% 為 stretch）、node 偵測迴圈 ≥3Hz、full-stack RAM 餘量 ≥0.8GB、近距 7 類 sanity 不退化**。
**recall 門檻推導（80/50 不是任意取整）**：S3 的功能需求是「拿出 cup 後 ≤1s 觸發一次事件」（F43：事件驅動 + `class_cooldown_sec: 5.0`，只需第一次偵測成功即觸發）。偵測迴圈 ≥3Hz 下，1s 內有 ~3 次獨立判定機會，事件觸發機率 = 1−(1−p)³（p = 單幀 recall）：**p=0.80 → 99.2%**（1s 內觸發，demo 等級穩定，這是 1.5m pass 線的依據）；**p=0.50 → 87.5%（1s 內）/ 98.4%（2s 內）**——50% 定為 2.0m stretch 線，代價是接受最壞 ~2s 的觸發延遲（仍在 F43 的「≤1s 首偵測即可」的寬鬆面內，故只列 stretch 不列 pass）。30s 靜置窗是**量測窗口而非觸發需求**：@3Hz ≈ 90 幀樣本，讓單點 recall 估計的統計噪音可控。

---

## §3 三條路線交叉比較總表（Required investigation 核心）

| 路線 | 成本（GFLOPs/RAM/動相機/build） | 增益證據等級 | 裁定 |
|------|------|------|------|
| ① conf 0.3 + 時序確認 | 0 / 0 / 否 / 0 | 機制證據強（BYTE 設計）、無距離-recall 直接數字 | **A1 control arm，先量** |
| ② 模型放大 n→s @640 | +15.3 / +100-250MB / 否 / ~10min | **官方 +7.7 mAP（最強）** | **B，主力刀** |
| ③ 輸入放大 @960/1280 | +6.8~+16.2 / +100-400MB / **是** / ~10-20min | 機制合理、官方零數字、社區混雜 | **C 次位；D（s@960）壓軸看 RAM** |
| ④ seg 變體 | +13.5 / +150-300MB / 否 / ~15min | box mAP 反而 -1.3 | **出局（goal 3 再議 mask×顏色）** |
| ⑤ SAHI tiling | ×5 推理 | AP 證據強但全是離線域 | **runtime 出局，離線 replay 工具** |

---

## §4 與 cross-validate 文件的矛盾標注（按 spec 要求明說）

1. **修正 PINTO 報告 §5a**（`docs/perception/research/2026-06-11-pinto-model-zoo-pawai-fit-report.md:130-135`）：該報告裁定「正確的第一刀 = YOLO26n re-export `imgsz=1280`」。本研究以三點推翻其優先序：(a) n@1280 與 s@640 GFLOPs 等值（F24）但證據強度懸殊（F2 vs F38）；(b) 現役相機 640x480 使 n@1280 退化為插值（F30）——PINTO 報告未考慮相機輸入端；(c) repo 自己 6/10 的 launch 候選清單已內定 960 而非 1280（F34），1280 從未是 repo 共識。**「不用換 zoo 模型、incumbent 路線內解決」的大方向兩報告一致**，只是第一刀從「n 升解析」改為「升 s」。
2. **與 supervision 報告 §7a/§6 的分工——互補，但其 conf 基線已過時，必須標明**（`docs/perception/research/2026-06-11-supervision-pawai-fit-report.md:143,152-156`）：分工面互補無重疊——為避免兩線重複量同一件事（goal :74 的明確要求）：**本矩陣量「配置 × 距離 × recall/Hz/RAM」（on-device）**，supervision spike 量「threshold+ByteTrack 的 FP 抑制與 track 連續性」（offline/WSL 對錄影）。**矛盾點**：supervision §7a（:154）寫「現行 `confidence_threshold=0.5` 📍`object_perception_node.py:159`」、§6 spike 協議（:143）也以「threshold 0.5 vs 0.3」設計量測——這個 0.5 基線**已被 b1f5058 過時化**（與 §4.3 的 goal :16 是同一筆過時 context）：node `:159` 的 declared default 確實仍是 0.5，但 effective conf 是 **0.35**（launch `:39` 後置 override + yaml 同值，F35）。**連帶配對缺口**：兩線 control 基線因此不一致（supervision spike：0.5 vs 0.3；本矩陣：A0=0.35 vs A1=0.30），「A1 上機數據直接餵 supervision spike 當 ground truth 配對」**在基線對齊前不成立**。對齊二選一：(a) supervision spike 的 baseline 同步改 0.35（**建議**——0.5 已非現役配置，重量它沒有 demo 意義）；或 (b) 本矩陣 A 加量一組 conf=0.5 arm（僅在要保留與 supervision 報告既有數字可比性時才做）。
3. **goal 文件 context 過時一處**：goal :16 寫 `confidence_threshold=0.5`，現役 launch/yaml 均為 **0.35**（F35；b1f5058 已修，`docs/pawai-brain/perception/object/CLAUDE.md` 坑 #9 在案）。本報告所有「基線」均以 0.35 為準。
4. **goal 候選清單 vs repo 既定候選**：goal :8 問「n@1280？s@640？s@960？seg？」；repo launch 註解（F34）既定候選為 `s_640 / n_960 / s_960`——本研究裁定跟隨 repo 的 960 系（理由見 Q5），1280 不進矩陣。
5. **`docs/pawai-brain/perception/object/CLAUDE.md` 陷阱清單**：全部仍有效且被本矩陣 SOP 引用（ultralytics 禁裝 Jetson → WSL export；TRT 參數字串；fixed-shape input_size；conf 非 runtime param）。無矛盾。
6. **CLAUDE.md「debug_image ~6-8 Hz」表述的精確化**：該數字含 `publish_fps: 8` 限流上限（F26），不應被讀成「模型只能跑 6-8Hz」——本報告據此判斷模型放大的 Hz 衝擊為次線性，與 CLAUDE.md 字面印象不同但與 code 一致。

---

## §5 Verdict：**GO_BENCH_MATRIX**

證據足以排序配置（官方家族規格 + 官方 Jetson n 錨點 + 兩個獨立 s 級社區錨點 + export 行為全確認 + node/launch 基礎建設已就位），不需要先做 WSL replay 才能排矩陣（replay 降級為可選前置，見下）。

### 上機測試矩陣（≤4 配置）

| # | 配置 | WSL 前置 | 預估純推理* | 預估 node Hz | 預估 RAM delta | pass 門檻（全配置同） |
|---|------|---------|------------|-------------|----------------|----------------------|
| **A** | n@640 基線 re-measure + **conf 0.3 control**（A0=0.35 / A1=0.30） | 無（現役模型） | 5-16ms | 6-8Hz | 0 | 記錄 cup recall @1.0/1.5/2.0m 各 30s 基線；A1 對 A0 的 recall 增益 |
| **B** | **s@640**（`yolo26s_640.onnx`，相機不動） | export s.pt imgsz=640 | 7-18ms | 5-7Hz | +100~250MB | ①cup@1.5m recall ≥80%（@2.0m ≥50% stretch）②偵測迴圈 ≥3Hz ③full-stack RAM 餘 ≥0.8GB ④近距 7 類 sanity 不退化 |
| **C** | **n@960 + 相機 1280x720x30**（`yolo26n_960.onnx`） | export n.pt imgsz=960 | 9-11ms | 4-6Hz | +100~200MB | 同上 + face node CPU 漲幅記錄 |
| **D** | **s@960 + 相機 1280x720x30**（`yolo26s_960.onnx`，RAM 最危） | export s.pt imgsz=960 | 25-40ms | 3-5Hz | +300~600MB | 同上；RAM 先量再跑（違反 0.8GB 即棄測） |

\* Orin Nano **Super MAXN** 假設（F22）；若 nvpmodel 非 Super 檔，全表 ÷1.4-1.7。估算方法與假設見 F25/F27。
pass 門檻中 recall 80%/50% 的推導見 Q10（由 1−(1−p)³ 事件觸發機率對 S3「≤1s 觸發」需求反推，非任意取整）。
出局項：seg（Q2）、SAHI runtime（Q9）、INT8（F44）、n@1280（Q5，由 C 取代）。

### WSL 前置動作清單（上機日前完成）

1. WSL 獨立 venv：`uv venv && uv pip install ultralytics onnxruntime`（**禁令只限 Jetson**，`docs/pawai-brain/perception/object/CLAUDE.md` 不能做 #1）。
2. Export 3 顆 ONNX（fixed shape、預設 e2e）：`yolo export model=yolo26s.pt format=onnx imgsz=640`、`model=yolo26n.pt imgsz=960`、`model=yolo26s.pt imgsz=960`；檔名按 launch 註解慣例 `yolo26s_640.onnx / yolo26n_960.onnx / yolo26s_960.onnx`（F34）。
3. WSL 用 onnxruntime CPU 對 6/9 S3 錄影抽幀做 sanity：確認輸出 shape `(1,300,6)`、cup 在近距幀有偵測、座標域正確（F16/F23 的 engine 風險防線第一層）。**可選加碼**：對整段 S3 錄影離線跑 4 配置 recall 對照，預先排序（即原 NEEDS_TEST_WSL_REPLAY 的內容，降級為加分項）。
4. `rsync` 3 顆 ONNX 到 `/home/jetson/models/`（走 audited deploy 路徑）。
5. **前一晚預燒 engine**：Jetson 上不開 full demo，逐一 `OBJECT_MODEL=... OBJECT_INPUT_SIZE=... ros2 launch object_perception object_perception.launch.py` 讓 TRT cache 各自落到 `trt_cache/<stem>/`（F28/F29；每顆 3-15min，總計 ~30-45min）。燒完跑一次近距 cup sanity。
6. 上機日開場：`sudo bash benchmarks/scripts/prepare_env.sh` 鎖定 nvpmodel/jetson_clocks 並**記錄當前 power mode**（F22）。

### 量測腳本面（不改 runtime code）

- recall@distance：沿用 `capture_baseline_round.py percep` 流程，記得隔離 gesture topic（CLAUDE.md 6/4 坑：`--gesture-topic /__no_gesture__`）。
- Hz：node debug overlay 的 FPS 字串（`object_perception_node.py:520`）+ `ros2 topic hz`；RAM：`tegrastats` 前後對照。

### 對應 verdict 的下一步（一個，具體）

**把上面「WSL 前置動作清單」立為一張 ready-for-agent issue（標題建議：`bench: YOLO26 scale-up matrix WSL prep — export s640/n960/s960 + S3 replay sanity`），本週在 WSL 完成 1-5 項，模型與 TRT cache 預燒就緒後，下次上機日按矩陣 A→B→C→D 執行，每配置 30 分鐘、含 gate 判定。** A1（conf 0.3 control）若直接讓 cup@1.5m 達標，B/C/D 順延為驗證性質而非救火。

---

## 附錄：來源清單

**官方文件**：
- https://docs.ultralytics.com/models/yolo26/ （家族規格、task 變體、STAL/ProgLoss、e2e 輸出）
- https://docs.ultralytics.com/guides/nvidia-jetson/ （Orin Nano Super YOLO26n 全格式 benchmark、AGX 異常行、MAXN/jetson_clocks）
- https://docs.ultralytics.com/modes/export/ （imgsz/dynamic/nms/batch、(1,300,6) 與 max_det 關係）
- https://docs.ultralytics.com/guides/end2end-detection （max_det export 可調、>300 品質警告、雙 head shape）
- https://docs.ultralytics.com/tasks/segment/ （YOLO26n/s-seg 規格）
- https://docs.ultralytics.com/guides/sahi-tiled-inference/ （SAHI 指引，無數字）
- https://docs.ultralytics.com/yolov5/tutorials/tips_for_best_training_results （推理尺寸=訓練尺寸建議）
- https://onnxruntime.ai/docs/execution-providers/TensorRT-ExecutionProvider.html （workspace 1GB、rebuild 條件、timing cache）
- https://github.com/IntelRealSense/realsense-ros （rgb_camera.color_profile）

**論文 / issue / 社區**：
- https://arxiv.org/abs/2509.25164 （YOLO26 paper：STAL/ProgLoss/MuSGD）
- https://arxiv.org/abs/2502.15737 （Orin Nano/NX YOLOv8n/s 邊緣實測，端到端口徑）
- https://arxiv.org/abs/2202.06934 （SAHI 原始論文 AP 數字）
- https://arxiv.org/html/2604.19233 （adaptive slicing：fixed SAHI overhead）
- https://forums.developer.nvidia.com/t/jetson-orin-nano-fp16-int8-performance/326723 （YOLOv8s TRT FP16 103qps）
- https://forums.developer.nvidia.com/t/slow-fps-on-orin-nano-8-gb-yolov8/280071 （Python pipeline 10FPS vs trtexec 12ms）
- https://github.com/ultralytics/ultralytics/issues/22479 （官方 vs 實測 3.5x 差距）
- https://github.com/ultralytics/ultralytics/issues/18849 （VisDrone imgsz 1280 漲跌互見）
- https://github.com/ultralytics/ultralytics/issues/23820 （seg proto = 輸入 1/4）
- https://www.stereolabs.com/blog/performance-of-yolo-v5-v7-and-v8 （AGX Orin v8s 260FPS）
- https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267 （YOLO26 C++ TRT drift 報告，弱證據）
- https://developer.nvidia.com/blog/nvidia-jetson-orin-nano-developer-kit-gets-a-super-boost/ （Super 韌體升級 1.7x）
- https://developer.nvidia.com/embedded/jetson-modules （AGX Orin 32GB 200 TOPS/1792 cores vs Orin Nano 67 TOPS/1024 cores，F19 比例口徑）
- https://www.nvidia.com/content/dam/en-zz/Solutions/gtcf21/jetson-orin/nvidia-jetson-agx-orin-technical-brief.pdf （AGX Orin 系列規格 technical brief）
- https://forums.developer.nvidia.com/t/high-ram-consumption-with-cuda-and-tensorrt-on-jetson-xavier-nx/183109 （cuDNN/TRT 函式庫 ≥600MB、ORT+TRT EP process ≥2GB，F27 RAM 量級錨，Xavier 世代）

**本地 code / 文件**：
- `object_perception/object_perception/object_perception_node.py`（:83-137 HSV、:156-175 params、:266-303 ONNX init + cache per stem、:322-343 letterbox/rescale、:352-424 tick、:384 raw parse、:520 FPS overlay）
- `object_perception/launch/object_perception.launch.py`（:19-39 OBJECT_MODEL/OBJECT_INPUT_SIZE/conf 0.35）
- `object_perception/config/object_perception.yaml`（conf 0.35、input_size 640、publish_fps 8、whitelist 7 類、cooldown 5s）
- `scripts/start_full_demo_tmux.sh`（:144-145 相機 640x480x15）
- `docs/pawai-brain/perception/object/CLAUDE.md`（陷阱 #1/#6/#9 等）
- `docs/perception/research/2026-06-11-pinto-model-zoo-pawai-fit-report.md`（§5a，本研究修正其第一刀排序）
- `docs/perception/research/2026-06-11-supervision-pawai-fit-report.md`（§3.3/§6/§7a，分工對接）
