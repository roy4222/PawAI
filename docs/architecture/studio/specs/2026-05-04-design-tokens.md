# PawAI Studio Design Tokens — 2026-05-04

> **Status**: step 1 of approved chat-first redesign spec (`2026-05-04-studio-chat-first-redesign-design.md` v2.1)
> **Source files**: `pawai-studio/frontend/lib/design-tokens.ts` + `pawai-studio/frontend/app/globals.css` 「Chat-first redesign tokens」block
> **Skill used**: `ui-ux-pro-max` `--design-system` (style: AI-Native UI, palette: minimal black + accent, typography: Inter)

---

## 1. 設計脊椎一句話

> **chat 是主戲、其他 chrome 越輕越好；六個 feature panel 是 sheet 不搶 focus；dev tools 預設不存在於主畫面。**

每個 token 都圍繞這句話設計。reference mock（ChatGPT/Claude.ai 風）已是業界證明過的對話介面架構。我們只在情境上加：cyan accent（呼應 Go2 / 守護犬）、tri-state capability chip（Nav / Depth）、dev mode opt-in。

---

## 2. Token 分類與 rationale

### 2.1 Bubble color — 不對稱才能看清楚誰在說

| token | 值 | rationale |
|---|---|---|
| `--bubble-user-bg` | `#0EA5E9` cyan-500 | 與整體 dark base 反差大、視覺上抓得住。**色相和現有 `--primary` (#7C6BFF purple) 不同**，避免和系統按鈕混淆 |
| `--bubble-user-fg` | `#031019` | cyan 上的對比 ≥ 7:1，超過 WCAG AAA |
| `--bubble-ai-bg` | `transparent` | 重 chrome 是反 AI-native 設計（`ui-ux-pro-max` 直接列為 antipattern）。AI 訊息靠細 outline 即可分隔 |
| `--bubble-ai-border` | `rgba(255,255,255,0.08)` | 暗背景上的細白線，剛好可見不搶眼 |
| `--bubble-ai-fg` | `var(--foreground)` | 重用全局 `#F0F0F5` |

**為什麼不用既有 `--primary` (purple)** 給 bubble：purple 已經是按鈕 / focus ring / sidebar 的主色。bubble 也用 purple 等於整個 UI 是同一坨色，視覺層次崩。Cyan 是 sub-accent，只給 chat 領域用。

### 2.2 Pill color — 要看得到、但別搶 chat focus

| token | 值 | rationale |
|---|---|---|
| `--pill-bg` | `rgba(255,255,255,0.04)` | 4% 白覆蓋於 dark base = 一層淡淡的 glass。在 ChatGPT 的「上下文 chip」也是這量級 |
| `--pill-border` | `rgba(255,255,255,0.08)` | 邊框比 bg 多 4%，視覺上能看出形狀但不刺眼 |
| `--pill-fg` | `var(--muted-foreground)` `#8B8B9E` | 文字默認 muted；只有當 emphasis（如「Brain 待命中」狀態變化）才升級 |

### 2.3 Navbar — icon-only 是抓得住的安靜

| token | 值 | rationale |
|---|---|---|
| `--nav-border` | `rgba(255,255,255,0.06)` | 比 sheet border 還淡 — nav 應該感覺像「漂浮在 base 之上」而不是分區 |
| `--nav-icon-fg` | `var(--muted-foreground)` | default 灰，跟周遭吵不起來 |
| `--nav-icon-hover-fg` | `var(--foreground)` | hover 升白 — 對使用者「點得下去」的明確 affordance |
| `--nav-icon-active-fg` | `#0EA5E9` | 開著的 sheet 對應的 nav icon 用 cyan 強調，跟使用者在 chat 互動時看到的 cyan 是同一色 |
| `--nav-icon-hover-bg` | `rgba(255,255,255,0.04)` | 微弱的 hover background，比純色變色 hover 更柔軟 |

**沒有 active state 還顯示 dot/underline**：傳統 nav 用 underline 來表示「你在這頁」。但這裡點 button 是開 sheet 不是切頁，underline 反而會誤導。改成 active = sheet 還開著 → icon 變 cyan → sheet 關 = icon 回灰。

### 2.4 Sheet — 右側 380px，slide 200ms

| token | 值 | rationale |
|---|---|---|
| `--sheet-bg` | `var(--surface)` `#141419` | 比 base `#0A0A0F` 亮一階；視覺上是「升起來的層」 |
| `--sheet-border` | `var(--border)` `#2A2A35` | 跟 base 邊界明確分隔，不混色 |
| `--sheet-backdrop` | `rgba(0,0,0,0.45)` | 45% 黑遮住 chat — chat 還隱約看得到（不打斷對話 focus），但 sheet 是當下主角 |
| `--sheet-w` (TS only) | `380px` desktop / `100%` mobile | 夠裝面板（face track card / pose 圖 / nav gates），不會壓到 chat |
| `--sheet-radius` | `16px` 左側 desktop / 上方 mobile | rounded-l-2xl — 跟 bubble radius 一致，視覺有韻律 |
| `--anim-sheet-slide` | `200ms cubic-bezier(0.32, 0.72, 0, 1)` | iOS / Linear 用的 spring-ish curve；200ms 是 micro-interaction 上限，再長就感覺鈍 |

**為什麼桌面右側 / mobile 底部**：右側 slide 在桌面是 panel pattern（不打斷主內容），底部 slide 在 mobile 是原生 app pattern（拇指能搆到 close button）。

### 2.5 Dev mode — 預設不存在、opt-in 才出現

| token | 值 | rationale |
|---|---|---|
| `--dev-button-bg` | `rgba(124,107,255,0.15)` | 重用全局 primary purple 的 15% — 一看就知道是「系統工具」不是 chat 互動 |
| `--dev-button-hover-bg` | `rgba(124,107,255,0.25)` | hover 升到 25% — 不過度但有反應 |
| `--dev-badge-bg` | `#F59E0B` amber | mock reply / no-key 標記用警示色，使用者一看就知道「現在不是真 LLM 在回」 |
| `--dev-badge-fg` | `#0B0700` | amber 上 4.5:1 接近黑色保證對比 |

**沒帶 `?dev=1` 主畫面 0 dev 元素**：這是設計上的硬決定。如果 `?dev=1`，右下角才浮一個 ⚙ 按鈕（44×44px 滿足 a11y touch target）。

### 2.6 Capability gate — 三色 chip 一眼分辨

| token | 值 | rationale |
|---|---|---|
| `--gate-ok` | `#22C55E` green-500 | 全球 ok 訊號色，重用既有 `--success` |
| `--gate-block` | `#EF4444` red-500 | 全球 stop 訊號色，重用既有 `--destructive` |
| `--gate-unknown` | `#6B7280` gray-500 | 灰是「沒有資訊」的中性色，不是「壞」也不是「好」。**這個 token 重要**：plan v2 §1.2 user 提到 tri-state 不可混用 false 和 unknown |

---

## 3. Typography

### 3.1 Font family

```
"Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", system-ui, sans-serif
```

- **Inter** 是 AI-Native UI / dashboard 的事實標準（OpenAI / Linear / Notion 都用）
- **Noto Sans TC** 在 Google Fonts 是免費中文 fallback，跟 Inter x-height 接近不會有 baseline 錯位
- **PingFang TC** 給 macOS / iOS 用戶最佳化
- **Microsoft JhengHei** Windows fallback
- 順序保證每個平台都有最佳 native 字體

Inter 已在 `globals.css` 的 `body` font-family 宣告，所以 chat 直接繼承不需重複設定。

### 3.2 Size scale

| token | px | 用途 | rationale |
|---|---|---|---|
| `chatBody` | 15 | bubble 內文 | 14 太小（mobile 容易壓力），16 又像系統訊息。15 是聊天 app 的舒適值 |
| `chatMeta` | 11 | timestamp + 名字 | 比 body 小 4px 視覺降階。低於 11 在 retina 上會糊 |
| `navLabel` | 12 | tooltip / hamburger 項目 | nav 是次要資訊；12 比 muted text 默認 13 再小一階 |
| `sheetTitle` | 16 | sheet 頂部標題 | sheet 是「主導入口」需要明顯 |
| `pill` | 12 | "Brain 已就緒" | 跟 navLabel 同階 |
| `devBadge` | 10 | "(mock)" / "(no key)" | 標記用最小可讀字 |

### 3.3 Line height

| token | 值 | 為什麼 |
|---|---|---|
| `chatBody` | 1.6 | 中英混排需要 1.5–1.75（`ui-ux-pro-max` UX rule `line-height` 直接點名 1.5–1.75）。1.6 是中間值，CJK reading 比較舒服 |
| `chatMeta` | 1.3 | 元資訊不需要寬 leading，1.3 緊湊省空間 |
| `relaxed` | 1.7 | sheet panel 內描述文字用 |

---

## 4. Layout constants

### 4.1 Width / max-w

| token | 值 | rationale |
|---|---|---|
| `chatMaxW` | 768px (`max-w-3xl`) | UX rule `line-length` 限 65–75 字元 / 行；15px Inter @ 768px ≈ 70 字元 |
| `bubbleMaxW` desktop | 70% of chat container | 留 30% 給 ChatGPT 風的「對話一邊靠邊」感；100% 會看起來像 system message |
| `bubbleMaxW` mobile | 90% | 手機螢幕窄，70% 太擠 |
| `sheetW` desktop | 380px | 装得下大部分 panel content；460+ 開始壓到 chat |
| `sheetW` mobile | 100% | bottom sheet 常規做法 |
| `inputMaxW` | 768px | 跟 chatMaxW 對齊，視覺一致 |

### 4.2 Height / spacing

| token | 值 | rationale |
|---|---|---|
| `navbarH` | 48px (`h-12`) | 跟現有 Topbar 一致，不破壞既有 layout |
| `bubblePadX` | 16px | 對應 16-grid 系統 |
| `bubblePadY` | 12px | 緊湊但不擠；ChatGPT 大約 px-4 py-3 |
| `bubbleGapY` | 12px | 連續訊息間 vertical rhythm |
| `bubbleRadius` | 16px (`rounded-2xl`) | 大圓角 = 友善、AI；小圓角 = 工程 dashboard |
| `pillRadius` | 9999px | full pill — 跟一條訊息對比強 |
| `inputRadius` | 20px | 比 bubble 再大一階，input 是「主互動點」 |
| `devButtonSize` | 44×44px | 滿足 `touch-target-size` UX rule |
| `devButtonOffset` | 16px | bottom-right 距邊 16px = 安全區 |

---

## 5. Animation rules

### 5.1 Duration scale

所有 micro-interaction 在 120–300ms（UX rule `duration-timing`）：

| 用途 | 時長 | curve |
|---|---|---|
| sheet 滑入 / 退出 | 200ms | `cubic-bezier(0.32, 0.72, 0, 1)` (iOS-spring) |
| message 進入 chat | 150ms | `ease-out` — 快速但有減速感 |
| dev button fade | 250ms | `ease` — 出現 / 消失較不重要，可慢一點 |
| bubble hover | 120ms | `ease` — 最快 hover feedback |
| pill 變化 | 200ms | `ease` |
| typing dot pulse | 1.4s | `ease-in-out infinite` — 不是 micro-interaction |
| streaming shimmer (預留) | 1.8s | `ease-in-out infinite` |

### 5.2 Performance — `transform` / `opacity` only

UX rule `transform-performance` 強制：所有動畫只能改 `transform` 或 `opacity`，**禁止** width / height / margin / padding 動畫（強制 reflow）。

例如 sheet slide：
```css
.sheet { transform: translateX(100%); }
.sheet[data-open] { transform: translateX(0); }
```
**不要** `width: 0 → 380px`。

### 5.3 `prefers-reduced-motion`

`globals.css` 的 `@media (prefers-reduced-motion: reduce)` 區塊把所有 chat 動畫塌成 0ms。元件不需要額外處理 — 直接讀 `--anim-*` CSS var 就會自動退讓。

---

## 6. Mobile rules

低於 `md` (768px) breakpoint 時：

| 元件 | 桌面 | 手機 |
|---|---|---|
| Navbar 6 個 icon | row 排列 + tooltip | 全收進 hamburger menu，每項 `icon + 中文 label` |
| Sheet | 從右側滑入，380px 寬 | 從底部滑入，100% 寬 |
| Bubble max-w | 70% | 90% |
| Chat container padding-x | 32px | 16px |
| Dev button | 44×44px bottom-right | 同 |

實作上元件用 Tailwind 的 `md:` 變體切換，**不要** 在 runtime 讀 `breakpoints` 常數做 JS-side branching。

---

## 7. 不在這輪設計範圍

- **Light mode** — Demo 是 dark only，不浪費這輪時間做 light（user §5 明確 dark mode only）
- **Theme customisation UI** — 不做使用者選色
- **AB-test 多版本** — 只一個 token set，不做替代主題
- **Brand logo / illustration** — 用 `lucide-react PawPrint` icon，無 custom logo

---

## 8. 後續使用方式

### 8.1 Component 寫法

```tsx
// 用 CSS var (preferred — runtime 可被 prefers-reduced-motion override)
<div className="bg-[var(--bubble-user-bg)] text-[var(--bubble-user-fg)]
                rounded-[var(--bubble-radius)] px-[var(--bubble-pad-x)] py-[var(--bubble-pad-y)]
                transition-colors duration-[var(--anim-bubble-hover)]" />

// 或用 TS const (preferred for layout calculations)
import { designTokens } from "@/lib/design-tokens";
<div style={{ maxWidth: designTokens.layout.chatMaxW }} />
```

### 8.2 Tailwind v4 arbitrary value

Tailwind v4 + 我們的 `@theme inline` 設定下，CSS var 可以直接用 `bg-[var(--name)]` 形式。
不要為了「方便」把 cyan 寫進 `tailwind.config` 主 palette — chat tokens 是局部命名空間，不該汙染全局。

### 8.3 Storybook / 視覺 review

實作 step 4–7 時，每個元件至少要有一個 dev page 範例（可放 `/studio/dev` 或單一 `/storybook` 頁），用本 token 表逐項驗收。

---

## 9. 變更紀錄

- **2026-05-04**：初版，從 spec v2.1 step 1 產出。
