import { AlertTriangle } from "lucide-react";
import type { SkillPlan } from "@/contracts/types";

export function BubbleAlert({ plan }: { plan: SkillPlan }) {
  return (
    <div className="flex gap-2 rounded-lg border border-red-400/30 bg-red-500/10 px-3 py-2 text-xs">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
      <div>
        <span className="font-mono text-red-300">alert</span>
        <span className="text-muted-foreground"> · </span>
        <span className="font-medium text-foreground">{plan.selected_skill}</span>
        <span className="ml-1 text-muted-foreground">· {plan.reason}</span>
      </div>
    </div>
  );
}
