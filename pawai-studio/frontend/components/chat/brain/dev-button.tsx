"use client";

import { Suspense } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { Settings } from "lucide-react";
import { useSheetStore } from "@/stores/sheet-store";

function DevButtonInner() {
  const sp = useSearchParams();
  const pathname = usePathname();
  // Guard 1: only render when ?dev=1 is present.
  if (sp.get("dev") !== "1") return null;
  // Guard 2: hide on /studio/dev itself — that page IS the dev panel,
  // a floating ⚙ would be redundant / confusing.
  if (pathname === "/studio/dev") return null;
  const open = useSheetStore((s) => s.openSheet);
  return (
    <button
      type="button"
      onClick={() => open("dev")}
      className={
        "fixed bottom-4 right-4 z-30 flex h-11 w-11 items-center justify-center rounded-full " +
        "bg-[var(--dev-button-bg)] hover:bg-[var(--dev-button-hover-bg)] " +
        "transition-colors " +
        // Visible focus ring for keyboard nav.
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 " +
        "focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]"
      }
      style={{ transitionDuration: "var(--anim-dev-button-fade)" }}
      aria-label="開發者工具"
      title="開發者工具"
    >
      <Settings className="h-5 w-5" />
    </button>
  );
}

/**
 * DevButton — floating ⚙ in bottom-right corner.
 *
 * Renders ONLY when:
 *   1. URL has `?dev=1` query param, AND
 *   2. current pathname is NOT `/studio/dev` (which already shows the
 *      same dev tools full-page; a floating button would be redundant)
 *
 * Mounted once at studio-layout root so it works on /studio,
 * /studio/face, /studio/live, etc. — dev mode is session-wide.
 *
 * Wrapped in Suspense because Next App Router prod build requires a
 * Suspense boundary around any client component using `useSearchParams()`.
 */
export function DevButton() {
  return (
    <Suspense fallback={null}>
      <DevButtonInner />
    </Suspense>
  );
}
