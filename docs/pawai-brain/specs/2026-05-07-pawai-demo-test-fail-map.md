# PawAI Demo Fail-Map (5/7 Night)

> 只記 FAIL / OBS 條目。PASS 直接打勾在 checklist v2.1。
> 格式 per spec §12。
> Spec：`2026-05-07-pawai-demo-test-plan.md`
> Checklist：`2026-05-07-pawai-demo-test-checklist-v2.md`

---

## Phase A — 7 Functions

### Sync / Build baseline (5/7 17:07)
- WSL → Jetson sync 完成（5/7 17:07，warnings 為 face_dashboard_nextjs/node_modules legacy 殘留，無關緊要）
- Jetson `scripts/start_full_demo_tmux.sh` 已是 5/7 10:16 版本，含 `conversation_graph_node`（grep -c = 4）
- 5 packages colcon build 成功 13.3s（pawai_brain / interaction_executive / vision_perception / speech_processor / face_perception）

## [#A1.1] startup / import smoke / langgraph 缺套件
結果：FAIL → A:BLOCKER → 已修
分類：A
觸發：`python3 -c "import pawai_brain.conversation_graph_node"` on Jetson
預期：import 成功
實際：`ModuleNotFoundError: No module named 'langgraph'`
Trace/topic：N/A（pre-runtime）
是否可重現：YES（直到安裝為止）
下一步：已執行 `pip install langgraph` on Jetson，裝好 langgraph 1.1.10 + langchain-core 1.3.3 + langgraph-checkpoint 4.0.3 等。重測 4 個 import 全 PASS。
**Carry-over**：deps 應該寫進 `pawai_brain/package.xml` 或 README，下次 fresh Jetson 不會再遇到。記入 P2 backlog。

## [#A1.2] full demo / langgraph 分支 .env 未載入
結果：FAIL → A:BLOCKER → 已修
分類：A
觸發：`bash scripts/start_full_demo_tmux.sh` → `conversation_graph_node ready (engine=langgraph, openrouter=off)`
預期：openrouter=on（OpenRouter Gemini 主路徑可用）
實際：openrouter=off（key 沒進 tmux 子 shell 環境）→ 會直接掉 RuleBrain
Trace/topic：log line 14（"openrouter=off"），launch params 缺 enable_openrouter:=true
是否可重現：YES（每次 cold start 都會發生，直到 .env source 進腳本）
下一步：
- script fix：`scripts/start_full_demo_tmux.sh:1-30` 加 `set -a; source $WORKDIR/.env; set +a` 同時注入 ROS_SETUP（每個 tmux pane 都會 re-source）
- live fix：手動 kill brain → tmux send-keys re-source .env → relaunch → 確認 `openrouter=on`
- 驗證：smoke pub 「你好」收到 reply `[excited] 嗨！你回來啦...` 從 Gemini 出來，proposed=None ✓
**Demo 影響**：未修則所有對話都掉 RuleBrain 罐頭句，persona / 對話記憶 / 環境 context 全失效。

## [#A2.1.1] 連續對話 latency baseline (smoke-PATIENT-01)
結果：OBS（B 類觀察）
分類：B
觸發：`ros2 topic pub --once /event/speech_intent_recognized` (text=「你好")
預期：< 10s 收到 chat_candidate
實際：首句約 25s 內到（精確時間沒抓 — pub 後 25s 才發現 chat_candidate publish）
Trace/topic：`/brain/chat_candidate` 確認 reply 從 Gemini 出（persona [excited] tag）
是否可重現：YES（首句冷啟）
下一步：明天連續多輪測時觀察是否 prefix cache 生效讓 P50 < 5s（會議基線 5/5 night 是 RTX 8000 vLLM ~1.5s，OpenRouter Gemini 預期較高但仍應 < 5s 中位數）

## [#A2.1.2] CapabilityContext + skill_gate trace_only 行為驗證 (caps-02)
結果：PASS
分類：A
觸發：`你可以做什麼`
預期：LLM 提案 self_introduce，但 skill_gate 標 trace_only（不執行 motion），reply 列功能
實際：✓ Trace 完整 6 stage 可見：
  - input ok（你可以做什麼）
  - llm_decision ok（google/gemini-3-flash-preview）
  - json_validate ok（valid）
  - repair ok（pass_through）
  - skill_gate **blocked**（detail=`self_introduce:defer`）
  - output ok（reply: `[playful] 我會的可多啦！我可以聽你說話、陪你聊天，還能認出你是誰...`）
Trace/topic：`/brain/conversation_trace`（每 stage 一條 JSON）+ `/brain/chat_candidate` 含 reply
是否可重現：YES
下一步：對應 spec §5 主腳本 S1 + S2，已通過。`accepted_trace_only` Studio 應該可見（待現場 DevPanel 視覺確認）。

## [#A2.1.3] 連續多輪 single-flight 排隊行為觀察
結果：OBS（pre-baseline 不穩）
分類：B
觸發：短時間內 5+ pub（smoke-002/003/NEW/verify-01）+ caps-01
預期：每輪都能處理或 dropped 有 warning log
實際：只有 smoke-PATIENT-01（waited 25s）和 caps-02（waited 60s）成功 publish chat_candidate；中間 4-5 個 session_id 沒有對應 published 訊息也沒看到 dropped warning
Trace/topic：tmux capture brain log 缺少 dropped 警告；但 graph 處理時間每輪 ~10-25s，多 pub 可能 race
是否可重現：YES（rapid pub）
下一步：demo 場景下使用者語音間隔 >5s，自然不會撞到此行為。記入 P2 backlog 觀察 single-flight 是否需要 queue 而非 drop。

## [#A2.2] safety_gate stop / 緊急 keyword 短路 (3 phrases)
結果：PASS
分類：A
觸發：「停」/「stop」/「緊急」 三條獨立 pub
預期：safety_gate 攔截，bypass LLM，回 `好的，我停下來` 罐頭
實際：✓ 三條 trace 都是 input → **safety_gate status=hit detail=stop_move** → output (detail=safety_path)
  - reply: `好的，我停下來。` (RuleBrain canned)
Trace/topic：`/brain/conversation_trace` 完整三段；無 LLM call（safety_gate 短路）
是否可重現：YES
**Hard gate 確認**：safety_gate 確實是 demo 第一道閘門，3/3 不漏。

## [#A3.4] invalid / disabled skill 不執行 motion
結果：PASS（跳舞）/ OBS（後空翻 — rapid-pub 排隊掉，非邏輯失敗）
分類：A
觸發：「跳舞」（disabled in registry）/「後空翻」（unknown）
預期：LLM 提案被 skill_gate blocked / rejected_not_allowed，**不發 /skill_request、不發 /webrtc_req**
實際：
- 跳舞：Gemini persona 直接婉拒（reply: `[playful] 跳舞我現在還不太會耶，我的關節今天有點緊。不過如果你對我比個...`）
  → 沒提 skill，所以 skill_gate 沒 trace
  → `/brain/skill_request` topic timeout 5s 確認沒任何訊息
- 後空翻：未被 brain 處理（rapid pub 排隊掉，跟 A2.1.3 同一個 OBS）
Trace/topic：dance-01 trace = memory → llm_decision → json_validate → repair → output（缺 skill_gate stage 因為沒提案）
是否可重現：YES（跳舞，每次 demo）
**Hard gate 確認**：整個今晚 session `/webrtc_req` 0 message — invalid skill 真的動 = **0** ✓

## [#Hard-Gate-Summary] 截至目前的 demo 安全閘
- ✅ safety_gate keyword 短路 100%（3/3 phrases）
- ✅ invalid skill 不執行 motion 100%（0 webrtc_req emitted）
- ✅ trace_only mode 正確 defer（caps-02: skill_gate blocked self_introduce:defer）
- ✅ `/brain/skill_request` 和 `/webrtc_req` 至今 0 訊息
- 後續要驗：執行型 skill（wave_hello / sit_along / wiggle confirm）能正確發 skill_request → motion 真跑

## [#A5.4-noise] object_remark 對靜態物體狂講
結果：FAIL → A:BLOCKER → 已修
分類：A
觸發：Roy 開 full demo 後，YOLO 持續偵測同一張咖啡色椅子，brain_node 每 5s 發一次 `看到咖啡色的椅子了` TTS，干擾語音主鏈測試
預期：同一物體只講 1 次，60s 後可再觸發
實際：每 5s 重講（SkillContract.cooldown_s=5 只擋 skill 不擋同物重發）
Trace/topic：`/event/object_detected` 持續、`/skill_request` 每 5s 一筆 say `text="看到咖啡色的椅子了"`
是否可重現：YES（每次靜態物體入鏡都會）
下一步：已修 — `brain_node.py` 加 `OBJECT_REMARK_DEDUP_S=60.0` + `_object_remark_seen[(class, color)] = ts` per-key gate（commit 685c97d）。restart `interaction_executive launch` 生效。
**Demo 影響**：未修則任何靜態物體展示都會干擾對話 + Studio 大螢幕 spam。


(items appended as testing progresses)

---

## Phase B — Demo Main Flow

(items appended as testing progresses)

---

## Phase C — Triage Notes

(P0 fixes applied + verification results)
