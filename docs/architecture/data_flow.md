> **⚠️ OUTDATED** — 節點名稱未對齊實作（如 `FacePerceptionNode` 已不存在），資料流以 [interaction_contract.md](./interaction_contract.md) v2.0 為準。

# 資料流與互動流程

**文件定位**：PawAI 系統資料流向與互動流程說明  
**適用讀者**：開發者、整合者、測試人員  
**版本**：v1.0  
**更新日期**：2026-03-08

---

## 1. 系統資料流總覽

```
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Device Layer                                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │
│  │ RealSense   │  │ Go2 Robot   │  │ Microphone  │                 │
│  │ D435        │  │ Pro         │  │ Array       │                 │
│  │ (RGB+Depth) │  │ (Actuators) │  │ (Audio)     │                 │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                 │
└─────────┼────────────────┼────────────────┼────────────────────────┘
          │                │                │
          ▼                │                ▼
    /camera/...      /webrtc_req      /audio/...
          │                │                │
          ▼                │                ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 2: Perception Layer                                           │
│  ┌─────────────────┐  ┌─────────────────┐                          │
│  │ face_perception │  │ speech_processor│                          │
│  │ - YuNet         │  │ - ASR (Qwen3)   │                          │
│  │ - IOU Tracker   │  │ - TTS (Qwen3)   │                          │
│  │ - SFace (opt)   │  │                 │                          │
│  └────────┬────────┘  └────────┬────────┘                          │
│           │                    │                                   │
│           ▼                    ▼                                   │
│  /state/perception/face    /event/speech_intent                     │
│  /event/face_detected                                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 3: Interaction Executive                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ - Event Aggregator (事件聚合)                                │   │
│  │ - State Machine (狀態機)                                     │   │
│  │ - Skill Dispatcher (技能分派)                                │   │
│  │ - Safety Guard (安全仲裁)                                    │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                        │
│                           ▼                                        │
│              /state/executive/brain                                │
│                           │                                        │
└───────────────────────────┼────────────────────────────────────────┘
                            │
                            ▼
                      /webrtc_req
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  Layer 1: Device Layer (Actuators)                                   │
│  ┌─────────────┐                                                    │
│  │ Go2 Robot   │  執行動作 (wave/sit/stand)                         │
│  │ Pro         │                                                    │
│  └─────────────┘                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Face Perception 資料流

### 2.1 人臉偵測 → 揮手 完整流程

```
時間軸 ──────────────────────────────────────────────────────────────▶

[Frame N]   [Frame N+1]   [Frame N+2]   [Event]    [Skill]   [Action]
   │            │             │            │          │          │
   ▼            ▼             ▼            ▼          ▼          ▼
┌──────┐    ┌──────┐     ┌──────┐    ┌──────┐   ┌──────┐   ┌──────┐
│RGB   │    │RGB   │     │RGB   │    │      │   │      │   │      │
│Frame │───▶│Frame │────▶│Frame │    │      │   │      │   │      │
│      │    │      │     │      │    │      │   │      │   │      │
└──┬───┘    └──┬───┘     └──┬───┘    │      │   │      │   │      │
   │           │            │        │      │   │      │   │      │
   ▼           ▼            ▼        │      │   │      │   │      │
┌────────────────────────────────┐   │      │   │      │   │      │
│ YuNet Detector                 │   │      │   │      │   │      │
│ - Detect faces                 │   │      │   │      │   │      │
│ - Return bboxes + confidence   │   │      │   │      │   │      │
└───────────┬────────────────────┘   │      │   │      │   │      │
            │                        │      │   │      │   │      │
            ▼                        │      │   │      │   │      │
┌────────────────────────────────┐   │      │   │      │   │      │
│ IOU Tracker                    │   │      │   │      │   │      │
│ - Match with existing tracks   │   │      │   │      │   │      │
│ - Assign track_ids             │   │      │   │      │   │      │
│ - Estimate distance from depth │   │      │   │      │   │      │
└───────────┬────────────────────┘   │      │   │      │   │      │
            │                        │      │   │      │   │      │
            ▼                        │      │   │      │   │      │
    /state/perception/face           │      │   │      │   │      │
    (10 Hz continuous)               │      │   │      │   │      │
            │                        │      │   │      │   │      │
            ▼                        ▼      │   │      │   │      │
    ┌──────────────────────┐    ┌──────────┐│   │      │   │      │
    │ Event Trigger        │    │ Cooldown ││   │      │   │      │
    │ - New face detected  │───▶│ Check    ││   │      │   │      │
    │ - Interval passed    │    │ (5 sec)  ││   │      │   │      │
    └──────────────────────┘    └─────┬────┘│   │      │   │      │
                                      │     │   │      │   │      │
                                      ▼     │   │      │   │      │
                               /event/face_detected   │   │      │
                               (triggered)            │   │      │
                                      │               │   │      │
                                      ▼               ▼   ▼      ▼
                               ┌──────────────────────────────────┐
                               │ FaceInteractionNode              │
                               │ - Parse event                    │
                               │ - Check cooldown                 │
                               │ - Send WebRtcReq                 │
                               └──────────┬───────────────────────┘
                                          │
                                          ▼
                               /webrtc_req (WebRtcReq)
                                          │
                                          ▼
                               ┌──────────────────────────────────┐
                               │ go2_driver_node                  │
                               │ - Receive WebRtcReq              │
                               │ - Send via WebRTC                │
                               └──────────┬───────────────────────┘
                                          │
                                          ▼
                               WebRTC: rt/api/sport/request
                               api_id: 1016 (Hello)
                                          │
                                          ▼
                               ┌──────────────────────────────────┐
                               │ Go2 Pro Robot                    │
                               │ Execute: Hello (wave) 🐕👋       │
                               └──────────────────────────────────┘
```

### 2.2 時序說明

| 階段 | 延遲預算 | 實際組件 | 說明 |
|------|----------|----------|------|
| 影像擷取 | 33 ms | RealSense | 30 FPS = 33ms/幀 |
| YuNet 偵測 | 30-50 ms | YuNet (CUDA) | Jetson 優化後 |
| IOU 追蹤 | 1-2 ms | IOUTracker | NumPy 運算 |
| 深度估計 | 1-2 ms | Depth median | 簡單統計 |
| 狀態發布 | 1 ms | ROS2 pub | 本地通訊 |
| 事件觸發 | 0 ms | 立即 | 無延遲 |
| Skill 請求 | 5-10 ms | ROS2 pub | 本地通訊 |
| WebRTC 傳輸 | 20-50 ms | WebRTC | 網路延遲 |
| Go2 執行 | 500 ms | Go2 動作 | Hello 動作時間 |
| **總計** | **~600 ms** | | 從人臉出現到揮手 |

---

## 3. 狀態機流程

### 3.1 Face Perception 內部狀態

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FacePerceptionService                        │
│                                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐      │
│  │  NO_FACE │───▶│ DETECTED │───▶│ TRACKING │───▶│   LOST   │      │
│  │          │    │          │    │          │    │          │      │
│  │ 無人臉   │    │ 新偵測   │    │ 穩定追蹤 │    │ 追丟     │      │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘      │
│       │               │               │               │            │
│       │               │               │               │            │
│       ▼               ▼               ▼               ▼            │
│   持續偵測      publish_event    publish_state      等待           │
│                                    (10Hz)         max_lost       │
│                                                    frames        │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 事件觸發條件

| 事件 | 觸發條件 | 發布內容 |
|------|----------|----------|
| `detected` | 新 track_id 出現 | 第一個人臉的 track 資訊 |
| `detected` | 間隔 `event_interval_sec` 秒且有臉 | 當前最顯著人臉資訊 |
| (無 lost 事件) | MVP 簡化 | 僅追蹤遺失，不發布事件 |

---

## 4. 深度估計流程

### 4.1 深度計算

```
IOUTracker.update()
    │
    ├── 取得偵測框 bbox: (x1, y1, x2, y2)
    │
    ├── 裁切深度影像 ROI
    │   roi = depth_frame[y1:y2, x1:x2]
    │
    ├── 過濾無效深度值
    │   valid = roi[(roi > 0) & (roi < 10000)]
    │   # 過濾 0 (無深度) 和極大值 (錯誤)
    │
    ├── 計算中位數距離
    │   distance_mm = np.median(valid)
    │
    └── 轉換為米
        distance_m = distance_mm * 0.001
        
FaceTrack.distance_m = distance_m
```

### 4.2 深度精度

| 距離範圍 | 精度 | 說明 |
|----------|------|------|
| 0.5 - 1.0 m | ±3 cm | 高品質深度 |
| 1.0 - 2.0 m | ±5 cm | 良好深度 |
| 2.0 - 3.0 m | ±10 cm | 可用深度 |
| > 3.0 m | 不可靠 | 深度品質下降 |

---

## 5. 錯誤處理流程

### 5.1 無模型檔案

```
YuNetDetector.__init__()
    │
    ├── 檢查 model_path.exists()
    │   │
    │   └── False
    │       │
    │       └── raise FileNotFoundError
    │           "YuNet model not found: {path}"
    │
    └── face_perception_node 捕獲例外
        │
        └── 記錄錯誤並退出
            "Failed to load YuNet model, please run setup_jetson.sh"
```

### 5.2 無深度影像

```
IOUTracker.update()
    │
    ├── depth_frame is None
    │   │
    │   └── distance_m = None
    │
    └── FaceTrack 仍建立
        但 distance_m 為 null
        
JSON 輸出: "distance_m": null
```

### 5.3 深度 ROI 無效

```
_estimate_distance()
    │
    ├── roi 大小為 0 (bbox 無效)
    │   └── return None
    │
    ├── valid.size == 0 (無有效深度像素)
    │   └── return None
    │
    └── 正常計算
        return float(np.median(valid)) * scale
```

---

## 6. 效能監控

### 6.1 延遲測量點

```python
# face_perception_service.py

class FacePerceptionService:
    def process(self, frame_bgr, depth_frame, stamp_sec):
        t_start = time.time()
        
        # 1. 偵測
        t0 = time.time()
        detections = self._detector.detect(frame_bgr)
        t_detect = time.time() - t0
        
        # 2. 追蹤
        t1 = time.time()
        tracks = self._tracker.update(detections, depth_frame)
        t_track = time.time() - t1
        
        # 3. 發布
        t2 = time.time()
        self._publisher.publish_face_state(tracks, stamp_sec)
        t_pub = time.time() - t2
        
        t_total = time.time() - t_start
        
        # Log 效能（每 100 幀）
        if self._frame_count % 100 == 0:
            self._logger.debug(
                f"Perf: detect={t_detect*1000:.1f}ms "
                f"track={t_track*1000:.1f}ms "
                f"pub={t_pub*1000:.1f}ms "
                f"total={t_total*1000:.1f}ms"
            )
```

### 6.2 預期效能指標

| 組件 | 延遲預算 | 監控閾值 |
|------|----------|----------|
| YuNet 偵測 | 50 ms | > 100 ms 警告 |
| IOU 追蹤 | 5 ms | > 10 ms 警告 |
| 狀態發布 | 5 ms | > 10 ms 警告 |
| **單幀總計** | **100 ms** | **> 150 ms 警告** |

---

## 7. 測試驗證流程

### 7.1 單元測試

```python
# 測試 IOU 計算
def test_iou_overlap():
    tracker = IOUTracker()
    iou = tracker._iou(
        (100, 100, 200, 200),  # 框 A
        (150, 150, 250, 250)   # 框 B (50% 重疊)
    )
    assert 0.14 < iou < 0.15  # IOU ≈ 1/7
```

### 7.2 整合測試

```bash
# 1. 啟動 RealSense
ros2 launch realsense2_camera rs_launch.py

# 2. 啟動 face_perception
ros2 launch face_perception face_perception.launch.py

# 3. 觀察狀態輸出
ros2 topic hz /state/perception/face
# 預期：average rate: 10.0

# 4. 觀察事件觸發
ros2 topic echo /event/face_detected
# 預期：站在相機前時看到事件

# 5. 驗證 skill 發送
ros2 topic echo /webrtc_req
# 預期：事件後 5 秒內看到 WebRtcReq
```

---

## 8. 相關文件

- [README.md](./README.md) - 架構總覽
- [face_perception.md](./face_perception.md) - 人臉模組詳細架構
- [interaction_contract.md](./interaction_contract.md) - 介面規格

---

*維護者：System Architect*  
*最後更新：2026-03-08*
