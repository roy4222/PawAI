# Jetson 真機 Smoke 結果（Phase B Day 2 開頭）

**日期**：2026-05-04 evening（執行於 5/4 20:03–20:30 WSL+Jetson）
**Plan 來源**：`/home/roy422/.claude/plans/jetson-kind-book.md`
**目的**：驗證 Phase B Day 1 commits（OpenRouter Gemini 鏈、Skill Registry、Studio chat-first）能在 Jetson 實機跑起來，再決定後續是否進 B1 TTS 換血 / self_introduce / B6 PR port。

---

## TL;DR

- ✅ **Step 1** USB 喇叭硬體 — `aplay` 出聲
- ✅ **Step 2** TTS node 單獨 — edge-tts + USB 喇叭出中文
- ✅ **Step 3** llm_bridge brain mode + OpenRouter Gemini — 3/3 round 命中（無 timeout warning）
- ✅ **Step 4** 全鏈 LLM → TTS（legacy mode 走 `/tts` 直發） — 3/3 端到端，喇叭聽到三句中文 reply

**結論**：OpenRouter Gemini → llm_bridge → TTS → USB 喇叭這條鏈在 Jetson 實機 PASS。可以進 follow-up（B1 TTS 換血、self_introduce、PR port）。

---

## 環境

- WSL：`/home/roy422/newLife/elder_and_dog`，commit `a55f83a`（5/4 chat-first redesign 結尾）
- Jetson：`~/elder_and_dog`，rsync 同步（無 git history）
- 網路：Jetson 直接外網 OK；同時有 SSH tunnel 到 RTX 8000 (`localhost:8000` vLLM, `:8001` ASR)
- USB 硬體：喇叭 CD002-AUDIO 在 **card 2**（`plughw:2,0`）— **CLAUDE.md 寫 card 3 是錯的**，需改
- USB 麥克風未插（user 確定 Demo 用筆電 Studio 收音，明天不用補）

---

## 過程中遇到的坑（明天 / 後續修）

### 1. Jetson `install/` 是舊版，brain mode 全失效
- 症狀：`output_mode:=brain` 設了沒生效，`/brain/chat_candidate` 不發
- 根因：rsync 帶來新源碼，但 `install/speech_processor/.../llm_bridge_node.py` 仍是 commit `fda1b3c` 之前的舊檔
- 解法：`colcon build --packages-select speech_processor`
- **再次踩坑**：`setuptools 81.0.0` 太新，colcon setup.py shim 用的 `--editable`/`--uninstall` 在 80+ 被砍 → build 失敗
  - 修：`pip install --user "setuptools<70"` → 降到 `69.5.1` → build 過
  - **TODO**：寫進 CLAUDE.md「Jetson setuptools 必須 < 70」

### 2. OpenRouter timeout 2.0s 對 Jetson 太緊
- 症狀：第一輪 brain mode 注入後，log 看 `LLM[openrouter:google/gemini-3-flash-preview] timeout (2.0s)` → fallback 整條走完到 Ollama，總共 17s 才回
- 量基線：直接 curl OpenRouter 3 輪，total 1.43–1.57s（DNS 1.5ms / TTFB ~100ms）
- 結論：Python `requests` overhead + parse + retry 把 1.5s 推到 2s 邊緣
- 修：bump `openrouter_request_timeout_s:=4.0` + `openrouter_overall_budget_s:=5.0`
- **TODO**：把 default 從 2.0/2.2 → 4.0/5.0（commit fda1b3c 的 default 對 Jetson 不安全）

### 3. `_on_speech_event` 讀 `text` 不是 `transcript`
- 症狀：注入 `{"transcript":"你好",...}` 結果 LLM reason 寫「語音輸入為空」，回 generic 「汪！我在這…」
- 根因：`speech_processor/speech_processor/llm_bridge_node.py:308` `payload.get("text", "")`
- 修：注入訊息改用 `text` 欄位
- **TODO**：跟 ASR node 的實際 publish schema 對一下；intent contract 可能有歷史漂移，要在 `docs/contracts/interaction_contract.md` 確認哪個是真相

### 4. Reply 不帶 audio tag
- 症狀：3 輪 reply 都是純文字（`你好呀！我是 PawAI。`），無 `[excited]` 等
- 對比：5/4 LLM eval 的 Gemini 輸出全部帶 audio tag
- 推測：llm_bridge_node 的 system prompt 跟 eval 的 persona prompt 不同，沒要求 tag
- **TODO**：B1 TTS 換血時順便對齊 prompt（不影響今天 smoke，因為 edge_tts 也不解析 tag）

### 5. SSH heredoc + tmux 在 Bash 裡的引號地獄
- 多次 `Exit 255`，原因是雙層引號 + `pkill` 回非零中斷腳本
- 解法：`ssh ... bash -s <<'EOF'` 配 `|| true` 護甲
- 已落到 `scripts/_tts_smoke_jetson.sh` / `_llm_bridge_smoke_jetson.sh` / `_e2e_smoke_jetson.sh`（都標 `_` 前綴表 ad-hoc）

---

## 數據

### Step 3：llm_bridge brain mode（OpenRouter Gemini 命中後）

| Round | 輸入 text | reply_text | intent | skill | 延遲 |
|---|---|---|---|---|---|
| good-1 | 你好 | 你好呀！我是 PawAI。 | greet | hello | 3.31s |
| good-2 | 你今天怎麼樣 | 我感覺很棒，隨時準備出發！ | status | – | 3.39s |
| good-3 | 我喜歡狗 | 我也最喜歡你了，汪汪！ | chat | – | 3.38s |

無 `LLM[openrouter:...] timeout` warning ⇒ Gemini 鏈成功（成功路徑無 success log，靠「沒 fail log」反推）。

### Step 4：全鏈 legacy mode → /tts → USB 喇叭

| Round | 輸入 | reply | LLM | TTS gen | TTS playback | wall |
|---|---|---|---|---|---|---|
| e2e-1 | 你好 | 你好呀！我是 PawAI。 | 3.5s | 0.65s | 3.16s | 10.58s* |
| e2e-2 | 今天天氣真好 | 對呀，很適合一起出去玩！ | 3.5s | 1.32s | 2.83s | 10.89s* |
| e2e-3 | 我喜歡你 | 我也好喜歡你，汪汪！ | 3.5s | 1.01s | 2.70s | 10.58s* |

*wall 含我手動 `sleep 9`，實際純 E2E ≈ 7s。

---

## Follow-up 排序（明天決定要不要切 navigation）

P0（今天 smoke 暴露的修正）— **5/4 evening 第二輪已完成**：
1. ✅ CLAUDE.md 修：USB 喇叭 `plughw:2,0` + Jetson setuptools < 70 + rsync 不 rebuild install/
2. ✅ `llm_bridge_node` `openrouter_request_timeout_s` default 2.0 → 4.0、`overall_budget_s` 2.2 → 5.0
3. ✅ Schema 對齊澄清：`stt_intent_node:1136` 和 `llm_bridge_node:308` 都用 `text`；contract doc 也是 `text`。今天 smoke 的「empty input」是我注入時筆誤用 `transcript`，不是程式碼 bug

### B（audio tag strip）— 同輪一併做
- ✅ 新檔 `speech_processor/speech_processor/audio_tag.py`（純函數，無 ROS 依賴）
- ✅ `tts_node.py` import + 在 `tts_callback` 開頭 strip + 保留 `raw_text` 供 log
- ✅ 13 unit tests PASS（含中文括號保留、idempotent、空字串 guard）
- ✅ Jetson smoke：`"[excited] 你是誰"` → log 顯示 `→ stripped "你是誰"`，喇叭實聽 tag 已不被唸出

P1（B1 TTS 換血，spec §8 已寫，~1 天）：
4. Gemini 3.1 Flash TTS PCM 24kHz audio contract
5. TTSProvider 統一 WAV bytes
6. audio tag 渲染（含 system prompt 對齊讓 Gemini reply 帶 tag）

P2（其他 B 任務）：
7. META_SKILLS["self_introduce"] 6-step（contract 已就位，等 trigger 確認）
8. B6 PR #38/#40/#41/#42 port
9. B7 60min 供電壓測

---

## 動作

- ✅ smoke 結果寫進此檔
- 🔲 commit + push 此檔 + 3 個 ad-hoc smoke 腳本（`scripts/_*_smoke_jetson.sh`）
- 🔲 Jetson 端 tmux session `e2e-smoke` 已 kill（`tmux kill-session -t e2e-smoke`）
