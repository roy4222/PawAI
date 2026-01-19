#!/usr/bin/env zsh
set -e

export ROBOT_IP=${ROBOT_IP:-"192.168.123.161"}
export CONN_TYPE=${CONN_TYPE:-"webrtc"}

if ! ping -c 1 "$ROBOT_IP" > /dev/null 2>&1; then
  echo "無法連線至 $ROBOT_IP，請確認網路與 IP 設定"
  exit 1
fi

source /opt/ros/humble/setup.zsh
source /home/roy422/ros2_ws/install/setup.zsh

ros2 launch go2_robot_sdk robot.launch.py \
  slam:=true \
  nav2:=false \
  rviz2:=false \
  foxglove:=true \
  joystick:=false \
  teleop:=true
