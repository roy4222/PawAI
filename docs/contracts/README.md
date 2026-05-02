# Contracts — 跨主線 ROS2 介面契約

> Brain 主線（pawai-brain/）與 Navigation 主線（navigation/）共同遵守的 topic / action / service / message schema。
> 任何感知模組或控制邏輯改動，**先改契約，後改 code**。

---

## 文件

| 檔案 | 內容 |
|------|------|
| [interaction_contract.md](interaction_contract.md) | 完整 ROS2 topic / action / message schema（v2.5 凍結，5/12 demo 主線） |

---

## 設計總則（抽自 archive/2026-05-docs-reorg/architecture-misc/CLAUDE.md+AGENT.md）

### Topic 形式：Event vs State

| 種類 | 用途 | QoS | 命名前綴 |
|------|------|-----|---------|
| **Event** | 一次性觸發信號（Intent recognized / Gesture detected / Goal reached） | RELIABLE，KEEP_LAST(10) | `/event/...` |
| **State** | 持續狀態快照（Face perception state 10Hz / Pose state） | BEST_EFFORT，KEEP_LAST(1) | `/state/...` |
| **Capability** | 能力閘門 Bool（Brain Executive 用於 pre-action validate） | RELIABLE，TRANSIENT_LOCAL（latched） | `/capability/...` |
| **Cmd** | 動作命令（Go2 driver / Nav 出口） | RELIABLE，KEEP_LAST(10) | `/cmd_vel`, `/webrtc_req` |

### Latched Topic（TRANSIENT_LOCAL）

- 慢頻、最後值即真相 → latched（如 `/capability/nav_ready`、`/state/perception/face`）
- 高頻、僅當下有效 → 非 latched（如 `/scan`、camera image）

### Correlation ID

- 跨節點關聯事件（語音 → Brain → 動作）→ 同一個 `correlation_id`
- 格式：UUID4 字串
- Speech intent → Brain skill plan → Go2 cmd 全鏈帶同一個 id

### 動作出口唯一原則

- 所有實體動作（Go2 移動、語音播放、頭部）**唯一出口在 Layer 3 Brain Executive**
- 感知模組只發 event/state，**不直接發 cmd**
- Safety Gate 在 Executive 內部（Pre-action Validate + Reactive Stop）

---

## 修改流程

1. 改 `interaction_contract.md` — schema、QoS、欄位定義
2. PR 通過 contract review
3. 各模組 implementation 跟進
4. CI `pre-commit topic contract check` 防止實作偏離

> **Pre-commit hook**：`scripts/hooks/git-pre-commit.sh` 會跑 contract check，commit 時自動驗證。
