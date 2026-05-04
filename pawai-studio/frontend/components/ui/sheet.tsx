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
   * Visual side. Desktop default = right-slide; mobile (< md) overrides to
   * bottom-slide regardless of this prop. Mobile-aware behaviour is encoded
   * via Tailwind `md:` variants on the Popup className.
   */
  side?: "right";
  /** Optional className appended to the inner Popup. */
  className?: string;
}

/**
 * Sheet — slide-in side panel built on Base UI Dialog primitive.
 *
 * Layout rules (matches design tokens 2026-05-04):
 * - Desktop (≥ md): fixed right edge, 380px wide, slides from translate-x-full
 * - Mobile (< md): fixed bottom edge, full width, slides from translate-y-full,
 *   max-height 80vh
 *
 * Accessibility:
 * - Esc / backdrop click → onOpenChange(false) (Base UI built-in)
 * - Focus trap inside Popup while open
 * - Backdrop dims chat to keep it visible (45% black, --sheet-backdrop)
 * - prefers-reduced-motion: all transitions collapse to 0ms via
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
            "fixed inset-0 z-40 bg-[var(--sheet-backdrop)]",
            "transition-opacity",
            "data-[ending-style]:opacity-0",
            "data-[starting-style]:opacity-0",
          )}
          style={{ transitionDuration: "var(--anim-sheet-slide)" }}
        />
        <Dialog.Popup
          className={cn(
            "fixed z-50 flex flex-col bg-[var(--sheet-bg)] text-foreground",
            "border border-[var(--sheet-border)]",
            // Desktop: right slide. Mobile: bottom slide.
            "inset-x-0 bottom-0 max-h-[80vh] rounded-t-2xl",
            "md:inset-x-auto md:bottom-0 md:top-0 md:right-0 md:h-screen md:max-h-screen",
            "md:w-[var(--sheet-w)] md:rounded-t-none md:rounded-l-2xl",
            // Slide transitions — initial / open / closing states from Base UI.
            "transition-transform",
            "data-[starting-style]:translate-y-full md:data-[starting-style]:translate-x-full md:data-[starting-style]:translate-y-0",
            "data-[ending-style]:translate-y-full md:data-[ending-style]:translate-x-full md:data-[ending-style]:translate-y-0",
            // Default state (open) — no transform.
            "translate-y-0 md:translate-x-0",
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
        </Dialog.Popup>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
