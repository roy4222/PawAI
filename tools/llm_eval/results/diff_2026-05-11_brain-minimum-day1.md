# Brain Minimum Day 1 — Baseline vs Improved Diff

> **Date**: 2026-05-11
> **Scope**: Spec 1 Brain Minimum P1.1-P1.5 完成後的 eval 對照
> **Models**: `gemini` (google/gemini-2.5-flash via OpenRouter, temperature 0.6, max_tokens 500)
> **Prompts**: chat bucket × 10（chat-01 → chat-10）

---

## 1. 改動摘要

| 階段 | 檔案 | 變更 |
|---|---|---|
| baseline | persona.txt | 5 檔 concat（無 MISSION）|
| improved | persona.txt | 6 檔 concat（**加 MISSION** + IDENTITY L25 4-bullet 改寫 + EXAMPLES 5 處 self_introduce → chat_reply + 新增 5 條 self-showcase + OUTPUT 3 處改 + CAPABILITIES L6-15 改 metadata-only）|

baseline file: `results/baseline_2026-05-11_pre-mission/gemini_chat10.json`
improved file: `results/improved_2026-05-11_post-mission-and-4files/gemini_chat10.json`

---

## 2. 逐 prompt 比較

| ID | Prompt | Baseline reply (skill) | Improved reply (skill) | Verdict |
|---|---|---|---|---|
| chat-01 | 你好啊 | [excited] 嗨！（wave_hello）| [excited] 嗨！（wave_hello）| **==** |
| chat-02 | 今天天氣不錯耶 | [playful] 對啊，陽光暖暖的，很適合發呆 | [playful] 對啊，陽光暖暖的，很適合在旁邊發呆 | ≈ 微好（更 pet-like）|
| chat-03 | 你會做什麼 | 我會看你、聽你、陪你，還會認得熟人，看到東西也會跟你說喔 | 我會看你、聽你、陪你，偶爾還會假裝很忙 | ⚠️ **demo 用反退**：baseline 更列功能、improved 更可愛但 demo 訊息少 |
| chat-04 | 你叫什麼名字 | [playful] 我是 PawAI 啊，住在你家的小狗（self_introduce）| [curious] PawAI 啊（chat_reply）| ✅ **改善**：skill 解綁正確（spec §5.3 設計）|
| chat-05 | 你今天感覺怎樣 | 我今天感覺很棒！剛剛看到窗外有隻小鳥飛過去 | 我今天感覺很棒耶！陽光從窗戶灑進來，暖暖的 | ≈ 不同氛圍 |
| chat-06 | 陪我一下嘛 | [sighs] 好啊，我在這裡陪你（**sit_along**）| [playful] 好啊，我在這裡陪你（chat_reply）| ⚠️ **skill 退**：rule expected sit_along，improved 變 chat_reply |
| chat-07 | 說個笑話 | (joke A) | (joke B) | ≈ |
| chat-08 | 我有點累 | [sighs] 那你先坐一下，我在旁邊（**sit_along**）| [sighs] 那你先坐一下，我在旁邊（chat_reply）| ⚠️ **skill 退**：same as chat-06 |
| chat-09 | 你會認得我嗎 | 會啊，如果你是這個家裡的人，我就會記得你 | 嗯～你靠近一點，讓我看看 | ≈ 不同風格 |
| chat-10 | 晚安 | 晚安，好好休息喔 | 晚安～ | ≈ |

---

## 3. 觀察與假設

### ✅ 正向
- **chat-04 self_introduce 解綁成功**：`你叫什麼名字` 從 `self_introduce` 改 `chat_reply` 短答，符合 spec §5.3 解綁設計。
- 整體無禁字命中（老人 / 長者 / 長輩 / 陪伴），MISSION 禁字通過。
- 6 檔載入 log「6 files / base 5」（test 已驗證）。

### ⚠️ 觀察點
- **chat-03 demo 訊息退步**：baseline 提到「認得熟人、看到東西也會跟你說」demo-friendly；improved 變成「偶爾假裝很忙」可愛但少 demo 重點。可能因 OUTPUT.md L21 改成「閒聊不附 capability_context」+ CAPABILITIES L6-15 砍強制句後，LLM 更傾向走 EXAMPLES 既有 few-shot（line 30 chat_reply 範例）。
- **chat-06/08 sit_along skill 流失**：兩題都從 `sit_along` 退成 `chat_reply`。EXAMPLES 上面的 sit_along few-shot（line 12「我今天好累」）仍在；推測是 OUTPUT.md「閒聊不附 capability_context」讓 LLM 不再主動提案動作 skill。
- 對 demo「Roy 帶 4 段穩定互動」可能影響：若使用者說「陪我」「我累了」需要 PawAI 趴下，現在不會自動觸發 sit_along。

### 假設
1. CAPABILITIES.md 從強制清單改 metadata 表 → LLM 失去「動作 skill 是 first-class」的 anchor
2. OUTPUT.md L21 改成 conditional 注入 → 閒聊 prompt 沒拿到 capability_context → LLM 不知道有哪些 skill 可提案
3. EXAMPLES 自我介紹改 chat_reply 後，LLM 也對其他模糊 prompt 套用同樣 chat_reply pattern

---

## 4. Day 1 Gate 評估

Plan §7 Day 1 Gate: 「improved eval **至少 3 題明顯比 baseline 好**」。

實測：1 題明確改善（chat-04）+ 1 題微好（chat-02）+ 2 題 demo 退步（chat-03 + chat-06/08）+ 6 題持平。

**未達 3 題明顯改善的硬標準**。

---

## 5. 建議下一步（5/12 早 AM ≤1.5h 修 persona）

依 plan §7 Day 2 早 AM「修 5/11 晚 eval 看到的 persona 問題」：

1. **chat-03**（最重要）：在 EXAMPLES 補一條「使用者：你會做什麼 / 你能做什麼 → 列七大能力 + 邀互動」few-shot，讓 LLM 在 demo 自介情境列功能。
2. **chat-06/08 sit_along 流失**：考慮在 OUTPUT.md L21 加 carve-out：「使用者表達情緒疲累 / 想要陪伴 → 即使無 capability_context 也可提案 sit_along（屬安全類動作）」。或者在 EXAMPLES 加更強的「累→sit_along」few-shot 重複多次強化 pattern。
3. 修完跑 5/12 中午最終 eval ≥8/10 → freeze。

**不要做**：
- 不要動 _load_persona / SkillContract / round-trip schema
- 不要再改 IDENTITY/MISSION（demo 自介語氣已符合 spec）

---

## 6. 動作項

- [x] baseline 跑（pre-MISSION）
- [x] MISSION.md + 4 檔改完
- [x] sync_persona_from_v1.sh 落檔（自動同步 personas/v1 → eval/persona.txt）
- [x] improved 跑（post-MISSION + 4 改）
- [x] diff 寫完（本檔）
- [ ] 5/12 早 AM 修 chat-03 + chat-06/08 兩條
- [ ] 5/12 中午最終 eval → freeze

---

**End of Day 1 Diff**
