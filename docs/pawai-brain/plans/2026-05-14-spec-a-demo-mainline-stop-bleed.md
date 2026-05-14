# Spec A — Demo 主線止血 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec**：[docs/pawai-brain/specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md](../specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md)（commit `a1ebdd2`）

**Goal**：在沒有 Jetson / Go2 條件下，把下週 demo 的 6 個結構性風險（Brain bring-up / persona / TTS 單出口 / gesture gate / pose Brain-side state / preflight 工具）以 4 個 PR（1 → 2A → 2B → 3）依序合入，不回退今日 `b05205d`~`caef6b5` 之 lock/orphan/env/CRLF 修補。

**Architecture**：靜態修補（persona / package / docs）先行；CLI preflight 與 Executive runtime guard 次之；行為變更（gesture gate、pose 模擬）最後。所有 ROS-runtime check 透過 pawai_cli 既有 SSH wrapper 在 Jetson 執行；本機僅檢 repo 文件與 persona scan。Preflight 失敗時 pre-start 直接 exit、post-start 走 `release_if_owned + cleanup + exit`，禁裸 `Lock.release()`。

**Tech Stack**：Python 3.10+（ROS 2 Humble + pawai_cli）、pytest、rclpy、click、ament_python、langgraph、langchain-core。Repo 用 uv 管 Python deps（`uv pip install`）。

**Base**：`main` @ commit `a1ebdd2`（spec wording cleanup 後 HEAD）。

---

## File Structure

### Create

| 檔案 | 責任 | PR |
|------|------|-----|
| `tools/pawai_cli/pawai_cli/preflight.py` | CheckResult 資料型別、10 條 mechanical checks、6 條 semantic scripts、runner、輸出 | 2A / 2B |
| `tools/pawai_cli/tests/test_preflight.py` | preflight mechanical unit test（mock SSH / subprocess / ROS graph） | 2A |
| `tools/pawai_cli/tests/test_demo_start_hook.py` | `demo start` 雙階段 hook 順序與 `release_if_owned` 行為 | 2A |
| `tools/pawai_cli/tests/test_persona_scoped_scan.py` | persona scoped scan（STATUS_NOTE 不誤殺、claim pattern 抓得到） | 2A |
| `tools/pawai_cli/tests/test_semantic_dryrun.py` | semantic 6 scripts（mock LLM trace）+ pose injection isolation | 2B |
| `interaction_executive/test/test_tts_guard_timer.py` | Executive runtime TTS guard timer（5s polling + 60s 去重 + trace warning） | 2A |
| `interaction_executive/test/test_gesture_conversation_gate.py` | thumbs_up / peace 在 tts_playing 或 chat_active 不進 pending_confirm | 3 |
| `pawai_brain/test/test_pose_brain_simulation.py` | Pose cache dict 7 case，含「t=20 不重發」痛點 | 3 |

### Modify

| 檔案 | 改動 | PR |
|------|------|-----|
| `pawai_brain/package.xml` | 補可用 rosdep key `python3-requests` | 1 |
| `requirements-jetson.txt`（repo 根，**非** `pawai_brain/`）| 補 `langgraph` / `langchain-core` 含版本 pin；確認 `requests` 已列 | 1 |
| `docs/pawai-brain/README.md:18` | 主模型改 `openai/gpt-5.4-mini`，fallback 列 `google/gemini-3-flash-preview` | 1 |
| `docs/runbook/README.md` | Jetson bring-up 必跑 `uv pip install -r requirements-jetson.txt` | 1 |
| `docs/pawai_cli/team-onboarding.md` | 加 demo 合法 chain；禁用 legacy launch | 1 |
| `pawai_brain/personas/v1/CAPABILITIES.md` | 行 22 / 26 / 27 砍誇大字、行 32 / 55 改寫硬數字、結尾新增 STATUS_NOTE | 1 |
| `pawai_brain/personas/v1/EXAMPLES.md` | 補 2 條降級對話範例 | 1 |
| `tools/pawai_cli/pawai_cli/main.py` | 新增 click 子命令 `demo preflight` + flags；`demo start` 內部呼叫 pre-start / post-start hook | 2A / 2B |
| `interaction_executive/interaction_executive/brain_node.py` | 行 574 frozenset 加 `thumbs_up` / `peace`；新增 TTS guard timer | 2A / 3 |
| `pawai_brain/pawai_brain/conversation_graph_node.py` | `_on_pose` 改 dict cache；`_format_current_pose` 三態；`pose_stale_threshold_s` ROS param | 3 |
| `pawai_brain/pawai_brain/nodes/world_state_builder.py` | `set_pose_provider` 兼容 tuple+dict；prompt 注入呼叫 `_format_current_pose` | 3 |
| `scripts/start_full_demo_tmux.sh` | `ROS_SETUP` 加 `.env` propagation 共用片段；停用 `event_action_bridge` 啟動 | 2A |
| `.gitignore` | 確認 `runtime/` 已忽略；若否加 `runtime/`（PR 2B） | 2B |

### Out of scope（不動）

- `pawai_brain/pawai_brain/graph.py` / `llm_client.py` / `rule_fallback.py`
- `interaction_executive/interaction_executive/skill_contract.py`
- `pawai_brain/pawai_brain/nodes/skill_policy_gate.py`（`LLM_PROPOSABLE_SKILLS`）
- `vision_perception/` 任何 code
- `event_action_bridge.py`（只從 start script 移除啟動，code 不動）
- `interaction_contract.md`（pose 走 Brain-side simulation，不動 contract）

---

# Day 0：Recovery + Hardware Bring-up Gate

> **MUST RUN BEFORE ANY PR EXECUTION.** 不過此關不准開任何 PR group goal。

**背景**：執行 Spec A 前一日嘗試平行跑 PR1/PR2A/PR2B/PR3 四個 goal，在同一個 workspace 內互相 checkout/stash，導致 branch / stash 漂移。明日恢復 Go2 / Jetson 在手，但第一步**不是繼續 goal**，是收拾狀態 + 用真機驗 PR1 假設。

## D0.1：Workspace 狀態盤點

- [ ] **Step 1：停所有正在跑的 goal / subagent / terminal**

確認所有 Spec A 相關背景 process 都已停。`ps aux | grep -E "claude|goal|subagent" | grep -v grep` 應為空（或只有當前 session）。

- [ ] **Step 2：盤點 worktree / branch / stash 狀態**

在主 workspace `/home/roy422/newLife/elder_and_dog`：

```bash
cd /home/roy422/newLife/elder_and_dog

# 1. 哪些 worktree 存在
git worktree list

# 2. 哪些 spec-a branch 存在 + 各 HEAD
git branch --list 'spec-a/*' --verbose

# 3. 哪些 stash 存在
git stash list

# 4. 當前 HEAD 與 main 差異
git log --oneline main..HEAD 2>/dev/null | head -10
git log --oneline HEAD..main 2>/dev/null | head -10

# 5. 是否有未追蹤 / 修改檔
git status --short
```

把上述輸出貼進 `runtime/preflight/day0-audit-<timestamp>.md`（runtime/ 已 gitignored）。

- [ ] **Step 3：辨識「哪個 branch 真的有哪個 PR 群的改動」**

對每個 `spec-a/*` branch 跑：

```bash
for B in $(git branch --list 'spec-a/*' | tr -d '* '); do
  echo "=== $B ==="
  git log --oneline main..$B 2>/dev/null
done
```

對每個 stash 跑：

```bash
git stash list | while read entry; do
  idx=$(echo "$entry" | grep -oE '^stash@\{[0-9]+\}')
  echo "=== $idx ==="
  git stash show -p "$idx" | head -20
done
```

辨識：
- 哪些檔案屬 PR1（package.xml / requirements / persona / docs）
- 哪些屬 PR2A（preflight.py / brain_node.py guard / start_full_demo_tmux）
- 哪些屬 PR2B（semantic dry-run additions）
- 哪些屬 PR3（gesture frozenset / pose dict / world_state_builder）
- 哪些是 collision（同檔被多個 goal 改）

若 collision 出現：以 PR 群順序裁決（PR1 最先、PR3 最後；後者繼承前者結果），不是時間先後。

## D0.2：Worktree 隔離（執行前硬性條件）

從此刻起，**主 workspace `/home/roy422/newLife/elder_and_dog` 禁止用於跑 goal / subagent**。每個 PR 群有獨立 worktree。

- [ ] **Step 1：建 4 個 worktree（每 PR 群一個）**

```bash
cd /home/roy422/newLife/elder_and_dog

# PR1
git worktree add ../elder_and_dog-pr1 spec-a/pr1-static-fixes 2>/dev/null || \
  git worktree add -b spec-a/pr1-static-fixes ../elder_and_dog-pr1 main

# PR2A
git worktree add ../elder_and_dog-pr2a -b spec-a/pr2a-mechanical-guard \
  spec-a/pr1-static-fixes

# PR2B
git worktree add ../elder_and_dog-pr2b -b spec-a/pr2b-semantic-dryrun \
  spec-a/pr2a-mechanical-guard

# PR3
git worktree add ../elder_and_dog-pr3 -b spec-a/pr3-behavior-gate \
  spec-a/pr2b-semantic-dryrun

git worktree list
```

PR2A/2B/3 的 base branch 在 PR1 merge 前是 placeholder（尚不存在於 main）；先用 sibling branch 當 base，merge 鏈走完後再 rebase 到 main。

- [ ] **Step 2：把 stash 內 PR3 改動 apply 到 PR3 worktree**

從 D0.1 Step 3 辨識的 stash 內容，挑 PR3 相關 hunks：

```bash
cd ../elder_and_dog-pr3

# 對於每個 PR3 相關 stash：
git stash show -p stash@{N} -- \
  interaction_executive/interaction_executive/brain_node.py \
  pawai_brain/pawai_brain/conversation_graph_node.py \
  pawai_brain/pawai_brain/nodes/world_state_builder.py \
  pawai_brain/test/ \
  interaction_executive/test/ \
  | git apply --3way -

git status
```

衝突手動解。Apply 成功後**不要立刻 drop stash**，先用 `git stash list` 留 backup，到 PR3 merge 後再 `git stash drop stash@{N}`。

同樣方式處理 PR1 / PR2A / PR2B 漂移到 stash 的 hunks。

- [ ] **Step 3：禁止規則**

從此刻起 Spec A 執行期間：

```text
- 主 workspace /home/roy422/newLife/elder_and_dog 禁止用於跑 PR goal。
- 每個 PR group goal 必須在對應 ../elder_and_dog-pr<N> worktree 內跑。
- 禁止 git stash（除非明確指示且只在當前 worktree 內）。
- 禁止 git checkout 切換 branch（worktree 已固定 branch）。
- 禁止改動其他 PR 群檔案（PR1 不准動 preflight.py，PR2A 不准動 persona 等）。
- 若 HEAD 變動超出預期或 git status 出現非預期 untracked，停下回報。
```

## D0.3：PR1 Clean-up（First Mergeable Group）

明日第一個 actionable 任務是把 PR1 整理乾淨並 merge 進 main。**所有後續 PR 都依賴 PR1 base**。

- [ ] **Step 1：在 PR1 worktree 內 review 改動**

```bash
cd ../elder_and_dog-pr1
git log --oneline main..HEAD
git diff main..HEAD --stat
```

對照 Task 1.2-1.10 清單，確認：
- `pawai_brain/package.xml` 有補 `python3-requests`
- `requirements-jetson.txt`（repo 根）含 `langgraph` / `langchain-core`
- `docs/pawai-brain/README.md:18` 主模型已改 `openai/gpt-5.4-mini`
- `docs/runbook/README.md` 有 Jetson bring-up `uv pip install` 段
- `docs/pawai_cli/team-onboarding.md` 有 demo 合法 chain
- `CAPABILITIES.md` 行 22/26/27/32/55 已收斂 + STATUS_NOTE
- `EXAMPLES.md` 補 2 條降級對話

- [ ] **Step 2：跑 Task 1.11 自驗 grep**

```bash
awk '/^## STATUS_NOTE/{exit} {print}' pawai_brain/personas/v1/CAPABILITIES.md > /tmp/persona-pre-status.txt
grep -nE "我會跟隨|會跟隨你|可以跟著|我會主動巡邏|會主動巡邏|我會靜音|進入靜音模式|我會監聽|進入監聽模式" /tmp/persona-pre-status.txt
grep -nE "我會跟著你|我可以跟著你|我會靠近你|我可以自己找你" pawai_brain/personas/v1/EXAMPLES.md
```

兩個 grep 都應該無輸出。若有違規，當場修。

- [ ] **Step 3：處理昨日 PR1 review 的 3 個 finding**

D0 執行者要查昨日 review 紀錄。若 review 已歸納成 task，照修；若未歸納，列出當前已知 PR1 issues 並逐項解決，commit 訊息標 `spec-a/pr1: review fix — <topic>`。

- [ ] **Step 4：push + 開 PR + 等 merge**

```bash
git push -u origin spec-a/pr1-static-fixes
# 走 Task 1.12 的 PR 開法
```

PR1 merge 進 main 後，**才能解鎖 PR2A 執行**。

## D0.4：Jetson Hardware Bring-up Gate

PR1 merge 後、PR2A 開跑前，必須驗 PR1 在 Jetson 上的假設成立。

- [ ] **Step 1：sync 最新 main 到 Jetson**

```bash
cd /home/roy422/newLife/elder_and_dog  # 主 workspace 用於 sync，不跑 goal
git checkout main
git pull --ff-only
~/sync once     # 或既有 deploy 流程
```

- [ ] **Step 2：Jetson 上裝 deps**

```bash
ssh jetson-nano
cd ~/elder_and_dog
git log --oneline -3  # 確認含 PR1 commits
uv pip install -r requirements-jetson.txt
python3 -c "import langgraph, langchain_core, requests, yaml; print('imports OK')"
```

`imports OK` 才算 gate pass。任何 import error → 回 PR1 補 requirements。

- [ ] **Step 3：Jetson 上 colcon build + 跑 conversation_graph_node 5 秒**

```bash
ssh jetson-nano
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
colcon build --packages-select pawai_brain interaction_executive
source install/setup.zsh
timeout 5 ros2 run pawai_brain conversation_graph_node 2>&1 | tail -20
```

期望：5 秒內無 ImportError / ROS 啟動錯誤。出現 RuleBrain 降級訊息可接受（OPENROUTER_KEY 可能還沒設）。

- [ ] **Step 4：Jetson 上驗 `.env` propagation 假設**

```bash
ssh jetson-nano
cd ~/elder_and_dog
cat scripts/start_full_demo_tmux.sh | grep -A2 "ROS_SETUP"
# 確認 set -a / source .env / set +a 共用片段已落地（這是 PR 2A 才做，
# D0.4 此步驟只 baseline 既有狀態；若已在 PR1 順帶改了也 OK）
```

D0.4 全 pass → 解鎖 PR2A 執行。

## D0.5：Goal Prompt 規範

從 PR2A 開始所有 goal / subagent dispatch 必須帶下列 prompt header：

```text
WORKTREE BOUNDARIES（強制）：

- 你的工作目錄是 /home/roy422/newLife/elder_and_dog-pr<N>
- 禁止 cd 出此目錄，禁止 checkout 其他 branch
- 禁止 git stash（除非任務明確要求）
- 禁止改動其他 PR 群檔案；當前 PR 允許動的檔案清單見 plan 對應「File Structure」
- 若發現 git HEAD 變動超出預期、或 git status 出現非預期 untracked，立即停下回報，不要自行恢復

當前 PR：spec-a/pr<N>-<topic>
Base branch：spec-a/pr<N-1> 或 main
任務範圍：plan 中 Task <X.Y> 至 <X.Z>
```

每個 goal 完成後 review 必須包含：
- `git log --oneline <base>..HEAD`：commit 數 vs plan 預期一致
- `git diff <base>..HEAD --stat`：動的檔在允許清單內
- `git status --short`：working tree clean
- `git stash list`：未增加新 stash

任一不符 → 該 PR rollback、不 merge。

## D0.6：硬體在手後的執行順序調整

PR1 / D0.4 完成後，PR2A / 2B / 3 的執行**改在真 Jetson 上做 post-start 驗證**：

| PR | Mock 範圍（dev 機）| 真機驗證（Jetson 在手）|
|----|-------------------|---------------------|
| 2A | 既有 mock SSH unit test | demo start hook 跑一輪真實 lifecycle；preflight 10 條全跑；TTS guard timer 真實 trigger 一次測試 |
| 2B | semantic mock unit test | `pawai demo preflight --semantic --reason day0-real` 跑 6 scripts，人工判讀；報告留 `runtime/preflight/` |
| 3 | gesture / pose unit test | 真實手勢 thumbs_up + chat_active → 不誤觸 wiggle；真實 pose sitting 20s 後問「我在幹嘛」→ 答「坐著」 |

**禁止**：
- 把現場閾值調參（gesture cooldown / pose stable vote / fallen threshold）塞回 Spec A
- 真機驗證若揭出 bug，分兩類：
  - **Spec A 本身錯**：修進對應 PR
  - **現場調參需求**：開新 issue 給 Spec C/D，**不**進 Spec A

D0.6 完成 → Spec A 驗收結束，spec / plan 進 archive。

---

# PR 群 1：靜態修補

**Branch**：`spec-a/pr1-static-fixes`
**Base**：`main` @ `a1ebdd2`
**估行數**：~180 行（純 markdown / xml / txt）
**驗收**：banned literal grep 自驗；現有 test suite 不退化

---

## Task 1.1：建立 PR 1 branch

- [ ] **Step 1：建 branch**

```bash
git checkout main
git pull --ff-only
git status  # 應顯示 working tree clean
git checkout -b spec-a/pr1-static-fixes
```

---

## Task 1.2：修 `pawai_brain/package.xml` 加可用 rosdep key

**Files：**
- Modify：`pawai_brain/package.xml`

- [ ] **Step 1：讀現況**

```bash
cat pawai_brain/package.xml
```

Expected：第 9-13 行為 5 個 `<exec_depend>`，無 `python3-requests`。

- [ ] **Step 2：插入 `python3-requests` exec_depend**

在 `<exec_depend>python3-yaml</exec_depend>` 之後、`<test_depend>` 之前加一行：

```xml
  <exec_depend>python3-yaml</exec_depend>
  <exec_depend>python3-requests</exec_depend>

  <test_depend>ament_copyright</test_depend>
```

不放假 rosdep key（`python3-langgraph` 等不存在），langgraph / langchain-core 走 `requirements-jetson.txt` + preflight import check。

- [ ] **Step 3：驗 xml well-formed**

```bash
python3 -c "import xml.etree.ElementTree as ET; ET.parse('pawai_brain/package.xml')"
```

Expected：無輸出（success）。

- [ ] **Step 4：commit**

```bash
git add pawai_brain/package.xml
git commit -m "spec-a/pr1: pawai_brain package.xml — 補 python3-requests exec_depend

langgraph / langchain-core 走 requirements-jetson.txt + preflight import
check，不放未驗證 rosdep key。"
```

---

## Task 1.3：補 `requirements-jetson.txt` 含 langgraph / langchain-core

**Files：**
- Modify：`requirements-jetson.txt`（repo 根，非 `pawai_brain/` 下）

- [ ] **Step 1：讀現況**

```bash
grep -nE "^(requests|langgraph|langchain)" requirements-jetson.txt
```

Expected：只有 `requests` 一行（其他缺）。

- [ ] **Step 2：在 `requests` 附近加 langgraph 與 langchain-core**

找到 `requests` 那行，後面（或同一塊 LLM stack 區）加：

```text
langgraph>=0.2.0,<0.5.0
langchain-core>=0.3.0,<0.4.0
```

版本下限對齊 Brain `graph.py` 既有 API；上限保守鎖 minor，避免無預警 breaking。

- [ ] **Step 3：驗 pip parser 接受**

```bash
python3 -m pip install --dry-run -r requirements-jetson.txt 2>&1 | head -5
```

Expected：dry-run 解析成功（不會真裝）；任何 syntax error 必須先修。

- [ ] **Step 4：commit**

```bash
git add requirements-jetson.txt
git commit -m "spec-a/pr1: requirements-jetson 補 langgraph + langchain-core

對齊 pawai_brain/pawai_brain/graph.py 既有 API；版本下限鎖 minor 上限
避免 silent breaking。preflight imports check 將強擋安裝缺失。"
```

---

## Task 1.4：修 `docs/pawai-brain/README.md:18` 主模型名稱

**Files：**
- Modify：`docs/pawai-brain/README.md`，line 18

- [ ] **Step 1：替換行 18**

原文：

```markdown
- **LLM provider chain** — OpenRouter 主線(Gemini 3 Flash / DeepSeek V4 Flash / Qwen3.6 Plus eval) → OpenRouter fallback → Ollama qwen2.5:1.5b → RuleBrain
```

改為：

```markdown
- **LLM provider chain** — OpenRouter 主線 `openai/gpt-5.4-mini`，fallback `google/gemini-3-flash-preview` → Ollama qwen2.5:1.5b → RuleBrain。以 `pawai_brain/pawai_brain/conversation_graph_node.py` 與 `launch/pawai_conversation_graph.launch.py` 為準
```

- [ ] **Step 2：驗 markdown 結構沒崩**

```bash
head -25 docs/pawai-brain/README.md
```

Expected：行 18 已改、其他行未動。

- [ ] **Step 3：commit**

```bash
git add docs/pawai-brain/README.md
git commit -m "spec-a/pr1: README — 主模型對齊 code

主線 openai/gpt-5.4-mini（不是 Gemini 3 Flash）；fallback gemini-3-flash-preview；
以 conversation_graph_node.py / launch params 為準。"
```

---

## Task 1.5：`docs/runbook/README.md` 加 Jetson bring-up 安裝指引

**Files：**
- Modify：`docs/runbook/README.md`

- [ ] **Step 1：grep 是否已有 Jetson bring-up 區塊**

```bash
grep -nE "Jetson|bring.?up|uv pip|requirements-jetson" docs/runbook/README.md | head -10
```

- [ ] **Step 2：在 Jetson bring-up 段（或檔末新增區塊）加入**

```markdown
## Jetson Brain Bring-up（Spec A）

Jetson 上首次部署或 `pawai_brain` 套件升級時必跑：

```bash
cd ~/elder_and_dog
uv pip install -r requirements-jetson.txt
```

此步驟確保 `langgraph` / `langchain-core` / `requests` 等 Brain runtime
deps 安裝；`pawai demo preflight --target jetson` 的 `imports` check 會
強制驗證。
```

若已有 bring-up 區塊，將上述命令插入相應位置。

- [ ] **Step 3：commit**

```bash
git add docs/runbook/README.md
git commit -m "spec-a/pr1: runbook 加 Jetson Brain deps 安裝指引

uv pip install -r requirements-jetson.txt；preflight imports check 強驗。"
```

---

## Task 1.6：`docs/pawai_cli/team-onboarding.md` 加 demo 合法 chain

**Files：**
- Modify：`docs/pawai_cli/team-onboarding.md`

- [ ] **Step 1：grep 既有 demo 啟動段**

```bash
grep -nE "demo start|legacy|llm_bridge|/tts|event_action" docs/pawai_cli/team-onboarding.md | head -10
```

- [ ] **Step 2：在合適位置（demo 啟動段附近）加新區塊**

```markdown
## Demo 主線唯一合法 chain（Spec A）

下週 demo 期間，唯一合法 demo 啟動入口：

```bash
pawai demo start    # 內部自動跑 pre-start / post-start mechanical preflight
```

唯一合法 ROS chain：

```
conversation_graph_node → /brain/chat_candidate
  → brain_node → /brain/proposal
  → interaction_executive_node → /tts
  → tts_node → /state/tts_playing
```

**禁用作 demo 啟動入口**：
- `scripts/start_full_demo_tmux.sh`（除非用於 dev debug，且不取 demo lock）
- `scripts/start_llm_e2e_tmux.sh`
- `scripts/run_speech_test.sh`

**Demo runtime 禁啟 node**（preflight `legacy_processes_not_running` 會擋）：
- `llm_bridge_node`
- `intent_tts_bridge_node`
- `event_action_bridge`
- `route_runner_node`

若手動啟動上述任一 legacy node，`pawai demo start` preflight 會 FAIL；
請先 `pawai demo stop` 或手動 kill 後重跑。
```

- [ ] **Step 3：commit**

```bash
git add docs/pawai_cli/team-onboarding.md
git commit -m "spec-a/pr1: team-onboarding 加 demo 唯一合法 chain + legacy 禁用清單"
```

---

## Task 1.7：`CAPABILITIES.md` 收斂行 22 / 26 / 27

**Files：**
- Modify：`pawai_brain/personas/v1/CAPABILITIES.md` lines 22, 26, 27

- [ ] **Step 1：讀現況**

```bash
sed -n '20,30p' pawai_brain/personas/v1/CAPABILITIES.md
```

確認行內容：
- L22 含「靜音模式」「監聽模式」「召喚跟隨」
- L26 含「主動巡邏」
- L27 含「跟隨、自主巡邏、自主尋物閉環」

- [ ] **Step 2：修行 22**

原文：

```markdown
| 手勢 | 6 種靜態：手掌(palm)→暫停 / 拳頭(fist)→靜音模式 / 食指(index)→監聽模式 / OK→確認 / 大拇指(thumb)→搖屁股 / 比 yeah(peace)→伸懶腰；揮手(wave)會打招呼 | 動態畫圈跳舞、勾手召喚跟隨 |
```

改為：

```markdown
| 手勢 | 4 種主推靜態：手掌(palm)→暫停 / OK→確認 / 大拇指(thumbs_up)→搖屁股（需 OK 確認） / 比 yeah(peace)→伸懶腰（需 OK 確認）；揮手(wave)可選打招呼 | 拳頭與食指特殊模式目前隱藏開發中；動態畫圈跳舞、勾手召喚跟隨皆未實裝 |
```

- [ ] **Step 3：修行 26**

原文：

```markdown
| 守護 | 陌生人會提醒、跌倒會喊名字 | 主動巡邏 |
```

改為：

```markdown
| 守護 | 陌生人偵測、跌倒偵測（demo 期保守處理，僅 trace） | （未實裝） |
```

- [ ] **Step 4：修行 27**

原文：

```markdown
| 移動 | 直線走 1 公尺、看到障礙會停 | 動態繞行、跟隨、自主巡邏、自主尋物閉環 |
```

改為：

```markdown
| 移動 | 短距移動為實驗性，需明確要求 | 動態繞行、自主尋物閉環皆未實裝 |
```

- [ ] **Step 5：commit**

```bash
git add pawai_brain/personas/v1/CAPABILITIES.md
git commit -m "spec-a/pr1: CAPABILITIES 砍 4 句誇大字（22/26/27）

靜音/監聽模式 → hidden，移到 STATUS_NOTE；主動巡邏/跟隨 → 未實裝；
動態手勢 → 未實裝。"
```

---

## Task 1.8：`CAPABILITIES.md` 修硬數字（行 32 / 55）

**Files：**
- Modify：`pawai_brain/personas/v1/CAPABILITIES.md` lines 32, 55

- [ ] **Step 1：讀現況**

```bash
sed -n '30,35p;53,57p' pawai_brain/personas/v1/CAPABILITIES.md
```

- [ ] **Step 2：修行 32**

原文：

```markdown
# 你的可用技能（只能從以下 17 個選一個，不可自編）
```

改為：

```markdown
# 你的可用技能（只能從以下清單選一個，不可自編）
```

- [ ] **Step 3：修行 55**

原文：

```markdown
如果使用者要的事這 18 個都做不到（「幫我倒水」「飛起來」「訂便當」），
```

改為：

```markdown
如果使用者要的事上面清單都做不到（「幫我倒水」「飛起來」「訂便當」），
```

- [ ] **Step 4：commit**

```bash
git add pawai_brain/personas/v1/CAPABILITIES.md
git commit -m "spec-a/pr1: CAPABILITIES 刪硬寫數字 17/18 → 清單參考

實際 active skill 數量會隨 registry 變動，硬寫易腐。"
```

---

## Task 1.9：`CAPABILITIES.md` 結尾新增 STATUS_NOTE

**Files：**
- Modify：`pawai_brain/personas/v1/CAPABILITIES.md`（檔尾 append）

- [ ] **Step 1：確認目前檔尾**

```bash
tail -10 pawai_brain/personas/v1/CAPABILITIES.md
```

- [ ] **Step 2：在檔尾 append**

```markdown

---

## STATUS_NOTE — Demo 行為規範

**可主動展示能力**：
- 人臉辨識（已註冊的人）
- 語音中文對話（短句聊天、自介、能力解釋）
- OK 二次確認、palm 全面暫停
- 基本手勢觸發（thumbs_up → wiggle、peace → stretch，需 OK 確認）
- 基本姿勢 grounding（standing / sitting；fallen 只作保守展示或 trace）
- 物體與顏色辨識（COCO 大物件 + 12 色）
- Studio trace 可視化

**可解釋但不主動承諾**：
- stranger_alert：能偵測未知人臉，但 demo 時保守處理不主動打斷
- fallen_alert：能偵測跌倒，但 demo 時不主動 TTS 插話
- nav_demo_point：短距移動為實驗性，需明確要求
- approach_person：靠近人為實驗性，需明確要求

**不列為 demo 能力**（被問到時誠實說「目前不做」或「還在開發」）：
- 跟隨（follow_me / follow_person）
- 主動巡邏（patrol_route）
- 靜音模式（enter_mute_mode）
- 監聽模式（enter_listen_mode）
- Circle / ComeHere 動態手勢
- 長期記憶（只能記最近幾輪對話）
- 多人 robust 辨識
- 自主尋物
```

- [ ] **Step 3：commit**

```bash
git add pawai_brain/personas/v1/CAPABILITIES.md
git commit -m "spec-a/pr1: CAPABILITIES 結尾加 STATUS_NOTE 三層 demo 行為規範

可主動展示 / 可解釋但不主動承諾 / 不列為 demo 能力；
LLM 引用此節判斷如何回答能力問題。"
```

---

## Task 1.10：`EXAMPLES.md` 新增 2 條降級對話

**Files：**
- Modify：`pawai_brain/personas/v1/EXAMPLES.md`（檔尾 append）

- [ ] **Step 1：確認檔尾**

```bash
tail -5 pawai_brain/personas/v1/EXAMPLES.md
```

- [ ] **Step 2：append 2 條範例**

```markdown

### 範例 N — 使用者問做不到的能力（跟隨）

使用者：你會跟著我走嗎？
PawAI：這個能力我還不主動承諾 demo。現在我比較適合展示認人、聽你說話、看手勢，還有理解你現在的姿勢。

### 範例 N+1 — 使用者問降級能力（陌生人）

使用者：你會看到陌生人嗎？
PawAI：我能偵測未知人臉，但 demo 時會保守處理，不會一直插話。你可以在 Studio 看 trace。
```

- [ ] **Step 3：commit**

```bash
git add pawai_brain/personas/v1/EXAMPLES.md
git commit -m "spec-a/pr1: EXAMPLES 加 2 條降級範例（跟隨/陌生人）

短句 PawAI 口吻，與 STATUS_NOTE 三層分類對齊。"
```

---

## Task 1.11：PR 1 自驗（claim pattern grep）

- [ ] **Step 1：驗 claim pattern 在 STATUS_NOTE 外無違規**

```bash
# 取 STATUS_NOTE 之前的內容
awk '/^## STATUS_NOTE/{exit} {print}' pawai_brain/personas/v1/CAPABILITIES.md > /tmp/persona-pre-status.txt

# claim pattern grep
grep -nE "我會跟隨|會跟隨你|可以跟著|我會主動巡邏|會主動巡邏|我會靜音|進入靜音模式|我會監聽|進入監聽模式" /tmp/persona-pre-status.txt
```

Expected：grep 無輸出（exit 1）。若有輸出，回頭修對應行。

- [ ] **Step 2：驗 EXAMPLES claim pattern 也乾淨**

```bash
grep -nE "我會跟著你|我可以跟著你|我會靠近你|我可以自己找你" pawai_brain/personas/v1/EXAMPLES.md
```

Expected：無輸出（範例措辭是「不主動承諾」「保守處理」，不該命中 banned）。

- [ ] **Step 3：跑既有 persona test（若有）**

```bash
cd pawai_brain && python -m pytest test/ -v --tb=short 2>&1 | tail -20
cd ..
```

Expected：既有 test 全綠（或維持與 base 同等狀態）。

---

## Task 1.12：推 PR 1 並開 PR

- [ ] **Step 1：push branch**

```bash
git push -u origin spec-a/pr1-static-fixes
```

- [ ] **Step 2：開 PR（gh CLI）**

```bash
gh pr create --base main --head spec-a/pr1-static-fixes \
  --title "spec-a/pr1: static fixes — package / requirements / README / persona / runbook" \
  --body "$(cat <<'EOF'
## Summary

Spec A PR 群 1：靜態修補。純 markdown / xml / txt 改動，預期不動 runtime Python。

對應 spec sections §2 / §3 / Appendix C：
- `pawai_brain/package.xml`：補 `python3-requests` exec_depend
- `requirements-jetson.txt`（repo 根）：補 `langgraph` / `langchain-core` 版本 pin
- `docs/pawai-brain/README.md:18`：主模型對齊 code（`openai/gpt-5.4-mini`）
- `docs/runbook/README.md`：Jetson bring-up `uv pip install` 指引
- `docs/pawai_cli/team-onboarding.md`：demo 唯一合法 chain + legacy 禁用
- `personas/v1/CAPABILITIES.md`：4 行誇大字句砍除、硬數字 17/18 改寫、結尾新增 STATUS_NOTE 三層
- `personas/v1/EXAMPLES.md`：補 2 條降級對話範例

## Test plan
- [x] xml well-formed
- [x] pip dry-run parse 成功
- [x] claim pattern grep（STATUS_NOTE 外）無違規
- [x] EXAMPLES 不含 banned claim
- [x] 既有 persona test 全綠

Spec：docs/pawai-brain/specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md
EOF
)"
```

- [ ] **Step 3：等 review 與 merge 後**

```bash
git checkout main
git pull --ff-only
git log --oneline -1  # 確認 PR 1 已 merge 進 main
```

---

# PR 群 2A：Runtime Mechanical Guard

**Branch**：`spec-a/pr2a-mechanical-guard`
**Base**：PR 1 merged 後 main
**估行數**：~600-800 行（preflight 主體 + Executive guard + 3 個 test file）

---

## Task 2A.1：建 PR 2A branch

- [ ] **Step 1**

```bash
git checkout main && git pull --ff-only
git checkout -b spec-a/pr2a-mechanical-guard
```

---

## Task 2A.2：preflight.py — CheckResult 資料型別與 runner skeleton

**Files：**
- Create：`tools/pawai_cli/pawai_cli/preflight.py`

- [ ] **Step 1：寫 test 先**

Create `tools/pawai_cli/tests/test_preflight.py`：

```python
"""Spec A preflight unit tests — CheckResult + runner skeleton."""

import pytest

from pawai_cli import preflight


def test_check_result_basic_pass():
    r = preflight.CheckResult(name="dummy", status="pass", detail="ok")
    assert r.is_pass()
    assert not r.is_fail()
    assert not r.is_warn()
    assert not r.is_skip()


def test_check_result_fail_with_hint():
    r = preflight.CheckResult(
        name="dummy",
        status="fail",
        detail="boom",
        fix_hint="run `make fix`",
    )
    assert r.is_fail()
    assert r.fix_hint == "run `make fix`"


def test_check_result_status_validation():
    with pytest.raises(ValueError):
        preflight.CheckResult(name="x", status="bogus")


def test_runner_aggregates_results():
    results = [
        preflight.CheckResult(name="a", status="pass"),
        preflight.CheckResult(name="b", status="fail", detail="x"),
        preflight.CheckResult(name="c", status="warn", detail="y"),
        preflight.CheckResult(name="d", status="skip", detail="z"),
    ]
    summary = preflight.summarize(results)
    assert summary.pass_count == 1
    assert summary.fail_count == 1
    assert summary.warn_count == 1
    assert summary.skip_count == 1
    assert not summary.all_passed  # has FAIL
    assert summary.exit_code == 1


def test_runner_all_pass():
    results = [preflight.CheckResult(name="a", status="pass")]
    summary = preflight.summarize(results)
    assert summary.all_passed
    assert summary.exit_code == 0
```

- [ ] **Step 2：跑 test 看 fail**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -15
cd ../..
```

Expected：ImportError，`preflight` module not found。

- [ ] **Step 3：寫最小實作**

Create `tools/pawai_cli/pawai_cli/preflight.py`：

```python
"""Spec A — pawai demo preflight 機制檢查與 semantic dry-run。

Mechanical：10 條 check（5 pre-start + 5 post-start），每條標 target
（local / jetson_ssh）。
Semantic：6 條語音劇本 dry-run（5 core + 1 persona guard）。

詳見 spec docs/pawai-brain/specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

_VALID_STATUS = frozenset({"pass", "fail", "warn", "skip"})


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str = ""
    fix_hint: str = ""
    target: str = "local"  # local / jetson_ssh

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUS:
            raise ValueError(
                f"invalid status {self.status!r}; want one of {sorted(_VALID_STATUS)}"
            )

    def is_pass(self) -> bool:
        return self.status == "pass"

    def is_fail(self) -> bool:
        return self.status == "fail"

    def is_warn(self) -> bool:
        return self.status == "warn"

    def is_skip(self) -> bool:
        return self.status == "skip"


@dataclass
class Summary:
    results: list[CheckResult] = field(default_factory=list)
    pass_count: int = 0
    fail_count: int = 0
    warn_count: int = 0
    skip_count: int = 0

    @property
    def all_passed(self) -> bool:
        return self.fail_count == 0

    @property
    def exit_code(self) -> int:
        return 0 if self.all_passed else 1


def summarize(results: Iterable[CheckResult]) -> Summary:
    s = Summary(results=list(results))
    for r in s.results:
        if r.is_pass():
            s.pass_count += 1
        elif r.is_fail():
            s.fail_count += 1
        elif r.is_warn():
            s.warn_count += 1
        elif r.is_skip():
            s.skip_count += 1
    return s
```

- [ ] **Step 4：跑 test 看 pass**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
cd ../..
```

Expected：5 tests pass。

- [ ] **Step 5：commit**

```bash
git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight skeleton — CheckResult + Summary

frozen dataclass，status enum，summarize 計數；後續 check 函式 / CLI
wiring 由下一步補。"
```

---

## Task 2A.3：persona scoped scan（check #3）+ test

**Files：**
- Create：`tools/pawai_cli/tests/test_persona_scoped_scan.py`
- Modify：`tools/pawai_cli/pawai_cli/preflight.py`

- [ ] **Step 1：寫 test**

Create `tools/pawai_cli/tests/test_persona_scoped_scan.py`：

```python
"""Persona scoped scan — STATUS_NOTE 不誤殺、claim pattern 抓得到。"""

import textwrap

from pawai_cli import preflight


def _md(body: str) -> str:
    return textwrap.dedent(body).lstrip("\n")


def test_status_note_disclaimer_not_flagged(tmp_path):
    """STATUS_NOTE「不列為 demo 能力」段含關鍵字但屬合法降級宣告。"""
    f = tmp_path / "CAPABILITIES.md"
    f.write_text(_md("""
        # 能力清單
        | 手勢 | OK 確認 |

        ## STATUS_NOTE — Demo 行為規範

        **不列為 demo 能力**：
        - 跟隨（follow_me / follow_person）
        - 主動巡邏（patrol_route）
        - 靜音模式（enter_mute_mode）
        - 監聽模式（enter_listen_mode）
    """))
    result = preflight.check_persona_no_banned(f)
    assert result.is_pass(), result.detail


def test_claim_pattern_in_capability_section_flagged(tmp_path):
    f = tmp_path / "CAPABILITIES.md"
    f.write_text(_md("""
        # 能力清單
        | 移動 | 我會跟隨你走 1 公尺 |

        ## STATUS_NOTE
        不列為 demo：跟隨
    """))
    result = preflight.check_persona_no_banned(f)
    assert result.is_fail(), "expected claim pattern '我會跟隨' to fail"
    assert "我會跟隨" in result.detail


def test_neutral_word_alone_not_flagged(tmp_path):
    """單詞「跟隨」未組成 claim pattern 不該失敗。"""
    f = tmp_path / "CAPABILITIES.md"
    f.write_text(_md("""
        # 能力清單
        | 描述 | 我可以說明跟隨能力的設計概念，但 demo 不主動承諾 |
    """))
    result = preflight.check_persona_no_banned(f)
    assert result.is_pass(), result.detail


def test_missing_file_fails(tmp_path):
    result = preflight.check_persona_no_banned(tmp_path / "nope.md")
    assert result.is_fail()
    assert "not found" in result.detail.lower()


def test_multiple_violations_all_listed(tmp_path):
    f = tmp_path / "CAPABILITIES.md"
    f.write_text(_md("""
        # 能力
        | a | 我會跟隨你 |
        | b | 我會主動巡邏 |
        | c | 進入靜音模式 |
    """))
    result = preflight.check_persona_no_banned(f)
    assert result.is_fail()
    # 三個違規都該被列出
    for pat in ("我會跟隨", "我會主動巡邏", "進入靜音模式"):
        assert pat in result.detail
```

- [ ] **Step 2：跑 test 看 fail**

```bash
cd tools/pawai_cli && python -m pytest tests/test_persona_scoped_scan.py -v 2>&1 | tail -15
cd ../..
```

Expected：5 tests fail with `AttributeError: module 'pawai_cli.preflight' has no attribute 'check_persona_no_banned'`。

- [ ] **Step 3：實作 check function**

Append to `tools/pawai_cli/pawai_cli/preflight.py`：

```python
import re
from pathlib import Path

# Spec A §7.3.1 claim-pattern banlist (規則：claim，不是單詞)
_BANNED_CLAIM_PATTERNS: tuple[str, ...] = (
    r"我會跟隨",
    r"會跟隨你",
    r"可以跟著",
    r"我會主動巡邏",
    r"會主動巡邏",
    r"我會靜音",
    r"進入靜音模式",
    r"我會監聽",
    r"進入監聽模式",
)

_STATUS_NOTE_HEADING = "## STATUS_NOTE"


def _strip_status_note(content: str) -> str:
    """Drop the STATUS_NOTE section (and beyond) — it intentionally lists
    降級用語，不應觸發 banned scan。"""
    idx = content.find(_STATUS_NOTE_HEADING)
    if idx == -1:
        return content
    return content[:idx]


def check_persona_no_banned(path: Path) -> CheckResult:
    """Check #3 — persona_loaded_no_banned (target=local, Spec A §7.3.1)."""
    if not path.exists():
        return CheckResult(
            name="persona_loaded_no_banned",
            status="fail",
            detail=f"persona file not found: {path}",
            fix_hint=f"check Spec A §3 改動是否落地；確認 {path} 存在",
            target="local",
        )
    raw = path.read_text(encoding="utf-8")
    scoped = _strip_status_note(raw)
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(scoped.splitlines(), start=1):
        for pat in _BANNED_CLAIM_PATTERNS:
            if re.search(pat, line):
                hits.append((lineno, pat))
    if hits:
        detail = "; ".join(f"L{ln}: {pat}" for ln, pat in hits)
        return CheckResult(
            name="persona_loaded_no_banned",
            status="fail",
            detail=detail,
            fix_hint="改寫違規行；STATUS_NOTE 段不掃，可移至 STATUS_NOTE",
            target="local",
        )
    return CheckResult(
        name="persona_loaded_no_banned",
        status="pass",
        detail=f"scanned {len(scoped.splitlines())} lines (STATUS_NOTE excluded)",
        target="local",
    )
```

- [ ] **Step 4：跑 test 看 pass**

```bash
cd tools/pawai_cli && python -m pytest tests/test_persona_scoped_scan.py -v 2>&1 | tail -10
cd ../..
```

Expected：5 tests pass。

- [ ] **Step 5：commit**

```bash
git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_persona_scoped_scan.py
git commit -m "spec-a/pr2a: preflight check #3 persona scoped scan

STATUS_NOTE 段排除；claim pattern（我會跟隨/進入靜音模式 等）grep；
與 Appendix B reply pattern 同調，避免單詞誤殺。"
```

---

## Task 2A.4：preflight imports check（#1）+ test

**Files：**
- Modify：`tools/pawai_cli/pawai_cli/preflight.py`、`tools/pawai_cli/tests/test_preflight.py`

- [ ] **Step 1：寫 test（mock SSH wrapper）**

Append to `tools/pawai_cli/tests/test_preflight.py`：

```python
from unittest.mock import MagicMock

def test_imports_check_jetson_pass(monkeypatch):
    def fake_ssh(cmd, **kw):
        # python3 -c "import langgraph, ..." → exit 0
        return MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_imports(target="jetson")
    assert r.is_pass()
    assert r.target == "jetson_ssh"


def test_imports_check_jetson_fail(monkeypatch):
    def fake_ssh(cmd, **kw):
        return MagicMock(
            returncode=1,
            stdout="",
            stderr="ModuleNotFoundError: No module named 'langgraph'",
        )
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_imports(target="jetson")
    assert r.is_fail()
    assert "langgraph" in r.detail
    assert "uv pip install" in r.fix_hint


def test_imports_check_local_runs_inproc(monkeypatch):
    """target=local 跑本機 python，不走 SSH。"""
    sentinel = []
    def fake_ssh(*a, **kw):
        sentinel.append("ssh_called")
        return MagicMock(returncode=0)
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_imports(target="local")
    # 不該呼叫 SSH
    assert "ssh_called" not in sentinel
    # 本機應該能 import yaml/requests 至少（langgraph 視 dev env 可能無）
    assert r.target == "local"
```

- [ ] **Step 2：跑 test 看 fail**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py::test_imports_check_jetson_pass -v 2>&1 | tail -10
cd ../..
```

Expected：`AttributeError: ... has no attribute 'check_imports' / '_ssh_run'`。

- [ ] **Step 3：實作**

Append to `preflight.py`：

```python
import subprocess
from typing import Literal

Target = Literal["jetson", "local", "both"]

_REQUIRED_IMPORTS = ("langgraph", "langchain_core", "requests", "yaml")


def _ssh_run(cmd: str, timeout: int = 15) -> subprocess.CompletedProcess:
    """SSH wrapper — **必須**復用 pawai_cli 既有 host 解析鏈，禁止平行讀
    `os.environ['JETSON_HOST']`。

    使用 `shell.jetson_host()`（tools/pawai_cli/pawai_cli/shell.py:62）取
    host；若需要 demo env（含 Tailscale IP override / `.env` propagation），
    用 `main._build_demo_env()`（main.py:647）。這條鏈在
    `b05205d`~`caef6b5` 已修穩，preflight 不得重寫。
    """
    from pawai_cli import shell  # 既有 helper
    host = shell.jetson_host()
    if not host:
        raise RuntimeError(
            "shell.jetson_host() returned empty; "
            "check JETSON_HOST / .env / Tailscale override"
        )
    return subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout={timeout}",
         host, cmd],
        capture_output=True, text=True, timeout=timeout + 5,
    )


def check_imports(target: Target = "jetson") -> CheckResult:
    """Check #1 — imports (Spec A §7.3 / §2.4)."""
    cmd = f'python3 -c "import {", ".join(_REQUIRED_IMPORTS)}"'
    if target == "local":
        proc = subprocess.run(
            ["python3", "-c", f'import {", ".join(_REQUIRED_IMPORTS)}'],
            capture_output=True, text=True,
        )
        actual_target = "local"
    else:
        proc = _ssh_run(cmd)
        actual_target = "jetson_ssh"
    if proc.returncode == 0:
        return CheckResult(
            name="imports", status="pass",
            detail="all 4 modules import OK",
            target=actual_target,
        )
    return CheckResult(
        name="imports", status="fail",
        detail=proc.stderr.strip() or "non-zero exit",
        fix_hint="on Jetson: uv pip install -r requirements-jetson.txt",
        target=actual_target,
    )
```

- [ ] **Step 4：跑 test pass**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -15
cd ../..
```

- [ ] **Step 5：commit**

```bash
git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight check #1 imports (jetson_ssh + local)

langgraph / langchain_core / requests / yaml；fail 指向
uv pip install -r requirements-jetson.txt；monkeypatch-friendly _ssh_run wrapper。"
```

---

## Task 2A.5：env_key check（#2）+ test

**Files：**
- Modify：`tools/pawai_cli/pawai_cli/preflight.py`、`tools/pawai_cli/tests/test_preflight.py`

- [ ] **Step 1：寫 test**

Append `test_preflight.py`：

```python
def test_env_key_present_in_env(monkeypatch):
    monkeypatch.setenv("OPENROUTER_KEY", "sk-or-v1-xxxxx")
    r = preflight.check_env_key(allow_fallback=False)
    assert r.is_pass()
    assert "length=" in r.detail


def test_env_key_missing_fails(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = preflight.check_env_key(allow_fallback=False)
    assert r.is_fail()
    assert "OPENROUTER" in r.detail


def test_env_key_missing_with_fallback_warns(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    r = preflight.check_env_key(allow_fallback=True, fallback_reason="OpenRouter down")
    assert r.is_warn()
    assert "FALLBACK ACCEPTED" in r.detail
    assert "OpenRouter down" in r.detail


def test_env_key_alt_var_name(monkeypatch):
    monkeypatch.delenv("OPENROUTER_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-yyyyy")
    r = preflight.check_env_key(allow_fallback=False)
    assert r.is_pass()
```

- [ ] **Step 2：實作**

Append `preflight.py`：

```python
import os


def check_env_key(
    allow_fallback: bool = False,
    fallback_reason: str = "",
) -> CheckResult:
    """Check #2 — env_key (Spec A §7.3, fallback PASS 條件詳 §7.2)."""
    key = os.environ.get("OPENROUTER_KEY") or os.environ.get("OPENROUTER_API_KEY")
    if key:
        return CheckResult(
            name="env_key", status="pass",
            detail=f"OPENROUTER_KEY length={len(key)}",
            target="local",
        )
    if allow_fallback:
        return CheckResult(
            name="env_key", status="warn",
            detail=f"FALLBACK ACCEPTED: {fallback_reason or '(no reason)'}",
            target="local",
        )
    return CheckResult(
        name="env_key", status="fail",
        detail="OPENROUTER_KEY / OPENROUTER_API_KEY both empty",
        fix_hint="check .env; verify start_full_demo_tmux.sh ROS_SETUP set -a",
        target="local",
    )
```

- [ ] **Step 3：跑 test + commit**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
cd ../..

git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight check #2 env_key + --allow-fallback WARN

key 缺失預設 FAIL；allow_fallback=True 改 WARN 並印 reason；
支援 OPENROUTER_KEY / OPENROUTER_API_KEY 兩 alias。"
```

---

## Task 2A.6：pose_grounding_code_ready check（#4）+ test

**Files：**
- Modify：`preflight.py`、`test_preflight.py`

- [ ] **Step 1：寫 test**

```python
def test_pose_grounding_check_signature_supports_dict(monkeypatch):
    """模擬 world_state_builder.set_pose_provider 已支援 dict shape。"""
    def fake_ssh(cmd, **kw):
        # SSH 跑 inspect 印出 signature OK
        return MagicMock(returncode=0, stdout="pose_provider_dict_compat=true\n", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_pose_grounding(target="jetson")
    assert r.is_pass()


def test_pose_grounding_check_dict_unsupported(monkeypatch):
    def fake_ssh(cmd, **kw):
        return MagicMock(returncode=2, stdout="", stderr="set_pose_provider does not accept dict")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_pose_grounding(target="jetson")
    assert r.is_fail()
    assert "dict" in r.detail.lower()
```

- [ ] **Step 2：實作**

```python
_POSE_PROBE_SCRIPT = (
    "from pawai_brain.nodes.world_state_builder import set_pose_provider; "
    "import inspect; "
    "sig = inspect.signature(set_pose_provider); "
    "print('pose_provider_dict_compat=true') "
    "if any(p.annotation in (dict, 'dict') or 'dict' in str(p.annotation) "
    "       for p in sig.parameters.values()) "
    "else exit(2)"
)


def check_pose_grounding(target: Target = "jetson") -> CheckResult:
    """Check #4 — pose_grounding_code_ready (Spec A §7.3)."""
    cmd = f'python3 -c "{_POSE_PROBE_SCRIPT}"'
    if target == "local":
        proc = subprocess.run(
            ["python3", "-c", _POSE_PROBE_SCRIPT],
            capture_output=True, text=True,
        )
        actual = "local"
    else:
        proc = _ssh_run(cmd)
        actual = "jetson_ssh"
    if proc.returncode == 0:
        return CheckResult(
            name="pose_grounding_code_ready", status="pass",
            detail="set_pose_provider signature accepts dict shape",
            target=actual,
        )
    return CheckResult(
        name="pose_grounding_code_ready", status="fail",
        detail=proc.stderr.strip() or "set_pose_provider dict shape not supported",
        fix_hint="confirm Spec A PR 3 (pose Brain-side simulation) 已 merge",
        target=actual,
    )
```

- [ ] **Step 3：跑 test + commit**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
cd ../..

git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight check #4 pose_grounding_code_ready

inspect.signature(set_pose_provider) 確認支援 dict shape；PR 3 後此 check
PASS。"
```

---

## Task 2A.7：legacy_processes_not_running check（#5）+ test

**Files：**
- Modify：`preflight.py`、`test_preflight.py`

- [ ] **Step 1：寫 test**

```python
def test_legacy_processes_all_absent(monkeypatch):
    def fake_ssh(cmd, **kw):
        # pgrep -f returns 1 when no match
        return MagicMock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_legacy_processes()
    assert r.is_pass()


def test_legacy_processes_one_running(monkeypatch):
    calls = []
    def fake_ssh(cmd, **kw):
        calls.append(cmd)
        # llm_bridge_node 跑著
        if "llm_bridge_node" in cmd:
            return MagicMock(returncode=0, stdout="12345\n", stderr="")
        return MagicMock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_legacy_processes()
    assert r.is_fail()
    assert "llm_bridge_node" in r.detail
    assert "pawai demo stop" in r.fix_hint
```

- [ ] **Step 2：實作**

```python
_LEGACY_NODES = (
    "llm_bridge_node",
    "intent_tts_bridge_node",
    "event_action_bridge",
    "route_runner_node",
)


def check_legacy_processes(target: Target = "jetson") -> CheckResult:
    """Check #5 — legacy_processes_not_running (Spec A §7.3)."""
    running: list[str] = []
    for node in _LEGACY_NODES:
        cmd = f"pgrep -f {node}"
        if target == "local":
            proc = subprocess.run(["pgrep", "-f", node], capture_output=True, text=True)
        else:
            proc = _ssh_run(cmd)
        if proc.returncode == 0 and proc.stdout.strip():
            running.append(node)
    if running:
        return CheckResult(
            name="legacy_processes_not_running", status="fail",
            detail=f"legacy nodes running: {', '.join(running)}",
            fix_hint="pawai demo stop, or manually kill above PIDs",
            target="jetson_ssh" if target != "local" else "local",
        )
    return CheckResult(
        name="legacy_processes_not_running", status="pass",
        detail="no legacy nodes detected",
        target="jetson_ssh" if target != "local" else "local",
    )
```

- [ ] **Step 3：跑 test + commit**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
cd ../..

git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight check #5 legacy_processes_not_running

pgrep -f 確認 llm_bridge / intent_tts_bridge / event_action_bridge /
route_runner 未在 Jetson 跑；違規列名 + fix hint。"
```

---

## Task 2A.8：post-start checks #6-#10（ROS graph + trace）

**Files：**
- Modify：`preflight.py`、`test_preflight.py`

由於 #6-#10 都依賴 ROS topology / topic info / trace ping，這 5 條共用 helper。

- [ ] **Step 1：寫 test（mock SSH 回傳 ros2 cli 輸出）**

Append `test_preflight.py`：

```python
_ROS_NODE_LIST = """\
/conversation_graph_node
/interaction_executive_node
/tts_node
/brain_node
"""

_TOPIC_INFO_TTS_OK = """\
Type: std_msgs/msg/String
Publisher count: 1
Subscription count: 1
Node name: interaction_executive_node
"""

_TOPIC_INFO_TTS_FOREIGN = _TOPIC_INFO_TTS_OK + """
Node name: event_action_bridge
"""

_TRACE_OUTPUT_OK = """\
data: '{"stage": "input", "engine": "langgraph", "text": "__preflight_ping_TOKEN__"}'
---
data: '{"stage": "world_state", "engine": "langgraph"}'
---
data: '{"stage": "capability", "engine": "langgraph"}'
---
data: '{"stage": "llm_decision", "engine": "langgraph", "status": "ok"}'
---
data: '{"stage": "output", "engine": "langgraph"}'
---
"""
# TOKEN 由 test 動態替換成實際產生的 token，驗 correlation 強關聯路徑


def test_conversation_graph_alive_pass(monkeypatch):
    def fake_ssh(cmd, **kw):
        if "node list" in cmd:
            return MagicMock(returncode=0, stdout=_ROS_NODE_LIST, stderr="")
        if "topic info /brain/text_input" in cmd:
            return MagicMock(returncode=0,
                stdout="Subscription count: 1\nNode name: conversation_graph_node\n",
                stderr="")
        return MagicMock(returncode=1, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_conversation_graph_alive()
    assert r.is_pass()


def test_tts_publisher_unique_foreign_fails(monkeypatch):
    def fake_ssh(cmd, **kw):
        if "topic info /tts" in cmd:
            return MagicMock(returncode=0, stdout=_TOPIC_INFO_TTS_FOREIGN, stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_tts_publisher_unique()
    assert r.is_fail()
    assert "event_action_bridge" in r.detail


def test_tts_publisher_unique_pass(monkeypatch):
    def fake_ssh(cmd, **kw):
        return MagicMock(returncode=0, stdout=_TOPIC_INFO_TTS_OK, stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_tts_publisher_unique()
    assert r.is_pass()


def test_chat_candidate_publisher_unique_pass(monkeypatch):
    fixture = "Type: std_msgs/msg/String\nPublisher count: 1\nNode name: conversation_graph_node\n"
    def fake_ssh(cmd, **kw):
        return MagicMock(returncode=0, stdout=fixture, stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_chat_candidate_publisher_unique()
    assert r.is_pass()


def test_tts_playing_state_available_pass(monkeypatch):
    fixture = "Type: std_msgs/msg/Bool\nPublisher count: 1\nNode name: tts_node\n"
    def fake_ssh(cmd, **kw):
        return MagicMock(returncode=0, stdout=fixture, stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_tts_playing_state_available()
    assert r.is_pass()


def test_brain_trace_pipeline_pass(monkeypatch):
    """Token 注入 trace 觸發強關聯；stages 完整；engine=langgraph。"""
    captured_token = {}
    def fake_ssh(cmd, **kw):
        if "topic pub" in cmd:
            # 從 publish 命令抽出 ping token
            import re
            m = re.search(r"__preflight_ping_[0-9a-f]+__", cmd)
            if m:
                captured_token["t"] = m.group(0)
            return MagicMock(returncode=0, stdout="", stderr="")
        if "topic echo" in cmd or "trace" in cmd:
            # 把 _TRACE_OUTPUT_OK 的 TOKEN 換成這次實際 token
            body = _TRACE_OUTPUT_OK.replace(
                "__preflight_ping_TOKEN__", captured_token.get("t", "TOKEN_NOT_SET"))
            return MagicMock(returncode=0, stdout=body, stderr="")
        return MagicMock(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_brain_trace_pipeline(allow_fallback=False)
    assert r.is_pass(), r.detail


def test_brain_trace_pipeline_stale_buffer_fails(monkeypatch):
    """Trace 不含 token、payload 也無 stamp >= t_publish → correlation lost。"""
    stale = """\
data: '{"stage": "input", "engine": "langgraph"}'
---
data: '{"stage": "world_state", "engine": "langgraph"}'
---
data: '{"stage": "capability", "engine": "langgraph"}'
---
data: '{"stage": "llm_decision", "engine": "langgraph"}'
---
data: '{"stage": "output", "engine": "langgraph"}'
---
"""
    def fake_ssh(cmd, **kw):
        if "topic pub" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout=stale, stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_brain_trace_pipeline(allow_fallback=False)
    assert r.is_fail()
    assert "correlation" in r.detail.lower() or "stale" in r.detail.lower()


def test_brain_trace_pipeline_weak_correlation_via_stamp(monkeypatch):
    """無 token echo，但 trace 含 stamp >= t_publish → 弱關聯仍 pass。"""
    import time
    future_stamp = time.time() + 1.0  # 必 > t_publish
    body = f"""\
data: '{{"stage": "input", "engine": "langgraph", "stamp": {future_stamp}}}'
---
data: '{{"stage": "world_state", "engine": "langgraph"}}'
---
data: '{{"stage": "capability", "engine": "langgraph"}}'
---
data: '{{"stage": "llm_decision", "engine": "langgraph"}}'
---
data: '{{"stage": "output", "engine": "langgraph"}}'
---
"""
    def fake_ssh(cmd, **kw):
        if "topic pub" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout=body, stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_brain_trace_pipeline(allow_fallback=False)
    assert r.is_pass(), r.detail


def test_brain_trace_pipeline_missing_stage_fails(monkeypatch):
    truncated_with_token = """\
data: '{"stage": "input", "engine": "langgraph", "text": "TOKEN_HERE"}'
---
data: '{"stage": "output", "engine": "langgraph"}'
---
"""
    def fake_ssh(cmd, **kw):
        if "topic pub" in cmd:
            import re
            m = re.search(r"__preflight_ping_[0-9a-f]+__", cmd)
            if m:
                truncated_with_token_replaced = truncated_with_token.replace(
                    "TOKEN_HERE", m.group(0))
                fake_ssh._echo_body = truncated_with_token_replaced
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=0, stdout=getattr(fake_ssh, "_echo_body", ""), stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_brain_trace_pipeline(allow_fallback=False)
    assert r.is_fail()
    assert "world_state" in r.detail or "missing" in r.detail.lower()


def test_brain_trace_pipeline_fallback_accepted(monkeypatch):
    fallback_trace = """\
data: '{"stage": "input", "engine": "rule_brain", "text": "TOKEN_HERE"}'
---
data: '{"stage": "world_state", "engine": "rule_brain"}'
---
data: '{"stage": "output", "engine": "rule_brain", "status": "ok"}'
---
"""
    def fake_ssh(cmd, **kw):
        if "topic pub" in cmd:
            import re
            m = re.search(r"__preflight_ping_[0-9a-f]+__", cmd)
            if m:
                fake_ssh._echo_body = fallback_trace.replace("TOKEN_HERE", m.group(0))
            return MagicMock(returncode=0)
        return MagicMock(returncode=0, stdout=getattr(fake_ssh, "_echo_body", ""), stderr="")
    monkeypatch.setattr(preflight, "_ssh_run", fake_ssh)
    r = preflight.check_brain_trace_pipeline(allow_fallback=True, fallback_reason="LLM down")
    assert r.is_warn() or r.is_pass()
    assert "FALLBACK" in r.detail or "rule_brain" in r.detail
```

- [ ] **Step 2：實作 #6-#10**

Append to `preflight.py`：

```python
import json
import time

_LANGGRAPH_REQUIRED_STAGES = (
    "input", "world_state", "capability", "llm_decision", "output",
)
_FALLBACK_REQUIRED_STAGES = ("input", "world_state", "output")


def _parse_topic_info_publishers(stdout: str) -> list[str]:
    """從 `ros2 topic info -v` 輸出抽 publisher node 名稱清單。

    **嚴格只解析 Publishers section**。不做「無 section heading 時 fallback
    抓所有 Node name」— 那會把 subscribers（例如 `/tts` 的 `tts_node`）誤算
    成 publisher，導致 unique check false fail。

    若 stdout 無法解析出 Publishers section，回傳空 list，由 caller 判定為
    `fail`（"could not parse publishers section"），而不是 silent grabbing all。
    """
    nodes: list[str] = []
    section: Optional[str] = None
    for line in stdout.splitlines():
        stripped = line.strip()
        low = stripped.lower()
        # ros2 cli 不同版本可能用 "Publishers:" / "Publisher count: N"
        # / "Publishers" 等；都以 "publisher" 開頭觸發
        if low.startswith("publisher"):
            section = "pub"
            continue
        if low.startswith("subscription") or low.startswith("subscriber"):
            section = "sub"
            continue
        if section == "pub" and stripped.startswith("Node name:"):
            nodes.append(stripped.split(":", 1)[1].strip())
    return nodes


def _topic_info_parseable(stdout: str) -> bool:
    """Did the output contain any Publisher / Subscription section header?"""
    low = stdout.lower()
    return ("publisher" in low) or ("subscription" in low) or ("subscriber" in low)


def check_conversation_graph_alive() -> CheckResult:
    """Check #6."""
    nodes_proc = _ssh_run("ros2 node list")
    if nodes_proc.returncode != 0:
        return CheckResult(
            name="conversation_graph_alive", status="fail",
            detail=f"ros2 node list failed: {nodes_proc.stderr.strip()}",
            fix_hint="confirm demo stack 已啟動；ROS_DOMAIN_ID 一致",
            target="jetson_ssh",
        )
    if "/conversation_graph_node" not in nodes_proc.stdout:
        return CheckResult(
            name="conversation_graph_alive", status="fail",
            detail="conversation_graph_node missing from ros2 node list",
            fix_hint="pawai demo stop && pawai demo start",
            target="jetson_ssh",
        )
    info = _ssh_run("ros2 topic info /brain/text_input -v")
    if "Subscription count: 0" in info.stdout or "conversation_graph_node" not in info.stdout:
        return CheckResult(
            name="conversation_graph_alive", status="fail",
            detail="/brain/text_input has no conversation_graph_node subscriber",
            fix_hint="check launch params / topic remap",
            target="jetson_ssh",
        )
    return CheckResult(
        name="conversation_graph_alive", status="pass",
        detail="node alive and subscribed to /brain/text_input",
        target="jetson_ssh",
    )


def _check_unique_publisher(topic: str, expected_node: str, check_name: str) -> CheckResult:
    info = _ssh_run(f"ros2 topic info {topic} -v")
    if info.returncode != 0:
        return CheckResult(
            name=check_name, status="fail",
            detail=f"ros2 topic info {topic} failed: {info.stderr.strip()}",
            target="jetson_ssh",
        )
    if not _topic_info_parseable(info.stdout):
        # Output format unrecognized — refuse to guess, fail explicitly
        return CheckResult(
            name=check_name, status="fail",
            detail=f"could not parse Publishers section from "
                   f"`ros2 topic info {topic} -v` output; refuse to guess "
                   f"(would risk false pass/fail)",
            fix_hint="check ros2 cli version on Jetson; "
                     "consider switching to rclpy graph API",
            target="jetson_ssh",
        )
    pubs = _parse_topic_info_publishers(info.stdout)
    if not pubs:
        return CheckResult(
            name=check_name, status="fail",
            detail=f"no publisher for {topic}",
            target="jetson_ssh",
        )
    if set(pubs) != {expected_node}:
        foreign = sorted(set(pubs) - {expected_node})
        return CheckResult(
            name=check_name, status="fail",
            detail=f"foreign publishers on {topic}: {', '.join(foreign)}",
            fix_hint=f"demo runtime 不該啟 {foreign}；檢查 start_full_demo_tmux.sh",
            target="jetson_ssh",
        )
    return CheckResult(
        name=check_name, status="pass",
        detail=f"{topic} unique publisher = {expected_node}",
        target="jetson_ssh",
    )


def check_chat_candidate_publisher_unique() -> CheckResult:
    return _check_unique_publisher(
        "/brain/chat_candidate", "conversation_graph_node",
        "chat_candidate_publisher_unique",
    )


def check_tts_publisher_unique() -> CheckResult:
    return _check_unique_publisher(
        "/tts", "interaction_executive_node",
        "tts_publisher_unique",
    )


def check_tts_playing_state_available() -> CheckResult:
    return _check_unique_publisher(
        "/state/tts_playing", "tts_node",
        "tts_playing_state_available",
    )


def _parse_trace_stages(
    stdout: str,
    token: Optional[str] = None,
    after_ts: Optional[float] = None,
) -> tuple[list[str], Optional[str], bool]:
    """從 `ros2 topic echo /brain/conversation_trace` 輸出抽 stage 序列、engine、
    與 correlation 結果。

    Correlation 判定：
    - 強關聯：任一 stage payload 字串含 `token`（input stage 通常會 echo
      使用者文字；或 trace 內帶 request_id / input_text 欄位）
    - 弱關聯：payload 含 `stamp` 或 `ts` 欄位且 >= after_ts
    - 兩者都無 → correlated=False（caller 視為 stale buffer，fail）
    """
    stages: list[str] = []
    engine: Optional[str] = None
    correlated = False
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload_str = line[len("data:"):].strip().strip("'\"")
        try:
            obj = json.loads(payload_str)
        except json.JSONDecodeError:
            continue
        if "stage" in obj:
            stages.append(obj["stage"])
        if "engine" in obj and engine is None:
            engine = obj["engine"]
        # 強關聯：token 在 payload 任何字串值內
        if token and not correlated:
            if token in payload_str:
                correlated = True
        # 弱關聯：stamp >= after_ts
        if not correlated and after_ts is not None:
            for stamp_field in ("stamp", "ts", "timestamp"):
                v = obj.get(stamp_field)
                if isinstance(v, (int, float)) and v >= after_ts:
                    correlated = True
                    break
    return stages, engine, correlated


def check_brain_trace_pipeline(
    allow_fallback: bool = False,
    fallback_reason: str = "",
    wait_seconds: int = 8,
) -> CheckResult:
    """Check #7 — publish ping + collect trace + verify stage 序列 / engine。

    **Correlation**：每次 ping 帶唯一 token `__preflight_ping_<8hex>__`，
    確保收到的 trace 是這次 ping 觸發的、不是 buffered 舊 trace。判定條件：
    1. 必要：trace 任一 stage payload 含此 token（強關聯）
    2. 補救：若 token 找不到（trace schema 未 echo input text），則時間窗
       guard — 只接受 ping publish 之後 `wait_seconds` 內收到的 trace
       （需 trace payload 含 stamp 或用 `--field-csv` 抓 ROS header）
    若兩條都沒滿足 → fail "trace correlation lost — likely stale buffer"。
    """
    import secrets
    import time as _time
    token = f"__preflight_ping_{secrets.token_hex(4)}__"
    t_publish = _time.time()
    pub = _ssh_run(
        f'ros2 topic pub --once /brain/text_input std_msgs/msg/String '
        f'"data: \\\"{token}\\\""'
    )
    if pub.returncode != 0:
        return CheckResult(
            name="brain_trace_pipeline", status="fail",
            detail=f"failed to publish ping: {pub.stderr.strip()}",
            target="jetson_ssh",
        )
    echo = _ssh_run(
        f"timeout {wait_seconds} ros2 topic echo /brain/conversation_trace"
    )
    stages, engine, correlated = _parse_trace_stages(echo.stdout, token=token,
                                                    after_ts=t_publish)
    if not stages:
        return CheckResult(
            name="brain_trace_pipeline", status="fail",
            detail="no trace received within wait window",
            fix_hint="conversation_graph_node alive? check ROS_DOMAIN_ID",
            target="jetson_ssh",
        )
    if not correlated:
        return CheckResult(
            name="brain_trace_pipeline", status="fail",
            detail=(f"trace correlation lost — token {token} not found in trace "
                    f"and no stamp >= t_publish; likely stale buffer"),
            fix_hint="check trace schema for input echo / stamp; "
                     "or rerun preflight after 5s drain",
            target="jetson_ssh",
        )
    required = _LANGGRAPH_REQUIRED_STAGES
    expected_engine = "langgraph"
    if allow_fallback:
        required = _FALLBACK_REQUIRED_STAGES
        expected_engine = None  # rule_brain or langgraph_degraded both OK
    missing = [s for s in required if s not in stages]
    if missing:
        return CheckResult(
            name="brain_trace_pipeline", status="fail",
            detail=f"trace missing stages: {missing}; got {stages}",
            target="jetson_ssh",
        )
    if expected_engine and engine != expected_engine:
        return CheckResult(
            name="brain_trace_pipeline", status="fail",
            detail=f"engine={engine}, expected {expected_engine}",
            fix_hint="OpenRouter key / network? or use --allow-fallback",
            target="jetson_ssh",
        )
    if allow_fallback:
        return CheckResult(
            name="brain_trace_pipeline", status="warn",
            detail=f"FALLBACK ACCEPTED: {fallback_reason or '(no reason)'}; engine={engine}",
            target="jetson_ssh",
        )
    return CheckResult(
        name="brain_trace_pipeline", status="pass",
        detail=f"engine={engine}, stages={'->'.join(stages)}",
        target="jetson_ssh",
    )
```

- [ ] **Step 3：跑 test + commit**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -20
cd ../..

git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight checks #6-#10 (post-start ROS topology + trace)

- conversation_graph_alive: ros2 node list + topic info /brain/text_input
- chat_candidate_publisher_unique / tts_publisher_unique /
  tts_playing_state_available: 共用 _check_unique_publisher
- brain_trace_pipeline: topic pub __preflight_ping__ + parse stage 序列；
  fallback PASS 條件分支（rule_brain engine + 3 stages）。"
```

---

## Task 2A.9：preflight runner + CLI 主入口 + 輸出格式

**Files：**
- Modify：`preflight.py`、`tools/pawai_cli/pawai_cli/main.py`
- Modify：`test_preflight.py`

- [ ] **Step 1：寫 runner test**

Append `test_preflight.py`：

```python
def test_run_mechanical_pre_start_only(monkeypatch):
    """--target jetson --pre-start-only 只跑 5 條 pre-start。"""
    monkeypatch.setenv("OPENROUTER_KEY", "sk-or-xxx")
    monkeypatch.setattr(preflight, "_ssh_run",
        lambda cmd, **kw: MagicMock(returncode=0, stdout="", stderr=""))
    monkeypatch.setattr(preflight, "check_persona_no_banned",
        lambda *a, **kw: preflight.CheckResult(name="persona_loaded_no_banned", status="pass"))
    monkeypatch.setattr(preflight, "check_pose_grounding",
        lambda *a, **kw: preflight.CheckResult(name="pose_grounding_code_ready", status="pass"))
    results = preflight.run_mechanical(phase="pre_start", target="jetson")
    names = [r.name for r in results]
    assert "imports" in names
    assert "env_key" in names
    assert "persona_loaded_no_banned" in names
    assert "pose_grounding_code_ready" in names
    assert "legacy_processes_not_running" in names
    # post-start 不該出現
    assert "tts_publisher_unique" not in names
    assert "brain_trace_pipeline" not in names
    assert len(results) == 5


def test_run_mechanical_post_start_only(monkeypatch):
    monkeypatch.setattr(preflight, "_ssh_run",
        lambda cmd, **kw: MagicMock(returncode=0,
            stdout="Node name: conversation_graph_node\n", stderr=""))
    results = preflight.run_mechanical(phase="post_start", target="jetson",
        allow_fallback=True, fallback_reason="dev")
    names = [r.name for r in results]
    assert "conversation_graph_alive" in names
    assert "imports" not in names
    assert len(results) == 5


def test_run_mechanical_all_skips_non_target(monkeypatch):
    """target=local 下 jetson_ssh checks 標 SKIP。"""
    monkeypatch.setenv("OPENROUTER_KEY", "sk-or-xxx")
    monkeypatch.setattr(preflight, "check_persona_no_banned",
        lambda *a, **kw: preflight.CheckResult(name="persona_loaded_no_banned", status="pass"))
    results = preflight.run_mechanical(phase="all", target="local")
    skipped = [r for r in results if r.is_skip()]
    # imports/pose_grounding/legacy_processes/conversation_graph_alive/...
    # 全部 jetson_ssh check 應被跳過；只 env_key + persona scoped scan 真跑
    assert len(skipped) >= 5
```

- [ ] **Step 2：實作 runner + 輸出**

Append `preflight.py`：

```python
_PRE_START_CHECKS = (
    "imports", "env_key", "persona_loaded_no_banned",
    "pose_grounding_code_ready", "legacy_processes_not_running",
)
_POST_START_CHECKS = (
    "conversation_graph_alive", "brain_trace_pipeline",
    "chat_candidate_publisher_unique", "tts_publisher_unique",
    "tts_playing_state_available",
)

_PERSONA_PATH = Path("pawai_brain/personas/v1/CAPABILITIES.md")


def run_mechanical(
    phase: str = "all",  # pre_start / post_start / all
    target: Target = "jetson",
    allow_fallback: bool = False,
    fallback_reason: str = "",
    skip: Optional[set[str]] = None,
) -> list[CheckResult]:
    """Run mechanical checks per Spec A §7."""
    skip = skip or set()
    results: list[CheckResult] = []

    def _maybe(check_name: str, runner, target_kind: str):
        if check_name in skip:
            results.append(CheckResult(name=check_name, status="skip",
                detail="--skip"))
            return
        if target == "local" and target_kind == "jetson_ssh":
            results.append(CheckResult(name=check_name, status="skip",
                detail="target=local; jetson_ssh check skipped"))
            return
        results.append(runner())

    if phase in ("pre_start", "all"):
        _maybe("imports", lambda: check_imports(target=target), "jetson_ssh")
        _maybe("env_key",
            lambda: check_env_key(allow_fallback=allow_fallback,
                                  fallback_reason=fallback_reason),
            "local")
        _maybe("persona_loaded_no_banned",
            lambda: check_persona_no_banned(_PERSONA_PATH), "local")
        _maybe("pose_grounding_code_ready",
            lambda: check_pose_grounding(target=target), "jetson_ssh")
        _maybe("legacy_processes_not_running",
            lambda: check_legacy_processes(target=target), "jetson_ssh")
    if phase in ("post_start", "all"):
        _maybe("conversation_graph_alive",
            check_conversation_graph_alive, "jetson_ssh")
        _maybe("brain_trace_pipeline",
            lambda: check_brain_trace_pipeline(
                allow_fallback=allow_fallback,
                fallback_reason=fallback_reason),
            "jetson_ssh")
        _maybe("chat_candidate_publisher_unique",
            check_chat_candidate_publisher_unique, "jetson_ssh")
        _maybe("tts_publisher_unique",
            check_tts_publisher_unique, "jetson_ssh")
        _maybe("tts_playing_state_available",
            check_tts_playing_state_available, "jetson_ssh")
    return results


def format_report(results: list[CheckResult]) -> str:
    """Spec A §7.4 純 ASCII 表格。"""
    lines = []
    lines.append(f"PawAI Demo Preflight — {len(results)} checks")
    lines.append("")
    total = len(results)
    for idx, r in enumerate(results, start=1):
        status_str = r.status.upper().ljust(4)
        line = f"[{idx}/{total}] {r.name:<38} {status_str}  {r.detail}"
        lines.append(line)
        if r.is_fail() and r.fix_hint:
            lines.append(f"        → {r.fix_hint}")
    s = summarize(results)
    lines.append("")
    lines.append(f"RESULT: {s.pass_count} PASS / {s.fail_count} FAIL "
                 f"/ {s.warn_count} WARN / {s.skip_count} SKIP")
    return "\n".join(lines)
```

- [ ] **Step 3：把 click 子命令加進 `main.py`**

讀現況：

```bash
grep -nE "^@cli.|^def demo|click.command" tools/pawai_cli/pawai_cli/main.py | head -20
```

在 `main.py` 找到 `demo` group 定義處（既有），新增子命令：

```python
# tools/pawai_cli/pawai_cli/main.py — 在 demo group 內加（與既有 demo start / stop 同一 group）

import click
from . import preflight as _preflight


@demo.command("preflight")
@click.option("--target", type=click.Choice(["jetson", "local", "both"]),
              default="jetson", show_default=True,
              help="local: 跳過所有 jetson_ssh check 標 SKIP")
@click.option("--pre-start-only", "phase_flag", flag_value="pre_start")
@click.option("--post-start-only", "phase_flag", flag_value="post_start")
@click.option("--semantic", is_flag=True,
              help="Semantic dry-run 6 scripts (PR 2B)")
@click.option("--allow-fallback", is_flag=True,
              help="Accept LLM fallback (rule_brain) as WARN; reason required")
@click.option("--reason", default="",
              help="Reason for --allow-fallback or --semantic (mandatory)")
@click.option("--skip", multiple=True,
              help="Skip specific check by name (repeatable)")
def demo_preflight(target, phase_flag, semantic, allow_fallback, reason, skip):
    """Spec A — pawai demo preflight。

    Mechanical (預設)：10 條檢查。
    --semantic：6 scripts 語音 dry-run（PR 2B 提供）。
    """
    if allow_fallback and not reason:
        raise click.UsageError("--allow-fallback requires --reason \"<text>\"")
    if semantic and not reason:
        raise click.UsageError("--semantic requires --reason \"<text>\"")
    if semantic:
        # PR 2B 實作
        from . import preflight as p
        if not hasattr(p, "run_semantic"):
            raise click.ClickException(
                "Semantic dry-run not yet available (PR 2B); use mechanical only"
            )
        results = p.run_semantic(reason=reason)
    else:
        phase = phase_flag or "all"
        results = _preflight.run_mechanical(
            phase=phase,
            target=target,
            allow_fallback=allow_fallback,
            fallback_reason=reason,
            skip=set(skip),
        )
    click.echo(_preflight.format_report(results))
    summary = _preflight.summarize(results)
    raise SystemExit(summary.exit_code)
```

- [ ] **Step 4：跑 test 與 CLI 自驗**

```bash
cd tools/pawai_cli && python -m pytest tests/test_preflight.py -v 2>&1 | tail -10
python -m pawai_cli.main demo preflight --target local 2>&1 | tail -15
cd ../..
```

Expected：unit test 全綠；`--target local` 跑出至少 5 個 SKIP + 2 個 PASS（env_key + persona）。

- [ ] **Step 5：commit**

```bash
git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_preflight.py
git commit -m "spec-a/pr2a: preflight runner + CLI demo preflight

run_mechanical(phase, target, allow_fallback, skip)；ASCII 報告；
--target local 跳過 jetson_ssh 標 SKIP；--allow-fallback/--semantic
均需 --reason；exit code = 1 if any FAIL else 0。"
```

---

## Task 2A.10：`demo start` 雙階段 hook + `release_if_owned` 整合 + 對應 test

**Files：**
- Modify：`tools/pawai_cli/pawai_cli/main.py`（既有 `demo start`）
- Create：`tools/pawai_cli/tests/test_demo_start_hook.py`

- [ ] **Step 1：寫 test 先**

Create `tools/pawai_cli/tests/test_demo_start_hook.py`：

```python
"""Spec A `demo start` 雙階段 preflight hook 順序 + release_if_owned 行為。"""

from unittest.mock import MagicMock, patch
import pytest

# 假設 main.py 內 demo_start 邏輯可透過 CliRunner 模擬
from click.testing import CliRunner
from pawai_cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


def _mock_check(name, status):
    from pawai_cli.preflight import CheckResult
    return CheckResult(name=name, status=status)


def _fake_lk(user="alice", host="laptop1"):
    """Create a fake Lock instance with transition_if_owned bound."""
    lk = MagicMock()
    lk.user = user
    lk.host = host
    lk.transition_if_owned = MagicMock(return_value=True)
    return lk


def test_pre_start_fail_does_not_acquire_lock(runner, monkeypatch):
    """pre-start fail → exit 1，不應呼叫 Lock.acquire。"""
    calls = []
    monkeypatch.setattr("pawai_cli.preflight.run_mechanical",
        lambda phase, **kw: [_mock_check("imports", "fail")] if phase == "pre_start" else [])

    def fake_acquire(**kw):
        calls.append("acquire")
        return _fake_lk()
    # Lock.acquire 是 classmethod，patch class attribute
    monkeypatch.setattr("pawai_cli.lock.Lock.acquire", fake_acquire)

    result = runner.invoke(cli, ["demo", "start"])
    assert result.exit_code != 0
    assert "acquire" not in calls


def test_post_start_fail_cleanup_release(runner, monkeypatch):
    """post-start fail → cleanup + Lock.release_if_owned，不留 lock；
    必須是 acquire → start.sh → cleanup → release_if_owned 順序。"""
    calls = []

    def fake_pre(*a, **kw): return [_mock_check("imports", "pass")]
    def fake_post(*a, **kw): return [_mock_check("tts_publisher_unique", "fail")]

    def fake_acquire(**kw):
        calls.append("acquire")
        return _fake_lk(user="alice", host="laptop1")

    def fake_start_sh(*a, **kw):
        calls.append("start.sh")
        return 0

    def fake_cleanup(*a, **kw):
        calls.append("cleanup")

    def fake_release(**kw):
        calls.append(f"release_if_owned(user={kw.get('user')}, host={kw.get('host')})")
        return True

    monkeypatch.setattr("pawai_cli.preflight.run_mechanical",
        lambda phase, **kw: fake_pre() if phase == "pre_start" else fake_post())
    monkeypatch.setattr("pawai_cli.lock.Lock.acquire", fake_acquire)
    monkeypatch.setattr("pawai_cli.main._run_start_sh", fake_start_sh)
    monkeypatch.setattr("pawai_cli.main._cleanup_demo_stack", fake_cleanup)
    monkeypatch.setattr("pawai_cli.lock.Lock.release_if_owned", fake_release)

    result = runner.invoke(cli, ["demo", "start"])
    assert result.exit_code != 0
    # 嚴格順序：acquire 在前、release_if_owned 在後且帶 owner kwargs
    assert calls[0] == "acquire"
    assert calls[1] == "start.sh"
    assert calls[2] == "cleanup"
    assert calls[3].startswith("release_if_owned(user=alice")


def test_orphan_preflight_runs_before_pre_start_preflight(runner, monkeypatch):
    """既有 orphan preflight 必須在 spec-a pre-start preflight 之前。"""
    calls = []

    def fake_orphan(*a, **kw):
        calls.append("orphan_preflight")

    def fake_pre(phase, **kw):
        calls.append(f"preflight:{phase}")
        return [_mock_check("imports", "pass")]

    monkeypatch.setattr("pawai_cli.main._orphan_driver_preflight", fake_orphan)
    monkeypatch.setattr("pawai_cli.preflight.run_mechanical", fake_pre)
    monkeypatch.setattr("pawai_cli.lock.Lock.acquire",
        lambda **kw: _fake_lk(user="x", host="y"))
    monkeypatch.setattr("pawai_cli.main._run_start_sh", lambda *a, **kw: 0)
    monkeypatch.setattr("pawai_cli.main._wait_for_ready", lambda *a, **kw: True)

    runner.invoke(cli, ["demo", "start"])
    orphan_idx = calls.index("orphan_preflight")
    pre_idx = calls.index("preflight:pre_start")
    assert orphan_idx < pre_idx


def test_transition_to_running_uses_instance_method(runner, monkeypatch):
    """post-start PASS 後必須走 lk.transition_if_owned('running', user=, host=)。"""
    monkeypatch.setattr("pawai_cli.preflight.run_mechanical",
        lambda phase, **kw: [_mock_check("imports", "pass")])
    lk = _fake_lk(user="alice", host="laptop1")
    monkeypatch.setattr("pawai_cli.lock.Lock.acquire", lambda **kw: lk)
    monkeypatch.setattr("pawai_cli.main._run_start_sh", lambda *a, **kw: 0)
    monkeypatch.setattr("pawai_cli.main._wait_for_ready", lambda *a, **kw: True)

    runner.invoke(cli, ["demo", "start"])
    # lk.transition_if_owned 至少被 call 一次，且帶 ("running", user=, host=)
    assert lk.transition_if_owned.called
    args, kwargs = lk.transition_if_owned.call_args
    assert args[0] == "running"
    assert kwargs.get("user") == "alice"
    assert kwargs.get("host") == "laptop1"


def test_no_naked_lock_release_on_failure(runner, monkeypatch):
    """任何 post-lock 失敗都不該走 Lock.release() 裸版本。"""
    naked_called = []

    monkeypatch.setattr("pawai_cli.preflight.run_mechanical",
        lambda phase, **kw: ([_mock_check("imports", "pass")] if phase == "pre_start"
                             else [_mock_check("tts_publisher_unique", "fail")]))
    monkeypatch.setattr("pawai_cli.lock.Lock.acquire",
        lambda **kw: _fake_lk(user="x", host="y"))
    monkeypatch.setattr("pawai_cli.main._run_start_sh", lambda *a, **kw: 0)
    monkeypatch.setattr("pawai_cli.main._cleanup_demo_stack", lambda *a, **kw: None)
    monkeypatch.setattr("pawai_cli.lock.Lock.release_if_owned",
        lambda **kw: True)
    # 任何呼叫 Lock.release() 都記為違規
    monkeypatch.setattr("pawai_cli.lock.Lock.release",
        lambda: naked_called.append("naked_release"))

    runner.invoke(cli, ["demo", "start"])
    assert naked_called == []
```

- [ ] **Step 2：實作 hook（修改既有 `demo start`）**

讀現況：

```bash
grep -nE "def demo_start|orphan|acquire|transition_if_owned|release_if_owned" tools/pawai_cli/pawai_cli/main.py | head -30
```

在 `demo start` 函式內，於既有 orphan preflight 與 acquire lock 之間插入 pre-start preflight；於 `wait_for_ready` 與 `transition_if_owned("running")` 之間插入 post-start preflight。

Sketch（細節以實際 main.py 為準）：

```python
# main.py demo start handler 內，依 Spec A §7.5 順序
# 真實 API（驗於 lock.py + main.py:851/874/877/900/903/956）：
#   Lock.read()                                       classmethod
#   Lock.acquire(user=..., host=..., branch=..., sha=..., state="starting", ...)
#                                                     classmethod，回 instance lk
#   lk.transition_if_owned("running", user=user, host=host)
#                                                     instance method
#   Lock.release_if_owned(user=..., host=...)         classmethod
#   Lock.release()                                    legacy classmethod — **禁用**

from pawai_cli.lock import Lock


def demo_start(...):
    lock_state = Lock.read()
    # 既有：lock state routing / orphan preflight / -y / --force
    _orphan_driver_preflight(...)
    _handle_force_or_yes(...)

    # ★ Spec A pre-start preflight（未取 lock，fail 直接 exit）
    pre_results = preflight.run_mechanical(phase="pre_start", target="jetson")
    if not preflight.summarize(pre_results).all_passed:
        click.echo(preflight.format_report(pre_results), err=True)
        raise SystemExit(1)

    # 既有：acquire lock + start.sh
    lk = Lock.acquire(user=user, host=host, branch=branch, sha=sha,
                      state="starting", ...)
    rc = _run_start_sh(...)
    if rc != 0:
        # 既有失敗路徑（已在 caef6b5 前就 owner-aware）
        _cleanup_demo_stack(...)
        Lock.release_if_owned(user=user, host=host)
        raise SystemExit(rc)

    _wait_for_ready(...)

    # ★ Spec A post-start preflight
    post_results = preflight.run_mechanical(
        phase="post_start", target="jetson",
        allow_fallback=allow_fallback, fallback_reason=reason,
    )
    if not preflight.summarize(post_results).all_passed:
        click.echo(preflight.format_report(post_results), err=True)
        click.echo("post-start preflight failed; stack and lock cleaned up. "
                   "Fix the failing checks and re-run `pawai demo start`.", err=True)
        _cleanup_demo_stack(...)
        Lock.release_if_owned(user=user, host=host)
        raise SystemExit(1)

    # 既有：lk.transition_if_owned("running", user=user, host=host)
    if not lk.transition_if_owned("running", user=user, host=host):
        # 既有保留行為：lock 被別人接管，不 mark running
        click.echo("lock taken over during startup, NOT marking running", err=True)
        raise SystemExit(2)
```

**禁止**：
- `Lock.release()`（裸 release，無 owner check）
- 引用 `lock.release_if_owned(...)` 形式（無 `Lock.`）— 它不是 module-level function
- 引用 `lock.acquire_or_force(...)` — 此 API 不存在

- [ ] **Step 3：跑 test**

```bash
cd tools/pawai_cli && python -m pytest tests/test_demo_start_hook.py -v 2>&1 | tail -20
cd ../..
```

Expected：4 tests pass。

- [ ] **Step 4：commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_demo_start_hook.py
git commit -m "spec-a/pr2a: demo start 雙階段 preflight hook + release_if_owned

順序：orphan preflight → pre_start preflight → acquire lock → start.sh
      → wait_for_ready → post_start preflight → transition_if_owned(running)
pre-start fail → exit 1（無 lock）
post-start fail → cleanup + release_if_owned + exit 1
禁裸 Lock.release()。"
```

---

## Task 2A.11：Executive runtime TTS guard timer + test

**Files：**
- Modify：`interaction_executive/interaction_executive/brain_node.py`
- Create：`interaction_executive/test/test_tts_guard_timer.py`

- [ ] **Step 1：寫 test**

Create `interaction_executive/test/test_tts_guard_timer.py`：

```python
"""Spec A Executive runtime TTS guard timer."""

from unittest.mock import MagicMock, patch
import time

import pytest


@pytest.fixture
def brain_node_with_guard(monkeypatch):
    # 用最小化 stub 構造 brain_node，重點測 _tts_publisher_audit 邏輯
    from interaction_executive import brain_node as bn

    node = MagicMock()
    node.get_name.return_value = "interaction_executive_node"
    node.get_logger.return_value = MagicMock()
    node._last_tts_guard_violation_ts = 0.0
    node._last_tts_guard_violation_set = frozenset()
    return bn, node


def test_no_foreign_publisher_silent(brain_node_with_guard):
    bn, node = brain_node_with_guard
    node.get_publishers_info_by_topic.return_value = [
        MagicMock(node_name="interaction_executive_node"),
    ]
    bn.BrainNode._tts_publisher_audit(node)
    # 無 ERROR log
    node.get_logger().error.assert_not_called()


def test_foreign_publisher_logged_once(brain_node_with_guard):
    bn, node = brain_node_with_guard
    node.get_publishers_info_by_topic.return_value = [
        MagicMock(node_name="interaction_executive_node"),
        MagicMock(node_name="event_action_bridge"),
    ]
    bn.BrainNode._tts_publisher_audit(node)
    assert node.get_logger().error.called
    # 立即第二次呼叫同樣的 foreign set — 60s 內不該重複 log
    node.get_logger().error.reset_mock()
    bn.BrainNode._tts_publisher_audit(node)
    node.get_logger().error.assert_not_called()


def test_foreign_set_changes_relogs(brain_node_with_guard):
    bn, node = brain_node_with_guard
    node.get_publishers_info_by_topic.return_value = [
        MagicMock(node_name="interaction_executive_node"),
        MagicMock(node_name="event_action_bridge"),
    ]
    bn.BrainNode._tts_publisher_audit(node)
    node.get_logger().error.reset_mock()
    # 違規 set 變了，應該再 log
    node.get_publishers_info_by_topic.return_value = [
        MagicMock(node_name="interaction_executive_node"),
        MagicMock(node_name="llm_bridge_node"),
    ]
    bn.BrainNode._tts_publisher_audit(node)
    node.get_logger().error.assert_called()


def test_trace_published_on_violation(brain_node_with_guard):
    bn, node = brain_node_with_guard
    node._trace_pub = MagicMock()
    node.get_publishers_info_by_topic.return_value = [
        MagicMock(node_name="interaction_executive_node"),
        MagicMock(node_name="event_action_bridge"),
    ]
    bn.BrainNode._tts_publisher_audit(node)
    node._trace_pub.publish.assert_called()
    call_arg = node._trace_pub.publish.call_args[0][0]
    # 訊息應含 stage='tts_guard'
    assert "tts_guard" in str(call_arg.data)
```

- [ ] **Step 2：實作（修改 `brain_node.py`）**

讀現況：

```bash
grep -nE "class BrainNode|def __init__|create_timer|create_publisher.*trace" interaction_executive/interaction_executive/brain_node.py | head -20
```

在 `BrainNode.__init__` 內加：

```python
# Spec A §4 — TTS publisher runtime guard timer
self._last_tts_guard_violation_ts: float = 0.0
self._last_tts_guard_violation_set: frozenset[str] = frozenset()
self._tts_guard_dedup_window_s: float = 60.0
if self.declare_parameter("enable_tts_guard", True).value:
    self.create_timer(5.0, self._tts_publisher_audit)
```

在 class 內加 method：

```python
def _tts_publisher_audit(self) -> None:
    """Spec A §4 — runtime guard timer：detect-only，不 kill。"""
    import time
    try:
        pubs = self.get_publishers_info_by_topic("/tts")
    except Exception as exc:
        self.get_logger().debug(f"tts_guard probe failed: {exc}")
        return
    foreign = frozenset(
        p.node_name for p in pubs
        if p.node_name != self.get_name()
    )
    now = time.time()
    if not foreign:
        # 復原時清掉去重 cache
        self._last_tts_guard_violation_set = frozenset()
        return
    if (foreign == self._last_tts_guard_violation_set
            and (now - self._last_tts_guard_violation_ts) < self._tts_guard_dedup_window_s):
        return
    self._last_tts_guard_violation_set = foreign
    self._last_tts_guard_violation_ts = now
    msg = f"Foreign /tts publishers detected: {sorted(foreign)}"
    self.get_logger().error(msg)
    # 發 trace warning
    if hasattr(self, "_trace_pub") and self._trace_pub is not None:
        from std_msgs.msg import String
        import json
        trace_msg = String()
        trace_msg.data = json.dumps({
            "stage": "tts_guard",
            "status": "warn",
            "foreign_publishers": sorted(foreign),
        }, ensure_ascii=False)
        self._trace_pub.publish(trace_msg)
```

- [ ] **Step 3：跑 test**

```bash
cd interaction_executive && python -m pytest test/test_tts_guard_timer.py -v 2>&1 | tail -10
cd ..
```

- [ ] **Step 4：commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py interaction_executive/test/test_tts_guard_timer.py
git commit -m "spec-a/pr2a: Executive TTS guard timer (5s polling, 60s dedup)

detect-only：foreign /tts publisher 出現時 log ERROR + trace warning
stage=tts_guard；不 kill node。enable_tts_guard ROS param 預設 True，
可關閉。"
```

---

## Task 2A.12：`start_full_demo_tmux.sh` `.env` propagation + 停用 event_action_bridge

**Files：**
- Modify：`scripts/start_full_demo_tmux.sh`

- [ ] **Step 1：讀現況 — `.env` 處理與 event_action_bridge 啟動指令**

```bash
grep -nE "set -a|source.*env|event_action_bridge|ROS_SETUP" scripts/start_full_demo_tmux.sh | head -20
```

- [ ] **Step 2：在 `ROS_SETUP` 共用片段內加 `.env` propagation**

定位 `ROS_SETUP` 變數定義（通常為多行字串），改為（保留既有 source 行）：

```bash
ROS_SETUP='
set -a
[ -f "$WORKDIR/.env" ] && . "$WORKDIR/.env" || echo "[WARN] .env not found at $WORKDIR/.env" >&2
[ -f "$WORKDIR/.env.local" ] && . "$WORKDIR/.env.local" || true
set +a
source /opt/ros/humble/setup.bash
source "$WORKDIR/install/setup.bash"
'
```

注意：用單引號包字串，避免 `$OPENROUTER_KEY` 在父 shell 提前展開。

- [ ] **Step 3：停用 `event_action_bridge` 啟動**

找到啟動 `event_action_bridge` 的 line（grep 確認），改為註解（保留註解說明）：

```bash
# Spec A §4 — demo 主線不啟 event_action_bridge（避免 /tts 雙路）
# tmux send-keys -t "${SESSION}:vision" 'ros2 run vision_perception event_action_bridge' C-m
```

獨立 commit：

```bash
git add scripts/start_full_demo_tmux.sh
git commit -m "spec-a: keep event_action_bridge out of demo mainline

Spec A §4 — demo runtime 不啟 event_action_bridge，避免 /tts 第二
publisher slot；code 不動，legacy/debug 可手動啟。"
```

- [ ] **Step 4：commit `.env` 改動**

```bash
git add scripts/start_full_demo_tmux.sh
git commit -m "spec-a/pr2a: start_full_demo_tmux .env cross-pane propagation

ROS_SETUP 共用片段：set -a; source .env / .env.local; set +a。
單引號包字串避免父 shell 提前展開 OPENROUTER_KEY。
CRLF 防護沿用 PR67 cherry-pick #2 的 tr -d '\\r'（不在本 PR 動）。"
```

兩個獨立 commit；可分 2 步做。

---

## Task 2A.13：PR 2A 整合測試 + push + 開 PR

- [ ] **Step 1：跑全套相關 tests**

```bash
cd tools/pawai_cli && python -m pytest tests/ -v 2>&1 | tail -20
cd ../interaction_executive && python -m pytest test/ -v 2>&1 | tail -10
cd ..
```

Expected：既有 + 新增 test 全綠。

- [ ] **Step 2：本機 dry-run CLI**

```bash
JETSON_HOST=jetson-nano python -m tools.pawai_cli.pawai_cli.main demo preflight --target local 2>&1 | tail -20
```

Expected：jetson_ssh checks 標 SKIP；env_key + persona_loaded_no_banned 真跑。

- [ ] **Step 3：push + 開 PR**

```bash
git push -u origin spec-a/pr2a-mechanical-guard
gh pr create --base main --head spec-a/pr2a-mechanical-guard \
  --title "spec-a/pr2a: runtime mechanical guard — preflight + Executive TTS guard" \
  --body "$(cat <<'EOF'
## Summary

Spec A PR 群 2A — runtime mechanical guard。對應 spec §2 / §4 / §7。

主要新增：
- `tools/pawai_cli/pawai_cli/preflight.py`：10 條 mechanical checks（5 pre-start + 5 post-start）+ runner + ASCII 報告
- `pawai demo preflight` CLI 子命令（含 `--target` / `--allow-fallback` / `--reason`）
- `pawai demo start` 雙階段 hook：orphan → pre-start → lock → start.sh → wait → post-start → transition(running)
- Executive TTS guard timer：5s polling、60s 去重、發 trace `tts_guard` warning
- `start_full_demo_tmux.sh`：`.env` cross-pane propagation；停用 `event_action_bridge` 啟動（獨立 commit）

## Test plan
- [x] preflight unit tests（10 checks）
- [x] persona scoped scan 5 case
- [x] demo start hook 順序 + release_if_owned 行為 4 case
- [x] TTS guard timer 4 case
- [x] dev 機 `--target local` smoke 通過

## 不回退
- 不動 lock corruption fix (`b05205d`~`84f201f`)
- 不動 orphan preflight (`b05205d`)
- 不動 IP override (`8ac67a7`)
- 不動 CRLF / BOM (`caef6b5`)

Spec：docs/pawai-brain/specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md
EOF
)"
```

- [ ] **Step 4：merge 後**

```bash
git checkout main && git pull --ff-only
```

---

# PR 群 2B：Semantic Dry-Run

**Branch**：`spec-a/pr2b-semantic-dryrun`
**Base**：PR 2A merged
**估行數**：~300-400

---

## Task 2B.1：建 branch

- [ ] **Step 1**

```bash
git checkout main && git pull --ff-only
git checkout -b spec-a/pr2b-semantic-dryrun
```

---

## Task 2B.2：確認 `runtime/` 在 `.gitignore`

- [ ] **Step 1：grep**

```bash
grep -nE "^runtime/?|^/runtime/?" .gitignore || echo "MISSING"
```

- [ ] **Step 2：若 MISSING，append**

```bash
echo -e "\n# Spec A runtime artifacts\nruntime/" >> .gitignore
git add .gitignore
git commit -m "spec-a/pr2b: .gitignore runtime/ (preflight semantic reports)"
```

若已存在，跳過此 commit。

---

## Task 2B.3：semantic dry-run skeleton + 6 scripts 定義

**Files：**
- Modify：`tools/pawai_cli/pawai_cli/preflight.py`
- Create：`tools/pawai_cli/tests/test_semantic_dryrun.py`

- [ ] **Step 1：寫 test**

Create `tools/pawai_cli/tests/test_semantic_dryrun.py`：

```python
"""Spec A §8 semantic dry-run — 6 scripts 結構與 banned/required pattern 邏輯。"""

from unittest.mock import MagicMock, patch
from pawai_cli import preflight


def test_six_scripts_defined():
    scripts = preflight.SEMANTIC_SCRIPTS
    names = [s["id"] for s in scripts]
    assert names == ["1", "2", "3", "4", "5", "5b"]


def test_global_banned_patterns():
    bans = preflight.GLOBAL_BANNED_REPLY_PATTERNS
    assert "我會跟著你" in bans
    assert "我會巡邏" in bans
    assert "進入監聽模式" in bans
    # 不是 ban 單詞
    assert "跟隨" not in bans
    assert "巡邏" not in bans


def test_global_banned_proposed_skills():
    assert preflight.GLOBAL_BANNED_SKILLS == frozenset({
        "follow_me", "follow_person", "patrol_route",
        "enter_mute_mode", "enter_listen_mode",
    })


def test_pattern_check_pass_for_clean_reply():
    reply = "嗨！很高興看到你。"
    result = preflight.evaluate_reply(
        reply=reply, proposed_skill="chat_reply", script_id="1",
    )
    assert result["banned_grep"] == "PASS"
    assert result["skill_blacklist"] == "PASS"


def test_pattern_check_fail_on_promise():
    reply = "好啊我會跟著你走，沒問題。"
    result = preflight.evaluate_reply(
        reply=reply, proposed_skill="chat_reply", script_id="5b",
    )
    assert result["banned_grep"] == "FAIL"
    assert "我會跟著你走" in result["banned_grep_detail"]


def test_skill_blacklist_fail():
    result = preflight.evaluate_reply(
        reply="ok", proposed_skill="follow_me", script_id="1",
    )
    assert result["skill_blacklist"] == "FAIL"


def test_script_2_word_count_warn_zone(monkeypatch):
    reply = "我是 PawAI，我可以聽你說、看你比手勢、認得你和家人；Studio 上能看到我每步決策。"  # ~50 字
    result = preflight.evaluate_reply(reply=reply, proposed_skill="chat_reply", script_id="2")
    # 50 字 < 60 hard fail
    assert result["required_grep"] in ("WARN", "FAIL")


def test_pose_injection_skipped_when_live_publisher(monkeypatch):
    monkeypatch.setattr(preflight, "_jetson_topic_has_live_publisher",
        lambda topic: True)
    skipped = preflight.maybe_inject_pose("sitting", force=False)
    assert skipped is False
    # force=True 才執行
    monkeypatch.setattr(preflight, "_jetson_run_pub",
        lambda *a, **kw: True)
    assert preflight.maybe_inject_pose("sitting", force=True) is True
```

- [ ] **Step 2：實作 SEMANTIC_SCRIPTS + evaluate_reply + maybe_inject_pose**

Append to `preflight.py`：

```python
# ============================================================
# Spec A §8 — Semantic dry-run
# ============================================================

GLOBAL_BANNED_REPLY_PATTERNS: tuple[str, ...] = (
    r"我會跟著你",
    r"可以跟著你",
    r"我能跟隨",
    r"我會巡邏",
    r"可以巡邏",
    r"我會靜音",
    r"我會進入監聽模式",
    r"come here",
    r"circle",
    r"畫圈.*跳舞",
    r"勾手.*跟隨",
)

GLOBAL_BANNED_SKILLS = frozenset({
    "follow_me", "follow_person", "patrol_route",
    "enter_mute_mode", "enter_listen_mode",
})

SCRIPT_5B_BANNED: tuple[str, ...] = (
    r"我會跟著你走", r"我可以跟著你走",
    r"我會靠近你", r"我可以自己找你",
)
SCRIPT_5B_BANNED_SKILLS = frozenset({"follow_me", "follow_person", "approach_person"})

SEMANTIC_SCRIPTS: list[dict] = [
    {"id": "1", "text": "你好", "wait_s": 8,
     "required": {"max_chars": 50},
     "banned_extra": ()},
    {"id": "2", "text": "介紹一下自己", "wait_s": 12,
     "required": {
         "min_chars": 60, "max_chars": 240,
         "warn_below": 80, "warn_above": 180,
         "keyword_groups": [
             ["人臉", "認人"],
             ["語音", "聽你"],
             ["手勢"],
             ["姿勢", "動作"],
             ["物體", "東西"],
             ["Studio", "Brain"],
         ],
         "min_groups_hit": 5,
     },
     "banned_extra": ()},
    {"id": "3", "text": "你會什麼", "wait_s": 10,
     "required": {
         "or_pass": {
             "any_of": ["還在測試", "目前不展示", "保守處理", "demo 不主動"],
             "absent_all_of": ["follow_me", "patrol_route", "enter_mute_mode",
                              "enter_listen_mode", "跟隨", "巡邏", "靜音", "監聽"],
         },
     },
     "banned_extra": ()},
    {"id": "4", "text": "我在幹嘛", "wait_s": 10,
     "pose_inject": "sitting", "pose_delay_s": 5,
     "required": {"must_contain": "坐"},
     "banned_extra": ()},
    {"id": "5", "text": "你看到什麼", "wait_s": 10,
     "required": {
         "world_state_dependent": True,
         "if_no_object": {"any_of": ["沒看到", "不確定", "目前看不到"]},
     },
     "banned_extra": ()},
    {"id": "5b", "text": "你會跟我走嗎", "wait_s": 10,
     "required": {"any_of": ["目前不主動承諾", "還在測試", "demo 先不展示"]},
     "banned_extra": SCRIPT_5B_BANNED,
     "banned_skills_extra": SCRIPT_5B_BANNED_SKILLS},
]


def evaluate_reply(
    *,
    reply: str,
    proposed_skill: str,
    script_id: str,
    world_state_has_object: Optional[bool] = None,
) -> dict:
    """跑全域 + per-script banned/required check。"""
    out: dict = {}
    spec = next((s for s in SEMANTIC_SCRIPTS if s["id"] == script_id), None)
    if spec is None:
        raise ValueError(f"unknown script_id {script_id!r}")

    # banned grep
    banned_patterns = list(GLOBAL_BANNED_REPLY_PATTERNS) + list(spec.get("banned_extra", ()))
    banned_hits = [p for p in banned_patterns if re.search(p, reply)]
    out["banned_grep"] = "FAIL" if banned_hits else "PASS"
    out["banned_grep_detail"] = ", ".join(banned_hits)

    # skill blacklist
    banned_skills = GLOBAL_BANNED_SKILLS | spec.get("banned_skills_extra", frozenset())
    out["skill_blacklist"] = "FAIL" if proposed_skill in banned_skills else "PASS"

    # required
    req = spec.get("required", {})
    rv = _evaluate_required(reply, req, world_state_has_object)
    out["required_grep"] = rv["status"]
    out["required_grep_detail"] = rv.get("detail", "")

    return out


def _evaluate_required(
    reply: str, req: dict, world_state_has_object: Optional[bool],
) -> dict:
    n = len(reply)
    # 字數 hard fail
    if "min_chars" in req and n < req.get("min_chars", 0):
        return {"status": "FAIL", "detail": f"chars={n} < min {req['min_chars']}"}
    if "max_chars" in req and n > req["max_chars"]:
        return {"status": "FAIL", "detail": f"chars={n} > max {req['max_chars']}"}
    # warn 區
    warn_reasons = []
    if "warn_below" in req and n < req["warn_below"]:
        warn_reasons.append(f"chars={n} < warn_below {req['warn_below']}")
    if "warn_above" in req and n > req["warn_above"]:
        warn_reasons.append(f"chars={n} > warn_above {req['warn_above']}")
    # must_contain
    if "must_contain" in req and req["must_contain"] not in reply:
        return {"status": "FAIL", "detail": f"missing '{req['must_contain']}'"}
    # any_of
    if "any_of" in req and not any(s in reply for s in req["any_of"]):
        return {"status": "FAIL", "detail": f"no any_of: {req['any_of']}"}
    # or_pass（Script 3）
    if "or_pass" in req:
        op = req["or_pass"]
        has_degrade = any(s in reply for s in op["any_of"])
        has_no_risky = all(s not in reply for s in op["absent_all_of"])
        if not (has_degrade or has_no_risky):
            return {"status": "FAIL",
                    "detail": "neither degrade language nor risky-free"}
    # keyword groups（Script 2）
    if "keyword_groups" in req:
        hit = sum(1 for grp in req["keyword_groups"] if any(k in reply for k in grp))
        need = req.get("min_groups_hit", len(req["keyword_groups"]))
        if hit < need:
            return {"status": "FAIL", "detail": f"keyword groups hit {hit}/{need}"}
    # world_state_dependent
    if req.get("world_state_dependent"):
        if world_state_has_object is False:
            ino = req.get("if_no_object", {})
            if not any(s in reply for s in ino.get("any_of", [])):
                return {"status": "FAIL",
                        "detail": f"no any_of: {ino.get('any_of')}"}
    if warn_reasons:
        return {"status": "WARN", "detail": "; ".join(warn_reasons)}
    return {"status": "PASS", "detail": f"chars={n}"}


def _jetson_topic_has_live_publisher(topic: str) -> bool:
    proc = _ssh_run(f"ros2 topic info {topic} -v")
    pubs = _parse_topic_info_publishers(proc.stdout)
    return bool(pubs)


def _jetson_run_pub(topic: str, msg_type: str, payload: str) -> bool:
    proc = _ssh_run(f'ros2 topic pub --once {topic} {msg_type} "{payload}"')
    return proc.returncode == 0


def maybe_inject_pose(pose: str, force: bool = False) -> bool:
    """Inject synthetic /event/pose_detected;
    若已有 live publisher，預設 skip 並回 False；force=True 強跑。

    **Schema**：canonical key 為 `pose`（與 vision_perception 真實 event 對齊，
    驗於 conversation_graph_node._on_pose_detected:955）。**不可**用 `name`，
    否則 Brain parser 認不出，synthetic event 假裝 inject 成功但 Brain cache
    無更新，script 4「我在幹嘛」會 silent false pass。
    """
    if not force and _jetson_topic_has_live_publisher("/event/pose_detected"):
        return False
    import json
    payload = json.dumps({"pose": pose, "confidence": 0.85})
    return _jetson_run_pub(
        "/event/pose_detected", "std_msgs/msg/String",
        f"data: '{payload}'",
    )
```

- [ ] **Step 3：跑 test + commit**

```bash
cd tools/pawai_cli && python -m pytest tests/test_semantic_dryrun.py -v 2>&1 | tail -15
cd ../..

git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/tests/test_semantic_dryrun.py
git commit -m "spec-a/pr2b: semantic dry-run skeleton — 6 scripts + evaluate_reply

Global banned reply/skill；per-script 字數 / any_of / or_pass / keyword_groups
/ must_contain / world_state_dependent；pose injection isolation
（live publisher 存在則 skip，--force-pose-inject 強跑）。"
```

---

## Task 2B.4：semantic runner + 報告 + CLI wiring

**Files：**
- Modify：`preflight.py`、`main.py`

- [ ] **Step 1：實作 run_semantic + 報告 writer**

Append `preflight.py`：

```python
import datetime as _dt


def run_semantic(
    reason: str,
    scripts_filter: Optional[set[str]] = None,
    force_pose_inject: bool = False,
) -> list[CheckResult]:
    """Spec A §8 — 6 scripts dry-run。"""
    results: list[CheckResult] = []
    selected = [s for s in SEMANTIC_SCRIPTS
                if scripts_filter is None or s["id"] in scripts_filter]
    for spec in selected:
        if "pose_inject" in spec:
            injected = maybe_inject_pose(spec["pose_inject"], force=force_pose_inject)
            if not injected and not force_pose_inject:
                results.append(CheckResult(
                    name=f"semantic_{spec['id']}", status="warn",
                    detail="pose injection skipped (live publisher present); "
                           "use --force-pose-inject to override",
                    target="jetson_ssh",
                ))
                continue
            import time as _t
            _t.sleep(spec.get("pose_delay_s", 5))
        # publish text input
        _ssh_run(
            f'ros2 topic pub --once /brain/text_input std_msgs/msg/String '
            f'"data: \\\"{spec["text"]}\\\""'
        )
        # collect reply
        echo = _ssh_run(
            f"timeout {spec['wait_s']} ros2 topic echo /brain/chat_candidate --once"
        )
        reply, proposed = _parse_chat_candidate(echo.stdout)
        if reply is None:
            results.append(CheckResult(
                name=f"semantic_{spec['id']}", status="fail",
                detail=f"no /brain/chat_candidate within {spec['wait_s']}s",
                target="jetson_ssh",
            ))
            continue
        ev = evaluate_reply(
            reply=reply, proposed_skill=proposed or "",
            script_id=spec["id"],
        )
        bad = any(ev[k] == "FAIL" for k in ("banned_grep", "skill_blacklist", "required_grep"))
        warn = any(ev[k] == "WARN" for k in ("banned_grep", "skill_blacklist", "required_grep"))
        status = "fail" if bad else ("warn" if warn else "pass")
        results.append(CheckResult(
            name=f"semantic_{spec['id']}", status=status,
            detail=f"reply={reply[:80]!r}; "
                   f"banned={ev['banned_grep']}; required={ev['required_grep']}; "
                   f"skill={ev['skill_blacklist']}",
            target="jetson_ssh",
        ))
    return results


def _parse_chat_candidate(stdout: str) -> tuple[Optional[str], Optional[str]]:
    """從 ros2 topic echo /brain/chat_candidate 抽 reply_text 與 proposed_skill。"""
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip().strip("'\"")
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            continue
        return obj.get("reply_text") or obj.get("reply"), obj.get("proposed_skill")
    return None, None


def write_semantic_report(
    results: list[CheckResult], reason: str,
    report_dir: Path = Path("runtime/preflight"),
) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = report_dir / f"semantic-{ts}.md"
    lines = [
        f"# PawAI Semantic Dry-Run — {ts}",
        f"Reason: {reason}",
        "",
    ]
    for r in results:
        lines.append(f"## [{r.name}]")
        lines.append(f"- status: {r.status.upper()}")
        lines.append(f"- detail: {r.detail}")
        lines.append("")
    lines.append("## 人工判讀")
    lines.append("(請操作者填入自然度 1-5 與最終判定 y/n)")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
```

- [ ] **Step 2：CLI wiring（更新 `main.py demo_preflight`）**

把 PR 2A 的 stub `from . import preflight as p; if not hasattr(p, "run_semantic")` 移除，改為直接呼叫：

```python
    if semantic:
        results = _preflight.run_semantic(
            reason=reason,
            force_pose_inject=False,  # 未來加 flag 再開
        )
        path = _preflight.write_semantic_report(results, reason)
        click.echo(_preflight.format_report(results))
        click.echo(f"\n報告已寫入：{path}")
```

- [ ] **Step 3：commit**

```bash
git add tools/pawai_cli/pawai_cli/preflight.py tools/pawai_cli/pawai_cli/main.py
git commit -m "spec-a/pr2b: semantic dry-run runner + 報告 writer + CLI wiring

run_semantic 跑 6 scripts；pose injection isolation；reply 解析；
report 寫入 runtime/preflight/semantic-<ts>.md，含人工判讀區。"
```

---

## Task 2B.5：PR 2B push + 開 PR

- [ ] **Step 1**

```bash
cd tools/pawai_cli && python -m pytest tests/ -v 2>&1 | tail -10
cd ../..
git push -u origin spec-a/pr2b-semantic-dryrun
gh pr create --base main --head spec-a/pr2b-semantic-dryrun \
  --title "spec-a/pr2b: semantic dry-run — 6 scripts + report writer" \
  --body "Spec A §8 — pawai demo preflight --semantic --reason \"<text>\"，6 scripts (5 core + 1 persona guard)，mechanical banned/required check + 報告寫 runtime/preflight/。"
```

- [ ] **Step 2：merge 後 `git checkout main && git pull --ff-only`**

---

# PR 群 3：Behavior Gate

**Branch**：`spec-a/pr3-behavior-gate`
**Base**：PR 2B merged
**估行數**：~350-500

---

## Task 3.1：建 branch + 前置 grep

- [ ] **Step 1**

```bash
git checkout main && git pull --ff-only
git checkout -b spec-a/pr3-behavior-gate
```

- [ ] **Step 2：確認 `_CONVERSATION_GATED_GESTURES` 順序仍早於 `_GESTURE_CONFIRM`**

```bash
grep -nE "_CONVERSATION_GATED_GESTURES|_GESTURE_CONFIRM" interaction_executive/interaction_executive/brain_node.py
```

Expected：line 614 gate check 早於 line 648 confirm 處理（base @ caef6b5 已確認）。

- [ ] **Step 3：盤點 `set_pose_provider` callers**

```bash
grep -rn "set_pose_provider" pawai_brain/ interaction_executive/ tools/ 2>/dev/null
```

期望：列出所有 caller（test、conversation_graph_node、world_state_builder 自身）。

---

## Task 3.2：Gesture gate — frozenset 加 thumbs_up / peace + test

**Files：**
- Create：`interaction_executive/test/test_gesture_conversation_gate.py`
- Modify：`interaction_executive/interaction_executive/brain_node.py:574`

- [ ] **Step 1：寫 test 先**

Create `interaction_executive/test/test_gesture_conversation_gate.py`：

```python
"""Spec A §5 — thumbs_up / peace 在 tts_playing 或 chat_active 時被 gate。"""

from unittest.mock import MagicMock
import time
import pytest

from interaction_executive.brain_node import BrainNode


@pytest.fixture
def node():
    n = MagicMock(spec=BrainNode)
    n._GESTURE_CONFIRM = BrainNode._GESTURE_CONFIRM
    n._CONVERSATION_GATED_GESTURES = BrainNode._CONVERSATION_GATED_GESTURES
    n._CONVERSATION_GATE_S = BrainNode._CONVERSATION_GATE_S
    n._tts_playing = False
    n._last_chat_input_ts = 0.0
    n._pending_confirm = MagicMock()
    n._publish_trace = MagicMock()
    n._cooldown_ok = MagicMock(return_value=True)
    return n


def _now():
    return time.time()


def _invoke_gesture(node, gesture):
    BrainNode._handle_gesture_event(node, MagicMock(data=f'{{"gesture":"{gesture}"}}'))


def test_thumbs_up_idle_enters_confirm(node):
    node._tts_playing = False
    node._last_chat_input_ts = 0.0
    _invoke_gesture(node, "thumbs_up")
    node._pending_confirm.request_confirm.assert_called()


def test_thumbs_up_tts_playing_gated(node):
    node._tts_playing = True
    _invoke_gesture(node, "thumbs_up")
    node._pending_confirm.request_confirm.assert_not_called()


def test_thumbs_up_chat_active_gated(node):
    node._tts_playing = False
    node._last_chat_input_ts = _now() - 5.0  # chat active 窗內
    _invoke_gesture(node, "thumbs_up")
    node._pending_confirm.request_confirm.assert_not_called()


def test_peace_tts_and_chat_gated(node):
    node._tts_playing = True
    node._last_chat_input_ts = _now() - 5.0
    _invoke_gesture(node, "peace")
    node._pending_confirm.request_confirm.assert_not_called()


def test_palm_not_gated_under_tts(node):
    """palm 是 safety，永遠不被 gate。"""
    node._tts_playing = True
    _invoke_gesture(node, "palm")
    # palm 走 safety path（非 _GESTURE_CONFIRM），不該被 gate 攔截
    # 此 case 主要驗 palm 沒進 confirm 流程
    node._pending_confirm.request_confirm.assert_not_called()


def test_peace_idle_enters_confirm(node):
    node._tts_playing = False
    node._last_chat_input_ts = 0.0
    _invoke_gesture(node, "peace")
    node._pending_confirm.request_confirm.assert_called()


def test_gated_set_membership_regression():
    """Regression guard：未來不可不小心移除 thumbs_up / peace。"""
    assert "thumbs_up" in BrainNode._CONVERSATION_GATED_GESTURES
    assert "peace" in BrainNode._CONVERSATION_GATED_GESTURES
    assert "palm" not in BrainNode._CONVERSATION_GATED_GESTURES
```

- [ ] **Step 2：跑 test 看 fail（thumbs_up / peace 尚未在 gate）**

```bash
cd interaction_executive && python -m pytest test/test_gesture_conversation_gate.py -v 2>&1 | tail -15
cd ..
```

Expected：multiple fails — `thumbs_up_tts_playing_gated` / `peace_tts_and_chat_gated` 等 fail。

- [ ] **Step 3：改 frozenset (`brain_node.py:574`)**

原文：

```python
    _CONVERSATION_GATED_GESTURES = frozenset({"wave", "fist", "index"})
```

改為：

```python
    _CONVERSATION_GATED_GESTURES = frozenset({
        "wave",
        "fist",
        "index",
        "thumbs_up",
        "peace",
    })
```

- [ ] **Step 4：跑 test pass**

```bash
cd interaction_executive && python -m pytest test/test_gesture_conversation_gate.py -v 2>&1 | tail -15
cd ..
```

Expected：7 tests pass。

- [ ] **Step 5：commit**

```bash
git add interaction_executive/interaction_executive/brain_node.py interaction_executive/test/test_gesture_conversation_gate.py
git commit -m "spec-a/pr3: gesture gate 加 thumbs_up / peace（止 wiggle 誤觸）

_CONVERSATION_GATED_GESTURES 加兩成員；TTS 播放或 chat active 30s 窗內
不再進 pending_confirm。palm safety path 不變。"
```

---

## Task 3.3：Pose Brain-side simulation — `world_state_builder.set_pose_provider` 兼容 dict

**Files：**
- Modify：`pawai_brain/pawai_brain/nodes/world_state_builder.py`
- Modify (test)：`pawai_brain/test/`（既有 world_state_builder test，若有）

- [ ] **Step 1：讀現況**

```bash
grep -nE "set_pose_provider|current_pose|_pose_provider" pawai_brain/pawai_brain/nodes/world_state_builder.py
```

確認當前 signature：通常為 `set_pose_provider(provider: Callable[[], tuple[str, float] | None])`。

- [ ] **Step 2：寫 test（兼容層）**

新增或擴充 `pawai_brain/test/test_pose_brain_simulation.py`：

```python
"""Spec A §6 — pose Brain-side state simulation 7 case。"""

import time
import pytest

from pawai_brain.nodes import world_state_builder as wsb


def _fake_provider_dict(data):
    return lambda: data


def _fake_provider_tuple(t):
    return lambda: t


def test_provider_tuple_legacy_works():
    """舊 tuple 仍可用。"""
    wsb.set_pose_provider(_fake_provider_tuple(("sitting", time.time())))
    out = wsb.format_current_pose(now=time.time(), stale_threshold_s=30.0)
    assert out is not None
    assert "坐" in out


def test_provider_dict_fresh_high_conf():
    now = 100.0
    wsb.set_pose_provider(_fake_provider_dict({
        "name": "sitting", "confidence": 0.85,
        "first_seen_ts": now - 5.0, "last_seen_ts": now - 1.0,
    }))
    out = wsb.format_current_pose(now=now, stale_threshold_s=30.0)
    assert "坐著" in out
    assert "5" in out  # duration_s ≈ 5
    assert "信心" not in out  # high conf 不提信心


def test_provider_dict_fresh_low_conf():
    now = 100.0
    wsb.set_pose_provider(_fake_provider_dict({
        "name": "sitting", "confidence": 0.4,
        "first_seen_ts": now - 5.0, "last_seen_ts": now - 1.0,
    }))
    out = wsb.format_current_pose(now=now, stale_threshold_s=30.0)
    assert "可能" in out
    assert "不太確定" in out


def test_provider_dict_stale():
    now = 100.0
    wsb.set_pose_provider(_fake_provider_dict({
        "name": "sitting", "confidence": 0.9,
        "first_seen_ts": now - 40.0, "last_seen_ts": now - 40.0,
    }))
    out = wsb.format_current_pose(now=now, stale_threshold_s=30.0)
    assert "最後看到" in out
    assert "40" in out
    assert "不確定" in out


def test_provider_returns_none():
    wsb.set_pose_provider(lambda: None)
    out = wsb.format_current_pose(now=time.time(), stale_threshold_s=30.0)
    assert out is None


def test_duration_uses_now_minus_first_seen_not_last_minus_first():
    """主要痛點 case：transition-only event，不重發；duration 必須是 now-first_seen。"""
    now = 100.0
    wsb.set_pose_provider(_fake_provider_dict({
        "name": "sitting", "confidence": 0.85,
        "first_seen_ts": 80.0, "last_seen_ts": 80.0,  # 不重發
    }))
    out = wsb.format_current_pose(now=now, stale_threshold_s=30.0)
    assert out is not None
    # duration = 100 - 80 = 20 秒；非 stale（age=20 < 30）
    assert "20" in out
    assert "持續" in out


def test_fallen_uses_safe_chinese():
    now = 100.0
    wsb.set_pose_provider(_fake_provider_dict({
        "name": "fallen", "confidence": 0.9,
        "first_seen_ts": now - 1.0, "last_seen_ts": now - 1.0,
    }))
    out = wsb.format_current_pose(now=now, stale_threshold_s=30.0)
    assert "可能跌倒" in out
    # 不該直喊「你跌倒了」
    assert "你跌倒了" not in out
```

- [ ] **Step 3：跑 test 看 fail**

```bash
cd pawai_brain && python -m pytest test/test_pose_brain_simulation.py -v 2>&1 | tail -20
cd ..
```

Expected：multiple fails。

- [ ] **Step 4：實作（修改 `world_state_builder.py`）**

讀現況確認舊 API，然後新增 `format_current_pose` 函式並修改 `set_pose_provider` 支援 dict。

```python
# world_state_builder.py 內

_POSE_ZH = {
    "standing": "站著",
    "sitting": "坐著",
    "crouching": "蹲著",
    "bending": "彎腰",
    "fallen": "可能跌倒",
    "akimbo": "雙手叉腰",
    "knee_kneel": "單膝跪地",
}

_pose_provider = None


def set_pose_provider(provider):
    """Spec A §6 — 支援兩種 shape：
    - 舊：Callable[[], tuple[str, float] | None]
    - 新：Callable[[], dict | None]，含 name/confidence/first_seen_ts/last_seen_ts
    """
    global _pose_provider
    _pose_provider = provider


def _normalize_pose_data(now: float):
    """正規化 provider 輸出為 dict（or None）。"""
    if _pose_provider is None:
        return None
    raw = _pose_provider()
    if raw is None:
        return None
    if isinstance(raw, dict):
        return {
            "name": raw["name"],
            "confidence": raw.get("confidence"),
            "first_seen_ts": raw["first_seen_ts"],
            "last_seen_ts": raw["last_seen_ts"],
        }
    # tuple legacy
    name, ts = raw
    return {
        "name": name, "confidence": None,
        "first_seen_ts": ts, "last_seen_ts": ts,
    }


def format_current_pose(*, now: float, stale_threshold_s: float = 30.0):
    """Spec A §6.2 三態 prompt 注入文字；無 cache 回 None。"""
    data = _normalize_pose_data(now)
    if data is None:
        return None
    name = data["name"]
    zh = _POSE_ZH.get(name, name)
    age_s = now - data["last_seen_ts"]
    duration_s = now - data["first_seen_ts"]
    stale = age_s >= stale_threshold_s
    conf = data.get("confidence")
    if stale:
        return (f"[最近姿勢] 我最後看到你像是{zh}，但那已經是 "
                f"{age_s:.0f} 秒前，現在不確定")
    if conf is not None and conf < 0.5:
        return f"[最近姿勢] 你可能是{zh}，但我不太確定"
    return f"[最近姿勢] 你現在看起來是{zh}，已持續約 {duration_s:.0f} 秒"
```

- [ ] **Step 5：跑 test pass + commit**

```bash
cd pawai_brain && python -m pytest test/test_pose_brain_simulation.py -v 2>&1 | tail -15
cd ..

git add pawai_brain/pawai_brain/nodes/world_state_builder.py pawai_brain/test/test_pose_brain_simulation.py
git commit -m "spec-a/pr3: pose Brain-side simulation — world_state_builder 三態

set_pose_provider 兼容舊 tuple + 新 dict；format_current_pose 三態：
fresh+high_conf / fresh+low_conf / stale；fallen→可能跌倒；
duration_s = now - first_seen_ts（修 transition-only 流痛點）；
STALE_THRESHOLD_S 預設 30s（可由 conversation_graph_node ROS param 覆寫）。"
```

---

## Task 3.4：`conversation_graph_node._on_pose` 改 dict cache + ROS param

**Files：**
- Modify：`pawai_brain/pawai_brain/conversation_graph_node.py`

- [ ] **Step 1：讀現況**

```bash
grep -nE "_on_pose|_recent_pose|set_pose_provider|pose.*stale" pawai_brain/pawai_brain/conversation_graph_node.py | head -20
```

- [ ] **Step 2：實作 dict cache**

在 `conversation_graph_node.py` 的 BrainNode（或對應類別）`__init__` 內：

```python
# Spec A §6 — pose Brain-side state cache
self._pose_cache: Optional[dict] = None
self._pose_stale_threshold_s = self.declare_parameter(
    "pose_stale_threshold_s", 30.0).value

# 提供 provider 給 world_state_builder
from pawai_brain.nodes import world_state_builder
world_state_builder.set_pose_provider(self._pose_provider)
```

`_on_pose` callback：

```python
def _on_pose(self, msg):
    """Update pose cache; 同 pose 不重置 first_seen_ts。

    **Event schema**：canonical key 為 `pose`（vision_perception 既有契約，
    驗於 conversation_graph_node._on_pose_detected:955）。Parser **必須**讀
    `pose`；額外容忍 `name` 作為防禦（避免任何遺留 publisher 仍用舊 key）。

    **Cache dict shape**：內部 field 取名 `name`（無 contract 影響；
    world_state_builder._normalize_pose_data 一致讀 cache["name"]）。
    """
    import time
    import json
    try:
        payload = json.loads(msg.data)
    except (json.JSONDecodeError, AttributeError):
        return
    if not isinstance(payload, dict):
        return
    # canonical key 是 "pose"；"name" 容忍作 fallback
    pose_value = payload.get("pose") or payload.get("name")
    if not isinstance(pose_value, str) or not pose_value.strip():
        return
    pose_value = pose_value.strip()
    now = time.time()
    confidence = payload.get("confidence")
    if self._pose_cache is None or self._pose_cache.get("name") != pose_value:
        # 新 pose 或 cache 空：reset first_seen
        self._pose_cache = {
            "name": pose_value,
            "confidence": confidence,
            "first_seen_ts": now,
            "last_seen_ts": now,
        }
    else:
        # 同 pose 重發：只更新 last_seen + confidence
        self._pose_cache["last_seen_ts"] = now
        if confidence is not None:
            self._pose_cache["confidence"] = confidence


def _pose_provider(self) -> Optional[dict]:
    """Provider hook for world_state_builder."""
    return self._pose_cache
```

- [ ] **Step 3：unit test for `_on_pose` schema 兼容與 transition rule**

新增（或擴充既有）`pawai_brain/test/test_conversation_graph_pose.py`：

```python
"""Spec A §6 — conversation_graph_node._on_pose parser 與 cache transition。"""

import json
import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# 假設 BrainNode 可獨立構造（依現有 test 風格；若需要更多 mock，照
# pawai_brain/test/test_conversation_graph_node.py 既有 helper 組裝）
from pawai_brain.conversation_graph_node import BrainNode


@pytest.fixture
def node():
    n = MagicMock(spec=BrainNode)
    n._pose_cache = None
    return n


def _msg(payload: dict):
    return SimpleNamespace(data=json.dumps(payload))


def test_canonical_pose_key_accepted(node):
    BrainNode._on_pose(node, _msg({"pose": "sitting", "confidence": 0.8}))
    assert node._pose_cache is not None
    assert node._pose_cache["name"] == "sitting"
    assert node._pose_cache["confidence"] == 0.8


def test_legacy_name_key_tolerated(node):
    """容忍舊 publisher 用 `name`；canonical 仍是 `pose`。"""
    BrainNode._on_pose(node, _msg({"name": "standing"}))
    assert node._pose_cache is not None
    assert node._pose_cache["name"] == "standing"


def test_pose_key_wins_when_both_present(node):
    BrainNode._on_pose(node, _msg({"pose": "sitting", "name": "standing"}))
    assert node._pose_cache["name"] == "sitting"


def test_same_pose_keeps_first_seen(node, monkeypatch):
    t0 = 1000.0
    monkeypatch.setattr(time, "time", lambda: t0)
    BrainNode._on_pose(node, _msg({"pose": "sitting"}))
    first_seen = node._pose_cache["first_seen_ts"]

    monkeypatch.setattr(time, "time", lambda: t0 + 8.0)
    BrainNode._on_pose(node, _msg({"pose": "sitting"}))
    assert node._pose_cache["first_seen_ts"] == first_seen  # not reset
    assert node._pose_cache["last_seen_ts"] == t0 + 8.0


def test_different_pose_resets_first_seen(node, monkeypatch):
    t0 = 1000.0
    monkeypatch.setattr(time, "time", lambda: t0)
    BrainNode._on_pose(node, _msg({"pose": "sitting"}))

    monkeypatch.setattr(time, "time", lambda: t0 + 8.0)
    BrainNode._on_pose(node, _msg({"pose": "standing"}))
    assert node._pose_cache["name"] == "standing"
    assert node._pose_cache["first_seen_ts"] == t0 + 8.0
    assert node._pose_cache["last_seen_ts"] == t0 + 8.0


def test_invalid_json_silently_dropped(node):
    BrainNode._on_pose(node, SimpleNamespace(data="not json"))
    assert node._pose_cache is None


def test_missing_pose_field_silently_dropped(node):
    BrainNode._on_pose(node, _msg({"confidence": 0.9}))
    assert node._pose_cache is None
```

跑 test：

```bash
cd pawai_brain && python -m pytest test/test_conversation_graph_pose.py -v 2>&1 | tail -15
cd ..
```

Expected：7 cases pass。

- [ ] **Step 4：commit**

```bash
git add pawai_brain/pawai_brain/conversation_graph_node.py
git commit -m "spec-a/pr3: conversation_graph_node pose dict cache + ROS param

_on_pose: 同 name 不重置 first_seen_ts；不同 name 全 reset；
pose_stale_threshold_s ROS param 預設 30s；_pose_provider hook 餵
world_state_builder.format_current_pose。"
```

---

## Task 3.5：PR 3 整合測試 + push + 開 PR

- [ ] **Step 1：跑所有相關 test**

```bash
cd pawai_brain && python -m pytest test/ -v 2>&1 | tail -20
cd ../interaction_executive && python -m pytest test/ -v 2>&1 | tail -10
cd ../tools/pawai_cli && python -m pytest tests/ -v 2>&1 | tail -10
cd ../..
```

Expected：全綠。

- [ ] **Step 2：用 PR 2A/2B 提供的 preflight 自驗（dev local）**

```bash
python -m tools.pawai_cli.pawai_cli.main demo preflight --target local 2>&1 | tail -20
```

Expected：`pose_grounding_code_ready` 從 SKIP 改為 PASS（因 PR 3 已實作 dict shape，但 target=local 仍標 SKIP 因為它是 jetson_ssh 類）；本機只跑 env_key + persona scoped scan。

- [ ] **Step 3：push + 開 PR**

```bash
git push -u origin spec-a/pr3-behavior-gate
gh pr create --base main --head spec-a/pr3-behavior-gate \
  --title "spec-a/pr3: behavior gate — gesture conv gate + pose Brain-side state" \
  --body "$(cat <<'EOF'
## Summary

Spec A PR 群 3 — behavior gate（最後一群）。對應 spec §5 / §6。

- `_CONVERSATION_GATED_GESTURES` 加 `thumbs_up` / `peace`（止 wiggle 誤觸）
- `world_state_builder`：`set_pose_provider` 兼容 tuple+dict；`format_current_pose` 三態（fresh+high / fresh+low / stale）；`duration_s = now - first_seen_ts`（修 transition-only 痛點）
- `conversation_graph_node`：`_on_pose` 改 dict cache，同 name 不重置 first_seen；`pose_stale_threshold_s` ROS param 預設 30s
- `_POSE_ZH` 中文表，`fallen → 可能跌倒`（不喊警報）

## Test plan
- [x] gesture gate 7 case（含 palm 不被 gate + frozenset membership regression）
- [x] pose simulation 7 case（含「t=20 不重發」痛點 case 6）
- [x] 既有 pawai_brain / interaction_executive test 全綠

Spec：docs/pawai-brain/specs/2026-05-14-spec-a-demo-mainline-stop-bleed.md
EOF
)"
```

- [ ] **Step 4：merge 後**

```bash
git checkout main && git pull --ff-only
```

---

# Spec A 收尾驗收（Jetson 回來後）

## Task FINAL.1：dev 機本機驗收

- [ ] **Step 1**

```bash
python -m tools.pawai_cli.pawai_cli.main demo preflight --target local
```

Expected：
- `env_key` PASS（或 FAIL with hint，視 `.env` 狀態）
- `persona_loaded_no_banned` PASS
- 其餘 8 條 SKIP
- exit 0（無 FAIL）

## Task FINAL.2：Jetson 上整套驗收（硬體回來日 0）

- [ ] **Step 1：bring-up**

```bash
ssh jetson-nano
cd ~/elder_and_dog
git pull
uv pip install -r requirements-jetson.txt
colcon build --packages-select pawai_brain interaction_executive
source install/setup.zsh
exit
```

- [ ] **Step 2：本機跑 `pawai demo start`**

```bash
pawai demo start
```

Expected：
- 既有 orphan preflight 過
- Spec A pre-start preflight 5/5 PASS
- start.sh 啟動成功
- wait_for_ready 通過
- Spec A post-start preflight 5/5 PASS
- transition_if_owned("running") 成功
- demo ready

任一 FAIL 看 hint，照 Spec A §7.5 規則修。

- [ ] **Step 3：semantic dry-run**

```bash
pawai demo preflight --semantic --reason "demo 前驗收"
```

Expected：
- 6 scripts mechanical 全 PASS（或 WARN 經人工接受）
- 自然度評分 ≥ 4/5
- 總體判定 y
- 報告寫入 `runtime/preflight/semantic-<ts>.md`

- [ ] **Step 4：`pawai demo stop`**

```bash
pawai demo stop
```

確認 cleanup + `release_if_owned`。

---

# Self-Review Checklist

## Spec coverage（每 §對 task）

- §1 Scope：FINAL.1 / FINAL.2（acceptance gate 對應）
- §2 P0-zero Brain bring-up：1.2 / 1.3 / 1.4 / 1.5 / FINAL.2
- §3 Persona 收斂：1.7 / 1.8 / 1.9 / 1.10 / 1.11
- §4 TTS 單出口：2A.11（Executive guard）/ 2A.12（停用 event_action_bridge）/ 2A.8（preflight #9）
- §5 Gesture gate：3.2
- §6 Pose Brain-side state：3.3 / 3.4
- §7 Preflight 工具：2A.2-2A.10
- §7.3.1 Persona scoped scan：2A.3
- §8 Semantic dry-run：2B.3 / 2B.4
- §9 PR 群結構：四個 PR 群完整呈現
- §10 Risks / Rollback：每 task `commit` 訊息標 spec-a/pr<N>，可獨立 revert
- §11 Acceptance：FINAL.1 / FINAL.2
- Appendix A Pose follow-up schema：不實作（spec 附錄留檔）
- Appendix B Banned pattern：2A.3 + 2B.3 用同一份來源
- Appendix C 跨套件改動：File Structure 表
- Appendix D Demo 保底腳本：FINAL.2 Step 3

## Placeholder scan

無 TODO / TBD / FIXME / 「fill in details」。
每個 step 都有 exact code 或 exact command + expected output。

## Type consistency

- `CheckResult.status` 一律 `pass/fail/warn/skip`（lowercase string，frozenset 驗證）
- `CheckResult.target` 一律 `local` / `jetson_ssh`
- `Target` Literal 為 `jetson / local / both`（CLI flag），對應內部 `local` / `jetson_ssh` 標示
- `phase` 一律 `pre_start / post_start / all`
- `run_mechanical` / `run_semantic` 一律回傳 `list[CheckResult]`
- `format_current_pose` 一律回 `Optional[str]`
- `_pose_cache` dict shape 一律 `{name, confidence, first_seen_ts, last_seen_ts}`
- gesture frozenset 一律含 `wave/fist/index/thumbs_up/peace`，不含 `palm`

無命名衝突。

---

**End of Implementation Plan**
