'use client'

import { User } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import type { FaceState } from '@/contracts/types'

export function FacePanel() {
  const faceState = useStateStore((s) => s.faceState) as FaceState | null

  const status = !faceState
    ? 'inactive' as const
    : faceState.face_count > 0
      ? 'active' as const
      : 'inactive' as const

  const tracks = faceState?.tracks ?? []

  return (
    <PanelCard
      title="人臉辨識"
      icon={<User className="h-4 w-4" />}
      status={status}
      count={faceState?.face_count}
    >
      {tracks.length === 0 ? (
        <div className="py-4 text-center text-muted-foreground text-sm">
          等待人臉偵測...
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {tracks.map((t) => (
            <div key={t.track_id} className="flex items-center justify-between rounded-lg bg-muted/30 px-3 py-2">
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-medium text-foreground">
                  {t.stable_name === 'unknown' ? '未知人物' : t.stable_name}
                </span>
                <span className="text-xs text-muted-foreground">
                  Track #{t.track_id} · {t.mode === 'stable' ? '已穩定' : '辨識中'}
                </span>
              </div>
              <div className="flex gap-1.5">
                <MetricChip label="相似度" value={Math.round(t.sim * 100)} unit="%" />
                {t.distance_m != null && (
                  <MetricChip label="距離" value={Number(t.distance_m.toFixed(1))} unit="m" />
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </PanelCard>
  )
}
