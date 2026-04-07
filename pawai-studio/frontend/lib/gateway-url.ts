"use client";

const DEFAULT_GATEWAY_PORT = "8080";

function getBrowserProtocol(): "http:" | "https:" {
  if (typeof window === "undefined") return "http:";
  return window.location.protocol === "https:" ? "https:" : "http:";
}

function getBrowserHostname(): string {
  if (typeof window === "undefined") return "localhost";
  return window.location.hostname;
}

export function getGatewayHttpUrl(): string {
  const explicitUrl = process.env.NEXT_PUBLIC_GATEWAY_URL;
  if (explicitUrl) return explicitUrl.replace(/\/$/, "");

  const host = process.env.NEXT_PUBLIC_GATEWAY_HOST || getBrowserHostname();
  return `${getBrowserProtocol()}//${host}:${DEFAULT_GATEWAY_PORT}`;
}

export function getGatewayWsUrl(path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;

  const explicitWsUrl =
    normalizedPath === "/ws/events" ? process.env.NEXT_PUBLIC_WS_URL : undefined;
  if (explicitWsUrl) return explicitWsUrl;

  const httpUrl = getGatewayHttpUrl();
  const url = new URL(httpUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = normalizedPath;
  url.search = "";
  url.hash = "";
  return url.toString();
}
