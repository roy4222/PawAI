# Brain／Studio 組合與資源

從本技能 `scripts/start.sh` 追到 repo 的 `scripts/start_pawai_brain_tmux.sh` 與 `scripts/start_full_demo_tmux.sh`；mode 的完整 node 清單以實作為準。minimal 通常用於文字，e2e 增加語音輸出，full／demo 涉及感知與 robot driver；不要假設 minimal 就完全沒有可寫 robot 的 consumer。

Studio frontend、gateway、Brain、executive、ASR／TTS 是不同驗證層。查本次實際 engine／persona 及輸出，不套用舊版 full=legacy 或 full=LangGraph 的口訣。

driver、相機、音訊、tmux 與 port 是共享資源。start 可能自動 cleanup，handoff flag 可能只改提示；執行前讀相關分支與現行 ownership。cleanup 不應越過本次授權去結束其他人的 session。
