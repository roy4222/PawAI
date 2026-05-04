"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { Settings } from "lucide-react";
import { useSheetStore } from "@/stores/sheet-store";

function DevButtonInner() {
  const sp = useSearchParams();
  if (sp.get("dev") !== "1") return null;
  const open = useSheetStore((s) => s.openSheet);
  return (
    <button
      type="button"
      onClick={() => open("dev")}
      className="fixed bottom-4 right-4 z-30 flex h-11 w-11 items-center justify-center rounded-full transition-colors"
      style={{
        backgroundColor: "var(--dev-button-bg)",
        transitionDuration: "var(--anim-dev-button-fade)",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.backgroundColor = "var(--dev-button-hover-bg)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.backgroundColor = "var(--dev-button-bg)";
      }}
      aria-label="Open dev panel"
      title="Dev panel (?dev=1)"
    >
      <Settings className="h-5 w-5" />
    </button>
  );
}

/**
 * DevButton — floating ⚙ in bottom-right corner.
 *
 * Only renders when `?dev=1` is present in URL search params. Clicking it
 * opens the "dev" sheet variant via sheet-store (rendered by FeatureSheet).
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
