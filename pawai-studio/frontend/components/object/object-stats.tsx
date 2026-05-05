"use client"

// object-stats.tsx — 📊 偵測統計長條圖（PR #40 port）
import type { PawAIEvent } from "@/contracts/types"
import { OBJECT_WHITELIST, isWhitelisted, getLabel } from "./object-config"
import { extractObjectDetections } from "@/lib/object-event"
import { cn } from "@/lib/utils"

function useObjectStats(events: PawAIEvent[]): Map<string, number> {
  const stats = new Map<string, number>()
  for (const evt of events) {
    if (evt.source !== "object") continue
    const data = evt.data as Record<string, unknown>
    const objs = extractObjectDetections(data)
    for (const obj of objs) stats.set(obj.class_name, (stats.get(obj.class_name) ?? 0) + 1)
  }
  return stats
}

function StatBar({
  label,
  emoji,
  count,
  maxCount,
  inWhitelist,
}: {
  label: string
  emoji: string
  count: number
  maxCount: number
  inWhitelist: boolean
}) {
  const pct = maxCount > 0 ? (count / maxCount) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1.5 w-24 shrink-0">
        <span className="text-base select-none leading-none">{emoji}</span>
        <span className={cn("text-xs truncate", inWhitelist ? "text-foreground font-medium" : "text-muted-foreground")}>
          {label}
        </span>
      </div>
      <div className="flex-1 h-2 bg-border/30 rounded-full overflow-hidden">
        <div
          className={cn(
            "h-full rounded-full transition-all duration-700 ease-out",
            inWhitelist ? "bg-amber-400/70" : "bg-muted-foreground/30",
          )}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span
        className={cn(
          "text-xs tabular-nums font-mono w-6 text-right shrink-0",
          inWhitelist ? "text-amber-400" : "text-muted-foreground/60",
        )}
      >
        {count}
      </span>
    </div>
  )
}

export function StatsSection({ events }: { events: PawAIEvent[] }) {
  const stats = useObjectStats(events)
  if (stats.size === 0) {
    return <div className="flex items-center justify-center py-16 text-muted-foreground text-sm">暫無統計資料</div>
  }
  const allKeys = new Set([...stats.keys(), ...OBJECT_WHITELIST.map((e) => e.className)])
  const sorted = [...allKeys]
    .map((k) => [k, stats.get(k) ?? 0] as [string, number])
    .sort((a, b) => b[1] - a[1])
  const maxCount = sorted[0]?.[1] ?? 1
  const total = [...stats.values()].reduce((a, b) => a + b, 0)
  const wlTotal = OBJECT_WHITELIST.map((e) => stats.get(e.className) ?? 0).reduce((a, b) => a + b, 0)

  return (
    <div className="flex flex-col gap-4">
      <div className="grid grid-cols-3 gap-2">
        {[
          { label: "偵測總次數", value: total },
          { label: "白名單觸發", value: wlTotal },
          { label: "種類數", value: stats.size },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg bg-surface/60 border border-border/20 px-3 py-2.5 flex flex-col gap-0.5">
            <span className="text-[10px] text-muted-foreground">{label}</span>
            <span className="text-xl font-bold text-foreground tabular-nums">{value}</span>
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2.5">
        {sorted.map(([className, count]) => {
          const entry = OBJECT_WHITELIST.find((e) => e.className === className)
          return (
            <StatBar
              key={className}
              label={getLabel(className)}
              emoji={entry?.emoji ?? "📦"}
              count={count}
              maxCount={maxCount}
              inWhitelist={isWhitelisted(className)}
            />
          )
        })}
      </div>
      <p className="text-[10px] text-muted-foreground/40 text-right">🟡 金色 = 白名單 · 灰色 = 靜默過濾</p>
    </div>
  )
}
