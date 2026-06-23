# roboflow/supervision 對 PawAI 的可用性研究報告

> **日期**：2026-06-11
> **Verdict**：**GO_ADOPT_FOR_EVIDENCE**（offline/WSL evidence + evaluation tooling）；Jetson runtime 採用另案，前置條件為 benchmark（見 §5、§8）
> **研究方法**：deep-research workflow（5 角度 × 22 來源 × 104 claims）+ 本地 clone source 逐項查證。
> workflow 驗證階段撞 session limit，6 條 claims 完成 3 票對抗驗證（標 ✅3-0），其餘關鍵 claims 由本報告直接對本地 clone（`/home/roy422/newLife/supervision`，commit `b8ebc14`，2026-06-10，version `0.29.0.dev`）逐行查證（標 📍file:line）。
> **本研究為 read-only**：未改任何 PawAI code、未 commit、未安裝任何套件。

---

## TL;DR

Supervision 是 **model-agnostic 的 CV 後處理／工具函式庫**——不是模型、不是 detector、更不是 ASR。它對 PawAI 的價值集中在三件事：

1. **Evidence 視覺化與落盤**（annotators + JSONSink + VideoSink）→ 直接餵 Studio Evidence Center 的 offline pipeline。
2. **離線評估工具鏈**（mAP / ConfusionMatrix / dataset 轉換）→ 把「cup 0.7m 才看得到」從軼事變成可量化的 capability baseline 數字。
3. **偵測時序穩定化**（ByteTrack `minimum_consecutive_frames` + DetectionsSmoother）→ object 誤觸／閃爍的不換模型解法，但**只該以 spike 驗證後才考慮進 runtime**。

它**不能**直接解 cup 偵測距離（不是模型）、**不能**解 gesture 誤觸（無 hand/gesture connector、smoother 不平滑 class label）、對 speech **完全無關**。

---

## 1. Supervision 是什麼 / 不是什麼

**是什麼**：

- 一個 MIT license、純 Python（`requires-python >= 3.9` 📍`pyproject.toml:26`）的 CV utility library。自我定位：「A set of easy-to-use utils that will come in handy in any Computer Vision project」📍`pyproject.toml:8`。
- **Model-agnostic**：「Supervision was designed to be model agnostic. Just plug in any classification, detection, or segmentation model.」（README，✅3-0，[github.com/roboflow/supervision](https://github.com/roboflow/supervision)）
- 核心抽象是 `sv.Detections`——「standardizes results from various object detection and segmentation models into a consistent format」（✅3-0，[docs/detection/core](https://supervision.roboflow.com/latest/detection/core/)）。欄位：`xyxy / mask / confidence / class_id / tracker_id / data / metadata` 📍`src/supervision/detection/core.py:156-162`（注：workflow 曾誤殺「有 metadata 欄位」這條 claim，本地 source 證實 `metadata: dict[str, Any]` 確實存在於 core.py:162）。
- 周邊工具：24+ 種 annotators、ByteTrack tracker、PolygonZone/LineZone、DetectionsSmoother、InferenceSlicer、CSV/JSON sinks、dataset 格式轉換、mAP/F1/ConfusionMatrix metrics、video utilities。
- 活躍維護中：clone 當下最後 commit 為 2026-06-10。

**不是什麼**：

- **不是模型**：不含任何權重、不做推理，無法改善任何模型的辨識距離或準確率（✅2-1，[cheatsheet](https://roboflow.github.io/cheatsheet-supervision/)）。
- **不是 ASR / 與語音無關**：整個 `src/supervision/` 沒有任何音訊處理。
- **不是 ROS 套件**：無 rclpy 整合，所有對接要自己寫 adapter。
- **沒有泛用 ONNX Runtime / TensorRT adapter**：17 個 `from_*` connector（`from_ultralytics`、`from_inference`、`from_transformers`、`from_ncnn`…📍`detection/core.py:222-2007`）全是針對特定框架的物件格式；PawAI 的 YOLO26n ONNX raw output `(1,300,6)` 需手動建構（✅3-0）。但因為 `Detections` 是 dataclass，手動建構只要 ~5 行（`sv.Detections(xyxy=…, confidence=…, class_id=…)`），不算門檻。
- **不隱含 Roboflow Inference server**：supervision 是獨立 library，採用它不需要裝 Roboflow 的推理服務。

---

## 2. 對 PawAI 各感知模組的幫助

| 模組 | 現況 | 幫助程度 | 說明 |
|------|------|:---:|------|
| **object** | YOLO26n ONNX + TensorRT EP，`object_perception_node.py` 手刻 postprocess + cv2 繪圖 | ⭐⭐⭐ 最高 | raw `(300,6)` → `sv.Detections` 轉換 trivial（node 內 `object_perception_node.py:384-388` 已解出 x1y1x2y2/conf/cls）；ByteTrack、Smoother、PolygonZone、annotators、metrics 全部可接 |
| **face** | YuNet + SFace + 自製 IOU tracking | ⭐⭐ 部分 | bbox 可包成 `Detections`（identity 放 `data` dict），annotators / evidence 落盤可用；但 identity 邏輯、IOU 追蹤已存在且運作中，替換無收益——只在 offline evidence 渲染時有用 |
| **pose** | MediaPipe PoseLandmarker → 自製 sitting/fallen 分類 | ⭐⭐ 部分 | `sv.KeyPoints.from_mediapipe` **官方支援 PoseLandmarker 輸出** 📍`src/supervision/key_points/core.py:531-542`，配 `VertexAnnotator`/`EdgeAnnotator` 📍`key_points/annotators.py:30,104` 可做骨架 evidence 視覺化；但 pose 誤觸根因在 PawAI 自己的分類邏輯，supervision 不做姿勢分類 |
| **gesture** | MediaPipe Gesture Recognizer | ⭐ 很低 | `from_mediapipe` docstring 明載只支援「pose and face landmarks from `PoseLandmarker`, `FaceLandmarker` and the legacy `Pose` and `FaceMesh`」📍`key_points/core.py:539-542`——**沒有 hand landmarks / Gesture Recognizer connector**；且 gesture 誤觸是 class label 翻動，不是 bbox 抖動（見 §7b） |
| **speech** | SenseVoice / LLM / TTS | ✕ 無 | 純視覺 library，零交集（✅2-1） |

---

## 3. 功能對接清單（逐項對 PawAI）

### 3.1 `sv.Detections` — detection abstraction
📍`detection/core.py:127-162`。欄位 `xyxy/mask/confidence/class_id/tracker_id/data/metadata` 與 PawAI `/event/object_detected` 的 JSON payload（bbox + confidence + class + color evidence）幾乎一一對應。**價值不在 import 它，而在 schema 設計參考**——Plan D 的 `PerceptionEvent` 欄位命名若與之對齊，未來 offline 工具可零成本互轉（見 §4）。

### 3.2 Annotators — evidence 渲染
📍`annotators/core.py`：`BoxAnnotator`(:190)、`LabelAnnotator`(:1165)、**`RichLabelAnnotator`(:1480，支援自訂 TTF font——可取代 `object_perception_node.py:25,489-501` 為了 zh-TW label 手刻的 PIL 繞路）**、`TraceAnnotator`(:1942，畫移動軌跡)、`HeatMapAnnotator`(:2087)、`BlurAnnotator`(:1865)/`PixelateAnnotator`(:2199，臉部隱私遮蔽——展示影片可用）、`ComparisonAnnotator`(:3000，兩組偵測比對——調參前後對比圖）。✅3-0：annotators 是 Studio「看不懂機器為什麼反應」最直接可對接的功能。

### 3.3 Trackers — 時序穩定化
📍`tracker/byte_tracker/core.py:50-70`：`ByteTrack(minimum_consecutive_frames=N)`——「物體必須連續 N 幀被偵測才建立 track」，註解明寫「prevents the creation of accidental tracks」。這是**單幀假陽性誤觸的現成解法**（object 適用；gesture 不適用，見 §7b）。ByteTrack 的兩階段匹配還會用低信心偵測去維持既有 track——對「cup 看到又消失」的閃爍有幫助（對「從來沒看到」沒幫助）。

### 3.4 Zones / Line counting — 空間 gating
📍`detection/tools/polygon_zone.py:18-97`：`PolygonZone.trigger(detections)` 回傳每個 detection 是否在多邊形內的 bool array，錨點預設 `BOTTOM_CENTER` 可自訂。可做「只有互動區內的 cup/person 才觸發 brain event」的空間過濾——這正好對應 6/8 reactive_stop「側前家具誤判」同類問題在視覺層的版本。`LineZone` 📍`detection/line_zone.py:26` 對居家場景用處低（過線計數是零售場景）。

### 3.5 Dataset tools — 標註資料集
📍`dataset/core.py:330-626`：`DetectionDataset.from_yolo/from_coco/from_pascal_voc` + `as_*` 互轉。價值：把 demo 錄影抽幀標註成 YOLO 格式的「居家 cup/person 測試集」，餵 §3.6 的 metrics。

### 3.6 Metrics / Evaluation — 量化能力基線
📍`src/supervision/metrics/`：`mean_average_precision.py`、`f1_score.py`、`precision.py`、`recall.py`；`ConfusionMatrix` 📍`metrics/detection.py:200`。**與 6/18 scope pivot 的 scoreboard-first 路線直接共振**：用居家自錄資料集跑 YOLO26n 的 per-class mAP / per-distance recall，把「cup 0.7m」變成 scoreboard 上的數字，再決定要不要調 threshold / 換模型 / 上 slicer。需 `pandas>=2`（`metrics` extra）📍`pyproject.toml:62-64`。

### 3.7 Video utilities — 錄影與重播
📍`utils/video.py`：`VideoSink`(:76)、`get_video_frames_generator`(:231)、`process_video`(:283)、`FPSMonitor`(:459)。offline 工具鏈的膠水：rosbag/錄影 → 逐幀 annotate → evidence MP4。

### 3.8 Sinks — 結構化 evidence 落盤
📍`detection/tools/csv_sink.py:31`、`json_sink.py:13`：`CSVSink/JSONSink.append(detections, custom_data)` 把每幀偵測 + 自訂欄位（可塞 `decision_id`！）寫成 CSV/JSON——與 Plan E trace 的因果鏈 ID 對接後，就是 Evidence Center 的資料層。

### 3.9 InferenceSlicer — 小物件偵測（SAHI-style）
📍`detection/tools/inference_slicer.py:64-95`：把影像切成重疊小塊、各自推理、NMS 合併，multi-threaded callback 架構。**這是全庫唯一可能直接改善「遠距離小 cup」的功能**，但代價是一幀跑 N 次推理——Jetson 現況 debug_image 只有 6-8 Hz，切 4 片可能掉到 ~2 Hz。**NEEDS_BENCHMARK，勿直接上 runtime**。

---

## 4. 對 Plan C / D / E 的具體建議

### Plan C（pawai_contracts extraction）：**不要碰 supervision**
- `pawai_contracts` 的鐵律是 ROS-free 且依賴極輕（plan 明文「不准 import rclpy / IE / pawai_brain」）。supervision 硬依賴完整版 `opencv-python` + `matplotlib` + `scipy` 📍`pyproject.toml:50-61`——讓 contracts 帶上這坨是違反 plan 精神的。
- **唯一動作**：無。v1 contracts 範圍明文排除 PerceptionEvent，supervision 連 schema 參考的角色都排不進這個 PR。

### Plan D（Brain Router Phase 0 / PerceptionEvent）：**只借 schema 命名，不 import**
- Phase 0 是「逐字搬移 JSON 解析、輸出逐 byte 不變」，本來就不該引入任何新依賴。
- **具體建議**：設計 `PerceptionEvent` dataclass 欄位時，視覺類事件的欄位命名對齊 `sv.Detections` 慣例——`xyxy`（不是 x/y/w/h）、`confidence`、`class_id`、`tracker_id`（預留，現在可為 None）、`data`（自由 dict：identity/color/gesture name）。成本為零（只是命名選擇），收益是未來 offline 工具一行 `sv.Detections(xyxy=np.array([ev.xyxy]), …)` 就能把 PerceptionEvent 流轉成 supervision 生態的輸入。
- 不要為了 supervision 改 Phase 0 的「解析語意逐字搬移」原則——golden test 優先。

### Plan E（Brain Trace v1）：**trace 預留 evidence 欄位，落盤交給 Studio plan**
- Plan E 邊界是「schema + 發射、不落盤」。supervision 在這層沒有角色（它不是 ROS publisher）。
- **具體建議**：`trace_schema.py` 的「來源事件摘要」欄位裡保留 bbox（xyxy）與未來的 `tracker_id`。這樣 Studio Evidence Center 落盤後，可以用 `decision_id` join 回 debug 影格，再用 annotators 重建「機器當下看到什麼」的標註圖——這就是「為什麼沒反應」的視覺證據。
- JSONSink 的 `custom_data` 機制 📍`json_sink.py:169` 可作為 Evidence Center 落盤格式的參考（每列 = 一幀偵測 + decision_id）。

### Studio Evidence Center（future plan）：**supervision 的主場**
這是 verdict 的核心理由。建議的 offline pipeline：
```
demo 錄影/rosbag + /brain/trace JSONL + /event/* JSONL
   → 重建 sv.Detections（手寫 5 行 adapter）
   → ByteTrack 補 tracker_id（離線重跑，不動 runtime）
   → BoxAnnotator + RichLabelAnnotator(zh-TW TTF) + TraceAnnotator 疊圖
   → VideoSink 輸出 evidence clip（自動 mux 原音軌）
   → JSONSink 落盤（含 decision_id），Studio 前端讀檔呈現
```
全程在 WSL，零 Jetson 風險。

---

## 5. Jetson runtime 還是 WSL/offline tool？

**結論：v1 只做 WSL/offline，不進 Jetson runtime。** 理由：

1. **依賴衝突風險**：supervision 硬依賴 pip 完整版 `opencv-python>=4.5.5.64` 📍`pyproject.toml:54`（曾有 headless 化的 PR #180，但現行 codebase 已 revert 回完整版）。Jetson 上 ROS2 Humble 的 `cv_bridge` 綁系統 OpenCV，pip 再裝一份 cv2 會造成雙份 OpenCV 共存——可以動但 RAM 重複載入，且 8GB 統一記憶體的預算紀律是「保留 ≥0.8GB 餘量」。
2. **附帶依賴不小**：`matplotlib`、`scipy`、`pillow` 全是硬依賴 📍`pyproject.toml:52-59`，runtime node 用不到 matplotlib 卻必須裝。
3. **收益不對稱**：runtime 真正想要的只有 ByteTrack（一個檔案 📍`tracker/byte_tracker/core.py`）；evidence/metrics/dataset 的價值全部在 offline 端就能兌現。
4. **例外路徑**：若 spike 證明 ByteTrack 對 object 穩定性有實質改善、且想進 runtime，兩條路：(a) 在 Jetson 裝 supervision 並 benchmark RAM/Hz（走 `uv pip install`，先量 import 後 RSS 增量）；(b) 只 vendor `byte_tracker/` 進 object_perception（MIT license 允許）。**兩條都需要 benchmark 數據才准做，且不在本研究 scope。**

---

## 6. 最小可行 spike（offline evidence spike）

**目標**：用一段已錄好的 demo 影片（如 S3 cup take）證明「supervision 能產出 Studio 等級的 evidence clip + 量化閃爍改善」。

**要新增的檔案（全部在 offline 工具區，不碰 runtime）**：
- `benchmarks/scripts/supervision_evidence_spike.py` — 讀錄影 + `/event/object_detected` JSONL → 重建 `sv.Detections` → `ByteTrack(minimum_consecutive_frames=3)` → annotate → `VideoSink` 出 MP4 + `JSONSink` 出 JSONL
- （可選）`benchmarks/configs/supervision_spike.yaml` — 輸入路徑/參數

**不准改的檔案**：
- `object_perception/`、`interaction_executive/`、`pawai_brain/`、`pawai_contracts/`（未建）、`pawai-studio/` 的任何 runtime code
- 任何 launch / yaml / contract 文件
- 不在 Jetson 上裝任何東西；WSL 用獨立 venv（`uv venv && uv pip install supervision`）

**驗收標準**：
1. WSL venv 安裝成功，`python -c "import supervision; print(supervision.__version__)"` 過，PawAI repo `git status` 乾淨。
2. 對同一段 cup 錄影輸出 evidence MP4：bbox + zh-TW label（RichLabelAnnotator + 系統 TTF）+ track ID 穩定可見。
3. 量化報告一份：raw 偵測（threshold 0.5）vs「降 threshold 至 0.3 + `minimum_consecutive_frames=3` 過濾」的 (a) cup 首次偵測距離幀號 (b) 假陽性事件數 (c) track 斷裂次數。**這組數字直接回答 §7a 的「後處理路線有沒有救」**。
4. JSONL 落盤含每幀偵測 + 可塞 custom key（驗證 decision_id join 可行性）。

**預估**：1 個下午。失敗條件（任一成立則降級 NO_GO for runtime、維持 offline-only）：ByteTrack 在 6-8 Hz 低幀率下 track 斷裂嚴重（ByteTrack 假設較高幀率的 IOU 連續性）、或低 threshold + 時序過濾的假陽性壓不下來。

---

## 7. 三個指定問題

### (a) cup 0.7m 才看得到 → **不能直接解，有一條值得 spike 的間接路線**
- Supervision 不是模型，無法讓 YOLO26n 在 1.5m 看到本來看不到的 cup（✅2-1）。
- **間接路線 1（推薦 spike）**：現行 `confidence_threshold=0.5` 📍`object_perception_node.py:159` 是單幀硬切。改成「低 threshold（如 0.25-0.3）+ ByteTrack `minimum_consecutive_frames` 時序確認」可能把遠距離弱偵測撈回來、同時不增加誤報——這是 ByteTrack 兩階段匹配的設計用途（低信心偵測維持既有 track）。成本：零模型改動。§6 spike 直接驗證這條。
- **間接路線 2（NEEDS_BENCHMARK）**：`InferenceSlicer` 切片推理對小物件有效 📍`inference_slicer.py:64-95`，但 Jetson 上推理次數 ×N，現況 6-8 Hz 撐不撐得住未知，只能先 WSL 離線對錄影驗證「切片後遠距 cup 召回率提升多少」，值得才上 Jetson 量。
- 誠實結論：如果 0.7m 的根因是 cup 在輸入解析度下像素太少，真正的解在輸入解析度/模型側；supervision 只能在「模型偶爾看得到」的前提下把偶爾變穩定。

### (b) gesture 誤觸 → **基本幫不上**
- `from_mediapipe` 只接 pose/face landmarks，**不支援 hand landmarks / Gesture Recognizer** 📍`key_points/core.py:539-542`——連資料都進不去。
- 即使硬把手部 bbox 包成 Detections，`DetectionsSmoother` 平滑的是 `xyxy` + `confidence`（且硬依賴 `tracker_id`，沒有就整批跳過 📍`smoother.py:105-107`）——**它不平滑 class label**，而 gesture 誤觸是「thumbs_up ↔ ok 翻動」的分類層問題。
- 正解仍是 PawAI 既有的 N-frame debounce / cooldown 邏輯（WaveDetector、`gesture_every_n_ticks` 那一層）。supervision 的貢獻只剩 evidence：把誤觸當下的影格 + 偵測 log 落盤，讓人看得到「為什麼誤觸」。

### (c) Studio evidence 不足 → **最強對接點，建議採用**
- ✅3-0 確認 annotators 是「看不懂機器為什麼反應」最直接的對接。
- 具體鏈路見 §4 Studio Evidence Center：trace 的 `decision_id` join 偵測 JSONL join 影格 → annotators 重建標註圖 → VideoSink 出 clip。`RichLabelAnnotator` 順帶解掉 zh-TW label 的 PIL 手刻繞路（offline 版先行，runtime 版另案）。
- `ComparisonAnnotator` 📍`annotators/core.py:3000` 額外紅利：調參前後（如 threshold 0.5 vs 0.3+tracker）同幀對比圖，直接貼進 scoreboard 報告。

---

## 8. 最終 Verdict：**GO_ADOPT_FOR_EVIDENCE**

| 用途 | 裁決 |
|------|------|
| Offline evidence 工具鏈（WSL：annotators + sinks + video utils → Studio Evidence Center 資料層） | **GO_ADOPT_FOR_EVIDENCE** |
| Offline 評估（dataset + mAP/ConfusionMatrix → capability scoreboard） | **GO_ADOPT_FOR_EVIDENCE** |
| ByteTrack 低threshold+時序確認解 object 閃爍（先離線對錄影） | **GO_SPIKE_ONLY**（§6，一個下午） |
| InferenceSlicer 解遠距小物件 | **NEEDS_BENCHMARK**（離線先量召回率，Jetson 後量 Hz） |
| 進 Jetson runtime（任何形式） | 暫緩——等 spike + benchmark 數據，且優先考慮 vendor `byte_tracker/` 而非整包安裝 |
| gesture / speech | **NO_GO**（無對接面） |

單一強制裁決取 **GO_ADOPT_FOR_EVIDENCE**：因為即使兩個 spike 全失敗，evidence + evaluation 的價值已獨立成立，且與 Plan E → Studio Evidence Center 的既定路線零衝突、零 runtime 風險。

---

## 附錄：來源清單

**本地 source 查證**（clone `b8ebc14`，2026-06-10）：
`pyproject.toml`、`src/supervision/detection/core.py`、`detection/tools/{smoother,polygon_zone,inference_slicer,csv_sink,json_sink}.py`、`detection/line_zone.py`、`tracker/byte_tracker/core.py`、`key_points/{core,annotators}.py`、`annotators/core.py`、`metrics/`、`dataset/core.py`、`utils/video.py`

**Workflow 3 票對抗驗證通過（✅）**：
- [github.com/roboflow/supervision](https://github.com/roboflow/supervision)（README：model-agnostic、annotators）
- [supervision.roboflow.com/latest/detection/core](https://supervision.roboflow.com/latest/detection/core/)（Detections 定位、from_* 清單）
- [roboflow.github.io/cheatsheet-supervision](https://roboflow.github.io/cheatsheet-supervision/)（功能範圍）

**Workflow 抓取但未完成對抗驗證、已由本地 source 補證**：
- [supervision.roboflow.com/detection/tools/smoother](https://supervision.roboflow.com/detection/tools/smoother/) → 📍smoother.py:105-107 證實
- [github.com/roboflow/supervision/issues/1044](https://github.com/roboflow/supervision/issues/1044)（minimum_consecutive_frames）→ 📍byte_tracker/core.py:50-70 證實
- [supervision.roboflow.com/0.27.0/detection/tools/polygon_zone](https://supervision.roboflow.com/0.27.0/detection/tools/polygon_zone/) → 📍polygon_zone.py:18-97 證實
- [github.com/roboflow/supervision/pull/180](https://github.com/roboflow/supervision/pull/180)（headless 提案）→ 📍pyproject.toml:54 證實**現行已是完整版 opencv-python**（headless 方案不在現行依賴中）

**PawAI 對照檔案**：
`object_perception/object_perception/object_perception_node.py`、`docs/archive/superpowers-legacy/plans/2026-06-10-plan-{c,d,e}-*.md`
