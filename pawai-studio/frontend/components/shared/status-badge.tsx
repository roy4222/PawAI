"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type Status = "active" | "loading" | "error" | "inactive"

interface StatusBadgeProps {
  status: Status
}

const statusConfig: Record<Status, { className: string; label: string; pulse?: boolean }> = {
  active: {
    className: "bg-success/10 text-success border-transparent",
    label: "運作中",
  },
  loading: {
    className: "bg-warning/10 text-warning border-transparent",
    label: "載入中",
    pulse: true,
  },
  error: {
    className: "bg-destructive/10 text-destructive border-transparent",
    label: "錯誤",
  },
  inactive: {
    className: "bg-muted text-muted-foreground border-transparent",
    label: "離線",
  },
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status]

  return (
    <Badge
      className={cn(
        "text-[10px] px-1.5 py-0 h-5 rounded-full font-normal",
        config.className,
        config.pulse && "animate-pulse"
      )}
    >
      {config.label}
    </Badge>
  )
}
