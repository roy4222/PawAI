"use client";

import { useStateStore } from "@/stores/state-store";
import { GateChip } from "@/components/shared/gate-chip";
import { useTogglePlanMode } from "@/hooks/use-toggle-plan-mode";

/**
 * SkillTraceContent — pure trace + gate + plan content (no drawer chrome).
 *
 * Used by:
 *   - SkillTraceDrawer (legacy collapsible wrapper, retained for any
 *     pre-redesign callers)
 *   - DevPanel (Sheet content for ?dev=1)
 *   - /studio/dev page
 *
 * Avoids drawer-in-sheet nesting by isolating the data render from the
 * collapse UI.
 */
export function SkillTraceContent() {
  const brain = useStateStore((s) => s.brainState);
  const proposals = useStateStore((s) => s.brainProposals);
  const capability = useStateStore((s) => s.capability);
  const { planMode, togglePlanMode } = useTogglePlanMode();

  const planAclass =
    planMode === "A"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
      : "bg-amber-500/20 text-amber-300 border-amber-500/40";

  return (
    <div className="flex flex-col gap-3 px-4 py-3 text-xs">
      {/* Gate chips + Plan toggle */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <GateChip name="Nav" value={capability.nav_ready} />
          <GateChip name="Depth" value={capability.depth_clear} />
        </div>
        <button
          type="button"
          onClick={togglePlanMode}
          className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[10px] ${planAclass}`}
          title={
            planMode === "A"
              ? "Plan A：完整智能流程。點切到 Plan B（固定台詞）"
              : "Plan B：固定台詞。點切回 Plan A"
          }
        >
          Plan <span className="font-bold">{planMode}</span>
        </button>
      </div>

      {/* World flags */}
      {brain && (
        <div className="font-mono text-muted-foreground">
          World obs={String(brain.safety_flags.obstacle)} · emg=
          {String(brain.safety_flags.emergency)} · fall=
          {String(brain.safety_flags.fallen)} · tts=
          {String(brain.safety_flags.tts_playing)}
        </div>
      )}

      {/* Proposals list */}
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">
          Skill Trace · {proposals.length}
        </div>
        <div className="space-y-1">
          {proposals.length === 0 && (
            <div className="italic text-muted-foreground/60">尚無 brain proposal</div>
          )}
          {proposals.slice(0, 20).map((proposal) => (
            <div
              key={proposal.plan_id}
              className="truncate font-mono text-muted-foreground"
              title={`${proposal.selected_skill} · ${proposal.reason}`}
            >
              <span className="text-foreground">{proposal.selected_skill}</span>
              <span> · src={proposal.source}</span>
              <span> · prio={proposal.priority_class}</span>
              <span> · {proposal.reason}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
