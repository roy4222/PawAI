'use client'

import { Activity } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import type { PoseState } from '@/contracts/types'

export function PosePanel() {
  const poseState = useStateStore((s) => s.poseState) as PoseState | null

  const status = !poseState
    ? 'loading' as const
    : poseState.current_pose === 'fallen'
      ? 'error' as const
      : poseState.active
        ? 'active' as const
        : 'inactive' as const

  return (
    <PanelCard
      title="姿勢辨識"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 楊 — 看 docs/pose-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 pose-panel-spec.md
      </div>
    </PanelCard>
  )
}
