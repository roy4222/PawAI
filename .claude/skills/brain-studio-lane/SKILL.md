---
name: brain-studio-lane
description: 啟停或診斷 PawAI Brain、語音與 Studio 的 runtime 組合時使用。
---

# Brain／Studio runtime

依本次要驗證的輸出選最小組合；文字、音訊、完整互動需要的設備不同。只改 persona、前端或讀程式時，不自動啟動整套 runtime。

入口在本技能的 `scripts/{preflight,start,healthcheck,cleanup}.sh`，從 repo root 使用完整路徑 `.claude/skills/brain-studio-lane/scripts/`。先核對相關腳本與它呼叫的 launcher；可用 mode／flags 以實作為準。

- [runtime topology](references/runtime-topology.md)：組合與共享資源。
- [ports and environment](references/ports-env.md)：設定解析、shell 與裝置。
- [troubleshooting](references/troubleshooting.md)：install、audio、DDS 與程序問題。

`start.sh` 可能先自動 cleanup；`--handoff` 不代表只清部分資源。查清目前 session ownership 與操作影響，再依已有授權執行；不要為修一個面板清掉他人的 driver。full／demo 可能啟 robot writer，必須符合根 AGENTS 的動作邊界。

以實際 chat、音訊或畫面輸出驗證本次情境；HTTP 200、topic publisher 存在不等於整條流程成功。遇到可在既有範圍修復的錯誤就修復並重驗；只有缺必要資訊或授權才詢問。
