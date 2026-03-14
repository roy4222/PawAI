"use client"

import { Topbar } from "./topbar"
import { PanelContainer } from "./panel-container"
import { cn } from "@/lib/utils"

interface StudioLayoutProps {
  mainPanel: React.ReactNode
  sidebarPanels?: React.ReactNode[]
  bottomPanel?: React.ReactNode
  isConnected: boolean
}

export function StudioLayout({
  mainPanel,
  sidebarPanels,
  bottomPanel,
  isConnected,
}: StudioLayoutProps) {
  const hasSidebar = sidebarPanels && sidebarPanels.length > 0

  return (
    <div className="flex flex-col h-screen bg-background">
      <Topbar isConnected={isConnected} />
      <div className="flex flex-1 overflow-hidden">
        <main className={cn(
          "flex-1 overflow-hidden transition-all duration-300 ease-out",
        )}>
          {mainPanel}
        </main>
        {hasSidebar && (
          <PanelContainer position="sidebar">{sidebarPanels}</PanelContainer>
        )}
      </div>
      {bottomPanel && (
        <PanelContainer position="bottom">{bottomPanel}</PanelContainer>
      )}
    </div>
  )
}
