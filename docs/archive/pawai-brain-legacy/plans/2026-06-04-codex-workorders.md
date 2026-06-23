<!--
來源：route-paving workflow synthesis @ HEAD 885728f，2026-06-04。行號/檔案皆 source-verified。
執行狀態（Claude 維護）：
- 工單 1 (#118 Studio 證據 UI)：✅ 授權、Codex 進行中（純前端，WSL 可驗，不碰 Jetson）。
- 工單 2 (#120 gate→IE，default-OFF)：⏸ 待 Roy 授權（他明言「接之前要明確授權」；enforcement 是 motion-safety）。
- 工單 3 (#80 mic_stop 接線)：⏸ 待 Roy 授權 + 須 demo stop 後才部署；會改 demo VAD 預設，現在做會污染本輪 voice baseline。
- 工單 4 (schema_validator fail-closed 修正)：⏸ 低風險、非關鍵路徑（實際 blocker 是 sha_mismatch），待 Roy 一聲令下。
-->

# Codex Work-Orders — PawAI 軟體任務（2026-06-04，可在 WSL/dev 完成，無需 Jetson）

> 前置事實（全部已在 HEAD `885728f` WSL 上驗證）：
> - jetson SSH:22 目前 timeout（本批工單**完全不碰 Jetson/Go2**，純軟體）。
> - 全部驗收指令在 WSL 跑：`cd /home/roy422/newLife/elder_and_dog`。
> - frontend toolchain：node v24.11.0 / npm 11.6.1，`npm ci && npm run lint && npm run build` 在 HEAD 為綠。
> - pawai_brain offline 測試 338、interaction_executive 221、`test_capability_health_gate.py` 20 —— **gate 預設 OFF 時三者必須維持綠**。
> - `gh issue view` 無 `--json` 在本環境會 FETCH FAILED，要看 issue 一律加 `--json number,title,body,state,labels`。
>
> 誠實總則（North Star v2 §9 fail-closed）：能力分 pass/degraded/fail/insufficient_data；不可 over-claim；motion/nav 類 enforcement **預設關閉、未經 Roy 授權不得開啟**。

---

## 工單 1 — #118 Studio 證據 UI（provenance badge + scoreboard chip + trace reason-guard）

### 目標
在 Studio 前端把已經存在的後端 `GET /api/scoreboard`（frozen baseline 快照）顯示出來，並讓使用者一眼分辨資料來源是 **live(真 gateway) / mock(mock_server) / frozen(快照檔) / missing(檔不存在)**。Trace drawer 已大致建好，本工單只補「scoreboard chip + provenance badge + blocked/insufficient_data 一定要顯示 reason」三件事，**不重寫 drawer**。

### 要動的檔案
- 新增 `pawai-studio/frontend/hooks/use-scoreboard.ts`（GET `getGatewayHttpUrl()+"/api/scoreboard"`）
- 新增 `pawai-studio/frontend/components/shared/scoreboard-chip.tsx`（mirror 既有 `components/shared/gate-chip.tsx`，用 `components/ui/badge.tsx`）
- 新增 `pawai-studio/frontend/components/shared/provenance-badge.tsx`（4 態：live/mock/frozen/missing）
- 改 `pawai-studio/frontend/contracts/types.ts`：新增 `ScoreboardResponse` + `ScoreboardCapability` + provenance/backend enum。**不要**重複定義已存在的 `ConversationTracePayload`（types.ts:431-464 已有）
- 改 `pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx`：對 `blocked` / `insufficient_data` 狀態，若 `detail` 為空則 render 一個可見警告（不可空白）。drawer 本體已建好，**只加這個 reason-guard**
- 後端二選一加 backend 識別欄位（見下方契約決策）：改 `pawai-studio/backend/mock_server.py` + `pawai-studio/gateway/studio_gateway.py::_read_scoreboard`

### 資料／API 契約
後端 `GET /api/scoreboard`（studio_gateway.py:600-603，**已存在，不要重寫**）回傳：
```
{ provenance: "frozen"|"missing", source_path, schema_version, run_trusted,
  version_mismatch, git_commit, generated_at,
  capabilities: [ {capability_id, grade, failure_reason, brain_allowed, last_tested_at}, ... ] }
```
- **關鍵區分**：`provenance` 只表達「檔案身分」（frozen/missing），**不**表達 live/mock。live/mock 是「哪個 backend 在服務」這條獨立軸。
- **契約決策（採用 Option B，符合 #118「mock 不得假裝 live」）**：
  - gateway `_read_scoreboard` 回傳值新增 `"backend": "live"`。
  - mock_server **新增** stub `GET /api/scoreboard`（目前 mock_server 沒有此 route，已驗證）回傳 `{"provenance":"mock","backend":"mock","capabilities":[]}`。
- 前端 badge 邏輯：`backend==="mock"` → badge=mock；否則依 `provenance` 顯示 frozen/missing；fetch 失敗 → missing。
- scoreboard-chip 4 欄：`capability_id` / `grade` / `failure_reason` / `last_tested_at`；fetch 失敗或 `provenance==="missing"` → 顯示 "missing"，**永不空白**。

### 驗收（WSL，binary）
```bash
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npm ci
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npm run lint      # 0 errors
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npm run build     # 12 routes 編譯成功，exit 0
```
- 三條全 exit 0 = 過。任何 lint error 或 build fail = 不過。
- 後端 stub 驗證（在能起 backend 時）：`curl -s http://localhost:8080/api/scoreboard | python3 -m json.tool` 出現 `"backend"` 欄位；mock backend 回 `"backend":"mock"`。

### 誠實/scope 護欄
- chip/badge 只**顯示**快照，**不得**做 live recompute、不得觸發任何 motion/nav。
- `grade==="fail"`/`insufficient_data` 的能力在 UI 必須清楚標示，不可用顏色或文案暗示「可用」。face 目前 committed 快照 = FAIL，UI 不得呈現為 pass。
- mock 來源必須可見標記 mock，不得讓 demo 觀眾誤以為是真資料。

### 不做（scope guard）
- 不重寫 trace drawer（`skill-trace-content.tsx` 已 render 真 conversation_trace，只加 reason-guard）。
- 不改 `use-event-stream.ts` / `stores/state-store.ts` 的既有 trace 流。
- 不碰任何 Brain / IE / gate enforcement 邏輯（那是工單 4）。
- 不動 gateway `/api/scoreboard` 的 frozen/missing 解析邏輯，只加一個 `backend` tag。

---

## 工單 2 — #120 capability health gate → IE runtime 接線（**預設 OFF，enforcement 未經 Roy 授權不得啟用**）

### 目標
把「已完成的」純 gate 邏輯（#85 v0.2，`effective_status._grade_gate` + `CapabilityHealth`）接到 IE runtime：新增 grade loader（讀 frozen 快照）、skill→capability_id 對照、IE 第二道 gate。**純 wiring，不新增 gate 數學。** 全部走 ROS param **預設 OFF**：OFF 時 runtime 與今天 byte-identical。

> 紅旗：`capability_gate_enabled` 預設 `False`，且**不得**在任何 launch script / demo 入口設成 True。啟用是 motion-safety enforcement 變更，需 Roy 明確授權（CLAUDE.md「動 motion 先問」+ #120 RED-FLAG）。Codex 只寫 wiring 並保持 default-OFF。

### 要動的檔案
- 新增 `pawai_brain/pawai_brain/capability/health_loader.py`（讀快照 → `dict[capability_id → CapabilityHealth]` + skill→capability map）
- 改 `interaction_executive/interaction_executive/brain_node.py`（第二道 gate + param 宣告 + 收斂 allowlist）
- 改 `pawai_brain/pawai_brain/nodes/skill_policy_gate.py`（allowlist 收斂到單一來源）
- 改 `pawai_brain/pawai_brain/capability/registry.py`（gate ON 時 `_skill_entry` 把 health 當第 3 引數傳給 `compute_effective_status`；目前 registry.py:81 是 2-arg default-OFF）
- 新增 `pawai_brain/test/test_health_loader.py`

### 資料／API 契約
- **快照契約 = `pawai_brain/test/fixtures/baseline_snapshot.example.json`**（已讀，欄位與 `CapabilityHealth` 一一對應）：top-level `run_trusted` + `capabilities{cap_id:{capability_id, grade, claim_level, risk_role, dependency_role, brain_allowed, failure_reason?}}`。
- `CapabilityHealth` 既有定義（effective_status.py:27-34）：`grade / claim_level / dependency_role / risk_role / brain_allowed`，欄位 1:1 map，**不可改這個 dataclass**。
- **FAIL-CLOSED loader**：檔案不存在 / 不可讀 / JSON 壞 / schema invalid（schema 在 `.claude/schemas/baseline_snapshot.schema.json`，`jsonschema` 是 CI dep）/ `run_trusted==False` → 回傳「對每個 capability 都 yield `insufficient_data`」的 loader，**不得** try/except:pass 成空 dict（空 = 無意見 = 放行，禁止）。
- **skill→capability_id 對照**（明確、小表）：`wave_hello→gesture.wave`；`sit_along/stand/wiggle/stretch→nav.short_move`；`show_status/self_introduce/careful_remind→content`（content 類非 motion，passthrough）。**未對照到的 motion skill → gate ON 時 fail-closed block**，不得 passthrough。
- **IE 第二道 gate 位置**（brain_node.py `_on_chat_candidate`）：插在 allowlist 檢查（line 505）與 cooldown（line 515）之間。**必須同時 gate confirm 分支（line 541）與 trace_only 分支（line 563）**，不能只 gate execute（line 527）——否則 degraded motion skill 會被排進 OK-confirm 後執行。被 block 時用既有 `_emit_trace(stage="skill_gate", status="blocked", detail=reason)`（_emit_trace 簽名見 brain_node.py:886，kwargs-only）後 return。
- **allowlist 收斂**：`brain_node.py:574-584` 與 `skill_policy_gate.py:19-29` 的 `LLM_PROPOSABLE_SKILLS` 重複，收斂成單一來源；parity 由 `test_skill_policy_gate.py` 保護，須維持綠。
- **ROS param（default-OFF）**：`capability_gate_enabled`（bool，default `False`）+ `baseline_snapshot_path`（str，default `""`）。OFF = 不 load、不接 health、`compute_effective_status` 維持 2-arg 行為。

### 驗收（WSL，binary）
```bash
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/test_capability_health_gate.py -q   # 20 passed
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/ -q                                  # 338 passed（gate OFF 不得退）
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/ -q                        # 221 passed（gate OFF 不得退）
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/test_skill_policy_gate.py -q          # allowlist parity 綠
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai_brain/test/test_health_loader.py -q             # 新測試全綠
```
新測試 `test_health_loader.py` 必須涵蓋（binary 斷言）：
- loader 讀 `fixtures/baseline_snapshot.example.json` → 對應 capability 的 `CapabilityHealth` 欄位正確。
- 檔案不存在 / `run_trusted=False` / JSON 壞 → **每個 capability 都回 `insufficient_data`**（不是空）。
- skill→capability map：`wave_hello`→`gesture.wave`、`sit_along`→`nav.short_move`、未對照 motion skill → fail-closed。
- gate ON + 把某 motion skill 對應到 fail/insufficient capability → IE 端產生 `skill_gate/blocked` trace（可用 IE unit test 斷言 `_emit_trace` 被以 status="blocked" 呼叫）。

### 誠實/scope 護欄
- `capability_gate_enabled` **預設 False**，OFF path 必須 byte-identical（既有 338+221 測試是這條的守門員）。
- **不得**把 `capability_gate_enabled=True` 寫進任何 launch / demo / tmux 腳本，**不得**改 default。啟用需 Roy 授權。
- gate 只在 IE / brain pure-function 層，**不在 LLM prompt 層**做（North Star §9）。
- loader 不得 fail-open；任何不確定都退 `insufficient_data`。

### 不做（scope guard）
- 不改 `_grade_gate` / `CapabilityHealth` 數學（#85 v0.2 已凍結）。
- 不真的去跑或產生 baseline 快照（那是 HITL，需 Jetson）。
- 不接 Studio UI（那是工單 1）。
- 不啟用 enforcement、不接真實 motion 觸發。

---

## 工單 3 — #80 mic_stop 訊號接線（手動斷句 → `/event/mic_boundary`）

### 目標
讓「Studio 按停止錄音」能立即發出手動斷句訊號，使 on-Jetson `stt_intent_node` 不必等 energy VAD timeout 就 finalize。新增 `/event/mic_boundary` topic：frontend stop → gateway WS handler → 發 `/event/mic_boundary` → `stt_intent_node` 訂閱 → finalize + 釋放 echo gate。約 4 檔、10–15 行核心邏輯。

> ⚠️ 此工單動到語音主線。**只能在 demo 停掉後（`bash scripts/clean_full_demo.sh`）部署到 Jetson**——但部署/驗證是 Roy 的事，Codex 只寫 code 並讓 WSL 端編譯/測試過。
>
> ⚠️ 架構誠實提醒（已在 source 確認，務必讀懂再寫）：Studio 現行語音走 gateway `/ws/speech`（studio_gateway.py:742，前端送**整段 audio bytes** → gateway 端 cloud ASR），這與 on-Jetson `stt_intent_node` 的 energy_vad mic 路徑是**兩條不同管線**。mic_stop 的意義是給「on-Jetson stt mic 路徑 + 手動斷句」用的；不要把 `/ws/speech` 的整段上傳改造成串流。本工單只新增一條獨立的 `mic_stop` 控制訊號，不重構現有 `/ws/speech` 整段上傳流程。

### 要動的檔案
- `pawai-studio/frontend/hooks/use-audio-recorder.ts`：`stopRecording()`（line 239）在 `recorder.stop()` 後，透過 WS 送一筆 `{"type":"mic_stop", ...}` 控制訊息
- `pawai-studio/gateway/studio_gateway.py`：新增 WS `mic_stop` handler；`GatewayNode` 新增 `mic_boundary_pub = create_publisher(String, "/event/mic_boundary", QOS_EVENT)`（mirror speech_pub at line 174）；收到 mic_stop 即 publish
- `speech_processor/speech_processor/stt_intent_node.py`：新增 `create_subscription(String, "/event/mic_boundary", self._on_mic_boundary, 10)`（mirror line 387-401 既有訂閱）；callback 觸發 finalize 當前錄音 + 釋放 echo gate
- `scripts/start_full_demo_tmux.sh`：stt_intent_node block 加 `-p energy_vad.enabled:=False`（目前未傳 → 預設 True，stt_intent_node.py:517）

### 資料／API 契約
- WS mic_stop 訊息（前端 → gateway）：`{"type":"mic_stop","session_id":<str optional>,"ts":<float>}`。
- ROS topic `/event/mic_boundary`（gateway → stt）：`std_msgs/String`，payload JSON `{"event":"mic_stop","ts":<float>,"session_id":<str>}`。**此 topic 目前在全 source 為 0 引用（只存在 docs/plans），是全新增**。
- `stt_intent_node._on_mic_boundary`：收到後立即結束當前 capture window 並送 ASR、釋放 echo gate（既有 echo gate 變數 `_tts_playing`/`_tts_gate_open_time` 在 stt_intent_node.py:395-396）。
- 注意：mic_stop 接線後，e2e latency 才可能由手動斷句起算；**在 mic_stop 接好且 `energy_vad.enabled:=False` 前，baseline 量到的是 VAD-era latency**（從 speech_start_ts 起算，observer.py:219-222）。

### 驗收（WSL，binary）
```bash
# Python 編譯（4 個 .py 都要過）
cd /home/roy422/newLife/elder_and_dog && python3 -m py_compile speech_processor/speech_processor/stt_intent_node.py pawai-studio/gateway/studio_gateway.py
# 語音模組單元測試不得退
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest speech_processor/test/ -q
# 前端 lint+build（recorder 改動）
cd /home/roy422/newLife/elder_and_dog/pawai-studio/frontend && npm ci && npm run lint && npm run build
# grep 證明 topic 已接（3 端都要出現 /event/mic_boundary）
cd /home/roy422/newLife/elder_and_dog && grep -rn "/event/mic_boundary" speech_processor/speech_processor/stt_intent_node.py pawai-studio/gateway/studio_gateway.py
cd /home/roy422/newLife/elder_and_dog && grep -n "mic_stop" pawai-studio/frontend/hooks/use-audio-recorder.ts
cd /home/roy422/newLife/elder_and_dog && grep -n "energy_vad.enabled:=False" scripts/start_full_demo_tmux.sh
```
- 全部 exit 0、grep 三端都命中 = 過。
- （Jetson runtime 驗證屬 Roy，非本工單驗收）：部署後 `ros2 topic echo /event/mic_boundary`，按 Studio 停止 → 訊息立即出現、無 VAD timeout。

### 誠實/scope 護欄
- report 不得宣稱 "metric v2 (mic_stop 起算)" 或 "快 2 秒"，除非 mic_stop 已部署且 observer 真的改吃 mic_stop_ts。當前接線只是「讓 mic_stop 訊號存在並能 finalize」，latency 仍可能是 VAD-era，誠實標示為 OLD metric。
- 若之後 e2e_median fail `≤3.5s`，那是 as-is-with-VAD 的誠實結果，不是 regression。
- 不得在本工單就把 latency 改成 dual-record（mic_stop_ts / e2e_latency_ms_old 拆分）——那要等 observer 真的能拿到 mic_stop_ts（屬後續，不在此 scope）。

### 不做（scope guard）
- 不重構 `/ws/speech` 整段上傳為串流。
- 不改 cloud ASR / intent classifier。
- 不在本工單部署到 Jetson（部署需先停 demo，是 Roy 的步驟）。
- 不改 `voice_csv_to_jsonl.py` 的 latency 記錄格式。

---

## 工單 4 — `schema_validator_unavailable` fail-closed 修正（readiness schema 驗證）

### 目標
修掉 `benchmarks/core/readiness.py` 的潛在 fail-OPEN：當 `import jsonschema` 失敗時，現行碼回 `schema_validator_unavailable:<Exc>`（verdict 正確 fail-closed），但 schema 驗證本身被**靜默跳過**——malformed 快照在沒有 jsonschema 時會「通過」schema 檢查。把 jsonschema 釘進 runtime deps（讓 import 在 readiness 環境永不失敗），並補測試鎖住 fail-closed 行為。

### 要動的檔案
- `benchmarks/core/readiness.py`（`_schema_error`，line 87-101；行為不必大改，重點是把 import 失敗變成不可能 + 補測試覆蓋）
- 把 `jsonschema` 加進 pawai/benchmarks runtime 依賴宣告（找對應 `pyproject.toml` / `requirements*.txt` / `setup.py` 的 install_requires；以 repo 內真實存在的依賴宣告檔為準，**不要新建**慣例外的檔）
- 新增/擴充 `benchmarks/test/test_readiness.py`：monkeypatch 模擬 `import jsonschema` 失敗，斷言 verdict 為 not_ready 且 reason 含 `schema_validator_unavailable`

### 資料／API 契約
- `_schema_error(snapshot, schema)` 回傳 `str | None`：
  - import 失敗 → `"schema_validator_unavailable:<ExcClass>"`（保留 fail-closed）。
  - schema 不符 → `"schema_invalid:<path>:<msg>"`（既有）。
  - 通過 → `None`。
- reason 一旦非 None 即進 `reasons` list → `evaluate_readiness` verdict = `not_ready`（fail-closed，**不可**改成 warning 或放行）。
- schema 檔：`.claude/schemas/baseline_snapshot.schema.json`（已存在）。

### 驗收（WSL，binary）
```bash
# jsonschema 在 readiness 環境可 import（系統 + venv 兩個都要）
cd /home/roy422/newLife/elder_and_dog && python3 -c "import jsonschema; print('sys', jsonschema.__version__)"
/home/roy422/.venv/bin/python -c "import jsonschema; print('venv', jsonschema.__version__)"
# readiness 測試（含新 monkeypatch ImportError 案例）全綠
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest benchmarks/test/test_readiness.py -q
# benchmarks 全套不得退
cd /home/roy422/newLife/elder_and_dog && python3 -m pytest benchmarks/test/ -q
# 對 frozen 6/3 快照跑真 readiness CLI，first reason 應為 sha 相關，不得是 schema_validator_unavailable
cd /home/roy422/newLife/elder_and_dog && PAWAI_SCOREBOARD_PATH=artifacts/baseline/frozen/2026-06-03/baseline_snapshot.json /home/roy422/.venv/bin/pawai readiness --json
```
- 新測試斷言（binary）：patch `jsonschema` import 失敗時，`_schema_error` 回傳含 `schema_validator_unavailable` 的字串，且 `evaluate_readiness` verdict == not_ready。
- 依賴宣告檔出現 `jsonschema`。
- 上述全 exit 0 = 過。

### 誠實/scope 護欄
- 行為必須維持 **fail-closed**：缺 validator 時 verdict 不可變成 ready，也不可變成只是 warning。
- 不可為了讓測試過就把 `schema_validator_unavailable` 降級成 pass-through。
- 修的是「import 不該失敗 + 測試鎖住 fail-closed」，不是改變 readiness 的判定語意。

### 不做（scope guard）
- 不改 `_evaluate_sha` / version_mismatch / preflight 等其他 readiness reason 邏輯。
- 不碰 `build_scoreboard` 的快照產生流程。
- 不改 `.claude/schemas/baseline_snapshot.schema.json` 的 schema 內容（除非測試證明 schema 本身有 bug，那要另開工單）。
- 不處理 `deploy_sha_missing` 的 SSH-down fallback（那是另一個獨立 code gap，不在本工單）。

---

### 四工單交付順序建議（無硬相依，可並行；若要排序）
1. 工單 4（最小、純測試護欄）→ 2. 工單 1（前端，已驗證 toolchain 綠）→ 3. 工單 2（IE wiring，default-OFF）→ 4. 工單 3（語音主線，部署需 Roy 先停 demo）。

相關檔案（絕對路徑）：
- `/home/roy422/newLife/elder_and_dog/pawai-studio/gateway/studio_gateway.py`（`/api/scoreboard` line 600、`/ws/speech` line 742、publishers line 174）
- `/home/roy422/newLife/elder_and_dog/pawai-studio/backend/mock_server.py`（缺 `/api/scoreboard`）
- `/home/roy422/newLife/elder_and_dog/pawai_brain/pawai_brain/capability/effective_status.py`（`_grade_gate` line 42、2-arg default-OFF line 83）
- `/home/roy422/newLife/elder_and_dog/pawai_brain/pawai_brain/capability/registry.py`（2-arg gate call line 81）
- `/home/roy422/newLife/elder_and_dog/pawai_brain/test/fixtures/baseline_snapshot.example.json`（#120 loader 契約）
- `/home/roy422/newLife/elder_and_dog/interaction_executive/interaction_executive/brain_node.py`（gate 插入點 line 505-570、allowlist line 574、`_emit_trace` line 886）
- `/home/roy422/newLife/elder_and_dog/speech_processor/speech_processor/stt_intent_node.py`（訂閱 line 387、`energy_vad.enabled` default True line 517）
- `/home/roy422/newLife/elder_and_dog/pawai-studio/frontend/hooks/use-audio-recorder.ts`（`stopRecording` line 239）
- `/home/roy422/newLife/elder_and_dog/benchmarks/core/readiness.py`（`_schema_error` line 87-101）