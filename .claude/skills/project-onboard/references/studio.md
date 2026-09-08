# studio 導覽

正式入口：repo 的 `docs/architecture/studio/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`pawai-studio/`，依問題使用 rg 定位相關實作與測試。

分開 frontend、gateway、adapter 與 robot consumer。查 UI 按鈕的後端副作用、event schema、權限與 trace；可點擊介面或 HTTP 200 不證明 robot 路徑安全。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
