import { describe, expect, it } from "vitest";
import type { BrainTraceEvent } from "@/contracts/types";
import { buildTimeline, verdictTone } from "@/lib/trace-timeline";
import { gateZh, reasonZh } from "@/lib/trace-zh";

function trace(
  partial: Partial<BrainTraceEvent> & Pick<BrainTraceEvent, "decision_id" | "ts">
): BrainTraceEvent {
  return {
    v: 1,
    node: "brain_node",
    kind: "candidate",
    verdict: "accepted",
    gate: "safety",
    reason: "candidate:greet",
    detail: {},
    ...partial,
  };
}

describe("buildTimeline", () => {
  it("groups multiple decision ids in first-seen timestamp order", () => {
    const groups = buildTimeline([
      trace({ decision_id: "decision-b", ts: 20, gate: "tts_playing" }),
      trace({ decision_id: "decision-a", ts: 10, gate: "safety" }),
      trace({
        decision_id: "decision-b",
        ts: 30,
        kind: "policy_decision",
        verdict: "suppressed",
        gate: "tts_playing",
      }),
    ]);

    expect(groups.map((group) => group.decisionId)).toEqual(["decision-a", "decision-b"]);
    expect(groups[1].events).toHaveLength(2);
    expect(groups[1].verdict).toBe("suppressed");
    expect(groups[1].gates).toEqual(["tts_playing"]);
  });

  it("sorts events by timestamp ascending within a group", () => {
    const groups = buildTimeline([
      trace({ decision_id: "decision-a", ts: 30, kind: "skill_result" }),
      trace({ decision_id: "decision-a", ts: 10, kind: "candidate" }),
      trace({ decision_id: "decision-a", ts: 20, kind: "policy_decision" }),
    ]);

    expect(groups[0].events.map((event) => event.kind)).toEqual([
      "candidate",
      "policy_decision",
      "skill_result",
    ]);
    expect(groups[0].firstTs).toBe(10);
    expect(groups[0].lastTs).toBe(30);
  });

  it("caps by keeping the newest events", () => {
    const groups = buildTimeline(
      Array.from({ length: 6 }, (_, index) =>
        trace({ decision_id: `decision-${index}`, ts: index + 1 })
      ),
      { cap: 3 }
    );

    expect(groups.map((group) => group.decisionId)).toEqual([
      "decision-3",
      "decision-4",
      "decision-5",
    ]);
    expect(groups.map((group) => group.firstTs)).toEqual([4, 5, 6]);
  });

  it("detects shadow chains and lets shadow tone win", () => {
    const groups = buildTimeline([
      trace({ decision_id: "shadow-chain", ts: 10, gate: "safety" }),
      trace({ decision_id: "shadow-chain", ts: 20, gate: "ism_shadow", verdict: "blocked" }),
    ]);

    expect(groups[0].hasShadow).toBe(true);
    expect(verdictTone(groups[0].verdict, groups[0].hasShadow)).toBe("shadow");
  });
});

describe("verdictTone", () => {
  it("maps known verdicts and defaults unknown values to accepted", () => {
    expect(verdictTone("accepted")).toBe("accepted");
    expect(verdictTone("suppressed")).toBe("suppressed");
    expect(verdictTone("blocked")).toBe("blocked");
    expect(verdictTone("unexpected")).toBe("accepted");
  });
});

describe("trace zh labels", () => {
  it("looks up reason prefixes and falls back to the raw reason", () => {
    expect(reasonZh("cooldown:greet:[private]")).toBe("冷卻中（cooldown:greet:[private]）");
    expect(reasonZh("unknown_prefix:value")).toBe("unknown_prefix:value");
  });

  it("falls back to the raw gate for unmapped gates", () => {
    expect(gateZh("safety")).toBe("安全限制（safety）");
    expect(gateZh("future_gate")).toBe("future_gate");
  });
});
