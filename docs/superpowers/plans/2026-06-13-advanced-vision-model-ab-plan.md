# Advanced Vision / Object Model A-B 計畫（進階能力升級層）

> **日期**：2026-06-13　**狀態**：PLANNED（待 Roy 審核，審核前不實作、不改 runtime、不改 demo flow、不碰既有檔案）
> **作者 lane**：Cloud B（Advanced Capability Upgrade Plan）
> **硬底線**：2026-04-13 文件初版（週日）／週一繳交；五月展示。**本檔聚焦的是 6/18 期末發表的進階感知能力升級層**（master 決策 B-4：6/18 前 runtime 不換）。
>
> **上游連結（引用，不重抄）**：
> - 主決策 synthesis：[`docs/perception/research/2026-06-11-objdet-upgrade-synthesis-result.md`](../../perception/research/2026-06-11-objdet-upgrade-synthesis-result.md)（矩陣 A-E、conf 0.35 推翻 0.5、imgsz 1280 superseded、§4 上機清單 v1）
> - scale-up 線：[`2026-06-11-yolo26-scaleup-highres-seg-result.md`](../../perception/research/2026-06-11-yolo26-scaleup-highres-seg-result.md)（GO_BENCH_MATRIX）
> - supervision 線：[`2026-06-11-supervision-pawai-fit-report.md`](../../perception/research/2026-06-11-supervision-pawai-fit-report.md)（GO_ADOPT_FOR_EVIDENCE，offline only）
> - PINTO 線：[`2026-06-11-pinto-model-zoo-pawai-fit-report.md`](../../perception/research/2026-06-11-pinto-model-zoo-pawai-fit-report.md)（478_SC/LVFace/AdaFace 候選池）
> - 色彩線：[`2026-06-11-color-recognition-upgrade-result.md`](../../perception/research/2026-06-11-color-recognition-upgrade-result.md)（GO_LAB_NEAREST_NAME）
> - open-vocab 線：[`2026-06-11-open-vocab-indoor-classes-result.md`](../../perception/research/2026-06-11-open-vocab-indoor-classes-result.md)（NEEDS_TEST_VOCAB_REPLAY）
> - **既有排程 lane（引用，不重抄內文）**：[`2026-06-13-lane4-vision-benchmark-model-ab-plan.md`](2026-06-13-lane4-vision-benchmark-model-ab-plan.md)（W1-W5 spike + 上機矩陣日）
> - baseline 事實：[`docs/runbook/2026-06-13-post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md) §4（cup 0.7/1.0/1.5m recall 全高、conf 0.35、痛點＝cell_phone/bottle 混淆）
> - 模組真相：[`docs/pawai-brain/perception/object/README.md`](../../pawai-brain/perception/object/README.md)、其 `CLAUDE.md`（踩坑 #6 input_size、#9 conf 非 runtime param）
> - nav 對齊：[`docs/navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)（C1-C12）、[`2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)（F1-F10）

---

## 這份是什麼

本檔是「**如果時間足夠才測的進階視覺/物件模型能力升級層**」的決策框架——在既有 lane4 排程（W1-W5 spike + 上機矩陣 A-E）**之上**，回答「換不換模型、換哪顆、進不進 6/18 runtime」這層進階決策。每個 sub-capability 走 13 點完整分析 + 強制分級（proven / needs_hitl / research_only / do_not_claim_by_618）。

## 這份不是什麼

1. **不與 Cloud A（保守版 demo flow）重複**：phase conductor / offline fallback / demo 可靠度全歸 Cloud A，本計畫不重複；凡屬 demo flow 可靠度的能力，逐條標「歸 Cloud A，本計畫不重複」。
2. **不重抄 lane4**：lane4 的 W1-W5 spike 步驟、上機矩陣 T0-T7 時程、TRT 預燒 SOP **以 lane4 + synthesis §4 為權威**，本檔只做其上的進階決策層（換模觸發條件、進 runtime 與否、claim 分級），引用既有 lane 用連結。
3. **不是 runtime 行為真相**：runtime 行為以 code / topic schema / baseline-evidence 為準。
4. **不改任何既有檔案**：本任務只 Write 這一個 `advanced-vision-model-ab-plan.md`。

> **鐵律繼承（lane4 §forbidden + synthesis）**：①6/18 前 runtime 一律用現役 `n@640 / conf 0.35`（B-4 不換）；②supervision **絕不進 Jetson runtime**；③demo 錄影**絕不餵 LLM**（量測輸入非理解輸入）；④單次成功 ≠ 可靠（需 n=3）；⑤safe-stop ≠ 繞障（與 nav F2 一致）。

---

## §0 TL;DR（總表）

| # | Sub-capability | 分級 | 優先 | task_type | before_monday | enter_6/18_runtime |
|---|---|---|:---:|---|:---:|:---:|
| A1 | YOLO26n→26s 換模 A/B（640） | needs_hitl | P1 | mixed（WSL export + Jetson 量） | maybe | no |
| A2 | n@960 / 高解析輸入（720p 真像素） | needs_hitl | P1 | mixed（WSL export + Jetson + 動相機） | maybe | no |
| A3 | tiling / crop for small object（SAHI） | research_only | P2 | pure_software | no | no |
| A4 | cup/bottle/phone 類別混淆降低（核心痛點） | needs_hitl | P0 | mixed | yes | no |
| A5 | chair/laptop/bottle 進 demo pool（YOLOE vocab38） | needs_hitl | P1 | mixed | yes | no |
| A6 | HSV12 → Lab-LUT 色彩命名升級 | needs_hitl | P1 | mixed | yes | no |
| A7 | supervision metrics / confusion / video evidence | proven | P0 | pure_software | yes | no（offline only，永不進 Jetson runtime） |
| A8 | PINTO 候選池（478_SC / LVFace / AdaFace） | research_only | P2 | mixed | maybe（478_SC 離線 spike） | no |
| A9 | 最終換模決策框架（keep / switch / hi-res / no-change） | proven | P0 | pure_software | yes | no |

> **分級語意**：`proven`＝有可重跑數據/方法、結論已立（A7 evidence 鏈、A9 決策框架都是純軟體可定案）；`needs_hitl`＝機制可行但增益必須上機/真機量（A1/A2/A4/A5/A6）；`research_only`＝只落 spec / 高風險 / post-6/18（A3/A8）。
> **before_monday `yes`＝純軟體 spike 本週末可跑完**（對齊 lane4 W1-W5 立即開跑）；`maybe`＝需 Jetson 或 Roy 時段；`no`＝research only。
> **enter_6/18_runtime 全為 no（A7 永久 no）**：B-4 預設不換，且每條都卡在「benchmark 過 gate + HITL 過 + Roy 點頭 + 有 rollback」之後——6/18 前沒有任一條能滿足全部前提，故 demo runtime 一律現役。

---

## §1 範圍與邊界

### 與 Cloud A（demo flow 可靠度）的分界

| 主題 | 歸屬 |
|---|---|
| phase conductor / demo 段落編排 / offline fallback / demo 當天可靠度 | **Cloud A**（本計畫不重複） |
| object node 在 demo 行為（cup-only 鎖、conf 0.35、person 靜音、60s dedup） | **既有 runtime / Cloud A demo flow**（本計畫不動，只引用為 baseline） |
| 「換不換模型 / 換哪顆 / 高解析要不要上 / 色彩升不升 / 進不進 runtime」進階決策 | **本計畫（Cloud B）** |
| 「新類別誰消費、講什麼台詞」（brain 編排） | **不在本 lane**（synthesis §5 #5、lane4 §forbidden 7：掛 brain 編排線） |

### 與既有 lane plan（lane4）的分界

| 層 | lane4（既有排程 = aggressive refactor 已排） | 本計畫（進階決策層） |
|---|---|---|
| W1-W5 spike 步驟 / 上機矩陣 T0-T7 時程 / TRT 預燒 SOP | **權威在 lane4 + synthesis §4** | 引用，不重抄 |
| 每線 gate 門檻數值 | lane4 §6 表 + synthesis §4b | 引用 + 在 §5 彙整成 pass/fail 總表（含 nav ladder 對齊欄） |
| 「過 gate 之後做什麼」（換模觸發條件、進 runtime、claim 升級） | lane4 未展開（只到「數據進決策」） | **本計畫 §2 逐能力 + §7 決策表 + §9 觸發條件** |

> **同一上機矩陣日，兩 lane 不各跑一次**：lane4 負責「跑出數字」，本計畫負責「數字出來後的進階裁決」。本計畫的 Jetson/Go2 task 全部標「執行掛 lane4 上機矩陣日，本計畫不另開上機名額」。

---

## §2 逐能力 13 點分析

> 每節輸出 13 點（缺一不可）：1 Desired demo benefit｜2 Current baseline｜3 Candidate options｜4 Required data｜5 Pure software tasks｜6 Jetson tasks｜7 Go2 HITL tasks｜8 Metrics｜9 Pass/fail threshold｜10 Risk｜11 Rollback｜12 Before Monday?｜13 Enter 6/18 runtime?

---

### A1 — YOLO26n vs YOLO26s 換模 A/B（640，FPS/RAM/溫度代價 vs recall/混淆收益）

1. **Desired demo benefit**：用「升模型容量」收掉 cup 的類別混淆（baseline §4：cup 持續被同時認成 cell_phone/bottle），讓「我看到杯子」更不會誤判成 phone/bottle；發表可講「我們量過 n vs s 的代價/收益、有數據決策」。
2. **Current baseline**：runtime＝YOLO26n ONNX + ORT TRT EP FP16 @640、conf 0.35（README、CLAUDE.md #9）。官方規格 n=2.4M/5.4 GFLOPs/COCO mAP 40.9；s=9.5M/20.7/48.6（scale-up F1）。官方 Jetson Orin Nano Super 錨點 n=4.57ms / s=7.17ms engine-only（scale-up F14/F40）。現役 debug Hz 6-8（`publish_fps:8` 限流，scale-up F26），瓶頸在 Python 前後處理非 engine。
3. **Candidate options**：(a) 維持 n@640（現役，B-4 預設）；(b) **s@640**（scale-up 主力刀；GFLOPs +15.3 換官方 +7.7 mAP，scale-up F39 證據量排序最高）；(c) INT8（出局：mAP -3.1 方向相反，F44）；(d) seg 變體（出局：box mAP -1.3、GFLOPs +65%，F5）。
4. **Required data**：cup recall @1.0/1.5/2.0m（30s 靜置 ≈90 幀）、**cup↔cell_phone↔bottle 混淆矩陣**（baseline 真痛點）、node 偵測迴圈 Hz、full-stack RAM delta（tegrastats）、**Jetson 溫度**、近距 7 類 sanity 不退化。錨點來自 W1 WSL export（lane4 W1）。
5. **Pure software tasks**：[pure_software] 引用 lane4 **W1**（WSL `uv venv` export `yolo26s_640.onnx` fixed-shape e2e + ORT CPU 對 S3 錄影抽幀 sanity，確認 shape `(1,300,6)`）——本計畫不重寫，只在 §3 補「混淆矩陣須與 recall 同 run 量出」這條進階要求。
6. **Jetson tasks**：[Jetson needed] 掛 lane4 上機矩陣 **T2（s@640）**：量 §A1.4 全部指標（含本計畫新增的混淆矩陣 owner）。TRT engine 前夜 W6 預燒（synthesis §4d，~3-15 分/顆，**嚴禁與 demo stack 同跑**，1GB workspace 峰值）。
7. **Go2 HITL tasks**：[Go2 motion needed] 無——object 不需 Go2 motion；但 D435 須在 demo 視角（機上 ~30cm 高度，lane4 §8）。Roy 在場操作相機/擺杯。**不涉及 Go2 行走**（與 nav 完全解耦）。
8. **Metrics**：cup@1.5m recall（%）、混淆率＝(cup 框被標成 phone/bottle 的事件數 / cup 總事件數)、Hz、RAM 餘量（GB）、溫度（°C）。
9. **Pass/fail threshold**（synthesis §4b T2 + 本計畫補混淆）：① cup@1.5m recall **≥80%**（@2.0m ≥50% stretch）② 偵測迴圈 **≥3Hz** ③ full-stack RAM 餘 **≥0.8GB** ④ 近距 7 類 sanity 不退化 ⑤ **混淆率較 n@640 baseline 下降**（無硬數字門檻，相對改善即記；baseline 0.7m phone 4/6、bottle 2/6）⑥ **溫度 < 75°C**（保守，現役 object 壓測 48-56°C，README 4/4-4/5）。
10. **Risk**：① s@640 對混淆的改善是假說、未量；recall 已經高（baseline 不掉 recall），s 可能只小幅改混淆不值得換。② nvpmodel 若非 Super MAXN，FPS ÷1.4-1.7（scale-up F22），須 T0 記錄。③ Hackster/AGX 的 TRT engine drift 前科（F16/F23）→ engine 燒完必過 sanity。④ Jetson 供電不穩（XL4015→2464，CLAUDE.md）→ 持續 Super 檔功耗上升的電源側風險（synthesis §5 #1 未裁）。
11. **Rollback**：`OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env 一行切回 n@640（scale-up F34）；TRT cache 按 model stem 分目錄→現役 engine 完好（lane4 §10）。本計畫零 runtime diff。
12. **Before Monday?** maybe — WSL export（W1）本週末可做（yes）；但「換模收益」的裁定點在 Jetson，不在開發機，須等上機矩陣日（Roy 時段，B-3 決策）。故整體 maybe。
13. **Enter 6/18 runtime?** no — B-4 預設不換；即使 T2 過四門檻，「換主 object 模型」是 hard-to-reverse（synthesis §6 應補 ADR），6/18 前不滿足「benchmark 明顯贏 + latency 可接受 + HITL 過 + rollback + Roy 點頭」全部前提。落地 = post-6/18。

---

### A2 — YOLO26n@960 / 更高輸入解析度（誠實處理 1280 插值自欺）

1. **Desired demo benefit**：把遠距小 cup 從 small 物件域（640 下 1.5m≈25px）抬進 medium 域（720p 下≈50px，scale-up F32），理論上撈回遠距 recall；發表可講「我們量過高解析的真實代價」。
2. **Current baseline**：相機只餵 640x480x15（scale-up F30，`start_full_demo_tmux.sh:144-145`）。**注意 baseline §4 已證：conf 0.35 下 cup 0.7-1.5m recall 都不掉**——高解析的價值對「現有 demo 距離」已被削弱，主要意義在 >1.5m（demo 不主打）。
3. **Candidate options**：(a) n@640（現役）；(b) **n@960 + 相機 720p 真像素**（scale-up C，取代 1280）；(c) s@960 + 720p（scale-up D，RAM 最危 +300~600MB / 口徑分歧 §2 #12）；(d) **n@1280 — 已 superseded**（lane4 §2「不得再引用」：相機 640x480 餵 1280 = 純插值自欺，scale-up §4 #1）。
4. **Required data**：同 A1 三距離 recall + 混淆 + Hz + RAM；**額外**：face node CPU 漲幅（共用 color topic，像素×2.25，scale-up F37）、D435 USB 頻寬 / RealSense node CPU。
5. **Pure software tasks**：[pure_software] 引用 lane4 W1（export `yolo26n_960.onnx` / `yolo26s_960.onnx` fixed-shape）。**誠實要求（本計畫新增）**：報告必須明寫「960 配 720p 才有真像素；若相機不動，960 模型亦是插值放大」——不得把插值增益當真增益。
6. **Jetson tasks**：[Jetson needed] 掛 lane4 上機 **T3（n@960+720p，改 `rgb_camera.color_profile:=1280x720x30` 一行）** 與 **T4（s@960+720p，RAM 先量再跑，違反 0.8GB 即棄測）**。改相機 profile 後重啟 camera/face/object。
7. **Go2 HITL tasks**：[Go2 motion needed] 無 Go2 motion；D435 demo 視角 + Roy 操作。
8. **Metrics**：cup recall@距離、混淆率、Hz、**RAM delta（tegrastats 仲裁 synthesis §2 #12 口徑分歧）**、face node CPU 漲幅（紀錄性，不設 fail 線）、溫度。
9. **Pass/fail threshold**（synthesis §4b T3/T4）：同 A1 四門檻 + **T4 RAM delta 違反 0.8GB 即棄測**；溫度 <75°C；720p 下近距 7 類 sanity 不退化。
10. **Risk**：① 動相機的漣漪面廣（face CPU、下游 bbox 座標域假設、USB 頻寬，scale-up F37）→ demo 既有功能回歸風險。② s@960 RAM 邊緣（口徑差 3-4 倍未裁，synthesis §5 #2）。③ 高解析對 demo 距離（≤1.5m）收益已被 baseline 削弱，可能投入不成比例。④ 相機 profile 改動若漏還原 → demo 行為偏移。
11. **Rollback**：相機 profile env 一行切回 640x480x15；`OBJECT_MODEL` 切回 n@640；lane4 §6「當日結束還原現役 + `pawai smoke full`」是硬 gate。
12. **Before Monday?** maybe — WSL export yes；上機裁定要 Roy 時段 + 動相機（風險較 A1 高），整體 maybe。
13. **Enter 6/18 runtime?** no — 動相機改 demo pipeline 風險高，B-4 預設不換；落地 post-6/18 且需先做 face/USB 漣漪面完整回歸。

---

### A3 — tiling / crop for small object（SAHI / InferenceSlicer，小物近拍）

1. **Desired demo benefit**：對遠距小物件理論增益最大（SAHI 論文 inference-only +6.8~5.3 AP，scale-up F41）；但這是 offline upper-bound 探索，非 demo 能力。
2. **Current baseline**：runtime 無 tiling。supervision `InferenceSlicer` 存在（supervision §3.9）但 NEEDS_BENCHMARK。
3. **Candidate options**：(a) 不做（現役）；(b) **offline replay 用 InferenceSlicer/SAHI 量「切片能撈回多少遠距 cup」當 upper-bound 參考**（supervision §7a 路線 2、scale-up Q9）；(c) runtime tiling（**出局**：4 片+全圖 ≈ 5x 推理 → node 6-8Hz 掉到 ~1.5-2Hz，連 ≥3Hz 門檻都過不了，scale-up F41/Q9）。
4. **Required data**：offline replay 對 S3 錄影的「切片 vs 全圖」遠距 cup 召回差；切片延遲倍率（純參考）。
5. **Pure software tasks**：[pure_software] WSL 獨立 venv，對 demo 錄影離線跑 InferenceSlicer，量 recall upper-bound。**非 lane4 W 項排定範圍**（lane4 未列 tiling spike）→ 本計畫標為 **P2 選配 spike，餘力才做**，不佔 W1-W5。
6. **Jetson tasks**：無——runtime tiling 已裁出局，不上 Jetson 量 Hz（synthesis 已封）。
7. **Go2 HITL tasks**：無。
8. **Metrics**：offline 遠距 cup recall（切片 vs 全圖）、切片延遲倍率（參考）。
9. **Pass/fail threshold**：純探索無 gate；若 offline 顯示切片大幅撈回遠距 cup → 記為「未來高解析/換模仍不夠時的 last-resort offline 工具」，**不轉 runtime**。
10. **Risk**：投入產出比低（demo 不主打 >1.5m）；易誘發「順手上 runtime」越界（明令禁止）。
11. **Rollback**：純 offline additive，無 runtime 變動，無需 rollback。
12. **Before Monday?** no — 非 lane4 排定 W 項、P2 餘力項；本週末優先跑 W1-W5。
13. **Enter 6/18 runtime?** no — runtime tiling 已被 synthesis/scale-up 裁出局（Hz 不過），永久 offline-only。

---

### A4 — cup / bottle / phone 類別混淆降低（核心痛點）

1. **Desired demo benefit**：**這是 baseline §4 證實的唯一真痛點**——cup 持續被同時認成 cell_phone/bottle（0.7m: phone 4/bottle 2；1.5m: phone 6/bottle 4）。降混淆 = demo 可講「我看到杯子」更可信，避免 LLM 接到污染事件講錯（注意：person 已靜音、object cup-only 鎖，但混淆事件仍進 brain）。
2. **Current baseline**：n@640 conf 0.35；recall 不掉、**混淆才是問題**（acceptance report §4、synthesis 結論、lane4 §3.1）。混淆率從未以矩陣量化。
3. **Candidate options**：(a) **s@640 升容量降混淆**（=A1，最直接，官方 +7.7 mAP 含更強類別判別）；(b) **時序確認壓混淆**（supervision ByteTrack `minimum_consecutive_frames=3` + 低 conf，offline spike＝lane4 W4；機制：連續 N 幀同類才成 track，壓單幀假類）；(c) **class_whitelist 鎖 cup-only**（現役 demo 已用 `[41,999]`，CLAUDE.md #7）——但這只是「不報 phone/bottle」，**不解模型把 cup 認成 phone 的根因**；(d) open-vocab 加細粒度容器類（=A5，**反而升混淆風險**，§A5.10）。
4. **Required data**：**cup↔cell_phone↔bottle 混淆矩陣**（per 距離、per 配置）；ByteTrack 時序過濾後的假類事件下降數（lane4 W4 量）；s@640 vs n@640 同照片混淆對照。
5. **Pure software tasks**：[pure_software] 引用 lane4 **W4**（`supervision_evidence_spike.py`：S3 錄影 + object JSONL → `sv.Detections` → ByteTrack(N=3) → 量 conf 0.35 vs 0.30+N=3 的假陽性數/track 斷裂）；本計畫補「混淆矩陣須含 phone/bottle 雙向」這條進階要求。
6. **Jetson tasks**：[Jetson needed] 掛 lane4 上機 T1（A0/A1 control）+ T2（s@640）：每配置量混淆矩陣，仲裁「升容量 vs 時序確認」哪個壓混淆有效。
7. **Go2 HITL tasks**：無 Go2 motion；D435 demo 視角。
8. **Metrics**：混淆率（cup→phone、cup→bottle 雙向，per 配置）；時序過濾後假類事件下降數；ByteTrack 在 6-8Hz 的 track 斷裂次數（失敗條件，supervision §6）。
9. **Pass/fail threshold**：① s@640 或時序確認任一使混淆率較 n@640 baseline **明確下降**（相對改善，無硬門檻）② ByteTrack offline：6-8Hz 下 track 不嚴重斷裂（lane4 W4 gate；失敗＝runtime 路線 NO_GO、維持 offline-only）③ cup 自身 recall 不退化（差 <5pp）。
10. **Risk**：① 混淆可能是 nano 容量天花板，s 也壓不下去 → 換模無效。② ByteTrack 在低幀率（6-8Hz）IOU 連續性差 → 時序確認失效（supervision §6 失敗條件）。③ class_whitelist 鎖 cup-only 是 demo 障眼法，不能對外宣稱「解決混淆」。
11. **Rollback**：A1/A2 的 env 切回；W4 純 offline；class_whitelist runtime param 可即時切（CLAUDE.md #7）。
12. **Before Monday?** yes — W4 supervision spike 本週末可跑完（lane4 P1，offline）；混淆矩陣的 WSL 對照（s vs n 同照片）亦可在 W1/W2 順帶出。
13. **Enter 6/18 runtime?** no — 換模（A1）落地 post-6/18；ByteTrack runtime 化另案（supervision §5，需 vendor `byte_tracker/` 或裝套件 benchmark，B-4 不換）；6/18 demo 靠 class_whitelist cup-only + person 靜音 + 60s dedup（既有 runtime）扛混淆，**不對外宣稱降混淆能力**。

---

### A5 — chair / laptop / bottle 是否加入 demo object pool（open-vocab YOLOE vocab38）

1. **Desired demo benefit**：擺脫 cup-only，發表可展示更多居家類（chair/laptop/bottle/藥瓶/遙控器…），對齊 Roy 6/9「發揮 COCO 更多類別、別只 cup-only」（open-vocab F15）。
2. **Current baseline**：code 支援 COCO 80（README）；brain TTS whitelist ~32 類；demo 實際 cup-only（conf 0.35）。**前提修正（open-vocab §1）**：chair(56)/laptop(63)/bottle(39)/remote(65)/bowl(45)/餐具(42-44)/cell_phone(67) **本來就在 COCO 80** → 「加它們進 pool」**不需要 open-vocab**，是 recall/距離 + brain 編排問題。真缺口 = 22 個非 COCO 類（藥瓶/眼鏡/鑰匙/拐杖/輪椅/馬克杯…）。
3. **Candidate options**：(a) **COCO 內擴 pool**（chair/laptop/bottle 直接放開 whitelist + brain 加台詞，零模型改動，但屬 brain 編排線、不在本 lane）；(b) **YOLOE-26 custom vocab38 set-then-export**（open-vocab 唯一候選；同 YOLO26 架構、export 後零 text-encoder 成本，open-vocab §2）解真缺口 22 類；(c) closed-set LVIS（**出局**：搜尋範圍內無獨立供給，是 open-vocab 劣化版，open-vocab §4a）；(d) Grounding DINO / OWL-ViT（**出局**：Orin Nano <1 FPS / 權重 API-gated / 精度不足，open-vocab §5）。
4. **Required data**：per-class recall × 距離（38 類 v0）、**容器類混淆矩陣**（藥瓶↔水瓶↔杯子，open-vocab §6.1）、cup 基線對齊（不退化）、藥瓶 prompt A/B（"pill bottle"/"medicine bottle"/"prescription bottle"，open-vocab Q8）、export ONNX 輸出 shape 驗證（推定 `(1,300,38)+(1,32,160,160)`，open-vocab §2.3）。
5. **Pure software tasks**：[pure_software] 引用 lane4 **W2**（YOLOE vocab38 WSL replay，需 Roy 拍照素材 V0-2：居家物件×0.5/1.0/1.5m，D435 高度 ~30cm 模擬）。
6. **Jetson tasks**：[Jetson needed] 掛 lane4 上機 **T5（條件配置 E，W2 過門檻才執行）**：YOLOE-26s-seg vocab38 @勝者 imgsz；vocab 命中 smoke（藥瓶/鑰匙/眼鏡）；node 類別表臨時換 vocab 對應表（測試 branch，**不進 main**）。TRT W6 預燒（W2 過才燒）。
7. **Go2 HITL tasks**：無 Go2 motion；D435 demo 視角。
8. **Metrics**：新類 1.0m recall、容器混淆率、cup 退步 pp、Hz（seg 形態 ×1.6 GFLOPs 的 Hz check，synthesis §2 #2）、RAM 餘量、溫度。
9. **Pass/fail threshold**（lane4 W2 + synthesis T5）：① demo 核心組新類 1.0m recall **≥0.5** ② 容器混淆 **<30%** ③ cup 退步 **<5pp** → 過＝export 兩版掛配置 E；再不過＝**NO_GO_STAY_COCO80** + guardian 類改走 PINTO 472 屬性線。上機 T5 額外：≥3Hz、RAM 餘 ≥0.8GB、溫度 <75°C。
10. **Risk**：① rare 類 AP_r ~22（S 尺寸 proxy，open-vocab §3）→ 藥瓶等十次七八次標不準；藥瓶連 LVIS 都沒有、零紙面證據。② **加細粒度容器類反而升 cup↔bottle↔藥瓶混淆**（與 A4 痛點衝突，open-vocab §6.1）——這是 A5 與 A4 的直接張力。③ class_id 表意全變，不換對應表會把 vocab id 講成 COCO 名（open-vocab §2.3）。④ 距離不解：新類多比 cup 更小（鑰匙/眼鏡），1m+ recall 預期更差。
11. **Rollback**：vocab 對應表走測試 branch 不進 main；`OBJECT_MODEL` 切回 n@640；當日還原 SOP（lane4 §6）。
12. **Before Monday?** yes — W2 replay 本週末可跑（需 Roy V0-2 拍照素材，~30min；lane4 P0）。
13. **Enter 6/18 runtime?** no — 機制可行但精度未證（NEEDS_TEST_VOCAB_REPLAY）；契約 bump（v2.5→v2.6，synthesis §2 #9 合併工單）+ brain 編排全 post-6/18（lane4 §forbidden 5/7）。6/18 **不可講** open-vocab / 藥瓶/鑰匙辨識（lane4 §13 forbidden）。

---

### A6 — HSV12 vs Lab-LUT color naming（色彩命名升級）

1. **Desired demo benefit**：12 色不夠且不準（紅杯 red↔pink 翻動、米/木色擠錯桶）→ 升 19+1 zh 色名 + Lab 感知距離，發表可講「顏色描述更準更細」（如「米色的碗」）。
2. **Current baseline**：`analyze_bbox_color` 整 bbox crop + 12 色 HSV mask（README §HSV）；contract v2.5 封閉 12 enum（color §F12）。根因排序：③12 色粒度（確定）≥①bbox 背景污染（高）>②光照（中）（color §1）。
3. **Candidate options**：(a) HSV12（現役）；(b) **方案 A：Lab+CIEDE2000 最近色名（32³ LUT，19+1 zh 名）+ 中央 50% 取樣 + 事件級 3 次多數決 + demo AWB lock SOP**（color GO_LAB_NEAREST_NAME，全管線 0.190ms/bbox WSL 實測 ≈ 現役 HSV 0.186ms）；(c) k-means（出局：init 隨機→翻動，color §Q5）；(d) seg mask 取色（出局：seg 變體已被 scale-up 裁出局，color F20）；(e) gray-world / tiny classifier（出局：crop 級毀訊號 / 違反零模型紅線，color Q6/Q8）。
4. **Required data**：54 格 bag 矩陣（9 物 × 3 光照 × 2 距離，含 HSV12 baseline 同 bag 對照）；per-color accuracy、Unknown 率、翻動率；黃燈格 AWB lock 掃描值。
5. **Pure software tasks**：[pure_software] 引用 lane4 **W3**（`color_naming_spike.py`：現役 HSV12 vs Lab-LUT ×（整 bbox / 中央 50%）四組並排，桌面驗紅杯不再 red↔pink 翻動）。
6. **Jetson tasks**：[Jetson needed] 掛 lane4 上機 **T6（色彩 54 格 bag，必備 36 格）**：回 A0 基線配置（n@640、conf 0.35、相機 640x480、AWB AUTO）錄 bag，離線兩法同算。黃燈格加 AWB lock 掃描。
7. **Go2 HITL tasks**：無 Go2 motion；需 9 件色彩物件 + 三光照可控（窗光/黃燈/關主燈）+ Roy 在場佈置。
8. **Metrics**：per-color accuracy（正確色名事件/總事件）、Unknown 率、翻動率（同格色名變化次數/事件數）。
9. **Pass/fail threshold**（color §Q9 / synthesis T6）：per-color accuracy **≥0.8/色**（新色名首輪 ≥0.6 stretch）。**Falsification**：HSV12 + AWB lock 已全色 ≥0.8 → 改判 **NO_GO_KEEP_HSV12**（根因在光照管理非演算法）。
10. **Risk**：① 色名表 v0 錨點邊界要上機調（color §5）。② 動 contract（v2.5→v2.6）+ zh_tables + Studio TS + parity test + 一條 regex 測試需改（color §6）→ 下游同步鏈，與 open-vocab 22 類合併為一次 bump（synthesis §2 #9）。③ AWB lock 只在固定場次有效，Go2 漫遊保持 AUTO（color Q7）。
11. **Rollback**：color node 實作 **6/18 前禁止**（lane4 §forbidden 3）；T6 純 bag 錄製 additive；contract 不動（synthesis §4b T6 不動 contract）。落地 post-6/18 才碰 node。
12. **Before Monday?** yes — W3 color spike 本週末可跑（lane4 P1，offline，桌面驗錨點）。
13. **Enter 6/18 runtime?** no — node 實作 + contract bump 整段 post-6/18（lane4 §forbidden 3/5）；6/18 **不可講「19 色辨識」**（lane4 §13 forbidden）；demo 維持 12 色 HSV（既有 runtime）。

---

### A7 — Supervision metrics / confusion matrix / video evidence（offline only，evidence 用，永不進 Jetson runtime）

1. **Desired demo benefit**：把「cup 0.7m 才看得到」「混淆」從軼事變數字（mAP/ConfusionMatrix）；產出 Studio 等級 annotated evidence MP4（bbox + zh 標籤 + track），供發表展示「機器當下看到什麼」+ 餵 capability scoreboard（supervision §1/§8）。
2. **Current baseline**：object node 手刻 cv2 繪圖 + PIL CJK overlay（README）；無離線 metrics、無 confusion matrix 工具、無 annotated evidence pipeline。supervision 已 GO_ADOPT_FOR_EVIDENCE（offline only）。
3. **Candidate options**：(a) 不做（現役，evidence 空白）；(b) **supervision offline 工具鏈**（WSL：`sv.Detections` 重建 + ByteTrack + annotators + VideoSink + JSONSink + ConfusionMatrix/mAP，supervision §4 Studio Evidence Center）；(c) 自刻 evidence（重複造輪、無 ByteTrack/metrics）。
4. **Required data**：demo 錄影（6/9-6/10 S2/S3，不餵 LLM）+ `/event/object_detected` JSONL（Roy 指認位置，lane4 B-8）。
5. **Pure software tasks**：[pure_software] 引用 lane4 **W4**（`supervision_evidence_spike.py`：重建 `sv.Detections` → ByteTrack(N=3) → zh 標注 MP4 + JSONL，`custom_data` 塞 decision_id）；本計畫補「ConfusionMatrix（cup/phone/bottle）也用 supervision metrics 出，餵 A4/A9 決策」。
6. **Jetson tasks**：**無，且永久不上 Jetson**——supervision 硬依賴完整 opencv-python + matplotlib + scipy，Jetson cv_bridge 綁系統 OpenCV，雙份 OpenCV 共存違反 ≥0.8GB 紀律（supervision §5）。
7. **Go2 HITL tasks**：無。
8. **Metrics**：spike 驗收＝WSL venv 裝成功 + evidence MP4（bbox+zh label+track ID 穩定可見）+ 量化報告（conf 0.35 vs 0.30+N=3 的首偵測幀號/假陽性數/track 斷裂）+ JSONL decision_id join 可行。
9. **Pass/fail threshold**（supervision §6 / lane4 W4）：decision_id join 可行 ∧ 6-8Hz 下 ByteTrack track 不嚴重斷裂（失敗＝**runtime 路線 NO_GO、維持 offline-only**；但 evidence/metrics 價值獨立成立，spike 全失敗仍 GO_ADOPT_FOR_EVIDENCE）。
10. **Risk**：① ByteTrack 在低幀率 track 斷裂（supervision §6 失敗條件）→ 只影響「時序壓混淆」結論，不影響 evidence/metrics。② 誤把 supervision 裝進 Jetson（明令禁止）。③ 依賴版本：`metrics` extra 需 pandas≥2、annotators 需 opencv 完整版（supervision §3.6）。
11. **Rollback**：全 offline additive，WSL 獨立 venv，PawAI repo `git status` 乾淨——**無需 rollback**。
12. **Before Monday?** yes — W4 本週末可跑（lane4 P1，offline；是 Lane 2 annotated clip 的上游）。
13. **Enter 6/18 runtime?** **no（永久）** — supervision 絕不進 Jetson runtime（鐵律）；ByteTrack 若要 runtime 化＝另案 vendor `byte_tracker/`（單檔 MIT）+ benchmark，post-6/18。evidence 工具鏈本就只在 WSL/Studio offline。

---

### A8 — PINTO model zoo 候選池（478_SC / LVFace / AdaFace 等，face/embedding 升級候選）

1. **Desired demo benefit**：① 478_SC 直擊 scoreboard 唯一明確不及格能力（greet gate 的 sitting 判定不穩，PINTO §4.1）；② LVFace/AdaFace 解 6/8 enrollment 漂移 + 低品質臉（運動模糊/中遠距小臉）。發表敘事：「我們有精選候選池 + benchmark 制度」。
2. **Current baseline**：face＝YuNet+SFace+IOU tracking；pose=sitting 用 MediaPipe（baseline §4：sitting 3 次 conf 0.55，two-class work 但 greet gate 文件建議可關，CLAUDE.md VIS-4）。face 辨識 baseline §4＝**unknown sim 0.2287（enrollment 過期，非回歸）**，修法 re-enroll（非換模）。
3. **Candidate options**：(a) 不換（現役；face 辨識先 re-enroll 而非換模，acceptance §4）；(b) **478_SC sitting 分類器 ensemble**（115KB/MIT/CPU <1.5ms，與 landmark 幾何正交，PINTO §4.1 最高 ROI）；(c) **LVFace-T**（ByteDance ICCV2025，76.7MB，**權重 non-commercial** → 學術專題 OK 商用死，PINTO §4.1）；(d) **AdaFace ir18**（CVPR2022 MIT，低品質臉專家，PINTO §4.1）；(e) bbalg 防翻動配方（純 Python MIT，不裝模型就能抄，PINTO §4.1）。
4. **Required data**：478_SC vs MediaPipe sitting agreement/分歧（Go2 視角 person crop，離線）；face recognition sweep（fresh-enrollment + 距離/模糊）不及格才上場（PINTO 觸發條件）。
5. **Pure software tasks**：[pure_software] 478_SC 離線 spike＝lane4 **W5 的一部分**（pose 3-way A/B：MediaPipe vs YOLO26n-pose vs **478_SC**，同餵 `classify_pose`）。**注意：W5 主體是 pose 幾何內戰（gesture YOLO 路線已死，維持 MediaPipe+bbalg，synthesis §3），478_SC 是其中一方**。LVFace/AdaFace 的離線對照 = synthesis §7 標「未完成」、本計畫標 P2 觸發式（face sweep 不及格才動），不佔 W1-W5。
6. **Jetson tasks**：[Jetson needed]（觸發後）478_SC 上 Jetson 估 <1.5ms；但 **W5 晉級者排「下下次上機」**（synthesis §4a W5、lane4 W5 gate），本上機矩陣日不排 pose（GPU 讓給 object，synthesis §2 #4）。LVFace/AdaFace 上機＝post-6/18 face 能力線立項後。
7. **Go2 HITL tasks**：[Go2 motion needed] 無 Go2 motion；478_SC 訓練域是 AVA 電影、Go2 仰角是 out-of-domain → 上線前必錄 Go2 視角 sitting/standing clips 實測（PINTO §4.1，沿用 `capture_baseline_round.py`）。
8. **Metrics**：478_SC sitting 正確率（人工 GT）vs MediaPipe；漏偵幀；分歧分佈。face：sim 分數、TAR@FAR（LVFace IJB-C 88.53%@1e-6 為紙面參考）。
9. **Pass/fail threshold**：478_SC 晉級 gate＝對 MediaPipe **+10pp 或救回 ≥30% 漏偵幀**（lane4 W5、synthesis §4a）；晉級也只排下下次上機。face 換模＝先 re-enroll 後 sweep 仍不及格才觸發（PINTO 觸發條件）。
10. **Risk**：① 478_SC out-of-domain（Go2 仰角/沙發遮擋）→ 離線過、上機崩。② LVFace 權重 non-commercial（候選池必掛旗，PINTO §6）。③ 大 tarball 陷阱（AdaFace 21.3GB / LVFace 1.7GB，要 HF/releases 單檔，PINTO §6.1）。④ face 辨識 baseline 失敗主因是 enrollment 漂移**非模型**（acceptance §4）→ 換模可能是錯方向，先 re-enroll。
11. **Rollback**：全離線候選評估，不部署（lane4 §forbidden 3「PINTO 候選不部署」）；無 runtime 變動。
12. **Before Monday?** maybe — 478_SC 離線 spike 併入 W5 本週末可做（yes 那部分）；LVFace/AdaFace 對照是 P2 觸發式（face sweep 不及格才動），整體 maybe。
13. **Enter 6/18 runtime?** no — 478_SC 晉級也排下下次上機（synthesis §4a）；LVFace/AdaFace post-6/18 face 能力線；6/18 face 辨識靠 re-enroll（非換模）+ pose sitting 靠 `greet_require_sitting` param 防呆（既有 runtime，CLAUDE.md VIS-4）。

---

### A9 — 最終決策框架：keep YOLO26n / switch YOLO26s / high-res only / no runtime change（only benchmark）

1. **Desired demo benefit**：發表可講「我們有明確的換模決策框架 + 觸發條件，不是拍腦袋」——對齊老師「先量化能力再決定換不換模型」（MEMORY 618 scope pivot）。
2. **Current baseline**：B-4＝6/18 前 runtime 不換（n@640/conf 0.35）；synthesis verdict＝BLOCKED_BY_HARDWARE_TEST（決策樹每個分叉都指向上機矩陣日）。
3. **Candidate options（四條決策路徑 + 觸發條件）**：

   | 路徑 | 觸發條件（全部滿足才動） | 落地時機 |
   |---|---|---|
   | **keep YOLO26n**（預設） | 上機矩陣 A1（conf control）已讓 cup@1.5m ≥80% **且** 混淆相對可接受 → B-D 降驗證性質 | 6/18 demo（現役） |
   | **switch YOLO26s@640** | T2 過四門檻 **且** 混淆率較 n 明確下降 **且** Hz≥3 ∧ RAM≥0.8GB ∧ 溫度<75°C **且** Roy 點頭 **且** rollback 驗證（env 切回 + 分目錄 cache） | **post-6/18**（hard-to-reverse，補 ADR，synthesis §6） |
   | **high-res only（n@960+720p）** | T3 過門檻 **且** face/USB 漣漪面回歸通過 **且** Roy 接受動相機風險 | **post-6/18**（動 demo pipeline 風險高） |
   | **no runtime change（only benchmark）** | 上機數據顯示換模收益 < 風險/成本，或任一線未過 gate | 6/18 demo（現役）+ 數據進 scoreboard |
4. **Required data**：A1-A6 全部上機數字（recall/混淆/Hz/RAM/溫度/色彩 accuracy）。
5. **Pure software tasks**：[pure_software] 決策框架文件化（本檔 §7/§9）+ lane4 **V3 決策回填**（每線 GO/NO_GO 寫回 research docs、cup/person/chair baseline 進 scoreboard、矩陣勝者宣告）。
6. **Jetson tasks**：無新增——消費 A1-A6 上機數據。
7. **Go2 HITL tasks**：無。
8. **Metrics**：每條觸發條件有數字背書（無懸空 verdict）；scoreboard cup@distance 數字可溯源。
9. **Pass/fail threshold**：決策表每格觸發條件可逐條對上數據 or forbidden claims（lane4 §13）。
10. **Risk**：① 上機日沒排（B-3 = post-6/18）→ 框架成立但無上機數字，只能用 W replay 數據決策（仍是真數據，lane4 §13）。② 決策被「順手換」誘惑越界（B-4 守門）。
11. **Rollback**：純文件 + scoreboard 回填，無 runtime 變動。
12. **Before Monday?** yes — 框架本身純軟體可定案（本檔）；V3 回填隨數據到位。
13. **Enter 6/18 runtime?** no — 框架的預設輸出就是「6/18 不換」（B-4）；任何 switch 路徑落地 post-6/18 + ADR。

---

## §3 任務清單（task_type + tests + HITL checklist + rollback）

> 凡引用 lane4 W/T 項者，**執行權威在 lane4 + synthesis §4**，本表只列「進階決策層」要附加的事與 gate。所有 Jetson/Go2 task **掛 lane4 上機矩陣日，本計畫不另開上機名額**。

| Task | sub-cap | task_type | 內容（進階層附加） | tests / 驗證 | HITL checklist | rollback |
|---|---|---|---|---|---|---|
| **AV-1 混淆矩陣口徑** | A1/A4 | pure_software | 在 lane4 W1 export sanity + 上機 recall 量測中，**強制同 run 出 cup↔phone↔bottle 雙向混淆矩陣**（不只 recall） | spike 腳本可重跑、混淆矩陣 CSV 歸檔；flake8 max-line 100 | n/a（WSL）；上機段見 AV-5 | 純 offline additive，無 rollback |
| **AV-2 高解析誠實標註** | A2 | pure_software | W1 export 報告明寫「960 配 720p 才真像素；相機不動＝插值」；1280 標 superseded 不引用 | 報告含 insulation 條款；對照 baseline §4「距離不掉 recall」 | n/a | 無 |
| **AV-3 supervision evidence + ConfusionMatrix** | A7/A4 | pure_software | lane4 W4 + 補「ConfusionMatrix(cup/phone/bottle) 用 sv.metrics 出，餵 A9」 | WSL venv import 過、evidence MP4 + JSONL + CM CSV；`git status` 乾淨 | n/a | WSL 獨立 venv，無 rollback |
| **AV-4 色彩 spike 錨點驗證** | A6 | pure_software | lane4 W3（HSV12 vs Lab-LUT 四組並排，紅杯不翻動 sanity） | spike 腳本入 repo、桌面驗錨點 | n/a | node 不動（禁），無 rollback |
| **AV-5 上機矩陣進階裁決** | A1/A2/A4/A5 | jetson_needed | 掛 lane4 上機 T1-T5：每配置回填混淆矩陣 + 仲裁「升容量 vs 時序確認 vs open-vocab」 | 每配置四門檻數字齊（synthesis §4b）；溫度 <75°C；bag 可離線重算 | ☐ T0 記 nvpmodel power mode ☐ engine W6 預燒（不同跑 demo stack）☐ conf 改動 kill 重啟 ☐ D435 demo 視角 ☐ class_whitelist 固定 ☐ **當日還原現役 + `pawai smoke full`** | env 一行切回 n@640；TRT 分目錄 cache 現役完好；測試 branch 不進 main |
| **AV-6 色彩 54 格 bag** | A6 | jetson_needed | 掛 lane4 T6（回 A0 基線錄 bag，離線兩法同算） | per-color accuracy ≥0.8（HSV12 falsification 同 bag）；bag 歸檔 | ☐ 9 件色彩物件 ☐ 三光照可控 ☐ 黃燈格 AWB lock 掃描 ☐ Roy 佈置 | bag 純錄製；node/contract 不動 |
| **AV-7 open-vocab 條件配置 E** | A5 | jetson_needed | 掛 lane4 T5（W2 過門檻才執行；vocab 對應表測試 branch） | 新類 1.0m recall ≥0.5 ∧ 容器混淆 <30% ∧ cup 退步 <5pp ∧ ≥3Hz ∧ RAM≥0.8GB | ☐ W2 replay 先過 ☐ vocab 表測試 branch 不進 main ☐ TRT 預燒 W2 過才燒 | 測試 branch 丟棄；`OBJECT_MODEL` 切回 |
| **AV-8 478_SC 離線對照** | A8 | pure_software | 併入 lane4 W5（pose 3-way A/B 之一方） | sitting 正確率 vs MediaPipe；晉級 gate +10pp / 救回 ≥30% | n/a（離線）；晉級者上機排下下次 | 純離線候選，不部署 |
| **AV-9 決策框架回填** | A9 | pure_software | lane4 V3：每線 GO/NO_GO 回填 research docs + scoreboard；矩陣勝者宣告 | 無懸空 verdict、數字可溯源 | n/a | 純文件 |
| **AV-10 SAHI offline upper-bound（餘力）** | A3 | pure_software | P2 選配：InferenceSlicer 對 S3 錄影量遠距 cup 召回 upper-bound（不轉 runtime） | offline recall 對照；標「last-resort offline 工具」 | n/a | 純 offline，無 rollback |

> **AV-8 nav 對齊聲明**：478_SC 屬 perception sitting，**與 nav capability ladder 無關**（ladder C1-C12 全是 motion 能力）；本計畫無任何 task 觸及 nav motion，故不需 Go2 motion HITL（與 nav lane6 完全解耦）。

---

## §4 三桶分類（Pure software / Jetson / Go2 HITL）

### 桶 1：Pure software（WSL，可 AFK，本週末可跑）

- AV-1 混淆矩陣口徑、AV-2 高解析誠實標註、AV-3 supervision evidence + ConfusionMatrix（A7）、AV-4 色彩 spike（A6）、AV-8 478_SC 離線（A8）、AV-9 決策框架回填（A9）、AV-10 SAHI offline（A3，餘力）。
- 對應 lane4 W1/W2/W3/W4/W5 + V3（**執行權威在 lane4**）。獨立 venv、不碰 runtime code、素材/模型不進 git、flake8 max-line 100。

### 桶 2：Jetson needed（掛 lane4 上機矩陣日，Roy 在場，不另開上機名額）

- AV-5 上機矩陣進階裁決（A1/A2/A4/A5，掛 T1-T5）、AV-6 色彩 54 格 bag（A6，掛 T6）、AV-7 open-vocab 配置 E（A5，掛 T5，W2 過門檻才跑）。
- 前置：W1 模型 rsync（純檔案 5min）+ W6 前夜 TRT 預燒（30-75min，不同跑 demo stack）。
- 478_SC / LVFace / AdaFace 上機＝**下下次上機 / post-6/18**（A8，本日不排）。

### 桶 3：Go2 motion needed

- **無**。本計畫所有 task 都是 object/perception（D435 視角，不需 Go2 行走）。
- **明確聲明**：safe-stop / 繞障 / patrol / approach 等 motion 能力**不在本 lane**——歸 nav lane6（[ladder C1-C12](../../navigation/2026-06-13-nav-capability-ladder.md)）。本計畫零 nav motion task，與 nav ladder 不重疊。

---

## §5 Metrics / Pass-fail threshold 總表

> 對齊 synthesis §4b T1-T6 + acceptance §4 baseline；nav 欄全標「N/A — 非 nav 能力」（本 lane 不涉 ladder C1-C12）。

| sub-cap | recall | confidence | confusion（混淆矩陣） | FPS（Hz） | RAM | Jetson 溫度 | nav ladder 對齊 |
|---|---|---|---|---|---|---|---|
| A1 s@640 | cup@1.5m ≥80%（@2.0m ≥50% stretch） | conf 0.35 基線（kill 重啟改） | 較 n@640 baseline（0.7m phone4/bottle2）明確下降 | ≥3Hz | 餘 ≥0.8GB | <75°C | N/A |
| A2 n@960/s@960+720p | 同上（≥1.5m 才見高解析增益） | conf 0.35 | 同上 | ≥3Hz | T4 違反 0.8GB 即棄測 | <75°C | N/A |
| A3 SAHI offline | offline upper-bound（無 gate） | — | — | runtime 出局（<2Hz） | — | — | N/A |
| A4 降混淆 | cup 自身 recall 退 <5pp | 0.35 vs 0.30+N=3 | **核心指標**：phone/bottle 雙向混淆下降；ByteTrack 6-8Hz track 不嚴重斷裂 | ≥3Hz（換模線） | 餘 ≥0.8GB | <75°C | N/A |
| A5 open-vocab E | 新類 1.0m ≥0.5；cup 退 <5pp | conf sweep 0.25-0.35 | 容器混淆 <30% | ≥3Hz（seg ×1.6 GFLOPs check） | 餘 ≥0.8GB | <75°C | N/A |
| A6 色彩 Lab-LUT | n/a（色彩非 recall） | per-color acc ≥0.8/色（新名 ≥0.6 stretch） | n/a；翻動率（同格色名變化/事件）↓ | n/a（A0 基線錄 bag） | n/a | n/a | N/A |
| A7 supervision | 量化 metrics（mAP/CM）offline | conf 0.35 vs 0.30+N=3 | ConfusionMatrix 是產物 | 6-8Hz track 不斷裂（spike gate） | **永不上 Jetson** | n/a | N/A |
| A8 478_SC | sitting 正確率 +10pp / 救回 ≥30% 漏偵 | — | — | <1.5ms CPU（估） | 忽略不計 | n/a | N/A |
| A9 決策框架 | 消費 A1-A6 | — | 消費 A4/A7 CM | 消費全部 | 消費全部 | 消費全部 | N/A |

> **NO OVERCLAIM 對齊**：以上 gate 全部「過 gate 才記能力」；任一未過＝對外取保守措辭（lane4 §13 forbidden：不可講「cup 2m 可偵測」「支援藥瓶/鑰匙辨識」「19 色辨識」「精準物體分類」「可靠顏色」）。單次成功 ≠ 可靠（混淆矩陣需多距離 n 樣本，acceptance §4 用 6 次/35s）。

---

## §6 Rollback 總表

| sub-cap | runtime 變動 | rollback 機制 | 驗證 |
|---|---|---|---|
| A1 s@640 | 無（6/18 前）；post-6/18 換 `OBJECT_MODEL` | env 一行切回 n@640；TRT cache 分目錄保現役 | `pawai smoke full` 綠（lane4 §6） |
| A2 高解析 | 無（6/18 前） | 相機 profile env 切回 640x480；`OBJECT_MODEL` 切回 | 同上 + face/USB 回歸 |
| A3 SAHI | 無（永久 offline） | 無需 rollback | — |
| A4 降混淆 | 無（6/18 前）；class_whitelist runtime param 可即時切 | A1/A2 env 切回；ByteTrack offline | class_whitelist `ros2 param set` |
| A5 open-vocab E | 無（測試 branch 不進 main） | 丟棄測試 branch；`OBJECT_MODEL` 切回 | 當日還原 SOP |
| A6 色彩 Lab-LUT | 無（node 實作 6/18 前禁；contract 不動） | bag 純錄製；落地 post-6/18 才碰 node + contract | T6 不動 contract（synthesis §4b） |
| A7 supervision | **無（永不進 Jetson runtime）** | WSL 獨立 venv，`git status` 乾淨 | repo diff 對 object_perception/ 為空 |
| A8 PINTO 候選 | 無（不部署，lane4 §forbidden 3） | 純離線候選評估 | 無 runtime diff |
| A9 決策框架 | 無（純文件 + scoreboard） | — | — |

> **全 lane rollback 共識**：6/18 前所有 sub-cap 對 `object_perception/` / contract / zh 表 **零接觸**（lane4 §forbidden 1/3/5）；`git diff` 對 runtime 檔案為空是 Fable review checklist 硬項（lane4 §14）。

---

## §7 決策表（before_monday + enter_6/18_runtime + 理由）

| sub-cap | before_monday | 理由 | enter_6/18_runtime | 理由 |
|---|:---:|---|:---:|---|
| A1 s@640 換模 | maybe | WSL export 本週末可（yes）；換模裁定在 Jetson（Roy 時段 B-3） | no | B-4 不換 + hard-to-reverse 需 ADR；6/18 前不滿足全前提 |
| A2 高解析 | maybe | export yes；上機動相機需 Roy + 風險較高 | no | 動 demo pipeline 風險高；落地 post-6/18 |
| A3 SAHI | no | 非 W1-W5 排定、P2 餘力 | no | runtime tiling 已裁出局（Hz <2） |
| A4 降混淆 | yes | W4 supervision spike + 混淆對照本週末可跑 | no | 換模 post-6/18；6/18 靠 cup-only 鎖 + person 靜音扛 |
| A5 open-vocab | yes | W2 replay 本週末可（需 Roy V0-2 拍照） | no | 精度未證 + contract/brain bump post-6/18；6/18 不可講 |
| A6 色彩 Lab-LUT | yes | W3 color spike 本週末可（桌面驗錨點） | no | node 實作 + contract bump post-6/18；6/18 不可講 19 色 |
| A7 supervision | yes | W4 本週末可（Lane 2 上游） | no（永久） | 鐵律：絕不進 Jetson runtime |
| A8 PINTO 候選 | maybe | 478_SC 併 W5 可（yes）；LVFace/AdaFace P2 觸發式 | no | 478_SC 排下下次上機；face 換模 post-6/18（先 re-enroll） |
| A9 決策框架 | yes | 純軟體框架 + V3 回填 | no | 預設輸出即「6/18 不換」 |

---

## §8 需 Roy 拍板的 open decisions

1. **上機矩陣日要不要排在 6/18 前**（lane4 B-3 三選一）：① 6/15/6/16 全天（數據趕上發表）② 半天精簡（T0-T2+T6 必備）③ post-6/18（零發表風險，W 數據照樣可講）。**本計畫所有 Jetson task 掛此決策**；若 ③，A1/A2/A5/A6 全部只有 W replay 數據（仍真數據），無上機裁定。
2. **V0 素材指認**（lane4 B-8）：object JSONL 位置 + demo 錄影路徑 + W2 居家拍照素材（~30min）。AV-1/AV-3/AV-7 都 block 在此。
3. **nvpmodel power mode / 供電**（synthesis §5 #1，**需電源側意見**）：要不要為 demo 常駐 Super MAXN 檔？功耗上升 vs XL4015→2464 供電不穩前科（8+ 次斷電，20V 安全極限）。影響全部 FPS 解讀（÷1.4-1.7）。
4. **RAM 估算口徑分歧**（synthesis §2 #12 / §5 #2）：goal1（activation 全包）vs goal2（engine 邊際）對 s@960 差 3-4 倍；T4/T5 tegrastats 仲裁一次後，要不要寫成 benchmark 慣例。
5. **A4 vs A5 張力裁決**：open-vocab 加細粒度容器類（藥瓶/水瓶/馬克杯）會**升 cup↔bottle 混淆**（open-vocab §6.1），與 A4「降混淆」目標衝突。若 A4 是 demo 優先，A5 的容器擴充可能要砍——**Roy 定 demo 主軸**（純準 cup vs 多類但混淆）。
6. **478_SC / face 換模方向**：face 辨識 baseline 失敗主因是 enrollment 漂移**非模型**（acceptance §4）→ 確認「先 re-enroll、不換模」是 6/18 路線（A8 預設），LVFace/AdaFace 留 post-6/18 候選池。
7. **contract v2.6 合併 bump 時機**（synthesis §2 #9）：色名 19+1 與 vocab 22 類兩條 GO 後**合併一次** bump（避免靜默漂移）——全 post-6/18，確認不在 6/18 前動。
8. **demo 措辭最終界線**（acceptance §4 / lane4 §13）：可講「近中距杯子穩定偵測 / 手勢穩定 / 坐姿判定」；**不可講** phone/bottle 精準分類、可靠顏色、19 色、藥瓶/鑰匙、2m 可偵測。請 Roy 確認 claim 清單與簡報一致。

---

## 附錄：與 nav capability ladder / claim wording 的對齊聲明

- 本計畫**零 nav motion 能力**，不觸及 [ladder C1-C12](../../navigation/2026-06-13-nav-capability-ladder.md)；§5 metrics 表 nav 欄全 `N/A`。
- safe-stop ≠ 繞障的鐵則（nav F2/C11）在本計畫對應為「object 偵測 ≠ 物體觸發移動」——acceptance/README non-claims 明列「不得用物體觸發機器狗移動」，與 nav 不可講清單一致。
- 本計畫所有 object claim 走 acceptance §4 + README 能力卡（`object.cup` ~1m 近距 CLAIM_WITH_CAVEAT）為真相層；任何升級 claim 須先過 §5 gate + Roy 拍板，未過取保守措辭。
