"use client";

import { useEventStore } from "@/stores/event-store";
import type { PawAIEvent } from "@/contracts/types";

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("zh-TW", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return "--:--:--";
  }
}

export function EventTicker() {
  const events = useEventStore((s) => s.events);
  const recent = events.slice(0, 20);

  return (
    <div className="h-10 border-t border-zinc-800/60 flex items-center px-4 overflow-hidden shrink-0">
      <span className="text-[10px] text-zinc-600 mr-3 shrink-0">EVENTS</span>
      <div className="flex gap-4 overflow-x-auto no-scrollbar">
        {recent.map((e: PawAIEvent, i: number) => (
          <span
            key={`${e.id}-${i}`}
            className="text-[10px] font-mono text-emerald-400/70 whitespace-nowrap"
          >
            {formatTime(e.timestamp)} {e.source}.{e.event_type}
          </span>
        ))}
        {recent.length === 0 && (
          <span className="text-[10px] text-zinc-700">
            waiting for events...
          </span>
        )}
      </div>
    </div>
  );
}
