# Phase B Implementation Notes — 2026-05-04

> **Status**: working notes（短檔，與 [`2026-05-01-pawai-11day-sprint-design.md`](2026-05-01-pawai-11day-sprint-design.md) 配套）
> **Scope**: 5/4 當天 vertical slice 鎖定的關鍵決策。實作細節落 code，文件不寫長。
> **Goal**: 今晚跑通 Studio button → Brain → Trace Drawer → mock executor 一條 vertical slice。

---

## 今日優先序

```
B2 skill_contract.py（擴 9 → 26 + bucket）
→ B3a pending_confirm.py + tests
→ B3b brain_node 規則 / cooldown / confirm 接線
→ B5a Gateway /api/skill_registry + /api/skill/trigger + /api/plan_mode
→ B5b Studio Skill Console + Trace Drawer
→ Mini E2E 收尾
背景：B1 eval scaffold（dry-run capable，無 API key 也能 commit）
```

**今天不做**：B6 PR port、B7 60min 供電、實機 Go2/TTS/Gemini 接線。

---

## 關鍵決策

### 1. SkillContract 三欄位語意分離

```python
bucket: Literal["active", "hidden", "disabled", "retired"]   # 產品/展示分類，Studio 讀
static_enabled: bool                                          # 全局開關（registry-time）
enabled_when: list                                            # runtime 條件（Nav/Depth Gate / robot_stable）
```

- **Studio** 讀 `bucket` 決定 `enabled` / `grayed-out` / `hidden`
- **Brain** 讀 `static_enabled + enabled_when` 決定能不能 build_plan
- 三者**不互相覆蓋**，新欄位 `bucket` 純做展示語意

`acknowledge_gesture` 標 `bucket="retired"`，保留 contract 但 Studio 不顯示、brain 不再選。

### 2. PendingConfirm 行為

純 Python state machine（`interaction_executive/interaction_executive/pending_confirm.py`），零 ROS2 依賴。

```
state: Idle | Pending(skill, args, started_at, ok_stable_since)
events:
  request_confirm(skill, args, now) → 進 Pending
  tick(now, current_gesture):
    - now - started_at > 5s  → 回 Idle, return CANCELLED("timeout")
    - current_gesture == "OK":
        - ok_stable_since is None: 設 ok_stable_since = now
        - now - ok_stable_since >= 0.5s: 回 Idle, return CONFIRMED(skill, args)
    - current_gesture not in (None, "", "OK"):
        - 回 Idle, return CANCELLED("different_gesture")
    - current_gesture in (None, ""):
        - ok_stable_since 重置為 None，繼續 Pending
```

**Active Confirm Set 4 條**（spec §4.2）：`wiggle / stretch / approach_person / nav_demo_point[非 Studio button trigger]`。

Studio button trigger 的 `nav_demo_point` 由 button 本身代表確認，**bypass** PendingConfirm。

### 3. Mini E2E PASS 標準

```
Studio 按 [self_introduce] button
  → POST /api/skill/trigger {"skill":"self_introduce"}
  → Gateway publish ROS2 /brain/manual_trigger
  → brain_node 收到 → build_plan(self_introduce)（meta skill 6 步）
  → publish /brain/proposal（SkillPlan JSON）
  → Trace Drawer 即時渲染 6-step plan + reason + Nav/Depth Gate Bool
  → mock executor（log-only）逐步發 /brain/skill_result step_started/step_success
  → 最後 status=completed
  → Trace Drawer 顯示 ✓
```

**不依賴**：Go2 driver、真 TTS（Gemini/edge/Piper）、相機、LiDAR、實機 Nav2。

**Gate 狀態 — tri-state（`true` / `false` / `unknown`）**：
- 訂 `/capability/nav_ready` + `/capability/depth_clear`（`std_msgs/Bool`）
- 收到 Bool `true` → `true`；收到 Bool `false` → `false`
- **未收到任何訊息 → `unknown`**（topic 不存在或 publisher 未啟動）
- Trace Drawer 三色：綠（true）/ 紅（false）/ 灰（unknown）
- Brain Pre-action validate 規則：高風險 NAV/MOTION 要求 `gate == true`；`unknown` 與 `false` 同樣視為不過 gate（保守降級為 SAY），但 Studio UI 與 log 必須能區分這兩者，方便現場除錯

### 4. B1 eval scaffold — dry-run 模式

無 `OPENROUTER_API_KEY` 也要能 commit / dry-run：

```bash
python tools/llm_eval/run_eval.py --dry-run                       # 印出 prompt × model 矩陣不打 API
python tools/llm_eval/run_eval.py --models gemini,deepseek,qwen   # 真打 API（需 key）
python tools/llm_eval/score.py results/<timestamp>.json           # 半人工 4 軸打分
```

scaffold done definition：
- `prompts.json`（50 題，5 桶）
- `persona.txt`（system prompt，正向語氣，不列拒絕清單）
- `run_eval.py`（含 --dry-run）
- `score.py`（4 軸 1–5，寫回 JSON）
- `README.md`（usage + key 設定）

---

## 跨天延後項目

| 延後 | 預計時點 |
|---|---|
| B4 感知擴實機調參（Wave 動態 / HSV / sitting / bending / fallen name） | 5/5 |
| B1 真 LLM × 50 prompt 跑批 + 模型決策 | 5/5（拿到 key 後） |
| TTS provider chain 實接（Gemini 3.1 / edge-tts / Piper） | 5/5–5/6 |
| B6 PR #38 / #40 / #41 / #42 前端 port | 5/6–5/7 |
| B7 8 scene Plan A 連跑 + 60 min 供電壓測 | 5/7–5/8 |
| 實機 Go2 / Megaphone / D435 串 Brain executor | 5/5 起 |

---

## 變更紀錄

- **2026-05-04**：初版 — 鎖定 bucket / PendingConfirm / Mini E2E / B1 dry-run 四個決策。
