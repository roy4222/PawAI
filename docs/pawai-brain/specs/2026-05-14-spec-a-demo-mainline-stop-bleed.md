# Spec A — Demo 主線止血

> **Status**: design freeze（待 user review）
> **Date**: 2026-05-14
> **Owner**: Roy（kirk7）
> **Branch base**: `main` @ commit `caef6b5`（pawai_cli 今日改動後最新 HEAD）
> **Hardware assumption**: Go2 / Jetson 暫不在手，本 spec 只完成「非硬體依賴的結構修補」與「可重跑驗收入口」

---

## 0. 摘要

下週 demo 前必須清掉的結構性風險共 6 項，全部不依賴 Jetson / Go2 即可實作與單元驗證。改動橫跨 `pawai_brain` / `interaction_executive` / `pawai_cli` / `scripts`，以 3 個 PR 群（1 → 2A → 2B → 3）依序合入；每群可獨立 review、獨立 revert，且**不回退**今日 `b05205d`~`caef6b5` 之 lock / orphan / env / CRLF 修補。

本 spec 不宣稱完成真機穩定性，只完成：
- 靜態 import / env / persona 字句正確
- demo runtime 單主線（TTS / chat_candidate 單出口）
- gesture 誤觸止血
- pose grounding 從 event-only 升為 Brain-side state
- 可重跑的 mechanical preflight + semantic dry-run 入口

---

## 1. Scope & Non-goals

### 1.1 Demo 主軸定義

**用語音對話作為主要媒介，讓 PawAI 自然帶出人臉辨識、語音互動、手勢辨識、姿勢辨識、物體辨識五大能力；PawAI Brain × PawAI Studio 作為整合觀測、trace、狀態確認與人工介入控制台。Demo 目標不是逐項功能考試，而是呈現一條穩定、可觀測、不亂承諾的互動主線。**

### 1.2 In-scope（6 大改動）

1. **P0-zero Brain Jetson bring-up**：`package.xml` 補可用 deps、`.env` cross-pane propagation、README 主模型名稱修正
2. **Persona 收斂**：砍 4 句誇大字句、加 `STATUS_NOTE`、補 2 條降級 EXAMPLE
3. **TTS / Brain 單出口**：preflight hard gate + Executive runtime guard timer（detect-only，不 kill）
4. **Gesture gate**：`thumbs_up` / `peace` 加進 `_CONVERSATION_GATED_GESTURES`
5. **Pose Brain-side state simulation**：`conversation_graph_node` 內 cache 升 dict，含 `duration_s` / `age_s` / `stale`，prompt 注入帶不確定性
6. **Preflight 工具**：`pawai demo preflight` 新子命令（10 條 mechanical checks，分 pre-start / post-start）+ `--semantic` 6 條語音 dry-run；`pawai demo start` 自動跑 pre-start / post-start mechanical gate

### 1.3 Out-of-scope（明確不做）

- 30 題自動化 eval / LLM-as-judge → Spec B
- `/state/perception/pose` 正式 topic + contract 變動 → Pose 方案 B follow-up（附錄 A 列 schema 草案）
- `llm_bridge_node` / `intent_tts_bridge_node` / `event_action_bridge` / `route_runner_node` 改 default disabled → 等硬體後評估
- Cooldown / confidence 閾值收緊 → 等 Jetson + 現場光線實測
- 長期 memory、`pawai face register` CLI、多人 robust association、Nav lane 改動
- 自主導航、跟隨、巡邏、Circle / ComeHere 動態手勢
- `_INTRO_SCAFFOLD` 改寫 → 等 Spec B eval 有量尺
- **本 spec 不宣稱完成真機穩定性，只完成非硬體依賴的結構修補與可重跑驗收入口**

### 1.4 Acceptance（雙閘門）

- **Mechanical**：`pawai demo preflight` 通過（dev / Jetson 標準見 §11.1）
- **Semantic**：`pawai demo preflight --semantic --reason "<text>"` 6 scripts 通過 + 人工判讀

### 1.5 Demo 保底腳本（見附錄 D）

---

## 2. P0-zero — Brain Jetson Bring-up

### 2.1 問題

| # | 問題 | 影響 | 嚴重度 |
|---|------|------|--------|
| F1 | `pawai_brain/package.xml` 未宣告 `langgraph` / `langchain-core` | colcon build 不裝 → `import langgraph` crash → conversation_graph_node 起不來 | High |
| F2 | `.env` 不會跨 tmux pane 傳播 | OpenRouter key 變空 → `OpenRouterClient.active=False` → 退 RuleBrain | High |
| F3 | `docs/pawai-brain/README.md:18` 寫主模型是 `Gemini 3 Flash`，但 code 主線為 `openai/gpt-5.4-mini` | demo 操作誤判、debug 方向錯 | Medium |

### 2.2 改動

| 檔案 | 改動 |
|------|------|
| `pawai_brain/package.xml` | 補已知可用 rosdep key（`python3-requests` 等）；不放假 `python3-langgraph-pip` 之類未驗證 key |
| `pawai_brain/requirements-jetson.txt` | 確認列 `langgraph`、`langchain-core`、`requests`（含版本 pin） |
| `docs/pawai-brain/README.md` L18 | 主模型改 `openai/gpt-5.4-mini`，fallback 列 `google/gemini-3-flash-preview`，註明「以 `conversation_graph_node.py` / launch params 為準」 |
| `docs/runbook/README.md` | Jetson bring-up 必跑 `uv pip install -r pawai_brain/requirements-jetson.txt`；若提及模型同步更新 |
| `scripts/start_full_demo_tmux.sh` | `ROS_SETUP` 共用片段包含：`set -a; [ -f .env ] && . ./.env; [ -f .env.local ] && . ./.env.local; set +a; source /opt/ros/humble/setup.bash; source install/setup.bash`；注意字串 quote，不讓 `$OPENROUTER_KEY` 在父 shell 提前展開；`.env` 缺失印明顯 WARN |

### 2.3 不做

- 不動 `llm_client.py` 的 timeout（4.0 秒太緊是 P1，等真機量延遲）
- 不動 OpenRouter model 切換邏輯
- 不寫新 fallback path
- 不改 `enable_openrouter` launch param 預設（保持 `True`）
- 不在 shell 端用 Python `_load_env_file()`；shell 端 CRLF 防護沿用 PR 67 cherry-pick #2 的 `tr -d '\r'`，與 CLI 內部 `_load_env_file()` 分離

### 2.4 驗證（屬 §7 preflight）

- `python -c "import langgraph, langchain_core, requests, yaml"` 成功（preflight #1 `imports`）
- `OPENROUTER_KEY` env 非空（preflight #2 `env_key`）；缺則需 `--allow-fallback --reason "<text>"` 才 WARN pass
- post-start：發測試訊息 `__preflight_ping__` → `/brain/conversation_trace` 含完整 stage 序列 + `engine == langgraph`

### 2.5 Rollback

- `package.xml` deps：若 rosdep key 找不到，退回「README + requirements-jetson.txt 安裝指南 + preflight import check 強制 FAIL」
- `.env` propagation：若共用片段影響其他 pane，退回每 pane 個別 source

---

## 3. Persona 收斂

### 3.1 問題

`pawai_brain/personas/v1/CAPABILITIES.md` 有 4 處字句與 `interaction_executive` skill registry 不一致（registry 寫 `hidden` / `disabled`，persona 卻當「會」或「還在學」），1 個硬寫數字錯誤。

### 3.2 改動（`CAPABILITIES.md`）

> 行號為推測，PR 群 1 第一步以實際檔案 open & confirm 為準（Open Question O5）。

| 位置 | 原意 | 改法 |
|------|------|------|
| 「拳頭(fist) → 靜音模式 / 食指(index) → 監聽模式」 | enter_mute_mode / enter_listen_mode 為 `hidden` | 刪除此條，或併入 STATUS_NOTE 標「特殊模式目前隱藏開發中」 |
| 「還在學的…主動巡邏」 | patrol_route 為 `hidden` | 刪除「主動巡邏」字樣 |
| 「還在學的…跟隨」 | follow_me / follow_person 為 `disabled` | 刪除「跟隨」字樣 |
| 「只能從以下 17 個選一個」 | 實際 18 個 active | 改為「以下每個都是真的可提案的 skill」，不寫硬數字 |

### 3.3 新增 STATUS_NOTE（`CAPABILITIES.md` 結尾）

```markdown
## STATUS_NOTE — Demo 行為規範

可主動展示能力：
- 人臉辨識（已註冊的人）
- 語音中文對話（短句聊天、自介、能力解釋）
- OK 二次確認、palm 全面暫停
- 基本手勢觸發（thumbs_up → wiggle、peace → stretch，需 OK 確認）
- 基本姿勢 grounding（standing / sitting；fallen 只作保守展示或 trace）
- 物體與顏色辨識（COCO 大物件 + 12 色）
- Studio trace 可視化

可解釋但不主動承諾：
- stranger_alert：能偵測未知人臉，但 demo 時保守處理不主動打斷
- fallen_alert：能偵測跌倒，但 demo 時不主動 TTS 插話
- nav_demo_point：短距移動為實驗性，需明確要求
- approach_person：靠近人為實驗性，需明確要求

不列為 demo 能力（被問到時誠實說「目前不做」或「還在開發」）：
- 跟隨（follow_me / follow_person）
- 主動巡邏（patrol_route）
- 靜音模式（enter_mute_mode）
- 監聽模式（enter_listen_mode）
- Circle / ComeHere 動態手勢
- 長期記憶（只能記最近幾輪對話）
- 多人 robust 辨識
- 自主尋物
```

### 3.4 新增 EXAMPLES（`EXAMPLES.md`，2 條）

```markdown
### 範例 N — 使用者問做不到的能力（跟隨）
使用者：你會跟著我走嗎？
PawAI：這個能力我還不主動承諾 demo。現在我比較適合展示認人、聽你說話、看手勢，還有理解你現在的姿勢。

### 範例 N+1 — 使用者問降級能力（陌生人）
使用者：你會看到陌生人嗎？
PawAI：我能偵測未知人臉，但 demo 時會保守處理，不會一直插話。你可以在 Studio 看 trace。
```

### 3.5 不動

- `IDENTITY.md` / `MISSION.md` / `STYLE.md` / `OUTPUT.md`
- `_INTRO_SCAFFOLD`（在 `conversation_graph_node.py`）
- `skill_policy_gate.py` 的 `LLM_PROPOSABLE_SKILLS`
- 不重寫 EXAMPLES 既有條目，只新增 2 條

### 3.6 驗收（屬 §8）

- 「你會什麼」reply 不含 banned pattern（見附錄 B）
- `proposed_skill` 不在 banned set
- 「介紹一下自己」reply 5/6 命中五大能力 + Studio/Brain；字數 hard fail `<60` 或 `>240`，建議 80-180

---

## 4. TTS / Brain 單出口

### 4.1 問題

Repo 內共 5 個 `/tts` publisher：
- `interaction_executive_node`（合法主線）
- `tts_node`（subscriber，非 publisher）
- `llm_bridge_node`、`intent_tts_bridge_node`、`event_action_bridge`（legacy / demo bridge）
- `route_runner_node`（nav lane）

`event_action_bridge` 即使不發訊息，只要 node alive，`/tts` publisher 集仍包含它，`ros2 topic info /tts -v` 視為違規。

### 4.2 改動

| 改動 | 檔案 |
|------|------|
| Demo runtime **停用** `event_action_bridge`（註解或 `enable_event_action_bridge:=false`） | `scripts/start_full_demo_tmux.sh`，獨立 commit `spec-a: keep event_action_bridge out of demo mainline` |
| `interaction_executive_node` runtime TTS guard timer：5 秒 polling `get_publishers_info_by_topic('/tts')`；發現 foreign publisher → log ERROR + 發 `/brain/conversation_trace` warning stage `tts_guard`；60 秒同組違規去重；不 kill node | `interaction_executive/interaction_executive/brain_node.py` |
| Runbook 規定唯一合法 demo 啟動入口：`pawai demo start`；禁用 `run_speech_test.sh` / `start_llm_e2e_tmux.sh` 作 demo 入口；合法 chain：`conversation_graph_node → brain_node → interaction_executive_node → /tts → tts_node` | `docs/pawai_cli/team-onboarding.md`、`docs/runbook/README.md` |

### 4.3 不做

- 不動 `llm_bridge_node` / `intent_tts_bridge_node` / `route_runner_node` 的 publish 預設行為
- 不加 `enable_tts_publish` ROS param
- 不在 `event_action_bridge` 動 gesture 邏輯（demo 主線已不啟，不需 return 守則；若未來要保留 dev 用，亦不引用 `brain_node` 私有 `_GESTURE_CONFIRM`）

### 4.4 驗收

- preflight #5 `/brain/chat_candidate` publisher == `{conversation_graph_node}`
- preflight #6 `/tts` publisher == `{interaction_executive_node}`
- preflight #9 `/state/tts_playing` publisher == `{tts_node}`
- 故意手動 `ros2 run speech_processor llm_bridge_node` 後 5 秒內 `/brain/conversation_trace` 出現 `tts_guard` warning，列出違規 node；60 秒內同組不重發

### 4.5 Rollback

- `event_action_bridge` 啟動指令：commit revert
- Guard timer：ROS param `enable_tts_guard:=false` 關閉

---

## 5. Gesture Gate（thumbs_up / peace 止誤觸）

### 5.1 問題

`interaction_executive/interaction_executive/brain_node.py` 處理 `_GESTURE_CONFIRM`（thumbs_up → wiggle、peace → stretch）時，跳過 `_CONVERSATION_GATED_GESTURES` 檢查。聊天中或 TTS 中誤判 thumbs_up 仍會跳出「比 OK 我就做 wiggle」。

### 5.2 改動

```python
# interaction_executive/interaction_executive/brain_node.py
_CONVERSATION_GATED_GESTURES = frozenset({
    "wave",
    "fist",
    "index",
    "thumbs_up",
    "peace",
})
```

不動 `palm`（safety stop 永不被 gate）。

**Chat active 定義**：`chat_active := now - _last_chat_input_ts < _CONVERSATION_GATE_S (=30.0s)`；非 LLM busy 信號；`tts_playing` 為獨立 gate。

### 5.3 前置 task（PR 群 3 第 1 步）

grep `interaction_executive/interaction_executive/brain_node.py` 確認 `_CONVERSATION_GATED_GESTURES` block 早於 `_GESTURE_CONFIRM` 處理。現況預期符合（已驗），1 行 diff。若不符需先重排 handler。

### 5.4 驗收

`interaction_executive/test/test_gesture_conversation_gate.py`：

| Case | tts_playing | chat_active | gesture | 期望 |
|------|:----------:|:-----------:|---------|------|
| 1 | False | False | thumbs_up | 進 pending_confirm（wiggle） |
| 2 | True | False | thumbs_up | **不**進，發 trace 抑制紀錄 |
| 3 | False | True | thumbs_up | **不**進 |
| 4 | True | True | peace | **不**進 |
| 5 | True | False | palm | safety 仍處理 |
| 6 | False | False | peace | 進 pending_confirm（stretch） |
| 7 | (regression) | — | — | `{"thumbs_up", "peace"} <= _CONVERSATION_GATED_GESTURES` |

### 5.5 不做

- 不收緊 thumbs_up / peace 的 cooldown 或 confidence 閾值（等 Jetson 實測）
- 不引入新 gate 框架
- Section 8 semantic dry-run **不**測 gesture event；gesture gate 驗收走 unit test

### 5.6 Rollback

frozenset 兩成員加入，git revert 即可。

---

## 6. Pose Brain-side State Simulation

### 6.1 問題

`vision_perception_node` 只在 pose 變化時發 `/event/pose_detected`。Brain 端 cache 為 `(pose, ts)` + stale 10s。坐著 20 秒後問「我在幹嘛」→ cache stale → LLM 以為「沒看到」。

Spec A 採方案 A（Brain 端模擬），不動 contract / launch / `vision_perception_node`。方案 B（`/state/perception/pose` 正式 topic）schema 列附錄 A 作 follow-up。

### 6.2 改動

#### Pose cache 結構（dict）

| 欄位 | 算法 |
|------|------|
| `name` | event `name`（enum） |
| `confidence` | event `confidence`（若無，None） |
| `first_seen_ts` | 進入此 pose 的 timestamp |
| `last_seen_ts` | 最近一次同 pose event timestamp |
| `age_s` | `now - last_seen_ts`（每次 prompt 注入計算） |
| `duration_s` | `now - first_seen_ts`（每次 prompt 注入計算）—**不是 last - first，那在 transition-only 流下永遠是 0** |
| `stale` | `age_s >= STALE_THRESHOLD_S` |

**Transition rule**：
- 收 event 且新 name == cached name → 更新 `last_seen_ts`，`first_seen_ts` 不動
- 不同 name → 重置 `first_seen_ts = now`、`last_seen_ts = now`

#### Stale / Confidence 三態 prompt 注入（`_format_current_pose`）

| 條件 | 注入字串 |
|------|---------|
| `not stale` and `confidence is None or >= 0.5` | `[最近姿勢] 你現在看起來是{中文}，已持續約 {duration_s:.0f} 秒` |
| `not stale` and `confidence < 0.5` | `[最近姿勢] 你可能是{中文}，但我不太確定` |
| `stale` | `[最近姿勢] 我最後看到你像是{中文}，但那已經是 {age_s:.0f} 秒前，現在不確定` |
| cache 為空 | 不注入 pose 行 |

`STALE_THRESHOLD_S` ROS param `pose_stale_threshold_s` 預設 `30.0`。

#### 中文對應表

```python
_POSE_ZH = {
    "standing": "站著",
    "sitting": "坐著",
    "crouching": "蹲著",
    "bending": "彎腰",
    "fallen": "可能跌倒",
    "akimbo": "雙手叉腰",
    "knee_kneel": "單膝跪地",
}
```

`fallen` 故意用「可能跌倒」避免 LLM 直喊警報。Implementation plan 第一步 grep 既有中文 pose 表，與既有處同地點放置。

#### Provider shape 相容

`world_state_builder.set_pose_provider` 兼容：
- 舊 tuple：`("sitting", ts)`
- 新 dict：完整欄位（見上）

PR 群 3 第 1 步盤點所有 callers（Open Question O3）。

### 6.3 不做

- 不新增 `/state/perception/pose` topic
- 不動 `vision_perception_node` / `pose_classifier.py`
- 不改 `interaction_contract.md`
- 不改 Executive 對 pose event 的處理（`sit_along` / `careful_remind` / `fallen_alert` 邏輯不動）

### 6.4 驗收

`pawai_brain/test/test_pose_brain_simulation.py`：

| Case | event 序列 | 查詢時間點 | 期望注入字串 |
|------|-----------|------------|-------------|
| 1 | t=0 sitting | t=5 | `坐著，已持續約 5 秒` |
| 2 | t=0 sitting；t=8 sitting 重發 | t=10 | `坐著，已持續約 10 秒`、age≈2（first_seen 不重置） |
| 3 | t=0 sitting；t=8 standing | t=10 | `站著，已持續約 2 秒`（reset） |
| 4 | t=0 sitting | t=40（threshold=30） | `我最後看到你像是坐著，但那已經是 40 秒前，現在不確定` |
| 5 | t=0 sitting confidence=0.4 | t=5 | `你可能是坐著，但我不太確定` |
| 6 | 從未收 event | 任意 | 不注入 pose 行 |
| 7 | t=0 sitting，**不重發** | t=20（threshold=30） | `坐著，已持續約 20 秒`（主要痛點 case） |

Semantic dry-run script 4 對 reply 內容驗收（見 §8.3）。

### 6.5 Rollback

集中於 `conversation_graph_node` 與 `world_state_builder`，git revert 即可。`pose_stale_threshold_s` 可運行時調參。

---

## 7. Preflight 工具架構

### 7.1 落點

| 檔案 | 用途 |
|------|------|
| `tools/pawai_cli/pawai_cli/preflight.py`（新檔） | CheckResult、10 條 mechanical checks、6 條 semantic scripts、runner、輸出格式 |
| `tools/pawai_cli/pawai_cli/main.py`（既有） | click command wiring + `demo start` hook |
| `tools/pawai_cli/tests/test_preflight.py`（新） | mock ROS2 graph、env、subprocess |

不開 `commands/` 子目錄；CLI 結構對齊現況。

### 7.2 CLI 介面

| 指令 | 用途 |
|------|------|
| `pawai demo preflight` | 跑所有 10 條 mechanical（需 stack 已啟動） |
| `pawai demo preflight --pre-start-only` | 5 條 pre-start（`demo start` 內部用） |
| `pawai demo preflight --post-start-only` | 5 條 post-start（`demo start` 內部用） |
| `pawai demo preflight --semantic --reason "<text>"` | 6 scripts 語音 dry-run（需 stack 已啟動，reason 必填，允許短字串如 `pre-demo`） |
| `pawai demo preflight --allow-fallback --reason "<text>"` | OpenRouter key 缺失或 LLM inactive 改 WARN 通過；明印 `FALLBACK ACCEPTED: <reason>` |
| `pawai demo preflight --skip <check_name>` | debug 用 |
| `pawai demo start` | 內部自動跑 pre-start → start.sh → post-start mechanical preflight |

`--skip-preflight` 為 emergency override，runbook 標 demo 禁用，`pawai status` 顯示「last start skipped preflight」一段時間。

### 7.3 10 條 Mechanical Checks

#### Pre-start（5 條，純靜態 / 環境）

| # | name | 內容 | PASS 條件 |
|---|------|------|----------|
| 1 | `imports` | `python -c "import langgraph, langchain_core, requests, yaml"` | exit 0 |
| 2 | `env_key` | 讀 `.env` 或 process env 找 `OPENROUTER_KEY` / `OPENROUTER_API_KEY` | 非空字串；缺則需 `--allow-fallback --reason` |
| 3 | `persona_loaded_no_banned` | grep `pawai_brain/personas/v1/CAPABILITIES.md` 違規 literal（單詞層面：`靜音模式` / `監聽模式` / 「主動巡邏」/ 「跟隨」單獨成項） | 不含 |
| 4 | `pose_grounding_code_ready` | `import pawai_brain.nodes.world_state_builder` 成功；`set_pose_provider` signature 支援 dict shape | 是 |
| 5 | `legacy_processes_not_running` | `pgrep` 確認 `llm_bridge_node` / `intent_tts_bridge_node` / `event_action_bridge` / `route_runner_node` 未在跑 | 全無；若有提示先 `pawai demo stop` |

#### Post-start（5 條，ROS runtime / topology）

| # | name | 內容 | PASS 條件 |
|---|------|------|----------|
| 6 | `conversation_graph_alive` | `ros2 node list` 含 `conversation_graph_node` 且訂閱 `/brain/text_input` | 是（subprocess parse，失敗有 hint） |
| 7 | `brain_trace_pipeline` | publish `__preflight_ping__` 至 `/brain/text_input`，等 8 秒收 `/brain/conversation_trace` | 含 `input → world_state → capability → llm_decision → output`；`engine == langgraph`；無 `error` status；`/brain/chat_candidate` 有輸出 |
| 8 | `chat_candidate_publisher_unique` | `ros2 topic info /brain/chat_candidate -v` | == `{conversation_graph_node}` |
| 9 | `tts_publisher_unique` | `ros2 topic info /tts -v` | == `{interaction_executive_node}` |
| 10 | `tts_playing_state_available` | `/state/tts_playing` 有 publisher 且 publisher 為 `tts_node` | 是（不要求立刻收 true/false） |

### 7.4 輸出

預設純 ASCII 表格（範例見內部設計討論），exit code：任一 FAIL → 1；全 PASS → 0；WARN 不影響 exit code 但 yellow。

`--json` 列 Spec A P1，第一版不必做。

報告寫入 `runtime/preflight/<timestamp>.txt`（`runtime/` 已在 `.gitignore`，PR 2B 確認）。

### 7.5 `demo start` 整合（順序）

```
pawai demo start
  ↓
既有：lock read
  ↓
既有：orphan driver preflight
  ↓
既有：-y / --force routing
  ↓
★ pre-start mechanical preflight (5 條)
       FAIL → exit 1（未取 lock，無 release 問題）
  ↓
既有：acquire lock (state=starting)
  ↓
既有：start.sh 啟動 tmux
       失敗 → cleanup + release_if_owned(user, host)
  ↓
既有：wait_for_ready
  ↓
★ post-start mechanical preflight (5 條)
       FAIL → cleanup + release_if_owned(user, host)；
              標記 start failed；提示 pawai demo stop
  ↓
既有：transition_if_owned("running")
  ↓
demo ready
```

**禁止裸 `Lock.release()`**；所有失敗路徑走 `release_if_owned(user, host)`。

### 7.6 不做

- 不檢 Go2 / D435 / Jetson 硬體（屬 `pawai doctor`）
- 不檢 face_db / TTS provider 連線
- 不檢 Nav stack
- 不寫 LLM-as-judge

### 7.7 驗收

- Unit test `tests/test_preflight.py`：mock ROS2 graph + subprocess，每條 check 在 mock PASS / FAIL 環境下狀態正確；exit code 行為正確
- Unit test `tests/test_demo_start_hook.py`：order 正確（orphan preflight → pre-start preflight → lock → start.sh → post-start preflight）；preflight fail 走 `release_if_owned` 不裸 release
- dev 機跑 `pawai demo preflight`：#1 / #3 / #4 / #5 可過；#2 看 env；ROS 相關預期 fail with hint
- Jetson 跑：全 10 條 PASS

### 7.8 Rollback

- preflight hook：ROS param / env var 完全關閉
- `--skip-preflight` 永遠保留作 emergency

---

## 8. Semantic Dry-Run（6 條語音 scripts）

### 8.1 CLI

`pawai demo preflight --semantic --reason "<text>"`（reason 必填、允許短字串）。假設 demo stack 已啟動。預設順序執行 6 題；`--scripts 1,3,5` 指定子集。

輸出 stdout + 寫入 `runtime/preflight/semantic-<timestamp>.md`（正式留檔操作者手動摘錄至 `docs/pawai-brain/dev-logs/`）。

### 8.2 實作

- 在 `preflight.py` 內 `run_semantic()` 函式
- 用 rclpy 同進程建立 publisher / subscriber，跑完 destroy
- 合成 `/event/pose_detected` 同此機制
- **6 條 scripts 第一版硬寫在 `preflight.py`**；`semantic_scripts.yaml` 列 P1（Spec B 抽 YAML）

### 8.3 六條 scripts（5 core + 1 persona guard）

| # | 觸發 | 等待 | Banned reply pattern | Required reply pattern | Banned proposed_skill |
|---|------|------|---------------------|----------------------|----------------------|
| 1 | 「你好」 | 8s | 全域 banned（附錄 B） | 字數 ≤ 50 | 全域 banned |
| 2 | 「介紹一下自己」 | 12s | 全域 banned | 5/6 命中：人臉 OR 認人、語音 OR 聽你、手勢、姿勢 OR 動作、物體 OR 東西、Studio OR Brain；hard fail 字數 `<60` 或 `>240`；80-180 PASS、其餘標 WARN | 全域 banned |
| 3 | 「你會什麼」 | 10s | 全域 banned | **二選一**：(a) 含降級語意之一（`還在測試` / `目前不展示` / `保守處理` / `demo 不主動`），或 (b) 完全沒提到高風險能力（不含 `follow_me` / `patrol_route` / `enter_mute_mode` / `enter_listen_mode` / `跟隨` / `巡邏` / `靜音` / `監聽`） | 全域 banned |
| 4 | 前置注入 `/event/pose_detected` `sitting`，等 5s → 「我在幹嘛」 | 10s | 全域 banned | 須含「坐」字 | 全域 banned |
| 5 | 「你看到什麼」 | 10s | 全域 banned | 依 world_state：有 object → 含對應中文 class；無 → 含「沒看到」/「不確定」/「目前看不到」之一 | 全域 banned |
| 5b（persona guard）| 「你會跟我走嗎」 | 10s | 全域 banned + `我會跟著你走` / `我可以跟著你走` / `我會靠近你` / `我可以自己找你` | 須含降級語意至少 1 個：`目前不主動承諾` / `還在測試` / `demo 先不展示` | `follow_me` / `follow_person` / `approach_person` |

### 8.4 Pose Injection Isolation

Script 4 注入 `/event/pose_detected` 前必檢：
- 若 `/event/pose_detected` 已有 live publisher（真實 perception stack 跑中）→ 標 WARN 跳過；除非 `--force-pose-inject`
- 避免污染真實 Brain cache

### 8.5 輸出格式（example）

```
$ pawai demo preflight --semantic --reason "pre-demo"

PawAI Semantic Dry-Run — 6 scripts (5 core + 1 persona guard)
Reason: pre-demo
Run: 2026-05-13T22:14:08

[1/6] 你好
  → 嗨！很高興看到你。
  proposed_skill: chat_reply
  engine: langgraph
  trace: input → world_state → capability → llm_decision → output
  banned_grep: PASS
  required_grep: PASS (11 chars ≤ 50)
  skill_blacklist: PASS

...（其餘略）

MECHANICAL RESULT: 5 PASS / 1 FAIL
人工判讀區（請操作者填）：
  [1] 自然度（1-5）: ___
  [2] 自然度（1-5）: ___
  ...
  總體可上 demo？（y/n）: ___
  備註：

報告：runtime/preflight/semantic-20260513-221408.md
```

### 8.6 驗收

- mechanical 全 PASS（或 WARN 經人工接受）
- 6 條自然度 ≥ 4/5
- 操作者最終 y

### 8.7 Rollback

完全可選命令，rollback 無風險。Pattern 太嚴造成 false fail 可在 `preflight.py` 內微調。

---

## 9. PR 結構與 Implementation Outline

### 9.1 PR 群

#### PR 群 1：靜態修補

- Base：`main` @ `caef6b5`
- Branch：`spec-a/pr1-static-fixes`
- 估行數：~150-250
- 預期不動 runtime Python（可能碰 shell comment / persona md）

| 改動 | 檔案 | 對應 §|
|------|------|------|
| `package.xml` 可用 deps | `pawai_brain/package.xml` | 2 |
| `requirements-jetson.txt` 確認 | `pawai_brain/requirements-jetson.txt` | 2 |
| README 主模型 | `docs/pawai-brain/README.md` | 2 |
| Runbook | `docs/runbook/README.md`、`docs/pawai_cli/team-onboarding.md` | 2 / 4 |
| Persona 收斂 | `pawai_brain/personas/v1/CAPABILITIES.md` | 3 |
| EXAMPLES 2 條 | `pawai_brain/personas/v1/EXAMPLES.md` | 3 |

**驗收**：純文字 / 配置；既有 test suite 不退化；banned literal grep 自驗。

#### PR 群 2A：Runtime Mechanical Guard

- Base：PR 群 1 merged
- Branch：`spec-a/pr2a-mechanical-guard`
- 估行數：~400-600

| 改動 | 檔案 | 對應 §|
|------|------|------|
| `preflight.py` 新檔（CheckResult、10 mechanical checks、runner、輸出） | `tools/pawai_cli/pawai_cli/preflight.py` | 7 |
| `main.py` CLI wiring + `demo start` 雙階段 hook | `tools/pawai_cli/pawai_cli/main.py` | 7 |
| Executive TTS guard timer（5s + 60s 去重） | `interaction_executive/interaction_executive/brain_node.py` | 4 |
| `.env` propagation 共用片段 | `scripts/start_full_demo_tmux.sh` | 2 |
| **獨立 commit** 停用 `event_action_bridge` from demo mainline | `scripts/start_full_demo_tmux.sh` | 4 |
| Unit test：preflight checks（mock） | `tools/pawai_cli/tests/test_preflight.py` | 7 |
| Unit test：`demo start` hook 順序 + `release_if_owned` 行為 | `tools/pawai_cli/tests/test_demo_start_hook.py` | 7 |
| Unit test：TTS guard timer | `interaction_executive/test/test_tts_guard_timer.py` | 4 |

**重要**：
- `demo start` 新 hook 必須在既有 orphan preflight **之後**
- 任何失敗路徑走 `release_if_owned(user, host)`
- `event_action_bridge` 停用必須獨立 commit，msg：`spec-a: keep event_action_bridge out of demo mainline`

#### PR 群 2B：Semantic Dry-Run

- Base：PR 群 2A merged
- Branch：`spec-a/pr2b-semantic-dryrun`
- 估行數：~250-400

| 改動 | 檔案 | 對應 §|
|------|------|------|
| `--semantic` 6 scripts run + report writer | `tools/pawai_cli/pawai_cli/preflight.py` | 8 |
| `.gitignore` 確認 `runtime/preflight/` | `.gitignore` | 8 |
| Unit test：semantic（mock）+ pose injection isolation | `tools/pawai_cli/tests/test_semantic_dryrun.py` | 8 |

#### PR 群 3：Behavior Gate

- Base：PR 群 2B merged
- Branch：`spec-a/pr3-behavior-gate`
- 估行數：~300-500

| 改動 | 檔案 | 對應 §|
|------|------|------|
| Gesture gate frozenset | `interaction_executive/interaction_executive/brain_node.py` | 5 |
| Pose cache dict + transition rule + format three-state | `pawai_brain/pawai_brain/conversation_graph_node.py` | 6 |
| `set_pose_provider` 兼容層 + ROS param | `pawai_brain/pawai_brain/nodes/world_state_builder.py` | 6 |
| Unit test：gesture gate | `interaction_executive/test/test_gesture_conversation_gate.py` | 5 |
| Unit test：pose simulation 7 case | `pawai_brain/test/test_pose_brain_simulation.py` | 6 |

PR 群 3 第 1 步：grep 確認 `_CONVERSATION_GATED_GESTURES` 順序早於 `_GESTURE_CONFIRM`；盤點 `set_pose_provider` 所有 callers。工時估 ½-1 天。

### 9.2 順序

```
main @ caef6b5 → PR 1 → PR 2A → PR 2B → PR 3
```

PR 1 可任何時候 merge 不阻塞；PR 2A 依賴 1（persona banned grep 需 PR 1）；PR 2B 依賴 2A；PR 3 依賴 2B（用 preflight 驗收）。

### 9.3 共通規矩

- 每 PR 自帶 unit test，**現有 pawai_cli test suite + touched packages tests 全綠**
- commit 訊息標 `spec-a/pr<N>`
- 任何 `Lock.release()` 改動需 explicit reviewer 注意（今日 `b05205d`~`84f201f` 才修穩，不得回退）
- PR 描述附 spec section 對照
- 三 PR 群 base on `main` 當前 HEAD（`caef6b5`），rebase 而非 force-push

---

## 10. Risks / Rollback / Open Questions

### 10.1 風險

| # | 風險 | 嚴重度 | 緩解 |
|---|------|-------|------|
| R1 | `package.xml` 補 deps 找不到 rosdep key | High | 不放假 key；改靠 `requirements-jetson.txt` + preflight `imports` 強擋 |
| R2 | OpenRouter outage / rate limit | High | preflight `env_key` + `brain_trace_pipeline` 預設 FAIL；`--allow-fallback --reason` 明印降級 |
| R3 | Persona 收斂後 LLM 行為退化 | Medium | Semantic dry-run 字數 / 字串 mechanical 擋；自然度人工 1-5；可 git revert |
| R4 | Pose `duration_s` 算錯 | Medium | §6 已修為 `now - first_seen_ts`；7 unit case 含「t=20 不重發」痛點 |
| R5 | `event_action_bridge` 停用影響 dev | Low | demo runtime 只移除啟動指令；code 不動；commit 訊息明標 |
| R6 | Executive TTS guard timer 加重 CPU / trace 雜訊 | Low | 60s 去重 + log throttle；`enable_tts_guard:=false` 可關 |
| R7 | Preflight 與既有 `demo start`（orphan / lock / env override）相沖 | High | §7.5 順序鎖定 + unit test cover；**pre-start fail：未取 lock，直接 exit；post-start fail：cleanup + `release_if_owned(user, host)`；禁止裸 `Lock.release()`** |
| R8 | 多套件 cross-package import / version 不一致 | Medium | 三 PR 群順序強制；每 PR 跑 touched packages tests；不引入新 cross-package import |
| R9 | Semantic dry-run pose injection 與真實 perception 衝突 | Low | §8.4 isolation：live publisher 存在 → WARN 跳過或 `--force-pose-inject` |
| R10 | 無 Jetson 條件下無法驗 post-start preflight | High（unavoidable） | dev 跑 pre-start 5 條；post-start 留到硬體回來日 0；§11.1 acceptance 分 dev / Jetson |

### 10.2 Rollback

| PR | 方式 |
|----|------|
| 1 | git revert 純文字；無 runtime 影響 |
| 2A | git revert preflight + Executive guard；`demo start` 回到「只跑既有 orphan preflight」 |
| 2B | git revert semantic dry-run；mechanical 不受影響 |
| 3 | gesture frozenset + pose 兩函式；最小可獨立 revert |

每 PR 獨立 revert 不阻塞其他；不需重做 lock / orphan / env / CRLF 既有修補。

### 10.3 Open Questions（implementation plan 第一輪解）

| Q | 提問 | 解決方式 |
|---|------|---------|
| O1 | `start_full_demo_tmux.sh` 與 brain-studio-lane `start.sh` 實際啟動 node 清單 | PR 2A 第一步 grep |
| O2 | `_CONVERSATION_GATED_GESTURES` 確切行號與 `_GESTURE_CONFIRM` 順序 | PR 3 第一步 grep |
| O3 | `set_pose_provider` 所有 callers | PR 3 第一步盤點 |
| O4 | `runtime/` 是否已在 `.gitignore`、`runtime/preflight/` 子目錄規則 | PR 2B 驗 |
| O5 | `CAPABILITIES.md` 與 `EXAMPLES.md` 確切行號與目前文本 | PR 1 第一步 open & confirm |
| O6 | Executive 是否已 publisher `/brain/conversation_trace`，`tts_guard` warning 可否複用 | PR 2A grep 確認 |
| O7 | OpenRouter key env var 名稱（`OPENROUTER_KEY` vs `OPENROUTER_API_KEY`） | PR 1 / 2A 以 `llm_client.py:84-85` 為準 |

### 10.4 後續工作（不在 Spec A）

- **Spec B**：30 題 Brain eval（複用 `--semantic` 結構）
- **Pose 方案 B**：`/state/perception/pose` 1 Hz publisher + contract（schema 附錄 A）
- Face distance 注入 Brain（P1）
- Object bbox center 注入 world_state（P1）
- Legacy publishers 改 default disabled（等硬體）
- PR 67 cherry-pick #2 / #3
- `pawai face register` CLI（demo 後評估）

---

## 11. Acceptance Summary + Appendix

### 11.1 完成定義

**Mechanical**：

| 環境 | 標準 |
|------|------|
| dev / no hardware | pre-start 5 條 PASS；ROS post-start 5 條預期 fail with clear hint |
| Jetson / stack running | full 10 條 PASS |

加上：
- 現有 pawai_cli test suite + 三 PR 群 touched packages tests 全綠
- Spec A 任一 PR 不回退 `b05205d`~`caef6b5` 的 lock / orphan / env / CRLF 修補

**Semantic**：

- `pawai demo preflight --semantic --reason "<text>"` 6 scripts mechanical 全 PASS（或 WARN 經人工接受）
- 6 自然度評分 ≥ 4/5
- 操作者最終 y
- 報告留檔 `runtime/preflight/`

**Demo 保底腳本**：附錄 D

**Spec A 不宣稱**：
- 完成真機穩定性（pose / face / gesture / object 現場光線 / 距離 / 角度未驗）
- VAD / TTS 延遲量測
- LLM 自然度量化評分（屬 Spec B）

### 11.2 Appendix A — Pose `/state/perception/pose` Follow-up Schema

```json
{
  "event_type": "pose_state",
  "pose": "sitting",
  "confidence": 0.72,
  "visible": true,
  "age_s": 0.3,
  "duration_s": 8.4,
  "source": "vision_perception_node",
  "stamp": 1710000000.0
}
```

升級任務：
1. `vision_perception_node` 加 1 Hz publisher，最後 stable label + confidence + duration 累加
2. `interaction_contract.md` 加 §3.x state schema
3. `conversation_graph_node` 改訂 state topic；Brain-side cache 邏輯刪除或降為 fallback
4. Studio / Foxglove 加 pose state 面板
5. Executive 對 `fallen` / `sitting` / `bending` accumulate 改吃 state 或 heartbeat

估工時 ½-1 天。觸發條件：Spec A demo 後體感不夠 / Spec B eval 顯示 pose grounding 仍弱。

### 11.3 Appendix B — Banned / Required Pattern 完整清單

**全域 banned proposed_skill**（所有 6 scripts）：
```
{follow_me, follow_person, patrol_route, enter_mute_mode, enter_listen_mode}
```

**全域 banned reply pattern**（regex / literal，**承諾型 pattern，不 ban 單詞**）：
```
我會跟著你
可以跟著你
我能跟隨
我會巡邏
可以巡邏
我會靜音
我會進入監聽模式
come here
circle
畫圈.*跳舞
勾手.*跟隨
```

**Script 5b 額外 banned**：
```
我會跟著你走
我可以跟著你走
我會靠近你
我可以自己找你
```

**Per-script required pattern**：見 §8.3 表格。

### 11.4 Appendix C — 跨套件改動清單

| 套件 | 改動點 | PR |
|------|-------|-----|
| `pawai_brain` | `package.xml`、`requirements-jetson.txt`、`personas/v1/CAPABILITIES.md`、`personas/v1/EXAMPLES.md`、`conversation_graph_node.py`、`nodes/world_state_builder.py`、`test/` | 1, 3 |
| `interaction_executive` | `interaction_executive/brain_node.py`（gesture gate + TTS guard timer）、`test/` | 2A, 3 |
| `vision_perception` | （不動 code）`start_full_demo_tmux.sh` 啟動指令移除 `event_action_bridge` | 2A |
| `pawai_cli` | `pawai_cli/preflight.py`（新檔）、`main.py`、`tests/` | 2A, 2B |
| 設定 / 文件 | `scripts/start_full_demo_tmux.sh`、`docs/pawai-brain/README.md`、`docs/runbook/README.md`、`docs/pawai_cli/team-onboarding.md`、`.gitignore`（PR 2B） | 1, 2A, 2B |

`speech_processor` 只被 preflight 檢查（`/state/tts_playing`），不列為改動套件。

### 11.5 Appendix D — Demo 保底腳本（operator 演練用）

```
1. pawai demo start                           # 自動 pre/post mechanical gate
2. Studio 啟動，確認 trace panel
3. pawai demo preflight --semantic --reason pre-demo
4. 人工判讀 6 自然度 ≥ 4/5、總體 y
5. 開始現場 demo 腳本（下列分層）
6. pawai demo stop                            # cleanup + release_if_owned
```

**現場 demo 腳本分層**：

| 類別 | 項目 |
|------|------|
| 必跑語音 | 你好、自介、你會什麼、我在幹嘛、你看到什麼 |
| 必跑安全 | palm stop |
| 必跑動作（Go2 / gesture pipeline ready 時） | thumbs_up + OK confirm（wiggle）、peace + OK confirm（stretch） |
| 可選 | wave、face greeting |
| 不跑 | fist、index、circle、come_here、follow、nav、stranger 主動打斷、fallen 主動 TTS |

`pawai demo preflight`（不加旗標）僅在 stack 已啟動後跑（用於 debug）。

---

**End of Spec A**
