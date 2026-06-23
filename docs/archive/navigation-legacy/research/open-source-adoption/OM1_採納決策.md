# OM1 採納決策（對 Go2 ROS2 Humble 專案）

更新日期：2026-03-02

## 結論

OM1 對本專案有幫助，但定位應為「上層任務與安全治理框架」而非「直接替換現有 Nav2/AMCL 導航主線」。

目前建議：

- 採納 OM1 的可觀測性與模式治理思路
- 延後 OM1 全棧接管與 Zenoh 優先遷移
- 拒絕在當前實機風險期做大規模架構置換

## 觀察依據（repo 事實）

1. OM1 本體是 AI runtime，不是單一導航堆疊：`OM1/README.md`
2. OM1 的 Go2 自主導航仍依賴外部 Nav2/SLAM 能力：`OM1/README.md`
3. OM1 內部存在 Nav2/SLAM 啟停 hook（HTTP API 形式）：
   - `OM1/src/hooks/nav2_hook.py`
   - `OM1/src/hooks/slam_hook.py`
4. OM1 在導航資料流上有 AMCL / goal_pose provider 思路：
   - `OM1/src/providers/unitree_go2_amcl_provider.py`
   - `OM1/src/actions/navigate_location/connector/unitree_go2_nav.py`
5. OM1 依賴集合重且版本鎖定明顯（含 `torch==2.6.0`、`ultralytics==8.3.156`、`eclipse-zenoh==1.4.0`）：`OM1/pyproject.toml`
6. 本專案現況主線為 ROS2 Humble + Nav2 + AMCL + DWB：`go2_robot_sdk/config/nav2_params.yaml`

## 採納 / 延後 / 拒絕

## A. 立即採納（Now）

### A1. 安全監督層（外圈）

- 目標：降低碰撞與停滯失控風險。
- 做法：在現有 Nav2 外部增加 deterministic safety supervisor（心跳逾時即停、topic freshness gate、cmd_vel 仲裁）。
- 原則：不改 Nav2 核心，不改 AMCL，不改 DWB 插件。

### A2. 模式與生命週期治理

- 借 OM1 mode/hook 思路建立本專案的 nav lifecycle runbook。
- 行為：mapping/navigation/guard 的進出場要有明確 gate 與 rollback。

### A3. 失敗分類與復盤標準化

- 對齊 OM1 的流程化運作優點，但保留本專案現有工具。
- 每次 failure 需能快速分類：感測、TF、costmap、controller、系統資源。

## B. 條件採納（Later）

### B1. 任務層語義導航接入

- 可借 `unitree_go2_nav.py` 的「文字目標 -> pose」流程。
- 僅作上層任務輸入，不直接接管底層控制回路。

### B2. Zenoh 互通

- 先做 shadow mode（旁路資料流），確認 topic 命名、時序與資源消耗後再評估主路整合。

## C. 暫不採納（Hold）

### C1. OM1 全棧替換

- 原因：現有實機仍在安全收斂期；整體替換會放大變數並降低可歸因性。

### C2. 在控制閉環中引入高不確定推理

- 原因：當前首要是 deterministic safety，不適合把非確定性決策放入主控制鏈。

## 兩週執行計畫（最小風險）

## Week 1（整合治理，不動核心）

1. 建立 `cmd_vel` 仲裁策略文件（優先序 + deadman）
2. 建立 topic freshness gate（scan/point_cloud2/amcl_pose/TF）
3. 建立 action watchdog（超時、無進展、重試上限）
4. 保持現有 stride A/B 測試流程不變

驗收：

- 50 次短距測試 0 碰撞
- ABORT 率下降（目標 <= 10%）

## Week 2（觀測與回復）

1. 固定 incident packet（rate、status、cmd_vel、odom、costmap snapshot）
2. recovery 固化：stop -> clear -> rotate -> retry once -> fail-safe stop
3. 完成一次 shadow mode 的 OM1 介面可行性檢查（不接主控制）

驗收：

- 100 次短距測試成功率 >= 95%
- 可在 10 分鐘內定位失敗類型

## 風險與防線

1. 依賴衝突風險：OM1 heavy deps（torch/ultralytics/zenoh）可能污染現有環境。
   - 防線：環境隔離，不在主測試環境混裝。
2. 通信複雜度風險：ROS2 與 Zenoh 同時運作會增加排錯成本。
   - 防線：先 shadow，後主路；先記錄，後控制。
3. 架構漂移風險：過早把 LLM runtime 拉進控制閉環。
   - 防線：保持任務層與控制層邊界。

## 最終建議

OM1 對本專案的正確使用方式是：

- 用它的治理與任務層思路強化現有系統
- 不在當前階段替換你的導航核心

先把現有 Nav2 主線做到「安全、穩定、可重現」，再做 OM1 深整合，收益最大且風險最低。
