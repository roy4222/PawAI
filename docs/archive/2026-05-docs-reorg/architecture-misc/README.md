# PawAI 系統架構

> Status: current

> 跨模組技術契約、架構原則、資料流。

## 文件索引

| 文件 | 位置 | 狀態 |
|------|------|:----:|
| ROS2 介面契約 v2.1 | [contracts/interaction_contract.md](contracts/interaction_contract.md) | **凍結** |
| Clean Architecture 分層原則 | [designs/clean_architecture.md](designs/clean_architecture.md) | 有效 |
| 系統資料流圖 | [designs/data_flow.md](designs/data_flow.md) | 有效 |
| v2.1 gesture enum 提案 | [proposals/v2.1-gesture-enum-ok-to-fist.md](proposals/v2.1-gesture-enum-ok-to-fist.md) | 提案 |

## 閱讀建議

- **整合者**：先看 contracts/interaction_contract.md
- **新模組開發者**：先看 designs/clean_architecture.md
- **Studio 開發者**：直接看 [Pawai-studio/](../Pawai-studio/README.md)

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| contracts/ | ROS2 介面契約（凍結文件） |
| designs/ | 架構設計原則 |
| proposals/ | 待決提案 |
| archive/ | 已被取代的舊設計 |
