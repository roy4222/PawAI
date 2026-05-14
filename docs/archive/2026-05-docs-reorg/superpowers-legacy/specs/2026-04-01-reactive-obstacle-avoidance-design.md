# Reactive Obstacle Avoidance — D435 Depth

**日期**：2026-04-01
**狀態**：Draft
**前置研究**：`docs/導航避障/research/2026-03-25-reactive-obstacle-avoidance.md`

---

## 一句話定位

D435 depth image → 前方上半部 ROI → 統計近距離像素比例 + 最小距離 → 超閾值就發 obstacle event → executive 觸發 Damp。

**不做自主導航、不做繞障、不做路徑規劃。** 這是反應式安全停車。

---

## 架構

```
D435 depth (15fps, 424x240, uint16 mm)
    │
    ▼
obstacle_avoidance_node (ROS2, vision_perception package)
    │  訂閱: /camera/camera/aligned_depth_to_color/image_raw
    │  內部: ObstacleDetector (純 Python/numpy, ~50 行)
    │
    ▼  發布: /event/obstacle_detected (String JSON, 只在偵測到時發)
    │
interaction_executive_node (已實作)
    │  收到 OBSTACLE event → 切換到 OBSTACLE_STOP
    │  執行 ACTION_DAMP (api_id 1001)
    │  debounce 2s + min_duration 1s → 恢復
    │
    ▼
Go2 (WebRTC /webrtc_req)
```

---

## ObstacleDetector（核心邏輯）

**純 Python class，不依賴 ROS2，100% 可單元測試。**

### 輸入
- `depth_frame`: numpy array `(H, W)` float32，單位 meters（由 node 轉換）

### 處理流程
1. **ROI 裁切**：取中央前方帶狀區域（跳過天花板和地板）
   - 垂直：40%~80%（D435 裝在額頭朝前，上方是天花板，下方是地板）
   - 水平：中央 60%
2. **無效值過濾**：`depth == 0` 或 `depth > max_range` 視為無效，不參與計算
3. **障礙物統計**：
   - `distance_min`：ROI 內有效像素的最小距離
   - `obstacle_ratio`：ROI 內 `< threshold_m` 的像素佔有效像素比例
4. **判定**：`obstacle_ratio >= ratio_trigger` → `is_obstacle = True`

### 輸出
```python
@dataclass
class ObstacleResult:
    is_obstacle: bool
    distance_min: float      # meters
    obstacle_ratio: float    # 0.0~1.0
    zone: str                # "clear" / "warning" / "danger"
```

### 三段式判定（Pass / Warning / Danger）
| Zone | 條件 | 行為 |
|------|------|------|
| clear | `obstacle_ratio < ratio_trigger` OR `distance_min > warning_m` | 無動作 |
| warning | `ratio_trigger` 達標 AND `distance_min` 在 `threshold_m ~ warning_m` | log only（不發 event） |
| danger | `ratio_trigger` 達標 AND `distance_min < threshold_m` | 發 `/event/obstacle_detected` |

### 參數（全部可調）
| 參數 | 預設 | 說明 |
|------|------|------|
| `threshold_m` | 0.8 | 危險距離（觸發 Damp） |
| `warning_m` | 1.2 | 警告距離（log only） |
| `max_range_m` | 3.0 | 超出此距離視為無障礙 |
| `roi_top_ratio` | 0.4 | ROI 頂部（佔 frame 高度比例） |
| `roi_bottom_ratio` | 0.8 | ROI 底部 |
| `roi_left_ratio` | 0.2 | ROI 左邊 |
| `roi_right_ratio` | 0.8 | ROI 右邊 |
| `obstacle_ratio_trigger` | 0.15 | 15% 像素達危險距離才觸發 |

---

## obstacle_avoidance_node（ROS2 包裝）

### 訂閱
- `/camera/camera/aligned_depth_to_color/image_raw`（sensor_msgs/Image, uint16 mm）

### 發布
- `/event/obstacle_detected`（std_msgs/String, JSON）— 只在 danger zone 時發布

### 處理流程
1. 收到 depth image callback
2. 轉換 uint16 mm → float32 meters
3. 呼叫 `ObstacleDetector.detect()`
4. **幀級 debounce**：連續 `N` 幀（預設 3）都是 danger 才發 event（避免 depth 抖動誤觸發）
5. 發布 event（rate-limited，預設 5 Hz）— payload 含 `stamp/event_type/distance_min/obstacle_ratio/zone`
6. 每幀 log zone 狀態（debug level）

### Event Schema（對齊 contract v2.2）
```json
{
  "stamp": 1775012345.678,
  "event_type": "obstacle_detected",
  "distance_min": 0.45,
  "obstacle_ratio": 0.23,
  "zone": "danger"
}
```

### Launch 參數
```python
"threshold_m": 0.8
"warning_m": 1.2
"max_range_m": 3.0
"obstacle_ratio_trigger": 0.15
"publish_rate_hz": 5.0
"debounce_frames": 3
"depth_topic": "/camera/camera/aligned_depth_to_color/image_raw"
```

---

## Executive 整合（已完成）

Executive v0 已實作 OBSTACLE_STOP 狀態 + debounce：
- 收到 `/event/obstacle_detected` → OBSTACLE_STOP → ACTION_DAMP
- 2s 無新 obstacle event → 嘗試 clear
- min_duration 1s → 回到前一狀態

**不需要改 executive 程式碼。**

---

## 檔案結構

### 新增
```
vision_perception/
  vision_perception/
    obstacle_detector.py           # 純 Python/numpy 核心邏輯
    obstacle_avoidance_node.py     # ROS2 node 包裝
  test/
    test_obstacle_detector.py      # 7+ unit tests (TDD)
  launch/
    obstacle_avoidance.launch.py   # Launch config
```

### 修改
```
vision_perception/setup.py         # 加 console_scripts entry
scripts/start_full_demo_tmux.sh    # 加 obstacle window
```

---

## TDD 測試案例

| # | 測試 | 輸入 | 預期 |
|:-:|------|------|------|
| 1 | 無障礙 | 全部 2.0m | `is_obstacle=False, zone="clear"` |
| 2 | 近距離障礙 | ROI 中央 0.3m | `is_obstacle=True, zone="danger"` |
| 3 | 部分障礙（低於 trigger） | 5% 像素 0.3m | `is_obstacle=False`（< 15%） |
| 4 | 警告區 | 20% 像素 1.0m | `zone="warning"`（不發 event） |
| 5 | 無效深度值 | 全部 0（NaN/invalid） | `is_obstacle=False`（無有效數據） |
| 6 | 混合有效/無效 | 50% 零 + 50% 0.3m | 只計算有效像素的比例 |
| 7 | 自定義閾值 | threshold=1.0, 全部 0.9m | `is_obstacle=True` |

---

## 降級策略（Sprint 計畫已定義）

| 場景 | 策略 |
|------|------|
| 30x 防撞全過 | Damp + 正常恢復 |
| 漏停 > 10% | 降為 Damp-only（不恢復） |
| 誤停 > 20% | Demo A 用、Demo B 關 |
| 整體不穩 | 完全停用 |

---

## 驗證計畫

### Phase 1：單元測試（TDD）
```bash
python3 -m pytest vision_perception/test/test_obstacle_detector.py -v
```

### Phase 2：Jetson 桌測
- D435 + obstacle_avoidance_node 單獨跑
- 手動拿物體接近鏡頭，觀察 Foxglove `/event/obstacle_detected`
- 確認 zone 判定正確

### Phase 3：Go2 上機 10x 防撞
- Go2 行走 → 前方放障礙物 → 觀察是否停下
- 記錄 stop latency、漏停率、誤停率

---

## 不做的事

- 不做繞障 / 路徑規劃
- 不做後方/側方偵測
- 不做 pointcloud 處理
- 不做 nvblox / costmap
- 不做地面落差偵測（第一版）
- 不改 executive 程式碼（已支援 OBSTACLE_STOP）
