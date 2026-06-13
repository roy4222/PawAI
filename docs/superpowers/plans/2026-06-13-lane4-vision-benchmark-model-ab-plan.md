# Lane 4：Vision Benchmark / Model A-B（感覺測試 → evidence/benchmark）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)、[系統 Phase 3 plan](2026-06-11-phase3-vision-evidence-model-benchmark.md)（**本 plan = 其 aggressive 排程版**：W1-W5 立即開跑、上機矩陣日改為 Roy 可選提前；矩陣內容/門檻/紀律全文沿用不重抄）、7 條研究線 result docs（verdict 已收斂，`docs/perception/research/2026-06-11-*.md`）
> **鐵律繼承**：demo 錄影**絕不餵 LLM**；supervision 不進 Jetson runtime；上機日不動 contract；數據出來前不換任何 runtime 模型/參數

---

## 1. Goal

把「cup 1m+ 不穩」「手勢誤觸」這類感覺敘述換成數據：**W1-W5 五個 WSL 離線 spike 本週末全部跑完**（候選模型 export、open-vocab replay、色彩 Lab-LUT、supervision evidence、pose 三方 A/B），上機矩陣日（A-E + 色彩 54 格）由 Roy 決定排 6/15-16 或 post-6/18。產出 = 每候選一行數據 + GO/NO_GO + capability baseline 更新。**6/18 前 runtime 一律用現役配置**（n@640 / conf 0.35），數據只進決策不進部署（B-4）。

## 2. Current state

- **7 條研究線 verdict 全收斂**（6/11）：supervision=GO_ADOPT_FOR_EVIDENCE（offline only）、PINTO=ADOPT_AS_CANDIDATE_SOURCE（478_SC/LVFace/AdaFace 候選池）、objdet synthesis=BLOCKED_BY_HARDWARE_TEST（矩陣 A-E 清單 v1 完成）、yolo26 scale-up=GO_BENCH_MATRIX、pose-gesture=NEEDS_TEST_HITL_CLIPS（gesture YOLO=死路，維持 MediaPipe+bbalg）、色彩=GO_LAB_NEAREST_NAME、open-vocab=NEEDS_TEST_VOCAB_REPLAY（YOLOE-26 38 類 vocab v0）。
- **已推翻舊論（不得再引用）**：imgsz=1280 superseded（相機 640x480 插值自欺）；effective conf=**0.35** 非 0.5；seg 變體 det 任務出局；SAHI runtime 出局；「遙控器/碗/手機類別缺口」不成立（COCO 80 已含，是 recall/距離問題）。
- **素材**：demo 錄影已錄完（6/9-6/10 S2/S3 takes）；object JSONL 需 Roy 指認位置（B-8）；`.tmp/yolo_export/` 有 `yolo26n.pt / yolo26s.pt / yolo26n-pose.pt` + `export_models.py` + `out/` 目錄——**ONNX 是否已 export 成 fixed-shape e2e 需 W1 第一步確認**。
- **runtime 可調面已備**（A/B 不需改 code）：`OBJECT_MODEL` / `OBJECT_INPUT_SIZE` env、`confidence_threshold` launch arg、`class_whitelist` runtime param、TRT cache 按 model stem 分目錄。
- **工具**：`capture_baseline_round.py percep`（+topic 隔離坑 SOP）、`scripts/obj_matrix_cap.py` + `benchmarks/core/object_matrix.py`（per-cell PASS/DEGRADED/FAIL CSV）、`scripts/lidar_front_sector.py`。
- gesture 誤觸現防線：`gesture_recognizer_min_conf=0.7` + `gesture_min_votes=3`（demo 凍結值），誤觸率從未量化。

## 3. Problems / gaps

1. cup@1.0/1.5/2.0m recall 沒有數字——「0.7m 可用、1m+ 不穩」是印象，矩陣 A-E 就是為了給數字（s@640 是主力刀假說）。
2. 候選（YOLO26s、n@960、YOLOE vocab38、Lab-LUT、YOLO26n-pose、478_SC）全部停在紙面，W1-W5 沒跑就永遠 BLOCKED。
3. gesture 誤觸：有防線值但無量化（誤觸率@min_conf×min_votes 掃描從未做）。
4. supervision evidence（annotated MP4 + decision_id join）是 Lane 2 annotated clip 的上游，沒 spike 就一直空轉。
5. 上機矩陣日的排程衝突：需 Roy 全天 + 家用場地 + 前夜 TRT 預燒——與發表準備搶時間（故設為 B-3 決策，不硬排）。

## 4. Scope

- 全程 offline 工具區：`benchmarks/scripts/`（W3 `color_naming_spike.py`、W4 `supervision_evidence_spike.py` 皆新建）、W1/W2/W5 的 export/replay 腳本、`.tmp/` 工作區、獨立 venv（`uv venv && uv pip install`）。
- 數據歸檔：`benchmarks/results/`、bag/CSV/MP4/JSONL（素材與模型不進 git）。
- 上機日（若 B-3=提前）：env/測試 branch 臨時配置，**不進 main**。
- runtime 檔案（object_perception/、contract、zh 表）：**本 lane 期間零接觸**（落地=post-6/18 另案）。

## 5. Forbidden scope

1. **6/18 前任何 runtime 模型/參數更換禁止**（含「順手把 conf 改 0.30」）——B-4 預設答案是不換；例外需 Roy 點頭 + demo smoke 全綠。
2. supervision 不進 Jetson runtime（`pip install supervision` 到 Jetson 禁止）；ByteTrack runtime 化另案。
3. 色彩方案 A node 實作禁止（T6 per-color ≥0.8 過門檻後 post-6/18 另案）；PINTO 候選不部署；YOLO-pose 不換線（晉級也排下下次上機日）。
4. demo 錄影絕不餵 LLM（量測輸入，非理解輸入）。
5. contract v2.5→v2.6 bump 整段 post-6/18。
6. 上機日若排在 6/18 前：**當日結束必須還原 demo 現役配置 + 跑一輪 demo smoke**（`pawai smoke full`），TRT 現役 engine 不得被覆蓋（分目錄紀律）。
7. Brain 端「新類別誰消費、講什麼台詞」不在本 lane。

## 6. Proposed tasks

> W/T 編號沿用 synthesis §4 與系統 Phase 3 plan；細部步驟、門檻、時長以系統 Phase 3 plan 為權威，本表只列 aggressive 排程差異與 gate。

| Task | 內容（摘要） | Gate / 門檻 | 優先 |
|---|---|---|---|
| **V0 素材確認** | Roy 指認 object JSONL + demo 錄影路徑（B-8）；W2 拍照素材（居家物件 × 0.5/1.0/1.5m，D435 高度 ~30cm 模擬，~30 min） | 素材可定位、時間窗可 join | P0（blocker） |
| **W1 export + sanity** | 確認 `.tmp/yolo_export/out/` 既有 ONNX 可用性；缺則 export `yolo26s_640 / yolo26n_960 / yolo26s_960`（fixed-shape e2e）；ORT CPU 對 S3 錄影抽幀 sanity（shape `(1,300,6)`、近距 cup 有偵測）；rsync 到 `/home/jetson/models/`（audited deploy，純檔案 additive） | sanity 全過 | P0（上機硬前置） |
| **W2 YOLOE vocab replay** | 38 類 vocab v0 `set_classes` → 對 V0-2 照片 + 錄影重放；藥瓶 prompt A/B；conf sweep 0.25-0.35 | 新類 1.0m recall ≥0.5 ∧ 容器混淆 <30% ∧ cup 退步 <5pp → 過=export 兩版掛配置 E；再不過=NO_GO_STAY_COCO80 | P0 |
| **W3 色彩 spike** | `color_naming_spike.py`：現役 HSV12 vs Lab-LUT（19+1 zh 色名 v0）×（整 bbox / 中央 50%）四組並排 | 紅杯不再 red↔pink 翻動（sanity） | P1 |
| **W4 supervision evidence spike** | `supervision_evidence_spike.py`：S3 錄影 + object JSONL → `sv.Detections` 重建 → ByteTrack(N=3) → zh 標注 MP4 + JSONL（`custom_data` 塞 decision_id）；量化 conf 0.35 vs「0.30+N=3」 | decision_id join 可行；6-8Hz 下 track 不嚴重斷裂（失敗=runtime 路線 NO_GO、維持 offline-only） | P1（Lane 2 clip 的上游） |
| **W5 pose 3-way A/B** | S2 坐姿段逐幀：MediaPipe vs YOLO26n-pose（min_score sweep）vs 478_SC，同餵 `classify_pose` | 晉級 gate：+10pp 或救回 ≥30% 漏偵幀；晉級也只排下下次上機 | P1 |
| **W7 gesture 誤觸量化（新增）** | 用 demo 錄影（非手勢段）離線跑 recognizer：誤觸發數 @ min_conf {0.5,0.7,0.8} × min_votes {1,3,5} 矩陣 → 現役值（0.7×3）的誤觸率有數字、有更優組合則記錄為 post-6/18 候選 | 純紀錄性（不改 runtime） | P2 |
| **上機矩陣日**（B-3=提前才執行） | W6 前夜 TRT 預燒（嚴禁同跑 demo stack）→ T0 power mode 鎖定 → T1-T5 矩陣 A-E（cup recall@1.0/1.5/2.0m + Hz + RAM tegrastats + 溫度；conf 改動必 kill 重啟）→ T6 色彩 54 格（必備 36）bag → T7 收尾 + **還原現役 + demo smoke** | 各配置四門檻（cup@1.5m ≥80%、≥3Hz、RAM 餘 ≥0.8GB、7 類 sanity）；T4 RAM 先量再跑違反即棄測 | Roy 決策 |
| **V3 決策回填** | 每線 GO/NO_GO 寫回 research docs；cup/person/chair baseline 進 scoreboard（gesture 沿用 6/4 數據標注非本期產出）；矩陣勝者宣告文件 | 無懸空 verdict、數字可溯源 | P0（有數據就回填） |

## 7. Pure software tasks（WSL，可 AFK）

V0 之後的 W1 / W2 / W3 / W4 / W5 / W7 全部（獨立 venv、不碰 runtime code、素材不進 git）；V3 的文件回填。W2 等 Roy 拍照素材，其餘拿到 JSONL/錄影路徑即可開跑。

## 8. Jetson / Go2 HITL tasks（Roy 在場）

| 項 | 需要 | 時長 |
|---|---|---|
| W1 末端 rsync 模型檔到 Jetson | Jetson（純檔案） | 5 min |
| W6 前夜 TRT 預燒 | Jetson（不開 demo stack） | 30-75 min |
| 上機矩陣日 T0-T7 | **Jetson + Go2（D435 機上視角）+ 家用場地 + 三光照 + 9 件色彩物件 + Roy 全程** | 核心 4.5-5h；含 T5+選配 ≈6h（排全天或砍 T6 選配排半天） |
| 還原驗證 | 當日收尾 `pawai smoke full` | 15 min |

**建議給 Roy 的三選一（B-3）**：① 6/15 或 6/16 全天（數據趕上發表，可講實測數字）② 半天精簡版（T0-T2+T6 必備 36 格：基線+主力刀+色彩）③ post-6/18（零發表風險，W1-W5 數據照樣可講）。任一選擇都不 block 其他 lane。

## 9. Tests

- 每個 W spike 有可重跑腳本 + 歸檔產物（CSV/MP4/JSONL/對照表）；gate 判定全部數字背書。
- spike 腳本入 repo 須過 blocking flake8（max-line 100）；`git status` 乾淨（素材/模型不進 git）。
- 上機日：每配置 gate 四門檻數據齊；bag 可離線重算；當日還原後 demo smoke 綠。
- recall 量測口徑統一 `capture_baseline_round.py percep` + topic 隔離（6/4 坑）。

## 10. Rollback strategy

- W1-W7 全離線 additive——**沒有東西需要 rollback**。
- 上機日臨時配置走 env/測試 branch 不進 main；`OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env 一行切回現役；TRT cache 分目錄保證現役 engine 完好；當日還原 SOP 是 gate（§5-6）。
- 任一 spike 失敗 = 該線 NO_GO 記錄，不連坐其他線（E 配置 fallback=NO_GO_STAY_COCO80、色彩 falsification=NO_GO_KEEP_HSV12、W5 不可抽幀=順延補錄）。

## 11. Done criteria

1. W1-W5 各有產物 + gate 判定（W7 盡力）；研究線 verdict 從 BLOCKED/NEEDS_TEST 推進到 GO/NO_GO 或「待上機」。
2. 上機矩陣：若跑了——A-E 數據表 + 矩陣勝者宣告 + 36 格色彩 bag 歸檔 + Jetson 還原驗證綠；若 post-6/18——W 數據齊備、上機 checklist 成文待排。
3. capability baseline（cup@distance 等）有可溯源數字進 scoreboard（有上機數據才更新 recall@distance；無則維持 6/4 基線並標注）。
4. 6/18 發表的能力宣稱逐條對得上數據或 forbidden claims。

## 12. Execution order

V0（Roy，6/13-14）→ W1（即刻）→ W2/W3/W4/W5 並行（6/14-15）→ W7（餘力）→ B-3 決策 →（若提前）W6+上機日（6/15 或 6/16）→ V3 回填（6/16-17）。

## 13. 6/18 presentation impact

- 正面：發表可講「感知能力邊界是量出來的」——W replay 數據（新類 recall、色彩對照、pose 三方）即使沒上機也是真數據；若上機日跑了，cup recall@distance 直接進簡報。
- 風險控制：runtime 零變動（B-4 預設不換）→ demo 行為與已錄影片一致；上機日若排 6/15-16，還原+smoke 是硬 gate。
- 不可講：「cup 2m 可偵測」「支援藥瓶/鑰匙辨識」「19 色辨識」等任何未過 gate 的能力（forbidden claims 持續有效）。

## 14. Fable review checklist

- [ ] 每個 spike 腳本可重跑（參數化輸入路徑，不寫死 Roy 機器路徑）
- [ ] 素材/模型/bag 不進 git；flake8 過
- [ ] W4 的 JSONL 格式與 decision_id join 欄位文件化（handoff Lane 2）
- [ ] 上機日 checklist 含還原 SOP + demo smoke + TRT 分目錄斷言
- [ ] 無任何 runtime 檔案 diff（git diff 對 object_perception/ contracts/ 為空）
- [ ] 推翻舊論清單（§2）未被走回頭路（conf 基線 0.35、無 1280、無 SAHI runtime）
- [ ] 量測口徑：topic 隔離 + kill 重啟換 conf 都寫進腳本/檢查表

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 4 Task <W-x / V-x>（見 docs/superpowers/plans/2026-06-13-lane4-vision-benchmark-model-ab-plan.md §6；
細部步驟與門檻以 docs/superpowers/plans/2026-06-11-phase3-vision-evidence-model-benchmark.md 對應段為權威）。
紀律：
- 全程 offline：獨立 venv（uv venv && uv pip install ...），不碰 runtime code、不裝任何東西進 Jetson runtime。
- demo 錄影只餵程式（ORT/cv2/supervision），絕不餵 LLM。
- 素材/模型/產物不進 git；spike 腳本入 repo 過 flake8 max-line=100。
- 量測口徑：conf 基線 0.35；recall 用 capture_baseline_round.py percep + --gesture-topic /__no_gesture__。
產出要求：可重跑腳本 + 歸檔產物（CSV/MP4/JSONL）+ gate 判定數字。
完成後：單 commit（只含腳本與文件）、PR 描述附產物路徑與 gate 結果。不得 merge，等 Fable review。
```
