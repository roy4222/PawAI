# PawAI 5/22~6/18 北極星 v2（amended）— 機構場域巡檢與互動助理 POC

> **文件類型**：北極星 v2（定位 + 三層擴充模型 + 取捨規則 + spike gate）
> **狀態**：**Draft for 5/22 discussion**（撰寫日 2026-05-21；2026-05-22 amended after 教授 5/21 機構巡檢 pivot）
> **窗口**：2026-05-22 ~ 2026-06-18
> **檔名日期**：2026-05-22（對應 sprint 啟動日，非撰寫日）
> **Supersedes**：[`2026-05-19-pawai-may-june-north-star-design.md`](2026-05-19-pawai-may-june-north-star-design.md)

---

## 0. 背景與 supersede 理由

### v1 為何失效

v1（5/19）拍板隔天，**5/20 雅文驗收會議**老師最關鍵的回饋仍是：「PAI 的定位問題——狗 / 機器人 / 助理需要重新思考」。同一場會也暴露：物件偵測效果差、手勢誤觸嚴重、姿勢辨識不穩、導航只能停障。

v1 把問題框成「居家四足機器人 + 互動 70% / 守護 30%」，但這個敘事仍無法回答老師最核心的質疑：**「為什麼一定要這隻狗？把狗抽掉，這些功能好像也可以做，而且可以做得更好。」**

### v2 三個結構性修正（v2 原版設計 — 5/22 撰寫）

1. **定位敘事**：從「居家陪伴機器狗」改成「**室內場域具身 AI 任務 POC**」。不是放飛夢想，是把場域抽象成「已知小型室內」涵蓋家裡、學校走廊、展場、商場、長照空間——但 6/18 驗收邊界仍壓在小型已知場域。**（此為 v2 原版定位；amendment 後已收斂為機構照護場域主軸，見下方 amendment 段及 §1。）**

2. **心智模型**：從 P0/P1/P2 線性切法改成 **L1/L2/L3 三層擴充模型**。L1 包裝層（已有底沒包好）、L2 擴充槓桿（改 schema / 接線就解鎖新故事）、L3 賣夢層（寫進未來潛力）。避免「我們是不是又在砍功能」的焦慮——不是砍，是分層。

3. **commit 策略**：從「現在直接 commit 全部 P0」改成 **Spike-then-commit**。W1 並行驗 3 個硬 gate，分項決定 L2 升級深度。

### 2026-05-22 amendment（教授 5/21 機構巡檢 pivot）

v2 commit 後不到 24 小時，5/21 教授兩個半小時會議再度收斂定位：**居家完全 reject**，主軸定為「長照 / 日照中心等機構場域的室內巡檢與互動助理 POC」。整體工程能力一行不砍，只重新包裝場景、簡化 L2 為單一路線（取消 α/β 二分）、強化 §4 場景語言對照與 §8 VLM 升為巡檢核心。完整 amendment diff 見 **附錄 A.2**。本文件後續章節已反映 amendment 後狀態。

### 累積的決策依據

v2 整合 2026-05-21 brainstorming session 累積的 7 份 subagent 深度報告：
- Hiwonder ROSOrin Pro 競品分析（OpenClaw 不換、3 個小設計可借鑑）
- PINTO_model_zoo 兩輪掃描（Top 5 + 對應 PawAI 已決方向）
- 物件辨識升級實戰（YOLOv8s + ByteTrack + CLAHE）
- 手勢誤觸根因（dwell time + HandOwnerFilter + idle window）
- 姿勢/跌倒 SOTA（state machine + depth fusion）
- VLM scene_describe 可行性（cloud only，Gemini 2.5 Flash 主線）
- Engagement Gate + 影片腳本架構

並由 2026-05-22 兩份深挖補強：
- 2D LiDAR + D435 融合導航避障（STVL feasibility）
- Object event schema 升級 + depth/bearing（F6 最低成本實作）

---

## 1. 新定位：機構場域巡檢與互動助理 POC

### 主 statement

> **PawAI 是一套以 Unitree Go2 為載體、面向長照 / 日照中心等機構場域的室內巡檢與互動助理 POC。PawAI 是照護人員派出去的機構巡檢助理，但它到現場後不是冷冰冰的攝影機，而是會用狗式互動做第一層陪伴與確認。**

它的工作不是取代照護人員，而是在可建圖、可重複巡視的小型機構室內空間中，協助完成「接收巡檢任務 → 移動到固定巡檢點 → 感知現場 → 與人互動 → 回報結果」的原型驗證。

### 「為什麼是狗」三鐵律

每個展示片段必須通過三題：
- ✅ 需要**移動**嗎？（手機/平板/監視器做不到）
- ✅ 需要**實體存在**嗎？（雲端 AI 做不到）
- ✅ 需要**多模態同時**嗎？（單一感測器做不到）

三個都中 → 進 demo。只中一個 → 退到背景互動或砍。

### 拒絕的標籤

- ❌ **寵物玩具**：20 公斤機體當寵物有安全疑慮，且太浪費硬體
- ❌ **居家陪伴狗**：一般家庭不是合理採購方，手機 / 智慧音箱 / App 競品太強，且機體過大
- ❌ **語音助理**：Apple / 小米早做且更穩，差異化不足
- ❌ **自由巡邏機器人**：6/18 內做不到大型場域動態繞行

### 場景分層

| 層 | 場景 | 用途 |
|---|---|---|
| **主軸** | 長照 / 日照中心 / 養護機構 | 產品故事與影片主場景 |
| **技術手段** | 小型已知室內巡檢 | 6/18 demo 的可驗證能力邊界 |
| **拍攝替代場** | 家裡 / 學校走廊 / 實驗室 | 代替真實機構場域拍攝，不作產品定位 |
| **未來延伸** | 校園、商場、居家延伸、導盲、救災、戶外工業巡檢 | L3 roadmap，不列 6/18 必達 |

### POC 框架的對外敘事

> PawAI 不是在宣稱已能商用部署，而是在機構照護場域做 Physical AI 原型驗證：固定攝影機只能看，App 只能提醒，PawAI 可以走到現場，用多模態感知先幫照護人員確認狀況。

---

## 2. 三層擴充模型

### L1 包裝層 — 已有能力沒包好（必做，6 工作天）

不用大改架構，靠 skill metadata、demo policy、文件分層、Studio trace 就能把現有能力包成產品力。

| # | 項目 | 工程量 | 來源 |
|---|---|---:|---|
| L1-1 | skill metadata（SKILL.md）+ per-agent tool scope（巡護 / 居家 / debug 三 mode） | 1.5d | OpenClaw 借鑑 |
| L1-2 | demo_policy / CAPABILITIES.md 對齊新定位 | 0.5d | OpenClaw 借鑑 |
| L1-3 | persona 4 檔分離（IDENTITY / SOUL / USER / STYLE） | 0.5d | OpenClaw 借鑑 |
| L1-4 | Studio trace 強化（AI 決策透明化展示） | 1d | 既有 |
| L1-5 | Mapping QA Checklist + `build_map.sh` 提示三段 SOP | 1d | Mapping 分析 |
| L1-6 | 物件 HSV 3 個後處理（Gaussian blur + morphology + central crop） | 0.5d | OpenCV 分析 |
| L1-7 | AprilTag 場域 anchor（家裡 demo 場域貼 4 張 tag36h11） | 1d | OpenCV 分析 |
| **L1 小計** | | **6 天** | |

### L2 擴充槓桿 — 單一路線，多個深度檔位

**時程現實**：4 週可用 ~20 工作天，扣除 Week 0 收尾（3-5d）+ W1 spike（5d）+ L1 包裝（6d，可平行）= 約 10-12 個淨工作天給 L2。教授 5/21 會議後，L2 不再分成「導航 vs 感知」兩條互斥路線，而是服務同一條機構巡檢閉環。W1 spike 只決定每個能力做到完整版、thin 版，或 fallback 版。

**L2-must（不管 spike 結果，W1 後立即排程）**：

| # | 項目 | 工程量 | demo 體驗價值 |
|---|---|---:|---|
| L2-C | **NAV executor 補齊**（`/nav/goto_relative` + named goal 真接通） | 2d | brain 真能叫 Go2 走 |
| L2-D | **Named waypoint registry**（家裡 4-5 點 + Studio UI） | 2d | 「PawAI 去客廳」可用 |
| L2-E | **手勢 3 補充**（dwell + HandOwnerFilter + idle） | 2.5d | 誤觸狂炸 demo 殺手必修 |
| L2-F | **姿勢 fallen state machine**（5 態 + edge-triggered） | 2d | fallen 是 safety 主線 |
| **must 小計** | | **8.5 天** | 跨 W2-W4 平行排 |

**L2-single（單一路線，必做；W1 spike 決定每能力深度檔位）**：

教授 5/21 pivot 後，機構巡檢場景不再需要「Nav 繞障 vs Perception」的二元取捨——巡檢閉環裡 NAV、Object、VLM、Engagement 都是必要的。spike 結果只決定每個能力做完整版、thin 版、或 fallback 版。

| # | 項目 | 工程量 | spike 對應 |
|---|---|---:|---|
| L2-A1 | **Nav fusion 到 depth safety**（D435 `depth_to_scan` → reactive_stop） | 7d | spike #1 PASS 才做；FAIL 退 LiDAR-only |
| L2-B1 | **Object schema v2**（depth + bearing + `find_nearest`，class set 對應機構物件，見 §6）| 5~9d | spike #2 決定深度檔位（見下） |
| L2-G | **Engagement Gate**（OpenWakeWord「嗨 PawAI」+ 統一 wake/gesture/face 抽象） | 3d | 不依賴 spike |
| L2-H | **VLM scene_describe**（巡檢回報核心，到點觀察） | 3d | 不依賴 spike |
| **single 小計** | | **18~22d**（依 spike #2 / #1 結果浮動） | |

**Object schema v2 三檔深度**（spike #2 決定）：

| spike #2 結果 | 做哪檔 | 範圍 | 工程量 |
|---|---|---|---:|
| #2 PASS | **完整版 schema v2**：depth + bearing + `find_nearest` + IoU tracking + `position_3d` | 整套巡檢「看到誰在哪、有什麼物品、距離多遠」 | 9d |
| #2 PASS 但時程吃緊 | **thin 版 schema v2**：只 depth + bearing + backward compat；無 tracking / `position_3d` | 「最近紅色物品」可運作，無多物件持續追蹤 | 5d |
| #2 FAIL | **side-channel depth cache**：event schema 完全不動；object node 內部維護 `bbox_id → depth_m` dict；brain 透過 service `/object_perception/query_depth` 按需查 | 無 schema 改動，最小可用 | 1d |

spike 結果出來後寫 `2026-05-28-w1-spike-results.md` 並 commit 選定深度檔位。

**L2-stretch（時程有餘才加，不承諾）**：

| # | 項目 | 觸發條件 |
|---|---|---|
| L2-A2 | **Nav fusion 升 STVL**（D435 進 Nav2 local costmap，可繞靜態障礙） | spike #3 PASS + W4 有 5 天 buffer。機構走廊單純，**不是必要**，僅作 demo 加分鏡頭 |
| L2-I | **Plan hardcoded templates ×2** | W4 有 2 天 buffer |
| L2-J | **YOLOv8s + ByteTrack + 條件 CLAHE** | W4 有 2.5 天 buffer |

**L2 可延後（明確不進 6/18，列下一階段 backlog）**：

- HomeObjects-3K + 自拍 fine-tune（7 天，下一階段做 YOLOv8s 升級時一起）
- Plan dynamic JSON（hardcoded 2 個 templates 已能撐 demo）
- Depth fusion + velocity trigger for pose（state machine 已能撐）

### L3 工程候選清單 — 考慮過但不做（不進 6/18）

這是「**工程上 considered 但暫不做**」的技術項清單。**對外敘事用的產品願景 roadmap 見 §12 L3 產品願景表**。

| # | 工程項目 | 限制 |
|---|---|---|
| L3-1 | 大型場域動態人流避讓 | social nav planner，4 週不可達 |
| L3-2 | 完整自主尋物閉環（跨房間任務鏈） | 需 long-horizon plan + memory |
| L3-3 | RTAB-Map / RGB-D VSLAM 主導航 | ARM64 + 四足晃動風險高 |
| L3-4 | VLM 即時決策導航 | latency + cost |
| L3-5 | OpenClaw 整套移植 | rosclaw 不成熟，安全層比現有弱 |
| L3-6 | 任意照片找走失人員（ad-hoc face query） | 隱私 + 架構翻面 |
| L3-7 | YOLOv9-Wholebody28 2-for-1 整合（物件 + body keypoint） | 需 spike 評估 RAM |
| L3-8 | VSDLM 嘴在動 + 看著 multimodal Engagement | 6 月後 P1 加分 |
| L3-9 | 6D pose / Objectron / 3D 物件框 | 不必要 |
| L3-10 | Multi-person 3+ 同框穩定追蹤 | demo 後重構 |
| L3-11 | Local VLM on Jetson | Orin Nano 8GB 共存不可能，Reject |

---

## 3. 任務閉環

替代「功能拼盤」的 demo 形態。每個感知模組存在的意義都對齊到這條閉環：

```
聽懂你 (語音/文字)
   ↓
認得你 (人臉 + 身份)
   ↓
看懂環境 (物件 + 姿勢 + 手勢 + 導航狀態)
   ↓
理解任務 (Brain LLM + Plan)
   ↓
安全仲裁 (Safety/Policy/Expression 三層)
   ↓
安全移動 (Nav executor + reactive_stop)
   ↓
到點感知 (VLM scene describe + 物件 depth/bearing)
   ↓
回報結果 (TTS + Studio trace)
```

**整合度高的判準**：這條閉環一氣呵成，不是逐功能輪播。

---

## 4. Brain / Skill / Executive 產品化包裝

### Safety / Policy / Expression 三層架構（PawAI Brain 學術貢獻）

PawAI Brain 不是「把 LLM 接到機器狗」，是設計了一套**讓 LLM 安全控制實體的決策架構**。學生作品很少做到這個深度，這是 5/19 老師會議沒講出來的賣點。

| 層 | 角色 | PawAI 元件 |
|---|---|---|
| **Safety** | 硬性安全閘門：高風險動作（後空翻、移動中急停、跨房間 nav）必須過 capability gate + ack confirm | `SafetyLayer` + `nav_capability` + `reactive_stop_node` |
| **Policy** | 決策層：LLM 輸出 intent → Executive 驗證 → Skill Dispatcher 路由 | `interaction_executive` + `pawai_brain` |
| **Expression** | 表達層：persona + Skill 動作 + TTS + Studio trace 呈現 | `pawai_brain/personas/v1/` + `tts_node` + Studio |

**LLM 不直接 publish cmd_vel、不直接決定速度、不直接控 Nav2**。LLM 只產生 intent / plan，實際執行由 deterministic layer 做。

### 任務級包裝（OpenClaw 借鑑的 3 個小設計）

OpenClaw 不引入。只借鑑 3 個有設計思想的小東西：

1. **System prompt 拆 4 個 md 檔**（IDENTITY / SOUL / USER / STYLE）— 比現在塞在 Python config dict 裡好維護、非工程師也能調
2. **Skill 目錄加 `SKILL.md` metadata** — 讓 LLM 自己決定 call 哪個 skill，比硬 routing 彈性高
3. **Per-agent tool allow/deny list**（巡護 / 居家 / debug 三 mode）— 巡護 mode 自動關掉「講笑話 / 伸懶腰」這種寵物 skill

### 不引入

- ❌ OpenClaw 整套（rosclaw 不成熟、安全層弱、ROS2 bridge 不穩定）
- ❌ LLM-as-direct-actuator（ROSOrin 那種 `LLM → eval → cmd_vel`）
- ❌ Voyager 風格 code-as-action（程式碼安全風險）

### 場景語言對照表（內部術語 → 對外敘事）

教授 5/21 會議後，所有對外（簡報、影片、訪客 demo）的講法必須換成場景語言，避免再用工程術語讓觀眾看不懂。內部開發仍用工程術語：

| 工程語言（內部） | 場景語言（對外敘事） |
|---|---|
| Named waypoint | **固定巡檢點** |
| Object schema v2 | **回報物品位置與距離** |
| VLM scene describe | **到現場後描述環境狀態** |
| Engagement Gate | **被叫喚後才回應，避免打擾** |
| Fallen state machine | **疑似異常姿態確認** |
| D435 + LiDAR fusion | **近距離障礙補強與現場感知** |
| Studio trace | **系統決策透明化** ⚠️ 不是 debug 畫面 |

**PaStudio 三鏡頭**是內部 debug 工具，**demo / 影片中不出現**（暴露完成度不夠）。

### `patrol_status`：多源融合的巡檢狀態（不是 detector class）

巡檢回報需要的「通道是否暢通 / 有沒有人 / 有沒有疑似異常」**不是單一 detector class**，而是由 brain / executive 組合多個來源產出的高階狀態：

| `patrol_status` 值 | 來源組合 |
|---|---|
| `passage_clear` / `passage_blocked` | D435 depth slice + LiDAR scan + 規則 |
| `person_present` | object/person detector + face_identity |
| `suspected_unusual_pose` | pose classifier + state machine + 持續時間 |
| `object_near_path` | object schema + nav waypoint + 距離規則 |
| `unknown_obstacle` | LiDAR / D435 但無 class match |

**邊界清楚**：`object_schema` 負責「看到什麼、在哪裡、多遠」；`patrol_status` 負責「現場是否正常」。前者是 detector 輸出，後者是 brain 推論。

---

## 5. 導航與避障：LiDAR 主線 + D435 depth safety

### D435 定位 statement（必須誠實寫，避免吹過頭）

> D435 不是單純攝影機，而是 PawAI 的 RGB-D 空間感知模組。**短期**用於 depth safety、物件距離與方向估計、到點觀察；**中期**用於 RGB-D 物件定位與 VLM 場景描述；**長期**才探索 RGB-D SLAM、3D mapping 與 depth-assisted face / pose perception。**現階段 D435 不取代 RPLIDAR + Nav2 主導航，而是補強近距離 3D 感知與安全判斷。**

### 主導航路線（不動）

- **RPLIDAR + Cartographer + AMCL + Nav2**：5/11 burndown 換來的穩定 stack
- **reactive_stop_node 4-mode + twist_mux priority 200**：保留現有 4 mode + 11 條 unit test
- **不換 collision_monitor**：4 週工程量不划算，列 6 月後 P2

### D435 三層擴充（依 spike 結果分層）

| 層 | 做法 | 角色 | spike gate |
|---|---|---|---|
| **必做** | LiDAR 仍是 Nav2 主導航 | 地圖、定位、基本避障 | n/a |
| **必做** | `depth_to_scan_node` 把 D435 投影成 `/scan_depth`（地面以上 10-40cm slice） | 補低矮 / 近距障礙，餵 reactive_stop | spike #1 |
| **Spike** | STVL (`spatio_temporal_voxel_layer`) 進 Nav2 local costmap | 讓 D435 進 Nav2 costmap，嘗試真正局部避障 | spike #3 |
| **未來** | RTAB-Map / RGB-D VSLAM | 賣夢，不進 6/18 主線 | L3 |

### D435 mount 角度策略

**不直接定案 12° 下傾**。先測兩個角度：

- **正視 / 微下傾（0-5°）**：保人臉與互動視野
- **下傾 10-15°**：保地面 / 低矮障礙

**單顆 D435 不能同時完美承擔「看人臉」+「看地面」**——這是物理限制。spec 必須誠實寫出來。W1 spike 同步驗證：12° 下傾下 face_perception 還能用嗎？

### 紅旗

| 風險 | 嚴重 | 對策 |
|---|:---:|---|
| STVL 在 Orin Nano + Go2 OOM | **P0 blocker** | W1 spike 先驗，FAIL 則退回 depth_safety only |
| 12° 下傾讓 face_perception 看不到站立成人臉 | **P0 blocker** | W1 spike，FAIL 則拆兩顆 camera 或 face 改用 Go2 內建 camera |
| USB 3.0 bandwidth 跟 face camera 搶 bus（5/11 撞牆等級） | 高 | face camera 從 30 → 15 Hz |
| AMCL plateau bug（5/3 已知）導致第二個 goal stuck | 高 | spike #3 前先修，否則 5m 繞兩障礙不可能 |
| Go2 sport mode MIN_X=0.5m 門檻 | 已修 | RobotControlService 已 handle |

### Demo readiness 老實話

| 場景 | 可達 % | 是否賣 |
|---|---:|:---:|
| 靜態包包 / 椅子繞行（1.5m goal） | **70%** | ✅ 可賣 |
| 5m 繞 2 障礙（含 AMCL plateau fix） | 50% | ⚠️ 加分 |
| 走動家人避讓 | **35%** | ❌ 不要賣 |
| 整體「會走過去看」demo | **50-55%** | ⚠️ 框成「會閃靜態障礙」|

---

## 6. RGB-D 物件感知：object schema v2

### 為什麼這個比換大 YOLO 重要

現在 brain 只拿到 `class / color / time`，無法做空間任務。schema 升級後解鎖一整片新故事：

- 「**巡檢看到誰在哪、有什麼物品、通道是否暢通**」（機構巡檢核心）
- 「幫我看王爺爺的助行器在哪 / 水杯在哪 / 輪椅旁的物品」
- 「前方 1.5m 有障礙物」
- 「到巡檢點後拍照回報」
- 「找到物品後回報方向與距離」

### 機構場景的物件類別（A 層 = detector class set）

class 集合按機構巡檢需求收斂；通用 COCO 80 類**保留訂閱**但 demo 不靠它們：

| 類別 | 來源 | 備註 |
|---|---|---|
| `person` / `resident` | object detector + face_identity | **身份由 face_identity 認，不由 object schema 負責**「張奶奶」這種 specific identity |
| `wheelchair` | object detector | 機構必備辨識物 |
| `cane` / `walker` | object detector | 可合成「助行輔具」單一類別，短期模型不一定能細分 |
| `medicine_box` | object detector | candidate / future fine-tune（demo 用紙盒貼標籤代替） |
| `cup` / `bottle` | object detector (COCO 既有) | 民生物品 |
| `bag` / `personal_item` | object detector (COCO 既有 backpack/handbag) | 長輩遺失物 |
| `chair` | object detector (COCO 既有) | 環境基準 |

**B 層巡檢狀態（`patrol_status`）見 §4**：通道是否暢通、人是否在場、是否疑似異常——由 brain / executive 組合多源產生，**不是 detector class**。

### Schema v2（backward compatible）

```json
{
  "stamp": 1716350123.45,
  "event_type": "object_detected",
  "frame_id": "base_link",
  "objects": [{
    "class_name": "backpack",
    "confidence": 0.82,
    "bbox": [x1, y1, x2, y2],
    "color": "red",
    "color_confidence": 0.71,
    "center_px": [320, 240],
    "depth_m": 1.52,
    "bearing_rad": 0.34,
    "bearing_text": "左前方",
    "position_3d": {"x": 1.43, "y": 0.51, "z": 0.20},
    "position_quality": "good",
    "track_id": 7
  }]
}
```

`position_quality ∈ {good, poor, unavailable}`。舊欄位全留，brain `apply_object_detected_json` 不炸。

### Depth 取樣策略

不要單點 `depth[cy, cx]`（極易踩 hole）。5×5 中位數 + std check：

```python
def sample_depth(depth_mm, cx, cy, win=5):
    patch = depth_mm[cy-2:cy+3, cx-2:cx+3]
    valid = patch[(patch > 200) & (patch < 6000)]  # D435 spec range
    if valid.size < 5:
        return None, "unavailable"
    med, std = np.median(valid) / 1000.0, np.std(valid)
    quality = "good" if std < 50 else "poor"
    return med, quality
```

**fallback**：5×5 失敗 → 試 bbox 上 1/3（人 / 椅子身軀比腳穩）→ 仍失敗 `unavailable`。

### Bearing 計算 + 中文化

```python
# pixel → camera_color_optical_frame → TF base_link → bearing
def bearing_text(rad):
    deg = math.degrees(rad)
    if abs(deg) < 15:  return "正前方"
    if abs(deg) < 45:  return "左前方" if deg > 0 else "右前方"
    if abs(deg) < 135: return "左側" if deg > 0 else "右側"
    return "後方"
```

### `find_nearest` 純 Python 函式

LLM **不算座標只組句子**。Python 先 filter + 排序，LLM 模板化回答：

```
照護人員: 幫我看王爺爺的助行器在哪
Tool: find_nearest(class='walker')
→ {bearing_text: '左前方', depth_m: 1.5, age_s: 3}
Assistant: 助行器在你左前方 1.5 公尺，3 秒前看到的。
```

（同樣 query 模板適用於拍攝替代場的家用物件範例「找紅色背包」，schema 一致；**紅色背包僅作替代拍攝道具**，非主場景敘事用語）

### 紅旗（D435 物理極限，誠實寫）

| 物件類型 | depth 可用率 |
|---|---:|
| bottle / cup / chair / backpack | **85-90%** ✅ |
| 黑色筆電 / 鏡面 | ~50% ⚠️ |
| TV / 玻璃 / window | **幾乎全 unavailable** ❌ |

**整體 15-25% bbox 會 poor/unavailable**——接受並 graceful degrade「我看到助行器但距離測不到」。**不試圖用 ML 補洞**（4 週做不完）。

---

## 7. Engagement Gate：叫名字才回頭

### 戰略價值

直接打到老師「為什麼是狗」最痛的問題——**狗本來就是叫名字才回頭**。always-on 監聽不像狗，像 Echo Dot。

機構巡檢場景下，trigger 來源有兩類使用者：
- **照護人員主動派遣**：「PawAI，去活動區巡一下」
- **長者主動發起互動**：揮手 / 喊名字 / 看向 PawAI

兩類都走同一條 Engagement Gate 抽象。**陌生人路過不打招呼、不亂回應**——這是「不打擾」的設計，符合機構環境禮儀。

### Wake word + 統一抽象

OpenWakeWord「嗨 PawAI」自訂模型（Piper 合成 100 樣本訓練）。**真正的 spec 不是 wake word，是 Engagement Gate 抽象層**——把 wake word / OK 手勢 / 揮手 / 喊名字 / 看著 PawAI 統一成一個 `/event/engagement_triggered` topic：

```json
{
  "source": "wake_word" | "gesture_ok" | "gesture_wave" | "face_approach",
  "confidence": 0.92,
  "ts": ...,
  "ttl_sec": 8.0
}
```

訂閱者：
- `interaction_executive` → 切 ATTENTIVE state，開 ASR + 開高頻 face/gesture
- `stt_intent_node` → 只在 engagement 期間發 LLM
- AMBIENT 時 ASR 完全不跑（省 cloud cost + 省 Jetson GPU）

### State machine

```
AMBIENT (wake word listening, ~5% CPU)
  └─[wake hit / OK / wave / face_yaw_aligned]→ ATTENTIVE (8s window)
        ├─[speech end]→ ASR → LLM → TTS → 回 AMBIENT
        └─[timeout 8s 無互動]→ 回 AMBIENT
```

### 對齊「為什麼是狗」

| 能力 | 狗的對應 |
|---|---|
| 叫名字喚醒（wake word） | 狗叫名字才回頭 |
| OK 手勢進手勢模式 | 狗對主人手勢敏感 |
| 看著 PawAI 自動進 ATTENTIVE | 狗會察言觀色 |
| 不叫不互動 | 狗在旁邊待著，不會插嘴 |

### 不做

- ❌ Look-and-Talk 純視覺喚醒（Google Nest 等級，6/18 不現實）
- ❌ Conversation Mode 多輪免喚醒（Alexa Conversation 等級）
- ❌ VSDLM 嘴在動 + 看著 multimodal（P1 加分，列下一階段）

---

## 8. VLM scene describe：巡檢回報核心能力

教授 5/21 pivot 後，VLM 從 v2 原本「demo 殺手鐧 nice-to-have」**升為巡檢閉環的核心能力**——巡檢的「到點 → 觀察 → 回報」這段，VLM 是把現場視覺翻譯成「活動區看到 3 位住民、王爺爺在窗邊」這種報告語言的關鍵。不能砍。

### 路線

- **主線**：Gemini 2.5 Flash（OpenRouter）— P50 1.2-2s，~$0.00045/call
- **Fallback**：GPT-5.4-mini Vision（同 OpenAI key 省整合）
- **離線兜底**：**Reject local VLM**（Orin Nano 8GB 共存不可能），改 graceful degrade「網路不穩，我看不清楚」

### 主要用法

**到巡檢點後描述現場**：誰在做什麼、物品在哪、有沒有疑似異常。VLM 輸出 + brain `patrol_status` 規則組合成最終 TTS 回報。

### 巡檢回報流程

```
照護人員："PawAI，去活動區巡一下"
→ Brain (gpt-5.4-mini) 解析 → tool: navigate(activity_room) + observe_and_report
→ Nav2 到達 → 等 1s 穩定 → grab 1 frame (D435 1280×720, JPEG q=85, ~150KB)
→ POST Gemini 2.5 Flash + 中文 prompt → 1.5-2s
→ 結合 face_identity（住民身份）+ object_schema（物品位置）+ patrol_status（通道狀態）
→ Brain 組合 → TTS「活動區目前正常，有 3 位住民，張奶奶在窗邊」
```

**Latency budget**：nav 8-20s + capture 0.5s + VLM 2s + TTS 1.5s ≈ **12-25s**（可接受）

**Fallback**：VLM 失敗 → YOLO `person` class 在 frame 內？→ 退化「我偵測到 N 個人」

### 預算衝擊

12 call/day × 30 day < $0.20，**0 預算風險**

### 紅旗

- Wi-Fi 死 = 功能死（demo 現場備 4G 熱點）
- Hallucination ~10%（緩解：強制 JSON 輸出 + cross-check YOLO bbox count）
- 中文 fallback 英文（system prompt 強制「**只用繁體中文回覆，不超過 30 字**」）

---

## 9. 手勢 / 姿勢 / 人臉 / 語音穩定化

### 手勢 3 補充（必做，不論 spike，2.5 天）

ROSOrin Pro 穩定其實是**示範場景遮蔽**（手收進腰部 / 移出 ROI），不是設計勝出。PawAI 客廳長拍才暴露。

| 補充 | 工程量 | 預期改善 |
|---|---:|---|
| Dwell time 0.6s 取代 vote buffer | 0.5d | 誤觸率降 60-70% |
| HandOwnerFilter（臉框綁手） | 1-2d | 多人誤觸歸零 |
| Hysteresis + 強制 idle 2s | 0.5d | 「手放著一直觸發」根除 |

### 姿勢 fallen state machine（必做，2 天）

不走 LSTM 路線（風險高），走 **state machine + edge-triggered alert**：

```
states: STANDING → FALLING → FALLEN → RECOVERED
transitions:
  STANDING → FALLING: vertical_ratio 下降 > 0.3 in 0.5s
  FALLING → FALLEN: vertical_ratio < 0.45 維持 > 1.0s
  FALLEN → RECOVERED: vertical_ratio > 0.6 維持 > 2.0s
  alert 只在 → FALLEN 邊緣發 (edge-triggered)
```

**fallen 可信賴度 60% → 90%+**。bending / akimbo / knee_kneel 維持 v1 降級策略（uncertain_pose）。

### 人臉（小改高回報）

- 把 `face_identity_enroll_cv.py` 包成 `pawai face enroll / list / verify` CLI（現場註冊）
- 陌生人警報維持預設關閉
- **不碰**：track 抖動根治、多人 3+ 同框（demo 後重構，列 L3）

### 語音 VAD（小改高回報）

- **Silero VAD 單一路徑**（已寫好但未啟用）取代 energy VAD
- 預期消除 2-10s 飄移
- **不碰**：echo gate 1.5s magic number、Megaphone 16kHz、LLM（5/12 已 freeze）

---

## 10. 模型選型：PINTO 3 類 + YOLO + Cloud LLM/VLM

### 範圍收窄（不要看到模型就想試）

PINTO 只討論三類：
- **物件偵測**：YOLO 家族 + INT8/FP16
- **人體互動**：Wholebody / head / hand / face（支援 Engagement Gate / fallen）
- **輕量分類**：wave / pose / face attribute（補 MediaPipe 弱點）

### 推薦清單（按狀態分類，不再混用 P0）

| 狀態 | 模型 | 來源 | 對應章節 | 備註 |
|---|---|---|---|---|
| **W1 spike candidate** | 6DRepNet360 | PINTO #423 | §7 Engagement Gate head pose | L2-G must；視 Engagement Gate 上線時程加 |
| **W1 spike candidate** | WHC 揮手分類 | PINTO #481 | §9 手勢 WaveDetector | L2-must 手勢補強時加 |
| **W1 spike candidate** | YOLOv8s + ByteTrack | Ultralytics | §10 物件偵測升級 | L2-stretch（W4 buffer 才加）|
| **Current baseline**（已在跑，不動） | gpt-5.4-mini | OpenAI | §4 Brain LLM 主線 | 5/12 freeze |
| **Current baseline** | Gemini 3 Flash | OpenRouter | §4 Brain LLM fallback | 5/12 freeze |
| **W1 spike candidate** | Gemini 2.5 Flash Vision | OpenRouter | §8 VLM 主線 | L2-H must（巡檢回報核心）|
| **W1 spike candidate** | GPT-5.4-mini Vision | OpenAI | §8 VLM fallback | 與 Gemini 2.5 同條件 |
| **Current baseline** | Whisper Small (cuda fp16) / SenseVoice cloud | 既有 | §9 ASR | 不碰 |
| **Current baseline** | Piper huayan / edge-tts / Gemini Despina | 既有 | §9 TTS | 不碰 |
| **L3 research candidate**（下一階段，不裝） | Lightweight-Head-Pose | PINTO #293 | 6DRepNet360 fallback | pose 預算吃緊時降階 |
| **L3 research candidate** | YOLOv9-Wholebody28 | PINTO #464 | 物件 + Engagement + Fallen 2-for-1 | 6 月後 spike 評估 |
| **L3 research candidate** | VSDLM 嘴在動 | PINTO 個人 repo | Engagement Gate multimodal | 6 月後 P1 加分 |
| **L3 research candidate** | HomeObjects-3K fine-tune | Ultralytics | 物件家用類別 mAP 80%+ | 下一階段做 |

### 拒絕

| 模型 | 拒絕理由 |
|---|---|
| YOLO26s | TensorRT bbox drift bug（Hackster 作者退回 v8n） |
| SmolVLM / Moondream2 / 任何 local VLM | Orin Nano 8GB 共存不可能（RAM 餘 0.8-1.5GB） |
| OpenClaw 整套 | rosclaw 不成熟、安全層弱、ROS2 bridge 不穩定 |
| YOLO-World / GroundingDINO | Orin Nano <2 FPS，「找助行器 / 找指定顏色物品」用 YOLOv8s + HSV mask 就好 |
| Depth-Anything-Small | D435 0.3-3m 已 ±2cm，加 Depth-Anything 多吃 1.5GB + 80ms |
| LSTM 跌倒分類 | state machine 已能達 90%+ |
| MediaPipe Face Mesh 468 點 | 不必要 |

### L3 候選（寫進未來潛力）

- **YOLOv9-Wholebody28** (PINTO #464)：MIT INT8，2-for-1 同時餵物件偵測 + Engagement head + Fallen keypoint。**6 月後 spike 評估 RAM**
- **VSDLM** (Visual Speech Detection by Lip Movement)：Engagement Gate multimodal 加分
- **HomeObjects-3K fine-tune YOLOv8s**：12 個家用類別 mAP 80%+，下一階段做

---

## 11. 6/18 demo 驗收腳本

### 場域

**主場景敘事**：長照 / 日照中心 / 養護機構（影片裡用 AI 生成補完）。
**實拍替代場**：家裡 / 學校走廊 / 實驗室（小型可控、人流可控、特徵密、可重複建圖）。場域定義以「< 100㎡」為 POC 邊界。

**Demo 穩定化**：場域貼 4 張 AprilTag tag36h11（對應 L1-7）作為 **demo grounding 輔助證據**——讓觀眾在影片中能看到「PawAI 識別環境標記」這個視覺事件，並讓 brain 收到 `/event/location_anchor` 補充 context。AprilTag **不是 nav status 替代品、不取代 AMCL/Nav2**，只是「PawAI 看見並識別了這個地點」的視覺輔助。

### Demo 主腳本：一條任務閉環，三段呈現

教授 5/21 pivot 後，demo 不再是三個獨立場景，而是**一條完整任務閉環故事**——「派去 → 現場 → 回報」——三段呈現。這對應 v2 §3 任務閉環，也對應教授提到 RoboPair「複合式任務，不要單一功能切片」的競品借鑑。

| 段 | 內容 | 對應能力 | 「為什麼是狗」鐵律 |
|---|---|---|:---:|
| **段 1 派去巡檢** | 照護人員：「PawAI，去活動區巡一下」→ Engagement Gate 接到指令 → Brain 拆解 → Nav executor 啟動 → PawAI 走向 named waypoint（活動區） | Engagement Gate + Brain + NAV executor + Named waypoint | 移動 ✅ 實體 ✅ 多模態 ✅ |
| **段 2 現場互動** | PawAI 到達活動區後 → face_identity 認出張奶奶「張奶奶您好」→ 偵測到某長輩久坐 → 主動靠近「您坐很久了，我陪您一下」→ Object schema 記錄物品位置（輪椅 / 助行器 / 水杯）+ patrol_status 判斷通道暢通 | face_identity + Pose state + LLM persona + Object schema + Engagement Gate | 移動 ✅ 實體 ✅ 多模態 ✅ |
| **段 3 巡檢回報** | PawAI 回到照護人員端 → VLM scene describe + 多源融合 → TTS：「活動區目前正常，有 3 位住民，張奶奶在窗邊，王爺爺在沙發。沒有異常。」| VLM scene describe + face_identity + object_schema + patrol_status + TTS | 移動 ✅ 實體 ✅ 多模態 ✅ |

**跌倒情境退為段 2 的 if-branch**（不獨立成場景）：如果段 2 PawAI 偵測到 fallen state machine 觸發 → 走過去確認 → 加入段 3 回報「**活動區有一位長者倒在地上，請工作人員立刻確認**」。**收尾情感落點**：PawAI 走到長者旁邊那個畫面 → 黑屏 → 「PawAI — Physical AI for Institutional Care」。

### Demo failure fallback（必寫進 spec）

每個主要技能必須有 fallback path，避免 demo 現場啞掉：

| 技能 | 主路徑 | Fallback |
|---|---|---|
| VLM scene describe | Gemini 2.5 Flash | YOLO person count → 「我偵測到 N 個人」 |
| Wake word | OpenWakeWord 「嗨 PawAI」 | 退回 always-on ASR + manual button trigger |
| ASR | Silero VAD + SenseVoice cloud | Studio 鍵盤輸入 |
| Nav goto_relative | Nav2 + STVL/depth_safety | 原地轉身 + 語音「我無法移動，但我聽到你了」 |
| Object find_nearest | depth_m good | depth_m unavailable → 「我看到助行器但距離測不到」 |
| Fallen detect | state machine | 退回單幀規則（v1 行為）|
| Brain LLM | gpt-5.4-mini | gemini-3-flash → RuleBrain rescue |
| TTS | Gemini Despina | edge-tts → Piper |

**Demo 演出策略**：
- 先放錄影 30 秒「標準版」建立可信度
- 再現場 live 跑一遍證明真實
- 即使 live 出包，觀眾已買單

---

## 12. 非目標與未來潛力

### 本窗口不做（明確擋掉）

- ❌ **PawAI 定位成居家陪伴狗**（一般家庭非合理採購方，手機/智慧音箱競品太強）
- ❌ **PawAI 取代照護人員**（定位是輔助第一線確認，不取代專業判斷）
- ❌ **任何醫療級監測宣稱**（POC 不做、無證照、不擔責）
- ❌ 完整自主尋物閉環（物件感知只到 schema v2 + find_nearest）
- ❌ 大型場域動態人流繞行必達（只列 spike 加分）
- ❌ 大規模自建資料集訓練（HomeObjects fine-tune 列下一階段）
- ❌ 姿勢 7 類全分類主動觸發（fallen state machine 已收斂）
- ❌ 重寫 Brain / 引入 OpenClaw / rosclaw（PawAI 已有 skill_contract + Executive）
- ❌ PawAI 定位成寵物狗或語音助理
- ❌ Local VLM on Jetson（RAM 不可能）
- ❌ LLM 直接 publish cmd_vel（安全紅線）

### 本窗口不碰（凍結項）

- 人臉 track 抖動根治、多人 3+ 同框 bbox 互竄（demo 後重構）
- 語音 echo gate 1.5s magic number、Megaphone 16kHz 硬體限制
- LLM（5/12 已 freeze `openai/gpt-5.4-mini`）

### L3 產品願景 roadmap（影片末段挑 3 個）

工程候選清單見 §2 L3。下表是**對外敘事用**的產品願景，附成熟度時程：

| 未來場景 | 敘事價值 | 技術延伸 | 時程層級 |
|---|---|---|---|
| 校園 / 機構巡邏 | 最接近現有 demo，可自然延伸 | waypoint 巡邏、異常回報、遠端查看 | 1-3 個月 |
| 商場遺失物協尋 | B2B 想像強，採購方合理 | 物件搜尋、人員查找、地圖巡檢 | 3-6 個月 |
| 居家延伸 | 長照機構成功後可下放家庭 | 小型化、安全距離、家用 UI | 6-12 個月 |
| 導盲 / 弱勢輔助 | 教授原本推薦，公益敘事強 | 人流避障、語音導航、高安全驗證 | 1 年+ |
| 救災 / 戶外搜救 | 機器狗不可替代性最強 | 戶外導航、樓梯、熱源/煙霧/通訊 | 1-2 年+ |
| 戶外巡檢 / 工業巡檢 | 商業價值高 | 防水防塵、長距導航、設備辨識 | 1-2 年+ |

**5/27 影片末段選擇**（不全塞，避免稀釋焦點）：
1. **校園 / 機構巡邏** — 最接近現在，可信
2. **導盲 / 弱勢輔助** — 接住老師原本建議
3. **救災 / 戶外搜救** — 最大夢想，最能凸顯狗的不可替代性

商場遺失物 / 居家延伸 / 戶外工業巡檢可放簡報文字，不放影片鏡頭。

### 對外敘事範式

> PawAI 不是在宣稱已能商用部署，是在機構照護場域做 Physical AI 原型驗證：固定攝影機只能看，App 只能提醒，PawAI 可以走到現場，用多模態感知先幫照護人員確認狀況。未來可擴展至校園、商場、居家延伸、導盲、救災等場景。整套架構已為下列方向預留：跨房間任務鏈、社交導航、人臉 ad-hoc query、3D mapping、長期記憶、自訂物件辨識。

---

## 13. W1 spike gate 與 4 週時程

### W1 三個硬 gate（同步並行）

| spike | 驗收標準 | PASS → | FAIL → |
|---|---|---|---|
| **#1 Depth safety gate**（baseline critical） | D435 `depth_to_scan` 投影成 `/scan_depth`（地面以上 10-40cm slice），reactive_stop 訂雙 scan 取 min，1m 內低矮包包 / 椅子腳能穩定觸發 slow / danger | 解鎖 L2-A1（Nav fusion 到 depth safety）正式做；spike #3 可繼續評估 | **Nav fusion 全降級為 LiDAR-only**，L2-A1 砍；NAV 只做 executor + named waypoint，靠 LiDAR 既有避障 + Studio / VLM demo 視覺補；不重新規劃整個 5/22-6/18 |
| **#2 Object schema v2 gate** | `object_perception_node` 加 depth 訂閱 + bearing 計算 + schema v2 backward compat；brain `_recent_objects` 吃新欄位無 regression；20 物件場景 position_quality 分布報告（good ≥70%） | 解鎖 L2-B1 完整版（含 IoU tracking + `position_3d` + `find_nearest`，9 天工程）；時程吃緊可降 thin 版（5 天，無 tracking / `position_3d`） | 退 **side-channel depth cache** — event schema 完全不動，object node 內部維護 `bbox_id → depth_m` dict，brain 透過 service `/object_perception/query_depth` 按需查（~1 天）；保「巡檢看到誰在哪」最小可用 |
| **#3 STVL feasibility gate**（**stretch only**，PASS 也不是必做） | STVL @ Orin Nano 8GB + 現有 5 模型共存不 OOM（RAM ≤7.5GB peak）；D435 12° 下傾下 face_perception 可用率 ≥80%；STVL ghost obstacle 在 Go2 急轉時不會把自己框住 | 解鎖 L2-A2 stretch（STVL 進 Nav2 costmap 繞靜態障礙）作為 demo 加分鏡頭——機構走廊單純，**不是必達** | L2-A2 確認放棄。主路線本來就不靠 STVL（機構走廊靠 LiDAR + reactive_stop + depth safety 已足夠），對主 demo 無影響 |

**深度檔位決定規則**（不再決定路線，路線只有一條）：
- spike #1 PASS + #2 PASS → L2 全套高電路（depth safety + Object schema 完整版 + VLM + Engagement Gate）
- spike #1 PASS + #2 FAIL → 同上但 Object 退 side-channel depth cache
- spike #1 FAIL → Nav fusion 全砍，靠 LiDAR + VLM + Engagement Gate + side-channel depth cache 撐 demo
- spike #3 PASS → W4 stretch 加 STVL 繞障 demo 鏡頭；FAIL 或無時間 → 不做

### Week 0 前置（5/22 前必完成）

繼承 v1 第 0 章 Week 0 Spec A 收尾：4 PR merge + Day 0 recovery + `pawai demo preflight` 兩階段全 PASS。

### 4 週時程（單一路線粗排）

> **粗排免責**：下方週次排程為 north-star 級粗估，僅作為「方向 + 必達 milestone」對照。**精確天數、依賴、並行排程、owner 分配留給後續 implementation plan**（用 writing-plans skill 產出）。
>
> **時程現實**：4 週可用 ~20 工作天，扣掉 W1（5d）= W2-W4 有 ~15 工作天主線時間。
>
> **L2-single 工程量加總**：L2-must 8.5d + L2-A1 depth safety 7d + L2-B1 Object schema（5~9d 依 spike #2）+ L2-G Engagement 3d + L2-H VLM 3d = **26.5~30.5 工程天**。**必須 2 dev 並行 + L2-stretch 多項保留 W4 buffer**。spike #2 FAIL 退 side-channel cache 1d 可省 4~8d。STVL stretch 只在 spike #3 PASS + W4 還有 5d 才加。

#### W1（5/22-5/28，5 工作天）— 共同前置

| 日 | 工作 |
|---|---|
| 5/22-5/23 | spike branch 開：D435 mount 12° STL 印製 + `depth_to_scan_node` MVP + Object schema v2 backward compat 試做 |
| 5/24-5/25 | STVL 整合試跑 + 三 spike 並行驗證 |
| 5/26 | spike 結果 review + 寫 `2026-05-28-w1-spike-results.md`，commit Object schema 深度檔位 + STVL stretch 決策 |
| 5/27-5/28 | L1 包裝層平行開展（skill metadata + persona 4 檔分離 + Mapping QA Checklist + AprilTag mount） |

#### W2-W4 — L2-single 主路線（spike 結果決定每能力深度）

| 週 | 主軸 | 必達 milestone |
|---|---|---|
| W2 (5/29-6/4) | NAV executor + named waypoint（活動區 / 護理站 / 休息區 4-5 點）+ depth safety（D435 進 reactive_stop，spike #1 PASS）+ L2-must 並行（手勢 3 補充） | 「PawAI 去活動區」走 named waypoint + 遇障停 |
| W3 (6/5-6/11) | Engagement Gate（wake word「嗨 PawAI」）+ VLM scene_describe + Object schema 實作（依 spike #2 完整 / thin / side-channel）+ L2-must 並行（fallen state machine） | 巡檢三段閉環 E2E：「派去 → 現場互動 → 回報」首次跑通 |
| W4 (6/12-6/18) | Demo 腳本固化 + fallback paths 全驗 + stretch（spike #3 PASS 加 STVL demo 鏡頭 / Plan templates / 物件 YOLOv8s 視時程加分）| 三段巡檢閉環 demo 連跑 5/5 通過率 |

### 4 週後立即排程（L3 開展）

- W5+ HomeObjects-3K + 自拍 fine-tune YOLOv8s
- W5+ YOLOv9-Wholebody28 spike
- W5+ VSDLM 嘴在動 multimodal

### 全域風險

demo flow 預期連跑 30 分鐘以上，可能撞 stale state（見第 5 章 F7 紅旗）。若 F7 尚未根治，nav 段前 fresh restart stack；若已根治，需由 watchdog/preflight 證明 `/cmd_vel_nav` 與 lifecycle 狀態正常。

---

## 附錄 A：變更紀錄

### A.1 與 v1（2026-05-19）變更對照

| v1 章節 | v2 對應 | 變更 |
|---|---|---|
| v1 §0 Week 0 | v2 §13 共同 W1 前置 | 沿用 |
| v1 §1 定位收斂 | v2 §1 新定位 | **全章重寫**：居家四足機器人 → 室內場域具身 AI 任務 POC（後再 amend 為機構巡檢助理，見 A.2）|
| v1 §2 物件偵測 | v2 §6 + §10 | **拆**：升級主軸從「換大 YOLO」改「schema v2 + depth/bearing」；模型選型獨立成章 |
| v1 §3 手勢辨識 | v2 §9.手勢 | 沿用，吸收 subagent 3 個補充（dwell + HandOwner + idle）|
| v1 §4 導航避障 | v2 §5 + §13 | **重寫**：D435 三層擴充 + Spike-then-commit 取代固定 P0/P1 |
| v1 §5 姿勢辨識 | v2 §9.姿勢 | 沿用 P2 降級 + 加 state machine |
| v1 §6 人臉 + 語音 | v2 §9.人臉 + 語音 | 沿用，吸收 Silero VAD 切換 |
| v1 §7 全域驗收 | v2 §11 demo 驗收腳本 | **重寫**：三場景按情感曲線排 + Demo fallback 寫入規格（後再 amend 為單一任務閉環三段呈現，見 A.2）|
| v1 §8 非目標 | v2 §12 非目標與未來潛力 | **擴展**：加 L3 完整 roadmap |
| - | v2 §2 三層擴充模型 | **新增** |
| - | v2 §3 任務閉環 | **新增** |
| - | v2 §4 Brain/Skill/Executive 包裝 | **新增**（含 Safety/Policy/Expression 三層敘事）|
| - | v2 §7 Engagement Gate | **新增** |
| - | v2 §8 VLM scene describe | **新增** |

### A.2 v2 → v2-amended（2026-05-22 教授 5/21 機構巡檢 pivot）

教授 5/21 兩個半小時會議後，定位從「室內場域具身 AI 任務 POC」收斂為「**面向長照 / 日照中心等機構場域的室內巡檢與互動助理 POC**」。amendment 範圍 medium，工程能力一行沒砍。

| 章 | amendment 動作 |
|---|---|
| §1 定位 | 重寫主 statement + 場景分層（主軸長照 / 技術手段巡檢 / 拍攝替代場 / 未來延伸）+ 拒絕標籤加「居家陪伴狗」 |
| §2 L2 | 取消 α/β 二分；改 **L2-single 單一路線 + spike 決定深度檔位**；L2-stretch trigger 重整；L3 改為「工程候選清單」並指向 §12 產品 roadmap |
| §4 Brain | 加 **場景語言對照表**（7 項工程語言 → 對外敘事）+ **`patrol_status` 概念**（多源融合，不是 detector class）+ PaStudio 三鏡頭 demo 不出現 |
| §6 Object schema | 加 **機構場景 A 層 class set**（resident / wheelchair / cane-walker / medicine_box / cup-bottle / bag / chair）+ 註明 person 身份由 face_identity；example query 從「找紅色背包」改「巡檢看到誰在哪、有什麼物品、通道是否暢通」 |
| §7 Engagement Gate | 微 reframe：trigger 兩類來源（**照護人員主動派遣** + 長者主動發起互動）；陌生人不打擾 |
| §8 VLM | 從「nice-to-have」**升為巡檢回報核心**；用法改「到巡檢點後描述現場 + 多源融合成 TTS 回報」 |
| §11 demo 場景 | 重寫為**一條任務閉環三段呈現**（派去 → 現場 → 回報）；跌倒退為段 2 if-branch；場域分「主場景敘事=機構」+「實拍替代場=家裡」 |
| §12 非目標 | 新加「不做居家陪伴狗 / 不取代照護人員 / 無醫療級監測宣稱」；新增 **L3 產品願景 roadmap**（6 項 + 時程層級）+ 影片末段挑 3 個 |
| §13 W1 spike | **spike #3 STVL 降為 stretch-only**（PASS 也不是必達）；W2-W4 改成**單一路線粗排**，取消 α/β |
| header | 狀態 "Draft for 5/22 discussion" 後加「2026-05-22 amended after 教授 5/21 機構巡檢 pivot」 |

## 附錄 B：累積決策依據（subagent 報告索引）

2026-05-21 brainstorming session：
1. Hiwonder ROSOrin Pro 競品分析（OpenClaw 拆解）
2. PINTO_model_zoo Top 5
3. AI 影片腳本 + seedance/gpt-image 工作流
4. 物件辨識升級實戰（YOLOv8s + ByteTrack + CLAHE）
5. 手勢誤觸根因（dwell + HandOwner + idle）
6. 姿勢/跌倒 SOTA（state machine + depth fusion）
7. VLM scene_describe 可行性（cloud only）
8. Engagement Gate + Wake word 架構
9. Structured Plan + Multi-Step Orchestration（hardcoded templates P1）

2026-05-22 brainstorming session：
10. PINTO 廣度掃描對應 PawAI 已決方向
11. 2D LiDAR + D435 融合導航避障實戰
12. 物件 event schema 升級 + depth/bearing 整合

2026-05-22 教授 5/21 pivot 後 reconciliation：
13. v2 spec vs 教授新方向（機構巡檢）reconciliation + demo 三場景重設計
14. 影片生成管線澄清：OpenRouter 可用 `bytedance/seedance-2.0`（text/image-to-video，~$7/M tokens）；本案改以 **Seedance 路線**評估，**不走 Sora**（Sora 與 Seedance 為不同模型；教授 5/21 提到的「Sora via OpenRouter」實為 Seedance）
15. Nyanmaru repo 評估（教授講錯名字，實際就是 PINTO_model_zoo，無新東西）

---

## 文件治理

- 本文件 supersede [`2026-05-19-pawai-may-june-north-star-design.md`](2026-05-19-pawai-may-june-north-star-design.md)
- v1 加 superseded header 但不刪
- 後續每日進度更新到 `references/project-status.md`
- L1 包裝層執行進度寫到 `docs/mission/sprint-b-prime.md`（沿用既有 sprint 文件）
- W1 spike 結果寫到 `docs/superpowers/specs/2026-05-28-w1-spike-results.md`（新檔，spike 結束後寫）
- 後續 implementation plan 用 writing-plans skill 產出
