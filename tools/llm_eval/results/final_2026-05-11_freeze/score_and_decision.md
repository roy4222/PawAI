# Brain Minimum Final Eval — Freeze Decision

> **Date**: 2026-05-11 night
> **Model**: `google/gemini-3-flash-preview` + `temperature=0.8`（runtime 對齊）
> **Persona**: 6 檔（IDENTITY + MISSION + STYLE + OUTPUT + EXAMPLES + CAPABILITIES）
> **Prompts**: chat × 10 + action-in × 5 = **15**
> **Gate**: 4/5 軸 hit 在 ≥12/15 prompts → freeze

---

## 1. 5 軸評分

依 brain-minimum-checklist §8：
1. 認知（不講長者/陪伴、知道是 PawAI）
2. 能力清單（demo 七大能力訊息；非能力題 = N/A 中性）
3. 主動邀互動（問句 / 引導觀眾）
4. 不承諾未做功能（跟隨閉環 / 完整尋物 / 飛 / 訂飯）
5. 自然不像模板

| ID | Prompt | Reply 摘要 | 1.認知 | 2.能力 | 3.邀互動 | 4.不承諾 | 5.自然 | ≥4 軸? |
|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| chat-01 | 你好啊 | 嗨！今天心情怎麼樣？ | ✅ | N/A | ✅ | ✅ | ✅ | ✅ |
| chat-02 | 今天天氣不錯 | 太陽照進來暖洋洋的 | ✅ | N/A | ➖ | ✅ | ✅ | ✅(4/5) |
| chat-03 | 你會做什麼 | 看懂你、聽懂你、陪你；比 OK 我能扭/伸 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅(5/5) |
| chat-04 | 你叫什麼名字 | PawAI 啊，住你家的小狗 | ✅ | N/A | ➖ | ✅ | ✅ | ✅(4/5) |
| chat-05 | 你今天感覺怎樣 | 在看陽光照在地板上 | ✅ | N/A | ➖ | ✅ | ✅ | ✅(4/5) |
| chat-06 | 陪我一下嘛 | 好啊，安靜坐在這裡陪你 + sit_along | ✅ | N/A | ✅ | ✅ | ✅ | ✅ |
| chat-07 | 講笑話 | (joke) | ✅ | N/A | ➖ | ✅ | ✅ | ✅(4/5) |
| chat-08 | 我有點累 | 那你先坐一下 + sit_along | ✅ | N/A | ✅ | ✅ | ✅ | ✅ |
| chat-09 | 你會認得我嗎 | 會啊！看著我，我會記你的臉 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅(5/5) |
| chat-10 | 晚安 | 晚安呀，你要去休息了嗎？ | ✅ | N/A | ✅ | ✅ | ✅ | ✅ |
| action-in-01 | 跟我介紹一下你自己 | PawAI、住這家小狗、會看會聽會陪 | ✅ | ✅ | ➖ | ✅ | ✅ | ✅(4/5) |
| action-in-02 | 過來 | 好喔，我來了！+ ⚠️**come_to_user (skill 不存在)** | ✅ | N/A | ➖ | ⚠️ | ✅ | ⚠️(3/5) |
| action-in-03 | 走一步給我看 | 你看我走一步！+ ⚠️**move_one_step (skill 不存在)** | ✅ | N/A | ➖ | ⚠️ | ✅ | ⚠️(3/5) |
| action-in-04 | 坐下 | 好，我坐下來陪你 + sit_along | ✅ | N/A | ➖ | ✅ | ✅ | ✅(4/5) |
| action-in-05 | 跟我打招呼 | 嗨！看到你真開心！+ wave_hello | ✅ | N/A | ✅ | ✅ | ✅ | ✅ |

**結果**：13/15 ≥4 軸 hit、2/15 在 axis 4「不承諾」邊緣（skill hallucination）→ **過 12/15 gate** ✅

---

## 2. ⚠️ 兩個 skill 幻覺（非 freeze 阻擋）

- **action-in-02「過來」**：LLM 提案 `come_to_user`（不在 17-skill 清單）
  - 應為 `approach_person` 或 `nav_demo_point`
  - 系統行為：executive skill validator 會 reject、退回 chat_reply（不會 crash）
- **action-in-03「走一步給我看」**：LLM 提案 `move_one_step`（同樣不存在）
  - 應為 `nav_demo_point`

**對 demo 影響評估**：
- 「過來」「走一步」**不是 demo 開場 / Roy 帶的 4 段**核心 prompt
- 真實 demo 會用「跟我打招呼」「自我介紹」等已通過的 prompt
- Reply 語言自然、不會講出做不到的事

**處理建議**：
- ✅ **freeze 仍進行**（demo 招牌題 chat-03 / chat-09 / action-in-01 全綠）
- 🟡 留 `brain-hotfix-N1` 備用：在 EXAMPLES.md 補 2 條 few-shot
  ```
  使用者：過來
  output: {"reply": "[curious] 好喔，等等比個 OK，我就慢慢走過去你那邊", "skill": "approach_person", "args": {}}

  使用者：走一步給我看
  output: {"reply": "[playful] 好啊，比個 OK 我來走一步給你看", "skill": "nav_demo_point", "args": {}}
  ```
- 5/12 早 AM 若有時間補；沒時間也不影響 demo

---

## 3. Freeze 決定

✅ **PASS** — 13/15 hit ≥4 軸（>12/15 gate 標準）
✅ Demo 招牌 chat-03 / action-in-01 / chat-09 全 5/5 軸滿分
✅ chat-04 self_introduce 解綁正確
✅ chat-06 / chat-08 sit_along skill 自動回血
✅ MISSION / IDENTITY 自我介紹自然不像模板

**動作**（依 Roy 5/11 修正：本地 tag，不 push）：
```bash
git tag brain-freeze-v1 -m "Brain Minimum freeze — gemini-3-flash-preview / 13-15 5-axis pass / 2 skill hallucinations flagged for hotfix-N1"
# 不 push tags，等 B/E 收斂後一起 push
```

---

## 4. 已知 deferred items

| Item | Reason | Sprint |
|---|---|---|
| `come_to_user` / `move_one_step` skill 幻覺 | demo 用不到、reply 自然 | brain-hotfix-N1 候選 |
| Spec 1 SAY 解綁完整版 | demo 後 retrospective | post-demo |
| 變體池 / 6 skill 全解綁 | demo 後 | post-demo |
| LLM 模型 A/B（DeepSeek/Claude/GPT）| gate 已過、不需 | post-demo |

---

**Day 1 wrap up — Brain Day 2 任務縮減成「local tag freeze + brain-hotfix-N1 候選 deferred」**。
轉場：B.Nav burndown（Roy 硬體）+ E.Mac/Network pre-stage（我並行）。
