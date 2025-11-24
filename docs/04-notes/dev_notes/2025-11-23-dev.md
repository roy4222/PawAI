# 開發日誌 - 2025/11/23

**日期：** 2025年11月23日  
**作者：** Roy  
**主題：** Phase 1 自動化腳本開發與測試準備

---

# 📅 開發日誌：Go2 專案 - 實機開發環境最終定案

**日期**：2025/11/23 (Sun)  
**作者**：Roy  
**狀態**：Phase 1 環境建置與連線架構完成，進入實機測試階段。

---

## 🏆 核心突破：雙機協同開發架構 (Dual-Host Setup)

成功建立 **「Mac (運算中樞) ↔ Windows (豪華指揮艙)」** 的協同開發環境。解決了 Mac 效能不足與網路隔離的雙重問題。

### 1. 網路架構定案 (Dual NIC + Tunneling)

**物理架構**：Mac 採用「有線 + 無線」雙刀流，Windows 走有線網路。

**關鍵 IP**：

- Mac **Wi-Fi** (連狗): `192.168.12.117`
- Mac **有線** (連 Windows): `192.168.1.177`
- Windows **有線**: `192.168.1.146`

**通訊打通**：成功利用 SSH 的 **Port Forwarding (Host Port 2222 / 8765)**，將 Windows 的指令和 Foxglove 畫面安全地轉發給 Mac 內部的 Ubuntu 虛擬機。

**連線成果**：

- ✅ Windows VS Code SSH → Mac (成功遠端編輯)。
- ✅ Windows Foxglove → Mac (成功看到 3D 畫面)。

### 2. 核心軟體配置

- **系統**：Ubuntu 22.04 + ROS2 Humble。
- **驅動**：`elder_and_dog` 倉庫編譯成功。
- **視覺化**：安裝並驗證 Foxglove Studio App (Windows)，確認可以接收並渲染 `/scan` (雷達) 與 `/camera/image_raw` (影像)。
- **效率優化**：安裝 ROS2 壓縮影像外掛，解決原始影像頻寬塞車問題。

### 3. 下一步行動 (Action Plan)

1. **實作**：開始實作 **Phase 2 關鍵模組**：座標轉換 (Level 1：地面假設法) 與 FSM 尋物邏輯 (使用 Mock Data)。
2. **協作**：本週 (11/26 週會) 與 VLM 組 (C組) 確認 `Detection2DArray` 介面規範。
3. **目標**：確保 12/03 前，系統能實現 **「發送假座標 → 機器狗自動導航」** 的閉環測試。

---

**總結：** 今天的努力架設了專案最堅實的硬體與網路基礎，為下週的軟體演算法開發鋪平了道路。

---

## 📋 今日目標

1. ✅ 建立 Phase 1 一鍵自動化測試腳本
2. ✅ 更新 Phase 1 執行指南，加入快速模式
3. ⏳ 開始執行 Phase 1 測試（SLAM + Nav2 建圖驗證）

---

## 🎯 完成項目

### 1. 開發 `phase1_test.sh` 自動化腳本

**背景問題：**

- Phase 1 測試需要開 4 個終端
- 每個終端都要手動貼一堆環境載入指令
- 容易忘記載入 ROS2 環境或設定環境變數
- 新手容易在環境配置階段卡關

**解決方案：**  
建立一鍵腳本 `phase1_test.sh`，包含以下功能：

#### 功能模組

|指令|功能|說明|
|---|---|---|
|`zsh phase1_test.sh env`|環境檢查|自動建立 `connect_dog` alias、配置網卡、測試雙通|
|`zsh phase1_test.sh t1`|Terminal 1：啟動驅動|執行 `start_go2_simple.sh`|
|`zsh phase1_test.sh t2`|Terminal 2：監控頻率|自動載入環境並執行 `ros2 topic hz /scan`|
|`zsh phase1_test.sh t3`|Terminal 3：啟動 SLAM+Nav2|自動啟動完整導航堆疊 + Foxglove|
|`zsh phase1_test.sh t4`|Terminal 4：互動控制|互動式控制介面，支援 `auto` 一鍵巡房|
|`zsh phase1_test.sh save_map`|儲存地圖|一鍵存檔到 `maps/phase1.{yaml,pgm}`|
|`zsh phase1_test.sh nav_test`|測試導航|執行 Nav2 自動導航測試|
|`zsh phase1_test.sh check`|系統檢查|檢查所有節點、topic 頻率、地圖檔案|

#### Terminal 4 互動模式

進入 Terminal 4 後，提供互動式命令介面：

```bash
輸入指令 > auto        # 自動巡房建圖（前進→左轉→前進→右轉→前進→左轉）
輸入指令 > forward     # 前進 3 秒
輸入指令 > left        # 左轉 3 秒
輸入指令 > right       # 右轉 3 秒
輸入指令 > sit         # 趴下
輸入指令 > stand       # 站起來
輸入指令 > help        # 顯示所有可用指令
輸入指令 > quit        # 退出控制模式
```

**特色功能：**

- ✅ 彩色終端輸出（綠色=成功、紅色=錯誤、黃色=警告）
- ✅ 自動環境載入（ROS2 + workspace）
- ✅ 智能錯誤檢查（驅動未啟動會提示）
- ✅ `auto` 指令一鍵完成建圖巡房
- ✅ 所有步驟都有清楚的狀態提示

---

### 2. 更新文件

#### 修改檔案：

`docs/01-guides/slam_nav/phase1_execution_guide_v2.md`

- 新增「⚡ 快速模式：一鍵腳本（推薦新手）」章節
- 保留原有的「🚀 標準模式：4 Terminal 分工架構」
- 提供兩種執行方式：快速模式（適合新手）vs 標準模式（適合理解細節）

#### 文件結構：

```markdown
## ⚡ 快速模式：一鍵腳本（推薦新手）
  - 步驟 1：環境檢查（zsh phase1_test.sh env）
  - 步驟 2：開 4 個終端執行（t1/t2/t3/t4）
  - 步驟 3：儲存地圖和測試（save_map / nav_test / check）

## 🚀 標準模式：4 Terminal 分工架構
  - 步驟零：環境就緒
  - Terminal 1：啟動驅動
  - Terminal 2：系統監控
  - Terminal 3：啟動 SLAM + Nav2 + Foxglove
  - Terminal 4：建圖移動
  （保留原有詳細手動指令）
```

---

### 3. 技術細節與除錯

#### 問題 1：`connect_dog` alias 檢測失敗

**症狀：**

```bash
step_env:12: command not found: connect_dog
```

**原因：**

- 使用 `command -v connect_dog` 和 `type connect_dog` 在 zsh 中對 alias 檢測不穩定
- alias 需要在當前 shell session 重新載入才能生效

**解決方案：**

```bash
# 改用 grep 檢查 .zshrc 檔案內容
if ! grep -q "alias connect_dog=" ~/.zshrc; then
    # 寫入 alias
    cat >> ~/.zshrc << 'EOF'
alias connect_dog='...'
EOF
fi

# 重新載入
source ~/.zshrc

# 直接執行指令（不依賴 alias）
sudo ip addr flush dev enp0s2
sudo ip addr add 192.168.12.222/24 dev enp0s2
sudo ip link set enp0s2 up
sudo ip route add 192.168.12.0/24 dev enp0s2
```

#### 問題 2：Terminal 4 執行 TEST.sh 時顯示驅動未運行

**症狀：**

```bash
✗ 錯誤：Go2 驅動節點未運行
```

**原因：**

- `TEST.sh` 內建的 `check_driver()` 函數會檢查 `go2_driver_node` 是否運行
- `phase1_test.sh` 的 Terminal 4 沒有在執行前檢查驅動狀態

**解決方案：**

```bash
# 在 step_t4() 函數開頭加入驅動檢查
if ! ros2 node list 2>/dev/null | grep -q go2_driver_node; then
    echo -e "${RED}❌ 錯誤：Go2 驅動節點未運行${NC}"
    echo -e "${YELLOW}請先在 Terminal 1 執行: zsh phase1_test.sh t1${NC}"
    exit 1
fi
```

#### 問題 3：TEST.sh 需要在專案目錄執行

**解決方案：**  
在每個執行 `TEST.sh` 的地方加上 `cd $PROJECT_DIR`：

```bash
cd $PROJECT_DIR
zsh TEST.sh forward
```

---

## 🔍 系統狀態確認

### 當前環境配置

```bash
# 網路配置
Mac Wi-Fi        → Go2-xxxx (192.168.12.1)
Mac Shared 網卡  → 網際網路
VM enp0s2        → 192.168.12.222 (連接 Go2)
VM enp0s1        → 192.168.64.2 (Shared，連接 Mac)

# ROS2 環境
ROS_DISTRO       → humble
Workspace        → /home/roy422/ros2_ws
Project Root     → /home/roy422/ros2_ws/src/elder_and_dog
Connection Type  → WebRTC
Robot IP         → 192.168.12.1
```

### 節點運行狀態

執行 `ros2 node list` 確認以下節點運行中：

- `/go2_driver_node` ✅（有兩個，可能是重複啟動）
- `/go2_robot_state_publisher` ✅
- `/go2_pointcloud_to_laserscan` ✅
- `/go2_teleop_node` ✅

---

## 📊 測試進度

### Phase 1 檢查清單（未完成）

```
✅ 步驟零：環境就緒檢查（connect_dog + 雙通測試）
🔄 Terminal 1：啟動 Go2 驅動（已啟動，但需重新測試）
⏳ Terminal 2：監控 /scan 頻率（尚未執行）
⏳ Terminal 3：啟動 SLAM + Nav2 + Foxglove（尚未執行）
⏳ Mac 端：連線 Foxglove 並設定面板（尚未執行）
⏳ Terminal 4：控制機器狗建圖（尚未執行）
⏳ 儲存地圖檔案（phase1.yaml + phase1.pgm）（尚未執行）
⏳ 測試 Nav2 自動導航（尚未執行）
```

**目前狀態：** 已完成腳本開發，準備開始實際測試

---

## 🎓 學習心得

### 1. Shell 腳本開發技巧

**Alias 檢測最佳實踐：**

- ❌ 不要用 `command -v` 或 `type` 檢測 alias（不穩定）
- ✅ 用 `grep -q "alias xxx=" ~/.zshrc` 檢查檔案內容
- ✅ 直接執行指令本體，不依賴 alias（更可靠）

**錯誤處理：**

```bash
set -e  # 遇到錯誤立即停止（但要小心副作用）

# 更好的方式：針對關鍵步驟檢查
if ! ros2 node list 2>/dev/null | grep -q go2_driver_node; then
    echo "錯誤訊息"
    exit 1
fi
```

**彩色輸出：**

```bash
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No Color

echo -e "${GREEN}✅ 成功${NC}"
echo -e "${RED}❌ 失敗${NC}"
```

### 2. ROS2 環境管理

**每個新終端必須執行：**

```bash
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
source install/setup.zsh
export CONN_TYPE=webrtc
export ROBOT_IP="192.168.12.1"
```

**建議做法：**

- 寫成函數 `load_ros_env()` 統一管理
- 或加入 `~/.zshrc` 自動載入（但要注意不同專案的衝突）

### 3. 使用者體驗設計

**好的 CLI 工具應該：**

- ✅ 提供清楚的進度提示（用顏色區分狀態）
- ✅ 錯誤訊息要具體（告訴使用者「怎麼修」而非只有「出錯了」）
- ✅ 提供互動模式（而非只能執行一次就結束）
- ✅ 支援一鍵自動化（`auto` 指令）
- ✅ 有完整的 help 說明

**範例：**

```bash
# ❌ 不好的錯誤訊息
echo "Error"

# ✅ 好的錯誤訊息
echo -e "${RED}❌ 錯誤：Go2 驅動節點未運行${NC}"
echo -e "${YELLOW}請先在 Terminal 1 執行: zsh phase1_test.sh t1${NC}"
```

---

## 🔜 下一步行動

### 立即執行（今天/明天）

**1. 完成 Phase 1 測試**

```bash
# 步驟 1：環境檢查
zsh phase1_test.sh env

# 步驟 2：開 4 個終端
Terminal 1: zsh phase1_test.sh t1
Terminal 2: zsh phase1_test.sh t2
Terminal 3: zsh phase1_test.sh t3
Terminal 4: zsh phase1_test.sh t4

# 步驟 3：自動建圖
Terminal 4 輸入: auto

# 步驟 4：儲存地圖
zsh phase1_test.sh save_map

# 步驟 5：測試導航
zsh phase1_test.sh nav_test

# 步驟 6：系統檢查
zsh phase1_test.sh check
```

**2. 記錄測試結果**

- /scan 頻率是否 > 5 Hz
- /map 頻率是否 ~1 Hz
- 地圖檔案是否成功儲存
- Nav2 導航是否成功
- Foxglove 連線是否穩定
- 截圖保存 Foxglove 地圖畫面

**3. 如果 Phase 1 通過**

- 更新開發日誌：`2025-11-23-phase1-test-result.md`
- 準備 Phase 2 測試環境（4-5 坪空間）
- 按照 `phase2_execution_guide.md` 進行測試

---

## 📝 待辦事項

### 本週末（11/23-11/24）

- [ ] **Phase 1 測試完成**
    - [ ] SLAM 建圖成功
    - [ ] 地圖存檔成功（phase1.yaml + phase1.pgm）
    - [ ] Nav2 單點導航成功
    - [ ] 撰寫測試報告

### 下週初（11/25-11/26）

- [ ] **Phase 2 測試**（如果 Phase 1 通過）
    - [ ] 大空間建圖（4-5 坪）
    - [ ] 多點導航測試
    - [ ] 障礙物避障測試
    - [ ] 巡邏穩定性測試

### 11/27-11/30（Week 2）

- [ ] **開始座標轉換開發**（根據三組分工計畫）
    - [ ] 學習 tf2_ros 基礎
    - [ ] 實作地面法（Z=0）座標轉換
    - [ ] 撰寫 Mock VLM Node（假資料測試）

---

## 💡 備註

### 腳本位置

- **主腳本**：`/home/roy422/ros2_ws/src/elder_and_dog/phase1_test.sh`
- **控制腳本**：`/home/roy422/ros2_ws/src/elder_and_dog/TEST.sh`
- **啟動腳本**：`/home/roy422/ros2_ws/src/elder_and_dog/start_go2_simple.sh`

### 重要文件

- **Phase 1 指南（快速版）**：`docs/01-guides/slam_nav/phase1_execution_guide_v2.md`
- **Phase 1 指南（標準版）**：`docs/01-guides/slam_nav/phase1_execution_guide.md`
- **速查表**：`docs/01-guides/slam_nav/quick_reference.md`
- **Phase 2 指南**：`docs/01-guides/slam_nav/phase2_execution_guide.md`

### 已知問題

**1. 驅動節點重複**：`ros2 node list` 顯示兩個 `/go2_driver_node`

- 可能原因：重複啟動或測試時未正確關閉
- 影響：目前看起來不影響功能，但應該只有一個
- 解決方案：測試前先 `pkill -f go2_driver_node` 確保清除舊程序

**2. TEST.sh 的 set -e**：任何指令失敗會導致腳本停止

- 影響：某些可恢復的錯誤會直接中斷
- 目前狀況：可接受，因為關鍵操作不應該失敗

---

## 📸 截圖記錄

（待測試時補充）

- [ ] Foxglove 連線成功畫面
- [ ] SLAM 建圖過程（/map topic 有黑白網格）
- [ ] Nav2 路徑規劃畫面（綠色/藍色軌跡）
- [ ] Terminal 顯示 /scan 頻率 > 5 Hz
- [ ] 儲存的地圖檔案（phase1.pgm 預覽）

---

**總結：** 今天主要完成了 Phase 1 自動化腳本的開發與文件更新，大幅簡化了測試流程。明天（或今天晚上）將開始實際執行 Phase 1 測試，驗證 SLAM + Nav2 的基本功能是否正常運作。這是專題的關鍵里程碑，完成後即可進入座標轉換和 VLM 整合階段。

**狀態：** ✅ 開發完成，⏳ 等待測試