# Vision Perception Skeleton Design

**日期**：2026-03-18
**狀態**：Draft
**目標**：建立 gesture + pose 的 4/13 demo pipeline 最小骨架

---

## Context

face_perception 已落地為 ROS2 package，今日進行 Jetson smoke test。手勢/姿勢辨識目前只有設計文件和前端佔位，沒有 runnable pipeline。需要在不衝突 Jetson 人臉測試的前提下，建立可測的骨架。

**核心約束**：
- Jetson 同時間只允許一組視覺 pipeline 實測
- 所有測試先接 Foxglove，穩定後再接 PawAI Studio → Go2
- frozen contract 不能動
- 開發用 subagent 並行，以 package 邊界隔離

---

## Architecture

```
4/13 Demo 當天：

realsense_node → /camera/color/image_raw + /camera/aligned_depth_to_color/image_raw
  ├── face_identity_node        → /event/face_identity + /state/perception/face（現有，不動）
  └── vision_perception_node    → /event/gesture_detected + /event/pose_detected（新建）
```

face 用 YuNet+SFace，gesture+pose 用 RTMPose wholebody。兩者獨立 process，共享 camera topic。

---

## Package Structure

```
vision_perception/
  vision_perception/
    __init__.py
    vision_perception_node.py     # ROS2 node（Layer 2）
    gesture_classifier.py         # 純 Python 單幀分類（Layer 1）
    pose_classifier.py            # 純 Python 單幀分類（Layer 1）
    event_builder.py              # 共用 JSON builder
    inference_adapter.py          # 推理介面（ABC）
    mock_inference.py             # Mock 實作
    mock_event_publisher.py       # 獨立 mock node
  config/
    vision_perception.yaml
  launch/
    vision_perception.launch.py
    mock_publisher.launch.py
  test/
    test_gesture_classifier.py
    test_pose_classifier.py
    test_event_builder.py
  setup.py
  package.xml
```

---

## Layer 1: Classifiers

**設計原則**：純單幀判定，不管狀態。Temporal smoothing / hysteresis buffer 由 node 管理。

### gesture_classifier.py

```python
# classifier 的可能回傳值（不含 "wave"）
STATIC_GESTURES = ("stop", "point", "fist")

def classify_gesture(
    hand_kps: np.ndarray,       # (21, 2) COCO-WholeBody hand keypoints
    hand_scores: np.ndarray,    # (21,) confidence per keypoint
) -> tuple[str | None, float]:
    """單幀靜態手勢判定。
    回傳 ("stop" | "point" | "fist", confidence) 或 (None, 0.0)。
    不回傳 "wave" — wave 需要時序，由 Node 層從連續 stop 幀 + 手腕 x 反轉偵測產出。
    不做 temporal smoothing — 由 caller 負責。
    """
```

**分類規則**（rule-based，不需訓練）：
- **stop**：五指展開，所有指尖到手腕距離 > 閾值
- **point**：食指伸展，其他指彎曲
- **fist**：所有指尖靠近手掌（MCP 距離 < 閾值）
- **wave**：**classifier 不回傳 wave**。Node 層偵測連續 stop 幀中手腕 x 座標反轉 ≥2 次 → 升級為 wave

**雙手使用策略**：Node 層對 left_hand 和 right_hand 分別呼叫 `classify_gesture`，取 confidence 較高者作為該幀結果，並記錄 hand = "left" | "right" 用於 event。Phase 1 mock 測試下只模擬單手。

### pose_classifier.py

```python
POSES = ("standing", "sitting", "crouching", "fallen")

def classify_pose(
    body_kps: np.ndarray,       # (17, 2) COCO body keypoints
    body_scores: np.ndarray,    # (17,) confidence per keypoint
    bbox_ratio: float | None,   # width/height（跌倒偵測用，由 Node 傳入）
) -> tuple[str | None, float]:
    """單幀姿勢判定。混合法：角度 + 高度比。
    fallen 優先判斷（安全功能）。
    不覆蓋的閾值區間回傳 (None, 0.0)，由 Node 層保持上一穩定狀態。
    """
```

**分類規則**（依優先序，第一個命中即回傳）：
1. **fallen**（優先，安全功能）：bbox_ratio > 1.0 且 trunk_angle > 60°
2. **standing**：hip_angle > 160° 且 knee_angle > 160°
3. **crouching**：hip_angle < 80° 且 knee_angle < 80°
4. **sitting**：70° < hip_angle < 130° 且 trunk_angle < 30°
5. **fallback**：以上皆不符 → 回傳 `(None, 0.0)`，Node 層保持上一個穩定狀態

**bbox_ratio 計算責任**：由 Node 層從 detector bbox 或 keypoint bounding box 計算後傳入，classifier 不自行計算。

### 單元測試

每個 classifier 至少覆蓋：
- 每種分類結果各一組 mock keypoints
- 邊界值（例如 hip_angle ≈ 160°）
- keypoint 全零 / NaN 的 graceful handling

---

## Shared Event Builder

```python
# event_builder.py
GESTURE_COMPAT_MAP = {"fist": "ok"}  # v2.0 契約相容層

def build_gesture_event(gesture: str, confidence: float, hand: str) -> dict:
    """產生 /event/gesture_detected JSON payload。
    stamp 自動填入（time.time()）。event_type hard-coded。
    自動套用 GESTURE_COMPAT_MAP（實作用 fist，對外發 ok）。
    """
    return {
        "stamp": time.time(),                                    # auto
        "event_type": "gesture_detected",                        # hard-coded
        "gesture": GESTURE_COMPAT_MAP.get(gesture, gesture),     # compat layer
        "confidence": round(confidence, 4),
        "hand": hand,                                            # "left" | "right"
    }

def build_pose_event(pose: str, confidence: float, track_id: int = 0) -> dict:
    """產生 /event/pose_detected JSON payload。
    track_id 預設 0 = 未追蹤。contract 允許無法對應時使用。
    """
    return {
        "stamp": time.time(),                                    # auto
        "event_type": "pose_detected",                           # hard-coded
        "pose": pose,
        "confidence": round(confidence, 4),
        "track_id": track_id,                                    # 0 = no tracking
    }
```

以上 JSON 結構逐欄對齊 `interaction_contract.md` v2.0 §4.3 / §4.4。

mock_event_publisher 和 vision_perception_node 都 import 這個模組，保證 JSON 格式一致。

---

## Inference Adapter

```python
# inference_adapter.py
class InferenceAdapter(ABC):
    @abstractmethod
    def infer(self, image_bgr: np.ndarray) -> InferenceResult:
        """回傳標準化 keypoints。"""

@dataclass
class InferenceResult:
    body_kps: np.ndarray          # (17, 2)
    body_scores: np.ndarray       # (17,)
    left_hand_kps: np.ndarray     # (21, 2)
    left_hand_scores: np.ndarray  # (21,)
    right_hand_kps: np.ndarray    # (21, 2)
    right_hand_scores: np.ndarray # (21,)
```

### mock_inference.py

```python
class MockInference(InferenceAdapter):
    """回傳可配置的假 keypoints。
    scenario 參數：'standing_idle', 'sitting', 'fallen', 'wave', 'stop', 'fist' 等。
    用於開發機測試 node pipeline，不需要 GPU。
    """
```

### Phase 2（未來）：RTMPoseInference

```python
# 未來由 Phase 2 實作，今天不寫
class RTMPoseInference(InferenceAdapter):
    def __init__(self, model_path: str, backend: str = 'onnxruntime', device: str = 'cuda'):
        # rtmlib.Wholebody(...)
```

**關鍵約束**：Phase 2 只替換 inference adapter，不改 classifier 輸出格式或 topic schema。

---

## Layer 2: ROS2 Node

### vision_perception_node.py

```python
class VisionPerceptionNode(Node):
    # 參數：
    #   inference_backend: "mock" | "rtmpose"（Phase 2）
    #   publish_fps: 8.0          ← 控制 debug_image 發布頻率，不影響 event（event 是觸發式）
    #   tick_period: 0.05         ← 主迴圈頻率（20Hz）
    #   color_topic, depth_topic
    #   gesture_vote_frames: 5
    #   pose_vote_frames: 20
    #   mock_scenario: "standing_idle"

    # 訂閱：camera color（+ depth optional）
    # Publisher（QoS: Reliable, Volatile, depth=10 — 對齊 contract v2.0 §8.2）：
    #   /event/gesture_detected   (String JSON) — v2.0 凍結，觸發式（狀態變化時）
    #   /event/pose_detected      (String JSON) — v2.0 凍結，觸發式（狀態變化時）
    #   /vision_perception/debug_image (Image BGR8) — 帶 keypoint overlay，受 publish_fps 控制

    # Temporal smoothing（node 層管理，不在 classifier 裡）：
    #   gesture_buffer: deque(maxlen=5)
    #   pose_buffer: deque(maxlen=20)
    #   只在 majority vote 結果「變化」時發 event
    #   classifier 回傳 None 時不加入 buffer（保持上一穩定狀態）

    # Wave 偵測（node 層，不在 classifier 裡）：
    #   追蹤連續 stop 幀中手腕 x 座標，偵測反轉 ≥2 次 → 發 wave event
    #   Phase 1 mock 下此邏輯可測 buffer 投票，但無法模擬真實 wave 時序

    # 雙手策略：
    #   對 left_hand / right_hand 分別呼叫 classify_gesture
    #   取 confidence 較高者，記錄 hand = "left" | "right"

    # 錯誤處理（參考 face_identity_node.py 行 446-463, 481-484）：
    #   shutting_down flag + rclpy.ok() 檢查
    #   safe_publish: try/except 包 debug_image publish
    #   camera 斷流：tick 中 color is None 時 early return
    #   inference 例外：try/except 包推理呼叫，log warning 不 crash
```

### mock_event_publisher.py

```python
class MockEventPublisher(Node):
    """完全繞過 inference + classifier，直接用 event_builder 發假事件。
    用途：前端開發（Studio GesturePanel / PosePanel）。
    不與 vision_perception_node 混用 — 兩條獨立路徑。

    場景序列（可配置）：
    idle(3s) → wave(2s) → stop(2s) → point(2s) → fist(2s)
    → standing(3s) → sitting(2s) → crouching(2s) → fallen(2s) → 循環
    """
```

---

## ROS2 Topics

### Phase 1 必做

| Topic | Schema 來源 | QoS | 頻率 | 狀態 |
|-------|------------|-----|------|------|
| `/event/gesture_detected` | contract v2.0 §4.3 | Reliable, Volatile, depth=10 | 觸發式 | **凍結** |
| `/event/pose_detected` | contract v2.0 §4.4 | Reliable, Volatile, depth=10 | 觸發式 | **凍結** |
| `/vision_perception/debug_image` | 內部 | Best-effort, depth=1 | publish_fps | 內部 |

### Phase 1 可延後

| Topic | 理由 |
|-------|------|
| `/state/perception/gesture` | v2.1 proposal，非 blocker |
| `/state/perception/pose` | v2.1 proposal，非 blocker |

---

## Foxglove 整合

所有 debug_image + event topic 透過 foxglove_bridge 暴露（port 8765）。
與 face_perception 共用同一個 bridge instance。
驗收方式：Foxglove Studio 打開看到 keypoint overlay + Raw Messages 看到正確 JSON。

---

## 並行開發分工

| 工作 | 負責 | 碰什麼檔案 | Jetson |
|------|------|-----------|--------|
| Subagent A | gesture_classifier.py, pose_classifier.py, test/test_gesture_classifier.py, test/test_pose_classifier.py | **不碰** event_builder, node, launch, mock | 不用 |
| Subagent B | vision_perception_node.py, event_builder.py, mock_*.py, inference_adapter.py, launch/, config/, setup.py, package.xml, test/test_event_builder.py | **不碰** classifier 函式簽名 | 不用 |
| 你 + 主 session | face_perception Jetson smoke | face_perception/（只讀）、Jetson 環境 | 獨佔 |

**硬規則**：
- Subagent A 不 import event_builder，不碰 ROS2，測試直接用 `np.ndarray` 建構 mock keypoints（不 import InferenceResult）
- Subagent B 不改 classifier 函式簽名，擁有 test_event_builder.py
- 兩者共享介面 = classifier 的函式簽名 + InferenceResult dataclass（在 spec 裡凍結）

### Mock 路徑對照

| 路徑 | 輸入 | 經過 | 輸出 | 用途 |
|------|------|------|------|------|
| mock_inference | Camera topic | Node + classifier + 假 keypoints | event topics + debug_image | 測試整條 pipeline |
| mock_event_publisher | 無 | 直接 event_builder | event topics（無 debug_image） | 前端開發，不需 camera |

---

## Phase 分界

### Phase 1（今天）
- vision_perception ROS2 package skeleton
- gesture_classifier + pose_classifier（純 Python + 單元測試）
- event_builder（共用 JSON builder + GESTURE_COMPAT_MAP）
- inference_adapter ABC + MockInference
- vision_perception_node（接 mock inference）
- mock_event_publisher（給前端用）
- debug_image publisher
- /event/gesture_detected + /event/pose_detected

### Phase 2（Jetson 部署，人臉 smoke 完成後）
- RTMPoseInference adapter（rtmlib + onnxruntime-gpu）
- 替換 mock → 真實推理
- FPS / 記憶體 benchmark
- 與 face_identity_node 共存測試

### Phase 3（整合）
- Foxglove 驗證 → PawAI Studio 串接
- Executive 層消費 gesture/pose events
- Go2 行為回應
- state topics（v2.1，若有需要）

---

## Frozen Interfaces（不可變更）

以下介面在 Phase 1-3 過程中不可變更：

1. **classifier 函式簽名**（本 spec 定義）
2. **InferenceResult dataclass**（本 spec 定義）
3. **event JSON schema**（interaction_contract v2.0 §4.3, §4.4）
4. **topic 名稱**（interaction_contract v2.0 §2）

---

## Verification

### Phase 1 驗收
```bash
# Build
colcon build --packages-select vision_perception
source install/setup.zsh

# 單元測試
python -m pytest vision_perception/test/ -v

# Mock node 跑起來
ros2 launch vision_perception vision_perception.launch.py inference_backend:=mock

# 確認 topic
ros2 topic list | grep -E "gesture|pose|vision"
ros2 topic echo /event/gesture_detected --once
ros2 topic echo /event/pose_detected --once
ros2 topic hz /vision_perception/debug_image

# Mock publisher（給前端）
ros2 launch vision_perception mock_publisher.launch.py

# Foxglove
# 連接 ws://localhost:8765，看到 debug_image + event JSON
```
