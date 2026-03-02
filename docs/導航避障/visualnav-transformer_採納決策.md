# visualnav-transformer 採納決策（對 Go2 ROS2 Humble 專案）

更新日期：2026-03-02

## 結論

visualnav-transformer（GNM/ViNT/NoMaD）有研究參考價值，但不適合目前直接上你這條實機主線。

決策：

- 採納：模型/資料處理的局部概念（離線或 shadow）
- 延後：任何會進入控制閉環的 learned planner
- 拒絕（目前）：替換 Nav2/AMCL 主導航

## 觀察依據（repo 事實）

1. 部署路徑以 ROS1 Noetic 為主（`rospy`）且示例是 LoCoBot：
   - `visualnav-transformer/README.md`
   - `visualnav-transformer/deployment/src/navigate.py`
2. 運行模式依賴 topological map + image-goal，與目前 Nav2 座標目標流程不同：
   - `visualnav-transformer/deployment/src/create_topomap.py`
   - `visualnav-transformer/deployment/src/navigate.py`
3. 控制鏈是 `/waypoint` -> `pd_controller` -> `cmd_vel`，非 Nav2 controller plugin：
   - `visualnav-transformer/deployment/src/pd_controller.py`
4. 本專案當前主線是 ROS2 Humble + Nav2 + AMCL + DWB：
   - `go2_robot_sdk/config/nav2_params.yaml`

## 採納 / 延後 / 拒絕

## A. 立即採納（Now）

### A1. 資料前處理與時序視窗思路

- 借其影像前處理、context queue 設計，作為視覺實驗的離線基礎。

### A2. Shadow 評測框架

- 以 observer 身分跑 ViNT/NoMaD，不輸出到底盤。
- 目的：量測 latency、可行性、與 Nav2 差異，不改主線安全行為。

## B. 條件採納（Later）

### B1. 視覺子目標建議器（guarded advisor）

- 僅做子目標建議，最終仍由 Nav2 costmap + controller 決策。
- 必須具備 hard fallback（任一異常即回純 Nav2）。

## C. 暫不採納（Hold）

### C1. visualnav-transformer 直接接管 `/cmd_vel`

- 原因：會降低可解釋性與可重現性，與當前安全收斂目標衝突。

### C2. 直接 ROS1 流程移植到 ROS2 實機主線

- 原因：版本與中介層差異大，整合成本高且回歸風險高。

## 兩週建議路線

## Week 1

1. 完成現有 stride A/B 與 ABORT 收斂（主線不變）
2. 建立 visualnav shadow runner（離線/旁路）
3. 量測推理延遲與結果可行性（不下發命令）

驗收：

- 主線 0 碰撞
- ABORT <= 10%

## Week 2

1. 對比 shadow 提案與 Nav2 真實路徑差異
2. 定義 guarded advisor 的接受條件（必須 costmap-free + kinematic feasible）
3. 僅在低風險區域做小規模 gated 測試

驗收：

- 主線成功率 >= 95%
- ABORT <= 5%
- 無新增安全事件

## 風險與防線

1. ROS1/ROS2 差異風險：不做直接主線混接。
2. 非確定性控制風險：learned output 不可直通底盤。
3. 域偏移風險：LoCoBot/Topomap 假設不等於 Go2 室內場景。

## 最終建議

visualnav-transformer 對你目前最有價值的是「研究參考與 shadow 對照」，不是立即部署方案。

先把現有 Nav2 安全穩定指標做滿，再考慮以 guarded advisor 方式引入，這是最低風險路徑。
