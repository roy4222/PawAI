"use client";

import type { CapabilityTriState } from "@/contracts/types";

const TRI_LABEL: Record<CapabilityTriState, string> = {
  true: "OK",
  false: "BLOCK",
  unknown: "?",
};

const TRI_CLASS: Record<CapabilityTriState, string> = {
  true: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
  false: "bg-red-500/20 text-red-300 border-red-500/40",
  unknown: "bg-zinc-500/20 text-zinc-400 border-zinc-500/40",
};

export interface GateChipProps {
  name: string;
  value: CapabilityTriState;
  /** "compact" = `Nav OK` 一行 mono；"card" = 大字 + 標籤雙行（NavigationPanel 用） */
  variant?: "compact" | "card";
}

/**
 * GateChip — tri-state capability gate display (used in SkillTraceContent
 * + NavigationPanel). Single source of truth for tri-state colour mapping.
 */
export function GateChip({ name, value, variant = "compact" }: GateChipProps) {
  if (variant === "card") {
    return (
      <div
        className={`flex flex-col gap-0.5 rounded-lg border px-3 py-2 font-mono ${TRI_CLASS[value]}`}
        title={`${name} = ${value}`}
      >
        <span className="text-[10px] uppercase tracking-wider opacity-80">{name}</span>
        <span className="text-base font-bold leading-none">{TRI_LABEL[value]}</span>
      </div>
    );
  }
  return (
    <span
      className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 font-mono text-[10px] ${TRI_CLASS[value]}`}
      title={`${name} = ${value}`}
    >
      {name}
      <span className="font-bold">{TRI_LABEL[value]}</span>
    </span>
  );
}
