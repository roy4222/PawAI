# Brain／Studio 排查

- 變更沒生效：查執行程序的 revision、source／install 路徑、persona 安裝內容與環境。確認是否需要 build，再重啟本次擁有的程序。
- topic 不通：核對實際 ROS_DOMAIN_ID、DDS、overlay 與 publisher／subscriber；有 publisher 不代表有有效資料。
- 音訊問題：分開檢查 TTS artifact、格式、播放路徑與實際裝置；Go2 audio state machine 與本機 speaker 是不同路徑。不要每次都重開整隻狗。
- frontend 慢或失敗：看錯誤、資源與依賴狀態後處理，不先反覆 npm install。
- 殘留或 port 衝突：確認程序 owner、啟動來源與本輪範圍，再做針對性停止；不以 tmux kill-server 或廣泛 pkill 作通用修復。

舊測試結果與 fallback 設定只能當定位線索；修復後驗證本次需要的實際輸出。
