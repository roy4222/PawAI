# Pose Executive and Brain Integration

這份文件看 `/event/pose_detected` 發出後，Executive、Brain、demo bridge 分別怎麼處理。這裡是目前「姿勢和 pawai brain 綁定薄弱」的主要原因。

## 1. Executive 主線

檔案：

```text
interaction_executive/interaction_executive/brain_node.py::_on_pose()
```

目前正式 rule：

| pose | Executive 行為 |
| --- | --- |
| `fallen` | 穩定累積後觸發 `fallen_alert` |
| `sitting` | 穩定 1 秒後觸發 `sit_along` |
| `bending` | 穩定 1 秒後觸發 `careful_remind` |
| `standing` | 清 timer，不觸發 |
| `crouching` | 清 timer，不觸發 |
| `akimbo` | 清 timer，不觸發 |
| `knee_kneel` | 清 timer，不觸發 |

所以你原本列的「蹲下、彎腰還沒綁互動動作和語音」需要拆開看：

- `bending` 已有 Executive 正式 skill：`careful_remind`。
- `crouching` 沒有 Executive 正式 skill，主要靠 demo bridge TTS。
- `akimbo/knee_kneel` 沒有 Executive 正式 rule。

## 2. Fallen path

Executive fallen 流程：

```text
pose == fallen
  -> fallen_first_seen starts
  -> 持續 fallen_accumulate_s，預設 2.0 秒
  -> cooldown 15 秒
  -> world_state.fallen = True
  -> emit fallen_alert skill
```

name 注入：

```text
raw pose payload name/identity
  -> fallback 最近 30 秒 stable face identity
  -> fallback "有人"
```

注意：`/event/pose_detected` 本身 `track_id=0`，沒有真的和 face track 綁定。現在只是用最近 stable face name 近似。

## 3. Sitting / bending path

```text
sitting
  -> stable 1s
  -> sit_along
```

```text
bending
  -> stable 1s
  -> careful_remind
```

這兩個在 pending confirm 期間不發 plan，避免蓋掉使用者正在 OK 確認的 gesture / skill。

## 4. Demo bridge path

檔案：

```text
vision_perception/vision_perception/event_action_bridge.py
```

它也直接訂閱 `/event/pose_detected`，把部分 pose 轉成 `/tts`：

| pose | demo TTS |
| --- | --- |
| `sitting` | 會不會太累？ |
| `crouching` | 我在這裡喔 |
| `bending` | 請小心喔 |
| `akimbo` | 你看起來很有架式喔！ |
| `knee_kneel` | 需要我幫忙嗎？ |
| `fallen` | 故意移除，不走 demo bridge TTS |

這條是 demo shortcut，不是長期主線。風險是它會和 Executive 的 `sit_along/careful_remind` 重複講話，尤其是 `sitting` / `bending` 同時被兩邊處理。

## 5. Brain world state

Brain handler：

```text
pawai_brain/pawai_brain/conversation_graph_node.py::_on_pose_detected()
```

它只做一件事：

```text
self._recent_pose = (pose_name, time.time())
```

world state builder：

```text
pawai_brain/pawai_brain/nodes/world_state_builder.py
```

目前 stale window：

```text
_POSE_STALE_S = 10.0
```

格式化中文：

```text
conversation_graph_node.py::_POSE_ZH
```

目前只支援：

```text
standing -> 站著
sitting -> 坐著
crouching -> 蹲著
fallen -> 跌倒
```

缺：

```text
bending -> 彎腰
akimbo -> 雙手叉腰
knee_kneel -> 單膝跪地
```

所以「我在幹嘛」答不出彎腰、叉腰、單膝跪地，不一定是 perception 沒辨識，而是 Brain formatting 直接 drop 掉未知 pose。

## 6. 最大架構問題：pose 是 state，但 event 是 transition

Pose 是持續狀態，例如你坐著 5 分鐘還是坐著。

但現在 `/event/pose_detected` 是 state transition，只在 pose 改變時發。這會造成兩個問題：

1. Brain 10 秒後 stale，長時間同姿勢會失憶。
2. Executive 的 fallen/sitting/bending accumulate timer 需要重複看到同 pose，但上游可能只發一次 transition event。

如果實測發現 `fallen_alert` 或 `sit_along` 不穩，要優先查這個設計矛盾，而不是只調 classifier。

可選修法：

| 方案 | 說明 |
| --- | --- |
| A | `vision_perception_node` 增加 `/state/perception/pose` 週期狀態 topic，event 仍保留 transition |
| B | `/event/pose_detected` 對 `fallen/sitting/bending` 重複發 stable heartbeat |
| C | Executive 改成收到一次 transition 後自己用 state topic 確認 |
| D | Brain pose stale 從 10s 改長，但這只修問答，不修 Executive |

建議長期採 A：event 表示「變化」，state 表示「現在」。

