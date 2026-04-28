import { ChevronRight } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSkillStep({ result }: { result: SkillResult }) {
  return (
    <div className="flex gap-2 px-3 py-1 text-xs text-muted-foreground">
      <ChevronRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-blue-400" />
      <div>
        <span className="font-mono text-blue-400">{result.status}</span>
        {result.step_index !== null && (
          <span> · {result.step_index + 1}/{result.step_total}</span>
        )}
        <span> · {result.detail || result.selected_skill}</span>
      </div>
    </div>
  );
}
