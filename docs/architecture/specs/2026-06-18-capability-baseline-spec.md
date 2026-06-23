# Capability Baseline Spec（6/18 逐功能規格）

> ✅ **Status：current — measurement truth**（specs 層唯一現行真相源；其餘 specs 見 [`README.md`](README.md) 的 current/legacy 分區）。本檔定義「怎麼量」；**能力 grade 結果**（pass/fail）以 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) 為準，**能不能講**連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。門檻在跑完 baseline 前 provisional。
> **性質**：15 個 capability 的逐功能 baseline 規格（9+1 問）。這份是「**每個能力怎麼量、怎樣算 pass**」的**唯一真相源**。
> **不放**：架構決策（見 Master Plan）、code skeleton（見 Implementation Plan）、上機步驟（見 Runbook）。
> **關係**：
> - 總控 / 架構決策 / 三軸定義 / 15 能力 index → `docs/archive/pawai-brain-legacy/plans/2026-05-31-capability-baseline-scoreboard-plan.md`（Master Plan）
> - TDD 實作 → `docs/archive/pawai-brain-legacy/plans/2026-06-01-scoreboard-implementation-plan.md`
> - 上機跑 baseline → `docs/runbook/2026-06-18-baseline-runbook.md`
> **狀態**：逐功能 grill **全收**（2026-06-01）。15 能力全拍定：face ✅、voice(command+stop) ✅、pose(basic+fall) ✅、gesture.wave ✅、object.cup ✅、nav×4 ✅、brain(skill_gate+trace) ✅、studio.evidence ✅、cli.readiness ✅。下一步：四份 baseline docs 整體 review → 另開 fast/slow plan。

---

## 9+1 問框架（每個 capability 一律回答這 10 項）

1. **6/18 是否主張**
2. **`claim_level`**：mainline / studio_only / future / not_claimed
3. **`risk_role`**：safety_critical / safety_support / actuation / convenience / evidence_only
4. **`dependency_role`**：trigger / content / safety_guard / actuation / evidence（fail 時依賴它的 skill 怎麼降級）
5. **observer 狀態**：現成 / 要新 / 卡住（誰產可評分記錄，附 file:line）
6. **baseline scenario**：怎麼跑（距離 / 輪數 / idle 段）
7. **metrics**：量哪些指標
8. **pass / degraded / fail 門檻**（provisional，數字 calibrate-from-run-1；硬性 fail 結構先鎖）
9. **fail / degraded fallback**：Brain 怎麼降級
10. **換模型條件**：什麼 baseline 數據才允許評估換模型

> 門檻一律 **provisional until baseline**；硬性 fail 結構（如 nav collision=0、face wrong-person、voice.stop FN=0）先鎖、數字上機校準。

---

## 1. `face.recognition` ✅（2026-06-01 拍定）

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——只主張「註冊者辨識 + 問候」 |
| 2 | claim_level | mainline |
| 3 | risk_role | evidence_only |
| 4 | dependency_role | **content**（fail→不叫名字，仍可互動）|
| 5 | observer | ❌ 要新 `face_baseline_observer`（吃 `/state/perception/face` 連續流，Task 4b；**勿用 event-only observer**）|
| 6 | scenario | 距離 **1m / 2m**（3m optional stress、**drop 0.5m**）；註冊者 1-2 人 + 陌生人 2-3 人；多人同框只驗「會不會把 unknown 叫成註冊者」 |
| 7 | metrics | `registered_recall` / `unknown_false_accept_rate` / `wrong_person_count` / `time_to_stable_ms`（**棄 TAR@FAR**，小樣本可理解指標）|
| 8 | pass/deg/fail | **不對稱門檻**：`registered_recall` ≥80% / 60-80% / <60%；`unknown_false_accept_rate` ≤3% / 3-10% / >10%。**硬規則：`wrong_person_count` ≥1 且小樣本 → 不得 pass，只能 degraded/fail**（認錯人 / 把陌生人叫成註冊者皆計 false_accept；20 次錯 1 次=5% 仍危險）|
| 9 | fallback | **分層**：degraded → 不叫名但可語音互動；fail → 只泛稱「有人來了」絕不叫名；都不觸發 motion |
| 10 | 換模型 | 只有 `unknown_false_accept_rate` fail（>10%）才考慮換 YuNet/SFace；**且先試 `sim_threshold` 調高（現 0.40）+ face_db 重 enroll** 這些零成本手段；recall fail 單獨不換（多為距離/光線/enroll 品質）|

**主張範圍理由**：North Star §5 禁「守護 / 陌生人警報」；`stranger_alert` skill 已被 5/27 改 silent（`text=""`）；`sim_threshold_upper` 5/8 從 0.30 收緊到 0.40 是為壓 60%+ 陌生人誤報——所以陌生人=泛稱不點名、不警報，baseline 重點是 unknown-false-accept。

**Criterion 映射（接 aggregator F2 分離指標，給實作者）**：face 的 `criteria_by_capability["face.recognition"]` =
```python
[
  Criterion("registered_recall",         pass_min=0.80, degraded_min=0.60, higher_is_better=True),
  Criterion("unknown_false_accept_rate", pass_min=0.03, degraded_min=0.10, higher_is_better=False),
  Criterion("wrong_person_count",        pass_min=0,    degraded_min=0,    higher_is_better=False),  # ≥1 → 該 metric 非 pass → 拉低總 grade（硬規則）
]
```
aggregate 按 (capability_id, scenario_kind) 分組產出這些 key：`registered_recall`=positive round pass 率、`unknown_false_accept_rate`=idle round false_trigger 率、`wrong_person_count`=positive round 卻 false_trigger（認錯人）次數。**round_meta 須標 `scenario_kind`**（positive=known 出場 / idle=只陌生人或無人）。`time_to_stable_ms` 為觀測欄、非 gating criterion。

**Studio evidence**：name（或 unknown）/ similarity / face box / D435 distance / 該能力 scoreboard grade chip（全是 `/state/perception/face` 現成欄位）。

**code 接地**：`/state/perception/face` 每 tick 發全部 tracks（`face_identity_node.py:634-641`，含 track_id/stable_name/sim/distance_m/bbox/mode/face_count）；`/event/face_identity` 只在 stable transition 發（:561）、**從不發 unknown** → 故 observer 必走 state 流。閾值現況 `sim_threshold_upper:0.40 / lower:0.22 / stable_hits:2 / max_faces:5`（`face_perception/config/face_perception.yaml`）。

---

## 2. 語音功能 ✅（2026-06-01 拍定，voice recon workflow file:line 接地）

> 拆兩 row：`voice.command`（固定指令）、`voice.stop`（說「停」）。observer = 現成 `speech_test_observer`（PASS/MARGINAL/FAIL，CSV 含 asr/intent/e2e latency + confidence）。

### 2a. `voice.command`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——固定指令輸入 |
| 2 | claim_level | mainline |
| 3 | risk_role | convenience |
| 4 | dependency_role | **trigger**（fail→不觸發該 skill）|
| 5 | observer | ✅ `speech_test_observer` 現成（→ A2 轉 record）|
| 6 | scenario | 6-8 個 demo 固定指令各 ≥3 輪（從 `speech_30round.yaml` 取 demo 主線用到的 intent）|
| 7 | metrics | accuracy / e2e_latency / play_ok_rate（ASR/intent/TTS 為 **sub-metric**，任一 fail 則 row fail）+ **TTS TTFA 另計** |
| 8 | pass/deg/fail | accuracy **≥80% / 70-80% / <70%**；e2e_median ≤3.5s；play_ok ≥80%；**TTFA p90 ≤2s/2-4s/>4s**（latency 起算見「設計結論」）|
| 9 | fallback | **分層**：ASR/intent fail → 請重說 / RuleBrain 接手；TTS quality lane 慢 → edge_tts fast lane；TTS 全斷 → Studio 顯示文字不出聲。degraded 不觸發 motion 類 skill |
| 10 | 換模型 | （ASR）SenseVoice local fallback 已備；（TTS）TTFA fail(>4s) **且** edge_tts fallback 也 fail 才談 ElevenLabs，且需評估雲端依賴風險（斷網則廢，與 Edge AI framing 矛盾）|

**code 接地**：`speech_test_observer.py` 已有 PASS_CRITERIA（fixed_accuracy≥80%/e2e_median≤3500ms/e2e_max≤6000ms/play_ok≥80%）+ CSV 欄位（asr_latency_ms/intent_latency_ms/e2e_latency_ms/intent_confidence/match/status）；intent 分類 `intent_classifier.py:36-200`（7 SUPPORTED_INTENTS + confidence 權重）。

### 2b. `voice.stop`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——說「停」會停（互動體驗，**非安全機制宣稱**）|
| 2 | claim_level | mainline |
| 3 | risk_role | convenience（operator_abort）|
| 4 | dependency_role | **trigger** |
| 5 | observer | 🟡 命中率現成；從 30 輪拆「停」專項 |
| 6 | scenario | 「停」專項 N 輪（含噪音）|
| 7 | metrics | FN（漏聽）|
| 8 | pass/deg/fail | **FN 硬性=0**（任一漏聽=fail，不平均）|
| 9 | fallback | **不影響安全評級**——motion 安全一律由 `reactive_stop` + 物理 e-stop 保證 |
| 10 | 換模型 | n/a |

**定性鎖定**：stop 是「額外便利」，真安全靠 reactive_stop + 物理 e-stop（對齊 North Star「安全靠物理不靠語音」）。**不在任何 skill 的安全依賴鏈**。
**code**：`safety_gate.py:11` `SAFETY_KEYWORDS=("停","stop","暫停","煞車","緊急")` → bypass LLM → `stop_move`（:23）= 現成的 System 1 fast path 雛形。

### 設計結論：manual mic boundary + latency 起算（v0.1 baseline 範圍）

> voice recon workflow 證實，6/18 語音主線改用 **manual mic boundary**（VAD 已被 ADR-0003 凍結、不作斷句依據），baseline latency 從 `manual_mic_stop` 起算才反映真實 demo 操作。

**v0.1 baseline scope（要做）**：
- voice.command/stop 量測（走 demo entrypoint）
- **mic_stop signal（demo-blocking 前置）**：Studio `use-audio-recorder.ts` stopRecording 發 WebSocket `mic_stop` event → stt_intent_node 訂閱 → 立即 finalize + 解 echo gate。topic = `/event/mic_boundary`。**沒有它，manual mic boundary 量不到，latency 還是 VAD 舊世界。**（~10-15 行）
- **latency clock 改 mic_stop-based（雙記錄）**：observer 同時記 `mic_stop_ts` 與舊 `speech_start_ts`；新 `e2e_latency_ms` 用 mic_stop、舊欄位改名 `e2e_latency_ms_old` 保留對照。**報告明標「metric v2（mic_stop 起算）」避免被誤讀成「快了 2 秒」（量法變，非系統變快）**。
- VAD `energy_vad.enabled` 6/18 demo 設 False（main 拔掉），safe default 留 True（fallback）；echo gate 在 manual mic_stop 時立即解（避免時序衝突丟錄音）。

**not v0.1（另線：Voice Latency Improvement / System1-System2 Fast Path）**：
- fast_router 節點（`graph.py` 在 safety_gate 後插分流：intent∈SUPPORTED 且 conf≥0.8 **且非 motion** → System1 canned shortcut skip LLM；否則 System2 走完整 LLM）
- Piper fast TTS cache、canned first-feedback、LLM/VLM slow path orchestration
- **go/no-go 條件 = baseline fail**：若 voice.command baseline 顯示 `mic_stop_to_first_feedback >1s` 或 `mic_stop_to_e2e >3.5s` 或 `TTS TTFA p90 >2s` 才啟動。對齊「沒有 baseline fail，不談架構重構」。
- diffusion action model = 明確 future（無 dataset、Go2 靠 skill API、對 latency 無直接幫助）。

**System1 fast-path 安全細節**：motion intent（如 `come_here`）即使 conf≥0.8 也**不能純 canned 直接動**，仍須過 nav gate（避免「靠近/靠精」ASR 誤聽觸發 Go2 前進）；只有 greet/status/canned-reply 等無 motion 才能純 System1。

**completeness critic 抓到的洞**（記入另線 spec，非 v0.1）：Sev2 confidence 計算無 absolute threshold（誤觸風險）、Sev5 canned 帶 audio tag 但 piper 不支援（情感不一致，去 tag）、Sev6 no-speech/空 ASR 無 fallback（按 mic 沒講話→播「沒聽清楚」尷尬，加 `intent=no_speech`）。

**現實接地**：60-70% 已就位（intent classifier / safety_gate 短路 / canned template 30+ 句 / TTS cache 框架 / echo gate）；30-40% 要補（mic_stop 訊號流 / fast_router / latency 改點）。

---

## 3. 姿勢辨識 ✅（2026-06-01 拍定）

> 單幀 2D 幾何分類（`pose_classifier.classify_pose`：trunk_angle/hip_angle/vertical_ratio，COCO 17 keypoints）。standing/sitting/crouching/bending 穩；akimbo/knee_kneel 不穩（不主張）。fallen 幻覺確認存在（無人時鎖衣架判 fallen，README:71；投票 buffer 20 幀只降未消）。

### 3a. `pose.basic`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **否**（不進 Brain 主線）——只 Studio 顯示「看得出在做什麼」|
| 2 | claim_level | **studio_only** |
| 3 | risk_role | evidence_only |
| 4 | dependency_role | content |
| 5 | observer | ❌ 新 `perception_baseline_observer`（event）薄測 |
| 6 | scenario | standing/sitting（+crouching/bending）各 ≥3 次 recall，**只 observe 不觸發 motion** |
| 7 | metrics | recall（各姿勢命中率）|
| 8 | pass/deg/fail | 寬門檻（studio_only）：recall ≥70% 可顯 / <70% 連 studio 也不信。akimbo/knee_kneel 不穩→不主張 |
| 9 | fallback | studio-only 顯示；任何情況不進 Brain 決策、不觸發 motion |
| 10 | 換模型 | **6/18 前不換**；recall fail **只降級為 unknown / 不顯示姿勢**（不觸發換模型工作）。future 若要把 pose 升級成照護/主線能力，才評估 RTMPose/PINTO。（避免 P2 功能因 baseline fail 偷偷變成 P0 換模型工作）|

### 3b. `pose.fall`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **否**（North Star §5 禁說跌倒可靠）|
| 2 | claim_level | **future** |
| 3 | risk_role | evidence_only |
| 4 | dependency_role | evidence |
| 5 | observer | ❌ 本輪不測 |
| 6 | scenario | **不測**（幻覺未解）|
| 7 | metrics | — |
| 8 | pass/deg/fail | 標 **insufficient_data**（不評）|
| 9 | fallback | Studio 可顯紅 alert 供 debug，但 **fallen TTS 永靜音**（現狀 `FALL_ALERT_TTS=""`，event_action_bridge 5/8 移除模板）、不停車、不進 Brain |
| 10 | 換模型 | n/a（幻覺是判定邏輯問題非模型，先不主張）|

**code 接地**：fallen 判定 `interaction_rules.py:83 should_fall_alert`（要 persist 夠久）；fallen TTS muted（`event_action_bridge.py:75-80` 移除模板 + Brain `fallen_alert` `FALL_ALERT_TTS=""`）；vertical_ratio gate（`pose_classifier.py:81` ankle_y/image_height>0.7）已濾部分 false fallen 但未根治衣架幽靈。

## 4. 手勢辨識 `gesture.wave` ✅（2026-06-01 拍定）

> wave 走 `WaveDetector`（dynamic_gesture_detector，per-hand，window 1.5s/reversals 2/amplitude 50px/cooldown 2.5s）。static（ok/thumbs/palm）走 `gesture_classifier`+`detect_ok_circle`，code 還在跑但 **6/18 不主張**。

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——只主張 wave（揮手打招呼）。static ok/thumbs/palm **全不主張**（不進 Brain 主線）|
| 2 | claim_level | mainline |
| 3 | risk_role | convenience（emote）|
| 4 | dependency_role | **trigger**（fail→完全不觸發 wave_hello）|
| 5 | observer | ❌ 新 `perception_baseline_observer`（event）。**必走 demo recognizer backend + 人工 ground-truth**——wave confidence `hardcode 1.0`（vision_perception_node.py:414）無鑑別力，recall/誤觸完全靠人工標註；**不可用壓測 mediapipe backend 的 idle 結果當最終 baseline**（backend≠demo）|
| 6 | scenario | person-present idle（人在框內手自然放鬆）60s×10=**10min** + natural hand motion + real wave **1m/2m 各≥10 次**。每 round 標 `scenario_kind`（idle / positive）|
| 7 | metrics | wave recall / **idle false_trigger_rate**（scenario_kind=idle）/ repeated_trigger_count / latency |
| 8 | pass/deg/fail | recall ≥90%/80-90%/<80%；**idle 誤觸是硬 gate（權重 > recall）：≤1/10min=pass / 1-3=degraded / >3=fail（不管 recall）**。注意 person-present idle ≠ idle-EMPTY，真值要「人在框內不刻意比手勢」|
| 9 | fallback | pass→觸發 `wave_hello`（emote api 1016）；degraded→Studio 顯示不觸發；fail→完全不用 gesture trigger |
| 10 | 換模型 | **修法順序**：(1) 先調 WaveDetector 超參（reversals/amplitude/cooldown/window，零成本）；(2) **不**先修 static recognizer score floor（static 非主張）；(3) 超參調不下 **且** recall 真 fail 才看 PINTO 481_WHC 揮手模型（go/no-go 2026-06-06）。idle 誤觸 fail 優先調 cooldown/reversals |

**code 接地**：`WaveDetector`（vision_perception_node.py:153-155，per-hand + 2.5s publish cooldown）；wave confidence hardcode 1.0（:414，繞過 vote buffer）；static 路徑 `gesture_classifier.py` + `detect_ok_circle`（:377-386）；recon 證 MediaPipe Recognizer 無 `score_threshold`（預設 -1=停用）→ static 無 confidence floor。

## 5. 物體辨識 `object.cup` ✅（2026-06-01 拍定）

> YOLO26n ONNX + TensorRT FP16。`whitelist=[41,999]`=cup-only（41=COCO cup，999=dummy 強制 INTEGER_ARRAY 避 BYTE_ARRAY 坑）。**cup-only 是刻意對齊 6/18 主張、非壞掉**（commit b81cfdd 5/27 demo video mode）。

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——只主張 object.cup。bottle/wallet/key/denture/`object.general`/VLM 場景描述 **全 future** |
| 2 | claim_level | mainline |
| 3 | risk_role | evidence_only |
| 4 | dependency_role | content |
| 5 | observer | ❌ 新 `perception_baseline_observer`（event）。**baseline 必須真起 `object_perception`**（現無 consumer 訂 `/event/object_detected`）|
| 6 | scenario | positive：cup 放桌上 1m/2m 各 ≥5 次（含背景干擾）；idle：空場景/無 cup 連續 60s 量 false-positive。每 round 標 `scenario_kind`。**不測地上/人手拿**（複雜度高、非 demo 主線）|
| 7 | metrics | `cup_recall` / `idle_false_positive`（事件數）/ `wrong_class_count` / latency。**計算規則（對齊 aggregator scenario_kind 分組）**：<br>• **positive cup round**：cup detected=pass；no detection=miss；**wrong class（cup 在場卻認成 bottle 等）=wrong_class／miss → 傷 `cup_recall`，不算 false-positive**<br>• **idle no-cup round**：任何 cup 事件=false_positive |
| 8 | pass/deg/fail | **不對稱門檻**：cup recall ≥80%/60-80%/<60%（content，漏認只是不提、不傷）。**idle false-positive**：1 個 idle round = **1 個 60s 窗**（生一筆 record，`false_trigger`=該窗內有無誤報 cup）；單窗 0 次=pass / 1 次=degraded / >1 次=fail。**aggregator 對齊**：`unknown_false_accept_rate` = 誤觸窗數/總窗數（單窗 0→rate 0；跨 N 窗 k/N），`object.cup` Criterion 用此率、門檻對應上述事件數語意（憑空說「有杯子」很傷 demo）|
| 9 | fallback | **分層**：pass→口頭 remark「桌上有杯子」；degraded→Studio 顯示 bbox/label 不口頭；fail→不進 demo 主線 |
| 10 | 顏色 / 換模型 | **顏色不進 claim**（無 color detection code，`coco_classes.py:152 class_color` 只是 debug 上色）。**修法順序**：(1) cup-only whitelist 現狀正確、不動；(2) baseline fail 先調 conf threshold/lighting/ROI/TRT（零換模型）；(3) recall fail 且調不下才測 YOLO26s（mAP+7.7pp，但 Nano FPS **HIGH risk**）；(4) PINTO/VLM 更後。wallet/key/denture 全 future 不拖累 6/18 |

**code 接地**：`object_perception.yaml:20 class_whitelist=[41,999]`；event schema `class_name`/`confidence`/`bbox`/`event_type=object_detected`（object_perception_node.py:365,416）；無 color detection（只有 `class_color` debug 上色 + `red→紅色` label 翻譯表）。

## 6. 導航避障 ✅（2026-06-01 拍定，nav recon + D435 fusion recon file:line 接地）

> 4 能力拆開。**核心紀律**：safe_stop/no_auto_resume 是 safety_critical，short_move 是 actuation——全是 mainline **target**，但 baseline pass 前一律 insufficient_data，**不可寫成 pass**。RPLIDAR(Sensitivity mode，**已設非待改**) 主力 2D nav，D435 depth witness 補強，Go2 內建 LiDAR/range_obstacle/onboard 全 spike/future。

### 6a. `nav.safe_stop`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | P0 target（why-dog 安全核心）|
| 2 | claim_level | mainline |
| 3 | risk_role | **safety_critical** |
| 4 | dependency_role | **safety_guard** |
| 5 | observer | ❌ recorder `_cb_reactive_status` no-op（BD-7 未接）→ **insufficient_data** |
| 6 | scenario | 真障礙停車 N 輪 |
| 7 | metrics | `collision_count` / `stop_margin_m` / `stop_latency_ms`（先記錄）/ `false_stop_rate`（先記錄，避免亂停）|
| 8 | pass/deg/fail | **結構現在鎖、數字 calibrate-from-run-1**：`collision_count` 任一次=fail（硬門檻）；`stop_margin_m` pass 需 ≥0.10m；stop_latency/false_stop_rate 先記錄不硬設 |
| 9 | fallback | **FAIL→禁所有 motion/nav**（safety_guard）|
| 10 | 補強 | D435 當 depth witness 交叉驗證 LiDAR stop 是否合理；**baseline 前不當主判斷來源** |

**不可寫**：`safe_stop 已完成`。runtime 有 reactive_stop 4-mode，但 recorder 沒接好前一律 insufficient_data。

### 6b. `nav.no_auto_resume`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | P0 target |
| 2 | claim_level | mainline |
| 3 | risk_role | **safety_critical** |
| 4 | dependency_role | **safety_guard** |
| 5 | observer | ❌ **比量測缺口更嚴重——行為定義衝突** |
| 6 | scenario | 障礙移開後不暴衝 N 輪 |
| 7 | metrics | 暴衝次數（任一暴衝=fail 硬性）|
| 8 | pass/deg/fail | **正確行為定義（先鎖）**：stop 後**不自動 resume 原 goal**，必須 operator/Brain 發新命令才動 |
| 9 | fallback | **FAIL→禁所有 motion/nav** |
| 10 | ⚠️ 行為待改 | **現行 `reactive_stop_node.py:307 _maybe_call_nav_pause` 是 auto-resume**（離開 danger→`/nav/resume`），且 hold_brake mode 又故意不 resume（:33-34）→ **行為不統一、與 no_auto_resume 語意相反**。標 insufficient_data + 「**行為待重定義（BD-8）**」。不只量不到，是設計要改 |

### 6c. `nav.short_move`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | P0 target / **why-dog 具身證明**（為何要機器狗不是 APP）|
| 2 | claim_level | mainline |
| 3 | risk_role | **actuation** |
| 4 | dependency_role | **actuation** |
| 5 | observer | 🟡 手動發 `/nav/goto_relative`→**讀 action result**（`bool success` / `string message` / `float32 actual_distance`）量得到；但 demo 主線量不到（見下）。⚠️ **DOC BUG（待修，勿照抄）**：原文寫的 `/event/nav/mission`(outcome_code) **不存在**——source 無此 topic、無 `outcome_code` 欄位。真實 observer surface 是 `/nav/goto_relative` 的 action **result**（型別 `go2_interfaces/action/GotoRelative`，由 `nav_capability/nav_action_server_node.py` serve；`actual_distance` 在 :408 填）。量測請讀 action result，不要訂閱不存在的 `/event/nav/mission`。|
| 6 | scenario | goto_relative 0.3m×N / 0.5m×N |
| 7 | metrics | goto 成功率 / actual_distance 分佈 |
| 8 | pass/deg/fail | goto SUCCEEDED rate ≥85%/70-85%/<85%（calibrate-from-run-1）|
| 9 | fallback | **需 #6a safe_stop + #6b no_auto_resume 先 pass 才能走 motion**；未達前不放行 |
| 10 | ⚠️ 3 個 blocker | **現 insufficient_data，不可寫 pass**：(a) Brain skill `nav_demo_point→goto_relative` 斷在 `interaction_executive_node.py:278`（只接 goto_named，goto_relative 走 `nav_unimplemented_phase_a`，BD-10+ 才接）；(b) F7 未定位（reactive_stop narrow-field threshold 經 mux pri200 遮蔽 nav pri10）；(c) 0.85 profile 無可信實機 motion 證據。baseline pass 才從 target 變可講 |

### 6d. `nav.dynamic_avoidance`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **否**（future/bonus，明確不講）|
| 2 | claim_level | **future** |
| 3 | risk_role | actuation |
| 4 | dependency_role | actuation |
| 5-9 | — | 架構 stop-only 不繞障；標 insufficient_data；不主張（非 fail）|
| 10 | 後話 | ComposableNode + velocity_smoother，Phase 11+ |

### 6e. nav spike / future queue（全不進 6/18 主宣稱）

**quick sanity spike（上機十幾分鐘可測、不主張）**：
- `range_obstacle[4]`：Go2 內建 4 向粗略障礙距離，零 consumer、韌體語意未記錄。10 分鐘 sanity test 看值域/方向/更新率。
- onboard avoidance（api 1004）：Go2 機身內建避障，從未測（ADR-0006 禁用）。5 分鐘低風險環境測。
- **D435 Fusion Shadow Test**：不讓 Go2 動，只錄資料——啟 D435 pointcloud→`/scan_d435_shadow`（`pointcloud_to_laserscan`，**必須 `target_frame:=base_link` 且先驗 TF**——不設 target_frame 會讓 height filter 在 optical frame 語意錯掉，high/low 切片全亂；參考 `docs/archive/navigation-legacy/research/2026-05-25-realsense-d435-full-stack-deepdive.md:90`）、height filter **0.05-0.50**（非舊 0.20-0.80）+ 同錄 `/scan_rplidar`，放矮箱/桌面邊緣/椅腳三種障礙，量「RPLIDAR 漏掉而 D435 補到的比例」。**不可沿用舊 detour script**（hack TF / `depthimage_to_laserscan` 無 height filter / danger=0.40 / safety_only 舊坑）。延遲/TF/false-positive 可接受才考慮接 safe_stop 或 Nav2 obstacle layer。**過了才升級，不可先宣稱 fusion 已可靠**。

**future sidecar（6/18 不碰）**：
- Go2 內建 3D LiDAR：**拿得到**（decode path 活、~7Hz；推翻舊「拿不到/頻率低」說法）**但 Pro 韌體每幀~22 點≈18% 覆蓋太稀疏**，不能當主導航；密集版只在 EDU 版+CycloneDDS。
- nvblox/Isaac ROS、ORB_SLAM2/RTAB-Map RGB-D SLAM、D435 full costmap fusion：post-baseline，Jetson 8GB 算力評估後再說。

**D435 定位校正（重要，修 doc drift）**：D435 **不是避障死路**。當前水平掛法（離地 0.52m、FOV ±29°）地面最近可見約 0.94m，0-0.94m 是盲區——但這是**掛法 trade-off（可調俯角/改參數改善），非物理死路**。（latency：本地證據只支持 `depth_safety_node` status tick ~5Hz≈200ms，**不代表端到端 stop latency**——從感測到 Go2 停住的 e2e latency 仍需 baseline 實測；4/3 的 1.5s 是當時 e2e 估計）4/3 失敗是倉促偽診斷（掛角/參數/延遲三層混為一談）。正確定位：**RPLIDAR 高度補強 witness + depth safety gate + 人臉/物體相機**。深度+光達融合是業界標配（Nav2 obstacle_layer 多 observation_sources，`nav2_params_detour.yaml:220` 已有 `scan d435_scan` 配法，但 detour script 有危險舊坑不可直接復活）。

> nav 內部 blocker（F7 診斷、0.85 profile 標記、recorder BD-7/8、D435 shadow test）屬 nav workstream，不是 capability spec 的 grill 範圍——見 docs/architecture/navigation/。

## 7. PawAI Brain ✅（2026-06-01 拍定，skill_gate + trace 鏈 file:line 接地）

> **核心紀律（避免偷換概念）**：brain 兩個能力跟感知能力**量法不同**——不是上機採樣統計分佈，是**邏輯真值表 / scenario replay**。而且 `brain.skill_gate` 必須拆成兩層看，**現有 gate 能擋 world flags ≠ scoreboard grade 已 fail-closed 接進 gate**：
>
> | 層 | 是什麼 | 現況 | 怎麼驗 |
> |---|---|---|---|
> | **Skill Policy Gate（現有）** | 吃 `demo_status_baseline` + `static_enabled` + `cooldown` + WorldFlags(`tts_playing`/`obstacle`/`nav_safe`)，回 `effective_status` → `proposed`/`needs_confirm`/`blocked` | ✅ 已實作（`compute_effective_status` + `normalize_proposal_v2`），340 offline tests 覆蓋這層 | pytest 真值表（現成可測）|
> | **Capability Health Gate（scoreboard-first 真正要的）** | 吃 baseline `grade` / `claim_level` / `brain_allowed`，fail-closed 擋掉 grade≠pass 或 claim_level∈{future,not_claimed} 的 skill | ❌ **`compute_effective_status()` 目前完全沒吃 grade**（effective_status.py:38-70 無 grade 分支）| 待 v0.2 接 + 真值表（**接了才算數**）|
>
> **SayCan 類比**：LLM 提候選 skill（"say"）→ gate 用 baseline grade 當 affordance（"can"）決定能不能做。我們的 `brain_allowed = (grade==pass AND claim_level==mainline)` 就是 SayCan 的 affordance-gating，只是 affordance 來源是 baseline scoreboard。
>
> **裁決：`brain.skill_gate` 不能因為 340 offline tests 就寫 pass**——那些 test 驗的是 Skill Policy Gate 層，不是 grade-consuming 層。grade 沒接進 gate 之前一律 `insufficient_data`。

### 7a. `brain.skill_gate`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | P0 target（scoreboard-first 能不能落地的核心）。**但 grade 未接進 gate 前 = insufficient_data，不可寫 pass** |
| 2 | claim_level | mainline |
| 3 | risk_role | **safety_critical**（gate fail-open＝unsafe skill 漏放行，直接安全風險）|
| 4 | dependency_role | **safety_guard** |
| 5 | observer | **pytest 真值表，非上機採樣**。🟡 Skill Policy Gate 層現成可測（340 tests）；❌ Capability Health Gate 真值表＝新 deliverable（依賴 grade 接進 `compute_effective_status`，尚未做）。**理由**：gate 失敗模式是「該擋沒擋」（fail-open），要窮舉真值表證明；採樣永遠測不到「grade=insufficient_data 時有沒有 fail-closed」這種角落（正常 demo 不會自然產生那狀態）|
| 6 | scenario | 真值表窮舉：每個 (claim_level × grade × risk_role) 組合 → 預期 gate 行為。**重點 case**：grade∈{fail,insufficient_data} 的 skill 必被擋；claim_level∈{future,not_claimed} 永不進 mainline；motion/nav 在 insufficient_data 必 fail-closed |
| 7 | metrics | `unsafe_allowed_count`（該擋卻放行數）/ fail-closed 真值表覆蓋數 ÷ 應覆蓋數 |
| 8 | pass/deg/fail | **只有 pass / fail / insufficient_data，無 degraded**（gate 不允許半對）。**pass 條件全部成立**：(a) `unsafe_allowed_count = 0`；(b) grade≠pass 的依賴 skill 全被擋；(c) future/not_claimed 的 capability 永不進 mainline；(d) insufficient_data 對 motion/nav 必 fail-closed。任一條 fail-open＝fail |
| 9 | fallback | **gate fail → 不允許 demo 主線 motion/nav**，只能 Studio 顯示或 explain-only。fail-closed 是預設（缺 grade／snapshot 不可信 → 全當 insufficient_data → 擋）|
| 10 | v0.2 必做 | **grade 接進 gate 是 v0.2 必做、非 optional**。**插入點（對齊 Master Plan §D line 184）**：grade 分支接在 `disabled / studio_only / explain_only / demo_guide / static_enabled / enabled_when / cooldown` 判定**之後**、`tts_playing / obstacle / nav_safe` physical-block 判定**之前**——grade∈{fail,insufficient_data} 或 claim_level∈{future,not_claimed} → `disabled`/`blocked`，reason 帶 baseline provenance。**不可覆蓋 skill-level hard disable**：`disabled/studio_only/explain_only` 是 skill 層硬約束，capability grade 不得翻案（否則會出現「能力 pass 但 skill 本該 disabled」被錯放行）。接了 + 真值表全綠才從 insufficient_data 升 pass |

**不可寫**：`skill_gate 已完成` / `340 tests 過＝scoreboard gate 已落地`。現有 tests 只覆蓋 Skill Policy Gate（world flags），不覆蓋 grade-consuming 層。

### 7b. `brain.trace`

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——「決策可解釋」是 demo 給老師看的證據鏈（為何做/為何擋）|
| 2 | claim_level | mainline |
| 3 | risk_role | **evidence_only** |
| 4 | dependency_role | **evidence** |
| 5 | observer | **固定 scenario replay**，檢查 trace stage 是否完整（非上機採樣、非真值表）。🟡 trace 已在發（`/brain/conversation_trace`），observer = 跑固定對話腳本 → 比對 trace stage 序列完整性 |
| 6 | scenario | replay 數個固定對話：(a) 正常 skill 放行、(b) skill 被 gate 擋、(c) needs_confirm、(d) rejected_not_allowed、(e) safety「停」短路。每個都檢查 trace |
| 7 | metrics | trace 完整率（每次 proposal 有無 skill_gate stage）/ blocked-with-reason 率 |
| 8 | pass/deg/fail | **pass 條件（code path，scenario replay 可驗）**：(a) 每次 skill proposal 都有 `skill_gate` trace；(b) 被擋時 detail 帶 reason；(c) proposed / blocked / needs_confirm / rejected_not_allowed 四態都能從 trace 看出。**(d) Studio 顯示真實 trace（非 mock）= §8 `studio.evidence` 的判定範圍，§7b 不自評該項**（避免把 Brain trace code path 與 Studio evidence 混成一個能力）。degraded＝trace 發得出但有 conditional-emit 破洞（如 chat turn 無 `skill_gate` row）|
| 9 | fallback | trace 是唯讀證據層，不 gate 任何行為；fail（trace code path 缺漏）→ 只影響「可解釋性」展示，不影響 motion/nav 安全 |
| 10 | 換模型 | n/a（觀測層）|

> **§7b / §8 邊界（2026-06-01 Roy review 鎖定）**：`brain.trace` 的 **code path 完整性**可由 scenario replay 獨立驗證（trace 有沒有發、四態可不可辨、reason 在不在）；**Studio 顯示的是不是真實 trace（非 mock）留給 §8 `studio.evidence` 定義**。兩者是不同能力，不可混評。

**code 接地**：
- **skill_gate 鏈**：`CapabilityRegistry.build_entries`（registry.py:54）組 entry → `compute_effective_status`（effective_status.py:26，純函式、**無 grade 分支**）→ `normalize_proposal_v2`（skill_policy_gate.py:88）按 effective_status 分流：`available`→proposed、`needs_confirm`→needs_confirm、其他→`blocked` detail=`{name}:{eff}`；entry=None 但在 allowlist→`blocked: not_in_capability_context`（**已是 fail-closed，drop 不轉 brain_node**，:79-82）。`brain_allowed` 概念目前**只在 doc，code 尚未實作**。
- **trace 鏈**：每 stage append `state["trace"]`，已實作 stage = `input`/`mode_classifier`/`safety_gate`/`llm_decision`/`json_validate`/`skill_gate`/`repair`/`verifier`；`_publish_traces`（conversation_graph_node.py:944）發 `TracePayload`(session_id/stage/status/detail/engine，schemas.py:43) → `/brain/conversation_trace`；`brain_node._emit_trace`（:887）另一條含 `ts`。Studio gateway 消費見 `pawai-studio/gateway/studio_gateway.py`（real-vs-mock 待 §8 一起驗）。

> **fast/slow 系統是另線（獨立 plan，不塞進本 spec 主體）**：6/18 正確版本＝三層階序 **Safety Kernel（`reactive_stop` / e-stop / `no_auto_resume` / nav safety，永遠最高、brain-independent）> System1（低風險、可驗證、低延遲互動捷徑：fixed intent / canned / cached TTS / non-motion skill）> System2（LLM/VLM 慢思考）**。對齊 SayCan / Nav2 BT，**非** diffusion action model / VLA low-level policy。
> **硬邊界（防 fast_router 為了快跳過 gate）**：fast path **不得繞過** `skill_policy_gate` / `capability_health gate` / nav safety；只允許 **non-motion / canned / explain-only** 類互動先行。motion/nav 一律仍走完整 gate + Safety Kernel。
> go/no-go = voice baseline fail。詳見 §2 設計結論 + 新 plan `docs/archive/pawai-brain-legacy/plans/2026-06-02-fast-slow-interaction-lane-plan.md`（brain 架構審查產出）。

## 8. `studio.evidence` ✅（2026-06-01 拍定，gateway + frontend recon file:line 接地）

> **核心 framing（recon 翻案）**：Studio **不缺 dashboard，缺「誠實層」**。感知面板/影像/chat/trace 都已存在且相當完整 ── 真正的洞是 **mock 與 live 用同一套 event 格式、前端無 provenance、且預設 `start.sh` 跑的是 mock server**（`start.sh:44-46` port 8080）。老師看畫面時無法分辨真感知 vs 腳本 mock。所以 6/18 的「最小可信」工作 = **在既有 dashboard 上加誠實層**（provenance 標籤 + frozen scoreboard chip + reason），**不是再做面板**。**缺的是可信度,不是覆蓋度。**

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——`existing live dashboard + provenance label + frozen scoreboard chip`。**明確不是**「完整 observability dashboard / runtime health monitor」 |
| 2 | claim_level | mainline |
| 3 | risk_role | **evidence_only** |
| 4 | dependency_role | **evidence** |
| 5 | observer | gateway live smoke + **frontend source-label smoke**（跑 live 看 `live` / 跑 mock 看 `mock`）+ screenshot / `/api/*` check |
| 6 | scenario | (a) 起 live gateway → 驗 UI 標 `live`；(b) 起 mock server → 驗 UI 明顯標 `mock`（不得偽裝）；(c) replay 一段對話 → 驗 trace drawer 顯 stage/status/reason；(d) 載入一份 `baseline_snapshot.json` → 驗 chip 顯 capability/grade/reason/timestamp；(e) 斷某來源 → 驗顯 `missing` 非空白 |
| 7 | metrics | provenance 正確率（mock↔mock / live↔live）/ trace 顯示完整度 / scoreboard chip 欄位齊全 / blocked+insufficient_data 有 reason |
| 8 | pass/deg/fail | **pass（5 條全成立）**：(1) 前端明確標來源 `live/mock/frozen/missing`；(2) **跑 mock server 時 UI 必須明顯顯 `mock`，不得偽裝 live**；(3) `/brain/conversation_trace` 能顯 stage/status/detail(reason)；(4) frozen scoreboard chip 顯 `capability_id/grade/reason(failure_reason)/last_tested_at`；(5) **blocked/insufficient_data 必帶 reason**（不准只顯 `fail`）。<br>**degraded**：live trace 有但無 scoreboard chip／有 chip 但無 provenance／trace 不完整但非 mock。<br>**fail**：UI 仍 mock 且無標籤／trace 完全顯不出／**scoreboard 偽裝成 live health**／blocked 無 reason |
| 9 | fallback | Studio 掛 → scoreboard grade 仍可由 **CLI / snapshot 檔**讀（§9），不影響 baseline 判讀；Studio 是 evidence 不是 authority |
| 10 | 換模型 | n/a（evidence 層）|

**⚠️ 必寫進 spec 的 overclaim 防線（Roy 鎖定）**：
> **Studio 顯示的是 evidence,不是 authority。** Studio 可展示 Brain trace / frozen scoreboard / live sensor events,**但不能宣稱「IE 第二道 gate 已吃 scoreboard / runtime 全層已 enforce」,因為 P1-1（`brain_node.py:505-533` executor 不查 grade/effective_status）尚未修**。Studio 顯示「gate blocked X」只反映 PawAI Brain（pawai_brain）那層的 gate 決策;IE scoreboard-aware enforcement 是 v0.2 待補。

**scope 例外聲明（修 Master Plan line 229 drift）**：frozen scoreboard chip 是 6/18 **新增的極小唯讀 Studio 任務**（`GET /api/scoreboard` 讀 `baseline_snapshot.json` → 前端一個 chip），**是 Master/Implementation Plan line 229「Studio UI 砍項」的有限例外** ── 例外範圍嚴格限：**唯讀、不 live recompute、不接 runtime Brain gate、只讀 frozen snapshot**。超出此範圍的 Studio health panel / runtime monitor 仍砍。

**code 接地**：
- **live 已存在**：`studio_gateway.py:73-82` 訂真 ROS topic（face/gesture/pose/speech/object + `/state/pawai_brain` + `/brain/proposal` + `/brain/skill_result` + **`/brain/conversation_trace`(:81)** + shadow）→ PawAIEvent envelope → `/ws/events`；video 走 Image→JPEG→WS binary。前端面板齊（`frontend/components/` face/gesture/pose/object/speech/chat/navigation/live）。**§7b 依賴的「Studio 顯真實 trace」架構上通**（trace 已 forward），差前端 trace drawer 渲染確認。
- **provenance greenfield**：現有 `source` 欄位（`contracts/types.ts:25,59,95,118,155`）是**感知模態**（face/speech/...）**非資料真偽**；mock(`backend/mock_server.py`) 發的 envelope 與 live **一字不差**；前端 `use-websocket.ts` 連同一 `/ws/events`、分不出後端是 gateway 還是 mock。→ **provenance 標籤是 #1 deliverable**。
- **scoreboard chip greenfield**：`/api/capability`（`studio_gateway.py:268,538-541`）只回 **Nav/Depth 的 Bool tri-state**（Phase B Trace Drawer），**不是 baseline scoreboard grade** → `/api/scoreboard` 為新 endpoint。
- **預設即 mock**：`start.sh:44-46` 預設起 mock server（port 8080）；live 要 `start-live.sh --live` 連 Jetson。→ 誠實層沒做之前,預設 demo 畫面就是假資料。

## 9. `cli.readiness` ✅（2026-06-01 拍定，pawai CLI recon file:line 接地）

> **authority 核心句**：`pawai readiness` 是 **demo readiness authority** ── 它以 **frozen baseline snapshot + deploy manifest + preflight metadata** 做 **fail-closed 判定**。Studio 只讀它的結果做 evidence 展示（§8），**Brain v0.1 不即時消費它**（v0.2 才接 runtime gate）。分工：`doctor`=系統現在能不能跑（環境/網路/lock/driver）；`readiness`=demo 用的 baseline snapshot 可不可信。**兩者不混。**

| # | 項目 | 決定 |
|---|---|---|
| 1 | 6/18 主張 | **是**——`pawai readiness` 作 demo readiness authority |
| 2 | claim_level | mainline |
| 3 | risk_role | **safety_support**（誤判 ready 會讓不可信數據上 demo / 餵 Studio，間接安全相關）|
| 4 | dependency_role | **evidence** |
| 5 | observer | **pytest 真值表 + 一次 Jetson smoke**（非採樣）。失敗模式是「該說不可信卻說 ready」(fail-open)，要窮舉真值表 |
| 6 | scenario | 真值表窮舉 (snapshot 缺檔 / schema 錯 / run_trusted=False / preflight fail / sha mismatch / capability list 不全 / age 過舊 / 全通過) → 預期 verdict；+ 1 次 Jetson smoke（真 snapshot → `pawai readiness` 跑得出 + `--json` 格式正確）|
| 7 | metrics | fail-closed 真值表覆蓋數 ÷ 應覆蓋數；`fail_open_count`（該 not_ready 卻 ready）|
| 8 | pass/deg/fail | **只有 pass / fail / insufficient_data，無 degraded**。**注意兩層別混**：(a)『**capability grade**』= readiness **機制本身**正不正確（真值表全綠 + Jetson smoke 過 → pass；任一 fail-open → fail；尚未建 → insufficient_data）；(b)『**runtime verdict**』= 命令對某份 snapshot 的輸出 `ready / not_ready`。scoreboard 評的是 (a) |
| 9 | fallback | readiness 機制本身壞 → 對自己也 fail-closed（當 not_ready）；Studio/CLI 顯 not_ready。任何不確定 = not_ready |
| 10 | 換模型 | n/a（CLI 工具層）|

**命令設計**：新 `pawai readiness` / `pawai readiness --json` 子命令（**與 `doctor` 分開、不塞進 doctor 主邏輯**；但 `doctor` 可呼叫它顯摘要）。

**檢查表（最小，全項皆 fail-closed 預設）**：
```text
baseline_snapshot.json 存在嗎？
snapshot schema version 對嗎？
run_trusted == true 嗎？
layer0_preflight 是 pass / pass_with_warnings 嗎？
snapshot git_sha 跟 deployed manifest（.pawai-last-deploy）sha 對得上嗎？
snapshot age（advisory，不擋 verdict）
15 個 capability 是否都列出？
mainline 能力是否都有 grade / reason？
```

**fail-closed 規則（任何不確定 = not_ready）**：
```text
snapshot 缺檔              → not_ready
schema invalid             → not_ready
run_trusted == false       → not_ready
layer0_preflight fail      → not_ready
snapshot sha != deploy sha → not_ready   ← 跑的不是這份 code，硬擋
capability list 不全       → not_ready
mainline 能力缺 grade/reason → not_ready
全部通過                   → ready
```

**有效期限（不設武斷時間 TTL）**：**硬 stale 訊號 = sha mismatch**（snapshot.git_sha != 當前 deploy sha → not_ready）。**age 只警告不擋 verdict**：`>3 days → warning`、`>7 days → strong warning`。理由：時間不重要,重要的是「這份 snapshot 是不是當前跑的 code 量的」── 3 天前但 sha 對=可信;1 小時前但 sha 不對=不可信。
> **概念別混（防 drift）**：deploy manifest 的 `stale_after_h=6h`（IMPL `current_run_meta`，檢查**部署記錄**新舊）與這裡 snapshot age 3d/7d advisory（檢查**baseline snapshot**新舊）是**不同概念**，兩者各自為政、不可互相套用。

**demo 當天 override（有界 + 留痕，不萬能）**：`pawai readiness --accept-warnings`（或 `--force-ready`）
- **可 override（軟條件）**：age warning / missing optional notes / preflight `pass_with_warnings`
- **不可 override（硬條件）**：snapshot missing / schema invalid / run_trusted=False / layer0_preflight fail / **sha mismatch** / capability list 不全
- override 必留痕（蓋進 readiness 輸出）：`{"override": true, "operator": "...", "reason": "...", "timestamp": "..."}` → demo 後追問題不失憶；evidence 看得出「人工放行,非真綠」。對齊 nav runbook「明確人工安全 override」。

**snapshot 路徑（沿用 nav env-override 慣例,不寫死）**：

| 用途 | 路徑 | git |
|---|---|---|
| working snapshot | `artifacts/baseline/baseline_snapshot.json`（Jetson `~/elder_and_dog/...`）| ❌ `.gitignore` 加 `artifacts/` |
| frozen demo snapshot | `artifacts/baseline/frozen/2026-06-18/baseline_snapshot.json` | ❌（量測產物）|
| example fixture（test + Studio mock + schema example）| `pawai_brain/test/fixtures/baseline_snapshot.example.json` | ✅ git-track（需穩定樣本）|

- `pawai readiness` + gateway `/api/scoreboard`（§8）皆用 env 可覆寫 `PAWAI_SCOREBOARD_PATH`（預設 working 路徑）。WSL 跑 readiness 經 SSH 讀 Jetson 路徑（沿用 `status.py:88 cat {jetson_repo}/.pawai-last-deploy`）。

**§8 ↔ §9 接點**：§9 產 + freeze 的 `baseline_snapshot.json` 就是 §8 `/api/scoreboard` 唯讀的那份;demo 當天用 frozen snapshot,不即時重算（避免 grade 抖動讓 Brain/UI 跳變）。**`/api/scoreboard` owner = Studio gateway/frontend team**（非 Brain），source path 由 `PAWAI_SCOREBOARD_PATH` 控制（預設 working 路徑）。

**code 接地**：
- **已存在**：`.pawai-last-deploy` provenance manifest（`main.py:95` 構造含 git sha + deploy ts、`main.py:643` 寫 Jetson、`status.py:12,88` 讀）;`pawai doctor`/`status` click 命令齊。
- **greenfield（全新）**：`pawai readiness` 子命令、`build_scoreboard.py`（Impl Plan Task 3b，`--out` 現為裸 `baseline_snapshot.json` 待定目錄）、`baseline_snapshot.json`、freeze 機制、`PAWAI_SCOREBOARD_PATH` env、§8 `/api/scoreboard`。

---

> 每節拍定後立即 fold + 該能力 dry-run（若涉及 observer 邏輯）。所有門檻 provisional until baseline。
