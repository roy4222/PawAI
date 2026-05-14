# Demo 前凍結 Backlog

> **凍結期間**：2026-05-11 起 → 5/18 demo 後解鎖
> **目的**：Demo 前不再加新功能。所有「願望」全鎖在這份清單，5/18 後再評估。
> **唯一例外**：見下方「破例規則」。

---

## 為什麼存在

過去 51 sessions 的摩擦分析顯示，Demo 前最大風險不是「技術做不到」，而是 **demo 前一直加新東西** — 加完沒時間整合測試，反而把原本穩定的功能弄壞。

這份檔案唯一存在的意義：**下次手癢時 `git grep` 一下被擋住**。

---

## 凍結清單（demo 前不要動）

### LLM / Persona

- [ ] **persona 再改** — N2 已凍結。除非 5/13 後 Roy 親耳實機驗收 N2 真的還是「太表層」，才開 N3。
- [ ] **LangGraph 重構** — `llm_bridge_node` (1100 行) 拆 chat_agent。5/16 demo 後再做。
- [ ] **per-session memory** — 跨輪記憶。現有 deque(maxlen=10) 已夠 demo 用。
- [ ] **anthropic/claude-opus-4.7 燒錢路徑** — 已 freeze 在 offline only。

### 前端 / Studio

- [ ] **Model switcher UI 按鈕** — 切 gpt-mini / gemini / qwen-7b / opus / rule。Demo 評審不會點。要切用 `PAWAI_LLM_MODEL=... bash scripts/start_full_demo_tmux.sh` env override。
- [ ] **Studio + Foxglove polish** — 樣式 / 排版。功能可用即可。
- [ ] **idle animation UI** — `idle_*` params default off，demo 不啟用。

### 手勢

- [ ] **circle 畫圈 → dance** — 動態手勢加分項，demo 後再做。
- [ ] **come_here 勾手 → 跟隨** — 跟隨模式本身就在凍結清單，動態手勢更不該動。
- [ ] **自定義手勢學習** — 完全未啟動。

### 姿勢

- [ ] **akimbo 雙手叉腰 TTS + 動作綁定** — 加分項，enum 已收，TTS/motion 不做。
- [ ] **knee_kneel 單膝跪地 TTS + 動作綁定** — 同上。
- [ ] **crouch 蹲下 / bend 彎腰 互動動作** — 加分項。`/event/pose_detected` 仍會發，但 demo 不靠這個。
- [ ] **跌倒 scale-invariant ratio 調參** — `pose_classifier` 已有，threshold 細調凍結。

### 物體

- [ ] **yolov8n A/B 切換** — 主線 yolo26n + HSV 12 色 schema v2.5 已凍結。
- [ ] **物體 ↔ LLM context inject** — 若劇本寫到「PawAI 主動講看到紅杯子」反推出真缺口，才開 N3 hotfix。**預設凍結**。

### TTS

- [ ] **TTS chain v2 spec 重構** — 已凍結。
- [ ] **ElevenLabs / GPT-Realtime 替換** — 凍結，現有 openrouter_gemini Despina 已過關。
- [ ] **Piper 加入 fallback chain** — 候選 hotfix。若劇本驗證階段發現雲端網路風險高，才開 N3。**預設凍結**。

### Nav

- [ ] **動態避障繞行（自動 detour）** — Stage 2 L3 已 FAIL，demo 走「融合進 costmap 安全停車」話術，不宣稱自動繞開。
- [ ] **跟隨模式** — 完全未啟動。
- [ ] **自主巡邏** — 完全未啟動。
- [ ] **自主尋物閉環** — 完全未啟動。

### 其他

- [ ] **新增任何 SkillContract** — 除非劇本反推出真缺口（如 `demo_opener` / `say_failure_explain`），否則不加。
- [ ] **CI / 測試套件擴充** — demo 後再做。
- [ ] **文件網站樣式微調** — 黃/陳負責，但 demo 前不要拉 Roy 進來幫忙。

---

## 破例規則

要動上面任何一項 → 必須：

1. **`git tag brain-hotfix-N3+`**（按序：N3 / N4 / ...）
2. **在此檔下方「Hotfix Justification Log」加一筆**，寫清楚：
   - 動哪一項
   - 為什麼必須現在動（不能等 5/18）
   - 預估工時
   - 風險（會不會弄壞已穩定的東西）
3. **必須在 N3 commit 前先實機 smoke 原本穩定的功能**（避免 hotfix 弄壞 baseline）

---

## Hotfix Justification Log

> 格式：日期 / tag / 項目 / 理由 / 工時 / smoke 結果

### 2026-05-11 / `brain-hotfix-N3` / Demo-host harness 補強（Task A+B+C）

**動了什麼**：
- **Task A**：訂 `/event/object_detected` → `WorldStateSnapshot.recent_objects` → `_build_user_message` 注入 `[最近看到] 紅色的杯子（5 秒前）`。Demo §[2:30] 紅杯子段 LLM 才能即興 contextual 講話。
- **Task B**：訂 `/brain/demo_segment` → `_demo_session_state` (with lock) → `capability_builder.demo_session_provider` → prompt 注入 `[demo] 段:gesture 已演:wiggle 建議下一步:stretch, wave`。PawAI 才能 demo-host 引導而不重複拋同一個 skill。
- **Task C**：`response_repair` 加 rule-only verifier — reply 太短 / capability_question 沒提具體 skill（**動態取自 capability_context.capabilities，不 hardcode**）/ demo segment 沒結尾邀請 → trace `stage="verifier" status="warn"`。**永不擋 output**，純觀測供後續 persona 調整。

**為什麼必須現在動（不能等 5/18）**：
- Demo §[2:30] 紅杯子段在 demo_script.md §4 已標為「劇本反推真缺口」P0 — 沒這個 LLM 講不出「紅色的杯子，是新的嗎？」，紅杯子段直接破功。
- demo-host 引導是整場 demo 「PawAI 不是 chatbot」的核心 — N2 persona 寫了但 brain 不知道演到哪，引導會打架。
- Reply verifier 是 Osmani「every mistake becomes a rule」的入口 — 沒 trace 留底，Roy 無從調 persona。

**工時**：~4h（含 33 個新 test，pre-deploy 全綠）

**風險評估**：
- LangGraph 拓樸不動（11 nodes 不變）
- Model / TTS / nav 完全不碰
- `_placeholder_session` 保留為 fallback，未配置 provider 不破舊行為
- Lock 保 ROS callback × graph worker race
- Skill name 動態從 capability_context 取，不耦合 SkillContract import
- 回退方案：`git revert HEAD` 退回 N2 baseline，gpt-5.4-mini + N2 persona 仍可用

**Smoke 結果**：待 5/13 早 Jetson 跑 Smoke A/B/C（見 `docs/runbook/demo_script.md` §4 + plan `to-view-synthetic-sun.md`）

**Schema 變更**：
- `docs/contracts/interaction_contract.md`：trace stage enum 加 `verifier`、status enum 加 `warn`
- `pawai-studio/frontend/contracts/types.ts`：同步 union 加 `verifier` / `warn`
- `pawai_brain/pawai_brain/schemas.py`：TracePayload comment 補列

---

### 2026-05-11 / `brain-hotfix-N3.1` / demo_segment hardening + TS union sync (`80ec823`)

review post-N3 抓到：`_on_demo_segment` 對 truthy 非 list (`shown_skills=1`) 會 TypeError 殺 ROS callback；frontend types `status` union 缺 `hit`/`needs_confirm`/`demo_guide`（後端早就在發）。  
修：抽 `_sanitize_str_list` helper、`types.ts` 補齊 3 個 status。+ 6 regression test。225 tests green。

---

### 2026-05-11 / `brain-hotfix-N4` / self_intro_request scaffold (`afd3fcd` + `f9988bd` N4.1)

**動了什麼**：
- mode_classifier 加 `self_intro_request` mode（priority > identity）— 識別「自我介紹」「介紹一下你自己」「跟教授 demo」等
- `[intro_scaffold]` 5 段提示注入：身份 + 專題 + 能力概覽 + grounded 觀察 + 拋下一步
- `self_intro_request` 也注入 capability_context（從 17 skill 挑 2-3 個講）
- wave_hello SAY「嗨！」→「嗨～我是 PawAI！很高興認識你～」

**為什麼必須現在動**：5/11 night live 測 PawAI 回「介紹一下你自己」只說「我是 PawAI，住在這個家裡的小狗」— 完全沒講專題、能力、硬體。identity mode 的 mode_hint 寫「不要列功能清單」，逼 LLM 走極簡，跟 demo-host 要的相反。

**N4.1 review fix**：scaffold 含「不是聊天機器人」「不要說成長者陪伴」這類負面 framing 會 prime LLM 反向 leak。改正向描述（具身互動 AI / 多模態感知融合）+ assert 禁詞 NOT in msg。

**工時**：~2h（N4 1h + N4.1 1h，含 12+8 test）。245 tests green。

---

### 2026-05-11 / `brain-hotfix-N5` / scene understanding (`631b98b` + `0f13d98` N5.1)

**動了什麼**：
- 三種 perception 三種 cache 語意：
  - **Object**: recent_window 30s + class-dedup + **person filter** + **color_conf < 0.6 → None**
  - **Pose**: last_known，**永不過期** + age_s
  - **Gesture**: recent_window 8s + dedup by (gesture, hand) within 5s
- `_format_pose_line` age 三段保守措辭：< 15s「目前姿勢」/ 15-120s「最近姿勢」/ > 120s「歷史姿勢…需要再確認」
- mode_classifier 加 `scene_query`（看到什麼 / 我在幹嘛 / 猜猜我），priority > identity
- `[scene_hint]` prompt 注入「整合 [眼前的人]、姿勢、手勢、最近看到的物體做 1-3 句場景描述」（正向 framing，物件名中文）
- spec 落地：`docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md`

**N5.1 review fix**：scene_query regex 對「你覺得我」「你猜我」太貪，吃 capability_question。收窄 + 補「猜猜我在做什麼」（不需「你」前綴）+ 反例 test（你覺得我該展示什麼功能 → capability_question）。

**為什麼必須現在動**：5/11 demo log Roy 問「你看到什麼」reply 只列物體，沒整合姿勢/手勢/人臉。「我現在在幹嘛」reply「站著或坐著跟我聊天」hedge — 因為 pose 沒進 prompt。

**工時**：~3h（N5 2h + N5.1 1h，含 28 test）。280 tests green。

---

### 2026-05-11 / `brain-hotfix-N6` / demo polish (`d4c4236` + `eb422e9` N6.1)

**動了什麼**：
- **conversation-active gate**：`_last_chat_input_ts` 在 speech/text input 時 update；`_on_gesture` 對 wave/fist/index 在 30s 內擋住（palm safety 例外）
- **fist/index motion 對齊規格**：enter_mute_mode 加 stand_down + SAY「進入靜音模式，我先坐下」；enter_listen_mode 加 balance_stand + SAY「我站起來認真聽你說」
- **sit_along SAY**：「我也趴下來陪你」→「會不會太累，我陪你坐一下」（user 規格命中）
- **`[whispers]` / `[sighs]` audio tag normalize**：validator 端 `normalize_audio_tags` → `[curious]`；skill SAY 模板（system_pause / stretch）+ brain_node IDLE_CANNED + EXAMPLES.md (6 處) + OUTPUT.md allowed tag list 全清

**N6.1 review fix**：N6 新加 gate tests assert 錯欄位（`_latest_plan` 不存在 fixture）+ gesture_gate 抑制只發 ROS logger 不發 trace（Studio Trace Drawer 看不到）。fix：改用 `_drain_proposals` pattern；suppression 加 `_emit_trace(stage="gesture_gate", status="blocked", detail="<gesture>:conversation_active_<s>s")`；contract.md + types.ts 加 `gesture_gate` stage。

**為什麼必須現在動**：5/11 demo log 對話中段冒「[excited] 嗨～我是 PawAI！」「[curious] 我在聽」干擾流程；故事段 `[whispers]` 整段語氣鎖；fist/index SAY 沒對齊 demo 規格。

**工時**：~3h（N6 2h + N6.1 1h，含 13+7 test）。489 tests green.

---

### 2026-05-11 / `brain-hotfix-N7` / vision sensitivity + lane self-heal (`717a24a` + `8d81dd9`)

**動了什麼**（vision_perception 端，明確 user request 鬆綁）：
- `vision_perception.yaml`：`gesture_vote_frames` 3→5（穩定 majority）+ `gesture_stable_s` 0.5→0.3（hold 縮短）— Net 5 幀 @ 20Hz ≈ 250ms vote + 300ms hold = ~550ms 反應，修 fist 不認
- `pose_classifier.py` fallen 閾值鬆綁（user：「身體接觸地面附近就要觸發」）：
  - `vertical_ratio` 上界 0.4→0.45（蜷曲跌倒、彎膝側躺常落 0.35-0.45）
  - `ankle_on_floor` Y 比 0.7→0.6（遠景接得到）
- `trunk_angle > 60°` 不動（深鞠躬 FP 風險高，deferred）
- start.sh 加 self-heal：probe Jetson tmux + local next dev → 自動 cleanup → preflight

**為什麼必須現在動**：fist 完全沒觸發（user 5/11 night 反饋）；跌倒太嚴只認標準直挺平躺；lane 重啟流程手動 cleanup 太麻煩（每次都要打兩條命令）。

**Vision rule 例外**：`/home/roy422/newLife/elder_and_dog/.claude/rules/vision-perception.md` 寫「fallen 閾值不要動」— user 5/11 明示要動，本 hotfix 列入例外紀錄。trunk_angle 60° 守住，只放寬 vertical_ratio + ankle，最低面積擾動。

**工時**：~1.5h（含 vision 36 tests + 4 regression）

---

### 2026-05-11 / `brain-hotfix-N8` / demo polish 二修 (`53cbdae`)

**動了什麼**（5/11 night live demo 後 user 抓到 3 個 bug）：
- **Bug #1 gate 失效**：對話中段 wave/fist/index 還是觸發 skill。加 `tts_playing` 第二層 gate — PawAI 講話時也擋。理由：可能 Jetson stale build 或 race；belt-and-suspenders 防呆
- **Bug #2 「跟教授打招呼」**：被 self_intro_request regex 吃進去走完整自介。從 alternative 拿掉 `打.*招呼`/`問好`，只剩「介紹」動詞 → 改走 chat → wave_hello path
- **Bug #3 stretch 不等 OK 直接 fire**：PendingConfirm `request_confirm` 加 `current_gesture` 參數 + `_must_release_ok` flag — user 手已在 OK 位置時，等 user 放開（轉非 OK）後再次 OK 才算。Bug #3 真因：user 自然手勢被 classifier 誤判為 OK，0.5s stable window 太鬆

**為什麼必須現在動**：B-lite 紀律 — user 明示這 3 個是 demo killer（中段插話 + 嘴上說等 OK 身體直接動），不修就破「PawAI 有控制感」印象。30-case checklist 跑完只會更多症狀，不會改變要修這 3 個的事實。

**工時**：~1h（含 6 PendingConfirm release-first test + 1 mode_classifier 反向 case）。495 tests green。

---

### 2026-05-11 / docs 跟著落地

- `docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md`（`2b7a981`）— N5 事後設計文件
- `docs/runbook/demo_script.md`（`e6d667a`）— 5 分鐘 happy path 劇本
- `docs/runbook/demo-30-case-checklist.md`（`0c030a1`）— 30 case acceptance + N8 後 8 case regression（`85ac682`）

---

## 5/18 解鎖後排序

Demo 過後優先評估的項目（不是承諾要做，只是排序參考）：

1. LangGraph 重構（架構債）
2. 物體 ↔ LLM context inject（互動深度）
3. TTS Piper fallback chain（穩定性）
4. Dynamic gesture（circle / wave / come_here）
5. 動態避障繞行（Nav L3）
6. Model switcher UI（debug 工具）

---

## 相關文件

- `docs/runbook/demo_script.md` — 5 分鐘劇本（凍結後寫，劇本反推真缺口）
- `references/project-status.md` — 各模組當前狀態
- `docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md` — 5/9 spec（含 demo-frozen-backlog 上游需求）
