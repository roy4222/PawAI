# PawAI 5/22~6/18 北極星 — 從功能整合走向定位清楚、可自主移動的居家四足機器人

> ⚠️ **本文件已被 v2 supersede**：見 [`2026-05-22-pawai-may-june-north-star-v2-design.md`](2026-05-22-pawai-may-june-north-star-v2-design.md)
>
> v2 修正：定位從「居家陪伴四足機器人」改為「**室內場域具身 AI 任務 POC**」；P0/P1/P2 線性切法改為 **L1/L2/L3 三層擴充模型**；commit 策略改為 **Spike-then-commit**（W1 驗 3 個硬 gate，分項決定 L2 升級深度）。本文件保留作歷史紀錄，新工作以 v2 為準。
>
> 文件類型：北極星（問題陳述 + 目標成果 + 驗收標準）
> 日期：2026-05-19（驗收第一天）
> 窗口：2026-05-22 ~ 2026-06-18
> 每章固定格式：現況 → 根因 → 6/18 目標 → 驗收標準 → 優先序與風險

---

## 0. 背景

5/18 對指導老師現場 demo 後，老師最關鍵的回饋是「PAI 的定位問題——狗 / 機器人 / 助理需要重新思考」；5/19 老師進一步收斂出「智能守護與陪伴，不是助理、也不是寵物」的方向。同時 demo 暴露物件偵測效果差、手勢誤觸嚴重、姿勢辨識不穩、導航只能停障等問題。

這份文件是 5/22~6/18 窗口的北極星：它說明這個月「希望解決的問題」、各問題的目標成果與驗收標準，**不排每日任務、不指派負責人**——任務拆解留給後續的 implementation plan。

它也明確擋掉「看起來酷但會把四週炸掉」的東西（見第 8 章）。北極星不只說做什麼，也說不做什麼。

---

## 前置：Week 0｜Spec A 收尾（窗口啟動先決條件）

### 為何在北極星
5/14 Spec A「demo 主線止血」plan 的 4 個 PR 目前一個都沒 merge 進 main，Day 0 recovery（branch/stash 漂移收拾）也未完成，`pawai demo preflight` 工具不在 main 上。第 3 章（手勢 gate）、第 5 章（姿勢 Brain-side simulation）、第 6 章（TTS 單出口、Brain bring-up deps）的止血改動就壓在這些未 merge 的 PR 裡。北極星其他章在此之前是地基懸空。

### Week 0 必須完成
1. **Day 0 recovery**：收拾 4 個 `spec-a/pr*` branch 的 commit 漂移、清未用 stash、確認工作樹乾淨。
2. **4 PR 依序 merge**（嚴格序列，PR2A 的 `pose_grounding_code_ready` 要 PR3 後才 PASS）：
   - PR1 — Brain bring-up deps（langgraph / langchain-core 進 requirements）+ persona 文案收斂
   - PR2A — preflight 機械檢查 + TTS guard + demo start hook
   - PR2B — preflight semantic dry-run
   - PR3 — gesture conversation gate + pose Brain-side simulation（降級方案）
3. **Jetson Hardware Bring-up Gate**：sync main → `uv pip install` → import 驗證 → colcon build → `conversation_graph_node` 5 秒無 ImportError。

### 完成判準
4 PR 全在 `origin/main`；`pawai demo preflight` 兩階段（dev local + Jetson post-start）全 PASS。**未過此關，不啟動 5/22 窗口的 P0 工作。**

---

## 1. 定位收斂（P0｜基礎）

### 現況
PawAI 不是「沒有定位」，而是三份文件對「PawAI 是什麼」講不出同一個版本：
- `docs/mission/README.md:39` —「居家互動機器狗，互動 70% / 守護 30%」
- `personas/v1/MISSION.md:11,22` —「自主尋物＋具身互動」，兩大支柱是「Brain＋導航避障」
- `personas/v1/IDENTITY.md:22` —「70% 小狗 / 20% 童心 / 10% 守護」

5/18 老師指出定位不明；5/19 進一步收斂出「智能守護與陪伴」方向。

### 根因
1. 定位從未被任何一份文件統一收束，各模組各自發展。
2. persona 偏狗式互動，但 demo 與文件骨架仍偏語音助理與功能清單——狗是皮，骨架是助理。
3. 功能之間沒有被一條「任務」串起來，看起來是並列的功能清單，不是一個系統。

### 6/18 目標
三份文件統一為老師收斂版定位：

> **PawAI 是一套以 Unitree Go2 為載體的智能守護與陪伴型居家四足機器人。它不是語音助理，也不是單純寵物；它整合語音、文字、LLM、視覺感知與 Skills，理解家庭情境後，以語音、動作、提醒、短距移動與趣味互動提供陪伴與安全守護。**

定位三層：
- **類別**：居家四足機器人
- **核心價值**：智能守護與陪伴
- **互動風格**：狗式互動 / 趣味 Skills（降一階，不放主定位首句）
- **非目標**：不是語音助理、不是單純寵物

四大價值支柱（取代舊的「互動 70% / 守護 30%」比例）：

| 支柱 | 內容 | 與一般助理的差異 |
|---|---|---|
| 生活問答 | 天氣、出門提醒、情緒陪伴 | 結合當下情境與機器狗動作回應，不是純語音回答 |
| 物件偵測 | 理解家庭環境中的常見物品；未來配合導航發展成接近尋物/協助找物 | 物件不是清單辨識，而是 Brain 的環境 grounding |
| 安全守護 | 身分辨識、陌生人提醒、跌倒/姿勢異常、移動前安全仲裁 | 安全狀態會影響是否允許 Skills 或移動 |
| 陪伴娛樂 | 語音聊天、故事、趣味 Skills、靜/動態手勢、站起/陪坐/伸懶腰等具身回應 | 狗式互動風格落在這裡，提供在場感 |

任務閉環（每個功能的存在意義對齊到這條閉環）：

| 階段 | 對應能力 |
|---|---|
| 理解輸入 | 語音 / 文字 |
| 感知家庭情境 | 人臉 / 姿勢 / 物體 / 手勢 / 導航狀態 |
| LLM/Brain 決策 | 意圖判斷 / 任務拆解 / Skills 選擇 |
| Safety/Executive 仲裁 | 安全守護 / 能力狀態 / 移動前檢查 |
| Skills 回應 | 語音 / 動作 / 短距移動 / 趣味互動 / Studio 回報 |

整合度高 = 這條閉環一氣呵成，不是逐功能輪播。

### 驗收標準
- `docs/mission/README.md`、`personas/v1/MISSION.md`、`IDENTITY.md` 三處定位 statement 改為一致（老師收斂版）。
- 八大功能/persona 文字對齊到四大價值支柱。
- 6/18 demo 能以一條任務閉環串起功能（見第 7 章），而非逐功能展示。
- Demo 開場 30 秒內能說清 PawAI 的類別、價值、非目標與四大支柱。

### 優先序與風險
- **P0｜基礎**——其他章的錨點，第一週內定稿。
- 風險低：此版直接採用老師 5/19 說法，無張力。唯一工作是把既有文件與 persona 文字對齊，屬文件治理。

---

## 2. 物件偵測（P0-C｜環境 grounding）

### 現況
物件偵測在 5/18 demo 表現極差。現況（`object_perception_node.py` + 0511 object 文件）：
- 模型 YOLO26n（2.4M 參數、9.5MB、COCO mAP 40.1%），ONNX Runtime + TensorRT EP FP16
- 輸入 640×640 letterbox、~15 FPS、conf 門檻 0.5、COCO 80 類全開
- 顏色用 HSV 12 色純規則 bucket；無深度、無 tracking（每幀獨立偵測）

### 根因（排序）
1. **模型容量太小**——nano 對小物件（杯子/瓶子/手機/書，正是居家道具）召回率最差。
2. **輸入 640 太低**——1.5m 外的物件在特徵圖上像素過少，直接漏掉。
3. **conf 0.5 偏高**——把 0.3–0.5 的真陽性全濾掉，砍掉一半召回。
4. **TensorRT EP 可能 silent fallback 到 CPU**——provider 參數或 cache 失效時無聲掉速。
5. **HSV 顏色純規則不穩**——不知材質/光源，bbox crop 含背景污染。
6. **COCO 天花板 + 無 tracking**——學校特定物無類別；conf 抖動讓物件閃爍出現/消失，Brain 的 context 斷續。

### 6/18 目標
物件偵測不是「辨識清單」，而是 **Brain 的環境 grounding**——讓 PawAI 能可靠看懂家庭環境中的常見物品，並提供穩定的「物件＋顏色」context 給 LLM 描述與決策。

P0 範圍（皆為調參/換模型/後處理，不含訓練）：
- YOLO26s A/B（mAP 47.1%，vs 26n）
- input size A/B（640 vs 768/960）
- conf 0.5 → 0.3/0.35 A/B + class-specific threshold
- class-specific bbox 面積門檻（避免全域門檻誤殺小物件）
- IoU / temporal stable voting（消除單幀閃爍）——stable voting 可參考 DimOS `ObjectDB` 的 pending → permanent 兩層設計（看到 N 次才升 permanent），目標是「Brain 看到穩定環境」而非每幀 YOLO 結果
- 顏色改 central crop 內縮 + CLAHE + LAB/KMeans 取代純 HSV bucket
- 現場確認 TensorRT EP 真的生效、無 silent fallback CPU

**Future work（本窗口不做）**：5/22~6/18 不做完整自建資料集訓練；但需建立下一階段資料來源候選——HomeObjects-3K、Open Images、Objects365、YCB/BOP、SUN RGB-D/ScanNet。若 YOLO26s + 後處理仍不足以穩定支撐固定展示物，下一階段以 HomeObjects-3K + PawAI 自拍資料（200–500 張/類，只針對 demo 類別）做 fine-tune，不一開始就跳 Open Images / Objects365 大訓練。

### 驗收標準
- 必達展示集（杯子、手機、書、椅子、背包）在 demo 距離 1–2m 能穩定辨識；瓶子、遙控器、時鐘列為觀察集，不作必達承諾。
- 同一物件需通過 IoU / temporal stable voting 後才進 Brain context，避免單幀閃爍污染 LLM。
- 對高飽和、單一主色物件能穩定輸出主色；低飽和、反光、多色物件允許 Unknown，不硬猜。
- Brain 能在對話中自然引用最近穩定看到的物件。
- Jetson 實測 FPS / RAM / 溫度在升級後仍在安全預算內，且確認 TensorRT EP 沒有 fallback 到 CPU。

### 優先序與風險
- **P0-C｜環境 grounding P0**——支撐定位中「物件偵測」支柱與任務閉環的「感知家庭情境」段。
- 風險：換模型須重建 TRT cache（首次 3–10 分鐘）；解析度提高會掉 FPS，需與 tick_period 一起調；**絕不可 `pip install ultralytics`**（破壞 Jetson torch wheel），只換 `.onnx` 檔。
- 工程量：中（模型/參數/後處理升級，約 1 週）。

---

## 3. 手勢辨識（P0-B｜互動可靠性）

### 現況
手勢辨識在 5/18 demo 誤觸嚴重——手只是自然放著就一直觸發動作。現況（`vision_perception_node.py` + 0511 gesture 文件）：
- vote buffer 5 幀 + stable gate `gesture_stable_s` 0.3s（N7 為了 fist 反應快，從 0.5s 放寬）
- 6 靜態手勢（palm/fist/index/ok/thumbs_up/peace）+ wave 動態手勢
- conversation gate 只保護 `{wave, fist, index}`；dedup window 僅 1.0s

### 根因（排序）
1. **沒有同手勢冷卻**。手放著時 classifier 在 `fist ↔ ok ↔ peace ↔ None` 間抖動；現有 gate 只看「連續相同 label」，label 一換就重新計時並 re-fire。這是誤觸主因。
2. **`thumbs_up/peace` 不受 conversation gate**。即使不直接執行動作，誤判時仍會插入 OK 確認提示，干擾互動。
3. **dedup window 太短（1.0s）**——抖動產生的事件間隔常 >1s，輕鬆穿過。
4. **沒有「進入手勢模式」總開關**——任何時刻只要鏡頭有手，pipeline 就一路觸發。
5. legacy `event_action_bridge` 雙路徑——若與 executive 同跑，wave 會被處理兩次。

### 6/18 目標
手勢辨識的 P0 不是增加更多手勢，而是把「看見手」和「使用者有意互動」分開。6/18 前的成功標準是：平時不亂觸發、刻意揮手能打招呼、OK 能明確進入/退出手勢模式。

P0 範圍：
- **短期止血**（小改）：加同手勢冷卻（per-label，3–5s）、`thumbs_up/peace` 納入 conversation gate、dedup window 拉長至 3–5s、`gesture_stable_s` 視效果調回保守值。
- **OK 模式開關**（治本）：新增 `GestureModeGate`：
  - `DISABLED`（預設）：只允許 wave / palm / ok；其他靜態手勢事件全部丟棄。
  - `ENABLED`：允許靜態手勢轉技能，但仍需 per-label cooldown 與 conversation gate。
  - 偵測到 OK 並穩定後切換模式並語音提示；復用現有 OK 偵測與 PendingConfirm 的 release-gate 邏輯。
  - `palm` 作為 safety gesture 可 bypass；`wave` 作為打招呼入口可 bypass，但必須通過較高門檻與 5–8 秒 cooldown。
- 確認 demo 腳本沒同時啟 `event_action_bridge`。

P0 不承諾「6 靜態手勢各自都穩」——這跟「少誤觸」目標衝突。P0 是 wave / palm / OK 穩定可靠，其他靜態手勢只在 ENABLED 模式中被辨識與觀察。

### 驗收標準
- **Idle**：手自然放在鏡頭前靜止 30 秒，不觸發任何動作或語音。
- **Wave**：刻意揮手 10 次，至少 8 次觸發打招呼；走動/整理手部不偽觸發。
- **OK mode**：OK 能進入/退出手勢模式，且有語音或 Studio 回饋；DISABLED 時 thumbs_up/peace/fist/index 不觸發技能。
- **Conversation gate**：TTS 播放或對話進行中，非 safety 手勢不打斷語音互動。
- **ENABLED 模式**：靜態手勢可被辨識並顯示在 Studio；高風險動作仍需 OK 或確認，不直接觸發。

### 優先序與風險
- **P0-B｜互動可靠性 P0**——支撐定位中「陪伴娛樂」支柱的狗式互動，誤觸會直接毀掉 demo 觀感。
- 風險：OK 模式開關引入「先比 OK 才能下手勢」的互動約定，使用者/老師需要被告知；wave 在走動場景的偽觸發需實機驗（建議提高 `min_amplitude_px`）。
- 工程量：短期止血約 1 天；OK 模式開關約 2–3 天（含測試與上機）。

---

## 4. 導航避障（P0-A｜核心閉環）

### 現況
導航是 PawAI 從「會互動」進化到「能在家庭空間中行動」的核心能力。0511 nav 文件顯示，PawAI 已有一套貼近 Go2 的 navigation stack：RPLIDAR 建圖/定位/避障 + AMCL/Nav2 規劃 + reactive_stop 止損 + twist_mux 仲裁 + Go2 driver。這套 stack 已處理四足特性：Go2 速度門檻、LiDAR mount yaw=π、機鼻安全距離與 teleop/nav/reactive_stop 控制權衝突。`nav_capability` 也已提供 `/nav/goto_relative`、`/nav/goto_named`、`/nav/run_route`、`/nav/pause|resume|cancel`、`/capability/nav_ready|depth_clear` 與 `/state/nav/status`。

PawAI 不缺 Hiwonder 那種導航架構，已有更貼近 Go2 的版本；缺的是「產品化接線」與「安全成熟度」。整合方向是把自然語言任務層接到既有 `nav_capability`，而非換掉 nav stack。

### 根因
1. **Executive NAV executor 未實作**——`interaction_executive_node.py:220` 仍是 `nav_unimplemented_phase_a`。Brain 知道 NAV skill、SafetyLayer gate 也接好，但「真正把 NAV step 送到 `/nav/goto_relative`」沒做 → 語音/Brain 無法直接叫 Go2 走。
2. **`nav_ready` 太薄**：目前只看 AMCL pose 曾出現與 covariance，缺 lifecycle active、`map -> base_link` TF、costmap freshness、scan freshness、`/cmd_vel_nav` publisher sanity，可能 false positive。
3. **避障是止損、不是繞行**：`reactive_stop` 是 safety brake；D435 目前只是 `/capability/depth_clear` fail-closed gate，不會 stop 已在跑的 Nav2 goal，也尚未進 Nav2 local costmap。

### 已踩坑與治理結論
- **5/11 撞牆真主因是控制權仲裁，不是感測視野不足**：`safety_only` 在 clear zone 沉默，`twist_mux` timeout 後殘留 `/cmd_vel_joy` 接管。治理結論：nav demo 前必查 `/cmd_vel_joy` 無 hot publisher，reactive_stop 使用 4-mode 狀態機，不再使用舊 `safety_only` 敘事。
- **Go2 零速不等於急停**：`cmd_vel=0` 曾無法保證停車。治理結論：零速走 `StopMove(1003)`，`Damp(1001)` 不當移動中急停。
- **LiDAR threshold 必須按機鼻距離重算**：舊 `danger=0.6m` 對 Go2 太近。治理結論：主線使用 `danger=1.1m / slow=1.7m`，後續做 base_link projection。
- **detour profile 不可直接用**：舊腳本含 `safety_only`、低 danger threshold、yaml drift、D435 TF 臨時值。治理結論：6/18 不以 detour profile 作必達展示。
- **F7 是 P0 blocker**：5/12 出現 goal accepted 但 `/cmd_vel_nav` 不出。治理結論：場測第一件事驗 `goto_relative` motion；若無法根治，需 watchdog 與明確降級策略。

（其他已知坑如 slam_toolbox ARM64 棄用、setuptools<70、`/goal_pose` QoS race 等，留在 implementation plan 與 nav 文件，不入北極星主章。）

### 6/18 目標（兩段）

**必達 P0｜止損級 + 語音叫得動**
- 語音或 Studio 可觸發短距自主移動；Brain/Executive 走 NAV executor。
- 支援 `goto_relative 0.3–0.5m` 與至少 2 個命名地點；移動前檢查 `nav_ready`、`depth_clear`、`nav_paused`，高風險需 OK 確認。
- 前方障礙時 reactive_stop 讓 Go2 停下，並語音/Studio 回報「前方有障礙，我先停下來」。
- 每次 nav demo 前必須 preflight：`/cmd_vel_joy` 無 hot publisher、twist_mux inputs 正常、`map -> base_link` TF 可查、Nav2 lifecycle active、`/cmd_vel_nav` publisher sanity 通過。

**加分 P1｜繞行 / 局部重規劃**
- 障礙清除後可 resume 或重送 goal。
- 受控場地中展示一次靜態障礙的局部重規劃或繞行；繞行失敗必須降級為停車 + 等待/重送 goal。
- 重規劃可參考 DimOS 的 `ReplanLimiter`（同區域限次重規劃 + 走遠歸零）與 stuck detection（時間窗位移），用以避免在死角無限 recovery 抖動。
- D435 depth 參與 `nav/pause` 或 local obstacle observation 的實驗線。
- 評估 Nav2 `collision_monitor` 作為 reactive_stop 的正式替代。

### 驗收標準
- **必達 gate**：「PAI，過來一下」→ Brain 產生 nav skill → Executive 過 safety gate → Go2 走 0.3–0.5m → 遇障停 → 回報原因；命名地點導航（≥2 點）可運作。
- 障礙移開後 Go2 不可自動暴衝；必須等待明確 resume、重送 goal，或保持停車並回報狀態。
- **加分 gate**：受控場地至少一次成功局部重規劃/繞行，失敗能安全降級為停車。
- 整條閉環在 Studio 可見 nav/depth/paused 狀態與「為什麼停」。

### 優先序與風險
- **P0-A｜核心閉環 P0，吃滿四週**——任務閉環「安全移動」段，也是定位中「短距移動提供陪伴與守護」的物理基礎。
- 未解風險（6/18 前要管理）：

  | 風險 | 嚴重度 | 要做的事 |
  |---|---|---|
  | F7：goal accepted 但 `/cmd_vel_nav` 不出，10s timeout ABORT，Go2 不動 | P0 blocker | 場測第一件事就測 motion；根治或加 watchdog（demo 連跑 30min+ 會撞 stale state） |
  | nav_ready 太薄會 false positive | 高 | 只補 lifecycle + TF + scan freshness 三項，不無限加 check |
  | D435 只是 gate，不會 stop active nav | 中-高 | 必達靠 RPLIDAR 單鏈路；D435→`/nav/pause` 列加分線 |
  | progressive mode 依賴「無殘留 teleop」操作紀律 | 高 | 每次 demo 前查 `/cmd_vel_joy` 無 publisher（重演 5/11 撞牆的人為因素） |
  | detour profile 腳本有多個 bug，不可直接用 | 中 | 6/18 不展 detour，只展 danger 停車（除非先修） |

- 明確不承諾：複雜人流動態繞行、長距離跟隨人、自主尋物完整閉環、D435 完全整合進 Nav2 costmap（除非實測通過）。
- 風險底線：Go2 是四足非輪式，速度門檻、滑動與 footprint 使繞行難度高；5/3 L3 繞行曾 FAIL。因此繞行只列加分，不列必達。
- 工程量：高（四週主戰場）。

---

## 5. 姿勢辨識（P2｜降級為情境感知）

### 現況
姿勢辨識目前使用 `pose_classifier` 純規則分類，依關節高度、夾角與 bbox 幾何判斷 7 個 enum：`standing / sitting / crouching / fallen / bending / akimbo / knee_kneel`，並透過 vote buffer 做穩定化。

5/18 demo 中，`bending`、`akimbo`、`knee_kneel` 效果差且定義不明確；它們不適合作為 6/18 主動展示或技能觸發能力。

### 根因
1. 2D 骨架無深度。`akimbo` 需要正面看到雙肘外撐，但插腰時手腕常被身體遮住；`knee_kneel` 需要側面看到雙膝高度差，但側面又容易遮住支撐腳 ankle。這些姿勢本身依賴視角，單一 2D rule 很難穩定。
2. `bending` 與 `fallen` 的 guard 互相干擾。彎腰摸地、手臂前伸會改變 bbox 與 torso geometry，可能被誤報成 `fallen`；而為了避免 `fallen` 誤報加的 bbox guard，又會讓 `bending` 判斷更不穩。
3. `_majority` 缺少最低票數門檻。buffer 剛開機或姿勢轉換時，少數幀就可能形成 majority，造成開機抖動與「半坐半蹲」狀態反覆跳動。

### 6/18 目標
姿勢辨識不再追求「7 類全分類並主動觸發動作」，降級為情境感知：讓 PawAI 知道使用者大致狀態，並能在對話中自然提到。

- 6/18 demo 不主動展示、不觸發 `bending / akimbo / knee_kneel`；它們可保留為 debug/Studio 觀察項，或在 implementation 中降級為 `uncertain_pose`。
- `standing / sitting / crouching / fallen` 作為主要狀態；其中只有 `fallen` 可走 safety alert，其餘只進 Brain context，不主動打斷。
- `_majority` 加 60% 最低票數門檻，例如 20 幀中至少 12 幀同 pose 才輸出。
- 姿勢互動收斂為單一路徑，避免 Executive 與 `event_action_bridge` 雙重發話。
- 加分：用人物 bbox 長寬比、輪廓水平度、地面 band、D435 depth 或 optical flow 區分「跌倒」與「緩慢蹲下/彎腰」。

### 驗收標準
- 主要狀態 `standing / sitting / crouching / fallen` 在 demo 距離能穩定辨識。
- 使用者保持同一姿勢靜止時，不反覆刷出 pose event。
- Brain 能在對話中引用姿勢 context，例如「你現在坐著，我陪你一下」。
- `bending / akimbo / knee_kneel` 不主動觸發技能；若出現在 Studio，需標示為 uncertain/experimental。
- `fallen` 維持 safety 主線，不因降級而退化。

### 優先序與風險
- **P2｜降級項**。這是減少干擾的治理工作，不是主線能力擴張。
- 風險：`fallen` 屬安全功能，不可被一起削弱；因此只降級不穩姿勢，不碰 `fallen` 核心 safety gate。
- 工程量：低，以減法與門檻收斂為主。

---

## 6. 人臉辨識 ＋ 語音功能（維持｜小改高回報）

5/18 demo 中人臉與語音表現都不錯，本窗口不大改。原則：維持為主，只做「包裝已存在能力」的低風險小改，不碰已凍結的穩定鏈路。

### 6.1 人臉辨識

**現況**：身份判定準（YuNet + SFace + hysteresis 雙閾值，整合 smoke 2 分鐘 21 次穩定零誤判），但 track 生命週期會抖（45 次/2min）。陌生人警報已關閉——unknown ≠ 陌生人，小模型在低光/側臉/未註冊時誤判率高。

**根因**：track 抖動需重構偵測穩定性或換 tracker；多人 3+ 同框 bbox 互竄。兩者都是結構性問題，非凍結窗能解。會議提到的「人臉註冊介面」缺的不是模型能力——`scripts/face_identity_enroll_cv.py` 已存在、node 會自動偵測 DB 變更重訓——缺的是 CLI 包裝與「註冊後立即驗證」流程。

**6/18 目標**：
- 把 `face_identity_enroll_cv.py` 包成 `pawai face enroll / list / verify` 或等價 CLI，支援到校現場加同學/老師臉。
- 陌生人警報維持預設關閉，新增 trace-only / explicit-enable 模式。
- 註冊時做樣本品質檢查（偵測不到臉的照片給回饋，不靜默 skip）。

**驗收標準**：現場能用 CLI 註冊新臉並立即驗證；已註冊熟人能被穩定叫出名字；陌生人不會在空地誤觸警報。

**優先序與風險**：維持級小改，低風險（不碰 node 核心邏輯）。不碰：track 抖動根治、多人同框——標為 demo 後重構。

### 6.2 語音功能

**現況**：ASR 三層 fallback chain（qwen_cloud/SenseVoice → sensevoice_local → whisper_local）與 TTS 主備鏈（gemini → edge → piper）邏輯乾淨、實機驗證穩。唯一痛點是 VAD：目前主路徑用 in-process energy VAD，固定尾巴約 1.3s，2–10s 的「飄」來自 energy 閾值在不同噪音環境判定不穩。

**根因**：老師說的「改神經網路 VAD」——`vad_node.py` 其實已經是 Silero 神經網路 VAD（`min_silence_ms 400`，已寫好但未在主 demo 啟用）。問題不是「從零做」，而是雙 VAD 路徑並存會 race，需讓 `stt_intent_node` 改吃 `vad_node` 事件、關掉內部 energy VAD。

**6/18 目標**：處理 VAD 延遲，不碰 ASR/TTS/LLM 主鏈。
- **A 方案**：Silero VAD 單一路徑，關掉內部 energy VAD，消除雙 VAD race，順帶砍掉約 0.4s 尾巴。上主線前必須跑完整 e2e。
- **B 方案**：若 Silero 切換風險過高，只調 energy VAD 參數作為保底（`silence_duration_ms 800→600`、`speech_end_grace_ms 500→300`，純調參、零程式改動）。

**驗收標準**：語音互動延遲較 5/18 明顯下降且穩定（不再出現 8–10s 飄移）；ASR/TTS fallback chain 維持可用；切換後跑完整 e2e 回歸無 regression。

**優先序與風險**：維持級，但 VAD 切換屬「中改、需 e2e 重測」，建議排在本窗口早期做完並鎖死。風險：VAD 切換會改變 speech segment 邊界，可能影響 ASR 完整度與 echo gate；若 e2e 不穩，必須退回 energy VAD 調參（B 方案）。不碰：echo gate 1.5s magic number（5/4 實機調出的安全值）、Megaphone 16kHz 硬體限制、LLM（5/12 已 freeze `openai/gpt-5.4-mini`，fallback `google/gemini-3-flash-preview`）。

---

## 7. 全域驗收（6/18 demo 與驗收骨架）

### 6/18 demo 形態
demo 必須是一條任務閉環一氣呵成，不是逐功能輪播：

```
聽懂你 → 認得你 → 看懂環境 → 安全移動 → 互動回報 → 做出反應
```

範例腳本：使用者出聲 → PawAI 認出名字打招呼 → 對話中提到環境物件/使用者姿勢 → 「PAI 過來一下」走一小段、遇障停並回報 → 比 OK 進手勢模式做一個趣味互動 → 收尾。

### 驗收骨架：`pawai demo preflight`
沿用 Spec A 設計的兩階段 preflight 作為全域驗收骨架：
- **階段一（dev local）**：`pawai demo preflight --target local` — no FAIL；local applicable checks PASS，Jetson-only checks 可 SKIP。
- **階段二（Jetson post-start）**：`pawai demo start` 雙階段 hook preflight 全 PASS。
- **語意 dry-run**：`pawai demo preflight --semantic` 6 條 script 通過，回覆自然度 ≥ 4/5。

### 各章驗收彙總
| 章 | 驗收 gate（摘要） |
|---|---|
| 1 定位 | 三份文件 statement 一致；demo 開場 30 秒能說清類別/價值/非目標/四支柱 |
| 2 物件 P0-C | 必達展示集穩定辨識、不閃爍；TRT EP 無 fallback CPU |
| 3 手勢 P0-B | idle 30s 不誤觸；揮手 8/10 觸發；OK 進退手勢模式 |
| 4 導航 P0-A | 必達：語音叫得動 + 走 0.3–0.5m + 遇障停 + 不暴衝；加分：一次繞行 |
| 5 姿勢 P2 | 4 穩定 enum 不誤觸；fallen 維持可靠 |
| 6 人臉+語音 | CLI 現場註冊；VAD 延遲明顯下降且穩定 |

### 全域風險
demo flow 預期連跑 30 分鐘以上，可能撞 stale state（見第 4 章 F7）。若 F7 尚未根治，nav 段前 fresh restart stack；若已根治，需由 watchdog/preflight 證明 `/cmd_vel_nav` 與 lifecycle 狀態正常。

---

## 7.5 Runtime budget & Mode 治理（跨章節）

> 補入：2026-05-20。物件章節升級研究時暴露：三個 P0（nav / object / gesture）+ 維持項（人臉 / 語音 / brain / studio）若同時滿速跑，必壓爆 Jetson Orin Nano 8GB。這條治理章是所有 P0 與維持章的共同約束，不歸任何單一章。

### 7.5.1 核心原則

6/18 demo **不應讓所有高負載模組同時滿速跑**。PawAI 是有狀態的居家四足機器人，不是「所有功能一直全開」的功能清單機器。

```
該看物件時看物件 → 該移動時把 safety/nav 放第一
該聊天時把 speech/brain 放第一 → 該手勢互動時才提升 gesture
```

### 7.5.2 功能效能分級

| 模組 | 常駐策略 | 理由 |
|---|---|---|
| Go2 driver / reactive_stop / twist_mux | **必須常駐** | safety 不能關 |
| RPLIDAR / Nav2 / AMCL | nav demo 時常駐 | 移動主線 |
| D435 depth safety | nav 時常駐 | 移動前 gate、`/capability/depth_clear` |
| Speech VAD / ASR trigger | 常駐但低負載 | 互動入口 |
| Face identity | 可常駐低頻 | 認人是主線，但不需滿 FPS |
| Gesture | **不可全時高敏** | OK 模式開關（北極星 §3）、cooldown |
| Pose | 降頻 context | P2，不該搶 P0 資源 |
| Object detection | **降頻 / 按需** | grounding 非 safety brake；1–2 FPS 對 Brain context 已足 |
| Studio video / heavy debug | demo 時限流 | 吃 bandwidth / CPU |

### 7.5.3 Demo Mode 表（Executive / Studio 切換）

| Mode | 觸發 | Object | Gesture | Pose | Nav | 用途 |
|---|---|---|---|---|---|---|
| **Chat** | 對話為主、無視覺問題 | low-rate / off | gate DISABLED | low-rate context | off | 7 章敘事第 1–2 段「聽懂你 / 認得你」 |
| **Scene** | 使用者問「你看到什麼」 | **boost on**（5–10s 後降回） | gated | low-rate | off | 7 章敘事「看懂環境」 |
| **Nav** | 「PAI 過來一下」 | low-rate（1–2 FPS）或 off | safety gestures only | off | **on** | 7 章敘事「安全移動」 |
| **Gesture** | OK 進入手勢模式 | low-rate | **boost on** | off | off | 7 章敘事「做出反應」 |
| **Demo full** | 全閉環 | 分段啟用 | 分段啟用 | 分段啟用 | 分段啟用 | 由 Executive 在閉環中切 Mode，**不是全開** |

切換規則範例：
- 使用者問「你看到什麼」 → Object boost 5–10s 後降頻
- 使用者說「過來」 → Object 降頻、Nav / safety 優先
- OK 進手勢模式 → Gesture boost、Object 降頻
- TTS 播放中 → 非 safety perception 不觸發技能（既有 conversation gate）

### 7.5.4 三情境量測（所有 P0 升級必須通過）

任何 P0 章節（nav / object / gesture）的能力升級評估，除了「能力是否變強」，**必須** 額外通過三組情境量測：

| 情境 | 啟動範圍 | 該章節 KPI | 共同 KPI |
|---|---|---|---|
| **單跑** | 該模組 + 必要 driver | 章節內定義（如 obj FPS ≥ 8） | RAM ≥ 0.8GB、temp < 75°C |
| **Full perception** | 該模組 + face + vision + brain + speech（無 nav） | 章節內定義（如 obj FPS ≥ 5） | RAM ≥ 0.8GB、temp < 75°C、TTS / ASR 延遲不可較單跑增加 > 30% |
| **Nav mode** | nav stack + 該模組降頻 | 章節內定義（如 obj 1–2 FPS） | **`/cmd_vel_nav` 不可掉**、無 gap > 200ms — hard gate |

通過情境分級對應到部署策略：
- 只過單跑 → 升級候選，不部署
- 過單跑 + Full perception → 可作為某 Mode 預設
- 全過 → 可作為 6/18 demo 預設
- 部分過 → 列為 boost-only（特定 Mode 觸發）

### 7.5.5 系統指標 hard floor（全情境）

- RAM available ≥ 0.8 GB
- 溫度 < 75°C OK，75–80°C warn，> 80°C no-go
- Camera frame drop：`/camera/camera/color/image_raw` 平均 ≥ 15 FPS
- 同跑 brain 時：TTS / ASR 延遲 vs 單跑 ≤ +30%
- 同跑 nav 時：`/cmd_vel_nav` 無 gap > 200ms

任何升級若違反任一 hard floor，**不可** 列為 6/18 demo 預設。

### 7.5.6 對其他章節的拘束

- **第 2 章 物件**：模型 / 參數升級評估必須涵蓋 §7.5.4 三情境，不只看 single-run FPS。明文點：26s 若僅單跑通過、Nav mode 把 nav 拉掉 → 列 boost-only，**不作常駐預設**。詳見 object benchmark protocol §5。
- **第 3 章 手勢**：OK 模式開關天然降低常駐負載；ENABLED 模式須驗證在 Full perception 下不打架。
- **第 4 章 導航**：Nav mode 啟動時要明確告訴 Executive「object 降頻、pose off」；不允許 nav demo 同時跑滿 perception。
- **第 5 章 姿勢**：本身已降級 P2，符合本治理章「降頻 context」位置。
- **第 6 章 人臉 + 語音**：維持級，face 低頻、speech 常駐低負載，符合既有定位。
- **第 7 章 全域驗收**：`pawai demo preflight` 應在 demo 啟動時印出當前 Mode 與預期 KPI，不允許在 Full perception + Nav mode 同時 boost。

### 7.5.7 與 §8 非目標的關係

本治理章把「不可全速全開」明文化。對應到 §8 增補：
- **本窗口不做**：全模組無 Mode 切換的「永遠全開」demo 形態。
- **本窗口至少要做（discipline-level）**：以 launch 腳本 / 配置檔 / 手動 Mode 切換的 discipline 驗證三情境量測通過。Executive 自動 Mode 廣播（cross-node mode topic + 自動切換邏輯）是**加分項，不是 P0 deliverable** — 是否列入由 implementation plan 評估投資報酬後決定，超出本窗口 scope 也 OK。

換句話說：runtime budget 是 P0 共同約束（量測必須通過），但「如何讓系統自動切 Mode」是 implementation 層級決定，本北極星不對此承諾交付物。

---

## 8. 非目標與延期項

北極星不只說做什麼，也明確擋掉「看起來酷但會炸掉四週」的東西。

**本窗口不做**：
- 不做完整自主尋物閉環（物件偵測只到環境 grounding）。
- 不做複雜人流動態繞行必達（繞行只列加分）。
- 不做大規模自建資料集訓練（HomeObjects-3K + 自拍資料 fine-tune 列下一階段候選）。
- 不做姿勢 7 類全分類主動觸發（降級為情境感知）。
- 不重寫 Brain / 不引入 OpenClaw 架構（PawAI 已有 skill_contract + Executive，缺的是 demo 敘事收束）。
- 不把 PawAI 定位成寵物狗或語音助理。

**本窗口不碰（凍結項）**：
- 人臉 track 抖動根治、多人 3+ 同框 bbox 互竄（demo 後重構）。
- 語音 echo gate 1.5s magic number、Megaphone 16kHz 硬體限制。
- LLM（5/12 已 freeze `openai/gpt-5.4-mini`）。

> 註：現場閾值調參（gesture cooldown / pose vote / fallen threshold）不混入 Week 0 Spec A 收尾；依第 3/5 章作為獨立工作處理。

**外部設計參考（不作底層替代，不作工程依賴）**：
- DimOS（dimensionalOS/dimos）不作為 PawAI 底層替代方案；PawAI 主線仍維持 ROS2/Nav2 + PawAI Brain/Executive。PawAI 只參考其 agent-native skill interface、spatial memory / object permanence 敘事、Go2 skill catalog 與 demo packaging。
- 接近尋物（未來方向）：可參考 DimOS 的 spatial memory RAG 與 MCP server 設計；本窗口不做。
- Go2 sport mode api_id 對照表：可拿 DimOS 的 Unitree Go2 skill catalog 與 `go2_robot_sdk` 現有動作對一次，查表用（如 `RecoveryStand` 對「跌倒後扶起」），非整合。

---

## 附錄：優先序總覽

| 編號 | 模組 | 型態 | 6/18 目標 |
|---|---|---|---|
| Week 0 | Spec A 收尾 | 前置條款 | 4 PR merge + Day 0 recovery + preflight 兩階段 PASS |
| 1 | 定位收斂 | P0｜基礎 | 三份文件統一為老師收斂版定位 |
| 4 | 導航避障 | P0-A｜核心閉環，吃滿四週 | 必達：語音叫得動 + 遇障停；加分：繞行 |
| 3 | 手勢辨識 | P0-B｜互動可靠性 | 短期止血 + OK 模式開關 |
| 2 | 物件偵測 | P0-C｜環境 grounding | 模型/參數/後處理升級 |
| 5 | 姿勢辨識 | P2｜降級 | 降級為情境感知，砍 3 保 4 |
| 6 | 人臉 ＋ 語音 | 維持｜小改高回報 | 人臉註冊 CLI + 語音 VAD 收斂 |
