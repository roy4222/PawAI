# Runbook — Demo 救火 SOP + Ops

> **Scope**：Demo 現場救火 SOP + 環境/ops + demo-safe 啟動腳本索引。每份檔都應該能在 5 分鐘內讓人診斷或修復一類問題。
> **Status**：active（ops 真相層）。
> **Owner lane**：ops / runbook。
> **Source-of-truth 優先序**：本資料夾是**操作 SOP**真相，**不是能力 pass/fail 真相**。能力是否 pass 一律以 `docs/runbook/baseline-evidence/2026-06-04-hitl/`（最新唯一 trusted snapshot）+ canonical claim matrix（`docs/pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`）為準。
> **Maintained child files**：見下方索引。`baseline-evidence/` 是 **read-only 證據資料**（不在本 README 維護範圍，只被引用）。
> **本 README 不是**：能力 claim 真相（→ baseline-evidence + canonical matrix）、架構真相（→ 各 lane README）、門檻定義（→ `docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`）。

---

## 6/18 baseline / HITL runbook（capability 量測）

| 檔案 | 場景 | 何時打開 |
|------|------|---------|
| [2026-06-18-hitl-oneshot-runbook.md](2026-06-18-hitl-oneshot-runbook.md) | **最安全 operator runbook**（一次坐定跑 baseline，誠實 + 安全護欄、nav = 純 DRY-RUN） | Roy 回到 Jetson+Go2 要實跑 capability baseline 時 |
| [2026-06-18-baseline-runbook.md](2026-06-18-baseline-runbook.md) | baseline 量測流程（JSONL / snapshot / freeze；含 `/event/nav/mission` doc-bug 註記） | 看「怎麼量、存哪、怎麼 freeze」 |
| `baseline-evidence/`（read-only 證據） | 實測 snapshot + raw jsonl + manifest + readiness | 查能力 pass/fail 的最終事實（`2026-06-04-hitl/` = 當前唯一 trusted；`2026-06-03-first-trusted-face/` 已被取代、historical） |
| [2026-06-03-first-trusted-baseline-evidence.md](2026-06-03-first-trusted-baseline-evidence.md) | 🕰️ historical 里程碑（6/3 第一次可信量測，face=fail） | 引用 6/3 里程碑（**不可當作當前 face 狀態**） |

---

## 救火檔索引

| 檔案 | 場景 | 何時打開 |
|------|------|---------|
| [jetson.md](jetson.md) | Jetson Orin Nano 8GB 環境 | ROS2 / CUDA / 環境變數 / 套件路徑問題 |
| [network.md](network.md) | 網路排查 | Go2 / Jetson / GPU server / 開發機之間連線異常 |
| [gpu-server.md](gpu-server.md) | RTX 8000 GPU server 連線 | 雲端 LLM / ASR 不通、SSH tunnel 異常 |
| [go2-operation.md](go2-operation.md) | Go2 基礎動作操作 | 動作 ID 速查、WebRTC 命令格式、緊急停止 |
| [demo_script.md](demo_script.md) · [demo-fallback-script.md](demo-fallback-script.md) · [demo-30-case-checklist.md](demo-30-case-checklist.md) | Demo 展示腳本 / fallback / 檢核 | demo 當天展示流程與備援 |

---

## Demo 啟動腳本（不在 runbook，列在這裡方便查）

```bash
# 主流程
bash scripts/start_llm_e2e_tmux.sh             # 語音 + LLM 主線
bash scripts/start_nav_capability_demo_tmux.sh # nav_capability 平台層 demo
bash scripts/start_face_identity_tmux.sh       # 人臉辨識
bash scripts/start_full_demo_tmux.sh           # 四功能整合（demo 主線）

# 環境清理
bash scripts/clean_full_demo.sh                # 清 demo 全環境
bash scripts/clean_speech_env.sh               # 只清語音
bash scripts/clean_face_env.sh --all           # 人臉
```

詳見 [`/CLAUDE.md`](../../CLAUDE.md) §「建構與執行」。
