# NavDP 採納決策（對 Go2 ROS2 Humble 專案）

更新日期：2026-03-02

## 結論

NavDP 可參考，但定位為「研究/評測與局部技術來源」，不適合作為當前實機主導航替換方案。

決策：

- 採納：局部方法與工程模式（MPC/服務化接口/資料管線概念）
- 延後：任何會取代現有 Nav2 主鏈路的策略
- 拒絕（目前）：以 NavDP 端到端策略直接接管實機 Go2 主控制

## 觀察依據（repo 事實）

1. NavDP 主體定位是 sim-to-real 研究與基準框架：`NavDP/README.md`
2. 主要依賴 IsaacSim/IsaacLab 生態做評測：`NavDP/README.md`
3. 導航模型以 HTTP server 形式提供（非現成 ROS2 Nav2 插件）：
   - `NavDP/baselines/navdp/navdp_server.py`
   - `NavDP/eval_nogoal_wheeled.py`
4. 配置多數針對 wheeled/benchmark pipeline，而非你目前 Go2 Nav2 主線：
   - `NavDP/baselines/nomad/configs/robot_config.yaml`
5. 本專案現況為 ROS2 Humble + Nav2 + AMCL + DWB：`go2_robot_sdk/config/nav2_params.yaml`

## 採納 / 延後 / 拒絕

## A. 立即採納（Now）

### A1. 服務化接口思路

- 借 NavDP 的 server-client 分層模式，強化你現有測試/評測接口一致性。
- 用途：快速 A/B 評估不同規劃策略，不動主控制鏈。

### A2. MPC 跟蹤思路（旁路驗證）

- 借鑑 `logoplanner` 的 MPC 架構做旁路實驗，不直接接管 cmd_vel。
- 先用 replay/sandbox 比較穩定性與延遲。

### A3. 視覺深度管線參考

- 借 NavDP 中 depth-anything 相關資料處理思路，對照你現有 DA3 管線。

## B. 條件採納（Later）

### B1. NavDP 策略 shadow mode

- 僅做「建議軌跡」輸出，不直接控制機器人。
- 與 Nav2 同場對比成功率、ABORT、卡住時間。

### B2. 局部路徑輔助器

- 若現有 DWB/MPPI 調參後仍有系統性局部極小值問題，再評估小範圍接入。

## C. 暫不採納（Hold）

### C1. 端到端 mapless 直接上主線

- 原因：你目前任務是安全與可重現穩定，端到端替換會提高變數與風險。

### C2. 以 Isaac benchmark 指標直接等同實機可用

- 原因：benchmark 好不代表現場安全可控，仍需實機 gate 驗證。

## 實作原則（與當前專案對齊）

1. 不破壞現有 Nav2/AMCL 主線
2. 所有新策略先 shadow，再 guarded assist，最後才考慮主路
3. 每次只改一個變數，保留 rollback

## Gate（進階前硬條件）

1. 0 碰撞（固定回合測試）
2. ABORT <= 5%
3. 100 次短距成功率 >= 95%
4. 監控指標完整（scan/costmap/cmd_vel/odom/action status）

## 近期建議

1. 先完成你正在做的 stride=2 vs 1 固定座標 A/B
2. 完成現有 Nav2 的 watchdog + 有界 recovery
3. 再將 NavDP 策略以 shadow mode 接入對照

## 補充

已存在一份更細的轉移路線圖：`docs/navigation/NavDP_採納轉移路線圖.md`。
本文件作為「決策層摘要」，用於報告與執行邊界對齊。
