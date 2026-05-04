# 2026-05-04 — Phase 2 開發順序 Spec

> **目的**:把 Phase 2 七個 PR 的執行順序、量測護欄、baseline 通過標準、scope cut 寫死,避免 5/4–5/12 期間每天反覆討論。
> **前置**:[`2026-05-04-demo-scope-freeze.md`](2026-05-04-demo-scope-freeze.md) 已 commit `16dc384`。
> **作者**:Roy + Claude(brainstorming session)
> **狀態**:Spec — 等 user review 後進 writing-plans 拆 implementation plan。

---

## Context

5/3 demo 失敗根因 = B1(`nav_action_server` 不 enforce max_speed)+ B2(AMCL 靜止不收斂)兩 bug 串連,4hr 工作量擋住整條導航驗收。Phase 2 要修這兩個 bug + 5 個附帶改動,讓 5/12 demo 主線(`nav_demo_point` ≥ 4/5 PASS + Pause-Resume + 30 min 供電連測)能穩定跑。

但 8 天時間 + 7 個 PR 有風險,所以這份 spec 把:
- **執行順序**(降低風險的排序)
- **量測護欄**(每步驗收用什麼數據)
- **PASS 標準**(baseline 的 HARD vs SOFT 條件)
- **可砍清單**(時間擠到 5/10 還沒做完哪些可以丟)

一次決定清楚。

---

## 戰略:Y 收斂 P0 主線

不做「全部 7 個 PR 清光」,做「主線生死線 + 高風險 PR 5 with fallback + 其他視時間」。

```
必做(demo-blocking):    PR 1 → PR 6-lite → PR 2 → Baseline A → PR 5(with flag)→ Baseline B
時間夠才做(semi-block):   PR 4-lite / PR 7(grep-only)
明確砍掉(future work):    PR 3
```

---

## 執行順序(時序圖)

```
5/4–5/6  ┌── PR 1 ──┐  ┌─ PR 6-lite ─┐  ┌── PR 2 ──┐  ┌── Baseline A ──┐
         │ B1 + B5  │→ │ preflight + │→ │ B2 AMCL  │→ │ 5×nav_demo_pt  │  go/no-go
         │ 距離速度 │  │ bag helper  │  │ plateau  │  │ ≥ 4/5 HARD PASS │  ← 第一個閘門
         └──────────┘  └─────────────┘  └──────────┘  └────────────────┘

5/7–5/8  ┌── PR 5 ──┐  ┌─ Baseline A 回歸 ─┐  ┌── Baseline B ──┐
         │ Go2-safe │→ │ 確認 BT 改沒回退   │→ │ 2-3× pause-    │  go/no-go
         │ BT (flag)│  │ 5×重跑            │  │ resume         │  ← 第二個閘門
         └──────────┘  └────────────────────┘  └────────────────┘

5/9      ┌── PR 4-lite ──┐  ┌── PR 7 grep ──┐
         │ 看 Studio 需要 │  │ confirm-only  │  ← 視時間做
         │ 才加 reasons  │  │ 不改 code     │
         └────────────────┘  └────────────────┘

5/10     ┌── 30 min 供電連測 ──┐  ┌── approach_person ──┐
         │ V6 驗收             │  │ V8 P1 加分           │
         └─────────────────────┘  └──────────────────────┘

5/11     Dry run + 修小 bug
5/12     Demo
```

兩個 go/no-go 閘門:
1. **Baseline A < 4/5 PASS**:**不**進 PR 5,先收窄場景或 debug。如果還是過不了,demo 主線降級成「短距離 0.3m」或「只展示 pause-resume 不展示自主導航」
2. **Baseline B < 2/3 PASS**:**不**進 PR 4/7,demo 流程改成「只展示 Baseline A 場景 + approach_person」

---

## PR 細項

### PR 1 — B1+B5 導航距離/速度正確性 🔴 必做

**目標**:送 0.5m goal,Go2 實走 0.45–0.55m(目前是 1.04m,2x overshoot)

**改動**:
- `nav_capability/nav_capability/nav_action_server_node.py`
  - **B1**:`max_speed` enforce — 動態 `set_parameters()` 把 `controller_server.FollowPath.max_vel_x` 在 goal accept 時降速、goal end 時還原
  - **B5**:`actual_distance` — `start_pose` 在 goal accept 時鎖定 `world_state.amcl_pose`,結束時用 `current - start_pose` 算

**前置驗證**(寫 code 前):
1. `ros2 param get /controller_server FollowPath.max_vel_x` 確認 param 真的存在(不是 plugin 內部不可動的 hardcoded 值)
2. `ros2 param set /controller_server FollowPath.max_vel_x 0.3` 確認 runtime 改動會生效

**驗收**:
- `ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.5}"` → `actual_distance ∈ [0.425, 0.575]`(target × [0.85, 1.15])
- 連跑 3 次,3 次都在範圍內

**估工**:0.5–1 天

---

### PR 6-lite — Preflight 檢查 + Baseline bag helper 🔴 必做

**目標**:給後續所有 PR 一個客觀量測基準。**不寫 parser**,先收 bag 資料。

#### 6-lite-A: `scripts/preflight_nav_lite.py`

一次性快照,30 行 Python,subscribe 一次 → print → exit。

**檢查項**(只 4 項):
1. `/scan_rplidar` last msg age < 1s → PASS / FAIL
2. TF `map → base_link` 可查 + age < 1s → PASS / FAIL
3. `/amcl_pose` last msg age < 5s + cov_xy → PASS / WARN(YELLOW)/ FAIL(RED)
4. `/capability/nav_ready` latched value + reasons(若有)→ 直接印出

**輸出格式**:
```
[PASS] /scan_rplidar age=0.10s
[PASS] tf map→base_link age=0.05s
[WARN] /amcl_pose cov_xy=0.388 (YELLOW, > 0.30)
[PASS] /capability/nav_ready ready=true level=YELLOW
———
preflight: 1 WARN, 0 FAIL → demo 可繼續(YELLOW 短距離 only)
```

**用法**:`python3 scripts/preflight_nav_lite.py` → demo 前、每次 baseline 前跑

#### 6-lite-B: `scripts/record_nav_baseline.sh`

包 `ros2 bag record`,固定 record 這些 topics:
```bash
TOPICS=(
  /amcl_pose
  /capability/nav_ready
  /capability/depth_clear
  /state/nav/paused
  /cmd_vel
  /cmd_vel_obstacle
  /tf
  /tf_static
  /scan_rplidar
  /nav/goto_relative/_action/feedback   # 若 topic 存在
  /nav/goto_relative/_action/status     # 若 topic 存在
)
OUT_DIR="logs/nav_baseline/$(date +%Y%m%d-%H%M%S)-run${1:-N}"
ros2 bag record -o "$OUT_DIR" "${TOPICS[@]}"
```

**用法**:`bash scripts/record_nav_baseline.sh 1`(在第二個 tmux window 跑)→ Ctrl-C 結束 → bag 落地

**parser 延後**:等先有 2-3 包真 bag,再決定欄位 schema(parser 寫進 PR 8 或 future work)

**驗收**:
- Preflight 跑出 4 行輸出,可以看到 cov / age / level
- bag record 跑 30 秒,`ros2 bag info` 看到 topic list 至少 8 個 topic 有資料

**估工**:1–1.5 hr

---

### PR 2 — B2 AMCL 收斂 🔴 必做

**目標**:Go2 站 60s 不動,covariance 從 0.45 收斂到 ≤ 0.30

**改動**:
- `go2_robot_sdk/config/nav2_params.yaml` `amcl` section
  - `update_min_d: 0.10 → 0.05`
  - 加 `recovery_alpha_slow: 0.001`
  - 加 `recovery_alpha_fast: 0.1`(如果現況沒設)

**前置驗證**:
- 先用 PR 6-lite-B 錄一包**修改前** baseline(Go2 靜止 60s),看 cov 軌跡 — 確認是 plateau 不是 drift
- 修改後再錄一包,直接比對 cov_xy 時間序列

**驗收**:
- 用 `ros2 bag info` + 簡單 grep 看 `/amcl_pose` cov 在 60s 內降 ≥ 30%
- CPU 沒明顯升高(看 `top` 或 jetson stats)

**估工**:0.5 天

---

### Baseline A — 5×無障礙 nav_demo_point 🚦 第一個 go/no-go

**目標**:驗 PR 1+2 修好沒,以及主線導航可不可 demo

**HARD PASS(必過,4 條)**:
1. `nav_action_server` 回 `SUCCEEDED`
2. 無碰撞、無人工介入
3. `actual_distance ∈ target × [0.85, 1.15]`
4. 中途 `nav_ready` 不掉到 `RED`

**SOFT METRIC(只記錄不擋,5 條)**:
- goal xy error
- time to complete
- start/end covariance
- 中途 YELLOW 持續時間
- `cmd_vel` 是否出現異常尖峰(> 0.6 m/s 或 < -0.1 m/s)

**做法**:
1. 跑 `python3 scripts/preflight_nav_lite.py`,確認 PASS / WARN(可繼續)
2. 跑 `bash scripts/record_nav_baseline.sh N`(N = 1..5)
3. Foxglove 設 initialpose、發 goal `goto_relative 0.5m`
4. 看 action result + 用 `ros2 topic echo` 看 actual_distance
5. 重複 5 次,**起點同一個地板膠帶位置**

**通過 ≥ 4/5**:進 PR 5
**通過 < 4/5**:停下來看 bag,debug B1/B2 或場景設定。**不**直接做 PR 5

**估工**:2 hr(實機)

---

### PR 5 — Go2-safe BT(with launch flag)🟠 必做但風險最高

**目標**:移除 Nav2 recovery 裡的 Spin / BackUp,避免 Go2 demo 當天卡 spin loop

**改動**(三個檔案):
1. **新建** `go2_robot_sdk/config/behavior_trees/navigate_w_replanning_go2_safe.xml`
   - 基於 Nav2 Humble default `navigate_w_replanning_and_recovery.xml`(從 nav2_bt_navigator share dir copy)
   - 移除 `<Spin>` 和 `<BackUp>` recovery node
   - 保留 `<Wait>` + `<ClearEntireCostmap>`
   - 失敗路徑:plan fail → clear local + global once → retry → still fail → safe abort(回 FAILED)

2. **改** `go2_robot_sdk/config/nav2_params.yaml`
   - `bt_navigator.ros__parameters.default_nav_to_pose_bt_xml`:不寫死,改用 launch arg

3. **改** `nav_capability/launch/nav_capability.launch.py`(或 demo tmux script)
   - 加 launch arg `use_go2_safe_bt:=true`(default true,demo 用)
   - 條件 substitute BT XML 路徑

**Feature flag 機制**(關鍵):
```python
use_safe_bt = LaunchConfiguration('use_go2_safe_bt')  # default 'true'
bt_xml_path = PythonExpression([
    "'", safe_bt_path, "' if '", use_safe_bt, "' == 'true' else '", default_bt_path, "'"
])
```

**前置驗證**:
1. `ros2 pkg prefix nav2_bt_navigator`找到 default BT XML 位置,複製過來改
2. 確認 Nav2 Humble 的 BT plugin name(`Spin` / `BackUp` / `Wait`),版本相容性
3. 在 WSL 起 dry run(不實機),`ros2 launch ... use_go2_safe_bt:=false` 確認 fallback 還能跑

**驗收**:
- 兩個 launch arg 切換都能跑(`use_go2_safe_bt:=true` / `false`)
- safe BT 模式下,故意發無解 goal(障礙堵死),`ros2 topic echo /behavior_tree_log` 不出現 `Spin` / `BackUp`,只看到 `ClearCostmap` + `ComputePathToPose` retry
- 重跑 Baseline A 5 次,通過率不低於 PR 5 之前的數據(防回退)

**估工**:2 hr + 1 hr 回歸測試

---

### Baseline B — 2-3×Pause-Resume 🚦 第二個 go/no-go

**目標**:驗 demo 主線安全性

**HARD PASS(必過,5 條)**:
1. 障礙出現時 `/capability/depth_clear` → false
2. `/state/nav/paused` → true
3. `/cmd_vel_obstacle` 0 速 publish 生效(mux pri 200)
4. 障礙移除後能 resume **或** safe abort(都算 PASS)
5. 無碰撞、無人工急停

**SOFT METRIC**:
- pause latency(障礙進場到 cmd_vel=0)
- resume latency(障礙離場到 cmd_vel ≠ 0)
- 最終是否抵達 goal
- reactive_stop 觸發次數(預期場景下觸發是正常,不算 fail)

**做法**:
1. 跑 preflight + bag record
2. 發 `goto_relative 1.0m` goal
3. Go2 走到 0.5m 處時人站到前方 0.6m
4. 觀察 5s,然後人離開
5. 確認 resume 或 safe abort,看 bag 確認所有 HARD 條件
6. 重複 2-3 次

**通過 ≥ 2/3**:demo 主線 ready
**通過 < 2/3**:debug reactive_stop 或 pause/resume 邏輯,**不**進 PR 4/7

**估工**:1.5 hr(實機)

---

### PR 4-lite — nav_ready reasons 升級(視 Studio 需要)🟡 半可砍

**判定規則**:
- 如果 Studio panel 要顯示 `nav_ready level + reasons`(P1 加分),就做
- 如果只用 simple bool(主線 demo 不展示 panel),就**跳過**

**最小改動**(若做):
- `nav_capability/nav_capability/nav_ready_check.py`
- 只加 2 項 reason(不加 lifecycle / TF):
  - `scan_age=X.XXs`(從 `/scan_rplidar` last msg)
  - `covariance_xy=X.XXX (level=YELLOW)`(從 amcl_pose,沿用現有)
- 輸出格式改成 JSON list of strings

**Out**:lifecycle check / TF check 都跳過 — 理由:demo 期間 lifecycle 用人工 `lifecycle set ... activate` workaround 已經 work,TF check 在 reactive_stop 已隱含

**估工**:1 hr(若做)

---

### PR 7 — Goal 路徑統一(grep-only)🟡 半可砍

**最小做法**:
1. `grep -rn "ros2 topic pub.*goal_pose" scripts/` — 確認還有沒有
2. 如果 0 hits → **只更新 CLAUDE.md 註解**,不改 `send_relative_goal.py`
3. 如果有 hits → 把那行 deprecate 註解掉,demo 流程確認改走 action

**不做**:`send_relative_goal.py` 完整改寫成走 `/nav/goto_relative` action(留 future work)

**估工**:30 min

---

### 砍 — PR 3(B3+B4 gate 參數化)❌ Future work

**理由**:
- B3 capability_publisher param callback:`launch.py` arg override 已經夠用,runtime tune 是錦上添花
- B4 YELLOW gate threshold 寫死:demo mode 啟動時手動加 launch arg 繞,不寫 code
- 5/12 後 5/13 才修

---

## 量測護欄(統一)

每個 PR 完成 + Baseline A/B 都用同一套:

```bash
# 1. 起 demo stack
bash scripts/start_nav_capability_demo_tmux.sh

# 2. preflight check(window N+1)
python3 scripts/preflight_nav_lite.py

# 3. bag record(window N+2,背景)
bash scripts/record_nav_baseline.sh <run_id>

# 4. 跑測試
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.5}"

# 5. Ctrl-C bag record,看 ros2 bag info logs/nav_baseline/<最新>
```

baseline 結果寫進:`docs/navigation/research/2026-05-XX-baseline-runs.md`(每天 append)

---

## 凍結 / 不能做(沿用 5/4 scope freeze)

- 不直接 `ros2 topic pub /goal_pose`(走 action server)
- demo 週(5/4–5/12)不動硬體
- 不無限加 nav_ready check
- **新加**:5/9 之後不開新 PR(只允許 bug fix 與 demo 場景調整)

---

## 工時總計

| 項目 | 工時 |
|---|---|
| PR 1(B1+B5) | 0.5–1 天 |
| PR 6-lite(preflight + bag helper) | 1.5 hr |
| PR 2(B2 AMCL) | 0.5 天 |
| Baseline A 5×實機 | 2 hr |
| PR 5(Go2-safe BT with flag) | 3 hr |
| Baseline A 回歸 5× | 1.5 hr |
| Baseline B 2-3×實機 | 1.5 hr |
| PR 4-lite(若做) | 1 hr |
| PR 7(grep + 註解) | 30 min |
| 30 min 供電連測 | 30 min(背景) |
| approach_person(P1) | 2 hr |
| 5/11 dry run + 小修 | 4 hr |
| **小計 P0 必做** | **~14 hr / 2 天** |
| **連同回歸 + 加分 + dry run** | **~22 hr / 3 天** |
| **時間 buffer** | **5 天**(8 天 - 3 天 = 5 天緩衝) |

---

## 落地檔案

```
新建:
  docs/navigation/plans/2026-05-04-phase2-dev-order-spec.md   ← 本檔
  scripts/preflight_nav_lite.py                                ← PR 6-lite-A
  scripts/record_nav_baseline.sh                               ← PR 6-lite-B
  go2_robot_sdk/config/behavior_trees/navigate_w_replanning_go2_safe.xml  ← PR 5
  docs/navigation/research/2026-05-XX-baseline-runs.md         ← baseline log

修改:
  nav_capability/nav_capability/nav_action_server_node.py      ← PR 1 (B1+B5)
  go2_robot_sdk/config/nav2_params.yaml                        ← PR 2 (B2) + PR 5 (BT path)
  nav_capability/launch/nav_capability.launch.py               ← PR 5 launch arg
  docs/navigation/CLAUDE.md                                    ← PR 7 註解(若需)
  nav_capability/nav_capability/nav_ready_check.py             ← PR 4-lite(若做)
```

---

## 進入 writing-plans 的條件

User review 本 spec 後:
1. 確認 Y 收斂、PR 5 feature flag、Baseline A/B HARD/SOFT 標準
2. 確認 PR 4-lite / PR 7 可砍邏輯
3. 確認 8 天時程合理

通過後,我會 invoke writing-plans skill,把 PR 1 拆成 implementation plan(B1 / B5 / verify),其他 PR 後續 commit 完當下再各自開 plan。
