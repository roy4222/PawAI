# PawAI CLI 踩坑解法清單

每條都是真實踩過的坑，按「最常見」→「邊角」排序。

---

## A. 安裝 / 環境

### A1. `pawai: command not found`

```
✗ pawai: command not found
```

**原因**：`uv pip install -e` 裝到的 venv `bin/` 不在 PATH，或者用 user install 但 `~/.local/bin` 沒加 PATH。

**解法**（擇一）：

```bash
# 1) 用 venv（推薦）
source ~/.venv/bin/activate
which pawai  # 應該找到

# 2) 確認 user install 路徑
python3 -m pip show -f pawai-cli | grep bin/pawai
# 把對應 bin/ 加進 PATH

# 3) 應急：直接呼叫
python3 -m pawai_cli.main doctor
```

---

### A2. `build_editable hook missing` / `cannot be installed in editable mode`

**原因**：系統 pip/setuptools < 64，不支援 PEP 660 editable install。

**解法**：

```bash
# 推薦：用 venv + uv（自帶新版 pip/setuptools）
python3 -m venv ~/.venv && source ~/.venv/bin/activate
curl -LsSf https://astral.sh/uv/install.sh | sh
uv pip install -e tools/pawai_cli

# 不想裝 uv：升級系統 pip
python3 -m pip install --upgrade pip setuptools
python3 -m pip install -e tools/pawai_cli
```

> 沒先 activate venv 直接跑 `uv pip` 會炸出「No virtual environment found」之類錯誤。
> 如果你刻意要裝到系統 Python，加 `--system`：`uv pip install --system -e tools/pawai_cli`

---

### A3. Jetson 上 setuptools < 70 / colcon build fail with `option --editable not recognized`

**原因**：Jetson 端 setuptools 80+ 拿掉 `--editable`/`--uninstall` flag，但 colcon 的 setup.py shim 還在用。

**解法**（在 Jetson 上）：

```bash
pip install --user "setuptools<70"   # 已知好版本 69.5.1
```

詳見 `CLAUDE.md` 的 Jetson 測試規範段。

---

## B. doctor 紅燈

### B1. `✗ JETSON_HOST=xxx unreachable`

doctor 會自動偵測原因並印 hint。常見三種：

#### B1a. SSH config 沒對應的 Host 區塊

```
✗ JETSON_HOST=jetson unreachable
  → no `Host jetson` block in ~/.ssh/config
    add one pointing at the Jetson Tailscale IP, or set JETSON_HOST in .env.local
```

**解法**：在 `~/.ssh/config` 加：

```sshconfig
Host jetson
    HostName 100.83.109.89   # Tailscale IP
    User jetson
```

或在 `.env.local` 改成你已有的 alias：`JETSON_HOST=orin`。

#### B1b. SSH key 沒推上 Jetson

```
✗ JETSON_HOST=jetson unreachable
  → ssh-copy-id jetson   # if key not yet authorized
```

**解法**：

```bash
ssh-copy-id jetson   # 一次性，會 prompt 密碼
ssh jetson 'echo OK' # 驗證
```

#### B1c. Tailscale 沒登入或斷線

```
✗ JETSON_HOST=jetson unreachable
  → tailscale up   # if Tailscale offline
```

**解法**：

```bash
# Mac
open -a Tailscale  # 從選單列登入

# Linux
sudo tailscale up
```

確認狀態：`tailscale status`，Jetson 那行應該不是 `offline`。

---

### B2. `⚠ Studio frontend node_modules missing`

```
⚠ Studio frontend node_modules missing
  → cd .../pawai-studio/frontend && npm install
```

**解法**：

```bash
cd pawai-studio/frontend && npm install
# 或直接 pawai demo start，會自動 npm install
```

---

### B3. `⚠ Studio frontend .env.local missing`

```
⚠ Studio frontend .env.local missing
  → cp .../.env.local.example .../.env.local
    (`pawai demo start` will auto-generate from JETSON_TAILSCALE_IP)
```

**解法**：跑 `pawai demo start` 會自動建。或手動：

```bash
cp pawai-studio/frontend/.env.local.example pawai-studio/frontend/.env.local
$EDITOR pawai-studio/frontend/.env.local  # 確認 NEXT_PUBLIC_GATEWAY_HOST 是 Jetson IP
```

---

## C. Studio frontend / Demo

### C1. Studio 三個 panel 都 `DISCONNECTED`，no events

![3 panels DISCONNECTED screenshot — face/gesture/object]

**根因**：browser 連不到 Gateway。

**檢查**：

```bash
# 1) Gateway 在 Jetson 上有沒有跑（demo:gateway window）
ssh jetson 'tmux ls; curl -s localhost:8080/health'

# 2) Gateway 從本機可達嗎？
curl -s http://$JETSON_TAILSCALE_IP:8080/health
# 應該回 {"status":"ok","node":true,"ws_clients":...}

# 3) Frontend env 對嗎？
cat pawai-studio/frontend/.env.local
# 應該有 NEXT_PUBLIC_GATEWAY_HOST=<Jetson IP>，不是 localhost
```

**最常見錯**：`.env.local` 漏寫 `NEXT_PUBLIC_GATEWAY_HOST` → browser fallback 到 `window.location.hostname`（Mac 上 = localhost）→ 連 Mac 自己 port 8080（沒東西）→ DISCONNECTED。

修法：照 [B3](#b3) 補上 `.env.local`，或刪掉 `.env.local` 再跑 `pawai demo start`（會自動生成）。

---

### C2. `pnpm dev` 跳 `ERR_PNPM_IGNORED_BUILDS` 然後死

```
[ERR_PNPM_IGNORED_BUILDS] Ignored build scripts: msw@2.14.5, sharp@0.34.5...
[ERROR] Command failed with exit code 1: pnpm install
```

**根因**：pnpm 11 的 `dev` 在啟動前會跑 deps status check，會 spawn `pnpm install`，遇 ignored builds warning 退出非零，rollback 到 `next dev` 之前。

**解法**：

```bash
# 短期：用 pawai demo start（已用 node_modules/.bin/next 繞掉）
pawai demo start

# 或手動
cd pawai-studio/frontend && ./node_modules/.bin/next dev

# 長期：本 repo canonical 是 npm（package-lock.json 已 commit）
# 不要用 pnpm install，會產生 pnpm-lock.yaml 污染
```

---

### C3. Port 3000 被別的 dev server 卡住

```
✓ Frontend at http://localhost:3000/studio
# 但開 browser 看到不是 PawAI Studio
```

**檢查**：

```bash
lsof -iTCP:3000 -sTCP:LISTEN   # 找佔用 process
curl -s http://localhost:3000 | grep -o '<title>[^<]*</title>'
```

**解法**：

```bash
# 確認是無關 process 後 kill 它
kill <PID>

# 或讓 PawAI 用 3001
cd pawai-studio/frontend && ./node_modules/.bin/next dev -p 3001
# 注意：start.sh 預期 3000，要手動跑就要記得 .env.local 跟 browser URL 都改
```

---

### C4. `pawai demo start` 後 status 顯示 `tmux: none`

**根因**：race。`start.sh` return 後立即跑 status，Jetson 上的 `tmux new-session -d` 還沒真正落地。

**解法**：等 10–20 秒再跑：

```bash
pawai demo start
sleep 20
pawai status   # 應該看到 demo: 13 windows
```

---

### C5. demo 起來了但 ROS node 不全 / brain_node 沒 ready

```bash
pawai status        # 看 ROS node 列表
pawai logs brain --lines 200 | grep -E "ERROR|Traceback|ready"
pawai logs all      # 全 pane log
```

常見原因：
- LLM tunnel 沒開（看 `demo:llm` window 有沒有 connection refused）
- USB 麥克風或喇叭沒接上（`demo:asr` / `demo:tts` 會抱怨）
- Go2 沒上電或 IP 不通：`ssh jetson 'ping -c 2 192.168.123.161'`

---

## D. Deploy / Sync

### D1. rsync 一堆 `cannot delete non-empty directory` warning

```
cannot delete non-empty directory: pawai-studio/backend/.venv/lib/...
cannot delete non-empty directory: ros-mcp-server/utils
```

**已修**：CLI 加了 `--exclude=.venv/` `--exclude=node_modules/` 等，正常情況不會再看到。

如果還看到，代表 rsync 想刪某個你 local 沒有但 remote 有的目錄但裡面非空。檢查：

```bash
ssh jetson 'find ~/elder_and_dog -name .venv -o -name node_modules' | head
# 找到後決定要不要 ssh 進去 rm -rf
```

---

### D2. Deploy 完 `pawai status` 顯示 `Last deploy: none`

**Deploy 是同步流程**：rsync → colcon build → 最後寫 `.pawai-last-deploy` → 回傳。
所以 deploy 命令結束時檔案理論上應該已經存在。看到 `none` 通常代表：

1. **看的是 deploy 之前跑的 status**（兩條指令不是同一輪）
2. **`JETSON_REPO` 路徑跟實際 deploy 目標不一致** — status 讀的是 `$JETSON_REPO/.pawai-last-deploy`
3. **遠端寫入失敗**（disk full / 權限）

**Verify 順序**：

```bash
# 1) 直接看遠端檔
ssh jetson 'ls -la ~/elder_and_dog/.pawai-last-deploy 2>&1; cat ~/elder_and_dog/.pawai-last-deploy 2>&1'

# 2) 不存在 → 看 deploy 有沒有真的成功
pawai status --short
pawai jetson deploy --module brain 2>&1 | tail -10   # 看最後一行有沒有「Deploy complete.」

# 3) 存在但 status 讀不到 → 檢查 JETSON_REPO 是否對得上
grep JETSON_REPO .env.local
ssh jetson 'echo $HOME && ls -d ~/elder_and_dog 2>&1'
```

---

### D3. colcon build fail：`option --editable not recognized`

見 [A3](#a3-jetson-上-setuptools--70--colcon-build-fail-with-option---editable-not-recognized)。

---

### D4. Deploy 顯示 demo 還在跑，要 restart

```
Demo session is running. Deploy may require restart. Continue? [y/N]
```

**選 y** 通常 OK（Python source 改完不需要立刻 restart，下一次 launch 才生效）。
**改 ROS msg / launch file** 才需要：

```bash
pawai demo stop
pawai jetson deploy --module brain
pawai demo start
```

---

## E. Mac 搬家踩坑（首次設定）

按順序解：

1. **Tailscale 沒登入** → `open -a Tailscale` 登入
2. **SSH key 沒推** → `ssh-copy-id jetson`（直接打 alias；shell 沒 source `.env.local` 不會有 `$JETSON_HOST`）
3. **缺工具** → `brew install tmux node`
4. **`.env.local` 沒建** → `cp .env.local.example .env.local`，填 `JETSON_TAILSCALE_IP` + `OPENROUTER_KEY`
5. **`SSH config` 的 Host alias 跟 `JETSON_HOST` 不一致** → 兩邊改成一致
6. **frontend `node_modules` 缺** → `pawai demo start` 會自動 install，或手動 `cd pawai-studio/frontend && npm install`
7. **frontend `.env.local` 缺** → `pawai demo start` 會自動寫，或手動從 example 複製

**驗證一條龍**：

```bash
pawai doctor       # 0 blocking, 0 warnings
pawai jetson deploy --module brain  # 應該 sync + build 成功
pawai demo start   # 看到「✅ Gateway reachable」「✅ Frontend: http://localhost:3000/studio」
```

---

## F. 其他

### F1. 我想看 CLI 內部做了什麼

```bash
# doctor 加 --verbose 印 SSH stderr 細節
pawai doctor --verbose

# 直接看 source
cat tools/pawai_cli/pawai_cli/main.py

# Bash side：所有 demo/cleanup 腳本
ls .claude/skills/brain-studio-lane/scripts/
ls scripts/start_*.sh scripts/clean_*.sh
```

### F2. 我想加新 module 到 CLI

編輯 `tools/pawai_cli/pawai_cli/modules.py`，加 `ModuleInfo` 條目，
重裝：`uv pip install -e tools/pawai_cli`。

新 module 自動進 `pawai dev info <new>` 和 `pawai jetson deploy --module <new>`。

### F3. 我有自己的 ~/sync 腳本

`pawai jetson deploy` 會優先用 `~/sync once`（如果存在且 executable），
否則 fallback 到內建 rsync。內建 rsync exclude 已涵蓋 cache 目錄，多數情況不需要自訂腳本。

---

## G. Jetson 換網路

### G1. Jetson 從家裡搬到學校 — 我該擔心什麼？

短答：
- **Tailscale IP `100.83.109.89` 通常不變** — 跨網路一致
- **Jetson 本地 LAN/Wi-Fi IP 會變** — 但 CLI 不依賴它
- **Go2 IP 應該不變** — 還是 `192.168.123.161`，前提是 Jetson↔Go2 Ethernet 線還插著

最容易壞的事情：**Jetson 的 Ethernet 被拔去插學校網路**，導致 Go2 link 不見。

`pawai doctor` 的 Network topology 區塊會在這時翻紅：
- `Jetson internet route: eth0` ← ⚠ Ethernet 變成 uplink
- `Jetson Go2 link: no 192.168.123.x interface` ← ✗ Go2 線沒接

**修法**：學校用 **Wi-Fi 上網**，Ethernet 保留給 Go2。

### G2. Tailscale Reconnecting

開機/換網路後 30s-2min 內，doctor 可能短暫紅燈。等 60s 再跑：

```bash
sleep 60 && pawai doctor
```

### G3. 學校 Wi-Fi 擋 outbound

學校網路偶爾擋 SSH (22) 或 outbound HTTP — 表現是 SenseVoice tunnel / OpenRouter 連不到。
fallback：用 local ASR / local TTS（`ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'`）。

---

## H. Tailscale Sharing

### H1. 我接受 share link 後 `tailscale status` 看不到 Jetson

- 確認你接受 share 時用的是你自己的 Tailscale 帳號（不是 Roy 的）
- 跑 `tailscale up`
- 重新點 share link

### H2. 同一台筆電換 Tailscale 帳號

如果你先前裝 Tailscale 用了不同帳號：

```bash
sudo tailscale logout
sudo tailscale up   # 引導你登入新帳號
```

### H3. Tailscale free tier 上限

Free Personal tier 可以接受別人的 share node 不佔 user 配額。不需付費。
