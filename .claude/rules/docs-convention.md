---
paths:
  - "docs/**"
  - "references/**"
  - "CLAUDE.md"
---

# 文件慣例規則

## 真相來源層級
1. **程式碼** — 永遠是最終真相
2. **references/*.md** — 模組快速導覽（指向權威文件）
3. **docs/模組/README.md** — 權威設計文件
4. **docs/mission/README.md** — 專案方向
5. **CLAUDE.md** — Claude Code 工作指令

## 更新原則
- 改了程式碼 → 同步更新對應的 `docs/模組/README.md`
- 新增/移除 ROS2 topic → 同步更新 `docs/architecture/interaction_contract.md`
- 每日收工 → 更新 `references/project-status.md`
- 不主動重寫沒碰到的文件

## 命名約定
- 檔案：`.md`（小寫，不用 `.MD`）
- 日期前綴：`YYYY-MM-DD-description.md`
- Spec：`docs/superpowers/specs/YYYY-MM-DD-*-design.md`
- Plan：`docs/superpowers/plans/YYYY-MM-DD-*.md`

## Sprint B-prime 文件結構
- **每日任務**：`docs/mission/sprint-b-prime.md`
- **設計規格**：`docs/superpowers/specs/2026-03-27-operation-b-prime-sprint-design.md`
- **實作計畫**：`docs/superpowers/plans/2026-03-27-operation-b-prime.md`
- **系統狀態**：`references/project-status.md`（每日更新）
