# PawAI Brain Persona / Capability / Memory

**目的**：整理 PawAI Brain 最容易改壞的三塊：persona prompt、skill 可用性、短期記憶。這份文件偏開發導覽，不是產品說明。

---

## 1. Persona 載入

入口：`pawai_brain/pawai_brain/conversation_graph_node.py::ConversationGraphNode._load_persona()`

`llm_persona_file` 有三種情況：

| 情況 | 行為 |
|------|------|
| 空字串 | 使用 `_INLINE_PERSONA`，只要求 JSON `reply/skill/args` |
| 指向單一檔案 | 整份檔案作為 system prompt，`_capabilities_md=""` |
| 指向資料夾 | 要求 6 檔齊全，5 檔進 system prompt，`CAPABILITIES.md` 單獨快取 |

目錄模式需要：

```text
pawai_brain/personas/v1/
├── IDENTITY.md
├── MISSION.md
├── STYLE.md
├── OUTPUT.md
├── EXAMPLES.md
└── CAPABILITIES.md
```

system prompt 串接順序：

```text
IDENTITY.md
MISSION.md
STYLE.md
OUTPUT.md
EXAMPLES.md
```

`CAPABILITIES.md` 不放進 base system prompt。它只在特定 mode 以 `[能力描述]` lazy inject。

---

## 2. Prompt 注入順序

入口：`ConversationGraphNode._build_user_message()`

每輪 user message 依序組成：

```text
[語音] 使用者說：「...」
[環境] 台北 下午 14:30，外面 ...
[眼前的人] roy
[最近姿勢] 坐著（2 秒前）
[最近手勢] 大拇指（1 秒前）
[最近看到] 紅色的杯子（5 秒前）
[demo] 段:... 已演:... 建議下一步:...
[能力描述]
  CAPABILITIES.md
[能力 runtime]
  compact capability_context JSON
[mode_hint]
[intro_scaffold]
[scene_hint]
```

不是每行都一定出現。是否出現取決於 world state、mode、demo session。

---

## 3. Capability Lazy Inject 規則

`CAPABILITIES.md` 只在下列 mode 注入：

```text
capability_question
action_request
self_intro_request
```

不注入：

```text
chat
identity
safety
scene_query
```

原因：如果每輪都把能力清單塞進 prompt，PawAI 會變成一直念功能表，身份問答也會退化成專題簡報。

如果改 persona 後發現 PawAI 太像客服或功能表，先檢查：
1. `mode_classifier` 是否分錯 mode。
2. 是否不小心把 `CAPABILITIES.md` 合進 base prompt。
3. `EXAMPLES.md` 是否有太多列功能清單的 few-shot。

---

## 4. Self Intro 和 Scene Query

### Self Intro

Mode：`self_intro_request`

會額外注入 `_INTRO_SCAFFOLD`，要求 PawAI 用 5 段方式做 demo 自介：
1. 開場 + 身份
2. 專案定位
3. 能力概覽
4. grounded 現場觀察
5. 拋下一步邀請

這條會看到 `CAPABILITIES.md`，所以容易講得很滿。明天如果要調自然度，優先看：
- `pawai_brain/personas/v1/STYLE.md`
- `pawai_brain/personas/v1/EXAMPLES.md`
- `_INTRO_SCAFFOLD` in `conversation_graph_node.py`

### Scene Query

Mode：`scene_query`

會額外注入 `_SCENE_HINT`，要求整合：
- `[眼前的人]`
- `[最近姿勢]`
- `[最近手勢]`
- `[最近看到]`

目前限制：
- face 沒有距離進 prompt。
- pose 10 秒後 stale。
- object 沒有位置/數量/confidence。

所以「你看到什麼」可以做基本回答，但「我手上拿什麼 / 我離你多遠」仍偏弱。

---

## 5. Capability Context 來源

資料流：

```text
interaction_executive.skill_contract.SKILL_REGISTRY
        |
        v
CapabilityRegistry
        ^
        |
pawai_brain/config/demo_guides.yaml

pawai_brain/config/demo_policy.yaml
        |
        v
limits / max_motion_per_turn

WorldStateSnapshot + SkillResultMemory + demo_session
        |
        v
capability_builder()
        |
        v
state["capability_context"]
```

檔案：
- `pawai_brain/pawai_brain/capability/registry.py`
- `pawai_brain/pawai_brain/capability/effective_status.py`
- `pawai_brain/pawai_brain/nodes/capability_builder.py`
- `pawai_brain/config/demo_guides.yaml`
- `pawai_brain/config/demo_policy.yaml`

---

## 6. Effective Status 規則

入口：`pawai_brain/pawai_brain/capability/effective_status.py::compute_effective_status()`

第一個命中規則勝出：

```text
baseline disabled       -> disabled
baseline studio_only    -> studio_only
kind demo_guide         -> explain_only
baseline explain_only   -> explain_only
static_enabled false    -> disabled
enabled_when non-empty  -> disabled
cooldown_remaining > 0  -> cooldown
tts_playing + SAY step  -> defer
obstacle + MOTION step  -> blocked
nav_safe false + NAV    -> blocked
baseline available_confirm -> needs_confirm
else -> available
```

這裡決定 LLM 能不能提案，不決定最終執行。最終仍由 `interaction_executive` 仲裁。

---

## 7. Skill 能介紹，不代表能執行

三個集合要分清楚：

| 集合 | 來源 | 意義 |
|------|------|------|
| Persona 能描述的能力 | `CAPABILITIES.md` | PawAI 可以用自然語言介紹 |
| Registry 裡的能力 | `interaction_executive.skill_contract.SKILL_REGISTRY` | 系統知道這個 skill contract |
| LLM 可提案能力 | `LLM_PROPOSABLE_SKILLS` in `skill_policy_gate.py` | Brain 可以把它放進 `proposed_skill` |

只改其中一處會出問題：
- 只改 `CAPABILITIES.md`：PawAI 會說，但 skill 不一定存在。
- 只改 `SKILL_REGISTRY`：系統能執行，但 LLM 不一定知道。
- 只改 `LLM_PROPOSABLE_SKILLS`：LLM 可能提案，但 capability gate 會擋。

目前 `CAPABILITIES.md` 的數字也要小心：文件寫「17 個」，實際列出 18 個；`SKILL_REGISTRY` 還更多。明天若整理能力清單，避免寫死數字。

---

## 8. Memory 記什麼

檔案：`pawai_brain/pawai_brain/memory.py`

`ConversationMemory(max_turns=5)` 存的是 OpenAI chat history 格式：

```json
[
  {"role": "user", "content": "我叫 Roy"},
  {"role": "assistant", "content": "[playful] Roy，我記住了"}
]
```

寫入點：`conversation_graph_node.py::_process_one()`

只有符合以下條件才寫入：
- `reply` 非空
- `intent in ("greet", "chat", "status")`

不記：
- raw LLM JSON
- proposed_skill
- world_state
- face/pose/gesture/object perception
- validation error
- skill execution trace

所以「剛剛做了什麼動作」不要期待從 ConversationMemory 找，要看 `SkillResultMemory` / `/brain/skill_result`。

---

## 9. 狀態記憶不是對話記憶

| 記憶 | 檔案 | 內容 | 壽命 |
|------|------|------|------|
| ConversationMemory | `memory.py` | 最近 5 turns user/assistant | reset_context 清掉 |
| SkillResultMemory | `capability/skill_result_memory.py` | 最近 5 筆 terminal skill result | process-local |
| WorldStateSnapshot | `capability/world_snapshot.py` | tts, obstacle, nav, active_skill, recent_objects | process-local |
| face latest cache | `conversation_graph_node.py` | `_recent_face_identity` | stale 3s |
| pose latest cache | `conversation_graph_node.py` | `_recent_pose` | stale 10s |
| gesture latest cache | `conversation_graph_node.py` | `_recent_gesture` | stale 5s |

這解釋目前 scene query 的限制：Brain 不是完整 world model，只是把這些短期快照組成 prompt。

---

## 10. Validation / Fallback

LLM 應輸出：

```json
{"reply": "...", "skill": "chat_reply", "args": {}}
```

Validation pipeline：

```text
llm_raw
  -> strip markdown fences
  -> json.loads()
  -> require dict
  -> normalize reply
  -> strip emoji
  -> normalize audio tags
  -> truncation guard
```

Fallback pipeline：

```text
OpenRouter returns None
  -> json_validate no_raw
  -> response_repair repair_failed=True
  -> output_builder RuleBrain fallback

LLM returns invalid JSON
  -> json_validate parse_fail
  -> response_repair repair_failed=True
  -> output_builder RuleBrain fallback

Graph unexpected exception
  -> wrapper catches
  -> _publish_error_trace()
  -> _publish_fallback_chat_candidate()
```

重要：`repair.py` 目前不是「真的修 JSON」。Phase 2 才會做 retry-prompt。現在 parse/truncation 問題基本就是 RuleBrain fallback。

---

## 11. 測試覆蓋

常用測試：

```bash
python3 -m pytest pawai_brain/test -q
```

重點測試檔：

| 測什麼 | 檔案 |
|--------|------|
| persona loader / reset / handler | `pawai_brain/test/test_conversation_graph_node.py` |
| prompt 注入 | `pawai_brain/test/test_user_message_builder.py` |
| mode regex collision | `pawai_brain/test/test_mode_classifier.py` |
| graph smoke | `pawai_brain/test/test_graph_smoke.py` |
| capability registry | `pawai_brain/test/test_capability_registry.py` |
| effective status | `pawai_brain/test/test_effective_status.py` |
| skill gate | `pawai_brain/test/test_skill_policy_gate.py` |
| validator | `pawai_brain/test/test_validator.py` |
| response repair verifier | `pawai_brain/test/test_response_repair.py` |
| LLM offline fallback | `pawai_brain/test/test_llm_client_offline.py` |

缺口：
- 沒有真正 ROS2 pub/sub integration test。
- 沒有 live OpenRouter 測試。
- persona 語意主要靠人工 eval，不是 golden test。
- repair retry 未實作。

---

## 12. 明天改 Brain 最容易踩的坑

1. 改 persona 時，不要把 `CAPABILITIES.md` 放進 base prompt。
2. 新增 skill 要同時看 `CAPABILITIES.md`、`SKILL_REGISTRY`、`LLM_PROPOSABLE_SKILLS`。
3. `available_confirm` 只表示 needs_confirm，不是直接執行。
4. `demo_guide` / `explain_only` 可介紹，但不會 motion。
5. 對話 memory 不記動作，要看 `/brain/skill_result`。
6. JSON repair 現在不真的修，看到 parse fail 就先查 prompt/模型輸出。
7. scene query 答不出姿勢，多半是 pose stale，不是 LLM 不懂。
8. object 答得太少，是 world snapshot 只存 class/color/time，不是 YOLO 一定沒看到。

