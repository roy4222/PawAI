# PawAI Demo 測試功能清單 v2

> **用途:** 今日 fail-map / 5/13–14 場地測試 / 5/18 Demo 前驗收
> **建議使用方式:** 一項一項勾，失敗記錄原因、trace/topic、是否可重現
> **撰寫日期:** 2026/05/07
> **最後更新:** 2026/05/08 evening（八階段在家驗收 + 三個 fix commit + Jetson 整合驗證）
> **標記:** `[x] PASS` / `FAIL→A:BLOCKER` / `FAIL→B:OBS` / `SKIP→C` / `[ ]` 待測

---

## 5/8 完成度概覽（morning 測試 + evening 修復）

| 區塊 | 完成度 | 核心驗證 |
|---|---|---|
| §1 啟動與部署 | 🟢 PASS（5/5） | 13 windows（含新加 depth_safety）、19+ nodes、single chat publisher、openrouter=on |
| §2.1 ASR→Brain→TTS | 🟢 PASS（5/5） | 你好/你可以做什麼/我是 Roy→記住名字/睡前故事 |
| §2.2 Stop / Safety | 🟢 PASS（2/2） | 動作中說「停」/「stop」→ wave_hello / sit_along **preempted** + safety_path |
| §2.3 TTS 長句 | 🟢 PASS | 睡前故事 5 句連貫，audio tag `[whispers]` 正確；mic + Studio **統一走 Gemini Despina** ✅ |
| §2.4 Fallback | 🟢 鏈路通 | RuleBrain rescue 在 ASR 不穩時觸發（[curious] 沒聽清楚） |
| §3.1 motion skills | 🟢 PASS（4/4） | wave_hello (api 1016)、careful_remind、show_status、sit_along (api 1009) 全動 |
| §3.2 needs_confirm | 🟢 **軟體鏈路全通** | thumbs_up→wiggle→OK confirm + plan completed + api_id=1033 全 PASS；硬體面 Go2 沒實際扭屁股待 [#wiggle-no-physical-motion] 5/9 追 |
| §3.3 self_introduce | 🟡 部分 | 語音 trace_only PASS；Studio button 不存在 SKIP |
| §3.4 Skill 合法性 | 🟢 PASS（3/3） | 後空翻/爬樓梯/跳舞 全部 LLM persona 婉拒，0 motion api_id |
| §4 誤觸抑制 | 🟢 沿用 | stranger_alert / object_remark say-only 不打斷 motion 與長句 TTS |
| §6.1 Studio 對話顯示 | 🟢 沿用 | ChatPanel 顯示語音輸入 + Gemini reply + audio tag |
| §6.2 Brain Trace | 🟢 PASS | safety_gate / accepted / accepted_trace_only / needs_confirm chip 全可見 |
| §6.3 Studio 五功能視角 | ⏸ 待測 | 5/8 evening 沒測到 |
| §4.1 Roy 站位 greet | 🟢 PASS | 1.5m 入鏡觸發 greet_known_person say+motion；3 次入鏡 cooldown 生效（2-3 plan）|
| §5 五功能個別 | ⏸ 待 5/13 場地 | 人臉/手勢/姿勢/物體成功率 |
| §7 Demo 3 連跑 | ⏸ 待 5/14 SL201 | 10 步腳本 + Hard gate |
| §8 導航避障 | ⏸ 待 5/13 場地 | — |
| §9 硬體穩定 | ⏸ 待 5/13 場地 | 30/60 min run + 供電 |

---

## ✅ 5/8 evening 已 commit 修復（已 push remote 待 confirm）

| Commit | Fix 範圍 | Jetson 驗證 |
|---|---|---|
| `35bdf1d` fix(scripts): add depth_safety window | [#A1.3] | ✅ `/capability/depth_clear` Publisher count=1 |
| `a2eefc8` fix(tts): unify mic + Studio paths to Gemini | [#TTS-gemini] | ✅ tts_node log `[openrouter_gemini]` 全路徑使用 |
| `44a8a73` fix(executive): repair OK-confirm flow | [#F-confirm] 2a/2b + [#F-confirm-timeout] | ✅ `PROPOSAL wiggle confirmed_via_ok` 出現 |

WSL 端 pytest 61/61 PASS（18 pending_confirm + 43 brain_rules）；Jetson 上 colcon build OK；executive node restart 後新邏輯生效。

---

## 🟡 仍待解 backlog（明天追）

### [#wiggle-no-physical-motion] 1033 發出但 Go2 沒實際扭屁股（B:OBS）

5/8 evening 22:56 軟體鏈路完整通過：thumbs_up→PENDING→OK→CONFIRMED→plan completed→`/webrtc_req api_id=1033 (WiggleHips)` 全部 OK，但 Roy 實機觀察狗沒做任何動作。

go2 driver log 沒看到 reject — Go2 對不支援 api_id 慣性 silent ignore（memory 已記）。

**5/9 追**：
1. 手動發 `1002 BalanceStand` 後再發 `1033` 看是否 state precondition
2. Foxglove 看 IMU/joint state 確認 micro-motion
3. 翻 Go2 SDK 文件確認 v1.1.7 是否支援 WiggleHips
4. 若硬體不支援，wiggle skill 改用其他可用 motion（`Content` 1020 / `Pose` 1028）

不影響 demo 主流程（其他 motion 都正常），可降為 OBS 留場地驗。

### 暫不修（OBS 記錄）

- **[#F-confirm-pose-still-emits]** 5/8 morning F 階段 PENDING 期間仍見 6 次 greet_known_person（但時間戳全在 timeout 結束後 emit；evening live_window 改 5s 後沒重複觀測）
- **[#sit_along-no-stand-up]** by design，狗坐下後保持坐姿
- **§9.1 Jetson reboot** 5/7 night 1 次（XL4015 風險，等場地驗）

### ✅ 5/8 evening §5.2 + confirm 全鏈打通

**[#thumb-label-mismatch] vision `"thumb"` → `"thumbs_up"` 對齊 contract** ✅ 已修
- `vision_perception/gesture_recognizer_backend.py:53` 把 `Thumb_Up` 映射改成 `"thumbs_up"`（對齊 `interaction_contract.md:485` enum）
- 修後驗證：thumbs_up gesture event 正確發出，brain 收到後觸發 `_GESTURE_CONFIRM[thumbs_up→wiggle]`

**[#wiggle-api-id-typo] wiggle_hip 1029 → 1033 對應正確 motion** ✅ 已修
- `skill_contract.py:118` 原本 `"wiggle_hip": 1029` 是 typo（1029 是 Scrape 拜拜）
- 對齊 `robot_commands.py:43` `"WiggleHips": 1033`

**[#F-confirm + #F-wiggle-motion-no-fire] 端到端 confirm 流打通** ✅
- 5/8 evening 22:56 完整 trace：
  ```
  thumbs_up→PendingConfirm wiggle → say_canned awaiting_ok →
  OK→CONFIRMED → wiggle plan accepted+started+say+motion+completed →
  /webrtc_req api_id=1033 ✓
  ```

### 🟡 仍待解（5/9 追）

**[#wiggle-no-physical-motion] 1033 發出去但 Go2 沒動**
- 5/8 evening 22:56 完整 confirm 鏈路 + WiggleHips api_id=1033 發送 OK
- 但 Roy 實機觀察：「沒做任何動作」
- go2 driver log 沒有 reject / error 訊息（Go2 對未支援 api_id 慣性 silent ignore）
- 推測：
  - Go2 firmware v1.1.7 不支援 `WiggleHips`（需查 SDK 文件）
  - 或需先 `BalanceStand` (1002) 才能 wiggle（state precondition）
  - 或動作幅度太小肉眼沒看到（不太可能）
- **明天追**：
  1. 試手動發 `1002 BalanceStand` 後再發 `1033`
  2. Foxglove 看 IMU/joint state 確認狗有沒有微動
  3. 翻 Go2 SDK 文件確認 WiggleHips 在 v1.1.7 是否支援
  4. 若硬體不支援，wiggle skill 改用其他 motion（例：`Content` 1020 / `Pose` 1028）

---

## 沿用 5/7 night commit（背景）

- `202a7e3` start_full_demo_tmux.sh source .env
- `685c97d` object_remark per-(class,color) 60s dedup
- `10829ca` per-message TTS routing（5/8 evening `a2eefc8` 把 mic 也 routed Gemini）
- `e1363c8` stranger_alert / object person 靜音
- `67c28ce` Studio Gateway CORS

詳細 fail-map：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`（含 [#A1.3]、[#F-confirm]、[#TTS-gemini] 完整 root cause）

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
- [x] **`greet_known_person` 執行**：5/8 evening Roy 1.5m 入鏡觸發完整 say+motion plan，cooldown 機制生效 ✓
- [x] **skill result 回流**：5/8 morning 4 個 skill 全部 `started → step_started → step_success → completed` ✓
- [x] **下一輪能接續**：sit_along 後問「剛剛成功了嗎？」→ `[playful] 成功了喔！我已經乖乖坐好了` ✓ (5/8 D5)

### 3.2 Confirm Mode

- [x] **`wiggle` needs_confirm**：「搖一下」→ skill_gate `needs_confirm` detail=wiggle ✓ (5/8 F1)
- [~] **OK 手勢確認**：5/8 evening 修 4 階段（flicker / face-pose guard / 30s timeout / live_window 5s）後 `PROPOSAL wiggle src=rule:confirmed reason=confirmed_via_ok:wiggle` ✓；**但 motion 沒 fire**（[#F-wiggle-motion-no-fire] backlog）
- [ ] **`stretch` needs_confirm**：未測（先解 wiggle motion 再驗 stretch）
- [ ] **OK 手勢確認**（stretch）：未測
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

- [x] **Roy 可控站位 greet**：1.5m 觸發 greet_known_person say+motion 完整 ✓ (5/8 evening；brain log `identity:roy` 3 次 + `identity:grama` 1 次驗 face_db)
- [x] **重複問候 cooldown**：3 次入鏡只觸發 ~2 個完整 plan（cooldown 機制生效）✓ (5/8 evening)
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

- [x] **OK 手勢**：5/8 evening 11 events，7 個 confidence=1.0 ✓
- [x] **Thumbs up**：5/8 evening 5 events，4 個 confidence=1.0 ✓（**但 vision 發 `"thumb"` ≠ brain 期待 `"thumbs_up"`，thumbs_up→wiggle confirm 流斷在這裡，見 [#thumb-label-mismatch]**）
- [x] **Palm**：5/8 evening 3 events，全 confidence=1.0 ✓
- [x] **Peace**：5/8 evening 4 events，全 confidence=1.0 ✓
- [ ] **Fist**：未測，記 OBS
- [ ] **Wave 側面**：5/8 evening 3 個誤觸 wave event（手過渡時偵測），側面成功率待 5/13 場地驗
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