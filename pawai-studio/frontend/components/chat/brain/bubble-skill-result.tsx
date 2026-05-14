import { CheckCircle2, XCircle } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSkillResult({ result }: { result: SkillResult }) {
  const ok = result.status === "completed";
  const Icon = ok ? CheckCircle2 : XCircle;

  return (
    <div className="flex gap-2 px-3 py-1 text-xs text-muted-foreground">
      <Icon className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${ok ? "text-emerald-400" : "text-amber-400"}`} />
      <div>
        <span className="font-mono">{result.status}</span>
        <span className="ml-1">· {result.selected_skill}</span>
        {result.detail && <span className="ml-1">· {result.detail}</span>}
      </div>
    </div>
  );
}
