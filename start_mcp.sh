#!/bin/zsh
# 一鍵啟動 MCP 所需的所有服務

set -e
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

echo "🐕 啟動 Go2 MCP 控制系統..."

# 檢查 tmux session 是否已存在
if tmux has-session -t go2_mcp 2>/dev/null; then
    echo "⚠️  Session 'go2_mcp' 已存在！"
    echo "📋 選項："
    echo "  1. tmux attach -t go2_mcp  （連接到現有 session）"
    echo "  2. tmux kill-session -t go2_mcp  （刪除後重新啟動）"
    exit 1
fi

# 使用 tmux 管理多個 Terminal
tmux new-session -d -s go2_mcp

# Pane 0: rosbridge (啟動快，約 2-3 秒)
tmux send-keys -t go2_mcp:0 "cd $SCRIPT_DIR && zsh phase1_test.sh bridge" C-m

# 水平分割 - Pane 1: Driver (WebRTC 握手需要時間)
tmux split-window -h -t go2_mcp:0
tmux send-keys -t go2_mcp:0.1 "sleep 3 && cd $SCRIPT_DIR && zsh start_go2_simple.sh" C-m

# 垂直分割 - Pane 2: snapshot_service (等 Driver 就緒後啟動)
tmux split-window -v -t go2_mcp:0.0
tmux send-keys -t go2_mcp:0.2 "sleep 8 && source ~/ros2_ws/install/setup.zsh && export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp && export CYCLONEDDS_URI=/home/roy422/local_only_v2.xml && ros2 run go2_robot_sdk snapshot_service" C-m

# 連接到 session
echo "✅ 所有服務已啟動中..."
echo "⏳ 請等待約 12 秒讓系統就緒..."
echo "📋 連接 tmux session: tmux attach -t go2_mcp"
echo "🛑 停止服務: tmux kill-session -t go2_mcp"

tmux attach -t go2_mcp
