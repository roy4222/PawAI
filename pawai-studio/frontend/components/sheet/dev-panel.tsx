"use client";

import { SkillButtons } from "@/components/chat/brain/skill-buttons";
import { SkillTraceContent } from "@/components/chat/brain/skill-trace-content";
import { GestureToggle } from "@/components/chat/gesture-toggle";
import { DemoPhaseButtons } from "@/components/operator/demo-phase-buttons";
import { OfflineToggle } from "@/components/operator/offline-toggle";

/**
 * DevPanel — Sheet content for the "dev" variant. Top half = Skill Console,
 * bottom half = Skill Trace + capability gates + plan toggle. The operator
 * manual FLOOR controls (plan4: five-scene phase buttons + offline toggle +
 * D4 gesture toggle) live here too — HIDDEN, reachable only via ?dev=1. They
 * are the manual fallback that ALWAYS works when auto-advance fails.
 *
 * D4（pre-6/18 iter2）：GestureToggle 從主/觀眾視圖移到此處作操作員 fallback。
 * 手勢偵測 runtime 全程 ON，由 brain demo_phase=s4_gesture 的 phase gate 管
 * 範圍；此開關只是 gateway override，預設不點＝沿用既有行為。
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
      <div className="flex flex-col gap-1.5 border-t border-[var(--sheet-border)] p-3">
        <span className="font-mono text-[11px] text-zinc-400">
          手勢辨識開關（FLOOR）
        </span>
        <GestureToggle />
      </div>
      <div className="border-t border-[var(--sheet-border)]">
        <SkillTraceContent />
      </div>
    </div>
  );
}
