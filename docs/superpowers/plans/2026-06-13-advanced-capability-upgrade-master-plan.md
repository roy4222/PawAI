# PawAI Advanced Capability Upgrade — Master Plan（進階能力升級層統領 + Evidence/Benchmark cross-cutting）

> **日期**：2026-06-13（六）　**狀態**：PLANNED — 待 Roy 審核，審核通過前不實作、不改 runtime、不改 demo flow、不碰任何既有檔案
> **作者 lane**：Cloud B（Advanced Capability Upgrade Plan）　**硬底線**：2026-06-18 期末發表
>
> **上游連結（引用，不重抄內文）**：
> - 既有 aggressive 套件（本份是其「如果時間足夠」的進階補充層，不取代）：[`2026-06-13-aggressive-pre618-master-plan.md`](2026-06-13-aggressive-pre618-master-plan.md)（北極星、B-1~B-10、6/17 回穩日、fallback 三層、demo snapshot 凍結）
> - current baseline：[`docs/runbook/2026-06-13-post-refactor-acceptance-report.md`](../../runbook/2026-06-13-post-refactor-acceptance-report.md)（軟體 95% / pre-6/18 ~63% / 北極星 ~33%；HITL #2 Task3 nav 撞牆 NOT_DEMO_READY）
> - nav capability ladder：[`docs/navigation/2026-06-13-nav-capability-ladder.md`](../../navigation/2026-06-13-nav-capability-ladder.md)（C1-C12）、claim wording：[`2026-06-13-nav-618-claim-wording.md`](../../navigation/2026-06-13-nav-618-claim-wording.md)（F1-F10）
> - 五份 domain plan（全部讀過，本份統領）：
>   - [Vision / Object Model A-B](2026-06-13-advanced-vision-model-ab-plan.md)（A1-A9）
>   - [Gesture / Pose](2026-06-13-advanced-gesture-pose-plan.md)（G1-G3 / P1-P3）
>   - [Navigation Capability](2026-06-13-advanced-navigation-capability-plan.md)（A1-A10，nav 版）
>   - [Voice Fast-Path](2026-06-13-advanced-voice-fast-path-plan.md)（V1-V8）
>   - [Security / Control Hardening](2026-06-13-advanced-security-control-hardening-plan.md)（§2.1-§2.10）

---

## 這份是什麼

這是 **PawAI Advanced Capability Upgrade track 的統領 master**——把五份 domain plan（vision / gesture-pose / nav / voice / security）收進一張全域能力地圖，並**獨家處理研究方向 6（Evidence / Benchmark cross-cutting）**（無獨立檔案，在本份 §4 統一規劃）。回答四個統領問題：

1. 這個 advanced track 與 **Cloud A（保守 demo flow 可靠度）**、**既有 lane1-6（已排程 aggressive refactor）** 的三方分界在哪？
2. 跨五領域的 proven / needs_hitl / research_only **誠實能力地圖**長怎樣？
3. 什麼條件才 **maybe 進 6/18 demo runtime**（Gate）？
4. **Roy 稀缺時段**（純軟體 AFK / Jetson / Go2 HITL）怎麼配，才不與既有 HITL #1/#2、B-3 矩陣日、B-9 nav 場測撞時段？

## 這份不是什麼

- **不取代既有 aggressive master**：[`2026-06-13-aggressive-pre618-master-plan.md`](2026-06-13-aggressive-pre618-master-plan.md) 的北極星、依賴閘門、B-1~B-10、6/17 回穩日、fallback 三層、demo snapshot 凍結**持續有效**；本份只在其「如果時間足夠才測的進階能力層」之上加一層決策框架，引用既有 B 系列用編號。
- **不與 Cloud A 搶主線**：phase conductor / offline fallback / demo 當天可靠度全歸 Cloud A；凡屬 demo flow 可靠度的能力，逐條標「歸 Cloud A，本計畫不重複」。
- **不重抄既有 lane1-6 plan**：lane1-6 = 已排程的 aggressive refactor；本份 advanced plan = 在其之上「如果時間足夠才測的進階能力」。引用既有 lane 用連結，不複製內文。
- **不是 runtime 行為真相**：runtime 行為以 code / topic schema / acceptance report 為準；本份是「成熟度敘事 + 升級路徑 + 進 runtime 決策框架」。
- **零 runtime diff（本 track 鐵則）**：6/18 前所有 advanced sub-capability 的預設輸出都是「不換 runtime」（B-4）；唯一例外是已被五份 plan 標 proven 且 byte-identical 的 bugfix（security route_id sanitize，見 §5 Gate）。

---

## §1 North Star 與三方定位

### 1.1 北極星（不變，引用 v2 master）

> **把 PawAI 從「demo 拼裝系統」重構成安全、可觀測、可擴展、可部署、可驗證的具身 AI 機器狗平台。**
> 本 advanced track 對北極星的貢獻 = **把每個能力的真實成熟度量化、講清楚邊界、留下可溯源證據**——不是把能力做到「全部完成」，而是讓 6/18 發表「講得出哪裡 proven、哪裡只是 research、為什麼不換模型」都有數據背書。

### 1.2 三方分界（advanced track ↔ Cloud A ↔ 既有 lane1-6）

| 軸 | 既有 lane1-6（aggressive refactor，已排程） | Cloud A（保守 demo flow 可靠度） | **本 advanced track（Cloud B）** |
|---|---|---|---|
| **定位** | 把 Brain/Studio/CLI/Vision/Security/Nav 推到「現時間內可達最高版本」的實作 | demo 當天「五幕怎麼演、斷網怎麼退、可靠度」 | 「如果時間足夠才測的進階能力 + 換不換的決策框架 + evidence/benchmark」 |
| **產出** | code merged + 單測綠（lane1-6 task） | phase conductor / offline fallback / demo snapshot | 5 份 domain plan 的 spike 數據 + 分級 + Gate + 本份 evidence/benchmark cross-cutting |
| **runtime 變更** | flag-gated 行為變更（預設 = 現行為，可翻） | 不新增能力，只編排 | **零 runtime diff**（除 byte-identical bugfix） |
| **誰拍板** | Roy 審 lane plan + HITL | Roy 定 demo 腳本 + fallback 層 | Roy 審本 track + 決定 maybe 項是否進 runtime（AB 決策） |

**邊界鐵則**：
1. 凡屬「demo 當天 nav/voice/vision 那一幕怎麼演、斷網退路、五幕指揮」→ **歸 Cloud A，本 track 不重複**（五份 plan 已逐條標註）。
2. 凡屬「已排程的 lane task 實作步驟（W1-W7 spike / T6-1~T6-10 / T5S-1~T5S-9 / N1-N8 / ISM stage 2a-2d）」→ **權威在既有 lane plan**，本 track 引用編號做決策、不重抄。
3. advanced track 的價值 = 在 lane 數據出來後「換不換、進不進 runtime、claim 升到哪級」的**進階裁決層** + evidence/benchmark cross-cutting。

### 1.3 NO OVERCLAIM 統領紀律（全 track + 全 domain 生效）

- 四分級強制：**proven / needs_hitl / research_only / do_not_claim_by_618**，與 nav ladder C1-C12、claim wording F1-F10、acceptance baseline 完全一致。
- **單次成功 ≠ 可靠**（需 n=3）；**safe-stop ≠ 繞障**（nav F2/C11，object 對應「物體偵測 ≠ 物體觸發移動」）。
- 任何 benchmark proven 的是**方法論 / 穩定度數字**，**不是能力 pass**（gesture.wave 仍 fail、pose.basic 仍 insufficient、fallen 仍 future、cup 仍 CLAIM_WITH_CAVEAT、nav 短距未 n=3 不單獨宣稱）。
- 數字 / 路徑 / 模型名 / threshold 全部來自實際讀到的來源文件；不確定標「需 Roy 指認 / 待量測」。

---

## §2 跨領域 P0/P1/P2 統整總表（五份 plan 全收）

> 收齊五份 domain plan 的所有 sub-capability。`task_type`：pure_software / jetson_needed / go2_motion_needed / mixed。`before_monday`：純軟體本週末可跑完=yes、需 Jetson/Roy 時段=maybe、research only=no。`enter_runtime`：6/18 demo runtime。

| 領域 | # | 能力 | 分級 | P | task_type | before_monday | enter_runtime |
|---|---|---|---|:---:|---|:---:|:---:|
| **Vision** | A1 | YOLO26n→26s 換模 A/B（640） | needs_hitl | P1 | mixed | maybe | no |
| Vision | A2 | n@960 / 高解析輸入（720p 真像素） | needs_hitl | P1 | mixed | maybe | no |
| Vision | A3 | tiling / crop（SAHI offline） | research_only | P2 | pure_software | no | no |
| Vision | A4 | cup/bottle/phone 類別混淆降低（核心痛點） | needs_hitl | P0 | mixed | yes | no |
| Vision | A5 | chair/laptop/bottle 進 pool（YOLOE vocab38） | needs_hitl | P1 | mixed | yes | no |
| Vision | A6 | HSV12→Lab-LUT 色彩命名 | needs_hitl | P1 | mixed | yes | no |
| Vision | A7 | supervision metrics / confusion / video evidence | proven | P0 | pure_software | yes | no（永久 offline） |
| Vision | A8 | PINTO 候選池（478_SC/LVFace/AdaFace） | research_only | P2 | mixed | maybe | no |
| Vision | A9 | 最終換模決策框架 | proven | P0 | pure_software | yes | no |
| **Gesture** | G1 | Gesture model alternatives（YOLO 死路終裁） | do_not_claim_by_618 | P2 | pure_software | no | no |
| Gesture | G2 | Gesture false-trigger benchmark（ROC 掃描） | proven | P0 | pure_software | yes | no |
| Gesture | G3 | thumbs_up/peace/OK 靜態手勢穩定度 | needs_hitl | P1 | mixed | maybe | no |
| **Pose** | P1 | sitting/standing confidence calibration | needs_hitl | P1 | mixed | maybe | no |
| Pose | P2 | bending/fallen demo-safe 風險評估 | do_not_claim_by_618 | P0 | pure_software | yes | no |
| Pose | P3 | Pose model A/B（MediaPipe/RTMPose/YOLO26n-pose） | research_only | P1 | pure_software | maybe | no |
| **Nav** | NV-A1 | short goto 0.3/0.5/1.0m（n=3）[C1/C2/C3] | needs_hitl | P1 | go2_motion_needed | maybe | maybe |
| Nav | NV-A2 | safe-stop margin（只停不轉）[C4] | proven | P0 | mixed | yes | yes |
| Nav | NV-A3 | stop-resume / operator-confirm [C5] | needs_hitl | P1 | mixed | maybe | maybe |
| Nav | NV-A4 | named poses / routes 恢復 [C10] | needs_hitl | P0 | go2_motion_needed | maybe | maybe |
| Nav | NV-A5 | route patrol prototype（單圈）[C9] | research_only | P1 | go2_motion_needed | maybe | no |
| Nav | NV-A6 | approach Roy / person（spec only，F6）[C12] | research_only | P2 | pure_software | no | no |
| Nav | NV-A7 | D435+LiDAR fusion→costmap（F3）[C12] | research_only | P2 | pure_software | no | no |
| Nav | NV-A8 | local costmap / DWB / true detour [C11] | do_not_claim_by_618 | P2 | pure_software | no | no |
| Nav | NV-A9 | 不掃圖直走（straight + safe-stop + evidence）[C4+C1] | needs_hitl | P1 | mixed | maybe | maybe |
| Nav | NV-A10 | AMCL initialpose 朝向校正 SOP（6/13 撞牆根因）[C7] | needs_hitl | P0 | mixed | yes | yes |
| **Voice** | V1 | ASR anti-hallucination（黑名單擴充） | proven | P0 | pure_software | yes | no |
| Voice | V2 | VAD threshold tuning（2-10s 瓶頸） | needs_hitl | P1 | jetson_needed | maybe | maybe |
| Voice | V3 | demo 指令 rule-based fast path | proven | P0 | pure_software | yes | maybe |
| Voice | V4 | 小模型 intent classifier 可行性 | research_only | P2 | pure_software | no | no |
| Voice | V5 | Cloud LLM vs local rule engine routing | proven | P1 | pure_software | yes | maybe |
| Voice | V6 | Local TTS / pre-render phrase pack | needs_hitl | P0 | mixed | yes | maybe |
| Voice | V7 | TTS ack / request_id（播放確認回路） | needs_hitl | P1 | mixed | maybe | no |
| Voice | V8 | Interrupt / cancel speaking | research_only | P2 | jetson_needed | no | no |
| **Security** | S1 | gateway auth secure-default（B-6） | needs_hitl | P1 | mixed | maybe | maybe |
| Security | S2 | Foxglove clientPublish 降權（B-5） | needs_hitl | P1 | mixed | no | maybe |
| Security | S3 | /webrtc_req whitelist enforcement flip | needs_hitl | P1 | jetson_needed | no | no |
| Security | S4 | forbidden API driver-level block（blacklist） | proven | P0 | pure_software | yes | maybe |
| Security | S5 | nav action auth（interface 級，post-6/18） | research_only | P2 | go2_motion_needed | no | no |
| Security | S6 | DDS domain isolation / SROS2 feasibility | research_only | P2 | jetson_needed | no | no |
| Security | S7 | cmd_vel / mux ownership boundary | research_only | P2 | go2_motion_needed | no | no |
| Security | S8 | route_id sanitize（注入防護） | proven | P0 | pure_software | yes | **yes** |
| Security | S9 | security smoke 擴充 | proven | P0 | pure_software | yes | n/a |
| Security | S10 | emergency stop / hold brake policy | needs_hitl | P1 | go2_motion_needed | no | maybe |

**全表計數**：43 sub-capability。分級分佈 = proven 10 / needs_hitl 19 / research_only 11 / do_not_claim_by_618 3。

> ⚠️ 命名消歧：nav 版 plan 自己也用 A1-A10 編號；本 master 為避免與 vision A1-A9 撞號，nav 一律前綴 **NV-**。引用 nav 能力時連帶 ladder C 編號。

---

## §3 三分類全域盤點（誠實能力地圖）

> 對外發表「我們有什麼」時，只能用 proven 一欄背書；needs_hitl 一律帶「待真機/n=3」；research_only 只能講「有 spec、屬研究」；do_not_claim_by_618 一律不提。

### 3.1 `proven`（純軟體可定案 / 已有真機證據，但仍受 §5 Gate 約束才進 runtime）

| 能力 | proven 的精準邊界（防誤讀） |
|---|---|
| Vision A7 supervision evidence | proven 的是「離線 metrics/confusion/video evidence 工具鏈可用」；**永不進 Jetson runtime** |
| Vision A9 決策框架 | proven 的是「換模決策框架 + 觸發條件成文」；預設輸出就是「6/18 不換」 |
| Gesture G2 誤觸 benchmark | proven 的是「誤觸 ROC 方法論 + 現役值誤觸數字」；**不是** gesture.wave/靜態手勢能力 pass |
| Pose P2 fallen demo-safe | proven 的是「不演跌倒的證據鏈鎖死」；`enable_fallen:=false` 維持現役，對外絕不提跌倒 |
| Nav NV-A2 safe-stop margin | proven = ladder C4 `HARDWARE_PROVEN_WITH_LIMIT`（trackB 多次 0 撞 0 暴衝）；**必明講 safe-stop 不是繞障** |
| Voice V1 ASR anti-hallucination | proven 的是「黑名單防線量化 + 擴充」；延遲類數字全為開發期 proxy，不可宣稱語音延遲 |
| Voice V3 rule-based fast path | proven 的是「常用指令繞 LLM 的純函式路由」；come_here 永不接 motion（F6） |
| Voice V5 LLM↔rule routing | proven 的是「決策表 + 純函式單測」（等價重構，byte-identical） |
| Security S4 forbidden blacklist | proven 的是「driver 層拒 3 條 BANNED 的機制 + 單測封閉」；**enforcement flip 是否打開仍受 Gate** |
| Security S8 route_id sanitize | proven = 純軟體 bugfix、合法輸入 byte-identical；**唯一可確定進 runtime 的 enforced 變更** |
| Security S9 security smoke | proven = 滲透斷言可重跑；測試工具不進 runtime（n/a） |

### 3.2 `needs_hitl`（機制/鏈路在，增益或升級必須真機量）

Vision A1/A2/A4/A5/A6（上機矩陣裁定）；Gesture G3、Pose P1（demo 距離 n=3 / pose observer）；Nav NV-A1/A3/A4/A9/A10（全 motion HITL，A10 是其餘的硬前置）；Voice V2/V6/V7（VAD 量測 / pre-render 載入 / ack 回路）；Security S1/S2/S3/S10（enforcement flip 彩排 / foxglove 降權 / whitelist 動作回歸 / 急停彩排）。

**共同鐵則**：未過 HITL（或未達 n=3）一律不升 proven、不對外宣稱；HITL FAIL 不連坐其他格（ladder §6）。

### 3.3 `research_only` / `do_not_claim_by_618`（只落 spec / 永久禁制）

| 級別 | 能力 | 6/18 措辭 |
|---|---|---|
| research_only | Vision A3 SAHI、A8 PINTO（LVFace non-commercial 掛旗）；Pose P3；Nav NV-A5 patrol v0 / NV-A6 approach / NV-A7 fusion；Voice V4 / V8；Security S5 / S6 / S7 | 最多講「有 spike 數據 / 有 spec，屬研究路線」；approach=F6 禁、fusion=F3 禁 |
| do_not_claim_by_618 | Gesture G1（YOLO 死路終裁）；Pose P2（fallen 不演）；Nav NV-A8（free roam / dynamic detour，F1/F2 永遠禁） | 對外一律不提（G1 防重啟討論、P2 防誤講守護、NV-A8 防誤講自主繞障） |

### 3.4 跨領域張力與依賴（單一 plan 看不到、master 才能盤點）

> 五份 domain plan 各自封閉；以下是**跨 domain 的衝突 / 依賴 / 共用前置**，只有 master 層能盤點，必須在審 plan 時一併裁決。

| 張力 / 依賴 | 涉及 domain | 衝突點 | master 裁決方向 |
|---|---|---|---|
| **降混淆 vs 加類別** | Vision A4 ↔ A5 | open-vocab 加細粒度容器類（藥瓶/水瓶/馬克杯）會**升** cup↔bottle 混淆，與 A4 降混淆目標直接衝突 | Roy 定 demo 主軸（AB-1）；A4 優先則 A5 容器擴充砍 |
| **GPU 預算競爭** | Vision（object）↔ Pose（P3 YOLO-pose） | 同上機矩陣日 GPU 讓給 object（synthesis §2 #4），pose 換線排「下下次上機」非 B-3 | 6/18 前 pose 不上機；P3 純離線取捨表 |
| **RAM 8GB 互斥** | Nav（nav stack）↔ Brain（demo stack）↔ Vision（s@960） | nav stack 與 brain demo 8GB 互斥（獨立時段）；s@960 RAM 邊緣 +300~600MB | nav 走 B-9 獨立時段；s@960 違反 0.8GB 即棄測（EB-4 仲裁） |
| **素材共用 / 單一 blocker** | Vision A1/A4/A7 ↔ Gesture G2 ↔ Pose P1/P3 | 全部 block 在同一個 B-8 素材指認（demo 錄影 + object JSONL 路徑） | EB-1/EB-2 統一收齊；無則順延補錄、不 block 其他 lane |
| **VAD 邊際效益** | Voice V2 ↔ demo 收音路徑 | 若 demo 走 Studio 筆電 mic（繞 VAD），V2 VAD tuning 邊際效益低 | AB-8 先定收音路徑，再決定 V2 做不做 |
| **face 換模 vs re-enroll** | Vision A8 ↔ acceptance §4 | face 辨識失敗主因是 enrollment 漂移**非模型** → 換模可能是錯方向 | AB-6：6/18 走 re-enroll 不換模；LVFace/AdaFace 留 post-6/18 |
| **foxglove 降權 vs nav initialpose** | Security S2 ↔ Nav NV-A10/C7 | foxglove clientPublish 降權會斷「nav initialpose-via-Foxglove」工作流 | 發表不開 Foxglove + Studio `/api/nav/initialpose` 實機驗過才降權（B-5） |
| **nav 授權 vs nav 能力** | Security（S5/S8）↔ Nav（NV-A1~A10） | Security 只碰「誰能命令 nav」（授權/消毒），nav 能力 claim 全歸 ladder | 嚴格分界：S8 route_id 消毒可進 runtime、nav 能力 claim 對齊 C1-C12 |
| **NV-A10 是 motion 總前置** | Nav NV-A1/A4/A5/A9 全依賴 NV-A10 | 6/13 撞牆根因＝initialpose 朝向不準；未校正前所有 motion 重測必再撞 | NV-A10 朝向校正 SOP 是 B-9 開場儀式，過了才往下測 |

---

## §4 Evidence / Benchmark cross-cutting（研究方向 6，無獨立檔案，本份統一處理）

> 這是「把分散在五份 plan 的證據/量測工作」收斂成一條 cross-cutting 軸，避免每份 plan 各自造輪。每項標 task_type + P 級 + before_monday + 上游歸屬。

### 4.1 Cross-cutting 任務總表

| # | Evidence/Benchmark 項 | task_type | P | before_monday | 上游歸屬（不重做） | 產物 |
|---|---|:---:|:---:|---|---|---|
| **EB-1** | object JSONL dataset（cup/phone/bottle 混淆矩陣源） | pure_software | P0 | yes（需 Roy 指認路徑） | Vision A1/A4/A7、lane4 W4/B-8 | 重建 `sv.Detections` + ConfusionMatrix CSV |
| **EB-2** | gesture/pose benchmark clips（誤觸 / sitting GT） | pure_software | P0 | yes（需 Roy 指認 S2/S3 takes） | Gesture G2、Pose P1/P3 | ROC CSV + sitting precision/recall |
| **EB-3** | nav HITL dataset（短距 n=3 / safe-stop margin） | go2_motion_needed | P1 | maybe（掛 B-9） | Nav NV-A1/A2、ladder N3/N8 | 每發 cov/actual/朝向/結果記錄表 |
| **EB-4** | FPS/CPU/GPU/RAM/temperature profiler | jetson_needed | P1 | maybe（掛 B-3） | Vision A1-A6、Pose P3、lane4 T0-T6 | tegrastats 仲裁表（RAM 口徑統一） |
| **EB-5** | replayable demo sessions（trace + annotated MP4） | pure_software | P0 | yes | Vision A7、Lane 2 Evidence Center | bbox+zh label+track MP4 + JSONL decision_id |
| **EB-6** | model comparison reports（每線 GO/NO_GO） | pure_software | P0 | yes | Vision A9、Gesture G1、Pose P3、lane4 V3 | research docs 回填 + verdict |
| **EB-7** | benchmark scoreboard（cup@distance / pose / nav 入帳） | pure_software | P1 | yes | acceptance §4、6/4 trusted snapshot | scoreboard 數字可溯源 |
| **EB-8** | capability ladder auto-update（HITL 後回填） | pure_software | P1 | n/a（HITL 後觸發） | nav ladder §6 維護規則、claim matrix | label 升/降級回填 + claim wording 同步 |

### 4.2 Cross-cutting 鐵則

1. **demo 錄影絕不餵 LLM**（量測輸入非理解輸入，lane4 §1）——EB-1/EB-2/EB-5 全部離線 replay。
2. **supervision 絕不進 Jetson runtime**（雙份 OpenCV 共存違反 ≥0.8GB 紀律）——EB-1/EB-5 全在 WSL 獨立 venv。
3. **scoreboard 取兩者中較保守者**：6/4 trusted snapshot nav 四能力全 `insufficient_data`（n=0），本 track 的 trackB/6-9 HITL 是人工觀測證據、尚未回灌自動 trusted 流程；EB-7/EB-8 回填前，對外 claim 與 scoreboard 一律取較保守（nav ladder §5）。
4. **RAM 口徑分歧待仲裁**：goal1（activation 全包）vs goal2（engine 邊際）對 s@960 差 3-4 倍——EB-4 在 T4/T5 tegrastats 一次性仲裁後寫成 benchmark 慣例（待 Roy 拍 AB-4）。
5. **單次成功 ≠ 可靠**：EB-3 nav 短距、EB-2 sitting precision 全部要求 n≥3 / n≥10；未達不下強結論。

### 4.3 Evidence/Benchmark 與既有工具的關係

- **不新造輪**：Lane 2 Studio Evidence Center（trace_store / export / report / viewer）是 EB-5 的 runtime 端上游；EB-5 只補「離線 annotated MP4 + ConfusionMatrix」的 WSL 端。
- **量測口徑沿用** `capture_baseline_round.py percep` + topic 隔離（6/4 坑：object 用 `--gesture-topic /__no_gesture__`、gesture 用 `--object-topic /__no_object__`）。
- **profiler 沿用** tegrastats / jtop；EB-4 唯一新增 = 把 nvpmodel power mode（÷1.4-1.7 修正係數）寫進每份 FPS 報告抬頭（待 AB-2 供電決策）。

### 4.4 逐項 Evidence/Benchmark 分析（cross-cutting 6 是無獨立檔案的研究方向，在此展開）

> 每項：目的 / 來源素材 / 產出 / pass-fail / 風險 / rollback。凡引用既有 lane W/T 項者執行權威在該 lane，本份只做 cross-cutting 收斂。

**EB-1 — object JSONL dataset（混淆矩陣源）** ｜ pure_software P0 ｜ before_monday yes（block 在 B-8 素材指認）
- **目的**：把 acceptance §4 的「cup 持續被認成 cell_phone/bottle」（0.7m phone 4/bottle 2、1.5m phone 6/bottle 4）從軼事變 ConfusionMatrix；餵 Vision A4 降混淆裁決與 A9 決策框架。
- **來源素材**：demo 錄影（6/9-6/10 S2/S3，**絕不餵 LLM**）+ `/event/object_detected` JSONL（路徑需 Roy 指認，B-8）。
- **產出**：WSL 獨立 venv `sv.Detections` 重建 → `sv.metrics.ConfusionMatrix`（cup/phone/bottle 雙向）CSV，per 距離 per 配置。
- **pass-fail**：decision_id join 可行 + ConfusionMatrix 可重跑（紀錄性，不設換線門檻）；6-8Hz 下 ByteTrack track 不嚴重斷裂則時序壓混淆路線可行、否則 runtime 路線 NO_GO 維持 offline-only。
- **風險 / rollback**：素材不足 → 標方向性參考不下強結論；WSL venv `git status` 乾淨 → 無 rollback。

**EB-2 — gesture/pose benchmark clips（誤觸 / sitting GT）** ｜ pure_software P0 ｜ before_monday yes（block 在 B-8）
- **目的**：Gesture G2 誤觸 ROC（把「0.7×3 零 spam」印象變數字）+ Pose P1 sitting/standing precision（pose.basic 升 pass 前置）+ P3 三方取捨表。
- **來源素材**：demo 錄影非手勢段（誤觸分母）+ 手勢段（漏觸分母）+ S2 坐姿段（sitting GT，與 lane4 W5 共用）。
- **產出**：min_conf × min_votes × stable_s ROC CSV + 誤觸來源歸因（palm↔ok 混淆 / 過渡幀 / 背景手）+ sitting precision/recall（vs 人工 GT，n≥10 需 pose observer）。
- **pass-fail**：現役值（0.7×3×0.5）誤觸有數字 + ROC 落點明確；sitting precision ≥0.8 @ n≥10 才可標「two-class demo 距離可用（窄版）」，否則維持 insufficient_data。
- **風險 / rollback**：腳本層重放 vote/stable 邏輯須與 runtime 常數對拍（加單測）；全離線 additive → 無 rollback。

**EB-3 — nav HITL dataset（短距 n=3 / safe-stop margin）** ｜ go2_motion_needed P1 ｜ before_monday maybe（掛 B-9）
- **目的**：把 nav 從「短距能走（單次）+ safe-stop（多次但無結構化記錄）」升到可溯源 n=3 數據集；餵 ladder N3/N8 升級與 claim wording S1/S2。
- **來源素材**：B-9 nav 場測真機（NV-A10 朝向校正過後）；每發記 covariance / actual_distance / 朝向偏移角 / 結果（reached/abort/撞）；錄 `/cmd_vel_nav` angular.z + `/amcl_pose` yaw 供歪斜根因鎖定（H1 步態 60% / H2 DWB 30% / H3 TF 10%）。
- **產出**：0.3m × n=3、0.5m × n=3 記錄表 + safe-stop margin 量化表（danger 距離 vs 機鼻 buffer vs 速度 vs 反應時間）。
- **pass-fail**：0.3/0.5m × 3 全 reached + 0 撞 → C1/C2 升 demo_ready 候選；任一撞 = 該距離 FAIL 當日不再試（abort 條 1/5）；1.0m 需 N2 進 green 才測（大概率排不上，F8 禁講）。
- **風險 / rollback**：6/13 已撞一次牆，NV-A10 未過前重測仍撞；現場 emergency_stop engage 中止；FAIL 不連坐、proven table 照實標。

**EB-4 — FPS/CPU/GPU/RAM/temperature profiler** ｜ jetson_needed P1 ｜ before_monday maybe（掛 B-3）
- **目的**：給 Vision 換模 A/B 與 Pose 換線提供統一資源量測；解決 RAM 估算口徑分歧（AB-4）。
- **來源素材**：B-3 上機矩陣日 tegrastats / jtop；每配置（A0 control / s@640 / n@960 / s@960）量 RAM delta、Hz、溫度。
- **產出**：tegrastats 仲裁表（goal1 activation 全包 vs goal2 engine 邊際，一次性裁定寫成 benchmark 慣例）+ 每份 FPS 報告抬頭標 nvpmodel power mode（÷1.4-1.7 修正）。
- **pass-fail**：每配置 RAM 餘 ≥0.8GB（T4 s@960 違反即棄測）+ Hz ≥3 + 溫度 <75°C。
- **風險 / rollback**：供電不穩（XL4015→2464，常駐 Super 檔功耗上升，AB-2 待裁）；TRT engine drift 前科 → 燒完必過 sanity；當日還原現役 + smoke。

**EB-5 — replayable demo sessions（trace + annotated MP4）** ｜ pure_software P0 ｜ before_monday yes
- **目的**：產出 Studio 等級 annotated evidence MP4（bbox + zh 標籤 + track ID）+ trace replay，供發表展示「機器當下看到什麼」；是 Lane 2 Evidence Center 的離線上游。
- **來源素材**：demo 錄影 + object JSONL（同 EB-1）；trace JSONL（gateway trace_store，acceptance §2 已驗 export/report）。
- **產出**：supervision VideoSink MP4（zh label + ByteTrack）+ JSONSink（`custom_data` 塞 decision_id 可 join trace）。
- **pass-fail**：MP4 bbox+zh label+track 穩定可見 + JSONL decision_id join 可行（spike gate；evidence 價值獨立於 ByteTrack 是否斷裂）。
- **風險 / rollback**：誤把 supervision 裝進 Jetson（明令禁止，永久 offline）；WSL 獨立 venv → 無 rollback。

**EB-6 — model comparison reports（每線 GO/NO_GO）** ｜ pure_software P0 ｜ before_monday yes
- **目的**：每線（換模 / 高解析 / open-vocab / 色彩 / pose 換線 / gesture YOLO）寫回 verdict，防懸空、防「順手換」越界。
- **來源素材**：A1-A6 上機數字 + W replay 數據 + 既有 research docs。
- **產出**：每線 GO/NO_GO 回填 research docs（lane4 V3）+ 矩陣勝者宣告；Gesture G1 終裁表（YOLO 死路，防重啟討論）+ Pose P3 取捨表。
- **pass-fail**：無懸空 verdict + 每條觸發條件可逐條對上數據 or forbidden claims。
- **風險 / rollback**：上機日若 post-6/18，只有 W replay 數據（仍真數據）；純文件 → 無 rollback。

**EB-7 — benchmark scoreboard（cup@distance / pose / nav 入帳）** ｜ pure_software P1 ｜ before_monday yes
- **目的**：把 cup@distance、pose precision、nav 能力數字進 scoreboard，對外 claim 可溯源。
- **來源素材**：acceptance §4 baseline + EB-1/EB-2/EB-3 數據 + 6/4 trusted snapshot。
- **產出**：scoreboard 數字可溯源；nav 在 scoreboard 層維持 `insufficient_data` 直到 HITL 回灌（取較保守）。
- **pass-fail**：cup@distance 數字可溯源 + scoreboard 與對外 claim 取兩者較保守者一致。
- **風險 / rollback**：build_scoreboard 必 WSL（記憶坑）；純數據 → 無 rollback。

**EB-8 — capability ladder auto-update（HITL 後回填）** ｜ pure_software P1 ｜ before_monday n/a（HITL 後觸發）
- **目的**：把 HITL 結果回填 ladder label + claim wording，保持 golden source 一致。
- **來源素材**：EB-3 nav HITL 結果 + ladder §6 維護規則。
- **產出**：label 升/降級回填 ladder §2/§3 + claim wording 對應句同步；FAIL 不連坐。
- **pass-fail**：每次升級有「日期 + 文件路徑級證據」（無證據不准比現在更高 label）。
- **風險 / rollback**：6/13 撞牆後 C1 caveat 回填屬 golden-source ladder 範疇（非本 master 直接改）；純文件 → 無 rollback。

---

## §5 進入 6/18 demo runtime 的決策流程（Gate）

### 5.1 預設姿態（B-4 繼承）

> **6/18 前換 runtime 模型/參數的預設答案 = 不換。** 43 個 sub-capability 中，預設輸出全部是「6/18 不換 / 維持現役 / shadow 收數據」。

### 5.2 進 runtime 的硬 Gate（全部滿足才 maybe）

任一能力 maybe 進 6/18 runtime，必須**同時**滿足：

1. **benchmark 明顯贏**（相對 baseline 有可溯源數字證明增益，非單次、非印象）；
2. **latency / 資源可接受**（FPS ≥ 門檻、RAM 餘 ≥0.8GB、溫度 <75°C、無 demo pipeline 回歸）；
3. **HITL 過**（真機驗證，n=3 或對應 N 項 PASS）；
4. **有秒級 rollback**（env / param flag，off = byte-identical 已驗）；
5. **Roy 點頭**（對應 AB / B 決策）。

### 5.3 maybe 項的 Gate 現況（六個 maybe-enter-runtime）

| 能力 | 卡在哪個 Gate | 6/17 回穩日決策依據 |
|---|---|---|
| Nav NV-A2 safe-stop | 已 proven（C4）+ 已 enter=yes；**唯一以 nav 能力本體 proven 進 runtime 的**（NV-A10 的 enter=yes 是定位操作儀式、非能力本體） | 配 §3 標準說法（safe-stop 不是繞障），fallback 各層都用得到 |
| Nav NV-A10 initialpose SOP | 已 enter=yes（motion 必走前置儀式） | 純軟體 SOP + 真機校正一輪；不講「可靠收斂」 |
| Nav NV-A1/A3/A9/A4 | Gate 3（HITL）——全卡在 NV-A10 朝向校正先過 | A10 過 + n=3 0 撞才升；否則退 fallback ②③ |
| Voice V3/V5/V6 | Gate 1-2 已備（純函式 / pre-render）；Gate 5（Roy）+ 6/17 彩排逐項 | 預設不併；回穩日視彩排決定（AB-5） |
| Security S1（auth flip） | Gate 3（T5S-8 彩排）+ Gate 5（B-6） | 彩排全綠才 on，否則 default-off |
| Security S4（blacklist） | Gate 3（動作回歸零誤殺）+ Gate 5（Roy 點頭） | 零誤殺 + 點頭才 maybe 翻 enforced |
| Security S2（foxglove 降權） | Gate 5（B-5）+ initialpose 替代驗證 | 發表不開 Foxglove + Studio initialpose 驗過才降權 |
| **Security S8 route_id** | **全 Gate 已過**（純軟體 bugfix、byte-identical） | **唯一可確定進 runtime 的 enforced 變更** |

### 5.4 永不進 runtime（硬編碼）

Vision A7 supervision（永久 offline）；所有 research_only（spec only）；所有 do_not_claim_by_618；Security S5/S6/S7（post-6/18 全鏈 rebuild / 安全鏈本體）。

---

## §6 Roy 時段預算（與既有 master HITL #1/#2 + B-3/B-9 對齊，不另開衝突時段）

> 既有 aggressive master §5 已定：固定兩晚 HITL（#1、#2，各 ~2h，demo lane）+ 兩個可選大時段（**B-3 上機矩陣日**、**B-9 nav 場測**，建議至多選一提前）。本 track **所有 Jetson/Go2 task 掛這些既有時段，不另開**。

### 6.1 桶 1 — Pure software AFK（不需 Roy，本週末可平行跑）

> 唯一前置 = Roy 指認素材路徑（EB-1/EB-2，無則順延補錄、不 block 其他 lane）。

| 來源 | AFK 可做項 |
|---|---|
| Vision | A7 supervision evidence（W4）、A9 決策框架、A4 混淆對照（W1/W4）、A6 色彩 spike（W3）、A2 高解析誠實標註、A8 478_SC 離線（W5）、A3 SAHI（餘力） |
| Gesture/Pose | G2 誤觸 ROC、G1 終裁表、P2 fallen 裁定、G3/P1 離線 confusion/剖析、P3 取捨表（依賴 W5） |
| Nav | NV-A10 SOP 文件、NV-A2 margin 量化表、NV-A9 不掃圖直走可行性文件、引用 Lane 6 純軟體項 |
| Voice | V1 黑名單擴充、V3 fast-path 純函式、V5 routing 決策表、V6 phrase pack 預渲染（軟體部分） |
| Security | S8 route_id sanitize、S4 blacklist 機制、S9 security_smoke 擴充、S1 token wiring（軟體部分）、S10 文件債（不碰凍結三檔）、S5/S6/S7 spec 草擬 |
| Evidence | EB-1/EB-2/EB-5/EB-6/EB-7（全離線） |

### 6.2 桶 2 — Jetson needed（無 Go2 motion，掛 B-3 矩陣日或 Jetson 短時段）

| 來源 | 掛哪 | 項 |
|---|---|---|
| Vision | **B-3 上機矩陣日** | A1/A2/A4/A5 上機裁決（T1-T5）、A6 色彩 54 格 bag（T6）、A7 不上機（永久 offline） |
| Pose | Jetson 短時段（~30min，無 motion） | P1 建 pose observer（T-P1-3，pose.basic 升 pass 硬前置）、G3 Jetson 觀測 conf |
| Voice | Jetson（HITL #1/#2 順帶） | V2 VAD 量測（需真機 mic）、V6 pre-render 載入驗證 |
| Security | **HITL #2（6/15 晚）** | S1 auth-on 彩排（T5S-8）、S9 security_smoke 真機跑、S2 foxglove 降權驗證 |
| Evidence | 掛 B-3 | EB-4 profiler（tegrastats RAM 仲裁） |

### 6.3 桶 3 — Go2 motion needed（需 e-stop + 淨空 + Roy 在場，掛 B-9 nav 場測）

| 來源 | 掛哪 | 項（依賴序） |
|---|---|---|
| Nav | **B-9 nav 場測**（nav stack 與 brain demo 8GB 互斥，獨立時段） | NV-A10 initialpose 校正（開場儀式）→ NV-A2 safe-stop N8 + NV-A1 短距 n=3 → NV-A9 不掃圖直走 → NV-A4/A5 poses+patrol（stretch，時間不夠先砍） |
| Gesture | 併 Cloud A confirm 彩排（不單獨佔時） | G3 peace→OK→WeGo n=3（confirm flow 編排歸 Cloud A，本 track 只供穩定度數據） |
| Security | 併 B-9 或動作回歸時段 | S4 blacklist-on 零誤殺（低風險）、S10 急停彩排；S3 whitelist-on / S5/S7 = post-6/18 |

> **B-3 vs B-9 二選一張力**：四天內兩個大時段都排非常硬。aggressive master 建議至多選一個提前——**nav 場測（B-9）對 6/18 直接價值較高**（poses 不重錄則 route/goto_named 全空轉、nav 段只能影片 fallback），但 **6/13 撞牆後 nav motion 全段壓回 NOT_DEMO_READY**，B-9 排不排取決於 NV-A10 朝向校正先過。Vision 上機矩陣日（B-3）若 post-6/18，A1/A2/A5/A6 只有 WSL replay 數據（仍是真數據、可講能力邊界）。

### 6.4 B-3 / B-9 排程決策樹（給 Roy 一頁看完該排哪個）

```
6/15-16 至多選一個大時段（aggressive master §5）
│
├─ 若 NV-A10 朝向校正 SOP（純軟體，週末做完）看起來可行
│   └─ 排 B-9 nav 場測（半天）
│       ├─ 開場 NV-A10 真機校正一輪 → goto 0.3m 暖身
│       │   ├─ 0 撞 → 往下測 NV-A2 safe-stop N8 + NV-A1 短距 n=3（EB-3）
│       │   │         → 時間有餘才 NV-A9 不掃圖直走 / NV-A4-A5 patrol（stretch）
│       │   └─ 仍撞 → 當日所有 motion abort；nav 段退 fallback ③純影片（S1 已錄）
│       └─ Vision A1/A2/A5/A6 只能 WSL replay 數據（仍可講能力邊界，no 上機裁定）
│
└─ 若 nav motion 風險評估太高（NV-A10 不穩 / e-stop / 淨空條件不足）
    └─ 排 B-3 上機矩陣日（半天～全天）
        ├─ Vision A1/A2/A4/A5 上機裁決（T1-T5）+ A6 色彩 bag（T6）+ EB-4 profiler
        ├─ Pose / Gesture 不上機（GPU 讓 object；G3/G2 用離線數據）
        └─ nav 段全走 fallback ③純影片（S1 已錄），EB-3 順延 post-6/18
```

**master 建議**：兩個 SOP/評估文件（NV-A10、NV-A9、Vision W replay）週末全做完，**6/15 才依純軟體結果二選一**——若 NV-A10 校正看起來可行則排 B-9（nav 對 6/18 故事價值最高），否則排 B-3（vision 數據趕發表）。**B-10 nav 段發表形態**（live 短距 / 遙控輔助+Studio 證據 / 純影片）在 6/17 回穩日依 B-9 結果定，不預設。

---

## §7 全域 Rollback 原則

| 層級 | 原則 | 時效 |
|---|---|---|
| **純軟體文件 / 離線 spike** | additive、WSL 獨立 venv、素材/模型/CSV/MP4 不進 git、`git status` 乾淨 → **無東西需 rollback**；腳本入 repo 過 blocking flake8（max-line 100） | n/a |
| **runtime flag（若 maybe 翻）** | 一律 env/param-gated 預設關 = byte-identical（已驗）；翻 default 是獨立 PR；revert 任一不連動 | 秒級 |
| **Jetson 上機（換模/換參）** | 當日結束**必還原 demo 現役配置**（n@640 / conf 0.35 / 640x480）+ `pawai smoke full`；TRT cache 按 model stem 分目錄保現役 engine 完好；測試 branch 不進 main | 當日 SOP |
| **Go2 motion HITL** | 現場可中止（`emergency_stop.py engage` mux pri 255 + StopMove / `pawai demo stop` 路由 nav cleanup）；任一 FAIL 不連坐、proven table 照實標、claim wording 對應降級 | 現場 |
| **資料項（poses/routes）** | runtime 資料非 code，錄壞重錄；`evidence pull` 異地備份（B2 bug 6/13 已修，缺失目錄優雅跳過） | 重錄 |
| **demo fallback（永備）** | 已錄影片 S1-S5 + tag `demo-2026-06-snapshot` = 發表保底，**任何 advanced 項都不得使其失效**；nav 段三層 fallback（live 短距 / 遙控輔助+Studio 證據 / 純影片）任一層都能交付 | 永備 |
| **main 壞掉** | 停新刀 → revert 最近綠 commit；最壞退 tag `post-demo-refactor-baseline-2026-06-10`（`b1f0bc4`）或 6/17 `pre-618-checkpoint` | tag |

---

## §8 與既有 master 附錄 B（B-1~B-10）的關係 + 本 track 新增決策（AB 系列）

### 8.1 引用既有 B 系列（不重新定義，只標 advanced track 的依賴）

| 既有 B 決策 | 本 track 哪些能力依賴它 |
|---|---|
| **B-3**（上機矩陣日排不排） | Vision A1/A2/A4/A5/A6、Pose P3 上機、EB-4 profiler 全掛此 |
| **B-4**（6/18 前不換 runtime） | 全 track 的 enter_runtime 預設 = no 的根據；§5 Gate 的守門人 |
| **B-5**（foxglove 降權） | Security S2 |
| **B-6**（gateway auth flip） | Security S1 |
| **B-8**（Lane 4 素材指認） | Vision A1/A4/A5/A7、Gesture G2、Pose P1/P3、EB-1/EB-2 全 block 在此 |
| **B-9**（nav 場測時段） | Nav NV-A1/A2/A4/A5/A9/A10、EB-3 全掛此 |
| **B-10**（nav 段發表形態） | Nav NV-A9 vs NV-A10 路線選擇的下游 |

### 8.2 本 advanced track 新增需 Roy 拍板的決策（AB 系列，與 B 系列並行）

| # | 決策 | 影響 | 本份建議 | 時點 |
|---|---|---|---|---|
| **AB-1** | A4（降混淆）vs A5（open-vocab 加容器類）直接張力——加細粒度容器類會升 cup↔bottle 混淆，與降混淆衝突 | Vision demo 主軸 | Roy 定 demo 主軸（純準 cup vs 多類但混淆）；若 A4 優先則 A5 容器擴充砍 | 審 plan / B-3 前 |
| **AB-2** | nvpmodel power mode / 供電（需電源側意見）——是否為 demo 常駐 Super MAXN（功耗 vs XL4015→2464 斷電前科 8+ 次） | 全部 FPS 解讀（÷1.4-1.7） | 待電源側意見；EB-4 報告抬頭標明 power mode | B-3 前 |
| **AB-3** | A10 vs A9 nav 路線（最關鍵）——6/13 撞牆後走「修 initialpose 朝向再 goto」還是「不掃圖 teleop 低速直走 + safe-stop 兜底 + Studio 證據」 | 6/18 nav 那一幕主演出形態 | 兩條都先做純軟體評估；motion 時段先驗 A10、A9 作平行 fallback ②保底（不互斥） | B-9 前 / 6/17 |
| **AB-4** | RAM 估算口徑分歧（goal1 全包 vs goal2 邊際對 s@960 差 3-4 倍）——T4/T5 tegrastats 仲裁後是否寫成 benchmark 慣例 | EB-4 / Vision A2 解讀 | 上機一次性仲裁後成文 | B-3 後 |
| **AB-5** | 6/18 前是否允許把 V1 黑名單擴充 / V5 等價重構 / V6 phrase pack 載入 / S4 blacklist / S8 route_id 併進 demo build | Voice/Security maybe 項 | 預設不併（B-4）；S8 route_id 例外（byte-identical bugfix）；其餘 6/17 回穩日視彩排逐項 | 6/17 |
| **AB-6** | face 換模方向——baseline §4 face 辨識失敗主因是 enrollment 漂移**非模型** | Vision A8 | 確認 6/18 走 re-enroll 不換模；LVFace/AdaFace（non-commercial）留 post-6/18 候選池 | 審 plan |
| **AB-7** | pose observer 是否本期建（P1 T-P1-3 是 pose.basic 升 pass 硬前置） | Pose P1、claim matrix | 若 Roy 有 Jetson 時段值得順手做（不需 Go2/e-stop）；否則 post-6/18 | B-3 / HITL |
| **AB-8** | Q1 demo 收音路徑——Studio 筆電 mic（繞 VAD）還是機上 USB mic（吃 VAD） | Voice V2 是否值得做 | 若走 Studio 收音，VAD tuning 邊際效益低，V2 可砍 | 審 plan |
| **AB-9** | contract v2.6 合併 bump 時機——色名 19+1 與 vocab 22 類兩條 GO 後合併一次 bump | Vision A5/A6 落地 | 全 post-6/18，確認 6/18 前不動 contract | 審 plan |
| **AB-10** | demo 措辭最終界線（對齊簡報）——可講近中距杯子穩定/手勢穩定/坐姿判定；不可講 phone/bottle 精準分類/可靠顏色/19 色/藥瓶鑰匙/2m/跌倒守護/自主避障/語音延遲數字 | 全 track claim | Roy 確認 claim 清單與簡報一致 | 6/17 |

### 8.3 既有 master 凍結表的繼承（不重寫，只標 advanced track 立場）

- demo snapshot forbidden claims **持續有效**；已錄影片 + tag 不可動。
- `executive.yaml` / `start_full_demo_tmux.sh` / `.claude/skills/` 採「逐改知情」（先 runtime param/env、確需改檔單獨 PR + demo smoke 全綠 + Roy 點頭）——Security S2 foxglove 降權碰 `start_full_demo_tmux.sh:274` 即走此程序。
- ISM `ism_enabled` staged enable 2a-2d 歸 Lane 1（本 advanced track 不碰 Brain ISM；引用其 off=legacy 紀律）。

---

## §9 建議執行順序（若 Roy 批准進階開發）

### 9.1 立刻可平行跑的純軟體 P0（不需 Roy、不需硬體、本週末）

> 唯一前置 = Roy 指認 EB-1/EB-2 素材（B-8）。以下全部 AFK、零 runtime diff、過 flake8、`git status` 乾淨。

1. **Security S8 route_id sanitize** — 唯一可確定進 runtime 的 byte-identical bugfix，先做掉沒理由不修。
2. **Security S9 security_smoke 擴充** + **S4 blacklist 機制**（單測封閉）。
3. **Vision A7 supervision evidence + ConfusionMatrix（EB-1/EB-5）** + **A9 決策框架**。
4. **Gesture G2 誤觸 ROC（EB-2）** + **Pose P2 fallen demo-safe 裁定**（兩條 overclaim 防線）。
5. **Nav NV-A10 initialpose 朝向校正 SOP** + **NV-A2 safe-stop margin 量化表** + **NV-A9 不掃圖直走可行性文件**（回應 6/13 撞牆 + Roy 需求）。
6. **Voice V1 黑名單擴充** + **V3 fast-path 純函式** + **V5 routing 決策表**。
7. **EB-6 model comparison reports** 隨各線數據到位回填。

### 9.2 等 Jetson 時段（B-3 矩陣日 / Jetson 短時段）

8. Vision A1/A2/A4/A5 上機裁決（T1-T5）+ A6 色彩 bag（T6）+ EB-4 profiler（B-3）。
9. Pose P1 建 pose observer（AB-7 通過 + Jetson 短時段）。
10. Security S1 auth-on 彩排 + S9 真機跑（HITL #2）。

### 9.3 等 Go2 motion 時段（B-9 nav 場測，e-stop 在場）

11. **NV-A10 initialpose 校正（開場儀式，所有 motion 前置）** → NV-A2 safe-stop N8 + NV-A1 短距 n=3（EB-3）→ NV-A9 不掃圖直走 → NV-A4/A5 patrol（stretch，先砍）。
12. Gesture G3 confirm flow n=3（併 Cloud A 彩排）。
13. Security S4 blacklist-on 零誤殺 + S10 急停彩排（併 B-9）。

### 9.4 6/17 回穩日 + post-6/18

- **6/17 回穩日**：所有 maybe-enter-runtime 項逐項決定 flag 狀態（AB-5）；未過 HITL 一律 flag-off 進發表；EB-8 ladder/claim 回填；demo 全流程 smoke 綠。
- **post-6/18**：所有換模落地（Vision A1/A2 + ADR）、contract v2.6 bump（A5/A6）、PINTO/pose 換線（A8/P3）、nav research 三條實作（NV-A6/A7 + patrol v1）、Security 三 research spec（S5/S6/S7）、auto-resume 終局（nav A-9）。

---

## §10 6/18 發表能誠實講什麼（per-domain honest claim summary）

> 把全 track 的分級收斂成「發表時每個領域能講 / 不能講」一頁——對齊老師「先量化能力再決定換不換模型」的要求，也是 §8 AB-10 措辭清單的展開。**這不是新承諾，是把五份 plan 的 proven 欄翻成簡報語言。**

| 領域 | 6/18 可講（proven / 已驗） | 6/18 必須帶 caveat（needs_hitl） | 6/18 絕不可講（research / forbidden） |
|---|---|---|---|
| **Vision/Object** | 近中距杯子穩定偵測（CLAIM_WITH_CAVEAT）；有換模決策框架 + 離線 evidence/metrics（supervision MP4） | 換模 A/B 數據（待上機）；色彩升級（離線錨點） | phone/bottle 精準分類、可靠顏色、19 色、藥瓶/鑰匙辨識、2m 可偵測、open-vocab |
| **Gesture** | peace/OK 靜態手勢 demo confirm flow（已現役）；誤觸防線是量出來的工作點（ROC） | peace/OK n=3 穩定度（demo 距離） | gesture.wave 可用、換手勢模型、palm 精準 |
| **Pose** | 坐姿判定（窄版、正面，已現役）；fallen 不演的證據鏈 | sitting precision（待 pose observer n≥10） | 跌倒偵測可靠、防跌倒守護、緊急警報、坐下偵測 pass |
| **Nav** | 正前方障礙安全停（safe-stop，C4，明講不是繞障）；定位重設操作（initialpose） | 短距 0.3-0.5m 自主移動（待 NV-A10 校正 + n=3）；停下後操作員確認續走 | 自由巡邏、動態繞障/繞行、自主找人、D435 已融合 costmap、1.0m+ 乾淨連續導航、auto-resume |
| **Voice** | ASR 防幻覺防線（黑名單）；常用指令繞 LLM 的 fast path；雲端/本地路由決策 | VAD 調優（待真機）；常用句預渲染 | 語音延遲數字（全為開發期 proxy，mic_stop 未接線）、打斷播放 |
| **Security/Control** | gateway 認證機制（401/403 已驗）；driver 層 forbidden-api block 機制；route_id 注入點已消毒；安全滲透自動化 smoke | auth-on enforcement（待彩排）；whitelist/blacklist flip（待動作回歸） | 未授權者已不能讓 Go2 動（DDS 面未收斂）；DDS 已隔離 |

**一句總結（發表敘事）**：PawAI 在 6/18 能誠實展示的是「**一台感知多模態、互動有狀態機、安全有縱深防禦、能力邊界量化清楚的居家四足具身機器人**」——每個能力都標了成熟度，換不換模型有數據框架，nav 用 capability ladder 管理宣稱，沒有任何 overclaim。**這比「假裝全部都會」更站得住，也正是老師要的「為何要機器狗 + Edge AI + 聚焦」的答案。**

---

## 附錄：與 nav ladder / claim wording / acceptance baseline 的對齊聲明

- 本 master 不重定義 nav 能力 label——一律引用 [ladder C1-C12](../../navigation/2026-06-13-nav-capability-ladder.md) 與 [claim wording F1-F10](../../navigation/2026-06-13-nav-618-claim-wording.md)；NV-A2 = C4 `HARDWARE_PROVEN_WITH_LIMIT`、NV-A1 = C1/C2/C3、NV-A10 = C7、NV-A8 = C11 `DO_NOT_CLAIM`、NV-A6/A7 = C12 spec only。
- current baseline 一律以 [acceptance report](../../runbook/2026-06-13-post-refactor-acceptance-report.md) 為準：軟體 95% / pre-6/18 ~63% / 北極星 ~33%；cup recall 距離不掉、痛點是混淆；face 失敗是 enrollment 漂移非模型；nav motion HITL #2 Task3 撞牆 = NOT_DEMO_READY。
- **NO OVERCLAIM 終裁**：本 track 任何 benchmark 數字不洗成能力 pass；對外 claim 與 scoreboard 取較保守者；單次成功 ≠ 可靠（n=3）；safe-stop ≠ 繞障；demo 措辭以 §8 AB-10 鎖定的清單為準。
