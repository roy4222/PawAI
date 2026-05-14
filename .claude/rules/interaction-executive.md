---
paths:
  - "interaction_executive/**"
---

# interaction_executive 模組規則

## 現況
- **狀態**：空殼，Sprint B-prime Day 4-5 實作
- **設計**：thin orchestrator / demo controller，不是 AI brain
- **Spec**：`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-27-operation-b-prime-sprint-design.md`
- **Plan**：`docs/archive/2026-05-docs-reorg/superpowers-legacy/plans/2026-03-27-operation-b-prime.md` Task 3-5

## 設計要點
- 純 Python state machine（`state_machine.py`，無 ROS2 依賴，100% testable）
- ROS2 node wrapper（`interaction_executive_node.py`）
- 取代 `event_action_bridge` + `interaction_router`
- 狀態：IDLE → GREETING → CONVERSING → EXECUTING → EMERGENCY → OBSTACLE_STOP
- 優先序：EMERGENCY > obstacle > stop > speech > gesture > face
- 5s dedup、30s timeout、obstacle debounce 2s + min duration 1s
- `/executive/status` 2Hz 廣播（state + previous_state + duration + timestamp）
- LLM timeout > 2s → RuleBrain fallback

## 測試
```bash
python3 -m pytest interaction_executive/test/ -v
colcon build --packages-select interaction_executive
```
