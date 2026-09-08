# 環境與部署

從 repo 的 `docs/runbook/README.md`、`docs/pawai_cli/README.md` 及 `tools/pawai_cli/` 查實際設定。區分來源 checkout、同步目的地、build/install space 與正在執行的程式；部署紀錄比遠端未同步的 .git 更能說明該次版本。

主機、GPU、ROS overlay、IP 與音效卡以當下檢查為準。source setup 必須匹配實際 shell；Python 或 launch 是否需 build 由安裝方式決定，不假設所有檔案都 symlink。只診斷本機時不自動 SSH、sync 或 deploy。
