"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { SkillButtons } from "@/components/chat/brain/skill-buttons";
import { SkillTraceContent } from "@/components/chat/brain/skill-trace-content";

/**
 * /studio/dev — full-page dev panel for direct URL access.
 *
 * Same content as the sheet-mounted DevPanel, but rendered as a standalone
 * page (no nav, no chat). Useful for debugging without entering /studio
 * proper (e.g. monitoring brain proposals while user-facing UI is busy).
 */
export default function DevPage() {
  useEventStream();
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex h-12 items-center justify-between border-b border-[var(--nav-border)] px-5 shrink-0">
        <h1 className="text-sm font-semibold">Dev Mode</h1>
        <span className="text-xs text-muted-foreground">
          一般使用者請回到 <a href="/studio" className="underline hover:text-foreground">/studio</a>
        </span>
      </header>
      <div className="flex-1 overflow-y-auto">
        <SkillButtons />
        <div className="border-t border-[var(--sheet-border)]">
          <SkillTraceContent />
        </div>
      </div>
    </div>
  );
}
