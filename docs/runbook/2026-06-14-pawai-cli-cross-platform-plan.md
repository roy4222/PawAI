# PawAI CLI Cross-Platform Compatibility Plan (2026-06-14)

> 作者：Carl（CLI cross-platform builder）
> 範圍：`tools/pawai_cli` 現狀稽核 + 跨平台相容計畫 + macOS 操作員 runbook。
> **這份文件是 audit + 計畫，不是重寫。** Typer/Rich/pipx 一律歸 P2（6/18 後）。
> **本輪未改任何 code**（doc-only），218 CLI 測試維持綠。理由見 §6。

---

## 0. TL;DR（先講結論）

| 平台 | 優先級 | 結論 | 6/18 可用？ |
|------|:------:|------|:-----------:|
| **WSL2 Ubuntu**（repo 在 Linux fs） | **P0** | ✅ 完整支援，Roy 現在就在用 | 是 |
| **macOS native** | **P0** | ✅ **程式碼層無 blocker**；platform.py 已判 Darwin=supported；所有本機依賴（ssh/rsync/git/bash/tmux via brew）macOS 都有。**但本輪無法 runtime 驗證**（我們在 WSL/Linux 上）→ 標記為「audit-pass，runtime 待 Roy 的 MacBook 跑一次」 | 是（待 Roy 一次 smoke 驗收） |
| **Linux native** | P0（順帶） | ✅ 完整支援（CI 跑的就是這個） | 是 |
| **Windows native（PowerShell/CMD/Git Bash）** | **P1** | ⛔ 刻意擋掉（exit 10）。需要的工作量見 §4，**不承諾 6/18 前做** | 否（請走 WSL2） |
| **Jetson 本機裝 CLI** | — | 不需要。CLI 從 Mac/WSL 端跑，靠 SSH 操作 Jetson | N/A |
| Typer / Rich / pipx 重構 | **P2** | 6/18 後再談，本輪 forbidden | 否 |

**對 6/18 最重要的一句話**：Roy 帶 MacBook 當操作端 → macOS 必須是「最可靠的操作環境」。
程式碼層我已確認沒有會擋住 macOS 的東西；唯一缺口是「沒有真機 macOS runtime 證據」。
請 Roy 在 MacBook 上跑一次 §7 的驗收清單（約 5 分鐘）把這個缺口補掉。

---

## 1. 現狀稽核：平台支援表（per command group）

判定方式：閱讀 `tools/pawai_cli/pawai_cli/*.py`，逐 command group 列出「本機端」會直接依賴
的外部工具/系統假設。**注意**：絕大多數重活（flock / tmux / ros2 / colcon / nmcli / ip /
ps / find / curl）都在 **Jetson 端**透過 `ssh` 執行，本機只需要把 SSH 接通。本機端真正的
硬依賴只有：`ssh`、`rsync`、`git`、`bash`（呼叫 start.sh/cleanup.sh/healthcheck.sh）、
`tail`（`logs` 的 `local:` target）、外加選配的 `tailscale` / `tmux` / `node` / `npm`。

| Command group | 本機端硬依賴 | WSL2 | macOS | Win-native PS |
|---------------|-------------|:----:|:-----:|:-------------:|
| `pawai doctor` | `git`,`ssh`,`tailscale`(選),`tmux`/`node`/`npm`(只檢查存在),`curl`(remote) | works | works※ | blocked（platform gate exit 10） |
| `pawai status` | `ssh`,`git` | works | works※ | blocked |
| `pawai jetson deploy` | `ssh`,`rsync`,`git` | works | works※ | blocked（無原生 rsync/ssh） |
| `pawai demo start/stop` | `ssh`,`bash`（start.sh/cleanup.sh）,`git` | works | works※ | blocked（bash + flock-over-ssh 路徑） |
| `pawai smoke brain/vision/object/nav/full` | `ssh` | works | works※ | blocked |
| `pawai evidence pull` | `rsync`,`ssh` | works | works※ | blocked |
| `pawai readiness [freeze]` | 純本機檔案 + `benchmarks.core`（純 Python） | works | works | blocked（gate）/ 邏輯本身可跑 |
| `pawai face list/enroll/delete/rebuild/test` | `ssh` | works | works※ | blocked |
| `pawai net wifi list/status/connect/forget` | `ssh` | works | works※ | blocked |
| `pawai logs <module>` | `ssh`,`tail`（`local:` target，如 studio 的 `/tmp/studio_frontend.log`） | works | works※ | blocked |
| `pawai docs / dev info / contract check` | `git`,`bash`/`python3`,`$EDITOR` | works | works※ | blocked |
| `pawai health brain/nav` | `ssh`,`bash`（healthcheck.sh） | works | works※ | blocked |

- **works**：閱讀程式碼確認無平台假設衝突；WSL2 有 Roy 的實機使用佐證。
- **works※（macOS）**：閱讀程式碼確認無 blocker，但**本輪無 macOS runtime 證據**。
  標記為 audit-pass / runtime-deferred。差異風險見 §3「macOS 細節」。
- **blocked**：被 `platform.assert_supported()` 在 `cli()` 進入點直接擋下（exit 10）。

### 1.1 platform.py 的判定邏輯（逐字擷取 + WHY）

`tools/pawai_cli/pawai_cli/platform.py::detect()`：

| `platform.system()` | 額外判斷 | 判定 kind | supported | WHY |
|---------------------|----------|-----------|:---------:|-----|
| `Darwin` | — | `macos` | **True** | macOS 有 ssh/rsync/git/bash/flock；brew 補 tmux/node。Unix 語義完整 |
| `Windows` | — | `windows_native` | **False** | PowerShell/CMD/Git Bash 沒有可靠的 ssh+rsync+flock+tmux+`/tmp`+Unix permission 語義 → deploy/demo lock 會出不可預期行為 |
| `Linux` | `/proc/version` 含 `microsoft` **或** `WSL_DISTRO_NAME` 有值 → 是 WSL | — | — | 區分 WSL1/WSL2 |
| ┗ WSL | `/proc/version` 含 `wsl2` **或** kernel major ≥ 5 | `wsl2` | **True** | WSL2 是真 Linux kernel，rsync/flock/Unix 語義正確 |
| ┗ WSL | kernel major < 5（且非 wsl2 字串） | `wsl1` | **False** | WSL1 是 syscall 翻譯層，rsync `--delete` / flock / inotify 行為不可靠 |
| 純 Linux | 非 WSL | `linux` | **True** | 原生 Linux |
| 其他 | — | `unknown` | **False** | 未知平台保守擋下 |

`check_repo_path(info, repo)`：**只在 `wsl2`** 檢查 repo 是否在 `/mnt/c/` 或 `/mnt/d/`
（Windows 檔案系統）。是的話回報錯誤——因為 9P 檔案系統 I/O 慢、rsync 語義（permission/
mtime/inode）在 DrvFs 上會壞。macOS / 原生 Linux 不做此檢查。

`assert_supported(repo)`：不 supported **或** repo path 違規 → 印出 actionable 修法
（`wsl --install` / `wsl --set-version 2` / 把 repo 搬進 Linux home）後 `sys.exit(10)`。
這個 gate 在 `cli()` group callback 最前面跑，**任何 subcommand 都會先過這關**。

**稽核結論**：這個分類正確且保守。macOS 被正確判為 supported，Windows-native 被正確擋下。
測試覆蓋完整（`test_platform.py` 9 條，含 mock Darwin/Linux/WSL2/WSL1/Windows + `/mnt/c`
拒絕 + exit code 10 驗證）。**這層不需要改。**

---

## 2. 本機端依賴清單（哪些工具、誰在本機跑、誰在 Jetson 跑）

把「本機 vs Jetson」分清楚是整份稽核的關鍵。**Windows 之所以被擋，不是因為 Jetson 端的
Linux 指令（那些跑在 Jetson 上），而是因為「本機端」這幾個工具 + Unix 語義在 Windows
native 缺失。**

| 工具 | 在哪跑 | macOS 有？ | WSL2 有？ | Win-native 有？ | 備註 |
|------|--------|:----------:|:---------:|:---------------:|------|
| `ssh` | 本機 → Jetson | ✅ 內建 | ✅ | ⚠️ OpenSSH 可選裝但 `~/.ssh/config`/agent 行為不同 | `shell.ssh_args()` |
| `rsync` | 本機 ↔ Jetson | ✅ 內建（舊版 2.6.9，見 §3） | ✅ | ❌ 無原生 | deploy / evidence pull |
| `git` | 本機 | ✅ | ✅ | ✅（Git for Windows） | branch/sha/status |
| `bash` | 本機（呼叫 .sh） | ✅ | ✅ | ⚠️ Git Bash 有但 tmux/路徑語義不合 | start/cleanup/healthcheck |
| `tail` | 本機（`logs` 的 local: target） | ✅ | ✅ | ❌ 原生無 | `local:/tmp/studio_frontend.log` |
| `flock` | **Jetson**（over ssh） | N/A（不在本機跑） | N/A | N/A | demo lock，**本機不需要** |
| `tmux` | **Jetson**（demo）+ 本機（doctor 只檢查存在/Studio） | brew | apt | ❌ | doctor 只 `shutil.which` 警告 |
| `node`/`npm` | 本機（Studio frontend） | brew | apt | （Win 有但整條 demo 走不到） | doctor 只檢查存在 |
| `tailscale` | 本機（找 Jetson peer IP） | cask（CLI 可能不在 PATH，見 §3） | apt/官方 | — | `shutil.which` None 時優雅退化 |
| `ros2`/`colcon`/`nmcli`/`ip`/`ps`/`find`/`curl` | **全在 Jetson** | N/A | N/A | N/A | 全走 `run_remote` |

**本機路徑假設稽核**（會不會在 macOS 爆？）：
- `Path.home()`、`os.path.expanduser("~/.cache/pawai")`、`Path(...).expanduser()` → macOS 全正常。
- `LOCK_FLOCK_PATH = "/tmp/pawai-demo-lock.flock"` → 只當字串拼進 **Jetson 端** ssh 指令，本機從不碰。
- `modules.py` 的 `local:/tmp/studio_frontend.log` → macOS 有 `/tmp`，`tail` 也有，OK。
  （Windows native 才會壞，但已被 gate 擋下。）
- `shell.local_identity()` 用 `os.getenv("USER") or os.getenv("USERNAME") or "unknown"` →
  已含 Windows fallback（雖然 Windows 已被 gate 擋，這是 belt-and-suspenders，無害）。

**→ 沒有任何「hardcoded Linux 路徑會在 macOS 爆掉」的情況。** 這就是為什麼本輪 doc-only。

---

## 3. macOS 細節（純讀 code 稽核 + 待驗證項）

我**不能**在這台（WSL/Linux）跑 macOS runtime，以下是讀 code 推出的差異點，
全部標記為「待 Roy MacBook 驗證」：

1. **`tailscale` CLI 不一定在 PATH**（macOS App Store / 直裝 app 版）。
   - 程式碼行為：`network._run_tailscale_status_json()` 先 `shutil.which("tailscale")`，
     None 就回 `[]` peers → `doctor` 印 `⚠ no Tailscale peer`，**不會 crash**。
   - `doctor` 已內建 macOS 專屬 hint（main.py:465）：`open -a Tailscale`。
   - **操作員修法**：裝 `brew install --cask tailscale`，或把 app 內 CLI symlink 進 PATH：
     `sudo ln -s /Applications/Tailscale.app/Contents/MacOS/Tailscale /usr/local/bin/tailscale`。
   - **待驗證**：`tailscale status --json` 在 macOS 的輸出 schema 與 Linux 一致（peer 結構相同，應該一致，但沒實測）。
2. **macOS 內建 `rsync` 是 2.6.9（2006 年）**，非常舊但 `rsync -az --delete --exclude-from`
   這些旗標 2.6.9 都支援 → deploy 應該可跑。evidence pull 用 `rsync -az`（無 --delete）更保守。
   - **建議**（非必須）：`brew install rsync` 拿到 3.x，行為與 Jetson/Linux 端一致，較不易踩舊版邊角。
   - **待驗證**：用內建 2.6.9 跑一次 `pawai jetson deploy --module brain --no-build` 看 exclude-from 行為。
3. **`bash` 版本**：macOS 內建 `/bin/bash` 是 3.2（GPLv2 老版）。CLI 呼叫的 .sh 腳本
   （start.sh / cleanup.sh / healthcheck.sh）若用到 bash 4+ 語法（associative array、`${x,,}`）
   在 macOS 3.2 會壞。**但這些腳本跑在哪？** `_invoke_start_sh` 等是 `shell.stream(["bash", ...], cwd=repo_root)`
   → **在本機跑**。
   - **待驗證（重要）**：demo start 在 macOS 上會本機跑 start.sh。需確認 start.sh 不依賴 bash 4+。
     若依賴 → 操作員 `brew install bash` 並確保 PATH 優先（或腳本 shebang 指 `/usr/bin/env bash`）。
     **註**：6/18 Roy 的 MacBook 主要當「操作端」跑 status/smoke/evidence，**demo start 仍建議在能
     直連 Jetson 的環境執行 / 或 demo 本身在 Jetson tmux 跑**——若 Roy 只用 Mac 跑 status/smoke/evidence/doctor，
     完全不碰本機 bash 腳本路徑，風險為零。
4. **`platform.node()`**（demo lock 的 host 欄位）在 macOS 回主機名 → 正常，無平台問題。
5. **SSH ControlMaster / agent**：macOS 的 ssh-agent 與 keychain 整合，第一次可能要
   `ssh-add --apple-use-keychain ~/.ssh/id_ed25519`。`doctor` 的 SSH 檢查會抓到不通並給 hint。

---

## 4. Windows native（PowerShell）blocker 清單 + 各自工作量（P1，**不承諾 6/18**）

目前刻意擋下（exit 10），並引導使用者裝 WSL2。若未來要做原生 PowerShell 支援，
逐項 blocker 與工作量：

| Blocker | 為何擋 | 解掉要做什麼 | 量級 |
|---------|--------|-------------|:----:|
| 無原生 `rsync` | deploy / evidence pull 核心 | 改用 `scp -r` 或 WinSCP CLI 或 robocopy+ssh；要重寫 `_do_rsync_and_build` + `evidence._pull_read_only`，且 `--delete`/exclude 語義要重做 | 大 |
| `ssh` 行為差異 | OpenSSH for Windows 的 `~/.ssh/config`、agent、ControlPath 不同 | 測 + 文件化 Windows OpenSSH 設定；可能要避開 ControlMaster | 中 |
| `bash` 腳本（start/cleanup/healthcheck） | demo start/stop/health 都呼叫 .sh | 要嘛要求 Git Bash 並驗證腳本相容，要嘛把關鍵腳本邏輯移進 Python | 大 |
| `flock`-over-ssh + `/tmp` 語義 | demo lock 在 Jetson 端跑（其實 OK），但 Windows 本機的 lock 觀念/路徑顯示會混亂 | 大致 OK（lock 在 Jetson），主要是文件與錯誤訊息 | 小 |
| `tail`（logs local: target） | `pawai logs studio` 讀本機 `/tmp/...log` | 換成 Python 讀檔（`Path.read_text()` 取末 N 行） | 小 |
| 路徑分隔 / `expanduser` | `~/.cache/pawai`、`~/.ssh/config` 在 Windows 是 `%USERPROFILE%` | `Path.home()` 其實已跨平台；主要是 `/tmp` 硬字串 | 小 |
| 終端 emoji / 編碼 | `✓ ✗ ⚠` 在 cp950/cp1252 console 會亂碼 | `chcp 65001` 或改 ASCII fallback | 小 |

**結論**：原生 PowerShell 不是「改幾行」能搞定的，rsync + bash 腳本兩個大項就足以讓它變成
一個獨立 sprint。**6/18 前的官方答案 = 「Windows 使用者請裝 WSL2」**，這也是現在 gate 的
引導訊息（`wsl --install -d Ubuntu`）。

---

## 5. 分階段路線圖（staged path）

- **P0（現在～6/18）**：
  - WSL2：維持綠（Roy 在用）。
  - macOS：**audit-pass**；唯一動作是 Roy 在 MacBook 跑一次 §7 驗收，把 runtime 證據補上。
  - 文件：本份 plan + macOS 操作員 runbook（§7）。
  - **零 code 改動**（除非 §7 驗收當場抓到真 blocker，屆時再做最小修補）。
- **P1（6/18 後）**：
  - 若團隊真的有人只能用 Windows：評估 §4 的 rsync/bash 兩大項，估一個獨立 sprint。
  - macOS：把 §7 驗收結果回填本文件，必要時加 macOS 專屬 hint。
- **P2（更後面）**：
  - Typer + Rich + pipx 重構（更好的 help/補全/打包）。**本輪 forbidden，不在此計畫展開。**

---

## 6. 為什麼本輪「doc-only，零 code 改動」

按使用者硬性指示：「只在『低風險、additive、mock 可測、明確是跨平台 blocker』時才改 code；
任何有行為風險的就寫成文件項、不要改。」

逐項檢視後，**找不到符合條件的 code 改動**：
- macOS 沒有 hardcoded Linux 路徑會爆（§2 已逐一確認 `Path.home`/`expanduser`/`/tmp` 字串
  都只在 Jetson 端或 macOS 也有的位置）。
- CRLF / env-loading 已經有 `_load_env_file` 的 BOM+CR 正規化處理（main.py:27-48）。
- `local_identity` 已有 Windows fallback。
- platform.py 的分類正確、測試完整。

唯一「真實」的缺口是 **macOS runtime 證據**，那不是 code 能補的——只能 Roy 在 MacBook 上跑。
若硬要為了「有交付 code」而改東西，會違反 hard scope（且可能破壞 218 測試）。
**因此誠實的結論是：doc-over-code，本輪不動 code。**

> 若 §7 驗收在 macOS 上抓到具體 blocker（例如 start.sh 用了 bash 4 語法導致 demo start 在 Mac 失敗），
> 那會是一個有證據、可 mock 測試的最小修補——屆時再做，並記錄在此文件。

---

## 7. macOS 操作員 Runbook（Roy 的 6/18 MacBook）

> 目標：MacBook 當「操作端」，用 `status` / `smoke` / `evidence` / `doctor` 遠端盯 Jetson demo。
> 全程不需要在 Mac 本機跑 ROS / demo stack（那些在 Jetson tmux 裡）。

### 7.1 一次性安裝

```bash
# 1) Homebrew（若還沒裝）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# 2) 必要工具
brew install tmux node            # tmux 給 demo 腳本本機呼叫；node 給 Studio frontend（選）
brew install rsync                # 建議：拿 3.x，避免內建 2.6.9 舊版邊角
brew install --cask tailscale     # SSH 上 Jetson 的網路層

# 3) 把 repo clone 進 Mac home（不要放在外接/網路碟）
cd ~ && git clone <repo-url> elder_and_dog && cd elder_and_dog

# 4) 裝 CLI（uv 優先）
uv pip install -e tools/pawai_cli
#   沒有 uv：python3 -m pip install -e tools/pawai_cli
#   pawai: command not found → 把 ~/.local/bin（或 venv bin）加進 PATH，
#   或用 `python3 -m pawai_cli.main` 替代
```

### 7.2 SSH 上 Jetson（一次性）

```bash
# Tailscale 登入並接受 Roy 分享的 Jetson 節點
open -a Tailscale          # 登入同一個 tailnet，接受分享

# tailscale CLI 不在 PATH 的話（macOS app 版常見）：
sudo ln -s /Applications/Tailscale.app/Contents/MacOS/Tailscale /usr/local/bin/tailscale

# 設定 .env.local（個人覆寫；secrets 只放這）
cp .env.local.example .env.local
$EDITOR .env.local         # 填 JETSON_HOST / JETSON_TAILSCALE_IP / OPENROUTER_KEY

# ~/.ssh/config 加一個 Host 區塊，指向 Jetson 的 Tailscale IP，例如：
#   Host jetson-nano
#       HostName 100.x.x.x
#       User jetson
# 然後把 key 推上去（macOS keychain）：
ssh-add --apple-use-keychain ~/.ssh/id_ed25519   # 若 key 名不同自行替換
ssh-copy-id jetson-nano                           # 用你 .ssh/config 的 alias
```

### 7.3 每日操作（操作端最常用四件事）

```bash
pawai doctor                 # 環境健檢；macOS 上若 tailscale 不在 PATH 會給 `open -a Tailscale` hint
pawai status                 # 看 Jetson tmux / ROS node / demo lock / branch 對不對
pawai smoke brain --rounds 3 # 前提：Jetson 上 demo lane 已在跑；SSH 上去跑 5（或 3）輪語音 E2E
pawai smoke full --rounds 3  # brain+vision+object+gateway+trace 一次掃
pawai evidence pull          # 把 Jetson runtime/traces/*.jsonl 拉回本機 artifacts/evidence/traces（只讀）
pawai logs brain --lines 200 # 抓某模組 pane 末 200 行
```

### 7.4 macOS 上 demo start 的注意事項

- 若 Roy 只用 Mac 跑 **status / smoke / evidence / doctor / logs**：**零本機 bash 腳本路徑**，最安全，
  也是 6/18 操作端的建議用法。
- 若要在 Mac 本機跑 `pawai demo start`：它會本機 `bash` 呼叫 `start.sh`。**先確認**（§3 第 3 點）
  start.sh 不依賴 bash 4+；若失敗，`brew install bash` 並確保 PATH 優先。
- demo lock / flock 都在 Jetson 端，macOS 本機不需要 flock。

### 7.5 macOS 驗收清單（把 §0 的「runtime 待驗證」缺口補掉，約 5 分鐘）

在 MacBook 上依序跑，全綠即可把本文件 §3 的「待驗證」改成「已驗證」：

```bash
pawai --version                       # CLI 裝好了
pawai doctor                          # 平台判 macos=supported；列出該補的東西
pawai status                          # SSH 通、看得到 Jetson tmux
pawai evidence pull                   # rsync 拉得回 trace（驗 macOS rsync 行為）
pawai smoke full --rounds 3           # 前提 demo lane 在跑；驗 ssh + remote source 路徑
# （選）pawai jetson deploy --module brain --no-build   # 驗 macOS rsync --delete + exclude-from
```

跑完請把結果（哪些綠/哪些抓到 blocker）回填本文件，並通知 Carl 是否需要最小修補。

---

## 8. 測試 / 閘門狀態

- 基線：`PYTHONPATH=tools/pawai_cli python3 -m pytest tools/pawai_cli/tests -q` → **218 passed**（本輪起點，未變）。
- 本輪 doc-only，無新增 `.py`，無 flake8 目標。
- 無法在本環境驗證：**macOS runtime、Windows PowerShell runtime**（誠實標記為 deferred）。
