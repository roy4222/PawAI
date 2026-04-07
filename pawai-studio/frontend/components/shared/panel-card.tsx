"use client"

import { useState } from "react"
import Link from "next/link"
import { X, ChevronDown, ChevronRight, ExternalLink } from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { StatusBadge } from "./status-badge"
import { LiveIndicator } from "./live-indicator"
import { cn } from "@/lib/utils"

type Status = "active" | "loading" | "error" | "inactive"

interface PanelCardProps {
  title: string
  icon: React.ReactNode
  status?: Status
  count?: number
  defaultCollapsed?: boolean
  href?: string
  onDismiss?: () => void
  children: React.ReactNode
}

export function PanelCard({
  title,
  icon,
  status = "inactive",
  count,
  defaultCollapsed = false,
  href,
  onDismiss,
  children,
}: PanelCardProps) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed)
  const showLive = status === "active" || status === "loading"

  return (
    <Card className="bg-card border-border/50 rounded-xl">
      <CardHeader
        className="p-3 flex flex-row items-center gap-2 space-y-0 cursor-pointer select-none hover:bg-surface-hover/50 transition-colors duration-150 rounded-t-xl"
        onClick={() => setCollapsed((c) => !c)}
      >
        {/* Collapse indicator */}
        {collapsed
          ? <ChevronRight className="h-3 w-3 text-muted-foreground/50 shrink-0" />
          : <ChevronDown className="h-3 w-3 text-muted-foreground/50 shrink-0" />
        }
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
        {href && (
          <Link
            href={href}
            onClick={(e) => e.stopPropagation()}
            className="h-5 w-5 flex items-center justify-center opacity-40 hover:opacity-100 text-muted-foreground hover:text-foreground transition-opacity"
            title="開啟詳細頁面"
          >
            <ExternalLink className="h-3 w-3" />
          </Link>
        )}
        {onDismiss && (
          <Button
            variant="ghost"
            size="icon"
            className="h-5 w-5 p-0 opacity-50 hover:opacity-100 hover:bg-transparent text-muted-foreground cursor-pointer"
            onClick={(e) => { e.stopPropagation(); onDismiss(); }}
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </CardHeader>
      <div className={cn(
        "overflow-hidden transition-all duration-200",
        collapsed ? "max-h-0" : "max-h-[400px]"
      )}>
        <CardContent className="p-3 pt-0 overflow-y-auto max-h-[380px]">
          {children}
        </CardContent>
      </div>
    </Card>
  )
}
