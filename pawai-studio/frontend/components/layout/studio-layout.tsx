"use client"

import { Topbar } from "./topbar"
import { PanelContainer } from "./panel-container"

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
  return (
    <div className="flex flex-col h-screen bg-[#0E0E13]">
      <Topbar isConnected={isConnected} />
      <div className="flex flex-1 overflow-hidden">
        <main className="flex-1 overflow-hidden">{mainPanel}</main>
        {sidebarPanels && sidebarPanels.length > 0 && (
          <PanelContainer position="sidebar">{sidebarPanels}</PanelContainer>
        )}
      </div>
      {bottomPanel && (
        <PanelContainer position="bottom">{bottomPanel}</PanelContainer>
      )}
    </div>
  )
}
