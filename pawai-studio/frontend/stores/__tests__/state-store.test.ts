import { describe, it, expect, beforeEach } from "vitest";
import { useStateStore } from "../state-store";

describe("ttsMessages ring buffer", () => {
  beforeEach(() => {
    useStateStore.setState({ ttsMessages: [] });
  });

  it("appendTtsMessage adds entry to ttsMessages", () => {
    useStateStore.getState().appendTtsMessage({
      id: "evt-1",
      text: "嗨",
      timestamp: 1000,
      origin: "tts",
    });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
    expect(useStateStore.getState().ttsMessages[0].text).toBe("嗨");
  });

  it("dedups by event id", () => {
    const msg = { id: "evt-1", text: "嗨", timestamp: 1000, origin: "tts" };
    useStateStore.getState().appendTtsMessage(msg);
    useStateStore.getState().appendTtsMessage(msg);
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });

  it("trims to max 200 (shift oldest)", () => {
    for (let i = 0; i < 205; i++) {
      useStateStore.getState().appendTtsMessage({
        id: `evt-${i}`,
        text: `msg-${i}`,
        timestamp: i * 10000, // each 10s apart to bypass rate-limit window
        origin: "tts",
      });
    }
    const msgs = useStateStore.getState().ttsMessages;
    expect(msgs).toHaveLength(200);
    expect(msgs[0].id).toBe("evt-5"); // first 5 dropped
    expect(msgs[199].id).toBe("evt-204");
  });

  it("preserves source field when present", () => {
    useStateStore.getState().appendTtsMessage({
      id: "evt-1",
      text: "我來扭給你看",
      timestamp: 1000,
      origin: "tts",
      source: "skill_say",
    });
    expect(useStateStore.getState().ttsMessages[0].source).toBe("skill_say");
  });
});

describe("ttsMessages rate-limit", () => {
  beforeEach(() => {
    useStateStore.setState({ ttsMessages: [] });
  });

  it("rate-limits same source within 5s window", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "看到杯子", timestamp: 1000000, origin: "tts", source: "object_remark" });
    append({ id: "2", text: "看到椅子", timestamp: 1002000, origin: "tts", source: "object_remark" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });

  it("allows same source after 5s", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "看到杯子", timestamp: 1000000, origin: "tts", source: "object_remark" });
    append({ id: "2", text: "看到椅子", timestamp: 1007000, origin: "tts", source: "object_remark" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);
  });

  it("never rate-limits chat_reply (pending user reply)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "嗨", timestamp: 1000000, origin: "tts", source: "chat_reply" });
    append({ id: "2", text: "好啊", timestamp: 1000500, origin: "tts", source: "chat_reply" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);
  });

  it("never rate-limits skill_say (active skill SAY steps)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "我是 PawAI", timestamp: 1000000, origin: "tts", source: "skill_say" });
    append({ id: "2", text: "會看臉聽聲", timestamp: 1000500, origin: "tts", source: "skill_say" });
    append({ id: "3", text: "隨時跟我互動", timestamp: 1001000, origin: "tts", source: "skill_say" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(3);
  });

  it("never rate-limits say_canned (LLM/OpenRouter fallback replies)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "我聽不太懂", timestamp: 1000000, origin: "tts", source: "say_canned" });
    append({ id: "2", text: "再說一次好嗎", timestamp: 1000500, origin: "tts", source: "say_canned" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);
  });

  it("rate-limits no-source spontaneous (alert/object_remark/greet)", () => {
    const append = useStateStore.getState().appendTtsMessage;
    append({ id: "1", text: "陌生人警示", timestamp: 1000000, origin: "tts" });
    append({ id: "2", text: "再次警示", timestamp: 1002000, origin: "tts" });
    expect(useStateStore.getState().ttsMessages).toHaveLength(1);
  });
});

describe("brainTraces ring buffer (Evidence Center T2B-3)", () => {
  beforeEach(() => {
    useStateStore.setState({ brainTraces: [] });
  });

  const trace = (i: number, verdict: "accepted" | "suppressed" = "suppressed") => ({
    v: 1,
    ts: 1000 + i,
    decision_id: `gesture-${i}`,
    node: "brain_node",
    kind: "policy_decision" as const,
    verdict,
    gate: "pending_confirm",
    reason: "confirm_in_flight",
    detail: { shadow: false },
  });

  it("appendBrainTrace prepends entries", () => {
    useStateStore.getState().appendBrainTrace(trace(1));
    useStateStore.getState().appendBrainTrace(trace(2));
    const traces = useStateStore.getState().brainTraces;
    expect(traces).toHaveLength(2);
    expect(traces[0].decision_id).toBe("gesture-2"); // newest first
  });

  it("caps at 50 like conversationTraces", () => {
    for (let i = 0; i < 55; i++) {
      useStateStore.getState().appendBrainTrace(trace(i));
    }
    const traces = useStateStore.getState().brainTraces;
    expect(traces).toHaveLength(50);
    expect(traces[0].decision_id).toBe("gesture-54");
    expect(traces[49].decision_id).toBe("gesture-5");
  });

  it("keeps verdict for suppressed-reason filtering", () => {
    useStateStore.getState().appendBrainTrace(trace(1, "accepted"));
    useStateStore.getState().appendBrainTrace(trace(2, "suppressed"));
    const suppressed = useStateStore
      .getState()
      .brainTraces.filter((t) => t.verdict === "suppressed");
    expect(suppressed).toHaveLength(1);
    expect(suppressed[0].gate).toBe("pending_confirm");
  });
});
