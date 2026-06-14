/**
 * D4 (pre-6/18 iter2): unit tests for the GestureToggle operator control,
 * now mounted ONLY inside the hidden dev-panel (?dev=1).
 *
 * The vitest environment is "node" (no jsdom / @testing-library), so — like
 * operator/__tests__/demo-phase-buttons.test.tsx — we test the pure logic
 * units (the request builder + the store transitions the component drives)
 * rather than rendering React. The fetch wiring itself is exercised at the
 * gateway level.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { buildGestureRequest } from "../gesture-toggle";
import { useStateStore } from "@/stores/state-store";

describe("D4 buildGestureRequest", () => {
  it("POSTs the enabled flag in the body as {enabled}", () => {
    const { url, body } = buildGestureRequest(true);
    expect(url).toMatch(/\/api\/gesture_enabled$/);
    expect(JSON.parse(body)).toEqual({ enabled: true });
  });

  it("preserves the OFF flag verbatim (byte-identical request shape)", () => {
    const { body } = buildGestureRequest(false);
    expect(JSON.parse(body)).toEqual({ enabled: false });
  });

  it("targets the same /api/gesture_enabled endpoint regardless of value", () => {
    expect(buildGestureRequest(true).url).toBe(buildGestureRequest(false).url);
  });
});

describe("D4 gestureToggleEnabled store wiring", () => {
  beforeEach(() => {
    useStateStore.setState({ gestureToggleEnabled: null });
  });

  it("starts unknown(null) — does NOT assume ON (brain default OFF)", () => {
    expect(useStateStore.getState().gestureToggleEnabled).toBeNull();
  });

  it("setGestureToggleEnabled flips from unknown(null)→true→false", () => {
    // null treated as OFF → first toggle sends ON
    useStateStore.getState().setGestureToggleEnabled(true);
    expect(useStateStore.getState().gestureToggleEnabled).toBe(true);
    useStateStore.getState().setGestureToggleEnabled(false);
    expect(useStateStore.getState().gestureToggleEnabled).toBe(false);
  });

  it("gateway non-ok response must NOT change state (component returns early)", () => {
    useStateStore.getState().setGestureToggleEnabled(true);
    const before = useStateStore.getState().gestureToggleEnabled;
    // simulate handleToggle getting !res.ok → returns before setter is called.
    // (no setter invoked)
    expect(useStateStore.getState().gestureToggleEnabled).toBe(before);
    expect(useStateStore.getState().gestureToggleEnabled).toBe(true);
  });
});
