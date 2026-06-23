# 2026-06-18 Capability Claim Matrix（全 repo claim 真相源）

> **Status**: active / **canonical claim source** ｜ **Created**: 2026-06-05 ｜ **Owner lane**: mission（戰略邊界）
> **這頁是什麼**：6/18 demo / 簡報 / 文件對「每一項能力能講什麼、不能講什麼、屬哪個分級、證據在哪」的**單一真相源（canonical）**。任何 mission 文件（demo-flow-plan / final-presentation-outline / README）提到能力 claim，一律**連結到本頁**，不重複整份散文。
> **這頁不是什麼**：不是量測協定（怎麼量見 [`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)）；不是能力 grade 的原始數據（grade 與 caveats 的最終事實依據是 baseline-evidence snapshot，見下方權威鏈）。本頁是把 evidence + audit 的判決收斂成「能不能講」的對照表。
>
> **證據權威鏈（最新優先）**：
> 1. **實測證據（最終事實）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/) — 6/04 HITL trusted snapshot，SHA `78fbf36`，`run_trusted=true`，readiness=`not_ready`。grade + honesty caveats 凌駕一切敘事。
> 2. **收斂審計（read-only）**：[`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) §2 — claim-scope / 換不換模型 / docs-drift 裁定。
> 3. **能力規格（怎麼量）**：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)。
> 4. **戰略邊界（能不能講）**：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md) v2 — §5 禁說 / §7 nav 鐵律 / §9 scoreboard-first。
>
> `2026-06-03-first-trusted-face/` 已被 6/04 取代，僅作歷史。

---

## 0. 速查表（grade 一覽）

| capability | grade（6/04） | claim level | demo 怎麼用 |
|---|---|---|---|
| `face.recognition` | 🟢 pass（窄版） | CLAIM_WITH_CAVEAT | Brain 可用：認出已註冊 Roy 並問候（窄版邊界） |
| `object.cup` | 🟢 pass（窄版近距 ~1m） | CLAIM_WITH_CAVEAT | Brain 可用：~1m 近距 cup-only 辨識（窄版邊界） |
| `voice.command` | 🟢 pass（窄版） | CLAIM_WITH_CAVEAT | Brain 可用：固定指令集意圖分類 |
| `voice.stop` | 🔴 fail | DO_NOT_CLAIM | 只誠實揭露 fail；**不可當安全停車** |
| `gesture.wave` | 🔴 fail | DO_NOT_CLAIM | camera 動態 wave 不演；退靜態手勢 / Studio 顯示 |
| `pose.basic` / `pose.fall` | ⚪ insufficient_data | DO_NOT_CLAIM | Studio-only；跌倒是 future、`enable_fallen:=false` |
| `nav.safe_stop` / `no_auto_resume` / `short_move` / `dynamic_avoidance` | ⚪ insufficient_data | DO_NOT_CLAIM | 預設純 Studio/Foxglove 顯示零自走 |
| `brain.skill_gate` / `brain.trace`（安全層拒絕） | ⚪ insufficient_data | CLAIM_WITH_CAVEAT（限機制） | 可 demo deterministic 安全拒絕 + trace；非 e2e pass |
| brain 反幻覺 | 🔴 fail | DO_NOT_CLAIM | 不宣稱「不會幻覺 / 已通過反幻覺測試」 |
| `studio.evidence` | ⚪ insufficient_data | NEEDS_RETEST | 旁證載體；不單獨宣稱 pass |
| `cli.readiness` | ⚪ insufficient_data | — | 本輪未量測 |

> **readiness=`not_ready`** 是正確 fail-closed，因 `voice.stop` / `gesture.wave` fail + nav / brain 未量，**非因 face**。

---

## 1. 8 欄位能力卡（每能力 canonical）

> 欄位：Current Claim｜Claim Level｜Evidence-Provenance｜Pass/Degraded/Fail/Insufficient｜Fallback｜Non-Claims｜Model Candidates｜Next Retest。
> grade 的原始數值與 honesty caveats 以 baseline-evidence `README.md` 為準，本頁不重抄完整 JSONL。

### face.recognition

- **Current Claim**：6/04 trusted 量測對「已註冊的 Roy」在 ~1.5–2.4m（D435 depth）拿到 pass，示範認出註冊者並問候。
- **Claim Level**：CLAIM_WITH_CAVEAT
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=9, registered_recall=1.0, unknown_false_accept=0.0, p50≈74ms）
- **Pass/Fail**：🟢 pass（窄版）——僅單一註冊者 Roy、單光照、最低 positive conf 僅 0.2378、idle=空景。
- **Fallback**：track 抖動 / 名字閃 → 退泛稱「看到有人靠近並打招呼」或只秀 `debug_image` 證鏈路。
- **Non-Claims**：陌生人拒絕 / 守護犬 / 陌生人警報 / 「不會認錯人」 / 「已可靠 / 已穩定」 / 身份驗證 / 門禁級確認 / 2m+ 可靠 / 通用人臉辨識。
- **Model Candidates**：BASELINE_NOW（YuNet + SFace，現役 pass 不換）。
- **Next Retest**：#81 乾淨重跑（≥2 註冊者 + 多光照、真實陌生人樣本、conf 離開 0.24 邊界、full-stack 久放後複測）。

### object.cup

- **Current Claim**：~1m 近距、桌上單色杯子受控擺位可靠辨識「杯子」這一類，config 硬鎖 cup-only（`class_whitelist=[41,999]`）。
- **Claim Level**：CLAIM_WITH_CAVEAT
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（5/5 positive @1m, conf 0.83–0.88, idle 0 誤觸, n=7）
- **Pass/Fail**：🟢 pass（窄版近距）——2m 無樣本、distance=manual_declared、latency p90≈4.9s。
- **Fallback**：距離拉遠 / 延遲尷尬 → 鎖 ~1m、不說「即時」、改「我看到桌上有物品」。
- **Non-Claims**：通用物體辨識 / 80 類 / 「2m 也穩」 / 「即時 / 很快」 / 地上水杯提醒（絆倒守護語言）/ 把 LLM 口播「我看到杯子」當感知證據 / 用物體觸發機器狗移動。
- **Model Candidates**：BASELINE_NOW（YOLO26n TRT FP16，現役窄版 pass 不換）。
- **Next Retest**：多距離 1 / 1.5 / 2m 各 5 筆 + D435 depth 量距；跨光線 / 冷啟 TRT 重跑。

### voice.command

- **Current Claim**：對固定指令集的「意圖分類」成功率 0.875，純 Python 關鍵字規則分類器，可作 Brain 三層決策合法輸入。
- **Claim Level**：CLAIM_WITH_CAVEAT
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=24, success_rate=0.875, false-trigger=0.0；latency 全 null、CSV 由終端重建、git_commit≠snapshot SHA、單講者）
- **Pass/Fail**：🟢 pass（窄版）。
- **Fallback**：ASR 聽錯 → 清楚發音 retake。
- **Non-Claims**：語音延遲 / 反應時間 / mic_stop 急停 / 自由對話 / LLM 直接操控機器狗 / 把 0.875 講成「ASR 辨識率」。
- **Model Candidates**：BASELINE_NOW（規則分類器 + SenseVoice/Whisper ASR，現役不換）。
- **Next Retest**：真人對 demo 麥克風跑完整 ASR→intent e2e ≥20 筆（含 take_photo/status）、量 e2e latency、換非 Roy 講者 + 噪音。

### voice.stop

- **Current Claim**：語音「停」6/04 量到 0.667、scoreboard 誠實標 fail、`brain_allowed=false`，只是便利互動指令、**不是安全機制**。
- **Claim Level**：DO_NOT_CLAIM（僅可誠實揭露 fail 本身）
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=6, 0.667, FN=2：R16 no-ack / R18→come_here）
- **Pass/Fail**：🔴 fail（baseline 後 speech code 零變更，fail live）。
- **Fallback**：真安全靠 `reactive_stop` + 物理 e-stop；語音停只作便利指令，現場不對機器狗喊停。
- **Non-Claims**：「說停就停」 / 安全停車 / 緊急停止 / mic_stop latency / 接 nav / motion 觸發 / ASR 同音容錯。
- **Model Candidates**：SPIKE_AFTER_FAIL（不是換模型；intent_classifier 加 safety tie-break + 調 VAD）。
- **Next Retest**：intent_classifier 加 safety tie-break + 單測 → 調 VAD → HITL n≥15 重跑，pass 前不接 motion。

### gesture.wave

- **Current Claim**：揮手（camera 動態 wave）6/04 量到 fail、scoreboard 如實標 fail；改用靜態 palm / 舉手或只在 Studio gesture panel 顯示 event。
- **Claim Level**：DO_NOT_CLAIM（fail，需 fallback）
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=9, recall=0.0, 6/6 positive 全 none, wave_pub=False 全程）
- **Pass/Fail**：🔴 fail——根因 = 1.5m hand detection 間歇 + WaveDetector 門檻過嚴。靜態手勢 thumbs_up / ok 可用但**非此能力**。
- **Fallback**：camera 動態 wave 不演（已知 fail 非現場故障）；退靜態 palm / 舉手，或語音 `wave_hello(1016)`（**另一條路徑**），或只在 Studio 顯示並標 fail。
- **Non-Claims**：「揮手可觸發打招呼」 / 把 wave 演成可靠互動 / 宣稱手勢觸發 Go2 motion / 把 `wave_hello` 語音路徑混為 camera wave 已 pass。
- **Model Candidates**：SPIKE_AFTER_FAIL（不是換模型；調 gesture_min_score / min_amplitude_px / vote_frames）。
- **Next Retest**：HITL 調 gesture_min_score 0.1→0.05、min_amplitude_px 50→35、vote_frames/stable_s revert 後重測；否則腳本改 palm fallback。

### pose.basic / pose.fall

- **Current Claim**：姿勢 / 跌倒有能力鏈路但本輪未量測；demo 不做、用應用場景影片帶過。
- **Claim Level**：DO_NOT_CLAIM
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=0, 無 pose observer, fall claim_level=future, `brain_allowed=false`）
- **Pass/Fail**：⚪ insufficient_data（pose.basic = Studio-only）；跌倒是 **future**、非緊急行為。
- **Fallback**：鏡頭帶到 Studio fallen 紅標時旁白**絕不提跌倒**；demo 啟動維持 `enable_fallen:=false`。
- **Non-Claims**：跌倒偵測可靠 / 防跌倒守護 / 坐下偵測已 pass / 把 pose 觀察當醫療判斷。
- **Model Candidates**：FUTURE_RESEARCH（跌倒）；pose.basic 待建 observer。
- **Next Retest**：建 pose observer 工具 + HITL 收 ground-truth 樣本才可談 pass；fall 本就 future 不進 demo。

### nav.safe_stop / nav.no_auto_resume / nav.short_move / nav.dynamic_avoidance

- **Current Claim**：nav 預設只在 Studio / Foxglove 顯示 LiDAR 點雲 + depth + map，證明邊緣端感知環境；action chain 已接線且 fail-closed 正確（dry-run 證明，**非真實移動 / 非動態避障**）。
- **Claim Level**：DO_NOT_CLAIM（預設純 Studio 顯示零自走）
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=0；live dry-run 在 AMCL gate `amcl_lost` abort、actual_distance=0、Go2 零 motion；F7 = goal accept 後 `/cmd_vel_nav` 無 publisher，未在 fresh stack 定位）
- **Pass/Fail**：⚪ insufficient_data。dry-run 只證 fail-closed + action chain 接線，不證真實移動或動態避障。
- **Fallback**：nav 全段降純 Studio 顯示；真實 0.3m motion 僅限 F7 fresh-stack 不復現 + 供電穩 + e-stop + Roy 旁站的 stretch goal。
- **Non-Claims**：動態繞障 / 自走巡檢 / 完整自主導航 / 跟隨人 / 「停了不會暴衝」（現行 no_auto_resume 實為 auto-resume）/ 任何真實自走宣稱 / 把 voice.stop 講成 safety stop。
- **Model Candidates**：FUTURE_RESEARCH（PINTO WHC/SC spike go/no-go 另案）；nav stack 現役不換。
- **Next Retest**：F7 fresh-stack root cause + 供電穩 + e-stop + HITL 量 safe_stop / short_move；pass 前一律不真實 motion。

### brain.skill_gate / brain.trace（安全層拒絕 + 反幻覺）

- **Current Claim（限安全層機制）**：Brain 安全層是 **deterministic**：safety_gate 對「停 / 緊急」硬短路繞過 LLM、skill allowlist 擋越權 skill；可 demo「叫 LLM 操作機器狗 → 被拒絕」+ Studio trace 顯示拒絕理由（**機制存在 + 單測通過**）。
- **Claim Level**：CLAIM_WITH_CAVEAT（限安全層機制）/ 反幻覺 = DO_NOT_CLAIM
- **Evidence-Provenance**：安全層拒絕 = code + 單測層級（91 pure-Python test），`brain.skill_gate` / `brain.trace` 本輪 **insufficient_data**（n=0, `brain_allowed=false`）。反幻覺 = **fail**（6/04 operator 觀察 persona 自編下雨 / 看到杯子 / 姿勢）。
- **Pass/Fail**：⚪ insufficient_data（skill_gate / trace 未量 e2e）；反幻覺 🔴 fail。
- **Fallback**：安全拒絕只說「邏輯 + 91 test + Studio 即時顯示」，**不說「實機端到端驗證過」**；persona 幻覺句出現時不當真實感知。
- **Non-Claims**：「Brain 不會幻覺 / 只講真實感測 / 通過反幻覺測試 / persona 自然度已驗證」 / `brain.skill_gate`「pass」 / 把網路天氣「外面在下雨」演成真實感知 / 「非幻覺自主 agent」。
- **Model Candidates**：BASELINE_NOW（safety = deterministic rule，不依賴 LLM）；反幻覺 grounding verifier = SPIKE_AFTER_FAIL。
- **Next Retest**：安全層 e2e N≥10 危險 / 越權指令 100% 攔截 + 久放後仍生效 + negative case；反幻覺需實作 grounding verifier + 刪幻覺 few-shot + 關 `_get_weather()` 注入。

### studio.evidence

- **Current Claim**：Studio 同框顯示各能力 chip + trace + debug_image，證明 demo 是即時感知非寫死。
- **Claim Level**：NEEDS_RETEST（可作旁證載體展示、不單獨宣稱 pass）
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（n=0, 本輪未量測）
- **Pass/Fail**：⚪ insufficient_data。evidence 顯示 / provenance 有價值，但**不等於能力 pass**（除非綁 trusted baseline 資料）。
- **Fallback**：前端無 fetch `/api/scoreboard` 的 chip 牆 → 開場 / 收尾改秀 git-tracked baseline-evidence JSON + dev trace GateChip。
- **Non-Claims**：studio.evidence「已 pass」 / 把 Studio 顯示當能力本身的驗證。
- **Model Candidates**：STUDIO_ONLY_NOW（顯示載體，不進 Brain motion）。
- **Next Retest**：端到端 demo 時量測 Studio trace 同步性與 evidence 完整度。

---

## 2. 模型研究分層（避免把研究當實作 backlog）

| 標籤 | 意思 | 對應能力 |
|---|---|---|
| **BASELINE_NOW** | 現役 pass / 機制可用，**不換模型** | face / object.cup / voice.command / brain 安全層 |
| **STUDIO_ONLY_NOW** | 只進 Studio 顯示，不進 Brain motion | studio.evidence / pose.basic |
| **SPIKE_AFTER_FAIL** | 先零成本調參 + 補 baseline，**不是換模型** | voice.stop / gesture.wave / brain 反幻覺 grounding |
| **FUTURE_RESEARCH** | future vision，不進 6/18 | pose.fall（跌倒）/ nav 全段 / PINTO WHC/SC spike |

> **錦標賽結論（6/05 audit §6）**：六條能力全 `KEEP_CURRENT`——6/18 demo claim 沒有一條依賴換模型。兩條 fail 的修法是調參 + 補量測，不是換模型。

---

## 3. 用詞紀律（一行版，細節回 North Star §2/§5）

- 一律「守望 / 提醒 / 回報 / 非接觸 / 可解釋互動」；**禁用**守護 / guardian / 陌生人警報 / 保護長者 / 照護安全 / 防跌倒。
- 被問可靠度，一律指 6/04 scoreboard 證據 + 窄版邊界；先講做到的、被追問再講限制。
- 窄版 pass 不擴張：face=僅 Roy/空景、object.cup=~1m cup-only、voice.command=固定指令分類。
- fail 誠實揭露：voice.stop 不當安全停車、gesture.wave camera 動態不演。
- insufficient_data 只顯示不宣稱：nav 零自走、pose Studio-only、studio.evidence 不單獨 pass。
