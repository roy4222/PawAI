# PawAI Post-Demo Refactor Master Plan

> 日期：2026-06-10 晚（demo 影片全錄完當天）
> 性質：**總施工圖**——接下來數週重構的目標、原則、已拍板決策、執行順序。
> 不是單一 task plan；可執行細節在五份子 plan（本文 §6 連結）。
> 上游：audit 主報告 [`../specs/2026-06-10-pawai-architecture-audit.md`](../specs/2026-06-10-pawai-architecture-audit.md)
> + findings ledger（99 條，含逐條查證）。
> 決策來源：Roy 2026-06-10 晚 grill-me 訪談逐題拍板（Q1-Q6）。

---

## 1. 目標

> **Demo 影片已完成，6/18 前不再把「可錄影」當最高限制。接下來目標是把 PawAI
> 從 demo 拼裝系統，重構成穩定、可觀測、可擴展的機器狗平台。**（Roy 原話）

四個目標、一個禁令：

1. **穩定**：不改 A 壞 B；每次改動有測試和 rollback；main 永遠可部署。
2. **可觀測**：PawAI 沒反應時，能立刻知道是誰擋掉（face 沒認到？object 沒事件？
   gesture 被 phase 擋？active_plan 卡住？TTS 還在講？nav 被 covariance 擋？）——
   Studio / CLI 都看得到原因。
3. **可擴展**：新增感知 / skill / demo flow 不再到處改 if/else。Brain 從
   「callback 堆 + demo flags」變成「事件路由 + 狀態機 + policy + trace」。
4. **保留安全骨架**：`interaction_executive_node` 唯一 actuator 出口、SafetyLayer、
   SkillContract、PendingConfirm、StopMove 路由、twist_mux 優先序——**不推倒**。
   真正要拆的是 Brain 內部仲裁、CLI 操作工具、Studio 證據中心。
5. **禁令：不做一次性大爆炸重寫**。像工程施工一層一層換，不直接拆承重牆。

## 2. Baseline（已完成）

| 項目 | 狀態 |
|---|---|
| Demo 影片 S1-S5 | ✅ 全錄完 |
| Plan 0 baseline cleanup | ✅ 完成（working tree 乾淨、demo 修法本就分主題 commit）|
| 四套測試 | ✅ IE 258 / vision 138 / object 41（含修復的 12 色 stale test）/ Studio tsc 0 error |
| Tag | ✅ `post-demo-refactor-baseline-2026-06-10`（= `b1f0bc4`，已 push）|
| 回滾點 | `git checkout post-demo-refactor-baseline-2026-06-10`；demo 凍結文件 `docs/pawai-demo/2026-06-10-demo-snapshot.md` |
| POST_DEMO_ONLY | ✅ 解鎖（audit 47 條可開工；SAFE 32 條本來就能動）|

到 6/18 前仍保留的退路紀律：main 不長期紅；`executive.yaml` 與 demo 啟動參數
（`scripts/start_full_demo_tmux.sh` overrides）非經明確測試不翻動。

## 3. 重構原則（每份子 plan 都繼承）

1. main 永遠可部署；一切走 PR + CI 綠才 merge。
2. 每刀要小、可 rollback（feature flag / shim / revert 單 PR）。
3. **搬家和行為變更分開**：純搬移 PR 零行為 diff；行為修正疊在搬家之後。
4. Trace additive-only：儀表化不夾帶 gating 變更。
5. contracts 先只搬資料、不搬邏輯。
6. 硬體/能力宣稱必須過 HITL gate；`docs/pawai-demo/2026-06-10-demo-snapshot.md`
   的 forbidden claims 對所有對外材料持續有效。
7. 觀測類（訊息/顯示）與政策類（閘值/行為）永不同 PR。
8. Codex 串行實作、Fable 寫 spec/review、WritingPlan 是中間合約、HITL 是真實驗收。

## 4. 已拍板決策（2026-06-10 晚，Roy 逐題確認）

| # | 決策 |
|---|---|
| D1 | POST_DEMO_ONLY 解鎖；不等 6/18；但 main 可部署紀律 + demo 參數不亂翻保留到 6/18 |
| D2 | **CI 先行**，兩層：Tier 1 = Brain/Studio/CLI（IE、pawai_brain 補檔、Studio gateway pytest、pawai_cli）；Tier 2 = object/vision 補檔/nav_capability/go2_robot_sdk。三入口 = PR gate（Actions）+ pre-commit（path-triggered，<10s）+ runtime gate（healthcheck/smoke）|
| D3 | CLI v2 切 4 刀；第 1 刀 = deploy sync 安全 + demo start healthcheck **hard-block**（`--skip-healthcheck` 逃生口、大字警告）+ status 真實性升級。`~/sync` 降級顯式 opt-in（不刪）；`demo school` 歸檔拆 helper |
| D4 | **pawai_contracts 開工**。正式推翻兩條舊規（「zh 表三份拷貝是故意的」、「pawai_brain 不依賴 IE」）。新規則：**IE 與 pawai_brain 不互相依賴，共同依賴 pawai_contracts**。v1 嚴格 data-only + shim + parity tests + 零行為變更；ROS-free（不准 import rclpy / IE / pawai_brain）|
| D5 | **Trace 邊界**：schema 屬 pawai_contracts；發射屬 Brain/IE/conversation_graph（每個 gate early-return 必發 suppressed，含 gate/reason/demo_phase/active_plan/pending_confirm/cooldown remaining/source summary）；落盤與呈現屬 Studio gateway（`runtime/traces/{session_id}.jsonl`，CLI 只讀同一份）。**「Trace 的單一真相是 pawai_contracts schema + gateway JSONL。Brain 只負責說明自己為什麼做/不做；Studio 只負責記錄與呈現；CLI 只負責讀取與匯出，不再發明第三套 trace。」** Trace v1 additive-only；無 gateway 即無落盤（接受）；retention 每檔 ~20MB、留 20 sessions、`evidence_pull.sh` 拉回後可清 |
| D6 | **ISM 詳細 plan 延後**：等 Router golden fixtures + Trace 真實紀錄落地後才寫；現在只凍結設計約束（§7）|

## 5. 工作流順序

```
（已完成）Plan 0 baseline → tag
今天起：
  Plan A  CI/CD Guardrails        ← Codex 第 1 批（純 workflow/hook，保護後面所有刀）
  Plan B  CLI v2 First Slice      ← 第 2 批（deploy 安全 / healthcheck 閘 / status）
  Plan C  pawai_contracts 抽取    ← 第 3 批（Brain v2 地基，零行為）
  Plan D  Brain Router Phase 0    ← 第 4 批（解析抽出，golden fixtures）
  Plan E  Brain Trace v1          ← 第 5 批（可與 D 並行 review；先儀表化舊路徑）
之後（各等前置落地）：
  ISM 詳細 plan（等 D+E）→ Brain v2 Phase 1/2
  Studio Evidence Center 詳細 plan（等 E 的 schema）
  CLI 第 2-4 刀（新命令 Typer Phase A / error registry / packaging）
  Dead code 歸檔批次（等 CI Tier 2 蓋住對應套件）
  Object A/B、pose observer、nav 研究線（獨立 HITL session，量測不承諾）
```

## 6. 第一批五份 implementation plans

| Plan | 文件 | 一句話 |
|---|---|---|
| A | [`2026-06-10-plan-a-ci-guardrails.md`](2026-06-10-plan-a-ci-guardrails.md) | CI 兩層擴張 + pre-commit path-triggered + ros2-test-suite 同步；只動 workflow/hook，零 runtime |
| B | [`2026-06-10-plan-b-cli-v2-first-slice.md`](2026-06-10-plan-b-cli-v2-first-slice.md) | deploy 不再可能刪 `.env`；demo start 不再假成功；status 看得到 gateway 與各模組 |
| C | [`2026-06-10-plan-c-pawai-contracts-extraction.md`](2026-06-10-plan-c-pawai-contracts-extraction.md) | 共用真相搬進 ROS-free 新套件；shim 保舊 import；606 測試零改動全綠 |
| D | [`2026-06-10-plan-d-brain-router-phase0.md`](2026-06-10-plan-d-brain-router-phase0.md) | 五個感知 callback 的解析抽成 PerceptionEvent；golden fixture 證明 proposal 不變 |
| E | [`2026-06-10-plan-e-brain-trace-v1.md`](2026-06-10-plan-e-brain-trace-v1.md) | 每個 gate 早退發 suppressed trace；`/brain/trace` 上線；回答「為什麼沒反應」|

執行模式：**Codex 一次一個 plan、一個 plan 內依 task 順序、每 task 一個 commit、
每 plan 一個 PR**（Plan A 例外：每個 CI suite 獨立 PR，附 Actions log 證明新
invocation 真的跑且測試數 > 0）。Fable review 每個 PR；CI 綠 + review 過 → merge。

## 7. ISM 設計約束（只凍結原則，不是可執行任務）

等 Router（golden fixtures）+ Trace（真實事件節奏紀錄）落地後，詳細 plan 才開寫。
屆時必須遵守：

1. **感知事件永遠不能直接改狀態**——只能產生候選 intent，由 policy 對照當前狀態裁決。
2. 優先序鐵律：**safety > explicit command > confirm flow > 自發社交 proposal**。
3. 每個 active interaction 必須有 **watchdog**（吸收 6/9「stranger plan 卡死全系統」
   教訓；參考 IE nav_step_timeout 模式；SkillContract.timeout_s 已存在但 brain 側未用）。
4. **pending confirm 不能吃掉全部感知**——confirm 在飛時其他事件要 queue 或
   suppressed-with-trace，不准黑洞。
5. TTS ack（utterance_id + terminal event）最終要納入，取代 Bool 猜測。
6. demo_phase 未來是 **operator scene mask**（latched topic、操作員工具發布、
   policy 表消費、每次變更本身是 trace 事件），不是硬編 demo flag。
7. 狀態草案（可被 trace 數據修正）：IDLE / LISTENING / SPEAKING / CONFIRM_PENDING /
   EXECUTING / ALERT_ACTIVE / SAFETY_HOLD；轉移來源只有四種：skill_result 生命週期、
   confirm 結果、TTS ack、操作員指令。
8. 上線必須帶 `ism_enabled` flag + v1 fallback；test_brain_rules 73 條 + 6/9 場景
   重演測試（ALERT 卡住 → cup/greet 被 queue/suppressed-with-trace 而非黑洞）是驗收網。

## 8. 暫不做（明確出界）

- Brain ISM 詳細實作（等 D+E）
- Studio Evidence Center 詳細實作（等 E schema；落盤/export/panel 屬於它）
- D435+LiDAR costmap fusion（research spec 先行，禁宣稱）
- Object 模型大換血（A/B 是量測任務，鎖定條件 cup ≥1m 5/5 + ≥4Hz + 溫度正常）
- Nav patrol / dynamic detour / approach-person
- Speech 大重構（tts_node 拆解、llm_bridge 退役、utterance 所有權收斂 = Wave 3+）
- 任何 `executive.yaml` / demo 啟動參數翻動（6/18 前）

## 9. 殘留待 Roy 決策（不擋第一批，遇到再拍）

1. **Dead code 歸檔原則**（建議：scripts → `scripts/archive/`；套件內模組 → 直接
   git 刪除（git history 即歸檔），一套件一 PR、附 zero-consumer grep 證據；
   **不放 `docs/archive/`**——docs 樹不收 code）。
2. **HITL 證據治理**：新開 `docs/hitl/`（動 docs-convention 需你核）+ raw artifacts
   進 git 粒度（建議：≤1MB 的 CSV/JSONL 進 `benchmarks/results/raw/`，影音/大檔不進）。
3. **S1 簿記**：S1 最後用哪個方案錄成（A 0.5m / C initialpose / 遙控輔助）？
   決定 nav capability ladder 上 operator-confirm 迴圈標 HARDWARE_PROVEN 還是
   WIRED_RUNTIME——影響 6/18 簡報能講的話。
4. Studio operator mode enforcement 強度（token / 第二 port / 信任內網）——
   Evidence Center plan 寫作時要用。
5. Ollama 本地 LLM 層去留（主線收編 / 留 legacy / 放棄離線智能）。
6. Object A/B 與 pose observer 的第一場 HITL session 排期。
7. Stop-resume 終局（operator-confirm 永久化 vs resume_policy=auto 留大場地）+
   安全層投資方向（強化自製 reactive_stop vs nav2_collision_monitor 遷移）。
