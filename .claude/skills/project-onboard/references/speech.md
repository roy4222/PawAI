# 語音模組

> 最後更新：2026-03-18
> 狀態：**FROZEN**（3/17 freeze，等硬體到貨再做最後一輪）

## 這個模組是什麼

語音互動的完整管線：喚醒詞 → ASR（語音轉文字）→ Intent 分類 → 回覆生成 → TTS（文字轉語音）→ Go2 喇叭播放。是 4/13 Demo A 的核心鏈路之一。目前走 no-VAD 主線（Energy VAD 內建但非必要路徑）。

## 權威文件

- `docs/語音功能/README.md` — 模組完整設計、選型比較、架構分層
- `docs/語音功能/jetson-MVP測試.md` — Jetson 上的實測紀錄與除錯歷程
- `docs/architecture/interaction_contract.md` §3.2, §4.2 — `/state/interaction/speech` 和 `/event/speech_intent_recognized` schema
- `docs/superpowers/specs/2026-03-14-speech-30round-validation-design.md` — 30 輪驗收框架設計

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `speech_processor/speech_processor/stt_intent_node.py` | ASR + Intent 整合節點。錄音 → Whisper 轉寫 → IntentClassifier 分類 → 發布 event |
| `speech_processor/speech_processor/tts_node.py` | TTS 合成 + Go2 Megaphone DataChannel 播放（4001/4003/4002） |
| `speech_processor/speech_processor/llm_bridge_node.py` | **取代 intent_tts_bridge_node** — 呼叫 Cloud LLM，發布 /tts + /webrtc_req |
| `speech_processor/speech_processor/intent_tts_bridge_node.py` | 舊版 Intent → 模板回覆（僅 30 輪測試用） |
| `speech_processor/speech_processor/speech_test_observer.py` | 30 輪測試 observer node，聚合 topic 資料輸出 CSV/JSON |
| `speech_processor/config/speech_processor.yaml` | 語音模組參數設定 |

## 啟動腳本

| 腳本 | 用途 |
|------|------|
| `scripts/start_llm_e2e_tmux.sh` | **語音+LLM 主線**（edge-tts + USB 外接 + Ollama fallback） |
| `scripts/start_full_demo_tmux.sh` | **四功能整合 Demo**（face + vision + speech + Go2） |
| `scripts/smoke_test_e2e.sh` | 5/10 輪 smoke test |
| `scripts/clean_all.sh` | 全環境清理（speech + Go2 driver + daemon） |
| `scripts/run_speech_test.sh` | 30 輪驗收 orchestration |

## ROS2 Topics

| Topic | 方向 | 用途 |
|-------|------|------|
| `/event/speech_intent_recognized` | stt_intent_node → | 語音意圖事件（JSON） |
| `/asr_result` | stt_intent_node → | ASR 純文字輸出 |
| `/tts` | → tts_node | TTS 輸入文字 |
| `/webrtc_req` | tts_node → go2_driver | Go2 WebRTC 命令 |
| `/state/interaction/speech` | stt_intent_node → | 語音管線狀態（5Hz） |

## 目前狀態

[FROZEN] — E2E 已通（ASR→LLM→TTS→Megaphone→Go2 說話），10/10 對話、9/10 播放率。
延遲 median 5.4s（LLM 2.7-4.1s 是最大瓶頸）。Megaphone 20/20 連續（cooldown 0.5s）。
RuleBrain fallback 5/5。不再動 code，等硬體到貨後做：外接喇叭/麥克風 A/B、自激測試、清晰度最終決策。

## Go2 音訊播放

**主線**：Megaphone DataChannel — ENTER(4001) → UPLOAD(4003) × N → EXIT(4002)
- chunk_size=4096 base64 chars，payload 含 `current_block_size`
- DataChannel msg type 必須 `"req"`（不是 `"msg"`）
- 70ms chunk interval，+16dB gain boost
- try/finally 保證 4002 必送，tail_sec=0.5s

**備選**：WebRTC audio track（研究分支，Go2 不播放 RTP 音訊）

## 已知陷阱

- **Megaphone silent fail**：連續播放偶爾 Go2 不出聲（9/10），疑似狀態機未完全重置
- **Go2 對音訊 API silent ignore**：格式不對不報錯，play_state 永遠 not_in_use
- **Echo gate**：tts_playing(True) 必須在 TTS request 入口就開，不能等合成完。cooldown 1s
- **HyperX 麥克風是 stereo-only**：必須 `channels:=2` + 手動 downmix
- **麥克風原生 44.1kHz**：node 內重取樣至 16kHz，需設 `capture_sample_rate:=44100`
- **Whisper Small 輸出偏簡體**：IntentClassifier 有繁體+簡體+Whisper 誤辨詞
- **zsh glob 會炸陣列參數**：provider_order 參數要加引號 `'["whisper_local"]'`
- **CTranslate2 CUDA**：裝在 `~/.local/ctranslate2-cuda/`
- **同時間只能一套 speech session**：測試前必須 `bash scripts/clean_all.sh`

## 開發入口

- **改 intent 規則**：編輯 `stt_intent_node.py` 中的 `intent_rules` dict，加入關鍵字與權重。同步更新 `intent_tts_bridge_node.py` 的 `reply_templates`
- **改 TTS provider**：`ros2 run speech_processor tts_node --ros-args -p provider:=piper` 或 `elevenlabs` 或 `melotts`
- **新增語音節點**：在 `speech_processor/speech_processor/` 建檔，更新 `setup.py` 的 `entry_points`，rebuild + source

## 驗收方式

```bash
# 快速驗證 TTS → Go2 播放
ros2 topic pub --once /tts std_msgs/msg/String '{data: "測試播放"}'

# 確認語音管線輸出
ros2 topic echo /event/speech_intent_recognized
ros2 topic echo /asr_result

# 30 輪完整驗收
bash scripts/run_speech_test.sh --skip-driver --skip-build
```

通過門檻（來源：jetson-MVP 測試手冊）：
- Fixed round 命中率 >= 80%
- E2E 中位數延遲 <= 3500ms
- Go2 播放成功率 >= 80%
