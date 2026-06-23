# PawAI Brain（LangGraph 對話決策大腦）— 架構詳述

**版本**：2026-05-11 freeze 快照
**位置**：`pawai_brain/`
**入口**：`pawai_brain/conversation_graph_node.py` → `build_graph()` (`pawai_brain/graph.py`)
**狀態**：5/12 brain-freeze-v2，95% 完成

---

## 0. 明天開發用閱讀入口

這份 `brain.md` 保留為總覽與凍結快照。若要在學校快速定位問題，優先讀同資料夾拆出的 4 份文件：

| 文件 | 用途 |
|------|------|
| `brain-runtime-flow.md` | ROS2 topic、wrapper、ThreadPoolExecutor、輸入到 `/brain/chat_candidate` 的完整資料流 |
| `brain-graph-node-map.md` | 12-node LangGraph 每個 node 的檔案位置、輸入/輸出、trace、常見故障 |
| `brain-persona-capability-memory.md` | persona 6 檔載入、CAPABILITIES lazy inject、skill 可用性、memory/fallback |
| `brain-debug-runbook.md` | 明天現場 debug 指令、trace 判讀、常見症狀到檔案位置 |

**快速原則**：
- Brain 只提出 `reply_text + proposed_skill`；真正執行與仲裁在 `interaction_executive`。
- 看問題先 echo `/brain/conversation_trace`，不要先猜 LLM。
- `conversation_graph_node.py` 檔頭仍寫 11-node，但實際 `build_graph()` 是 12-node，以 `pawai_brain/graph.py` 為準。

---

## 1. 模組定位

`pawai_brain` 是 PawAI 系統的**對話決策大腦**。它的工作是把多模態感知（face / pose / gesture / object）+ 對話歷史 + skill registry 整合進 LangGraph，產出一個 **ChatCandidate**（reply_text + intent + proposed_skill + args），由下游 `interaction_executive` 做仲裁與執行。

**核心設計原則**：
- Brain 是「建議者」，Executive 是「決策者」（單一控制權）
- 三層大腦：Safety → Policy → Expression
- 多數 graph node 是 pure / testable，外部 I/O 集中在 provider 注入點；主要例外是 `llm_decision`（透過注入的 `OpenRouterClient` 發 LLM request）與 `world_state_builder`（透過 provider callable 抓 ROS 快照，含 wttr.in 帶 cache 的 HTTP 呼叫）— 但這些 I/O 都走注入介面，在測試端用 mock 即可全套跑 pytest
- 觀測性優先：每個 node 都寫 trace entry，前端 Studio 可看

**對外介面**：
- 訂閱：`/event/speech_intent_recognized` / `/brain/text_input` + 一堆 `/state/*` 與 `/event/*`（共 12 個）
- 發佈：`/brain/chat_candidate`（決策）+ `/brain/conversation_trace`（觀測）

---

## 2. 12-Node Graph 拓撲

```
        ┌──────────────────────────────────────────────────────┐
        │                    ENTRY: "input"                    │
        └──────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                  1 │  input_normalizer    │  正規化 user_text，空字串短路
                    └──────────────────────┘
                              │
                              ▼
                    ┌──────────────────────┐
                  2 │  mode_classifier     │  分類 7 種 mode（regex）：
                    └──────────────────────┘  safety / identity /
                              │                capability_question /
                              ▼                action_request /
                    ┌──────────────────────┐   self_intro_request /
                  3 │  safety_gate         │   scene_query / chat
                    └──────────────────────┘  ★ Conditional Branch ★
                          ┌───┴───┐
              safety_hit=True   safety_hit=False
                       │              │
                       │              ▼
                       │    ┌──────────────────────┐
                       │  4 │  world_state_builder │  時間/天氣 + face/pose/
                       │    └──────────────────────┘  gesture/recent_objects
                       │              │
                       │              ▼
                       │    ┌──────────────────────┐
                       │  5 │  capability_builder  │  skills + limits +
                       │    └──────────────────────┘  demo_session
                       │              │
                       │              ▼
                       │    ┌──────────────────────┐
                       │  6 │  memory_builder      │  最近 5 turns 對話
                       │    └──────────────────────┘
                       │              │
                       │              ▼
                       │    ┌──────────────────────┐
                       │  7 │  llm_decision        │  ★ OpenRouter LLM ★
                       │    └──────────────────────┘  gpt-5.4-mini →
                       │              │              gemini-3-flash (fallback)
                       │              ▼
                       │    ┌──────────────────────┐
                       │  8 │  json_validator      │  parse_persona_json +
                       │    └──────────────────────┘  strip_emoji + cap_length
                       │              │              + truncation 檢測
                       │              ▼
                       │    ┌──────────────────────┐
                       │  9 │  response_repair     │  Phase 1 直通 + 內容
                       │    └──────────────────────┘  verifier（僅 warn）
                       │              │
                       │              ▼
                       │    ┌──────────────────────┐
                       │ 10 │  skill_policy_gate   │  比對 capability_context
                       │    └──────────────────────┘  正規化 proposed_skill
                       │              │
                       └──────┐       │
                              ▼       ▼
                    ┌──────────────────────┐
                 11 │  output_builder      │  三路：safety / fallback / LLM
                    └──────────────────────┘  → reply_text + intent +
                              │                proposed_skill + args
                              ▼
                    ┌──────────────────────┐
                 12 │  trace_emitter       │  終點（publish 在 wrapper 做）
                    └──────────────────────┘
                              │
                              ▼
                             END
```

**統計**：12 nodes，11 條 linear edge + 1 條 conditional edge（2 branch）。
**唯一分歧點**：`safety_gate` 命中（停/stop/煞車...）→ 直接跳到 `output_builder`，省掉整段 LLM pipeline。

---

## 3. State Schema（`ConversationState` TypedDict, total=False）

| 區塊 | 欄位 | 型別 | 用途 |
|------|------|------|------|
| **Input** | `session_id` | str | dedupe key |
| | `source` | str | "speech" / "text" |
| | `user_text` | str | 正規化後輸入 |
| | `input_origin` | str \| None | "studio_text" → 走 Gemini TTS quality lane |
| **Context** | `world_state` | dict | 環境 + face + pose + gesture + recent_objects |
| | `capability_context` | dict | skills + limits + skill_results + demo_session |
| | `history` | list[dict] | 最近 5 turns |
| | `perception_context` | dict | placeholder（未用） |
| | `env_context` | dict | DEPRECATED（併入 world_state）|
| **Classification** | `mode` | str | 7 種 mode 之一 |
| **Safety** | `safety_hit` | bool | 觸發 conditional edge |
| **LLM I/O** | `llm_raw` | str | OpenRouter raw text |
| | `llm_json` | dict | parsed persona JSON |
| **Validation** | `validation_error` | str | JSON 解析錯誤訊息 |
| | `repair_failed` | bool | 修復用盡 → fallback |
| **Output** | `reply_text` | str | 最終 reply（繁中）|
| | `intent` | str | greet / chat / status / command... |
| | `selected_skill` | str \| None | P0 legacy 欄位 |
| | `proposed_skill` | str \| None | skill_policy_gate 推薦 |
| | `proposed_args` | dict | skill 引數 |
| | `proposal_reason` | str | 推薦原因（debug）|
| | `confidence` | float | 0.0-1.0 |
| | `reasoning` | str | LLM 自述決策（debug）|
| | `selected_demo_guide` | str \| None | demo guide 名稱 |
| **Observability** | `trace` | list[dict] | 各 node 寫入觀測點 |

---

## 4. 12 個 Node 的職責表

| Node | 讀取 | 寫入 | 外部呼叫 | 分支/門控 |
|------|------|------|---------|---------|
| `input_normalizer` | user_text | user_text（strip）+ trace | — | 空字串短路 |
| `mode_classifier` | user_text | mode | — | 純分類，不分支（但影響 prompt 注入）|
| `safety_gate` | user_text | safety_hit + reply_text + intent="stop" + 等預填欄位 | — | **Hard gate**：命中關鍵字 → 預填 + bypass LLM |
| `world_state_builder` | world/speaker/pose/gesture providers | world_state{period,time,weather,current_speaker,current_pose,current_gesture,recent_objects} | wttr.in（cached 10min）+ provider callbacks | stale 過濾（speaker 3s, pose 10s, gesture 5s）|
| `capability_builder` | world_state, registry, skill_result_provider, policy_provider, demo_session_provider | capability_context{capabilities[],limits[],demo_session,recent_skill_results} | `CapabilityRegistry.build_entries()` | 未配置時短路 |
| `memory_builder` | history_provider | history（list[dict]）| `ConversationMemory.recent()` | 純 passthrough |
| `llm_decision` | history, user_message（builder 注入）| llm_raw | **OpenRouter chat**（gpt-mini → gemini-flash） | LLM error 寫 trace，不分支 |
| `json_validator` | llm_raw | llm_json + validation_error | `parse_persona_json` + `strip_emoji` + `normalize_audio_tags` + `cap_length` + `looks_truncated` | parse 失敗 → 觸發 repair |
| `response_repair` | llm_json, validation_error, capability_context | repair_failed + 內容 verifier warnings（不 block）| `try_repair()`（Phase 1 直通）| 僅 warn，從不 gate |
| `skill_policy_gate` | llm_json.skill/args, capability_context | proposed_skill + proposed_args + selected_demo_guide | capability_context lookup + legacy allowlist fallback | drop 不在 context 內的提案；effective_status 路由 |
| `output_builder` | safety_hit, repair_failed, llm_json, user_text | reply_text + intent + selected_skill + 預設值 | `fallback_reply()`（RuleBrain）| 三路 router：safety / fallback / happy path |
| `trace_emitter` | trace | — | — | 終點 marker（publish 在 wrapper）|

---

## 5. World State 內容

由 `world_state_builder` 注入 `state["world_state"]`：

```python
{
  "period":      "下午",            # 早上/中午/下午/晚上/深夜
  "time":        "14:30",
  "weather":     "晴天 28°C",       # wttr.in（cached）
  "current_speaker": "roy",         # face_identity 注入，stale 3s
  "current_pose": {                 # N5-B，stale 10s
    "name": "sitting",
    "age_s": 2.3
  },
  "current_gesture": {              # N5-B，stale 5s
    "name": "wave",
    "age_s": 1.1
  },
  "recent_objects": [               # N3-A，30s 視窗
    {"class": "cup", "color": "red", "age_s": 5.2},
    {"class": "chair", "color": "brown", "age_s": 18.4}
  ],
  "tts_playing": false,
  "obstacle": false,
  "nav_safe": true,
  "active_skill": null
}
```

**Prompt 注入順序**（在 `_build_user_message` 內）：

```
[語音] 或 [文字] + 使用者說的話
[環境] {period} {time}，{weather}
[眼前的人] {current_speaker}
[最近姿勢] 坐著（2 秒前）          ← N5-B
[最近手勢] 揮手（1 秒前）          ← N5-B
[最近看到] 紅色的杯子（5 秒前）、咖啡色的椅子（18 秒前）  ← N3-A，上限 3 筆
[demo] {demo_session 內容}        ← N3-B
[能力描述] ← 只在 capability_question / action_request / self_intro_request
[能力 runtime] (JSON capabilities + limits + skill_results)
[mode_hint] / [intro_scaffold] / [scene_hint]
```

---

## 6. Conversation Mode（1C OpenClaw-lite）

`mode_classifier` 用 regex 把使用者輸入分類，影響 prompt 注入：

| Mode | 觸發 | LLM 注入 | 行為 |
|------|------|---------|------|
| `safety` | 停 / stop / 煞車 / 暫停 / 緊急 | — | safety_gate 短路 |
| `identity` | 「你是誰」「介紹一下」 | `[mode_hint]` 身份框架 | **不**送 capability，純人設答 |
| `capability_question` | 「你會什麼」「能做啥」 | `[能力描述]` + capability JSON | 列出可做事項 |
| `action_request` | 「請…」「幫我…」+ 動詞 | `[能力描述]` + capability JSON | 可提案 skill |
| `self_intro_request` | Studio formal intro cue | `[能力描述]` + `[intro_scaffold]` 5 段結構 | 100-180 字介紹 |
| `scene_query` | 「看到什麼」「在幹嘛」 | `[scene_hint]` 整合 pose+gesture+objects | grounded 場景敘述 |
| `chat`（default）| 其他 | — | 一般對話 |

**核心設計**：Lazy capability injection — chat / identity / safety 模式**不**注入能力清單，避免 LLM 變成「念功能表機器」。

---

## 7. Support Layer（Graph 周邊基礎設施）

```
pawai_brain/
├── llm_client.py            ──► OpenRouter chat，雙模型 fallback
├── memory.py                ──► ConversationMemory（deque max 5 turns，thread-safe）
├── validator.py             ──► parse_persona_json + strip_emoji + audio tag 正規化
├── repair.py                ──► try_repair（Phase 1 嚴格 parse）
├── rule_fallback.py         ──► 關鍵字 → intent + canned reply templates
├── schemas.py / state.py    ──► 型別契約
│
├── personas/v1/             ──► system prompt 組件
│   ├── IDENTITY.md          ──► PawAI 身份核心
│   ├── MISSION.md           ──► 專案定位
│   ├── CAPABILITIES.md      ──► 能力清單（lazy 注入）
│   ├── STYLE.md             ──► 說話風格
│   ├── OUTPUT.md            ──► JSON schema
│   └── EXAMPLES.md          ──► few-shot examples
│
└── capability/
    ├── registry.py             ──► CapabilityRegistry（合併 skill + demo_guide）
    ├── effective_status.py     ──► WorldFlags + 純函式狀態推算
    ├── world_snapshot.py       ──► ROS /state/* 快照（N3-A object cache）
    ├── skill_result_memory.py  ──► 最近 5 筆執行結果
    └── demo_guides_loader.py   ──► YAML pseudo-skills
```

### 7.1 LLM Client（雙模型 fallback chain）

```python
OpenRouterClient.chat(system, history, user) →
  1. Try gpt-5.4-mini (timeout 4.0s)
  2. If timeout → return None（沒預算給 fallback）
  3. If error AND remaining > 0.3s → try gemini-3-flash (min(remaining, 4.0s))
  4. Both fail → return None（graph 走 RuleBrain fallback）
```

**Key params**：
- `openrouter_request_timeout_s = 4.0`（5/4 從 2.0s 拉高給 urllib3 overhead）
- `openrouter_overall_budget_s = 5.0`（總預算）
- API key 必須 `.strip()`（5/12 hotfix：CRLF 會 500）

### 7.2 Capability Registry（Phase A.6）

`CapabilityRegistry.build_entries(world: WorldFlags, recent_results)` → `list[CapabilityEntry]`：

每個 entry：
- `name`, `kind`（skill / demo_guide）
- `effective_status`（available / needs_confirm / disabled / defer / blocked / cooldown / studio_only / explain_only）
- `can_execute`, `requires_confirmation`, `reason`
- 可序列化為 LLM dict 注入 prompt

**Status priority**（first match wins，純函式 `effective_status.py`）：
1. Baseline gates：disabled / studio_only / explain_only
2. Dynamic enable：static_enabled / enabled_when
3. Cooldown：剩餘冷卻秒數
4. Physical blocks：TTS 中 → defer；obstacle → blocked；nav unsafe → blocked
5. Confirmation gate：available_confirm → needs_confirm
6. Default：available

### 7.3 World Snapshot（N3-A）

`WorldStateSnapshot` 接收所有 `/state/*` 推送，提供：
- `to_world_flags()` → `WorldFlags`（給 effective_status 用）
- `to_dict()` → 完整快照
- `get_recent_objects(window_s=30)` → 過濾並計算 age_s

**Object cache 邏輯**（N5-A 過濾）：
- 每 `class` 保留最新一筆（latest-wins，避免 spam）
- color_confidence < 0.6 → 丟掉 color（精度 > 豐富度）
- `person` 排除（face_identity 擁有人）
- deque maxlen=8

### 7.4 Persona 載入

`ConversationGraphNode.__init__` 啟動時讀 `personas/v1/*.md`：
- IDENTITY + MISSION + STYLE + OUTPUT + EXAMPLES → 拼成 system_prompt
- CAPABILITIES.md 單獨快取 → mode 觸發時 lazy 注入

---

## 8. ROS2 Integration（ConversationGraphNode wrapper）

```
                  ConversationGraphNode (ROS2 node)
                  ─────────────────────────────────
┌──────────────────────────── Subscribers ───────────────────────────┐
│ /event/speech_intent_recognized  → _on_speech_event                │
│ /brain/text_input                → _on_text_input                  │
│ /state/perception/face           → _on_face_state                  │
│ /event/pose_detected             → _on_pose_detected               │
│ /event/gesture_detected          → _on_gesture_detected            │
│ /event/object_detected           → _on_object_detected             │
│ /state/tts_playing               → world_snapshot                  │
│ /state/reactive_stop/status      → world_snapshot                  │
│ /state/nav/safety                → world_snapshot                  │
│ /state/pawai_brain               → world_snapshot                  │
│ /brain/skill_result              → SkillResultMemory               │
│ /brain/demo_segment              → demo session（locked）           │
│ /brain/reset_context             → clear memory + 5s suppress      │
└────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
              ThreadPoolExecutor(2 workers, "convgraph")
              + single-flight lock（非 blocking）
                                 │
                                 ▼
              _process_one(text, confidence, session_id, input_origin):
                build initial_state
                  → graph.invoke()  ← 12-node 執行
                  → publish /brain/chat_candidate
                  → publish /brain/conversation_trace per entry
                  → memory.add(text, reply) 若是真實對話 turn
                                 │
                                 ▼
              Failure boundary：try / except → rule_fallback.fallback_reply()
                                              + error trace entry
┌─────────────────────── Publishers ────────────────────────────────┐
│ /brain/chat_candidate         (給 interaction_executive)          │
│ /brain/conversation_trace     (給 Studio / 觀測)                  │
└───────────────────────────────────────────────────────────────────┘
```

**注入模式**（pure function 風格）：
```python
world_state_builder.set_world_provider(snapshot)
world_state_builder.set_speaker_provider(face_provider)
world_state_builder.set_pose_provider(pose_provider)
world_state_builder.set_gesture_provider(gesture_provider)

capability_builder.configure(
    registry=registry,
    skill_result_provider=skill_results.recent,
    policy_provider=policy,
    demo_session_provider=snapshot_demo_session,
)

memory_builder.set_history_provider(memory.recent)

llm_decision.configure(
    client=openrouter_client,
    system_prompt=system_prompt,
    user_message_builder=self._build_user_message,
)
```

---

## 9. Trace 觀測模型

每個 node 都會 append 到 `state["trace"]`：

```python
state.setdefault("trace", []).append({
    "stage": "llm_decision",
    "status": "ok" | "warn" | "error",
    "detail": {
        "model": "openai/gpt-5.4-mini",
        "latency_ms": 1156.3,
        "tokens": 248,
        ...
    }
})
```

Wrapper 把每筆 trace 用 `TracePayload` 包裝後 publish 到 `/brain/conversation_trace`，Studio 前端可以看到完整 12-node 執行流（含 conditional edge 走哪邊、validator 為何 retry、skill_policy_gate 為何 drop 提案）。

這是 Brain 設計的最大特色：**可觀測 > 黑盒**。

---

## 10. 降級策略（三層保險）

```
LLM 主線：OpenRouter gpt-5.4-mini
            │ fail
            ▼
LLM 備援：OpenRouter gemini-3-flash
            │ fail（或 graph 整段 except）
            ▼
JSON 解析失敗：try_repair → 仍失敗
            │
            ▼
RuleBrain fallback：rule_fallback.fallback_reply(user_text)
  關鍵字 → intent → canned template:
    "停" → "stop" → "好的，停止動作。"
    "你好" → "greet" → "哈囉，我在這裡。"
    "狀態" → "status" → "我目前狀態正常。"
    else → "unknown" → "請再說一次。"
```

每層都會寫 trace（degraded=True）讓 Studio 看到降級點。

---

## 11. 5/12 brain-freeze-v2（與 4/x baseline 對照）

| Layer | 4/x baseline | 5/12 freeze-v2 | 動機 |
|-------|--------------|----------------|------|
| LLM primary | gemini-3-flash (1.89s P50) | **gpt-5.4-mini (1.16s P50, -39%)** | 8-model A/B：gpt-mini 完勝 |
| LLM fallback | — | gemini-3-flash | OpenRouter 韌性 |
| max_tokens | 120（限 40 字 reply）| **2000，不限長度** | 放開敘事、memory deque(10) |
| audio tag | gemini 3.0 不支援 | **gemini 3.1 native** [excited]/[laughs] | persona v3 情緒渲染 |
| Mode classification | 4 modes | **7 modes**（加 self_intro / scene_query / capability_question 拆 chat） | 5/11 N5 scene perception |
| World state | env + speaker | **+ pose / gesture / recent_objects** | N3-A + N5-B |

### 8-model A/B 結論
- ✅ **gpt-5.4-mini**：P50 1.16s, $0.018/12-call, 質量 4.5/5，唯一真懂 emoji context
- gemini-3-flash：P50 1.89s，做 fallback
- ❌ DeepSeek V4 Flash：P95 34s reasoning tail
- ❌ Claude Haiku：JSON 4/12 包 markdown fence
- ❌ Claude Sonnet：2× 慢 + 貴 + 無優勢
- ❌ GPT Nano：漏 audio tag

---

## 12. Conditional Edge 與 Subgraph

```python
g.add_conditional_edges(
    "safety_gate",
    _route_after_safety,
    {
        "output": "output",
        "world_state": "world_state",
    },
)

def _route_after_safety(state: ConversationState) -> str:
    return "output" if state.get("safety_hit") else "world_state"
```

**沒有 subgraph**，單一 flat 12-node StateGraph。
**沒有 compiled graph 快取**，每個 `ConversationGraphNode.__init__` compile 一次（生產通常 1 instance）。

---

## 13. Test 覆蓋

主要測試檔（pawai_brain/test/）：
- `test_conversation_graph_node.py`（3 測試）：訂閱、reset_context、handler 整合
- `test_world_snapshot.py`（11 測試 N3-A）：class dedup / color gate / person filter / window 過濾
- `test_user_message_builder.py`（9 測試）：prompt 注入 / 未知 class 跳過 / 顏色翻譯
- `test_mode_classifier.py`：7 種 mode 分類
- `test_response_repair.py`：N3-C verifier 警告規則
- `test_capability_builder_node.py`：registry + skill_result + policy 注入

---

## 14. 關鍵設計決策（給寫計畫書的參考）

1. **三層大腦**（Safety → Policy → Expression）：
   - Safety = `safety_gate`（hard kill switch）
   - Policy = `skill_policy_gate`（authorize skill execution）
   - Expression = `llm_decision` + `output_builder`（語言層）

2. **單體 graph 而非 multi-agent**：
   - 12 node 線性 + 1 條件分支，flat 易調試
   - 對抗 prompt drift 的方式是「強化 validator + verifier」而非「多 agent 投票」

3. **Pure function + dependency injection**：
   - 所有 node 不直接訪問 ROS / 檔案 / 網路
   - Providers 在 ROS wrapper 端注入
   - 全套可用 mock 跑 pytest

4. **Lazy capability injection（1D）**：
   - chat / identity / safety 模式不送 capability，避免 LLM 列功能表
   - 只在 capability_question / action_request / self_intro_request 才送

5. **Trace 是一等公民**：
   - 每個 node 都寫，per-entry publish 到 ROS topic
   - 前端 Studio 直接視覺化執行流

6. **降級可控**：
   - LLM 主備 + JSON repair + RuleBrain fallback，每層都 traceable
   - degraded=True flag 一路傳到 chat_candidate

---

## 15. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| 12-node 拓撲 | `pawai_brain/graph.py` |
| ROS wrapper + 注入 | `pawai_brain/conversation_graph_node.py` |
| State schema | `pawai_brain/state.py` + `schemas.py` |
| LLM client | `pawai_brain/llm_client.py` |
| Persona | `pawai_brain/personas/v1/*.md` |
| Capability 框架 | `pawai_brain/capability/registry.py` + `effective_status.py` |
| World snapshot（N3-A）| `pawai_brain/capability/world_snapshot.py` |
| 5/11 N5 scene perception spec | `docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md` |
| 5/12 brain-freeze 紀錄 | `docs/pawai-brain/dev-logs/2026-05-12-llm-naturalness-ab-eval.md` |
