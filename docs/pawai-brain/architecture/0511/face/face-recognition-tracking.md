# Face Recognition And Tracking

## Pipeline

```text
RGB frame
  │
  ▼
YuNet detect
  │ bbox + landmarks
  ▼
SFace alignCrop
  │ 112x112 aligned face
  ▼
SFace feature
  │ 128-D embedding
  ▼
Face DB cosine similarity
  │ raw_name + raw_sim
  ▼
IOU tracking
  │ track_id
  ▼
Stable identity hysteresis
  │ stable_name + sim + mode
  ▼
Depth ROI median
  │ distance_m
  ▼
state/event JSON
```

## Model Files

Jetson 實機使用固定路徑：

```text
/home/jetson/face_models/face_detection_yunet_2023mar.onnx
/home/jetson/face_models/face_recognition_sface_2021dec.onnx
```

選型原因：
- YuNet 跑 CPU，避免搶 pose / object / gesture 的 GPU。
- SFace 可直接用 OpenCV `FaceRecognizerSF`，部署最少。
- 2023mar 版 YuNet 是實機可用版本，舊版有 OpenCV dynamic shape 相容問題。

## Face DB

資料夾：

```text
/home/jetson/face_db/
├── roy/
│   ├── roy_0000.png
│   └── ...
├── grama/
│   └── ...
└── model_sface.pkl
```

`model_sface.pkl` 結構：

```python
{
    "embeddings": {"roy": [emb1, emb2, ...]},
    "centroids": {"roy": mean_embedding},
    "counts": {"roy": 30}
}
```

啟動時會計算各人名資料夾 PNG 數量。如果 counts 跟 pickle 裡不同，`face_identity_node` 會自動重訓並覆寫 `model_sface.pkl`。所以註冊新照片後，最簡單的重訓方式是重啟 face node。

## Similarity 判定

位置：

```text
face_perception/face_perception/face_identity_node.py
  cosine_similarity()
  predict_name()
  decide_stable_name()
```

比對邏輯：

```text
對每個 person:
  若有 samples，取 frame embedding 和所有 sample 的最大 cosine similarity
  否則和 centroid 比

最高分者成為 raw_name/raw_sim
```

Jetson YAML threshold：

| 參數 | 值 | 意義 |
|------|----|------|
| `sim_threshold_upper` | `0.40` | 高於此值才提出人名，5/8 收緊以減少陌生人誤判 |
| `sim_threshold_lower` | `0.22` | 低於此值直接 unknown |
| 中間帶 | `0.22-0.40` | 沿用前一個 stable identity |

這是雙閾值 hysteresis，不是單純 `sim > x`。它的目的是讓臉短暫模糊、轉頭、光線變化時不立刻掉成 unknown。

## Stable Identity

每個 track 會有一份狀態：

```python
{
    "candidate_name": "unknown",
    "candidate_hits": 0,
    "last_stable_name": "unknown",
    "last_stable_sim": -1.0,
    "last_known_ts": 0.0,
}
```

Jetson YAML：

| 參數 | 值 | 意義 |
|------|----|------|
| `stable_hits` | `2` | 連續兩次 proposed name 一致才鎖定 |
| `unknown_grace_s` | `2.5` | 已知人短暫掉信心時保留身份 |

事件觸發點：
- `old_stable_name == "unknown"` 且變成 known：發 `identity_stable`。
- known 變成另一個 stable name：發 `identity_changed`。
- track 消失：發 `track_lost`。

## IOU Tracking

位置：

```text
FaceIdentityNode.assign_tracks()
FaceIdentityNode.bbox_iou()
```

Jetson YAML：

| 參數 | 值 | 意義 |
|------|----|------|
| `track_iou_threshold` | `0.15` | bbox 和舊 track IOU 大於此值才沿用 track_id |
| `track_max_misses` | `20` | 連續 20 次 tick 未匹配才丟掉 track |
| `max_faces` | `5` | 每幀最多處理 5 張臉 |

限制：
- 這不是 DeepSORT，也沒有跨離場 re-ID。
- 人離開再回來會是新的 `track_id`。
- 多人交錯時 bbox 可能互竄，尤其 D435 畫面窄、臉小、側身時。

## 距離估計

位置：

```text
face_identity_node.py tick()
```

算法：

```python
roi = depth[y1:y2, x1:x2]
valid = roi[(roi > 0) & (roi < 10000)]
distance_m = median(valid) * 0.001
```

輸出：

```json
"distance_m": 1.25
```

目前用途：
- Executive 的 `AttentionMachine` 用距離判斷 `ENGAGED`。
- 已經足夠支撐「人是否靠近並停留」。

尚未完成：
- 沒有把 face distance 接到導航避障。
- 沒有做多人最近人排序，Brain 端只取第一個 known track。
- depth ROI 若包含背景，距離會偏遠；若臉部深度空洞，會是 `null`。

## 實機參數總表

| 參數 | Jetson YAML |
|------|-------------|
| `det_score_threshold` | `0.35` |
| `min_face_area_ratio` | `0.001` |
| `track_iou_threshold` | `0.15` |
| `track_max_misses` | `20` |
| `stable_hits` | `2` |
| `unknown_grace_s` | `2.5` |
| `sim_threshold_upper` | `0.40` |
| `sim_threshold_lower` | `0.22` |
| `publish_compare_image` | `false` |
| `headless` | `true` |
| `publish_fps` | `8.0` |
