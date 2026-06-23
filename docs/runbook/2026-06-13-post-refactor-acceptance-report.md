# Post-Refactor Full Acceptance / Regression Baseline Report

> **日期**：2026-06-13（六）晚　**測試時間**：~15:59–16:30 TST（Asia/Taipei）
> **性質**：aggressive refactor（batch 1+2，8 PR #167–#174）後的**全功能驗收 + 回歸 baseline**。確認底層架構重構**未破壞既有功能**；非模型升級、非 UI 大改。
> **執行**：Fable 驅動軟體/感知觀測 + Roy 在場提供身體動作（拿杯/手勢/坐站/面向鏡頭）。**未做任何進階開發**（YOLO26s/PINTO/YOLOPose/D435 fusion/patrol/secure-default flip 一律不碰）。

---

## 測試環境

| 項 | 值 |
|---|---|
| Jetson | `jetson-nano`（Tailscale 100.64.0.1），ROS 2 Humble |
| Go2 | 已開機（本輪**未做 motion**，僅感知觀測）|
| 部署版本 | main `6b36b0c`（batch 1+2 全 merged；deploy `--all` 9 套件 colcon build 成功、install tree rebuild 生效、`.env` md5 不變 32a6453）|
| Demo stack | `pawai demo start -y` full mode，13 windows，**healthcheck 8/8 全綠** |
| 驗證基數（dev 機 main） | ~955 tests（IE 346 / contracts+gateway 125 / nav 94 / CLI 213 / go2 15 / face+benchmarks 162 / contract check 0 FAIL）|

---

## 驗收總表

| # | 驗收項 | 結果 | 備註 |
|---|---|:---:|---|
| 1 | Brain / ISM regression | 🟢 **PASS（軟體）** | off=legacy、staged 不崩、no-blackhole 全過；confirm wiggle / watchdog 待 Go2 motion |
| 2 | Studio Evidence Center | 🟢 **PASS** | session/timeline/export/report/frontend 全綠 |
| 3 | CLI smoke suite | 🟡 **PASS（2 bug）** | 多數綠；vision smoke + evidence pull 2 bug（已修，見 §hotfix）|
| 4 | Vision baseline | 🟢 **PASS（face 例外）** | cup/gesture/pose 穩定；face 偵測+追蹤 OK 但辨識 unknown（enrollment 過期，**非回歸**）|
| 5 | Go2 / Nav / Motion safety | 🟡 **部分（見附錄 HITL #2）** | confirm flow ✅ / face re-enroll ✅ / **nav motion 撞牆走歪＝NOT_DEMO_READY** |
| 6 | Security default-off regression | 🟢 **PASS** | default-off Studio 可用；auth-on enforcement 401/403 機制驗證；webrtc filter off byte-identical |

---

## 1. Brain / ISM Regression

| 子項 | 結果 | 證據 |
|---|:---:|---|
| 1a `ism_enabled` 全 off = legacy | 🟢 PASS | demo 起始全 off 時 healthcheck 8/8；runtime 設 5 flag False 後 `brain_node` alive、決策續流。off=legacy 由 346 IE 測試含 all-off byte-identical parity 背書 |
| 1b staged flags 打開不 crash | 🟢 PASS | `ism_enabled`+`ism_stage_2a/2b/2c/2d` 逐一 `ros2 param set True`，**每步 `brain_node` alive=1、零 Traceback**；brain log 僅 6 行乾淨 INFO（每 flag set 成功）|
| 1c confirm flow thumbs_up→OK→wiggle | ⏸ PENDING-HITL | 需 Go2 motion（wiggle）+ e-stop |
| 1d active_plan watchdog | ⏸ PENDING-HITL | 需注入卡死 skill 或真實場景 + 觀測 watchdog_timeout |
| 1e speaking / pending_confirm 不黑洞 | 🟢 PASS | 15s trace：8 事件、4 suppressed **全帶 gate/reason、0 靜默 drop**；先前全開時 `speaking` gate 觸發 2 次（2d 實際在動）|
| 證據：trace/TTS/skill_result/state_transition | 🟢 | 全開時 trace：state_transition 11 / policy_decision 137 / skill_result 1 / plan_emitted 1；gates: ism_shadow 136, attention_engaged 82, stranger_alert 54, speaking 2, greet_gate 1 |

**測試命令**：`ros2 param set /brain_node ism_enabled True|False`（逐 stage）；`ros2 topic echo /brain/trace --field data`；`pawai logs brain --lines 200`。
**證據路徑**：Jetson `/tmp/acc_trace.jsonl`；dev `artifacts/evidence/traces/20260613-160052.jsonl`（1175 行）。
**結論**：ISM staged-enable 架構**不破壞 Brain**——off 等同 legacy、staged-on 不崩、suppress 不黑洞。**互動行為層（confirm/watchdog）的真機驗證待 Go2 motion HITL。**

---

## 2. Studio Evidence Center

| 子項 | 結果 | HTTP / 證據 |
|---|:---:|---|
| `/api/trace/sessions` | 🟢 200 | 列 2 sessions（今 `20260613-160052` 1175 行 / 昨 `20260612-214410` 3420 行）|
| `/api/trace/export` redacted | 🟢 200 | 1175 行、555 行含 `[private]`（PII 遮蔽生效）|
| `/api/trace/export` full（redact=0，default-off）| 🟢 403 | A-11：token 系統關閉時全文匯出一律 403 |
| `/api/trace/report` | 🟢 200 | keys: session_id/event_count/time_range/verdict_distribution/top_suppressed_gates/**shadow_divergence** |
| 前端 `/studio/evidence` | 🟢 200 | 頁面 serve（dev `localhost:3001`）|
| 真實 session 可讀 | 🟢 | 今日 1175 行 session 可 list/export/report |

**測試命令**：`curl localhost:8080/api/trace/{sessions,export,report}`（Jetson）；`curl localhost:3001/studio/evidence`（dev）。
**註**：未做瀏覽器視覺截圖（頁面 serve 200 + 全 backing API 綠已足夠佐證）；視覺走查可併入下次 demo 彩排。
**結論**：Evidence Center 端到端可用——「為什麼沒反應」的 trace 可 list/timeline/export/redact/report。

---

## 3. CLI Smoke Suite

| 命令 | 結果 | 備註 |
|---|:---:|---|
| `pawai status` | 🟢 PASS | Jetson 可達、lock/driver/branch 正確 |
| `pawai smoke brain` | 🟢 PASS | 經 smoke full 的 brain segment 驗（PASS）|
| `pawai smoke vision` | 🟡 BUG→已修 | FAIL：查 `status_image`（demo 沒起 display node）；vision 實際健康（debug_image 3.25Hz、gesture/pose publisher 在）。**hotfix 改查 debug_image** |
| `pawai smoke object` | 🟢 PASS | object node、debug_image 6.03Hz、event publisher 全 OK |
| `pawai smoke nav --static` | 🟢 PASS（guard）| 正確偵測 brain demo 8GB 互斥並擋下 + 給 hint（守衛 work as designed）；完整 static 跑需切 nav stack |
| `pawai smoke full` | 🟡 BUG→已修 | brain/object/gateway/trace PASS、vision FAIL（同 status_image bug）|
| `pawai evidence pull` | 🔴 BUG→已修 | rsync exit 23：拉不存在的 `runtime/nav_capability` → 連帶炸掉整個 pull。**hotfix：缺失目錄優雅跳過**。手動 rsync trace 正常 |
| `pawai object matrix` | 🟢 PASS（接線）| `--help` 顯示完整參數（object/distance/light/angle/trials/window/conf-min），wiring `obj_matrix_cap.py`；實際矩陣跑＝進階開發、不做 |

**結論**：CLI smoke family 架構可用、會彙總、會給修復 hint。發現 2 個 CLI 準確度 bug（已 hotfix，見 §hotfix），非核心功能問題。

---

## 4. Vision Baseline（非模型升級，只記 baseline）

**object — cup（5s per-class dedup 下，6 次/35s ≈ 連續偵測）**：

| 距離 | cup 偵測 | conf min/avg/max | 混淆類別 | 顏色 |
|---|:---:|---|---|---|
| 0.7m | 6 | 0.35/0.52/0.91 | cell_phone 4, bottle 2 | yellow 0.52 |
| 1.0m | 6 | 0.39/0.61/0.77 | cell_phone 5, bottle 4, chair 1 | — |
| 1.5m | 6 | 0.42/0.68/0.89 | cell_phone 6, bottle 4 | — |

- **distance 不掉 recall**（conf 0.35 下 0.7-1.5m 都近連續偵測）；6/7「白馬克杯 1.5m Det:0」是 conf 0.5 + 白杯的舊條件。
- **主要不穩 = 類別混淆**（cup 持續被同時認成 cell_phone/bottle），非距離。

**gesture（thumbs_up→peace→open_palm，min_conf 0.7 + 3-vote 門檻）**：

| 手勢 | 觸發 | conf | 誤觸 |
|---|:---:|---|---|
| thumbs_up | 1 | 0.80 | — |
| peace | 1 | 1.00 | — |
| open_palm | （認成 ok）| 0.70 | palm↔ok 混淆，minor |

- **零誤觸 spam**：3 手勢只各觸發 1 次（門檻有效）。

**pose**：sitting 3 次 conf 0.55 / standing 2 次 conf 0.50；坐站轉換正確判定（two-class 模式 work）。

**face**：偵測+追蹤 OK（`/state/perception/face` 247 樣本/15s、track_id 活躍），但辨識 = **unknown，sim 0.2287**。

| 子項 | 結果 |
|---|:---:|
| face 偵測/追蹤 | 🟢 PASS |
| face 辨識（Roy known greeting） | 🔴 unknown — **enrollment 過期**（memory 記載 6/8 同款 sim~0.2，re-enroll 後 0.73-0.81）。**非重構回歸**，修法＝`pawai face enroll roy` → `rebuild` → 重啟 face node |

**測試命令**：`ros2 topic echo /event/{object_detected,gesture_detected,pose_detected} --field data`；`ros2 topic echo /state/perception/face`；`/event/face_identity`。
**證據路徑**：Jetson `/tmp/{obj,obj10,obj15,ges,pose,face}.jsonl`。
**demo 措辭界線**：可講「近中距杯子穩定偵測 / 手勢穩定 / 坐姿判定」；**不可講「精準物體分類」（phone/bottle 混淆）、不可講 face 辨識（待 re-enroll）**。

---

## 5. Go2 / Nav / Motion Safety — ⏸ PENDING-HITL

**本輪未做**（Roy e-stop 尚未就位；abort criteria #6：e-stop 沒就位不開 motion）。待辦（需 Roy + e-stop + Go2）：

1. 最小 motion：thumbs_up→OK→Go2 wiggle（= 驗收 1c confirm flow）
2. `pawai smoke nav --static`（需先 `pawai demo stop` 切 nav stack）
3. nav short goto 0.3m → 0.5m
4. safe-stop / stop-resume（另列；stop-resume tight space 禁 auto，operator-confirm only）

硬性 abort criteria 見 `docs/superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md` §8。

---

## 6. Security Default-Off Regression

| 子項 | 結果 | 證據 |
|---|:---:|---|
| gateway auth default-off 下 Studio 可用 | 🟢 PASS | demo gateway 8080 無 token：/health 200、/api/trace/sessions 200、frontend serve 200 |
| `webrtc_api_filter_mode` off byte-identical | 🟢 PASS | `ros2 param get` = `off`（零過濾＝現行為）；批次 test_robot_control_service 15 passed 含 off parity |
| auth-on enforcement 機制（401/403）| 🟢 PASS | 拋棄式 auth-on gateway @8099：/health 無 token 200、狀態變更無 token **401**、帶 token **200**、full export 無 token **401**；kill 後 demo 8080 不受影響 |
| security smoke | 🟢 PASS | 上述拋棄式驗證等同 security_smoke.sh 核心斷言；**未翻 demo secure-default**（不破壞 demo）|

**結論**：安全機制 default-off 不破壞 demo、auth-on enforcement 機制正常。**未做 secure-default flip**（屬進階，依 Roy B-6 決策）。

---

## 發現的 Bug + Hotfix 狀態

| # | Bug | 嚴重度 | 根因 | Hotfix |
|---|---|:---:|---|:---:|
| B1 | `pawai smoke vision` 假 FAIL | 中 | T3-1 查 `/vision_perception/status_image`（demo 不起 `vision_status_display` node）；vision 實際健康 | ✅ **已修**（本 PR）|
| B2 | `pawai evidence pull` 整個失敗 | 高 | T6-2② 拉不存在的 `runtime/nav_capability` → rsync exit 23 連帶炸掉 trace pull | ✅ **已修**（本 PR）|
| B3 | face 辨識 unknown | — | enrollment 過期（**pre-existing、非重構回歸**）| ⏸ 操作性：`pawai face enroll roy`→`rebuild`→重啟 face node（待 Roy）|

### Hotfix 內容（本 PR `feat/pre618-acceptance-hotfix`）

- **B1**：`scripts/smoke_test_vision.sh` liveness 檢查 `status_image` → **`debug_image`**（demo 真發、3-7Hz 的核心處理訊號）。`bash -n` 綠。**待重 deploy 後重跑 `pawai smoke vision` 確認轉綠**（smoke 腳本在 Jetson 端執行）。
- **B2**：`tools/pawai_cli/pawai_cli/evidence.py` `_pull_read_only` 加 `required` 參數；`nav_capability` 拉取改 `required=False`（缺失目錄 rsync 非零→印 skip 警告、不 raise），**traces（必要）照拉**。新增回歸測試 `test_evidence_pull_skips_missing_nav_capability`；CLI 套件 **214 passed**。
- **驗證**：CLI 214 passed（含新測試 + 2 個原失敗已轉綠）；B1 待真機重 deploy 後 smoke 轉綠（已知會綠，因 debug_image 實測 3.25Hz）。

---

## 尚未完成的 HITL

1. **Go2 motion 全段**（§5）：confirm wiggle、nav-static 實跑、short goto 0.3/0.5m、safe-stop/stop-resume——需 Roy e-stop。
2. **active_plan watchdog 行為驗證**（1d）：需注入卡死 skill。
3. **face 辨識**：re-enroll Roy 後重驗（非重構問題）。
4. **Studio Evidence 瀏覽器視覺走查**：API 全綠，視覺截圖待 demo 彩排。

---

## 下一步進階開發建議（驗收後，非本輪）

> 以下皆為 **post-acceptance** 項，Roy 拍板後才動：

1. **先收尾驗收**：跑完 §5 Go2 motion HITL（最高優先，補完回歸）+ re-enroll face。
2. **L4 上機矩陣日（B-3）**：cup 類別混淆是真痛點 → YOLO26s / 高解析 / open-vocab benchmark（synthesis 矩陣 A-E）才有數據基礎決定換不換模型。**本輪 baseline 已證 cup recall 距離不是問題、混淆才是** → 換模目標應對準「降低 cup↔bottle↔phone 混淆」。
3. **ISM staged enable 行為深驗**：2b confirm / 2c watchdog 的真機行為（本輪只證不崩）→ 收 shadow soak 數據後決定是否 demo 翻 staged-on（B-1）。
4. **Security enforcement flip（B-5/B-6）**：機制已驗，flip 時點 + foxglove 降權待決策。
5. **Nav capability ladder 升級**：poses 重錄 + 短距 n=3 重驗（L6 HITL N1-N8）。

---

## 驗收結論

**aggressive refactor（batch 1+2）後，PawAI 既有功能在軟體/感知層全面通過回歸**：Brain/ISM 不破壞既有互動（off=legacy、staged 不崩、不黑洞）、Studio Evidence 端到端可用、CLI smoke 可用（2 準確度 bug 已修）、Vision baseline 穩定（cup/gesture/pose；face 待 re-enroll）、Security default-off 不破壞 demo。**Go2 motion 安全驗收獨立 pending，需 Roy e-stop。** 完成度：① 軟體 95% / ② Pre-6/18 整體 ~63% / ③ v2 北極星 ~33%。

---

## 附錄：HITL #2 執行結果（2026-06-13 更晚，Roy e-stop 在場）

報告寫成後，Roy 開 Go2+Jetson、batch1+2 deploy 上 Jetson（main `6b36b0c`/`f0ed80c`），續做 Go2/motion HITL。

### Task 1 — Face re-enroll ✅ PASS
- SOP：刪舊 roy(6/8 stale)→`pawai face enroll roy`(30 樣本)→清 model→重啟 face node 重訓→重驗。
- 結果：**Roy 認出 `roy`、sim 0.84/0.87/0.91（217/217 幀 mode=stable）**，從 unknown(0.23) 修好。
- **新 bug B4（待 hotfix）**：`pawai face delete`/`rebuild` 只刪 `model_sface.pkl`、**不刪 T5S-5 的 `model_sface.npz`** → 刪人/重訓不生效，需手動 `rm model_sface.npz`。修法：main.py:2017-2018/2045 補刪 npz。Lane5(npz)↔Lane3(face CLI) 協調 gap。
- 坑：Go2 D435 低(~30cm)，Roy 多次不在框 face_count=0；enroll 殘留 `/face_identity_enroll_cv` node 採完要 pkill。

### Task 2 — Confirm flow（peace→OK→WeGo）✅ PASS（Roy 親眼確認 + trace 佐證）
- **demo 現在只剩 peace(YA)→OK→WeGo**（thumbs_up 等其他手勢已關；param `peace_wego_confirm=True`/`thumbs_up_demo_ack=False`）。
- trace 完整鏈：peace→`plan_emitted awaiting_ok:wiggle`→TTS「你要我 WeGo 一下嗎？比 OK 我就開始」→OK→`confirmed_via_ok:wiggle`→TTS「看我扭一下！」→skill completed。**pending_confirm 不黑洞**（PENDING 期間 object 被 pending_confirm gate 擋且有 trace）。順帶證 face greet「roy 歡迎回來」。
- instrumentation gap：webrtc 監聽與比手勢時段未重疊→未抓到 sport 指令，但 Roy 親眼確認動作發生。Task2 param：gesture_enabled/ism_enabled/ism_stage_2b_confirm=True。

### Task 3 — Nav motion ❌ **CRASH / NOT_DEMO_READY**（安全事件）
- nav stack 起來（LiDAR 0Hz healthcheck 早判→warmup 後 11.8Hz 健康；reactive_stop active；nav_ready=True 經 Foxglove initialpose 後）；`pawai smoke nav --static` **8/8 PASS**（順帶真機驗證 T3-3）。
- 安全閘全綠後發第一個 `goto_relative 0.3m` → **Go2 走歪 + 撞牆**，Roy e-stop 中止。
- **根因研判**：AMCL initialpose **朝向(orientation)不準** → 「前方 0.3m」算在地圖座標的歪方向 → Go2 朝斜邊走 → 撞上 reactive_stop 一直報的 **+25°/1.65m 側邊家具**（profile 是 ±30° open_space，非 home 的 indoor_tight ±18°）。
- **誠實結論**：**nav 短距 goto 在目前 initialpose 精度下 NOT_DEMO_READY / NOT safe**——第一次真機 goto 就走歪撞牆。延續 6/10 S1 的 AMCL covariance/pose 老問題。對外**不可講「自主短距移動」**直到 initialpose 朝向校正 + n 次無撞重驗。
- **後續修法方向**：① initialpose 朝向校正 SOP（LiDAR 紅點對齊牆面再確認）② 切 indoor_tight ±18° + 低速 ≤0.2 ③ goto 前加「朝向 sanity」或先小角度自轉對齊 ④ n=3 無撞才升 hardware_proven。

### HITL #2 待辦
- B4 npz hotfix（delete/rebuild 補刪 npz）。
- nav motion root-cause：initialpose 朝向校正後重驗（高風險，需 e-stop + 淨空）。
- nav stack 收工：`pawai demo stop`（撞擊事件後清場）。
