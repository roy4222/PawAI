// PawAI Studio — Chat-first design tokens
//
// Added 2026-05-04 (Phase B — studio-chat-first-redesign step 1).
// Companion CSS variables live in `app/globals.css` under the
// "/* ── Chat-first redesign tokens (2026-05-04) */" block.
//
// Scope:
//   - Adds NEW tokens for chat / nav / sheet / dev mode.
//   - Does NOT override existing tokens (--primary purple, --foreground,
//     --background, etc.). Existing button / badge / card components keep
//     working unchanged.
//   - Dark mode only — no light mode this round.
//
// Spec: docs/pawai-brain/studio/specs/2026-05-04-studio-chat-first-redesign-design.md
// Rationale: docs/pawai-brain/studio/specs/2026-05-04-design-tokens.md

export const designTokens = {
  // ─────────────────────────────────────────────────────────────
  // Color (dark only). Hex values match the CSS variables in
  // globals.css; consumers should generally use the var(--name)
  // form via Tailwind (`bg-[var(--bubble-user-bg)]`) rather than
  // hex literals.
  // ─────────────────────────────────────────────────────────────
  color: {
    // Chat surfaces — reuse global background / surface for cohesion.
    chatBg: "var(--background)",
    chatSurface: "var(--surface)",

    // User bubble: vivid cyan (matches reference mock). High contrast against
    // dark base; reads as "you" without needing an avatar.
    bubbleUserBg: "#0EA5E9",
    bubbleUserFg: "#031019",

    // AI bubble: transparent + thin outline (ChatGPT/Claude.ai pattern). Keeps
    // chat stream visually quiet so the focus is on text.
    bubbleAiBg: "transparent",
    bubbleAiBorder: "rgba(255,255,255,0.08)",
    bubbleAiFg: "var(--foreground)",

    // Status pill (top centred "Brain 已就緒 obs:ok ...").
    pillBg: "rgba(255,255,255,0.04)",
    pillBorder: "rgba(255,255,255,0.08)",
    pillFg: "var(--muted-foreground)",
    pillFgEmphasis: "var(--foreground)",

    // Navbar (icon-only buttons).
    navBg: "var(--background)",
    navBorder: "rgba(255,255,255,0.06)",
    navIconFg: "var(--muted-foreground)",
    navIconHoverFg: "var(--foreground)",
    // Cyan accent for active feature button (matches user bubble).
    navIconActiveFg: "#0EA5E9",
    navIconHoverBg: "rgba(255,255,255,0.04)",

    // Sheet (right-side slide panel).
    sheetBg: "var(--surface)",
    sheetBorder: "var(--border)",
    sheetBackdrop: "rgba(0,0,0,0.45)",

    // Dev mode tokens (only visible with ?dev=1).
    devButtonBg: "rgba(124,107,255,0.15)",
    devButtonHoverBg: "rgba(124,107,255,0.25)",
    devBadgeBg: "#F59E0B", // amber — flags "(mock)" / "(no key)" labels.
    devBadgeFg: "#0B0700",

    // Tri-state capability gate chips (Nav / Depth in NavigationPanel).
    gateOk: "#22C55E",
    gateBlock: "#EF4444",
    gateUnknown: "#6B7280",
  },

  // ─────────────────────────────────────────────────────────────
  // Typography — Inter for Latin, Noto Sans TC / PingFang for 中文.
  // Inter is already declared in globals.css; we only define the
  // size scale here.
  // ─────────────────────────────────────────────────────────────
  font: {
    sans:
      '"Inter", "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", ' +
      "system-ui, -apple-system, sans-serif",
    mono: '"Fira Code", ui-monospace, "JetBrains Mono", monospace',
  },

  fontSize: {
    chatBody: "15px", // slightly larger than 14 default — long-form reading
    chatMeta: "11px", // timestamp / sender name above bubble
    navLabel: "12px", // tooltip / hamburger menu item
    sheetTitle: "16px",
    pill: "12px",
    devBadge: "10px",
  },

  lineHeight: {
    chatBody: 1.6, // 中英混排需要稍寬 leading
    chatMeta: 1.3,
    relaxed: 1.7,
  },

  fontWeight: {
    normal: 400,
    medium: 500,
    semibold: 600,
  },

  // ─────────────────────────────────────────────────────────────
  // Spacing & Layout
  // ─────────────────────────────────────────────────────────────
  layout: {
    navbarH: "48px", // h-12 — kept from current Topbar
    chatMaxW: "768px", // max-w-3xl — ChatGPT 級 line length
    chatPadX: {
      mobile: "16px",
      desktop: "32px",
    },
    bubbleMaxW: { desktop: "70%", mobile: "90%" },
    bubblePadX: "16px",
    bubblePadY: "12px",
    bubbleGapY: "12px", // vertical gap between consecutive bubbles
    bubbleRadius: "16px", // rounded-2xl
    pillRadius: "9999px",
    pillPadX: "12px",
    pillPadY: "4px",

    sheetW: {
      desktop: "380px",
      mobile: "100%", // full-width sheet on mobile (slide from bottom)
    },
    sheetRadius: "16px", // rounded-l-2xl on desktop
    sheetMobileRadius: "16px 16px 0 0", // top corners only when from-bottom

    inputMaxW: "768px",
    inputRadius: "20px",
    inputPadX: "16px",
    inputPadY: "12px",
    inputGap: "8px", // between input / mic / send

    devButtonSize: "44px", // 44x44 — meets a11y touch target
    devButtonOffset: "16px", // bottom-right corner offset
  },

  // ─────────────────────────────────────────────────────────────
  // Animation timing — keep all motion in the 120-300ms range
  // (UX guideline: micro-interactions feel snappy here).
  // Respect prefers-reduced-motion: components should fall back
  // to instant transitions.
  // ─────────────────────────────────────────────────────────────
  animation: {
    sheetSlide: "200ms cubic-bezier(0.32, 0.72, 0, 1)",
    messageAppear: "150ms ease-out",
    devButtonFade: "250ms ease",
    bubbleHover: "120ms ease",
    pillFade: "200ms ease",
    typingDot: "1.4s ease-in-out infinite", // 3-dot pulse for Brain thinking
    streamingShimmer: "1.8s ease-in-out infinite", // future LLM streaming UI
  },

  // ─────────────────────────────────────────────────────────────
  // Breakpoints — match Tailwind defaults for predictability.
  // < md = mobile rules below kick in.
  // ─────────────────────────────────────────────────────────────
  breakpoints: {
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
  },

  // ─────────────────────────────────────────────────────────────
  // Mobile behaviour rules (rendered below md breakpoint).
  // Components should branch on the `md` Tailwind variant rather
  // than reading these constants at runtime — kept here for spec
  // documentation only.
  // ─────────────────────────────────────────────────────────────
  mobile: {
    navHamburgerBreakpoint: "md", // < md → 6 buttons collapse to hamburger
    sheetSlideFrom: "bottom", // < md → bottom sheet, not right
    bubbleMaxW: "90%",
    chatPadX: "16px",
  },

  // ─────────────────────────────────────────────────────────────
  // Z-index scale — kept simple. Sheet sits above navbar so the
  // backdrop dims everything; dev button always above content but
  // below sheet so opening the sheet hides it.
  // ─────────────────────────────────────────────────────────────
  z: {
    devButton: 30,
    navbar: 40,
    sheetBackdrop: 49,
    sheet: 50,
  },
} as const;

export type DesignTokens = typeof designTokens;
