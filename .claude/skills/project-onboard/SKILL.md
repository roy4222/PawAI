---
name: project-onboard
description: 接手 PawAI、查專案架構或跨模組工作入口時使用。
---

# PawAI 上車

先讀根 AGENTS；依本次問題從 `docs/README.md`、`docs/architecture/README.md` 與相關模組 README 定位來源。不要求為單檔修正讀完專案。

| 問題 | 按需入口 |
|---|---|
| Brain／Studio | [brain](references/brain.md)、[studio](references/studio.md) |
| 感知 | [face](references/face.md)、[gesture](references/gesture.md)、[pose](references/pose.md)、[object](references/object.md) |
| 語音 | [speech](references/speech.md) |
| 導航避障 | [nav](references/nav.md) |
| 環境／驗證 | [environment](references/environment.md)、[validation](references/validation.md) |

Reference 是定位提示；規格看 `docs/contracts/`、`docs/architecture/`、`docs/adr/`，現況看程式及實際 artifact。`references/project-status.md` 是歷史快照，只在追溯舊事時查，不代表本輪優先序。日期、主機、GPU、部署版本從本次證據確認。

完成後直接回答使用者的問題，指出影響結論的未知與下一個可執行步驟。
