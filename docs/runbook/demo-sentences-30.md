# PawAI 30 展示句腳本

> **用途**：5/14 校園 demo 現場按順序講 / 做的展示流程
> **參考**：`docs/pawai-brain/architecture/0511/{brain,face,gesture,pose,object,speech}.md`
> **撰寫日期**：2026-05-12
> **總時長**：依語速約 8-12 分鐘
> **與 demo-30-case-checklist.md 的差別**：那份是「驗收測試」（pass/fail），這份是「演出腳本」（按順序講）

---

## 演出設計原則

1. **6 段 × 5 句**：每段聚焦一個能力軸，順序遞進
2. **每句標觸發模組**：演講者可以同時對觀眾解釋「現在在示範什麼」
3. **預期 PawAI 反應**：知道理想答長什麼樣才能臨場判定 demo 有沒有失靈
4. **失靈時要說什麼**：每句都有 fallback talk track，掩蓋技術問題
5. **動作 (★) 標記**：要做手勢/姿勢的句子前面加 ★

---

## A. 開場 + 自我認知（5 句，~90 秒）

> 目標：建立 PawAI 是「具身互動小狗」的人格框架，不是 chatbot；展現 Brain 七 mode 中 `identity` + `self_intro_request` + `capability_question` 三種。

| # | 你說 | 觸發 Brain mode | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **A1** | 「嗨！PawAI！」 | greet → wave_hello skill 直發 | ★ 手勢: wave_hello（搖頭+揮手） + 「嗨～很高興看到你！[excited]」 | 講話沒動作就「動作太久沒做有點生疏」 |
| **A2** | 「你是誰？」 | identity mode（短版人格） | ~30 字身份回答，不列功能清單，不講 Go2 細節 | — |
| **A3** | 「我現在在跟同學介紹你，自我介紹一下吧。」 | self_intro_request | 100-180 字結構化：身份 + 專題定位 + 2-3 個 skill + grounded 觀察 + 邀請 | 太短就接「我也可以再詳細一點」 |
| **A4** | 「你會什麼？」 | capability_question | 具體列 4-5 個能力（看人 / 手勢 / 姿勢 / 物體 / 聊天），不講「很多功能」 | 列得太空泛就追問「比方說呢？」 |
| **A5** | 「跟隨我可以嗎？」 | capability_question（誠實限制） | 應該說「跟隨還在開發中」，**不能亂承諾** | 若它答應，現場糾正「它有時候會 over-promise」 |

---

## B. 場景理解（scene_query 融合，5 句，~120 秒）

> 目標：展示 N5-C scene_query mode — face + pose + gesture + recent_objects 融合成語境敘述。**這是整場最技術濃度高的一段，請慢慢講。**

| # | 你說 | 觸發 | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **B1** | 「你現在看到什麼？」 | scene_query → world_state 整合 | 串起：眼前的人（roy）+ 最近姿勢 + 最近手勢 + 桌上 recent_objects | 它只講物體沒講人 → 「它應該也看到我，給它一點時間」 |
| **B2** ★ | （手裡舉一杯紅色的杯子）「我手上拿的是什麼？」 | object_perception + HSV 12 色 | 「看到紅色的杯子了～」（class+color 對齊） | 顏色錯：「真實光線下顏色判斷有時候會跳，那是 HSV 分類的限制」 |
| **B3** | 「桌上還有什麼？」 | recent_objects 30s 視窗 | 列 ≤ 3 樣，含 age_s 自然帶過 | 沒講到桌上的東西 → 「物體偵測有 30 秒視窗，剛剛沒看到就會 miss」 |
| **B4** | 「我們在哪？」 | world_state period + time | 早上/下午/晚上 + 大致時間，不亂編地點 | 它編了地點 → 「它不知道實際位置，這是它在用上下文猜測」 |
| **B5** | 「你看得到我嗎？」 | face_identity stable_name | 「我看到 roy 了，距離大概 1.2 公尺」（若有 face DB 命中） | 認不出來 → 「它資料庫只認得我跟阿嬤，這位是『陌生人』」 |

---

## C. 手勢觸發（5 句 + 動作，~120 秒）

> 目標：展示 9-gesture enum 中的 5 個 — palm（safety）/ fist（mode switch）/ index / wave / thumbs_up+ok（HIGH-risk confirm flow）。**注意手要在 2m 內，光線足夠。**

| # | 你做 + 你說 | 觸發 | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **C1** ★ | （比手掌停止 palm）「停一下！」 | gesture=palm → system_pause（**SAFETY always**）| Go2 立刻停止任何 motion，回「好，我先停一下」 | Palm 沒辨識 → 「手勢辨識有 ~550ms 反應時間，再比久一點」 |
| **C2** ★ | （比 wave 揮手）「揮揮看到嗎？」 | gesture=wave → wave_hello skill 直發 | wave_hello 動作 + 招呼 reply | 揮手太快沒觸發 → 「揮手檢測需要 1.5 秒內 2 次方向反轉」 |
| **C3** ★ | （比握拳 fist）「我要進入安靜模式」 | gesture=fist → enter_mute_mode | 「好，我進入安靜模式」（之後 chat 不主動 reply）| 觸發不到 → 「N7 已經把 fist 投票放寬到 5 frames」 |
| **C4** ★ | （比食指 index）「我要說話了」 | gesture=index → enter_listen_mode | 「好，我在聽」 | 同上 |
| **C5** ★ | （先比 thumbs_up）「做得很好！」「[等 prompt confirm]」「OK」（比 ok 手勢）| thumbs_up → wiggle 提案 → 等 OK → 執行 | 第一次比 thumbs_up：「要我搖屁股嗎？比個 OK 我就做」→ 比 OK → 執行 wiggle | 它直接執行沒 confirm → 「正常它要先問，這是 HIGH-risk skill 規則」 |

---

## D. 姿勢觸發（5 句，~90 秒）

> 目標：展示 7-pose classifier（standing / sitting / crouching / bending / fallen / akimbo / knee_kneel），focus 在 demo 期穩定的 5 個。**fallen TTS 已 demo silence（5/8 + 5/12 雙重決議），Studio 會有紅色警示但 Go2 不會喊話。**

| # | 你做 | 觸發 | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **D1** ★ | 站著對 PawAI 問：「你看我現在站著對不對？」 | pose=standing（baseline 不發 event）| 從 [最近姿勢] 帶到回答 | — |
| **D2** ★ | 坐到椅子上 1 秒 | pose=sitting → sit_along skill | 「會不會太累？」（demo bridge TTS, 5s cooldown）| 偵測不到 → 「坐姿要 y-geometry 兩條 leg 同時看到」 |
| **D3** ★ | 蹲下來摸地板 | pose=crouching | 「我在這裡喔」（demo bridge）| — |
| **D4** ★ | 站著彎腰撿東西 | pose=bending | 「請小心喔」 | 變成 fallen → 「deep-bending guard 應該擋住，N7 也調過 vertical_ratio」 |
| **D5** ★ | （**僅 Studio 螢幕**示範跌倒輪廓，**不真摔**）演講中提：「真的跌倒會觸發 fallen_alert skill — 內建 stop_move + SAY『偵測到 roy 跌倒，請注意安全』，cooldown 15 秒。今天 demo 我們不真跌，我給你看 trace」 | （口頭講解 + Studio 看 trace）| Studio 顯示 fallen event 走 fallen_alert skill 路徑 | — |

---

## E. 物體 + 顏色辨識（5 句 + 道具，~90 秒）

> 目標：展示 YOLO26n + HSV 12 色 + brain TTS 白名單 ~32 類整合。**準備 3 樣道具：紅杯子、棕色椅子（demo 場地通常本來就有）、書。**

| # | 你說 + 道具 | 觸發 | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **E1** ★ | （拿紅杯子）「這是什麼顏色的？」 | object: cup + color=red | 「看到紅色的杯子了」（confidence ≥ 0.6 才講顏色）| 沒講顏色 → 「N5-A 設計：color confidence < 0.6 會丟掉顏色，這是精度 > 豐富度」 |
| **E2** ★ | （指向棕色椅子）「那邊那個是什麼？」 | object: chair + color=brown | 「咖啡色的椅子」 | 講藍色 → 「HSV brown 規則是 H∈[5,25] + V<130，光線太亮會被誤判成 orange」 |
| **E3** ★ | （拿一本書）「這個你認得嗎？」 | object: book（在 TTS 白名單內）| 「看到書了」+ 可能加性格句 | — |
| **E4** | 「你最近看到什麼？」 | recent_objects 30s 窗 | 列 ≤ 3 樣 + age（秒前） | 講到 person → 解釋「人類已被 N5-A filter 排除，避免 face / object 雙重講」 |
| **E5** ★ | （故意拿一個飛盤或滑板之類）「這是什麼？」 | YOLO 認得但**不在 ~32 類 TTS 白名單** | 視覺面板會顯示 frisbee/skateboard，但 PawAI 不會主動 remark | 觀眾以為失靈時可講：「這是設計過的 — UI 顯示 80 類但只對 32 類室內物件 remark，避免機器人碎念飛盤」 |

---

## F. 情感對話 + audio tag（5 句，~120 秒）

> 目標：展示 LLM persona v3 + audio tag 情緒渲染（gemini Despina quality lane）+ 5-turn memory + 多 mode 切換。**這段最展現「不是 chatbot」的差異。**

| # | 你說 | 觸發 | 預期 PawAI 反應 | 失靈 fallback |
|:-:|------|-----|-----|------|
| **F1** | 「我今天有點累。」 | chat mode + persona empathy | 帶 `[gentle]` audio tag，溫柔語氣（gemini 渲染）| 沒有情緒 → 走 fast lane 了 → 「fast lane edge_tts 不渲染 audio tag」 |
| **F2** | 「跟我說個笑話。」 | chat mode + persona playful | 帶 `[playful]` 或 `[laughs]`，故事化 reply | — |
| **F3** | 「謝謝你今天陪我。」 | chat mode + persona warmth | 帶 `[excited]` 或 `[gentle]`，回應自然 | — |
| **F4** | 「等等，剛剛我們說我累了，你還記得嗎？」 | memory check（5-turn deque）| 應該指回 F1 提到的累 | 它說不記得 → 「memory 只存最近 5 turns，這是設計 trade-off」 |
| **F5** | 「我要走了，再見！」 | chat mode + closure | 自然 goodbye，可能含 `[gentle]` | 講太長就點頭微笑收場 |

---

## 演出總控

### 順序建議
A → B → C → D → E → F，遞進「認知 → 感知 → 互動 → 情感」。每段間可以暫停 5-10 秒讓觀眾消化。

### 觀眾提問緩衝句
- 「這部分我可以再詳細解釋嗎？」
- 「我先讓它看下一個再回答你，可以嗎？」
- 「這個問題我先記著，等 demo 結束再回答你比較完整」

### 全場失靈應急
| 狀況 | 應急 |
|------|------|
| 突然完全沒回應 | `pawai status` 看 tmux 哪個 window 死了 → 在筆電上 announce「我重啟一下感知 stack，30 秒」 → `pawai demo stop && pawai demo start` |
| ASR 認不出（背景太吵）| 切到 Studio 用 text input 繼續，講「現場太吵語音不穩，我改用文字 demo」 |
| 顏色一直辨錯 | 主動帶過：「光線變化下顏色 detection 是 HSV 規則的限制，post-demo 會做 indoor dataset fine-tune」 |
| Go2 完全不動 | 講解「demo 70% 互動 30% 守護，這時候我們聚焦在感知 + 對話這塊」，靠 Studio 螢幕補 |
| Wi-Fi 全斷 | 切 Case C：unset OPENROUTER_KEY、TTS_PROVIDER=piper、ASR 走 local。「現在這是全離線模式，回覆會比較短，但 perception 全部正常」 |

### 帶下場 checklist（5/14 早上）
- [ ] 紅杯子 / 書（其他道具場地會有）
- [ ] 筆電充飽 + 充電線
- [ ] Mac + Mac→Go2 SSH 已驗
- [ ] Tailscale 已登
- [ ] `pawai doctor` 全綠
- [ ] Backup：USB hotspot（場地 Wi-Fi 不穩時）
- [ ] face_db 內已有 roy + 你 demo 同伴的臉（或預期演示「陌生人」）

---

## 引用

- 模組能力範圍：`docs/pawai-brain/architecture/0511/`
- 驗收（vs 演出）：`docs/runbook/demo-30-case-checklist.md`
- Fallback 三 case 切換：`docs/runbook/mac-migration-setup.md` §6
- 30 輪 ASR 驗收（自動化）：`test_scripts/speech_30round.yaml`
