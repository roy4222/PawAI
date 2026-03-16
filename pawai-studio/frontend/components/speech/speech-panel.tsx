'use client'

import { Mic } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import type { SpeechState } from '@/contracts/types'

const PHASE_LABELS: Record<string, string> = {
  idle_wakeword: '等待喚醒',
  wake_ack: '已喚醒',
  loading_local_stack: '載入中...',
  listening: '聆聽中',
  transcribing: '辨識中',
  local_asr_done: 'ASR 完成',
  cloud_brain_pending: '等待大腦',
  speaking: '說話中',
  keep_alive: '待命',
  unloading: '卸載中',
}

export function SpeechPanel() {
  const speechState = useStateStore((s) => s.speechState) as SpeechState | null

  const status = !speechState
    ? 'inactive' as const
    : speechState.phase !== 'idle_wakeword'
      ? 'active' as const
      : 'inactive' as const

  const phase = speechState?.phase ?? 'idle_wakeword'
  const phaseLabel = PHASE_LABELS[phase] ?? phase

  return (
    <PanelCard
      title="語音互動"
      icon={<Mic className="h-4 w-4" />}
      status={status}
    >
      <div className="flex flex-col gap-3">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">狀態</span>
          <span className="text-sm font-medium text-foreground">{phaseLabel}</span>
        </div>

        {speechState?.last_asr_text && (
          <div className="rounded-lg bg-muted/30 px-3 py-2">
            <span className="text-xs text-muted-foreground block mb-1">最近辨識</span>
            <span className="text-sm text-foreground">{speechState.last_asr_text}</span>
          </div>
        )}

        {speechState?.last_intent && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">意圖</span>
            <MetricChip label="intent" value={0} unit={speechState.last_intent} />
          </div>
        )}

        {speechState?.models_loaded && speechState.models_loaded.length > 0 && (
          <div className="flex gap-1.5 flex-wrap">
            {speechState.models_loaded.map((m) => (
              <span key={m} className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                {m}
              </span>
            ))}
          </div>
        )}

        {!speechState && (
          <div className="py-2 text-center text-muted-foreground text-sm">
            等待語音模組連線...
          </div>
        )}
      </div>
    </PanelCard>
  )
}
