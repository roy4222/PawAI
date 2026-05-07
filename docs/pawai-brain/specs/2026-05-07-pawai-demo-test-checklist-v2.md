# PawAI Demo Test Checklist v2.1

> 用途：今日 fail-map / 5/13–14 場地測試 / 5/18 Demo 前驗收
> Spec：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-plan.md`
> Fail-map：`docs/pawai-brain/specs/2026-05-07-pawai-demo-test-fail-map.md`
> 撰寫：2026/05/07
> 標記：`PASS` / `FAIL→A:BLOCKER` / `FAIL→B:OBS` / `SKIP→C`
> v2.1 修正自 v2：(a) careful_remind 觸發句移到 §5.3 pose 章；(b) 早晚問候標 OBS；(c) trace stage 名稱保留 `llm_decision / json_validate`（與 `/brain/conversation_trace` 實際 publish 字串一致）

---

## 一、啟動與部署檢查（P0）

### 1.1 Build / Import

- [ ] **同步 Jetson**：`~/sync once` 成功
- [ ] **colcon build**：`pawai_brain` build 成功
- [ ] **colcon build**：`interaction_executive` build 成功
- [ ] **colcon build**：`vision_perception` build 成功
- [ ] **colcon build**：`speech_processor` build 成功
- [ ] **colcon build**：`face_perception` build 成功
- [ ] **import smoke**：`pawai_brain.conversation_graph_node` 可 import
- [ ] **import smoke**：`pawai_brain.capability.registry` 可 import
- [ ] **import smoke**：`interaction_executive.brain_node` 可 import
- [ ] **import smoke**：`speech_processor.tts_split` 可 import

### 1.2 Full Demo 啟動

- [ ] **full demo tmux 起得來**：`bash scripts/start_full_demo_tmux.sh`
- [ ] **單一 chat publisher**：有 `/conversation_graph_node`，沒有 `/llm_bridge_node`
- [ ] **Brain topics 存在**：`/brain/chat_candidate`、`/brain/proposal`、`/brain/conversation_trace`
- [ ] **Perception topics 存在**：`/state/perception/face`、`/event/gesture_detected`、`/event/pose_detected`、`/event/object_detected`
- [ ] **Studio gateway 正常**：大螢幕能看到 ChatPanel / Trace Drawer

---

## 二、語音主鏈（P0）

### 2.1 ASR → pawai_brain → Brain → TTS

- [ ] **單輪對話**：「你好」→ PAI 有回答
- [ ] **連續五輪不中斷**：連續問 5 句不 crash、不卡住
- [ ] **CapabilityContext 生效**：「你可以做什麼」→ 回答六大功能
- [ ] **記住名字**：「我是 Roy」→ 下一輪「你記得我嗎」能接續
- [ ] **時間感知**：「現在幾點」→ 回答合理時間
- [ ] **天氣感知**：「今天天氣如何」→ 回答台北天氣或自然 fallback
- [ ] **早晚問候 (OBS)**：晚上說「早安」→ 能自然糾正或提醒（B 類觀察，不擋）

### 2.2 Stop / Safety

- [ ] **中文 stop**：「停」→ 立即停止 / 靜音
- [ ] **英文 stop**：「stop」→ 立即停止 / 靜音
- [ ] **緊急詞**：「緊急」「煞車」「暫停」→ safety_gate hit
- [ ] **任何狀態 stop 都生效**：動作中也能停

### 2.3 TTS 品質

- [ ] **一般對話自然**：語氣不像冷冰冰機器音
- [ ] **長句不漏整句**：「講一個短短的睡前故事」→ 不漏句、不卡死
- [ ] **長句不跳行**：>40 字元回答不中途跳段
- [ ] **語氣連貫觀察**：後半段語氣是否維持，記 `OBS`
- [ ] **TTS 開始播放延遲**：記錄秒數，目標 < 12–15s

### 2.4 Fallback

- [ ] **OpenRouter timeout / 失敗**：系統不 crash
- [ ] **LangGraph fallback**：Gemini → DeepSeek → RuleBrain
- [ ] **RuleBrain rescue**：至少能回覆罐頭句
- [ ] **斷網測試**：只做 observation，不當 hard gate

---

## 三、Brain / Skill 呼叫鏈（P0）

### 3.1 LLM → Brain → Skills

- [ ] **`wave_hello` 執行**：「跟我打招呼」→ accepted + motion
- [ ] **`sit_along` 執行**：「陪我坐一下」→ accepted + motion
- [ ] **`show_status` 執行**：「你現在狀態如何」→ accepted + 狀態回覆
- [ ] **`greet_known_person` 執行**：Roy 入鏡或提案 → 問候 Roy
- [ ] **skill result 回流**：執行後 `/brain/skill_result` 有結果
- [ ] **下一輪能接續**：LLM 知道上一個 skill 成功 / 失敗

> `careful_remind` 是 PAI 主動觸發（看到危險姿勢時），**不是 Roy 喊出來的指令**。已移到 §5.3 pose 測項。

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

- [ ] **不存在 skill**：「後空翻」→ `rejected_or_blocked` 任一，不動
- [ ] **禁用 skill**：「跳舞」→ `blocked` 或 `rejected_not_allowed`，不動（重點是不 motion）
- [ ] **unknown-but-allowlisted 防線**：缺 capability_context 時不應執行 allowlisted skill
- [ ] **invalid skill 不會 motion**：3 次測試 3 次都不能動
- [ ] **Brain 拒絕原因可見**：Studio Trace Drawer 看得到原因

---

## 四、誤觸抑制（P0）

### 4.1 陌生人 / 人臉

- [ ] **Roy 可控站位 greet**：Roy 1.5m 可觸發至少 1 次問候
- [ ] **重複問候 cooldown**：Roy 連續路過，第 2–3 次不狂喊
- [ ] **陌生人累積 5 秒**：不是一入鏡就警告
- [ ] **手 / 反光 / 玻璃**：不出聲打斷
- [ ] **Studio-only 誤判可記錄**：可有 chip，但不可 TTS 打斷

### 4.2 跌倒 / 姿勢

- [ ] **跌倒不出聲打斷**：側躺可出 Studio fall chip，但喇叭不喊
- [ ] **推車 / 椅子誤判抑制**：入鏡 5 秒不出聲打斷
- [ ] **對話中躺下**：TTS 不被 fall alert 打斷
- [ ] **兩條 fall TTS 路徑都靜音**：`FALL_ALERT_TTS` + `POSE_TTS_MAP["fallen"]` 都不出聲

### 4.3 多模態互不干擾

- [ ] **講話中不被人臉打斷**
- [ ] **講話中不被姿勢打斷**
- [ ] **動作中不被 object / pose TTS 插隊**
- [ ] **pending confirm 期間 OK 不誤觸其他流程**

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
- [ ] **側躺 / 躺平**：觀察 fall chip，不出聲
- [ ] **推車 / 椅子**：不出聲打斷
- [ ] **`careful_remind` 主動觸發**：Roy 做 bending 姿勢 → PAI 主動「小心一點」
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

- [ ] **語音輸入顯示**：ChatPanel 顯示使用者語音
- [ ] **PAI 回覆顯示**：ChatPanel 顯示 TTS 文本
- [ ] **歷史保留**：短流程中不消失
- [ ] **頁面切換不中斷對話**

### 6.2 Brain Trace

- [ ] **顯示 LLM 決策**：LLM 想呼叫什麼 skill 看得見
- [ ] **`accepted` chip**：至少出現 1 次
- [ ] **`needs_confirm` chip**：至少出現 1 次
- [ ] **`rejected_not_allowed` / `blocked` chip**：至少出現 1 次
- [ ] **`accepted_trace_only` chip**：至少出現 1 次
- [ ] **11-stage trace**：`input / safety_gate / world_state / capability / memory / llm_decision / json_validate / repair / skill_gate / output / trace`
- [ ] **engine label**：能看到 `langgraph`

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
- [ ] **Trace coverage**：`accepted` / `needs_confirm` / `rejected_or_blocked` / `accepted_trace_only` 都至少出現 1 次

### 7.3 自由互動（OBS）

- [ ] **Roy 15 分鐘自然互動**
- [ ] **第二人 15 分鐘自然互動（如有）**
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

- [ ] **連續運作 30 分鐘**
- [ ] **連續運作 1 小時**：若今天時間不夠，5/12 補
- [ ] **變壓器穩定**
- [ ] **Jetson 不突然斷電**

### 9.2 機構

- [ ] **光達不晃動**
- [ ] **頭盔不脫落**
- [ ] **喇叭不掉**
- [ ] **線材不卡腿**
- [ ] **做 motion 時線不拉扯**

### 9.3 網路 / API

- [ ] **WiFi 穩定**
- [ ] **OpenRouter API 可連**
- [ ] **TTS 延遲 < 15 秒**
- [ ] **Studio websocket 不斷線**

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

- [ ] **動態避障 detour** `SKIP→C`
- [ ] **多 skill 一次輸出** `SKIP→C`
- [ ] **邊講邊動並行** `SKIP→C`
- [ ] **語音控導航 / move_forward 數值** `SKIP→C`
- [ ] **電量 <20% safety** `SKIP→C`
- [ ] **完整參數 range validation** `SKIP→C`
- [ ] **新人現場註冊** `SKIP→C`
- [ ] **Wave 正面 / 轉圈** `SKIP→C`
- [ ] **小物 >2m** `SKIP→C`
- [ ] **Gemini → GPT-5 fallback** `SKIP→C`（沒實作）
