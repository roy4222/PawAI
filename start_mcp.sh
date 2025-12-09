#!/bin/zsh
# 一鍵啟動 MCP 所需的所有服務
# 用法: zsh start_mcp.sh

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 專案路徑
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
CONNECT_IF="${CONNECT_IF:-enp0s1}"

echo -e "${BLUE}🐕 啟動 Go2 MCP 控制系統...${NC}"

# ==========================================
# ROS2 環境載入函數（複用自 phase1_test.sh）
# ==========================================
load_ros_env() {
    echo -e "${BLUE}🔧 載入 ROS2 環境...${NC}"
    source /opt/ros/humble/setup.zsh
    cd $SCRIPT_DIR
    source ~/ros2_ws/install/setup.zsh
    export CONN_TYPE=webrtc
    export ROBOT_IP="192.168.12.1"
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    export CYCLONEDDS_URI="/home/roy422/cyclonedds_dual.xml"
    echo -e "${GREEN}✅ 環境已載入${NC}"
}

# ==========================================
# 網路檢查（參考 phase1_test.sh step_env）
# ==========================================
check_network() {
    echo -e "${YELLOW}🔍 檢查網路連通性...${NC}"
    
    # 測試 Go2 連線
    if ping -c 1 192.168.12.1 > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Go2 機器狗連線正常${NC}"
    else
        echo -e "${RED}❌ 無法連接 Go2 機器狗 (192.168.12.1)${NC}"
        echo -e "${YELLOW}請先執行: zsh phase1_test.sh env${NC}"
        exit 1
    fi
}

# ==========================================
# 檢查 tmux session
# ==========================================
if tmux has-session -t go2_mcp 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Session 'go2_mcp' 已存在！${NC}"
    echo -e "📋 選項："
    echo -e "  1. ${BLUE}tmux attach -t go2_mcp${NC}  （連接到現有 session）"
    echo -e "  2. ${BLUE}tmux kill-session -t go2_mcp${NC}  （刪除後重新啟動）"
    exit 1
fi

# 載入環境並檢查網路
load_ros_env
check_network

# ==========================================
# 使用 tmux 管理多個 Terminal
# ==========================================
echo -e "${BLUE}📺 建立 tmux session...${NC}"
tmux new-session -d -s go2_mcp

# Pane 0: rosbridge (啟動快，約 2-3 秒)
tmux send-keys -t go2_mcp:0 "cd $SCRIPT_DIR && zsh phase1_test.sh bridge" C-m

# 水平分割 - Pane 1: Driver (WebRTC 握手需要時間)
tmux split-window -h -t go2_mcp:0
tmux send-keys -t go2_mcp:0.1 "sleep 3 && cd $SCRIPT_DIR && zsh start_go2_simple.sh" C-m

# 垂直分割 - Pane 2: snapshot_service (等 Driver 就緒後啟動)
tmux split-window -v -t go2_mcp:0.0
tmux send-keys -t go2_mcp:0.2 "sleep 8 && cd $SCRIPT_DIR && \
source /opt/ros/humble/setup.zsh && \
source ~/ros2_ws/install/setup.zsh && \
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp && \
export CYCLONEDDS_URI=/home/roy422/cyclonedds_dual.xml && \
ros2 run go2_robot_sdk snapshot_service" C-m

# 連接到 session
echo -e "${GREEN}✅ 所有服務已啟動中...${NC}"
echo -e "${YELLOW}⏳ 請等待約 12 秒讓系統就緒...${NC}"
echo -e "📋 連接 tmux session: ${BLUE}tmux attach -t go2_mcp${NC}"
echo -e "🛑 停止服務: ${BLUE}tmux kill-session -t go2_mcp${NC}"

tmux attach -t go2_mcp
