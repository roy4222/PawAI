"use client"

interface PanelContainerProps {
  children: React.ReactNode
  position: "sidebar" | "bottom"
}

export function PanelContainer({ children, position }: PanelContainerProps) {
  if (position === "sidebar") {
    return (
      <aside className="flex flex-col gap-4 w-[340px] overflow-y-auto p-4 border-l border-[#2A2A35] bg-[#0E0E13]">
        {children}
      </aside>
    )
  }

  return (
    <div className="flex flex-row gap-4 h-[240px] w-full p-4 border-t border-[#2A2A35] bg-[#0E0E13] overflow-x-auto">
      {children}
    </div>
  )
}
