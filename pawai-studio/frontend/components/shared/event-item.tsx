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
  speech: "bg-purple-500/10 text-purple-400 border-transparent",
  gesture: "bg-[#22C55E]/10 text-[#22C55E] border-transparent",
  pose: "bg-orange-500/10 text-orange-400 border-transparent",
}

function getSourceColor(source: string): string {
  const key = source.toLowerCase()
  for (const [k, v] of Object.entries(sourceColorMap)) {
    if (key.includes(k)) return v
  }
  return "bg-[#2A2A35] text-[#8B8B9E] border-transparent"
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
        "flex flex-row items-center gap-2 p-1.5 rounded-lg transition-colors duration-150",
        onClick && "cursor-pointer hover:bg-[#1C1C24]"
      )}
      onClick={onClick}
    >
      <span className="font-mono text-xs text-[#55556A] shrink-0">
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
      <span className="text-xs text-[#8B8B9E] shrink-0">{eventType}</span>
      <span className="text-xs text-[#F0F0F5] flex-1 truncate">{summary}</span>
    </div>
  )
}
