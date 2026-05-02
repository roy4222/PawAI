# PawClaw — Embodied Brain Evolution（Phase A → Phase B）

> **Status**: current（演進設計，與 MVS spec 並存）
> **Date**: 2026-04-27
> **Builds on**:
> - [`2026-04-27-pawai-brain-skill-first-design.md`](2026-04-27-pawai-brain-skill-first-design.md)（Brain MVS）
> - [`2026-04-11-pawai-home-interaction-design.md`](2026-04-11-pawai-home-interaction-design.md)（PawAI 系統定位）
> **Inspired by**: [openclaw/openclaw](https://github.com/openclaw/openclaw) — capability registry / agent loop / per-session queue / workspace files
> **Scope**: 把 PawAI Brain 從「demo script player」演進為「懂 Go2 身體的通用 robot agent」。命名為 **PawClaw**：PawAI body × OpenClaw-style harness engineering。

---

## 1. Context — 為什麼現在要寫這份

MVS spec（同日落地）解決了「Brain 與 Executive 的責任邊界、Skill-first 抽象、Studio Chat Console」三個結構問題，**但缺一塊**：

> **Brain 不知道自己的身體狀態**。
>
> - 不知道「現在能不能走」（AMCL 收斂？地圖載入？路徑安全？）
> - 不知道「nav_capability 有哪些 action 可用」（已有 4 action + 3 service，Brain 完全沒接）
> - 不知道「如果不能做，要怎麼跟使用者說明」（go_to_named_place 只是 disabled stub）

於是現階段 PawAI Brain 是**互動 Brain**，不是**通用 robot Brain**。對使用者說「去門口看一下」會得到沉默或誤判，而不是「我現在定位還不穩，先不要移動」。

OpenClaw 的核心 insight 對這個問題很直接 — 它把 capability、context、tool execution 抽象成 first-class 的 declarable artifact，讓 agent 在執行前就「知道自己能不能做」。我們可以偷它的 4 個 pattern，搭配 PawAI 既有的 Skill-first 架構，做出 **PawClaw — 居家機器狗版的 OpenClaw**。

但**不要全偷**。OpenClaw 是個人助手平台，多通道、plugin marketplace、sandbox container 對機器狗都不適用。挑「能讓 PawAI 變懂身體」的最小核心。

---

## 2. 兩階段演進

```
Phase A：Brain MVS（已有 spec/plan，5/16 demo 上場）
  目標：能演示 7 場景，Brain/Executive/Studio 三方解耦
  本 spec 對 Phase A 的唯一改動：
    go_to_named_place 從「disabled stub」升級為「正式註冊但 enabled_when 條件未滿足」
    → Studio 顯示「我為什麼不能做」而非單純灰階按鈕

Phase B：PawClaw Embodied Brain V1（5/16 後，5/18 展示前 or 6 月答辯前）
  目標：Brain 知道身體狀態、知道能做什麼、知道為什麼不能做
  新增：
    - CapabilityRegistry（SkillContract 擴充 enabled_when predicates）
    - BodyState（WorldState 擴充 localization / map / battery / nav_ready）
    - Nav Skill Pack（go_to_named_place / go_to_relative / run_patrol_route / pause / resume / cancel）
    - SkillPlanner（從 brain_node 抽出，rule-based 仍為主，LLM 為輔）
    - Workspace files（BODY.md / SKILLS.md / SAFETY.md / PLACES.md / DEMO_MODE.md）
    - Tool schema export（為 Phase C LLM function calling 鋪路）

Phase C（不在本 spec）：LLM-augmented Skill Selection
  Brain 把 SKILL_REGISTRY 餵給 LLM 做 function calling
  LLM 提案 → Brain rule 驗證 → SafetyLayer.validate → Executive
  仍然「LLM 不直接控狗」，只是 LLM 變成另一個 proposal source
```

**關鍵原則**：Phase A → Phase B 是**加法**不是改寫。MVS 程式碼不會被廢；新增的 CapabilityRegistry、BodyState、Nav Skill Pack 都是擴充點。

---

## 3. PawClaw 核心架構

```
┌─────────────────────────────────────────────────────────────────┐
│  Inputs                                                          │
│  /event/* (perception)  /brain/text_input  /brain/skill_request  │
│  /brain/chat_candidate  (Phase C: LLM tool_call)                 │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Brain Context Builder                                            │
│  - 多模態事件聚合                                                │
│  - BodyState snapshot（含 localization / map / battery / nav）   │
│  - CapabilityRegistry view（enabled / disabled / reasons）       │
│  - Workspace files context（BODY.md / DEMO_MODE.md 等）          │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ SkillPlanner（rule-first；Phase C: + LLM proposal）              │
│  1. SafetyLayer.hard_rule(event)  ← 永遠先                       │
│  2. CriticalAlertRule              ← ALERT 可中斷 SEQUENCE       │
│  3. Active sequence guard                                        │
│  4. Capability predicate filter   ← 從 enabled skills 中選        │
│  5. Rule table match → SkillPlan                                 │
│  6. Chat fallback (1500ms LLM wait)                              │
└────────────────┬────────────────────────────────────────────────┘
                 ▼  /brain/proposal (SkillPlan)
┌─────────────────────────────────────────────────────────────────┐
│ Capability Validator                                             │
│  1. SafetyLayer.validate(plan, body_state)                       │
│  2. Skill.enabled_when 全部通過？                                │
│  3. Skill.cooldown 檢查                                          │
│  4. 若 reject → emit /brain/skill_result(BLOCKED_BY_SAFETY,      │
│                                          reason="amcl_red"      │
│                                          + suggestion="先做定位") │
│     → Brain 自動產 chat_reply 解釋給使用者                        │
│  5. 若 accept → enqueue                                          │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│ Executive（dispatcher，3 executors）                             │
│  SAY    → /tts                                                   │
│  MOTION → /webrtc_req (sport)                                    │
│  NAV    → nav_capability action client（4 actions + 3 services） │
└────────────────┬────────────────────────────────────────────────┘
                 ▼
            Go2 Pro / Nav2 stack
```

**新增層**：Brain Context Builder + Capability Validator。其餘是 MVS 既有的擴充（多吃幾個 state topic、多幾條 skill）。

---

## 4. Capability Registry（OpenClaw 偷 #1）

擴充 MVS 的 `SkillContract`，加上 **enabled_when 述詞**：能力是否啟用，由 BodyState 動態判定，不是硬編 boolean。

```python
# skill_contract.py（Phase B 擴充）

@dataclass
class CapabilityPredicate:
    """述詞：以 BodyState 為輸入，回傳 (ok, reason)。"""
    name: str
    check: Callable[["BodyState"], tuple[bool, str]]


@dataclass
class SkillContract:
    name: str
    steps: list[SkillStep]
    priority_class: PriorityClass

    # MVS 既有
    safety_requirements: list[str] = field(default_factory=list)
    cooldown_s: float = 0
    timeout_s: float = 8.0
    fallback_skill: str | None = None
    description: str = ""
    args_schema: dict = field(default_factory=dict)
    ui_style: Literal["normal","alert","safety"] = "normal"

    # Phase B 新增
    enabled_when: list[CapabilityPredicate] = field(default_factory=list)
    static_enabled: bool = True       # 取代舊 enabled flag（永久關閉）
    requires_confirmation: bool = False   # 高風險動作需 Studio confirm
    risk_level: Literal["low","medium","high"] = "low"


def is_enabled(contract: SkillContract, body: "BodyState") -> tuple[bool, list[str]]:
    """回傳是否啟用 + 所有不通過的 reasons。
    Studio 可顯示給使用者：『我不能做 X 因為 Y、Z』。
    """
    if not contract.static_enabled:
        return False, ["statically_disabled"]
    reasons: list[str] = []
    for pred in contract.enabled_when:
        ok, reason = pred.check(body)
        if not ok:
            reasons.append(reason)
    return (len(reasons) == 0, reasons)
```

**範例 — nav skill 怎麼宣告 enabled_when**：

```python
SKILL_REGISTRY["go_to_named_place"] = SkillContract(
    name="go_to_named_place",
    steps=[SkillStep(NAV, {"action": "goto_named", "args": {"name_template": "{place}"}})],
    priority_class=PriorityClass.SKILL,
    args_schema={"place": "string"},
    enabled_when=[
        CapabilityPredicate("nav_stack_ready",
            lambda b: (b.nav_stack_ready, "nav stack 未啟動") if not b.nav_stack_ready else (True, "")),
        CapabilityPredicate("amcl_converged",
            lambda b: (b.amcl_covariance_ok, "AMCL 定位未收斂") if not b.amcl_covariance_ok else (True, "")),
        CapabilityPredicate("map_loaded",
            lambda b: (b.map_loaded, "地圖未載入") if not b.map_loaded else (True, "")),
        CapabilityPredicate("battery_ok",
            lambda b: (b.battery_pct > 20, f"電量過低 {b.battery_pct}%") if b.battery_pct <= 20 else (True, "")),
    ],
    requires_confirmation=False,
    risk_level="medium",
    description="導航到已命名的地點",
)
```

Studio Chat 對應顯示：

```
[user]   去門口看一下
[brain]  intent: navigate · candidate skill: go_to_named_place(place="門口")
[capability]  ✗ blocked_by_capability
              · AMCL 定位未收斂
              · 地圖未載入
[brain]  fallback: chat_reply
[say]    我現在還不能移動 — 定位還沒收斂、地圖也還沒載入。要先建圖嗎？
```

**這就是「懂自己身體」**：Brain 在發 proposal **之前**已經知道做不到，並能用人話解釋。

---

## 5. BodyState（OpenClaw context engine 偷 #2）

擴充 MVS 的 `WorldState`，加入 robot-body specific fields：

```python
# body_state.py（取代 / 包裝 world_state.py）

@dataclass
class BodyStateSnapshot:
    # MVS WorldState fields
    obstacle: bool = False
    emergency: bool = False
    fallen: bool = False
    tts_playing: bool = False
    nav_safe: bool = True

    # Phase B 新增 — localization
    map_loaded: bool = False
    amcl_active: bool = False
    amcl_covariance_ok: bool = False         # < 閾值代表收斂
    amcl_pose_age_s: float = 999.0           # 多久沒更新

    # Phase B 新增 — nav stack
    nav_stack_ready: bool = False            # nav2 lifecycle = active
    nav_action_running: str | None = None    # 正在跑哪個 action
    nav_route_active: str | None = None      # route_id

    # Phase B 新增 — sensors
    rplidar_alive: bool = False
    d435_alive: bool = False

    # Phase B 新增 — system
    battery_pct: float = 100.0
    cpu_temp_c: float = 0.0
    last_update: float = field(default_factory=time.time)


class BodyState:
    """Thread-safe BodyState aggregator. Subscribes to all body-relevant topics."""

    def __init__(self, node: Node):
        self._node = node
        self._lock = threading.Lock()
        self._snap = BodyStateSnapshot()

        # 既有 (MVS)
        node.create_subscription(Bool, "/state/tts_playing", self._on_tts, _TL)
        node.create_subscription(String, "/state/reactive_stop/status", self._on_reactive, _BE)
        node.create_subscription(String, "/state/nav/safety", self._on_nav_safety, _BE)

        # Phase B 新增
        node.create_subscription(PoseWithCovarianceStamped, "/amcl_pose", self._on_amcl, _RE)
        node.create_subscription(String, "/state/nav/heartbeat", self._on_nav_hb, _BE)
        node.create_subscription(String, "/state/nav/status", self._on_nav_status, _BE)
        node.create_subscription(LaserScan, "/scan", self._on_lidar_alive, _BE)
        node.create_subscription(Image, "/camera/color/image_raw", self._on_d435_alive, _BE)
        node.create_subscription(Float32, "/state/battery", self._on_battery, _BE)
```

`/amcl_pose` 的 covariance 矩陣對角線元素（x/y variance）小於閾值（例如 0.5）即視為「收斂」。`/state/nav/heartbeat`（既有，1Hz）告訴你 nav stack 活著。`/state/nav/status`（10Hz JSON）告訴你正在跑哪個 action。

**重點**：BodyState 是 **read-only snapshot**，給 Brain Context Builder 與 Capability Validator 用，不存決策狀態（決策狀態在 brain_node 裡）。

---

## 6. Nav Skill Pack（正式整合導航避障）

對應現有 nav_capability 的 4 actions + 3 services：

```python
# skill_contract.py 內 SKILL_REGISTRY 新增 6 條

SKILL_REGISTRY["go_to_named_place"] = SkillContract(
    name="go_to_named_place",
    steps=[SkillStep(NAV, {"action": "goto_named", "args": {"name_template": "{place}"}})],
    priority_class=PriorityClass.SKILL,
    args_schema={"place": "string"},
    enabled_when=[NAV_STACK_READY, AMCL_CONVERGED, MAP_LOADED, BATTERY_OK],
    safety_requirements=["not_emergency", "not_obstacle"],
    risk_level="medium",
    description="導航到已命名的地點（如:廚房、門口）",
)

SKILL_REGISTRY["go_to_relative"] = SkillContract(
    name="go_to_relative",
    steps=[SkillStep(NAV, {"action": "goto_relative",
                            "args": {"distance_template": "{distance}", "yaw_template": "{yaw}"}})],
    priority_class=PriorityClass.SKILL,
    args_schema={"distance": "float", "yaw": "float"},
    enabled_when=[NAV_STACK_READY, AMCL_CONVERGED],   # 不需要地圖
    safety_requirements=["not_emergency", "not_obstacle"],
    risk_level="medium",
    description="向前/相對方向走一段距離",
)

SKILL_REGISTRY["run_patrol_route"] = SkillContract(
    name="run_patrol_route",
    steps=[SkillStep(NAV, {"action": "run_route", "args": {"route_id_template": "{route_id}"}})],
    priority_class=PriorityClass.SEQUENCE,
    args_schema={"route_id": "string"},
    enabled_when=[NAV_STACK_READY, AMCL_CONVERGED, MAP_LOADED, ROUTE_EXISTS, BATTERY_OK],
    safety_requirements=["not_emergency", "not_obstacle"],
    timeout_s=300.0,
    risk_level="high",
    requires_confirmation=True,    # 巡邏前要 Studio confirm
    description="執行命名巡邏路線",
)

SKILL_REGISTRY["pause_navigation"] = SkillContract(
    name="pause_navigation",
    steps=[SkillStep(NAV, {"action": "pause_service"})],   # 走 service 不是 action
    priority_class=PriorityClass.SAFETY,
    description="暫停目前導航（保留可恢復）",
)

SKILL_REGISTRY["resume_navigation"] = SkillContract(
    name="resume_navigation",
    steps=[SkillStep(NAV, {"action": "resume_service"})],
    priority_class=PriorityClass.SKILL,
    enabled_when=[NAV_STACK_READY],
    description="恢復暫停的導航",
)

SKILL_REGISTRY["cancel_navigation"] = SkillContract(
    name="cancel_navigation",
    steps=[SkillStep(NAV, {"action": "cancel_service"})],
    priority_class=PriorityClass.SAFETY,
    description="完全取消目前導航 / 路線",
)
```

**Executive NAV dispatch 擴充**：

```python
def _dispatch_nav(self, args: dict) -> bool:
    action = args["action"]
    if action == "goto_named":
        from go2_interfaces.action import GotoNamed
        client = self._get_action_client("/nav/goto_named", GotoNamed)
        goal = GotoNamed.Goal()
        goal.name = args.get("name", "")
        client.send_goal_async(goal, feedback_callback=self._on_nav_feedback)
        return True
    elif action == "goto_relative":
        from go2_interfaces.action import GotoRelative
        # ... 類似
    elif action == "run_route":
        # RunRoute action
    elif action == "pause_service":
        from std_srvs.srv import Trigger
        client = self._get_service_client("/nav/pause", Trigger)
        client.call_async(Trigger.Request())
        return True
    # ...
```

**Brain 新規則**：自然語言 → nav skill。

```python
RULES.append(NavRule(
    keywords_to_skill={
        ("去", "前往", "走到"): "go_to_named_place",
        ("巡邏", "巡視", "繞一圈"): "run_patrol_route",
        ("暫停", "停一下"): "pause_navigation",   # 注意：純「停」仍由 SAFETY hard_rule 處理 stop_move
        ("繼續", "再開始"): "resume_navigation",
        ("取消", "別走了"): "cancel_navigation",
    },
    place_extractor=...,    # 從 transcript 抽 "{place}" 參數
))
```

---

## 7. Workspace Files（OpenClaw AGENT.md 偷 #3）

OpenClaw 有 `AGENTS.md / SOUL.md / TOOLS.md / memory/`，PawClaw 對應：

```
workspace/
├── BODY.md          # Go2 身體能力、限制、運動 api 清單
├── SKILLS.md        # SKILL_REGISTRY 人類可讀版（含 enabled_when 解釋）
├── SAFETY.md        # 永遠不能做的清單 + 為什麼
├── PLACES.md        # 已命名地點 + 路線（從 named_poses + routes 衍生）
└── DEMO_MODE.md     # Demo 場景配置（5/16 / 5/18 / 答辯）
```

**MVS 階段：純人類可讀 markdown**（給工程師、組員、教授看）。
**Phase C 階段：餵進 LLM context**（讓 LLM 推理時知道身體能力與安全規則）。

範例 `BODY.md`：

```markdown
# PawAI Body Capabilities

## Hardware
- Unitree Go2 Pro
- Jetson Orin Nano 8GB
- Intel RealSense D435 (RGB-D)
- RPLIDAR A2M12 (10 Hz, 360°)
- 外接 USB 麥克風 / 喇叭

## Motion API（white-listed sport api_ids）
| name | api_id | 風險 | 何時用 |
|---|---|---|---|
| stop_move | 1003 | low | safety stop / pause action |
| sit | 1009 | low | 待命姿勢 |
| stand | 1004 | low | 站起 |
| balance_stand | 1002 | low | 平衡站立（重心穩定） |
| hello | 1016 | low | 揮手互動 |
| content | 1020 | low | 開心搖擺 |

## BANNED API
1030 (FrontFlip), 1031 (FrontJump), 1301 (Handstand) — 居家環境風險過高

## Locomotion limits
- 最低速度 0.5 m/s（sport mode 才會抬腳）
- 最大速度 1.0 m/s（demo 限速）
- 最小轉彎半徑 ~0.6 m

## Sensor coverage
- D435 視角 ~87° H × 58° V，遠不到 360°
- RPLIDAR 360° 但無高度資訊
- 跌倒偵測靠 D435 RGB → MediaPipe Pose
```

範例 `PLACES.md`（從 `~/elder_and_dog/runtime/nav_capability/named_poses/` 動態產生）：

```markdown
# PawAI Known Places

| name | x | y | yaw | last_seen |
|---|---|---|---|---|
| entrance | 1.2 | 0.3 | 1.57 | 2026-04-26 22:30 |
| kitchen | 3.4 | -0.8 | 0.0 | 2026-04-26 22:32 |
| sofa | 0.5 | -2.1 | -1.57 | 2026-04-26 22:33 |

## Routes
- patrol_living_room: [entrance, sofa, entrance]
```

---

## 8. SkillPlanner（從 brain_node 抽出）

MVS 的 `brain_node._on_speech_intent / _on_gesture / ...` 把規則邏輯散在 callback 內。Phase B 抽成獨立 `skill_planner.py`：

```python
# skill_planner.py

class SkillPlanner:
    def __init__(self, registry: dict, body: BodyState, safety: SafetyLayer):
        self._registry = registry
        self._body = body
        self._safety = safety

    def plan_for(self, event: BrainEvent) -> SkillPlan | None:
        """Pure function: event → plan. No ROS2 dependency."""
        # 1. Safety hard rule
        if plan := self._safety.hard_rule(event):
            return plan
        # 2. Critical alert
        if plan := self._match_alert(event):
            return plan
        # 3. Filter to enabled skills
        body_snap = self._body.snapshot()
        candidates = [name for name, c in self._registry.items()
                      if is_enabled(c, body_snap)[0]]
        # 4. Rule match within enabled set
        if plan := self._match_rules(event, candidates):
            return plan
        return None

    def explain_unavailability(self, skill_name: str) -> str:
        """產生人類可讀的『為什麼不能做 X』。"""
        contract = self._registry[skill_name]
        ok, reasons = is_enabled(contract, self._body.snapshot())
        if ok:
            return ""
        return f"{skill_name} 目前不可用：{'、'.join(reasons)}"
```

**好處**：
- `brain_node.py` 變薄（只負責 ROS2 wiring）
- planner 純 Python 可獨立測試（給定 event + body snap → 預期 plan）
- Phase C 可加 `LLMSkillPlanner` 平行存在，由設定切換

---

## 9. Tool Schema Export（為 Phase C 鋪路）

OpenClaw 的 tool schema 是 OpenAI function-calling 格式。MVS 不用 LLM，但可以**現在就把 SKILL_REGISTRY 自動轉成 schema**，這樣 Phase C 加 LLM 時不必再寫一輪：

```python
# skill_contract.py

def export_openai_tools(registry: dict, body: BodyStateSnapshot) -> list[dict]:
    tools = []
    for name, contract in registry.items():
        ok, _reasons = is_enabled(contract, body)
        if not ok:
            continue   # LLM 只看當前可用的 skill
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": contract.description,
                "parameters": _to_jsonschema(contract.args_schema),
            },
        })
    return tools
```

Studio Skill Trace Drawer 可加一個 debug 視窗顯示「LLM 此刻會看到的 tools」，給工程師 / 教授 demo 看。

---

## 10. PawClaw vs OpenClaw 對照表

| OpenClaw 概念 | PawClaw 對應 | 實作位置 |
|---|---|---|
| Tool registry | SKILL_REGISTRY | `skill_contract.py` |
| Tool schema (OpenAI) | `export_openai_tools()` | `skill_contract.py`（Phase B 加） |
| allow/deny lists | `enabled_when` predicates | `skill_contract.py`（Phase B 加） |
| Agent loop | brain_node + executive_node | 既有（MVS） |
| Per-session queue lane | SkillQueue + push_front preempt | 既有（MVS） |
| AGENTS.md / SOUL.md workspace | BODY.md / SKILLS.md / SAFETY.md | `workspace/`（Phase B 加） |
| Memory persistence | （Phase D 才做，MVS/B 都不做） | — |
| Tool event stream | /brain/skill_result lifecycle | 既有（MVS） |
| Safety hard rules | SafetyLayer.hard_rule | 既有（MVS） |
| Pre-action validation | SafetyLayer.validate + CapabilityValidator | MVS 部分有，Phase B 擴充 |
| Multi-channel bridges | （不抄）只有 Studio | — |
| Plugin marketplace | （不抄）ROS2 package 即 plugin | — |
| Sandbox container | （不抄）信任邊界由 robot 物理特性提供 | — |
| Multi-agent routing | （不抄）單 Brain + 單 Executive | — |

---

## 11. 漸進實作計畫（不打斷 MVS）

### Phase A：MVS 不動 + 一個微調

**唯一需要動 MVS plan 的地方**：把 `go_to_named_place` 從「`enabled=False`」改成「正式註冊 + `enabled_when` 永遠 false（暫用 lambda: (False, "Phase B 才整合 nav")）」。這樣 Studio 已經能顯示「為什麼不能做」的人話訊息，為 Phase B 鋪路。

具體 patch：在 MVS plan Task 1.1 Step 3 SKILL_REGISTRY 那段，把 `go_to_named_place` 改成：

```python
"go_to_named_place": SkillContract(
    name="go_to_named_place",
    steps=[SkillStep(ExecutorKind.NAV, {"action": "goto_named", "args": {}})],
    priority_class=PriorityClass.SKILL,
    description="導航到已命名的地點（Phase B 才正式整合）",
    static_enabled=True,     # 不再用 enabled=False
    enabled_when=[
        # 暫時永遠 false 但有人類可讀 reason
        CapabilityPredicate("phase_b_pending",
            lambda b: (False, "Phase B 才整合 nav_capability")),
    ],
    args_schema={"place": "string"},
),
```

對應 SkillContract dataclass 也要早加 `enabled_when` field（即使 MVS 大多 skill 都用空 list）。這個小改動讓 Phase A → Phase B 的轉換是 add field value，不是 schema migration。

### Phase B：完整 PawClaw 化（5/16 demo 後）

**新增檔案**：
- `interaction_executive/interaction_executive/body_state.py`（擴 / 取代 world_state.py）
- `interaction_executive/interaction_executive/capability.py`（CapabilityPredicate / is_enabled / 標準 predicate 庫）
- `interaction_executive/interaction_executive/skill_planner.py`（從 brain_node 抽出）
- `interaction_executive/interaction_executive/nav_skill_executor.py`（NAV step 分派 + action client 管理）
- `workspace/BODY.md` / `SKILLS.md` / `SAFETY.md` / `PLACES.md` / `DEMO_MODE.md`
- `scripts/generate_workspace_docs.py`（從 SKILL_REGISTRY 自動生 SKILLS.md，從 named_poses 自動生 PLACES.md）

**修改**：
- `interaction_executive/interaction_executive/skill_contract.py`：加 `CapabilityPredicate` / `enabled_when` / `requires_confirmation` / `risk_level` / `static_enabled` / `is_enabled()` / `export_openai_tools()`
- `interaction_executive/interaction_executive/brain_node.py`：planner 邏輯外提 + 在 reject path 自動發 chat_reply 解釋
- `interaction_executive/interaction_executive/interaction_executive_node.py`：NAV executor 完整實作
- 新增 6 條 nav skill 進 SKILL_REGISTRY
- Studio：Skill Trace Drawer 新增 「Capability Status」分頁，列每個 skill 的 enabled/reason；Skill Buttons 灰階按鈕 hover 顯示 reason
- `docs/contracts/interaction_contract.md` v2.6：新增 BodyState / nav skill schema

**驗收**：
- 對 PawAI 說「去廚房」未啟動 nav stack → Studio Chat 出現「我現在還不能移動，因為 nav stack 沒啟動」
- 啟動 nav stack 但 AMCL 未收斂 → 「定位還沒收斂」
- 全部就緒 → 真的走過去
- 巡邏時 SAFETY 中斷可恢復（cancel + resume）
- 所有 6 條 nav skill 各有 unit test 與 mocked action client integration test

---

## 12. 不做 / 不要做

| 不做 | 原因 |
|---|---|
| OpenClaw multi-channel（WhatsApp / Slack / Discord） | PawAI 場景是局部居家，Studio WebSocket 足夠 |
| OpenClaw plugin marketplace | ROS2 package 即 plugin；不需第三方分發 |
| Docker / SSH sandbox | 機器人 runtime 在 Jetson 信任邊界內，不適合 |
| Multi-agent sub-goal decomposition | Brain MVS 邏輯清晰；多 agent 反而難 debug |
| Long-term memory persistence（人物 profile / 對話歷史） | 4/13 deadline + 5/16 demo 太緊；Phase D 評估 |
| Hot-reload skills | SKILL_REGISTRY 是 Python dict，restart cost 可接受 |
| Browser control / shell exec tools | 機器人不需要這類 tool |
| Voice cloning / wake word | speech_processor 已有 SenseVoice + Whisper + edge-tts |

---

## 13. 答辯論述升級（從 MVS 視角 → PawClaw 視角）

| 面向 | MVS 論述 | PawClaw 論述 |
|---|---|---|
| 系統架構 | 三層 Brain + 單一動作出口 | 三層 Brain + Capability Registry + 身體狀態感知 |
| Agent design | Skill-first、harness-oriented | Embodied agent — 知道自己能做什麼、不能做什麼、為什麼 |
| HRI | 多模態感知 × Skill 編排 | 多模態 × 能力感知 × 身體可解釋性（「我為什麼不能做 X」） |
| Edge-Cloud | 4 級降級鏈 | 4 級降級 + Capability-aware 降級（nav 掛 ≠ 全部掛） |
| Robotics 產品化 | Skill Contract + 安全閘 | Skill Contract + Capability Predicate + Workspace docs（自描述系統） |
| 對標業界 | （MVS 不提） | OpenClaw harness engineering pattern × Embodied AI |

關鍵句：

> **PawClaw 不是 OpenClaw + Go2，而是 OpenClaw 的 harness engineering pattern 套用到 robot body 場域 — 能力宣告、能力驗證、能力解釋全部 first-class。**

---

## 14. 文件索引

| 文件 | 用途 |
|---|---|
| **本文件** | PawClaw 演進路線、Phase A → B 設計 |
| `docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md` | Brain MVS 技術 spec（Phase A） |
| `docs/pawai-brain/plans/2026-04-27-pawai-brain-skill-first.md` | Brain MVS 實作 plan（Phase A） |
| `docs/pawai-brain/architecture/overview.md` | Brain × Studio 整合總覽（已對外可讀） |
| `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-11-pawai-home-interaction-design.md` | PawAI 系統定位（產品 / 願景 / 4/11 三層） |
| `docs/mission/README.md` | 專案方向、時程、分工 |

未來可能新增（Phase B 正式啟動時）：
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/plans/2026-XX-XX-pawclaw-embodied-brain-v1.md` — Phase B 實作 plan
- `workspace/BODY.md` / `SKILLS.md` / `SAFETY.md` / `PLACES.md` / `DEMO_MODE.md` — agent workspace files
