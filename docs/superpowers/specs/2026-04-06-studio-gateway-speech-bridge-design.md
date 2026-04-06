# Studio Gateway — Speech Bridge（最小可用版）

**日期**：2026-04-06
**狀態**：approved
**觸發原因**：Go2 風扇噪音導致機身 ASR 不可用，需要外部語音入口
**原則**：把 speech bridge 做成 Studio Gateway 的第一個可用能力，不做完整 Studio

---

## 1. 一句話定位

瀏覽器 push-to-talk 收音 → Jetson Gateway ASR → intent → ROS2 publish → Executive 零改動。

## 2. 架構

```
[任何裝置的瀏覽器]
  http://JETSON_IP:8080/speech
  push-to-talk 按鈕錄音 → 送出原始音訊（瀏覽器原生 sample rate）
         ↓ WebSocket /ws/speech（binary）
[Jetson: studio_gateway.py]
  FastAPI + WebSocket + rclpy
  ├── 收到 WAV → POST http://localhost:8001 (SenseVoice ASR)
  ├── ASR 文字 → intent_rules 分類
  ├── rclpy publish /event/speech_intent_recognized
  └── WebSocket 回傳結果給瀏覽器
         ↓ ROS2 topic（本機，零跨機）
[Jetson: interaction_executive_node（零改動）]
```

## 3. 設計決策

| 決策 | 選擇 | 原因 |
|------|------|------|
| Server 位置 | Jetson 本機 | rclpy 直接 publish，避開跨機 DDS |
| 收音方式 | 瀏覽器 Web Audio API | 平台無關，Mac/Windows/手機都能用 |
| 音訊傳輸 | push-to-talk，錄完整段送 | 最低風險，不做即時串流 |
| 音訊格式 | 瀏覽器錄原始音訊，server 負責 resample | 瀏覽器不保證 16kHz，server 統一處理 |
| ASR | SenseVoice cloud (port 8001) | 沿用既有 tunnel，不新增依賴 |
| Intent 分類 | 從 stt_intent_node 抽出 | 複用現有 rules，保持一致 |
| 前端 VAD | 不做 | push-to-talk 就夠 |
| 認證 | 不做 | 內網 Demo 用 |

## 4. 元件規格

### 4.1 Web 頁面（`static/speech.html`）

- 單頁，純 HTML + JS，無框架
- Web Audio API 取 mic permission
- push-to-talk 按鈕：按下開始錄音，放開送出
- 錄音：MediaRecorder API 取瀏覽器原生 sample rate（通常 48kHz），輸出 webm/opus 或 WAV
- WebSocket 連 `ws://JETSON_IP:8080/ws/speech`，送 binary audio blob
- **不做前端 resample**：server 端負責轉換成 SenseVoice 需要的 16kHz mono WAV
- 顯示區域：
  - 錄音狀態（idle / recording / processing）
  - ASR 文字結果
  - Intent 分類結果
  - publish 狀態（success / error）

### 4.2 Gateway Server（`studio_gateway.py`）

- FastAPI + uvicorn，port 8080
- 啟動時初始化 rclpy node（`studio_gateway_node`）
- 靜態檔案 serve：`/speech` → `static/speech.html`

**WebSocket endpoint `/ws/speech`**：
1. 收到 binary message（audio bytes，可能是 webm/opus 或 WAV）
2. Server 端 resample 到 16kHz mono WAV（用 ffmpeg 或 scipy/librosa）
3. POST `http://localhost:8001`（SenseVoice ASR）
4. 解析 ASR 回傳文字
5. intent_rules 分類（複用 stt_intent_node 邏輯）
6. rclpy publish `/event/speech_intent_recognized`（String msg, JSON payload）
7. WebSocket 回傳 JSON：`{"asr": "...", "intent": "...", "confidence": 0.9, "published": true}`

**ROS2 publish schema — 對齊 interaction_contract.md v2.4 §4.2**：

真相來源：`docs/architecture/contracts/interaction_contract.md` §4.2

```json
{
  "stamp":             1775440000.123,
  "event_type":        "intent_recognized",
  "intent":            "chat",
  "text":              "你好嗎",
  "confidence":        0.9,
  "provider":          "sensevoice_cloud",
  "source":            "web_bridge",
  "session_id":        "uuid-v4",
  "matched_keywords":  [],
  "latency_ms":        850.0,
  "degraded":          false,
  "timestamp":         "2026-04-06T10:30:00"
}
```

- `source: "web_bridge"` 標記來源，與 stt_intent_node 的 `"mic"` 區別
- `event_type` / `stamp` / `provider` 對齊 contract，Executive 和 observer 不需改動
- `session_id` / `matched_keywords` / `latency_ms` / `degraded` / `timestamp` 對齊 stt_intent_node 實際 payload，確保 log 分析工具相容

### 4.3 Intent 分類器（`intent_classifier.py`）

從 `speech_processor/speech_processor/stt_intent_node.py` 抽出：
- `intent_rules` dict（關鍵字 → intent 映射）
- `classify_intent(text: str) -> tuple[str, float]`
- 純 Python，無 ROS2 依賴，可單獨測試

## 5. 檔案結構

```
pawai-studio/
├── gateway/
│   ├── studio_gateway.py      # FastAPI + rclpy server
│   ├── intent_classifier.py   # Intent rules（從 stt_intent_node 抽出）
│   ├── static/
│   │   └── speech.html        # Web 收音頁面
│   └── requirements.txt       # fastapi, uvicorn, websockets, requests
├── backend/                   # 既有 mock_server（不動）
├── frontend/                  # 既有 Next.js（不動）
└── README.md                  # 更新啟動說明
```

Gateway 和既有 backend/frontend 共存，不互相干擾。

## 6. Demo 操作流程

1. Jetson 啟動 demo stack（`start_full_demo_tmux.sh`，加 gateway window）
2. Mac/手機瀏覽器打開 `http://JETSON_IP:8080/speech`
3. 按住按鈕說「你好」→ 放開 → 頁面顯示 ASR + intent → Go2 回話
4. 視覺互動（face/gesture/pose）照常走 Jetson 本機
5. 兩條路共存：視覺事件 + 網頁語音 → Executive 統一仲裁

## 7. 混合模式驗收標準

1. 瀏覽器說話 → Go2 TTS 回話（E2E < 5s）
2. face greeting + web speech 不互相打架
3. EMERGENCY（fallen）期間 web speech 被忽略
4. stop gesture 仍優先於 web speech
5. 3 輪固定 demo flow 可重現

## 8. 前提條件

- SenseVoice cloud ASR tunnel (port 8001) 可從 Jetson localhost 連到
- 瀏覽器和 Jetson 在同一區網（能連 JETSON_IP:8080）
- Jetson 有 `fastapi`, `uvicorn`, `websockets`, `requests`（uv pip install）
- Jetson 有 `ffmpeg`（audio resample 用）或 `scipy`/`librosa`

### 8.1 Port 分配（Jetson 部署時）

| Port | 用途 | 說明 |
|:----:|------|------|
| 8001 | SenseVoice ASR server（SSH tunnel） | 保留給 ASR，不可被其他 server 佔用 |
| 8080 | Studio Gateway（本 spec） | Web 收音 + ROS2 bridge |
| 8000 | LLM server（SSH tunnel） | vLLM Qwen2.5-7B |

**注意**：`pawai-studio/backend/mock_server.py` 預設也跑 port 8001。在 Jetson 上 **mock_server 不啟動**（它是開發機用的 mock，Jetson 上 8001 由真實 SenseVoice tunnel 佔用）。如果需要在開發機同時跑 mock_server 和 ASR tunnel，mock_server 應改用 port 8002。

## 9. 不做的事

- 不做前端 VAD / 即時串流
- 不做使用者認證
- 不改 Executive / stt_intent_node / 任何既有 ROS2 node
- 不做完整 Studio 後端架構重整
- 不接 face/gesture/pose/object WebSocket 推送（P1）
- 不做 chat history / session 管理

## 10. 降級方案

如果 SenseVoice cloud tunnel 不穩：
- Gateway 改呼叫 Jetson 本地 SenseVoice（sherpa-onnx int8）
- 精度從 92% 降到 ~85%，但不依賴外網

## 11. 後續擴展路徑（不在本 spec scope）

- P1：Gateway 訂閱 ROS2 event topics → WebSocket 推給 Studio 前端
- P1：Studio 前端 face/gesture/pose panel 接真實數據
- P2：Gateway 替代 mock_server，成為 Studio 唯一後端
- P2：chat orchestration + session 管理
