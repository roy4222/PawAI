import { ShieldAlert } from "lucide-react";
import type { SkillResult } from "@/contracts/types";

export function BubbleSafety({ result }: { result: SkillResult }) {
  return (
    <div className="flex gap-2 rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-2 text-xs">
      <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
      <div>
        <span className="font-mono text-amber-300">safety</span>
        <span className="text-muted-foreground"> · {result.status}</span>
        {result.detail && <span className="ml-1 text-muted-foreground">· {result.detail}</span>}
      </div>
    </div>
  );
}
