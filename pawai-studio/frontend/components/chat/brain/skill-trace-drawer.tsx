"use client";

import { useEffect, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStateStore } from "@/stores/state-store";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import type { CapabilityTriState, PlanMode } from "@/contracts/types";

const TRI_LABEL: Record<CapabilityTriState, string> = {
  true: "OK",
  false: "BLOCK",
  unknown: "?",
};

const TRI_CLASS: Record<CapabilityTriState, string> = {
  true: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  false: "bg-red-500/20 text-red-300 border-red-500/40",
  unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/40",
};

function GateChip({ name, value }: { name: string; value: CapabilityTriState }) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[10px] ${TRI_CLASS[value]}`}
      title={`${name} = ${value}`}
    >
      {name}
      <span className="font-bold">{TRI_LABEL[value]}</span>
    </span>
  );
}

export function SkillTraceDrawer() {
  const [open, setOpen] = useState(false);
  const brain = useStateStore((state) => state.brainState);
  const proposals = useStateStore((state) => state.brainProposals);
  const capability = useStateStore((state) => state.capability);
  const planMode = useStateStore((state) => state.planMode);
  const setPlanMode = useStateStore((state) => state.setPlanMode);

  // Hydrate planMode from gateway on first mount.
  useEffect(() => {
    let cancelled = false;
    fetch(`${getGatewayHttpUrl()}/api/plan_mode`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && d?.mode) setPlanMode(d.mode as PlanMode);
      })
      .catch(() => {
        /* gateway not up yet — keep default */
      });
    return () => {
      cancelled = true;
    };
  }, [setPlanMode]);

  async function togglePlanMode() {
    const next: PlanMode = planMode === "A" ? "B" : "A";
    setPlanMode(next); // optimistic
    try {
      await fetch(`${getGatewayHttpUrl()}/api/plan_mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: next }),
      });
    } catch {
      /* rollback could go here; keep optimistic for Demo */
    }
  }

  const planAclass =
    planMode === "A"
      ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
      : "bg-amber-500/20 text-amber-300 border-amber-500/40";

  return (
    <div className="border-t border-border/50 bg-background/80">
      {/* Header bar — always visible. Gates + Plan toggle. */}
      <div className="flex items-center justify-between gap-2 px-4 py-1.5 text-[11px]">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="h-7 gap-1 rounded-none px-1 text-xs"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Skill Trace · {proposals.length}
        </Button>
        <div className="flex items-center gap-1.5">
          <GateChip name="Nav" value={capability.nav_ready} />
          <GateChip name="Depth" value={capability.depth_clear} />
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
      </div>

      {open && (
        <div className="max-h-52 overflow-y-auto px-4 pb-3 text-xs">
          {brain && (
            <div className="mb-2 font-mono text-muted-foreground">
              World obs={String(brain.safety_flags.obstacle)} · emg=
              {String(brain.safety_flags.emergency)} · fall=
              {String(brain.safety_flags.fallen)} · tts=
              {String(brain.safety_flags.tts_playing)}
            </div>
          )}
          <div className="space-y-1">
            {proposals.length === 0 && (
              <div className="text-muted-foreground/60 italic">尚無 brain proposal</div>
            )}
            {proposals.slice(0, 10).map((proposal) => (
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
      )}
    </div>
  );
}
