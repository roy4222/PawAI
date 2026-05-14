# PawAI Brain Skill-First MVS — 系統設計規格

> **Status**: current
> **Date**: 2026-04-27
> **Author**: 盧柏宇（Roy）
> **Scope**: PawAI Brain 三層架構落地（Skill-first reframe）+ Studio Brain Skill Console + Action Outlet Refactor
> **Builds on**: [`2026-04-11-pawai-home-interaction-design.md`](2026-04-11-pawai-home-interaction-design.md)（Skill 提到核心；4/11 spec 中的「PawAI Brain 三層」、「Skill Contract」、「Skill Queue」、「self_introduce meta skill」都被本設計細化與重新組織）
> **Defers**: 四個 PawAI repo PR（#38/#40/#41/#42）整併 — Brain MVS 穩定後再做（§9 Phase 3 hooks）

---

## 1. Context

PawAI Brain 三層架構（Safety / Policy / Expression）在 4/11 spec 已定義，現況為 v0：speech intent 直接進 state machine，**三條路徑同時 publish `/webrtc_req`**（`llm_bridge_node:596` / `interaction_executive_node:257` / `event_action_bridge:100`）卻沒有單一仲裁者，跌倒事件 race（`interaction_router` 2s debounce vs `interaction_executive` 立刻 STOP）。直接照 4/11 spec 加新 Brain node 會變成第四個寫手，重演導航踩過的「多控制源互搶」事故。

本設計把 **Skill 提到核心**：所有能力（聊天 / 動作 / 導航 / 警示 / 序列）都用統一的 `SkillContract` 表達；Brain 只負責**選 skill / 串 skill / 何時跑 skill**；Executive 只實作三個底層 executor（`say` / `motion` / `nav`）；Safety Layer 永遠 deterministic 且最高優先。Studio 的 Chat 頁不是聊天框，而是 **Brain Skill Console** — 像「會聊天的技能編排器」，使用者看著 Chat 卷動就把整個 Brain 決策過程看完。

**MVS 範圍**：5/16 demo 能演示 7 個場景（你好 / 停 / 介紹自己 / wave / 陌生人 3s / 熟人問候 / 跌倒），全程在 Studio Chat Console 觀測。**不做 PawAI Memory**、**不抄四個 PR**（Phase 3 預留 hooks）。

---

## 2. 架構總覽

```
┌──────────────────────────────────────────────────────────────────┐
│ Inputs                                                           │
│  /event/speech_intent_recognized   /event/face_identity          │
│  /event/gesture_detected           /event/pose_detected          │
│  /event/object_detected            /brain/chat_candidate         │
│  /brain/text_input  /brain/skill_request  (Studio 注入)           │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│ brain_node (純規則 router，無 LLM 直連)                           │
│  1. world_state.update(event)                                    │
│  2. safety_layer.hard_rule(event) → SkillPlan(stop_move)         │
│  3. critical_alert_rule(event) → SkillPlan(alert)                │
│  4. if active_sequence and event.priority > ALERT: drop          │
│  5. dedup (source, key) within 1s                                │
│  6. rule table → SkillPlan                                       │
│  7. speech 未命中 → 等 1500ms /brain/chat_candidate              │
│       命中 → SkillPlan(chat_reply, text=candidate.reply_text)    │
│       逾時 → SkillPlan(say_canned, text="我聽不太懂")            │
└───────────────────────────────┬──────────────────────────────────┘
                                ▼  /brain/proposal (SkillPlan)
┌──────────────────────────────────────────────────────────────────┐
│ interaction_executive_node (唯一 sport /webrtc_req 出口)         │
│  1. safety_layer.validate(plan, world)                           │
│     reject → emit /brain/skill_result(blocked_by_safety)         │
│  2. SAFETY/ALERT preempt: 清 queue → 立刻 dispatch                │
│  3. SEQUENCE: enqueue 多個 SkillStep                              │
│  4. queue worker 逐步 dispatch:                                   │
│       executor=say     → /tts                                     │
│       executor=motion  → /webrtc_req (sport)                      │
│       executor=nav     → nav_capability action client             │
│  5. step 完成/失敗 → emit /brain/skill_result                     │
│  6. publish /state/pawai_brain (TRANSIENT_LOCAL, 2 Hz)            │
│  ※ Executive 不訂 /brain/skill_result（自己發、不自己訂）         │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                       Go2 Pro / nav stack
```

**三層架構對應**（4/11 spec 用語）：
- **Safety Layer** = `safety_layer.py`（hard_rule + validate），位於 brain_node + executive_node 兩端
- **Policy Layer** = `brain_node.py` 的 rule table + 仲裁演算法
- **Expression Layer** = SAY executor + Studio bubble 視覺 + skill description 文字

---

## 3. Skill 模型（核心）

### 3.1 Primitive executor（Executive 只認三個）

```python
class ExecutorKind(str, Enum):
    SAY    = "say"     # → /tts (str)，TTS pipeline 接手
    MOTION = "motion"  # → /webrtc_req (WebRtcReq, sport api_id)
    NAV    = "nav"     # → nav_capability action client（goto_named/goto_relative/run_route）

@dataclass
class SkillStep:
    executor: ExecutorKind
    args: dict   # {"text": str} | {"name": str} | {"action": str, "args": dict}
                 # 可含 {text_template} / {name_template}，由 Brain 在展開時解析
```

### 3.2 Skill 與 Plan 結構

```python
class PriorityClass(IntEnum):
    SAFETY   = 0   # safety_stop（hard rule）
    ALERT    = 1   # stranger / fallen 等 critical
    SEQUENCE = 2   # 多步互動（self_introduce 等）
    SKILL    = 3   # 單步互動（acknowledge_gesture 等）
    CHAT     = 4   # 自由對話 / 文字回覆

@dataclass
class SkillContract:
    name: str
    steps: list[SkillStep]                  # 永遠 list；primitive 即 [1 step]
    priority_class: PriorityClass
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""                   # 給 Brain reasoning + Studio bubble 顯示
    args_schema: dict = field(default_factory=dict)
    ui_style: Literal["normal","alert","safety"] = "normal"  # Chat bubble 顏色 hint

    # MVS 用：永久關閉旗標（替代舊 `enabled`，語意更明確）
    static_enabled: bool = True

    # Phase B（PawClaw evolution）預留 — MVS 階段為空 list，行為等同 always-enabled。
    # 詳見 docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md
    enabled_when: list = field(default_factory=list)         # list[CapabilityPredicate] in Phase B
    requires_confirmation: bool = False                       # 高風險動作需 Studio confirm
    risk_level: Literal["low","medium","high"] = "low"

@dataclass
class SkillPlan:
    plan_id: str
    selected_skill: str        # 對應 SKILL_REGISTRY key
    steps: list[SkillStep]     # 已展開、模板已解析
    reason: str                # "rule:keyword_stop" / "user asked introduction" / ...
    source: str                # "rule" / "llm_bridge" / "studio_button" / "studio_text" / "face_timer"
    priority_class: PriorityClass
    session_id: str | None     # 對應 /brain/chat_candidate
    created_at: float
```

### 3.3 SkillResult lifecycle（Executive 回報，Studio 渲染）

```python
class SkillResultStatus(str, Enum):
    ACCEPTED          = "accepted"            # plan-level，validate 通過
    STARTED           = "started"             # plan-level，queue worker 開跑
    STEP_STARTED      = "step_started"
    STEP_SUCCESS      = "step_success"
    STEP_FAILED       = "step_failed"
    COMPLETED         = "completed"           # plan-level
    ABORTED           = "aborted"             # plan-level，被 ALERT/SAFETY 中斷
    BLOCKED_BY_SAFETY = "blocked_by_safety"   # plan-level，validate 拒絕

@dataclass
class SkillResult:
    plan_id: str
    step_index: int | None   # plan-level 事件 = None；step-level 為 0..N
    status: SkillResultStatus
    detail: str              # 失敗原因 / safety reason / step skill name
    timestamp: float
```

> **Executive 不訂閱 `/brain/skill_result`**。SkillResult 是 Executive 發給 Brain + Studio 的**單向**事件流；Executive 內部 step 進度由 queue worker 自己管理，不需要回讀自己發出的訊息。

### 3.4 SKILL_REGISTRY（MVS 9 條）

> **設計原則**：底層只有 say/motion/nav 三個 executor。`stop_move` 是 motion alias、`chat_reply` / `say_canned` 是 say alias、ALERT 與 SEQUENCE 結構同為 composite，只差 priority / cooldown / ui_style。**ALERT 是 semantic type，不是 executor**；Executive 不需要 `execute_alert()` 分支。

| Name | Priority | Steps（展開） | Cooldown | enabled | 說明 |
|---|---|---|---|---|---|
| `chat_reply` | CHAT | `[say{text}]` | 0 | true | **來自 llm_bridge** 的自然回覆，semantic alias of say |
| `say_canned` | CHAT | `[say{text}]` | 0 | true | **Brain 規則 fallback** 固定台詞通道（LLM 掛或逾時用） |
| `stop_move` | SAFETY | `[motion{name:"stop_move"}]` | 0 | true | Safety hard rule 直達；motion alias |
| `acknowledge_gesture` | SKILL | `[motion{name:"content"}, say{text:"收到"}]` | 3 | true | wave / ok / thumbs_up 通用回應 |
| `greet_known_person` | SKILL | `[say{text_template:"歡迎回來，{name}"}, motion{name:"hello"}]` | 20 (per-name) | true | 熟人問候 |
| `self_introduce` | SEQUENCE | 10 步（5 say + 5 motion 交替，見 §3.5） | 60 (whole) | true | 開場 wow moment |
| `stranger_alert` | ALERT | `[say{text:"偵測到不認識的人，請注意"}]` | 30 | true | unknown face ≥3s 觸發。**MVS 不做 motion**（Phase 3 視穩定度再加） |
| `fallen_alert` | ALERT | `[motion{name:"stop_move"}, say{text:"偵測到有人跌倒，請確認是否需要協助"}]` | 15 | true | **stop_move 是「停下機器狗自己」，不是 balance_stand** |
| `go_to_named_place` | SKILL | `[nav{action:"goto_named", args:{...}}]` | 0 | **false** | nav KPI 未通過，MVS `static_enabled=True` + `enabled_when=[phase_b_pending(False)]`；Studio Skill Button 灰階，hover 顯示「Phase B 才整合 nav_capability」（為 PawClaw evolution 鋪路） |

> **`chat_reply` vs `say_canned`**：兩者底層都是 say，但 source 不同：
> - `chat_reply`：source = `"llm_bridge"`，由 llm_bridge 透過 `/brain/chat_candidate` 提供 reply_text
> - `say_canned`：source = `"rule:chat_fallback"` 或其他規則，text 來自 Brain hardcoded（chat_candidate 逾時、LLM 全掛時用）
> Studio bubble 用不同顏色 / icon 區分，trace 才好懂。

### 3.5 META_SKILL 展開定義

```python
META_SKILLS: dict[str, list[SkillStep]] = {
    "self_introduce": [
        SkillStep(SAY,    {"text": "我是 PawAI，你的居家互動機器狗"}),
        SkillStep(MOTION, {"name": "hello"}),
        SkillStep(SAY,    {"text": "平常我會待在你身邊，等你叫我"}),
        SkillStep(MOTION, {"name": "sit"}),
        SkillStep(SAY,    {"text": "你可以用聲音、手勢，或直接跟我互動"}),
        SkillStep(MOTION, {"name": "content"}),
        SkillStep(SAY,    {"text": "我也會注意周圍發生的事情"}),
        SkillStep(MOTION, {"name": "stand"}),
        SkillStep(SAY,    {"text": "如果看到陌生人，我會提醒你提高注意"}),
        SkillStep(MOTION, {"name": "balance_stand"}),
    ],
}
```

`MOTION_NAME_MAP`（搬自既有 `speech_processor/llm_contract.py` 的 `SKILL_TO_CMD`，擴充至完整名單）：

```python
MOTION_NAME_MAP: dict[str, int] = {
    "hello":         1016,
    "stop_move":     1003,
    "sit":           1009,
    "stand":         1004,
    "content":       1020,
    "balance_stand": 1002,
}
BANNED_API_IDS: set[int] = {1030, 1031, 1301}  # FrontFlip / FrontJump / Handstand
```

---

## 4. Topic 契約（新 + 改）

### 4.1 新 topics

| Topic | Type | QoS | Direction | Payload |
|---|---|---|---|---|
| `/brain/chat_candidate` | `std_msgs/String` (JSON) | depth=10, RELIABLE | llm_bridge → brain | 見 §4.2 |
| `/brain/text_input` | `std_msgs/String` (JSON) | depth=10, RELIABLE | gateway → brain | `{request_id, text, source:"studio_text", created_at}` |
| `/brain/skill_request` | `std_msgs/String` (JSON) | depth=10, RELIABLE | gateway → brain | `{request_id, skill, args, source:"studio_button", created_at}` |
| `/brain/proposal` | `std_msgs/String` (JSON) | depth=10, RELIABLE | brain → executive (+ gateway 觀測) | `SkillPlan` JSON |
| `/brain/skill_result` | `std_msgs/String` (JSON) | depth=20, RELIABLE | executive → brain + gateway | `SkillResult` JSON |
| `/state/pawai_brain` | `std_msgs/String` (JSON) | depth=1, **TRANSIENT_LOCAL** | brain → gateway/Studio | 見 §4.3 |

### 4.2 `/brain/chat_candidate` schema

```json
{
  "session_id": "...",          // 沿用既有 speech contract 的 session_id，不另造
  "reply_text": "...",
  "intent": "chat",
  "selected_skill": null,       // ⚠ MVS diagnostic only; Brain 不執行此欄位
  "source": "llm_bridge",
  "confidence": 0.8,
  "created_at": 1714000000.0
}
```

> **`selected_skill` is diagnostic only in MVS**。Brain MVS 純規則，**只取 `reply_text`** 作為 chat_reply 的內容。LLM 即使建議 `selected_skill: "sit"` 也不會被執行，避免 LLM 間接控狗。Action skill 的選擇只能來自：
> - Brain 規則 table（語音關鍵字 / 手勢 / 人臉 / 姿勢 / 物體事件）
> - Studio Skill Button 的 `/brain/skill_request`（仍經 SKILL_REGISTRY 驗證 + safety）
> 此欄位保留是為了讓 Studio Trace Drawer 看見 LLM 的「建議」（debug 用），但實際執行路徑不採用。

### 4.3 `/state/pawai_brain` schema

```json
{
  "timestamp": 1714000000.0,
  "mode": "idle|chat|skill|sequence|alert|safety_stop",
  "active_plan": {
    "plan_id": "p-...",
    "selected_skill": "self_introduce",
    "step_index": 3,
    "step_total": 10,
    "started_at": 1714000010.0
  },
  "active_step": { "executor": "motion", "args": { "name": "sit" } },
  "fallback_active": false,
  "safety_flags": {
    "obstacle": false, "emergency": false, "fallen": false,
    "tts_playing": false, "nav_safe": true
  },
  "cooldowns": {
    "stranger_alert": 1714000040.0,
    "greet_known_person:alice": 1714000020.0
  },
  "last_plans": [
    /* ring buffer 5 筆，給 Skill Trace Drawer */
    {"plan_id": "...", "selected_skill": "...", "source": "...",
     "priority": 2, "accepted": true, "reason": "...", "created_at": 0}
  ]
}
```

### 4.4 既有 topic 的角色變更（不刪 schema）

| Topic | 舊角色 | 新角色 |
|---|---|---|
| `/event/speech_intent_recognized` | llm_bridge 訂 + executive 訂 | **brain 訂閱**；llm_bridge 仍訂以決定是否產 chat_candidate |
| `/event/gesture_detected` | router + executive 訂 | **brain 訂閱**；router 保留但 brain 不依賴 |
| `/event/pose_detected` | router + executive 訂 | **brain 訂閱**；router 保留但 brain 不依賴 fall_alert |
| `/event/face_identity` | llm_bridge + router + executive 訂 | **brain 訂閱**；其他訂閱者不影響 |
| `/event/object_detected` | executive 訂 | **brain 訂閱** |
| `/state/tts_playing` | executive + bridge 訂 | **brain world_state 訂閱**（沿用既有 publisher） |
| `/state/reactive_stop/status`、`/state/nav/safety` | nav 內部 | **brain world_state 訂閱** |
| `/tts` | llm_bridge / executive / bridge 三方都發 | **MVS runtime path：僅 Executive 發 production TTS**；手動 `ros2 topic pub` / 測試工具 / mock_server 仍允許發 |
| `/webrtc_req` (sport)：api_id ≠ 4001-4004 | llm_bridge / executive / bridge 三方都發 | **僅 Executive 發** |
| `/webrtc_req` (audio)：api_id ∈ {4001, 4002, 4003, 4004}（Megaphone enter/exit/upload/cleanup） | tts_node | **不變**；tts_node 是唯一 audio publisher |

---

## 5. Brain Rule Table（MVS 7 場景 + 1 fallback）

```python
RULES = [
    SafetyRule(
        keywords=["停","stop","煞車","暫停","緊急"],
        skill="stop_move",
        reason="rule:safety_keyword",
    ),
    SequenceRule(
        keywords=["介紹你自己","自我介紹","你是誰"],
        skill="self_introduce",
        reason="rule:self_introduce_keyword",
    ),
    SkillRule(
        event="gesture",
        match=lambda e: e.gesture in {"wave","ok","thumbs_up"},
        skill="acknowledge_gesture",
        args=lambda e: {"gesture": e.gesture},
        reason="rule:gesture_ack",
    ),
    SkillRule(
        event="face",
        match=lambda e: e.identity_stable and e.identity != "unknown",
        skill="greet_known_person",
        args=lambda e: {"name": e.identity},
        cooldown_key=lambda e: f"greet_known_person:{e.identity}",
        cooldown_s=20.0,
        reason="rule:known_face",
    ),
    AlertTimerRule(
        event="face",
        match=lambda e: e.identity == "unknown",
        skill="stranger_alert",
        accumulate_s=3.0,
        cooldown_s=30.0,
        reason="rule:unknown_face_3s",
    ),
    AlertTimerRule(
        event="pose",
        match=lambda e: e.pose == "fallen",
        skill="fallen_alert",
        accumulate_s=2.0,
        cooldown_s=15.0,
        reason="rule:pose_fallen_2s",
    ),
    ChatFallbackRule(
        wait_ms=1500,
        on_candidate=lambda c: SkillPlan(selected_skill="chat_reply", text=c.reply_text),
        on_timeout=SkillPlan(selected_skill="say_canned", text="我聽不太懂"),
        reason="rule:chat_fallback",
    ),
]
```

`/brain/text_input` 與 `/brain/skill_request` 也餵進同一條 Brain pipeline（不繞過 rule + safety）：
- `text_input` → 當作 speech intent 走 keyword + chat_fallback 路徑
- `skill_request` → 直接驗 SKILL_REGISTRY 中存在 + enabled + cooldown，通過後展開為 SkillPlan

---

## 6. Brain 仲裁演算法

```text
on_event(event):
    1. world.update(event)
    2. plan = safety_layer.hard_rule(event)
       if plan: emit(plan); return                 # SAFETY 永遠先
    3. plan = match_alert_rules(event)
       if plan and not in_cooldown(plan):
           emit(plan); return                      # ALERT 永遠先（可中斷 SEQUENCE）
    4. if state.has_active_sequence and event.implied_priority > PriorityClass.ALERT:
           drop(event, reason="active_sequence_protected"); return
    5. dedup_key = (event.source, event.coalesce_key, time_bucket_1s())
       if dedup_key in dedup_cache: drop; return
       dedup_cache.add(dedup_key)
    6. plan = match_rules(event)
       if plan and not in_cooldown(plan): emit(plan); return
    7. # speech 未命中 → 開 chat_buffer
       if event.kind == "speech":
           chat_buffer.put(event.session_id, event)
           schedule_timeout(event.session_id, 1500ms)
           return

on_chat_candidate(candidate):
    buffered = chat_buffer.pop(candidate.session_id)
    if buffered:
        emit(SkillPlan(selected_skill="chat_reply",
                       text=candidate.reply_text, source="llm_bridge"))

on_chat_timeout(session_id):
    buffered = chat_buffer.pop(session_id)
    if buffered:
        emit(SkillPlan(selected_skill="say_canned",
                       text="我聽不太懂", source="rule:chat_fallback"))
```

優先序：`SAFETY (0) > ALERT (1) > SEQUENCE (2) > SKILL (3) > CHAT (4)`
Sequence 執行中：只有 SAFETY/ALERT 可中斷；SKILL/CHAT 全部丟棄（不 queue）。

---

## 7. Executive Step Dispatch

```text
on /brain/proposal (SkillPlan):
    1. ok, reason = safety_layer.validate(plan, world)
       if not ok:
           emit /brain/skill_result(plan.id, status=BLOCKED_BY_SAFETY, detail=reason)
           return
    2. emit /brain/skill_result(plan.id, status=ACCEPTED)
    3. if plan.priority_class in (SAFETY, ALERT):
           skill_queue.clear(reason="preempted")   # 對被中斷者發 ABORTED
           skill_queue.push_front(plan)
       else:
           skill_queue.push(plan)
    4. queue worker 啟動（若未啟動）

queue worker loop:
    plan = skill_queue.peek()
    if plan is None: idle
    if plan.id changed: emit STARTED
    for step_index, step in enumerate(plan.steps):
        emit STEP_STARTED(step_index)
        ok = dispatch(step.executor, step.args)
        if step.executor == SAY: 等 /state/tts_playing 由 true→false
        elif step.executor == MOTION: 等 dispatch ack（MVS 信任 Go2，不等實際動作完成）
        elif step.executor == NAV: 等 action client result
        emit STEP_SUCCESS or STEP_FAILED
        if step_failed and plan.fallback_skill:
            enqueue fallback; break
    emit COMPLETED
    skill_queue.pop()

dispatch(executor, args):
    if executor == SAY:
        publish /tts (String=args["text"])
    if executor == MOTION:
        api_id = MOTION_NAME_MAP[args["name"]]
        assert api_id not in BANNED_API_IDS
        publish /webrtc_req (WebRtcReq, api_id=api_id, parameter=str(api_id))
    if executor == NAV:
        nav_action_client.send_goal(args["action"], args["args"])
```

---

## 8. Studio = Brain Skill Console

### 8.1 Layout（沿用 `/studio/page.tsx`，主 panel = ChatPanel）

```
┌──────────────────────────────────────────────────────────────┐
│ Brain Status Strip                                           │
│ [Brain] mode: sequence · self_introduce 3/10 · safety: ✓     │
│ [Face] [Speech] [Gesture] [Pose] [Object]  ← MODULE_STATUS   │
├──────────────────────────────────────────────────────────────┤
│ Conversation Stream                                          │
│   [user]         介紹你自己                                   │
│   [brain_plan]   self_introduce  · rule:self_introduce_kw    │
│   [skill_step]   1/10 say "我是 PawAI..."                    │
│   [say]          我是 PawAI，你的居家互動機器狗               │
│   [skill_step]   2/10 motion hello                           │
│   ...                                                        │
│   [user]         停！                                         │
│   [safety]       safety_stop · queue cleared                 │
│   [skill_step]   1/1 motion stop_move                        │
├──────────────────────────────────────────────────────────────┤
│ Skill Buttons                                                │
│ [self_introduce] [hello] [sit] [stand] [stop] [say...]       │
├──────────────────────────────────────────────────────────────┤
│ [Input ............................] [送出]                  │
└──────────────────────────────────────────────────────────────┘
                                   └─ Skill Trace Drawer (toggle)
                                      plan_id / steps / safety / world_state
```

### 8.2 ChatMessage union（chat-panel.tsx:14-37 重寫）

```ts
type ChatMessage =
  | UserMessage          // 既有：使用者文字輸入
  | VoiceMessage         // 既有：使用者語音轉錄
  | BrainPlanMessage     // 新：Brain 選了哪個 skill + reason
  | SkillStepMessage     // 新：執行第幾步 + executor + args
  | SayMessage           // 取代 AIMessage：來自 say step 的執行（含 chat_reply / say_canned 區分樣式）
  | SafetyMessage        // 新：safety_stop 或 blocked_by_safety
  | AlertMessage         // 新：ALERT skill 開始（紅底）
  | SkillResultMessage   // 新：completed / aborted / failed
```

### 8.3 Skill Buttons → `/brain/skill_request`

按下按鈕：`POST /api/skill_request {skill, args}` → gateway publish `/brain/skill_request` → Brain 走 rule + safety → SkillPlan → Executive。**不走 synthetic speech intent**。

按鈕清單（MVS）：
```
[ self_introduce ] [ hello ] [ sit ] [ stand ] [ content ] [ stop ]
```

`go_to_named_place` 因 `enabled=false` 顯示為灰階按鈕，hover tooltip：「Disabled: nav KPI pending」。

### 8.4 Chat 文字 input → `/brain/text_input`

`POST /api/text_input {text}` → gateway publish `/brain/text_input` → Brain 走同 rule pipeline（含 chat_fallback 1500ms 等 LLM）。**不偽裝成 `/event/speech_intent_recognized`**。

### 8.5 Gateway 改動（`pawai-studio/gateway/studio_gateway.py`）

```python
# 訂閱
TOPIC_MAP["/state/pawai_brain"]  = "brain_state"
TOPIC_MAP["/brain/proposal"]     = "brain_proposal"
TOPIC_MAP["/brain/skill_result"] = "brain_skill_result"

# 發佈
self._pub_skill_request = self.create_publisher(String, "/brain/skill_request", 10)
self._pub_text_input    = self.create_publisher(String, "/brain/text_input", 10)

# REST
@app.post("/api/skill_request")
@app.post("/api/text_input")
```

### 8.6 Pydantic schemas 擴充（`backend/schemas.py`）

新增：`SkillPlan`、`SkillStep`、`SkillResult`、`PawAIBrainState`、`SkillRequest`、`TextInput`。
擴充既有 `BrainState` → 與 `PawAIBrainState` 合併或 deprecate。

### 8.7 mock_server 同步擴充

`mock_server.py` 需能 mock `/api/skill_request` + `/api/text_input` + WebSocket 送假 `brain_state` / `brain_proposal` / `brain_skill_result`。前端可離線開發。

---

## 9. Phase 計畫

### Phase 0：Action Outlet Refactor（1-2 天）

**目標**：sport `/webrtc_req` 收成 Executive 單一出口；TTS audio `/webrtc_req` 不動。**用 feature flag 漸進切換，不硬切**。

| 檔案 | 改動 |
|---|---|
| `speech_processor/speech_processor/llm_bridge_node.py` | 新增 ROS2 param `output_mode: legacy\|brain`（default=`legacy`，不破壞既有聊天）。<br>`legacy` 模式：維持發 `/tts` + sport `/webrtc_req`（現狀）<br>`brain` 模式：**只**發 `/brain/chat_candidate`（用既有 `session_id`），不發 `/tts`、不發 sport `/webrtc_req`<br>新 launch `start_pawai_brain_tmux.sh` 設 `output_mode:=brain`；舊 launch 保持預設 |
| `vision_perception/launch/*` | 新增 `enable_event_action_bridge` launch arg（default=true），brain demo launch 設 false |
| `vision_perception/vision_perception/event_action_bridge.py` | **不刪檔**，僅 launch 不啟 |
| `vision_perception/vision_perception/interaction_router.py` | **不刪、不改**，brain MVS 不依賴 |
| `interaction_executive/...` | **不動**（待 Phase 1 重寫） |

**驗收**：
```bash
# 1. legacy 模式仍能跑既有 e2e
bash scripts/start_llm_e2e_tmux.sh
# 預期：聊天功能正常（llm_bridge 仍發 /tts + sport /webrtc_req）

# 2. brain 模式下，sport /webrtc_req 來源限制
bash scripts/start_pawai_brain_tmux.sh   # Phase 1 完成後
grep -rn "create_publisher" --include="*.py" /home/roy422/newLife/elder_and_dog/ \
  | grep "WebRtcReq" \
  | grep -v "^.*tts_node.py:" \
  | grep -v "^.*interaction_executive_node.py:"
# 預期：no output

# 3. tts_node 只發 audio api 4001-4004，不發 sport
grep -n "WebRtcReq" /home/roy422/newLife/elder_and_dog/speech_processor/speech_processor/tts_node.py \
  | head -20
# 手動審視 api_id 賦值，應只見 {4001, 4002, 4003, 4004}（Megaphone enter/upload/exit/cleanup）
# 補一個 source-level test：speech_processor/test/test_tts_audio_api_only.py
#   - import tts_node
#   - 收集所有 api_id literal
#   - assert 都在 {4001,4002,4003,4004}
```

### Phase 1：Brain MVS 後端（5-6 天）

**新檔**：
- `interaction_executive/interaction_executive/skill_contract.py`
  - `ExecutorKind` / `PriorityClass` / `SkillStep` / `SkillContract` / `SkillPlan` / `SkillResult` / `SkillResultStatus`
  - `SKILL_REGISTRY`（9 條）/ `META_SKILLS`（self_introduce 等）
  - `MOTION_NAME_MAP`（搬自 `llm_contract.py:SKILL_TO_CMD` 並擴充）/ `BANNED_API_IDS`
- `interaction_executive/interaction_executive/safety_layer.py`
  - `SafetyLayer.hard_rule(event) -> SkillPlan | None`
  - `SafetyLayer.validate(plan, world) -> (bool, reason)`
- `interaction_executive/interaction_executive/world_state.py`
  - 訂 `/state/tts_playing`、`/state/reactive_stop/status`、`/state/nav/safety`
  - 提供 `WorldState` snapshot dict
- `interaction_executive/interaction_executive/skill_queue.py`
  - `SkillQueue`：deque[SkillPlan]、`push` / `push_front` / `peek` / `pop` / `clear(reason)`
- `interaction_executive/interaction_executive/brain_node.py`
  - 訂全部事件 + chat_candidate + text_input + skill_request
  - 內部 state：`unknown_face_first_seen` / `fallen_first_seen` / `last_alert_ts` / `chat_buffer` / `dedup_cache`
  - 仲裁演算法（§6）
  - 發 `/brain/proposal` + `/state/pawai_brain` (2 Hz)
- 測試：`test_safety_layer.py` / `test_skill_contract.py` / `test_brain_rules.py` / `test_skill_queue.py`

**改檔**：
- `interaction_executive/interaction_executive/interaction_executive_node.py`
  - 移除直接訂 `/event/*`，改訂 `/brain/proposal`（**不訂 `/brain/skill_result`**，自己發、不自己訂）
  - 實作 §7 的 step dispatch loop
  - 發 `/brain/skill_result`（每 plan / step）
  - 移除 ad-hoc `/cmd_vel` 邏輯（forward 動作改由 nav skill 處理；MVS 不做）
- `interaction_executive/setup.py` + `launch/interaction_executive.launch.py` + `config/executive.yaml`
- `interaction_executive/interaction_executive/state_machine.py`
  - **MVS 完全不動**（避免擴散）。它的高階 enum / timeout / dedup / emergency 邏輯在 MVS 不被使用，但檔案保留以利未來擴充。Phase 1 完成後再評估是否真的廢除或重構。

**Verification**：
```bash
# 1. Unit tests
python3 -m pytest interaction_executive/test/ -v
# 預期：safety_layer (5 keyword + 4 validate) / skill_contract (9 SKILL + META expansion)
#       brain_rules (7 場景 dry run) / skill_queue (push/preempt/clear)

# 2. 整合 dry run（不開 Studio）
ros2 run interaction_executive brain_node &
ros2 run interaction_executive interaction_executive_node &
ros2 topic pub --once /event/speech_intent_recognized std_msgs/String \
  '{data: "{\"intent\":\"chat\",\"transcript\":\"停\",\"session_id\":\"t1\"}"}'
ros2 topic echo /brain/proposal --once       # 應見 stop_move SkillPlan
ros2 topic echo /brain/skill_result          # 應見 ACCEPTED → STARTED → STEP_STARTED → STEP_SUCCESS → COMPLETED
```

### Phase 2：Studio Brain Skill Console（3-4 天）

**Gateway**：見 §8.5
**Schemas**：見 §8.6
**Mock**：見 §8.7
**Frontend**：
- `frontend/contracts/types.ts`：鏡像新 schemas
- `frontend/stores/state-store.ts`：`brainState` 改 `PawAIBrainState` + 兩個 ring buffer
- `frontend/hooks/use-event-stream.ts`：3 個新事件分派
- `frontend/components/chat/chat-panel.tsx`：重寫 ChatMessage union（§8.2）+ 整合新 bubbles
- `frontend/components/chat/`：新增 `bubble-brain-plan.tsx` / `bubble-skill-step.tsx` / `bubble-safety.tsx` / `bubble-alert.tsx` / `bubble-skill-result.tsx` / `skill-buttons.tsx` / `brain-status-strip.tsx` / `skill-trace-drawer.tsx`

**Verification**：
- mock_server + frontend 一起跑，按 `[self_introduce]` Skill Button：
  - Conversation Stream 應依序顯示 brain_plan → 10 個 skill_step + say bubble → completed
  - Brain Status Strip 即時更新 step 進度
  - Skill Trace Drawer 列出 plan + safety = ✓
- 按 `[stop]`：safety bubble 出現、queue cleared
- Chat 輸入「介紹你自己」：等同按 self_introduce 按鈕
- Chat 輸入「今天天氣」：1500ms 內收 chat_candidate → say "今天..."；逾時 → say_canned "我聽不太懂"

### Phase 3：四個 PR 整合（Brain MVS 穩後再做，不在本 spec 範圍）

預留 hooks（檔案註解 placeholder）：
- `vision_perception/.../gesture_processor.py` ← 抄 PR#38 wave 動態手勢（45-frame palm-x deque）
- `vision_perception/.../pose_processor.py` ← 抄 PR#41 fallen 幾何規則（hip/trunk angle）
- `speech_processor/.../llm_bridge_node.py` ← 抄 PR#42 prompt + Plan B 台詞
- PR#40 後端不抄；whitelist UX 概念可考慮搬到 object panel

---

## 10. 關鍵檔案清單（總覽）

**新增**：
- `interaction_executive/interaction_executive/brain_node.py`
- `interaction_executive/interaction_executive/skill_contract.py`
- `interaction_executive/interaction_executive/safety_layer.py`
- `interaction_executive/interaction_executive/world_state.py`
- `interaction_executive/interaction_executive/skill_queue.py`
- `interaction_executive/test/test_safety_layer.py`
- `interaction_executive/test/test_skill_contract.py`
- `interaction_executive/test/test_brain_rules.py`
- `interaction_executive/test/test_skill_queue.py`
- `speech_processor/test/test_tts_audio_api_only.py`（驗 tts_node 只發 audio api）
- `pawai-studio/frontend/components/chat/bubble-*.tsx`（5 個 bubble）
- `pawai-studio/frontend/components/chat/skill-buttons.tsx`
- `pawai-studio/frontend/components/chat/brain-status-strip.tsx`
- `pawai-studio/frontend/components/chat/skill-trace-drawer.tsx`
- `scripts/start_pawai_brain_tmux.sh`

**修改**：
- `speech_processor/speech_processor/llm_bridge_node.py`（新 `output_mode` 參數；brain 模式只發 chat_candidate）
- `interaction_executive/interaction_executive/interaction_executive_node.py`（重寫：訂 /brain/proposal、step dispatch、發 /brain/skill_result）
- `interaction_executive/setup.py` + `launch/interaction_executive.launch.py` + `config/executive.yaml`
- `pawai-studio/gateway/studio_gateway.py`（TOPIC_MAP + 2 publishers + 2 REST）
- `pawai-studio/backend/schemas.py`（+ 6 個新 model）
- `pawai-studio/backend/mock_server.py`（同步 mock 新 endpoints + WS payload）
- `pawai-studio/frontend/contracts/types.ts`（鏡像）
- `pawai-studio/frontend/stores/state-store.ts`（brainState slot 改 schema + 2 ring buffer）
- `pawai-studio/frontend/hooks/use-event-stream.ts`（3 個新事件分派）
- `pawai-studio/frontend/components/chat/chat-panel.tsx`（重寫 ChatMessage union + 整合新 bubbles）
- `vision_perception/launch/*`（新 `enable_event_action_bridge` arg）
- `docs/contracts/interaction_contract.md`（v2.5：新增 6 個 topic schema）
- `interaction_executive/CLAUDE.md` + `AGENT.md`（更新 Brain/Executive 邊界）

**不動**（保護現有資產）：
- `tts_node.py`（仍發 audio /webrtc_req + /state/tts_playing）
- `state_machine.py`（內部結構保留）
- `vision_perception/event_action_bridge.py`（檔案留，launch 不啟）
- `vision_perception/interaction_router.py`（保留，brain 不依賴）
- 任何感知模組（face / vision / object / speech 收音與 ASR）
- `nav_capability` package
- 其他 5 個 perception sidebar panel（face / speech / gesture / pose / object）

---

## 11. 重用既有資產

| 想做的事 | 直接用既有 | 路徑 |
|---|---|---|
| LLM 三級 fallback 邏輯 | `llm_bridge_node` 內已實作 cloud → local → RuleBrain | `speech_processor/llm_bridge_node.py:200-450` |
| LLM JSON parse + BANNED_API_IDS | `parse_llm_response` / `BANNED_API_IDS` | `speech_processor/llm_contract.py` |
| State machine 高階狀態 | 既有六狀態 + dedup + timeout（MVS 不用，但保留） | `interaction_executive/state_machine.py` |
| reactive_stop 整合 | `/state/reactive_stop/status`、twist_mux | 已就緒，brain world_state 訂閱即可 |
| nav_capability action server | `goto_relative` / `goto_named` / `run_route` | nav_action_server_node 已 expose（Phase 1 only stub）|
| Studio gateway + Pydantic | FastAPI + WebSocket + TOPIC_MAP | `pawai-studio/gateway/studio_gateway.py` |
| Studio Zustand store + brainState slot | 已有 `brainState` 與 `updateBrainState()` | `pawai-studio/frontend/stores/state-store.ts` |
| Chat 主 panel layout | 既有 / 不需改 routing | `pawai-studio/frontend/app/(studio)/studio/page.tsx` |
| MOTION_NAME → api_id 對照 | `SKILL_TO_CMD` | `speech_processor/llm_contract.py:22-28`（搬 + 擴充） |

---

## 12. Demo 對照（Phase 2 結束時手動跑）

| 輸入 | 期望 Chat 流（縮寫） |
|---|---|
| 「你好」 | user → brain_plan(chat_reply or say_canned) → skill_step(say) → say |
| 「停」 | user → brain_plan(stop_move, ui:safety) → safety("queue cleared") → skill_step(motion stop_move) → completed |
| 「介紹你自己」 | user → brain_plan(self_introduce) → 10× (skill_step + say/motion bubble) → completed |
| wave 手勢 | brain_plan(acknowledge_gesture) → skill_step(motion content) → say "收到" |
| 熟人 alice 入鏡 | brain_plan(greet_known_person, args:{name:alice}) → say "歡迎回來，alice" → motion hello |
| 陌生人持續 ≥3s | brain_plan(stranger_alert, ui:alert, 紅底) → say "偵測到不認識的人，請注意" |
| pose=fallen 持續 ≥2s | brain_plan(fallen_alert, ui:alert) → motion stop_move → say "偵測到有人跌倒..." |
| 序列中按 [stop] | safety bubble 中斷正在跑的 sequence，aborted → 立刻 stop_move |

---

## 13. 設計取捨摘要（為什麼長這樣）

| 取捨 | 為什麼 |
|---|---|
| Skill 是核心，proposal 只是 envelope | 所有能力統一抽象、Studio 視覺化一致、未來 LLM function calling 直接餵 SKILL_REGISTRY |
| Executive 只實作 say/motion/nav 三 executor | composite skill 由 Brain 展開即可；Executive 簡單可信 |
| MVS Brain 純規則（不直接呼 LLM） | 4/11 spec 的「降級鏈」自動成立；MVS 完全可離線測試；LLM 後續加 function calling 不動 Brain |
| llm_bridge 加 `output_mode` feature flag | Phase 0 不打斷既有聊天，漸進切換更穩 |
| `chat_candidate.selected_skill` diagnostic only | LLM 不能間接控狗；action 選擇只能來自 Brain rule / skill_request |
| `stranger_alert` MVS 不做 motion | 警示 say 即可；少一個 motion 風險小 |
| `fallen_alert` 用 stop_move 不用 balance_stand | 是「人跌倒」不是「狗跌倒」；balance_stand 是 Go2 自己重心穩定動作 |
| Sequence 執行中只 SAFETY/ALERT 可中斷 | demo 行為可預測；race 邏輯最少 |
| Studio Quick Action → /brain/skill_request 而非 synthetic speech | 路徑語意清楚；不偽裝成另一種事件 |
| 4 個 PR 整合延後 | PR 仍在改進中，先穩 Brain 地基；避免抄了又被改 |
| `state_machine.py` MVS 不動 | 避免擴散；既有測試保留；未來再評估 |

---

## 14. 與 4/11 spec 的關係

本 spec **不取代** 4/11 spec，而是**細化它的 Brain 三層**並用 Skill-first 重新組織：

| 4/11 spec 段 | 本 spec 對應 |
|---|---|
| §5.1 命名體系（PawAI Brain / Skills / Memory） | §3 SkillContract / §4 `/state/pawai_brain`（Memory MVS 不做） |
| §5.2 Brain / Executive 關係 | §2 架構總覽（明確化 sport /webrtc_req 單一出口） |
| §5.3 三層架構 | §2 架構總覽 + §6 Brain 仲裁 + §7 Executive dispatch + safety_layer.py |
| §5.5 PawAI Skills | §3.4 SKILL_REGISTRY（9 條，含 enabled 旗標）|
| §5.6 Action Sequencing | §3.5 META_SKILLS + §6 sequence 中只 SAFETY/ALERT 可中斷 |
| §5.7 self_introduce sequence | §3.5 META_SKILLS["self_introduce"]（10 步明確）|
| §5.10 Guardian State Artifact | §4.3 `/state/pawai_brain` schema |
| §5.4 降級路徑 | Brain 純規則 + chat_candidate / say_canned 區分 + Plan B 通道 |

---

## 15. 未來擴充（不在 MVS 範圍）

- **LLM function calling**：把 SKILL_REGISTRY 餵給 LLM 作為 tool schema，由 LLM 直接產 SkillPlan（仍經 Brain rule + safety_layer 驗證）
- **PawAI Memory**：person_profiles / greeting_cooldown / session_context（4/11 spec §5.9）
- **Dynamic SEQUENCE composition**：Brain 根據 context 動態組合 SkillStep 而不只用 META_SKILLS
- **Executive 事件型驅動**：MOTION 等 Go2 真實 ack 而非 dispatch ack
- **Safety Layer 擴充**：加入 IMU、battery、temperature 條件
- **四個 PR 功能整合**（§9 Phase 3 hooks）

---

## 附錄 A：與 ROS2 介面契約 v2.4 的差異

新增於 v2.5：
- `/brain/chat_candidate`、`/brain/text_input`、`/brain/skill_request`、`/brain/proposal`、`/brain/skill_result`
- `/state/pawai_brain`（TRANSIENT_LOCAL）

行為變更（同 topic 但語意換）：
- `/event/*`：訂閱者集合縮減（Brain 為主，舊 router/bridge 僅在 legacy launch 啟動）
- `/tts`、`/webrtc_req`(sport)：MVS runtime 唯一 publisher = `interaction_executive_node`（manual / test 工具不在此限）
- `/webrtc_req`(audio, api_id 4001-4004)：唯一 publisher = `tts_node`（不變）

附錄結束。
