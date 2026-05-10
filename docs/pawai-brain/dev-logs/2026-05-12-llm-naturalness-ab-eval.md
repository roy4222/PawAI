# LLM 自然度 4-Model A/B Eval — 2026-05-12

> **目的**：較急問題 #1 — Gemini-3-Flash 死板感是否值得換模型
> **方法**：4 模型 × 12 demo-focused prompts = 48 calls
> **結果檔**：`tools/llm_eval/results/2026-05-12-demo-focused-ab.json`
> **跑法**：`set -a; source .env; set +a; python3 tools/llm_eval/run_eval.py --prompts tools/llm_eval/prompts_demo_focused.json --models gemini,deepseek,opus,gpt --output ...`

## Latency

| 模型 | P50 | P95 | min | max | mean | tokens out 總計 |
|---|---|---|---|---|---|---|
| **opus** ⭐ | **1.59s** | 3.44s | 1.23 | 3.44 | **1.82** | 811 |
| gemini | 1.83s | 3.15s | 1.51 | 3.15 | 1.90 | 583 |
| gpt | 3.88s | 6.17s | 2.33 | 6.17 | 4.06 | 1528 |
| deepseek | 3.64s | **34.22s** ❌ | 1.81 | 34.22 | 8.97 | 1756 |

**意外發現**：Anthropic Opus 的 P50 **比 Gemini-3-Flash 還快**（1.59s vs 1.83s）。
Deepseek-V4 是 reasoning model，P95 慢尾 34s 完全不能 live demo。

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

## 結論與決策建議

### 強推：Demo 主線升級為 **Opus 4.7**

| 理由 | 數據 |
|---|---|
| P50 比 Gemini 快 13% | 1.59s vs 1.83s |
| 質感平均勝 1.5 分 | 4.0 vs 2.5 |
| 自動換 skill 避免重複 | demo-host-02 stretch vs wiggle |
| 短答狗腔對 demo 互動最對味 | demo-trick-01「才不是～」 |
| 成本可接受 | $3.6 per 60-min demo session |

**換法**：
```python
# pawai_brain/launch/pawai_conversation_graph.launch.py
# 加 launch arg llm_model_slug，default="anthropic/claude-opus-4.7"
# 同時更新 conversation_graph_node._build_openrouter_config 讓它讀 param
```

### GPT-5.5：作為「自介稿 + fallback 話術產生器」（offline 用）

質量最高（4.6/5），但 4s P50 對 live demo 偏慢，互動會卡。
最佳用途：跑一次離線生成 30-50 條候選 reply 存進 EXAMPLES.md / persona / canned fallback，平時 live 跑 Opus。

### Deepseek-V4-Flash：砍

reasoning model 慢尾 P95 34s，rote 程度與 Gemini 同級，無上線價值。

### Gemini-3-Flash：留作 cost-floor backup

當 OpenRouter Anthropic / OpenAI 都 down 時的最後 fallback。CP 值最高（$0.02 per 12 calls）但 demo 質量明顯弱。

## 待人工確認

我這份是看 raw output 的主觀評分。要嚴謹（特別是「是否要切主線」這種大決策），建議跑：

```bash
python3 tools/llm_eval/score.py tools/llm_eval/results/2026-05-12-demo-focused-ab.json
# 互動式問你 4 軸 × 48 = 共 ~10 分鐘
```

打分後再看 `--report` summary，與本文質性結論交叉驗證。

## 跟著要做的事（如果決定切 Opus）

1. `conversation_graph_node.py` 加 `llm_model_slug` ROS param
2. `pawai_conversation_graph.launch.py` 加同名 launch arg, default `anthropic/claude-opus-4.7`
3. `start_pawai_brain_tmux.sh` / `start_full_demo_tmux.sh` 加環變或 launch arg pass-through
4. Jetson smoke：60s 自介 × 5 看 latency 在 Jetson tunnel 條件下是否仍 ≤2s
5. 預算閥：給 OpenRouter key 設月 budget cap（避免 demo 失控費用）
6. **不換 prompt cache 假設** — Opus 跟 Gemini cache 機制不同，第一輪 latency 可能有差，要實測

## 答辯準備

被問「為什麼換 Opus」時可以講：
> 我們對 4 個 demo-focused prompt 跑了 48 call A/B（Gemini-3-Flash baseline / DeepSeek-V4-Flash / GPT-5.5 / Claude Opus 4.7）。Opus 在 P50 latency（1.59s vs Gemini 1.83s）、自然度、角色一致性、自動換 skill 避免重複等四個面向勝出，且 cost 在可接受範圍內。Deepseek 因 reasoning 慢尾 P95 34s 不適合 live。GPT 質量最高但延遲過高，留作 offline 文案生成。
