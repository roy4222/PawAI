# 物體辨識 — Claude Code 工作規則

> 這是模組內的工作規則真相來源。

## 不能做

- Sprint Day 8 之前不要寫任何物體辨識程式碼（Hard Gate 未通過）
- 不要用 PyTorch FasterRCNN（舊方案已棄用）
- 不要超過 4-6h timebox

## 改之前先看

- `docs/辨識物體/README.md`（模組現況）
- `docs/辨識物體/research/2026-03-25-object-detection-feasibility.md`（可行性研究）
- `docs/superpowers/plans/2026-03-27-operation-b-prime.md` Task 8

## Go 條件

1. 前 7 天 baseline 穩定（Demo A 5 輪 >= 4/5）
2. Jetson RAM headroom >= 1.5GB
3. GPU 無持續滿載
4. D435 pipeline 不衝突
5. 半天內能完成 Phase 0
