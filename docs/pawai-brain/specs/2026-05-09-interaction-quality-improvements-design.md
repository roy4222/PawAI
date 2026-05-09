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

**P1-2 Context reset on refresh**
- **`conversation_graph_node`**（不是 brain_node）訂 `/brain/reset_context` topic（std_msgs/Empty）→ 呼叫 `self._memory.clear()` + 清 `_seen_sessions`
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
