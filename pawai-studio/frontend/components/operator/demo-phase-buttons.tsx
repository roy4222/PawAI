"use client";

import { useEffect, useState } from "react";
import { useStateStore } from "@/stores/state-store";
import { authHeaders } from "@/lib/gateway-auth";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { cn } from "@/lib/utils";

/**
 * DemoPhaseButtons — plan4 operator manual FLOOR (pre-6/18 demo).
 *
 * HIDDEN operator surface: the manual five-scene fallback that ALWAYS works
 * when auto-advance fails. Each button POSTs /api/demo_phase {phase}; the
 * gateway publishes reset_context THEN the phase to /brain/demo_phase so換幕
 * 不污染。Mounted ONLY inside the hidden dev-panel (reachable via ?dev=1) —
 * NOT in the main chat panel ("hidden, not flashy").
 *
 * Mirrors components/chat/gesture-toggle.tsx: authHeaders() + getGatewayHttpUrl()
 * + mount-time GET cache init + optimistic update + silent no-op when gateway
 * offline. Truth = gateway cache + /ws/events brain:demo_phase broadcast.
 */

// The 5 canonical demo phases (button/publish set). Kept in sync with the
// gateway DEMO_PHASE_WHITELIST + brain interaction_state.PHASE_ALLOWED_KINDS.
// "all" is the conservative全開 fallback (rollback ladder rung 4).
export const DEMO_PHASES = [
  { phase: "s1_nav", label: "S1 移動進場" },
  { phase: "s2_greet", label: "S2 認人問候" },
  { phase: "s3_pose_object", label: "S3 姿勢/物體" },
  { phase: "s4_gesture", label: "S4 手勢" },
  { phase: "s5_safety", label: "S5 安全拒絕" },
  { phase: "all", label: "全開 (退保守)" },
] as const;

export type DemoPhaseValue = (typeof DEMO_PHASES)[number]["phase"];

/** Pure helper — the request shape this component POSTs (testable without DOM). */
export function buildDemoPhaseRequest(phase: string): {
  url: string;
  body: string;
} {
  return {
    url: `${getGatewayHttpUrl()}/api/demo_phase`,
    body: JSON.stringify({ phase }),
  };
}

export function DemoPhaseButtons() {
  const demoPhase = useStateStore((s) => s.demoPhase);
  const setDemoPhase = useStateStore((s) => s.setDemoPhase);
  const [busy, setBusy] = useState<string | null>(null);

  // 掛載時讀 gateway cache 初始化（null = 本 session 尚未切換過）。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getGatewayHttpUrl()}/api/demo_phase`, {
          headers: { ...authHeaders() },
        });
        if (!res.ok) return;
        const data = (await res.json().catch(() => null)) as
          | { phase?: string | null }
          | null;
        if (!cancelled && typeof data?.phase === "string") {
          setDemoPhase(data.phase);
        }
      } catch {
        // gateway 未啟動 — 保持 unknown
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setDemoPhase]);

  async function handleClick(phase: string) {
    if (busy) return;
    setBusy(phase);
    try {
      const { url, body } = buildDemoPhaseRequest(phase);
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body,
      });
      if (!res.ok) return;
      const data = (await res.json().catch(() => null)) as
        | { ok?: boolean; phase?: string; error?: string }
        | null;
      if (data?.ok && typeof data.phase === "string") {
        // optimistic update（WS brain:demo_phase 廣播會再同步一次）
        setDemoPhase(data.phase);
      }
    } catch {
      // gateway 不在線 — 不改 state
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-1.5 p-3">
      <span className="font-mono text-[11px] text-zinc-400">
        操作員手動切幕（FLOOR）{demoPhase ? ` — 現: ${demoPhase}` : ""}
      </span>
      <div className="flex flex-wrap gap-1.5">
        {DEMO_PHASES.map(({ phase, label }) => {
          const active = demoPhase === phase;
          return (
            <button
              key={phase}
              type="button"
              onClick={() => handleClick(phase)}
              disabled={busy != null}
              title={`切到 ${label}（先 reset_context 再切 phase）`}
              aria-label={`切換到 ${label}`}
              aria-pressed={active}
              className={cn(
                "inline-flex items-center gap-1 rounded-md border px-2 py-1",
                "font-mono text-[11px] transition-colors disabled:opacity-50",
                active
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                  : "border-border/50 bg-zinc-500/10 text-zinc-400",
              )}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
