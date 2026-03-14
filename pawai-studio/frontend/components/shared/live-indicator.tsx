"use client"

import { cn } from "@/lib/utils"

interface LiveIndicatorProps {
  active: boolean
}

export function LiveIndicator({ active }: LiveIndicatorProps) {
  return (
    <span
      className={cn(
        "inline-block w-1.5 h-1.5 rounded-full",
        active
          ? "bg-success motion-safe:animate-pulse"
          : "bg-muted-foreground/40"
      )}
    />
  )
}
