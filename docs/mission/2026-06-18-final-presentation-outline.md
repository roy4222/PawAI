# 2026-06-18 期末報告內容大綱（Final Presentation Outline）

> **Status**: v1 合成稿 ｜ **Created**: 2026-06-04 ｜ **Deadline**: 2026-06-18 驗收
> **性質**：這是期末報告（口頭簡報 + 文件）的**內容大綱與旁白邊界**，不是開發計劃。它規定「每一段要講什麼、放什麼證據、誰講、哪些話能講、哪些話一律不講」。
> **誠實鐵律來源**：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（以下簡稱 North Star）。本文件所有 do_say / dont_say 一律以 North Star §5 禁說清單、§7 nav 鐵律、§9 scoreboard-first、§11 報告原則為最終約束。
> **可靠度紀律**：依 **6/04 HITL trusted baseline snapshot**（SHA `78fbf36`，最新權威），3 項窄版 pass——`face.recognition`（n=9, recall=1.0；僅單一註冊者 Roy / idle 空景 / 真陌生人未測）、`object.cup`（~1m 近距 cup-only, n=7）、`voice.command`（n=24, success_rate=0.875）；2 項 **fail**——`voice.stop`（0.667, FN=2，**不可當安全停車**）、`gesture.wave`（recall=0.0）；pose / nav.* / brain.* / studio.evidence 皆 `insufficient_data`，`readiness verdict=not_ready`（因 voice.stop / gesture.wave fail + nav / brain 未量，**非因 face**）。窄版 pass 一律維持保守邊界（不宣稱守護 / 拒絕陌生人 / 通用物體 / 2m+ / 安全停車）。每能力分級的 canonical 真相源見 [`docs/mission/2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md)。`2026-06-03-first-trusted-face/` 已被取代，僅作歷史。報告全程：**先講做到的（量化機制 / Edge AI 邊緣感知 / 安全 gate / Studio evidence），被追問再講限制。**

---

## 0. 報告敘事主軸 + Before/After

### 0.1 一句話敘事主軸

> **PawAI 是一條完整的具身 AI 工程鏈：以 Unitree Go2 Pro 為載體，自行整合感測器 → 邊緣運算 → 多模態 AI 感知 → 任務決策（PawAI Brain）→ 機器人控制 → 可觀測（Studio）。我們不是把現成 AI 接上玩具狗，而是處理「AI 代勞不了的部分」——供電、固定、座標校正、資源預算、安全 gate、可靠度量測。能宣稱什麼由 scoreboard 量出來，不靠嘴。**

整份報告用一條線串起來：**Before（遙控機器狗）→ 工程改裝與整合 → 量化驗證（誠實層）→ After（具身 AI 守望）**。每一段都回到這條線，避免變成「功能清單朗讀」。

### 0.2 Before / After（這是開場與收尾共用的對照）

| 維度 | Before：原廠 Go2（遙控機器狗） | After：PawAI（具身 AI 守望）|
|---|---|---|
| 控制方式 | 手機 App / 遙控器人操作 | 語音 / 人臉 / 手勢 / 姿勢 / 物體多模態觸發 → Brain 決策 |
| 感知 | 內建感測封閉、LiDAR 覆蓋率約 18% | 外掛 D435 + RPLIDAR + USB 音訊，全在 Jetson 邊緣即時感知 |
| 智能 | 無語意理解 | PawAI Brain 三層（Safety → Policy → Expression），LLM 提建議、不直接控制 |
| 安全 | 無語意安全層 | rule-based 危險動作拒絕 + 雙層 fail-closed gate（91 unit test 背書）|
| 可觀測 | 黑箱 | PawAI Studio：感知 event → Brain decision → gate → skill result 可見 |
| 可靠度 | 不量測 | preflight → observer → JSONL → scoreboard → readiness 可重現工程鏈路量化 |

> ⚠️ **Before/After 的誠實邊界**：After 欄是「系統能力的設計範圍」，不是「每一項都已 pass」。6/04 量到 **3 項窄版 pass（face / object.cup / voice.command）+ 2 項 fail（voice.stop / gesture.wave）+ 其餘 `insufficient_data`**，readiness=not_ready。開場可以講 After 的**架構與工程鏈路已打通、且 3 項窄版能力已 pass**，但**不可暗示每項能力都已驗證可靠、也不可把窄版 pass 擴張成通用宣稱**——這條界線貫穿全 7 段。

### 0.3 全段嚴守的三條鐵律（每段 dont_say 的母規則）

1. **用詞**：一律「守望 / 提醒 / 回報 / 非接觸」。**禁用**守護 / guardian / 陌生人警報 / 保護長者 / 照護安全 / 防跌倒（North Star §2/§5）。
2. **scoreboard-first**：pass → 可進 Brain 控制機器人；degraded → 可顯示可語音、不可控制；fail → 不宣稱不觸發；insufficient_data → 不放行 motion / nav（North Star §9）。被問可靠度，一律指 scoreboard 證據。
3. **nav 鐵律**：`nav.safe_stop` / `no_auto_resume` 在 baseline 標 pass（或明確人工 override）前一律 `insufficient_data`，未 pass 前 nav 相關 claim **只在 Studio 顯示、不口頭宣稱**；前置鎖 F7（`/cmd_vel_nav` 不出 root cause）須先在 fresh stack 定位（North Star §7）。

---

## 第 1 段：PawAI 是什麼

**本段目標**：用一句定位 + 一張對比，讓老師立刻懂這不是「裝 AI 的玩具狗」，而是一條完整的具身 AI 工程鏈。先建立誠實基調（能力靠量測、不靠嘴）。

**報告人**：Roy（開場）

**要放的內容重點**：
- 一句話定位（North Star §1 鐵律）：PawAI 是面向機構公共空間的「非接觸式守望互動」四足機器人 POC，互動 70% / 守望 30%。
- 這是一個具身 AI 系統工程：硬體改裝（Go2 背上掛 Jetson + LiDAR + D435 + USB 音訊）→ 邊緣運算（Jetson Orin Nano）→ 多模態 AI 感知（人臉 / 語音 / 手勢 / 姿勢 / 物體）→ 任務決策（PawAI Brain 三層引擎）→ 機器人控制（interaction_executive 單一出口）→ 可觀測（PawAI Studio）。
- 與「把現成 ChatGPT 接機器人」的差異：我們處理的是 AI 代勞不了的部分——供電、固定、座標校正、安全 gate、資源預算、fail-closed。
- 誠實基調（North Star §11）：能宣稱什麼由 scoreboard 量化決定；每句宣稱都有 ROS topic / debug image / Studio trace 背書。

**可引用的 repo 證據與數據**：
- North Star 定位與報告原則：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（§1 一句話、§11 報告原則）
- 非接觸守望 POC 定位決策：[`docs/adr/0001-pawai-2026-06-poc-non-contact-positioning.md`](../adr/0001-pawai-2026-06-poc-non-contact-positioning.md)
- 平台層 / demo 層雙敘事：[`docs/adr/0002-pawai-platform-and-demo-scenario-two-layer-narrative.md`](../adr/0002-pawai-platform-and-demo-scenario-two-layer-narrative.md)
- 專案概述（Go2 載體、互動 70% / 守望 30%、PawAI Brain 三層）：`CLAUDE.md`

**建議視覺**：
- 一張「PawAI = 載體 × 邊緣 × 感知 × 決策 × 控制 × 觀測」六格定位圖。
- Go2 背上掛 Jetson + LiDAR + D435 的實機照片（近拍硬體堆疊）。

**do_say**：
- 「PawAI 是非接觸式守望互動四足機器人 POC。」
- 「我們在 Go2 上從硬體改裝一路做到 Robot Brain。」
- 「能力可靠度由 scoreboard 量出來，不是嘴上說。」

**dont_say**：
- 守護犬 / guardian / 保護長者 / 照護。
- 「這是完整的長照機器人。」
- 「功能全開、全自主。」

---

## 第 2 段：工程路線總覽（一張大圖串起六層系統）

**本段目標**：用一張端到端架構大圖把整個系統一次講清楚，建立後面每段的座標系。強調事件驅動 + 單一控制權 + fail-closed。

**報告人**：Roy

**要放的內容重點**：
- 端到端資料流：Go2 Pro（載體 / 電池）→ Jetson Orin Nano（邊緣運算）→ D435 / RPLIDAR / USB 麥克風（感測器）→ 五大 AI 感知 event（face / object / gesture / pose / speech）→ PawAI Brain 三層（Safety → Policy → Expression）→ skills allowlist 決策 → interaction_executive 單一出口控制 Go2 / Studio 即時觀察。
- 三層系統架構（mission §5）：Layer3 中控 → Layer2 感知 → Layer1 驅動，事件驅動、單一控制權。
- 關鍵設計原則：Brain 是「建議者」（只給 reply_text + proposed_skill），interaction_executive 是「決策者」（單一動作出口）；**LLM 永遠不直接控制機器人**。
- Edge AI framing（North Star §10）：face / pose / gesture 走 CPU、object 走 GPU TensorRT FP16、安全層 reactive_stop 全在 Jetson 邊緣即時跑。
- scoreboard-first 閘門（§9）：pass → 進 Brain / degraded → 只顯示 / fail → 不宣稱 / insufficient_data → 不放行 motion。這條 gate 卡在 Brain 入口。

**可引用的 repo 證據與數據**：
- 三層系統架構：[`docs/mission/README.md`](README.md)（§5）
- Brain 建議者 / Executive 決策者單一控制權、三層大腦對應：[`docs/archive/pawai-brain-legacy/architecture-0511/brain/brain.md`](../pawai-brain/architecture/0511/brain/brain.md)（§1、§14）
- 真實系統拓撲（13-window）：[`scripts/start_full_demo_tmux.sh`](../../scripts/start_full_demo_tmux.sh)
- scoreboard-first + Edge AI：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（§9、§10）

**建議視覺**：
- 主視覺大圖：Go2 載體 → Jetson 邊緣 → D435/LiDAR/麥克風 → 5 感知 event → PawAI Brain（Safety→Policy→Expression）→ skills allowlist → interaction_executive → Go2 控制 / Studio 觀察，**標出 scoreboard gate 卡在 Brain 入口**。
- 資料流箭頭圖：感知 event JSON → Brain decision → gate → skill result → Studio trace。

**do_say**：
- 「事件驅動、單一控制權、fail-closed。」
- 「Brain 提建議，Executive 才決策與執行。」
- 「感知全在 Jetson 邊緣即時跑。」

**dont_say**：
- 「LLM 直接控制機器狗。」
- 「這張圖每個功能都已驗證可靠。」（架構圖是設計，不等於每項都 pass。）

---

## 第 3 段：工程筆記網站（亮點，不是附錄）

**本段目標**：把「工程過程可追蹤」當差異化亮點：我們不是只剪一支成果影片，而是把硬體搭建、模型選型、benchmark、部署、safety/fail-closed、每個模組的工程決策全程留痕。**誠實標示站點本體目前 in-progress，承載體是 repo `docs/`。**

**報告人**：Roy（或負責文件站的組員代述）

**要放的內容重點**：
- 亮點主張：軟硬體開發很難、不能完全依賴 AI，所以我們把過程整理成可追蹤文件——讓「為什麼這樣做」可被檢視。
- 已累積的結構化素材（全在 repo）：4 篇 ADR、benchmark 選型制度（Research Brief → Candidate Shortlist YAML → Benchmark → Decision）、部署 runbook（含真實 baseline-evidence JSON 證據檔）、各感知模組 README/CLAUDE/AGENT 三件套、capability-baseline spec、大量 LiDAR / 硬體研究 log。
- 模型選型制度化：face/pose/gesture/stt 每個任務都有 `candidates.yaml` + archived `raw.jsonl` + `env_snapshot` + 3/21 決策文件——「為什麼選 YuNet」有 71 FPS CPU benchmark 背書。
- safety/fail-closed 設計有程式碼背書：`scoreboard_schema.py` 的 pass/degraded/fail/insufficient_data 分級 + Brain capability fail-closed 落點。
- 誠實口徑（避免 overclaim）：文件站「本體」（Astro/Starlight 骨架）目前 **in-progress、責任在組員（黃 / 陳）**；現在的承載體就是 repo `docs/`，現場可直接翻。nav 研究 log 只能呈現為「過程 / 設計」，不可呈現為「已完成能力」（North Star §7）。

**可引用的 repo 證據與數據**：
- 4 篇 ADR：[`docs/adr/`](../adr/)
- benchmark 選型制度：[`benchmarks/configs/`](../../benchmarks/configs/) + [`benchmarks/results/archive/`](../../benchmarks/results/archive/)（face/gesture/pose/stt `candidates.yaml` + 2026-03-21 archived `raw.jsonl` + `env_snapshot`）
- 可運作 scoreboard core：[`benchmarks/core/scoreboard_schema.py`](../../benchmarks/core/scoreboard_schema.py)（pass/degraded/fail/insufficient_data 分級）
- 真實證據檔（最新 trusted）：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（`baseline_result.jsonl` / `baseline_snapshot.json` / `preflight_result.json` / `jetson_manifest.json` / `readiness_output.json`，SHA `78fbf36`；`2026-06-03-first-trusted-face/` 已被取代，僅作歷史）
- capability-baseline spec：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)
- 文件站責任交接（黃 / 陳）：[`docs/mission/handoff_316.md`](handoff_316.md)（§2.4 / §3.3）

**建議視覺**：
- repo `docs/` 樹狀截圖（adr / runbook / benchmarks / perception 三件套）當「工程留痕」證據牆。
- 一條 benchmark 制度流程圖：Research Brief → Shortlist YAML → Benchmark → Decision，配 face YuNet 71 FPS 數據。
- baseline-evidence 真實 JSON 檔截圖（preflight / snapshot / readiness）。

**do_say**：
- 「開發過程全程留痕在 repo。」
- 「模型選型走制度化 benchmark，不是拍腦袋。」
- 「文件站正由團隊把素材組織成可瀏覽知識庫（in-progress）。」

**dont_say**：
- 「工程筆記文件站已建好可瀏覽。」（repo 內無 Astro/Starlight 骨架，網站本體 0%。）
- 「benchmark 數據是 Jetson 全套最新。」（archived 停在 2026-03-21。）
- 「nav 研究 log = 已完成導航能力。」

---

## 第 4 段：從硬體到軟體搭建（按六層講）

**本段目標**：按層級系統性展開：硬體 → Runtime → 感知 → 大腦 → 控制 → 觀察，每層講清楚做了什麼、難在哪。重點放硬體層「從零搭出來」的真實感，並把每層的能力宣稱綁回 scoreboard 狀態。

**報告人**：盧

**要放的內容重點（六層）**：
- **硬體層（從零搭出來）**：Jetson Orin Nano 8GB（老師提供 $249）掛 Go2 背上吃 28.8V 電池、外接 RPLIDAR A2M12 + D435 + USB 麥克風 / 喇叭；自行解供電（自製 DC-DC 降壓鏈）、固定（3D 列印背板 + 螺絲）、座標校正（鋼尺量 + 物理錨定）、通訊繞道（Ethernet 避 OTA、USB 音訊繞 Megaphone 16kHz）。
- **Runtime 層**：ROS2 Humble + colcon 多套件、WSL → Jetson rsync + colcon build 部署流程、topic schema contract 驗證（`pawai contract check`）、事件驅動 JSON topic 契約。
- **感知層**：face（YuNet + SFace, CPU）、object（YOLO26n ONNX + TensorRT FP16, GPU）、gesture（Gesture Recognizer, CPU）、pose（MediaPipe, CPU）、ASR（SenseVoice / Whisper）——五路感知 event 上 Brain。
- **大腦層**：LLM（gpt-5.4-mini 主線）+ memory（記住名字）+ policy（9 項 skill allowlist 閘控）+ safety（SafetyLayer hard rule + validate）+ skills contract。Brain 三層 Safety → Policy → Expression 在程式上對應明確。
- **控制層 + 觀察層**：interaction_executive（state machine 單一動作出口）→ Go2 action（WebRTC DataChannel）+ TTS（edge_tts / Gemini）；PawAI Studio（ChatPanel + brain trace chip + Live feed）做即時觀察。每層的能力宣稱都綁 scoreboard：pass 才進 Brain 控制，否則只顯示。

> ⚠️ **config drift 提醒（給盧 + 全組）**：`vision_perception.yaml` 預設值是 `gesture_backend: "rtmpose"` / `pose_backend: "rtmpose"`（檔案第 22-23 行）。demo 實際跑的 `recognizer` / `mediapipe` 是 `start_full_demo_tmux.sh:165` 的 **launch override**。報告講 backend 時以 **demo 啟動腳本為真相來源**，不要照 yaml 講，也別現場改錯 yaml。

**可引用的 repo 證據與數據**：
- 硬體上機 / 供電不穩 / 雙平台架構 / Jetson 操作要點：`CLAUDE.md`
- RPLIDAR 整合上機：[`docs/archive/navigation-legacy/research/2026-04-25-rplidar-a2m12-integration-log.md`](../navigation/research/2026-04-25-rplidar-a2m12-integration-log.md)
- LiDAR 座標校正：[`docs/archive/navigation-legacy/research/2026-04-29-mount-measurement.md`](../navigation/research/2026-04-29-mount-measurement.md)
- 六層全套 13-window 啟動：[`scripts/start_full_demo_tmux.sh`](../../scripts/start_full_demo_tmux.sh)
- 大腦三層對應 + Brain/Executive 分工：[`docs/archive/pawai-brain-legacy/architecture-0511/brain/brain.md`](../pawai-brain/architecture/0511/brain/brain.md)
- Safety 層程式碼：[`interaction_executive/interaction_executive/safety_layer.py`](../../interaction_executive/interaction_executive/safety_layer.py)
- 觀察層真實 ROS→WS 橋：[`pawai-studio/gateway/studio_gateway.py`](../../pawai-studio/gateway/studio_gateway.py)

**建議視覺**：
- 系統硬體拓撲圖：Go2（載具 / 電池）→ 自製 DC-DC 降壓鏈 → Jetson → 旁掛 RPLIDAR（3D 列印背板螺絲固定）+ D435 + USB 麥克風 / 喇叭，每元件標一行「難題 + 人工解法」。
- 六層堆疊圖（硬體 / Runtime / 感知 / 大腦 / 控制 / 觀察），每層標主要元件 + 該層能力的 scoreboard 狀態（pass / insufficient_data）。

**do_say**：
- 「這套外掛硬體 + 感知 + 安全堆疊是我們從零整合到 Go2 上。」
- 「感知全在 Jetson 邊緣端即時跑。」
- 「控制走 interaction_executive 單一出口，能力 pass 才放行。」

**dont_say**：
- 「把現成機器人接 AI。」（我們是從硬體改裝做起。）
- 「每層都已完整驗證可靠。」（綁 scoreboard 狀態。）
- 「D435 能做避障。」（4/3 已停用。）

---

## 第 5 段：工程挑戰與突破（老師想聽的重點，挑 4 個，這段最厚）

**本段目標**：放足工程深度。挑四個 AI 代勞不了、必須真工程的硬骨頭，每個用「痛點 → 根因 → 人工解法 → 程式 / 數據背書」四段講透。這是全報告技術含金量最高的一段。

**報告人**：盧（硬體挑戰 ①②）+ Roy（系統挑戰 ③④）

---

### 挑戰 ① Go2 非原生開發平台（供電 / SDK / 網路 / 控制介面）— 報告人：盧

- **痛點**：供電 8+ 次燒板斷電（4/29 十分鐘跳 3 次）。
- **根因**：Go2 馬達瞬間電流尖峰造成 XL4015 輸出電壓塌陷、Jetson DC jack 欠壓關機。
- **人工解法**：硬體換板 XL4015 → 2464 升降壓恒壓恒流模組（含過流 / 過壓 / 過溫保護）。加上 Go2 sport mode「cmd_vel=0 不會停車」硬體陷阱（MIN_X 0.50 m/s），driver 改成 zero → StopMove（api_id=1003）。
- **程式 / 數據背書**：driver routing 有 11 條 unit test 背書。
- **收斂**：這是 AI 寫不出來、必須人到現場換零件調限流的工程。
- **repo 證據**：
  - 系統限制（供電 / 麥克風 / Megaphone / LiDAR）：[`docs/deliverables/thesis/5-系統限制與可行性分析.md`](../deliverables/thesis/5-系統限制與可行性分析.md)
  - cmd_vel=0 不停車 + StopMove 修正 + 11 unit test：`CLAUDE.md`（§Go2 sport mode）

> ⚠️ **誠實 caveat**：供電「根因仍在（Go2 馬達電流尖峰），2464 只是緩解 + 人工監控」，不可講「已徹底根治」。

---

### 挑戰 ② Jetson 邊緣資源受限（8GB 統一記憶體同時跑模型 + ROS2 + 感測器）— 報告人：盧

- **痛點**：8GB 統一記憶體要同時跑模型 + ROS2 + 感測器。
- **根因**：ARM 生態碎片化（ultralytics 破壞 ARM PyTorch、mediapipe 無官方 ARM wheel、onnxruntime-gpu 需 Jetson AI Lab 特殊 index、setuptools 必須 <70）。
- **人工解法**：分配 CPU（face / pose / gesture）+ GPU（object TensorRT FP16）。
- **數據背書**：三感知壓測 60s PASS（RAM 1.2GB / 52°C / GPU 0%）、保留 ≥0.8GB 餘量。
- **repo 證據**：
  - Jetson 記憶體預算 / setuptools<70 / ARM 生態陷阱：`CLAUDE.md`
  - Jetson 25W / Go2 電池供電 / ARM 碎片化：[`docs/deliverables/thesis/背景知識/4-9-Jetson.md`](../deliverables/thesis/背景知識/4-9-Jetson.md)

> ⚠️ **誠實 caveat**：三感知壓測 PASS 是 face+pose+gesture **CPU**，**不含 object GPU + 三路 video**。6/18 demo 形態（三路 debug_image + langgraph + ASR 同跑）的 RAM 餘量尚未實機 smoke 驗過——這是 demo 前必做的 open question，不可講「全模組同跑已驗證穩定」。

---

### 挑戰 ③ AI 不能直接控制機器人 → 加 Brain / policy / safety gate — 報告人：Roy

- **痛點**：LLM 自然度高，但不能讓它直接控制 15-20kg 的機器狗。
- **根因 / 設計**：危險動作（翻跟斗 / 後空翻 / 倒立）拒絕是 **100% rule-based 硬編碼**（`SafetyLayer.unsafe_request` 關鍵字字面比對），**完全不經 LLM**；LLM 提案受 9 項 allowlist 閘控、生不出 motion api_id。
- **人工解法（雙層 fail-closed）**：`validate()` 攔 banned_api（backflip → api_id=1301 ∈ BANNED_API_IDS）+ executor `_dispatch_step()` 執行前再攔一次；世界狀態預設 `nav_ready` / `depth_clear=False`（publisher 沉默就當不可用）。
- **程式 / 數據背書**：整條安全鏈 91 個 unit test 全綠。
- **repo 證據**：
  - rule-based 拒絕 + fail-closed 雙層 + 91 test：[`interaction_executive/interaction_executive/safety_layer.py`](../../interaction_executive/interaction_executive/safety_layer.py) + [`interaction_executive/test/test_safety_layer.py`](../../interaction_executive/test/test_safety_layer.py)
  - 9 項 LLM allowlist 單源真相：[`pawai_brain/pawai_brain/nodes/skill_policy_gate.py`](../../pawai_brain/pawai_brain/nodes/skill_policy_gate.py)

> ⚠️ **誠實 caveat**：(a) 拒絕是「關鍵字比對」**非 LLM 判斷**；(b) 只覆蓋 5 組硬編碼關鍵字、**非通用危險動作偵測**；(c) backflip 是 demo-only 假動作（Go2 sport mode 本就沒這能力），**不可暗示「本來想做被擋」**；(d) 91 test 是 pure-Python，**真機 Go2+Jetson 端到端 BLOCKED 從未錄過**（屬 HITL Batch 4）——只能說「邏輯 + 91 test + Studio 即時顯示」，不可說「實機端到端驗證過」。

---

### 挑戰 ④ Demo 不能只靠感覺 → preflight / baseline observer / scoreboard / fail-closed — 報告人：Roy

- **痛點**：怎麼證明「能力可靠」而不是「看起來會動」。
- **設計**：可靠度由 **preflight → observer → JSONL → build_scoreboard → frozen snapshot → pawai readiness** 這條可重現工程鏈路量化產出。
- **誠實層在運作**：6/04 量到 face / object.cup / voice.command **窄版 pass**、`voice.stop` / `gesture.wave` **fail**——系統就誠實把 fail 標 fail、`readiness=not_ready`（正確 fail-closed，因 voice.stop / gesture.wave fail + nav / brain 未量），而非過度宣稱。**拿真正的 fail（voice.stop / gesture.wave）當誠實層範例**，這是「誠實度即可信度」的工程化。
- **程式 / 數據背書**：
  - 6/04 trusted snapshot（face/object.cup/voice.command pass、voice.stop/gesture.wave fail、其餘 insufficient_data、readiness=not_ready）：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（SHA `78fbf36`）
  - scoreboard 分級 + readiness 硬擋：[`benchmarks/core/scoreboard_schema.py`](../../benchmarks/core/scoreboard_schema.py) + [`benchmarks/core/readiness.py`](../../benchmarks/core/readiness.py)
  - canonical claim 真相源：[`docs/mission/2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md)（`2026-06-03-first-trusted-face/` 已被取代，僅作歷史）

> ⚠️ **誠實 caveat（重要，QA 會問）**：6/04 那份 trusted snapshot readiness verdict=`not_ready`（正確 fail-closed），但 snapshot `wsl_dirty=true` / `jetson_dirty=true` 是**未追蹤檔案存在（slide PDF / `.tmp/`），非追蹤碼變更**；clean tracked-tree commit 為 SHA `78fbf36`。**口徑必帶**：「這是可信量測（非乾淨 release freeze），證據全程留痕在 repo」，並準備好說明下次 freeze 會附 `git status --short` 或從乾淨 checkout 重跑。（6/03 那份舊 readiness 第一條 reason 曾是 `schema_validator_unavailable`，已被 6/04 取代，不再是現況。）

---

**挑戰段收斂**：這四個挑戰的共同點是「真實機器人系統工程裡 AI 代勞不了的部分」——供電要換零件、資源要手動分配、控制要加確定性 gate、可靠度要量測。

**建議視覺**：
- 挑戰 ① 時間線圖：4/29 十分鐘跳電 3 次 → XL4015 vs 2464 模組實物對比照。
- 挑戰 ② 資源分配圖：CPU（face/pose/gesture）+ GPU（object）+ 三感知壓測 60s 數據卡（RAM 1.2GB / 52°C）。
- 挑戰 ③ 安全 gate 雙層 fail-closed 流程圖（語音 → unsafe_request → 雙 plan → validate reject → executor 再攔）。
- 挑戰 ④ scoreboard 工程鏈路圖（preflight → observer → JSONL → build_scoreboard → frozen snapshot → readiness）+ 91 test 綠燈截圖。

**do_say**：
- 「供電是 AI 寫不出來、必須人到現場換零件調限流的工程。」
- 「危險動作拒絕純 rule-based、完全不經 LLM。」
- 「LLM 生不出 motion api_id，執行層再攔一次。」
- 「可靠度是量出來的：voice.stop / gesture.wave 量到 fail，系統就誠實標 fail、readiness 仍 not_ready。」

**dont_say**：
- 「LLM 判斷這是危險動作所以拒絕。」（是關鍵字比對，非 LLM。）
- 「這是通用危險動作偵測。」（只覆蓋 5 組硬編碼關鍵字。）
- 「供電問題已徹底根治。」（根因仍在，是緩解。）
- 「這段 BLOCKED 已在真機端到端錄過。」（目前是 pure-Python test 綠燈。）

---

## 第 6 段：實機展示（放在工程路線後，當「驗證工程成果」）

**本段目標**：把實機展示定位成「驗證工程成果」。錨在有強實機背書的互動 70% 主線（face / 語音 / 物體 / 手勢姿勢 / Studio / 安全拒絕），每個鏡頭配 Studio trace 背書。**nav 嚴格只講目前接線與 dry-run 邊界、不做任何真實自走、不口頭宣稱。**

**報告人**：Roy（主持 demo）+ 盧（硬體段補述）

**展示流程指向**：以 [`docs/mission/demo-scope.md`](demo-scope.md) 與 [`scripts/start_full_demo_tmux.sh`](../../scripts/start_full_demo_tmux.sh) 為當天系統形態的真相來源；canonical 9 步故事見 North Star §6。

**要放的內容重點**：
- **最穩閉環（純互動主線、強實機背書）**：
  1. 人臉認出註冊者 → 主動守望語氣問候（5/8 實機 PASS、2 分鐘 21 次穩定鎖定）。
  2. 固定語音指令 → Brain → TTS（連續 5+ 輪不 crash、stop/safety bypass LLM）。
  3. 揮手 / 比 OK → 回應（wave_hello api 1016 真機 PASS）。
  4. 桌上杯子 → 辨識 + 顏色提醒（demo 硬鎖 cup-only `class_whitelist=[41,999]`；object.cup 6/04 窄版 pass：~1m 近距、n=7、recall=1.0、idle 0 誤觸；**僅近距 ~1m，2m 未驗**）。
  5. 全程 Studio 顯示每步 evidence。
- **安全拒絕 BLOCKED 視覺化（差異化亮點）**：對 PawAI 說「請翻跟斗」→ TTS 講「這個動作不安全，我不能執行」+ Studio chat-panel 同步出現紅色 badge「request_backflip · blocked_by_safety · banned_api:1301」。證明危險指令在 rule-based Safety 層被攔、LLM 從頭沒機會生成、執行層 validate 再擋一次。
- **Studio thinking trace（差異化主秀）**：dev mode 開 Conversation Trace 面板，同一句輸入逐條跑 `safety_gate → capability → llm_decision → verifier → skill_gate → output` 色票流——「不只是 chatbot、有決策與安全閘」。
- **nav 鐵律（North Star §7，嚴守邊界）**：nav.safe_stop / no_auto_resume 在 baseline 標 pass 前一律 insufficient_data。前置鎖 F7（goal accept 但 controller 完全不發 `/cmd_vel_nav`、no_progress ABORT）未在 fresh stack 定位。**所以 demo nav 預設只走純 Studio / Foxglove 顯示**：(a) 顯示 LiDAR `/scan_rplidar` 點雲 + depth + map（「系統在邊緣端感知環境」）。真實 motion 屬 stretch goal，**不列入 baseline 排練流程**——只有 F7 在 fresh stack 確認不復現 + 供電穩 + e-stop + Roy 旁站時，才人工 override 短距 0.3m 單次（明說單次、家裡、未經 baseline 重現）。**絕不做連續自走 / 繞障 / 多 goal。**
- **拍攝紀律**：每個鏡頭旁邊一定要有 Studio trace 或 debug image 對照（North Star §6 硬前提）；手勢距離 1.3-3m、單人入鏡；全程 `enable_fallen:=false` 不觸發任何跌倒 / 陌生人語句。

**可引用的 repo 證據與數據**：
- canonical 9 步故事 + nav 鐵律：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（§6、§7）
- demo 範圍（導航避障停用、come_here 停用、手勢 stop 為主停止、Studio Gateway 網頁語音）：[`docs/mission/demo-scope.md`](demo-scope.md)
- demo 當天系統形態（`enable_fallen:=false` / gesture recognizer / object YOLO26n / langgraph）：[`scripts/start_full_demo_tmux.sh`](../../scripts/start_full_demo_tmux.sh)
- cup-only 白名單：[`object_perception/config/object_perception.yaml`](../../object_perception/config/object_perception.yaml)
- 翻跟斗 BLOCKED 雙 plan + 端到端 reject test：[`interaction_executive/interaction_executive/safety_layer.py`](../../interaction_executive/interaction_executive/safety_layer.py) + [`interaction_executive/test/test_safety_layer.py`](../../interaction_executive/test/test_safety_layer.py)
- 紅色 blocked_by_safety badge：[`pawai-studio/frontend/components/chat/chat-panel.tsx`](../../pawai-studio/frontend/components/chat/chat-panel.tsx)
- F7 demo blocker root cause 未定位：[`docs/archive/navigation-legacy/research/2026-05-11-nav-avoidance-deep-research.md`](../navigation/research/2026-05-11-nav-avoidance-deep-research.md)
- 5/12 night goto_relative 0.3m 誤差 0.2mm、0.5m 在 danger 0.81m 停（唯一一次性 motion 證據）：[`references/project-status.md`](../../references/project-status.md)

> ⚠️ **Studio scoreboard 主畫面誠實修正（reviewer must-fix）**：前端**沒有任何元件 fetch `/api/scoreboard`**（gateway 有 endpoint 在 line 600，但 UI 上不存在 scoreboard pass/fail chip 牆）。開場 / 證據主畫面**不要承諾螢幕有 scoreboard LED**，改用 **dev trace GateChip + 直接秀 git-tracked baseline-evidence JSON 檔**為 primary，旁白講「我們的量測證據全程留痕在 repo」。

**建議視覺**：
- 互動主線 demo 動線 storyboard（認人 → 問候 → 語音 → 手勢 → 杯子 → Studio），每格標對應 ROS topic / debug image。
- 翻跟斗 BLOCKED 三連拍：語音輸入 → TTS 拒絕 → Studio 紅色 banned_api:1301 badge。
- Studio dev mode Conversation Trace 色票流截圖（safety_gate → capability → llm_decision → verifier → skill_gate → output）。
- nav dry-run 蒙太奇：Foxglove 同畫面 LiDAR `/scan_rplidar` 點雲 + D435 depth + home map（旁白只講「在邊緣感知環境」）。

**do_say**：
- 「這些是已在真機跑通的工程成果。」
- 「危險指令進到系統，機器人也不可能真的翻——因為 Go2 本來就沒有翻跟斗這個動作，我們造一個被禁的 api 來示範安全層怎麼攔。」
- 「nav 目前只展示邊緣感知與接線，安全停車尚未達 pass、不做真實自走。」
- 「被問可靠嗎就指 scoreboard 證據。」

**dont_say**：
- 「人臉辨識通用可靠 / 能拒絕陌生人 / 2m+ 可靠 / 不會認錯人。」（6/04 是窄版 pass：僅註冊者 Roy 一人、idle 空景、真實陌生人未測——只可講「能認出已註冊的人並問候」。）
- 「安全停車已完成 / 停了不會自己衝。」（現行 reactive_stop 是 auto-resume，行為衝突未修。）
- 「成功走完 0.5m。」（實際走 0.41m 撞 danger 停。）
- 「機器狗會自己走過去 / 自動找人 / 巡邏 / 動態繞障。」
- 「通用物體辨識 / 認得 80 種物件。」（demo 鎖 cup-only。）
- 「偵測到跌倒。」（`enable_fallen:=false`，禁說跌倒偵測。）
- 「螢幕上有 scoreboard pass/fail 燈號。」（前端無此 UI。）

---

## 第 7 段：應用場景（最後才講，用守望框架收斂）

**本段目標**：在誠實展示完工程成果後，才談應用想像。分近 / 中 / 長期三級，全部用「守望」語言、標清楚哪些是已驗證能力延伸、哪些是設計意圖未驗證。**巡檢標為延伸場景，非現況。** 最後收斂成一句定位。

**報告人**：Roy（收尾）

**要放的內容重點**：
- **近期（最貼近已驗證能力）**：機構單人**互動提醒**——基於已跑通的人臉認人問候 + 語音對話 + 物件提醒 + Studio evidence 這條互動主線，做「到現場看一眼、認得人、提醒一句、回報到 Studio」。**單人巡檢標為延伸**：互動主線是基礎，巡檢（需移動到多點）依賴 nav，屬延伸。
- **中期（需 nav baseline pass 後解鎖，延伸場景）**：門口巡檢 / 環境巡檢——需要 `nav.safe_stop` / `no_auto_resume` 先在 baseline 標 pass（目前 insufficient_data）；標明這是「安全層 pass 後才放行的中期目標」，非現況。
- **長期（設計動機，明確標未驗證）**：弱勢輔助——借鑑導盲犬的「非接觸守望價值」作為設計動機，但**不宣稱導盲能力**；斷網守望目前只是設計意圖未驗證。
- **用詞紀律（North Star §5）**：全程「守望 / 提醒 / 回報 / 非接觸」。每談一個場景都標清楚是「已驗證能力延伸」還是「設計意圖」。
- **收斂一句**：PawAI 是「先到現場看一眼、理解狀況、提醒與回報」的非接觸式守望助理（巡檢為延伸場景）。

**可引用的 repo 證據與數據**：
- 定位 / 禁說清單 / 斷網守望=設計意圖未驗證：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（§2、§5、§10）
- 非接觸守望 POC 定位：[`docs/adr/0001-pawai-2026-06-poc-non-contact-positioning.md`](../adr/0001-pawai-2026-06-poc-non-contact-positioning.md)
- 互動 70% / 守望 30% 專案方向：[`docs/mission/README.md`](README.md)
- 各能力 claim_level / nav target 但 pass 前 insufficient_data：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)

**建議視覺**：
- 近 / 中 / 長期三級時間軸圖，每級標「已驗證能力延伸」或「設計意圖未驗證」色標；巡檢明確掛在「中期 / 延伸」格。
- 收斂一句定位的全螢幕標語頁：「先到現場看一眼、理解狀況、提醒與回報的非接觸式守望助理」。

**do_say**：
- 「近期 = 機構單人互動提醒（基於已跑通互動主線）。」
- 「中期 = 門口 / 環境巡檢（延伸場景，需 nav baseline pass 後解鎖）。」
- 「長期 = 弱勢輔助（設計動機，借鑑導盲犬非接觸守望價值）。」
- 「PawAI 是『先到現場看一眼、理解狀況、提醒與回報』的非接觸式守望助理。」

**dont_say**：
- 「已能巡邏整個機構 / 自動找人 / 跟隨人 / 導盲。」
- 「長照可靠 / 保護長者 / 守護。」
- 「斷網守望已成立。」（只是設計意圖未驗證。）
- 「把中長期目標講成現況。」

---

## 附錄 A：報告人分工總表

| 段 | 主題 | 報告人 | 備註 |
|---|---|---|---|
| 0 | 敘事主軸 + Before/After | Roy | 開場，建立誠實基調 |
| 1 | PawAI 是什麼 | Roy | 一句定位 + 六格定位圖 |
| 2 | 工程路線總覽（大圖）| Roy | 主視覺架構圖 |
| 3 | 工程筆記網站（亮點）| Roy（或文件站組員代述）| 誠實標 in-progress |
| 4 | 從硬體到軟體搭建（六層）| **盧** | 硬體層「從零搭出來」 |
| 5 ① | 挑戰：Go2 非原生平台 / 供電 | **盧** | 硬體挑戰 |
| 5 ② | 挑戰：Jetson 資源受限 | **盧** | 硬體 / 資源挑戰 |
| 5 ③ | 挑戰：AI 不能直接控制 / safety gate | Roy | 系統挑戰 |
| 5 ④ | 挑戰：preflight / scoreboard / fail-closed | Roy | 系統挑戰 |
| 6 | 實機展示（驗證成果）| Roy 主持 + 盧 硬體段補述 | nav 只講 dry-run 邊界 |
| 7 | 應用場景（守望框架收斂）| Roy | 收尾 |

---

## 附錄 B：QA 可能被問 + 建議答法

> 取自三輪審查（Linus 技術審查 / 教授 QA 模擬 / Demo 風險稽核）的 qa_traps。**標準答法的核心：誠實揭露 > 過度宣稱；被問可靠度一律指證據。** 旁白團隊請逐條背熟。

| # | 可能被問 | 陷阱 | 建議答法 |
|---|---|---|---|
| 1 | 你說 scoreboard 是主角，螢幕哪個元件顯示每能力 pass/fail 燈號？ | 前端無 scoreboard chip 元件 | 「目前是 frozen JSON 證據檔 + dev trace gate chip，pass/fail LED 是後端規劃中、前端尚無 consumer。」不含糊帶過。 |
| 2 | face 你秀它認出 Roy 叫名字，這有量過嗎？是 pass 嗎？ | 窄版 pass 易被擴張成「通用可靠」 | 「6/04 量到**窄版 pass**（n=9, recall=1.0, false-accept=0.0），所以 chip 標 pass、demo 秀的是認出已註冊的人並問候；但**僅單一註冊者 Roy / idle 空景 / 真實陌生人未測**——所以不宣稱拒絕陌生人、不宣稱不會認錯人、不宣稱守護。」 |
| 3 | face 認錯人的機率多少？會不會把陌生人當成 Roy？ | 把窄版 pass 講成「不會認錯」 | 誠實答「6/04 n=9 下 registered_recall=1.0、unknown_false_accept=0.0，但 idle 只測過空景、**沒拿真實陌生人臉測過**，所以我們不宣稱『不會認錯人』也不宣稱能拒絕陌生人；擴張邊界要靠 #81 乾淨重跑（≥2 註冊者 + 真陌生人樣本）。」 |
| 4 | 今天哪些能力真的 pass？哪些 fail？ | 逼問能力分級 | 「6/04 量到 **3 項窄版 pass**（認已註冊 Roy / ~1m 近距杯子 / 固定語音指令 0.875）+ **2 項 fail**（voice.stop 0.667、揮手 recall 0.0）+ 其餘 insufficient_data；readiness 仍 `not_ready`，是因為安全關鍵的 voice.stop / nav 未過——這正是 fail-closed 與誠實層的價值，不是缺陷。」 |
| 5 | 你說遇人會安全停車，停下後障礙移開它會自己往前嗎？ | 致命：現行 reactive_stop 是 auto-resume | 「現行 reactive_stop 是 auto-resume 行為，no_auto_resume 是待重設計的目標，所以我們今天不做真實自走、只示意停下。」**絕不說「停了不會自己衝」。** |
| 6 | request_backflip——Go2 本來會翻跟斗，是你們禁掉的嗎？ | 暗示系統原本支援 | 「Go2 sport mode 本就沒有翻跟斗動作，api_id=1301 是我們為了走 reject 流程刻意造的 demo-only 假動作，不是禁掉既有能力。」 |
| 7 | 同義詞測試：我說「給我來個空中翻滾」會不會也被擋紅燈？ | 純字面比對，同義詞不觸發 | 「紅色視覺化是指定關鍵字觸發的示範；但 LLM allowlist 9 項不含任何 backflip skill，同義詞即使不亮紅燈也一樣無法被執行。」區分「視覺化觸發」與「實際執行防護」兩層。 |
| 8 | 你跑的是真 gateway 還是 mock？mock_server 也會顯示 blocked_by_safety。 | 兩者前端畫面相同 | 現場指出啟動的是 `studio_gateway` 真 rclpy node，並能秀真實 `ros2 topic echo /brain/skill_result` 佐證。 |
| 9 | 翻跟斗被擋是真機試過、還是只有單元測試？ | 91 test 是 pure-Python 無真機 | 「規則 + 91 test 背書 + Studio 紅標可見；真機 Go2+Jetson 端到端整段今天現場才串，屬 HITL Batch 4。」明確區分「邏輯驗證 vs 實機端到端」。 |
| 10 | F7 那個 nav bug 定位了嗎？怎麼保證 demo 當天 Go2 會動？ | F7 至今無修復紀錄 | 「所以移動段預設不做真實自走，只做純感知顯示；真實 0.3m motion 只在 dry-run 通過 + Roy 旁站 e-stop 才做。」 |
| 11 | 你這份量測快照在哪台機器、什麼狀態下跑的？乾淨嗎？ | wsl_dirty / jetson_dirty=true | 「6/04 trusted snapshot，clean tracked-tree commit SHA `78fbf36`；dirty flag 是**未追蹤的 slide PDF / `.tmp/`，不是追蹤碼變更**，sha-gate 能擋 version_mismatch。這是可信量測、非乾淨 release freeze，下次 freeze 會附 `git status --short` 或從乾淨 checkout 重跑。」 |
| 12 | 第 7 段那 12 步思考流是真的每次跑出來、還是錄好的？跟一般 chatbot 差在哪？ | 需走 langgraph 非 legacy brain_node | 確認 demo 走 langgraph 引擎（`start_full_demo_tmux.sh` 預設 CONVERSATION_ENGINE=langgraph），現場 dev mode 即時跑出 safety_gate → capability → llm_decision → verifier → skill_gate → output。 |
| 13 | 你說全在 Jetson 邊緣跑，斷網還能守望嗎？ | 斷網守望是設計意圖未驗證 | 「斷網守望目前只是設計意圖，North Star §10 明禁當已成立證據；現行語音主線仍走 Cloud path。」 |
| 14 | 物件辨識為什麼只認杯子？只會認杯子、還是關掉了別的？ | cup-only 是刻意硬鎖 | 「demo 刻意只開驗證範圍內的杯子這一類（`class_whitelist=[41,999]`），不是『只能認杯子』；通用物體辨識在禁說清單。」 |
| 15 | wave 的 confidence 怎麼算的？ | code 裡 hardcode 1.0 | 誠實答「目前 confidence 是固定值、無鑑別力，這正是它還沒 pass 的原因，鑑別力要靠 baseline 補。」 |
| 16 | 這個機器狗 demo 全程它有自己走過嗎？還是都你們搬的？ | nav 零自走是刻意的 | 「安全停車與自走還沒 pass，所以今天不讓它自己走——這是安全紀律不是做不到。」把限制講成負責任。 |

---

## 附錄 C：demo 前必做前置鎖（給 Roy，避免某段排練順口升級成「已 pass」）

1. **頂層前提鎖**：依 6/04 HITL trusted snapshot，face / object.cup / voice.command 為**窄版 pass**——可講「認出已註冊 Roy」「~1m 近距杯子」「固定語音指令分類」，但一律綁窄版邊界（不擴張到通用 / 拒絕陌生人 / 2m+ / 安全停車）；gesture.wave / voice.stop 為 **fail**（誠實標 fail，camera 動態 wave 不演、voice.stop 不當安全停車）；nav / pose / brain / studio 為 `insufficient_data`（只顯示不宣稱）。若 6/18 前再跑出新 pass，再依升級規則放寬旁白。
2. **nav 移動段預設 = 純 Studio / Foxglove 顯示零實機 motion**；真實 0.3m goto_relative 降為「dry-run 通過 + F7 fresh stack 不復現 + Roy 旁站 e-stop」的 stretch goal，不列入 baseline 排練。
3. **scoreboard 開場主畫面 = baseline-evidence JSON + dev trace GateChip**（非承諾 scoreboard chip UI，前端無此元件）。
4. **config 真相來源 = `start_full_demo_tmux.sh`**（recognizer/mediapipe 來自 launch override，非 `vision_perception.yaml`，該檔是 rtmpose）；確認跑的是 demo 腳本而非裸 launch 或 nav stack 腳本。
5. **object_perception 硬前置**：demo 前確認在 demo entrypoint 真起且有 consumer 訂 `/event/object_detected`，否則第 6 段杯子段連「鏈路在跑」都秀不出。
6. **voice 輸入層**：demo 前實測 ASR 對 5 組 unsafe keyword + 核心指令的辨識率（純字面比對無同音容錯，ASR 聽錯則 rule 不命中、紅色 BLOCKED 不出現）。
