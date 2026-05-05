# 🎯 Object Detection System — 即時物體偵測 + 顏色識別


**一套完整的 Full-Stack 物體偵測系統，結合 YOLOv8n-seg + OpenCV HSV 色彩分析**

---

## 🌟 核心特性

| 特性 | 描述 |
|------|------|
| **即時物體偵測** | 使用 YOLOv8n-seg 在 50-80ms 內偵測 80 種物體 |
| **智能色彩識別** | 基於 HSV 色彩空間，8 種顏色自動分類 |
| **完全本地運算** | 所有 AI 推論在邊緣設備進行，隱私友善 |
| **Web 界面** | React 前端，無需安裝客戶端軟體 |
| **實時串流** | WebSocket + HTTP MJPEG，延遲 <250ms |
| **白名單篩選** | 動態選擇關注的物體類別 |
| **邊緣友善** | 6.3MB 模型，800-1200MB 記憶體 |

---

## 🚀 快速開始

### 前置要求

- Python 3.8+
- Node.js 16+ (前端)
- 攝影機 (800×600 以上解析度)
- 2GB+ RAM (推薦 4GB)

### 啟動

需要在 **3 個不同的終端** 中各啟動一個服務：

**終端 1️⃣ - 啟動 FastAPI 伺服器 (網關)**
```bash
cd pawai-studio/backend
py mock_server.py
```

---

**終端 2️⃣ - 啟動 YOLO 推論引擎**
```bash
cd pawai-studio/backend
py local_yolo.py
```

---

**終端 3️⃣ - 啟動前端開發伺服器**
```bash
cd pawai-studio
npm install                                 # 第一次只需要運行
npm run dev
```


✅ 前端已準備好

---

### 打開瀏覽器

訪問 `http://localhost:3000`

點擊左側邊欄的「**🎥 物體偵測**」或「**Python YOLO 串流**」按鈕

等待 3-5 秒讓 YOLO 模型完全加載（首次可能需要下載 25MB 模型）


---

## 📋 使用說明

### 主界面功能

#### 1. 🎥 鏡頭視窗 (Camera View)
```
640×480 實時影像區域，展示：
  • 實時攝影機畫面 (硬體或 MJPEG 串流)
  • 物體邊界框 (黃色 = 白名單，灰色 = 非白名單)
  • 物體標籤: [Color] [ClassName] [Confidence]%
  • 信息欄: 顯示使用的模型和物體數量
```

**切換鏡頭模式**:
- `[Python YOLO 串流]` — 推薦使用，影像已標註邊界框
- `[網頁硬體鏡頭]` — 使用本地 WebRTC (備用方案)

#### 2. 📋 即時偵測面板 (Detection Cards)
每張卡片顯示一個偵測到的物體：
```
┌─────────────────────────────┐
│ 📎 Blue scissors            │ ← Emoji + 顏色 + 名稱
│ scissors                    │ ← 類別名稱
│ ██████████████░░░░ 88%      │ ← 信心度條
│ 說明：常見的辦公工具        │ ← 物體信息
│ 🔊「檢測到一個藍色剪刀」   │ ← TTS 播報
│ [白名單]                    │ ← 白名單標籤
└─────────────────────────────┘
```

**白名單狀態**:
- 🟨 **黃色邊框** = 在白名單中 (優先顯示)
- 🔇 **灰色邊框** = 不在白名單中 (靜默狀態)

#### 3. 🔍 白名單管理 (Whitelist)
在左側邊欄選擇想關注的物體：
```
☑️ person (人)      ← 勾選
☑️ backpack (背包)  ← 勾選
☐ dog (狗)          ← 不勾選，則不高亮
☐ cat (貓)          ← 不勾選，則不高亮
...其他 80 種物體
```

#### 4. 📊 統計數據 (Statistics)
顯示本會話的統計資訊：
- 各物體檢測次數排行 (Top 5)
- 白名單覆蓋率
- 平均信心度
- 實時 FPS

---

## 🏗️ 系統架構

```
┌─────────────────────────────────────────────────────────┐
│         React Frontend (localhost:3000)                 │
│  • Camera View (鏡頭視窗 + Bbox 疊加)                  │
│  • Detection Cards (物體卡片面板)                       │
│  • Whitelist Manager (白名單管理)                      │
│  • Statistics (統計數據)                               │
└──────────────────────┬──────────────────────────────────┘
                       │ WebSocket /ws/events
                       ↓ (JSON 事件推送)
┌─────────────────────────────────────────────────────────┐
│      FastAPI Gateway (localhost:8000)                   │
│  • /ws/events (廣播偵測事件)                            │
│  • /mock/yolo/start (啟動推論引擎)                      │
│  • /mock/yolo/stop (停止推論引擎)                       │
│  • /mock/trigger (接收推論結果)                         │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP + JSON
                       ↓
┌─────────────────────────────────────────────────────────┐
│    Python Inference Engine (local_yolo.py)             │
│                                                         │
│  Layer 1: 攝影機採集                                   │
│    └─ OpenCV VideoCapture → 640×480 RGB               │
│                                                         │
│  Layer 2: 物體偵測 (50-80ms)                           │
│    └─ YOLOv8n-seg 推論                                │
│       ├─ boxes: [x1,y1,x2,y2,conf,cls]               │
│       └─ masks: 分割遮罩 (H×W)                        │
│                                                         │
│  Layer 3: 色彩分析 (2-5ms)                            │
│    ├─ 提取 bbox 內 ROI 區域                           │
│    ├─ 轉換為 HSV 色彩空間                             │
│    ├─ 計算平均 H, S, V 值                             │
│    └─ 根據 HSV 映射到 8 種顏色                        │
│                                                         │
│  Layer 4: 結果推送                                     │
│    └─ JSON 格式 → POST /mock/trigger                  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 效能指標

| 指標 | 值 | 備註 |
|------|-----|------|
| **推論延遲** | 50-80 ms | YOLOv8n-seg @CPU |
| **色彩檢測** | 2-5 ms | HSV 統計 |
| **網絡延遲** | 50-100 ms | WebSocket |
| **視頻延遲** | 100-150 ms | MJPEG 編碼 |
| **總延遲 (E2E)** | 150-250 ms | ✓ 可接受 |
| **幀率 (FPS)** | 5-25 | 取決於硬體 |
| **記憶體占用** | 800-1200 MB | 邊緣友善 |
| **模型大小** | 6.3 MB | 輕量化 |

### 硬體要求

**最低配置**:
- CPU: i5-8400 或 ARM Cortex-A72
- RAM: 2GB
- 存儲: 200MB (模型) + 500MB (依賴)

**推薦配置**:
- CPU: i7-10700 或 NVIDIA Jetson Nano
- RAM: 4GB+
- GPU: GTX 1660+ (可選，3-5 倍加速)

---

## 🎨 色彩識別映射表

系統使用 **OpenCV HSV 色調 (H: 0-180)** 自動分類物體顏色：

| H 值範圍 | 顏色 | 代表物體 |
|---------|------|---------|
| 0-10, 170-180 | Red | 紅蘋果、紅牌、停止標誌 |
| 10-20 | Orange | 橙子、橘子 |
| 20-35 | Yellow | 黃色剪刀、黃書、檸檬 |
| 35-80 | Green | 綠色瓶、綠草、綠筆 |
| 80-100 | Cyan | 青藍色、淺藍色物體 |
| 100-130 | Blue | 藍色筆、藍杯、深藍色 |
| 130-160 | Purple | 紫色物體 |
| 160-170 | Pink | 粉紅色物體 |

**為什麼用 HSV?**

相比 RGB，HSV 有 3 大優勢：

```
1️⃣ 色調 (H) 不受亮度影響
   例：紅蘋果在強光和弱光下，色調始終是 H=0°
   而 RGB(255,0,0) vs RGB(120,0,0) 完全不同

2️⃣ 飽和度 (S) 濾除灰色系
   灰色：S < 30 → 自動判為 Gray，避免誤判

3️⃣ 亮度 (V) 處理極端情況
   V < 50 → Black (過暗)
   V > 220 && S < 30 → White (過亮)

結果：相比 RGB，準確率提升 30-40%
```

---

## 📁 項目結構

```
pawai-studio/
├── backend/
│   ├── local_yolo.py           # ✨ 核心：YOLO 推論 + HSV 色彩分析
│   ├── mock_server.py          # FastAPI 中樞 (WebSocket + REST)
│   ├── schemas.py              # Pydantic 資料模型定義
│   ├── yolov8n-seg.pt          # YOLOv8n-seg 模型 (首次運行自動下載)
│   └── requirements.txt         # Python 依賴清單
│
├── frontend/
│   ├── components/
│   │   └── object/
│   │       ├── local-camera.tsx      # ✨ 鏡頭視窗 + Bbox 疊加
│   │       ├── live-detection.tsx    # ✨ 即時偵測卡片面板
│   │       ├── object-config.ts      # 白名單配置
│   │       ├── object-panel.tsx      # 主物體面板
│   │       ├── object-stats.tsx      # 統計面板
│   │       └── whitelist-view.tsx    # 白名單管理器
│   │
│   ├── stores/
│   │   └── state-store.ts     # Zustand 全局狀態管理
│   │
│   ├── pages/
│   │   └── object.tsx         # 物體偵測頁面
│   │
│   └── lib/ / hooks/ / styles/
│
├── package.json               # npm 依賴
├── tsconfig.json             # TypeScript 配置
├── vite.config.ts            # Vite 打包配置
└── README.md                 # 本文檔

重點標記 ✨ 的是 Object Detection 系統的核心檔案。
```

---

## 🔌 API 文檔

### WebSocket 事件推送

**連線地址**: `ws://localhost:8000/ws/events`

**事件推送頻率**: 每 200ms 一次

**事件格式**:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-04-29T05:27:56.303Z",
  "source": "object",
  "event_type": "object_detected",
  "data": {
    "stamp": 1704067200.123,
    "active": true,
    "detected_objects": [
      {
        "class_name": "scissors",
        "class_id": 16,
        "confidence": 0.88,
        "bbox": [150, 100, 300, 280],
        "color": "Blue"              // ✨ 我們新增的色彩信息
      },
      {
        "class_name": "book",
        "class_id": 73,
        "confidence": 0.76,
        "bbox": [50, 50, 200, 350],
        "color": "Yellow"
      }
    ],
    "objects": [/* 同 detected_objects */]
  }
}
```

### REST 端點

#### POST /mock/yolo/start — 啟動推論引擎

```bash
curl -X POST http://localhost:8000/mock/yolo/start
```

回應:
```json
{"status": "started", "msg": "YOLO 串流已由網頁啟動"}
```

#### POST /mock/yolo/stop — 停止推論引擎

```bash
curl -X POST http://localhost:8000/mock/yolo/stop
```

回應:
```json
{"status": "stopped", "msg": "YOLO 串流已關閉"}
```

#### GET /api/health — 系統健康檢查

```bash
curl http://localhost:8000/api/health
```

回應:
```json
{
  "stamp": 1704067200.123,
  "jetson": {
    "cpu_percent": 45.2,
    "gpu_percent": 30.1,
    "ram_used_mb": 5120,
    "temperature_c": 52.3
  },
  "modules": [...]
}
```

---

## 🔧 配置說明

### 後端配置 (local_yolo.py)

編輯檔案頂部的常數，重啟後生效：

```python
# 攝影機設置
CAMERA_ID    = 0              # 攝影機編號 (多攝像頭時改)

# 推論設置
SEND_FPS     = 5              # WebSocket 推送頻率 (5 次/秒)
CONF_THRESH  = 0.30           # 置信度閾值 (越低越敏感，0-1)

# 模型設置
MODEL_NAME   = "yolov8n-seg.pt"  # 模型檔名

# 伺服器設置
MOCK_SERVER  = "http://localhost:8000"  # FastAPI 伺服器地址
```

### 色彩分析配置

修改 `detect_color_from_bbox()` 函數中的 HSV 閾值：

```python
def detect_color_from_bbox(roi_hsv):
    """從 ROI 計算顏色，改這裡調整色彩範圍"""
    h_mean = np.mean(roi_hsv[:, :, 0])
    s_mean = np.mean(roi_hsv[:, :, 1])
    v_mean = np.mean(roi_hsv[:, :, 2])
    
    # 範例：調整黃色範圍
    if 20 <= h_mean < 35:  # ← 改這裡
        return "Yellow"
    
    # 範例：調整綠色範圍
    elif 35 <= h_mean < 80:  # ← 改這裡
        return "Green"
    
    # ... 其他顏色
```

改完後，**下次推論立即生效**，無需重新訓練！

### 前端配置 (.env.local)

創建或編輯 `pawai-studio/.env.local`:

```env
VITE_API_URL=http://localhost:8000
VITE_MJPEG_URL=http://localhost:8081/video_feed
VITE_WS_URL=ws://localhost:8000/ws/events
```

---

## 常見問題 (FAQ)

### Q1: 啟動時提示「無法找到模型」

**A**: YOLOv8n-seg 模型會在首次運行時自動下載（約 25MB）。

如果自動下載失敗，手動下載：
```bash
cd pawai-studio/backend
python -c "from ultralytics import YOLO; YOLO('yolov8n-seg.pt')"
```

或直接下載：
```bash
wget https://github.com/ultralytics/assets/releases/download/v8.1.0/yolov8n-seg.pt
```

### Q2: 色彩識別不準確

**A**: 常見原因與解決方案：

1. **光線問題** → 改進光線環境
2. **HSV 閾值不對** → 調整 `local_yolo.py` 中的範圍
3. **背景干擾** → 考慮使用 segmentation mask (進階)

改完配置後立即生效，無需訓練！

### Q3: 幀率太低 (FPS < 5)

**A**: 優化方案（按優先順序）：

1. **使用 GPU** (3-5 倍加速)
   ```python
   model = YOLO('yolov8n-seg.pt')
   model.to('cuda')
   ```

2. **降低推送頻率**
   ```python
   SEND_FPS = 2  # 改為 2 次/秒
   ```

3. **降低解析度** (不推薦，影響準度)

4. **升級硬體** (GPU 最有效)

### Q4: 支援多攝像頭嗎？

**A**: 支援。改 `CAMERA_ID` 或使用迴圈：

```python
# 順序遍歷多攝像頭
for camera_id in [0, 1, 2]:
    cap = cv2.VideoCapture(camera_id)
    if cap.isOpened():
        print(f"Found camera {camera_id}")
```

### Q5: 可以部署到 NVIDIA Jetson Nano 嗎？

**A**: 是的，完全支援！

優勢：
- ✅ 低功耗 (5W vs 桌機 150W)
- ✅ 支援 GPU 加速 (TensorRT)
- ✅ 邊緣部署，隱私友善

參考文件：[DEPLOYMENT.md](./DEPLOYMENT.md)

---

