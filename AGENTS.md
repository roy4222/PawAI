# AGENTS.md — PawAI

PawAI 是 Unitree Go2 Pro 的 ROS 2 Humble 具身互動工作區。人類入口是 `README.md`；文件入口是 `docs/README.md`。回覆用自然臺灣繁體中文，先說結果與影響，區分已確認、推論與未驗。

## 工作與來源

依本次問題讀相關程式、測試、契約與模組 README；局部修改不要求完整上車。跨模組接手使用 `project-onboard`。正式規格在 `docs/contracts/`、`docs/architecture/`、`docs/adr/`，操作在 `docs/runbook/`、`docs/pawai_cli/`；歷史文件不代表當前狀態。

完成已授權範圍，包含修正本次造成的問題與適當驗證，不在第一版就停下等重複確認。依變更風險選驗證；隔離的本機測試與修復可直接繼續。文件修字不跑整套 ROS2。不得把本機／SIM 結果稱為硬體驗收。

保留其他人的變更；不順手復活 archive。安裝 Python 套件用 `uv pip install`；查找優先 `rg`。例外需記錄或上拋，不能靜默吞掉。

## 架構與實體邊界

- `go2_robot_sdk/go2_robot_sdk/domain` 不依賴 ROS2 或 presentation。
- `pawai_brain` 提出 intent；`interaction_executive` 負責安全裁決與單一動作出口，兩者透過 `pawai_contracts`，不互相 import。這是設計約束，現況仍需查 publisher、action client 與 launcher，不能只引用文件宣稱已成立。
- 不新增繞過仲裁的 cmd_vel／webrtc_req writer。啟動 dashboard、full demo 或 lane 可能同時啟動控制面，先查具體副作用。
- 真機動作需 Roy 當次明確授權、fresh 感測與場地／電量檢查、現場可停止的操作者；不能以讀碼、preflight 通過或舊場測代替。不得繞過安全、碰撞、確認閘門，或自行修改 firmware／Unitree 設定。
- 共用 driver、相機、音訊與 demo lock：只處理本次擁有或已授權的 session；接管他人資源需要協調與授權，不自動 force、廣泛 pkill 或 kill-server。
- 測試可能有 robot／SSH 副作用。尤其 nav integration 的 fake mux 測試不得直接在可達真機的 ROS graph 自動執行。

## 環境與驗證

部署前確認實際來源 checkout、target、目前程序與 deploy receipt；舊 WSL／Jetson 路徑、IP、GPU 或音效卡號不是現況。不要從舊記憶同步整個工作樹或覆蓋遠端修改。

ROS2 build／source 使用實際 workspace 與 shell；是否需 rebuild 依 install 方式與執行路徑判斷。純 Python 隔離測試不要求先上 Jetson。topic／interface 變更查 `scripts/ci/check_topic_contracts.py` 及受影響測試；launcher／driver 變更另外區分本機檢查與尚未執行的硬體驗證。

## Skills

內建 Skill 的正文與腳本維護在 `.claude/skills/`；Codex 可依下列路由直接讀對應 SKILL.md，其他 runtime 也使用相同來源：

- 接手／跨模組：`.claude/skills/project-onboard/SKILL.md`
- Brain／Studio runtime：`.claude/skills/brain-studio-lane/SKILL.md`
- 導航／避障 runtime：`.claude/skills/nav-avoidance-lane/SKILL.md`
- CLI／部署／鎖：`.claude/skills/pawai-cli/SKILL.md`
- 部署 smoke：`.claude/skills/jetson-verify/SKILL.md`
- 展示就緒：`.claude/skills/demo-preflight/SKILL.md`
- 套件測試：`.claude/skills/ros2-test-suite/SKILL.md`
- Review：`.claude/skills/reviewer/SKILL.md`
- 文件同步：`.claude/skills/update-docs/SKILL.md`

工程工作優先使用本次 runtime 已安裝且適用的 Matt Pocock Skills；不要假設固定別名或模型 wrapper 存在，也不要因缺 Skill 阻塞可完成的工作。
