# E2E 語音管線穩定化 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Megaphone 10/10 + 反應延遲 ≤ 8s + RuleBrain fallback 可用

**Architecture:** 修改 3 個 ROS2 node（tts_node / llm_bridge_node / stt_intent_node），每個 task 只改一個變因。驗證在 Jetson + Go2 實機上進行，用 smoke_test_e2e.sh + 人工監聽判定。

**Tech Stack:** ROS2 Humble / Python 3.10 / faster-whisper (CUDA) / Piper TTS / vLLM (Qwen3.5-9B) / Unitree Go2 WebRTC DataChannel

**Spec:** `docs/superpowers/specs/2026-03-17-e2e-stabilization-design.md`

---

## File Map

| 檔案 | Task | 改動 |
|------|------|------|
| `speech_processor/speech_processor/tts_node.py:820-824` | Task 1 | Megaphone cooldown 0.5s in finally block |
| `speech_processor/speech_processor/llm_bridge_node.py:99-122` | Task 2 | SYSTEM_PROMPT 收短 reply_text |
| `speech_processor/speech_processor/llm_bridge_node.py:182` | Task 2 | max_tokens 300→120 |
| `speech_processor/speech_processor/stt_intent_node.py:344-356` | Task 3 | WhisperLocalProvider.transcribe() 加 lock |
| `speech_processor/speech_processor/stt_intent_node.py:494-501` | Task 3 | __init__ 尾部加 warmup thread |
| `speech_processor/speech_processor/llm_bridge_node.py:189-192` | Task 4 | force_fallback parameter |
| `speech_processor/speech_processor/llm_bridge_node.py:342-343` | Task 4 | force_fallback 分支 |
| `speech_processor/speech_processor/tts_node.py:802-804` | Task 6 | Preemptive EXIT (backup only) |

---

## Task 1: Megaphone Cooldown 0.5s

**Files:**
- Modify: `speech_processor/speech_processor/tts_node.py:820-824`

- [ ] **Step 1.1: 修改 finally block — 4002 加 try/except + cooldown**

在 `_play_on_robot_datachannel()` 方法中，將第 820-824 行：

```python
        finally:
            # ALWAYS send EXIT — if skipped, Go2 stays in ENTER state and goes silent
            self._send_audio_command(4002, json.dumps({}))
            self._publish_tts_playing(False)
            self.get_logger().info("Megaphone playback completed")
```

改成：

```python
        finally:
            # ALWAYS send EXIT — if skipped, Go2 stays in ENTER state and goes silent
            try:
                self._send_audio_command(4002, json.dumps({}))
            except Exception as exc:
                self.get_logger().error(f"Megaphone EXIT(4002) failed: {exc}")
            # Cooldown: let Go2 Megaphone state machine fully reset before next session.
            # Echo gate stays active during this 0.5s (_tts_playing still True).
            # Total echo gate closure = 0.5s cooldown + 1.0s echo_cooldown_ms = 1.5s.
            time.sleep(0.5)
            self._publish_tts_playing(False)
            self.get_logger().info("Megaphone playback completed (cooldown 0.5s)")
```

- [ ] **Step 1.2: 確認 build 通過**

```bash
cd /home/jetson/elder_and_dog
colcon build --packages-select speech_processor
source install/setup.zsh
```

Expected: `speech_processor` build 成功，無 error。

- [ ] **Step 1.3: 重啟 session + 跑 10 輪 smoke test**

```bash
bash scripts/start_llm_e2e_tmux.sh
# 在另一個 terminal：
bash scripts/smoke_test_e2e.sh 10
```

**同時人工監聽**：每輪 Go2 是否有聲音。記錄 silent_fail round 編號。

Expected:
- smoke_test 10/10 pass
- 人工判定 silent_fail_count = 0

如果 silent_fail > 0，記錄哪幾輪失敗，繼續下一個 task，步驟 6 回來加 preemptive EXIT。

- [ ] **Step 1.4: Commit**

```bash
git add speech_processor/speech_processor/tts_node.py
git commit -m "fix(speech): add Megaphone 4002 cooldown 0.5s to fix silent fail"
```

---

## Task 2: LLM 回覆收短

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:99-122` (SYSTEM_PROMPT)
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:182` (max_tokens)

- [ ] **Step 2.1: 修改 max_tokens 300 → 120**

在 `_declare_parameters()` 中，將第 182 行：

```python
        self.declare_parameter("llm_max_tokens", 300)
```

改成：

```python
        self.declare_parameter("llm_max_tokens", 120)
```

- [ ] **Step 2.2: 修改 SYSTEM_PROMPT — reply_text 限 25 字**

在 `SYSTEM_PROMPT` 中，將第 110 行：

```python
reply_text — 你要說的中文回覆（簡短自然，15-40字。人臉事件時要叫出對方名字）
```

改成：

```python
reply_text — 你要說的中文回覆（一句話，不超過 25 字。人臉事件時要叫出對方名字）
```

將第 121 行：

```python
- reply_text 不超過 50 字
```

改成：

```python
- reply_text 不超過 25 字
```

- [ ] **Step 2.3: 確認 build 通過**

```bash
colcon build --packages-select speech_processor
source install/setup.zsh
```

- [ ] **Step 2.4: 重啟 session + 5 輪延遲測試**

```bash
bash scripts/start_llm_e2e_tmux.sh
```

對著 Go2 說 5 句話（例如「你好」「你是誰」「現在幾點」「你好嗎」「停止」），記錄每輪：
- speech_end timestamp（stt_intent_node log: `speech_end` 事件或 ASR 開始前的最後 VAD 時間）
- upload_start timestamp（tts_node log: `Megaphone:` 開始上傳 chunks 的時間）
- reply_text 內容
- 回覆是否自然

> **指標說明**：spec 定義的主指標是 `speech_end → Go2 開始出聲（audible start）`。
> 但 Go2 沒有可查詢的播放狀態 API（play_state 永遠回 not_in_use），因此無法精確量測 audible start。
> 這裡用 `speech_end → upload_start` 作為 **proxy 指標**（下界）。實際 audible start 會晚於 upload_start 約 0.5-1s（Megaphone 緩衝 + 解碼延遲）。
> 人工監聽時用碼錶粗估 `speech_end → 聽到聲音` 作為 **體感指標**（上界），兩者取交叉驗證。

Expected（proxy 指標 upload_start）:
- median(speech_end → upload_start) ≤ 5s = Pass
- 5s < median ≤ 6s = Acceptable
- median > 6s = Fail

體感指標參考：人工監聽 median(speech_end → 聽到聲音) 應 ≤ 6s

**Rollback**：如果 llm_bridge_node log 出現 >10% "parse/validation failed"（JSON 被截斷），將 max_tokens 改回 150。

- [ ] **Step 2.5: Commit**

```bash
git add speech_processor/speech_processor/llm_bridge_node.py
git commit -m "perf(speech): reduce LLM max_tokens 300→120 + prompt limit 25 chars"
```

---

## Task 3: ASR Warmup + Inference Lock

**Files:**
- Modify: `speech_processor/speech_processor/stt_intent_node.py:344-356` (transcribe lock)
- Modify: `speech_processor/speech_processor/stt_intent_node.py:311-342` (_ensure_model rename)
- Modify: `speech_processor/speech_processor/stt_intent_node.py:494-501` (warmup thread)

- [ ] **Step 3.1: 將 WhisperLocalProvider.transcribe() 加 self._lock 序列化**

將 `_ensure_model()` 改名為 `_ensure_model_unlocked()` — 去掉內部的 `with self._lock:`，因為 lock 會由外層 `transcribe()` 持有。

將第 311-342 行的 `_ensure_model` 方法：

```python
    def _ensure_model(self) -> None:
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return

            try:
                from faster_whisper import WhisperModel

                self._backend = "faster_whisper"
                self._model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                )
                return
            except Exception:
                pass

            try:
                import whisper

                self._backend = "openai_whisper"
                self._model = whisper.load_model(self.model_name)
                return
            except Exception as exc:
                raise RuntimeError(
                    "Whisper local backend not available. Install faster-whisper or openai-whisper."
                ) from exc
```

改成：

```python
    def _ensure_model_unlocked(self) -> None:
        """Load model if not yet loaded. Caller must hold self._lock."""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel

            self._backend = "faster_whisper"
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            return
        except Exception:
            pass

        try:
            import whisper

            self._backend = "openai_whisper"
            self._model = whisper.load_model(self.model_name)
            return
        except Exception as exc:
            raise RuntimeError(
                "Whisper local backend not available. Install faster-whisper or openai-whisper."
            ) from exc
```

- [ ] **Step 3.2: 將 transcribe() 包在 self._lock 裡**

將第 344-356 行的 `transcribe` 方法：

```python
    def transcribe(
        self, audio_bytes: bytes, sample_rate: int, language: str
    ) -> ASRResult:
        self._ensure_model()
        started = time.monotonic()

        if self._backend == "faster_whisper":
            return self._transcribe_faster_whisper(
                audio_bytes, sample_rate, language, started
            )
        return self._transcribe_openai_whisper(
            audio_bytes, sample_rate, language, started
        )
```

改成：

```python
    def transcribe(
        self, audio_bytes: bytes, sample_rate: int, language: str
    ) -> ASRResult:
        with self._lock:
            self._ensure_model_unlocked()
            started = time.monotonic()

            if self._backend == "faster_whisper":
                return self._transcribe_faster_whisper(
                    audio_bytes, sample_rate, language, started
                )
            return self._transcribe_openai_whisper(
                audio_bytes, sample_rate, language, started
            )
```

- [ ] **Step 3.3: 在 SttIntentNode.__init__ 尾部加 warmup thread**

在第 501 行（`self.get_logger().info(...)` 之後）加入：

```python
        # ASR warmup: preload Whisper model + trigger CUDA JIT in background
        self._warmup_done = False
        threading.Thread(target=self._do_warmup, daemon=True).start()
```

- [ ] **Step 3.4: 新增 _do_warmup 方法**

在 `_declare_parameters` 方法之前（第 502 行附近）加入：

```python
    def _do_warmup(self) -> None:
        """ASR warmup in background thread: preload Whisper model + trigger CUDA JIT.

        Runs in daemon thread to avoid blocking ROS2 executor callbacks.
        Uses self._lock in transcribe() to serialize with first real ASR call.
        """
        whisper = self.providers.get("whisper_local")
        if whisper is None:
            self._warmup_done = True
            return

        self.get_logger().info("ASR warmup started")
        try:
            t0 = time.monotonic()
            silent_pcm = np.zeros(self.sample_rate, dtype=np.float32)
            wav_bytes = self._encode_wav(silent_pcm)
            whisper.transcribe(wav_bytes, self.sample_rate, self.language)
            elapsed = time.monotonic() - t0
            self.get_logger().info(
                f"ASR warmup completed in {elapsed:.1f}s (warmup_done=true)"
            )
        except Exception as e:
            self.get_logger().warn(f"ASR warmup failed (non-fatal): {e}")
        self._warmup_done = True

```

- [ ] **Step 3.5: 確認 build 通過**

```bash
colcon build --packages-select speech_processor
source install/setup.zsh
```

- [ ] **Step 3.6: 驗證 warmup + 首輪 ASR 延遲**

```bash
bash scripts/start_llm_e2e_tmux.sh
```

觀察 stt_intent_node pane log：
1. 應出現 `ASR warmup started`
2. 3-5s 後出現 `ASR warmup completed in X.Xs (warmup_done=true)`
3. warmup 完成後立刻說第一句話
4. 觀察 ASR 延遲（log 中 `latency_ms` 欄位）

Expected: 首輪 ASR 延遲 ≤ 1.5s = Pass

- [ ] **Step 3.7: Commit**

```bash
git add speech_processor/speech_processor/stt_intent_node.py
git commit -m "perf(speech): add ASR warmup thread + inference lock for WhisperLocalProvider"
```

---

## Task 4: force_fallback 參數 + RuleBrain 路徑驗證

**Files:**
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:189-192` (parameter)
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:204-218` (read parameter)
- Modify: `speech_processor/speech_processor/llm_bridge_node.py:342-343` (branch)

- [ ] **Step 4.1: 新增 force_fallback parameter**

在 `_declare_parameters()` 中，第 192 行 `state_publish_hz` 之後加：

```python
        self.declare_parameter("force_fallback", False)
```

- [ ] **Step 4.2: 讀取 force_fallback**

在 `_read_parameters()` 中，第 218 行 `self.state_publish_hz = _float(...)` 之後加：

```python
        self.force_fallback = _bool("force_fallback")
```

- [ ] **Step 4.3: 在 _call_llm_and_act 加 force_fallback 分支**

將第 342-343 行：

```python
        try:
            result = self._call_cloud_llm(user_message)
```

改成：

```python
        try:
            if self.force_fallback:
                self.get_logger().info("force_fallback=True, skipping LLM")
                result = None
            else:
                result = self._call_cloud_llm(user_message)
```

其餘 `if result is not None: ... elif self.enable_fallback: ...` 結構不動。

- [ ] **Step 4.4: 確認 build 通過**

```bash
colcon build --packages-select speech_processor
source install/setup.zsh
```

- [ ] **Step 4.5: 強制 fallback 5 輪驗收**

重啟 llm-e2e session，但 llm_bridge_node 改用 force_fallback:=true。

最簡單的方式是修改 `start_llm_e2e_tmux.sh` 的 llm_bridge_node 啟動行，臨時加 `-p force_fallback:=true`，或者手動在對應 tmux pane 裡重啟 llm_bridge_node：

```bash
ros2 run speech_processor llm_bridge_node --ros-args \
  -p force_fallback:=true \
  -p llm_endpoint:="http://localhost:8000/v1/chat/completions"
```

5 輪固定話術（人工對著 Go2 說）：

| 輪 | 說 | 預期 log |
|----|-----|---------|
| 1 | 你好 | `force_fallback=True` → `RuleBrain fallback: intent=greet` → Go2 說「哈囉，我在這裡。」 |
| 2 | 停止 | `RuleBrain fallback: intent=stop skill=stop_move` → Go2 說「好的，停止動作。」 |
| 3 | 你好嗎 | `RuleBrain fallback: intent=status` → Go2 說「我目前狀態正常。」 |
| 4 | 你好 | 同 1 |
| 5 | 停下來 | 同 2 |

Expected: 5/5 有聲 + intent-action 對齊 + 無 timeout + 無自激 = Pass

- [ ] **Step 4.6: Commit**

```bash
git add speech_processor/speech_processor/llm_bridge_node.py
git commit -m "feat(speech): add force_fallback parameter for RuleBrain path testing"
```

---

## Task 5: 斷 Tunnel 真實 Fallback 驗收

**Files:** 無程式碼改動，純驗證步驟

> **執行位置**：以下所有命令必須在 **Jetson** 上執行（因為 llm_bridge_node 跑在 Jetson 上，SSH tunnel 的 `localhost:8000` 是 Jetson 的 loopback）。不要在 WSL2 開發機上跑——開發機的 localhost:8000 與 Jetson 的無關。

- [ ] **Step 5.1: 斷 SSH tunnel（在 Jetson 上）**

```bash
# 在 Jetson 上執行
pkill -f "ssh.*-L 8000"
curl -sf --max-time 3 http://localhost:8000/v1/models && echo "TUNNEL STILL UP" || echo "TUNNEL DOWN"
```

Expected: `TUNNEL DOWN`

- [ ] **Step 5.2: 重啟 llm_bridge_node（短 timeout + 關閉 force_fallback）**

在 Jetson 的 llm-e2e session 的 llm_bridge_node pane 裡重啟：

```bash
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_timeout:=3.0 \
  -p force_fallback:=false \
  -p llm_endpoint:="http://localhost:8000/v1/chat/completions"
```

- [ ] **Step 5.3: 5 輪固定話術驗收**

與 Task 4 相同的 5 輪話術。觀察 log：
- 應出現 `LLM connection refused` 或 `LLM timeout (3.0s)`
- 緊接著 `LLM failed, falling back to RuleBrain`
- Go2 播放 RuleBrain 回覆

Expected: 5/5 有聲 + intent-action 對齊 = Pass

- [ ] **Step 5.4: 恢復 tunnel（在 Jetson 上）**

```bash
# 在 Jetson 上執行
ssh -f -N -L 8000:localhost:8000 roy422@140.136.155.5
curl -sf --max-time 3 http://localhost:8000/v1/models && echo "TUNNEL UP" || echo "STILL DOWN"
```

---

## Task 6（備案）: Preemptive EXIT — 僅在 Task 1 未達 10/10 時執行

> **Round 2 mitigation only.** 如果 Task 1 已達 10/10，跳過此 task。

**Files:**
- Modify: `speech_processor/speech_processor/tts_node.py:802-804`

- [ ] **Step 6.1: 在 4001 ENTER 前加 preemptive EXIT**

將第 802-804 行：

```python
        # Enter megaphone mode
        self._send_audio_command(4001, json.dumps({}))
        time.sleep(0.1)
```

改成：

```python
        # Preemptive EXIT: reset Go2 Megaphone state in case previous session didn't clean up.
        # Round 2 mitigation only — adds ~0.3s to reaction latency (affects main metric).
        try:
            self._send_audio_command(4002, json.dumps({}))
        except Exception as exc:
            self.get_logger().warn(f"Preemptive EXIT failed: {exc}")
        time.sleep(0.3)

        # Enter megaphone mode
        self._send_audio_command(4001, json.dumps({}))
        time.sleep(0.1)
```

- [ ] **Step 6.2: Build + 10 輪 smoke test**

```bash
colcon build --packages-select speech_processor && source install/setup.zsh
bash scripts/start_llm_e2e_tmux.sh
bash scripts/smoke_test_e2e.sh 10
```

與 Task 1 結果 before/after 對照。

- [ ] **Step 6.3: Commit（如果有改善）**

```bash
git add speech_processor/speech_processor/tts_node.py
git commit -m "fix(speech): add preemptive Megaphone EXIT before ENTER (Round 2)"
```

---

## 總驗收 Checklist

完成 Task 1-5 後：

- [ ] **Megaphone 穩定**：smoke_test 10 輪 + 人工監聽，silent_fail = 0
- [ ] **反應延遲**：5 輪 median(speech_end → playback_start) ≤ 5s
- [ ] **ASR warmup**：首輪 ASR ≤ 1.5s
- [ ] **RuleBrain fallback**：斷 tunnel 5 輪全部有聲 + intent 正確
- [ ] **reply 品質**：抽查 reply_text，回覆自然不呆板

| 目標 | Today baseline | Demo gate |
|------|---------------|-----------|
| Megaphone | ≥ 9/10 | 10/10, silent_fail=0 |
| 延遲 (a) | ≤ 6s | ≤ 5s |
| Fallback | ≥ 4/5 | 5/5 |
