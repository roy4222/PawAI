# 互動品質改善 — Design Spec

> **建立**：2026-05-09
> **狀態**：Roy 已 brainstorm 認可、進 plan 階段
> **動機**：Demo 功能完成度 65-70%，但**互動完整度估 45-55%** — 主鏈能跑，節奏 / 記憶邊界 / 主動性 / 說話品質 / Studio 可觀測性都未到產品感
> **硬底線**：5/13 場地驗、5/14 三連跑、5/18 demo

---

## 0. 設計原則

1. **先修架構漏接，不先大換模型** — Gemini 3 Flash 不一定不好，問題在啟動路徑可能落回弱 persona / 自切 chunk silent skip / Studio 不顯示自主語音
2. **不重構成 GPT Realtime 整套 voice agent** — Demo 前風險太高
3. **TTS 三段策略** — 短句 / 情緒句 / 故事走不同 provider，不要全部走 6-7s 主鏈
4. **all-or-nothing > silent skip** — 任何階段失敗都要 fallback chain 接管，禁止 silent partial output
5. **互動策略 > 止血** — face / object cooldown 從工程止血升級為 attention policy

---

## 1. 問題清單與根因（已驗證）

### 1.1 TTS 跳句（demo 級事故）

**位置**：`speech_processor/speech_processor/tts_node.py:625-630`

```python
ok_parts = [p for p in results if p is not None]
full_pcm = b"".join(ok_parts)
```

**根因**：自切 chunk → 並行 N 個 OpenRouter `/audio/speech` request → 任一失敗 silent skip 拼接剩下的

**症狀**：使用者聽到「念一念跳到結尾」，第 4 句完全消失沒有提示

### 1.2 TTS 首音 6-7s

**根因**：
- OpenRouter `/audio/speech` 是 OpenAI-compatible request/response，**不是 streaming**
- 並行打 N 個 chunk，等最慢的那個（max latency）才能拼接播放
- 不是 sum 而是 max — 但 max 通常就是 6-7s

**影響**：互動感死，使用者以為斷線

### 1.3 LLM 回覆死板

**位置**：`pawai_brain/pawai_brain/conversation_graph_node.py:67-72` (inline 備案 6 行) vs `tools/llm_eval/persona.txt` (185 行完整 persona)

**根因待驗證**：`pawai_conversation_graph.launch.py` 預設 `llm_persona_file` 是空 → 落回 inline 備案 → 回覆模板化

### 1.4 LLM 不主動鏈式調用

**根因**：系統其實會自動進 PendingConfirm（`brain_node.py:403-415`），但 **persona 沒明寫**「使用者要求扭一扭/搖一下/比 OK 就做動作時，必須 output `skill: wiggle`」→ LLM 只說「好啊請比個 OK」但不出 skill 欄位 → 永遠不進 PendingConfirm

### 1.5 重複觸發干擾

- `brain_node.py:67` `OBJECT_REMARK_DEDUP_S = 60.0`，dedup key = `(class, color)` → **同一椅子顏色抖動就繞過**
- `brain_node.py:637-640` `greet_known_person` per-identity 20s → **路過比 OK 會被打招呼打斷**
- `brain_node.py:256-259` `_has_active_sequence` **只擋 SEQUENCE 優先級，不擋 SKILL** → 動作中還是會 emit object_remark plan
- **無全局 engaged-state**

### 1.6 Studio 缺自主語音氣泡

**位置**：`pawai-studio/frontend/.../chat-panel.tsx:96-112`

**根因**：ChatPanel 只在「pending user request」時把 reply 當 AI bubble；自主語音（stranger_alert / object_remark / greet）只進 `lastTtsText` 不進 messages 陣列

### 1.7 ASR 簡體輸出

**位置**：`asr_client.py:48`、`sensevoice_server.py:66/122`、`asr_node.py:70/142` 全部硬編 `language="zh"`

**根因**：無 OpenCC 層，SenseVoice 預設輸出簡體

### 1.8 重整不重置 context

**位置**：`conversation_graph_node.py:149` `ConversationMemory(max_turns=5)` in-memory deque

**根因**：前端 reload 只清 UI state，brain memory 不清；無 reset API / topic

### 1.9 無 idle 行為

**根因**：brain pure reactive，無 `last_user_interaction_ts`、無 idle timer

---

## 2. 修復計畫（依 Roy 確認的優先順序）

### Wave 0 — P0 demo 級止血（今天/明天）

**P0-1 TTS silent-skip 止血**
- `tts_node.py:625-630` 改 all-or-nothing：任一 chunk None → `return None` 讓上層 fallback chain 接 edge-tts
- 不立刻移除 chunking（整段一次送可能 timeout），保留並行但失敗就整段 fallback
- 預期：**跳句立即消失**；首音延遲不變（後續 P2 處理）

**P0-2 Gateway /tts JSON envelope parse**
- 確認 `studio_gateway.py` `_on_tts_msg()` 是否正確抽 reply_text 出來給 ChatPanel
- 若 ChatPanel 收到 JSON 字串而非純文字，這裡修
- 預期：Studio 不再顯示原始 JSON

### Wave 1 — P1 互動骨架補完（5/10-5/12）

**P1-1 Studio ChatPanel 顯示所有 utterance**
- `chat-panel.tsx` 改成監聽全部 TTS event，不只配對 pending request
- 加 source 標記區分：`user_speech` / `llm_reply` / `say_canned` / `idle_chatter`
- `state-store.ts` 加 `messages` 陣列保留所有 robot utterance
- 收益：Roy 知道狗講過啥、Brain 全可觀測

**P1-2 Context reset on refresh**
- `brain_node` 加 `/brain/reset_context` topic（std_msgs/Empty）→ 呼叫 `ConversationMemory.clear()` + 清 `_seen_sessions`
- `studio_gateway` 加 `/api/reset` POST endpoint → publish 該 topic
- 前端 `use-websocket.ts` connect 時呼叫 `/api/reset`
- 收益：頁面重整就是新對話，不會混淆

**P1-3 ASR 簡→繁 OpenCC**
- 加依賴 `uv pip install opencc`（s2twp 簡→繁台灣）
- 掛點：`asr_client.py` 出口（return text 前）統一轉繁
- 加 launch arg `asr_output_locale: zh-TW` 預設
- 收益：Studio + brain context 全是繁體，台灣語感對齊

**P1-4 LLM persona 不死板 — 保守版 A（Roy 5/9 brainstorm 確認）**

**已實證根因**：
- `pawai_conversation_graph.launch.py:20-22` `llm_persona_file` 預設 `default_value=""`
- 空字串落回 `conversation_graph_node.py:67-72` 6 行 inline persona（176 字元 vs 完整 11.5KB / 6940 tokens）
- **但**：`scripts/start_full_demo_tmux.sh:217` **已正確傳** `llm_persona_file:=...persona.txt`
- 真正問題：`scripts/start_pawai_brain_tmux.sh:15` 還在啟舊 `llm_bridge_node`，不是 conversation_graph_node — 這條路徑會 silent 用 inline persona

**1A 立即做（半天，必做）**
- 修 `pawai_conversation_graph.launch.py` 預設 → `tools/llm_eval/persona.txt` 絕對路徑
- 修 `conversation_graph_node._load_persona()` — missing/empty 改 ERROR raise 而非 silent fallback
- 修 `scripts/start_pawai_brain_tmux.sh` 切到 conversation_graph_node 路徑，移除 llm_bridge_node
- 加開機 log：`[persona] loaded /path, N lines, sha=...`

**1B 同日做（半天，輕量重排）**
- **不拆檔**（拆檔風險高、validator/repair 都要動）；單檔 `persona.txt` 內部重排成 OpenClaw 式 5 層：
  ```
  ## Identity (誰、靈魂 70/20/10)
  ## Style Rules (hard constraints — 不說「我是 AI」、字數上限、語氣分布)
  ## Skill Policy (17 skills + 觸發條件 + 主動提案規則)
  ## Few-shot Examples (12 → 16-20 個，補：奶奶/陌生人語氣、主動 wiggle、silent reply)
  ## Runtime Instructions (audio tag、JSON schema、capability_context 用法)
  ```
- 補 wiggle/OK 主動提案 rule + 5 個 few-shot：
  > 當使用者要求「扭一扭 / 搖一下 / 比 OK 就動 / 來個可愛動作」時，**必須**輸出 `{"skill": "wiggle", "reply": "[playful] 好啊！比個 OK 我就扭給你看"}`，不可只講話不出 skill
- **不**硬規則「句尾汪/嗚」（避免幼兒化、尷尬重複）；改寫成「**偶爾、低頻、只在 playful 情緒**」guideline
- 注入順序：穩定區（identity/rules/skills/examples）在前，volatile（runtime/memory/face_state）在後 — prefix-cache 友善

**1C 同日做（半天，A/B eval）**
- launch 加 `llm_model` + `llm_temperature` arg（已有但需驗）
- 用 `tools/llm_eval/` 框架跑 30 round 4 組對照：
  - Gemini-3 + temp 0.2（baseline）
  - Gemini-3 + temp 0.6
  - DeepSeek-V4 + temp 0.2
  - DeepSeek-V4 + temp 0.6
- 評分維度：persona 維持力、JSON schema 命中率、skill 提案率、中文自然度、延遲
- 結論決定主線

**1D 同日做（半天）— current_speaker 注入**
- `_build_user_message()` 從 face_state 抓最近 1 秒 identity → 加 `current_speaker: Roy / 奶奶 / 陌生人 / unknown`
- persona few-shot 加對應 examples（對奶奶溫柔慢、對 Roy 俏皮快、對陌生人禮貌試探）
- face_state 不可得時 fallback `unknown`，prompt 不報錯

**明確不做（demo 前風險）**
- ❌ Reply Tags `<say><skill>` schema 改造（動 validator + repair + skill_gate，太深）
- ❌ persona.txt 拆 4 檔（IDENTITY/RULES/SKILLS/EXAMPLES 多檔）— 留 demo 後
- ❌ Claude Opus 4.7 / GPT-5.5 試點（成本高、延遲不確定、GPT-5.5 官方未列）
- ❌ 完整 OpenClaw 8 種 hook 系統化

**預期收益**：互動自然度 5/10 → 7-8/10；不誘人感大幅改善；wiggle/OK 主動鏈式打通

### Wave 2 — P2 互動品質升級（5/12-5/13）

**P2-1 face/object audible cooldown 調整**
- `OBJECT_REMARK_DEDUP_S` 60 → 保留；**dedup key 改成 `class_name` 不含 color**（`brain_node.py:760-764`）
- `greet_known_person` per-identity 20s → 60s（甚至 90-120s 看實測）
- 加全局 engaged-state：`_user_engaged_until_ts`，speech intent 進來就更新；engaged 期間 stranger_alert / object_remark / greet 全靜音
- 收益：路過比 OK 不再被打招呼打斷；同一椅子顏色抖動不會繞過 dedup

**P2-2 TTS Plan A spike — gemini_native provider**
- 新增 `TTSProvider_GeminiNative` class，**保留** `openrouter_gemini` 不取代
- 用 google-genai SDK，加 prompt prefix「請使用台灣用語的繁體中文，以親切活潑、像小狗的語氣朗讀。語氣要連貫不要斷句。」
- **先確認模型名**：官方目前是 `gemini-2.5-flash-preview-tts` / `gemini-2.5-pro-tts`，文章寫的 `gemini-3.1-flash-tts-preview` 待 Jetson smoke 驗證
- Jetson 跑 10 句 smoke：短句 / 長句 / audio tag / 繁中台灣語氣 / fallback / timeout
- 若 streaming 真實可用 → 評估 Megaphone 邊收邊播；若不可用 → 整段送但 prompt 改善至少解決語氣
- 收益（如果通）：跳句永久消失 + 語氣連貫 + 首音 ~1-2s
- 收益（如果不通）：至少解決語氣，延遲問題 fall back 到 P2-3

**P2-3 TTS provider 雙軌路由**
- `tts_callback` 加路由邏輯：
  - **短句即時反應**（< 30 字 或 source=say_canned）→ edge-tts（1-2s）
  - **情緒句 / 長句 / 故事**（> 30 字 或 LLM free reply）→ gemini_native（如 P2-2 通）或 openrouter_gemini（fallback）
- ElevenLabs / gpt-4o-mini-tts 不在 demo 前引入（成本 + 風險）
- 收益：60%+ 對話走 edge-tts 1-2s 路徑，互動感大幅提升

### Wave 3 — P3 加分項（5/14 之後或 demo 後）

**P3-1 Idle 待機行為**
- `brain_node` 加 `last_user_interaction_ts` (在 `_on_speech_intent` / `_on_gesture` 更新)
- 加 `_idle_tick_timer` (0.2 Hz)
- guardrail：
  - `not _has_active_sequence()`
  - `_pending_confirm.state == IDLE`
  - `_chat_buffer.empty()`
  - `last_tts_finished_ts > 5s ago`
  - `depth_clear == True`
  - `now - last_user_interaction_ts > 600s` (10 min)
- whitelist：`say_canned` 短句、`wave_hello`；**禁止** wiggle / stretch / nav / dance 自主觸發
- LLM 決策路徑：brain 主動 emit `idle_prompt` event → conversation_graph_node 用特殊 system prompt「你閒置了 10 分鐘，講一句可愛的觀察」→ output 走 say_canned plan
- 收益：產品感升級為「會自己玩」

---

## 3. 不做的事（Demo 前明確 out of scope）

- ❌ ElevenLabs / GPT-Realtime-2 TTS 主鏈替換（成本 $99+/mo + 風險高）
- ❌ LLM streaming 改 conversation_graph_node（動 LangGraph 太深）
- ❌ VAD 演算法替換（webrtc-vad / silero-vad，風險誤切句）
- ❌ Megaphone 16kHz → 24kHz 改造（DataChannel 協議改動，Go2 不一定支援）
- ❌ 完整 OpenClaw 9 層 prompt 架構重構（單層 persona 加 rule 已夠）
- ❌ 雷達 / Nav2 整合 idle 巡邏（守護犬 spec 已 superseded）

---

## 4. 驗收標準

### Wave 0 完成標誌
- [ ] 跳句不再發生（5 句故事連續播 5 次無斷）
- [ ] Studio 不顯示原始 JSON

### Wave 1 完成標誌
- [ ] Studio ChatPanel 顯示所有 PawAI utterance（包含 stranger_alert / object_remark / greet / idle）
- [ ] 重整頁面後第一句對話不帶舊 context
- [ ] ASR 輸出全是繁體（5/5 round 抽樣 100% 繁體）
- [ ] 開機 log 確認 persona.txt 185 行載入
- [ ] 「比 OK 我就扭一扭」mic 觸發 → wiggle skill 進 PendingConfirm（3/3 round）

### Wave 2 完成標誌
- [ ] 路過比 OK 連續 5 次：face greet 出現 ≤ 2 次
- [ ] 自由對話首音延遲 中位數 < 3s（如 P2-2 通）或 < 5s（如只 P2-3 雙軌）
- [ ] 同一椅子 60s 內 dedup 不繞過（顏色抖動測試）

### Wave 3 完成標誌（demo 後）
- [ ] 閒置 10 min 觸發 idle utterance ≥ 1 次
- [ ] idle 期間 user 一講話立刻 cancel（ < 500ms）

---

## 5. 風險與待驗證假設

| 假設 | 待驗 |
|---|---|
| 文章寫的 `gemini-3.1-flash-tts-preview` 模型名 | 官方 docs 主線是 `gemini-2.5-flash-preview-tts`，先 Jetson smoke 確認 |
| native SDK streaming 真的能 1-2s 首音 | 待 Jetson 10 句 smoke；可能還是 6-7s（Google API region latency） |
| Megaphone DataChannel 邊收邊播可行 | 目前是整 WAV chunk_size=4096 base64 上傳，streaming 要重看協議 |
| ElevenLabs class 已實作可直接啟用 | code 第 234 行存在，但未 demo 期測試；spike 不在 demo 前做 |
| OpenCC s2twp 在 Jetson aarch64 wheel 可用 | `uv pip install opencc-python-reimplemented` 預期 OK |
| persona.txt 185 行 model 真能跟 | Gemini-3 上下文 1M tokens 不是問題；deepseek-v4-flash 待測 |

---

## 6. 實作順序與分支策略

主分支 `main` 不長 trunk-based；建議：

1. **`fix/tts-silent-skip`** — P0-1 + P0-2，半天，merge 即上 Jetson 驗
2. **`feat/studio-full-chat`** — P1-1，1 天
3. **`feat/context-reset`** — P1-2，半天
4. **`feat/asr-tw`** — P1-3，半天
5. **`fix/persona-load`** — P1-4 + P1-5（同改 persona.txt + launch），半天
6. **`feat/attention-policy`** — P2-1，1 天
7. **`spike/gemini-native-tts`** — P2-2，1-2 天，**spike branch 不 merge**，確認可行再開 feat
8. **`feat/tts-dual-route`** — P2-3，半天（依 P2-2 結果調整）
9. **`feat/idle-mode`** — P3-1，1-2 天

每支 PR 都跑：`pytest 61/61` + Jetson colcon build + 手動 demo flow 5 句驗。

---

## 7. 預期 demo 改善

| 維度 | Before (5/8 evening) | After (Wave 0+1+2 完成) |
|---|---|---|
| 互動完整度 | 45-55% | 70-80% |
| TTS 跳句 | 偶發 | 0% |
| 自由對話首音延遲 | 6-7s | 2-4s |
| Studio 對話可觀測性 | 30%（只 pending request） | 100% |
| Persona 自然度 | 模板感 | 完整 persona + 主動鏈式 |
| 路過比 OK 被打斷 | 有 | 無（engaged-state） |
| 重整 context 混淆 | 有 | 無 |
| ASR 簡繁 | 簡體 | 繁體 |

Idle 行為（Wave 3）為 demo 後加分項，不列入 demo 驗收。
