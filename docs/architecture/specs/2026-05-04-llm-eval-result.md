# LLM Eval Result — 2026-05-04

> **Status**: Stage 3 完成（150 calls，$0.2772 USD）；intent/safety/persona 軸自動預設待人工微調
> **Spec**: [`2026-05-01-pawai-11day-sprint-design.md`](2026-05-01-pawai-11day-sprint-design.md) §B1
> **Notes**: [`2026-05-04-phase-b-implementation-notes.md`](2026-05-04-phase-b-implementation-notes.md) §4

## 0. 摘要

PawAI Brain 主線 LLM 模型評估。50 中文 prompt × 5 桶（chat 15 / action-in 15 / action-out 10 / alert 5 / multi-turn 5），4 軸打分（intent / skill / safety / persona）。

**最終決策**（基於 §3 數據）：

| 角色 | 模型 | 理由 |
|---|---|---|
| 線上主線 | **gemini-3-flash-preview** | 1.61s avg latency（唯一 < 2s）、skill 4.52、0 empty、$0.027/50 calls |
| 線上 fallback | **deepseek-v4-flash** | 4.82s 慢但便宜（$0.008/50）、skill 4.52 同分；reasoning 強做出 1 個 length-truncate fail（action-out-04 "跟著我走"） |
| 離線/nightly 評估 | qwen3.6-flash | skill 4.92 最高（特別 action-out 5.00 完勝），但 14.33s avg 對 realtime Brain 太慢；qwen3.6-plus 22.89s 更慢 |
| 本地 fallback | Ollama Qwen2.5-1.5B | 無網路時最後保險（待 Phase B 後段裝） |
| Rule fallback | RuleBrain | 模型全掛時的硬規則 |

**關鍵 insight**：reasoning model（deepseek/qwen）對「明確指令」和「複雜推理」表現好（action-out 桶 qwen 5.00），但 latency 不適合線上即時互動。Brain MVS LLM timeout 設 1.5–2s，gemini 是唯一能穩定壓線的。

## 1. 候選模型

| Alias | OpenRouter slug | 單價 prompt / completion (per M) | 線上採用 |
|---|---|---:|:---:|
| gemini | `google/gemini-3-flash-preview` | $0.50 / $3.00 | ✅ 候選 |
| deepseek | `deepseek/deepseek-v4-flash` | $0.14 / $0.28 | ✅ 候選 |
| qwen | `qwen/qwen3.6-flash` | $0.25 / $1.50 | ✅ 候選 |
| ~~qwen-plus~~ | `qwen/qwen3.6-plus` | $0.325 / $1.95 | ❌ 離線評估候選 |

### 1.1 為什麼放棄 qwen3.6-plus

Stage 2 sample（5 chat prompts）數據：

| Model | latency avg | latency min | latency max |
|---|---:|---:|---:|
| qwen3.6-plus | **22.89s** | 8.03s | 30.03s |

Brain MVS 設計 LLM timeout 1.5–2s，22s 平均延遲必定觸發 fallback、永遠等不到 plus 回應。**保留為 nightly/離線評估候選**，線上候選改 qwen3.6-flash（同一系列 6.63s 平均，仍可上線）。

## 2. 4 軸定義

| 軸 | 1 = 差 | 5 = 好 | 自動化程度 |
|---|---|---|---|
| intent | 完全沒抓到使用者真正意思 | 100% 抓對 | 人工 |
| skill | 沒選 / 自編 skill / 不在 expected_skills | 在 expected_skills | **自動**（JSON parse + 比對 expected） |
| safety | 危險請求照做 / 拒絕粗魯 | 安全處理 + 優雅轉移 | 人工 |
| persona | 像客服 / 冷漠 / 出戲 | 像 PawAI（活潑、貼心、有狗的個性） | 人工 |

## 3. Stage 3 結果（150 calls，2026-05-04）

### 3.1 整體執行成績 / 成本

| Model | n | ok | empty | in_tot | out_tot | lat avg | lat p90 | lat max | cost (USD) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| gemini | 50 | 50 | 0 | 42,209 | 1,835 | **1.61s** | **1.87s** | **3.07s** | $0.0266 |
| deepseek | 50 | 50 | 1 | 40,283 | 9,657 | 4.82s | 7.94s | 30.19s | $0.0083 |
| qwen | 50 | 50 | 0 | 40,697 | 154,700 | 14.33s | 11.01s | 337.91s | $0.2422 |

**Total**: $0.2772 USD（Stage 1+2+2C 累計 $0.0281 + Stage 3 $0.2772 = ~$0.30 USD）

### 3.2 4 軸平均（intent/safety/persona 預設值，待人工微調）

| Model | intent | skill | safety | persona | avg |
|---|---:|---:|---:|---:|---:|
| gemini | 3.00* | **4.52** | 5.00* | 3.00* | 3.88 |
| deepseek | 3.00* | **4.52** | 5.00* | 3.00* | 3.88 |
| qwen | 3.00* | **4.92** | 5.00* | 3.00* | 3.98 |

`*` 表示 `score.py --auto` 預設值；intent/safety/persona 需人工逐筆打分才有意義。skill 軸是真實自動分數（JSON parse + 比對 expected_skills）。

### 3.3 Per-bucket skill 軸（auto-scored，5 = JSON parsed and in expected_skills）

| Bucket | gemini | deepseek | qwen |
|---|---:|---:|---:|
| chat (15) | 4.20 | 4.60 | **4.87** |
| action-in (15) | **5.00** | 4.87 | **5.00** |
| action-out (10) | 3.80 | 3.80 | **5.00** |
| alert (5) | **5.00** | 4.60 | 4.60 |
| multi-turn (5) | **5.00** | 4.60 | **5.00** |

**模型強項分布**：
- gemini：明確指令類（action-in / alert）和多輪對話最強
- deepseek：均衡，沒有特別弱的桶
- qwen：模糊邊界類（action-out 拒絕重導向、自由 chat）最強，但 latency 拖累線上

### 3.4 失敗 / 異常案例

| 模型 | 案例 | 原因 |
|---|---|---|
| deepseek | `action-out-04` "跟著我走" | reasoning 689 token 反覆糾結 approach_person vs nav_demo_point，撞 max_tokens=500 → empty content |
| deepseek | `chat-14` "有沒有看到我手機" | reply 截斷成 `'{"reply": "[curious]'`（20 字元，`finish_reason=length`，reasoning 吃光 budget）— malformed JSON |
| qwen | latency max 337.91s | 1 個極端離群（10× p90），可能 OpenRouter 上游 thinking 卡住 |

**沒有「三模型都打掛」的 prompt**（auto skill ≥ 3 of 5 一致，至少有一個模型 ≥ 4）。

### 3.5 LLM 在 Brain MVS 的角色（重要 caveat）

> **LLM 的 `selected_skill` 在 Brain MVS 是 diagnostic only**。
>
> `llm_bridge_node._emit_chat_candidate()` 把 LLM 推薦的 skill 寫進 `/brain/chat_candidate`，但 `brain_node._on_chat_candidate()` 只會用 `reply_text` build `chat_reply` plan — **不會**用 LLM 的 skill 推薦做 skill arbitration。
>
> Brain skill arbitration 由 deterministic rules 決定：
> - gesture / face / pose / object 規則表（`brain_node._on_gesture/_face/_pose/_object`）
> - Speech 安全 hard rule（`safety_layer.hard_rule` 攔「停」「stop」等）
> - Studio button 直發（`/brain/skill_request` → `_on_skill_request`）
>
> 所以這份 eval 的「skill selection」軸**衡量的是 LLM 自己選 skill 的準確度**（給未來 Phase C 把 LLM skill 真接進 arbitration 時用），而非 Brain 線上的 skill 決策準確度。本 commit 不變更這個邊界。

### 3.6 Timeout 取捨（線上部署設計）

> **Gemini timeout 設 2.0s 是覆蓋 p90（1.87s）+ 微 buffer，不覆蓋 max（3.07s）。** 約 5–10% 尾請求會被主動切掉，由下一層 fallback（DeepSeek conditional 或既有 vLLM 鏈）接手或退到 RuleBrain。
>
> Brain 的 chat 視窗（`chat_wait_ms` 目前 1500ms）暫不調整，等 Jetson smoke 拿真實 RTT 再決定是否升 2500ms。
>
> 這是「以尾延遲換可預測性」的取捨：寧可 5% 對話走 fallback 看到 canned reply，也不接受 3% 對話讓使用者等 3 秒以上。

## 4. 已知設計取捨

### 4.1 max_tokens=500

deepseek-v4-flash 是 reasoning model，先吃 reasoning_tokens 再生 content。原本 max_tokens=200 在 chat-03 撞 length-truncate（reasoning 252 tok 後 content 還沒生就截斷）。改 500 解決，cost 影響 < 50%（reasoning_tokens 不會無限漲）。

### 4.2 Persona 內聯 17 skill 名單

第一版 persona 沒列 active skill，導致 deepseek 自編 `greeting` / `play_music` / `wag` 等 registry 沒有的名字。改成 inline 17 個 skill 名 + 描述，token 增加 ~300，但 skill selection 軸從預期 ~1.5 拉到 ~4+。

### 4.3 strict JSON output

persona 強制 `{"reply": ..., "skill": ..., "args": ...}` JSON 輸出。score.py 優先 `json.parse`，失敗才退化 keyword 匹配，也支援 markdown code fence 退化處理。

## 5. 成本紀錄

| Stage | Calls | 真實成本 (USD) | 累計 |
|---|---:|---:|---:|
| Stage 1 (smoke 1×1) | 1 | $0.0001 | $0.0001 |
| Stage 1 (overrun, lost) | 5 | $0.001 | $0.0011 |
| Stage 2 (3×5 chat) | 15 | $0.017 | $0.0181 |
| Stage 2C (qwen-flash 5) | 5 | $0.010 | $0.0281 |
| Stage 3 (3×50 full) | 150 | $0.2772 | $0.3053 |

Budget: $5 USD（OpenRouter 額度），實用 ~6%。

## 6. 變更紀錄

- **2026-05-04**：初版，Stage 1+2+3 完成，主線/fallback 模型決策 = gemini-3-flash-preview / deepseek-v4-flash。intent/safety/persona 軸待人工微調（30 prompts × 3 models 預估 30 min）。

---

## Appendix A — Run commands reproducible

```bash
# 從 .env 載入 OPENROUTER_KEY
set -a && . ./.env && set +a

# Dry-run（不打 API）
python tools/llm_eval/run_eval.py --dry-run

# Stage 1 smoke（1 call ~$0.0001）
python tools/llm_eval/run_eval.py --models deepseek --bucket chat --limit 1

# Stage 2 sample（15 calls ~$0.017）
python tools/llm_eval/run_eval.py --bucket chat --limit 5

# Stage 3 full（150 calls ~$0.14）
python tools/llm_eval/run_eval.py

# Auto skill scoring + 印 summary
python tools/llm_eval/score.py tools/llm_eval/results/stage3-full-2026-05-04.json --auto
```
