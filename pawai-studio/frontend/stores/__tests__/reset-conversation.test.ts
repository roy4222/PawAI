/**
 * P1-2: Unit tests for new-conversation reset behavior.
 *
 * Tests the store-level state clearing that handleNewConversation performs
 * after POST /api/reset succeeds. The fetch call itself is tested at the
 * gateway integration level; here we only verify state transitions.
 */
import { describe, it, expect, beforeEach } from "vitest";
import { useStateStore } from "../state-store";

describe("P1-2 new-conversation reset", () => {
  beforeEach(() => {
    // Reset to clean state before each test
    useStateStore.setState({ ttsMessages: [] });
  });

  it("clearing ttsMessages via setState removes all entries", () => {
    // Populate some messages first (10s apart to bypass rate-limit dedup window)
    useStateStore.getState().appendTtsMessage({
      id: "tts-1",
      text: "你好",
      timestamp: 1000,
      origin: "tts",
    });
    useStateStore.getState().appendTtsMessage({
      id: "tts-2",
      text: "我是 PawAI",
      timestamp: 12000,
      origin: "tts",
    });
    expect(useStateStore.getState().ttsMessages).toHaveLength(2);

    // Simulate what handleNewConversation does
    useStateStore.setState({ ttsMessages: [] });

    expect(useStateStore.getState().ttsMessages).toHaveLength(0);
  });

  it("clearing ttsMessages is idempotent when already empty", () => {
    useStateStore.setState({ ttsMessages: [] });
    useStateStore.setState({ ttsMessages: [] });
    expect(useStateStore.getState().ttsMessages).toHaveLength(0);
  });

  it("after reset, new messages can still be appended", () => {
    useStateStore.getState().appendTtsMessage({
      id: "tts-old",
      text: "舊訊息",
      timestamp: 1000,
      origin: "tts",
    });

    // Reset
    useStateStore.setState({ ttsMessages: [] });

    // Should be able to append again
    useStateStore.getState().appendTtsMessage({
      id: "tts-new",
      text: "新訊息",
      timestamp: 2000,
      origin: "tts",
    });

    const msgs = useStateStore.getState().ttsMessages;
    expect(msgs).toHaveLength(1);
    expect(msgs[0].id).toBe("tts-new");
  });
});
