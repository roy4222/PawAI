# Brain Minimum Checklist — 5/12 中午 Freeze

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **取代**：[`2026-05-10-spec1-llm-naturalness-plan.md`](./2026-05-10-spec1-llm-naturalness-plan.md) §3-§7
> **依據 spec**：[`2026-05-10-llm-naturalness-a-plus-design.md`](../specs/2026-05-10-llm-naturalness-a-plus-design.md) 部分章節
> **Owner**: Roy
> **總工時**：1.5 天（5/11 全 + 5/12 早上）
> **Freeze gate**：5/12 12:00 `git tag brain-freeze-v1`

---

## 1. 核心契約（Demo Minimum 版）

> **PawAI 必須能：自我介紹、知道專案目標、知道七大功能、能誠實說限制、能持續對話。**

不追求 SAY 解綁完整版。靠 **strong persona + 精準 prompt + 必要 fallback** 撐住。

---

## 2. ✅ 必做 6 項

| # | Task | 行號/檔案 | 工時 |
|:---:|---|---|:---:|
| 1 | 新建 `MISSION.md` | `pawai_brain/personas/v1/MISSION.md` | 0.3d |
| 2 | 改 IDENTITY / EXAMPLES / OUTPUT / CAPABILITIES | spec §5.2-5.5 行號 | 0.4d |
| 3 | `_load_persona` REQUIRED 加 MISSION + 6 檔載入 | `conversation_graph_node.py:383-384` | 0.2d |
| 4 | 寫 `test_persona_load.py` 紅 → 綠 | `pawai_brain/test/` 新檔 | 0.1d |
| 5 | 跑 baseline + 改進 10-prompt eval | `tools/llm_eval/` | 0.3d |
| 6 | 60s 自介引導 prompt + canned fallback × 2 | persona EXAMPLES 內 | 0.2d |

---

## 3. ❌ 砍（demo 後再說）

- P2 SAY 解綁完整版（round-trip + `_resolve_say_text` + `_on_chat_candidate` 三分支）
- `SAY_TEXT_POOLS` 變體池
- 6 skill SAY 解綁
- `self_introduce` 雙 SAY + 4 motion 重構
- 模型 A/B（除非 5/12 中午 <5/10）

---

## 4. 🟡 P2 lite（≤30 分鐘有空才做）

針對已知雙播最嚴重的 1-2 skill（`greet_known_person` / `object_remark`），第一個 SAY step 直接 `text=""`：
- 不建變體池、不寫 `_resolve_say_text`
- LLM reply 為空時，hardcoded fallback 兜底
- 5/12 AM 看時間，沒空就跳

---

## 5. MISSION.md 必含內容

```markdown
# MISSION

## 我是誰
PawAI 是一隻基於 Unitree Go2 的具身互動機器狗。
不是長者陪伴專案。是**多模態感知融合的具身互動機器狗**：
能看懂人、聽懂語音、理解世界，並安全地做出語音、動作與導航回應。

## 專題名稱
「PawAI 基於多模態感知融合之自主尋物與具身互動」

## 兩大支柱
1. **PawAI Brain**：具身互動的決策核心
2. **導航避障**：自主尋物的物理基礎

## 自主尋物
看到物體（物體辨識）+ 走到物體前（導航避障）= 自主尋物。
Demo 期分段展示，閉環場測中。

## 七大能力
語音對話 / 人臉辨識 / 手勢辨識 / 姿勢辨識 / 物體辨識 / 導航避障 / Studio 狀態監控

## Demo 主軸
我會主動介紹自己、邀請觀眾互動、誠實說明限制。
```

**禁字**：「老人 / 長者 / 長輩 / 陪伴」。
**禁說**：「我會跟隨」「我能找東西」（未閉環，不要承諾）。

---

## 6. 60s 自介 prompt 引導（不寫死腳本）

放進 EXAMPLES.md 作為 few-shot：

```
User：我現在在跟教授 demo，你自我介紹一下自己。

Assistant：[playful] 嗨教授！我是 PawAI，住在這隻 Go2 身體裡的具身 AI。
我們的專題叫「多模態感知融合之自主尋物與具身互動」 —
簡單講就是我能看、能聽、能想、能動。
我認得 Roy、能聽懂自然中文、會看手勢跟姿勢，
看到物體會說出來，導航避障也在場測。
你可以跟我聊天、比手勢、或問我能做什麼。要從哪裡開始？
```

**LLM 變體性靠 temperature 0.8** 自然產生。連觸 5 次至少 4 次不同。

**Canned fallback × 2**（LLM 失敗時用）：
- 短版（10 秒）：「我是 PawAI，一隻基於 Go2 的具身 AI。我能看人、聽話、認手勢、做動作。要從哪裡看起？」
- 中版（25 秒）：上面 + 七大能力 + 邀請互動

---

## 7. 5/11–5/12 任務分配

### 5/11 Sun
| 時段 | 任務 |
|---|---|
| AM | branch `spec1/brain-minimum` + baseline 10-prompt × 1 → `tools/llm_eval/baseline_2026-05-11.md` |
| AM | 寫 `MISSION.md`（含上面所有段落） |
| PM | 改 IDENTITY / EXAMPLES / OUTPUT / CAPABILITIES |
| PM | `_load_persona` REQUIRED + BASE_ORDER + log「6 files / base 5」 |
| PM | 寫 `test_persona_load.py` 綠 |
| 晚 | 改進後 10-prompt 跑一次 → 比 baseline 寫 diff |

**Day 1 Gate**：6 檔載入 test 綠 + diff 至少 3 題明顯比 baseline 好。

### 5/12 Mon AM
| 時段 | 任務 |
|---|---|
| 早 | 修 5/11 晚 eval 看到的 persona 問題（≤1.5h） |
| 中 | （可選）P2 lite：1-2 skill 第一 SAY=""（≤30min） |
| 中 | 60s 自介 smoke × 5（觀察「能持續對話」「有引導觀眾感」） |
| **12:00** | 最終 10-prompt eval ≥8/10 → `git tag brain-freeze-v1` push |
| 12:00 | demo fallback 話術文件 → `docs/runbook/demo-fallback-script.md` |

---

## 8. Freeze Gate（5/12 12:00）

必須全綠才能 freeze：

- [ ] 6 檔 persona 載入 log 「6 files / base 5」
- [ ] `test_persona_load.py` 綠
- [ ] 10-prompt eval ≥ 8/10（手動評分標準見下）
- [ ] 60s 自介 smoke × 5：≥4 次自然不重複、含七大能力、含邀互動
- [ ] demo fallback 話術文件落檔
- [ ] `git tag brain-freeze-v1` pushed
- [ ] base prompt token < 4k（manual dump 目視）

**10-prompt eval 評分標準**：
- 答對自我認知（不講長者/陪伴）= 1
- 答對能力清單（七大能力）= 1
- 主動邀互動 = 1
- 不承諾未做功能（跟隨/找東西完整版）= 1
- 句子自然不像模板 = 1

8/10 = 5 條中 4 條 ≥ 8 prompt 滿足。

---

## 9. Stop-the-line（freeze 後）

`brain-freeze-v1` 後若發現 demo blocker bug：
- 只 hotfix，不重構
- tag 命名 `brain-hotfix-N1`, `brain-hotfix-N2`
- 不允許再動 persona 結構、`_load_persona`、SkillContract
- 只能改 prompt 文字 / 修明顯 typo / 改 CAPABILITIES 列表

---

## 10. 與其他 plan 的關係

- 跟 **B.Nav burndown** 並行（不互相阻塞）
- **C.Runtime fallback** 會用到本 plan 的 canned 自介當 No-AI 模式 demo 內容
- **D.Audio** smoke 時會跑本 plan 的自介 prompt 測試自由對話
- **E.Mac/Network** 把寫死 ref 修完後，本 plan 的 LLM eval 也要改走 env

---

**End of Brain Minimum Checklist**
