# PawAI Brain Graph Node Map

**目的**：把 12-node LangGraph 和本地程式碼逐一對上。現場看到 trace 時，可直接查到是哪個檔案、哪個函式、哪種錯。

**權威入口**：`pawai_brain/pawai_brain/graph.py`

---

## 1. Graph 拓撲

```text
ENTRY
  |
  v
input
  |
  v
mode_classifier
  |
  v
safety_gate
  |\
  | \ safety_hit=True
  |  v
  | output -> trace -> END
  |
  | safety_hit=False
  v
world_state
  |
  v
capability
  |
  v
memory
  |
  v
llm
  |
  v
validator
  |
  v
repair
  |
  v
skill_gate
  |
  v
output
  |
  v
trace
  |
  v
END
```

`conversation_graph_node.py` 檔頭註解還寫 11-node，實際以 `graph.py` 的 12-node 為準。

---

## 2. 12 個 Node 對照表

| # | Graph node | 檔案 / 函式 | 讀取 | 寫入 | Trace stage | 常見狀態 |
|---|------------|-------------|------|------|-------------|----------|
| 1 | `input` | `nodes/input_normalizer.py::input_normalizer()` | `user_text` | strip 後 `user_text` | `input` | `ok`, `error:empty` |
| 2 | `mode_classifier` | `graph.py::_mode_classifier_node()` + `nodes/mode_classifier.py::classify_mode()` | `user_text` | `mode` | `mode_classifier` | `safety`, `self_intro_request`, `scene_query`, `identity`, `capability_question`, `action_request`, `chat` |
| 3 | `safety_gate` | `nodes/safety_gate.py::safety_gate()` | `user_text` | `safety_hit`; hit 時預填 stop output | `safety_gate` | `hit`, `ok` |
| 4 | `world_state` | `nodes/world_state_builder.py::world_state_builder()` | provider cache | `world_state` | `world_state` | `ok` |
| 5 | `capability` | `nodes/capability_builder.py::capability_builder()` | `world_state`, registry, skill results, demo session | `capability_context` | `capability` | `ok`, `error:not_configured` |
| 6 | `memory` | `nodes/memory_builder.py::memory_builder()` | `ConversationMemory.recent()` | `history` | `memory` | `ok` |
| 7 | `llm` | `nodes/llm_decision.py::llm_decision()` | system prompt, history, user message | `llm_raw` | `llm_decision` | `ok`, `fallback`, `error:not_configured` |
| 8 | `validator` | `nodes/json_validator.py::json_validator()` | `llm_raw` | `llm_json`, `validation_error` | `json_validate` | `ok`, `error:no_raw`, `error:parse_fail`, `retry:truncated` |
| 9 | `repair` | `nodes/response_repair.py::response_repair()` | `validation_error`, `llm_json`, `capability_context` | `repair_failed`; verifier warnings | `repair`, `verifier` | `ok`, `fallback`, `warn` |
| 10 | `skill_gate` | `nodes/skill_policy_gate.py::skill_policy_gate()` | `llm_json.skill`, `llm_json.args`, `capability_context` | `proposed_skill`, `proposed_args`, `selected_demo_guide` | `skill_gate` | `proposed`, `needs_confirm`, `blocked`, `demo_guide`, `rejected_not_allowed` |
| 11 | `output` | `nodes/output_builder.py::output_builder()` | safety / repair / llm fields | `reply_text`, `intent`, `selected_skill`, `confidence` | `output` | `ok`, `fallback`, `safety_path` |
| 12 | `trace` | `nodes/trace_emitter.py::trace_emitter()` | `trace` | no-op | wrapper publishes | no-op |

---

## 3. Mode Classifier

檔案：`pawai_brain/pawai_brain/nodes/mode_classifier.py`

優先序固定：

```text
safety
  > self_intro_request
  > scene_query
  > identity
  > capability_question
  > action_request
  > chat
```

這個優先序很重要：
- 「介紹一下你自己」要進 `self_intro_request`，不是 `identity`。
- 「你看到什麼」要進 `scene_query`，不是 `capability_question`。
- 「停」類安全詞永遠先於其他 mode。

若現場回答像功能清單，先看 trace 裡的 `mode_classifier` 是否被分錯。

---

## 4. World State Builder

檔案：`pawai_brain/pawai_brain/nodes/world_state_builder.py`

輸出範例：

```json
{
  "period": "下午",
  "time": "14:30",
  "weather": "晴天 +28°C 濕度65%",
  "source": "speech",
  "timestamp": 1773561600.0,
  "current_speaker": "roy",
  "current_pose": {"name": "sitting", "age_s": 2.3},
  "current_gesture": {"name": "thumbs_up", "age_s": 1.1},
  "tts_playing": false,
  "obstacle": false,
  "nav_safe": true,
  "active_skill": null,
  "active_skill_step": 0,
  "recent_objects": [
    {"class": "cup", "color": "red", "age_s": 5.2}
  ]
}
```

Stale gate：
- face speaker：3 秒
- pose：10 秒
- gesture：5 秒
- objects：30 秒 window，由 `WorldStateSnapshot.get_recent_objects()` 控制

目前限制：
- face 只進 `current_speaker`，不進 `distance_m / face_count / bbox`。
- pose/gesture 只進 name + age，不進 confidence / hand。
- object 只進 class/color/age，不進 bbox / confidence / count。

---

## 5. LLM Decision

檔案：
- `pawai_brain/pawai_brain/nodes/llm_decision.py`
- `pawai_brain/pawai_brain/llm_client.py`

`llm_decision()` 自己不組 prompt，而是呼叫 wrapper 注入的 `ConversationGraphNode._build_user_message()`。

OpenRouter 行為：

```text
if no key or enable_openrouter=false:
  return None

try primary model (default: openai/gpt-5.4-mini)
  if ok: return raw JSON text
  if timeout: return None
  if HTTP/connection/parse error and budget remains:
    try fallback model (default: google/gemini-3-flash-preview)
```

注意：primary timeout 不跑 fallback model。這是為了守住整體延遲。

---

## 6. Validation / Repair

檔案：
- `pawai_brain/pawai_brain/validator.py`
- `pawai_brain/pawai_brain/nodes/json_validator.py`
- `pawai_brain/pawai_brain/nodes/response_repair.py`
- `pawai_brain/pawai_brain/repair.py`

Validator 做：
- strip markdown fence
- parse JSON object
- normalize `reply` 欄位
- strip emoji
- normalize unstable audio tags：`[sighs]` / `[sigh]` -> `[curious]`
- truncation guard

Repair 現況：
- `response_repair()` 遇 `validation_error` 直接 `repair_failed=True`。
- `repair.py::try_repair()` 目前只是再 parse 一次，Phase 2 才會做 LLM retry prompt。

所以明天如果看到 `json_validate:error` 或 `repair:fallback`，不要期待系統真的修 JSON，它會走 RuleBrain。

---

## 7. Skill Policy Gate

檔案：`pawai_brain/pawai_brain/nodes/skill_policy_gate.py`

重點不是「LLM 說 skill 就會執行」，而是：

```text
LLM JSON skill
  |
  v
passthrough? chat_reply / say_canned / null
  -> no proposed_skill

lookup capability_context
  |
  +-- no entry and in allowlist
  |     -> blocked:not_in_capability_context
  |
  +-- no entry and unknown
  |     -> rejected_not_allowed
  |
  +-- demo_guide
  |     -> selected_demo_guide, no proposed_skill
  |
  +-- skill effective_status=available
  |     -> proposed_skill
  |
  +-- skill effective_status=needs_confirm
  |     -> proposed_skill, trace needs_confirm
  |
  +-- blocked/cooldown/defer/disabled/explain_only
        -> no proposed_skill
```

`LLM_PROPOSABLE_SKILLS` 只是一層允許清單，不等於 persona 可以描述的所有能力。

目前清單：

```text
show_status
self_introduce
wave_hello
sit_along
stand
greet_known_person
careful_remind
wiggle
stretch
```

---

## 8. Output Builder

檔案：`pawai_brain/pawai_brain/nodes/output_builder.py`

三條路：

```text
safety_hit
  -> safety_gate 已預填 reply / selected_skill / intent

repair_failed or llm_json is None
  -> rule_fallback.fallback_reply(user_text)

happy path
  -> reply_text = llm_json.reply
  -> intent = llm_json.intent or "chat"
  -> proposed_skill 保留 skill_gate 結果
```

`selected_skill` 是 legacy P0 diagnostic，正常動作提案看 `proposed_skill`。

---

## 9. Trace 判讀

一輪正常 capability 問答大概會看到：

```text
input: ok
mode_classifier: capability_question
safety_gate: ok
world_state: ok detail="下午 14:30 objs=1 spk=roy pose=none gst=none"
capability: ok detail="28 skills + 6 guides"
memory: ok detail="2 turn(s)"
llm_decision: ok detail="openai/gpt-5.4-mini"
json_validate: ok
repair: ok
skill_gate: proposed / needs_confirm / blocked / ...
output: ok
```

異常時先看最早出現的非 `ok` stage。不要只看最後 reply。

