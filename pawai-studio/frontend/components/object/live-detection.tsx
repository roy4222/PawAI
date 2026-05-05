"use client"

// live-detection.tsx — 📡 即時偵測卡片 Grid（PR #40 port）
import { isWhitelisted, getObjectEntry, getLabel } from "./object-config"
import { cn } from "@/lib/utils"

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100)
  const color = pct >= 80 ? "bg-emerald-400" : pct >= 60 ? "bg-amber-400" : "bg-rose-400"
  const text = pct >= 80 ? "text-emerald-400" : pct >= 60 ? "text-amber-400" : "text-rose-400"
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-border/40 rounded-full overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${pct}%` }} />
      </div>
      <span className={cn("text-[11px] tabular-nums font-mono font-semibold shrink-0", text)}>{pct}%</span>
    </div>
  )
}

interface DetectionLite {
  class_name: string
  confidence: number
  color?: string
}

function ObjectCard({ obj, idx }: { obj: DetectionLite; idx: number }) {
  const entry = getObjectEntry(obj.class_name)
  const inWL = isWhitelisted(obj.class_name)
  return (
    <div
      className={cn(
        "rounded-xl border bg-card/80 p-4 flex flex-col gap-3",
        "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3",
        "hover:bg-surface-hover transition-all duration-200",
        inWL ? "border-amber-400/20 shadow-[0_0_12px_rgba(251,191,36,0.06)]" : "border-border/30 opacity-60",
      )}
      style={{ animationDelay: `${idx * 60}ms` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <span className="text-2xl select-none leading-none">{entry?.emoji ?? "📦"}</span>
          <div className="flex flex-col gap-0.5">
            <span className="text-sm font-semibold text-foreground leading-tight">
              {obj.color && obj.color !== "Unknown" ? `${obj.color} ` : ""}
              {getLabel(obj.class_name)}
            </span>
            <span className="text-[10px] text-muted-foreground font-mono">{obj.class_name}</span>
          </div>
        </div>
        {inWL ? (
          <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded-full bg-amber-400/10 text-amber-400 border border-amber-400/20 font-medium">
            白名單
          </span>
        ) : (
          <span className="shrink-0 text-[9px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground border border-border/20">
            靜默
          </span>
        )}
      </div>
      <ConfidenceBar value={obj.confidence} />
      {entry && (
        <div className="flex flex-col gap-1">
          <p className="text-[10px] text-muted-foreground leading-relaxed line-clamp-2">{entry.situation}</p>
          <p className="text-[10px] text-emerald-400/80 italic flex items-start gap-1">
            <span className="shrink-0">🔊</span>
            <span>「{entry.tts}」</span>
          </p>
        </div>
      )}
    </div>
  )
}

export function LiveDetectionSection({
  objects,
  isActive,
}: {
  objects: DetectionLite[]
  isActive: boolean
}) {
  if (!isActive || objects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
        <span className="text-5xl opacity-30 select-none">📦</span>
        <p className="text-sm">等待偵測中...</p>
        <p className="text-xs opacity-60">Jetson 連線後 YOLO 推送即會顯示</p>
      </div>
    )
  }
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
      {objects.map((obj, i) => (
        <ObjectCard key={`${obj.class_name}-${i}`} obj={obj} idx={i} />
      ))}
    </div>
  )
}
