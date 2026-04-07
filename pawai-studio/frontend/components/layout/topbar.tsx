"use client"

import Link from "next/link"
import { PawPrint, Monitor } from "lucide-react"
import { LiveIndicator } from "@/components/shared/live-indicator"

interface TopbarProps {
  isConnected: boolean
}

export function Topbar({ isConnected }: TopbarProps) {
  return (
    <header className="relative flex items-center justify-between h-12 px-5 border-b border-border/40 shrink-0 bg-background">
      <Link href="/studio" className="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
        <PawPrint className="h-5 w-5 text-primary" />
        <span className="text-sm font-semibold text-foreground tracking-tight">
          PawAI Studio
        </span>
        <span className="text-[10px] font-mono text-muted-foreground/50 uppercase tracking-widest ml-1">
          control
        </span>
      </Link>
      <div className="flex items-center gap-2">
        <Link
          href="/studio/live"
          className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-mono text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800/50 transition-colors"
        >
          <Monitor className="h-3 w-3" />
          LIVE
        </Link>
        <LiveIndicator active={isConnected} />
        <span className="text-xs text-muted-foreground">
          {isConnected ? "已連線" : "未連線"}
        </span>
      </div>
      {/* Accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sky-400/30 to-transparent" />
    </header>
  )
}
