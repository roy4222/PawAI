"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useStateStore } from "@/stores/state-store";
import { SkillTraceContent } from "./skill-trace-content";

/**
 * SkillTraceDrawer — legacy collapsible drawer wrapper.
 *
 * Post-step-G this is no longer mounted in ChatPanel. Retained for any
 * pre-redesign code paths (none in main repo as of step H, but we keep the
 * file as a thin shell — no dead behaviour, just delegates to
 * SkillTraceContent inside a collapsible panel).
 *
 * For new code, prefer `<SkillTraceContent />` directly (works inside Sheet
 * without drawer-in-sheet nesting).
 */
export function SkillTraceDrawer() {
  const [open, setOpen] = useState(false);
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
        Skill Trace · {proposals.length}
      </Button>
      {open && <SkillTraceContent />}
    </div>
  );
}
