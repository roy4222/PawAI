# 導航 runtime 接線

由本技能 `scripts/start.sh` 追當前 mapping／amcl／capability／fallback 分支與底層 launcher，列本輪實際啟用的 driver、scan、定位、planner、mux、safety consumer 和 writer。

mapping 也要核對是否啟 driver 或 UI goal tools；不能只看 mode 名稱宣稱 read-only。amcl／capability 涉及導航命令；fallback 的 standalone reactive 可直接發 cmd_vel 主動前進，不是停車模式，不能與 Nav2 控制並行。

查 map→odom、odom→base_link 與 sensor TF 各自唯一 owner，避免重複 publisher。核對 mux 的實際 priority、timeout 和所有 hot publishers；安全來源沉默時勝出者不一定是 nav。

每條停止路徑分開追到 driver：zero、cancel、停止發布、watchdog、StopMove。UI 顯示 stopped 或程序被清掉不能證明機體已停。
