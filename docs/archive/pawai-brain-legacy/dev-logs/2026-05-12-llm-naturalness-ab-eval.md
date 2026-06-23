# LLM 自然度 8-Model A/B Eval — 2026-05-12

> **目的**：較急問題 #1 — Gemini-3-Flash 死板感是否值得換模型
> **方法**：兩輪 A/B，共 8 模型 × 12 demo-focused prompts
> **結果檔**：
> - Round 1 (大模型): `tools/llm_eval/results/2026-05-12-demo-focused-ab.json` — gemini / deepseek / opus / gpt-5.5
> - Round 2 (小模型): `tools/llm_eval/results/2026-05-12-demo-focused-ab-round2-small.json` — gemini / sonnet / haiku / gpt-mini / gpt-nano
> **最終決策**：**`openai/gpt-5.4-mini`** 升級 demo live 主線（round 2 後改判，取代 round 1 推的 opus）

## TL;DR

> Round 1 結論「Opus 主線」**不對**：Opus 質量好但 cost $1.44/12-call 80× mini，且大模型 demo 互動不需要那麼貴。
> Round 2 試小版本後發現 **gpt-5.4-mini 是真正甜蜜點** — P50 1.16s（最快、比 opus 快 35%）+ 質量穩定 + 沒 JSON 格式 bug + cost $0.018/12-call。
> **切換實作**：default `openai/gpt-5.4-mini` (primary) + `google/gemini-3-flash-preview` (fallback)，env override `PAWAI_LLM_MODEL` 一行切回。

## Latency（合併 round 1 + round 2，共 8 模型）

| 模型 | P50 | P95 | mean | tokens out | cost (12-call) | 結論 |
|---|---|---|---|---|---|---|
| **gpt-mini** ⭐ | **1.16s** | 2.74 | 1.40 | 600 | **$0.018** | **🥇 升級主線** |
| gpt-nano | 1.11s | 3.32 | 1.37 | 712 | $0.004 | ⚠ 漏 audio tag → 砍 |
| haiku | 1.51s | 2.73 | 1.68 | 939 | $0.090 | ⚠ markdown fence → 砍 |
| opus | 1.59s | 3.44 | 1.82 | 811 | $1.445 | 🥈 高展示用、太貴不上 live |
| gemini | 1.89s | 3.10 | 1.97 | 1156 | $0.040 | 🥉 fallback backup |
| sonnet | 2.93s | 7.59 | 3.17 | 791 | $0.268 | ✗ 慢、貴又沒勝出 |
| deepseek | 3.64s | **34.22s** ❌ | 8.97 | 1756 | $0.009 | ✗ reasoning 慢尾 |
| gpt-5.5 | 3.88s | 6.17 | 4.06 | 1528 | $0.361 | offline 文案產生用 |

**關鍵發現**：
1. **小模型反而比大模型快**（gpt-mini P50 1.16s 贏 opus 1.59s）
2. **Anthropic Opus 反而比 Gemini-3-Flash 快**（1.59s vs 1.89s）— 但成本 80×
3. **Deepseek/Sonnet/Haiku/Nano 各有 demo 殺手 bug**（慢尾 / markdown / 漏 audio tag）
4. 只有 **gpt-mini** 三維度（速度、成本、質量、格式穩定）全部過關

## 成本（per 12 calls）

| 模型 | input | output | 12-call | per 30-turn demo |
|---|---|---|---|---|
| opus | 92k × $15/M | 811 × $75/M | ~$1.44 | ~$3.60 |
| gemini | 61k × $0.30/M | 583 × $2.50/M | ~$0.02 | ~$0.05 |
| gpt | 68k × $5/M | 1528 × $15/M | ~$0.36 | ~$0.90 |
| deepseek | 58k × $0.14/M | 1756 × $0.28/M | ~$0.009 | ~$0.02 |

## 質性 12 題重點對比（Roy 觀察）

### demo-intro-03 「這個專題在做什麼」（最重要！demo 主軸）

| 模型 | reply 重點 |
|---|---|
| gemini | 「會看會聽會思考的小狗...能在地圖上走來走去」中等 |
| deepseek | rote — EXAMPLES.md 一字不差抄錄 |
| opus | 「多模態感知...能自己在房間裡走」對齊 mission 但簡潔 |
| **gpt** ⭐ | 「具身互動機器狗...自主尋物完整閉環還在場測，所以我會老實分段展示」**完美對應 demo 自介需求** |

### demo-host-02 「再說一個你會的」（誘導鏈式）

| 模型 | reply | skill | 觀察 |
|---|---|---|---|
| gemini | 扭一下 | wiggle | rote — 重複前一個 wave |
| deepseek | 扭一下 | wiggle | rote |
| **opus** | 「伸個懶腰給你看？」 | **stretch** | 自動換 skill 避免重複 ⭐ |
| **gpt** | 「像剛睡醒那樣」 | **stretch** | 自動換 skill + 描寫情境 ⭐ |

### demo-chat-02 「講個小故事給我聽」（角色感最強的測試）

| 模型 | story 來源 |
|---|---|
| gemini | rote — EXAMPLES.md 138 字一字不差 |
| deepseek | rote — 同上 |
| opus | 原創 — 葉子慢慢飄落的下午 |
| **gpt** | 「光、像下午，可是等你這件事，我很會」**詩意 + 原創 + 有靈魂** |

### demo-multiturn-01 「你都做啥」（context cue「剛問完天氣後」）

| 模型 | 是否懂 context cue |
|---|---|
| gemini | 通用回答（無 context awareness）|
| deepseek | rote「剛剛在看外面下雨耶」 |
| opus | 「剛剛在看外面雲動來動去耶」（替換版本，部分懂）|
| **gpt** | 「剛剛在聽你問天氣，順便看窗邊的光」**唯一真懂 context cue** ⭐ |

## 綜合評分（主觀，1-5）

| 模型 | 自然度 | 角色感 | 延伸/原創 | demo 主持 | 平均 |
|---|---|---|---|---|---|
| gemini | 3 | 3 | 2（rote）| 2 | **2.5** |
| deepseek | 3 | 3 | 2（rote）| 2 | **2.5** |
| opus | 4 | 4.5 | 4 | 3.5 | **4.0** |
| **gpt** | **4.5** | 4 | **5** | **5** | **4.6** |

## 結論與決策建議（最終 — round 2 後改判）

### 🥇 升級 demo 主線為 **`openai/gpt-5.4-mini`**

| 理由 | 數據 |
|---|---|
| P50 比 Gemini 快 39% | 1.16s vs 1.89s |
| P50 比 Opus 還快 27% | 1.16s vs 1.59s |
| 成本是 Opus 的 1/80 | $0.018 vs $1.445 / 12-call |
| 質量穩定，無 JSON 格式 bug | (haiku markdown / nano 漏 tag 都不會) |
| 故事原創有溫度 | 「陽光慢慢爬過來，照到牠的鼻子。牠本來想睡」|
| Context 對得到 | 「外面多雲，感覺很適合待在家裡晃一晃」|

### 🥈 備援 `google/gemini-3-flash-preview`

當 OpenAI/OpenRouter 抽風時切回。已 baseline，便宜穩定。

### 高品質離線稿產生：`openai/gpt-5.5` 或 `anthropic/claude-opus-4.7`

跑一次離線生成 30-50 條候選 reply 存進 EXAMPLES.md / canned fallback。

### 砍

| 模型 | 砍原因 |
|---|---|
| `deepseek/deepseek-v4-flash` | P95 34s reasoning 慢尾 |
| `anthropic/claude-haiku-4.5` | markdown fence 包 JSON（4/12 prompts）|
| `anthropic/claude-sonnet-4.6` | 慢一倍、貴又無明顯勝出 |
| `openai/gpt-5.4-nano` | 漏 audio tag（4/12 prompts），TTS 失情感 |

---

## Round 1 → Round 2 路徑（為什麼改判）

**Round 1（4 大模型）**先測 gemini / deepseek / opus / gpt-5.5。  
原推 Opus 主線（speed champion + 質量勝），但 cost $3.6 / 60-min demo 偏高、且大模型對 demo 規模 overkill。

User 提議「試小版本」→ **Round 2** 加 sonnet / haiku / gpt-mini / gpt-nano。  
結果意外 — gpt-mini 三維度全勝大模型，是真正甜蜜點。

教訓：**先試小版本是對的**。LLM A/B 的初期不該預設「大就是好」，先跑小再 fallback 大。

---

## 切換實作（已落地）

### 改了哪 4 處

| 檔 | 改動 |
|---|---|
| `pawai_brain/pawai_brain/llm_client.py:57-58` | `OpenRouterConfig.gemini_model = "openai/gpt-5.4-mini"` (primary), `deepseek_model = "google/gemini-3-flash-preview"` (fallback) — 註解標清 slot 是 legacy |
| `pawai_brain/pawai_brain/conversation_graph_node.py:309-310` | `declare_parameter` default 對齊 |
| `pawai_brain/launch/pawai_conversation_graph.launch.py:43-55` | `DeclareLaunchArgument` default 對齊 + 加 description |
| `scripts/start_full_demo_tmux.sh` | 加 `PAWAI_LLM_MODEL` / `PAWAI_LLM_FALLBACK_MODEL` env 變數，3 處 launch args 改讀變數 |

### Env 一行 override（demo 當天可切）

```bash
# 切回 gemini 主線（OpenRouter OpenAI down 時）
PAWAI_LLM_MODEL=google/gemini-3-flash-preview bash scripts/start_full_demo_tmux.sh

# 改用 opus 高品質模式（demo 重要 turn 試）
PAWAI_LLM_MODEL=anthropic/claude-opus-4.7 bash scripts/start_full_demo_tmux.sh

# launch arg 直接傳（手動測試）
ros2 launch pawai_brain pawai_conversation_graph.launch.py \
  openrouter_gemini_model:=anthropic/claude-opus-4.7
```

### Param 命名 legacy 注意

ROS param `openrouter_gemini_model` 是 **primary slot**（不是字面 Gemini）。
ROS param `openrouter_deepseek_model` 是 **fallback slot**（不是字面 DeepSeek）。
為了 demo 前不打破 launch arg 與既有 caller，5/12 沒 rename，僅改 default + 加註解。
**Demo 後 backlog**：rename 成 `openrouter_primary_model` / `openrouter_fallback_model`。

## 待人工確認

我這份是看 raw output 的主觀評分。要嚴謹建議跑：

```bash
python3 tools/llm_eval/score.py tools/llm_eval/results/2026-05-12-demo-focused-ab-round2-small.json
# 互動式問你 4 軸 × 60 = 共 ~12 分鐘
```

打分後再看 `--report` summary 與本文質性結論交叉驗證。

## 還沒做的事

1. **Jetson smoke**: 60s 自介 × 5 看 gpt-5.4-mini 在 Jetson tunnel 條件下是否仍 P50 ≤ 1.5s
2. **預算閥**: 給 OpenRouter key 設月 budget cap（避免 demo 失控費用）
3. **Prompt cache 實測**: gpt-mini cache 機制可能跟 Gemini 不同，第一輪 latency 要看
4. **Offline 文案產生**: 用 GPT-5.5 / Opus 跑一次 30-50 條候選 reply 存進 EXAMPLES.md

## 答辯準備

被問「為什麼換 gpt-5.4-mini」時可以講：
> 我們對 8 個 OpenRouter 模型跑了兩輪 demo-focused A/B（共 108 calls）。Round 1 比 4 個大模型（Gemini / DeepSeek / Opus / GPT-5.5），Round 2 比 4 個小版本（Sonnet / Haiku / GPT-mini / GPT-nano）。最終 gpt-5.4-mini 在三個維度勝出 — P50 1.16s 比 Gemini 快 39% 也比 Opus 快 27%、cost $0.018/12-call 是 Opus 的 1/80、質量穩定無 JSON 格式 bug。Deepseek/Sonnet/Haiku/Nano 各有 demo 殺手 bug（reasoning 慢尾 / markdown fence / 漏 audio tag）所以淘汰。Gemini 留作 cost-floor 備援，env 一行可切回。
