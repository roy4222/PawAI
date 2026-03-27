# LLM Brain Reference

> 最後更新：2026-03-17

## 模組定位

LLM Brain 是系統的中樞決策引擎。不直接控制硬體，根據感知事件提出意圖判斷和技能建議。
LLM 只提建議，Interaction Executive 做最終決策。

## 權威文件

| 文件 | 用途 |
|------|------|
| `docs/Pawai-studio/brain-adapter.md` | 四級降級、Brain 介面設計 |
| `docs/Pawai-studio/system-architecture.md` | Gateway、快慢系統 |
| `docs/architecture/contracts/interaction_contract.md` | `/state/executive/brain` schema |
| `docs/superpowers/specs/2026-03-16-llm-integration-mini-spec.md` | LLM 整合完整規格 |

## 技術棧

| 組件 | 技術 | 部署 |
|------|------|------|
| 雲端 LLM | vLLM + Qwen3.5-9B/27B | RTX 8000 (GPU 0) |
| 本地 Fallback | Qwen3.5-0.8B INT4 | Jetson（動態載入） |
| 規則引擎 | Python dict mapping | Jetson |
| 橋接節點 | `llm_bridge_node.py` | Jetson ROS2 |

## 核心程式

`speech_processor/speech_processor/llm_bridge_node.py`

## LLM 鏈路流程

```
語音觸發：
  使用者說「你好」
  → /event/speech_intent_recognized (intent=greet, text=你好)
  → llm_bridge_node 收到
    → 讀 /state/perception/face（作為 context）
    → POST Cloud LLM (Qwen3.5-9B)
    → 回傳 JSON: {intent, reply_text, selected_skill, reasoning, confidence}
  → 發 /tts（回覆文字）
  → 延遲 0.5s
  → 發 /webrtc_req（動作指令）

人臉觸發：
  攝影機看到 Roy → /event/face_identity (identity_stable)
  → llm_bridge_node 收到（60s 冷卻去重）
  → 同上 LLM 呼叫流程
```

## ROS2 介面

**訂閱**：
- `/event/speech_intent_recognized` — 語音觸發
- `/event/face_identity` — 人臉觸發（只聽 `identity_stable`，排除 `unknown`）
- `/state/perception/face` — 背景 context

**發布**：
- `/tts` — 回覆文字
- `/webrtc_req` — Go2 動作
- `/state/executive/brain` — 決策狀態

## 四級降級

| Level | Brain | 觸發條件 | 能力 |
|:-----:|-------|---------|------|
| 0 | CloudBrain (vLLM) | 網路正常 | 完整對話 |
| 1 | LocalBrain (0.8B) | 雲端超時 | 基本對話 |
| 2 | RuleBrain | 本地 LLM 記憶體不足 | 模板回覆 |
| 3 | MinimalBrain | 系統壓力極大 | 僅 stop/greet |

## Skill 映射（P0）

| LLM `selected_skill` | Go2 `api_id` | 動作 |
|----------------------|------------|------|
| `hello` | 1016 | 揮手 |
| `stop_move` | 1003 | 停止（**安全優先，不等 TTS**） |
| `null` | — | 無動作 |

## 啟動

```bash
# 啟動 llm_bridge_node
ros2 run speech_processor llm_bridge_node --ros-args \
  -p llm_endpoint:="http://140.136.155.5:8000/v1/chat/completions"

# 模擬語音事件測試
ros2 topic pub --once /event/speech_intent_recognized std_msgs/msg/String \
  "{data: '{\"event\":\"speech_intent_recognized\",\"session_id\":\"test-001\",\"intent\":\"greet\",\"text\":\"你好\",\"confidence\":0.95}'}"

# 監聽輸出
ros2 topic echo /tts
ros2 topic echo /webrtc_req
```

## 已知陷阱

- Temperature 必須 0.2（高溫度會破壞 JSON 格式輸出）
- **Qwen3.5 thinking mode 必須關閉**：`chat_template_kwargs: {"enable_thinking": false}`，否則回應含推理過程
- **timeout 15s**（雙重 SSH tunnel 延遲大），**max_tokens 300**
- 語音 session_id 去重 + 人臉 (track_id, name) 60s 冷卻，防重複觸發
- `stop_move` priority=1，立即發 `/webrtc_req`，不等 TTS
- LLM 呼叫用 `threading.Thread` + `_llm_lock`，同時只有一個 LLM 請求
- **vLLM 偶爾掛**：每天開工前 `curl /v1/models` 確認
- audiohub 命令 msg type 必須 `"req"`（不是 `"msg"`）

## 當前狀態

- llm_bridge_node 已完成，E2E 已驗證（10/10 對話）
- vLLM on RTX 8000 已部署（Qwen3.5-9B），但不穩定
- RuleBrain fallback 待驗證（斷 tunnel 後是否能回應）
- FastAPI Gateway（ros2_bridge_node）待實作
