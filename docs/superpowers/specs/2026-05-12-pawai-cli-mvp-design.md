# PawAI CLI MVP — Design Spec

**Date**: 2026-05-12
**Deadline**: 2026-05-14（週三 5 人帶 Go2 進校園）
**Status**: Draft → pending user review → implementation
**Scope**: MVP only（6 個指令）；mock process 真起、fallback smoke、sync wrapper 全在 Phase 2

---

## 1. 目標

**為什麼現在做**：5/14-15 週三四，5 個人在自己筆電平行開發 PawAI 不同模組，但只有 1 台 Jetson + 1 隻 Go2。原本想 post-demo 才做的 CLI，因為「協作入口」變必要，提前到 demo 前完成。

**判準**：5 個人 clone repo 後跑 `pawai doctor` 通過 → 用 `pawai dev info <module>` 知道自己負責什麼 → 想實機驗證時 `pawai status` 看別人在不在跑 → 安全的話 `pawai jetson deploy --module X` → `pawai demo start` → `pawai logs X` → 完工 `pawai demo stop`。

**核心設計原則**：
1. CLI 是「協作入口 + 實機控制」，**不背負各模組 mock runtime**（那個延後）
2. 包裝既有 bash，不重寫 — `pawai demo start` 內部就是呼叫 `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`
3. `--module` 是貫穿 dev info / deploy / logs 的軸心概念，對應 8 條開發線
4. 沒有真正的 mutex 鎖；`status` 是「警告系統」不是「強制系統」

---

## 2. 範圍邊界（強制收斂避免 scope creep）

### 在範圍內（MVP）
- 6 個指令 + 8 個 module 別名
- Python 3.10+ + Click（不用 typer，避免額外 deps）
- 跨 Mac / WSL / Linux 安裝（`uv pip install -e tools/pawai_cli`）
- 純包裝既有 bash / git / ssh / rsync，不重寫任何邏輯

### 明確不在範圍內（Phase 2 各自開單獨 spec）
- ❌ `pawai dev mock <module>` 真起 mock process（每個 module 環境陷阱太多）
- ❌ `pawai fallback smoke` 自動跑三個離線 case
- ❌ `pawai sync once` rsync wrapper（沿用 `~/sync once`）
- ❌ `pawai jetson build <pkg>` 跨機器 colcon build
- ❌ tab completion / 互動 TUI
- ❌ telemetry / metrics

### 永遠不做（顯式排除）
- ❌ 真正的 mutex / file lock — 5 個人靠 Slack/Discord 溝通比較好
- ❌ 多帳號 Jetson SSH 切換 — 共用 `jetson@jetson-nano`
- ❌ Go2 IP 自動發現 — `ROBOT_IP` 已 env 化

---

## 3. 完整指令規格

### 3.1 `pawai doctor`

驗證執行環境。沒有 flag。

**輸出範例**：
```
PawAI environment doctor
────────────────────────
✓ Python 3.11.5
✓ Git 2.43 + ssh-agent loaded
✓ Repo root: /Users/roy422/newLife/elder_and_dog (clean)
✓ .env.local loaded (12 vars)
✓ JETSON_HOST=jetson-nano reachable (ssh OK, 89ms)
✓ Tailscale up (100.83.109.89)
✓ ROBOT_IP=192.168.123.161 (not pinged)
⚠ tmux 3.4 (Jetson is 3.4a — minor diff OK)
✗ Node 18 missing (Studio frontend won't run locally)
✗ OPENROUTER_KEY empty (cloud LLM unavailable, RuleBrain only)

3 critical OK · 2 warnings · 0 blocking
Run `pawai doctor --verbose` for details.
```

**檢查項目**：
- Python ≥ 3.10
- git installed + repo clean
- `.env.local` 存在且能讀
- `$JETSON_HOST` 可 ssh（用 `ssh -o ConnectTimeout=5 $JETSON_HOST echo OK`）
- Tailscale 啟用（`tailscale status`，可選）
- `$ROBOT_IP` 設了（不 ping，避免在校園 LAN ping 外網）
- tmux 在 PATH
- Node + pnpm 存在（Studio 用，缺只是 warning）
- `$OPENROUTER_KEY` 非空（缺只是 warning）

**Exit code**：0 全 critical 過；2 有 critical fail。

### 3.2 `pawai status`

查 Jetson 上現在有什麼在跑。**5 人協作避免互踩的核心指令**。

**輸出範例**：
```
PawAI live status @ jetson-nano (queried 2 sec ago)
───────────────────────────────────────────────────
🟢 tmux sessions:
   demo          14 windows  started 18:32 by jetson  (3 hr 12 min ago)
   pawai_brain   2 windows   started 18:33 by jetson
   studio_gw     1 window    started 18:35 by jetson

🟢 ROS nodes (15):
   /face_identity_node, /vision_perception_node, /object_perception_node,
   /stt_intent_node, /tts_node, /conversation_graph_node, /interaction_executive_node,
   /go2_driver_node, /event_action_bridge, /interaction_router, ...

🟡 git on Jetson:
   branch:   main (2 commits behind origin)
   last sync: 18:30 by roy@mac (`pawai jetson deploy --module brain`)

⚠ Heads-up:
   • demo session has been up 3+ hours; consider `pawai demo stop` first
   • Last deploy was by another person (roy@mac); ask before re-deploying
```

**實作**：
- `ssh $JETSON_HOST 'tmux ls'` → parse session/window count
- `ssh $JETSON_HOST 'ros2 node list 2>/dev/null'` → count + 前 10 個
- `ssh $JETSON_HOST 'cd $JETSON_REPO && git log -1 --format="%h|%ci|%s" && git status --short --branch'`
- 「Last deploy」紀錄寫進 `$JETSON_REPO/.pawai-last-deploy`（包 user + host + module + timestamp）

**Heads-up 規則**：
- Session 超過 2 小時 → 提示可考慮 stop
- 上次 deploy 不是當前使用者 → 提示先確認

**Exit code**：永遠 0（純資訊，不是 gate）。

### 3.3 `pawai dev info <module> [--open]`

印模組導覽資訊。8 個 module 各一份。

**輸出範例**（`pawai dev info gesture`）：
```
Module: gesture — 手勢辨識
──────────────────────────
Architecture:
  docs/pawai-brain/architecture/0511/gesture.md

Packages:
  vision_perception  (與 pose / object 共用 vision_perception_node)

Local tests:
  python3 -m pytest vision_perception/test -v -k gesture

Deploy:
  pawai jetson deploy --module gesture

Logs (after demo start):
  pawai logs gesture
  → tail tmux pane `demo:vision` on Jetson

Go2 access:
  No direct motion — safe for local/mock dev.
  (interaction_executive may route gesture → wave_hello/wiggle skills)

Backend choices:
  recognizer  ★ 主線 (MediaPipe Gesture Recognizer Task API)
  mediapipe   備援 (MediaPipe Hands + classifier rules)
  rtmpose     拒用 (3/21 benchmark: kp scatter to face)

Recent freeze: 2026-05-11 N7 (vote_frames 3→5, stable_s 0.5→0.3)
```

**`--open` flag**：呼叫 `$EDITOR <architecture md>`（fallback `code`、再 fallback 純印路徑）。

**8 個 module 表**（寫進 `modules.py` 常數）：

| Module | Package | Architecture md | Logs target | Go2 access |
|--------|---------|----------------|------|---------|
| `face` | `face_perception` | `face.md` | `demo:face` | none |
| `speech` | `speech_processor` | `speech.md` | `demo:asr` / `demo:tts` | TTS via Megaphone |
| `gesture` | `vision_perception` | `gesture.md` | `demo:vision` | indirect (via skills) |
| `pose` | `vision_perception` | `pose.md` | `demo:vision` | fallen_alert → stop_move |
| `object` | `object_perception` | `object.md` | `demo:object` | none |
| `nav` | `go2_robot_sdk` | (nav 文件) | `demo:go2` | **direct motion** |
| `brain` | `pawai_brain` | `brain.md` | `demo:llm` / `pawai_brain:exec` | via Executive |
| `studio` | `pawai-studio` | (studio 文件) | local `npm run dev` | none |

### 3.4 `pawai jetson deploy --module <module>`

把該 module 對應的 package 推到 Jetson 並 colcon build。**部署前先呼 status check 提醒。**

**流程**：
1. 內部呼 `pawai status`（簡短版），警告 demo session 在跑
2. 若有 demo session：問「現在 deploy 會需要重啟 demo，繼續？(y/N)」
3. rsync 該 package 上 Jetson（`rsync -avz --delete <package>/ jetson@<host>:$JETSON_REPO/<package>/`）
4. SSH 上 Jetson 跑 `colcon build --packages-select <package> && source install/setup.zsh`
5. 寫 `$JETSON_REPO/.pawai-last-deploy`：
   ```json
   {"user": "roy@mac", "module": "gesture", "package": "vision_perception", "ts": "2026-05-12T19:43:00+08:00", "git_sha": "39c2e48"}
   ```
6. 若 demo 在跑 → 印「重啟提示：`pawai demo stop && pawai demo start`」

**Flag**：
- `--no-build`：只 rsync 不 colcon
- `--no-confirm`：跳過 demo session 確認（CI / 信任場景）
- `--all`：所有 8 個 package（小心用，~3-5 分鐘）

### 3.5 `pawai demo start|stop`

包裝既有 brain-studio-lane skill。

**`pawai demo start`**：
- 等價 `bash .claude/skills/brain-studio-lane/scripts/start.sh demo`
- 但前面加一段 status check：「有 demo session 在跑了，要先 stop 嗎？」
- 印 `tmux attach -t demo` 提示（給想看 log 的）

**`pawai demo stop`**：
- 等價 `bash .claude/skills/brain-studio-lane/scripts/cleanup.sh`
- 列出被殺的 session（已內建）

**Flag**：
- `--no-studio`：只跑 brain + perception，不開 Studio gateway（適合不需要前端的人）
- `--brain-only`：只跑 brain（最小開銷）

### 3.6 `pawai logs <module>|all [--follow]`

把 tmux pane log 撈到本機。

**實作**：
- `pawai logs gesture` → `ssh $JETSON_HOST 'tmux capture-pane -p -t demo:vision -S -2000'`
- `pawai logs all` → 撈所有 demo session 的 pane（5 個主要的）
- `--follow`：類似 `tail -f`，每 2 秒 capture 一次 diff

**Module → tmux target 對應**：見 §3.3 表。

---

## 4. 目錄與安裝

```
tools/pawai_cli/
├── pyproject.toml
├── README.md
└── pawai_cli/
    ├── __init__.py
    ├── main.py              # Click root + 6 subcommand
    ├── modules.py            # MODULES 字典（8 個 module 元資料）
    ├── doctor.py             # pawai doctor
    ├── status.py             # pawai status
    ├── dev.py                # pawai dev info
    ├── jetson.py             # pawai jetson deploy (+ shared SSH util)
    ├── demo.py               # pawai demo start/stop
    ├── logs.py               # pawai logs
    └── shell.py              # subprocess + ssh helpers
```

**`pyproject.toml` 重點**：
```toml
[project]
name = "pawai-cli"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "click>=8.1",
    "python-dotenv>=1.0",   # 讀 .env.local
]

[project.scripts]
pawai = "pawai_cli.main:cli"
```

**安裝**：
```bash
cd ~/newLife/elder_and_dog
uv pip install -e tools/pawai_cli
# 之後 `pawai` 在 PATH 上
```

---

## 5. 配置與 env

CLI 啟動時 `python-dotenv.load_dotenv()` 讀順序：
1. `$PAWAI_REPO_ROOT/.env.local`（最高）
2. `$PAWAI_REPO_ROOT/.env`
3. Shell env

**必要 env**：
- `JETSON_HOST`（default `jetson-nano`）
- `JETSON_REPO`（default `/home/jetson/elder_and_dog`）
- `ROBOT_IP`（default `192.168.123.161`，僅 doctor 顯示用）

**選用**：
- `OPENROUTER_KEY` / `PAWAI_LLM_MODEL` / `TTS_PROVIDER`（doctor 顯示但不要求）
- `EDITOR`（`dev info --open` 用）

---

## 6. 實作里程碑（1-1.5 天）

### Day 1 上午（4h）— skeleton + 3 個輕量指令
- [ ] `tools/pawai_cli/` 目錄 + `pyproject.toml` + Click skeleton
- [ ] `modules.py` 8 個 module 元資料表
- [ ] `pawai doctor` 完整（含 ssh check）
- [ ] `pawai dev info <module>` + `--open`
- [ ] `pip install -e .` smoke test

### Day 1 下午（4h）— Jetson 互動
- [ ] `shell.py` SSH helper（`run_remote()` + error 處理）
- [ ] `pawai status`（含 tmux ls + ros2 node list + git status + last-deploy）
- [ ] `pawai logs <module>`（capture-pane）
- [ ] `pawai logs --follow`（polling 版）

### Day 2 上午（3h）— Deploy + Demo
- [ ] `pawai jetson deploy --module X`（rsync + colcon + last-deploy 寫入）
- [ ] `pawai demo start` / `pawai demo stop`（包既有 bash）
- [ ] `--no-confirm` / `--no-studio` / `--brain-only` flags

### Day 2 下午（3h）— 驗收 + 5 人 onboard
- [ ] WSL 端 5 個指令全跑一遍綠
- [ ] 寫 `tools/pawai_cli/README.md`（給 5 人的 quickstart）
- [ ] Update `docs/runbook/mac-migration-setup.md` 加 §10 CLI quickstart
- [ ] 5 人各自 clone → `uv pip install -e tools/pawai_cli` → `pawai doctor` 驗證

**Buffer**：剩半天處理意外。

---

## 7. 給 5 人的 quickstart（會寫進 README.md）

```bash
# 一次性
cd ~/newLife/elder_and_dog
uv pip install -e tools/pawai_cli
cp .env.example .env.local && vim .env.local   # 填 OPENROUTER_KEY 等

# 每日
pawai doctor               # 環境 OK？
pawai dev info <你的模組>   # 我負責什麼？
# ... 在自己筆電寫 code ...
python3 -m pytest <module pkg>/test -v   # 本機跑測試

# 想實機驗證
pawai status               # 別人在跑嗎？
pawai jetson deploy --module <你的模組>   # 推上去
pawai demo start           # 起 demo（或別人已經起了就跳過）
pawai logs <你的模組> --follow   # 看 log
# 對 Go2 講話 / 比手勢 / 走過去
pawai demo stop            # 結束（看 status 沒人接力的話）
```

---

## 8. 風險與緩解

| 風險 | 機率 | 影響 | 緩解 |
|------|:----:|:----:|------|
| 5/14 前做不完 | 中 | 高 | Scope hard-fixed 6 指令；超時砍 `logs --follow` 或 `--no-studio` |
| SSH key 沒派發給 5 人 | 高 | 高 | Runbook §4 加「Jetson 端執行 `for k in ~/keys/*.pub; do cat $k >> ~/.ssh/authorized_keys; done`」批次加 key |
| Windows 使用者 `python-dotenv` / SSH 雷 | 中 | 中 | doctor 偵測 Windows + 顯示 WSL fallback 提示 |
| 5 人 deploy 互踩 colcon build cache | 中 | 中 | last-deploy 記錄 + status 提醒；真衝突就改 sequential（Slack 喊一聲）|
| Studio frontend 各人版本不同 | 低 | 低 | `pawai dev info studio` 印固定 commit pinning |

---

## 9. Phase 2 待做（明確排除以收斂 MVP）

| 指令 | 描述 | 預估 |
|------|------|:----:|
| `pawai dev mock <module> [--scenario X]` | 每個 module 真起 mock launch | 1-1.5 天 |
| `pawai fallback smoke` | 三個離線 case 自動跑 + 出報告 | 0.5 天 |
| `pawai sync once` | rsync wrapper（不限 module）| 0.3 天 |
| `pawai jetson build <pkg>` | 只 build 不 deploy | 0.3 天 |
| `pawai env doctor` | 列所有 env + .env 衝突檢查 | 0.5 天 |
| Tab completion | bash/zsh/fish 自動補全 | 0.5 天 |
| Telemetry | 5 人使用情況收集 | 1 天 |

---

## 10. 驗收標準

### 10.1 WSL 端（CLI 寫完當天）
- [ ] `uv pip install -e tools/pawai_cli` 成功，`which pawai` 找到
- [ ] `pawai doctor` 全綠（或預期的 warning）
- [ ] `pawai dev info` 8 個 module 都列得出
- [ ] `pawai dev info gesture --open` 開到 architecture md
- [ ] `pawai status` 撈到 Jetson tmux + ros2 node + git
- [ ] `pawai jetson deploy --module brain` 跑通，看到 `.pawai-last-deploy` 寫入
- [ ] `pawai demo start` → `pawai logs brain` 看到 conversation_graph_node ready → `pawai demo stop`

### 10.2 5 人 onboard（5/14 中午）
- [ ] 5 個人都跑通 `pawai doctor` + `pawai dev info <自己模組>`
- [ ] 至少 2 人成功跑通 `pawai jetson deploy --module X` + `pawai demo start`
- [ ] `pawai status` 至少警示一次「另一個人剛 deploy 過」（中午有人試過撞車場景）

### 10.3 5/14 下午校園實測
- [ ] Go2 進校園後，CLI 在 Tailscale 不穩的情況下仍能用（SSH 重試）
- [ ] 至少一個 module owner 用 CLI 完成「改 code → deploy → demo → logs → 修 → re-deploy」一輪

---

## 11. 索引

| 主題 | 檔案 |
|------|------|
| Mac 遷移 housekeeping spec（前置） | `docs/superpowers/specs/2026-05-12-mac-migration-prep-design.md` |
| 六大模組架構（dev info 引用對象） | `docs/pawai-brain/architecture/0511/{brain,face,gesture,pose,object,speech}.md` |
| 既有 demo launcher（demo start 包它）| `.claude/skills/brain-studio-lane/scripts/start.sh` |
| 既有 cleanup（demo stop 包它）| `.claude/skills/brain-studio-lane/scripts/cleanup.sh` |
| 既有 transport（status SSH 邏輯參考）| `.claude/skills/jetson-verify/scripts/transport.py` |
