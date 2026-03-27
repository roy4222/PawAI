# 人臉辨識 Reference

> 最後更新：2026-03-18
> 狀態：**USABLE** — Jetson smoke passed 2026-03-18（D435 + state/event/debug_image 全通）

## 模組定位

**P0 核心功能**，純本地推理，無雲端依賴。負責人臉偵測、追蹤、身份識別、深度估計。

## 權威文件

| 文件 | 用途 |
|------|------|
| `docs/人臉辨識/README.md` | 故障排除與啟動指南 |
| `docs/architecture/contracts/interaction_contract.md` §3.1, §4.1-4.2 | ROS2 topic schema（v2.1） |
| `docs/Pawai-studio/event-schema.md` §1.2, §2.1 | Studio 前端 event/state schema |

## 技術棧

| 組件 | 技術 | 備註 |
|------|------|------|
| 偵測器 | YuNet (ONNX) | **必須用 legacy 版**，2023mar 在 Jetson OpenCV 4.5.4 崩潰 |
| 識別器 | SFace (ONNX) | 128 維 cosine similarity |
| 深度攝影機 | Intel RealSense D435 | RGB-D aligned |
| 人臉資料庫 | SFace embeddings pickle | `/home/jetson/face_db/model_sface.pkl` |

## 核心程式

| 檔案 | 用途 |
|------|------|
| `scripts/face_identity_infer_cv.py` | 主推理腳本（CLI 驅動） |
| `scripts/face_identity_enroll_cv.py` | 人臉註冊工具 |

## ROS2 介面

**State**：`/state/perception/face`（10 Hz）
```json
{
  "stamp": 1773926400.789,
  "face_count": 1,
  "tracks": [{
    "track_id": 1, "stable_name": "Roy", "sim": 0.42,
    "distance_m": 1.25, "bbox": [100, 150, 200, 280], "mode": "stable"
  }]
}
```

**Event**：`/event/face_identity`（觸發式，4 種 event_type）

| event_type | 觸發條件 |
|-----------|----------|
| `track_started` | 新 track_id 首次出現 |
| `identity_stable` | Hysteresis 穩定化達標（stable_hits=3） |
| `identity_changed` | 同 track_id 的 stable_name 變更 |
| `track_lost` | 連續 max_misses 幀未匹配 |

## 已知陷阱

- YuNet **必須用 legacy 版本**（Jetson OpenCV 4.5.4 限制）
- 人臉資料庫必須在 `/home/jetson/face_db/`，結構為 `{person_name}/*.png`
- Hysteresis 穩定化需 ~0.3 秒（3 幀確認 + 置信度遲滯 0.35/0.25）
- 不可同時跑多個 `face_identity_infer_cv.py`（相機裝置忙碌）
- `distance_m` 可能為 null（超出深度範圍）

## 啟動流程（Jetson）

```bash
# Terminal A：相機
ros2 launch realsense2_camera rs_launch.py \
  depth_module.profile:=640x480x30 rgb_camera.profile:=640x480x30 align_depth.enable:=true

# Terminal B：人臉辨識
python3 scripts/face_identity_infer_cv.py \
  --db-dir /home/jetson/face_db \
  --yunet-model /home/jetson/face_models/face_detection_yunet_2023mar.onnx \
  --sface-model /home/jetson/face_models/face_recognition_sface_2021dec.onnx \
  --publish-fps 8 --no-publish-compare-image --headless
```

## 驗證

```bash
ros2 topic echo /state/perception/face    # 應有 10Hz JSON
ros2 topic echo /event/face_identity      # 走近 → track_started → identity_stable → 離開 → track_lost
```

## 當前狀態

- 偵測 + 追蹤 + 識別 MVP 穩定
- state/event topic 已對齊 interaction_contract v2.1
- QoS 已修正（RELIABLE → BEST_EFFORT for D435 camera，3/23）
- YuNet default 已從 legacy 改為 2023mar（3/25）
- `face_perception` ROS2 package 已完成，Clean Architecture 重構為中期目標
