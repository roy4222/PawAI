# reactive_stop Safety Fix Plan — 5/12 修法落地

> **Status**: ready-to-execute
> **Date**: 2026-05-11 night（subagent 調查完成）
> **Owner**: Roy
> **依據**：[`nav-root-cause-burndown §4 B5`](./2026-05-11-nav-root-cause-burndown.md)
> **觸發**：5/11 上機 B5 motion 階段 Go2 撞 1.5m 處障礙物
> **核心結論**：不只是空間問題。**reactive_stop + twist_mux 的「沉默 → 自動降級」設計違反安全直覺**，加上 danger 閾值對 Go2 機身太近、缺漸進減速。

---

## 1. 根因（subagent 5/11 調查確認）

### 1.1 mux「沉默 → 自動降級」陷阱

twist_mux 是 ROS package（無 fork），所有 input 統一 0.5s timeout：
- reactive_stop 在 danger 發 0.0 → mux 用 obstacle priority 200 → /cmd_vel = 0 → Go2 停 ✅
- 障礙移開 → reactive_stop 進 clear → **`safety_only=true` 完全不 publish**
- 0.5s 後 mux 認為 obstacle channel 過期 → 降級到 teleop priority 100
- teleop 還在送 0.5 m/s → /cmd_vel = 0.5 → driver Move 1008 → **Go2 全速衝出**

mux 假設「沉默 = 不要管」，但 reactive_stop 的「沉默」應被解讀為「保持上一次決定」。設計層面衝突。

### 1.2 danger threshold 對 Go2 機身太近

LiDAR 安在 base_link 前 17.5cm（`scripts/start_*.sh` 都用 `--x 0.175 --y 0 --z 0.18 --yaw 3.14159`）。
Go2 機鼻 ≈ base_link 前 50-60cm（推估 v8 mount）。
`reactive_stop_node.compute_front_min_distance()` 只看 LiDAR 視距、無軸向投影。
LiDAR 看到 0.6m → 機鼻只剩 ~0.2m → 加 0.5 m/s × 0.3s 反應 + 機身慣性 → **必撞**。

### 1.3 safety_only mode 在 slow zone 完全不限速

| safety_only | danger (<0.6m) | slow (<1.0m) | clear (≥1.0m) |
|:---:|:---:|:---:|:---:|
| false (standalone) | 0.0 | 0.45 | 0.60 |
| **true (mux mode)** | **0.0** | **沉默** | **沉默** |

mux 模式下 slow zone 沉默 → mux 切到 teleop / nav full speed → 「停 ↔ 全速」二元、沒漸進減速。

---

## 2. Top 3 最小修法（demo 5/12 前）

預估總工時 **~3.5h**，涉及 2-3 檔案，無 breaking change。

### Fix 1 — `safety_only` 在 slow zone 也限速（0.5h）

**檔案**：`go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`

**改動**：`safety_only=true` 路徑下，slow zone 不要再沉默，改 publish `slow_speed=0.45 m/s`：

```python
# Before
if self._safety_only:
    if zone in ("danger", "emergency"):
        self._publish_zero(...)
    return  # silent in slow / clear

# After
if self._safety_only:
    if zone in ("danger", "emergency"):
        self._publish_zero(...)
    elif zone == "slow":
        self._publish_slow(...)  # 0.45 m/s 漸進減速
    return  # silent only in clear
```

priority 200 > teleop 100 / nav 10 → slow speed 會蓋過 teleop full speed，但比直接 clear → mux release 安全。

### Fix 2 — danger threshold 加大 + base_link projection（2h）

**檔案 A**：`go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`（新增函數）

```python
def project_to_nose_distance(lidar_distance_m: float,
                              lidar_to_base_x: float = 0.175,
                              base_to_nose_x: float = 0.50) -> float:
    """LiDAR 視距 → Go2 機鼻到障礙物距離。

    base_link 前 17.5cm 是 LiDAR、前 50cm 是機鼻 → 機鼻在 LiDAR 前 32.5cm。
    機鼻距離 = LiDAR 視距 - (base_to_nose_x - lidar_to_base_x)
    """
    nose_offset = base_to_nose_x - lidar_to_base_x  # 0.325m
    return max(0.0, lidar_distance_m - nose_offset)
```

**檔案 B**：`reactive_stop_node.py`

```python
# 在 compute_front_min_distance 後加投影
front_lidar = compute_front_min_distance(...)
front_nose = project_to_nose_distance(front_lidar)
zone = classify_zone(front_nose, danger=0.4, slow=1.0)
# 注意 danger 閾值改 0.4m（投影後）= LiDAR 視距 0.725m
```

新增 param：
- `lidar_to_base_x` (default 0.175)
- `base_to_nose_x` (default 0.50, 之後可從 URDF 讀)

### Fix 3 — clear 後 dwell 1s + mux timeout 延長（1h）

**檔案 A**：`reactive_stop_node.py` 加 dwell：

```python
# 障礙剛移開 (danger/slow → clear)：再多 publish 0 持續 1s 才放手
if prev_zone in ("danger", "slow") and zone == "clear":
    self._dwell_until = now + 1.0
if now < self._dwell_until:
    self._publish_zero(...)
    return  # 在 dwell 期間繼續 publish 0
```

**檔案 B**：`go2_robot_sdk/config/twist_mux.yaml`

```yaml
topics:
  obstacle:
    timeout: 1.5  # 原 0.5
```

組合效果：障礙移開 → reactive_stop 還會 publish 0 持續 1s → mux timeout 1.5s 才釋放 → **總共 2.5s buffer**。期間使用者可重新發 cmd_vel 確認真要繼續。

### Fix 4（補丁性，0.5h）— Hysteresis 防 boundary 抖動

`reactive_stop_node.py` 已有 `clear_debounce_frames=3`（離 danger 才用），擴成所有方向：

```python
# 任何 zone transition 都要 N frames 連續才生效
self._zone_history.append(new_zone)
if len(self._zone_history) >= self._debounce_frames:
    if all(z == new_zone for z in self._zone_history[-self._debounce_frames:]):
        self._zone = new_zone
```

5/11 log 顯示 1s 內 slow ↔ clear 跳兩次 → 這個必要。

---

## 3. 不在這份 plan（demo 後再做）

❌ **`cmd_vel_gate` 中介 node**（4h）— 新增 ROS node 在 mux 跟 driver 中間做 explicit confirm。完整 fix 但 demo 前風險大。
❌ **動態 safety margin**（基於加速度算 danger）— 估算複雜
❌ **D435 fusion 給 reactive_stop**（4/3 已知 D435 nav 主線停用）

---

## 4. 驗收條件

| 測試 | 標準 |
|---|---|
| 0.4 m/s 推 Go2 接近障礙 | LiDAR 視距 0.725m 觸發停（機鼻 ~0.4m） |
| 障礙移開 | Go2 不會立刻全速恢復；至少 1.5s 才接 teleop |
| 0.5-1.0m slow zone | Go2 用 0.45 m/s 漸進減速（不是停 ↔ 全速）|
| Boundary 1.0m / 0.6m 抖動 | Hysteresis 避免 zone 在 1s 內跳 >2 次 |
| 11 unit tests + 新增 zone transition test | 全綠 |

---

## 5. 5/12 排程建議

依 master plan：5/12 PM 13:00-15:30 是 B6/B7 + C/D smoke 時段。本 fix 應在 B6 之前做完：

| 時段 | 任務 |
|---|---|
| 5/12 早 AM | Fix 1 + Fix 4（safety_only slow + hysteresis）+ unit test 補強 |
| 5/12 上午中 | Fix 2（base_link projection + danger 0.6→0.4 投影後）+ test |
| 5/12 早 11:00 | Fix 3（dwell + mux timeout）+ test |
| 5/12 中 12:00 | sync to Jetson + colcon build + 上機 B5 重測 |
| 5/12 13:30 | B6 AMCL + B7 goto 0.3/0.5m |

**前提**：5/12 早上 reactive_stop fix 必須在 B6 之前落地，否則 B6 motion 會重蹈 5/11 覆轍。

---

## 6. 影響面

| 受影響 | 風險 | 對策 |
|---|---|---|
| `start_reactive_stop_tmux.sh` | safety_only=false 走原 standalone driver direct，本 fix 不打到 | 不動 |
| `start_nav_capability_demo_tmux.sh` | safety_only=true，本 fix 主戰場 | 5/12 早 AM 改完即可 |
| `start_nav_capability_demo_tmux_detour.sh` | 同上 | 順手測 |
| `nav2_params.yaml` footprint | 不動（footprint 是 nav2 costmap 用的，跟 reactive_stop 獨立） | 不動 |
| Demo 主線 | nav 反應稍慢 (+1.5s buffer)、slow zone 限速 0.45 | 可接受、demo 不會跑全速 |

---

## 7. 開放問題

1. **`base_to_nose_x = 0.50`** 是推估值。建議 5/12 早上量一次實機機鼻到 base_link footprint 中心的距離（用捲尺）。如果是 0.55 或 0.45 修一下 default。
2. **dwell 1.0s + mux timeout 1.5s 是經驗值**，5/12 上機重測可能要調。

---

**End of reactive_stop Safety Fix Plan**
