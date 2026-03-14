"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

interface EventItemProps {
  timestamp: string
  eventType: string
  source: string
  summary: string
  onClick?: () => void
}

const sourceColorMap: Record<string, string> = {
  face: "bg-blue-500/10 text-blue-400 border-transparent",
  speech: "bg-primary/10 text-primary border-transparent",
  gesture: "bg-success/10 text-success border-transparent",
  pose: "bg-orange-500/10 text-orange-400 border-transparent",
  brain: "bg-warning/10 text-warning border-transparent",
  system: "bg-info/10 text-info border-transparent",
}

function getSourceColor(source: string): string {
  const key = source.toLowerCase()
  for (const [k, v] of Object.entries(sourceColorMap)) {
    if (key.includes(k)) return v
  }
  return "bg-muted text-muted-foreground border-transparent"
}

export function EventItem({
  timestamp,
  eventType,
  source,
  summary,
  onClick,
}: EventItemProps) {
  return (
    <div
      className={cn(
        "flex flex-row items-center gap-2 p-2 rounded-lg transition-colors duration-150",
        onClick && "cursor-pointer hover:bg-surface-hover"
      )}
      onClick={onClick}
    >
      <span className="font-mono text-[11px] text-muted-foreground/60 shrink-0">
        {timestamp}
      </span>
      <Badge
        className={cn(
          "text-[10px] px-1.5 py-0 h-4 rounded-full font-normal shrink-0",
          getSourceColor(source)
        )}
      >
        {source}
      </Badge>
      <span className="text-xs text-muted-foreground shrink-0">{eventType}</span>
      <span className="text-xs text-foreground/80 flex-1 truncate">{summary}</span>
    </div>
  )
}
