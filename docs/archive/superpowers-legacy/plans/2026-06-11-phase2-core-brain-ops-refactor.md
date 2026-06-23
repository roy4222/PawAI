# 系統 Phase 2：Core Brain / Ops 重構（2A ISM 接入 + 2B Studio Evidence Center + 2C CLI v2 第二刀）

> **日期**：2026-06-11　**狀態**：pre-6/18 範圍 **IMPLEMENTED**（2026-06-12，PR #160/#161/#162）；post-6/18 範圍維持設計鎖定
> **執行收據**：[`docs/runbook/2026-06-12-phase2-pre618-checkpoint.md`](../../runbook/2026-06-12-phase2-pre618-checkpoint.md)——含 T2B-0 落實方式、三個對 plan 文字的工程修正（2A suppressed 側 evaluate() 取代 propose()／2C smoke 走 stream_remote／2C conftest real_repo + dotenv 中和）、留給 Roy 的真機項（T2A-4 soak 等）
> **上游文件**：
> - v2 統領文件：[`2026-06-11-pawai-system-refactor-v2-master.md`](2026-06-11-pawai-system-refactor-v2-master.md)（下稱「v2 master」；北極星全文 + 系統 Phase 1-5 編成）
> - 6/10 Master plan：[`2026-06-10-post-demo-refactor-master-plan.md`](2026-06-10-post-demo-refactor-master-plan.md)（D1-D6 拍板 + §7 ISM 凍結約束）
> - 2A 權威施工圖：[`2026-06-11-plan-ism-interaction-state-machine.md`](2026-06-11-plan-ism-interaction-state-machine.md)（下稱「ISM plan」）
> - 2B 上游交棒：[`2026-06-10-plan-e-brain-trace-v1.md`](2026-06-10-plan-e-brain-trace-v1.md)（下稱「Plan E」，已 merge PR #154）
> - 安全對照：[`../../security/2026-06-11-pawai-hardening-plan.md`](../../security/2026-06-11-pawai-hardening-plan.md)（下稱「hardening plan」）

## 命名消歧（必讀）

本套件有三套互不相干的編號，內文一律寫全名、禁止裸寫「Phase N」：

| 編號系統 | 指什麼 | 範圍 |
|---|---|---|
| **系統重構 Phase 1-5** | 本 v2 套件的大階段（本文件＝系統 Phase 2） | CI → Core Brain/Ops → Vision → Nav/安全 → 收口 |
| **ISM Phase 0-3** | `interaction_state.py` 狀態機自己的實作階段（ISM plan §5-§8） | Phase 0 純核心（已實作 PR #159）→ Phase 1 shadow → Phase 2 staged enable（2a-2g）→ Phase 3 權威化 |
| **安全 hardening P0-P3** | hardening plan 的修補優先級 | P0 gateway/foxglove → P1 DDS/driver/nav → P2 應用層 fail-closed → P3 隱私/CI |

> **北極星（一句引用，出自 v2 master）**：把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台——Perception Nodes → Perception Router → Interaction State Machine → Policy + Safety Layer → Skill Executor → Trace + Evidence，三支撐＝PawAI CLI v2 / PawAI Studio v2 / pawai_contracts。

---

## Goal

系統 Phase 2 把「Brain 決策可觀測、證據可落盤可匯出、操作可一鍵驗證」三件事接起來：

- **2A Brain ISM 接入**：ISM Phase 1 shadow——`brain_node.py` 實例化已 merge 的 ROS-free 狀態機（ISM Phase 0，PR #159），餵真實事件、發 `STATE_TRANSITION`/`CANDIDATE` shadow trace，與 legacy 裁決並排比對，**不依其裁決行動**。
- **2B Studio Evidence Center first slice**：Plan E 的 `/brain/trace` 從「live 可見」升級到「gateway JSONL 落盤 + export endpoint + 前端 suppressed-reason viewer」。
- **2C CLI v2 第二刀**：`pawai smoke brain` + `pawai evidence pull` + structured error messages，全部是包既有腳本 / rsync 的零 runtime 行為工具。

**硬規則（6/18 期末發表前）**：6/18 前**只做 ISM Phase 1 shadow + Evidence Center first slice（外加零 runtime 行為的 CLI 工具）**，**不做 ISM staged enable、不改現有 Brain runtime 行為**。shadow wiring 雖然會動 `brain_node.py`，但是 additive 且 `ism_shadow_enabled` 參數預設 False＝emit 行為 byte-identical，屬零行為變更；`ism_enabled`（ISM staged enable 總開關）**整個 6/18 前不存在或不翻**。

---

## Scope

| 主線 | Create | Modify |
|---|---|---|
| 2A | `interaction_executive/test/test_ism_shadow_parity.py` | `pawai_contracts/pawai_contracts/trace_schema.py`（+`TraceKind.STATE_TRANSITION`，additive）、`pawai_contracts/test/test_trace_schema.py`、`interaction_executive/interaction_executive/brain_node.py`（shadow wiring，flag 預設 off）、`.github/workflows/ros_build.yaml`（**僅當**抽出 ROS-free 純測檔時手動加入 Invocation 3 逐檔清單；parity 測試本體不進 CI，見 Tests 章） |
| 2B | `pawai-studio/gateway/trace_store.py` + 對應單測 | `pawai-studio/gateway/studio_gateway.py`（落盤掛載 + export endpoint）、`pawai-studio/frontend/hooks/use-event-stream.ts`、`pawai-studio/frontend/stores/state-store.ts`、`pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx` |
| 2C | `tools/pawai_cli/pawai_cli/evidence.py`（若邏輯較厚）+ CLI 測試、`tools/pawai_cli/tests/conftest.py`（隔離前置，現況 tests/ 無此檔＝新建） | `tools/pawai_cli/pawai_cli/main.py`（`smoke`/`evidence` 命令） |

post-6/18 延伸（設計鎖定、本 plan 排程但不展開逐行 TDD）：ISM staged enable 2a-2g + ISM Phase 3 權威化 + source trust 修法（見 Tasks 2A 後段）；2B 的三件延後 Studio 能力——decision timeline（session timeline 完整版）、session 報告匯出、annotated evidence clip——落點在 2B post-6/18 段（見 Tasks 2B 後段）。

## Forbidden scope

- **6/18 前不做 ISM staged enable**：不引入/不翻 `ism_enabled`，不替換任何 legacy gate，19 個 `_suppressed` 早退一行不刪（刪碼統一歸系統 Phase 5 T5B-3、硬依賴 G7；ISM Phase 3 只做翻 default + legacy 路徑停用，不刪碼）。
- **不改任何 Brain runtime 行為**：shadow 的 `Decision` 不得影響任何 emit/return；trace 永遠 additive-only（觀測類與政策類永不同 PR）。
- **demo 凍結檔案不碰**：`executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/`（至 6/18，除 Roy 明示授權）。
- 2B 不做：Plan E 表外 6 處未插樁 suppression（gesture confirm cooldown / stranger 內部 5 條件 / pose 路徑 / object whitelist / skill_request cooldown / chat stale drop——trace v2 另案，追蹤位置＝Plan E「表外 gap（v2 候選）」清單）、annotated evidence clip / Supervision 對接（系統 Phase 3 的 W4 spike 完成後回流——落點見 2B post-6/18 段）、session timeline 完整版（落點同上）、`/brain/conversation_trace` 與 `/brain/trace` 整併（post-ISM，歸系統 Phase 5 的 5C 收尾）。mock_server 的 trace 模擬（STUDIO-4 route parity）列 optional follow-up，非 first slice。
- 2C 不做：`pawai smoke vision|object|nav|full`（無現成 smoke script，需新寫採集腳本——vision/object 的**採集 script 屬系統 Phase 3（其 V3-3 產出）、CLI wiring 屬系統 Phase 5 T5A-2**（歸屬切分依系統 Phase 3 plan 勘注）；nav 屬系統 Phase 4、full 屬系統 Phase 5 收口）；Typer/Rich 遷移（系統 Phase 5）。
- 安全行為變更不混入：hardening P2-1（source 不可自稱）與 hardening P2-2（SafetyLayer 不信 wire `priority_class`）都是行為變更＝post-6/18 獨立 commit/PR；gateway 端認證簽章與 S0 enforcement flip 屬系統 Phase 4。

## Inputs / prerequisite docs

| 前置 | 狀態 | 用途 |
|---|---|---|
| ISM Phase 0（`interaction_state.py` + 33 純測，PR #159） | merged | 2A shadow 直接實例化，不再動核心 |
| Plan E（`/brain/trace` schema + 發射 + gateway 橋接，PR #154） | merged | 2A trace 複用 `decision_id`/`_suppressed` 漏斗；2B 落盤的資料源 |
| Plan D（perception_router） | merged | candidate 來源（乾淨事件） |
| S0-2 gateway access-control（`auth.py`，env-gated 預設關） | merged | 2B `trace_store.py` 的 ROS-free pure-module 先例 + export auth 設計約束 |
| Roy D5 拍板（master plan） | 已拍板 | Evidence 邊界：schema=pawai_contracts、發射=Brain/IE、落盤=gateway、CLI 只讀，「不再發明第三套 trace」 |
| hardening plan P2-1/P2-2/P3-1 | 文件 | source trust 與 PII 邊界的對照 |

---

## Tasks

### 執行紀律（治理原則，繼承 master plan，全 task 適用）

main 永遠可部署；每刀小 PR + CI 綠 + 紅綠驗證才 merge；搬家與行為變更分開 PR；trace/觀測 additive-only；觀測類與政策類永不同 PR；Codex 串行實作 + Fable spec/review；硬體能力宣稱必過 HITL gate；demo snapshot 的 forbidden claims 對所有對外材料持續有效。

### 2A：Brain ISM 接入（pre-6/18 = ISM Phase 1 shadow only）

> 權威施工圖是 ISM plan §6（本節引用不複製）；以下摘要到可獨立讀懂的程度。

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T2A-1**（= ISM plan Task 1.1） | `pawai_contracts/trace_schema.py` additive 加 `TraceKind.STATE_TRANSITION = "state_transition"`（先寫測試：新值存在 + 既有 6 個 enum 值凍結不變；`CANDIDATE` Plan E 已預留） | Codex 實作 | contracts 單測紅→綠；既有 `test_verdict_and_kind_enums_frozen` 同步更新且 additive |
| **T2A-2**（= ISM plan Task 1.2） | `brain_node.py` shadow 接線：param `ism_shadow_enabled`（declare 預設 **False**）+ 新 `test_ism_shadow_parity.py`。接點明細見下方「shadow 接點規格」 | Codex 實作 | parity 測試：shadow **off**＝emit byte-identical、零新 publish；shadow **on**＝每事件多發 shadow trace（標 `shadow=true`）但 emit 仍 byte-identical |
| **T2A-3**（= ISM plan Task 1.3） | 6/9 黑洞重演測試：模擬 ALERT/EXECUTING 卡住時 cup/greet 進來 → 斷言 ISM 裁決為 `SUPPRESS`-with-trace（reason `gate:executing`/`gate:alert_active`），**非靜默 drop**；watchdog 逾時 → `ERROR_RECOVERY` → `IDLE` | Codex 實作 | 重演測試綠，併入 `test_ism_shadow_parity.py` |
| **T2A-4** | 真機 shadow 驗證 + soak：Jetson 開 shadow 跑一輪 demo，`ros2 topic echo /brain/trace | grep state_transition` 看 ISM 跟真實事件走的狀態軌跡；merge 後讓 shadow 在 **6/18 發表全程開著**收真實數據（這是 ISM Phase 2 staged enable 的數據源） | Roy HITL | trace 軌跡與 demo 動線對得上；無 callback 例外、無延遲回退 |

**shadow 接點規格（T2A-2 的 spec 邊界，Fable 撰寫 spec / Codex 照做）**：

- **ACCEPT 側收斂在 `_emit()`**（`brain_node.py:467`）：plan 被 emit 前把對應 `Candidate` 餵 `self._ism.propose()`，記 shadow verdict。
- **SUPPRESS 側收斂在 `_suppressed()`**（`brain_node.py:523`）：Plan E 已把 19 個 gate 早退統一進這個漏斗（已帶 gate/reason/decision_id），shadow 只需在漏斗內並排呼叫 `propose()`，不必回到 19 個呼叫點逐一插樁。
- **TransitionSignal 側**：`_on_skill_result()`（STARTED/terminal lifecycle）、`WorldState` 的 `/state/tts_playing`（TTS_ACK start/end）、`_tick_pending_confirm()` 的 `CONFIRMED`/`CANCELLED`、`_on_reset_context()`（operator reset）→ 各餵 `apply_signal()`。
- **watchdog tick 掛現有 10Hz timer**，不新增 timer。
- **`propose()` 必須在 `self._lock` 外呼叫**（Plan E 紀律：`_suppressed` 內部會取鎖，trace/裁決呼叫不得巢狀取鎖）。
- **shadow 呼叫永不拋例外（never-raises，比照 Plan E `_trace()` 紀律）**：所有 ISM shadow 呼叫（`propose()`/`apply_signal()`/watchdog tick）外層一律包 try/except，例外僅 log debug、**永不影響 emit/return**——真實事件 payload 出現 spec 外形狀時不得炸掉 brain callback。並加對應單測：mock `propose()` 拋例外時 emit 仍 byte-identical。
- **enum 撞名陷阱**：`interaction_state.Verdict`（ACCEPT/SUPPRESS/QUEUE/PREEMPT）與 `pawai_contracts.trace_schema.Verdict`（ACCEPTED/SUPPRESSED/BLOCKED）**同名不同 enum**，wiring 必須 alias import（如 `from interaction_state import Verdict as IsmVerdict`），禁止混用。
- **`ism_shadow_enabled` 必須 runtime 可切**（每次使用時讀，不可只在 `__init__` 讀一次——6/8 reactive_stop param 教訓）：T2A-4 真機開 shadow 走 `ros2 param set /brain_node ism_shadow_enabled true`，**不碰凍結中的 `start_full_demo_tmux.sh`**。

**2A post-6/18（設計鎖定，引用 ISM plan §7-§8，不在本 plan 展開逐行 TDD）**：

- **ISM staged enable**＝ISM plan §7 的 **2a-2g 七個 sub-phase**，每個獨立 PR + `ism_enabled` 子開關 + legacy fallback + 真機驗證，順序：2a demo_phase 等價切換 → 2b CONFIRM_PENDING 非黑洞 → 2c EXECUTING watchdog → 2d SPEAKING chokepoint → 2e ALERT/SAFETY 優先序 → 2f 自發社交 candidate 化 → 2g TTS utterance_id ack（跨 speech 模組，最後）。
- **ISM Phase 3 權威化**：`ism_enabled` 預設翻 True + legacy gate 路徑停用（**不刪碼**——19 個分散 `_suppressed` 早退死碼的刪除統一歸系統 Phase 5 T5B-3，以本項完成＝G7 為硬閘門）+ 文件同步（contract + brain 架構文件）。
- **紀律**：ISM plan 明文「ISM Phase 1 shadow 數據落地前不展開 staged enable 的逐行 TDD」。T2A-4 的 soak 數據是展開前提。

**source trust boundary（安全對照，行為變更全屬 post-6/18）**：

| 項目 | 對應 findings | 落地位置 | 時點 |
|---|---|---|---|
| 移除對 wire 自稱 `source` 的信任（`_STUDIO_BUTTON_BYPASS_CONFIRM`，`brain_node.py:1642`） | GAP1-01(HIGH) / LLM-02(HIGH) / GAP2-03(HIGH)；hardening P2-1 | ISM plan §3.3，於 staged enable **2b/2e** 落地 | post-6/18 |
| SafetyLayer 不信 wire `priority_class`、改由 `SKILL_REGISTRY` 重查 | LLM-01(HIGH)；hardening P2-2 | 獨立 commit，**不混入任何零行為 PR** | post-6/18 |
| gateway 端認證後簽章（nonce/HMAC） | hardening P0-1 延伸 | 系統 Phase 4（S0 enforcement flip） | post-6/18 |

pre-6/18 本 plan 對 source trust 只交付兩件事：**修法已寫進 ISM plan §3.3** + **T2A-3 重演測試**（裁決層的回歸網先立起來）。

### 2B：Studio Evidence Center first slice

> Roy D5 已拍板邊界：**schema=pawai_contracts、發射=Brain/IE、落盤=gateway、CLI 只讀**——「不再發明第三套 trace」。現況：gateway 對 `/brain/trace` 是純 bridge 零落盤（`studio_gateway.py` TOPIC_MAP `:113-115` 注解明寫 persistence 留給本 plan）；前端 `use-event-stream.ts` 的 brain case 沒有 trace 分支，suppressed reason 前端無結構化呈現。

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T2B-0**（決策 gate，**T2B-1 落盤動工前必須先決**） | ① **PII 欄位政策**（hardening P3-1 / SEC-03 / GW-07：trace 含人名/語音文字、且經 `/ws/events` 廣播）——遮蔽 / 保留 / 僅本機三選一。② **export endpoint 的 auth 形態**：S0-2 的 token 只擋非 GET method——export 若做成 `GET /api/trace/export`，auth-on 下 trace 內容仍公開可讀；選項＝做成 POST，或對 trace export 例外 token-gate | **Roy 決策** | 決策記錄寫回本文件附錄 + hardening plan 對應條目 |
| **T2B-1** | gateway 新純模組 `trace_store.py`（比照 `auth.py` 的 ROS-free pure-module 先例：env 設定路徑、可單測、不 import rclpy）。JSONL 落盤 `runtime/traces/{session_id}.jsonl`；retention 每檔 ~20MB、留 20 sessions。⚠ subscriber callback 在 ROS executor thread——寫檔走 buffered queue/lock，不得在 callback 內同步 I/O 阻塞 | Codex 實作 | 純模組單測（rotation/retention/queue flush）紅→綠；gateway 既有測試零修改全綠 |
| **T2B-2** | export endpoint（形態依 T2B-0 拍板；草案 `GET /api/trace/export?since=...`）：讀 `trace_store` 的 JSONL、依 `since` 過濾、串流回傳 | Codex 實作 | endpoint 測試（含 auth-on 情境）；`curl` 實測拉得回 JSONL |
| **T2B-3** | 前端 suppressed-reason viewer first slice：`hooks/use-event-stream.ts` brain case 加 `event_type === "trace"` 分支 + `stores/state-store.ts` 新 slice（比照 `conversationTraces` cap 50）+ 掛進 `components/chat/brain/skill-trace-content.tsx`（該元件被 DevPanel sheet 與 `/studio/dev` page 三處共用——改一處三處生效） | Codex 實作 | 前端單測（store slice + event 分流）；本機 Studio 起來看 suppressed reason 結構化呈現 |
| **T2B-4** | CLI 對接＝2C 的 `pawai evidence pull`（見 T2C-2）；CLI **只讀** JSONL，不寫不轉換 | （併 2C） | 同 T2C-2 |

**2B post-6/18（設計鎖定，不展開逐行 TDD；三項皆以 T2B-1 落盤 + T2B-2 export 為基座，各自獨立 task/PR）**：

- **decision timeline（session timeline 完整版）**：前端把 JSONL session 軌跡渲染成 timeline view（first slice 的 suppressed-reason viewer 之上疊加）。
- **session 報告匯出**：export endpoint 之上生成 session 摘要報告（含 suppress 漏斗統計）。
- **annotated evidence clip**：消費系統 Phase 3 W4 spike 的 offline MP4/JSONL 產物，回流 Evidence Center（W4 完成為前置）。

### 2C：CLI v2 第二刀

> 現況：CLI 是 click 框架、已有 `health brain|nav` 可仿（`main.py` `_LANE_HEALTHCHECK:789`）；無 smoke/evidence 命令。三條 task 全部零 runtime 行為（只包腳本/rsync）。

| Task | 內容 | 載體 | 驗證 |
|---|---|---|---|
| **T2C-0**（前置或同 PR） | 測試隔離：conftest 把 `PAWAI_REPO_ROOT` 指 `tmp_path`；**#150 教訓**——新測試必須全 mock `shell.stream`/`shell.run_remote`，否則本機 300s 假掛再現（`.env.local` 污染） | Codex 實作 | CLI 套件本機 <10s 全綠 |
| **T2C-1** | `pawai smoke brain`：仿 `health brain` pattern（`_build_demo_env()` + `JETSON_HOST` 注入 + `shell.stream`），包既有 `scripts/smoke_test_e2e.sh` / `scripts/_e2e_smoke_jetson.sh`；新 `_SMOKE_SCRIPTS` dict 仿 `_LANE_HEALTHCHECK` | Codex 實作 | mock 測試（argv/env 斷言）+ 真機跑一次綠（見 Jetson 章節） |
| **T2C-2** | `pawai evidence pull`：rsync 既有 pattern（`_do_rsync_and_build:548` 已示範 argv 組法）把 Jetson 端 `runtime/traces/*.jsonl` + artifacts 拉回本機 `artifacts/`（與 readiness 的 `DEFAULT_SNAPSHOT_REL = artifacts/baseline/baseline_snapshot.json` 銜接）；邏輯較厚就仿 `readiness.py` 開獨立 `evidence.py` 再 `cli.add_command` | Codex 實作 | mock 測試（rsync argv 斷言）+ 真機拉回第一批 JSONL |
| **T2C-3** | structured error messages：click 錯誤訊息含修復建議（如「SSH 不通 → 檢查 `pawai doctor` Network topology / Tailscale」）；先小步：smoke/evidence 兩命令做到位，不全 CLI 翻修 | Codex 實作 | 錯誤路徑測試（斷 SSH mock → 訊息含建議字串） |

---

## Tests / verification

**CI（fast-gate，Invocation 1-8，no-ROS2 環境）**：
- 既有 invocation 全綠。ISM Phase 0 純測 `test_interaction_state.py` **已在 Invocation 3（interaction_executive）的逐檔明列清單內**（commit d3eb520 接入），不另立 invocation。
- 新測試接入：contracts `test_trace_schema.py` 更新（Invocation 7）、gateway `trace_store` 純模組測試（比照 Invocation 8 `test_auth.py` 先例手動加入）、CLI 測試（Invocation 4 跑 `tools/pawai_cli/tests` 整目錄，自動涵蓋）。
- **`test_ism_shadow_parity.py` 不進 fast-gate**：parity 測試須實例化 BrainNode → import rclpy，而 fast-gate 是 no-ROS2 環境、Invocation 3 為逐檔明列且 rclpy 依賴測試明文「Excluded from CI, run locally instead」——定位為**本機 rclpy tier**，比照 Plan E `test_trace_emission.py` / `test_brain_rules.py`。若要 CI 覆蓋 shadow 裁決邏輯，把 ROS-free 的 Candidate→Decision 對映斷言抽成獨立純測檔、手動加入 Invocation 3 清單（對應 Scope 2A 的 ros_build.yaml 條件式條目）。

**本機（WSL）**：
- IE：`python3 -m pytest interaction_executive/test/ -q`（既有 276+ 全綠零修改 + 新 parity/重演測試）。
- contracts：`PYTHONPATH=pawai_contracts python3 -m pytest pawai_contracts/test/ -q`。
- gateway：`cd pawai-studio/gateway && python3 -m pytest -q`。
- 前端：store/hook 單測 + 本機 Studio mock 環境目視。
- CLI：套件測試全 mock、<10s。

**真機（Jetson + Go2）**：
- **shadow 開跑**（T2A-4）：`ros2 param set /brain_node ism_shadow_enabled true` → 跑一輪 demo 動線 → `ros2 topic echo /brain/trace` 看 `state_transition` 軌跡與事件對齊、emit 行為與 shadow off 無差。
- **evidence pull**（T2C-2 × T2B-1）：demo 跑完 → 本機 `pawai evidence pull` → 拉回第一批真實 `runtime/traces/*.jsonl`、行數 >0、JSON 可解析。
- **smoke brain**（T2C-1）：`pawai smoke brain` 綠（包 `smoke_test_e2e.sh` 5 輪）。

## Jetson / Go2 requirement

| 項目 | 需要硬體？ | 說明 |
|---|---|---|
| T2A-1/2/3、T2B-1/2/3、T2C-0/1/2/3 實作與單測 | 否 | WSL 可完成（純模組 + mock） |
| T2A-4 shadow 真機驗證 + 6/18 soak | **是**：Jetson + Go2 demo stack | 開 shadow 走 runtime param，不碰凍結腳本 |
| T2B 落盤/export 真機驗證、T2C-1/2 真機收尾 | **是**：Jetson（Go2 視 demo 動線而定） | demo lane 跑時順帶驗證，不需專屬場測 |

## Done criteria

**pre-6/18**：
1. ISM Phase 1 shadow merged：`ism_shadow_enabled` 預設 off 時 612+73 測試**零變動全綠**；on 時 emit 不變、多發 shadow trace。
2. T2A-4 真機 shadow 驗證過 + **soak 啟動**（6/18 發表全程開著收數據）。
3. gateway JSONL 落盤 + export endpoint + 前端 suppressed-reason viewer **可用**（T2B-0 兩個決策已拍板並落實）。
4. `pawai evidence pull` 拉回真實 JSONL；`pawai smoke brain` 綠。
5. 全程零 Brain runtime 行為變更（`ism_enabled` 不存在或不翻）。

**post-6/18**：
6. ISM staged enable 2a-2g 全綠（七個獨立 PR，各帶子開關 + legacy fallback + 真機驗證）。
7. ISM Phase 3 權威化（`ism_enabled` 預設翻 True + legacy 路徑停用（不刪碼）+ 文件同步）；19 個分散早退死碼的刪除歸系統 Phase 5 T5B-3（硬依賴 G7，非本 plan 交付）。
8. source trust 修法落地（hardening P2-1 經 ISM staged enable 2b/2e；hardening P2-2 獨立 commit）。

## Rollback / fallback

- **2A**：`ism_shadow_enabled` 預設 off＝rollback 是 no-op；異常時 `ros2 param set /brain_node ism_shadow_enabled false` 即回 byte-identical；整 PR revert 無消費者依賴。**6/18 發表 soak 同規**：發表期間任何異常（callback 例外/延遲回退）當場 `ros2 param set /brain_node ism_shadow_enabled false` 退出 soak；soak 開啟以 T2A-4 彩排（真機一輪 demo）驗證通過為前置——全程 soak 是本 plan 對 ISM plan Phase 1 驗收的加碼項，必須可隨時退。
- **2B**：`trace_store` 走 env 開關（比照 `auth.py` env-gated 預設行為），關掉＝回純 bridge；export endpoint / 前端 viewer 各自獨立 revert，不影響 Plan E 既有 live bridge。
- **2C**：`smoke`/`evidence` 是新增命令，獨立可 revert，不碰既有 deploy/demo/health 路徑。
- **基線**：baseline tag `post-demo-refactor-baseline-2026-06-10`（=`b1f0bc4`）永遠是退守點。

## 6/18 freeze constraint

- **硬規則（與 Goal 同文重申）**：6/18 前只做 ISM Phase 1 shadow + Evidence Center first slice（外加零 runtime 行為的 CLI 工具），**不做 ISM staged enable，不改現有 Brain runtime 行為**。shadow wiring 動 `brain_node.py` 但 additive 且 `ism_shadow_enabled` 預設 False＝emit byte-identical，屬零行為變更；`ism_enabled` 整個 6/18 前**不存在或不翻**。
- **凍結檔案**：`executive.yaml`、`scripts/start_full_demo_tmux.sh`、`.claude/skills/` 除 Roy 明示授權外禁改至 6/18——T2A-4 開 shadow 一律走 runtime `ros2 param set`，不修改凍結腳本。
- 行為變更全數排 post-6/18：ISM staged enable 2a-2g、ISM Phase 3 權威化、hardening P2-1/P2-2、gateway 簽章（系統 Phase 4）。
- demo snapshot 的 forbidden claims 對所有對外材料持續有效；6/18 發表期間 shadow soak 屬觀測，不得宣稱「狀態機已上線」。

---

## 附錄：T2B-0 決策記錄（2026-06-12 已拍板並落實）

| 決策 | 選項 | Roy 拍板 | 日期 |
|---|---|---|---|
| trace PII 欄位政策 | 遮蔽 / 保留 / 僅本機 | **保守預設（混合）**：safe summary 可顯示；name/transcript/image path/full text 預設 private。落實＝磁碟 JSONL 存完整（僅本機）、離機路徑（WS 廣播 + 預設 export）一律過 `redact_trace_event()` | 2026-06-12（AFK 指令） |
| export auth 形態 | POST / GET+例外 token-gate | **GET＋例外 token-gate**（「export 即使 GET 也要 auth」）：`auth.export_access()`——auth-on 時 GET 無 token → 401；`redact=0` 完整匯出在 token 系統關閉時一律 403；default-off 下 redacted export 開放（S0-2 byte-identical 原則） | 2026-06-12（AFK 指令） |
