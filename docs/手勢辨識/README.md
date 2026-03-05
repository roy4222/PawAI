# 手勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 用手勢指揮機器狗
- **靜態手勢**：停止 (手掌張開)、跟我來 (招手)、坐下 (雙手下壓)
- **動態手勢**：去那邊 (指向某方向)、畫圈 (巡邏這個區域)

---

## 邊緣端 (Jetson 8GB) - 即時反應

### 21 點手部關鍵點偵測

| 方案 | 特點 | 延遲 |
|------|------|------|
| **MediaPipe Hands** | Google 官方、on-device real-time、21 關鍵點 | ~15-20ms |
| **ros2_trt_pose_hand** | NVIDIA-AI-IOT、TensorRT 優化、ROS2 wrapper | 即時 |

**ros2_trt_pose_hand 輸出**：
- 21 keypoints
- 6 類手勢 (fist/pan/stop/fine/peace/no hand)
- 直接命中「邊緣即時反應」需求

### 靜態手勢分類

**常見做法**：Landmarks → 小型分類器

- MediaPipe landmarks + MLP/線性 SVM
- 延遲低、可控、易加入自訂手勢

### 動態手勢 (畫圈、揮手)

**方法**：追蹤 landmarks 時間序列

| 方法 | 特點 |
|------|------|
| **規則** | 軌跡方向/速度/圓形擬合 |
| **DTW/HMM** | 時間序列匹配 |
| **輕量 RNN/TCN** | 深度學習分類 |

**限制**：
- 遮擋造成 landmarks 抖動
- 快速運動失真
- 相機視角改變

---

## 雲端端 (5×RTX 8000) - 精細理解

### 3D 手部姿態/網格重建

| 方案 | 功能 | 備註 |
|------|------|------|
| **FrankMocap** | 單目影像 → 身體/手/臉 3D pose | 開源 |
| **InterHand2.6M** | 雙手互動 3D dataset + baseline | 研究用 |
| **HaMeR** | Transformer 做 3D hand mesh recovery | 較新 |

### 是否需要上雲端？

| 需求 | 建議 |
|------|------|
| 基本指令 (停止/跟隨/指向) | **邊緣端即可**，<100ms |
| 連續手語/複雜多模態 | 上雲端用更強模型 |

**分工策略**：
- 邊緣：手部偵測 → 低延遲指令
- 雲端：精細姿態/語義確認 (補充判斷)

---

## RGB-D 深度應用

### 深度在手勢辨識的優勢

1. **3D 幾何問題**：減少單目 scale/遮擋/背景歧義
2. **安全規則**：「手在 0.5-2m 才生效」
3. **指向估計**：3D pointing ray

### 資料分工建議

```
Jetson 端：
  ↓ D435 aligned_depth
  ↓ 取 ROI 深度統計
  ↓ 計算 3D 座標
  ↓ 只傳 3D 座標 (不上完整 depth)
```

若需上雲：`compressed_depth_image_transport` (PNG 壓縮)

---

## 機器人整合

### <100ms 延遲達成

1. 手勢辨識**必須在邊緣端完成**
2. 雲端只做「可選再確認」或「高階語義」
3. 使用 ros2_trt_pose_hand (TensorRT/ROS2)

### ROS2 控制串接

```
手勢節點 → /gesture_cmd (自訂 msg)
  ↓
Unitree 控制節點
  ↓
呼叫 Sport Service (StopMove/跟隨模式等)
```

**Unitree 介面**：
- SDK2 sports service
- 高階運動控制介面

---

## 手勢定義與 Skill 對應

| 手勢 | 類型 | 對應 Skill |
|------|------|------------|
| 手掌張開 | 靜態 | `stop()` |
| 招手 | 靜態 | `follow_person()` |
| 雙手下壓 | 靜態 | `sit_down()` |
| 指向方向 | 動態 | `navigate_to(direction)` |
| 畫圈 | 動態 | `patrol_area()` |

### 多模態衝突處理

**問題**：語音說「停止」但手勢是「跟隨」

**常見策略**：
- 優先級設定 (語音 > 手勢 或反之)
- 置信度比較
- 最後指令優先

---

## 參考資源

- [MediaPipe Hands](https://mediapipe-studio.webapps.google.com/studio/demo/hands)
- [ros2_trt_pose_hand](https://github.com/NVIDIA-AI-IOT/ros2_trt_pose_hand)
- [FrankMocap](https://github.com/facebookresearch/frankmocap)
- [InterHand2.6M](https://github.com/facebookresearch/InterHand2.6M)
- [HaMeR](https://github.com/geopavlakos/hamer)
