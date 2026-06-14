"use client";

import { useEffect, useState } from "react";
import { WifiOff } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { authHeaders } from "@/lib/gateway-auth";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { cn } from "@/lib/utils";

/**
 * OfflineToggle — plan4 operator manual FLOOR (pre-6/18 demo).
 *
 * HIDDEN operator surface: toggles offline mode (local LLM/TTS short-path) when
 * the network degrades. POST /api/offline_mode {enabled}; gateway publishes Bool
 * to /brain/offline_mode. Default OFF = byte-identical. Mounted ONLY inside the
 * hidden dev-panel (?dev=1). Mirrors components/chat/gesture-toggle.tsx.
 *
 * NOTE: plan3 owns the brain-side offline_mode semantics (param vs topic);
 * runtime切換落地前操作員退啟動前 env override（proven）。
 */
export function OfflineToggle() {
  const offline = useStateStore((s) => s.offlineMode);
  const setOffline = useStateStore((s) => s.setOfflineMode);
  const [busy, setBusy] = useState(false);

  // 掛載時讀 gateway cache 初始化（null = 本 session 尚未切換過）。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getGatewayHttpUrl()}/api/offline_mode`, {
          headers: { ...authHeaders() },
        });
        if (!res.ok) return;
        const data = (await res.json().catch(() => null)) as
          | { enabled?: boolean | null }
          | null;
        if (!cancelled && typeof data?.enabled === "boolean") {
          setOffline(data.enabled);
        }
      } catch {
        // gateway 未啟動 — 保持 unknown
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setOffline]);

  async function handleToggle() {
    if (busy) return;
    // unknown(null) 視為 OFF（brain 預設線上）→ 第一次點擊送 ON。
    const next = offline !== true;
    setBusy(true);
    try {
      const res = await fetch(`${getGatewayHttpUrl()}/api/offline_mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) return;
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; enabled?: boolean }
        | null;
      if (data?.ok && typeof data.enabled === "boolean") {
        setOffline(data.enabled);
      }
    } catch {
      // gateway 不在線 — 不改 state
    } finally {
      setBusy(false);
    }
  }

  const stateLabel = offline === null ? "?" : offline ? "ON" : "OFF";
  const stateClass =
    offline === null
      ? "border-border/50 bg-zinc-500/10 text-zinc-400"
      : offline
        ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
        : "border-emerald-500/40 bg-emerald-500/15 text-emerald-300";

  return (
    <div className="flex flex-col gap-1.5 p-3">
      <span className="font-mono text-[11px] text-zinc-400">離線模式（FLOOR）</span>
      <button
        type="button"
        onClick={handleToggle}
        disabled={busy}
        title="離線模式開關（網路降級時切本地 LLM/TTS）"
        aria-label={`離線模式：${stateLabel}`}
        aria-pressed={offline === true}
        className={cn(
          "inline-flex items-center gap-1.5 self-start rounded-md border px-2 py-1",
          "font-mono text-[11px] transition-colors disabled:opacity-50",
          stateClass,
        )}
      >
        <WifiOff className="h-3 w-3" />
        <span>離線</span>
        <span className="font-semibold">{stateLabel}</span>
      </button>
    </div>
  );
}
