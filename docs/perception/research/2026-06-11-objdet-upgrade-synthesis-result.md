# Synthesis Result: object detection 升級總裁決 + 單一上機測試日清單 v1

> **日期**：2026-06-11
> **對應 goal**：`docs/perception/research/goals/2026-06-11-objdet-upgrade-synthesis-goal.md`
> **Synthesis Verdict**：**BLOCKED_BY_HARDWARE_TEST**（清單 v1 完成（§4）；兩條 GO 線與兩條 NEEDS_TEST 線全部收斂到「WSL 前置週 + 一個上機測試日」即可裁定，無不可調和矛盾）
> **本 synthesis 為 read-only 收斂**：未改四份 input results、未改 code、未 commit。本檔是唯一寫入物。
> **Input 完整性**：四份 deepdive results 全部存在且 verdict slot 已填（無缺檔）。既排定 spike 的完成度查證：`benchmarks/scripts/` 下無 `supervision_evidence_spike.py` / `color_naming_spike.py` / sitting A/B 產物，`docs/perception/research/` 亦無 spike 結果檔 ⟹ **supervision ByteTrack spike 與 478_SC 離線對照均未完成**，本清單將其編入前置週（§4a），不引用不存在的結果。

---

## TL;DR

1. **四份 verdict 可以共存，無 INCONSISTENT**：goal 1（GO_BENCH_MATRIX）拿走上機日主時段；goal 3（GO_LAB_NEAREST_NAME）的 54 格驗收矩陣排同日下午（共用相機與場地，bag 錄了離線可重算）；goal 2（NEEDS_TEST_VOCAB_REPLAY）與 goal 4（NEEDS_TEST_HITL_CLIPS）的裁定點都在 WSL 離線——goal 2 過門檻才掛上機日的條件配置 E，goal 4 本輪明確不佔上機名額。
2. **三個真矛盾，全部已裁**：① effective conf 基線——goal 2 與 supervision 報告寫 0.5，goal 1 查實 launch/yaml 已是 **0.35**（b1f5058），一切量測設計以 0.35 為基線；② PINTO §5a「第一刀 = n@1280 re-export」被 goal 1 推翻（s@640 優先、1280 由 960+720p 真像素取代），該節 superseded；③ goal 1「seg 出局」vs goal 2 唯一候選全是 `-seg` 權重——適用範圍不同（det 任務的 seg 變體出局；YOLOE 無純 det 權重屬供給側被迫、mask 棄用），實質相容但 E 配置門檻必須保留 Hz check。
3. **一個量測口徑分歧必須上機裁定**：同級配置的 RAM 估算，goal 1（activation 全包口徑）估 s@960 = +300~600MB，goal 2（engine 邊際口徑）估 YOLOE-26s-seg@960 = +100-150MB——差 3-4 倍。上機日每配置 `tegrastats` 前後對照是唯一仲裁。
4. **上機日總長 = 全天**（無 E、無 stretch 約 4.5h；含 E + 色彩選配格約 6h + buffer）。**TRT engine 必須前一晚預燒**（3 顆 det 引擎 30-45 分鐘 + 條件性 YOLOE 1-2 顆；1GB workspace 峰值不可與 demo stack 同跑）。
5. **下游同步鏈相撞點要先指定 owner**：goal 2（+22 類）與 goal 3（12→19 色名）各自附帶 contract / `zh_tables.py` / Studio TS / parity test 同步工單——兩條都過門檻時應合併成**一次** contract bump（v2.5→v2.6），不要分兩次動。

---

## §1 四份 input 的 verdict 與承重 findings

| Goal | Verdict（已填） | 承重 top 3 findings |
|------|----------------|---------------------|
| **1. yolo26-scaleup-highres-seg** | `GO_BENCH_MATRIX`（≤4 配置矩陣 A→B→C→D） | ① s@640 才是第一刀：n@1280 與 s@640 GFLOPs 等值（21.6 vs 20.7）但官方 +7.7 mAP 證據一面倒向 s，且現役相機 640x480 使 n@1280 退化為插值（F24/F2/F30）；② 6-8Hz 不是模型瓶頸：官方 Orin Nano Super YOLO26n TRT FP16 純推理 4.57ms，Hz 由 Python 前後處理主導，換 s 級衝擊次線性（F14/F26）；③ seg 變體純虧損：box mAP -1.3、GFLOPs +65%、CPU mask 後處理 → 出局（F4/F5） |
| **2. open-vocab-indoor-classes** | `NEEDS_TEST_VOCAB_REPLAY` | ① 路線收斂到單一候選 YOLOE-26 custom-vocab set-then-export（同 YOLO26 架構、export 後零 text-encoder 成本；YOLO-World 被 +10~11.4 AP 壓制、GDINO 級跑不動/拿不到、closed-set 無獨立供給）；② 精度證據不足以 GO：S 尺寸 LVIS-rare AP ~22、藥瓶連 LVIS 1203 都沒有、cup 都只有 0.7m 穩 → 必須先 WSL replay；③ 前提修正：remote/bowl/餐具本來就在 COCO 80，真類別缺口 = 22 類 |
| **3. color-recognition-upgrade** | `GO_LAB_NEAREST_NAME`（方案 A + 中央 50% 取樣 + 事件級平滑 + demo AWB lock 選配） | ① 根因排序 ③12 色粒度（確定）≥ ①bbox 背景污染（高）> ②光照（中）；② 方案 A 全管線實測 0.190ms/bbox（WSL，附可重跑腳本），與現役 HSV 同價、Jetson 外推 ≤1ms；③ 色名表選自訂 zh-native 19 名 +1 保留位（TTS 中文輸出鏈是硬需求），k-means/seg-mask/gray-world/tiny-classifier 全出局 |
| **4. yolo-pose-gesture** | `NEEDS_TEST_HITL_CLIPS` | ① classifier 輸入本來就是 COCO 17 kpt、z 軸從未被使用 → 結構性改寫成本 ≈0，真成本在 score 語意重校（F11-F19）；② 手勢 YOLO 路線確認死路：官方無 hand 預訓練模型、社區品全是 MediaPipe 蒸餾 + NC/AGPL 授權鏈 → 靜態手勢不可替代，整併上限「一顆換一顆半」；③ 唯一裁不了的（Go2 視角 sitting 品質）離線免費可測，**本輪不佔上機名額**（上機日讓給 object 矩陣） |

對照之既有結論：**PINTO 報告** = ADOPT_AS_CANDIDATE_SOURCE（cup 此 zoo 無解；478_SC 是最高 ROI 候選；bbalg 防翻動配方免費）；**supervision 報告** = GO_ADOPT_FOR_EVIDENCE（ByteTrack spike GO_SPIKE_ONLY、InferenceSlicer NEEDS_BENCHMARK、runtime 暫緩）。

---

## §2 Contradiction Matrix

> 凡例：✅ 一致／互補；⚠️ 表面矛盾，已裁定；❌ 真矛盾，需動作（本表無未解 ❌——全部附裁定）。

| # | 耦合點 | 兩造主張 | 裁定 | 對清單的影響 |
|---|--------|----------|------|--------------|
| 1 | **goal 1 勝出配置 × goal 2 模型尺寸公平性** | goal 1 矩陣排序 control→s@640→n@960→s@960（勝者未定，待上機）；goal 2 要求 replay 與 goal 1 勝出配置同 imgsz 同尺寸出數字 | ✅ **附對齊條件**：goal 2 replay 必須同時出 n（現役對齊）與 s（goal 1 主力刀對齊）兩組數字；條件配置 E 的 imgsz 鎖定 goal 1 上機日勝者（勝者未出前先 export 640 與 960 兩版備用） | E 配置 export 兩版 ONNX；E 排在 A-D 之後執行 |
| 2 | **goal 1「seg 出局」× goal 2 唯一候選全是 `-seg` 權重** | goal 1：YOLO26s-seg box mAP -1.3、GFLOPs +65% → 剔除；goal 2：Ultralytics 全部 YOLOE 權重（含 YOLOE-26）任務欄都是 Instance Segmentation，無純 det 權重 | ⚠️ **適用範圍不同，實質相容**：goal 1 裁的是「用 seg 變體解 cup recall」；goal 2 用 seg 權重是供給側被迫，mask 係數/proto 棄用（parse 改一行切片 `[:, :6]`、CPU 零額外成本）。但 det→seg 的 ~×1.6 GFLOPs 代價真實存在（goal 2 §9 已計入）⟹ 「seg 出局」表述精確化為「**det 任務的 seg 變體出局；YOLOE-seg 屬例外（無 det 權重可選），mask 棄用**」 | E 配置 pass 門檻保留「偵測迴圈 ≥3Hz」check，不可因「mask 沒用到」跳過 Hz 驗證 |
| 3 | **goal 1 seg 裁決 × goal 3 方案 D（GO_SEG_MASK_COLOR 路線）** | goal 3 **沒有**選 GO_SEG_MASK_COLOR——明文跟隨 goal 1 裁決把 D 封死，選 GO_LAB_NEAREST_NAME | ✅ 一致。**Synthesis 新增條件路徑**：若 E 配置（YOLOE-seg）上線，proto tensor 隨車附贈 → goal 3 預留的「seg 上線後 A 的查表直接套 mask 內像素」升級條款被動觸發。注意 mask 合成是 CPU 後處理（每 instance 係數×proto+sigmoid+resize），**不是零成本**，啟用前要量 CPU | 不改本輪清單；列入 §5 未解問題 #3 |
| 4 | **goal 4 整併算盤 × goal 1 GPU/RAM 預算** | 兩線都想吃 GPU 增量（goal 1 矩陣 B-D +100~600MB；goal 4 pose +200-400MB 獨立 node） | ✅ **goal 4 自行讓位解除衝突**：本輪上機不排 pose（「用最貴的資源回答最便宜的問題」），先 WSL 離線 3-way sitting A/B；GPU 占空比紙面合計 <25% 不是本輪瓶頸。pose 晉級後才需處理 RAM 疊加與 L3 重測 | pose 不進上機日清單；3-way A/B 編入前置週 W5 |
| 5 | **effective conf 基線：0.35 vs 0.5** | goal 1 F35（audited）：launch `:39` default 0.35 + yaml 0.35，node `:159` 的 0.5 只是 declared default 已被 override（b1f5058）；goal 2 finding 10 與 supervision 報告 §6/§7a 仍寫「現役 0.5」 | ⚠️ **真矛盾，裁定 0.35 為準**（goal 1 對 launch/yaml/坑 #9 的查證最完整）。goal 2 的「0.5 對 zero-shot rare 類過高」論點不受影響（0.35 對 rare 類仍偏高，replay 照樣 sweep 0.25-0.35）；supervision spike 的 baseline 從「0.5 vs 0.3」改為「**0.35 vs 0.30**」（採 goal 1 §4.2 建議 (a)：0.5 已非現役配置，重量它沒有 demo 意義） | W4 spike 協議改基線；上機日 A0=0.35 / A1=0.30 維持 goal 1 原設計 |
| 6 | **PINTO 報告 §5a「第一刀 = n@1280 re-export」× goal 1 矩陣排序** | PINTO：WSL re-export imgsz=1280 是 cup 的正解第一刀；goal 1：三點推翻——GFLOPs 等值但證據懸殊、現役相機 640x480 使 1280 成插值自欺、repo 6/10 內定候選是 960 非 1280 | ⚠️ **採 goal 1，PINTO §5a 該節 superseded**。「不換 zoo 模型、incumbent 路線內解決」的大方向兩報告一致，只是第一刀從「n 升解析」改為「升 s」、高解析線由 n@960+720p 真像素承接 | 矩陣 C 用 n@960+720p；1280 不進清單 |
| 7 | **L3「GPU 0%」基石 × 四線** | L3 三感知壓測 = face+pose+gesture 全 CPU、GPU 0%；goal 1 矩陣與 E 配置都只動 object（object 本來就在 GPU，不在 L3 三感知範圍）；goal 4 一旦晉級 = 基石正式作廢 | ✅ **本輪不觸動基石**。唯一推翻路徑是 pose 晉級，屆時按 goal 4 Q8 清單做等價重測（face CPU + recognizer CPU + YOLO-pose GPU + object GPU + Whisper burst ≥60s） | 不影響本清單；L3 重測列 §5 未解問題 #4 |
| 8 | **supervision ByteTrack spike × goal 1 A1 control 的分工** | 兩線都量「低 conf + 時序」 | ✅ **互補無重疊**（goal 1 F42 已劃界）：上機矩陣量「配置×距離×recall/Hz/RAM」（on-device），supervision spike 量「FP 抑制 + track 連續性」（offline 對錄影）。基線對齊後（#5），A1 上機數據可直接餵 spike 當配對 ground truth | W4 與上機日 A 段資料互餵；不重複量測 |
| 9 | **goal 2 類別擴充 × goal 3 色名擴表（下游同步鏈相撞）** | 兩條 verdict 各自附帶同一條同步鏈：contract 文件（goal 2 = 描述文字「COCO 80」；goal 3 = color enum 12 值 bump）+ `pawai_contracts/zh_tables.py` + Studio `object-config.ts` + parity test | ⚠️ **非矛盾，是工程相撞**：兩條都過門檻時若分兩次 bump contract = 兩次 `pawai contract check` 鏈動員 + 兩次靜默漂移風險。裁定：**合併為一次 v2.5→v2.6 bump**，在兩條驗收都出結果後執行 | 列 §6 next steps；上機日不動 contract |
| 10 | **goal 1 C/D 動相機（720p）× goal 3 色彩矩陣 / face pipeline** | C/D 配置改 `rgb_camera.color_profile:=1280x720x30`；goal 3 的 54 格矩陣與 AWB lock SOP 也動相機參數；face_identity_node 共用同一 color topic（CPU ×2.25 像素） | ✅ **排程隔離解決**：色彩矩陣 F 段固定在 A0 基線配置（640x480、AUTO AWB 起步）錄 bag，保證與現役可比；C/D 段同跑 face node 記 CPU 漲幅（goal 1 F37）；若 C/D 勝出，色彩補拍 720p 對照格列 stretch | F 段排在 A-D 之後、用基線配置；AWB 掃描只在黃燈格做 |
| 11 | **PINTO 478_SC × goal 4 sitting 三訊號源** | PINTO：SC 是最高 ROI、建議 ensemble；goal 4：三選二正解 =「一條幾何 + SC」，幾何內戰（MediaPipe vs YOLO-pose）離線裁，不開三線 | ✅ 完全互補：goal 4 的 W5 離線實驗一次餵三方（MediaPipe / YOLO-pose / 478_SC），同時回答幾何內戰與 SC 的 Go2 視角 domain 疑慮 | W5 一個實驗收兩個答案 |
| 12 | **RAM 估算口徑：goal 1 vs goal 2** | goal 1 對 s@960 估 **+300~600MB**（FP16 權重 + activation/buffer ∝ 像素×通道 + TRT context 全包口徑）；goal 2 對 YOLOE-26s-seg@960 估 **+100-150MB**（engine 邊際口徑） | ⚠️ **同級配置差 3-4 倍，紙面不可裁**——兩者假設體系不同（goal 1 含 activation 放大、goal 2 只算 engine 級邊際）。裁定：以 goal 1 的保守估算排程（D 配置 RAM 先量再跑），上機 `tegrastats` 實測為唯一仲裁 | D 與 E 配置都掛「RAM 先量再跑、違反 0.8GB 即棄測」規則 |

---

## §3 Unified Decision Table（一列一個 sub-bottleneck）

| Sub-bottleneck | Supporting deepdive(s) | Verdict | Confidence | Next action |
|----------------|------------------------|---------|------------|-------------|
| **cup 遠距（>0.7m 看不到）** | goal 1（主）；supervision §7a（control arm 機制）；PINTO §5a（superseded 方向） | `GO_BENCH_MATRIX`：A（n@640 + conf0.30 control）→ B（s@640 主力刀）→ C（n@960+720p）→ D（s@960+720p，RAM 最危） | **高**（官方家族規格 + 官方 Jetson n 錨點 + 兩獨立 s 級社區錨點；recall@distance 實際增益必須上機量） | W1 WSL export 3 ONNX + 預燒 → 上機日 T1-T4 |
| **類別缺口（22 個非 COCO 居家類）** | goal 2（主）；PINTO §4b（guardian 屬性級替代 472_DEIMv2） | `NEEDS_TEST_VOCAB_REPLAY`：YOLOE-26 custom-vocab 唯一候選；closed-set / transformer 全出局 | **機制高、精度低**（rare AP ~22 proxy、藥瓶零紙面證據） | W2 WSL vocab replay（38 類 v0 + 混淆矩陣 + cup 不退化）→ 過門檻掛上機日條件配置 E |
| **顏色（12 色不夠 + 不準）** | goal 3（主）；supervision F21（平滑不可外包）；goal 1 F12（seg proto 解析度） | `GO_LAB_NEAREST_NAME`：Lab+CIEDE2000 LUT（19+1 zh 色名）+ 中央 50% 取樣 + 事件級 3 次多數決 + demo AWB lock SOP | **高**（根因診斷 + 內嵌可重跑微基準 0.190ms/bbox）；最終驗收靠 54 格矩陣（含 HSV12 falsification） | W3 WSL spike script → 上機日 T6 錄 54 格 bag（離線兩法同算）→ per-color ≥0.8 過門檻才進 node 實作 + contract bump |
| **pose / 手勢（sitting 不穩、誤觸）** | goal 4（主）；PINTO §4.1/§5b（478_SC + bbalg 配方） | `NEEDS_TEST_HITL_CLIPS`：手勢 YOLO 路線**死**（維持 MediaPipe + bbalg）；pose 幾何內戰離線裁，**本輪不佔上機** | **手勢出局：高**（官方無模型 + 蒸餾天花板 + NC/AGPL）；**pose 增益：未知**（離線可裁） | W5 WSL 3-way sitting A/B（MediaPipe vs YOLO26n-pose vs 478_SC）；晉級 gate = +10pp 或救回 ≥30% 漏偵幀 → 下下次上機 |
| **輪廓 / seg** | goal 1（det 任務裁決）+ goal 3（顏色 ROI）+ goal 2（YOLOE-seg 例外） | **det 任務 seg 出局**；mask 唯一合法再入口 = E 配置（YOLOE-seg）副產品，且 mask 啟用須另量 CPU | **高** | 無獨立動作；條件路徑掛 §2 #3 |
| **誤觸 / 閃爍（時序穩定化）**（補充列） | supervision §6（spike 協議）+ goal 1 F39（0 GFLOPs control） | `GO_SPIKE_ONLY`（offline ByteTrack `minimum_consecutive_frames=3`）；baseline 對齊 0.35 | **中**（BYTE 機制證據強、無距離-recall 直接數字） | W4 WSL spike（與 W2 共用錄影素材）；runtime 化等 spike + 上機 A1 數據 |

---

## §4 上機測試日清單 v1（核心交付）

### §4a 前置週 WSL 清單（上機日之前完成；W1 為上機日硬前置，W2 決定 E 配置存廢，W3-W5 可全平行）

| # | 項目 | 內容（WSL 前置動作） | 產出 / 門檻 | 預估時間 | 平行性 |
|---|------|---------------------|-------------|----------|--------|
| **W1** | object 矩陣 export + sanity（goal 1 §5 清單 1-4） | `uv venv && uv pip install ultralytics onnxruntime`（禁令只限 Jetson）；export 3 顆 fixed-shape e2e ONNX：`yolo26s_640.onnx` / `yolo26n_960.onnx` / `yolo26s_960.onnx`；ORT CPU 對 6/9 S3 錄影抽幀 sanity（shape `(1,300,6)`、近距 cup 有偵測、座標域正確）；`rsync` 到 `/home/jetson/models/`（走 audited deploy） | 3 顆 ONNX 落 Jetson + sanity 全過；可選加碼：整段 S3 離線 4 配置 recall 預排序 | **半天** | 與 W2-W5 平行 |
| **W2** | YOLOE vocab replay（goal 2 §12） | 下載 `yoloe-26s-seg.pt` + `yoloe-26n-seg.pt`；`set_classes`（v0 38 條目）後直接 predict 跑自拍照（藥瓶/鑰匙串/眼鏡/遙控器/容器混淆組/拖鞋/毛巾/拐杖 × 0.5/1.0/1.5m，D435 視角高度 ~30cm）+ demo 錄影重放；藥瓶 prompt A/B（"pill bottle"/"medicine bottle"/"prescription bottle"）；conf sweep 0.25-0.35；驗證 export ONNX 輸出 shape（推定 `(1,300,38)+(1,32,160,160)` 同型，未實證） | 三表：per-class recall×距離、容器混淆矩陣、cup 基線對齊。**門檻：demo 核心組新類 1.0m recall ≥0.5 ∧ 容器混淆 <30% ∧ cup 退步 <5pp** → 過 = export 640+960 兩版 ONNX、上機日掛配置 E；不過 = 縮 vocab 重測一輪，再不過 `NO_GO_STAY_COCO80` | **一個下午 + 半天拍照** | 拍照素材可與 W4 共用 |
| **W3** | 色彩 spike script（goal 3 §7） | 寫 `benchmarks/scripts/color_naming_spike.py`：讀 demo 錄影幀，同畫面並排輸出「現役 `analyze_bbox_color` vs Lab-LUT（§5 v0 表）×（整 bbox / 中央 50%）」四組色名+純度；驗 v0 錨點邊界合理性 | spike 腳本入 repo + 桌面驗證通過（紅杯不再 red↔pink 翻動為主要 sanity） | **半天** | 完全獨立 |
| **W4** | supervision ByteTrack spike（supervision §6，**基線改 0.35**） | WSL venv `uv pip install supervision`；讀 cup 錄影 + `/event/object_detected` JSONL → `sv.Detections` → `ByteTrack(minimum_consecutive_frames=3)` → annotate → evidence MP4 + JSONL | 量化報告：baseline **conf 0.35** vs「0.30 + N=3 時序過濾」的首偵測幀號 / 假陽性數 / track 斷裂次數（6-8Hz 低幀率下 ByteTrack IOU 連續性是失敗條件） | **一個下午** | 與 W2 共用錄影；資料層與上機 A 段互餵 |
| **W5** | pose 3-way sitting A/B（goal 4 §5；含 478_SC 離線對照——**未完成，編入**） | `uv pip install ultralytics onnxruntime mediapipe`；export `yolo26n-pose.onnx`（驗 shape 推定 `(1,300,57)`）；對 6/9-6/10 demo 錄影（S2 坐姿段）逐幀跑三方：MediaPipe（現役 33→17）/ YOLO26n-pose（conf<門檻 kpt 歸零 + min_score sweep 0.1-0.3）/ 478_SC（person crop 來源 = YOLO-pose bbox）；全餵 `classify_pose`（two_class、`sitting_trunk_max_deg=45`） | 逐幀對照表：sitting 正確率（人工 GT）、漏偵幀、分歧分佈。**晉級 gate：YOLO-pose ≥ MediaPipe +10pp 或救回 ≥30% 漏偵幀**（晉級者排**下下次**上機，本上機日不排） | **一個下午** | 完全獨立；不 block 上機日 |
| **W6** | **前一晚 Jetson 預燒 TRT engine**（goal 1 §5 清單 5） | Jetson 上**不開 full demo stack**，逐一 `OBJECT_MODEL=... OBJECT_INPUT_SIZE=... ros2 launch object_perception object_perception.launch.py` 讓 TRT cache 落 `trt_cache/<stem>/`：`s_640` → `n_960` → `s_960` →（W2 過門檻才有）`yoloe26s_vocab38_640` / `_960`；每顆燒完跑近距 cup（或 vocab 物件）sanity——**F16 AGX mAP 0.045 異常 + Hackster drift 前科 ⟹ 每顆 engine 必過已知場景 sanity 才算燒好** | 3-5 顆 engine cache 就緒 + sanity 紀錄。**紀律：1GB TRT workspace 峰值，預燒期間不得同跑 demo stack** | **每顆 3-15 分鐘；3 顆 ~30-45 分、5 顆 ~50-75 分**（首次 build 口徑） | 序列執行（同一 GPU） |

### §4b 上機測試日時程（單日；依賴排序 = engine 已預燒 → 不動相機的先跑 → 動相機的後跑 → 色彩 bag 壓軸）

> 全配置共同量測方法：recall 沿用 `capture_baseline_round.py percep` 並隔離 gesture topic（`--gesture-topic /__no_gesture__`，6/4 坑）；Hz = node debug overlay FPS 字串 + `ros2 topic hz`；RAM = `tegrastats` 前後對照；conf 非 runtime param，A0→A1 必須 kill 重啟 node。

| 時段 | 項目 | 配置 | 前置（已於 W1/W6 完成者標 ✓） | Jetson 上量什麼 | pass-fail 門檻 | 預估時間 |
|------|------|------|------|------|------|------|
| **T0** | 開場鎖定 | — | `sudo bash benchmarks/scripts/prepare_env.sh`（nvpmodel + jetson_clocks）+ **記錄當前 power mode**（若非 Super MAXN，全部 FPS 預估 ÷1.4-1.7，門檻不變但解讀要標）；`source scripts/device_detect.sh`；確認 5 顆 engine cache 在位 | power mode、初始 RAM 基線（tegrastats） | n/a（紀錄性） | **15 分** |
| **T1** | 矩陣 A：基線 + control | n@640 現役模型；A0=conf 0.35 → kill 重啟 → A1=conf 0.30 | 無新檔（現役模型）✓ | cup recall @1.0/1.5/2.0m 各 30s 靜置（@3Hz ≈90 幀樣本）；A1 對 A0 的 recall 增益；Hz；RAM 基線 | 紀錄性基線；**若 A1 已讓 cup@1.5m ≥80% → B-D 降級為驗證性質** | **40 分**（含 1 次重啟） |
| **T2** | 矩陣 B：主力刀 | **s@640**（`OBJECT_MODEL=yolo26s_640.onnx`，相機不動） | W1 export ✓ + W6 預燒 ✓ | 同 T1 三距離 recall + Hz + full-stack RAM + 近距 7 類 sanity | ① cup@1.5m recall **≥80%**（@2.0m ≥50% stretch）② 偵測迴圈 **≥3Hz** ③ full-stack RAM 餘 **≥0.8GB** ④ 近距 7 類 sanity 不退化 | **30 分** |
| **T3** | 矩陣 C：高解析 | **n@960 + 相機 1280x720x30**（`rgb_camera.color_profile` 一行改） | W1 export ✓ + W6 預燒 ✓；改相機 profile + 重啟 camera/face/object | 同 T2 + **face node CPU 漲幅紀錄**（共用 color topic，像素 ×2.25） | 同 T2 四門檻 + face CPU 漲幅記錄（紀錄性，不設 fail 線） | **35 分**（含相機切換） |
| **T4** | 矩陣 D：壓軸試探 | **s@960 + 720p**（RAM 最危配置） | W1 export ✓ + W6 預燒 ✓ | **RAM 先量再跑**：tegrastats 確認 delta；通過才跑三距離 recall + Hz | 同 T2 四門檻；**RAM delta 違反 0.8GB 即棄測**（goal 1 估 +300~600MB vs goal 2 口徑 +100-150MB——本段同時仲裁 §2 #12 口徑分歧） | **30 分**（棄測則 10 分） |
| **T5** | 條件配置 E（W2 過門檻才執行） | **YOLOE-26s-seg vocab38** @ goal 1 勝者 imgsz（640 或 960；E 是 seg 形態輸出，parse 切片 `[:, :6]` 已於 W2 驗過 shape） | W2 export ✓ + W6 預燒 ✓；node 類別表臨時換 vocab 對應表（測試 branch，不進 main） | vocab 命中 smoke：藥瓶/鑰匙/眼鏡 @0.5/1.0m；容器混淆組同框；cup 對照；Hz；RAM | ① 新類 1.0m 現場 recall 與 W2 replay 數字同向（無系統性崩跌）② cup 不退化 ③ **≥3Hz**（seg 形態 ×1.6 GFLOPs 的 Hz check，§2 #2）④ RAM 餘 ≥0.8GB | **30 分**（W2 不過則跳過） |
| **T6** | 色彩 54 格 bag 矩陣（goal 3 Q9） | **回 A0 基線配置**（n@640、conf 0.35、相機 640x480、AWB AUTO）——保證與現役可比、bag 離線可重算任何演算法 | W3 spike 通過 ✓；6 必備物件（紅/藍/白/黑杯、綠碗、米色碗）+ 3 選配（黃杯/咖啡馬克杯/粉紅杯）就位；三光照可控（窗光/黃燈/關主燈） | 每格 `ros2 bag record /camera/.../color/image_raw /event/object_detected` ≥60s（≥10 事件樣本）；**必備 36 格**（6 物 × 3 光照 × 2 距離 0.7/1.5m）；黃燈格加跑 **AWB lock 掃描**（白紙 3000→5500 step 100-200 取 S 最低）+ lock 對照格；選配 18 格 = stretch | 離線判定（兩法同 bag 重算）：per-color accuracy **≥0.8/色**（新色名首輪 ≥0.6 stretch）、Unknown 率、翻動率；**falsification：HSV12+AWB lock 已全 ≥0.8 → 改判 NO_GO_KEEP_HSV12** | **必備 36 格 ~90 分 + AWB 掃描 ~20 分；選配 +40 分** |
| **T7** | 收尾 | — | — | 矩陣勝者宣告（按 T1-T5 gate）；RAM/GPU 總表回填實測值；勝出配置寫回 launch env 候選註解（文件，不 commit）；bag/CSV 歸檔 | n/a | **20 分** |

**總時長估算**：核心（T0-T4 + T6 必備 + T7）≈ **4.5-5h（大半天）**；含 T5 + T6 選配 ≈ **6h + 排障 buffer ⟹ 排全天**。
**可平行項**：T6 的物件/光照佈置可在 T2-T4 跑 recall 靜置 30s 窗時由第二人預備；其餘全序列（同一 Jetson + 同一相機）。
**順序依賴**：T1→T2 無相機改動先行；T3/T4 動相機集中在後（只切一次 720p）；T6 回 640x480 壓軸（一次切回）。相機 profile 共切換 2 次，已最小化。

### §4c RAM / GPU 預算總表（守 ≥0.8GB 紀律；全部輪跑、嚴禁多模型同跑）

> 口徑：delta 相對「現役 n@640 full demo stack」基線；估算出處 goal 1 F27/Q6、goal 2 §9、goal 4 F32-F33；**全部需 tegrastats 實測回填**。

| 配置 | 預估 RAM delta | GPU engine 佔用估 | 0.8GB 紀律判定 | 排程處置 |
|------|---------------|-------------------|----------------|----------|
| A：n@640（基線） | 0 | ~4-13%（8Hz × 5-16ms） | PASS（現況成立） | 直接跑 |
| B：s@640 | +100~250MB | ~6-15% | PASS 預期 | 直接跑 |
| C：n@960 + 720p | +100~200MB（+RealSense/face CPU 漲幅另計） | ~8-12% | PASS 預期 | 直接跑，記 face CPU |
| D：s@960 + 720p | **+300~600MB（goal 1 口徑）/ +100-150MB（goal 2 口徑）** | ~10-20% | **邊緣——口徑分歧待裁（§2 #12）** | **RAM 先量再跑，違反即棄測** |
| E：YOLOE-26s-seg vocab38 | @640 +50-80MB / @960 +100-150MB（goal 2 口徑；保守按 goal 1 口徑看齊 D） | det×1.6 GFLOPs 形態 | 邊緣（@960 時） | 同 D 規則 |
| （參考）YOLO26n-pose 晉級後 | +200-400MB 獨立 node / +50-150MB 併 process | +5-8% 佔空比 | 本輪不排 | 下下次上機 + L3 等價重測 |
| **同跑紀律** | 任一時刻 GPU 上只有**一顆** object engine（`OBJECT_MODEL` env 輪換）；換配置 = kill node → 換 env → 重啟（engine 已預燒，啟動 ~秒級） | — | — | — |

### §4d TRT engine build 時間排程（全部移出上機日）

| Engine | Build 時間估（首次） | 排程 | 備註 |
|--------|---------------------|------|------|
| `yolo26s_640` | 3-15 分 | **前一晚 W6 第 1 顆** | 燒完近距 cup sanity |
| `yolo26n_960` | 3-15 分 | W6 第 2 顆 | fixed-shape：input_size 餵錯直接 fail（坑 #6） |
| `yolo26s_960` | 5-15 分 | W6 第 3 顆 | 最大顆，殿後 |
| `yoloe26s_vocab38_640` / `_960` | 各 5-15 分 | W6 第 4-5 顆（W2 過門檻才燒） | seg 形態雙輸出，sanity 用 vocab 物件 |
| **合計** | **3 顆 ~30-45 分；5 顆 ~50-75 分** | 前一晚一次完成；**期間不得同跑 demo stack（1GB workspace 峰值 OOM 風險）** | timing cache 未開（現役 code 不改），不指望跨 build 加速 |

---

## §5 未解的 cross-cutting 問題（無單一 deepdive 認領）

1. **nvpmodel power mode 未驗證**（goal 1 F22）：全部 FPS 預估錨在 Orin Nano Super MAXN；若實機在舊 15W 檔，預估 ÷1.4-1.7。T0 開場記錄是強制項，但「要不要為了 demo 常駐 Super 檔（功耗/XL4015 供電不穩前科）」沒人裁——供電線 8+ 次斷電紀錄在案，Super 檔功耗上升與 20V 安全極限的交互**需要電源側意見**。
2. **RAM 估算口徑分歧**（§2 #12）：goal 1 與 goal 2 對同級配置差 3-4 倍。T4/T5 實測可裁這一次，但「以後估 RAM 用哪個口徑」應在結果出來後寫成一條 benchmark 慣例（activation 全包 vs engine 邊際），否則下次研究又各說各話。
3. **E 配置 mask 副產品的顏色升級路徑**（§2 #3）：若 E 上線，goal 3 的方案 D 升級條款被動觸發，但 mask 合成的 per-instance CPU 成本（係數×proto+sigmoid+resize）沒人量過——啟用前需要一個 30 分鐘的微基準，目前無 owner。
4. **L3 等價重測的觸發管理**（§2 #7）：pose 晉級（W5 過 gate）後，L3「GPU 0%」基石作廢與重測清單（goal 4 Q8）誰排程、排在哪次上機，未定。
5. **contract bump 合併工單**（§2 #9）：色名 19+1 與 vocab 22 新類的同步鏈（contract v2.6 + zh_tables + Studio TS + parity test + `class_whitelist` 語意重文件化 + `test_object_perception.py:336-348` regex 測試改寫）——兩條 GO 後合併執行，但**新類別「誰消費、講什麼台詞」是 brain 編排問題**（goal 2 §7 標 scope 外），掛在 6/9 待辦 #4「PawAI Brain 流程編排深挖」，至今無 plan。
6. **色彩矩陣與 720p 的組合格**（§2 #10）：T6 固定在 640x480 基線拍；若 C/D 勝出成為新主線，色彩驗收嚴格說要在 720p 下重確認（resize 到 64×64 後演算法成本不變，但 bbox 內容物比例與 AWB 行為可能變）——列 stretch，無人 own。
7. **goal 2 拍照素材的代表性**：自拍照（WSL replay 用）與 Go2 實機視角（D435 高度 ~30cm、可能晃動）之間的 domain gap 只靠「遠端模擬慣例」背書；E 配置的現場 smoke 是第一次真驗證，若 replay 過了但 T5 崩跌，沒有預先定義的歸因流程（prompt 措辭？距離？視角？）。

---

## §6 Synthesis Verdict 與下一步

### Verdict: `BLOCKED_BY_HARDWARE_TEST`

五選一裁定理由：
- ~~READY_TO_COMMIT~~：沒有任何一條線的 code 改動已被數據授權——goal 3 雖是 GO，其 verdict 自帶「per-color ≥0.8 過門檻才進 node 實作與 contract bump」的上機閘。
- ~~READY_TO_ADR~~：方向性決策（s@640 優先、YOLOE 唯一候選、Lab-LUT、手勢路線死）都還押在實測門檻後面；ADR 在數據落地前是空文。唯一例外是「手勢 YOLO 路線出局」已可定案，但它是維持現狀（不動作），不需 ADR。
- ~~NEEDS_NEW_RESEARCH~~：紙面證據已到頂——四份 deepdive 共 160+ findings，剩下的全部是「沒人測過我們要的東西」，再搜也搜不出來。
- ~~INCONSISTENT~~：§2 的 12 個耦合點全部附裁定，三個真矛盾（conf 基線、PINTO 第一刀、seg 適用範圍）均已收斂，無需第二輪 grill。
- **BLOCKED_BY_HARDWARE_TEST ✅**：決策樹的每個分叉（矩陣勝者、E 存廢、色彩過門檻、pose 晉級）都指向同一個瓶頸——**§4 的前置週 + 一個上機測試日**。清單已完成，等上機。

### 建議的下一步動作（依序）

1. **立 3 張 ready-for-agent issues（WSL 前置週，本週完成）**：
   - `bench: YOLO26 scale-up matrix WSL prep — export s640/n960/s960 + S3 replay sanity`（W1，goal 1 原案）
   - `spike: YOLOE-26 vocab38 WSL replay — per-class recall × 距離 + 容器混淆矩陣 + cup 基線`（W2）
   - `spike: WSL offline 3-way sitting A/B — yolo26n-pose vs mediapipe vs 478_SC on demo clips`（W5，goal 4 原案）
   W3（color spike script）與 W4（supervision ByteTrack spike，**基線改 0.35**）可併入既有 perception 工作流或各立一張。
2. **排定上機測試日**（W1 完成 + W6 預燒後的第一個可上機時段），按 §4b T0-T7 執行；當日產出 = 矩陣勝者 + E 存廢 + 36 格色彩 bag。
3. **上機日後**：(a) 兩條 GO 線的 contract v2.5→v2.6 **合併 bump**（§5 #5）；(b) RAM 估算口徑慣例寫入 benchmark 制度（§5 #2）；(c) 屆時若「s 級 + open-vocab + 新色名表」三線全過，**那一刻才是 READY_TO_ADR**——主 object 模型從「COCO 80 closed-set n 級」遷移到「custom-vocab s 級」是 hard-to-reverse 決策，應補一張 ADR。

### 後續 test goal 的 `/goal` 草稿（不自動觸發，依 done criteria 附上）

```
/goal-research 上機測試日執行 goal：object 升級矩陣 + 色彩驗收矩陣（單日）

Context：synthesis（docs/perception/research/2026-06-11-objdet-upgrade-synthesis-result.md）
已裁定 BLOCKED_BY_HARDWARE_TEST，前置週 W1-W6 完成後執行本 goal。

Tasks：
1. 按 §4b T0-T7 時程執行；T0 必記 nvpmodel power mode 與 tegrastats 基線。
2. 矩陣 A-D（+條件 E）逐配置記錄：cup recall @1.0/1.5/2.0m（30s 窗）、偵測迴圈 Hz、
   full-stack RAM delta（tegrastats）、近距 7 類 sanity；門檻照 §4b 表。
3. T6 錄滿 36 必備色彩格 bag（+黃燈 AWB lock 掃描）；離線兩法同 bag 重算。
4. 回填 §4c RAM/GPU 總表實測值，並裁定 §2 #12 的估算口徑分歧。

Verdict slot（擇一）：MATRIX_WINNER_<A|B|C|D|E>_COMMIT / ALL_FAIL_REPLAN /
PARTIAL_NEEDS_SECOND_DAY
Done criteria：每配置 gate 判定有數字背書；色彩 bag 歸檔可離線重算；
勝出配置的 launch env 候選註解更新草稿（不 commit）。
Constraints：嚴禁上機日現燒 engine；嚴禁多 object 模型同跑；conf 改動必 kill 重啟。
```

---

## 附錄：輸入文件清單

- `docs/perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md`（GO_BENCH_MATRIX）
- `docs/perception/research/2026-06-11-open-vocab-indoor-classes-result.md`（NEEDS_TEST_VOCAB_REPLAY）
- `docs/perception/research/2026-06-11-color-recognition-upgrade-result.md`（GO_LAB_NEAREST_NAME）
- `docs/perception/research/2026-06-11-yolo-pose-gesture-result.md`（NEEDS_TEST_HITL_CLIPS）
- 對照：`2026-06-11-pinto-model-zoo-pawai-fit-report.md`（ADOPT_AS_CANDIDATE_SOURCE）、`2026-06-11-supervision-pawai-fit-report.md`（GO_ADOPT_FOR_EVIDENCE）
