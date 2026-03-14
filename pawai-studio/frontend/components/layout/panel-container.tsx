"use client"

interface PanelContainerProps {
  children: React.ReactNode
  position: "sidebar" | "bottom"
}

export function PanelContainer({ children, position }: PanelContainerProps) {
  if (position === "sidebar") {
    return (
      <aside className="flex flex-col gap-3 w-[360px] overflow-y-auto p-4 border-l border-border/40 bg-background animate-in slide-in-from-right-4 duration-300">
        {children}
      </aside>
    )
  }

  return (
    <div className="flex flex-row gap-3 h-[240px] w-full p-4 border-t border-border/40 bg-background overflow-x-auto animate-in slide-in-from-bottom-4 duration-300">
      {children}
    </div>
  )
}
