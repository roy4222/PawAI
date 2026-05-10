# Spec 5 Nav 場測 Checklist — 5/13–14 LM307 + 5/16 Demo

> **Status**: ready-for-fieldtest
> **Date**: 2026-05-10
> **依據 spec**：[`2026-05-10-spec5-navigation-roadmap.md`](../specs/2026-05-10-spec5-navigation-roadmap.md) §3
> **執行日**：5/13 LM307 場勘 + 5/14 預演 + 5/16 demo
> **執行者**：Roy（操作機器人）+ 1 人（觀察 Foxglove / 隨時 e-stop）
> **目的**：把「Nav P0 SLAM+Nav2 基本展示」從**現有 tmux script** 推上場地，並寫好 go/no-go 條件與失敗降級路徑。**不**寫實作 plan — 因為實作已存在，這裡是場測風險控管。

---

## 1. demo 主軸（只做這個）

> **「Go2 自己在房間裡走 1 公尺，中途放紙箱會停，移走會繼續。」**

✅ 做：
- `nav_capability` action `goto_relative 1.0m`
- `reactive_stop` 對紙箱觸發停 → resume

❌ 不做：
- 動態 detour（繞開）
- 多 waypoint 巡邏
- 招手過來 / 尋物 / 跟隨

---

## 2. 啟動指令（demo 當天照念）

```bash
# 0. 環境檢查（每次都跑）
ssh jetson-nano
cd ~/elder_and_dog
source /opt/ros/humble/setup.zsh
source install/setup.zsh
echo $ROS_DOMAIN_ID

# 1. 確認場地地圖檔存在（demo 場地 = LM307）
ls /home/jetson/maps/lm307_demo.{pbstream,yaml,pgm}
# 若不存在 → 先跑：bash scripts/build_map.sh lm307_demo
# fallback：home_living_room_v8.yaml（家裡客廳，僅當場地建圖失敗時用）

# 2. 啟動 nav_capability demo（**必須 override MAP env**，script 預設是 home_living_room_v8）
MAP=/home/jetson/maps/lm307_demo.yaml \
ROBOT_IP=192.168.123.161 \
  bash scripts/start_nav_capability_demo_tmux.sh

# 3. 等 ~50s lifecycle active
ros2 topic echo /diagnostics --once | grep -E "active|ACTIVE"

# 4. Foxglove 設 /initialpose（Go2 真實位置 + 朝向）

# 5. 發 goto_relative
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 1.0}"
```

---

## 3. 5/13 LM307 場勘 Checklist

### 3.1 前置（onsite 1h）

| # | Item | Pass? | 備註 |
|---|---|:---:|---|
| C1 | 場地測量：可直線 ≥1.5m 空間 | ☐ | demo 主動作 1m + buffer |
| C2 | 地板材質檢查：是否反光（影響 RPLIDAR）| ☐ | 鏡面地板 → 雷達雜訊 |
| C3 | 環境光照：D435 RGB 不過曝 / 不過暗 | ☐ | 落地玻璃旁慎選位置 |
| C4 | 觀眾席 → Go2 路徑無人擋 | ☐ | demo 走道清空 |
| C5 | 電源：XL4015 降壓板 + Go2 充電 | ☐ | spec 已知陷阱：XL4015 反覆斷電 |
| C6 | Wi-Fi vs Ethernet：用 Ethernet 直連 192.168.123.161 | ☐ | 避 Go2 OTA 自動更新 |

### 3.2 建圖

| # | Item | Pass? | 備註 |
|---|---|:---:|---|
| M1 | `bash scripts/build_map.sh lm307_demo` 啟動 5-window | ☐ | |
| M2 | 走完場地一圈（約 5 分鐘） | ☐ | Foxglove 看 cartographer trajectory |
| M3 | `finish_trajectory` + `write_state` + `map_saver_cli` 三 step | ☐ | spec §3.1 |
| M4 | 地圖檔落地：`/home/jetson/maps/lm307_demo.{yaml,pgm,pbstream}` | ☐ | |
| M5 | 用 Foxglove 看 map.pgm，無大空洞、無錯位 | ☐ | 有空洞 → 補走一遍 |

### 3.3 Nav demo dry-run（5/13 evening）

| # | Item | Pass? | 備註 |
|---|---|:---:|---|
| N1 | `start_nav_capability_demo_tmux.sh` 啟動 9-window 全部正常（5/10 確認 script 共 9 windows） | ☐ | `tmux list-windows -t nav_capability` 看數量 |
| N2 | `ros2 action list \| grep '^/nav/goto_relative$'` + `ros2 action info /nav/goto_relative` 確認 action server 起來 | ☐ | 不要用 `topic list`，action 不在 topic 列表 |
| N3 | Foxglove 設 `/initialpose`、AMCL particle 收斂 < 30s | ☐ | particles 散 → 重設 pose |
| N4 | `goto_relative 1.0` × 5 次：≥4 次到達（spec §9 要求 ≥80%） | ☐ | **demo go/no-go gate** |
| N5 | 中途放紙箱：reactive_stop 100% 觸發、移走紙箱 resume | ☐ | **demo go/no-go gate** |
| N6 | 30s 連續運行不撞、不卡 | ☐ | spec §9 要求 30 分鐘，demo 用 30s 即可 |

---

## 4. Go/No-Go 判定（5/14 evening 之前定）

| 條件 | demo 5/16 動作 |
|---|---|
| N4 ≥4/5 + N5 100% | ✅ Go：照 §2 跑完整 nav demo |
| N4 = 3/5 + N5 100% | ⚠️ Soft Go：減為 0.5m goto_relative，降低速度 |
| N4 ≤2/5 或 N5 fail | ❌ No-Go：走降級路徑 §5 |

---

## 5. 降級路徑（No-Go）

### 5.1 reactive_stop 單獨 demo
若 nav_capability 不穩、但 reactive_stop 仍 work：
```bash
bash scripts/start_reactive_stop_tmux.sh
# 手動 teleop 推 Go2 → 紙箱前自動停
```
demo 講法：「導航還在調，但安全停障已經 work」。

### 5.2 純展示靜態 demo
若 reactive_stop 也不穩：
- demo 拿掉 nav 段
- 把時間補給 Spec 1（自我介紹 / 對話展示）+ Spec 2 手勢
- demo 講法：「導航在開發中，今天展示感知 + 互動主軸」

### 5.3 場地問題降級
若 5/13 發現 LM307 地板反光 / Wi-Fi 干擾：
- 改 demo 場地（與場務確認備案教室）
- 若無備案：用「家裡客廳已建圖」做 demo（接受場地差異風險）

---

## 6. 已知陷阱（CLAUDE.md 已記錄、5/13 onsite 對照）

- `min_vel_x` ≥ 0.45（Go2 sport mode 門檻 0.50）
- `GO2_PUBLISH_ODOM_TF=0` 建圖；預設 1 demo
- `goal_pose` `-r 2 --times 5`（BEST_EFFORT race）
- `reactive_stop_node` `safety_only:=true` 必須在 mux 模式（priority 200）— `start_nav_capability_demo_tmux.sh` 已內建
- **不要在 full stack 跑 `test_mux_priority.py`**（4/26 22:30 撞過）
- runtime path 用 `~/elder_and_dog/runtime/`，不要寫 install/share
- `pkg_share` 預設路徑會被 colcon build 覆蓋 → 用 env override `NAV_NAMED` / `NAV_ROUTES`

---

## 7. 5/16 demo 當天前 30 分鐘 checklist

| # | Item | Pass? |
|---|---|:---:|
| D1 | Jetson + Go2 + RPLIDAR + D435 全亮 | ☐ |
| D2 | Ethernet 直連 192.168.123.161（無 Wi-Fi）| ☐ |
| D3 | XL4015 降壓板電壓穩定 20V | ☐ |
| D4 | 地圖檔最後修改日期確認（5/13 場勘版） | ☐ |
| D5 | `start_nav_capability_demo_tmux.sh` 啟動 + Foxglove 連線 | ☐ |
| D6 | AMCL 設 `/initialpose` + particles 收斂 | ☐ |
| D7 | `goto_relative 0.3` 試走一次（demo 前 dry-run） | ☐ |
| D8 | 紙箱 / e-stop 隨身備好 | ☐ |
| D9 | 降級腳本（§5.1, §5.2）已 review、知道怎麼切 | ☐ |
| D10 | 觀察員（負責 e-stop）就位 | ☐ |

---

## 8. 不在這份 checklist 的事

❌ 動態避障繞行（spec §4，demo 後）
❌ 招手過來（spec §5，demo 後）
❌ 尋物導航（spec §6，demo 後）
❌ 自動巡邏（spec §7，demo 後）
❌ 跟隨模式（spec §8，demo 後可能不做）

這些都是 **demo 後** 才會啟動，不應該為了 demo 嘗試臨時做。

---

## 9. demo 後檢討記錄欄

| 項 | 結果 | 備註 |
|---|---|---|
| nav demo 是否上 | ☐ Go / ☐ Soft Go / ☐ No-Go | |
| 觀眾反應 | | |
| 故障次數 | | |
| 後續優先（P1 動態 detour vs P2 招手過來） | | |

---

**End of Spec 5 Nav Field Test Checklist**
