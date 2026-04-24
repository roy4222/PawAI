"use client"

// history-feed.tsx — 📋 偵測記錄 Feed
import type { PawAIEvent } from "@/contracts/types"
import { isWhitelisted, getObjectEntry, getLabel } from "./object-config"
import { extractObjectDetections } from "@/lib/object-event"
import { cn } from "@/lib/utils"

function FeedRow({ event }: { event: PawAIEvent }) {
  const data = event.data as Record<string, unknown>
  const raw  = extractObjectDetections(data)
  const wl   = raw.filter((o) => isWhitelisted(o.class_name))
  const mute = raw.filter((o) => !isWhitelisted(o.class_name))
  if (raw.length === 0) return null
  const time = new Date(event.timestamp).toLocaleTimeString("zh-TW", { hour12: false })
  return (
    <div className={cn(
      "flex items-start gap-3 py-2.5 px-3 rounded-lg border border-border/20 bg-surface/30",
      "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-1 motion-safe:duration-300",
      wl.length > 0 && "border-amber-400/15"
    )}>
      <span className="text-[10px] tabular-nums text-muted-foreground/60 font-mono mt-0.5 shrink-0 w-16">{time}</span>
      <div className="flex flex-wrap gap-1.5 flex-1">
        {wl.map((obj, i) => {
          const entry = getObjectEntry(obj.class_name)
          return (
            <span key={i} className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-amber-400/10 border border-amber-400/20 text-amber-300">
              <span>{entry?.emoji ?? "📦"}</span>
              <span className="font-medium">{getLabel(obj.class_name)}</span>
              <span className="text-[10px] opacity-70 font-mono">{Math.round(obj.confidence * 100)}%</span>
            </span>
          )
        })}
        {mute.map((obj, i) => (
          <span key={i} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-muted/50 border border-border/20 text-muted-foreground">
            <span>{getLabel(obj.class_name)}</span>
            <span className="opacity-50 font-mono">{Math.round(obj.confidence * 100)}%</span>
          </span>
        ))}
      </div>
    </div>
  )
}

export function HistoryFeedSection({ events }: { events: PawAIEvent[] }) {
  const objectEvents = events.filter((e) => e.source === "object").slice(0, 30)
  if (objectEvents.length === 0) {
    return <div className="flex items-center justify-center py-16 text-muted-foreground text-sm">尚無偵測記錄</div>
  }
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-3 px-1 pb-1 text-[10px] text-muted-foreground/70">
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-amber-400/60" />白名單（觸發 TTS）</span>
        <span className="flex items-center gap-1"><span className="inline-block w-2 h-2 rounded-full bg-border" />靜默</span>
      </div>
      {objectEvents.map((evt, i) => <FeedRow key={`${evt.id}-${i}`} event={evt} />)}
    </div>
  )
}
