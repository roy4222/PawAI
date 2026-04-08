# 黃旭 — 物體辨識互動設計

> **目標**：決定要辨識哪些物體、偵測到後 Go2 說什麼。用自己電腦+鏡頭測試物體辨識效果。

---

## 你的任務

1. 用自己的鏡頭跑 YOLO26n，測試哪些物品能穩定偵測
2. 決定白名單（哪些 COCO class 開啟）+ 每個物品的 TTS 回應
3. 前端 Studio `/studio/object` 頁面也要一起刻好（見 [Studio 分工](../pawai-studio/object-assignment.md)）

---

## 模型資訊

| 項目 | 值 |
|------|---|
| 模型 | **YOLO26n**（Ultralytics YOLO v12 Nano） |
| Python 套件 | `ultralytics` (pip install) |
| 資料集 | **COCO 80 class**（預訓練） |
| 運算 | CPU 可跑（Jetson 上用 TensorRT FP16 加速） |
| Jetson 效能 | 15 FPS 穩定 |
| 限制 | 小物體+低光線辨識率低 |

### COCO 80 class 完整列表（適合室內的標 ✅）

| class_id | 英文 | 中文 | 室內適用 | 實測結果 |
|:--------:|------|------|:--------:|:--------:|
| 0 | person | 人 | ✅ | |
| 24 | backpack | 背包 | ✅ | |
| 25 | umbrella | 雨傘 | ✅ | |
| 26 | handbag | 手提包 | ✅ | |
| 39 | bottle | 水瓶 | ⚠️ | ❌ 已驗證失敗 |
| 41 | cup | 杯子 | ✅ | ✅ 已驗證通過 |
| 56 | chair | 椅子 | ✅ | |
| 57 | couch | 沙發 | ✅ | |
| 60 | dining table | 桌子 | ✅ | |
| 63 | laptop | 筆電 | ✅ | |
| 64 | mouse | 滑鼠 | ⚠️ | |
| 65 | remote | 遙控器 | ❌ 太小 | |
| 66 | keyboard | 鍵盤 | ✅ | |
| 67 | cell phone | 手機 | ✅ | ✅ 已驗證通過 |
| 73 | book | 書本 | ⚠️ | ⚠️ 平放難、翻開可 |
| 74 | clock | 時鐘 | ✅ | |
| 75 | vase | 花瓶 | ✅ | |
| 76 | scissors | 剪刀 | ❌ 太小 | |

完整 80 class 清單：https://docs.ultralytics.com/datasets/detect/coco/

---

## 本機復現步驟

### 環境安裝

```bash
# Python 3.9+
pip install ultralytics opencv-python
```

> **注意**：`ultralytics` 會安裝 YOLOv8 系列。YOLO26n 是更新的版本，但 API 完全相容。
> 你先用 `yolo11n`（最新 Nano）測試，COCO class_id 和 class_name 跟 Jetson 上完全一樣。
> 如果 Roy 之後提供 `yolo26n.onnx`，你可以切換。

### 測試腳本

建一個 `test_object.py`：

```python
"""物體辨識測試 — 用你的鏡頭即時辨識物體"""
from ultralytics import YOLO
import cv2

# 載入模型（第一次跑會自動下載 ~6MB）
model = YOLO("yolo11n.pt")  # Nano 版，速度快

# COCO 中文對照
CN_NAMES = {
    "person": "人", "backpack": "背包", "umbrella": "雨傘",
    "bottle": "水瓶", "cup": "杯子", "chair": "椅子",
    "laptop": "筆電", "mouse": "滑鼠", "keyboard": "鍵盤",
    "cell phone": "手機", "book": "書本", "clock": "時鐘",
    "vase": "花瓶", "handbag": "手提包", "couch": "沙發",
    "dining table": "桌子", "remote": "遙控器",
}

cap = cv2.VideoCapture(0)
print("按 q 離開。試試看拿各種物品到鏡頭前！")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # 辨識（conf=0.3 比較寬鬆，可以調）
    results = model(frame, conf=0.3, verbose=False)

    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            cls_name = model.names[cls_id]
            conf = float(box.conf[0])
            cn_name = CN_NAMES.get(cls_name, cls_name)

            # 畫框
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            color = (0, 255, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            label = f"{cn_name} {conf:.0%}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            print(f"  {cn_name} (class {cls_id}) {conf:.0%}")

    cv2.imshow("Object Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 測試要點

- 鏡頭放桌上，高度 **~30cm**（模擬 Go2 視角）
- **開燈！** 光線不足小物體幾乎無法辨識
- 每種物品測 10 次：遠/近/正面/側面/不同光線
- 記錄：哪些物品穩定（>70%）、哪些不穩定、哪些完全不行
- 注意物體角度：平放 vs 立起來差很多（書本就是這樣）

---

## 參考程式碼（Jetson 上的實際程式）

| 檔案 | 說明 |
|------|------|
| `object_perception/object_perception/object_perception_node.py` | 物體辨識 ROS2 節點 |
| `object_perception/object_perception/yolo_detector.py` | YOLO 偵測器 |
| `interaction_executive/interaction_executive/state_machine.py` | 物體→TTS 映射 |

---

## 目前的映射（只有 1 個）

| 物體 | TTS 語音 | 備註 |
|------|---------|------|
| cup（杯子） | 「你要喝水嗎？」 | ✅ 穩定 |
| 其他所有物體 | **什麼都不說** | |

---

## 請填這個映射表（交給 Roy）

| 物體 | COCO class_id | 開啟? | TTS 語音（Go2 要說什麼） | Go2 動作 | 備註 |
|------|:------------:|:-----:|----------------------|---------|------|
| cup（杯子） | 41 | ✅ | 「你要喝水嗎？」 | — | 已驗證 |
| cell phone（手機） | 67 | ? | ? | ? | 已驗證可偵測 |
| book（書本） | 73 | ? | ? | ? | 翻開才偵測得到 |
| backpack（背包） | 24 | ? | ? | ? | |
| laptop（筆電） | 63 | ? | ? | ? | |
| chair（椅子） | 56 | ? | ? | ? | 太常見，要不要忽略？ |
| person（人） | 0 | ? | ? | ? | 人臉模組已處理 |
| ＿＿ | ? | ? | ? | ? | 你想加的 |

**冷卻時間**：目前每個 class 有 5 秒冷卻，避免重複觸發。

---

## 已知限制

- **光線不足時小物體幾乎無法辨識** — Demo 必須開燈
- 物體需在一定高度且正對攝影機角度
- **YOLO26n 是 Nano 版**（9.5MB），小物件偵測率低，大物件沒問題
- 平放的扁平物體（書本、手機平放）辨識困難
- Demo 時建議用大物品 + 手持展示（不要放桌上）
- 水瓶 (bottle) 已確認偵測不到，不要列入展示

---

## 交付方式

1. 測試報告：每種物品的辨識率（10 次中幾次成功，不同光線/角度）
2. 填好的白名單 + TTS 映射表
3. Studio `/studio/object` 頁面 PR

**deadline**：4/13 前映射表 + Studio 頁面
