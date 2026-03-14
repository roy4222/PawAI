'use client'

import { User } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { FaceState } from '@/contracts/types'

export function FacePanel() {
  const faceState = useStateStore((s) => s.faceState) as FaceState | null
  const events = useEventStore((s) => s.events.filter((e) => e.source === 'face'))

  const status = !faceState
    ? 'loading' as const
    : faceState.face_count > 0
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="人臉辨識"
      icon={<User className="h-4 w-4" />}
      status={status}
      count={faceState?.face_count}
    >
      {/* TODO: 鄔 — 看 docs/face-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 face-panel-spec.md
      </div>
    </PanelCard>
  )
}
