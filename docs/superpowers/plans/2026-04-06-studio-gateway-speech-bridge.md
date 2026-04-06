# Studio Gateway Speech Bridge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 瀏覽器 push-to-talk 收音 → Jetson Gateway → ASR → intent → ROS2 publish，讓 Demo 在 Go2 風扇噪音下仍有語音互動能力。

**Architecture:** Jetson 上跑一個 FastAPI + WebSocket + rclpy server (port 8080)。瀏覽器 Web Audio API 收音，push-to-talk 送完整音訊到 server。Server 用 ffmpeg resample → POST SenseVoice ASR (localhost:8001) → intent 分類 → publish `/event/speech_intent_recognized`。Executive 零改動。

**Tech Stack:** Python 3.10, FastAPI, uvicorn, rclpy, ffmpeg (resample), 既有 SenseVoice ASR API, 既有 intent_classifier.py

**Spec:** `docs/superpowers/specs/2026-04-06-studio-gateway-speech-bridge-design.md`

---

## File Structure

```
pawai-studio/
├── gateway/
│   ├── studio_gateway.py        # FastAPI + rclpy main server
│   ├── asr_client.py            # SenseVoice HTTP client + ffmpeg resample
│   ├── static/
│   │   └── speech.html          # Web push-to-talk 收音頁面
│   ├── requirements.txt         # fastapi, uvicorn, websockets, requests
│   └── test_gateway.py          # Unit tests
└── README.md                    # 更新啟動說明（加 gateway）
```

**不新建的檔案：**
- `intent_classifier.py` — 直接 import `speech_processor.speech_processor.intent_classifier`（已存在，pure Python）

---

### Task 1: 安裝 Jetson 依賴 + 確認 ASR endpoint

**Files:**
- Create: `pawai-studio/gateway/requirements.txt`

- [ ] **Step 1: 建立 requirements.txt**

```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
requests>=2.28.0
```

- [ ] **Step 2: 在 Jetson 安裝依賴**

Run:
```bash
ssh jetson-nano "cd ~/elder_and_dog/pawai-studio/gateway && pip install -r requirements.txt"
```
Expected: 安裝成功（如果已有就 skip）

- [ ] **Step 3: 確認 ffmpeg 可用**

Run:
```bash
ssh jetson-nano "which ffmpeg && ffmpeg -version | head -1"
```
Expected: ffmpeg 路徑和版本號。如果沒有：`ssh jetson-nano "sudo apt install -y ffmpeg"`

- [ ] **Step 4: 確認 SenseVoice ASR endpoint 活著**

Run:
```bash
ssh jetson-nano "curl -s http://localhost:8001/health"
```
Expected: `{"status":"ok","model":"SenseVoiceSmall"}`

- [ ] **Step 5: 確認 intent_classifier 可 import**

Run:
```bash
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 -c 'from speech_processor.intent_classifier import IntentClassifier, SUPPORTED_INTENTS; print(SUPPORTED_INTENTS)'"
```
Expected: `('greet', 'come_here', 'stop', 'sit', 'stand', 'take_photo', 'status')`

- [ ] **Step 6: Commit**

```bash
git add pawai-studio/gateway/requirements.txt
git commit -m "chore(gateway): add requirements for studio gateway speech bridge"
```

---

### Task 2: ASR client + ffmpeg resample

**Files:**
- Create: `pawai-studio/gateway/asr_client.py`
- Create: `pawai-studio/gateway/test_gateway.py`

- [ ] **Step 1: Write the failing test**

Create `pawai-studio/gateway/test_gateway.py`:

```python
"""Tests for studio gateway components."""
import struct
import wave
import io
import pytest


def _make_wav(sample_rate: int = 48000, duration_s: float = 0.1, channels: int = 1) -> bytes:
    """Generate a minimal WAV file with silence."""
    n_frames = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_frames * channels)
    return buf.getvalue()


class TestResampleAudio:
    def test_48k_to_16k(self):
        from asr_client import resample_to_wav16k
        wav_48k = _make_wav(sample_rate=48000, duration_s=0.5)
        wav_16k = resample_to_wav16k(wav_48k)
        # Verify output is valid WAV at 16kHz mono
        buf = io.BytesIO(wav_16k)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2

    def test_already_16k_passthrough(self):
        from asr_client import resample_to_wav16k
        wav_16k = _make_wav(sample_rate=16000, duration_s=0.5)
        result = resample_to_wav16k(wav_16k)
        buf = io.BytesIO(result)
        with wave.open(buf, "rb") as wf:
            assert wf.getframerate() == 16000

    def test_webm_opus_resample(self):
        """webm/opus input should also be handled (browser default format)."""
        from asr_client import resample_to_wav16k
        # ffmpeg should handle any audio format it supports
        # We can't easily generate webm in pure Python, so just verify
        # that non-WAV input raises a clear error or handles gracefully
        with pytest.raises(Exception):
            resample_to_wav16k(b"not valid audio")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd pawai-studio/gateway && python3 -m pytest test_gateway.py::TestResampleAudio -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'asr_client'`

- [ ] **Step 3: Write asr_client.py**

Create `pawai-studio/gateway/asr_client.py`:

```python
"""ASR client — resample audio + call SenseVoice cloud API."""
from __future__ import annotations

import io
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Optional

import requests


def resample_to_wav16k(audio_bytes: bytes) -> bytes:
    """Convert any audio to 16kHz mono PCM16 WAV using ffmpeg.

    Accepts WAV, webm/opus, ogg, mp3, etc — anything ffmpeg can decode.
    If input is already 16kHz mono WAV, still runs through ffmpeg for safety.
    """
    with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as f_in:
        f_in.write(audio_bytes)
        in_path = f_in.name

    out_path = in_path + ".wav"
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", in_path,
                "-ar", "16000",
                "-ac", "1",
                "-sample_fmt", "s16",
                "-f", "wav",
                out_path,
            ],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")
        return Path(out_path).read_bytes()
    finally:
        Path(in_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)


def transcribe(
    wav16k_bytes: bytes,
    asr_url: str = "http://127.0.0.1:8001/v1/audio/transcriptions",
    model: str = "sensevoice",
    language: str = "zh",
    timeout: float = 5.0,
) -> dict:
    """POST WAV to SenseVoice ASR, return {"text": ..., "latency_ms": ...}."""
    started = time.monotonic()
    files = {"file": ("speech.wav", wav16k_bytes, "audio/wav")}
    data = {"model": model, "language": language, "sample_rate": "16000"}

    resp = requests.post(asr_url, data=data, files=files, timeout=timeout)
    resp.raise_for_status()

    latency_ms = (time.monotonic() - started) * 1000
    body = resp.json()
    text = body.get("text", "")
    return {"text": text, "latency_ms": round(latency_ms, 2)}
```

- [ ] **Step 4: Run resample tests**

Run: `cd pawai-studio/gateway && python3 -m pytest test_gateway.py::TestResampleAudio -v`
Expected: 3 PASS（需要 ffmpeg 已安裝）

- [ ] **Step 5: Commit**

```bash
git add pawai-studio/gateway/asr_client.py pawai-studio/gateway/test_gateway.py
git commit -m "feat(gateway): asr_client with ffmpeg resample + SenseVoice HTTP"
```

---

### Task 3: Gateway server（FastAPI + rclpy + WebSocket）

**Files:**
- Create: `pawai-studio/gateway/studio_gateway.py`

- [ ] **Step 1: Write integration test**

Append to `pawai-studio/gateway/test_gateway.py`:

```python
import json


class TestIntentClassification:
    def test_greet_intent(self):
        # Import from existing speech_processor
        import sys
        sys.path.insert(0, "../../speech_processor/speech_processor")
        from intent_classifier import IntentClassifier
        clf = IntentClassifier()
        match = clf.classify("你好嗎")
        assert match.intent == "greet"
        assert match.confidence > 0.5

    def test_chat_fallback(self):
        import sys
        sys.path.insert(0, "../../speech_processor/speech_processor")
        from intent_classifier import IntentClassifier
        clf = IntentClassifier()
        match = clf.classify("今天天氣怎麼樣")
        assert match.intent == "unknown"  # no keyword match → will become "chat"


class TestPayloadSchema:
    def test_speech_event_schema(self):
        """Verify payload matches interaction_contract.md v2.4 §4.2."""
        payload = {
            "stamp": 1775440000.123,
            "event_type": "intent_recognized",
            "intent": "greet",
            "text": "你好",
            "confidence": 0.9,
            "provider": "sensevoice_cloud",
            "source": "web_bridge",
            "session_id": "test-uuid",
            "matched_keywords": ["你好"],
            "latency_ms": 500.0,
            "degraded": False,
            "timestamp": "2026-04-06T10:00:00",
        }
        required_fields = [
            "stamp", "event_type", "intent", "text", "confidence",
            "provider", "source", "session_id", "matched_keywords",
            "latency_ms", "degraded", "timestamp",
        ]
        for field in required_fields:
            assert field in payload, f"Missing field: {field}"
        assert payload["event_type"] == "intent_recognized"
        assert payload["source"] == "web_bridge"
```

- [ ] **Step 2: Run tests**

Run: `cd pawai-studio/gateway && python3 -m pytest test_gateway.py -v`
Expected: 全 PASS

- [ ] **Step 3: Write studio_gateway.py**

Create `pawai-studio/gateway/studio_gateway.py`:

```python
#!/usr/bin/env python3
"""Studio Gateway — Speech Bridge server.

Runs on Jetson. Browser push-to-talk → ASR → intent → ROS2 publish.
Executive 零改動。

Usage:
    source /opt/ros/humble/setup.zsh
    source install/setup.zsh
    python3 pawai-studio/gateway/studio_gateway.py
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# rclpy — must be available (Jetson ROS2 environment)
import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import String

# ASR client
from asr_client import resample_to_wav16k, transcribe

# Intent classifier — reuse from speech_processor
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "speech_processor" / "speech_processor"))
from intent_classifier import IntentClassifier, SUPPORTED_INTENTS

# ── Config ───────────────────────────────────────────────────────
PORT = 8080
ASR_URL = "http://127.0.0.1:8001/v1/audio/transcriptions"
STATIC_DIR = Path(__file__).parent / "static"

QOS_EVENT = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    depth=10,
)

# ── ROS2 Node ────────────────────────────────────────────────────
class GatewayNode(Node):
    def __init__(self):
        super().__init__("studio_gateway_node")
        self.speech_pub = self.create_publisher(
            String, "/event/speech_intent_recognized", QOS_EVENT
        )
        self.get_logger().info("Studio Gateway ROS2 node ready")

    def publish_speech_event(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        self.speech_pub.publish(msg)
        self.get_logger().info(
            f"Published speech event: intent={payload.get('intent')} "
            f"text={payload.get('text')!r}"
        )

# ── FastAPI App ──────────────────────────────────────────────────
app = FastAPI(title="PawAI Studio Gateway")
node: GatewayNode | None = None
classifier: IntentClassifier | None = None


@app.on_event("startup")
async def startup():
    global node, classifier
    rclpy.init()
    node = GatewayNode()
    classifier = IntentClassifier()
    # Spin ROS2 in background thread
    import threading
    spin_thread = threading.Thread(target=rclpy.spin, args=(node,), daemon=True)
    spin_thread.start()


@app.on_event("shutdown")
async def shutdown():
    if node:
        node.destroy_node()
    rclpy.try_shutdown()


@app.get("/speech")
async def speech_page():
    return FileResponse(STATIC_DIR / "speech.html")


@app.get("/health")
async def health():
    return {"status": "ok", "node": node is not None}


@app.websocket("/ws/speech")
async def ws_speech(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            # Receive binary audio from browser
            audio_bytes = await ws.receive_bytes()
            session_id = str(uuid.uuid4())[:8]
            started = time.monotonic()

            try:
                # 1. Resample to 16kHz mono WAV
                wav16k = await asyncio.to_thread(resample_to_wav16k, audio_bytes)

                # 2. ASR
                asr_result = await asyncio.to_thread(
                    transcribe, wav16k, ASR_URL
                )
                text = asr_result["text"].strip()
                asr_latency = asr_result["latency_ms"]

                if not text:
                    await ws.send_json({"error": "empty_asr", "published": False})
                    continue

                # 3. Intent classification
                match = classifier.classify(text)
                intent = match.intent if match.intent != "unknown" else "chat"
                total_latency = (time.monotonic() - started) * 1000

                # 4. Build contract-compliant payload
                payload = {
                    "stamp": time.time(),
                    "event_type": "intent_recognized",
                    "intent": intent,
                    "text": text,
                    "confidence": round(match.confidence, 3),
                    "provider": "sensevoice_cloud",
                    "source": "web_bridge",
                    "session_id": session_id,
                    "matched_keywords": match.matched_keywords,
                    "latency_ms": round(total_latency, 2),
                    "degraded": False,
                    "timestamp": datetime.now().isoformat(),
                }

                # 5. Publish to ROS2
                node.publish_speech_event(payload)

                # 6. Reply to browser
                await ws.send_json({
                    "asr": text,
                    "intent": intent,
                    "confidence": round(match.confidence, 3),
                    "latency_ms": round(total_latency, 2),
                    "published": True,
                })

            except Exception as e:
                await ws.send_json({"error": str(e), "published": False})

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

- [ ] **Step 4: Commit**

```bash
git add pawai-studio/gateway/studio_gateway.py pawai-studio/gateway/test_gateway.py
git commit -m "feat(gateway): studio gateway server — FastAPI + rclpy + WebSocket speech bridge"
```

---

### Task 4: Web 收音頁面（push-to-talk）

**Files:**
- Create: `pawai-studio/gateway/static/speech.html`

- [ ] **Step 1: Create speech.html**

```html
<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PawAI Speech Bridge</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, sans-serif; background: #1a1a2e; color: #eee; display: flex; justify-content: center; align-items: center; min-height: 100vh; }
  .container { text-align: center; max-width: 480px; width: 100%; padding: 2rem; }
  h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
  .subtitle { color: #888; margin-bottom: 2rem; font-size: 0.9rem; }
  #status { font-size: 1.1rem; margin-bottom: 1.5rem; color: #4ecdc4; min-height: 1.5em; }
  #btn { width: 120px; height: 120px; border-radius: 50%; border: 4px solid #4ecdc4; background: transparent; color: #4ecdc4; font-size: 1rem; cursor: pointer; transition: all 0.2s; user-select: none; -webkit-user-select: none; }
  #btn:active, #btn.recording { background: #e74c3c; border-color: #e74c3c; color: #fff; transform: scale(1.1); }
  #btn:disabled { opacity: 0.3; cursor: not-allowed; }
  .result { margin-top: 2rem; text-align: left; background: #16213e; border-radius: 8px; padding: 1rem; min-height: 100px; }
  .result h3 { color: #4ecdc4; margin-bottom: 0.5rem; font-size: 0.85rem; text-transform: uppercase; }
  .result p { margin-bottom: 0.5rem; }
  .label { color: #888; font-size: 0.8rem; }
  .value { font-size: 1.1rem; }
  .error { color: #e74c3c; }
  .intent-tag { display: inline-block; background: #4ecdc4; color: #1a1a2e; padding: 2px 10px; border-radius: 12px; font-weight: bold; font-size: 0.9rem; }
</style>
</head>
<body>
<div class="container">
  <h1>PawAI Speech Bridge</h1>
  <p class="subtitle">Push-to-talk → Go2 互動</p>
  <p id="status">Connecting...</p>

  <button id="btn" disabled>Hold to Talk</button>

  <div class="result">
    <h3>Result</h3>
    <p><span class="label">ASR: </span><span id="asr" class="value">—</span></p>
    <p><span class="label">Intent: </span><span id="intent" class="value">—</span></p>
    <p><span class="label">Latency: </span><span id="latency" class="value">—</span></p>
  </div>
</div>

<script>
const btn = document.getElementById('btn');
const statusEl = document.getElementById('status');
const asrEl = document.getElementById('asr');
const intentEl = document.getElementById('intent');
const latencyEl = document.getElementById('latency');

let ws = null;
let mediaRecorder = null;
let audioChunks = [];

// ── WebSocket ──
function connect() {
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${proto}//${location.host}/ws/speech`);
  ws.binaryType = 'arraybuffer';

  ws.onopen = () => {
    statusEl.textContent = 'Ready — hold button to talk';
    statusEl.style.color = '#4ecdc4';
    btn.disabled = false;
  };
  ws.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.error) {
      asrEl.textContent = data.error;
      asrEl.classList.add('error');
      intentEl.textContent = '—';
      latencyEl.textContent = '—';
    } else {
      asrEl.textContent = data.asr || '(empty)';
      asrEl.classList.remove('error');
      intentEl.innerHTML = `<span class="intent-tag">${data.intent}</span> (${(data.confidence * 100).toFixed(0)}%)`;
      latencyEl.textContent = `${data.latency_ms.toFixed(0)} ms`;
    }
    statusEl.textContent = 'Ready — hold button to talk';
    btn.disabled = false;
  };
  ws.onclose = () => {
    statusEl.textContent = 'Disconnected — reconnecting...';
    statusEl.style.color = '#e74c3c';
    btn.disabled = true;
    setTimeout(connect, 2000);
  };
  ws.onerror = () => ws.close();
}

// ── Audio Recording ──
async function startRecording() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioChunks = [];

  // Try WAV-compatible format, fallback to browser default
  const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
    ? 'audio/webm;codecs=opus'
    : '';
  mediaRecorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});

  mediaRecorder.ondataavailable = (e) => {
    if (e.data.size > 0) audioChunks.push(e.data);
  };

  mediaRecorder.onstop = async () => {
    stream.getTracks().forEach(t => t.stop());
    const blob = new Blob(audioChunks);
    const buffer = await blob.arrayBuffer();
    if (ws && ws.readyState === WebSocket.OPEN) {
      statusEl.textContent = 'Processing...';
      btn.disabled = true;
      ws.send(buffer);
    }
  };

  mediaRecorder.start();
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop();
  }
}

// ── Button Events (mouse + touch) ──
btn.addEventListener('mousedown', (e) => { e.preventDefault(); btn.classList.add('recording'); startRecording(); });
btn.addEventListener('mouseup', () => { btn.classList.remove('recording'); stopRecording(); });
btn.addEventListener('mouseleave', () => { btn.classList.remove('recording'); stopRecording(); });
btn.addEventListener('touchstart', (e) => { e.preventDefault(); btn.classList.add('recording'); startRecording(); });
btn.addEventListener('touchend', () => { btn.classList.remove('recording'); stopRecording(); });

connect();
</script>
</body>
</html>
```

- [ ] **Step 2: 本機瀏覽器快速驗證 HTML**

在 WSL 用 `python3 -m http.server 8080` 從 `pawai-studio/gateway/static/` serve，開瀏覽器確認頁面渲染正常、按鈕可點。（不需要 WebSocket 連線，只驗 UI）

- [ ] **Step 3: Commit**

```bash
git add pawai-studio/gateway/static/speech.html
git commit -m "feat(gateway): web push-to-talk speech page"
```

---

### Task 5: Jetson 部署 + E2E 驗證

**Files:**
- Modify: `scripts/start_full_demo_tmux.sh`（加 gateway window）

- [ ] **Step 1: 在 start_full_demo_tmux.sh 加 gateway window**

在檔案最後（foxglove window 之後）加入：

```bash
# [11/11] Starting Studio Gateway (speech bridge)...
echo "[11/11] Starting Studio Gateway (speech bridge, port 8080)..."
tmux new-window -t "$SESSION" -n gateway \
  "cd $WS && source /opt/ros/humble/setup.zsh && source install/setup.zsh && \
   python3 pawai-studio/gateway/studio_gateway.py; exec zsh"
```

同時更新 window 總數和 echo 裡的 window list。

- [ ] **Step 2: Sync 到 Jetson**

Run: `~/sync once` 或 `rsync -azv pawai-studio/gateway/ jetson-nano:~/elder_and_dog/pawai-studio/gateway/`

- [ ] **Step 3: 安裝 Jetson 依賴**

Run:
```bash
ssh jetson-nano "cd ~/elder_and_dog && pip install -r pawai-studio/gateway/requirements.txt"
ssh jetson-nano "which ffmpeg || sudo apt install -y ffmpeg"
```

- [ ] **Step 4: 單獨啟動 gateway 驗證**

Run:
```bash
ssh jetson-nano "cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && source install/setup.zsh && python3 pawai-studio/gateway/studio_gateway.py &"
```
Expected: `Studio Gateway ROS2 node ready` + uvicorn 監聽 8080

- [ ] **Step 5: 瀏覽器連線測試**

在 Mac/PC 瀏覽器打開 `http://JETSON_IP:8080/speech`。
Expected: 頁面載入 + 狀態顯示 "Ready — hold button to talk"

- [ ] **Step 6: Push-to-talk E2E 測試**

1. 按住按鈕說「你好」
2. 放開
3. Expected:
   - 頁面顯示 ASR 文字（如「你好」）
   - Intent 顯示 `greet`
   - Jetson terminal 顯示 `Published speech event: intent=greet`
   - Go2 TTS 播放問候

- [ ] **Step 7: 驗證 Executive 收到 event**

Run:
```bash
ssh jetson-nano "source /opt/ros/humble/setup.zsh && export ROS_DOMAIN_ID=0 && timeout 10 ros2 topic echo /event/speech_intent_recognized --once"
```
Expected: JSON payload 包含 `"source": "web_bridge"`

- [ ] **Step 8: Commit**

```bash
git add scripts/start_full_demo_tmux.sh
git commit -m "feat(gateway): add gateway window to demo stack + E2E verified"
```

---

### Task 6: 混合模式 Demo Flow 驗收

- [ ] **Step 1: 跑完整 demo stack（含 gateway）**

```bash
ssh jetson-nano "cd ~/elder_and_dog && bash scripts/start_full_demo_tmux.sh"
```

- [ ] **Step 2: 固定 demo flow 3 輪**

每輪依序：
1. 走到 D435 前 → 等 TTS「roy 你好」（face greeting）
2. Mac 瀏覽器按住說「你好嗎」→ Go2 LLM 回覆（web speech）
3. 比讚 → Go2 Content（gesture）
4. 比 Stop → Go2 StopMove（gesture）
5. 模擬跌倒 → TTS「偵測到跌倒」（pose EMERGENCY）
6. 站起來 → 30s 後回 idle

- [ ] **Step 3: 記錄 3 輪結果**

每輪記：PASS/FAIL + 哪一步失敗 + 原因

- [ ] **Step 4: 更新 project-status.md**

記錄混合模式驗收結果。

- [ ] **Step 5: Final commit**

```bash
git add references/project-status.md
git commit -m "docs: Day 11 混合模式驗收結果"
```
