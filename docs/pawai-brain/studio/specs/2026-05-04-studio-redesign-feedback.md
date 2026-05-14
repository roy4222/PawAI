# Studio Redesign — UI/UX Review Feedback

> **Status**: Step 10 review output (`ui-ux-pro-max` skill)
> **Date**: 2026-05-04
> **Scope**: 3 axes locked by user — chat / nav+sheet / dev mode
> **Files reviewed**: 7 components, 978 lines total
> **Methodology**: search.py rules（accessibility / touch / animation / focus）+ 手動程式碼比對 + design-tokens.md 一致性檢查

---

## Axis 1 — Main Chat View

**File**: `pawai-studio/frontend/components/chat/chat-panel.tsx` 427 行

### ✅ 沒問題

| 項目 | 證據 |
|---|---|
| Chat-only stream，brain debug widgets 全砍 | l1-22 imports 純淨 |
| max-w-3xl 居中 + 響應式 padding | l332 `mx-auto flex max-w-[var(--chat-max-w)]` |
| User bubble cyan / AI bubble transparent + outline | design token 一致（l339-345 / l390-395）|
| Audio tag verbatim 渲染 | l344, l397 直接 render `msg.text` 不 strip |
| Empty state 簡潔 | l300-323 只有 logo + 標題 + composer，沒 quick actions skill button |
| typing indicator 用 animate-bounce | l410-414，符合 `transform-performance` 規則 |
| TTS reply useEffect 有 race-fix arming（commit 3432d25）| l180-200 |
| Bubble gap-3 (12px) 對應 token `bubbleGapY: "12px"` | l332 |

### ⚠️ 建議修改（< 200 行）

| # | 嚴重度 | 問題 | 修法 | 估行數 |
|---|---|---|---|---|
| A1 | HIGH | **Send/Mic 按鈕 h-8 w-8 (32px) 違反 `touch-target-size` 44×44 規則** | l253-289：`h-8 w-8` → `h-9 w-9`（mobile-critical 的話 `h-10`）；`bottom-2.5` → `bottom-2` 配合 | ~6 |
| A2 | MEDIUM | **isThinking spinner 無 aria-live** — 螢幕閱讀器使用者 8s 等待中毫無回饋 | l403：包 `<div role="status" aria-live="polite">`，加 `<span className="sr-only">PawAI 正在思考</span>` | ~4 |
| A3 | LOW | DevButton mount 在 chat-panel 兩個分支裡（l305 + l330），重複 | 提到 `studio-layout.tsx` root 一次 mount 就好 | ~3（含刪除）|

### 📌 Follow-up（不阻塞收工）

- **Voice bubble 視覺冗餘**：l356 cyan bg + cyan border 是同色，border 視同隱形。可砍 border 或改 bg 區隔。design 取捨，非 a11y 必要。
- **disabled chat input 在 isThinking 時**：使用者打字會卡 8s。ChatGPT-like 但可考慮放開（讓使用者 queue 下一句）。Phase C 才考慮。

---

## Axis 2 — Navigation + Sheet

**Files**:
- `components/layout/nav-tabbar.tsx` 63 行
- `components/layout/feature-nav.tsx` 89 行
- `components/ui/sheet.tsx` 104 行
- `components/sheet/feature-sheet.tsx` 95 行

### ✅ 沒問題

| 項目 | 證據 |
|---|---|
| icon-only + `title` + `aria-label` 雙重保險 | feature-nav l46-83 每顆按鈕 |
| Esc / backdrop click 關閉 | sheet.tsx 用 Base UI Dialog 內建 |
| Focus trap inside Popup while open | Base UI Dialog 內建 |
| Mobile hamburger fallback < md | feature-nav l44-59 `md:hidden` |
| Mobile bottom-slide / Desktop right-slide | sheet.tsx l64-72，Tailwind `md:` variants 正確 |
| Single Sheet primitive driven by sheet-store | feature-sheet.tsx l70-94，no nested dialogs |
| z-index 分層 backdrop=40 / popup=50 | sheet.tsx l52, l61 |
| Dialog.Close 有 aria-label="Close" | sheet.tsx l93 |
| nav-menu 走獨立 inline branch（不入 PANELS map）| feature-sheet.tsx l84-92 + type `Exclude<SheetName, null \| "nav-menu">` |
| FeatureNav active state cyan 跟 sheet 開著 sync | feature-nav l64-78 |

### ⚠️ 建議修改（< 200 行）

| # | 嚴重度 | 問題 | 修法 | 估行數 |
|---|---|---|---|---|
| B1 | **CRITICAL (mobile)** | **手機 hamburger 唯一 nav 入口 h-8 w-8 (32px)** — 拇指誤觸率高 | feature-nav.tsx l51 `h-8 w-8` → `h-11 w-11`（44×44），icon `h-4` → `h-5` | ~3 |
| B2 | HIGH | **Desktop FeatureNav 6 顆按鈕 h-8 w-8** 同 touch target 問題 | l73 `h-8 w-8` → `h-9 w-9`（36×36 是桌面妥協值） | ~3 |
| B3 | HIGH | **icon-only 按鈕沒 focus ring** — `focus-states` 規則明確要求 | feature-nav.tsx + nav-tabbar.tsx LIVE link：加 `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--nav-icon-active-fg)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]` | ~6 |
| B4 | MEDIUM | **Sheet title `text-sm` (14px) 違反 design-tokens.md 規定 sheetTitle 16px** | sheet.tsx l81 `text-sm` → `text-base` | ~1 |
| B5 | MEDIUM | **LiveIndicator 1.5×1.5 (6px) 沒 aria-label，mobile (< sm) 是唯一連線指示** | shared/live-indicator.tsx 加 `role="status"` + `aria-label="connection status"` 或 visible text | ~2 |
| B6 | LOW | DevButton 同樣 fixed bottom-right 位置，sheet (z-50) 開時被 backdrop (z-40) 蓋 | 確認設計刻意（sheet 互斥），加註解即可 | 0（doc only）|

### 📌 Follow-up

- **Sheet swipe-to-close on mobile**：Base UI Dialog 有 `Handle` primitive 支援拖拉手把（PoC 看到的 export）。目前沒接，mobile 只能 Esc / backdrop 關。phase C 加分。
- **Sheet header 沒 visual hierarchy**：title + description 都左對齊，X close 在右。OK 但 reference mock 範本可加 backdrop blur / glass。視覺加分。

---

## Axis 3 — Dev Mode

**File**: `pawai-studio/frontend/components/chat/brain/dev-button.tsx` 50 行

### ✅ 沒問題

| 項目 | 證據 |
|---|---|
| 主畫面預設 0 dev 元素 | l9-10 `if (sp.get("dev") !== "1") return null` |
| Suspense 包 useSearchParams | l3, l46-49（Next App Router prod build 必需）|
| 44×44 touch target ✅（**唯一達標**）| l16 `h-11 w-11` |
| aria-label "Open dev panel" | l27 |
| `/studio/dev` 直連可用 | app/(studio)/studio/dev/page.tsx 51 行 |

### ⚠️ 建議修改（< 200 行）

| # | 嚴重度 | 問題 | 修法 | 估行數 |
|---|---|---|---|---|
| C1 | HIGH | **DevButton 沒 focus ring** | dev-button.tsx l13-32：加 `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 focus-visible:ring-offset-2 focus-visible:ring-offset-background` | ~1 |
| C2 | LOW | **Inline `onMouseEnter / Leave` 改 backgroundColor 不慣用** | 改 Tailwind `hover:bg-[var(--dev-button-hover-bg)]`，砍 onMouseEnter/Leave handler | ~6（含刪除）|
| C3 | LOW | **Tooltip "Dev panel (?dev=1)" 對 user 沒幫助**（已在 dev mode 才看得到此 button） | l28 `title="Dev panel (?dev=1)"` → `title="開發者工具"` | ~1 |

### 📌 Follow-up

- **DevButton 在 isThinking 時可被點**：點開 dev sheet 不影響 chat pending，OK。但 dev sheet 內部互動如果改 plan_mode、可能間接影響後續對話。phase C 看 demo 驗收狀況再決定。

---

## 累計修改量估算

| Axis | 估行數 |
|---|---|
| A1 (Send/Mic touch target) | 6 |
| A2 (isThinking aria-live) | 4 |
| A3 (DevButton dedupe) | 3 |
| B1 (hamburger 44×44) | 3 |
| B2 (FeatureNav 36×36) | 3 |
| B3 (icon focus rings) | 6 |
| B4 (Sheet title 16px) | 1 |
| B5 (LiveIndicator a11y) | 2 |
| C1 (DevButton focus ring) | 1 |
| C2 (DevButton hover idiom) | 6 |
| C3 (DevButton tooltip 文案) | 1 |
| **Total** | **~36 行** |

**遠低於 200 行門檻** → 建議今天進 commit I 全部修掉。

---

## Commit I 建議

**做：A1 + A2 + B1 + B2 + B3 + B4 + B5 + C1 + C2 + C3**（10 項，~33 行）

**重要性排序**：
1. **B1（mobile hamburger 44×44）** — Demo 上若有人用平板 / 手機示範，這是主要痛點
2. **B3 + C1（focus rings）** — 鍵盤無障礙必補
3. **A1 + B2（其他 touch targets）** — 桌面妥協 36×36 已可接受，但連手機 44×44 一起補比較整齊
4. **A2（aria-live）** — 螢幕閱讀器使用者體驗
5. **B4（sheet title 16px）** — token 一致性
6. **C2（hover idiom）** — code quality
7. **A3（DevButton dedupe）** — code quality
8. **B5（LiveIndicator aria-label）** — a11y
9. **C3（tooltip 文案）** — UX polish

**不做（follow-up）**：voice bubble 簡化、Sheet swipe-to-close、disabled input UX、Sheet glass effect — 都是 design optionality / phase C 範圍。

---

## 我推薦的 commit message

```
polish(studio): chat-first redesign a11y + touch target fixes (commit I)

post-step-H ui-ux-pro-max review 找到 10 個小修，全部 < 5 行 each、總和
~33 行。修完後主畫面、Sheet、Dev mode 三軸的 a11y 與 touch target 才真
完整對齊 spec v2.1 + design tokens。

Highlights:
- mobile hamburger 32px → 44px (mobile-critical, 拇指可用)
- 6 icon button + Live link + Send/Mic + DevButton 補 focus-visible ring
- Sheet title 14px → 16px（修 design-tokens.md 不一致）
- isThinking 加 aria-live="polite" + sr-only 文字
- DevButton hover 改用 Tailwind hover: idiom，砍 inline event handler
- LiveIndicator 加 role="status" + aria-label
- DevButton 從 chat-panel 兩個分支 dedupe 到 studio-layout root

Feedback doc: docs/pawai-brain/studio/specs/2026-05-04-studio-redesign-feedback.md
Plan: ~/.claude/plans/gemini-3-flash-preview-optimized-beacon.md (Step 10)
```

---

## 還要確認的 1 件事（給 user 決定）

**A3 改動（DevButton dedupe）會動 studio-layout.tsx**。雖然只 3 行，但會把 DevButton 的渲染權從 ChatPanel 移到 StudioLayout — 這代表 `/studio/face`、`/studio/live`、`/studio/dev` 直連時也會看到 ⚙ 按鈕（如果帶 `?dev=1`）。

兩種選擇：

**(a)** A3 照做：dev button 全 layout 共享，`/studio/face?dev=1` 也能浮 ⚙
**(b)** A3 跳過：只在 ChatPanel 渲染 dev button（現狀）

我傾向 (a) — dev mode 的 entry 是「你帶 ?dev=1 在這個 session 裡到處都能 debug」，邏輯更一致。但 (b) 更保守。

選 (a) 或 (b) 後我把 commit I 做完。

---

## 變更紀錄

- **2026-05-04**：初版，三軸 review 完成，10 個建議修改，預估 ~33 行 → 建議今天 commit I。
