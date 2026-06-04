"use client";

import { Badge } from "@/components/ui/badge";
import type {
  ProvenanceState,
  ScoreboardBackend,
  ScoreboardProvenance,
} from "@/contracts/types";

interface ProvenanceBadgeProps {
  provenance?: ScoreboardProvenance;
  backend?: ScoreboardBackend;
  missing?: boolean;
}

const provenanceClasses: Record<ProvenanceState, string> = {
  live: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  frozen: "bg-sky-500/20 text-sky-300 border-sky-500/40",
  mock: "bg-amber-500/20 text-amber-300 border-amber-500/40",
  missing: "bg-red-500/20 text-red-300 border-red-500/40",
};

const provenanceLabels: Record<ProvenanceState, string> = {
  live: "live",
  frozen: "frozen",
  mock: "mock",
  missing: "missing",
};

export function ProvenanceBadge({
  provenance,
  backend,
  missing,
}: ProvenanceBadgeProps) {
  const state: ProvenanceState =
    missing === true || provenance === "missing"
      ? "missing"
      : backend === "mock"
        ? "mock"
        : backend === "live"
          ? "live"
          : provenance ?? "frozen";

  return (
    <Badge
      className={provenanceClasses[state]}
      title={`scoreboard provenance: ${provenanceLabels[state]}`}
    >
      {provenanceLabels[state]}
    </Badge>
  );
}
