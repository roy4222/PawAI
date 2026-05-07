# PawAI Capability-Aware Self-Demonstration — Design

> **Status**: spec (approved 2026-05-07 brainstorm)
> **Date**: 2026-05-07
> **Phase**: A.6（Capability awareness — LangGraph 內加 capability layer）
> **Demo target**: 2026-05-18 校內驗收
> **Predecessor**: `docs/pawai-brain/specs/2026-05-06-conversation-engine-langgraph-design.md`
>                 `docs/pawai-brain/architecture/overview.md` §3.5
> **Successor**: 待寫 `docs/pawai-brain/specs/2026-05-XX-pawclaw-workspace-files-design.md`（Phase 2 OpenClaw 樣式 workspace markdown）

---

## 1. 目標

讓 PAI 從「會回答 + 會提 skill」升級為「**自己介紹自己、自己選展示方式**」的 self-demonstration agent。

問題：上一版 LangGraph primary 雖然能 propose skill，但 LLM 不知道：
- 現在哪些能力可以展示、哪些只能說明、哪些被關閉
- 上一個 skill 跑成功 / 失敗
- runtime 條件（TTS 播放中、obstacle、cooldown）影響哪些能力

結果：LLM 容易「亂喊 skill 名字」或「一直說我可以做很多事」但不知道現在能不能做。

解法：在 LangGraph 內注入 **CapabilityContext** — 一張 LLM 看得到的統一能力表，27 條真 skill + 6 條 demo guide pseudo-skill 合成同一個 schema，每輪依 world_state 算 effective_status。

核心原則：

> **每個功能都讓 LLM 看得見、能提案、能理解限制；真正執行仍由 Brain/Executive 把關。**

不是「LLM 自由直控所有 skill」，而是「LLM 擁有完整能力認知、尊重 runtime 狀態」。

---

## 2. 兩階段範圍

### Cut A — 5/18 demo MVP（本 spec 實作範圍）

- `SkillContract` 加 4 個靜態欄位（display_name / demo_status_baseline / demo_value / demo_reason）
- 新 `pawai_brain/config/demo_guides.yaml`（6 條 demo guide）
- 新 graph 節點：`world_state_builder`、`capability_builder`
- 拔掉舊節點：`context_builder`、`env_builder`（責任併入 world_state_builder）
- `skill_policy_gate` 新增 `kind=demo_guide` 分支（demo_guide 只進 conversation_trace，**不進 /brain/chat_candidate**）
- `pawai_brain` 訂閱 `/brain/skill_result`，最近 5 筆進 prompt
- Persona prompt 升級：capability rules + chaining rules
- `demo_session` schema placeholder（active / shown_skills / candidate_next，不更新）

估 ~2.5 天。

### Cut B — 5/18 後 Phase 2 forward path（本 spec 不實作）

- OpenClaw 樣式 workspace files：`pawai_brain/workspace/SOUL.md` / `SKILLS.md` / `DEMO.md` 注入 prompt
- Hermes-lite procedural memory：skill_result 統計 success rate、cooldown 自動調整
- `demo_session` state machine：`idle → introducing → demonstrating → done`，PAI 主動接下一個 skill
- needs_confirm 真 confirm handoff（OK 手勢 / Studio button → unblock skill）
- CapabilityRegistry 從 skill_contract 抽到獨立 module，與 BodyState 整合（PawClaw Phase B）

本 spec 的所有介面 / 檔名 / 欄位都依 Cut B 的目標形狀取，避免將來改名。

---

## 3. 不變式

1. `/brain/chat_candidate` schema **不加新欄位** — Brain contract 不認識 DemoGuide 概念
2. DemoGuide 永遠不發 `/brain/proposal`，只進 `/brain/conversation_trace`
3. `brain_node` / `interaction_executive` 程式碼不動
4. legacy `llm_bridge_node` 不動，仍可作 manual fallback
5. `interaction_executive/skill_contract.py` 加 4 欄位，不影響 brain_node / executive 既有讀取邏輯（新欄位有預設值）
6. needs_confirm 第一版 **沒有 confirm handoff 機制** — 只是 trace + LLM 引導使用者 OK/button

---

## 4. 資料模型

### 4.1 三層架構

```
真能力      SkillContract  (interaction_executive/skill_contract.py)  ← executive 用
demo guide  DemoGuide      (pawai_brain/config/demo_guides.yaml)      ← pawai_brain 用
合併視圖    CapabilityContext  (graph state, 每輪 rebuild)             ← LLM 看
```

### 4.2 SkillContract 加 4 個靜態欄位

```python
@dataclass
class SkillContract:
    # ── 既有欄位 ──
    name: str
    steps: list[SkillStep]
    priority_class: PriorityClass
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0.0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""
    args_schema: dict = field(default_factory=dict)
    ui_style: Literal["normal", "alert", "safety"] = "normal"
    static_enabled: bool = True
    enabled_when: list = field(default_factory=list)
    requires_confirmation: bool = False
    risk_level: Literal["low", "medium", "high"] = "low"
    bucket: SkillBucket = "active"

    # ── Phase A.6 新增 ──
    display_name: str = ""
    demo_status_baseline: Literal[
        "available_execute",
        "available_confirm",
        "explain_only",
        "studio_only",
        "disabled",
    ] = "disabled"
    demo_value: Literal["high", "medium", "low"] = "low"
    demo_reason: str = ""
```

### 4.3 DemoGuide（新 dataclass + yaml）

`pawai_brain/config/demo_guides.yaml`：

```yaml
face_recognition_demo:
  display_name: 人臉辨識
  baseline_status: explain_only
  demo_value: high
  intro: 我可以認出熟人。請 Roy 站到鏡頭前 1.5 公尺左右，我會主動打招呼。
  related_skills: [greet_known_person]

speech_demo:
  display_name: 語音對話
  baseline_status: explain_only
  demo_value: high
  intro: 你可以問我任何問題，我會記得最近聊過的事。
  related_skills: [chat_reply, self_introduce]

gesture_demo:
  display_name: 手勢辨識
  baseline_status: explain_only
  demo_value: high
  intro: 請對著鏡頭比 OK、讚、或握拳，我會跟你互動。
  related_skills: [wave_hello]

pose_demo:
  display_name: 姿勢辨識
  baseline_status: explain_only
  demo_value: high
  intro: 我能分辨站立、坐下、躺平。請讓我看看你的姿勢。
  related_skills: [sit_along]

object_demo:
  display_name: 物體辨識
  baseline_status: explain_only
  demo_value: medium
  intro: 我能辨識大物件和 12 種顏色。請拿純色物件靠近鏡頭。
  related_skills: [object_remark]

navigation_demo:
  display_name: 導航避障
  baseline_status: explain_only
  demo_value: medium
  intro: 我能做簡化導航和短距離移動。動態避障今天不主動展示，需要場地比較大。
  related_skills: [nav_demo_point, approach_person]
```

對應 dataclass：

```python
@dataclass(frozen=True)
class DemoGuide:
    name: str
    display_name: str
    baseline_status: Literal["explain_only", "studio_only", "disabled"]
    demo_value: Literal["high", "medium", "low"]
    intro: str
    related_skills: list[str] = field(default_factory=list)
```

DemoGuide 限制：`baseline_status` 不能是 `available_execute` / `available_confirm`（demo guide 永遠不會「執行」）；registry 啟動時 assert。

### 4.4 effective_status enum

```
available       — LLM 可提案執行（kind=skill, baseline=available_execute）
explain_only    — 可介紹，不可執行（baseline=explain_only 或 demo_guide）
needs_confirm   — 可介紹但執行需 OK / Studio button（baseline=available_confirm）
blocked         — 物理條件擋住（obstacle / nav 不安全）
cooldown        — 剛跑過、cooldown_s 還沒到
defer           — TTS / motion 進行中，等空閒
studio_only     — 只走 Studio button（baseline=studio_only）
disabled        — 策略上關閉（baseline=disabled）
```

### 4.5 effective_status 計算規則（capability_builder）

```
入: SkillContract / DemoGuide + WorldStateSnapshot
出: effective_status + reason

規則優先序（命中即停；physical block 必須在 needs_confirm 之前，否則 wiggle/stretch 會永遠請使用者 OK 但實際不能做）：
  baseline == disabled            → effective = disabled
  baseline == studio_only         → effective = studio_only
  kind == demo_guide              → effective = explain_only
  baseline == explain_only        → effective = explain_only
  static_enabled == False         → effective = disabled, reason="靜態未啟用"
  enabled_when 條件未通過         → effective = disabled, reason=enabled_when 訊息
  cooldown_remaining_s(skill) > 0 → effective = cooldown, reason="cooldown 剩 X 秒"
  world.tts_playing && skill 含 SAY → effective = defer, reason="TTS 播放中"
  world.obstacle && skill 含 MOTION → effective = blocked, reason="前方有障礙"
  world.nav_safe == False && skill 是 NAV → effective = blocked, reason="導航未 ready"
  baseline == available_confirm   → effective = needs_confirm, reason="需 OK 確認"
  其他                            → effective = available
```

### 4.6 CapabilityContext（LLM 看到的合併視圖）

graph state 新增 `capability_context` 欄位：

```python
class ConversationState(TypedDict, total=False):
    # ... 既有欄位 ...
    world_state: dict        # 由 world_state_builder 填
    capability_context: dict  # 由 capability_builder 填
    recent_skill_results: list[dict]  # 由 conversation_graph_node 注入
```

`capability_context` 序列化成 JSON 給 LLM：

```json
{
  "capabilities": [
    {
      "name": "self_introduce",
      "kind": "skill",
      "display_name": "自我介紹",
      "effective_status": "available",
      "demo_value": "high",
      "can_execute": true,
      "requires_confirmation": false,
      "reason": ""
    },
    {
      "name": "wiggle",
      "kind": "skill",
      "display_name": "搖擺",
      "effective_status": "needs_confirm",
      "can_execute": false,
      "reason": "需 OK 確認"
    },
    {
      "name": "gesture_demo",
      "kind": "demo_guide",
      "display_name": "手勢辨識",
      "effective_status": "explain_only",
      "can_execute": false,
      "intro": "請對著鏡頭比 OK、讚、或握拳",
      "related_skills": ["wave_hello"]
    }
  ],
  "limits": [
    "目前動態避障不是主展示項目",
    "陌生人警告已關閉避免誤觸",
    "一次最多執行一個動作"
  ],
  "demo_session": {
    "active": false,
    "shown_skills": [],
    "candidate_next": []
  },
  "recent_skill_results": [
    {"name": "self_introduce", "status": "completed", "detail": "6 steps", "ts": 1730...}
  ]
}
```

`limits` 來自 `pawai_brain/config/demo_policy.yaml`（新增）：

```yaml
limits:
  - 目前動態避障不是主展示項目
  - 陌生人警告已關閉避免誤觸
  - 一次最多執行一個動作
  - 手勢以靜態 OK / 讚 / 握拳為主
  - 人需要站在約 2 公尺外才容易完整辨識
max_motion_per_turn: 1
```

---

## 5. Graph 流程（11 節點）

```
input
 → safety_gate ─┬─→ output (safety_hit, skip middle)
                └─→ world_state_builder
                    → capability_builder
                    → memory_builder
                    → llm_decision
                    → json_validator
                    → response_repair
                    → skill_policy_gate
                    → output
                    → trace → END
```

變動：
- 新增 `world_state_builder`（取代原 `context_builder`，並吸收 `env_builder` 的 time/weather）
- 新增 `capability_builder`
- 移除 `context_builder`（純 stub，無價值）
- 移除 `env_builder`（責任併入 world_state_builder）

節點數從 11 變 11（淨 0）。

---

## 6. 節點責任

### 6.1 world_state_builder（新）

讀 `WorldStateSnapshot`（process-local cache，由 wrapper 訂閱 ROS topics 維護），組成：

```python
state["world_state"] = {
    # 環境
    "period": "早上",
    "time": "09:23",
    "weather": "晴 24°C",  # best-effort, may be empty
    "source": "speech",
    "timestamp": 1730...,
    # Runtime flags
    "tts_playing": False,
    "obstacle": False,
    "nav_safe": True,
    "active_skill": None,        # 取自 /state/pawai_brain.active_plan.selected_skill
    "active_skill_step": 0,      # 取自 /state/pawai_brain.active_plan.step_index
}
```

WorldStateSnapshot 訂閱來源（皆 latched / TRANSIENT_LOCAL，wrapper 拿最新值）：
- `/state/tts_playing` (Bool) → `tts_playing`
- `/state/reactive_stop/status` (String JSON) → `obstacle`
- `/state/nav/safety` (String JSON) → `nav_safe`
- `/state/pawai_brain` (String JSON, TRANSIENT_LOCAL) → `active_skill`、`active_skill_step`

任一 topic 沒到（subscription 未收到第一筆）→ 預設保守值（tts_playing=False, obstacle=False, nav_safe=True, active_skill=None）。

trace: `{stage: "world_state", status: "ok", detail: "<period> <time>"}`

### 6.2 capability_builder（新）

```
入: SKILL_REGISTRY + load_demo_guides() + state.world_state + cooldown_state
出: state.capability_context = {capabilities, limits, demo_session, recent_skill_results}
```

每輪重算（不 cache）：
1. SKILL_REGISTRY 27 條 → 各自套 §4.5 規則 → CapabilityEntry(kind=skill)
2. demo_guides.yaml 6 條 → 一律 explain_only → CapabilityEntry(kind=demo_guide)
3. demo_policy.yaml limits → 直接複製
4. state.recent_skill_results → 直接複製
5. demo_session placeholder → 全 false / 空 list

**`cooldown_remaining_s(skill)` 計算**（pawai_brain 自己算，不依賴 brain_node）：
```
last_completed_ts = max(r.ts for r in recent_skill_results
                        if r.name == skill and r.status == "completed",
                        default=None)
if last_completed_ts is None: return 0
cooldown_remaining = max(0, last_completed_ts + skill.cooldown_s - now())
```

注意：這是 pawai_brain 的「LLM 看得到的 cooldown 視圖」，與 brain_node 的真實 cooldown enforcement 是兩套（後者才是真 gate）。MVP 階段 5 筆 deque 對 27 條 skill 通常足夠覆蓋，未命中時視為 cooldown=0（不擋）。

trace: `{stage: "capability", status: "ok", detail: "27 skills + 6 guides"}`

### 6.3 memory_builder / llm_decision / json_validator / response_repair / output_builder

不動（沿用 Cut A 邏輯）。

### 6.4 skill_policy_gate（升級：兩條 kind 分支）

**關鍵**：passthrough / null / 非字串必須在 `lookup` 前處理。`chat_reply` / `say_canned` 雖然在 `SKILL_REGISTRY` 內 baseline=available_execute，但語意上是「LLM 已用 reply_text 表達」，不應被當成 executable skill proposal。

```python
PASSTHROUGH_SKILLS = frozenset({"chat_reply", "say_canned"})

def normalize_proposal(raw_skill, raw_args, capability_context) -> tuple[
    proposed_skill: str | None,
    proposed_args: dict,
    selected_demo_guide: str | None,   # ← 新
    trace_status: str | None,
    trace_detail: str,
]:
    args = raw_args if isinstance(raw_args, dict) else {}

    # 1. passthrough / null / 非字串 / 空字串 — 必須最先處理
    if not isinstance(raw_skill, str):
        return None, args, None, None, ""
    skill_str = raw_skill.strip()
    if not skill_str or skill_str in PASSTHROUGH_SKILLS:
        return None, args, None, None, ""

    # 2. 找 capability entry
    entry = lookup(skill_str, capability_context)

    # 3. 沒找到（不在 SKILL_REGISTRY 也不在 demo_guides）
    if entry is None:
        return skill_str, args, None, "rejected_not_allowed", skill_str

    # 4. demo_guide 分支
    if entry.kind == "demo_guide":
        return None, args, entry.name, "demo_guide", entry.name

    # 5. skill 分支 — 套 effective_status
    if entry.effective_status == "available":
        return entry.name, args, None, "proposed", entry.name
    if entry.effective_status == "needs_confirm":
        return None, args, None, "needs_confirm", entry.name
    # explain_only / blocked / cooldown / defer / studio_only / disabled
    return None, args, None, "blocked", f"{entry.name}:{entry.effective_status}"
```

### 6.5 output_builder（小改）

state.selected_demo_guide 寫進 trace（在 trace_emitter 階段），**不寫進 chat_candidate**。

---

## 7. /brain/chat_candidate schema

**不變**（Brain contract 保持乾淨）：
```json
{
  "session_id": "...",
  "reply_text": "...",
  "intent": "...",
  "selected_skill": null,
  "proposed_skill": "...",
  "proposed_args": {},
  "proposal_reason": "...",
  "engine": "langgraph",
  "source": "pawai_brain",
  "confidence": 0.8,
  "created_at": 1730...
}
```

---

## 8. /brain/conversation_trace 新 status

skill_gate 階段擴 status enum：
```
proposed                  — kind=skill, effective=available
accepted                  — brain_node 接受（既有）
accepted_trace_only       — brain_node 接 trace_only（既有）
blocked                   — kind=skill, effective ∈ {blocked, cooldown, defer, explain_only, studio_only, disabled}
cooldown                  — 細分 blocked（可選）
needs_confirm             — kind=skill, baseline=available_confirm   ← 新
demo_guide                — kind=demo_guide                           ← 新
rejected_not_allowed      — 名字不在 SKILL_REGISTRY 也不在 demo_guides（既有）
```

trace payload：
```json
{
  "session_id": "...",
  "engine": "langgraph",
  "stage": "skill_gate",
  "status": "demo_guide",
  "detail": "gesture_demo",
  "ts": 1730...
}
```

Studio Skill Trace Drawer 新增 chip color：
- `demo_guide` → 藍色
- `needs_confirm` → 黃色

---

## 9. recent_skill_results feedback loop

`/brain/skill_result` 已由 executive 發布（`interaction_executive_node.py:222-231`），payload 含：
```json
{
  "plan_id": "p-abcd1234",
  "step_index": 5,
  "status": "completed",         // 或 aborted / blocked_by_safety / step_failed / step_success / started / accepted
  "detail": "",
  "selected_skill": "self_introduce",   // ← skill 名稱直接帶在 payload，不需 plan_id 反查
  "priority_class": 2,
  "step_total": 6,
  "step_args": {},
  "timestamp": 1730...
}
```

`conversation_graph_node` 新增 subscriber：

```python
self.create_subscription(String, "/brain/skill_result", self._on_skill_result, 10)

# 只記終局狀態，避免被中間 step_started/step_success 灌爆 deque
TERMINAL_STATUSES = frozenset({"completed", "aborted", "blocked_by_safety", "step_failed"})

def _on_skill_result(self, msg):
    try:
        payload = json.loads(msg.data)
    except json.JSONDecodeError:
        return
    status = str(payload.get("status", ""))
    if status not in TERMINAL_STATUSES:
        return
    name = str(payload.get("selected_skill") or "").strip()
    if not name:
        return  # malformed; ignore
    self._skill_result_memory.add({
        "name": name,
        "status": status,
        "detail": str(payload.get("detail", ""))[:80],
        "ts": time.time(),
    })
```

`SkillResultMemory` 是 process-local deque（maxlen=5），與 `ConversationMemory` 並列但獨立。

每輪 capability_builder 把它複製進 `capability_context.recent_skill_results`。

**注意**：spec 不要求 executive 改 `/brain/skill_result` schema — `selected_skill` 已存在。

---

## 10. Persona prompt 升級

`tools/llm_eval/persona.txt` 加新段落：

```
## CapabilityContext 規則

每輪你會在 user message 結尾收到一個 capability_context JSON，列出你目前所有能力。
規則：

1. 你可以自由介紹任何 capability（包含 explain_only / disabled）
2. 你只能在 skill 提案中放 effective_status="available" 且 can_execute=true 的能力（kind=skill）
3. kind=demo_guide 是展示腳本，不會真的執行 motion；要使用時放在 skill 欄位即可，系統會自動分流
4. needs_confirm 的 skill 要請使用者比 OK 手勢或按 Studio 按鈕；reply 要主動說明
5. 一次最多提議一個 skill 或一個 demo_guide
6. 看到 recent_skill_results 上一個 skill completed → 可自然銜接「接下來要不要看 X」
7. 上一個 skill blocked / rejected → 簡短說明，不要重複要求同一個
8. 沒有使用者明確要求時，不要連續主動發動多個 motion
9. 使用者問「你會做什麼」時，主要列出 demo_guide 而不是 skill 內部名字（demo_guide 比較像「功能」概念）
```

---

## 11. 5/18 demo_status_baseline 27 條分類

```
available_execute (8):
  chat_reply, say_canned, show_status, self_introduce, careful_remind,
  wave_hello, sit_along, greet_known_person

available_confirm (2):
  wiggle, stretch

explain_only (5):
  stranger_alert, object_remark, nav_demo_point, approach_person, fallen_alert
  (+ 6 個 demo_guides: face_recognition / speech / gesture / pose / object / navigation)

studio_only (1):
  system_pause

disabled / retired (10):
  dance, follow_me, follow_person, go_to_named_place,    ← 4 個 SkillContract.bucket=disabled
  patrol_route, akimbo_react, knee_kneel_react,          ← 3 個 SkillContract.bucket=hidden
  enter_mute_mode, enter_listen_mode,                    ← 2 個 SkillContract.bucket=hidden
  acknowledge_gesture                                    ← 1 個 SkillContract.bucket=retired
  (effective_status 統一為 disabled，但 bucket 保留歷史語意；未來不要把 retired 當 disabled 重新開啟)

特殊 (1):
  stop_move (safety_gate 短路，不在 LLM 提案集，但 baseline=available_execute)
```

合計：27 真 skill + 6 demo guide = **33 條 capability**。

---

## 12. 檔案異動

### 新增

```
pawai_brain/
├── config/
│   ├── demo_guides.yaml
│   └── demo_policy.yaml
├── pawai_brain/
│   ├── capability/
│   │   ├── __init__.py
│   │   ├── registry.py              # 合併 SkillContract + DemoGuide → CapabilityContext
│   │   ├── world_snapshot.py        # WorldStateSnapshot dataclass + process-local cache
│   │   ├── skill_result_memory.py   # deque(maxlen=5)
│   │   ├── effective_status.py      # 計算規則純函式
│   │   └── demo_guides_loader.py    # yaml → DemoGuide list
│   └── nodes/
│       ├── world_state_builder.py
│       └── capability_builder.py
└── test/
    ├── test_capability_registry.py
    ├── test_effective_status.py
    ├── test_skill_result_memory.py
    └── test_capability_builder_smoke.py
```

### 修改

```
interaction_executive/interaction_executive/skill_contract.py
  + 4 欄位 (display_name / demo_status_baseline / demo_value / demo_reason)
  + 27 條 SKILL_REGISTRY 補預設值（依 §11 分類）

pawai_brain/pawai_brain/state.py
  + world_state, capability_context, recent_skill_results, selected_demo_guide

pawai_brain/pawai_brain/graph.py
  - 拔掉 context_builder, env_builder
  + 加入 world_state_builder, capability_builder

pawai_brain/pawai_brain/nodes/skill_policy_gate.py
  + kind 分支處理（demo_guide → selected_demo_guide）
  + effective_status 分支處理（needs_confirm / blocked）

pawai_brain/pawai_brain/nodes/output_builder.py
  + selected_demo_guide → trace（不進 chat_candidate）

pawai_brain/pawai_brain/conversation_graph_node.py
  + 訂 /brain/skill_result
  + WorldStateSnapshot 訂閱 /state/tts_playing, /state/reactive_stop/status, /state/nav/safety
  + 把 recent_skill_results / world_state 注入 graph initial_state

tools/llm_eval/persona.txt
  + CapabilityContext 規則段（§10）

pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx
  + demo_guide / needs_confirm chip 顏色

docs/pawai-brain/architecture/overview.md
  + 改 SkillContract 27 + DemoGuide 6 + CapabilityContext 三層敘述
```

### 不動

```
interaction_executive/interaction_executive/brain_node.py
interaction_executive/interaction_executive/interaction_executive_node.py
pawai-studio/gateway/studio_gateway.py
speech_processor/speech_processor/llm_bridge_node.py
```

---

## 13. 風險與 Fallback

| 風險 | Mitigation |
|------|-----------|
| capability_context 太大讓 LLM context bloat | 每條只給必要欄位（name/kind/display_name/effective_status/can_execute/reason/intro），27+6 條 ~1.5KB 可忍受；若 demo 觀察 LLM 截斷再改 trim 策略 |
| demo_guide 與 skill 名稱撞名 | registry.py 啟動時 assert SKILL_REGISTRY.keys() ∩ demo_guides.keys() == ∅ |
| world_snapshot 訂閱流量 | 全部 LATEST QoS + small payload，Jetson 無壓力 |
| LLM 一次提兩個 skill | skill_policy_gate 只取第一個 + trace `multiple_proposals_truncated`（既有邏輯擴增） |
| /brain/skill_result 來不及在下一輪到達 | recent_skill_results.add 是 best-effort；下一輪沒來就上一輪結果，自然 |
| recent_skill_results 滿 5 筆後舊 skill 的 cooldown 視圖消失 | 接受（MVP）；brain_node 真實 cooldown 仍會 enforce；Phase 2 改成 per-skill latched dict |
| `effective_status` 計算錯把 available → blocked | unit test 覆蓋每條規則；`test_effective_status.py` 驗各 baseline × world_state 組合 |
| 5/18 前測試不夠 | 5/13-14 場地測試前必跑全 33 條 baseline matrix 一次 |
| LangGraph 引入新節點導致 graph 失敗 | wrapper-level catch（既有）→ RuleBrain fallback；恢復 Cut A 行為 |
| YAML load 失敗 | demo_guides_loader 啟動時 try/except → 空 list + warn log，不阻塞啟動 |

---

## 14. 驗收（5/18 前必達）

**功能**：

- [ ] 「介紹你自己」→ reply 帶六大功能列表（自動引用 demo_guides.intro）；若 LLM 提案 self_introduce → brain_node trace `accepted_trace_only`（提案 self_introduce 是首選但非硬綁）
- [ ] 「你可以做什麼」→ reply 列出 6 個 demo_guide，引導使用者選
- [ ] 「展示手勢辨識」→ trace skill_gate=demo_guide / detail=gesture_demo + reply 引導比 OK
- [ ] 「跳舞」→ skill_gate trace=blocked, detail=dance:disabled + reply 自然解釋
- [ ] 「動一下」（LLM 選 wiggle）→ trace=needs_confirm + reply 請使用者比 OK
- [ ] self_introduce 跑完 → 下一輪 LLM 看到 recent_skill_results、自然銜接「接下來要不要看 X」
- [ ] 拔網路 → RuleBrain reply + capability_context 仍出現（純從 SKILL_REGISTRY/yaml 算）
- [ ] tts 播放中 → 所有 SAY-step skill effective=defer，LLM 不提案

**Studio**：
- [ ] Trace Drawer 顯示 demo_guide 藍 chip + needs_confirm 黃 chip
- [ ] 既有 proposed / accepted / blocked / rejected chip 不受影響

**回歸**：
- [ ] `pytest pawai_brain/test/ -v` 全綠（既有 54 + 新增 ~30）
- [ ] `pytest speech_processor/test/test_llm_bridge_node.py` 全綠
- [ ] `colcon build --packages-select pawai_brain interaction_executive` 通過
- [ ] legacy mode（CONVERSATION_ENGINE=legacy）行為不變

---

## 15. 不在本 spec 範圍

- ❌ OpenClaw workspace markdown files（`workspace/SOUL.md` / `SKILLS.md` / `DEMO.md`） — Cut B
- ❌ Hermes-lite procedural memory（skill success rate 統計） — Cut B
- ❌ `demo_session` state machine 真實 transitions — Cut B
- ❌ needs_confirm 真 confirm handoff（OK 手勢 → unblock） — Cut B
- ❌ Studio text input / face / pose / object 接 graph — Phase 2
- ❌ context_builder 重建 perception state（已被 world_state_builder 取代）
- ❌ `llm_bridge_node` 真瘦身（spec 2026-05-06 Cut 3）

---

## 16. Brainstorm 決策歷史（Q1-Q5）

```
Q1 scope: C — 5/18 MVP + Phase 2 forward path 同 spec，先做 MVP
Q2 demo_status: C — baseline (策略) + effective (runtime override) 兩層
Q3 feedback loop: A+ — recent_skill_results read-only + demo_session schema hook
Q4 baseline 分類: B- — 5 層 enum (available_execute / available_confirm /
                         explain_only / studio_only / disabled)
Q5 demo_guide 存放: B — 獨立 demo_guides.yaml；CapabilityContext 才合併視圖

User overrides on draft 1 (4 fixes):
1. selected_demo_guide 不進 /brain/chat_candidate（保 Brain contract 乾淨）
2. world_state_builder + capability_builder 分開保留
3. context_builder + env_builder 都拔掉，併入 world_state_builder
4. needs_confirm MVP 不做真 confirm handoff，只 trace + reply 引導
```

---

## 17. 後續工作（Phase 2+）

- OpenClaw workspace markdown：`workspace/SOUL.md`（persona）+ `SKILLS.md`（capability summary）+ `DEMO.md`（demo policy）注入 prompt 取代 inline
- Hermes-lite skill_result 統計：每 skill 滾動 success rate，effective_status 加 `unstable` enum（連續失敗 N 次 → 暫時降級到 explain_only）
- demo_session FSM：introducing → demonstrating → done，PAI 在沒人講話時 tick 主動接下一個
- needs_confirm 真 handoff：OK 手勢偵測 → /event/confirm → pawai_brain 把 pending_confirm skill 升級為 available
- CapabilityRegistry 獨立 module（與 BodyState 整合，PawClaw Phase B forward path）
