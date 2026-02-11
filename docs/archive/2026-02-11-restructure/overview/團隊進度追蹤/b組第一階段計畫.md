**角色定位：** 測試環境提供者 / MCP 測試環境建置 / 運算資源管理（MCP 架構版）
**核心資源：** 學校 GPU 伺服器 (RTX 8000) + 學校 VM (跳板)
**架構變更（12/6）：** 從「必須成功的模擬器」改為「選用的測試環境 + MCP 支援」

**最高指導原則：**

> 「MCP 架構讓實機測試變得更安全，Isaac Sim 從『必要項』降為『選用項』。我們的新角色是提供穩定的 ROS2 測試環境（實機或模擬器皆可），協助 Roy 驗證 MCP 整合。」
>

---

## 🎯 新成功標準（MCP 架構）

| 等級 | 提供環境 | rosbridge 連線 | 判定 |
| --- | --- | --- | --- |
| 🟢 **優秀** | Isaac Sim 可用 + rosbridge 穩定 | ✅ 正常 | 完美測試環境 |
| 🟡 **及格** | **協助 Roy 實機測試** + rosbridge 穩定 | ✅ 正常 | **足夠使用（通過）** |
| 🔴 **失敗** | 無法提供任何測試環境 | ❌ 無法連線 | **Roy 只能單打獨鬥** |

**關鍵變化：**
- ❌ 舊標準：模擬器必須成功，否則砍掉
- ✅ 新標準：提供測試環境即可（實機或模擬器）

---

## 📅 階段性任務詳解（MCP 架構版）

### 🟡 Week 6：MCP 測試環境建置 (12/5 - 12/8)

**目標：** 提供穩定的 ROS2 測試環境，協助 Roy 驗證 MCP 基礎串接

#### 新增責任（MCP 專屬）

1. **在測試環境部署 rosbridge**
    - [ ] 安裝 rosbridge-suite
      ```bash
      sudo apt-get install ros-humble-rosbridge-suite
      ```
    - [ ] 啟動 rosbridge WebSocket (port 9090)
      ```bash
      ros2 launch rosbridge_server rosbridge_websocket_launch.xml
      ```
    - [ ] 驗證 rosbridge 可正常連線

2. **協助 Roy 驗證 MCP 控制**
    - [ ] 若 Isaac Sim 可用：在模擬器環境測試 MCP（降低實機風險）
    - [ ] 若模擬器不可用：協助 Roy 實機測試，待命處理問題
    - [ ] 確認 rosbridge 穩定運行，無斷線問題

3. **環境選擇（二選一即可通過）**
    - **方案 A（理想）**：Isaac Sim + rosbridge
        - [ ] 安裝 Isaac Sim 2023.1.1
        - [ ] 部署 `go2_omniverse` 專案
        - [ ] 載入最簡場景（空房間 + 狗）
        - [ ] 確認 ROS2 Topics 正常：`/scan`, `/camera/image_raw`, `/odom`
    - **方案 B（及格）**：協助 Roy 實機測試
        - [ ] 確保 GPU 伺服器可 SSH 連入
        - [ ] 提供穩定的網路環境
        - [ ] 隨時待命協助故障排查

**📅 12/8 驗收點：**
> 必須回報：「rosbridge 運行穩定，[實機/模擬器] 測試環境可用」

**關鍵變化：**
- ❌ 舊任務：必須連上 GPU 伺服器桌面（VNC/NoMachine）
- ✅ 新任務：提供 rosbridge 測試環境（實機或模擬器皆可）

---

### 🟠 Week 7：協助 Roy 測試（12/9 - 12/15）

**目標：** 確保 rosbridge 穩定運行，支援 Claude Desktop 整合測試

1. **rosbridge 穩定性監控**
    - [ ] 監控 rosbridge WebSocket 連線狀態
    - [ ] 若斷線，協助 Roy 重啟服務
    - [ ] 記錄連線日誌，分析斷線原因

2. **測試環境維護**
    - [ ] 若使用模擬器：確保 Isaac Sim 正常運行
    - [ ] 若使用實機：待命處理硬體問題
    - [ ] 協助 Roy 驗證 MCP Action 控制

**📅 12/15 驗收點：**
> rosbridge 連續運行 1 小時無斷線，Roy 的 MCP 測試順利進行

---

### 🔗 Week 8：LLM API 監控（選用）(12/16 - 12/22)

**目標：** 若 Claude API 速度慢或費用高，部署本地 LLM

#### 選用任務（非必要）

1. **本地 LLM 部署**
    - [ ] 安裝 Ollama（本地 LLM 引擎）
    - [ ] 部署輕量模型（如 Llama 3.1 8B）
    - [ ] 設定 API Gateway 控制費用

2. **Token 使用監控**
    - [ ] 監控 Claude API Token 使用量
    - [ ] 若超過預算，切換至本地 LLM
    - [ ] 記錄效能差異（速度、準確度）

**決策點：**
- ✅ Claude API 可用且費用可接受 → 不執行此階段
- ❌ Claude API 太慢或太貴 → 執行本地 LLM 部署

---

### ❌ 移除的開發任務（MCP 簡化）

**不再需要開發（被 MCP 架構取代）：**
- ❌ **VLM API 部署**（`inference_server.py` FastAPI）→ C 組整合進 Roy 的 Snapshot Service
- ❌ **資源調度腳本**（`start_sim.sh` / `start_vlm.sh`）→ MCP 不需要切換模式

---

## 🏁 Week 9-10：備援與監控 (12/23 - 1/6)

**目標：** 確保 1/7 Demo 成功

1. **錄製備案影片**：
    - 若模擬器可用：錄製一段完美的「自動尋物」影片（剪輯用）
2. **系統監控**：
    - 安裝 `btop` 或 `nvtop`，Demo 當天隨時監看伺服器負載

---

## 📅 B 組每日作戰 SOP

1. **連線**：SSH 進 GPU 伺服器。
2. **檢查**：`nvidia-smi` 確認顯卡狀態。
3. **啟動**：
    - Roy 要測邏輯 $\rightarrow$ `./start_sim.sh` (並確認 VNC 可連)。
    - C 組要測模型 $\rightarrow$ `./start_vlm.sh`。
4. **待命**：在群組回報「伺服器已就緒」。

---

### 💡 給 B 組的一句話總結

> 「你們的任務不是做動畫，而是**『架橋』**。
11/30 前架好通往模擬器的橋 (VNC/Streaming)，12/10 前架好通往 AI 的橋 (API)。
畫面糊一點沒關係，只要能動，Roy 就能把專題做完！」
> 

**開始執行！** 🚀