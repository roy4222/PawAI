# PawAI Brain Debug Runbook

**目的**：明天帶去學校後，遇到 Brain 不自然、沒反應、亂提 skill、看不到現場狀態時，用這份從症狀快速查到 topic / trace / 檔案。

---

## 1. 第一優先：看 Brain Trace

```bash
ros2 topic echo /brain/conversation_trace
ros2 topic echo /brain/chat_candidate
```

判讀順序：

| Trace stage | 問題代表什麼 | 下一步 |
|-------------|--------------|--------|
| `input` | 有沒有收到文字 | 查 ASR 或 `/brain/text_input` |
| `mode_classifier` | intent 分類是否正確 | 查 `nodes/mode_classifier.py` |
| `safety_gate` | 是否被 stop 類短路 | 查使用者文字是否含「停/stop/緊急」 |
| `world_state` | 現場感知是否進 Brain | 看 detail 的 `objs/spk/pose/gst` |
| `capability` | skill registry / demo guide 是否載入 | 看 `N skills + M guides` |
| `memory` | history 幾輪 | 看是不是 reset 或 intent 不寫 memory |
| `llm_decision` | OpenRouter 是否成功 | `ok` 看 model，`fallback` 看錯誤 |
| `json_validate` | LLM JSON 是否合規 | `no_raw/parse_fail/truncated` |
| `repair` | 是否走 fallback | 目前 repair 不重試 |
| `verifier` | 回答品質警告 | 太短、能力問答沒具體 skill、demo 沒 follow-up |
| `skill_gate` | skill 是否被允許 | `proposed/needs_confirm/blocked/rejected_not_allowed` |
| `output` | 最終輸出路徑 | `ok/fallback/safety_path` |

一輪正常 trace 大概像：

```text
input: ok
mode_classifier: scene_query
safety_gate: ok
world_state: ok detail="下午 14:30 objs=1 spk=roy pose=sitting gst=none"
capability: ok detail="28 skills + 6 guides"
memory: ok detail="2 turn(s)"
llm_decision: ok detail="openai/gpt-5.4-mini"
json_validate: ok detail="valid"
repair: ok detail="pass_through"
skill_gate: proposed / needs_confirm / blocked / ...
output: ok
```

---

## 2. 現場 Topic 快查

### Brain I/O

```bash
ros2 topic echo /brain/chat_candidate
ros2 topic echo /brain/conversation_trace
ros2 topic echo /brain/text_input
ros2 topic echo /event/speech_intent_recognized
```

### World State 來源

```bash
ros2 topic echo /state/perception/face
ros2 topic echo /event/object_detected
ros2 topic echo /event/gesture_detected
ros2 topic echo /event/pose_detected
ros2 topic echo /state/tts_playing
ros2 topic echo /state/reactive_stop/status
ros2 topic echo /state/nav/safety
ros2 topic echo /state/pawai_brain
```

### Capability / Demo

```bash
ros2 topic echo /brain/skill_result
ros2 topic echo /brain/demo_segment
```

---

## 3. Node Log 必看字串

```text
conversation_graph_node ready
```

確認：
- `openrouter=on/off`
- `persona=file/inline`

```text
[persona] loaded directory ... 6 files verified
```

代表 persona 6 檔齊。沒有這行時，可能走 inline persona，回答會很罐頭。

```text
CapabilityRegistry build failed
```

代表 skill / demo guide 名稱衝突或 registry 建置失敗。後續 LLM proposed skill 很可能被 `not_in_capability_context` 擋掉。

```text
graph fatal:
```

代表 wrapper catch-all，會直接走 RuleBrain fallback。

```text
graph invocation already in progress — dropping turn
```

代表上一輪還在跑，這一輪被 single-flight guard 丟掉。現場如果「我講了沒反應」，要查這行。

```text
Published /brain/chat_candidate: session=... reply=... proposed=...
```

最後確認 Brain 是否真的有發出候選回覆。

---

## 4. 症狀到原因

### A. PawAI 沒反應

檢查順序：

1. `/event/speech_intent_recognized` 有沒有文字。
2. `/brain/conversation_trace` 有沒有新 trace。
3. log 是否有 `graph invocation already in progress`。
4. `/brain/chat_candidate` 有沒有 publish。
5. 若 chat_candidate 有，但沒聲音，問題在 `interaction_executive` 或 TTS，不在 Brain。

相關檔案：
- `conversation_graph_node.py::_on_speech_event()`
- `conversation_graph_node.py::_process_one()`
- `conversation_graph_node.py::_publish_chat_candidate_from_state()`

### B. 回答突然很罐頭

看 trace：
- `llm_decision:fallback`
- `json_validate:error`
- `repair:fallback`
- `output:fallback`

常見原因：
- OpenRouter key 沒載入。
- LLM timeout。
- LLM 回 invalid JSON。
- persona 沒載入，走 inline。

相關檔案：
- `llm_client.py`
- `validator.py`
- `nodes/json_validator.py`
- `nodes/response_repair.py`
- `rule_fallback.py`

### C. 自我介紹像功能清單

檢查：

1. `mode_classifier` 是不是 `self_intro_request`。
2. `CAPABILITIES.md` 是否被改進 base prompt。
3. `EXAMPLES.md` 是否 few-shot 過度列功能。
4. `_INTRO_SCAFFOLD` 是否太硬。

相關檔案：
- `nodes/mode_classifier.py`
- `conversation_graph_node.py::_build_user_message()`
- `pawai_brain/personas/v1/STYLE.md`
- `pawai_brain/personas/v1/EXAMPLES.md`
- `pawai_brain/personas/v1/CAPABILITIES.md`

### D. 問「你看到什麼」答不出

看 `world_state` trace detail：

```text
objs=0 spk=unknown pose=none gst=none
```

代表 Brain 沒拿到現場資料。再分別查：

```bash
ros2 topic echo /state/perception/face
ros2 topic echo /event/object_detected
ros2 topic echo /event/pose_detected
ros2 topic echo /event/gesture_detected
```

注意目前限制：
- pose 只快取 10 秒。
- gesture 只快取 5 秒。
- object 只保 class/color/time。
- face 只進 speaker，不進 distance。

相關檔案：
- `nodes/world_state_builder.py`
- `capability/world_snapshot.py`
- `conversation_graph_node.py::_on_face_state()`
- `conversation_graph_node.py::_on_pose_detected()`
- `conversation_graph_node.py::_on_gesture_detected()`
- `conversation_graph_node.py::_on_object_detected()`

### E. LLM 說要做動作，但沒有做

看 `/brain/chat_candidate`：

```json
"proposed_skill": null
```

再看 trace `skill_gate`：

| status | 意義 |
|--------|------|
| `blocked` | capability status 不允許，或 not_in_capability_context |
| `needs_confirm` | 已保留 proposed_skill，下游應要求 OK |
| `rejected_not_allowed` | skill 不在允許清單 |
| `demo_guide` | 只是展示腳本，不會 motion |

如果 `/brain/chat_candidate` 有 `proposed_skill`，但沒執行，問題多半在 `interaction_executive`。

相關檔案：
- `nodes/skill_policy_gate.py`
- `capability/effective_status.py`
- `interaction_executive/interaction_executive/brain_node.py`

### F. 問「剛剛做了什麼」答不出

原因：ConversationMemory 不記 skill execution。它只記 `greet/chat/status` 類對話。

查：

```bash
ros2 topic echo /brain/skill_result
```

相關檔案：
- `memory.py`
- `capability/skill_result_memory.py`
- `conversation_graph_node.py::_on_skill_result()`

---

## 5. 現場最小測試腳本

### 文字輸入測 Brain，不經 ASR

```bash
ros2 topic pub --once /brain/text_input std_msgs/String \
'{data: "{\"text\":\"你看到什麼？\",\"request_id\":\"manual-scene-1\",\"source\":\"studio_text\"}"}'
```

然後看：

```bash
ros2 topic echo /brain/conversation_trace
ros2 topic echo /brain/chat_candidate
```

### 測 safety short-circuit

```bash
ros2 topic pub --once /brain/text_input std_msgs/String \
'{data: "{\"text\":\"停！\",\"request_id\":\"manual-stop-1\",\"source\":\"studio_text\"}"}'
```

期待：
- trace: `safety_gate: hit`
- output: `safety_path`
- chat_candidate: `selected_skill=stop_move`, `reply_text=好的，我停下來。`

### 測 self intro mode

```bash
ros2 topic pub --once /brain/text_input std_msgs/String \
'{data: "{\"text\":\"請你自我介紹一下自己\",\"request_id\":\"manual-intro-1\",\"source\":\"studio_text\"}"}'
```

期待：
- mode_classifier: `self_intro_request`
- user prompt 有 `[能力描述]`、`[能力 runtime]`、`[intro_scaffold]`

### 測 scene query mode

```bash
ros2 topic pub --once /brain/text_input std_msgs/String \
'{data: "{\"text\":\"我現在在幹嘛？\",\"request_id\":\"manual-scene-2\",\"source\":\"studio_text\"}"}'
```

期待：
- mode_classifier: `scene_query`
- prompt 有 `[scene_hint]`
- world_state trace 顯示 pose/object/face 是否進來

---

## 6. 修改後驗證

Brain 純 Python 測試：

```bash
python3 -m pytest pawai_brain/test -q
```

若只改 mode regex：

```bash
python3 -m pytest pawai_brain/test/test_mode_classifier.py -q
python3 -m pytest pawai_brain/test/test_user_message_builder.py -q
```

若改 skill gate / capability：

```bash
python3 -m pytest pawai_brain/test/test_skill_policy_gate.py -q
python3 -m pytest pawai_brain/test/test_capability_registry.py -q
python3 -m pytest pawai_brain/test/test_effective_status.py -q
python3 -m pytest pawai_brain/test/test_graph_smoke.py -q
```

若改 persona loader / prompt：

```bash
python3 -m pytest pawai_brain/test/test_conversation_graph_node.py -q
python3 -m pytest pawai_brain/test/test_user_message_builder.py -q
```

Jetson 上改 Python 後仍要 build：

```bash
colcon build --packages-select pawai_brain
source install/setup.zsh
```

---

## 7. 明天暫不建議動的區域

除非有明確測試，明天現場不建議大改：

- `skill_policy_gate.py` 的 allowlist 與 v2 gate。
- `effective_status.py` 的 priority order。
- `conversation_graph_node.py` 的 single-flight lock。
- persona lazy inject 規則。
- `/state/tts_playing` QoS。

這些區域一改錯，會出現「LLM 會說但不執行」、「動作在 TTS 中插話」、「新對話不乾淨」、「trace 看起來正常但下游亂掉」。

