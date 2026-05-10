---
name: brain-studio-lane
description: >
  PawAI Brain × Studio 開發 lane 的標準操作。管 conversation_graph_node、
  interaction_executive、tts、asr、studio gateway、frontend、Mac 操作端。
  觸發詞："brain lane"、"啟 brain"、"開 brain"、"brain dev"、"/brain-lane"、
  "起 studio"、"開 studio"、"brain studio"、"PawAI Brain"。
  在使用者要做 LLM persona 調整、Studio chat 測試、自然度 eval、TTS 驗證、
  Brain freeze 後測試時主動建議。也用於 Brain × Nav 切換時的 lane handoff。
  不要在 Nav / SLAM / LiDAR / 避障場景觸發（那是 nav-avoidance-lane）。
---

# brain-studio-lane

PawAI Brain + Studio 一切 runtime 的固定操作法。把過去手動逐一 export env、
source .env、選 plughw card#、避坑、起 tmux 的流程，包成 4 個 sub-command。

每次叫起這個 skill 就走固定 4 步：preflight → start → healthcheck → cleanup。
不再靠記憶開 node、不再每次踩 Jetson 路徑差異 / .env 沒 source 的坑。

## 為什麼存在

Brain 開發跟 Nav 場測共用 1 台 Jetson + 1 隻 Go2，必須輪流啟動。每次手動拼裝
容易漏 node、漏 .env、漏 plughw 卡號漂移、漏 Jetson 路徑差異（`~/elder_and_dog`
vs `~/newLife/elder_and_dog`）。skill 把這些固化成腳本，搭配 nav-avoidance-lane
的對應 cleanup → handoff 機制。

## CLI 介面

四個 sub-command，全部走 `bash .claude/skills/brain-studio-lane/scripts/{name}.sh`：

```bash
# 啟動（mode = minimal | e2e | full，studio 是 overlay flag）
bash .claude/skills/brain-studio-lane/scripts/start.sh <mode> [--studio]

# 啟動前檢查（自動被 start.sh 呼叫；也可手動跑）
bash .claude/skills/brain-studio-lane/scripts/preflight.sh <mode> [--studio]

# 健康檢查（start 後手動跑，或 dev cycle 中要 verify 時跑）
bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh

# 清理（兩 lane 一律清 go2_driver；handoff 旗標只影響 cleanup 完的提示文字）
bash .claude/skills/brain-studio-lane/scripts/cleanup.sh [--handoff nav|none]
```

## Mode 對照表

| mode | 啟什麼 | 用什麼底層 script | 用途 |
|---|---|---|---|
| `minimal` | interaction_executive + conversation_graph_node | `scripts/start_pawai_brain_tmux.sh` | 改 persona / few-shot 後純文字 pub `/brain/text_input` 測 |
| `e2e` | minimal + tts_node | `scripts/start_pawai_brain_tmux.sh` + 補 tts window | 用 Studio chat / 文字輸入測完整 reply→audio |
| `full` | go2 + camera + face + vision + executive + asr + tts + llm + object + gateway | `scripts/start_full_demo_tmux.sh` | 五功能 demo。⚠️ **此 mode 用 legacy `llm_bridge_node`，不是新 6 檔 persona brain**。Demo 用，新 persona 改動在這個 mode 看不到 |

`--studio` overlay：在 Jetson 起 `studio_gateway`（port 8080），在當前環境起 Next.js
frontend（port 3000，被占用自動 fallback 3001/3002）。frontend env `NEXT_PUBLIC_GATEWAY_URL`
自動指向 Jetson Tailscale IP `100.83.109.89:8080`。

## 預設執行流程

使用者說「啟 brain e2e」「開 brain studio」「brain lane minimal」時：

1. **解析意圖** — 從句中抓 mode + studio overlay
2. **跑 preflight** — `bash scripts/preflight.sh <mode> [--studio]`
3. **如果 P0 fail** → 報出原因，問使用者要怎麼處理（修還是降級）
4. **如果 preflight pass** → `bash scripts/start.sh <mode> [--studio]`
5. **跑 healthcheck** — `bash scripts/healthcheck.sh`，回報哪些 topic alive
6. **告知 frontend URL**（如果有 `--studio`）

切去 nav lane 時：使用者說「換 nav」「切去 nav」「handoff nav」→ 跑 `cleanup --handoff nav`。

## Preflight 檢查項（P0 / P1 分級）

P0 fail 直接擋啟動，P1 fail 只 warn 不擋。詳見 `references/troubleshooting.md`。

| 檢查項 | 級別 | 失敗動作 |
|---|---|---|
| Jetson SSH 通（`ssh jetson-nano echo`） | **P0** | 擋 |
| `~/elder_and_dog/.env` 存在於 Jetson | **P0** | 擋 |
| port 8080 沒被占用（Jetson）| **P0** | 擋（但 cleanup 會自動清） |
| `OPENROUTER_API_KEY` 在 .env 內 | **P1** | warn — 會 fallback RuleBrain 仍可跑 |
| LLM tunnel `localhost:8000/health` 200 | **P1** | warn — 會 fallback local Qwen / RuleBrain |
| ASR tunnel `localhost:8001` alive（e2e/full）| **P1** | warn — 會 fallback whisper_local |
| Jetson 上 `aplay -l` 找得到 CD002-AUDIO（e2e/full + 有外接喇叭時）| **P1** | warn — TTS 仍 publish 到 `/tts`，只是沒實體聲音 |
| Jetson 上 `~/elder_and_dog/install/pawai_brain/share/pawai_brain/personas/v1/` 6 檔齊（minimal/e2e）| **P0** | 擋 — brain 會 inline persona，跟 freeze 不一致 |
| 沒有 `nav_*` tmux session 在跑 | **P1** | warn — 提醒先 nav cleanup --handoff brain |

## Healthcheck 驗證項

| 項目 | 怎麼檢 | 應該看到 |
|---|---|---|
| brain 已 ready | `tmux capture-pane -t pawai_brain:conv_graph` 包含 `conversation_graph_node ready` | ✅ |
| OpenRouter 通 | log 有 `openrouter=on` | ✅（off 表示 .env 沒 source） |
| persona 6 檔載入 | log 有 `loaded directory ... 6 files verified` | ✅ |
| `/brain/chat_candidate` 有 publisher | `ros2 topic info /brain/chat_candidate` Publisher count ≥ 1 | ✅ |
| `/tts` 有 publisher（e2e/full）| `ros2 topic info /tts` Publisher count ≥ 1 | ✅ |
| Studio gateway `/health` 200（--studio）| `curl localhost:8080/health` | `{"status":"ok",...}` |
| Frontend port alive（--studio）| `curl localhost:3000` 或 3001 | HTML 200 |

## Handoff 邏輯

`--handoff` 旗標**目前不影響清的範圍**（兩 lane cleanup 都會清 go2_driver），
只影響 cleanup 完的下一步提示文字。

理由：nav lane 的 `start.sh` 直接呼叫既有 `start_*_tmux.sh`，那些腳本內部
都會自啟 driver instance，無 reuse 機制 → 若 cleanup 不清 driver，nav 啟
動後會雙 driver / 雙 publisher / 雙 odom，AMCL 行為混亂。

| 用法 | 行為 |
|---|---|
| `cleanup --handoff nav` | 清全部 brain process + driver，提示「下一步建議跑 nav-avoidance-lane start」 |
| `cleanup --handoff none`（或不帶）| 清全部 brain process + driver，提示「完整清理完成」 |

未來若實作「nav start 偵測既有 driver 跳過自啟」，再讓 handoff 真正影響
是否保留 driver。目前先以 unconditional 清 driver 換取安全。

## 常見場景速查

**改完 persona 想測自然度（純文字）**：
```
brain-studio-lane start minimal --studio
→ 開 http://localhost:3001/studio 用 Chat 測
```

**改完 persona 想測語音輸出**：
```
brain-studio-lane start e2e --studio
→ Chat 打字，會聽到 Jetson USB 喇叭播 reply
```

**Demo 五功能整合驗證**：
```
brain-studio-lane start full --studio
⚠️ 這個 mode 走 legacy brain，新 persona 改動看不到
```

**切去 nav 場測**：
```
brain-studio-lane cleanup --handoff nav
nav-avoidance-lane start fallback
```

## 進一步閱讀

- `references/runtime-topology.md` — 各 mode 啟哪些 node、誰 publish 誰 sub
- `references/ports-env.md` — env vars + port 表 + Jetson/WSL 路徑差異
- `references/troubleshooting.md` — 8+ 條已踩過的坑 + 修法
