# Phase 1 執行指南書 - SLAM + Nav2 小空間驗證

**日期：** 2025/11/21
**目標：** 驗證 SLAM + Nav2 基本通訊與流程（1-2 坪小空間）
**總耗時：** 約 30-40 分鐘
**預期成果：** 確認系統能運作，為 Phase 2 大空間測試做準備

---

## 🚀 快速開始 - Headless/Foxglove 版（複製貼上即可）

你在 Mac VS Code SSH（無 GUI）操作，所有視覺改用 Foxglove，所有控制改用 CLI。請在 VS Code 開**至少三個終端分頁**（建圖時可能需要第四個用於控制機器狗移動）。

### 🛠️ 前置（每次開機）
1. Mac 連 `Go2-xxxx`，Shared 網卡保持上網。  
2. VS Code SSH 進 Ubuntu。  
3. 執行 `connect_dog`；`ping -c 3 192.168.12.1` 確認通。  

### Terminal 1：啟動驅動
```zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh start_go2_simple.sh
# 等到看到 "Video frame received" 或 "✓ 環境已準備"
# start_go2_simple.sh 會自動載入 ROS2 環境，無需手動 source
```

### Terminal 2：環境 + /scan 頻寬監控
```zsh
# 先設定環境（路徑是 ros2_ws/src/elder_and_dog）
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh   # 若檔案不存在，先 colcon build 再 source
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# ⚠️ 等待 Terminal 1 出現 "Video frame received" 後再執行下方指令

# 監控頻寬
ros2 topic hz /scan
# 應顯示 "average rate: 7.XX hz"
# 如果 < 5 Hz，代表頻寬有問題（見下方故障排查）
# 如果顯示「topic [/scan] does not appear to be published yet」，確認 Terminal 1 驅動是否已完全啟動
```

### Terminal 3：啟動 SLAM + Nav2 + Foxglove（不開 RViz）
```zsh
# 先設定環境（與 Terminal 2 相同）
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# 啟動導航堆疊（包含 Foxglove，不開 RViz）
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=false foxglove:=true
```

### Mac 端（Chrome）：用 Foxglove 取代 RViz
1. 打開 `https://studio.foxglove.dev/`
2. Open Connection → Foxglove WebSocket → `ws://192.168.64.2:8765`
   - ⚠️ 確認 IP：在 VM 中執行 `ip addr show enp0s1` 查看 Shared 網卡的 IP
   - ⚠️ 確認 Terminal 3 已啟動且有 `foxglove:=true` 參數
3. 面板設定：3D 啟用 `/map`, `/scan`, TF, Robot Model；需要時加影像面板。

### 驗證 SLAM（無需 Start At Dock）
- Foxglove 3D 若看到黑白網格在更新，表示 slam_toolbox 已建圖。  
- 若沒地圖，Terminal 2 跑 `ros2 topic hz /map` 確認是否有資料。

### 建圖移動（用指令代替手把）
開啟新的 Terminal 4（或使用 Terminal 2），執行：
```zsh
# 先設定環境（若是新終端）
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"

# 控制機器狗移動以建立地圖
zsh TEST.sh forward
sleep 1
zsh TEST.sh left
sleep 1
zsh TEST.sh forward
```
觀察 Foxglove 地圖是否擴展。

**提示**：執行 `zsh TEST.sh help` 可查看所有可用指令（sit, stand, forward, backward, left, right 等）。

### 儲存地圖（CLI）
```zsh
# 建立地圖目錄
mkdir -p /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps

# 儲存地圖
ros2 run nav2_map_server map_saver_cli -f /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1

# 驗證檔案
ls -lh /home/roy422/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1*
```

### 測試導航（取代 RViz 2D Goal）
- **方法 A（Foxglove）**：3D 面板右上角「Publish Navigation Goal」，在白色空地點擊拖曳方向。  
- **方法 B（Python 腳本）**：  
```zsh
python3 /home/roy422/ros2_ws/src/elder_and_dog/scripts/nav2_goal_autotest.py --distance 0.5
```

---

## 📋 Phase 1 完整檢查清單

在你執行上述指令後，請核對以下檢查項：

```
□ Terminal 1: 驅動啟動，出現 "Video frame received"
□ Terminal 2: /scan 頻率 > 5 Hz
□ Foxglove: 地圖網格持續更新（建圖成功）
□ Terminal 2: /map 頻率 ~1 Hz
□ Foxglove: TF/Robot Model 顯示正常
□ maps 目錄有 phase1.{yaml,pgm} 存檔
□ 導航成功（Foxglove 目標或 nav2_goal_autotest 腳本）
```

**若所有項都打勾，恭喜！Phase 1 通過，可以進行 Phase 2。**

---

## 🔴 故障排查

### 問題 1：/scan 頻率低於 5 Hz（頻寬耗盡）

**症狀：**
- `ros2 topic hz /scan` 顯示 1-2 Hz 而非 7 Hz
- 地圖建不起來或建圖很慢
- 視覺化（Foxglove/RViz）非常卡頓

**解決方案：**
1. **關閉高頻寬顯示：**
   - Foxglove：先暫時移除高頻影像/點雲面板
   - RViz（若有 GUI）：取消勾選 Image / PointCloud2 / DepthCloud

2. **確認 WiFi 訊號：**
   ```zsh
   # Terminal 2：檢查 WiFi 強度
   iwconfig wlan0 | grep "Signal level"
   # 應 > -50 dBm（信號良好）
   ```

3. **若仍未改善，重啟系統：**
   ```zsh
   # Terminal 3 按 Ctrl+C 停止 ros2 launch
   # Terminal 1 按 Ctrl+C 停止驅動
   # 等待 5 秒
   # 重新執行：驅動 → ROS2 → ros2 launch
   ```

---

### 問題 2：地圖沒有更新或為空白

**症狀：**
- RViz 的地圖視窗空白或無變化
- `/map` 頻率為 0 Hz

**原因與解決：**

| 原因 | 檢查步驟 | 解決方案 |
|------|--------|--------|
| SLAM 未啟動 | `ros2 node list \| grep slam` | 重新執行 `ros2 launch` 時確保 `slam:=true` |
| /scan 無輸入 | `ros2 topic echo /scan --max-count 1` | 檢查機器狗驅動是否正常（Terminal 1 日誌） |
| LiDAR 故障 | 機器狗遠程查看 LiDAR 是否轉動 | 機器狗可能需要重啟 |
| SlamToolbox 未正常初始化 | 確認 `ros2 topic hz /map` 有輸出 | 重啟 ros2 launch；Headless 模式無需按 Start At Dock |

---

### 問題 3：看不到 SlamToolboxPlugin

**症狀：** RViz 中找不到 SlamToolboxPlugin 或 "Start At Dock" 按鈕

**解決方案：**
1. **在 Displays 清單中新增：**
   - Displays 面板 → "Add" 按鈕
   - 搜尋 "SlamToolboxPlugin"
   - 點擊添加

2. **若找不到，檢查 SLAM Toolbox 是否安裝：**
   ```zsh
   apt list --installed | grep slam-toolbox
   # 應看到 slam-toolbox 相關套件
   ```

---

### 問題 4：導航目標（2D Goal）沒有反應

**症狀：**
- 在 Foxglove 發送目標後無反應，或機器狗不動

**檢查步驟：**
1. **確認 Costmap 已初始化：**
   ```zsh
   ros2 topic echo /global_costmap/costmap --max-count 1
   # 應有資料輸出
   ```

2. **確認 Nav2 節點都在運行：**
   ```bash
   ros2 node list | grep nav2
   # 應看到：/amcl_node, /planner_server, /controller_server
   ```

3. **若 Costmap 還未出現，等待 10 秒（Nav2 啟動慢）：**
   ```zsh
   # 等待期間觀察 Foxglove /map 及 TF 變化
   ```

4. **若仍無反應，檢查機器狗位置與地圖對齐：**
   ```zsh
   # Terminal 2：查看定位
   ros2 topic echo /amcl_pose --max-count 1
   # 應有數值（如 x: 0.1, y: 0.2）而非全 0
   ```

   **若位置全為 0，需手動初始化：**
   - Foxglove 3D 右上「Publish Pose」設定初始位姿，或在有 GUI 的 RViz 用 2D Pose Estimate

---

### 問題 5：地圖存檔失敗

**症狀：**
- `map_saver_cli` 執行後無輸出或出錯

**解決方案：**
```zsh
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

1. **記錄結果：**
   - 打開 `/home/roy422/ros2_ws/src/elder_and_dog/docs/04-notes/dev_notes/20251121_slam_test.md`
   - 填寫所有「Phase 1」的欄位（時間、頻率、結果等）

2. **準備 Phase 2：**
   - 清出 4-5 坪的空間
   - 放置 3-5 個障礙物（椅子、盒子）
   - 標記起點位置
   - 準備好後按照 `PHASE2_EXECUTION_GUIDE.md` 進行

3. **若出問題：**
   - 檢查故障排查部分
   - 記錄下遇到的問題與解決方案
   - 這些資訊對後續 VLM + 尋物 FSM 開發很有幫助

---

**祝測試順利！有任何問題隨時回報。** 🚀
