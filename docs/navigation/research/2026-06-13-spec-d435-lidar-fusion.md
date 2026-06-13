# Spec：D435 + LiDAR Fusion（近距盲區補償，research prototype）

> **日期**：2026-06-13　**狀態**：SPEC ONLY — Lane 6 T6-8①（**零實作碼**；spec 未過 Roy 審不開工，系統 [Phase 4 T4B-5](../../superpowers/plans/2026-06-11-phase4-robot-control-nav-hardening.md) 紀律）
> **上游**：[Lane 6 plan §6 T6-8](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)、[capability ladder C12](../2026-06-13-nav-capability-ladder.md)
> **歷史 spec**：[`specs/2026-05-03-d435-rplidar-fusion-detour.md`](../specs/2026-05-03-d435-rplidar-fusion-detour.md)（5/3 evening 漸進三段式設計，本 spec 是其在「先解兩根因」前提下的重寫）
> **current label**：`DO_NOT_CLAIM`（spec only）——對外最多講「研究路線已有 spec、屬 research prototype」。

---

## 0. 為什麼這份 spec 開頭就是「根因前置」

5/3 一整天的 detour demo（自動繞開靜態障礙）**沒拿到**，且 [`specs/2026-05-03-d435-rplidar-fusion-detour.md`](../specs/2026-05-03-d435-rplidar-fusion-detour.md) 的漸進三段式設計**卡在 Phase 3**。後續拆解（[`README.md` §42](../README.md)、[`plans/2026-05-04-phase2-dev-order-spec.md` §14](../plans/2026-05-04-phase2-dev-order-spec.md)）確認 detour 反覆失敗的根因**不是 D435 沒融合、不是 DWB 設計、不是場地、不是感測器**，而是兩個 nav 基礎 bug 串連。因此 **fusion 開工前必須先把這兩個根因解掉**，否則加再多感測器都會被同樣的 bug 擋住。

### 根因 B1 — `nav_action_server` 不 enforce max_speed

- **症狀**：0.5m goal 實際走 1.04m（[`README.md` §42](../README.md)、[`plans/2026-05-04-phase2-dev-order-spec.md` §14](../plans/2026-05-04-phase2-dev-order-spec.md)）。
- **後果**：goal 距離不可信 → 任何「停在障礙前 X m」的 fusion 邏輯都失準（停障點會超衝）。
- **fusion 前置條件**：max_speed 必須在 `nav_action_server` 層 enforce，goal 距離與實走距離誤差收斂到可預期範圍，**才談 fusion 提早停障**。

### 根因 B2 — AMCL 靜止不收斂（plateau）

- **症狀**：`update_min_d=0.10` 導致 AMCL 在靜止時不更新 → covariance 卡 YELLOW 不收斂（[`README.md` §42](../README.md)、[`research/2026-05-01-amcl-180-degree-diagnosis.md`](2026-05-01-amcl-180-degree-diagnosis.md)）。
- **後果**：costmap 對齊度差 → D435 marking 進 costmap 時，障礙的世界座標會漂 → fusion 的「在地圖上標障礙」失去意義。
- **fusion 前置條件**：covariance 有可靠收斂 SOP（[capability ladder C7 / N2](../2026-06-13-nav-capability-ladder.md)）；AMCL plateau 不解，fusion 進 costmap 是錯上加錯。

> **硬閘**：B1 + B2 任一未解 → fusion **不開工**。本 spec 後續所有路線都以「B1/B2 已解」為前提。

---

## 1. Goal（spec 範圍）

補 RPLIDAR-A2M12 的 **2D 平面盲區**——尤其矮障礙（地面雜物）與 LiDAR 安裝平面以下/以上的物體——用 D435 depth 作為**額外的障礙 observation source**，提升「停得更準 / 停得更早」的可靠性。**本 spec 的 fusion = 讓 safe-stop 更可靠，不是動態繞障**（繞障是 [ladder C11](../2026-06-13-nav-capability-ladder.md) `DO_NOT_CLAIM`）。

## 2. 兩條候選路線（比較，不預設選哪條）

| | 路線 A：costmap obstacle layer | 路線 B：depth → `/scan_d435` light 版 |
|---|---|---|
| **作法** | D435 直接當 Nav2 `local_costmap` 的 observation source（或 STVL voxel layer），3D marking + clearing | `depthimage_to_laserscan` 把 depth 壓成 2D `/scan_d435`，與 `/scan_rplidar` 一起餵 obstacle layer（[`README.md` §70 配置已設計](../README.md)） |
| **盲區補償** | 真 3D（高/低障礙都補） | 只補單一掃描高度帶（`scan_height` 窗） |
| **CPU/RAM** | 高（voxel layer + clearing 昂貴，Jetson 8GB 緊） | 低（單條 2D scan，[5/3 spec Phase 1 已驗工具鏈](../specs/2026-05-03-d435-rplidar-fusion-detour.md)） |
| **TF / 高度過濾風險** | 高（需精確 camera→base_link TF + 高度過濾，5/3 風險清單列過） | 中（`output_frame=camera_depth_optical_frame`，需對齊） |
| **與 RPLIDAR 衝突** | 兩 source 同層需 clearing 協調 | 兩條 scan 進 obstacle layer，clearing 各自 |
| **6/8 backlog 對應** | trackB §6 backlog 5「D435→local costmap 融合」 | trackB §6 backlog 5「depth→/scan_d435 進 obstacle layer + DenoiseLayer」 |
| **建議起點** | — | **B（light 版）優先 spike**：CPU 安全、工具鏈已驗、最小變更面；A 留作 B 不足時的升級 |

> 路線選定本身是 spike 的產出，不在 spec 預判。**6/9 Roy 已給 D435 fusion 的進度序**（[`2026-06-09-nav-vision-hitl-execution.md` §65](../../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)）：① D435 shadow test（**不動狗**，錄 `/scan_d435_shadow` vs `/scan_rplidar` 比 D435 補到哪些 RPLIDAR 漏障）→ ② 接 Nav2 local costmap（observation source 或 STVL voxel layer）→ ③ 靜態障礙 3/5 能否繞/更準停 → ④ reactive patrol。**今天不做、不准宣稱已融合。**

## 3. Safety gate（fusion 開後的安全約束）

1. **fail-closed 繼承**：D435 既有 `/capability/depth_clear` fail-closed gate（IE SafetyLayer 消費，擋 MOTION skill）**維持不動**；fusion 是「額外 observation」非「取代 depth_clear」。
2. **fusion 不得放寬 reactive_stop**：reactive_stop 仍是 stop-based、`angular.z=0`；fusion 只能讓 danger 觸發**更早/更準**，不能讓 Go2「停下後轉向」（[Lane 6 §5 Forbidden 1/2](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。
3. **誤偵防呆**：D435 depth 雜訊（地面反光/玻璃）不得造成「幽靈障礙永久停車」——需 clearing + DenoiseLayer，且 D435 source 必須可一鍵關（env/param），出問題退回純 RPLIDAR。
4. **emergency_stop 待命**：任何 fusion HITL motion 全程 `emergency_stop.py` engage 終端就位（[Lane 6 §8 abort 條 6](../../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。
5. **8GB 互斥**：fusion 增加感知負載，必須先量 RAM（路線 A 風險高）；nav stack 與 brain demo stack 互斥的鐵則不變。

## 4. HITL 升級條件（從 `research_prototype` 往上）

| 階段 | 條件 | 升到 |
|---|---|---|
| spec 過審 | Roy 審本 spec + B1/B2 已解 | 可開工（仍 `research_prototype`） |
| shadow 證據 | D435 shadow test：`/scan_d435_shadow` 補到 RPLIDAR 漏的障礙、無大量幽靈點（**Go2 不動**） | spec 路線選定 |
| costmap 接入 | D435 進 local costmap，靜態障礙停障點比純 RPLIDAR **更準/更早**（量化，n≥3） | `hardware_proven`（fusion-assisted safe-stop） |
| 繞障 | **不在本 spec 範圍**——繞障是 [ladder C11](../2026-06-13-nav-capability-ladder.md) `DO_NOT_CLAIM`，需另案（Nav2 Collision Monitor polygon footprint，trackB §6 backlog 4，demo 後 ~7/2） | — |

## 5. 禁 claim（forbidden，與 demo snapshot 一致）

- ❌ **「D435 已融合進 costmap」**——除非路線過 §4 costmap 接入並回填 [ladder C12](../2026-06-13-nav-capability-ladder.md)。
- ❌ **「融合後能動態繞障/繞行」**——fusion ≠ 繞障；繞障是 stop-based reactive_stop 做不到的（`angular.z=0`），且硬轉摔過狗（5/2）。
- ❌ **「三陣攝影機/三鏡頭參與導航」**——只有 2D RPLIDAR 進迴路；D435 是 fusion 才會加（[trackB §2](2026-06-08-trackB-hitl-results.md)：RGB/物體/人臉/語音與 nav goal 零連接）。
- ❌ 在 B1/B2 未解時宣稱任何 fusion 進度。

## 6. 不做（scope 邊界）

- 不寫任何 fusion 實作碼（spec only）。
- 不改 reactive_stop 4-mode 本體、不改 `nav_action_server` single-goal 模型（B1 的 max_speed enforce 修補歸 nav 基礎 bug fix，不在 fusion spec）。
- 不買新感測器、不重建 map。
