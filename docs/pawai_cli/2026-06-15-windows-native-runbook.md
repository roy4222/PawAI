# PawAI CLI — Windows 原生（PowerShell）Runbook

> 日期：2026-06-15　狀態：**code 已放行 Windows native + 邏輯驗過（platform 11 tests），實機待 Roy 在 Windows 跑**
> 一句話：**Windows 原生 PowerShell 可直接用「純 SSH」類指令（face enroll/list/delete/rebuild、status、logs、doctor）；`demo start/stop/health` 因為跑本機 bash 腳本，需要 WSL2 / Git Bash / Mac，已在 CLI 加清楚提示。**

---

## 0. 為什麼 Windows 原生現在能用（6/15 放行）

- `tools/pawai_cli/pawai_cli/shell.py` 用 **`subprocess.run([list])`、無 `shell=True`**，SSH 是 `["ssh","-o",...,host,cmd]` list → Windows 的 **OpenSSH `ssh.exe`** 直接吃；遠端命令在 Jetson zsh 跑（`shlex.quote` 是給遠端的、與本機 Windows 無關）。
- `platform.py` 原本擋 Windows native（exit 10），6/15 改 **`supported=True`**（kind=`windows_native`）。
- **face 指令全是 SSH-passthrough**（在 Jetson 上跑、不需 Windows 相機）→ Windows 原生可直接用。
- **`demo start/stop/health` 跑本機 bash 腳本** → Windows 原生無 bash，CLI 會印清楚提示要你改 WSL2/Git Bash。

| 指令 | Windows 原生 PowerShell |
|---|---|
| `pawai doctor` | ✅（本機只 tailscale/which/ssh probe；tmux/node 缺只是 warn） |
| `pawai status` | ✅ 純 SSH |
| `pawai face list` | ✅ 列出 Jetson face_db 人物+樣本數+備份警告 |
| `pawai face enroll --person-name <名>` | ✅ 在 Jetson headless 採樣（**不用 Windows 相機**） |
| `pawai face delete <名>` | ✅ 刪 face_db 子資料夾 |
| `pawai face rebuild` | ✅ 刪 model cache、下次重訓 |
| `pawai logs brain --lines 100` | ✅ 抓 Jetson tmux pane |
| `pawai demo start / stop` | ⚠️ 需 bash → 用 WSL2 / Git Bash / Mac / 在 Jetson 起 |
| `pawai health brain` | ⚠️ 需 bash（同上） |

---

## 1. 一次性安裝（Windows，PowerShell）

```powershell
# 1) Python 3.10+（winget 或 python.org）
winget install Python.Python.3.12     # 或到 python.org 裝
python --version                       # 確認 >= 3.10

# 2) OpenSSH client（Win10 1809+ / Win11 內建；確認）
ssh -V                                 # 有版本即可；沒有→ 設定>應用程式>選用功能 裝 OpenSSH 用戶端

# 3) Tailscale（下載安裝 https://tailscale.com/download/windows）→ 用你的帳號登入、接受 Roy 的 share

# 4) Git（clone 用；winget install Git.Git）

# 5) clone repo（放本機，不要放網路磁碟）
cd $HOME ; git clone <repo-url> elder_and_dog ; cd elder_and_dog

# 6) venv + 裝 CLI（只 click + python-dotenv，無 Linux-only 套件）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e tools\pawai_cli
pawai --version                        # 能印版本 = 平台閘門已放行 Windows native

# 7) SSH config：%USERPROFILE%\.ssh\config 加（指向 Jetson Tailscale IP）
#    Host jetson-nano
#        HostName 100.83.109.89
#        User jetson
type $env:USERPROFILE\.ssh\config      # 確認
ssh jetson-nano "echo ok"              # 應印 ok（SSH 通；第一次會問 fingerprint→yes）

# 8) 環境變數（PowerShell session 設，或寫進 repo 的 .env）
$env:JETSON_HOST = "jetson-nano"
$env:JETSON_TAILSCALE_IP = "100.83.109.89"   # 留空也行，doctor 會從 tailscale 偵測
$env:OPENROUTER_KEY = "..."                    # 跟 Roy 拿（doctor / demo 才需要）
```

> 永久環境變數：`setx JETSON_HOST jetson-nano`（新開 PowerShell 生效），或寫進 repo 根的 `.env`（CLI 有 CRLF 正規化、Windows 編輯也 OK）。

---

## 2. 人臉管理（Roy 要的：註冊 / 看現有 / 選取刪除）

```powershell
.\.venv\Scripts\Activate.ps1 ; cd $HOME\elder_and_dog

# 看現在 face_db 有哪些人臉（+樣本數，⚠ 標疑似備份目錄）
pawai face list

# 註冊新人臉（在 Jetson 上採樣 30 張、訂 Jetson 相機，不用 Windows 鏡頭）
pawai face enroll --person-name roy
#  → 採完後跑：pawai face rebuild（刪 model cache）→ 重啟 face_identity_node 重訓

# 選取刪除某人（會先顯示樣本數 + 互動確認）
pawai face delete <名>          # 加 -y 跳過確認

# 重訓（刪 model_sface.pkl/.npz，下次 face node 啟動重建）
pawai face rebuild
```

> ⚠️ **enroll/rebuild 後要讓新人臉生效**：重啟 Jetson 的 `face_identity_node`（demo 重起，或 ssh 進 Jetson 重啟該 node）。face_db 衛生：備份資料夾務必移出 `/home/jetson/face_db`（否則被當人名訓進 model、稀釋 centroid）。

---

## 3. 其他可直接用的（純 SSH）

```powershell
pawai doctor                    # 環境健檢（tmux/node missing 只是 warn）
pawai status                    # Jetson tmux/ROS node/git/上次 deploy
pawai logs brain --lines 100    # 抓 Jetson brain pane
```

---

## 4. demo 生命週期（Windows 原生不行 → 用 WSL2/Mac）

`pawai demo start/stop`、`pawai health` 跑本機 bash 腳本（start.sh/cleanup.sh/healthcheck.sh）+ 本機 Studio frontend（next dev）。Windows 原生 PowerShell 沒 bash，CLI 會印：

```
✗ demo start 需要 bash（start.sh）— Windows 原生 PowerShell/CMD 沒有 bash。
  → demo 生命週期（start/stop/health）請用 WSL2 / Git Bash / Mac，或在 Jetson 端起。
```

**處置**：demo 用 WSL2（`wsl` 進 Ubuntu）或 Mac 起；Windows 原生專做 face 管理 + status/logs/doctor。
（進階：Windows 裝 Git Bash + Node 後 `demo start` *可能* 能跑，但未驗證、不保證 — 不是 6/15 主線。）

---

## 5. 待 Roy 在實體 Windows 驗（我無法在 Linux 替代）

1. 🔴 `pawai --version` + `pawai doctor`（確認閘門放行 + tailscale/ssh 解析）。
2. 🔴 `pawai face list`（列得出 Jetson face_db 人物）。
3. 🔴 `pawai face enroll --person-name test`（Jetson 採樣跑得起來）+ `pawai face delete test`。
4. 🟠 `pawai status` / `pawai logs brain`（SSH 抓得到）。
5. 🟡 `ssh jetson-nano "echo ok"`（OpenSSH + Tailscale + SSH config 通）。

把這幾條的輸出貼回來，就能確認 Windows 原生實機綠燈。
