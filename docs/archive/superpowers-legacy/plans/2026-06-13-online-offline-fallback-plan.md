# Online / Offline Fallback Plan — PawAI 五幕 Demo 語音/TTS 韌性計畫

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 計畫群：PawAI Demo Flow Reliability Sprint（Cloud A）｜本份：Online / Offline Fallback Plan

---

## 1. Goal（目標）

讓 6/18 demo 五幕在**任意網路狀況**下都不開天窗：

- **online**（網路正常）：走主線 ASR/LLM/cloud TTS，保有自然度與彈性對話。
- **offline / degraded**（網路差、cloud 慢、tunnel 斷）：**不等 cloud timeout**，直接走 rule canned phrase + local TTS（piper/edge），最好預先 render WAV cache 讓 latency≈0。

核心原則三句：
1. **網路差不可卡** — cloud 慢時 online 路徑要在數秒內 fallback，不可讓使用者乾等 15s/60s timeout。
2. **每幕都有保底台詞** — 五幕各備一句 offline canned phrase（§9 五句），phase 決定播哪句。
3. **byte-identical 退路** — 不啟用 offline mode 時，行為與現行主線完全一致（純加法，不改主線行為）。

本計畫**只規劃，不實作 code**。能力誠實分三級（proven / needs-HITL / research-only）。

---

## 2. Current state（現狀，已實測 anchor）

### 2.1 Online 路徑（主線，現行）

**LLM 鏈**（`speech_processor/llm_bridge_node.py`）：
- 主線 `openai/gpt-5.4-mini`（CLAUDE.md / handoff）。
- OpenRouter gemini fallback model `google/gemini-3-flash-preview`（`llm_bridge_node.py:233` declare 預設）。
- gemini timeout → return None（**不**再試 DeepSeek，budget 不足；`llm_bridge_node.py:537/675-696`）；非 timeout error 才條件試 DeepSeek。
- 最終 fallback：brain 端 `rule:chat_fallback` → `say_canned`「我聽不太懂」（`brain_node.py:1139-1141`，source=`rule:chat_fallback`）。
- env override：`PAWAI_LLM_MODEL` / `LLM_ENDPOINT`（CLAUDE.md）。

**TTS 鏈**（`speech_processor/tts_node.py`）：
- providers：`PIPER` / `EDGE_TTS` / `OPENROUTER_GEMINI`（`tts_node.py:98-103`）。
- 主線 `openrouter_gemini` voice Despina，model `google/gemini-3.1-flash-tts-preview`（`tts_node.py:979-988`）。
- 三層 fallback chain：`_build_fallback_chain()`（`tts_node.py:1119-1133`）建 gemini → edge_tts → piper；all-or-nothing chunk 失敗則整段走下一個 provider（`tts_node.py:668-687`）。
- env override：`TTS_PROVIDER`（CLAUDE.md）。

**ASR 鏈**：`sensevoice_cloud → sensevoice_local → whisper_local`（CLAUDE.md `provider_order`）。
- env override：`ASR_PROVIDER_ORDER`。

### 2.2 既有 timeout 值（現行，已實測）

| 參數 | 位置 | 現行預設 | 觀察 |
|---|---|---|---|
| `llm_timeout`（vLLM/local 路徑） | `llm_bridge_node.py:201` | **15.0s** | 太長，online 卡 cloud 時會乾等到 15s |
| `openrouter_request_timeout_s` | `llm_bridge_node.py:242` | 4.0s | 合理，gemini 單發 budget |
| `openrouter_gemini_timeout_s`（TTS） | `tts_node.py:153` dataclass default | **60.0s** | **過長**（CLAUDE.md 也標 60s 太長） |
| `openrouter_gemini_timeout_s`（TTS） | `tts_node.py:989` env declare default | **6.0s** | ⚠ **與 :153 不一致**（見 §3 gap G-T1） |
| `chat_wait_ms`（brain 等 reply window） | `brain_node.py:439` | 1500ms | 等 LLM reply 才 say_canned 的窗口 |

### 2.3 既有 offline 手段（env override，proven）

CLAUDE.md「完全離線模式」一行：
```
LLM_ENDPOINT="http://127.0.0.1:1/" TTS_PROVIDER=piper \
  ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' \
  bash scripts/start_full_demo_tmux.sh
```
- `LLM_ENDPOINT` 指本地不存在 port → ConnectionRefused <1ms → 即時 fallback（與 3/17 斷 tunnel 5/5 fallback 同機制）。
- **proven anchor**：5/12 brain-freeze-v2 night offline chain 實機驗過 LLM/TTS fallback（handoff 證）；3/17 斷 tunnel RuleBrain 5/5 pass（MEMORY）。

---

## 3. Problems / gaps（問題與缺口）

| 編號 | 問題 | 嚴重度 | 來源 |
|---|---|---|---|
| **G-T1** | `openrouter_gemini_timeout_s` 兩處預設不一致（dataclass `:153`=60.0 vs env declare `:989`=6.0）。實際生效值取決於 param 讀取路徑（`:1093` 從 get_parameter 取，應為 6.0），但 dataclass default 60.0 是潛在地雷 — 若某路徑直接用 dataclass 預設會卡 60s。需先**確認實際生效值**再收緊。 | 高 | code 實測 |
| **G-T2** | `llm_timeout=15.0s`（`:201`）對 demo 太長 — cloud LLM 慢時使用者乾等 15s 才 fallback。注意此值用於 vLLM/local endpoint 路徑（`:738`），OpenRouter 路徑走 `openrouter_request_timeout_s`(4s)。需釐清 demo 主線（gpt-5.4-mini via OpenRouter？）實際吃哪條 timeout。 | 高 | code 實測 |
| **G-O1** | **無 runtime offline 開關**：目前 offline 只能靠「啟動前 env override」，啟動後無法不重啟就切 offline。demo 當天 network drop 需要**不重啟**就強制 canned + local TTS。 | 高 | 缺 feature |
| **G-O2** | **無 phase-aware canned phrase 表**：§9 五句 canned 尚未落地成「phase → 該播哪句」的對映；目前 say_canned 內容由各觸發點散落硬編。 | 中 | 缺 feature |
| **G-O3** | **無 WAV pre-render cache**：offline 時即使走 piper，首句合成仍需 ~2.4s（MEMORY）。五幕 canned 應可預先合成存 WAV，demo 當天 latency≈0。Piper 已有 cache（重複句 ≈0s，MEMORY）但需 demo 前**主動暖機/預存**五句。 | 中 | 缺 SOP |
| **G-O4** | online↔offline 切換無單一控制點，且不保證 byte-identical 退路有測試覆蓋。 | 中 | 缺測試 |

---

## 4. Scope（範圍）

本計畫只負責「語音/LLM/TTS 的 online/offline 韌性」，落在三件事：

1. **Timeout 收緊**（純軟體 param 調整 + 釐清生效路徑）：讓 online 在 cloud 慢時快速 fallback，不卡。
2. **Runtime offline mode 開關**（純軟體 + param，needs-HITL）：`pawai demo mode online|offline`（CLI 層，由 Lane 3 規劃實作）對應 brain + tts param，直接走 canned + local TTS、跳過 cloud。
3. **五幕 canned phrase 表 + WAV pre-render**（純軟體 + SOP，needs-HITL）：§9 五句綁 phase，piper 預合成存檔。

與 **Conductor**（`2026-06-13-demo-phase-conductor-plan.md`）交叉：phase 決定**要播哪句 canned**；本計畫提供「每個 phase 對應的 offline 台詞」，Conductor 負責 phase 切換時機。

---

## 5. Forbidden scope（禁止範圍）

延續計畫群共同禁區（§11）+ 本份特定禁區：

- ❌ **不換 LLM / TTS / ASR 模型當主線**（gpt-5.4-mini / Despina / sensevoice 維持；offline 只用既有 piper/edge/local ASR）。
- ❌ **不重寫 fallback chain 架構**（`_build_fallback_chain` 既有邏輯不動，只加 offline 短路與 timeout 調整）。
- ❌ **不改 online 主線行為**（offline mode 預設 off = byte-identical 現行）。
- ❌ 不做 LLM streaming（架構改動大，P2 deferred per MEMORY）。
- ❌ 不大改 Studio UI、不完整重寫 CLI、不進 Phase 3/4/5。
- ❌ 不在本計畫實作任何 code（只規劃）。

---

## 6. Tasks（任務清單，每項標 [pure software] / [Jetson needed] / [Go2 motion needed] + tests + HITL + rollback）

### T-FB-1：釐清 + 統一 `openrouter_gemini_timeout_s` 生效值 `[pure software]`
- **內容**：確認 `tts_node.py:153`（60.0）vs `:989`（6.0）哪個實際生效（`:1093` 從 get_parameter 取，研判生效=6.0）；統一 dataclass default 與 env declare default 一致（建議都 6.0，並評估 demo 可收到 **4.0s**）。修 `:153` 的 60.0 為 6.0 消除地雷。
- **能力分級**：needs-HITL（改完單測綠後待真機驗 cloud-slow fallback）。
- **tests**：`speech_processor` 既有 tts 單測 + 新增「param 生效值 = declare default」斷言；模擬 gemini 超時 → 走 edge fallback 在預期 timeout 內觸發。
- **HITL checklist**：Jetson 上 demo lane 起 → 拔網/限速模擬 cloud 慢 → 觀測首句在 ≤(設定 timeout + edge 合成) 內出聲，無 60s 黑洞。
- **rollback**：param 還原原值（dataclass 60.0 / env 6.0），無行為改動。

### T-FB-2：收緊 `llm_timeout` 並釐清 demo 主線吃哪條 timeout `[pure software]`
- **內容**：釐清 demo 主線（gpt-5.4-mini）走 OpenRouter 路徑（吃 `openrouter_request_timeout_s`=4s）還是 vLLM/local 路徑（吃 `llm_timeout`=15s, `:738`）。若主線吃 15s → 建議 demo 收到 **6.0s**（保守上限，超過就走 rule:chat_fallback say_canned）。env override 提供 `PAWAI_LLM_TIMEOUT`（若未存在則規劃新增 param 讀取，純加法）。
- **能力分級**：needs-HITL。
- **tests**：單測模擬 LLM 超時 → 在收緊 timeout 內 fall through 到 `rule:chat_fallback`（`brain_node.py:1139`）。
- **HITL checklist**：demo lane + `force_fallback` 或斷 tunnel → 量 speech_end → say_canned 出聲 latency；確認 ≤ 收緊 timeout + TTS。
- **rollback**：param 還原 15.0。

### T-FB-3：五幕 canned phrase 表（phase → offline 台詞） `[pure software]`
- **內容**：把 §9 五句固化成「phase → canned phrase」對映（資料表，非散落硬編）。online 時不啟用（仍走 LLM reply）；offline 時各 phase 用對應 canned。**與 Conductor 交叉**：Conductor 切 `demo_phase`，本表決定 offline 模式下該 phase 播哪句。
- **能力分級**：needs-HITL（表本身純軟體，但需真機確認每幕台詞與 phase 對得上）。
- **tests**：單測 `phase → canned` 對映完整（5 個 phase 各有對應句）；offline 模式下 phase=s3_pose_object emit 的 say_canned == §9 S3 句。
- **HITL checklist**：見 §8。
- **rollback**：offline mode off → 此表不啟用，online 行為不變。

### T-FB-4：WAV pre-render cache（五幕 canned 預合成） `[pure software]` + `[Jetson needed]`（暖機在 Jetson 上）
- **內容**：規劃一個 demo 前置步驟，用 piper 預先合成 §9 五句 → 存 WAV cache（利用 tts_node 既有 piper cache 機制，MEMORY：重複句 ≈0s）。demo 當天 offline canned latency≈0。實作形式：demo preflight 階段對五句各發一次 `/tts`（暖 cache）或預存 WAV 檔。
- **能力分級**：needs-HITL（cache 暖機 SOP，待真機確認 ≈0s）。
- **tests**：cache hit 路徑單測（重複句返回 cached WAV）；preflight 腳本 dry-run 列出五句。
- **HITL checklist**：Jetson 上 preflight 暖機後，重發五句各一次量 latency ≈0；確認 cache 不被 colcon build / deploy --delete 清掉（runtime/ 已在 rsync-excludes，MEMORY 6/12）。
- **rollback**：不暖機則首句 ~2.4s（degraded 但不開天窗）。

### T-FB-5：Runtime offline mode 開關（brain + tts param 短路 cloud） `[pure software]`
- **內容**：規劃 runtime param（例：brain `offline_mode` bool + tts provider 即時切 piper/edge）讓**不重啟**即可：(a) LLM 路徑直接走 rule canned（跳過 cloud LLM）；(b) TTS 直接走 local（跳過 gemini）；(c) ASR 走 local order。對應 CLI `pawai demo mode offline`（Lane 3 實作 param set 包裝）。**預設 off = byte-identical 現行**。注意：tts_node mid-session 切 provider 風險 — Megaphone silent fail（MEMORY）；但 demo 主線走 USB 外接喇叭非 Megaphone，風險較低，仍需 HITL 驗。
- **能力分級**：needs-HITL（純軟體 + param，但 runtime 切換需真機驗不卡/不 silent fail）。
- **tests**：單測 offline_mode=True → LLM 路徑回 canned 不發 cloud request；offline_mode=False → 行為與現行 byte-identical（迴歸測試）。
- **HITL checklist**：見 §8。
- **rollback**：`offline_mode=False`（預設）即還原；或退回啟動前 env override（proven 手段，§2.3）。

---

## 7. Pure software tasks（純軟體任務匯總）

可在 WSL / 開發機完成單測、不需 Jetson 的部分：
- T-FB-1 timeout 值統一 + param 斷言單測。
- T-FB-2 timeout 收緊 + fall-through 單測。
- T-FB-3 phase→canned 對映表 + 對映完整性單測。
- T-FB-5 offline_mode param 邏輯 + byte-identical 迴歸單測。
- T-FB-4 的 cache hit 路徑單測（暖機本身需 Jetson）。

**注意**：新增 core .py 受 blocking flake8（max-line=100，MEMORY）；CI fast gate 跑 speech 純 Python 測試。

---

## 8. Jetson / Go2 HITL tasks（真機驗收，需 Roy 在場）

> 安全前置（反映 §4 即時硬體狀態）：開工第一件事 = **確認 Go2 停穩 + `pawai demo stop` 清場**（6/13 EOD nav stack 還在跑、剛撞牆）。brain demo stack 與 nav stack **8GB 互斥**，跑語音 fallback HITL 前先確認 nav stack 已停。D435 有 MIPI error，**本計畫所有 HITL 不依賴 D435/Go2 motion**（純語音/TTS），可在 nav 清場後安全進行。

| HITL | 內容 | 觸發 | 通過標準 | 能力分級 |
|---|---|---|---|---|
| **H-1** | timeout 收緊真機驗（T-FB-1/2） | demo lane + 限速/拔網模擬 cloud 慢 | online 在 ≤收緊 timeout 內 fallback 出聲，無 60s/15s 黑洞 | needs-HITL |
| **H-2** | runtime offline mode 切換（T-FB-5） | demo lane + `pawai demo mode offline`（或 param set） | 切換後不重啟、LLM 走 canned、TTS 走 local、無 silent fail | needs-HITL |
| **H-3** | 五幕 canned + WAV cache（T-FB-3/4） | offline mode + 逐幕切 demo_phase（配合 Conductor） | 每幕播對應 §9 canned、cache hit latency≈0 | needs-HITL |
| **H-4** | byte-identical 退路（T-FB-5 off） | offline mode off | 行為與現行主線一致（online LLM reply 正常） | needs-HITL（迴歸） |
| **H-5** | env-offline 完整鏈重驗 | `LLM_ENDPOINT=…1/ TTS_PROVIDER=piper ASR=local` 啟動 | 全鏈 offline 出聲、無 cloud 等待 | **proven**（5/12 / 3/17）— 發表日**復驗一次** |

---

## 9. Tests（測試策略）

**單元（pure software，CI fast gate）**：
- timeout 生效值斷言（T-FB-1/2）。
- LLM 超時 → `rule:chat_fallback` say_canned fall-through（`brain_node.py:1139`）。
- TTS gemini fail → edge → piper chain 觸發（`_build_fallback_chain`）。
- phase→canned 對映完整（5 phase）。
- offline_mode=False byte-identical 迴歸。

**整合（真機 HITL，§8）**：H-1..H-5。

**證據要求**：每個 HITL 紀錄日期 + latency + 是否 silent fail；offline canned 出聲錄影（保底 fallback 也是 demo snapshot 證據，與 §S1 nav 同邏輯）。

---

## 10. Rollback（回退）

| 層級 | 回退手段 |
|---|---|
| 最強（單一 flag） | `offline_mode=False`（預設）→ 全部回現行 online 主線 byte-identical。 |
| timeout | param 還原原值（`llm_timeout`=15.0 / `openrouter_gemini_timeout_s` dataclass=60.0 env=6.0）。 |
| 啟動前 env（proven） | `LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'` — 不需任何新 code，5/12 proven。 |
| 最終保底 | demo 當天 cloud 全崩 + runtime 開關失效 → 重啟帶 env override（proven）→ 仍失效則純影片 fallback（demo snapshot）。 |

**三層任一都能交付，不開天窗。**

---

## 11. Done criteria（完成判準）

- [ ] G-T1 釐清 + 統一（timeout 不再有 60s 地雷），單測綠。
- [ ] G-T2 timeout 收緊到保守值，online cloud-slow fallback 真機 ≤ 收緊值（H-1）。
- [ ] runtime offline mode 開關規劃完成、CLI 接口與 Lane 3 對齊、byte-identical 迴歸測試綠（H-2/H-4）。
- [ ] 五幕 canned 表落地、WAV pre-render SOP 寫入 operator runbook（H-3）。
- [ ] env-offline 完整鏈發表日復驗一次（H-5 proven 復驗）。
- [ ] 能力分級表（§12）併入 master plan 完成度追蹤。

---

## 12. 能力分級總表（誠實三級）

| 能力 | 分級 | 證據 / 條件 |
|---|---|---|
| env-offline 完整鏈（LLM_ENDPOINT + TTS_PROVIDER=piper + local ASR） | **proven** | 5/12 brain-freeze-v2 night offline chain 實機；3/17 斷 tunnel RuleBrain 5/5（MEMORY）。發表日復驗。 |
| TTS gemini→edge→piper fallback chain | **proven**（chain 存在且 5/12 驗過） | `tts_node.py:1119-1133`；5/12 night |
| LLM gpt-5.4-mini → gemini → rule:chat_fallback | **proven**（fallback 機制） | `llm_bridge_node.py` + `brain_node.py:1139` |
| timeout 收緊（T-FB-1/2） | **needs-HITL** | code merged + 單測綠後待 H-1 |
| runtime offline mode 開關（T-FB-5） | **needs-HITL** | 純軟體 + param，待 H-2/H-4 |
| WAV pre-render cache（T-FB-4） | **needs-HITL** | 待 H-3 確認 ≈0s |
| 五幕 canned 表（T-FB-3） | **needs-HITL** | 待 H-3 phase 對映 |
| 換 LLM/TTS/ASR 模型當主線 | **forbidden** | §5 / §11 |
| LLM streaming pipeline | **research-only / deferred** | MEMORY P2，不進本 sprint |

---

## 13. Execution order（執行順序）

1. **T-FB-1 / T-FB-2**（timeout 釐清 + 收緊，純軟體）— 先消除「卡 timeout」這個最痛的點，低風險高回報。
2. **T-FB-3**（phase→canned 表，純軟體）— 與 Conductor 對齊台詞對映。
3. **T-FB-5**（runtime offline mode，純軟體 + Lane 3 CLI 接口）— byte-identical 迴歸先綠。
4. **T-FB-4**（WAV pre-render，需 Jetson 暖機）。
5. **HITL H-1..H-5**（Roy 在場，nav 清場後）— 純語音/TTS，不依賴 D435/Go2 motion，風險最低，可優先排進 HITL queue。

---

## 14. 6/18 presentation impact（對發表的影響）

- **正面**：網路差是 demo 最常見翻車點（VAD/LLM/cloud TTS 任一卡 timeout = 全場乾等）。本計畫讓五幕在 offline 下「秒回保底台詞」，**評審看不出是 fallback**（latency≈0 的 canned + local TTS）。
- **誠實 claim**：對外只講「具備網路降級韌性，雲端不可用時本地語音保底」— **不講** offline mode 是新功能的程度（env-offline 才是 proven，runtime 開關是 needs-HITL）。
- **保底層級**：cloud 正常→自然對話；cloud 慢→快速 fallback；cloud 全崩→env-offline（proven）→ 純影片（snapshot）。三層任一交付，不開天窗。
- **風險揭露**：runtime offline 切換（T-FB-5）若 H-2 未驗過，demo 當天**改用啟動前 env override**（proven）而非 runtime 切換。

---

## 15. 交叉引用（五份計畫互連）

- **Master**：[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md) — 本計畫完成度進度匯入。
- **Conductor**：[`2026-06-13-demo-phase-conductor-plan.md`](2026-06-13-demo-phase-conductor-plan.md) — **phase 決定播哪句 canned**；本計畫提供「phase → offline 台詞」對映（T-FB-3），Conductor 負責切換時機與清理（pending_confirm/active_plan/cooldown）。
- **S1 Nav**：[`2026-06-13-s1-low-risk-navigation-plan.md`](2026-06-13-s1-low-risk-navigation-plan.md) — s1_nav phase 全 suppress 社交，offline 台詞 §9 S1「我正在移動到巡檢位置」。
- **Operator Runbook**：[`2026-06-13-demo-operator-runbook-plan.md`](2026-06-13-demo-operator-runbook-plan.md) — WAV pre-render 暖機 SOP、online↔offline 切換操作、env override 備援指令寫入。
- **Lane 1 ISM**：[`2026-06-13-lane1-brain-ism-staged-enable-plan.md`](2026-06-13-lane1-brain-ism-staged-enable-plan.md) — offline_mode 與 ism_enabled 互不衝突（offline 是語音層短路，ISM stage 2a 是 phase policy 接管）；offline_mode 應與 ISM 各 stage 正交。
- **Lane 3 CLI**：[`2026-06-13-lane3-cli-v2-completion-plan.md`](2026-06-13-lane3-cli-v2-completion-plan.md) — `pawai demo mode online|offline` 由 Lane 3 實作（param set 包裝，零 runtime 行為例外需 Roy 點頭）；`pawai status` brain runtime 區塊顯示 offline_mode。
- 相關既有文件：[`docs/archive/runbook-legacy/2026-06-13-roy-hitl-queue.md`](../../archive/runbook-legacy/2026-06-13-roy-hitl-queue.md)（H-1..H-5 入列）。
