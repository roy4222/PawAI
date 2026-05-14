# LoGoPlanner 採納決策（對 Go2 ROS2 Humble 專案）

更新日期：2026-03-02

## 結論

有幫助，但幫助是「局部工程能力」而不是「現在就取代主導航」。

決策：

- 採納：資料前處理、深度感知管線、MPC 方法論（先旁路）
- 延後：LoGoPlanner policy 接管局部規劃
- 拒絕（目前）：端到端主線替換 Nav2/AMCL

## 觀察依據（repo 與外部證據）

1. LoGoPlanner 以研究/基準框架形態提供，主流程為 server 推理：
   - `NavDP/baselines/logoplanner/logoplanner_server.py`
   - `NavDP/baselines/logoplanner/logoplanner_realworld_server.py`
2. 實機部署示例主要是 LeKiwi（3 輪全向車）而非 Go2 導航主線：
   - `NavDP/baselines/logoplanner/README.md`
   - `NavDP/baselines/logoplanner/lekiwi_logoplanner_host.py`
3. LoGoPlanner 依賴 IsaacSim/IsaacLab 生態與較重模型鏈路：
   - `NavDP/README.md`
4. 本專案目前問題是安全與穩定（status=6、卡住、感測稀疏），現有主線為 ROS2 Humble Nav2：
   - `go2_robot_sdk/config/nav2_params.yaml`

## 採納 / 延後 / 拒絕

## A. 立即採納（Now）

### A1. 深度前處理與品質控制思路

- 借 LoGoPlanner 在深度資料清洗、空洞補值、時間一致性處理的做法。
- 目標：改善局部感知輸入品質，降低 controller 無解軌跡機率。

### A2. 服務化 A/B 評估模式

- 借其 server-client decoupling 思路，建立你目前 Nav2 與實驗策略的可比較流程。
- 目標：同路線、同指標、可回放比較。

### A3. MPC 跟蹤方法論（shadow）

- 先作旁路驗證，不接管 `cmd_vel`。
- 目標：評估是否能降低局部抖動與停滯。

## B. 條件採納（Later）

### B1. Guarded-assist 局部建議器

- LoGoPlanner 僅輸出建議軌跡，由現有 Nav2 安全層裁決。
- 需滿足 safety gate 後才提升權限。

### B2. 限場景 pilot

- 僅在低風險區域啟用，保留一鍵 fallback 到純 Nav2。

## C. 暫不採納（Hold）

### C1. LoGoPlanner 直接接管主導航

- 原因：與你目前 ROS2 Nav2 主線差異過大，且實機可靠性與可維運性不足。

### C2. 用 benchmark 結果直接推論實機安全

- 原因：場景和硬體假設不一致，不能替代現場驗證。

## 兩週可執行計畫

## Week 1

1. 完成現有 stride=2 vs 1 固定座標 A/B（12 段）
2. 固化 incident packet（scan/costmap/cmd_vel/odom/action status）
3. 建立 LoGo shadow 評估腳手架（不控制機器人）

驗收：

- 0 碰撞
- ABORT <= 10%

## Week 2

1. 將 LoGo 輸出轉為「建議軌跡」記錄，和 Nav2 實際軌跡對比
2. 驗證 MPC 旁路性能（延遲、穩定性、可重現）
3. 確立 guarded-assist 的啟用/回退條件

驗收：

- 100 次短距成功率 >= 95%
- ABORT <= 5%
- 無新增安全事件

## 風險與防線

1. 架構風險：研究框架與現有主線耦合過深
   - 防線：先 shadow，再 guarded，最後才 pilot。
2. 模型風險：端到端輸出不可預期
   - 防線：安全層最終裁決，不允許直通底盤。
3. 資源風險：Jetson 8GB 算力/記憶體壓力
   - 防線：獨立環境與資源監控，先離線回放再上機。

## 最終建議

LoGoPlanner 對你有幫助，但要用在「提升方法」不是「替代核心」。

先把現有 Nav2 主線做到穩定可重現，再把 LoGoPlanner 以 shadow/guarded 模式逐步納入，才是低風險高收益路徑。
