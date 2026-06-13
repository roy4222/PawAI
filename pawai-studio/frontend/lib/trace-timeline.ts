import type { BrainTraceEvent } from "@/contracts/types";

export type TraceGroup = {
  decisionId: string;
  events: BrainTraceEvent[];
  firstTs: number;
  lastTs: number;
  verdict: string;
  gates: string[];
  hasShadow: boolean;
};

type DecoratedEvent = {
  event: BrainTraceEvent;
  index: number;
};

const DEFAULT_CAP = 2000;

function sortedByTimestamp(events: BrainTraceEvent[]): BrainTraceEvent[] {
  return events
    .map((event, index): DecoratedEvent => ({ event, index }))
    .sort((a, b) => {
      const byTs = a.event.ts - b.event.ts;
      return byTs === 0 ? a.index - b.index : byTs;
    })
    .map(({ event }) => event);
}

export function buildTimeline(
  events: BrainTraceEvent[],
  opts: { cap?: number } = {}
): TraceGroup[] {
  const cap = opts.cap ?? DEFAULT_CAP;
  if (cap <= 0) return [];

  const sorted = sortedByTimestamp(events);
  const capped = sorted.length > cap ? sorted.slice(sorted.length - cap) : sorted;
  const groupsByDecision = new Map<string, TraceGroup>();
  const groupGateSets = new Map<string, Set<string>>();
  const policyDecisionGroups = new Set<string>();

  for (const event of capped) {
    let group = groupsByDecision.get(event.decision_id);
    if (!group) {
      group = {
        decisionId: event.decision_id,
        events: [],
        firstTs: event.ts,
        lastTs: event.ts,
        verdict: event.verdict,
        gates: [],
        hasShadow: false,
      };
      groupsByDecision.set(event.decision_id, group);
      groupGateSets.set(event.decision_id, new Set<string>());
    }

    group.events.push(event);
    group.lastTs = event.ts;
    group.hasShadow = group.hasShadow || event.gate === "ism_shadow";
    if (event.kind === "policy_decision") {
      group.verdict = event.verdict;
      policyDecisionGroups.add(event.decision_id);
    } else if (!policyDecisionGroups.has(event.decision_id)) {
      group.verdict = event.verdict;
    }

    const gates = groupGateSets.get(event.decision_id);
    if (gates && event.gate && !gates.has(event.gate)) {
      gates.add(event.gate);
      group.gates.push(event.gate);
    }
  }

  return [...groupsByDecision.values()];
}

export function verdictTone(
  verdict: string,
  hasShadow = false
): "accepted" | "suppressed" | "blocked" | "shadow" {
  if (hasShadow) return "shadow";
  if (verdict === "suppressed" || verdict === "blocked") return verdict;
  return "accepted";
}
