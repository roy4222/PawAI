"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { getGatewayWsUrl } from "@/lib/gateway-url";

type VideoSource = "face" | "vision" | "object";
type StreamStatus = "connected" | "no_signal" | "disconnected";

const RECONNECT_DELAY_MS = 3000;
const NO_SIGNAL_TIMEOUT_MS = 10_000;
const FPS_BUFFER_SIZE = 10;

interface UseVideoStreamOptions {
  source: VideoSource;
  enabled?: boolean;
}

interface UseVideoStreamResult {
  imageUrl: string | null;
  fps: number;
  isConnected: boolean;
  status: StreamStatus;
}

function getWsUrl(source: VideoSource): string {
  return getGatewayWsUrl(`/ws/video/${source}`);
}

export function useVideoStream({
  source,
  enabled = true,
}: UseVideoStreamOptions): UseVideoStreamResult {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [fps, setFps] = useState(0);
  const [status, setStatus] = useState<StreamStatus>("disconnected");

  const prevUrlRef = useRef<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const noSignalTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const frameTimestamps = useRef<number[]>([]);
  const unmountedRef = useRef(false);

  const updateFps = useCallback(() => {
    const buf = frameTimestamps.current;
    if (buf.length < 2) {
      setFps(0);
      return;
    }
    const n = buf.length;
    const elapsed = buf[n - 1] - buf[0];
    if (elapsed <= 0) {
      setFps(0);
      return;
    }
    setFps(Math.round(((n - 1) * 1000) / elapsed * 10) / 10);
  }, []);

  const resetNoSignalTimer = useCallback(() => {
    if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
    noSignalTimer.current = setTimeout(() => {
      if (!unmountedRef.current) setStatus("no_signal");
    }, NO_SIGNAL_TIMEOUT_MS);
  }, []);

  const connectRef = useRef<() => void>(() => {});

  const connect = useCallback(() => {
    if (unmountedRef.current || !enabled) return;

    const url = getWsUrl(source);
    const ws = new WebSocket(url);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    ws.onopen = () => {
      if (unmountedRef.current) {
        ws.close();
        return;
      }
      setStatus("connected");
      frameTimestamps.current = [];
      resetNoSignalTimer();
    };

    ws.onmessage = (ev) => {
      if (unmountedRef.current) return;

      const blob = new Blob([ev.data], { type: "image/jpeg" });
      const newUrl = URL.createObjectURL(blob);

      // Revoke previous URL to prevent memory leak
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
      }
      prevUrlRef.current = newUrl;
      setImageUrl(newUrl);

      // FPS tracking
      const now = performance.now();
      frameTimestamps.current.push(now);
      if (frameTimestamps.current.length > FPS_BUFFER_SIZE) {
        frameTimestamps.current.shift();
      }
      updateFps();

      setStatus("connected");
      resetNoSignalTimer();
    };

    ws.onclose = () => {
      if (unmountedRef.current) return;
      setStatus("disconnected");
      if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
      reconnectTimer.current = setTimeout(
        () => connectRef.current(),
        RECONNECT_DELAY_MS
      );
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [source, enabled, updateFps, resetNoSignalTimer]);

  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  useEffect(() => {
    unmountedRef.current = false;

    if (enabled) {
      connect();
    }

    return () => {
      unmountedRef.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (noSignalTimer.current) clearTimeout(noSignalTimer.current);
      wsRef.current?.close();
      if (prevUrlRef.current) {
        URL.revokeObjectURL(prevUrlRef.current);
        prevUrlRef.current = null;
      }
    };
  }, [connect, enabled]);

  return { imageUrl, fps, isConnected: status === "connected", status };
}
