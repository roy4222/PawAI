# Advanced Gesture / Pose Model Alternatives + 誤觸 / 穩定度 Benchmark（Cloud B）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核，審核前不實作、不改 runtime、不改 demo flow、不碰任何既有檔案
> **作者 lane**：Cloud B（Advanced Capability Upgrade Plan，硬底線 6/18 期末發表）
> **上游連結**：
> - [yolo-pose-gesture 研究結果](../../perception/research/2026-06-11-yolo-pose-gesture-result.md)（verdict=NEEDS_TEST_HITL_CLIPS；gesture YOLO=死路、pose 三方 A/B）
> - [Lane 4 Vision Benchmark / Model A-B plan](2026-06-13-lane4-vision-benchmark-model-ab-plan.md)（gesture 誤觸量化=W7、pose 三方 A/B=W5；本 plan 做其上的進階層，**不重抄**）
> - [Post-Refactor Acceptance Report](../../runbook/2026-06-13-post-refactor-acceptance-report.md)（§4 baseline：gesture min_conf 0.7+3vote 零誤觸、pose sitting/standing two-class conf 0.5-0.55）
> - [手勢 README](../../pawai-brain/perception/gesture/README.md) / [手勢 CLAUDE](../../pawai-brain/perception/gesture/CLAUDE.md)
> - [姿勢 README](../../pawai-brain/perception/pose/README.md) / [姿勢 CLAUDE](../../pawai-brain/perception/pose/CLAUDE.md)
> - [能力 claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)（`gesture.wave`=🔴fail / `pose.basic`/`pose.fall`=⚪insufficient_data，皆 DO_NOT_CLAIM）
> - [Nav capability ladder C1-C12](../../navigation/2026-06-13-nav-capability-ladder.md) / [claim wording F1-F10](../../navigation/2026-06-13-nav-618-claim-wording.md)（本 plan 不含 nav 能力；引用僅為對齊 no-overclaim 詞彙）
>
> **這份是什麼**：在 gesture / pose 既有防線之上的「**進階能力升級層**」——模型替代品評估（誠實呈現 gesture YOLO 死路）、誤觸率量化 benchmark（純軟體、可離線 replay）、靜態手勢與 sitting/standing 穩定度提升、fallen 是否 demo-safe 的風險評估、pose model 三方 latency/accuracy 取捨。所有結論強制分級 proven / needs_hitl / research_only / do_not_claim_by_618。
>
> **這份不是什麼**：
> - **不是 Cloud A 的保守版 demo flow**：phase conductor / offline fallback / demo 可靠度歸 Cloud A，本 plan 不重複。
> - **不重抄 Lane 4**：W5（pose 三方 A/B）與 W7（gesture 誤觸量化）是既有排程；本 plan 引用其 gate，**進階層 = 在其數據出來後才測的「誤觸 ROC 曲線 / 穩定度提升 / fallen 安全性裁定 / 模型晉級門檻」**。引用 lane4 用連結、不複製內文。
> - **不是換 runtime 的授權**：6/18 前換 runtime 模型/參數的預設答案是「不換」（master B-4）。本 plan 全部 spike 為離線 additive，**零 runtime diff**。
> - **不是 nav plan**：nav 能力（C1-C12）歸 Lane 6 / Cloud A，本 plan 任何措辭不觸碰 nav label。

---

## §0 TL;DR — Sub-capability 總表

| # | Sub-capability | 分級 | 優先 | task_type | before_monday | enter_6/18_runtime |
|---|---|---|:---:|---|:---:|:---:|
| G1 | Gesture model alternatives（MediaPipe vs YOLOPose/RTMPose/YOLO26n-pose） | do_not_claim_by_618 | P2 | pure_software | no | no |
| G2 | Gesture false-trigger benchmark（min_conf × min_votes ROC 掃描） | proven | P0 | pure_software | yes | no |
| G3 | thumbs_up / peace / OK 靜態手勢穩定度（demo 收斂 peace→OK→WeGo） | needs_hitl | P1 | mixed | maybe | no |
| P1 | sitting / standing confidence calibration（two-class conf 0.5-0.55 提升） | needs_hitl | P1 | mixed | maybe | no |
| P2 | bending / fallen demo-safe 風險評估（跌倒偵測是否納入 demo） | do_not_claim_by_618 | P0 | pure_software | yes | no |
| P3 | Pose model A/B（MediaPipe Pose vs RTMPose lw vs YOLO26n-pose latency/accuracy） | research_only | P1 | pure_software | maybe | no |

> **一句話結論**：6/18 前唯一值得排的純軟體高價值項是 **G2（誤觸 ROC，把「0.7×3 零 spam」從印象變數字）** 與 **P2（fallen demo-safe 文件裁定，鎖死「不演跌倒」的證據鏈）**；其餘全部是「離線出數字 → 進候選池 → post-6/18 才談換線」，**沒有任何一項進 6/18 demo runtime**（B-4）。

---

## §1 範圍與邊界

### 1.1 與 Cloud A（保守版 demo flow）的分界

| 項目 | 歸屬 | 本 plan 立場 |
|---|---|---|
| phase conductor / demo 段落編排 | **Cloud A** | 不重複；本 plan 只產出「哪個手勢/姿勢穩定到可進 demo」的數據供 Cloud A 取用 |
| offline fallback（無網/模型 down 退路） | **Cloud A** | 不重複 |
| demo 可靠度 / smoke / 彩排 | **Cloud A** | 不重複；G3/P1 的 HITL checklist 與 Cloud A 彩排可併排，但不搶主線 |
| 模型替代品評估 / 誤觸量化 / 穩定度提升 / 跌倒安全性裁定 | **Cloud B（本 plan）** | 全部 |

**硬規則**：本 plan 的任何 task 若觸及 demo flow 可靠度，標註「歸 Cloud A，本計畫不重複」並只保留數據產出面。

### 1.2 與既有 Lane plan 的分界

| 既有 lane | 內容 | 本 plan 的進階層差異 |
|---|---|---|
| [Lane 4 W5](2026-06-13-lane4-vision-benchmark-model-ab-plan.md) | pose 三方逐幀 A/B（MediaPipe vs YOLO26n-pose vs 478_SC），gate=+10pp 或救回 ≥30% 漏偵 | 本 plan **P3** = W5 跑完後的「latency/accuracy 取捨決策表 + 晉級下下次上機的配置門檻」，不重跑 W5 |
| [Lane 4 W7](2026-06-13-lane4-vision-benchmark-model-ab-plan.md) | gesture 誤觸數 @ min_conf{0.5,0.7,0.8}×min_votes{1,3,5} 矩陣（純紀錄性） | 本 plan **G2** = 把 W7 的矩陣**升級成 ROC（誤觸 vs 漏觸 雙軸）+ 統計顯著性 + 最優工作點建議**，並補「誤觸來源歸因」。W7 是計數，G2 是決策曲線 |
| [yolo-pose-gesture result](../../perception/research/2026-06-11-yolo-pose-gesture-result.md) | verdict 已收斂：gesture YOLO 死路、pose 17kpt 可行、改寫成本~0 | 本 plan **G1/P3** 引用其 §1-§5 結論，**不重新論證**；只補「替代品終裁表 + 為何維持 MediaPipe 的一頁誠實說明」 |

**鐵律繼承（自 Lane 4 §1）**：demo 錄影**絕不餵 LLM**（量測輸入非理解輸入）；任何替代模型不進 Jetson runtime；數據出來前不換任何 runtime 模型/參數。

### 1.3 No-overclaim 對齊

本 plan 涉及的能力在 [claim matrix](../../mission/2026-06-18-capability-claim-matrix.md) 的 trusted 狀態：
- `gesture.wave` = 🔴 **fail**（DO_NOT_CLAIM）；靜態手勢（palm/fist/index/thumbs_up/peace/ok）= **fallback/demo-only，未經 trusted baseline 量測**。
- `pose.basic`/`pose.fall` = ⚪ **insufficient_data**（DO_NOT_CLAIM）；跌倒=future、`enable_fallen:=false`。

**單次成功 ≠ 可靠**（需 n=3，沿用 ladder §1 鐵則）。本 plan 任何 HITL 穩定度宣稱都以 n=3 為門檻，未達一律標 `needs_hitl` 不升 `proven`。nav 不在本 plan 範圍——不觸碰 C1-C12 / F1-F10。

---

## §2 逐能力 13 點分析

---

### G1 — Gesture model alternatives（MediaPipe baseline vs YOLOPose / RTMPose / YOLO26n-pose）

**分級：`do_not_claim_by_618`｜優先：P2｜task_type：pure_software**

**1. Desired demo benefit**
理論上「換一顆更準的手勢模型」可降低 palm↔ok 混淆（acceptance §4 觀測到 open_palm 被認成 ok）、提升遠距手部偵測（gesture.wave 6/4 fail 根因之一 = 1.5m hand detection 間歇）。

**2. Current baseline**
- 主線 = **MediaPipe Gesture Recognizer**（CPU 7.2 FPS，21 手部關鍵點），靜態 palm/fist/index/thumbs_up/peace + 自製幾何 ok（`detect_ok_circle`）+ 時序 wave（`WaveDetector`）。
- `gesture.wave` 6/4 trusted = 🔴 **fail**（n=9, recall=0.0，根因 = 1.5m hand detection 間歇 + WaveDetector 門檻過嚴）。
- 靜態手勢 = fallback/demo-only，未經 trusted baseline。

**3. Candidate options**
| 選項 | 結論 | 來源 |
|---|---|---|
| (a) Ultralytics 官方 hand-kpt 模型 | **不存在**——pretrained pose 只有 COCO person 17kpt 一類 | [result F39](../../perception/research/2026-06-11-yolo-pose-gesture-result.md) |
| (b) 社區 hand-kpt YOLO（`marceloeatworld/yolo26-training` / `chrismuntean/YOLO11n-pose-hands`） | **死路**：訓練資料是 MediaPipe 蒸餾（品質天花板=現任）、license=CC BY-NC-SA 4.0 非商用 / AGPL、用 GPU 換 CPU 現任已有的東西 | [result F40-F43](../../perception/research/2026-06-11-yolo-pose-gesture-result.md) |
| (c) RTMPose-wholebody（含手部 keypoint） | GPU 91-99% 滿載（pose README 已記），與 Whisper CUDA 衝突；wholebody 手部精度未驗 | pose README §操作限制；result F32 |
| (d) YOLO26n-pose 接管 wave | **僅 wave 可被接管**（body wrist 餵 WaveDetector）；palm/fist/ok/peace 等靜態手勢離不開 21 點手部 | [result F26-F27](../../perception/research/2026-06-11-yolo-pose-gesture-result.md) |
| (e) **維持 MediaPipe + bbalg 防翻動 + 條件式 WHC/PGC** | **唯一合理線**（零模型成本） | [result F43-F44](../../perception/research/2026-06-11-yolo-pose-gesture-result.md) |

**4. Required data**
本能力**不需新數據**——替代品的死路屬性是 license/蒸餾鏈/官方缺權重的事實判定，已在 yolo-pose-gesture result 完成。唯一可補的是「為何維持 MediaPipe」的一頁誠實說明（文件，非數據）。

**5. Pure software tasks**
- T-G1-1 [pure software]：寫「手勢模型替代品終裁表」一頁（引用 result F39-F43），明示 (a) 不存在 / (b) 死路三重理由 / (c) RTMPose GPU 衝突 / (d) 只能接管 wave / (e) 維持 MediaPipe。**這是文件，不是 benchmark**。

**6. Jetson tasks**
無（替代品全部紙面出局，不值得佔 Jetson 名額）。

**7. Go2 HITL tasks**
無。

**8. Metrics**
無新量測（決策依據 = license/權重存在性/蒸餾鏈，已定）。

**9. Pass/fail threshold**
不適用——這是「不換」的負面結論，gate = 「終裁表逐條對得上 result 證據、無走回頭路（不得重提社區 hand-kpt YOLO 為候選）」。

**10. Risk**
唯一風險 = 有人未讀 result 又重啟「換手勢模型」討論，浪費時段。終裁表的存在就是防線。

**11. Rollback**
無（純文件 additive，無 rollback 需求）。

**12. Should we do before Monday？** **no**
理由：結論已定（gesture YOLO 死路），終裁表是 1 小時文件工作、無數據產出、不阻塞任何 lane。可順手在 V3 回填階段一併寫，不單獨排時段。

**13. Should it enter 6/18 demo runtime？** **no**
理由：所有替代品出局，runtime 維持 MediaPipe（B-4 不換）。demo 措辭：`gesture.wave` 仍 DO_NOT_CLAIM、靜態手勢 demo-only。

---

### G2 — Gesture false-trigger benchmark（min_conf × min_votes ROC 掃描）

**分級：`proven`（指「誤觸率有可溯源數字」這件事 proven，非手勢能力 proven）｜優先：P0｜task_type：pure_software**

> ⚠️ 措辭防呆：本能力 proven 的是「**誤觸 benchmark 方法論 + 現役值的誤觸數字**」，**不是** gesture.wave/靜態手勢的能力 pass。claim matrix `gesture.wave`=fail 不因本 benchmark 改變。

**1. Desired demo benefit**
acceptance §4 記「3 手勢只各觸發 1 次（門檻有效），零誤觸 spam」——但**誤觸率從未量化**（Lane 4 §2 明記）。量化後可在發表講「誤觸防線是量出來的工作點」而非「感覺沒亂跳」，並驗證現役 `min_conf=0.7 × min_votes=3`（demo 凍結值）是否在 ROC 最優區。

**2. Current baseline**
- 防線值：`gesture_recognizer_min_conf=0.7` + `gesture_min_votes=3` + `gesture_stable_s=0.5`（demo 凍結，[Lane 4 §2](2026-06-13-lane4-vision-benchmark-model-ab-plan.md)）。
- acceptance §4 觀測：thumbs_up/peace/open_palm 各觸發 1 次、零 spam（n 極小、非統計量）。
- Lane 4 **W7** 已排「誤觸數 @ min_conf{0.5,0.7,0.8}×min_votes{1,3,5} 矩陣」（純紀錄性）。

**3. Candidate options**
| 選項 | 說明 |
|---|---|
| (a) 沿用 W7 矩陣（9 格計數） | Lane 4 已排，計數而非曲線 |
| (b) **G2 進階：ROC 雙軸**（誤觸率 vs 漏觸率），加 stable_s 第三維 sweep {0.3,0.5,0.7} | 本 plan 增量：把計數升級成決策曲線 + 最優工作點 |
| (c) 加「誤觸來源歸因」 | 標註每次誤觸的 ground-truth label（palm↔ok 混淆？過渡幀？背景手？）→ 指出是 conf 問題還是 votes 問題還是混淆問題 |

**4. Required data**
- demo 錄影**非手勢段**（誤觸的分母 = 沒比手勢卻觸發）+ demo 錄影**手勢段**（漏觸的分母 = 比了手勢沒觸發）。
- 素材路徑需 Roy 指認（Lane 4 V0/B-8 同款 blocker）。**不可用則順延補錄**（同 W5 step 0 SOP）。

**5. Pure software tasks**
- T-G2-1 [pure software]：獨立 venv（`uv venv && uv pip install mediapipe opencv-python`），離線跑 MediaPipe Gesture Recognizer 對非手勢段抽幀，逐幀記原始 gesture+score，**在腳本層重放投票/穩定 gate**（複製 `vision_perception_node` 的 vote+stable_s 邏輯，不 import runtime、不改 runtime）。
- T-G2-2 [pure software]：對 min_conf{0.5,0.7,0.8} × min_votes{1,3,5} × stable_s{0.3,0.5,0.7} 全格算誤觸次數/分鐘；手勢段算漏觸率 → 出 ROC CSV。
- T-G2-3 [pure software]：誤觸來源歸因（人工標每次誤觸的真實情境）→ 標出現役值（0.7×3×0.5）在 ROC 上的位置 + 是否有 Pareto 更優工作點（記為 post-6/18 候選，不改 runtime）。

**6. Jetson tasks**
無（離線 replay，CPU MediaPipe 在 WSL 跑得動）。

**7. Go2 HITL tasks**
無。

**8. Metrics**
- 誤觸率（false trigger / 分鐘，非手勢段）。
- 漏觸率（missed / 真實手勢數，手勢段）。
- 每格 ROC 點（FP-rate, FN-rate）。
- 現役值的工作點座標 + 與 Pareto front 距離。

**9. Pass/fail threshold**
本 task 是**紀錄性 benchmark**，gate = 「現役值誤觸率有數字、ROC 曲線可重跑、現役值落點明確」。**不設換線門檻**（即使找到更優工作點，6/18 前不改凍結值——B-4）。若現役值誤觸率 >1/分鐘 → 標為「post-6/18 調參候選」交 Roy 決策（仍不改 6/18 凍結值）。

**10. Risk**
- 素材不足（非手勢段太短 → 誤觸分母小、統計力弱）→ rollback：標「樣本不足、僅供方向性參考」，不下強結論。
- 腳本層重放的 vote/stable 邏輯與 runtime 不一致 → 用 runtime 同款常數（README §0.5s gate）逐行對照，加單測對拍。

**11. Rollback**
純離線 additive，無 runtime 變動 → 無 rollback。腳本入 repo 需過 blocking flake8（max-line 100）、`git status` 乾淨（素材不進 git）。

**12. Should we do before Monday？** **yes**
理由：① 純軟體、可 AFK、零硬體；② 高價值——把 acceptance 的「零 spam」印象變成發表可講的 ROC 數字；③ 不阻塞、不碰 runtime；④ 是 Lane 4 W7 的自然延伸，順勢做掉。**唯一前置 = Roy 指認非手勢段素材**（無則順延補錄、不 block 其他 lane）。

**13. Should it enter 6/18 demo runtime？** **no**
理由：benchmark 是離線決策數據，現役凍結值（0.7×3）不因數字更動（B-4）。即使找到 Pareto 更優工作點，也是 post-6/18 調參候選。demo runtime 零變動。

---

### G3 — thumbs_up / peace / OK 靜態手勢穩定度（demo 收斂 peace→OK→WeGo）

**分級：`needs_hitl`｜優先：P1｜task_type：mixed（pure software 重放 + Jetson/Go2 HITL 觸發驗證）**

**1. Desired demo benefit**
demo 已收斂為 **peace(YA)→OK→WeGo** confirm flow（acceptance 附錄 Task 2：`peace_wego_confirm=True` / `thumbs_up_demo_ack=False`，thumbs_up 已關）。穩定度提升 = peace 與 OK 在 demo 距離（~1.5-2m）下穩定觸發、palm↔ok 不混淆，讓 confirm flow 不卡。

**2. Current baseline**
- acceptance §4：thumbs_up conf 0.80（1 次）、peace conf 1.00（1 次）、open_palm 被認成 ok（conf 0.70，palm↔ok 混淆 minor）。
- acceptance 附錄 Task 2：peace→OK→WeGo confirm flow **PASS**（Roy 親眼 + trace 佐證），但 n=1。
- 有效範圍 ~2m（4/8 會議）；僅單人。

**3. Candidate options**
| 選項 | 說明 |
|---|---|
| (a) 純軟體：palm↔ok 混淆量化（離線 replay confusion matrix） | 找出混淆是 conf 問題還是 `detect_ok_circle` 幾何閾值問題 |
| (b) 幾何閾值微調（`detect_ok_circle` 的 `hand_width×0.3`） | 零模型成本，post-6/18 候選 |
| (c) HITL：peace/OK n=3 觸發驗證（demo 距離） | 把 confirm flow 從 n=1 升 n=3 |

**4. Required data**
- 離線：demo 錄影手勢段（含 peace/OK/palm 各數次）→ confusion matrix。
- HITL：Jetson + D435 + Roy 在 demo 距離比 peace/OK 各 ≥3 次。

**5. Pure software tasks**
- T-G3-1 [pure software]：離線 replay demo 錄影手勢段 → peace/OK/palm/thumbs_up confusion matrix；標出 palm↔ok 混淆的 conf 分布 → 判定混淆來源（recognizer 分類 vs `detect_ok_circle` 幾何）。
- T-G3-2 [pure software]：若混淆來自幾何閾值 → 提出 `detect_ok_circle` 閾值候選值（**僅文件，不改 runtime**）。

**6. Jetson tasks**
- T-G3-3 [Jetson needed]：在 Jetson 起 `vision_perception`（`gesture_backend:=recognizer`，demo 主線組合），對 demo 距離觀測 peace/OK conf 與觸發（不發 Go2 motion，純感知觀測）。

**7. Go2 HITL tasks**
- T-G3-4 [Go2 motion needed]：peace→OK→WeGo 全鏈 n=3（含 Go2 wiggle motion）。**歸 Cloud A demo flow 彩排可併**——本 plan 只負責「穩定度數據」面，confirm flow 編排歸 Cloud A，本計畫不重複。**需 e-stop 就位**（acceptance abort criteria #6）。

**8. Metrics**
- palm↔ok 混淆率（confusion matrix off-diagonal）。
- peace/OK 觸發成功率 @ demo 距離（n=3）。
- confirm flow 端到端成功率（peace→OK→WeGo，n=3）。

**9. Pass/fail threshold**
- 離線：confusion matrix 產出、palm↔ok 混淆來源判定。
- HITL：peace/OK 各 n=3 全觸發 + confirm flow n=3 全完成 → 可標「demo 距離靜態 confirm 手勢穩定（窄版、n=3）」；**未達 n=3 維持 `needs_hitl`，不升 proven**。
- ⚠️ 即使 n=3 過，claim matrix `gesture.wave`（動態 wave）仍 fail——本 task 只證**靜態 confirm 手勢**，不得洗成「手勢能力 pass」。

**10. Risk**
- palm↔ok 混淆在現場拖慢 confirm flow → 風險控制 = 台詞退「比 OK 我就開始」（acceptance 附錄已是此台詞），混淆時操作員可重比。
- HITL 需 e-stop（含 Go2 wiggle motion）→ 無 e-stop 不開（abort criteria #6）。

**11. Rollback**
- 離線部分 additive 無 rollback。
- 任何閾值候選**不進 runtime**（B-4）→ 無 runtime rollback 需求。HITL 若混淆嚴重 → demo 退「只演 peace 單手勢 + 語音 confirm」fallback（歸 Cloud A）。

**12. Should we do before Monday？** **maybe**
理由：離線 confusion matrix（T-G3-1/2）值得做（純軟體、補強 G2）；HITL（T-G3-3/4）**maybe**——需 Roy + Jetson + e-stop + Go2，與 Cloud A demo 彩排搶時段，建議併入 Cloud A 的 confirm flow 彩排一起跑，不單獨排。

**13. Should it enter 6/18 demo runtime？** **no（行為已在 runtime，本 task 不新增 runtime 變動）**
理由：peace→OK→WeGo confirm flow **已是現役 runtime 行為**（acceptance 附錄 Task 2 已 PASS）；本 task 只是**量化其穩定度 + 提供混淆改善候選**，不改任何 runtime 參數/模型。閾值候選 post-6/18 才談。

---

### P1 — sitting / standing confidence calibration（two-class conf 0.5-0.55 提升）

**分級：`needs_hitl`｜優先：P1｜task_type：mixed（pure software 重放 + Jetson HITL 觀測）**

**1. Desired demo benefit**
sitting 是 greet gate 的**硬依賴**（VIS-4：known face stable + 3s 內 pose=sitting + cooldown）。sitting 判定穩定 = greet「roy 歡迎回來」能在 Roy 坐下時觸發（acceptance 附錄 Task 2 已順帶證 greet）。conf 0.5-0.55 偏中等 → 提升信心 = greet 更穩、Studio pose chip 不抖。

**2. Current baseline**
- acceptance §4：sitting 3 次 conf 0.55 / standing 2 次 conf 0.50；坐站轉換正確判定（two-class 模式 work）。
- `pose.basic` 6/04 trusted = ⚪ **insufficient_data**（無 pose observer，n=0）。
- two-class 模式：only sitting/standing 發事件（fallen/akimbo/knee_kneel 等不在 two-class 發）。
- 6/9 修法全在規則參數層：`pose_min_avg_score` 注入、`sitting_trunk_max_deg` 35→45、two_class 粗分類、20 幀投票 buffer。

**3. Candidate options**
| 選項 | 說明 |
|---|---|
| (a) 純軟體：sitting/standing 逐幀 confidence 來源剖析（離線 replay） | conf 偏低是 avg_score 眼耳偏移（result F18：MediaPipe 眼/耳 4 點恆 0 壓低 avg ~24%）還是規則邊界 |
| (b) `pose_min_avg_score` / `sitting_trunk_max_deg` sweep（離線） | 找出讓 sitting conf 提升、不增誤判的參數區（**僅文件候選，不改 runtime**） |
| (c) 478_SC ensemble（外觀分類器補強幾何） | [result F46](../../perception/research/2026-06-11-yolo-pose-gesture-result.md)：SC 與 landmark 幾何正交、建議 ensemble。**屬 Lane 4 W5 範圍** → 本 plan 引用不重跑 |
| (d) 建 pose observer 工具收 ground-truth | claim matrix `pose.basic` Next Retest 明列「建 observer + HITL 收 ground-truth 才可談 pass」 |

**4. Required data**
- 離線：demo 錄影坐姿段（S2 認人坐姿，acceptance/Lane 4 W5 同素材）逐幀 17kpt + conf。
- HITL：Jetson + D435 + Roy 坐/站轉換，收 ground-truth 樣本（pose observer，目前不存在）。

**5. Pure software tasks**
- T-P1-1 [pure software]：離線 replay S2 坐姿段 → sitting/standing 逐幀 conf 來源剖析（拆解 avg_score 眼耳偏移 vs 規則邊界，引用 result F18）。
- T-P1-2 [pure software]：`pose_min_avg_score` / `sitting_trunk_max_deg` 離線 sweep → 提出讓 sitting conf 提升且不增誤判的參數候選（**僅文件，不改 runtime**）。

**6. Jetson tasks**
- T-P1-3 [Jetson needed]：在 Jetson 起 pose pipeline + 建簡易 pose observer（記 `/event/pose_detected` 樣本 + 人工 ground-truth label），收 sitting/standing 各 ≥10 樣本。**這是 claim matrix `pose.basic` 升 pass 的前置**（建 observer）。**屬量測工具，不改 runtime 行為**。

**7. Go2 HITL tasks**
無（pose 觀測不需 Go2 motion；greet 觸發是 Brain 行為，歸 Cloud A demo flow，本 plan 不重複）。

**8. Metrics**
- sitting/standing precision/recall（vs 人工 ground-truth，n≥10）。
- sitting conf 分布（現役 0.55 → 候選參數下的分布）。
- greet gate 觸發成功率（sitting → greet，**歸 Cloud A**，本 plan 不量）。

**9. Pass/fail threshold**
- 離線：conf 來源剖析完成 + 參數候選有數據背書。
- HITL：sitting/standing precision ≥ 0.8 @ n≥10（demo 正面距離）→ 可標「sitting/standing two-class 在正面 demo 距離可用（窄版、n≥10）」。**未建 observer / n<10 維持 `needs_hitl`、claim matrix 維持 insufficient_data**。
- ⚠️ 任何結論不得宣稱「坐下偵測已 pass」（claim matrix Non-Claims）——除非建了 observer + n≥10 + precision ≥0.8。

**10. Risk**
- 側面坐姿 hip_angle/trunk_angle 偏差（pose README 已記）→ demo 建議正面面向攝影機（風險控制，歸 Cloud A 編排）。
- 參數 sweep 過擬合 demo 錄影 → 用 hold-out 段驗證 + 標「僅 demo 距離正面適用」。

**11. Rollback**
- 離線 additive 無 rollback。
- 參數候選**不進 runtime**（B-4）→ 無 runtime rollback。pose observer 是新增量測工具（additive），不改既有行為。

**12. Should we do before Monday？** **maybe**
理由：離線剖析（T-P1-1/2）值得做（純軟體、與 Lane 4 W5 共用素材）；建 pose observer（T-P1-3）**maybe**——需 Jetson，但這是 `pose.basic` 升 pass 的硬前置，若 Roy 有 Jetson 時段值得順手做（不需 Go2、不需 e-stop）。

**13. Should it enter 6/18 demo runtime？** **no**
理由：sitting 判定**已是現役 runtime 行為**（greet gate 依賴它）；本 task 量化穩定度 + 提供參數候選，不改 runtime。參數調整 post-6/18 才談（B-4）。demo 措辭維持「坐姿判定（窄版、正面）」，不講「坐下偵測 pass」。

---

### P2 — bending / fallen demo-safe 風險評估（跌倒偵測是否納入 demo）

**分級：`do_not_claim_by_618`｜優先：P0｜task_type：pure_software**

**1. Desired demo benefit**
明確裁定「fallen 是否納入 demo」並鎖死證據鏈——避免發表時誤講「跌倒守護/緊急警報」。bending（彎腰「請小心喔」）是 demo 互動段可用項，fallen 是 future 非緊急。本能力的「benefit」= **誠實邊界本身**（防 overclaim）。

**2. Current baseline**
- `pose.fall` claim matrix = DO_NOT_CLAIM、claim_level=future、`brain_allowed=false`、demo 維持 `enable_fallen:=false`。
- fallen TTS 兩條路徑皆 mute（5/8：`_on_fall_alert` 與 `_on_pose_event` 的 POSE_TTS_MAP 移除 fallen key），Studio 仍顯示紅 alert chip（視覺保留、不發語音）。
- 已知幻覺：無人時鎖定衣架/椅子判 fallen（4/8 會議確認頻繁）；推車/椅子 mid-frame 假跌倒（5/8 ankle-on-floor gate 緩解：`ankle_y/image_height > 0.7` 才認）。
- result F20：COCO 躺姿通病，需 rotation-augmented 重訓才穩；F9：YOLO 系亦弱（倒立/罕見姿勢）→ **換模型也救不了 fallen**。
- bending：trunk>30°/knee>130°/hip<160°/bbox≤1.0 → 「請小心喔」(Active 互動段)。

**3. Candidate options**
| 選項 | 說明 |
|---|---|
| (a) 維持 `enable_fallen:=false`（demo 不演跌倒） | 現役決策，最安全 |
| (b) 開 fallen 僅 Studio 紅 chip 顯示、TTS 全 mute | 現役已是此態（chip 留、語音 mute） |
| (c) 量化 fallen 幻覺率（離線 replay 無人/有椅場景） | 把「幻覺頻繁」變數字、佐證為何不演 |
| (d) 換模型救 fallen | **死路**（result F9/F20：COCO/YOLO 躺姿通病皆需重訓）→ 不做 |

**4. Required data**
- 離線：含椅子/衣架/推車的 demo 錄影段（無人或彎腰）→ fallen 誤觸幀數。
- bending 互動段錄影（彎腰「請小心」觸發）→ 確認 bending 與 fallen 不混淆。

**5. Pure software tasks**
- T-P2-1 [pure software]：離線 replay 含家具/無人段 → 量 fallen 幻覺率（誤觸幀/分鐘），佐證「為何 demo 不演跌倒」。
- T-P2-2 [pure software]：寫「fallen demo-safe 裁定」一頁——結論 = **不納入 demo**（`enable_fallen:=false`），證據鏈 = 幻覺率數字 + result F9/F20（換模型救不了）+ claim matrix future。明示對外**絕不提跌倒/守護/緊急警報**。
- T-P2-3 [pure software]：bending vs fallen 離線分離度驗證（彎腰段不被吃成 fallen，deep-bending guard 有效性確認）。

**6. Jetson tasks**
無（離線 replay；幻覺率不需 Jetson 即可量）。

**7. Go2 HITL tasks**
無（fallen 不演 = 不需 motion）。

**8. Metrics**
- fallen 幻覺率（誤觸幀/分鐘，無人/家具場景）。
- bending 與 fallen 的混淆率（deep-bending guard 有效性）。

**9. Pass/fail threshold**
本能力**不追求 pass**——gate = 「fallen demo-safe 裁定文件成文、幻覺率有數字、bending/fallen 分離度確認、`enable_fallen:=false` 證據鏈鎖死」。
**強制 do_not_claim_by_618**：對外絕不講跌倒偵測可靠/防跌倒守護/緊急警報已 pass（claim matrix Non-Claims）。「EMERGENCY」是內部 routing 標籤，非已驗證能力。

**10. Risk**
- demo 現場 Studio 紅 chip 被觀眾/老師問「這是跌倒嗎」→ 風險控制 = 旁白**絕不提跌倒**（pose README Fallback：鏡頭帶到紅標時旁白絕不提跌倒）。
- 有人重啟「demo 演跌倒守護」討論 → 裁定文件 = 防線。

**11. Rollback**
無 runtime 變動（`enable_fallen:=false` 維持現役）→ 無 rollback。純文件 + 離線數據 additive。

**12. Should we do before Monday？** **yes**
理由：① 純軟體、零硬體；② **高價值低風險**——鎖死「不演跌倒」的證據鏈是 6/18 overclaim 防線的關鍵一環；③ 幻覺率數字佐證決策，發表被問時有據可答；④ 不阻塞任何 lane。

**13. Should it enter 6/18 demo runtime？** **no**
理由：`enable_fallen:=false` 維持現役，fallen 不進 demo runtime。bending（「請小心喔」）**已是現役互動段行為**，本 task 不新增 runtime 變動，只確認 bending/fallen 分離度。

---

### P3 — Pose model A/B（MediaPipe Pose vs RTMPose lw vs YOLO26n-pose latency/accuracy 取捨）

**分級：`research_only`｜優先：P1｜task_type：pure_software（離線 A/B）；晉級後上機=Jetson，但 post-6/18**

**1. Desired demo benefit**
若某 pose 模型在 Go2 仰角 + 居家場景下 sitting 判定明顯更準 → 長期可提升 greet 穩定 + 多人就緒（YOLO26n-pose 原生多人 + person bbox 副產品）。**6/18 不換**——這是 post-demo 升級路線的決策數據。

**2. Current baseline**
- 主線 = **MediaPipe Pose**（CPU，GPU 0%，L1 單模 13.5 FPS / 共存口徑 18.5 FPS）。
- RTMPose lw = 備援（GPU 91-99% 滿載，與 Whisper CUDA 衝突）。
- YOLO26n-pose：紙面 = 純推理 5-8ms、node 內 15-25ms（10-15Hz）、RAM +50-400MB、GPU +5-8% 佔空比；**改寫成本~0**（classify_pose 本來就吃 COCO 17kpt，result F11-F16）；但 **GPU-0% 基石作廢**（result F38）。

**3. Candidate options**
| 選項 | latency | accuracy 取捨 | 來源 |
|---|---|---|---|
| MediaPipe Pose（現役） | CPU ~74ms/幀、13.5 FPS、GPU 0% | sitting 6/9 參數修正後待量；眼/耳 4 點恆 0 壓 avg_score | result F36/F18 |
| RTMPose lw（備援） | GPU 91-99% 滿載 | wholebody 含手部，但與 Whisper 衝突、akimbo/knee_kneel 候選 | pose README §93 |
| YOLO26n-pose | node 內 15-25ms、GPU +5-8%、RAM +50-400MB | 17kpt 全有效（無眼耳偏移）、多人原生、person bbox；fallen 仍弱（F9） | result F30-F33 |

**4. Required data**
- 離線：demo 錄影 S2 坐姿段逐幀，三方同餵 `classify_pose`（backend 無關純函數，result F45）→ sitting 判定對照表。**這正是 Lane 4 W5** → 本 plan **不重跑 W5**，P3 = W5 數據出來後的 latency/accuracy 取捨決策表 + 晉級配置門檻。

**5. Pure software tasks**
- T-P3-1 [pure software]：**引用 Lane 4 W5 結果**（不重跑），製作 latency/accuracy 取捨決策表：三方 sitting 正確率 vs latency vs RAM vs GPU 佔空比 vs 多人能力。
- T-P3-2 [pure software]：寫「pose 換線晉級門檻」——沿用 result Q10 gate：sitting 正確率 ≥ MediaPipe +10pp 或救回 ≥30% 漏偵幀 → 才排下下次上機（**不是 6/18**）。

**6. Jetson tasks**
- T-P3-3 [Jetson needed]（**post-6/18，晉級才做**）：若 W5 過 gate，yolo26n-pose@640 TRT FP16 上機，門檻 = node 內 pose ≥8Hz / full-stack RAM 餘 ≥0.8GB / object lane Hz 不退化 ≥6Hz / GPU util 增量 ≤30pp / HITL sitting 正確率 ≥ MediaPipe（result Q10）。**前夜 TRT 預燒、不同跑 demo stack**。

**7. Go2 HITL tasks**
無（pose 觀測不需 Go2 motion）。

**8. Metrics**
- 三方 sitting 正確率（vs ground-truth，W5 產出）。
- latency（node 內單幀）/ RAM / GPU 佔空比。
- L3 等價重測：face(CPU)+recognizer(CPU)+YOLO-pose(GPU)+object(GPU)+Whisper burst 同跑 RAM/temp/Hz（result Q8，post-6/18）。

**9. Pass/fail threshold**
- 離線（P3-1/2）：取捨表 + 晉級門檻成文。
- 晉級 gate（W5）：sitting +10pp 或救回 ≥30% 漏偵 → 排**下下次上機**（明確非 6/18）。
- 上機 gate（post-6/18）：result Q10 六門檻全過才升候選 runtime。
- **research_only**：6/18 前不換、不上機；數據只進決策池。

**10. Risk**
- GPU-0% 基石作廢（result F38）→ 整併後需 L3 等價重測 + Whisper CUDA burst 互動（3/21 L2 錨點 -20% FPS）。
- 多人優勢需 node 工程（per-track buffer）才兌現（result F24），不是換 adapter 就有 → 不得宣稱「換 YOLO-pose 就多人」。
- fallen 換模型救不了（F9/F20）→ pose 換線**不解決 fallen**，不得連帶宣稱跌倒改善。

**11. Rollback**
- 離線 additive 無 rollback。
- 晉級上機（post-6/18）走 env/測試 branch、`OBJECT_MODEL` 同款分目錄 TRT cache、不進 main、當日還原 + smoke（沿用 Lane 4 §10 SOP）。

**12. Should we do before Monday？** **maybe**
理由：P3-1/2 是**引用 W5 結果的決策文件**——W5 本週末跑（Lane 4 排程），W5 一出數據就能寫取捨表（純軟體、無額外硬體）。但 P3 依賴 W5 完成，故 maybe（W5 沒跑完就 blocked）。上機（P3-3）明確 post-6/18。

**13. Should it enter 6/18 demo runtime？** **no**
理由：6/18 前 pose runtime 維持 MediaPipe（B-4 不換）；YOLO-pose 晉級也只排**下下次上機**（result Q10 + Lane 4 §5 明定）。research_only，數據只進 post-demo 決策。

---

## §3 任務清單（task_type + tests + HITL checklist + rollback）

| Task | task_type | 內容 | Tests / 驗證 | HITL checklist | Rollback |
|---|---|---|---|---|---|
| T-G1-1 | pure software | 手勢替代品終裁表（引用 result F39-F43） | 終裁表逐條對 result 證據；無重提社區 hand-kpt YOLO | — | 純文件 additive，無 |
| T-G2-1 | pure software | 離線 replay 非手勢段 + 腳本層重放 vote/stable gate | 重放邏輯加單測對拍 runtime 常數；flake8 max-line 100 | — | 無 runtime 變動 |
| T-G2-2 | pure software | min_conf×min_votes×stable_s ROC CSV | CSV 可重跑；現役值落點明確 | — | 無 |
| T-G2-3 | pure software | 誤觸來源歸因 + Pareto 工作點（不改 runtime） | 每誤觸標 ground-truth；Pareto 更優記 post-6/18 候選 | — | 無 |
| T-G3-1 | pure software | peace/OK/palm confusion matrix（離線） | confusion matrix 可重跑 | — | 無 |
| T-G3-2 | pure software | `detect_ok_circle` 閾值候選（僅文件） | 候選有 confusion 數據背書 | — | 不進 runtime，無 |
| T-G3-3 | Jetson needed | Jetson 觀測 peace/OK conf @ demo 距離（純感知，無 motion） | `gesture_backend:=recognizer`；觀測 conf+觸發 | e-stop 不需（無 motion）；單人；demo 距離 ~1.5-2m | 無 runtime 變動 |
| T-G3-4 | Go2 motion needed | peace→OK→WeGo n=3（含 wiggle）— **confirm flow 編排歸 Cloud A，本 plan 只供穩定度數據** | n=3 全完成；trace 鏈完整 | **e-stop 就位**（abort #6）；Go2 開機；單人；淨空 | demo 退「peace 單手勢 + 語音 confirm」(Cloud A) |
| T-P1-1 | pure software | sitting/standing conf 來源剖析（離線，引用 F18） | 拆解 avg_score 眼耳偏移 vs 規則邊界 | — | 無 |
| T-P1-2 | pure software | `pose_min_avg_score`/`sitting_trunk_max_deg` sweep（僅文件候選） | hold-out 段驗證；標「demo 距離正面適用」 | — | 不進 runtime，無 |
| T-P1-3 | Jetson needed | 建 pose observer + 收 sitting/standing ground-truth n≥10 | observer 記事件+人工 label；precision/recall | e-stop 不需（無 motion）；正面距離；單人 | observer 是 additive 工具，無 |
| T-P2-1 | pure software | fallen 幻覺率（離線 replay 家具/無人段） | 誤觸幀/分鐘有數字 | — | 無 |
| T-P2-2 | pure software | fallen demo-safe 裁定（不納入 demo，`enable_fallen:=false`） | 證據鏈=幻覺率+F9/F20+claim matrix future | — | 無（維持現役） |
| T-P2-3 | pure software | bending vs fallen 分離度（deep-bending guard 有效性） | 彎腰段不被吃成 fallen | — | 無 |
| T-P3-1 | pure software | pose 三方 latency/accuracy 取捨表（**引用 W5、不重跑**） | 取捨表含 latency/RAM/GPU/多人 | — | 無 |
| T-P3-2 | pure software | pose 換線晉級門檻（result Q10，排下下次上機） | 門檻成文、非 6/18 | — | 無 |
| T-P3-3 | Jetson needed（**post-6/18**） | yolo26n-pose@640 TRT FP16 上機（晉級才做） | result Q10 六門檻 | 前夜 TRT 預燒、不同跑 demo stack；當日還原+smoke | env/測試 branch、分目錄 TRT cache、不進 main |

**通用 tests（所有 spike 腳本）**：入 repo 過 blocking flake8（max-line 100）；`git status` 乾淨（素材/模型/CSV/MP4 不進 git）；參數化輸入路徑（不寫死 Roy 機器路徑）；量測口徑沿用 `capture_baseline_round.py percep` + topic 隔離（6/4 坑：object 用 `--gesture-topic /__no_gesture__`、gesture 用 `--object-topic /__no_object__`）。

---

## §4 Pure software vs Jetson vs Go2 HITL 三桶分類

### 桶 A — Pure software（WSL 離線，可 AFK，零硬體）

| Task | 依賴 |
|---|---|
| T-G1-1 終裁表 | result 文件（已有） |
| T-G2-1/2/3 誤觸 ROC | demo 非手勢段素材（Roy 指認 V0/B-8） |
| T-G3-1/2 手勢 confusion | demo 手勢段素材 |
| T-P1-1/2 sitting conf 剖析 | S2 坐姿段（與 W5 共用） |
| T-P2-1/2/3 fallen 安全裁定 | 家具/無人段 + bending 段 |
| T-P3-1/2 pose 取捨表 | **Lane 4 W5 結果**（依賴 W5 完成） |

**全部 additive、不碰 runtime code、素材不進 git、獨立 venv。** 唯一前置 = Roy 指認素材路徑（無則順延補錄，不 block 其他 lane）。

### 桶 B — Jetson needed（Roy + Jetson，無 Go2 motion，無需 e-stop）

| Task | 需要 | 時長 |
|---|---|---|
| T-G3-3 Jetson 觀測 peace/OK conf | Jetson + D435（純感知觀測） | ~20 min |
| T-P1-3 建 pose observer + 收 ground-truth | Jetson + D435 + Roy 坐/站 | ~30 min |

### 桶 C — Go2 motion needed（Roy + Jetson + Go2 + e-stop）

| Task | 需要 | 時長 | 歸屬註記 |
|---|---|---|---|
| T-G3-4 peace→OK→WeGo n=3 | Jetson + Go2 + **e-stop** + 淨空 | ~20 min | confirm flow 編排**歸 Cloud A**；本 plan 只供穩定度數據 |
| T-P3-3 yolo26n-pose 上機 | Jetson（**post-6/18**） | 前夜預燒 30-75min + 上機 | 晉級才做，非 6/18 |

**硬規則（abort criteria #6）**：e-stop 沒就位不開任何 Go2 motion（沿用 acceptance §5）。

---

## §5 Metrics / Pass-fail threshold 總表

| Sub-cap | 主 metric | Pass 門檻 | 不 pass 時 |
|---|---|---|---|
| G1 | （無數據） | 終裁表對得上 result 證據 | 無——負面結論本身即 gate |
| G2 | 誤觸率/分鐘 + ROC | 現役值（0.7×3×0.5）誤觸有數字、ROC 可重跑、落點明確 | 樣本不足→標方向性參考 |
| G3 | palm↔ok 混淆率 + peace/OK n=3 觸發 | confusion 產出 + （HITL）n=3 全觸發 + confirm flow n=3 | n<3 維持 needs_hitl，退單手勢 fallback |
| P1 | sitting/standing precision @ n≥10 | observer 建立 + precision ≥0.8 | 無 observer/n<10 維持 insufficient_data |
| P2 | fallen 幻覺率 + bending 分離度 | 裁定成文、幻覺率有數字、`enable_fallen:=false` 鎖死 | 無——do_not_claim 本身即目標 |
| P3 | 三方 sitting 正確率 + latency/RAM/GPU | 取捨表成文 + 晉級門檻（+10pp 或救回 ≥30%）→ 排下下次上機 | 不過 gate→維持 MediaPipe，YOLO-pose 歸檔 |

**全表共通**：單次成功 ≠ 可靠（n=3）；HITL 穩定度未達 n=3 一律 `needs_hitl` 不升 `proven`；任何 metric 不得洗成 claim matrix 的能力 pass（gesture.wave 仍 fail、pose.basic 仍 insufficient、fallen 仍 future）。

---

## §6 Rollback 總表

| 類別 | Task | Rollback 策略 |
|---|---|---|
| 純文件 | T-G1-1, T-P2-2, T-P3-1/2 | additive，無 rollback 需求 |
| 離線 spike（腳本+CSV/MP4） | T-G2-*, T-G3-1/2, T-P1-1/2, T-P2-1/3 | 全離線 additive、不碰 runtime code；腳本入 repo 過 flake8、`git status` 乾淨；素材不進 git → **無東西需 rollback** |
| Jetson 觀測（無 motion） | T-G3-3, T-P1-3 | 純感知觀測 + 量測工具 additive，不改 runtime 行為 → 無 runtime rollback |
| Go2 motion | T-G3-4 | confirm flow 已是現役行為（不新增變動）；現場混淆→退 Cloud A「peace 單手勢 + 語音 confirm」fallback |
| Post-6/18 上機 | T-P3-3 | env/測試 branch 不進 main；`OBJECT_MODEL`/分目錄 TRT cache 保現役 engine 完好；當日還原 + `pawai smoke` |

**核心保證**：本 plan **零 runtime diff**（`git diff` 對 `vision_perception/` 應為空）；任何參數/模型候選皆 post-6/18 另案，6/18 前 demo runtime 與已錄影片一致（B-4）。

---

## §7 決策表（before_monday + enter_6/18_runtime + 理由）

| Sub-cap | before_monday | enter_6/18_runtime | 理由 |
|---|:---:|:---:|---|
| G1 | **no** | **no** | 結論已定（YOLO 死路），終裁表 1 小時、無數據、可併 V3 回填；runtime 維持 MediaPipe |
| G2 | **yes** | **no** | 純軟體高價值（誤觸印象→ROC 數字）、可 AFK、不阻塞；凍結值 0.7×3 不因數字改（B-4） |
| G3 | **maybe** | **no** | 離線 confusion 值得做；HITL 需 Roy+Jetson+e-stop，併 Cloud A confirm 彩排；confirm flow 已是現役行為、不新增變動 |
| P1 | **maybe** | **no** | 離線剖析值得（與 W5 共素材）；建 observer 需 Jetson 但是 pose.basic 升 pass 硬前置；sitting 判定已是現役、不改 runtime |
| P2 | **yes** | **no** | 純軟體、鎖死「不演跌倒」證據鏈是 overclaim 防線關鍵；`enable_fallen:=false` 維持現役 |
| P3 | **maybe** | **no** | 取捨表依賴 W5 完成；6/18 前不換、晉級也只排下下次上機（research_only） |

**總結**：6/18 進 demo runtime 的 sub-capability = **0 個**（全 no）。before_monday=yes 只有 **G2、P2**（純軟體高價值防線）。

---

## §8 需 Roy 拍板的 open decisions

1. **素材定位（blocker，對齊 Lane 4 V0/B-8）**：G2 需 demo 錄影**非手勢段** + **手勢段**；P1/P3 需 S2 坐姿段；P2 需含家具/無人段。請 Roy 指認既有 demo 錄影路徑（6/9-6/10 S2/S3 takes）；不可用則順延補錄（不 block 其他 lane）。
2. **G2 是否值得超出 W7 做 ROC**：W7 已排計數矩陣；G2 進階成 ROC + 歸因。是否要這層進階（建議 yes，純軟體增量小、發表價值高），或 W7 計數即足夠。
3. **G3/P1 的 Jetson/Go2 時段**：T-G3-3/T-P1-3（Jetson，無 motion）與 T-G3-4（Go2 motion，需 e-stop）是否排，何時排（建議併 Cloud A confirm flow 彩排 + Roy Jetson 時段，不單獨佔時）。
4. **pose observer 是否本期建**：T-P1-3 是 `pose.basic` 升 pass 的硬前置（claim matrix Next Retest 明列）。本期建（需 Jetson）或 post-6/18，請 Roy 定。
5. **fallen demo Studio 紅 chip 的旁白策略**：P2 裁定「不演跌倒」，但 Studio 紅 chip 仍顯示。現場被問時旁白策略（pose README Fallback：絕不提跌倒）由 Roy + Cloud A demo flow 最終確認。
6. **P3 晉級上機的「下下次上機日」**：result Q10 + Lane 4 §5 明定 YOLO-pose 晉級也排下下次（非 6/18 前那次 object 矩陣日）。請 Roy 確認 pose 換線時程歸 post-6/18。

---

## 附：Cloud A / Lane 邊界再確認（防重複）

- **demo flow 可靠度 / phase conductor / offline fallback** = Cloud A，本 plan 不重複（G3-4 confirm 編排、P2 旁白策略、P1 greet 觸發皆只供數據、編排歸 Cloud A）。
- **gesture 誤觸計數矩陣（W7）/ pose 三方逐幀 A/B（W5）** = Lane 4 既有排程，本 plan 引用 gate、不重跑（G2 是 W7 的 ROC 進階、P3 是 W5 的取捨表進階）。
- **gesture YOLO 死路 / pose 17kpt 可行** = yolo-pose-gesture result 已收斂，本 plan 引用結論、不重新論證。
- **nav 能力（C1-C12 / F1-F10）** = Lane 6 / Cloud A，本 plan 不觸碰任何 nav label。
