# PawAI 系統架構 — 介面契約

> 跨模組技術契約與架構原則。

## 這不是模組，是契約庫

architecture/ 存放所有模組共用的介面定義。不擁有任何 ROS2 node。

## 核心契約

| 文件 | 位置 | 用途 |
|------|------|------|
| ROS2 介面契約 v2.1 | `contracts/interaction_contract.md` | **所有 topic/service/action 的 schema 和 QoS 定義** |
| Clean Architecture | `designs/clean_architecture.md` | Layer 2 模組分層原則 |
| 系統資料流 | `designs/data_flow.md` | 端到端資料流圖 |

## 三層架構

```
Layer 3（中控）：interaction_executive_node — 事件聚合、決策、Go2 指令
Layer 2（感知）：face / speech / gesture / pose / obstacle / object — 各自發 event + state
Layer 1（驅動）：go2_driver_node + D435 + Jetson — 硬體抽象
```

## 接手確認清單

- [ ] 讀完 `contracts/interaction_contract.md` 的 topic 列表
- [ ] 確認新 node 的 QoS 與 contract 一致
- [ ] 新增 topic 時同步更新 contract
