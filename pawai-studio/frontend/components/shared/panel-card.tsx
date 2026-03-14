"use client"

import { X } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "./status-badge"
import { LiveIndicator } from "./live-indicator"

type Status = "active" | "loading" | "error" | "inactive"

interface PanelCardProps {
  title: string
  icon: React.ReactNode
  status?: Status
  count?: number
  onDismiss?: () => void
  children: React.ReactNode
}

export function PanelCard({
  title,
  icon,
  status = "inactive",
  count,
  onDismiss,
  children,
}: PanelCardProps) {
  const showLive = status === "active" || status === "loading"

  return (
    <Card className="bg-card border-border/50 rounded-xl">
      <CardHeader className="p-3 flex flex-row items-center gap-2 space-y-0">
        <span className="h-4 w-4 text-muted-foreground shrink-0 flex items-center justify-center">
          {icon}
        </span>
        <span className="text-sm font-medium text-foreground flex-1 truncate">
          {title}
        </span>
        {count !== undefined && (
          <Badge className="rounded-full bg-muted text-muted-foreground border-transparent text-[10px] px-1.5 py-0 h-5 font-normal">
            {count}
          </Badge>
        )}
        {showLive && <LiveIndicator active={status === "active"} />}
        <StatusBadge status={status} />
        {onDismiss && (
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 p-0 opacity-50 hover:opacity-100 hover:bg-transparent text-muted-foreground cursor-pointer"
            onClick={onDismiss}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </CardHeader>
      <CardContent className="p-3 pt-0">{children}</CardContent>
    </Card>
  )
}
