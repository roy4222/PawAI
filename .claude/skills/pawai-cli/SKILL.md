---
name: pawai-cli
description: 使用或診斷 PawAI CLI 的部署、狀態、log、demo 與共享設備鎖。
---

# PawAI CLI

先看相關 subcommand 的 `--help` 或 `tools/pawai_cli/` 實作，再使用確實存在的 flags。CLI 未安裝時讀 source／文件繼續定位，不為查一個操作跑完所有 help。

| 問題 | 按需來源 |
|---|---|
| 操作與錯誤 | `docs/pawai_cli/usage-guide.md`、`docs/pawai_cli/troubleshooting.md` |
| 指令入口 | [command reference](references/command-reference.md) |
| lock／部署版本 | [lock semantics](references/lock-semantics.md) |
| 主機連線 | [network diagnosis](references/network-diagnosis.md) |
| 初次安裝 | `docs/pawai_cli/team-onboarding.md` |

先查 `pawai doctor`／`pawai status` 所需的一項；部署按使用者指定模組與 revision。`-y` 只略過普通提示，`--force` 代表接管，不能用來繞過他人的鎖；自身 stale lock 先用 owner-aware 路徑。共享資源變更與機體動作依根 AGENTS。

`rsync` 後 Jetson 的 `.git` 不一定代表已部署程式；查 deploy receipt 與實際執行路徑。平台錯誤依當前 CLI 的檢查處理，不把舊 WSL 假設變成所有本機工作的禁令。
