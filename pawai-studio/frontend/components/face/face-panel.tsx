'use client'

import { User, UserX } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { EventItem } from '@/components/shared/event-item'
import { Button } from '@/components/ui/button'
import { LiveFeedCard } from '@/components/live/live-feed-card'
import { LocalCameraCard } from '@/components/gesture/local-camera-card'
import { useMemo, useState, useEffect, useRef } from 'react'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import { FaceTrackCard } from './face-track-card'
import { cn } from '@/lib/utils'
import type { FaceState, FaceTrack } from '@/contracts/types'

const EVENT_TYPE_LABELS: Record<string, string> = {
  track_started: '新追蹤',
  identity_stable: '身份確認',
  identity_changed: '身份變更',
  track_lost: '追蹤消失',
}

export function FacePanel() {
  const faceState = useStateStore((s) => s.faceState) as FaceState | null
  const allEvents = useEventStore((s) => s.events)
  const faceEvents = useMemo(
    () => allEvents.filter((e) => e.source === 'face').slice(-10),
    [allEvents]
  )

  // Source toggle — default Jetson live feed, fallback to browser webcam
  // (dev only, when no Jetson is connected and you just want to verify framing).
  const [useLocalCam, setUseLocalCam] = useState(false)

  const [vanishingTracks, setVanishingTracks] = useState<FaceTrack[]>([])
  const prevTracksRef = useRef<FaceTrack[]>([])

  useEffect(() => {
    const currentTracks = faceState?.tracks ?? []
    const prevTracks = prevTracksRef.current
    // 找出消失的 track（存在於 prevTracks 但不在 currentTracks 中）
    const disappeared = prevTracks.filter(pt =>
      !currentTracks.some(ct => ct.track_id === pt.track_id)
    )
    if (disappeared.length > 0) {
      setVanishingTracks(prev => [...prev, ...disappeared])
      // 5 秒後移除
      const timer = setTimeout(() => {
        setVanishingTracks(prev => prev.filter(t => !disappeared.some(d => d.track_id === t.track_id)))
      }, 5000)
      return () => clearTimeout(timer)
    }
    prevTracksRef.current = currentTracks
  }, [faceState?.tracks])

  const status = !faceState
    ? 'loading' as const
    : faceState.face_count > 0
      ? 'active' as const
      : 'inactive' as const

  const tracks = faceState?.tracks ?? []
  const allTracks = useMemo(() => {
    const currentIds = new Set(tracks.map(t => t.track_id))
    const vanishingWithoutCurrent = vanishingTracks.filter(vt => !currentIds.has(vt.track_id))
    return [...tracks, ...vanishingWithoutCurrent]
  }, [tracks, vanishingTracks])

  return (
    <PanelCard
      title="人臉辨識"
      href="/studio/face"
      icon={<User className="h-4 w-4" />}
      status={status}
      count={faceState?.face_count}
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

        {/* ── 2-col layout: live feed + track list ── */}
        <div className="md:grid md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:gap-3 md:items-start">
          <div>
            {useLocalCam ? (
              <LocalCameraCard title="Local Camera" mirror />
            ) : (
              <LiveFeedCard
                source="face"
                title="Face Live"
                topicName="/face_identity/debug_image"
              />
            )}
          </div>

          <div className="mt-3 md:mt-0 flex flex-col gap-3">
            {status === 'loading' ? (
              <div className="flex flex-col items-center justify-center py-6 gap-2 text-muted-foreground">
                <div className="animate-spin rounded-full h-8 w-8 border-2 border-warning border-t-transparent" />
                <span className="text-sm">正在連線...</span>
              </div>
            ) : allTracks.length > 0 ? (
              <div className="flex flex-col gap-2">
                {allTracks.map((t, i) => (
                  <FaceTrackCard
                    key={`${t.track_id}-${i}`}
                    track={t}
                    isVanishing={vanishingTracks.some(vt => vt.track_id === t.track_id)}
                  />
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-6 gap-2 text-muted-foreground">
                <UserX className="h-8 w-8 opacity-40" />
                <span className="text-sm">尚未偵測到人臉</span>
              </div>
            )}
          </div>
        </div>

        {/* Event history - Optional for M2 */}
        {false && faceEvents.length > 0 && (
          <div className="flex flex-col gap-1 border-t border-border/30 pt-2 mt-1">
            <span className="text-xs text-muted-foreground mb-1">最近事件</span>
            {faceEvents.map((e) => {
              const data = e.data as Record<string, unknown>
              const name = String(data.stable_name ?? '')
              const sim = Number(data.sim ?? 0)
              const summary = name
                ? `${name}（${Math.round(sim * 100)}%）`
                : ''
              return (
                <EventItem
                  key={e.id}
                  timestamp={new Date(e.timestamp).toLocaleTimeString('zh-TW', { hour12: false })}
                  eventType={EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
                  source={e.source}
                  summary={summary}
                />
              )
            })}
          </div>
        )}
      </div>
    </PanelCard>
  )
}
