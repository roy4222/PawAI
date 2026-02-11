# Depth Anything V2 安裝與使用指南

**適用環境**：學校 GPU 伺服器 (RTX 8000 48GB)  
**最後更新**：2025/12/14

---

## 1. 環境設定

### 連接資料夾

```bash
cd ~/Depth_Anything_V2
cd Depth-Anything-V2
```

### 啟動 Conda 環境

```bash
conda activate depth-v2
```

---

## 2. 安裝依賴

> ⚠️ **專案規範**：必須使用 `uv pip install` 而非 `pip install`

### PyTorch (CUDA 12.4 版本)

```bash
uv pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

> 💡 這會安裝支援 CUDA 12.4 的 PyTorch，能在 CUDA 13.0 驅動上運行

### 其他依賴

```bash
uv pip install -r requirements.txt
```

---

## 3. 下載模型權重

> ⚠️ **注意**：三個 checkpoint 約 3-4 GB，確認有足夠磁碟空間與下載權限
> 網路不穩時可先線下下載再同步上傳

### 相對深度模型 (Relative Depth) ~1.3GB

```bash
mkdir -p checkpoints
wget -O checkpoints/depth_anything_v2_vitl.pth \
  https://huggingface.co/depth-anything/Depth-Anything-V2-Large/resolve/main/depth_anything_v2_vitl.pth
```

### Metric Depth 模型（真實距離）

**室內場景 (Indoor) - 最大 20m** ~1.3GB
```bash
wget -O checkpoints/depth_anything_v2_metric_hypersim_vitl.pth \
  https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-Hypersim-Large/resolve/main/depth_anything_v2_metric_hypersim_vitl.pth
```

**室外場景 (Outdoor) - 最大 80m** ~1.3GB
```bash
wget -O checkpoints/depth_anything_v2_metric_vkitti_vitl.pth \
  https://huggingface.co/depth-anything/Depth-Anything-V2-Metric-VKITTI-Large/resolve/main/depth_anything_v2_metric_vkitti_vitl.pth
```

---

## 4. 基本使用

### CLI 執行

```bash
# 圖片
python run.py --encoder vitl --img-path assets/examples --outdir outputs

# 影片
python run_video.py --encoder vitl --video-path video.mp4 --outdir video_output
```

---

## 5. Python API 使用

### 5.1 相對深度 (Relative Depth)

建立 `test_depth.py`：

```python
import cv2
import torch
import numpy as np
import time
from depth_anything_v2.dpt import DepthAnythingV2

IMAGE_PATH = "assets/examples/demo01.jpg"

def main():
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    model_configs = {
        'vitl': {'encoder': 'vitl', 'features': 256, 'out_channels': [256, 512, 1024, 1024]},
    }
    
    model = DepthAnythingV2(**model_configs['vitl'])
    model.load_state_dict(torch.load('checkpoints/depth_anything_v2_vitl.pth', map_location='cpu'))
    model = model.to(DEVICE).eval()

    raw_img = cv2.imread(IMAGE_PATH)
    
    t_start = time.time()
    depth = model.infer_image(raw_img)
    print(f"推論時間: {time.time() - t_start:.4f} 秒")
    
    print(f"深度範圍: {depth.min():.4f} ~ {depth.max():.4f}")
    print(f"中心點深度: {depth[depth.shape[0]//2, depth.shape[1]//2]:.4f}")

if __name__ == '__main__':
    main()
```

### 5.2 Metric Depth（真實距離，公尺）

建立 `test_metric.py`：

```python
import sys
sys.path.insert(0, 'metric_depth')

import cv2
import torch
import numpy as np
import time
from depth_anything_v2.dpt import DepthAnythingV2

IMAGE_PATH = "assets/examples/demo01.jpg"
SCENE_TYPE = 'indoor'  # 'indoor' 或 'outdoor'

def main():
    DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    if SCENE_TYPE == 'indoor':
        dataset, max_depth = 'hypersim', 20.0
    else:
        dataset, max_depth = 'vkitti', 80.0
    
    model_configs = {
        'vitl': {'encoder': 'vitl', 'features': 256, 'out_channels': [256, 512, 1024, 1024]},
    }
    
    model = DepthAnythingV2(**{**model_configs['vitl'], 'max_depth': max_depth})
    model.load_state_dict(
        torch.load(f'checkpoints/depth_anything_v2_metric_{dataset}_vitl.pth', map_location='cpu'),
        strict=False
    )
    model = model.to(DEVICE).eval()

    raw_img = cv2.imread(IMAGE_PATH)
    
    t_start = time.time()
    depth = model.infer_image(raw_img)
    print(f"推論時間: {time.time() - t_start:.4f} 秒")
    
    H, W = depth.shape
    print(f"最近距離: {depth.min():.2f} m")
    print(f"最遠距離: {depth.max():.2f} m")
    print(f"中心點距離: {depth[H//2, W//2]:.2f} m")

if __name__ == '__main__':
    main()
```

---

## 6. 距離校正（Scale Calibration）

> ⚠️ 單鏡頭估距有「尺度模糊 (Scale Ambiguity)」問題，**必須校正**

### 校正流程

1. **準備標靶**：在 1m, 2m, 3m 位置放置物體（用捲尺量）
2. **拍照測試**：執行 `test_metric.py`
3. **計算係數**：`scale_factor = 實際距離 / 模型輸出`
4. **套用校正**：`depth = depth * scale_factor`

### 校正記錄表

| 實際距離 | 模型輸出 | 校正係數 | 校正後 |
|---------|---------|---------|--------|
| 1.0 m | ___ m | | |
| 2.0 m | ___ m | | |
| 3.0 m | ___ m | | |
| **平均** | | **___** | |

### 注意事項

- ✅ **統一輸入解析度**：固定使用 640x480，避免不同解析度導致比例漂移
- ✅ **相機內參**：若擛入參數變更，需重新校正
- ✅ **場景一致**：室內用 `hypersim`，室外用 `vkitti`

---

## 7. 深度取樣技巧

> 💡 **不要用單點或平均值！** 背景會把距離拉大

### 推薦方法：分位數取樣

```python
import numpy as np

def get_object_distance(depth_map, bbox, percentile=15):
    """
    從 bbox 區域取得物體距離
    使用 10-20% 分位數避免背景干擾
    """
    x1, y1, x2, y2 = bbox
    roi = depth_map[y1:y2, x1:x2]
    
    # 用分位數而非平均值
    distance = np.percentile(roi, percentile)
    return distance

def get_region_depths(depth_map, percentile=10):
    """左/中/右區域深度摘要"""
    H, W = depth_map.shape
    
    left_roi = depth_map[:, :W//3]
    center_roi = depth_map[H//4:3*H//4, W//3:2*W//3]  # 中心區域更小
    right_roi = depth_map[:, 2*W//3:]
    
    return {
        "left_m": np.percentile(left_roi, percentile),
        "center_m": np.percentile(center_roi, percentile),
        "right_m": np.percentile(right_roi, percentile),
    }
```

### 輸出格式

```python
{
    "distance_m": 0.85,      # 距離（公尺）
    "direction": "center",   # 方位：left/center/right
    "confidence": 0.92       # 信心度（如有 YOLO）
}
```

---

## 8. 效能參考與優化

| 項目 | 數值 | 備註 |
|------|------|------|
| 推論時間 (vitl) | ~0.38 秒 | RTX 8000 |
| VRAM 使用 | ~6 GB | "|
| 輸出解析度 | 與輸入相同 | |

### ⚙️ 優化建議

若 DA3 + YOLO 串行超過 500ms SLA：

| 方案 | 優化效果 | 缺點 |
|------|---------|------|
| 降解析度 640x480 | 加快 ~30% | 細節減少 |
| 換 vitb 模型 | 加快 ~50% | 精度稍降 |
| 預載權重 | 避免冷啟延遲 | 必做 |
| 並行推理 | 充分利用 GPU | 需調整程式碼 |

```python
# 預載權重範例（FastAPI 啟動時）
@app.on_event("startup")
async def load_models():
    global depth_model, yolo_model
    depth_model = load_da3().cuda().eval()
    yolo_model = load_yolo_world()
    # 暫熱一次
    _ = depth_model.infer_image(dummy_image)
```

---

## 8. 相關資源

- [官方 GitHub](https://github.com/DepthAnything/Depth-Anything-V2)
- [HuggingFace 模型](https://huggingface.co/depth-anything)
- [Depth Anything V3 (最新)](https://github.com/ByteDance-Seed/Depth-Anything-3)

---

## 9. 替代方案

| 模型 | 特點 | 適用場景 |
|------|------|---------|
| **ZoeDepth** | 不需校正的 Metric Depth | 需要開箱即用的精確距離 |
| **Marigold** | 細節極強（基於 Stable Diffusion） | 需要高畫質深度圖（但較慢） |

---

## 10. 專題整合測試計畫

### 10.1 測試目標

將 Depth Anything V2 (Metric) 整合至 Go2 機器狗尋物系統，提升避障成功率從 50-60% 至 **80%+**。

### 10.2 測試項目

| 編號 | 測試項目 | 預期結果 | 驗收標準 |
|------|---------|---------|---------|
| T1 | **模型載入測試** | GPU 正常載入 | 無錯誤，VRAM < 10GB |
| T2 | **推論速度測試** | 單張圖片推理完成 | **< 500ms** |
| T3 | **距離精度測試** | 1m, 2m, 3m 標準距離量測 | 校正後誤差 < 20% |
| T4 | **區域深度摘要** | 左/中/右區分位數深度 | 正確識別障礙方位 |
| T5 | **FastAPI Server 測試** | `/perceive` 端點正常回應 | HTTP 200 + JSON |
| T6 | **ROS2 整合測試** | `/perception_context` 正常發布 | Hz > 0.5 |
| T7 | **避障成功率測試** | 機器狗繞開正前方障礙物 | **5 次中 4 次成功** |

> ⚠️ **T7 必須包含**：失敗重試 / timeout (5s) / fallback 至純視覺路徑

### 10.3 詳細測試步驟

#### T1: 模型載入測試

```bash
cd ~/Depth_Anything_V2/Depth-Anything-V2
conda activate depth-v2
python -c "
import torch
from depth_anything_v2.dpt import DepthAnythingV2
model = DepthAnythingV2(encoder='vitl', features=256, out_channels=[256,512,1024,1024], max_depth=20.0)
model.load_state_dict(torch.load('checkpoints/depth_anything_v2_metric_hypersim_vitl.pth'), strict=False)
model = model.cuda().eval()
print('✅ 模型載入成功')
print(f'VRAM: {torch.cuda.memory_allocated()/1e9:.2f} GB')
"
```

#### T3: 距離精度測試

1. 在已知距離放置物體（用捲尺量）
2. 拍照並執行 `test_metric.py`
3. 記錄結果：

| 實際距離 | 模型輸出 | 誤差 | 校正係數 |
|---------|---------|------|---------|
| 1.0 m | ___ m | ___ % | |
| 2.0 m | ___ m | ___ % | |
| 3.0 m | ___ m | ___ % | |

#### T4: 區域深度摘要測試

```python
def get_region_depths(depth_map):
    H, W = depth_map.shape
    left = depth_map[:, :W//3].min()
    center = depth_map[:, W//3:2*W//3].min()
    right = depth_map[:, 2*W//3:].min()
    return {
        "左側最近": f"{left:.2f}m",
        "中央最近": f"{center:.2f}m", 
        "右側最近": f"{right:.2f}m"
    }
```

### 10.4 預期成果

| 指標 | 目前 | 目標 |
|------|------|------|
| 避障成功率 | 50-60% | **80%+** |
| 感知延遲 | N/A | < 1 秒 |
| 距離誤差 | N/A | < 30% |

### 10.5 測試時程

| 日期 | 測試項目 |
|------|---------|
| 12/14-15 | T1, T2, T3 (GPU 伺服器) |
| 12/16 | T4, T5 (FastAPI Server) |
| 12/17 | T6 (ROS2 整合) |
| 12/20-21 | T7 (實機避障) |

---

## 11. 與 YOLO-World 整合

### 整合架構

```
相機圖片 ──┬──► YOLO-World ──► 物件偵測 (類別 + bbox)
           │
           └──► DA3 Metric ──► 深度圖 (公尺)
                      │
                      ▼
              Context Builder ──► 「前方 0.8m 有紙箱」
```

### 偵測類別

```python
DETECT_CLASSES = ["水瓶", "眼鏡", "藥盒", "椅子", "桌子", "紙箱", "人"]
```

### 摘要輸出格式

```
[環境感知摘要]
- 正前方 0.8m：紙箱（障礙物）
- 右側 2.3m：水瓶（目標）
- 左側暢通
⚠️ 建議：向左繞行
```

