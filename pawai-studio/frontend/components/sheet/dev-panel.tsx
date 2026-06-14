"use client";

import { SkillButtons } from "@/components/chat/brain/skill-buttons";
import { SkillTraceContent } from "@/components/chat/brain/skill-trace-content";
import { DemoPhaseButtons } from "@/components/operator/demo-phase-buttons";
import { OfflineToggle } from "@/components/operator/offline-toggle";

/**
 * DevPanel — Sheet content for the "dev" variant. Top half = Skill Console,
 * bottom half = Skill Trace + capability gates + plan toggle. The operator
 * manual FLOOR controls (plan4: five-scene phase buttons + offline toggle)
 * live here too — HIDDEN, reachable only via ?dev=1. They are the manual
 * fallback that ALWAYS works when auto-advance fails.
 *
 * Triggered via the floating ⚙ DevButton (only visible with ?dev=1) or by
 * direct URL `/studio/dev`.
 */
export function DevPanel() {
  return (
    <div className="flex flex-col">
      <SkillButtons />
      <div className="border-t border-[var(--sheet-border)]">
        <DemoPhaseButtons />
      </div>
      <div className="border-t border-[var(--sheet-border)]">
        <OfflineToggle />
      </div>
      <div className="border-t border-[var(--sheet-border)]">
        <SkillTraceContent />
      </div>
    </div>
  );
}
