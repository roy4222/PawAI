"use client";

import { useStateStore } from "@/stores/state-store";
import { GateChip } from "@/components/shared/gate-chip";
import { useTogglePlanMode } from "@/hooks/use-toggle-plan-mode";
import type { ConversationTracePayload } from "@/contracts/types";

function statusToClass(status: string): string {
  switch (status) {
    case "accepted":
    case "ok":
      return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    case "accepted_trace_only":
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
    case "proposed":
      return "bg-slate-500/20 text-slate-300 border-slate-500/40";
    case "blocked":
    case "fallback":
    case "retry":
      return "bg-amber-500/20 text-amber-300 border-amber-500/40";
    case "rejected_not_allowed":
    case "error":
      return "bg-rose-500/20 text-rose-300 border-rose-500/40";
    case "needs_confirm":
      return "bg-yellow-500/20 text-yellow-300 border-yellow-500/40";
    case "demo_guide":
      return "bg-blue-500/20 text-blue-300 border-blue-500/40";
    default:
      return "bg-slate-500/20 text-slate-300 border-slate-500/40";
  }
}

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
  const traces = useStateStore((s) => s.conversationTraces);
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

      {/* Conversation Trace list */}
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground/70">
          Conversation Trace · {traces.length}
        </div>
        <div className="space-y-1">
          {traces.length === 0 && (
            <div className="italic text-muted-foreground/60">尚無 trace</div>
          )}
          {traces.slice(0, 20).map((t: ConversationTracePayload, i: number) => (
            <div
              key={`${t.session_id}-${t.ts}-${i}`}
              className={`rounded border px-2 py-1 font-mono text-xs ${statusToClass(t.status)}`}
              title={`${t.engine} · ${t.session_id}`}
            >
              <span className="font-medium">{t.stage}</span>
              <span className="opacity-60"> · </span>
              <span className="font-semibold">{t.status}</span>
              {t.detail ? (
                <>
                  <span className="opacity-60"> · </span>
                  <span className="truncate">{t.detail}</span>
                </>
              ) : null}
              <span className="ml-2 text-[10px] opacity-50">{t.engine}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
