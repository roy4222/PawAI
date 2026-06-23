# PawAI Brain v2 + CLI v2 PRD（demo 後重構提案，待 Roy 審核）

> 狀態：**draft for review**（2026-06-10）。**不在 6/18 demo 範圍**——這是錄完影片後
> 的正式重構案。本文只提需求/架構/邊界，不含實作細節。
> 起因：6/9-6/10 HITL 反覆證明 `brain_node.py` 的「if/else 疊加 + 單一 TTS 通道
> 搶佔」是 demo 不穩的結構性根因（stranger_alert 霸佔、手勢誤觸搶話、NAV step
> 失敗卡死 active_plan）。今天用「外科手術」修法（phase gate / 各種 enable flag）
> 撐過 demo，但這些是症狀繃帶，不是根治。

---

## 0. 指導原則（Roy 6/10 拍板）

1. **demo 前不大重構**；demo 後才動 v2。
2. **真正控制狗的那層永遠是我們自己的**（e-stop / Nav2 / reactive_stop / gesture
   誤觸 / TTS 搶占 / 現場安全）。OpenClaw / NeMo Guardrails / ROSClaw 只**啟發**
   agent layer / skill schema / guardrails / trace 設計，**不直接當 Go2 的腦**。
3. v2 保留 ROS2 / safety / Go2 ownership；把 agent 思考層與安全執行層**明確切開**。
4. 任何 v2 元件上線都要能**降級回 v1 行為**（feature flag），不可一次性切換。

---

## 1. 為什麼要 Brain v2（v1 的結構性債）

| v1 症狀 | 6/10 繃帶 | 根因 |
|---|---|---|
| stranger_alert 霸佔 brain → cup/greet 全黑 | `stranger_alert_enabled=false` | 所有事件搶同一條 active_plan，高優先 alert 卡死低優先社交 |
| 手勢誤觸搶 TTS / pending confirm | `gesture_enabled` gate + min_conf | 無 phase 概念，任何事件任何時刻都能觸發 |
| greet/object/gesture 互相搶話 | `demo_phase` gate（最小版）| 無中央仲裁，先到先佔 TTS |
| NAV step 失敗卡死 active_plan | STEP_FAILED 視為 terminal | plan 生命週期狀態散落、無 watchdog |
| 「我有沒有講出去」靠 bool 猜 | — | TTS 無 request id / ack |
| TTS 杜撰未感測世界（下雨/看到杯子）| persona 反幻覺 prompt | LLM 拿不到結構化 world state、無 guardrail 強制 |

**結論**：v1 的 callback 直接搶 actuator，沒有「先標準化事件 → 中央仲裁 → 守則過濾
→ 執行」的分層。每加一個功能就多一條 if/else 和一個 enable flag。

---

## 2. Brain v2 目標架構（5 層，對齊 HRI 文獻的分層仲裁）

```
 感測事件 (face/object/pose/gesture/speech/nav_safety)
   │
   ▼  ① Perception Event Router
        - 把各 topic 的 raw JSON 標準化成 typed PerceptionEvent
        - 去抖 / 去重 / 信心門檻 / stable-frame（目前散在各 node，集中化）
   │
   ▼  ② Interaction State Machine（核心，解「搶同一條 TTS」）
        - demo phase / 對話狀態 / pending confirm / active skill 單一真相源
        - 事件 → candidate intent（不直接執行）
   │
   ▼  ③ Policy / Guardrail Layer（啟發自 NeMo Guardrails）
        - 優先序：safety > explicit user input > face greet > object remark > gesture
        - 能不能講 / 要不要確認 / 禁止行為（backflip 等）
        - 「只用已驗證能力、不可靠能力只顯示不宣稱」硬編成規則
   │
   ▼  ④ Skill Executor（只執行不思考 = 現 interaction_executive）
        - SAY / MOTION / NAV，單一 actuator 出口
        - TTS request_id + ack/terminal event（取代 bool 猜）
        - NAV 安全 envelope（今天的 fail-closed gate 留用）
   │
   ▼  ⑤ Trace / Evidence
        - 每句話 / 每動作都能回溯「哪個 sensor / event / rule 觸發」
        - Studio trace + baseline evidence 直接吃這層
```

**與現況對應**：④ 已存在（`interaction_executive_node`，是好的，不動）。
②③ 是新的——把現在散在 `brain_node.py` 的 callback gate 收斂進來。①⑤ 部分存在
（event_builder / conversation_trace），需強化。

**遷移策略（增量、可降級）**：
- Phase 0：抽 PerceptionEvent dataclass + Router（不改行為，只標準化輸入）。
- Phase 1：把今天的 `demo_phase` 升級成真正的 InteractionStateMachine（②）。
- Phase 2：抽 Policy Layer（③），把所有 `*_enabled` flag 收斂成一張 priority/policy 表。
- Phase 3：TTS request_id + ack（④ 強化）。
- 每 phase 都有 v1 fallback flag，221+ IE 測試 + 345 brain 測試當回歸網。

**明確不做**：不換掉 ROS2 / 不換掉 interaction_executive 出口 / 不把 LLM 直接接
actuator / 不引入 OpenClaw 當 runtime。

---

## 3. 為什麼要 CLI v2

v1 `pawai_cli`（Click）已可用（doctor/status/deploy/demo/logs），但：
- 操作工具，**不是狗的安全 runtime** → 可以比 Brain 早重構、風險低。
- 老師/同學電腦要能裝（目前需 clone repo + WSL）。
- face enroll / object A/B / nav goto / smoke 散在各 script，沒收進 CLI。

## 4. CLI v2 目標（Typer + Rich + pipx）

```
pawai demo   start | stop | status
pawai face   enroll | list | delete | rebuild | test      # 6/15 帶去學校加臉用
pawai object test --model yolo26s --class cup --distance 1.0   # 接今天的 model A/B
pawai nav    goto --distance 0.5                          # 接 nav_executor（HITL 後）
pawai smoke  vision | nav | full                          # 接今天的 under_load_probe
pawai doctor                                              # Jetson/Go2/網路健檢
```

- **Typer + Rich**：漂亮表格 / 進度 / 錯誤訊息（取代現在 Click 的純文字）。
- **pipx 安裝**：`pipx install pawai-cli` → 老師電腦免 clone。
- **保留** v1 的 lock 語意（`-y` ≠ `--force`）、CRLF 防線、IP 解析優先序、
  platform exit 10（這些是 5/14 硬化過的，不可退化）。

## 5. 風險與邊界
- Brain v2 是**大重構**，必須在 demo 後、且有完整測試回歸網才動。
- CLI v2 風險低，但 `pawai nav goto` / `pawai object test` 會動硬體 → 一律
  default-off + 明確 confirm + 沿用 NAV fail-closed envelope。
- 外部框架（OpenClaw/NeMo/ROSClaw/GR00T）：**研究啟發用**，逐一評估，
  不在本 PRD 落地範圍。

## 6. 待 Roy 決策
1. Brain v2 四層 Phase 0-3 的順序與範圍認可？
2. CLI v2 是否優先於 Brain v2（你早上傾向 CLI 可先做）？
3. 哪些外部框架值得開獨立研究案（NeMo Guardrails 看來最對 ③ Policy 層）？
