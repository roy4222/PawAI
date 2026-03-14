# PawAI Studio Design Tokens

**版本**：v1.0
**建立日期**：2026-03-14
**適用範圍**：所有 Panel 元件必須遵守

> 所有人的 UI 必須使用這份 token，不可自行定義顏色/圓角/間距。
> 排版可自由發揮，但視覺語言必須一致。

---

## 1. 色板

### 基礎色

在 `globals.css` 的 `.dark` class 中定義，元件中使用 shadcn 的語意名稱。

| Token | CSS Variable | Hex | 用途 |
|-------|-------------|-----|------|
| background | `--background` | `#0A0A0F` | 全站背景 |
| surface | `--surface` | `#141419` | 卡片、Panel 背景 |
| surface-hover | `--surface-hover` | `#1C1C24` | 卡片 hover 狀態 |
| border | `--border` | `#2A2A35` | 邊框、分隔線 |

### 文字色

| Token | CSS Variable | Hex | 用途 |
|-------|-------------|-----|------|
| text-primary | `--foreground` | `#F0F0F5` | 主文字 |
| text-secondary | `--muted-foreground` | `#8B8B9E` | 次要文字（標籤、說明） |
| text-muted | — | `#55556A` | 提示文字、placeholder |

### 主色調

| Token | CSS Variable | Hex | 用途 |
|-------|-------------|-----|------|
| accent | `--primary` | `#7C6BFF` | 主色調（AI 紫） |
| accent-hover | `--primary-hover` | `#9585FF` | 主色 hover |
| accent-foreground | `--primary-foreground` | `#FFFFFF` | 主色上的文字 |

### 語意色

| Token | CSS Variable | Hex | 用途 |
|-------|-------------|-----|------|
| success | `--success` | `#22C55E` | 正常 / 連線中 / stable |
| warning | `--warning` | `#F59E0B` | 警告 / hold / loading |
| destructive | `--destructive` | `#EF4444` | 錯誤 / 離線 / critical |
| info | `--info` | `#3B82F6` | 資訊 / keep_alive / 待命 |

### 使用規則

```tsx
// 正確：使用語意名稱
<div className="bg-surface border-border text-foreground" />
<Badge className="bg-success text-white" />

// 錯誤：硬編碼顏色
<div className="bg-[#141419] border-[#2A2A35]" />
<Badge className="bg-green-500" />
```

---

## 2. 字體

| 用途 | 字體 | Tailwind class | 備註 |
|------|------|---------------|------|
| 標題/UI | Inter | `font-sans` | 預設，shadcn 內建 |
| 程式碼/數據 | Fira Code | `font-mono` | 延遲數值、JSON、程式碼 |
| 中文 | Noto Sans TC | fallback | `font-sans` 的 fallback |

### 字級

| 名稱 | Tailwind | 用途 |
|------|---------|------|
| xs | `text-xs` (12px) | 時間戳、微小標籤 |
| sm | `text-sm` (14px) | 次要文字、Panel 內文 |
| base | `text-base` (16px) | 主文字、聊天訊息 |
| lg | `text-lg` (18px) | Panel 標題 |
| xl | `text-xl` (20px) | 頁面標題 |

---

## 3. 間距與圓角

### 圓角

| Token | 值 | 用途 |
|-------|-----|------|
| `--radius` | `12px` | 卡片、Panel |
| `--radius-sm` | `8px` | 按鈕、Badge、輸入框 |
| `--radius-full` | `9999px` | 頭像、圓形指示器 |

### 間距

| 情境 | Tailwind | 值 |
|------|---------|-----|
| Panel 內部 padding | `p-4` | 16px |
| 元素間距 | `gap-3` | 12px |
| 小元素間距 | `gap-2` | 8px |
| Panel 之間 | `gap-4` | 16px |

---

## 4. 動畫

| 效果 | 持續時間 | Tailwind | 用途 |
|------|---------|---------|------|
| hover 色變 | 150ms | `transition-colors duration-150` | 按鈕、卡片 hover |
| Panel 展開 | 300ms | `animate-in slide-in-from-right-4 duration-300` | sidebar 面板出現 |
| Panel 展開（底部）| 300ms | `animate-in slide-in-from-bottom-4 duration-300` | bottom 面板出現 |
| 資料更新 | 300ms | `transition-all duration-300` | 數值變化 |
| pulse 脈衝 | 2s loop | `animate-pulse` | LiveIndicator、狀態點 |
| bounce 思考 | loop | `animate-bounce` | ChatPanel 思考指示器 |

### 尊重 reduced-motion

```tsx
// 所有動畫都要加這個
className="motion-safe:animate-pulse"
className="motion-safe:transition-all motion-safe:duration-200"
```

---

## 5. 共用元件規範

每個 Panel 必須使用以下共用元件，不可自行重寫。

### PanelCard

```tsx
// 用法
<PanelCard title="人臉辨識" icon={<User />} status="active">
  {/* 你的 Panel 內容 */}
</PanelCard>

// 規範
// - 固定 header：icon + title + StatusBadge + 收合按鈕
// - 背景：bg-card
// - 邊框：border-border/50
// - 圓角：rounded-xl
// - padding：p-3（header）、p-3 pt-0（content）
```

### StatusBadge

```tsx
<StatusBadge status="active" />   // 綠色 + pulse
<StatusBadge status="loading" />  // 黃色 + pulse
<StatusBadge status="error" />    // 紅色
<StatusBadge status="inactive" /> // 灰色
```

### EventItem

```tsx
<EventItem
  timestamp="14:32:05"
  eventType="identity_stable"
  source="face"
  summary="偵測到小明（92%）"
/>
// hover 時背景變 surface-hover
// 點擊時高亮 + 展開對應 Panel
```

### MetricChip

```tsx
<MetricChip label="距離" value={1.2} unit="m" />
<MetricChip label="信心度" value={92} unit="%" trend="up" />
// trend: "up" 綠色箭頭 | "down" 紅色箭頭 | "stable" 無箭頭
```

### LiveIndicator

```tsx
<LiveIndicator active={true} />
// 綠色圓點 + pulse 動畫
// active=false 時灰色、無動畫
```

---

## 6. Panel 尺寸規範

| 位置 | 最小寬度 | 最大寬度 | 高度 |
|------|---------|---------|------|
| sidebar | 360px | 360px | 自適應 |
| bottom | 100% | 100% | 200-300px |
| main (Chat) | 剩餘空間 | 剩餘空間 | 100vh - topbar |

### 響應式

| 螢幕 | 行為 |
|------|------|
| >= 1200px | sidebar 展開，完整 layout |
| 768-1199px | sidebar 改為可收合的 tabs |
| < 768px | 僅 Chat，底部 tab 切換 Panel |

---

## 7. 全域樣式

### Scrollbar

自訂 scrollbar：6px 寬、圓角、背景透明、thumb 用 `border` 色。

### 文字選取

選取文字背景為 `rgba(124, 107, 255, 0.25)`（primary 的 25% 透明度）。

---

*最後更新：2026-03-14*
