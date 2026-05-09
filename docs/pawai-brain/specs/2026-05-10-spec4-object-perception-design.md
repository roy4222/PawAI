# Object Perception Upgrade — 設計規格

> **Status**: draft
> **Date**: 2026-05-10
> **Spec ID**: Spec 4 of 6（demo-quality roadmap）
> **Scope**: 物體辨識升級：YOLOv8n vs YOLO26n benchmark + 顏色辨識準度 + (進階) 室內資料集 fine-tune
> **執行視窗**：demo 後（demo 用現有 yolo26n + COCO 即可）
> **Owner**: Roy
> **依據**：
> - `docs/pawai-brain/perception/object/CLAUDE.md`
> - `object_perception/object_perception/object_node.py`
> - `benchmarks/configs/`（unified benchmark framework）

---

## 1. 範圍：3 件事

### 1.1 P0：YOLOv8n vs YOLO26n benchmark
- 大物件（椅子、桌子、人）+ 小物件（杯子、書、瓶子、手機）
- 距離：1m / 2m / 3m
- 指標：mAP / 小物件 recall / FPS / GPU% / RAM

### 1.2 P0：顏色辨識
- 現況：HSV 簡單判別，「咖啡色椅子」常誤判
- 改：YOLO bbox 內取 RGB 中位數 → KMeans cluster → 對應 11 種色名（紅/橙/黃/綠/藍/紫/粉/白/黑/灰/咖啡）
- 物體 cooldown 30 分鐘（同 object + 同 color）

### 1.3 P2：室內資料集（進階，demo 後再評估）
- COCO 80 class 對「家裡」覆蓋不足（鑰匙、遙控器、藥盒）
- 候選資料集：Open Images / Objects365 / 自蒐
- 風險：fine-tune 時間 + GPU 預算 + Jetson TRT 重新編

---

## 2. 非目標

❌ 不做：
- 物體 grasping / pick-up（沒手）
- 物體位置記憶（「鑰匙在哪」）
- 物體狀態判斷（杯子是空的還滿的）
- multi-class fusion（「紅色貓 + 棕色狗」）

---

## 3. Benchmark 設計

### 3.1 模型候選
| 模型 | 大小 | mAP@COCO | 備註 |
|---|---|---|---|
| YOLOv8n | 6.2M | 37.3 | baseline |
| YOLO26n | 9.5M | ~38.0 | 現用 |
| YOLO26s | ~20M | ~43.6 | （Spec 4 P1）|
| YOLO11n | ~5M | 39.5 | benchmark only |

### 3.2 測試場景
- 椅子（大）@ 1m / 2m / 3m × 3 角度
- 杯子（小）@ 1m / 2m × 顏色 4 種（紅/白/咖啡/透明）
- 書（小）@ 1m / 1.5m
- 人 @ 1m / 2m / 3m

每場景跑 30 frame，看 detect rate + bbox stability + class confidence。

### 3.3 顏色準度測試
- 標準色卡 11 色，每色 3 個物體（杯/椅/書）
- 距離 1m，正面光
- 指標：top-1 準度、top-2 準度

---

## 4. 顏色 pipeline 設計

```python
def extract_color(frame, bbox) -> str:
    crop = frame[y1:y2, x1:x2]
    # 1. 去除邊界 10% 像素（背景污染）
    crop = crop[h//10:-h//10, w//10:-w//10]
    # 2. KMeans k=3 找主色
    pixels = crop.reshape(-1, 3)
    kmeans = KMeans(3).fit(pixels)
    centers = kmeans.cluster_centers_
    counts = np.bincount(kmeans.labels_)
    dominant = centers[counts.argmax()]
    # 3. RGB → 11 色名 mapping（離散 LAB 空間）
    return rgb_to_color_name(dominant)
```

---

## 5. 驗收

### P0
- YOLOv8n vs YOLO26n：>10% 差異才考慮升級
- 小物件 (<10cm) recall ≥60%
- 顏色 top-1 ≥75%（11 色測試）
- FPS ≥6（debug_image）
- GPU% ≤95%（cooperative with face/pose）

### P2（demo 後）
- 室內資料集：家裡 10 個常見物件 detect rate ≥70%

---

## 6. 實作分階段（demo 後）

| Phase | 內容 | 工時 |
|---|---|---|
| 1 | benchmark framework 加 object_candidates.yaml | 0.5d |
| 2 | YOLOv8n / YOLO26n / YOLO11n 三向跑 | 1d |
| 3 | 顏色 pipeline + KMeans + LAB mapping | 1d |
| 4 | object_remark 變體池 + cooldown（共用 Spec 1）| 0.5d |
| 5 | 驗收 + decision report | 0.5d |
| 6 | (P2) 室內資料集評估（不一定做）| 3-5d |

**P0 總計**：3.5 天

---

## 7. 後續 spec 銜接
- Spec 1：object_remark 變體池機制是 Spec 1 SAY 解綁的延伸
- Spec 5：尋物導航（指定物體 → 走過去）依賴本 spec 的 detection
