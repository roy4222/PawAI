# Phase 1.5 執行指南 - SLAM + Nav2 大空間雙視覺化驗證（終極版）

**日期：** 2025/12/01（Phase 1 架構驗證完成後）
**目標：** 驗證雙視覺化架構（Windows RViz2 + Foxglove）+ SLAM/Nav2 導航閉環（3-5 坪空間）
**總耗時：** 約 2-3 小時
**預期成果：** 確認基礎架構完全穩定，為座標轉換與 VLM 整合做準備

**🏆 核心突破：** Windows ↔ Mac VM Native DDS 零延遲架構已於 2025/11/30 驗證成功！

---

---

## 📊 Phase 1.5 架構總覽

### 網路拓樸（雙橋接架構）

```
Go2 機器狗 (192.168.12.1)
    ↓ (Wi-Fi)
Mac 主機 (192.168.12.117) Wi-Fi 網卡
    ↓ (UTM Bridge - Wi-Fi)
Ubuntu VM (enp0s1: 192.168.12.222) ← 連接 Go2 (Wi-Fi 橋接)
         (enp0s2: 192.168.1.200)   ← 連接家用網路 (有線橋接)
    ↓ (有線網路 Native DDS)
Windows 開發機 (192.168.1.146)
    ├─ RViz2 (零延遲主控) ← Phase 1.5 新增
    └─ Foxglove Studio (監控備案)
```

### 雙視覺化分工

| 工具 | 用途 | 優勢 | 延遲 |
|------|------|------|------|
| **Windows RViz2** | 主控介面 | Native DDS，零延遲（< 1ms），發送導航目標 | **< 1ms** |
| **Foxglove Studio** | 監控備案 | WebSocket，跨平台，影像串流友善 | ~50-100ms |

---

## 🛠️ 步驟零：環境就緒（每次開機執行一次）

### 前置條件檢查清單

- [ ] **Mac 主機**：Wi-Fi 連上 `Go2-xxxx`（192.168.12.x）
- [ ] **Mac 主機**：有線網卡連上家用路由器（192.168.1.x）
- [ ] **Windows 主機**：有線網卡連上家用路由器（192.168.1.146）
- [ ] **VM 雙網卡**：
  - enp0s1 橋接 Wi-Fi（Go2 網段 192.168.12.222）
  - enp0s2 橋接有線網卡（家用網段 192.168.1.200）
- [ ] **Windows VPN 清場**：無 Hamachi (25.x.x.x) / Radmin (26.x.x.x) / WSL (172.x.x.x)

---

### A. Mac VM 網卡配置（開機後執行一次即可）

**執行位置：** 任一 Mac VM Terminal

**⚠️ 重要：此步驟只需開機後執行一次，不用每個終端都跑！**

```bash
# 方法 1：使用 alias（推薦，簡潔）
connect_dog

# 方法 2：使用自動化腳本（會額外檢查網路雙通）
cd ~/ros2_ws/src/elder_and_dog
zsh phase1_test.sh env
```

**兩者差異：**
- `connect_dog`：只配置網卡（enp0s1: 192.168.12.222）
- `phase1_test.sh env`：配置網卡 + 檢查 Go2/Windows 連線 + 建立 alias（如果不存在）

**驗證雙通（關鍵連線）：**
```bash
# 測試 Go2 連線（必須通）
ping -c 3 192.168.12.1
# ✅ 預期：延遲 < 50ms

# 測試 Windows 連線（必須通）
ping -c 3 192.168.1.146
# ✅ 預期：延遲 < 5ms（有線網路）

# 如果以上兩個都通，環境就緒！
```

### 🔧 建立 `connect_dog` alias（首次設定，只需執行一次）

如果執行 `connect_dog` 時顯示 "command not found"，請建立 alias：

```bash
cat >> ~/.zshrc << 'EOF'

# ==========================================
# Go2 機器狗網路配置 alias
# ==========================================
alias connect_dog='sudo ip addr flush dev enp0s1 && \
sudo ip addr add 192.168.12.222/24 dev enp0s1 && \
sudo ip link set enp0s1 up && \
sudo ip route add 192.168.12.0/24 dev enp0s1 && \
echo "✅ Go2 網路已配置完成 (enp0s1: 192.168.12.222)"'
EOF

# 重新載入設定
source ~/.zshrc

# 現在可以使用了
connect_dog
```

**注意事項**：
- ⚠️ 如果看到 `RTNETLINK answers: File exists`，表示 IP 已經設定過，可以忽略（正常現象）
- ⚠️ 需要 `sudo` 權限，第一次執行會要求輸入密碼
- ⚠️ **網卡配置**：enp0s1 橋接 Wi-Fi（Go2），enp0s2 橋接有線網卡（Windows）

---

## ⚡ 快速模式：一鍵腳本（推薦新手）

如果你覺得手動貼指令太麻煩，可以使用自動化腳本 `phase1_test.sh`：

### **步驟 1：環境檢查（開機後執行一次即可）**

```bash
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh env
```

**這會自動：**
- 建立 `connect_dog` alias（如果還沒有）
- 配置 Go2 網卡（enp0s1: 192.168.12.222）
- 測試網路雙通（Go2 + Windows）

**⚠️ 此步驟只需開機後執行一次，後續開新終端不用再跑！**

### **步驟 2：開 4 個終端執行（腳本會自動載入 ROS2 環境）**

**⚠️ 重要說明：**
- 每個 `phase1_test.sh t1/t2/t3/t4` 腳本內部都會自動執行 `load_ros_env()` 函數
- 該函數會自動 source ROS2 環境、設定環境變數（CONN_TYPE、ROBOT_IP 等）
- **你不需要在每個終端手動執行 `source` 指令**
- 只要執行對應的 `t1/t2/t3/t4` 指令即可

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
zsh phase1_test.sh t1
```

**檢查點**：
- ✅ 看到 `"Video frame received"` 或相機串流啟動訊息
- ✅ **不要關閉這個終端**，讓它持續運行
- ℹ️ `phase1_test.sh t1` 會自動載入 ROS2 環境並啟動驅動

---

## 📊 Terminal 2：系統監控

**目的**：監控關鍵 topic 頻率，確保頻寬正常。

```bash
# Terminal 2
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh t2
```

**這會自動執行：**
- 載入 ROS2 環境
- 監控 `/scan` 頻率（應顯示 ~7 Hz）
- ⚠️ **等待 Terminal 1 出現 "Video frame received" 後再執行**

**標準值**：
- `/scan`: ~7 Hz（如果 < 5 Hz，Foxglove 需關閉相機影像面板）
- `/map`: ~1 Hz（SLAM 啟動後才有）

---

## 🤖 Terminal 3：啟動 SLAM + Nav2 + Foxglove

**目的**：啟動建圖、導航、視覺化系統。

```bash
# Terminal 3
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh t3
```

**這會自動執行：**
- 載入 ROS2 環境
- 啟動 SLAM Toolbox（建圖）
- 啟動 Nav2（導航）
- 啟動 Foxglove Bridge（視覺化，port 8765）

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
   - 輸入：`ws://192.168.1.200:8765`
   - ⚠️ **確認 IP**：在 VM 執行 `ip addr show enp0s2 | grep "inet "` 查看家用網卡 IP（應為 192.168.1.200）

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
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh t4
```

**互動模式：**
- 輸入 `auto`：自動巡房建圖（推薦）
- 或手動輸入指令：`forward`, `left`, `right`, `back`

**手動控制（替代方案）：**
```bash
# 如果需要精細控制，可使用 TEST.sh
zsh TEST.sh forward   # 前進 3 秒
zsh TEST.sh left      # 左轉 3 秒
zsh TEST.sh right     # 右轉 3 秒
```

**檢查點（Foxglove）**：
- ✅ 地圖上的黑白網格隨著機器狗移動而擴展
- ✅ 白色區域 = 可通行空間，黑色線條 = 障礙物邊界
- ✅ 灰色區域 = 未探索區域
- 💡 建議讓機器狗繞房間一圈，確保地圖覆蓋完整（3x3m 以上）

---

## 💾 儲存地圖

當你覺得地圖建得夠完整了（涵蓋 > 3x3m），執行存檔：

```bash
# 方法 1：使用腳本（推薦）
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh save_map
```

**手動儲存（替代方案）：**
```bash
# 在任一終端執行
mkdir -p ~/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps
ros2 run nav2_map_server map_saver_cli -f ~/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1_5

# 驗證檔案
ls -lh ~/ros2_ws/src/elder_and_dog/src/go2_robot_sdk/maps/phase1_5*
# 應看到：phase1_5.yaml (元數據) + phase1_5.pgm (圖像)
```

---

## 🚀 導航測試（Phase 1.5 核心）

**目的**：驗證 Nav2 + 雙視覺化能否正常導航（**需執行 5 次，成功率 ≥ 80%**）

### 方法 1：使用腳本（推薦）

```bash
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh phase1_test.sh nav_test
```

這會自動執行 5 次導航測試並記錄成功率。

### 方法 2：Windows RViz2 手動測試

1. 在 Windows 啟動 RViz2（參見快速啟動命令）
2. 點擊工具列 **2D Goal Pose** 按鈕
3. 在地圖的白色（可通行）區域點擊並拖曳箭頭設定方向
4. 觀察機器狗是否成功導航至目標

### 方法 3：Foxglove GUI（備案）

1. 在 Foxglove 3D 面板右上角找到 **Publish Navigation Goal** 按鈕
2. 在地圖上點擊目標位置並設定方向

**成功標準（每次測試）：**
- ✅ 終端機顯示 `Goal succeeded!` 或機器狗到達目標位置
- ✅ RViz2/Foxglove 顯示路徑規劃軌跡（綠色/藍色線條）
- ✅ 5 次測試中至少 4 次成功（≥ 80%）

---

## ✅ Phase 1.5 完整檢查清單

完成後，請核對以下項目：

```
□ 1. Go2 驅動啟動成功（Terminal 1: "Video frame received"）
□ 2. /scan 頻率 > 5 Hz（Terminal 2: 穩定 30 秒）
□ 3. SLAM + Nav2 + Foxglove 全部啟動（Terminal 3: 無持續 ERROR）
□ 4. TF 樹完整（執行 ros2 run tf2_tools view_frames 生成 PDF）
□ 5. 雙視覺化正常（Windows RViz2 + Foxglove 同時連線）
   - Windows RViz2 顯示 /scan + /map + /tf
   - Foxglove 連線成功 (ws://192.168.1.200:8765)
□ 6. 建圖與地圖存檔成功（涵蓋 > 3x3m，phase1_5.yaml + .pgm）
□ 7. Nav2 導航測試（5 次中至少 4 次成功，≥ 80%）
```

**通過標準：7 項中至少 6 項通過（≥ 85.7%）**

**若通過，恭喜！可以開始座標轉換開發（W7-W8 核心任務）**

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
   ip addr show enp0s2 | grep "inet "
   # 應該看到 192.168.1.200/24（家用網段）
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

**⚠️ 注意：如果使用 `phase1_test.sh t1/t2/t3/t4`，環境會自動載入，不需手動執行！**

以下指令僅適用於**手動執行 ROS2 指令**時（不透過腳本）：

```bash
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI=/home/roy422/cyclonedds.xml
```

**建議（可選）**：
- 將上述指令加入 `~/.zshrc` 的 ROS2 專案區段，未來每次開終端自動有 ROS2 環境
- 但即使不加入 `.zshrc`，使用 `phase1_test.sh` 腳本也能正常運作

---

**祝測試順利！有任何問題隨時回報。** 🚀

---

## 📝 Phase 1.5 重要新增內容

本文件是 Phase 1 小空間測試的進階版本，主要新增以下內容：

### 🆕 與 Phase 1 的差異

1. **雙視覺化架構**
   - 新增 Windows RViz2（零延遲主控，< 1ms）
   - 保留 Foxglove Studio（監控備案，WebSocket）

2. **網路架構升級**
   - UTM 雙橋接模式（enp0s1 + enp0s2）
   - Windows ↔ VM Native DDS 通訊
   - 驗證三通（Go2 + Internet + Windows）

3. **Nav2 導航測試**
   - 使用 Windows RViz2 的 2D Goal Pose 工具
   - 5 次導航測試（成功率 ≥ 80%）
   - 完整的測試記錄表

4. **TF 樹驗證**
   - 使用 `tf2_tools view_frames` 生成 PDF
   - 驗證完整 TF 鏈路（map → odom → base_link → camera_link/lidar_link）

5. **測試報告模板**
   - 4 張截圖要求
   - 頻率與性能數據表格
   - 7 項驗收檢查清單

### 📸 必備截圖（4 張）

1. **Windows RViz2**：顯示 /scan + /tf + /map
2. **Foxglove Studio**：連線畫面與 3D 視圖
3. **TF 樹結構圖**：frames.pdf
4. **Nav2 成功導航**：RViz2 2D Goal Pose 測試

### ✅ 驗收標準

**通過要求：** 7 項檢查中至少 **6 項通過**（≥ 85.7%）

| # | 檢查項 |
|---|--------|
| 1 | Go2 驅動啟動（無 ERROR，Video frame received） |
| 2 | /scan 頻率 > 5 Hz（穩定 30 秒） |
| 3 | SLAM + Nav2 + Foxglove 全部啟動 |
| 4 | TF 樹完整（map → odom → base_link） |
| 5 | **雙視覺化正常（RViz2 + Foxglove 同時運作）** ← 新增 |
| 6 | 建圖與地圖存檔成功（涵蓋 > 3x3m） |
| 7 | Nav2 導航測試（5 次中至少 4 次成功） ← 新增 |

### 🎯 Phase 1.5 完成後的行動

**若測試通過（≥ 6/7）：**
- ✅ 提交測試報告
- ✅ 更新專案進度至 65%
- ✅ **開始座標轉換開發**（W7-W8 核心任務）

**若測試未通過（< 6/7）：**
- ⚠️ 逐項排查失敗原因
- ⚠️ **座標轉換開發不得開始，直到 Phase 1.5 通過**

---

## 📚 相關文件

### 快速參考
- **完整計畫**：`/home/roy422/.claude/plans/zesty-napping-meadow.md`（包含所有詳細步驟）
- **Phase 1 小空間**：`docs/01-guides/slam_nav/slam+nav2小空間測試.md`
- **測試報告模板**：`docs/03-testing/slam-phase1_test_results_ROY.md`

### 配置檔案
- **VM CycloneDDS**：`~/cyclonedds.xml`
- **Windows CycloneDDS**：`C:\dev\cyclonedds.xml`
- **RViz2 配置**：`go2_robot_sdk/config/single_robot_conf.rviz`

### 網路架構
- **雙橋接說明**：`docs/00-overview/開發計畫.md`（2.1 節）
- **網路拓樸圖**：`docs/00-overview/專題目標.md`

### 開發日誌
- **最新架構突破**：`docs/04-notes/dev_notes/2025-11-30-dev.md`

---

## 🚀 快速啟動命令總結

### Mac VM（4 個 Terminal）

```bash
# Terminal 1: 啟動驅動
zsh phase1_test.sh t1

# Terminal 2: 監控頻率
zsh phase1_test.sh t2

# Terminal 3: 啟動 SLAM + Nav2 + Foxglove
zsh phase1_test.sh t3

# Terminal 4: 控制機器狗
zsh phase1_test.sh t4
# 然後輸入 'auto' 自動巡房
```

### Windows RViz2

```cmd
cd C:\dev\ros2_humble
call local_setup.bat
set CYCLONEDDS_URI=file:///C:/dev/cyclonedds.xml
set RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
set ROS_DOMAIN_ID=0
ros2 run rviz2 rviz2
```

### Foxglove Studio

- 連線至：`ws://192.168.1.200:8765`

---

**文件版本：** v1.0
**最後更新：** 2025/12/01
**維護者：** FJU Go2 專題組 - Roy

**祝 Phase 1.5 測試順利！有任何問題隨時回報。** 🚀
