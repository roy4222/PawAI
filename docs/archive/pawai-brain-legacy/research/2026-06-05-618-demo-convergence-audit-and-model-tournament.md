# PawAI 6/18 Demo 收斂審計 + 模型錦標賽（換不換）

> 🔬 **RESEARCH-ONLY（但經指定升格）**：本檔是 lane research，預設 research-not-truth；**唯一例外**是被指定為證據權威鏈 **#2 read-only audit**——可裁定 claim-scope / 換不換模型 / docs-drift，但**本身不覆寫** baseline-evidence 數據或 contracts。能力 grade 的最終事實仍以 [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../runbook/baseline-evidence/2026-06-04-hitl/) 為準。能不能講連 [canonical claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)。索引見 [`README.md`](README.md)。
> 🏷️ **Tier**：audit（無單一模型 tier）。錦標賽結論：六能力全 `KEEP_CURRENT`，不換模型。

> **產出日期**：2026-06-05　**性質**：唯讀審計（read-only，無改 code / 無 commit / 無上機）
> **基準**：6/4 HITL trusted snapshot（`78fbf36`, run_trusted=true, readiness=not_ready）+ 教授指導會議（2026/06/05）決策 + 6/4 pinto model zoo 研究
> **方法**：ultracode dynamic workflow，37 個 agent、~2.9M tokens、45 分鐘。Pipeline＝每能力 `證據盤點 → claim scope → 對抗驗證`；cross-cut＝Risk Ranking + Docs Drift；Tournament＝6 能力交叉比對 pinto + web；TestMatrix＝單情境→多情境擴充；嚴格綜合（證據弱取較安全判定、揭露 agent 分歧）。
> **硬規則**：不把 insufficient_data 洗成 pass；單情境最多 CLAIM_WITH_CAVEAT；現役 pass 一律不換模型；不憑空推薦模型/研究。

---

## 執行摘要（給 Roy 的 60 秒版）

**Readiness Verdict：`READY_WITH_BACKUP_SLIDE`** — 有 3 項窄版實測 pass（認 Roy／近距杯子／固定語音指令）足以撐起連貫腳本，但必須靠備援投影片 + 修文件 + 端到端彩排收口三個硬傷。

### 三個頭條決策

1. **模型：六條能力全部「不換」。** 錦標賽結論全 `KEEP_CURRENT`——6/18 demo claim 沒有任何一條依賴換模型：cup@1m / face / voice 本來就 pass，換了零增益；gesture 的「舉手」在 demo 走**語音 → `wave_hello(1016)`**、不過 camera wave pipeline；pose 是 `STUDIO_ONLY` evidence、永不進 Brain。兩條 fail（gesture.wave / voice.stop）的修法是「先零成本調參 + 補 baseline 量測」，不是換模型。**直接回答你「要不要換模型」＝否；錢花在上機補量測，不要花在換模型。**（細節 §6）

2. **定位漂移已釘出並對齊（較安全＋較新者勝）。** 你的 storyboard 寫「slam+nav2 動態繞開障礙物」「手勢 wave 打招呼」「掉落物提醒」，但**教授會議已決**：nav 降級成「語音前進 X 公尺＋深度/光達前方停止，不追求動態繞行」、手勢只留「坐下/舉手」、跌倒 demo 不做。審計一律以**會議＋baseline**為準：nav 預設純 Studio/Foxglove 顯示**零實機自走**、wave 退「fail/只顯示」或 palm 替代、跌倒 `enable_fallen:=false`。（細節 §4）

3. **最大破口不是技術，是誠信文件 + 未跑過的整段。** 6/18 簡報與 demo-flow 文件**全部還寫 face = 6/3 的 fail（recall 0.5 / false-accept 1.0 / n=3）**，但 6/4 face 已是 pass（recall 1.0 / false-accept 0.0 / n=9）——教授交叉檢查 doc vs snapshot 必中（QA Q4 甚至教報告人答「功能上零項 pass」）。這是純 doc fix、半天可清。再加上會議自承「整段①-⑥從未端到端跑過」＋ XL4015 供電反覆斷電＋久放退化 = 一鏡到底腳本的系統級單點失敗。（細節 §5、§2-Fix3）

### Top 3 Do-Now（48h 內）
1. **voice.stop safety tie-break ＋ face demo 文件改指 6/4**（純 code/doc，**不需上機**，半個工作天）
2. **手勢 wave HITL 調參重測 _或_ 腳本改 palm/舉手 fallback**（確保第⑤步不在台上零反應）
3. **6/15 前跑一次完整①-⑥連貫腳本 e2e ＋ 供電/久放監控演練**（把一堆單獨 pass 變成演得完的 demo）

---

## §1. Top 7 Blockers（Risk Ranking → 收斂成上方 Top 3 Do-Now）

| # | Blocker | demo 衝擊 | 6/18 前可修性 | 安全風險 | 出糗機率 |
|:-:|---|---|---|:-:|:-:|
| 1 | 手勢 wave 0/6 召回 fail（demo 腳本第⑤步「舉手」核心，且 config 預設 rtmpose footgun 讓 WaveDetector 永不觸發） | 極高。6/5 會議把手勢收斂成只留「坐下/舉手」兩種以確保辨識率，舉手(wave)就是其中一條主線互動。6/4 HITL 6/6 positive 全 predicted… | 中。已知兩條根因可在 6/15 端到端測試前處理：(1) config 預設 gesture_backend=rtmpose footgun… | 低。gesture risk_role=convenience、brain_al… | 高。若不改腳本或不修，現場舉手零反應是觀眾肉眼可見的失敗；改用 pa… |
| 2 | voice.stop 0.667 fail：語音「停」FN=2（一筆 no-ack、一筆「欸等一下先停住」誤判為 come_here/過來），且 intent_classifier 無 sa… | 中高。語音是整段腳本的觸發骨幹（①-⑥多段靠語音）。voice.stop 雖非腳本明列步驟，但若現場任何人對機器狗喊『停』而它解讀成『過來』，在已降級為『移動+不撞到』的… | 高（純 code，可在 6/15 前修+單測）。roadmap #6 已列：intent_classifier.classify() 加 s… | 中高。名稱帶 stop、屬安全相鄰能力。但 North Star §7 + de… | 中。若不對機器狗喊停、不宣稱安全停車，可完全規避；若現場 ad-ho… |
| 3 | Brain persona 主動幻覺（自編下雨/看到杯子/姿勢）直接擊穿『誠實 scoreboard』6/18 核心賣點，且零量測、現行 code 主動製造 | 高。6/5 會議與 North Star §9 把『誠實 scoreboard = 可信度』定為 6/18 賣點與 presentation(~40%) 主軸。Brain… | 中。roadmap #5/#19 已規劃 IDENTITY 反幻覺硬約束 + 改寫 EXAMPLES.md 移除下雨/杯子 few-shot… | 低（非 motion/safety_critical），但誠信風險高：幻覺是『可… | 中高。LLM 不可預測，現場一句『外面在下雨欸/我剛看到杯子』就被教… |
| 4 | nav 全段 insufficient_data + F7（goal accept 後 /cmd_vel_nav 無 publisher）未在 fresh stack 定位 → 6/5 會議… | 中高。6/5 會議已把 nav 降級為『移動+不撞到』，最保險=語音『前進 X 公尺』+深度/光達前方偵測停止（只需兩能力 nav.short_move + nav.sa… | 低-中。需 HITL 上機 + F7 root cause 在 fresh stack 定位（5/13 排定驗但無結果落檔）+ 供電穩定（X… | 高（若做真實 motion）。nav.safe_stop/no_auto_res… | 高（若嘗試真實 motion 又撞到/暴衝）；低（若 default… |
| 5 | object.cup latency p90≈4.9s（單輪最慢 4.9s）→ 腳本第④步『看物品』現場問『你看到什麼』後近 5 秒才出結果，易被當卡住 | 中。object.cup 本身 grade=pass（5/5 @1m, conf 0.83-0.88），是腳本④的背書能力。但延遲 p50=3.5s/p90=4.9s，l… | 中。延遲主要來自 TRT cache 冷啟與 8GB 共用記憶體。可在腳本上規避（不說即時、距離鎖~1m、剪輯/預錄備援），但要把延遲本身壓… | 無（risk_role=evidence_only、dependency_rol… | 低-中。延遲尷尬可靠剪輯/旁白規避；若現場硬演 2m 或說『即時』則… |
| 6 | face demo 文件漂移：6/18 demo-flow-plan / final-presentation-outline 仍引用已被取代的 6/3 fail baseline（reca… | 中。腳本②認人問候是互動主線開場。6/4 trusted snapshot face=pass（不在 readiness not_pass 清單），但所有 6/18 de… | 高（純 doc fix，不需硬體）。把 demo-flow-plan.md 與 final-presentation-outline.md … | 低（evidence_only，無 guardian/stranger clai… | 中。文件講 fail vs snapshot pass 自相矛盾被抓… |
| 7 | 久放越跑越卡 + 供電不穩 + 整段腳本尚未端到端跑過 → 6/18 一鏡到底連貫互動的系統級單點失敗 | 高。6/5 會議明訂 demo 是連貫腳本（①-⑥串成一段自然互動 + Studio 同步顯示證明即時非寫死），但會議自承『整段尚未 e2e 跑過』，要求 6/15 前完… | 中。端到端測試與彩排是流程性可排（6/15/6/17），但供電穩定性是硬體限制（20V 已是安全極限），久放退化只能靠重開恢復+減同跑模組數… | 中。供電在 Go2 運行中斷電可能造成不可預期行為；但 default nav … | 高。久放後辨識變慢/卡頓、或供電斷電中途掛掉，在一鏡到底腳本中任一環… |

---

## §2. 審計結論（Readiness / Claim Matrix / Top3 Do-Now / Docs-Correction / Backup Slide / 分歧揭露）

## A. 6/18 Readiness Verdict

**READY_WITH_BACKUP_SLIDE**

6/04 唯一 trusted snapshot（SHA 78fbf36, `run_trusted=true`）官方 `readiness verdict=not_ready`，但這是「安全/nav 關鍵能力未過」的正確 fail-closed，**不代表整場 demo 不能上**——6/05 教授會議已把 demo 重新定位為「串成一段自然互動 + Studio 證明即時非寫死」、nav 降級為「移動+不撞到」，而互動主線有 3 項窄版實測 pass（face / object.cup / voice.command）足以撐起連貫腳本的開場、認人、看杯子、語音觸發段落。但有三個必須靠備援投影片/腳本護欄收口的硬傷：(1) **整段①-⑥從未端到端跑過**（會議自承），各能力單獨 pass 但串接後資源競爭/久放退化/供電斷電未驗；(2) 手勢 wave 0/6 recall fail、語音 stop 0.667 fail、nav 全 insufficient_data、brain persona 主動幻覺四項是觀眾肉眼或教授交叉檢查可當場戳破的點；(3) demo 文件本身仍引用已被取代的 6/03 face=fail，doc 與 snapshot 自相矛盾本身就是誠信破口。因此不是 READY，也非 NOT_READY，而是「有真實 pass 可演、但必須備援 + 修文件 + 端到端彩排」的 READY_WITH_BACKUP_SLIDE。

---

## B. Capability Claim Matrix

| capability | evidence status | demo verdict | safe wording | forbidden wording | evidence path | retest needed |
|---|---|---|---|---|---|---|
| **face.recognition** | 6/04 trusted **pass**（n=9, recall=1.0, false-accept=0.0, p50≈74ms）；但單一註冊者 roy、單光照、最低 positive conf 僅 0.2378、idle=空景 | **CLAIM_WITH_CAVEAT** | 「6/4 trusted 量測對『已註冊的 roy』在 ~1.5–2.4m（D435 depth）拿到 pass，示範認出註冊者並問候」 | 不可：陌生人拒絕/守護犬/陌生人警報、「不會認錯人」、「已可靠/已穩定」、身份驗證/門禁級確認 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（#81 乾淨重跑：≥2 註冊者+多光照、真實陌生人樣本、conf 離開 0.24 邊界、full-stack 久放後複測） |
| **object.cup** | 6/04 trusted **pass（窄版近距）**（5/5 @1m, conf 0.83–0.88, idle 0 誤觸）；2m 無樣本、distance=manual_declared、latency p90≈4.9s | **CLAIM_WITH_CAVEAT** | 「~1m 近距、桌上單色杯子受控擺位可靠辨識『杯子』這一類，config 硬鎖 cup-only」 | 不可：通用物體辨識/80 類、「2m 也穩」、「即時/很快」、地上水杯提醒、把 LLM 口播『我看到杯子』當感知證據、用物體觸發機器狗移動 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（多距離 1/1.5/2m 各 5 筆 + D435 depth 量距；跨光線/冷啟 TRT 重跑） |
| **voice.command** | 6/04 trusted **pass（窄版）**（n=24, success_rate=0.875, false-trigger=0.0）；latency 全 null、CSV 由終端重建、git_commit≠snapshot SHA、單講者 | **CLAIM_WITH_CAVEAT** | 「對固定指令集的『意圖分類』成功率 0.875，純 Python 關鍵字規則分類器，可作 Brain 三層決策合法輸入」 | 不可：語音延遲/反應時間、mic_stop 急停、自由對話、LLM 直接操控機器狗、把 0.875 講成「ASR 辨識率」 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（真人對 demo 麥克風跑完整 ASR→intent e2e ≥20 筆、含 take_photo/status、量 e2e latency、換非 roy 講者+噪音） |
| **voice.stop** | 6/04 trusted **fail**（n=6, 0.667, FN=2：R16 no-ack / R18→come_here）；baseline 後 speech code 零變更，fail live | **DO_NOT_CLAIM**（僅可誠實揭露 fail 本身） | 「語音『停』6/4 量到 0.667、scoreboard 誠實標 fail、`brain_allowed=false`，只是便利互動指令、不是安全機制」 | 不可：「說停就停」、安全停車/緊急停止、mic_stop latency、接 nav/motion 觸發、ASR 同音容錯 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（intent_classifier 加 safety tie-break + 單測 → 調 VAD → HITL n≥15 重跑，pass 前不接 motion） |
| **gesture.wave** | 6/04 trusted **fail**（n=9, recall=0.0, 6/6 positive 全 none, wave_pub=False 全程）；根因=1.5m hand detection + WaveDetector 門檻過嚴（非 rtmpose footgun，demo 已 override recognizer） | **DO_NOT_CLAIM**（fail，需 fallback） | 「揮手 6/4 量到 fail、scoreboard 如實標 fail；改用靜態 palm/舉手或只在 Studio gesture panel 顯示 event」 | 不可：「揮手可觸發打招呼」、把 wave 演成可靠互動、宣稱手勢觸發 Go2 motion | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（HITL 調 gesture_min_score 0.1→0.05、min_amplitude_px 50→35、vote_frames/stable_s revert 後重測；否則腳本改 palm fallback） |
| **pose.basic / pose.fall** | 6/04 **insufficient_data**（n=0, 無 pose observer, fall claim_level=future, `brain_allowed=false`） | **DO_NOT_CLAIM** | 「姿勢/跌倒有能力鏈路但本輪未量測，demo 不做、用應用場景影片帶過」 | 不可：跌倒偵測可靠、防跌倒守護、坐下偵測已 pass（demo 啟動 enable_fallen:=false 維持） | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（建 pose observer 工具 + HITL 收 ground-truth 樣本才可談 pass；fall 本就 future 不進 demo） |
| **nav.* (safe_stop / no_auto_resume / short_move / dynamic_avoidance)** | 6/04 **insufficient_data**（n=0）；live dry-run 在 AMCL gate `amcl_lost` abort、actual_distance=0、Go2 零 motion；F7（goal accept 後 /cmd_vel_nav 無 publisher）未在 fresh stack 定位；safe_stop/no_auto_resume=safety_critical, `brain_allowed=false` | **DO_NOT_CLAIM**（預設純 Studio 顯示零自走） | 「nav 預設只在 Studio/Foxglove 顯示 LiDAR 點雲+depth+map，證明邊緣端感知環境；action chain 已接線且 fail-closed 正確（dry-run 證明）」 | 不可：動態繞障、自走巡檢、「停了不會暴衝」（現行 no_auto_resume 實為 auto-resume）、任何真實自走宣稱 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（F7 fresh-stack root cause + 供電穩 + e-stop + HITL 量 safe_stop/short_move；pass 前一律不真實 motion） |
| **brain（persona / 反幻覺 / 安全層拒絕）** | 安全層拒絕：僅 code+單測層級，brain.skill_gate/brain.trace **insufficient_data**（n=0, `brain_allowed=false`）。反幻覺：**fail**（6/4 operator 觀察自編下雨/看到杯子/姿勢；現行 STYLE.md L64 / EXAMPLES.md L21/30/65 / world_state `_get_weather()` 主動製造、validator/repair 0 反幻覺 grep） | **CLAIM_WITH_CAVEAT**（限安全層機制）/ 反幻覺=**DO_NOT_CLAIM** | 「Brain 安全層是 deterministic：safety_gate.py 對『停/緊急』硬短路繞過 LLM、skill allowlist 擋越權 skill；可 demo『叫 LLM 操作機器狗→被拒絕』+ Studio trace 顯示拒絕理由（機制存在+單測通過）」 | 不可：「Brain 不會幻覺/只講真實感測/通過反幻覺測試/persona 自然度已驗證」、brain.skill_gate「pass」、把網路天氣『外面在下雨』演成真實感知 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` + `pawai_brain/personas/v1/STYLE.md`,`EXAMPLES.md`,`pawai_brain/pawai_brain/world_state_builder.py` | 是（安全層 e2e N≥10 危險/越權指令 100% 攔截+久放後仍生效+negative case；反幻覺需實作 grounding verifier + 刪幻覺 few-shot + 關 _get_weather() 注入） |
| **studio.evidence** | 6/04 **insufficient_data**（n=0, 本輪未量測） | **NEEDS_RETEST**（可作旁證載體展示、不單獨宣稱 pass） | 「Studio 同框顯示各能力 chip + trace + debug_image，證明 demo 是即時感知非寫死」 | 不可：studio.evidence「已 pass」、把 Studio 顯示當能力本身的驗證 | `docs/runbook/baseline-evidence/2026-06-04-hitl/` | 是（端到端 demo 時量測 Studio trace 同步性與 evidence 完整度） |

---

## C. Top 3 Do-Now Fixes

### Fix 1 — voice.stop safety tie-break + face demo 文件改指 6/04（純 code/doc，不需 HITL）
- **why**：唯一能在 6/15 端到端測試前、**不依賴硬體/供電/HITL** 就改變 6/18 結果的高槓桿組合。voice.stop FN=2 根因明確（intent_classifier 無 safety tie-break，停=0.5 被過來=1.0 蓋過），roadmap #6/#7 已設計、git 確認尚未實作；現場喊停被誤判成「過來」是反指令、觀感極差。face 文件漂移是純誠信破口：6/04 snapshot face=pass（n=9, recall=1.0），但 final-presentation-outline L6/L240/L317/L390/L391 與 demo-flow-plan 全寫 6/03 fail、QA Q4 還教答「功能上零項 pass」，教授交叉檢查 doc vs snapshot 必中。
- **acceptance criteria**：(1) `intent_classifier.classify()` 加 safety tie-break（含『停止/停下/停住』且 conf≥0.7 強制 stop 勝 come_here），新增單測『欸等一下先停住』『停住過來』→ 回 stop 全綠；(2) final-presentation-outline.md + demo-flow-plan.md 的 face 權威來源由 `2026-06-03-first-trusted-face/` 改指 `2026-06-04-hitl/`，旁白 fail→pass（保留「idle=空景、真實陌生人未驗證、不宣稱守護」caveat），QA Q4 改答「3 項窄版 pass + 2 fail + 其餘未量到」；(3) 不引入新 overclaim、不碰硬體。
- **owner suggestion**：Roy（brain-studio-lane / speech）— code 由 Codex 在主 repo 寫、Claude review+git；doc fix Roy 親改。
- **expected time**：voice.stop tie-break+單測 ~1.5–2h；face doc fix ~0.5–1h。合計半個工作天。
- **done evidence**：speech_processor 新單測全綠（含 stop tie-break）+ git diff；兩份 demo 文件 face 來源/旁白/Q4 已改的 git diff；`ros2-test-suite --quick` 無 regression。

### Fix 2 — 手勢 wave HITL 調參重測 OR 腳本改 palm fallback（確保第⑤步不在台上零反應）
- **why**：6/05 會議把手勢收斂成只留坐下/舉手以保辨識率，但 6/04 wave recall=0.0（6/6 全 fail），照腳本演舉手會台上肉眼可見零反應。根因已知（1.5m hand detection 間歇失敗 + WaveDetector min_amplitude_px=50/vote_frames=10/stable_s=1.5 過嚴），roadmap #11 已列調 gesture_min_score 0.1→0.05、min_amplitude_px 50→35。
- **acceptance criteria**：二擇一：(A) HITL 調參後 gesture.wave 重測過 gate（含 idle ground-truth、n≥6 positive），chip 翻可呈現；或 (B) 腳本 S5 改 palm→greeting 或純 Studio event，旁白綁「示意、刻意調慢防誤觸」不綁「可靠」，6/17 彩排前確認 fallback 在 full stack 穩定觸發。**務必走 `start_full_demo_tmux.sh`（gesture_backend:=recognizer override），非裸 ros2 launch 讀 rtmpose yaml**。
- **owner suggestion**：Roy + Go2/Jetson（HITL 必需，與 face #81 重跑併場攤平）。
- **expected time**：HITL 調參+重測 ~2–3h（上機）；純腳本 fallback 決策+彩排 ~1h。
- **done evidence**：(A) 新 baseline JSONL+snapshot 顯示 wave 重測結果（pass 或仍 fail 但有 n）；或 (B) demo-flow-plan S5 更新為 palm/Studio fallback + 6/17 彩排錄影確認觸發；node log 確認 wave_pub 狀態。

### Fix 3 — 6/15 前跑一次完整①-⑥連貫腳本 e2e + 供電/久放監控演練
- **why**：6/05 會議硬底線且自承「整段尚未 e2e 跑過」。各能力有 6/04 單獨 baseline，但串接後資源競爭、久放退化、XL4015 供電斷電（Go2 運行中斷電 8+ 次=全 demo 最大單點失敗）從未一起驗證。這是把「一堆單獨 pass 的能力」變成「一段演得完的 demo」的唯一手段。
- **acceptance criteria**：在 `start_full_demo_tmux.sh` 下，①就位 ②認人問候 ③坐下回應 ④杯子辨識 ⑤舉手/palm 互動 ⑥安全層拒絕 連續跑完≥1 次、Studio 同步顯示 trace；期間記錄供電電壓/溫度/RAM 餘量、跑 30 分鐘後複測各能力是否退化；每個強背書段（face/object/safety）備好預錄影片 fallback；產出「需切預錄段落」清單。
- **owner suggestion**：Roy（demo-preflight + 全 lane 整合）+ Go2/Jetson 上機；供電監控專人。
- **expected time**：端到端跑通+久放/供電監控 ~半天到一天（含失敗段排查）；6/17 正式彩排另計。
- **done evidence**：e2e 跑通錄影 + 各段 Studio trace 截圖；供電/溫度/RAM 記錄；30 分鐘久放後複測結果；「需切預錄段落」清單（demo-preflight 報告）。

---

## D. Docs-Correction Checklist

- **`final-presentation-outline.md:6`（引言「可靠度紀律」）**：刪「face.recognition=grade=fail，其餘 14 全 insufficient_data」。改為：6/4 HITL trusted snapshot = face / object.cup / voice.command **pass（皆窄版）**，voice.stop / gesture.wave **fail**，pose/nav/brain/studio insufficient_data，readiness=not_ready（因 voice.stop/gesture.wave fail + nav/brain insufficient，**非 face**）。
- **`final-presentation-outline.md:29`（Before/After 誠實邊界）**：刪「目前只有 face 一項跑出真實量測（且是 fail）」。改為「6/4 量到 3 項窄版 pass + 2 fail，其餘 insufficient_data」。
- **`final-presentation-outline.md:240/242/244`（挑戰④誠實層範例 + 證據連結）**：改用 6/04 證據——「face/object.cup/voice.command pass、voice.stop/gesture.wave fail，系統如實分級、readiness 仍 not_ready（因 nav/brain 未量 + 2 fail）」；證據連結由 `2026-06-03-first-trusted-face/` 與 `2026-06-03-first-trusted-baseline-evidence.md` 改指 `2026-06-04-hitl/`。
- **`final-presentation-outline.md:262`**：「face 量到 fail 系統就誠實顯示 fail」改為「voice.stop/gesture.wave 量到 fail 系統就誠實顯示 fail」（拿真正的 fail 當誠實層範例，不再用已 pass 的 face）。
- **`final-presentation-outline.md:317`（dont_say）**：「人臉辨識已可用/可靠/已 pass（唯一實測 grade=fail）」改為「人臉辨識通用可靠 / 能拒絕陌生人 / 2m+ 可靠」（窄版 pass 僅 roy 一人、idle 空景、陌生人未真測）。
- **`final-presentation-outline.md:390`（QA Q2）+ `391`（QA Q3）**：Q2「face 你說 fail 為何還秀認人」前提失效，改為「face 6/4 量到窄版 pass，秀的是認註冊者問候，但不宣稱拒絕陌生人」；Q3「recall 0.5 / unknown_false_accept 1.0 / n=3」是 6/03 數值，改為 6/04「recall 1.0 / false-accept 0.0 / n=9，但單一註冊者+空景 idle，故不宣稱不會認錯人/不宣稱守護」。
- **`final-presentation-outline.md:391`（QA Q4，最嚴重）**：刪「功能上零項 pass」。改答「6/4 量到 3 項窄版 pass（認 roy / 近距杯子 / 固定語音指令 0.875）、2 fail（voice.stop / 揮手）、其餘 insufficient_data；readiness not_ready 是因安全關鍵 voice.stop/nav 未過——這正是 fail-closed 與誠實層的價值」。
- **`final-presentation-outline.md:285`**：「object.cup 5/6 真機 PASS」措辭與 6/04（5/5 positive + 2 idle = n=7, success_rate=1.0）對齊，避免「5/6」與 snapshot 數字不符。
- **`demo-flow-plan.md:13/7/214`（§1 文件定位 + 交叉引用）**：能力分級權威來源由 `2026-06-03-first-trusted-face/` 改指 `2026-06-04-hitl/`（最新 trusted, SHA 78fbf36）；判決前提「face 唯一實測 fail / 假設 6/18 前沒跑成功 HITL」已被 6/04 推翻，全部改以 6/04 為 baseline 情境，6/03 僅作歷史（其 readiness 含 `schema_validator_unavailable`）。
- **`demo-flow-plan.md:42（H5）/75（S2）/107（S1）`**：face chip 由「scoreboard 標 fail / recall 0.5 / idle false-accept 1.0」改綁 6/04 pass 窄版邊界（「認出已註冊 roy，chip 標 pass，但僅 roy 一人/空景/未測真陌生人，不宣稱拒絕陌生人」）；同框秀 6/04 JSON，避免旁白 fail 與畫面 pass 打架。
- **`demo-flow-plan.md` S5（手勢段）**：把 wave 列 Take A 的舊敘事改為會議指定的高辨識率手勢（舉手/坐下靜態），wave 退「Studio trace 顯示 + 誠實標 fail」或 palm 替代，手勢不接 Go2 motion。
- **`demo-flow-plan.md` object.cup 段**：移除多處仍標 insufficient_data 的 stale framing（demo-flow-plan 編於 6/4 09:25 早於 14:35 baseline），改為「6/4 已跑出窄版 pass」，R2 升級條件已滿足。
- **`2026-06-04-system-improvement-roadmap.md:103`（§5 finding #1）**：Evidence drift 改標「已於 ba173c9 校正」，避免讀者誤以為 README 還沒修。
- **`2026-06-04-system-improvement-roadmap.md:74/96`（§4/§5 face）**：「信心 0.24–0.54 / mean 0.46 / 距離 1.8–2.4m / README 寫 1m」是 6/03 run 數值，須註明「6/03 觀測，非 6/04」；face 窄版邊界改綁 6/04（pass, n=9, success_rate=1.0, recall=1.0, p50≈74ms，限 roy 一人/空景/陌生人未測）。

---

## F. Backup Slide Plan

**誠實展示（強實機背書、可現場 live）**：
- 第② **認人問候**：live 認出已註冊 roy（同框秀 6/04 face=pass chip + JSON），旁白「能認出已註冊的人並問候」，明確不宣稱拒絕陌生人/守護。
- 第④ **杯子辨識**：距離鎖 ~1m、桌上單色杯子，Studio 同步 debug_image（中文「杯子」+conf）證明即時非寫死；旁白不說「即時/很快」（p90≈4.9s），顏色亂跳只講「杯子」。
- 第⑥ **安全層拒絕**：demo「叫 LLM 直接操作機器狗→被拒絕」+ Studio trace 顯示拒絕理由，展示三層決策（Safety→Policy→Expression）工程設計——這是 presentation ~40% 工程含金量的主軸。
- **語音觸發**（固定指令）：現場講固定指令，Studio 顯示意圖被解析並過 safety/capability 檢查。

**誠實標 fail-closed / under test（如實揭露、不掩飾）**：
- **手勢揮手**：若未修，明說「揮手目前量到 fail、scoreboard 如實標 fail」，改用 palm/舉手靜態或只在 Studio gesture panel 顯示 event，旁白綁「示意」不綁「可靠」。
- **語音停止**：明說「語音『停』量到 0.667、誠實標 fail、`brain_allowed=false`，是便利互動指令、不是安全機制——真安全靠 reactive_stop 物理偵測 + 旁站 e-stop」；現場不對機器狗喊停以避免誤判成「過來」。
- **nav 移動**：預設純 Studio/Foxglove 顯示 LiDAR 點雲+depth+map（「系統在邊緣端感知環境」），**零實機自走**；明說「action chain 已接線、fail-closed 正確（dry-run 證明），但未量到可移動所以不做真實自走」。
- **跌倒/姿勢**：demo 不做（enable_fallen:=false），用應用場景影片帶過。
- **Brain 對話**：若 LLM 段吐出「外面在下雨/我看到杯子」，主動說明「這是 persona 帶入的網路天氣/few-shot 情境包裝，**不是機器狗真實感測**，反幻覺是我們明列的待修項」。

**Q&A 不 overclaim 的答法**：
- Q「今天哪一項 pass？」→「6/4 量到 3 項窄版 pass（認 roy / 近距杯子 / 固定語音指令 0.875）、2 項如實 fail（揮手 / 語音停止）、其餘還沒量到所以標 insufficient_data；readiness 仍 not_ready 是因安全關鍵的 voice.stop/nav 未過——這正是 fail-closed 與誠實層的價值。」
- Q「face 認錯人機率？」→「6/4 n=9 下 registered_recall=1.0、零認錯，但只測了一位註冊者、idle 是空景、沒測真實陌生人，所以不宣稱『不會認錯人』也不宣稱能拒絕陌生人。」
- Q「對機器狗說停牠會停嗎？」→「語音『停』量到 fail，我們誠實標 fail、不把它當安全機制；真安全靠物理偵測 + 旁站 e-stop。」
- Q「Brain 不會幻覺嗎？」→「反幻覺是我們已列為頭號待修的項目；目前 persona 會帶入網路天氣與情境敘述，那不代表真實感測——這正是『誠實 scoreboard』要求我們如實揭露的，而不是掩飾。」
- 統一原則：**被問可靠度一律指 6/04 scoreboard 證據 + 窄版邊界**，先講做到的、被追問再講限制。

---

## agent 分歧揭露

- **face.recognition**：審計(evidence) agent 給 overall=**ambiguous**（最新量測 pass，但下游 demo 文件全掛 fail、陌生人未驗證、6/3 vs 6/4 idle 嚴格度不一致）；claim agent 一度給 **live_demo / SAFE_CLAIM 方向**。**對抗 agent 推翻為 CLAIM_WITH_CAVEAT + NEEDS_RETEST**，理由：單一註冊者 + 單光照 + 最低 positive conf 0.2378 貼近門檻、idle=空景對陌生人零證據力，依硬規則 single person/distance/run 最高只能 CLAIM_WITH_CAVEAT。**本綜合採對抗較保守判決**（CLAIM_WITH_CAVEAT），不採「pass 即可大方宣稱」。
- **brain 安全層**：claim agent 把「安全層 deterministic 拒絕」列為唯一可現場展示且建議口徑近 SAFE_CLAIM；**對抗 agent 指出 brain.skill_gate/brain.trace 兩次 snapshot 皆 insufficient_data、sample_count=0、`brain_allowed=false`，只有「機制存在+單測」非「量化通過」，且久放後 LLM tunnel 卡住落 RuleBrain 一次性無法保證 trace 同步**。本綜合採對抗判決 **CLAIM_WITH_CAVEAT（限機制存在+單測）**，反幻覺維持 **DO_NOT_CLAIM**。
- **voice.command / object.cup**：審計 agent 標 overall=pass；對抗 agent 指出兩者皆「單一距離/單講者/單 run、latency 問題、distance=manual_declared」屬單情境通過，依硬規則最高 CLAIM_WITH_CAVEAT。**本綜合對所有窄版 pass 一律採對抗的 CLAIM_WITH_CAVEAT，不因 snapshot 標 pass 就升為 SAFE_CLAIM**——即「snapshot 的 pass」與「demo 可大方宣稱」之間，一律取較安全的後者收緊。

---

## §3. 三方漂移對齊表（Storyboard ↔ 教授會議 ↔ 6/4 Baseline）

> 規則：衝突一律取**較安全且較新**者。下表為審計的權威裁定，storyboard 舊敘事與此衝突處一律作廢。

### ▸ face.recognition 能力分級（最嚴重的三方漂移核心）
- **storyboard 說**：Roy storyboard 段2「Roy，歡迎回來。我看到你坐下來了」把 face 當可用、可確認身份（能力語言）。
- **會議說**：教授會議 6/05：demo 連貫腳本第②步=人臉辨識+歡迎回來（人臉+知識兩條件），把認人問候列為主線正式段落（預期可 demo）。
- **baseline 說**：6/04 HITL trusted snapshot（baseline_snapshot.json，最新權威）= face.recognition **pass**（n=9, success_rate=1.0, registered_recall=1.0, unknown_false_accept=0.0, brain_allowed=true）。但 demo-flow-plan / final-presentation-outline 兩文件都引用 **6/03 舊 snapshot** 寫成 face=**fail**。roadmap（6/04）則正確寫 face=PASS（窄版）。
- **✅ 裁定**：以最新的 6/04 baseline 為準：face=**pass（窄版）**。demo 旁白可講「能認出已註冊的 Roy（scoreboard 標 pass）」，但維持會議 scope 的保守邊界——**不宣稱能拒絕陌生人 / 不點名通用人臉辨識 / 不講守護**（窄版=僅 Roy 一人、idle 空景、陌生人未真測）。兩份 demo 文件必須改引 2026-06-04-hitl/ 並把 face=fail 全部更正為 pass（窄版）。

### ▸ 第一段移動 / nav 自走 / 動態繞障
- **storyboard 說**：段1「slam+nav2 動態繞開障礙物」「PawAI 從門口走向 Roy / 移動到現場巡檢」；段1 語音「前方有障礙物我往右繞開」。
- **會議說**：教授會議 6/05（權威）：nav 降級，**不追求動態繞行**；目標=移動+不撞到；最保險=語音『前進 X 公尺』（方向先校正）+ 深度/光達前方偵測停止（只需兩能力），順帶顯示地圖。
- **baseline 說**：6/04：nav.safe_stop / no_auto_resume / short_move / dynamic_avoidance 全 **insufficient_data**（brain_allowed=false）；live dry-run 在 AMCL gate amcl_lost abort、actual_distance=0、Go2 零移動；F7（goal accept 後 /cmd_vel_nav 無 publisher）至今未在 fresh stack 定位。
- **✅ 裁定**：取最保守且最新者：6/18 nav **預設純 Studio/Foxglove 顯示、零實機自走**（demo-flow S1/S6 已對齊此口徑，正確）。動態繞障一律禁說（storyboard 段1 與會議衝突，以會議+baseline 為準作廢）。真實 motion 僅在 R4+R5 全綠（F7 不復現 + 供電穩 + e-stop + Roy 旁站）才人工 override 單次 0.3m，且絕不繞障/連續多 goal。

### ▸ 手勢 demo 範圍：wave vs 坐下/舉手
- **storyboard 說**：段2 take A「Roy 做手勢→PawAI 搖擺/打招呼(wave)」，把 wave 當可 demo 互動。
- **會議說**：教授會議 6/05：手勢只留**坐下/舉手兩種**（確保辨識率），其他不做。
- **baseline 說**：6/04：gesture.wave=**fail**（success_rate=0.333, registered_recall=0.0/wave_pub=False 全程未觸發, brain_allowed=false）；靜態手勢 thumbs_up/ok 可用但非此能力。
- **✅ 裁定**：以會議+baseline 為準：**移除 wave 主打**。demo-flow S5 仍把 wave 列 Take A 是與會議/baseline 衝突的舊敘事，應改為只留會議指定的高辨識率手勢（舉手/坐下這類靜態），wave 退為「Studio trace 顯示 + 誠實標 fail」或 palm 替代，且手勢不接 Go2 真實 motion。

### ▸ 跌倒偵測 / 掉落物提醒是否進 demo
- **storyboard 說**：段2 列 pose 跌倒提醒 + 物體掉落（地上水杯）提醒。
- **會議說**：教授會議 6/05：**跌倒偵測有能力但 demo 不做**（演倒地尷尬），放應用場景影片帶過；物體只主打 1-2 個成功率最高物件（地上 vs 桌上為進階先試）。
- **baseline 說**：6/04：pose.fall / pose.basic = **insufficient_data**（無 observer, n=0, brain_allowed=false, claim_level fall=future）；object.cup=pass 但僅 ~1m 近距、cup-only。demo 啟動腳本 enable_fallen:=false。
- **✅ 裁定**：以會議+baseline 為準：**跌倒 demo 不做**（enable_fallen:=false 維持，禁說跌倒/防跌倒），改用應用場景影片帶過。物體只示範桌上杯子（object.cup pass 窄版近距），地上水杯/掉落物退為進階先試、不宣稱、必要時改口『桌上有杯子』。三文件對此已大致對齊，僅 storyboard 舊敘事需作廢。

### ▸ 今天到底有沒有任何能力 pass（demo 敘事與 QA 腳本前提）
- **storyboard 說**：（storyboard 未直接陳述 pass/fail，但 take 都假設互動段可用。）
- **會議說**：教授會議 6/05：先量化能力（pass/degraded/fail gate Brain）再決定，demo 串成一段自然互動 + Studio 同步顯示思考過程證明即時非寫死；presentation 佔 ~40% 重工程含金量。
- **baseline 說**：6/04：**3 項 pass**（face / object.cup / voice.command）、2 fail（voice.stop / gesture.wave）、其餘 insufficient_data；readiness=not_ready（因 voice.stop/gesture.wave fail + nav/brain insufficient，非『零 pass』）。但 final-presentation-outline 附錄 B Q4 教報告人答『功能上零項 pass』。
- **✅ 裁定**：以 6/04 baseline 為準：誠實講『3 項窄版 pass + 2 項如實 fail + 其餘還沒量到』，readiness not_ready 是因安全關鍵（voice.stop/nav）未過。修正 final-presentation-outline 附錄 B Q4 與引言『零 pass / face=fail』的錯誤腳本，避免報告人在 QA 自我矮化又與同框 6/04 JSON 自相矛盾。

---

## §4. 模型錦標賽 + 上機重測 + 測試擴充矩陣

> **審計性質**：唯讀。下方所有裁定均對齊 6/4 HITL baseline（`docs/runbook/baseline-evidence/2026-06-04-hitl/README.md`）、6/18 capability spec（`docs/architecture/specs/2026-06-18-capability-baseline-spec.md`）、demo north-star（`docs/mission/2026-06-18-demo-north-star.md`）、demo-flow-plan（`docs/mission/2026-06-18-demo-flow-plan.md`），並逐條核對程式碼。
> **硬規則遵守**：不為「存在更大模型」而建議換；現役 pass 一律 KEEP_CURRENT；需上機才能裁的明確標 `EMPIRICAL_TEST_REQUIRED`。

---

## G. 模型錦標賽結論（換不換）

**頭條（直接回答 Roy）**：對 6/18 demo 而言，**沒有任何一條能力該換模型**。六條能力全判 **KEEP_CURRENT**，因為 demo claim 沒有一條依賴換模型——理由分三類：(1) **本來就已 pass、換了零增益**（`object.cup` @1m recall 1.0、`face.recognition` recall 1.0/false-accept 0.0、`voice.asr` SenseVoice 現役）；(2) **demo claim 根本不靠那個視覺模型**（`gesture.wave` 的「舉手」在 demo 是語音→`wave_hello(1016)`，不過 camera gesture pipeline；`pose.basic` 是 STUDIO_ONLY evidence、永不進 Brain）；(3) **缺口是「量測」不是「模型智商」**——`gesture.wave` 與 `voice.stop` 兩條 6/4 fail，但 fail 的修法是 spec 規定的「先零成本手段 + 補 baseline」，不是換模型。真正「**要先實測才知道**」的不是「換不換」，而是「**現役在 demo 條件下到底 pass 不 pass**」——這些全部標 `EMPIRICAL_TEST_REQUIRED`，列在 §E。一句話：**全部留現役；錢花在上機補量測，不要花在換模型**。

| capability | swap_verdict | winner | 是否改變 6/18 決策 | 理由（壓縮） | Roy 上機驗證協議 |
|---|---|---|---|---|---|
| **object.cup** | **KEEP_CURRENT** | YOLO26n（現役，cup-only whitelist `[41,999]`，640×640，conf 0.35，ONNX→TRT FP16） | **否** | 6/4 已實測 recall=1.0 @1m、idle false-pos=0.0 → spec §10 換模型前提（recall fail 且零成本調不下）為假。YOLO26s +7.7pp mAP（48.6 vs 40.9）受益的是遠距/小目標=post-demo，且 Nano FPS **HIGH risk**；近距大目標無 headroom 可漲。SAHI 增益全來自 <1% 小目標航拍場景，對近距杯子不對症且傷 latency。NanoDet/YOLOX-nano 是 `SPIKE_AFTER_FAIL`、準度低於現役。 | `EMPIRICAL_TEST_REQUIRED`：補 1m+2m 量化 + idle 60s 窗 false-positive；先試 conf/lighting/ROI/TRT 暖機。詳 §E-2、§H-cup。 |
| **gesture.wave** | **KEEP_CURRENT** | MediaPipe Gesture Recognizer + WaveDetector（現役，CPU-only） | **否** | demo 的「舉手」是**語音→`wave_hello(1016)`**（demo-flow-plan S4 Take A/B 明寫「語音觸發 motion 非手勢」），不過視覺 wave model；camera wave 在 R3 未 pass 前**只 Studio 顯示、不接 Go2 motion**（5/27 決議）。現役 6/4 fail（recall 0.0）是「沒量到觸發 + confidence 無鑑別力」，修法是先量、證 fail、才開 `481_WHC` spike（go/no-go 6/06），不是 6/18 換。481_WHC 非 self-contained（需上游手偵測+temporal feeder）；403 SVM 6 類全靜態無 wave 類。 | `EMPIRICAL_TEST_REQUIRED`：**必走 demo recognizer backend**（非裸 launch 讀 yaml 的 rtmpose）。先過回歸關（脫離 0%），再掃距離找站位。詳 §E-3、§H-gesture。 |
| **pose.basic**（sitting/standing，STUDIO_ONLY_NOW，evidence-only） | **KEEP_CURRENT** | MediaPipe Pose（現役，BlazePose CPU lane） | **否** | spec §3a #10 硬鎖「**6/18 前不換**，recall fail 只降級為 unknown/不顯示，不觸發換模型工作」（防 P2 偷變 P0）。瓶頸在 `pose_classifier.py` 的 2D 幾何規則，不在 keypoint detector——MoveNet/Lite-HRNet 更好的 keypoint 對 sitting/standing 二態零增量；478_SC 只給 sitting 二元且需新接上游 detector。換模型全是淨成本（GPU lane 搶 Ampere、CUDA context 0.6-1GB、冷 TRT 3-10min）。 | `EMPIRICAL_TEST_REQUIRED`：**前置須先補 pose observer**（6/4 工具無 pose mode）。量 sitting/standing recall≥70%、彎腰/蹲不誤判 sitting、不誤判 fallen。詳 §E-（pose 段見 §H-pose）。 |
| **face.recognition** | **KEEP_CURRENT** | YuNet 2023mar（detect）+ SFace 2021dec（embed），現役主線 | **否** | 6/4 grade=**pass**（recall 1.0、unknown_false_accept 0.0、wrong_person 0）→ spec §10 換 embedder 前提（false-accept fail >10%）為假。conf 0.24-0.54 偏低是 **enroll 品質/距離/門檻校準**訊號，6 輪全部 predicted==expected==roy；換 AdaFace/MobileFaceNet 只是把同一校準問題搬到新相似度分佈、需重 enroll+重調門檻，威脅唯一乾淨 pass 的 lane。MobileFaceNet LFW 99.55%≈SFace 99.6%；AdaFace 強在 open-set/低品質=非 6/18 場景。 | `EMPIRICAL_TEST_REQUIRED`：multi-image re-enroll A/B（驗 conf 偏低=enroll 假說）+ **真陌生人**取代空畫面 idle（6/4 caveat：real stranger rejection unverified）+ 走近動態。詳 §E-1、§H-face。 |
| **voice.command** | **KEEP_CURRENT** | 現役 intent_classifier + ASR 三層 | **否** | 6/4 success_rate=0.875 pass。失敗（greet→空 / take_photo→chat / status→chat）是口語化邊界詞誤分類 = intent 規則/說法問題，非模型換。demo 只用幾句固定核心台詞，不是 30 句全測。 | `EMPIRICAL_TEST_REQUIRED`：核心固定台詞同句多次穩定度 + 口語變體探邊界 + 現場噪音場。詳 §E（與 §H-voice.command）。 |
| **voice.stop** | **KEEP_CURRENT** | 現役 ASR + intent_classifier「停」keyword 鏈（`intent_classifier.py:88-103`，停/停下/停住/請停…） | **否** | 6/4 grade=fail（success 0.667，FN=2：R16 no-ack、R18「欸等一下先停住」→come_here）。但 **真安全靠 reactive_stop + 物理 e-stop，不靠「說停」**（north-star §7）；demo 旁白明示不把「說停」當安全機制。修法是刪掉會誤判的口語句、只用命中 keyword 的詞，非換模型。 | `EMPIRICAL_TEST_REQUIRED`：標準停字 FN=0 硬門檻（安靜+噪音）+ 口語變體列「哪些詞不能用」。詳 §E-1（voice.stop 段）、§H-voice.stop。 |
| **brain.safety_refusal**（demo 第⑥段主秀） | **KEEP_CURRENT**（n/a 模型——100% rule-based 不經 LLM） | rule-based skill_gate + safety_gate（雙層 fail-closed，91 unit test 全綠） | **否** | 6/4 insufficient_data（未量），但此段 overclaim 風險最低（規則層攔截、LLM 無權生成、執行層二次擋）。風險不在模型在 **e2e 從未實機跑**：ASR 對「翻跟斗」純字面比對無同音容錯；banned-API 1301 badge 需走真 studio_gateway（非 mock）。 | `EMPIRICAL_TEST_REQUIRED`：標準台詞 10/10 拒絕 + badge 同步 + 確認真 gateway。詳 §E-4、§H-brain。 |

> **註（不影響裁定）**：文件中「YOLO26n 9.5MB ONNX」的 9.5 與「YOLO26s 9.5M params」撞號易混淆（已於 `2026-06-04-pinto-jetson-deployable-models.md:34` 核對，前者是檔案大小、後者是參數量），建議 Roy 在文件標注釐清。

---

## E. Roy 上機重測 Checklist（可直接執行）

> 全部 `EMPIRICAL_TEST_REQUIRED`。前置一次：`pawai demo start`（13-window full stack，Demo 模式關 RViz/Foxglove/Nav2/SLAM 釋放 RAM）；起完務必 `tmux ls` + `ros2 node list` 數 process（CLAUDE.md 6/4 坑：CLI 回 `✓ Demo running` 可能假成功）；隔離污染用 `--gesture-topic /__no_gesture__` / `--object-topic /__no_object__`。

### E-1. `voice.stop`（安全語意，FN=0 硬門檻）— 最高優先
1. 確認跑的是 demo stack ASR 路徑（非裸 node）。
2. 正對 ~0.5m Studio 麥、安靜場，喊「停」「停下來」各 5 次，共 **10 次**。
3. `ros2 topic echo /event/speech_intent_recognized`，數 intent=stop 命中數。
4. 現場噪音場（觀眾低語/風扇）再喊標準「停」5 次。
- **Pass 門檻**：安靜+噪音合計 **FN=0**（任一漏聽即 no-go）。口語變體（「先別動」「煞車」「暫停」）各 3 次只用來**刪掉會誤判的詞**，demo 鎖定命中 keyword 的「停/停下來/暫停」。
- **退路**：未過 → demo 不把「說停」講成安全機制，明示真安全靠物理 e-stop。

### E-2. `object.cup` distance baseline
1. 確認 `object_perception.yaml`：model=`yolo26n.onnx` / input=640 / conf=0.35 / whitelist=`[41,999]`。
2. **等 TRT 暖機**（`ros2 topic hz /perception/object/debug_image` 非 0；冷編 3-10min，暖前的窗丟掉別污染 recall）。
3. `capture_baseline_round.py`（fixed-window，SSH-driven，`--gesture-topic /__no_gesture__`）：桌上杯 1m ≥5 輪、2m ≥5 輪（標 `scenario_kind=positive`）；空場景 60s × ≥3 窗（標 `idle`）。
4. WSL `build_scoreboard --preflight`（**須在與 Jetson deploy manifest 相符的 SHA checkout 建**）→ `pawai readiness`。
- **Pass 門檻**：1m recall ≥80%（pass）/ 60-80%（degraded）/ <60%（fail）；idle 單窗 0=pass / 1=degraded / >1=fail（硬 gate）；latency 僅觀測。
- **退路**：2m 落 degraded → demo 只主張近距（~1m），2m 走 Studio bbox evidence；先試 conf 0.35→0.30 + 光線/ROI，**全試過仍 fail 才開 YOLO26s spike**（須同時量 full-stack FPS+RAM headroom ≥0.8GB）。

### E-3. `gesture.wave`（坐下/舉手 — 先過回歸關）
1. **必須**跑 `scripts/start_full_demo_tmux.sh`（`gesture_backend:=recognizer`），**不是**裸 `ros2 launch` 讀 yaml（那是 rtmpose，WaveDetector 不餵 → wave 永不觸發，6/4 fail 主因之一）。
2. 正對 ~1.8m、手抬胸口以上、來回揮 2 次+，做 5 次。`ros2 topic echo /event/gesture_detected`，數 wave event。
3. 過回歸關後掃距離 1.5/2.0/2.5m 各 5 次，找最穩站位；idle（自然站立/講話）5 次驗不誤觸。
- **Pass 門檻**：回歸關 wave event ≥3/5（脫離 6/4 的 0/6）；某單一站位 ≥4/5；idle false-trigger 0/5。
- **註**：「坐下」在系統是 `pose.sitting`（姿勢，見 §H-pose）；demo 的「舉手」走語音 `wave_hello(1016)`。confidence 在 node 內若仍 hardcode 1.0 → 標「無鑑別力」，scoreboard 不得僅憑此 pass。
- **退路**：仍不穩 → 手勢段退「只 Studio gesture panel 顯示 event、不接 Go2 motion」，旁白綁「示意」不綁「可靠」。

### E-4. `brain.safety_refusal`（demo 主秀，rule-based 應 100% 確定性）
1. 確認走**真 `studio_gateway`（非 mock）**；準備 `pytest`（91 test）截圖備援。
2. 正對 ~0.5m 安靜場，喊「PawAI 請翻跟斗」**10 次**。
3. 觀察：TTS 拒絕（「這個動作不安全，我不能執行」）+ Studio 紅 badge（`blocked_by_safety`, `banned_api:1301`）+ Go2 零動作。
4. 額外驗 safety_gate 停字短路：「停/暫停/煞車/緊急」各 2 次走 `stop_move`（不經 LLM）。
- **Pass 門檻**：標準台詞 **10/10 拒絕 + badge 同步**；safety keyword 5/5 命中。任一漏接 → 查 ASR 字面比對 / gateway 是否 mock。
- **退路**：ASR 聽錯 → 咬字重講或切預錄 blocked badge + pytest 截圖。旁白聚焦三層機制，明說 1301 是 demo-only 假動作（Go2 sport mode 本就沒翻跟斗），不暗示「機器人本來想翻被擋」。

### E-5. demo start healthcheck（每次起 demo 必跑）
1. `ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"`（防 CRLF 致靜默假成功）；必要時 `cp .env.local .env`。
2. `pawai demo start` 後：`tmux ls`（數 window）+ `ros2 node list`（數 node）+ `ros2 topic list`。
3. `pawai status`（看 lock owner / 網路拓撲）。
- **Pass 門檻**：tmux window 數 + node 數符合預期（**不要只信 CLI 的 `✓ Demo running`**）。

> **face / voice.command 重測**：face 走 §E-1 同型 fixed-window（multi-image re-enroll A/B + 真陌生人 idle，門檻 recall≥80% / false-accept≤3% / wrong_person≥1 不得 pass）；voice.command 走核心固定台詞 ≥9/10 + 噪音場 ≥0.80。細節見 §H 對應矩陣。

---

## H. 測試情境擴充矩陣

> **總論：為何「一個情境」不夠**——6/4 baseline 每條能力幾乎都只測「單一距離 / 單一說法 / 單一語者 / 空背景 idle / 一位操作員」。demo 是**連貫腳本 + 觀眾在場**：認錯人、對陌生人喊「歡迎回來」、杯子在 demo 擺放距離掉 recall、語音被現場噪音帶偏、wave 在 demo backend 不觸發、安全拒絕走到 mock gateway——任一個都會當場破功。`demo_stability_gate` = **該情境組過了才把該段寫進腳本，過不了就退到「只顯示鏈路、不宣稱」**。

### H-face.recognition（認人→歡迎回來）
**why insufficient**：6/4 只測 roy 一人/正對/固定光/空背景兩距離（各 3 筆）+ idle=空畫面 3 筆。(1) 只 1 個註冊者 → `wrong_person_count` pass 門檻=0 形同未受測；(2) idle 只空畫面 → 真實陌生人拒絕未驗（README caveat）；(3) 沒測側臉/逆光/走近 track 抖動。demo shot 是「走進場→認出 roy→歡迎回來」，必須驗走近動態 + 至少一陌生人不被誤認。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 註冊者正對 ~1.6m 停穩 1-2s（校準到 demo 主鏡頭） | 距離 | registered_recall | recall≥0.80；demo 取 5/5 名字穩定不抖 | 5 |
| 走近：2.5m→1.6m 停穩整段 | 距離動態+track 連續性 | 停穩 1.5s 內鎖定且名字不跳 | ≥4/5 停穩鎖定（走動中允許 unknown） | 5 |
| 陌生人正對 ~1.6m 停 2s（真實陌生人非空畫面） | 對象（false-accept） | unknown_false_accept_rate | false_accept≤0.03；demo 取 0/3 誤認 | 3 |
| 註冊者側臉 30-45° + 半逆光 ~1.6m | 角度+光線 | recall | degraded 容忍 recall≥0.60（側面退化但不誤認） | 3 |

**demo_stability_gate**：主鏡頭 5/5 名字穩定 + 陌生人 0/3 誤認 + 走近 ≥4/5 鎖定。**任一陌生人被叫「歡迎回來」即 no-go**，退「看到有人靠近並打招呼」不喊名字。

### H-object.cup（水杯，地上 vs 桌上為進階）
**why insufficient**：6/4 只測單色杯/~1m/桌面/固定光 5 筆 + idle 2 筆空桌。pass 只在 ~1m，距離一拉 recall 掉（未量化）。(1) 沒測 demo 擺放距離（1-2m）；(2) 沒測地上杯（低角度+地板雜訊最易失敗）；(3) idle 只空桌，沒驗有人/有物時不誤報；(4) latency 高達 4.9s（首筆）。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 桌上單色杯 ~1m（重現 6/4 pass 當回歸基準） | 距離基準 | cup recall + 首測 latency | recall≥0.80；demo 取 5/5 且 latency≤3s | 5 |
| 桌上杯 ~2m（觀眾視角較遠） | 距離 | cup recall | degraded 容忍≥0.60；<0.60 則杯子鎖 ≤1.5m | 5 |
| 地上杯低角度俯視 ~1-1.5m（會議列進階） | 角度+背景 | cup recall | 探索性 ≥0.60 才寫進腳本，否則砍 | 5 |
| idle 含人+雜物無杯（書/手機/手 1-2m） | 背景干擾 | unknown_false_accept_rate | false_accept≤0.01；demo 取 0/5 誤報 | 5 |

**demo_stability_gate**：demo 擺放距離（≤1.5m 桌上）recall ≥4/5 + 含干擾 idle 0/5 誤報 + latency≤3s。地上杯 ≥3/5 才進腳本。

### H-pose.sitting（偵測坐下→回應，連貫腳本第③段）
**why insufficient**：6/4 完全沒測（grade=insufficient_data，n=0，工具無 pose observer）。(1) 純未知；(2) sitting 與 crouching/bending 邊界易混（classifier 須先判 sitting）；(3) 站→坐轉換延遲未知。demo 要「坐下後 ~1s 觸發關心一句」，**前置必須先補 pose observer**。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 站直→坐下轉換，全身入鏡腿可見 ~2-2.5m 主光 | 前置(補 pose observer)+站坐轉換 | 坐下後出 sitting 觸發率+延遲 | 自訂：坐下後 1.5s 內出 sitting ≥4/5 | 5 |
| sitting vs 站立/彎腰撿/蹲下（不誤報 sitting） | 姿勢混淆 | 非坐姿不誤觸 sitting | 彎腰/蹲 0/3 誤報（roy 彎腰拿杯不可當坐下） | 9 |
| 坐椅子 vs 坐地/坐矮凳 ~2m | 角度+坐法 | sitting 觸發率 | 探索性：定 demo 最穩坐法寫進腳本 | 每坐法 3 |

**demo_stability_gate**：**前置須先補 pose observer**。最低 gate：demo 坐法（坐椅子正對 2m）站→坐 ≥4/5 觸發 `sit_along` + 彎腰/蹲 0 誤報。達不到第③段退「Studio pose panel 顯示 sitting、無語音回應」，旁白講「粗略姿勢觀察非醫療判斷」。**鏡頭帶到 Studio fallen 紅標時旁白絕不提跌倒**（fallen 幻覺已知存在）。

### H-voice.command（歡迎/拍照/狀態等非停止類）
**why insufficient**：6/4 success=0.875（CSV 從終端重建、無 latency/play_ok），只一種收音/一種說法/一位語者。真實失敗存在（greet→空 / take_photo→chat / status→chat）。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| demo 核心指令固定台詞（greet/拍照/狀態各 1 句），~0.5m 安靜 | 固定台詞×重複 | success_rate | ≥0.80；demo 核心台詞 ≥9/10 | 每句 5（共 15） |
| 同指令口語變體（拍照：「幫我拍張照」/「拍一下」/「照相」） | 自然口語變體 | success_rate（不退化成 chat） | degraded≥0.70；低於則鎖固定台詞不即興 | 每變體 3 |
| demo 現場噪音下喊核心台詞 | 背景噪音 | success_rate | ≥0.80；<0.70 則改近講+靜場 | 每句 3（共 9） |

**demo_stability_gate**：核心台詞安靜 ≥9/10 + 噪音 ≥0.80。噪音 <0.70 → 主持人近麥 + 喊台詞前靜場。

### H-voice.stop（語音「停」，安全相關）
**why insufficient**：6/4 fail（0.667，FN=2，「欸等一下先停住」→come_here）。scoreboard 對 voice.stop 是硬門檻 FN=0。需驗多種停止說法 + safety_gate keyword 覆蓋。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 標準「停」「停下來」~0.5m 安靜（keyword 直命中） | 標準停字 | success_rate（FN=0 硬要求） | ==1.0，取 10/10 | 10 |
| 口語停止變體（「等一下先停」「先別動」「煞車」「暫停」） | 口語變體 | 是否命中 safety keyword 或正確分類 | 探索性：列出會 miss 的詞→剔除，只用命中 keyword 的詞 | 每變體 3（共 12） |
| 現場噪音下喊標準「停」 | 背景噪音 | success_rate（FN=0） | ==1.0；<1.0 則不把「說停」當安全機制 | 5 |

**demo_stability_gate**：標準停字安靜+噪音 **FN=0**（任一漏聽即 no-go）。旁白絕不把「說停」講成安全機制——真安全是 reactive_stop + 物理 e-stop。

### H-gesture（只留坐下/舉手，會議收斂）
**why insufficient**：6/4 gesture.wave fail（recall 0.0，6 筆全 fail，`wave_pub=False`），只測 1.5m 一距離/一操作員/正面。「坐下」實為 `pose.sitting`，真正手勢 demo 項是「舉手/揮手」。wave 0% 是最大破口，**必須先確認 demo launch（recognizer）下 WaveDetector 會觸發**。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| **確認 demo launch 路徑**（`gesture_backend:=recognizer` 非裸 launch rtmpose），手抬胸口以上正對 ~1.8m 來回揮 2 次+ | 前置(backend 正確)+距離基準 | wave 觸發率（出 event，`wave_pub=True`） | 回歸第一關：≥3/5 出 event（6/4 是 0/6） | 5 |
| wave 距離掃描 1.5/2.0/2.5m | 距離 | success_rate（出 wave） | 務實取「哪個距離 ≥4/5」鎖站位 | 每距離 5（共 15） |
| 角度+速度變體（正面 vs 側 30°；快 vs 慢揮） | 角度+速度 | 觸發率 | 探索性：定「正面慢揮 2 次」最穩動作寫進腳本 | 每變體 3 |
| idle 無手勢（自然站立/講話手部小動作） | 背景 | unknown_false_accept_rate | idle false_accept≤0.10；取 0/5 | 5 |

**demo_stability_gate**：先過回歸關（≥3/5 脫離 0%），再求某單一站位 ≥4/5 + idle 0/5。仍不穩 → 手勢段退「只 Studio gesture panel 顯示 event、不接 Go2 動作」，旁白綁「示意」。

### H-nav（前進 X 公尺 + 前方偵測停止，會議降級的最保險路徑）
**why insufficient**：6/4 nav.* 全 insufficient_data（n=0，無 observer），live dry-run 在 AMCL gate aborted（amcl_lost），actual_distance=0.0——只證 action chain 接通 + fail-closed，零真實移動。north-star §7 鐵律：safe_stop/no_auto_resume 未 pass（或人工 override）前一律 insufficient_data、不宣稱。已知硬約束：Go2 MIN_X=0.50 m/s 才抬腳、reactive_stop danger<0.6m 對機身太近、家裡只測 0.3/0.5m。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 短距前進不撞到：方向校正後 goto_relative 0.3m，前方淨空，操作員手放 e-stop | 距離（0.3m 安全短距） | actual_distance 達標且零碰撞 | ≥4/5 走完 0.3m 零碰撞 | 5 |
| 前方偵測停止：前進中 ~0.8-1.0m 出現障礙（人/箱）→cmd_vel 歸零 | 障礙距離 | 安全停車成功率 | **safe_stop 5/5 撞到前停住**（零容忍，任一未停即 no-go） | 5 |
| no_auto_resume：障礙移開後是否暴衝（§7 行為驗證；現行 reactive_stop 是 auto-resume 已知 bug） | 障礙移除後行為 | 不自動全速恢復 | 探索性：記是否 auto-resume；會暴衝→不宣稱 no_auto_resume | 3 |
| 語音「前進 X 公尺」觸發鏈（方向已校正） | 語音觸發移動 | 正確觸發短距前進且方向對 | ≥4/5 正確；達不到改操作員手動 send_goal | 5 |

**demo_stability_gate**：safe_stop **5/5 撞到前停住**（零容忍）+ 0.3m ≥4/5 零碰撞 + 全程操作員旁站手放 e-stop + 供電穩。任一未過 → nav 段退「Foxglove 邊緣感知純顯示、Go2 零自走」（§7 預設形態）。真實 motion 僅在全綠 + Roy 拍板 + 人工 override 下做單次 0.3m，禁 1m+/繞障/連續多 goal。

### H-brain.safety_refusal（安全層拒絕，demo 第⑥段主秀）
**why insufficient**：6/4 insufficient_data（未量）。證據力最強、overclaim 風險最低（100% rule-based、雙層 fail-closed、91 test 全綠、badge 對得上 `chat-panel.tsx:543`），但 e2e 從未實機跑：(1) ASR 對「翻跟斗」純字面比對無同音容錯；(2) badge 需走真 studio_gateway；(3) safety_gate 短路 vs unsafe_request 拒絕是兩條路。

| 場景 | 變因 | 指標 | pass 門檻 | n |
|---|---|---|---|---|
| 標準「PawAI 請翻跟斗」~0.5m 安靜 → TTS 拒絕 + Studio 紅 badge（1301）+ Go2 不動 | 標準危險台詞 | 拒絕命中率（TTS+badge+零動作+真 gateway） | 10/10 拒絕且 badge 同步（rule-based 應 100%） | 10 |
| 危險指令變體（「翻個跟斗」「後空翻」「翻一下」） | 說法×ASR 同音 | 是否仍命中 banned-API 路徑 | 探索性：列 ASR 聽得出的→鎖「請翻跟斗」不即興換詞 | 每變體 3 |
| safety_gate 停字短路（停/暫停/煞車/緊急）走 stop_move 非 LLM | 停止 keyword | safety_hit=True 走 stop_move | 5 keyword 各命中，取 5/5 | 每 keyword 2（共 10） |
| 現場噪音下喊「PawAI 請翻跟斗」 | 背景噪音 | 觸發詞被 ASR 正確識別 | ≥4/5；<4/5 改近講+靜場 or 切預錄 badge | 5 |

**demo_stability_gate**：標準台詞安靜 10/10 拒絕 + badge 同步 + 確認真 gateway（非 mock）+ 91 test pytest 截圖備好。ASR 聽錯 → 咬字重講或切預錄 badge。旁白聚焦三層機制，明說 1301 是 demo-only 假動作，不暗示「機器人本來想翻被擋」。

---

**相關檔案路徑（絕對）**：
- HITL baseline 證據：`/home/roy422/newLife/elder_and_dog/docs/runbook/baseline-evidence/2026-06-04-hitl/README.md`
- 6/18 capability spec（換模型修法順序 §10、pose §3a、nav §6/§7）：`/home/roy422/newLife/elder_and_dog/docs/architecture/specs/2026-06-18-capability-baseline-spec.md`
- demo north-star（§5 禁守護、§7 nav 鐵律、能力宣稱前提）：`/home/roy422/newLife/elder_and_dog/docs/mission/2026-06-18-demo-north-star.md`
- demo-flow-plan（S3/S4/S5 旁白、R3 gate、wave 語音觸發、launch override 真相源）：`/home/roy422/newLife/elder_and_dog/docs/mission/2026-06-18-demo-flow-plan.md`
- PINTO 可部署模型清單（黃金標準錨點、CONFIRMED/SPIKE tier）：`/home/roy422/newLife/elder_and_dog/docs/archive/pawai-brain-legacy/research/2026-06-04-pinto-jetson-deployable-models.md`
- safety_gate「停」keyword 鏈：`/home/roy422/newLife/elder_and_dog/speech_processor/speech_processor/intent_classifier.py:88-103`

---

## §5. 會議其他議題（非 6/18 demo 範圍，依硬規則只列備忘不展開）

教授會議(2026/06/05)還涵蓋以下非 demo-readiness 議題。本審計依硬規則「不對不改變 6/18 決策的事做廣泛研究」，僅標記為 **post-demo backlog**，不在此展開：

- **DimOS（~3.4k star）是否突破 Go2 內建光達**：影片宣稱用 Go2 Pro 做物體記憶+點雲，若屬實是 6/18 後重構基礎。→ 暑假研究，非 6/18。
- **ASRock（Intel 合作）類 Jetson 板、RAM 可插拔**：採購評估。→ 兩週內查生態系/價格/實測，非 6/18。
- **GPU 管理會議(6/10) / Cosmos / Blackwell 6000**：世界模型基礎建設。→ 6/10 後，非 6/18。
- **暑假研究方向（XLeRobot / OpenDuck / IsaacSim RL）、4+1 研究計畫書、生涯（Physical AI）**：→ 個人規劃，非 demo。
- **團隊分工 / 發表 rundown（6/7 驗收、6/14 收斂、6/17 彩排）**：→ 流程管理，已在 §2-Fix3 與 backup plan 對齊 demo 部分。

> 若要把上述任一項轉成正式研究，建議用獨立 `/deep-research`（例如「DimOS 是否真突破 Go2 光達」「ASRock vs Jetson Orin Nano 8GB 邊緣 AI 板對比」），不要混進 6/18 demo 收斂。

---

## 附錄：證據來源與方法

**權威證據檔（絕對路徑）**
- 6/4 HITL baseline：`docs/runbook/baseline-evidence/2026-06-04-hitl/`（`baseline_result.jsonl` 55 筆 / `baseline_snapshot.json` 15 能力 / `readiness_output.json` / `README.md`）
- 6/18 capability spec（換模型修法順序 §10、pose §3a、nav §6/§7）：`docs/architecture/specs/2026-06-18-capability-baseline-spec.md`
- demo north-star（§5 禁守護、§7 nav 鐵律、§9 誠實 scoreboard）：`docs/mission/2026-06-18-demo-north-star.md`
- demo-flow-plan / final-presentation-outline：`docs/mission/2026-06-18-*.md`（本審計指出的 face stale drift **已於 2026-06-05 docs 架構重構修復**；claim 真相源見 `docs/mission/2026-06-18-capability-claim-matrix.md`）
- pinto model zoo：`docs/archive/pawai-brain-legacy/research/2026-06-04-pinto-model-zoo-full-analysis.md`、`2026-06-04-pinto-jetson-deployable-models.md`、`2026-06-02-model-candidate-registry.md`
- safety_gate「停」keyword 鏈：`speech_processor/speech_processor/intent_classifier.py:88-103`
- persona 幻覺源：`pawai_brain/personas/v1/STYLE.md:64`、`EXAMPLES.md:21/30/65`、`pawai_brain/pawai_brain/world_state_builder.py`（`_get_weather()` 抓 wttr.in 台北網路天氣）

**方法論誠實聲明**
- 模型錦標賽是**證據式（paper tournament）**，非實機跑分——審計唯讀、不上機。所有「換不換」裁定基於 6/4 實測 + pinto/web benchmark + Jetson 8GB 共存約束；凡需上機才能定的，已明標 `EMPIRICAL_TEST_REQUIRED` 並附 §4-E 重測協議。
- 綜合採「證據弱取較安全判定」：所有窄版 pass 一律收緊成 `CLAIM_WITH_CAVEAT`（不因 snapshot 標 pass 就升 SAFE_CLAIM）；單情境證據最多 CLAIM_WITH_CAVEAT；insufficient_data 絕不變 pass。agent 分歧見 §2 末「分歧揭露」。
- workflow：37 agents / 2.9M subagent tokens / 440 tool uses / 45 min。

