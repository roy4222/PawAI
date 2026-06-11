# 系統 Phase 3：Vision Evidence + Model Benchmark（Plan V — 先建證據，用數據決定模型）

> **日期**：2026-06-11　**狀態**：PLANNED
> **上游文件**：
> - Master plan：[`2026-06-11-pawai-system-refactor-v2-master.md`](2026-06-11-pawai-system-refactor-v2-master.md)（系統 Phase 3 摘要 §Scope + 閘門 G3/G4）
> - 上機清單權威來源：[`../../perception/research/2026-06-11-objdet-upgrade-synthesis-result.md`](../../perception/research/2026-06-11-objdet-upgrade-synthesis-result.md)（下稱「synthesis」，verdict = BLOCKED_BY_HARDWARE_TEST；本 plan 的 W/T 編號沿用其 §4）
> - Evidence 工具上游：[`../../perception/research/2026-06-11-supervision-pawai-fit-report.md`](../../perception/research/2026-06-11-supervision-pawai-fit-report.md)
> - 同期 phase plan：[`2026-06-11-phase2-core-brain-ops-refactor.md`](2026-06-11-phase2-core-brain-ops-refactor.md)（2B Studio Evidence Center 是 W4 工具的回流目的地）

## 命名消歧（必讀）

本套件有三套互不相干的編號，內文一律寫全名、禁止裸寫「Phase N」：

| 編號系統 | 指什麼 | 範圍 |
|---|---|---|
| **系統重構 Phase 1-5** | 本 v2 套件的大階段（本文件＝系統 Phase 3） | CI → Core Brain/Ops → Vision → Nav/安全 → 收口 |
| **ISM Phase 0-3** | `interaction_state.py` 狀態機自己的實作階段（ISM plan §5-§8） | Brain 內 |
| **安全 hardening P0-P3** | hardening plan 的修補優先級 | 安全項 |

另注意本文件內部還有兩套小編號，皆沿用 synthesis：**W1-W6**（前置週工作項）與 **T0-T7**（上機日時段）；階段編號寫「**階段 3-0 ~ 3-4**」，與上表三套編號無關。

> **北極星（一句引用，全文見 master plan）**：把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台——Perception Nodes → Perception Router → ISM → Policy + Safety Layer → Skill Executor → Trace + Evidence，三支撐＝PawAI CLI v2 / PawAI Studio v2 / pawai_contracts。

---

## Goal

**核心立場：不是直接換模型，是先建 evidence + benchmark，用數據決定模型與 pipeline——「不再憑感覺說 cup 不穩」。**

系統 Phase 3 把 6/11 的 7 條感知研究線（全部 verdict 已填、全部收斂到「WSL 前置週 + 一個上機測試日」）執行到底，產出：

1. **Offline evidence pipeline**（supervision，WSL only）：demo 錄影 + `/event/object_detected` JSONL → annotated evidence MP4 + JSONL（含 `decision_id` join），回流系統 Phase 2B 的 Studio Evidence Center。
2. **上機矩陣數據**：object 升級矩陣 A-E（cup recall@1.0/1.5/2.0m + Hz + RAM(tegrastats) + 溫度）+ 色彩 54 格 bag 矩陣（含黃燈 AWB lock 掃描）。
3. **每研究線 GO/NO_GO 回填** + capability baseline（cup recall@distance；person/chair 近距 sanity；gesture 沿用 6/4 既有數據標注，非本 phase 產出）進 scoreboard。
4. **兩條 GO 後才動**的 runtime 換模/換參與 contract v2.5→v2.6 合併 bump。

對齊 master plan 系統 Phase 3 exit gate：「每候選有數據、KEEP/SWITCH verdict 文件化且引用數據、不留『未測但已宣稱』項」。

## Scope

| 階段 | 內容 | 場地 |
|---|---|---|
| **3-0 前置（blockers）** | Roy 交付素材：整理好的 `/event/object_detected` JSONL + demo 錄影（6/9-6/10 S2/S3 takes）＝ master plan 閘門 **G3** | — |
| **3-1 WSL 前置週** | W1 export/sanity、W2 YOLOE vocab replay、W3 色彩 spike、W4 supervision evidence spike、W5 pose 3-way sitting A/B——全程獨立 venv、不碰 runtime code | WSL |
| **3-2 上機測試日（一天）** | W6 前夜 TRT 預燒 → T0-T7：矩陣 A-E + T6 色彩 54 格 bag + RAM 口徑仲裁 + nvpmodel 記錄＝閘門 **G4** | Jetson + Go2 + 家用場地 |
| **3-3 決策回填** | 每線 GO/NO_GO 寫回 research docs + capability baseline/scoreboard 更新（`benchmarks/object_eval`、`artifacts/baseline`） | WSL |
| **3-4 runtime 落地（兩條 GO 後才動）** | 換模/換參 + contract v2.5→v2.6 **一次合併 bump** 及同步鏈 | WSL → Jetson 部署 |

新增檔案（全部 offline 工具區）：`benchmarks/scripts/supervision_evidence_spike.py`（**尚未存在**，W4 產出）、`benchmarks/scripts/color_naming_spike.py`（W3 產出）、W1/W2/W5 的 export 與 replay 腳本、矩陣數據 CSV/bag 歸檔。runtime 檔案（`object_perception/`、contract、zh 表、Studio TS）**只在階段 3-4 才碰**。

## Forbidden scope

1. **任何 runtime 模型更換／參數更換，在 gate 數字出來前一律禁止**——包含「順手把 conf 改 0.30」。上機日 T1-T5 的臨時配置走 env/測試 branch，不進 main。
2. **supervision 不進 Jetson runtime**：ByteTrack runtime 化、InferenceSlicer 上機、整包 `pip install supervision` 到 Jetson 全部禁止（supervision 報告 §5；唯一例外路徑＝spike + benchmark 數據後另案，且優先 vendor `byte_tracker/`）。
3. **色彩方案 A 的 node 實作禁止**，直到 T6 離線判定 per-color accuracy ≥0.8 過門檻（color result §3-Q9；falsification 成立則整線 NO_GO_KEEP_HSV12）。
4. **PINTO 候選（478_SC / LVFace / AdaFace 等）不部署**——它們是掛觸發條件的候選池，上線前必走 benchmark 制度（pinto report verdict = ADOPT_AS_CANDIDATE_SOURCE；「立刻在 Jetson 裝任何模型＝否」）。478_SC 在本 phase 的唯一角色是 W5 離線對照。
5. **YOLO-pose 不直接換線**：即使 W5 晉級，部署也排**下下次**上機日（本上機日名額已讓給 object 矩陣），且晉級即觸發「L3 GPU 0%」基石等價重測（另排程）。
6. **Brain 編排「新類別誰消費、講什麼台詞」不在本 phase**（open-vocab result §7 標 scope 外，掛 6/9 待辦 #4「PawAI Brain 流程編排深挖」另案）。
7. **nvpmodel 常駐決策不在本 phase 拍板**：T0 只做記錄與解讀標注；「demo 要不要常駐 Super 檔」涉及 XL4015 供電不穩前科（8+ 次斷電、20V 安全極限），需電源側意見（synthesis §5 #1，Roy 決策另案）。
8. **demo 錄影絕不餵 LLM**（見 Tasks 階段 3-0 鐵律）。
9. 凍結期（至 6/18）不碰 `executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/`（詳見 §6/18 freeze constraint）。

## Inputs / prerequisite docs

### 七條研究線吸收表（逐線 verdict + 在本 plan 的位置）

| # | 研究線（`docs/perception/research/2026-06-11-*.md`） | Verdict | 在本 plan 的位置 |
|---|---|---|---|
| 1 | `supervision-pawai-fit-report` | **GO_ADOPT_FOR_EVIDENCE**（EVIDENCE only，不進 Jetson runtime） | **W4** offline pipeline：demo 錄影/rosbag + `/brain/trace` JSONL + `/event/*` JSONL → 5 行 adapter 重建 `sv.Detections` → ByteTrack 離線補 `tracker_id` → Box/RichLabel(zh-TW TTF)/Trace annotators 疊圖 → VideoSink evidence clip + JSONSink（`custom_data` 塞 `decision_id`）→ Studio 前端讀檔。Metrics（mAP/ConfusionMatrix）需人工標註 GT 測試集（supervision 報告 §3.5/§3.6 dataset tools），本 phase 僅驗證管線可接、GT 標註另案（階段 3-3 不排） |
| 2 | `pinto-model-zoo-pawai-fit-report` | **ADOPT_AS_CANDIDATE_SOURCE**（候選池非立即部署） | 478_SC face landmark 進 **W5** 三方對照；LVFace/AdaFace 等掛觸發條件留候選池 + benchmark 制度，本 phase 不部署（Forbidden #4） |
| 3 | `objdet-upgrade-synthesis-result` | **BLOCKED_BY_HARDWARE_TEST** | 本 plan 的骨架來源：上機矩陣 **A**(conf 0.35→0.30)/**B**(YOLO26s@640)/**C**(YOLO26n@960+720p)/**D**(YOLO26s@960)/**E**(YOLOE vocab38 條件項)。推翻舊論：imgsz=1280 superseded（相機 640x480 插值自欺）、effective conf＝**0.35** 非 0.5。決勝指標：cup recall@1.0/1.5/2.0m + Hz + RAM(tegrastats) + 溫度 |
| 4 | `yolo26-scaleup-highres-seg-result` | **GO_BENCH_MATRIX** | s/960/seg 候選細節併入矩陣 **B/C/D**；det 任務 seg 變體出局；門檻（cup@1.5m ≥80% 等）進 T2-T4 |
| 5 | `yolo-pose-gesture-result` | **NEEDS_TEST_HITL_CLIPS** | **W5**＝WSL 離線 3-way sitting A/B（MediaPipe vs YOLO26n-pose vs 478_SC，餵 demo 錄影）；晉級 gate＝+10pp 或救回 ≥30% 漏偵幀；晉級即推翻「L3 GPU 0%」基石需重測。gesture YOLO 路線＝**死路**（無官方 hand 預訓練；社區品＝MediaPipe 蒸餾 + NC/AGPL），維持 MediaPipe + bbalg |
| 6 | `color-recognition-upgrade-result` | **GO_LAB_NEAREST_NAME** | 方案 A＝Lab+CIEDE2000 LUT + 自訂 zh 19 色名 + 中央 50% 取樣 + 事件級 3 次多數決 + demo AWB lock 選配；成本 0.190ms/bbox 與現役 HSV 同價。**W3** spike → **T6** 54 格(36 必備) bag 矩陣；per-color ≥0.8 過門檻才進 node 實作 + contract bump；falsification：HSV12+AWB lock 已全 ≥0.8 → NO_GO_KEEP_HSV12 |
| 7 | `open-vocab-indoor-classes-result` | **NEEDS_TEST_VOCAB_REPLAY** | 唯一候選 YOLOE-26 custom-vocab set-then-export（export 後零 text-encoder 成本）；真類別缺口 22 類、藥瓶連 LVIS 1203 都沒有（零紙面證據）；權重是 seg 形態、parse 改一行切片 `[:, :6]`。**W2**＝WSL vocab replay（38 類 v0 + 容器混淆矩陣 + cup 不退化門檻），過了才掛上機條件配置 **E** |

### 與其他系統 phase 的關係

- **W4 evidence 工具回流系統 Phase 2B**（Studio annotated evidence / suppressed-reason viewer 的影像層）。
- **`PerceptionEvent` 與 `sv.Detections` 的關係（事實澄清）**：supervision 報告 §4 曾建議 Plan D 把 `PerceptionEvent` 欄位命名對齊 `sv.Detections`（xyxy/confidence/class_id/tracker_id/data），**Plan D 實作未採納**（`interaction_executive/perception_router.py` 現行欄位無 xyxy/class_id/tracker_id/data）；W4 adapter 直接讀 `/event/object_detected` JSONL 的 bbox 欄位重建 `sv.Detections`、不依賴 `PerceptionEvent`，故不受影響。若仍要對齊命名，列 future follow-up（非本 phase）。
- **`pawai smoke vision|object` 的歸屬切分（本 plan 覆寫系統 Phase 2 plan 2C 行的籠統歸屬）**：採集 **script＝本 phase（系統 Phase 3，V3-3 產出）**、**CLI wiring＝系統 Phase 5（T5A-2 包進 CLI）**；系統 Phase 2 不做（其 2C 行「vision/object 屬系統 Phase 3」僅指 script，已同步勘注）。

### 前置狀態表

| 前置 | 狀態 | 用途 |
|---|---|---|
| Roy 素材：object JSONL + demo 錄影（G3） | **待交付（blocker）** | 階段 3-1 W2/W3/W4/W5 的離線輸入 |
| 上機日排程 + Roy HITL 在場（G4） | 待排（W1+W6 完成後第一個可上機時段） | 階段 3-2 |
| 7 條研究線 result docs | 已 commit | 上表 |
| `capture_baseline_round.py percep` + topic 隔離坑（6/4） | 既有 | T1-T5 recall 量測口徑 |
| demo snapshot forbidden claims | 持續有效 | 對外宣稱防線 |

---

## Tasks

### 執行紀律（治理原則，繼承 master plan，全 task 適用）

main 永遠可部署；每刀小 PR + CI 綠 + 紅綠驗證才 merge；搬家與行為變更分開 PR；trace/觀測 additive-only；觀測類與政策類永不同 PR；Codex 串行實作 + Fable spec/review；硬體能力宣稱必過 HITL gate；demo snapshot 的 forbidden claims 對所有對外材料持續有效。

### 階段 3-0：前置 blockers（G3）

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **V0-1** | 交付整理好的 `/event/object_detected` JSONL + demo 錄影（6/9-6/10 **S2 坐姿段 / S3 cup 段** takes），含每段對應場景標注 | **Roy**（素材） | 素材清單核對：每段錄影可定位到 take + 對應 JSONL 時間窗可 join |
| **V0-2** | W2 拍照素材：自拍居家物件照（藥瓶/鑰匙串/眼鏡/遙控器/容器混淆組/拖鞋/毛巾/拐杖 × 0.5/1.0/1.5m，D435 視角高度 ~30cm 模擬） | **Roy**（素材） | 物件 × 距離覆蓋齊；可與 W4 共用素材 |

> **鐵律：影片只由程式離線跑 detection/benchmark（ORT/cv2/supervision），絕不餵 LLM。** 錄影是量測輸入，不是理解輸入。

### 階段 3-1：WSL 前置週（全程零 Jetson 風險、獨立 venv `uv venv && uv pip install …`、不碰 runtime code；W 編號沿用 synthesis §4a）

| Task | 內容 | 產出 / 門檻 | 載體 | 驗證 |
|---|---|---|---|---|
| **W1** | object 矩陣 export + sanity：WSL export 3 顆 fixed-shape e2e ONNX（`yolo26s_640` / `yolo26n_960` / `yolo26s_960`）；ORT CPU 對 S3 錄影抽幀 sanity（shape `(1,300,6)`、近距 cup 有偵測、座標域正確）；rsync 到 `/home/jetson/models/`（走 audited deploy，純檔案 additive） | 3 顆 ONNX 落 Jetson + sanity 全過 | Codex 實作 | sanity 紀錄 + `git status` 乾淨（模型檔不進 repo） |
| **W2** | YOLOE-26 vocab replay（open-vocab result §12）：`set_classes`（38 條目 v0）後對 V0-2 照片 + demo 錄影重放；藥瓶 prompt A/B；conf sweep 0.25-0.35；驗 export ONNX 輸出 shape（推定 `(1,300,38)+(1,32,160,160)`） | 三表：per-class recall×距離、容器混淆矩陣、cup 基線對齊。**門檻：demo 核心組新類 1.0m recall ≥0.5 ∧ 容器混淆 <30% ∧ cup 退步 <5pp** → 過＝export 640+960 兩版、掛配置 E；不過＝縮 vocab 重測一輪，再不過 `NO_GO_STAY_COCO80` | Codex 實作 | 三表數據齊 + gate 判定有數字背書 |
| **W3** | 色彩 spike script：寫 `benchmarks/scripts/color_naming_spike.py`，讀 demo 錄影幀，同畫面並排「現役 `analyze_bbox_color` vs Lab-LUT（19+1 zh 色名 v0 表）×（整 bbox / 中央 50%）」四組色名+純度，桌面驗 v0 錨點邊界 | spike 腳本入 repo + 桌面驗證通過（**紅杯不再 red↔pink 翻動**為主要 sanity） | Codex 實作 | 腳本可重跑 + 對照截圖歸檔 |
| **W4** | supervision evidence spike：寫 `benchmarks/scripts/supervision_evidence_spike.py`（**尚未存在**）——讀 S3 cup 錄影 + object JSONL → 重建 `sv.Detections` → `ByteTrack(minimum_consecutive_frames=3)` → Box/RichLabel(zh-TW TTF)/Trace annotators → **evidence MP4 + JSONL**；JSONL `custom_data` 塞 `decision_id`，**驗 decision_id join 可行性**；量化報告：baseline **conf 0.35** vs「0.30 + N=3 時序過濾」的首偵測幀號/假陽性數/track 斷裂次數（基線依 synthesis §2 #5 裁定 0.35，非舊文獻的 0.5） | evidence MP4 + JSONL + 量化報告；**工具回流系統 Phase 2B viewer**。失敗條件（runtime 路線降級 NO_GO、維持 offline-only）：6-8Hz 低幀率下 ByteTrack track 斷裂嚴重、或假陽性壓不下來 | Codex 實作 | MP4 可播（bbox+zh label+track id 穩定可見）+ JSONL join 驗證 + PawAI repo 不裝 supervision 進 runtime 依賴 |
| **W5** | pose 3-way sitting A/B（含 478_SC 離線對照）：對 S2 坐姿段逐幀跑 MediaPipe（現役 33→17）/ YOLO26n-pose（export + min_score sweep 0.1-0.3）/ 478_SC（person crop 來源＝YOLO-pose bbox），全餵同一套 `classify_pose` | 逐幀對照表：sitting 正確率（人工 GT）、漏偵幀、分歧分佈。**晉級 gate：YOLO-pose ≥ MediaPipe +10pp 或救回 ≥30% 漏偵幀**；晉級者排**下下次**上機 + 觸發 L3「GPU 0%」基石重測排程。**fallback：若 demo 錄影不可抽幀（無可用坐姿段）→ 改在下次上機日補錄 sitting/standing clips，本 task 順延不 block 上機日** | Codex 實作（補錄 fallback＝Roy HITL） | 對照表 + gate 判定；gesture 線維持 MediaPipe + bbalg（不開工單） |

平行性：W1 為上機日硬前置、W2 決定 E 存廢，W3-W5 可全平行；全部不 block 系統 Phase 2（檔案面不重疊）。

### 階段 3-2：上機測試日（一天；Jetson + Go2 + 家用場地；T 編號沿用 synthesis §4b）

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **W6**（前一晚） | Jetson 預燒 TRT engine（不開 demo stack）：`s_640` → `n_960` → `s_960` →（W2 過門檻才有）`yoloe26s_vocab38_640/_960`；每顆燒完過已知場景 sanity（F16 AGX 異常 + Hackster drift 前科）。**紀律：1GB TRT workspace 峰值，預燒期間不得同跑 demo stack** | Roy HITL（Fable/Codex 遠端輔助） | 3-5 顆 engine cache 在 `trt_cache/<stem>/` + sanity 紀錄 |
| **T0** | 開場鎖定：`prepare_env.sh`（nvpmodel + jetson_clocks）+ **記錄當前 power mode**（非 Super MAXN 則 FPS 解讀 ÷1.4-1.7 標注，門檻不變）；tegrastats RAM 基線；確認 engine cache 在位 | Roy HITL | power mode + 基線記錄在案（常駐 Super 檔決策不在今天拍，Forbidden #7） |
| **T1** | 矩陣 **A**：n@640 現役，A0=conf 0.35 → **kill 重啟** → A1=conf 0.30；cup recall @1.0/1.5/2.0m 各 30s 靜置 + Hz + RAM 基線（recall 量測一律 `capture_baseline_round.py percep` + `--gesture-topic /__no_gesture__` 隔離，6/4 坑） | Roy HITL | 紀錄性基線；**若 A1 已讓 cup@1.5m ≥80% → B-D 降級為驗證性質** |
| **T2** | 矩陣 **B**：s@640（`OBJECT_MODEL=yolo26s_640.onnx`，相機不動）——主力刀 | Roy HITL | 門檻：① cup@1.5m recall ≥80%（@2.0m ≥50% stretch）② 偵測迴圈 ≥3Hz ③ full-stack RAM 餘 ≥0.8GB ④ 近距 7 類 sanity 不退化 |
| **T3** | 矩陣 **C**：n@960 + 相機 1280x720x30；同 T2 + **face node CPU 漲幅紀錄**（共用 color topic，像素 ×2.25） | Roy HITL | 同 T2 四門檻 + face CPU 紀錄（紀錄性） |
| **T4** | 矩陣 **D**：s@960 + 720p（RAM 最危）——**RAM 先量再跑、違反 0.8GB 即棄測**；本段同時**仲裁 RAM 估算口徑分歧**（goal 1 全包口徑 +300~600MB vs goal 2 邊際口徑 +100-150MB，差 3-4 倍，tegrastats 是唯一仲裁） | Roy HITL | 同 T2 四門檻；口徑仲裁數據記入 §4c 總表 |
| **T5** | 條件配置 **E**（W2 過門檻才執行）：YOLOE-26s-seg vocab38 @ 勝者 imgsz；node 類別表臨時換 vocab 對應表（**測試 branch，不進 main**）；vocab 命中 smoke + cup 對照 + Hz + RAM | Roy HITL | ① 新類 1.0m 現場 recall 與 W2 replay 同向 ② cup 不退化 ③ ≥3Hz（seg 形態 ×1.6 GFLOPs 的 Hz check）④ RAM ≥0.8GB |
| **T6** | 色彩 54 格 bag 矩陣（**回 A0 基線配置**：n@640、conf 0.35、640x480、AWB AUTO）：**必備 36 格**（6 物 × 3 光照 × 2 距離 0.7/1.5m）每格 bag ≥60s（≥10 事件樣本）；**黃燈格加跑 AWB lock 掃描**（白紙 3000→5500 step 100-200 取 S 最低）+ lock 對照格；選配 18 格 stretch。bag 離線兩法（HSV12 baseline vs Lab-LUT）同算 | Roy HITL | bag 歸檔可離線重算；判定門檻在階段 3-3（per-color ≥0.8） |
| **T7** | 收尾：矩陣勝者宣告（按 T1-T5 gate）、RAM/GPU 總表回填實測值、勝出配置寫 launch env 候選**註解草稿（文件，不 commit）**、bag/CSV 歸檔 | Roy HITL + Fable 撰寫 | 當日產出三件：矩陣勝者 + E 存廢 + 36 格色彩 bag |

時長：核心 ≈4.5-5h；含 T5 + 選配 ≈6h + buffer ⟹ **排全天**。同跑紀律：任一時刻 GPU 上只有一顆 object engine（`OBJECT_MODEL` env 輪換、kill→換 env→重啟）；嚴禁上機日現燒 engine。

### 階段 3-3：決策回填

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **V3-1** | 每研究線 GO/NO_GO verdict 回填各自 research result doc（objdet 矩陣勝者、E 存廢、色彩過門檻/falsification、W4/W5 gate 結果）；synthesis §5 未解項逐條更新（RAM 口徑慣例寫入 benchmark 制度） | Fable 撰寫 | 7 條線無懸空 verdict；引用全部是實測數字 |
| **V3-2** | capability baseline 更新：**cup**（recall@1.0/1.5/2.0m + Hz + RAM）+ **person/chair**（T2 近距 sanity 等級，非 recall@distance 量測）數據進 scoreboard（`benchmarks/object_eval`、`artifacts/baseline`）；**gesture** 沿用 6/4 既有 baseline 數據並標注「非本 phase 產出」（研究線 5 維持 MediaPipe + bbalg）。W4 的 mAP/ConfusionMatrix（supervision metrics）需人工標註 GT 測試集（supervision 報告 §3.5/§3.6 dataset tools），**本 phase 僅驗證管線可接、GT 標註另案，不進本次 scoreboard** | Codex 實作 | scoreboard 數字可溯源到矩陣 CSV / bag / 6/4 baseline 標注 |
| **V3-3** | `pawai smoke vision|object` 採集腳本草案（包 `capture_baseline_round.py` 口徑 + topic 隔離），**交系統 Phase 5 包進 CLI**（本 phase 只產 script 不動 CLI）。**歸屬釐清（覆寫系統 Phase 2 plan 2C 行的「vision/object 屬系統 Phase 3」語意）：script＝系統 Phase 3、CLI wiring＝系統 Phase 5 T5A-2**，系統 Phase 2 plan 已同步勘注 | Codex 實作 | 腳本可獨立執行；Phase 5 plan 收到 handoff 註記 |
| **V3-4** | 若「s 級 + open-vocab + 新色名表」三線全過 → 補一張 ADR（主 object 模型從 COCO 80 closed-set n 級遷移到 custom-vocab s 級，hard-to-reverse） | Fable 撰寫 + Roy 決策 | ADR 引用矩陣數據；未全過則不立 |

### 階段 3-4：runtime 落地（**兩條 GO 後才動**；「上機日不動 contract」）

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **V4-1** | Roy 拍板：矩陣勝者採用 + E 存廢 + 色彩 GO/NO_GO（依 3-3 數據） | Roy 決策 | 決策記入 master plan 附錄 A 決策登記簿 |
| **V4-2** | runtime 換模/換參 PR：`OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env 切換 + launch 預設更新（含 conf 若 A1 勝出）；TRT cache 按 model 分目錄 | Codex 實作 | 紅綠驗證 + Jetson smoke + env 一行可切回現役 n@640 |
| **V4-3** | contract v2.5→**v2.6 一次合併 bump**（synthesis §2 #9 裁定，不分兩次）：色名 19+1 enum + vocab 新類描述 + `pawai_contracts/zh_tables.py` + Studio `object-config.ts` + parity test + `class_whitelist` 語意重文件化 + `test_object_perception.py:336-348` regex 測試改寫（色名表移模組級後機制必改、意圖保留） | Codex 實作 | `pawai contract check` 綠 + zh parity test 綠 + 同步鏈五點一次到位 |
| **V4-4** | 色彩方案 A node 實作（Lab-LUT + 中央 50% + 事件級 3 次多數決 + AWB lock SOP 文件化）——**僅在 T6 per-color ≥0.8 過門檻後** | Codex 實作 | pixel-level 單測（補現缺的色彩回歸網）+ bag 重放對照 |

---

## Tests / verification

- **階段 3-1**：每個 W spike 有可重跑腳本 + 歸檔產物（JSONL/MP4/對照表）；W2/W5 gate 判定有數字背書；repo `git status` 乾淨（素材與模型不進 git）；CI 不受影響（spike 腳本若入 repo 需過 blocking flake8 max-line=100）。
- **階段 3-2**：每配置 gate 判定有數字（recall/Hz/RAM/溫度）；conf 改動必 kill 重啟（param 只在 `__init__` 讀一次的既有坑）；色彩 bag 可離線重算任何演算法；T0 power mode 記錄在案。
- **階段 3-3**：scoreboard 數字可溯源；7 線 verdict 無懸空；「不留未測但已宣稱項」（master plan 系統 Phase 3 exit gate ③）。
- **階段 3-4**：每 PR CI 綠 + 紅綠驗證；換模 PR 與 contract bump PR 分開（搬家與行為變更分 PR）；部署後 Jetson smoke + demo 主場景（S3 cup）回歸。

## Jetson / Go2 requirement

| 階段 | Jetson | Go2 | 說明 |
|---|---|---|---|
| 3-0 / 3-1 | **不需**（W1 末端 rsync 模型檔除外，純檔案 additive） | 不需 | 全 WSL、獨立 venv、零 Jetson 風險 |
| 3-2（含 W6 前夜） | **需要一整天** + 前夜預燒時段 | **需要**（D435 機上視角 + 家用場地擺位；motion 不需） | **Roy 必須在場**（HITL）；家用場地 + 三光照可控 + 9 件色彩物件就位 |
| 3-3 | 不需 | 不需 | 離線回填 |
| 3-4 | 部署 + smoke 需要 | 回歸 demo 場景需要 | 標準 deploy 流程 |

## Done criteria

1. **四個 W spike 各有產物**：W2 三表、W3 spike 腳本+對照、W4 evidence MP4+JSONL（decision_id join 驗證過）、W5 逐幀對照表（或 fallback 補錄排程記錄在案）。
2. **上機矩陣有完整數據表**：A-E 每配置 recall@1.0/1.5/2.0m + Hz + RAM(tegrastats) + 溫度；RAM 口徑仲裁有結論；36 格色彩 bag 歸檔。
3. **每研究線 verdict 回填**：7 條線 GO/NO_GO 寫回 research docs，無懸空。
4. **cup（recall@1.0/1.5/2.0m）+ person/chair（近距 sanity 等級）capability baseline 進 scoreboard**（`benchmarks/object_eval`、`artifacts/baseline`），數字可溯源；**gesture 沿用 6/4 既有 baseline 數據並標注「非本 phase 產出」**（研究線 5 結論：維持 MediaPipe + bbalg、不開工單，本 phase 不採 gesture 新數據——上機日 T1-T5 反向隔離 gesture topic）。
5. **contract bump 僅在 GO 後完成**：v2.6 一次合併 bump + 同步鏈五點到位；若任一線 NO_GO 則該線不進 contract（部分 bump 仍合併為一次）。
6. W4 evidence MP4/JSONL 的**檔案格式與 `decision_id` join 欄位已文件化並 handoff 系統 Phase 2B**（2B 收到註記即算數；Studio Evidence Center 的實際消費驗證歸系統 Phase 2B 的 done criteria，不 block 本 phase 收口）；smoke 採集腳本已 handoff 系統 Phase 5。

## Rollback / fallback

- **全部離線工具與數據 additive**：W1-W5 腳本、bag、CSV、MP4、JSONL 不動任何 runtime 行為——本 phase 3-4 之前**沒有東西需要 rollback**。
- **runtime 換模一行切回**：`OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env override 回現役 `yolo26n.onnx`@640；**TRT cache 按 model 分目錄**（`trt_cache/<stem>/`），切回不需重燒。
- **contract bump rollback**：v2.6 PR revert 即回 v2.5（同步鏈五點在同一 PR，revert 原子）。
- **色彩線 fallback**：falsification 成立（HSV12+AWB lock 全 ≥0.8）→ `NO_GO_KEEP_HSV12`，只留 AWB lock SOP 文件，零 code 變更。
- **E 配置 fallback**：W2 不過 → `NO_GO_STAY_COCO80`，T5 直接跳過。
- **W5 fallback**：錄影不可抽幀 → 下次上機日補錄 clips，pose 線整體順延，不 block 其他線。

## 6/18 freeze constraint

- **demo 凍結（至 6/18）**：`executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/` 除 Roy 明示授權外禁改。本 phase 的階段 3-0/3-1 全程不碰這三者；T1-T5 的臨時配置走 env override 與測試 branch，**不寫回凍結檔案**。
- **階段 3-2 上機日若排在 6/18 前**：當日結束必須把 Jetson 還原到 demo 現役配置（n@640、conf 0.35、相機 640x480）並跑一輪 demo smoke 確認，TRT 現役 engine cache 不得被覆蓋（分目錄紀律保證）。**建議直接排 6/18 後**，除非 Roy 明示授權提前。
- **階段 3-4（runtime 換模 + contract bump）整段 post-6/18**：它必然觸碰 demo 主線行為。
- demo snapshot 的 forbidden claims 持續有效：上機數據出來前，對外不得宣稱「cup 1.5m 可偵測」「支援藥瓶/鑰匙辨識」「19 色辨識」等任何未過 gate 的能力。

---

## 附錄：synthesis 既裁矛盾的快速對照（執行時別走回頭路）

| 已裁定 | 結論 | 出處 |
|---|---|---|
| effective conf 基線 | **0.35**（launch/yaml 已 override，b1f5058），非 0.5；W4/T1 基線一律 0.35 | synthesis §2 #5 |
| imgsz=1280 | **superseded**（相機 640x480 使 1280 成插值自欺）；高解析線由 n@960+720p 真像素承接 | synthesis §2 #6 |
| 「seg 出局」適用範圍 | det 任務的 seg 變體出局；YOLOE-seg 屬例外（無 det 權重可選），mask 棄用、parse 切片 `[:, :6]`，但 E 必保留 ≥3Hz check | synthesis §2 #2 |
| pose 上機名額 | 本上機日不排 pose（W5 離線裁），晉級也排下下次 | synthesis §2 #4 |
| RAM 口徑 | 紙面不可裁（差 3-4 倍），T4/T5 tegrastats 實測仲裁，事後寫成 benchmark 慣例 | synthesis §2 #12 / §5 #2 |
| contract 同步鏈 | 色名 + vocab 兩條 GO 後**合併一次** v2.5→v2.6 bump；上機日不動 contract | synthesis §2 #9 |
