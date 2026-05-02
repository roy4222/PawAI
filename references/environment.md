# 環境與部署 Reference

## 定位

Jetson Orin Nano 開發環境、colcon build、部署流程、網路配置。

## 權威文件

- **環境建置**：`docs/runbook/README.md`
- **硬體配置**：`docs/archive/2026-05-docs-reorg/setup-misc/hardware/`
- **網路排查**：`docs/archive/2026-05-docs-reorg/setup-misc/network/`

## 雙平台架構

| 平台 | 用途 | 備註 |
|------|------|------|
| Windows/Mac（開發機） | VS Code SSH → Jetson，程式碼編輯 | |
| Jetson Orin Nano 8GB | ROS2 runtime、模型推理、Go2 連線 | Shell 用 zsh |
| Go2 Pro | 運動控制、音訊播放 | 192.168.12.1 (Wi-Fi) / 192.168.123.161 (Ethernet) |
| RTX 8000 (x5) | Cloud LLM (vLLM) | 140.136.155.5 |

## Jetson 連線

- SSH：`jetson-nano`（Tailscale IP 100.83.109.89）
- Repo 路徑：`~/elder_and_dog`（不是 `~/newLife/elder_and_dog`）

## Build 流程

```bash
source /opt/ros/humble/setup.zsh    # Jetson 用 zsh
colcon build --packages-select <pkg>
source install/setup.zsh            # build 後必須重新 source
```

## 記憶體預算（8GB 統一記憶體）

- D435 + YuNet + ASR + TTS + ROS2 → 保留 ≥ 0.8GB 餘量
- 展示模式關閉 RViz/Foxglove/Nav2/SLAM
- L3 壓測實測：face+pose+gesture 同跑 → RAM 1.2GB, temp 52°C

## 部署注意

- `pip install` → 一律用 `uv pip install`
- `.bash` / `.zsh` 不可混用
- HyperX 麥克風 stereo-only → `channels:=2` + 手動 downmix
- rsync `--delete` 會清 build/install/log/ → 需 `--exclude`
- vision_perception executable 裝到 `bin/` 而非 `lib/` → 需手動 symlink

## 已知環境陷阱

- Go2 OTA 自動更新：連外網會被更新韌體 → 用 Ethernet 直連
- 多 driver instance 殘留：`killall python3` 只殺 parent → 需逐一 pkill
- Go2 重開機後 WebRTC ICE 可能 FROZEN→FAILED → 等 10s+ 第二個 candidate
- clean_all.sh 的 `set -e` + `pipefail`：grep 空結果會中斷 → 尾端加 `|| true`
- `ROS_DOMAIN_ID` 必須所有 node 一致

## 環境清理

```bash
bash scripts/clean_speech_env.sh              # 語音（不碰 go2_driver）
bash scripts/clean_speech_env.sh --with-go2-driver  # 含 driver
bash scripts/clean_face_env.sh --all          # 人臉
bash scripts/clean_all.sh                     # 全部
```
