# 人臉辨識與追蹤系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 機器狗能看到人、知道是誰、知道人在哪個方向
- 可以根據人的位置轉頭或移動
- **雲端負責「懂人是誰」，邊緣負責「快速反應」**

---

## 邊緣端 (Jetson 8GB) - 即時感知

### 人臉偵測方案

| 方案 | 特點 | 適用場景 |
|------|------|----------|
| **BlazeFace / MediaPipe** | 極輕量、低延遲、為行動端設計 | 首選方案，工程落地快 |
| **SCRFD** | 速度/精度平衡、InsightFace 家族 | 需要更高精度時 |
| **RetinaFace** | 精度導向、可輕量化 | 複雜場景 |

**關鍵點**：
- 使用 TensorRT 優化
- 輸入尺寸控制在合理範圍
- 避免 CPU 前處理瓶頸

### 人臉追蹤 (跨 frame 維持 ID)

| 方案 | 特點 | 開銷 |
|------|------|------|
| **SORT** | 最輕量、Kalman + Hungarian | 最低 |
| **ByteTrack** | 利用低分數框、減少軌跡碎裂 | 中 |
| **DeepSORT** | 加入外觀特徵、ID 更穩定 | 高 (需 embedding 網路) |

**建議**：人臉追蹤用 SORT/ByteTrack 即可，不需要像行人那麼強的 re-id

### 常見效能瓶頸

1. **資料搬運**：影像前處理在 CPU → GPU 拷貝造成延遲
2. **多模型串接**：各自做 resize/normalize 會線性累加
3. **推理精度**：TensorRT FP16/INT8 需權衡

### NVIDIA Isaac ROS 路線

- DNN Inference (TensorRT/Triton)
- NITROS (zero-copy)
- D435 → Encoder → TensorRT Node → Decoder

---

## 雲端端 (5×RTX 8000) - 深度識別

### 人臉識別模型

**主流方案**：ArcFace-style embedding

- **InsightFace**：整合式工具箱，含偵測/對齊/識別
- **Faiss/Milvus/Qdrant**：向量檢索與身份比對

**容量評估**：
- 人臉 embedding 模型相對小
- 48GB VRAM 可同時跑多路並行
- 建議用 Triton + 動態批次管理

### 頭部朝向/視線估計

| 方案 | 功能 | 備註 |
|------|------|------|
| **6DRepNet** | 頭部朝向 (unconstrained head pose) | 開源實作 |
| **OpenFace 2.0** | 一體化行為分析 (landmark + head pose + gaze + AUs) | 較完整 |
| **RT-GENE** | 視線估計 (gaze estimation) | 含 ROS 套件 |

**實務做法**：
1. InsightFace 做身份 embedding
2. OpenFace / 6DRepNet 做 head pose/gaze
3. 後端融合成「互動狀態」(看著你/背對你/對話中)

### 5×RTX 8000 分工建議

| 卡片 | 功能 | 說明 |
|------|------|------|
| **卡 1** | 人臉偵測/對齊/embedding | InsightFace + Faiss GPU |
| **卡 2** | 頭部朝向/視線 | OpenFace 或 6DRepNet |
| **卡 3** | 視覺屬性/情緒 | 擴充用 |
| **卡 4-5** | 語音服務或備援 | ASR/LLM/TTS |

**容錯**：可用 Kubernetes + NVIDIA device plugin 做健康檢查與重啟

---

## 邊緣-雲端協作架構

### 資料流設計

**邊緣端預篩選**：
- 偵測到人臉 → 上傳 ROI crop + metadata
- 或上傳 embedding 向量 (更省頻寬)

**壓縮策略 (由省頻寬到最省)**：

1. **整張 RGB 串流** (H.264/H.265)：延遲可控但頻寬最大
2. **人臉 crop (JPEG)**：常見折衷，只在新 track 或每 N 秒上傳
3. **Embedding 向量**：頻寬最省，但邊緣需有一致模型

### 深度資訊處理

**建議**：邊緣端處理 depth → 只傳 3D 座標

```
D435 aligned_depth → 取 ROI 深度統計 (median) → 傳 3D 坐標
```

若需上雲：使用 `compressed_depth_image_transport` (PNG 壓縮)

---

## ROS2 整合

### LAN 內 (Jetson ↔ Go2)

- Unitree SDK2 基於 CycloneDDS
- 與 ROS2 DDS 底層相容
- 用 ROS2 msg/topic 控制/取狀態

### 跨 WAN (邊緣 ↔ 雲端)

| 方案 | 用途 |
|------|------|
| **DDS Router** | 官方方案，TCP/WAN 範例 |
| **Zenoh Bridge** | 更輕量，減少 discovery 壓力 |

---

## 參考資源

- [InsightFace](https://github.com/deepinsight/insightface)
- [OpenFace](https://github.com/TadasBaltrusaitis/OpenFace)
- [6DRepNet](https://github.com/thohemp/6DRepNet)
- [NVIDIA Isaac ROS DNN Inference](https://github.com/NVIDIA-ISAAC-ROS/isaac_ros_dnn_inference)
- [RealSense ROS2](https://github.com/IntelRealSense/realsense-ros)
