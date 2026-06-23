# PawAI Brain

> **Scope**：PawAI 互動主線「怎麼理解、決策、說話、呈現」的**架構真相層** — Brain 決策 / Studio / speech / perception(face,gesture,pose,object) / architecture / specs / plans。
> **Status**：active（架構真相層）。本檔**不是**「當前能力 claim」真相 — 任何 brain / 感知能力是否 pass / 可否進 Brain 主線，一律以 canonical claim matrix（見下「Brain 能力 claim」區塊）為準。
> **Owner lane**：brain-studio（搭配各模組 `CLAUDE.md` / `perception/*` 工作規則）。
> **Source-of-truth 優先序**（高→低）：程式碼 / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/`（實測，最新唯一 trusted snapshot，SHA `78fbf36`，readiness=`not_ready`）＞ `docs/mission/2026-06-18-capability-claim-matrix.md`（canonical Capability Claim Matrix）＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B（claim 判決依據）＞ `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`（門檻 / 怎麼量，provisional until baseline）＞ `docs/mission/2026-06-18-demo-north-star.md`（戰略邊界 / 禁說清單）＞ 本檔（架構）＞ `docs/contracts/interaction_contract.md`（topic/action schema, v2.5 凍結）。
> **Maintained child files**：`architecture/README.md`（架構索引）、`architecture/overview.md`（Brain × Studio 整合總覽）、`specs/`、`plans/`、`speech/README.md`、`studio/README.md`、`perception/{face,gesture,pose,object}/`（各帶 `CLAUDE.md`）。
> **Archived / historical 邊界**：`architecture/0511/**` 為 **5/11 freeze-snapshot**（保留作引用，不重複維護）；`docs/archive/2026-05-docs-reorg/superpowers-legacy/` 全 frozen；`research/*.md` 一律 **research-not-truth**（唯一例外：6/05 convergence audit 經指定升格為 evidence-hierarchy #2）。
> **本 README 不是**：能力 claim 真相（→ canonical claim matrix）、門檻定義（→ `specs/2026-06-18-capability-baseline-spec.md`）、操作手冊（→ `docs/runbook/`）、產品劇本（→ `docs/mission/README.md`）。

---

## 一句話

**PawAI Brain 是把多模態感知(face / speech / gesture / pose / object)轉成 SkillPlan 的決策層,LLM 只提建議,Executive 才執行,所有實體動作都過 Safety Gate。**

---

## Brain 能力 claim（引用 canonical，勿在此重複整份）

> **權威**：`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B Capability Claim Matrix（brain 行），基準為 `docs/runbook/baseline-evidence/2026-06-04-hitl/`（最新唯一 trusted snapshot）。下面只是入口摘要 — 細節不在此重複。

- **Current Claim**：Brain 安全層拒絕機制 **存在且單測通過**（`safety_gate.py` 對「停 / 緊急」硬短路繞過 LLM、skill allowlist 擋越權 skill）。
- **Claim Level**：安全層機制 = **CLAIM_WITH_CAVEAT（限機制存在 + 單測層級）**；反幻覺 = **DO_NOT_CLAIM**；`brain.skill_gate` / `brain.trace` = **insufficient_data**（n=0, `brain_allowed=false`）。
- **Evidence-Provenance**：`docs/runbook/baseline-evidence/2026-06-04-hitl/` + 程式碼（`pawai_brain/personas/v1/`、`world_state_builder.py`）。
- **Pass / Degraded / Fail / Insufficient**：安全層 = 機制存在（未做 e2e N 次攔截量測）；反幻覺 = **fail**（6/4 operator 觀察自編下雨 / 看到杯子 / 姿勢）；skill_gate / trace = **insufficient_data**。
- **Fallback / 安全規則**：deterministic safety hard rule + banned_api gate + LLM `selected_skill` diagnostic-only；LLM 掛 → say_canned；Brain 掛 → 單一出口斷掉即真的斷掉。
- **Non-Claims（禁說）**：不得宣稱「Brain 不會幻覺 / 只講真實感測 / 通過反幻覺測試 / persona 自然度已驗證」、不得把 `brain.skill_gate` 講成 pass、不得把網路天氣「外面在下雨」演成真實感知。可宣稱 deterministic safety / allowlist；不講「非幻覺自主 agent」。
- **Model Candidates**：見 `docs/archive/pawai-brain-legacy/research/2026-06-02-model-candidate-registry.md`（research-not-truth；分層 BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH，不預設為實作 backlog）。
- **Next Retest**：安全層 e2e N≥10 危險 / 越權指令 100% 攔截 + 久放後仍生效 + negative case；反幻覺需實作 grounding verifier + 刪幻覺 few-shot + 關 `_get_weather()` 注入。各感知能力（face / object.cup / voice / gesture / pose）分級一律見 canonical claim matrix。

---

## 架構主線（能力是否 pass 一律回 canonical claim matrix）

> 以下是 Brain 的**架構組成**（機制存在性），**不是**能力 pass 宣稱。任何「這條 demo 段落能不能講、屬哪層」一律回 canonical claim matrix + 北極星 §5 禁說清單。6/05 教授會議起採 **scoreboard-first**：先量化能力（pass / degraded / fail / insufficient gate Brain）再決定換不換模型，不把模型研究預設變成實作 backlog。

- **Skill Registry** — 27-entry SkillContract（Active / Hidden / Disabled / Retired + per-entry demo metadata）；OK 二次確認三層原則。機制存在；能力是否上台依 claim matrix。
- **三層決策** — Safety（deterministic hard rule + banned_api gate）→ Policy（rule router + 仲裁）→ Expression（reply / tone / Studio bubble）。安全層 = CLAIM_WITH_CAVEAT（機制存在 + 單測）；反幻覺 = DO_NOT_CLAIM。
- **LLM / TTS provider chain** — cloud 主線 → fallback → 本地 → RuleBrain / Piper（具體 provider 以程式碼 + `speech/README.md` 為準）。模型分層 BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH，見 `research/2026-06-02-model-candidate-registry.md`（research-not-truth）。
- **Conversation Engine** — `pawai_brain` LangGraph stateful graph，`conversation_engine` / `conversation_shadow_engine` feature flag；legacy `llm_bridge_node` 仍可切回（見 `architecture/overview.md` §3.5）。
- **Studio Brain Skill Console** — Brain Status Strip + Trace Drawer + Skill Buttons。Studio evidence 顯示 / provenance 有價值，但**不等於能力 pass**（除非綁 trusted baseline 資料）。`studio.evidence` 6/04 為 insufficient_data。

---

## 文件導覽

> 入口導覽。能力分級回 canonical claim matrix；門檻回 6/18 capability-baseline-spec。

| 檔案 / 路徑 | 內容 |
|---|---|
| **入口頁(本檔)** | `docs/pawai-brain/README.md` |
| **架構索引** | `docs/pawai-brain/architecture/README.md` |
| **架構總覽**(Brain × Studio 整合) | `docs/pawai-brain/architecture/overview.md` |
| **canonical Capability Claim Matrix**（能力分級真相源） | `docs/mission/2026-06-18-capability-claim-matrix.md`（判決來源：6/05 audit §B） |
| **能力門檻 / 怎麼量**（provisional until baseline） | `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md` |
| **戰略邊界 / 禁說清單** | `docs/mission/2026-06-18-demo-north-star.md` |
| **最新實測 trusted snapshot**（能力 pass/fail 最終事實） | `docs/runbook/baseline-evidence/2026-06-04-hitl/` |
| **Phase A Brain MVS spec** | `docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md` |
| **PawClaw evolution spec** | `docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md` |
| **介面契約**（v2.5 凍結） | `docs/contracts/interaction_contract.md` |
| **PawAI Studio 設計** | `docs/pawai-brain/studio/README.md` |

---

## Legacy / Archive

舊版研究、歷史決策、各模組 README 仍在以下原位:
- `docs/archive/pawai-brain-legacy/architecture-0511/` — **5/11 freeze-snapshot**（各 lane 5/11 凍結快照,保留作引用,不重複維護;只在 `architecture/README.md` 註明它是 freeze-snapshot）
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/` — 設計 spec 歷史(4/10 守護犬 / 4/11 home interaction / 4/27 brain MVS / pawclaw evolution / 5/01 sprint),全 frozen
- `docs/pawai-brain/speech/` `docs/pawai-brain/perception/face/` `docs/pawai-brain/perception/gesture/` `docs/pawai-brain/perception/pose/` `docs/pawai-brain/perception/object/` — 各感知模組權威文件(各帶 `CLAUDE.md` 工作規則)
- `docs/pawai-brain/studio/` — Studio 既有設計

本資料夾維護互動主線**架構真相**;舊文件保留作歷史與引用,不重複維護。能力是否 pass 一律回 canonical claim matrix,不在敘事文件重複整份。
