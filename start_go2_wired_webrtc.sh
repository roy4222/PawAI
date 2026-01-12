#!/usr/bin/env zsh

#
# 🚀 Go2 有線 WebRTC 模式啟動器
# 
# 這是一個針對 Go2 Pro 的「終極方案」：
# 使用有線網路連接 (192.168.123.161)，但跑 WebRTC 協定。
# 優點：穩定、低延遲、無 WiFi 干擾、保留所有視覺功能。
#

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}=======================================${NC}"
echo -e "${BLUE}    Go2 有線 WebRTC 模式 (Wired Mode)   ${NC}"
echo -e "${BLUE}=======================================${NC}"

# 配置區域
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"

echo -e "${YELLOW}1. 檢查網路連線...${NC}"
if ping -c 1 $ROBOT_IP > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 找到機器狗 (IP: $ROBOT_IP)${NC}"
else
    echo -e "${RED}✗ 無法連線至 $ROBOT_IP${NC}"
    echo "請確認：1. 網路線已插好 2. 本機 IP 已設為 192.168.123.x"
    exit 1
fi

echo -e "${YELLOW}2. 載入 ROS2 環境...${NC}"
source /opt/ros/humble/setup.zsh
source install/setup.zsh

echo -e "${YELLOW}3. 啟動驅動程式...${NC}"
echo "模式：Wired WebRTC (Stable & Fast)"

ros2 launch go2_robot_sdk robot.launch.py \
    rviz2:=false \
    slam:=false \
    nav2:=false \
    foxglove:=true \
    joystick:=false \
    teleop:=true
