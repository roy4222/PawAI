# 環境與部署

> 最後更新：2026-03-15

## 這個模組是什麼

開發環境建置、Jetson 操作要點、Go2 連線、build 流程、跨機器同步。
不是某個 ROS2 package，而是所有模組共用的基礎設施知識。

## 權威文件

- `docs/runbook/README.md` — 環境建置總覽
- `docs/archive/2026-05-docs-reorg/setup-misc/hardware/` — 硬體設置指南（Jetson、GPU server）
- `docs/runbook/go2-operation.md` — Go2 基礎操作
- `docs/runbook/network.md` — 網路問題排查
- `AGENTS.md` — 跨機器開發架構、SSH 指令、auto-sync 流程

## 雙平台架構

| 環境 | 路徑 | 用途 |
|------|------|------|
| **WSL2（開發機）** | `/home/roy422/newLife/elder_and_dog` | 程式碼編輯、git、VS Code |
| **Jetson Orin Nano** | `/home/jetson/elder_and_dog` | ROS2 runtime、colcon build、GPU 推理、Go2 連線 |

- **Source of truth 是 WSL**，不要直接在 Jetson 上改 code
- Sync 方式：`sshfs`，Jetson 的 `/home/jetson` 掛在 WSL 的 `/home/roy422/jetson`
- Auto-sync：`~/sync start`（WSL → Jetson 單向），排除 `.git/`、`build/`、`install/`、`log/`
- SSH target：`jetson-nano`

## Go2 連線

| 連線方式 | IP | 用途 |
|---------|----|----|
| Wi-Fi AP | 192.168.12.1 | 無線連線 |
| Ethernet | 192.168.123.161 | 有線連線（穩定，推薦） |

啟動 driver：
```bash
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

## Build 流程

```bash
# Jetson 上
source /opt/ros/humble/setup.zsh        # 注意是 .zsh

colcon build                                         # 全部
colcon build --packages-select go2_robot_sdk         # 單一
colcon build --packages-select speech_processor      # 語音

source install/setup.zsh                 # build 後必須重新 source
```

- Launch 檔案改動不需 rebuild，重啟即可
- Python 程式碼改動必須 rebuild + re-source
- `setup.bash` 和 `setup.zsh` 不可混用

## 核心程式目錄

| 目錄 | 用途 |
|------|------|
| `go2_robot_sdk/` | Go2 驅動，Clean Architecture 分層 |
| `go2_interfaces/` | 自訂 ROS2 訊息（`WebRtcReq.msg`） |
| `speech_processor/` | 語音模組全套 |
| `scripts/` | 啟動/測試/清理腳本 |
| `go2_robot_sdk/config/` | SLAM/Nav2/CycloneDDS/Joystick 參數 |
| `go2_robot_sdk/launch/robot.launch.py` | 主 launch |

## 目前狀態

[DONE] — 開發環境穩定，WSL↔Jetson 同步正常，Go2 連線可用。

## 已知陷阱

- **Jetson shell 是 zsh**：所有 source 指令用 `.zsh`，用 `.bash` 會環境不完整
- **zsh glob 炸陣列**：ROS2 參數含陣列時要加引號 `'["item"]'`，或 `setopt nonomatch`
- **麥克風裝置漂移**：ALSA default 不一定指向 HyperX，啟動時需指定 `input_device:=0`
- **rsync --delete 會清 build/**：sync 時需 `--exclude` 或 `--filter=':- .gitignore'`
- **ROS_DOMAIN_ID**：所有 node 必須一致，否則互相看不到 topic
- **Jetson 記憶體 8GB**：D435 + YuNet + ASR + TTS + ROS2 同時跑要保留 >= 0.8GB 餘量，展示模式關閉 RViz/Foxglove/Nav2/SLAM
- **CycloneDDS 設定**：跨機器通訊需要 `go2_robot_sdk/config/cyclonedds.xml`

## 開發入口

- **第一次建置**：讀 `docs/runbook/README.md`，照步驟設定 WSL + Jetson
- **Go2 連線除錯**：`ros2 topic list` 確認 driver 輸出，`ros2 topic info /webrtc_req -v` 確認訂閱者
- **新增 ROS2 節點**：建檔 → 更新 `setup.py` entry_points → `colcon build` → `source install/setup.zsh` → `ros2 run`

## 驗收方式

```bash
# 確認 ROS2 環境正常
ros2 topic list

# 確認 Go2 driver 運作
ros2 topic echo /webrtc_req

# 確認 Jetson 同步
ssh jetson-nano "ls /home/jetson/elder_and_dog/speech_processor/"

# 確認記憶體餘量
ssh jetson-nano "free -h"
```
