# AI 大腦（pawai_brain — LangGraph 對話決策）

## 這個模組是什麼

Layer 3 的對話決策核心。它把多模態感知（face/pose/gesture/object）+ 對話歷史 + skill registry 整合進 12-node LangGraph StateGraph，
產出一個 ChatCandidate（reply_text + intent + proposed_skill + args），由下游 `interaction_executive` 做仲裁與執行。
Brain 是「建議者」，Executive 是「決策者」（單一控制權原則）。

## 0511 權威文件

| 文件 | 用途 |
|------|------|
| `docs/pawai-brain/architecture/0511/brain/brain.md` | 主總覽 + 12-node graph 拓撲 + State schema + 5/12 brain-freeze-v2 |
| `docs/pawai-brain/architecture/0511/brain/brain-runtime-flow.md` | ROS2 → wrapper → ThreadPoolExecutor → graph.invoke() 完整 flow |
| `docs/pawai-brain/architecture/0511/brain/brain-graph-node-map.md` | 12 個 node 的職責、輸入/輸出、trace entry、常見故障 |
| `docs/pawai-brain/architecture/0511/brain/brain-persona-capability-memory.md` | persona 6 檔、CAPABILITIES lazy inject、skill registry、memory |
| `docs/pawai-brain/architecture/0511/brain/brain-debug-runbook.md` | 現場 debug 指令、trace 判讀、症狀 → 檔案位置 |

## 核心程式檔案

| 檔案 | 用途 |
|------|------|
| `pawai_brain/graph.py` | `build_graph()` — 12-node StateGraph 真相 |
| `pawai_brain/conversation_graph_node.py` | ROS2 wrapper + 注入 + ThreadPoolExecutor |
| `pawai_brain/llm_client.py` | OpenRouter 雙模型 fallback（gpt-5.4-mini → gemini-3-flash）|
| `pawai_brain/capability/world_snapshot.py` | WorldStateSnapshot + N3-A object cache |
| `pawai_brain/capability/registry.py` | CapabilityRegistry（skill + demo_guide 合併）|
| `pawai_brain/personas/v1/` | 6 個 persona MD 檔（IDENTITY/MISSION/STYLE/OUTPUT/EXAMPLES/CAPABILITIES）|
| `pawai_brain/rule_fallback.py` | RuleBrain fallback（關鍵字 → canned reply）|

## 關鍵 ROS2 topic / event

| Topic | 方向 | 內容 |
|-------|------|------|
| `/event/speech_intent_recognized` | → Brain | 語音意圖（主要輸入）|
| `/brain/text_input` | → Brain | Studio 文字輸入（JSON envelope，source="studio_text"）|
| `/brain/chat_candidate` | Brain → Executive | 決策輸出（reply_text + intent + proposed_skill）|
| `/brain/conversation_trace` | Brain → Studio | 12-node trace entries（每條 per-publish）|
| `/state/perception/face` | → Brain | current_speaker（stale 3s）|
| `/event/pose_detected` | → Brain | current_pose（stale 10s）|
| `/event/gesture_detected` | → Brain | current_gesture（stale 5s）|
| `/event/object_detected` | → Brain | recent_objects（30s 快取）|
| `/brain/reset_context` | → Brain | Clear ConversationMemory + 5s suppress |

## 已知陷阱

- **API key 必須 `.strip()`**：CRLF 尾綴會造成 OpenRouter 500（5/12 hotfix）
- **graph.py 是 12-node 真相**：`conversation_graph_node.py` 檔頭寫 11-node 是舊的，以 `build_graph()` 為準
- **Lazy capability injection**：chat / identity / safety 模式不送 capability，避免 LLM 列功能表（1D 設計）
- **single-flight lock**：wrapper 用 non-blocking lock 防止 concurrent invoke，新輸入在執行中直接丟棄
- **`openrouter_request_timeout_s = 4.0`**（從 2.0s 拉高是因為 urllib3 overhead，5/4）
- **Brain 只提建議**：skill 要不要執行是 interaction_executive 的決策，不要在 Brain 直接發 Go2 命令

## 開發入口

```bash
# 全功能 demo（含 Brain）
bash scripts/start_full_demo_tmux.sh

# Brain 單獨（含 Executive）
bash .claude/skills/brain-studio-lane/scripts/start.sh demo

# 觀測 trace
ros2 topic echo /brain/conversation_trace
ros2 topic echo /brain/chat_candidate

# 5 輪 E2E smoke test
bash scripts/smoke_test_e2e.sh

# Build
colcon build --packages-select pawai_brain && source install/setup.zsh
```
