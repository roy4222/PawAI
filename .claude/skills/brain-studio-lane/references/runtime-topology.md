# Runtime Topology — Brain × Studio Lane

各 mode 啟哪些 node、誰 publish 誰 sub、共享 driver 怎麼回事。

## Mode：minimal

```
┌─────────────────────────────────────────┐
│ tmux session: pawai_brain (3 windows)   │
├─────────────────────────────────────────┤
│ window: brain          → interaction_executive_node              │
│ window: conv_graph     → conversation_graph_node (LangGraph)     │
│ window: event_bridge_off → event_action_bridge (disabled)         │
└─────────────────────────────────────────┘

Topic graph：
  /brain/text_input  → conversation_graph_node
                     → /brain/chat_candidate  → interaction_executive_node
                                              → (no SAY plan in minimal — exec 不發 /tts)
```

底層腳本：`scripts/start_pawai_brain_tmux.sh`
資源：~0.4 GB RAM / 10% CPU

## Mode：e2e

```
minimal + 1 window:
└─ window: tts        → tts_node (edge_tts + plughw:CD002AUDIO,0)

新增 topic flow：
  Studio chat / 手動 pub /brain/text_input
    → conv_graph → /brain/chat_candidate
    → interaction_executive_node → SAY plan → /tts (String)
    → tts_node → edge_tts cloud → audio bytes → ALSA plughw → 喇叭
```

底層腳本：`start_pawai_brain_tmux.sh` + 額外起 `tts_node` window（skill 自己拼）
資源：~0.6 GB RAM / 20% CPU

## Mode：full

```
┌──────────────────────────────────────────────────────────┐
│ tmux session: demo (13 windows)                          │
├──────────────────────────────────────────────────────────┤
│ go2 / camera / face / vision / executive / asr / tts /   │
│ llm (legacy llm_bridge_node) / camtf / depth_safety /    │
│ fox / object / gateway                                   │
└──────────────────────────────────────────────────────────┘
```

⚠️ **legacy brain**：用 `speech_processor.llm_bridge_node` 而非 `pawai_brain.conversation_graph_node`。
Persona 走 `tools/llm_eval/persona.txt`（單檔），不是新 6 檔架構。新 persona 改動在這個 mode 看不到。

底層腳本：`scripts/start_full_demo_tmux.sh`
資源：~1.6 GB RAM / 75% CPU / 50% GPU

## Studio overlay

```
Jetson:                    本機 (WSL/Mac):
  studio_gateway      ←──  Next.js dev server (port 3000/3001)
  (port 8080)              env: NEXT_PUBLIC_GATEWAY_URL=http://100.83.109.89:8080
  ↑
  訂閱 11 ROS topics:
    /state/perception/face
    /event/gesture_detected
    /event/pose_detected
    /event/speech_intent_recognized
    /event/object_detected
    /state/pawai_brain
    /brain/proposal
    /brain/skill_result
    /brain/conversation_trace
    /brain/conversation_trace_shadow
    /tts
```

Frontend → POST /api/chat → Gateway 發 /brain/text_input → brain → /brain/chat_candidate → Gateway WebSocket → Frontend 顯示。
TTS 走 ROS /tts → tts_node → 實體喇叭（不經 Frontend）。

## go2_driver_node 共享問題

| Lane / mode | 是否需要 go2_driver |
|---|---|
| brain minimal | ❌ 不需 |
| brain e2e | 🟡 不需（local TTS 不靠 driver；除非走 datachannel megaphone）|
| brain full | ✅ 需要（megaphone TTS + 動作 demo）|
| nav 任何 mode | ✅ 需要 |

⚠️ **Driver reuse 機制尚未實作** — 兩 lane 的 `start.sh` 直接呼叫既有
`scripts/start_*_tmux.sh`，那些底層腳本都會自啟 driver instance（不會偵測
既有的 reuse）。為避免雙 driver / 雙 publisher / 雙 odom 衝突，cleanup
**一律清 driver**，不論 `--handoff` 旗標值。

`--handoff` 旗標目前只影響 cleanup 完的下一步提示文字，不影響清的範圍。

## 切換流程速查

```
情境：剛測完 brain，要切 nav 場測
─────────────────────────────────
brain-studio-lane cleanup --handoff nav
  → 殺 conv_graph + tts + studio + frontend + go2_driver
  → 提示：「下一步建議 bash .claude/skills/nav-avoidance-lane/scripts/start.sh <mode>」
nav-avoidance-lane start fallback
  → 自啟 tf + sllidar + go2_driver + reactive_stop（10s WebRTC ICE handshake）
```

```
情境：剛測完 nav，要切回 brain
─────────────────────────────────
nav-avoidance-lane cleanup --handoff brain
  → 殺 sllidar + reactive_stop + nav2 + go2_driver + D435
  → 提示：「下一步建議 bash .claude/skills/brain-studio-lane/scripts/start.sh <mode>」
brain-studio-lane start e2e --studio
  → 自啟 conv_graph + tts（minimal/e2e 不啟 driver；full 才啟）
```

未來若實作「start 偵測既有 driver 跳過自啟」，再讓 `--handoff` 真正影響
是否保留 driver — 目前先以 unconditional 清換取安全。
