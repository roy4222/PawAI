# PawAI Studio（studio_gateway + mock_server + Next.js 16）

## 這個模組是什麼

Studio 是 PawAI 系統的觀測、操作與對話前端，同時也是 demo 現場的語音替代入口（筆電收音代替機身 mic）。
chat-first 設計（5/4 落地）：主畫面 ChatGPT 風純對話，6 個感知模組收進 navbar icon-only button 開 center modal。
雙路徑架構：Jetson 模式（FastAPI + rclpy）/ Mock 模式（純 Python，支援 opt-in Gemini 真對話）。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/studio/studio.md` | Studio 主總覽 + 雙路徑架構 + 5/11 freeze 快照 |
| `docs/pawai-brain/architecture/0511/studio/studio-runtime-flow.md` | WebSocket 端點 + ROS2 ↔ Gateway 完整訊息流 + 跨線程橋接模型 |
| `docs/pawai-brain/architecture/0511/studio/studio-frontend-components.md` | Next.js panel 拆分 + Zustand stores + 事件分派規則 |
| `docs/pawai-brain/architecture/0511/studio/studio-gateway-mock-bridge.md` | Gateway vs Mock 雙路徑對比 + PawAIEvent schema + 各模組 data schema |
| `docs/pawai-brain/architecture/0511/studio/studio-debug-runbook.md` | 症狀 → 檔案定位（DISCONNECTED / ChatPanel 沒泡泡 / Trace 空白等）|

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `pawai-studio/gateway/studio_gateway.py` | Jetson 模式：FastAPI + GatewayNode(rclpy) + TOPIC_MAP 10 個 |
| `pawai-studio/backend/mock_server.py` | Mock 模式：periodic push + opt-in Gemini + Demo A 場景 |
| `pawai-studio/frontend/hooks/use-websocket.ts` | WS 連線狀態機（3s 重連，L13）|
| `pawai-studio/frontend/stores/state-store.ts` | 各模組 state + TTS messages（Zustand，ring buffer）|
| `pawai-studio/frontend/contracts/types.ts` | PawAIEvent + 所有模組 TS 型別（真相）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/brain/conversation_trace` | Brain → Gateway → Studio | 12-node trace（Trace Drawer 視覺化）|
| `/tts` | Executive → Gateway → Studio | TTS text → `tts_speaking` event → ChatPanel AI 泡泡 |
| `/brain/text_input` | Studio → Brain | 使用者文字輸入（`POST /api/text_input`）|
| `/brain/skill_request` | Studio → Executive | 技能按鈕（`POST /api/skill_request`）|
| `/brain/reset_context` | Studio → Brain | 清 memory（`POST /api/reset`）|

## 已知陷阱

- **CORS hotfix 5/7**：Gateway 已設 `allow_origins=["*"]`（`studio_gateway.py` L444-449）；Mock 只允許 localhost。Jetson 跨 Tailscale IP 發 POST 要靠 Gateway wildcard
- **ChatPanel AI 泡泡不出現**：`/tts` topic 沒被 `_on_tts_msg()` 接到 → broadcast 沒 `tts_speaking` event → `state-store.lastTtsText` 不更新
- **TTS rate-limit**：非 chat_reply / skill_say / say_canned 的自發性 TTS 限 5s 一次（`state-store.ts` L1-5）
- **skill_registry import 失敗**：Mock `SKILL_REGISTRY = {}` silent fallback（L29-31），表現為技能按鈕全 unknown
- **Video streaming Jetson only**：`cv2 + cv_bridge` 需要，Mac/Mock 模式無影像

## 開發入口

```bash
# Mock 模式（本機開發）
bash pawai-studio/start-live.sh --mock
# → http://localhost:3000/studio
# → http://localhost:8080

# Mock + 真 Gemini（需 .env OPENROUTER_KEY）
set -a && . ./.env && set +a
MOCK_OPENROUTER=1 bash pawai-studio/start-live.sh --mock

# Jetson 模式
GATEWAY_HOST=100.83.109.89 bash pawai-studio/start-live.sh --live

# TypeScript 檢查
cd pawai-studio/frontend && npx tsc --noEmit
```
