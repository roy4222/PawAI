# PawAI CLI v2 — Typer + Rich 重建計畫（PLAN ONLY）

> **作者**：CLI lane 技術寫作者　**日期**：2026-06-14　**狀態**：PLAN ONLY — 待 Roy 審核
>
> ⛔ **這是計畫，不是實作。6/18 前不做 full Typer/Rich rewrite。** 本份文件只規劃，零 code 改動。
> Typer/Rich/pipx 一律歸 **post-6/18**；6/18 前只允許「不改 runtime 行為、零測試破壞」的最小整備（見 §2、§10）。
>
> **上游文件（引用、不重複）**：
> - 跨平台稽核：[`elder_and_dog-wt/cli-crossplatform/docs/runbook/2026-06-14-pawai-cli-cross-platform-plan.md`](../../../../elder_and_dog-wt/cli-crossplatform/docs/runbook/2026-06-14-pawai-cli-cross-platform-plan.md)
>   （平台支援表、本機/Jetson 依賴拆分、macOS runbook、Windows blocker 工作量 — **本文不重抄，直接引用**）
> - face CLI 改善提案：[`docs/pawai_cli/2026-06-14-face-enroll-cli-proposal.md`](../../pawai_cli/2026-06-14-face-enroll-cli-proposal.md)（face 子命令現況/gap）
> - CLI v2 第一刀（已落地）：[`2026-06-10-plan-b-cli-v2-first-slice.md`](2026-06-10-plan-b-cli-v2-first-slice.md)（明文「不做 Typer/Rich 遷移＝第 2 刀」）
> - 系統 Phase 5（5A）：[`2026-06-11-phase5-productization-cli-cleanup.md`](2026-06-11-phase5-productization-cli-cleanup.md)（解除「不做 Typer」保留的歸屬）
> - Lane 3 CLI v2 完整化：[`2026-06-13-lane3-cli-v2-completion-plan.md`](2026-06-13-lane3-cli-v2-completion-plan.md)（smoke family / face 生命週期 / status 可信度，**Typer/pipx/三平台不提前**）
> - CLI 使用手冊：[`docs/pawai_cli/README.md`](../../pawai_cli/README.md)、[`usage-guide.md`](../../pawai_cli/usage-guide.md)、[`troubleshooting.md`](../../pawai_cli/troubleshooting.md)、[`team-onboarding.md`](../../pawai_cli/team-onboarding.md)、[`modules.md`](../../pawai_cli/modules.md)
>
> **Code 現實基準**：`tools/pawai_cli/pawai_cli/main.py`（2066 行，Click v1）、`platform.py`、`evidence.py`、`readiness.py`、`status.py`、`shell.py`、`lock.py`、`modules.py`、`network.py`、`errors.py`、`cache.py`。測試 `tools/pawai_cli/tests`（cross-platform plan §8 記為 **218 passed**；Lane 3 plan 記 173 — 以實機 `pytest` 為準）。conftest 有網路封鎖 + `real_repo` marker。

---

## 0. TL;DR（先講結論）

| 主題 | 結論 | 6/18 前？ |
|------|------|:---------:|
| **full Typer/Rich rewrite** | **post-6/18**。本份只給目標架構 + migration + rollback 設計 | ❌ |
| **6/18 操作端最低可用**（MacBook / WSL2 / PowerShell） | 用既有 Click CLI 即可達標；PowerShell native 不支援 → 導 WSL2 或 MacBook | ✅ §2 checklist |
| **PowerShell native 支援** | 刻意不做（platform gate exit 10），引導 WSL2。工作量見 cross-platform plan §4 | ❌ |
| **uv / pipx / editable 安裝** | 6/18 維持 `venv + uv pip install -e`；pipx 歸 post-6/18 | ✅ 維持現狀 |
| **Rich 輸出（表格 / 顏色 / spinner）** | post-6/18，且必須保留 `--plain` / `NO_COLOR` 機器可讀路徑（CI/script 依賴 stdout 解析） | ❌ |
| **command tree 凍結（§4）** | 6/18 前 surface 凍結；Typer 遷移 byte-identical 沿用此 tree | tree=✅ / 遷移=❌ |

**一句話**：6/18 操作端靠「**既有 Click CLI + MacBook/WSL2**」就夠，Typer/Rich 純粹是 post-6/18 的開發體驗升級，**不能進 6/18 變更窗口**（demo 凍結期不碰 runtime/操作工具核心路徑）。

---

## 1. 現況與痛點

### 1.1 現況（事實，引用 code）

- **框架**：Click v1，單檔 `main.py` 2066 行（外加 `evidence.py` / `readiness.py` 兩個獨立 command module 用 `cli.add_command` 掛上）。
- **命令分群**：`doctor` / `status` / `dev info` / `jetson deploy` / `demo {start,stop,school(retired)}` / `health {brain,nav}` / `smoke {brain,vision,object,nav,full}` / `object matrix` / `net wifi {list,status,connect,forget}` / `logs` / `docs` / `contract check` / `face {list,enroll,delete,rebuild,test}` / `readiness [freeze]` / `evidence pull`。
- **執行模型**：本機端只做 `git` / `ssh` / `rsync` / `bash`（呼叫 start/cleanup/healthcheck.sh）/ `tail`；重活（`ros2` / `colcon` / `nmcli` / `tmux` / `flock` / `find`）全在 Jetson 端透過 `shell.run_remote` / `shell.stream_remote` 跑（拆分權威見 cross-platform plan §2）。
- **平台 gate**：`platform.assert_supported()` 在 `cli()` callback 最前面跑，Windows-native = exit 10，WSL1 = exit 10，WSL2 在 `/mnt/c|/mnt/d` = 報錯（cross-platform plan §1.1 已逐字稽核，判定正確，**本層不改**）。
- **錯誤處理**：`errors.py::structured_error` 給 actionable hints（smoke family 已採用）；`.env` 載入有 `_load_env_file` 的 BOM + CRLF 正規化（main.py:27-48，6/4 CRLF 假成功事件的防線）。
- **安裝**：`venv + uv pip install -e tools/pawai_cli`（README §1）。

### 1.2 痛點（為何想升 Typer/Rich）

| # | 痛點 | 證據 | Typer/Rich 能解？ |
|---|------|------|:-----------------:|
| P-1 | **單檔 2066 行** main.py，命令 + 業務邏輯 + remote-command 字串組裝混雜，新人難導航 | `main.py` 全長；smoke 四個命令各自重抄一段 `probe + source ROS + stream_remote`（DRY 已部分靠 `_smoke_full_*` helper，但 brain/vision/object 仍各一份） | ⚠️ 拆檔是重構問題，Typer 只是順帶；Rich 無關 |
| P-2 | **help 文字手刻**、無 shell 補全（zsh/bash completion） | Click 有 completion 但專案未啟用；隊友靠 README 查 flag | ✅ Typer 內建 completion + 自動 help |
| P-3 | **輸出全是手刻 `click.echo` + emoji**（✓ ✗ ⚠ ℹ），無表格對齊（`status` / `face list` / `smoke full summary` 都手算欄寬 `{x:<8}`） | `_smoke_full_print_summary`、`net_wifi_list` 的 `{n.ssid:<28}`、status.py | ✅ Rich Table 自動對齊；但**會破壞 stdout 解析**（見 §1.3） |
| P-4 | **type 註解 + 參數驗證手刻**（`click.IntRange` / 手動 `if value < 0: raise`） | `smoke_brain` 的 IntRange、`smoke_vision` 的手動 `--with-events < 0` 檢查 | ✅ Typer 用 type hint 自動驗證 |
| P-5 | **長操作無進度回饋**（deploy rsync、smoke 5 輪、enroll 300s timeout 全是黑屏等待） | `face_enroll` timeout=300、deploy rsync stream | ✅ Rich spinner/progress（但 SSH stream 的即時輸出已是進度，需斟酌） |
| P-6 | **無集中式 verbosity / `--json` 慣例**（`readiness` 有 `--json`，其他沒有；`doctor` 有 `--cache` 但無 json） | readiness.py:23 vs 其他 | ⚠️ 設計問題，與框架無關 |

### 1.3 反向痛點（為何 Typer/Rich 有風險 — 必須先講）

- **stdout 是合約**：`smoke full` 的 summary、`doctor` 的 `N blocking · M warnings` 結尾、`readiness --json`、`face list` 的逐行輸出，都可能被 CI / script / 其他 agent 解析。Rich 預設加 ANSI color + box-drawing → **非 TTY 時雖會降級，但表格欄位重排會破壞既有解析**。⟹ Typer/Rich 遷移**必須保證**：非 TTY（pipe / CI）走 byte-identical-ish plain 路徑，或提供 `--plain` 強制。
- **退出碼是合約**：`doctor` exit 2（blocking）、平台 gate exit 10、smoke 透傳 remote rc、lock 衝突 exit 2。Typer 的 exception 處理與 Click 不同（`typer.Exit(code=...)`），遷移時**每個 `sys.exit(...)` / `raise SystemExit(...)` / `click.ClickException` 都要逐一對照退出碼**。
- **依賴體積**：Rich 拉進 `pygments` 等；對「五人本機 venv」可接受，但對「想 pipx 單檔分發」會變大。

---

## 2. 6/18 前最低可用 checklist（MacBook / WSL2 / PowerShell）

> **目標**：6/18 demo 當天，操作端（Roy 的 MacBook 為主）能可靠跑 `doctor` / `status` / `smoke` / `evidence` / `logs`。**全部用既有 Click CLI 達成，零 Typer/Rich。**

平台支援與每平台 runbook 的權威來源是 **cross-platform plan**；此處只列 6/18 必過的最小閘門：

### 2.1 WSL2 Ubuntu（Roy 主開發機 — 已綠）
- [ ] **6/18-必做**：`pawai doctor` 全綠（或只剩已知 warning），repo 在 Linux home（非 `/mnt/c|/mnt/d`，gate 會擋）。
- [ ] **6/18-必做**：`pawai smoke full --rounds 3` 在 demo lane 起著時通過（既有命令）。

### 2.2 macOS native（Roy 6/18 操作端 — audit-pass，待真機 smoke）
- [ ] **6/18-必做**：依 cross-platform plan §7.1–7.2 一次性安裝（brew tmux/node/rsync/tailscale + `uv pip install -e` + SSH/Tailscale 接通）。
- [ ] **6/18-必做**：跑 cross-platform plan §7.5 的 5 分鐘驗收清單（`--version` / `doctor` / `status` / `evidence pull` / `smoke full --rounds 3`），把「runtime 待驗證」缺口補掉。
- [ ] **6/18-必做（風險項）**：若操作端需在 Mac 本機 `pawai demo start`，先確認 `start.sh` 不依賴 bash 4+（cross-platform plan §3 第 3 點）；**建議改為「demo 在 Jetson tmux 跑、Mac 只當遠端操作端」以繞過本機 bash 路徑**。
- [ ] post-6/18：把 §7.5 驗收結果回填 cross-platform plan，必要時加 macOS 專屬 hint。

### 2.3 Windows PowerShell native（不支援 → 導流）
- [ ] **6/18-必做**：確認 platform gate 仍在（PowerShell/CMD/Git Bash = exit 10），且引導訊息正確（`wsl --install -d Ubuntu` + repo 搬進 Linux home）。**這是「最低可用」= 明確擋下並導流，不是讓它半殘運作。**
- **官方答案**：Windows 使用者 6/18 前一律走 **WSL2 Ubuntu** 或 **MacBook**。PowerShell native 的 rsync / bash 兩大 blocker 是獨立 sprint（cross-platform plan §4），**不承諾 6/18**。
- [ ] **6/18-必做（文件）**：team-onboarding / troubleshooting 明寫「Windows 請裝 WSL2 或用 Mac 操作端」一行，避免隊友當天卡在 exit 10 不知所措。

### 2.4 6/18 前**禁止**做的事（凍結窗口紀律）
- ❌ 不引入 Typer / Rich / pipx（破壞 218 測試風險 + demo 凍結期不碰核心工具）。
- ❌ 不改 command surface（flag / 退出碼 / stdout 格式），除非是 cross-platform plan §7.5 驗收當場抓到的**真 blocker 最小修補**。
- ❌ 不改 `platform.py` 判定邏輯（已稽核正確）。

---

## 3. Typer + Rich 重建目標（post-6/18）

> 北極星：**開發體驗升級，操作行為零退化**。surface（命令樹 / flag / 退出碼 / 機器可讀 stdout）對既有使用者與 CI **必須維持相容**（§9 compatibility wrapper）。

### 3.1 目標清單（對應 §1.2 痛點）
1. **拆檔**（P-1）：`main.py` → `pawai_cli/commands/{doctor,status,demo,smoke,jetson,face,object,net,logs,docs,contract,readiness,evidence}.py`，每檔一個 Typer sub-app，`app.add_typer(...)` 組裝。業務邏輯（remote-command 組裝、source-ROS 樣板）抽進 `pawai_cli/remote.py` 收斂 DRY。
2. **shell completion**（P-2）：`pawai --install-completion` zsh/bash 支援；help 由 type hint + docstring 自動生成。
3. **Rich 輸出**（P-3）：`status` / `face list` / `smoke full summary` / `net wifi list` / `doctor` 改 Rich Table / Panel，**但**：
   - 非 TTY（pipe / `CI=1` / `NO_COLOR`）→ 自動降級為無 ANSI plain。
   - 新增全域 `--plain`：強制無格式、欄位順序與舊版一致，給 script 解析。
4. **type-hint 驗證**（P-4）：`IntRange` → `typer.Option(min=, max=)`；移除手刻 `if < 0` 檢查。
5. **Rich progress**（P-5）：deploy rsync / smoke 多輪 / enroll 給 spinner/progress，**但 SSH stream 即時輸出優先保留**（進度不能蓋掉錯誤行）。
6. **集中 verbosity/json 慣例**（P-6）：全域 `-v/--verbose`、`--json`（凡有結構化輸出的命令都支援），收斂到一個 output helper。

### 3.2 非目標（明確排除）
- ❌ 不改 Jetson 端執行模型（remote-over-SSH 不變）。
- ❌ 不改 lock / flock / deploy rsync 安全機制（Plan B 已落地，不重做）。
- ❌ 不改 platform gate 政策。
- ❌ 不做 PowerShell native（仍歸獨立 sprint）。

---

## 4. Command Tree（6/18 凍結 surface；Typer 遷移沿用）

> 此樹 = 既有命令 + Lane 3 / face proposal 規劃中的補完。**標 `[現有]` 已實作、`[Lane3]` 屬 Lane 3 plan、`[新]` 本計畫提議（post-6/18）。** Typer 遷移時**逐一對照退出碼與 stdout**（§9）。

```
pawai
├── doctor              [現有]  --verbose --expect-demo --fix --deep --cache N
├── status              [現有]  --short
├── dev
│   └── info <module>   [現有]  --open
├── jetson
│   └── deploy          [現有]  --module --all -y/--yes --no-build --no-sync --force
├── demo
│   ├── start           [現有]  --no-studio --brain-only --nav capability -y --force
│   │                           --skip-healthcheck --with-shadow
│   ├── stop            [現有]  --force
│   └── status          [新]    別名/薄包既有 `pawai status`，補 demo-lane 視角（lock owner/lane/healthcheck 摘要）
├── smoke
│   ├── brain           [現有]  --rounds N(1..30)
│   ├── vision          [現有]  --with-events N
│   ├── object          [現有]  --with-cup
│   ├── nav             [現有]  --static（motion 屬 HITL，CLI 只做 static）
│   └── full            [現有]  --rounds N  (brain+vision+object+gateway+trace summary)
├── evidence
│   └── pull            [現有]  --dest …（rsync 只讀拉回 runtime/traces）
├── logs <module>       [現有]  --lines N   (module=all 掃 8 個 pane；local: target 用 tail)
├── face
│   ├── list            [現有]  （已有 ghost-dir ⚠ 警告）
│   ├── enroll          [現有/Lane3]  --person-name(必填) --samples 30
│   │                           [Lane3/proposal]：enroll 前 ghost-dir 警告、人名過 _clean_face_name、
│   │                           早退提示（N 秒無臉）
│   ├── delete <name>   [現有]  -y/--yes（已有注入防護 + .npz purge）
│   ├── rebuild         [現有]  （刪 pkl/.npz；proposal 建議 rebuild 前也印 ghost-dir 警告）
│   └── test            [現有]  （跑 face_perception pytest — 注意非 sim 驗證，見 face proposal §2）
├── object
│   └── matrix          [現有]  --object --distance --light --angle --trials --window
│                               --conf-min --object-topic --auto --gap --out --notes
│                               --allow-short-window
│   └── test-matrix     [新/別名]  對齊使用者心智模型；薄包 `object matrix`（保留舊名）
├── nav                 [新群組]  把 nav 相關 surface 顯式化（目前散在 demo/smoke）
│   ├── static          [新/別名]  = `smoke nav --static`（唯讀靜態檢查）
│   └── reactive        [新]      薄包 nav-avoidance-lane 的 reactive_stop 健檢/啟動引導
│                                 （**僅引導/唯讀**；實際 motion 仍 HITL，CLI 不觸發移動）
├── net
│   └── wifi
│       ├── list        [現有]
│       ├── status      [現有]
│       ├── connect <ssid>  [現有]  -y（prompt 密碼，不儲存）
│       └── forget <ssid>   [現有]  -y
├── docs <target>       [現有]  --open
├── contract
│   └── check           [現有]  --jetson
└── readiness           [現有]  --json …  / readiness freeze …
```

**新增項說明（全 post-6/18，6/18 前不做）**：
- `demo status`：使用者問「demo 起來了沒」時自然會打 `pawai demo status`；目前要打 `pawai status`。薄包別名，零行為變更。
- `object test-matrix`：使用者 prompt 提到的命名；保留 `object matrix` 為真名，`test-matrix` 為別名避免破壞既有腳本。
- `nav static` / `nav reactive`：把 nav 的「靜態 smoke」與「reactive_stop 引導」從 `smoke nav` / nav-lane script 顯式化進 `nav` 群組。**鐵律**：CLI 的 nav 命令一律**唯讀 / 引導**，**永不觸發 Go2 移動**（motion 回歸是 HITL，CLAUDE.md §nav 多處強調 nav motion `NOT_DEMO_READY`）。

---

## 5. Windows PowerShell / WSL2 / macOS 支援策略

> 權威拆解（平台支援表、本機/Jetson 依賴、blocker 工作量、macOS 細節、操作員 runbook）全在 **cross-platform plan**。本節只給「Typer 遷移時要注意的平台差異」與「6/18 導流策略」。

| 平台 | 6/18 策略 | Typer 遷移注意 |
|------|-----------|---------------|
| **WSL2 Ubuntu** | P0，已綠，維持 | completion 安裝路徑（zsh/bash）；Rich 在 Windows Terminal 的 WSL pane 顏色 OK |
| **macOS native** | P0 操作端，audit-pass + 真機 smoke（§2.2） | Rich 在 macOS Terminal/iTerm2 OK；確認 `--install-completion` zsh（macOS 預設 zsh）；rsync 2.6.9 行為不受框架影響 |
| **Linux native** | P0（CI 跑的就是），維持 | CI 在非 TTY → 必須走 plain（§9） |
| **Windows PowerShell native** | **不支援，導 WSL2/MacBook**。platform gate exit 10 維持 | 即使 post-6/18 做 Typer，**仍不解 PowerShell**；Rich 的 ANSI 在舊 conhost 亂碼是另一個理由不碰 |

**PowerShell native 導流訊息**（6/18 前確認 gate 文字正確，cross-platform plan §1.1）：
```
✗ Platform: Windows native unsupported (PowerShell / CMD / Git Bash).
  -> Install WSL2:  wsl --install -d Ubuntu
  -> Move repo:    git clone <url> ~/elder_and_dog   (NOT under /mnt/c)
```

---

## 6. uv / pipx / editable install 決策

| 維度 | 6/18（凍結期） | post-6/18 |
|------|----------------|-----------|
| **安裝方式** | **維持 `venv + uv pip install -e tools/pawai_cli`**（README §1 既有 SOP） | 評估 pipx |
| **為何 6/18 維持 editable** | ① 隊友已熟、文件已寫；② editable 讓「rsync 源碼後 CLI 立即生效」；③ 換安裝法 = 改 onboarding + 風險，凍結期不值得 | — |
| **pipx** | ❌ 不做。pipx 適合「裝給終端使用者的工具」，但 PawAI CLI 是「跟著 repo 走、常改、editable」的開發工具 | ✅ 評估：給「只操作不開發」的人（純 MacBook 操作端）一個 `pipx install` 一鍵裝，但要解決「editable vs 凍結版本」二元 |
| **uv 角色** | 維持（`uv pip install` 取代 `pip install`，CLAUDE.md 硬規則） | 可評估 `uv tool install`（uv 版的 pipx）取代 pipx，與專案 uv 慣例一致 |
| **打包** | 無（editable，不打 wheel） | post-Typer 可考慮 `uv build` 出 wheel，但會放大 Rich 依賴體積（§1.3） |

**決策**：6/18 **不碰安裝方式**。pipx/uv-tool 的取捨留待 Typer 遷移時一併決定（同一個 PR 動 `pyproject.toml` 較省）。

---

## 7. 測試矩陣

> 既有測試基線：`PYTHONPATH=tools/pawai_cli python3 -m pytest tools/pawai_cli/tests -q`（cross-platform plan §8 記 218 passed；以實機為準）。conftest 有網路封鎖 + `real_repo` marker。

### 7.1 Typer 遷移的測試守則（post-6/18）
| 軸 | 既有覆蓋 | 遷移後必加 |
|----|---------|-----------|
| **退出碼** | 部分（platform exit 10、doctor exit 2、lock exit 2 有測） | **每個命令的退出碼快照測試**（遷移前先補齊，當作 golden） |
| **stdout 格式** | 散見各命令測試 | **plain 模式 byte-level 對照**（遷移前後 `--plain` 輸出 diff = 空） |
| **平台判定** | `test_platform.py` 9 條（Darwin/Linux/WSL2/WSL1/Windows + /mnt/c + exit 10） | 不動（platform.py 不改） |
| **remote-command 組裝** | smoke/face/object 的 mock run_remote 測試 | 抽出 `remote.py` 後針對 command-string 組裝寫單元測試（不需 SSH） |
| **TTY vs 非 TTY** | 無 | **新增**：mock `sys.stdout.isatty()` → 驗證 Rich 自動降級 |
| **completion** | 無 | 新增 `--install-completion` smoke |

### 7.2 平台 runtime 測試（不在 CI，靠人）
| 平台 | 誰跑 | 何時 | 內容 |
|------|------|------|------|
| WSL2 | Roy | 隨時 | 主開發機，常態 |
| macOS | Roy | 6/18 前一次 | cross-platform plan §7.5（5 分鐘） |
| Linux native | CI | 每 PR | pytest（非 TTY → 驗 plain 路徑） |
| Windows PS | — | — | 不測（gate 擋下，導流） |

### 7.3 遷移驗收閘門（post-6/18）
- [ ] 既有 218 測試全綠（不得回歸）。
- [ ] 新增退出碼快照 + plain stdout 對照測試先綠（golden 建立於遷移**前**）。
- [ ] `pawai <cmd> --plain` 輸出與 v1 byte-identical（CI/script 相容）。
- [ ] macOS + WSL2 各跑一次 §7.2 runtime smoke。

---

## 8. Migration Plan（post-6/18，分階段不大爆破）

> 原則：**逐 command group 遷移**，不一次重寫 main.py。Typer 與 Click 可共存（Typer 底層即 Click），允許「Typer app 掛 legacy Click commands」過渡。

| 階段 | 內容 | 風險 | 閘門 |
|------|------|:----:|------|
| **M0（遷移前置）** | 補齊退出碼 + plain stdout golden 測試（§7.1）；抽 `remote.py` DRY（純重構，行為不變） | 低 | 218+golden 全綠 |
| **M1（骨架）** | 建 `typer.Typer()` 根 app，把既有 Click group 用 `typer.main.get_command` / 共存方式掛上；`pawai` 入口指向 Typer app。**命令行為不變** | 中（入口切換） | golden 全綠 + 手測各命令 help/退出碼 |
| **M2（拆檔 + type-hint）** | 逐群組 `doctor`→`status`→`smoke`→`jetson`→`face`→`object`→`net`→其餘，搬進 `commands/*.py`、改 Typer Option/type-hint，移除手刻驗證 | 中 | 每群組遷完跑該群組測試 + 退出碼快照 |
| **M3（Rich 輸出）** | 加 Rich Table/Panel/progress，**同時實作 `--plain` + 非 TTY 降級**；plain 輸出對照 golden | **高**（stdout 合約） | plain byte-identical + TTY 降級測試 |
| **M4（completion + 收尾）** | `--install-completion`、全域 `-v`/`--json` 收斂、README/usage-guide 更新 | 低 | 文件同步 + macOS/WSL2 runtime smoke |
| **M5（安裝法決策）** | 評估 pipx / `uv tool install`、wheel 打包（§6） | 中 | onboarding 文件更新 |

**每階段獨立可 merge、獨立可 rollback**（§9）。M3（Rich）最危險，安排在最後、有完整 golden 守。

---

## 9. Rollback / Compatibility Wrapper

### 9.1 相容性合約（遷移期間必須維持）
1. **命令樹不變**：§4 凍結 surface；遷移不刪/不改既有命令路徑與 flag 名。
2. **退出碼不變**：每個 `sys.exit` / `ClickException` / `typer.Exit` 對照 golden（§7.1）。
3. **plain stdout 不變**：`--plain` 與非 TTY 路徑 byte-identical-ish；Rich 只在 TTY 加彩。
4. **環境變數不變**：`PAWAI_CACHE_DIR` / `PAWAI_SYNC_CMD` / `PAWAI_TRUST_ENV_IP` / `JETSON_*` / `NO_COLOR` 行為不變。

### 9.2 Rollback 機制
- **階段化 = 隨時可退**：M0–M5 每階段一個 PR，出問題 `git revert` 單一 PR 即回到上一個綠狀態（main.py 在 M2 前不刪，逐群組搬空後才移除）。
- **入口開關（M1 期）**：可用 env `PAWAI_CLI_LEGACY=1` 在過渡期強制走舊 Click 入口（過渡期保留，M4 後移除）。此 escape hatch 讓 demo 期若 Typer 入口出包能一行退回。
- **plain 強制**：任何 Rich 輸出出包，`--plain` / `NO_COLOR=1` 立即回到無格式路徑（不需 revert）。

### 9.3 6/18 的 rollback 立場
- 6/18 前**根本沒有 Typer**，所以 6/18 的 rollback = 「什麼都不用做」。這正是把 Typer 排在 post-6/18 的最大理由：**凍結窗口不引入需要 rollback 的東西**。

---

## 10. 6/18 前必做 vs post-6/18 分界（總表）

| 項目 | 分界 | 出處 |
|------|:----:|------|
| 跑 macOS §7.5 驗收 5 分鐘清單 | **6/18-必做** | §2.2 / cross-platform plan §7.5 |
| 確認 PowerShell gate + 導流文字正確 | **6/18-必做** | §2.3 / cross-platform plan §1.1 |
| team-onboarding/troubleshooting 補「Windows 走 WSL2/Mac」一行 | **6/18-必做** | §2.3 |
| WSL2 `pawai doctor` / `smoke full` 綠 | **6/18-必做** | §2.1 |
| 維持 `venv + uv pip install -e` 安裝法 | **6/18-必做（維持現狀）** | §6 |
| 確認 Mac 本機 demo start 的 bash 4+ 風險（或改遠端操作） | **6/18-必做（風險項）** | §2.2 / cross-platform plan §3 |
| face enroll 前置改善（ghost 警告 / 人名清洗 / 早退） | post-6/18（除非 Lane 3 提前納入 — 屬零 runtime CLI 層） | face proposal §3 / Lane 3 |
| `demo status` / `object test-matrix` / `nav static|reactive` 別名 | **post-6/18** | §4 |
| Typer 骨架 + 拆檔 + type-hint（M0–M2） | **post-6/18** | §8 |
| Rich Table/progress + `--plain` 降級（M3） | **post-6/18** | §8 |
| shell completion + 全域 `-v`/`--json`（M4） | **post-6/18** | §8 |
| pipx / `uv tool install` / wheel 打包（M5） | **post-6/18** | §6 / §8 |
| PowerShell native 原生支援（rsync/bash 兩大 blocker） | **post-6/18，獨立 sprint，不承諾** | §5 / cross-platform plan §4 |

---

## 附註：與既有計畫的關係（避免重複）

- **不重做** Plan B（deploy 不刪 .env / healthcheck hard-gate / status gateway 可見）— 已落地，本計畫沿用。
- **不搶** Lane 3（smoke family / face 生命週期 / status 可信度）的零-runtime CLI 補完 — 那些可在 6/18 前做（屬 CLI 層、零 runtime 行為），本計畫的 Typer/Rich 一律在其**之後**。
- **不重抄** cross-platform plan 的平台支援表 / runbook / blocker 工作量 — 直接引用。
- 本計畫**唯一新增**的是：①「Typer/Rich 目標架構 + migration + rollback 設計」②「command tree 顯式凍結 + 提議別名」③「6/18 操作端最低可用 checklist 的 CLI-v2 視角」。
