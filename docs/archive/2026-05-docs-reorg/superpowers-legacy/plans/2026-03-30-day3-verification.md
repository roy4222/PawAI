# Day 3 四核心驗證 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可重複的四核心模組桌測流程：Foxglove layout + thin observer + 10-case checklist

**Architecture:** 三個獨立交付物，無相互依賴。Foxglove layout 是靜態 JSON，observer 是獨立 Python 腳本（非 ROS2 package），checklist 已在 spec 中定義。

**Tech Stack:** Foxglove Studio layout JSON, Python 3 + rclpy, JSONL

---

## File Structure

| 檔案 | 職責 | 建立/修改 |
|------|------|----------|
| `foxglove/day3-verification.json` | Foxglove Studio layout（4 panel） | 建立 |
| `scripts/verification_observer.py` | Thin observer，訂閱 5 event topics → JSONL | 建立 |
| `logs/.gitkeep` | 確保 logs/ 被 git track（JSONL 本身 gitignore） | 建立 |
| `.gitignore` | 加入 `logs/*.jsonl` | 修改 |

---

### Task 1: Foxglove Layout JSON

**Files:**
- Create: `foxglove/day3-verification.json`

- [ ] **Step 1: 建立 foxglove 目錄和 layout 檔**

Foxglove Studio layout 格式是一個 JSON，頂層有 `configById` 和 `globalVariables`，每個 panel 用 tab ID 對應。

```json
{
  "configById": {
    "3D!face_debug": {
      "cameraState": {},
      "followMode": "follow-none",
      "scene": {},
      "imageMode": {
        "imageTopic": "/face_identity/debug_image"
      }
    }
  },
  "globalVariables": {},
  "userNodes": {},
  "playbackConfig": { "speed": 1 },
  "layout": "..."
}
```

實際內容需要符合 Foxglove Studio 的 layout schema。建立 4-panel grid：
- 左上：Image panel → `/face_identity/debug_image`
- 右上：Image panel → `/vision_perception/status_image`
- 左下：RawMessages panel → 5 個 event topics
- 右下：RawMessages panel → `/state/perception/face` + `/state/tts_playing`

```bash
mkdir -p foxglove
```

寫入 `foxglove/day3-verification.json`（完整內容見下方 Step 2）。

- [ ] **Step 2: 寫入完整 layout JSON**

Layout 用 Foxglove Studio 的 `Tab` + `Grid` 配置，4 panel 2x2：

```json
{
  "configById": {
    "Image!face_debug": {
      "imageMode": {
        "imageTopic": "/face_identity/debug_image"
      },
      "foxpixy": {}
    },
    "Image!vision_status": {
      "imageMode": {
        "imageTopic": "/vision_perception/status_image"
      }
    },
    "RawMessages!events": {
      "topicPath": "/event/face_identity",
      "diffEnabled": false,
      "diffMethod": "custom",
      "diffTopicPath": "",
      "showFullMessageForDiff": false
    },
    "RawMessages!state": {
      "topicPath": "/state/perception/face",
      "diffEnabled": false,
      "diffMethod": "custom",
      "diffTopicPath": "",
      "showFullMessageForDiff": false
    }
  },
  "globalVariables": {},
  "userNodes": {},
  "playbackConfig": { "speed": 1.0 },
  "layout": {
    "direction": "column",
    "first": {
      "direction": "row",
      "first": "Image!face_debug",
      "second": "Image!vision_status",
      "splitPercentage": 50
    },
    "second": {
      "direction": "row",
      "first": "RawMessages!events",
      "second": "RawMessages!state",
      "splitPercentage": 50
    },
    "splitPercentage": 55
  }
}
```

> **Note**: Foxglove RawMessages panel 只能綁一個 topic。如果需要同時看多個 event topic，可以在 Foxglove UI 中手動加 panel 或切換 topic。左下 panel 預設綁 `/event/face_identity`，測試時手動切換到需要的 topic 即可。實際多 topic 同時觀察靠 observer JSONL。

- [ ] **Step 3: Commit**

```bash
git add foxglove/day3-verification.json
git commit -m "feat: add Foxglove layout for Day 3 four-module verification"
```

---

### Task 2: Verification Observer

**Files:**
- Create: `scripts/verification_observer.py`
- Create: `logs/.gitkeep`
- Modify: `.gitignore`

- [ ] **Step 1: 確保 logs 目錄結構**

```bash
touch logs/.gitkeep
```

在 `.gitignore` 加入：
```
logs/*.jsonl
```

- [ ] **Step 2: 寫 verification_observer.py**

```python
#!/usr/bin/env python3
"""Day 3 verification observer — subscribes to 5 event topics, appends JSONL."""

import argparse
import json
import signal
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityType, DurabilityType
from std_msgs.msg import String

# --- Config -----------------------------------------------------------

TOPICS = [
    "/event/face_identity",
    "/event/interaction/welcome",
    "/event/speech_intent_recognized",
    "/event/gesture_detected",
    "/event/pose_detected",
]

# Topic → 預設 source（payload 中有 source 欄位則覆蓋）
SOURCE_MAP = {
    "/event/face_identity": "face_identity_node",
    "/event/interaction/welcome": "interaction_router",
    "/event/speech_intent_recognized": "stt_intent_node",
    "/event/gesture_detected": "vision_perception_node",
    "/event/pose_detected": "vision_perception_node",
}

# Topic → payload 中哪個欄位作為 event_type
EVENT_TYPE_FIELD = {
    "/event/face_identity": "event_type",
    "/event/interaction/welcome": "event_type",
    "/event/speech_intent_recognized": "event_type",
    "/event/gesture_detected": "gesture",
    "/event/pose_detected": "pose",
}


class VerificationObserver(Node):
    def __init__(self, output_path: Path):
        super().__init__("verification_observer")
        self._output_path = output_path
        self._file = open(output_path, "a")
        self._counts: dict[str, int] = defaultdict(int)

        qos = QoSProfile(
            reliability=ReliabilityType.RELIABLE,
            durability=DurabilityType.VOLATILE,
            depth=10,
        )

        for topic in TOPICS:
            self.create_subscription(
                String,
                topic,
                lambda msg, t=topic: self._on_event(t, msg),
                qos,
            )

        self.get_logger().info(f"Observer started — writing to {output_path}")
        self.get_logger().info(f"Subscribed topics: {TOPICS}")

    def _on_event(self, topic: str, msg: String):
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            payload = {"raw": msg.data}

        event_type_field = EVENT_TYPE_FIELD.get(topic, "event_type")
        event_type = payload.get(event_type_field, "unknown")

        source = payload.get("source", SOURCE_MAP.get(topic, "unknown"))

        record = {
            "ts": time.time(),
            "topic": topic,
            "source": source,
            "event_type": event_type,
            "payload": payload,
        }

        line = json.dumps(record, ensure_ascii=False)
        self._file.write(line + "\n")
        self._file.flush()
        self._counts[topic] += 1

        self.get_logger().info(
            f"[{topic}] event_type={event_type} (total: {self._counts[topic]})"
        )

    def print_summary(self):
        self.get_logger().info("--- Summary ---")
        total = 0
        for topic in TOPICS:
            count = self._counts[topic]
            total += count
            self.get_logger().info(f"  {topic}: {count}")
        self.get_logger().info(f"  TOTAL: {total}")
        self.get_logger().info(f"  Output: {self._output_path}")

    def destroy_node(self):
        self._file.close()
        super().destroy_node()


def main():
    parser = argparse.ArgumentParser(description="Day 3 verification observer")
    default_name = f"day3-verification-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    parser.add_argument(
        "--output",
        type=str,
        default=str(Path("logs") / default_name),
        help="Output JSONL path",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    rclpy.init()
    node = VerificationObserver(output_path)

    def shutdown(sig, frame):
        node.print_summary()
        node.destroy_node()
        rclpy.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.print_summary()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 在 Jetson 上測試 observer 啟動**

```bash
# 前提：已 source install/setup.zsh
python3 scripts/verification_observer.py
# 預期輸出：
# [INFO] Observer started — writing to logs/day3-verification-20260330-XXXXXX.jsonl
# [INFO] Subscribed topics: ['/event/face_identity', ...]
# Ctrl+C 後印 summary（全 0 正常，因為還沒啟動其他 node）
```

- [ ] **Step 4: Commit**

```bash
git add scripts/verification_observer.py logs/.gitkeep .gitignore
git commit -m "feat: add thin verification observer for Day 3 four-module test"
```

---

### Task 3: 整合驗證（在 Jetson 上執行）

這不是寫程式，是操作流程。列出來是為了確保 Task 1-2 的產出可用。

**前置條件：** Jetson 已開機，四模組可正常啟動。

- [ ] **Step 1: 啟動 full demo（ENABLE_ACTIONS=false）**

```bash
ENABLE_ACTIONS=false bash scripts/start_full_demo_tmux.sh
```

等所有 window ready（約 30-40 秒，ASR warmup ~15s）。

- [ ] **Step 2: 啟動 observer**

開一個新 terminal：

```bash
cd ~/elder_and_dog
source install/setup.zsh
python3 scripts/verification_observer.py
```

- [ ] **Step 3: 開 Foxglove 連線**

1. 瀏覽器開 Foxglove Studio（https://studio.foxglove.dev 或本地安裝）
2. 連線 `ws://<jetson-ip>:8765`
3. Import layout：左上選單 → Import layout → 選 `foxglove/day3-verification.json`
4. 確認 4 panel 出現

- [ ] **Step 4: 執行 10 個 test case**

按 spec 的 checklist 逐一執行。每個 case 完成後口頭記錄 pass/fail。

- [ ] **Step 5: 事後驗證**

```bash
# 各 topic event 數量
jq -r '.topic' logs/day3-verification-*.jsonl | sort | uniq -c

# 檢查 welcome
jq 'select(.topic == "/event/interaction/welcome")' logs/day3-verification-*.jsonl

# 檢查手勢
jq 'select(.event_type == "stop" or .event_type == "thumbs_up")' logs/day3-verification-*.jsonl

# 檢查語音 transcript
jq 'select(.topic == "/event/speech_intent_recognized") | {ts: .ts, type: .event_type, text: .payload.text, intent: .payload.intent}' logs/day3-verification-*.jsonl
```

- [ ] **Step 6: 判定結果**

- 10/10 pass → 進 Phase 2（`ENABLE_ACTIONS=true`）
- 有 fail → 記錄 blocker，修復後重測

- [ ] **Step 7: Phase 2 — ENABLE_ACTIONS=true**

```bash
# 清環境
bash scripts/clean_full_demo.sh
# 重啟
ENABLE_ACTIONS=true bash scripts/start_full_demo_tmux.sh
```

補跑 case 6（stop → Go2 stop_move）和 case 7（thumbs_up → Go2 content 動作）。

---

## Self-Review Checklist

- [x] Spec 的 5 個 topic 全部在 observer 中訂閱 ✅
- [x] EVENT_TYPE_FIELD 對齊契約：gesture 用 `gesture` 欄位、pose 用 `pose` 欄位、其他用 `event_type` ✅
- [x] JSONL 欄位 5 個：ts, topic, source, event_type, payload ✅
- [x] Foxglove layout 4 panel：face debug image, vision status image, events, state ✅
- [x] 10 case checklist 在 spec 中，plan 不重複定義 ✅
- [x] Case 10 修正版：低頻人工觸發 + state/debug image 持續更新 ✅
- [x] Phase 2 用 stop_move / thumbs_up（不是 content） ✅
- [x] `.gitignore` 排除 JSONL ✅
- [x] 無 placeholder、無 TBD ✅
