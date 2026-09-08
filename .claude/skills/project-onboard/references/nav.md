# nav 導覽

正式入口：repo 的 `docs/architecture/navigation/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`nav_capability/`，依問題使用 rg 定位相關實作與測試。

依實際 launcher 追 map→odom→base_link→sensor 的唯一 TF owner，以及 planner→mux→driver 命令鏈。核對 scan 前向與停止行為；速度、mount、map 與安全距離需本次實測，不照搬歷史參數。standalone reactive 可能主動移動，hold_brake／progressive／沉默的語意以當前程式核對。停止服務不保證 StopMove；觀察任務不直接發 goal。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
