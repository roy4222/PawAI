# Runtime Fallback Readiness — 5/12 移交前

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **Owner**: Roy
> **目的**：5/12 移交學校前，確認三種啟動模式都能 work，避免到學校才發現「網路不通就整個死」「LLM 斷線就 crash」「Mac 連不上 Jetson 就 demo 失敗」。

---

## 1. 三種啟動模式

| 模式 | 條件 | demo 用途 |
|---|---|---|
| **正常** | Jetson + Cloud LLM tunnel + Studio + 全感知 | 主 demo 路徑 |
| **No-AI** | LLM tunnel 斷 / 學校網路不通 cloud | 應急 fallback：PawAI 還能播 canned 自介、手動觸發 skill、Studio 不 crash |
| **Mac as operator** | Mac 跑 Studio、Jetson 跑 runtime | 學校預設模式（家裡是 Tailscale，學校換區網）|

---

## 2. ✅ Mode 1：正常模式 smoke

**啟動指令**（5/12 早確認家裡 baseline）：
```bash
# Jetson 上
source /opt/ros/humble/setup.zsh
source install/setup.zsh
source config/school_demo.env   # 等 E plan 建好
bash scripts/start_full_demo_tmux.sh
```

**Pass criteria**：
- [ ] tmux 13 windows 全綠
- [ ] `ros2 topic list` 看得到 /event/speech_intent_recognized、/state/perception/face、/event/gesture_detected
- [ ] Studio (Mac browser) 連得上 Jetson `:8080/health` 回 200
- [ ] 對著麥克風說「你好」→ TTS 從 Go2 喇叭出來
- [ ] 自介 prompt 觸發 → LLM 回應 < 3s

---

## 3. ✅ Mode 2：No-AI fallback（最容易死）

**情境**：學校 Wi-Fi 不能打 SSH tunnel 到開發伺服器，LLM endpoint 失效。

**現有支援檢查**：
- `pawai_brain` 是否有 RuleBrain fallback？(memory 顯示有，需驗證)
- LLM endpoint 失敗多久後 fallback 啟動？

**測試指令**（用 env 模擬，不用 iptables — 不需 sudo、不污染 Jetson 網路狀態）：
```bash
# 把 endpoint 指到一定打不通的 port，強制觸發 fallback
LLM_ENDPOINT="http://127.0.0.1:1/v1/chat/completions" \
QWEN_ASR_BASE_URL="http://127.0.0.1:1/v1/audio/transcriptions" \
ASR_URL="http://127.0.0.1:1/v1/audio/transcriptions" \
ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' \
TTS_PROVIDER=piper \
  bash scripts/start_full_demo_tmux.sh

# 對著麥克風說「自我介紹一下」
# 預期：
# - ASR 走 sensevoice_local（cloud 連 :1 立刻 ConnectionRefused → fallback）
# - LLM 走 RuleBrain，講 canned 自介
# - TTS 走 Piper（不依賴雲端）
# - Studio 顯示 ASR/LLM 仍有事件
# - 系統不 crash
```

**還原**：把 tmux session kill 掉重啟，不留 env，不需要 cleanup。

**Pass criteria**：
- [ ] LLM tunnel 斷時不 crash
- [ ] ASR 自動 fallback 到 `sensevoice_local`
- [ ] PawAI 至少能播 canned 自介（短版 10 秒）
- [ ] 手動 Studio button 觸發 skill 仍能 work
- [ ] Studio 顯示明顯 fallback indicator（若無，記下，demo 期靠 Roy 知道就好）

**降級話術**（嵌進 `docs/runbook/demo-fallback-script.md`）：
- 若 demo 當天 No-AI mode：「PawAI 現在用本地大腦回應，可能不像雲端那樣多變化，但七大能力都能展示」

---

## 4. ✅ Mode 3：Mac as operator

**Mac 端啟動指令**（demo 預設）：
```bash
# Mac 上
cd ~/path/to/elder_and_dog
git pull
cd pawai-studio
GATEWAY_HOST=<學校 Jetson IP> GATEWAY_PORT=8080 bash start-live.sh --live
# → 開瀏覽器到 http://localhost:3000/studio
```

**Jetson 端**（學校 Jetson）：
```bash
ssh jetson@<學校 Jetson IP>
cd ~/elder_and_dog
git pull   # 5/12 移交前最後一次 pull
source config/school_demo.env
bash scripts/start_full_demo_tmux.sh
```

**Pass criteria**（5/12 PM 在家用 Mac 模擬學校網段）：
- [ ] Mac ping 得到 Jetson IP
- [ ] Mac browser 打得開 `http://<Jetson_IP>:8080/health` 回 200
- [ ] Mac Studio 顯示「connected」（不是 mock fallback）
- [ ] Mac Studio button 觸發 skill → Go2 真的動
- [ ] Mac 看得到 Foxglove `ws://<Jetson_IP>:8765`

**家裡模擬學校網段方法**：
- 用手機熱點：Mac + Jetson 都連手機熱點，模擬陌生網段
- 或：Mac 切到家裡 Wi-Fi 5G、Jetson 留 Ethernet 直連 Go2 + 透過 USB tether 到 Mac

---

## 5. demo fallback 話術文件

5/12 中午 Brain freeze 後一併寫進 `docs/runbook/demo-fallback-script.md`：

```markdown
# Demo Fallback Script

## 若 LLM tunnel 斷
PawAI 自動走本地 RuleBrain。
講法：「PawAI 現在用本地大腦回應」

## 若 ASR cloud 斷
自動 fallback 到 sensevoice_local。
講法：（不用講，使用者無感）

## 若 Mac 連不上 Jetson
重連步驟：
1. 確認 GATEWAY_HOST 環變
2. ping <Jetson_IP>
3. curl http://<Jetson_IP>:8080/health
4. 重啟 start-live.sh

## 若 Go2 連不上
1. ping 192.168.123.161
2. 確認 Ethernet 直連（不要走 Wi-Fi）
3. 重啟 Go2

## 若 nav 不穩
PawAI 自己講「導航在場測中，今天先展示感知與互動」
demo 跳過 nav 段，補 brain 對話

## 若 reactive_stop 也不穩
講「安全停障在開發中」
完全跳過動作 demo，只做純對話
```

---

## 6. 5/12 PM 任務排程

| 時段 | 任務 |
|---|---|
| 13:00-13:30 | Mode 1 smoke（家裡） |
| 13:30-14:00 | Mode 2 No-AI smoke（env bad endpoint：`LLM_ENDPOINT=http://127.0.0.1:1/...` + `QWEN_ASR_BASE_URL=http://127.0.0.1:1/...`） |
| 14:00-15:00 | Mode 3 Mac as operator（家裡用手機熱點模擬） |
| 15:00-15:30 | 寫 `docs/runbook/demo-fallback-script.md` |

**Gate**：三模式各一次 smoke pass + fallback 話術文件落檔。

---

## 7. 與其他 plan 的關係

- **A.Brain Minimum** 的 canned 自介（短版 10s）= 本 plan Mode 2 的核心 demo 內容
- **D.Audio** 在 Mode 1+3 都會跑到，注意 USB 麥在 Mac 模式下要不要重綁
- **E.Mac/Network** 的 `school_demo.env` + Mac wrapper 是本 plan Mode 3 的前提

---

## 8. 不在這份 plan 的事

❌ 完全離線 LLM（Ollama 本地 Qwen2.5）— 之前 P1 排程，demo 後再說
❌ 多 Jetson session 切換
❌ Edge 算力 profiling

---

**End of Runtime Fallback Readiness**
