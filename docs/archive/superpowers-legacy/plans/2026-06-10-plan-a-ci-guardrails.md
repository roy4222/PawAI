# Plan A: CI/CD Guardrails Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 demo 關鍵套件的既有測試（IE 258 / pawai_cli 144 / Studio gateway 64 / pawai_brain 補檔 / nav_cap 49 / go2_sdk ~44 / object 41）接進 GitHub Actions 與 pre-commit，重構期間不再裸奔。

**Architecture:** 沿用現有「每個 top-level `test/` 套件一個獨立 pytest invocation」模式（避免 package 撞名，`.github/workflows/ros_build.yaml:78-80` 已有先例）。Tier 1（Brain/Studio/CLI）先上、Tier 2（感知/硬體）後上。gateway 測試因 `studio_gateway.py:32` module-level `import rclpy`，跑在 Tier-2 ROS container job 裡。pre-commit 只加 path-triggered scope，預算 <10s。

**Tech Stack:** GitHub Actions、pytest、bash pre-commit hook。**零 runtime 程式碼變更**。

---

## Scope

- 改：`.github/workflows/ros_build.yaml`（fast-gate 新 invocations + container job 新 step + pip 依賴）
- 改：`scripts/hooks/git-pre-commit.sh`（smart-scope 擴張）
- 改：`.claude/skills/ros2-test-suite/scripts/run_all_tests.py`（PACKAGES dict 4→9）

## Forbidden scope（本 plan 絕不碰）

- 任何 `*.py` runtime 程式碼（連 import 排版都不准動）
- 任何測試檔內容（測試紅了 = 回報，不准在本 plan 裡修測試）
- `--import-mode=importlib` 切換（單變量原則，另開 PR 才准）
- `nav_capability/test/integration/test_mux_priority.py` **永不納入任何自動化**
  （FakePublisher 會經 mux 灌真實 0.30 m/s，4/26 撞機紀錄在案）
- `go2_robot_sdk/test/test_import.py`（WSL/runner 上 SystemExit -1，已知紅，POST_DEMO 修）

## PR 切割規則（Roy/codex 約定）

每個 Task = 一個獨立 PR，PR description 必附該次 Actions run link，證明新 invocation
**真的執行且測試數 > 0**。Task A6（pre-commit）與 CI PR 分開（失敗面不同、各自可 revert）。

## 驗證紅綠的通用步驟（每個 CI Task 都做一次）

在 PR branch 上：故意把該 suite 一個 assert 改壞 → push → 確認 Actions 變紅 →
revert 該 commit → 確認變綠。紅綠證據截圖/link 附在 PR。

---

### Task A1: Fast-gate invocation 3 — interaction_executive（Tier 1）

**Files:**
- Modify: `.github/workflows/ros_build.yaml`（在 invocation 2 之後、`- name: Upload coverage report` 之前）

- [x] **Step 1: 本機先驗證 9 個 rclpy-free 檔案清單**

```bash
cd /home/roy422/newLife/elder_and_dog
grep -L "import rclpy" interaction_executive/test/test_*.py
```
Expected：列出 9 檔 = `test_attention_machine.py test_idle_mvp.py test_pending_confirm.py test_safety_layer.py test_skill_contract.py test_skill_contract_demo_fields.py test_skill_queue.py test_state_machine.py test_world_state.py`（不含 attention_integration / brain_rules / mini_e2e / nav_executor 四個 rclpy 檔）。

- [x] **Step 2: 本機跑一次確認綠**

```bash
PYTHONPATH=interaction_executive python3 -m pytest \
  interaction_executive/test/test_attention_machine.py \
  interaction_executive/test/test_idle_mvp.py \
  interaction_executive/test/test_pending_confirm.py \
  interaction_executive/test/test_safety_layer.py \
  interaction_executive/test/test_skill_contract.py \
  interaction_executive/test/test_skill_contract_demo_fields.py \
  interaction_executive/test/test_skill_queue.py \
  interaction_executive/test/test_state_machine.py \
  interaction_executive/test/test_world_state.py -q
```
Expected: 全 PASS（~150+ tests，<3s）。

- [x] **Step 3: 在 ros_build.yaml invocation 2 區塊後面加 invocation 3**

在 `pawai_brain/test/test_world_state_builder.py \`…`-v --tb=short` 之後（仍在同一個
`Pure Python unit tests` run block 內）加：

```yaml
          # Invocation 3 (2026-06-10 Plan A, Tier 1): interaction_executive —
          # rclpy-free subset only (4 rclpy files run locally, see docs/archive/superpowers-legacy/
          # plans/2026-06-10-plan-a-ci-guardrails.md). Isolated PYTHONPATH to avoid
          # top-level 'test' package collision.
          PYTHONPATH=interaction_executive pytest \
            interaction_executive/test/test_attention_machine.py \
            interaction_executive/test/test_idle_mvp.py \
            interaction_executive/test/test_pending_confirm.py \
            interaction_executive/test/test_safety_layer.py \
            interaction_executive/test/test_skill_contract.py \
            interaction_executive/test/test_skill_contract_demo_fields.py \
            interaction_executive/test/test_skill_queue.py \
            interaction_executive/test/test_state_machine.py \
            interaction_executive/test/test_world_state.py \
            -v --tb=short
```

- [x] **Step 4: PR + 紅綠驗證 + merge**

```bash
git checkout -b ci/ie-fast-gate && git add .github/workflows/ros_build.yaml
git commit -m "ci: add interaction_executive rclpy-free tests to fast gate (Tier 1, Plan A1)"
gh pr create --fill
```
跑通用紅綠步驟，附 Actions link，Fable review 後 merge。

---

### Task A2: Fast-gate invocation 4 — tools/pawai_cli（Tier 1）

**Files:**
- Modify: `.github/workflows/ros_build.yaml`（pip 依賴行 + invocation 4）

- [x] **Step 1: 本機確認 144 測試綠且依賴只有 click + python-dotenv**

```bash
python3 -m pytest tools/pawai_cli/tests -q
```
Expected: `144 passed`（~2s）。

- [x] **Step 2: fast-gate 的 Install dependencies 行加 click 與 python-dotenv**

```yaml
      - name: Install dependencies
        run: pip install pytest pytest-cov flake8 numpy opencv-python-headless jsonschema pyyaml click python-dotenv
```

- [x] **Step 3: invocation 3 之後加 invocation 4**

```yaml
          # Invocation 4 (Plan A2, Tier 1): pawai_cli — pure mock tests, deps = click+dotenv
          pytest tools/pawai_cli/tests -v --tb=short
```
（pawai_cli 的 tests/ 目錄名不叫 `test`，無撞名問題，不需 PYTHONPATH。）

- [x] **Step 4: PR + 紅綠驗證 + merge**（同 A1 格式，branch `ci/cli-fast-gate`）

---

### Task A3: Invocation 2 補齊 pawai_brain 7 檔（Tier 1）

**Files:**
- Modify: `.github/workflows/ros_build.yaml`（pip 依賴 + invocation 2 檔案清單）

19 檔中 CI 已有 10；**可補 7**：capability_builder_node、capability_registry、
demo_guides_loader、demo_policy_loader、health_loader、llm_client_offline（需
`requests`）、graph_smoke（需 `langgraph`）。**排除 2**：test_conversation_graph_node、
test_user_message_builder——兩者 import `conversation_graph_node` → module-level
`import rclpy`（pawai_brain/pawai_brain/conversation_graph_node.py:26），runner 沒有
rclpy，留在本機 L1 層。

- [x] **Step 1: 本機模擬 runner 依賴跑 7 檔**

```bash
PYTHONPATH=pawai_brain python3 -m pytest \
  pawai_brain/test/test_capability_builder_node.py \
  pawai_brain/test/test_capability_registry.py \
  pawai_brain/test/test_demo_guides_loader.py \
  pawai_brain/test/test_demo_policy_loader.py \
  pawai_brain/test/test_health_loader.py \
  pawai_brain/test/test_llm_client_offline.py \
  pawai_brain/test/test_graph_smoke.py -q
```
Expected: 全 PASS。若 graph_smoke 在 runner 因 langgraph 子依賴失敗 → 從本 PR 移除該檔並在 PR note 記錄（不修測試）。

- [x] **Step 2: pip 行加 `requests langgraph`**（接 A2 改過的行尾）

- [x] **Step 3: invocation 2 的檔案清單加上述 7 檔**（維持既有 `PYTHONPATH=pawai_brain pytest` 結構，按字母序插入）

- [x] **Step 4: PR + 紅綠驗證 + merge**（branch `ci/pawai-brain-fill`）

---

### Task A4: Studio gateway pytest — Tier-2 ROS container step（Tier 1 保護目標）

gateway import rclpy（studio_gateway.py:32），只能跑在有 ROS 的環境。
`test_environment` job 的 rostooling humble container 有 rclpy。

**Files:**
- Modify: `.github/workflows/ros_build.yaml`（`test_environment` job，`build and test` step 之後加一個 step）

- [x] **Step 1: 加 container step**

```yaml
      - name: Studio gateway tests (needs rclpy — Plan A4, Tier 1)
        run: |
          pip3 install -r pawai-studio/gateway/requirements.txt pytest \
            opencv-python-headless numpy pydub || \
          pip3 install --break-system-packages -r pawai-studio/gateway/requirements.txt \
            pytest opencv-python-headless numpy pydub
          bash -c "source /opt/ros/humble/setup.bash && \
            cd pawai-studio/gateway && python3 -m pytest -q --tb=short"
```
（requirements.txt = fastapi/uvicorn/requests/opencc；video_bridge 另需 cv2+numpy；
test_gateway 的 wav 處理需 pydub 已在 job 前段裝過，重複裝無害。）

- [x] **Step 2: 本機等價驗證**

```bash
cd pawai-studio/gateway && python3 -m pytest -q
```
Expected: `64 passed, 1 skipped`（opencc 在本機沒裝會 skip 1；container 裝了 requirements 會 65 passed）。

- [x] **Step 3: PR + 紅綠驗證 + merge**（branch `ci/gateway-container-tests`；紅綠驗證改壞 `test_gateway.py` 一個 assert 即可）

---

### Task A5: Tier 2 — nav_capability / go2_robot_sdk / object_perception / vision 補檔

**Files:**
- Modify: `.github/workflows/ros_build.yaml`（invocation 5/6/7 + invocation 1 補 2 檔）

- [x] **Step 1: 本機驗證各 suite 的 CI-safe 子集**

```bash
# nav_capability：排除 integration/（mux 危險測試永不自動化）
PYTHONPATH=nav_capability python3 -m pytest nav_capability/test/ \
  --ignore=nav_capability/test/integration -q
# go2_robot_sdk：排除 test_import.py（已知紅）與 test_reactive_stop_node.py（rclpy）
grep -L "import rclpy" go2_robot_sdk/test/test_*.py | grep -v test_import
PYTHONPATH=go2_robot_sdk python3 -m pytest \
  go2_robot_sdk/test/test_robot_control_service.py \
  go2_robot_sdk/test/test_reactive_stop_release_gate.py \
  go2_robot_sdk/test/test_depth_geometry.py -q
# object
python3 -m pytest object_perception/test/ -q
```
Expected: 全 PASS（nav_cap ~49、go2 三檔依 grep 結果為準、object 41）。
若 go2 的 release_gate 檔 grep 顯示 import rclpy → 從清單剔除並記錄於 PR note。

- [x] **Step 2: fast-gate 加 invocation 5/6/7**

```yaml
          # Invocation 5 (Plan A5, Tier 2): nav_capability pure-lib tests.
          # NEVER add test/integration/ — test_mux_priority drives a real
          # 0.30 m/s through the mux (2026-04-26 runaway incident).
          PYTHONPATH=nav_capability pytest nav_capability/test/ \
            --ignore=nav_capability/test/integration -v --tb=short
          # Invocation 6 (Plan A5, Tier 2): go2_robot_sdk safety-critical pure tests.
          # test_import.py excluded (aioice guard SystemExit on non-colcon env);
          # test_reactive_stop_node.py excluded (rclpy — local L1 tier).
          PYTHONPATH=go2_robot_sdk pytest \
            go2_robot_sdk/test/test_robot_control_service.py \
            go2_robot_sdk/test/test_reactive_stop_release_gate.py \
            go2_robot_sdk/test/test_depth_geometry.py \
            -v --tb=short
          # Invocation 7 (Plan A5, Tier 2): object_perception
          PYTHONPATH=object_perception pytest object_perception/test/ -v --tb=short
```

- [x] **Step 3: invocation 1 的 vision 區塊補 2 個 local-only 檔**

在 `vision_perception/test/test_gesture_recognizer_backend.py \` 之後加：

```yaml
            vision_perception/test/test_lidar_obstacle_detector.py \
            vision_perception/test/test_obstacle_detector.py \
```

- [x] **Step 4: PR + 紅綠驗證 + merge**（branch `ci/tier2-perception-hw`；本 task 一個 PR 可，PR note 列出每個 invocation 的測試數）

---

### Task A6: pre-commit path-triggered 擴張（獨立 PR）

**Files:**
- Modify: `scripts/hooks/git-pre-commit.sh:66-79`（smart-scope 區塊）

- [x] **Step 1: 在 face_perception 區塊之後追加**

```bash
if echo "$STAGED" | grep -q '^interaction_executive/'; then
  # rclpy-free subset only — keep the hook runnable on machines without ROS.
  TEST_ARGS="$TEST_ARGS interaction_executive/test/test_attention_machine.py \
interaction_executive/test/test_idle_mvp.py \
interaction_executive/test/test_pending_confirm.py \
interaction_executive/test/test_safety_layer.py \
interaction_executive/test/test_skill_contract.py \
interaction_executive/test/test_skill_contract_demo_fields.py \
interaction_executive/test/test_skill_queue.py \
interaction_executive/test/test_state_machine.py \
interaction_executive/test/test_world_state.py"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}interaction_executive"
fi

if echo "$STAGED" | grep -q '^tools/pawai_cli/'; then
  TEST_ARGS="$TEST_ARGS tools/pawai_cli/tests/"
fi

if echo "$STAGED" | grep -q '^nav_capability/'; then
  TEST_ARGS="$TEST_ARGS nav_capability/test/ --ignore=nav_capability/test/integration"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}nav_capability"
fi

if echo "$STAGED" | grep -q '^object_perception/'; then
  TEST_ARGS="$TEST_ARGS object_perception/test/"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}object_perception"
fi

if echo "$STAGED" | grep -q '^pawai_brain/'; then
  TEST_ARGS="$TEST_ARGS pawai_brain/test/"
  PYTHONPATH_EXTRA="${PYTHONPATH_EXTRA:+$PYTHONPATH_EXTRA:}pawai_brain"
fi
```
（pawai_brain 本機有 rclpy/langgraph，跑全 dir；go2_robot_sdk 刻意**不**進 pre-commit
——保 <10s 預算，CI 蓋。）

- [x] **Step 2: 量時間**

```bash
touch interaction_executive/touch.tmp tools/pawai_cli/touch.tmp && git add -A
time bash scripts/hooks/git-pre-commit.sh; git reset -q && rm -f interaction_executive/touch.tmp tools/pawai_cli/touch.tmp
```
Expected: 總時間 <10s（IE 子集 ~3s + CLI ~2s）。超過 → 回報，砍 pawai_brain 全 dir 改檔案清單。

- [x] **Step 3: 故意失敗驗證 BLOCKED 行為**

改壞 `tools/pawai_cli/tests/test_cache.py` 一個 assert → stage → `git commit -m x` →
Expected: `[pre-commit] BLOCKED: tests failed.`；revert。

- [x] **Step 4: PR + merge**（branch `ci/pre-commit-scope`）

---

### Task A7: ros2-test-suite skill PACKAGES dict 同步

**Files:**
- Modify: `.claude/skills/ros2-test-suite/scripts/run_all_tests.py:15-32`

- [x] **Step 1: PACKAGES dict 從 4 目錄擴到 9**：speech_processor、face_perception、
vision_perception、go2_robot_sdk（既有）+ interaction_executive、pawai_brain、
nav_capability、object_perception、`tools/pawai_cli`（tests 路徑 `tools/pawai_cli/tests`）。
每項沿用現有 dict 條目格式（path / test_dir / 備註）；nav_capability 條目註明
`--ignore=test/integration`。同步修正檔頭過期註解（「4 packages」→「9」）。

- [x] **Step 2: 跑一次全套**

```bash
python3 .claude/skills/ros2-test-suite/scripts/run_all_tests.py
```
Expected: 9 個 suite 各自回報，總結 PASS（go2_sdk 的 test_import 3 紅為已知，
輸出需標示 known-fail 而非整體 FAIL——若 skill 腳本不支援 known-fail，該 suite
加 ignore 參數）。

- [x] **Step 3: Commit**（可併入 A6 的 PR 或獨立小 PR）

---

## Tests / 驗收

- 每個 CI Task 的 PR 附 Actions link + 紅綠驗證證據。
- 全部 merge 後：fast gate 總測試數從 ~640 → **~1,100+**，總時長仍 <2 分鐘。
- pre-commit 實測 <10s。

## Rollback

每個 Task 是獨立 PR → `git revert <merge-commit>` 即回滾單一 suite，互不影響。
workflow 檔案無 runtime 影響，revert 零風險。

---

## 執行結果（2026-06-11，全數完成）

7 PRs 全 merge，皆附紅綠驗證 Actions link（細節見各 PR description）：

| Task | PR | 結果 | 與 plan 的偏差（皆已查證並記錄於 PR） |
|------|----|----|----|
| A1 | #143 | invocation 3 = **111 tests** | 9 檔 → **6 檔**：idle_mvp/safety_layer/world_state 間接 import rclpy/std_msgs（`grep -L "import rclpy"` 抓不到 transitive import） |
| A2 | #146 | invocation 4 = **144 tests, 1.41s** | **需要 `PYTHONPATH=tools/pawai_cli`**；本機 300s+1 fail = `.env.local` 污染與真實 ssh timeout（runner 不受影響）→ follow-up #150 |
| A3 | #144 | invocation 2 = **278 tests**（17 檔） | 無 |
| A4 | #145 | container gateway step = **65 tests** | container 需先裝 **ffmpeg**（resample 測試）與 **`'pytest>=7'`**（apt pytest 6.x 撞 anyio plugin） |
| A5 | #148 | invocation 5 = **67**、6 = **63**、invocation 1 +20；object **41** | nav_cap 實為 67 非 ~49；**object 進不了 fast gate**（module-level std_msgs/rclpy）→ 改 container step（A4 模式） |
| A6 | #147 | hook 3→7 套件，worst-case **8.6s** | plan 的 TEST_ARGS 累加式會撞 top-level `test` package（多個 test/ 有 `__init__.py`）→ 改 **per-package 隔離 invocation**；pawai_cli 不進 hook（300s）；IE 用 6 檔版；順手修 PYTHONPATH 尾冒號 cwd 注入 |
| A7 | #149 | skill 4→**8** 套件，本機全套 **1019 passed** | pawai_cli 暫不收（#150 修好再加回）；順手修 0-test KeyError |

**驗收對照**：fast gate 總測試 643 → **1,038**（355+19sub/278/111/144/67/63）+ container 106（65+41）= **1,144+**；fast gate 仍 <2 分鐘；pre-commit 8.6s <10s。

**執行紀錄上的發現**：A6 merge 後 hook 立即在本機攔下 A5 的 deliberate-break commit（紅綠驗證因此改用「workflow 指向不存在路徑」的 job 級 break，同一條 bash -e 傳播路徑）— 護欄上線當天就工作了。
