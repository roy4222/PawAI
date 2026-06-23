# Face Brain And Executive Integration

## 消費者拓撲

```text
face_identity_node
  ├─ /state/perception/face
  │    ├─ pawai_brain.conversation_graph_node
  │    │    └─ world_state.current_speaker
  │    ├─ pawai-studio.gateway
  │    │    └─ face panel
  │    ├─ vision_perception.event_action_bridge
  │    │    └─ pose/gesture demo TTS name interpolation
  │    └─ vision_perception.interaction_router
  │         └─ legacy gesture/person enrichment
  │
  └─ /event/face_identity
       ├─ interaction_executive.brain_node
       │    ├─ AttentionMachine face_visible + distance_m
       │    ├─ greet_known_person
       │    ├─ stranger_alert
       │    └─ fallen_alert name cache
       └─ vision_perception.interaction_router
            └─ legacy welcome event
```

## Brain：把臉變成 prompt 語境

檔案：

```text
pawai_brain/pawai_brain/conversation_graph_node.py
pawai_brain/pawai_brain/nodes/world_state_builder.py
```

`conversation_graph_node` 訂閱 `/state/perception/face`：

```python
for track in payload.get("tracks", []):
    name = str(track.get("stable_name") or "unknown")
    if name and name != "unknown":
        self._recent_face_identity = (name, time.time())
        return
```

`world_state_builder` 再做 stale filter：

```text
若 identity != unknown 且 age < _SPEAKER_STALE_S
  world_state.current_speaker = identity
否則
  current_speaker = unknown
```

因此 Brain 能回答：
- 「你看得到我嗎？」
- 「我是誰？」
- 「你現在看到誰？」

限制：
- Brain 端只取第一個 known track，沒有選最近者。
- Brain 不看 `distance_m`、`bbox`、`sim`，只拿名字。
- `/brain/reset_context` 後會 suppress face speaker 5 秒，避免剛 reset 又被舊臉寫回上下文。

## Executive：用 event 做互動仲裁

檔案：

```text
interaction_executive/interaction_executive/brain_node.py
interaction_executive/interaction_executive/attention_machine.py
```

`brain_node._on_face()` 會：

1. 讀 `stable_name` / `identity` / `name`。
2. 讀 `distance_m` / `depth_m`。
3. 把 face visible 和 distance 餵給 attention 狀態機。
4. 對 known stable face 做 greet。
5. 對 unknown 累積超過門檻後做 stranger alert。
6. 快取最近 stable known name，供 fallen pose 沒帶人名時補上。

## AttentionMachine 和距離

狀態：

```text
IDLE
  └─ face visible >= 0.5s
NOTICED
  └─ distance <= 1.6m 且 dwell >= 1.5s
ENGAGED
  └─ speech intent 或 active plan
INTERACTING
```

這代表 known face 不是一出現就打招呼，而是要「臉穩定 + 人靠近 + 停留」才算互動意圖。

## Known Face Greeting

觸發條件：

```text
event stable identity
identity != unknown
沒有 active skill/sequence
沒有 pending confirm
TTS 沒在播放
attention state == ENGAGED
同名 20 秒 cooldown 未命中
```

輸出 plan：

```json
{
  "skill": "greet_known_person",
  "args": {"name": "roy"},
  "source": "rule:known_face"
}
```

所以「容易重複打招呼」目前已經有幾層保護：
- stable event 才觸發，不看每幀 state。
- 必須 ENGAGED。
- 同名 20 秒 cooldown。
- TTS/skill/pending confirm 時不觸發。

仍可能重複的原因：
- face node 重啟後 cooldown 狀態重置。
- track lost 後重新進場，identity_stable 又發。
- 光線造成 identity_changed 或 known/unknown 來回跳。
- 多人場景 track 互竄。

## Stranger Alert

目前存在於 Executive：

```text
identity == unknown
unknown 持續 >= unknown_face_accumulate_s，預設 3 秒
attention state != IDLE
沒有 active skill/sequence
沒有 pending confirm
TTS 沒在播放
stranger_alert 30 秒 cooldown 未命中
```

風險：
- unknown 不等於陌生人，可能只是低光、側臉、沒註冊、深度/偵測抖動。
- 這條規則一旦 audible，Demo 現場很容易誤觸。

建議：
- 學校開發先改成 trace-only，或在 config 裡提供 disable flag。
- 若要保留 audible，應要求「unknown face + 距離近 + 停留 + 無已知人 + 二次確認」。

## Fallen Alert Name Cache

Executive 在 face event stable known 時快取：

```text
_last_stable_identity_name
_last_stable_identity_ts
```

當 pose 發 `fallen` 但 payload 沒有人名，Executive 會用 30 秒內的 stable face identity 補成：

```text
Roy 跌倒了
```

沒有 cached face 時 fallback 是「有人」。

## Studio 和 Legacy Bridge

Studio：

```text
pawai-studio/gateway/studio_gateway.py
  /state/perception/face -> source=face -> frontend face panel
```

Legacy/demo bridge：

```text
vision_perception/event_action_bridge.py
  /state/perception/face -> _latest_face_name
  gesture/pose TTS template 可用 {name}
```

Legacy interaction router：

```text
vision_perception/interaction_router.py
  /event/face_identity -> welcome event
  /state/perception/face -> gesture who/face_track_id enrichment
```

目前主線應以 `interaction_executive` 為準；legacy router/bridge 應視為 demo 或過渡層，避免和 Executive 重複發聲。
