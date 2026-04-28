"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStateStore } from "@/stores/state-store";

export function SkillTraceDrawer() {
  const [open, setOpen] = useState(false);
  const brain = useStateStore((state) => state.brainState);
  const proposals = useStateStore((state) => state.brainProposals);

  return (
    <div className="border-t border-border/50 bg-background/80">
      <Button
        type="button"
        variant="ghost"
        size="sm"
        className="h-8 w-full justify-start gap-1 rounded-none px-4 text-xs"
        onClick={() => setOpen((value) => !value)}
      >
        {open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
        Skill Trace · {proposals.length} proposals
      </Button>
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
            {proposals.slice(0, 10).map((proposal) => (
              <div key={proposal.plan_id} className="truncate font-mono text-muted-foreground">
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
