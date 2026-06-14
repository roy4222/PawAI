# Plan 5 — Post-Refactor HITL Closure / Rehearsal（HITL 收束 + 6/17 彩排 + 唯一確認 runtime 變更 + P1 證據）

> 日期：2026-06-13　狀態：PLANNED — 待 Roy 審核
> 角色：Cloud/Fable = planner+reviewer（讀 source、設計、切 task packet、定 tests/rollback/stop-conditions、review Codex 產出、對抗性查 overclaim/demo-break/safety、指示修正、整合）。Codex = builder（照 task packet 實作、寫測試、跑測試、小 commit/PR、回報 diff+test-result+risk；**不擴 scope、不改 runtime claim、未經明確標記且 Roy 授權不得動 Go2**）。
> Plan ID：`plan5`　計畫群：PawAI Pre-6/18 Final Execution（與 Cloud A demo-flow 五份、nav incident 兩份、Cloud B advanced 六份並行）

---

## 0. 本份在計畫群裡的位置（先讀，避免重複別人工項）

本份是 **HITL 收束層 + 6/17 彩排總閘 + 唯一確認 runtime bugfix（S8 route_id）+ P1 offline 證據**。**不重複**下列各 plan 的實作工項，只引用其 id 並承接其 HITL：

| 領域 | 真相 plan（不在此重做） | 本份承接 |
|---|---|---|
| phase 詞彙/切換清理/CLI/chip | `conductor`（T-C1~T-C4 / H-C1~H-C4） | 彩排時驗 phase gate 不串台、auto vs manual 二選一 |
| timeout 收緊 / canned 表 / WAV cache / runtime offline | `fallback`（T-FB-1~T-FB-5 / H-1~H-5） | 彩排日復驗 H-5 env-offline；canned 五句鎖定 |
| s1_nav profile / initialpose SOP / 短距 n=3 / 三層 fallback | `s1-nav`（T-S1-1~T-S1-6 / H1~H5） | nav motion HITL gate H1→H2→H3 整合進彩排 go/no-go |
| nav 撞牆根因 T0/R1/R2/R3/R5 診斷與修法 | `nav-motion-incident-root-cause-plan` + `nav-incident-runbook`（D0~D5 / P0-1~P0-3） | 彩排只消費「T0 已排除 + n=3 過」結論，不自己診斷 TF |
| 操作員逐幕 runbook（六欄表 / 三洞段 / 平台表） | `runbook`（T-RB-1~T-RB-9） | 彩排前置 dry-run；face/confirm/nav 三洞段交叉引用 |
| CLI v2（`pawai demo phase` / `demo mode` / `status brain` / `face delete`） | `lane3-cli-v2-completion-plan`（T3-5/T3-6/…） | **本份 T5-1 face delete .npz 修法是 Lane 3 T3-5 的 spec 來源**，實作落 Lane 3 |
| 進階能力 benchmark/證據（vision/gesture/pose/voice/security） | Cloud B `advanced-*`（A4/A7/G2/G3/P1/P2/V*/S*） | **本份 P1 段只承接 offline-only 證據，且明令不得 override demo flow** |
| nav 能力 label / 對外台詞 | `nav-capability-ladder.md` / `nav-618-claim-wording.md` | 只引用、不自定義 label/句 |

> **鐵律（每段標題旁掛）**：demo flow > advanced capability；nav safety > nav capability；honesty > appearance。AFK 完成的只能說「code merged + 單測綠」（needs-HITL），**只有 Roy 在場真機 HITL 過的才算 proven**。

---

## 1. Goal

讓 6/18 前最後一哩「HITL 收束 + 彩排」可靠落地：

1. **三個 post-refactor 洞各自閉合到誠實級別**：
   - **face**：B4 bug（CLI delete/rebuild 只刪 `.pkl` 不刪真正的 `.npz`）修法 spec + face_db 衛生 SOP + 發表日 re-enroll sim≥0.7。
   - **confirm**：現場先試目標路徑 `thumbs_up→OK→wiggle`、失敗立刻退已驗的 `peace→OK→WeGo`；台詞只講「比 OK 確認後執行」，不指定到未驗手勢。
   - **nav motion**：承接 incident plan 的 T0 排除 + n=3 gate，未過 → s1_nav 退遙控/影片。
2. **落地唯一確認的 runtime 變更**：Security **S8 route_id sanitize** — 經查 **已實作 + 已測 + 已含 security_smoke MOT-04**（見 §2），本份把它**收尾為「byte-identical 驗證 + read/write 雙路徑確認 + security smoke 跑綠」**，不重寫。
3. **6/17 彩排總閘**：依各 HITL 結果，**逐幕**決定 `auto_advance_enabled`（ENHANCEMENT，預設 OFF）vs **manual floor**（FLOOR：hidden Studio 按鈕 / `ros2 param set demo_phase`）。**兩種都要彩排到**，6/18 絕不押 auto-advance（Q6）。
4. **五幕全流程彩排 + `pawai smoke full` 綠 + tag `pre-618-checkpoint`**：五幕照順序、每幕只觸發該幕功能、不串台。
5. **P1 offline-only 證據/benchmark**（object 杯/瓶/手機混淆、gesture 誤觸 ROC、pose sitting precision、supervision 標註 MP4）——**全在 WSL offline、永不進 Jetson runtime、不得 override demo flow**。

**本份不寫 runtime code**（Cloud/Fable 是 planner+reviewer）。Codex 依本份的 task packet 實作 **唯二**會動到 code 的東西：T5-1（CLI face delete 補刪 `.npz`，歸 Lane 3 spec）與 T5-3（S8 驗證測試補強，若有缺口），其餘皆 SOP/決策表/證據腳本。

---

## 2. Current state（cite code file:line，已實際查證）

### 2.1 face B4 bug（已查證，Gotcha #3）
- CLI `face delete`：`tools/pawai_cli/pawai_cli/main.py:2018` 只 `rm -f /home/jetson/face_db/model_sface.pkl`。
- CLI `face rebuild`：`main.py:2045` 同樣只 `rm -f .../model_sface.pkl`。
- **真正的 embedding cache 是 `.npz`**：`face_perception/face_perception/face_identity_node.py:75-83`（`_resolve_*` suffix 邏輯：`model_path.with_suffix(".npz")`）、`:134` `np.savez(...)` 實際寫出。`model_path` 預設 `.../model_sface.pkl`（`:214`），但 train 後落 `.npz`。
- ⚠️ **repo 內無 `.npz`**：它是 **Jetson runtime 訓練產物**，`grep` repo 抓不到屬正常。**HITL 必須 `ls /home/jetson/face_db/` 在機上確認真實檔名**（可能是 `model_sface.npz`，也可能因版本不同有其它 cache），**未上機 ls 前不得在 delete 清單寫死 `.npz` 存在**。
- 既有測試 anchor：`face_perception/test/test_model_io.py:58/68/69`（`.npz`/`.pkl` 路徑解析已有測）。

### 2.2 Security S8 route_id sanitize（已查證 — 已實作 + 已測 + 已 smoke）
- 機制：`nav_capability/nav_capability/lib/route_validator.py:24-55` `sanitize_route_name()` — `os.path.basename` + 白名單 `ROUTE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")`（`:8`）；拒 `%`（percent-encoding，`:37`）、拒 `.`/`..`（`:40`）、拒 `/`、`\`（`:43`）、collapse 後再驗（`:46-48`）。
- **read 路徑已 wired**：`route_runner_node.py:233` `route_id = sanitize_route_name(route_id)`（`/nav/run_route` `_load_route`）。
- **write 路徑已 wired**：`log_pose_node.py:88/111/112` `sanitize_route_name(goal.name / goal.route_id)`（`/log_pose`）。
- **既有測試**：`nav_capability/test/test_route_validator.py:116`（合法 id 不變：`sample`/`route_1`/`my-route`）、`:135`（拒 `../etc/passwd`/`..`/`/abs/path`/`a/b`/`a\b`/`..%2f..%2fetc`/`%2e%2e%2froute`/`route;rm`/``/`.`）——**URL-encoded 變體已覆蓋**。
- **security smoke 已含**：`scripts/security_smoke.sh:128-132` `[MOT-04]` route_id `../evil` 拒絕手動驗證步驟。
- ⟹ **S8 在 code 層已完成**（Lane 5 T5S-2 已落地）。本份對 S8 = **驗證收尾**（跑既有測試 + security_smoke + 確認 byte-identical），**不重寫、不宣稱本份新建**。

### 2.3 phase / canned / timeout / nav（引 source plan，code 已查證）
- phase gate：`interaction_state.py:33` `PHASE_ALLOWED_KINDS`；`brain_node.py:311-321` runtime set callback（unknown phase 拒絕保留舊值）、`:331-351` `_DEMO_PHASES`/`_phase_allows`、`:1348/1747/1945` gesture/greet/object 早退；`/brain/reset_context`（Empty）`:252`、`/brain/gesture_enabled`（Bool）`:258`。**詞彙擴充/切換清理由 `conductor` T-C1/T-C2 擁有，本份不重做。**
- canned 五句 + WAV cache + timeout：`fallback` T-FB-1~T-FB-5；timeout 事實 `llm_timeout=15s`（`llm_bridge_node.py:201`）、`openrouter_gemini_timeout_s` dataclass `tts_node.py:153`=60 dead-default vs env `:989`=6（實際生效 ~6）。**本份只在彩排復驗 H-5 env-offline、鎖定五句文字。**
- nav 撞牆：T0 URDF `go2.urdf:48-58/70-80` fixed joints → `/tf_static` 與 AMCL/driver 雙 authority 衝突（CO-PRIMARY）；R1 AMCL yaw 注入 forward；R2 0.5m→1.04m 超衝；R3 reactive slow-band 沉默；R5 gate yaw-blind（只查 c[0]+c[7] 不查 c[35]）。**全由 `nav-motion-incident-root-cause-plan` 擁有；本份只在 nav HITL gate 消費其「T0 已排除 + n=3 過」結論。**

### 2.4 既有可用 anchor（彩排直接用，不新建）
- `pawai smoke full`（`main.py:1292`）、`pawai smoke nav --static`（`:1153`，`--static` 必填）、`pawai smoke brain|vision|object`（`:924/968/...`，腳本對映 `_SMOKE_SCRIPTS` `:912-915`）。
- tag：repo 既有 `demo-2026-06-snapshot`、`post-demo-refactor-baseline-2026-06-10`；**`pre-618-checkpoint` 為新 tag**。
- `pawai evidence pull`（只讀 trace JSONL）、`pawai face list|enroll|rebuild|test`、`python3 scripts/emergency_stop.py engage`、`scripts/lidar_front_sector.py`。

---

## 3. Scope（本份做什麼）

1. face B4 修法 spec（補刪 `.npz`，含「先 ls 機上確認真檔名」前置）+ face_db 衛生 SOP + 發表日 re-enroll HITL（sim≥0.7）。
2. confirm-wiggle HITL（目標 `thumbs_up→OK→wiggle` vs 已驗 `peace→OK→WeGo`），含 e-stop 與台詞鎖定。
3. **S8 route_id sanitize 驗證收尾**（byte-identical 確認 + read/write 雙路徑 + 跑 `test_route_validator.py` + `security_smoke.sh` MOT-04）。
4. 6/17 彩排總閘：逐幕 `auto_advance_enabled` ON/OFF 決策表（四級 rollback ladder：auto-advance → hidden Studio 按鈕 → `ros2 param set` → `demo_phase=all` + 影片），**auto 與 manual floor 都彩排**。
5. nav motion HITL gate H1→H2→H3（承接 s1-nav / incident plan），未過 → s1_nav 退層②/③。
6. 五幕全流程彩排 + `pawai smoke full` 綠 + tag `pre-618-checkpoint`。
7. P1 offline-only 證據：object 杯/瓶/手機混淆 benchmark（supervision，**永不上 Jetson runtime**）、gesture 誤觸 ROC、pose sitting precision、supervision 標註 MP4。

---

## 4. Forbidden scope（本份不做）

- ❌ 不寫/改 runtime code，**唯二例外**：T5-1（CLI face delete 補 `.npz`，純 string 改、歸 Lane 3）、T5-3（S8 測試補強，**僅在發現缺口時**——目前查證無缺口，預設只跑既有測試）。
- ❌ **不重寫 S8 route_id sanitize**（已實作）；不宣稱本份新建它；不把它當「新 runtime 變更」對外講（它是 byte-identical bugfix，已在庫）。
- ❌ 不 flip 其它 enforcement（S1 gateway auth / S2 Foxglove 降權 / S4 blacklist enforced）——全 default-off，唯 Roy 在 HITL 後點頭（B-5/B-6）。**唯一確認進 runtime 的是 S8**。
- ❌ 不重做 conductor/fallback/s1-nav/runbook/incident/Lane 3 的實作工項（只引用 id + 承接 HITL）。
- ❌ 不把 P1 證據/benchmark 當 P0；不讓 P1 override demo flow；supervision/metrics **永不進 Jetson runtime**（雙 OpenCV 違反 ≥0.8GB 餘量）；demo 錄影**絕不餵 LLM**。
- ❌ 不押 auto-advance 為 6/18 交付賭注（ENHANCEMENT，預設 OFF，逐幕）；manual hidden Studio 按鈕永遠是 FLOOR。
- ❌ 不把 goto_relative 當 S1 主線；任何 plan 不得依賴 goto_relative（NOT_DEMO_READY）。
- ❌ 不講 fallen/跌倒/guardian/emergency-alert（`enable_fallen:=false` 永久鎖）；不講自主導航 / 全自動 live demo / 2m 物體 / 可靠顏色 / 19 色 / 動態繞障 / auto-resume。
- ❌ **不對移動中 Go2 送 Damp(1001)**（會摔）；e-stop 走 `emergency_stop.py engage` + `StopMove(1003, rt/api/sport/request)`。

---

## 5. Tasks（總表，每項：id / task_type / P 級 / 檔案 / 測試 / rollback / demo_impact / needs_roy / needs_go2_motion）

> task_type：`pure_software`（WSL/開發機，無硬體）｜`jetson`（SSH 上 Jetson，無 Go2 motion）｜`go2_motion`（Go2 會動，e-stop 就位 + Roy 授權）。

### T5-1　CLI face delete/rebuild 補刪 `.npz`（B4 修法 spec → Lane 3 實作）
- task_type：**pure_software**（string 改 + 單測；上機 ls 屬 T5-2 HITL）
- 優先級：**P0**
- 檔案：`tools/pawai_cli/pawai_cli/main.py`（face delete `:2016-2019` 的 `rm -f ...model_sface.pkl` → 補 `model_sface.npz`；face rebuild `:2045` 同步）；新增/擴充 `tools/pawai_cli/test/test_face_commands.py`（無則新建）。
- 測試（**用 `rm -f` 故對「檔不存在」天生安全；測試驗指令字串 + 兩種機上存在情境的 mock，不靠「.npz 一定存在」的空斷言**）：
  - `test_face_delete_cmd_contains_both_pkl_and_npz`：斷言 delete 組出的遠端指令字串**同時含** `model_sface.pkl` 與 `model_sface.npz`（`rm -f` 形式，缺檔不報錯）。
  - `test_face_rebuild_cmd_contains_both_pkl_and_npz`：rebuild 同樣含兩者。
  - `test_face_delete_safe_when_npz_absent`（mock SSH 回 `.npz` 不存在）：指令仍含 `.npz`、`rm -f` 不因缺檔失敗（驗 idempotent，非 hardcoded「一定存在」斷言）。
  - `test_face_delete_removes_npz_when_present`（mock SSH 回 `.npz` 存在）：指令含 `.npz` 且 mock 確認該路徑被 `rm`。
  - 全用既有 mock SSH / `CliRunner`，**不真連 Jetson**；機上真檔名最終以 T5-2 `ls` 為準（未上機不斷言實際存在）。
  - `cd tools/pawai_cli && python3 -m pytest test/test_face_commands.py -v && python3 -m pytest -q`（全 CLI 測試不回歸）。
- rollback：`git revert <T5-1 commit>`（純 string 改，移除後回只刪 `.pkl` 現行為）。
- demo_impact：間接（修好才能讓 face re-enroll 乾淨 → S2 具名問候穩）；**不改任何 runtime node 行為**（只改 CLI 發出的 `rm` 字串）。
- needs_roy：否（spec + 單測）；**上機驗真實檔名屬 T5-2**。
- needs_go2_motion：否。
- 歸屬備註：實作 ticket 對齊 `lane3-cli-v2-completion-plan` **T3-5**（face delete B4 fix）。本份提供 spec + 測試契約；若 Lane 3 已排 T3-5，本 task 退化為「review Lane 3 PR 是否同時刪 `.pkl`+`.npz`」。

### T5-2　face_db 衛生 + 發表日 re-enroll（sim≥0.7）
- task_type：**jetson**（無 Go2 motion；訂 camera topic）
- 優先級：**P0**
- 檔案：無 code；產出 SOP 段交 `runbook` §8.6.1（本份提供步驟 + 機上 ls 前置）。
- 測試（HITL 機上）：
  - **先 ls 確認真檔名**：`ssh jetson-nano 'ls -la /home/jetson/face_db/'` → 記錄真實 cache 檔名（`.npz`/`.pkl` 實際存在哪些），回填 T5-1 delete 清單（**未 ls 不得寫死**）。
    - **若 ls 顯示 `.npz` 不存在**（例如剛 delete 完、face node 尚未重訓 → 只剩 person 子目錄、無 cache）→ **正常、非錯誤**：此時 cache 尚未生成，直接走下一步 `enroll → rebuild → 重啟 face node` 讓它**重訓生成新 cache**；`rm -f` 對缺檔安全（不報錯）。**若 ls 顯示是其它副檔名**（非 `.npz`）→ 停、回報真檔名、修正 T5-1 delete 清單後再 merge（見 Stop Conditions #2）。
  - `pawai face list` → 只剩 `roy`（無 `_backup*`/`old*` 幽靈目錄）。
  - `mv /home/jetson/face_db/*_backup* /home/jetson/face_db_archive/`（備份移出 `face_db` 外）。
  - `pawai face enroll --person-name roy`（訂 `/camera/.../color/image_raw`，與 demo camera 不衝突）→ `pawai face rebuild`（含 T5-1 後的 `.npz` 刪除；**T5-1 未 merge 前手動 `rm -f /home/jetson/face_db/model_sface.npz`**）→ 重啟 face node 重訓。
  - `pawai face test` → sim ≥ 0.7（記日期 + 數值）。
- rollback：sim < 0.7 → S2 退 **generic greet**（不秀具名）或還原前一晚 backup pkl/npz；幽靈目錄誤刪 → 從 `face_db_archive/` 還原。
- demo_impact：S2 具名問候的前置（needs-HITL，proven 僅一次 HITL#2 sim 0.87 / 6/8 0.73-0.81，脆）。
- needs_roy：**是**（機上 ls + enroll + 重驗）。
- needs_go2_motion：否。

### T5-3　S8 route_id sanitize 驗證收尾（byte-identical + read/write 雙路徑 + security smoke）
- task_type：**pure_software**（測試）+ **jetson**（security_smoke MOT-04 機上手動驗）
- 優先級：**P0**
- 檔案：**讀-only 驗證**（不改 `route_validator.py`，已實作）；若發現 read/write 任一路徑未 wired 或測試缺 case 才補 `nav_capability/test/test_route_validator.py`。
- 測試：
  - `cd nav_capability && python3 -m pytest test/test_route_validator.py -v` — 全綠（含 `:116` 合法不變、`:135` 拒 traversal/URL-encoded/shell-like，**100% reject bad / 100% pass good**）。
  - 確認 read 路徑 `route_runner_node.py:233` + write 路徑 `log_pose_node.py:88/111/112` 都呼叫 `sanitize_route_name`（grep 驗證，已查證存在）。
  - `bash -n scripts/security_smoke.sh`（語法檢查；CI 不跑此腳本）。
  - 機上手動（HITL）：照 `security_smoke.sh:129-132` MOT-04 發 `ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: '../evil', loop: false}"` → 確認被拒、**無 route 檔在 route root 外被開啟**。
- rollback：N/A（純驗證；若 T5-3 補了測試 → `git revert`，sanitize 行為不變）。
- demo_impact：無（byte-identical bugfix，安全縱深；**對外只講「route_id 已做路徑穿越防護」，不講新功能**）。
- needs_roy：否（pure 測試）；MOT-04 機上手動可由代操跑（無 Go2 motion）。
- needs_go2_motion：否。
- ⚠️ Cloud review 重點：**確認本 task 不被誤寫成「實作 S8」**——S8 已在庫（§2.2），本 task 是驗證，任何 PR 若新增 sanitize 邏輯即 overclaim，打回。

### T5-4　confirm-wiggle HITL（目標 thumbs_up→OK→wiggle vs 已驗 peace→OK→WeGo）
- task_type：**go2_motion**（Go2 wiggle 會動）
- 優先級：**P0**
- 檔案：無 code；產出 HITL checklist + 台詞鎖定段交 `runbook` §8.6.2 / `conductor` H-C3。
- 測試（HITL）：
  - 前置：`pawai smoke vision`（手勢 event 出得來）；`demo_phase=s4_gesture` + `gesture_enabled=true`；e-stop 就位。
  - 現場**先試目標** `thumbs_up→OK→wiggle`（param 路徑 `thumbs_up_demo_ack`）；30s 內未動或誤觸 → **立刻退已驗** `peace→OK→WeGo`（`peace_wego_confirm`）。
  - PendingConfirm `timeout_s=30.0`/`stable_s=0.5`（`brain_node.py:186`）→ 確認 30s 不黑洞、卡住可 `/brain/reset_context` 清。
- rollback：誤觸/連發 → `ros2 param set /brain_node gesture_enabled false`（cancel in-flight confirm，`brain_node.py:426`）；wiggle 不動 → 退 `peace→WeGo`；Go2 異常 → **e-stop**。
- demo_impact：S4（needs-HITL，目標路徑未驗）。**台詞鎖死**：只講「比 OK 確認後我就執行動作」，**不保證觸發手勢、不保證是哪個動作**（thumbs_up/wiggle 皆 needs-HITL）。
- needs_roy：**是**（Go2 motion + 手勢）。
- needs_go2_motion：**是**（e-stop 就位 + Roy 授權）。

### T5-5　nav motion HITL gate H1→H2→H3（承接 s1-nav / incident，未過退 fallback）
- task_type：**go2_motion**
- 優先級：**P0**
- 檔案：無 code；產出 gate 決策 + go/no-go 交 `s1-nav` H1/H2/H3 + `runbook` §8.6.3。
- 測試（HITL，**前置 = incident plan 的 T0 已排除 + D1-D5 全綠 + θ_error<5° + e-stop**）：
  - **H1**：indoor_tight ±18° 護欄重驗 — 正前障礙 → danger 停 0 撞、clear → 放行、右前家具 → 不誤擋（`lidar_front_sector.py` 佐證）。
  - **H2**：initialpose 朝向校正一輪 — LiDAR 紅點對齊牆 → covariance 進黃帶 → sanity 與目視一致。
  - **H3**：短距 `send_relative_goal.py` 0.3m × **n=3** 全 `reached`、**0 撞 0 暴衝**（撞牆根因的最終裁決）。
- rollback：任一發撞/走歪 → **立即 e-stop** → `pawai demo stop` → **s1_nav 退層②（遙控 + Studio 證據）/ 層③（純影片）**、claim 退保守（去「可靠」、不講「自主短距移動」）。
- demo_impact：S1（今天 0.3m 撞牆 = FAILED）。**只有 H1+H2+H3 全綠才允許 s1_nav 走 live 層①**；否則退 fallback。
- needs_roy：**是**。
- needs_go2_motion：**是**（e-stop + Roy 授權；T0 未排除前**禁任何 motion**）。
- 引用：根因與 T0 修法歸 `nav-motion-incident-root-cause-plan`（D0~D5 / P0-1~P0-3）；本份不自己診斷 TF。

### T5-6　6/17 彩排總閘 — 逐幕 auto_advance vs manual floor 決策表
- task_type：**jetson**（+ S1 段含 go2_motion 視 T5-5 結果）
- 優先級：**P0**
- 檔案：無 code；產出「逐幕 ON/OFF 決策表 + 四級 rollback ladder」交 `master` §12 Phase C + `runbook`。
- 測試（彩排日）：
  - 逐幕依 HITL 結果填 `auto_advance_enabled`（ENHANCEMENT，預設 OFF）；**每幕兩種都彩排**：(a) auto-advance guard/trigger/timeout/canned-rescue；(b) manual floor（hidden Studio 按鈕 / `ros2 param set demo_phase`）。
  - **per-scene auto-advance enable 數值 pass criteria（非主觀「看起來穩」，彩排當天逐幕對表）**：
    - **s1_nav**：不開 auto（FAILED→fallback，永走 manual/影片），N/A。
    - **s2_greet**：彩排 ≥3 次進幕，**≥3/3 次** stable known face（`identity_stable` sim≥0.7）在 `max_wait_s` 內觸發 entry-greet、0 次誤觸／串台 → 才可 enable auto；否則 OFF。
    - **s3_pose_object**：彩排 ≥3 次，**≥3/3 次** cup（object）在 `max_wait_s`(5–8s) 內觸發 remind、0 串台 → enable；否則 OFF。
    - **s4_gesture**：30s 內 **≥1 次高信心手勢（conf>0.9）** 觸發 prompt 且 0 誤觸（僅 S4 生效）→ enable；否則 OFF（退 manual）。
    - **s5_safety**：keyword/text rule-first（proven），auto 即「關鍵字一觸發即 reject」，**1/1 端到端拒絕** → 可 auto；LLM 永不 override。
    - **任一幕未達上述次數/信心 → 該幕 6/18 走 manual floor**（never bet auto，Q6）。
  - 驗 **one-keystroke disable**：逐幕 flag 可即時關（`ros2 param set` 或 Studio）；關掉後 manual floor 仍 100% 可用。
  - 驗 phase switch 清 `pending_confirm`/`active_plan`/`gesture cooldown` + trace transition type（消費 conductor T-C2）。
- rollback（四級 ladder，逐幕獨立）：auto-advance → hidden Studio 按鈕 → `ros2 param set demo_phase <phase>` → `demo_phase=all` + 影片。
- demo_impact：決定 6/18 控制面形態。**6/18 絕不押 auto-advance**（Q6）；FLOOR 單獨即可交付。
- needs_roy：**是**（彩排決策）。
- needs_go2_motion：S1 段視 T5-5（若 live 則 motion + e-stop）；S2-S5 否。

### T5-7　五幕全流程彩排 + `pawai smoke full` 綠 + tag `pre-618-checkpoint`
- task_type：**jetson**（S1 視 T5-5 含 go2_motion）
- 優先級：**P0**
- 檔案：無 code；tag 動作 `git tag pre-618-checkpoint <sha>`（指向 6/17 凍結 commit）。
- 測試（彩排日，硬閘）：
  - 開場安全前置（`runbook` §8.0：Go2 停穩 / `pawai demo stop` 清 nav stack / D435 重插 / 8GB stack 交接 / e-stop 就位）。
  - 各 flag 設「發表態」（HITL 過則 presentation-ready；未過則 OFF）。
  - `pawai smoke full` **全綠**（`main.py:1292`）。
  - 五幕**照順序**（s1_nav→s2_greet→s3_pose_object→s4_gesture→s5_safety），**每幕只觸發該幕功能、不串台**（trace 驗 suppress 集合對 `PHASE_ALLOWED_KINDS`）。
  - 全綠 → `git tag pre-618-checkpoint`；**main 凍結 6/17 18:00**，之後不進新 code。
- rollback：彩排任一幕翻 → 退該幕 fallback（S1 影片 / S2 generic greet / S4 peace 路徑 / 全域 `demo_phase=all`+`ism_enabled=false` byte-identical）；smoke full 紅 → 不打 tag、回滾到上一個綠 commit。
- demo_impact：**6/18 go/no-go 硬閘**（不可滑期、滑期 = hard stop）。
- needs_roy：**是**。
- needs_go2_motion：S1 段視 T5-5；其餘否。

### T5-P1a　object 杯/瓶/手機混淆 benchmark（supervision，offline-only）
- task_type：**pure_software**（WSL 隔離 venv，**永不上 Jetson runtime**）
- 優先級：**P1**
- 檔案：產出 `benchmarks/scripts/`（offline confusion-matrix 腳本，新建，不接 ROS2）+ `benchmarks/results/`（CSV）+ 證據文字；**不碰任何 runtime node**。
- 測試：
  - WSL 隔離 venv 跑 supervision ConfusionMatrix，輸出 cup↔phone↔bottle 雙向混淆 CSV（per-distance 0.7/1.0/1.5m）；replay demo 錄影離線 CPU 分析（**錄影絕不餵 LLM**）。
  - `python3 -m pytest benchmarks/` 不回歸（若新增腳本含可測函式）。
- rollback：刪除 `benchmarks/scripts/` 新檔（純加法，offline）；`git revert`。
- demo_impact：**無**（P1 證據，不 override demo flow）。對外只當「我們量化了混淆、知道邊界」的誠實佐證。
- needs_roy：否（AB-1 vision 主軸決策另計，不阻塞本 benchmark）。
- needs_go2_motion：否。

### T5-P1b　gesture 誤觸 ROC + pose sitting precision（offline-only）
- task_type：**pure_software**
- 優先級：**P1**
- 檔案：`benchmarks/scripts/`（gesture `min_conf×min_votes×stable_s` ROC 掃描、pose sitting confusion-matrix，新建 offline）+ `benchmarks/results/` CSV。
- 測試：
  - gesture：掃 ROC → false-trigger vs false-negative 曲線 + 標當前工作點（`0.7×3×0.5`）+ Pareto 建議（**post-6/18 候選，不進 runtime**）。
  - pose：sitting precision confusion-matrix + 門檻候選（**寫但不套用、不進 runtime**）。
  - `python3 -m pytest benchmarks/` 不回歸。
- rollback：刪新檔 / `git revert`。
- demo_impact：**無**（P1）。gesture/pose 門檻**一律不改 runtime**（B-4 鐵律：6/18 前不換 params）。
- needs_roy：否（觀測；門檻調整需 Roy + post-6/18）。
- needs_go2_motion：否。
- 禁區：pose `enable_fallen:=false` 永久鎖，**fallen 不量化為可 demo 能力**；只做 sitting，bending≠fallen 不混淆。

### T5-P1c　supervision 標註 MP4（offline-only 證據）
- task_type：**pure_software**
- 優先級：**P1**
- 檔案：`benchmarks/results/`（標註 MP4 輸出）+ 證據腳本 `benchmarks/scripts/`。
- **磁碟預算（WSL，非 Jetson）**：標註 MP4 全在 **WSL 本機 `benchmarks/results/`**，**不上 Jetson、不進 git LFS、不 commit 大檔**（`.gitignore` 排除 `benchmarks/results/*.mp4`，只 commit 腳本 + CSV）。處理前先 `df -h` 確認 WSL 餘量 ≥ 2× 來源錄影大小（annotate 輸出約等大）；來源 demo 錄影若 >2GB，先轉碼/裁剪段落再 annotate（避免一次處理 10GB 全片）。輸出僅作附件證據、不入版控。
- 測試：WSL 對 demo 錄影跑 supervision annotate → 輸出標註 MP4；確認**檔案產出 + 不接 ROS2 + 不上 Jetson + 不 commit 大 MP4**。
- rollback：刪輸出 MP4 / 新腳本。
- demo_impact：**無**（P1 證據；可當「能力可視化」附件，**非 demo 主線**）。
- needs_roy：否。
- needs_go2_motion：否。

---

## 6. Pure software tasks（純軟體匯總，WSL/開發機可完成、無硬體）

| Task | 為何純軟體 | 阻塞硬體？ |
|---|---|---|
| T5-1 | CLI `rm` 字串改 + mock SSH 單測 | 否（上機驗檔名屬 T5-2） |
| T5-3 | 跑既有 `test_route_validator.py` + `bash -n security_smoke.sh` + grep 雙路徑 | 否（MOT-04 機上手動可代操，無 motion） |
| T5-P1a/b/c | WSL 隔離 venv，supervision/benchmark offline，永不上 Jetson | 否 |

> 新增 core `.py` 受 blocking flake8（max-line=100）；CI fast gate 跑 speech/vision/benchmarks 純 Python 測試。**P1 benchmark 腳本不得 import rclpy / 不得接 runtime topic**。

---

## 7. Jetson tasks（no-motion，SSH 上 Jetson）

| Task | 內容 | 前置 |
|---|---|---|
| T5-2 | face_db 衛生 + re-enroll sim≥0.7（含**機上 ls 確認真 cache 檔名**） | nav stack 已 stop（8GB 互斥）；D435 健康（MIPI error 需重插） |
| T5-3（MOT-04 段） | security_smoke route_id `../evil` 拒絕機上手動驗 | nav lane 在跑（route_runner 起著）；無 Go2 motion |
| T5-6（S2-S5 段） | 彩排 phase gate 不串台 + auto/manual 二態 | brain demo 起著、Go2 停穩 |
| T5-7（S2-S5 段） | `pawai smoke full` + 五幕順序驗 | 開場安全前置全過 |

> 共同前置（handoff 2026-06-13 EOD）：**先確認 Go2 停穩 + `pawai demo stop` 清 nav stack**（剛撞牆 e-stop）；nav 與 brain **8GB 互斥**；D435 MIPI error → brain demo 前重插 USB。

---

## 8. Go2 HITL tasks（motion，e-stop 就位 + Roy 授權）

| Task | motion 內容 | 安全閘 | 未過 fallback |
|---|---|---|---|
| T5-4 | confirm → Go2 wiggle/WeGo | e-stop 就位；`gesture_enabled false` 可即時 cancel | 退 `peace→WeGo`（已驗）；台詞不指定手勢 |
| T5-5 H1 | indoor_tight 護欄（Go2 接近障礙） | e-stop；safe-stop 失效立即停 | 收更窄錐 / 退遙控 |
| T5-5 H2 | initialpose 朝向校正（可能微調朝向） | e-stop | 不發 goto，退層②/③ |
| T5-5 H3 | 0.3m × n=3 短距 | e-stop；**T0 未排除前禁 motion**；任一撞即停 | 退影片、claim 退保守 |
| T5-6/T5-7 S1 段 | 視 T5-5 結果決定 live 或 fallback | 同 T5-5 | s1_nav 退層②/③ |

> **硬規則**：① **不對移動中 Go2 送 Damp(1001)**；e-stop = `emergency_stop.py engage` + `StopMove(1003, rt/api/sport/request)`。② 任何 motion 前確認 **Roy 在場 + e-stop 物理可即時按到 + Roy 明確授權**。③ nav motion **T0 URDF authority 未排除前一律禁**（消費 incident plan D1 結論）。

---

## 9. Tests（彙整）

### 9.1 純軟體（CI fast gate / WSL，無硬體）
- T5-1：`cd tools/pawai_cli && python3 -m pytest test/test_face_commands.py -v`（delete+rebuild 字串同時含 `.pkl`+`.npz`）+ `python3 -m pytest -q`（不回歸）。
- T5-3：`cd nav_capability && python3 -m pytest test/test_route_validator.py -v`（100% reject bad / 100% pass good）+ `bash -n scripts/security_smoke.sh` + grep 雙路徑 wired。
- T5-P1a/b/c：`python3 -m pytest benchmarks/`（新腳本含可測函式時不回歸）；輸出 CSV/MP4 檔案產出驗證。

### 9.2 Jetson no-motion
- T5-2：`ls /home/jetson/face_db/` → `pawai face list`（只剩 roy）→ enroll → rebuild（含 `.npz`）→ `pawai face test` sim≥0.7。
- T5-3 MOT-04：機上發 `route_id: '../evil'` → 拒、無越界開檔。
- T5-7：`pawai smoke full` 全綠 + 五幕順序 trace 驗 suppress 集合對 `PHASE_ALLOWED_KINDS`。

### 9.3 Go2 HITL（motion）
- T5-4：confirm 目標→退 peace；30s 不黑洞。
- T5-5：H1 護欄 / H2 朝向 / H3 0.3m×n=3 0 撞。

### 9.4 回歸護欄（byte-identical）
- T5-1：face node 行為不變（只改 CLI `rm` 字串）。
- T5-3：sanitize 行為不變（不改 `route_validator.py`）。
- T5-6/7：`demo_phase=all` + `ism_enabled=false` + offline=false = 現行為（~955 tests 綠，消費 conductor/master byte-identical 退路）。

---

## 10. Rollback（逐 task 已附，全域如下）

| 層級 | 觸發 | 動作 |
|---|---|---|
| T5-1 | face delete 改錯 | `git revert <commit>` → 回只刪 `.pkl` |
| T5-3 | 誤改 sanitize | `git revert`；sanitize 行為本就不變 |
| face 退 generic | sim<0.7 | S2 不秀具名 / 還原 backup pkl+npz |
| confirm 退 | wiggle 不動 | 退 `peace→WeGo`；`gesture_enabled false` |
| nav 退 fallback | H1/H2/H3 任一未過或撞 | e-stop → s1_nav 退層②/③ + 影片；claim 退保守 |
| auto 退 manual | auto-advance 不穩 | one-keystroke disable → hidden Studio 按鈕 → `ros2 param set demo_phase` → `demo_phase=all`+影片 |
| 全域退保守 | 任一幕失控 | `demo_phase=all` + `ism_enabled=false` + offline=false（byte-identical 現行為）|
| P1 退 | benchmark 出包 | 刪 `benchmarks/` 新檔（純加法 offline，零 demo 影響）|
| tag 退 | smoke full 紅 | 不打 `pre-618-checkpoint`，回滾到上一綠 commit |

> 每一 rollback 都往**現行已驗行為**退，不引入新行為。

---

## 11. Done criteria

- [ ] T5-1：CLI delete+rebuild 同時刪 `.pkl`+`.npz`，單測綠；spec 對齊 Lane 3 T3-5。
- [ ] T5-2：機上 ls 確認真 cache 檔名、face_db 無幽靈目錄、re-enroll sim≥0.7（記日期+數值，needs-HITL）。
- [ ] T5-3：`test_route_validator.py` 全綠 + read(`route_runner:233`)/write(`log_pose:88/111/112`) 雙路徑確認 + security_smoke MOT-04 機上拒絕；**確認未誤寫成「實作 S8」**。
- [ ] T5-4：confirm 目標路徑現場試、失敗退 peace；台詞不指定手勢（needs-HITL）。
- [ ] T5-5：H1+H2+H3 全綠（0.3m n=3 0 撞）→ s1_nav 可 live 層①；否則退層②/③（needs-HITL，T0 前置）。
- [ ] T5-6：逐幕 auto/manual 二態彩排、one-keystroke disable 驗過、四級 ladder 鎖定。
- [ ] T5-7：開場安全前置全過 + `pawai smoke full` 綠 + 五幕順序不串台 + tag `pre-618-checkpoint`、main 6/17 18:00 凍結。
- [ ] T5-P1a/b/c：offline 證據產出（CSV/MP4），**全在 WSL、零 Jetson runtime、零 demo flow override**。
- [ ] 每幕能力分級標明（S1=FAILED→fallback、S2/S3/S4=needs-HITL、S5=proven、S8=已實作 byte-identical），對外 claim 綁 `nav-618-claim-wording.md` S1-S8/F1-F10。

---

## 12. Execution order

1. **純軟體先行（6/13-6/15 AFK，無硬體）**：T5-1（face .npz spec/單測）→ T5-3（S8 驗證收尾）→ T5-P1a/b/c（offline 證據，可並行）。
2. **Jetson no-motion（HITL 視窗）**：T5-2（face re-enroll，nav 清場後）→ T5-3 MOT-04 機上驗。
3. **Go2 motion（Roy 在場 + e-stop + T0 已排除）**：T5-5 H1→H2→H3（nav gate）→ T5-4（confirm wiggle）。
4. **6/17 彩排日**：T5-6（逐幕 auto/manual 決策）→ T5-7（五幕全流程 + smoke full + tag）。

> 跨 plan 依賴：T5-5 **依賴** `nav-motion-incident-root-cause-plan` 的 **T0 排除 + D1-D5 綠**；T5-6/7 **依賴** `conductor` T-C1/T-C2（phase 詞彙 + 切換清理）已 merge + `fallback` 五句 canned 鎖定；T5-2 **依賴** T5-1 或手動 `.npz` workaround。**本份不阻塞任何 lane 的純軟體 code（可與 conductor/fallback/Lane 3 並行）**。

---

## 13. Codex Implementation Prompt（AFK 起手）

> 角色：你是 builder。**只做下列 task packet 標 pure_software 的項**（T5-1、T5-3、T5-P1a/b/c）。**不得**動 runtime node 行為、不得改 nav claim、不得碰 Go2、不得擴 scope。每項：先寫/補測試（red）→ 最小實作（green）→ 跑測試貼結果 → 小 commit/PR → 回報 diff + test-result + risk。

1. **T5-1（先做，最小）**：在 `tools/pawai_cli/pawai_cli/main.py` 的 `face delete`（`:2016-2019`）與 `face rebuild`（`:2045`）的遠端指令字串，於 `rm -f /home/jetson/face_db/model_sface.pkl` **旁加** `model_sface.npz`（用 `&& rm -f .../model_sface.npz` 或單一 `rm -f ... .pkl .npz`）。新建/補 `tools/pawai_cli/test/test_face_commands.py`：用 `CliRunner` + mock `shell.run_remote`，斷言兩個命令組出的字串**同時含** `model_sface.pkl` 與 `model_sface.npz`。跑 `python3 -m pytest test/ -v`。**不改 face_identity_node。**
2. **T5-3（驗證，勿實作）**：跑 `cd nav_capability && python3 -m pytest test/test_route_validator.py -v` 貼全綠；grep 確認 `route_runner_node.py:233` 與 `log_pose_node.py:88/111/112` 都呼叫 `sanitize_route_name`；`bash -n scripts/security_smoke.sh`。**若全綠 → 不改任何 code，只回報「S8 已實作+已測，無需修改」**。僅在發現缺 case（例如新攻擊變體未覆蓋）才補 `test_route_validator.py` 的 parametrize。**嚴禁新增/改寫 `sanitize_route_name` 邏輯**。
3. **T5-P1a/b/c（offline，隔離）**：在 `benchmarks/scripts/` 新建 offline 腳本（supervision ConfusionMatrix / gesture ROC / pose sitting / annotate MP4），**不得 `import rclpy`、不得接 ROS2 topic、不得寫進 Jetson runtime 路徑**。輸出落 `benchmarks/results/`。確保新增 `.py` 過 flake8 max-line=100。

**回報格式**：每 task 回 `diff 摘要 / 測試指令+結果 / 風險（含是否觸碰 forbidden）`。任何需要動 runtime 行為、改 claim、碰硬體的念頭 → **停下、回報、等 Cloud 指示**。

---

# Codex Implementation Packet

### Packet A — T5-1 face delete/rebuild 補 `.npz`
- **exact files**：`tools/pawai_cli/pawai_cli/main.py`（`:2016-2019` delete cmd、`:2045` rebuild cmd）；`tools/pawai_cli/test/test_face_commands.py`（新建或擴充）。
- **exact change**：delete cmd 由
  `"rm -f /home/jetson/face_db/model_sface.pkl && "`
  → `"rm -f /home/jetson/face_db/model_sface.pkl /home/jetson/face_db/model_sface.npz && "`
  rebuild cmd（`:2045`）同步加 `.npz`；docstring `:2042` 文字可順帶提及 `.npz`（非必要）。
- **exact tests**：`cd tools/pawai_cli && python3 -m pytest test/test_face_commands.py -v && python3 -m pytest -q`
- **acceptance**：兩命令字串各含 `model_sface.pkl` 與 `model_sface.npz`；全 CLI 測試綠；無 runtime node 改動；flake8 過。

### Packet B — T5-3 S8 驗證收尾
- **exact files**：read-only（`nav_capability/nav_capability/lib/route_validator.py`、`route_runner_node.py`、`log_pose_node.py`、`scripts/security_smoke.sh`、`nav_capability/test/test_route_validator.py`）。**預期零 code 改動。**
- **exact commands**：
  `cd nav_capability && python3 -m pytest test/test_route_validator.py -v`
  `grep -n "sanitize_route_name" nav_capability/nav_capability/route_runner_node.py nav_capability/nav_capability/log_pose_node.py`
  `bash -n scripts/security_smoke.sh`
- **acceptance**：測試全綠；read+write 路徑 grep 命中；security_smoke 語法 OK；**回報「已實作，無需修改」**。僅缺 case 時補測試（不碰 sanitize 邏輯）。

### Packet C — T5-P1a/b/c offline 證據
- **exact files**：`benchmarks/scripts/*.py`（新建）、`benchmarks/results/*`（輸出）。
- **exact tests**：`python3 -m pytest benchmarks/`（含可測函式時）；輸出 CSV/MP4 存在性檢查。
- **acceptance**：腳本不 import rclpy、不接 topic、不寫 Jetson runtime 路徑；輸出落 `benchmarks/results/`；flake8 過。**零 demo flow 影響。**

---

# Cloud Review Checklist（Fable 審 Codex 產出）

- [ ] **Overclaim 掃描**：T5-3 PR 是否誤新增/改寫 `sanitize_route_name`？若有 → 打回（S8 已實作，本份只驗證）。
- [ ] **Demo-break 掃描**：T5-1 是否只改 CLI 發出的 `rm` 字串、未動 `face_identity_node`？P1 腳本是否確實不 import rclpy / 不接 runtime？
- [ ] **Safety 掃描**：任何 PR 是否偷渡 Go2 motion / Damp(1001) / 放寬 covariance 門檻 / flip 非 S8 的 enforcement？→ 打回。
- [ ] **Byte-identical**：T5-1/T5-3 對 runtime node 行為零影響；`demo_phase=all`+`ism_enabled=false`+offline=false 回歸測試綠。
- [ ] **Scope**：無「順便清理/重構」；每 task 有 tests + rollback；無 placeholder。
- [ ] **.npz 主張（conditional，非 hardcoded）**：T5-1 測試斷言 `.npz` 在**指令字串**（合理，因 repo 無 .npz）+ 兩種 mock 機上情境（存在/不存在皆 `rm -f` 安全）；**機上真檔名以 T5-2 ls 為準**，PR 不得宣稱已驗機上存在、不得寫「.npz 一定存在」的空斷言。
- [ ] **Claim wording**：S1/S4 任何文字綁 `nav-618-claim-wording.md`，無新增/放水句；S8 對外只講「路徑穿越防護」不講新功能。

---

# Stop Conditions（出現即停、回報、等 Cloud/Roy）

1. T5-3 發現 read 或 write 路徑**未** wired `sanitize_route_name` → 停（這會是 incident plan 範疇的安全缺口，需重評）。
2. T5-2 機上 ls 顯示 cache 檔名**不是** `.npz`（例如其它副檔名）→ 停、回報真檔名、修正 T5-1 delete 清單後再 merge。
3. 任何 Go2 motion task（T5-4/T5-5）前 **T0 URDF authority 未經 incident plan D1 確認排除** → **禁 motion**、停。
4. T5-5 H3 任一發撞牆/走歪 → **立即 e-stop、停 H3、s1_nav 退 fallback**。
5. `pawai smoke full` 紅（T5-7）→ **不打 tag**、停、回滾到上一綠 commit。
6. 任何 PR 觸及 forbidden（換模型 / live SLAM / fallen claim / 非 S8 enforcement flip / goto_relative 依賴 / P1 上 Jetson runtime）→ 停、打回。
7. 6/17 18:00 main 凍結後仍有未 merge 的 P0 → 停、走全域保守 fallback（`demo_phase=all` + 影片），不硬塞 code。

---

# Required Evidence（每項交付須附）

- T5-1：`pytest` 全綠輸出截圖/log + diff（顯示兩命令含 `.pkl`+`.npz`）。
- T5-2：機上 `ls -la /home/jetson/face_db/` 輸出 + `pawai face test` 的 sim 數值 + 日期（needs-HITL 證據）。
- T5-3：`test_route_validator.py` 全綠 + grep 雙路徑命中 + security_smoke MOT-04 機上拒絕的 terminal log。
- T5-4：confirm HITL 錄影（目標試 + 退 peace）+ 觸發路徑記錄（哪條動了 Go2）+ 日期。
- T5-5：H1/H2/H3 各輪 covariance / actual_distance / 0撞 結果，回填 `nav-capability-ladder.md` proven table。
- T5-6：逐幕 auto/manual 決策表（填好的）+ one-keystroke disable 驗證 log。
- T5-7：`pawai smoke full` 全綠 log + 五幕順序 trace（每幕 suppress 集合）+ `git tag pre-618-checkpoint` 的 sha。
- T5-P1a/b/c：CSV / 標註 MP4 檔案 + 「不接 ROS2 / 不上 Jetson」的 venv 隔離證明（pip list 或 import 檢查）。

---

# Rollback Plan（全域，逐 task 已於 §5/§10 附）

- **單一 flag 退保守**：`ros2 param set /brain_node demo_phase all` + `ism_enabled false` + offline=false → 回 6/10 已驗現行為（byte-identical）。
- **code 退**：T5-1/T5-3 任一 PR `git revert`，runtime node 行為本就不變。
- **HITL 退**：face→generic greet / confirm→peace→WeGo / nav→遙控+影片，全往已驗行為退。
- **彩排退**：smoke full 紅 → 不 tag、回滾上一綠 commit；6/17 18:00 後不進新 code。
- **P1 退**：刪 `benchmarks/` 新檔，零 demo 影響。
- **最終保底**：cloud 全崩 + runtime 開關失效 → env-offline（proven）→ 純影片 fallback（`demo-2026-06-snapshot`）。三層任一交付，不開天窗。
