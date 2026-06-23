# PawAI CLI User Manual

**English** | [中文](./README.zh.md)

> **Documentation governance (governance header)**
> - **Scope**: Operations manual for the single-entry CLI (`pawai`) on the five-person shared Jetson — install / doctor / deploy / demo lock / logs.
> - **Status**: active / ops tooling manual (**not** a capability or product source-of-truth layer).
> - **Owner lane**: ops (used alongside the [`../runbook/`](../runbook/) firefighting SOPs).
> - **Source-of-truth priority**: This file is the source of truth for CLI **command behavior**; but any question of "whether a capability passes / can be claimed / how to interpret a demo" always defers to the EVIDENCE_AUTHORITY order in [`../README.md` §Conflict arbitration](../README.md#衝突仲裁誰是真相來源) (baseline-evidence ＞ convergence audit ＞ capability-baseline-spec ＞ north-star).
> - **Maintained child files**: [`usage-guide.md`](usage-guide.md) (daily use), [`team-onboarding.md`](team-onboarding.md) (getting started), [`troubleshooting.md`](troubleshooting.md) (pitfalls), [`modules.md`](modules.md) (8-module reference).
> - **Routing**: This folder is listed in [`docs/README.md`](../README.md) under "Supporting folders → PawAI CLI". The long-form spec / plan for the CLI design background lives in `../superpowers/` (historical/research-only).
> - **What this README is NOT**: It is not a capability scoreboard, not a demo script (for the script see [`../mission/README.md`](../mission/README.md)), and not the interface contract (see [`../contracts/interaction_contract.md`](../contracts/interaction_contract.md)). The fact that a CLI-printed nav action can run ≠ real movement / dynamic obstacle avoidance (nav capability always defers to baseline-evidence's insufficient_data).

`pawai` is a single-entry tool for the 5-person team that wraps the scattered `scripts/`, `tmux`, `ssh jetson`,
`colcon build`, and `bash .claude/skills/.../start.sh` into consistent commands.

> It does not replace the existing bash scripts; it just turns "everyone memorizes their own set of commands" into "the whole team memorizes one set."

> **Daily use:** After a teammate finishes onboarding, please see [`usage-guide.md`](usage-guide.md) — scenario walkthroughs, decision trees, Phase 1 new behaviors, and an error-message reference table for the three high-frequency commands (`jetson deploy` / `demo start` / `demo stop`). This README remains the **command reference manual** (complete flags, environment variables, Lock mechanism design).

---

## 1. Installation (first time)

```bash
cd ~/elder_and_dog          # 或 ~/newLife/elder_and_dog

# 先建立並啟用 venv（避免污染系統 Python，也避開 uv 找不到 venv 的錯）
python3 -m venv ~/.venv
source ~/.venv/bin/activate

uv pip install -e tools/pawai_cli
pawai --version             # 應該印出 0.1.0
```

Every new shell needs `source ~/.venv/bin/activate`, or add it to `~/.zshrc` / `~/.bashrc`.

Without `uv` installed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或最後手段（不用 uv）：
python3 -m pip install -e tools/pawai_cli
```

> The Jetson **does not need** the CLI installed (the CLI runs from your Mac/WSL side and operates the Jetson over SSH).

### System prerequisites (Mac)

```bash
brew install tmux node            # tmux 給 demo 腳本、node 給 Studio frontend
brew install --cask tailscale     # 用來 SSH 上 Jetson
```

### System prerequisites (Linux/WSL)

```bash
sudo apt install tmux nodejs npm
```

### Supported platforms

Supported:

- macOS native
- Linux native
- WSL2 Ubuntu (repo on a Linux filesystem, e.g. `~/elder_and_dog`)

Not supported:

- Windows PowerShell / CMD / Git Bash native
- WSL1
- WSL2 but with the repo on a Windows filesystem such as `/mnt/c/...`, `/mnt/d/...`

The reason is pragmatic: the CLI relies on `ssh`, `rsync`, `flock`, `tmux`, `bash`, `/tmp`, and Unix
permission semantics. Pure Windows native will produce unpredictable behavior in deploy / demo lock.

### First-time setup of .env.local

```bash
cp .env.local.example .env.local
$EDITOR .env.local       # 填 JETSON_HOST / JETSON_TAILSCALE_IP / OPENROUTER_KEY
```

`.env.local` is a personal override; `.env` holds the shared repo defaults. **Secrets go only in `.env.local`**.
See [.env.local.example](../../.env.local.example) for the complete variable list.

### Push the SSH key to the Jetson (one-time)

`.env.local` is read only by the `pawai` CLI; **the shell does not auto-export it**. So just run directly:

```bash
ssh-copy-id jetson             # 填你 `~/.ssh/config` 裡的 alias
```

Or source `.env.local` into the shell first and then use the variable:

```bash
set -a; source .env.local; set +a
ssh-copy-id "$JETSON_HOST"
```

`JETSON_HOST` defaults to `jetson-nano`; you can change it in `.env.local` to the alias you use in your SSH config.
Remember to set up the corresponding `Host` block in `~/.ssh/config` first (pointing at the Jetson's Tailscale IP).

---

## 2. 5-minute quick start

```bash
pawai doctor                       # 1) 確認環境健康（會列出該補的東西）
pawai jetson deploy --module brain # 2) 推 brain 改動到 Jetson + colcon build
pawai demo start                   # 3) 啟動 13-window demo + 本機 Studio
pawai status                       # 4) 看 tmux/ROS node/last deploy
pawai logs brain --lines 200       # 5) 抓 brain pane 最後 200 行
pawai demo stop                    # 6) 收工
```

The full flow with a complete list of pitfalls is in [troubleshooting.md](troubleshooting.md).

---

## 3. Command reference

| Command | One-liner |
|------|-------|
| [`pawai doctor`](#doctor) | Health check the local and Jetson environments, with actionable hints |
| [`pawai status`](#status) | View the Jetson's current tmux / ROS node / git / last deploy |
| [`pawai dev info <module>`](#dev-info) | View a module's packages / docs / tests / log target |
| [`pawai jetson deploy`](#jetson-deploy) | rsync the whole repo + colcon build the specified module |
| [`pawai demo start`](#demo-start) | Start the brain-studio-lane (Jetson tmux + local Studio) |
| [`pawai demo stop`](#demo-stop) | Tear down the demo session |
| [`pawai demo school`](#demo-school) | **DEPRECATED** (the 5/16 event has passed; the publisher remains in `scripts/school_demo_ending.py`) |
| [`pawai health brain`](#health-brain) | Run the brain demo healthcheck |
| [`pawai health nav`](#health-brain) | Run the nav-avoidance-lane healthcheck |
| [`pawai smoke vision`](#smoke-vision) | Run the vision lane static/HITL smoke |
| [`pawai smoke object`](#smoke-object) | Run the object lane static/HITL cup smoke |
| [`pawai object matrix`](#object-matrix) | On-site object detection matrix capture, CSV written to the Jetson |
| [`pawai smoke nav`](#smoke-nav) | Run the nav capability static-only smoke (zero motion + 8GB mutual exclusion) |
| [`pawai smoke full`](#smoke-full) | Run the 6/17 stabilization master tool: brain + vision/object static + gateway/trace |
| [`pawai logs <module>`](#logs) | Grab the last N lines of the corresponding tmux pane |
| [`pawai docs <target>`](#docs) | Open architecture/onboarding/contract docs |
| [`pawai contract check`](#contract) | Run topic schema validation (local by default, --jetson runs remote) |
| [`pawai face list`](#face-db) | List Jetson face_db persons and sample counts, flagging suspected backup directories |
| [`pawai face delete <name>`](#face-db) | Delete the specified person directory and clear the face model, retraining on restart |
| [`pawai net wifi {list,status,connect,forget}`](usage-guide.md#85-pawai-net-wifi--jetson-wi-fi-控制無需-ssh-手動) | Jetson Wi-Fi control (no manual SSH nmcli needed) |

---

### doctor

Validate the local + Jetson environment; **only with 0 blocking issues are you safe to proceed**.

```bash
pawai doctor          # 預設輸出
pawai doctor --verbose # SSH 失敗時印出 stderr 細節
```

Items checked:

- Whether the platform is macOS / Linux / WSL2; Windows native, WSL1, and a `/mnt/c` repo are blocked
- Python ≥ 3.10
- git + repo state (dirty/clean)
- Whether `.env.local` exists; if missing, suggests `cp .env.local.example .env.local`
- Whether SSH to `$JETSON_HOST` works; if not, checks `~/.ssh/config` and gives an ssh-copy-id or tailscale up hint
- Read-only spot-check of the Jetson ROS env: source Humble + repo `install/setup.zsh`, confirming core packages and the install tree timestamp
- Whether `tailscale status` runs
- The `ROBOT_IP` variable (does not actively ping)
- Whether `tmux` / `node` / `npm` are on PATH; for any missing, gives the `brew install` or `apt install` command
- The Studio frontend's `node_modules` and `.env.local`
- Whether `OPENROUTER_KEY` is set

**Exit code**: `0` (green) / `2` (has blocking issues). CI-friendly.

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
  ✓ local → Jetson Tailscale: OK YOUR_JETSON_IP
  ✓ Jetson internet route: wlan0
  ✓ Jetson Go2 link: eth0 192.168.123.X/24
  ✓ Jetson → Go2 ping: OK 192.168.123.161
  ℹ Gateway 8080: SKIP (no demo running)
```

Reading guide:
- `Jetson internet route: eth0` → **warning** — Ethernet likely hijacked for school uplink, Go2 link lost
- `Jetson Go2 link: ✗` → Go2 Ethernet not connected to Jetson
- `Gateway 8080: SKIP` → expected when no demo running; only red if `--expect-demo` or active demo lock

### Jetson ROS env block

`pawai doctor` also prints a non-blocking ROS environment sanity check before the final summary:

```
== Jetson ROS env ==
  ✓ Jetson ROS core packages present: pawai_contracts, interaction_executive, go2_interfaces
  ✓ Jetson install tree is up to date with latest commit
```

This check SSHes to Jetson with a short timeout and runs read-only commands only. It sources both `/opt/ros/humble/setup.zsh` and `$JETSON_REPO/install/setup.zsh`, then checks:

- core packages: `pawai_contracts`, `interaction_executive`, `go2_interfaces`
- whether the newest file under `install/` is older than the latest repo commit

All findings in this block are **warnings only**. Missing packages or stale `install/` output means run `pawai jetson deploy` or `colcon build` on Jetson; it does not change the `0 blocking` green path. If SSH is unavailable, the block prints one `⚠ ... skipped` line and does not block.

---

### status

```bash
pawai status         # 完整輸出（tmux + ROS nodes + git + last deploy）
pawai status --short # 跳過 ROS node list，適合快速看 lock/branch/tmux
```

Reads from the Jetson:
- `tmux ls` — find sessions like `demo:` / `pawai_brain:` / `studio_gw:` / `llm-e2e:`
- `ros2 node list` — see whether perception/brain are up
- `ps -eo … | grep go2_driver_node|go2_robot_sdk` — list the Go2 driver process's PID / user / tty / start time / cmd (P0)
- Brain runtime block — if `brain_node` is in the ROS node list, shows shadow/ISM flags, `demo_phase`, gesture/stranger alert flags, and lists any existing `ism_stage_2*` parameters; if the node is absent it shows `(brain not running)`
- `$JETSON_REPO/.pawai-last-deploy` — JSON record of who, when, which module was deployed, the git SHA, and whether `rsync` or `~/sync once` was used

**Go2 driver processes block** (P0, especially important on the five-person shared Jetson):
- Lists all `go2_driver_node` / `ros2 launch go2_robot_sdk` processes on the Jetson
- If a driver exists but **there is no demo lock at all**, it prints `⚠ drivers running with NO demo lock — orphan or direct ros2 launch`, indicating someone bypassed `pawai demo start`
- ❗ It **does not** compare the Jetson process user (`jetson`) against the lock owner (a local user such as `alice`) — the two fields have different semantics, and comparing them would misfire

The **Heads-up section** warns about:
- A demo is running, so deploy must stop first
- The last deployer was not you (multi-person collaboration scenario)

**SSH failure / timeout (🟡 fail-fast)**: When the first SSH probe (`tmux ls`) times out / fails, status immediately short-circuits and prints `✗ Jetson unreachable over SSH` + the reason; it **will not** spend another 30s timing out the remaining 4 probes one by one.

`--short` does not SSH to the Jetson to run `ros2 node list`, so it is suitable for viewing the real tmux/lock/deploy state right after a demo stops while the ROS daemon cache has not yet refreshed.

> ⚠️ **race**: Right when `pawai demo start` returns, the Jetson tmux may not have spawned yet, so running status immediately
> will show `tmux: none`; just wait 10–20 seconds and run it again.

---

### dev info

View all the resources related to a module.

```bash
pawai dev info brain          # 文字輸出
pawai dev info gesture --open # 用 $EDITOR / code 開主文件
```

Supported modules: `face` `speech` `gesture` `pose` `object` `nav` `brain` `studio`.
Aliases: `vision` → `gesture`, `object-perception` → `object`, `pawai-brain` → `brain`, etc.

The full module table is in [modules.md](modules.md).

---

### face db

`pawai face` manages `/home/jetson/face_db` on the Jetson; all database operations run over SSH.

```bash
pawai face list
pawai face delete alice
pawai face delete alice -y
```

`face list` lists the person subdirectories and `.png` sample counts; if a subdirectory name looks like a backup
(`_backup*`, `old*`, `_old*`, or a name containing `backup`), the output appends
`⚠ 疑似備份目錄，建議移出 face_db` at the end. Such directories should not remain in `face_db`, or they will be treated as identities during training.

`face delete <name>` accepts only a single-level person name; an empty string, `.`, `..`, a name containing `/`, or a name starting with `.` is rejected locally and never sent over SSH. Without `-y/--yes` it first lists the directory's sample count and requires a second confirmation; once confirmed it deletes `/home/jetson/face_db/<name>` and clears `model_sface.pkl`, so the next restart of `face_identity_node` will retrain.

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

**Sync logic** (Plan B2 priority inversion, after the 2026-06-10 `.env` deletion incident):
1. **Always use the built-in audited rsync by default**, with the exclude list coming from the single contract file
   `tools/sync/rsync-excludes.txt` (`.git/`, `.env`, `.env.*`, `.env.local`,
   `.ssh/`, `build/`, `install/`, `log/`, cache directories, etc. — 16 entries, guarded by tests)
2. `~/sync once` is now **opt-in**: it requires `PAWAI_SYNC_CMD=1` and `~/sync` to exist and be executable,
   and prints a `⚠ UNAUDITED` warning (it has no exclude contract — the culprit of the 6/10 incident)
3. **Post-sync guard**: after any sync path (whether it succeeded or failed), checks that the Jetson's
   `.env`/`.env.local` still exist; if they are gone, it fails loudly + prints the restore SOP

Secrets stay only in the local `.env.local` and are never pushed to the Jetson by deploy.
For manual sync use `scripts/sync_to_jetson.sh` (shares the same exclude contract, does not build).

**Build logic**: Runs `colcon build --packages-select <packages corresponding to the module>` on the Jetson,
with the build log streamed directly to your local machine.

**Deploy record**: On success it writes `$JETSON_REPO/.pawai-last-deploy` (JSON),
which `pawai status` reads.

> ⚠️ When a demo is running, deploy prompts for confirmation — in most cases you should `demo stop` first, then deploy, then `demo start`.

---

### demo start

Starts the brain-studio-lane, in three modes:

```bash
pawai demo start             # 預設 = full + Studio overlay（推薦）
pawai demo start --no-studio # full mode 但不開本機 Studio
pawai demo start --brain-only # 只起 brain（minimal mode，無 perception）
pawai demo start --nav capability # 起導航避障 capability stack（手動 action 場測）
pawai demo start --with-shadow # brain lane healthy/running 後啟用 shadow soak
pawai demo start -y          # 跳過一般確認；不能搶別人的 lock
pawai demo start --skip-healthcheck # 逃生口：跳過 post-start healthcheck gate（見下）
```

What the default mode does:
1. **Orphan driver preflight (P1)**: After reading the lock, if **there is no lock but the Jetson still has a `go2_driver_node` process** (a direct `ros2 launch` / manual tmux / leftover from a previous crash):
   - `--force` → automatically runs cleanup then continues
   - `-y` → exit 2 (does **not** auto-clean, to avoid CI / newcomers accidentally killing someone's manual session)
   - interactive → prompts `Cleanup orphan drivers and continue?`
   - **skips this check when a lock exists** (no reliable session id, so it avoids an unreliable judgment)
2. Detects an old lane (Jetson tmux session / local `next dev`), and auto-cleans if found
3. Runs preflight (SSH/.env/port 8080/OpenRouter key/LLM tunnel/ASR tunnel/USB speaker/nav session conflict)
4. SSHes into the Jetson and starts `start_full_demo_tmux.sh` (13-window: go2/D435/face/vision/object/asr/tts/llm/executive/gateway/...)
5. Local frontend:
   - missing `.env.local` → auto-generated from `.env.local.example` (substituting `JETSON_TAILSCALE_IP`)
   - missing `node_modules` → automatically runs `npm install`
   - launches with `node_modules/.bin/next dev` and writes `/tmp/pawai-frontend.pid`
6. Healthcheck:
   - from the local machine, curl `http://$JETSON_TAILSCALE_IP:8080/health`
   - from the local machine, probe whether `http://localhost:3000/studio` returns 200
7. Prints the real Studio URL

On success it finally prints:

```
✅ Gateway reachable from local: http://YOUR_JETSON_IP:8080
✅ Frontend: http://localhost:3000/studio
```

**Post-start healthcheck hard gate (Plan B4)**: `start.sh` rc==0 **does not count as success** —
the 6/4 `.env` CRLF incident proved that tmux may not have spawned at all yet still report `✓ Demo running`.
After start.sh succeeds, `demo start` runs the lane-specific healthcheck
(brain → `brain-studio-lane/scripts/healthcheck.sh`, nav capability →
`nav-avoidance-lane/scripts/healthcheck.sh`), and **only on pass does it transition the lock to `running`**.
On fail → exit 1, the lock stays at `starting` as evidence, and it prints inspect/cleanup guidance.
The escape hatch (only when the healthcheck itself is broken): `--skip-healthcheck`, which prints a large warning.

After the Brain lane starts successfully, it additionally reminds you that shadow soak still needs to be enabled manually:

```text
↳ shadow soak 需手動開啟：ssh <jetson> ros2 param set /brain_node ism_shadow_enabled True（或用 --with-shadow）
```

`--with-shadow` applies only to the brain lane; it cannot be combined with `--nav capability`. After the
healthcheck passes and the demo lock has transitioned to `running`, it SSHes to the Jetson and runs
`ros2 param set /brain_node ism_shadow_enabled True` on `/brain_node`, then
`ros2 param get` reads it back to confirm the value is `True`. If the param set or read-back fails, the CLI exits
non-zero and prints the manual remediation command; the demo itself is already running, so this failure does not clear the lock, nor does it stop the demo.

**`JETSON_TAILSCALE_IP` resolution priority** (shared by `demo start` / `health brain`):
1. `PAWAI_TRUST_ENV_IP=1` → trust the env value without override (an escape hatch for hand-crafted testing)
2. **Tailscale peer online + has an IP → the detected value overrides env** (even if env is already set); when env and detection disagree it prints two lines of warning telling you which IP is in use / how to silence it
3. peer offline / detection failed → keep the original env value

The reason "detection wins" by default: a stale IP left in `.env.local` is the most common failure mode in multi-person use; `pawai doctor` already flags the mismatch, but `health brain` / `demo start` need to actually **use the right IP**, not just warn.

If you run `start.sh` manually, the CLI does not inject, and detection fails, the script will fail explicitly and will no longer fall back to a hard-coded IP.

#### Nav capability mode

`pawai demo start --nav capability` goes through
`.claude/skills/nav-avoidance-lane/scripts/start.sh capability`. It starts:

- RPLIDAR `/scan_rplidar`
- D435 aligned depth + `/capability/depth_clear`
- Go2 driver + Nav2 / AMCL / twist_mux
- `reactive_stop_node mode=progressive`
- `nav_capability` 6 nodes

This mode's scope is **nav stack bringup + manual ROS2 action field testing**, not Brain voice navigation:

- ✅ manual `ros2 action send_goal /nav/goto_relative ...`
- ❌ saying "go forward" by voice to make the Go2 move (the Executive NAV executor is not yet implemented)
- ❌ auto navigation without a field map
- ❌ detour / fallback / amcl / mapping through `pawai demo start`

At a new venue, do not directly use the home map `/home/jetson/maps/home_living_room_v8.yaml`. First follow
`nav-field-runbook.md`
to build or confirm the venue map, then run capability.

The first movement test should only be a short distance:

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.3, yaw_offset: 0.0, max_speed: 0.0}"
```

If the goal is accepted but the Go2 does not move, follow the F7 Debug section of `nav-field-runbook.md` to check
`/cmd_vel_nav`, mux priority, and Nav2 lifecycle. `pawai status` only shows raw nav
topics; it does not treat WorldState-derived fields as safety truth.

---

### demo stop

```bash
pawai demo stop
```

Calls the corresponding cleanup based on the `lane` in the lock:

- `lane=brain` (or an old lock with no lane) → `.claude/skills/brain-studio-lane/scripts/cleanup.sh`
- `lane=nav_capability` → `.claude/skills/nav-avoidance-lane/scripts/cleanup.sh`

Brain cleanup only shuts down the local frontend pointed to by `/tmp/pawai-frontend.pid`; it does not use
`pkill -f "next.*dev"` to sweep away a teammate's other Next.js projects.

---

### demo school

**[DEPRECATED 2026-06-10, Plan B6]** The 5/16 school recruitment event has passed, and the command is retired —
`pawai demo school` now only reports a retired message and exits non-zero.

The ending publisher's **wait-for-subscriber-then-publish pattern** (wait for DDS
discovery → publish → spin 1.5s to ensure RELIABLE QoS delivery, solving the
one-shot `ros2 topic pub` race that drops messages roughly 1/3 of the time) remains in
`scripts/school_demo_ending.py`, where it can be run directly on the Jetson and also serve as a reference implementation for any
"reliable one-shot publish" need.

> The brain-side `school_demo_request` mode (homophone fault tolerance for "資管", etc.) is unaffected and still lives in
> pawai_brain.

---

### health brain

```bash
pawai health brain
```

Runs `.claude/skills/brain-studio-lane/scripts/healthcheck.sh`, but with the CLI injecting
`JETSON_HOST` and `JETSON_TAILSCALE_IP`, so the healthcheck does not hard-code a hostname or lack the env.
After the demo is up, use it to confirm Gateway 8080, the Studio frontend, the Jetson tmux, and the brain stack.

`pawai health nav` is the same, running `nav-avoidance-lane/scripts/healthcheck.sh`
(the corresponding check for the nav capability stack). Both are also the same scripts called behind the `demo start` post-start hard
gate (Plan B4).

> The brain healthcheck.sh now fails hard: if `JETSON_TAILSCALE_IP` is not set it errors out immediately
> (no longer falling back to a hard-coded IP; the nav script does not use this variable). Going through the `pawai`
> entry point injects it automatically; running it bare requires you to export it yourself.

---

### smoke brain (added in 6/12 system Phase 2 / 2C)

```bash
pawai smoke brain                # 預設 5 輪
pawai smoke brain --rounds 3     # 1-30 輪
```

SSHes to the Jetson and runs `scripts/smoke_test_e2e.sh` (voice E2E fixed-script acceptance). **Prerequisite: the demo
lane or llm-e2e session is already running** (the script has been dual-stack compatible since 6/12: it recognizes both the brain demo's
`conversation_graph_node` and the legacy `llm_bridge_node`; playback evidence accepts either a
Megaphone WAV or USB-speaker local playback). Before running, it first probes that the remote script exists
(fail-closed); on failure the exit code is passed through verbatim along with a "↳" fix hint (`pawai health brain`
/ `pawai demo start`). **Verified 5/5 on real hardware on 6/12**.

---

### smoke vision

```bash
pawai smoke vision                  # static-only：node / status_image hz / event publishers
pawai smoke vision --with-events 3  # HITL：static 綠後等待 3 個 gesture/pose event
```

SSHes to the Jetson and runs `scripts/smoke_test_vision.sh`. The default is static-only: it checks the
`vision_perception` node, `/vision_perception/status_image` hz > 0, and that
both topics `/event/gesture_detected` and `/event/pose_detected` have publishers.
`--with-events N` enters HITL mode after static is all green, and only counts as PASS if it accumulates N
gesture/pose events within 60 seconds.

Prerequisite: the vision lane has been started by `pawai demo start`; the CLI first sources
`/opt/ros/humble/setup.zsh` and `install/setup.zsh` to avoid a non-interactive SSH not seeing the
ROS environment. On failure the exit code is passed through verbatim, with a hint to first confirm the demo is running.

---

### smoke object

```bash
pawai smoke object              # static-only：node / debug_image hz>=3 / event publisher
pawai smoke object --with-cup   # HITL：static 綠後等待 60 秒 cup event
```

SSHes to the Jetson and runs `scripts/smoke_test_object.sh`. The default is static-only: it checks the
`object_perception` node, `/perception/object/debug_image` average hz >= 3, and that the
`/event/object_detected` topic has at least 1 publisher.

`--with-cup` calls `capture_baseline_round.py percep` after static is all green to collect a 60-second
`object.cup` positive round, outputting to `artifacts/baseline/smoke_object.jsonl`; it only counts as PASS if it writes
`pass_fail=pass` and `predicted_label=cup`. HITL mode always passes
`--gesture-topic /__no_gesture__` to prevent gesture events from polluting the object measurement (the reverse pollution is also a known pitfall).

Prerequisite: the object lane has been started by `pawai demo start`; the CLI first sources
`/opt/ros/humble/setup.zsh` and `install/setup.zsh`. On failure the exit code is passed through verbatim, with a hint to first confirm the demo is running.

---

### object matrix

```bash
pawai object matrix --object cup --distance 0.7 --light normal
pawai object matrix --object cup --distance 1.0 --light low --angle left --trials 3 --auto --gap 1.5
pawai object matrix --object cup --distance 0.7 --light normal --out artifacts/object_matrix/cup.csv
```

SSHes to the Jetson and runs `python3 scripts/obj_matrix_cap.py`, used for on-site object detection
matrix capture. The CLI is only responsible for passing through parameters, sourcing the ROS environment, and streaming live output; the capture tool itself subscribes to
`/event/object_detected`, collects trial by trial, and writes the CSV to the Jetson repo.

Common pass-through parameters: `--object`, `--distance`, `--light`, `--angle`, `--trials`,
`--window`, `--conf-min`, `--object-topic`, `--auto`, `--gap`, `--out`,
`--notes`, `--allow-short-window`. `--out` defaults to
`artifacts/object_matrix/object_matrix.csv`; on success the CLI prints the full CSV path on the Jetson.
When you need to pull it back to your local machine, use `pawai evidence pull` or `scp`.

Daily on-hardware matrix use: first `pawai demo start` to bring up the object lane, then run
`pawai object matrix ...` one entry at a time across object / distance / light /
angle combinations, and before wrapping up each day pull
`artifacts/object_matrix/*.csv` back and put it into evidence. On failure the exit code is passed through verbatim; if the object
lane is not up, restart the demo first, then capture.

### smoke nav

```bash
pawai smoke nav --static   # static-only：nodes / scan hz / AMCL / action list / reactive status
```

SSHes to the Jetson and runs `scripts/smoke_test_nav_static.sh`. `--static` must be passed explicitly; without it the command is rejected, because dynamic nav regression is HITL and outside the scope of the CLI's automated smoke.

This smoke is a zero-motion, read-only check: it only reads `ros2 node list`, `ros2 topic hz /scan_rplidar`, `ros2 topic info /amcl_pose`, `ros2 action list`, and `ros2 topic info /state/reactive_stop/status`. The script does not send actions, does not publish `/cmd_vel*`, and does not touch `/goal_pose`.

Before running, the CLI first reads the demo lock. If the brain demo lane is running, or any non-`nav_capability` lane holds the lock, it fails before the remote script and prompts you to `pawai demo stop` first; this is the mutual-exclusion guard between the brain and nav stacks on the 8GB Jetson. Only after the mutual exclusion passes does it probe that the remote script exists and source `/opt/ros/humble/setup.zsh` and `install/setup.zsh` to run.

---

### smoke full

```bash
pawai smoke full               # brain 3 輪 + vision/object static + gateway/trace
pawai smoke full --rounds 5    # 調整 brain E2E 輪數（1-30）
```

The 6/17 stabilization master tool. The CLI SSHes to the Jetson segment by segment and aggregates the rc:
`brain` runs the existing `scripts/smoke_test_e2e.sh` (3 rounds by default), `vision` runs
`scripts/smoke_test_vision.sh` static-only, `object` runs
`scripts/smoke_test_object.sh` static-only, then it checks the Studio gateway
`http://localhost:8080/health` must contain `"status":"ok"`, and finally compares
whether the total line count of `runtime/traces/*.jsonl` increases after a brief wait.

`smoke full` explicitly excludes nav and does not send a goal: on the 8GB Jetson the brain and nav are resource-exclusive, and full
only verifies the brain / perception static / gateway evidence chain needed for the demo to stabilize. Any segment FAIL
makes the overall exit non-zero; the summary table lists each segment's PASS/FAIL and rc, with a "↳" fix hint for failing segments.

---

### evidence pull (added in 6/12 system Phase 2 / 2C)

```bash
pawai evidence pull                      # → artifacts/evidence/traces/
pawai evidence pull --dest /tmp/traces   # 自訂目的地
```

rsyncs the Jetson gateway trace store's `runtime/traces/*.jsonl` (Evidence Center on-disk output,
see `docs/architecture/studio/README.md`) back to the local machine and prints a summary
(files / events / suppressed). **Read-only**: no `--delete`, does not touch the Jetson side, does not rewrite the
JSONL (Roy D5: the CLI is only responsible for reading and exporting). The failure message includes fixes (`pawai doctor` to check
Tailscale; no files on the Jetson side = the gateway is not running or `PAWAI_TRACE_STORE_ENABLED=0`).

---

### logs

```bash
pawai logs brain                 # 預設 500 行
pawai logs brain --lines 200     # 改成 200 行
pawai logs all --lines 1000      # 抓全部 demo pane
```

The panes grabbed are configured by `modules.py`. `brain` maps to `demo:llm` + `demo:executive` + `pawai_brain:conv_graph`.

`logs all` grabs: `demo:face` `demo:vision` `demo:object` `demo:asr` `demo:tts` `demo:llm` `demo:executive` `demo:gateway`.

Interactive follow:

```bash
ssh jetson 'tmux attach -t demo'
```

---

### docs

```bash
pawai docs brain          # → docs/archive/pawai-brain-legacy/architecture-0511/brain/brain.md
pawai docs face           # → architecture/0511/face.md
pawai docs gesture        # → architecture/0511/gesture/gesture.md
pawai docs onboarding     # → docs/pawai_cli/team-onboarding.md
pawai docs contract       # → docs/contracts/interaction_contract.md
pawai docs brain --open   # 用 $EDITOR 開
```

Unknown target → prints the list + exit 2.

---

### contract

```bash
pawai contract check          # 本機 branch 跑 scripts/ci/check_topic_contracts.py
pawai contract check --jetson # 透過 SSH 在 Jetson deployed copy 跑
```

The local-first default is to validate the contract consistency of **your current branch** — the install on the Jetson may be someone else's stale sync.

---

## 4. Workflow examples

### Finished editing brain code → push to Jetson → view logs

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

### First setup after moving across platforms

Follow the "**Mac move-in pitfalls**" section of [troubleshooting.md](troubleshooting.md),
or just run `pawai doctor` and clear the warnings one by one.

---

## 5. Environment variable reference

CLI read order: `.env` → `.env.local` (the latter overrides the former).

| Variable | Default | Purpose |
|------|------|-----|
| `JETSON_HOST` | `jetson-nano` | SSH alias / hostname |
| `JETSON_REPO` | `/home/jetson/elder_and_dog` | The repo path on the Jetson |
| `JETSON_TAILSCALE_IP` | `YOUR_JETSON_IP` | Used by the local browser to reach the Studio Gateway |
| `ROBOT_IP` | `192.168.123.161` | Go2 IP |
| `OPENROUTER_KEY` / `OPENROUTER_API_KEY` | (none) | LLM cloud key |
| `PAWAI_LLM_MODEL` | `openai/gpt-5.4-mini` | Primary LLM |
| `PAWAI_LLM_FALLBACK_MODEL` | `google/gemini-3-flash-preview` | LLM fallback |
| `TTS_PROVIDER` | `openrouter_gemini` | TTS provider |
| `OPENROUTER_GEMINI_VOICE` | `Despina` | TTS voice |
| `ASR_PROVIDER_ORDER` | `["sensevoice_cloud","sensevoice_local","whisper_local"]` | ASR priority order |
| `PAWAI_REPO_ROOT` | (auto-detects git root) | Manually specify when running the CLI from a non-repo directory |

---

## 6. Advanced

### Running the CLI from a subdirectory

The CLI uses `git rev-parse --show-toplevel` to find the repo root, which is automatically correct in most cases. If you are not inside a git repo:

```bash
PAWAI_REPO_ROOT=~/elder_and_dog pawai status
```

### Running unit tests

```bash
python3 -m pytest tools/pawai_cli/tests -v
```

### Upgrade / reinstall

```bash
uv pip install -e tools/pawai_cli --force-reinstall
```

---

## 7. Lock mechanism (shared Jetson among multiple people)

`$JETSON_REPO/.pawai-demo-lock` is the single source of truth for the shared Jetson:

- `state: starting` — `pawai demo start` has acquired the lock and is starting up
- `state: running` — start.sh finished and the demo is running normally
- `lane: brain | nav_capability` — used by stop / force takeover to select the correct cleanup
- `tmux_session: demo | nav-cap-demo` — for status display and on-site debugging
- `pawai demo stop` / start failure — the lock is removed

**Stale rules**:
- `starting` > 10 min → treated as a startup failure, prompts to clear
- `running` > 4 hr → marked `STALE` in `pawai status`, but **not** auto-deleted
- A stale lock you left behind can be cleared by `pawai demo stop` owner-aware, without needing `--force`
- Even if someone else's lock is stale, communicate first; only `--force` after confirming they are not using it

### `-y` vs `--force`

| Flag | Skip the normal prompt? | Can take over someone else's lock? |
|---|---|---|
| `-y` | ✅ | ❌ |
| `--force` | ✅ | ✅ |

`pawai demo start --force` / `pawai demo stop --force` / `pawai jetson deploy --force` all take over.
Before taking over someone else's demo on-site tomorrow, **please communicate first**.

### Branch mismatch

`rsync` does not sync `.git/`, so the git state on the Jetson does not represent the code actually running. `.pawai-last-deploy` is the real runtime provenance.

`pawai status` compares:
- **local branch** (the one you checked out)
- **install branch** (the deploy source recorded in `.pawai-last-deploy`)
- **dirty** (whether the working tree had uncommitted changes at deploy time)

On mismatch it prints `⚠ MISMATCH`. To make both sides consistent → switch to the right branch then `pawai jetson deploy --module X`.

---

## 8. Design philosophy

- **Wrap, don't replace**: all the heavy lifting is still done by `scripts/*.sh`; the CLI is only responsible for "correct order + environment + hints"
- **Give an actionable hint on failure**: doctor does not just say "missing"; it gives the corresponding `brew install` / `cp example`
- **idempotent**: running each command an extra time will not break anything; deploy/demo start both detect old state and auto-clean
- **Don't hide errors**: all of rsync/colcon's output is streamed to the local stdout, no swallowing errors
- **Multi-person friendly**: `.pawai-last-deploy` records who last touched what; deploy warns when someone else is demoing

---

## 8. Further reading

- Pitfalls encountered + fixes: [troubleshooting.md](troubleshooting.md)
- Detailed info on the 8 modules: [modules.md](modules.md)
- CLI source code: `tools/pawai_cli/pawai_cli/`
- brain-studio-lane start.sh: `.claude/skills/brain-studio-lane/scripts/start.sh`
- Variable templates: [.env.local.example](../../.env.local.example) / [frontend/.env.local.example](../../pawai-studio/frontend/.env.local.example)
