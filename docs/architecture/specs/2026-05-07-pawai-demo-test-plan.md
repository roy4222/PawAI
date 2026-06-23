# PawAI Demo 驗收測試計畫 v1

| 欄位 | 值 |
|---|---|
| 撰寫日期 | 2026-05-07 |
| 撰寫人 | Roy（盧柏宇）+ Claude brainstorm |
| 適用 demo | 5/18 期末展示 |
| 預計使用日 | 今日（5/7-8 fail-map 建立）+ 5/13-14 LM 307 場地測試 |
| 狀態 | v1 / 待 Roy review |

---

## 0. 設計目的

把 5/6 那份大測試清單（~100 項）收斂成 **demo 能不能演完** 的客觀驗收計畫。
不測完整論文系統，不重複會議紀錄已標的「明確放推」項目。
今日跑 fail-map → triage → 修 → 重測，5/13-14 帶到 LM 307 真實場地驗證。

---

## 1. 設計原則

**三大原則**：

1. **兩階段 × 三類分類 × 三層交付物**
2. **Fail-fast-to-record，不 fail-stop**：fail 先記錄不深修，全部跑完再 triage
3. **客觀指標 + demo 反向門檻 + benchmark 數字**：A 類用 demo 不出糗為標準、B 類記成功率給論文

```text
        Part A (5/13 下午 / 今日)        Part B (5/14 下午 / 今日後段)
        ────────────────                ────────────────
        七功能單測                        Studio 統一入口整合
        客觀指標 + demo 反向門檻             demo 主腳本 3 連跑
                ↓                              ↑
        ┌─ A 類 fail → BLOCKER → triage 修 → 重測
        ├─ B 類 fail → OBS 進整合不計分
        └─ C 類       → SKIP（明確放推）
```

---

## 2. A / B / C 分類定義

### A 類：出糗 / 安全 / 會打斷 demo
**Fail 凍結，不進 demo 主流程，必修**。

| 項目 |
|---|
| 語音主鏈：ASR → pawai_brain → brain_node → TTS 任一段斷 |
| `stop` 不生效 |
| invalid skill 會真的動 |
| fall / stranger 會出聲打斷對話 |
| TTS 長句會漏整句或卡死 |
| Studio trace 完全看不到 Brain 決策 |
| Go2 動作不穩、會撞、會摔、會卡 queue |
| 系統 crash / 需要重啟才能繼續 |

### B 類：效果不好但不危險
**5/14 可進整合，但標 OBS，不計分，不擋 demo 流程**。

| 項目 |
|---|
| Roy 人臉 5 次只中 2-3 次 |
| 物體（特別是杯子）辨識不穩 |
| 姿勢彎腰 / 蹲下不穩 |
| 手勢 wave 不穩 |
| 天氣回答不夠漂亮 |
| 語氣不夠自然但沒有漏字 |
| 導航只能直走，不能繞障 |
| TTS 首句延遲偏高（10s 上下）但能播 |

### C 類：明確放推（不進主流程）
**Spec 末尾備註，避免日後忘了是有意 skip**。

| 項目 |
|---|
| 動態避障（detour） |
| 多 skill 一次輸出 |
| 邊講邊動並行 |
| 語音控導航（move_forward(0.5) 等數值） |
| 電量 <20% safety |
| 完整參數 range validation |
| 新人現場註冊 |
| 動態手勢 wave 正面、轉圈 |
| 小物 >2m 辨識 |
| Gemini → GPT-5（沒實作此鏈路） |

---

## 3. 交付物三層

| 層 | 內容 | 用途 |
|---|---|---|
| **L1 現場簡化 Markdown** | PASS / FAIL→A:BLOCKER / FAIL→B:OBS / SKIP→C + 一句註解 | 現場快速勾選，不負擔注意力 |
| **L2 Studio trace log** | 自動保留，每次 LLM decision / skill_gate / accepted / rejected / needs_confirm | 事後查 root cause |
| **L3 手機錄影** | 拍機器狗 + Studio 大螢幕 | 事後補 TTS 延遲、誤觸次數、動作是否成功 |

**事後整理**：影片 + Markdown + trace log → 整合進 Google Sheet 給組員 / 老師。**現場不開 Sheet**。

### L1 記錄格式（每項一塊）
```md
## [#X] <功能> / <子項>
結果：PASS / FAIL / OBS / SKIP
分類：A / B / C
觸發：（語句、動作、姿勢）
預期：
實際：
Trace/topic：（看到什麼）
是否可重現：YES / NO / 未試
下一步：（修哪一行 / 觀察 / 不動）
```

---

## 4. Part A — 七功能單測

**預算**：4 小時（含 30 分鐘緩衝）。Fail-fast-to-record：fail 不深修、繼續跑。

**例外**：若 build / launch / full demo startup 無法成立，或出現安全風險（會撞、會摔、會卡 queue），**立即暫停測試先修**；其他 fail 才記錄後集中 triage。

### 順序（9 步）

| # | 項目 | 預算 | 為什麼這個順序 |
|---|---|---|---|
| 1 | Build / import / full demo 啟動 | 15m | 先驗 startup baseline |
| 2 | 語音主鏈 | 40m | ASR/Brain/TTS 是其他所有的依賴 |
| 3 | Studio × Brain | 30m | 純軟體可平行驗、capability_context 注入 |
| 4 | 手勢辨識 | 20m | 信心度最高，先建立基準 |
| 5 | 人臉辨識 | 25m | 次穩 |
| 6 | 姿勢辨識 | 25m | 預期不穩 |
| 7 | 物體辨識 | 20m | 預期不穩 |
| 8 | 導航避障 | 30m | 最佔空間最重，環境不就緒可降為 nav_ready + reactive_stop 快驗 |
| 9 | 重跑所有 BLOCKER | 30m | 確認可重現再進 triage |

### 各項 A 類門檻 + B 類觀察數字

#### #1 Build / import / full demo 啟動
- **A 類門檻**：
  - 三套 colcon build 成功（pawai_brain / interaction_executive / vision_perception / speech_processor / face_perception）
  - full demo tmux 起得來，所有 node 不 crash
  - 拿得到 `/state/perception/face` / `/event/gesture_detected` / `/event/pose_detected` / `/event/object_detected` / `/brain/proposal`
- **B 類觀察**：startup 總時間、warmup 完成後 RAM 用量

#### #2 語音主鏈
- **A 類門檻**：
  1. ASR → Brain → TTS 五輪不斷（同一 session）
  2. `stop` / `停` 關鍵字立即靜音
  3. 長句不漏整句、不卡死
  4. 拔網 10s 後 RuleBrain 接得回（不 crash）
- **B 類觀察**：TTS 首句延遲 P50 / P95；對話記憶能否記住 Roy；天氣 / 時間是否帶入；persona v3 語氣
- **Fail 分流**：
  - full demo 起不來 → 修啟動（前置 blocker）
  - 某句 LLM/TTS fail → 記 OBS，繼續往後測

#### #3 Studio × Brain
**路由前提**：`pawai_brain` LangGraph **只訂語音輸入**（`/event/speech_intent_recognized`）。Studio chat 走 `/api/text_input` → `/brain/text_input` → `brain_node` synthetic speech buffer，**不進 LangGraph capability_context / LLM 提案路徑**。Studio button 走 `/skill_request` 直發 Executive，是手動 skill 路徑。
- **A 類門檻**：
  1. **語音輸入**觸發 8 條 demo-safe skill，DevPanel 看得到對應 11 stage trace
  2. `跳舞` / `後空翻`（語音）必為 blocked / rejected
  3. Studio Trace Drawer / DevPanel（`?dev=1`）顯示 `accepted` / `needs_confirm` / `rejected_or_blocked` / `trace_only` 四種狀態
  4. Studio button「完整自我介紹」直發 skill_request，6-step sequence 跑完
- **B 類觀察**：self_introduce trace_only 是否清楚標示、capability_context chip 是否顯示對、Studio chat 文字輸入路徑（synthetic speech）是否能跑通對話

#### #4 手勢辨識
- **A 類門檻**：
  1. Palm / Thumbs_up / Peace / OK 各能在可控姿勢觸發 ≥1 次
  2. OK 二次確認 5s state machine 走完一輪
- **B 類觀察**：5 次中成功幾次、Wave 側面成功率、Fist 辨識率

#### #5 人臉辨識
- **A 類門檻**：
  1. Roy 在可控站位觸發 ≥1 次 greet
  2. 連續路過第 2-3 次 cooldown 內**不重複問候**
  3. 陌生人 / 手 / 反光**不出聲**（Studio-only 紅 chip 可記錄不擋）
- **B 類觀察**：Roy 5 次成功幾次、陌生人 5s 累積觸發率、track 抖動次數

#### #6 姿勢辨識
- **A 類門檻**：
  1. 站、坐至少各觸發 1 次正確姿勢分類
  2. 跌倒（側躺）**不出聲打斷對話**（Studio 紅 fall chip OK）
  3. 推車入鏡 5s 不誤判跌倒出聲
- **B 類觀察**：站 / 坐 / 躺 各 5 次成功幾次、蹲穩定度

#### #7 物體辨識
- **A 類門檻**：
  1. 至少 1 個純色大物（椅子 / 人）<1.5m 觸發 object_remark
  2. `看到 X 色的 Y` TTS 模板正確
- **B 類觀察**：椅子 / 杯子 / 人 各 5 次成功幾次、色彩判定正確率

#### #8 導航避障
- **A 類門檻**（場地就緒）：
  1. AMCL warmup 後 `goto_relative 1.0m` 跑得到
  2. 中途放紙箱 reactive_stop 真的停
  3. 移走後 resume 能繼續
  4. 整輪不撞、不摔、不卡 queue
- **A 類門檻（場地不就緒，降級）**：
  - `nav_ready` true、`depth_clear` 對障礙翻轉、`reactive_stop` 對 fake 障礙停
- **B 類觀察**：停車 distance、resume 延遲、odom 漂移量

#### #9 重跑所有 BLOCKER
- 確認 fail 可重現 → 進 triage
- 不可重現的 fail 標 `INTERMITTENT`，triage 時降一級

---

## 5. Part B — 整合測試 = 5/18 demo 主腳本 v0

**核心理念**：Part B 不是另一份測試，**它就是 5/18 demo 主腳本的 v0**。今天跑完 Part B 改完 bug，5/14 跑出來的腳本就是 5/18 demo 用的。

### 主腳本（10 步）

```text
[ 開場 ]
S0  Roy 入鏡 1.5m → greet
    （沒觸發改手動語音開場，不中止）

[ 介紹環節 ]
S1  「你可以做什麼」→ 六大功能 + Studio guide chip 高亮
S2  「介紹一下你自己」→ trace_only（狗不動，只說介紹文）
S3  Studio button「完整自我介紹」→ 6-step sequence

[ 功能登場（語音主控）]
S4  「跟我打招呼」或 Wave 側面 → wave_hello execute
S5  拿紅杯 / 椅子 < 1.5m → object_remark（PASS or OBS，不擋）
S6  「搖一下」→ needs_confirm → 比 OK → wiggle execute
S7  「陪我坐一下」→ sit_along execute

[ 邊界與安全 ]
S8  Roy 側躺 / 推車 → Studio 紅 fall chip + 不出聲打斷
S9  「跳舞」/「後空翻」→ LLM 婉拒 + trace blocked / rejected
S10 「停」→ 立即靜音 + stop
```

### 通過標準（三層門檻）

#### Hard gate（3 輪 0 容忍）
- 誤觸 TTS 打斷對話 = 0
- invalid skill 真的動 = 0
- `stop` 失效 = 0
- 系統需重啟 = 0

#### Demo flow gate
- 3 輪至少 2 輪完整順跑（不需中途重啟）

#### Trace coverage
- `accepted` / `needs_confirm` / `rejected_or_blocked` / `trace_only` 四種至少各出現 1 次

#### Perception 不當 hard gate
- 人臉 / 物體 / 姿勢 / 手勢 記成功率不擋 demo
- 例外：會出聲打斷的誤觸仍算 Hard gate fail

### 預算

| 區段 | 時間 |
|---|---|
| 主腳本 3 連跑 | 45m（每輪 ~12m + 重置 3m）|
| 自由互動 | 30m |
| Trace coverage 補測 / 緩衝 | 15m |
| **合計** | 90m |

### 自由互動環節（30 分鐘）

- Roy + 1 位老師輪流跟 PAI 互動 15 分鐘 × 2 輪
- 不照腳本，純看自然互動感
- **只記 observation**：demo 觀眾視角清晰度、誤觸出現幾次、感覺自然程度
- 不設 A 類門檻（會議紀錄已定「自然互動為最重要」是質性目標）

---

## 6. Triage SOP（fail-map 收完即動）

**原則**：今日跑完 §4 + §5 後立刻 triage，不等 5/14。

### 流程

```text
1. 收集所有 FAIL→A:BLOCKER 條目
2. 每條 reproduce 一次驗證可重現性
3. 按優先序排隊（見下表）
4. P0 全修完才動 P1，P1 全修完才動 P2
5. 每修一條：寫一行 fix note + 重跑該項驗證 → 過了才下一條
6. 不修 B / C 類（除非 root cause 跟 A 類同源，順手修）
7. 全部修完跑一輪 §5 主腳本，確認無 regression
```

### 優先級

| Pri | 內容 |
|---|---|
| **P0 demo blocker** | full demo 起不來 / ASR → pawai_brain → brain_node → TTS 主鏈斷 / `stop` 失效 / invalid skill 真的動 / 誤觸 TTS 打斷 / 系統 crash 需重啟 / 會撞 / 會摔 / queue 卡死 |
| **P1 單一展示路徑斷** | `wave_hello` 不跑 / `wiggle needs_confirm` 不通 / `self_introduce trace_only` trace 不對 / Studio 某個 chip 顯示錯 / 某一個 perception demo 不穩 |
| **P2 品質 / 數字不好** | TTS 延遲偏高但能播 / Roy 5 次只中 2 次 / 物體顏色不準 / 姿勢成功率低 / 語氣不夠自然 |

### 修法守則

- **fail-map 收完才動手**，不要邊測邊修（避免污染後續測試）
- **例外**：若 build / launch / startup 無法成立，或出現安全風險（會撞、會摔、會卡 queue），立即暫停測試先修
- **修一條測一條**，不堆積
- **改參數優先於改邏輯**（YAML threshold > Python rule > 架構動）
- **改完跑一輪 §5 主腳本**，確認沒 regression

---

## 7. C 類明確不測清單（避免日後忘了是有意 skip）

| 項目 | 為什麼 skip |
|---|---|
| 動態避障（detour） | L3 PASS 失敗根因為 nav_action_server max_speed 不 enforce + AMCL plateau bug，5/03 已知 |
| 多 skill 一次輸出 | persona / policy 設計上一次最多一個 skill |
| 邊講邊動並行 | 目前是序列，不是並行；TTS / motion timing 未同步 |
| 語音控導航 / move_forward(數值) | 5/8 系統設計上語音不開 nav |
| 電量 <20% safety | 硬體 telemetry 沒接 |
| 完整參數 range validation | 目前只做 args 非 dict 歸 `{}`，沒有完整 schema gate |
| 新人現場註冊 | face_db 為 demo 期固定 alice / grama / Roy |
| Wave 正面 / 動態手勢轉圈 | 會議已定「正面 wave 預期失敗」 |
| 小物 >2m 辨識 | YOLO / D435 解析度不足 |
| Gemini → GPT-5 鏈路 | 沒實作。實際路徑：**LangGraph primary**（`pawai_brain`）= Gemini → DeepSeek → RuleBrain；**legacy llm_bridge_node** = Gemini → DeepSeek → vLLM → Ollama → RuleBrain。Demo 走 LangGraph primary |

---

## 8. 參考資料 — 七 agent 盤點 file:line 索引

### Brain × Studio
- LangGraph：`pawai_brain/pawai_brain/graph.py:31-63`、`nodes/*.py`（11 stage）
- Brain node MVS：`interaction_executive/interaction_executive/brain_node.py:1-500+`
- Skill registry：`interaction_executive/interaction_executive/skill_contract.py:127-640`（27 skills）
- Pending confirm：`interaction_executive/interaction_executive/pending_confirm.py:70-150`（5s state machine）
- Capability builder：`pawai_brain/pawai_brain/capability/registry.py:44-100`、`effective_status.py:26-71`
- Demo guides：`pawai_brain/config/demo_guides.yaml:1-37`（六大功能）
- Studio chat：`pawai-studio/frontend/components/chat/chat-panel.tsx:57-180`
- Studio trace：`pawai-studio/frontend/components/chat/brain/skill-trace-content.tsx:45-150`
- Studio gateway：`pawai-studio/gateway/studio_gateway.py:59-71`（WS 路由）

### Perception
- Face：`face_perception/` + `face_perception/config/face_perception.yaml:23` `sim_threshold_upper:0.40`
- Stranger 累積：`interaction_executive/config/executive.yaml:8` `unknown_face_accumulate_s:5.0`
- Gesture：`vision_perception/vision_perception/gesture_classifier.py:14-65`
- Pose：`vision_perception/vision_perception/pose_classifier.py:23-31` + akimbo / knee_kneel L223-375
- Object：`object_perception/object_perception/object_perception_node.py:1-127`（YOLO26n + 12 色 HSV）
- Fall TTS 雙路關閉：`vision_perception/vision_perception/event_action_bridge.py:61` `FALL_ALERT_TTS=""`

### Speech
- LLM bridge：`speech_processor/speech_processor/llm_bridge_node.py:176-181`（fallback 鏈）+ deque(maxlen=10)
- Persona v3：`tools/llm_eval/persona.txt`（4777 bytes）
- TTS chunking：`speech_processor/speech_processor/tts_split.py`（30 字句切 + 40 字 chunk + comma -1）

### Navigation
- Nav capability：`scripts/start_nav_capability_demo_tmux.sh`
- Reactive stop：`go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`
- Depth safety：`go2_robot_sdk/go2_robot_sdk/depth_safety_node.py`

---

## 9. 風險與已知限制

| 風險 | 緩解 |
|---|---|
| TTS 首句延遲 ~10s（會議基線） | 接受，Demo 話術預留等待 |
| 拔網 → RuleBrain 文案有限 | 補 1 句「我現在連不到雲端」（P2 改） |
| `wave_hello` 30s cooldown 數值找不到 | 5/13 現場驗 Roy 路過 5 次不狂喊 |
| repair.py Phase 2 stub | Gemini 怪輸出時 fallback 文字呆板，可接受 |
| 跌倒誤判推車 | ankle-on-floor gate + FALL_ALERT_TTS="" 雙保險 |
| 物體 >2m 辨識 | demo 話術引導 Roy 拿到 <1.5m |
| Jetson 過熱 / 連續 1h | 5/12 場地測試先驗 1h baseline |

---

## 10. 後續時程

| 時段 | 內容 |
|---|---|
| **今日（5/7 night → 5/8）** | Part A 4h + Part B 90m fail-map → triage 修 P0/P1 |
| **5/12 晚 8:00** | 機器狗送到 LM 307，跑 30 分鐘 1h baseline 硬體穩定性 |
| **5/13 13:00-17:00** | 用本 spec 重跑 Part A 七功能（4 小時） |
| **5/14 13:00-17:00** | Part B 整合 3 連跑 + 自由互動 + 5/14 上午只修 A 類 P0 |
| **5/15-17** | 每天跑一次 Part B 完整流程，bug fix |
| **5/18 上午** | 最後 Checklist（會議紀錄 §10.1 / §10.2 / §10.3） |
| **5/18 期末展示** | — |

本 spec 在 5/13 / 5/18 之間視 fail-map 結果迭代版本（v1 → v2 → ...）。每次大改在文件末尾追加 Changelog。

---

## Changelog

| 版本 | 日期 | 改動 |
|---|---|---|
| v1 | 2026-05-07 | 初版（Roy + Claude brainstorm，7 agent 盤點為依據） |
| v1.1 | 2026-05-07 | Roy review fix：(1) #1 startup gate topic 改 face state + perception events；(2) #3 Studio × Brain 標清楚 LangGraph 只訂語音輸入、Studio chat 走 synthetic speech、Studio button 走 skill_request；(3) §7 fallback 鏈路區分 LangGraph primary vs legacy llm_bridge |
