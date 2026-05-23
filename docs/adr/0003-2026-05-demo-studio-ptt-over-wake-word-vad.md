# ADR-0003: 2026-05 demo 階段以 Studio Push-to-Talk 取代 Wake Word / VAD

- **Date**: 2026-05-23
- **Status**: accepted

## Context

PawAI 互動入口（engagement trigger）長期有兩個未解問題：

1. **VAD 延遲**：energy VAD 斷句 2-10s 飄移，是 E2E 對話最大瓶頸（synthesis §10 + 5/18 E2E demo 數據）。Silero VAD 替換已寫但未啟用
2. **Wake word 缺失**：v2 spec §7 規劃 OpenWakeWord「嗨 PawAI」自訓 100 樣本 + 3d 工程量

5/22 grill 中使用者點出：**PawAI Studio composer.tsx 已有 mic button**（push-to-talk UI 完整：isRecording / startRecording / stopRecording / AudioVisualizer），且 5/27 demo 主操作者就是照護人員端的 Studio 操作員。

替代方案考量過：
- (a) 用 wake word + VAD（v2 原規劃，3d 工程量 + 100 樣本訓練 + W3 才會動會撞 demo 固化期）
- (b) Studio push-to-talk 取代，wake word / VAD 暫不做
- (c) 兩者都做（wake word 給場景內長者主動互動 / push-to-talk 給 Studio 操作員）

## Decision

**2026-05 demo 階段**，PawAI 互動入口收斂為三源觸發抽象，**不做 wake word / VAD**：

| Engagement source | 用途 | 工程現況 |
|---|---|---|
| `studio_ptt` | Studio 操作員按 mic button 主動派遣 / 對話 | Studio UI 已有，差 ASR direct path（拔掉 VAD 跳過去）|
| `face_approach` | 場景內長者走近 PawAI 並 face 直視 | face_perception 已有，差訂閱 → engagement event publish |
| `gesture_ok` | 場景內長者比 OK 手勢觸發 | vision_perception 已有，差訂閱 → engagement event publish |

Engagement Gate 統一抽象**保留**（v2 spec §7 概念不廢），只是 source 從「wake_word + face + gesture」改為「studio_ptt + face + gesture」。

明確凍結：
- VAD 整段拆掉（不再 energy / 不切 Silero）
- Wake word 不訓練、不整合
- Engagement Gate 狀態機簡化：ATTENTIVE 進入由 engagement source 任一觸發、退出由 timeout 8s

工程量比較：原 v2 L2-G (3d) → 本 ADR (~1.5-2d) = **回收 1-1.5d** 給 nav / object。

## Consequences

**正面**：

- 5/27 demo 對話延遲從「VAD 2-10s + ASR 1s + LLM 1.5s」降為「按住 mic 即錄、放開即送 → ASR 1s + LLM 1.5s」
- 工程量回收 1-1.5d 給 nav / object 主線
- 「我們有思考過互動入口取捨」可作為對外敘事亮點（非「我們沒做 wake word」）
- 場景內長者主動互動仍可走 face / gesture（不依賴 wake word）

**負面**：

- 失去「嗨 PawAI」這種「像智慧音箱 / 像狗叫名字」的情感互動鏡頭——demo 旁白要主動 frame「我們選擇可控的互動入口」，否則觀眾會問為什麼沒做
- 場景內長者單獨在場（沒 Studio 操作員 + 不會 OK 手勢 + 不走近）時無法主動發起互動，由照護人員端 Studio 派遣涵蓋
- 長期 PawAI 走向「居家 / 助手」延伸（ADR-0002 平台身份層）若需要 always-on 互動，wake word 仍需重啟——屆時開 ADR-000X 加回

## Related

- v2 spec §7 Engagement Gate 設計（wake word 部分被本 ADR 取代，多源觸發抽象保留）
- ADR-0002 雙層敘事：本 ADR 限定 2026-06 demo 場景層，平台身份層保留 wake word 未來可能性
- Studio composer.tsx mic button：`pawai-studio/frontend/components/chat/composer.tsx` 已存在
- 未來若重啟 wake word，開新 ADR supersede 本 ADR 第三段「明確凍結」即可
