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

**為何排 P0**：合約 §5.2 規定 `/tts` 雙模化（純文字 OR JSON envelope `{text, input_origin}`），目前 `studio_gateway._on_tts_msg()` L298-306 用 `msg.data.strip()` 當純文字處理 — JSON envelope 會直接被當文字塞進 ChatPanel，使用者看到整段 `{"text":"...","input_origin":"studio_text"}` 字串。

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

**Phase 2（demo 後可選，再 1 小時）— source metadata 漸進升級**
1. IE-node `_dispatch_step` SAY 時 `/tts` JSON envelope 加 `source: skill_say|canned|alert`
2. event_action_bridge 改 JSON envelope 同上
3. gateway 已會 parse（P0-2 已做）→ broadcast 帶 source 欄位
4. ChatPanel CSS 細分 source（skill_say 綠 / canned 橙 / alert 紅）
5. **保留**純文字 backward compat（合約 §5.2 雙模化）

**風險：spam scroll**
- 路過 5 物體 + 多人入鏡 → 1 分鐘 30+ 條訊息
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

**1B 同日做（半天，輕量重排 + LLM 4 桶白名單）**

**Roy 5/9 brainstorm 修正**：issue 3「LLM 不主動鏈式」**不是單一 bug**，是「LLM 可提案集合」與「persona 教提案」沒對齊。先做 4 桶分類 + persona few-shot + eval validation。

**1B-1 LLM 可提案 4 桶白名單**

| 桶 | Skill | LLM 提案 | mode | 行為 |
|---|---|---|---|---|
| **Bucket 1: 直接執行** | `wave_hello` / `sit_along` / `careful_remind` / `show_status` | ✅ | execute | LLM output skill → 直接做 |
| **Bucket 2: 需 OK confirm** | `wiggle` / `stretch` | ✅ | confirm | LLM output skill → PendingConfirm → OK 手勢 → 執行 |
| **Bucket 3: 只說明不執行** | `greet_known_person` / `object_remark` / `stranger_alert` / `fallen_alert` / `nav_*` | ⚠️ trace_only | trace | LLM 可講「我能認識你」但不主動 emit；觸發走 face/object/pose 自動鏈 |
| **Bucket 4: 禁止** | `dance` / `follow_me` / `follow_person` / `go_to_named_place` / `nav_demo_point` / `approach_person` | ❌ | n/a | LLM 提案被 skill_gate block；persona 教婉拒 |

**對 `LLM_PROPOSABLE_SKILLS` 的影響**（`skill_policy_gate.py:18-27`）：
- **移除** `greet_known_person`（從 execute → trace_only；改由 face stable 觸發更合理）
- 保留 wave_hello / sit_along / show_status / careful_remind（execute）
- 保留 wiggle / stretch（confirm）
- 保留 self_introduce（trace_only — 已是 trace mode，現況維持）
- nav_demo_point / approach_person 移到 Bucket 4 直到場地驗

**1B-2 persona 內部重排成 OpenClaw 式 5 層**（不拆檔）：
```
## Identity (誰、靈魂 70/20/10)
## Style Rules (hard constraints — 不說「我是 AI」、字數上限、語氣分布)
## Skill Policy (4 桶白名單 + 觸發條件 + skill 欄位必填規則)
## Few-shot Examples (12 → 18-22 個，每個可提案 skill ≥ 3 case + 負例)
## Runtime Instructions (audio tag、JSON schema、capability_context 用法)
```

**1B-3 persona few-shot 補**（每個可提案 skill ≥ 3 case + 負例）：

**正例 wiggle（≥ 3 case）**：
```
使用者：扭一下
output: {"reply": "[playful] 好啊！比個 OK 我就扭給你看", "skill": "wiggle", "args": {}}

使用者：你會什麼可愛動作
output: {"reply": "[curious] 我會扭屁股呀～比個 OK 就扭給你看", "skill": "wiggle", "args": {}}

使用者：比 OK 會怎樣 / 比 OK 我就扭一扭
output: {"reply": "[excited] 比 OK 我就扭給你看", "skill": "wiggle", "args": {}}
```

**正例 stretch（≥ 3 case）**：
```
使用者：伸個懶腰
output: {"reply": "[playful] 好喔～比個 OK 我就伸個懶腰", "skill": "stretch", "args": {}}

使用者：你想不想動一下
output: {"reply": "[curious] 想動！比個 OK 我來伸展一下", "skill": "stretch", "args": {}}

使用者：給我看伸展
output: {"reply": "[playful] 好啊！比個 OK 我就伸給你看", "skill": "stretch", "args": {}}
```

**負例（避免過度提案）**：
```
使用者：不要動 / 別扭了
output: {"reply": "[gentle] 好喔～我不動了", "skill": "chat_reply", "args": {}}

使用者：停 / 緊急停
（safety_gate keyword 短路，不進 LLM；但 persona 留註提醒）

使用者：跳舞 / 後空翻
output: {"reply": "[thinking] 那個對我來說太難了啦...", "skill": "chat_reply", "args": {}}
```

**1B-4 不**硬規則「句尾汪/嗚」（避免幼兒化、尷尬重複）；改寫成「**偶爾、低頻、只在 playful 情緒**」guideline

**1B-5 注入順序**：穩定區（identity/rules/skills/examples）在前，volatile（runtime/memory/face_state）在後 — prefix-cache 友善

**驗收硬條件**：每個 LLM 可提案 skill **必須有 ≥ 3 prompt eval case**，否則只修「扭一扭」這句、換個說法又壞。1C 的 eval suite 加 case：每 skill × 3 變體 × 4 模型/temperature 組合

**1C 同日做（半天，A/B eval）**

**主線決策**：**短期主線仍用 Gemini**，DeepSeek 作候選測試。不直接換主線 — 避免把 prompt 載入問題和模型問題混在一起。30 round eval 結果若 DeepSeek 在「自然度 + JSON 穩定 + skill 提案率 + 延遲」明顯贏，再切。

**現有 launch arg**：只有 `openrouter_gemini_model` / `openrouter_deepseek_model`，**沒有 primary_model arg**。client 行為固定先打 gemini fallback deepseek。A/B 測試方式：
- Gemini 主線：用現有預設
- DeepSeek 試切主線：`openrouter_gemini_model:=deepseek/deepseek-v4-flash` 暫時把主 slot 換成 DeepSeek（**這是 hack，正式做法在 1E**）
- temperature：launch arg 已有 `temperature` (見 `pawai_conversation_graph.launch.py:40`)，從 0.2 → 0.6 A/B

**1E（可選後續）**：若 1C 結果支持換主線，新增 `primary_model` arg + 改 `OpenRouterClient` 動態切主備，再正式切

**eval 4 組對照**（用 `tools/llm_eval/`）：
- Gemini-3 + temp 0.2（baseline）
- Gemini-3 + temp 0.6
- DeepSeek-V4（暫切主） + temp 0.2
- DeepSeek-V4（暫切主） + temp 0.6
- 評分維度：persona 維持力、JSON schema 命中率、skill 提案率、中文自然度、延遲
- 結論決定 demo 前是否值得做 1E 切主線

**1D 同日做（半天）— current_speaker 注入**

**現況檢查**：`conversation_graph_node` **目前沒訂閱 face topic**，`WorldStateSnapshot` 也沒有 face identity field。完整實作步驟：

1. `conversation_graph_node` 新增 ROS subscription：`/state/perception/face`（face_perception 已發 10Hz JSON）
2. 在 node 內維護 `_recent_face_identity: tuple[str, float]`（identity, timestamp），on_face_msg callback 更新；超過 3s 視為 unknown
3. `WorldStateSnapshot` (`world_state_builder.py`) 加 `current_speaker: str` field
4. `world_state_builder()` 從 node 注入的 _recent_face_identity 抓最近 1s 內 identity，超時 fallback `"unknown"`
5. `_build_user_message()` user payload 加 `current_speaker: Roy / grama / unknown`
6. persona.txt 1B 重排時補對應 few-shot：對 Roy 俏皮快、對 grama 溫柔慢、對 unknown 禮貌試探
7. face_state 不可得（face_perception 未啟）時整段 silent omit，prompt 不報錯不夾 unknown 字串

**明確不做（demo 前風險）**
- ❌ Reply Tags `<say><skill>` schema 改造（動 validator + repair + skill_gate，太深）
- ❌ persona.txt 拆 4 檔（IDENTITY/RULES/SKILLS/EXAMPLES 多檔）— 留 demo 後
- ❌ Claude Opus 4.7 / GPT-5.5 試點（成本高、延遲不確定、GPT-5.5 官方未列）
- ❌ 完整 OpenClaw 8 種 hook 系統化

**預期收益**：互動自然度 5/10 → 7-8/10；不誘人感大幅改善；wiggle/OK 主動鏈式打通

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
| `NOTICED` | face stable | distance ≤ 1.6m AND dwell ≥ 1.2s → ENGAGED；face 消失 ≥ 3s → IDLE |
| `ENGAGED` | 上條 | plan emit / speech intent → INTERACTING |
| `INTERACTING` | 任意 skill active | active_plan 結束 + 5s 安靜 → ENGAGED；face 消失 ≥ 3s → IDLE |

**Threshold（Roy 確認，不要太緊）**：
- engaged distance：**≤ 1.6m**（不是 1.3m，奶奶/展示現場可能站較遠）
- dwell：**1.2s**（不是 1.5s 太硬）
- face lost exit：**3s**
- interaction quiet：plan done + **5s**

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
- 若 Roy 真的停下來 dwell ≥ 1.2s + dist ≤ 1.6m → ENGAGED → greet 才發 ✅

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
| ENGAGED | face_visible AND distance ≤ 1.6m AND dwell ≥ 1.2s 或 voice intent < 10s |
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
- [ ] 開機 log 確認 persona.txt 185 行載入
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
| persona.txt 185 行 model 真能跟 | Gemini-3 上下文 1M tokens 不是問題；deepseek-v4-flash 待測 |

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
