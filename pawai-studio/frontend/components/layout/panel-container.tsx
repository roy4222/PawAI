"use client"

import { useState, useCallback, useRef, useEffect } from "react"
import { cn } from "@/lib/utils"

interface PanelContainerProps {
  children: React.ReactNode
  position: "sidebar" | "bottom"
}

const SIDEBAR_MIN = 280
const SIDEBAR_MAX = 600
const SIDEBAR_DEFAULT = 380

export function PanelContainer({ children, position }: PanelContainerProps) {
  const [width, setWidth] = useState(SIDEBAR_DEFAULT)
  const dragging = useRef(false)
  const startX = useRef(0)
  const startW = useRef(0)

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    dragging.current = true
    startX.current = e.clientX
    startW.current = width
    document.body.style.cursor = "col-resize"
    document.body.style.userSelect = "none"
  }, [width])

  useEffect(() => {
    const onMouseMove = (e: MouseEvent) => {
      if (!dragging.current) return
      // Dragging left = wider sidebar (sidebar is on the right)
      const delta = startX.current - e.clientX
      const newW = Math.min(SIDEBAR_MAX, Math.max(SIDEBAR_MIN, startW.current + delta))
      setWidth(newW)
    }
    const onMouseUp = () => {
      if (!dragging.current) return
      dragging.current = false
      document.body.style.cursor = ""
      document.body.style.userSelect = ""
    }
    window.addEventListener("mousemove", onMouseMove)
    window.addEventListener("mouseup", onMouseUp)
    return () => {
      window.removeEventListener("mousemove", onMouseMove)
      window.removeEventListener("mouseup", onMouseUp)
      if (dragging.current) {
        dragging.current = false
        document.body.style.cursor = ""
        document.body.style.userSelect = ""
      }
    }
  }, [])

  if (position === "sidebar") {
    return (
      <aside
        className="relative flex flex-col gap-3 overflow-y-auto p-4 border-l border-border/40 bg-background animate-in slide-in-from-right-4 duration-300"
        style={{ width }}
      >
        {/* Resize handle */}
        <div
          className={cn(
            "absolute left-0 top-0 bottom-0 w-1 cursor-col-resize z-10",
            "hover:bg-sky-400/30 active:bg-sky-400/50 transition-colors"
          )}
          onMouseDown={onMouseDown}
        />
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
