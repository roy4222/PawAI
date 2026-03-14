"use client"

import { PawPrint } from "lucide-react"
import { LiveIndicator } from "@/components/shared/live-indicator"

interface TopbarProps {
  isConnected: boolean
}

export function Topbar({ isConnected }: TopbarProps) {
  return (
    <header className="flex items-center justify-between h-12 px-5 border-b border-border/40 shrink-0 bg-background">
      <div className="flex items-center gap-2.5">
        <PawPrint className="h-5 w-5 text-primary" />
        <span className="text-sm font-semibold text-foreground tracking-tight">
          PawAI Studio
        </span>
      </div>
      <div className="flex items-center gap-2">
        <LiveIndicator active={isConnected} />
        <span className="text-xs text-muted-foreground">
          {isConnected ? "已連線" : "未連線"}
        </span>
      </div>
    </header>
  )
}
