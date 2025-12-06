#!/bin/zsh
# Phase 1 自動化測試腳本
# 用法: zsh phase1_test.sh [步驟編號]
# 步驟: env, t1, t2, t3, t4, save_map, nav_test, check

set -e  # 遇到錯誤立即停止

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 專案路徑
PROJECT_DIR="/home/roy422/ros2_ws/src/elder_and_dog"
MAP_DIR="$PROJECT_DIR/src/go2_robot_sdk/maps"
CONNECT_IF="${CONNECT_IF:-enp0s1}"   # 可透過環境變數覆蓋實際連狗的網卡

# ROS2 環境載入函數
load_ros_env() {
    echo -e "${BLUE}🔧 載入 ROS2 環境...${NC}"
    source /opt/ros/humble/setup.zsh
    cd $PROJECT_DIR
    source install/setup.zsh
    export CONN_TYPE=webrtc
    export ROBOT_IP="192.168.12.1"
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

    # CycloneDDS 配置選擇（根據使用場景）
    # - local_only_v2.xml：開發模式（VM 內部測試，解決雙網卡問題）
    # - cyclonedds_dual.xml：整合模式（支援 Windows RViz2 零延遲控制）
    if [[ -n "$USE_WINDOWS_RVIZ2" ]]; then
        export CYCLONEDDS_URI="/home/roy422/cyclonedds_dual.xml"
        echo -e "${GREEN}✅ 環境已載入 (整合模式: Windows RViz2 支援)${NC}"
    else
        export CYCLONEDDS_URI="/home/roy422/local_only_v2.xml"
        echo -e "${GREEN}✅ 環境已載入 (開發模式: VM 內部測試)${NC}"
    fi

    echo -e "${BLUE}   CycloneDDS 配置: $CYCLONEDDS_URI${NC}"
}

# 步驟零：環境檢查
step_env() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}步驟零：環境就緒檢查${NC}"
    echo -e "${BLUE}========================================${NC}"

    # 強力網路清洗，避免 DHCP/NetworkManager 重新塞入干擾 IP
    echo -e "${BLUE}🧹 正在執行強力網路清洗...${NC}"
    sudo systemctl stop NetworkManager 2>/dev/null || true
    sudo killall dhclient 2>/dev/null || true
    sudo ip addr flush dev "$CONNECT_IF"
    sudo ip addr add 192.168.12.222/24 dev "$CONNECT_IF"
    sudo ip link set "$CONNECT_IF" up
    sudo ip route add 192.168.12.0/24 dev "$CONNECT_IF" 2>/dev/null || true
    echo -e "${GREEN}✅ 網路清洗完成 (只保留 192.168.12.222 on $CONNECT_IF)${NC}"

    # 載入 zsh 設定
    echo -e "${YELLOW}1. 載入 Zsh 設定...${NC}"
    source ~/.zshrc

    # 喚醒 Go2 網卡
    echo -e "${YELLOW}2. 配置 Go2 網卡（需要 sudo 權限）...${NC}"

    # 先檢查是否已經寫入過 alias
    if ! grep -q "alias connect_dog=" ~/.zshrc; then
        echo -e "${YELLOW}正在建立 connect_dog alias...${NC}"
        cat >> ~/.zshrc << 'EOF'

# ==========================================
# Go2 機器狗網路配置 alias
# ==========================================
alias connect_dog='sudo ip addr flush dev enp0s1 && \
sudo ip addr add 192.168.12.222/24 dev enp0s1 && \
sudo ip link set enp0s1 up && \
echo "✅ Go2 網路已配置完成 (192.168.12.222)"'
EOF
        echo -e "${GREEN}✅ connect_dog alias 已寫入 ~/.zshrc${NC}"
    fi

    # 重新載入 zsh 設定
    source ~/.zshrc

    # 直接執行網卡配置（不管 alias 是否生效）
    echo -e "${YELLOW}配置網卡...${NC}"
    sudo ip addr flush dev "$CONNECT_IF"
    sudo ip addr add 192.168.12.222/24 dev "$CONNECT_IF"
    sudo ip link set "$CONNECT_IF" up
    echo -e "${GREEN}✅ Go2 網路已配置完成 (192.168.12.222) on $CONNECT_IF${NC}"

    # 測試雙通
    echo -e "${YELLOW}3. 測試網路連通性...${NC}"
    echo -e "${BLUE}   測試網際網路...${NC}"
    if ping -c 1 google.com > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ 網際網路連線正常${NC}"
    else
        echo -e "${RED}   ❌ 無法連接網際網路${NC}"
        exit 1
    fi

    echo -e "${BLUE}   測試 Go2 機器狗連線...${NC}"
    if ping -c 1 192.168.12.1 > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Go2 機器狗連線正常${NC}"
    else
        echo -e "${RED}   ❌ 無法連接 Go2 機器狗 (192.168.12.1)${NC}"
        echo -e "${YELLOW}   請確認：${NC}"
        echo -e "${YELLOW}     1. Mac 主機已連接 Go2-xxxx Wi-Fi${NC}"
        echo -e "${YELLOW}     2. UTM Network 0 已橋接至 Wi-Fi (en0)${NC}"
        exit 1
    fi

    echo -e "${BLUE}   測試 Windows 連線...${NC}"
    if ping -c 1 192.168.1.146 > /dev/null 2>&1; then
        echo -e "${GREEN}   ✅ Windows 連線正常 (192.168.1.146)${NC}"
    else
        echo -e "${YELLOW}   ⚠️  無法連接 Windows (192.168.1.146)${NC}"
        echo -e "${YELLOW}   Windows RViz2 可能無法使用，但實機測試可繼續${NC}"
    fi

    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ 環境檢查完成！可以開始測試${NC}"
    echo -e "${GREEN}========================================${NC}\n"

    echo -e "${YELLOW}下一步：開 4 個終端，分別執行：${NC}"
    echo -e "  Terminal 1: ${BLUE}zsh phase1_test.sh t1${NC}"
    echo -e "  Terminal 2: ${BLUE}zsh phase1_test.sh t2${NC} (等 T1 出現 'Video frame received')"
    echo -e "  Terminal 3: ${BLUE}zsh phase1_test.sh t3${NC}"
    echo -e "  Terminal 4: ${BLUE}zsh phase1_test.sh t4${NC} (用來控制移動)"
}

# Terminal 1: 啟動驅動
step_t1() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Terminal 1: 啟動 Go2 驅動${NC}"
    echo -e "${BLUE}========================================${NC}"

    # ⚠️ 關鍵修正：必須載入環境，否則 RMW/CYCLONEDDS 設定會丟失
    load_ros_env

    echo -e "${YELLOW}執行: zsh start_go2_simple.sh${NC}"
    echo -e "${YELLOW}請等待看到 'Video frame received'...${NC}\n"

    # 使用 source 而非 zsh，讓環境變數可以傳遞
    source start_go2_simple.sh
}

# Terminal 2: 監控頻率
step_t2() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Terminal 2: 監控 /scan 頻率${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    echo -e "${YELLOW}⚠️  請確認 Terminal 1 已出現 'Video frame received'${NC}"
    echo -e "${YELLOW}監控 /scan topic 頻率（應該 > 5 Hz）...${NC}\n"

    ros2 topic hz /scan
}

# Terminal 3: 啟動 SLAM + Nav2 + Foxglove
step_t3() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Terminal 3: 啟動 SLAM + Nav2 + Foxglove${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    echo -e "${YELLOW}啟動導航堆疊...${NC}"
    echo -e "${YELLOW}等待看到 'Server listening on port 8765'...${NC}\n"

    ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=false foxglove:=true
}

# Terminal 4: 控制移動（互動模式）
step_t4() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Terminal 4: 控制機器狗移動${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    # 檢查驅動是否運行
    if ! ros2 node list 2>/dev/null | grep -q go2_driver_node; then
        echo -e "${RED}❌ 錯誤：Go2 驅動節點未運行${NC}"
        echo -e "${YELLOW}請先在 Terminal 1 執行: zsh phase1_test.sh t1${NC}"
        exit 1
    fi

    echo -e "${GREEN}✅ 驅動節點運行中${NC}\n"

    echo -e "${GREEN}可用指令:${NC}"
    echo -e "  ${BLUE}forward${NC}  - 前進 3 秒"
    echo -e "  ${BLUE}backward${NC} - 後退 3 秒"
    echo -e "  ${BLUE}left${NC}     - 左轉 3 秒"
    echo -e "  ${BLUE}right${NC}    - 右轉 3 秒"
    echo -e "  ${BLUE}stop${NC}     - 停止"
    echo -e "  ${BLUE}balance${NC}  - 平衡站立"
    echo -e "  ${BLUE}sit${NC}      - 趴下"
    echo -e "  ${BLUE}stand${NC}    - 站起來"
    echo -e "  ${BLUE}help${NC}     - 顯示所有指令"
    echo -e "  ${BLUE}auto${NC}     - 自動巡房建圖"
    echo -e "  ${BLUE}quit${NC}     - 退出\n"

    while true; do
        echo -ne "${YELLOW}輸入指令 > ${NC}"
        read cmd

        case $cmd in
            quit|exit|q)
                echo -e "${GREEN}退出控制模式${NC}"
                break
                ;;
            auto)
                echo -e "${BLUE}執行自動巡房建圖...${NC}"
                cd $PROJECT_DIR
                zsh TEST.sh forward
                sleep 2
                zsh TEST.sh left
                sleep 2
                zsh TEST.sh forward
                sleep 2
                zsh TEST.sh right
                sleep 2
                zsh TEST.sh forward
                sleep 2
                zsh TEST.sh left
                echo -e "${GREEN}✅ 自動巡房完成${NC}"
                ;;
            help)
                cd $PROJECT_DIR
                zsh TEST.sh help
                ;;
            forward|backward|left|right|stop|balance|sit|stand)
                echo -e "${BLUE}執行: $cmd${NC}"
                cd $PROJECT_DIR
                zsh TEST.sh $cmd
                ;;
            *)
                echo -e "${RED}未知指令: $cmd${NC}"
                echo -e "輸入 ${BLUE}help${NC} 查看可用指令"
                ;;
        esac
    done
}

# 儲存地圖
step_save_map() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}儲存地圖${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    # 建立地圖目錄
    echo -e "${YELLOW}1. 建立地圖目錄...${NC}"
    mkdir -p $MAP_DIR

    # 儲存地圖
    echo -e "${YELLOW}2. 儲存地圖到 $MAP_DIR/phase1...${NC}"
    ros2 run nav2_map_server map_saver_cli -f $MAP_DIR/phase1

    # 驗證檔案
    echo -e "${YELLOW}3. 驗證地圖檔案...${NC}"
    if [[ -f "$MAP_DIR/phase1.yaml" && -f "$MAP_DIR/phase1.pgm" ]]; then
        echo -e "${GREEN}✅ 地圖儲存成功！${NC}"
        ls -lh $MAP_DIR/phase1*
    else
        echo -e "${RED}❌ 地圖儲存失敗${NC}"
        exit 1
    fi
}

# 導航測試
step_nav_test() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}導航測試${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    echo -e "${YELLOW}測試 Nav2 自動導航（前進 0.5 公尺）...${NC}"

    if [[ -f "$PROJECT_DIR/scripts/nav2_goal_autotest.py" ]]; then
        python3 $PROJECT_DIR/scripts/nav2_goal_autotest.py --distance 0.5
    else
        echo -e "${RED}❌ 找不到 nav2_goal_autotest.py${NC}"
        echo -e "${YELLOW}請使用 Foxglove 手動測試導航${NC}"
        exit 1
    fi
}

# 檢查清單
step_check() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}Phase 1 檢查清單${NC}"
    echo -e "${BLUE}========================================${NC}\n"

    load_ros_env

    echo -e "${YELLOW}正在檢查系統狀態...${NC}\n"

    # 檢查 Terminal 1: 驅動
    echo -e "${BLUE}1. 檢查驅動節點...${NC}"
    if ros2 node list | grep -q "go2_driver_node"; then
        echo -e "   ${GREEN}✅ go2_driver_node 運行中${NC}"
    else
        echo -e "   ${RED}❌ go2_driver_node 未運行${NC}"
    fi

    # 檢查 Terminal 2: /scan 頻率
    echo -e "\n${BLUE}2. 檢查 /scan topic 頻率...${NC}"
    echo -e "   ${YELLOW}(執行 5 秒測試)${NC}"
    SCAN_HZ=$(timeout 5 ros2 topic hz /scan 2>&1 | grep "average rate" | awk '{print $3}' || echo "0")
    if (( $(echo "$SCAN_HZ > 5" | bc -l) )); then
        echo -e "   ${GREEN}✅ /scan 頻率: $SCAN_HZ Hz${NC}"
    else
        echo -e "   ${RED}❌ /scan 頻率過低: $SCAN_HZ Hz (應 > 5 Hz)${NC}"
    fi

    # 檢查 Terminal 3: SLAM/Nav2
    echo -e "\n${BLUE}3. 檢查 SLAM 節點...${NC}"
    if ros2 node list | grep -q "slam_toolbox"; then
        echo -e "   ${GREEN}✅ SLAM Toolbox 運行中${NC}"
    else
        echo -e "   ${RED}❌ SLAM Toolbox 未運行${NC}"
    fi

    echo -e "\n${BLUE}4. 檢查 Nav2 節點...${NC}"
    if ros2 node list | grep -q "bt_navigator"; then
        echo -e "   ${GREEN}✅ Nav2 運行中${NC}"
    else
        echo -e "   ${RED}❌ Nav2 未運行${NC}"
    fi

    echo -e "\n${BLUE}5. 檢查 Foxglove Bridge...${NC}"
    if ros2 node list | grep -q "foxglove_bridge"; then
        echo -e "   ${GREEN}✅ Foxglove Bridge 運行中${NC}"
        echo -e "   ${YELLOW}   連線位址: ws://192.168.1.200:8765 (家用網段)${NC}"
    else
        echo -e "   ${RED}❌ Foxglove Bridge 未運行${NC}"
    fi

    # 檢查地圖檔案
    echo -e "\n${BLUE}6. 檢查地圖檔案...${NC}"
    if [[ -f "$MAP_DIR/phase1.yaml" && -f "$MAP_DIR/phase1.pgm" ]]; then
        echo -e "   ${GREEN}✅ 地圖檔案存在${NC}"
        ls -lh $MAP_DIR/phase1*
    else
        echo -e "   ${YELLOW}⚠️  地圖尚未儲存（執行 'zsh phase1_test.sh save_map'）${NC}"
    fi

    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${GREEN}檢查完成！${NC}"
    echo -e "${BLUE}========================================${NC}"
}

# ==========================================
# MCP 相關步驟 (Phase 4+)
# ==========================================

# 啟動 rosbridge (MCP 通訊橋接)
step_bridge() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}啟動 rosbridge (Port 9090)${NC}"
    echo -e "${BLUE}========================================${NC}"

    echo -e "${YELLOW}載入 ROS2 環境...${NC}"
    source /opt/ros/humble/setup.zsh
    export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
    export CYCLONEDDS_URI=/home/roy422/local_only_v2.xml

    echo -e "${GREEN}✅ 環境已載入${NC}"
    echo -e "${YELLOW}啟動 rosbridge WebSocket server...${NC}"
    echo -e "${YELLOW}Port: 9090${NC}\n"

    ros2 launch rosbridge_server rosbridge_websocket_launch.xml
}

# 啟動 MCP 模式 (Driver only, 不含 SLAM/Nav2)
step_mcp() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}MCP 模式：啟動 Go2 Driver (精簡版)${NC}"
    echo -e "${BLUE}========================================${NC}"

    load_ros_env

    echo -e "${YELLOW}啟動 Go2 Driver (不含 SLAM/Nav2)...${NC}"
    echo -e "${YELLOW}適用於 Kilo Code / Claude Desktop MCP 控制${NC}\n"

    ros2 launch go2_robot_sdk robot.launch.py slam:=false nav2:=false
}

# 主函數
main() {
    case "$1" in
        env)
            step_env
            ;;
        t1)
            step_t1
            ;;
        t2)
            step_t2
            ;;
        t3)
            step_t3
            ;;
        t4)
            step_t4
            ;;
        save_map|save)
            step_save_map
            ;;
        nav_test|nav)
            step_nav_test
            ;;
        check)
            step_check
            ;;
        bridge)
            step_bridge
            ;;
        mcp)
            step_mcp
            ;;
        *)
            echo -e "${BLUE}========================================${NC}"
            echo -e "${BLUE}Phase 1 自動化測試腳本${NC}"
            echo -e "${BLUE}========================================${NC}\n"
            echo -e "${YELLOW}用法: zsh phase1_test.sh [步驟]${NC}\n"
            echo -e "可用步驟:"
            echo -e "  ${BLUE}env${NC}       - 步驟零：環境檢查（網路、connect_dog）"
            echo -e "  ${BLUE}t1${NC}        - Terminal 1：啟動 Go2 驅動"
            echo -e "  ${BLUE}t2${NC}        - Terminal 2：監控 /scan 頻率"
            echo -e "  ${BLUE}t3${NC}        - Terminal 3：啟動 SLAM + Nav2 + Foxglove"
            echo -e "  ${BLUE}t4${NC}        - Terminal 4：控制機器狗移動（互動模式）"
            echo -e "  ${BLUE}save_map${NC}  - 儲存地圖到 maps/phase1"
            echo -e "  ${BLUE}nav_test${NC}  - 測試 Nav2 自動導航"
            echo -e "  ${BLUE}check${NC}     - 檢查所有項目狀態"
            echo -e "  ${BLUE}bridge${NC}    - 🆕 啟動 rosbridge (Port 9090)"
            echo -e "  ${BLUE}mcp${NC}       - 🆕 MCP 模式：Driver only (Kilo Code 用)\n"
            echo -e "${YELLOW}建議執行順序（Phase 1 SLAM 測試）:${NC}"
            echo -e "  1. 單一終端執行: ${BLUE}zsh phase1_test.sh env${NC}"
            echo -e "  2. 開 Terminal 1: ${BLUE}zsh phase1_test.sh t1${NC}"
            echo -e "  3. 開 Terminal 2: ${BLUE}zsh phase1_test.sh t2${NC}"
            echo -e "  4. 開 Terminal 3: ${BLUE}zsh phase1_test.sh t3${NC}"
            echo -e "  5. 開 Terminal 4: ${BLUE}zsh phase1_test.sh t4${NC} (輸入 auto 自動建圖)"
            echo -e "  6. 任一終端:     ${BLUE}zsh phase1_test.sh save_map${NC}"
            echo -e "  7. 任一終端:     ${BLUE}zsh phase1_test.sh check${NC}\n"
            echo -e "${YELLOW}MCP 模式（Kilo Code / Claude Desktop）:${NC}"
            echo -e "  1. 單一終端執行: ${BLUE}zsh phase1_test.sh env${NC}"
            echo -e "  2. 開 Terminal 1: ${BLUE}zsh phase1_test.sh bridge${NC}"
            echo -e "  3. 開 Terminal 2: ${BLUE}zsh phase1_test.sh mcp${NC}"
            echo -e "  4. 在 Kilo Code 中使用 ROS2專家 Mode\n"
            ;;
    esac
}

main "$@"
