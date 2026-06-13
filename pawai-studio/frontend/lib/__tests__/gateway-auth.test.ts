import { afterEach, describe, expect, it } from "vitest";
import { authHeaders, getGatewayToken } from "@/lib/gateway-auth";

const originalGatewayToken = process.env.NEXT_PUBLIC_GATEWAY_TOKEN;

afterEach(() => {
  if (originalGatewayToken === undefined) {
    delete process.env.NEXT_PUBLIC_GATEWAY_TOKEN;
  } else {
    process.env.NEXT_PUBLIC_GATEWAY_TOKEN = originalGatewayToken;
  }
});

describe("gateway auth", () => {
  it("keeps auth headers default-off when the token is empty", () => {
    expect(authHeaders("")).toEqual({});
  });

  it("attaches a bearer token when configured", () => {
    expect(authHeaders("abc")).toEqual({ Authorization: "Bearer abc" });
  });

  it("reads and trims the gateway token from the public env var", () => {
    process.env.NEXT_PUBLIC_GATEWAY_TOKEN = "  abc  ";

    expect(getGatewayToken()).toBe("abc");
  });

  it("returns no gateway token when env is unset in node", () => {
    delete process.env.NEXT_PUBLIC_GATEWAY_TOKEN;

    expect(getGatewayToken()).toBe("");
    expect(authHeaders()).toEqual({});
  });
});
