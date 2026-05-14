"use client";

import { Brain, ShieldCheck } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { cn } from "@/lib/utils";

const MODE_LABEL: Record<string, string> = {
  idle: "待命",
  chat: "聊天",
  skill: "技能",
  sequence: "序列",
  alert: "警示",
  safety_stop: "安全停止",
};

export function BrainStatusStrip() {
  const brain = useStateStore((state) => state.brainState);
  const mode = brain?.mode ?? "idle";
  const active = brain?.active_plan;
  const safety = brain?.safety_flags;

  return (
    <div className="flex min-h-11 items-center gap-3 border-b border-border/50 bg-surface/60 px-4 text-xs">
      <div className="flex items-center gap-2 font-medium text-foreground">
        <Brain className="h-4 w-4 text-sky-400" />
        <span>Brain</span>
        <span className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[11px]">
          {MODE_LABEL[mode] ?? mode}
        </span>
      </div>
      {active && (
        <div className="min-w-0 truncate text-muted-foreground">
          <span className="font-mono text-foreground">{active.selected_skill}</span>
          {active.step_total ? (
            <span className="ml-2">
              step {active.step_index + 1}/{active.step_total}
            </span>
          ) : null}
        </div>
      )}
      <div className="ml-auto flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
        <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" />
        <span className={cn(safety?.obstacle && "text-amber-400")}>
          obs:{safety?.obstacle ? "on" : "ok"}
        </span>
        <span className={cn(safety?.emergency && "text-red-400")}>
          emg:{safety?.emergency ? "on" : "ok"}
        </span>
        <span className={cn(safety?.fallen && "text-red-400")}>
          fall:{safety?.fallen ? "on" : "ok"}
        </span>
        <span>tts:{safety?.tts_playing ? "on" : "idle"}</span>
      </div>
    </div>
  );
}
