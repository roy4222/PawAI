'use client'

import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState, GestureEvent } from '@/contracts/types'
import { cn } from '@/lib/utils'

// ──────────────────────────────────────────────
// 常數
// ──────────────────────────────────────────────

const GESTURE_LABELS: Record<string, string> = {
  wave: '揮手',
  stop: '停止',
  point: '指向',
  fist: '握拳',
  ok: 'OK',
}

const GESTURE_EMOJI: Record<string, string> = {
  wave: '👋',
  stop: '✋',
  point: '👆',
  fist: '✊',
  ok: '👌',
}

const MAX_HISTORY = 10

// ──────────────────────────────────────────────
// 子元件：事件歷史列
// ──────────────────────────────────────────────

function EventHistoryItem({ event }: { event: GestureEvent }) {
  const d = event.data
  const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })
  const label = GESTURE_LABELS[d.gesture] ?? d.gesture
  const emoji = GESTURE_EMOJI[d.gesture] ?? '🤚'

  return (
    <div className={cn(
      'flex items-center gap-2 rounded-md px-2.5 py-1.5',
      'bg-surface/40 border border-border/20',
      'text-xs text-muted-foreground',
    )}>
      <span>{emoji}</span>
      <span className="text-foreground font-medium">{label}</span>
      <span className="ml-auto tabular-nums">{time}</span>
      <span className="shrink-0 text-[10px]">
        {d.hand === 'left' ? '左手' : '右手'} · {Math.round(d.confidence * 100)}%
      </span>
    </div>
  )
}

// ──────────────────────────────────────────────
// 主元件
// ──────────────────────────────────────────────

export function GesturePanel() {
  const gestureState = useStateStore((s) => s.gestureState) as GestureState | null
  const allEvents = useEventStore((s) => s.events)

  // 最近 10 筆 gesture 事件
  const gestureEvents = allEvents
    .filter((e): e is GestureEvent => e.source === 'gesture')
    .slice(0, MAX_HISTORY)

  // ── 狀態機 ─────────────────────────────────
  // null            → loading（尚未收到第一筆 state）
  // status=loading  → loading
  // active=false    → inactive
  // active=true     → active
  const panelStatus: 'active' | 'inactive' | 'loading' | 'error' =
    gestureState === null ? 'loading'
      : gestureState.status === 'loading' ? 'loading'
        : gestureState.active ? 'active'
          : 'inactive'

  const gesture = gestureState?.current_gesture ?? null
  const gestureLabel = gesture ? (GESTURE_LABELS[gesture] ?? gesture) : null
  const gestureEmoji = gesture ? (GESTURE_EMOJI[gesture] ?? '🤚') : null

  return (
    <PanelCard
      title="手勢辨識"
      href="/studio/gesture"
      icon={<Hand className="h-4 w-4" />}
      status={panelStatus}
    >
      <div className="flex flex-col gap-3">

        {/* ── Loading ── */}
        {panelStatus === 'loading' && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <span className="animate-spin text-2xl">🌀</span>
            <span>正在連線...</span>
          </div>
        )}

        {/* ── Inactive ── */}
        {panelStatus === 'inactive' && (
          <div className="py-6 flex flex-col items-center gap-2 text-muted-foreground text-sm">
            <Hand className="h-8 w-8 opacity-30" />
            <span>尚未偵測到手勢</span>
          </div>
        )}

        {/* ── Active：手勢卡片 ── */}
        {panelStatus === 'active' && (
          <>
            {/* 手勢卡片 */}
            {gestureLabel ? (
              <div
                key={gesture}   // key 變化時觸發 crossfade
                className={cn(
                  'rounded-lg border border-border/30 bg-surface/50 px-4 py-3',
                  'flex items-center justify-between gap-3',
                  'motion-safe:animate-[bounce_0.2s_ease-out]',
                  'hover:bg-surface-hover motion-safe:transition-colors motion-safe:duration-150',
                )}
              >
                {/* 左：emoji */}
                <span className="text-3xl select-none">{gestureEmoji}</span>

                {/* 中：名稱 + 左右手 */}
                <div className="flex-1 flex flex-col gap-0.5">
                  <span className="text-sm font-semibold text-foreground">{gestureLabel}</span>
                  <span
                    className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full w-fit font-medium',
                      gestureState?.hand === 'left'
                        ? 'bg-blue-500/10 text-blue-400'
                        : 'bg-emerald-500/10 text-emerald-400',
                    )}
                  >
                    {gestureState?.hand === 'left' ? '← 左手' : '右手 →'}
                  </span>
                </div>

                {/* 右：信心度 */}
                <MetricChip
                  label="信心度"
                  value={Math.round((gestureState?.confidence ?? 0) * 100)}
                  unit="%"
                />
              </div>
            ) : (
              <div className="py-4 text-center text-muted-foreground text-sm">
                等待手勢偵測...
              </div>
            )}

            {/* 事件歷史 */}
            {gestureEvents.length > 0 && (
              <div className="flex flex-col gap-1.5">
                <span className="text-[11px] text-muted-foreground font-medium px-0.5">
                  最近偵測記錄
                </span>
                {gestureEvents.map((evt, i) => (
                  <EventHistoryItem key={`${evt.id}-${i}`} event={evt} />
                ))}
              </div>
            )}
          </>
        )}

      </div>
    </PanelCard>
  )
}
