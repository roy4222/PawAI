"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getGatewayWsUrl } from "@/lib/gateway-url";

const RECONNECT_DELAY_MS = 3000;

interface TextConfirm {
  intent: string;
  confidence: number;
  published: boolean;
}

interface UseTextCommandResult {
  sendText: (text: string) => boolean;
  isConnected: boolean;
  lastConfirm: TextConfirm | null;
}

function getTextWsUrl(): string {
  return getGatewayWsUrl("/ws/text");
}

export function useTextCommand(): UseTextCommandResult {
  const [isConnected, setIsConnected] = useState(false);
  const [lastConfirm, setLastConfirm] = useState<TextConfirm | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const unmountedRef = useRef(false);
  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (unmountedRef.current) return;

    const ws = new WebSocket(getTextWsUrl());
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
        const data = JSON.parse(ev.data as string);
        if (data.published !== undefined) {
          setLastConfirm({
            intent: data.intent ?? "",
            confidence: data.confidence ?? 0,
            published: data.published ?? false,
          });
        }
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setIsConnected(false);
      reconnectTimer.current = setTimeout(
        () => connectRef.current(),
        RECONNECT_DELAY_MS
      );
    };

    ws.onerror = () => {
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
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  const sendText = useCallback((text: string): boolean => {
    const ws = wsRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(text);
      return true;
    }
    return false;
  }, []);

  return { sendText, isConnected, lastConfirm };
}
