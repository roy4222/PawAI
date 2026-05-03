# 2026-05-03 — Stage 1 + Recovery 主線打穿

> **今日唯一目標**：Go2 遇靜態障礙能可控停下；障礙移除後，能 reset + re-send goal 繼續到達。
> **不做**：漂亮繞行、人類動態避障、D435 進 costmap、`nav_demo_point` 封裝。

---

## 取捨決策

| 階段 | 今日狀態 | 收尾標準 |
|---|---|---|
| Stage 1 靜態箱：可控停 | **MUST** | ≥ 2/3 不撞、不摔、不大甩 |
| Stage 4 Recovery / Resume | **MUST（主菜）** | ≥ 2/3，最好 3/3 |
| Stage 2 D435 低矮物 | stretch only（capability-only） | `/capability/depth_clear` ≤ 1s 翻 false |
| Stage 3 人類動態 | **不做** | — |
| Stage 5 Demo 封裝 | 只記筆記 | Foxglove topic 清單 + 話術草稿 |

**砍的順序**：3 → 5 實作 → 2。**Stage 4 不能砍**。

---

## 時間盒

### Block A — nav_round_reset.sh 上 Jetson + 確認腳本（30 min）
- [ ] 想辦法 sync 到 Jetson（`scp` / Tailscale 重連 / USB）
- [ ] **確認** `scripts/nav_round_reset.sh` 已含 QoS flags（`--qos-durability transient_local --qos-reliability reliable`，line 95-96）— 不要回改
- [ ] **確認** `call_service` request default 已是顯式 if-empty 分支（line 80-83）— 不要簡化成 `${3:-{}}`，那會展開成 `{}}` 讓 YAML parse fail
- [ ] Jetson cold run：預期 NOT-READY，腳本不 crash
- [ ] Stack 起來後再跑：預期 READY、三個 capability 都不是 unknown

**門檻**：READY 拿不到不准進 Block C。

### Block B — 場景校準（30 min）
- [ ] 地板膠帶標 box 中心、Go2 起點與朝向
- [ ] 量左右淨空（≥ 0.8m）
- [ ] `scan_health_check.py` 確認 RPLIDAR 看到的 box 距離與測量一致（容差 ±5cm）
- [ ] 拍場景照、寫進今天 R3 紀錄

**5/2 R2 no-op 的根因很可能就在場景**，這步不省。

### Block C — Stage 1 R3（45 min）
- [ ] 同 yaml（5/2 三行改動保留）、同場景、watchdog danger > 1s
- [ ] 跑 1-2 輪
- [ ] 每輪記：起點 / 終點 / cmd_vel 序列特徵 / 是否撞摔大甩 / Nav2 結果
- [ ] R3 結論 append 到 `docs/navigation/plans/2026-05-02-dynamic-obstacle-demo.md`

**判分**：
- 類 R1（試繞 + 可控停）→ Stage 1 ✅
- 類 R2（早早放棄）→ 放寬場景（box 1.5m / goal 2.5m / 兩側 1m）再 1 輪
- 連寬場景都 fail → revert yaml 回 K1 stable，Stage 1 改宣告「reactive_stop only」

### Block D — Stage 4 三輪（2h，今日主菜）

每輪流程：
```bash
# 0. 確認起點乾淨
bash scripts/nav_round_reset.sh    # 必須 READY

# 1. 送 goal — 走 nav_capability 主線，不要直發 /navigate_to_pose
python3 scripts/send_relative_goal.py --distance 1.5
# 或 ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
#   "{distance: 1.5, yaw_offset: 0.0, max_speed: 0.5}"

# 2. 等 Go2 接近 → 放 box → reactive_stop 觸發停車
#    （`/cmd_vel_obstacle` mux pri 200 蓋 0、`/state/nav/paused` 翻 true）

# 3. 移走 box

# 4. reset
bash scripts/nav_round_reset.sh    # 必須 READY

# 5. re-send 同 goal
python3 scripts/send_relative_goal.py --distance 1.5

# 6. 觀察是否到達
```

**為什麼不用 `/navigate_to_pose`**：5/2 已知 BUG #2（`/nav/pause` 只有
`nav_action_server` 接、`bt_navigator` 沒接）。直發 `/navigate_to_pose` 會
繞過 pause/resume 鏈路，Stage 4 主線「reactive_stop 觸發 → `/state/nav/paused`
→ reset 解鎖 → re-send 恢復」**根本沒驗到**。必須走 `/nav/goto_relative`。

**每輪記錄**：
| 輪次 | 停車距離 | reset 後 nav_ready / depth_clear / nav_paused | re-send 後 inflation 殘影？ | 摔/大甩 | 到達精度 | PASS? |

**門檻**：3/3 = Stage 4 進 demo 話術。2/3 = 黃燈、寫 risk log、明天延伸。≤ 1/3 = 紅燈、檢討 reset 鏈。

### Block E — Stage 2 capability-only（1h，stretch）

**只有 Block A-D 都過了才做。**

- [ ] `ros2 param set /reactive_stop_node enable_nav_pause true`
- [ ] `ros2 param set /depth_safety_node stop_distance_m 0.35`
- [ ] 拖鞋 / 紙袋放 D435 ROI 0.3-0.5m
- [ ] `ros2 topic echo /capability/depth_clear` 看是否 ≤ 1s 翻 false
- [ ] **不接 Executive 擋 plan、不停 active goal** — 純 capability 翻轉

通過 = 第二階段「安全 gate 存在」可宣稱。

### Block F — 收工（30 min）
- [ ] update `docs/navigation/plans/2026-05-02-dynamic-obstacle-demo.md`：append R3 + Recovery 三輪
- [ ] 在本檔末追加「demo 話術草稿」段落
- [ ] 更新 `references/project-status.md`：5/3 進度
- [ ] `/update-docs`

---

## 收尾標準

**綠燈（demo 主線通）**
- ✅ nav_round_reset.sh 在 Jetson 跑出 READY
- ✅ Stage 1 ≥ 2/3 可控停
- ✅ Stage 4 ≥ 2/3 recovery + re-send 到達

**黃燈** — 1 過、4 部分過：寫 risk log，明天延伸 Block D，5/12 demo 話術降一階

**紅燈** — Stage 1 都沒過：revert yaml，Stage 1 改「reactive_stop only」demo

---

## 關鍵檔案速查

| 用途 | 路徑 |
|---|---|
| Round reset 腳本 | `scripts/nav_round_reset.sh` |
| Emergency lock | `nav_capability/scripts/emergency_stop.py` |
| 5/2 試跑紀錄（R3 append 在這） | `docs/navigation/plans/2026-05-02-dynamic-obstacle-demo.md` |
| Nav2 yaml（不要再改） | `go2_robot_sdk/config/nav2_params.yaml` |
| 場景校準工具 | `scripts/start_scan_only_tmux.sh` + `scan_health_check.py` |
| 啟動 stack | `scripts/start_nav_capability_demo_tmux.sh` |

---

## Demo 話術草稿（Block F 補完）

> _收工時填_

- **已完成**：定點導航 + 靜態障礙可控停車 + 障礙移除後 recovery + re-send 到達
- **未宣稱**：完整繞行、人類動態避障、D435 進 costmap、語意 3D mapping
- **Foxglove 顯示**：`/local_costmap` / `/capability/nav_ready` / `/capability/depth_clear` / `/state/nav/paused` / `/cmd_vel` / `/scan_rplidar`

---

## 5/3 evening 實際執行（事後補）

### Block A 結果：✅ READY 通過

實際執行不止 plan 寫的 6 步，沿路修了 4 個 Jetson 環境 bug：

1. **rsync `--delete` + trailing slash 災難**：第一次誤用 `--delete` + `nav_capability/`/`go2_robot_sdk/`/`scripts/` 三個 source 帶 trailing slash → rsync 把 contents 展平合併到 dest → `--delete` 把 `scripts/` 內 不在任何 source 內的檔案刪光（包括 `start_nav_capability_demo_tmux.sh` 等）。修法：第二次正確 rsync **不帶 trailing slash + 不 --delete**，孤兒手動 `rm -rf` 清理
2. **頂層 6 個孤兒目錄 + 2 個檔**：`launch/`/`urdf/`/`test/`/`resource/`/`config/`/`package.xml`/`setup.py` 全是 rsync 災難留下的合併產物，逐一清掉
3. **頂層孤兒 .py**：`nav_capability/*.py` + `go2_robot_sdk/*.py` 直接攤在 pkg root（package.py 應該在 nested module dir），手動 `find -maxdepth 1 -name "*.py" -delete`
4. **`~/.local/.../entry_points.txt` 缺 3 個 entry**：`reactive_stop_node` + `capability_publisher_node` + `depth_safety_node` 都不在 distribution metadata（colcon build 失敗導致），手動 echo append 到 `nav_capability-0.1.0.dist-info/entry_points.txt` + `go2_robot_sdk-0.0.0.dist-info/entry_points.txt`，這樣 launch 才能 load entry point

最終 7 nav nodes 全活、`nav_round_reset.sh` 跑出 READY ✅

### Block B 結果：✅ 場地校準完成

實測場景：
- box 距 Go2 鼻尖 1.5m（lidar 看 1.70m，因為 lidar 在 base_link 前 17.5cm + mount yaw=π）
- left 1.62m / right 1.46m
- back 0.71m
- 場景比預期寬

### Block C 結果：✅ Stage 1 R3 R1 PASS（K-STATIC-AVOID-CONTROLLED）

詳見 `2026-05-02-dynamic-obstacle-demo.md` 末尾 5/3 R3 R1 段落。

### Block D 結果：⚠️ 自動 recovery 部分通

**Demo A 1.5m goal 流程跑通**（success reached actual_distance=1.401m）但有反覆：
- 多輪嘗試「box 在路上 + Go2 自動停 + 拿走 box + 自動繼續」
- 最終跑通的版本是「分兩個 0.5m goal」：第一個 goal 走 0.4m 撞 box stop→reach（tolerance 內判 success）、第二個 goal 又走 0.4m 完成 demo
- 不是純單一 goal 走完，因為 xy_goal_tolerance 0.10 + tolerance 設計讓 reactive_stop 觸發後 nav 提早判 reached

**5/3 執行學到的 5 個未解卡點**：

| # | 卡點 | 影響 | 後續處理 |
|---|---|---|---|
| 1 | AMCL cov plateau 在 0.30-0.42 | YELLOW 限 0.5m goal、長 goal 被拒 | 等收斂 60s+ 偶爾 GREEN，物理推 Go2 + 重設 initialpose 偶爾打破 plateau |
| 2 | Forward warmup 雙刃刀 | 收斂 cov 但破壞場景（推 Go2 進 box 0.3-0.5m） | 用 0.3m 不要 0.5m |
| 3 | xy_goal_tolerance 0.10m + reactive_stop 觸發 | Go2 走 0.4m 撞 box 仍判 reached → 沒 active goal 可 resume | 用 1.5m 大 goal 留 buffer |
| 4 | Box 距離 sweet spot 太窄 | 太近（< 1.0m）DWB 規劃失敗 / 太遠（> 1.7m）reactive 不觸發 | 1.0-1.5m 之間最穩 |
| 5 | DWB 「No valid trajectory」+ BT spin recovery 也 collision | Goal 0ms 接受但 60s 沒動 → no_progress | 場景必須左右 ≥ 1.2m + 後方 ≥ 0.6m |

### Block E 結果：⚠️ Stage 2 detour 全部 FAIL

詳見 `2026-05-02-dynamic-obstacle-demo.md` 末尾「第二階段 Detour 嘗試」段落。

結論：**Stage 2 在當前 yaml 不可能繞**。要做需要 robot.launch.py 改 + nav2_params_detour.yaml + 寬場景。

### Block F 結果：✅ /update-docs 完成

更新檔案：
- `references/project-status.md`（5/3 進度段）
- `.claude/skills/project-onboard/references/project-status.md`（header + 模組狀態表）
- `docs/navigation/plans/2026-05-02-dynamic-obstacle-demo.md`（5/3 R3 R1 結果）
- `docs/navigation/plans/2026-05-03-stage1-and-recovery.md`（本檔，append 實際執行）

### 最終 demo 收工狀態

- **Demo A 可以錄**：「Go2 接收目標 → 自主導航 → 偵測障礙物自動停車 → 障礙移除後接收新指令繼續」
  - 兩個 0.5m goal 接龍版本最穩，視覺上看起來像連續一段
- **Demo B 不能錄**：DWB 在當前 yaml 不會繞，等 5/4-5/8 改 detour profile 後再試
