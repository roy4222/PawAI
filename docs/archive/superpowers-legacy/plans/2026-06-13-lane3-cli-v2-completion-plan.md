# Lane 3：CLI v2 完整化（smoke family + face 生命週期 + status 可信度）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)、[系統 Phase 5 plan](2026-06-11-phase5-productization-cli-cleanup.md)（5A——本 plan 把其中「對 6/18 直接有用且零 runtime 行為」的子集提前；Typer/pipx/三平台不提前）、[系統 Phase 3 plan](2026-06-11-phase3-vision-evidence-model-benchmark.md)（V3-3 採集腳本歸屬——本 plan 連 script 帶 wiring 一起做，覆寫原「script=Phase3、wiring=Phase5」切分）
> **Code 現實基準**：`tools/pawai_cli/`（click、173 tests ~0.7s、conftest 網路封鎖 + real_repo marker、errors.py structured hints、`_SMOKE_SCRIPTS`/`_LANE_HEALTHCHECK` pattern、face list/enroll/rebuild/test 已有）

---

## 1. Goal

把上機操作的人為錯誤面再砍一輪：**每個感知能力有一鍵 smoke**（不再靠記 ros2 指令）、**face_db 生命週期不出 CLI**（補 delete + 幽靈目錄防呆）、**status 反映 brain runtime 真相**（發表日「shadow 到底開了沒」一眼可見）、**demo start 不再讓 shadow 靜默斷流**。全部維持「CLI 包既有腳本/SSH、零 runtime 行為」的既定哲學。

## 2. Current state（code 實證）

- 命令樹：`doctor / status / dev info / jetson deploy / demo start|stop / health brain|nav / smoke brain / net wifi / logs / docs / contract check / readiness / evidence pull / face list|enroll|rebuild|test`。
- `pawai smoke brain`：SSH 上 Jetson 跑 `smoke_test_e2e.sh`（6/12 真機 5/5；#163-#165 修過 SSH env / 凍結檔 glob / tts race）。
- `pawai evidence pull`：rsync 拉 `runtime/traces/*.jsonl` + 印 events/suppressed/shadow 摘要。
- `pawai face`：list（掃 face_db 子目錄）/ enroll（headless 採樣）/ rebuild（刪 pkl 觸發重訓）/ test（pytest）；**無 delete、無幽靈目錄防呆**（`train_model` 把 `_backup*`/`old*` 當人名的已知坑只有文件記載）。
- `pawai status`：lock / tmux / Go2 driver process / 網路；**不顯示 brain runtime params**。
- 測試基礎：conftest 把未 mock 的 ssh/rsync 即時 `blocked-by-conftest`；`real_repo` marker；173 passed ~0.7s。
- 已知互斥事實：**nav stack 與 brain demo stack 8GB 互斥**（6/7 實證）——smoke 設計必須尊重。

## 3. Problems / gaps

1. `pawai smoke brain` 只覆蓋語音 e2e——vision/object/nav 壞了要等人工發現（6/12 stt 長期靜默死亡的教訓：**沒有 smoke 的 lane 就是會爛在那**）。
2. 發表日兩個已知坑無工具防線：① demo 重啟後 `ism_shadow_enabled` 歸 False（soak 斷流）② brain runtime flag 狀態（demo_phase / gesture_enabled / Lane 1 的 ism flags）無處可看，只能 ssh + ros2 param get。
3. face_db 生命週期缺口：不能刪人；備份目錄放錯位置會變幽靈身份稀釋 centroid（6/8 實證），CLI 不警示。
4. `pawai object test`：object 矩陣工具（`scripts/obj_matrix_cap.py` + `benchmarks/core/object_matrix.py`，6/9 已入庫）沒有 CLI 入口。
5. doctor 不驗 ROS env / 套件 import / colcon 狀態（deploy 後「以為 build 了其實沒有」仍可能發生）。

## 4. Scope

- `tools/pawai_cli/pawai_cli/`：`main.py`（新 subcommands）、`smoke.py`（若邏輯厚）、既有 `errors.py`/`modules.py` 沿用。
- `scripts/`：新 `smoke_test_vision.sh`、`smoke_test_object.sh`、`smoke_test_nav_static.sh`（Jetson 端執行體，與 CLI wiring 同 PR 或前後 PR）。
- `tools/pawai_cli/tests/`：每命令 mock 測試（argv/env/rc 斷言）。
- 文件：`docs/pawai_cli/README.md` 指令表同步（同 PR）。

## 5. Forbidden scope

1. **不做 Typer/Rich 遷移、pipx、三平台安裝**（系統 Phase 5 T5A-1/4/5——大遷移不進 5 天窗）。
2. **零 runtime 行為**：CLI 只包腳本/SSH/rsync；不改任何 node 程式碼。唯一例外 = B-7 的 `--with-shadow`（CLI 代下 `ros2 param set`，需 Roy 點頭）。
3. **smoke 不動 Go2 motion**：`smoke nav` 只做 static 檢查（拓撲/頻率/服務在位），不發 goal——motion 回歸是系統 Phase 4 的 HITL 範疇。
4. **不碰凍結三檔**；smoke 腳本是新增檔案，不修改 `start_full_demo_tmux.sh`。
5. 不做 lane scripts 升格 / preflight 統一 / session manifest（T5A-7，post-6/18）。
6. `smoke full` 不嘗試同跑 nav + brain（8GB 互斥）——full = demo lane 範圍。

## 6. Proposed tasks

| Task | 內容 | 優先 | 驗證 |
|---|---|---|---|
| **T3-1 `pawai smoke vision`** | 新 `scripts/smoke_test_vision.sh`（Jetson 端）：vision node alive → `/vision_perception/status_image` hz>0 → `/event/gesture_detected`、`/event/pose_detected` topic 存在且 publisher 在位 → 「static PASS」；`--with-events N` 選項=等真人觸發 N 事件（HITL 模式）。CLI wiring 仿 `_SMOKE_SCRIPTS` + `stream_remote`（#163 教訓：先 source setup.zsh） | P0 | mock 測試（argv/env）+ 真機 static 綠 |
| **T3-2 `pawai smoke object`** | 新 `scripts/smoke_test_object.sh`：object node alive → `/perception/object/debug_image` hz ≥3 → `/event/object_detected` publisher 在位；`--with-cup` 選項=60s 內收到 cup 事件（HITL 模式，沿 `capture_baseline_round.py percep` 口徑 + `--gesture-topic /__no_gesture__` 隔離坑） | P0 | 同上 |
| **T3-3 `pawai smoke nav --static`** | 新 `scripts/smoke_test_nav_static.sh`：nav lane 在跑時——nav nodes alive、`/scan_rplidar` hz ≥10、`/amcl_pose` 在、4 個 action server 列表在、reactive_stop status topic 在；**不發 goal、不動 Go2**；偵測到 brain demo lock 時直接 FAIL 並提示互斥 | P0 | mock 測試 + （nav 場測日順帶）真機一次 |
| **T3-4 `pawai smoke full`** | 串 brain → vision → object（demo lane 範圍）+ gateway `/health` + trace 落盤增長檢查；彙總各段 rc 為摘要表 + 單一 exit code；任一段失敗回非零 | P0 | mock（rc 彙總邏輯）+ 真機綠（6/17 回穩日的主工具） |
| **T3-5 `pawai face delete <name>`** | SSH 刪 `face_db/<name>/` →（自動）刪 `model_sface.pkl` → 提示重啟 face node 重訓；雙重確認（`-y` 跳過）；**附帶**：`face list` 加幽靈目錄警示（`_backup*`/`old*`/非人名模式 → ⚠ 提示移出 face_db） | P0 | mock 測試（rm argv 斷言 + 確認流）+ Jetson 實測一輪 delete→rebuild |
| **T3-6 `pawai status` brain 區塊** | status 加「Brain runtime」區塊：SSH `ros2 param get` 抓 `ism_shadow_enabled / ism_enabled / ism_stage_2*（存在才顯示）/ demo_phase / gesture_enabled / stranger_alert_enabled`；node 不在時顯示 `(brain not running)` 不報錯 | P0 | mock 測試（param get 輸出解析 + node 不在 fallback） |
| **T3-7 `pawai demo start` shadow 提示 / `--with-shadow`** | 最低限（零行為）：demo start 成功後印提醒行「shadow soak 需手動：ros2 param set …」。**B-7 Roy 點頭後**：`--with-shadow` flag = healthcheck 過後 CLI 代下 param set 並回讀驗證 | P0（提示）/ P1（flag） | mock 測試；真機：start --with-shadow 後 status 顯示 shadow=True |
| **T3-8 `pawai object matrix`** | wiring `scripts/obj_matrix_cap.py`（既有）：透傳 distance/object/duration 參數、輸出 CSV 路徑提示——上機矩陣日（Lane 4）的現場工具 | P1 | mock 測試（argv 透傳） |
| **T3-9 doctor 補強** | doctor 加：Jetson 端 `source setup.zsh && ros2 pkg list` 抽查核心套件（pawai_contracts/interaction_executive/go2_interfaces）、install tree 時間戳 vs 最新 commit 提示（「rsync 不 rebuild」坑的偵測線） | P2 | mock 測試 |

## 7. Pure software tasks（WSL，可 AFK）

全部 T3-1~T3-9 的腳本撰寫 + CLI wiring + mock 測試（conftest 已保證不打真網路；新測試遵守「全 mock `shell.stream`/`run_remote`」紀律——#150 教訓）。

## 8. Jetson / Go2 HITL tasks

不需 Go2。Jetson 各一次（併入 HITL #1 / 回穩日）：

| 項 | 內容 |
|---|---|
| HITL #1（6/14 晚，~15 min） | demo lane 跑著時：`smoke vision` / `smoke object` static 綠；`smoke full` 綠；`status` brain 區塊值正確；`face delete` 對測試身份跑一輪 delete→rebuild→重訓 |
| Lane 6 場測時段（B-9）順帶 | `smoke nav --static` 真機一次（是 Lane 6 HITL matrix 的開場儀式，不專排） |
| 6/17 回穩日 | `pawai smoke full` 作為回穩主工具跑全綠；`--with-shadow`（若 B-7 通過）驗證 |

## 9. Tests

- CLI 套件：新增 mock 測試全進 `tools/pawai_cli/tests/`，套件本機 <10s 全綠（173 → 增長）；未 mock 遠端呼叫 = `blocked-by-conftest` 即時紅。
- 腳本層：`bash -n` 語法檢查進 pre-commit 既有 hook；smoke 腳本各含 `--help`。
- 紅綠：每個 smoke 先寫「該 lane 不在跑 → 非零 + structured hint」的紅案例。
- 真機層：§8 各一次綠 run。

## 10. Rollback strategy

- 全部新增命令/腳本，獨立 PR revert，不碰既有 deploy/demo/health/smoke brain 路徑。
- `--with-shadow` 失敗（param set 不上）→ 印警告 + exit 非零，不影響 demo 本體已 running 的狀態；不想用就不帶 flag。
- smoke 誤判（false RED）的處置：smoke 只讀不寫，誤判不傷系統；修判定條件即可。

## 11. Done criteria

1. `pawai smoke vision|object|nav --static|full` merged + mock 綠 + 真機綠各一次。
2. `pawai face delete` + 幽靈警示 merged + Jetson 實測一輪。
3. `pawai status` 能回答「shadow 現在開著嗎、demo_phase 是什麼、ism stage 開了哪些」。
4. 6/17 回穩日以 `pawai smoke full` 為主工具完成全綠驗證。
5. `docs/pawai_cli/README.md` 指令表同步。

## 12. Execution order

T3-1/T3-2/T3-5/T3-6（並行，互不重疊）→ T3-4（依賴 1/2）→ T3-7 → T3-3 → T3-8 → T3-9。6/13-14 AFK 完成 P0；HITL #1 真機收尾。

## 13. 6/18 presentation impact

- 正面：發表日早上 `pawai smoke full` 一鍵確認全系統健康；`status` 確認 shadow 開著；`--with-shadow` 消滅最容易忘的坑。發表可講「任何隊友一條命令驗整機」。
- 風險：零（全 additive 工具）。
- 不可講：「CLI 已產品化／可 pipx 安裝」（系統 Phase 5）。

## 14. Fable review checklist

- [ ] 每個 smoke 經 `stream_remote` 且先 source setup.zsh（#163）；`ros2 topic pub` 類一律 `--times 2 -r 1`（#165）
- [ ] 新測試零真網路（conftest 斷言生效）；CLI 套件 <10s
- [ ] `smoke nav` 真的零 motion（grep 無 send_goal / cmd_vel）
- [ ] `face delete` 有雙重確認 + structured error hints；rm 路徑經消毒（不可能 `face_db` 外）
- [ ] `status` 在 node 不在/SSH 斷時優雅降級（fail-fast 訊息，不假成功）
- [ ] 8GB 互斥防線：smoke nav 偵測 demo lock、smoke full 不含 nav
- [ ] README 指令表同 PR 更新

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 3 Task <T3-x>（見 docs/archive/superpowers-legacy/plans/2026-06-13-lane3-cli-v2-completion-plan.md §6）。
紀律：
- CLI 只包既有腳本/SSH/rsync，零 runtime 行為；新 Jetson 端腳本放 scripts/。
- 仿既有 pattern：_SMOKE_SCRIPTS / stream_remote（先 source setup.zsh）/ errors.py structured hints。
- 測試全 mock shell.stream / run_remote（conftest 會擋真網路）；先紅後綠。
- 不碰 executive.yaml / start_full_demo_tmux.sh / .claude/skills/；不發任何 nav goal。
驗證命令：
  cd tools/pawai_cli && python3 -m pytest tests/ -q     # <10s 全綠
  bash -n scripts/smoke_test_*.sh
完成後：單 commit、PR 描述附紅綠證據 + 真機驗證步驟（給 Roy 的逐行指令）。不得 merge，等 Fable review。
```
