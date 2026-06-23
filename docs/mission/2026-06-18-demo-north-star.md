# 2026-06-18 Demo North Star v2

> **Status**: v2 — 戰略邊界文件（取代 2026-05-29 v1 draft）
> **Created**: 2026-05-29 ｜ **v2**: 2026-05-31 ｜ **Deadline**: 2026-06-18
> **性質**：這是 6/18 專題驗收的**戰略邊界文件**，不是開發計劃。它回答「要展示什麼、為什麼需要機器狗、哪些話不能講、哪些能力只是候選、哪些一定要守住」。實作計劃見 `docs/archive/pawai-brain-legacy/plans/2026-05-31-capability-baseline-scoreboard-plan.md`。
> **與 ADR 的關係**：本文件的定位用詞 **amend ADR-0001 / ADR-0002**（平台/demo 雙層敘事保留；demo 層由「非接觸式機構巡檢助理」reframe 為「機構公共空間非接觸式守望互動 POC」）。ADR 正文待本文件 review 後再正式 amend，此處先記錄不 silent conflict。
> **可靠度紀律**：本文件所有 P0 / P1 / P2 分層皆標 **`provisional until baseline`**——必須等上機 capability baseline 跑出數據，才從 provisional 轉 locked。先決定後量化是被禁止的。
> **能力 claim 真相源**：每能力「能講什麼 / 不能講什麼 / 屬哪個分級」以 [`docs/mission/2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md) 為 canonical（綁 6/04 HITL trusted snapshot）；本文件是戰略邊界，能力是否 pass 一律回 claim matrix + baseline-evidence。
> **v2 三項保留意見已套用（2026-06-05）**：(1) §1/§3 的「安全停車」改為 **baseline pass 後才宣稱**、未 pass 只在 Studio 顯示；(2) §10「斷網也能守望」保守化為**設計意圖、需 current-path baseline 驗證**；(3) §9 capability health gate 改述為**將補在既有 effective_status 純函式中、非現成已存在**。

---

## 1. One-Line North Star

> **PawAI 是面向機構公共空間的非接觸式守望互動四足機器人 POC。**

6/18 demo **不宣稱**完整長照、完整導盲或完整自主導航；它展示的是一台四足機器人如何以**量化驗證過的**感知與語音能力，在室內場域完成一段**安全、可解釋**的守望互動。**短距移動與「遇障安全停車」是 6/18 的目標而非既成宣稱**——`nav.short_move` / `nav.safe_stop` 在 nav baseline run 標 pass（或明確人工安全 override）前一律 `insufficient_data`、**只在 Studio 顯示、不口頭宣稱**（見 §5 / §7）。

6/18 是現場展示，不是剪輯影片，也不是展示「功能清單全部完成」。目標是跑出一條可信的守望互動閉環，而非把每個研究方向做到 production。

---

## 2. Positioning

定位分兩層（沿用 ADR-0002 雙層敘事）：

- **平台層**：PawAI 是**安全優先的居家 / 機構四足具身互動機器人**。
- **6/18 demo 層**：**面向機構公共空間的非接觸式守望互動 POC**。

明確標記：

- **照護**是長期 vision，**不是** 6/18 主張。
- **導盲犬**是價值參考（借鑑「幫看不到危險的人先看到」的非接觸守望價值），**不是** 6/18 能力主張。
- **巡檢**是 future / 可延伸場景，**不是**完整 patrol demo。

### 「守望」canonical 定義（6/18 用詞）

> **守望**：PawAI 在**非接觸**前提下，觀察室內公共空間中的人、物與互動狀態，提供**提醒、回報與可解釋的互動**；**不包含**攙扶、接觸、主動保護、陌生人警報或替代照護人員。

> ⚠️ **用詞紀律**：6/18 一律用「守望」，**不用**「守護 / guardian / 陌生人警報 / 保護長者 / 照護安全」——後者在既有文件綁定 guardian mode + 已停用的陌生人警報，責任感過重且會引來無法承諾的期待。「守護 / guardian」屬舊框架 / future，不進本文件主語言。

### 為什麼選機構而非居家

Go2 機體大、重（**十多公斤級，約 15–20kg**），**居家空間不實用**；機構公共空間（長照中心交誼廳 / 校園公共區）較適合四足平台移動，也對齊 ADR-0001 既有的「機構」定位。

---

## 3. Why Quadruped（回答老師最核心的質疑）

> 為什麼一定要機器狗？不是 APP / 音箱 / 固定攝影機 / 一般機器人就好？

| 替代方案 | 做得到 | 做不到 |
|---|---|---|
| APP | 語音 / 通知 | 無法在場、無法移動、無法看見現場 |
| 智慧音箱 | 對話 | 無法視覺感知、無法移動、無法展示安全停車 |
| 固定攝影機 | 監看固定角度 | 無法走到角落、無法實體回應、無低視角 |
| 一般輪式機器人 | 移動較穩 | 較少四足平台的在場感與互動辨識特色 |
| **PawAI / Go2** | **看、聽、走、停、回報、Studio 證據** | 不承諾接觸式照護或完整自主導航 |

**「非狗不可」錨在我們能可靠展示的具身核心**（不是錨在完整引導/跟隨）：

- 能移動到現場
- 有在場感
- 能從低視角觀察人與物
- 能用身體反應（坐下 / 拒絕危險動作）
- （目標，**baseline pass 後才宣稱**）能在物理空間中**安全停下**——`nav.safe_stop` 未在 baseline 標 pass 前不口頭宣稱，只在 Studio 顯示
- 能把現場證據送回 Studio

> **重點句**：PawAI 的價值不是「更會聊天」（那會輸雲端大模型），而是能在**物理空間中到場、觀察、提醒、回報，並（目標）在遇到風險時安全停下**——這些 APP / 音箱 / 固定攝影機本質上做不到。（「安全停下」是 6/18 的具身證明**目標**，`nav.safe_stop` 在 baseline 標 pass 前不作為已成立宣稱，只在 Studio 顯示。）

---

## 4. Demo Promise（6/18 承諾）

> PawAI **只使用目前量化驗證為可靠的能力**進入 Brain 主線，完成一段**非接觸式室內守望互動流程**；每個判斷都能在 Studio 顯示證據；不可靠能力**只顯示、不觸發、不宣稱**。

被問「可靠嗎」時，回答方式是指向 scoreboard：「這項 pass 所以 Brain 在用、這項 degraded 所以只顯示、這項 fail 所以 6/18 不宣稱」——**scoreboard 的誠實本身就是可信度**（見 §9）。

---

## 5. Non-Claims / 禁說清單（避免 overclaim）

6/18 **不宣稱**：

- 完整自主導航
- 自動找人
- 動態繞障已完成
- 導盲犬能力已完成 / 可引導盲人
- 跟隨人
- 巡邏整個機構
- 長照照護可靠
- 跌倒偵測可靠
- 通用物體辨識
- 功能全開 / 全自主
- LLM 回答自然度 = 機器人可靠性
- 守護 / 陌生人警報 / 主動保護

分兩層講，避免提前宣稱未經 baseline 的能力：

- **目前（baseline 前）可說的「價值 / 角色語言」**：守望、提醒、回報、非接觸、可解釋互動、Studio evidence；以及「借鑑導盲犬的非接觸守望價值，但 6/18 不宣稱導盲能力」。
- **通過 baseline（scoreboard 標 pass）後才說的「能力宣稱」**：短距安全移動、遇障安全停車、揮手互動、物件辨識——**每一項都僅在該能力於 scoreboard 標 pass 後才進旁白**；其中「遇障安全停車」需 nav baseline run 標 pass（或明確人工安全 override）後才宣稱，未 pass 前一律 `insufficient_data`、只在 Studio 顯示、不口頭宣稱。

---

## 6. Canonical Demo Story（串成故事，不是功能清單）

1. PawAI 在機構公共空間待機。
2. 使用者靠近，PawAI 透過**人臉辨識**確認是否為註冊對象。
3. PawAI 主動打招呼，並透過**語音 / Studio** 進入互動。
4. 使用者給出**固定語音指令**，Brain 解析意圖並通過 safety / capability 檢查。
5. 使用者**揮手**：若 baseline 顯示 `gesture.wave` 可靠則回應互動；若不可靠，只在 Studio 顯示（不觸發動作）。
6. PawAI 執行**短距移動**或準備靠近。
7. 前方出現人或障礙物時，PawAI **安全停下，不自動暴衝恢復**（no_auto_resume）。
8. PawAI 辨識桌上 demo 物件（例如杯子），做**提醒 / 描述**。
9. **Studio 顯示每一步的 evidence**：感知 event → Brain decision → safety / capability gate → skill result。

> 規則：影片 / 旁白裡每一句宣稱，都要有對應的 ROS topic、debug image 或 Studio trace 背書。

---

## 7. P0 必留底線（`provisional until baseline`）

> 「必留底線」= 範圍優先級（不能再砍的東西），**不是** runtime 攔截。runtime 攔截一律用 gate（Engagement / capability / safety / depth gate、證據用的 gate-0）。
> 以下全為 **provisional**，需上機 baseline 後轉 locked。

- **face.recognition**：註冊者辨識與問候
- **voice.command**：固定指令輸入
- **brain.skill_gate**：Brain 不亂執行不可靠能力（fail-closed）
- **studio.evidence**：Studio 顯示每步證據（差異化全押可驗證，這是硬前提）
- **nav.short_move + nav.safe_stop**：6/18 具身證明的**目標**——「機器狗非噱頭」要靠這一條，但**baseline pass 後才宣稱**。完整自主導航、動態繞障、跟隨人**不屬於 6/18 主張**。（前置鎖：① F7 `cmd_vel_nav` 不出的 root cause 須在 fresh stack 上定位；② `nav.safe_stop` / `nav.no_auto_resume` 在 nav baseline run **pass（或明確人工安全 override）前，scoreboard 一律 `insufficient_data`**——未 pass 前文件 / demo 不得宣稱已具備安全停車或具身導航能力，nav 相關 claim 一律不講。）
- **object.cup**：至少一類 demo 物件可靠辨識
- **gesture.wave**：**P0 target / candidate**——需 baseline 驗證誤觸率後才鎖定（不寫「P0 必成」，否則與「先量化」矛盾）

---

## 8. Scope Boundary（`provisional until baseline`）

**P1 / Bonus**：

- 完整導航
- 動態繞障
- D435 active pause / cancel
- 多物件追蹤
- 粗姿勢描述（standing / sitting / bending）
- PINTO WHC / SC spike（go/no-go 2026-06-06）

**P2 / Future**：

- 導盲犬能力
- 跟隨人
- 跌倒偵測
- 雙手插腰 / 單腳跪地
- 假牙 / 鑰匙 / 錢包（COCO 不含、不自訓）
- 真 VLM 場景理解
- ElevenLabs 主線
- 照護場景 / 守護 / 陌生人警報

---

## 9. Scoreboard-First Principle（整份文件的核心方法論）

能力不是二元的「有 / 沒有」，而是分級：

- **pass**：可進 Brain 主線（可控制機器人）
- **degraded**：可顯示、可語音說明，但**不可控制機器人**
- **fail**：不宣稱、不觸發
- **insufficient_data**：不放行高風險動作（motion / nav）

> **Brain 必須 fail-closed**：當能力為 `degraded` / `fail` / `insufficient_data` 時，**不得用該能力觸發 motion / nav 類動作**。此 health gate **不是現成已存在的強制 gate**——它**將補在 `pawai_brain` 既有的 effective_status 純函式中**（新增 `capability_health` 分支，#85 v0.2），**6/18 預設關閉（fail-closed）、不接 runtime motion 觸發**，僅作為能力分級的設計落點，也不在 LLM prompt 層做。**在它真正接上前，不得宣稱「capability health gate 已存在 / 已生效」。**

這也是 §4 demo promise 的執行機制：scoreboard 決定 Brain 能不能用某能力，而不是「功能寫了就用」。

---

## 10. Edge AI Framing（回應老師「不要只用 PC / GPU 算力評估」）

> PawAI 的 Edge AI 價值在於 **Jetson 端即時感知、ROS2 狀態整合、安全 gate、fallback 行為與 Studio evidence**。雲端 LLM / TTS 是**互動品質加分，不是系統可靠性的唯一來源**。

具體證明：感知（face / pose / gesture / object）+ 安全層 + reactive_stop 全在 Jetson 邊緣跑。斷網守望（本地感知 + 固定指令 / RuleBrain / Piper）是**設計上的目標路徑，尚未經 current-path baseline 驗證，因此目前只作為「設計意圖」陳述、不作為已成立的 Edge AI 證據**（repo 雖有 `sensevoice_local` / `whisper_local` / `piper` / RuleBrain fallback 線索，但現行語音主線仍走 Studio / Gateway / Cloud path，完整斷網閉環尚未在 current path 跑通；通過 baseline 後才升級為已驗證證據）。不要用桌機 GPU 標準評估 Jetson 表現。

---

## 11. Reporting Guidance（簡報怎麼講）

**優先講**：

- Before / After（Before：Go2 只是遙控機器狗；After：能語音、視覺、Brain、安全 gate、Studio 監控）
- 為什麼需要 Go2（§3）
- 硬體與系統整合難點（第三方 SDK、降壓板防燒、3D 列印固定座、有線網路、TTS/ASR/LLM fallback、危險動作鎖定）
- 高層架構圖（User / D435 / Jetson / ROS2 / PawAI Brain / Studio / 雲端 LLM / Go2）
- 資料流程圖（感知 event → Brain → safety / capability gate → skill → robot action → Studio evidence）
- 實測數據與 Studio evidence

**避免一開場就講**：

- 我們還做不到完整導航
- 我們還不能真的長照
- 我們還不能導盲

（老師原則：先講你做到的，人家追問再說限制；單一功能串成故事。）

---

## 一句話總結

這份文件不是在說「我們要做哪些功能」，而是在說：

> **6/18 我們如何誠實但有力地展示 PawAI 的價值，並避免過度承諾。**
