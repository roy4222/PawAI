import { Brain } from "lucide-react";
import type { SkillPlan } from "@/contracts/types";

export function BubbleBrainPlan({ plan }: { plan: SkillPlan }) {
  return (
    <div className="flex gap-2 rounded-lg border border-sky-400/15 bg-sky-400/5 px-3 py-2 text-xs">
      <Brain className="mt-0.5 h-3.5 w-3.5 shrink-0 text-sky-400" />
      <div className="min-w-0">
        <span className="font-mono text-sky-400">brain</span>
        <span className="text-muted-foreground"> selected </span>
        <span className="font-medium text-foreground">{plan.selected_skill}</span>
        <span className="ml-1 text-muted-foreground">· {plan.reason}</span>
      </div>
    </div>
  );
}
