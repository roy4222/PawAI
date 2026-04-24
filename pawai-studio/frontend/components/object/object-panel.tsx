"use client"

/**
 * object-panel.tsx — 主進入點（組裝用）
 * ─────────────────────────────────────────────────────────────────
 * 只負責組裝各 section 元件，不包含任何業務邏輯或 UI 細節。
 *
 * 檔案結構：
 *   object-config.ts    功能層（白名單、TTS、工具函式）
 *   live-detection.tsx  📡 即時偵測卡片 Grid
 *   history-feed.tsx    📋 偵測記錄 Feed
 *   object-stats.tsx    📊 偵測統計長條圖
 *   whitelist-view.tsx  ✅ 白名單對照表
 *   local-camera.tsx    📷 本機鏡頭 + bbox overlay
 *   object-panel.tsx    ← 你在這裡（組裝 + export）
 */

import { useState } from "react"
import { Package } from "lucide-react"
import { PanelCard } from "@/components/shared/panel-card"
import { MetricChip } from "@/components/shared/metric-chip"
import { useStateStore } from "@/stores/state-store"
import { useEventStore } from "@/stores/event-store"
import type { ObjectState } from "@/contracts/types"
import { extractObjectDetections } from "@/lib/object-event"
import { cn } from "@/lib/utils"

import { isWhitelisted, getObjectEntry, getLabel } from "./object-config"
import { LiveDetectionSection } from "./live-detection"
import { HistoryFeedSection }   from "./history-feed"
import { StatsSection }         from "./object-stats"
import { WhitelistSection }     from "./whitelist-view"
import { LocalCameraView }      from "./local-camera"

// Re-export 功能函式，讓其他模組（如 use-layout-manager）能直接從這裡 import
export type { ObjectEntry } from "./object-config"
export { OBJECT_WHITELIST, isWhitelisted, getObjectEntry, getLabel } from "./object-config"

// ── Tab 定義 ────────────────────────────────────────────────────

type Tab = "camera" | "live" | "feed" | "stats" | "whitelist"

const TABS: { id: Tab; label: string; emoji: string }[] = [
  { id: "camera",    label: "本機鏡頭", emoji: "📷" },
  { id: "live",      label: "即時偵測", emoji: "📡" },
  { id: "feed",      label: "偵測記錄", emoji: "📋" },
  { id: "stats",     label: "偵測統計", emoji: "📊" },
  { id: "whitelist", label: "白名單",   emoji: "✅" },
]

// ── Sidebar Panel（首頁側欄，精簡卡片）──────────────────────────

function SidebarPanel() {
  const objectState  = useStateStore((s) => s.objectState) as ObjectState | null
  const allEvents    = useEventStore((s) => s.events)
  const objectEvents = allEvents.filter((e) => e.source === "object").slice(0, 10)

  const panelStatus: "active" | "inactive" | "loading" =
    objectState === null ? "loading" : objectState.active ? "active" : "inactive"

  const allObjects       = objectState?.detected_objects ?? []
  const whitelistedObjs  = allObjects.filter((o) => isWhitelisted(o.class_name))
  const filteredOutCount = allObjects.length - whitelistedObjs.length

  return (
    <PanelCard
      title="物件偵測" href="/studio/object"
      icon={<Package className="h-4 w-4" />}
      status={panelStatus}
      count={whitelistedObjs.length || undefined}
      defaultCollapsed
    >
      <div className="flex flex-col gap-3">
        {panelStatus === "loading" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
            <span>正在連線...</span>
          </div>
        )}
        {panelStatus === "inactive" && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <Package className="h-8 w-8 opacity-30" />
            <span>尚未偵測到白名單物件</span>
          </div>
        )}
        {panelStatus === "active" && (
          <>
            {whitelistedObjs.length > 0 ? (
              <div className="flex flex-col gap-2">
                {whitelistedObjs.map((obj, i) => {
                  const entry = getObjectEntry(obj.class_name)
                  return (
                    <div key={`${obj.class_name}-${i}`} className={cn(
                      "rounded-lg border border-border/30 bg-surface/50 px-4 py-3 flex flex-col gap-1.5",
                      "motion-safe:animate-in motion-safe:slide-in-from-right-4 motion-safe:duration-200",
                      "hover:bg-surface-hover transition-colors duration-150"
                    )}>
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex items-center gap-2">
                          <span className="text-xl select-none">{entry?.emoji ?? "📦"}</span>
                          <div className="flex flex-col gap-0">
                            <span className="text-sm font-semibold text-foreground">{getLabel(obj.class_name)}</span>
                            <span className="text-[10px] text-muted-foreground font-mono">{obj.class_name} · class_id {entry?.classId ?? "?"}</span>
                          </div>
                        </div>
                        <MetricChip label="信心度" value={Math.round(obj.confidence * 100)} unit="%" />
                      </div>
                      {entry && (
                        <div className="text-[11px] text-muted-foreground bg-surface/60 rounded-md px-2.5 py-1.5 border border-border/10">
                          <span className="text-amber-400/80 font-medium">情境：</span>{entry.situation}
                        </div>
                      )}
                      {entry?.tts && (
                        <div className="text-[11px] text-emerald-400/90 flex items-start gap-1.5">
                          <span className="shrink-0">🔊</span>
                          <span className="italic">「{entry.tts}」</span>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                偵測到非白名單物件（{filteredOutCount} 個），無情境反應
              </div>
            )}
            {filteredOutCount > 0 && whitelistedObjs.length > 0 && (
              <p className="text-[10px] text-muted-foreground/50 px-0.5">另有 {filteredOutCount} 個非白名單物件已過濾</p>
            )}
            {objectEvents.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[11px] text-muted-foreground font-medium px-0.5">偵測記錄</span>
                {objectEvents.map((evt, i) => {
                  const data = evt.data as Record<string, unknown>
                  const objs = extractObjectDetections(data)
                  const wl   = objs.filter((o) => isWhitelisted(o.class_name))
                  if (wl.length === 0) return null
                  const time = new Date(evt.timestamp).toLocaleTimeString("zh-TW", { hour12: false })
                  return (
                    <div key={`${evt.id}-${i}`} className={cn("flex items-center gap-2 rounded-md px-2.5 py-1.5 bg-surface/40 border border-border/20 text-xs text-muted-foreground")}>
                      <span className="shrink-0">{wl.map((o) => getObjectEntry(o.class_name)?.emoji ?? "📦").join("")}</span>
                      <span className="text-foreground font-medium">{wl.map((o) => getLabel(o.class_name)).join("、")}</span>
                      <span className="ml-auto tabular-nums">{time}</span>
                      <span className="shrink-0 text-[10px]">{Math.round((wl[0].confidence ?? 0) * 100)}%</span>
                    </div>
                  )
                })}
              </div>
            )}
          </>
        )}
      </div>
    </PanelCard>
  )
}

// ── Full Page Panel（/studio/object）────────────────────────────

function FullPagePanel() {
  const [activeTab, setActiveTab] = useState<Tab>("camera")
  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const allEvents   = useEventStore((s) => s.events)
  const allObjects  = objectState?.detected_objects ?? []
  const isActive    = objectState?.active ?? false
  const wlCount     = allObjects.filter((o) => isWhitelisted(o.class_name)).length

  return (
    <div className="flex flex-col gap-4 w-full h-full">
      {/* 頁頭 */}
      <div className="flex items-center justify-between gap-3 px-1">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl select-none">📦</span>
          <div>
            <h1 className="text-base font-bold text-foreground">物件偵測</h1>
            <p className="text-[11px] text-muted-foreground">YOLO26n · COCO 80-class</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {isActive ? (
            <>
              <span className="inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />運作中
              </span>
              {wlCount > 0 && (
                <span className="text-xs px-2.5 py-1 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 tabular-nums">
                  {wlCount} 個白名單物件
                </span>
              )}
            </>
          ) : (
            <span className="text-xs px-2.5 py-1 rounded-full bg-muted text-muted-foreground border border-border/30">等待中</span>
          )}
        </div>
      </div>

      {/* Tab 導覽 */}
      <div className="flex items-center gap-1 p-1 rounded-xl bg-surface/60 border border-border/20">
        {TABS.map((tab) => (
          <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={cn(
            "flex-1 flex items-center justify-center gap-1.5 py-2 px-3 rounded-lg text-xs font-medium transition-all duration-150",
            activeTab === tab.id
              ? "bg-card text-foreground shadow-sm border border-border/30"
              : "text-muted-foreground hover:text-foreground hover:bg-surface-hover"
          )}>
            <span className="text-sm">{tab.emoji}</span>
            <span className="hidden sm:inline">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab 內容 */}
      <div className="flex-1 overflow-y-auto min-h-0 pr-0.5">
        {activeTab === "camera"    && <LocalCameraView />}
        {activeTab === "live"      && <LiveDetectionSection objects={allObjects} isActive={isActive} />}
        {activeTab === "feed"      && <HistoryFeedSection events={allEvents} />}
        {activeTab === "stats"     && <StatsSection events={allEvents} />}
        {activeTab === "whitelist" && <WhitelistSection />}
      </div>
    </div>
  )
}

// ── Export ──────────────────────────────────────────────────────

export function ObjectPanel({ fullPage = false }: { fullPage?: boolean }) {
  if (fullPage) return <FullPagePanel />
  return <SidebarPanel />
}
