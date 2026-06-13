import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useEffect: (effect: () => void | (() => void)) => {
      effect();
    },
    useState: <T>(initial: T) => [initial, vi.fn()],
  };
});

import { useScoreboard } from "@/hooks/use-scoreboard";

const originalGatewayToken = process.env.NEXT_PUBLIC_GATEWAY_TOKEN;

afterEach(() => {
  vi.unstubAllGlobals();
  if (originalGatewayToken === undefined) {
    delete process.env.NEXT_PUBLIC_GATEWAY_TOKEN;
  } else {
    process.env.NEXT_PUBLIC_GATEWAY_TOKEN = originalGatewayToken;
  }
});

function stubScoreboardFetch() {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ score: 0 }),
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

describe("gateway auth wiring", () => {
  it("sends Authorization on gateway fetches when a token is configured", () => {
    process.env.NEXT_PUBLIC_GATEWAY_TOKEN = "secret-token";
    const fetchMock = stubScoreboardFetch();

    useScoreboard();

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8080/api/scoreboard",
      { headers: { Authorization: "Bearer secret-token" } },
    );
  });

  it("does not send Authorization when the gateway token is unset", () => {
    delete process.env.NEXT_PUBLIC_GATEWAY_TOKEN;
    const fetchMock = stubScoreboardFetch();

    useScoreboard();

    const options = fetchMock.mock.calls[0]?.[1] as RequestInit | undefined;
    const headers = options?.headers as Record<string, string> | undefined;
    expect(headers?.Authorization).toBeUndefined();
  });
});
