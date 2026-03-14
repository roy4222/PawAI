"use client"

import { Badge } from "@/components/ui/badge"
import { ArrowUp, ArrowDown } from "lucide-react"
import { cn } from "@/lib/utils"

interface MetricChipProps {
  label: string
  value: number
  unit?: string
  trend?: "up" | "down" | "stable"
}

export function MetricChip({ label, value, unit, trend }: MetricChipProps) {
  return (
    <Badge
      variant="outline"
      className="border-[#2A2A35] bg-transparent gap-1 font-mono text-xs px-2 py-0.5"
    >
      <span className="text-[#8B8B9E]">{label}:</span>
      <span className="text-[#F0F0F5]">
        {value}
        {unit && <span className="text-[#55556A] ml-0.5">{unit}</span>}
      </span>
      {trend === "up" && (
        <ArrowUp className={cn("h-3 w-3 text-[#22C55E]")} />
      )}
      {trend === "down" && (
        <ArrowDown className={cn("h-3 w-3 text-[#EF4444]")} />
      )}
    </Badge>
  )
}
