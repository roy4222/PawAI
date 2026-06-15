#!/usr/bin/env bash
# scripts/start_reactive_forward_demo.sh
# ⚠️⚠️ NOT_DEMO_SAFE（6/15 實機撞車）：demo_forward 在 standalone 直發 /cmd_vel 時會停，
#     但本腳本走「整合路徑」reactive → /cmd_vel_obstacle → twist_mux(200) → driver 時，
#     reactive danger-stop **沒攔截到**、6/15 狗以 0.6m/s 直撞障礙。整合 motion 鎖 fallback，
#     待查清 mux 路徑為何 danger-stop 不可靠（standalone 會、整合不會）才可再用。
# Act1 demo_forward — 短距直行 + 正前障礙安全停車，整合進 PawAI brain demo stack。
#
# 定位（誠實 claim）：
#   ✅ 短距離直行 + 正前方障礙安全停車（front-stop）
#   ❌ 不是完整自主避障導航 / 不是動態繞障 / 不是走到人面前
#
# 前提：先跑 `pawai demo start --with-lidar`，它提供：
#   - brain demo（face/object/gesture/safety/Studio）
#   - raw LiDAR /scan_rplidar（start_lidar_monitor_tmux.sh，已含 --ros-args fix）
#   - 單一 go2_driver + twist_mux（robot.launch.py，mux 預設 on）
#
# 本腳本只加 reactive_stop_node，**不開第二 driver / 不開 Nav2 / AMCL / 建圖 / goto**。
# 它發 /cmd_vel_obstacle（twist_mux priority 200）→ mux 輸出 remap /cmd_vel_out→/cmd_vel
# → brain demo 那個唯一 go2_driver 執行。S2-S5 走 /webrtc_req，與本路徑不衝突。
#
# enable=false 起步鎖住 → 無 motion，直到 operator 觸發：
#   bash scripts/act1_forward.sh        # enable=true → 走 → 遇障停 → force-stop + lock
#   bash scripts/act1_forward.sh hold   # 立刻 force-stop + lock
#
# demo_forward 參數＝6/15 實機驗證版（Go2 走 ~0.75m、正前障礙前 ~30cm 停）：
#   front_arc_deg=18（只看正前、忽略側牆）/ danger=1.1 / slow=1.3
#   slow_speed=0.6（=normal，跳過 slow 區避開 Go2 MIN_X 0.5 卡住）/ normal=0.6
#   front_offset_rad=π（LiDAR 反裝 yaw=π 補正）
set -euo pipefail

SESSION="act1react"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
CMD_VEL_TOPIC="${ACT1_CMD_VEL_TOPIC:-/cmd_vel_obstacle}"   # mux input (priority 200); 改 /cmd_vel 才是 standalone
FRONT_ARC="${ACT1_FRONT_ARC_DEG:-18.0}"
DANGER="${ACT1_DANGER_M:-1.1}"
SLOW="${ACT1_SLOW_M:-1.3}"

echo "=== Act1 demo_forward reactive_stop (整合 brain stack via twist_mux) ==="
echo "    publish=${CMD_VEL_TOPIC}  arc=±${FRONT_ARC}°  danger=${DANGER}m  slow=${SLOW}m  speed=0.6  enable=FALSE(locked)"

tmux kill-session -t "$SESSION" 2>/dev/null || true
trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

tmux new-session -d -s "$SESSION" -n reactive
tmux send-keys -t "$SESSION:reactive" "$ROS_SETUP && ros2 run go2_robot_sdk reactive_stop_node --ros-args -p cmd_vel_topic:=${CMD_VEL_TOPIC} -p front_offset_rad:=3.14159 -p front_arc_deg:=${FRONT_ARC} -p danger_distance_m:=${DANGER} -p slow_distance_m:=${SLOW} -p slow_speed:=0.6 -p normal_speed:=0.6 -p enable:=false" Enter
sleep 3

echo ""
echo "=== Started (LOCKED — 無 motion 直到 operator 觸發) ==="
echo "  驗證: ros2 param get /reactive_stop_node enable        # 應為 False"
echo "       ros2 node list | grep -c go2_driver               # 應為 1（brain demo 的，不應變 2）"
echo "  觸發: bash ~/elder_and_dog/scripts/act1_forward.sh      # 短距前進 + 遇障停"
echo "       bash ~/elder_and_dog/scripts/act1_forward.sh hold  # 立即停 + 鎖"
echo "  Attach: tmux attach -t $SESSION   Kill: tmux kill-session -t $SESSION"
