# 專案進度快照

> 最後更新：2026-05-12 night（**離線 fallback chain 實機驗證** + 5/12 brain-freeze-v2 / N3-N8 demo-host）

## 2026-05-11 — N3 ~ N8 全日 brain demo-host 收尾

### 本日 15 commits + 6 tags

```
85ac682 docs(runbook): add N8 8-case regression list before Mac migration
53cbdae fix(brain): N8 three demo polish bugs from 5/11 live log
0c030a1 docs(runbook): 30-case acceptance checklist before Mac migration
717a24a feat(vision): N7 fist vote frames + fallen sensitivity
8d81dd9 feat: N7 fist vote + fallen threshold loosen + lane self-heal
eb422e9 fix(brain): N6.1 — gesture_gate trace observability + test correctness
d4c4236 feat(brain): N6 demo polish — conversation gate + P0 spec + audio tag filter
2b7a981 docs(brain): document N5 scene perception design (after-the-fact)
0f13d98 fix(brain): N5.1 narrow scene_query 你覺得我 / 你猜我 patterns
631b98b feat(brain): N5 scene understanding — pose + gesture + scene_query
f9988bd fix(brain): N4.1 positive-frame scaffold + _sanitize_str_list helper
afd3fcd feat(brain): N4 self_intro_request scaffold for demo opening
80ec823 fix(brain): N3.1 demo_segment hardening + TS status union sync
561d6ab feat(brain): N3 demo-host harness — object context + demo_session + verifier
e6d667a docs(runbook): freeze backlog + 5min demo script
```

Tags: `brain-hotfix-N3` → `N4` → `N5` (committed via 631b98b earlier session)
→ `N5.1` → `N6` → `N7` → `N8` — N3 / N4 / N6 經過 review fix 後 tag 移到最新

### 7-題較急問題對照狀態

| # | 較急問題 | 狀態 | 本日落地 |
|---|---|---|---|
| 1 | LLM 模糊不主動 | **解** | N4 `self_intro_request` mode + 5 段 scaffold；N4.1 正向 framing |
| 2 | 手勢辨識 (6 靜態 + wave 動態) | **解** | N3 既有 mapping；N6 fist/index motion 對齊規格；N7 vote_frames 3→5 + stable_s 0.5→0.3 修 fist 不認 |
| 3 | 姿勢辨識 (站/坐/跌倒+人名) | **解** | N3 fallen + face cache name；N6 sit_along SAY「會不會太累」；N7 vertical_ratio 0.4→0.45 + ankle 0.7→0.6 |
| 4 | 物體辨識唸出 | **解** | N3 recent_objects → LLM JIT context；N3 person filter；N3 color_confidence gate |
| 5 | 導航避障 | 凍結 | 5/12 nav burndown 3/3 已通過；本日 brain-only 收尾 |
| 6 | Model switcher UI | 凍結 | 用 `PAWAI_LLM_MODEL=` env override；trace model 欄位不順手加（已 llm_decision.detail）|
| 7 | TTS chain (gemini→edge→piper) | **已實裝** | `tts_node.py:1064-1091` 三層 fallback chain 早在；本日 audio tag normalize 解 whisper 整段語氣鎖 bug |

### N3 ~ N8 元件落地

**N3 demo-host harness**（`561d6ab`）
- `WorldStateSnapshot._recent_objects` deque(maxlen=8, 30s window, class-dedup)
- 訂 `/event/object_detected` → JIT inject `[最近看到]` 進 LLM prompt
- `demo_session` placeholder → real (provider chain + lock，訂 `/brain/demo_segment`)
- `response_repair` 加 rule-only verifier（too_short / no_specific_skill / no_followup_invitation）
- Schema：trace stage enum +`verifier`、status enum +`warn`

**N4 self_intro_request scaffold**（`afd3fcd` + `f9988bd` N4.1）
- mode_classifier 加 `self_intro_request`（demo+介紹 / 詳細介紹 / 完整介紹 / 跟教授 demo），priority > identity
- `[intro_scaffold]` 5 段：身份 / 專題 / 能力 / grounded 觀察 / 拋下一步
- N4.1 正向 framing（移除「不要說成長者陪伴」「不是聊天機器人」這類負面 prime）
- wave_hello SAY 「嗨！」→「嗨～我是 PawAI！很高興認識你～」

**N5 scene understanding**（`631b98b` + `0f13d98` N5.1）
- `WorldStateSnapshot._last_pose`（永不過期 + age_s）+ `_recent_gestures`（8s window，dedup by gesture+hand）
- mode_classifier 加 `scene_query`（看到什麼 / 我在幹嘛 / 猜猜我）
- prompt 注入 `[目前姿勢]` / `[最近姿勢]` / `[歷史姿勢]` 三段 age 措辭 + `[剛剛手勢]` + `[scene_hint]`
- N5.1 收窄 `你覺得我` / `你猜我` regex 不吃 capability_question
- spec：`docs/superpowers/specs/2026-05-11-n5-scene-perception-design.md`

**N6 demo polish**（`d4c4236` + `eb422e9` N6.1）
- conversation-active gate：wave/fist/index 在最近 30s 有 speech/text input 時不 fire（palm safety 例外）
- N6.1 加 `tts_playing` 第二層 gate + trace `gesture_gate` `blocked` 觀測
- enter_mute_mode 加 stand_down motion / enter_listen_mode 加 balance_stand motion
- sit_along SAY「我也趴下來陪你」→「會不會太累，我陪你坐一下」
- `[whispers]` / `[sighs]` audio tag normalize → `[curious]`（validator + skill SAY + persona EXAMPLES + OUTPUT.md 全清）
- Schema：trace stage enum +`gesture_gate`

**N7 vision sensitivity + lane self-heal**（`717a24a` + `8d81dd9`）
- vision_perception.yaml：`gesture_vote_frames` 3→5、`gesture_stable_s` 0.5→0.3（fist 觸發更穩）
- pose_classifier.py：fallen `vertical_ratio` 0.4→0.45（接住蜷曲跌倒）、`ankle_on_floor` 0.7→0.6（遠景接住）
- brain-studio-lane start.sh：probe Jetson tmux + local next dev → 自動 cleanup → preflight；`--no-clean` 可跳過

**N8 demo polish 二修**（`53cbdae`）
- gate 加 `tts_playing` 第二層（防 stale build + race）
- mode_classifier 拿掉 `跟.*打.*招呼`/`問好`（不再 hijack 走 5 段自介；改 chat → wave_hello path）
- PendingConfirm 加 `_must_release_ok`（user 手已在 OK 位置時 request_confirm，必須先放開才能再次比 OK 觸發；防 stretch/wiggle 立即觸發）

### 測試狀態（本日落地時）

- pawai_brain：219 → 280 → 245 → 252（變動因為 N5/N5.1 引入新 test）
- interaction_executive：195 → 230 → 236（gesture gate / pending_confirm release-first）
- vision_perception：36 (gesture/pose classifier，PYTHONPATH 跑)
- **Local 全套 495 tests green @ N8 commit**

### Jetson 部署狀態

- N3 ~ N7 全程 ~/sync once + colcon build pawai_brain interaction_executive vision_perception 完成
- **N8 commit 後 Jetson SSH 短暫 timeout**（5/11 night 17:00+），sync + build 待 Jetson 回穩
- 開機後跑：`bash .claude/skills/brain-studio-lane/scripts/start.sh demo`（self-heal 自動 cleanup）

### 後續紀律

- **brain 設計接近 freeze** — user 5/11 night 明示「pawai brain 就差不多了，全力衝導航避障」
- 剩餘 brain 改動需先過 N9 hotfix justification（見 `docs/runbook/demo-frozen-backlog.md`）
- 8-case regression（N8 後 mandatory）+ 30-case 完整 checklist 在 `docs/runbook/demo-30-case-checklist.md`
- 通過後搬 Mac，跑 5-case post-Mac smoke 確認跨平台無 regression

---

## 2026-05-12 — brain-freeze-v2 + Jetson live + 5 較急問題收尾

### 本日 8 brain commits + 3 tags

```
e5fdc0a feat(brain): persona demo-host follow-up + skill demo mode (brain-hotfix-N2)
c285b60 fix(tts): strip OPENROUTER_KEY for openrouter_gemini provider (brain-hotfix-N1)
778739f feat(scripts): propagate PAWAI_LLM_MODEL env through brain-studio-lane
cc24619 docs(runbook): add demo fallback script for 5/18 demo
60e4e84 docs(llm-eval): expand A/B log with round-2 small-model results
2fd4aec feat(brain): switch live LLM primary to gpt-5.4-mini, gemini fallback
4f509d5 tools(llm_eval): add demo-focused 4-model A/B harness
320d4d0 feat(brain+vision): cover demo gesture and fall-alert painpoints
```

Tags: `brain-freeze-v2` (49ecac7) → `brain-hotfix-N1` (c285b60 TTS strip) → `brain-hotfix-N2` (e5fdc0a persona host)

### 較急問題清單（測試功能清單 v2）對應狀態

| # | 較急問題 | 狀態 |
|---|---|---|
| 1 | LLM 模糊不主動 | **主線換 `openai/gpt-5.4-mini`**（8-model A/B 後決策）+ persona demo-host 補強（強制具體 skill 名 + 結尾邀請）+ mode_classifier 補「可以做什麼」「會什麼動作」變體 |
| 2 | 手勢 6 靜態 + 3 動態 | 6 靜態全到 mapping（palm→pause / fist→mute / index→listen / ok→confirm / thumbs_up→wiggle / peace→stretch / wave→hello）；circle / come_here 標 demo 後 |
| 3 | 姿勢 7 種 + 跌倒人名 | 7 enum 齊；fallen_alert SAY 模板 → "偵測到 {name} 跌倒，請注意安全"；name 從 brain 30s face cache 注入；bridge audible disabled (避免雙播) |
| 4 | 物體 yolo26n vs 8n + 顏色 | 主線 yolo26n + HSV 12 色 (5/6 凍結 schema v2.5)；A/B 標 demo 後 |
| 5 | 導航避障空間問題 | 5/12 nav burndown demo 最低目標 3/3 通過（goto 0.3m、reactive_stop danger 1.1m 1 次煞停、SLAM/Nav2 stack 36 node 全跑）。詳見 `docs/navigation/research/2026-05-11-nav-avoidance-deep-research.md §10` |

### LLM A/B benchmark（8-model）

| Model | P50 | P95 | cost (12-call) | verdict |
|---|---|---|---|---|
| **gpt-5.4-mini** ⭐ | **1.16s** | 2.74 | $0.018 | live primary |
| gpt-nano | 1.11 | 3.32 | $0.004 | 漏 audio tag → 砍 |
| haiku-4.5 | 1.51 | 2.73 | $0.090 | markdown fence → 砍 |
| opus-4.7 | 1.59 | 3.44 | $1.445 | offline only |
| gemini-3-flash | 1.89 | 3.10 | $0.040 | fallback backup |
| sonnet-4.6 | 2.93 | 7.59 | $0.268 | 砍 |
| deepseek-v4 | 3.64 | **34.22** | $0.009 | 砍 (慢尾) |
| gpt-5.5 | 3.88 | 6.17 | $0.361 | offline 文案 |

### Jetson 5/12 night live test 結果

- Brain stack full demo 13 windows / 20 nodes 全活
- 60s 自介 ×5：4/5 captured (Round 1 lost = ros2 CLI discovery race，Studio gateway path 無此問題)，**P50 1.85s** Jetson tunnel
- Reply 自然原創、context-aware（「外面又悶又濕」/「悶悶的」/「悶濕」/「晚上有點悶熱」每輪不重複）
- Fallback env override 真的 propagate（`PAWAI_LLM_MODEL=google/gemini-3-flash-preview` 切回後 Gemini reply 3.80s + 自然「偷看外面的雲，厚厚的好像棉花糖」）
- TTS gemini Despina 真的播從 USB CD002-AUDIO ✅
- Bug fix: `.env` CRLF → `OPENROUTER_KEY` 含 `\r` → TTS Authorization header 500 → `.strip()` 修復

### 5/12 night Roy 反饋 → hotfix-N2

實機聊天後 Roy 抓出 LLM 還是「模糊、不講具體 skill 名、講完不問下一步」。N2 修：
- STYLE.md 移除「不要每句結尾拋問題」一刀切
- CAPABILITIES.md 改「明確問則講具體 skill 名稱」+ 補完整 7 領域真實能力清單
- MISSION.md Demo 主軸加「我是 host 不是 chatbot」+ 強制具體 skill 名稱
- EXAMPLES.md +6 demo-host follow-up few-shot
- mode_classifier 補「可以做什麼/會什麼動作/有什麼動作/具體有哪些」regex
- brain-studio-lane skill 加 `demo` mode = `full + --studio` 一鍵全開（5 perception + brain + Studio frontend）

待驗收：5/13 sync + rebuild + 重 smoke 看 N2 改動是否生效（5/12 night SSH 連線異常停下，persona 已 commit 但未上 Jetson）

### 5/12 night — 離線 fallback chain 實機驗證（Go2 已搬到學校前）

bad OPENROUTER_KEY 模擬雲端掛掉，五句連發走過完整 chain：

| 層 | 結果 |
|----|------|
| LLM primary `gpt-5.4-mini` | bad key → fail |
| LLM fallback `gemini-3-flash-preview` | 同 key → fail |
| Brain `rule:chat_fallback` rescue | ✅ `chat_candidate_timeout` 後接手 `say_canned`「我聽不太懂」|
| TTS primary `openrouter_gemini` | bad key → fail |
| TTS fallback `edge_tts` | ✅ 接手合成 + 播放 |
| TTS final `piper` | 未觸發（edge_tts 已 catch；要拔網才能驗）|

紀錄：[`docs/runbook/2026-05-12-offline-fallback-verification.md`](../../../docs/runbook/2026-05-12-offline-fallback-verification.md)

副產品（4 個 bug/坑）：
1. `pawai demo start` 不 forward Mac shell 的 `TTS_PROVIDER` / `ASR_PROVIDER_ORDER`（brain-studio-lane skill default 蓋掉）
2. `/brain/text_input` 期 JSON `{"text":"..."}` 不接純文字
3. `ros2 topic pub --once` 跟 RELIABLE subscriber discovery race，要用 `--rate 1 --times 3`
4. 裸 SSH `faster_whisper` 因 `LD_LIBRARY_PATH` 不繼承會 import 失敗（demo tmux 內 OK）

ASR 三段 fallback inherently 需現場麥克風 — 排明天到場 5 分鐘做。

---

## 2026-05-09 — Roy 8 issue 互動品質改善（13 PR merged）

5/8 evening Roy 列 8 issue：TTS 音色 / LLM 死板 / LLM 不主動鏈式 / 物體人臉重複干擾 / Studio 顯示每句 / ASR 簡→繁 / refresh 重置 / idle 待機。5/9 全天 spec brainstorm → 5 個 feature branch + 4 P0 audit 全 merge `origin/main`（PR #51-#62 + #64）。

### 主線狀態（不是「100% 完成」）

| # | Issue | 狀態 | 殘餘 |
|---|---|---|---|
| 1 | TTS 音色 | 部分 | ElevenLabs spike 待 Roy 親耳評；現走 Gemini quality lane + emotional tag 強制 |
| 2 | LLM 死板 | 主線落地 | 待 Jetson smoke：「介紹一下」是否真擺脫 70 字功能列表 |
| 3 | LLM 主動鏈式 | 主線落地 | 待 Jetson smoke：「扭一下」LLM 是否穩定出 `skill: wiggle` |
| 4 | 重複觸發干擾 | 主線落地 | 待 Jetson smoke：路過比 OK 不被打招呼 |
| 5 | Studio 顯示每句 | 完成 | — |
| 6 | ASR 簡→繁 | 主線落地 | 待 Jetson runtime 確認 `opencc` import |
| 7 | refresh reset | 主線落地 | 待 Jetson smoke：按鈕清 brain 後第一句不帶舊 context |
| 8 | Idle 待機 | MVP **default OFF** | demo 啟用待 Roy 決定 |

### 新元件（5/9 落地）

- topic：`/brain/reset_context` (std_msgs/Empty)
- `/tts` envelope schema 擴 `source` 欄位（`chat_reply` / `say_canned` / `skill_say`），純文字 backward compat
- 新 module：`pawai_brain/pawai_brain/nodes/mode_classifier.py`（5-mode regex）
- 新 module：`interaction_executive/interaction_executive/attention_machine.py`（4-state pure Python）
- 新 directory：`pawai_brain/personas/v1/{IDENTITY,STYLE,CAPABILITIES,EXAMPLES,OUTPUT}.md`（OpenClaw-lite L7）
- 新 helper（兩份）：`text_normalization.py`（speech_processor + gateway 各一份避免 cross-package import）
- 新 params：idle_*（default off）/ enable_s2twp / tts_dual_route_enabled / tts_fast_lane_threshold / llm_temperature default 0.8

### Carry-over（5/10）
- Jetson sync + colcon build (含 `rm -rf build/install/pawai_brain` 強制 data_files 重 install) + restart demo
- 5 case Roy 親測（介紹/audio tag/扭一下/路過 OK/新對話按鈕）
- ElevenLabs Spike-Mini 由 Roy 親耳評分（`tools/tts_spike/`）
- 本機 main reconcile（22 ahead local 個人 commit / 14 behind origin/main）

### Spec / plan 文件
- spec：`docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md`
- roadmap：`docs/pawai-brain/plans/2026-05-09-master-execution-roadmap.md`
- 5 個 branch plans 在 `docs/pawai-brain/plans/2026-05-09-*` 和 `2026-05-11-*` 和 `2026-05-12-*`

---

## 2026-05-05 night（unstaged，未 commit）

聚焦在「Voice → Brain → Studio E2E + LLM 個性化」整套接通。本日上午 5 commits 為感知/Studio panel；下午+晚上工作集中在 LLM 個性化路線：

| 改動範圍 | 檔案 | 摘要 |
|---|---|---|
| Brain MVS 路徑啟用 | `scripts/start_full_demo_tmux.sh` | llm_bridge 顯式 `output_mode:=brain`、加 `enable_openrouter`、persona file、`max_reply_chars=0`、`llm_max_tokens=2000`、`llm_timeout=20.0` |
| Brain keyword 移除 | `interaction_executive/interaction_executive/brain_node.py` | self_introduce / show_status keyword bypass 拿掉（self_introduce 含 motion，近距離被 SafetyLayer 擋成 sleep；LLM persona 自然處理） |
| Brain timing | `interaction_executive/config/executive.yaml` | `chat_wait_ms`：1500 → 20000ms（雲端 LLM 長 reply 需要時間） |
| LLM 字數限制解除 | `speech_processor/speech_processor/llm_bridge_node.py` | `max_reply_chars` default 40 → 0；`_post_process_reply` cap≤0 跳過截斷；`_call_llm` 改用 `self._system_prompt`（之前還在用 inline 12 字 SYSTEM_PROMPT） |
| 對話記憶 | 同上 | `_convo_history: deque(maxlen=10)`，OpenRouter + vLLM/Ollama 兩條路徑都送 history；只在 chat/greet/status 寫入 |
| 環境 context | 同上 | `_time_of_day_zh()` 6 段 + `_get_weather_text()`（wttr.in/Taipei，10min cache，2s timeout） |
| Persona v3 | `tools/llm_eval/persona.txt` | 4777 bytes，70/20/10 小狗/童心/守護，明令禁客服腔、不要主動列功能、長度情境決定 |
| Eval alias | `tools/llm_eval/run_eval.py` | `gemini` alias `google/gemini-3-flash-preview` → `google/gemini-2.5-flash` |
| Studio trace | `pawai-studio/frontend/components/chat/chat-panel.tsx` | 加單行 skill trace bar（`brain:skill_result` selected_skill / status / detail） |
| Brain test | `interaction_executive/test/test_brain_rules.py` | 加 2 條 show_status keyword test（後因移除 keyword bypass，test 仍保留以驗 SKILL_REGISTRY 完整性） |

### Truncation Bug Diagnosis（5h+ debug session）
反覆出現「reply 在中文逗號或無標點處截斷至 30-40 字」。途中試了：切 stable Gemini → 切 DeepSeek → 拉 timeout 4s→30s → 拉 chat_wait_ms 1500→20000 → 改 temperature 0.2→0.7 → 都沒解。最後 curl 直打 OpenRouter API 回完整 138 token 故事 → 對比 md5 發現 **Jetson `install/` stale**，內含舊 `cap=40` 強制截斷邏輯。`speech_processor` 是 ament_python，sync source 不會更新 `install/`，必須 colcon build。已用 `--symlink-install` rebuild。**Stale install 是真兇**，model / timeout / temperature 全是 false lead。

### 待驗證
- 重 build 後第一次完整 smoke test 還沒跑（睡前故事 / 介紹功能 / 累陪聊三句）
- DeepSeek V4 Flash vs Gemini 2.5 Flash 真實長回覆 A/B（之前 A/B 全被 stale install 干擾，無效）

### 衍生 backlog
- **LangGraph 重構評估**（使用者建議）：chat + tool calling 路徑目前散落在 `llm_bridge_node` (1100 行) + `brain_node._on_chat_candidate` + Studio gateway，多源 path 增加隱藏 bug 風險。建議搬到 `pawai-studio/backend/chat_agent/`，**5/16 demo 後再做**

## 2026-05-05 進度（5 commits，上午）

## 2026-05-05 進度（5 commits）

| Commit | 主軸 | 影響 |
|---|---|---|
| `45d29a8` | docs: 6 README aligned to MOC + 5/12 sprint design | 上午 docs 重構（face/gesture/pose/object/speech/studio）|
| `add6b51` | feat(studio): B6 PR port — Pose/Gesture/Object/Speech panels + center modal | Sheet right-drawer → center modal；4 panel 抄入 PR #38/40/41/42；ChatPanel mic 與 SpeechPanel 分離；用 `LiveFeedCard` 接 Jetson `/ws/video/{face,vision,object}` |
| `4f638ae` | feat(perception): land MOC P0 sensing demo bridge | gesture enum remap (palm/fist/index/thumb/peace) + OK 幾何規則 + 0.5s `gesture_stable_s` param + object HSV 4 色 + event_action_bridge demo bridge (pose→/tts) |
| `ca32655` | feat(perception): pose 7 + akimbo/knee_kneel | pose_classifier `_is_akimbo` / `_is_knee_kneel`；POSE_TTS_MAP 補 akimbo/knee_kneel template |
| `95982d6` | feat(perception): Wave 動態手勢 + gesture demo bridge | dynamic_gesture_detector.WaveDetector；`/event/gesture_detected` raw 訂閱 + GESTURE_TTS_MAP{"wave"} |

**TTS 路徑（5/5）**：tts_node `local_playback:=true` + `local_output_device:=plughw:0,0`（USB CD002-AUDIO，Go2 driver 沒跑時的可聽路徑）。OpenRouter Gemini 仍 locked main，但 demo bridge smoke 用 edge-tts。

**待補（明天）**：
- pose 分類效果待 tune（5/5 實機回報不穩；threshold / vote / scale-invariant ratio）— `~/.claude/projects/.../memory/project_pose_classifier_tuning_0505.md`
- Stretch #43 OK 二次確認 + Studio toast UI
- Stretch #44 yolov8n A/B
- Stretch contract.md v2.6 收尾文件升版（gesture/pose enum + object color/class_id 欄位）

## 當前階段

語音 3/17 freeze。人臉 + vision Phase 2 真推理通過（3/18）。Benchmark 框架 Batch 0+1 完成（3/19，core + face YuNet baseline，28 tests pass）。下一步：Jetson 真實 benchmark + Batch 2（pose/gesture adapter）。

## 里程碑

| 里程碑 | 日期 | 狀態 |
|--------|------|------|
| 功能閉環凍結 | 3/12 | [DONE] |
| 介面契約 v2.0 凍結 | 3/13 | [DONE] |
| 語音 30 輪驗收框架 | 3/14-15 | [DONE] 框架建好，待 Jetson 上跑第一輪 |
| 攻守交換 | 3/16 | [DONE] Roy 交出架構核心 |
| 手勢/姿勢技術選型 | 3/16 | [DONE] DWPose + TensorRT（待本機驗證） |
| 語音 E2E 基線 | 3/17 | [DONE] 10/10 對話、9/10 播放、median 5.4s |
| 人臉 Jetson smoke | 3/18 | [DONE] D435 + state/event/debug_image 全通 |
| vision_perception Phase 1 | 3/18 | [DONE] mock mode Jetson 驗證通過 |
| vision_perception Phase 2 | 3/18 | [DONE] RTMPose 真推理 Jetson 驗證通過（balanced mode, ~3.8 Hz debug_image, GPU 91-99%） |
| Benchmark 框架 Batch 0+1 | 3/19 | [DONE] core framework + face YuNet adapter，28 tests pass |
| P0 穩定化 | 4/6 | [PENDING] |
| Phase B Day 1 — Skill Registry + LLM eval + Studio chat-first | 5/4 morning | [DONE] commits 9f45f65 / 8347f26 / fda1b3c / 0f8a576..a55f83a |
| Phase B Day 2 — Jetson smoke + B1 Plan D TTS 換血（Despina + chain） | 5/4 evening | [DONE] commits 29d46dd / 3c3a933 / 1df3afe / 4f6da89 / 54c68d0 / 5671b33 |
| **最終展示** | **4/13** | **[PENDING] 硬底線** |

## 各模組狀態

| 模組 | 狀態 | 說明 |
|------|------|------|
| 語音閉環 | [USABLE / 5/5 night 升級中] | Brain MVS 路徑（output_mode=brain → /brain/chat_candidate → /brain/proposal → /tts）已接通；persona v3 / 對話記憶 / 環境 context / 字數解除全 unstaged；stale install 已排除；待 rebuild 後真實 smoke 驗收 |
| 人臉閉環 | [USABLE] | Jetson smoke passed（3/18）。D435 + state/event/debug_image 全通。int32 序列化 bug 已修。待驗：有人時識別準確率 |
| 姿勢辨識 | [USABLE] | **全 MediaPipe**（3/21 晚）：MediaPipe Pose (CPU) 18.5 FPS、GPU 0%、Foxglove 實測通過。RTMPose 降為備援 |
| 手勢辨識 | [USABLE] | **全 MediaPipe**（3/21 晚）：MediaPipe Hands (CPU) 16.8 FPS、GPU 0%。RTMPose 手部 keypoints 不可靠已驗證 |
| FastAPI Gateway | [PENDING] | 骨架待建 |
| Mock Event Server | [AVAILABLE] | vision_perception mock_event_publisher 可直接用，循環發 gesture+pose 假事件 |
| PawAI Studio | [PENDING] | 鄔負責，mock_event_publisher 已可接 |
| LLM Brain | [STABLE] | Qwen2.5-7B-Instruct on RTX 8000，max_tokens 120，RuleBrain fallback 5/5 |
| Benchmark 框架 | [STABLE] | L1 全模型完成（face/pose/gesture/stt），L2 共存矩陣完成。3/25 決策數據齊全 |
| 文件網站 | [PENDING] | 黃/陳負責，Astro + Starlight |
| nav_capability | [USABLE] | 5/3:capability_publisher launch default 0.40→**0.45**(對齊 nav_action_server YELLOW upper 0.50)、xy_goal_tolerance 0.15→**0.10**。Demo A 1.5m goal 流程跑通。Jetson `~/.local/.../entry_points.txt` 缺 3 個 entry 已手補 |
| D435 safety gate | [USABLE] | 5/2:`depth_safety_node` (go2_robot_sdk),fail-closed,手擋 1.03s 翻轉。5/3 demo 中觀察到 box ≤0.4m 即 depth_clear→false 觸發 auto-pause |
| Executive safety wiring | [USABLE] | 5/2:WorldState 訂三個 capability、SafetyLayer 三段 gate。92/92 unit tests 過,未接 launch |
| Capability launch wiring | [USABLE] | 5/3:8 windows + 7 nav nodes 全活、`nav_round_reset.sh` READY 流程驗證。已知坑：colcon build setuptools 不相容 → editable install 直接 source rsync 生效 |
| **Stage 1 遇障停車** | **[PASS]** | 5/3 R3 R1：box 1.5m / goal 1.8m → Go2 走 0.85m / drift 0.19m / 停 box 前 0.54m。reactive_stop + D435 + auto-pause 三鏈同步。**K-STATIC-AVOID-CONTROLLED PASS** |
| **Stage 2 自動繞行** | **[L1+L2 PASS / L3 FAIL]** | 5/3 evening 完成 D435+RPLIDAR fusion 進 local_costmap (Phase 1+2 PASS)；Phase 3 L3 真自動繞開 FAIL，根因為 nav_action_server max_speed 不 enforce + AMCL plateau bug 串連，Go2 永遠進不到 DWB 測試起點。新檔：`nav2_params_detour.yaml` / `start_nav_capability_demo_tmux_detour.sh` / `robot.launch.py` 加 nav_params_file arg。Demo B 話術「融合進 costmap 安全停車」不宣稱「自動繞開」 |
| nav_round_reset.sh | [STABLE] | 5/3 新工具：emergency release / nav resume / costmap clear / 3 capability snapshot / cmd_vel quiet → READY/NOT-READY summary |

## 近期焦點(2026-05-02 更新)

**Phase A 導航底座日完成**(commits `a3bdd2e` / `9fe6046` / `e413406`):
1. ✅ `/state/nav/paused` latched topic + nav_action_server pause/resume + cancel/re-send (BUG #2)
2. ✅ `/capability/depth_clear` fail-closed(D435 ROI gate)
3. ✅ `/capability/nav_ready` v0.5(AMCL freshness + covariance)
4. ✅ WorldState 接三個 capability + SafetyLayer 三段 gate(NAV / MOTION / nav_paused)
5. ✅ 9 份外部 stack research(Odin / OM1 / NavDP / visualnav / amigo_ros2 / DimOS + 2 papers)+ synthesis 排好 P0/P2/P3 優先序
6. 🟡 Foxglove D435 點雲 TF (static_transform_publisher) 暫時頂著,正式 D435 mount 校正排到 5/13 後

**5/2 深夜試跑教訓**(動態避障 v0):
- ⚠️ **Damp (api_id=1001) 不能當移動中 emergency stop** — 馬達軟鬆弛 → Go2 摔倒。改用 `emergency_stop.py engage` (mux pri 255 + lock) + StopMove (1003,**必填 topic=rt/api/sport/request**)
- ⚠️ **detour fail 條件 ≤ 1s** — 不是等 5-6s。reactive 進 danger zone 即代表 DWB 沒在 0.6m 之外繞掉,本輪已失敗
- ⚠️ **velocity_smoother 不解此 bug** — mux pri 200 切換 bypass smoother;v1 才考慮 reactive 漸進 ramp
- ⚠️ **WebRtcReq 必填 topic** — `api_id=1003` 在不同 topic 下意義不同(sport=StopMove vs obstacles_avoid=Move)

**day 2 P0**(明天必做):
1. 場景校準 + R3:標 box 位置 / Go2 起點 / 左右淨空,跑第三輪驗證 R1 行為是否可重現
2. 第二階段 K-LOW-OBSTACLE-DETECT/GATE:D435 對低矮物 ≤1s 翻 depth_clear=false
3. 接 `interaction_executive.launch.py` — 把 capability_publisher / depth_safety / executive 串起
4. Brain rules `speech_nav_demo` + `face_wave_approach`
5. `/capability/nav_ready` 升級 v1 — lifecycle service + TF map→base_link + costmap healthy(取代 pose age)
6. Studio Trace Drawer LED 顯示 3 個 capability bool

## 近期焦點(3/21 更新)

**已完成（3/18-3/21）**：
1. ✅ Benchmark 框架 Batch 0+1（core + 6 adapters: YuNet/SCRFD/RTMPose/MediaPipe/Whisper）
2. ✅ L1 全模型基線（face 3 / pose 3 / gesture 2 / stt 2 = 10 個模型）
3. ✅ L2 共存矩陣（face+pose / scrfd+pose / whisper+pose）
4. ✅ MediaPipe ARM64 可安裝驗證（推翻先前結論）
5. ✅ face Research Brief 決策回填（YuNet=主線, SCRFD=備援）
6. ✅ Jetson 環境問題修復（onnxruntime GPU/CPU 衝突、numpy 降級、OpenCV 4.13 相容）

**下一步**：
1. 本地 LLM benchmark（Qwen2.5-0.5B 等小模型 fallback）
2. TTS benchmark（Piper vs MeloTTS）
3. L3 全模型共存（face + pose + whisper 同時 30s）
4. 外接喇叭/麥克風到貨後重測語音
5. PawAI Studio 串接（鄔負責）

## 3/16 後分工

| 人 | 3/16 → 4/6 | 4/6 → 4/13 |
|----|-------------|-------------|
| **Roy** | Brain Adapter + DWPose Jetson 部署 + 整合 | 端到端 + Demo pipeline |
| **楊** | 手勢/姿勢 x86 demo + Studio gesture/pose 互動 | 整合測試 + Demo B |
| **鄔** | 全部 Studio 面板 | Demo Showcase + 微調 |
| **黃** | 文件站內容 | 展示站首頁 |
| **陳** | 架構圖 + 環境建置文件 | 團隊介紹 + 校對 |

## 已解決的重大問題

- Go2 音訊播放三層 bug（asyncio 跨執行緒 + WAV sample rate + intent 名稱不對齊）
- CTranslate2 CUDA 加速（Whisper Small 延遲從 10s+ 降到 ~0.6s）
- HyperX stereo-only 麥克風問題（手動 downmix）
- Energy VAD 整合到 stt_intent_node
- LLM Bridge 支援本地 Ollama models（2026-03-16）
- **Megaphone「失效」誤判修正**（2026-03-17）— API 沒死，是 payload 格式/msg type 不對
- **Echo gate timing 修正**（2026-03-17）— tts_playing 提前到 TTS request 入口 + 1s cooldown
- **Qwen3.5 thinking mode 關閉**（2026-03-17）— enable_thinking=false，乾淨 JSON 輸出
- **face_identity_node int32 序列化修正**（2026-03-18）— np.int32 bbox 無法 json.dumps，轉 Python int
- **vision_perception Phase 1 骨架落地**（2026-03-18）— gesture+pose mock mode，23 unit tests，Jetson 驗證通過

## 關鍵技術決策（3/16 新增）

### 手勢/姿勢推理拓樸（3/18 統一）

- **主路徑**：rtmlib + RTMPose wholebody 單模型（一次推理同時產出 body + hand keypoints）
- **升級選項**：DWPose wholebody（精度略優，但 Jetson 上零成功記錄）
- **備援**：hand-only + body-only 雙模型（wholebody 不達標時啟用）
- MediaPipe 僅作 x86 概念驗證，不上 Jetson
- 詳見 `docs/pawai-brain/perception/gesture/README.md`、`docs/pawai-brain/perception/pose/README.md`、`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-18-vision-perception-skeleton-design.md`

### vision_perception 架構（3/18 新增）

- face_identity_node（現有）+ vision_perception_node（新建）共享 D435 camera topic
- vision_perception_node 支援 `use_camera=false`（mock mode，不需相機）
- gesture+pose 共用推理，分兩個 classifier
- 契約不變：`/event/gesture_detected`、`/event/pose_detected` 對齊 v2.0
