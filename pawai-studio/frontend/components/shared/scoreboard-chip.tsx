"use client";

import { ProvenanceBadge } from "@/components/shared/provenance-badge";
import type { ScoreboardGrade } from "@/contracts/types";
import { useScoreboard } from "@/hooks/use-scoreboard";

const gradeClasses: Record<ScoreboardGrade, string> = {
  pass: "text-emerald-300",
  degraded: "text-amber-300",
  fail: "text-red-300",
  insufficient_data: "text-zinc-300",
};

export function ScoreboardChip() {
  const { data, loading } = useScoreboard();

  if (loading) {
    return <div className="text-xs text-zinc-400">loading</div>;
  }

  const capabilities = data?.capabilities ?? [];
  const hasCapabilities = capabilities.length > 0;

  return (
    <div className="space-y-2 text-xs text-zinc-300">
      <ProvenanceBadge
        provenance={data?.provenance}
        backend={data?.backend}
        missing={!data}
      />
      <div className="space-y-1">
        {hasCapabilities ? (
          capabilities.map((capability) => {
            const reason = capability.failure_reason?.trim();
            const reasonText = reason || (capability.grade === "pass" ? "—" : "⚠ 缺 reason");
            const reasonClass = reason
              ? "text-zinc-400"
              : capability.grade === "pass"
                ? "text-zinc-600"
                : "text-amber-300";
            return (
              <div
                key={capability.capability_id}
                className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_minmax(0,1fr)] gap-2 rounded border border-zinc-700/60 bg-zinc-900/40 px-2 py-1"
              >
                <span className="truncate">{capability.capability_id}</span>
                <span className={gradeClasses[capability.grade]}>{capability.grade}</span>
                <span className={`truncate ${reasonClass}`}>{reasonText}</span>
                <span className="truncate text-zinc-500">
                  {capability.last_tested_at ?? "—"}
                </span>
              </div>
            );
          })
        ) : (
          <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)_minmax(0,1fr)] gap-2 rounded border border-red-500/40 bg-red-500/10 px-2 py-1 text-red-300">
            <span>missing</span>
            <span className="text-red-300">insufficient_data</span>
            <span>—</span>
            <span>—</span>
          </div>
        )}
      </div>
    </div>
  );
}
