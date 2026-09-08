# 分層查連線

先從目前 CLI 設定與 doctor／status 確認目標，不套用舊 IP。分開查操作者主機→Jetson 的路由／SSH，以及 Jetson→Go2 的連線；前一段成功不能證明後一段。

SSH 失敗查主機身分、路由與授權；不要自動繞過 host key 驗證。Go2 ping 只證明 ICMP，可再依本次授權檢查 WebRTC transport 與單一連線占用。連線握手、有效資料與 robot 動作各自需要證據。

Tailscale 分享、ACL 或 IP 變更依本次請求處理，不能為診斷自行擴大網路存取。secret 與金鑰不得輸出到 logs 或回覆。
