# Jetson Orin Nano Super 替換 VM 架構研究報告

> **研究日期：** 2026/01/19  
> **狀態：** 研究完成，待實機驗證  
> **研究目標：** 評估是否能用 Go2 Pro 內建導航 API，以及 Jetson 如何整合

---

## 📋 目錄

1. [研究背景](#1-研究背景)
2. [Go2 Pro 內建 API 研究結果](#2-go2-pro-內建-api-研究結果)
3. [go2_ros2_sdk 的 Nav2 整合架構](#3-go2_ros2_sdk-的-nav2-整合架構)
4. [架構決策分析](#4-架構決策分析)
5. [Jetson 整合方案](#5-jetson-整合方案)
6. [下一步行動計畫](#6-下一步行動計畫)
7. [參考資源](#7-參考資源)

---

## 1. 研究背景

### 1.1 原始問題

我們想知道：

1. **Go2 Pro 有內建的「導航到座標」API 嗎？**
   - 如果有，Jetson 只需做 AI（YOLO + 深度估計），把目標座標丟給 Go2 處理
   - 這樣可以大幅簡化 Jetson 的算力需求

2. **Jetson Orin Nano Super 的定位是什麼？**
   - 替換 VM？
   - 補充 VM 的 AI 能力？
   - 還是獨立的邊緣運算單元？

### 1.2 研究來源

| 來源 | 說明 |
|------|------|
| [legion1581/unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect) | 第三方 WebRTC SDK |
| [RoboVerse Wiki](https://wiki.theroboverse.com/en/unitree-go2-app-console-commands) | 社群整理的 API 文檔 |
| [Unitree 官方文檔](https://support.unitree.com) | 官方 SLAM/Navigation 服務 |
| 本地 go2_ros2_sdk codebase | 現有實作分析 |

---

## 2. Go2 Pro 內建 API 研究結果

### 2.1 關鍵發現：Go2 沒有「座標導航」API！

經過深入研究，我們發現一個重要結論：

> **Unitree Go2 Pro 沒有內建「導航到絕對座標」的 API！**

### 2.2 obstacles_avoid API 詳解

`api_id=1003` 的 `mode` 參數含義：

| Mode | 真正含義 | 說明 |
|------|---------|------|
| `mode=0` | 標準避障模式 | 速度控制 + 基本避障 |
| `mode=1` | 進階避障模式 | 增強的障礙物偵測邏輯 |
| `mode=2` | **跟隨模式** | Follow mode，**不是絕對座標！** |

### 2.3 可用的 WebRTC Topics

```python
RTC_TOPIC = {
    # SLAM 相關主題
    "SLAM_QT_COMMAND": "rt/qt_command",
    "SLAM_ADD_NODE": "rt/qt_add_node",
    "SLAM_ADD_EDGE": "rt/qt_add_edge",
    "SLAM_QT_NOTICE": "rt/qt_notice",
    "SLAM_ODOMETRY": "rt/lio_sam_ros2/mapping/odometry",
    
    # LiDAR SLAM (uslam) 相關主題
    "LIDAR_MAPPING_CMD": "rt/uslam/client_command",
    "LIDAR_NAVIGATION_GLOBAL_PATH": "rt/uslam/navigation/global_path",
    "LIDAR_LOCALIZATION_ODOM": "rt/uslam/localization/odom",
    
    # 障礙物避免
    "OBSTACLES_AVOID": "rt/api/obstacles_avoid/request",
    
    # 機器人位姿
    "ROBOTODOM": "rt/utlidar/robot_pose",
}
```

### 2.4 完整 API ID 參考表

#### 移動控制 (1000-1099)

| API ID | 動作 | 說明 |
|--------|------|------|
| 1001 | Damp | 阻尼控制 |
| 1002 | BalanceStand | 平衡站立 |
| 1003 | StopMove | 停止移動（也用於避障） |
| 1004 | StandUp | 站起來 |
| 1005 | StandDown | 準備坐下 |
| 1006 | RecoveryStand | 從跌倒狀態恢復 |
| 1007 | Euler | 歐拉角控制 |
| **1008** | **Move** | **速度控制移動** |
| 1009 | Sit | 坐下 |

#### 互動動作 (1016-1099)

| API ID | 動作 | 說明 |
|--------|------|------|
| 1016 | Hello | 揮手打招呼 |
| 1017 | Stretch | 伸懶腰 |
| 1018 | TrajectoryFollow | 跟隨軌跡 |
| 1021 | Wallow | 打滾 |
| 1022 | Dance1 | 跳舞 1 |
| 1023 | Dance2 | 跳舞 2 |
| 1033 | WiggleHips | 扭屁股 |
| 1036 | FingerHeart | 比愛心 |

---

## 3. go2_ros2_sdk 的 Nav2 整合架構

### 3.1 資料流圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ROS2 環境 (Ubuntu VM)                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐  │
│  │    Nav2     │    │  twist_mux  │    │     go2_driver_node     │  │
│  │  (路徑規劃) │───▶│  (優先權5)  │───▶│  (訂閱 /cmd_vel)        │  │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘  │
│                            ▲                       │                │
│  ┌─────────────┐           │                       ▼                │
│  │  Joystick   │───────────┘           ┌─────────────────────────┐  │
│  │  (優先權10) │                       │  robot_control_service  │  │
│  └─────────────┘                       │  handle_cmd_vel()       │  │
│                                        └───────────┬─────────────┘  │
│                                                    │                │
│                                                    ▼                │
│                                        ┌─────────────────────────┐  │
│                                        │    command_generator    │  │
│                                        │    gen_mov_command()    │  │
│                                        └───────────┬─────────────┘  │
│                                                    │                │
│                                                    ▼                │
│                                        ┌─────────────────────────┐  │
│                                        │     WebRTCAdapter       │  │
│                                        │  send_movement_command()│  │
│                                        └───────────┬─────────────┘  │
│                                                    │                │
└────────────────────────────────────────────────────┼────────────────┘
                                                     │ WebRTC
                                                     ▼
                                        ┌─────────────────────────┐
                                        │        Go2 Pro          │
                                        │   api_id=1008 (速度)    │
                                        │   或 1003 (避障速度)    │
                                        └─────────────────────────┘
```

### 3.2 關鍵程式碼路徑

| 步驟 | 檔案 | 函數/方法 |
|------|------|----------|
| 1. 訂閱 cmd_vel | `go2_driver_node.py:288` | `_setup_subscribers()` |
| 2. 處理 Twist 訊息 | `go2_driver_node.py:359` | `_on_cmd_vel()` |
| 3. 呼叫控制服務 | `robot_control_service.py:22` | `handle_cmd_vel()` |
| 4. 生成 WebRTC 指令 | `command_generator.py:92` | `gen_mov_command()` |
| 5. 發送到 Go2 | `webrtc_adapter.py:122` | `send_movement_command()` |

### 3.3 command_generator.py 詳解

```python
def gen_mov_command(x: float, y: float, z: float, obstacle_avoidance: bool = False) -> str:
    """
    生成移動指令
    
    Args:
        x: 前進/後退速度 (m/s)
        y: 左右橫移速度 (m/s)  
        z: 旋轉速度 (rad/s) 或 yaw (避障模式)
        obstacle_avoidance: 是否啟用避障模式
    """
    if obstacle_avoidance:
        # 避障模式：api_id=1003, topic=rt/api/obstacles_avoid/request
        parameters = {"x": x, "y": y, "yaw": z, "mode": 0}
        command = create_command_structure(
            api_id=1003,
            parameter=parameters,
            topic=OBSTACLE_AVOIDANCE_TOPIC,
        )
    else:
        # 標準運動模式：api_id=1008, topic=rt/api/sport/request
        parameters = {"x": x, "y": y, "z": z}
        command = create_command_structure(
            api_id=1008,
            parameter=parameters,
            topic=SPORT_MODE_TOPIC,
        )
    return json.dumps(command)
```

### 3.4 twist_mux.yaml 配置

```yaml
/twist_mux:
  ros__parameters:
    topics:
      joy:
        topic   : cmd_vel_joy
        timeout : 0.5
        priority: 10        # 搖桿優先權較高
      navigation:
        topic   : cmd_vel
        timeout : 0.5
        priority: 5         # Nav2 優先權較低
```

**意義：** 搖桿可以隨時接管 Nav2 的控制權，作為安全機制。

---

## 4. 架構決策分析

### 4.1 結論：必須使用 Nav2

由於 Go2 沒有內建「座標導航」API，所以：

> **無論 Jetson 還是 VM，都需要跑 Nav2 來做路徑規劃！**

Go2 只負責執行 cmd_vel 速度指令。

### 4.2 L1 LiDAR 硬體限制

根據 CMU autonomy_stack_go2 的發現：

> **Go2 Pro 的 L1 LiDAR 無法偵測高度 < 30cm 的障礙物！**

這是硬體限制，意味著：
- 需要額外感測器（如 RealSense D435i）來補充近距離/低矮障礙物偵測
- 或使用 nvblox 做視覺避障

### 4.3 架構選項比較

| 選項 | 說明 | 優點 | 缺點 |
|------|------|------|------|
| **A. VM + Jetson 分工** | VM 跑 SLAM+Nav2，Jetson 跑 AI | 保留現有架構、風險低 | 多一層網路延遲 |
| **B. Jetson 替換 VM** | Jetson 跑所有 ROS2 節點 | 最簡潔、低延遲 | 需要完整遷移 |
| **C. 混合模式** | Jetson 跑 AI + cuVSLAM，VM 跑 Nav2 | 利用 Jetson GPU 優勢 | 架構複雜 |

---

## 5. Jetson 整合方案

### 5.1 推薦架構：Option B（Jetson 替換 VM）

```
┌─────────────────────────────────────────────────────────────────┐
│                   Jetson Orin Nano Super                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   cuVSLAM    │  │    nvblox    │  │  YOLO-World  │          │
│  │ (Isaac ROS)  │  │  (3D 避障)   │  │  (物件偵測)  │          │
│  │  GPU 加速    │  │  GPU 加速    │  │  GPU 加速    │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
│         │                 │                 │                  │
│         ▼                 ▼                 ▼                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │                    Nav2                           │          │
│  │         (路徑規劃 + 全局/局部 Costmap)            │          │
│  └──────────────────────┬───────────────────────────┘          │
│                         │                                      │
│  ┌──────────────────────▼───────────────────────────┐          │
│  │              go2_driver_node                      │          │
│  │         (WebRTC 連線 + cmd_vel 轉換)              │          │
│  └──────────────────────┬───────────────────────────┘          │
│                         │                                      │
└─────────────────────────┼──────────────────────────────────────┘
                          │ WebRTC (Wi-Fi)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Go2 Pro                                     │
├─────────────────────────────────────────────────────────────────┤
│  接收 api_id=1008 或 1003，執行速度指令                          │
│  內建 LIO-SAM（可選用作輔助定位）                                │
└─────────────────────────────────────────────────────────────────┘
```

### 5.2 感測器配置

| 感測器 | 來源 | 用途 |
|--------|------|------|
| RealSense D435i | Jetson USB | 視覺定位(cuVSLAM) + 深度(nvblox) + RGB(YOLO) |
| L1 LiDAR | Go2 WebRTC | 輔助建圖（遠距離） |
| Go2 Odometry | Go2 WebRTC | 里程計融合 |

### 5.3 算力分配估計

Jetson Orin Nano Super 規格：
- **GPU**: 1024 CUDA cores, 67 TOPS (INT8)
- **CPU**: 6-core Arm Cortex-A78AE
- **RAM**: 8GB LPDDR5

預估算力需求：

| 模組 | GPU 使用率 | CPU 使用率 | 備註 |
|------|-----------|-----------|------|
| cuVSLAM | ~20% | ~10% | Isaac ROS 優化 |
| nvblox | ~15% | ~5% | 3D 重建 |
| YOLO-World | ~30% | ~5% | 可降頻至 5 FPS |
| Nav2 | ~5% | ~30% | 主要吃 CPU |
| ROS2 通訊 | ~5% | ~20% | WebRTC + Topics |
| **總計** | **~75%** | **~70%** | 有餘裕 |

### 5.4 Isaac ROS 套件需求

```bash
# 需要安裝的 Isaac ROS 套件
isaac_ros_visual_slam      # cuVSLAM 視覺定位
isaac_ros_nvblox           # 3D 障礙物地圖
isaac_ros_image_pipeline   # 影像處理加速
```

---

## 6. 下一步行動計畫

### Phase 1：驗證現有架構（1-2 天）

- [ ] 確認 `/cmd_vel` → Go2 的完整資料流
- [ ] 測試 Nav2 發送目標，觀察機器狗反應
- [ ] 驗證 `obstacle_avoidance` 參數的效果

### Phase 2：Jetson 基礎環境（3-5 天）

- [ ] 在 Jetson 安裝 ROS2 Humble
- [ ] 安裝 Isaac ROS 套件（cuVSLAM, nvblox）
- [ ] 設定 RealSense D435i

### Phase 3：SLAM 驗證（2-3 天）

- [ ] 測試 cuVSLAM 定位精度
- [ ] 比較 cuVSLAM vs slam_toolbox
- [ ] 測試 nvblox 3D 建圖

### Phase 4：Nav2 整合（2-3 天）

- [ ] 移植 go2_driver_node 到 Jetson
- [ ] 配置 Nav2 + cuVSLAM
- [ ] 測試端對端導航

### Phase 5：AI 整合（3-5 天）

- [ ] 部署 YOLO-World
- [ ] 整合物件偵測 → Nav2 目標
- [ ] 完整系統測試

---

## 7. 參考資源

### 7.1 官方文檔

- [Unitree Go2 開發者文檔](https://support.unitree.com/home/en/developer)
- [Isaac ROS 文檔](https://nvidia-isaac-ros.github.io/)
- [Nav2 文檔](https://docs.nav2.org/)

### 7.2 社群資源

- [RoboVerse Wiki - Go2 API 參考](https://wiki.theroboverse.com/en/unitree-go2-app-console-commands)
- [legion1581/unitree_webrtc_connect](https://github.com/legion1581/unitree_webrtc_connect)
- [CMU autonomy_stack_go2](https://github.com/jizhang-cmu/autonomy_stack_go2)

### 7.3 本地檔案

- `go2_robot_sdk/go2_robot_sdk/application/utils/command_generator.py` - 指令生成
- `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py` - 主驅動節點
- `go2_robot_sdk/config/nav2_params.yaml` - Nav2 配置
- `go2_robot_sdk/config/twist_mux.yaml` - 速度指令複用配置

---

## 📝 研究日誌

### 2026-01-19

- 完成 legion1581/unitree_webrtc_connect SDK 分析
- 確認 Go2 沒有內建「座標導航」API
- 理解 go2_ros2_sdk 的 Nav2 整合架構
- 確認 `mode=2` 是「跟隨模式」，不是「絕對座標」
- 整理完整的 API ID 參考表
- 規劃 Jetson 替換 VM 的架構方案

---

**研究結論：Go2 Pro 依賴外部 SLAM + Nav2 進行座標導航，Jetson 需要跑完整的導航堆疊。**
