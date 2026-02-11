# CycloneDDS 配置使用指南

**文件目的：** 說明何時使用哪個 CycloneDDS 配置檔案
**最後更新：** 2025/12/02
**重要性：** 🔴 **理解這個差異是使用 Windows RViz2 的關鍵！**

---

## 📋 配置檔案總覽

專案中有 **3 個** CycloneDDS 配置檔案：

| 檔案名稱 | 位置 | 用途 | 何時使用 |
|---------|------|------|----------|
| `local_only_v2.xml` | `/home/roy422/` | 開發模式（VM 內部測試） | VM 內部開發、解決雙網卡問題 |
| `cyclonedds_dual.xml` | `/home/roy422/` | 整合模式（Windows RViz2） | 使用 Windows RViz2 零延遲控制 |
| `cyclonedds.xml` | `go2_robot_sdk/config/` | 舊版配置（已廢棄） | ❌ 不要使用 |

---

## 🎯 使用場景對比

### 場景 1：VM 內部開發測試

**使用時機：**
- 在 VM 內部執行 4 Terminal 測試
- 不需要 Windows RViz2
- Terminal 1 ↔ Terminal 2 ↔ Terminal 3 通訊

**配置檔案：** `local_only_v2.xml`

**啟動方式：**
```bash
# 方法 1：使用預設配置（phase1_test.sh 自動選擇）
zsh phase1_test.sh t1
zsh phase1_test.sh t2
zsh phase1_test.sh t3

# 方法 2：手動設定
export CYCLONEDDS_URI=/home/roy422/local_only_v2.xml
ros2 launch go2_robot_sdk robot.launch.py
```

**特點：**
- ✅ 解決雙網卡 DDS 通訊問題
- ✅ 強制所有通訊走 loopback（127.0.0.1）
- ❌ Windows RViz2 無法連線
- ✅ 可使用 Foxglove WebSocket（Port 8765）

---

### 場景 2：Windows RViz2 零延遲控制

**使用時機：**
- 需要 Windows RViz2 主控介面
- 發送導航目標（2D Goal Pose）
- Phase 1.5 測試
- Demo 展示

**配置檔案：** `cyclonedds_dual.xml`

**啟動方式：**
```bash
# 設定環境變數啟用整合模式
export USE_WINDOWS_RVIZ2=1

# 啟動系統
zsh phase1_test.sh t1
zsh phase1_test.sh t2
zsh phase1_test.sh t3
```

**Windows 端配置（不變）：**
```cmd
cd C:\dev\ros2_humble
call local_setup.bat
set CYCLONEDDS_URI=file:///C:/dev/cyclonedds.xml
set RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ros2 run rviz2 rviz2
```

**特點：**
- ✅ VM 內部通訊正常（優先使用 loopback）
- ✅ Windows RViz2 Native DDS 連線（< 1ms 延遲）
- ✅ 同時支援本機 + 跨機器通訊
- ✅ 可同時使用 Windows RViz2 + Foxglove

---

## 🔧 配置檔案內容對比

### `local_only_v2.xml`（開發模式）

```xml
<Interfaces>
    <NetworkInterface name="lo"/>  <!-- 只允許 loopback -->
</Interfaces>
<Peers>
    <Peer address="127.0.0.1"/>    <!-- 只連接本機 -->
</Peers>
```

**網路拓樸：**
```
Terminal 1 ─┐
Terminal 2 ─┼─ 127.0.0.1 (loopback)
Terminal 3 ─┘

Windows ──❌──X (無法連線)
```

---

### `cyclonedds_dual.xml`（整合模式）

```xml
<Interfaces>
    <NetworkInterface name="lo" priority="10"/>      <!-- 本機優先 -->
    <NetworkInterface name="enp0s2" priority="5"/>   <!-- 允許跨機器 -->
</Interfaces>
<Peers>
    <Peer address="127.0.0.1"/>        <!-- 本機 Terminal 通訊 -->
    <Peer address="192.168.1.146"/>    <!-- Windows RViz2 連線 -->
</Peers>
```

**網路拓樸：**
```
Terminal 1 ─┐
Terminal 2 ─┼─ 127.0.0.1 (loopback, 優先使用)
Terminal 3 ─┘
             │
             └─ enp0s2 (192.168.1.200)
                   │
                   └─ Windows RViz2 (192.168.1.146)
```

---

## ⚙️ 快速切換配置

### 方法 1：使用環境變數（推薦）

```bash
# 開發模式（預設）
zsh phase1_test.sh t1

# 整合模式（Windows RViz2）
export USE_WINDOWS_RVIZ2=1
zsh phase1_test.sh t1
```

### 方法 2：手動設定

```bash
# 開發模式
export CYCLONEDDS_URI=/home/roy422/local_only_v2.xml
ros2 launch go2_robot_sdk robot.launch.py

# 整合模式
export CYCLONEDDS_URI=/home/roy422/cyclonedds_dual.xml
ros2 launch go2_robot_sdk robot.launch.py
```

---

## 🐛 故障排查

### 問題 1：Windows RViz2 看不到 Topics

**症狀：**
```cmd
ros2 topic list
# 只顯示：
# /parameter_events
# /rosout
```

**原因：** VM 使用了 `local_only_v2.xml`（只允許本機通訊）

**解決方案：**
```bash
# 在 VM 切換至整合模式
export USE_WINDOWS_RVIZ2=1

# 重啟所有 Terminal
zsh phase1_test.sh t1
zsh phase1_test.sh t2
zsh phase1_test.sh t3
```

---

### 問題 2：VM 內部 Terminal 收不到 Data

**症狀：**
- `ros2 node list` 看得到節點
- `ros2 topic hz /scan` 無輸出

**原因：** 使用了錯誤的配置或多個 Terminal 使用不同配置

**解決方案：**
```bash
# 確保所有 Terminal 使用相同配置
export CYCLONEDDS_URI=/home/roy422/cyclonedds_dual.xml

# 重置 ROS2 Daemon
ros2 daemon stop

# 重啟所有節點
```

---

### 問題 3：不確定當前使用哪個配置

**檢查方式：**
```bash
echo $CYCLONEDDS_URI
```

**預期輸出：**
- 開發模式：`/home/roy422/local_only_v2.xml`
- 整合模式：`/home/roy422/cyclonedds_dual.xml`

---

## 📊 決策樹

```
需要 Windows RViz2 嗎？
    │
    ├─ 是 → 使用 cyclonedds_dual.xml
    │       export USE_WINDOWS_RVIZ2=1
    │       特點：零延遲控制、Native DDS
    │
    └─ 否 → 使用 local_only_v2.xml
            預設配置
            特點：穩定、解決雙網卡問題
```

---

## 🎯 建議的使用策略

### 日常開發（80% 時間）

**使用：** `local_only_v2.xml`（開發模式）

**理由：**
- 穩定、可靠
- 不受雙網卡問題影響
- 足以應付 VM 內部測試

---

### 整合測試與 Demo（20% 時間）

**使用：** `cyclonedds_dual.xml`（整合模式）

**理由：**
- Windows RViz2 零延遲控制
- 真實反映最終部署架構
- Demo 展示效果好

---

## 🔗 相關文件

- **開發日誌 11/30：** 記錄 Windows RViz2 架構建立過程
- **開發日誌 12/01-12/02：** 記錄雙網卡 DDS 通訊問題解決
- **測試報告：** `docs/03-testing/slam-phase1_5_test_results_ROY.md`

---

## ✅ 總結

**核心概念：**
- **開發模式**：VM 內部測試，穩定優先
- **整合模式**：Windows RViz2 控制，效能優先

**切換方式：**
```bash
# 開發模式（預設）
zsh phase1_test.sh t1

# 整合模式（Windows RViz2）
export USE_WINDOWS_RVIZ2=1
zsh phase1_test.sh t1
```

**重要提醒：**
- 🔴 所有 Terminal 必須使用**相同的配置檔案**
- 🔴 切換配置後需要**重啟所有 ROS2 節點**
- 🔴 Windows 端配置（`C:\dev\cyclonedds.xml`）**不需要修改**

---

**文件版本：** v1.0
**最後更新：** 2025/12/02
**維護者：** Roy
