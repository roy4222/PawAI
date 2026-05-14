# Studio UX Polish — 設計規格

> **Status**: draft
> **Date**: 2026-05-10
> **Spec ID**: Spec 6 of 6（demo-quality roadmap）
> **Scope**: Studio 前端 demo 體驗強化：scroll 行為、五功能視角、demo 操作面板
> **執行視窗**：demo 前若 5/9 fix 無重現 → 整份 spec 可砍 / 延後
> **Owner**: Roy
> **依據**：
> - `pawai-studio/frontend/components/chat/chat-panel.tsx`
> - `docs/pawai-brain/studio/README.md`
> - 5/9 evening Round 2 commit `87e2d5d`（stick-to-bottom 已修）

---

## 1. 範圍：3 件事

### 1.1 P0：Chat scroll 行為（**5/9 已修，待驗**）
- 5/9 commit `87e2d5d`：30px tolerance + scroll listener
- demo 前再實測 1 次，無重現可砍此項

### 1.2 P1：五功能視角 sidebar
- demo 時評審可在 dev sidebar 看：
  - 人臉 panel：當前識別到誰、confidence
  - 語音 panel：ASR 文字、intent
  - 手勢 panel：last detected gesture
  - 姿勢 panel：last detected pose
  - 物體 panel：scene 內 object list

### 1.3 P2：Demo 操作面板
- demo 主控介面：
  - Brain Status Strip（已有）
  - 一鍵觸發 skill button：self_introduce / wave_hello / wiggle / stretch / sit_along
  - **「下一步引導」hint**：demo 流程 8 步檢核 list
  - 一鍵 reset context（5/9 已有 button）

---

## 2. 非目標

❌ 不做：
- Studio mobile 版（demo 用筆電）
- 多語言切換（demo 中文）
- 主題切換（dark mode 已有）
- WebRTC 視訊串流到 Studio（用 Foxglove 即可）
- Studio 控制 Go2 動作（違反單一動作出口）

---

## 3. P0：scroll 行為驗證

### 3.1 5/9 fix 設計
```typescript
// chat-panel.tsx (commit 87e2d5d)
const STICK_TO_BOTTOM_TOLERANCE = 30; // px
useEffect(() => {
  const el = scrollRef.current;
  if (!el) return;
  const handleScroll = () => {
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShouldStickToBottom(distance < STICK_TO_BOTTOM_TOLERANCE);
  };
  el.addEventListener("scroll", handleScroll);
  return () => el.removeEventListener("scroll", handleScroll);
}, []);
```

### 3.2 驗證測試
- 5+ 句連續對話 → 自動滾到底
- 手動 scroll up 看舊訊息 → 不被打斷
- scroll 到中間後新訊息進來 → 不強拉底
- 5+ 次往返 → 行為一致

**若無重現**：本 spec P0 完成，砍掉。

---

## 4. P1：五功能視角

### 4.1 設計
sidebar 已有 5 個 dev panel（face/speech/gesture/pose/object/live），但是：
- 各自獨立，demo 時切來切去很亂
- 沒有「最近活動」timeline 整合

### 4.2 改進
新增「Demo Overview」panel：
```
┌─ Last Detection (10s window) ──┐
│ 👤 Face: Roy (0.92)             │
│ 🎤 ASR: "你好"                   │
│ 🖐️ Gesture: thumbs_up (0.95)    │
│ 🧍 Pose: standing               │
│ 🥤 Object: cup × 2 (red, white) │
└──────────────────────────────────┘
```

10 秒 sliding window，主訊息整合在一張 card。

**工時**：1 天

---

## 5. P2：Demo 操作面板

### 5.1 8 步 demo 流程 hint
```
Demo Flow Checklist
├ [ ] S0 PawAI 待命（Idle）
├ [ ] S1 「你會什麼」（Capability question）
├ [ ] S2 「介紹一下」（Self-showcase）
├ [ ] S3 揮手（Gesture demo）
├ [ ] S4 「搖一下」+ OK（Confirm flow）
├ [ ] S5 「陪我坐一下」（Pose interaction）
├ [ ] S6 看杯子 / 椅子（Object remark）
├ [ ] S7 跌倒模擬（Safety alert）
└ [ ] S8 「停」（Safety stop）
```

每步點擊 → 自動傳預設 prompt 觸發（不影響真實 ASR）。
完成自動勾選。

**工時**：1.5 天

---

## 6. 驗收

### P0
- scroll 5+ 來回測試一致

### P1
- Demo Overview panel 5 種事件都能 10s 內顯示
- 切到 sidebar 不丟失主對話

### P2
- 8 步 checklist 一鍵觸發成功率 ≥90%
- demo 主操作員（Roy）可一螢幕完成全流程

---

## 7. 實作分階段

| Phase | 內容 | 工時 | 何時 |
|---|---|---|---|
| P0 | scroll 重現驗證（無 → 砍）| 0.5d | demo 前 |
| P1 | Demo Overview panel | 1d | demo 後 |
| P2 | Demo flow checklist | 1.5d | demo 後 |

**P0 總計**：0.5 天（可能 0 天）；**P1+P2 總計**：2.5 天（demo 後）

---

## 8. 後續 spec 銜接
- Spec 1：self-showcase 主場 → 透過 Demo Overview 視覺化展示
- Spec 2-5：各 demo 的 perception event 都會餵 Demo Overview
