#!/usr/bin/env zsh

#
# 快速啟動 Go2 機器人驅動
# 用途：最小化啟動 - 只啟動機器人驅動和感測器，不啟用 SLAM/Nav2/RViz
#

set -e

# 若使用者以 bash 執行，重新以 zsh 啟動以避免 setup.zsh 語法錯誤
if [ -z "$ZSH_VERSION" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
WORKSPACE_ROOT=$(cd "$SCRIPT_DIR/../.." && pwd)

# 設置顏色輸出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   Go2 機器人驅動 - 快速啟動${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 默認機器人 IP
ROBOT_IP="${ROBOT_IP:-192.168.12.1}"
CONN_TYPE="${CONN_TYPE:-webrtc}"

# 可選：允許命令行參數覆蓋 IP
if [ "$#" -gt 0 ]; then
    ROBOT_IP="$1"
fi

echo -e "${YELLOW}環境配置：${NC}"
echo "  Robot IP: $ROBOT_IP"
echo "  Connection Type: $CONN_TYPE"
echo "  Workspace: $WORKSPACE_ROOT"
echo ""

# source ROS2
echo -e "${YELLOW}載入 ROS2 環境...${NC}"
source /opt/ros/humble/setup.zsh

# source workspace
echo -e "${YELLOW}載入 workspace...${NC}"
source "$WORKSPACE_ROOT/install/setup.zsh"

# 導出機器人 IP
export ROBOT_IP="$ROBOT_IP"
export CONN_TYPE="$CONN_TYPE"

# ⚠️ 關鍵修正：設定 CycloneDDS 環境變數（與 phase1_test.sh 保持一致，若外部已設定則不覆蓋）
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI="${CYCLONEDDS_URI:-/home/roy422/local_only_v2.xml}"

echo -e "${GREEN}✓ 環境已準備 (CycloneDDS: $CYCLONEDDS_URI)${NC}"
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  啟動中... (按 Ctrl+C 停止)${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 啟動最小化配置
ros2 launch go2_robot_sdk robot.launch.py \
  rviz2:=false \
  slam:=false \
  nav2:=false \
  foxglove:=false \
  joystick:=false \
  teleop:=false
