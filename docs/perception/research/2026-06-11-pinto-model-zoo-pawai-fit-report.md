# PINTO_model_zoo 對 PawAI 的可用性研究報告

> **日期**：2026-06-11
> **Verdict**：**ADOPT_AS_CANDIDATE_SOURCE**（按能力線分層進候選池；3 個 BENCHMARK_CANDIDATE、9 個附觸發條件的 MAYBE；任何模型上線前仍走 benchmark 制度）
> **研究方法**：ultracode workflow——第一輪 6 路平行盤點（object/face/pose/gesture/other/repo 機制）+ 14 個候選深查（預設懷疑視角）+ 完整性批判者；批判者抓出缺口後第二輪補查 4 個（478_SC / 475_VSDLM / 477_PGC / 451_DAN 表情家族）；481_WHC / 431_NITEC 由主線直接對本地 clone 補證。共 25 個 subagents、~400 次工具呼叫。
> **本地 clone**：`/home/roy422/newLife/PINTO_model_zoo`（commit `1ed3508`，2026-06-07，depth-1）
> **本研究為 read-only**：未改 code、未 commit、未在任何機器安裝模型。

---

## TL;DR

PINTO_model_zoo 是 **483 個模型目錄的「轉檔動物園」**（單人 hobby 專案，作者 Katsuya Hyodo，活躍維護中）——不是 library、不是 runtime，是「上游模型 → ONNX/TFLite/OpenVINO 多格式轉檔 + 自家 S3 hosting」的集散地。對 PawAI 的正確用法是**候選池來源**，不是立刻換模型（scoreboard-first）。

三個重點結論：

1. **「三百個模型都量化過」不成立**——實際 483 個目錄；抽樣查證 INT8 覆蓋約 57%（母體下限約 30%）、FP16 約 77%、純 ONNX FP32 至少 23%，而且**對 PawAI 最有價值的 2025-2026 新目錄（47x-48x）恰好是 ONNX-only 重災區**。但實害小：PawAI 主線本來就是 ONNX → TensorRT EP FP16（build-time 轉換），TFLite INT8 只走 CPU。
2. **真正的寶不在「換掉現任」而在「補缺口」**：三個 BENCHMARK_CANDIDATE 裡兩個是 face recognition 挑戰者（LVFace、AdaFace），一個是 115KB 的坐姿分類器（478_SC）——它對接的是 scoreboard 上**唯一明確不及格**的能力（greet gate 的 sitting 判定）。
3. **cup 0.7m 在這個 zoo 裡沒有答案**：所有 COCO 域候選（132_YOLOX 高解析、334_DAMO-YOLO）都被深查否決，因為「YOLO26n 在 WSL re-export `imgsz=1280`」幾分鐘就能複製它們唯一的賣點，模型還更新更準。

---

## 1. PINTO_model_zoo 是什麼 / 不是什麼

**是什麼**：

- 483 個編號模型目錄（001-488，缺 6 個號）+ `999_media`；每目錄 = `download*.sh` + `LICENSE` + `README` +（46% 有）`demo/`。模型本體不進 git（repo 僅 363MB），從作者自費的 **Wasabi S3** 拉 `resources.tar.gz`（801 個 URL 實測 HEAD 200 存活）。
- 格式光譜：ONNX / TFLite(Float32/FP16/INT8/EdgeTPU) / OpenVINO / CoreML / TFJS / TF-TRT / saved_model——但**覆蓋率因年代而異**（見 §2）。
- **活躍**：近 12 個月約 115 commits、新增約 20 目錄（469-488），最後 commit 2026-06-07。2025-11 有一波作者自製超輕量分類器高峰（475-481），2026-04 起有 LVFace/TransFace/DEIMv2-Wholebody 新貨。
- 兩類內容物：(a) 上游模型的轉檔 snapshot（如 144_YuNet、290_AdaFace）；(b) **PINTO 自訓自標模型**（Wholebody 系列、475-481 分類器家族）——後者上游就是 zoo 本身。
- `post_process_gen_tools`（21 個目錄）：把 NMS 燒進 ONNX 的產生器，輸出 `[N,7]` 單檔模型——與 PawAI YOLO26n 的 NMS-free `(1,300,6)` 同哲學。

**不是什麼**：

- **不是 library / runtime**：拿到的是模型檔，前後處理要自己寫（README 自承「skipped the work of making sample code」；demo 覆蓋 222/483）。
- **不全有量化**（§2）。
- **不是維護保證**：轉檔是 snapshot，上游死了 zoo 不會救（YOLOX 上游休眠、DAMO-YOLO 棄置、DTLN 休眠 4 年）。
- **不是單一授權**：root MIT 只管轉換腳本；401/483 目錄帶上游 LICENSE，抽查見 **GPL-3.0（307_YOLOv7）/ AGPL-3.0（298）/ CC BY-NC-SA 禁商用（062）/ 82 個無 LICENSE**——逐目錄查是硬規矩。
- **基礎設施有單點故障**：單一 Wasabi bucket、作者個人付費、無 checksum 無版本鎖；22 個最舊目錄的 Google Drive 路徑已 404。**選定的模型應自行鏡像備份**。

---

## 2. 「三百個模型都有量化過」查證

| 口徑 | 數字 | 方法 |
|------|------|------|
| 模型目錄總數 | **483**（非 300；488 是最大編號） | `ls -d [0-9]*_*` 排除 999_media |
| 抽樣 30 目錄：有 TFLite INT8 | **~57%** | 含 18 個 tarball 實際 `tar -tzf` 開箱 |
| 抽樣 30 目錄：有任何 FP16 變體 | **~77%** | 同上 |
| 抽樣 30 目錄：純 ONNX FP32 | **≥23%** | 304/324/477/486 tarball 全列表確認 |
| convert_script 普查（221 目錄有此檔） | int8 ~147-153（**母體下限 ~30%**）、fp16 ~200-208 | grep；critic 複核量級一致 |

**判定：宣稱不成立**，但 critic 給了一個公平的 nuance：2022 年前後 zoo 約 300 目錄時代（openvino2tensorflow/onnx2tf 全套產出期）「幾乎全有量化」大致為真——**使用者的記憶可能停在那個年代**。新的 47x-48x 系列（正是對 PawAI 最有價值的）多為 ONNX-only。

**對 PawAI 的實害評估：小。** TFLite INT8 = CPU 路徑（PawAI CPU 已被 face/pose/gesture 吃滿，價值有限）；ONNX-only 目錄照樣走 onnxruntime-gpu 1.23.0 + TensorRT EP 的 `trt_fp16_enable`（與 YOLO26n 同款主線）。另注意專案已知坑：Jetson CUDA int8 限制是 CTranslate2 的事，TRT 的 INT8 需自備 calibration、且本 zoo 至少一例校準公式錯誤（117_DTLN 把影像的 `data/255` 套在音訊上，INT8 變體幾乎肯定壞掉）。

---

## 3. 五能力盤點結果總表

| 能力 | 現任 | zoo 裡有沒有貨 | 結論 |
|------|------|------|------|
| **object (cup 遠距)** | YOLO26n TRT FP16 | COCO 域候選全被否決 | **此 zoo 無解**；正解是 incumbent re-export `imgsz=1280` + SAHI（見 §5a） |
| **face 偵測** | YuNet 71.3 FPS CPU | 387_YuNetV2（640x640 直系升級）| 現任達標；YuNetV2 留作遠距小臉對照組 |
| **face 辨識** | SFace | **483_LVFace、290_AdaFace 兩個 BENCHMARK_CANDIDATE** | 此 zoo 最強供給線 |
| **pose / sitting** | MediaPipe Pose | **478_SC（BENCHMARK_CANDIDATE）**、137_MoveNet_MultiPose（MAYBE） | SC 直擊 greet gate 痛點 |
| **gesture** | MediaPipe Gesture Recognizer | 477_PGC、427_RTMPose_Hand、481_WHC（皆條件式） | 先做零成本實驗再說（§5b） |
| **speech** | SenseVoice/LLM/TTS | 有 audio 模型（YAMNet/DTLN/Whisper/SER）但 **無 VAD/KWS** | **VAD 瓶頸此 zoo 幫不上**；音訊域正解是 Silero VAD（不在 zoo 裡） |
| **guardian/nav（future）** | — | 472_DEIMv2-Wholebody34、429_OSNet、439_Depth-Anything、097_YAMNet、431_NITEC | 全掛觸發條件，等能力線立項 |

---

## 4. 深查結果明細

### 4.1 BENCHMARK_CANDIDATE（3 個）

**`483_LVFace`（face recognition 挑戰者，首選）**
- ByteDance，ICCV 2025 Highlight；LVFace-T 76.7MB FP32 ONNX、112x112、ArcFace 標準對齊（YuNet 5 landmarks 直接可餵，近 drop-in）。
- 直接對應兩個已命名痛點：6/8 HITL enrollment 漂移（sim 0.2→re-enroll 0.73-0.81）與 guardian 陌生人 low-FAR（IJB-C TAR@FAR=1e-6 88.53%）。
- ⚠️ **權重 non-commercial research only**（code MIT 但上游明文限制）——學術專題 OK、商用路線死，候選池必掛旗。
- ⚠️ 別跑 `download.sh`（1.7GB tarball 九成是用不到的 DEIMv2 偵測器），HF 直拉 T 檔。
- 觸發條件：face recognition 能力分數在「fresh-enrollment + 距離/模糊 sweep」協議下不及格。

**`290_AdaFace`（低品質臉專家，license 較乾淨的備選）**
- CVPR 2022、**MIT**；quality-adaptive margin 在 TinyFace/IJB-S（低品質集）SOTA——正中「機器狗運動模糊 + 中遠距小臉」這個 SFace 沒有機制應對的缺口。
- ir18/ir50/ir101 速度階梯；ONNX 靜態 112x112 opset 11 與 TRT EP 零摩擦。
- ⚠️ zoo tarball 是 **21.3GB all-in-one**——不要碰，直接從上游 repo 匯出 ir18 單檔；上游已遷移 CVLface，換之前先看一眼有無更新權重。
- 誠實註記：6/8 的 sim 崩跌一半是 face_db 衛生問題（SOP 已修），換模型不是萬靈丹；SFace 過 gate 就不動。

**`478_SC`（坐姿分類器——本研究最高 ROI 發現）**
- PINTO 2025-11 自製；**MIT、115KB-875KB、輸入 32x24 整身 crop、x86 CPU 0.124ms/次**（Jetson 估 <1.5ms），不碰 GPU、RAM 忽略不計。
- **對接 scoreboard 上唯一明確不及格的能力**：VIS-4 greet gate 硬依賴 pose=sitting，MediaPipe 判定不穩到文件建議直接關 gate。SC 是外觀式分類，與 landmark 幾何規則**正交**——建議 ensemble（雙確認或 OR + `bbalg` 遲滯平滑），把 3s sitting window 命中率拉起來。
- 前級免費：YOLO26n person bbox（class 0）或 MediaPipe landmarks 推 bbox。
- ⚠️ 訓練域是 AVA 電影片段，Go2 仰角 + 沙發 + 桌面遮擋是 out-of-domain——上線前必錄 Go2 視角 sitting/standing clips 實測（沿用 `capture_baseline_round.py` 流程）。
- 順帶依賴：`uv pip install bbalg`（純 Python、MIT，雙窗投票平滑）。

### 4.2 MAYBE（附明確觸發條件，按觸發可能性排序）

| 目錄 | 是什麼 | 觸發條件 | 關鍵風險 |
|------|------|------|------|
| `481_WHC`* | 揮手時序分類器（3DConv、4-8 幀 32x32 crop 序列、F1 0.98-0.99、CPU 0.3-0.5ms、MIT、GitHub releases 單檔直下） | wave 互動回到 demo 主線（3/23 被移除；WaveDetector footgun 文件在案） | 需 hand bbox 序列 + crop 追蹤 |
| `477_PGC` | 「指向鏡頭 yes/no」二元分類（MIT、<1MB、CPU 數 ms） | ① gesture 誤觸 fail gate ② 確認 point 語意=指著狗（若是「指方向叫狗去」它反而有害） | IPN Hand 正面坐姿域 vs 狗仰角；**demo 的 bbalg 雙窗投票 + per-hand 追蹤配方不用模型也值得抄** |
| `451_DAN` | 表情辨識 AffectNet-8（MIT、TRT EP demo 同款 pattern、GPU 5-10ms/face） | Expression 層情緒能力線立項（PRD 層面先確認） | FER 本質：AffectNet-8 SOTA 也只 62-67%，長者臉誤判 anger/sad 已知，只能降級成正/負/中三桶用；RAM 200-300MB 撞紀律須實測 |
| `137_MoveNet_MultiPose` | 6 人單次 forward、TFLite CPU（**走 TFLite 不要走 TRT**——ONNX→TRT 有輸出錯誤前科） | guardian 多人 pose 立 scoreboard line | A/B 必加零新模型對照組：YOLO26n person bbox + MediaPipe per-crop top-down |
| `472_DEIMv2-Wholebody34` | 34 類人體部件偵測（Apache-2.0、NMS-free [N,7] 輸出與 YOLO26n 同款整合形態）；輪椅/拐杖/年齡/8 向頭朝向是全 stack 零覆蓋的長者敘事能力 | guardian/長者屬性進 scoreboard | Jetson 只跑得動 Atto/Femto，關節 AP 慘（0.03-0.09）不能當 pose 用；ort≥1.21 TRT EP 需 `trt_op_types_to_exclude` workaround |
| `427_RTMPose_Hand` | 21 點手部 keypoint（Apache-2.0、top-down crop 式） | **先做零成本實驗**：現有 MediaPipe Hands landmarks + 規則/KNN + 時序平滑解 class 翻動；失敗且遠距是主因才回頭 | 兩段 GPU pipeline；RTMPose GPU 滿載前科需洗清 |
| `429_OSNet` | 全身外觀 ReID（MIT、x0_25 僅 0.2M params、CPU 可跑） | guardian follow / 陌生人跨時間再現立項 | **TRT FP16 下 merged-similarity 變體輸出壞掉**（0.725→0.999），必須用 feature_only 變體 + 外部 cosine；換衣即失效，文件不可 overclaim |
| `439_Depth-Anything` | 單目稠密深度（V1 snapshot） | nav-depth 立 scoreboard line | **zoo 目錄本身 SKIP**（落後兩代、S 變體 tarball 7.17GB）；屆時從上游取 V2-S（Apache）308-364 輸入；輸出是相對深度，避障需 metric 化 |
| `117_DTLN` | 即時降噪（MIT、CPU ~0.2ms/hop、16kHz 對齊管線） | 拍板復活機身收音路線（目前已廢棄改筆電收音） | zoo 的 INT8 校準公式錯誤（用上游自帶檔）；競品 DeepFilterNet3/GTCRN 更強，DTLN 只配當 baseline |

\* `481_WHC` 第一輪每角度名額被佔未深查，由主線對本地 README/LICENSE 補證（MIT、規格屬實）。

### 4.3 SKIP（理由摘要）

| 目錄 | 一句話理由 |
|------|------|
| `132_YOLOX` | 唯一賣點（現成 1088x1920 高解析 ONNX）被 incumbent 支配：YOLO26n WSL re-export `imgsz=1280` 幾分鐘複製且更準（mAP ~40 vs YOLOX-Nano 25.8）；2021 架構、raw 輸出要自寫 42.8k anchors 的 CPU decode+NMS |
| `334_DAMO-YOLO` | 上游 2024-05 後棄置；demo README 自曝 TRT FP16 精度劣化前科；NMS 嵌圖破壞單 engine 路徑 |
| `459/464_YOLOv9-Wholebody25/28` | 被同作者 supersede ≥4 次（→468→471 MIT→485/488 Apache）；GPL-3.0；無關節輸出做不了 sitting |
| `484_TransFace` | 被同 release 的 LVFace 全面壓制（1/4.5 大小、新兩年、準度相當）；雙邊上游 license=null；最小變體 330MB 違反 RAM 紀律 |
| `442_YOLOX-HandLR-Dist` | hand bbox 需求被 449_WholeBody12（同 AP、多 8 類、Apache）與 488_DEIMv2（NMS-free）嚴格壓制 |
| `475_VSDLM` | 解析度數學否決：D435 640x480 下嘴部 1.5m 只有 ~15px，模型原生 48px；且只是單幀開合分類非現成 VAD；音訊域 Silero VAD 是更便宜的第一實驗 |
| `259_Emotion_FERPlus` / `453_FairDAN` | 2016 老件 / emotion head 同顆 DAN 但多出 gender/race 屬性（長照專案倫理地雷）+ 914MB |
| `072_NanoDet`、`003_posenet` 等古董層 | 世代淘汰，僅池完整性記錄 |

---

## 5. 三個痛點的具體答案

### (a) cup 0.7m → **此 zoo 無解，但研究過程鎖定了正解**
Wholebody 系全是人體類（無 cup）；COCO 域候選全被 incumbent 支配。正確的第一刀（與 supervision 報告 §7a 互補）：
1. **WSL 上 `ultralytics` re-export YOLO26n `imgsz=1280`**（禁令只限 Jetson 安裝，不擋 WSL 匯出）→ Jetson TRT FP16 重建 engine，量遠距 cup recall vs Hz。
2. 低 threshold (0.25-0.3) + 時序確認（supervision ByteTrack spike，已另案）。
3. SAHI tiling 離線驗證。
三者都不用換模型、不用這個 zoo。

### (b) gesture 誤觸 → **條件式供給 + 一個免費贈品**
- 零成本實驗先行：MediaPipe Hands landmarks + 規則/KNN + 時序平滑（427 深查指出的對照組）。
- `477_PGC` 只在「point=指著狗」語意下是現成 verifier；`481_WHC` 是 wave 回歸主線時的確認器。
- **免費贈品**：PINTO demo 的防翻動配方（SORT per-hand 追蹤 + `bbalg` long/short 雙窗投票）**不裝任何模型就能抄進現有 gesture lane**——這可能是 gesture 誤觸最便宜的解。

### (c) sitting 不穩（greet gate）→ **478_SC ensemble，本研究最高 ROI**
115KB、<1.5ms、MIT、前級免費、訊號正交。唯一閘門是 Go2 視角 domain 實測。建議的最小 spike：WSL 上拿 demo 錄影的 person crop 離線跑 SC，對照 MediaPipe sitting 判定的 agreement/分歧分佈，一個下午出數字。

---

## 6. 使用機制注意事項（操作層）

1. **大 tarball 陷阱**：AdaFace 21.3GB、TransFace 3.59GB、Depth-Anything-S 7.17GB、LVFace 1.7GB——**永遠先看有沒有 GitHub releases / HF 單檔路徑**（481_WHC、483_LVFace 都有），或在 dev 機開箱抽單檔再 rsync。
2. **鏡像紀律**：選定候選後把模型檔備份到自己的儲存（Wasabi 單 bucket、無 checksum、作者個人付費）。
3. **License 欄位進 scoreboard**：每個候選登記 license（LVFace=NC、SC/WHC/PGC/AdaFace/OSNet=MIT、DEIMv2=Apache、YOLOv9 系=GPL），82 個無 LICENSE 目錄視同最嚴格。
4. **與 benchmark 制度對接**：本報告的 BENCHMARK_CANDIDATE/MAYBE 直接餵 `benchmarks/configs/{task}_candidates.yaml` 的 shortlist 格式；觸發條件寫進 scoreboard 的 capability line 定義。
5. **與 supervision 研究的關係**（同日另份報告）：互補不重疊——PINTO zoo 供模型，supervision 供後處理/evidence/評估工具；SC+bbalg 的時序平滑哲學與 supervision ByteTrack 時序確認同路數。

---

## 7. 最終 Verdict：**ADOPT_AS_CANDIDATE_SOURCE**

| 層 | 裁決 |
|------|------|
| 作為五能力的候選池來源（餵 benchmark 制度） | **ADOPT_AS_CANDIDATE_SOURCE** |
| `478_SC` sitting ensemble | **BENCHMARK_CANDIDATE**——建議最先動（離線 spike 一個下午） |
| `483_LVFace` / `290_AdaFace` face recognition | **BENCHMARK_CANDIDATE**——等 face 能力線 sweep 不及格才上場 |
| cup 0.7m / VAD 瓶頸 | **此 zoo 無供給**（正解分別是 incumbent 高解析 re-export 與 Silero VAD） |
| 立刻在 Jetson 裝任何模型 | 否——全部先過 WSL 離線驗證 + benchmark 制度 |

單一強制裁決取 ADOPT_AS_CANDIDATE_SOURCE：483 個目錄裡真正對 PawAI 有效的供給集中在 **face recognition 挑戰者**與 **2025 超輕量分類器家族**（後者整套 MIT、CPU 亞毫秒、全是「掛在現有 bbox 後面的 1-bit verifier」形態，與 PawAI 的 ensemble/gate 架構天然契合）；其餘大半是已被 supersede 的舊轉檔。把它當「精選過的候選池目錄」用，不要當「全部量化好的寶庫」用。

---

## 附錄 A：研究過程透明度

- 第一輪 workflow：21 agents（6 盤點 + 14 深查 + 1 critic），critic 抓出 8 項缺口/矛盾，其中關鍵缺口（475-480 家族只撈到 481、表情整類漏掉、深查 rec 反轉無理由）由第二輪 4 agents 補查解決；目錄總數三個版本的矛盾（484/488/483）由 critic 實測裁定為 **483 模型目錄 + 999_media**。
- 深查 rec 反轉的理由已在 §4.3 補齊（critic 要求）：132_YOLOX/442/459 的「角度首選→SKIP」全是「被 incumbent 或同 zoo 後繼嚴格支配」，非矛盾。
- 量化覆蓋率三個數字（57%/69%/30%）是三種分母（30 目錄抽樣 / convert_script 子集 / 全母體下限），抽樣點估計 95% CI 約 ±18pp，方向一致。

## 附錄 B：未深查的觀察名單（盤點階段記錄）

`387_YuNetV2`（face 偵測 640x640 零成本對照）、`431_NITEC`（eye-contact，ENGAGED gate 替代，MIT，主線已補證）、`476_OCEC`（閉眼/打瞌睡，F1 0.992）、`480_HSC`（微笑，小變體 F1 0.48-0.74 偏弱）、`479_PUC`（作者自承失敗，略過）、`097_YAMNet`（聲音事件 521 類，guardian 聽覺通道）、`286_SCI`（低光增強，千級參數）、`435_MobileFaceNet`（alignment 前處理）、`449_YOLOX-WholeBody12` / `488_DEIMv2-Wholebody49`（hand bbox 需求時優於 442/464）、`247_PoseC3D`（跌倒時序分類，事件觸發式）、`346_facial_expression_mobilefacenet`（FER 的 CPU 備選）、`356_EdgeYOLO`、`376_RT-DETR`、`333_E2Pose`、`115_MoveNet`、`402_trt_pose`、`469_Face_Deblurring`、`146_FastDepth`、`362_ZoeDepth`、`430_FastReID`、`254_FullSubNet-plus`。
