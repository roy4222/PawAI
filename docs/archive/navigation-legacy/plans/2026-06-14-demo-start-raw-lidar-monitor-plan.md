# Demo Start Raw LiDAR Monitor Plan（B5 + A3，6/18 前最小整合）

**Goal:** 讓 `pawai demo start --with-lidar`（或 `PAWAI_DEMO_WITH_LIDAR=1`）在 brain demo healthy 之後，**額外**啟一個 raw LiDAR monitor 當「證據窗」—— 只產 `/scan_rplidar` topic 給現場觀測 / Foxglove，**不啟 nav2 / amcl / nav_action_server / 第二個 go2_driver、不發任何 motion**。預設關閉，不開時行為 byte-identical。

**Status:** B5（CLI + script）已實作並通過 unit test；本文件為 A3 plan，記錄設計界線、驗收清單、與 post-6/18 full nav 整合的邊界。

**Scope freeze（6/18 前）:** 只 sllidar + static TF + `/scan_rplidar`。禁止 Go2 motion / goto_relative / live SLAM / autonomous approach / D435+LiDAR fusion / 第二 driver / nav2 / amcl。

---

## 1. 為什麼要這個（動機）

- Demo 現場想展示「狗有 LiDAR 感知環境」的證據，但 **full nav stack（nav2 + amcl + nav_action_server + reactive_stop）風險高**：6/13 撞牆事件後 nav motion 標記 `NOT_DEMO_READY`（見 MEMORY `project_nav_incident_rootcause_0613`）。
- 折衷：只開「感知層」—— RPLIDAR 出 `/scan_rplidar`，配 `base_link→laser` static TF 讓 Foxglove 能把點雲畫在機身座標。**沒有任何節點訂閱 scan 去算 cmd_vel**，所以零 motion 風險。
- 與 brain demo 並存：brain demo 的單一 `go2_driver`（`scripts/start_full_demo_tmux.sh` 內）不受影響，不會被起第二個。

---

## 2. 架構與檔案

### 2.1 新增 / 改動檔案

| 檔案 | 動作 | 責任 |
|------|------|------|
| `scripts/start_lidar_monitor_tmux.sh` | 新增 | Jetson 端 2-window tmux（session `lidarmon`）：static TF + sllidar → `/scan_rplidar` |
| `tools/pawai_cli/pawai_cli/main.py` | 改 | `demo start --with-lidar` 旗標 + env alias + `_start_lidar_monitor` / `_stop_lidar_monitor` / `_lidar_monitor_manual_command`；`_cleanup_for_lock`（brain lane）+ no-lock stop 路徑接 teardown |
| `tools/pawai_cli/tests/test_cli.py` | 改 | 9 個新 unit test（旗標/env alias/default-off/失敗不拆 demo/stop 路由），全 mock 不連真 Jetson |

**不改：** `scripts/start_full_demo_tmux.sh` 核心（避免衝突 / 維持 byte-identical default-off）。

### 2.2 拓撲（`lidarmon` session）

```
window tf       : ros2 run tf2_ros static_transform_publisher
                    --x 0.175 --y 0 --z 0.18 --yaw 3.14159
                    --frame-id base_link --child-frame-id laser
window sllidar  : ros2 run sllidar_ros2 sllidar_node
                    -p serial_port:=/dev/rplidar -p serial_baudrate:=256000
                    -r /scan:=/scan_rplidar
```

- ROS env source 參照 `scripts/start_reactive_stop_tmux.sh`：`/opt/ros/humble` + `~/rplidar_ws` + `~/elder_and_dog install`，皆 `setup.zsh`。
- TF 數值（x=0.175, y=0, z=0.18, yaw=π）與 reactive_stop / nav_capability 一致 —— LiDAR 安在 base_link 前 17.5cm、高 18cm、反裝（yaw=π）。

### 2.3 控制流（CLI）

```
pawai demo start --with-lidar
  → 解析旗標（--with-lidar 或 PAWAI_DEMO_WITH_LIDAR=1）
  → （--with-lidar + --nav capability 互斥 → UsageError）
  → 既有 brain demo start.sh + healthcheck（hard gate 不變）
  → transition_if_owned("running") 成功
  → _start_lidar_monitor()  ← SSH 到 Jetson 跑 start_lidar_monitor_tmux.sh
       成功 → "✓ LiDAR monitor running"
       失敗 → 印手動補救、exit 0（brain demo 仍在）

pawai demo stop / 重啟 cleanup / force-takeover cleanup
  → _cleanup_for_lock(lock)
       brain lane → _stop_lidar_monitor() 先清 → _invoke_cleanup_sh()
       nav  lane → _invoke_nav_cleanup_sh()（不碰 lidar，nav lane 自帶 sllidar）
  → no-lock stop 路徑 → _stop_lidar_monitor() + _invoke_cleanup_sh()
```

`_stop_lidar_monitor` 只 `tmux kill-session -t lidarmon` + `pkill sllidar_node` + `pkill static_transform_publisher（child-frame-id laser）`，**絕不 pkill go2_driver**（那是 brain cleanup 的事，單一 driver 不變）。

---

## 3. Default-off / byte-identical 證明

- 旗標 `--with-lidar` 與 env `PAWAI_DEMO_WITH_LIDAR=1` 皆預設 false/unset。
- `demo start` 主流程在 lidar block 前完全未變動；`if with_lidar:` 為 false 時整段不執行 → 與舊版同路徑（unit test `test_demo_start_default_does_not_start_lidar` 驗 `_start_lidar_monitor` 未被呼叫）。
- `demo stop` 多了一個 `_stop_lidar_monitor()`：當沒起過 monitor 時，`tmux kill-session` / `pkill` 都是 no-match best-effort（`2>/dev/null; true`），不改變 brain cleanup 結果、不影響 exit code。
- 新 script `start_lidar_monitor_tmux.sh` 只有在 `--with-lidar` 時才被 SSH 觸發，平時躺著不動。

---

## 4. 驗收清單

### 4.1 自動（已驗，CI / 本機）

- [x] `bash -n scripts/start_lidar_monitor_tmux.sh` 語法 OK
- [x] `pawai_cli` unit test 全綠（227 passed，含 9 個新 lidar test）
  - default-off 不啟 monitor
  - `--with-lidar` / `PAWAI_DEMO_WITH_LIDAR=1` 啟 monitor（healthy 之後）
  - lidar 啟動失敗 → 不拆 demo、印手動補救、exit 0
  - `--with-lidar` + `--nav capability` → UsageError exit 2
  - `_start_lidar_monitor` SSH 命令含 script 路徑、不含 nav2/amcl
  - `_stop_lidar_monitor` 只 kill lidarmon/sllidar/static TF、不含 go2_driver
  - brain stop 先 lidar 再 brain；nav stop 不碰 lidar

### 4.2 HITL-only（Roy 上機，真 Jetson + RPLIDAR）

- [ ] `pawai demo start --with-lidar` 後 **brain stack 正常**（`pawai health brain` 綠 / `ros2 node list` 有 5 perception + brain）
- [ ] `ros2 topic hz /scan_rplidar` ≈ **9–13 Hz**
- [ ] `ros2 node list | grep -c go2_driver` = **1**（不變 2）
- [ ] `ros2 node list | grep -E 'nav2|amcl|nav_action'` = **空**（無 nav stack）
- [ ] **RAM headroom ≥ 0.8 GB**（sllidar + TF 額外開銷，8GB 統一記憶體預算內）
- [ ] `pawai demo stop` 後：`tmux ls` 無 `lidarmon`、`pgrep -f sllidar_node` 空、`pgrep -f 'static_transform_publisher.*laser'` 空
- [ ] 不開 `--with-lidar` 時整套 demo 行為與舊版一致（byte-identical sanity）

---

## 5. 已知坑 / 注意

- **serial port 競爭**：`lidarmon` 與 nav_capability lane 不可同時跑（都搶 `/dev/rplidar`）→ `--with-lidar` 已與 `--nav capability` 互斥（UsageError）。手動跑 monitor 前確認 nav lane 沒在跑。
- **TF 衝突**：本 monitor 只發 `base_link→laser` static TF，**不發** `map→odom` / `odom→base_link`（那是 AMCL / driver 的事）。不會與 brain demo 的 TF 樹打架。⚠️ 若日後 brain demo 也發 `base_link→laser`，需去重避免雙 static TF（目前 brain demo 不發）。
- **RAM**：3 感知壓測基線 RAM 1.2GB（CLAUDE.md L3），加 brain + driver 後接近預算上限；sllidar + TF 開銷小但 HITL 必須實量 headroom。
- **card / serial 漂移**：`/dev/rplidar` 為 udev symlink；若未設可用 `RPLIDAR_SERIAL_PORT` env override 腳本。
- **失敗語意**：lidar monitor 是「加值證據窗」，失敗**不應**拆掉已 healthy 的 brain demo —— 故 `_start_lidar_monitor` 失敗只警告 + 手動補救命令，exit 0。

---

## 6. 與 post-6/18 full nav 整合的界線

本計畫是 **6/18 前的最小、低風險墊腳石**，**不是** full nav。與 post-6/18 整合的分界：

| 維度 | 本計畫（6/18 前，B5/A3） | post-6/18 full nav（見 `2026-06-14-unified-demo-stack-single-go2-driver-plan.md`） |
|------|------------------------|--------------------------------------------------|
| 啟動什麼 | sllidar + static TF（`/scan_rplidar`） | + nav2 + amcl + nav_action_server + reactive_stop + twist_mux |
| go2_driver | brain demo 的單一 driver，不動 | 統一單一 driver 給 brain + nav 共用（unified stack 的核心議題） |
| motion | 零 | goto / DriveOnHeading / route（需 6/13 撞牆根因全修 + HITL gate） |
| 旗標 | `--with-lidar`（default-off） | 由 unified stack 計畫定義（lane 路由 / 單 driver 共用） |
| 風險 | 低（純感知，無 control loop） | 高（control loop + Go2 MIN_X 慣性，需 e-stop + 場測） |

**交接點：** post-6/18 unified stack 接手時，`start_lidar_monitor_tmux.sh` 的 sllidar + static TF 拓撲可被 unified stack 直接吸收/取代；屆時 `--with-lidar` 旗標應**收斂進** unified stack 的單一 driver 共用設計，避免兩套各自起 sllidar。本計畫刻意**不**碰單一 driver 共用問題（那是 unified plan 的範疇），只保證「不起第二個 driver」。

> 引用：post-6/18 整合主文件 `docs/archive/navigation-legacy/plans/2026-06-14-unified-demo-stack-single-go2-driver-plan.md`（由 Cloud 端產出 / 整合；本 worktree 不建立該檔，僅標記為前向交接目標）。
> 6/13 撞牆根因：`docs/navigation/2026-06-13-nav-motion-incident-root-cause-plan.md` + `2026-06-13-nav-incident-runbook.md`。

---

## 7. Rollback

- CLI：`git revert <ab7bd1f>`（移除 `--with-lidar` 旗標 + 三個 helper + stop teardown 接線）。
- Script：`git rm scripts/start_lidar_monitor_tmux.sh`（或留著不啟用，default-off 無副作用）。
- 兩者皆 default-off，不 revert 也不影響不帶旗標的舊行為。
