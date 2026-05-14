"use client";

import { useStateStore } from "@/stores/state-store";
import { GateChip } from "@/components/shared/gate-chip";
import { useTogglePlanMode } from "@/hooks/use-toggle-plan-mode";

/**
 * NavigationPanel — Sheet content for the "navigation" feature button.
 *
 * Surfaces three live signals that observers care about during a Demo:
 *   1. Capability gates (Nav Ready / Depth Clear) — tri-state
 *   2. Plan A / Plan B toggle — quick switch when network or LLM degrades
 *   3. (future) recent nav goals + map snapshot — left as TODO note
 *
 * No panel-card wrapper here — Sheet provides the chrome. Just stack
 * sections with consistent spacing.
 */
export function NavigationPanel() {
  const capability = useStateStore((s) => s.capability);
  const { planMode, togglePlanMode } = useTogglePlanMode();

  const planAClasses =
    planMode === "A"
      ? "bg-emerald-500/20 text-emerald-200 border-emerald-500/40 hover:bg-emerald-500/30"
      : "bg-zinc-500/10 text-zinc-300 border-zinc-500/30 hover:bg-zinc-500/20";

  const planBClasses =
    planMode === "B"
      ? "bg-amber-500/20 text-amber-200 border-amber-500/40 hover:bg-amber-500/30"
      : "bg-zinc-500/10 text-zinc-300 border-zinc-500/30 hover:bg-zinc-500/20";

  return (
    <div className="flex flex-col gap-5 p-4">
      {/* Section 1 — Capability Gates */}
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Capability Gates
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <GateChip name="Nav Ready" value={capability.nav_ready} variant="card" />
          <GateChip name="Depth Clear" value={capability.depth_clear} variant="card" />
        </div>
        <p className="text-[11px] text-muted-foreground/70 leading-relaxed">
          兩個 gate 必須都為 <span className="text-emerald-400 font-mono">OK</span> 才允許
          高風險動作（NAV / 大幅 MOTION）。<span className="font-mono">unknown</span> 表示
          還沒收到對應 topic 訊息，與 <span className="font-mono">BLOCK</span> 一樣保守
          降級為 SAY。
        </p>
      </section>

      {/* Section 2 — Plan A / B */}
      <section className="flex flex-col gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Plan Mode
        </h3>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => {
              if (planMode !== "A") togglePlanMode();
            }}
            className={`flex flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors ${planAClasses}`}
          >
            <span className="font-mono text-[10px] uppercase tracking-wider opacity-80">
              Plan A
            </span>
            <span className="text-sm font-semibold">完整智能流程</span>
            <span className="text-[11px] opacity-70">LLM + skill arbitration</span>
          </button>
          <button
            type="button"
            onClick={() => {
              if (planMode !== "B") togglePlanMode();
            }}
            className={`flex flex-col gap-1 rounded-lg border px-3 py-2 text-left transition-colors ${planBClasses}`}
          >
            <span className="font-mono text-[10px] uppercase tracking-wider opacity-80">
              Plan B
            </span>
            <span className="text-sm font-semibold">固定台詞</span>
            <span className="text-[11px] opacity-70">網斷時的演出腳本</span>
          </button>
        </div>
      </section>

      {/* Section 3 — Future content placeholder */}
      <section className="flex flex-col gap-1 rounded-lg border border-dashed border-border/50 p-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/60">
          Coming next (B7 / D-day)
        </h3>
        <p className="text-[11px] text-muted-foreground/50 leading-relaxed">
          最近 nav goal 列表、距離 / ETA chip、建圖 snapshot 預覽。
        </p>
      </section>
    </div>
  );
}
