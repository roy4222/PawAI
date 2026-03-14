'use client'

import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import type { GestureState } from '@/contracts/types'

export function GesturePanel() {
  const gestureState = useStateStore((s) => s.gestureState) as GestureState | null

  const status = !gestureState
    ? 'loading' as const
    : gestureState.active
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="手勢辨識"
      icon={<Hand className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 黃 — 看 docs/gesture-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 gesture-panel-spec.md
      </div>
    </PanelCard>
  )
}
