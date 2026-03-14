"use client"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"

type Status = "active" | "loading" | "error" | "inactive"

interface StatusBadgeProps {
  status: Status
}

const statusConfig: Record<Status, { className: string; label: string; pulse?: boolean }> = {
  active: {
    className: "bg-[#22C55E]/10 text-[#22C55E] border-transparent",
    label: "運作中",
  },
  loading: {
    className: "bg-[#F59E0B]/10 text-[#F59E0B] border-transparent",
    label: "載入中",
    pulse: true,
  },
  error: {
    className: "bg-[#EF4444]/10 text-[#EF4444] border-transparent",
    label: "錯誤",
  },
  inactive: {
    className: "bg-[#2A2A35] text-[#55556A] border-transparent",
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
