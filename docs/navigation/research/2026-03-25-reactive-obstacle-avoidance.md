# 反應式避障可行性研究報告

---

**文件版本**：v1.0
**建立日期**：2026-03-25
**作者**：System Architect
**文件定位**：技術決策依據 — 反應式避障方案選型與架構設計
**適用範圍**：Unitree Go2 Pro + Intel RealSense D435 + NVIDIA Jetson Orin Nano 8GB
**前置文件**：
- [`docs/navigation/README.MD`](../導航避障/README.MD) — 導航避障總體規劃
- [`docs/navigation/深度攝影機避障.md`](../導航避障/深度攝影機避障.md) — Phase 0-2 設計文件
- [`docs/navigation/Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md`](../導航避障/Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md) — LiDAR Go/No-Go 分析

---

## 1. 摘要與決策建議

### 1.1 一句話決策

> **採用 D435 ROI Depth Threshold 作為反應式避障主線，放棄 LiDAR/Nav2 路徑。**

### 1.2 決策摘要

| 項目 | 決策 |
|------|------|
| **主線方案** | 方案 A：D435 ROI Depth Threshold（~50 行 Python，純 numpy） |
| **LiDAR 避障** | No-Go — WebRTC 通道 `gap_max > 1.0s`，違反安全硬門檻 |
| **Nav2 整合** | 暫不投入 — LiDAR 資料新鮮度未達 gate，且時程不允許（4/13 硬底線） |
| **預估工時** | 10-12 小時（含 30 次防撞測試） |
| **資源衝擊** | 極小 — 純 numpy ROI 運算，CPU 增量 < 2%，記憶體增量 < 50MB |
| **安全定位** | P2 加分項 — 不搶 P0 人臉/語音/AI 大腦的穩定性 |

### 1.3 決策依據三要素

1. **LiDAR 資料不可用**：Go2 Pro WebRTC 通道實測 0.03-2Hz，gap_max 常態 > 1.0s，違反連續避障硬門檻
2. **D435 已就位**：設備已安裝、TF 已校準、face_perception 已使用 RGB 通道，depth 通道空閒可用
3. **時程壓力**：4/13 文件繳交、五月展示，僅能投入最簡方案

---

## 2. 背景

### 2.1 Go2 Pro LiDAR 問題歷史

Go2 Pro 搭載 3D LiDAR，理論上可提供 360° 障礙感知。然而自專案初期（2025 年底）即發現 LiDAR 資料透過 WebRTC 通道傳輸時頻率極低、間隔不穩定。多輪深度研究（2026-01 至 2026-03）確認此為系統性問題而非偶發故障。

### 2.2 為什麼被列為 P2

根據 [`docs/mission/README.md`](../mission/README.md) v2.2 的核心定位：

> 「以人機互動為主、導航避障為輔」

專案 P0 為人臉辨識 + 中文語音互動 + AI 大腦決策。導航避障從一開始即被定義為 P2 加分項，原因包括：

- Go2 Pro 的 LiDAR 頻率問題在早期即被發現
- 團隊人力集中在感知與互動模組
- 展示場景為室內定點互動，非長距離自主巡航

### 2.3 已有的設計文件

[`docs/navigation/深度攝影機避障.md`](../導航避障/深度攝影機避障.md) 於 2026-03-11 建立，規劃了 Phase 0（反應式避障）→ Phase 1（Nav2 局部導航）→ Phase 2（nvblox + 語意）三階段路線。該文件設計完整但因以下原因未落地：

- LiDAR 資料新鮮度始終未通過 Gate G3（`gap99 <= 0.5s`、`gap_max <= 1.0s`）
- 3/16 攻守交換後，核心人力轉向語音/手勢/姿勢模組
- Phase 0 設計依賴 `nav2_collision_monitor`，架構偏重

本報告在該文件基礎上，提出更輕量的替代方案。

---

## 3. Go2 LiDAR 深度分析（為什麼不可用）

### 3.1 問題本質：WebRTC 通道限制，非硬體問題

Go2 Pro 的 LiDAR 硬體本身功能正常。問題在於 Go2 Pro 的資料傳輸架構：

```
[Go2 內部 LiDAR] → [Go2 內部處理] → [WebRTC DataChannel] → [外部 ROS2]
```

Go2 Pro **僅支援 WebRTC 通道**傳輸感測資料。LiDAR 點雲經過 Go2 內部處理後，透過 WebRTC DataChannel 以 JSON/Binary 格式傳送到外部 Jetson。這條路徑的頻寬與排程特性，導致點雲更新頻率遠低於硬體原生能力。

### 3.2 Go2 Pro vs EDU 差異

| 特性 | Go2 Pro | Go2 EDU |
|------|---------|---------|
| DDS 支援 | 無（僅 WebRTC） | CycloneDDS 直連 |
| LiDAR 存取 | 透過 WebRTC DataChannel 間接取得 | 直接 ROS2 topic |
| 理論 LiDAR 頻率 | 10Hz（硬體） | 10Hz（硬體） |
| 實測 LiDAR 頻率 | **0.03-2Hz** | ~10Hz（社群報告） |
| 即時避障可行性 | **No-Go** | 可行 |

Go2 Pro 無法像 EDU 版本透過 CycloneDDS/Ethernet 直接存取 LiDAR topic。所有感測資料必須經過 WebRTC 通道，這是架構性限制，無法透過軟體調優解決。

### 3.3 實測數據

根據 [`Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md`](../導航避障/Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md) 的分析：

| 指標 | 實測值 | 安全門檻 | 判定 |
|------|--------|----------|------|
| 平均頻率 | 0.03-2 Hz | >= 5 Hz | **FAIL** |
| gap_max | > 1.0s（常態） | <= 1.0s | **FAIL** |
| gap_99 | > 0.5s | <= 0.5s | **FAIL** |
| Burst+Gap 模式 | 數幀 burst 後長 gap | 穩定間隔 | **FAIL** |

**關鍵特徵**：LiDAR 資料並非穩定低頻，而是呈現 **burst + gap** 模式 — 短時間內收到數幀資料（burst），隨後出現超過 1 秒的空白期（gap）。這種模式對即時避障尤其危險，因為在 gap 期間機器人完全「失明」。

### 3.4 資料路徑全鏈分析

```
[LiDAR 硬體 10Hz]
    → [Go2 內部 MCU 處理]          ← 無法存取/調整
    → [Go2 WebRTC 序列化]          ← 頻寬受限、排程不可控
    → [WebRTC DataChannel 傳輸]    ← 與音訊/視訊/控制共用通道
    → [go2_ros2_sdk 解碼]          ← LIDAR_POINT_STRIDE 降採樣
    → [pointcloud_to_laserscan]    ← 轉 2D LaserScan
    → [/scan topic]                ← 實測 0.03-2Hz
```

瓶頸位於 Go2 內部的 WebRTC 序列化與 DataChannel 傳輸層，這兩層對外部開發者完全不透明、不可調整。

### 3.5 gap_max > 1.0s = No-Go 的硬門檻

根據研究綜整文件定義的 Go/No-Go Gate：

> **No-Go 任一成立**：
> - `gap_max > 1.0s`
> - `gap99 > 0.5s`（連續避障模式）
> - `age99 > 0.2s`（moving localization）

以 Go2 Pro 行走速度 0.2 m/s 計算：

- gap_max = 1.0s → 盲區距離 = **0.2m**
- gap_max = 2.0s → 盲區距離 = **0.4m**（超過 Go2 機身半徑）

在 1-2 秒的感測空白期內，Go2 可能已經撞上障礙物。這不是「體感不好」的問題，而是**物理安全風險**。實測中已發生撞椅子事件。

### 3.6 LIDAR_POINT_STRIDE 問題

`go2_ros2_sdk` 預設 `LIDAR_POINT_STRIDE=8`，意即每 8 個點只取 1 個，丟棄 87.5% 的點雲資料。即使將 stride 降至 1，仍無法解決 WebRTC 通道的頻率瓶頸。Stride 調整只能改善空間解析度，無法改善時間解析度。

### 3.7 上游 PR #181 未落地

go2_ros2_sdk 上游有 PR #181 嘗試改善 LiDAR 傳輸效率，但截至本文撰寫日（2026-03-25），該 PR 尚未合併。即使合併，也無法根本解決 WebRTC 通道的架構性頻寬限制。

---

## 4. D435 深度避障技術評估

### 4.1 D435 硬體規格

| 規格 | 數值 |
|------|------|
| 深度 FOV | 87° (H) x 58° (V) |
| 有效深度範圍 | 0.3m - 3.0m（室內最佳） |
| 深度精度 | < 2% @ 2m |
| 深度解析度 | 最高 1280x720 @ 30fps |
| 建議避障解析度 | 424x240 @ 15fps（Jetson 優化） |
| 快門類型 | Global shutter（紅外 IR） |
| 介面 | USB 3.0 Type-C |
| 尺寸 | 90 x 25 x 25 mm |
| 重量 | 72g |

### 4.2 D435 vs LiDAR 比較表

| 比較項目 | D435 深度 | Go2 Pro LiDAR（經 WebRTC） |
|----------|-----------|---------------------------|
| **實際更新率** | **30 fps**（可調） | **0.03-2 Hz** |
| **視角** | 87° x 58°（前方） | 360°（全向） |
| **有效範圍** | 0.3-3.0m | 0.3-12m |
| **盲區** | 0.3m 近距 + 後方/側方 | 近場低矮物（LiDAR 高度以下） |
| **資料路徑** | USB 3.0 直連 Jetson | WebRTC DataChannel 間接 |
| **可控性** | 完全可控（SDK + ROS2 driver） | 不可控（Go2 內部處理） |
| **額外成本** | 零（已安裝） | 零（已內建） |
| **可靠性** | 穩定 | 不穩定（burst+gap） |
| **光線敏感** | 強光/IR 干擾 | 不受光線影響 |
| **反光/玻璃** | 深度失效 | 可偵測 |

### 4.3 D435 的核心優勢

1. **30fps vs <2Hz**：更新率差距超過一個數量級，是決定性優勢
2. **已有設備**：D435 已安裝於 Go2 頭部，TF 已校準，face_perception 已使用 RGB 通道
3. **零額外成本**：不需採購新硬體，不需改動機械結構
4. **完全可控**：realsense2_camera ROS2 driver 提供完整參數調整能力
5. **資料路徑可靠**：USB 3.0 直連 Jetson，不經過 Go2 內部處理

### 4.4 D435 的已知限制

1. **僅前方 87°**：無側方與後方覆蓋，Go2 後退或側移時無保護
2. **0.3m 近距盲區**：D435 最小深度距離 0.3m，極近距離障礙無法偵測
3. **玻璃與反光**：紅外結構光遇到透明或鏡面材質時深度失效
4. **強光干擾**：戶外強光或 IR 光源可能干擾深度品質
5. **低紋理表面**：純白牆面等低紋理區域深度可能稀疏

---

## 5. 四種可行方案比較

### 方案 A：ROI Depth Threshold（推薦）

**原理**：直接訂閱 D435 depth image，對中央 ROI 區域計算最小深度值，與閾值比較決定 stop/slow/clear。

**特點**：
- 最簡實作，核心邏輯約 50 行 Python
- 純 numpy 運算，無額外依賴
- 不需 PointCloud2、不需 TF 轉換、不需 Nav2
- 可直接發送 WebRTC 停車命令或 `/cmd_vel`

### 方案 B：depthimage_to_laserscan + 自訂節點

**原理**：將 D435 depth image 轉換為虛擬 LaserScan，再由自訂節點判斷距離閾值。

**特點**：
- 利用 `depthimage_to_laserscan` ROS2 package
- 輸出標準 LaserScan 格式，未來可接入 Nav2
- 中等複雜度，需處理 scan 參數配置
- 增加一個 ROS2 node 的開銷

### 方案 C：pointcloud_to_laserscan + 自訂節點

**原理**：啟用 D435 PointCloud2 輸出，轉為 LaserScan 後處理。

**特點**：
- 需啟用 D435 pointcloud（額外 CPU/記憶體開銷）
- 資料量較大（424x240 = ~100K 點/幀）
- 精確度高，可做 3D 地面去除
- 較高的系統複雜度

### 方案 D：NVIDIA nvblox

**原理**：使用 NVIDIA Isaac ROS nvblox 建立 3D ESDF 地圖，做體積避障。

**特點**：
- GPU 加速，精確的 3D 障礙表示
- 系統複雜度極高，依賴重
- Jetson 8GB 記憶體壓力大
- 部署與除錯成本高
- 與目前 P2 定位不符

### 方案比較表

| 指標 | 方案 A (ROI Threshold) | 方案 B (depth→laserscan) | 方案 C (pointcloud→laserscan) | 方案 D (nvblox) |
|------|:---:|:---:|:---:|:---:|
| **實作複雜度** | 極低（~50 行） | 中（~200 行 + config） | 中高（~300 行 + config） | 極高 |
| **額外 CPU** | < 2% | ~5% | ~10% | ~25% |
| **額外 GPU** | 0% | 0% | 0% | 30-50% |
| **額外記憶體** | < 50 MB | ~100 MB | ~200 MB | ~1.5 GB |
| **精確度** | 中（ROI 粗粒度） | 中高（2D 掃描線） | 高（3D 點雲） | 極高（3D 體積） |
| **Nav2 擴展性** | 低 | 高（標準 LaserScan） | 高（標準 PointCloud2） | 極高 |
| **部署風險** | 極低 | 低 | 中 | 高 |
| **工時估算** | 4-6hr | 8-12hr | 12-16hr | 40hr+ |
| **適合 P2 定位** | **是** | 是 | 勉強 | 否 |

**決策**：方案 A 最符合 P2 定位 — 最小投入、最低風險、足夠實用。若未來需要更精確的避障或 Nav2 整合，可平滑升級至方案 B。

---

## 6. 推薦方案 A 詳細設計（Clean Architecture）

### 6.1 層級設計

遵循專案 [Clean Architecture 分層原則](../architecture/clean_architecture.md)，將避障模組分為四層：

```
obstacle_guard/
├── domain/
│   ├── entities/
│   │   └── obstacle_zone.py        # ObstacleZone entity
│   └── interfaces/
│       └── depth_provider.py        # IDepthProvider interface
├── application/
│   └── services/
│       └── obstacle_guard_service.py # ObstacleGuardService
├── infrastructure/
│   └── d435_depth_adapter.py        # D435DepthAdapter
└── presentation/
    └── obstacle_guard_node.py       # ROS2 Node 入口
```

### 6.2 Domain Layer

```python
# domain/entities/obstacle_zone.py
from dataclasses import dataclass
from enum import Enum

class ZoneLevel(Enum):
    CLEAR = "clear"       # 無障礙，正常行動
    SLOW = "slow"         # 減速區，降低速度
    STOP = "stop"         # 停車區，立即停止

@dataclass
class ObstacleZone:
    level: ZoneLevel
    min_depth_m: float          # ROI 內最小深度（公尺）
    valid_pixel_ratio: float    # 有效深度像素比例
    stamp_sec: float            # 時間戳

    @property
    def is_safe(self) -> bool:
        return self.level == ZoneLevel.CLEAR

    @property
    def is_degraded(self) -> bool:
        """有效像素過少，深度品質退化"""
        return self.valid_pixel_ratio < 0.3
```

```python
# domain/interfaces/depth_provider.py
from abc import ABC, abstractmethod
import numpy as np

class IDepthProvider(ABC):
    @abstractmethod
    def get_depth_frame(self) -> tuple[np.ndarray | None, float]:
        """回傳 (depth_image_uint16, timestamp_sec)
        depth_image 單位為 mm（D435 原生格式）
        無資料時回傳 (None, timestamp)
        """
        raise NotImplementedError
```

### 6.3 Application Layer

```python
# application/services/obstacle_guard_service.py
import numpy as np
from ...domain.entities.obstacle_zone import ObstacleZone, ZoneLevel

class ObstacleGuardService:
    """ROI 深度閾值避障服務

    算法：
    1. 從 depth image 擷取中央 ROI
    2. 過濾地面區域（排除 ROI 下方 1/4）
    3. 計算 ROI 內有效像素的最小深度
    4. 與 stop/slow 閾值比較，輸出 ZoneLevel
    """

    def __init__(
        self,
        stop_threshold_m: float = 0.8,
        slow_threshold_m: float = 1.5,
        roi_width_ratio: float = 0.33,
        roi_height_start: float = 0.25,   # ROI 起始高度比例（排除上方天花板）
        roi_height_end: float = 0.75,     # ROI 結束高度比例（排除下方地面）
        min_valid_ratio: float = 0.1,     # 最低有效像素比例
    ):
        self._stop_mm = int(stop_threshold_m * 1000)
        self._slow_mm = int(slow_threshold_m * 1000)
        self._roi_w = roi_width_ratio
        self._roi_h_start = roi_height_start
        self._roi_h_end = roi_height_end
        self._min_valid = min_valid_ratio

    def evaluate(self, depth_mm: np.ndarray, stamp_sec: float) -> ObstacleZone:
        """評估單幀深度影像，回傳 ObstacleZone"""
        h, w = depth_mm.shape[:2]

        # 1. 擷取 ROI：中央 1/3 寬 x 中間 1/2 高
        cx = w // 2
        half_w = int(w * self._roi_w / 2)
        y_start = int(h * self._roi_h_start)
        y_end = int(h * self._roi_h_end)

        roi = depth_mm[y_start:y_end, cx - half_w:cx + half_w]

        # 2. 過濾無效值（0 = 無深度）
        valid_mask = roi > 0
        valid_ratio = float(np.count_nonzero(valid_mask)) / max(roi.size, 1)

        # 3. 有效像素不足 → 保守停車
        if valid_ratio < self._min_valid:
            return ObstacleZone(
                level=ZoneLevel.STOP,
                min_depth_m=0.0,
                valid_pixel_ratio=valid_ratio,
                stamp_sec=stamp_sec,
            )

        # 4. 計算有效像素最小深度
        min_depth_mm = int(np.min(roi[valid_mask]))
        min_depth_m = min_depth_mm / 1000.0

        # 5. 閾值判斷
        if min_depth_mm < self._stop_mm:
            level = ZoneLevel.STOP
        elif min_depth_mm < self._slow_mm:
            level = ZoneLevel.SLOW
        else:
            level = ZoneLevel.CLEAR

        return ObstacleZone(
            level=level,
            min_depth_m=min_depth_m,
            valid_pixel_ratio=valid_ratio,
            stamp_sec=stamp_sec,
        )
```

### 6.4 Infrastructure Layer

```python
# infrastructure/d435_depth_adapter.py
import numpy as np
import time
from ..domain.interfaces.depth_provider import IDepthProvider

class D435DepthAdapter(IDepthProvider):
    """D435 深度影像適配器

    接收 ROS2 depth image callback 傳入的 numpy array，
    提供給 ObstacleGuardService 使用。
    """

    def __init__(self):
        self._latest_frame: np.ndarray | None = None
        self._latest_stamp: float = 0.0

    def update(self, depth_mm: np.ndarray, stamp_sec: float) -> None:
        """由 ROS2 callback 呼叫，更新最新深度幀"""
        self._latest_frame = depth_mm
        self._latest_stamp = stamp_sec

    def get_depth_frame(self) -> tuple[np.ndarray | None, float]:
        return self._latest_frame, self._latest_stamp
```

### 6.5 Presentation Layer

```python
# presentation/obstacle_guard_node.py
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from cv_bridge import CvBridge
import json
import time

from ..infrastructure.d435_depth_adapter import D435DepthAdapter
from ..application.services.obstacle_guard_service import ObstacleGuardService

class ObstacleGuardNode(Node):
    def __init__(self):
        super().__init__("obstacle_guard_node")

        # 參數宣告
        self.declare_parameter("stop_threshold", 0.8)
        self.declare_parameter("slow_threshold", 1.5)
        self.declare_parameter("roi_width_ratio", 0.33)
        self.declare_parameter("roi_height_start", 0.25)
        self.declare_parameter("roi_height_end", 0.75)
        self.declare_parameter("evaluate_hz", 10.0)

        # Infrastructure
        self._adapter = D435DepthAdapter()
        self._bridge = CvBridge()

        # Application
        self._service = ObstacleGuardService(
            stop_threshold_m=self.get_parameter("stop_threshold").value,
            slow_threshold_m=self.get_parameter("slow_threshold").value,
            roi_width_ratio=self.get_parameter("roi_width_ratio").value,
            roi_height_start=self.get_parameter("roi_height_start").value,
            roi_height_end=self.get_parameter("roi_height_end").value,
        )

        # ROS2 Subscriber: D435 depth image
        self.create_subscription(
            Image,
            "/camera/camera/depth/image_rect_raw",
            self._on_depth,
            10,
        )

        # ROS2 Publisher: 避障狀態
        self._status_pub = self.create_publisher(
            String, "/obstacle_guard/status", 10
        )

        # 定時評估（與 depth callback 解耦）
        hz = self.get_parameter("evaluate_hz").value
        self.create_timer(1.0 / hz, self._evaluate)

        self.get_logger().info(
            f"ObstacleGuardNode started: stop={self.get_parameter('stop_threshold').value}m, "
            f"slow={self.get_parameter('slow_threshold').value}m"
        )

    def _on_depth(self, msg: Image) -> None:
        """深度影像 callback — 僅更新 adapter，不做運算"""
        depth = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        self._adapter.update(depth, stamp)

    def _evaluate(self) -> None:
        """定時評估障礙狀態"""
        frame, stamp = self._adapter.get_depth_frame()
        if frame is None:
            return

        zone = self._service.evaluate(frame, stamp)

        # 發布狀態
        payload = {
            "stamp": zone.stamp_sec,
            "level": zone.level.value,
            "min_depth_m": round(zone.min_depth_m, 3),
            "valid_ratio": round(zone.valid_pixel_ratio, 3),
            "degraded": zone.is_degraded,
        }
        msg = String()
        msg.data = json.dumps(payload)
        self._status_pub.publish(msg)

        # 動作觸發（可接 /webrtc_req 或 /cmd_vel）
        if zone.level.value == "stop":
            self._send_stop()

    def _send_stop(self) -> None:
        """發送停車指令

        實作選項：
        1. 發布 /webrtc_req 的 StopMove 命令（與現有驅動整合）
        2. 發布 /cmd_vel 零速（需 twist_mux 仲裁）
        """
        # TODO: 根據系統整合方式選擇實作
        pass
```

### 6.6 ROS2 介面設計

#### 訂閱 Topic

| Topic | Message Type | 來源 | 說明 |
|-------|-------------|------|------|
| `/camera/camera/depth/image_rect_raw` | `sensor_msgs/Image` | realsense2_camera | D435 深度影像（uint16, mm） |

#### 發布 Topic

| Topic | Message Type | 目標 | 說明 |
|-------|-------------|------|------|
| `/obstacle_guard/status` | `std_msgs/String` (JSON) | 監控 / 中控 | 避障狀態（level, min_depth, valid_ratio） |

#### 動作發送（二選一）

| 方式 | Topic | 適用情境 |
|------|-------|---------|
| WebRTC 停車 | `/webrtc_req` | 與現有 go2_driver_node 整合，直接 DataChannel 停車 |
| cmd_vel 零速 | `/cmd_vel_safe` + twist_mux | 未來 Nav2 整合時使用 |

#### 參數列表

| 參數 | 型別 | 預設 | 說明 |
|------|------|------|------|
| `stop_threshold` | float | 0.8 | 停車距離閾值（公尺） |
| `slow_threshold` | float | 1.5 | 減速距離閾值（公尺） |
| `roi_width_ratio` | float | 0.33 | ROI 寬度佔畫面比例 |
| `roi_height_start` | float | 0.25 | ROI 起始高度比例（排除天花板） |
| `roi_height_end` | float | 0.75 | ROI 結束高度比例（排除地面） |
| `evaluate_hz` | float | 10.0 | 評估頻率 |

### 6.7 狀態輸出 Schema

```json
{
  "stamp": 1773561600.789,
  "level": "stop",
  "min_depth_m": 0.652,
  "valid_ratio": 0.87,
  "degraded": false
}
```

| 欄位 | 型別 | 說明 |
|------|------|------|
| `stamp` | float | 深度幀時間戳（Unix seconds） |
| `level` | string | `"clear"` / `"slow"` / `"stop"` |
| `min_depth_m` | float | ROI 內最小有效深度（公尺） |
| `valid_ratio` | float | 有效深度像素比例 [0, 1] |
| `degraded` | bool | 深度品質是否退化（valid_ratio < 0.3） |

---

## 7. D435 前處理建議

### 7.1 深度濾波器配置

D435 ROS2 driver 內建硬體級後處理濾波器，建議啟用以改善深度品質：

| 濾波器 | 用途 | 建議設定 |
|--------|------|---------|
| **Decimation Filter** | 降解析度，減少運算量 | `filter_magnitude: 2`（解析度減半） |
| **Spatial Filter** | 空間平滑，去除邊緣雜訊 | `filter_smooth_alpha: 0.5`, `filter_smooth_delta: 20` |
| **Temporal Filter** | 時間平滑，去除閃爍 | `filter_smooth_alpha: 0.4`, `filter_smooth_delta: 20` |

### 7.2 realsense2_camera Launch 參數

```yaml
# 建議 D435 避障配置
depth_module.depth_profile: '424x240x15'   # Jetson 優化：低解析度 + 15fps
enable_depth: true
enable_color: true    # face_perception 需要 RGB，不可關閉
enable_infra1: false
enable_infra2: false
enable_gyro: false
enable_accel: false
pointcloud.enable: false   # 方案 A 不需要 PointCloud2
spatial_filter.enable: true
temporal_filter.enable: true
decimation_filter.enable: true
decimation_filter.filter_magnitude: 2
clip_distance: 3.0    # 超過 3m 的深度截斷
```

**注意**：原始設計文件建議 `enable_color: false`，但由於 face_perception 已使用 D435 RGB 通道，**必須保持 `enable_color: true`**。避障模組僅使用 depth 通道，不增加額外頻寬。

### 7.3 與 face_perception 共用 D435 的注意事項

| 議題 | 現況 | 建議 |
|------|------|------|
| D435 驅動實例 | face_perception 的 launch 已啟動 realsense2_camera | 避障模組**不再額外啟動** D435 驅動，直接訂閱同一 topic |
| RGB 通道 | face_perception 訂閱 `/camera/camera/color/image_raw` | 互不干擾 |
| Depth 通道 | 目前無人訂閱 `/camera/camera/depth/image_rect_raw` | obstacle_guard_node 訂閱此 topic |
| USB 頻寬 | RGB 640x480@30fps + Depth 424x240@15fps | USB 3.0 頻寬充裕，實測無問題 |
| CPU 負擔 | face_perception: YuNet CPU ~10% | 避障 numpy ROI: < 2% 增量 |

---

## 8. Nav2 整合現狀（為什麼不用）

### 8.1 已完成的工作

專案在 2025-11 至 2026-03 期間，已完成以下 Nav2 相關工作：

| 已完成項目 | 證據 |
|-----------|------|
| SLAM 建圖 | `scripts/start_nav2_localization.sh`、地圖檔案 |
| Nav2 完整配置 | `go2_robot_sdk/config/nav2_params.yaml` |
| AMCL 定位 | 可出 `/amcl_pose`（停車定位可用） |
| DWB 路徑規劃 | 配置完整，短距導航有時可成功 |
| twist_mux 仲裁 | `go2_robot_sdk/config/twist_mux.yaml` |
| D435 URDF | `go2_robot_sdk/urdf/go2_with_realsense.urdf` |
| 碰撞監控配置 | `docs/navigation/深度攝影機避障.md` 中的 collision_monitor_params |

### 8.2 為什麼棄用

| 原因 | 詳情 |
|------|------|
| **LiDAR < 2Hz** | 連續避障的硬門檻未通過（gap_max > 1.0s），Nav2 costmap 無法即時更新 |
| **安全風險** | 實測中已發生撞椅子事件 — LiDAR gap 期間機器人持續前進 |
| **時程壓力** | 4/13 文件繳交，核心人力已全投入 P0 感知/互動模組 |
| **複雜度過高** | Nav2 全鏈路（SLAM + AMCL + costmap + controller + collision_monitor）調試成本高 |
| **定位衝突** | 導航避障是 P2 加分項，不應搶佔 P0 資源 |

### 8.3 Nav2 配置的已知問題

| 問題 | 嚴重度 | 說明 |
|------|--------|------|
| `LIDAR_POINT_STRIDE=8` | 致命 | 丟棄 87.5% 點雲，costmap 障礙極稀疏 |
| `inflation_radius=0.35` | 高危 | Go2 體長 0.6m，僅 5cm 緩衝 |
| `movement_time_allowance=20s` | 中危 | 卡住判定過慢 |
| `BaseObstacle.scale=0.40` | 中危 | 避障權重不足 |
| 無 stale-data stop gate | 高危 | 感測逾時時無停車機制 |

### 8.4 未來恢復 Nav2 的條件

若未來要恢復 Nav2 導航，需滿足以下前置條件：

1. **硬體升級**：取得 Go2 EDU（支援 CycloneDDS 直連 LiDAR）或自行加裝外部 LiDAR
2. **感測新鮮度 Gate 通過**：`gap99 <= 0.5s`、`gap_max <= 1.0s`、`age99 <= 0.2s`
3. **stale-data stop gate**：實作並通過故障注入測試（3 秒感測黑屏必須停車）
4. **方案 B 升級**：先將方案 A 升級為 `depthimage_to_laserscan`，提供標準 LaserScan 給 Nav2
5. **D435 作為 costmap 觀測源**：在 `nav2_params.yaml` local costmap 新增 D435 PointCloud2/LaserScan

---

## 9. 與現有系統的整合

### 9.1 D435 共用感測器策略

D435 是系統內的共用感測器，多模組共享：

```
[Intel RealSense D435]
    ├── RGB: /camera/camera/color/image_raw
    │       └── face_perception (face_identity_node)
    ├── Depth: /camera/camera/depth/image_rect_raw
    │       └── obstacle_guard_node (新增)
    └── PointCloud2: /camera/camera/depth/color/points
            └── 目前未使用（未來方案 B/C 可啟用）
```

ROS2 的 pub/sub 模型天然支援多訂閱者，不需額外處理。

### 9.2 twist_mux 安全優先級

現有 `twist_mux.yaml` 配置：

```yaml
topics:
  joy:
    topic: cmd_vel_joy
    timeout: 0.5
    priority: 10       # 搖桿最高
  navigation:
    topic: cmd_vel
    timeout: 0.5
    priority: 5        # 導航
```

若未來避障需要透過 `cmd_vel` 路徑（而非直接 WebRTC 停車），建議新增：

```yaml
  safety:
    topic: cmd_vel_safe
    timeout: 0.1       # 短逾時 → 不搶佔
    priority: 100      # 最高優先級
```

**但目前建議**：方案 A 直接透過 `/webrtc_req` 發送 StopMove 命令，繞過 twist_mux。理由是 Go2 Pro 的移動控制本身就走 WebRTC DataChannel，透過 `/webrtc_req` 發送停車命令是最直接的路徑。

### 9.3 與 Demo 啟動腳本的整合

obstacle_guard_node 應整合至 Demo 啟動腳本（如 `scripts/start_full_demo_tmux.sh`），作為獨立 tmux pane：

```bash
# 在 tmux session 中新增 pane
tmux new-window -t demo -n obstacle_guard
tmux send-keys -t demo:obstacle_guard \
  "ros2 run obstacle_guard obstacle_guard_node --ros-args \
   -p stop_threshold:=0.8 -p slow_threshold:=1.5" Enter
```

### 9.4 啟動順序

```
1. D435 Driver (realsense2_camera)     ← face_perception launch 已啟動
2. face_perception (face_identity_node) ← 訂閱 RGB
3. vision_perception (手勢/姿勢)        ← 訂閱 RGB
4. obstacle_guard_node                  ← 訂閱 Depth（新增）
5. go2_driver_node                      ← 接收 /webrtc_req
```

obstacle_guard_node 啟動不依賴其他感知模組，僅需 D435 driver 已就緒。

---

## 10. 實作路線圖

| 階段 | 工作項目 | 預估工時 | 產出 |
|------|---------|:--------:|------|
| **S1** | obstacle_guard_node 核心實作（domain + application + infrastructure + presentation） | 4-6hr | 可獨立運行的 ROS2 node |
| **S2** | 參數調校（stop/slow 閾值、ROI 範圍） | 1-2hr | 適合實際場景的參數組 |
| **S3** | 與 go2_driver_node 整合（/webrtc_req StopMove） | 1hr | 自動停車功能 |
| **S4** | Launch 整合（加入 Demo 啟動腳本） | 1hr | 一鍵啟動 |
| **S5** | 30 次防撞測試 | 2-3hr | 測試報告 |
| | **總計** | **~10-12hr** | |

### 驗收標準

| 測試項目 | 通過標準 |
|----------|---------|
| 基本偵測 | 0.8m 內障礙觸發 STOP（30/30） |
| 減速區 | 0.8-1.5m 障礙觸發 SLOW |
| 連續測試 | 30 次直行障礙測試，0 碰撞 |
| 品質退化 | valid_ratio < 0.3 時保守停車 |
| D435 斷線 | D435 USB 拔除時系統不 crash |
| 資源使用 | CPU 增量 < 5%，記憶體增量 < 100MB |

---

## 11. 風險與緩解

| 風險 | 機率 | 影響 | 緩解措施 |
|------|:----:|:----:|---------|
| **D435 深度 + face RGB 搶 USB 頻寬** | 低 | 中 | USB 3.0 理論 5Gbps，RGB+Depth 實際約 200Mbps，餘量充裕。若出問題可降低 depth 解析度/幀率 |
| **地面誤判為障礙** | 中 | 中 | ROI 排除下方 25% 畫面（`roi_height_end: 0.75`）；可進一步用深度梯度排除水平面 |
| **玻璃/反光物深度失效** | 中 | 中 | `valid_ratio < 0.3` 時保守停車（「未知即危險」策略） |
| **僅前方 87° 防護** | 高 | 中 | 明確標示為「前向避障」，Go2 後退/側移時由操作者負責。Demo 場景以前進為主 |
| **0.3m 近距盲區** | 中 | 低 | D435 規格限制，0.3m 內已是碰撞距離，此時應已觸發停車。stop_threshold=0.8m 提供足夠煞車距離 |
| **Jetson 記憶體壓力** | 極低 | 低 | 純 numpy ROI 運算，記憶體增量 < 50MB。目前系統餘量 1.2GB+ |
| **depth image 延遲** | 低 | 中 | D435 USB 3.0 直連延遲 < 30ms，遠優於 LiDAR WebRTC 路徑 |

---

## 12. 開源專案研究摘要

專案早期評估了 5 個導航避障相關開源專案，結論為**「借概念不搬整套」**：

| 專案 | 核心定位 | 對本專案的價值 | 採納決策 |
|------|---------|---------------|---------|
| **Odin-Nav-Stack** | ROS1 導航棧 | 安全外圈、可觀測性、有界恢復流程的工程思路 | 借概念（安全監督層） |
| **OM1** | AI Runtime | 模式治理、失敗分類、安全監督層架構 | 借概念（lifecycle 管理） |
| **NavDP** | Sim-to-Real 研究框架 | 服務化接口、MPC 旁路、深度管線參考 | 借概念（深度前處理） |
| **LoGoPlanner** | 研究基準 | 深度前處理、A/B 評估模式、MPC shadow | 借概念（深度品質控制） |
| **visualnav-transformer** | GNM/ViNT/NoMaD | 資料前處理、Shadow 評測框架 | 僅研究參考 |

**共同結論**：所有專案都不適合直接移植。本專案應保持現有 ROS2 主線，從各專案提取可用的工程方法與局部技術。方案 A 的 ROI Depth Threshold 正是吸取了這些專案「保守安全優先」的核心理念，以最小複雜度實現基礎防護。

完整採納決策文件見 [`docs/navigation/開源專案/`](../導航避障/開源專案/) 目錄。

---

## 13. 參考資料

### 專案內部文件

| 文件 | 路徑 |
|------|------|
| 導航避障總體規劃 | `docs/navigation/README.MD` |
| 深度攝影機避障設計 | `docs/navigation/深度攝影機避障.md` |
| LiDAR 低頻感測研究 | `docs/navigation/Go2_低頻感測與BurstGap_研究綜整_2026-03-03.md` |
| 落地計畫 v2 | `docs/navigation/落地計畫_v2.md` |
| 開源專案採納決策 | `docs/navigation/開源專案/*.md` |
| Clean Architecture 原則 | `docs/pawai-brain/architecture/designs/clean-architecture.md` |
| ROS2 介面契約 v2.1 | `docs/contracts/interaction_contract.md` |
| 人臉辨識配置 | `face_perception/config/face_perception.yaml` |
| twist_mux 配置 | `go2_robot_sdk/config/twist_mux.yaml` |
| Nav2 參數 | `go2_robot_sdk/config/nav2_params.yaml` |

### 硬體規格

- [Intel RealSense D435 Datasheet](https://www.intelrealsense.com/depth-camera-d435/)
- [Unitree Go2 Pro Specifications](https://www.unitree.com/go2/)
- [NVIDIA Jetson Orin Nano 8GB Module](https://developer.nvidia.com/embedded/jetson-orin-nano)

### ROS2 / Nav2

- [RealSense ROS2 Wrapper](https://github.com/IntelRealSense/realsense-ros)
- [Nav2 Collision Monitor](https://docs.nav2.org/tutorials/docs/using_collision_monitor.html)
- [Nav2 Voxel Layer](https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html)
- [depthimage_to_laserscan](https://github.com/ros-perception/depthimage_to_laserscan)
- [pointcloud_to_laserscan](https://github.com/ros-perception/pointcloud_to_laserscan)
- [twist_mux](https://github.com/ros-teleop/twist_mux)

### 開源導航專案

- [Odin-Nav-Stack](https://github.com/jc-cr/Odin-Nav-Stack) — ROS1 導航棧
- [OM1 (Openmind)](https://github.com/OpenmindAGI/OM1) — AI Runtime
- [NavDP](https://github.com/navdp/NavDP) — Sim-to-Real 導航研究
- [LoGoPlanner](https://github.com/navdp/NavDP/tree/main/baselines/logoplanner) — 局部規劃研究基準
- [visualnav-transformer](https://github.com/robodhruv/visualnav-transformer) — GNM/ViNT/NoMaD

### NVIDIA Isaac ROS

- [Isaac ROS nvblox](https://nvidia-isaac-ros.github.io/repositories_and_packages/isaac_ros_nvblox/index.html)

---

*文件維護者：System Architect*
*狀態：v1.0 — 決策文件，待實作驗證後更新為 v1.1*
