"use client";

import { Dialog } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface SheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  description?: string;
  children: ReactNode;
  /**
   * Visual side. Kept for backward compat — the actual layout is center modal
   * regardless of this prop. The old "right-side drawer" mode is retired
   * (see `docs/pawai-brain/studio/README.md` §「跳窗模式遷移」).
   */
  side?: "right" | "center";
  /** Optional className appended to the inner Popup card. */
  className?: string;
}

/**
 * Sheet — center modal built on Base UI Dialog primitive.
 *
 * Layout rules (5/5 redesign, replaces 5/4 right-drawer):
 * - All sizes: backdrop fades in, card scales in from 95% → 100% with fade
 * - Card: max-w-3xl, max-h-[85vh] (desktop) / max-h-[90vh] (mobile)
 * - Card scrolls internally if content overflows
 *
 * Inspired by PR #41 (Gua) pose history modal; chosen for "focus a single
 * panel" demo UX over the old right drawer that crowded the chat column.
 *
 * Accessibility:
 * - Esc / backdrop click → onOpenChange(false) (Base UI built-in)
 * - Focus trap inside Popup while open
 * - Backdrop dims chat to keep context visible (--sheet-backdrop, default 65% black)
 * - prefers-reduced-motion: transitions collapse to 0ms via
 *   --anim-sheet-slide CSS var (see globals.css)
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: SheetProps) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Backdrop
          className={cn(
            "fixed inset-0 z-40 bg-[var(--sheet-backdrop)] backdrop-blur-sm",
            "transition-opacity",
            "data-[ending-style]:opacity-0",
            "data-[starting-style]:opacity-0",
          )}
          style={{ transitionDuration: "var(--anim-sheet-slide)" }}
        />
        <Dialog.Popup
          className={cn(
            // Center the modal in viewport
            "fixed inset-0 z-50 flex items-center justify-center p-4 md:p-6",
            "pointer-events-none",
          )}
          style={{ transitionDuration: "var(--anim-sheet-slide)" }}
        >
          <div
            className={cn(
              // Card itself
              "pointer-events-auto flex w-full max-w-3xl flex-col",
              "max-h-[90vh] md:max-h-[85vh]",
              "rounded-2xl bg-[var(--sheet-bg)] text-foreground",
              "border border-[var(--sheet-border)] shadow-2xl",
              // Scale + fade transitions (open / closing states from Base UI)
              "transition-[opacity,transform]",
              "data-[starting-style]:opacity-0 data-[starting-style]:scale-95",
              "data-[ending-style]:opacity-0 data-[ending-style]:scale-95",
              // Default state (open)
              "opacity-100 scale-100",
              className,
            )}
            style={{ transitionDuration: "var(--anim-sheet-slide)" }}
          >
            {/* Header — title + close button */}
            <header className="flex items-start justify-between gap-2 px-4 py-3 border-b border-[var(--sheet-border)]">
              <div className="flex flex-col gap-0.5 min-w-0">
                {title && (
                  <Dialog.Title className="text-base font-semibold truncate">
                    {title}
                  </Dialog.Title>
                )}
                {description && (
                  <Dialog.Description className="text-xs text-[var(--pill-fg)]">
                    {description}
                  </Dialog.Description>
                )}
              </div>
              <Dialog.Close
                className="shrink-0 w-7 h-7 flex items-center justify-center rounded-md hover:bg-[var(--nav-icon-hover-bg)] transition-colors"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </Dialog.Close>
            </header>
            {/* Body — scrollable */}
            <div className="flex-1 overflow-y-auto">{children}</div>
          </div>
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
