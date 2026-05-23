# ADR-0001: PawAI 2026-06 POC 採非接觸式機構巡檢助理定位

- **Date**: 2026-05-23
- **Status**: accepted

## Context

2026-05 三場驗收暴露 PawAI 定位與安全張力：

- **5/18 葉承達**：機體 20kg、走路晃動、Go2 sport mode MIN_X 0.5m/s。明確警示「阿嬤拉手互動可能直接摔倒、骨折」「撞老人腿可能斷」。
- **5/20 雅文**：質疑「老人陪伴」use case 容錯率，認為老人對錯誤動作容忍度不一定高。
- **5/22 呂奇傑**：接受長照場域定位，但建議安全機制要作為 demo highlight（請翻跟斗 → 拒絕執行）。

定位張力：v2 spec amend 後主軸為「機構巡檢與互動助理 POC」，但若沒有明文化安全邊界，demo 影片很容易出現「PawAI 跟長者擊掌 / 摸頭 / 攙扶」這類高風險鏡頭——這類鏡頭表面上強化「為什麼是狗」的情感說服力，實際上把 6/18 demo 推向責任不清的灰色地帶。

替代方案考量過：(a) 強硬永久宣告 PawAI 永遠不做物理接觸；(b) 不立紅線靠 demo 排練約束。(a) 太早放棄未來可能性、(b) 紅線在多 agent / 接手者場景容易滑回「陪伴狗」敘事。本 ADR 取中間：**限定 2026-06 POC 階段**，留 future ADR 加 safety case 重啟物理接觸功能的空間。

## Decision

2026-06 POC / demo 階段，PawAI 定位為**非接觸式機構巡檢助理**：

- PawAI 負責**感知、提醒、回報、引導注意力**
- PawAI **不負責攙扶、碰觸、推拉、承重、安撫性肢體互動**
- 任何物理接觸型互動都視為 future work，**必須另開 ADR 加安全設計與驗證**才能放行

落地約束：

1. Demo 影片 / 簡報 / 對外材料不出現長者物理接觸 PawAI 鏡頭
2. PawAI 不主動靠近長者過近距離（具體閾值由 nav stack 既有 reactive_stop / depth_safety 涵蓋，本 ADR 不訂死數字）
3. 一切物理協助由照護人員執行

## Consequences

**正面**：

- 安全責任邊界清晰，無醫療級 / 物理協助宣稱包袱
- 同時解決葉承達 5/18 + 雅文 5/20 兩位老師質疑
- 「非接觸式」成核心對外口號，差異化更明確
- 多 agent / 接手者透過 CONTEXT.md → ADR-0001 能快速理解這條紅線
- 限定 POC 階段，不關死未來「物理互動」探索路徑

**負面**：

- 失去「PawAI 摸頭安撫 / 跟長者擊掌」這類情感鏡頭——這正是「為什麼是狗」最直觀的論據之一
- 未來想做「主動靠近 fallen 確認 / 攙扶 / 安撫」必須走新 ADR + safety case，多一道流程
- 部分競品（家用陪伴型機器人）能做的互動 PawAI 短期不能做，敘事比較強調「巡檢工作犬」而非「療癒犬」

## Related

- v2 spec：`docs/superpowers/specs/2026-05-22-pawai-may-june-north-star-v2-design.md`
- Review synthesis：`docs/pawai-demo/2026-05-review-synthesis.md`
- 未來若重啟物理接觸功能，請開 ADR-000X supersede 本 ADR 的相關條款（不必整篇 supersede）
