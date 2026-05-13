# PawAI 新隊友 30 分鐘上手

> 支援 macOS / Linux native / WSL2 Ubuntu。不要在 Windows PowerShell、CMD、
> Git Bash、WSL1，或 WSL `/mnt/c/...` repo 直接跑 `pawai`；CLI 會擋下這些
> 環境，避免 rsync/flock/tmux 行為不一致。

## 0. 你需要什麼

- macOS / Linux / WSL2
- GitHub repo 存取權
- Roy 在群組發的 Tailscale share link

## 1. 裝工具（5 min）

```bash
# macOS
brew install tmux node tailscale

# Linux / WSL
sudo apt install tmux nodejs npm
# Tailscale: https://tailscale.com/download/linux
```

## 2. 加入 Tailscale（5 min）

1. 打開 Roy 發的 share link
2. 用你自己**免費的** Tailscale 帳號登入（不需付費，不佔 Roy 配額）
3. 接受 share
4. 終端跑：
   ```bash
   tailscale status
   ```
   應該看到 `roy422` 的 jetson node（hostname 含 "jetson"）
5. 測延遲：
   ```bash
   tailscale ping jetson
   ```
   `< 50ms` 是好狀態

## 3. clone repo + 裝 CLI（10 min）

```bash
git clone <repo-url> elder_and_dog
cd elder_and_dog

# 建 venv（避免污染系統 Python）
python3 -m venv ~/.venv
source ~/.venv/bin/activate

# 裝 CLI
uv pip install -e tools/pawai_cli
pawai --version   # 應印 0.x.y

# 環境變數
cp .env.local.example .env.local
$EDITOR .env.local
```

`.env.local` 需要填的：
- `OPENROUTER_KEY` — 跟 Roy 拿
- `JETSON_TAILSCALE_IP` — 可留空讓 CLI 從 `tailscale status` 偵測；如果 doctor
  找不到 peer 但你知道 IP，就填 `100.83.109.89`
- `JETSON_HOSTNAME_HINT` — 預設 `orin`；如果 share hostname 不匹配，就填
  `orinnano-super`

## 4. doctor 應該全綠（5 min）

```bash
pawai doctor
```

預期看到：
- `== Tailscale ==` 區塊：`✓ Tailscale peer 'orinnano-super' online=true ip=100.83.109.89`
- `== Network topology ==` 區塊：
  - `✓ local → Jetson Tailscale: OK 100.83.109.89`
  - `✓ Jetson internet route: wlan0`（**不能是 eth0**，否則 Go2 線被搶用）
  - `✓ Jetson Go2 link: eth0 192.168.123.X/24`
  - `✓ Jetson → Go2 ping: OK 192.168.123.161`
  - `ℹ Gateway 8080: SKIP (no demo running)` ← 這是正常的，不是紅燈

紅燈時對照 `docs/pawai_cli/troubleshooting.md` B / G / H 章。

## 5. 第一個任務（5 min）

開自己的 branch：

```bash
git checkout -b feat/<yourname>-explore
```

部署你負責的模組：

```bash
pawai docs <module>             # 先看架構文件
pawai jetson deploy --module <module>
```

啟動 demo：

```bash
pawai demo start
```

如果看到「Another user is in demo」訊息 — 不要 `--force`，跟對方溝通。

完成後一定要停：

```bash
pawai demo stop
```

`pawai status` 隨時查看誰在 demo、用哪個 branch、跑了多久。
趕時間只要看 lock/branch/tmux 時用：

```bash
pawai status --short
```

`--short` 不會遠端呼叫 `ros2 node list`，所以不會被 ROS daemon cache 誤導。

### 導航避障場測（只有負責 nav 的人跑）

`pawai demo start --nav capability` 會啟完整 nav capability stack，但它只代表
「Nav2 / RPLIDAR / D435 / reactive_stop / nav_capability 已起來」。它**不**代表
語音可以叫 Go2 走；Brain → NAV executor 還沒接。

到學校或新場地時，不要直接用家裡 map：

```text
/home/jetson/maps/home_living_room_v8.yaml
```

先照
[`docs/pawai-brain/architecture/0511/nav/nav-field-runbook.md`](../pawai-brain/architecture/0511/nav/nav-field-runbook.md)
建圖或確認 school map，再跑：

```bash
pawai demo start --nav capability
```

第一個移動測試只做 0.3m：

```bash
ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative \
  "{distance: 0.3, yaw_offset: 0.0, max_speed: 0.0}"
```

如果 goal accepted 但 Go2 不動，不要硬加距離。照 nav field runbook 的 F7 Debug
查 `/cmd_vel_nav`、mux priority、Nav2 lifecycle。

## 規矩（明天現場守住）

- **一次只能一個人 `pawai demo start`** — Jetson + Go2 是共用資源
- **`-y` ≠ `--force`**：`-y` 只跳自己的確認，**不能**蓋別人的 lock；要接手別人 demo 必須 `--force`
- **`pawai demo stop` 預設只清自己的 lock**；自己的 stale lock 不需要 `--force`
- **停別人的 demo 用 `--force` 並先告訴對方**；Phase 1 還沒有 `--reason` audit prompt，不要把 `--force` 當快速鍵
- **deploy 中看到「someone is in demo」prompt → 先溝通**，不要直接 `--force`
- **stale lock（demo 跑超過 4hr）不會自動清** — `pawai status` 會標 STALE，要清也要確認對方真的不在用
- **secrets 只留本機 `.env.local`** — `pawai jetson deploy` 會排除 `.env` / `.env.*` / `.env.local` / `.ssh/`
- **brain stack 起來後可跑 `pawai health brain`** — 它比手打 healthcheck 少踩 SSH alias / IP env 的坑
- **nav capability 是手動 action 場測，不是語音導航 demo** — 不要對外說 Brain 已能導航
