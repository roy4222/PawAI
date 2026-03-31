---
paths:
  - "go2_robot_sdk/**"
  - "go2_interfaces/**"
---

# go2_robot_sdk 模組規則

## 現況
- **狀態**：驅動層穩定，Clean Architecture 分層
- **主線**：WebRTC DataChannel 通訊（api_id 命令）

## 關鍵檔案
- `go2_robot_sdk/go2_robot_sdk/main.py`（go2_driver_node 主程式）
- `go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/webrtc_adapter.py`（WebRTC 通訊層）
- `go2_interfaces/msg/WebRtcReq.msg`（自訂 ROS2 訊息）

## 開發注意
- **兩個執行緒**：ROS2 executor（callback）+ asyncio event loop（WebRTC）
- **send_command()** 已正確處理跨執行緒（`run_coroutine_threadsafe`）
- **Megaphone 音訊**：4001(enter) → 4003(upload, 4096 base64) → 4002(exit)，msg type = `"req"`
- **Megaphone cooldown**：4002 EXIT 後 sleep 0.5s
- **多 driver instance 殘留**：`killall python3` 不夠，需 `pkill -9 go2_driver; pkill -9 robot_state`
- **Go2 OTA**：連外網會自動更新韌體，Demo 當天 Ethernet 直連
- **Go2 重開機後 WebRTC ICE** 可能 FROZEN→FAILED，通常第二個 candidate 成功（等 10s+）

## Go2 動作 API ID（權威：go2_robot_sdk/domain/constants/robot_commands.py）
- 1001: Damp (soft stop)
- 1002: BalanceStand
- 1003: StopMove
- 1004: StandUp
- 1009: Sit
- 1016: Hello
- 1020: Content
