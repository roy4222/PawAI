---
name: update-docs
description: 依 PawAI 的程式或操作變更，更新受影響的正式文件。
---

# 同步文件

先確認使用者指定的 diff、commit 或時間範圍，包含相關未提交修改；只更新真正受影響的事實。

| 變更 | 主要 owner |
|---|---|
| 模組行為 | 模組 README、`docs/architecture/` 對應領域 |
| topic／schema／QoS／跨模組命令 | `docs/contracts/interaction_contract.md` |
| Brain／Studio | `docs/architecture/brain/`、`docs/architecture/studio/` |
| 安裝／部署／launcher | `docs/runbook/`、`docs/pawai_cli/` 或模組操作入口 |
| 已定方向／決策 | 本次任務涉及的方向文件或 `docs/adr/` |

從 `docs/README.md` 核對現存路徑與責任。不更新 archived sprint 或 Skill 內的歷史 status 來冒充當前進度。文件與程式有差異時，區分已定契約、已實作行為及未驗結果，不擅自把實作偏差升格成新決策。

依已有授權完成相關文件與必要連結核對，不按檔案數要求重複批准。保留不相關內容及其他人的修改；沒有證據不填 PASS。commit／push 依本次請求與既有授權，只 stage 自己的變更，不跳過 hooks、不編造作者。

回報改了哪些事實、驗證結果與尚待決定的實質問題。
