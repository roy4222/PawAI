"use client"

/**
 * object-panel.tsx — 5-tab object detection panel.
 *
 * Tabs: 📷 本機鏡頭 / 📡 即時偵測 / 📋 偵測記錄 / 📊 偵測統計 / ✅ 白名單
 *
 * Ported from PR #40 (object_syu) — `/mock/yolo/start` Python control was
 * dropped in favour of `LiveFeedCard source="object"` (Jetson D435 + YOLO
 * debug image), see `local-camera.tsx`. All sections read from the same
 * gateway-driven `useStateStore.objectState` + `useEventStore.events`.
 */

import { useState } from "react"
import { Package } from "lucide-react"
import { useStateStore } from "@/stores/state-store"
import { useEventStore } from "@/stores/event-store"
import type { ObjectState } from "@/contracts/types"
import { cn } from "@/lib/utils"

import { isWhitelisted } from "./object-config"
import { LiveDetectionSection } from "./live-detection"
import { HistoryFeedSection } from "./history-feed"
import { StatsSection } from "./object-stats"
import { WhitelistSection } from "./whitelist-view"
import { LocalCameraView } from "./local-camera"

// Re-export functional helpers so other modules can import from one place.
export type { ObjectEntry } from "./object-config"
export { OBJECT_WHITELIST, isWhitelisted, getObjectEntry, getLabel } from "./object-config"

type Tab = "camera" | "live" | "feed" | "stats" | "whitelist"

const TABS: { id: Tab; label: string; emoji: string }[] = [
  { id: "camera", label: "本機鏡頭", emoji: "📷" },
  { id: "live", label: "即時偵測", emoji: "📡" },
  { id: "feed", label: "偵測記錄", emoji: "📋" },
  { id: "stats", label: "偵測統計", emoji: "📊" },
  { id: "whitelist", label: "白名單", emoji: "✅" },
]

export function ObjectPanel() {
  const [activeTab, setActiveTab] = useState<Tab>("camera")
  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const allEvents = useEventStore((s) => s.events)
  const allObjects = objectState?.detected_objects ?? []
  const isActive = objectState?.active ?? false
  const wlCount = allObjects.filter((o) => isWhitelisted(o.class_name)).length

  return (
    <div className="flex flex-col gap-4 w-full p-3 pt-0">
      {/* 頁頭 */}
      <div className="flex items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <Package className="h-5 w-5 text-amber-400" />
          <div>
            <h1 className="text-base font-bold text-foreground">物件偵測</h1>
            <p className="text-[11px] text-muted-foreground">YOLO26n · COCO 80-class</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isActive ? (
            <>
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                運作中
              </span>
              {wlCount > 0 && (
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 tabular-nums">
                  {wlCount} 個白名單物件
                </span>
              )}
            </>
          ) : (
            <span className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground border border-border/30">
              等待中
            </span>
          )}
        </div>
      </div>

      {/* Tab 導覽 */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-surface/60 border border-border/20">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-all duration-150",
              activeTab === tab.id
                ? "bg-card text-foreground shadow-sm border border-border/30"
                : "text-muted-foreground hover:text-foreground hover:bg-surface-hover",
            )}
          >
            <span className="text-sm">{tab.emoji}</span>
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab 內容 */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-0.5">
        {activeTab === "camera" && <LocalCameraView />}
        {activeTab === "live" && <LiveDetectionSection objects={allObjects} isActive={isActive} />}
        {activeTab === "feed" && <HistoryFeedSection events={allEvents} />}
        {activeTab === "stats" && <StatsSection events={allEvents} />}
        {activeTab === "whitelist" && <WhitelistSection />}
      </div>
    </div>
  )
}
