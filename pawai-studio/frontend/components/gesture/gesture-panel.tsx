'use client'

import { useState } from 'react'
import { Hand } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { Button } from '@/components/ui/button'
import { LiveFeedCard } from '@/components/live/live-feed-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { GestureState, GestureEvent } from '@/contracts/types'
import { cn } from '@/lib/utils'
import { LocalCameraCard } from './local-camera-card'

// ──────────────────────────────────────────────
// 9-gesture mapping (MOC §4 + sprint design §4 Skill Registry)
//
// 3 groups: System Control / Interaction & Emotion / Dynamic
// Active 5 / Hidden 2 / Future 2 — see docs/pawai-brain/perception/gesture/README.md
// ──────────────────────────────────────────────

const GESTURE_LABELS: Record<string, string> = {
  // System Control
  palm: '張開手掌',
  fist: '握拳',
  index: '食指',
  ok: 'OK',
  // Interaction & Emotion
  thumb: '讚',
  peace: '比 YA',
  // Dynamic
  wave: '揮手',
  comehere: '招手過來',
  circle: '畫圓',
  // Legacy aliases (state-store may still emit these names)
  stop: '停止 (Palm)',
  point: '指向 (Index)',
  thumbs_up: '讚 (Thumb)',
}

const GESTURE_EMOJI: Record<string, string> = {
  palm: '🖐️',
  fist: '👊',
  index: '☝️',
  ok: '👌',
  thumb: '👍',
  peace: '✌️',
  wave: '👋',
  comehere: '🫴',
  circle: '🔄',
  // Legacy
  stop: '🖐️',
  point: '☝️',
  thumbs_up: '👍',
}

/** Gesture → mode label per MOC. */
const GESTURE_MODE: Record<string, string> = {
  palm: 'Pause',
  fist: 'Mute',
  index: 'Listen',
  ok: 'Confirm',
  thumb: 'Happy',
  peace: 'Relax',
  wave: 'Greeting',
  comehere: 'Follow',
  circle: 'Dance',
}

/** Tone color for the mode chip. */
const MODE_TONE: Record<string, string> = {
  Pause: 'bg-red-500/15 text-red-300 border-red-500/30',
  Mute: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
  Listen: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
  Confirm: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  Happy: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  Relax: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  Greeting: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  Follow: 'bg-pink-500/15 text-pink-300 border-pink-500/30',
  Dance: 'bg-fuchsia-500/15 text-fuchsia-300 border-fuchsia-500/30',
}

const MAX_HISTORY = 10

/** Normalize gesture key to lowercase no-space (matches GESTURE_LABELS keys). */
function normalizeGestureKey(g: string | null | undefined): string {
  return (g ?? '').trim().toLowerCase().replace(/[-\s]+/g, '')
}

function gestureLabel(g: string | null | undefined): string {
  if (!g) return ''
  const key = normalizeGestureKey(g)
  return GESTURE_LABELS[key] ?? g
}

function gestureEmoji(g: string | null | undefined): string {
  if (!g) return '🤚'
  const key = normalizeGestureKey(g)
  return GESTURE_EMOJI[key] ?? '🤚'
}

function gestureMode(g: string | null | undefined): string | null {
  if (!g) return null
  const key = normalizeGestureKey(g)
  return GESTURE_MODE[key] ?? null
}

// ──────────────────────────────────────────────
// 子元件：事件歷史列
// ──────────────────────────────────────────────

function EventHistoryItem({ event }: { event: GestureEvent }) {
  const d = event.data
  const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })
  const label = gestureLabel(d.gesture)
  const emoji = gestureEmoji(d.gesture)
  const mode = gestureMode(d.gesture)

  return (
    <div className={cn(
      'flex items-center gap-2 rounded-md px-2.5 py-1.5',
      'bg-surface/40 border border-border/20',
      'text-xs text-muted-foreground',
    )}>
      <span>{emoji}</span>
      <span className="text-foreground font-medium">{label}</span>
      {mode && (
        <span className={cn(
          'shrink-0 rounded border px-1 py-px text-[9px] font-semibold uppercase tracking-wider',
          MODE_TONE[mode] ?? 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
        )}>
          {mode}
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
// 主元件
// ──────────────────────────────────────────────

export function GesturePanel() {
  const gestureState = useStateStore((s) => s.gestureState) as GestureState | null
  const allEvents = useEventStore((s) => s.events)

  // Source toggle — default Jetson live feed, fallback to browser webcam
  // (dev only, when no Jetson is connected and you just want to verify framing).
  const [useLocalCam, setUseLocalCam] = useState(false)

  // 最近 10 筆 gesture 事件
  const gestureEvents = allEvents
    .filter((e): e is GestureEvent => e.source === 'gesture')
    .slice(0, MAX_HISTORY)

  // ── 狀態機 ─────────────────────────────────
  const panelStatus: 'active' | 'inactive' | 'loading' | 'error' =
    gestureState === null ? 'loading'
      : gestureState.status === 'loading' ? 'loading'
        : gestureState.active ? 'active'
          : 'inactive'

  const gesture = gestureState?.current_gesture ?? null
  const label = gestureLabel(gesture)
  const emoji = gestureEmoji(gesture)
  const mode = gestureMode(gesture)

  return (
    <PanelCard
      title="手勢辨識"
      href="/studio/gesture"
      icon={<Hand className="h-4 w-4" />}
      status={panelStatus}
    >
      <div className="flex flex-col gap-3 p-3 pt-0">

        {/* ── Source toggle ── */}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border/20 bg-surface/30 p-2">
          <div className="text-[11px] text-muted-foreground">
            畫面來源：
            <span className={cn('ml-1 font-medium', useLocalCam ? 'text-amber-300' : 'text-emerald-300')}>
              {useLocalCam ? '本機相機（dev fallback）' : 'Jetson Live Feed'}
            </span>
          </div>
          <Button
            size="sm"
            variant={useLocalCam ? 'default' : 'secondary'}
            className="h-7 text-xs"
            onClick={() => setUseLocalCam((v) => !v)}
          >
            {useLocalCam ? '改用 Jetson Feed' : '本機相機（fallback）'}
          </Button>
        </div>

        {/* ── Live feed (left-equivalent in vertical stack) ── */}
        <div className="md:grid md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:gap-3 md:items-start">
          <div>
            {useLocalCam ? (
              <LocalCameraCard title="Local Camera" mirror />
            ) : (
              <LiveFeedCard
                source="vision"
                title="Vision Live (Pose + Gesture)"
                topicName="/vision_perception/debug_image"
              />
            )}
          </div>
          <div className="mt-3 md:mt-0 flex flex-col gap-3">{/* right column populated by sections below */}

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
            {label ? (
              <div
                key={gesture}
                className={cn(
                  'rounded-lg border border-border/30 bg-surface/50 px-4 py-3',
                  'flex items-center justify-between gap-3',
                  'motion-safe:animate-[bounce_0.2s_ease-out]',
                  'hover:bg-surface-hover motion-safe:transition-colors motion-safe:duration-150',
                )}
              >
                <span className="text-3xl select-none">{emoji}</span>

                <div className="flex-1 flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">{label}</span>
                    {mode && (
                      <span className={cn(
                        'rounded border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider',
                        MODE_TONE[mode] ?? 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30',
                      )}>
                        {mode}
                      </span>
                    )}
                  </div>
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
        </div>

      </div>
    </PanelCard>
  )
}
