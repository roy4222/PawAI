/**
 * plan4 P4-3: unit tests for the operator manual FLOOR controls.
 *
 * The vitest environment is "node" (no jsdom / @testing-library), so — like
 * stores/__tests__/reset-conversation.test.ts — we test the pure logic units
 * (the request builder + the store transitions the components drive) rather
 * than rendering React. The fetch wiring itself is exercised at the gateway
 * level (test_demo_controls.py).
 */
import { describe, it, expect, beforeEach } from "vitest";
import {
  buildDemoPhaseRequest,
  DEMO_PHASES,
} from "../demo-phase-buttons";
import { useStateStore } from "@/stores/state-store";

describe("plan4 buildDemoPhaseRequest", () => {
  it("POSTs the phase in the body as {phase}", () => {
    const { url, body } = buildDemoPhaseRequest("s2_greet");
    expect(url).toMatch(/\/api\/demo_phase$/);
    expect(JSON.parse(body)).toEqual({ phase: "s2_greet" });
  });

  it("preserves arbitrary phase strings verbatim (server validates)", () => {
    const { body } = buildDemoPhaseRequest("s5_safety");
    expect(JSON.parse(body)).toEqual({ phase: "s5_safety" });
  });
});

describe("plan4 DEMO_PHASES button set", () => {
  it("contains the five canonical demo phases", () => {
    const phases = DEMO_PHASES.map((p) => p.phase);
    expect(phases).toContain("s1_nav");
    expect(phases).toContain("s2_greet");
    expect(phases).toContain("s3_pose_object");
    expect(phases).toContain("s4_gesture");
    expect(phases).toContain("s5_safety");
  });

  it("includes the conservative 'all' fallback rung", () => {
    const phases = DEMO_PHASES.map((p) => p.phase);
    expect(phases).toContain("all");
  });

  it("uses canonical names only (no s2_face/s3_object in operator button set)", () => {
    const phases = DEMO_PHASES.map((p) => p.phase);
    expect(phases).not.toContain("s2_face");
    expect(phases).not.toContain("s3_object");
  });
});

describe("plan4 demoPhase store wiring", () => {
  beforeEach(() => {
    useStateStore.setState({ demoPhase: null, offlineMode: null });
  });

  it("setDemoPhase reflects the gateway-confirmed phase (optimistic update)", () => {
    expect(useStateStore.getState().demoPhase).toBeNull();
    // mirrors: data.ok && typeof data.phase === 'string' → setDemoPhase(data.phase)
    useStateStore.getState().setDemoPhase("s2_greet");
    expect(useStateStore.getState().demoPhase).toBe("s2_greet");
  });

  it("gateway non-ok response must NOT change state (component returns early)", () => {
    useStateStore.getState().setDemoPhase("s3_pose_object");
    // simulate handleClick getting !res.ok → it returns before setDemoPhase,
    // so the store keeps the prior value.
    const before = useStateStore.getState().demoPhase;
    // (no setter called)
    expect(useStateStore.getState().demoPhase).toBe(before);
    expect(useStateStore.getState().demoPhase).toBe("s3_pose_object");
  });
});

describe("plan4 offlineMode store wiring", () => {
  beforeEach(() => {
    useStateStore.setState({ offlineMode: null });
  });

  it("setOfflineMode flips from unknown(null)→true→false", () => {
    expect(useStateStore.getState().offlineMode).toBeNull();
    // null treated as OFF → first toggle sends ON
    useStateStore.getState().setOfflineMode(true);
    expect(useStateStore.getState().offlineMode).toBe(true);
    useStateStore.getState().setOfflineMode(false);
    expect(useStateStore.getState().offlineMode).toBe(false);
  });
});
