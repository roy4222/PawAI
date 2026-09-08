# 設定、shell 與裝置

由 CLI resolved configuration、相關 start.sh 與本次環境確認 host、workspace、gateway URL、frontend port、模型 provider 與 audio device。舊 .env 示例、port、卡號與 fallback chain 不是目前事實；不要輸出 secret 值來證明存在。

tmux server/session 的環境可能沿用舊值，啟動前核對本次命令實際收到的必要變數。source setup 要匹配實際 shell；source tree、install tree 與執行入口分開確認。

跨主機 UI 應以操作者能到達的 gateway endpoint 配置；HTTP 可達、WebSocket 接通、chat 與音訊成功分開驗證。音效卡會漂移，依當下裝置識別，不硬寫舊 card number。
