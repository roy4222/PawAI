# PawClaw Master Integration Plan

> **Status**: current（唯一入口 / single source of integration truth）
> **Date**: 2026-04-28
> **Author**: 盧柏宇（Roy）
> **Scope**: 把 PawAI 的 7 個模組（人臉 / 語音 / 手勢 / 姿勢 / 物體 / 導航 / Brain×Studio）整合成「機器狗版 OpenClaw」的單一作戰圖。本文件**不重複**既有 spec / plan 的施工細節，只做整合視角、Phase 排序、Done criteria。
>
> **與既有 4 份文件的關係**：
> - 本文件 = 唯一入口（從這裡開始讀）
> - [`docs/architecture/pawai-brain-studio-overview.md`](../../architecture/pawai-brain-studio-overview.md) = 對外總覽（教授 / 答辯讀物）
> - [`specs/2026-04-27-pawai-brain-skill-first-design.md`](../specs/2026-04-27-pawai-brain-skill-first-design.md) = Phase A 設計藍圖
> - [`plans/2026-04-27-pawai-brain-skill-first.md`](2026-04-27-pawai-brain-skill-first.md) = Phase A 實作 plan（34 task，已執行 Phase 0）
> - [`specs/2026-04-27-pawclaw-embodied-brain-evolution.md`](../specs/2026-04-27-pawclaw-embodied-brain-evolution.md) = Phase B 演進 spec

---

## 1. North Star

> **PawAI Brain = 機器狗版 [OpenClaw](https://github.com/openclaw/openclaw)。**
>
> 使用者用自然語言跟機器狗自然互動。Brain **知道 Go2 能做什麼、不能做什麼、為什麼**。所有能力都以 **Skill** 暴露給 LLM 與 Studio；危險動作永遠經過 deterministic safety layer。
>
> 應用場景：**居家互動（70%） + 守護犬（30%）**。

**三個不可動搖的設計原則**：

1. **Skill-first** — 所有能力（聊天 / 動作 / 導航 / 警示 / 序列）都是 `SkillContract`。LLM 只能透過 skill registry 操作機器狗。
2. **單一動作出口** — sport `/webrtc_req` 只能由 `interaction_executive_node` 發。任何 LLM、任何 Studio button、任何 perception event 都不准繞過。
3. **Capability-aware** — Brain 在發 plan 之前**已知道做不到**。對使用者說「去廚房」時，會回「定位還沒收斂」而不是沉默或亂走。

---

## 2. 七大模組整合圖

```
┌─────────────────────────────────────────────────────────────────┐
│  Layer 2 — 感知（5 模組，全部已上機）                              │
│                                                                 │
│  人臉    │ 語音    │ 手勢    │ 姿勢    │ 物體                    │
│  ────────┼─────────┼─────────┼─────────┼─────────                │
│  YuNet+  │ Sense-  │ Media-  │ Media-  │ YOLO26n+                │
│  SFace   │ Voice + │ Pipe    │ Pipe    │ TRT FP16                │
│          │ Whisper │         │ Pose    │                         │
│  95% ✅  │ 90% ✅  │ 90% ✅  │ 95% ✅  │ 70% ✅                  │
│   ↓        ↓        ↓        ↓        ↓                          │
│ /event/face_identity                                             │
│ /event/speech_intent_recognized                                  │
│ /event/gesture_detected                                          │
│ /event/pose_detected                                             │
│ /event/object_detected                                           │
│ /state/perception/face                                           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 3 — Brain × Executive × Studio（要做的就是這個）          │
│                                                                 │
│  ┌───────────────────────────────────────────┐                  │
│  │ PawAI Brain (brain_node) — Phase A 規則  │                  │
│  │    Phase B + Capability Validator         │                  │
│  │    Phase C + LLM Planner（function call）│                  │
│  └─────────────────────┬─────────────────────┘                  │
│                        ▼  /brain/proposal (SkillPlan)            │
│  ┌───────────────────────────────────────────┐                  │
│  │ Interaction Executive — 唯一動作出口       │                  │
│  │   SAY / MOTION / NAV 三個 executor         │                  │
│  └─────────────────────┬─────────────────────┘                  │
│                        ▼                                        │
│  ┌───────────────────────────────────────────┐                  │
│  │ PawAI Studio — Brain Skill Console        │                  │
│  │   8 種 bubble + Skill Buttons + Trace     │                  │
│  └───────────────────────────────────────────┘                  │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  Layer 1 — 執行（已上機 / 開發中）                                │
│  Go2 sport API（locomotion）                                    │
│  Go2 Megaphone audio（4001-4004）                               │
│  nav_capability platform（4 actions / 3 services / 3 states）   │
│   ↑                                                              │
│   └─── 導航避障：硬體 mount blocked，5/9 起執行 7 階段 roadmap   │
└─────────────────────────────────────────────────────────────────┘
```

**整合視角的關鍵 insight**：

- **6 個模組已經做完或在收尾**（face / speech / gesture / pose / object 完成、nav 進行中）
- **缺的是「整合者」** — Brain × Executive × Studio 把它們縫成一個 agent
- **Phase A 不是新功能 demo，而是把已存在的能力暴露為 Skill**

---

## 3. Capability Registry — 七大模組變成 Skill

每個模組的能力都註冊成 `SkillContract`，讓 LLM 可以選用：

```
Skill = name + args_schema + executor + safety_requirements
      + enabled_when + risk_level + cooldown + fallback
```

完整 dataclass 見 [Phase A spec §3](../specs/2026-04-27-pawai-brain-skill-first-design.md#3-skill-模型核心)；Phase B 擴充欄位見 [PawClaw spec §4](../specs/2026-04-27-pawclaw-embodied-brain-evolution.md#4-capability-registryopenclaw-偷-1)。

**七大模組的 Skill 暴露清單**：

| 模組 | 提供的 Event/State | Phase A skills | Phase B skills | Phase C 補完 |
|------|------------------|---------------|----------------|--------------|
| **語音功能** | `/event/speech_intent_recognized` `/state/interaction/speech` | `chat_reply` `say_canned` `stop_move`（語音「停」） | — | LLM 透過 `/brain/chat_candidate` |
| **人臉辨識** | `/event/face_identity` `/state/perception/face` | `greet_known_person(name)` `stranger_alert` | + `wait_for_owner` | LLM 用人臉 context 選擇問候語 |
| **手勢辨識** | `/event/gesture_detected` | `acknowledge_gesture(type)`（wave/ok/thumbs_up） | + `gesture_navigation`（指向哪走過去） | — |
| **姿勢辨識** | `/event/pose_detected` | `fallen_alert` | + `assist_fallen_person` | — |
| **物體辨識** | `/event/object_detected` | `comment_on_object(class)`（cup→「要喝水嗎？」） | + `find_object(class)` `bring_object(class)` | LLM 主動使用 |
| **導航避障** | `/state/nav/safety` `/state/nav/heartbeat` `/state/nav/status` | `go_to_named_place`（disabled stub） | **6 條 nav skill**：goto_named / goto_relative / run_route / pause / resume / cancel | LLM 規劃複合路徑 |
| **Brain×Studio** | `/brain/*` `/state/pawai_brain` | 9 條 MVS skill + META_SKILL self_introduce | + Capability Validator + BodyState | LLM function calling |

**這就是 OpenClaw tool registry 的 PawAI 版本** — 唯一差別是：
- 工具不是 web API、不是 shell command，是**機器狗的具身能力**
- 安全層永遠在 LLM 之後驗證一次（不只 prompt-time，還有 runtime validate）

---

## 4. Phase A — 5/16 Demo MVS（進行中）

**目標**：把 Skill 抽象、單一出口、Studio 觀測、Safety 框架立起來。**這是 Phase B/C 的地基，不是終點**。

**範圍**：演示 7 場景證明系統會分辨聊天 / 動作 / 警示。

| 場景 | 觸發模組 | Skill | 狀態 |
|------|---------|-------|------|
| 你好 | 語音 | `chat_reply` | ⏳ Phase 1 |
| 停 | 語音 | `stop_move`（safety hard rule） | ⏳ Phase 1 |
| 介紹自己 | 語音 | `self_introduce`（10 步 META） | ⏳ Phase 1 |
| 揮手回應 | 手勢 | `acknowledge_gesture(wave)` | ⏳ Phase 1 |
| 熟人問候 | 人臉 | `greet_known_person(alice)` | ⏳ Phase 1 |
| 陌生人警示 | 人臉 | `stranger_alert`（≥3s） | ⏳ Phase 1 |
| 跌倒警示 | 姿勢 | `fallen_alert`（≥2s） | ⏳ Phase 1 |

**導航避障**：Phase A **只接狀態，不承諾移動**。`go_to_named_place` 註冊為 skill 但 `enabled_when=[("phase_b_pending", "...")]`，Studio 顯示「為什麼不能做」而非灰階按鈕。

**實作 plan**：見 [`plans/2026-04-27-pawai-brain-skill-first.md`](2026-04-27-pawai-brain-skill-first.md) — 34 tasks 分 3 phases：

| Phase | 內容 | 進度 |
|-------|------|------|
| **Phase 0**（5 tasks） | Action Outlet Refactor — sport `/webrtc_req` 收成 Executive 單一出口 | ✅ **完成**（2026-04-28，tag `pawai-brain-phase0-done`） |
| **Phase 1**（13 tasks） | Brain MVS 後端 — skill_contract / safety_layer / world_state / skill_queue / brain_node + executive 重寫 | ⏳ 下一步 |
| **Phase 2**（16 tasks） | Studio Brain Skill Console — schemas / gateway / mock + 8 React components + chat-panel 重寫 | ⏳ Phase 1 後 |

**5/16 Demo 腳本**：見 [overview §9](../../architecture/pawai-brain-studio-overview.md#9-demo-流程516-省夜3-分鐘)（3 分鐘流程）。

---

## 5. Phase B — Embodied Brain（5/16 後）

**目標**：補你問過缺的導航整合。Brain 從「能演 demo 場景」升級為「**懂 Go2 身體**」。

**新增三大塊**：

1. **BodyState**（擴 WorldState）
   - 訂閱 `/state/nav/{heartbeat,status,safety}` `/amcl_pose` `/map_metadata` `/battery`
   - 提供 `nav_stack_ready` `amcl_covariance_ok` `map_loaded` `battery_pct`

2. **Capability Validator**
   - `SkillContract.enabled_when: list[CapabilityPredicate]`
   - 動態評估：電池 < 20% → 禁遠導航；AMCL 未收斂 → 禁 nav skill
   - reject path 自動產 `chat_reply` 解釋給使用者

3. **Nav Skill Pack**（對接 nav_capability platform 4 actions + 3 services）
   - `go_to_named_place(place)`
   - `go_to_relative(distance, angle)`
   - `run_patrol_route(route_id)`
   - `pause_navigation` / `resume_navigation` / `cancel_navigation`

**OpenClaw 偷的 4 個 pattern**：

| OpenClaw 概念 | PawAI 落地 | Phase |
|---------------|------------|-------|
| Capability Registry（allow/deny + tool registry） | `enabled_when` + `is_enabled()` | B |
| Context Engine | `BodyState` | B |
| AGENTS.md / SOUL.md | `workspace/{BODY,SKILLS,SAFETY,PLACES,DEMO_MODE}.md` | B |
| Tool schema export（OpenAI function-calling JSON） | `export_openai_tools()` | B |
| Multi-channel adapter | 不偷（場景不需要） | — |
| Plugin marketplace | 不偷（ROS2 package 即 plugin） | — |
| Sandbox container | 不偷（信任邊界內） | — |

**Spec**：見 [`specs/2026-04-27-pawclaw-embodied-brain-evolution.md`](../specs/2026-04-27-pawclaw-embodied-brain-evolution.md)。
**Plan**：尚未撰寫，待 Phase A 完成後新建 `plans/2026-XX-XX-pawclaw-embodied-brain-v1.md`。

**Demo 升級對話範例**：

```
[user]   去廚房幫我拿杯水
[brain]  candidate: bring_object(class="cup", place="廚房")
[capability]  ✗ blocked
              · AMCL 定位未收斂
              · 地圖未載入
              · bring_object 在 Phase B 仍未實作
[brain]  fallback: chat_reply
[say]    我現在還不能移動 — 定位還沒收斂、地圖也還沒載入。
         拿東西這個技能也還在開發中。要我先建圖嗎？
```

---

## 6. Phase C — OpenClaw-style LLM Planner（5/19 驗收後）

**目標**：LLM 不控狗、只能選 skill。Brain 把 SKILL_REGISTRY 餵給 LLM 作為 function-calling tool schema。

**LLM 提案 → Brain rule 驗證 → Capability Validator → Safety Layer → Executive**：

```
User: 「巡邏一下家裡，看到陌生人就警告」

LLM 看到 SKILL_REGISTRY 後產：
{
  "tool_calls": [
    {"skill": "run_patrol_route", "args": {"route_id": "home_guard"}},
    {"skill": "stranger_alert"}  // 條件式提醒
  ]
}

Brain：
  ✓ run_patrol_route enabled_when 全過
  ✓ stranger_alert 已是 face rule 自動觸發，不需 LLM 顯式呼叫
  → 出 SkillPlan(run_patrol_route)

Capability Validator：
  ✓ AMCL 收斂、map 載入、battery > 20%
  → ACCEPTED

Executive：
  → nav_capability action client (run_route)
  → 巡邏中若 face module 偵測到陌生人，原本的 face rule 自動 fire stranger_alert
  → 巡邏 + 陌生人警示同時運作（兩個獨立 SkillPlan，由 Skill Queue 編排）
```

**關鍵原則**：
- LLM **永遠**只是 proposal source，不是 execution path
- Phase A 的規則 router 仍存在，作為 LLM 不可用時的 fallback（這就是降級鏈本體）
- Capability Validator 確保 LLM 提案不可能繞過硬體狀態

**Spec / Plan**：尚未撰寫，5/19 demo 後再開。

---

## 7. 每模組的 Done Criteria（接進 Brain 的驗收）

每個模組要明確寫「怎樣算接進 Brain」。沒過全部就是「跑得起來但沒整合」。

### 通用 6 條（每個模組都要過）

| # | 項目 | 驗證方式 |
|---|------|---------|
| 1 | 有 `/event/*` 或 `/state/*` topic 寫入 contract | `python3 scripts/ci/check_topic_contracts.py` |
| 2 | 至少 1 條 SkillContract 對應到該模組能力 | `pytest interaction_executive/test/test_skill_contract.py` |
| 3 | Studio Chat 至少 1 種 bubble 渲染該 skill 的 lifecycle | mock_server 觸發 → frontend 看到 bubble |
| 4 | 至少 1 條 Brain rule 監聽該模組事件 | `pytest interaction_executive/test/test_brain_rules.py` |
| 5 | 有 fallback / cooldown / dedup 行為定義 | `pytest`（cooldown / dedup / fallback test） |
| 6 | 有 demo 腳本納入 5/16 Demo 流程 | `bash scripts/start_pawai_brain_tmux.sh` 跑得通 |

### 各模組獨有的 Done Criteria

| 模組 | 獨有條件 | 達成 phase |
|------|---------|-----------|
| **語音** | LLM cloud → local → say_canned 三級 fallback；`output_mode=brain` 不發 sport `/webrtc_req` | A（Phase 0 ✅ + Phase 1 整合） |
| **人臉** | 熟人 cooldown 20s/人；陌生人 ≥3s 才觸發 stranger_alert | A |
| **手勢** | wave / ok / thumbs_up / stop 四種對應 skill；fist→ok 相容 map 不破 | A |
| **姿勢** | fallen ≥2s 才觸發 fallen_alert；emergency 可關閉開關保留 | A |
| **物體** | per-class cooldown 5s；whitelist 至少 6 class（cup/bottle/person/dog/chair/dining_table） | A（部分） + B（find/bring） |
| **導航** | nav_capability 4 actions 全部對接；BodyState 知道 nav_ready；Studio 顯示「為什麼不能走」 | **B**（A 只接狀態） |
| **Brain×Studio** | 7 場景 Demo 通過；Brain Status Strip + 8 bubble + Trace Drawer 全可視；單一出口 audit 過 | A（Phase 1+2） |

---

## 8. Roadmap & 時程

```
2026-04-28 (今天)   ─┬─ Master Integration Plan 寫成（本文件）
                     │
                     ▼
2026-04-29~05-04    ─┬─ Phase 1 Brain backend（13 tasks）
                     │  · skill_contract / safety_layer / world_state
                     │  · skill_queue / brain_node 規則仲裁
                     │  · executive 重寫
                     │
                     ▼
2026-05-05~05-09    ─┬─ Phase 2 Studio Console（16 tasks）
                     │  · 8 種 bubble + Skill Buttons + Trace Drawer
                     │  · gateway 擴充 + frontend integrate
                     │
                     ▼
2026-05-09~05-12    ─┬─ Demo dry run × 3
                     │  · 7 場景驗證
                     │  · LiDAR mount 上機（並行）
                     │
                     ▼
2026-05-13          ─── 帶到學校 freeze
2026-05-19~05-21    ─── 三天驗收（Phase A 線上）
                     │
                     ▼
2026-05-22~06-XX    ─┬─ Phase B PawClaw 演進
                     │  · BodyState + Capability Validator
                     │  · Nav Skill Pack 6 條
                     │  · Workspace files
                     │
                     ▼
2026-06            ─┬─ 口頭報告
                     │
                     ▼
（5/19 後 + 設備 ready）  Phase C — LLM Planner（OpenClaw-style function calling）
```

**硬底線**：
- 4/13 文件繳交 ✅（已過）
- 5/13 帶去學校
- 5/19~5/21 三天驗收
- 6 月口頭報告

---

## 9. 不做（明確邊界）

避免「太亂」再次發生。**任何不在這份 master plan 列名的工作都需要先回到這份文件審視 scope**。

| 不做 | 原因 |
|------|------|
| LLM 直接控狗（任何 phase） | 違反 north star |
| 重寫 4 份既有文件（spec/plan/PawClaw spec/overview） | 重複會 drift；本文件當入口即可 |
| Phase A 強行做導航 | nav stack 仍在物理 mount blocker；硬塞會壓縮 5/16 demo |
| 抄 4 個 PawAI repo PR（#38/#40/#41/#42）進 Phase A | PR 仍在改進；Phase A 穩定後評估 |
| OpenClaw 多通道（WhatsApp / Slack） | 場景是局部居家，Studio WebSocket 足夠 |
| OpenClaw plugin marketplace | ROS2 package 即 plugin |
| OpenClaw sandbox container | 機器人 runtime 在 Jetson 信任邊界內 |
| Memory / 跨 session 記憶 | 5/19 deadline 太緊，Phase D 評估 |
| Multi-agent sub-goal decomposition | 單 Brain 邏輯清晰，多 agent 反而難 debug |

---

## 10. 文件索引（更新後 single source of truth）

| 文件 | 角色 | 何時讀 |
|------|------|--------|
| **本文件** | 唯一入口 + 整合視角 + Phase 排序 + Done criteria | **每次都先讀** |
| [`pawai-brain-studio-overview.md`](../../architecture/pawai-brain-studio-overview.md) | 對外總覽（教授 / 答辯） | 解釋系統給外人 |
| [`specs/2026-04-27-pawai-brain-skill-first-design.md`](../specs/2026-04-27-pawai-brain-skill-first-design.md) | Phase A 設計藍圖（schema / 規則 / topic 契約） | 寫 code 前查 schema |
| [`plans/2026-04-27-pawai-brain-skill-first.md`](2026-04-27-pawai-brain-skill-first.md) | Phase A 施工圖（34 tasks） | 執行 Phase 1/2 |
| [`specs/2026-04-27-pawclaw-embodied-brain-evolution.md`](../specs/2026-04-27-pawclaw-embodied-brain-evolution.md) | Phase B 演進 spec | 5/19 後 |
| [`specs/2026-04-11-pawai-home-interaction-design.md`](../specs/2026-04-11-pawai-home-interaction-design.md) | PawAI 系統定位（4/11 三層 Brain 概念源） | 答辯論述補強 |
| [`docs/architecture/contracts/interaction_contract.md`](../../architecture/contracts/interaction_contract.md) | ROS2 介面契約（v2.4 → v2.5 Phase A → v2.6 Phase B） | 任何新 topic |
| [`docs/mission/README.md`](../../mission/README.md) | 專案方向、時程、分工 | 接手 / 解釋大方向 |
| 7 模組各自 README | 模組真相來源 | 改該模組時 |

**舊文件不刪，但 deprecation 順序**：
- 4/11 spec：保留作答辯論述背景
- 4/27 三件套：spec / plan / PawClaw spec — 全保留，本文件引用而非替代
- overview：保留作對外文件，但 Phase B 章節要在 5/19 後重寫

---

## 11. 今日狀態（2026-04-28 執行檢查點）

| 項目 | 狀態 |
|------|------|
| North Star 共識 | ✅ PawAI Brain = 機器狗版 OpenClaw |
| Phase 0（Action Outlet Refactor） | ✅ 完成，tag `pawai-brain-phase0-done` |
| Master Integration Plan | ✅ 本文件 |
| Phase 1 開工 | ⏳ 待用戶確認後啟動 |

**下一步建議**：
1. 用戶 review 本文件 → 確認整合視角到位
2. 啟動 Phase 1 Task 1.1（`skill_contract.py`，含 Phase B forward-compat 欄位）
3. Phase 1 task 1-7（純 Python，本地 pytest 即可驗）並行於 Jetson 跑 Phase 0 deferred runtime smoke

---

## 附錄 A：與既有 Plan 的關係（避免 drift）

| 既有文件 | 本 master plan 的角色 |
|---------|---------------------|
| `2026-04-27-pawai-brain-skill-first.md`（34 tasks） | **本 master plan §4 引用它**。施工細節不複製，只指向。Phase 1/2 執行仍以該檔為主。 |
| `2026-04-27-pawclaw-embodied-brain-evolution.md` | **本 master plan §5 引用它**。Phase B 啟動時新建獨立 plan 檔，本文件加連結。 |
| `2026-04-26-nav-capability-s2.md` | nav_capability platform 已完成，本 master plan §2 / §5 引用為 Phase B 整合對象 |
| `2026-04-24-p0-nav-obstacle-avoidance.md` | nav 底層執行 plan，與 Phase B 整合 |

**衝突處理規則**：
- 若本文件與既有 spec / plan 衝突 → **本文件勝**（north star 優先）
- 既有 spec / plan 內部細節衝突 → 以 commit 時間較新者為準
- 任何重大 scope 變更 → 先改本文件，再改下游 spec / plan
