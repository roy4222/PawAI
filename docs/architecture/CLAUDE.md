# 系統架構 — Claude Code 工作規則

> 這是 architecture/ 的工作規則真相來源。

## 不能做

- 不要修改 interaction_contract.md 的已凍結欄位（v2.1 凍結）
- 不要刪除 SUPERSEDED 文件（保留在 archive/ 供追溯）
- 新增 topic 必須同步更新 contract

## 改之前先看

- `docs/architecture/contracts/interaction_contract.md`（凍結契約）
- `docs/architecture/designs/clean_architecture.md`
- `CLAUDE.md`（根目錄，有完整 topic 列表）

## 驗證指令

```bash
# CI 會自動檢查 contract
python3 scripts/ci/check_topic_contracts.py
```
