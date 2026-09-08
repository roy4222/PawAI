# CLI 指令入口

指令與 flags 以相關 subcommand 的 --help、repo 的 `docs/pawai_cli/README.md` 及 `tools/pawai_cli/` 為準。

- 環境／狀態：`pawai doctor`、`pawai status`。
- 模組入口：`pawai dev info <module>`。
- 已授權部署：`pawai jetson deploy --module <module>`。
- 已授權 demo：`pawai demo start`／`pawai demo stop`；先確認 lock 與控制面影響。
- 排查輸出：`pawai logs <module>`，額外 flags 查 help。

是否能省略 build 取決於真正 install／source 路徑與本次變更，不能假設 Python 修改永遠不需 build。不要把固定距離動作當成 CLI 健檢。遠端命令需明確傳遞 target workspace，不假設本機變數存在於遠端 shell。
