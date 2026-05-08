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

## [#A2.3-feat] Studio chat → Gemini TTS / 其他 → edge_tts (per-message routing)
結果：PASS
分類：feature (Roy 5/7 night 加 demo 需求)
觸發：5 步 smoke
- Smoke 1: `ros2 topic pub --once /tts std_msgs/String 'data: 測試純文字一'`
- Smoke 2: `curl -X POST http://192.168.0.222:8080/api/text_input -d '{"text":"小狗你今天好嗎"}'`
- Smoke 3: 麥克風講「你好」（待 Roy 確認）
- Smoke 4: 物體偵測 → object_remark
- Smoke 5: 拔 OPENROUTER_KEY fallback（待跑）
預期：Studio chat 走 Gemini，其他走 edge_tts
實際：
- ✅ Smoke 1：「測試純文字一」 → `🎤 [edge_tts]`
- ✅ Smoke 2：「小狗你今天好嗎」 → `🎤 [openrouter_gemini]` (Despina voice, 2 chunks parallel, 6.5s first-chunk, 12s audio)
- ⏸ Smoke 3：待 Roy 麥克風驗
- ✅ Smoke 4：「看到咖啡色的椅子了」(object_remark) → `🎤 [edge_tts]`
- ⏸ Smoke 5：待跑
- 啟動 log：`tts_node: studio chain built: ['openrouter_gemini', 'edge_tts', 'piper']`
- pawai_brain: `Published /brain/chat_candidate session=txt-... input_origin=studio_text`
Trace/topic：`/tts` JSON envelope when input_origin=studio_text；純文字 when None
是否可重現：YES
下一步：等 Roy 跑麥克風語音 + Gemini key 失效 fallback。Demo 影響：5/18 demo 用 Studio chat 演 Gemini TTS (Despina) 漂亮聲音、其他通道 edge_tts 維持 demo 反應速度。
修法：commit 10829ca（per-message routing 5 file plumbing + studio chain pre-build）
build_plan bug 中途發現：line 627 只 copy text 不 copy input_origin → fix line 632-634

## [#Reboot-1] Jetson 重開機（XL4015 供電不穩）
結果：FAIL → 已恢復
分類：A (硬體 demo 風險，memory project_jetson_power_issue.md 已標)
觸發：build smoke 過程中 SSH 突然 timeout，Tailscale ping 不通
預期：Jetson 連續運行 30 min+
實際：uptime 0 min（reboot），Roy 確認重開電源
Trace/topic：N/A
是否可重現：YES (XL4015 在 Go2 運行中歷史多次掉電)
下一步：持續觀察。建議 demo 準備期間插穩定電源，Go2 換大電源不依賴 XL4015。

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

---

## Phase D — 5/8 morning 在家驗收（A-H 八階段）+ 三項 fix

### Sync / Build / 啟動 (5/8 09:31)
- WSL → Jetson sync 完成（warnings 為 face_dashboard_nextjs/node_modules legacy 殘留，無關緊要）
- `bash scripts/start_full_demo_tmux.sh` 起 12 個 window，19 個 ROS2 node
- A 階段 baseline 5/5 PASS：單一 `/conversation_graph_node`、`engine=langgraph openrouter=on`、Brain/Perception topics、Studio Gateway :8080

### 5/8 morning 測試結果概覽

| 階段 | 結果 | 備註 |
|------|------|------|
| A Baseline | 🟢 5/5 | 但發現 `depth_safety_node` 沒被啟動腳本拉起（[#A1.3]）|
| B 語音回歸 | 🟢 5/5 | 含記住名字、長句 TTS、persona tag |
| C trace_only | 🟢 C1 PASS / C2 SKIP | C2 Studio button 不存在也不需要 |
| D motion skills | 🟢 5/5 | wave_hello + sit_along + 接續記憶 |
| E 動作中 stop | 🟢 2/2 | preempted hard gate 守住 |
| F confirm mode | 🔴 F1+F2 PASS / F3+F4 FAIL | OK 手勢 confirm wiring 失效（[#F-confirm]）|
| G invalid skill | 🟢 3/3 | 後空翻/爬樓梯/跳舞 0 motion |
| H 多模態干擾 | 🟢 H1+H3 PASS / H2 SKIP→5/13 | fallen 在家不便驗 |

---

## [#A1.3] full demo / depth_safety_node 沒在啟動腳本
結果：FAIL → A:BLOCKER → **已修（5/8 morning, 程式碼提交，待 Jetson 整合驗證）**
分類：A
觸發：`bash scripts/start_full_demo_tmux.sh` cold start 後對狗講「跟我打招呼」
預期：wave_hello plan accepted → motion api_id=1016 執行
實際：D 階段 wave_hello + sit_along 全部 `blocked_by_safety: depth_not_clear_for_motion`
Trace/topic：
- `/capability/depth_clear` Publisher count = 0（3 個 subscriber 全在等 latched message）
- `world_state.depth_clear` default `False` → `safety_layer.py:94` block 所有 MOTION step
- `/brain/skill_result`：`{"plan_id":"p-d9e57bf5","status":"blocked_by_safety","detail":"depth_not_clear_for_motion"}`
- LLM 收到 blocked_by_safety 後 reflect 為「[sighs] 失敗了，前面空間不夠」（**不是幻覺**）
是否可重現：YES（每次 fresh start）
下一步（已執行）：
- 5/8 morning 熱修：手動 `tmux new-window -t demo -n depth_safety 'ros2 run go2_robot_sdk depth_safety_node'` → publish=true → motion 解禁
- 永久修：`scripts/start_full_demo_tmux.sh` 在 camtf 後插入 depth_safety window（[10/13]），啟動序列更新為 13 個 window
- 待驗證（下次 session）：fresh `bash scripts/start_full_demo_tmux.sh` 後 `/capability/depth_clear` Publisher count = 1

## [#F-confirm] OK 手勢 confirm wiring 失效 + 背景 auto-rule 蓋掉
結果：FAIL → A:BLOCKER → **已修（5/8 morning, 程式碼提交 + 5 個 unit test 全綠，待 Jetson 整合驗證）**
分類：A
觸發：對狗講「搖一下」進入 needs_confirm wiggle，比 OK 手勢確認
預期：wiggle 真執行（webrtc_req 對應 motion api_id）
實際：
- F1+F2 needs_confirm wiggle 進入 PENDING 正確 ✓
- F3 比 OK gesture confidence=1.0 偵測到，但 wiggle **0 個 plan accepted**
- 反觸發：wave_hello x14 + greet_known_person x12 + object_remark x16 + stranger_alert x6
Trace/topic：
- `/event/gesture_detected`：ok / wave 在 5/8 log 中混雜出現（MediaPipe Gesture Recognizer 在 OK 和 wave 之間 flicker）
- `/brain/conversation_trace`：session 進入 `skill_gate needs_confirm wiggle` 後就被 background plan 蓋掉
是否可重現：YES（每次 PENDING 期間）
Root cause（5/8 morning 程式碼追查）：
- **2a**：`pending_confirm.py:161-163` 對任何非 OK 非 NEUTRAL gesture 立即 CANCEL → MediaPipe flicker 第一個 wave event 進來就退出 PENDING → 接著 `_on_gesture` 走 `_GESTURE_DIRECT["wave"]` 直接 fire wave_hello
- **2b**：`brain_node.py` 的 `_on_face`（greet_known_person）和 `_on_pose`（sit_along / careful_remind）沒有 PENDING guard，PENDING 期間持續 emit plan 蓋掉 confirm 流（`_on_gesture:471` 已有 guard，face/pose 漏掉）
下一步（已執行）：
- **2a fix**：`pending_confirm.py:155-162` 改寫 — 非 OK gesture 改為 reset OK stability streak 但保持 PENDING，timeout (5s) 為唯一 cancel 路徑
- **2b fix**：`brain_node.py:621-622` _on_face、`:671` sit_along、`:683` careful_remind 三處加 `or self._pending_confirm.state == ConfirmState.PENDING` guard
- **Test 同步**：
  - `test_pending_confirm.py` 改寫 2 個 test：`test_different_gesture_stays_pending`、`test_wrong_gesture_after_partial_ok_resets_streak_but_stays_pending`（皆驗證 flicker 後可以 resume OK 完成 confirm）
  - `test_brain_rules.py` 新增 3 個 test：face/sitting/bending during PENDING 不發 plan
  - WSL 端 `pytest interaction_executive/test/` 60 個 test 全綠（18 pending_confirm + 42 brain_rules）
- 待驗證（下次 session）：Jetson 上重講「搖一下」+ 比 OK → wiggle 執行 + PENDING 5s 期間無 greet_known_person/sit_along/careful_remind plan emit

## [#TTS-gemini] Mic 路徑 TTS 想統一走 Gemini Flash TTS preview
結果：OBS → P1 升級為 fix（用戶 5/8 morning 明確要求） → **已修（程式碼提交，待 Jetson 整合驗證）**
分類：B（升 P1）
觸發：5/8 morning B4 睡前故事 Roy 親耳聽完後反饋：「目前是用 edge tts 雖然延遲蠻低的 但我還是想用 google/gemini-3.1-flash-tts-preview 當 main 講話的」
預期：mic 與 Studio chat 統一音色（Gemini Despina）
實際：
- Studio chat → Gemini Despina TTS（5/7 commit 10829ca per-message routing）✓
- Mic 路徑 → edge_tts（routing 條件 `input_origin == "studio_text"` 排除 mic）
是否可重現：YES（by design）
下一步（已執行）：
- `tts_node.py:1040-1043` routing 條件改為「OPENROUTER_KEY 有設就一律用 Gemini chain」（`_studio_fallback_chain` 不再依 input_origin 區分）
- `input_origin` 欄位保留供未來 per-source policy（chunk size / voice tweak）
- 待驗證（下次 session）：Jetson 上對麥克風講「你好」→ 應聽到 Gemini Despina 音色（不是 edge_tts 平直音）；OPENROUTER_KEY 失敗時自動 fallback edge_tts → Piper

---

## 5/8 morning 程式碼變更 summary

| 檔案 | 變更 | 對應 fail-map |
|------|------|--------------|
| `scripts/start_full_demo_tmux.sh` | 加 `depth_safety` window，[10/13]，總 window 12 → 13 | [#A1.3] |
| `interaction_executive/interaction_executive/pending_confirm.py` | line 155-162 非 OK gesture stays PENDING | [#F-confirm] 2a |
| `interaction_executive/interaction_executive/brain_node.py` | line 621/672/684 加 PENDING guard | [#F-confirm] 2b |
| `interaction_executive/test/test_pending_confirm.py` | 改寫 2 個 test 對應新行為 | [#F-confirm] |
| `interaction_executive/test/test_brain_rules.py` | 新增 3 個 face/pose during PENDING test | [#F-confirm] |
| `speech_processor/speech_processor/tts_node.py` | line 1040 routing 條件改 OPENROUTER_KEY 即用 Gemini chain | [#TTS-gemini] |

整體：3 個 commit（每個 fix 一個），unit test 60/60 PASS（WSL 端 pytest）。
