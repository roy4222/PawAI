# brain 導覽

正式入口：repo 的 `docs/architecture/brain/README.md`；介面查 `docs/contracts/interaction_contract.md`。程式入口：`pawai_brain/pawai_brain/`，依問題使用 rg 定位相關實作與測試。

從 graph.py、conversation_graph_node.py、llm_client.py 定位當前 provider、persona、節點與 timeout。Brain 只 propose；追 proposal 至 executive 的實際 gate、trace 與測試，不依舊節點數或模型名稱判斷。

歷史研究與已移除的 archive 可以由 git history 追溯；不將舊 architecture-0511 路徑列為現行權威。實機能力以具名版本、設定與 artifact 為準。
