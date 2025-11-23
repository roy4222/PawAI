# Phase 1 執行指南 - SLAM + Nav2 小空間驗證（最終穩健版）

**日期：** 2025/11/23（更新版）
**目標：** 驗證 SLAM + Nav2 基本通訊與流程（1-2 坪小空間）
**總耗時：** 約 30-40 分鐘
**預期成果：** 確認系統能運作，為 Phase 2 大空間測試做準備

---

## 🛠️ 步驟零：環境就緒（每次開機做一次）

### 前置條件
1. **Mac 本機**：Wi-Fi 連上 `Go2-xxxx`，Shared 網卡（有線或另一個 Wi-Fi）保持上網。
2. **VS Code**：SSH 連入 Ubuntu VM (預設 `192.168.64.2`)。

### 執行指令

```bash
# 1. 載入 Zsh 設定（如果你的 .zshrc 已包含 ROS2 環境）
source ~/.zshrc

# 2. 喚醒 Go2 網卡（需 sudo 權限）
connect_dog

# 3. 確認雙通（兩個都要通）
ping -c 1 google.com        # ✅ 延遲 ~3ms（網際網路）
ping -c 1 192.168.12.1      # ✅ 延遲 ~10ms（Go2 機器狗）
```

### 🔧 建立 `connect_dog` alias（首次設定，只需執行一次）

如果執行 `connect_dog` 時顯示 "command not found"，請建立 alias：

```bash
cat >> ~/.zshrc << 'EOF'

# ==========================================
# Go2 機器狗網路配置 alias
# ==========================================
alias connect_dog='sudo ip addr flush dev enp0s2 && \
sudo ip addr add 192.168.12.222/24 dev enp0s2 && \
sudo ip link set enp0s2 up && \
sudo ip route add 192.168.12.0/24 dev enp0s2 && \
echo "✅ Go2 網路已配置完成 (192.168.12.222)"'
EOF

# 重新載入設定
source ~/.zshrc

# 現在可以使用了
connect_dog
```

**注意事項**：
- ⚠️ 如果看到 `RTNETLINK answers: File exists`，表示 IP 已經設定過，可以忽略（正常現象）
- ⚠️ 需要 `sudo` 權限，第一次執行會要求輸入密碼
- ⚠️ 確認網卡名稱是 `enp0s2`（執行 `ip link` 確認）

---

## ⚡ 快速模式：一鍵腳本（推薦新手）

如果你覺得手動貼指令太麻煩，可以使用自動化腳本 `phase1_test.sh`：

### **步驟 1：環境檢查（單一終端）**

```bash
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh env
```

這會自動：
- 建立 `connect_dog` alias（如果還沒有）
- 配置 Go2 網卡
- 測試網路雙通（Google + Go2）

### **步驟 2：開 4 個終端執行**

**Terminal 1:**
```bash
zsh phase1_test.sh t1
```

**Terminal 2:**（等 T1 出現 "Video frame received"）
```bash
zsh phase1_test.sh t2
```

**Terminal 3:**
```bash
zsh phase1_test.sh t3
```

**Terminal 4:**（互動模式）
```bash
zsh phase1_test.sh t4
```

在 Terminal 4 輸入 `auto` 即可自動巡房建圖！

### **步驟 3：儲存地圖和測試（任一終端）**

```bash
# 儲存地圖
zsh phase1_test.sh save_map

# 測試導航
zsh phase1_test.sh nav_test

# 檢查所有項目狀態
zsh phase1_test.sh check
```

---

## 🚀 標準模式：4 Terminal 分工架構

如果你想了解每個步驟的細節，或需要客製化參數，請使用以下標準流程。

你在 Mac VS Code SSH（無 GUI）操作，所有視覺改用 Foxglove，所有控制改用 CLI。
請在 VS Code 開**4 個終端分頁**。

---

## 📡 Terminal 1：啟動驅動

**目的**：啟動 Go2 機器狗的基礎驅動（感測器、相機、LiDAR）

```bash
# Terminal 1
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh start_go2_simple.sh
```

**檢查點**：
- ✅ 看到 `"Video frame received"` 或 `"✓ 環境已準備"`
- ✅ **不要關閉這個終端**，讓它持續運行
- ℹ️ `start_go2_simple.sh` 會自動載入 ROS2 環境，無需手動 source

---

## 📊 Terminal 2：系統監控

**目的**：監控關鍵 topic 頻率，確保頻寬正常。

```bash
# Terminal 2
# 載入環境（若 .zshrc 已包含，可省略前兩行）
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# ⚠️ 等待 Terminal 1 出現 "Video frame received" 後再執行

# 監控雷達頻率
ros2 topic hz /scan
# 應顯示 "average rate: 7.XX hz"
# 如果 < 5 Hz，代表頻寬有問題（見下方故障排查）
```

**標準值**：
- `/scan`: ~7 Hz（如果 < 5 Hz，Foxglove 需關閉相機影像面板）
- `/map`: ~1 Hz（SLAM 啟動後才有）

---

## 🤖 Terminal 3：啟動 SLAM + Nav2 + Foxglove

**目的**：啟動建圖、導航、視覺化系統。

```bash
# Terminal 3
# 載入環境
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# 啟動導航堆疊（包含 Foxglove，不開 RViz）
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=false foxglove:=true
```

**檢查點（Terminal 3 日誌）**：
- ✅ `[slam_toolbox-X] ...` → SLAM 正常
- ✅ `[amcl-X] ...` → Nav2 定位正常
- ✅ `[foxglove_bridge-X] Server listening on port 8765` → Foxglove 正常
- ✅ 無持續性紅色 ERROR（少量 WARN 可忽略）

---

## 🖥️ Mac 端：Foxglove 視覺化

**前提**：
- ✅ Terminal 3 已啟動且出現 `Server listening on port 8765`
- ✅ VM 防火牆已關閉（`sudo ufw status` 應顯示 `inactive`）

**操作步驟**：

1. **連線 Foxglove**
   - 打開 Chrome：`https://studio.foxglove.dev/`
   - **Open Connection** → **Foxglove WebSocket**
   - 輸入：`ws://192.168.64.2:8765`
   - ⚠️ **確認 IP**：在 VM 執行 `ip addr show enp0s1 | grep "inet "` 查看 Shared 網卡 IP

2. **設定 3D 面板**（如果是第一次使用）
   - 點擊左側 **Add Panel** → 選擇 **3D**
   - 在 3D 面板設定中啟用：
     - `/map` (Topic: nav_msgs/OccupancyGrid)
     - `/scan` (Topic: sensor_msgs/LaserScan)
     - `TF` (勾選顯示座標系)
     - `Robot Model` (勾選顯示機器人模型)

3. **可選：相機影像面板**
   - 新增 **Image** 面板 → 選擇 `/camera/image`
   - ⚠️ **注意**：影像會消耗大量頻寬，建圖時建議關閉

**檢查點（Foxglove）**：
- ✅ 3D 面板出現機器人模型（Robot Model）
- ✅ `/scan` topic 有綠色雷射點
- ✅ `/map` 開始出現黑白網格（可能需要等待 10-20 秒）

---

## 🎮 Terminal 4：建圖移動

**目的**：用 CLI 指令控制機器狗移動，讓 SLAM 掃描環境建立地圖。

```bash
# Terminal 4
# 載入環境
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# 控制機器狗移動（一邊看 Foxglove 地圖變化）
# 腳本位於 ~/ros2_ws/src/elder_and_dog/TEST.sh
zsh TEST.sh forward   # 前進 3 秒
sleep 2
zsh TEST.sh left      # 左轉 3 秒
sleep 2
zsh TEST.sh forward   # 再前進 3 秒
sleep 2
zsh TEST.sh right     # 右轉 3 秒
```

**檢查點（Foxglove）**：
- ✅ 地圖上的黑白網格隨著機器狗移動而擴展
- ✅ 白色區域 = 可通行空間，黑色線條 = 障礙物邊界
- ✅ 灰色區域 = 未探索區域

**提示**：
- 執行 `zsh TEST.sh help` 可查看所有可用指令
- 建議讓機器狗繞房間一圈，確保地圖覆蓋完整

---

## 💾 儲存地圖

當你覺得地圖建得夠完整了，執行存檔：

```bash
# 在 Terminal 4 執行
# 1. 建立地圖目錄（如果還沒建）
mkdir -p /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps

# 2. 儲存地圖
ros2 run nav2_map_server map_saver_cli -f /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1

# 3. 驗證檔案
ls -lh /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1*
# 應看到：phase1.yaml (地圖元數據) 和 phase1.pgm (地圖圖像)
```

---

## 🚀 導航測試

**目的**：驗證 Nav2 能否根據地圖自動導航。

### 方法 A：使用 Foxglove GUI

1. 在 Foxglove 3D 面板右上角找到 **Publish Navigation Goal** 按鈕
2. 在地圖的白色（可通行）區域點擊並拖曳箭頭設定方向
3. 鬆開滑鼠，Nav2 會自動規劃路徑並移動機器狗

### 方法 B：使用 Python 腳本（CLI）

```bash
# 在 Terminal 4 執行
python3 /home/roy422/ros2_ws/src/elder_and_dog/scripts/nav2_goal_autotest.py --distance 0.5
```

**成功標準**：
- ✅ 終端機顯示 `Goal succeeded!`
- ✅ 機器狗真的移動了 0.5 公尺並停下
- ✅ Foxglove 地圖上顯示路徑規劃軌跡（綠色/藍色線條）

---

## ✅ Phase 1 完整檢查清單

完成後，請核對以下項目：

```
□ Terminal 1: 驅動啟動成功，看到 "Video frame received"
□ Terminal 2: /scan 頻率 > 5 Hz
□ Terminal 3: SLAM/Nav2/Foxglove 正常運行，無持續 ERROR
□ Foxglove: 連線成功 (ws://192.168.64.2:8765)
□ Foxglove: 地圖網格持續更新（建圖成功）
□ Foxglove: TF/Robot Model 顯示正常
□ maps 目錄有 phase1.{yaml,pgm} 存檔
□ 導航成功（Foxglove 目標或 nav2_goal_autotest 腳本）
```

**若所有項都打勾，恭喜！Phase 1 通過，可以進行 Phase 2。**

---

## 🔴 故障排查

### 問題 1：/scan 頻率低於 5 Hz（頻寬耗盡）

**症狀**：
- `ros2 topic hz /scan` 顯示 1-2 Hz 而非 7 Hz
- 地圖建不起來或建圖很慢
- Foxglove 非常卡頓

**解決方案**：
1. **關閉高頻寬顯示**：Foxglove 暫時移除 Image 面板（相機影像很吃頻寬）
2. **確認 WiFi 訊號**：
   - Mac 端：確認連上 `Go2-xxxx` 而非其他 Wi-Fi
   - 靠近 Go2 機器狗，減少無線干擾
3. **重啟系統**：
   ```bash
   # Terminal 3 按 Ctrl+C 停止 ros2 launch
   # Terminal 1 按 Ctrl+C 停止驅動
   # 等待 5 秒，重新執行 Terminal 1 → Terminal 3
   ```

---

### 問題 2：地圖沒有更新或為空白

**症狀**：
- Foxglove 的地圖視窗空白或無變化
- `/map` 頻率為 0 Hz

**原因與解決**：

| 原因 | 檢查步驟 | 解決方案 |
|------|--------|--------|
| SLAM 未啟動 | `ros2 node list \| grep slam` | 重新執行 Terminal 3，確保 `slam:=true` |
| /scan 無輸入 | `ros2 topic echo /scan --max-count 1` | 檢查 Terminal 1 日誌，確認驅動正常 |
| LiDAR 故障 | 目視機器狗 LiDAR 是否轉動 | 機器狗可能需要重啟 |
| SLAM 初始化中 | 等待 20-30 秒 | SLAM Toolbox 需要時間初始化 |

---

### 問題 3：Foxglove 連不上

**症狀**：
- Chrome 顯示 "Connection failed" 或 "WebSocket error"

**解決方案**：
1. **確認 Terminal 3 已啟動**：
   ```bash
   # 在另一個終端檢查
   ps aux | grep foxglove_bridge
   # 應該有 process 在運行
   ```
2. **確認 VM IP**：
   ```bash
   ip addr show enp0s1 | grep "inet "
   # 應該看到 192.168.64.X/24
   ```
3. **確認防火牆已關閉**（根據你的開發日誌）：
   ```bash
   sudo ufw status
   # 應顯示 "Status: inactive"
   ```
4. **確認 Foxglove 參數**：
   - Terminal 3 啟動時必須有 `foxglove:=true`

---

### 問題 4：導航目標沒有反應

**症狀**：
- 在 Foxglove 發送目標後無反應，或機器狗不動

**檢查步驟**：
1. **確認 Costmap 已初始化**：
   ```bash
   ros2 topic echo /global_costmap/costmap --max-count 1
   # 應有資料輸出
   ```
2. **確認 Nav2 節點都在運行**：
   ```bash
   ros2 node list | grep nav2
   # 應看到：planner_server, controller_server, bt_navigator
   ```
3. **檢查機器狗定位**：
   ```bash
   ros2 topic echo /amcl_pose --max-count 1
   # 應有數值（如 x: 0.1, y: 0.2）而非全 0
   ```

**若位置全為 0，需手動初始化**：
- ⚠️ **關鍵步驟**：在 Foxglove 3D 面板右上角找到 **Publish Pose** 按鈕
- 在地圖上點擊機器狗當前位置，拖曳箭頭設定方向
- 設定初始姿態後，再發送 Navigation Goal

---

### 問題 5：地圖存檔失敗

**症狀**：
- `map_saver_cli` 執行後無輸出或出錯

**解決方案**：
```bash
# 確認目錄存在
mkdir -p /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps

# 確認有寫入權限
ls -ld /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps
# 應看到 drwx...（可寫）

# 重新執行存檔
ros2 run nav2_map_server map_saver_cli -f /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1
```

---

## 📝 完成後的動作

1. **記錄結果**：
   - 建立新的開發日誌：`docs/04-notes/dev_notes/2025-11-23-phase1-test.md`
   - 記錄所有檢查項、頻率數據、遇到的問題與解決方法
   - 截圖 Foxglove 地圖存檔

2. **準備 Phase 2**：
   - 清出 4-5 坪的空間
   - 放置 3-5 個障礙物（椅子、盒子）
   - 標記起點位置
   - 準備好後按照 `PHASE2_EXECUTION_GUIDE.md` 進行

3. **若出問題**：
   - 檢查故障排查部分
   - 記錄下遇到的問題與解決方案
   - 這些資訊對後續 VLM + 尋物 FSM 開發很有幫助

---

## 📌 環境載入快速參考

每個新終端都需要執行（如果你的 `.zshrc` 尚未包含）：

```bash
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"
```

**建議**：將上述指令加入 `~/.zshrc` 的 ROS2 專案區段，未來每次開終端自動載入。

---

**祝測試順利！有任何問題隨時回報。** 🚀
