---
name: demo-preflight
description: >
  Demo 前置檢查工具。在部署到 Jetson 後、Demo 展示前、或需要確認系統就緒時觸發。
  觸發詞："demo check"、"demo 準備"、"preflight"、"demo ready"、
  "準備好了嗎"、"展示前檢查"、"/preflight"。
  在 jetson-deploy 或 jetson-verify 完成後、使用者提到 demo 或展示時應主動建議。
  不要在純開發、文件編輯、或不涉及部署/展示的場景觸發。
---

# demo-preflight

Demo 前置檢查 — 確認 Jetson + Go2 + 所有模組的 Demo 就緒狀態。

## 使用方式

使用者說「demo check」或「demo 準備好了嗎」時：

1. 先確認要跑 `--quick`（5 項核心，2 分鐘）還是 `--full`（15+ 項，5 分鐘）
2. 透過 SSH 連到 Jetson 執行檢查腳本
3. 產出 go/no-go 報告

```bash
# Quick mode（Demo 前 2h）
ssh jetson-nano "cd ~/elder_and_dog && python3 .claude/skills/demo-preflight/scripts/preflight.py --mode quick"

# Full mode（Demo 前 48h）
ssh jetson-nano "cd ~/elder_and_dog && python3 .claude/skills/demo-preflight/scripts/preflight.py --mode full"
```

## Quick 檢查項（5 項，任一 FAIL = NO-GO）

| # | 檢查 | 命令 | 通過條件 |
|---|------|------|----------|
| 1 | Jetson SSH 連線 | `ssh jetson-nano echo ok` | 回傳 ok |
| 2 | D435 相機 | `ros2 topic list \| grep /camera` | 有 camera topic（或 `ls /dev/video*`） |
| 3 | Go2 WebRTC | `ping -c1 -W2 192.168.123.161` | ping 通 |
| 4 | USB 麥克風 | `arecord -l \| grep -i uac\|usb` | 找到 USB 錄音設備 |
| 5 | USB 喇叭 | `aplay -l \| grep -i cd002\|usb` | 找到 USB 播放設備 |

## Full 檢查項（Quick 5 項 + 以下 10 項）

| # | 檢查 | 命令 | 通過條件 |
|---|------|------|----------|
| 6 | ROS2 Domain ID | `echo $ROS_DOMAIN_ID` | 非空且一致 |
| 7 | face_db 存在 | `ls ~/face_db/` | 至少 1 個人的資料夾 |
| 8 | YuNet 模型 | `ls ~/face_models/face_detection_yunet_2023mar.onnx` | 檔案存在 |
| 9 | SFace 模型 | `ls ~/face_models/face_recognition_sface_2021dec.onnx` | 檔案存在 |
| 10 | Whisper 模型 | `ls ~/.cache/huggingface/hub/models--Systran--faster-whisper-small/` | 目錄存在 |
| 11 | LLM Endpoint | `curl -s -o /dev/null -w '%{http_code}' http://localhost:8000/v1/models` | 200（需先開 SSH tunnel） |
| 12 | Ollama 本地 | `curl -s http://localhost:11434/api/tags \| grep qwen` | 有 qwen 模型 |
| 13 | RAM 餘量 | `free -m \| awk '/Mem:/{print $7}'` | ≥ 800MB |
| 14 | 溫度 | `cat /sys/devices/virtual/thermal/thermal_zone*/temp` | < 75°C |
| 15 | 殘留 process | `ps aux \| grep -E 'go2_driver\|stt_intent\|tts_node' \| grep -v grep \| wc -l` | 0（無殘留） |

## 報告格式

```
## Demo Preflight Report
**時間**：2026-03-26 14:30
**模式**：quick / full
**結果**：GO / NO-GO

### 檢查結果
| # | 項目 | 狀態 | 備註 |
|---|------|------|------|
| 1 | SSH  | PASS |      |
| 2 | D435 | FAIL | /dev/video* not found |
...

### 結論
- PASS: X/Y
- FAIL: Z 項（列出）
- 建議：修復 FAIL 項後重跑
```

## Gotchas

- USB device index 重開機後會飄（mic 24→0, speaker hw:3,0→hw:1,0）— preflight 只檢查設備存在，不檢查 index
- Go2 ping 可能因 Wi-Fi AP 模式需用 192.168.12.1 而非 192.168.123.161
- LLM endpoint 需要先開 SSH tunnel：`ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5`
- Jetson SSH host 是 `jetson-nano`（Tailscale IP 100.83.109.89）
- 殘留 process 檢查：0 是 clean state，>0 表示上次 session 未正確清理
