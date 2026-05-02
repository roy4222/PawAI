# 測試腳本與驗證指南

**檔案版本：** v1.0
**建立日期：** 2025/11/18
**適用對象：** 所有開發者

---

## 📋 目錄

1. [概述](#概述)
2. [TEST.sh 快速開始](#testsh-快速開始)
3. [P0 核心功能](#p0-核心功能)
4. [坐下命令驗證](#-坐下命令驗證posture-test-sequence)
5. [P1-P3 預留功能](#p1-p3-預留功能)
6. [常見問題](#常見問題)
7. [進階用法](#進階用法)
8. [ROS2 直接發送動作指令](#ros2-直接發送動作指令)

---

## 🚀 ROS2 直接發送動作指令（快速參考）

> **2025/12/31 更新**：Demo 錄影時可直接用 ROS2 指令觸發動作，無需透過 TEST.sh

### 快速指令格式

```bash
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: <API_ID>, parameter: '', priority: 0}" --once
```

### 常用動作 API ID 速查表

| 動作 | API ID | 指令 | 分類 |
|------|--------|------|------|
| **Hello** | 1016 | `api_id: 1016` | ⭐ Demo 推薦 |
| **Dance1** | 1022 | `api_id: 1022` | ⭐ Demo 推薦 |
| **Dance2** | 1023 | `api_id: 1023` | ⭐ Demo 推薦 |
| **FingerHeart** | 1036 | `api_id: 1036` | ⭐ Demo 推薦 |
| **Stretch** | 1017 | `api_id: 1017` | ⭐ Demo 推薦 |
| **WiggleHips** | 1033 | `api_id: 1033` | ⭐ Demo 推薦 |
| **Wallow** | 1021 | `api_id: 1021` | 打滾 |
| **StandUp** | 1004 | `api_id: 1004` | 基礎 |
| **StandDown** | 1005 | `api_id: 1005` | 基礎 |
| **Sit** | 1009 | `api_id: 1009` | 基礎 |
| **RecoveryStand** | 1006 | `api_id: 1006` | 緊急恢復 |
| **StopMove** | 1003 | `api_id: 1003` | 停止 |
| **BalanceStand** | 1002 | `api_id: 1002` | 平衡站立 |
| **FrontFlip** | 1030 | `api_id: 1030` | ⚠️ 危險 |
| **FrontJump** | 1031 | `api_id: 1031` | ⚠️ 危險 |
| **Handstand** | 1301 | `api_id: 1301` | ⚠️ 危險 |
| **MoonWalk** | 1305 | `api_id: 1305` | ⚠️ 危險 |
| **Bound** | 1304 | `api_id: 1304` | ⚠️ 危險 |

### Demo 錄影常用指令

```bash
# Hello 打招呼
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: 1016, parameter: '', priority: 0}" --once

# Dance1 跳舞
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: 1022, parameter: '', priority: 0}" --once

# FingerHeart 比愛心
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: 1036, parameter: '', priority: 0}" --once

# Stretch 伸懶腰
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: 1017, parameter: '', priority: 0}" --once

# WiggleHips 扭屁股
ros2 topic pub /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{id: 0, topic: 'rt/api/sport/request', api_id: 1033, parameter: '', priority: 0}" --once
```

### MCP Tool 使用方式（Kilo Code）

如果使用 Kilo Code 整合，可直接輸入：

```
go2_perform_action(action='Hello')
go2_perform_action(action='Dance1')
go2_perform_action(action='FingerHeart')
```

> ⚠️ **注意**：MCP Tool 需要 rosbridge 和 ros-mcp-server 正常運行

---

## 概述

### TEST.sh 是什麼？

`TEST.sh` 是一個 Go2 機器人測試框架，用於驗證系統的各項功能。它分為四個階段實現：

- **P0（核心）**：基本動作、感測器監測、系統檢查 ✅ **已完成**
- **P1（導航）**：SLAM、Nav2 控制 ⏳ 預留
- **P2（物體）**：物體偵測、巡邏邏輯 ⏳ 預留
- **P3（界面）**：互動菜單、配置管理 ⏳ 預留

### 檔案位置

```
/home/roy422/ros2_ws/src/elder_and_dog/TEST.sh
```

---

## TEST.sh 快速開始

### 前置條件

1. **啟動機器人驅動**（終端 1）

```zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh start_go2_simple.sh
```

輸出應顯示：
```
✓ 環境已準備
========================================
  啟動中... (按 Ctrl+C 停止)
========================================
[INFO] [go2_driver_node-3]: Robot IPs: ['192.168.12.1']
[INFO] [go2_driver_node-3]: Video frame received for robot 0
```

> ℹ️ 說明：  
> - 若 WebRTC 尚未成功建立（例如 `/con_notify` HTTP timeout、data channel 一直停在 `connecting`），那麼 `TEST.sh` 中的 sit/stand/forward 等動作指令**可能不會生效**。  
> - 在這種情況下，請先依照 [webrtc_troubleshooting.md](./webrtc_troubleshooting.md) 的流程，確認 `aiortc` 版本、Go2 模式與 HTTP `/con_notify` 是否正常（可用 `curl` 測試）。  
> - 在 WSL2 環境下，偶爾會遇到網路 / 虛擬網卡特有問題，若多次嘗試仍不穩定，建議在原生 Ubuntu 機器交叉驗證一次。

2. **準備測試環境**（終端 2）

```zsh
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws
source install/setup.zsh
cd src/elder_and_dog
```

### 基本使用

```zsh
# 顯示幫助
zsh TEST.sh help

# 查看系統狀態
zsh TEST.sh health

# 執行單個命令
zsh TEST.sh sit(坐下)
zsh TEST.sh standdown (趴下)
zsh TEST.sh forward
zsh TEST.sh imu
```

---

## P0 核心功能

### 🎮 基本動作控制

| 命令 | 功能 | 執行時間 |
|------|------|---------|
| `sit` | 機器狗坐下（下半身坐下） | 瞬間 |
| `stand` | 機器狗站起 | 瞬間 |
| `balance` | 平衡站立（重要！） | 瞬間 |

**範例**：
```zsh
zsh TEST.sh sit      # 坐下
zsh TEST.sh stand
zsh TEST.sh standdown   # 站立改姿態；需執行兩次才會完全趴下
zsh TEST.sh balance  # 平衡站立
```

**動作說明**：
- **sit**：機器狗的下半身坐下，上半身保持直立
- **standdown**：站立改姿態的中間動作，**需連續執行兩次** 才會把身體完全放低（趴下）
- **stand**：機器狗完全站起，四肢伸直（正常站立姿態）
- **balance**：機器狗保持平衡站立姿態（運動準備狀態）

### 🎬 娛樂動作

| 命令 | 功能 | 執行時間 |
|------|------|---------|
| `wallow` | 打滾動作 | 1-2 秒 |
| `hello` | 打招呼 | 瞬間 |
| `stretch` | 伸展身體 | 瞬間 |
| `dance1` | 舞蹈 1 | 2-3 秒 |
| `dance2` | 舞蹈 2 | 2-3 秒 |
| `flip` | 前翻 | 1-2 秒 |
| `jump` | 前跳 | 1 秒 |

**範例**：
```zsh
zsh TEST.sh wallow   # 打滾
zsh TEST.sh hello    # 打招呼
zsh TEST.sh dance1   # 舞蹈 1
zsh TEST.sh flip     # 前翻
```

**預期輸出**：
```
→ 執行：打滾（Wallow）
✓ 指令已發送
```

### 🚶 移動控制

| 命令 | 功能 | 速度 | 持續時間 |
|------|------|------|---------|
| `forward` | 向前移動 | 0.3 m/s | 3 秒 |
| `backward` | 向後移動 | -0.3 m/s | 3 秒 |
| `left` | 左轉 | 0.5 rad/s | 3 秒 |
| `right` | 右轉 | -0.5 rad/s | 3 秒 |
| `stop` | 立即停止 | 0 | 瞬間 |

**範例**：
```zsh
zsh TEST.sh forward  # 前進 3 秒
zsh TEST.sh left     # 左轉 3 秒
zsh TEST.sh stop     # 停止
```

**預期輸出**：
```
→ 執行：前進 3 秒（速度 0.3 m/s）
✓ 前進完成
```

**⚠️ 注意**：執行移動命令前確保周圍環境寬敞！

### 📊 感測器監測

| 命令 | 監測項目 | 輸出類型 | 監測時間 |
|------|---------|---------|---------|
| `joint` | 關節位置/速度 | 數值流 | 10 秒 |
| `imu` | 加速度/角速度 | 數值流 | 10 秒 |
| `lidar` | LiDAR 頻率 | 統計資訊 | 5 秒 |
| `odom` | 里程計 | 數值流 | 10 秒 |
| `state` | 機器狀態 | 數值流 | 10 秒 |

**範例**：
```zsh
zsh TEST.sh joint   # 監測關節（10 秒自動停止）
zsh TEST.sh imu     # 監測 IMU（10 秒自動停止）
zsh TEST.sh lidar   # 監測 LiDAR 頻率（5 秒自動停止）
```

**預期輸出**（joint）：
```
→ 監測關節狀態（按 Ctrl+C 停止）

header:
  seq: 12345
  stamp:
    sec: 1763467364
    nsec: 123456789
  frame_id: go2_base
name:
- FL_hip_joint
- FL_thigh_joint
...
position: [0.1, -0.8, 1.2, ...]
velocity: [0.01, -0.02, 0.01, ...]
effort: [1.2, 2.3, 1.8, ...]
```

### ⚙️ 系統診斷

| 命令 | 用途 | 檢查項目 |
|------|------|---------|
| `health` | 完整系統檢查 | 節點、Topics、版本、警告 |
| `list-topics` | 列出所有 topics | 所有可用的 ROS2 topics |
| `list-nodes` | 列出所有節點 | 所有運行的 ROS2 節點 |
| `help` | 顯示幫助 | 命令清單與用法 |

**範例**：
```zsh
zsh TEST.sh health       # 完整系統檢查
zsh TEST.sh list-topics  # 列出 13 個 topics
zsh TEST.sh list-nodes   # 列出 26 個節點
zsh TEST.sh help         # 顯示所有命令
```

**health 命令輸出示例**：
```
========================================
  系統健康檢查
========================================

📊 節點狀態：
  ✓ go2_driver_node: 運行中
  ✓ robot_state_publisher: 運行中
  ✓ pointcloud_aggregator: 運行中

📡 Topic 狀態：
  ✓ /cmd_vel: 可用
  ✓ /joint_states: 可用
  ✓ /imu: 可用
  ✓ /point_cloud2: 可用

⚙️  版本信息：
  NumPy: 1.24.4
  SciPy: 1.8.0

⚠️  已知問題（通常可忽略）：
  - NumPy/SciPy: 已升級為相容版本（numpy 1.24.4）
  - ffmpeg: 若缺失，TTS 會警告（非關鍵）
  - ELEVENLABS_API_KEY: 未設定時 tts_node 失敗（非關鍵）

========================================
✓ 檢查完成
```

---

### 🔍 坐下命令驗證（Posture Test Sequence）

自動化測試序列，用於確定不同坐下/站起命令的實際行為。這對於理解 Go2 SDK 中哪個命令實現「完全坐下」vs「下半身坐下」至關重要。

**命令**：
```zsh
zsh TEST.sh posture-test
```

**測試流程**（自動執行 5 步）：
1. 確認機器人當前狀態（應站立）
2. 執行 `standdown` (api_id: 1005) - 預期：站立改姿態準備坐下
3. 執行 `sit` (api_id: 1009) - 預期：坐下（需觀察是下半身或完全）
4. 執行 `risefit` (api_id: 1010) - 預期：從坐下站起
5. 執行 `stand` (api_id: 1004) - 預期：完全站起

**每步間隔**：3 秒（讓機器人完成動作）

**執行示例**：
```zsh
$ zsh TEST.sh posture-test

========================================
  坐下命令驗證序列
========================================

本測試將系統地驗證所有坐下/站起相關命令的實際行為

✓ 測試計劃：
  1. 確認機器人當前狀態（應站立）
  2. 執行 standdown (api_id: 1005) - 預期：站立改姿態準備坐下
  3. 執行 sit (api_id: 1009) - 預期：坐下（下半身坐下或完全坐下？）
  4. 執行 risefit (api_id: 1010) - 預期：從坐下站起
  5. 執行 stand (api_id: 1004) - 預期：完全站起

開始測試序列...

[步驟 1/5] 檢查當前狀態（等待 2 秒讓機器人穩定）
✓ 請觀察機器人狀態

[步驟 2/5] 執行 standdown (api_id: 1005)
→ 執行：站立改姿態（準備坐下）
✓ 指令已發送
等待 3 秒讓機器人完成動作...
✓ 請觀察機器人是否改變姿態（但仍站立）

[步驟 3/5] 執行 sit (api_id: 1009)
→ 執行：坐下
✓ 指令已發送
等待 3 秒讓機器人完成動作...
✓ 請觀察機器人是否：
    - 只有下半身坐下？
    - 完全坐下（屁股著地）？

... (繼續 risefit 和 stand 步驟)
```

**觀察點**：

| API ID | 命令 | 需要觀察 | 備註 |
|--------|------|---------|-----|
| 1005 | standdown | 是否改變姿態但仍站立？ | 應作為 sit 的準備動作（實測需連續下達兩次才會完全趴下） |
| 1009 | sit | 下半身坐下 vs 完全坐下 | **重點關注** |
| 1010 | risefit | 是否成功從坐下狀態站起 | 應與 sit 配對 |
| 1004 | stand | 是否回到完全站立 | 標準動作 |

**結果記錄**：

測試完成後，腳本會顯示結果記錄模板：
```
API ID | 命令名稱  | 實際行為 | 說明
-------|----------|--------|-----
1005   | standdown | ??     | 需觀察
1009   | sit       | ??     | 需觀察（下半身 vs 完全坐下）
1010   | risefit   | ??     | 需觀察
1004   | stand     | ??     | 需觀察
```

請根據實際觀察結果更新該表格，並將發現回報到 [GitHub Issues](https://github.com/username/project/issues) 或開發文件。

**現有已知信息**：
- `sit` (1009) 被標記為「下半身坐下」
- `standdown` (1005) 的中文名是「站立改姿態」，暗示可能是準備坐下的中間狀態
- `risefit` (1010) 的中文名是「從坐下站起」，應與 sit 配對

---

## P1-P3 預留功能

### P1（導航與 SLAM）- ⏳ 計畫中

預計實現以下功能（框架已預留）：

```zsh
zsh TEST.sh start-slam      # 啟動 SLAM Toolbox
zsh TEST.sh stop-slam       # 停止 SLAM
zsh TEST.sh start-nav2      # 啟動 Nav2 導航
zsh TEST.sh send-goal       # 發送導航目標
zsh TEST.sh save-map        # 保存地圖
zsh TEST.sh load-map        # 載入地圖
```

### P2（物體偵測與巡邏）- ⏳ 計畫中

預計實現以下功能（框架已預留）：

```zsh
zsh TEST.sh start-coco      # 啟動 COCO 物體偵測
zsh TEST.sh stop-coco       # 停止偵測
zsh TEST.sh show-annotated  # 顯示標註影像
zsh TEST.sh start-patrol    # 啟動自動巡邏
zsh TEST.sh stop-patrol     # 停止巡邏
```

### P3（互動菜單與配置）- ⏳ 計畫中

預計實現以下功能（框架已預留）：

```zsh
zsh TEST.sh menu            # 進入互動式菜單
zsh TEST.sh save-preset     # 保存配置
zsh TEST.sh load-preset     # 載入配置
```

---

## 常見問題

### Q1：運行 TEST.sh 時出現「ROS2 環境未載入」

**錯誤訊息**：
```
✗ 錯誤：ROS2 環境未載入
```

**解決方案**：
```zsh
source /opt/ros/humble/setup.zsh
cd /home/roy422/ros2_ws
source install/setup.zsh
cd src/elder_and_dog
```

### Q2：運行 TEST.sh 時出現「Go2 驅動節點未運行」

**錯誤訊息**：
```
✗ 錯誤：Go2 驅動節點未運行
```

**解決方案**：
先在另一個終端啟動驅動：
```zsh
cd /home/roy422/ros2_ws/src/elder_and_dog
zsh start_go2_simple.sh
```

### Q3：機器狗不響應動作命令

**可能原因**：
1. WebRTC 連接未建立
2. 手機 App 仍在連接

**解決方案**：
```zsh
# 檢查健康狀態
zsh TEST.sh health

# 確認機器人 IP 和連接
export ROBOT_IP="192.168.12.1"

# 關閉手機 App，重新啟動驅動
zsh start_go2_simple.sh
```

### Q4：感測器監測沒有輸出數據

**可能原因**：
1. 感測器節點未啟動
2. Topic 名稱不存在

**解決方案**：
```zsh
# 列出所有可用的 topics
zsh TEST.sh list-topics

# 查看特定 topic 是否存在
ros2 topic list | grep imu
```

### Q5：NumPy/SciPy 版本警告

**警告訊息**：
```
NumPy version >=1.17.3 and <1.25.0 is required...
```

**解決方案**：
已在環境設置時修正。驗證：
```zsh
python3.10 -c "import numpy; print(numpy.__version__)"
# 應輸出 1.24.4
```

---

## 📚 SDK 全部可用動作命令

本章節列出 Go2 SDK（`robot_commands.py`）中定義的全部動作命令。這些命令可以通過 `TEST.sh` 或直接通過 ROS2 topic 發送執行。

### 🎮 基本姿態控制（Posture Control）

用於改變機器人的基本姿態，這些是最常用的命令。

| 命令 | api_id | 功能 | 備註 |
|------|--------|------|------|
| `StandUp` | 1004 | 站起 | ✅ 已在 TEST.sh 實現 |
| `Sit` | 1009 | 坐下 | ✅ 已在 TEST.sh 實現 |
| `BalanceStand` | 1002 | 平衡站立 | ✅ 已在 TEST.sh 實現 |
| `StandDown` | 1005 | 從站立狀態改變姿態 | 通常用於準備坐下 |
| `RecoveryStand` | 1006 | 從摔倒恢復到站立 | 緊急恢復命令 |
| `RiseSit` | 1010 | 從坐下站起 | 起身動作 |
| `Damp` | 1001 | 進入被動模式 | ⚠️ 停止電源控制，慎用 |

**使用範例**：
```zsh
zsh TEST.sh stand    # 使用 TEST.sh
# 或直接用 ROS2：
ros2 topic pub --once /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{topic: 'rt/api/sport/request', api_id: 1004}"
```

### 🎬 娛樂與表情動作（Entertainment）

機器人可執行的娛樂性動作。

| 命令 | api_id | 功能 | 執行時間 | 備註 |
|------|--------|------|---------|------|
| `Wallow` | 1021 | 打滾 | 1-2 秒 | ✅ 已在 TEST.sh 實現 |
| `Hello` | 1016 | 打招呼 | 瞬間 | ✅ 已在 TEST.sh 實現 |
| `Stretch` | 1017 | 伸展身體 | 瞬間 | ✅ 已在 TEST.sh 實現 |
| `Dance1` | 1022 | 舞蹈 1 | 2-3 秒 | ✅ 已在 TEST.sh 實現 |
| `Dance2` | 1023 | 舞蹈 2 | 2-3 秒 | ✅ 已在 TEST.sh 實現 |
| `FrontFlip` | 1030 | 前翻 | 1-2 秒 | ✅ 已在 TEST.sh 實現 |
| `FrontJump` | 1031 | 前跳 | 1 秒 | ✅ 已在 TEST.sh 實現 |
| `FrontPounce` | 1032 | 前撲 | 1-2 秒 | 待測試 |
| `FingerHeart` | 1036 | 手指愛心 | 瞬間 | 待測試 |
| `WiggleHips` | 1033 | 扭屁股 | 1-2 秒 | 待測試 |
| `Content` | 1020 | 滿足動作 | 瞬間 | 表情動作 |
| `Scrape` | 1029 | 刮擦 | 瞬間 | 待測試 |

**使用範例**：
```zsh
zsh TEST.sh wallow    # 打滾
zsh TEST.sh hello     # 打招呼
zsh TEST.sh dance1    # 舞蹈 1
zsh TEST.sh flip      # 前翻
zsh TEST.sh jump      # 前跳
```

### 🏅 特技動作（Tricks & Stunts）

高難度動作，通常需要足夠的空間。

| 命令 | api_id | 功能 | 難度 | 備註 |
|------|--------|------|------|------|
| `Handstand` | 1301 | 倒立 | ⭐⭐⭐⭐⭐ | 高風險 |
| `MoonWalk` | 1305 | 月球漫步 | ⭐⭐⭐⭐ | 向後移動 |
| `Bound` | 1304 | 彈跳 | ⭐⭐⭐ | 高跳躍 |
| `OnesidedStep` | 1303 | 單邊步 | ⭐⭐⭐ | 單邊移動 |
| `CrossStep` | 1302 | 交叉步 | ⭐⭐⭐ | 交叉移動 |

⚠️ **注意**：執行特技動作前確保周圍環境寬敞，機器人有足夠空間！

### 🚶 移動控制（Movement）

這些命令涉及步態和移動模式，通常需要配合 `/cmd_vel` topic。

| 命令 | api_id | 功能 | 備註 |
|------|--------|------|------|
| `Move` | 1008 | 移動命令 | 由 `/cmd_vel` 參數化（已在 TEST.sh 實現） |
| `StopMove` | 1003 | 停止移動 | 安全停止 |
| `SwitchGait` | 1011 | 切換步態 | walk / trot / bound 等 |
| `ContinuousGait` | 1019 | 持續步態 | 連續運動模式 |
| `FreeWalk` | 1045 | 自由行走 | 較安全的移動模式 |
| `CrossWalk` | 1051 | 橫向行走 | 側向移動 |
| `EconomicGait` | 1035 | 經濟步態 | 節能模式 |

**使用範例**（已在 TEST.sh 實現）：
```zsh
zsh TEST.sh forward   # 前進 3 秒
zsh TEST.sh backward  # 後退 3 秒
zsh TEST.sh left      # 左轉 3 秒
zsh TEST.sh right     # 右轉 3 秒
zsh TEST.sh stop      # 停止
```

### ⚙️ 身體參數控制（Body Control）

調整機器人的物理參數。

| 命令 | api_id | 功能 | 參數 | 備註 |
|------|--------|------|------|------|
| `BodyHeight` | 1013 | 調整身體高度 | 0.0-1.0（歸一化） | 需要參數 |
| `FootRaiseHeight` | 1014 | 調整抬腿高度 | 0.0-1.0 | 需要參數 |
| `SpeedLevel` | 1015 | 調整速度等級 | 0-10 | 需要參數 |
| `Euler` | 1007 | 歐拉角控制 | roll/pitch/yaw | 需要參數 |

**使用範例**（需要擴展 TEST.sh）：
```zsh
# 直接用 ROS2（示例）
ros2 topic pub --once /webrtc_req go2_interfaces/msg/WebRtcReq \
  "{topic: 'rt/api/sport/request', api_id: 1013, parameter: '0.5'}"
```

### 🔍 狀態查詢（Get State）

查詢機器人當前的狀態和參數。

| 命令 | api_id | 功能 | 返回值 |
|------|--------|------|--------|
| `GetState` | 1034 | 查詢整體狀態 | 完整機器人狀態 |
| `GetBodyHeight` | 1024 | 查詢身體高度 | 當前高度值 |
| `GetFootRaiseHeight` | 1025 | 查詢抬腿高度 | 當前抬腿值 |
| `GetSpeedLevel` | 1026 | 查詢速度等級 | 當前速度等級 |

### 🎯 其他命令（Miscellaneous）

| 命令 | api_id | 功能 | 備註 |
|------|--------|------|------|
| `Trigger` | 1012 | 觸發命令 | 用途待確認 |
| `TrajectoryFollow` | 1018 | 軌跡跟蹤 | 高級導航功能 |
| `SwitchJoystick` | 1027 | 切換搖桿模式 | 多模式支援 |
| `Pose` | 1028 | 姿態模式 | 特定姿態 |
| `StandOut` | 1039 | 站出來 | 特殊站立姿態 |
| `Standup` | 1050 | 站起（重複） | 與 StandUp 重複 |

### 🧪 測試命令的建議順序

若要系統地測試所有命令，建議按以下順序進行：

1. **基本姿態**（安全、易驗證）
   ```zsh
   zsh TEST.sh sit
   zsh TEST.sh stand
   zsh TEST.sh balance
   ```

2. **簡單動作**（低風險）
   ```zsh
   zsh TEST.sh hello
   zsh TEST.sh stretch
   zsh TEST.sh wallow
   ```

3. **複雜動作**（中等風險，需要空間）
   ```zsh
   zsh TEST.sh dance1
   zsh TEST.sh dance2
   zsh TEST.sh flip
   zsh TEST.sh jump
   ```

4. **特技動作**（高風險，需要寬敞空間）
   ```zsh
   # 僅在確保安全的情況下執行
   # zsh TEST.sh 會新增 trick 命令以支援
   ```

---

## 進階用法

### 批次測試

連續測試多個功能：

```zsh
# 測試所有動作
for action in sit stand balance; do
  echo "測試 $action..."
  zsh TEST.sh $action
  sleep 1
done
```

### 監測與日誌

將輸出保存到文件：

```zsh
zsh TEST.sh health > /tmp/health_check.log
cat /tmp/health_check.log
```

### 直接使用 ROS2 命令

若要更細粒度的控制，可直接使用 ROS2 命令：

```zsh
# 發送自定義速度
ros2 topic pub /cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.5}, angular: {z: 0.2}}" -r 10

# 監測 topic 頻率
ros2 topic hz /joint_states

# 查看 topic 數據
ros2 topic echo /imu
```

### 使用 RViz 進行可視化

```zsh
# 啟動 RViz（若驅動已運行）
rviz2

# 在 RViz 中：
# 1. 設定 Fixed Frame 為 "base_link"
# 2. 添加 /joint_states（RobotModel）
# 3. 添加 /point_cloud2（PointCloud2）
# 4. 添加 /tf（TF）
```

---

## 腳本架構說明

### 目錄結構

```
/home/roy422/ros2_ws/src/elder_and_dog/
├── TEST.sh                    # 主測試腳本（370 行）
├── start_go2_simple.sh        # 快速啟動驅動
├── install/                   # ROS2 編譯結果
│   └── setup.zsh             # 環境變數
├── src/
│   └── go2_robot_sdk/
│       ├── launch/
│       │   └── robot.launch.py
│       ├── config/
│       │   ├── joystick.yaml
│       │   └── ...
│       └── ...
└── docs/
    └── README.md              # 本文檔
```

### 核心模組

TEST.sh 包含以下模組：

| 模組 | 功能 | 行數 |
|------|------|------|
| 環境檢查 | ROS2/workspace 驗證 | 30 |
| 基本動作 | sit/stand/balance | 60 |
| 移動控制 | forward/backward/left/right/stop | 100 |
| 感測器 | joint/imu/lidar/odom/state | 80 |
| 系統診斷 | health/list/help | 100 |

---

## 版本歷史

| 版本 | 日期 | 變更內容 |
|------|------|---------|
| v1.0 | 2025/11/18 | 初始版本（P0 功能完成） |

---

## 相關文件

- [README.md](./README.md) - 開發文件總覽
- [environment_setup_ubuntu.md](./environment_setup_ubuntu.md) - 環境設置
- [package_structure.md](./package_structure.md) - 套件結構

---

## 支援與反饋

若遇到問題，請：

1. 檢查本文檔中的[常見問題](#常見問題)章節
2. 執行 `zsh TEST.sh health` 確認系統狀態
3. 查看 ROS2 日誌：`~/.ros/log/`
4. 提交 GitHub Issue（標籤 `test-script` 或 `help-wanted`）

---

**最後更新：** 2025/11/18
**維護者：** FJU Go2 專題組
