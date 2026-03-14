"use client"

import { PawPrint, Settings } from "lucide-react"
import { Button } from "@/components/ui/button"
import { LiveIndicator } from "@/components/shared/live-indicator"

interface TopbarProps {
  isConnected: boolean
}

export function Topbar({ isConnected }: TopbarProps) {
  return (
    <header className="flex items-center justify-between h-12 px-4 bg-[#141419] border-b border-[#2A2A35] shrink-0">
      <div className="flex items-center gap-2">
        <PawPrint className="h-4 w-4 text-[#7C6BFF]" />
        <span className="text-sm font-semibold text-[#F0F0F5]">PawAI Studio</span>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <LiveIndicator active={isConnected} />
          <span className="text-xs text-[#8B8B9E]">
            {isConnected ? "已連線" : "未連線"}
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-[#8B8B9E] hover:text-[#F0F0F5] hover:bg-[#2A2A35]"
        >
          <Settings className="h-4 w-4" />
        </Button>
      </div>
    </header>
  )
}
