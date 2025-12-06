---

# Roy 第一階段計畫 (MCP 架構版)

**狀態：🔥 進行中｜目標：MCP + LLM Agent 整合｜覆蓋期程：12/5 - 1/7**
**架構變更：** 從傳統「座標轉換 + FSM」改為「MCP + Claude Desktop」自然語言控制

---

## 🟢 階段一：基礎建設與驗收（11/23 - 11/26）✅ 已完成

- **環境搭建（已完成）**
  - [x] Mac UTM + 雙網卡 (Shared/Bridged) 設定
  - [x] Windows 遠端開發環境 (VS Code SSH + Foxglove)
  - [x] 機器狗驅動與影像串流驗證
- **SLAM 建圖（已完成）**
  - [x] 執行建圖：啟動 `robot.launch.py` 控制狗掃描房間
  - [x] 產出地圖：存檔 `phase1.yaml` 與 `phase1.pgm`
- **Nav2 導航驗收（已完成）**
  - [x] 自動導航測試完成
  - [x] 撰寫報告：整理 Foxglove 截圖與 Log

---

## 🟡 Week 6：MCP 基礎串接（12/5 - 12/8）

**目標：驗證 Claude → MCP → ROS2 基本控制流程**

### 關鍵發現（12/6 研究結果）
- ✅ ros-mcp-server 完全支援 Action（可直接控制 Nav2）
- ✅ 58 個 MCP 工具涵蓋所有 ROS2 需求
- ✅ go2_omniverse 與實機共用相同 ROS2 介面
- ✅ 成功率從 <20% 提升至 80-90%

### 必要套件安裝
- [ ] 安裝 rosbridge-suite
  ```bash
  sudo apt-get install ros-humble-rosbridge-suite
  ```
- [ ] 安裝 ros-mcp-server 依賴
  ```bash
  cd /home/roy422/ros2_ws/src/elder_and_dog/ros-mcp-server
  uv pip install -e .
  ```

### 測試 rosbridge 連線
- [ ] 啟動 rosbridge WebSocket (port 9090)
- [ ] 驗證 MCP Server 可連線
- [ ] 測試 `get_topics()` 列出所有話題
- [ ] 測試 `subscribe_once("/joint_states")` 讀取感測器

### 12/8 Go/No-Go 決策
- ✅ 成功：rosbridge 連線正常，可讀取 Go2 話題 → 繼續 Week 7
- ❌ 失敗：無法連線或工具無法使用 → **回歸原計畫（座標轉換開發）**

---

## 🟠 Week 7：Claude Desktop 整合（12/9 - 12/15）

**目標：實現自然語言控制 Go2 移動**

### Claude Desktop 設定
- [ ] 配置 `~/.config/Claude/claude_desktop_config.json`
  ```json
  {
    "mcpServers": {
      "ros-go2": {
        "command": "bash",
        "args": ["-c", "cd /home/roy422/ros2_ws/src/elder_and_dog/ros-mcp-server && uvx ros-mcp --transport=stdio"],
        "env": {
          "ROSBRIDGE_IP": "localhost",
          "ROSBRIDGE_PORT": "9090"
        }
      }
    }
  }
  ```

### Snapshot Service 開發（替代座標轉換）
- [ ] 建立 `/capture_snapshot` 服務節點
- [ ] 整合 YOLO 標註（若 C 組完成）
- [ ] 與 MCP 的圖像傳輸整合

### 測試案例
- [ ] 連線測試：「請連線到機器人」
- [ ] 感測器讀取：「顯示目前關節狀態」
- [ ] 直接控制：「往前移動 1 公尺」
- [ ] 視覺輸入：「看一下前方有什麼」

---

## 🔴 Week 8：YOLO 整合與導航（12/16 - 12/22）

**目標：整合物件檢測與 Nav2 導航**

### 導航整合
- [ ] Claude 透過 MCP 訂閱 `/detected_objects`
- [ ] 識別目標物品（如「眼鏡」）
- [ ] 使用 `send_action_goal()` 發送 Nav2 目標
- [ ] 監控反饋直到到達

### 測試流程
- [ ] 完成「找眼鏡」端到端流程（簡化版）
- [ ] 驗證 Claude 能理解自然語言並轉換為 ROS2 指令

---

## 🟣 Week 9：Prompt Engineering（12/23 - 12/29）

**目標：調教 Claude 扮演「Go2 機器狗助手」角色**

### System Prompt 設計
- [ ] 定義 Go2 能力與限制
- [ ] 設計互動原則（溫暖、耐心、主動報告）
- [ ] 列出可用 ROS2 指令
- [ ] 設定安全限制（速度、障礙物檢測）

### 測試案例
- [ ] 「Go2，你好」→ 語音回應
- [ ] 「幫我找眼鏡」→ 完整尋物流程
- [ ] 「去廚房」→ 導航至已知位置
- [ ] 「停下來」→ 緊急停止

**成功標準：** 穩定扮演機器狗角色，成功率 > 70%

---

## 🔵 Week 10：穩定性測試與 Demo 準備（12/30 - 1/6）

**目標：確保 1/7 發表成功**

### 測試清單
- [ ] 連續運行 10 分鐘無斷線
- [ ] 尋物成功率 > 80%（測試 10 次）
- [ ] 網路切換測試（Wi-Fi → 有線）
- [ ] 異常處理（命令無效、感測器失效）

### 備案準備
- **Plan A**：現場實機 Demo
- **Plan B**：預錄成功案例影片
- **Plan C**：簡報展示 + 技術架構圖

### Demo 腳本（5 分鐘）
1. 開場（30 秒）：介紹專題背景
2. 技術展示（2 分鐘）：「Go2，幫我找桌上的水瓶」
3. 創新亮點（1 分鐘）：MCP 架構 + 自然互動
4. Q&A（2 分鐘）

---

## ❌ 移除的開發任務（MCP 簡化）

### 不再需要開發（被 MCP 取代）
- ❌ **座標轉換演算法**（Level 1 地面法）→ LLM Vision 直接判斷
- ❌ **FSM 狀態機**（IDLE/PATROL/DETECTED...）→ LLM 自然語言決策
- ❌ **雲端通訊 HTTP API**（Mac ↔ 學校）→ MCP WebSocket

---

## 📅 關鍵日期一覽表

| 日期 | 任務 | 預期產出 |
| --- | --- | --- |
| 11/24 (日) | Phase 1 驗收 | 🗺️ 客廳地圖檔 (.yaml) 與導航截圖 |
| 11/30 (日) | Phase 2-A 數學 | 📐 座標轉換節點（假訊號 → 真座標） |
| 12/05 (四) | Phase 2-B 通訊 | 📡 與學校伺服器互傳資料 |
| 12/10 (二) | Phase 3 邏輯 | 🧠 FSM 節點（狗會自己找東西） |
| 12/14 (六) | Phase 4 演習 | 🎥 Demo 預錄影片 |
| 12/17 (二) | Demo Day | 🏆 現場/影片展示 |

這份計畫已涵蓋學期末前所有任務。
**現在，請回到 Phase 1，把那張地圖跑出來吧！** 🚀
