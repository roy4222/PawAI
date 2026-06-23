<!--
來源：ultracode system-improvement-research workflow（9 agents，grounded in 2026-06-04 HITL baseline + 實際 code + 0511 arch docs）@ main ba173c9。
規模：26 個 blocker/high 問題、24 個 6/18 相關、4 個 blocker（cli .env CRLF / gesture backend default / nav observer / nav F7）。

⚠️ Claude review 修正（gesture #2 vs #11，務必讀）：
- roadmap #2 說「wave fail 因 config default=rtmpose 讓 WaveDetector 不可達」。config default 確實是 rtmpose
  (`vision_perception/config/vision_perception.yaml:22`、`launch/vision_perception.launch.py:21`)，**是真 footgun**
  ——直接 launch 不經 demo override → rtmpose backend 不餵 WaveDetector → wave 永不觸發。把 default 改 recognizer 值得做。
- **但今天 HITL 的 wave fail 不是這個原因**：demo (`scripts/start_full_demo_tmux.sh:165`) 已 override
  `gesture_backend:=recognizer`，實測 running node = recognizer、node log = `recognizer: ... wave_pub=False`
  （WaveDetector 有被餵、有跑、就是沒觸發）。→ **今天 wave fail 的真因是 #11（偵測器門檻 + 1.5m 手部追蹤），不是 #2。**
  #2 修 config-default footgun（好），但別誤以為改 default 就解了今天的 wave fail。
-->

# PawAI 跨系統改進路線圖 — 2026-06-04 HITL Baseline 後

## 1. 執行摘要

今天的 trusted snapshot（`78fbf36`, readiness=not_ready）暴露了一個系統性真相：**多數 PASS 都是「窄版 PASS」，多數需要動作/移動的能力都還沒有真正量測過**。最痛的三件事：(1) **Brain LLM 自編世界狀態（幻覺）**——TTS 會自信地說出下雨、看到杯子、坐著站著等它根本沒有感測器支撐的事實，這直接擊穿「誠實 scoreboard」這個 6/18 賣點；(2) **語音安全指令 voice.stop FAIL（0.667）**——「停」被誤判成 come_here、或 VAD timeout 沒回應，這是安全關鍵失敗；(3) **gesture.wave / pose / nav 全線無法量測**——wave 因 config backend 選錯（rtmpose）導致偵測器 code path 根本到不了、pose/nav 連 baseline observer 都沒寫、加上 `.env` CRLF 會讓 demo 靜默假成功。6/18 前最該修的：**先讓「可 demo 的能力」誠實可信（修幻覺、修 stop、修 wave backend），再讓「目前 insufficient_data 的能力」至少能被量測（補 pose/nav observer），把不能可靠展示的鎖在「只顯示、不觸發、不宣稱」。**

---

## 2. 跨系統優先級表（blocker / high 排序，最痛在最上）

| # | Subsystem | 問題 | Severity | Effort | 6/18 | 具體改法 |
|---|-----------|------|:--------:|:------:|:----:|---------|
| 1 | cli/orch | `.env` CRLF 讓 tmux pane 靜默 source 失敗，CLI 卻報「running」成功 | **blocker** | medium | ✅ | bash 層加 CRLF normalize（或寫 `.env.clean` 給 tmux source）+ preflight 加「ROS node 實際存活」檢查，healthcheck 過了才把 lock 轉 running |
| 2 | gesture | WaveDetector code path 不可達（config `gesture_backend=rtmpose`） | **blocker** | quick | ✅ | `vision_perception.yaml` 改 `gesture_backend: recognizer`（文件化主線），重測 wave 門檻 @1.5m |
| 3 | nav | 無 nav baseline observer，safe_stop/no_auto_resume 無法量測 | **blocker** | medium | ✅ | 新增 `benchmarks/core/nav_baseline_observer.py`，訂 `/scan_rplidar`+`/state/reactive_stop/status`+`/nav/goto_relative` result，記 collision/stop_margin/actual_distance |
| 4 | nav | F7：goal accepted 後 `/cmd_vel_nav` 無 publisher（10s timeout） | **blocker** | medium | ✅ | 乾淨重啟全 stack→設 initialpose→送 0.3m→抓 controller_server log/costmap/lifecycle 診斷根因，記入 roadmap |
| 5 | brain | **LLM persona 幻覺：自編下雨/看到杯子/姿勢**（Roy 頭號關注） | **high** | quick | ✅ | IDENTITY.md 加反幻覺硬約束；改寫 EXAMPLES.md 移除無 grounding 的下雨/杯子 few-shot 並加反例；response_repair 加 verifier WARN |
| 6 | speech | voice.stop 誤判：R18「停住…過來」→ come_here 勝出 | **high** | quick | ✅ | intent_classifier 加 safety tie-break：stop 主關鍵字（停止/停下/停住）confidence≥0.7 時強制 stop 勝；提高 stop 權重 |
| 7 | speech | voice.stop no-ack：R16「請你停下來」VAD timeout 不發佈 | **high** | quick | ✅ | `silence_duration_ms` 800→400、`stop_threshold` 0.01→0.008；中期接 `/event/mic_boundary` 手動 finalize |
| 8 | nav | no_auto_resume 行為衝突：reactive_stop 障礙清除後自動 resume | **high** | medium | ✅ | 移除 `_maybe_call_nav_pause` 的 auto-resume，只發 `/nav/pause`；加 `mode_on_clear=silent` param；demo 用 silent |
| 9 | nav | doc bug：`/event/nav/mission` topic 全 source 不存在，echo 永久 hang | **high** | quick | ✅ | 三份 runbook/spec 改成讀 `/nav/goto_relative` action result，observer 訂 result 不訂假 topic |
| 10 | nav | BD-7 recorder `_cb_reactive_status` no-op，reactive_stop 狀態沒被記 | **high** | medium | ✅ | wire `_cb_reactive_status` 訂 `/state/reactive_stop/status`，記 danger 進出+stop_margin；確認 launch 有 state_broadcaster |
| 11 | gesture | hand detection @1.5m 失敗（rtmpose wholebody 手部 kp 不穩） | **high** | medium | ✅ | 切 recognizer 後重測；若留 rtmpose 則 `gesture_min_score` 0.1→0.05、`min_amplitude_px` 50→35 |
| 12 | gesture | `vote_frames=10`+`stable_s=1.5` 讓靜態手勢延遲 ~2s 不可用 | **high** | quick | ✅ | 修好 wave 後 revert 到 N7 基線（`vote_frames=5`、`stable_s=0.3`），latency 回 ~550ms |
| 13 | object | ~1m 遠端召回率未量化（cup-only、距離拉遠掉很快） | **high** | medium | ✅ | 做 1.0/1.5/2.0/2.5m × n≥5 距離-召回曲線；<0.8 評估 yolo26s；North Star 標「可靠範圍 ~1.0-1.5m」 |
| 14 | object | input 固定 640×640，小物件遠距無法改善 | **high** | large | ❌ | 暫不改；中期 WSL 重匯 ONNX with dynamic_axes 再 A/B |
| 15 | face | 陌生人拒絕未驗證（idle 是空景，非真實 unknown 臉） | **high** | medium | ✅ | 跑 10-15 frame 真實未註冊者 @1-2m，確認 cosine < 0.40；否則調 threshold + 多角度重註冊 |
| 16 | face | 辨識信心窄又抖（0.24-0.54, mean 0.46），hysteresis 不穩風險 | **high** | medium | ✅ | 多角度/多光線重註冊 30-50 樣本 + quality filter（<0.50 拒收）+ 重 baseline 確認 mean>0.50 |
| 17 | pose | pose.basic 無 baseline observer，無法量測可靠度 | **high** | quick | ✅ | `perception_baseline_observer.py` 加 `normalize_pose_event()`，訂 `/event/pose_detected`，接 capture round |
| 18 | pose | pose.fall 設計「演示only但仍可觸發 skill」，與 North Star 衝突 | **high** | quick | ✅ | brain_node `_on_pose` 的 fallen 分支只記 world_state 不 emit skill（或 feature_flag 鎖死）；snapshot 維持 insufficient_data |
| 19 | pose | LLM 忽視/自編姿勢（與 brain 幻覺同源） | **high** | medium | ✅ | 見 #5；Prompt 加「pose=None 代表沒看到、不得自編」+ pose_freshness 標籤 |
| 20 | cli/orch | `.env` vs `.env.local` 檔名漂移（Jetson deploy vs local） | **high** | medium | ✅ | 定 `.env.local` 為 canonical、`.env` 為 template；preflight 先查 `.env.local`；rsync 允許帶 `.env.local` |
| 21 | cli/orch | preflight 只查 launch 回傳碼，不查 node 存活 | **high** | medium | ✅ | start.sh rc=0 後加 30s polling `ros2 node list`，count=0 則 fail 並清 session |
| 22 | cli/orch | Deploy SHA 對齊摩擦（main 在 deploy 後前進） | **high** | medium | ✅ | `pawai demo start --verify-sha`：local HEAD vs Jetson 部署 SHA 不一致 fail-fast |
| 23 | speech | ASR→intent 短同音字亂掉（照相→chat、狀態→chat） | **high** | medium | ✅ | 先 instrument R20/R25 印出實際 ASR text+matched keywords；確認是 ASR 降質還是 legacy `intent_node.py` 殘留路徑 |
| 24 | speech | TTS+Gemini 並行 chunk RMS 漂移（越念越大聲又變小） | **high** | medium | ✅ | 先測 sequential 確認並行是元兇；加 chunk RMS normalize 或 workers 8→2-3 |

---

## 3. 6/18 前 do-now 短清單（6/18 相關 AND quick/medium，能提升可信度/可 demo 能力）

建議執行順序（先解鎖「能不能誠實 demo」，再修「demo 品質」）：

1. **gesture backend 切 recognizer + revert vote_frames/stable_s**（#2, #12，quick）— 一個 config 改動同時解開 wave code path 與靜態手勢延遲，最高 CP 值。
2. **voice.stop tie-break + VAD 門檻調整**（#6, #7，quick）— 安全關鍵指令，demo 一定會被測「叫狗停」。兩個都是改 config/規則，5 分鐘 code + 10 分鐘測。
3. **Brain LLM 反幻覺**（#5, #19，quick）— Roy 頭號關注、也是 scoreboard 賣點。改 persona prompt（IDENTITY/EXAMPLES）+ response_repair verifier。**這條不修，誠實敘事就破功。**
4. **`.env` CRLF normalize + preflight node 存活檢查**（#1, #21，medium）— 今天就因為這個白白浪費時間，不修 6/18 當天會再踩。
5. **doc bug `/event/nav/mission` 修正 + runbook 誠實 caveat**（#9, 各 runbook，quick）— 防止 operator 6/18 當天 echo 假 topic 永久 hang。
6. **pose baseline observer `normalize_pose_event()`**（#17，quick）— 一個小函式就能讓 pose.basic 從 insufficient_data 變可量測，Studio 才能合法顯示姿勢語境。
7. **pose.fall 鎖死不觸發 skill**（#18，quick）— 對齊 North Star §4/§5，避免誤觸打斷對話又造成 overclaim。
8. **nav baseline observer + BD-7 wire + BD-8 no-auto-resume**（#3, #10, #8，medium）— 三件一起做才能把 nav 從 insufficient_data 推到「可量測（pass 或誠實 fail）」。注意實機跑 short_move 需 F7 先排除（#4）+ 人工安全 override。
9. **object 距離-召回曲線**（#13，medium）— 量化「可靠範圍 ~1-1.5m」，把 object.cup 的窄版 claim 釘死。

> **不進 do-now**：face 重註冊/陌生人驗證（#15/#16，medium 但需設備與時間，且 face 已 PASS 窄版可先用窄版 claim demo）；ASR 同音字（#23）與 TTS RMS（#24）需更多診斷，列為 do-now 後段或 backlog。

---

## 4. 各子系統重點

**人臉 (face_perception)** — 現狀：PASS 但是「Roy 一人 + 空景 idle + 信心 0.24-0.54」的窄版，陌生人從未真測。前 3 改進：(1) 跑真實未註冊者 10-15 frame @1-2m 驗證 cosine<0.40，否則調 threshold；(2) 多角度多光線重註冊 30-50 樣本 + quality filter 把 mean 信心推過 0.50；(3) 補 grama 第二人 baseline + 距離-召回 sweep（實際 1.8-2.4m，README 卻寫 1m）。

**語音 (speech_processor)** — 現狀：command PASS(0.875)、**stop FAIL(0.667)**、ASR 仍 VAD-era（2-10s 抖動）。前 3 改進：(1) intent_classifier 加 safety tie-break 讓 stop 主關鍵字必勝，解 R18 come_here 誤判；(2) VAD `silence_duration_ms` 800→400 解 R16 no-ack，中期接 `/event/mic_boundary` 手動 finalize；(3) instrument R20/R25 確認照相/狀態→chat 是 ASR 降質還是 legacy `intent_node.py` 殘留（順手刪掉 legacy）。

**姿勢 (pose)** — 現狀：basic / fall 都 insufficient_data（**根本沒 observer**）。前 3 改進：(1) `normalize_pose_event()` + 訂 `/event/pose_detected` 接 capture round，讓 pose.basic 可量測（quick，最高優先）；(2) brain_node fallen 分支改為只記 world_state 不 emit fallen_alert skill，對齊 North Star「不可靠只顯示不觸發」；(3) Prompt 加「pose=None 不得自編」+ freshness 標籤（與 brain 幻覺同源）。

**手勢 (gesture)** — 現狀：**wave FAIL(0/6)**，因 config backend=rtmpose 讓 WaveDetector 根本不可達；靜態 thumbs_up/ok/palm 可用。前 3 改進：(1) `gesture_backend: rtmpose→recognizer` 重啟主線 code path（blocker、quick）；(2) revert `vote_frames=5`/`stable_s=0.3` 把靜態延遲拉回 ~550ms；(3) 若 wave 仍不穩，Plan B 用 palm→greeting 當替代，scoreboard 誠實標 `gesture.wave=fail → 用 palm 替代`。

**物體 (object_perception)** — 現狀：cup PASS 但僅 ~1m 近距、cup-only（COCO 41）、其餘 80 類預設被 whitelist 擋掉。前 3 改進：(1) 距離-召回曲線量化「可靠範圍」；(2) 明確分層 P0=cup / P1=bottle·chair·person（已裝未測）/ P2=其餘，North Star 標「其他類只 UI 顯示不觸發 TTS」；(3) 加 TRT warmup gate 避免 6/18 當天 slow-first-frame 無預警。

**導航 (nav)** — 現狀：safe_stop/no_auto_resume/short_move/dynamic_avoidance 全 insufficient_data；live dry-run 在 AMCL gate fail-closed（actual_distance=0、Go2 零移動，action chain 與 fail-closed 都正確）。前 3 改進：(1) 寫 `nav_baseline_observer.py` 解鎖量測（blocker）；(2) 修 F7 `/cmd_vel_nav` 無 publisher 根因 + 修 BD-8 移除 auto-resume；(3) 修 doc bug（`/event/nav/mission` 不存在）+ runbook 加誠實 caveat（demo 只跑 Studio 視覺化、不宣稱真實移動）。

**Brain × Studio** — 現狀：**LLM persona 幻覺是頭號風險**；capability gate #120 預設 OFF；Studio scoreboard 只在 mount 時讀一次 stale 資料。前 3 改進：(1) 反幻覺：IDENTITY.md 加硬約束 + 改寫 EXAMPLES.md 移除無 grounding 的下雨/杯子並加反例 + response_repair verifier（quick，頭號）；(2) capability gate 6/18 決策：維持 OFF（誠實、避免假信心 block）或備好 minimal `health_config.yaml`（voice.stop=fail→block MOTION、nav.*=insufficient→block NAV）；(3) Studio scoreboard 加 refetch trigger，讓 `/api/scoreboard` 回 live capability_context 而非 cached snapshot。

**CLI / Orchestration** — 現狀：CLI 報 demo「running」成功，實機卻零移動（false success）。前 3 改進：(1) `.env` CRLF normalize + 把 lock「running」轉換綁在 healthcheck 通過後（blocker）；(2) preflight 加 node 存活 polling（不只查 SSH/launch rc）；(3) `.env.local` 定為 canonical 解檔名漂移 + `--verify-sha` 防 deploy SHA 漂移。

---

## 5. 誠實 / claim-scope 護欄

**demo 只能講窄版，以下 PASS 都是窄版，禁止泛化宣稱：**

- **face.recognition = PASS（窄版）**：僅 Roy 一人註冊、idle 是**空景無臉**（陌生人拒絕**從未真測**）、信心 0.24-0.54（mean 0.46，1 樣本落在 hysteresis 帶）、實際距離 1.8-2.4m。只能講「能認出已註冊的 Roy」，**不能講「能拒絕陌生人」**直到 #15 跑完。
- **object.cup = PASS（窄版）**：僅 cup（COCO 41）、僅 ~1m 近距、信心 0.85-0.88、7 樣本全正樣本。只能講「近距離能認杯子」，**不能講「通用物體辨識」**也不能講 2m+。
- **voice.command = PASS（窄版）**：固定指令集、**無 latency 數據**（VAD-era 2-10s 抖動）、`mic_stop` 未接線。只能講「固定指令辨識率 0.875」，**不能宣稱 mic_stop latency**。
- **voice.stop = FAIL**、**gesture.wave = FAIL**、**pose.basic/fall = insufficient_data**、**nav.* = insufficient_data**：6/18 前若未修，scoreboard 必須誠實顯示 fail/insufficient_data，**這些能力不得觸發 motion/nav，不得宣稱可靠**（North Star §4/§5/§9 fail-closed）。

**Roy 的 3 個 review finding（必須在敘事中誠實標註）：**

1. **Evidence drift**：baseline README 一處說 nav「deferred」，但實際已補 live dry-run（action accepted→AMCL gate abort）。README 與實際證據不一致，需校正——dry-run 證明的是「action chain 接線 + fail-closed 正確」，**不是** nav 可移動。
2. **Provenance**：trusted snapshot `78fbf36` 帶 `run_trusted=True` 但環境是 WSL / jetson_dirty 等 provenance 標記；reproducibility 受 deploy-SHA 漂移影響（見 #22）。引用數據時須附 provenance，不可當作乾淨環境結果。
3. **Claim scope**：所有 PASS 都要附「窄版邊界」一句話（誰/多遠/什麼條件），Studio scoreboard 的賣點正是這種誠實分級（pass/degraded/fail/insufficient_data），**泛化宣稱會直接摧毀這個賣點**。

---

## 6. 非 6/18（中長期 backlog）

| Subsystem | 項目 | Effort | 理由 |
|-----------|------|:------:|------|
| object | input 固定 640→dynamic_axes 重匯 ONNX 改善小物件遠距 | large | 風險高、需 WSL 重匯 + letterbox/rescale 改寫 + A/B |
| object | HSV 顏色辨識多光線/多角度魯棒性驗證 | medium | demo 不靠顏色，post-demo 再量化 |
| object | confidence 0.35 閾值 A/B（precision/recall/F1） | quick | 需 30+ ground-truth 標註，非 demo 關鍵 |
| face | IOU tracking 無 re-ID，重入產生新 track（greeting churn） | large | 設計已知可接受，必要時再做輕量 re-ID |
| face | enrollment quality UI feedback + retraining logging | medium | 流程改善，非 demo blocker |
| face | model path hardcode Jetson，無 WSL fallback | quick | 影響本地測試，非 demo |
| pose | pose vs gesture buffer 比例（20 vs 5 frame）context 鮮度 | medium | 加 latency warn 即可，非 blocker |
| pose | akimbo/knee_kneel contract enforcement（內部 7 種 vs 凍結 4 種） | medium | 防 contract 破壞，post-demo 清理 |
| nav | nav_ready gate 升級（lifecycle + TF + costmap freshness） | medium | 目前 basic gate 夠 demo，加 manual preflight caveat |
| speech | 刪 legacy `intent_node.py` + pre-commit hook 擋改 | quick | 架構債，與 #23 診斷一起做 |
| brain | capability gate #120 full wire-up（所有能力 graded + brain_allowed） | medium | 下次 freeze 才需要，6/18 維持 OFF |
| brain | registry health-threading keying（skill name vs capability_id） | quick | 內部一致性，無 demo 影響 |
| brain | Studio trace drawer 能力 drill-down（每 proposal 顯示考慮的能力） | medium | 觀測性增強，非 demo blocker |
| cli/orch | demo start 結構化 log（sanitized .env + ROS params + SHA） | quick | debug 用，提升下次 root-cause 速度 |