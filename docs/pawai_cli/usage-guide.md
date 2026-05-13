# PawAI CLI 日常使用手冊

> 給已經跑過 [`team-onboarding.md`](team-onboarding.md) 的隊友。
> 這份教你「每天怎麼用」，不是「怎麼裝」、也不是「壞掉怎麼修」。
>
> - **怎麼裝** → [`team-onboarding.md`](team-onboarding.md)
> - **指令完整參考表** → [`README.md`](README.md)
> - **紅燈 / 卡住排查** → [`troubleshooting.md`](troubleshooting.md)
> - **每日 walkthrough、決策樹、錯誤訊息對照** → **這裡**

最後更新：2026-05-13（Phase 1 完成後）

---

## §0. 快速場景索引

| 你想做什麼 | 跳到 |
|---|---|
| 開始今天的開發 demo | [§3 `pawai demo start`](#3-pawai-demo-start--啟動-demo) |
| 改完代碼推到 Jetson | [§2 `pawai jetson deploy`](#2-pawai-jetson-deploy--改完代碼推上去) |
| 停 demo / 換人接手 | [§4 `pawai demo stop`](#4-pawai-demo-stop--收工或交班) |
| 有人在跑 demo 我能 deploy 嗎 | [§2.4 多人協作決策樹](#24-多人協作決策樹--別人在跑-demo-我要-deploy) |
| 自己留下的 stale 鎖怎麼清 | [§4.2 自己的 stale 鎖](#42-自己的-stale-鎖phase-1-新行為) |
| CLI 印了奇怪訊息 | [§7 錯誤訊息對照](#7-錯誤訊息--下一步-對照) |
| 開工前環境健檢 | [§5 `pawai doctor`](#5-pawai-doctor--環境健檢) |
| 看 Jetson 現在誰在用 | [§6 `pawai status`](#6-pawai-status--看-jetson-現狀) |
| 列出 CLI 其他功能 | [§8 其他指令](#8-其他指令) |
| 5 人團隊規矩 | [§9 規矩速記](#9-規矩速記team-onboarding-的-recap--phase-1-補充) |

---

## §1. CLI 一張圖

```
                    ┌────────────────┐
   開工前  ───────►│  pawai doctor  │  Mac/WSL 本機 + Jetson 路徑通不通
                    └────────────────┘
                            │
                            ▼
                    ┌────────────────┐
   看現狀  ───────►│  pawai status  │  誰在用 demo / Last deploy / lock owner
                    └────────────────┘
                            │
        ┌───────────────────┼──────────────────────┐
        ▼                   ▼                       ▼
┌──────────────┐   ┌────────────────┐    ┌──────────────────┐
│ pawai jetson │   │ pawai demo     │    │ pawai health     │
│ deploy       │   │ start          │    │ brain            │
│ (sync+build) │   │ (lock + tmux)  │    │ (lane healthcheck│
└──────────────┘   └────────────────┘    └──────────────────┘
                            │
                            ▼
                    ┌────────────────┐
                    │  跑 demo / dev │
                    └────────────────┘
                            │
        ┌───────────────────┼──────────────────────┐
        ▼                   ▼                       ▼
┌──────────────┐   ┌────────────────┐    ┌──────────────────┐
│ pawai logs   │   │ pawai demo     │    │ pawai contract   │
│ <module>     │   │ stop           │    │ check            │
│ (tmux pane)  │   │ (release lock) │    │ (schema 驗證)    │
└──────────────┘   └────────────────┘    └──────────────────┘
```

10 個核心日常指令：`doctor` / `status` / `dev info` / `jetson deploy` / `demo start` / `demo stop` / `health brain` / `logs` / `docs` / `contract check`。本手冊按使用頻率講；指令簽名以 `pawai <cmd> --help` 為準。

---

## §2. `pawai jetson deploy` — 改完代碼推上去

### 2.1 典型場景：改完 brain → 推 → restart demo

```bash
# 1. 改完 Python，本機跑相關測試
python3 -m pytest pawai_brain/test -q

# 2. 推到 Jetson（含 rsync + colcon build brain 套件）
pawai jetson deploy --module brain

# 3. 確認推上去了
pawai status --short

# 4. 如果 demo 在跑，需要 restart 才生效（CLI 會提示）
pawai demo stop
pawai demo start
```

### 2.2 完整 walkthrough

```text
$ pawai jetson deploy --module brain
Sync: rsync whole repo
… rsync warnings about non-empty dirs (ros-mcp-server/…) — 可忽略
Build: colcon build --packages-select pawai_brain interaction_executive
Starting >>> pawai_brain
Finished <<< pawai_brain [2.8s]
Starting >>> interaction_executive
Finished <<< interaction_executive [2.8s]
Summary: 2 packages finished [6.5s]
Deploy complete.
```

每行解讀：
- `Sync: rsync whole repo` — 走完整 rsync（不是 `~/sync once`）
- `rsync warnings` — 已知 noise，不是 fail（[#troubleshooting D2](troubleshooting.md#d2-rsync-非空目錄-warning)）
- `Build: colcon build` — 在 Jetson 上跑 colcon
- `Deploy complete.` — `.pawai-last-deploy` 已更新

### 2.3 flags 速查

| flag | 用途 | 何時用 |
|---|---|---|
| `--module <name>` | 指定模組（brain / face / nav / ...）| 平常 |
| `--all` | 跑所有模組的 colcon build | 整個環境重建 |
| `--no-build` | 只 rsync、不 build | 改 launch / yaml / py 不需編譯時加速 |
| `--no-sync` | 只 build、不 rsync | 剛 rsync 過、再 build 一次 |
| `-y` | 跳一般確認（demo 在跑時還是會 prompt）| 自己的環境 + 已知後果 |
| `--force` | 接管別人 demo（強烈建議先溝通）| 緊急 |

### 2.4 多人協作決策樹 — 「別人在跑 demo 我要 deploy」

```
        pawai jetson deploy --module brain
                    │
                    ▼
    讀 .pawai-demo-lock，誰在跑？
                    │
    ┌───────────────┼───────────────────────────────┐
    ▼               ▼                                ▼
  沒人        是我自己                          是別人
   │              │                                   │
   │              ▼                                   ▼
   │     直接 sync+build              ⚠ alice@xxx is running a demo
   │     (deploy 完可能要              Deploying now may overwrite their install.
   │      restart demo 才生效)         Continue? [force/cancel]
   │              │                                   │
   │              ▼                                   ▼
   │     完成、提示 "restart demo"           ┌────────┴──────┐
   │                                          ▼               ▼
   │                                       force            cancel
   ▼                                       │                  │
直接 sync+build → Deploy complete       走溝通流程       退出 (exit 0)
                                       (alice 同意後)
                                       再帶 --force
```

關鍵字記：
- **`-y` 不能搶別人 lock** —— 訊息：`-y does not override another user's demo. Use --force.`
- **只有 `--force` 能在別人 running 時繞過 prompt**——而且必須先口頭溝通

### 2.5 Phase 1 新行為：rsync 自動排除密鑰

下列檔名 **不會** 被推上 Jetson（避免 `.env.local` 裡的 `OPENROUTER_KEY` 等 secret 跨帳號漏出）：

```
.env
.env.*
.env.local
.ssh/
```

每個人本機 `.env.local` 各自保留，**Jetson 端的 `.env` 由 Jetson owner 管理**，跟你的 .env.local 不衝突。

### 2.6 deploy 完該檢查什麼

```bash
pawai status --short
```

看 4 個區塊：

1. **`Last deploy`** —— 應該是你剛剛的 ts + user
2. **`Branch state`** —— `local` 跟 `install` 應該相同（branch 一致）
3. **`Demo lock`** —— 確認沒誤搶到別人的鎖
4. **`Heads-up`** —— 如果 demo 在跑，會提醒「deploy 可能要 restart」

---

## §3. `pawai demo start` — 啟動 demo

### 3.1 典型場景：上班第一個 demo

```bash
pawai doctor --cache 30     # 環境健檢（30s cache 給隊友共用）
pawai status --short        # 確認沒人正在跑
pawai demo start            # 啟動完整 demo + Studio overlay
```

成功的訊號：
- `✓ Demo running (lane: brain, lock owner: you@your-host)`
- `tmux ls` 看得到 `demo: 13 windows` 在 Jetson 上
- `curl http://$JETSON_TAILSCALE_IP:8080/health` 回 `{"status":"ok"}`
- `http://localhost:3000/studio` 開得起來

### 3.2 三個 mode 怎麼選

| 指令 | 跑什麼 | 用途 |
|---|---|---|
| `pawai demo start` | **demo** mode：13 windows + Studio overlay | 預設、平常 demo |
| `pawai demo start --no-studio` | **full** mode：13 windows、不啟 Studio frontend | 純 ROS2 debug、不需前端 |
| `pawai demo start --brain-only` | **minimal** mode：只 brain + interaction_executive | brain 邏輯隔離測試 |
| `pawai demo start --nav capability` | **nav_capability** lane：nav stack + AMCL + reactive_stop | 場測手動 `/nav/goto_relative` |

`--nav capability` 限制：
- 不能跟 `--brain-only` 合用（CLI 會 reject）
- 只支援 `capability` 這個 mode（其他 nav mode 走 lane skill 腳本）
- 第一次到新場地要先建圖 + 校 LiDAR 才跑

### 3.3 Lock 互動決策樹（這是 `demo start` 跟 `demo stop` 行為差異最大的地方）

```
        pawai demo start
                │
                ▼
    讀 .pawai-demo-lock
                │
    ┌───────────┼───────────────────────────────────┐
    ▼           ▼                                    ▼
  沒人      是我自己                            是別人
   │            │                                     │
   │            ▼                                     ▼
   │  "Existing lock is yours              "Another user is in demo: alice@xxx
   │   ({state}). Restarting demo."         branch=X state=Y"
   │            │                                     │
   │            ▼                                ┌────┴────┐
   │   清自己的 lane (cleanup.sh)              ▼          ▼
   │   release lock                       --force      無 --force
   │            │                            │             │
   │            ▼                            ▼             ▼
   │     重新 acquire lock              清別人的 lane    "`-y` does not override
   │            │                       release           another user's lock.
   │            │                       acquire           Use --force to take over."
   │            │                            │             → exit 2
   ▼            ▼                            ▼
acquire lock (starting)  ───────►  跑 start.sh  ───────►  transition lock → running
                                                          ✓ Demo running
```

**關鍵記憶點**：
- **自己的 existing lock** → CLI 把它當「restart」，自動清理、再起，不需任何 flag
- **別人的 lock** → 必須 `--force`，先溝通
- **flock 衝突**（連 3 次寫不進）→ `Failed to acquire lock after 3 retries`，**不要 retry，先 investigate**（可能 SSH 抖動或另一個 process 卡住）

### 3.4 啟動成功該看到什麼

```text
═══ 偵測舊 lane 狀態 ═══
    ✅ 沒有舊 lane 殘留
═══ 跑 preflight ═══
[P0] SSH to jetson ... ✅
[P0] /home/jetson/elder_and_dog/.env 存在 ... ✅
[P0] Jetson port 8080 空閒 ... ✅
[P1] LLM tunnel localhost:8000/health ... ✅
[P1] ASR tunnel localhost:8001 ... ✅
[P1] CD002-AUDIO USB 喇叭 ... ✅
[P1] 沒有 nav_* tmux session ... ✅
═══ preflight 結果 ═══
✅ Preflight pass — 可啟動 mode=full
═══ 啟動 brain stack (mode=full) on jetson ═══
═══ 啟動 Studio overlay ═══
    ✅ Frontend: http://localhost:3000/studio
═══ 啟動完成 ═══
✓ Demo running (lane: brain, lock owner: lubaiyu@Roy422deMacBook-Pro.local)
```

如果 preflight 卡在某條 → 該條前面有具體提示，照著修就行。

### 3.5 Phase 1 新行為：環境變數真的會傳到 Jetson

CLI 會把這幾個 env 從你本機 `.env.local` 或 shell export 傳到 Jetson tmux：

- `JETSON_TAILSCALE_IP`（必填，CLI 會自動偵測填上）
- `TTS_PROVIDER`（預設 `openrouter_gemini`，可改 `edge_tts` / `piper`）
- `ASR_PROVIDER_ORDER`（離線 fallback 鏈、JSON 陣列字串）
- `PAWAI_LLM_MODEL` / `PAWAI_LLM_FALLBACK_MODEL`

5/12 night 之前這幾個會被 `start.sh` 預設值蓋掉、現在用 `printf %q` 安全傳遞，**含單引號 / `$` / JSON 都不會壞**。如果你之前養成「export 後再跑 pawai」的習慣，現在直接寫進 `.env.local` 即可。

---

## §4. `pawai demo stop` — 收工或交班

### 4.1 典型場景：自己收工

```bash
pawai demo stop
```

成功訊號（4 個清理步驟全跑完）：

```text
═══ brain-studio-lane cleanup (handoff=none) ═══
[1] 殺 frontend (next dev) ...  ✅ frontend killed (pid=12345)
[2] 殺 Jetson tmux sessions ... ✅ tmux cleared (pawai_brain / studio_gw / demo / llm-e2e)
[3] pkill brain-only processes ... ✅ brain processes killed
[4] 清 go2_driver + 相關 C++ 子 process ... ✅
═══ cleanup 完成 (殘留 brain process: 0) ═══
```

### 4.2 自己的 stale 鎖（Phase 1 新行為）

如果你昨晚的 demo 沒清乾淨、lock 還在 Jetson 上、且狀態是 **`running` 但時間 > 4 小時**（或 `starting` > 10 分鐘）：

```bash
pawai demo stop          # ← 不需要 --force
```

CLI 會印：

```text
Reclaiming your own stale running lock (started 2026-05-12T15:00:00+00:00).
… cleanup steps …
```

然後用 owner-aware `release_if_owned()` 安全解鎖。

**這是 Phase 1 item 6 新行為**——之前你必須加 `--force`，現在不用了。**請不要養成對自己的鎖加 `--force` 的習慣**，會降低錯誤偵測能力。

### 4.3 別人的鎖 — 必須先溝通

```bash
pawai demo stop          # 預設拒絕
# → "Lock is owned by alice@alice-mac. Use --force to stop their demo."
# → exit 2
```

正確流程：

1. 看 `pawai status` 找到 lock owner (`alice@alice-mac`)
2. Slack / 走過去問 alice 還在不在用
3. 確認 OK 才：
   ```bash
   pawai demo stop --force
   ```

**Phase 2 規劃中**會要求 `--force --reason "alice agreed via slack"`，現在還沒；先養成口頭溝通的習慣。

### 4.4 跟 cleanup.sh 的關係

`pawai demo stop` 會根據 lock 的 `lane` 欄位 dispatch：

- `lane=brain` → `.claude/skills/brain-studio-lane/scripts/cleanup.sh`
- `lane=nav_capability` → `.claude/skills/nav-avoidance-lane/scripts/cleanup.sh`

如果你**直接跑 `cleanup.sh`**，**lock 不會被釋放**——只有 `pawai demo stop` 會碰 `.pawai-demo-lock`。建議統一走 CLI。

### 4.5 stop 完該怎麼確認

```bash
pawai status --short
```

看：

```text
Demo lock:
  (none)
```

如果還看到 lock owner，就是 `release_if_owned()` 失敗（race 或 flock 衝突），CLI 會印 `⚠ Lock release skipped — another process holds the flock or lock changed.`，這時候 `pawai status` 再跑一次通常就清了。

---

## §5. `pawai doctor` — 環境健檢

### 5.1 開工前先跑

```bash
pawai doctor --cache 30        # 30 秒內隊友共用結果，省 SSH 探測
pawai doctor                   # 立刻重跑（不走 cache）
pawai doctor --expect-demo     # 預期 demo 應該在跑（Gateway 8080 down 算 FAIL）
pawai doctor --fix             # 互動式修：目前只能補 JETSON_TAILSCALE_IP
pawai doctor --deep            # 多打一次 OpenRouter API（耗額度）
```

### 5.2 Phase 1 新行為

**第一行 `== Platform ==`** 是 Phase 1 新加的：

```text
== Platform ==
✓ Platform: macos           # 或 linux / wsl2
✗ Platform: Windows native unsupported  ← Windows native / WSL1 / /mnt/c 都會 FAIL
```

紅燈時會印 `wsl --install -d Ubuntu` 之類的具體下一步。

**Tailscale 嚴格度提升**：peer 找到、但 `online=False`（例如 Jetson 16 小時前最後上線、Tailscale daemon 還在 cache 它）——之前算 `✓`，**現在算 `✗`**，避免「以為通其實沒通」。

**Gateway 嚴格度跟 lock 連動**：

| Lock 狀態 | Gateway 8080 | doctor 嚴重度 |
|---|---|---|
| 無 lock / `starting` | down | `ℹ SKIP (no demo running)` |
| `running` | down | `✗ FAIL` ← Phase 1 新 |
| 任何 | up | `✓ OK` |

### 5.3 紅燈怎麼讀

每個 `✗` 後面緊跟著一行或多行 `→` 開頭的 fix instruction。**照著做就行**，doctor 不會給沒辦法執行的建議。

例：

```text
✗ no Tailscale peer hostname matches 'orin'
  → ask Roy for the share link and accept it in your Tailscale account
  → or set JETSON_HOSTNAME_HINT in .env.local if your share node has a different hostname
```

完整紅燈對照在 [`troubleshooting.md` §B](troubleshooting.md#b-doctor-紅燈)。

### 5.4 `--fix` 能修什麼

目前只能修一項：**`JETSON_TAILSCALE_IP` 跟 Tailscale 偵測 IP 不一致時自動更新 `.env.local`**。其他紅燈需要你手動處理（裝套件、改 SSH config 等）。

---

## §6. `pawai status` — 看 Jetson 現狀

### 6.1 預設 vs `--short`

| 模式 | 多花時間做什麼 | 何時用 |
|---|---|---|
| `pawai status` | 多打一次 `ros2 node list`（SSH 約 +2s）| 想看 ROS 節點實際在跑什麼 |
| `pawai status --short` | **不**打 `ros2 node list`（避免 daemon cache lie）| 90% 場合：看 lock / tmux / git / Last deploy |

**Phase 1 新行為**：`ros2 node list` 會被 daemon cache 騙——demo stop 後 30 秒內還會看到 phantom nodes。`--short` 避開這個。

### 6.2 看 Lock 區塊

```text
Demo lock:
  owner: alice@alice-mac
  branch: feat/face-yunet
  lane: brain
  tmux: demo
  state: running [STALE running]      ← 標籤
  started: 2026-05-12T15:00:00+00:00
```

- **owner** —— 誰在用（user@host）
- **lane** —— `brain` 或 `nav_capability`
- **state** —— `starting`（剛起、< 10 min 不算 stale）/ `running`（demo 跑著、> 4 hr 才算 stale）/ `stopping`
- **`[STALE …]`** —— 是「超過閾值」的警告。**只是警告，不會自動清**。處理規則見 [§4.2](#42-自己的-stale-鎖phase-1-新行為)、[§4.3](#43-別人的鎖--必須先溝通)

### 6.3 看 Branch state

```text
Branch state:
  local:   main
  install: feat/brain-langgraph
  ⚠ MISMATCH — running install is from feat/brain-langgraph, you have main checked out
```

代表 Jetson 上 build 出來的 `install/` 是別的 branch。你現在 `main` 改完直接 `pawai demo start`，**跑的還是別人的 brain**。要 `pawai jetson deploy --module brain` 才會把你的 branch 推上去。

### 6.4 Heads-up 區塊

不總是會出現。出現時通常是：

- `demo session is running; deploy may require restart.` —— 改了 code 要 deploy 才生效，且要 demo restart
- `last deploy was by alice; coordinate before overwriting.` —— 上次 deploy 不是你

---

## §7. 錯誤訊息 → 下一步 對照

CLI 的 user-actionable failure 字串對照。**不包含**正常 progress message（那些不是錯誤）。

| 訊息 | 來自指令 | 下一步 |
|---|---|---|
| `✗ Platform: Windows native unsupported` (exit 10) | 任何 | 改用 WSL2 Ubuntu；repo 不要放 `/mnt/c`，clone 到 `~/elder_and_dog` |
| `✗ Tailscale peer '...' is offline ip=...` | `doctor` | 在 Jetson 跑 `sudo tailscale up`；或檢查 Jetson Wi-Fi / internet route |
| `✗ no Tailscale peer hostname matches 'orin'` | `doctor` | 接受 Roy 的 Tailscale share link；或在 `.env.local` 設 `JETSON_HOSTNAME_HINT=<你看到的 hostname>` |
| `✗ JETSON_HOST=jetson unreachable` | `doctor` | `~/.ssh/config` 加 `Host jetson` 區塊；或 `ssh-copy-id jetson` |
| `✗ JETSON_TAILSCALE_IP is unset` (exit 2) | `start.sh` 裸跑 | 不要裸跑 `bash start.sh`；走 `pawai demo start`，CLI 會自動偵測注入 |
| `⚠ alice@xxx is running a demo on branch=X` + `Continue? [force/cancel]` | `jetson deploy` | 跟 alice 溝通；同意後輸入 `force` |
| `` `-y` does not override another user's demo. Use --force. `` (exit 2) | `jetson deploy -y` | 拿掉 `-y`、加 `--force`、先溝通 |
| `Existing lock is yours ({state}). Restarting demo.` | `demo start` | 正常訊息，CLI 會自動清理+重啟，無需動作 |
| `Another user is in demo: alice@xxx branch=X state=Y` + `Take over? [force/cancel]` | `demo start` | 跟 alice 溝通；同意後輸入 `force` |
| `` `-y` does not override another user's lock. Use --force to take over. `` (exit 2) | `demo start -y` | 拿掉 `-y`、加 `--force`、先溝通 |
| `Failed to acquire lock after 3 retries — flock held by another process or remote SSH issue. Investigate before retrying.` (exit 2) | `demo start` | **不要重跑**。SSH 上 Jetson 看 `/tmp/pawai-demo-lock.flock` 持有者；或檢查 SSH 抖動 |
| `Lock is owned by alice@alice-mac. Use --force to stop their demo.` (exit 2) | `demo stop` | 跟 alice 溝通；同意後 `pawai demo stop --force` |
| `No demo lock present.` | `demo stop` | 已沒鎖；cleanup 仍會跑一次清殘留 process |
| `⚠ Lock release skipped — another process holds the flock or lock changed.` | `demo stop` | 通常 race 或 SSH 抖動，跑一次 `pawai status` 確認；多半已乾淨 |
| `Error: --module is required unless --all is set` (exit 2) | `jetson deploy` | 加 `--module brain`（或其他），或加 `--all` |
| `module X has no colcon package; use --no-build` | `jetson deploy --module studio` | `studio` 等非 ROS 模組：加 `--no-build` |
| `Error: --nav capability cannot be combined with --brain-only` | `demo start` | 二選一 |
| `Error: --nav detour is intentionally unsupported` | `demo start --nav detour` | `--nav detour` 已知不穩，不要用；只支援 `--nav capability` |
| `rsync: cannot delete non-empty directory: ros-mcp-server/...` | `jetson deploy` | 已知 warning，**可忽略**；deploy 仍會成功 |

完整故障排查（含 Studio 紅燈、Go2 Ethernet 等）在 [`troubleshooting.md`](troubleshooting.md)。

---

## §8. 其他指令

### 8.1 `pawai health brain`（Phase 1 新）

```bash
pawai demo start              # 先啟動 demo
sleep 30                      # 等 stack 起來
pawai health brain            # 跑 8 步 healthcheck
```

會檢查：conv_graph 是否 ready、OpenRouter on/off、persona 6 檔載入、`/brain/chat_candidate` publisher、`/tts` publisher、tts_node alive、Studio gateway `/health`、Frontend port。

**Phase 1 修正**：之前 `healthcheck.sh` 寫死 `JETSON_HOST=jetson-nano`，team 用不同 SSH alias 會 fail。現在 CLI 注入 `$JETSON_HOST` + `$JETSON_TAILSCALE_IP` 給腳本。

### 8.2 `pawai logs <module> --lines 200`

抓 Jetson 上對應模組的 tmux pane 最後 N 行。例：

```bash
pawai logs brain                    # 200 行（預設）
pawai logs face --lines 500         # 500 行
pawai logs all                      # 一次抓 8 個 demo windows
```

### 8.3 `pawai docs <target>`

跳到 0511 架構文件：

```bash
pawai docs brain         # → docs/pawai-brain/architecture/0511/brain/brain.md
pawai docs --open speech # 用 $EDITOR 開
```

完整 target 清單跑 `pawai docs` 不帶參數會列出。

### 8.4 `pawai contract check`

跑 topic schema 驗證：

```bash
pawai contract check             # 本機跑（要 scripts/ci/check_topic_contracts.py）
pawai contract check --jetson    # 在 Jetson 上跑
```

修改 ROS topic schema 後一定要跑，CI 也會跑。

### 8.5 `pawai dev info <module>`

看模組 metadata（packages、docs、tests、log target、Go2 access、注意事項）。改完 brain 不確定該跑哪些 test 時很好用：

```bash
pawai dev info brain
pawai dev info brain --open      # 順便用 $EDITOR 打開主 doc
```

---

## §9. 規矩速記（team-onboarding 的 recap + Phase 1 補充）

| 規矩 | 為什麼 |
|---|---|
| **一次只能一人 demo** | Jetson 是共用、Go2 是唯一硬體；lock 強制這件事 |
| **接手前先溝通** | 不要直接 `--force` 搶；Phase 2 會強制 `--reason` |
| **`-y` ≠ `--force`** | `-y` 跳自己的確認、不能搶別人 lock；`--force` 才能搶 |
| **不在 `/mnt/c/` 下 clone**（Phase 1 新增） | WSL2 跨 filesystem I/O 慢 10x、rsync 語意會壞；clone 到 `~/elder_and_dog` |
| **自己的 stale 鎖直接 `pawai demo stop`**（Phase 1 新增） | 不需 `--force`；保留 `--force` 給「真的要搶別人」的場合 |
| **改完 Python 要 deploy 才生效** | `rsync` 不會自動 `colcon build`；`pawai jetson deploy` 才會 |
| **demo 在跑時 deploy 後要 restart** | `colcon build` 寫進 `install/`，跑著的 process 還在用舊的 |

---

## §10. 跟其他文件的關係（避免混淆）

| 文件 | 它教什麼 | 它**不**教 |
|---|---|---|
| [`team-onboarding.md`](team-onboarding.md) | 從零裝起來、第一次跑 `pawai doctor` 全綠的 30 分鐘流程 | 日常使用、錯誤訊息 |
| [`README.md`](README.md) | 指令完整參考表、所有 flag、環境變數表、Lock 機制設計 | 場景 walkthrough、決策樹 |
| [`troubleshooting.md`](troubleshooting.md) | A-J 章紅燈 / 卡住的故障排查 | 「正常路徑」的怎麼用 |
| [`modules.md`](modules.md) | 8 個 module 對應 package / test / log 索引 | CLI 操作 |
| **`usage-guide.md`（這份）** | 每日 walkthrough、三大高頻指令的決策樹、Phase 1 新行為對使用者的影響、錯誤訊息對照 | 完整 flag 列表（看 README）、首次安裝（看 onboarding）、紅燈解（看 troubleshooting） |

有疑問先按場景找對的文件、再回來這份找具體流程。
