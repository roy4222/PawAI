# Jetson Orin Nano SUPER 8GB 快系統實作指南

> **撰寫日期：** 2026/01/24  
> **目標硬體：** NVIDIA Jetson Orin Nano SUPER Developer Kit 8GB  
> **用途：** 設計並實作 Jetson 本地快系統（<200ms 導航避障 + 輕量 AI）

---

## 📋 目錄

1. [系統架構概覽](#1-系統架構概覽)
2. [SLAM 方案選擇與優化](#2-slam-方案選擇與優化)
3. [Nav2 配置優化（Jetson 8GB）](#3-nav2-配置優化jetson-8gb)
4. [YOLO11 部署與優化](#4-yolo11-部署與優化)
5. [Safety Layer 實作](#5-safety-layer-實作)
6. [WebRTC 連線穩定性優化](#6-webrtc-連線穩定性優化)
7. [Skills 模組設計](#7-skills-模組設計)
8. [資源監控與排查](#8-資源監控與排查)
9. [常見問題排查清單](#9-常見問題排查清單)
10. [下一步行動計畫](#10-下一步行動計畫)

---

## 1. 系統架構概覽

### 雙層架構圖

```
┌─────────────────────────────────────────────────────┐
│               GPU Server (RTX 6000 Blackwell 48GB)                │
│  ┌────────────────────────────────────────────────┐     │
│  │ 慢系統 (System 2) - 1-5s 延遲        │     │
│  ├─────────────────────────────────────────┐     │
│  │ Qwen2.5-72B (語意理解 + 任務規劃)      │     │
│  │ LLaVA-34B (VLM - 複雜場景理解)       │     │
│  │ Whisper Large V3 (STT - 語音轉文字)       │     │
│  │ SAM 2 (物件追蹤 - 44 FPS)                 │     │
│  └─────────────────────────────────────────┘     │
│  ┌────────────────────────────────────────────────┐     │
│  │ API Server (HTTP)                         │     │
│  │ - 提供統一的 REST API 給本地 Jetson │     │
│  │ - 處理請求路由和快取                  │     │
│  └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
                          │ HTTP API (1-5s)
                          ↓
┌─────────────────────────────────────────────┐
│            Jetson Orin Nano SUPER 8GB                  │
│  ┌────────────────────────────────────────────────┐     │
│  │ 快系統 (System 1) - <200ms 延遲            │     │
│  ├─────────────────────────────────────────┐     │
│  │ slam_toolbox (2D LiDAR SLAM)             │     │
│  │ Nav2 (導航 + 避障)                    │     │
│  │ 輕量 YOLO11 (物件偵測 - GPU 加速)      │     │
│  │ Safety Layer (速度限制 <0.3m/s)            │     │
│  │ go2_driver_node (WebRTC 連線)               │     │
│  │ Local API Client (呼叫 GPU Server)            │     │
│  └─────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────┘
                          │ cmd_vel (即時)
                          ↓
                     ┌─────────────────────────┐
                     │     Go2 Pro        │
                     │  (WebRTC 有線)     │
                     └─────────────────────────┘
```

### 任務分配原則

| 任務類型 | 位置 | 延遲要求 | 理由 |
|-----------|------|----------|--------|
| **實時導航/避障** | **Jetson 本地** | <200ms | 安全性要求，不能有網路延遲 |
| **輕量 AI 推理** | **Jetson 本地** | <100ms | 物件偵測需要即時回饋 |
| **語意理解/任務規劃** | **GPU Server** | 1-5s 可接受 | 複雜任務不佔用本地資源 |
| **場景理解 (VLM)** | **GPU Server** | 1-5s 可接受 | 需要大量 VRAM 計算 |
| **語音轉文字 (STT)** | **GPU Server** | 1-5s 可接受 | Whisper 需要較多 GPU 資源 |
| **語音回饋 (TTS)** | **Jetson 本地 或 GPU Server** | <500ms 可接受 | 考慮延遲和品質 |
| **物件追蹤** | **GPU Server 或 Jetson 本地** | 不嚴格限制 | 可選功能，Jetson 可跑簡單追蹤 |

### Jetson 8GB 資源分配概覽

| 模組 | GPU 使用率 | CPU 使用率 | RAM 使用量 | 說明 |
|-------|-----------|-----------|-----------|------|
| **slam_toolbox** | <5% | ~30% | ~1.5GB | 2D LiDAR SLAM，CPU 友善 |
| **Nav2** | <5% | ~30% | ~0.5GB | 路徑規劃，CPU 密集 |
| **YOLO11 (輕量版)** | ~15-20% | ~10% | ~1GB | 物件偵測 5-10 FPS |
| **Safety Layer** | 0% | ~5% | ~0.2GB | 速度控制邏輯 |
| **ROS2 通訊** | ~5% | ~20% | ~0.8GB | WebRTC + Topics |
| **go2_driver_node** | <5% | ~10% | ~0.5GB | WebRTC 適配器 |
| **HTTP API Client** | ~5% | ~10% | ~0.5GB | 與 GPU Server 通訊 |
| **總計（含預留）** | **~45-50%** | **~95%** | **~4.7GB** | 還有 3.3GB 餘裕 |

> **結論**：Jetson 8GB 足夠運行上述快系統，且還有約 30-35% GPU 和 5% RAM 的預留空間，可處理邊際情況或輕量擴充。

---

## 2. SLAM 方案選擇與優化

### 2.1 SLAM 方案對比表

| 方案 | 技術類型 | Jetson 8GB 可行性 | GPU 使用率 | RAM 使用量 | 優點 | 缺點 |
|-------|-----------|---------------|-----------|-----------|------|
| **slam_toolbox** | 2D LiDAR SLAM | ✅ 完全可用 | <5% | ~1.5GB | CPU 友善，部署簡單 | 3D 地圖資訊少 |
| **RTAB-Map** | RGB-D / 3D LiDAR SLAM | ⚠️ 部署複雜 | ~15-25% | ~2-3GB | 3D 地圖豐富 | 記憶體占用大 |
| **cuVSLAM** | 視覺-慣性 VSLAM | ⚠️ 可行但不推薦 | ~20-30% | ~1.5-2GB | GPU 加速，高精度 | 部署複雜 |

### 2.2 推薦方案：使用 slam_toolbox

**原因：**
1. **Jetson 8GB 限制**：cuVSLAM 佔用 20-30% GPU 和 1.5-2GB RAM，資源緊張
2. **與 Nav2 完美整合**：slam_toolbox 與 Nav2 已驗證相容，無需額外開發
3. **部署簡單**：直接 `apt install ros-humble-slam-toolbox`
4. **CPU 友善**：2D SLAM 不需要大量 GPU，為 YOLO11 保留 GPU 資源
5. **記憶體節省**：slam_toolbox RAM 使用量比 RTAB-Map 少約 50%
6. **已驗證**：專案已使用 slam_toolbox 完成 SLAM + Nav2 導航

### 2.3 slam_toolbox 配置建議

#### 基礎參數

```yaml
# slam_toolbox_online_async.yaml
slam_toolbox:
  ros__parameters:
    # 使用 2D LiDAR
    use_sim_time: False
    map_frame: odom
    odom_frame: odom
    base_frame: base_link
    scan_topic: /scan
    resolution: 0.05    # 5cm resolution
    
    # AMCL 參數（2D SLAM）
    use_sim_time: False
    update_frequency: 1.0
    map_update_interval: 2.0
    minimum_travel_distance: 0.1
    minimum_travel_heading: 0.1
    
    # 性能優化
    max_particles: 1000      # 降低粒子數（預設 2000）
    min_particles: 500       # 提高最小粒子數（預設 500）
```

#### 性能優化說明

| 參數 | 原值 | Jetson 8GB 優化值 | 理由 |
|-------|--------|------------------|------|
| `max_particles` | 2000 | 1000 | 降低粒子數，減少 CPU 負載 |
| `min_particles` | 500 | 500 | 避免粒子枯竭，提升穩定性 |
| `map_update_interval` | 2.0 | 2.0-0 | 提高更新頻率（2Hz），加快地圖響應 |
| `resolution` | 0.05 | 0.05 | 保持 5cm 解析度，平衡精度與效能 |

### 2.4 RTAB-Map 替代方案（進階）

**何時考慮 RTAB-Map：**
- 需要 3D 地圖和深度資訊豐富度
- 願意處理 RealSense D435i RGB-D 資料
- 可以離線建圖（後處理）
- 記憶體需求：2-3GB

**建議使用時機：**
- JetPack 6.0+ 到貨後
- 先用 slam_toolbox 驗證，了解性能瓶頸
- 如需 3D 地圖，再遷移到 RTAB-Map

---

## 3. Nav2 配置優化（Jetson 8GB）

### 3.1 現有 Nav2 配置分析

**文件路徑：** `go2_robot_sdk/config/nav2_params.yaml`

**現有配置的關鍵優化點：**

| 配置類別 | 參數 | 現值 | Jetson 8GB 優化值 | 說明 |
|-----------|--------|-------|------------------|------|
| **AMCL 優化** | `max_particles` | 2000 | 1000 | 降低粒子數，減少 CPU 負載 |
| **AMCL 優化** | `min_particles` | 500 | 500 | 避免粒子枯竭 |
| **更新頻率** | `save_pose_rate` | 0.5 | 1.0 | 提高至 1Hz，加快地圖更新 |
| **Controller Server** | `controller_frequency` | 20.0 | 10.0 | 提高控制頻率（10Hz），降低延遲 |
| **速度閾值** | `min_vel_x/y` | 0.001 | 0.1 | 降低最小速度閾值，Go2 能更順暢起步 |
| | `max_vel_x/y` | 0.5 | 0.3 | 降低最大速度，避免過衝 |
| **DWB 優化** | `max_vel_theta` | 1.0 | 0.5 | 降低角速度，避免瘋狂旋轉 |
| **採樣優化** | `vx/vy_samples` | 20 | 5 | 降低採樣數，減少計算負荷 |
| **Footprint** | `footprint` | [0.3, 0.15] | [0.3, 0.15], [0.3, -0.15]... | 縮小 footprint，減少 costmap 計算 |
| **Voxel Layer** | `inflation_radius` | 0.25 | 0.15 | 縮小膨脹半徑，減少膨脹計算量 |
| **Voxel Layer** | `cost_scaling_factor` | 3.0 | 3.0 | 提高 cost scaling，加快路徑規劃 |
| **Smoothing** | `w_smooth` | 0.2 | 0.3 | 啟用平滑器，使軌跡更流暢 |

### 3.2 Nav2 配置優化（Jetson 8GB）

#### 修改后的完整配置

```yaml
# nav2_params.yaml (Jetson 8GB 優化版)
amcl:
  ros__parameters:
    use_sim_time: False
    base_frame_id: "base_link"
    odom_frame_id: "odom"
    global_frame_id: "odom"
    
    # Jetson 8GB 優化
    max_particles: 1000      # 降低粒子數
    min_particles: 500       # 提高最小值
    save_pose_rate: 1.0    # 提高至 1Hz
    
    # 速度控制（Go2 限制）
    min_vel_x: 0.1          # 降低最小速度閾值
    min_vel_y: 0.1
    max_vel_x: 0.3          # 降低最大速度（Go2 起步需 <0.3m/s）
    max_vel_y: 0.3
    max_vel_theta: 0.5      # 降低角速度
    
    # 降低採樣負荷
    vx_samples: 5           # 降低採樣數（預設 20）
    vy_samples: 5
    vtheta_samples: 5

bt_navigator:
  ros__parameters:
    controller_frequency: 10.0    # 提高至 10Hz
    
    # 消除警告
    current_goal_checker: "general_goal_checker"
    goal_checker_plugins: ["general_goal_checker"]
    general_goal_checker:
      plugin: "nav2_controller::SimpleGoalChecker"
      stateful: True
      xy_goal_tolerance: 0.3   # 放寬容差
      yaw_goal_tolerance: 0.3

local_costmap:
  ros__parameters:
    update_frequency: 1.0
    publish_frequency: 1.0
    
    # Jetson 8GB 優化
    resolution: 0.05    # 保持 5cm 解析度
    height: 6              # 地圖高度保持 6m
    width: 6               # 地圖寬度保持 6m（足夠室內使用）
    
    # 縮小膨脹半徑
    inflation_radius: 0.15      # 縮小膨脹半徑
    cost_scaling_factor: 3.0      # 提高 cost scaling
    
    # 足球層配置
    plugins: ["static_layer", "voxel_layer"]
    
    # Voxel layer 優化
    voxel_layer:
      enabled: True
      publish_voxel_map: True
      observation_sources: scan
      scan:
        topic: scan
        min_obstacle_height: 0.1     # 新增：避免掃到地板
        max_obstacle_height: 2.0
        clearing: True
        marking: True
        data_type: "LaserScan"

planner_server:
  ros__parameters:
    use_sim_time: False   # 修改：實機環境使用 False
    
    # Jetson 8GB 優化
    planner_plugins: ["GridBased"]
    GridBased:
      plugin: "nav2_smac_planner/SmacPlannerHybrid"
      tolerance: 3.0                    # 放寬容差
      downsample_costmap: false           # 保持未下採樣
      allow_unknown: false              # 不進入未知區域
      max_iterations: -1                # 禁用最大迭代，使用默認（更快）
      max_planning_time: 3.5           # 降低最大規劃時間
      
      # 降低路徑計算複雜度
      motion_model_for_search: "REEDS_SHEPP"
      cost_travel_multiplier: 2.0       # 提高 cost multiplier（加快規劃）
      angle_quantization_bins: 64
      analytic_expansion_ratio: 3.5
      analytic_expansion_max_length: 3.0
      minimum_turning_radius: 0.30      # 最小轉彎半徑
      lookup_table_size: 20.0
      
      # 平滑器優化
      smoother:
        w_smooth: 0.3
        w_data: 0.2
        tolerance: 0.1
```

### 3.3 配置修改說明

| 優化類別 | 效果 | 資源節省 |
|-----------|------|-----------|
| **AMCL** | 規蓋率 +20-3%，CPU 負載-10% | 避免 AMCL 收斂 |
| **Controller** | 控制頻率 +50%（降低延遲 | CPU 負載-5% | 提升控制響應速度 |
| **速度閾值** | 提高最小速度，降低最大速度 | 平滑起動和停止 | 避免 Go2 起步震動 |
| **採樣** | 降低至 5 | CPU 負載-20% | 減少計算負荷 |
| **Footprint** | 縮小 footprint | costmap 計算量-30% | 加快路徑規劃 |
| **Voxel** | 縮小膨脹半徑 | 膨脹計算量-60% | 加快 costmap 更新 |
| **Planner** | 禁用最大迭代，降低規劃時間 | 路徑計算負荷-40% | 加快規劃響應 |

> **預期效果：** 整體延遲降低 30-50%，CPU 負載降低 15-25%，仍保持 Nav2 功能完整性。

---

## 4. YOLO11 部署與優化

### 4.1 推薦方案：Ultralytics YOLO11（Jetson 優化版）

**選擇理由：**
1. **Jetson 專門優化**：NVIDIA 提供完整的 Jetson 優化工具和指南
2. **官方支援**：有完整的 Jetson 部署文檔和性能數據
3. **輕量化**：INT8 權重模型，專為嵌入式設備優化
4. **C++ 實作**：純 C++ 引擎，推理速度快

**參考資源：**
- [Ultralytics YOLO11 Jetson Guide](https://docs.ultralytics.com/guides/nvidia-jetson/)
- [YOLOv8 on Jetson - Memory Issues 解決方案](https://nvidia-jetson.piveral.com/jetson-orin-nano/deploying-yolov8-on-jetson-orin-nano-int64-weights-and-memory-issues/)

### 4.2 YOLO11 安裝流程

```bash
# 在 Jetson 上執行
cd ~/ros2_ws/src

# 複製 Ultralytics YOLO11 倉庫
git clone https://github.com/ultralytics/ultralytics.git
cd ultralytics
pip install ultralytics -e yolov11

# 下載 Jetson 優化權重
# 在 GPU Server 下載後，透過 SFTP 傳輸到 Jetson
# 權重路徑：/home/roy422/yolo_weights/yolov11n_jetson.pt

# 驗證安裝
python3 -c "from ultralytics import YOLO11; model = YOLO11('yolov11n_jetson.pt'); print('Model loaded successfully')"
```

### 4.3 YOLO11 性能優化

| 優化項 | 配置 | 效果 | 資源節省 |
|-------|--------|-------|-----------|
| **輸入解析度** | `imgsz=640` | 降低圖片解析度，減少 CPU/GPU 負載 | CPU -10%，GPU -5% |
| **推論頻率** | `max_det=50` | 限制最大偵測數，減少峰值負荷 | CPU -5% |
| **批次大小** | `batch=1` | 使用批次推論，GPU 利用率更穩定 | GPU +5% 效率 |
| **TensorRT 優化** | 預設啟用 TensorRT | 推理速度提升 30-50% | GPU -10% |
| **INT8 量化** | 使用 INT8 權重模型 | 推理速度提升 20-30% | GPU -5%，RAM -10% |
| **多執行緒** | `workers=2` | Jetson 6 核心 CPU 可並行處理 | CPU 利用率 +20% |

### 4.4 Jetson 8GB 預期性能

| 指標 | Jetson 8GB 預期值 | 說明 |
|-------|-------------------|-------|------|
| **推理速度** | 8-12 FPS (640x640) | 適到物體偵測需要的即時速度 |
| **GPU 使用率** | ~15-20% | YOLO11 + Nav2 同時運行時的 GPU 佔用 |
| **RAM 使用量** | ~1GB | 包含模型、圖片緩衝 |
| **CPU 使用率** | ~10-15% | 主要用於資料預處理和 ROS2 通訊 |
| **延遲** | 80-120ms (偵測) | 滿足 <100ms 要求 |

> **結論**：使用 INT8 權重的 YOLO11 模型，在 Jetson 8GB 上可達到 8-12 FPS 推理速度，GPU 使用率約 15-20%，與 Nav2 同時運行不會造成資源爭奪。

---

## 5. Safety Layer 實作

### 5.1 Safety Layer 功能設計

```python
# safety_layer.py
import rclpy
from geometry_msgs.msg import Twist
from std_srvs.srv import Trigger, TriggerResponse

class SafetyLayer:
    def __init__(self):
        self.min_linear_x = 0.1      # Go2 最小起步速度
        self.max_linear_x = 0.3      # Go2 最大建議速度
        self.max_linear_y = 0.3
        self.max_angular_z = 0.5      # 限制角速度，避免瘋狂旋轉
        self.max_accel_x = 0.5        # 最大加速度
        self.max_accel_y = 0.5
        
        # 訂閾值
        self.vel_timeout = 1.0        # 速度超過 1s 未更新視為超時
        
    def clamp_velocity(self, cmd_vel: Twist) -> Twist:
        """限制速度在安全範圍內"""
        # 限制線性速度
        cmd_vel.linear.x = max(self.min_linear_x, min(cmd_vel.linear.x, self.max_linear_x))
        cmd_vel.linear.y = max(self.min_linear_y, min(cmd_vel.linear.y, self.max_linear_y))
        
        # 限制角速度
        cmd_vel.angular.z = max(-self.max_angular_z, min(cmd_vel.angular.z, self.max_angular_z))
        
        # 限制加速度（Go2 物理限制）
        # 簡單實作：假設加速度已在上游處理
        return cmd_vel
    
    def validate_command(self, msg: str) -> bool:
        """驗證指令是否為合法動作指令"""
        valid_actions = [
            'stop', 'forward', 'backward', 
            'left', 'right', 'turn_left', 'turn_right'
        ]
        return msg.lower() in valid_actions

class SafetyLayerNode:
    def __init__(self):
        self.safety_layer = SafetyLayer()
        self.cmd_vel_sub = self.create_subscription(
            Twist,
            'cmd_vel_unsafe',
            10 0  # Queue size 10
        )
        self.cmd_vel_safe_pub = self.create_publisher(
            Twist,
            'cmd_vel',
            10
        )
        
    def cmd_vel_unsafe_callback(self, msg: Twist):
        """接收未安全速度指令，限制後發布"""
        safe_msg = self.safety_layer.clamp_velocity(msg)
        self.cmd_vel_safe_pub.publish(safe_msg)
        
    def main(self, args=None):
        rclpy.init(args=args)
        node = SafetyLayerNode()
        rclpy.spin(node)
```

### 5.2 Safety Layer 整合到 Nav2

**方法一：在 Nav2 前插入 Safety Layer 節點**

```yaml
# 修改 twist_mux.yaml，將 Safety Layer 的優先級設為最高
twist_mux:
  ros__parameters:
    topics:
      cmd_vel_safe:        # Safety Layer 輸出
        topic: cmd_vel
        timeout: 0.5
        priority: 10        # 最高優先級
        locks: [stop]      # Safety Layer 可隨時停止機器人
        
      nav2:
        topic: cmd_vel_nav2    # Nav2 輸出
        timeout: 0.5
        priority: 5         # 較低優先級，被 Safety Layer 覆蓋
```

**方法二：使用 Nav2 的 Speed Controller**

```yaml
# nav2_params.yaml (Speed Controller 部分)
controller_server:
  ros__parameters:
    min_vel_x: 0.1          # Go2 最小起步速度
    min_vel_y: 0.1
    max_vel_x: 0.3          # Go2 最大速度
    max_vel_y: 0.3
    max_vel_theta: 0.5
    
    # 消除警告
    current_goal_checker: "general_goal_checker"
    goal_checker_plugins: ["general_goal_checker"]
    general_goal_checker:
      plugin: "nav2_controller::SimpleGoalChecker"
      stateful: True
      xy_goal_tolerance: 0.3   # 放寬容差
      yaw_goal_tolerance: 0.3
```

### 5.3 Safety Layer 性能預期

| 指標 | 預期值 |
|-------|-------------------|
| **速度限制** | 線性速度：0.1-0.3 m/s，角速度：0.5 rad/s | 避免 Go2 震動和失控 |
| **處理延遲** | <10ms | Safety Layer 的處理延遲 | 滿足 <100ms 總延遲要求 |
| **CPU 使用率** | ~5% | 簡單的速度限制邏輯 | CPU 負載低 |
| **RAM 使用量** | ~0.2GB | 節點對列和狀態 | RAM 佔用少 |

> **結論**：Safety Layer 可確保 Go2 的運動安全，同時不會增加太多系統負載。

---

## 6. WebRTC 連線穩定性優化

### 6.1 WebRTC 問題排查（基於 2026-01-17-dev.md）

**問題 1：`/scan` 全 `inf`（已解決）**
- **原因：** intensity 過濾導致點雲為空
- **解決方法：** intensity 過濾 fallback 機制
- **驗證：** `ros2 topic echo /scan --once` 輸出實際距離值

**問題 2：`/point_cloud2` 頻率低（已解決）**
- **原因：** LZ4 解碼器未啟用，使用 WASM 解碼
- **解決方法：** 使用 LZ4 主路徑優先
- **驗證：** `ros2 topic hz /point_cloud2` 輸出 14-15 Hz

**問題 3：WebRTC 連線不穩定**
- **原因：** 網路抖動或頻寬不足
- **解決方法：** 使用有線連線（CycloneDDS）或固定 IP
- **驗證：** `ping -c 10 192.168.123.161` 延遲穩定 <5ms

### 6.2 WebRTC 連線優化配置

```python
# go2_driver_node.py 優化建議
# 在 WebRTCAdapter 中啟用以下配置

class WebRTCAdapter:
    def __init__(self, robot_ip: str):
        self.robot_ip = robot_ip
        
        # WebRTC 連線優化
        self.keepalive_interval = 30.0     # 30 秒發送一次 keepalive
        self.enable_traffic_saving = True     # 啟用流量節省
        self.use_lz4_decoder = True         # 使用 LZ4 解碼器（加速）
        self.disable_auto_focus = True          # 禁用自動對焦（節省 CPU）
        
        # 影像優化
        self.camera_fps = 10                # 降低預設 30fps
        self.jpeg_quality = 80              # 降低預設 85
        self.publish_compressed_only = True   # 只發布壓縮影像
        
        # LiDAR 優化
        self.lidar_fps = 7                  # LiDAR 固定 7Hz（不降低）
```

### 6.3 啟動配置檢查清單

| 檢查項 | 指標 | 正確值 | 驗證方法 |
|-------|--------|-------|-----------|
| **Keepalive** | 每 30 秒 | 確認連線狀態 | 日誌檢查 `last_keepalive_time` |
| **流量節省** | True | 減少 WebRTC 頻寬使用 | 觀察網路流量 |
| **LZ4 解碼器** | True | 確認 LZ4 正在使用 | 日誌檢查 `decoder_type` |
| **相機 FPS** | 10 Hz | `ros2 topic hz /camera/image_raw/compressed` | 確認頻率符合預期 |
| **LiDAR FPS** | 7 Hz | `ros2 topic hz /point_cloud2` | 確認頻率穩定 |
| **連線延遲** | <5ms | `ping -c 10 192.168.123.161` | 確認低延遲 |

> **結論**：WebRTC 連線可透過調整 keepalive 間隔、使用 LZ4 解碼器、降低影像參數、固定 LiDAR 頻率來優化穩定性。

---

## 7. Skills 模組設計

### 7.1 本地 Skills API 架構

```python
# skills_server.py - Jetson 本地 API Server
from enum import Enum
import rclpy
from typing import Dict, Any
import time

class Skill(Enum):
    # 基礎技能（Jetson 本地處理）
    FIND_OBJECT = "find_object"
    NAVIGATE_TO = "navigate_to"
    PERFORM_ACTION = "perform_action"
    SAY = "say"
    LOOK_AROUND = "look_around"
    
    # 雲端處理技能（GPU Server）
    # LLM_UNDERSTAND = "llm_understand"
    VLM_ANALYZE = "vlm_analyze"
    STT = "stt"
    TTS = "tts"

class SkillsServer:
    def __init__(self):
        # 建立本地服務（供 HTTP API 呼叫）
        self.find_object_srv = self.create_service(
            FindObject,
            'find_object'
        )
        self.navigate_to_srv = self.create_service(
            NavigateTo,
            'navigate_to'
        )
        self.perform_action_srv = self.create_service(
            PerformAction,
            'perform_action'
        )
        self.say_srv = self.create_service(
            Say,
            'say'
        )
        self.look_around_srv = self.create_service(
            LookAround,
            'look_around'
        )
        
        # 建立 HTTP Client（呼叫 GPU Server）
        self.gpu_server_url = "http://192.168.1.100:8000"  # GPU Server IP
        
        # 任務路由規劃
        self.task_router: {
            Skill.LLM_UNDERSTAND: "local",    # 本地處理
            Skill.VLM_ANALYZE: "local",     # 本地處理
            Skill.STT: "remote",            # 遠端處理
            Skill.TTS: "local",             # 本地處理（可選）
        }
        
    def route_task(self, skill: Skill, params: Dict[str, Any]) -> Dict[str, Any]:
        """根據技能類型路由任務"""
        target = self.task_router.get(skill, "local")
        
        if target == "local":
            # 本地處理：直接調用相應服務
            if skill == Skill.FIND_OBJECT:
                return self._find_object_local(params)
            elif skill == Skill.NAVIGATE_TO:
                return self._navigate_to_local(params)
            elif skill == Skill.PERFORM_ACTION:
                return self._perform_action_local(params)
            elif skill == Skill.SAY:
                return self._say_local(params)
            elif skill == Skill.LOOK_AROUND:
                return self._look_around_local(params)
        else:
            # 遠端處理：呼叫 GPU Server API
            if skill == Skill.STT:
                return self._stt_remote(params)
            elif skill == Skill.TTS:
                return self._tts_remote(params)
        
        return {"status": "success", "result": result}
    
    def _find_object_local(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """本地物件搜尋"""
        # 調用 YOLO11 偵測
        # 詳細實作見第 4 節
        
        result = {
            "label": target_object,
            "distance": distance,
            "direction": direction,
            "confidence": confidence
        }
        return result
    
    def _navigate_to_local(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """本地導航"""
        # 調用 Nav2 Action Client
        target_pose = params.get('x'), params.get('y')
        
        # 發布 Nav2 目標
        self.nav_to_pose_client.send_goal(target_pose)
        
        return {"status": "navigating"}
```

### 7.2 Skills 任務路由策略

| 任務類型 | 本地 vs 遠端 | 判斷標準 | 優先級 |
|-----------|--------------|-----------|---------|
| **導航/避障** | **本地** | 需 <200ms 延遲，不能有網路延遲 | 最高 |
| **物件偵測** | **本地** | 需 <100ms 即時回饋 | 高 |
| **動作執行** | **本地** | 需即時回饋 | 高 |
| **語意理解** | **遠端** | 1-5s 可接受，需大量計算 | 中 |
| **場景理解 (VLM)** | **遠端** | 1-5s 可接受，需大量 VRAM | 低 |
| **語音轉文字 (STT)** | **遠端** | 1-5s 可接受，需中量計算 | 中 |
| **語音回饋 (TTS)** | **本地優先** | 需 <500ms，品質要求高 | 最高 |
| **物件追蹤** | **遠端優先** | 需大量計算 | 低 |

> **結論**：本地優先導航避障、物件偵測、動作執行；語意理解和語音相關任務交給 GPU Server，語音回饋優先考慮本地處理。

---

## 8. 資源監控與排查

### 8.1 監控工具安裝

```bash
# Jetson 8GB 系統監控工具
cd ~/ros2_ws

# 安裝監控工具
sudo apt install htop iotop sysstat

# 或使用 ROS2 內建監控
sudo apt install ros-humble-rqt-tf-tree
sudo apt install ros-humble-rqt-top
```

### 8.2 資源監控指標

| 資源 | 目標值 | 警告閾值 | 優化建議 |
|-------|--------|----------|-----------|----------|
| **CPU 使用率** | <70% | 持續使用 < 80% | 降低 AMCL 粒子數 |
| **GPU 使用率** | <50% | 持續使用 < 60% | 降低採樣和批次大小 |
| **RAM 使用量** | <4.5GB | 持續使用 < 5GB | 降低地圖解析度或批次大小 |
| **溫度** | <65°C | 持續 < 70°C | 避免降頻 |
| **功耗** | <15W | 持續 < 19W | JetPack 降頻模式 |

### 8.3 常見問題排查清單

| 問題類型 | 症狀 | 可能原因 | 排查步驟 |
|-----------|--------|----------|----------|----------|
| **系統崩潰** | OOM | YOLO 模型太大，批次大小過大 | 1. 降低批次大小 2. 調整輸入解析度 |
| | | | 高 CPU 負載 | 2. `htop` 檢查 CPU 使用率 3. `free -h` 檢查 RAM |
| **延遲過高** | >500ms | Nav2 規劃時間過長 | 1. 降低規劃時間 2. 降低 AMCL 粒子數 |
| **導航失敗** | 無法到達目標 | Footprint 過小 | 1. 擴大 footprint 2. 調整膨脹半徑 |
| | | | WebRTC 斷線 | 2. 檢查連線狀態，重啟 WebRTC |
| **YOLO 無法偵測** | 推理 FPS < 1 | TensorRT 未啟用 | 1. 啟用 TensorRT 引擎 2. 檢查 GPU 可用性 |
| **RAM 耗盡** | 持續增長 | 記憶體洩漏 | 1. 檢查是否有程式碼記憶體洩漏 |

---

## 9. 下一步行動計畫

### 9.1 立即可行（不依賴 Jetson 硬體）

- [x] **完成 SLAM 方案文獻調研筆記**
  - [x] 撰寫 `docs/01-guides/slam_nav/Jetson 8GB 快系統實作指南.md`
  - [ ] 包含 3 個 SLAM 方案的詳細對照
  - [ ] 每個方案的 Jetson 8GB 可行性評估
  - [ ] 整合參考資源連結

### 9.2 待 Jetson 到貨後執行（W2-W3）

- [ ] **JetPack 6.1 安裝 SOP**
  - [ ] 安裝 Jetson Orin Nano Super 開發者套件
  - [ ] 配置 CUDA 和 GPU 時鐘頻率
  - [ ] 啟用最高性能模式（`sudo /usr/bin/jetson_clocks`）
  - [ ] 驗證 JetPack 版本（`cat /etc/nv_tegra_release`）

- [ ] **RealSense D435i 整合**
  - [ ] 安裝 librealsense2 套件（`sudo apt install ros-humble-librealsense2`）
  - [ ] 測試相機連接（`realsense-viewer`）
  - [ ] 配置 JetPack 6.0+ 相容參數
  - [ ] 驗證深度影像和 RGB 影像發布

- [ ] **SLAM 方案驗證**
  - [ ] 測試 slam_toolbox 性能（建圖精度、延遲）
  - [ ] 測試 AMCL 粒子數最佳化
  - [ ] 驗證 Nav2 配置（路徑規劃速度、避障效果）
  - [ ] 如有需要，測試 RTAB-Map（需 JetPack 6.0+）

- [ ] **雙層架構實作**
  - [ ] 建立 HTTP API Client（Jetson 本地）
  - [ ] 實作 Skills Server 模組
  - [ ] 測試與 GPU Server 的通訊（HTTP 延遲）
  - [ ] 實作 Safety Layer 節點
  - [ ] 整合 Skills Server → Nav2 → Go2 流程

- [ ] **TTS 方案調研**
  - [ ] 評估本地 TTS 方案（espeak-ng、festival）
  - [ ] 評估雲端 TTS 方案（ElevenLabs、Azure TTS）
  - [ ] 比較延遲和語音品質

---

## 🔗 相關資源

### 參考文檔：
- [Isaac ROS Getting Started - System Requirements](https://nvidia-isaac-ros.github.io/v/release-3.2/getting_started/index.html)
- [Isaac ROS cuVSLAM Overview](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_visual_slam/index.html)
- [Ultralytics YOLO11 Jetson Guide](https://docs.ultralytics.com/guides/nvidia-jetson/)
- [Nav2 Configuration](https://docs.nav2.org/configuration/)
- [ROS2 Humble SLAM Toolbox](https://docs.ros.org/en/humble/p/slam_toolbox/)
- [Jetson Performance Best Practices](https://developer.nvidia.com/embedded-jetson/best-practices/)
- [RealSense D435 on Jetson](https://www.intel.com/content/www/us/en/support/articles/0000870686/intel-realsense-depth-cameras-d400-series-support-jetson-platform)

### 相關內部文件：
- `/mnt/c/Users/User/Desktop/elder_and_dog/docs/01-guides/slam_nav/Jetson 替換 VM.md` - 架構分析
- `/mnt/c/Users/User/Desktop/elder_and_dog/docs/00-overview/開發計畫.md` - 雙層 AI 架構
- `/mnt/c/Users/User/Desktop/elder_and_dog/go2_robot_sdk/config/nav2_params.yaml` - Nav2 基礎配置

---

**文檔維護者**: PawAI 專案團隊  
**最後更新**: 2026/01/24 13:50  
**文件路徑**: `/mnt/c/Users/User/Desktop/elder_and_dog/docs/01-guides/slam_nav/Jetson 8GB 快系統實作指南.md`
