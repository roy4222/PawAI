"use client";

import { useEffect } from "react";
import { useStateStore } from "@/stores/state-store";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import type { PlanMode } from "@/contracts/types";

interface UseTogglePlanModeResult {
  planMode: PlanMode;
  togglePlanMode: () => Promise<void>;
}

/**
 * useTogglePlanMode — shared logic for Plan A/B switch.
 *
 * Used by SkillTraceContent (dev panel header chip) and NavigationPanel
 * (large CTA). Hydrates from gateway on mount, then optimistically updates
 * via POST /api/plan_mode.
 */
export function useTogglePlanMode(): UseTogglePlanModeResult {
  const planMode = useStateStore((s) => s.planMode);
  const setPlanMode = useStateStore((s) => s.setPlanMode);

  // Hydrate from gateway once.
  useEffect(() => {
    let cancelled = false;
    fetch(`${getGatewayHttpUrl()}/api/plan_mode`)
      .then((r) => r.json())
      .then((d) => {
        if (!cancelled && d?.mode) setPlanMode(d.mode as PlanMode);
      })
      .catch(() => {
        /* gateway not up yet — keep default */
      });
    return () => {
      cancelled = true;
    };
  }, [setPlanMode]);

  async function togglePlanMode() {
    const next: PlanMode = planMode === "A" ? "B" : "A";
    setPlanMode(next); // optimistic
    try {
      await fetch(`${getGatewayHttpUrl()}/api/plan_mode`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mode: next }),
      });
    } catch {
      /* rollback could go here; keep optimistic for Demo */
    }
  }

  return { planMode, togglePlanMode };
}
