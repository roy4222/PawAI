# Ports & Environment Variables — Brain × Studio Lane

## Network ports

| Port | 服務 | 跑在哪 | 用途 |
|---|---|---|---|
| 8000 | LLM API endpoint | Jetson localhost (SSH tunnel) | Cloud LLM (vLLM Qwen2.5-7B on RTX 8000) |
| 8001 | ASR API endpoint | Jetson localhost (SSH tunnel) | SenseVoice cloud ASR |
| 8080 | studio_gateway | Jetson (Tailscale 100.83.109.89) | Studio API + WebSocket |
| 3000 | Next.js frontend | WSL/Mac localhost | Studio UI；占用時自動 fallback 3001/3002 |
| 8765 | foxglove_bridge | Jetson | RViz/Foxglove 可視化（可選） |
| 11434 | Ollama local LLM | Jetson | LLM cloud 斷線 fallback（可選） |

## SSH tunnels（在哪台機器跑）

```bash
# 從 Jetson 走 tunnel 到 RTX 8000 server（已經設好的話會 listen 8000/8001）
ssh -f -N -L 8000:localhost:8000 -L 8001:localhost:8001 user@rtx-server

# 確認 tunnel：
ssh jetson-nano "ss -tlnp | grep -E ':8000|:8001'"
# 應該看到 LISTEN 127.0.0.1:8000/8001
```

## Environment variables

### 路徑（**Jetson 與 WSL 不同**）

| Var | WSL | Jetson |
|---|---|---|
| `WORKSPACE` | `/home/roy422/newLife/elder_and_dog` | `/home/jetson/elder_and_dog` |
| repo path | 同 WORKSPACE | 同 WORKSPACE |
| persona dir | `$WORKSPACE/install/pawai_brain/share/pawai_brain/personas/v1/` | 同 |
| .env | `$WORKSPACE/.env` | 同 |

> ⚠️ `start_pawai_brain_tmux.sh` default `WORKSPACE=$HOME/newLife/elder_and_dog`，
> Jetson 上**必須** `WORKSPACE=/home/jetson/elder_and_dog` override。
> skill 的 start.sh 已自動帶。

### Brain runtime

```bash
# .env 必填（在 ~/elder_and_dog/.env）
OPENROUTER_API_KEY=sk-or-...

# launch param（pawai_conversation_graph.launch.py 預設）
llm_persona_file=$WORKSPACE/install/pawai_brain/share/pawai_brain/personas/v1
llm_temperature=0.8
openrouter_gemini_model=google/gemini-3-flash-preview
openrouter_request_timeout_s=4.0
openrouter_overall_budget_s=5.0
enable_openrouter=true   # ROS param，預設 true，但 OPENROUTER_API_KEY 空就 fallback
```

### TTS

```bash
TTS_PROVIDER=edge_tts                # or piper
EDGE_TTS_VOICE=zh-CN-XiaoxiaoNeural  # provider 內部 mapping
PIPER_MODEL_PATH=/home/jetson/models/piper/zh_CN-huayan-medium.onnx
LOCAL_PLAYBACK=true                  # local plughw 播
LOCAL_OUTPUT_DEVICE=plughw:CD002AUDIO,0   # 用 card name 不要用 number（會漂移）
PLAYBACK_METHOD=local                # 或 datachannel（走 Go2 megaphone）
```

### ASR (e2e/full mode)

```bash
INPUT_DEVICE=24      # USB UACDemoV1.0 = 24, HyperX SoloCast = 0
CHANNELS=1           # USB mono / HyperX 2 (stereo-only 硬體限制)
CAPTURE_SAMPLE_RATE=48000  # USB 48kHz / HyperX 44100
MIC_GAIN=4.0
QWEN_ASR_BASE_URL=http://127.0.0.1:8001/v1/audio/transcriptions
ASR_PROVIDER_ORDER='["sensevoice_cloud","sensevoice_local","whisper_local"]'
```

### Studio gateway / Frontend

```bash
GATEWAY_PORT=8080
GATEWAY_HOST=100.83.109.89             # Jetson Tailscale IP
NEXT_PUBLIC_GATEWAY_URL=http://100.83.109.89:8080  # frontend env
LLM_HOST=localhost                     # Jetson 上 cloud LLM tunnel
ASR_HOST=localhost                     # Jetson 上 cloud ASR tunnel
```

### Go2

```bash
ROBOT_IP=192.168.123.161  # Ethernet 直連
CONN_TYPE=webrtc
```

## .env 範例（Jetson `~/elder_and_dog/.env`）

```bash
# Cloud APIs
OPENROUTER_API_KEY=sk-or-...
QWEN_ASR_BASE_URL=http://127.0.0.1:8001/v1/audio/transcriptions

# Hardware
INPUT_DEVICE=24
CHANNELS=1
CAPTURE_SAMPLE_RATE=48000
MIC_GAIN=4.0
LOCAL_OUTPUT_DEVICE=plughw:CD002AUDIO,0

# Go2
ROBOT_IP=192.168.123.161
CONN_TYPE=webrtc
```

## tmux pane 環境繼承陷阱

tmux pane 是 fresh shell，**不繼承父 process 的 env**。`start_*.sh` 的 SOURCE_CMD 必須包含 `.env` source：

```bash
SOURCE_CMD="source /opt/ros/humble/setup.zsh && cd $WORKSPACE && source install/setup.zsh && \
  { [[ -f $WORKSPACE/.env ]] && set -a && source $WORKSPACE/.env && set +a; } || true"
```

`start_pawai_brain_tmux.sh` 之前少這段 → conv_graph 出 `openrouter=off`。skill 已 patch 既有腳本（提交 commit）。

## plughw card# 漂移

USB CD002-AUDIO 喇叭的 card index 隨啟動順序變（card 0/1/2/3 都看過）。
不要寫死 `plughw:3,0`，用 card name 或 runtime 偵測：

```bash
# Skill 內用 card name（推薦）
LOCAL_OUTPUT_DEVICE=plughw:CD002AUDIO,0

# Runtime 偵測 fallback
SPEAKER=$(aplay -l | grep -i 'cd002' | head -1 | awk '{print $2}' | tr -d ',')
LOCAL_OUTPUT_DEVICE=plughw:$SPEAKER,0
```

## Cloud LLM fallback chain

```
1. cloud LLM (gemini-3-flash via OpenRouter)
   ↓ timeout 5s 或無 OPENROUTER_API_KEY
2. local LLM (Ollama qwen2.5:1.5b on Jetson)
   ↓ Ollama 沒起
3. RuleBrain (純規則式回答)
```

只要任一層活，conv_graph 都會回 reply（不會炸）。但自然度差距大：cloud > local > rule。
