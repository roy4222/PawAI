# PawAI 6/9 導航 + 視覺執行研究報告

> 受眾：執行 6/9 HITL 與硬體前開發的 PawAI devs（Claude / Cow），目標 6/18 demo。
> 原則：**證據優先、不誇大**。每一條 claim 都標籤化，HARDWARE_PROVEN 只給有 HITL 文件直接背書的能力。
> 真相來源：本報告 §1 直接採用 VERIFY 對抗式誠實檢核表（已把 scout 的唯一一個過度評分 indoor-tight 從 HARDWARE_PROVEN 降為 WIRED_RUNTIME）。
> 日期：2026-06-09

---

## 1. Today Truth Table（今日真相表）

標籤定義：
- **EXISTING_CODE** — 程式碼存在，但未接成 runtime / 未在 demo 路徑啟用。
- **WIRED_RUNTIME** — 已接成可跑的 runtime（含 launch / param / 訂閱），但未在硬體上觀測到端到端行為。
- **HARDWARE_PROVEN** — 6/4 或 6/8 HITL 文件**直接**背書、實機觀測到結束行為（仍可能是窄版 / 單資料點）。
- **DEMO_READY** — 可在 demo 上以誠實台詞展示（HARDWARE_PROVEN 且台詞不誇大）。

### NAV

| capability | done? | 標籤 | 能否 demo 講 | 誠實 caveat | 證據 |
|---|---|---|---|---|---|
| short-distance goto | **done** | **HARDWARE_PROVEN** / DEMO_READY | 「收到短距前進指令會自己走一小步並到點停下」 | 6/8 單一 HITL 資料點、scoreboard n=0。離散步進：0.3m & 0.5m 都塌到 ~0.27m / ~3.45s（Go2 一步後 goal-close），**非校準距離、非連續**。8GB 兩 stack 互斥（與 brain 分開拍）。 | 6/8 HITL §1/§3；`nav_action_server_node.py:296-444` |
| safe-stop | **done** | **HARDWARE_PROVEN** / DEMO_READY | 「前方有障礙會停下，不撞、不暴衝」 | 僅反應式感測停車，**非轉向 / 非繞行**。**不是 no_auto_resume**（障礙清除後它會自動 resume，講「不會再走」是反向錯誤、禁止）。 | 6/8 HITL §1 NAV-2；`reactive_stop_node.py:210-263` |
| indoor-tight（感測修正） | **partial** | **WIRED_RUNTIME**（從 scout 的 HARDWARE_PROVEN **降級**） | 「我們找到並修正了窄場誤擋的感測原因（收窄前錐＋低速）」 | ±15°/danger-1.0 重啟讓 zone 變 clear、`nav_paused=false`，但**修正後 Go2 真的走過窄場從未被錄到**（orphaned-goal 擋掉）。沒有永久 script/profile。**感測狀態變化已證、穿越窄場能力未證**。HARDWARE_PROVEN 需要觀測到結束行為而非只有 clear zone 讀數。 | 6/8 HITL §4/§5；`reactive_stop_node.py:78,108-117` |
| stop-resume | **partial** | **WIRED_RUNTIME** | 不以能力 demo | pause→cancel→re-send loop 已完整實作。6/8 僅證前置條件：被擋 goto 存活 278s 無 no_progress abort → goal 仍活著可 resume。**resume loop 本身未在硬體上錄到**。 | 6/8 HITL §1 NAV-3；`nav_action_server_node.py:223-293` |
| goto_named | **partial** | **WIRED_RUNTIME** | **DO_NOT_CLAIM** | handler 存在（named-pose + standoff + AMCL gating + pause-aware）。未硬體證實；HITL §6.6：「ready 但需要更大空間（學校場地）才有意義」。 | 6/8 HITL §6.6；`nav_action_server_node.py:448-583` |
| dynamic-avoid | **not_done** | **EXISTING_CODE** | **DO_NOT_CLAIM** | `depth_safety_node` 明言「不是 controller、不 pause Nav2」。DWB 保守 profile 不自動繞行（`angular.z=0`，只停不轉）。HITL §7：「cannot claim dynamic detour」。future work。 | 6/8 HITL §2/§7；`nav-known-issues-roadmap.md:56-64` |

### VISION

| capability | done? | 標籤 | 能否 demo 講 | 誠實 caveat | 證據 |
|---|---|---|---|---|---|
| face.recognition | **pass（窄版）** | **HARDWARE_PROVEN**（量化 n=9）/ DEMO_READY | 「認得已註冊的 Roy，不會把空場景誤判成人」 | 僅註冊者、idle=空畫面、~1.5-2.4m、最低正樣本 conf 0.2378。**真實陌生人拒絕未驗證**。NON-claim：門禁級 / 「不會認錯」 / 2m+ / 通用人臉。greet gate = `identity_stable`+sitting+cooldown，非 raw recognition。 | 6/04 HITL README:13（recall=1.0, fa=0.0）；`brain_node.py:1010-1110` |
| object.cup | **pass（窄版 ~1m）** | **HARDWARE_PROVEN**（量化 n=7）/ DEMO_READY | 「近距（約 1 公尺）看到水杯會辨識出來」 | ≤1m only、`class_whitelist=[41,999]`（cup-only）、2m 未驗證/recall 崩（~28px@2m 低於 anchor floor）、latency p90≈4.9s **非「即時」**、distance=manual_declared。NON-claim：通用/80-class、2m、地上水杯/絆倒語言、cup→Go2 motion。 | 6/04 HITL `baseline_result.jsonl`（5/5@1m, conf 0.834-0.88） |
| object.chair (56) | predicted, **unmeasured** | **INSUFFICIENT_DATA** | **DO_NOT_CLAIM** | research 預測最強（大/規則/不依賴顏色），但**零 chair trial**。matrix 待測。 | research night-vision:62,70；yaml:21 |
| object.laptop (63) | predicted backup, **unmeasured** | **INSUFFICIENT_DATA** | **DO_NOT_CLAIM** | 預測 backup-1，無 trial。 | research:63,71 |
| gesture.wave | **fail** | 量化 fail（n=9） | **DO_NOT_CLAIM** | recall=0.0、`wave_pub=False` 全程。yaml `gesture_backend: rtmpose` footgun 關掉 WaveDetector → wave 永不觸發。靜態 thumbs_up/ok 是不同 path，**不可混為一談**。wontfix #131。 | 6/04 README:15,27；`vision_perception_node.py:342-432` |
| gesture.thumbs_up | works（靜態），**未上 scoreboard** | **WIRED_RUNTIME**（operator 確認、未量化為能力） | 「比讚會回應（靜態手勢）」— 僅在明確標示為靜態、與 wave 分開時 | operator 確認可動（0.5s stable gate）；不在 HITL scoreboard、無 n。**不可呈現為「手勢辨識通過」**（會洗白失敗的 wave）。 | `vision_perception_node.py:480-496`；`brain_node.py:781-791` |
| pose.sitting | **insufficient_data** | **INSUFFICIENT_DATA** | **DO_NOT_CLAIM** | n=0、tooling 無 pose observer。無 hysteresis、無 trusted baseline。**greet 硬依賴**（`greet_require_sitting=True`）→ demo 單點故障。除非 smoke ≥4/5，否則永不講「坐下」。 | 6/04 README:17；`pose_classifier.py:201-211` |
| pose.fall | future | **DO_NOT_CLAIM** | **DO_NOT_CLAIM** | `enable_fallen:=false`、future work、`brain_allowed=false`。 | claim-matrix §1 pose |
| studio.evidence | **insufficient_data** | **EXISTING_CODE / NEEDS_RETEST** | 「Studio 即時顯示感知事件與 brain trace（顯示載體，非能力 pass）」 | 顯示載體，6/4 未評分。**前端無 `/api/scoreboard` LED chip wall** — 不可宣稱有 live pass/fail LED 顯示。需同時顯示 4 感知 chip + brain trace + tts bubble 才算有效證據。 | claim-matrix §1；`studio_gateway.py:72-83` |
| under-load perf (VIS-8) | **unmeasured** | **HYPOTHESIS** | **DO_NOT_CLAIM** | e2e ~310-345ms 僅估計。首要嫌疑 H1 Studio video-bridge JPEG+WS，非 GPU 競爭。 | research night-vision:96-141 |

### Voice / Brain（完整性補充）

| capability | done? | 標籤 | 能否 demo 講 | 誠實 caveat | 證據 |
|---|---|---|---|---|---|
| voice.command | **pass（窄版）** | 量化 n=24 | 「語音意圖分類 ~0.875」 | 僅意圖分類，**非 ASR 率、非語音 e2e**。latency 全 null、CSV terminal 重建、單一講者。 | claim-matrix §1；baseline n=24 |
| voice.stop | **fail** | 量化 fail（n=6） | **DO_NOT_CLAIM** | 0.667、FN=2、`brain_allowed=false`。便利指令**非安全停車**。不可把「說停」當安全機制。 | claim-matrix §1；FN R16/R18 |
| brain.skill_gate / trace | mechanism only | **WIRED_RUNTIME + 91 unit tests** | 「Safety 層用規則擋掉危險指令（91 測試綠 + Studio 顯示）」 | 確定性、繞過 LLM。**#127 前未實機 e2e 驗證**。講「logic + 91 test + Studio live」，不講「實機端到端驗證過」。 | code + unit tests |
| brain anti-hallucination | **fail** | **DO_NOT_CLAIM** | **DO_NOT_CLAIM** | 6/04 operator 見 persona 編造下雨 / 看到水杯 / pose。**不可宣稱「不會幻覺 / persona 驗證過」**。 | claim-matrix §1；project-status 6/4 |

> **底線**：只有 4 個能力存活為 HARDWARE_PROVEN — **short-distance goto、safe-stop**（皆單 HITL、窄）+ 量化的 **face.recognition** + **object.cup**（皆窄版）。其餘全是 WIRED_RUNTIME / EXISTING_CODE / INSUFFICIENT_DATA / 量化 FAIL。scout 唯一過度評分（indoor-tight）已 default-down。

---

## 2. Navigation Data Plan（導航資料計畫）

### (a) 如何驗證 action / orphaned-goal 阻塞

**根因（兩段放大器）：**
1. **Client 端**（`scripts/send_relative_goal.py:78-85`）：`main()` 用 `try/finally: rclpy.shutdown()` 包全部。若 CLI 被殺（SSH 255）或在 `spin_until_future_complete`（L51/L59）中途 crash，**in-flight goal handle 從不被 cancel**（程式碼中沒有任何 `handle.cancel_goal_async()`）。crash 中又會重入第二次 `rclpy.shutdown()`（double `rcl_shutdown`，HITL §5）。
2. **Server 端**（`nav_action_server_node.py:188-194`）：`_accept_goal` 在 `self._goto_active=True` 時直接拒絕 `"rejecting goto_* goal — another goto_relative/goto_named is still active"`。`_goto_active` 只在 `_execute_relative`（`:300-301`）/ `_execute_named`（`:452-453`）的 `finally` 清掉。被殺的 *client* 不會 abort *server* 的 `execute_callback` → `_goto_active` 卡 True → 後續 goto 全被拒，直到 navcap 重啟。server 只檢查 `goal_handle.is_cancel_requested`（`:253`），但被殺的 client 永不設這個 flag。

**驗證步驟（6/9 HITL，可在硬體上做）：**
1. 啟 navcap，發第一個 `goto_relative`，**中途 Ctrl-C 殺掉 `send_relative_goal.py`**。
2. 立刻 `ros2 action send_goal /nav/goto_relative ...` 發第二個 → 預期被拒、log 印 `another goto still active`。→ **重現阻塞 = 確認 root cause**。
3. `ros2 node list` 確認 `nav_action_server_node` 仍活、未崩。
4. 套用 client 修正（§8 T1）後重做步驟 1-2 → 預期第二個 goto **被接受**（killed client 的 goal 已自我 cancel）。
5. 記錄：`/nav/goto_relative` 的 goal status 流轉（用 `ros2 action list -t` 確認 server 還在；echo server log）。

### (b) indoor-tight 要設的參數 + 要收集的結果

**現行 default**（`reactive_stop_node.py:67-106`，全在 `__init__:108-117` 讀一次）：
`danger_distance_m=1.1`、`slow_distance_m=1.7`、`slow_speed=0.45`、`normal_speed=0.60`、`front_arc_deg=30.0`、`front_offset_rad`（launch 帶 3.14159）、`clear_debounce_frames=5`。

**關鍵限制**：runtime callback `_on_param_change`（`:173-197`）**只接** `enable_nav_pause` / `safety_only` / `mode`。`front_arc_deg` / `danger_distance_m` / `slow_distance_m` **不可 runtime 改** → `ros2 param set` 靜默無效，**必須 kill node 重啟帶 `-p`**。

**要設的窄場 profile（重啟帶參數）：**
```
-p front_arc_deg:=15        # 或 20；收窄前錐，排除 ±30° off-path 家具
-p danger_distance_m:=1.0
-p slow_speed:=0.2
-p normal_speed:=0.3
```
**硬安全約束（HITL §4）**：±15° 窄錐**必須綁低速 ≤0.2 m/s**（側向覆蓋變少，靠低速補反應時間）。

**要收集的結果：**
- 正前方 ±15° 淨空距離（vs 舊 ±30° 把右前 -30° 家具算進來）→ 證實誤擋根因是錐寬非 TF。
- `nav_paused` 在窄場通道的狀態（預期 false / slow，非永久 danger）。
- **修正後 Go2 真的走過窄場的影片**（這是 6/8 缺的關鍵證據，orphaned-goal 修好後優先補）。

### (c) stop-resume 2s / 5s / 10s 結果表（硬體上填空模板）

| 障礙遮擋時長 | goto 是否存活（無 no_progress abort） | 障礙移開後是否自動 resume | resume 後是否到點 | 觀測延遲（移開→重新移動 s） | 備註 |
|---|---|---|---|---|---|
| 2s | ⬜ | ⬜ | ⬜ | ⬜ | |
| 5s | ⬜ | ⬜ | ⬜ | ⬜ | |
| 10s | ⬜ | ⬜ | ⬜ | ⬜ | |

> 前置：6/8 已證被擋 goto 存活 278s 無 abort（goal 仍活）。本表要補的是 **resume loop 端到端在硬體上發生**（6/8 未錄）。每格錄影。注意：reactive_stop 在 `hold_brake` mode **故意不 resume**（`:322-331`），測試請用一般 mode。

### (d) skew 診斷要錄的 topic + 判讀

根因排序（HITL §3）：H1 四足步態 yaw-drift ~60% > H2 DWB 短距欠修正 ~30% > H3 LiDAR TF offset ~10%。在 goto（最好 goto_named >1m）跑 **2-3 趟來回**，錄：

| topic | 內容 | 判讀 |
|---|---|---|
| `/cmd_vel_nav` `angular.z` | Nav2 最終輸出（post-smoother，mux nav2 priority-10）controller 命令的轉向 | drift 但 `angular.z≈0` 全程 → controller 沒在修 → **H1 步態漂移**（planner 不對抗的 open-loop body yaw）。`angular.z` 大幅擺盪/震盪 → controller 在硬修 → **H2 DWB 欠修正/overshoot** |
| `/amcl_pose` yaw | map frame 內被相信的 heading | **每趟同方向固定偏**（不論行進方向都偏同側）= **H3 LiDAR TF / mount-yaw 系統誤差**。**每趟隨機 / 方向相依** = **H1 步態**（非系統性） |
| `/odom` yaw | driver 推算 heading（odom→base_link，AMCL 修正前）| `/odom` yaw 與 `/amcl_pose` yaw **一起漂** → 狗真的轉了（物理 body rotation）= **H1**。兩者**分歧**（odom 直但 amcl-yaw 偏）→ 懷疑 localization/TF = **H3** |

**判定規則（HITL §3）**：同一路徑跑 2-3 次 — **一致同側偏 = TF (H3)**、**每趟不同 = 步態 (H1)**。（6/8 因 orphaned-goal 中斷未捕到此 wave，修好阻塞後優先補。）

---

## 3. Vision Data Plan（視覺資料計畫）

### Object Matrix（每格一觀測列的空白模板）

> 注意：repo 中 **`obj_matrix_cap.py` 不存在**（僅被 `supervision-vis3a-research.md:10,204` 與 project-status 引用）。現有 harness 是 `benchmarks/scripts/capture_baseline_round.py`（mode `percep`），但它**每個 window 只記一筆（first-match）**、**丟掉 bbox**、**無 light/angle/lux/trial/debug-image 欄位**。下表為目標 schema，需新 capture 工具（§8 T4）填。

| object | distance_m | light | angle_deg | trial(1-5) | detected | class_name | confidence | bbox_x | bbox_y | bbox_w | bbox_h | misclassified_as | debug_img_path | lux | 5-trial success | 備註 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chair | 1.0 | bright | 0 | 1 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | _/5 | |
| chair | 1.5 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | |
| chair | 2.0 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | |
| chair | 1.0 | dim | 0 | … | ⬜ | | | | | | | | | | _/5 | |
| laptop | 1.0 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | |
| cup | 1.0 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | （已知 pass，補距離曲線）|
| cup | 1.5 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | |
| cup | 2.0 | bright | 0 | … | ⬜ | | | | | | | | | | _/5 | （預期崩）|

欄位語意：`is_correct = (class_name == object)`；`misclassified_as` = 偵到但錯類，否則 null；idle/未偵到列 `detected=False`、空 class/conf（餵 FP/false-trigger 統計）。聚合 gate：`detected≥4 PASS / ==3 DEGRADED / <3 FAIL`。

### Pose / Gesture / Studio 證據欄位

| 訊號 | 欄位 | 來源 / 判讀 |
|---|---|---|
| pose `pose` | string（sitting/standing/…）| brain `_on_pose`（`brain_node.py:1112-1116`）只讀字串 `pose`，**不讀 `pose_vote_confidence`** |
| pose `pose_vote_confidence` | vote ratio = `pose_vote_count/len(pose_buffer)`（`:332-333`，4dp）| **是投票比例非分類器 raw conf**；`pose_buffer` maxlen=20（~1s@20Hz），**無 hysteresis** |
| pose sitting 門檻 | `trunk_angle<35°` AND seated y-geometry AND `ankle_above_hip>0.5*torso` AND `knee_angle<145°`（`pose_classifier.py:201-211`）| brain 要 sitting stable ≥1.0s 才 fire `sit_along`（`:1162`）；側面坐姿破 y-geometry |
| gesture `thumbs_up` cooldown | bridge `GESTURE_TTS_COOLDOWN_S=4.0`（`event_action_bridge.py:102,331`）；brain `demo_ack=True` 無 per-gesture cooldown（`:781-791`）| 上游再被 0.5s temporal-stable gate（demo yaml `gesture_stable_s=1.5`）+ only-emit-on-change 限速 |
| idle false-trigger | object per-class 5s cooldown（`object_perception_node.py:415-433`）+ `conf≥0.35`；gesture 需 vote winner 持 ≥`gesture_stable_s` 且 != last；brain `idle_enabled=False` default | 量測側：idle round 任何觀測 = `false_trigger=True`（`perception_baseline_observer:118-123`）|
| studio 證據鏈 | 必須截圖同時顯示 4 感知 chip（`/state/perception/face` + `/event/object_detected` + `/event/pose_detected` + `/event/gesture_detected`）+ brain trace（`/state/pawai_brain`、`/brain/proposal`、`/brain/skill_result`、`/brain/conversation_trace`）+ tts bubble（`/tts`）| gateway boot log 應印「subscribed to {len(TOPIC_MAP)} String topics + /tts + 2 capability Bool」= **10 String + /tts + 2 Bool**（`studio_gateway.py:251-252`）|

---

## 4. Cup Instability Study（水杯不穩定研究）

### 為什麼 cup 不穩定（程式碼層機制，皆在 `object_perception_node.py`）

1. **像素預算 / anchor floor**：輸入 letterbox 到固定 `input_size=640`（`:158,313-323`）。cup 杯緣 ~55px@1m → ~37px@1.5m → ~28px@2m，逼近 YOLO26n 有效 ≥20px anchor floor → 1m 偵得到、距離一拉 recall 崩。這就是 HITL「pass 只 @~1m」caveat 的機制。
2. **信心門檻**：`confidence_threshold=0.35`（yaml，刻意從 0.5 降為 +5-10% recall）。1m 實測 conf 0.834-0.88 遠高於門檻，但遠距小像素 cup conf 掉破 0.35 在 `:374` 被濾掉。YOLO26n 是 NMS-free（`(1,300,6)`），**不穩定是 conf 驅動非 NMS 驅動**。
3. **per-class 5s cooldown**（`:415-433`）：閃爍 cup 每 5s 才重發 → 邊緣 cup 掉破 conf >5s 讀成「丟失」，放大感知不穩定。

### 如何拆分 light / background / material / distance

- **Distance（主軸）**：像素預算決定，demo 必須 **≤1.5m**（research night-vision:79,89）。matrix 用 1.0/1.5/2.0m 三格固定其他變因，畫 recall-distance 曲線。
- **Light**：低光（~100-200 lux）同時降偵測 conf **且**搞垮 HSV 顏色分析（`analyze_bbox_color:81-135`）— V<50 強制 `m_black` → **紅杯被報「黑色杯子」**（night-vision:92）。matrix 加 bright/dim 兩格，記 `lux` 欄位，顏色錯報單獨統計。
- **Material**：亮面/陶瓷高光打爆 S/V、碎裂 dominant-color mask（ratio<0.25 → Unknown），且扭曲 bbox crop；金屬/透明 conf 更弱。matrix 用「同距同光、換材質」隔離。
- **Background**：雜亂提高 overlap/occlusion 風險 → research 要求物件間距 ≥20cm。跑全 80-class whitelist 是 HIGH-risk（night-vision:51）。matrix 固定乾淨背景做基線，再加雜亂背景對照。

### 何時把 cup 降級為 backup、只用 chair / laptop

**降級條件（用 §6 gate 判定）：**
- 若 cup matrix 在 1.5m **5-trial success <4/5**（DEGRADED 或 FAIL），且
- chair（預測最強：大 ~300×200px@1m、規則、不依賴顏色）在同條件 ≥4/5 →
**主秀換 chair**（必要時加 laptop），cup 降為 backup「近距加分項」，台詞限「約 1 公尺、桌上水杯」，移除任何「2m / 地上 / 通用物件」語言。chair/laptop 目前 **unmeasured，不可預先 claim**，必須先跑 matrix 取得數字才能升為主秀。

---

## 5. Tool Boundary（工具邊界）

| 工具 | 定位 | 邊界規則 | 升級條件 |
|---|---|---|---|
| **Roboflow Supervision** | **離線 CSV / 分析 only，非 live node** | NumPy-centric post-processing/viz 層，非 hard-real-time。重依賴樹（annotators、dataset I/O、matplotlib-class viz）競爭 8GB 統一記憶體 + CPU，無確定性保證。live node 已擁有價值路徑（TensorRT FP16 + thin JSON publisher）。ByteTrack/zones 屬 `interaction_executive` 或離線。 | 僅在開始產量化 eval report（§9 item 5）時採用離線；除非放棄自家 tracker 且 runtime 需 ByteTrack 並通過 RAM/CPU budget 測試，否則**永不進 live node** |
| **PINTO_model_zoo** | **post-demo spike only** | 480+ 預轉模型 + ONNX-surgery（`onnx2tf`、`sog4onnx` 等）。用於「換 backbone / fused-NMS graph 是否勝過 YOLO26n」當天 benchmark。保留在 `benchmarks/`，**永不成 runtime 依賴**。 | 僅當 item-5 eval 顯示 YOLO26n 某目標類別失敗 **且** 懷疑是模型架構問題；或需 fused-NMS/preprocessing-in-graph ONNX 回收 Nano CPU |
| **input resolution（`imgsz`）** | **唯一被物理證成的 live-node 槓桿** | 模型大小在固定像素下只給增量；input 解析度主導小物件。`imgsz` 640→1280 等於每物件像素寬加倍。 | item-5 log 顯示 cup/bottle 2m 系統性低 conf 時，**先升 `imgsz`**（單 pass、便宜）再考慮其他 |
| **SAHI / tiling** | **離線分析 only** | N× 推理 + merge/NMS latency 打擊，live loop 不可接受。 | 僅在更高 single-pass 仍 miss 時，對錄製 frame 做離線分析；**永不進 live node** |
| **YOLO26s** | 升級候選 | 固定像素下對小物件幫助有限（res 主導）。 | item-5 顯示非小物件類別 acc 不足且 RAM/CPU budget 測試過 |
| **segmentation（YOLO-seg）** | 升級候選 | nano-seg overhead 小（~1.89ms）但真實成本是 RAM/CPU 競爭 + Python mask 後處理。 | 僅當互動 policy **實際需要 sub-bbox 幾何**（如物件-表面關係、精確 occlusion）且 RAM budget 過。預設維持 bbox-only |
| **pose upgrade（YOLO-pose）** | 升級候選 | 已跑 MediaPipe Pose 做 sitting/fall。 | 僅當 MediaPipe 在我們距離準度失敗、且想單一 GPU backbone 時 |

**一句話**：Supervision / SAHI / PINTO 全是**離線 / spike 工具，排除在 live ROS hot loop 外**；runtime 維持 YOLO26n + TensorRT FP16 + thin event publisher。物理證成的唯一 live 槓桿是 **input resolution** 或 **物理拉近距離**，不是更大模型。所有升級 gate 在 **item-5 eval log**。

---

## 6. Pass/Fail Gates（通過/失敗閘門）

| Gate | 條件 | 失敗動作 |
|---|---|---|
| **object 主秀** | 主秀物件 5-trial **≥4/5 success** 才可當 primary demo object | <4/5 → 降為 backup，換 chair/laptop 主秀；全未達 → object 不上主秀 |
| **sitting 誤判** | sitting 誤判率 **>10%** → 不可講「坐下來了」 | 改台詞：`ros2 param set /brain_node greet_require_sitting false`、台詞去掉「坐下」；smoke <4/5 同樣不講 sitting |
| **thumbs_up idle 誤觸** | idle 狀態下 thumbs_up false-trigger **必須 = 0** | 任何 idle 誤觸 → 調 `gesture_stable_s` 上調、或該手勢退出 demo 路徑 |
| **Studio 證據鏈** | 截圖**必須同時**顯示 4 感知 chip + brain trace entry + tts_speaking bubble | 缺任一 → 不算有效證據，不可宣稱「Studio 顯示完整證據鏈」；**不可宣稱 LED pass/fail chip wall**（前端不存在）|
| **face 陌生人** | （已知缺口）idle 僅空畫面，真實陌生人拒絕未驗證 | 不講「不會認錯 / 門禁級」 |
| **cup 距離** | demo 必須 ≤1.5m（≤1m 最穩） | 超距 → 不講、或拉近 |

---

## 7. Demo Claim Table（展示宣稱表）

### NAV

| 能講 | 不能講 | fallback 台詞 |
|---|---|---|
| 「收到短距前進指令會自己走一小步並到點停下」 | 「自主導航 / 連續走 / 走到指定地點 / goto_named」 | 「目前展示的是短距前進到點停，定點導航在更大場地才有意義」 |
| 「前方有障礙會停下，不撞、不暴衝」 | 「會繞過障礙 / 動態避障 / 說停就停」「停了不會再走」（反向錯誤） | 「它偵測到前方障礙會停下等待，障礙移開後會自己繼續」 |
| 「我們找到並修正了窄場誤擋的感測原因」 | 「能在窄場自主穿越」（未錄到） | 「窄場感測修正已驗證，穿越錄影是下一步」 |

### VISION

| 能講 | 不能講 | fallback 台詞 |
|---|---|---|
| 「認得已註冊的人，不會把空場景誤判成人」 | 「門禁級 / 不會認錯 / 2m / 通用人臉 / 陌生人拒絕」 | 「目前驗證的是註冊者辨識，陌生人拒絕還在補資料」 |
| 「近距（約 1 公尺）看到水杯會辨識出來」 | 「通用物件 / 80 類 / 2m / 即時 / 地上水杯絆倒 / 物件觸發 Go2」 | 「物件辨識先驗證近距單一物件，更多類別與距離在量化中」 |
| 「比讚會回應（靜態手勢）」 | 「手勢辨識通過 / 揮手 wave」（wave recall=0.0） | 「靜態手勢可動，動態揮手還在修，是不同的處理路徑」 |
| 「Safety 層用規則擋掉危險指令（91 測試 + Studio 顯示）」 | 「實機端到端驗證過 / 不會幻覺 / persona 驗證過」 | 「安全層邏輯有 91 個測試綠 + Studio 即時顯示，實機 e2e 還在排」 |
| — | 「說停就是安全停車」（voice.stop fail 0.667）| 「語音停是便利指令，不是安全機制」 |

---

## 8. Tomorrow Dev Tickets（明日開發票 — 僅最小真實程式碼）

> 只列真實程式碼 ticket。research 項目不列為 committed dev（見 §9）。

### T1 — nav blocker fix（client 端 + server 端自我取消）
- **files**：`scripts/send_relative_goal.py`（`main()` L78-85）；`nav_capability/nav_capability/nav_action_server_node.py`（`_execute_nav_goal_with_pause_aware` L223-293）
- **內容**：client 在 KeyboardInterrupt/exception path 呼叫 `handle.cancel_goal_async()` 再 destroy；shutdown 改 idempotent（`if rclpy.ok(): rclpy.shutdown()` 一次）。server 加 client-liveness watch → disconnect 時 auto cancel/timeout active goal（不可在 AMCL/odom 瞬斷時誤殺仍在前進的 goal）。
- **acceptance**：殺掉 in-flight client 後，下一個 `goto_relative` **被接受**（不再 `another goto still active`）；server node 不崩。
- **WSL-doable**：client patch 可 WSL 寫+靜態檢查；**server auto-cancel 需硬體驗證**（client-liveness 真實 disconnect）。

### T2 — indoor-tight low-speed profile launcher
- **files**：新 `scripts/start_nav_tight_low_speed_tmux.sh`（複製 `start_nav_capability_demo_tmux.sh` 9-window，reactive 行改 `-p front_arc_deg:=15 -p danger_distance_m:=1.0 -p slow_speed:=0.2 -p normal_speed:=0.3`）
- **內容**：永久化 6/8 窄場修正；保留主 launcher（±30°/1.1m）給開放空間。無需改 yaml（CLI `-p` override）。
- **acceptance**：啟動後 `ros2 param get` 顯示 front_arc_deg=15；窄場通道 `nav_paused=false`。
- **WSL-doable**：腳本可 WSL 寫；**zone clear 行為需硬體驗證**。

### T3 — LiDAR sector / skew debug 錄製腳本
- **files**：新 `scripts/record_skew_diag.sh`（`ros2 bag record /cmd_vel_nav /amcl_pose /odom /scan_rplidar` + 2-3 趟 goto driver）
- **內容**：把 §2(d) 的三 topic 一鍵錄成 bag 供離線判讀 H1/H2/H3。
- **acceptance**：跑完產出 bag，含三 topic 非空，可離線比對 angular.z vs amcl-yaw vs odom-yaw。
- **WSL-doable**：腳本可 WSL 寫；**錄製需硬體**。

### T4 — object-matrix capture + offline CSV
- **files**：新 `benchmarks/scripts/obj_eval_live_capture.py`（複製 `capture_baseline_round.py:114-157` lazy-import-rclpy fixed-window pattern，但 object callback **每物件寫一 CSV row**、**保留 bbox**、`objects==[]` 時寫 `detected=False` row、加 `light`/`angle`/`lux`/`trial`/`debug_img_path` CLI 欄位）；新 `benchmarks/scripts/obj_eval_offline_aggregate.py`（pandas groupby `(object,distance,light,angle)` → `≥4 PASS / ==3 DEGRADED / <3 FAIL`）
- **acceptance**：跑一輪輸出 per-detection CSV（含 bbox 四欄）；aggregate 對每格輸出 PASS/DEGRADED/FAIL。純 `csv.DictWriter` + pandas，**Jetson 零新依賴**（不用 Supervision）。
- **WSL-doable**：capture 邏輯 + aggregate 可 WSL 寫+用假資料測；**真實 matrix 收集需硬體 + 相機**。

### T5 — Studio evidence checklist 驗證腳本
- **files**：新 `scripts/check_studio_evidence.sh`（確認 gateway boot log「10 String topics + /tts + 2 Bool」；echo 四感知 topic + `/brain/skill_result` + `/tts` 各一次確認非 mock）
- **內容**：把 §3/§6 的 Studio 證據鏈 gate 自動化，避免 demo 當天靠肉眼。
- **acceptance**：腳本回報四感知 chip + brain trace + tts 全有訊號（real `studio_gateway` 非 `mock_server.py`，用 `ros2 topic info -v` 證 publisher）。
- **WSL-doable**：腳本可 WSL 寫；**驗證需 Jetson 跑 gateway**。

---

## 9. Long-Term Ideal Roadmap（研究 + 紀錄，POST-6/18 — 全部 future work，非 6/18 承諾）

> 階段依賴序：**自由巡邏 → 動態繞行 → D435+LiDAR fusion local costmap → 視覺目標導航 → 模型升級**。
> 實際技術依賴序為 **costmap fusion(2) → layered(3) → MPPI controller(1) → visual-goal(4)**：depth 要先進 costmap 並與 LiDAR fuse，controller 才有東西可繞；視覺目標導航前提是前三者都過。
> Jetson Orin Nano 8GB 標籤：maturity / effort / risk。

### Phase 1 — 自由巡邏（free patrol）
- 現有 route_runner + named_pose + AMCL 已具基礎；自由巡邏 = 預存 waypoint loop。**maturity 高 / effort 低 / risk 低**（已有 RunRoute action）。仍受 8GB 兩 stack 互斥限制。

### Phase 2 — 動態繞行（dynamic detour，stop-only → controller）
- 現 `reactive_stop` 是 stop-only velocity scaler，**數學上無法轉向**：Nav2 collision_monitor 同類設計「只管速度大小與縮放，不改方向/heading」（[collision-monitor-node](https://docs.nav2.org/configuration/packages/collision_monitor/configuring-collision-monitor-node.html)、[collision_monitor](https://docs.nav2.org/configuration/packages/configuring-collision-monitor.html)）。繞行需 controller 產生新軌跡。
- **目標 = MPPI controller**：可調 critic（降 `ObstaclesCritic`/`CostCritic` 權重保留 `PathAlignCritic` → 偏離 path 繞動態障礙），含 `VelocityDeadbandCritic`（[MPPI README](https://docs.ros.org/en/humble/p/nav2_mppi_controller/__README.html)、[Tuning](https://docs.nav2.org/tuning/index.html)）。
- **0.5 m/s floor 是核心問題**：Go2 sport mode 忽略 <0.5 m/s 的 Move；MPPI default `vx_max:0.5` 已頂 Go2 floor → 避障幾乎全靠 yaw（`wz_max:1.9`）。用 `VelocityDeadbandCritic` 的 `deadband_velocities` 或 velocity_smoother `deadband_velocity`（[Velocity Smoother](https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html)、[MPPI Humble API](https://docs.ros.org/en/ros2_packages/humble/api/nav2_mppi_controller/)）設 ~0.5，讓 MPPI 要嘛真的走 0.5 arc 要嘛乾淨停 → 繞行變「停、原地轉到淨空 heading、走 0.5 arc」而非平滑滑行。
- **maturity 高（MPPI 是 Nav2 推薦 controller）/ effort 中（controller swap + 重 critic 調參，全 HITL）/ risk 中-高**（8GB Nano 6×A78 較弱，`batch_size` 降 ~400-600、20-30Hz；0.5 floor 使繞行粗糙，需對窄場家具驗證 — 正是 6/8 已現 false-positive 之處）。

### Phase 3 — D435 + LiDAR fusion local costmap
- depth 進 costmap 三路：`depthimage_to_laserscan`（單帶、丟垂直結構）/ `pointcloud_to_laserscan`（全平面、CPU 較高）/ **voxel layer**（保高度，`min/max_obstacle_height`、`z_resolution:0.05`、`z_voxels:16`；[Voxel Layer](https://docs.nav2.org/configuration/packages/costmap-plugins/voxel.html)、[pointcloud_to_laserscan](https://github.com/ros-perception/pointcloud_to_laserscan)）。Intel 建議 D435 marking range ≤1.25m（[ROS Answers](https://answers.ros.org/question/382873/)）。
- **兩個已知故障**：stale voxel（看到後移除的障礙殘留擋路；[Nav2 #4653](https://github.com/ros-navigation/navigation2/issues/4653)）；幾何（D435 ~20cm 盲區、深度量平行平面非真實 range、僅支援前向；[RealSense](https://ardupilot.org/copter/docs/common-realsense-depth-camera.html)）→ 低障礙（鞋/電線）盲。
- **正確配置 = 單一 local costmap 兩 `observation_sources`**：RPLIDAR `LaserScan`（密近 360° 平面）+ D435 高度通道（[Obstacle Layer](https://docs.nav2.org/configuration/packages/costmap-plugins/obstacle.html)、[Setting Up Sensors](https://docs.nav2.org/setup_guides/sensors/setup_sensors.html)）。**相機通道用 STVL**（時間衰減 voxel，治 stale-voxel bug，宣稱降 3D sensor 資源 ~2×，須排在 inflation 前；[STVL](https://docs.nav2.org/tutorials/docs/navigation2_with_stvl.html)），LiDAR 用 plain obstacle layer。plugin 疊序：obstacle(LiDAR) → stvl(D435) → inflation。6/8 LiDAR 幾何事實（±15-20° / danger 1.0 / yaw=π 反裝 / Go2 機鼻 ~50-60cm vs LiDAR 17.5cm）併入 inflation 調參。
- **maturity 高 / effort 中（denoise + mount 校正全 HITL）/ risk 中**（8GB 兩 sensor stream 進一 costmap；STVL 2× 效率是選它而非 stock voxel 的理由；低障礙盲是永久幾何限制）。

### Phase 4 — 視覺目標導航（object bbox + depth → map goal → NavigateToPose）
- pipeline：detector bbox → D435 depth 在該 pixel + intrinsics 投 3D（[arXiv 2506.13367](https://arxiv.org/pdf/2506.13367)）→ TF 轉 map frame → `PoseStamped(frame_id:map)` 設**standoff offset**（物件前方非物件本身）→ `NavigateToPose`（[Clearpath Nav2 Actions](https://docs.clearpathrobotics.com/docs/ros/tutorials/navigation_demos/actions/)）。
- **非 trivial 點**：不可投 raw bbox — 「direct projection 會致導航失敗」，建議 bbox 內 segmentation + erosion 排除邊界（[arXiv 2410.21926](https://arxiv.org/pdf/2410.21926)）；robust 版建小 semantic map（[arXiv 2007.00643](https://arxiv.org/pdf/2007.00643)）。PawAI v1 務實版：bbox 內核 median depth、goal 朝機器人偏移 ~0.6-0.8m、拒絕落在 costmap-lethal cell 的 goal。
- **maturity 研究成熟/整合不成熟 / effort 中-高（robustness 工作主導）/ risk 高**（bbox→goal 投影是已知故障點，且疊在 1-3 全過之上）。**最後做**。

### Phase 5 — 模型升級（YOLO26s / segmentation / pose）+ 視覺 eval 基礎
- **先做 item-5 eval（POST-6/18 第一件）**：embodied perception 因失焦/震動/光照失敗、預訓 detector 系統性 overconfident（[arXiv 2505.16815](https://arxiv.org/html/2505.16815)、[RoboBench 2510.17801](https://arxiv.org/html/2510.17801v1)）。方法：log 每偵測 distance/lighting/angle/bbox-px/conf + 存 failure frame，分 (1)2D 偵測 (2)空間 lift (3)導航/互動 三階段各自 metric。用 Supervision 離線算 mAP/AP-small/confusion。**所有其他升級 gate 在此數字上**。
- **小物件物理**：9cm cup@2m ~20px 在 YOLO recall 崩潰區（COCO 「small」<32×32px、floor ~10-15px；[Joel Huang](https://joelhuang.dev/blog/small-object-detection)、[Labellerr](https://www.labellerr.com/blog/small-object-detection/)、[arXiv 2401.12729](https://arxiv.org/pdf/2401.12729)）。**26s vs 26n 在固定像素下幫助有限 — input 解析度主導**（640→1280 倍增每物件像素；[ultralytics #24732](https://github.com/ultralytics/ultralytics/issues/24732)、[Pysource SAHI](https://pysource.com/2025/04/23/how-to-accurately-detect-small-objects-with-yolo-and-sahi/)）。
- **seg/pose 成本**：YOLOv8n-seg overhead ~1.89ms「minimal」（[emergentmind](https://www.emergentmind.com/topics/yolov8-seg-model)）、Orin Nano nano-detect ~4.57ms/im TRT FP16（[Ultralytics Jetson](https://docs.ultralytics.com/guides/nvidia-jetson)、[YOLO11 Orin Nano](https://www.ultralytics.com/blog/ultralytics-yolo11-on-nvidia-jetson-orin-nano-super-fast-and-efficient)）— 真實成本是 RAM/CPU 競爭 + Python mask 後處理。
- **PINTO_model_zoo**：480+ 預轉模型 + onnx2tf/NMS-surgery（[DeepWiki](https://deepwiki.com/PINTO0309/PINTO_model_zoo)、[conversion tools](https://deepwiki.com/PINTO0309/PINTO_model_zoo/7.3-conversion-and-deployment-tools)、[GitHub](https://github.com/PINTO0309/PINTO_model_zoo)）— 當天 benchmark 候選 spike。
- **maturity 高（eval 方法 + 模型皆成熟）/ effort 中 / risk 中**（升級的真實風險是 8GB RAM/CPU 競爭，非 FPS）。**全部 future work，非 6/18 承諾**。

---
*報告結束。所有 HARDWARE_PROVEN 僅 4 項（short goto / safe-stop / face / cup，皆窄版單點），其餘標籤如實降級。*
