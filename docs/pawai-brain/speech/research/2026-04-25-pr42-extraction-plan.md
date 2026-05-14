# PR #42 語音功能提取計畫

**日期**：2026-04-25
**來源 PR**：https://github.com/roy4222/PawAI/pull/42 (katiechen128 / 陳如恩)
**整體 PR review 結論**：REQUEST_CHANGES（不能直接 merge — CI 兩個 job 都 FAIL）— 詳見 `docs/mission/meetings/2026-04-25.md`
**本檔目的**：列出 PR 內**值得提取**到本地程式碼的功能，以及實作時要注意的事

---

## 可提取的功能

### 1. TTS voice 名對齊 edge-tts 主線

**來源**：PR 內 TTS 設定改成 `zh-CN-XiaoxiaoNeural`

**現況**：
- 4/25 會議結論：大陸口音 TTS **保留**（教授裁定 minor 問題）
- edge-tts 是現有主線，原 ElevenLabs voice ID `XrExE9yKIg1WjnnlVkGX` 是錯設定

**整合到本地**：
- 改 `speech_processor/config/speech_processor.yaml` 的 voice 欄位
- 一行設定，沒有風險
- 確認 `tts_node.py` 的 edge-tts provider 接受這個 voice 名

### 2. SenseVoice 簡體 → 繁體（zhconv）

**來源**：PR 內 ASR 後處理用 `zhconv.convert(text, 'zh-tw')`

**現況**：
- SenseVoice cloud 主線輸出簡體，現有 stack 沒做轉換
- 對症下藥，會直接改善 demo 觀感

**整合到本地**：
- 加到 `speech_processor/speech_processor/stt_intent_node.py`
  ASR provider 拿到 raw text 之後、做 intent matching 之前
- 注意 `zhconv` 套件要加進 `setup.py` 的 `install_requires`
- 用 `uv pip install zhconv` 在 Jetson 安裝

### 3. chatHistory 用 `audio_url` 去重

**來源**：PR 內 frontend chatHistory 處理邏輯

**現況**：
- 解決現有重播 bug — 同一筆 reply 被多次播放

**整合到本地**：
- 對應到 `pawai-studio/frontend/` 的對話記錄元件
- 注意原 PR 同時有「雙音訊播放器」bug（hook + component 各自播一次）
  → **提取去重邏輯時必須統一播放點**：要嘛 hook 播、要嘛 component 播，不要兩邊都播

---

## ❌ 不要的東西（嚴格禁止整合）

### 安全 / 安全性
- **`studio_api.py` 整支** — Shell injection 在 ffmpeg + edge-tts
  ```python
  cmd = f'edge-tts --voice ... --text "{reply_text}" --write-media {tts_filepath}'
  asyncio.create_subprocess_shell(cmd)
  ```
  LLM 輸出 `"; rm -rf ~; #` 就重灌 Jetson。
  正確做法：用 `create_subprocess_exec` + argv list，不要 shell。
- `connect_gpu.sh` hardcode `roy422@140.136.155.5`（內網 IP + 個人帳號）入版控

### 架構違規
- `studio_api.py` 是 FastAPI WebSocket，**繞過整個 ROS2 stack**
  （stt_intent_node / llm_bridge_node / tts_node 全不用，自己 call vLLM + edge-tts）
- 完全不發 `/event/speech_intent_recognized`，違反 `docs/contracts/interaction_contract.md`
- `chat_memory` 是 endpoint scope 的 list，多 client 共用會交叉污染
- 前端 `getSpeechWsUrl()` hardcode `ws://127.0.0.1:5000/ws/speech_interaction`
  → Jetson 部署直接壞

### 雜訊
- 8 個 `.mp3` binary（不該進 git）
- 6 個 ad-hoc `test_*.py`（用 `os.system`、`afplay` macOS-only、`input()` 互動，CI 會誤收）
- 兩份重複的 `start_pawai.command`（macOS-only `osascript`，但專案是 Jetson Linux）
- `Plan B` 段落塞在 `llm_bridge_node.py` `if __name__ == "__main__"` 之後 → 永遠不執行的死碼
- `except Exception as e: print(...)` 在 WebSocket loop 吞掉所有錯誤

### 邏輯錯誤
- 雙音訊播放器：hook 內 `new Audio(audioUrl); audio.play()` + component `audioRef.current.play()`
  → 每次回應放兩次（註解寫「終極防回音」「保證絕對不會雙重聲音」但實際相反）
- LLM `SYSTEM_PROMPT` 要求 50 字但 `max_tokens=100`，中文 ~1.5 字/token，會在句中截斷

---

## 實作優先級

| 優先級 | 項目 | 估時 |
|-------|------|------|
| P0 | TTS voice 改 `zh-CN-XiaoxiaoNeural` | 5 min |
| P0 | SenseVoice 後處理加 zhconv 簡→繁 | 15 min |
| P1 | chatHistory 去重邏輯 + 統一播放點 | 1 hr |

---

## 注意事項

- 改完 stt_intent_node.py 必須 `colcon build --packages-select speech_processor`
- 接著 `bash scripts/clean_speech_env.sh` + `bash scripts/start_llm_e2e_tmux.sh`
  跑 5 輪 smoke test 確認 zhconv 沒打到延遲
- voice 改成 XiaoxiaoNeural 後，可能要重跑 `scripts/smoke_test_e2e.sh` 確認 TTS cache 沒衝突
