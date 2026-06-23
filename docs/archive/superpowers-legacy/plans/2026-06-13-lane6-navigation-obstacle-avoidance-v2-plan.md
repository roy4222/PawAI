# Lane 6：Navigation / Obstacle Avoidance v2（能力階梯 + 恢復 + 可展示推進）

> **日期**：2026-06-13　**狀態**：PLANNED — 待 Roy 審核
> **上游**：[aggressive master](2026-06-13-aggressive-pre618-master-plan.md)、[系統 Phase 4 plan](2026-06-11-phase4-robot-control-nav-hardening.md)（4B——本 plan 把其中**能力面**的子集提前：T4B-1 ladder / T4B-3 orphan / T4B-4 profile / T4B-6 rejection reason；**安全面**仍歸 [Lane 5](2026-06-13-lane5-robot-control-security-hardening-plan.md)）、6/8 Track B HITL（[`results`](../../navigation/research/2026-06-08-trackB-hitl-results.md)）、6/9 HITL（[`execution log`](2026-06-09-nav-vision-hitl-execution.md)）
> **與 Lane 5 的分界**：Lane 5 管「**誰可以**命令 nav」（action auth、route_id 消毒、gateway token）；本 lane 管「**nav 本身能做什麼**」（poses/routes、短距可靠性、safe-stop、stop-resume、fusion/patrol/approach、ladder、claim wording）。
> **安全鐵則繼承**：移動中禁 Damp；`emergency_stop.py` engage 是唯一移動中急停；teleop 嚴格 kill；`test_mux_priority.py` 不可在 full stack 跑；nav stack 與 brain demo stack **8GB 互斥**。

---

## 1. Goal

把 PawAI 的移動能力從「短距能走 + 安全停（各有單次證據）」推進到「**可靠（n 次重複）、可恢復（poses/routes 重建且不再丟）、可展示（短 route demo + 固定路線巡邏 prototype）、可解釋（拒絕有理由、能力有階梯）**」。同時把 D435+LiDAR fusion / patrol v1 / approach person 三條研究線寫成可開工的 spec（pre-6/18 不寫 code），讓 6/18 的 nav 宣稱每一句都有對應證據或明確標 prototype。

## 2. Current state（誠實盤點，全部有出處）

**Navigation evidence table（current label 是 6/18 claim 的唯一依據；標籤升級只能透過 HITL matrix 結果）**：

| Capability | Evidence | **Current label** |
|---|---|---|
| 0.3m short goto | 6/7 SUCCEEDED（actual 0.118m）；6/8 Track B `reached actual=0.270m`——少量 HITL 證據、無重複性數據 | **HARDWARE_PROVEN_LOW_SAMPLE** |
| 0.5m short goto | 6/9 indoor_tight 走過一次（safe-stop 場景中），樣本不足 | **NEEDS_RETEST** |
| 1.0m goto | 從未成功——AMCL covariance 0.45 黃帶抖、nav 閘 yellow 只准 ≤0.5m → 被拒且 Studio 靜默回 idle | **NOT_DEMO_READY** |
| safe stop（正前停障） | 6/9：goto 0.5m → danger 停 @0.78m、0 撞 0 暴衝；但 margin 薄（機鼻 ~0.4m）；**stop-based 不繞行** | **HARDWARE_PROVEN_WITH_LIMIT** |
| stop-resume | auto-resume 以 Go2 MIN_X ~0.5 m/s lunge、短 goal 貼牆 0.21m（6/9）；operator-confirm 流程 gateway 已實作（6/10 S1）未完整驗 | **NEEDS_FIX_OR_OPERATOR_CONFIRM** |
| indoor_tight profile（±18° 誤擋修正） | 6/9：front 0.97→1.22m、zone danger→slow；窄錐必綁低速 ≤0.2 m/s | HARDWARE_PROVEN_WITH_LIMIT |
| AMCL initialpose 重定位 | 6/10：`/api/nav/initialpose` 實測 amcl_pose 跳到設定點；covariance 收斂無 SOP | HARDWARE_PROVEN_LOW_SAMPLE |
| orphan goal 自癒 | 6/9：`no_progress_timeout`(~10s) + `goto_max_duration_s=120` backstop；client cancel 仍沒送出 | HARDWARE_PROVEN_WITH_LIMIT（client 側 NEEDS_FIX） |
| patrol（固定 route 單圈） | run_route action 存在；routes 資料已遺失、從未跑過完整單圈 | **PROTOTYPE**（T6-3 後才可講） |
| goto_named / run_route | code 在、poses/routes 被 deploy 清掉 → 目前空轉 | NOT_DEMO_READY（T6-2 恢復後 NEEDS_RETEST） |
| free roam / dynamic detour（自由巡邏 / 動態繞障） | 不存在——reactive_stop `angular.z=0` 只停不轉；硬轉曾摔狗（5/2） | **DO_NOT_CLAIM** |
| D435+LiDAR fusion / approach person | 僅 depth_clear gate（Brain 層）；fusion 5/3 L3 FAIL；approach 未開發 | **DO_NOT_CLAIM**（research spec only） |

**Nav2 / AMCL / map 現況**：nav2_bringup + AMCL + `home_living_room` map（Studio nav panel 用 v8 map PNG + px↔world 轉換）；`REACTIVE_PROFILE=open_space|indoor_tight` 一鍵 profile 已在 `start_nav_capability_demo_tmux.sh`；covariance 閘 0.3/0.5 門檻 hardcoded。

**named poses / routes**：**已被 6/11 起的 deploy `--delete` 全部清掉**（#166 已修 excludes，`runtime/` 不會再被刪，但資料已失）——demo route、goto_named、run_route 目前**全部空轉**，這是 Lane 6 的第一刀。

**D435 與導航的關係**：現在**只有** `depth_clear` fail-closed gate（`/capability/depth_clear`，IE SafetyLayer 消費，擋 MOTION skill）——**D435 沒有融入 Nav2 costmap**（forbidden claim 明列）。fusion 歷史：5/3 詳測 L3 FAIL，根因＝`nav_action_server` max_speed 不 enforce + AMCL plateau；6/8 backlog 另有 depth→`/scan_d435` light 版路線。

**工具**：`lidar_front_sector.py`（±15/20/30° 扇區 debug）、`send_relative_goal.py`（有 double-shutdown bug）、Studio nav panel（map + pose + reactive status + paused_confirm + initialpose/start/stop）。

## 3. Problems / gaps

1. **能力斷電**：poses/routes 遺失 → run_route / goto_named 不可用；無備份與還原 SOP（會再發生）。
2. **可靠性無數據**：0.3/0.5m 各一次；1.0m 被黃帶卡死且無 covariance 收斂 SOP（「該等 / 該推 / 該放寬」沒有決策表）。
3. **拒絕不可見**：goal rejection reason 被吞（`nav_not_ready` / `another_goto_active` / yellow-band 限距都裸 reject）→ Roy 在 S1 看到的「按了沒反應」。
4. **orphan client 債**：Ctrl-C 時 cancel 沒送出（rclpy SIGINT 先關 context），靠 server timeout 自癒——根治法已知（`signal_handler_options=NO`）沒做。
5. **stop-resume 半成品**：operator-confirm 流程在 gateway 有了，但「auto-resume 禁用」只是台詞沒有 param 防呆；A-9 終局未決。
6. **三條研究線零 spec**：fusion / patrol v1 / approach person 連可審的設計都沒有，post-6/18 想開工也沒起點。
7. **claim 漂移風險**：6/9 鎖過一版台詞，之後 S1 錄成（方式待補記 A-1）、poses 遺失——6/18 版需要重鎖。

## 4. Scope

- `nav_capability/nav_action_server_node.py`：goal rejection 結構化 reason（message 分流，server 側 only）。
- `scripts/send_relative_goal.py` + goto client：orphan 根治（signal handling）。
- 新診斷腳本：`scripts/nav_covariance_probe.py`（covariance 收斂曲線量測）。
- `tools/pawai_cli/`：`evidence pull` 把 Jetson `runtime/nav_capability/{named_poses,routes}` 納入拉回清單（備份面；CLI 實作但主題歸本 lane）。
- 文件：capability ladder、restore SOP、HITL matrix、三條研究 spec、claim wording（落 `docs/architecture/navigation/`）。
- runtime 資料：named poses / routes 重錄（HITL）。

## 5. Forbidden scope

1. **fusion / patrol v1（自由路線）/ approach person 不寫 code**——pre-6/18 只交 spec；spec 未過 Roy 審不開工（系統 Phase 4 T4B-5 紀律）。
2. **不做動態繞障**：reactive_stop 維持 stop-based；任何「停下後自動轉向繞行」禁止（5/2 摔狗教訓）。
3. **不開 auto-resume**：tight space 禁用維持；本 lane 只加 param 防呆與 operator-confirm 固化，A-9 終局 post-6/18。
4. **不動承重牆**：twist_mux 優先序、reactive_stop 4-mode 狀態機、StopMove 路由、single-goal 模型——只加 reason / 修 client bug，不重寫。
5. **不碰 covariance 閘門檻值**（0.3/0.5 hardcoded）——黃帶問題先用診斷 SOP + 設準 initialpose 解；放寬門檻是行為變更，需 T6-5 數據 + Roy 決策後另案。
6. **安全面不在本 lane**：nav action auth、route_id 消毒、cmd_vel 收斂、DDS——歸 Lane 5 / 系統 Phase 4。
7. Studio nav UI 擴張不在本 lane（rejection reason 的前端呈現走 Lane 2 Evidence 既有管道；nav panel 本體不動）。
8. 不買、不裝新感測器；map 不重建（v8 沿用，重建是大工程另案）。

## 6. Proposed tasks

| Task | 內容 | 載體 | 優先 |
|---|---|---|---|
| **T6-1 capability ladder + proven table** | 四級標籤（`wired_only` / `hardware_proven` / `demo_ready` / `research_prototype`）+ 逐能力標級表（短距 goto / safe-stop / stop-resume / goto_named / run_route / 巡邏 / approach / fusion），每格附證據路徑（§2 表為起點）或明標 research；A-1（S1 簿記）OPEN 項標注待補 | Fable 文件 | P0（純軟體） |
| **T6-2 poses/routes restore + 防再丟** | ① 重錄 SOP（指令級：`/log_pose` → named_poses → route 組裝 → 驗證）；② 備份面：`pawai evidence pull` 納入 `runtime/nav_capability/`（拉回即異地備份）+ restore 指令（rsync 推回）；③ HITL 執行重錄（客廳 2-3 個 named poses + 1 條短 route） | 文件 + CLI 小改（Codex）+ **Roy HITL** | P0 |
| **T6-3 short-route demo + patrol prototype v0** | 用 T6-2 的 poses/routes：`run_route` 單圈（reactive_stop indoor_tight 護航、操作員監督、emergency_stop 待命）→ 錄 Studio 三層同框證據 → 成功即是「**固定路線巡邏 prototype（操作員監督）**」，6/18 可講可展示 | **Roy HITL**（B-9 時段） | P0（HITL） |
| **T6-4 短距可靠性重驗** | 0.3 / 0.5 / 1.0m 各 **n=3** 重複（每發記 covariance、actual distance、結果）；1.0m 先走 T6-5 的 covariance SOP（設準 initialpose 等收斂進 green）再發；結果填進 proven table——0.5m 三連過 = `demo_ready` 候選 | **Roy HITL**（B-9 時段） | P0（HITL） |
| **T6-5 goal rejection reason + covariance SOP** | ① server 側 reject 帶結構化 reason（`nav_not_ready:covariance=0.45` / `another_goto_active:<id>` / `paused` / `yellow_band_limit:0.5m`），單測各路徑；② 新 `nav_covariance_probe.py`：initialpose 後 covariance 收斂曲線（靜置 vs 0.3m warmup 兩模式）；③ 產出黃帶決策表（該等 / 該推 0.3m / 該重設 pose） | Codex 純軟體 + HITL 驗 | P0（軟體） |
| **T6-6 orphan client 根治** | goto client `rclpy.init(signal_handler_options=NO)` + 自管 SIGINT → cancel → 單次 shutdown；修 `send_relative_goal.py` double-shutdown；驗證：goto 進行中 Ctrl-C → server log 有 cancel、立即可接下一筆 | Codex 純軟體 + HITL 驗 | P1 |
| **T6-7 stop-resume operator-confirm 固化** | ① param 防呆：`resume_policy`（`operator_confirm` 預設 / `auto` 僅大場地）——tight profile 下 `auto` 被拒絕（單測）；② HITL 驗 gateway paused_confirm 流程一輪（danger 停 → 操作員按繼續 → 續走）；③ A-9 終局決策材料整理（lunge 數據 + 兩案利弊一頁） | Codex 小改 + **Roy HITL** | P1 |
| **T6-8 三條研究 spec（不寫 code）** | ① **D435+LiDAR fusion**：必須先解 5/3 兩根因（max_speed enforce + AMCL plateau），路線比較（costmap obstacle layer vs depth→`/scan_d435` light 版），safety gate 定義、HITL 升級條件；② **patrol v1**：T6-3 單圈之上的多圈/排程/暫停恢復，需大場地的部分明標；③ **approach person**：4 層開發（~4-5 天）拆解、與 face/depth 的接口、禁 claim 條款 | Fable 文件（各一份，落 `docs/archive/navigation-legacy/research/`） | P1（純軟體） |
| **T6-9 REACTIVE_PROFILE 驗收矩陣文件** | 兩 profile（open_space / indoor_tight）每格：`front_arc_deg` / `danger_distance_m` / 速度上限 / 適用場地 / HITL 證據；硬規則成文（窄錐必綁低速 ≤0.2、param 只在 `__init__` 讀改 profile 必 kill 重啟、`lidar_front_sector.py` 為現場標準工具）；（B-9 時段順帶各重跑一輪 danger 停/clear 放行） | Fable 文件 + HITL 順帶 | P1 |
| **T6-10 6/18 claim wording** | nav 段台詞鎖定（§13 草稿）+ fallback 三層（live 短距 → 遙控輔助+Studio 證據 → 純影片）+ 與簡報對齊的一頁 | Fable 文件 + Roy 過目 | P0（純軟體） |

## 7. Pure software tasks（WSL，可 AFK）

T6-1、T6-2①②（SOP 文件 + CLI include）、T6-5①②（reason 分流 + probe 腳本 + 單測）、T6-6、T6-7①、T6-8（三份 spec）、T6-9（文件）、T6-10。**nav 的純軟體面其實很厚**——HITL 排不出來也能先把這些全部落地。

## 8. Jetson / Go2 HITL tasks（Roy 在場；全部需要 nav stack = 與 brain demo lane 互斥，需專屬時段 **B-9**）

### 硬性 abort criteria（任一觸發 = 當場中止該項，整段場測重新評估後才續；寫進現場 checklist 逐條勾）

1. **Go2 出現非預期加速 / 非命令方向移動 → abort**（emergency_stop engage，當日該能力標 FAIL）。
2. **reactive_stop 該觸發沒觸發**（障礙進 danger 區未停）→ **abort 全部後續 motion 項**，先用 `lidar_front_sector.py` 診斷。
3. **AMCL covariance 在黃/紅區（>0.3）卻要送 >0.5m goal → 禁送**（先走 T6-5 covariance SOP 收斂進 green；黃區只准 ≤0.5m）。
4. **stop-resume 放開後衝速明顯過快（lunge 重現）→ abort**，resume 項當日不再試、退 operator-confirm only。
5. **狗與障礙/牆距離小於安全距離（機鼻 <0.3m）仍在動 → abort**。
6. **operator 的 e-stop（`emergency_stop.py` engage 終端）未就位 → 不開始任何 motion 項**；每項開始前口頭確認「e-stop ready」。

**HITL matrix（場地：客廳 indoor_tight；開場儀式：`pawai smoke nav --static`（Lane 3 T3-3）→ goto 0.3m 一發暖身；abort criteria 全程生效）：**

| # | 項 | 內容 | 依賴 | 估時 |
|---|---|---|---|---|
| N1 | poses/routes 重錄（T6-2③） | `/log_pose` × 2-3 點 + 組 1 條短 route + `evidence pull` 驗備份 | — | 20 min |
| N2 | covariance SOP 實測（T6-5②③） | probe 腳本跑收斂曲線（靜置 vs warmup）→ 填黃帶決策表 | T6-5 軟體 | 20 min |
| N3 | 短距可靠性（T6-4） | 0.3/0.5/1.0m × n=3（1.0m 先用 N2 的 SOP 進 green） | N2 | 30 min |
| N4 | rejection reason 驗證（T6-5①） | 故意黃帶發 1.0m → `ros2 action send_goal` 回讀結構化 reason | T6-5 軟體 | 10 min |
| N5 | demo route + patrol v0（T6-3） | run_route 單圈（操作員監督 + emergency_stop 待命）+ Studio 三層同框錄證據 | N1 | 30 min |
| N6 | stop-resume operator-confirm（T6-7②） | route/goto 中置障 → danger 停 → Studio 按「繼續」→ 續走 | N1 | 15 min |
| N7 | orphan 根治驗證（T6-6） | goto 中 Ctrl-C → cancel 送達 → 立刻可接下一筆 | T6-6 軟體 | 10 min |
| N8 | profile 矩陣重跑（T6-9） | indoor_tight danger 停 / clear 放行 / 無誤擋各一輪 | — | 15 min |
| 收尾 | 還原 | nav stack 停 → `pawai demo start` + `smoke full` 確認 brain lane 無恙 | — | 15 min |

合計 ~2.5-3h（半天時段；N5/N6 是 stretch，時間不夠先砍）。**Go2 全程需要**（motion）；安全紀律見頁首鐵則。

## 9. Tests

- T6-5①：單測覆蓋每條 reject 路徑的結構化 message（紅綠：先斷言現狀裸 reject）；既有 nav_capability 測試零修改。
- T6-6：單測 SIGINT 路徑（mock context）+ 實機 N7。
- T6-7①：單測 tight profile × `resume_policy=auto` 被拒。
- T6-2②：CLI mock 測試（rsync argv 含 nav_capability 路徑；遵守 conftest 網路封鎖）。
- probe 腳本：`bash -n` / flake8；輸出 CSV 可重算。
- HITL matrix 每項有 PASS/FAIL 欄，結果寫回 proven table（T6-1）。

## 10. Rollback strategy

- **軟體項**：T6-5/T6-6/T6-7 各獨立 PR revert；reason 分流是 message additive（不改 accept/reject 邏輯本身）；`resume_policy` param 預設=現行為。
- **HITL 項**：全部現場可中止（emergency_stop.py engage / `pawai demo stop` 路由 nav lane cleanup）；任何一項 FAIL 不連坐——proven table 照實標、claim wording 對應降級。
- **資料項**：poses/routes 是 runtime 資料非 code，錄壞重錄即可；`evidence pull` 備份讓「再被清掉」變成可還原事件。
- **demo fallback 不受影響**：S1 影片已錄；nav 段三層 fallback（§13）任一層都能交付。

## 11. Done criteria

1. **ladder + proven table 成文**：每格有證據路徑或明標 research_prototype；0.3/0.5/1.0m 有 n=3 數據（或誠實標「未排到 HITL」）。
2. **poses/routes 恢復且有備份迴路**：`evidence pull` 拉得回、restore SOP 走得通。
3. **拒絕可見**：黃帶拒 goal 時 reason 可讀（CLI 層；Studio 呈現走 Lane 2 管道不阻塞本項）。
4. **短 route demo**：N5 跑通（= patrol prototype v0 有證據）或明確記錄未排到。
5. 三條研究 spec 落檔可審；claim wording 經 Roy 過目鎖定。
6. orphan / stop-resume 防呆 merged + 驗證（或標 post-6/18）。

## 12. Execution order

T6-1 + T6-10（文件先行，6/13-14）→ T6-5①② + T6-6 + T6-7① + T6-2①②（純軟體，6/14-15 AFK）→ **B-9 場測時段**（N1→N2→N3→N4→（stretch）N5→N6→N7→N8→還原）→ 結果回填 T6-1/T6-10 → T6-8 + T6-9（穿插，6/16-17）。

## 13. 6/18 presentation impact

**可講（各句綁證據）**：
- 「室內已知地圖、操作員下令的短距自主移動（0.3-0.5m）」——n=3 重驗後可加「可靠」二字。
- 「正前方障礙物安全停下、不碰撞」——**明講是 safe-stop，不是繞障**（「偵測到障礙會停下等待，不會繞行」是誠實且站得住的說法）。
- 「停下後由操作員確認再續走」（operator-confirm，6/9 既定）。
- 「固定路線單圈巡邏 prototype（操作員監督）」——**僅在 N5 跑通後**；與「自由巡邏」嚴格區分。
- 「每次導航拒絕都有可讀理由」（T6-5 後）。
- 「D435+LiDAR 融合 / 自主找人：研究路線已有 spec，屬 research prototype」。

**不可講（forbidden claims 延續 + 更新）**：自由巡邏、動態繞障/繞行、D435 已融合進 costmap、自動續走（auto-resume）、「聽懂過來就走到 Roy 身邊」、未經 n 次重驗前的「可靠導航」。

**fallback 三層**：① live 短距 goto / 短 route（B-9 驗過才上）② 遙控輔助定位 + Studio map/狀態作為操作證據 ③ 純影片（S1 已錄）。發表日用哪層 = B-10 決策（依 B-9 結果）。

## 14. Fable review checklist

- [ ] proven table 每格有日期 + 文件路徑級證據；無「未測但已宣稱」格
- [ ] T6-5 reason 分流不改 accept/reject 判定邏輯（message-only diff）；covariance 閘門檻值零變動
- [ ] T6-6 不引入第二套 signal 處理路徑（單一 shutdown 流）
- [ ] T6-7 param 預設 = 現行為；tight×auto 拒絕有單測
- [ ] HITL matrix 每項有中止手段與還原步驟；總時長 ≤ 半天
- [ ] 三條 spec 各含：根因前置、safety gate、HITL 升級條件、禁 claim 條款；**零實作碼**
- [ ] claim wording 與 demo snapshot forbidden claims 逐條對過、無放水
- [ ] 與 Lane 5 零重工（auth/消毒不在本 lane）；與 Lane 3 T3-3 / Lane 2 Evidence 的接口只引用不重做

## 15. Codex implementation prompt template

```
你在 /home/roy422/newLife/elder_and_dog（branch: 新開 feature branch）。
任務：執行 Lane 6 Task <T6-x>（見 docs/archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md §6）。
紀律：
- TDD 紅綠；nav_capability 既有測試零修改。
- T6-5 是 message-only：不改 goal accept/reject 判定、不動 covariance 門檻值。
- 不碰：twist_mux、reactive_stop 4-mode 本體、StopMove 路由、single-goal 模型、
  fusion/patrol/approach 的任何實作碼（spec 是 Fable 的事）。
- CLI 改動（T6-2②）遵守 conftest 網路封鎖、mock rsync argv。
- 不發任何真實 nav goal（HITL 是 Roy 的事）；腳本只做量測與工具。
驗證命令：
  python3 -m pytest nav_capability/test/ -q
  cd tools/pawai_cli && python3 -m pytest tests/ -q
  bash -n scripts/nav_covariance_probe.py 2>/dev/null || python3 -m py_compile scripts/nav_covariance_probe.py
完成後：單 commit、PR 描述附紅綠證據 + HITL matrix 對應項（給 Roy 的逐行指令含中止手段）。
不得 merge，等 Fable review。
```
