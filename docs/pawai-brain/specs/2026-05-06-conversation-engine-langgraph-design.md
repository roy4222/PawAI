# Phase 0.5 — Conversation Engine × LangGraph Shadow Design

> **Status**: spec (approved 2026-05-06)
> **Date**: 2026-05-06
> **Phase**: A.5（Conversation Engine 過渡層）
> **Author**: brainstorm session 2026-05-06 evening
> **Demo target**: 2026-05-13 校內實機 demo（同週）+ tonight 影片錄製
> **Predecessor**: `docs/pawai-brain/architecture/overview.md` §3.5
> **Successor**: 待寫 `docs/pawai-brain/specs/2026-05-XX-langgraph-primary-cutover-design.md`（Phase 1 切 primary）

---

## 1. 目標

把 `llm_bridge_node.py`（1100 行）的責任攤平成可觀察、可測、可替換的 conversation orchestration layer，**同時不冒 demo 主線風險**。

具體三件事：

1. **llm_bridge 瘦身**：抽純 module（無新依賴、無行為變更）。
2. **Conversation output 升級成 SkillProposal**：legacy primary 開始 emit `proposed_skill`，brain_node 接 allowlist gate。
3. **LangGraph shadow skeleton**：新增 `pawai_brain` ROS2 package，shadow-only，發 `/brain/conversation_trace_shadow`，不 publish `chat_candidate`，不影響主線。

不做：LangGraph 切 primary、nav/motion-heavy skill 開放 LLM、Executive 重構、跨 session memory。

---

## 2. 核心設計原則

```
LLM reply_text 永遠自由發揮，永遠先講出來。
Skill proposal 是 optional side effect。
Brain 可以拒絕 skill，但不能吃掉自然回答。
Blocked skill → trace 記錄；使用者只感覺「沒做動作」，不感覺「沒回應」。
```

對應行為：
- 每一輪 chat_candidate 一定觸發 `chat_reply(reply_text)`（若 reply_text 非空）
- 若帶 `proposed_skill` 且通過 allowlist + safety + cooldown → enqueue 該 skill
- 若 blocked / rejected → 只發 trace，**不影響** chat_reply

---

## 3. 模型 stack（5/6 起優先採用）

| 層 | Primary | Fallback 1 | Fallback 2 |
|---|---|---|---|
| ASR | SenseVoice cloud（FastAPI on RTX 8000） | SenseVoice local（sherpa-onnx int8） | Whisper local |
| LLM | OpenRouter `google/gemini-3-flash-preview` | OpenRouter DeepSeek（既有 fallback chain） | RuleBrain |
| TTS | OpenRouter `google/gemini-3.1-flash-tts-preview` | edge-tts cloud | Piper local |
| Persona | `tools/llm_eval/persona.txt`（已含 17 skill JSON 格式）| inline SYSTEM_PROMPT | — |

**配置**：透過 `llm_persona_file` ROS param + `LLM_PROVIDER` / `TTS_PROVIDER` env。Gemini TTS provider 若今晚未接通，allowlist 走 edge-tts，spec 不阻塞。

---

## 4. Schema 變動

### 4.1 `/brain/chat_candidate`（擴 schema，向後相容）

新增 4 個欄位，既有欄位不變。

```json
{
  "session_id": "speech-1736...",
  "reply_text": "汪，我是 PawAI，我可以看見你也聽得懂你說話。",
  "intent": "chat",
  "selected_skill": null,            // legacy diagnostic — 仍由 adapt_eval_schema 填，僅 4 條 P0 skill
  "reasoning": "openrouter:eval_schema",
  "confidence": 0.82,

  // ── 新增（Phase 0.5）──
  "proposed_skill": "self_introduce",   // null | "show_status" | "self_introduce"（Phase 0.5 allowlist）
  "proposed_args": {},                  // dict，per-skill schema
  "proposal_reason": "user asked who I am",
  "engine": "legacy"                    // "legacy" | "langgraph"，便於 trace
}
```

關鍵差異：
- `selected_skill` **保留 legacy 語意**（4 條 P0 skill 的 diagnostic），Brain MVS 仍不採用做提案來源
- `proposed_skill` 是 **新欄位**，繞過 `adapt_eval_schema` 的 SKILL_TO_CMD 過濾，直接從 persona JSON 的 `skill` 欄帶過來
- 兩欄獨立，不互相干擾

### 4.2 `/brain/conversation_trace`（新 topic）

primary engine（legacy 或 langgraph）每階段發一筆。Studio Skill Trace Drawer 顯示。

```json
{
  "session_id": "speech-1736...",
  "engine": "legacy",
  "stage": "llm_decision" ,            // input | safety_gate | context | memory | llm_decision | json_validate | repair | skill_gate | output
  "status": "ok",                      // ok | retry | fallback | error
  "detail": "gemini-3-flash latency=850ms",
  "ts": 1730000000.123
}
```

### 4.3 `/brain/conversation_trace_shadow`（新 topic）

shadow engine 專用。Schema 同上但 `engine` 必為 shadow 那邊。**禁止** publish chat_candidate。

---

## 5. Persona / LLM JSON 契約

沿用 `tools/llm_eval/persona.txt` 既有格式：

```json
{"reply": "...", "skill": "self_introduce|show_status|...|null", "args": {...}}
```

**llm_bridge adapter 升級**（`llm_contract.py` 或 `conversation/validator.py`）：

```
persona.reply  → chat_candidate.reply_text
persona.skill  → chat_candidate.proposed_skill   (新)
persona.args   → chat_candidate.proposed_args    (新)
persona.skill ∈ SKILL_TO_CMD → chat_candidate.selected_skill (legacy diagnostic only)
```

`proposed_skill` 不過 SKILL_TO_CMD 過濾；交由 brain_node allowlist 把關。

---

## 6. brain_node 行為（新增邏輯）

```python
LLM_PROPOSABLE_SKILLS = {"show_status", "self_introduce"}

# Phase 0.5 執行策略（保守版，避免「reply + 10步 motion」太冗）
LLM_PROPOSAL_EXECUTE = {
    "show_status": "execute",          # 自然回答 + 跑 show_status
    "self_introduce": "trace_only",    # 自然回答即可，motion 不自動跑（demo button 仍可手動觸發）
}

def on_chat_candidate(msg):
    # 1. 永遠先講話
    if msg.reply_text:
        enqueue_proposal(SkillPlan.chat_reply(text=msg.reply_text))

    skill = msg.proposed_skill
    if not skill:
        return

    # 2. allowlist 檢查
    if skill not in LLM_PROPOSABLE_SKILLS:
        emit_trace(stage="skill_gate", status="rejected_not_allowed", detail=skill)
        return

    # 3. safety / cooldown / dedup
    block = pre_check(skill, msg.proposed_args)
    if block:
        emit_trace(stage="skill_gate", status="blocked", detail=block.reason)
        return

    # 4. 執行策略
    mode = LLM_PROPOSAL_EXECUTE[skill]
    if mode == "execute":
        enqueue_proposal(build_plan(skill, msg.proposed_args, source="llm_proposal"))
        emit_trace(stage="skill_gate", status="accepted", detail=skill)
    else:  # trace_only
        emit_trace(stage="skill_gate", status="accepted_trace_only", detail=skill)
```

**為何 self_introduce 走 trace_only**：
- 它是 10 步 motion sequence，跟自然 reply_text 同回合執行會很冗
- 5/5 night 移除 keyword rule 是因為近距離 SafetyLayer 會擋 motion 變 sleep；LLM 提案會撞同一面牆
- demo button 路徑保持完整版（`source="studio_button"`），需要看 motion 序列時改按鈕觸發
- 後續 Phase 1 若要打開，改成 `"execute"` 即可，schema 不變

---

## 7. LangGraph Shadow Skeleton（最小骨架）

新 ROS2 package：

```
pawai_brain/
├── package.xml
├── setup.py
├── launch/
│   └── pawai_conversation_graph.launch.py        # primary=off, shadow=on 預設
├── pawai_brain/
│   ├── __init__.py
│   ├── conversation_graph_node.py                # ROS2 node wrapper
│   ├── graph.py                                  # LangGraph build_graph()
│   ├── state.py                                  # ConversationState TypedDict
│   ├── nodes/
│   │   ├── __init__.py
│   │   ├── input_normalizer.py                   # Phase 0.5 必做
│   │   ├── llm_decision.py                       # Phase 0.5 必做（包現有 OpenRouter client）
│   │   ├── output_builder.py                     # Phase 0.5 必做（emit shadow trace）
│   │   └── trace_emitter.py                      # Phase 0.5 必做
│   └── prompts/
│       └── README.md                             # 指向 tools/llm_eval/persona.txt
└── test/
    └── test_graph_smoke.py                       # 1 個 happy path test
```

**Phase 0.5 graph 流程**（極簡 4 節點）：

```
input_normalizer → llm_decision → output_builder → trace_emitter
```

`safety_gate` / `context_builder` / `memory_builder` / `json_validator` / `response_repair` / `skill_policy_gate` 留到 Phase 1 補。

**Shadow 行為**：
- 訂 `/event/speech_intent_recognized`（同 legacy）
- 跑 graph，產生候選 chat_candidate dict
- **不 publish** `/brain/chat_candidate`
- 每階段 publish `/brain/conversation_trace_shadow`

**Feature flag**：

```bash
ros2 launch pawai_brain pawai_conversation_graph.launch.py \
    conversation_engine:=shadow \
    primary_engine:=legacy
```

`conversation_engine:=shadow` 是新 launch arg；`legacy` / `langgraph` 切 primary 留待 Phase 1。

---

## 8. llm_bridge_node 瘦身範圍

抽到 `speech_processor/speech_processor/conversation/`：

| 新檔 | 從 llm_bridge_node 抽出的責任 |
|---|---|
| `prompt_builder.py` | persona load + system prompt 組裝 + history merge |
| `llm_client.py` | OpenRouter call + Gemini/DeepSeek fallback chain + timeout |
| `validator.py` | JSON parse + schema check + emoji strip + truncation guard |
| `repair.py` | reply 截斷 / JSON 壞掉時的 retry prompt |
| `memory.py` | short-term conversation history（2-3 輪） |

**llm_bridge_node 重構後**只剩：
- ROS2 publisher / subscriber
- ROS param 讀取
- 把 ASR event 餵進 conversation pipeline
- 把 result publish 到 `/brain/chat_candidate`（含新 4 欄位）

行為**零變化**；既有測試 `test_llm_bridge_node.py` 應全綠。

---

## 9. Studio 顯示

`pawai-studio/frontend/components/chat/skill-trace-drawer.tsx` 新增三態 chip：

| Chip | 顏色 | 觸發條件 |
|---|---|---|
| `proposed` | 灰 | `proposed_skill` 非空 |
| `accepted` | 綠 | trace `status=accepted` 或 `accepted_trace_only` |
| `blocked` | 黃 | trace `status=blocked` |
| `rejected` | 紅 | trace `status=rejected_not_allowed` |

dev panel 新增 `Conversation Trace`（legacy）+ `Shadow Trace`（langgraph）兩個 tab。**ChatPanel 主聊天不放 trace**（避免污染 demo 視覺）。

---

## 10. 風險 / Fallback

| 風險 | Fallback |
|---|---|
| Gemini 3 Flash provider 接不通 | OpenRouter DeepSeek → RuleBrain |
| Gemini 3.1 Flash TTS provider 接不通 | edge-tts → Piper |
| LangGraph dependency 炸（import 失敗） | shadow node 不啟動，主線零影響 |
| persona LLM 回 invalid JSON | validator 走 repair；2 次失敗 fallback `say_canned` |
| `proposed_skill` 為 motion-heavy（不在 allowlist）| brain_node reject + trace；reply_text 仍播 |
| self_introduce 被 SafetyLayer 擋（即使 trace_only 也照常）| trace 顯示 blocked，chat_reply 已先播完 |

---

## 11. 不做的事（明確邊界）

- LangGraph 不切 primary（demo 後再切）
- nav / approach_person / wiggle / stretch 不開放 LLM 提案（仍走 rule + button）
- `proposed_skill` 不擴出 allowlist 兩條（show_status / self_introduce）以外
- llm_bridge 抽 module 不改 API、不改測試覆蓋
- Executive 不動

---

## 12. 驗收條件

| 項目 | 驗收方式 |
|---|---|
| llm_bridge 瘦身行為零變化 | `pytest speech_processor/test/test_llm_bridge_node.py` 全綠 |
| `proposed_skill` 走通 | smoke：問「介紹你自己」→ chat_candidate 有 `proposed_skill="self_introduce"` |
| Brain allowlist 生效 | 餵假 chat_candidate `proposed_skill="dance"` → trace `rejected_not_allowed`，無 proposal |
| show_status 真執行 | 問「你還好嗎」→ reply_text say + show_status SAY 步驟 |
| self_introduce trace_only | 問「你是誰」→ reply_text say，no motion，trace `accepted_trace_only` |
| Shadow 不影響主線 | shadow 啟動 / 關閉，legacy chat_candidate 行為一致 |
| Shadow trace 有資料 | `ros2 topic echo /brain/conversation_trace_shadow` 有 4 階段紀錄 |
| Studio 顯示 trace | proposed/accepted/blocked/rejected chip 都看得到 |

---

## 13. Demo 話術（5/13 校內實機）

> PawAI Brain 採 harness-oriented design。LLM 可以提出低風險對話型 skill 提案，例如狀態回報；涉及動作或導航的 skill 必須經過 deterministic rule、二次確認或 Studio 手動觸發，避免 LLM 直接控制機器狗。
>
> 目前 production path 走 legacy engine 保證穩定；LangGraph conversation graph 已作為 shadow engine 接入觀察 stateful decision flow，下一階段切 primary。
>
> Studio 的 Skill Trace Drawer 把整個決策過程攤開：LLM 提了什麼、Brain 接受還是擋下、為什麼。

---

## 14. 後續工作（Phase 1+）

- LangGraph 切 primary（feature flag `conversation_engine:=langgraph`）
- 補齊 6 個 graph 節點：safety_gate / context_builder / memory_builder / json_validator / response_repair / skill_policy_gate
- self_introduce 從 `trace_only` 切回 `execute`
- nav_demo_point 開放 LLM 提案 + OK confirm 流程
- read-only tools：get_robot_status / get_recent_objects / get_known_person

時程：5/13 demo 後啟動，與 PawClaw Phase B 平行推進。
