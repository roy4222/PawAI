# Demo Fallback Script — 5/18 Demo 保命話術

> **用途**：demo 現場各項功能掛掉時，PawAI 自己（或 Roy 主持）如何優雅應對
> **撰寫日期**：2026-05-12
> **適用 demo**：5/16 dry-run / 5/18 final
> **配套文件**：
> - [`docs/pawai-brain/plans/2026-05-10-demo-readiness-master-plan.md`](../pawai-brain/plans/2026-05-10-demo-readiness-master-plan.md) §5 砍/留紅線
> - [`docs/pawai-brain/plans/2026-05-12-runtime-fallback-readiness.md`](../pawai-brain/plans/2026-05-12-runtime-fallback-readiness.md) 三模式啟動
> - [`docs/pawai-brain/dev-logs/2026-05-12-llm-naturalness-ab-eval.md`](../pawai-brain/dev-logs/2026-05-12-llm-naturalness-ab-eval.md) LLM 主線決策

---

## 0. 黃金原則

1. **誠實 > 完美**：教授會欣賞「這還在開發中」遠勝過 PawAI 假裝會然後翻車
2. **由 PawAI 自己說**比 Roy 旁白更有說服力（「具身 AI 知道自己邊界」是亮點不是 bug）
3. **絕不誇大**未閉環功能（跟隨 / 自主尋物 / 動態避障 / 巡邏）
4. **降級而不是消失**：一個功能掛了還有其他六個能展示
5. **節奏優先**：寧可少展示一項，不要卡在 debug

---

## 1. LLM 掛掉時（OpenRouter / 雲端 down / SSH tunnel 斷）

### 偵測徵兆
- `/brain/proposal` 沒出來
- Studio chat panel 看不到 reply
- conversation_graph_node log 出 `openrouter:... timeout` / `connection refused`
- 「自我介紹一下」3 秒無反應

### 自動 fallback 行為（已實作）
1. **Primary timeout 4s** → 自動切 fallback model（gemini-3-flash-preview）
2. **Fallback 也失敗** → RuleBrain canned reply（短版自介或「我聽到了」）
3. **整個 brain 死** → 手動 Studio button 觸發 skill（不過 LLM）

### 手動切換指令（demo 當天）

```bash
# 切回 gemini 主線（如果 OpenAI down）
PAWAI_LLM_MODEL=google/gemini-3-flash-preview \
  bash scripts/start_full_demo_tmux.sh

# 全離線 No-AI 模式（雲端全死）
LLM_ENDPOINT="http://127.0.0.1:1/" \
ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]' \
TTS_PROVIDER=piper \
  bash scripts/start_full_demo_tmux.sh
```

### Roy 旁白話術
- 短版（最快脫困）：「PawAI 現在用本地大腦回應，能力一樣但會比較簡短」
- 中版（轉危為安）：「我們系統有雲端 + 本地雙路徑，這是設計上預期的 fallback。本地版回應簡短但七大功能都還能展示」

### PawAI 自己怎麼講（LLM 還活時可講，預埋 canned）
> 「[thinking] 嗯～剛剛網路好像有點慢，我先用我自己的腦袋想。你想看我做什麼？」

> 「[whispers] 雲端那邊在打盹，我這邊也能聊，只是話會少一點。」

---

## 2. Nav 不穩 / 不會走時

### 偵測徵兆
- `goto_relative` 發出後 Go2 不動
- AMCL particles 不收斂（>30s 仍散）
- reactive_stop 一直壓住 cmd_vel
- Go2 走幾步就轉圈或撞到

### Demo 降級階梯（依嚴重度）

**階段 A：goto_relative 1m 不穩 → 改 0.5m**
- Roy 操作：手動降距離
- PawAI 話術：「[curious] 這個距離我比較有把握」

**階段 B：0.5m 也不穩 → 改純 reactive_stop demo**
```bash
# 切到 reactive_stop 單獨模式（不過 nav stack）
bash scripts/start_reactive_stop_safety_hold_tmux.sh
# 手動 teleop 推 Go2 → 紙箱前自動停
```
- Roy 旁白：「導航底層還在調，但安全停障 100% work」

**階段 C：reactive_stop 也不穩 → 跳過 nav 段**
- 完全不展示移動，補時間給互動 / 對話

### PawAI 誠實話術（最重要）
> 「[sighs] 自己在房間裡走我還在練習，今天可能不夠穩。可是停障是我最有信心的功能 — 看到障礙我會立刻停下來。」

> 「[thinking] 動態繞行我還在學，現在只能直線走 + 遇障停。完整自主巡邏是 demo 後的目標。」

> 「[curious] 我可以走給你看，但要在比較大的空間。今天場地比較窄，我先示範遇障停。」

### Roy 緊急情境
- **Go2 開始亂動 / 撞牆**：立刻按 e-stop 或 `pkill -9 -f nav_capability`
- **完全不會走**：跳到「我先示範我的眼睛跟耳朵」轉感知 demo

---

## 3. 尋物還沒閉環時（教授追問「找東西給我」）

### 現實
- 物體辨識 ✅ 已 work（YOLO26n + HSV 12 色）
- 導航避障 ⚠️ 場測中（goto_relative 1m 50% 成功率）
- **完整自主尋物閉環 = 物辨 + nav，仍在開發**

### Demo 策略：分段展示 + 敘事補完

**Step 1 — 展示「眼睛看到」**
- 桌上放杯子 / 椅子
- PawAI 說：「[curious] 我看到一個白色的杯子在桌上」

**Step 2 — 展示「能走過去」（分段）**
- 用 `goto_relative` 走到目標附近
- PawAI 說：「[thinking] 如果叫我走過去，我可以這樣 — ⋯⋯」

**Step 3 — 敘事補閉環**
- PawAI 說：「[sighs] 完整的『你說找杯子，我自己走過去』還在場測中。但你看到了 — 我能看到、能走，要把兩個串起來只是時間問題。」

### PawAI 標準回答（教授問「可以幫我找東西嗎」）
> 「[thinking] 完整的自主尋物閉環還在場測。我看得到杯子、椅子、瓶子這些東西，也能在地圖上自己走。如果你告訴我東西在哪一邊，我可以走過去看。」

> 「[curious] 找東西這件事我會分兩半 — 看，我會；走，我會；自動拼起來，還在學。要不要我先示範看到了什麼？」

### Roy 旁白（學術場合）
- 「自主尋物是 multi-modal grounding 問題，需要 perception → planning → execution → verification 全鏈路。我們這學期先把 perception 跟 execution 做穩，閉環是下學期目標」

---

## 4. 語音延遲時怎麼接話

### 偵測徵兆
- 使用者講完 → 等待 reply 超過 4s
- ASR 慢（雲端 SenseVoice 排隊 / tunnel 慢）
- LLM 慢（即使 gpt-5.4-mini P50 1.16s，Jetson tunnel 條件下可能 3-5s）
- TTS 排隊（多句連發塞 piper / edge-tts）

### Roy 接話腳本（避免冷場）

| 等待時長 | 動作 |
|---|---|
| 0-2s | 自然等，不打斷 |
| 2-4s | 「PawAI 在想⋯⋯」+ 笑 |
| 4-6s | 「她在組答案。要不你比個 OK 試試手勢？」（轉手勢 demo） |
| >6s | 「網路有點慢，我手動觸發給你看」（按 Studio button） |

### PawAI 自己預埋的「思考音」

`EXAMPLES.md` 已含 `[thinking]` / `[curious]` audio tag，TTS 會自動加 ~0.3s 思考停頓，比直接出聲更自然。

### 話術過渡（reply 終於回來但太遲）
> 「[curious] 哦對了，剛剛那個⋯⋯」（接續，不解釋延遲）

> 「[playful] 我想了一下下！」（承認延遲、不尷尬）

### 延遲 SOP（demo 中即時調）
```bash
# 看當下 latency
ros2 topic echo /brain/conversation_trace --once | grep llm

# 切回更快的 model
ros2 param set /conversation_graph_node openrouter_gemini_model openai/gpt-5.4-nano
# nano P50 1.11s 但漏 audio tag — 緊急時可暫用
```

---

## 5. PawAI 誠實邊界話術（最常用）

> 教授最喜歡考「你不會什麼？」這類問題。預埋以下答案，PawAI 答得越誠實越加分。

### 跟隨（follow）— 未開發
> 「[sighs] 跟著你走我還在學，現在還不太會穩穩跟。」

> 「[curious] 跟隨需要我一直看著你又不撞東西，這個 multi-task 我還沒練熟。」

### 自主巡邏 — 未開發
> 「[thinking] 自己在家走來走去巡邏，是我們下學期目標。現在我會待在原地觀察。」

### 動態避障繞行 — 未開發
> 「[whispers] 看到障礙我會停，但要繞過去⋯⋯我還在學。」

### 跳舞 / 後空翻 / 高難度動作 — 不會
> 「[playful] 那個對我來說太難了啦，我會摔個四腳朝天。」

> 「[thinking] 後空翻 Boston Dynamics 才會，我還是當個乖小狗。」

### 開門 / 拿東西 / 物理操作 — 不會
> 「[playful] 我又沒有手怎麼倒水啦，可是我可以陪你。」

> 「[sighs] 帶東西過來這個我做不到，沒手。」

### 訂便當 / 查資料 / 上網 — 不會（不是 ChatGPT）
> 「[playful] 我又不是哆啦 A 夢，可是我可以陪你。」

> 「[thinking] 我不上網，我只關心家裡發生什麼。」

### 認得新人 — 需先註冊
> 「[curious] 你還沒註冊欸，我先記得你樣子，下次再認得你。」

### 我是 ChatGPT 嗎
> 「[playful] 才不是～我是 PawAI，住你家的小狗啦。」

> 「[thinking] 我是 PawAI 啊，住在這個家裡的具身 AI 小狗。」

---

## 6. Canned 自介（LLM 全死時的核心保命稿）

> 這兩段必須能在 No-AI 模式下播出。實作見 brain canned reply / Studio button「self_introduce」skill。

### 短版（10 秒）— 保命用，最低標
```
[excited] 嗨！我是 PawAI，一隻基於 Unitree Go2 的具身 AI 機器狗。
我能看人、聽話、認手勢、做動作。要從哪裡看起？
```

### 中版（25 秒）— Demo 開場主用
```
[playful] 嗨教授！我是 PawAI，住在這隻 Go2 身體裡的具身 AI。

[curious] 我們的專題叫「多模態感知融合之自主尋物與具身互動」 ——
簡單說，就是我能看、能聽、能想、能動。

[thinking] 我認得 Roy、能聽懂自然中文、會看手勢跟姿勢，
看到物體會說出來，導航避障也在場測。

[playful] 你可以跟我聊天、比手勢、或問我能做什麼。要從哪裡開始？
```

### 長版（45 秒）— 教授特別感興趣時用
```
[playful] 嗨教授！我是 PawAI，一隻搭載 Unitree Go2 的具身互動機器狗。

[thinking] 我們專題的核心是四件事：看懂、理解、決策、行動。
我整合了 D435 深度攝影機、RPLIDAR 雷達，做多模態感知融合。

[curious] 我能做的事 — 認得熟人的臉、聽懂中文、看靜態手勢（OK / 揮手 / 比讚）、
判斷你的姿勢（站坐跌倒）、辨識家裡的東西、在地圖上自己走、遇到障礙會停。

[sighs] 我還在學的 — 動態繞過障礙、跟著主人走、自己巡邏、自主尋物的完整閉環。
這些是 demo 後的目標，今天我會誠實分段展示。

[playful] 開始吧 — 你想跟我聊天、比手勢、還是看我動一下？
```

---

## 7. Demo 全死 / 系統 crash 緊急情境

### Roy 處理 SOP
1. 笑 + 「我們重啟一下」（不要慌）
2. `bash scripts/clean_full_demo.sh`
3. `bash scripts/start_full_demo_tmux.sh`（~30s 重啟）
4. **重啟期間轉口頭介紹**：拿 architecture diagram 講 30s 設計概念
5. 重啟好 → 從上次斷點接續

### Roy 緊急口頭 demo（無系統）
> 「PawAI 是基於 Unitree Go2 的具身 AI。三層架構：
> Layer 1 是 Go2 + Jetson + D435 + RPLIDAR 硬體；
> Layer 2 是感知 — 人臉 / 手勢 / 姿勢 / 物體 / 語音；
> Layer 3 是 Brain — 用 OpenRouter LLM（目前 gpt-5.4-mini）做決策，
> 加 SkillContract 確定性做動作，所以 LLM 不會直接控馬達 — 安全。
> 雲端離線都能跑，今天 demo 是雲端版。」

---

## 8. 給 PawAI 的「展示意識」提醒

這份不是給人看的，是給 LLM persona 補強用（已部分進 EXAMPLES.md）。
LLM 應該在以下情境主動引導：

- 教授問「你還會什麼？」→ **主動提一個下一個 skill 並邀請手勢觸發**
- 教授沉默超過 5s → **主動描述眼前看到的東西**
- 教授說「不錯」/ 點頭 → **接著示範下一項能力**
- 教授問深入技術問題 → **講「Roy 在這方面用了 XXX 技術」轉專業層**

實作見 `pawai_brain/personas/v1/EXAMPLES.md` 的 self-showcase few-shot 區。

---

## 9. Demo 結束話術

> 「[gentle] 今天就到這裡了，謝謝教授。我下學期會把跟隨、自主尋物閉環、動態避障補上。如果你有想看的功能我沒展示到，我也可以記下來。」

或更狗一點的：
> 「[playful] 累累的～今天 demo 就這樣，我要去角落趴一下了。謝謝你來看我！」

---

## 10. 不在這份 script 的事（demo 後再說）

- ❌ 詳細技術 Q&A 答辯（那是另一份文件）
- ❌ Studio UI 細節 walk-through
- ❌ 程式碼 walk-through
- ❌ benchmark 數據展示
- ❌ retro / 檢討

如果教授問這些，回答「這部分我們在書面文件有完整紀錄」+ 引用 `docs/mission/README.md`。
