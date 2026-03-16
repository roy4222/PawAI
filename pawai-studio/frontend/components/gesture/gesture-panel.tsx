'use client'

import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import type { GestureState } from '@/contracts/types'

const GESTURE_LABELS: Record<string, string> = {
  wave: '揮手',
  stop: '停止',
  point: '指向',
  ok: 'OK',
}

export function GesturePanel() {
  const gestureState = useStateStore((s) => s.gestureState) as GestureState | null

  const status = !gestureState
    ? 'inactive' as const
    : gestureState.active
      ? 'active' as const
      : 'inactive' as const

  const gesture = gestureState?.current_gesture
  const gestureLabel = gesture ? (GESTURE_LABELS[gesture] ?? gesture) : null

  return (
    <PanelCard
      title="手勢辨識"
      icon={<Hand className="h-4 w-4" />}
      status={status}
    >
      <div className="flex flex-col gap-3">
        {gestureLabel ? (
          <>
            <div className="flex items-center justify-between">
              <span className="text-2xl">{gesture === 'wave' ? '👋' : gesture === 'ok' ? '👌' : gesture === 'stop' ? '✋' : '👆'}</span>
              <div className="flex flex-col items-end gap-0.5">
                <span className="text-sm font-medium text-foreground">{gestureLabel}</span>
                <span className="text-xs text-muted-foreground">{gestureState?.hand === 'left' ? '左手' : '右手'}</span>
              </div>
            </div>
            <MetricChip label="信心度" value={Math.round((gestureState?.confidence ?? 0) * 100)} unit="%" />
          </>
        ) : (
          <div className="py-4 text-center text-muted-foreground text-sm">
            等待手勢偵測...
          </div>
        )}
      </div>
    </PanelCard>
  )
}
