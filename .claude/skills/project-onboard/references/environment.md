# 環境與部署（Jetson + Go2 + CLI）

## 這個模組是什麼

跨機器開發環境的基礎設施知識：Jetson 操作、Go2 連線、colcon build 流程、日常部署。
5/11 後**主入口是 `pawai-cli`**（統一部署、狀態檢查、tmux 管理），手動 SSH/colcon 流程保留作背景知識。

## 權威文件

| 文件 | 用途 |
|------|------|
| `.claude/skills/pawai-cli/SKILL.md` | pawai CLI 完整命令參考（pawai doctor / status / deploy / demo）|
| `docs/pawai_cli/team-onboarding.md` | 5 人團隊上手指南（首次設定 + 日常操作）|
| `docs/pawai_cli/troubleshooting.md` | 故障排查（G/H/I/J 章：Jetson / Go2 / Tailscale / 網路）|
| `docs/runbook/README.md` | 環境建置總覽（初次設定）|

## 雙平台架構

| 環境 | 路徑 | 用途 |
|------|------|------|
| **Mac / Windows（開發機）** | `/Users/lubaiyu/elder_and_dog`（Mac）| 程式碼編輯、git、VS Code SSH |
| **Jetson Orin Nano 8GB**（邊緣端）| `~/elder_and_dog` | ROS2 runtime、colcon build、推理、Go2 連線 |
| **Go2 Pro** | 192.168.12.1（Wi-Fi）/ 192.168.123.161（Ethernet）| 運動控制、音訊播放 |

**Tailscale**：Jetson IP 100.83.109.89（`jetson-nano` hostname），可從任何網路 SSH。

## pawai-cli 主入口（5/11 後）

```bash
# 診斷（開工前必跑）
pawai doctor

# 系統狀態
pawai status

# 部署到 Jetson（sync + build + restart）
pawai jetson deploy

# Demo 啟動 / 停止
pawai demo start
pawai demo stop

# 查 log
pawai logs <module>
```

詳細指令與場景（換教室 IP、多人共用 Jetson、lock collision 排解）指向 `.claude/skills/pawai-cli/SKILL.md`。

## Build 流程（背景知識）

```bash
# Jetson 上，必須用 zsh
source /opt/ros/humble/setup.zsh        # setup.bash 不可混用

colcon build                                         # 全部
colcon build --packages-select speech_processor      # 單一
colcon build --packages-select face_perception       # 人臉模組

source install/setup.zsh                 # build 後必須重新 source
```

**setuptools 版本限制**：Jetson 必須 `< 70`（setuptools 80+ 拿掉 `--editable` flag → `setup.py shim` 失敗）。
修法：`uv pip install "setuptools<70"`（已知好版本：69.5.1）。

## Go2 連線（背景知識）

```bash
export ROBOT_IP="192.168.123.161"
export CONN_TYPE="webrtc"
ros2 launch go2_robot_sdk robot.launch.py \
  enable_tts:=false nav2:=false slam:=false rviz2:=false foxglove:=false
```

## 已知陷阱

- **Jetson shell 是 zsh**：`source setup.zsh`，不是 `setup.bash`，兩者不可混用
- **tmux 不繼承 `LD_LIBRARY_PATH`**：啟動腳本中必須 export（含 `~/.local/ctranslate2-cuda/lib`）
- **setuptools < 70**：否則 colcon build 失敗（`option --editable not recognized`）
- **多 driver instance 殘留**：`killall python3` 只殺 launch parent，C++ 子 process 需逐一 `pkill`
- **Go2 OTA 自動更新**：連外網 Wi-Fi 會背景更新韌體，建議用 Ethernet 直連（192.168.123.161）
- **Jetson 記憶體 8GB**：D435 + YuNet + ASR + TTS + ROS2 同時跑保留 ≥ 0.8GB 餘量，Demo 關 RViz/Foxglove
- **rsync 只搬源碼**：`install/` 目錄不會同步，感覺 brain 新模式沒生效時跑 `colcon build`
- **ROS_DOMAIN_ID**：所有 node 必須一致，否則看不到彼此 topic

## 開發入口

```bash
# 確認 ROS2 環境
ros2 topic list

# 確認 Go2 driver 輸出
ros2 topic info /webrtc_req -v

# 新增 ROS2 節點標準流程
# 1. 建節點檔 → 2. 更新 setup.py entry_points
# 3. colcon build → 4. source install/setup.zsh → 5. ros2 run

# Tailscale / 網路問題
# → 見 docs/pawai_cli/troubleshooting.md §G/H/I/J
```
