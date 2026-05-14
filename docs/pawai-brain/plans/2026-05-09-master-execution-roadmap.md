# 5/9 互動品質改善 Master Execution Roadmap

> **建立**：2026-05-09
> **Spec 來源**：`docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md`
> **Demo 硬底線**：5/13 場地驗 / 5/14 三連跑 / 5/18 demo

8 個 issue 的總執行排程。每條 branch 有獨立 plan 文件 + 獨立 PR。

---

## Branch 與覆蓋對應

| Branch | Plan 文件 | 覆蓋 issue | 主軸 | 工時 | 排程 |
|---|---|---|---|---|---|
| **A** `feat/wave0-p11-observability` | [`2026-05-09-wave0-p11-observability-foundation.md`](./2026-05-09-wave0-p11-observability-foundation.md) | **5（完整）** + **1（部分：跳句）** | TTS 不跳句 + Studio 看得到每句 + IE-node SAY source 標記 | ~8.5h | 5/10 |
| **B** `feat/persona-openclaw-lite` | TBD（5/10 evening 寫）| **2（完整）** + **3（併入）** | persona 拆 5 檔 + mode classifier + capability lazy + identity few-shot | ~1.5 天 | 5/11 |
| **C** `feat/asr-tw-and-context-reset` | TBD | **6（完整）** + **7（完整）** | OpenCC s2twp 雙入口 + reset 手動按鈕 + dev-only F5 flag | ~3h | 5/11-12 |
| **D** `feat/attention-policy` | TBD | **4（完整）** | 4 狀態 attention machine + dwell 1.5s + quiet 8s + dedup key 去 color | ~1 天 | 5/12 |
| **E** `spike/elevenlabs-tts` + `feat/tts-dual-route` | TBD | **1（完整音色軌）** | ElevenLabs Spike-Mini → Real → 雙軌路由 + audio_format served_by | 半天 + 半天 + 半天 | 5/11 spike-mini / 5/12 spike-real / 5/13 dual-route |
| **F** `feat/idle-mode`（post-demo）| TBD | **8（完整）** | P3-1a MVP + P3-1b Studio toggle + P3-1c LLM 接入 | 5h | 5/19+ |

---

## 依賴順序

```
Branch A (5/10)
  ├─ unblock: Branch B / C / D / E 的 Studio 觀測（看得到每句才能驗 persona/ASR/attention）
  └─ unblock: Branch B Phase 2-mini source 已落地，後續 3 publisher 可漸進補

Branch A → Branch B + C （並行）
Branch A → Branch D （在 B/C merge 後做，因為 D 改 brain_node 多）
Branch E spike-mini 可與 B/C/D 並行（不動主鏈）
Branch E spike-real / dual-route 在 spike-mini GO 後才開
Branch F 全 demo 後
```

**5/10-5/13 demo 前主線**：A + B + C + D + E（不含 F）= 6 issue 全解（issue 8 idle 不解）。

---

## 已 commit 的 spec 與 plan

```
spec: docs/pawai-brain/specs/2026-05-09-interaction-quality-improvements-design.md
  928e083  issue 1 B-lite 收斂
  4de63ed  issue 1 review 4 點
  7f0b4e9  TTS spec + rules cleanup
  df9f96d  issue 2 P1-4 OpenClaw-lite 重寫
  56ff7e0  issue 2 review 5 點
  574f556  issues 3-8 收尾
  551ca24  brainstorm 收尾 review 2 點

plan: docs/pawai-brain/plans/2026-05-09-wave0-p11-observability-foundation.md
  2f5d07f  Wave 0 + P1-1 plan
```

Branch B-F 的 plan 文件會在對應 branch 開工前寫（避免 spec 還在迭代時提前寫死）。

---

## 「打完 8 題」狀態追蹤

| # | Issue | Spec 解法位置 | 解決於 |
|---|---|---|---|
| 1 | TTS 音色 vs 延遲 | P0-1 + P2-2 + P2-3 | A（跳句）+ E（音色）|
| 2 | LLM 死板 | P1-4 OpenClaw-lite | B |
| 3 | LLM 不主動鏈式 | 併入 P1-4 1F+1G | B |
| 4 | 物體/人臉重複干擾 | P2-1 attention policy | D |
| 5 | Studio 顯示每句 | P0-2 + P1-1 | A |
| 6 | ASR 簡→繁 | P1-3 OpenCC s2twp | C |
| 7 | refresh reset context | P1-2 手動按鈕 + dev-only F5 | C |
| 8 | idle 待機 | P3-1 a/b/c | F (post-demo) |

A 完成後狀態：1 部分 + 5 完整 = 1.5/8。
A+B+C+D+E 完成後狀態（demo 前目標）：1+2+3+4+5+6+7 完整 = 7/8。
F 留 demo 後 = 8/8（issue 8 預設 off，僅展示模式啟用）。
