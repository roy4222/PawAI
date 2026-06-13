"use client";

import { useEffect, useState } from "react";
import { Hand } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { authHeaders } from "@/lib/gateway-auth";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { cn } from "@/lib/utils";

/**
 * GestureToggle — demo-recording P0 操作員控制（6/9 demo plan）。
 *
 * 顯示「手勢 ON / OFF / ?」並 POST /api/gesture_enabled 翻轉。
 * 狀態真相 = gateway cache + /ws/events 的 brain:gesture_enabled 廣播
 * （所有開啟的 Studio 視窗同步）。session 啟動預設 OFF（brain yaml
 * gesture_enabled: false），初始 null 顯示中性「手勢 ?」，不假設 ON。
 * 操作流程：只在手勢段 take 開 ON，其餘時間保持 OFF。
 */
export function GestureToggle() {
  const enabled = useStateStore((s) => s.gestureToggleEnabled);
  const setEnabled = useStateStore((s) => s.setGestureToggleEnabled);
  const [busy, setBusy] = useState(false);

  // 掛載時讀 gateway cache 初始化（null = 本 session 尚未有人切換過）。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getGatewayHttpUrl()}/api/gesture_enabled`, {
          headers: { ...authHeaders() },
        });
        if (!res.ok) return;
        const data = (await res.json().catch(() => null)) as
          | { enabled?: boolean | null }
          | null;
        if (!cancelled && typeof data?.enabled === "boolean") {
          setEnabled(data.enabled);
        }
      } catch {
        // gateway 未啟動 — 保持 unknown
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setEnabled]);

  async function handleToggle() {
    if (busy) return;
    // unknown(null) 視為 OFF（brain 預設）→ 第一次點擊送 ON。
    const next = enabled !== true;
    setBusy(true);
    try {
      const res = await fetch(`${getGatewayHttpUrl()}/api/gesture_enabled`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify({ enabled: next }),
      });
      if (!res.ok) return;
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; enabled?: boolean }
        | null;
      if (data?.ok && typeof data.enabled === "boolean") {
        // optimistic update（WS 廣播之後會再同步一次，等值無感）
        setEnabled(data.enabled);
      }
    } catch {
      // gateway 不在線 — 不改 state
    } finally {
      setBusy(false);
    }
  }

  const stateLabel = enabled === null ? "?" : enabled ? "ON" : "OFF";
  const stateClass =
    enabled === null
      ? "border-border/50 bg-zinc-500/10 text-zinc-400"
      : enabled
        ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
        : "border-red-500/40 bg-red-500/10 text-red-300";

  return (
    <button
      type="button"
      onClick={handleToggle}
      disabled={busy}
      title="手勢辨識開關（demo 錄影 P0：只在手勢段開啟）"
      aria-label={`手勢辨識：${stateLabel}`}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px]",
        "transition-colors disabled:opacity-50",
        stateClass,
      )}
    >
      <Hand className="h-3 w-3" />
      <span>手勢</span>
      <span className="font-semibold">{stateLabel}</span>
    </button>
  );
}
