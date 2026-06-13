export function getGatewayToken(): string {
  const envToken = process.env.NEXT_PUBLIC_GATEWAY_TOKEN?.trim();
  if (envToken) return envToken;

  if (typeof window === "undefined") return "";

  try {
    return (window.localStorage.getItem("pawai_gateway_token") ?? "").trim();
  } catch {
    return "";
  }
}

export function authHeaders(token = getGatewayToken()): Record<string, string> {
  const trimmedToken = token.trim();
  if (!trimmedToken) return {};

  return { Authorization: `Bearer ${trimmedToken}` };
}
