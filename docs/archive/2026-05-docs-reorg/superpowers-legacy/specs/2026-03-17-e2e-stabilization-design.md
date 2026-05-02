# E2E 語音管線穩定化設計

**日期**：2026-03-17
**目標**：對著 Go2 說中文 → LLM 生成完整且清晰的中文回答，延遲可接受
**執行方式**：今日上機實作 + 驗證，每步單一變因

---

## 現狀

E2E LLM 語音管線已通：ASR → LLM (Qwen3.5-9B on RTX 8000) → TTS (Piper) → Megaphone → Go2 播放。

| 指標 | 現狀 | 目標 |
|------|------|------|
| 對話成功率 | 10/10 | 維持 |
| Megaphone 播放率 | 9/10（silent fail） | 10/10 |
| 反應延遲 speech_end → playback_start | ~7-15s | ≤ 8s（理想 ≤ 5s） |
| RuleBrain fallback | 未驗證 | 5/5 可用 |

### 延遲鏈分析（speech_end → playback_start）

| 階段 | Warm path | Worst case | 備註 |
|------|-----------|------------|------|
| grace period | 250ms | 250ms | speech_end_grace_ms |
| ASR (Whisper Small CUDA) | ~600ms | ~5.2s | 首輪冷啟動 penalty |
| Intent classify | <50ms | <50ms | |
| LLM (vLLM Qwen3.5-9B) | ~2-3s | ~5s | timeout 15s, max_tokens 300 |
| TTS (Piper local) | ~500ms | ~1s | |
| ROS2 topic relay | <10ms | <10ms | intra-process |
| 4001 ENTER + delay | 100ms | 100ms | |
| **合計** | **~3.5-4.5s** | **~11.6s** | |

主延遲指標 = **(a) speech_end → playback_start**（使用者停止說話到 Go2 開始出聲）
次延遲指標 = (b) speech_end → playback_done（含播放時間）

---

## 執行步驟

### 步驟 1：Megaphone Cooldown 0.5s

**目標**：消除 silent fail，播放率 10/10

**問題分析**：Go2 Megaphone 偶發 silent fail — log 顯示 `Megaphone playback completed` 但 Go2 無聲。指令送達但 Go2 內部 Megaphone 狀態機未重置完畢，下一輪 4001 ENTER 打到舊 session。

**改動**：`speech_processor/speech_processor/tts_node.py` — `_play_on_robot_datachannel()` finally block

```python
# 現在
finally:
    self._send_audio_command(4002, json.dumps({}))
    self._publish_tts_playing(False)
    self.get_logger().info("Megaphone playback completed")

# 改成
finally:
    try:
        self._send_audio_command(4002, json.dumps({}))
    except Exception as exc:
        self.get_logger().error(f"Megaphone EXIT(4002) failed: {exc}")
    time.sleep(0.5)  # cooldown: let Go2 reset Megaphone state machine
    self._publish_tts_playing(False)
    self.get_logger().info("Megaphone playback completed (cooldown 0.5s)")
```

**設計決策**：
- 4002 送出包在 try/except，確保即使 EXIT 失敗也不吃掉後面的 `tts_playing(False)`
- cooldown 放在 4002 之後、`tts_playing(False)` 之前 — echo gate 在 cooldown 期間仍 active
- **Echo gate 總關閉時間**：cooldown 0.5s（`_tts_playing` 仍為 True）+ echo gate cooldown 1.0s（`_on_tts_playing(False)` 觸發 `_tts_gate_open_time`）= **1.5s**。以正常對話節奏（2-3s 間隔）可接受，不會吃掉使用者下一句話
- 0.5s 保守值，後續可以試 0.3s
- 不影響主指標 (a)：cooldown 發生在 playback_start 之後

**驗證**：
```bash
colcon build --packages-select speech_processor && source install/setup.zsh
bash scripts/start_llm_e2e_tmux.sh
bash scripts/smoke_test_e2e.sh 10
```

| 判定 | 標準 |
|------|------|
| Pass | 10/10，silent_fail_count = 0 |
| Today baseline | ≥ 9/10 |
| Fail | ≤ 8/10 |
| Demo gate | 10/10 |

額外記錄：silent_fail 發生的 round 編號（供步驟 6 before/after 對照）

> **注意**：`smoke_test_e2e.sh` 只驗證 debug WAV 產出和 log 正常，無法自動偵測 Go2 是否真的出聲。silent fail 的最終判定需要**人工監聽**。建議在 smoke_test 跑的同時，人在 Go2 旁邊聽每一輪是否有聲音輸出。

---

### 步驟 2：LLM 回覆收短（max_tokens 120 + prompt 限 25 字）

**目標**：壓低 speech_end → playback_start

**改動 2a**：`llm_bridge_node.py` 第 182 行
```python
# 300 → 120
self.declare_parameter("llm_max_tokens", 120)
```

120 tokens 足夠：中文 25 字 ≈ 38-50 tokens + JSON 結構 ~30-40 tokens + reasoning 欄位 ~30 tokens。偏緊但可用。

**Rollback 條件**：如果 `parse_llm_response` 因 JSON 被截斷而失敗率 >10%（觀察 llm_bridge_node log 中 "parse/validation failed" 的頻率），回退到 `max_tokens=150`。

**改動 2b**：`llm_bridge_node.py` SYSTEM_PROMPT
```python
# 第 110 行：
# "reply_text — 你要說的中文回覆（簡短自然，15-40字。人臉事件時要叫出對方名字）"
# →
# "reply_text — 你要說的中文回覆（一句話，不超過 25 字。人臉事件時要叫出對方名字）"

# 第 121 行：
# "- reply_text 不超過 50 字"
# →
# "- reply_text 不超過 25 字"
```

**預期效果**：
- LLM 生成量 ~200 tokens → ~80 tokens，生成時間約減半
- TTS 合成量減少
- Megaphone chunks 減少
- 估計主指標從 ~4.7s → ~3.5s（warm path）

**驗證**：
```bash
# 重 build + 重啟後，連續 5 輪對話
# 用 log timestamp 算 speech_end → playback_start 中位數
```

| 判定 | 標準 |
|------|------|
| Pass | median ≤ 5s |
| Acceptable | 5s < median ≤ 6s |
| Fail | > 6s |

額外記錄：每輪 reply_text 內容（品質抽查，確認沒變呆板）

---

### 步驟 3：ASR Warmup Dummy Inference

**目標**：消除首輪 ASR 冷啟動 penalty（5.2s → ≤ 1.5s）

**改動**：`stt_intent_node.py`

在 `__init__` 尾部註冊一次性 warmup（daemon thread，不阻塞 ROS2 executor）：

```python
# __init__ 尾部加：
self._warmup_done = False
threading.Thread(target=self._do_warmup, daemon=True).start()
```

新增 method：
```python
def _do_warmup(self) -> None:
    """ASR warmup in background thread: preload Whisper model + trigger CUDA JIT.

    Runs in daemon thread to avoid blocking ROS2 executor callbacks
    (_drain_audio_queue, _check_recording_timeout, state publish).
    """
    whisper = self.providers.get("whisper_local")
    if whisper is None:
        self._warmup_done = True
        return

    self.get_logger().info("ASR warmup started")
    try:
        t0 = time.monotonic()
        # Build a valid 1s silent WAV — same dtype (float32) and path as real recording
        silent_pcm = np.zeros(self.sample_rate, dtype=np.float32)
        wav_bytes = self._encode_wav(silent_pcm)
        whisper.transcribe(wav_bytes, self.sample_rate, self.language)
        elapsed = time.monotonic() - t0
        self.get_logger().info(f"ASR warmup completed in {elapsed:.1f}s (warmup_done=true)")
    except Exception as e:
        self.get_logger().warn(f"ASR warmup failed (non-fatal): {e}")
    self._warmup_done = True
```

**額外改動 — 序列化 warmup 與正式 ASR**：`WhisperLocalProvider.transcribe()` 加 lock

```python
# WhisperLocalProvider.transcribe() 現在沒有 lock：
def transcribe(self, audio_bytes, sample_rate, language) -> ASRResult:
    self._ensure_model()
    ...

# 改成用 self._lock 包住整個 transcribe，與 _ensure_model 共用同一把 lock：
def transcribe(self, audio_bytes, sample_rate, language) -> ASRResult:
    with self._lock:
        self._ensure_model_unlocked()  # 不再自行 acquire lock
        ...
```

**原因**：warmup daemon thread 和使用者第一句話可能併發呼叫同一個 Whisper model。`_ensure_model()` 的 lock 只保護模型載入，不保護推理。擴展 `self._lock` 到 `transcribe()` 層級，確保 warmup 完成後才處理正式 ASR（或反過來）。GPU 同時間只能跑一個 inference，所以不影響效能。

**設計決策**：
- **daemon thread**：不用 timer callback，避免 warmup 的 3-5s 模型載入阻塞 ROS2 executor（timer callback 和其他 callback 共享同一個 executor 線程）
- **inference lock**：`WhisperLocalProvider.transcribe()` 加 `self._lock`，序列化 warmup 與正式推理，避免併發存取 model
- **np.float32**：與正式錄音路徑（audio callback 產出 float32）完全一致，確保 CUDA JIT 編譯結果可複用
- WAV bytes：用 `self._encode_wav()` 走正式 ASR 相同路徑
- 失敗 non-fatal

**驗證**：
```bash
bash scripts/start_llm_e2e_tmux.sh
# 觀察 stt_intent_node pane：
#   "ASR warmup started"
#   "ASR warmup completed in X.Xs (warmup_done=true)"
# 立刻說第一句話
```

| 判定 | 標準 |
|------|------|
| Pass | 首輪 ASR 延遲 ≤ 1.5s |
| Fail | 首輪 > 3s |

---

### 步驟 4：LLM_FORCE_FALLBACK — RuleBrain 路徑驗證

**目標**：確認 RuleBrain fallback 路徑本身沒 bug

**改動**：`llm_bridge_node.py`

```python
# _declare_parameters() 內加一行：
self.declare_parameter("force_fallback", False)

# _read_parameters() 內，_bool 定義之後加一行：
self.force_fallback = _bool("force_fallback")

# _call_llm_and_act() 中，原本的 result = self._call_cloud_llm(user_message) 那行改成：
if self.force_fallback:
    self.get_logger().info("force_fallback=True, skipping LLM")
    result = None
else:
    result = self._call_cloud_llm(user_message)
# 後面的 if result / elif enable_fallback / finally 結構不動
```

**設計決策**：
- `force_fallback` 為啟動時參數，不依賴動態參數回呼
- 不改動 `_rule_fallback` 本身 — 這輪只測路徑
- log 明確標記強制 fallback，不與真實 LLM 失敗混淆

**驗證（步驟 4 — 強制 fallback）**：
```bash
# 啟動時加 force_fallback:=true
ros2 run speech_processor llm_bridge_node --ros-args \
  -p force_fallback:=true
```

5 輪固定話術驗收：

| 輪次 | 話術 | 預期 intent | 預期 action | 預期 reply |
|------|------|------------|-------------|------------|
| 1 | 你好 | greet | hello | 哈囉，我在這裡。 |
| 2 | 停止 | stop | stop_move | 好的，停止動作。 |
| 3 | 你好嗎 | status | null | 我目前狀態正常。 |
| 4 | 你好 | greet | hello | 哈囉，我在這裡。 |
| 5 | 停下來 | stop | stop_move | 好的，停止動作。 |

| 判定 | 標準 |
|------|------|
| Pass | 5/5 有聲 + intent-action 對齊 + 無 timeout + 無自激 |
| Fail | 任何一輪無聲或 intent 錯配 |

---

### 步驟 5：斷 Tunnel 真實 Fallback 驗收

**目標**：確認雲端掛掉時，系統不會啞掉

**前置**：
```bash
# 斷 tunnel
pkill -f "ssh.*-L 8000"
curl -sf --max-time 3 http://localhost:8000/v1/models && echo "TUNNEL STILL UP" || echo "TUNNEL DOWN"
```

**改動**：驗收時臨時降低 `llm_timeout` 到 3s。如果 tunnel 已斷，`ConnectionRefusedError` 通常會在 <1s 內觸發 fallback，不需等到 timeout。降低 timeout 主要防禦半開連線（half-open connection）場景：
```bash
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_timeout:=3.0 \
  -p force_fallback:=false
```

跑步驟 4 相同的 5 輪固定話術。

| 判定 | 標準 |
|------|------|
| Pass | 5/5 有聲 + intent-action 對齊（LLM timeout → 自動 fallback） |
| Fail | 卡住或無聲 |

---

### 步驟 6（備案）：Preemptive EXIT — Round 2 Mitigation Only

> **僅在步驟 1 未達 10/10 時啟用。** 此為 Round 2 緩解措施，不是主線常態。

**改動**：`tts_node.py` — 4001 ENTER 之前

```python
# 現在
self._send_audio_command(4001, json.dumps({}))
time.sleep(0.1)

# 改成
try:
    self._send_audio_command(4002, json.dumps({}))  # preemptive reset
except Exception as exc:
    self.get_logger().warn(f"Preemptive EXIT failed: {exc}")
time.sleep(0.3)  # let Go2 process the reset
self._send_audio_command(4001, json.dumps({}))
time.sleep(0.1)
```

**代價**：每輪多 +0.3s，**影響主指標 (a)**
**驗證**：再跑 `smoke_test_e2e.sh 10`，與步驟 1 結果 before/after 對照

---

## 總驗收

完成步驟 1-5 後做一次完整驗收：

| 目標 | 驗證方式 | Today baseline | Demo gate |
|------|----------|---------------|-----------|
| Megaphone 穩定 | smoke_test 10 輪 | ≥ 9/10 | 10/10, silent_fail=0 |
| 反應延遲 (a) | 5 輪 log timestamp median | ≤ 6s | ≤ 5s |
| RuleBrain fallback | 斷 tunnel + 短 timeout + 5 輪 | ≥ 4/5 | 5/5 有聲 + intent 對齊 |

**額外記錄項**（每輪都記）：
- reply_text 內容（品質抽查）
- ASR 首輪延遲（warmup 效果）
- silent_fail 發生的 round 編號
- Megaphone chunks 數量

---

## 不動的東西

本次設計明確不碰：
- Megaphone chunk_interval（維持 70ms）
- Echo gate cooldown（維持 1000ms）
- Energy VAD 參數
- TTS provider（維持 Piper）
- Playback method（維持 datachannel）
- LLM streaming（留 P2）
- 22050Hz sample rate A/B（留 P1）
- length_scale A/B（留 P1）
- 人臉觸發（留 P2）

---

## 設計決策附錄

**為什麼不用 Go2 play_state 偵測 silent fail？**
Go2 的 Megaphone `play_state` API 永遠回傳 `not_in_use`（已知問題，見 CLAUDE.md）。無法可靠偵測播放狀態，因此 silent fail 只能靠人工監聽或 preemptive reset 緩解。

---

*維護者：System Architect*
*審核狀態：已修正 reviewer 反饋，待使用者確認*
