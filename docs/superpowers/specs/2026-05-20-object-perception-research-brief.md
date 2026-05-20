# 物件偵測升級 — 研究 Brief

> 文件類型：Research brief（外部調查 + PawAI 決策對齊）
> 日期：2026-05-20
> 關聯：[北極星 §2](2026-05-19-pawai-may-june-north-star-design.md) ／ 執行 protocol：`2026-05-20-object-perception-benchmark-protocol.md`
> 範圍：5/22–6/18 窗口物件偵測升級的「為什麼這樣做」。不含執行步驟（見 protocol）。

---

## 1. 問題陳述

5/18 demo 中，物件偵測在實機環境下表現極差：常見居家物（杯子、手機、書、椅子、背包）在 1–2m 距離仍頻繁漏檢或閃爍。這直接打斷 Brain 對家庭環境的描述能力，也讓「PawAI 看懂環境」這條敘事失效。

當前實作（`object_perception/object_perception/object_perception_node.py`）：
- 模型 YOLO26n（2.7M 參數、9.5MB ONNX，COCO mAP@0.5–0.95 ≈ 39.7%），ONNX Runtime + TensorRT EP FP16
- 輸入 640×640、`tick_period=0.067`（~15 FPS）、`publish_fps=8`
- `confidence_threshold=0.5`、COCO 80 類全開（`class_whitelist=[]` 代表不過濾）
- HSV 12 色純規則 bucket 對整個 bbox 做顏色分析，無深度、無 tracking

硬限制：
- Jetson Orin Nano 8GB 統一記憶體；同時要養人臉 / 手勢 / 姿勢 / 語音 / Brain
- **絕不可** `pip install ultralytics`（會破壞 Jetson torch wheel）→ 只能換 `.onnx` 檔
- 本窗口（–6/18）**不做**大規模自建資料集訓練

---

## 2. PawAI 成功標準

物件偵測在 PawAI 的位置不是「辨識清單」，而是 **Brain 的環境 grounding**。成功的定義不在 mAP，而在：

> 必達物件在 demo 場景（1–2m、正常光線）能 **穩定進入 Brain context**，使 Brain 在對話中能自然引用。

具體指標（細節在 protocol §5 門檻）：
- **P0 必達物件**（5 類，6/18 必須穩定）：杯子 / 手機 / 書 / 椅子 / 背包
- **P1 觀察物件**（3 類，先測但不保證）：瓶子（透明/反光） / 遙控器（COCO 無標準類別） / 時鐘（尺寸角度差異大）
- **穩定**＝同一物件需通過 temporal voting（N 幀內 ≥ M 幀同類）才進 Brain context，避免單幀閃爍污染 LLM
- **顏色**＝明顯時輸出，不確定時 `Unknown`，不硬猜

明確不追求：
- COCO 80 類全部穩定
- 任意距離、任意角度都能認
- 完整自主尋物閉環（本窗口不做，見 §6）

---

## 3. 根因假設與待驗證項

承接北極星 §2 排序，本 brief 不重新推導，僅標註「現場是否仍待驗證」。

| # | 假設 | 影響 | 本窗口驗證手段 |
|---|---|---|---|
| 1 | 模型容量太小（26n 對居家小物召回最差） | 高 | Protocol Step 3：26n → 26s A/B |
| 2 | 輸入 640 太低，1.5m 外物件像素過少 | 高 | Protocol Step 2：640 → 768 |
| 3 | `confidence_threshold=0.5` 偏高，砍掉 0.3–0.5 真陽性 | 高 | Protocol Step 1：0.5 → 0.35 → 0.30 |
| 4 | TensorRT EP silent fallback 到 CPU（provider 參數或 cache 失效） | 高 | Protocol §2 必查 |
| 5 | HSV 全 bbox 顏色規則受背景污染 | 中 | Protocol Step 6：central crop + CLAHE + LAB/KMeans 離線 prototype |
| 6 | COCO 類別缺（學校特定物）+ 無 tracking → 單幀閃爍，Brain context 斷續 | 中 | Protocol Step 5：temporal voting 離線 prototype |

「現場是否仍待驗證」全部標 **是**。任何結論在 protocol 跑完前都是推論。

---

## 4. 外部調查

### 4.1 Jetson Orin Nano 小 YOLO FPS 量級

**重要免責**：以下數字只作量級參考。不同 benchmark 的相機輸入、前後處理、TensorRT engine 版本、Python overhead 差異極大；最終決策以 PawAI 自己的 Jetson 實測為準（protocol Step 0 baseline）。

| 來源 | 平台 | 模型 | 輸入 | 精度 | 量級 |
|---|---|---|---|---|---|
| Ultralytics DeepStream guide | Jetson Orin **NX 16GB**（**不是 Nano**） | YOLO26s | 640 | TensorRT FP16 | ~126 FPS / 7.94 ms |
| Ultralytics DeepStream guide | Jetson Orin NX 16GB | YOLO26 各變體 | 640 | 多精度 | 表格未列 Nano 數據 |
| EdgeFirst yolo26-det 模型卡 | 通用 | YOLO26n/s/m/l/x | 640 | ONNX FP32 / TFLite INT8 | 模型卡列 mAP，**未填 Jetson 量測欄** |
| 既有 PawAI memory（3/21 batch） | Jetson Orin Nano 8GB | YOLO11n（前代）類比 | — | — | 與本任務相關性低，不直接引用 |

可結論的量級：
- Orin Nano 8GB 的 TensorRT throughput 大約是 Orin NX 16GB 的 **1/2 ~ 1/3**（GPU TFLOPS 差距）；推 26s 在 Nano 8GB 上 FP16 應在 **30–50 FPS 級**（理論上限，未計 ROS2 callback / Python / 預處理 overhead）。
- 實際 ROS2 pipeline 中，`tick_period=0.067` 已把節流定在 ~15 FPS；換 26s 後若推理時間仍小於 67ms，FPS 不會變化，只是延遲變大。
- 換 input 640 → 768 預期推理時間 ≈ ×1.44（像素數比例），可能讓 26n 在 tick 內跑不完；26s + 768 風險更大。

**所以 §4.1 給的不是「26s 一定夠快」，而是「26s 在 Nano 8GB 上有合理機會跑得動，但須現場量測延遲與 tick 內預算」**。

來源：
- Ultralytics DeepStream NVIDIA Jetson guide — https://docs.ultralytics.com/guides/deepstream-nvidia-jetson/
- EdgeFirst yolo26-det model card — https://huggingface.co/EdgeFirst/yolo26-det

### 4.2 居家物件資料集與 COCO 缺口

COCO 80 類涵蓋 cup / cell phone / book / chair / backpack 五個 P0 必達，所以「類別不存在」不是 P0 問題。**P0 的痛點是「COCO 訓練分布偏離居家近距相機視角」**：COCO 大量物件是中遠景 / 室外 / 多物雜亂場景，PawAI 是 1–2m 近距、單一主體、室內光線，分布差異導致 confidence 落點低。

**三層 dataset 策略**：

| 層 | 用途 | 推薦 | 為什麼 |
|---|---|---|---|
| **L1：PawAI 現場集** | 本窗口 benchmark dataset，**非訓練集** | 5 必達 + 3 觀察集 × 3 距離 × 3 光線，每組 30s rosbag | 唯一能回答「在我們的場地到底爛在哪」的資料；protocol Step 0 baseline 的素材來源 |
| **L2：fine-tune 第一選擇** | 若 §6 觸發條件成立才動 | **HomeObjects-3K + PawAI 自拍 200–500 張/類** | HomeObjects-3K 量小品質乾淨（2285 train / 404 val，AGPL-3.0），題目對 PawAI 對齊 |
| **L3：補強備選** | 只在 L2 仍不足時 | 抽 Open Images 類別 / YCB 桌面物 | 不整包用，避免整理成本 |

**HomeObjects-3K 重要限制**：其 12 類為 bed / sofa / chair / table / lamp / TV / laptop / wardrobe / window / door / potted plant / photo frame，**家具偏向**，與 PawAI P0 必達只有「椅子」一類直接重疊。所以 L2 fine-tune 不能單靠 HomeObjects-3K — 必須配上 PawAI 自拍的 cup / phone / book / backpack 集。HomeObjects-3K 的價值是補環境家具（chair / lamp / sofa / table），讓 Brain 環境敘事更豐富。

**不採用**：
- **COCO 自己重訓**：mAP 邊際提升小，工時不值
- **Open Images / Objects365 整包**：規模太大，本月工時放不下 pretrain
- **YCB / BOP**：偏 manipulation / 6D pose，目前 PawAI 沒有抓取需求
- **SUN RGB-D / ScanNet**：3D scene parsing，與 detection 不同題

來源：
- HomeObjects-3K — https://docs.ultralytics.com/datasets/detect/homeobjects-3k/
- Open Images — https://research.google/pubs/the-open-images-dataset-v4-unified-image-classification-object-detection-and-visual-relationship-detection-at-scale/
- Objects365 — https://www.objects365.org/overview.html
- YCB Benchmarks — https://www.ycbbenchmarks.com/

### 4.3 YOLO 任務類型對 PawAI 的取捨

| 任務 | PawAI 角色 | 本窗口取捨 |
|---|---|---|
| **Object Detection** | 環境 grounding 主線，§2 成功標準的承載者 | **本窗口主戰場** |
| **Pose Estimation** | 人的姿勢理解（站/坐/跌倒），由 `vision_perception` 處理 | 不和 object detection 混；姿勢辨識在北極星 §5 降級 P2 |
| **Multi-Object Tracking** | 物件 ID 追蹤、跨幀身分 | **本窗口不引入**；以 temporal voting 替代（§4.4） |
| **Segmentation** | 物件遮罩 → 更準的顏色 / 抓取候選區 | 6/18 不做；計算成本不值現階段 |
| **Classification** | 整張影像分類 | PawAI 不需要 |
| **OBB（oriented bbox）** | 旋轉框、空拍 / 工業 | PawAI 不需要 |

### 4.4 單幀閃爍與 object memory 做法

問題：YOLO 在 confidence 邊界（例如真值 ~0.45）會在連續幀間抖動，造成同一物件 OBJECT_DETECTED / OBJECT_LOST 事件反覆觸發。Brain 看到斷續事件流會在描述中「自我修正」，產生「我看到一本書 …… 啊書不見了 …… 又看到了」的破碎敘事。

**業界做法對比**：

| 做法 | 描述 | 成本 | 適合 PawAI？ |
|---|---|---|---|
| **Tracker（ByteTrack / OC-SORT）** | 跨幀 ID 維持，含 Kalman + 關聯 | 中（多一個 stage、需調參） | 未來方向；本窗口不引入 |
| **Temporal voting（N-of-M frames）** | 同類在 M 幀視窗內出現 ≥ N 幀才升 stable | 低（純後處理） | ✓ **本窗口採用** |
| **Two-tier object memory（DimOS ObjectDB）** | pending（候選）/ permanent（穩定）兩層，跨幀位置容差 | 中（要維 memory） | 6/18 可選；先做 voting，視效果決定是否升 |
| **Class-specific threshold** | 不同類給不同 conf 門檻（杯子可低、椅子可高） | 低 | ✓ 配合 Step 4 一起做 |

**取捨**：北極星已決定走 temporal voting + class-specific threshold；DimOS 兩層 memory 列為「voting 不夠才升級」的備案，不在本窗口必達範圍。

### 4.5 顏色穩定做法

現況：`analyze_bbox_color` 對整個 bbox 做 HSV 12 色 bucket，主要問題：
- bbox 內含背景（書本邊緣有桌面、杯子背後有牆）→ peak 顏色被污染
- HSV 對光源色溫敏感，偏暗 / 背光下分類失準
- 12 色純規則 bucket 對「材質色」（金屬、玻璃、塑膠反光）無解

**業界做法**：
- **Central crop**：bbox 內縮 30–40%（去邊緣 → 去背景）
- **CLAHE（Contrast Limited Adaptive Histogram Equalization）**：本地對比拉伸，減低光源差異
- **LAB / KMeans**：在 LAB 色空間（與人感知接近）做 K=2~4 分群，取最大 cluster 中心作主色
- **保守輸出**：peak 比例 < 閾值就回 `Unknown`，不硬猜（現有實作已做 0.25 門檻）

**取捨**：6/18 前以「central crop + CLAHE + LAB/KMeans」三件套替換 HSV bucket。Segmentation mask（精準前景）視為下一階段。

---

## 5. PawAI 本窗口決策

**做**（依 protocol 順序）：
1. 量現況 baseline（量化「到底爛在哪」，避免換錯東西）
2. 驗證 TensorRT EP 真的吃 GPU（推翻假設 4 的前提）
3. A/B：`confidence_threshold` 0.5 → 0.35
4. A/B：`input_size` 640 → 768
5. A/B：模型 26n → 26s
6. Class-specific threshold（杯子可低、椅子可高）
7. Temporal voting 離線 prototype（不改 node）
8. 顏色 central crop + CLAHE + LAB/KMeans 離線 prototype（不改 node）

**不做**：
- 完整自建資料集訓練
- 引入 ByteTrack / OC-SORT 等 tracker
- 跳 Open Images / Objects365 大訓練
- 任何 `pip install ultralytics` 類動作
- 把物件偵測當避障主感測器（避障靠 RPLIDAR + reactive_stop + Nav2，見北極星 §4）
- 把物件偵測當跟隨主感測器（跟隨靠人臉 / 人體 / 手勢 + nav approach）

---

## 6. 下一階段觸發條件

**若** YOLO26s + 768 input + `confidence_threshold` 調整 + class-specific threshold + temporal voting + 顏色升級全做完後，**P0 必達物件**在 1–2m 正常光線下仍無法穩定進 Brain context（依 protocol §5 門檻判斷），**才** 啟動下一階段資料 fine-tune：

```
Stage 2 (post-6/18 候選):
  - 資料來源：HomeObjects-3K（家具類，補環境） + PawAI 自拍 200–500 張/類
                * 自拍重點：cup / phone / book / backpack（HomeObjects-3K 不含）
                * 拍攝：demo 場地、1–2m、3 種光線、多角度
  - Fine-tune target：YOLO26s（保持與 §5 一致，避免再換骨幹）
  - 部署：產 .onnx + TensorRT engine cache，**不引入 ultralytics 至 Jetson**
  - 驗收：以同份 PawAI 現場集 rosbag 對照 baseline，必達物件 detect rate 改善 ≥ 20 pp
```

**明確止損點**：不在 §5 全做完前啟動 fine-tune；不在沒有量化證據前承諾訓練成本。

---

## 7. Benchmark 後待回答問題

這些問題在 protocol 跑完前**無法**用研究方式回答，必須等實測數據：

1. **26s 在 Jetson 8GB 上單跑 FPS 是多少？** 預期 ≥ 8 FPS。
2. **26s + 768 input 是否仍能在 `tick_period=0.067` 內完成推理？** 若不能，要鬆動 tick_period 還是降 input。
3. **必達物件在 1–2m 正常光線下的 `confidence` 真實落點？** 決定 Step 1 的最終門檻是 0.35 還是 0.30。
4. **TensorRT EP 是否 silent fallback 到 CPU？** Provider log + 推理延遲對照。
5. **Temporal voting 的 N 幀門檻設多少？** 預期 N=3/M=5；以 baseline rosbag 離線回放決定。
6. **與 nav / brain 同跑時 FPS 降幅？** 影響 §5 「degraded ≥ 5 FPS」是否成立。
7. **顏色 LAB/KMeans 是否在偏暗 / 背光下仍穩定？** rosbag 離線回放對照 HSV。

回答後，依結果寫 §5 的「採用 / 不採用 / 觸發 §6」結論段。

---

## 8. Runtime budget 是 P0 共同約束（非物件章節獨有，但物件升級必受其拘束）

物件偵測的「升級成功」不只看辨識率，更看是否能在 Jetson Orin Nano 8GB 的整體 runtime 預算內生存。本節是物件章節對齊北極星治理章的快照；治理權威以北極星跨章節章為準（見 [北極星 §7.5 Runtime budget](2026-05-19-pawai-may-june-north-star-design.md#75-runtime-budget--mode-治理跨章節)）。

**核心原則**：6/18 demo 不應讓所有高負載模組同時滿速跑。物件偵測的角色定位（grounding，不是 safety brake）允許它降頻。

**物件偵測在 mode 表內的位置**：

| Demo Mode | Object 物件偵測 | 理由 |
|---|---|---|
| Chat mode（語音/人臉/Brain） | low-rate（1–2 FPS）或 off | 對話主場景，object 只在需要引用環境時用 |
| Scene mode（看懂環境） | on（boost，最高設定） | 物件偵測是主角 |
| Nav mode（安全短距移動） | low-rate 或 off | nav / safety 優先佔 GPU / CPU |
| Demo full（任務閉環） | 分段：問「看到什麼」時 boost 5s，移動時降頻 | 由 Executive / Studio 切換 |

**物件偵測在升級評估時必須通過三組情境量測**（細節見 protocol §5）：
1. **Object only**：單跑乾淨基線，目標 ≥ 8 FPS
2. **Full perception**（object + face + gesture + pose + brain + speech，無 nav）：目標 ≥ 5 FPS
3. **Nav mode**（nav + safety + object low-rate）：object 可降至 1–2 FPS，但 **nav cmd_vel 不可掉**

任何模型 / 參數升級若無法通過情境 3 的「nav 不掉」測試，**不能** 設為常駐預設，只能列為 boost-only。

**Brain context 更新頻率**：物件偵測不需要 30 FPS。Brain 只需要「每 0.5–1.0 秒一次穩定 object context」就足以支撐對話與環境敘事；debug image 3–5 FPS 即可。**穩定 > 即時**。

---

## 變更紀錄
- 2026-05-20 草稿建立。
- 2026-05-20 §8 補入 runtime budget 共同約束（mode 表 + 三情境量測 + Brain context 更新頻率）；同步推一條變更回北極星 §7.5 治理章。
