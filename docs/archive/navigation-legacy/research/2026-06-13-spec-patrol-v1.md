# Spec：Patrol v1（固定路線多圈巡邏，research prototype）

> **日期**：2026-06-13　**狀態**：SPEC ONLY — Lane 6 T6-8②（**零實作碼**；spec 未過 Roy 審不開工）
> **上游**：[Lane 6 plan §6 T6-8](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)、[capability ladder C9](../2026-06-13-nav-capability-ladder.md)、[6/9 Phase 1.5 reactive patrol v0](../../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)
> **current label**：`PROTOTYPE`（patrol v0 = T6-3 的 run_route 單圈；本 spec 是其**之上的 v1**）——對外最多講「固定路線單圈巡邏 prototype（操作員監督）」，且**僅在 N5 跑通後**。

---

## 0. 根因前置：patrol v0 沒跑成的兩個前置缺口

patrol v1 建立在 **v0（run_route 單圈）跑通**之上；v0 自己還沒跑成，原因有二，spec 開頭先記，避免 v1 跳過 v0 直接設計多圈：

1. **routes 資料遺失**：`run_route` action 存在（[`nav_capability/nav_capability/route_runner_node.py`](../../nav_capability/nav_capability/route_runner_node.py)、[`go2_interfaces/action/RunRoute.action`](../../go2_interfaces/action/RunRoute.action)），但 routes 被歷次 deploy `--delete` 清掉（[master §2](../../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)）→ 從未跑過完整單圈。**v1 前置 = N1 重錄 + evidence pull 備份迴路**（[Lane 6 T6-2](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。
2. **居家空間太小 + orphaned-goal**：[trackB §5](2026-06-08-trackB-hitl-results.md) 記「最後沒拍到 Go2 走給你看」不是 nav 壞，是 orphaned-goal 累積（single-goal server + client double-shutdown）；route 是連續多 goal，orphan 問題會放大。**v1 前置 = N7 orphan 根治**（[Lane 6 T6-6](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。

> **硬閘**：N1（routes 恢復）+ N5（v0 單圈跑通）未達 → patrol v1 **不開工**。

---

## 1. Goal（spec 範圍）

在 T6-3 的「固定 route 單圈（操作員監督）」之上，把 patrol 擴成：**多圈 / 排程 / 中途暫停與恢復**——一條已錄的 route 能連續跑 N 圈、能由操作員暫停再續、能在 danger 停障後 operator-confirm 續走。**仍是固定路線**（route 是預錄的 named poses 序列），**不是自由巡邏、不是動態繞障**。

## 2. 三個能力增量（在 v0 之上）

| 增量 | 內容 | 依賴 v0 之外的前置 |
|---|---|---|
| **多圈** | 同一 route 連續跑 N 圈（`run_route` 加 `loops` 參數或外層排程）；每圈間 covariance 重檢（[ladder C7 / N2 SOP](../2026-06-13-nav-capability-ladder.md)） | 需較大空間才有意義（居家窄場一圈就到頭，[trackB §6 backlog 6](2026-06-08-trackB-hitl-results.md)：學校場地） |
| **排程** | 定時/事件觸發 patrol（非操作員每次手動發）——⚠️ **守護 30% 範疇，與互動主線分時**；觸發源與 Brain 的接口需另定 | Brain 接口（誰下令、台詞）不在本 lane（[Lane 6 §5](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)） |
| **暫停恢復** | patrol 中操作員暫停 → 續走；danger 停障 → operator-confirm 續走（**禁 auto-resume**，[ladder C5](../2026-06-13-nav-capability-ladder.md)） | N6 operator-confirm 流程驗過 |

> **明標需大場地的部分**：多圈與排程在居家客廳（淨空 ~1.1-1.5m，[trackB 頁首](2026-06-08-trackB-hitl-results.md)）幾乎無法展示——這兩項的 HITL 必須標「需學校/較大場地」，6/18 居家場景下**不承諾**。

## 3. Safety gate（patrol 開後的安全約束）

1. **每圈 covariance 重檢**：多圈累積會放大定位漂移；每圈起點重檢 covariance，YELLOW 不續圈（走 [N2 SOP](../2026-06-13-nav-capability-ladder.md)）。
2. **danger 停障 = operator-confirm，不 auto-resume**：patrol 遇障一律停、等操作員確認；tight space 下 `resume_policy=auto` 被 param 防呆拒絕（[Lane 6 T6-7](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。auto-resume 會 lunge 貼牆 0.21m（[6/9 §275](../../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)）。
3. **route 內每段限短距 + 低速**：route 的 named poses 間距承襲短距可靠性邊界（[ladder C1/C2](../2026-06-13-nav-capability-ladder.md)）；indoor_tight profile 必綁低速 ≤0.2 m/s（[ladder C6](../2026-06-13-nav-capability-ladder.md)）。
4. **operator + emergency_stop 全程待命**：patrol motion 全程操作員監督、`emergency_stop.py` engage 終端就位；非預期加速/方向 → abort（[Lane 6 §8 abort criteria](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。
5. **orphan 防線**：patrol 是多 goal 連續，client 必須走 N7 根治版（`signal_handler_options=NO` + 自管 cancel），否則中斷留 orphan 卡死整條 route。

## 4. HITL 升級條件（從 `PROTOTYPE` 往上）

| 階段 | 條件 | 升到 |
|---|---|---|
| v0 單圈 | [N5](../2026-06-13-nav-capability-ladder.md)：run_route 單圈跑通（indoor_tight 護航 + 操作員監督 + emergency_stop 待命）+ Studio 三層同框錄證據 | `PROTOTYPE` 有展示物（6/18 可講「單圈巡邏 prototype（操作員監督）」） |
| v1 暫停恢復 | patrol 中暫停→續走、danger 停→operator-confirm→續走，各一輪（居家可做） | v1 暫停恢復 `hardware_proven`（操作員監督限定） |
| v1 多圈/排程 | **需較大場地**：連續 N 圈無漂移失控、排程觸發可控 | post-6/18，需學校場地 HITL |

## 5. 禁 claim（forbidden，與 demo snapshot 一致）

- ❌ **「自由巡邏」「自主巡檢」**——patrol 是固定預錄 route，與自由巡邏嚴格區分（[ladder C9/C11](../2026-06-13-nav-capability-ladder.md)、[north-star §7](../../mission/2026-06-18-demo-north-star.md)）。
- ❌ **「巡邏中能動態繞障」**——遇障一律 stop-based 停、operator-confirm 續，不繞行。
- ❌ **「巡邏中障礙移開會自己繼續」**——auto-resume 禁用（lunge 不安全）。
- ❌ **v0 單圈未跑通（N5 未過）就講 patrol prototype**——[Lane 6 §13](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)：僅在 N5 跑通後可講。
- ❌ 在居家場景宣稱多圈/排程已達成。

## 6. 不做（scope 邊界）

- 不寫任何 patrol v1 實作碼（spec only）；v0 的 run_route 單圈本身是 T6-3 HITL，不是本 spec 的 code。
- 不改 `route_runner_node` / `run_route` action interface（多圈若做 = 加參數，屬 post-6/18 實作）。
- 排程的 Brain 接口（觸發源、台詞）不在本 lane。
- 不借 DimOS 整包（[6/9 §64](../../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)：DimOS 用 D435 VoxelGrid + 行為層做巡邏、非內建 LiDAR，值得借的是 VoxelGrid/FollowHuman/spatial-memory 概念，**非整包導入**，獨立 P2 研究）。
