# Live Demo 迭代發現報告（2026-06-14）

> 狀態：研究 + 計畫，零 runtime code 變更、未發 GitHub issue
> 來源：2026-06-14 Roy 在場 live HITL 試跑 + 6 條 lane 研究結果（Act1 nav / S3 object / object A-B / S2 face / S4 gesture / S5 safety / demo-flow / CLI 跨平台 / nav-single-driver）
> 範圍：6/18 發表前的段落穩定化；以「症狀為準」分流根因，先穩 S2-S5、後決 Act1 fallback

---

## 1. TL;DR

6/14 live HITL 的整體結論是「四互動段落（S2/S4/S5）已 PASS、S3 是可純軟體修復的 brain 端 bug、Act1 導航避障是唯一硬卡關但本質是診斷分叉樹而非單一失敗點」。S2 認人問候、S4 手勢確認、S5 安全拒絕三段在 live config 下不只「看起來能用」，而是與程式碼路徑一致的真 PASS（S5 是 rule-first 0s、no-LLM、執行層 banned_api reject，結構上無法被繞過）。S3「辨識到 cup 卻一直講手機」的真兇主要在 Brain 端：cell_phone(id67) 同時在 object_perception 白名單與 OBJECT_CLASS_ZH，Brain 又只取 `objects[0]`（YOLO 信心最高者），全鏈無 class 優先排序，phone 信心常高於桌上小 cup 就永遠搶話——這完全是純軟體可修，不需換模型。Act1 失敗的最高優先動作不是修導航，而是先用 Roy 給的 Stage1 量值（LiDAR 11.9Hz 活、front±15°=2.09m、+20°=1.70m）分流到正確的診斷分支，並在收工前 `pawai evidence pull` 保住當天證據。本輪原則：先把 S2-S5 穩住，再決定 Act1 用哪個 fallback，不要先大修導航（導航最容易吃掉整晚）。

### 段落狀態表

| 段落 | 狀態 | 根因（一句） | 6/18 影響 |
|------|:----:|------|------|
| **Act1 導航避障** | ❌ FAIL | 不是單一失敗點而是診斷分叉樹；當天到底跑哪個 topology（standalone reactive_stop vs progressive+goto）未知＝80% 分支的根；LiDAR 活但前錐讀 2.09m 淨空＝reactive 沒看到障礙（最可能：障礙低於 ~0.50m 掃描平面） | P0：nav motion 維持 NOT_DEMO_READY，退 fallback②（遙控+Foxglove LiDAR 證據）/ ③（影片）；A 層（standalone reactive_stop 障礙停）僅 Roy+e-stop upside |
| **S2 認人問候** | ✅ PASS | live config `greet_require_sitting=false`，靠 face stable+20s cooldown，不依賴 sitting/LLM/depth；台詞靜態 template 不會 dead air | GO；唯一單點故障＝face_db sim 老化，須 demo 前現場光線 re-enroll + face_db 衛生 |
| **S3 物品關懷** | ⚠️ DEGRADED | Brain 只取 `objects[0]` + 無 class 優先 + cell_phone 在白名單＝phone 永遠搶話；object_remark 卡 ENGAGED gate 慢一拍；pose 邊緣觸發（一直坐著不發事件）讓 sitting context 不更新 | P0：純軟體可修（whitelist 收 cup-only 或 brain class 優先排序）；pose 改加分非硬依賴 |
| **S4 手勢確認** | ✅ PASS | peace→OK 二確認→Go2 wiggle，與 `peace_wego_confirm=true` 路徑一致 | GO（需鎖配置：只留 peace、關 Studio 手勢按鈕、wiggle 屬 forbidden motion 需 Roy+e-stop） |
| **S5 安全拒絕** | ✅ PASS | rule-first（unsafe_request 在 LLM 之前 return）+ 執行層 validate banned_api:1301，雙層防線、phase-independent | GO；維持 backflip 已 proven 端到端；6/18 主線走 Studio 文字觸發規避 ASR 誤聽 |
| **整體 demo 流程** | ⚠️ 機制穩、flow 有風險 | 手動 phase 切換機制穩；但 auto_advance 預設 OFF＝never-dead-air 全靠操作員手按；offline_mode topic 不寫回 param＝驗證陷阱；operator-runbook 契約備註已過時 | P0/P1：靠彩排分派計時+canned 觸發角色；runbook docs 6/17 前必更新 |

---

## 2. 各段落根因分析

### 2.1 Act1 導航避障（❌ FAIL — P0）

**現象**：Act1 障礙停沒成功。Roy 列候選含「Go2 沒動 / Go2 走歪 / reactive_stop 沒啟 / cmd_vel 沒到 driver / 障礙高度不在 LiDAR 掃描平面 / LiDAR 沒看到」——這些候選互斥，代表連「當天是哪種啟動形態」都還沒確定。Stage1 已量到 LiDAR 11.9Hz 活、front±15°=2.09m、+20°(右前)=1.70m。

**Ranked 根因假設**：

1. **(最根本) Act1 當天跑哪個 topology 未知＝診斷分叉的根**。standalone reactive_stop（`start_reactive_stop_tmux.sh`，Go2 靠 `normal_speed=0.60` 自走遇障停、不靠 AMCL/goto）vs progressive nav stack（`start_nav_capability_demo_tmux.sh`，Go2 靠 goto_relative 前進、reactive_stop 只在 danger 發 0 pause nav）。若是 progressive，失敗症狀應是「走歪/超衝」（6/13 R1/R2 已撞牆）而非「沒動」；若是 standalone 且 Go2「沒動」→ 是 cmd_vel 沒到 driver 或 warmup/mux 問題；若 Go2 動了沒停 → LiDAR 沒看到障礙。
2. **(最可能技術因) LiDAR 活但前錐讀 2.09m 淨空＝reactive 沒看到障礙**。RPLIDAR A2M12 是 2D 單線掃描，掛 base_link+0.18m、base_link 離地 ~0.32m → 掃描面約離地 0.50m。任何矮於 ~0.50m 的障礙（矮箱/腳/椅面/抱枕/狗碗）完全不在掃描面 → front±15° 讀到的是背後 2.09m 的牆。
3. **progressive mode 在 slow band 沉默 + 側前 +20°(1.70m) 落 slow band**。open_space slow band（danger 1.1 / slow 1.7），+20°/1.70m 恰在邊界內側；progressive 在 slow/clear 回 None（沉默），只在 danger 發 0 → 側前 1.70m 家具「被看到了但不會觸發停」。
4. **(若 Go2 沒動) cmd_vel 沒到 driver / mux 鎖死 / MIN_X 門檻**。standalone 覆寫 `cmd_vel_topic:=/cmd_vel` 直連 driver，但若殘留 twist_mux（上次 nav session 沒清）→ reactive 發的 0.60 被 mux 蓋掉；或 `slow_speed=0.45 < MIN_X 0.5` 被 Go2 silently 忽略，slow band 不抬腳看起來「沒動」。
5. **(若 Go2 走歪) 6/13 已查根因重演**：R1 AMCL map-frame yaw 注入「前方」斜走 + R2 goto 不 enforce max_speed 超衝（0.5m→1.04m）+ T0 URDF 把 map→odom/odom→base_link 當 fixed joint 發 /tf_static 雙 authority 衝突（CO-PRIMARY，須先 `echo /tf_static` 排除）+ R5 靜態閘 yaw-blind。

> **Codex 交叉檢查（見 [`2026-06-14-codex-second-opinion-act1-s3.md`](2026-06-14-codex-second-opinion-act1-s3.md)）**：對著參數算，Stage1 量值（正前 2.09m clear、右前 1.70m 邊界 slow）**在現有門檻 `danger=1.1 / slow=1.7` 下本來就不該觸發 stop**。所以 Act1「沒成功」最可能是 ① 障礙物太矮（不過 ~0.50m 掃描面）② 障礙放太遠（>1.1m，Go2 走到 1.1m 前就該停但沒走到）③ Go2 根本沒走（standalone `slow_speed=0.45 < MIN_X 0.5`，Go2 收到 Move 0.45 silently 忽略，看起來像「沒動」）。Codex 並提醒：**Act1 是 standalone 路徑（`/scan → reactive_stop → /cmd_vel → driver`），不要硬套 Nav2/AMCL/T0 那套 progressive 故障模型**，會分散注意力。

**需查證據**（全 no-motion，收工前優先）：當天 tmux session 名與啟動指令；`ros2 node list`（幾個 go2_driver）；`ros2 action list | grep goto`（殘留 active goal）；`pawai evidence pull` 拉 [PR1a] goto log（有=goto 路、無=standalone 路）；`echo /tf_static --once`（排除 T0，最高優先）；障礙物實際高度/材質；`lidar_front_sector.py --once` 障礙物放正前 1.0m 是否讀 ~1.0m。

**可修方案**：診斷先行確認 topology；6/18 Act1 障礙停鎖定 standalone reactive_stop（不用 progressive+goto，那條綁 6/13 走歪根因）；障礙物寫死 >0.6m 高、不反光、放正前 ≤1.0m，或乾脆用「人站正前」（人高度必過掃描面，trackB 6/8 NAV-2 已用人/箱 1.03m 驗過 danger 停）；indoor_tight ±18° 窄錐必綁低速 ≤0.2 m/s；改 profile 必 kill 重啟帶參數（`front_arc_deg`/`danger`/`offset` 只在 `__init__` 讀）。

**6/18 fallback ladder（建議當天採層）**：
- **B 層（預設主線）**：遙控/手推障礙 + Foxglove `/scan_rplidar` 點雲 + reactive zone 狀態當「邊緣端即時感知」證據，零 motion 風險（Go2 站著、移動的是障礙物），100% 可交付。
- **A 層（Roy+e-stop upside）**：standalone reactive_stop live 障礙停，僅在 Roy 在場 + e-stop 就位 + 障礙物高度過 LiDAR 平面 + indoor_tight 窄錐重驗無誤擋後升上，人站正前最穩、最多一次，不穩立刻退。
- **C 層（永遠保底）**：S1 影片已錄（demo snapshot tag），旁白用保守版。

**優先級**：P0。**需 HITL**：是（topology 確認、障礙物高度驗、e-stop 就位皆需 Roy 在場；本輪只做 no-motion 診斷，不發任何 goto/forward）。

---

### 2.2 S2 face greet 穩定性（✅ PASS — GO）

**現象**：Roy 一靠近約 2 秒就 greet、人臉辨識快、3m 也 OK；且 S3 觀察到 pose(sitting) 沒出，但 S2 greet 仍正常觸發。

**Ranked 根因假設（為何 PASS）**：

1. **(最可能) live demo 走 `interaction_executive.launch.py` 載入 `executive.yaml`，已設 `greet_require_sitting=false`**——greet 不硬依賴 sitting，與 Roy「~2 秒就 greet、沒 pose 也觸發」完全一致。`demo_phase="all"` 使 `_phase_allows("greet")` 永為 True，`stranger_alert_enabled=false` 移除了 6/9 黑屏真兇。
2. **觸發路徑＝unknown→known 的 identity_stable 事件**（`face_identity_node.py:709-718`）→ `brain_node._on_face` → 20s/人 cooldown + skill contract 60s cooldown 雙層防重複；台詞為靜態 template「{name}，歡迎回來，我看到你了。」+ MOTION hello，不依賴 LLM、不會 dead air。
3. **(陷阱) brain code default 是 `greet_require_sitting=True`（`brain_node.py:774`），yaml override 才是 false**——有人若用 code default 判斷會誤以為 S2 有風險。

**收斂風險（不擋 PASS、但降穩定度）**：

- **face_db sim 老化是 greet 整條路徑的單點故障**（最高優先）。6/8 研究記錄 Roy 舊圖 sim 掉到 ~0.2 被判 unknown、re-enroll 後回 0.73-0.81。greet 不讀 depth（低光不會因深度抖動而擋），低光只影響 RGB 端 YuNet 偵測 + SFace sim 老化。
- **greet 是純 event-only**（進場 unknown→known 才觸發），Roy 一直在框內不會重問；重現 greet 須離框 ~5s（track_lost 後重進）；skill contract 60s cooldown 比 brain 20s 更長，是彩排連拍的真正瓶頸。
- **face_db 子目錄黑名單未實裝**，`_backup`/`old` 殘留會被 `train_model` 當幽靈身份稀釋 centroid。

**可修方案**：demo 前在現場光線下 re-enroll Roy + retrain（`pawai face enroll --person-name roy` → `pawai face rebuild` → 重啟 face node），備份資料夾務必移到 face_db **外**；現場保底 `ros2 param set /brain_node greet_require_sitting false`；站位 SOP 寫進 runbook（從鏡頭外走入或先遮臉 ~5s）；彩排前 `ros2 param set /brain_node greet_cooldown_s 3`、正式前改回 20。

**優先級**：機制 P0（確認 yaml）、衛生 P0（re-enroll）。**需 HITL**：是（現場 re-enroll + sim 量測需 Roy 在 Jetson）。

---

### 2.3 S3 物體辨識 / 關懷台詞（⚠️ DEGRADED — P0）

**現象**：杯子放面前 ~1m，UI 跳 cup，但 Brain 不講杯子、一直講 Roy 的手機(phone)；Brain 也沒偵測到 Roy 坐著（pose 沒出）。Roy 要求：cup 優先講、bottle 等也可講但 cup 優先、pose 只當加分不可卡住 S3。

**Ranked 根因假設**：

1. **(真兇 P0) `objects[0]`-only 選取 + 全鏈無 class 優先序 → phone 信心高就永遠搶話、cup 被丟**。producer `_publish_events` 依 YOLO NMS 信心降序建 `new_objects`，brain `parse_object/_on_object` 只取 `objects[0]`，全鏈零 class 排序 → 桌上小 cup 信心常低於近距大 phone，phone 佔 `objects[0]` 每輪被講。cell_phone(67) 同時在 `class_whitelist` 與 `OBJECT_CLASS_ZH('手機')`，build_object_tts 對 phone 回非 None。
   - **已親自釘死（2026-06-14 code 驗證，見 [`2026-06-14-codex-second-opinion-act1-s3.md`](2026-06-14-codex-second-opinion-act1-s3.md)）**：`zh_tables.py:22` `OBJECT_CLASS_ZH` **確實含 `"cell_phone": "手機"`** → deterministic `build_object_tts("cell_phone")` 會講「看到手機了」（cell_phone 不在 `OBJECT_TTS_SPECIAL_SUFFIX`，無尾句）。但 `build_object_tts` 永遠**不會帶人名**，所以 live 聽到的「**Roy 的**手機」這句帶名字的，是 **LLM 路徑**簽名——`conversation_graph_node._format_recent_objects`（N3-A「[最近看到]」prompt 注入 `world_state.recent_objects`）餵給 LLM 自然講出。
   - ⟹ **phone 同時餵兩條路徑**（deterministic object_remark **和** LLM recent_objects）。**所以最乾淨的修法是 producer 端 `class_whitelist` cup-only**——一刀同時餓死兩條路徑（phone 根本不進 `/event/object_detected`）；只改 brain 的 `objects[0]` 排序救不了 LLM 那條（recent_objects 仍會收到 phone）。nav-bg lane 稱「object_remark 白名單只有 cup/bottle/book」**不精確**：那是 `OBJECT_TTS_SPECIAL_SUFFIX`（只有這三類有額外尾句），完整 `OBJECT_CLASS_ZH` 講話白名單含 cell_phone。
2. **(慢一拍) object_remark 硬卡 `attention==ENGAGED`**（需 D435 depth≤1.6m + dwell 1.5s）。S2 greet 一觸發就進 INTERACTING，要 quiet 8s 才回 ENGAGED → S3 緊接 S2，cup 被 attention_engaged gate suppress。D435 depth 在 1.5-2m 抖也使 dwell reset。
3. **(pose 沒出) 雙因**。vision 端只在 pose_vote「變化」時才發事件（Roy 一開始就坐著→vote 從頭是 sitting→永不變→不發），brain 端 `last_sitting_seen_ts` 不更新；且即使 sitting 事件有發，demo config `demo_video_silent_sit_along=true` 把 sit_along 靜音、`demo_video_cup_compound=false` 又關掉 cup+sitting 複合句——pose 對 S3 既無聲又不更新 context。
4. **(換 take 沉默) producer 5s class_cooldown + brain 60s OBJECT_REMARK_DEDUP 疊加**——cup 講一次後 60s 內同 class suppress，換 take 間隔 <60s 就沉默。

**需查證據**：`ros2 topic echo /event/object_detected` 看同一秒 objects[] 順序與 cup/phone confidence（確認 phone 在 objects[0]）；`ros2 param get /object_perception_node class_whitelist`（67 是否在線）；`/brain/trace` 過濾 `class=cup` 看被哪個 gate 擋（attention_engaged / active_plan / tts_playing / object_remark_dedup）；`/event/face_identity` 的 distance_m 抖動範圍；`/event/pose_detected` 在持續坐著 vs 站起再坐。

**可修方案**：
- **P0 最小外科（brain 端 default-off）**：`_on_object` 對 `ev.objects` 先做 class 優先序排序再取首個——新增 `OBJECT_REMARK_PRIORITY=('cup','bottle','bowl','book',...)` param-gated（預設沿用 `objects[0]`=byte-identical），cup>bottle 滿足 Roy 需求。
- **P0 現場應急（零 code）**：`ros2 param set /object_perception_node class_whitelist '[41,999]'`（cup-only）或 `'[39,41,45]'`（cup/bottle/bowl）——runtime callback 即時生效、可即時切回，phone 永不進 event。
- **P1**：把 cell_phone 從講話白名單降級（build_object_tts 對 phone 回 None，類比 person 靜音），UI 仍顯示。
- **P1（attention）**：新增 `object_remark_attention_min` param（預設 ENGAGED），設 NOTICED 時對 cup/bottle 放寬（face 穩定即可講），符合「pose/距離不可卡住 S3」。
- **P1（pose 加分非硬依賴）**：cup remark 完全不依賴 pose，sitting 純 bonus（有 sitting 升級複合句、無 sitting 仍講 cup），複合句現硬鎖 `name=='Roy'` 建議泛化。

**優先級**：P0（真兇 + attention）、P1（pose / dedup）。**需 HITL**：是（多需 Roy 在場 echo + trace 確認 phone 是否真在 objects[0]、cup 被哪 gate 擋；純感知+brain、不涉 Go2 motion，安全）。

---

### 2.4 物體模型 A/B 與 Supervision offline benchmark（P1，非阻塞）

**核心結論**：S3「講手機」的真兇主要在 Brain 端、不是模型。模型本身確實會把 cup 誤認成 phone/bottle（acceptance §4：0.7m phone 4 次/bottle 2 次、1.5m phone 6 次），但這是次因——distance 不掉 recall（cup 0.7-1.5m 都近連續偵測），混淆才是痛點。**S3 修法是純軟體 brain 改動，完全不需換模型**。

**YOLO26s 換模已查清**：4 顆 ONNX（yolo26s_640 / yolo26n_960 / yolo26s_960 / yolo26n-pose_640）早在 6/10 export 完、shape 全相容 (1,300,6)，但尚未 rsync 上 Jetson、TRT 未預燒。**結論＝6/18 前大概率不要換**（B-4 預設不換、hard-to-reverse、且 S3 真兇是 brain 不是模型）。換主 object 模型需 TRT 預燒（不可與 demo stack 同跑、1GB workspace OOM）+ RAM 重量 + Roy 點頭 + rollback 驗證。

**今天可先做（零 runtime 風險）**：
- 現役 n@640 跑 cup/bottle/phone/chair × 0.7/1.0/1.5m baseline 矩陣：`obj_matrix_cap.py`（只訂 object topic 避跨流污染，window≥6s）。
- Supervision offline confusion matrix：`uv venv .tmp/sv_venv && uv pip install supervision`（**禁裝 Jetson**），用 demo 錄影 MP4 + JSONL 跑 `supervision_evidence_spike.py` → sv.metrics ConfusionMatrix 出真混淆矩陣。

**960 input 已查證＝插值自欺**（相機只餵 640x480，餵 960 是純插值無新像素；imgsz=1280 已 superseded）。Supervision 鐵律 offline-only（硬依賴完整 opencv+matplotlib+scipy，絕不進 Jetson runtime）。

**優先級**：P1（baseline 量化）/ P2（換模、960、tiling）。**需 HITL**：是（obj_matrix 要 live /event + Roy 指認錄影/JSONL 路徑）。

---

### 2.5 S4 gesture 確認流程（✅ PASS — GO）

**現象**：比 peace → Brain 問「比 OK 就開始」→ 比 OK → Go2 wiggle（搖）。Roy 要求：只保留 peace 辨識、其他手勢關掉、關掉 Studio 手勢按鈕（peace 不太會誤觸）。

**Ranked 根因假設（為何 PASS / 如何鎖配置）**：

1. **(最可能) live 走 `peace_wego_confirm=true`** → `_GESTURE_CONFIRM={'peace':'wiggle'}`，peace→請求 OK 二確認→OK→wiggle，與 live 完全吻合。現行 `executive.yaml` 已 `gesture_direct_disabled=true`（`_GESTURE_DIRECT={}`）→ palm/fist/index/wave 進來不觸發任何動作，達成 80% 目標。
2. **(唯一殘留) thumbs_up 仍在 `_GESTURE_CONFIRM`**（thumbs_up→wiggle），握杯/托腮易誤觸；設 `thumbs_up_demo_ack=true` 可改成只發輕量正向、不引出 wiggle。
3. **OK confirm 穩定**：PendingConfirm 有 N8 `must_release_ok`（手已在 OK 位置會 gate 住直到放開，避免立即誤觸）；OK 只在 confirm window 內有效，平時亂比 OK 無害。OK 是唯一二確認路徑，不可關。
4. **Studio「手勢按鈕」需釐清**：前端唯一手勢相關控制是 `GestureToggle`（ON/OFF 總開關），另有 `SkillButtons` 能直接 POST skill_request 觸發 wiggle（**繞過手勢/OK**）——後者對 Go2 安全更關鍵，可能才是 Roy 怕誤點的。
5. **wiggle=api_id 1020 是站立原地扭動、非位移**，但仍是 Go2 實體 motion → 屬 forbidden scope（需 Roy 授權+e-stop）。

**可修方案**：demo 啟動帶 `peace_wego_confirm:=true + gesture_direct_disabled:=true + thumbs_up_demo_ack:=true`（零 code，只有 peace 引 wiggle confirm）；釐清後從 live 面板隱藏 SkillButtons 手動 motion 觸發鈕；SOP 寫站位（D435 前 1-2m、單人、peace 穩住 ~2s、OK 穩住 ~1s）；S4 wiggle 前 Roy 授權 + e-stop 在手；台詞 fallback「好，我跟你 WeGo 一下！」（不發 motion）需 Roy 簽。

**優先級**：P0（只留 peace 配置 + wiggle e-stop）、P1（OK 穩定 / Studio 按鈕 / 入框 SOP）。**需 HITL**：是（wiggle motion + 釐清「手勢按鈕」指哪個）。

---

### 2.6 S5 safety reject（✅ PASS — GO）

**現象**：問後空翻/翻跟斗 → 秒回「這個動作不安全，我不能執行」，攔截成功。

**Ranked 根因假設（為何是真 PASS 而非裝飾）**：

1. **(最可能) 雙路徑皆 rule-first，LLM 結構上無法 override**。語音 `/event/speech_intent_recognized` 與 Studio 文字 `/brain/text_input`（經 `_on_text_input` 合流進 `_on_speech_intent`）都在 `brain_node.py:1391` 跑 `SafetyLayer.unsafe_request`，發生在 LLM/chat_buffer 之前（1437 行才進 LLM 等待），return 即走 → 0s、no-LLM、不可能被 LLM override。斷網/offline_mode 仍秒回（驗證 no-LLM）。
2. **執行層 reject 是真實紅線**：`request_backflip`（name=backflip→api_id 1301∈BANNED_API_IDS）在 IE node validate 必然 reject 成 BLOCKED_BY_SAFETY，發 `/brain/trace`（verdict=BLOCKED gate=safety reason=banned_api:1301），gateway 落盤 `runtime/traces/*.jsonl` + WS 廣播到 Studio 紅字。
3. **雙層防線**：即使有人繞鍵詞直接 `skill_request request_backflip`，validate 仍 100% 擋；backflip 也不在 LLM_PROPOSABLE_SKILLS。
4. **phase-independent 已驗**：reject return 在任何 `_phase_allows` 之前，任何 demo_phase 都擋。
5. **(唯一弱點) 鍵詞表固定 + ASR 誤聽**（Go2 風扇噪音 ~20%）——6/18 走 Studio 文字觸發（operator S5-Trigger）100% 命中鍵詞可完全規避。

**可修方案**：無需修改（已 proven、36 測試全綠）；6/18 S5 主線走 Studio 文字觸發、語音當加分 take；建議維持 backflip（已 6/10 proven 端到端），除非 Roy/老師明確要換詞（換詞=改 UNSAFE_KEYWORDS_REJECT + 補測試 + rebuild）；6/18 可把 Studio trace drawer / BLOCKED 紅字當鏡頭證據（呂奇傑指定的三層架構唯一視覺化）。

**優先級**：P0（已 PASS、確認展示路徑）。**需 HITL**：部分（驗 trace 落盤 + Studio 紅字需真機 gateway+frontend 同跑）。

---

## 3. 跨段共通風險

### 3.1 offline_mode topic↔param gap（驗證陷阱，非功能 bug）

topic↔param 其實已接通且行為正確：brain 有 `/brain/offline_mode` Bool subscriber → `_set_offline_mode`（與 param callback 共用），gateway publish 到同 topic、QoS 相容、行為正確（Studio toggle ON 後下句語音走 offline 短路播 canned）。**真正的 gap**：`_set_offline_mode` / `_set_demo_phase` 只更新實例屬性、不呼叫 `set_parameters` → 經 Studio topic 切換後 `ros2 param get /brain_node offline_mode` 仍回舊值（撒謊）。runbook 又叫操作員用 param get 驗證 → 上場驗證陷阱。**修法**：HITL §4 加「Studio offline toggle 切換後改看 `/brain/trace` 出現 `reason=offline_mode` 或聽是否秒回 canned，不要用 param get 驗」；備援退啟動前 env override `LLM_ENDPOINT=http://127.0.0.1:1/ TTS_PROVIDER=piper`。

### 3.2 phase / fallback dead air（never-dead-air 全靠操作員）

`auto_advance_phases` 預設 `[]` → 每幕 `max_wait` canned-rescue timer 永不 arm（`_arm_phase_wait_timer` 只在 `_auto_advance_on(phase)=True` 才 arm）→ manual-floor 下 brain 不會自動補話。chat 路徑有 `chat_wait_ms=1500ms` 保底（使用者真講話 1.5s 內必有聲），dead air 只發生在「純視覺觸發又沒觸發到」的展示空檔。**修法（保守版，6/18 主線）**：每幕都不開 auto_advance，彩排明確分派「計時人 + canned 觸發人」，max_wait 內沒視覺觸發就用 Studio skill_request(say_canned) 或文字補話；**理想版（6/17 彩排才決定）**：只對 S2 開 `auto_advance_phases=['s2_greet']` 讓進場 greet 自動補 + max_wait rescue，S3/S4/S5 仍 manual floor。**暖機必做**：tts_node 起後對 15 句各發一次 `/tts` 進 cache（禁 mid-session 重啟 tts_node），讓 canned 首句 latency≈0 不被誤判為 dead air。DEMO_CANNED_TABLE 15 句目前標 PENDING，待 Roy 6/15 簽。

### 3.3 CLI 跨平台（MacBook 6/18 主操作）

平台閘門集中於 `platform.py:detect()+assert_supported()`：WSL2 + macOS 放行、Windows native / WSL1 硬擋 exit 10（**PowerShell native 仍被拒且是設計意圖、非 bug**）。6/18 MacBook 主操作的真正風險不是閘門（macOS 會過），而是「閘門過了之後」CLI 對本機 ssh/rsync/bash + brain-studio-lane shell 腳本的隱性依賴：demo start/stop/health 走 `shell.stream(['bash', repo內.sh])`（需本機 clone repo + bash + Studio frontend node_modules）；純 SSH 指令（status/smoke brain/evidence pull/logs）Mac/WSL2 完全等價、可放心跑。**flock 其實在 Jetson 端跑**（非本機），README/onboarding 把「需本機 flock」當擋 Windows 理由是不精確的，但結論（擋 PowerShell）仍正確。**產出**：單頁 MacBook operator setup checklist（brew tmux/node/tailscale + git clone 到 ~/elder_and_dog 非 iCloud + ~/.venv + uv pip install -e + ~/.ssh/config Host + .env.local + pawai doctor 全綠）；6/18 CLI runbook 分 Layer A（純 SSH，Mac 安全）/ Layer B（本機 bash，需 Mac repo+bash+npm）；PowerShell blocker list（一律導向 `wsl --install -d Ubuntu` 或 MacBook）。**未驗最大風險**：MacBook 上 `bash .claude/skills/brain-studio-lane/scripts/start.sh` 是否有 GNU-only（realpath/sed -i）或 zsh-only 假設——需 Roy 實機驗。

### 3.4 operator-runbook 契約備註已過時（誤導風險）

runbook「契約備註 #1/#2/#3」已過時：PHASE_ALLOWED_KINDS 現已含 5 canonical 幕（runbook 卻寫 brain 還沒收、會被拒）、brain `/brain/demo_phase` subscriber 已存在（runbook 卻寫不存在）。會誤導操作員照舊 alias 表繞路、或誤以為 Studio 五幕鈕沒接通而退 param set。code 行為向後相容（alias 與 canonical 都吃），照舊打不會壞、只是多繞。**修法（docs-only，6/17 前必做）**：更新契約備註 #1/#2/#3 + 跑 P4-11 dry-run（找沒參與者照唸）逐條標出過時步驟。

### 3.5 雙 Go2 driver 衝突 + Studio/gateway 可達性

Go2 對單一 ROBOT_IP 只接受一條 WebRTC peer（單一 RTCPeerConnection + DataChannel id=0）；两份 robot.launch.py + nav2_amcl 裸 driver = 2-3 個 RTCPeerConnection 搶同一台 Go2 → ICE FROZEN→FAILED + /cmd_vel,/webrtc_req,/odom 撞名 + odom→base_link 雙 publisher。**6/18 前**：嚴格 SOP「一次只起一個 driver」、起 nav 前 `pawai demo stop` + 逐一 pkill -9。Studio/gateway auth 預設關 → MacBook 經 Tailscale 可達；唯一風險是設了 GATEWAY_AUTH_TOKEN 但前端沒帶 token → POST 全 401（6/18 凍結期建議 auth 維持 OFF）。

---

## 4. 6/18 影響矩陣

### 4.1 P0 必修（6/18 前一定要處理，多為純軟體/SOP/docs）

| 項目 | lane | 形態 | 風險 |
|------|------|------|------|
| S3 phone 搶話：whitelist 收 cup-only（現場 param）或 brain class 優先排序（default-off param） | S3 / object | 純軟體 / runtime param | 低（param 即時切回；brain 改需 smoke 全綠） |
| S2 demo 前現場光線 re-enroll Roy + face_db 衛生（移 _backup/old 出 face_db） | S2 | 外部 shell / CLI face | 低（不改 node code） |
| S2 確認 Jetson 上 `greet_require_sitting` 回 false（非 code default true） | S2 | 驗證 | 零（讀取） |
| S4 鎖配置：peace_wego_confirm + gesture_direct_disabled + thumbs_up_demo_ack | S4 | launch arg | 低 |
| Act1 收工前 `pawai evidence pull` 保住當天 goto log + reactive zone 時間線 | Act1 / nav | 只讀 | 零 motion |
| Act1 no-motion 診斷分流（topology / tf_static / lidar_front_sector / param get） | Act1 / nav | 只讀診斷 | 零 motion |
| operator-runbook 契約備註 #1/#2/#3 更新 + P4-11 dry-run | demo-flow | docs | 零 |
| DEMO_CANNED_TABLE 15 句 Roy 6/15 簽核 | demo-flow | docs/簽核 | 零 |
| 彩排分派計時人 + canned 觸發人（never dead air） + TTS 15 句暖機 | demo-flow | SOP | 零 |
| MacBook operator setup checklist + start.sh Mac-compat 驗 | CLI | docs / HITL | 低 |

### 4.2 可 fallback（不修也能交付，退保守路徑）

| 項目 | fallback |
|------|----------|
| Act1 live 障礙停 | 退 B 層（遙控+Foxglove LiDAR 證據，零 motion）/ C 層（影片保底）；A 層僅 Roy+e-stop upside |
| S5 語音觸發 | 退 Studio 文字觸發（100% 命中鍵詞，規避 ASR ~20% 誤聽） |
| S3 cup 換 take 沉默 | 換 take 前發 `/brain/reset_context`（已有清 dedup 邏輯，零 code） |
| offline_mode runtime 切換 | 退啟動前 env override（proven） |
| Studio 主控（MacBook） | 另派一人 SSH 在 Jetson 待命 param set backup |
| S4 wiggle motion | 退「say_canned 不發 motion」純語音 fallback |
| Tailscale 不穩 | Studio+gateway 跑 Jetson 本機接螢幕 / 影片保底 |

### 4.3 donotclaim / forbidden（6/18 前明確不做、不講）

- **不講** F1-F10 類 overclaim：自主導航 / 動態繞障 / D435 已與 LiDAR 融合 / auto-resume / safe-stop=繞障（safe-stop≠繞障是標準說法）。
- **不做**：Go2 motion（除 S4 wiggle 且需 Roy+e-stop）；goto_relative 當 live 主線（NOT_DEMO_READY）；live SLAM；autonomous approach；D435+LiDAR fusion runtime claim；model runtime switch；auto-advance 預設開；full CLI v2/Typer 大重寫；secure-default full flip。
- **post-6/18 架構**（不在 6/18 scope）：single-driver superset launch（LT-2）；T0 URDF 移 map/odom joint（LT-1）；nav2_amcl 走 mux（LT-3）；enable_lidar arg leak 修（LT-4）；共享 brake 決策層+actuation 層（LT-5/6）；reactive_stop footprint/corridor 升級；YOLO26s 換模 + 960+720p 相機；CLI pipx 路徑 / face verify sim 閉環 / WSL2 detect false-block 修。所有 nav 常駐共存待 LT-0 corun profiling gate 過。

---

## 5. 下一輪實測順序（Roy 指定，照抄）

> **原則**：先把 S2-S5 穩住，再決定 Act1 用哪個 fallback；不要先大修導航（導航最容易吃掉整晚）。

1. **S3 object mapping / bottle 也講喝水** — cup 優先講、bottle 等也可講但 cup 優先（whitelist 收 cup-only 或 brain class 優先排序）；pose 改加分非硬依賴。
2. **offline_mode / fallback / phase 操作確認** — Studio offline toggle 切換後看 `/brain/trace reason=offline_mode` 或聽秒回 canned（不用 param get 驗）；確認手動 phase 切換 + canned fallback 不 dead air。
3. **S2 face low-light / cooldown 微調** — 現場光線下 re-enroll + 量 sim≥0.7、face_db 衛生；確認 greet_cooldown / 入框 SOP。
4. **S4 gesture SOP** — 鎖只留 peace 配置、釐清並關 Studio 手勢按鈕、wiggle 前 e-stop 就位、入框站位 SOP。
5. **S5 safety trace** — 驗 trace 落盤 `runtime/traces/*.jsonl` 有 banned_api:1301 + Studio 紅字真出現；6/18 主線走 Studio 文字觸發。
6. **CLI MacBook runbook** — MacBook setup checklist + 純 SSH 指令（status/smoke/evidence）先驗、demo start（本機 bash）最後驗、start.sh Mac-compat 確認。
7. **Act1 nav fallback 決策** — 依 no-motion 診斷結果，6/17 回穩日由 Roy 定 B-10 當天層（預設 B 遙控+Foxglove 證據、A 為 Roy+e-stop upside、C 影片保底）。
8. **object A/B offline benchmark** — 現役 n@640 矩陣（cup/bottle/phone/chair × 0.7/1.0/1.5m）+ supervision offline confusion matrix（throwaway venv，禁裝 Jetson），決定換不換模型（結論傾向 6/18 不換）。

---

## 6. 決策拍板（2026-06-14 grill-me 結果）

> Roy 逐題拍板。標 ⚠️ 者為 Roy **覆寫**了報告原建議，以 Roy 決定為準。

| # | 領域 | 拍板決策 | 性質 | 需 HITL |
|---|------|---------|------|:---:|
| D1 | S3 修法 | **混合**：producer `class_whitelist` 收成飲水相關（cup/bottle/bowl/wine_glass，移除 phone/laptop）→ 一刀斷 object_remark + LLM recent_objects 兩條講手機路徑；再加 brain `OBJECT_REMARK_PRIORITY`（cup>bottle）保證 cup 贏。default-off param、預設 byte-identical | runtime code(brain)+yaml | 是(smoke) |
| D2 | S3 attention | `object_remark_attention_min=NOTICED`（只對 cup/bottle 放寬，免 S2 後 INTERACTING 8s quiet 吞 cup）。default-off param | runtime code | 是 |
| D3 ⚠️ | S3 pose | **保複合句「Roy 坐著拿杯子」當主線 + 上機修 vision pose 邊緣觸發 bug**（週期重發 or brain 改訂 `/state/pose` 連續狀態）。地板層：cup 簡單句沒 pose 也會講（pose 不卡 S3、只是讓「升級複合句」可靠）。RAM/topic 量風險 | vision runtime code | 是 |
| D4 | S4 Studio 鈕 | **藏掉 GestureToggle 按鈕**（偵測全程 ON，手勢動作靠 `demo_phase=s4_gesture` phase gate 管範圍，S2/S3 不被搶話） | frontend | — |
| D5 | S4 peace | 接受現行 config（`peace_wego_confirm + gesture_direct_disabled + thumbs_up_demo_ack`），零 code | 零 code(param) | — |
| D6 | S4 wiggle | Go2 實體 motion → 需 Roy 授權 + e-stop；不穩退純語音「好，我跟你 WeGo 一下！」 | — | 是(motion) |
| D7 | S5 指令 | 維持 backflip/翻跟斗/倒立（已 proven、36 測試綠），零 code | 零 code | 部分 |
| D8 ⚠️ | S5 觸發 | **語音現場喊主線**（用筆電 Studio 麥非機身麥，誤聽率較低）+ ASR 漏接時 operator 立刻 Studio 文字補同句當即時 fallback | 零 code | — |
| D9 ⚠️ | Act1 | **live 障礙停版（Go2 自走遇障停）**。Motion 紅線全套：① no-motion 診斷(D1-D5)先過 ② Roy+e-stop ③ 障礙 >0.6m 高過掃描面 ④ indoor_tight 窄錐重驗無誤擋 ⑤ demo profile `slow_policy=stop`（跳過 0.45<MIN_X 不可靠 slow band，直接 normal 0.60→StopMove）⑥ 不穩立刻退「人推障礙(零 motion)」再退影片 | reactive demo profile | 是(motion) |
| D10 ⚠️ | offline_mode | **小 code 修**：`_set_offline_mode`/`_set_demo_phase` 加 `set_parameters` 讓 param get 反映真值 | runtime code | 是(smoke) |
| D11 | gateway auth | 6/18 凍結期維持 **OFF**（MacBook 經 Tailscale 直達） | 零 code | — |
| D12 | CLI 安裝 | 6/18 維持 **venv + uv pip install -e**（pipx 列 post-6/18）；產單頁 MacBook checklist + 驗 start.sh Mac-compat（最大未驗風險） | docs+驗證 | 是(Mac 實跑) |
| D13 ⚠️ | object A/B | **6/15-16 跑**（發表要講「量過 n vs s 代價」）：現役 n@640 矩陣 + supervision offline confusion matrix（throwaway venv 禁裝 Jetson）。需 Roy 指認 demo 錄影 MP4 + JSONL 路徑。結論仍傾向 6/18 不換模 | offline 量測 | 是(素材) |
| D14 | auto-advance | 全幕維持 **manual FLOOR**（Roy 早定「這次不碰 auto-advance」），never-dead-air 靠操作員 + 15 句 TTS 暖機進 cache | 零 code | — |

**待 Roy 動作**：DEMO_CANNED_TABLE 15 句台詞 6/15 前簽核（`brain_node.py:107` 標 PENDING）。

**執行分層**（下一輪）：
- **AFK 純軟體可先做（需 Roy 授權動 runtime code）**：D1（S3 whitelist+priority）、D2（S3 attention param）、D4（S4 frontend 藏鈕）、D10（offline set_parameters）。每條小 PR / default-off / 可 rollback / smoke。
- **Roy 在場 HITL**：D3（pose 上機修）、D6/D9（Go2 motion，e-stop）、D8（語音 S5 驗）、D12（Mac 實跑）、D13（素材 + 量測）、S2 re-enroll。
- **零 code / docs / 運營**：D5、D7、D11、D14 + S2 站位/光線 SOP + operator runbook 契約備註更新。

---

## 7. 不在 6/18 前做的事（forbidden scope）

- **Go2 motion** — 除 S4 wiggle 外，且 wiggle 須 Roy 授權 + e-stop 在手。
- **goto_relative 當 live 主線** — 維持 NOT_DEMO_READY；不發任何 goto/forward 當 live。
- **live SLAM** — demo 期不建圖。
- **autonomous approach** — 不做自主接近 / 跟隨。
- **D435 + LiDAR fusion runtime claim** — D435 depth_safety 僅 advisory、未進 costmap；不講已融合補盲區。
- **model runtime switch** — 不換 object 主模型（YOLO26s rsync/TRT 預燒延 post-6/18）、不動相機 profile（960 配 640x480=插值自欺）。
- **auto-advance 預設開** — 維持 manual FLOOR；最多現場單幕（S2）由 Roy 逐次手動開。
- **full CLI v2 / Typer 大重寫** — 不為 PowerShell 改 shell.stream bash 抽象；不引 Typer/Rich。
- **secure-default full flip** — 6/18 凍結期 gateway auth 維持 OFF（MacBook 直接可達）。
- **nav 架構重構** — single-driver superset launch / T0 URDF 移 joint / nav2_amcl 走 mux / enable_lidar plumb / 共享 brake / reactive footprint-corridor，全 post-6/18 且待 LT-0 corun profiling gate + 真機 motion HITL。
- **face_identity_node runtime 改 / .npz purge 重做 / enroll 阻擋 ghost dir** — 本輪只研究、face enroll P0-B（套 _clean_face_name）/ P1-A（sim 閉環）需 Roy 另開授權。
- **runtime tiling / SAHI** — 永久 offline-only upper-bound 探索（5x 推理過不了 ≥3Hz 門檻）。

---

*本輪只「研究 + 寫計畫」，未修改任何 runtime code、未實際發 GitHub issue。所有 P0 落地需 Roy 在場 HITL（多為純感知+brain+只讀診斷，不涉 Go2 motion，安全）。*
