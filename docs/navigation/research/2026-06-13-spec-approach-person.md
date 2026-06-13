# Spec：Approach Person（自主走向人，research prototype）

> **日期**：2026-06-13　**狀態**：SPEC ONLY — Lane 6 T6-8③（**零實作碼**；spec 未過 Roy 審不開工）
> **上游**：[Lane 6 plan §6 T6-8](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)、[capability ladder C12](../2026-06-13-nav-capability-ladder.md)
> **current label**：`DO_NOT_CLAIM`（spec only）——對外最多講「研究路線已有 spec、屬 research prototype」。
> **這是最遠的一條**：approach person 是「看到/聽到人 → 走到人身邊」，需要把感知（face/depth）與移動（nav）第一次真正接起來——目前**零連接**。

---

## 0. 根因前置：approach 為何現在連起點都沒有

1. **感知與 nav goal 零連接**：[trackB §2](2026-06-08-trackB-hitl-results.md) 明證——只有 2D RPLIDAR 進導航迴路；**RGB / 物體 / 人臉 / 語音與 nav goal 零連接**。approach person 要的「人在哪 → 算出 goal 座標 → 走過去」這條鏈**整條不存在**。
2. **短距移動本身還在 low-sample**：approach 的「走過去」底層就是短距 goto，而短距可靠性還停在 [ladder C1/C2](../2026-06-13-nav-capability-ladder.md)（n<3、discrete-step）；底層不穩，approach 無從談起。
3. **fusion 兩根因連帶**：approach 走向人時會遇到障礙，需要 safe-stop（甚至 fusion）可靠——而 fusion 卡在 [B1 max_speed 不 enforce + B2 AMCL plateau](2026-06-13-spec-d435-lidar-fusion.md)。
4. **「聽懂過來就走到身邊」是明文 forbidden claim**：[Lane 6 §13](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) 不可講清單已列「聽懂過來就走到 Roy 身邊」——這條 spec 存在的目的是把它**規劃成可開工的 research**，不是讓它變成 6/18 可講。

> **硬閘**：短距 n=3（[N3](../2026-06-13-nav-capability-ladder.md)）+ fusion B1/B2 解 + face/depth→map 座標鏈設計過審，三者全缺一不開工。estimate ~4-5 天新開發（[trackB §6 backlog 6](2026-06-08-trackB-hitl-results.md)），明確超出 6/18。

---

## 1. Goal（spec 範圍）

把「偵測到目標人 → 估算人的地圖座標 → 規劃並走到人身邊一個安全距離 → 停下」拆成可獨立驗證的開發階段。**目標距離留安全裕度**（停在人前 ~0.8-1.0m，不貼人）；**全程 safe-stop 兜底**；**不做跟隨**（follow 是持續追蹤，更遠，明確不在此 spec）。

## 2. 四層開發拆解（~4-5 天，沿 trackB §6 backlog 6 的「物體導向導航需 4 層」框架套用到人）

| 層 | 內容 | 接口 | 依賴 |
|---|---|---|---|
| **L1 目標偵測** | face/person 偵測產生「目標存在 + 影像 bbox」（face_perception 既有 `/state/perception/face`；person 走 object_perception COCO person） | 訂閱 face/object event | 既有感知（不改 node，只訂閱） |
| **L2 像素 → 地圖座標** | bbox + D435 depth → 相機座標 → TF 轉 base_link → 轉 map 座標（需 AMCL 定位準 = B2 解 + [N2 covariance SOP](../2026-06-13-nav-capability-ladder.md)） | depth + TF + `/amcl_pose` | B2 AMCL plateau 解；D435 depth 對齊 |
| **L3 規劃走過去** | 算出「人前 ~0.8-1.0m 的 goal」→ 發 `/nav/goto_relative` 或 named-pose 式 goal → 短距移動（底層 = [ladder C1/C2](../2026-06-13-nav-capability-ladder.md)） | nav_capability action | 短距 n=3 過（N3）；B1 max_speed enforce |
| **L4 接近時 safe-stop / 繞障** | 走向人途中遇障 → safe-stop 兜底（stop-based）；**繞障不在此 spec**（繞障 = [ladder C11](../2026-06-13-nav-capability-ladder.md) `DO_NOT_CLAIM`） | reactive_stop（不改本體） | safe-stop [ladder C4](../2026-06-13-nav-capability-ladder.md) |

> L1→L4 嚴格分階段、前一層沒過不進下一層（沿 [5/3 spec 的 gate 分明紀律](../specs/2026-05-03-d435-rplidar-fusion-detour.md)）。

## 3. 與 face / depth 的接口（不改既有 node）

- **face**：訂閱 `/state/perception/face`（人臉狀態 10Hz JSON）/ `/event/face_identity`（identity_stable 事件）——approach 只**消費**，不改 face_identity_node。known-face gate 可沿用 [Brain 6/8 greet gate 邏輯](../../../CLAUDE.md)（known + stable）。
- **depth**：用 D435 `aligned_depth_to_color`（[5/3 spec 用同一 topic 做 depth→scan](../specs/2026-05-03-d435-rplidar-fusion-detour.md)）取 bbox 中心深度；既有 `/capability/depth_clear` fail-closed gate **維持**（approach 不繞過它）。
- **Brain 接口**：「誰觸發 approach、走到後說什麼台詞」**不在本 lane**（Lane 6 = nav 能力；Brain 接線歸 IE / Lane 1 範疇）。本 spec 只定義 nav 側的 goal 估算與移動。

## 4. Safety gate（approach 開後的安全約束）

1. **目標距離留裕度**：goal = 人前 ~0.8-1.0m，**絕不**算出貼人/穿過人的 goal；L2 座標估算錯誤（depth 雜訊/人移動）必須 fail-closed（估不出可靠座標就不發 goal）。
2. **人會動**：人是動態目標，approach 過程人若移動，goal 過期——需重估或放棄，**不得追著移動目標連續發 goal**（那是 follow，不在 scope，且易失控）。
3. **safe-stop 不可繞過**：approach 的「走過去」全程 reactive_stop 兜底；遇障停下 = operator-confirm（[ladder C5](../2026-06-13-nav-capability-ladder.md)），不 auto-resume。
4. **短距邊界繼承**：單次 goal 距離承襲短距可靠性（[ladder C1/C2](../2026-06-13-nav-capability-ladder.md)）；長距離 approach = 多次短 goal，每次重估 + covariance 重檢。
5. **operator + emergency_stop 全程待命**：approach motion 全程操作員監督、e-stop 就位；非預期加速/朝人衝 → 立即 abort（[Lane 6 §8 abort criteria 條 1/5](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。

## 5. HITL 升級條件（從 `research_prototype` 往上）

| 階段 | 條件 | 升到 |
|---|---|---|
| spec 過審 | Roy 審本 spec + §0 三硬閘（短距 n=3 / fusion B1B2 / 座標鏈設計）全達 | 可開工（仍 `research_prototype`） |
| L1+L2 | 偵測到人 + 算出穩定的 map 座標（**Go2 不動**，純座標驗證，n≥3 不同位置） | 座標鏈 proven |
| L3 | 發 goal 走到人前 ~0.8-1.0m 停（單次、操作員監督、n≥3） | `hardware_proven`（approach 單次、操作員監督） |
| L4 + 整合 | 途中遇障 safe-stop 兜底；多次短 goal 重估接近 | post-6/18 |

## 6. 禁 claim（forbidden，與 demo snapshot 一致）

- ❌ **「聽懂過來就走到 Roy 身邊」**——[Lane 6 §13](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) 明文 forbidden；除非 L1-L4 全過並回填 [ladder C12](../2026-06-13-nav-capability-ladder.md)。
- ❌ **「自主找人 / 自動走向使用者」**——6/18 前最多講「研究路線已有 spec、屬 research prototype」。
- ❌ **「跟隨 / follow」**——follow 是持續追動態目標，不在本 spec（[CLAUDE.md](../../../CLAUDE.md)：跟隨是文件級 future work）。
- ❌ **「看到物體/人走過去」當已具備能力**（[trackB §6](2026-06-08-trackB-hitl-results.md)：需 4 層新開發 ~4-5 天，超出 6/18）。

## 7. 不做（scope 邊界）

- 不寫任何 approach 實作碼（spec only）。
- 不改 face_identity_node / object_perception_node / reactive_stop 本體——approach 是上層消費者。
- 不做 follow（持續追蹤）；不做繞障（[ladder C11](../2026-06-13-nav-capability-ladder.md)）。
- Brain 觸發/台詞接線不在本 lane。
- 不買新感測器、不重建 map。
