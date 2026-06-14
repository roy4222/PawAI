# Codex 獨立第二意見 — Act1 nav 失敗 + S3 物體關懷台詞錯

> 2026-06-14。Codex read-only 交叉診斷（未改 code、未發 motion）。本檔為獨立第二意見快照，
> 將折進 [`2026-06-14-live-demo-iteration-findings.md`](2026-06-14-live-demo-iteration-findings.md) 的「Codex 交叉檢查」一節。
> 用途：對抗主線假設、抓主線可能查錯路的點。

## 最關鍵兩點（第二意見價值）

### Act1：Stage1 數據本身就「不該停」
- `reactive_stop_node` 預設 `danger_distance_m=1.1`、`slow_distance_m=1.7`，`classify_zone()` 用嚴格 `<`。
- Stage1 量到正前 ±15°=**2.09m（clear）**、右前 +20°=**1.70m（剛好 slow 邊界）**。
- → **在現有門檻下，這組距離根本不會觸發 stop**。Act1「沒成功」很可能不是 node 沒啟、不是 cmd_vel 沒到 driver，而是 **障礙放太遠 / demo 幾何與門檻設計** 問題。
- 次要：standalone slow 發 `0.45 m/s`，但 Go2 sport mode `MIN_X≈0.5`，driver 不會把 0.45 補到 0.5 → **Go2 收到 Move 0.45 但實機可能不動**，看起來像「沒動」。
- 主線文件多在解釋 Nav2 / progressive reactive_stop（slow 是 silent），但 **Act1 是 standalone**（直接 publish 0.45/0.60 到 `/cmd_vel`），不能直接套 progressive 那條主因。T0 TF authority / AMCL yaw 對 standalone 路徑（`/scan_rplidar → reactive_stop → /cmd_vel → driver`）不是第一優先，過度套 Nav2 incident 會分散注意力。

### S3：Brain 只取 `objects[0]`，且「Roy 的手機」可能不是 object_remark 產物
- `perception_router.parse_object()` 只讀 `objects[0]`；`object_perception_node._publish_events()` 依模型輸出順序 append，**沒有 cup / 中心 / 距離優先** → cup 被 phone 蓋掉。這比 cooldown/dedup 更直接的根因。
- **UI 看到 cup ≠ Brain 選 cup**。
- `build_object_tts("cell_phone")` 只組「看到手機了」，**不會說「Roy 的手機」**。若實際台詞含「Roy」，可能來自 conversation graph / LLM world_state（`recent_objects`），**只查 `build_object_tts()` 會查錯路** → 要先分辨 emitted skill source 是 `object_remark` 還是 LLM/chat reply。
- 「沒 pose」是獨立 pipeline 問題（`vision_perception_node` majority vote 太嚴全 None），不會由 cup 自動修復。

## Ranked 可證偽根因（完整）

### Act1 導航避障失敗
1. **[證據支持] LiDAR 活著但障礙沒進 stop 條件**（2.09m clear / 1.70m 邊界 slow）。驗證：reactive status `zone=clear/slow`、`reactive_stop_active=false`、`/cmd_vel` 非 0。
2. **[證據支持] Go2 sport mode 低速門檻使 slow 0.45 失真**（driver clamp 到 MAX 0.5，不補 0.45→0.5）。驗證：`/cmd_vel`=0.45、driver 收到 Move 0.45 但實機不動；調高 slow profile 或 slow→stop 後行為改變即證偽。
3. **[證據支持] reactive 幾何是角度扇形、非 footprint/corridor**（`compute_front_min_distance()` 只取 front arc 最小距離，走歪撞側邊會誤判沒啟動）。驗證：sector slow/clear 但機身側邊已交會障礙；改 footprint 會提前進 danger。
4. **[未驗證] driver/WebRTC ready gate 不足**（script 只 sleep 8s）。驗證：log 有無 driver ready / `_on_cmd_vel` / send 成功。
5. **[未驗證] 啟到錯 instance 或參數沒生效**（預設 topic `/cmd_vel_obstacle`、offset 0；script 傳 `/cmd_vel`+offset π+danger 1.1+slow 1.7，但只 kill tmux session 不清 orphan）。驗證：node startup log/params 是否真為這組值、mode=standalone。
6. **[未驗證] 障礙高度不在 LiDAR 掃描平面**（低矮/透明/細腳）。驗證：換穿過 LiDAR 平面的實體物，sector 立刻 `<1.1m`。

### S3 物體關懷台詞錯
1. **[證據支持] Brain 只取 `objects[0]`，cup 被 phone 蓋掉**。驗證：`/event/object_detected` payload `objects[0]=cell_phone`、cup 排後面。
2. **[證據支持] phone 先觸發後，active plan / TTS / skill cooldown 跨物件壓掉 cup**（class dedup 是 per-class 60s，但 skill cooldown / active plan 跨物件）。驗證：`/brain/trace` 出現這些 gate。
3. **[未驗證] attention gate 抑制 cup**（`_on_object()` 要求 `ENGAGED`：臉可見、≤1.6m、dwell ≥1.5s）。驗證：trace gate=`attention_engaged` 且 face 沒到 ENGAGED。
4. **[證據支持] pose 沒出是獨立 pipeline 問題**（majority vote 太嚴全 None），不由 cup 修復。驗證：`/event/pose_detected` 缺席或無 `sitting`。
5. **[未驗證] demo config/phase drift**（`executive.yaml` `demo_phase: all`；runtime 沒載或 phase 不允許 object 會被 `_phase_allows("object")` 擋）。
6. **[第二路徑疑點] 「Roy 的手機」非 `build_object_tts()` 產物**，疑來自 conversation graph / LLM world_state。驗證：emitted skill source = `object_remark` 還是 LLM/chat reply；檢查 `world_state.recent_objects`。

## Default-off / 可 rollback 修方向（僅方向，未實作）

**Act1**
- default-off `reactive_stop_demo_profile`：把 standalone slow/normal/danger 門檻、front arc、front offset 固定成可觀測 profile，關閉即回原參數。
- default-off slow 行為選項：`slow_policy=stop` 或 `slow_speed ≥ Go2 usable floor`，避開 0.45 不可靠區。
- default-off footprint/corridor 判斷：保留 sector min distance，可選機身寬度 + 前進 corridor。
- read-only preflight/status gate：啟動前只檢查並顯示 reactive params、publisher topic、driver ready、scan age、zone，不發 motion，異常 fail closed。

**S3**
- default-off S3 object selector：在 `objects[]` 中優先選 cup 或中心/近距離目標，rollback 回 first-object。
- object gate trace + suppressed-reason：對 attention/active_plan/TTS/cooldown/phase gate 輸出明確 reason（debug-only）。
- S3 phase entry 可回滾 context cleanup：進 S3 清 object dedup、object_remark cooldown、過期 active plan，僅限該 phase。
- pose 不作 cup 普通台詞前置：compound「Roy 坐著拿杯子」仍需 pose，普通 cup care line 只依賴 cup target（default-off S3 fallback line）。

## 相關檔案（絕對路徑）
- `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py`
- `go2_robot_sdk/go2_robot_sdk/lidar_geometry.py`
- `go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py`
- `go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py`
- `scripts/start_reactive_stop_tmux.sh`
- `interaction_executive/interaction_executive/brain_node.py`
- `interaction_executive/interaction_executive/perception_router.py`
- `object_perception/object_perception/object_perception_node.py`
- `object_perception/config/object_perception.yaml`
- `vision_perception/vision_perception/vision_perception_node.py`
