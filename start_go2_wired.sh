#!/usr/bin/env zsh

#
# 有線模式啟動 Go2 機器人驅動 (CycloneDDS)
# 用途：透過乙太網線連接 Go2，獲得更低延遲
#
# 使用前請確認：
# 1. Mac VM 網卡設定為 192.168.123.x 網段
# 2. Go2 已開機並連接網線
# 3. 可以 ping 通 192.168.123.161
#

set -e

# 若使用者以 bash 執行，重新以 zsh 啟動
if [ -z "$ZSH_VERSION" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

# 設置顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Go2 有線模式 (CycloneDDS)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==========================================
# 有線模式 IP 設定
# ==========================================
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
CONN_TYPE="cyclonedds"

# 可選：允許命令行參數覆蓋 IP
if [ "$#" -gt 0 ]; then
    ROBOT_IP="$1"
fi

echo -e "${YELLOW}有線模式配置：${NC}"
echo "  Robot IP: $ROBOT_IP"
echo "  Connection Type: $CONN_TYPE (CycloneDDS)"
echo "  Workspace: $WORKSPACE_ROOT"
echo ""

# ==========================================
# 檢查網路連通性
# ==========================================
echo -e "${YELLOW}檢查網路連通性...${NC}"

if ping -c 1 192.168.123.161 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ MCU (192.168.123.161) 連線正常${NC}"
else
    echo -e "${RED}✗ 無法連接 MCU (192.168.123.161)${NC}"
    echo -e "${YELLOW}請確認：${NC}"
    echo "  1. 網線已連接"
    echo "  2. Mac VM 網卡 IP 設為 192.168.123.x"
    echo "  3. Go2 已開機"
    exit 1
fi

# 嘗試 ping 其他設備
if ping -c 1 192.168.123.18 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Jetson (192.168.123.18) 連線正常${NC}"
else
    echo -e "${YELLOW}! Jetson (192.168.123.18) 無回應 (Go2 Pro 正常)${NC}"
fi

if ping -c 1 192.168.123.20 > /dev/null 2>&1; then
    echo -e "${GREEN}✓ LiDAR (192.168.123.20) 連線正常${NC}"
else
    echo -e "${YELLOW}! LiDAR (192.168.123.20) 無回應${NC}"
fi

echo ""

# ==========================================
# source ROS2
# ==========================================
echo -e "${YELLOW}載入 ROS2 環境...${NC}"
source /opt/ros/humble/setup.zsh

# source workspace
echo -e "${YELLOW}載入 workspace...${NC}"
source "$WORKSPACE_ROOT/install/setup.zsh"

# ==========================================
# CycloneDDS 設定
# ==========================================
export ROBOT_IP="$ROBOT_IP"
export CONN_TYPE="$CONN_TYPE"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# CycloneDDS 網卡設定 (根據你的實際網卡名稱調整)
NETWORK_IF="${NETWORK_IF:-enp0s1}"
export CYCLONEDDS_URI="<CycloneDDS><Domain><General><NetworkInterfaceAddress>$NETWORK_IF</NetworkInterfaceAddress></General></Domain></CycloneDDS>"

echo -e "${GREEN}✓ CycloneDDS 環境已設定${NC}"
echo "  RMW: $RMW_IMPLEMENTATION"
echo "  Network Interface: $NETWORK_IF"
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  啟動中... (按 Ctrl+C 停止)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# ==========================================
# 啟動 (可選擇是否啟用 SLAM/Nav2)
# ==========================================
# 預設關閉 SLAM/Nav2 以減少複雜度
# 若要啟用，執行: ENABLE_NAV=true zsh start_go2_wired.sh

if [ "${ENABLE_NAV:-false}" = "true" ]; then
    echo -e "${GREEN}啟用 SLAM + Nav2 模式${NC}"
    ros2 launch go2_robot_sdk robot.launch.py \
      rviz2:=true \
      slam:=true \
      nav2:=true \
      foxglove:=false \
      joystick:=false \
      teleop:=false
else
    echo -e "${YELLOW}純驅動模式 (不含 SLAM/Nav2)${NC}"
    ros2 launch go2_robot_sdk robot.launch.py \
      rviz2:=false \
      slam:=false \
      nav2:=false \
      foxglove:=false \
      joystick:=false \
      teleop:=false
fi
