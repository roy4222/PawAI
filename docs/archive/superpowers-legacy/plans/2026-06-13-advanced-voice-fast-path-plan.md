# Advanced Voice / Dialogue Fast Path — 延遲與防幻覺進階優化（Cloud B）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核，審核前不實作、不改 runtime、不改 demo flow、不碰任何既有檔案（只 Write 本份）
> **作者 lane**：Cloud B（Advanced Capability Upgrade Plan，硬底線 6/18 期末發表）
> **上游連結**：
> - [語音模組 README](../../pawai-brain/speech/README.md)（能力 claim 入口、TTS routing、ASR 三級 fallback、已知問題）
> - [語音模組 CLAUDE.md](../../pawai-brain/speech/CLAUDE.md)（不能改的硬規則：echo gate 1.5s、Whisper cuda+float16、LLM timeout>2s fallback）
> - [speech.md 架構詳述](../../pawai-brain/architecture/0511/speech/speech.md)（11-stage pipeline、yaml 參數、VAD 2-10s 瓶頸、執行緒模型）
> - [speech-runtime-flow.md](../../pawai-brain/architecture/0511/speech/speech-runtime-flow.md)（三段管線 STT/Brain/TTS、topic 表）
> - [speech-tts-lanes-megaphone.md](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)（dual-route、cache key、Megaphone 4001/4003/4002）
> - [2026-03-24 speech pipeline report](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)（RESEARCH-ONLY；VAD 2-10s 最大瓶頸、fast path 0.002s、cache hit）
> - [2026-03-21 STT benchmark](../../pawai-brain/speech/research/2026-03-21-stt-benchmark.md)（RESEARCH-ONLY；Whisper small/tiny RTF）
> - [能力 claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)（`voice.command`=🟢pass窄版 CLAIM_WITH_CAVEAT；`voice.stop`=🔴fail DO_NOT_CLAIM）
> - [aggressive master plan §B-4](2026-06-13-aggressive-pre618-master-plan.md)（6/18 前 runtime 換參預設「不換」）
> - [Cloud A demo phase conductor plan](2026-06-13-demo-phase-conductor-plan.md) / [Cloud A 計畫群](2026-06-13-demo-flow-reliability-master-plan.md)（offline fallback / phase / demo 可靠度歸 Cloud A）
> - [Nav capability ladder C1-C12](../../navigation/2026-06-13-nav-capability-ladder.md) / [claim wording F1-F10](../../navigation/2026-06-13-nav-618-claim-wording.md)（本 plan 不含 nav 能力；引用僅為對齊 no-overclaim 詞彙）
>
> **這份是什麼**：在語音既有 pipeline 之上的「**進階能力升級層**」——把延遲（fast-path 繞 LLM）與防幻覺（Whisper 靜音段假文字、intent 邊界）做成可量化、可離線 replay 的進階優化。具體 8 個 sub-direction：① ASR anti-hallucination ② VAD threshold tuning ③ rule-based demo command fast path ④ 小模型 intent classifier 可行性 ⑤ cloud LLM vs local rule engine routing ⑥ local TTS / pre-render phrase pack ⑦ TTS ack / request_id ⑧ interrupt / cancel speaking。所有結論強制分級 proven / needs_hitl / research_only / do_not_claim_by_618。
>
> **這份不是什麼**：
> - **不是 Cloud A 的保守版 demo flow**：phase conductor / **offline fallback 主線** / demo 可靠度 / canned phrase timeout 編排歸 Cloud A，本 plan **不重複 offline fallback**，只專注 fast-path 延遲與 anti-hallucination 進階優化。任何 task 觸及 demo flow 可靠度一律標「歸 Cloud A，本計畫不重複」。
> - **不重抄既有 lane plan**：Lane 1-6 是已排程 aggressive refactor；引用用連結、不複製內文。
> - **不是換 runtime 的授權**：6/18 前換 runtime 模型/參數/閾值的預設答案是「不換」（[master B-4](2026-06-13-aggressive-pre618-master-plan.md)）。本 plan 全部 spike 為離線 additive 或 env-gated default-off，**目標零 runtime diff**。
> - **不是 nav plan**：nav 能力（C1-C12）歸 Lane 6 / Cloud A，本 plan 任何措辭不觸碰 nav label（F1-F10）。

---

## §0 TL;DR — Sub-capability 總表

| # | Sub-capability | 分級 | 優先 | task_type | before_monday | enter_6/18_runtime |
|---|---|:---:|:---:|---|:---:|:---:|
| V1 | ASR anti-hallucination（Whisper 靜音/噪音段假文字防線量化 + 黑名單擴充） | proven | P0 | pure_software | yes | no |
| V2 | VAD threshold tuning（2-10s 瓶頸；需數據支撐才動） | needs_hitl | P1 | jetson_needed | maybe | no |
| V3 | Common demo command rule-based fast path（坐下/過來/翻跟斗/OK 繞 LLM） | proven | P0 | pure_software | yes | maybe |
| V4 | 小模型 intent classifier 可行性（vs 純 rule engine vs cloud LLM） | research_only | P2 | pure_software | no | no |
| V5 | Cloud LLM vs local rule engine routing（何時走哪條 → 決策表 + 單測） | proven | P1 | pure_software | yes | maybe |
| V6 | Local TTS / pre-render phrase pack（常用句預渲染 cache hit≈0s） | needs_hitl | P0 | mixed | yes | maybe |
| V7 | TTS ack / request_id（播放確認回路，目前只有 `/state/tts_playing` bool） | needs_hitl | P1 | mixed | maybe | no |
| V8 | Interrupt / cancel speaking（打斷正在播放的 Megaphone session） | research_only | P2 | jetson_needed | no | no |

> **一句話結論**：6/18 前唯一值得排的純軟體高價值項是 **V1（anti-hallucination 把黑名單命中率/誤殺率變數字）**、**V3（demo command fast-path table 鎖死哪些指令繞 LLM、含單測）**、**V5（routing 決策表 + 純函式單測）**、**V6（pre-render phrase pack 離線產 WAV，cache hit 即 0s）**。`enter_6/18_runtime` 標 `maybe` 的（V3/V5/V6）= 機制其實已部分在 code（fast path、cache、dual-route），本 plan 的進階層是「**離線資產 + 純函式重構 + 單測**」，要不要把離線資產接進 demo 啟動腳本由 Roy 在回穩日（6/17）拍。**V2 動 VAD 一律 maybe 且必須有 Jetson 數據**；**沒有任何一項要求換 ASR/LLM/TTS 模型**（與 master B-4 / claim matrix `Model Candidates` 一致）。

---

## §1 範圍與邊界

### 1.1 與 Cloud A（保守版 demo flow）的分界

| 項目 | 歸屬 | 本 plan 立場 |
|---|---|---|
| offline fallback 主線（無網/雲端 down 退路、五級 fallback 編排） | **Cloud A** | **不重複**；本 plan 只在 V5 引用 fallback chain 作 routing 決策依據，不重新設計 fallback |
| phase conductor / canned phrase per-幕 timeout | **Cloud A**（[phase conductor plan](2026-06-13-demo-phase-conductor-plan.md)） | 不重複；V6 的 pre-render phrase pack 可**供** Cloud A 的 `say_canned` 取用（提供離線 WAV 資產），但編排權在 Cloud A |
| demo 可靠度 / smoke / 彩排 / Plan B 固定台詞 | **Cloud A** + 陳若恩（[speech README Plan B](../../pawai-brain/speech/README.md)） | 不重複；V1/V3/V5 的單測可併入 ros2-test-suite，不搶主線 |
| ASR 防幻覺進階量化 / fast-path 延遲優化 / VAD 數據 / TTS ack / interrupt | **Cloud B（本 plan）** | 全部 |

**硬規則**：本 plan 任何 task 若觸及 offline fallback 編排或 demo 段落控制，標註「歸 Cloud A，本計畫不重複」，只保留**延遲/防幻覺數據與離線資產**產出面。

### 1.2 與既有 Lane plan 的分界

| 既有 lane | 內容 | 本 plan 的進階層差異 |
|---|---|---|
| [Lane 1 Brain ISM staged enable](2026-06-13-lane1-brain-ism-staged-enable-plan.md) | Brain 事件優先序 / ISM shadow / policy 接管 | 本 plan 不碰 Brain 裁決；V3 fast-path 是 **stt_intent_node / intent_classifier 層**（intent 分類），不是 Brain policy。引用不複製 |
| [Lane 3 CLI v2](2026-06-13-lane3-cli-v2-completion-plan.md) | `pawai smoke brain` / evidence pull | V1/V3/V5 單測**可被** `pawai smoke brain` 後置呼叫，但本 plan 不擴 CLI |
| [Lane 5 robot-control security](2026-06-13-lane5-robot-control-security-hardening-plan.md) | gateway auth / robot control | V7 TTS ack 不碰 gateway auth；只在 ROS topic 層加 request_id 回路（additive topic） |

**鐵律繼承**：① demo 錄影絕不餵 LLM（量測輸入非理解輸入，沿用 Lane 4 §1）；② 任何 spike 不進 Jetson runtime，除非 Roy 在回穩日明確點頭；③ 數據出來前不換任何 runtime 模型/參數/閾值（master B-4）。

### 1.3 No-overclaim 對齊

本 plan 涉及的能力在 [claim matrix](../../mission/2026-06-18-capability-claim-matrix.md) 的 trusted 狀態：

- **`voice.command`** = 🟢 **pass（窄版）**，CLAIM_WITH_CAVEAT。Evidence = 6/04 HITL（n=24, success_rate=0.875, false-trigger=0.0；**latency 全 null、CSV 由終端重建、單一講者 Roy**）。`Model Candidates=BASELINE_NOW`（規則分類器 + SenseVoice/Whisper，**現役不換**）。
- **`voice.stop`** = 🔴 **fail**，DO_NOT_CLAIM。Evidence = 6/04 HITL（n=6, 0.667, FN=2）。`Model Candidates=SPIKE_AFTER_FAIL`（**不是換模型**；intent_classifier 加 safety tie-break + 調 VAD）。
- **禁說清單（直接繼承 claim matrix `Non-Claims`）**：語音延遲 / 反應時間 / **mic_stop 急停（未接線、未量測）** / 自由對話辨識率 / LLM 直接操控機器狗 / 把 0.875 講成「ASR 辨識率」 / 把 voice.stop 講成 safety stop。
- **latency 鐵則**：6/04 voice e2e 是 **VAD-era**、CSV 無 latency 欄、`mic_stop` 觀測者未接線。本 plan 散文中所有 latency（VAD 2-10s / P50 1.16s / fast-path 0.002s / TTS ~1.5s/~6.5s 等）皆為**開發期 proxy 觀測**，**非 trusted 量測**——任何 V 項的「延遲改善」結論只能在離線/HITL 重新量到後才成立，且**不得對外宣稱語音延遲數字**（除非 Roy 授權一次完整含 latency 欄的 HITL 重跑）。

**單次成功 ≠ 可靠**（需 n=3，沿用 [ladder §1](../../navigation/2026-06-13-nav-capability-ladder.md) 鐵則）。nav 不在本 plan 範圍——不觸碰 C1-C12 / F1-F10。

---

## §2 逐能力 13 點分析

---

### V1 — ASR anti-hallucination（Whisper 靜音/噪音段假文字防線）

**分級：`proven`（防線機制已在 code 且 6/04 false-trigger=0.0）｜優先：P0｜task_type：pure_software**

**1. Desired demo benefit**
Whisper 在靜音/噪音段會幻覺出假文字（如「字幕by索兰娅」），若未擋會：(a) 產生假 intent → Go2 做出無人下令的動作（已被 `ENABLE_ACTIONS` 與 Brain safety 護住，但仍污染對話），(b) demo 現場 Go2 風扇/環境噪音觸發假對話、破壞「誠實感知」敘事。進階防線把「黑名單有效」從印象變成**可量化命中率 + 誤殺率**，並擴充 pattern。

**2. Current baseline**
- 主線 ASR = SenseVoice cloud (FunASR, ~350-400ms, 92%) → SenseVoice local (sherpa-onnx int8, ~400ms, 92%) → Whisper small (faster-whisper, ~3.0s, 52%, **幻覺率 8%**)。來源 [speech README §ASR 三級 Fallback](../../pawai-brain/speech/README.md)。
- 既有防線（[speech README Noisy Profile v1](../../pawai-brain/speech/README.md) + [speech.md Stage 5](../../pawai-brain/architecture/0511/speech/speech.md)）：
  - Whisper `vad_filter=True`（silero）+ `no_speech_threshold=0.6` + `log_prob_threshold=-1.0`。
  - 幻覺黑名單 **6→22 pattern** + 短文字（<2 字）過濾，命中發 `intent=hallucination`。
  - OpenCC s2twp 後處理。
- 6/04 trusted：`voice.command` **false-trigger=0.0**（n=24）——表示**現行防線在 Roy 單講者固定指令場景已 proven 不誤觸發**。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. 黑名單擴充（離線 corpus 驅動） | 蒐集靜音/噪音 clip → 跑 Whisper → 收集幻覺 pattern → 擴 22→N | **推薦**：純軟體、零 runtime 風險、可離線 replay |
| B. 提高 `no_speech_threshold` 0.6→0.7 | 更激進拒絕 | maybe；需數據證明不增漏觸（false negative） |
| C. 換掉 Whisper（只留 SenseVoice 兩層） | Whisper 是第三層 fallback、幻覺源 | **不做**（master B-4 不換模型；Whisper 是離線最後保底，刪了無網時無 ASR） |
| D. 能量門 + 長度啟發式（短於 X 字且低 RMS → 丟） | 與黑名單互補 | 可作 V1 子項，純函式可單測 |

**4. Required data**
- 靜音 clip ×N（demo 場地環境噪音、Go2 風扇噪音、空房間）— **需 Roy 在 demo 場地錄 raw 音檔**（不餵 LLM，只跑 ASR）。
- 既有 22 pattern 清單（從 `stt_intent_node.py` 抽出）。
- 6/04 HITL 的 false-trigger=0.0 作 baseline 對照。

**5. Pure software tasks**
- T-V1a `[pure software]`：抽 `stt_intent_node.py` 的幻覺黑名單 + 短文字過濾邏輯成 **ROS-free 純 module**（`hallucination_filter.py` 候選，比照 `tts_split.py` / `text_normalization.py` ROS-free pattern），讓 pre-commit hook 不需 source ROS 即可單測。**零行為變化**（純抽取）。
- T-V1b `[pure software]`：寫 offline replay harness — 吃 WAV 目錄 → 跑 ASR provider（可用 local SenseVoice / Whisper）→ 對每筆輸出跑 filter → 產 confusion table（命中數 / 誤殺數 / 漏擋數）。
- T-V1c `[pure software]`：以蒐集到的幻覺 corpus 擴黑名單，並量「擴充後對 24 筆固定指令 corpus 的誤殺率」（必須維持 0）。

**6. Jetson tasks**
- T-V1d `[Jetson needed]`：在 Jetson 上對 demo 場地 raw 噪音 clip 跑 Whisper（cuda+float16，**禁 int8 silent fail**，[CLAUDE.md 硬規則](../../pawai-brain/speech/CLAUDE.md)）→ 收集真實幻覺 pattern（場地特定）。**只讀、不改 runtime。**

**7. Go2 HITL tasks**
- 無 Go2 motion。（噪音可選 Go2 開機風扇實況，但不需 motion，歸 V1d 的環境錄音。）

**8. Metrics**
- 黑名單**命中率** = 擋下的幻覺 / 全部幻覺（離線 corpus）。
- **誤殺率** = 被黑名單擋掉的「真實指令」/ 全部真實指令（**必須 = 0** 於 24 筆固定指令 corpus）。
- 幻覺**漏擋率** = 沒擋下進到 intent 的幻覺 / 全部幻覺。

**9. Pass/fail threshold**
- PASS：擴充後 24 筆固定指令誤殺率 = 0（不退步），且幻覺漏擋率較 baseline 下降（離線 corpus）。
- FAIL：任一固定指令被誤殺，或漏擋率不降反升 → 回滾擴充。

**10. Risk**
- 過度擴黑名單 → 誤殺真實短指令（如「停」「坐」）。緩解：誤殺率硬門檻 0 + 對 24 筆 corpus 回歸。
- 場地噪音與開發環境不同 → 離線 corpus 代表性不足。緩解：標 needs HITL 補場地 clip（V1d）。

**11. Rollback**
- 黑名單擴充是 data/list 改動 → git revert 該 commit 即回 22 pattern。純 module 抽取若出錯 → revert，`stt_intent_node.py` 內聯邏輯仍在（抽取保留 shim）。

**12. Should we do before Monday? — yes**
純軟體、零 runtime 風險、可離線替代（不需 Jetson 即可做 T-V1a/b/c）。V1d 需 Jetson + 場地音檔可後補。把「防線有效」變數字直接支援 6/18「誠實揭露」敘事。

**13. Should it enter 6/18 demo runtime? — no**
黑名單擴充屬 data 改動，理論上低風險，**但 master B-4 預設不動 runtime**；且現行防線 6/04 已 false-trigger=0.0 proven，demo 現役足夠。擴充版作離線資產 + 候選，Roy 回穩日決定要不要併。**不對外宣稱「反幻覺已驗證」**（[speech README](../../pawai-brain/speech/README.md) 明示 voice 模組不宣稱反幻覺已驗證）。

---

### V2 — VAD threshold tuning（2-10s 瓶頸）

**分級：`needs_hitl`（任何 VAD 改動必須 Jetson 實機數據）｜優先：P1｜task_type：jetson_needed**

**1. Desired demo benefit**
VAD（speech_end 偵測）是 e2e 最大延遲源，自 3/18 起 known issue：**2-10s 不穩**（[speech.md §9](../../pawai-brain/architecture/0511/speech/speech.md)、[3/24 report §五](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）。縮短可讓「使用者說完 → PawAI 回應」更即時，提升 demo 對話體感。

**2. Current baseline**
- Energy VAD（in-process，非 Silero）。yaml 預設（[speech.md §11](../../pawai-brain/architecture/0511/speech/speech.md)）：`start_threshold=0.015`、`stop_threshold=0.01`、`silence_duration_ms=800`、`min_speech_ms=300`、`adaptive=false`。
- Noisy Profile v1（[speech README](../../pawai-brain/speech/README.md)，Go2 噪音環境）：`start_threshold=0.02`、`stop_threshold=0.015`、`silence_duration_ms=1000`、`min_speech_ms=500`、`mic_gain=8.0`。
- 開發期 proxy：VAD 錄音 P50 ~2.1s（[3/24 report §五](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)），但 2-10s 抖動。**非 trusted 量測**。
- ⚠️ 6/04 voice e2e 是 **VAD-era**，CSV 無 latency 欄——所以「VAD 是瓶頸」是開發觀測，沒有 trusted latency baseline 可對照。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. 調 `silence_duration_ms`（800/1000 → 600） | 更快判定 speech_end | maybe；**側風險**：太短會切斷長句（「請回復你現在的狀態」已知偶被截，[3/24 report §二](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)） |
| B. 換 Silero VAD（取代 energy VAD） | 業界標準、語音段更準 | research_only；架構改動大、[speech.md §9](../../pawai-brain/architecture/0511/speech/speech.md) 列為「徹底解決」選項，**6/18 前不做** |
| C. 外部 frontend（Studio push-to-talk / 手動斷句） | 繞過 VAD 完全 | **歸 Cloud A demo flow**（Studio 收音是 demo 主線，[speech README 核心流程](../../pawai-brain/speech/README.md)）；本 plan 不重複 |
| D. `adaptive` noise floor 開啟（alpha=0.02，預設 off） | 動態噪音適應 | maybe；需數據證明不增誤觸 |

**4. Required data**
- Jetson 實機、demo 麥克風（UACDemoV1.0 mono 48kHz）、demo 場地噪音下，量「speech_end 判定延遲」分布（n≥20，多句長）。
- 短指令（停/坐）vs 長句（狀態查詢）分開量——避免短句調快卻切斷長句。

**5. Pure software tasks**
- T-V2a `[pure software]`：抽 energy VAD 判定為純函式（吃 RMS 序列 → 回 speech_start/end 事件），寫單測覆蓋「短靜音不誤判 end / 長句不被切」邊界。**不改閾值，只重構可測。**

**6. Jetson tasks**
- T-V2b `[Jetson needed]`：在 Jetson 上以**現行閾值**量 VAD speech_end 延遲分布（baseline），再以候選閾值（A/D）量同一組句子，比較延遲 vs 截斷率。**全程不進 demo 啟動腳本，獨立 e2e session（[CLAUDE.md 測試規範](../../CLAUDE.md)：同時只一套 speech session）。**

**7. Go2 HITL tasks**
- 無 Go2 motion（純語音 e2e，`start_llm_e2e_tmux.sh` 不啟 Go2）。

**8. Metrics**
- speech_end 判定延遲 P50/P95（ms）。
- 長句**截斷率**（被 VAD 切成多段 / 全部長句）。
- 誤觸發率（噪音被當 speech_start）。

**9. Pass/fail threshold**
- PASS（**才允許提議**進 runtime）：候選閾值 P50 延遲下降且**截斷率不上升、誤觸率不上升**，n≥20。
- FAIL / 維持現狀：任一退步 → 不動 VAD（維持現行 yaml / Noisy Profile）。

**10. Risk**
- VAD 是「magic number 工程妥協」區，調錯 → 長句截斷（已知）或噪音誤觸（demo 翻車）。
- 開發環境調好、場地不同 → 失效。**故強制 needs_hitl + 場地數據。**

**11. Rollback**
- 閾值在 yaml / launch arg，env override 即回滾（`energy_vad.*` param）。純函式重構（V2a）若退步 → revert，內聯邏輯保留。

**12. Should we do before Monday? — maybe**
T-V2a 純函式重構可先做（無風險）。但**真正的閾值調整必須 Jetson + 場地數據**，且與 Cloud A 的 Studio 收音主線可能相互覆蓋（Studio push-to-talk 直接繞 VAD）——若 Cloud A 走 Studio 收音，VAD 調整邊際效益降低。建議：**先確認 demo 收音路徑（Studio vs 機上 mic）再決定是否值得調 VAD**。

**13. Should it enter 6/18 demo runtime? — maybe（強條件）**
只有在 T-V2b 量到「延遲降 + 零截斷退步 + 零誤觸退步」+ Roy 回穩日點頭 + 有 env rollback 時才 maybe。預設**不換**（master B-4）。**且不論調不調，對外都不宣稱語音延遲數字**（claim matrix Non-Claims）。

---

### V3 — Common demo command rule-based fast path（坐下/過來/翻跟斗/OK 繞 LLM）

**分級：`proven`（fast path 機制已在 code 且 6/04 voice.command 窄版 pass）｜優先：P0｜task_type：pure_software**

**1. Desired demo benefit**
固定 demo 指令（坐下 / 過來 / 停 / OK / 狀態 / 翻跟斗等）**繞過雲端 LLM**，直接走規則 → RuleBrain / 動作，延遲從 ~4.5s（cloud LLM + edge-tts）降到動作型 ~0s、模板回覆 cache hit ~0s（[3/24 report §五延遲基線](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)：stop/sit/stand=0.002s、greet cache hit=2.34s）。對 demo 是「指令秒回、不卡網路」的關鍵可靠性。

**2. Current baseline**
- **Intent fast path 已存在**（[speech README](../../pawai-brain/speech/README.md)：「stop/greet 等高頻 intent 跳過 LLM，直接 RuleBrain（~0ms）」）。
- Intent classifier = **純規則、無 ML**（[speech.md Stage 6](../../pawai-brain/architecture/0511/speech/speech.md)），7 intents：greet / come_here / stop / sit / stand / take_photo / status。`confidence = score / len(matched)`。
- 動作型 intent（stop/sit/stand）**不播 TTS**（`ACTION_ONLY_SKILLS`/`ACTION_ONLY_INTENTS`，[3/24 report §四](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）。
- 6/04 trusted：`voice.command` success_rate=**0.875**（n=24，純 Python 關鍵字規則分類器），窄版 pass。
- ⚠️ `come_here` intent **不接 nav goal**（[claim wording F6](../../navigation/2026-06-13-nav-618-claim-wording.md)：「聽懂過來就走到 Roy 身邊」是 forbidden claim；感知與 nav goal 零連接）——fast-path 對 `come_here` **只能做語音回應，不可觸發 motion**。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. 把 demo 指令集做成 canonical fast-path table（純資料） | 列每個 demo 指令 → intent → 走 fast path / 走 LLM / 走 canned | **推薦**：把現有散落的 fast-path 邏輯文件化 + 單測，零行為變化 |
| B. 擴指令集（加「翻跟斗」等 demo 動作指令） | demo 需要的新指令 | maybe；**翻跟斗等 motion 指令需 Go2 HITL 驗證安全**，且 motion 觸發要過 Brain safety（不在本 plan，標歸 Lane 1 / Cloud A） |
| C. 提高 fast-path confidence 門檻避免誤分類 | 0.8 門檻 | 可作單測項，不改 runtime 門檻 |

**4. Required data**
- demo 五幕用到的指令清單（與 Cloud A phase 表對齊：s2 greet / s3 object / s4 gesture 對應語音指令）。**需與 Cloud A 確認哪些指令進 demo。**
- 現行 intent_rules 字典（從 `stt_intent_node.py` / `intent_classifier.py` 抽）。
- 6/04 的 24 筆固定指令 corpus + 0.875 success_rate。

**5. Pure software tasks**
- T-V3a `[pure software]`：產 **demo command fast-path table 文件**（每指令：keyword → intent → 路徑{fast_path | llm | canned} → 是否播 TTS → 是否觸發 motion）。**純文件 + 對 `intent_classifier.py` 現況的對照**，不改 code。
- T-V3b `[pure software]`：對 `intent_classifier.py` 純函式寫/補單測——對 24 筆固定指令 corpus 驗 intent 正確率（回歸 baseline 0.875）+ fast-path 路由正確（哪些繞 LLM）。**純測試，零行為變化。**
- T-V3c `[pure software]`：若 B（擴指令）獲准，**只加 keyword 規則**（不加 motion 觸發），motion 部分標「歸 Lane 1 / Cloud A，本計畫不接線」。

**6. Jetson tasks**
- T-V3d `[Jetson needed]`（選配）：在 Jetson e2e 上量 fast-path 指令的「intent → reply」延遲，確認繞 LLM 真的快（**只讀觀測，不改 runtime**）。

**7. Go2 HITL tasks**
- T-V3e `[Go2 motion needed]`（**僅在 B 擴 motion 指令且 Roy 授權時**）：翻跟斗等新 motion 指令的安全驗證 → **歸 Lane 1 / Cloud A motion 安全鏈，本 plan 不主導**，只標依賴。`come_here` 永不接 motion（F6）。

**8. Metrics**
- fast-path 指令 intent 正確率（對 24 筆 corpus，目標 ≥ 0.875 不退步）。
- fast-path 路由正確率（該繞 LLM 的有繞）。
- 開發期 proxy：fast-path 指令延遲（動作型 ~0s、模板 cache hit ~0s）— **proxy，不對外宣稱**。

**9. Pass/fail threshold**
- PASS：24 筆 corpus intent 正確率 ≥ 0.875（不退步）+ fast-path table 與 code 一致 + 單測綠。
- FAIL：正確率退步或 table 與 code 不符 → 修 table（不改 runtime 行為）。

**10. Risk**
- 文件化過程若「順手改」intent 規則 → 動到 runtime 行為。**緩解：T-V3a/b 嚴格 read-only / test-only。**
- B 擴 motion 指令誤觸 → Go2 危險動作。緩解：motion 一律過 Brain safety，本 plan 不接線。

**11. Rollback**
- T-V3a/b 不改 runtime → 無需 rollback。T-V3c（加 keyword）若誤分類 → git revert 規則 commit。

**12. Should we do before Monday? — yes**
純軟體、把現有 fast-path 從「印象」變成「有 table + 單測」，直接強化 6/18 「固定指令秒回」可靠性敘事，零風險。

**13. Should it enter 6/18 demo runtime? — maybe**
fast-path 機制**本來就在 runtime**（現役 demo 已用）；本 plan 的 table + 單測是文件/測試層，不改 runtime。若 B 擴指令獲准且 motion 安全鏈（Lane 1/Cloud A）就緒，新 keyword 規則 maybe 進——由 Roy 拍。**對外只講 `voice.command` 窄版 pass（固定指令意圖分類），不講延遲數字、不講 LLM 操控機器狗**（claim matrix Non-Claims）。

---

### V4 — 小模型 intent classifier 可行性（vs 純 rule engine vs cloud LLM）

**分級：`research_only`（評估，無實作上機）｜優先：P2｜task_type：pure_software**

**1. Desired demo benefit**
理論上小模型 intent classifier（如輕量 BERT / fastText / 小 LLM intent head）可比純 keyword 規則更耐同義詞/語序變化（現行 `come_here`/`take_photo` 對非固定話術泛化弱，[3/24 report §三 intent 映射偏差](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）。

**2. Current baseline**
- Intent = **純規則 keyword match**（[speech.md Stage 6](../../pawai-brain/architecture/0511/speech/speech.md)），6/04 固定指令 0.875。
- 純規則優點：~0ms、可解釋、可單測、無模型依賴。缺點：泛化弱（非固定話術掉分）。
- 本地小 LLM 智商不足已驗：Qwen2.5-0.5B JSON parse 25%、語言漂移（[3/24 report §三](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）；Qwen2.5-0.8B「胡言亂語」（[speech README 已知問題](../../pawai-brain/speech/README.md)）。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. 維持純 rule engine | 現役 | **預設**：6/04 窄版 pass、零延遲、可單測 |
| B. 小模型 intent classifier（fastText / 輕量 encoder） | 離線評估泛化 | research_only：需標註 corpus + 評估，**6/18 前不上機**（master B-4） |
| C. cloud LLM 直接出 intent（現行 chat 路徑已做） | LLM 出 `intent` 欄 | 已存在於非 fast-path；延遲 ~1.16s，**不取代 fast-path** |

**4. Required data**
- intent 標註 corpus（固定 + 自由話術），需擴大於 6/04 的 24 筆（單講者）→ 多講者 + 同義變體。**需 Roy 提供或授權蒐集。**

**5. Pure software tasks**
- T-V4a `[pure software]`：寫一頁**誠實可行性 memo**——純 rule vs 小模型 vs cloud LLM 三方在「延遲 / 可解釋性 / 泛化 / Jetson 資源 / 維護成本」的取捨表，結論預期 = 「6/18 維持純 rule（窄版 pass 夠用），小模型列 post-6/18 候選」。
- T-V4b `[pure software]`（選配）：若有 corpus，離線跑 fastText baseline，量泛化 gain，**不上機、不接 runtime**。

**6. Jetson tasks** — 無（research_only，不上機）。

**7. Go2 HITL tasks** — 無。

**8. Metrics**
- 三方取捨表完成度（質性）。
- （選配）小模型 vs 純規則在自由話術 corpus 的 intent F1 差。

**9. Pass/fail threshold**
- 本項是 research，「PASS」= memo 落檔可審；不設能力門檻。小模型若離線 F1 不顯著贏純規則 → 維持純規則。

**10. Risk**
- 引入 ML intent → 失去可解釋性 + 增 Jetson 負載 + 失去 0ms。對 demo 無淨收益。

**11. Rollback** — 純評估，無 runtime 改動，無需 rollback。

**12. Should we do before Monday? — no**
無 demo 直接收益；需標註 corpus（未就緒）。純 memo 可後補。優先讓位給 V1/V3/V5/V6。

**13. Should it enter 6/18 demo runtime? — no**
明確不上機（master B-4 + 本地小模型智商已驗不足）。維持純 rule engine。

---

### V5 — Cloud LLM vs local rule engine routing（何時走哪條）

**分級：`proven`（routing 機制已在 code，五級 fallback 已驗）｜優先：P1｜task_type：pure_software**

**1. Desired demo benefit**
明確化「哪些輸入走 cloud LLM（慢但有個性）、哪些走 local rule engine / RuleBrain（快但固定）」的決策，避免：(a) demo 現場簡單指令誤走雲端被網路拖慢，(b) 雲端 down 時 fallback 路徑不明確。把 routing 做成**決策表 + 純函式單測**，提升可預測性。

**2. Current baseline**
- routing 已存在但散落（[speech README 架構碎片化警示 5/5](../../pawai-brain/speech/README.md)：chat + tool calling 路徑跨 `llm_bridge_node`(~624 行) + `brain_node` + Studio gateway）。
- 現行規則：intent ∈ {greet/stop/sit/stand 等高頻} → fast path 繞 LLM；intent ∈ {chat/status/unknown} → cloud LLM（[3/24 report §七](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）。
- LLM fallback chain（[speech README](../../pawai-brain/speech/README.md)）：OpenRouter `gpt-5.4-mini` → `gemini-3-flash` → Cloud Qwen2.5-7B → Ollama 1.5B → RuleBrain（五級）。**LLM timeout > 2s → RuleBrain**（[CLAUDE.md 硬規則](../../pawai-brain/speech/CLAUDE.md)）。
- ⚠️ 對話記憶只在 intent ∈ {greet/chat/status} 寫入；stop/sit/stand 不污染 context（[speech README 5/5](../../pawai-brain/speech/README.md)）——routing 決策表要保留此區分。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. routing 決策表文件化 + 純函式抽取 + 單測 | 把「哪條輸入走哪條」鎖死可測 | **推薦**：proven 機制、零行為變化、降 hidden bug 風險（呼應 5/5 碎片化警示） |
| B. LangGraph 重構（把 chat+tool routing 搬集中） | [speech README 下一步 backlog](../../pawai-brain/speech/README.md) 提案 | research_only / post-6/18（架構大改，明示 demo 後再做） |
| C. 動態 routing（依網路延遲自動切 local） | 偵測雲端慢自動降 local | maybe；需延遲量測（與 V2 共用 HITL），6/18 前 risk 高 |

**4. Required data**
- 現行 routing 邏輯（從 `llm_bridge_node.py` + `intent_classifier.py` 抽決策點）。
- 五級 fallback 觸發條件（timeout 4.0s / overall budget 5.0s，[speech.md §4](../../pawai-brain/architecture/0511/speech/speech.md)）。

**5. Pure software tasks**
- T-V5a `[pure software]`：產 **routing 決策表**——輸入維度（intent 類 / confidence / 是否含 safety keyword / 網路狀態）→ 路徑（fast_path | cloud_llm | rulebrain | canned）。對照 code 現況，標出散落點。
- T-V5b `[pure software]`：把 routing 判定抽純函式（吃 intent+confidence+flags → 回路徑 enum），寫單測覆蓋邊界（高頻 intent 繞 LLM / safety keyword 永 fast lane / timeout → RuleBrain / 記憶只在 chat 寫入）。**零行為變化。**

**6. Jetson tasks**
- T-V5c `[Jetson needed]`（選配）：在 Jetson e2e 驗證決策表與實際 routing 一致（斷 tunnel 測 fallback 路徑，[speech README RuleBrain fallback](../../pawai-brain/speech/README.md)：`force_fallback:=true`）。**只讀驗證。**

**7. Go2 HITL tasks** — 無 Go2 motion。

**8. Metrics**
- 決策表與 code 一致性（逐路徑對照，無未文件化分支）。
- 純函式單測覆蓋率（所有路徑 + fallback 觸發）。

**9. Pass/fail threshold**
- PASS：決策表覆蓋所有現行 routing 分支 + 單測綠 + 與 code 行為一致（無回歸）。
- FAIL：發現未文件化/未測分支 → 補測（不改行為）。

**10. Risk**
- 抽純函式時誤改 routing 行為 → demo 路徑變化。**緩解：嚴格行為等價 + 對照測試。**

**11. Rollback**
- 純函式抽取保留原 call site shim → revert commit 即回。決策表是文件，無 runtime 影響。

**12. Should we do before Monday? — yes**
純軟體、直接降低 [5/5 架構碎片化](../../pawai-brain/speech/README.md) 風險、強化 demo routing 可預測性，零風險。

**13. Should it enter 6/18 demo runtime? — maybe**
純函式抽取若行為等價且單測綠，理論可併（降 hidden bug），但 master B-4 預設不動 runtime；建議作為「可審的等價重構」，Roy 回穩日決定要不要併入 demo build（與 Lane 1/3 重構節奏對齊）。決策表本身是文件，必進（供操作員/簡報用）。

---

### V6 — Local TTS / pre-render phrase pack（常用句預渲染）

**分級：`needs_hitl`（離線產資產為 pure software，但接進播放鏈需 Jetson + Go2 驗）｜優先：P0｜task_type：mixed**

**1. Desired demo benefit**
demo 常用句（每幕 canned phrase、greet、object_remark、safety reply）**預先渲染成 WAV**，cache hit ≈ 0s（[3/24 report §四 TTS cache 預熱](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)：「啟動時 background thread 預合成 5 句常用模板，首次即 cache hit」）。對 demo 是「固定台詞秒回、不卡 TTS 雲端鏈（quality lane ~6.5s）」的關鍵保險，且雲端 TTS down 也能播。

**2. Current baseline**
- TTS cache 已存在（[speech-tts-lanes-megaphone.md §6](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)）：cache key = `text + voice + provider`；cache hit 後依 provider `output_format` 解碼。
- 啟動預熱已存在（5 句常用模板，[3/24 report §四](../../pawai-brain/speech/research/2026-03-24-speech-pipeline-report.md)）。
- 本地 TTS = Piper `zh_CN-huayan-medium.onnx`（離線、22050Hz、合成 ~2.0s）；雲端 = edge_tts（~1.5s）/ Gemini Despina quality lane（~6.5s 首音）。
- Megaphone 16kHz 硬體限制（[CLAUDE.md](../../pawai-brain/speech/CLAUDE.md)）：TTS 高頻會糊，WAV 須 16kHz/16bit/mono + 16dB gain。
- ⚠️ **tts_node mid-session 重啟會 Megaphone silent fail**（[speech.md §13 #8](../../pawai-brain/architecture/0511/speech/speech.md)）——pre-render 資產**必須在啟動時載入，不可 mid-session 熱載重啟 tts_node**。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. 離線批次 render phrase pack（Piper / edge_tts 預產 WAV 目錄） | 啟動載入 cache | **推薦**：純軟體產資產 + 啟動載入；雲端 down 也能播 |
| B. 擴大啟動預熱清單（5 句 → demo 全 canned set） | 沿用現有預熱機制 | 推薦：與 A 互補，最小改動（資料驅動） |
| C. 把 phrase pack 接進 Cloud A 的 `say_canned` | offline fallback 主線 | **歸 Cloud A，本計畫不重複**；本 plan 只**提供 WAV 資產 + 載入機制**，編排權在 Cloud A |

**4. Required data**
- demo canned phrase 清單（**需與 Cloud A 對齊**，phrase 文字 = [phase conductor plan §6](2026-06-13-demo-phase-conductor-plan.md) 每幕 expected TTS offline canned）。
- 音色決策（Despina vs Piper vs edge）——pre-render 用哪個 voice 影響 cache key 命中。

**5. Pure software tasks**
- T-V6a `[pure software]`：寫離線 render 腳本——吃 phrase 清單 + provider/voice → 批次產 16kHz/16bit/mono WAV（對齊 Megaphone 規格 + 16dB gain）→ 存資產目錄。**不改 tts_node**。
- T-V6b `[pure software]`：驗證 cache key 一致性——確認 pre-render 的 `text+voice+provider` key 與 runtime 查 cache 的 key 算法一致（否則 cache miss）。對 `tts_node` cache key 函式寫單測。

**6. Jetson tasks**
- T-V6c `[Jetson needed]`：在 Jetson 上載入 phrase pack（**啟動時注入 cache**，不 mid-session 重啟 tts_node）→ 量 cache hit 是否真 ≈ 0s（開發期 proxy）。確認載入不破壞現有 cache 行為。

**7. Go2 HITL tasks**
- T-V6d `[Go2 motion needed → 實為 Go2 driver needed，無 motion]`：經 Go2 Megaphone 實播 pre-render WAV，確認 16kHz 清晰度與音量（[CLAUDE.md 16kHz 硬限制](../../pawai-brain/speech/CLAUDE.md)）+ 無 Megaphone silent fail。**無 Go2 motion，只用 driver + Megaphone 播放。**（標記為「Go2 driver needed」子類，非 motion。）

**8. Metrics**
- pre-render phrase cache hit 率（demo canned set 全命中）。
- 開發期 proxy：canned phrase 首播延遲（cache hit 目標 ≈ 0s）— **proxy，不對外宣稱數字**。
- Megaphone 實播無 silent fail（n=3 連續）。

**9. Pass/fail threshold**
- PASS：demo canned set 100% cache hit + Megaphone 實播清晰可辨 + n=3 無 silent fail。
- FAIL：cache miss（key 不一致）→ 修 key 算法對齊；silent fail → 查 Megaphone 序列（4001/4003/4002 + EXIT 永送）。

**10. Risk**
- cache key 不一致 → pre-render 白做（miss）。緩解：T-V6b 單測對齊。
- **mid-session 載入重啟 tts_node → Megaphone silent fail**（已知坑）。緩解：只啟動時載入，**鐵律不 mid-session 重啟 tts_node**。
- 音色不一致（pre-render Piper vs runtime Despina）→ demo 音色跳。緩解：pre-render 用與 demo 主線一致 voice。

**11. Rollback**
- phrase pack 是資產目錄 + 載入旗標（env-gated）→ 關旗標即回現行預熱（5 句）。離線腳本不碰 runtime。

**12. Should we do before Monday? — yes**
離線產資產（T-V6a/b）純軟體零風險，且直接支援 demo「固定台詞秒回 + 雲端 down 也能播」可靠性。Jetson 載入驗證（T-V6c/d）可後補但建議排在彩排前。

**13. Should it enter 6/18 demo runtime? — maybe**
pre-render cache 載入若 cache key 對齊且 Megaphone 實播過（T-V6c/d PASS）+ Roy 點頭，**值得進**（提升 demo 可靠性、純 additive 載入）。但屬 Cloud A demo flow 範疇的「要不要當 canned 主路徑」由 Cloud A 決定；本 plan 只交付資產 + 載入機制。預設保守：作離線資產 + env-gated 載入。

---

### V7 — TTS ack / request_id（播放確認回路）

**分級：`needs_hitl`（additive topic 設計純軟體，但驗證需 Jetson + Go2 Megaphone）｜優先：P1｜task_type：mixed**

**1. Desired demo benefit**
目前播放狀態只有 `/state/tts_playing`（bool，[runtime-flow topic 表](../../pawai-brain/architecture/0511/speech/speech-runtime-flow.md)）——**無法知道「某一句具體 reply 是否播完 / 是否成功」**。加 request_id + ack 回路讓 Brain/Executive 能：(a) 確認某句 canned/safety reply 真的播出（不是 Megaphone silent fail），(b) 多句排隊時知道進度。對 demo 是「確認 safety 台詞真的有播」的可觀測性。

**2. Current baseline**
- `/tts` payload 雙模：純文字 OR JSON envelope `{"text", "input_origin", "source"}`（[speech-tts-lanes-megaphone.md §1](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)）。**envelope 無 request_id 欄。**
- `/state/tts_playing`（Bool, TRANSIENT_LOCAL latched）：合成前 True、播完+EXIT+cooldown 後 False（[speech-tts-lanes-megaphone.md §8](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)）。同時被 STT echo gate / Executive gate / Brain world state 消費。
- Megaphone EXIT 4002 在 finally 保證送出，但**沒有「播放成功」回報**——silent fail 只能靠「沒聲音」事後察覺（[speech-tts-lanes-megaphone.md §9](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)）。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. `/tts` envelope 加 `request_id` + 新 `/event/tts_ack` topic（additive） | 播完發 ack{request_id, status, served_by} | **推薦**：additive、不改現有 `/state/tts_playing` 行為、向後相容（無 id 的純文字仍走舊路） |
| B. 擴 `/state/tts_playing` 成 struct（帶 id） | 改現有 topic | **不做**：會破壞 echo gate / Executive / Brain 三個消費者（高風險），且 echo gate timing 是 magic number（[CLAUDE.md 不能改](../../pawai-brain/speech/CLAUDE.md)） |
| C. Megaphone 播放成功偵測（解析 Go2 回報） | 真確認硬體播出 | research_only：Go2 對音訊 API silent ignore（[MEMORY 已知陷阱](../../CLAUDE.md)），可能無回報，6/18 前不做 |

**4. Required data**
- 現行 `/tts` envelope schema（contract）+ `interaction_executive` SAY step 產 envelope 的點。
- contract 版本（interaction_contract.md，加新 topic 需同步更新 contract，[docs-convention 規則](../../CLAUDE.md)）。

**5. Pure software tasks**
- T-V7a `[pure software]`：設計 `/event/tts_ack` schema（additive topic）+ `/tts` envelope 加 optional `request_id`（向後相容：無 id 時行為不變）。**純設計 + contract 草案**，不改 code。
- T-V7b `[pure software]`：寫 ack 發布點的純邏輯單測（mock：播放成功 → ack status=ok；fallback 到 piper → served_by=piper；except → status=error 但 EXIT 仍送）。

**6. Jetson tasks**
- T-V7c `[Jetson needed]`：在 Jetson e2e 驗 ack 回路（純語音 stack）——發帶 id 的 `/tts` → 收 `/event/tts_ack`，確認 id 對得上、status 正確。**additive，不改現有播放行為。**

**7. Go2 HITL tasks**
- T-V7d `[Go2 driver needed，無 motion]`：經 Go2 Megaphone 實播，確認 ack 在「真有播出」vs「silent fail」兩種情況下狀態正確（silent fail 是否能被 ack 偵測 = 取決於選項 C，可能仍偵測不到硬體層失敗，標 limitation）。

**8. Metrics**
- ack request_id 對應正確率（發 N 句 → 收 N 個 ack，id 全對）。
- ack status 與實際播放結果一致率。
- limitation：Megaphone 硬體 silent fail 能否被 ack 偵測（預期否，需文件化）。

**9. Pass/fail threshold**
- PASS：帶 id 的 `/tts` → ack id 100% 對應 + status 反映 provider 結果（軟體層）+ 向後相容（無 id 純文字行為不變）。
- FAIL：破壞向後相容（舊純文字路徑變化）→ 回退設計。

**10. Risk**
- 動 `/tts` / `/state/tts_playing` 不慎破壞 echo gate（1.5s magic number）→ ASR 自激。**緩解：ack 是新 topic，不碰 `/state/tts_playing`；echo gate 不動。**
- Megaphone 硬體 silent fail 無法被軟體 ack 偵測（Go2 silent ignore）→ ack「成功」未必真播出。**必須文件化為 limitation，不可宣稱「ack=確認真播出」。**

**11. Rollback**
- ack 是 additive topic + optional envelope 欄 → 移除 publisher / 不發 id 即回現行。contract 草案 revert。

**12. Should we do before Monday? — maybe**
schema 設計 + 單測（T-V7a/b）純軟體可先做。但接線（V7c/d）需 Jetson + Go2，且要小心 echo gate；且 ack 對 demo 的直接收益（vs V1/V3/V6）較間接（可觀測性）。建議：**設計先行，接線視彩排是否需要「確認 safety 台詞播出」的可觀測性需求。**

**13. Should it enter 6/18 demo runtime? — no**
additive 可觀測性，非 demo 必需；且 Megaphone silent fail 偵測有硬限制（Go2 silent ignore）。設計落檔 + 單測，接線 post-6/18 或視 Roy 需求。**不對外宣稱「ack 確認真播出」**（硬體層偵測不到）。

---

### V8 — Interrupt / cancel speaking（打斷正在播放）

**分級：`research_only`（高風險、與 Megaphone state machine 衝突）｜優先：P2｜task_type：jetson_needed**

**1. Desired demo benefit**
理論上讓使用者「打斷」PawAI 正在播放的長句（如說錯了、想重問），提升對話自然度。對 demo 是「更像真寵物（叫一聲就停下說話聽你）」的進階互動。

**2. Current baseline**
- **無 interrupt 機制**。Megaphone 序列是 ENTER(4001) → UPLOAD(4003)×N → WAIT(duration+0.5s tail) → EXIT(4002) → cooldown 0.5s（[speech.md §7](../../pawai-brain/architecture/0511/speech/speech.md)），**WAIT 期間阻塞、不可中途取消**。
- `/state/tts_playing=True` 全程鎖死，echo gate 在播放期間**丟掉所有 ASR frame**（[speech.md §8](../../pawai-brain/architecture/0511/speech/speech.md)）——**所以播放期間根本聽不到使用者打斷**（設計上防自激）。
- ⚠️ **tts_node mid-session 重啟 → Megaphone silent fail**（[speech.md §13 #8](../../pawai-brain/architecture/0511/speech/speech.md)）——任何「中途清掉播放」若不當會卡 Megaphone state machine（[speech-tts-lanes-megaphone.md §9](../../pawai-brain/architecture/0511/speech/speech-tts-lanes-megaphone.md)：EXIT 沒送 → 後續無聲）。

**3. Candidate options**
| 選項 | 內容 | 結論 |
|---|---|---|
| A. Megaphone 中途 EXIT（4002）打斷 | 收 interrupt → 提前送 EXIT → 停播 | research_only：需驗 Megaphone state machine 是否接受中途 EXIT 而不卡死（高風險，[silent fail 坑](../../pawai-brain/architecture/0511/speech/speech.md)） |
| B. Studio 按鈕打斷（外部觸發，不靠 ASR） | 繞過 echo gate（播放期 ASR 聾） | maybe（**歸 Cloud A Studio 控制面**，本 plan 不主導 UI）；技術上仍需 A 的中途 EXIT |
| C. 不做（demo 用短句，不需打斷） | 維持現狀 | **6/18 預設**：demo 對話多為短回覆，打斷需求低；風險>收益 |

**4. Required data**
- Megaphone 中途 EXIT 行為（Go2 v1.1.7 韌體是否接受 UPLOAD 中途 EXIT 不卡死）——**需 Jetson + Go2 實驗，無文件**。

**5. Pure software tasks**
- T-V8a `[pure software]`：設計 interrupt topic + 狀態機草案（收 interrupt → 標記 cancel → 播放 loop 檢查旗標 → 提前 EXIT）。純設計，不接線。

**6. Jetson tasks**
- T-V8b `[Jetson needed]`：在 Jetson + Go2 driver 上**實驗** Megaphone 中途 EXIT 是否安全（送 EXIT 後下一句 ENTER 是否 silent fail）。**高風險 spike，隔離環境，不進 demo stack。**

**7. Go2 HITL tasks**
- T-V8c `[Go2 driver needed，無 motion]`：實機驗中途打斷後連續 n=3 句播放無 silent fail（若 V8b 顯示可行）。

**8. Metrics**
- 中途 EXIT 後下一句播放成功率（n=3，目標無 silent fail）。
- interrupt 到停播的延遲（proxy）。

**9. Pass/fail threshold**
- PASS（**才考慮**）：中途 EXIT 後 n=3 連續播放零 silent fail。
- FAIL（預期）：任一 silent fail → **放棄 interrupt，維持不做**（Megaphone state machine 不耐中途打斷）。

**10. Risk**
- **最高風險項**：中途 EXIT 卡死 Megaphone → demo 後續全無聲（需重啟 Go2 driver / 甚至 Go2 重開機，[MEMORY](../../CLAUDE.md)）。
- 播放期 echo gate 聾 → ASR 觸發打斷不可行（只能 Studio 外部觸發）。

**11. Rollback**
- 純設計無 runtime 改動。若 spike 接線 → env-gated 預設關，移除即回。**任何 silent fail 立即放棄。**

**12. Should we do before Monday? — no**
最高風險、與已知 Megaphone silent fail 坑直接衝突、demo 短句需求低、收益<風險。讓位給 V1/V3/V6。

**13. Should it enter 6/18 demo runtime? — no**
明確不進。Megaphone state machine 不耐中途打斷的風險過高，且 demo 對話以短句為主、打斷需求低。設計落檔作 post-6/18 research，**6/18 前不接線**。

---

## §3 任務清單（每 task：task_type + tests + HITL checklist + rollback）

> 約定：tests 欄含單測指令；HITL checklist 僅在需真機（Jetson / Go2）時填；rollback 一律可回現役。所有純函式抽取保留 call-site shim（行為零變化）。

### V1 — ASR anti-hallucination
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V1a 抽 hallucination_filter 純 module | pure_software | `python3 -m pytest speech_processor/test/ -v`（新增 filter 單測，比照 tts_split 模式） | — | revert；內聯邏輯保留 shim |
| T-V1b offline replay harness | pure_software | harness 對 corpus 產 confusion table，含 self-check（誤殺=0 於 24 筆） | — | 純工具，無 runtime |
| T-V1c 黑名單擴充 + 誤殺回歸 | pure_software | 24 筆固定指令誤殺率=0 回歸測試 | — | git revert list commit（回 22 pattern） |
| T-V1d Jetson 場地噪音 corpus | jetson_needed | — | ① clean-start `clean_speech_env.sh` ② Whisper cuda+float16（禁 int8）③ 只讀錄音不改 runtime ④ 同時只一套 speech session | 無 runtime 改動 |

### V2 — VAD threshold tuning
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V2a 抽 energy VAD 純函式 | pure_software | 單測：短靜音不誤 end / 長句不被切 | — | revert；內聯保留 |
| T-V2b Jetson VAD 延遲分布量測 | jetson_needed | — | ① `start_llm_e2e_tmux.sh` 獨立 session ② 現行閾值先量 baseline ③ 候選閾值 env override ④ 短/長句分開 n≥20 ⑤ 不進 demo 腳本 | 閾值在 yaml/env，override 即回 |

### V3 — demo command fast path
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V3a fast-path table 文件 | pure_software | 表與 intent_classifier code 對照（read-only） | — | 文件，無 runtime |
| T-V3b intent_classifier 單測補強 | pure_software | 24 筆 corpus intent 正確率 ≥0.875 + 路由正確 | — | test-only |
| T-V3c 擴 keyword 規則（若獲准） | pure_software | 新指令單測 + 24 筆回歸不退步 | — | git revert 規則 commit |
| T-V3d Jetson fast-path 延遲觀測 | jetson_needed | — | ① e2e session ② 只讀觀測 | 無 runtime |
| T-V3e motion 指令安全（若 B） | go2_motion_needed | **歸 Lane 1/Cloud A，本計畫不主導** | 依賴 Brain safety 鏈 | N/A（不接線） |

### V4 — 小模型 intent classifier
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V4a 三方可行性 memo | pure_software | memo 落檔可審 | — | 文件 |
| T-V4b fastText 離線 baseline（選配） | pure_software | 離線 F1 vs 純規則 | — | 不上機 |

### V5 — Cloud LLM vs rule engine routing
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V5a routing 決策表 | pure_software | 表覆蓋所有現行分支（對照 code） | — | 文件 |
| T-V5b routing 純函式 + 單測 | pure_software | 單測：高頻繞 LLM / safety 永 fast / timeout→RuleBrain / 記憶只 chat 寫 | — | revert；call site shim 保留 |
| T-V5c Jetson fallback 路徑驗證（選配） | jetson_needed | — | ① `force_fallback:=true` 測 RuleBrain ② 斷 tunnel 測五級 ③ 只讀 | 無 runtime |

### V6 — pre-render phrase pack
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V6a 離線 render 腳本 | pure_software | 產 16kHz/16bit/mono WAV（規格驗證） | — | 資產目錄，無 runtime |
| T-V6b cache key 一致性單測 | pure_software | pre-render key == runtime cache key | — | test-only |
| T-V6c Jetson cache 載入驗證 | jetson_needed | — | ① 啟動時載入（**禁 mid-session 重啟 tts_node**）② 量 cache hit | env 旗標關即回 5 句預熱 |
| T-V6d Go2 Megaphone 實播 | go2_motion_needed（實為 driver-only，無 motion） | — | ① Go2 driver + Megaphone ② 16kHz 清晰度/音量 ③ n=3 無 silent fail ④ 不 mid-session 重啟 tts | 同 V6c |

### V7 — TTS ack / request_id
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V7a ack schema + envelope 草案 | pure_software | contract 草案 + 向後相容檢查（無 id=舊行為） | — | 文件草案 |
| T-V7b ack 發布邏輯單測 | pure_software | 單測：ok/fallback served_by/except 仍 EXIT | — | test-only |
| T-V7c Jetson ack 回路驗證 | jetson_needed | — | ① e2e ② 帶 id `/tts`→收 ack id 對應 ③ 不碰 echo gate | additive topic 移除即回 |
| T-V7d Go2 silent-fail ack 邊界 | go2_motion_needed（driver-only） | — | ① Megaphone 實播 ② 驗 silent fail 是否被 ack 偵測（預期否，文件化 limitation） | 同 V7c |

### V8 — interrupt / cancel speaking
| task | task_type | tests | HITL checklist | rollback |
|---|---|---|---|---|
| T-V8a interrupt 狀態機草案 | pure_software | 設計落檔可審 | — | 文件 |
| T-V8b Jetson Megaphone 中途 EXIT spike | jetson_needed | — | ① **隔離環境**，不進 demo stack ② 中途 EXIT 後下句 ENTER 測 silent fail ③ 任一 silent fail 立即放棄 | 純 spike，env-gated 關 |
| T-V8c Go2 中途打斷 n=3 連播 | go2_motion_needed（driver-only） | — | ① 僅 V8b 顯示可行才做 ② n=3 零 silent fail | 放棄 interrupt 維持不做 |

---

## §4 Pure software vs Jetson vs Go2 HITL 三桶分類

### 桶 1 — Pure software（無硬體，6/18 前可全做，多數可離線 replay）
- **V1**：T-V1a 抽 filter module、T-V1b replay harness、T-V1c 黑名單擴充 + 誤殺回歸。
- **V2**：T-V2a energy VAD 純函式 + 單測。
- **V3**：T-V3a fast-path table、T-V3b intent 單測、T-V3c keyword 擴充（若獲准）。
- **V4**：T-V4a 可行性 memo、T-V4b fastText 離線（選配）。
- **V5**：T-V5a routing 決策表、T-V5b routing 純函式 + 單測。
- **V6**：T-V6a 離線 render 腳本、T-V6b cache key 單測。
- **V7**：T-V7a schema 草案、T-V7b ack 邏輯單測。
- **V8**：T-V8a interrupt 狀態機草案。

> 共通：純函式抽取一律保留 call-site shim（行為零變化）；新單測併入 `python3 -m pytest speech_processor/test/ -v`，可被 [ros2-test-suite](../../CLAUDE.md) / `pawai smoke brain` 後置呼叫。

### 桶 2 — Jetson needed（需 Jetson runtime，只讀觀測 / 離線資產載入，不改 demo flow）
- **V1 T-V1d**：場地噪音 corpus 收集（Whisper cuda+float16）。
- **V2 T-V2b**：VAD 延遲分布量測（baseline vs 候選閾值，獨立 e2e session）。
- **V3 T-V3d**：fast-path 延遲觀測（只讀）。
- **V5 T-V5c**：fallback 路徑驗證（`force_fallback` / 斷 tunnel）。
- **V6 T-V6c**：phrase pack cache 載入驗證（**禁 mid-session 重啟 tts_node**）。
- **V7 T-V7c**：ack 回路驗證（additive，不碰 echo gate）。
- **V8 T-V8b**：Megaphone 中途 EXIT spike（**隔離環境，高風險**）。

> 共通硬規則（[CLAUDE.md](../../CLAUDE.md) + [speech CLAUDE](../../pawai-brain/speech/CLAUDE.md)）：① clean-start `clean_speech_env.sh`；② 同時只一套 speech session；③ Whisper cuda+float16（禁 int8 silent fail）；④ 改 .py 必 `colcon build --packages-select speech_processor` + source；⑤ **絕不 mid-session 重啟 tts_node**（Megaphone silent fail）。

### 桶 3 — Go2 HITL（需 Go2，本 plan 全為 driver-only / Megaphone 播放，**無 Go2 motion**）
- **V6 T-V6d**：pre-render WAV 經 Megaphone 實播（16kHz 清晰度 + n=3 無 silent fail）。
- **V7 T-V7d**：ack 在真播 vs silent fail 的邊界驗證。
- **V8 T-V8c**：中途打斷後 n=3 連播（僅 V8b 可行才做）。
- **V3 T-V3e**（若擴 motion 指令）：翻跟斗等 motion 指令安全 → **歸 Lane 1 / Cloud A motion 安全鏈，本 plan 不主導、只標依賴**；`come_here` 永不接 motion（[F6](../../navigation/2026-06-13-nav-618-claim-wording.md)）。

> **本 plan 不需任何 Go2 motion**（語音是互動主線，不驅動移動）。所有「Go2 HITL」實為 Go2 driver + Megaphone 播放（無移動）。唯一 motion 相關（V3e 翻跟斗）明確讓給 Lane 1/Cloud A。

---

## §5 Metrics / Pass-fail threshold 總表

| # | 主要 metric | PASS threshold | FAIL → 動作 |
|---|---|---|---|
| V1 | 黑名單誤殺率（24 筆固定指令） / 幻覺漏擋率 | 誤殺=0 不退步 + 漏擋率較 baseline 降 | 任一指令誤殺 → 回滾擴充 |
| V2 | VAD speech_end 延遲 P50/P95 + 長句截斷率 + 誤觸率 | 延遲降 + 截斷率不升 + 誤觸不升（n≥20） | 任一退步 → 不動 VAD |
| V3 | intent 正確率（24 筆 corpus） + fast-path 路由正確 | ≥0.875 不退步 + table 與 code 一致 | 退步/不符 → 修 table（不改行為） |
| V4 | 三方取捨 memo（質性）/（選配）小模型 F1 gain | memo 可審；小模型不顯著贏則維持純規則 | — research，不設能力門檻 |
| V5 | routing 決策表覆蓋率 + 純函式單測 | 覆蓋所有現行分支 + 單測綠 + 行為等價 | 未文件化分支 → 補測 |
| V6 | demo canned set cache hit 率 + Megaphone n=3 無 silent fail | 100% cache hit + 實播清晰 + n=3 OK | cache miss → 修 key；silent fail → 查序列 |
| V7 | ack request_id 對應率 + 向後相容 | id 100% 對應 + 無 id 純文字行為不變 | 破壞相容 → 回退設計 |
| V8 | 中途 EXIT 後 n=3 連播 silent fail 數 | 零 silent fail | 任一 silent fail → 放棄 interrupt |

> **延遲類 metric 一律標「開發期 proxy」**——任何 V 項即便量到延遲改善，**6/18 對外都不宣稱語音延遲/反應時間數字**（[claim matrix Non-Claims](../../mission/2026-06-18-capability-claim-matrix.md)），除非 Roy 授權一次含 latency 欄的完整 trusted HITL 重跑。

---

## §6 Rollback 總表

| # | runtime 改動面 | rollback 機制 |
|---|---|---|
| V1 | 黑名單 list（data）+ 純 module 抽取 | git revert list commit（回 22 pattern）；module 抽取保留內聯 shim |
| V2 | 無（純函式 + 量測）/ 若調閾值在 yaml/env | env override `energy_vad.*` 即回現行/Noisy Profile v1 |
| V3 | 無（table + 單測）/ 若擴 keyword | git revert 規則 commit；motion 不接線 |
| V4 | 無（純評估） | N/A |
| V5 | 純函式抽取（行為等價） | revert commit；call-site shim 保留 |
| V6 | env-gated phrase pack 載入旗標 | 關旗標即回 5 句預熱；離線腳本不碰 runtime |
| V7 | additive topic + optional envelope 欄 | 移除 publisher / 不發 id 即回；contract 草案 revert |
| V8 | 無（設計）/ 若 spike 接線 env-gated 預設關 | 移除即回；任一 silent fail 立即放棄 |

> **共通鐵則**：① 全部 spike 預設 default-off / 離線 additive，目標零 runtime diff；② **絕不 mid-session 重啟 tts_node**（Megaphone silent fail）；③ 不動 echo gate 1.5s magic number（[CLAUDE.md](../../pawai-brain/speech/CLAUDE.md)）；④ 任何進 runtime 的提議都需 Roy 回穩日（6/17）點頭 + 有 rollback（master B-4）。

---

## §7 決策表：每 sub-capability 的 before_monday + enter_6/18_runtime + 理由

| # | Sub-capability | 分級 | 優先 | before_monday | enter_6/18_runtime | 理由 |
|---|---|:---:|:---:|:---:|:---:|---|
| V1 | ASR anti-hallucination | proven | P0 | **yes** | no | 純軟體零風險、防線已 6/04 false-trigger=0.0 proven；擴充版作離線資產，runtime 不動（B-4）；不宣稱反幻覺已驗證 |
| V2 | VAD threshold tuning | needs_hitl | P1 | **maybe** | maybe | 純函式重構可先做；真調閾值必 Jetson 場地數據；且 demo 收音若走 Studio 則邊際效益低 → 先確認收音路徑 |
| V3 | demo command fast path | proven | P0 | **yes** | maybe | 純軟體 table+單測強化「固定指令秒回」敘事；fast-path 機制本就在 runtime；擴 keyword/motion 由 Roy 拍 |
| V4 | 小模型 intent classifier | research_only | P2 | **no** | no | 無 demo 直接收益、需 corpus（未就緒）、本地小模型智商已驗不足；維持純 rule |
| V5 | LLM vs rule routing | proven | P1 | **yes** | maybe | 純軟體決策表+純函式單測降 5/5 架構碎片化風險；等價重構可審後 Roy 決定併不併 |
| V6 | pre-render phrase pack | needs_hitl | P0 | **yes** | maybe | 離線產 WAV 純軟體零風險、直接支援「台詞秒回 + 雲端 down 也能播」；Megaphone 實播驗過 + Roy 點頭值得進 |
| V7 | TTS ack / request_id | needs_hitl | P1 | **maybe** | no | schema+單測可先做；接線需 Jetson+Go2 且小心 echo gate；Megaphone silent fail 偵測有硬限制；非 demo 必需 |
| V8 | interrupt / cancel speaking | research_only | P2 | **no** | no | 最高風險（Megaphone state machine 不耐中途打斷）、demo 短句需求低、收益<風險；落檔 post-6/18 |

**Cloud B 一句話**：6/18 前實際動手只排 **V1 + V3 + V5 + V6 的純軟體部分**（全 P0/P1、全離線/純函式/單測、零 runtime diff），把「防幻覺有效 / 固定指令繞 LLM / routing 可預測 / 台詞秒回」從印象變成有數字+有單測的證據鏈。**沒有任何一項要求換 ASR/LLM/TTS 模型或調安全相關 timing**；VAD（V2）一律等數據；interrupt（V8）一律 post-6/18。

---

## §8 需 Roy 拍板的 Open Decisions

| # | 決策 | 選項 | Cloud B 傾向 | 阻擋什麼 |
|---|---|---|---|---|
| Q1 | demo 收音路徑 = Studio 筆電麥克風 還是 機上 USB mic？ | Studio（繞 VAD）/ 機上 mic（吃 VAD） | 確認後才知 V2 VAD tuning 值不值得做 | V2 是否啟動 |
| Q2 | demo 五幕 canned phrase 文字定稿（給 V6 pre-render） | 與 [Cloud A phase conductor §6](2026-06-13-demo-phase-conductor-plan.md) 對齊 | 取 Cloud A 清單為準，本 plan 只 render | V6 pre-render 資產內容 |
| Q3 | V6 pre-render 用哪個 voice？（Despina / edge Xiaoxiao / Piper） | 影響 cache key 命中 + demo 音色一致 | 與 demo 主線 TTS 同 voice（避免音色跳） | V6 cache key + 音色 |
| Q4 | V3 是否擴 demo 動作指令（翻跟斗等 motion）？ | 擴（需 Lane 1/Cloud A motion 安全）/ 不擴 | 不擴或只加非 motion keyword；motion 讓 Lane 1 | V3c/V3e |
| Q5 | 6/18 前是否允許把 V1 黑名單擴充 / V5 等價重構 / V6 phrase pack 載入 併進 demo build？ | 併（提升可靠性）/ 不併（B-4 預設不動） | 預設不併，回穩日（6/17）視彩排需求逐項決定 | enter_6/18_runtime 標 maybe 的三項 |
| Q6 | 是否授權一次「含 latency 欄」的完整 voice HITL 重跑？ | 授權（才能講延遲）/ 不授權（維持不講延遲） | 不強求；6/18 維持「不宣稱語音延遲」最安全 | 任何延遲數字對外宣稱 |
| Q7 | V7 ack 回路 / V8 interrupt 是否要進 6/17 前彩排觀測需求？ | 要（可觀測性）/ 不要（讓位 V1/V3/V6） | 不要；V7 設計落檔、V8 post-6/18 | V7c/d、V8 全部 |

---

> **結語**：本 plan 全程不碰 nav（C1-C12 / F1-F10 不觸碰）、不重複 Cloud A offline fallback、不換任何模型、不動 echo gate magic number、不 mid-session 重啟 tts_node。6/18 前的高價值純軟體交付集中在 V1/V3/V5/V6；VAD 與 interrupt 維持「數據先行 / post-6/18」。所有能力分級與 [claim matrix](../../mission/2026-06-18-capability-claim-matrix.md)（voice.command 窄版 pass / voice.stop fail）一致，無 overclaim。
