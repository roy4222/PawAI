# 2026-05-02 Docs Reorg

> 5/02 提前執行的大重組。原計畫鎖 5/13 demo 後執行，user review 後決定提前。

---

## 為何提前

1. **Docs 太亂卡決策**：18 個 top-level 散落（6 個中文資料夾 + architecture/ + setup/ + research/ + superpowers/ 27 specs + 20 plans），新成員找不到 demo 主線
2. **5/12 前壓力比 5/13 後低**：demo 後會湧入 dry run log + bug fix + post-mortem，那時搬遷反而會撞修補
3. **風險可控**：307 引用 / 32 檔的更新範圍清楚，git mv 整資料夾保留 history，git revert 一鍵回退

## 執行紀要

- **執行 commit**：見 git log（搜尋 commit message `docs: pre-demo reorg`）
- **Plan**：`~/.claude/plans/b-policy-foamy-moon.md`（v3，user review 後修 6 點）
- **Backup branch**：`backup/pre-docs-reorg-2026-05-02`（local-only）

## 內容來源

| 子資料夾 | 來源於 | 為什麼 archive |
|---------|--------|--------------|
| `superpowers-legacy/specs/` | `docs/superpowers/specs/`（27 檔抽 3 個 active 後剩 24 個） | 過期設計 spec，主線新檔已分流到 `pawai-brain/specs/` |
| `superpowers-legacy/plans/` | `docs/superpowers/plans/`（20 檔抽 8 個 active 後剩 12 個） | 過期實作 plan |
| `architecture-misc/` | `docs/architecture/` 殘餘（CLAUDE.md / AGENT.md / proposals / archive / README） | 設計總則已抽進 `contracts/README.md` |
| `research-misc/` | `docs/research/` 殘餘（go2-sdk-capability / llm_local） | 非 perception/speech 模型選型紀錄 |
| `setup-misc/` | `docs/setup/` 殘餘（hardware / network / software / README，runbook 4 檔已抽出） | runbook 沒收的 setup 文件 |
| `assets-misc/` | `docs/assets/`（搬時 0 引用） | diagram 圖檔，5/02 時無人引用 |
| `operations/` | `docs/operations/baseline-contract.md` | SUPERSEDED |
| `audit/` | `docs/audit/` | 過時審查紀錄 |

## 七主線去向（active）

| 新位置 | 來源 |
|--------|------|
| `docs/pawai-brain/perception/{face,gesture,pose,object}/` | `docs/{人臉,手勢,姿勢,辨識物體}辨識/` |
| `docs/pawai-brain/speech/` | `docs/語音功能/` |
| `docs/pawai-brain/studio/` | `docs/Pawai-studio/` |
| `docs/pawai-brain/architecture/{overview.md,designs/}` | `docs/architecture/{pawai-brain-studio-overview.md,designs/}` |
| `docs/pawai-brain/specs/` | `docs/superpowers/specs/` 中 3 個 active |
| `docs/pawai-brain/plans/` | `docs/superpowers/plans/` 中 brain-related active |
| `docs/pawai-brain/studio/plans/` | `docs/superpowers/plans/` 中 studio active |
| `docs/navigation/{research,research/lidar-dev,setup}/` | `docs/導航避障/` + `docs/setup/slam_nav/` |
| `docs/navigation/plans/` | `docs/superpowers/plans/` 中 nav active |
| `docs/navigation/CLAUDE.md` `docs/navigation/AGENT.md` | `docs/導航避障/` 對應檔 |
| `docs/navigation/legacy-readme-from-導航避障.md` | `docs/導航避障/README.md`（保留待人工 merge） |
| `docs/contracts/interaction_contract.md` | `docs/architecture/contracts/interaction_contract.md` |
| `docs/runbook/{jetson,network,gpu-server,go2-operation}.md` | `docs/setup/{hardware,network,software}/...` |
| `docs/deliverables/thesis/` | `docs/thesis/`（已刪 `__pycache__/`） |

## 引用更新

- 涉及 ~95 檔，~235 處引用替換（CLAUDE.md / references/ / 各模組 CLAUDE.md+AGENT.md / spec / plan）
- 全部一個 commit；回退用 `git revert <sha>` 或 `git reset --hard backup/pre-docs-reorg-2026-05-02`

## 不在這次 reorg 做

- 重寫各模組 README 內容（純搬位置）
- thesis `.docx` git-lfs 評估（5/14 後再評）
- contracts/ 新增 contract（只搬 `interaction_contract.md`）
- runbook/ 新增 SOP（只抽 4 個現有候選）
- 任何 src/ 變更
