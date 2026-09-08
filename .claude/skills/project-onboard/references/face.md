# face 導覽

正式入口：repo 的 `docs/architecture/perception/face/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`face_perception/`，依問題使用 rg 定位相關實作與測試。

核對 RGB／depth 來源、frame、identity 與追蹤輸出。人臉框、辨識結果與深度有效性分開驗證；裝置編號及模型設定以本次環境為準。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
