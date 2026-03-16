'use client'

import { Activity } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import type { PoseState } from '@/contracts/types'

const POSE_LABELS: Record<string, string> = {
  standing: '站立',
  sitting: '坐著',
  crouching: '蹲下',
  fallen: '跌倒',
}

const POSE_EMOJI: Record<string, string> = {
  standing: '🧍',
  sitting: '🪑',
  crouching: '🏋️',
  fallen: '⚠️',
}

export function PosePanel() {
  const poseState = useStateStore((s) => s.poseState) as PoseState | null

  const status = !poseState
    ? 'inactive' as const
    : poseState.current_pose === 'fallen'
      ? 'error' as const
      : poseState.active
        ? 'active' as const
        : 'inactive' as const

  const pose = poseState?.current_pose
  const poseLabel = pose ? (POSE_LABELS[pose] ?? pose) : null

  return (
    <PanelCard
      title="姿勢辨識"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      <div className="flex flex-col gap-3">
        {poseLabel ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-2xl">{POSE_EMOJI[pose!] ?? '🧍'}</span>
              <div className="flex flex-col items-end gap-0.5">
                <span className="text-sm font-medium text-foreground">{poseLabel}</span>
                {poseState?.track_id != null && (
                  <span className="text-xs text-muted-foreground">Track #{poseState.track_id}</span>
                )}
              </div>
            </div>
            <MetricChip label="信心度" value={Math.round((poseState?.confidence ?? 0) * 100)} unit="%" />
          </>
        ) : (
          <div className="py-4 text-center text-muted-foreground text-sm">
            等待姿勢偵測...
          </div>
        )}
      </div>
    </PanelCard>
  )
}
