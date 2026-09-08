---
name: nav-avoidance-lane
description: 啟停、診斷或規劃 PawAI 導航、建圖與避障的 runtime 場測時使用。
---

# 導航／避障 runtime

先確定本輪是觀察、建圖、定位還是受控移動；只讀研究或打開畫面不代表授權啟動完整導航。入口是本技能 `scripts/{preflight,start,healthcheck,cleanup}.sh`；從 repo root 使用 `.claude/skills/nav-avoidance-lane/scripts/` 完整路徑。

啟動前按需要查 [runtime topology](references/runtime-topology.md)、[sensor checks](references/sensor-stack.md) 及 [failure modes](references/troubleshooting.md)，並核對實際 launcher。mode 名稱不證明安全：`fallback` 的 standalone reactive controller 可能直接主動前進；preflight 通過也不是 movement 授權。

實體移動沿用根 AGENTS 的現場與當次授權條件。確認 writer、TF owner、scan 方向與停止路徑；不得有競爭 driver／teleop。保持 standalone reactive 與 Nav2 控制互斥。區分零速度、停止發布、cancel 與 StopMove，不能把其中一種當成全部。

依本輪行為收集資料與結果，明示哪些是靜態檢查、SIM 或實機觀察。移除障礙後是否恢復動作必須先由當前 controller 的狀態機與授權窗口決定，不套用舊版操作口訣。
