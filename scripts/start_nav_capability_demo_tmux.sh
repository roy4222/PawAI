#!/usr/bin/env bash
# Phase 10 demo launcher — full nav_capability stack on Jetson.
#
# Stack (8 windows):
#   tf            base_link → laser static TF
#   sllidar       RPLIDAR /scan_rplidar
#   robot         go2_robot_sdk robot.launch.py (driver + Nav2 wrapper + AMCL + mux + teleop)
#   reactive      reactive_stop_node → /cmd_vel_obstacle (mux priority 200)
#   navcap        nav_capability.launch.py (4 nodes)
#   pause-enable  enables enable_nav_pause runtime param after stack stabilizes
#   foxglove      foxglove_bridge for visualization (optional)
#   monitor       leave open for manual ros2 topic / ros2 action commands
#
# Usage:
#   bash scripts/start_nav_capability_demo_tmux.sh
#   ROBOT_IP=192.168.123.161 MAP=/home/jetson/maps/home_living_room_v7.yaml \
#     bash scripts/start_nav_capability_demo_tmux.sh
set -euo pipefail

SESSION="${SESSION:-nav-cap-demo}"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
MAP="${MAP:-/home/jetson/maps/home_living_room_v7.yaml}"
NAV_RUNTIME_DIR="${NAV_RUNTIME_DIR:-$HOME/elder_and_dog/runtime/nav_capability}"
NAV_NAMED="${NAV_NAMED:-$NAV_RUNTIME_DIR/named_poses/main.json}"
NAV_ROUTES="${NAV_ROUTES:-$NAV_RUNTIME_DIR/routes}"
ROS_SETUP='source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh 2>/dev/null && source ~/elder_and_dog/install/setup.zsh'

mkdir -p "$(dirname "$NAV_NAMED")" "$NAV_ROUTES"

echo "=== nav_capability Demo (Phase 10 KPI launcher) ==="
echo "  ROBOT_IP=$ROBOT_IP"
echo "  MAP=$MAP"
echo "  SESSION=$SESSION"
echo "  NAV_NAMED=$NAV_NAMED"
echo "  NAV_ROUTES=$NAV_ROUTES"

tmux kill-session -t "$SESSION" 2>/dev/null || true
ros2 daemon stop 2>/dev/null || true
sleep 1
ros2 daemon start 2>/dev/null || true

trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

echo "[1/8] static TF base_link -> laser (x=0.175, y=0, z=0.18, yaw=3.14159)"
tmux new-session -d -s "$SESSION" -n tf
tmux send-keys -t "$SESSION:tf" \
    "$ROS_SETUP && ros2 run tf2_ros static_transform_publisher --x 0.175 --y 0 --z 0.18 --yaw 3.14159 --frame-id base_link --child-frame-id laser" Enter
sleep 2

echo "[2/8] RPLIDAR (Standard mode -> /scan_rplidar)"
tmux new-window -t "$SESSION" -n sllidar
tmux send-keys -t "$SESSION:sllidar" \
    "$ROS_SETUP && ros2 run sllidar_ros2 sllidar_node --ros-args -p serial_port:=/dev/rplidar -p serial_baudrate:=256000 -p frame_id:=laser -p angle_compensate:=true -p scan_mode:=Standard -r /scan:=/scan_rplidar" Enter
sleep 4

echo "[3/8] robot.launch.py (driver + Nav2 wrapper + AMCL + mux + teleop)"
tmux new-window -t "$SESSION" -n robot
tmux send-keys -t "$SESSION:robot" \
    "$ROS_SETUP && export ROBOT_IP=$ROBOT_IP && ros2 launch go2_robot_sdk robot.launch.py nav2:=true slam:=false map:=$MAP rviz2:=false foxglove:=false enable_tts:=false decode_lidar:=false" Enter
echo "  Waiting 30s for nav stack lifecycle"
sleep 30

echo "[4/8] reactive_stop_node (safety_only mode → /cmd_vel_obstacle, only 0 on danger)"
# safety_only=true is REQUIRED when feeding mux (priority 200). Without it,
# clear/slow zones would publish 0.45/0.60 m/s and shadow nav (priority 10)
# permanently — Go2 would drive forward at reactive's normal_speed instead of
# obeying nav.
tmux new-window -t "$SESSION" -n reactive
tmux send-keys -t "$SESSION:reactive" \
    "$ROS_SETUP && ros2 run go2_robot_sdk reactive_stop_node --ros-args -p safety_only:=true" Enter
sleep 3

echo "[5/8] nav_capability.launch.py (4 nodes)"
tmux new-window -t "$SESSION" -n navcap
tmux send-keys -t "$SESSION:navcap" \
    "$ROS_SETUP && ros2 launch nav_capability nav_capability.launch.py named_poses_file:=$NAV_NAMED routes_dir:=$NAV_ROUTES" Enter
sleep 5

echo "[6/8] enable nav_pause runtime (15s delay)"
tmux new-window -t "$SESSION" -n pause-enable
tmux send-keys -t "$SESSION:pause-enable" \
    "$ROS_SETUP && sleep 15 && ros2 param set /reactive_stop_node enable_nav_pause true && echo 'enable_nav_pause=true active'" Enter

echo "[7/8] foxglove_bridge (optional, uses launch file — known-good path)"
tmux new-window -t "$SESSION" -n foxglove
tmux send-keys -t "$SESSION:foxglove" \
    "$ROS_SETUP && ros2 launch foxglove_bridge foxglove_bridge_launch.xml port:=8765" Enter

echo "[8/8] monitor window (manual ros2 commands)"
tmux new-window -t "$SESSION" -n monitor
tmux send-keys -t "$SESSION:monitor" "$ROS_SETUP" Enter

echo ""
echo "=== Started ==="
echo ""
echo "Sanity checks (run in monitor window):"
echo "  ros2 topic hz /scan_rplidar             # ~10 Hz"
echo "  ros2 topic hz /cmd_vel                  # only when goal active"
echo "  ros2 topic hz /state/nav/heartbeat      # 1 Hz"
echo "  ros2 topic hz /state/nav/status         # 10 Hz"
echo "  ros2 topic hz /state/nav/safety         # 10 Hz"
echo "  ros2 topic echo /state/nav/safety       # check driver_alive/lidar_alive/amcl_health"
echo "  ros2 action list | grep nav             # 4 actions"
echo "  ros2 service list | grep nav            # 3 services"
echo ""
echo "Phase 10 KPI verification:"
echo "  K1+K2  python3 scripts/send_relative_goal.py --distance 0.5  (x5 then 0.8 x5)"
echo "  K4     ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute \"{route_id: 'sample'}\""
echo "  K5     trigger danger zone (person enters 0.6m front); should auto-pause; step away -> resume"
echo "  K7     python3 nav_capability/scripts/emergency_stop.py engage  (then release)"
echo "  K8     python3 -m pytest nav_capability/test/integration/test_mux_priority.py"
echo "  K9     timeout 60 ros2 topic hz /state/nav/heartbeat (>=0.95) and status (>=9) and safety (>=9)"
echo "  K10    ros2 action send_goal /log_pose go2_interfaces/action/LogPose \"{name: 'alpha', log_target: 'named_poses'}\""
echo ""
echo "Attach: tmux attach -t $SESSION"
echo "Kill:   tmux kill-session -t $SESSION"
