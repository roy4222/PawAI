# Architecture Decision Records (ADR)

每個架構決策一份 markdown。檔名格式 `NNNN-kebab-case-title.md`（e.g. `0001-langgraph-over-rule-engine.md`）。

## 與 `docs/superpowers/specs/` 的分工
- **`docs/superpowers/specs/`**：歷史設計規格、Spike 計畫、北極星文件 — 通常含「為什麼這樣設計、後續細節怎麼跑」的長篇規格
- **`docs/adr/`**（本資料夾）：精煉的「我們決定 X、因為 Y、後果 Z」記錄 — 一次一個決策、可被未來提案 supersede

新決策從這裡開始；spec 是 ADR 的長版背景。

## 模板
```markdown
# ADR-NNNN: <decision title>

- **Date**: YYYY-MM-DD
- **Status**: proposed | accepted | superseded by ADR-XXXX
- **Context**: 為何需要這個決策？前提是什麼？
- **Decision**: 我們決定怎麼做。
- **Consequences**: 接受後會發生什麼（正反面）？
```
