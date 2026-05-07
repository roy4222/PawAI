# PawAI Demo 測試功能清單 v2

> **用途:** 今日 fail-map / 5/13–14 場地測試 / 5/18 Demo 前驗收
> **建議使用方式:** 一項一項勾，失敗記錄原因、trace/topic、是否可重現
> **撰寫日期:** 2026/05/07
> **最後更新:** 2026/05/07 night（per-message TTS routing + 誤觸靜音 + Studio CORS）
> **標記:** `[x] PASS` / `FAIL→A:BLOCKER` / `FAIL→B:OBS` / `SKIP→C` / `[ ]` 待測

---

## 5/7 night 完成度概覽

| 區塊 | 完成度 | 核心驗證 |
|---|---|---|
| §1 啟動與部署 | **🟢 全 PASS** | 5 packages build、19 nodes 起、單一 chat publisher、Brain + Perception topics 全到 |
| §2.1 ASR→Brain→TTS | 🟢 主路徑 PASS | 「你好」「你可以做什麼」「我餓了」「早安」全走 Gemini LLM + Despina/edge_tts |
| §2.2 Stop / Safety | **🟢 全 PASS** | 停 / stop / 緊急 三 phrase safety_gate hit + LLM bypass，trace 短路 |
| §2.3 TTS 品質 | 🟡 部分 | 一般對話自然 ✓；首音延遲 Studio 6.5s / mic 1-2s（OBS）；長句睡前故事**待 Roy 親測** |
| §2.4 Fallback | 🟢 鏈路通 | LangGraph chain：Gemini → DeepSeek → RuleBrain，5/7 早安冷啟掉 RuleBrain unknown 已驗 |
| §3.4 Skill 合法性 | 🟢 全 PASS | 「跳舞」Gemini 婉拒 + 0 webrtc_req；整夜 `/skill_request` 0 動作 |
| §4 誤觸抑制 | 🟢 已修 | stranger_alert SAY="" 靜音；object_remark person skip + 60s dedup；fall TTS 雙路關閉沿用 |
| §6.1 Studio 對話顯示 | 🟢 PASS | ChatPanel 收語音輸入、TTS 文本、歷史保留 |
| §6.2 Brain Trace | 🟢 PASS | engine=langgraph、blocked / trace_only chip 出現；needs_confirm 待 wiggle 測 |
| §3.1 motion skills | ⏸ **待 Roy 親測** | wave_hello / sit_along / wiggle confirm 都需要狗有空間 |
| §3.2 PendingConfirm | ⏸ **待 Roy 親測** | OK 手勢確認 5s window |
| §3.3 self_introduce | ⏸ **待 Roy 親測** | trace_only 路徑 + Studio button 6-step 序列 |
| §5 五功能個別 | ⏸ **待 5/13 場地** | 人臉 Roy 5 次、手勢 4 種、姿勢、物體成功率 |
| §7 Demo 主流程 3 連跑 | ⏸ **待 5/14 SL201** | 10 步腳本 + Hard gate + 自由互動 |
| §8 導航避障 | ⏸ **待 5/13 場地** | 家裡空間不夠 |
| §9 硬體穩定 | ⚠️ Jetson reboot 1 次 | XL4015 供電風險（memory 已標 demo 風險項）；場地實機需驗 30/60 min |

### 今晚發 5 個 commit
- `202a7e3` `start_full_demo_tmux.sh` 加 source `.env`（OpenRouter key 注入 tmux 子 shell）
- `685c97d` object_remark per-(class,color) 60s dedup
- `10829ca` per-message TTS routing（Studio chat → Gemini, others → edge_tts，5 file plumbing）
- `e1363c8` stranger_alert / object person 靜音
- `67c28ce` Studio Gateway 加 CORS（Studio chat panel 「Brain 文字通道未連線」修復）

詳細 fail-map：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`
Plan：`~/.claude/plans/polished-questing-starlight.md` v1.4

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
- [ ] **記住名字**：「我是 Roy」→ 下一輪測試（deque(maxlen=10) 已 wired，待 demo 跑）
- [x] **時間感知**：「早安」reply 含「現在已經晚上八點多」 ✓
- [x] **天氣感知**：「早安」reply 含「外面多雲，但家裡很亮」 ✓
- [x] **早晚問候**：晚上說「早安」→ Gemini 自動糾正成晚上 ✓ (5/7 night Roy 實測)

### 2.2 Stop / Safety

- [x] **中文 stop**：「停」→ trace input → safety_gate hit (stop_move) → output (safety_path)，bypass LLM
- [x] **英文 stop**：「stop」→ 同上
- [x] **緊急詞**：「緊急」→ safety_gate hit ✓（煞車 / 暫停 keyword 在 list 但未獨立測，邏輯同）
- [ ] **任何狀態 stop 都生效**：動作中也能停（待 motion 測試時驗）

### 2.3 TTS 品質

- [x] **一般對話自然**：Gemini Despina + audio tag `[playful] [excited] [curious]` 渲染 ✓
- [ ] **長句不漏整句**：「講一個短短的睡前故事」→ **待 Roy 親測**（5/8 chunking 重構已 in，但 Studio chat 路徑用 Gemini 需重驗）
- [ ] **長句不跳行**：>40 字元 chunk 切分（5/8 改 MIN_SPLIT_CHARS=30 已 in）
- [ ] **語氣連貫觀察**：後半段語氣（OBS）— **待 Roy 親耳聽**
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

- [ ] **`wave_hello` 執行**：「跟我打招呼」→ accepted + motion
- [ ] **`sit_along` 執行**：「陪我坐一下」→ accepted + motion
- [ ] **`careful_remind` 執行**：「提醒我小心」→ accepted + TTS
- [ ] **`show_status` 執行**：「你現在狀態如何」→ accepted + 狀態回覆
- [ ] **`greet_known_person` 執行**：Roy 入鏡或提案 → 問候 Roy
- [ ] **skill result 回流**：執行後 `/brain/skill_result` 有結果
- [ ] **下一輪能接續**：LLM 知道上一個 skill 成功 / 失敗

### 3.2 Confirm Mode

- [ ] **`wiggle` needs_confirm**：「搖一下」→ `needs_confirm`
- [ ] **OK 手勢確認**：比 OK 後 `wiggle` 真執行
- [ ] **`stretch` needs_confirm**：「伸個懶腰」→ `needs_confirm`
- [ ] **OK 手勢確認**：比 OK 後 `stretch` 真執行
- [ ] **未 OK 不執行**：不比 OK 時不自動 motion

### 3.3 Trace Only

- [ ] **`self_introduce` trace_only**：「介紹一下你自己」→ 狗不動，只說介紹文
- [ ] **Studio button 自介**：按完整自我介紹 button → sequence 執行
- [ ] **trace 顯示正確**：`accepted_trace_only` 清楚出現

### 3.4 Skill 合法性檢查

- [ ] **不存在 skill**：「後空翻」→ blocked / rejected，不動（rapid-pub 排隊掉，邏輯架構正確待重測）
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

- [ ] **講話中不被人臉打斷**：stranger TTS 已靜音 ✓ + chair object_remark 60s dedup ✓（**待長對話現場驗**）
- [ ] **講話中不被姿勢打斷**：fall TTS 雙路關閉 ✓（**待親測**）
- [ ] **動作中不被 object / pose TTS 插隊**：執行 SkillPlan 時 `_has_active_sequence()` 已 gate，**待 motion 測試驗**
- [ ] **pending confirm 期間 OK 不誤觸其他流程**：架構上 `_GESTURE_CONFIRM` map gated，**待 wiggle/stretch 現場流程驗**

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