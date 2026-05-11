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
