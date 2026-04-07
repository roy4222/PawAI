"use client"

import { Package } from "lucide-react"
import { PanelCard } from "@/components/shared/panel-card"
import { MetricChip } from "@/components/shared/metric-chip"
import { useStateStore } from "@/stores/state-store"
import { useEventStore } from "@/stores/event-store"
import type { ObjectState, PawAIEvent } from "@/contracts/types"
import { cn } from "@/lib/utils"

// ── COCO class labels ────────────────────────────────────────────

const COCO_LABELS: Record<string, { zh: string; icon: string }> = {
  person:        { zh: "人",      icon: "person" },
  bicycle:       { zh: "腳踏車",  icon: "bicycle" },
  car:           { zh: "汽車",    icon: "car" },
  dog:           { zh: "狗",      icon: "dog" },
  cat:           { zh: "貓",      icon: "cat" },
  chair:         { zh: "椅子",    icon: "chair" },
  bottle:        { zh: "瓶子",    icon: "bottle" },
  cup:           { zh: "杯子",    icon: "cup" },
  book:          { zh: "書",      icon: "book" },
  dining_table:  { zh: "餐桌",    icon: "table" },
  cell_phone:    { zh: "手機",    icon: "phone" },
  laptop:        { zh: "筆電",    icon: "laptop" },
  backpack:      { zh: "背包",    icon: "backpack" },
  umbrella:      { zh: "雨傘",    icon: "umbrella" },
  handbag:       { zh: "手提包",  icon: "bag" },
}

function getLabel(className: string): string {
  return COCO_LABELS[className]?.zh ?? className
}

const MAX_HISTORY = 10

// ── Event history item ───────────────────────────────────────────

function ObjectEventItem({ event }: { event: PawAIEvent }) {
  const data = event.data as Record<string, unknown>
  const objects = (data.objects ?? data.detected_objects ?? []) as Array<{ class_name: string; confidence: number }>
  const time = new Date(event.timestamp).toLocaleTimeString("zh-TW", { hour12: false })

  return (
    <div className={cn(
      "flex items-center gap-2 rounded-md px-2.5 py-1.5",
      "bg-surface/40 border border-border/20",
      "text-xs text-muted-foreground",
    )}>
      <Package className="h-3 w-3 shrink-0 text-amber-400/60" />
      <span className="text-foreground font-medium">
        {objects.map(o => getLabel(o.class_name)).join(", ")}
      </span>
      <span className="ml-auto tabular-nums">{time}</span>
      {objects.length > 0 && (
        <span className="shrink-0 text-[10px]">
          {Math.round((objects[0].confidence ?? 0) * 100)}%
        </span>
      )}
    </div>
  )
}

// ── Main component ───────────────────────────────────────────────

export function ObjectPanel() {
  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const allEvents = useEventStore((s) => s.events)

  const objectEvents = allEvents
    .filter((e) => e.source === "object")
    .slice(0, MAX_HISTORY)

  const panelStatus: "active" | "inactive" | "loading" =
    objectState === null ? "loading"
      : objectState.active ? "active"
        : "inactive"

  const objects = objectState?.detected_objects ?? []

  return (
    <PanelCard
      title="物件偵測"
      href="/studio/object"
      icon={<Package className="h-4 w-4" />}
      status={panelStatus}
      count={objects.length || undefined}
      defaultCollapsed
    >
      <div className="flex flex-col gap-3">

        {/* Loading */}
        {panelStatus === "loading" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
            <span>正在連線...</span>
          </div>
        )}

        {/* Inactive */}
        {panelStatus === "inactive" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <Package className="h-8 w-8 opacity-30" />
            <span>尚未偵測到物件</span>
          </div>
        )}

        {/* Active: detected objects */}
        {panelStatus === "active" && (
          <>
            <div className="flex flex-col gap-2">
              {objects.map((obj, i) => (
                <div
                  key={`${obj.class_name}-${i}`}
                  className={cn(
                    "rounded-lg border border-border/30 bg-surface/50 px-4 py-3",
                    "flex items-center justify-between gap-3",
                    "motion-safe:animate-in motion-safe:slide-in-from-right-4 motion-safe:duration-200",
                    "hover:bg-surface-hover motion-safe:transition-colors motion-safe:duration-150",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Package className="h-5 w-5 text-amber-400 shrink-0" />
                    <div className="flex flex-col gap-0.5">
                      <span className="text-sm font-semibold text-foreground">
                        {getLabel(obj.class_name)}
                      </span>
                      <span className="text-[10px] text-muted-foreground font-mono">
                        {obj.class_name}
                      </span>
                    </div>
                  </div>
                  <MetricChip
                    label="信心度"
                    value={Math.round(obj.confidence * 100)}
                    unit="%"
                  />
                </div>
              ))}
            </div>

            {/* Event history */}
            {objectEvents.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[11px] text-muted-foreground font-medium px-0.5">
                  偵測記錄
                </span>
                {objectEvents.map((evt) => (
                  <ObjectEventItem key={evt.id} event={evt} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </PanelCard>
  )
}
