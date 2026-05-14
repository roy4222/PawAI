# PawAI Brain

> **Status**: current(5/12 sprint 主線)
> **Date**: 2026-05-01
> **Scope**: PawAI 「怎麼理解、決策、說話、呈現」的單一真相層

---

## 一句話

**PawAI Brain 是把多模態感知(face / speech / gesture / pose / object)轉成 SkillPlan 的決策層,LLM 只提建議,Executive 才執行,所有實體動作都過 Safety Gate。**

---

## 目前主線(5/12 衝刺週)

- **Skill Registry** — 26 條 skill(Active 17 / Hidden 5 / Disabled 4 / Retired 1),OK 二次確認三層原則
- **LLM provider chain** — OpenRouter 主線(Gemini 3 Flash / DeepSeek V4 Flash / Qwen3.6 Plus eval) → OpenRouter fallback → Ollama qwen2.5:1.5b → RuleBrain
- **TTS provider chain** — Gemini 3.1 Flash TTS(audio tag,24kHz PCM)→ edge-tts → Piper
- **Persona** — 對齊 mission/README §2:居家互動 + 守護 + 多模態,正向語氣不列拒絕清單
- **Studio Brain Skill Console** — Brain Status Strip + Trace Drawer(Nav Gate / Depth Gate LED)+ Plan A/B 切換
- **Plan A / Plan B 切換** — 8 scene 雙版本,< 2 秒切換無感
- **Demo Storyboard v1** — 4:30 8 scene(System Ready → Nav Backbone → Personality → 熟人 → 手勢 → 物體 → Sensor Fusion → safety stop)

---

## 5/12 Demo 必做(對應 Storyboard Active 場景)

- `self_introduce`(6 步序列,Wow B)
- `greet_known_person`(熟人個人化問候)
- `wave_hello` / `wiggle` / `stretch`(手勢互動)
- `sit_along` / `careful_remind`(姿勢守護)
- `object_remark`(YOLO + HSV 顏色)
- `stranger_alert` + `stop_move`(陌生人 + safety stop)
- Brain 觸發 `nav_demo_point` / `approach_person`(Nav 由 navigation/ 主線實作)

---

## 文件導覽

> 5/12 衝刺期:大部分內容仍集中在 spec/plan,本 README 為入口導覽。

| 檔案 / 路徑 | 內容 |
|---|---|
| **入口頁(本檔)** | `docs/pawai-brain/README.md` |
| **架構總覽**(既有,未來搬入本目錄) | `docs/pawai-brain/architecture/overview.md` |
| **Phase A Brain MVS spec** | `docs/pawai-brain/specs/2026-04-27-pawai-brain-skill-first-design.md` |
| **PawClaw evolution spec** | `docs/pawai-brain/specs/2026-04-27-pawclaw-embodied-brain-evolution.md` |
| **5/12 Sprint design**(主線作戰地圖) | `docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md` |
| **Phase B Implementation Plan**(brain × studio 整合,5/4-5/8 任務) | `docs/pawai-brain/plans/2026-05-XX-phase-b-brain-studio.md`(尚未寫) |
| **介面契約** | `docs/contracts/interaction_contract.md` |
| **PawAI Studio 設計** | `docs/pawai-brain/studio/README.md` |

---

## Legacy / Archive

舊版研究、歷史決策、各模組 README 仍在以下原位:
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/` — 設計 spec 歷史(4/10 守護犬 / 4/11 home interaction / 4/27 brain MVS / pawclaw evolution / 5/01 sprint)
- `docs/pawai-brain/speech/` `docs/pawai-brain/perception/face/` `docs/pawai-brain/perception/gesture/` `docs/pawai-brain/perception/pose/` `docs/pawai-brain/perception/object/` — 各感知模組權威文件
- `docs/pawai-brain/studio/` — Studio 既有設計

本資料夾**只**維護 5/12 Demo 衝刺期 + 之後的主線版本;舊文件保留作歷史與引用,不重複維護。
