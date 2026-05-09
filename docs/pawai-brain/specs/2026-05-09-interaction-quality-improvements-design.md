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

**P0-2 Gateway `/tts` JSON envelope parse（P1-1 前置必要）**

**為何排 P0**（Roy 5/9 grep 確認，真實 bug 不是假想）：
- 上游 publisher 確實會發 JSON envelope：`interaction_executive_node.py:185-194` 在 step `input_origin` 存在時 `msg.data = json.dumps({"text": text, "input_origin": input_origin}, ensure_ascii=False)`
- 下游 gateway 在 `studio_gateway._on_tts_msg()` L298-306 `text = msg.data.strip()` 直接當純文字 wrap 進 `build_tts_event(text)` → ChatPanel 拿到的 `text` 欄位內容就是整段 JSON 字串
- 觸發條件：Studio 文字輸入經 chat_reply 路徑回 SAY step 時 `input_origin="studio_text"` 會帶進 envelope，**demo 期 Studio chat 100% 觸發**
- 合約 §5.2 規定 `/tts` 雙模化（純文字 OR JSON envelope）— gateway 必須處理

**改法**（gateway 側 ~10 行）：
1. `studio_gateway._on_tts_msg`：先嘗試 `json.loads(msg.data)`，成功且有 `text` field → 用 envelope.text + 帶 `origin = envelope.input_origin or "tts"`
2. parse 失敗或非 dict → 純文字 fallback（向後相容）
3. `build_tts_event(text, origin)` 帶上 origin 給 frontend

**預期**：Studio 不再顯示原始 JSON；P1-1 前端可放心 append

### Wave 1 — P1 互動骨架補完（5/10-5/12）

**P1-1 Studio ChatPanel 顯示所有 utterance（純前端起步 + 漸進升級）**

**已實證根因**：`chat-panel.tsx:96-112` 只在 `pendingRequestIdRef.current` 存在時把 `lastTtsText` append 進 messages。所有自動觸發 TTS（say_canned / stranger_alert / object_remark / greet / event_action_bridge gesture-pose-fall / route_runner / skill 中間 SAY step）全被丟掉。

**8 個 `/tts` publisher 沒一個帶 source metadata**：IE-node / event_action_bridge × 3（gesture/pose/fall）/ llm_bridge / intent_tts_bridge / route_runner — `/tts` msg type 是 `std_msgs/String` 純文字（少數含 JSON envelope 但只帶 input_origin）。

**前置依賴**：P0-2 Gateway `/tts` envelope parse 必須先做，不然 ChatPanel 顯示 JSON 字串。

**Phase 1（demo 前必做，1 小時）— 4 步精準改動**

**P1-1a state-store 加 ttsMessages 陣列**
- `state-store.ts`：保留 `lastTtsText` / `lastTtsAt`（其他 panel 還用），**新增** `ttsMessages: { id, text, timestamp, origin }[]`
- ring buffer max 200 條，超過 shift 最舊
- 用 `id` 欄位做 dedup key（PawAIEvent.id）— 防 React effect 重跑造成重複 bubble

**P1-1b ChatPanel 監聽 ttsMessages 全部 append**
- `chat-panel.tsx`：監聽 `ttsMessages` 變動 → 把新 message append 成 PawAI bubble
- 用 `lastSeenTtsIdRef` 記住最後處理的 event id；只 append 比 lastSeen 新的
- `use-event-stream.ts`：`case "tts"` → `appendTtsMessage({id, text, timestamp, origin})`，不要動 updateTts

**P1-1c pendingRequestIdRef 角色重新定義**
- **不刪 pendingRequestIdRef**！它仍然要管：
  - `isThinking` 狀態（user 送 chat → 等 reply 期間）
  - timeout / 失敗處理
  - speech intent 配對
- 改變的只是「是否顯示 TTS」這條判斷 — 從「pending 才顯示」變「永遠顯示」
- pending 中收到的 TTS 仍可額外觸發 isThinking=false，但不再 gate display

**P1-1d 樣式區分 pending vs spontaneous**
- pending TTS（user 剛問 → 配對的 reply）→ 一般 PawAI 灰氣泡
- 非 pending TTS（自動觸發 / spontaneous utterance）→ **淡灰氣泡 + 小時鐘圖標**
- 不需要後端 source metadata，純看「當下有沒有 pendingRequestId」分類
- demo 後 P1-1 Phase 2 拿到 origin 欄位再細分 skill_say/canned/alert

**Phase 2-mini（Roy 5/9 review #3 提前到 Wave 1，30min）— IE-node SAY source 單點**

只改 1 個 publisher（IE-node `_dispatch_step` SAY），其他 7 個維持純文字（demo 後再補）。CP 值最高，因為 IE-node SAY 是 demo 核心（self_introduce 10 步 + wave_hello 等都走這條），skill_say 不分色 demo 觀感跟 chat 完全混。

具體：
1. `interaction_executive_node.py:185-194` SAY envelope 已有 `input_origin`，再加 `source: "skill_say"` 欄位
2. gateway P0-2 改造後一併 parse `source` field 進 broadcast
3. ChatPanel CSS：skill_say（綠）/ chat_reply pending（一般灰）/ canned 與 alert（淡灰，沒 source 欄位）
4. **保留**純文字 backward compat（合約 §5.2 雙模化）

**Phase 2-full（demo 後可選，再 1 小時）— 其餘 publisher source metadata**
1. event_action_bridge 改 JSON envelope（gesture/pose/fall 三個）
2. llm_bridge / intent_tts_bridge / route_runner 改 JSON envelope
3. ChatPanel CSS 細分 source（skill_say 綠 / canned 橙 / alert 紅 / 其他）

**風險：spam scroll**

**P1-1 Phase 1 部分先做 client-side rate-limit**（Roy 5/9 review #1）— P2-1 attention policy 5/12-13 才上，5/10-12 之間 P1-1 一上線會洪水。

**Rate-limit 規則**（state-store 內 5 行 dedup logic）：
- **限制範圍**：spontaneous / autonomous TTS（origin 為 `say_canned` / `alert` / 其他自動觸發）
- **不擋**：user pending reply（`pendingRequestIdRef.current` 存在的 reply）、safety（含 stop/小心 keyword）、user 自己問的回覆
- **規則**：同 source（粗判可用 text 前 10 字 hash 或 origin 欄位）5s 內最多 1 條 append；超出 silently drop（不進 ttsMessages，不 append bubble）
- **目的**：5/10-12 開發測試體驗不洪水；P2-1 attention policy 上線後 rate-limit 仍保留作 belt-and-suspenders

其他防線：
- 緩解：依賴 P2-1 attention policy（only ENGAGED 才 emit）自然降量
- 前端 ring buffer 200 條 + auto-trim 防爆
- 加 filter UI（toggle 顯示 user_speech / llm_reply / auto_trigger）— Phase 2 可選

**避免兩個坑**（Roy 5/9 抓出）：
1. ❌ 不用 P0-2 直接做 P1-1 → ChatPanel 顯示整段 JSON 字串
2. ❌ 用「length 比較」或 useEffect 重跑 append → 同 TTS event 重複氣泡（用 event id dedup 解）

**收益**：Roy 知道狗講過啥、Brain 全可觀測；不用聽 Jetson 喇叭憑記憶 debug

**P1-2 Context reset on refresh — 手動為主 + F5 dev-only feature flag（Roy 5/9 收斂）**

**已實證 2 個非預期**：
1. **brain memory 全局單例**：`ConversationMemory` 在 `conversation_graph_node` 唯一例，多 ws client（筆電 + 手機 + 大螢幕）共用同一 deque，沒 per-session 隔離。F5 一台會清全 brain
2. **F5 vs 網路抖動 use-websocket.ts 無法區分**：都是 `close → 3s reconnect`。純 ws onopen 無條件 reset 會被網路抖斷誤觸

**Demo / Dev 雙模式設計（不綁死同一預設）**

| 模式 | reset 觸發 | env flag |
|---|---|---|
| **Demo（預設）** | 只靠手動「新對話」按鈕 | `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=false`（預設） |
| **Dev** | 手動按鈕 + F5 hybrid auto-detect | `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=true` |

**Frontend（`pawai-studio/frontend/`）**

**P1-2a 手動按鈕（必做、demo 主用）**
1. ChatPanel header 加「新對話」按鈕 → `fetch('/api/reset', {method: 'POST'})` + 清前端 messages 陣列
2. 操作員（Roy）控制按下時機，避免奶奶/教授看到對話突然斷
3. **按鈕加 confirm dialog + tooltip**（Roy 5/9 review）：
   - tooltip：「重置全局對話記憶（所有 device 共用）」
   - confirm dialog：「將清除目前所有對話記憶，包括其他開啟的 Studio 視窗。確定？」
   - 理由：brain memory 是全局單例，按下會清所有 device 對話 — 不能讓操作員誤觸
4. **不加刷新警告**：demo 預設 `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=false`，刷新不會 auto reset；加警告反而誤導

**P1-2b F5 auto-detect（dev-only feature flag）**
- 預設 **OFF**；開 `NEXT_PUBLIC_AUTO_RESET_ON_REFRESH=true` 才啟用
- 機制：
  ```ts
  // layout.tsx 或 _app.tsx — 永遠註冊 beforeunload 寫 flag（成本低）
  window.addEventListener('beforeunload', () => {
    sessionStorage.setItem('paw_refresh_at', Date.now().toString())
  })

  // use-websocket.ts ws.onopen — 只在 flag 開時才 reset
  if (process.env.NEXT_PUBLIC_AUTO_RESET_ON_REFRESH === 'true') {
    const refreshAt = sessionStorage.getItem('paw_refresh_at')
    if (refreshAt && Date.now() - parseInt(refreshAt) < 5000) {
      fetch('/api/reset', {method: 'POST'})
      sessionStorage.removeItem('paw_refresh_at')
    }
  }
  ```
- 限制（即使 flag 開也要知道）：
  - `beforeunload` 在「F5 / 關 tab / 導航離頁」都會觸發，不只 F5
  - 多 tab 下任一台 refresh 仍清全 brain（架構限制，前端解不掉）
  - 因此 demo 期建議 **OFF**

**P1-2c 明確不做**
- ❌ `ws.onopen` 無條件 reset（被網路抖斷誤觸）
- ❌ 用 `?fresh=1` query param（手動 F5 不會帶）

**Gateway（`pawai-studio/gateway/studio_gateway.py:385`）**

> 路徑修正：spec 之前寫 `server/`，實際是 `gateway/`

3. 新增 `POST /api/reset` endpoint → publish `/brain/reset_context`（std_msgs/Empty）→ 回 `{ok: true}`

**Brain（兩個 node 都訂同一 topic）**
4. `conversation_graph_node` 訂 `/brain/reset_context` → `self._memory.clear()` + `self._seen_sessions.clear()`
5. `brain_node` 訂同 topic → `self._pending_confirm.cancel("page_reset")`
6. **不清** `_active_plans` / `_state.attention`（多 tab 友善 + demo 中不打斷正在做的動作）

**多 tab 行為（明確標註）**
- demo 期：F5 一台會清全 brain（所有 device 對話一起重置）— 因 brain memory 全局
- demo 期建議靠手動按鈕，操作員控制時機；F5 auto-reset 預設 OFF
- demo 後 P1-2.5（可選）：改 per-session memory（每 ws client 獨立 deque + session_token），那時 F5 只清自己

**業界對照**
- ChatGPT / Claude Web 都**不**在 refresh 時 reset context，反而保留更友善
- PawAI 場景特殊（demo + 開發測試），用 feature flag 拆兩種預設 — demo 安全、dev 方便

**收益**：開發測試 F5 自動清乾淨（flag 開）；demo 期手動完全可控（flag 關）；網路抖動兩種模式都不誤觸

**P1-3 ASR 簡→繁 OpenCC（Roy 5/9 研究 + 雙入口修正）**

**已實證根因**：3 條 ASR provider 全硬編 `language="zh"`，無 zh-TW 選項
- `asr_client.py:48` cloud（QwenASRProvider HTTP `language="zh"`）
- `stt_intent_node.py:631` SenseVoiceLocalProvider（sherpa-onnx int8）
- `stt_intent_node.py:209/242` WhisperLocalProvider（faster-whisper / openai-whisper）
- **FunASR SenseVoice 無 zh-TW 選項**（只支援 `["zh", "en", "yue", "ja", "ko"]`）
- **Whisper 混訓簡繁，無法保證**

**Roy 抓到的關鍵漏網**：**Studio 瀏覽器麥克風 `/ws/speech` 繞過 `stt_intent_node`**

實際 ASR 雙路徑：
- 路徑 A：實機麥克風 → `stt_intent_node` → `/asr_result` + `/event/speech_intent_recognized`
- 路徑 B：Studio 瀏覽器麥克風 → `pawai-studio/gateway/studio_gateway.py:627 /ws/speech` → `asr_client.transcribe()` → `classifier.classify(text)` → publish speech event + 回前端

只改 `stt_intent_node` → Studio mic ASR bubble 仍簡體、brain context 仍吃簡體。

**設計：共用 helper + 雙入口都呼叫**

**1. 新增共用 helper**

`speech_processor/speech_processor/text_normalization.py`：
```python
"""Lazy-import OpenCC; fallback 原文 on any error."""
_converter = None

def to_traditional_tw(text: str) -> str:
    global _converter
    if not text:
        return text
    if _converter is None:
        try:
            from opencc import OpenCC
            _converter = OpenCC("s2twp.json")
        except Exception:
            _converter = False  # mark failed
            return text
    if _converter is False:
        return text
    try:
        return _converter.convert(text)
    except Exception:
        return text
```

**2. 兩個入口呼叫**

**入口 A：`stt_intent_node`**（行 1100 `_publish_asr_result` 前）
```python
from speech_processor.text_normalization import to_traditional_tw
# ...在 transcript = transcript_result.text.strip() 後、publish 前
if self._enable_s2twp:
    transcript = to_traditional_tw(transcript)
```

**入口 B：`pawai-studio/gateway/studio_gateway.py`**（`/ws/speech` handler `:627` 附近）
```python
from speech_processor.text_normalization import to_traditional_tw
# ...在 text = asr_result["text"].strip() 後、classify / publish 前
if enable_s2twp:
    text = to_traditional_tw(text)
```

或放更上游 `asr_client.py` 出口（取決於 gateway 是否直接調 asr_client；放 client 出口更集中）

**3. 套件 + Config**
- 套件：`opencc-python-reimplemented`（純 Python，ARM64 wheel 齊全）
- Config：`s2twp` — 簡→繁台灣 + 片語替換（網絡→網路、程序→程式、鼠標→滑鼠）
- 加依賴位置：
  - `speech_processor/setup.py`（stt_intent_node 用）
  - `pawai-studio/gateway/requirements.txt`（gateway 用）
- launch arg `enable_s2twp: true` 預設；env var `PAWAI_ENABLE_S2TWP` 給 gateway

**4. 邊緣案例**（OpenCC s2twp 原生處理）
- 中英混雜「OK 我搖一下」→ 跳過英文 ✅
- 數字/標點「10:30」「3+5」→ 直通 ✅
- SenseVoice `<|zh|>` 標記 → 已在 `stt_intent_node:324` 移除（不需動）
- 繁→簡→繁迴圈 → 不會發生（ASR 從不輸出繁體）

**5. 性能**：< 1ms（50 字內），E2E 無感

**為何不放 sensevoice_server.py**：cloud server 在 RTX 8000 共用其他服務；改 server 端涉及部署協調。客戶端轉乾淨單一責任

**為何不能只放單一入口**：
- 只放 stt_intent → Studio mic 漏網
- 只放 gateway → 實機 mic 漏網
- 必須雙入口共用 helper

**為何不放 brain entry**：brain 不負責文字正規化；intent classification 也應在繁體上做（避免簡繁差異影響規則匹配）

**收益**：Studio + 實機 + brain memory + LLM context **全部繁體**；s2twp 帶來台灣詞彙風格對齊

**P1-4 LLM persona 不死板 — OpenClaw-lite Persona Architecture（Roy 5/9 brainstorm 收斂後重寫）**

> **重寫動機**：5/9 brainstorm 第一版 1B「persona 內部 5 層重排不拆檔」被推翻。Roy 抓到核心：**現有 persona.txt 把「你是誰」+「你會什麼」+「JSON schema」+「few-shot」混在一個 184 行檔案，導致 LLM 一被問「介紹一下」就照 L24-36 的 9 條能力 bullet 串成功能型客服回答。死板的不是 model，是 prompt 教它這樣寫。**
>
> **解法靈感**：[OpenClaw 9 層 system prompt 架構](https://x.com/servasyy_ai/article/2029489020208848966)。**不照抄 9 層**（demo 前太大），抄它兩個核心設計：
> 1. **L7 Workspace Files = persona 拆檔**（IDENTITY 跟 CAPABILITIES 分檔）
> 2. **L8 Bootstrap Hook = capability_context lazy inject**（不是每輪都灌）
>
> **與 Phase B PawClaw 對接**：Phase B (`docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md`) 已規劃 `workspace/{BODY,SKILLS,SAFETY,PLACES,DEMO_MODE}.md` 但目的是**人類可讀文件**，Phase C 才注入 LLM。本 5/9 P1-4 拆的 5 檔是 **chat path LLM prompt 用**，命名 `pawai_brain/personas/v1/{IDENTITY,STYLE,CAPABILITIES,EXAMPLES,OUTPUT}.md` — 不同 namespace、不同階段、不衝突。Phase C 合流時可由 generator 從 BODY/SKILLS 抽 → personas/CAPABILITIES。

**5 個已實證根因**（Roy 5/9 brainstorm 診斷）：
1. `persona.txt` L24-36 寫死 9 條能力 bullet「被問『介紹自己』時要列出來」← 死板核心
2. `_build_user_message()` 每輪都灌完整 capability_context JSON ← 把 LLM anchor 到「能力選單」
3. `temperature=0.2` ← 趨向最常見答案，模板感
4. 單一 prompt 同時負責閒聊 / 技能選擇 / 安全 / demo guide ← 永遠在「我要不要執行功能」框架說話
5. `_build_user_message()` 寫死 `[語音輸入]` 即使是 Studio 文字輸入 ← prompt sanity 雜訊

---

**1A Persona Loader — 支援 file 或 directory mode（半天）**

**設計**：`llm_persona_file` 參數同時支援兩種模式，舊 persona.txt 立即可 fallback：

**重要區分**（Roy 5/9 review #3 修正）：

| 概念 | 範圍 | 啟動檢查 | 進 base system prompt? |
|---|---|---|---|
| **directory required files** | 5 檔（含 CAPABILITIES.md） | 全 5 檔必須存在，缺即 ERROR raise | — |
| **base system prompt** | 4 檔（IDENTITY + STYLE + OUTPUT + EXAMPLES） | 啟動 concat | ✅ 永遠載 |
| **CAPABILITIES.md** | 第 5 檔 | 啟動讀進記憶體 cache | ❌ base 不放；1D 由 user message conditional block 注入 |

```python
# conversation_graph_node._load_persona() 新邏輯
path = Path(self.llm_persona_file).expanduser()

if path.is_file():
    # 舊模式：單檔 persona.txt（向後相容）
    self._capabilities_md = ""  # legacy mode 沒拆檔，CAPABILITIES 內容已在 persona.txt
    return path.read_text(encoding="utf-8")

if path.is_dir():
    # 新模式：directory；5 檔必須齊，base 載 4
    REQUIRED = ["IDENTITY.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md", "CAPABILITIES.md"]
    BASE_ORDER = ["IDENTITY.md", "STYLE.md", "OUTPUT.md", "EXAMPLES.md"]

    contents = {}
    for fname in REQUIRED:
        f = path / fname
        if not f.is_file():
            self.get_logger().error(f"[persona] missing required {fname}")
            raise FileNotFoundError(f)
        contents[fname] = f.read_text(encoding="utf-8")

    base = "\n\n".join(contents[f] for f in BASE_ORDER)
    self._capabilities_md = contents["CAPABILITIES.md"]  # 給 1D 用，不進 base

    self.get_logger().info(
        f"[persona] loaded directory {path}, "
        f"5 files verified, base 4 files concat ({len(base)} chars), "
        f"CAPABILITIES.md cached separately ({len(self._capabilities_md)} chars), "
        f"base_sha={hashlib.sha256(base.encode()).hexdigest()[:12]}"
    )
    return base

raise FileNotFoundError(path)
```

**修改項**：
- 修 `pawai_conversation_graph.launch.py` 預設 → `pawai_brain/personas/v1`（directory）
- 修 `_load_persona()` 支援 file/dir 雙模；directory mode 5 檔必須齊（含 CAPABILITIES）但 base 只 concat 4 檔；缺 file 即 ERROR raise（不 silent fallback）
- node 加 `self._capabilities_md` 屬性給 1D user message 注入用
- 修 `scripts/start_pawai_brain_tmux.sh:15` 切到 conversation_graph_node 路徑，移除 llm_bridge_node
- 加開機 log：`[persona] loaded directory /path, 5 files verified, base 4 files concat, CAPABILITIES cached separately`
- 舊 `tools/llm_eval/persona.txt` 保留作 demo 安全網（launch arg fallback 即可切回）

---

**1B Persona 拆 5 檔（OpenClaw-lite L7 Workspace Files）**

**檔案結構**：

```
pawai_brain/personas/v1/
├── IDENTITY.md       # 你是誰（70/20/10 小狗童心守護者、靈魂、住在哪）
├── STYLE.md          # 怎麼說話（不客服腔、不拋問題、長度情境決定、audio tag）
├── CAPABILITIES.md   # 你會什麼（lazy inject — 1D 按 mode 注入，預設不載）
├── EXAMPLES.md       # 18-22 個 few-shot（含介紹/identity 6-8 例 — 1F 補）
└── OUTPUT.md         # JSON schema + skill proposal 規則（OpenClaw L5 抽離）
```

**現有 184 行 persona.txt 拆解對應**：

| 現有區段 | 拆到哪 |
|---|---|
| L1-23 Identity & 靈魂 | **IDENTITY.md**（保留全部） |
| L24-36 你具體會什麼（9 條 bullet） | **CAPABILITIES.md**（移出！demo 預設不注入） |
| L38-55 個性原則 DO/AVOID | **STYLE.md** |
| L62-68 回答長度規則 | **STYLE.md**（刪 L65「自我介紹 2-4 句」這條） |
| L69-82 對話記憶 | **STYLE.md** |
| L83-88 環境資訊 | **STYLE.md** |
| L89-114 17 個技能表 | **CAPABILITIES.md**（lazy inject） |
| L115-118 Audio Tag 8 個 | **OUTPUT.md** |
| L119-127 JSON 輸出格式 | **OUTPUT.md** |
| L128-165 13 個 Few-shot | **EXAMPLES.md**（補到 18-22 個 — 見 1F） |
| L166-185 CapabilityContext 規則 10 條 | **OUTPUT.md** |

**關鍵設計決定**：
- **IDENTITY.md 不講「我會什麼」**，只講「我是誰、我活在哪、我的靈魂」 — 介紹預設只看這檔，自然不會列功能
- **CAPABILITIES.md lazy inject**（見 1D）— 一般聊天 LLM 看不到能力清單，不會 anchor 到工具人模式
- **OUTPUT.md 抽出 JSON schema + audio tag** — 跟人格情緒文字分開，重寫人格時不用怕碰壞 schema 規則

**1B 工時**：拆檔 + 搬段落 + 刪 L24-36 + 刪 L65 = 1.5h（不寫新內容，純機械搬）

---

**1C Conversation Mode Classifier（OpenClaw-lite L8 Hook 雛形）**

**位置**：`pawai_brain/pawai_brain/nodes/mode_classifier.py`（新建，graph 第一個 node 之後）

**5 個 mode + rule-based classifier**（不用 LLM，~20 行）：

```python
MODE_PATTERNS = {
    "safety":              r"停|停止|不要動|別動|小心|警告|危險|stop",
    "identity":            r"你是誰|你叫什麼|介紹.*自己|你誰啊|你是 AI",
    "capability_question": r"你會什麼|你會啥|有什麼功能|能做什麼|會做啥|有哪些能力",
    "action_request":      r"扭|搖|伸|懶腰|揮|過來|坐下|跳舞|走|看[你我].*OK",
    # default: chat
}

def classify_mode(user_text: str) -> str:
    for mode, pattern in MODE_PATTERNS.items():
        if re.search(pattern, user_text):
            return mode
    return "chat"
```

**重要區分**（Roy 5/9 review #1 + #2 修正）：

> **capability_context 仍每輪建立**，給 graph `skill_policy_gate` v2 仲裁用（看 `effective_status` / cooldown / blocked / needs_confirm reason）— **lazy 是 prompt-level，不是 builder-level**。
>
> **system prompt 啟動時固定載 base 4 檔**（IDENTITY+STYLE+OUTPUT+EXAMPLES），不做 per-turn 重組（`llm_decision.configure(system_prompt=...)` 是啟動時注入，per-turn 重組會破壞 prefix-cache 友善性 + 改 graph node 介面）。
>
> **CAPABILITIES.md 與 mode hint 都注入 user message conditional block**，不動 system prompt。

| mode | trigger | base system prompt | user message conditional block |
|---|---|---|---|
| `safety` | 停/小心/danger keyword | base 4 檔 | safety_gate hard rule 在 brain_node 短路（**附加防線**：LangGraph safety_gate node 若也 hit 可加防線，**不取代** brain_node/Executive 的 SafetyLayer）；保留 mode 標籤給 trace |
| `identity` | 「你是誰」「介紹自己」 | base 4 檔 | + `[mode_hint] 不要列功能清單` ；**不注入** CAPABILITIES.md；**不注入** capability_context JSON |
| `capability_question` | 「你會什麼」「有什麼功能」 | base 4 檔 | + CAPABILITIES.md + `[能力] {capability_context JSON}` |
| `action_request` | 動作 keyword + skill 詞彙 | base 4 檔 | + CAPABILITIES.md + `[能力] {capability_context JSON}`（LLM 需看可提案 skill）|
| `chat` (default) | 其他 | base 4 檔 | **不注入** CAPABILITIES.md；**不注入** capability_context JSON |

**收益**：`identity` mode 直接解死板根因；`chat` mode 拿掉 capability JSON 後 LLM 不再被「能力清單」拉回工具人；**capability_context 仍每輪建立 → skill_policy_gate v2 effective_status gate 永不退化到 v1 allowlist**（防 Roy review #1 風險）。

**1C 工時**：classifier + 5 mode pattern + unit tests (8 cases) = 1h

---

**1D Capability Lazy Injection（OpenClaw-lite L8 Hook 落地）**

**位置**：`_build_user_message()` 改造（`conversation_graph_node.py:75-126`）。**system prompt 不動**（base 啟動載 4 檔，`llm_decision.configure()` 介面維持）。

**現況**：每輪都 dump `[能力] {capabilities, limits, recent_skill_results}` JSON 到 user message

**改造**（lazy 是 prompt-level，capability_context **仍每輪建立**給 graph 用）：

```python
def _build_user_message(state) -> str:
    text = (state.get("user_text") or "").strip()
    mode = state.get("mode") or "chat"
    source = state.get("source") or "speech"

    # 1E: 修「[語音輸入]」寫死 — 改用 source 判
    label = "[語音]" if source == "speech" else "[文字]"
    parts = [f"{label} 使用者說：「{text}」"]

    # world_state（time/weather/current_speaker）— 永遠注入
    ws = state.get("world_state") or {}
    if ws.get("period") or ws.get("time"):
        line = f"[環境] 台北 {ws.get('period', '')} {ws.get('time', '')}".rstrip()
        if ws.get("weather"):
            line += f"，外面 {ws['weather']}"
        parts.append(line)
    if ws.get("current_speaker") and ws["current_speaker"] != "unknown":
        parts.append(f"[眼前的人] {ws['current_speaker']}")

    # CAPABILITIES.md 與 capability_context JSON — 僅 capability_question / action_request 注入 prompt
    # 注意：capability_context 在 graph capability_builder 仍每輪建立，這裡只控「是否暴露給 LLM」
    if mode in ("capability_question", "action_request"):
        # CAPABILITIES.md 內容（人類可讀的能力描述，從 self._capabilities_md 讀）
        if self._capabilities_md:
            parts.append("[能力描述]\n" + self._capabilities_md)

        # capability_context JSON（runtime effective_status / cooldown / limits）
        cap = state.get("capability_context") or {}
        if cap:
            compact_caps = _compact_capabilities(cap)  # 既有邏輯
            cap_payload = {
                "capabilities": compact_caps,
                "limits": list(cap.get("limits") or []),
                "recent_skill_results": list(cap.get("recent_skill_results") or []),
            }
            parts.append("[能力 runtime] " + json.dumps(cap_payload, ensure_ascii=False))

    # mode hint — 僅 identity 注入特殊 instruction
    if mode == "identity":
        parts.append("[mode_hint] 使用者問你是誰。請從性格、生活、剛剛發生的事切入，不要列功能清單，除非他追問。")

    return "\n".join(parts)
```

**capability_builder graph node 維持每輪 build**：不改 `pawai_brain/nodes/capability_builder.py`，state["capability_context"] 永遠存在 — `skill_policy_gate` v2 看 `effective_status` 仲裁不退化到 v1 allowlist（Roy review #1）。

**1D 工時**：`_build_user_message()` 改造 + 單元測試 5 mode × 2 case (with/without capability inject) = 1h（比原估 1.5h 少，因不重組 system prompt）

---

**1E Runtime Params Sanity（半小時）**

| 參數 | 現值 | 改值 | 理由 |
|---|---|---|---|
| `temperature` | 0.2 | **0.6** | OpenClaw / Anthropic chat 建議 0.7-1.0；0.6 是 PawAI 折衷（保 JSON 穩定 + 提升自然度） |
| user message label | `[語音輸入]` 寫死 | 用 `source` 判 `[語音]` vs `[文字]` | Studio 文字 vs USB mic 同樣文字，prompt 標籤要對 |
| `max_tokens` | 500 | 不改 | 已 OK |
| `max_reply_chars` | 0（無上限） | 不改 | 5/5 已修 |

**修改位置**：`pawai_conversation_graph.launch.py:40` `temperature` default + `_build_user_message()` label 邏輯

---

**1F Identity / Self-intro Few-shot 補（必做，半天）**

**現況**：persona.txt L140 唯一 self_introduce few-shot 只有「[playful] 我是 PawAI 啊，住在你家的小狗。」12 字短句，**被 L24-36 + L65「2-4 句」蓋過**，LLM 不照短句 few-shot。

**1B 已刪掉 L24-36 + L65**，需在 EXAMPLES.md 補 6-8 個介紹/identity few-shot 涵蓋情境多樣性：

- **短應答**（5-12 字，閒聊接話用）— 「你是誰」/「你叫什麼」
- **中應答**（15-25 字，第一次見的人 / 略陌生情境）— 「嗨，自我介紹一下」
- **長應答**（30-50 字，使用者明確說「介紹詳細一點」/「你會什麼」追問後）
- **情境式**（不從零介紹，從「剛剛發生的事」切入）—「你都做啥？」（剛被問過天氣後）
- **反例**（被打斷 / 第二次被問）— 「你又是誰？」（5 分鐘前已介紹過）
- **婉拒**（做不到的事）— 「幫我倒水」

完整 few-shot 文本見 `pawai_brain/personas/v1/EXAMPLES.md` Identity 段。

**Wiggle / Stretch / 婉拒 few-shot 維持**（每個可提案 skill ≥ 3 case + 負例的硬條件不變，搬到 EXAMPLES.md）。

**驗收硬條件**：每個 LLM 可提案 skill 必須有 ≥ 3 prompt eval case；identity mode 必須有 ≥ 6 case 涵蓋短/中/長/情境/反例/婉拒。

**1F 工時**：補 6-8 identity case + 9 wiggle/stretch 正例 + 3 負例 + 寫進 EXAMPLES.md = 3h

---

**1G LLM 可提案 4 桶白名單（從原 1B-1 平移）**

| 桶 | Skill | LLM 提案 | mode | 行為 |
|---|---|---|---|---|
| **Bucket 1: 直接執行** | `wave_hello` / `sit_along` / `careful_remind` / `show_status` | ✅ | execute | LLM output skill → 直接做 |
| **Bucket 2: 需 OK confirm** | `wiggle` / `stretch` | ✅ | confirm | LLM output skill → PendingConfirm → OK 手勢 → 執行 |
| **Bucket 3: 只說明不執行** | `greet_known_person` / `object_remark` / `stranger_alert` / `fallen_alert` / `nav_*` | trace_only | trace | LLM 可講「我能認識你」但不主動 emit；觸發走 face/object/pose 自動鏈 |
| **Bucket 4: 禁止** | `dance` / `follow_me` / `follow_person` / `go_to_named_place` | ❌ | n/a | LLM 提案被 skill_gate block；persona 教婉拒 |

**對 `LLM_PROPOSABLE_SKILLS`（`skill_policy_gate.py:18-27`）的影響**：
- **移除** `greet_known_person`（從 execute → trace_only；改由 face stable 觸發更合理）
- 保留 wave_hello / sit_along / show_status / careful_remind（execute）
- 保留 wiggle / stretch（confirm）
- 保留 self_introduce（trace_only — 已是 trace mode）
- nav_demo_point / approach_person 場地驗前留 trace_only（不放 Bucket 4，因 demo button 仍可觸發）

**1G 工時**：改 `LLM_PROPOSAL_EXECUTE` dict（`brain_node.py:447-456`）+ unit test = 30min

---

**1H current_speaker 注入（從原 1D 平移，半天）**

**現況**：`conversation_graph_node` 沒訂閱 `/state/perception/face`；`WorldStateSnapshot` 沒 `current_speaker` field

**實作步驟**：
1. `conversation_graph_node` 訂 `/state/perception/face`（face_perception 8Hz JSON — spec 原寫 10Hz 是誤標）
2. node 內維護 `_recent_face_identity: tuple[str, float]`，callback 更新；> 3s 視為 unknown
3. `WorldStateSnapshot` 加 `current_speaker: str` field
4. `world_state_builder()` 從 node 注入抓最近 1s identity，超時 fallback `"unknown"`
5. `_build_user_message()` 在 1D 已加 `[眼前的人] {current_speaker}`（identity != unknown 才注入）
6. EXAMPLES.md 補 current_speaker few-shot：對 Roy 俏皮快、對 grama 溫柔慢、對 unknown 禮貌試探
7. face_perception 未啟（無 topic）整段 silent omit，prompt 不夾 unknown 字串

**1H 工時**：subscription + WorldState 擴 + builder 改 + 3 case few-shot = 3h

---

**1I Gemini / DeepSeek A/B（驗證用，不換主線 — Roy 5/9 收斂）**

**主線決策**：**Demo 前主線維持 Gemini-3 Flash + temperature 0.6**。1A-1H 落地後驗證實際自然度，不把希望押在換 model。

> Roy 引用：「如果 prompt 還在強迫模型列功能，Opus / GPT-5.5 只會更認真地列一份更漂亮的功能表。」

**A/B eval（用 `tools/llm_eval/`）— 4 組對照，純驗證 1A-1F 的效果是否真實**：
- Gemini-3 + temp 0.2（1A-1H 重構**前** baseline，作為對比）
- Gemini-3 + temp 0.6（1A-1H 重構**後** demo 主線）
- DeepSeek-V4 + temp 0.6（候選驗證；若明顯更好留 demo 後再切主）
- Gemini-3 + temp 0.9（探索上限；JSON schema 是否還穩）

**評分維度**（每組 30 round）：
- persona 維持力（不講「我是 AI」、不客服腔）
- JSON schema 命中率（reply / skill / args 三欄位）
- skill 提案率（在 action_request mode 下）
- 中文自然度（人工 1-5 分）
- 介紹死板度（identity mode 下「列功能 vs 講性格」比例）
- 延遲 P50/P95

**何時切主線**：5/16 demo 後若 DeepSeek 在 5 個維度有 ≥3 個明顯贏 + 延遲不差 → 切。Demo 前不換。

**1I 工時**：eval 30 round × 4 組 = 半天（Jetson 上跑）

---

**安全邊界（OpenClaw L1+L2 對照）**

> Roy 5/9 brainstorm：「**安全做事靠執行層，不靠 LLM 自律。**」

| OpenClaw 對應 | PawAI 落地（已有 / 不變） |
|---|---|
| LLM 只提出 proposal | persona OUTPUT.md 明寫 reply + skill + args；不能直接執行 |
| Tool registry 驗證 | `skill_policy_gate` v2 驗 effective_status |
| Allow/deny | `LLM_PROPOSABLE_SKILLS` + 4 桶（1G） |
| 執行層覆蓋 | `brain_node` PendingConfirm + SafetyLayer hard rule + IE-node validate |

**LLM 任何提案不會直接控狗** — 這是 PawAI Brain 既有設計（overview.md §2「Brain 提建議，Executive 才執行」），1A-1H 不動這條線。

---

**明確不做（demo 前風險）**

- ❌ Reply Tags `<say><skill>` schema 改造（動 validator + repair + skill_gate，太深）
- ❌ 完整 OpenClaw 9 層架構（demo 前太大；只抄 L7 拆檔 + L8 lazy inject）
- ❌ Phase B PawClaw 的 `workspace/{BODY,SKILLS,SAFETY,PLACES}.md` 整套（範圍不同 — 那是給人看的；本 5/9 拆的是給 LLM 看的）
- ❌ Claude Opus 4.7 / GPT-5.5 主線替換（成本 + 延遲 + GPT-5.5 官方未列；1I 純驗證）
- ❌ 完整 OpenClaw 8 種 hook 系統化（用簡單 mode classifier 已夠）
- ❌ persona content 大改寫（保留 184 行原內容 90%，只刪 L24-36 + L65 + 拆檔搬段落 + 補 6-8 介紹 few-shot）

---

**預期收益**

| 維度 | 重構前（5/8 evening） | 重構後（1A-1H 完成） |
|---|---|---|
| 介紹死板度 | LLM 看 L24-36 列 9 條功能 bullet → 70 字「住在這個家裡的小狗。我會聽你說話...」 | identity mode 不注入 capability，LLM 從 IDENTITY.md 講性格 → 「我啊？住你家的小狗～」5-25 字 |
| 工具人感 | 每輪都看到 capability JSON → 答話偏「我可以幫你 X」 | chat mode 不注入 capability → 答話自然 |
| Persona 維持 | inline 6 行 fallback 載入時退化嚴重 | directory mode + missing file ERROR raise，不會 silent 退化 |
| 自然度（人工 1-5） | 估 2-3 分 | 估 4-4.5 分（不換 model 前提） |
| Wiggle/OK 鏈式 | LLM 不出 skill 欄位 | EXAMPLES.md 補 9 case + 1G 桶清晰 → 出 skill 欄位 |
| Studio 文字 vs 語音 prompt | 全部標 `[語音輸入]` | 1E 改 source 判 `[語音]` / `[文字]` |

---

**1A-1I 總工時**：~1.5 天（拆檔 1.5h + classifier 1h + lazy inject 1.5h + runtime 0.5h + identity few-shot 3h + 4 桶 0.5h + current_speaker 3h + eval 4h ≈ 14-15h）

可與 issue 1 ElevenLabs Spike-Mini（5/11 半天）並行，5/12 evening 前完成 1A-1H，5/13 跑 1I eval，5/14 三連跑驗。

### Wave 2 — P2 互動品質升級（5/12-5/13）

**P2-1 Attention Policy（取代原 cooldown 調整）— Roy 5/9 brainstorm 確認**

**已實證的 3 個程式碼 bug**：
1. `brain_node.py:715` `_on_object` 沒讀 distance_m（YOLO 偵測就 emit）
2. `face_identity_node.py:82` `stable_hits=3` ≈ 0.3-0.5s（路過就觸發 greet）
3. `brain_node.py:256-259` `_has_active_sequence` 只擋 SEQUENCE 不擋 SKILL（動作中還是被插嘴）

**Roy 路過比 OK 場景時序**（4 個事件互相打斷）：
```
t=0.0  face stable 3 frames → greet emit ⚠️
t=0.5  thumbs_up → PendingConfirm 撞上 greet TTS
t=1.0  OK → wiggle 疊在 greet 後
t=1.5  椅子 → object_remark 又插嘴 ⚠️
```

**設計：4 狀態 attention machine（保守版，不做 5 狀態 / 不做 gaze）**

| State | 進入條件 | 退出條件 |
|---|---|---|
| `IDLE` | 無 face ≥ 0.5s | face 出現 → NOTICED |
| `NOTICED` | face stable | distance ≤ 1.6m AND dwell ≥ 1.5s → ENGAGED；face 消失 ≥ 3s → IDLE |
| `ENGAGED` | 上條 | plan emit / speech intent → INTERACTING |
| `INTERACTING` | 任意 skill active | active_plan 結束 + 8s 安靜 → ENGAGED；face 消失 ≥ 3s → IDLE |

**Threshold（Roy 5/9 review 收斂）**：
- engaged distance：**≤ 1.6m**（不是 1.3m，奶奶/展示現場可能站較遠）
- dwell：**1.5s**（Roy 5/9 review：手勢 OK 在 NOTICED+ 就允許，拉長 dwell 只減少路過 greet 不擋走過去比 OK）
- face lost exit：**3s**
- interaction quiet：plan done + **8s**（Roy 5/9 review：讓自動物體/人臉插嘴更保守；語音 intent 任何狀態可進，不妨礙連續講第二句）

**emit gate（取代零散 guard）**：

| Skill | 允許狀態 | 額外條件 |
|---|---|---|
| `greet_known_person` | **僅 ENGAGED** | per-identity cooldown 維持 |
| `stranger_alert` | NOTICED+ | 已有 3s 累積（不變） |
| `object_remark` | **僅 ENGAGED** | **AND not active_plan AND not pending_confirm AND not tts_playing** |
| `fallen_alert` | 任何狀態 | safety override |
| gesture confirm（thumbs_up/OK→wiggle） | **NOTICED+** | 確保「走過去比 OK」不被擋 |
| speech intent | **任何狀態** | 永遠允許（語音是明確互動邀請） |

**重要修正：object_remark 不看 distance**（Roy 抓到的）
- object event payload **無 `distance_m`**（只有 bbox/confidence/color）
- demo 前簡化：**只用 engaged gate + active_plan/pending/tts not 條件**，不看距離
- demo 後：object_perception 接 depth，payload 加 `distance_m`，那時再加 distance threshold

**其他改動**
- `OBJECT_REMARK_DEDUP_S` 60 保留；**dedup key 改成 `class_name` 不含 color**（`brain_node.py:760-764`）— 避免咖啡/灰色抖動繞過
- 修 `_has_active_sequence` → 拆成 `_has_active_skill_or_sequence`（順便修 SKILL 不擋 SKILL bug）
- 不改 face_perception（distance_m 已 publish）

**改動範圍**：~120 行 brain_node + 8 unit tests，半天

**Roy 路過比 OK 跑法**：
- t=0 face stable → NOTICED（不發 greet ✅）
- t=0.5 thumbs_up → PendingConfirm（NOTICED 允許 gesture ✅）
- t=1.0 OK → wiggle → INTERACTING
- t=1.5 椅子 → state≠ENGAGED → 靜音 ✅
- 若 Roy 真的停下來 dwell ≥ 1.5s + dist ≤ 1.6m → ENGAGED → greet 才發 ✅

**明確不做**
- ❌ Gaze detection（D435 視角不穩，5/13 demo 來不及）
- ❌ Exponential backoff cooldown（per-identity 20s 已夠）
- ❌ DISENGAGING 5 狀態 + 半折 cooldown（過度工程）
- ❌ object_remark distance gate（payload 無 distance_m，demo 後再做）
- ❌ RL/HMM（rule + 三 hard threshold 解 80%）

**收益**：路過不被打招呼/物體解說打斷；動作中不被插嘴；同一椅子顏色抖動不繞過 dedup

**P2-2 ElevenLabs Spike + 雙軌路由（Roy 5/9 brainstorm 收斂，取代原 Gemini native spike）**

> **背景**：Roy 5/9 brainstorm 路線改為「B-lite — ElevenLabs 可加，TTS provider spike，不立刻替換主鏈」。原 Gemini native SDK spike 退為 conditional fallback（見 P2-2-fallback）。

**P2-2a Spike-Mini（5/11 半天，gate Wave 2 設計選擇）**

範圍：
1. 帳號：ElevenLabs Free + Pay-As-You-Go $5 top-up（不買月費）
2. Voice 候選：Voice Library 中 2 個 Mandarin / Chinese 童音或年輕女聲 + 1 個多語年輕女聲（如 Hope / Bella 類型）；具體 voice ID 在實作當天查 Voice Library 補上（spec 不硬寫 voice ID 避免 library 變動）
3. 模型：`eleven_flash_v2_5`（low-latency 多語）
4. 5 句固定文本（短/中/長/情緒/safety 各一）
5. 量測：HTTP 整段 fetch latency（**不上 Megaphone**，落地 WAV / MP3 → 本機 paplay）
6. 主觀打分：音色雪寶感 1-5、中文自然度 1-5、破音/吞字/簡體腔 ✓/✗
7. 不驗：Megaphone 整合、streaming、Go2 實機

**Voice selection criteria**（不寫 voice ID，寫條件）：
- 童趣 + 溫暖 + 不客服腔 + 中文自然
- 不做 custom voice cloning（demo 前 out of scope — 授權/素材/聲線倫理/穩定性風險）

**GO 判準**（全過才進 Spike-Real）：
1. 至少 **1 個** voice 音色 ≥ 4/5
2. 中文自然度 ≥ 4/5
3. 5 句 HTTP latency：短句 < 2s AND 長句 < 4s
4. 無明顯破音 / 吞字 / 簡體腔
5. PAYG $5 quota 對 demo 期使用量夠（10k chars 換算 demo 多輪測試足夠）

**NO-GO**：任一核心項不過 → 5/12 改做 P2-2-fallback（Gemini native SDK Mini）

**P2-2b Spike-Real（5/12 半天，僅在 Mini GO 後執行）**

- Mini 全部 + ElevenLabs WAV 走 Megaphone 4001/4003/4002 鏈
- 5 句 Go2 實機 + 5 句 USB 喇叭
- GO：Mini GO 條件 AND Go2 實機 5 句無 silent fail AND echo gate 不誤觸
- NO-GO：撤掉 ElevenLabs，5/13 場地驗保 Gemini chain + edge-tts

**P2-2-fallback Gemini native SDK spike（conditional / post-demo）**

狀態：**conditional / post-demo**
觸發條件：
- ElevenLabs Spike-Mini no-go（5/12 退而求其次），或
- demo 後要降低 ElevenLabs 成本 / 避免 vendor lock-in / 想保留 Gemini Despina 風格

範圍（觸發時）：
- 新增 `TTSProvider_GeminiNative` class，**保留** `openrouter_gemini` 不取代
- google-genai SDK，prompt prefix「請使用台灣用語的繁體中文...」
- 模型名先 confirm：官方 `gemini-2.5-flash-preview-tts` 主線；文章寫的 `gemini-3.1-flash-tts-preview` 待驗
- Jetson 10 句 smoke

**P2-3 TTS 雙軌路由（B-lite final）**

**路由規則**（`tts_callback` 入口判一次，整通結束都屬該 provider；不在 chunk 後重判）

```
1. 計算 effective_text_length(text)
   - 去除 audio tag [playful]/[excited]/...
   - 去除空白與標點
   - 計中文字 + 英文 word（中文 1 char = 1 unit、英文 1 word = 1 unit）

2. safety / stop / alert / confirm prompt → 永遠 fast lane
   （source 標籤之後 P1-1 Phase 2 可拿到；demo 前用 keyword 短路：
    `停|停止|不要動|先不要動|別動|小心|警告|危險|stop` — 中文「停」是核心 demo 指令必收）

3. effective_length <= 30 → fast lane
   effective_length > 30 → quality lane
```

**Fast lane**（短句重速度）：
```
edge-tts → Piper
```
**不繞 ElevenLabs / Gemini**（雲端 latency 漂高會破壞「馬上回」體感）。Piper 本機保底，edge-tts fail 直接退 Piper。

**Quality lane**（長句重音色）— **依 Spike-Mini 結果二選一**：

```
Mini GO（主路線）：
  ElevenLabs (eleven_flash_v2_5) → OpenRouter Gemini → edge-tts → Piper

Mini NO-GO（fallback 路線）：
  Gemini native (P2-2-fallback) / OpenRouter Gemini → edge-tts → Piper
  └─ Gemini native 通則為主軌；不通則 OpenRouter Gemini 維持原樣
```

實作者注意：Mini NO-GO 時 ElevenLabs **不要**保留在主鏈當 fallback 第二位（音色 / latency 沒過就別繞了，直接砍）。

**Provider format 跟著實際 served_by**（Roy 5/9 review #1 — High）：

`tts_node._play_on_robot(audio_data)` 目前 L1185 用 `self.config.provider` 判 MP3/WAV，**雙軌 + fallback chain 後這個假設會壞**（例如 quality lane fallback 到 Piper 出 WAV，仍被當 MP3 decode）。

設計補丁（P2-3 必須含）：

1. Provider class 都加 `output_format: AudioFormat` 屬性（`elevenlabs` / `openrouter_gemini` / `edge_tts` = MP3、`piper` = WAV）
2. `synthesize()` 回傳 `(audio_bytes, served_by_format)` tuple，或在 provider chain 跑完後 tts_callback 記下 `last_served_format`
3. `_play_on_robot()` 改吃 `served_by_format` 而非 `self.config.provider`
4. 單元測試覆蓋：fast lane fallback edge→piper、quality lane fallback elevenlabs→gemini→edge→piper，每段 assert format 對

**閾值演進**：
- demo 前：30 字（spec 預設，保互動速度）
- ElevenLabs 短句 spike 確認穩定 < 2s 後（demo 後）：可降到 20 字 或 改 source metadata routing（依 P1-1 Phase 2 進度）

**收益**：60%+ 對話走 fast lane（edge-tts 1-2s）；長句走 ElevenLabs Flash v2.5（首音目標 < 4s）取雪寶感；跳句由 P0-1 all-or-nothing fallback 永久消失

### Wave 3 — P3 加分項（5/14 之後或 demo 後）

**P3-1 Idle 待機行為（Roy 5/9 brainstorm 詳細設計）**

**靈感**：遊戲 NPC idle animation + Anki Vector「occasionally piping in」+ Tamagotchi 多重條件觸發

**業界共識**（MIT Media Lab、Anki、Tamagotchi、HRI 文獻）：
1. 多因素觸發優於純 timer（時間 AND 無 face AND 無 ENGAGED）
2. 隨機 jitter ±30-50% 避免機械感
3. 內容池要大 + LLM 動態生成 + canned fallback
4. context-bound（「我看到桌上有杯子」勝過「天氣真好」）
5. owner control（可關閉，env var / launch arg）

**設計：兩 axis state machine（attention × idle_phase）**

attention 軸（issue 4 P2-1 已設計）：`ENGAGED / RECENT / IDLE`
idle_phase 軸（新加）：`NORMAL / DUE / COOLING`

| attention | 狀態 |
|---|---|
| ENGAGED | face_visible AND distance ≤ 1.6m AND dwell ≥ 1.5s 或 voice intent < 10s |
| RECENT | 上述 10-60s 內 |
| **IDLE** | > threshold（demo 60s / home 600s） → `idle_phase=DUE` 觸發 |

**前置依賴**：必須 issue 4 P2-1 attention policy 先做完，idle 才能掛 attention=IDLE 上面。建議**同 PR 一起做**或 attention 先 merge。

**觸發策略**
- `_state.last_user_interaction_ts`：在 `_on_speech_intent` / `_on_gesture` / `_on_face`(known engaged) / `_on_text_input` 4 處更新
- threshold：`idle_threshold_s` config（demo=60, home=600, dev=20）
- cooldown：`idle_cooldown_s` config（demo=120, home=600, dev=30）
- jitter：uniform(0.7, 1.3) × cooldown
- 每小時上限：`idle_max_per_hour=4`（deque 紀錄 ts，超過跳過）
- timer：新增 `_idle_tick_timer = self.create_timer(5.0, self._tick_idle)`（5s tick 夠用）

**內容生成（混合）**
- **主線**：brain 發 `/brain/idle_request` JSON `{context: {recent_objects, time_of_day, last_user_topic}}` → `conversation_graph_node` 訂閱 → 用特殊 system prompt（「自言自語、好玩、≤15 字、不對誰說」）→ 回 `/brain/chat_candidate` 走既有 `say_canned` 路徑
- **Fallback canned**（斷網或 LLM fail）：8-12 句寫死 `brain_node._IDLE_CANNED = ["[curious] 嗯～好安靜耶", "[playful] 我剛剛看到一隻小蟲耶", ...]`，random.choice
- **避重**：deque(maxlen=5) of last said text，重複就重抽
- **語氣對齊 persona**：idle prompt 強調 audio tag 風格 + ≤ 15 字 + playful/curious/yawn 三選一

**動作白名單（idle MVP — Roy 5/9 收斂）**
```python
IDLE_SAFE_SKILLS = ["say_canned", "wave_hello"]
# 比例（weighted random）：
#   say_canned 90% (純講話最安全)
#   wave_hello 10% (短促揮手；Phase b 才開比例可調)
# 禁止：sit_along (改變姿態)、wiggle / stretch (needs_confirm)、
#       nav / approach / dance (高風險)、stop_move (safety only)
```
**全部 non-confirm**：idle 動作不走 PendingConfirm

**取消與優先級（MVP 保守版 — Roy 收斂）**

brain_node 不是 executor，**不嘗試取消已送出的 active plan**。
- `_on_speech_intent` / `_on_gesture` / `_on_face`(known engaged) callback 只**阻止下一次 idle**：
  - 更新 `last_user_interaction_ts`
  - 設 `_idle_phase = COOLING`（強制冷卻）
  - 不 cancel 進行中的 idle plan（讓它自然走完，反正只是短句 + 揮手）
- safety override：fallen / stop_move / depth_unsafe 期間 `_tick_idle` 直接 return（現有 SafetyLayer + 顯式檢查雙保險）
- 上限：`_idle_recent_ts: deque(maxlen=4)` 記過去 4 次觸發；`now - oldest < 3600` 跳過

**三階段 MVP / Studio / LLM（Roy 5/9 拆）**

**P3-1a Idle MVP（spec only，現在不實作）**
- 前置：issue 4 P2-1 attention policy 先做完
- 範圍：state field + `_tick_idle` + `_maybe_emit_idle` + `_IDLE_CANNED` 8-12 句寫死
- 動作池：90% say_canned / 10% wave_hello（**不含 sit_along**）
- 模式：**預設 `idle_mode: off`**（demo 不主動觸發；要展示時手動切）
- 不接 LLM；不嘗試 cancel active plan
- ~80 行 brain_node 改動

**P3-1b Studio toggle（demo 期想展示才開）**
- Studio header 加 idle mode selector（off / demo / home / dev）
- 前端 POST `/api/idle_mode` → gateway publish `/brain/idle_mode` (std_msgs/String) → brain 訂閱熱切換
- demo 時 Roy 手動切 `demo` 展示；切 `off` 關
- ~40 行（前端 + gateway + brain 訂閱）

**P3-1c Idle LLM 接入（demo 後）**
- 接 `/brain/idle_request` → conversation_graph idle system prompt
- ~50 行；等 Wave 0/1/2 全穩

**改動範圍（總計）**
- a: `brain_node.py` ~+80 行 + `config/idle.yaml`
- b: `pawai-studio/frontend/` + `gateway/` + `brain_node.py` 訂閱 ~+40 行
- c: `conversation_graph_node.py` ~+50 行 + brain 發 idle_request ~+15 行
- 測試 +2 unit：`test_idle_trigger.py` / `test_idle_no_emit_when_active.py`

**三模式 + 預設改 off**
```yaml
# interaction_executive/config/idle.yaml
idle_enabled: true
idle_mode: "off"   # off | demo | home | dev (Roy 5/9 改預設 off)
profiles:
  demo: {threshold_s: 60,  cooldown_s: 120, max_per_hour: 6}
  home: {threshold_s: 600, cooldown_s: 600, max_per_hour: 4}
  dev:  {threshold_s: 20,  cooldown_s: 30,  max_per_hour: 30}
  off:  {enabled: false}
```
launch arg `idle_mode:=off`（預設）；展示時 `idle_mode:=demo`；env var `PAWAI_IDLE_MODE`

**為何預設 off**（Roy 5/9 抓出）
- demo 場地老師講話 / 切畫面 / 狗剛完成技能後，60s idle 可能插話像亂講
- demo 想展示時，操作員手動切 `demo` mode 或用 P3-1b Studio toggle
- 比「預設 demo 反而擾亂」更安全

**收益**：demo 想展示時可開、不想時不擾亂；home 期使用者覺得有靈魂；產品感從工具升級為陪伴

**明確不做**
- ❌ 預設 demo mode（會在演示中插話）
- ❌ MVP 接 LLM（會跟 speech/context/reset 主鏈混）
- ❌ MVP 含 sit_along（改變姿態風險）
- ❌ MVP 嘗試 cancel active plan（brain 不是 executor）
- ❌ idle 中 nav 巡邏 / 主動拍照
- ❌ context 太重（LLM prompt 只給最近 5 物體 + 時段）

---

## 3. 不做的事（Demo 前明確 out of scope）

- ❌ GPT-Realtime / GPT-Realtime-2 主鏈替換（voice agent 架構 + WebSocket session，demo 前重構成本太高，留 demo 後研究）
- ❌ ElevenLabs custom voice cloning（授權 / 素材 / 聲線倫理 / 穩定性風險；demo 期改用 Voice Library 現成聲線）
- ❌ ElevenLabs Pro $99/mo 月費（demo 期改用 Free + PAYG $5 top-up；demo 後再評估升級）
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
- [ ] 開機 log 確認 `personas/v1` directory 載入：5 檔 verified、base 4 檔 concat、CAPABILITIES.md cached separately、`base_sha` 印出
- [ ] 「比 OK 我就扭一扭」mic 觸發 → wiggle skill 進 PendingConfirm（3/3 round）

### Wave 2 完成標誌
- [ ] 路過比 OK 連續 5 次：face greet 出現 ≤ 2 次
- [ ] 短句首音延遲 中位數 < 2s（fast lane edge-tts）
- [ ] 長句首音延遲 中位數 < 4s（quality lane ElevenLabs Mini GO 後）或 < 6s（Mini NO-GO 退 Gemini native / OpenRouter）
- [ ] 同一椅子 60s 內 dedup 不繞過（顏色抖動測試）
- [ ] ElevenLabs Spike-Mini 5 句 GO 判準達標（音色 ≥ 4/5、中文自然 ≥ 4/5、無破音）

### Wave 3 完成標誌（demo 後）

**P3-1a MVP（按 idle_mode）**
- [ ] dev mode：閒置 20s 觸發 idle utterance ≥ 1 次
- [ ] demo mode：閒置 60s 觸發 idle utterance ≥ 1 次
- [ ] home mode：閒置 600s 觸發 idle utterance ≥ 1 次
- [ ] off mode：永不觸發

**Cancel / 互動行為**
- [ ] idle 期間 user 一講話 → 阻止下一次 idle，不 cancel 進行中的 plan（保守版）
- [ ] safety event（fallen / stop / depth_unsafe）期間不觸發 idle

**P3-1b Studio toggle**
- [ ] Studio header 可切 off/demo/home/dev mode
- [ ] 切換 < 1s 內 brain 行為改變（熱切換）

**P3-1c LLM idle**
- [ ] LLM idle utterance 內容含 audio tag，≤ 15 字
- [ ] 斷網時 fallback 到 canned pool

---

## 5. 風險與待驗證假設

| 假設 | 待驗 |
|---|---|
| ElevenLabs Flash v2.5 中文 voice 有「雪寶感」候選 | 5/11 Spike-Mini 跑 2-3 voice，主觀打分 ≥ 4/5 |
| ElevenLabs HTTP fetch 短句 < 2s、長句 < 4s（Jetson → ElevenLabs API） | 5/11 Spike-Mini latency 量測 |
| ElevenLabs PAYG $5 quota 對 demo 期足夠 | 10k chars 換算多輪 demo 測試估算 |
| ElevenLabs WAV → Megaphone 4001/4003/4002 整合穩定 | 5/12 Spike-Real Go2 實機 5 句 |
| Gemini native SDK 模型名 + streaming（fallback only） | 僅 Mini NO-GO 才驗 |
| OpenCC s2twp 在 Jetson aarch64 wheel 可用 | `uv pip install opencc-python-reimplemented` 預期 OK |
| personas/v1 base 4 檔（IDENTITY+STYLE+OUTPUT+EXAMPLES）+ 條件 inject CAPABILITIES.md model 真能跟 | Gemini-3 上下文 1M tokens 不是問題；deepseek-v4-flash 待測；token 預算 base ~10KB + capability inject ~5KB ≈ 15KB system+prompt |

---

## 6. 實作順序與分支策略

主分支 `main` 不長 trunk-based；建議：

**依賴順序**（必須串行）：
1. **`fix/tts-silent-skip`** — P0-1 + P0-2，半天，merge 即上 Jetson 驗
2. **`feat/studio-full-chat`** — P1-1，1 天
3. **`feat/context-reset`** — P1-2，半天
4. **`feat/asr-tw`** — P1-3，半天
5. **`fix/persona-load`** — P1-4，半天
6. **`feat/attention-policy`** — P2-1，1 天

**並行 / gate（Roy 5/9 review #3）**：
7. **`spike/elevenlabs-tts-mini`** — P2-2a，**可與上述 P0/P1 並行**，**最晚 5/11 完成**。半天工，只動 spike 工作目錄（不動主鏈），不擋 attention-policy / Studio chat 進度。**ElevenLabs Mini 是 quality lane 決策 gate，必須在 P2-3 開工前出結果**。
8. **`spike/elevenlabs-tts-real`** — P2-2b，5/12 半天，僅 Mini GO 後執行；含 Megaphone + Go2 實機
9. **`feat/tts-dual-route`** — P2-3，半天，**依 P2-2a 結果決定 quality lane 主軌**：
   - Mini GO → 主軌 ElevenLabs，鏈 `ElevenLabs → OpenRouter Gemini → edge-tts → Piper`
   - Mini NO-GO → 退而做 `spike/gemini-native-tts`，主軌改 Gemini native，鏈 `Gemini native → OpenRouter Gemini → edge-tts → Piper`（**不**在 Mini NO-GO 時把 ElevenLabs 留鏈中）
   - P2-3 必須含 audio_format / served_by 重構（見 P2-3 Provider format 補丁）
9. **`feat/idle-mode`** — P3-1，1-2 天

每支 PR 都跑：`pytest 61/61` + Jetson colcon build + 手動 demo flow 5 句驗。

---

## 7. 預期 demo 改善

| 維度 | Before (5/8 evening) | After (Wave 0+1+2 完成) |
|---|---|---|
| 互動完整度 | 45-55% | 70-80% |
| TTS 跳句 | 偶發 | 0% |
| 短句首音延遲（safety/confirm/短答） | 6-7s 全鏈 | < 2s（fast lane edge-tts） |
| 長句首音延遲（情緒句/故事） | 6-7s | < 4s（quality lane ElevenLabs Flash v2.5，Mini GO 後） |
| Studio 對話可觀測性 | 30%（只 pending request） | 100% |
| Persona 自然度 | 模板感 | 完整 persona + 主動鏈式 |
| 路過比 OK 被打斷 | 有 | 無（engaged-state） |
| 重整 context 混淆 | 有 | 無 |
| ASR 簡繁 | 簡體 | 繁體 |

Idle 行為（Wave 3）為 demo 後加分項，不列入 demo 驗收。
