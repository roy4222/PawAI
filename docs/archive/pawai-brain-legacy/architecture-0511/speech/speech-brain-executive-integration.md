# Speech Brain and Executive Integration

這份文件看 speech event 出來後如何進 Brain / Executive，以及舊 bridge 為什麼可能造成重複回覆。

## 1. STT output

`stt_intent_node` 發：

```text
/event/speech_intent_recognized
```

payload 內最重要欄位：

```text
session_id
text
intent
provider
latency_ms
degraded
source
```

Brain 和 Executive 都看 `session_id`。這是把 ASR event、Brain candidate、Executive chat buffer 串起來的 key。

## 2. Brain 主線

Brain 訂閱 speech event：

```text
pawai_brain/pawai_brain/conversation_graph_node.py::_on_speech_event()
```

它跑 LangGraph 後 publish：

```text
/brain/chat_candidate
```

Executive 會等同一個 `session_id` 的 candidate，匹配成功才 emit `chat_reply`。

流程：

```text
speech event
  -> interaction_executive buffers session_id
  -> pawai_brain produces /brain/chat_candidate
  -> interaction_executive matches session_id
  -> build_plan(chat_reply)
  -> interaction_executive_node dispatch SAY
  -> /tts
```

## 3. Executive buffer / timeout

檔案：

```text
interaction_executive/interaction_executive/brain_node.py
```

speech event 進來：

- 先跑 safety hard rule。
- cancel pending confirm。
- 放入 `chat_buffer[session_id]`。
- 建一個 `chat_wait_ms` timer。

如果 Brain candidate 沒在 timer 前回來：

```text
say_canned: 我聽不太懂
```

如果 candidate 晚到，buffer 已經被清掉，會被 drop。

## 4. SAY step 到 /tts

SAY step 由：

```text
interaction_executive/interaction_executive/interaction_executive_node.py::_dispatch_step()
```

發到：

```text
/tts
```

如果 SAY step args 有 `source` 或 `input_origin`，會包 JSON envelope：

```json
{"text": "...", "source": "chat_reply"}
```

否則發純文字。`tts_node` 兩種都能吃。

## 5. Legacy bridge 風險

目前還存在兩個 legacy path：

```text
speech_processor/speech_processor/llm_bridge_node.py
speech_processor/speech_processor/intent_tts_bridge_node.py
```

`intent_tts_bridge_node`：

- 訂閱 `/event/speech_intent_recognized`
- 直接用 template publish `/tts`

`llm_bridge_node`：

- 可訂閱 speech event
- 可 output legacy `/tts`
- 也可 output `/brain/chat_candidate`，視 `output_mode` 而定

如果這些和 `pawai_brain + interaction_executive` 同時開，可能出現：

```text
同一個語音事件
  -> Brain/Executive 回一次
  -> intent_tts_bridge_node 又 template 回一次
  -> llm_bridge_node legacy 再回一次
```

所以明天現場如果聽到「重複回答」或「模板句插入自然對話」，優先檢查這兩個 node 是否還在跑。

## 6. 使用者提到的混音問題

「動作所觸發的語音容易跟我的語音對話混在一起」通常不是 ASR 一個問題，而是三層疊加：

1. 多個 publisher 都能發 `/tts`。
2. Executive 有些感知 rule 會自主 SAY，例如 object/pose/face/gesture。
3. Echo gate 只能防 PawAI 聽到自己，不會阻止多條 TTS source 排隊或互相插話。

目前比較健康的做法：

- 所有動作語音都走 Executive SAY step。
- legacy direct `/tts` bridge 在 demo 主線關掉。
- 感知自主語音都要看 `tts_playing`、active skill、pending confirm。
- TTS node 本身不做高階仲裁，只負責合成和播放。

## 7. 明天第一個檢查

```bash
ros2 node list | grep -E "tts|llm_bridge|intent_tts|pawai_brain|interaction"
```

理想主線：

```text
stt_intent_node
pawai_brain conversation_graph_node
interaction_executive brain_node
interaction_executive_node
tts_node
```

要小心：

```text
intent_tts_bridge_node
llm_bridge_node output_mode=legacy
event_action_bridge raw /tts
```

這些不是一定錯，但要知道它們會直接或間接發 `/tts`。

