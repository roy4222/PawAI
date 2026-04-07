"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { PawAIEvent } from "@/contracts/types";

// Runtime fallback: env → same-origin hostname:8080 → localhost:8080
// Auto-select ws/wss based on page protocol
function getDefaultWsUrl(): string {
  if (typeof window !== "undefined") {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    return `${proto}://${window.location.hostname}:8080/ws/events`;
  }
  return "ws://localhost:8080/ws/events";
}
const DEFAULT_WS_URL = getDefaultWsUrl();
const RECONNECT_DELAY_MS = 3000;

interface UseWebSocketOptions {
  onMessage: (event: PawAIEvent) => void;
}

interface UseWebSocketResult {
  isConnected: boolean;
}

export function useWebSocket({ onMessage }: UseWebSocketOptions): UseWebSocketResult {
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const onMessageRef = useRef(onMessage);
  const unmountedRef = useRef(false);

  // Keep callback ref current without re-triggering effect
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const url =
      (typeof process !== "undefined" && process.env.NEXT_PUBLIC_WS_URL) ||
      DEFAULT_WS_URL;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setIsConnected(true);
    };

    ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data as string) as PawAIEvent;
        onMessageRef.current(event);
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setIsConnected(false);
      reconnectTimer.current = setTimeout(() => connectRef.current(), RECONNECT_DELAY_MS);
    };

    ws.onerror = () => {
      // onclose will fire after onerror; no extra handling needed
      ws.close();
    };
  }, []);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;
    connect();

    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current !== null) {
        clearTimeout(reconnectTimer.current);
      }
      wsRef.current?.close();
    };
  }, [connect]);

  return { isConnected };
}
