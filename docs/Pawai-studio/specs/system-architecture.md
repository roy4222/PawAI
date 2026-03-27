# PawAI Studio 系統架構

**文件版本**：v1.0
**最後更新**：2026-03-13
**對齊來源**：[mission/README.md](../mission/README.md) v2.0

---

## 快/慢雙系統設計

PawAI 的運算分為兩個系統，對應不同延遲需求：

### 快系統（Fast Path）— Jetson 本地

毫秒級反應，不經過網路。

```
USB 麥克風 → Sherpa-onnx KWS (常駐, ~50MB)
D435 RGB   → YuNet 人臉偵測 (常駐, ~100MB)
D435 RGB   → MediaPipe Hands/Pose (P1, 觸發式)
             → faster-whisper ASR (觸發式)
             → MeloTTS / Piper TTS (觸發式)
             → Safety Guard (常駐)
             → Go2 運動控制 (WebRTC DataChannel)
```

**特徵**：
- 喚醒詞、VAD、人臉偵測 → 常駐，<50ms
- ASR、TTS → 喚醒後載入，<1s（CUDA 加速）
- Safety Guard → stop 命令最高優先級，可打斷任何 skill

### 慢系統（Slow Path）— RTX 8000 雲端

秒級響應，需要網路。

```
ASR 文字 → 雲端 LLM (Qwen3.5-9B/27B, vLLM)
         → 事件理解 + 意圖判斷 + 技能調度建議
         → 回覆文字送回本地 TTS
         → Panel orchestration 指令送 Studio
```

**特徵**：
- LLM 推理 1-3s
- 雲端超時 fallback：2-4s 無回應 → 切換本地 Qwen3.5-0.8B
- Brain 只提建議，不直接控制 Go2

---

## Studio Gateway 架構

Gateway 部署在 RTX 8000 伺服器上，負責 Frontend ↔ ROS2 的橋接。

```
┌─────────────────────────────────────────────────┐
│  Studio Gateway (RTX 8000 Server)                │
│                                                  │
│  ┌──────────────┐  ┌─────────────────────────┐   │
│  │ FastAPI       │  │ WebSocket Manager       │   │
│  │ ├─ REST API   │  │ ├─ /ws/events (事件流)  │   │
│  │ │  /brain     │  │ ├─ /ws/state  (狀態同步)│   │
│  │ │  /timeline  │  │ └─ /ws/chat   (對話)    │   │
│  │ │  /skills    │  │                         │   │
│  │ │  /health    │  │                         │   │
│  │ └─ /command   │  └─────────────────────────┘   │
│  └──────┬───────┘                                 │
│         │                                         │
│  ┌──────┴───────────────────────────────────────┐ │
│  │ Redis Event Bus                               │ │
│  │ ├─ Pub/Sub  → 即時事件通知                    │ │
│  │ ├─ KV       → 最新狀態快取                    │ │
│  │ └─ Streams  → 事件時間軸（最近 1000 條）      │ │
│  └──────┬───────────────────────────────────────┘ │
│         │                                         │
│  ┌──────┴──────┐  ┌────────────────────────────┐  │
│  │ LLM Brain   │  │ ros2_bridge (選擇性部署)   │  │
│  │ (vLLM)      │  │ ROS2 Topics → Redis        │  │
│  │ Qwen3.5-9B  │  │ 部署在 Jetson 或 Gateway   │  │
│  └─────────────┘  └────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### REST API 端點

| 端點 | 方法 | 說明 |
|------|------|------|
| `GET /api/brain` | GET | 當前大腦狀態 |
| `GET /api/timeline` | GET | 事件時間軸（分頁） |
| `GET /api/health` | GET | 系統健康狀態 |
| `POST /api/command` | POST | 發送技能指令 |
| `POST /api/chat` | POST | 發送對話訊息 |

### WebSocket 頻道

| 頻道 | 方向 | 說明 |
|------|------|------|
| `/ws/events` | Server → Client | 即時事件推送 |
| `/ws/state` | Server → Client | 狀態變更推送 |
| `/ws/chat` | 雙向 | 對話訊息 |

---

## ros2_bridge 設計

橋接 ROS2 Topics ↔ Redis Event Bus。

### 訂閱的 ROS2 Topics

| Topic | 寫入 Redis | 說明 |
|-------|-----------|------|
| `/state/perception/face` | KV + Pub/Sub | 人臉狀態 |
| `/state/interaction/speech` | KV + Pub/Sub | 語音狀態 |
| `/state/executive/brain` | KV + Pub/Sub | 大腦狀態 |
| `/event/face_identity` | Streams + Pub/Sub | 人臉身份事件 |
| `/event/speech_intent_recognized` | Streams + Pub/Sub | 語音意圖事件 |
| `/event/gesture_detected` | Streams + Pub/Sub | 手勢事件 (P1) |
| `/event/pose_detected` | Streams + Pub/Sub | 姿勢事件 (P1) |

### 反向指令（Frontend → ROS2）

| 來源 | ROS2 Topic | 說明 |
|------|-----------|------|
| `POST /api/command` | `/webrtc_req` | 技能指令 |
| `POST /api/chat` | `/tts` (經 Brain 處理) | 對話輸入 |

---

## Mock Event Server

讓前端團隊不需要真機和 Jetson 即可開發。

### 功能

1. **事件重播**：讀取預錄的事件序列 JSON，按時間戳回放
2. **隨機生成**：按設定頻率產生假 face/speech/gesture 事件
3. **手動觸發**：REST API 手動發射指定事件
4. **場景模擬**：預設 Demo A/B/C 場景腳本

### 端點

| 端點 | 說明 |
|------|------|
| `POST /mock/replay` | 開始事件重播 |
| `POST /mock/trigger` | 手動觸發單一事件 |
| `POST /mock/scenario/{name}` | 執行預設場景（demo_a / demo_b / demo_c） |
| `GET /mock/status` | Mock Server 狀態 |

### 事件序列範例（Demo A）

```json
[
  {"t": 0.0,  "topic": "face_identity",  "data": {"event_type": "track_started", "track_id": 1}},
  {"t": 1.5,  "topic": "face_identity",  "data": {"event_type": "identity_stable", "track_id": 1, "stable_name": "Roy", "sim": 0.42}},
  {"t": 3.0,  "topic": "speech_intent",  "data": {"intent": "greet", "text": "你好", "confidence": 0.95}},
  {"t": 4.0,  "topic": "brain_state",    "data": {"state": "responding", "skill": "greet_person"}},
  {"t": 4.5,  "topic": "tts_status",     "data": {"state": "speaking", "text": "哈囉 Roy，你好！"}},
  {"t": 7.0,  "topic": "brain_state",    "data": {"state": "idle"}}
]
```

---

## 部署拓撲

```
┌─ 開發機 (Windows/Mac) ─────────────┐
│  VS Code + Next.js dev server       │
│  → http://localhost:3000            │
│  → ws://rtx-server:8000/ws/*       │
└─────────────────────────────────────┘

┌─ RTX 8000 Server ──────────────────┐
│  Studio Gateway (FastAPI :8000)     │
│  Redis (:6379)                      │
│  vLLM (Qwen3.5-9B :8080)          │
│  Mock Event Server (:8001)         │
└─────────────────────────────────────┘

┌─ Jetson Orin Nano ─────────────────┐
│  ROS2 Humble                        │
│  ros2_bridge_node → Redis          │
│  全部感知 + Executive 節點          │
└─────────────────────────────────────┘

┌─ Go2 Pro ──────────────────────────┐
│  WebRTC DataChannel                 │
│  運動控制 + 音訊播放                │
└─────────────────────────────────────┘
```

---

*最後更新：2026-03-13*
*維護者：System Architect*
