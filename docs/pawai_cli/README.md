# PawAI CLI 使用手冊

`pawai` 是 5 人團隊的單一入口工具，把分散的 `scripts/`、`tmux`、`ssh jetson`、
`colcon build`、`bash .claude/skills/.../start.sh` 包成一致的指令。

> 它不取代既有 bash 腳本，只是讓「每個人記一套指令」變成「全隊記一套」。

> **日常使用：** 隊友 onboarding 完之後，請看 [`usage-guide.md`](usage-guide.md) — 三個高頻指令（`jetson deploy` / `demo start` / `demo stop`）的場景 walkthrough、決策樹、Phase 1 新行為、錯誤訊息對照表。本 README 保留為**指令參考手冊**（完整 flag、環境變數、Lock 機制設計）。

---

## 1. 安裝（首次）

```bash
cd ~/elder_and_dog          # 或 ~/newLife/elder_and_dog

# 先建立並啟用 venv（避免污染系統 Python，也避開 uv 找不到 venv 的錯）
python3 -m venv ~/.venv
source ~/.venv/bin/activate

uv pip install -e tools/pawai_cli
pawai --version             # 應該印出 0.1.0
```

每次新 shell 都要 `source ~/.venv/bin/activate`，或把它寫進 `~/.zshrc` / `~/.bashrc`。

沒裝 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或最後手段（不用 uv）：
python3 -m pip install -e tools/pawai_cli
```

> Jetson **不需要**裝 CLI（CLI 從你的 Mac/WSL 端跑，靠 SSH 操作 Jetson）。

### 系統前置（Mac）

```bash
brew install tmux node            # tmux 給 demo 腳本、node 給 Studio frontend
brew install --cask tailscale     # 用來 SSH 上 Jetson
```

### 系統前置（Linux/WSL）

```bash
sudo apt install tmux nodejs npm
```

### 支援平台

支援：

- macOS native
- Linux native
- WSL2 Ubuntu（repo 放在 Linux filesystem，例如 `~/elder_and_dog`）

不支援：

- Windows PowerShell / CMD / Git Bash native
- WSL1
- WSL2 但 repo 放在 `/mnt/c/...`、`/mnt/d/...` 這類 Windows filesystem

原因很務實：CLI 會用到 `ssh`、`rsync`、`flock`、`tmux`、`bash`、`/tmp` 與 Unix
permission semantics。純 Windows native 會在 deploy/demo lock 上出現不可預期行為。

### 第一次設定 .env.local

```bash
cp .env.local.example .env.local
$EDITOR .env.local       # 填 JETSON_HOST / JETSON_TAILSCALE_IP / OPENROUTER_KEY
```

`.env.local` 是個人化覆寫；`.env` 是 repo 共用預設值。**Secrets 只放 `.env.local`**。
參考 [.env.local.example](../../.env.local.example) 找完整變數列表。

### SSH key 推上 Jetson（一次性）

`.env.local` 只有 `pawai` CLI 會讀，**shell 不會自動 export**。所以直接打：

```bash
ssh-copy-id jetson             # 填你 `~/.ssh/config` 裡的 alias
```

或先把 `.env.local` source 進 shell 再用變數：

```bash
set -a; source .env.local; set +a
ssh-copy-id "$JETSON_HOST"
```

`JETSON_HOST` 預設為 `jetson-nano`，可在 `.env.local` 改成你 SSH config 裡用的 alias。
記得 `~/.ssh/config` 對應的 `Host` 區塊要先建好（內容指向 Jetson 的 Tailscale IP）。

---

## 2. 5 分鐘上手

```bash
pawai doctor                       # 1) 確認環境健康（會列出該補的東西）
pawai jetson deploy --module brain # 2) 推 brain 改動到 Jetson + colcon build
pawai demo start                   # 3) 啟動 13-window demo + 本機 Studio
pawai status                       # 4) 看 tmux/ROS node/last deploy
pawai logs brain --lines 200       # 5) 抓 brain pane 最後 200 行
pawai demo stop                    # 6) 收工
```

整套流程在 [troubleshooting.md](troubleshooting.md) 有踩過的坑全清單。

---

## 3. 指令參考

| 指令 | 一句話 |
|------|-------|
| [`pawai doctor`](#doctor) | 本機與 Jetson 環境健檢，給 actionable hint |
| [`pawai status`](#status) | 看 Jetson 當前 tmux / ROS node / git / 上次 deploy |
| [`pawai dev info <module>`](#dev-info) | 看某模組的 packages / 文件 / tests / log target |
| [`pawai jetson deploy`](#jetson-deploy) | rsync 整個 repo + colcon build 指定模組 |
| [`pawai demo start`](#demo-start) | 啟動 brain-studio-lane（Jetson tmux + 本機 Studio） |
| [`pawai demo stop`](#demo-stop) | 清掉 demo session |
| [`pawai health brain`](#health-brain) | 跑 brain demo healthcheck |
| [`pawai logs <module>`](#logs) | 抓對應 tmux pane 最後 N 行 |
| [`pawai docs <target>`](#docs) | 開架構/onboarding/契約文件 |
| [`pawai contract check`](#contract) | 跑 topic schema 驗證（預設 local，--jetson 跑遠端） |

---

### doctor

驗證本機 + Jetson 環境，**0 blocking 才能放心做事**。

```bash
pawai doctor          # 預設輸出
pawai doctor --verbose # SSH 失敗時印出 stderr 細節
```

檢查項目：

- 平台是否為 macOS / Linux / WSL2；Windows native、WSL1、`/mnt/c` repo 會被擋
- Python ≥ 3.10
- git + repo 狀態（dirty/clean）
- `.env.local` 是否存在；缺就提示 `cp .env.local.example .env.local`
- SSH 到 `$JETSON_HOST` 是否通；不通會檢查 `~/.ssh/config` 給出 ssh-copy-id 或 tailscale up 提示
- `tailscale status` 是否能跑
- `ROBOT_IP` 變數（不主動 ping）
- `tmux` / `node` / `npm` 是否在 PATH；缺的給 `brew install` 或 `apt install` 指令
- Studio frontend 的 `node_modules` 和 `.env.local`
- `OPENROUTER_KEY` 是否設定

**Exit code**：`0`（綠）/ `2`（有 blocking）。CI 友善。

### doctor flags

| Flag | Effect |
|---|---|
| (none) | full check, no API calls, no file writes |
| `--fix` | prompt to write detected Tailscale IP into `.env.local` |
| `--deep` | one OpenRouter API call to verify key |
| `--cache 30` | cache result for 30s (avoids 5-person waiting on same SSH probes) |
| `--expect-demo` | treat Gateway 8080 down as FAIL instead of SKIP |
| `--verbose` | print SSH stderr on failure |

### Network topology block

`pawai doctor` prints a topology summary near the top:

```
== Network topology ==
  ✓ local → Jetson Tailscale: OK 100.83.109.89
  ✓ Jetson internet route: wlan0
  ✓ Jetson Go2 link: eth0 192.168.123.X/24
  ✓ Jetson → Go2 ping: OK 192.168.123.161
  ℹ Gateway 8080: SKIP (no demo running)
```

Reading guide:
- `Jetson internet route: eth0` → **warning** — Ethernet likely hijacked for school uplink, Go2 link lost
- `Jetson Go2 link: ✗` → Go2 Ethernet not connected to Jetson
- `Gateway 8080: SKIP` → expected when no demo running; only red if `--expect-demo` or active demo lock

---

### status

```bash
pawai status         # 完整輸出（tmux + ROS nodes + git + last deploy）
pawai status --short # 跳過 ROS node list，適合快速看 lock/branch/tmux
```

讀 Jetson 上的：
- `tmux ls` — 找 `demo:` / `pawai_brain:` / `studio_gw:` / `llm-e2e:` 等 session
- `ros2 node list` — 看 perception/brain 是否亮
- `$JETSON_REPO/.pawai-last-deploy` — JSON 紀錄誰、何時、deploy 了哪個 module、git SHA、用 `rsync` 還是 `~/sync once`

**Heads-up 區**會警告：
- demo 正在跑，deploy 要先 stop
- 上次 deploy 的人不是你（多人協作場景）

`--short` 不會 SSH 到 Jetson 跑 `ros2 node list`，所以適合 demo 剛停、ROS daemon cache
還沒刷新時看真實 tmux/lock/deploy 狀態。

> ⚠️ **race**：`pawai demo start` 剛回來時，Jetson tmux 可能還沒 spawn，馬上跑 status
> 會看到 `tmux: none`，等 10–20 秒再跑即可。

---

### dev info

看某模組的所有相關資源。

```bash
pawai dev info brain          # 文字輸出
pawai dev info gesture --open # 用 $EDITOR / code 開主文件
```

支援的 module：`face` `speech` `gesture` `pose` `object` `nav` `brain` `studio`。
別名：`vision` → `gesture`、`object-perception` → `object`、`pawai-brain` → `brain` 等。

完整模組表在 [modules.md](modules.md)。

---

### jetson deploy

```bash
pawai jetson deploy --module brain          # sync + build brain 套件
pawai jetson deploy --module gesture        # sync + build vision_perception
pawai jetson deploy --all                   # sync + build 所有 packages
pawai jetson deploy --module brain --no-build  # 只 sync 不 build
pawai jetson deploy --module brain --no-sync   # 只 build 不 sync
pawai jetson deploy --module brain -y          # 跳過 confirm
```

**Sync 邏輯**：
1. 如果你家 `~/sync` 是 executable（個人化 wrapper），用它
2. 否則用內建 rsync，自動 exclude：`.git/`、`.env`、`.env.*`、`.env.local`、
   `.ssh/`、`build/`、`install/`、`log/`、`__pycache__/`、`.pytest_cache/`、`.venv/`、`node_modules/`、`.next/`、
   `.ruff_cache/`、`.mypy_cache/`、`.DS_Store`

Secrets 只留本機 `.env.local`，不會被 deploy 推到 Jetson。

**Build 邏輯**：在 Jetson 上跑 `colcon build --packages-select <模組對應的 packages>`，
build log 直接 stream 到本機。

**Deploy 記錄**：成功後寫 `$JETSON_REPO/.pawai-last-deploy`（JSON），
`pawai status` 會讀。

> ⚠️ Demo 正在跑時 deploy 會跳 confirm — 多數情況要先 `demo stop` 再 deploy 再 `demo start`。

---

### demo start

啟動 brain-studio-lane，分三種 mode：

```bash
pawai demo start             # 預設 = full + Studio overlay（推薦）
pawai demo start --no-studio # full mode 但不開本機 Studio
pawai demo start --brain-only # 只起 brain（minimal mode，無 perception）
pawai demo start --nav capability # 起導航避障 capability stack（手動 action 場測）
pawai demo start -y          # 跳過一般確認；不能搶別人的 lock
```

預設模式做的事：
1. 偵測舊 lane（Jetson tmux session / 本機 `next dev`），有就 auto-cleanup
2. 跑 preflight（SSH/.env/port 8080/OpenRouter key/LLM tunnel/ASR tunnel/USB 喇叭/nav session 衝突）
3. SSH 進 Jetson 起 `start_full_demo_tmux.sh`（13-window：go2/D435/face/vision/object/asr/tts/llm/executive/gateway/...）
4. 本機 frontend：
   - 缺 `.env.local` → 從 `.env.local.example` 自動生成（替換 `JETSON_TAILSCALE_IP`）
   - 缺 `node_modules` → 自動跑 `npm install`
   - 用 `node_modules/.bin/next dev` 啟動，並寫 `/tmp/pawai-frontend.pid`
5. Healthcheck：
   - 從本機 curl `http://$JETSON_TAILSCALE_IP:8080/health`
   - 從本機 probe `http://localhost:3000/studio` 是否 200
6. 印出真正的 Studio URL

成功時最後印：

```
✅ Gateway reachable from local: http://100.83.109.89:8080
✅ Frontend: http://localhost:3000/studio
```

`JETSON_TAILSCALE_IP` 必須存在。CLI 會先嘗試從 `tailscale status` 自動偵測並注入；
如果直接手動跑 `start.sh` 或偵測失敗，腳本會明確 fail，不再 fallback 到寫死 IP。

#### Nav capability mode

`pawai demo start --nav capability` 走
`.claude/skills/nav-avoidance-lane/scripts/start.sh capability`。它會啟：

- RPLIDAR `/scan_rplidar`
- D435 aligned depth + `/capability/depth_clear`
- Go2 driver + Nav2 / AMCL / twist_mux
- `reactive_stop_node mode=progressive`
- `nav_capability` 6 nodes

這個模式的 scope 是 **nav stack bringup + 手動 ROS2 action 場測**，不是 Brain 語音導航：

- ✅ 手動 `ros2 action send_goal /nav/goto_relative ...`
- ❌ 語音說「往前走」讓 Go2 移動（Executive NAV executor 尚未實作）
- ❌ 沒有場地 map 時自動導航
- ❌ detour / fallback / amcl / mapping 透過 `pawai demo start`

到新場地不要直接用家裡 map `/home/jetson/maps/home_living_room_v8.yaml`。先照
[`nav-field-runbook.md`](../pawai-brain/architecture/0511/nav/nav-field-runbook.md)
建圖或確認場地 map，再跑 capability。

第一個移動測試只做短距離：

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.3, yaw_offset: 0.0, max_speed: 0.0}"
```

如果 goal accepted 但 Go2 不動，照 `nav-field-runbook.md` 的 F7 Debug 查
`/cmd_vel_nav`、mux priority、Nav2 lifecycle。`pawai status` 只顯示 raw nav
topic，不把 WorldState 衍生欄位當 safety truth。

---

### demo stop

```bash
pawai demo stop
```

依 lock 裡的 `lane` 呼叫對應 cleanup：

- `lane=brain`（或舊 lock 無 lane）→ `.claude/skills/brain-studio-lane/scripts/cleanup.sh`
- `lane=nav_capability` → `.claude/skills/nav-avoidance-lane/scripts/cleanup.sh`

Brain cleanup 只會關閉 `/tmp/pawai-frontend.pid` 指向的本機 frontend，不會用
`pkill -f "next.*dev"` 掃掉隊友其他 Next.js 專案。

---

### health brain

```bash
pawai health brain
```

跑 `.claude/skills/brain-studio-lane/scripts/healthcheck.sh`，但由 CLI 注入
`JETSON_HOST` 與 `JETSON_TAILSCALE_IP`，避免 healthcheck 寫死 hostname 或缺 env。
Demo 跑起來後用它確認 Gateway 8080、Studio frontend、Jetson tmux 與 brain stack。

---

### logs

```bash
pawai logs brain                 # 預設 500 行
pawai logs brain --lines 200     # 改成 200 行
pawai logs all --lines 1000      # 抓全部 demo pane
```

抓的 pane 由 `modules.py` 設定。`brain` 對應 `demo:llm` + `demo:executive` + `pawai_brain:conv_graph`。

`logs all` 抓：`demo:face` `demo:vision` `demo:object` `demo:asr` `demo:tts` `demo:llm` `demo:executive` `demo:gateway`。

互動式 follow：

```bash
ssh jetson 'tmux attach -t demo'
```

---

### docs

```bash
pawai docs brain          # → docs/pawai-brain/architecture/0511/brain/brain.md
pawai docs face           # → architecture/0511/face.md
pawai docs gesture        # → architecture/0511/gesture/gesture.md
pawai docs onboarding     # → docs/pawai_cli/team-onboarding.md
pawai docs contract       # → docs/contracts/interaction_contract.md
pawai docs brain --open   # 用 $EDITOR 開
```

Unknown target → 印列表 + exit 2。

---

### contract

```bash
pawai contract check          # 本機 branch 跑 scripts/ci/check_topic_contracts.py
pawai contract check --jetson # 透過 SSH 在 Jetson deployed copy 跑
```

預設 local-first 是為了驗證**你目前 branch** 的契約一致性 — Jetson 上的 install 可能是別人的 stale sync。

---

## 4. 工作流範例

### 改完 brain 程式碼 → 推上 Jetson → 看 log

```bash
# 1. 確認環境
pawai doctor

# 2. 推 + build
pawai jetson deploy --module brain

# 3. 重啟 demo（如果有在跑）
pawai demo stop && pawai demo start

# 4. 看 log
pawai logs brain --lines 300

# 5. 改完了
pawai demo stop
```

### 跨平台搬家後第一次設定

依照 [troubleshooting.md](troubleshooting.md) 的「**Mac 搬家踩坑**」章節，
或直接跑 `pawai doctor` 一條條解掉警告。

---

## 5. 環境變數參考

CLI 讀順序：`.env` → `.env.local`（後者覆寫前者）。

| 變數 | 預設 | 用途 |
|------|------|-----|
| `JETSON_HOST` | `jetson-nano` | SSH alias / hostname |
| `JETSON_REPO` | `/home/jetson/elder_and_dog` | Jetson 上的 repo 路徑 |
| `JETSON_TAILSCALE_IP` | `100.83.109.89` | 本機 browser 連 Studio Gateway 用 |
| `ROBOT_IP` | `192.168.123.161` | Go2 IP |
| `OPENROUTER_KEY` / `OPENROUTER_API_KEY` | （無） | LLM cloud key |
| `PAWAI_LLM_MODEL` | `openai/gpt-5.4-mini` | 主線 LLM |
| `PAWAI_LLM_FALLBACK_MODEL` | `google/gemini-3-flash-preview` | LLM fallback |
| `TTS_PROVIDER` | `openrouter_gemini` | TTS 提供者 |
| `OPENROUTER_GEMINI_VOICE` | `Despina` | TTS 聲音 |
| `ASR_PROVIDER_ORDER` | `["sensevoice_cloud","sensevoice_local","whisper_local"]` | ASR 優先順序 |
| `PAWAI_REPO_ROOT` | （自動偵測 git root） | 從非 repo 目錄跑 CLI 時手動指定 |

---

## 6. 進階

### 在子目錄跑 CLI

CLI 用 `git rev-parse --show-toplevel` 找 repo root，多數情況自動正確。如果你不在 git repo 內：

```bash
PAWAI_REPO_ROOT=~/elder_and_dog pawai status
```

### 跑單元測試

```bash
python3 -m pytest tools/pawai_cli/tests -v
```

### 升級 / 重裝

```bash
uv pip install -e tools/pawai_cli --force-reinstall
```

---

## 7. Lock 機制（多人共用 Jetson）

`$JETSON_REPO/.pawai-demo-lock` 是共用 Jetson 的 single source of truth：

- `state: starting` — `pawai demo start` 已 acquire lock，正在啟動
- `state: running` — start.sh 跑完，demo 正常運行
- `lane: brain | nav_capability` — stop / force takeover 用來選正確 cleanup
- `tmux_session: demo | nav-cap-demo` — status 顯示與現場 debug 用
- `pawai demo stop` / start 失敗 — lock 移除

**stale 規則**：
- `starting` > 10 min → 視為啟動失敗，會 prompt 清掉
- `running` > 4 hr → 標 `STALE` 在 `pawai status`，**不**自動刪
- 自己留下的 stale lock 可由 `pawai demo stop` owner-aware 清掉，不需要 `--force`
- 別人的 lock 即使 stale，也要先溝通；確認對方不在用後才 `--force`

### `-y` vs `--force`

| Flag | 跳一般 prompt？ | 可以搶別人 lock？ |
|---|---|---|
| `-y` | ✅ | ❌ |
| `--force` | ✅ | ✅ |

`pawai demo start --force` / `pawai demo stop --force` / `pawai jetson deploy --force` 都會搶。
明天現場接手別人 demo 前**請先溝通**。

### Branch mismatch

`rsync` 不同步 `.git/`，Jetson 上 git 狀態不代表實際跑的 code。`.pawai-last-deploy` 才是 runtime provenance。

`pawai status` 比對：
- **local branch**（你 checkout 的）
- **install branch**（`.pawai-last-deploy` 記錄的 deploy 來源）
- **dirty**（deploy 當下 working tree 是否有未 commit 改動）

不一致時印 `⚠ MISMATCH`。要讓兩邊一致 → 切到對的 branch 再 `pawai jetson deploy --module X`。

---

## 8. 設計理念

- **包裝不取代**：所有重活還是 `scripts/*.sh` 在做，CLI 只負責「正確順序 + 環境 + 提示」
- **失敗時給 actionable hint**：doctor 不只說「missing」，會給對應的 `brew install` / `cp example`
- **idempotent**：每個指令多跑一次不會壞掉；deploy/demo start 都會偵測舊 state 自動清
- **不藏錯**：rsync/colcon 的 output 全部 stream 到本機 stdout，不吞錯誤
- **多人友善**：`.pawai-last-deploy` 記錄誰最後動了什麼；deploy 會警告別人正在 demo

---

## 8. 進一步

- 踩過的坑 + 解法：[troubleshooting.md](troubleshooting.md)
- 8 個 module 的詳細資訊：[modules.md](modules.md)
- CLI 原始碼：`tools/pawai_cli/pawai_cli/`
- brain-studio-lane start.sh：`.claude/skills/brain-studio-lane/scripts/start.sh`
- 變數模板：[.env.local.example](../../.env.local.example) / [frontend/.env.local.example](../../pawai-studio/frontend/.env.local.example)
