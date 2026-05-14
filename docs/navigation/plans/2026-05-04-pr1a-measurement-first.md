# PR 1a — Measurement-first: 證明 overshoot 因果 + 改善 distance log 可信度

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在寫任何 SpeedOverride helper 之前,先用實機數據回答兩個問題:
1. **Overshoot 因果**:0.5m goal 走 1.04m 是否真的因為 `max_vel_x` 過大?或是其他因素(goal tolerance / DWB deceleration profile / Go2 sport-mode min / BT result timing / pause race)?
2. **`actual_distance` 可信度**:現況 `result.actual_distance` 算法是否反映真實位移?pause/resume 路徑下是否仍正確?

**Architecture:** 純 measurement / observability — **不**改控制邏輯、**不**新增 SpeedOverride、**不**綁 Nav2 param API。只:
- 在 `_execute_relative_inner` 加詳細 log(start_pose / end_pose / displacement / max_vel_x snapshot at start)
- 用 PR 6-lite 的 bag helper 收原始資料(`/cmd_vel` / `/amcl_pose` / `/odom`)
- 在 Jetson 跑三組對照(current / 0.30 / 0.45 max_vel_x via CLI `ros2 param set`)
- 數據寫進 `docs/navigation/research/2026-05-04-overshoot-causation.md`

PR1a 結束後 → 決策:
- **若 max_vel_x 真的影響 actual_distance** → 寫 PR1b(SpeedOverride helper,clamp 值用實機 sweet spot,**不**硬編)
- **若 max_vel_x 沒影響** → 改查 goal tolerance / BT result timing / pause race / `xy_goal_tolerance` / DWB stopping distance,PR1b 變成「修真正的 root cause」

**Tech Stack:** Python(rclpy logging only)、pytest、`~/sync`、`ros2 bag record`、`ros2 param set`、`ros2 topic echo`

**Spec source:** [`docs/navigation/plans/2026-05-04-phase2-dev-order-spec.md`](2026-05-04-phase2-dev-order-spec.md) commit `f386adf`(對 PR1 收斂解讀:不直接寫 helper,先驗因果)

**Supersedes:** [`2026-05-04-pr1-b1-b5-implementation.md`](2026-05-04-pr1-b1-b5-implementation.md)(因 5 個 review blocker 退回)

---

## File Structure

修改:
- `nav_capability/nav_capability/nav_action_server_node.py` — 加 logging only(start/end pose + displacement + max_vel_x snapshot)

新建:
- `scripts/measure_overshoot.sh` — 測量輔助腳本(包 `ros2 param get/set` + bag record + send_goal × 3)
- `docs/navigation/research/2026-05-04-overshoot-causation.md` — 數據紀錄 + 結論

不動:
- `nav_capability/lib/`(不新增 helper)
- `go2_robot_sdk/config/nav2_params.yaml`(用 CLI 暫時 override,不改 yaml 預設)
- 任何 launch / setup.py / 既有 lib

---

## Task 1: 加詳細 log 到 `_execute_relative_inner`(no behaviour change)

**Why:** 現況 log 只印 `current=(...) -> goal=(...)`,沒印 start_pose 鎖定點、最終位移、`max_vel_x` 觀測值。要先讓**單次 run 自帶足夠資訊**,bag 解析才有 reference。

**Files:**
- Modify: `nav_capability/nav_capability/nav_action_server_node.py`

- [ ] **Step 1:讀現況 line 296–404 確認改動點**

```bash
sed -n '296,404p' nav_capability/nav_capability/nav_action_server_node.py
```

確認 `_execute_relative_inner` 結構與當前 log 點。

- [ ] **Step 2:在 function 開頭加 `start_pose_log`(觀察用,**不**用於 actual_distance 計算)**

找到:
```python
    async def _execute_relative_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()

        # Phase 8 — driver liveness watchdog (E5) with 3s warmup (Phase 9 review #4).
```

改成:
```python
    async def _execute_relative_inner(self, goal_handle):
        goal = goal_handle.request
        result = GotoRelative.Result()

        # PR1a measurement — log goal-accept-time pose for offline analysis.
        # Pure observation; not used for actual_distance computation (that still
        # references cx,cy captured after AMCL gating, line ~354).
        accept_xy = self._current_xy()
        accept_ns = self.get_clock().now().nanoseconds
        self.get_logger().info(
            f"[PR1a] goto_relative ACCEPT distance={goal.distance:.3f} "
            f"max_speed_req={goal.max_speed:.3f} "
            f"accept_pose={accept_xy if accept_xy else 'None'} "
            f"accept_ns={accept_ns}"
        )

        # Phase 8 — driver liveness watchdog (E5) with 3s warmup (Phase 9 review #4).
```

- [ ] **Step 3:在 success path 加 displacement + duration + actual_distance 三方比對 log**

找到 `if success:` block(約 line 388):
```python
        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
        if success:
            result.success = True
            result.message = msg
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                result.actual_distance = float(math.hypot(ax - cx, ay - cy))
            goal_handle.succeed()
```

改成:
```python
        success, msg = await self._execute_nav_goal_with_pause_aware(goal_handle, nav_goal)
        end_ns = self.get_clock().now().nanoseconds
        if success:
            result.success = True
            result.message = msg
            cur_after = self._current_map_pose()
            if cur_after is not None:
                ax, ay, _ = cur_after
                # Existing computation — reference cx,cy captured at line ~354 (after AMCL gating).
                result.actual_distance = float(math.hypot(ax - cx, ay - cy))
                # PR1a measurement — also compute from accept_xy for divergence check.
                accept_displacement = (
                    float(math.hypot(ax - accept_xy[0], ay - accept_xy[1]))
                    if accept_xy is not None else float('nan')
                )
                duration_s = (end_ns - accept_ns) / 1e9
                self.get_logger().info(
                    f"[PR1a] goto_relative DONE goal={goal.distance:.3f} "
                    f"actual_dist_from_cxcy={result.actual_distance:.3f} "
                    f"actual_dist_from_accept={accept_displacement:.3f} "
                    f"duration_s={duration_s:.2f} "
                    f"end_pose=({ax:.3f},{ay:.3f}) "
                    f"cxcy=({cx:.3f},{cy:.3f}) "
                    f"accept_xy={accept_xy}"
                )
            goal_handle.succeed()
```

- [ ] **Step 4:在 abort/cancel path 也加最終位移 log(便於 debug)**

找到 `elif msg == "cancelled":` 與 `else:`(約 line 396–403):
```python
        elif msg == "cancelled":
            result.success = False
            result.message = msg
            goal_handle.canceled()
        else:
            result.success = False
            result.message = msg
            goal_handle.abort()
```

改成:
```python
        else:
            # cancelled / nav2_failed / no_progress_timeout
            cur_after = self._current_map_pose()
            if cur_after is not None and accept_xy is not None:
                ax, ay, _ = cur_after
                accept_displacement = float(math.hypot(ax - accept_xy[0], ay - accept_xy[1]))
                duration_s = (end_ns - accept_ns) / 1e9
                self.get_logger().info(
                    f"[PR1a] goto_relative END({msg}) goal={goal.distance:.3f} "
                    f"actual_dist_from_accept={accept_displacement:.3f} "
                    f"duration_s={duration_s:.2f} "
                    f"end_pose=({ax:.3f},{ay:.3f})"
                )
            result.success = False
            result.message = msg
            if msg == "cancelled":
                goal_handle.canceled()
            else:
                goal_handle.abort()
```

- [ ] **Step 5:py_compile + grep `[PR1a]` 確認三處 log point**

```bash
python3 -m py_compile nav_capability/nav_capability/nav_action_server_node.py
grep -n "\[PR1a\]" nav_capability/nav_capability/nav_action_server_node.py
```

Expected:
- py_compile: no output
- grep: 3 lines(ACCEPT / DONE / END)

- [ ] **Step 6:Run existing nav_capability tests(確認沒改壞)**

```bash
python3 -m pytest nav_capability/test/ -v --no-cov 2>&1 | tail -10
```

Expected: 既有 8 個 test files 全 pass,沒新增 unit test(本 task 是 logging only,單元測試效益低)。

- [ ] **Step 7:Commit**

```bash
git add nav_capability/nav_capability/nav_action_server_node.py
git commit -m "$(cat <<'EOF'
feat(nav): PR1a — observation logs in goto_relative for overshoot causation

Add three [PR1a] log points without behaviour change:
- ACCEPT: goal-accept-time pose snapshot + ns timestamp
- DONE:   end pose + duration + actual_distance computed from BOTH
          existing cxcy reference AND accept_xy reference (divergence check)
- END:    abort/cancel path also gets displacement + duration log

Pure observation — no SpeedOverride, no helper, no nav2 param touched.
Preparing for measurement runs in PR1a Task 3.
EOF
)"
```

---

## Task 2: `scripts/measure_overshoot.sh` — automation 助攻

**Why:** 手動 send_goal × 3 + 切 max_vel_x + bag record + 對照組,容易漏步驟。寫一個 script,固定 record / set / send / restore 流程。

**Files:**
- Create: `scripts/measure_overshoot.sh`

- [ ] **Step 1:寫 script**

`scripts/measure_overshoot.sh`:
```bash
#!/usr/bin/env bash
# PR1a — Measure overshoot under different controller_server.FollowPath.max_vel_x.
#
# Usage (run on Jetson, after start_nav_capability_demo_tmux.sh has Nav2 active and
# Foxglove initialpose set):
#
#   bash scripts/measure_overshoot.sh <label> <max_vel_x|keep>
#
# Examples:
#   bash scripts/measure_overshoot.sh baseline keep    # use yaml default
#   bash scripts/measure_overshoot.sh slow_30 0.30
#   bash scripts/measure_overshoot.sh slow_45 0.45
#
# Output:
#   logs/overshoot/<UTC>-<label>/
#     bag/  (ros2 bag record of /amcl_pose /cmd_vel /cmd_vel_obstacle /tf /odom
#            /nav/goto_relative/_action/* /controller_server/parameter_events)
#     run_<n>.json (action result)
#     params_before.txt / params_after.txt
#
set -euo pipefail

LABEL="${1:?label required, e.g. baseline | slow_30 | slow_45}"
TARGET="${2:?max_vel_x value or 'keep' required}"
RUNS="${RUNS:-3}"
DISTANCE="${DISTANCE:-0.5}"
MAX_SPEED_FIELD="${MAX_SPEED_FIELD:-0.0}"  # action goal max_speed field; 0 = unset

OUT_DIR="logs/overshoot/$(date -u +%Y%m%dT%H%M%SZ)-${LABEL}"
mkdir -p "${OUT_DIR}/bag"

echo "[measure] OUT=${OUT_DIR} target_max_vel_x=${TARGET} runs=${RUNS} distance=${DISTANCE}"

# Snapshot pre-test params
ros2 param get /controller_server FollowPath.max_vel_x > "${OUT_DIR}/params_before.txt" || true
ros2 param get /controller_server FollowPath.xy_goal_tolerance >> "${OUT_DIR}/params_before.txt" || true

# Override if requested
ORIG="$(grep -oE '[0-9.]+' "${OUT_DIR}/params_before.txt" | head -1 || echo 0.5)"
if [[ "${TARGET}" != "keep" ]]; then
  echo "[measure] ros2 param set FollowPath.max_vel_x ${TARGET} (orig=${ORIG})"
  ros2 param set /controller_server FollowPath.max_vel_x "${TARGET}"
  sleep 1
fi

# Start bag in background
TOPICS=(
  /amcl_pose
  /cmd_vel
  /cmd_vel_obstacle
  /tf
  /tf_static
  /odom
  /scan_rplidar
  /controller_server/parameter_events
  /capability/nav_ready
  /state/nav/paused
)
ros2 bag record -o "${OUT_DIR}/bag/run" "${TOPICS[@]}" &
BAG_PID=$!
sleep 2

# Send goals
for i in $(seq 1 "${RUNS}"); do
  echo "[measure] === run ${i} ==="
  ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
    "{distance: ${DISTANCE}, max_speed: ${MAX_SPEED_FIELD}}" \
    > "${OUT_DIR}/run_${i}.json" 2>&1 || true
  sleep 5  # let robot settle + AMCL re-converge between goals
done

# Stop bag
sleep 1
kill -INT "${BAG_PID}" 2>/dev/null || true
wait "${BAG_PID}" 2>/dev/null || true

# Restore param
if [[ "${TARGET}" != "keep" ]]; then
  echo "[measure] restoring max_vel_x to ${ORIG}"
  ros2 param set /controller_server FollowPath.max_vel_x "${ORIG}"
fi
ros2 param get /controller_server FollowPath.max_vel_x > "${OUT_DIR}/params_after.txt" || true

echo "[measure] DONE: ${OUT_DIR}"
ls -la "${OUT_DIR}"
ros2 bag info "${OUT_DIR}/bag/run" 2>&1 | head -20 || true
```

- [ ] **Step 2:`chmod +x` + py_compile-equivalent shell check**

```bash
chmod +x scripts/measure_overshoot.sh
bash -n scripts/measure_overshoot.sh
```

Expected: no output(syntax OK)。

- [ ] **Step 3:Commit**

```bash
git add scripts/measure_overshoot.sh
git commit -m "$(cat <<'EOF'
feat(scripts): measure_overshoot.sh — PR1a causation test harness

Automates: snapshot params -> override max_vel_x -> bag record -> N×
goto_relative goals -> stop bag -> restore param. Outputs to
logs/overshoot/<UTC>-<label>/ for offline comparison across labels
(baseline / slow_30 / slow_45).

Records 10 topics including /controller_server/parameter_events so
runtime param changes are visible in bag for replay sanity.
EOF
)"
```

---

## Task 3: Sync to Jetson + 三組對照量測

**Files:** N/A(實機 + bag 落地到 Jetson 的 `logs/overshoot/`)

**前置條件**:
- Jetson 開機、`~/sync start` 已起或 Task 3 Step 1 跑 `~/sync once`
- `bash scripts/start_nav_capability_demo_tmux.sh` 已起、Foxglove `/initialpose` 設好、AMCL 至少 YELLOW
- 場地:demo 起點(地板膠帶位置),0.5m 前無障礙(本 PR1a 是無障礙場景)

- [ ] **Step 1:WSL → Jetson 同步**

```bash
# WSL
~/sync once
~/sync status
```

Expected: `~/sync status` 顯示最後一次 sync timestamp 是現在。

- [ ] **Step 2:Jetson 上 install editable(若 nav_capability 改 lib 才需要,本 PR 沒改 lib)**

```bash
ssh jetson-nano "cd /home/jetson/elder_and_dog && python3 -c 'import nav_capability.nav_capability.nav_action_server_node' 2>&1 | head -5"
```

Expected: 沒 ImportError(editable install 已生效)。

- [ ] **Step 3:確認 demo stack 在跑、`[PR1a]` log 出現**

```bash
ssh jetson-nano 'tmux list-sessions'
# 找 nav_capability_demo session;進該 window 看 nav_action_server_node log
ssh jetson-nano 'tmux capture-pane -t nav_capability_demo:nav_action_server -p | tail -20'
```

Expected: 看到 `nav_action_server_node ready ...` 啟動 log。發一個 dry-run goal 確認 `[PR1a]` log 出現:
```bash
ssh jetson-nano 'cd /home/jetson/elder_and_dog && ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.0, max_speed: 0.0}"'
```
(distance=0 不會動,但會看到 `[PR1a] goto_relative ACCEPT ...`)

- [ ] **Step 4:跑 baseline(yaml 預設 max_vel_x)**

```bash
ssh jetson-nano 'cd /home/jetson/elder_and_dog && bash scripts/measure_overshoot.sh baseline keep'
```

Expected: 跑 ~30s,落到 `logs/overshoot/<UTC>-baseline/`。3 個 `run_N.json` + 1 包 bag。

**期間人工觀察**:Go2 視覺上有沒有走超過? Foxglove 的 amcl_pose 終點離 goal 多遠?

- [ ] **Step 5:跑 slow_30(`max_vel_x = 0.30`)**

```bash
ssh jetson-nano 'cd /home/jetson/elder_and_dog && bash scripts/measure_overshoot.sh slow_30 0.30'
```

⚠️ **預期可能拒抬腳**(Go2 sport mode min ~0.50)。如果 Go2 完全沒動,記錄並繼續到 slow_45。

- [ ] **Step 6:跑 slow_45(`max_vel_x = 0.45`)**

```bash
ssh jetson-nano 'cd /home/jetson/elder_and_dog && bash scripts/measure_overshoot.sh slow_45 0.45'
```

- [ ] **Step 7:擷取 [PR1a] log 三組各別存起來**

```bash
ssh jetson-nano 'cd /home/jetson/elder_and_dog && \
  for label in baseline slow_30 slow_45; do
    dir=$(ls -dt logs/overshoot/*-${label} | head -1)
    tmux capture-pane -t nav_capability_demo:nav_action_server -p \
      > "${dir}/nav_action_server_log.txt" 2>/dev/null || \
      journalctl --since "5 min ago" | grep PR1a > "${dir}/nav_action_server_log.txt" || true
  done'
```

(注意:`tmux capture-pane` 只看到當前 buffer。如果 Task 3 跑得久,tmux scrollback 可能滿。**手動檢查每個 dir 的 log 都有抓到 3 次 ACCEPT + 3 次 DONE/END**。如果沒有,**重跑該組**。)

---

## Task 4: 整理數據 + 寫結論

**Files:**
- Create: `docs/navigation/research/2026-05-04-overshoot-causation.md`

- [ ] **Step 1:從 Jetson 把三個 `logs/overshoot/<UTC>-*/` 複製回 WSL 看(或直接 sshfs 看)**

```bash
# WSL
ls -la ~/jetson/elder_and_dog/logs/overshoot/
```

(因為 sshfs mount,直接讀)

- [ ] **Step 2:從 [PR1a] log 抽三組數據**

每組 3 runs,每 run 抓:
- `goal=` 應該都 0.5
- `actual_dist_from_cxcy=` 與 `actual_dist_from_accept=`(看是否一致)
- `duration_s=`
- 從 bag 看 `/cmd_vel` linear.x 峰值(用 `ros2 bag play` + `ros2 topic echo /cmd_vel | grep linear -A 1` 或更高效用 `rosbag2_py` 寫個一次性讀 script)

- [ ] **Step 3:寫 `docs/navigation/research/2026-05-04-overshoot-causation.md`**

模板:
```markdown
# 2026-05-04 — Overshoot 因果驗證(PR1a 結果)

## 設定
- 場地:demo 起點(地板膠帶),0.5m 前方無障礙
- AMCL: cov_xy ≈ ___(YELLOW/GREEN)
- Goal: distance=0.5, max_speed=0.0(未在 action 設,只透過 ros2 param set 改 controller)
- yaml 預設 `controller_server.FollowPath.max_vel_x` = ___

## 數據

| label | run | actual_from_accept (m) | duration (s) | /cmd_vel.linear.x peak (m/s) | 視覺觀察 |
|---|---|---|---|---|---|
| baseline | 1 | ___ | ___ | ___ | ___ |
| baseline | 2 | ___ | ___ | ___ | ___ |
| baseline | 3 | ___ | ___ | ___ | ___ |
| slow_30 | 1 | ___ | ___ | ___ | (Go2 抬腳?) |
| slow_30 | 2 | ___ | ___ | ___ | ___ |
| slow_30 | 3 | ___ | ___ | ___ | ___ |
| slow_45 | 1 | ___ | ___ | ___ | ___ |
| slow_45 | 2 | ___ | ___ | ___ | ___ |
| slow_45 | 3 | ___ | ___ | ___ | ___ |

## actual_dist_from_cxcy vs actual_dist_from_accept

- 兩者差距 max:___ m(若 < 0.05m,代表 spec 寫的 B5「`cx,cy` 是 send-time 不是 start」**不成立** — `cx,cy` 在 AMCL gating 後但在任何 await 前抓的,跟 accept 時間幾乎沒差)
- 若有 pause/resume 的 run,兩者可能不同 — 需特別記錄

## 結論

選 1:
- [ ] **Causation 成立**:`max_vel_x` 從 ___ 降到 ___ 後,actual_dist 從 ___ 降到 ___,/cmd_vel peak 從 ___ 降到 ___ → **進 PR1b** 寫 SpeedOverride helper(clamp 值用實機 sweet spot ___,**param 化**不硬編)
- [ ] **Causation 不成立**:`max_vel_x` 改了 actual_dist 沒明顯變化 → **PR1b 改方向**,查 `xy_goal_tolerance`(現值 ___)/ DWB stopping distance / BT goal-checker timing / `goal_checker.GoalChecker.xy_goal_tolerance`
- [ ] **B5 假命題確認**:`actual_dist_from_cxcy ≈ actual_dist_from_accept`(差 < 0.05m)→ B5 不需修 code,改成「補充 log + 改 spec 描述」

## actual_distance pause/resume 邊界(若有)

如果 baseline 任一 run 觸發 pause/resume(本 PR1a 場景無障礙,不應該觸發),記錄行為。

## 下一步

→ PR1b plan 寫成:___(根據結論選的方向)
```

- [ ] **Step 4:Commit research log + 結論 commit**

```bash
git add docs/navigation/research/2026-05-04-overshoot-causation.md
git commit -m "$(cat <<'EOF'
research(nav): PR1a overshoot causation — measurement results

Three labels x 3 runs: baseline / slow_30 / slow_45.

Findings:
- actual_dist_from_cxcy vs actual_dist_from_accept divergence: ___m max
- max_vel_x effect on actual_dist: ___
- /cmd_vel peak under each label: ___

Decision: see "下一步" in the research doc — PR1b direction is ___.
EOF
)"
```

(實際填入本次 run 的數據)

---

## Task 5: 決策路由 — 寫 PR1b plan stub

**Files:** Conditional — 根據 Task 4 結論選擇

- [ ] **Step 1:選擇路徑**

依 Task 4 結論:
- **A:Causation 成立** → 寫 `2026-05-XX-pr1b-speed-override.md`,scope = SpeedOverride helper(clamp 值 param 化)+ 重跑 baseline 確認
- **B:Causation 不成立** → 寫 `2026-05-XX-pr1b-tolerance-or-bt.md`,scope = `xy_goal_tolerance` / DWB stopping distance / BT goal-checker 驗證 + 修
- **C:B5 假命題** → 不需 PR1b 改 code,把 PR1a logging 留下、更新 `2026-05-04-phase2-dev-order-spec.md` 的 B5 描述

- [ ] **Step 2:Commit dev-order-spec 的 B5 / B1 描述更新(如果結論需要)**

例如 C 路徑下,在 `dev-order-spec.md` § 7 B5 下加一段:
```markdown
> **2026-05-04 PR1a 驗證結論**:`cx,cy` 在 line 354 抓的時候沒有 await delay,實質就是 goal-accept-time pose,B5 描述不成立。保留 PR1a 加的 `[PR1a]` log 作為後續 debug 入口。
```

- [ ] **Step 3:Commit**

```bash
git add docs/navigation/plans/2026-05-04-phase2-dev-order-spec.md  # 如有改
git commit -m "$(cat <<'EOF'
docs(nav): update spec per PR1a measurement outcome

Route: A / B / C (pick one)
Detail: ___ (per research doc)
EOF
)"
```

---

## Self-Review Checklist

**Spec coverage**:
- B1 / B5 因果驗證 → Tasks 1–4 ✓
- 不在這個 PR1a 寫 SpeedOverride helper(等 PR1b)→ ✓
- 觀測 `[PR1a]` log + bag 雙重 evidence → ✓
- AGENTS.md `~/sync` workflow → Task 3 Step 1 ✓
- Pre-flight outcome 寫進研究檔 → Task 4 ✓

**Placeholders**:無 TBD/TODO 在 step 內。研究檔模板用 `___` 是預期 user 實機填,不是 plan 缺漏。

**Type consistency**:`accept_xy` 為 `Optional[Tuple[float, float]]`,Tasks 1 都用 None-guard。

**Out of scope (PR1b 才做)**:
- SpeedOverride helper(等 causation 結論)
- Clamp 值決策(等實機 sweet spot)
- nav_action_server_node 任何 behaviour 改變(本 PR 純加 log)
- B3 / B4(PR 3,且已被砍)

**Unit test 缺**:本 PR 純 logging,unit test 效益低 — 改靠 Task 1 Step 6 跑既有 8 個 test files 確認沒 regression。

---

## Execution Handoff

**Plan complete and saved to** `docs/navigation/plans/2026-05-04-pr1a-measurement-first.md`。

**兩個 execution 選項**:

1. **Subagent-Driven** — 我 dispatch fresh subagent 跑 Task 1+2(寫 code)、然後你跑 Task 3+4(實機 + 結論)、最後 dispatch agent 跑 Task 5(寫 PR1b stub)
2. **Inline** — 我這個 session 連續做 Task 1+2,Task 3+4 等你跑完實機回報,再做 Task 5
3. **手動** — 你照 plan 自己跑,我不執行

Task 3+4 一定要實機,所以無論哪種選項都會在 Task 2 之後等你回報數據。

**選哪一個?**
