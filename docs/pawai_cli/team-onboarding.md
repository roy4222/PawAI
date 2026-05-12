# PawAI 新隊友 30 分鐘上手

> Steps 5 + 規矩 在 L2 之後補。今天先到 doctor 全綠。

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
- `JETSON_TAILSCALE_IP` — **留空**（CLI 會自動從 tailscale status 偵測）
- `JETSON_HOSTNAME_HINT` — 預設 `orin` 即可；Roy 的 shared Jetson 目前叫 `orinnano-super`，SSH alias 仍是 `jetson`

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

## 5. 第一個任務 — Coming in L2

L2 加完 lock 之後本節會補：自己 branch → deploy → demo start → 規矩。
