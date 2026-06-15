# PawAI CLI — MacBook 現場操作 Runbook（6/18 demo 操作機）

> 日期：2026-06-15　狀態：**靜態分析（code 層唯讀）強烈支持可用 — 但未在任何 Mac 實機跑過；實機綠燈待 Roy 在 Mac 跑一輪**（靜態分析 ≠ 已驗證）
> 目的：6/18 用 MacBook 當現場操作機（起停 demo、看 log、註冊人臉）。
> 一句話：**macOS 是已明確支援的一級平台，CLI 把 Mac 當 SSH 跳板、所有 ROS2 在 Jetson 跑。WSL 測過 ≠ Mac 跑過，下面標 ⚠️ 的項目必須你在實體 Mac 上跑過才算數。**

---

## 0. 靜態分析結論（code 層唯讀調查 6/15，**未實機 = 非「已驗證」**）

| 項目 | 結論 | 證據 |
|---|---|---|
| macOS 是否被 CLI 放行 | ✅ **明確放行**（`supported=True`，**不會 exit 10**），且有 regression 測試保護 | `tools/pawai_cli/pawai_cli/platform.py:37-39`（Darwin → supported）；`tests/test_platform.py` patch Darwin 斷言 |
| `/mnt/c` 路徑檢查會不會誤擋 Mac | ✅ 不會（只對 wsl2 生效） | `platform.py:79-92`（`if info.kind != "wsl2": return None`） |
| demo lock 需不需要 Mac 本機 `flock(1)` | ✅ **不需要**。所有 `flock` + lock 讀寫都在 **Jetson** 上跑（SSH） | `lock.py`：`acquire`/`release_if_owned`/`transition_if_owned` 全走 `shell.run_remote(...)`，`flock` 在 remote 執行；lock 檔 `{jetson_repo}/.pawai-demo-lock` 在 Jetson |
| 8 個必測指令會不會在 Mac 本機跑 ROS2 | ✅ **不會**。7 個純 SSH 跳板；只有 `demo start` 會在 Mac 本機跑 Studio frontend（Node.js） | `status.py`/`network.py`/`main.py` 無本機 `ros2`/`tmux`/`colcon` 呼叫；SSH 抽象 `shell.py:74-93` |
| face enroll 需不需要 Mac 鏡頭 | ✅ **不需要**。在 Jetson headless 跑、訂 Jetson D435 topic | `main.py:2102-2115`（`run_remote` 跑 `face_identity_enroll_cv.py --headless`）；face_db 在 Jetson `/home/jetson/face_db` |
| 需要改 code 嗎 | ✅ **零 code 需要改**（macOS 放行 + 不誤跑 ROS2 都已是設計） | — |
| CLI 主線進入點 | **legacy `pawai`**（不是 `pawai2`；`pawai2` 還沒接 `--with-lidar`） | `pyproject.toml:21`；`v2/app.py` demo_start 無 `--with-lidar` |

> 結論：**設計與靜態分析強烈支持 Mac 可用，但「實機綠燈」這張票還沒拿到**——拿票方式見 §3。

---

## 1. 一次性安裝（MacBook，約 15 分鐘）

```bash
# 1) 系統前置（需先有 Homebrew）
brew install tmux node              # tmux 給 demo 腳本判斷、node 給 Studio frontend
brew install --cask tailscale       # SSH 上 Jetson 的網路
brew install bash                   # （建議）裝 5.x，避開 macOS 內建 bash 3.2 邊角

# 2) Python（CLI 需 >=3.10）
brew install uv
python3 --version                   # 確認 >= 3.10

# 3) clone repo（放 Mac home，不要放 iCloud/外接同步資料夾）
cd ~ && git clone <repo-url> elder_and_dog
cd ~/elder_and_dog

# 4) venv + 裝 CLI（只裝 click + python-dotenv，無 Linux-only wheel）
python3 -m venv ~/.venv && source ~/.venv/bin/activate
uv pip install -e tools/pawai_cli
pawai --version                     # 能印版本 = 平台閘門放行 Mac（關鍵第一個綠燈）

# 5) Tailscale：用 Roy 的 share link 登入 → 接受 share
tailscale status                    # 應看到 hostname 含 jetson/orin 的 node

# 6) SSH config：~/.ssh/config 加 Host 區塊（指向 Jetson Tailscale IP）
#    Host jetson-nano
#        HostName 100.83.109.89
#        User jetson
ssh-copy-id jetson-nano             # 推 Mac 公鑰上 Jetson（一次性）
ssh jetson-nano "echo ok"           # 應印 ok（SSH 通了）

# 7) env 覆寫
cp .env.local.example .env.local 2>/dev/null || true
$EDITOR .env.local
#   JETSON_HOST=jetson-nano
#   JETSON_TAILSCALE_IP=100.83.109.89   （留空 CLI 會從 tailscale status 偵測）
#   OPENROUTER_KEY=...                   （跟 Roy 拿）
```

---

## 2. 每次開工 / demo 操作

```bash
source ~/.venv/bin/activate && cd ~/elder_and_dog

# 環境健檢（期望 Platform: macos / Tailscale online / local→Jetson OK / 0 blocking）
pawai doctor

# 起 demo（brain + 5 感知在 Jetson；Studio frontend 在 Mac 本機 next dev）
pawai demo start --with-lidar       # 帶 raw LiDAR 證據窗（無 nav2/motion，安全）
#   ↳ 首次自動 npm install（~2 分鐘）+ next dev → http://localhost:3000/studio

pawai status                        # Jetson tmux/ROS node/git
pawai health brain                  # 8 項 healthcheck（全綠才算 ready）
pawai logs brain --lines 100        # 抓 Jetson brain pane（logs studio 才讀 Mac 本機檔）
pawai smoke brain --rounds 5        # demo 起著時跑 5 輪語音 E2E

# 人臉（全在 Jetson 跑、不用 Mac 鏡頭）
pawai face enroll --person-name roy
pawai face rebuild

pawai demo stop                     # 清 Mac frontend + Jetson tmux/process
```

---

> **⚠️ Act1 motion 不從 Mac 觸發**：`--with-lidar` 只起 raw LiDAR 證據窗（**無 motion**）。Act1 短距前進 = motion，**一律在 Jetson 端、由 Roy 手持實體 e-stop 跑**（見 `docs/navigation/2026-06-15-act1-demo-forward-estop-runbook.md`）。Mac 只負責起 brain demo / 看 log / face enroll。**別從 Mac 觸發 Act1**（雙 publisher 撞狗風險的 A-1 blocker 就活在這個 demo stack 上）。

## 3. ⚠️ 必須在實體 Mac 上跑過才算數（我無法在 WSL 替代）

按優先序。把這幾條的完整輸出貼回來，就能把實機綠燈拿到。

1. 🔴 **`pawai --version` + `pawai doctor`** — 確認平台閘門放行 Mac、`Platform: macos`、Tailscale/SSH 解析正常。
2. 🔴 **`pawai demo start --with-lidar` 的 lock + frontend 兩行** — lock acquire 是否成功（code 上是 Jetson 端 flock、應該沒事，但要實證）；`next dev` 起得來 + `http://localhost:3000/studio` 出 200（**注意 MEMORY 有 studio lockfile npm10↔11 @emnapi 不相容的坑**，Mac Node 版本第一次跑才知道）。
3. 🟠 **Mac 內建 `/bin/bash` 3.2 vs brew bash** — `shell.stream(["bash",...])` 抓到哪個；若沒裝 brew bash，確認 3.2 真的沒問題（靜態分析顯示腳本只用 bash 3.2 相容語法，但實跑為準）。
4. 🟡 **`pawai demo stop`** — Mac 本機 frontend kill + Jetson cleanup 是否乾淨。

---

## 4. Mac 不支援 / 異常時的 fallback

| 情境 | Fallback |
|---|---|
| Mac `pawai demo start` 卡 lock / 行為異常 | 改「Mac 只 SSH 進 Jetson、在 Jetson 端直接跑」：`ssh jetson-nano` → `cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh`；Studio frontend Mac 另開 `bash pawai-studio/start.sh` |
| Mac 起不了 Studio frontend（Node 問題） | brain demo 本體在 Jetson、不受影響（語音/感知照常），只是少 Studio 網頁；可改 Jetson foxglove 或純語音操作 |
| doctor 找不到 tailscale | `open -a Tailscale` 登入（doctor 對 Darwin 已內建此提示） |
| 任何指令在 Mac 報 `ros2: command not found` | 那是 bug（所有 ROS2 應在 Jetson）→ 回報，不要在 Mac 裝 ROS2 |

---

## 5. 關鍵檔案（除錯用，皆絕對路徑）

- 平台閘門：`tools/pawai_cli/pawai_cli/platform.py`（:37-39 放行 Mac、:79-92 mnt/c 不誤擋、:95-102 assert）
- SSH 抽象：`tools/pawai_cli/pawai_cli/shell.py`（:74-93）
- demo lock（全 remote）：`tools/pawai_cli/pawai_cli/lock.py`
- 主命令：`tools/pawai_cli/pawai_cli/main.py`（doctor Darwin :64-69/:465-466；demo start :1510-1651；face enroll :2102-2115）
- 既有 Mac 安裝文件：`docs/pawai_cli/{README.md,team-onboarding.md,usage-guide.md}`
