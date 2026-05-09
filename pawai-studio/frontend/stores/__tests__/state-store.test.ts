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
        timestamp: i,
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
