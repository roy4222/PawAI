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
          ? "bg-[#22C55E] motion-safe:animate-pulse"
          : "bg-[#55556A]"
      )}
    />
  )
}
