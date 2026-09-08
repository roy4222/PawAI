# gesture 導覽

正式入口：repo 的 `docs/architecture/perception/gesture/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`vision_perception/`，依問題使用 rg 定位相關實作與測試。

追手勢偵測、事件與其 consumer；確認 cooldown／持續時間及 stop 等事件是否繞過仲裁直接寫 robot。模型精度或已發布事件不代表已安全執行。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
