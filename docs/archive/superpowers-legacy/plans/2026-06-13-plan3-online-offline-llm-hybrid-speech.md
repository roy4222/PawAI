# Plan3 — Online / Offline / LLM-Hybrid Speech（線上／離線／LLM 混合語音）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> Plan ID：**plan3**　角色：Cloud/Fable = 規劃＋審查；Codex = 實作
> 計畫群：PawAI Demo Flow Reliability Sprint｜本份只負責 **Q5（C-plus 混合語音）+ offline fallback**
> 權威上層：[`2026-06-13-pawai-pre618-final-execution-plan.md`](2026-06-13-pawai-pre618-final-execution-plan.md)、[`2026-06-13-demo-flow-reliability-master-plan.md`](2026-06-13-demo-flow-reliability-master-plan.md)
> 交叉計畫：Conductor（plan2，phase 切換）、Lane 3 CLI（`pawai demo mode`）、S1 Nav（plan-s1）、Operator Runbook（plan-runbook）

---

## 1. Goal（目標）

讓 6/18 五幕 live demo 的**語音層**在任意網路狀況下都「不開天窗、不卡 timeout、安全優先」：

- **三層語音（Q5 = C-plus，非阻塞）**：
  - **Layer 1 快觸發**：fast intent / perception trigger，**不等 LLM**。
  - **Layer 2 LLM 自然回覆**：若在 short deadline 內返回才用（demo beat 1.5–2s，沿用 `chat_wait_ms=1500`；Q&A 4–6s）。
  - **Layer 3 rule canned fallback**：觸發條件為**任一**：無偵測 / 低信心 / LLM timeout / TTS timeout / 網路斷 / operator fallback / 時間壓力。
- **Safety 永遠 rule-first**，LLM 不能 override；**offline canned = 0s、safety = 0s**。
- **timeout 收緊**：`llm_timeout` 15→6（`llm_bridge_node.py:201`）；`openrouter_gemini_timeout_s` dataclass dead-default 60→6 一致性修正（`tts_node.py:153`；env 已生效 6 於 `:989`）。
- **五幕 3-tier canned phrase table**（success / degraded / generic）+ **WAV pre-render**（piper cache）。
- **`offline_mode` 新 param（預設 off = byte-identical）** + env-offline proven path（`LLM_ENDPOINT=http://127.0.0.1:1/`）。
- **rule fallback 觸發於 slow / broken / unstable**，不只「無偵測」。

**鐵律**：cloud LLM / cloud TTS **絕不可 block demo**。五幕**不可寫成純 canned**，也**不可讓任何一幕乾等 15s LLM timeout**。

本計畫**不實作 code**（Cloud/Fable 只規劃；Codex 依 §13 / Codex Implementation Packet 實作）。

---

## 2. Current state（現狀，引用 file:line）

### 2.1 LLM 鏈（`speech_processor/speech_processor/llm_bridge_node.py`）
- 主線 `openai/gpt-5.4-mini`（CLAUDE.md）；OpenRouter gemini fallback `google/gemini-3-flash-preview`（`:233` declare）。
- `llm_timeout` 預設 **15.0s**（`llm_bridge_node.py:201`）— 用於 **vLLM/local endpoint** 路徑（`:738`）。
- `openrouter_request_timeout_s` = **4.0s**（`llm_bridge_node.py:242`）；`openrouter_overall_budget_s` = 5.0s（`:243` 附近）。
- **G-T2 待釐清**：demo 主線（gpt-5.4-mini）走哪條 timeout — OpenRouter 路徑（4s）或 vLLM/local 路徑（15s）。收緊 `llm_timeout` 對「主線吃 OpenRouter」情形是**保險絲**（涵蓋 endpoint 被改成 vLLM 的 env override 場景），對「主線吃 vLLM」情形是**直接療效**。

### 2.2 TTS 鏈（`speech_processor/speech_processor/tts_node.py`）
- providers：`PIPER` / `EDGE_TTS` / `OPENROUTER_GEMINI`。
- 主線 `openrouter_gemini` voice Despina，model `google/gemini-3.1-flash-tts-preview`（`tts_node.py:979-988`）。
- fallback chain：`_build_fallback_chain()` 建 **gemini → edge_tts → piper**（`tts_node.py:1119-1133`）。
- `openrouter_gemini_timeout_s`：**dataclass default = 60.0**（`tts_node.py:153`，dead-default 地雷）；**env declare default = 6.0**（`tts_node.py:989`，`_env_float("OPENROUTER_GEMINI_TIMEOUT_S", 6.0)`）。**實際生效 = 6.0**（param 從 `get_parameter` 取，env declare 覆寫 dataclass）。`:153` 的 60.0 只在「某路徑直接讀 dataclass 而不經 param」才會引爆，屬一致性地雷。

### 2.3 Brain canned / chat fallback（`interaction_executive/interaction_executive/brain_node.py`）
- `chat_wait_ms` 預設 **1500**（`brain_node.py:439` declare、`:510` read）— 等 LLM reply window；超時走 `_on_chat_timeout`。
- chat timeout fallback：`_on_chat_timeout(session_id)`（`brain_node.py:1124-1145`）→ `build_plan("say_canned", args={"text": "我聽不太懂"}, source="rule:chat_fallback", reason="chat_candidate_timeout")`。
- `say_canned` 是既有 plan kind（多處：`:1139`、`:1416`、`:1451`、`:1581`、`:1998`、`:2098`）。
- **無 `offline_mode` param**（grep 確認，brain_node 無此 param，需新增）。
- demo_phase 機制存在（`:311` runtime callback 接受、驗證、拒絕未知；`:496` declare 預設 `all`；`:539` read）；`PHASE_ALLOWED_KINDS`（`interaction_state.py:33`）。**本計畫不改 phase 機制**（屬 Conductor/plan2），只消費「目前 demo_phase」決定 offline 播哪句 canned。

### 2.4 既有 offline 手段（env override，**proven**）
- CLAUDE.md「完全離線模式」：`LLM_ENDPOINT="http://127.0.0.1:1/" TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh`。
- `LLM_ENDPOINT` 指本地不存在 port → ConnectionRefused <1ms → 即時 fallback。
- **proven anchor**：5/12 brain-freeze-v2 night offline chain；3/17 斷 tunnel RuleBrain 5/5 pass（MEMORY）。

### 2.5 Piper WAV cache（**proven**）
- Piper TTS 有 cache 機制：重複句 cache hit ≈0s；新句 ~2.4s（MEMORY 3/18）。
- ⚠ **禁 mid-session 重啟 tts_node**（Megaphone silent-fail 坑，MEMORY）— phrase-pack 只能 boot-time 載入；demo 主線走 USB 外接喇叭（非 Megaphone）風險較低，仍需 HITL 驗。

---

## 3. Scope（範圍）

本計畫只動三個檔，四件事，**全為純加法、預設 off = byte-identical**：

1. **Timeout 收緊**（`llm_bridge_node.py` + `tts_node.py`）：`llm_timeout` 15→6；`openrouter_gemini_timeout_s` dataclass 60→6 一致性。
2. **五幕 3-tier canned phrase table**（`brain_node.py`）：success / degraded / generic 三桶，phase → 台詞對映；台詞用 Q4/Q5 鎖定 zh 句。
3. **`offline_mode` 新 param**（`brain_node.py`，預設 False = byte-identical）：True 時 LLM 路徑直接走 canned、跳過 cloud 等待；對應 CLI `pawai demo mode offline`（Lane 3 包裝 param set，本計畫只定 param 契約）。
4. **WAV pre-render SOP**（piper cache 暖機）：demo 前置對五幕 canned 各發一次 `/tts` 暖 cache，latency≈0。

**檔案邊界（exact）**：
- `speech_processor/speech_processor/tts_node.py`
- `speech_processor/speech_processor/llm_bridge_node.py`
- `interaction_executive/interaction_executive/brain_node.py`（canned table + offline_mode param）

---

## 4. Forbidden scope（禁止範圍）

- ❌ **不換主線模型**（gpt-5.4-mini / Despina / sensevoice 維持；offline 只用既有 piper/edge/local ASR）。
- ❌ **不重寫 `_build_fallback_chain` 架構**（只加 offline 短路與 timeout 調整）。
- ❌ **不改 phase 機制**（PHASE_ALLOWED_KINDS / demo_phase callback 屬 Conductor=plan2；本計畫只「讀」目前 phase）。
- ❌ **不改 safety chain / explicit input / Studio skill_request 行為**（safety > explicit > phase；offline_mode 不可短路 safety canned）。
- ❌ **不做 LLM streaming**（架構大改，P2 deferred，MEMORY）。
- ❌ **不寫五幕為純 canned**，也**不讓任一幕乾等 15s LLM timeout**（Q5 鐵律）。
- ❌ **不 mid-session 重啟 tts_node**（Megaphone silent-fail；phrase-pack 只 boot-time 載入）。
- ❌ **不依賴 goto_relative / 任何 Go2 motion**（本計畫全純語音/TTS，HITL 不碰 Go2 motion）。
- ❌ **不 overclaim**：未 HITL 前一律標 needs-HITL；只說「code merged + 單測綠（needs-HITL）」。
- ❌ 不改 `start_full_demo_tmux.sh` / `executive.yaml` / `.claude/skills/`（需另開 PR + demo smoke 全綠 + Roy 核可）。
- ❌ 不講 fallen / guardian / emergency-alert（enable_fallen:=false 永久鎖，屬其他 plan；canned table 不得含此類句）。

---

## 5. Tasks（任務清單）

> 每項：id / task_type（pure_software｜jetson｜go2_motion）/ 優先級 / exact files / exact tests / rollback / demo impact / needs_roy / needs_go2_motion。

### T1 — 統一 `openrouter_gemini_timeout_s` dataclass dead-default 60→6
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`speech_processor/speech_processor/tts_node.py`（`:153` dataclass `openrouter_gemini_timeout_s: float = 60.0` → `6.0`）
- **內容**：dataclass default 改 6.0 與 env declare（`:989`，`_env_float("OPENROUTER_GEMINI_TIMEOUT_S", 6.0)`）一致，消除 60s 地雷。**不改任何讀取路徑**（實際生效仍走 param=6.0），只是消除「某路徑誤讀 dataclass」的潛在 60s 黑洞。
- **⚠ .env / container 覆寫稽核（防 code 改被靜默還原）**：env declare 仍接受 `OPENROUTER_GEMINI_TIMEOUT_S`／LLM 端 `PAWAI_LLM_TIMEOUT` 覆寫。若 Jetson `.env`/`.env.local` 或 container 啟動注入 `OPENROUTER_GEMINI_TIMEOUT_S=60`（或 `llm_timeout`/`PAWAI_LLM_TIMEOUT=15`），code 改會被**靜默還原成 60/15s 黑洞**。**T6 WAV 暖機 SOP / runbook 開場前置須加一步**：`grep -E "OPENROUTER_GEMINI_TIMEOUT_S|PAWAI_LLM_TIMEOUT|LLM_TIMEOUT" .env .env.local` 確認**無 60/15 殘留**（demo 前置 audit）；H1 真機驗收時順帶確認生效值 ≤6s（非 .env 覆寫回大值）。
- **exact tests**：`speech_processor/test/test_tts_node.py`（無則新建）新增斷言 `TTSConfig().openrouter_gemini_timeout_s == 6.0`；既有 tts 單測全綠。
- **rollback**：`git revert <T1 commit>`；或單行還原 `:153` 為 `60.0`。
- **demo impact**：消除 cloud TTS 卡 60s 風險（正面）；off-path，不改主線播放行為。
- **needs_roy**：否（HITL 驗於 T9 合併量測）
- **needs_go2_motion**：否

### T2 — 收緊 `llm_timeout` 15→6（demo 保險絲）
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`speech_processor/speech_processor/llm_bridge_node.py`（`:201` `self.declare_parameter("llm_timeout", 15.0)` → `6.0`）
- **內容**：`llm_timeout` 收 15→6（vLLM/local 路徑 `:738` 的上限）。**保留 env override 能力**：若 declare 已用常數，改為 `_env_float("PAWAI_LLM_TIMEOUT", 6.0)` 風格（若 node 已有 `_env_float` helper 則用之；無則維持常數 6.0 並在 docstring 註記 rollback 值）。**不動** `openrouter_request_timeout_s`(4s) / `openrouter_overall_budget_s`(5s)。
- **exact tests**：`speech_processor/test/test_llm_bridge_node.py`（無則新建）斷言 `get_parameter("llm_timeout").value == 6.0`；模擬 LLM 超時 → 在 ≤6s 內回 None（讓 brain `_on_chat_timeout` 接手）。
- **rollback**：`git revert <T2 commit>`；或還原 `:201` 為 `15.0`。
- **demo impact**：cloud/local LLM 慢時最多等 6s 即 fallback canned（正面）。
- **needs_roy**：否（HITL 驗於 T9）
- **needs_go2_motion**：否

### T3 — 五幕 3-tier canned phrase table（success / degraded / generic）
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`（新增 module-level dict `DEMO_CANNED_TABLE`，靠近 `:80` 既有 idle canned pool；不改現有 say_canned 觸發點）
- **內容**：建「phase → {success, degraded, generic}」三桶台詞表（§9 完整文字鎖定，用 Q4/Q5 zh 句）。**online 不啟用此表**（仍走 LLM reply / 既有 say_canned）；**offline_mode=True 或 fallback 觸發時**，依目前 `self.demo_phase` 取對應桶台詞。三桶語意：
  - `success`：真觸發成功時的自然台詞（仍可被 LLM reply 取代）。
  - `degraded`：偵測到但信心低 / cloud 慢 → 退化但可信的台詞。
  - `generic`：無偵測 / 完全 fallback → 安全通用台詞。
  - **safety 幕（s5_safety）固定 rule-first**：canned = §9 S5 拒絕句，**不可被 offline_mode 以外的任何路徑改寫成 LLM**。
- **exact tests**：`interaction_executive/test/test_brain_node.py`（或既有 brain 測試檔）斷言：(a) `DEMO_CANNED_TABLE` 五個 phase key 各有 success/degraded/generic 三桶且非空；(b) 給定 `demo_phase=s3_pose_object` + fallback → emit 的 say_canned text ∈ s3 桶；(c) `demo_phase=all` 時不啟用此表（byte-identical：仍 emit「我聽不太懂」於 `_on_chat_timeout`）。
- **rollback**：`git revert <T3 commit>`；offline_mode off + demo_phase=all → 表不啟用，現行行為不變。
- **demo impact**：每幕都有保底台詞（正面），消除乾等。
- **needs_roy**：是（台詞文字定稿需 Roy 確認，§9）
- **needs_go2_motion**：否

### T4 — `offline_mode` 新 param（brain LLM 路徑短路 cloud）
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`（declare 靠近 `:496` demo_phase declare；runtime callback 靠近 `:311` 加入 `offline_mode` 分支）
- **內容**：新增 `self.declare_parameter("offline_mode", False)`（預設 False = byte-identical）。`offline_mode=True` 時：(a) chat candidate / LLM reply 路徑**直接走 T3 canned table**，**不開 `chat_wait_ms` 等待窗**（0s）；(b) runtime 可由 `ros2 param set /brain_node offline_mode true` 切換、**不重啟**；(c) runtime callback 接受 bool、log transition。**不短路 safety**：safety canned 永遠 rule-first（與 offline_mode 無關）。對應 CLI `pawai demo mode online|offline`（Lane 3 實作 param set 包裝，**本計畫只定 param 名稱與語意契約**）。
- **exact tests**：brain 單測斷言：(a) `offline_mode=True` → chat 路徑回 canned，**不發** cloud LLM request（mock LLM client 0 calls）；(b) `offline_mode=False` → 行為與現行 byte-identical（迴歸：仍走 chat_wait_ms → LLM reply / 超時 canned）；(c) runtime callback set `offline_mode true/false` 被接受且更新 `self.offline_mode`。
- **rollback**：`git revert <T4 commit>`；或 `ros2 param set /brain_node offline_mode false`（預設即 false）；或退回 §2.4 env-offline（proven）。
- **demo impact**：demo 當天 network drop 可不重啟切 offline、秒回 canned（正面）。
- **needs_roy**：是（runtime 切換需 HITL 驗不卡/不 silent fail，§8 H2）
- **needs_go2_motion**：否

### T5 — rule fallback 觸發條件擴充（slow / broken / unstable）
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`interaction_executive/interaction_executive/brain_node.py`（`_on_chat_timeout` `:1124-1145` 改為走 T3 phase-aware canned；新增 fallback-reason 列舉，**不改 timeout 機制本身**）
- **內容**：把現行「只在 chat_candidate_timeout（無 reply）才 canned」擴充為「**任一** fallback reason 都走 phase-aware canned」：
  - `chat_candidate_timeout`（既有，LLM 慢/無 reply）
  - `low_confidence`（perception 信心低於門檻 — 由現有 perception event 帶 confidence 欄位判斷，若無則此 reason 留 hook 不啟用，避免擴張 scope）
  - `llm_error` / `tts_error`（既有 chain 失敗信號）
  - `offline_mode`（T4）
  - `operator_fallback`（Studio hidden button / reset_context 後）
  - **不改觸發 timeout 的數值**（仍 `chat_wait_ms`）；只改「timeout 後播什麼」從固定「我聽不太懂」→ phase-aware T3 generic 桶。
  - `demo_phase=all`（非 demo 模式）時維持原「我聽不太懂」字串以保 byte-identical。
- **exact tests**：brain 單測：(a) `demo_phase=s2_greet` + chat timeout → emit say_canned ∈ s2 桶 generic；(b) `demo_phase=all` + chat timeout → emit「我聽不太懂」（byte-identical）；(c) safety 路徑不受 fallback reason 擴充影響（safety canned 仍 rule-first 0s）。
- **rollback**：`git revert <T5 commit>`；demo_phase=all 即還原原字串。
- **demo impact**：slow/broken/unstable 都有對幕保底（正面）。
- **needs_roy**：是（HITL 驗 §8 H1/H3）
- **needs_go2_motion**：否

### T6 — WAV pre-render cache 暖機 SOP（piper 五幕 canned）
- **task_type**：jetson（暖機在 Jetson 上跑；SOP 文件純軟體）
- **優先級**：P0
- **exact files**：本計畫 §9 + Operator Runbook（plan-runbook，交叉）；暖機指令用既有 `/tts` topic pub，**不新增 code 檔**（利用 tts_node 既有 piper cache）。若需腳本則新建 `scripts/warmup_canned_wav.sh`（純 ros2 topic pub 包裝，無 node 改動）。
- **內容**：demo 前置步驟：對 §9 三桶五幕共 N 句各發一次 `/tts`（boot-time、tts_node 已起後）暖 piper cache → demo 當天 offline canned latency≈0。**禁 mid-session 重啟 tts_node**（boot 後一次暖完）。
- **exact tests**：cache hit 路徑單測（`test_tts_node.py`：相同文字第二次合成走 cache 分支）；`scripts/warmup_canned_wav.sh --dry-run`（若建）列出 N 句不實發。
- **rollback**：不暖機 → 首句 ~2.4s（degraded 但不開天窗）；刪 `warmup_canned_wav.sh`。
- **demo impact**：offline canned 秒回（正面）。
- **needs_roy**：是（Jetson 暖機後量 latency≈0，§8 H3）
- **needs_go2_motion**：否

### T7 — `pawai demo mode online|offline` CLI 契約定義（給 Lane 3 接）
- **task_type**：pure_software（契約文件，本計畫不實作 CLI）
- **優先級**：P1（**契約定義 P1；CLI 實作本身 = post-6/18，歸 Lane 3**）
- **標籤 source of truth**：master §4.3 P2「`pawai demo mode` CLI 實作 = post-6/18（Q3）」為權威；本 T7 只交付**契約**（param 名稱/語意），6/18 不實作 CLI。雙處標籤以 master 為準。
- **exact files**：本計畫 §9.4（契約描述）；實作歸 Lane 3 CLI plan。
- **內容**：定義 CLI 子命令語意：`pawai demo mode offline` → `ros2 param set /brain_node offline_mode true` + （可選）`ros2 param set /tts_node provider piper`（**注意：tts_node mid-session 切 provider 風險，預設不切，只切 brain offline_mode**，台詞層先 offline，TTS 仍走既有 chain 的 piper 末端）；`online` → 還原 false。零 runtime 行為例外需 Roy 點頭。
- **exact tests**：N/A（契約文件；Lane 3 plan 負責 CLI client-side 測試）。
- **rollback**：契約刪除不影響 runtime（param 仍可手動 set）。
- **demo impact**：operator 一鍵切（正面）；fallback 為 §2.4 env-offline。
- **needs_roy**：是（CLI 行為由 Lane 3 + Roy 核）
- **needs_go2_motion**：否

### T8 — byte-identical 迴歸測試套件
- **task_type**：pure_software
- **優先級**：P0
- **exact files**：`speech_processor/test/test_tts_node.py`、`speech_processor/test/test_llm_bridge_node.py`、`interaction_executive/test/test_brain_node.py`
- **內容**：明確的「全 flag off → 與現行一致」迴歸：`offline_mode=False` + `demo_phase=all` → (a) brain chat 路徑走 LLM reply / 超時「我聽不太懂」；(b) timeout 值（除收緊外）路徑不變；(c) `DEMO_CANNED_TABLE` 不被觸發。確保進主線後既有 ~955 測試不退。
- **exact tests**：上述三檔的迴歸 case；`pytest speech_processor interaction_executive`（CI fast gate）全綠。
- **rollback**：N/A（測試本身）。
- **demo impact**：保證純加法、不誤傷主線（正面）。
- **needs_roy**：否
- **needs_go2_motion**：否

---

## 6. Pure software tasks（純軟體任務匯總，WSL/CI 可完成）

| Task | 檔案 | CI fast gate 跑 |
|---|---|---|
| T1 | `tts_node.py:153` | speech_processor pytest |
| T2 | `llm_bridge_node.py:201` | speech_processor pytest |
| T3 | `brain_node.py`（canned table） | interaction_executive pytest |
| T4 | `brain_node.py`（offline_mode param） | interaction_executive pytest |
| T5 | `brain_node.py`（fallback reasons） | interaction_executive pytest |
| T7 | §9.4 契約（無 code） | N/A |
| T8 | 三測試檔迴歸 | speech + interaction_executive pytest |

**注意**：新增 core .py 行受 blocking flake8（max-line=100，MEMORY）；GitHub Actions fast gate 跑 speech + pawai_brain 純 Python 測試。

---

## 7. Jetson tasks（no-motion）

| Task | 內容 | 前置 |
|---|---|---|
| T6 暖機 | tts_node 起後對五幕 N 句各發 `/tts` 暖 piper cache，量 latency≈0 | nav stack 已停（8GB 互斥）；tts_node boot 完成；**禁 mid-session 重啟** |
| H1/H2/H3（§8） | timeout 收緊驗 / offline_mode runtime 切換驗 / 五幕 canned + cache 驗 | demo lane 起、Roy 在場、nav 清場 |

**全程 no-motion**：不發 goto / cmd_vel / 任何 Go2 動作。D435 有 MIPI error 不影響（純語音/TTS）。

---

## 8. Go2 HITL tasks（motion）

**本計畫無 Go2 motion 任務。** 所有 HITL 為純語音/TTS，不依賴 Go2 motion / D435。

> 安全前置（與計畫群共用）：開工第一件事 = 確認 **Go2 停穩 + `pawai demo stop` 清 nav stack**（6/13 EOD nav 還在跑、剛撞牆）。brain demo stack 與 nav stack **8GB 互斥**。e-stop 就位（雖本計畫不動 Go2，仍遵守 sprint 安全前置）。**禁 Damp(1001) 對移動中 Go2**（屬其他 plan，這裡不發任何動作）。

| HITL | 內容 | 觸發 | 通過標準 | needs_roy | needs_go2_motion |
|---|---|---|---|:---:|:---:|
| **H1** | timeout 收緊真機驗（T1/T2） | demo lane + 限速/拔網模擬 cloud 慢 | online 在 ≤6s 內 fallback 出聲，無 60s/15s 黑洞 | 是 | 否 |
| **H2** | runtime offline_mode 切換（T4） | demo lane + `ros2 param set /brain_node offline_mode true`（或 `pawai demo mode offline`） | 切換不重啟、LLM 路徑走 canned、無 silent fail、`offline_mode false` 還原 byte-identical | 是 | 否 |
| **H3** | 五幕 canned + WAV cache（T3/T5/T6） | offline mode + 逐幕切 demo_phase（配合 Conductor=plan2） | 每幕播對應 §9 桶台詞、cache hit latency≈0、safety 幕固定拒絕句 | 是 | 否 |
| **H4** | byte-identical 退路（T8） | offline_mode off + demo_phase=all | 行為與現行主線一致（LLM reply 正常、超時「我聽不太懂」） | 是 | 否 |
| **H5** | env-offline 完整鏈復驗（§2.4 proven） | `LLM_ENDPOINT=…1/ TTS_PROVIDER=piper ASR=local` 啟動 | 全鏈 offline 出聲、無 cloud 等待 | 是 | 否 |

---

## 9. Tests（測試策略）

### 9.1 單元（pure software，CI fast gate）
- T1：`TTSConfig().openrouter_gemini_timeout_s == 6.0`（dataclass 一致）。
- T2：`llm_timeout` declare = 6.0；LLM 超時在 ≤6s fall through。
- T3：`DEMO_CANNED_TABLE` 五 phase × 三桶完整非空；phase→canned 對映正確。
- T4：`offline_mode=True` → 0 cloud LLM calls；`False` → byte-identical。
- T5：fallback reason 擴充 → phase-aware canned；`demo_phase=all` → 原字串；safety 不受影響。
- T8：全 flag off 迴歸（~955 不退）。

### 9.2 整合（真機 HITL，§8）：H1..H5。

### 9.3 五幕 3-tier canned phrase table（**§T3 定稿，需 Roy 確認文字**）

> 以下 success/generic 用既有計畫群 §9 五句為 success 基準；degraded 為「偵測到但退化」中間句；generic 為「完全 fallback」安全句。**台詞最終定稿須 Roy 於彩排前鎖定**（6/17 前，no late content change）。voice 用 demo 主線 voice（避免音色跳、cache-key 命中）。

| phase | success（真觸發） | degraded（信心低/cloud 慢） | generic（無偵測/完全 fallback） |
|---|---|---|---|
| **s1_nav** | 我正在移動到巡檢位置。 | 我正在前往巡檢位置，請稍等。 | 我先在這裡待命。 |
| **s2_greet** | Roy，歡迎回來，我看到你了。 | 嗨，歡迎回來。 | 哈囉，很高興見到你。 |
| **s3_pose_object** | 我看到杯子了，記得補充水分。 | 我看到桌上有東西，記得喝水喔。 | 記得多喝水、休息一下。 |
| **s4_gesture** | 你要我 WeGo 一下嗎？比 OK 我就開始。 | 我看到你的手勢了，比 OK 我就開始。 | 你可以比個手勢跟我互動。 |
| **s5_safety** | 這個動作不安全，我不能執行。 | 這個指令我不能做，太危險了。 | 為了安全，我不能執行這個動作。 |

- **s5_safety 三桶全為「拒絕語意」**：safety 永遠 rule-first，LLM 不可 override；offline / online 皆同句語意。
- **s3 pose=sitting 為 bonus 非硬依賴**（Q4）：杯子（object）為主觸發，sitting 不到不影響 canned。
- **不含** fallen / guardian / emergency-alert 任何字眼（enable_fallen:=false 永久鎖）。

> **台詞核可閘（Roy 簽核，hard gate）**：上表 15 句（5 phase × 3 tier）為**最終定稿候選**，**須 Roy 於 6/15 前最遲簽核鎖定**。**未簽核前 T3 task = blocked**：Codex 以 `LOCKED_CANNED` placeholder 實作 `DEMO_CANNED_TABLE` dict **結構**（key/tier 齊全、值先放暫定句），**不得自改措辭、不得擅自定稿**；Roy 簽核後一次性換上鎖定文字、不再 late change（彩排前 no late content change）。
>
> **Roy 核可簽名：__________　日期：__________　（未簽 = T3 阻塞，僅 placeholder 結構可進）**

### 9.4 CLI 契約（T7，給 Lane 3）
- `pawai demo mode offline` → `ros2 param set /brain_node offline_mode true`（預設**不**動 tts_node provider，避免 mid-session 切 provider 風險）。
- `pawai demo mode online` → `ros2 param set /brain_node offline_mode false`。
- `pawai status`（brain runtime 區塊）顯示 `offline_mode` / `demo_phase`（Lane 3 實作）。
- 零 runtime 行為例外需 Roy 點頭。

### 9.5 證據要求
- 每個 HITL 記錄日期 + speech_end→say_canned latency + 是否 silent fail。
- offline canned 出聲錄影（保底 fallback 也是 demo snapshot 證據）。
- T1/T2 量 cloud-slow fallback latency（≤6s）。

---

## 10. Rollback（回退）

| 層級 | 回退手段（exact command） |
|---|---|
| 最強（單 flag） | `ros2 param set /brain_node offline_mode false`（預設即 false）→ 全回現行 online byte-identical |
| timeout | `git revert <T1>`（tts 60.0）、`git revert <T2>`（llm 15.0）|
| canned table / fallback | `git revert <T3> <T5>`；或 demo_phase=all → 表不啟用 |
| offline param | `git revert <T4>`；或 param 維持 false |
| 啟動前 env（**proven**） | `LLM_ENDPOINT="http://127.0.0.1:1/" TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh` — 無新 code，5/12 proven |
| 最終保底 | cloud 全崩 + runtime 開關失效 → 重啟帶 env override（proven）→ 仍失效 → 純影片 fallback（snapshot） |

**三層任一都能交付，不開天窗。**

---

## 11. Done criteria（完成判準）

- [ ] T1 dataclass 60→6 一致，`TTSConfig().openrouter_gemini_timeout_s==6.0` 單測綠。
- [ ] T2 `llm_timeout` 15→6，LLM 超時 ≤6s fall through 單測綠。
- [ ] T3 五幕 3-tier canned table 落地，phase→桶對映單測綠，**台詞 Roy 鎖定**。
- [ ] T4 `offline_mode` param 預設 False，True→0 cloud LLM call、False→byte-identical 單測綠。
- [ ] T5 fallback reason 擴充（slow/broken/unstable）→ phase-aware canned，safety rule-first 不受影響。
- [ ] T6 WAV pre-render 暖機 SOP 寫入 runbook，Jetson 量 latency≈0（H3）。
- [ ] T7 CLI 契約交付 Lane 3。
- [ ] T8 byte-identical 迴歸（~955 不退）全綠。
- [ ] H1..H5 真機 HITL 通過（Roy 在場，nav 清場）；H5 env-offline 發表日復驗。

---

## 12. Execution order（執行順序）

1. **T1 + T2**（timeout 收緊，純軟體、低風險高回報）— 先消「卡 timeout」最痛點。
2. **T8 迴歸骨架**（先建 byte-identical 迴歸 case，後續每改一項都跑）。
3. **T3**（五幕 canned table，與 Conductor=plan2 phase 對齊台詞）。
4. **T4**（offline_mode param，byte-identical 迴歸先綠）。
5. **T5**（fallback reason 擴充 → phase-aware canned）。
6. **T7**（CLI 契約交付 Lane 3）。
7. **T6**（WAV 暖機，需 Jetson）。
8. **HITL H1..H5**（Roy 在場，nav 清場後）— 純語音/TTS，不依賴 D435/Go2 motion，風險最低，優先排進 HITL queue。

---

## 13. Codex Implementation Prompt（給 Codex 的實作提示）

> 你是 builder。依本 §13 + Codex Implementation Packet 實作 T1–T5 + T8（T6/T7 為 SOP/契約，不寫 node code）。**不得擴張 scope、不得改 runtime claim、不得碰 Go2 motion。** 每項小 commit + 跑測試 + 回報 diff/test-result/risk。

逐項：
1. **T1**：`tts_node.py:153` dataclass `openrouter_gemini_timeout_s: float = 60.0` → `6.0`。不動讀取路徑。加 dataclass 預設值斷言測試。
2. **T2**：`llm_bridge_node.py:201` `llm_timeout` 15.0 → 6.0（若 node 有 `_env_float` helper 則改 `_env_float("PAWAI_LLM_TIMEOUT", 6.0)`，否則常數 6.0 + docstring 註記 rollback=15.0）。不動 `openrouter_request_timeout_s`/`overall_budget`。
3. **T3**：`brain_node.py` module-level 新增 `DEMO_CANNED_TABLE`（§9.3 文字逐字），五 phase × 三桶（success/degraded/generic），新增 helper `_phase_canned(phase, tier)` 回字串。**不改既有 say_canned 觸發點**。
4. **T4**：`brain_node.py` `declare_parameter("offline_mode", False)`（靠 `:496`）；runtime callback（靠 `:311`）加 `offline_mode` bool 分支 + log；`offline_mode=True` 時 chat 路徑直接走 canned、**不開 chat_wait_ms 窗**。
5. **T5**：`brain_node.py` `_on_chat_timeout`（`:1124-1145`）改走 `_phase_canned(self.demo_phase, "generic")`，`demo_phase=='all'` 時維持「我聽不太懂」；新增 fallback-reason 列舉（`chat_candidate_timeout`/`llm_error`/`tts_error`/`offline_mode`/`operator_fallback`；`low_confidence` 留 hook 不啟用）。**不改 safety canned 路徑**。
6. **T8**：三測試檔（`test_tts_node.py`/`test_llm_bridge_node.py`/`test_brain_node.py`）補 byte-identical 迴歸 case。

**驗收**：`pytest speech_processor interaction_executive` 全綠 + flake8（max-line=100）綠 + 既有 ~955 不退。

---

## Codex Implementation Packet（精確實作包）

### 檔案清單（exact）
- `speech_processor/speech_processor/tts_node.py`（T1）
- `speech_processor/speech_processor/llm_bridge_node.py`（T2）
- `interaction_executive/interaction_executive/brain_node.py`（T3/T4/T5）
- `speech_processor/test/test_tts_node.py`（T1/T6 cache hit/T8）
- `speech_processor/test/test_llm_bridge_node.py`（T2/T8）
- `interaction_executive/test/test_brain_node.py`（T3/T4/T5/T8）

### 精確 commands
```bash
# 單測（WSL，CI fast gate 等價）
python3 -m pytest speech_processor/test/test_tts_node.py -q
python3 -m pytest speech_processor/test/test_llm_bridge_node.py -q
python3 -m pytest interaction_executive/test/test_brain_node.py -q
# flake8（新 core code blocking，max-line=100）
flake8 --max-line-length=100 \
  speech_processor/speech_processor/tts_node.py \
  speech_processor/speech_processor/llm_bridge_node.py \
  interaction_executive/interaction_executive/brain_node.py
# 全套 speech + interaction_executive 迴歸
python3 -m pytest speech_processor interaction_executive -q
```

### 接受標準（acceptance）
- T1：`TTSConfig().openrouter_gemini_timeout_s == 6.0`；既有 tts 測試全綠。
- T2：`llm_timeout` param value == 6.0；超時 ≤6s 回 None；env override（若實作）`PAWAI_LLM_TIMEOUT` 可覆寫。
- T3：`DEMO_CANNED_TABLE` 含 `s1_nav/s2_greet/s3_pose_object/s4_gesture/s5_safety` 各三桶非空；文字逐字 == §9.3。
- T4：`offline_mode` declare 預設 False；True→mock LLM client 0 calls；False→byte-identical。
- T5：phase-aware canned 正確；`demo_phase=all`→「我聽不太懂」；safety canned rule-first 0s 不受影響。
- T8：全 flag off → ~955 測試不退。
- 全部：commit 小顆、PR 乾淨、diff + test-result + risk 回報。

---

## Cloud Review Checklist（Cloud/Fable 審查清單）

- [ ] **零 overclaim**：PR 描述只說「code merged + 單測綠（needs-HITL）」，未宣稱 proven。
- [ ] **byte-identical 證明**：T8 迴歸實跑、`offline_mode=False`+`demo_phase=all` 行為 == 現行（貼測試輸出）。
- [ ] **safety rule-first 未被破壞**：T4/T5 未讓 offline_mode 短路 safety canned；safety 幕台詞固定拒絕語意。
- [ ] **無 scope 擴張**：未改 `_build_fallback_chain` 架構、未改 phase 機制（PHASE_ALLOWED_KINDS / demo_phase callback）、未動 `start_full_demo_tmux.sh`/`executive.yaml`/`.claude/skills/`。
- [ ] **timeout 收緊正確**：`tts_node.py:153`=6.0、`llm_bridge_node.py:201`=6.0；未誤動 `openrouter_request_timeout_s`(4s)。
- [ ] **台詞無禁詞**：canned table 不含 fallen/guardian/emergency-alert；voice 與 demo 主線一致。
- [ ] **mid-session tts_node 風險**：T7 CLI 契約預設不切 tts provider（避 Megaphone silent-fail）。
- [ ] **不依賴 Go2 motion / goto_relative / D435**。
- [ ] **flake8 max-line=100 綠**、~955 不退。

---

## Stop Conditions（停止條件）

立即停手、回報 Cloud/Fable，不自行決策：
- 任一 byte-identical 迴歸（T8）失敗 — 代表純加法假設破裂。
- 改動觸及 safety chain / explicit input / Studio skill_request 行為（禁區）。
- 需改 phase 機制（PHASE_ALLOWED_KINDS / demo_phase callback）才能完成 — 屬 Conductor=plan2，停手協調。
- 需 mid-session 重啟 tts_node 才能讓 cache/provider 生效 — 觸 Megaphone silent-fail 禁區。
- 需碰 `start_full_demo_tmux.sh` / `executive.yaml` / `.claude/skills/` — 需另開 PR + Roy 核可。
- 需發任何 Go2 motion / goto / cmd_vel — 本計畫禁止。
- ~955 既有測試任一退化且無法以純加法修復。
- 台詞文字未經 Roy 鎖定就要進主線（§9.3 需 Roy 定稿）。

---

## Required Evidence（必備證據）

提交時附：
1. **diff**（每 task 一顆 commit，最小範圍）。
2. **test-result**：`pytest speech_processor interaction_executive -q` 完整輸出（綠）；T8 byte-identical case 輸出。
3. **flake8 輸出**（max-line=100 綠）。
4. **byte-identical 證明**：`offline_mode=False`+`demo_phase=all` 的 chat timeout 仍 emit「我聽不太懂」的測試輸出。
5. **risk 回報**：列出任一 stop-condition 命中或近觸的情形。
6. **HITL（Roy 在場時）**：H1..H5 各記日期 + latency（speech_end→say_canned）+ silent-fail 與否；offline canned 出聲錄影。

---

## Rollback Plan（回退計畫，彙整）

| 觸發 | 動作 |
|---|---|
| 任一 task 行為異常 | `git revert <commit>`（每 task 獨立 commit，可單獨回退） |
| demo 當天 runtime 異常 | `ros2 param set /brain_node offline_mode false`（單 flag 回 online） |
| timeout 過嚴誤 fallback | `git revert <T2>` 還原 15.0（或 env `PAWAI_LLM_TIMEOUT=15`） |
| canned 表/fallback 出錯 | demo_phase=all → 表不啟用，行為回現行 |
| runtime 開關全失效 | 重啟帶 env override（proven §2.4）→ 仍失效 → 純影片 fallback |

---

## 14. 跨計畫依賴（cross-plan deps，引用不重複）

- **plan2（Conductor / demo-phase）**：phase 切換時機與清理（pending_confirm/active_plan/gesture_cooldown）+ PHASE_ALLOWED_KINDS 擴充至 s1_nav/s2_greet/s3_pose_object/s4_gesture/s5_safety + alias。本計畫**讀** `self.demo_phase` 決定 offline 播哪句，**不改** phase 機制。`brain_node.py` 為共享檔（plan2 改 phase 區塊、plan3 改 canned/offline_mode/fallback 區塊）— **需與 plan2 協調 brain_node.py 編輯區段避衝突**（merge 順序 LOCKED：plan2-T2-1/2/3 先 → plan3-T3/T4/T5 → plan2-T2-4/T2-5，見 master §8）。
  - **`greet_require_sitting` toggle 歸 plan2-T2-5、對 auto + manual 兩路徑都生效**（進 s2 設 False、進 s3 還原；不綁 `auto_advance_enabled`）。⟹ 本計畫 T5 的 s2 fallback canned **不得假設 sitting hardlock**：s2 offline/generic 桶（§9.3）以 face-only 為前提，sitting 缺席不擋 s2 canned。本計畫不自行改 `greet_require_sitting`。
- **Lane 3 CLI plan**：`pawai demo mode online|offline`（param set 包裝，§9.4 契約）+ `pawai status` brain runtime 區塊顯示 offline_mode/demo_phase。
- **plan-runbook（Operator Runbook）**：WAV pre-render 暖機 SOP（T6）+ online↔offline 切換操作 + env override 備援指令寫入 runbook。
- **plan-s1（S1 Nav）**：s1_nav phase 全 suppress 社交；offline 台詞 §9.3 s1「我正在移動到巡檢位置」。本計畫**不依賴** nav motion。
- **Lane 1 ISM plan**：`offline_mode` 與 `ism_enabled` 正交（offline_mode 是語音層短路台詞，ISM stage 2a 是 phase policy 接管）；不互相 leak。
