# PawAI Demo 測試功能清單 v2

> **用途:** 今日 fail-map / 5/13–14 場地測試 / 5/18 Demo 前驗收
> **建議使用方式:** 一項一項勾，失敗記錄原因、trace/topic、是否可重現
> **撰寫日期:** 2026/05/07
> **最後更新:** 2026/05/08 morning（A-G 八階段在家驗收，發現 depth_safety 漏啟 + confirm wiring 失效）
> **標記:** `[x] PASS` / `FAIL→A:BLOCKER` / `FAIL→B:OBS` / `SKIP→C` / `[ ]` 待測

---

## 5/8 morning 完成度概覽（在家測試）

| 區塊 | 完成度 | 核心驗證 |
|---|---|---|
| §1 啟動與部署 | 🟢 PASS（5/5） | 19 nodes、single chat publisher、openrouter=on、Brain/Perception topics、Gateway :8080 ✓；**但啟動腳本漏 `depth_safety_node`** |
| §2.1 ASR→Brain→TTS | 🟢 PASS（5/5） | 你好/你可以做什麼/我是 Roy→記住名字/睡前故事 |
| §2.2 Stop / Safety | 🟢 PASS（2/2） | 動作中說「停」/「stop」→ wave_hello / sit_along **preempted** + safety_path |
| §2.3 TTS 長句 | 🟢 PASS | 睡前故事 5 句連貫，audio tag `[whispers]` 正確渲染 |
| §2.4 Fallback | 🟢 鏈路通 | RuleBrain rescue 在 ASR 不穩時觸發（[curious] 沒聽清楚） |
| §3.1 motion skills | 🟢 PASS（4/4） | wave_hello (api 1016)、careful_remind、show_status、sit_along (api 1009) 全動 |
| §3.2 needs_confirm | 🔴 **FAIL→A:BLOCKER** | F1+F2 needs_confirm wiggle 正確，**F3 OK 手勢沒 wire 到 confirm**；wave/face auto-rule 蓋掉流程 |
| §3.3 self_introduce | 🟡 部分 | 語音 trace_only PASS（0 motion + accepted_trace_only）；Studio button **不存在** SKIP |
| §3.4 Skill 合法性 | 🟢 PASS（3/3） | 後空翻/爬樓梯/跳舞 全部 LLM persona 婉拒，0 motion api_id |
| §4 誤觸抑制 | 🟢 沿用 | stranger_alert / object_remark say-only 不打斷 motion 與長句 TTS |
| §6.1 Studio 對話顯示 | 🟢 沿用 | ChatPanel 顯示語音輸入 + Gemini reply + audio tag |
| §6.2 Brain Trace | 🟢 PASS | safety_gate hit / accepted / accepted_trace_only / needs_confirm chip 全可見 |
| §5 五功能個別 | ⏸ 待 5/13 場地 | 人臉/手勢/姿勢/物體成功率 |
| §7 Demo 3 連跑 | ⏸ 待 5/14 SL201 | 10 步腳本 + Hard gate |
| §8 導航避障 | ⏸ 待 5/13 場地 | — |
| §9 硬體穩定 | ⏸ 待 5/13 場地 | 30/60 min run + 供電 |

---

## 🔴 5/8 morning 必修 fix 清單

> 詳細 plan：`docs/pawai-brain/plans/2026-05-08-fix-depth-confirm-tts.md`（待寫）
> Fail-map 條目：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`（待補 [#A1.3] / [#F-confirm] / [#TTS-gemini]）

### A:BLOCKER（必修，影響 Demo S6 + motion 全鏈）

1. **[#A1.3] `depth_safety_node` 沒在 `start_full_demo_tmux.sh` 啟動**
   - 症狀：`/capability/depth_clear` publisher 0 個，default false → 所有 MOTION step `blocked_by_safety: depth_not_clear_for_motion`
   - 影響：5/8 morning 開測時 wave_hello + sit_along 全部 block；LLM 收到 `blocked_by_safety` 後幻覺說「前面空間不夠」
   - 熱修：`tmux new-window -t demo -n depth_safety 'ros2 run go2_robot_sdk depth_safety_node'` → publish 開始 → motion 解禁
   - 永久修：`scripts/start_full_demo_tmux.sh` 加 `depth_safety` window
   - 重現性：YES（每次 fresh start）

2. **[#F-confirm] OK 手勢沒 wire 到 PendingConfirm wiggle/stretch**
   - 症狀：F1+F2 needs_confirm wiggle 正確進入；F3 比 OK（confidence=1.0）後 **wiggle 0 個 plan accepted**，反而觸發 wave_hello x14、greet_known_person x12
   - 推測 root cause：
     a. PendingConfirm state 沒監聽 `/event/gesture_detected[ok]`，或監聽路徑被 background auto-rule 搶先消費
     b. brain_node 仍有 `wave gesture → wave_hello` 自動 rule（memory 寫 3/23 已移除，但 14 次 plan 顯示仍在跑）
     c. face 入鏡 → greet_known_person 12 次也持續觸發，覆蓋 confirm
   - 影響：Demo S6 wiggle confirm 流程完全跑不起來
   - 重現性：YES

### P1（OBS 升級，使用者明確要求）

3. **[#TTS-gemini] 麥克風語音輸入路徑想換成 `google/gemini-3.1-flash-tts-preview`**
   - 現況：Studio chat → Gemini Despina TTS；麥克風 → edge_tts
   - 用戶 5/8 morning 要求：「我還是想用 google/gemini-3.1-flash-tts-preview 當 main 講話的」
   - 影響：edge_tts 雖然延遲低（1-2s）但音色不夠 persona；Demo 想統一走 Gemini Flash TTS preview
   - 修法：擴展 5/7 commit 10829ca 的 per-message TTS routing，把 mic 路徑也指到 Gemini

### B:OBS（記錄不修）

4. **[#G-residual] F+G 階段累積 4 次 api_id=1016**
   - 來源：F3+F4 confirm 失敗時 OK 手勢被誤判成 wave，自動觸發 wave_hello
   - 屬於 [#F-confirm] 的衍生症狀，修了 #F-confirm 應自然消失

5. **[#sit_along] sit_along 無 auto stand-up step**
   - by design：contract steps=[say, sit motion]，狗坐下後保持坐姿
   - 不修（demo 設計就是「陪坐」）

### 5/8 morning 程式碼修法（Jetson 整合驗證 5/8 evening）
- **[#A1.3]** `scripts/start_full_demo_tmux.sh` 加 depth_safety window（[10/13]）→ ✅ Jetson 驗證 `Publisher count: 1`
- **[#F-confirm] 2a** `pending_confirm.py:155-162` 非 OK gesture stays PENDING → ✅ 不再 different_gesture cancel
- **[#F-confirm] 2b** `brain_node.py:621/672/684` _on_face / _on_pose 三處加 PENDING guard → ⚠️ 部分驗證（PENDING 期間仍見 6 次 greet_known_person，但都在 timeout 後窗外發出）
- **[#TTS-gemini]** `tts_node.py:1040` OPENROUTER_KEY 有設即用 Gemini chain → ✅ tts_node log 看到 `[openrouter_gemini]` 全路徑使用
- WSL 端 unit test 60/60 PASS（18 pending_confirm + 42 brain_rules）

### 🔴 Jetson 整合測試發現新問題（5/8 evening）

**[#F-confirm-timeout] PendingConfirm 多輪修復**

5/8 evening 演進：5s → 15s（user 等對話完）→ 30s + new_speech_intent cancel（user 換話題自動 cancel）→ 找到 gesture_live_window=0.5s 太短 → 5.0s

| 階段 | 修法 | 結果 |
|---|---|---|
| 1 | timeout 5s → 15s | 仍 timeout（user 走過去比手勢 >15s）|
| 2 | timeout 15s → 30s + `_on_speech_intent` cancel pending | timeout 仍發生（OK event 被認為 stale）|
| 3 | `_gesture_live_window_s` 0.5s → 5.0s | ✅ **CONFIRMED 真有 fire**：`PROPOSAL wiggle src=rule:confirmed reason=confirmed_via_ok:wiggle` |

**Root cause 真因**：vision_perception 發 gesture event rate ~3-4s 一個（不是 10Hz tick rate）。`brain_node._tick_pending_confirm` 0.5s gesture_live_window 把 fresh OK event 當 stale → tick 永遠拿到 None → 永不累積到 stable_s=0.5s。

**仍未解 #F-wiggle-motion-no-fire**（5/8 evening 22:14）：
- ✅ Brain emit PROPOSAL wiggle 確認
- ❌ 但實際 `/webrtc_req` 沒出 wiggle 對應 motion api_id（仍是 1016 wave_hello）
- 推測：wiggle plan 被後續 `wave_hello` / `greet_known_person` 提案蓋掉（PENDING 結束後 face/wave gesture 又自動 fire），或 wiggle plan 在 step 0 say 後被 preempt
- 待查：`/brain/skill_result` 抓不到完整 wiggle plan_id 序列，需更穩定的 monitor + 一次性執行
- **暫停修復**，繼續清單其他項目（5/8 evening Roy 指示）

### 沿用 5/7 night 已 commit
- `202a7e3` start_full_demo_tmux.sh source .env
- `685c97d` object_remark per-(class,color) 60s dedup
- `10829ca` per-message TTS routing（Studio→Gemini / mic→edge_tts）
- `e1363c8` stranger_alert / object person 靜音
- `67c28ce` Studio Gateway CORS

詳細 fail-map：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`

---

## 一、啟動與部署檢查（P0）

### 1.1 Build / Import

- [x] **同步 Jetson**：`~/sync once` 成功
- [x] **colcon build**：`pawai_brain` build 成功
- [x] **colcon build**：`interaction_executive` build 成功
- [x] **colcon build**：`vision_perception` build 成功
- [x] **colcon build**：`speech_processor` build 成功
- [x] **colcon build**：`face_perception` build 成功
- [x] **import smoke**：`pawai_brain.conversation_graph_node` 可 import（修了 `pip install langgraph` 缺套件）
- [x] **import smoke**：`pawai_brain.capability.registry` 可 import
- [x] **import smoke**：`interaction_executive.brain_node` 可 import
- [x] **import smoke**：`speech_processor.tts_split` 可 import

### 1.2 Full Demo 啟動

- [x] **full demo tmux 起得來**：`bash scripts/start_full_demo_tmux.sh`（修了 `.env` 沒 source 的 bug → openrouter=on）
- [x] **單一 chat publisher**：`/conversation_graph_node` 存在，無 `/llm_bridge_node`（langgraph default 分支）
- [x] **Brain topics 存在**：`/brain/chat_candidate`、`/brain/proposal`、`/brain/conversation_trace` ✓
- [x] **Perception topics 存在**：`/state/perception/face`、`/event/gesture_detected`、`/event/pose_detected`、`/event/object_detected` ✓
- [x] **Studio gateway 正常**：WebSocket /ws/* 全 accepted，CORS middleware 已加（Studio chat POST 修復）

---

## 二、語音主鏈（P0）

### 2.1 ASR → pawai_brain → Brain → TTS

- [x] **單輪對話**：「你好」→ Gemini reply `[excited] 嗨！你回來啦` ✓
- [x] **連續五輪不中斷**：Roy 麥克風 5+ 輪不 crash（早安/餓了/叫什麼/介紹/你好）
- [x] **CapabilityContext 生效**：「你可以做什麼」→ caps-02 trace 列六大功能 + skill_gate blocked self_introduce:defer
- [x] **記住名字**：「我是 Roy」→ 下一輪「我叫什麼名字？」→ `[laughs] 你是 Roy 啊！` ✓ (5/8 morning B3)
- [x] **時間感知**：「早安」reply 含「現在已經晚上八點多」 ✓
- [x] **天氣感知**：「早安」reply 含「外面多雲，但家裡很亮」 ✓
- [x] **早晚問候**：晚上說「早安」→ Gemini 自動糾正成晚上 ✓ (5/7 night Roy 實測)

### 2.2 Stop / Safety

- [x] **中文 stop**：「停」→ trace input → safety_gate hit (stop_move) → output (safety_path)，bypass LLM
- [x] **英文 stop**：「stop」→ 同上
- [x] **緊急詞**：「緊急」→ safety_gate hit ✓（煞車 / 暫停 keyword 在 list 但未獨立測，邏輯同）
- [x] **任何狀態 stop 都生效**：wave_hello 動作中說「停」+ sit_along 動作中說「stop」→ 兩 plan 都 `aborted: preempted` + stop_move api_id=1003 completed ✓ (5/8 morning E1+E2)

### 2.3 TTS 品質

- [x] **一般對話自然**：Gemini Despina + audio tag `[playful] [excited] [curious]` 渲染 ✓
- [x] **長句不漏整句**：「講一個短短的睡前故事」→ 5 句完整故事，audio tag `[whispers]` 正確 ✓ (5/8 morning B4)
- [x] **長句不跳行**：>40 字元 chunk 切分（5/8 MIN_SPLIT_CHARS=30，5 句連貫）✓
- [x] **語氣連貫觀察**：後半段語氣 Roy 親耳聽「還不錯」✓ (5/8 morning)
- [x] **TTS 開始播放延遲**：Studio chat (Gemini Despina) 6.5s 首音 / 麥克風 (edge_tts) ~1-2s。**目標 < 12-15s ✓**
- [ ] **Gemini TTS voice A/B**（**OBS，若恩 5/7 會議 action**）：Despina 以外候選 voice（如 Aoede / Charon / Fenrir 等 OpenRouter Gemini TTS preview 支援）試聽，挑 demo 最自然的

### 2.4 Fallback

- [x] **OpenRouter timeout / 失敗**：系統不 crash（5/7 早安初次冷啟掉到 RuleBrain unknown，無 traceback）
- [x] **LangGraph fallback**：Gemini → DeepSeek → RuleBrain（chain 注入 conversation_graph_node）
- [x] **RuleBrain rescue**：「[curious] 欸我沒聽清楚...」 unknown template 出現過 ✓（5/7 早安冷啟）
- [ ] **斷網測試**：只做 observation，不當 hard gate（**待 5/13 LM307 跑**）

---

## 三、Brain / Skill 呼叫鏈（P0）

### 3.1 LLM → Brain → Skills

- [x] **`wave_hello` 執行**：「跟我打招呼」→ accepted + step say + step motion (api 1016) ✓ (5/8 D1，**前提：depth_safety_node 已啟**)
- [x] **`sit_along` 執行**：「陪我坐一下」→ accepted + step say + step motion (api 1009 sit) ✓ (5/8 D4)
- [x] **`careful_remind` 執行**：「提醒我小心」→ TTS only by design ✓ (5/8 D2)
- [x] **`show_status` 執行**：「你現在狀態如何」→ TTS + OK 引導語 by design ✓ (5/8 D3)
- [ ] **`greet_known_person` 執行**：Roy 入鏡 → 5/8 morning F 階段背景發 12 次自動觸發（屬 [#F-confirm] 干擾項）
- [x] **skill result 回流**：5/8 morning 4 個 skill 全部 `started → step_started → step_success → completed` ✓
- [x] **下一輪能接續**：sit_along 後問「剛剛成功了嗎？」→ `[playful] 成功了喔！我已經乖乖坐好了` ✓ (5/8 D5)

### 3.2 Confirm Mode

- [x] **`wiggle` needs_confirm**：「搖一下」→ skill_gate `needs_confirm` detail=wiggle ✓ (5/8 F1)
- [ ] **OK 手勢確認**：FAIL→A:BLOCKER — OK gesture confidence=1.0 偵測到，但 wiggle 0 個 plan accepted；反觸發 wave_hello x14、greet_known_person x12（[#F-confirm]）
- [ ] **`stretch` needs_confirm**：未測（F3 失敗後跳過 F4）
- [ ] **OK 手勢確認**：未測
- [x] **未 OK 不執行**：F2 不比 OK 等 6s，wiggle 沒執行 ✓

### 3.3 Trace Only

- [x] **`self_introduce` trace_only**：「介紹一下你自己」→ 狗不動，只說介紹文（`/webrtc_req` 0 行）✓ (5/8 C1)
- [ ] **Studio button 自介**：SKIP→C — Studio 沒這個 button（5/8 morning Roy 確認不存在也不需要）
- [x] **trace 顯示正確**：skill_gate `accepted_trace_only` detail=self_introduce 多次出現 ✓ (5/8 C1)

### 3.4 Skill 合法性檢查

- [x] **不存在 skill**：「後空翻」→ `[thinking] 那個對我來說太難了啦...` LLM persona 婉拒，0 motion ✓ (5/8 G1)；「爬樓梯」→ `[thinking] 有點太刺激了` 0 motion ✓ (5/8 G2)
- [x] **禁用 skill**：「跳舞」→ Gemini persona 婉拒「跳舞我現在還不太會耶...」+ 0 skill_request + 0 webrtc_req ✓
- [x] **unknown-but-allowlisted 防線**：5/7 white box review 已修（pawai_brain skill_policy_gate.normalize_proposal_v2，27 case test pass）
- [x] **invalid skill 不會 motion**：整夜 `/webrtc_req` topic 0 motion 命令 ✓
- [x] **Brain 拒絕原因可見**：caps-02 trace 顯示 `skill_gate blocked self_introduce:defer` + dance trace 仍可觀察

---

## 四、誤觸抑制（P0）

### 4.1 陌生人 / 人臉

- [ ] **Roy 可控站位 greet**：Roy 1.5m 觸發 1 次問候（**待 demo 場景跑**，face_db 含 alice/grama）
- [ ] **重複問候 cooldown**：Roy 連續路過 2-3 次（cooldown 邏輯 `last_alert_ts` 已實作，**待現場驗證**）
- [x] **陌生人累積 5 秒**：`executive.yaml unknown_face_accumulate_s: 5.0` ✓（5/8 從 3.0 拉）
- [x] **手 / 反光 / 玻璃**：stranger_alert SAY="" 靜音 ✓（commit e1363c8 5/7 night）
- [x] **Studio-only 誤判可記錄**：`/brain/proposal` trace 仍 emit，TTS 路徑 `empty_tts_text` 不發 ✓

### 4.2 跌倒 / 姿勢

- [x] **跌倒不出聲打斷**：fall TTS 雙路關閉（`FALL_ALERT_TTS=""` + `POSE_TTS_MAP['fallen']` 拆掉）✓
- [ ] **推車 / 椅子誤判抑制**：5s ankle-on-floor gate 已實作（`pose_classifier.py:165-167`），**待現場驗推車入鏡**
- [ ] **對話中躺下**：TTS 不被 fall alert 打斷（架構上 chain 不會觸發 SAY，**待親測**）
- [x] **兩條 fall TTS 路徑都靜音**：`FALL_ALERT_TTS` + `POSE_TTS_MAP["fallen"]` 都關閉 ✓（commit b224217 + e1363c8 確認）

### 4.3 多模態互不干擾

- [x] **講話中不被人臉打斷**：5/8 morning B/C/D 階段全程 stranger_alert + greet_known_person plan 多次發但 TTS 不出聲，長句故事完整 ✓
- [ ] **講話中不被姿勢打斷**：fall TTS 雙路關閉 ✓（H2 SKIP — 在家不便躺下，**留 5/13 場地驗**）
- [x] **動作中不被 object / pose TTS 插隊**：5/8 D1/D4 wave_hello + sit_along motion 期間 background object_remark 多次但無 abort/preempt by object ✓
- [ ] **pending confirm 期間 OK 不誤觸其他流程**：FAIL→A:BLOCKER（[#F-confirm] OK 沒 wire，反觸發 wave_hello）

---

## 五、五功能個別測試（P0 + OBS）

### 5.1 人臉辨識

- [ ] **Roy 正面 1.5m**：至少成功 1 次
- [ ] **Roy 5 次成功率**：記 `x/5`
- [ ] **多人同框**：只記 OBS
- [ ] **側臉 / 低頭**：只記 OBS
- [ ] **陌生人誤觸次數**：記每 5 分鐘幾次

### 5.2 手勢辨識

- [ ] **OK 手勢**：至少成功 1 次
- [ ] **Thumbs up**：至少成功 1 次
- [ ] **Palm**：至少成功 1 次
- [ ] **Peace**：至少成功 1 次
- [ ] **Fist**：記 OBS
- [ ] **Wave 側面**：記成功率
- [ ] **Wave 正面 / 轉圈**：`SKIP→C`

### 5.3 姿勢辨識

- [ ] **站立**：至少成功 1 次
- [ ] **坐姿**：至少成功 1 次
- [ ] **躺平在地板上 → fallen 觸發**：5/7 會議共識「放寬判定為躺平在地上即算跌倒」（ankle-on-floor gate `pose_classifier.py:165-167` 已實作）。驗收：**fall chip 出現 ≥1 次（不出聲打斷對話）**
- [ ] **推車 / 椅子**：不出聲打斷
- [ ] **蹲下**：記 OBS
- [ ] **彎腰 / 叉腰 / 單膝跪地**：`SKIP→C` 或 OBS

### 5.4 物體辨識

- [ ] **大物件椅子**：<1.5m 至少成功 1 次
- [ ] **人類辨識**：看到人能顯示 / 回報
- [ ] **純色杯子**：記成功率，不當 blocker
- [ ] **顏色辨識**：記正確率
- [ ] **白杯 / 多色物 / 複雜背景**：OBS
- [ ] **小物 >2m**：`SKIP→C`

---

## 六、Studio 前端（P0）

### 6.1 對話顯示

- [x] **語音輸入顯示**：Roy 5/7 night ChatPanel 顯示「早安」「我餓了」等 ✓
- [x] **PAI 回覆顯示**：ChatPanel 顯示 Gemini reply（含 audio tag）✓
- [x] **歷史保留**：Roy 看到多輪對話保留 ✓
- [ ] **頁面切換不中斷對話**：useStateStore 不重連 WebSocket（**待親測切 panel 驗**）

### 6.2 Brain Trace

- [x] **顯示 LLM 決策**：caps-02 trace 顯示 `llm_decision detail=google/gemini-3-flash-preview` ✓
- [ ] **`accepted` chip**：（**Roy 待對 wave_hello 等 execute skill 驗**）
- [ ] **`needs_confirm` chip**：（**Roy 待對 wiggle/stretch 驗**）
- [x] **`rejected_not_allowed` / `blocked` chip**：caps-02 `skill_gate blocked self_introduce:defer` ✓
- [x] **`accepted_trace_only` chip**：self_introduce 路徑（**待 Studio Trace Drawer 視覺確認**）
- [x] **11-stage trace**：graph.py 11 nodes 確認；caps-02 echo 看到 6 stages（input/llm_decision/json_validate/repair/skill_gate/output）
- [x] **engine label**：`engine=langgraph` ✓

### 6.3 五功能視角

- [ ] **人臉視角**：看得到 face state / track
- [ ] **手勢視角**：看得到 gesture event
- [ ] **姿勢視角**：看得到 pose event
- [ ] **物體視角**：看得到 object event
- [ ] **大螢幕展示清楚**

---

## 七、Demo 主流程（P0）

### 7.1 主腳本 10 步

- [ ] **S0 Roy 入鏡**：greet，若失敗可手動語音開場，不中止
- [ ] **S1 你可以做什麼**：列六大功能
- [ ] **S2 介紹一下你自己**：trace_only，狗不動
- [ ] **S3 Studio 完整自介 button**：sequence 執行
- [ ] **S4 跟我打招呼**：`wave_hello`
- [ ] **S5 拿紅杯 / 椅子**：object_remark，PASS or OBS
- [ ] **S6 搖一下**：needs_confirm → OK → `wiggle`
- [ ] **S7 陪我坐一下**：`sit_along`
- [ ] **S8 側躺 / 推車**：Studio trace 可出現，不出聲
- [ ] **S9 跳舞 / 後空翻**：blocked / rejected，不動
- [ ] **S10 停**：立即 stop / 靜音

### 7.2 三輪連跑標準

- [ ] **Hard gate**：3 輪誤觸 TTS 打斷 = 0
- [ ] **Hard gate**：3 輪 invalid skill 真的動 = 0
- [ ] **Hard gate**：3 輪 stop 失效 = 0
- [ ] **Hard gate**：3 輪系統需重啟 = 0
- [ ] **Demo flow gate**：3 輪至少 2 輪完整順跑
- [ ] **Trace coverage**：`accepted` / `needs_confirm` / `rejected_or_blocked` / `trace_only` 都至少出現 1 次

### 7.3 自由互動（OBS）

- [ ] **Roy 15 分鐘自然互動**
- [ ] **老師 / 其他人 15 分鐘自然互動**
- [ ] **觀察自然度**
- [ ] **觀察長對話是否變慢**
- [ ] **觀察觀眾視角是否清楚**
- [ ] **記錄誤觸次數**

---

## 八、導航避障（P1 / 加分）

### 8.1 場地就緒時

- [ ] **AMCL warmup**
- [ ] **`nav_ready=true`**
- [ ] **`goto_relative 1.0m`**
- [ ] **中途放紙箱 reactive_stop 停**
- [ ] **移走後 resume**
- [ ] **整輪不撞、不摔、不卡 queue**

### 8.2 場地不就緒時降級

- [ ] **`nav_ready` 狀態可讀**
- [ ] **`depth_clear` 對障礙翻轉**
- [ ] **reactive_stop 對 fake obstacle 停**
- [ ] **記錄 odom 漂移量**
- [ ] **動態避障 / detour**：`SKIP→C`

---

## 九、硬體穩定性（P0）

### 9.1 電源

- [ ] **連續運作 30 分鐘**：5/7 night 中途 reboot，**未達 30 min**（fail-map [#Reboot-1]）
- [ ] **連續運作 1 小時**：5/12 LM307 補
- [ ] **新降壓器（換 V 後）連續運作不掉電**：5/7 會議 Roy 報告「換不同 V 大小後解決系統會跑掉的問題」。但 5/7 night 仍發生 1 次 reboot（fail-map `[#Reboot-1]` carry-over）。**5/12 LM307 連續 30/60 min 驗**
- [ ] **Jetson 不突然斷電**：5/7 night 1 次 reboot（XL4015 風險，memory project_jetson_power_issue.md 已標）

### 9.2 機構

- [ ] **光達不晃動**
- [ ] **新 LiDAR（私人科技）+ Go2 原廠 LiDAR 各跑各，不互相干擾**（5/7 會議 Roy 報告「接 Jetson 上跟 Go2 原廠 LiDAR 不衝突，各跑各的」）
- [ ] **頭盔不脫落**
- [ ] **新外接喇叭不掉**（會議提到「整體 Jetson + 新降壓器 + 新喇叭 重新配置後不擁擠」）
- [ ] **線材不卡腿**
- [ ] **做 motion 時線不拉扯**

### 9.3 網路 / API

- [ ] **WiFi 穩定**：Tailscale 5/7 night 失聯一次（伴隨 Jetson reboot），需 LM307 場地驗
- [x] **OpenRouter API 可連**：Gemini/DeepSeek chain 啟動 + 對話多輪 reply 通 ✓
- [x] **TTS 延遲 < 15 秒**：Studio chat (Gemini) 6.5s 首音 / 麥克風 (edge_tts) 1-2s ✓
- [x] **Studio websocket 不斷線**：gateway log /ws/speech /ws/video/* /ws/events 全 accepted ✓

---

## 十、邊界與刁難（P1）

### 10.1 使用者刁難

- [ ] **後空翻**
- [ ] **爬樓梯**
- [ ] **跳舞**
- [ ] **連續問 5 句**
- [ ] **奇怪矛盾指令**

### 10.2 環境刁難

- [ ] **多人同時在場**
- [ ] **吵雜環境**
- [ ] **燈光變化**
- [ ] **複雜背景**

### 10.3 系統刁難

- [ ] **短暫網路不穩**
- [ ] **長對話記憶是否變慢**
- [ ] **Jetson 溫度**
- [ ] **RAM 使用量**

---

## 十一、明確不測 / 放推（C 類）

`SKIP→C` — 不進主流程，只在末尾備註，避免日後忘了是有意 skip。

- [x] **動態避障 detour**：5/3 L3 PASS 失敗（nav_action_server max_speed 不 enforce + AMCL plateau）
- [x] **多 skill 一次輸出**：persona / policy 設計上一次最多一個 skill
- [x] **邊講邊動並行**：目前是序列，不是並行；TTS / motion timing 未同步
- [x] **語音控導航 / move_forward 數值**：5/8 系統設計上語音不開 nav
- [x] **電量 <20% safety**：硬體 telemetry 沒接
- [x] **完整參數 range validation**：目前只做 args 非 dict 歸 `{}`，沒有完整 schema gate
- [x] **新人現場註冊**：face_db 為 demo 期固定 alice / grama / Roy
- [x] **Wave 正面 / 轉圈**：5/7 教授會議共識「正面 wave 預期失敗」
- [x] **小物 >2m**：YOLO / D435 解析度不足
- [x] **Gemini → GPT-5 fallback**：實際是 Gemini → DeepSeek → RuleBrain，沒有 GPT-5

---

## 十二、測試紀錄格式

```md
## [#X] <功能> / <子項>
結果：PASS / FAIL / OBS / SKIP
分類：A / B / C
觸發：
預期：
實際：
Trace/topic：
是否可重現：YES / NO / 未試
下一步：
```

---

## 十三、Triage 優先級

### P0 demo blocker

- full demo 起不來
- ASR → pawai_brain → brain_node → TTS 主鏈斷
- stop 失效
- invalid skill 真的動
- 誤觸 TTS 打斷
- 系統 crash / 需要重啟
- 會撞 / 會摔 / queue 卡死

### P1 單一展示路徑斷

- `wave_hello` 不跑
- `wiggle / stretch needs_confirm` 不通
- `self_introduce trace_only` trace 不對
- Studio chip 顯示錯
- 某一個 perception demo 不穩

### P2 品質 / 數字不好

- TTS 延遲偏高但能播
- Roy 5 次只中 2 次
- 物體顏色不準
- 姿勢成功率低
- 語氣不夠自然

---

## 十四、最容易翻車 Top 10

1. **陌生人誤判出聲打斷**
2. **跌倒誤判出聲打斷**
3. **TTS 長句漏字 / 卡死**
4. **TTS 延遲太長**
5. **LLM 提 invalid skill 但狗真的動**
6. **needs_confirm 沒進 PendingConfirm**
7. **OK 手勢沒確認成功**
8. **Studio trace 看不到 Brain 決策**
9. **full demo 雙 publisher**
10. **多模態互相插隊**