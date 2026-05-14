"use client";

import { SkillButtons } from "@/components/chat/brain/skill-buttons";
import { SkillTraceContent } from "@/components/chat/brain/skill-trace-content";

/**
 * DevPanel — Sheet content for the "dev" variant. Top half = Skill Console,
 * bottom half = Skill Trace + capability gates + plan toggle.
 *
 * Triggered via the floating ⚙ DevButton (only visible with ?dev=1) or by
 * direct URL `/studio/dev`.
 */
export function DevPanel() {
  return (
    <div className="flex flex-col">
      <SkillButtons />
      <div className="border-t border-[var(--sheet-border)]">
        <SkillTraceContent />
      </div>
    </div>
  );
}
