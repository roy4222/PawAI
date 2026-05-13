# 多人協作型 CLI 工具的 UX 最佳實踐研究

> 日期：2026-05-13
> 目的：為 pawai CLI（Python click，五人共用 Jetson）下一輪升級提供事實基礎
> 方法：WebFetch / WebSearch 一手文件 + GitHub issue / 官方 doc 為主

---

## 1. 「Doctor」模式的標竿

### 1.1 各家工具的實際做法

#### flutter doctor — 業界範本

來源：[Flutter doctor output gist](https://gist.github.com/nitya/df7c48242e68ce5da1f60b2a34540a76)、[Codecademy 整理](https://www.codecademy.com/article/check-your-flutter-installation-with-flutter-doctor)、[dhiwise](https://www.dhiwise.com/post/flutter-doctor-command-a-vital-tool-for-developers)

**輸出形式（典型 macOS）**：

```
[✓] Flutter (Channel stable, 1.17.0, on Mac OS X 10.14.6, locale en-US)
[!] Android toolchain - develop for Android devices
    ✗ Unable to locate Android SDK.
      Install Android Studio from: https://developer.android.com/studio/index.html
      Or set ANDROID_SDK_ROOT to that location.
[!] Xcode - develop for iOS and macOS
    ✗ Xcode installation is incomplete; a full installation is necessary.
      Download at: https://developer.apple.com/xcode/
      Or run:
        sudo xcode-select --switch /Applications/Xcode.app/Contents/Developer
        sudo xcodebuild -runFirstLaunch
[!] Android Studio (version 3.6)
    ✗ Flutter plugin not installed; this adds Flutter specific functionality.
    ✗ Dart plugin not installed; this adds Dart specific functionality.
[!] Connected device
    ! No devices available

! Doctor found issues in 5 categories.
```

關鍵設計：

- **每節單行狀態**：`[✓]` 全 OK、`[!]` 有 warning、`[✗]` fatal
- **節內子項目用 `✓ / ✗` 細項**
- **失敗一定附「怎麼修」**（連結 + 指令）
- **結尾 summary line**（`Doctor found issues in N categories`）— 但社群長期抱怨「沒有一行式 final verdict」（[flutter#12767](https://github.com/flutter/flutter/issues/12767)）
- `-v` / `--verbose` 開更詳細路徑與版本
- **JSON 支援**：flutter doctor 不原生支援 JSON（多年 issue 未實現）

#### brew doctor

來源：[Homebrew Manpage](https://docs.brew.sh/Manpage)

- 只在「發現問題」時才印東西，沒問題就靜默 + exit 0
- **不支援 `--json`**
- 有 `--list-checks` 列出所有 audit method，可單跑（`brew doctor check_xcode_8_without_clt`）
- 文件上明確說「這些 warning 主要是給 maintainer 看的，使用上沒問題就忽略」— 對 pawai 來說這是反模式（使用者會困惑）

#### gh auth status

來源：[gh manual](https://cli.github.com/manual/gh_auth_status)

- 按 host 分區（github.com、自己 GHE）
- 標示哪個 account 是「active」
- **支援 `--json`**：有問題時 stderr + exit 1，但 `--json` 模式永遠 exit 0 除非 fatal
- `--show-token` 才會印 token（預設遮蔽）
- `--active` / `--hostname` 縮 scope

#### tailscale netcheck / status

來源：[Tailscale CLI doc](https://tailscale.com/kb/1080/cli)

- `netcheck` 印「實體網路條件」：UDP / IPv4 / IPv6 / NAT 行為（MappingVariesByDestIP）/ UPnP·NAT-PMP·PCP / DERP latency
- **`--format=json` 與 `--format=json-line`** 都支援
- `--every` 增量輸出（持續觀察）
- `tailscale status` 是 5 欄表格：IP / machine / owner / OS / 連線狀態（active/idle，包含 direct/relay 與頻寬）
- `--json` 給機器讀；`--peers --self` 過濾

#### rustup show

來源：[rustup 1.28.0 release blog](https://blog.rust-lang.org/2025/03/02/Rustup-1.28.0/)、[man rustup-show](https://linuxcommandlibrary.com/man/rustup-show)

```
Default host: x86_64-unknown-linux-gnu
rustup home:  /home/u/.rustup

installed toolchains
--------------------
stable-x86_64-unknown-linux-gnu (default)
nightly-x86_64-unknown-linux-gnu

active toolchain
----------------
stable-x86_64-unknown-linux-gnu (default)
rustc 1.76.0 (07dca489a 2024-02-04)
```

- 「分區用 dashed underline」風格極清晰
- 1.28.0 才大幅整理輸出
- 子命令：`rustup show active-toolchain --verbose`

#### gitlab-runner verify

- 走 server side check：runner 是否仍註冊有效
- 失敗會印 token 後 6 碼（fingerprint，非完整 token） — **可借鑑的 mask 範例**

### 1.2 共通好模式

| 模式 | 採用者 | 對 pawai 啟發 |
|------|--------|---------------|
| 每節單行 status header + 子項目 | flutter, rustup | `pawai doctor` 已有，可學 `[✓]/[!]/[✗]` 三態（不只 ✓/✗） |
| 失敗訊息自帶 fix instruction | flutter, gh | 目前 doctor 部分區塊只報錯不給指令 — 待補 |
| `--json` 給 CI / automation | gh, tailscale | **pawai 應加 `pawai doctor --json`**（CI 與 `pawai status` 整合用） |
| 個別 check 可單跑 | brew (`--list-checks`) | `pawai doctor --only network` 之類 |
| 結尾一行 verdict | flutter (部分)、rustup | **目前 pawai doctor 沒有 final line，會掃過就忘** |
| token / 敏感資料 mask 預設開 | gh (`--show-token` 才開) | Tailscale auth key、SSH key 不要進 doctor 輸出 |
| `--verbose` 開全資訊（路徑、版本） | flutter, tailscale | pawai 已有 verbose，要保留 |

### 1.3 應避免的反模式

- **brew doctor 「沒問題不印，給 maintainer 看的」**：使用者跑 doctor 就是想看到「我環境好嗎」— 沒輸出讓人懷疑自己跑錯了。pawai 必須有正面確認訊號
- **flutter 多年缺 final summary line**（[flutter#12767](https://github.com/flutter/flutter/issues/12767)）：scroll 滿屏輸出後沒一行結論，使用者要回頭數 `[!]`
- **gh CLI 在 WSL 對 binfmt_misc detection 把 native Linux 誤判為 WSL**（[cli#7878](https://github.com/cli/cli/issues/7878)）：WSL detect 不要靠單一啟發式
- **flutter doctor IDE plugin 區塊輸出格式長期不一致**（[flutter#22931](https://github.com/flutter/flutter/issues/22931)）：每個 check 模組應走同一格式化函式，不要各寫各的

### 1.4 互動式 wizard（firebase init 風格）

未找到 firebase init 一手 doc，但業界共識：

- 互動式 wizard 適合「**一次性設定**」（authenticate / 選 project / 寫 config 檔）
- **每次跑都會用到的命令不該互動**（如 `flutter doctor` 沒有互動，就是純診斷）
- pawai 啟發：`pawai init`（新成員首次設定）走 wizard；`pawai doctor` 保持純診斷

---

## 2. 鎖 / Lease / 多人協作

### 2.1 Terraform state lock — 最完整參考

來源：[Terraform locking doc](https://developer.hashicorp.com/terraform/language/state/locking)、[force-unlock command](https://developer.hashicorp.com/terraform/cli/commands/force-unlock)、[Spacelift 詳解](https://spacelift.io/blog/terraform-force-unlock)、[Scalr 維運指南](https://scalr.com/learning-center/terraform-state-lock-errors-emergency-solutions-prevention-guide/)

**Lock metadata（DynamoDB / S3 backend）**：

```json
{
  "ID":        "b8814894-4a5f-217b-e97b-c4f5c02a1f88",
  "Path":      "terraform-state/prod/terraform.tfstate",
  "Operation": "OperationTypeApply",
  "Who":       "user@build-agent-01",
  "Version":   "1.7.0",
  "Created":   "2024-01-15T08:42:11.123Z",
  "Info":      ""
}
```

**錯誤訊息（教科書級）**：

```
Error: Error acquiring the state lock

Lock Info:
  ID:        b8814894-4a5f-217b-e97b-c4f5c02a1f88
  Path:      terraform-state/prod/terraform.tfstate
  Operation: OperationTypeApply
  Who:       user@build-agent-01
  Version:   1.7.0
  Created:   2024-01-15 08:42:11 UTC
  Info:

Terraform acquires a state lock to protect the state from being written
by multiple users at the same time. Please resolve the issue above and try again.
For most commands, you can disable locking with the "-lock=false" flag, but this
is not recommended.
```

**force-unlock 設計**：

- `terraform force-unlock <LOCK_ID>` — 必須帶 ID（不能盲打），防呆
- 互動 prompt：「Do you really want to force-unlock? Only 'yes' will be accepted」
- `-force` 跳過 prompt（**注意**：HashiCorp 的 `-force` 是「跳過 confirmation」不是「無視 ID」）
- 不存在「heartbeat 自動釋放」：[issue#34](https://github.com/awslabs/amazon-dynamodb-lock-client/issues/34) 與 [PR#32287](https://github.com/hashicorp/terraform/pull/32287) 顯示 DynamoDB TTL 仍在討論
- DynamoDB TTL 「delete 可能延遲數小時」，所以社群作法是：**backend 在拿 lock 時主動覆蓋過期 entry**，不靠 TTL 清

### 2.2 Git LFS lock

來源：[git-lfs locking proposal](https://github.com/git-lfs/git-lfs/blob/main/docs/proposals/locking.md)、[git-lfs-locks man](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-locks.adoc)、[git-lfs-lock man](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-lock.adoc)

Lock 結構：`ID / Owner (name+email) / Path / CommitSHA / LockedAt / UnlockedAt`

- 「先 holiday 才需要 force unlock」是設計時的明確 user story — 寫進 proposal
- `git lfs locks --json` 標準格式
- `git lfs locks --verify` 標記哪些是「我自己的鎖」（用 `O` 符號）
- **`--force` unlock 別人的鎖**是允許的，但 proposal 警告「會導致對方 push 衝突」

### 2.3 DVC lock

來源：[DVC repro](https://dvc.org/doc/command-reference/repro)

- DVC 用「進程級 file lock」防止同主機並行 `dvc repro`
- 錯誤訊息：`Failed to lock before running a command: Cannot perform the cmd since DVC is busy and locked. Please retry the cmd later.`
- **不是分散式 lock**（同一台機器內），跟 pawai 場景（單台 Jetson 五人 SSH）相似度極高
- 但 DVC 沒有 owner / age 顯示，純粹「busy」

### 2.4 MLflow

來源：[MLflow troubleshooting](https://www.mindfulchase.com/explore/troubleshooting-tips/machine-learning-and-ai-tools/troubleshooting-mlflow-in-enterprise-ml-pipelines-tracking,-registry,-and-artifact-issues.html)

- MLflow 沒有 first-class lock，企業作法是「外掛 Redis / Postgres advisory lock」
- 衝突會丟 `RESOURCE_CONFLICT`
- 教訓：**沒有 lock 的工具，使用者會自己加鎖** — pawai 一開始就有 lock 是對的

### 2.5 共通好模式

| 模式 | 採用者 | pawai 啟發 |
|------|--------|------------|
| Lock metadata 包 `ID / Owner / Operation / Created / Version` | Terraform, git-lfs | pawai 目前 lock 已有 owner+branch+lane，可加 `pawai_version` 與 `operation`（demo_start / nav_capability_start） |
| Force unlock 必須帶 `LOCK_ID`（防誤刪） | Terraform | pawai `--force` 是否該要求帶 owner name 確認？目前看起來不要求 — 建議加 |
| Force unlock 互動 prompt + 「only 'yes' 」 | Terraform | pawai 已有 `-y` 與 `--force` 分離，方向正確 |
| Lock error 訊息直接列 metadata + 修法 | Terraform | pawai 應在 lock 衝突時直接印 `pawai demo stop --force --reason="..."` 範例 |
| `--reason` audit trail | （Terraform 沒原生，企業 wrapper 常加） | **pawai 應加 `--force --reason "owner went home"`** 並寫進 lock history log |
| 「我的鎖」標記 | git-lfs `--verify` 的 `O` | `pawai status` 可在 lock 是自己時加 `(yours)` |
| 不依賴 TTL，靠「下次 acquire 時主動清過期」 | Terraform community workaround | pawai 可加 `lock.expires_at`，acquire 時看到過期就覆蓋 |

### 2.6 反模式

- **DynamoDB TTL 自動清** — 延遲不可控（5 分鐘到數小時）。pawai 應該也別只靠 mtime + cron
- **Force unlock 不留 audit** — 後來查「誰打斷誰」會吵架
- **Lock error 訊息只說 "locked"** — DVC 就是這樣，使用者只能猜。Terraform 列 metadata 才是對的

---

## 3. CLI 跨平台（Mac + Windows WSL）

### 3.1 subprocess UTF-8 / cp950 問題

來源：[CPython issue#27179](https://bugs.python.org/issue27179)、[CPython#105312](https://github.com/python/cpython/issues/105312)、[runebook subprocess Windows](https://runebook.dev/en/docs/python/library/subprocess/windows-popen-helpers)、[medium cp950 案例](https://medium.com/@dd565345421/unicodedecodeerror-cp950-codec-can-t-decode-60ce2a026159)

**根因**：Windows console codepage 與 file codepage 不同：

- ANSI codepage（GetACP）：cp950（繁中）/ cp936（簡中）/ cp1252（英文）
- OEM codepage（GetOEMCP，console 用）：常見 cp437 / cp850
- Python `subprocess.run(..., text=True)` 預設用 `locale.getpreferredencoding(False)` → 拿到 ANSI codepage → 不是 UTF-8

**標準修法**（社群共識）：

```python
subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",   # 或 "ignore"，不要用預設 strict
)
```

- 永遠顯式給 `encoding="utf-8"` + `errors="replace"`
- 若子程序本身輸出 cp950（如 Windows 內建工具），則反過來 `encoding="cp950"`，但**統一 UTF-8 是穩的策略**
- Python 3.7+ 可設 `PYTHONUTF8=1` env var 全域 UTF-8

> pawai 今天剛踩到這個 bug — 修對了。建議在 CLI entry 直接：
> ```python
> import sys, io
> if sys.platform == "win32":
>     sys.stdout.reconfigure(encoding="utf-8")
>     sys.stderr.reconfigure(encoding="utf-8")
>     os.environ.setdefault("PYTHONIOENCODING", "utf-8")
> ```

### 3.2 WSL2 偵測與路徑轉換

來源：[wslPath PyPI](https://pypi.org/project/wslPath/)、[wsl-path-converter](https://pypi.org/project/wsl-path-converter/)、[wslpath2 GitHub](https://github.com/michidk/wslpath2)、[gist lamyj](https://gist.github.com/lamyj/f311c98e8939fd5a46c8e2420364dc35)

**WSL2 偵測方法**（已驗證，可靠順序）：

1. 讀 `/proc/sys/fs/binfmt_misc/WSLInterop` 是否存在（gh CLI 用這個，但非標準 Linux distro 會誤判 — [cli#7878](https://github.com/cli/cli/issues/7878)）
2. 讀 `/proc/version` 內含 `microsoft` 或 `WSL` 字串（更穩）
3. env var `WSL_DISTRO_NAME` 存在

建議組合：

```python
def is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False
```

**路徑轉換**：

- `wslpath -u 'C:\Users\foo'` → `/mnt/c/Users/foo`
- `wslpath -w '/mnt/c/Users/foo'` → `C:\Users\foo`
- WSL2 內呼叫 Windows 工具：subprocess + `wslpath` wrapping
- 反過來 Windows 看 WSL 用 `\\wsl$\Ubuntu-22.04\home\u\...` UNC 路徑（慢）

### 3.3 各家 CLI 在 Windows 的策略

| CLI | Windows native 策略 |
|-----|---------------------|
| `gh` | 原生 Windows binary（Go），認 cmd / PowerShell；WSL 內裝 Linux 版會跟 Windows 版 auth 互不相通（[cli#10082](https://github.com/cli/cli/discussions/10082)） |
| `kubectl` | 純 Go，原生 Windows；config 路徑 `%USERPROFILE%\.kube\config` |
| `aws cli` | Python，有 MSI installer；認 `%USERPROFILE%\.aws\` |
| `tailscale` | Windows GUI app + CLI；CLI 走 named pipe 跟 daemon 通訊 |

### 3.4 ssh / rsync 在 Windows native fallback

- Windows 10 1809+ 內建 OpenSSH client（`C:\Windows\System32\OpenSSH\ssh.exe`）— 但**沒有 rsync**
- 常見 fallback：
  - 要求使用者裝 [Cwrsync](https://itefix.net/cwrsync) 或 Git for Windows 的 rsync（Git Bash 有）
  - 或退而用 `scp -r`（簡陋但內建）
  - **業界共識**：複雜部署工具直接要求 WSL2

### 3.5 「Windows 一律要求 WSL2」策略

**找到的具體討論**：

- gh CLI 採「Windows native + WSL 內另裝 Linux 版」雙軌（[Windows Central guide](https://www.windowscentral.com/how-use-github-cli-app-windows-and-wsl)、[freecodecamp](https://www.freecodecamp.org/news/github-cli-wsl2-guide/)）
- Docker Desktop 強制 WSL2 backend 已成事實標準
- Flutter 不要求 WSL，但 Android 開發很多人 WSL2 跑

對 pawai 的建議：

- pawai 用 rsync + ssh + tmux + bash 腳本 — **Windows native 跑通的成本極高**
- **明確文件化「Windows 用戶請在 WSL2 內裝 pawai」**，doctor 偵測到 Windows native 直接拒絕並指引

### 3.6 Click 框架的跨平台

來源：[Click utils](https://click.palletsprojects.com/en/stable/utils/)、[Typer doc](https://typer.tiangolo.com/)

- Click：colorama 自動處理 Windows ANSI；`echo()` / `style()` / `progressbar()` 都 cross-platform；`get_text_stream()` 處理 Python 2/3 與不同 terminal encoding
- Typer：基於 Click，加 type hints；錯誤訊息走 Rich 格式化；自動 shell completion（bash/zsh/fish/PowerShell）
- **大型 CLI 用 Click 還是 Typer**：未找到權威評論。社群實務看法：
  - Click 更穩、ecosystem 更大、自訂 group 與 context 較彈性
  - Typer 對「新建小 CLI」極佳，但 group/group plugin pattern 複雜時繞回 Click
  - **pawai 已用 Click 是 reasonable choice**，沒必要遷移

### 3.7 共通好模式

- 永遠顯式 UTF-8 + `errors="replace"` 跑 subprocess
- WSL 偵測用 `/proc/version` 含 `microsoft` + `WSL_DISTRO_NAME` 雙保險
- 路徑抽象：CLI 內部一律存 POSIX-style，呼叫 Windows 工具時才用 `wslpath` 轉
- Windows native 沒 rsync → 要求 WSL2 是合理的硬規則

### 3.8 反模式

- **GH CLI binfmt_misc 單一偵測** 誤判 [cli#7878](https://github.com/cli/cli/issues/7878)
- 假設 `LANG=en_US.UTF-8` — Windows 沒這 env var
- 把 `\` vs `/` 散落各處硬編 — 用 `pathlib.PurePosixPath` / `PureWindowsPath`
- 寫 file lock 用 `fcntl` — Windows 沒有，要用 `msvcrt` 或抽象成 `portalocker`

---

## 4. Debug Bundle / 一鍵 collect logs

### 4.1 各家做法

#### tailscale bugreport

來源：[Tailscale bug report doc](https://tailscale.com/docs/account/bug-report)、[Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli)、[Fig manual](https://fig.io/manual/tailscale/bugreport)

- **不在本機產 zip**：產一個 `BUG-1b7641a...` 識別碼，寫進雲端 log
- 使用者把識別碼貼給 support，Tailscale 後台拉 log
- 客戶端 log 自動含「health status / network map / OS-dependent info」
- 識別碼本身**不含 PII**
- `--diagnose` 印詳細 system info（給 user 自己看是否要送）
- `--record` 產 before/after 一對 ID（reproduce 用）

**設計哲學**：log 已經在跑了（daemon），bugreport 只是 marker

#### kubectl cluster-info dump

來源：[Kubernetes debug-cluster](https://kubernetes.io/docs/tasks/debug/debug-cluster/_print/)

- 收：節點狀態、control plane logs、pod logs、resource usage、cluster config
- 預設輸出到 stdout（一坨 JSON），可 `--output-directory=./dump` 拆 file
- 沒做敏感資料 mask — **這是 kubectl 反模式**（secret 可能進 dump）

#### npm doctor

來源：[npm doctor doc](https://docs.npmjs.com/cli/v10/commands/npm-doctor)

檢查項目：

1. Registry connectivity
2. npm 版本 vs latest
3. Node 版本 vs LTS
4. Registry config
5. Git executable in PATH
6. Cache / global / local node_modules 權限
7. Cache integrity（checksum 驗證）

可子選：`npm doctor connection registry versions environment permissions cache`

**沒收 log**，純檢查 — 介於 doctor 與 bugreport 之間

#### gh CLI 的 environment 收集

從 [gh issue create](https://cli.github.com/manual/gh_issue_create) 與 repo 觀察：gh 沒有 `gh bug-report` 命令。GitHub 官方教使用者「自己貼 `gh --version` + OS + 重現步驟」

#### flutter bug-report

未找到 `flutter bug-report` 命令的一手 doc — 推測社群實務是貼 `flutter doctor -v` 輸出

### 4.2 共通好模式

| 模式 | 採用者 | pawai 啟發 |
|------|--------|------------|
| 雲端 daemon log + identifier 模式 | tailscale | pawai 沒雲端，不適用 |
| 本機 zip / 目錄 dump 模式 | kubectl, 業界多數 | **pawai 建議走這個**：`pawai bugreport` → `~/pawai-bugreport-2026-05-13-1234.zip` |
| 收集項目 = 環境變數 + 版本 + 最近 log + git 狀態 | 通用 | pawai 應收：<br>- `pawai --version`, ROS distro, Python ver<br>- `git rev-parse HEAD`, `git status -s`<br>- 最近 100 行 demo log<br>- `tailscale status --json`（含網路拓撲）<br>- lock 檔內容<br>- `pawai doctor --json` |
| 子選哪些 module 要收 | npm | `pawai bugreport --modules speech,nav` |

### 4.3 隱私 / mask

- tailscale 預設不在 bugreport 帶 PII，靠識別碼讓 support 後台拉（無 client 端 mask 問題）
- kubectl 沒做 mask — 反模式
- **pawai 必須 mask**：
  - SSH key path 可印，內容絕對不印
  - Tailscale auth key（`tskey-...`）正規式遮蔽
  - OpenAI / Anthropic API key（`sk-...`）正規式遮蔽
  - `.env` 內容不要 dump，只列 keys

### 4.4 輸出格式

- **markdown 比 JSON 適合貼 GitHub issue**：tailscale 識別碼不適用 pawai（沒雲端）
- **zip 適合附件**：kubectl 走 directory dump 也行
- 建議：產一個 `bugreport-<id>.md`（人可讀，貼 issue）+ 同名 `.zip`（含 raw log）

### 4.5 反模式

- 一坨 plain text 不分區 — 看不出哪段重要
- 不 mask token — 已有多起雲端帳號洩漏案例
- 互動式要 user 同意每個檔案 — 過度

---

## 5. Output / UX 細節

### 5.1 「錯誤自帶解法」

來源：[Cargo issue#10900](https://github.com/rust-lang/cargo/issues/10900)、[Cargo issue#14363](https://github.com/rust-lang/cargo/issues/14363)、[UX patterns for CLI tools](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html)、[Optique 0.7.0](https://hackers.pub/@hongminhee/2025/optique-070)

**cargo / rust 範例**：

```
$ cargo +nightly check
error: no such command: `+nightly`
        Cargo does not handle `+toolchain` directives.
        Did you mean to run `cargo` through `rustup` instead?
```

關鍵：**錯誤訊息點名常見錯因 + 給下一步**

**Levenshtein 「Did you mean」**：

- git 是業界範本：`git stauts` → suggest `status`
- 實作標準：edit distance ≤ 2 字、最多 suggest 3 個
- Python click 內建 `click.exceptions.UsageError` 但**沒原生 suggestion** — 需自寫或用 [click-didyoumean](https://pypi.org/project/click-didyoumean/) 套件
- Optique 0.7.0 標準做法：distance threshold + 最多 3 個 suggest

對 pawai 啟發：

- lock 衝突訊息應該長：
  ```
  Error: demo lock held by alice on branch nav-demo-fix (lane=brain, age 23m).
  
  If alice forgot to release, run:
      pawai demo stop --force --reason "alice afk, taking over for demo prep"
  
  Or wait and retry, or see who's active:
      pawai status
  ```
- 命令拼錯：`pawai dotor` → suggest `doctor`

### 5.2 ANSI color 跨平台

來源：[Click utils](https://click.palletsprojects.com/en/stable/utils/)、Python `colorama`

- Click 已內建 colorama 處理 Windows
- 偵測 `NO_COLOR` env var（[no-color.org](https://no-color.org/) 標準）— 使用者明示不要色
- 偵測 stdout 不是 TTY（被 pipe / redirect）→ 自動關色
- Click `echo(..., color=None)` 預設 auto-detect

### 5.3 進度條 / Spinner

- Click `progressbar()` 跨平台，但功能少
- **業界推薦 [Rich](https://rich.readthedocs.io/)**：跨平台、Spinner / progress / table / panel 一起
- 進度條在 CI（非 TTY）會自動退化成簡單 dot — Rich 與 tqdm 都做
- pawai `pawai jetson deploy` 跑 rsync 可加 spinner，但 rsync 本身 `--info=progress2` 已有原生進度，**不要疊兩層**

### 5.4 Click vs Typer 對「大型 CLI」

- **未找到一手權威建議**（HN / Reddit 帖各說各話）
- 已知事實：
  - FastAPI 作者建議 Typer（自己寫的）
  - 多 group + 多 plugin 大型 CLI（aws cli、gh）都用底層自寫或 Click 風格
  - Typer = Click + type hint sugar；不是另一個框架
- **建議**：pawai 已用 Click，不要遷移。若想要 type hint 友善可在 Click command 內手動 type annotate

### 5.5 共通好模式

| 模式 | 採用者 | pawai 啟發 |
|------|--------|------------|
| Error → next-step instruction | cargo, terraform, gh | pawai doctor / lock / deploy 每個錯誤都檢視 |
| Levenshtein typo 提示 | git, optique | 加 `click-didyoumean` 套件，5 行裝好 |
| NO_COLOR + auto-TTY-detect | 業界標準 | Click 已處理，確認 pawai 沒手動 print ANSI 字串繞過 |
| Exit code 語意化（0 ok, 1 user error, 2 system error, 3 lock conflict） | 各家 | pawai 目前 exit code 應該盤點 |
| `--quiet` / `-q` for CI | 普遍 | pawai 已有 verbose 沒有 quiet — 補上 |

### 5.6 反模式

- 錯誤訊息光說「failed」不說為什麼、怎麼修 — 大部分內部工具的通病
- 強制色彩無視 `NO_COLOR` 或 pipe — 把使用者 grep 輸出弄壞
- 進度條疊兩層 — 看起來很忙但訊息亂

---

## 6. 對 pawai 的具體行動清單

按優先序排，皆有上述章節證據支撐：

### P0（一週內）

1. **Lock error message 補 metadata + 修法**（§2.5）：照 Terraform 格式列 ID/Owner/Lane/Operation/Age，下方接 `pawai demo stop --force --reason "..."` 範例
2. **CLI entry 強制 UTF-8 stdout**（§3.1）：Windows / WSL 啟動時 `reconfigure(encoding="utf-8")`
3. **pawai doctor 加 final summary line**（§1.3）：`Doctor found N issues in M categories`，避免 flutter 那個多年抱怨
4. **pawai bugreport 命令**（§4）：產 `~/pawai-bugreport-<ts>.zip` 含 doctor json + lock + 最近 log + git status + tailscale status，**先做 token mask**

### P1（兩週內）

5. **doctor 三態 `[✓]/[!]/[✗]`**（§1.2）— 區分 warning vs fatal
6. **doctor --json**（§1.2）— 給 CI 與 status block 整合
7. **doctor --only \<check\>**（§1.2）— 抄 brew `--list-checks` pattern
8. **Lock 加 `expires_at` 並在 acquire 時主動清過期**（§2.5）— 不靠 mtime + cron
9. **`--force --reason "..."` 寫進 lock history log**（§2.5）— audit
10. **click-didyoumean**（§5.1）— 5 行 plug-in 改善體驗
11. **WSL detect 雙保險**（§3.2）— `/proc/version` + `WSL_DISTRO_NAME`

### P2（後續）

12. **Windows native 拒絕 + 指引裝 WSL2**（§3.5）— doctor 偵測到直接 fail
13. **Exit code 盤點與文件化**（§5.5）— 0/1/2/3 語意
14. **`--quiet` 模式給 CI**（§5.5）

---

## 附錄：來源列表

### Doctor 模式
- [Flutter doctor output gist](https://gist.github.com/nitya/df7c48242e68ce5da1f60b2a34540a76)
- [Codecademy flutter doctor](https://www.codecademy.com/article/check-your-flutter-installation-with-flutter-doctor)
- [dhiwise flutter doctor](https://www.dhiwise.com/post/flutter-doctor-command-a-vital-tool-for-developers)
- [flutter#12767 — one-line summary request](https://github.com/flutter/flutter/issues/12767)
- [flutter#22931 — IDE plugin output inconsistent](https://github.com/flutter/flutter/issues/22931)
- [Homebrew Manpage (brew doctor)](https://docs.brew.sh/Manpage)
- [gh auth status manual](https://cli.github.com/manual/gh_auth_status)
- [Tailscale CLI](https://tailscale.com/kb/1080/cli)
- [rustup man rustup-show](https://linuxcommandlibrary.com/man/rustup-show)
- [Rustup 1.28.0 release](https://blog.rust-lang.org/2025/03/02/Rustup-1.28.0/)
- [npm doctor](https://docs.npmjs.com/cli/v10/commands/npm-doctor)

### Lock / Lease
- [Terraform state locking](https://developer.hashicorp.com/terraform/language/state/locking)
- [terraform force-unlock](https://developer.hashicorp.com/terraform/cli/commands/force-unlock)
- [Spacelift force-unlock walkthrough](https://spacelift.io/blog/terraform-force-unlock)
- [Scalr — state lock error guide](https://scalr.com/learning-center/terraform-state-lock-errors-emergency-solutions-prevention-guide/)
- [dynamodb-lock-client#34 — heartbeat vs lease](https://github.com/awslabs/amazon-dynamodb-lock-client/issues/34)
- [terraform PR#32287 — dynamodb_lock_ttl](https://github.com/hashicorp/terraform/pull/32287)
- [terraform#25947 — DynamoDB TTL discussion](https://github.com/hashicorp/terraform-provider-aws/issues/25947)
- [git-lfs locking proposal](https://github.com/git-lfs/git-lfs/blob/main/docs/proposals/locking.md)
- [git-lfs-locks man](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-locks.adoc)
- [git-lfs-lock man](https://github.com/git-lfs/git-lfs/blob/main/docs/man/git-lfs-lock.adoc)
- [DVC repro](https://dvc.org/doc/command-reference/repro)
- [MLflow troubleshooting (mindfulchase)](https://www.mindfulchase.com/explore/troubleshooting-tips/machine-learning-and-ai-tools/troubleshooting-mlflow-in-enterprise-ml-pipelines-tracking,-registry,-and-artifact-issues.html)

### Cross-platform / Windows / WSL
- [CPython issue#27179 — subprocess wrong encoding on Windows](https://bugs.python.org/issue27179)
- [CPython#105312 — subprocess.run default encoding](https://github.com/python/cpython/issues/105312)
- [runebook subprocess Windows](https://runebook.dev/en/docs/python/library/subprocess/windows-popen-helpers)
- [medium — cp950 codec can't decode](https://medium.com/@dd565345421/unicodedecodeerror-cp950-codec-can-t-decode-60ce2a026159)
- [wslPath PyPI](https://pypi.org/project/wslPath/)
- [wsl-path-converter PyPI](https://pypi.org/project/wsl-path-converter/)
- [wslpath2 (michidk)](https://github.com/michidk/wslpath2)
- [lamyj gist — wslpath](https://gist.github.com/lamyj/f311c98e8939fd5a46c8e2420364dc35)
- [cli#7878 — gh WSL detection false positive](https://github.com/cli/cli/issues/7878)
- [cli#10082 — credential manager Windows/WSL](https://github.com/cli/cli/discussions/10082)
- [freecodecamp — gh cli WSL2 setup](https://www.freecodecamp.org/news/github-cli-wsl2-guide/)
- [Click utils doc](https://click.palletsprojects.com/en/stable/utils/)
- [Typer doc](https://typer.tiangolo.com/)

### Debug Bundle
- [Tailscale generate a bug report](https://tailscale.com/docs/account/bug-report)
- [Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli)
- [Fig manual — tailscale bugreport](https://fig.io/manual/tailscale/bugreport)
- [kubectl cluster-info dump (Kubernetes debug docs)](https://kubernetes.io/docs/tasks/debug/debug-cluster/_print/)
- [npm doctor](https://docs.npmjs.com/cli/v10/commands/npm-doctor)

### UX 細節
- [Cargo#10900 — improve no-such-subcommand](https://github.com/rust-lang/cargo/issues/10900)
- [Cargo#14363 — handle +toolchain](https://github.com/rust-lang/cargo/issues/14363)
- [UX patterns for CLI tools (Lucas Costa)](https://lucasfcosta.com/2022/06/01/ux-patterns-cli-tools.html)
- [Optique 0.7.0 — smarter error messages](https://hackers.pub/@hongminhee/2025/optique-070)
- [Levenshtein in Go CLIs (Prabesh Thapa)](https://prabeshthapa.medium.com/from-frustrating-typos-to-smart-suggestions-implementing-levenshtein-distance-in-go-clis-3708c0a3b4e1)
- [NO_COLOR convention](https://no-color.org/)
