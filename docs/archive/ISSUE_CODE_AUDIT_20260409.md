# [Audit] 4/9 全專案程式碼審查 — 20 項已驗證問題

**審查範圍**：全專案 ROS2 nodes、Shell scripts、Studio frontend、Gateway
**審查日期**：2026-04-09
**審查方法**：4 個並行 audit agent + 人工交叉驗證，排除誤報

---

## CRITICAL (3)

### C1. `smoke_test_e2e.sh:10` — 缺少 `set -e`，錯誤不中止腳本
```bash
# 現在
set -uo pipefail
# 應該是
set -euo pipefail
```
**影響**：任何命令失敗（ros2 topic pub、WAV 檢查、tmux capture）腳本繼續跑，smoke test 回報假的 PASS。
**位置**：`scripts/smoke_test_e2e.sh:10`

### C2. `run_speech_test.sh:5` — 缺少 `set -u`，未定義變數不報錯
```bash
# 現在
set -eo pipefail
# 應該是
set -euo pipefail
```
**影響**：若 `$ROBOT_IP`、`$CONN_TYPE` 等環境變數未設定，腳本帶空值繼續執行，30 輪測試結果不可信。
**位置**：`scripts/run_speech_test.sh:5`

### C3. `pawai-studio/start.sh:5` — 只有 `set -e`，缺少 `-u` 和 `pipefail`
```bash
# 現在
set -e
# 應該是
set -euo pipefail
```
**影響**：`node --version | sed ...` 失敗時不中止；未定義變數靜默展開為空字串。
**位置**：`pawai-studio/start.sh:5`

---

## HIGH (6)

### H1. `use-audio-recorder.ts` — WebSocket 在元件卸載時不關閉（記憶體洩漏）
**位置**：`pawai-studio/frontend/hooks/use-audio-recorder.ts:82-123`
**問題**：`sendAudio()` 建立的 WebSocket 存在 `wsRef`，但 useEffect cleanup（line 75-80）只呼叫 `cleanupAudioAnalysis()`，不關閉 WebSocket。元件卸載時若正在傳送音訊，WS 連線留在記憶體。
**修復**：cleanup 中加 `wsRef.current?.close()`

### H2. `tts_node.py:792` — TTS 播放失敗靜默告知下游「播完了」
**位置**：`speech_processor/speech_processor/tts_node.py:792-795`
**問題**：`_play_locally()` 的 exception handler 捕獲錯誤後，finally 仍發布 `tts_playing=False`。STT echo gate 收到後解除靜音，但使用者實際沒聽到 TTS 回應。
**影響**：TTS 播放失敗 → ASR 立刻重新收音 → 使用者困惑為何沒回應就又開始聽了。
**建議**：失敗時發布 error event 或重試一次。

### H3. Shell scripts 大量未加引號的變數展開
**位置**：
- `scripts/start_llm_e2e_tmux.sh:142-156` — `$ROBOT_IP`、`$CONN_TYPE`、`$LLM_ENDPOINT`
- `scripts/start_full_demo_tmux.sh:97,147,152,182` — ROS2 args 中的變數
- `scripts/run_speech_test.sh:77-79` — nested quote 中的變數

**影響**：若變數含空格或特殊字元，tmux send-keys 命令會斷裂。目前 IP/URL 不含空格所以沒炸，但極不穩健。
**修復**：所有 `$VAR` → `"$VAR"`

### H4. `start_full_demo_tmux.sh` 中 single-quote 包 `$VAR` 不展開
**位置**：`scripts/start_full_demo_tmux.sh:152,182`
```bash
# 現在 — 單引號不展開變數，ROS2 node 收到字面 "$QWEN_ASR_BASE_URL"
-p qwen_asr.base_url:='$QWEN_ASR_BASE_URL'
-p llm_endpoint:='$LLM_ENDPOINT'
```
**影響**：Demo 腳本啟動的 ASR/LLM 節點收到字面字串，cloud fallback 永遠失敗。

### H5. `use-video-stream.ts:121` — WebSocket onerror 靜默關閉，無日誌
**位置**：`pawai-studio/frontend/hooks/use-video-stream.ts:121-123`
**問題**：video stream WS 斷線時只 `ws.close()`，沒有 console.error 或 UI 提示。Live View 畫面凍結，使用者不知道是斷線還是卡住。

### H6. `run_speech_test.sh` — 臨時檔案無 trap 清理
**位置**：`scripts/run_speech_test.sh:235`
**問題**：`mktemp /tmp/round_done_XXXXXX` 建立暫存檔，但腳本沒有 `trap ... EXIT` 清理。Ctrl+C 中斷後暫存檔殘留。

---

## MEDIUM (8)

### M1. `stt_intent_node.py:27-30` / `llm_bridge_node.py:25-28` — `except Exception` 過寬
```python
try:
    import requests
except Exception:  # 會吃掉 SyntaxError, MemoryError 等
    requests = None
```
**修復**：改為 `except ImportError:`

### M2. `use-event-stream.ts` — 多處 `as unknown as Type` 無運行時驗證
**位置**：`pawai-studio/frontend/hooks/use-event-stream.ts:41,46,51,56,61,66`
**問題**：ROS2 事件 JSON 直接強轉 TypeScript 型別，若後端格式變動，前端不報錯但資料錯誤。
**建議**：加 zod 或手動 type guard。

### M3. `interaction_executive_node.py` — 多處 hardcoded timing 常數
**位置**：
- Line 209: D435 heartbeat stale threshold `1.0s`
- Line 175: obstacle debounce `2.0s`
- Line 81: forward command timer `0.1s`

**影響**：無法在 launch file 中調參，必須改程式碼。
**修復**：宣告為 ROS2 parameters with defaults。

### M4. `object_perception_node.py:52` — class_whitelist 無範圍驗證
**問題**：接受任意整數，COCO ID > 79 靜默忽略。
**修復**：啟動時 log warning for invalid IDs。

### M5. Shell scripts 大量 hardcoded sleep 無 health check
**位置**：`start_full_demo_tmux.sh:101,112,121,131,158,175,190,210,217`
**問題**：用 `sleep 10` 等待 Go2 就緒，系統慢時不夠、快時浪費時間。
**建議**：至少加 `ros2 topic info` 輪詢確認 publisher 存在。

### M6. `use-audio-recorder.ts:175-198` — animation frame 競爭條件
**問題**：`startRecording()` 啟動 rAF 迴圈，但 `cleanupAudioAnalysis()` 和新 rAF callback 之間有微小時間窗口可能雙重 pending。
**影響**：低機率 — 可能導致短暫的額外 CPU 消耗。

### M7. `video_bridge.py:92-99` — broadcast_bytes 從 ROS2 thread 呼叫 async
**問題**：`broadcast_bytes` 是 async method，但 ROS2 callback thread 如何呼叫它取決於 `studio_gateway.py` 的實作。若沒走 `run_coroutine_threadsafe()`，會有 thread safety 問題。
**狀態**：需確認 gateway 實際呼叫路徑。

### M8. `start_face_identity_tmux.sh:24` — `grep -q` 失敗觸發 `set -e` 退出
**位置**：`scripts/start_face_identity_tmux.sh:24`
**問題**：`ros2 pkg list | grep -q realsense2_camera` 若 realsense 未安裝，`grep -q` 回傳 1，觸發 `set -e` 中止腳本，但意圖只是印 WARNING 並繼續。
**修復**：加 `|| true`。

---

## LOW (3)

### L1. `use-text-command.ts:73` — connect useCallback 空依賴陣列
**問題**：`getTextWsUrl` 若動態變化，reconnect 會用舊 URL。目前安全（URL 是 module-level 常數）。

### L2. `live-feed-card.tsx:58-64` — img 缺少 onError 和 loading="lazy"
**問題**：影像載入失敗時無 fallback UI。

### L3. `chat-panel.tsx:208-213` — 缺少 Cmd+Enter (Mac) 送出支援
**問題**：只支援 Enter 送出，Mac 使用者習慣 Cmd+Enter。

---

## 排除的誤報

| 報告的問題 | 排除原因 |
|-----------|---------|
| `llm_bridge_node.py:357` lock deadlock | Python try/finally 保證 finally 執行，return 不會跳過 lock.release() |
| `vision_perception_node.py` close() 未呼叫 | `main()` 的 finally 區塊（line 444）確實呼叫 `node.close()` |
| `face_greet_history` 記憶體無限成長 | 程式碼在 >200 時裁剪到 ~101，sorted by timestamp 正確 |

---

## 建議修復優先序

1. **立即**：C1 + C2 + C3（一行修改，防止測試結果不可信）
2. **本週**：H1 + H2 + H4（影響 Demo 穩定性）
3. **下週**：H3 + H5 + H6 + M1（穩健性提升）
4. **Backlog**：M2-M8、L1-L3（品質改善）
