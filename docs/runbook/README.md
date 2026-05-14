# Runbook — Demo 救火 SOP

> Demo 現場炸的時候打開這個資料夾。每份檔都應該能在 5 分鐘內讓人診斷或修復一類問題。

---

## 救火檔索引

| 檔案 | 場景 | 何時打開 |
|------|------|---------|
| [jetson.md](jetson.md) | Jetson Orin Nano 8GB 環境 | ROS2 / CUDA / 環境變數 / 套件路徑問題 |
| [network.md](network.md) | 網路排查 | Go2 / Jetson / GPU server / 開發機之間連線異常 |
| [gpu-server.md](gpu-server.md) | RTX 8000 GPU server 連線 | 雲端 LLM / ASR 不通、SSH tunnel 異常 |
| [go2-operation.md](go2-operation.md) | Go2 基礎動作操作 | 動作 ID 速查、WebRTC 命令格式、緊急停止 |

---

## Demo 啟動腳本（不在 runbook，列在這裡方便查）

```bash
# 主流程
bash scripts/start_llm_e2e_tmux.sh             # 語音 + LLM 主線
bash scripts/start_nav_capability_demo_tmux.sh # nav_capability 平台層 demo
bash scripts/start_face_identity_tmux.sh       # 人臉辨識
bash scripts/start_full_demo_tmux.sh           # 四功能整合（demo 主線）

# 環境清理
bash scripts/clean_full_demo.sh                # 清 demo 全環境
bash scripts/clean_speech_env.sh               # 只清語音
bash scripts/clean_face_env.sh --all           # 人臉
```

詳見 [`/CLAUDE.md`](../../CLAUDE.md) §「建構與執行」。
