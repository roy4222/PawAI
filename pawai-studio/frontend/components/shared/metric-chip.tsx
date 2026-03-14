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
      className="border-border/50 bg-transparent gap-1 font-mono text-xs px-2 py-0.5"
    >
      <span className="text-muted-foreground">{label}:</span>
      <span className="text-foreground">
        {value}
        {unit && <span className="text-muted-foreground/60 ml-0.5">{unit}</span>}
      </span>
      {trend === "up" && (
        <ArrowUp className={cn("h-3 w-3 text-success")} />
      )}
      {trend === "down" && (
        <ArrowDown className={cn("h-3 w-3 text-destructive")} />
      )}
    </Badge>
  )
}
