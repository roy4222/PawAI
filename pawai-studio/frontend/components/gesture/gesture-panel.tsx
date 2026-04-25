'use client'

import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState, GestureEvent } from '@/contracts/types'
import { cn } from '@/lib/utils'

// ──────────────────────────────────────────────
// 常數：對應你的 gesture_recognition.py 的 mode/gesture
// ──────────────────────────────────────────────

/** 手勢辨識結果字串 → 中文名稱 */
const GESTURE_LABELS: Record<string, string> = {
  // 靜態手勢
  Palm:    '暫停互動',
  Fist:    '靜音',
  Thumb:   '正面回饋',
  Index:   '聆聽模式',
  OK:      '確認指令',
  Peace:   '放鬆模式',
  // 動態手勢
  Wave:    '打招呼',
  // 後端沿用舊 key 時的 fallback
  wave:    '打招呼',
  stop:    '暫停互動',
  fist:    '靜音',
  ok:      '確認指令',
}

/** 手勢辨識結果字串 → emoji */
const GESTURE_EMOJI: Record<string, string> = {
  Palm:    '🖐️',
  Fist:    '👊',
  Thumb:   '👍',
  Index:   '☝️',
  OK:      '👌',
  Peace:   '✌️',
  Wave:    '👋',
  wave:    '👋',
  stop:    '🖐️',
  fist:    '👊',
  ok:      '👌',
}

/** 手勢 → 對應的陪伴模式說明 */
const GESTURE_MODE: Record<string, string> = {
  Palm:    'Pause',
  Fist:    'Mute',
  Thumb:   'Happy',
  Index:   'Listen',
  OK:      'Confirm',
  Peace:   'Relax',
  Wave:    'Greeting',
  wave:    'Greeting',
  stop:    'Pause',
  fist:    'Mute',
  ok:      'Confirm',
}

/** 手勢 → Go2 動作 api_id + 動作名稱 */
const GO2_ACTION: Record<string, { api_id: number; name: string }> = {
  Palm:    { api_id: 1003, name: 'StopMove' },
  Fist:    { api_id: 1009, name: 'Sit' },
  Thumb:   { api_id: 1033, name: 'WiggleHips' },
  Index:   { api_id: 1004, name: 'StandUp' },
  OK:      { api_id: 1020, name: 'Content' },
  Peace:   { api_id: 1017, name: 'Stretch' },
  Wave:    { api_id: 1016, name: 'Hello' },
  wave:    { api_id: 1016, name: 'Hello' },
  stop:    { api_id: 1003, name: 'StopMove' },
  fist:    { api_id: 1009, name: 'Sit' },
  ok:      { api_id: 1020, name: 'Content' },
}

/** 模式 → accent 色（Tailwind 任意值） */
const MODE_COLOR: Record<string, { bg: string; text: string; dot: string }> = {
  Pause:    { bg: 'bg-red-500/10',    text: 'text-red-400',    dot: 'bg-red-400' },
  Mute:     { bg: 'bg-zinc-500/10',   text: 'text-zinc-400',   dot: 'bg-zinc-400' },
  Happy:    { bg: 'bg-emerald-500/10',text: 'text-emerald-400',dot: 'bg-emerald-400' },
  Listen:   { bg: 'bg-blue-500/10',   text: 'text-blue-400',   dot: 'bg-blue-400' },
  Confirm:  { bg: 'bg-amber-500/10',  text: 'text-amber-400',  dot: 'bg-amber-400' },
  Relax:    { bg: 'bg-violet-500/10', text: 'text-violet-400', dot: 'bg-violet-400' },
  Greeting: { bg: 'bg-pink-500/10',   text: 'text-pink-400',   dot: 'bg-pink-400' },
  Idle:     { bg: 'bg-muted/40',      text: 'text-muted-foreground', dot: 'bg-muted-foreground' },
}

const MAX_HISTORY = 10

// ──────────────────────────────────────────────
// 子元件：事件歷史列
// ──────────────────────────────────────────────

function EventHistoryItem({ event }: { event: GestureEvent }) {
  const d = event.data as any
  const gestureKey = d.gesture ?? d.current_gesture ?? 'unknown'
  const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })
  const label = GESTURE_LABELS[gestureKey] ?? gestureKey
  const emoji = GESTURE_EMOJI[gestureKey] ?? '🤚'
  const action = GO2_ACTION[gestureKey]

  return (
    <div className={cn(
      'flex items-center gap-2 rounded-md px-2.5 py-1.5',
      'bg-surface/40 border border-border/20',
      'text-xs text-muted-foreground',
    )}>
      <span className="shrink-0">{emoji}</span>
      <span className="text-foreground font-medium">{label}</span>
      {action && (
        <span className="text-[10px] text-muted-foreground/60">
          → {action.name}
        </span>
      )}
      <span className="ml-auto tabular-nums">{time}</span>
      <span className="shrink-0 text-[10px]">
        {d.hand === 'left' ? '左手' : '右手'} · {Math.round(d.confidence * 100)}%
      </span>
    </div>
  )
}

// ──────────────────────────────────────────────
// 子元件：Go2 動作徽章
// ──────────────────────────────────────────────

function Go2ActionBadge({ gesture }: { gesture: string }) {
  const action = GO2_ACTION[gesture]
  if (!action) return null
  return (
    <div className={cn(
      'flex items-center gap-1.5 rounded-md px-2.5 py-1.5 mt-1',
      'bg-surface border border-border/30',
      'text-xs',
    )}>
      <span className="text-muted-foreground">🤖 Go2 執行</span>
      <span className="font-mono font-semibold text-foreground">{action.name}</span>
      <span className="ml-auto text-muted-foreground/60 font-mono">#{action.api_id}</span>
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

  // 狀態機
  const panelStatus: 'active' | 'inactive' | 'loading' | 'error' =
    gestureState === null ? 'loading'
      : gestureState.status === 'loading' ? 'loading'
        : gestureState.active ? 'active'
          : 'inactive'

  const gesture = gestureState?.current_gesture ?? null
  const gestureLabel = gesture ? (GESTURE_LABELS[gesture] ?? gesture) : null
  const gestureEmoji = gesture ? (GESTURE_EMOJI[gesture] ?? '🤚') : null
  const mode = gesture ? (GESTURE_MODE[gesture] ?? 'Idle') : 'Idle'
  const modeColor = MODE_COLOR[mode] ?? MODE_COLOR.Idle

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
            <span className="text-xs opacity-60">比出手勢以開始互動</span>
          </div>
        )}

        {/* ── Active：手勢卡片 ── */}
        {panelStatus === 'active' && (
          <>
            {/* 主手勢卡片 */}
            {gestureLabel ? (
              <div
                key={gesture}
                className={cn(
                  'rounded-lg border border-border/30 bg-surface/50 px-4 py-3',
                  'flex items-center justify-between gap-3',
                  'motion-safe:animate-[bounce_0.2s_ease-out]',
                  'hover:bg-surface-hover transition-colors duration-150',
                )}
              >
                {/* 左：emoji */}
                <span className="text-3xl select-none">{gestureEmoji}</span>

                {/* 中：名稱 + 模式 badge */}
                <div className="flex-1 flex flex-col gap-1">
                  <span className="text-sm font-semibold text-foreground">{gestureLabel}</span>
                  <div className="flex items-center gap-1.5">
                    {/* 模式 badge */}
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full font-medium flex items-center gap-1',
                      modeColor.bg,
                      modeColor.text,
                    )}>
                      <span className={cn('h-1.5 w-1.5 rounded-full', modeColor.dot)} />
                      {mode}
                    </span>
                    {/* 左右手 badge */}
                    <span className={cn(
                      'text-[10px] px-1.5 py-0.5 rounded-full font-medium',
                      gestureState?.hand === 'left'
                        ? 'bg-blue-500/10 text-blue-400'
                        : 'bg-emerald-500/10 text-emerald-400',
                    )}>
                      {gestureState?.hand === 'left' ? '← 左手' : '右手 →'}
                    </span>
                  </div>
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

            {/* Go2 動作對應 */}
            {gesture && <Go2ActionBadge gesture={gesture} />}

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
