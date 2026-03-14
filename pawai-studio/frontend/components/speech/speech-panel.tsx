'use client'

import { Mic } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { useStateStore } from '@/stores/state-store'
import type { SpeechState } from '@/contracts/types'

export function SpeechPanel() {
  const speechState = useStateStore((s) => s.speechState) as SpeechState | null

  const status = !speechState
    ? 'loading' as const
    : speechState.phase !== 'idle_wakeword'
      ? 'active' as const
      : 'inactive' as const

  return (
    <PanelCard
      title="語音互動"
      icon={<Mic className="h-4 w-4" />}
      status={status}
    >
      {/* TODO: 陳 — 看 docs/speech-panel-spec.md 實作 */}
      <div className="h-32 flex items-center justify-center text-muted-foreground text-sm">
        待實作 — 參考 speech-panel-spec.md
      </div>
    </PanelCard>
  )
}
