# Pre-6/18 HITL Rehearsal Runbook（plan5 T5-RB｜Roy 回場必跑）

> 日期：2026-06-13 產出（AFK，**docs-only，不上機**）｜owner：Cloud/Fable（整合）｜狀態：PLANNED
> 角色：本檔是「**Roy 回到 Jetson + Go2 後照著跑**」的 HITL 收束清單。AFK 階段所有純軟體已 merged + 單測綠（**needs-HITL**）；**只有本檔逐項在真機過了，才可標 `proven`**。
> 鐵律：**manual FLOOR 先跑、auto-advance 後驗**；**no-motion 段全部先做完**；任何 Go2 motion **必須 Roy 授權 + e-stop 在手**。
>
> 交叉文件（同次 sprint 產出，merge 後同在 main）：
> - 操作員現場手冊：[`2026-06-18-operator-runbook.md`](2026-06-18-operator-runbook.md)（plan4）
> - S1 三層 fallback 決策 + claim wording：[`../navigation/2026-06-13-s1-fallback-decision.md`](../navigation/2026-06-13-s1-fallback-decision.md)（plan6 NS-6）
> - no-motion 診斷 SOP：[`../navigation/2026-06-13-no-motion-diagnostics-sop.md`](../navigation/2026-06-13-no-motion-diagnostics-sop.md)（plan6 NS-D2）
> - initialpose yaw 校正 SOP：[`../navigation/2026-06-13-initialpose-yaw-calibration-sop.md`](../navigation/2026-06-13-initialpose-yaw-calibration-sop.md)（plan6 NS-5）
> - co-run profiling 程序：[`../navigation/2026-06-13-corun-profiling-procedure.md`](../navigation/2026-06-13-corun-profiling-procedure.md)（plan1）
> - 總綱 / 憲法（Q1–Q6）：[`../superpowers/plans/2026-06-13-pawai-pre618-final-execution-plan.md`](../superpowers/plans/2026-06-13-pawai-pre618-final-execution-plan.md)

---

## §0 安全前置（每次開工第一件事，無例外）

- [ ] **Go2 停穩、四腳著地**；遙控器在手、**e-stop 就位**（`nav_capability/scripts/emergency_stop.py engage` / `StopMove(1003)`；**禁對運動中 Go2 送 `Damp(1001)`**）。
- [ ] **清場**：`pawai demo stop`（依 lock lane 路由）→ 確認 nav stack 不殘留（剛 goto 撞牆過）：`pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud; pkill -9 twist_mux`，再 `ros2 node list` 應乾淨。
- [ ] **8GB 互斥**：nav stack 與 brain demo stack **不同跑**（除非 §2 profiling 證實 C-CORESIDENT 可共存）。
- [ ] **`.env` 衛生**：`ssh jetson-nano "cd ~/elder_and_dog && sed -i 's/\r$//' .env .env.local"`（CRLF 會讓 demo 靜默假成功）；`grep -E "OPENROUTER_GEMINI_TIMEOUT_S|PAWAI_LLM_TIMEOUT|LLM_TIMEOUT" .env .env.local`（**確認無 60/15 殘留**會把 plan3 timeout 修正靜默還原）。
- [ ] **不要只信 CLI 成功訊息**：起 demo 後 `tmux ls` + 數 process + `ros2 node list` 親眼確認。
- [ ] `stranger_alert_enabled=false`（6/9 真兇）、`enable_fallen:=false`（永久鎖）。

---

## §1 face_db 衛生 + re-enroll（plan5 T5-1/T5-2，no-motion）

> 前置 S2 具名問候；**先機上 `ls` 確認真檔名**，不要假設。

1. [ ] `ssh jetson-nano "ls -la /home/jetson/face_db/"` — 確認 `model_sface.pkl` + `model_sface.npz`（embedding cache）真實檔名；**任何 `_backup*`/`old*` 子目錄移出 `face_db/` 外**（會變幽靈身份稀釋 centroid）。
2. [ ] `pawai face delete --person-name roy`（**T5-1 已修：現在同時 `rm -f` `.pkl` + `.npz`**，不再被舊 embedding cache 復活）。
3. [ ] `pawai face enroll --person-name roy`（訂 `/camera/.../color/image_raw`，與 demo camera 不衝突）。
4. [ ] `pawai face rebuild`（刪 pkl/.npz）→ 重啟 face node 重訓。
5. [ ] `pawai face test` → **Roy known sim ≥ 0.7**（未過則重 enroll；過期 enrollment 會掉到 ~0.2 被判 unknown）。
- **通過標準**：sim ≥ 0.7、`ls` 無幽靈備份目錄。**未過 → S2 退 generic greet（不秀具名）。**

---

## §2 co-run profiling（plan1，Roy 在場、**全程 no-motion**）

> 決定 S1 runtime layout（不是用猜的）。詳見 [`corun-profiling-procedure.md`](../navigation/2026-06-13-corun-profiling-procedure.md)。

1. [ ] 起 brain full demo（face/object/pose/gesture/brain/Studio/gateway/ASR/TTS）。
2. [ ] **配置 A**（brain baseline）：`bash scripts/corun_profile.sh --config A --duration 240 --interval 5` → `corun_profile_parse.py --config A`。
3. [ ] **配置 B**（+ raw LiDAR/Foxglove，不開完整 nav2）：`--config B`。
4. [ ] **配置 C**（+ AMCL/Nav2/costmap/reactive_stop/Foxglove，**no motion、不發 goto/cmd_vel**）：`--config C`（壓力上限；若 `OOM-RISK ABORT` 立即清場）。
5. [ ] 4-branch 判讀 → 鎖 S1 runtime layout（**6/16 09:00 後不得再改**）：
   - C 全 PASS → **C-CORESIDENT**（可 live 顯示 map/nav，仍不發 goto）
   - C FAIL / B PASS → **B-RESIDENT-LIDAR**（raw LiDAR + operator-assisted）
   - B FAIL / A PASS → **A-ONLY-VIDEO**（第三人稱 + Studio brain + 影片）
   - A FAIL → **BRAIN-FIRST**（先修 brain，nav 不談）
- **量**：RAM/CPU/GPU/temp/object debug_image Hz/face event/LiDAR Hz/gateway health/Studio 卡否/node crash/3–5 分鐘穩定否。

---

## §3 五幕 dry run（**先 manual floor，再 auto-advance**）

> 每幕四條路徑都要驗：**① trigger success ② canned fallback（never dead air）③ operator skip ④ trace evidence**。
> manual：Studio hidden 五幕鈕（`?dev=1`）或 `ros2 param set /brain_node demo_phase <phase>`。
> auto：`ros2 param set /brain_node auto_advance_phases '["<phase>"]'`（**逐幕、預設 OFF；6/17 彩排才決定開哪幕**）。

| 幕 | 觸發信號 | manual floor 驗 | auto 驗 | canned fallback | 能力 | 備註 |
|---|---|---|---|---|---|---|
| **S1 nav** | operator-arrived | 切 `s1_nav` → brain quiet（不社交） | — | 「我正在移動到巡檢位置」 | **FAILED→fallback** | **不發 goto_relative**；演法見 [s1-fallback-decision](../navigation/2026-06-13-s1-fallback-decision.md) |
| **S2 greet** | face known 0.5–1s | 切 `s2_greet`（Roy 已 known 也 greet＝gotcha #1）；不坐也問候（gotcha #2 sitting=false） | `auto_advance_phases:=["s2_greet"]` | 「Roy，歡迎回來」 | needs-HITL | 重現 greet 需遮臉~5s 再回 |
| **S3 pose+object** | cup 0.5–1s | 切 `s3_pose_object` → cup remind；sitting=bonus | — | 「記得多喝水」 | needs-HITL | sitting 不到不卡 |
| **S4 gesture confirm** | 一次高信心 gesture（**僅 S4**） | 切 `s4_gesture` → 手勢→OK→**Go2 wiggle** | — | 「比 OK 我就開始」 | needs-HITL | **★ Go2 motion：需 e-stop**；目標 thumbs_up→OK→wiggle，失敗退 proven peace→OK→WeGo |
| **S5 safety** | keyword/text | 切 `s5_safety` → 危險指令 → **rule-first reject（no LLM）** | — | 「這個動作不安全，我不能執行」 | **proven**（6/10） | LLM 不可 override；`s5_safety=∅` 不擋 SafetyLayer |

- [ ] 切幕清理驗（plan2 T2-2）：s4 confirm 在飛 → 切 s5 → trace 看 `phase_switch:s5_safety` cancel pending_confirm + active_plan 清、**attention 保留**。
- [ ] one-keystroke disable：任一幕 auto 不穩 → `auto_advance_phases:=[]` 即回 manual floor（**6/18 絕不押 auto**）。

---

## §4 控制面驗（plan4，no-motion）

- [ ] Studio hidden 五幕鈕（`?dev=1`）→ 每顆切 phase **先 reset 再切**，trace 記 transition；打錯 phase 被 400 拒、不 silent fall-through。
- [ ] `ros2 param set /brain_node demo_phase <phase>` backup 等效（四階梯第 3 階）。
- [ ] offline 切換：Studio offline toggle 或 `ros2 param set /brain_node offline_mode true` → LLM 路徑秒回 canned、**不重啟、無 silent fail**；`offline_mode false` 還原 byte-identical。
  - ⚠ **整合待辦**：plan4 gateway offline 發布形態（topic）vs plan3 brain `offline_mode`（param）需在此核對一次（gateway 端 TODO 已標）；若未接通，退啟動前 env override（proven）。

---

## §5 speech HITL（plan3 H1–H5，純語音/TTS，no-motion）

- [ ] **H1** timeout 收緊：限速/拔網模擬 cloud 慢 → online 在 **≤6s** fallback 出聲（無 60s/15s 黑洞）。
- [ ] **H2** runtime offline 切換：`offline_mode true` 不重啟、走 canned、無 silent fail；`false` 還原。
- [ ] **H3** 五幕 canned + WAV cache：offline + 逐幕切 demo_phase → 每幕播對應桶台詞、cache hit latency≈0、safety 幕固定拒絕句。**先暖機**（T6）：tts_node 起後對五幕句各發一次 `/tts`（**禁 mid-session 重啟 tts_node**）。
- [ ] **H4** byte-identical：`offline_mode=False` + `demo_phase=all` → 超時仍「我聽不太懂」。
- [ ] **H5** env-offline 全鏈復驗（proven）：`LLM_ENDPOINT="http://127.0.0.1:1/" TTS_PROVIDER=piper ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' bash scripts/start_full_demo_tmux.sh`。
- ⚠ **台詞鎖定閘**：`DEMO_CANNED_TABLE` 目前是 §9.3 暫定句 + `PENDING Roy sign-off (6/15)`；**Roy 6/15 前簽核 15 句**後一次換上、彩排前 no late change。

---

## §6 Go2 motion HITL（**唯一含 motion 的段，Roy 授權 + e-stop 強制**）

> 序列 LOCKED：nav 段（D1→D2→D3，互為前置）先；confirm-wiggle（D4，無 nav 依賴）獨立分支。**T0 URDF authority 未排除前禁一切 motion。**

- [ ] **前置**：先跑 [no-motion 診斷 SOP](../navigation/2026-06-13-no-motion-diagnostics-sop.md) D1（`echo /tf_static` 確認 map→odom / odom→base_link 無雙 authority 衝突）；plan1 profiling 允許 nav 共存。
- [ ] **D4 confirm→wiggle**（gate S4）：gesture→OK→Go2 wiggle；目標 thumbs_up→OK→wiggle，30s 試不過退 proven **peace→OK→WeGo**；pending_confirm 30s timeout 不黑洞。
- [ ] **D1–D3 nav（upside，非 6/18 依賴）**：indoor_tight ±18° 安全錐 → initialpose θ_error<5° → 短距 **DriveOnHeading** n=3（0.3m 0撞0超衝）。**全程不發 `goto_relative`。**
- **e-stop / abort 條件**：非指令方向動作 / 停不下來 / 機鼻 <0.3m 仍動 → `emergency_stop.py engage` 或 `StopMove(1003)`。

---

## §7 Evidence capture checklist（每項 HITL 都收）

- [ ] `pawai evidence pull` 拉 `runtime/traces/*.jsonl`（只讀）。
- [ ] trace grep：`phase:s5_safety:gesture`（S1/S5 suppress）、`timeout_canned_rescue` / `real_trigger`（auto rescue）、`phase_switch:*`（切幕清理）。
- [ ] 每 HITL 記：日期 + speech_end→say_canned latency + 是否 silent fail。
- [ ] offline canned 出聲**錄影**（即「最終保底影片」素材）；S2–S5 各段 take。
- [ ] face sim 值、profiling CSV（config A/B/C）、S1 演法決策（branch）。

---

## §8 6/17 彩排總閘（go/no-go，plan5 T5-6/T5-7）

- [ ] 逐幕決定 `auto_advance_enabled` vs manual floor（**兩種都彩排**）。
- [ ] per-phase max_wait floor：S1 10–20s / S2 3–5s / S3 5–8s / S4 8–10s / S5 3–5s，逾時必有 canned（**never dead air**）。
- [ ] **硬閘**：§0 安全前置全過 + `pawai smoke full` **全綠** + 五幕順序不串台 → `git tag pre-618-checkpoint`；**main 6/17 18:00 凍結**。smoke full 紅 → 不打 tag、回滾上一綠 commit。
- [ ] 四階 rollback ladder 演練：auto → Studio hidden 鈕 → `ros2 param set` → `demo_phase=all` + 影片。

---

## §9 誠實底線（對外措辭）

- AFK 完成 = 「code merged + 單測綠（**needs-HITL**）」；只有本檔逐項真機過 = `proven`。
- S1 = FAILED→fallback；S5 = proven（6/10）；S2/S3/S4 = needs-HITL；S8 route_id = 已實作 byte-identical。
- **不 claim**：autonomous navigation / 全自動 live demo / 動態繞障 / D435+LiDAR 已融合 / fallen 偵測 / 2m 物體 / 可靠色彩。所有 nav 對外句綁 [`nav-618-claim-wording`](../navigation/2026-06-13-nav-618-claim-wording.md) S1-S8 / F1-F10。
