# Gesture Executive and Brain Integration

這份文件看手勢事件進入互動層後發生什麼。這也是目前 wiggle 誤觸、重複打招呼、Brain 答不出手勢狀態的主要來源。

## 1. Executive 主要消費者

主要檔案：

```text
interaction_executive/interaction_executive/brain_node.py
```

它訂閱：

```text
/event/gesture_detected
```

目前直接映射：

| gesture | executive 行為 |
| --- | --- |
| `wave` | 直接觸發 `wave_hello` |
| `palm` | 直接觸發 `system_pause` |
| `fist` | 直接觸發 `enter_mute_mode` |
| `index` | 直接觸發 `enter_listen_mode` |
| `thumbs_up` | 不直接 wiggle，先進 pending confirm |
| `peace` | 不直接 stretch，先進 pending confirm |
| `ok` | 如果有 pending skill，確認執行 |

## 2. Confirm flow

`thumbs_up` 和 `peace` 現在是二段式：

```text
thumbs_up detected
    -> pending skill = wiggle
    -> say_canned: [curious] 比 OK 我就做 wiggle

ok detected within timeout
    -> emit skill_request(wiggle)
```

```text
peace detected
    -> pending skill = stretch
    -> say_canned: [curious] 比 OK 我就做 stretch

ok detected within timeout
    -> emit skill_request(stretch)
```

目前 pending timeout 約 30 秒，gesture live window 約 5 秒。這是因為 `/event/gesture_detected` 不是高頻連續 stream。

## 3. Conversation gate

Executive 有一個避免打斷對話的 gate：

```text
_CONVERSATION_GATED_GESTURES = {"wave", "fist", "index"}
```

如果最近 30 秒內有 chat，或 TTS 正在播，這三個 gesture 會被壓掉。

重要：`palm` 不被 gate，因為暫停必須最高優先權。

更重要：`thumbs_up` / `peace` 目前也不被 conversation gate 保護。測試裡甚至保留了這個行為：

```text
test_gesture_thumbs_up_NOT_gated_confirm_path_unchanged
```

所以如果 `thumbs_up` 誤判，它不會直接 wiggle，但會在對話中跳出「比 OK 我就做 wiggle」的語音提示。這就是目前「wiggle 容易誤觸」最可能的互動層原因。

## 4. Brain world state

Brain 也訂閱 gesture event：

```text
pawai_brain/pawai_brain/conversation_graph_node.py
```

它把最近手勢存成：

```text
_recent_gesture = (gesture_name, timestamp)
```

接著 `world_state_builder.py` 會把 5 秒內的 recent gesture 放進 prompt，讓 LLM 回答「我現在在做什麼」「我比了什麼」這類問題。

但目前有一個命名落差：

```text
conversation_graph_node.py 的 _GESTURE_ZH
```

目前偏向舊名字：

| 已支援 | 問題 |
| --- | --- |
| `wave` | OK |
| `stop` | legacy，不是 canonical `palm` |
| `point` | legacy，不是 canonical `index` |
| `ok` | OK |
| `thumbs_up` | OK |
| `victory` | legacy，不是 canonical `peace` |

缺少：

```text
palm
fist
index
peace
```

所以就算 perception 已經發出 canonical event，Brain 也可能無法把它翻成中文世界狀態。這會導致使用者問「我現在比什麼？」時，LLM 不一定答得出來。

## 5. Legacy router / bridge

還有兩個舊路徑需要注意：

```text
vision_perception/vision_perception/interaction_router.py
vision_perception/vision_perception/event_action_bridge.py
```

`interaction_router.py` 目前 whitelist：

```text
{"stop", "thumbs_up", "ok"}
```

它不是現在最完整的 Executive path，偏 demo / legacy。

`event_action_bridge.py` 有 raw gesture demo bridge：

| raw gesture | 行為 |
| --- | --- |
| `wave` | 直接 publish `/tts`：「Hi！很高興看到你！」 |

風險：如果 `event_action_bridge` 和 `interaction_executive` 同時跑，wave 可能會被兩條路徑處理，造成重複 TTS 或和對話混在一起。

## 6. 明天建議修正優先順序

P0：統一 gesture 名稱。

```text
stop -> palm
point -> index
victory -> peace
```

建議在 publish 前做一次 normalize，避免每個 consumer 各自維護 alias。

P1：修 Brain gesture 中文表。

```text
palm: 手掌/暫停手勢
fist: 握拳
index: 食指
peace: 勝利手勢
```

P1：收斂 wiggle 誤觸。

可選方向：

```text
方案 A：把 thumbs_up / peace 也加進 conversation gate
方案 B：保留提示，但 TTS busy / recent chat 時只更新 pending，不說提示
方案 C：提高 thumbs_up 觸發條件，例如需要連續兩次 stable event
```

P2：確認 legacy bridge 是否仍需要開。

如果 demo 主線已經走 `interaction_executive`，建議不要同時啟 `event_action_bridge` 的 raw wave TTS。

