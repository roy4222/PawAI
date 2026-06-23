# PawAI Brain 設計深挖 + 待改進 plan（6/9 晚 HITL）

> 來源:workflow `wkno55fam`（5 agents,file:line 核對過）。情境:明天錄 demo,HITL 三大污染源 = gesture 預設開著、face flicker、brain 無 demo phase。

## 1. 現況仲裁模型（一頁）

**仲裁分兩 node、brain 層沒有 priority。**
- **提案層 `brain_node.py`**:每感知 handler 訂一 topic、各自跑 gate,過了就 `_emit()` → `/brain/proposal`。**無跨感知優先序**,先過自己 gate 的先佔。
- **執行層 `interaction_executive_node.py`**:才有搶佔。`_on_proposal:95` 只認 `priority_class` —— SAFETY(0)/ALERT(1) 會 `queue.clear()` + abort + `push_front`;SEQUENCE/SKILL/CHAT 一律 FIFO,彼此不分大小。
- `state_machine.py` 是 legacy 空殼,runtime 不跑,真相在 `brain_node.py`。

各路徑 gate:

| 事件 | 可發 skill | gate |
|---|---|---|
| speech `:463` | stop_move / say_canned / chat_reply | 「停」繞所有 gate `:483` → unsafe → active/dedup → buffer |
| gesture `:737` | wave/pause/mute + wiggle/stretch(confirm) | **gesture_enabled `:748`** → pending → active-skill → **1s dedup `:766`** → 對話 gate(只擋 wave/fist/index) |
| face `:1039` | stranger_alert / greet | stranger: cooldown30 + attention≠IDLE + not active/pending/tts;greet: stable + sitting3s + 20s/人 |
| pose `:1141` | fallen / sit_along | fallen: 2s + cooldown15(不過 active/pending/tts);sitting/bending: 自帶 cooldown |
| object `:1220` | object_remark | **最嚴**: attention==ENGAGED + not active/pending/tts + 60s/class dedup |

**核心病灶**:`active_plan` / `pending_confirm` / `tts_playing` 是**全域共享單一 token,任一被佔,所有 gate 一起黑掉**,而 brain 層無 priority 讓高優先繞過。gesture 門檻最低(不讀 attention、dedup 1s 形同虛設、連對話 gate 都不過)→ 手一比 thumbs_up 立刻進 PendingConfirm **綁架 30s**,期間 greet/stranger/object/sit_along 全靜音。

## 2. 核心設計問題（根因各一句）

1. **gesture 污染**:`vision_perception_node.py:356-357` 把 recognizer raw confidence 丟進 `_` 丟棄 → 握杯/托腮靜止手被低信心硬分類 thumbs_up;1s dedup 形同虛設 + 30s confirm re-fire → 週期性自言自語。
2. **無 demo phase**:brain 只有一堆獨立 bool,`_on_set_params:247` runtime callback **只認 gesture_enabled 一個 key**;`/brain/demo_segment` 是給 LLM persona 的 prompt 注入,不 gate 感知。
3. **無跨感知優先序**:brain 層先到先佔,priority 只在下游 IE 且只兩級,ALERT gate 還不一致(fallen 能搶、stranger 被擋)。
4. **face 不穩**:`face_identity_node.py:400` 用 **max-over-samples**(非 centroid)對參差 enrollment 極敏感;enroll det 0.90 vs runtime 0.35 分布不匹配;hysteresis 死區 0.22-0.40 太窄 + stable_hits=2 → flicker。

## 3. 待改進 plan

### P0 — demo-blocking（今晚,~1 天）
- **P0-1 gesture 預設關（治本第一手、零 code）**:demo 啟動 `ros2 param set /brain_node gesture_enabled false`,錄到手勢段(S4)再 `true`。現成 declare `:283`/gate `:748`/callback `:247`。風險無。
- **P0-2 Studio Gesture On/Off toggle（讓 P0-1 不靠 SSH、0.5 天）**:gateway 走 topic 不用 param service。複製 `/api/reset` 模式:新 Bool topic `/brain/gesture_enabled`(gateway 發、brain 收)。4 處範本:brain import Bool + create_subscription(仿 `:232`)+ handler;gateway publisher(仿 `_reset_pub:196`)+ method(仿 `:452`);REST(仿 `/api/plan_mode:708`);frontend 複製 `use-toggle-plan-mode.ts` → `use-toggle-gesture.ts` + 按鈕 `skill-buttons.tsx:40`。
- **P0-3 分段 gating（demo_phase,時間夠才上）**:加 `demo_phase` string param,`_on_set_params:250` 認,每感知 handler 開頭 early-return。先做 P0-2 tracer bullet 驗 Bool 通道再疊。

### P1 — 治本（demo 後或有餘）
- **P1-1 gesture confidence 門檻（治本）**:`vision_perception_node.py:104` 後 declare `gesture_recognizer_min_conf`(0.7);改 `:355-357` 用 raw score 守門不丟棄。真 thumbs_up 通常 >0.85、握杯 0.4-0.6。須 colcon build vision + 重啟。
- **P1-2 confirm per-gesture cooldown 35s**:`:824-829` request_confirm 前加 `confirm_req:{gesture}` cooldown ≥ timeout 30s。**保留兩步 WeGo,不動 thumbs_up_demo_ack**。
- **P1-3 event priority preemption**:獨立 follow-up,**不塞 demo PR**(effort 2-3 天、風險高)。

### P2 — refactor（future）
統一 arbiter 按 priority_class 比大小;gate token 分級(safety/alert 繞過 tts/active);demo_phase 升正式狀態機。

> **Roy 6/9 加碼決策**:手勢**改 peace（比耶✌️）取代 thumbs_up**(比讚握東西太易誤觸)。peace 走同一 recognizer → **P1-1 門檻仍必做**(OK 確認鍵也誤觸);換 peace 時關 `peace_direct_stretch`、WeGo 台詞特例改綁 peace。

## 4. face 救援 SOP（Roy 說 face 其實 OK、不是困境 → 降優先,但記著）
Step0 清 face_db 幽靈目錄(`_backup/old`)+ rebuild + 重啟 → Step1 `save_debug_jpeg` 分離偵測 vs 識別 → Step2 framing 先於門檻(D435 角度對齊坐姿頭部,解 face_count=0)→ Step3 清第二臉 + 關 stranger_alert 或 `unknown_face_accumulate_s` 3→8 → Step4 re-enroll @ demo 距離光線 → Step5 re-enroll 後才調 sim threshold。
**S2 greet 降級樹**:sim 穩≥0.5 → `greet_require_sitting false`(A);抖但到 0.5 → 放寬黏性(B);到不了 → 去具名「我看到有人」或揮手當入口(C);整片不可靠 → S2 退純 object/gesture/safety(D)。

## 5. 不要做
不設 `thumbs_up_demo_ack=true`(退回一步,違反兩步 WeGo);不在 demo PR 塞 priority preemption(P1-3);face 沒 re-enroll 前不調 sim threshold(會把 roy 推進 unknown)。

**關鍵檔**:`brain_node.py`(gesture_enabled `:283/748`、callback `:247`、greet sitting `:1122`、confirm `:824`)、`vision_perception_node.py:356-357`、`face_perception/config/face_perception.yaml:11-24`、`face_identity_node.py:400`、`studio_gateway.py`(toggle 範本)。
