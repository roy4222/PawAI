# Demo Script — 5 分鐘 Happy Path 劇本

> **撰寫日期**：2026-05-11
> **適用 demo**：5/16 dry-run / 5/18 final
> **總長**：5 分鐘（300s）
> **配套文件**：
> - `docs/runbook/demo-frozen-backlog.md` — 凍結清單（劇本反推不出新需求就不動）
> - `docs/runbook/demo-fallback-script.md` — 失敗話術 + canned self-intro 10s/25s/45s
> - `pawai_brain/personas/v1/` — N2 persona（demo-host 模式）

---

## 0. 劇本撰寫原則

1. **PawAI 是 host 不是 chatbot**：每段結尾主動拋下一步，不要乾講完就停
2. **七大能力都要露面**：人臉 / 語音 / 手勢 / 姿勢 / 物體 / 對話 / 移動
3. **跌倒是 wow point**：放整場最強位置，前面節奏為它鋪墊
4. **失敗解釋本身是亮點**：reactive_stop 觸發時 PawAI 自己講為什麼停，比 demo 一切順利更打動評審
5. **不誇大未閉環**：跟隨 / 自主巡邏 / 自主尋物閉環 / 動態繞行 — 全部不說會做

---

## 1. 場地 / 道具清單

| 項目 | 說明 |
|---|---|
| Go2 起點 | 房間中央，朝向評審 |
| 紅色杯子 | 放桌上，距離 Go2 ~1.5m，評審可見 |
| 紙箱（障礙物） | 評審側放在 Go2 前進路徑上，~1.2m 處 |
| Roy 站位 | Go2 後方偏左，不擋評審視線 |
| 評審座位 | Go2 正前方 ~2m |
| Studio 投影 | 桌上筆電投影 Studio chat panel（評審看得到 reply 文字） |
| 麥克風 | USB UACDemoV1.0（device 24，Jetson 端） |
| 喇叭 | USB CD002-AUDIO（plughw:2,0） |

---

## 2. Pre-demo Checklist（demo 前 10 分鐘跑）

```bash
# 在 Jetson
bash .claude/skills/brain-studio-lane/scripts/preflight.sh demo
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
bash .claude/skills/brain-studio-lane/scripts/healthcheck.sh
```

- [ ] `/tts` 有 publisher
- [ ] `/brain/chat_candidate` 有 publisher
- [ ] Studio gateway `:8080/health` 200
- [ ] Frontend `:3000` 開得到 chat panel
- [ ] 人臉 db 含「Roy」（demo 前一天 enroll）
- [ ] 紅色杯子 yolo + HSV 認得（先 `ros2 topic echo /event/object_detected --once` 驗）
- [ ] reactive_stop 1.1m 煞停測一次

如果任一項紅燈 → 看 `demo-fallback-script.md` §1-2 決定要不要降級。

---

## 3. 5 分鐘劇本

### [0:00 — 0:30] 開場自介

**[評審入座，Roy 站定]**

ROY:
> PawAI，跟大家打個招呼吧。

**PawAI**（stand → wave → 中版自介）:
- motion: `stand` (1.5s) → `wave` (1s)
- audio tag: `[excited]` → `[playful]` → `[curious]`

```
[excited] 嗨教授！我是 PawAI，住在這隻 Go2 身體裡的具身 AI。

[curious] 我們的專題叫「多模態感知融合之自主尋物與具身互動」 ——
簡單說，就是我能看、能聽、能想、能動。

[thinking] 我認得 Roy、能聽懂自然中文、會看手勢跟姿勢，
看到物體會說出來，導航避障也在場測。

[playful] 你可以跟我聊天、比手勢、或問我能做什麼。要從哪裡開始？
```

**節奏**：25s 中版（見 `demo-fallback-script.md` §6）
**這段是 hardcoded**：`self_introduce` skill canned reply，不靠 LLM 即興。理由：開場最不能翻車。

**失敗預案**：LLM 死 → fallback short 版（10s）；TTS 死 → Roy 補旁白。

---

### [0:30 — 1:30] 認人 + 主動接話

**[Roy 移近 Go2，或評審靠近]**

PawAI（face_identity 觸發 → 主動接話）:
- 偵測到 Roy 臉 + 評審生面孔 → trigger interaction_router welcome event
- audio tag: `[curious]`

```
[curious] 嗨～你旁邊是新朋友嗎？
```

ROY:
> 這位是王教授，今天來看你 demo。

PawAI:
- audio tag: `[playful]`
- motion: `wave` (1s)

```
[playful] 王教授好！很高興見到你。
[thinking] 我等等可以介紹幾個功能 — 你想先看我認手勢，還是看我做動作？
```

**這段考驗 N2**：「主動拋下一步」必須在這裡生效。**5/13 早 N2 smoke 重點就是這段**。
**失敗預案**：N2 沒生效（PawAI 只說「教授好」就停）→ Roy 引導「PawAI 介紹一下你會什麼」轉手勢段。

---

### [1:30 — 2:30] 手勢示範

**[Roy 比 👍 thumbs_up]**

PawAI:
- gesture event: `thumbs_up` → skill `wiggle`
- audio tag: `[playful]`

```
[playful] 收到大拇指！我搖一下給你看。
```
- pause 0.8s
- motion: `wiggle` (~2s)

```
[excited] 怎麼樣？我還會比 OK、揮手、比讚這幾種手勢。要不要再試一個？
```

**[Roy 比 ✌️ peace]**

PawAI:
- gesture event: `peace` → skill `stretch`
- audio tag: `[playful]`

```
[playful] 收到！伸個懶腰。
```
- motion: `stretch` (~2s)

**節奏掌握**：兩個手勢就夠，不要 6 個全試完 — 太占時間。Roy 可隨機選 2-3 個。
**失敗預案**：手勢沒觸發 → Roy「我再比一次」重試 1 次；仍失敗 → 跳到物體段。
**凍結提醒**：circle / come_here 不要試（在 freeze 清單）。

---

### [2:30 — 3:30] 物體辨識 + LLM 自由發揮

**[Roy 或評審指紅杯子]**

ROY:
> PawAI，桌上那是什麼？

PawAI:
- 訂閱 `/event/object_detected` 拿最近 N 秒物體 + 顏色
- LLM 自由生成（不 hardcoded）
- audio tag: `[curious]`

```
[curious] 我看到一個紅色的杯子，是新的嗎？看起來蠻喜氣的。
```

教授（預期會問）:
> 你怎麼知道是紅色的？

PawAI（LLM 自由發揮，但限 30 字內）:
- audio tag: `[playful]` 或 `[thinking]`

```
[thinking] 我用 YOLO 認出杯子，再用 OpenCV 看主要顏色 ——
紅綠藍三個通道比一下，紅的最強，所以是紅色。
```

**這段是 LLM 即興**，不 hardcoded。
**前提**：brain 必須拿得到 object event 作為 context。**這是劇本反推出的真缺口 — 詳見下方 §4 待驗清單**。
**失敗預案**：brain 沒接到 object event → PawAI 講不出「紅杯子」→ Roy 補旁白「物體辨識 ✅、顏色 ✅，串到 LLM context 還在優化」轉跌倒段。

---

### [3:30 — 4:00] 跌倒（整場最強）

**[Roy 假裝跌倒趴地]**

PawAI:
- pose event: `fallen` + face cache 注入 name
- audio tag: `[worried]`
- bridge audible disabled（避免雙播），由 brain 走 LLM say

```
[worried] 偵測到 Roy 跌倒，請注意安全！
```

- pause 0.5s
- audio tag: `[concerned]`

```
[concerned] 你還好嗎？需要我做什麼？
```

**這是整場 wow point**。理由：
1. 真實安全價值（不是炫技）
2. 多模態融合最直接展示（pose + face → name → 自然語音）
3. 評審能立刻 grasp 為什麼 embodied AI 比手機 app 有意義

**失敗預案**：
- name 沒注入 → PawAI 講「偵測到有人跌倒」也夠用
- pose 沒觸發 → Roy 站起來重試 1 次；仍失敗 → 跳到 Nav 段

---

### [4:00 — 4:30] Nav + 失敗解釋

**[Roy 站起後]**

ROY:
> PawAI，過來這邊。

PawAI:
- skill: `goto_relative` 0.5m
- 中途 reactive_stop 觸發（前方紙箱 1.1m 內）
- audio tag: `[curious]`

```
[curious] 前面有東西擋住，我先停下來等。
```

ROY:
- 移開紙箱

```
[Roy 移開紙箱]
```

PawAI:
- 自動續走
- audio tag: `[playful]`

```
[playful] 好啦，謝謝！我走過去囉。
```

**這段亮點**：失敗解釋本身是 demo 亮點 — PawAI 自己講為什麼停，比一切順利更打動評審。
**話術紀律**：絕不講「我自動繞開」（凍結項目）。只講「我停下來等」+「謝謝你移開」。
**失敗預案**：goto 不動 → Roy「導航底層還在調，安全停障 100% work」轉殺手問。詳見 `demo-fallback-script.md` §2。

---

### [4:30 — 5:00] 殺手問 + 收尾

**[評審預期會問]**

教授:
> 你覺得做這個專題最難的是什麼？

PawAI（**hardcoded preset**，30s 答案）:
- audio tag: `[thinking]` → `[curious]`

```
[thinking] 最難的是「我同時要聊天、看環境、又要走路」這三件事。
Jetson 算力有限，所以我們把感知放邊緣、Brain 放雲端，
靠 ROS2 topic 把它們串起來。

[curious] 還有一件事 —— 怎麼讓我「不亂跑」。
LLM 不直接控馬達，所有動作走 SkillContract，
這樣即使 LLM 講錯話，馬達也不會亂動。

[playful] 你還想問什麼嗎？
```

**為什麼 hardcoded**：教授會問什麼可預測度高，preset 答案能控制長度 + 確保技術點清楚。
**失敗預案**：教授沒問殺手問 → 直接收尾。

ROY:
> 謝謝 PawAI。

PawAI:
- motion: `sit`
- audio tag: `[excited]`
- motion: `wave` (1s)

```
[excited] 謝謝大家！下次再見囉～
```

---

## 4. 劇本反推出的真缺口

寫完劇本後檢查：哪些段落「現有實作做不到」？

| 段落 | 真缺口 | 嚴重度 | 處理 |
|---|---|---|---|
| §3 §[2:30] 物體段 | brain 是否 inject object event 到 LLM context | **高** | 5/13 晚要看 `conversation_graph_node` 代碼確認，若沒接 → 候選 N3 hotfix |
| §3 §[0:00] 開場 | `self_introduce` skill canned reply 是否真的 25s 中版 | 中 | 5/13 早 N2 smoke 驗收 |
| §3 §[4:30] 殺手問 | 是否有 hardcoded preset 機制 | 中 | 不一定要做 skill，可以 persona EXAMPLES.md 加 few-shot |
| §3 §[3:30] 跌倒 | name 注入是否真的從 brain 30s face cache 拿 | 中 | 5/13 早 N2 smoke 驗收 |
| §3 §[1:30] 手勢 | thumbs_up → wiggle 是否真的觸發 motion（不是只發 TTS） | 中 | 5/13 早 N2 smoke 驗收 |
| §3 §[4:00] Nav | goto_relative 0.5m 中途 reactive_stop 觸發是否真有自然語音 | 中 | 已在 5/12 nav burndown 3/3 通過，driver 端確認 |

**5/13 晚 N3 候選 hotfix（依劇本反推優先序）**：
1. **brain inject object context** — 物體段沒這個 demo 不成立
2. 殺手問 preset few-shot — 補 EXAMPLES.md
3. 其餘為驗收項，不是新工作

**凍結紀律**：上面 N3 候選任一動 → 必須走 `demo-frozen-backlog.md` 破例規則（git tag N3 + justification）。

---

## 5. 念劇本演練法（給 Roy）

寫完馬上做一件事：**自己念一遍 PawAI 全部台詞 + Roy 全部台詞**（沒 robot 也要走）。

**計時節點**：
- 0:30 念到「要從哪裡開始？」
- 1:30 念完手勢段
- 2:30 念完紅杯子段
- 3:30 念完跌倒段
- 4:00 念完 Nav 段
- 5:00 收尾

**演練檢查**：
- [ ] 哪段卡？（台詞不順 / Roy 接話太突兀）→ 改劇本
- [ ] 哪段冷？（資訊量太少 / 評審會分心）→ 加 PawAI 一句
- [ ] 哪段尷尬？（PawAI 講完沒人接）→ 改 PawAI 結尾拋問題
- [ ] 哪段 wow？（聽完想拍手）→ 保留節奏

**第一次走絕對會彆扭**。記下卡點回頭改。

**演練頻率**：5/13 起每天晚上花 15 分鐘念一次。

---

## 6. 5/16 dry-run（找 1-2 個假評審）

**5/16 dry-run 之前要完成**：
- [ ] N2 smoke pass（5/13 早）
- [ ] N3 hotfix 決策（5/13 晚）—— 動還是不動 brain object context
- [ ] 劇本念過 3 次以上
- [ ] reactive_stop 1.1m demo 連跑 5 次穩定
- [ ] 紅杯子在場地實測 yolo + HSV 一次

**5/16 dry-run 流程**：
1. 找朋友當假評審（不能是團隊內人）
2. Roy 完整走一次 5 分鐘劇本
3. 朋友寫下「哪段聽不懂」「哪段最 wow」「哪段冷場」
4. 5/16 晚根據 feedback 改劇本（不改代碼）

---

## 7. 不在這份劇本的事

- ❌ 詳細技術 Q&A 答辯 → `docs/mission/README.md` + 學長學弟妹分工
- ❌ Studio UI walk-through → 評審看不到細節，不專門展示
- ❌ benchmark 數據展示 → 書面文件
- ❌ 動態手勢 / 動態繞行 / 跟隨 / 巡邏 / 尋物閉環 → 全部凍結，不演也不講
