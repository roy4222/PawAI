# Odin-Nav-Stack 採納決策（對 Go2 ROS2 Humble 專案）

更新日期：2026-03-02

## 結論

Odin-Nav-Stack 對本專案有參考價值，但應採用「借概念、不搬整套」策略。

核心判斷：

- 立即採納 Odin 的工程思路（安全外圈、可觀測性、恢復流程）
- 條件採納部分局部策略（heading 對齊、障礙記憶衰減理念）
- 暫不採納整套 ROS1 Noetic 架構與 NeuPAN 直接接管

## 觀察依據（repo 事實）

1. Odin 主體是 ROS1 Noetic：`Odin-Nav-Stack/README.md`
2. Odin 自述導航模式中，標準 Nav1 / custom planner 標註「Not recommended, TODO」：`Odin-Nav-Stack/README.md`
3. Odin 的自訂 DWA優化實作存在：
   - `Odin-Nav-Stack/ros_ws/src/model_planner/src/local_planner/dwa_planner.cpp`
   - `Odin-Nav-Stack/ros_ws/src/model_planner/src/local_planner/local_costmap.cpp`
4. Odin 語義導航流程是 ROS1 topic/service 路徑：`Odin-Nav-Stack/ros_ws/src/yolo_ros/scripts/object_query_node.py`
5. 本專案現況為 ROS2 Humble + Nav2 + AMCL + DWB：`go2_robot_sdk/config/nav2_params.yaml`

## 採納 / 延後 / 拒絕

## A. 立即採納（Now）

### A1. 安全外圈（必做）

- 在 Nav2 外部做硬性安全治理（cmd_vel 仲裁、freshness gate、heartbeat timeout）。
- 原則：安全層可獨立停車，不依賴 planner 正確性。

### A2. 可觀測性與故障復盤

- 固化失敗包：action status、odom、cmd_vel、scan、costmap 快照。
- 每次 ABORT/卡住可在 10 分鐘內分類根因。

### A3. 有界 recovery 流程

- stop -> clear costmap -> rotate scan -> retry once -> fail-safe stop。
- 避免無限重試造成持續風險。

## B. 條件採納（Later）

### B1. Heading 對齊增強（小幅參數收斂）

- Odin 的 heading boost 概念，可映射到 Nav2 DWB critics 調參。
- 僅在單變數 A/B 下小步調整，不一次改多項。

### B2. 障礙物記憶衰減概念

- Odin 的 obstacle decay 思路有價值，但在 ROS2 Nav2 需以插件/旁路方式實現。
- 建議先做「觀測+模擬/回放驗證」，再進主路。

### B3. 語義導航流程借鑑

- 指令解析 -> 目標物查找 -> 相對偏移 -> 發導航目標，此流程可保留。
- 需重寫為 ROS2 版並保持任務層/控制層邊界。

## C. 暫不採納（Hold）

### C1. Odin 全棧直接移植

- 原因：ROS1 Noetic 與本專案 ROS2 Humble 主線差異大，變數過多。

### C2. NeuPAN 直接上實機主控制

- 原因：目前仍有實機安全與可重現性課題，先穩定基線再談新規劃器。

## 兩週執行計畫（與現有測試節奏對齊）

## Week 1

1. 完成 stride=2 vs stride=1 固定座標 A/B（12 段往返）
2. 記錄成功率、ABORT、卡住時間、碰撞/擦撞
3. 固化 incident packet 與失敗分類

驗收：

- 50 次短距任務 0 碰撞
- ABORT <= 10%

## Week 2

1. 小幅調整 heading 相關參數（一次只改一個）
2. 加入 watchdog + 有界 recovery
3. 完成 100 次短距回歸

驗收：

- 成功率 >= 95%
- ABORT <= 5%
- 0 實體碰撞

## 風險與防線

1. ROS1/ROS2 混搭風險：避免直接搬運 Odin 運行鏈。
2. 新 planner 導入風險：先確保當前問題不是感測/TF/時序造成。
3. 參數抖動風險：嚴格單變數 A/B，禁止同輪多項同改。

## 最終建議

Odin 對本專案最有價值的是「工程方法與局部策略」，而非替換導航核心。

先把你現有 ROS2 Nav2 主線做成可重現的安全系統，再逐步吸收 Odin 的局部優化，收益最大、風險最小。
