'use client'

import { User, UserCheck } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { MetricChip } from '@/components/shared/metric-chip'
import { cn } from '@/lib/utils'
import type { FaceTrack } from '@/contracts/types'

interface FaceTrackCardProps {
  track: FaceTrack
  isVanishing?: boolean
}

export function FaceTrackCard({ track, isVanishing = false }: FaceTrackCardProps) {
  // 防禦性檢查：確保所有必要欄位都存在
  const isKnown = track?.stable_name && track.stable_name !== 'unknown'
  const simPercent = track?.sim != null ? Math.round(track.sim * 100) : 0
  const trackId = track?.track_id ?? 'N/A'
  const mode = track?.mode ?? 'unknown'

  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2.5",
        "bg-surface/50 border border-border/30",
        "motion-safe:transition-colors motion-safe:duration-150",
        "hover:bg-surface-hover",
        "motion-safe:animate-in motion-safe:slide-in-from-right-4 motion-safe:duration-200 motion-safe:delay-0",
        isVanishing && "opacity-50 transition-opacity duration-500"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex items-center justify-center w-9 h-9 rounded-full shrink-0",
          isKnown ? "bg-success/10" : "bg-muted"
        )}
      >
        {isKnown ? (
          <UserCheck className="h-4 w-4 text-success" />
        ) : (
          <User className="h-4 w-4 text-muted-foreground" />
        )}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground truncate">
            {isKnown ? track.stable_name : '未知人物'}
          </span>
          <Badge
            className={cn(
              "text-[10px] px-1.5 py-0 h-4 rounded-full font-normal border-transparent",
              "transition-colors duration-150",
              mode === 'stable'
                ? "bg-success/10 text-success"
                : mode === 'hold'
                  ? "bg-warning/10 text-warning"
                  : "bg-muted/10 text-muted-foreground"
            )}
          >
            {mode === 'stable' ? '已穩定' : mode === 'hold' ? '辨識中' : '未知狀態'}
          </Badge>
        </div>
        <span className="text-xs text-muted-foreground">
          Track #{trackId}
        </span>
      </div>

      {/* Metrics */}
      <div className="flex flex-col gap-1 items-end shrink-0">
        <MetricChip 
          label="相似度" 
          value={simPercent} 
          unit="%" 
          className="transition-all duration-300"
        />
        {track?.distance_m != null && (
          <MetricChip 
            label="距離" 
            value={Number(track.distance_m.toFixed(1))} 
            unit="m" 
            className="transition-all duration-300"
          />
        )}
      </div>
    </div>
  )
}
