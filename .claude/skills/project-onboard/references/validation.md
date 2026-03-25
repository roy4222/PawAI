# 測試與驗收 Reference

> 最後更新：2026-03-16

## 框架定位

30 輪語音驗收測試是自動化純觀察模式。Operator 只需在提示時說話，Observer 聚合 ROS2 topics 並輸出統計，無人工判分。

## 權威文件

| 文件 | 用途 |
|------|------|
| `test_scripts/speech_30round.yaml` | 30 輪測試定義（5 intent × 6 輪） |
| `scripts/run_speech_test.sh` | 測試 orchestration（7 階段） |
| `scripts/clean_speech_env.sh` | 環境清理（clean-start 保證） |
| `speech_processor/speech_processor/speech_test_observer.py` | Observer 節點實作 |
| `speech_processor/test/test_speech_test_observer.py` | Observer 單元測試（20 tests） |

## 30 輪測試定義

5 個 Intent 類別各 6 輪：greet / come_here / stop / take_photo / status。
每輪包含 canonical（標準語句）、conversational（口語化）、edge-case（長句/重複）。

## 啟動命令

```bash
# 完整流程
bash scripts/run_speech_test.sh

# 跳過 build + driver（最常用）
bash scripts/run_speech_test.sh --skip-driver --skip-build

# 假設所有 node 已在跑（最快）
bash scripts/run_speech_test.sh --nodes-running
```

## 7 階段流程

| 階段 | 作用 |
|------|------|
| 1 | `clean_speech_env.sh`（kill tmux + speech nodes + PulseAudio） |
| 2 | `colcon build`（可 `--skip-build`） |
| 3 | Launch 主節點（4-pane tmux） |
| 4 | 健康檢查（等 topic 出現，60s for Whisper CUDA load） |
| 4b | 暖機（operator 說一句不計分）+ 啟動 Observer |
| 5 | 30 輪測試迴圈（meta → speak → ack → wait TTS） |
| 6-7 | 報告生成（CSV + JSON）+ 結果摘要 |

## 通過門檻

| 指標 | 門檻 |
|------|------|
| Fixed accuracy | ≥ 80% |
| E2E 中位數延遲 | ≤ 3500ms |
| E2E 最大延遲 | ≤ 6000ms |
| Go2 播放成功率 | ≥ 80% |

**評分**：PASS（全過）/ MARGINAL（單一失敗且偏離 ≤10%）/ FAIL

## 環境清理

```bash
bash scripts/clean_speech_env.sh              # 預設：不碰 go2_driver_node
bash scripts/clean_speech_env.sh --with-go2-driver  # 診斷用
```

**關鍵步驟**：Stop PulseAudio + mask socket，防止 PA 持有 `/dev/snd/pcmC0D0c` 阻擋 PortAudio。

## Observer 架構

訂閱 5 個 topic，聚合 RoundRecord：

| 訂閱 Topic | 用途 |
|------------|------|
| `/state/interaction/speech` | 狀態轉移（LISTENING→RECORDING→TRANSCRIBING） |
| `/asr_result` | ASR 輸出文本 + 延遲 |
| `/event/speech_intent_recognized` | Intent + confidence |
| `/tts` | TTS 觸發文本 |
| `/webrtc_req` | WebRTC 播放命令 |

**特殊處理**：
- `hallucination` intent → 記錄但保持 pending，等真正 intent 或超時
- TTS/WebRTC 用 5s 時間窗口關聯到最近的 intent
- 30s meta timeout → finalize_as_timeout

## 輸出檔案

```
test_results/
├── speech_test_YYYYMMDD_HHMMSS.csv           # 逐輪原始（25 欄位）
├── speech_test_YYYYMMDD_HHMMSS_summary.json  # 統計 + Grade
```

## 開發用快速啟動腳本

| 腳本 | 用途 | Pane 數 |
|------|------|:-------:|
| `scripts/start_llm_e2e_tmux.sh` | **語音+LLM 主線**（edge-tts + USB + Ollama） | 4 |
| `scripts/start_full_demo_tmux.sh` | **四功能整合 Demo**（face+vision+speech+Go2） | 10 |

## CI 管道

- **PawAI Studio**：`.github/workflows/studio-ci.yml`（lint + build + backend import check）
- **ROS2 主專案**：`.github/workflows/ros_build.yaml`（fast-gate 16 tests + blocking contract check + ROS2 container build）

## 已知陷阱

- PulseAudio device lock → clean_speech_env.sh mask socket
- Whisper CUDA 首次載入慢 → health check 60s 寬限
- zsh glob 炸陣列參數 → 加單引號 `'["whisper_local"]'`
- HyperX 必須 stereo → `channels:=2` + 手動 downmix
- Orphan TTS（前一輪延遲進入下一輪）→ 5s time-window correlation

## 當前狀態

- 30 輪框架已建好（script + observer + YAML + 單元測試）
- 待 Jetson 上跑第一輪實測
