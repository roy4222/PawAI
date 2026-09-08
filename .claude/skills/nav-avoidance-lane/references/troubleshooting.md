# 導航失敗模式

以下是歷史事故帶來的核對方向，需對應當前程式與 artifact：

- 安全來源沉默後，mux 可能選到持續發布舊速度的 teleop。查所有輸入與 timeout，不只看 nav 或最高 priority。
- 全部來源沉默後，driver／機體可能仍保留最後 Move。停止發布不是主動停止；查 watchdog 是否真的送出並驗證停止。
- hold_brake、progressive、released、disabled 與 legacy safety_only alias 的語意由當前 reactive_stop_node.py 決定。不要把永久 zero 與 clear-zone 沉默混成同一機制。
- 定位偏移先查 raw scan 朝向、TF owner、odom、時間與地圖；不能從一次碰撞斷言 AMCL 或某 SLAM 工具永久不可用。
- 不動先查命令在哪層被拒絕或覆蓋；不要以增加速度、縮短安全距離或反覆送 goal 當通用診斷。
- 殘留 driver／writer 需依程序來源與 ownership 定點處理；清 launcher parent 不保證子程序退出。

檢查本身不授權發動作。回歸測試要先有隔離環境或本次實機授權與停止安排。
