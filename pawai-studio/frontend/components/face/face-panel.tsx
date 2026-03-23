'use client'

import { User, UserX } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { EventItem } from '@/components/shared/event-item'
import { useMemo, useState, useEffect, useRef } from 'react'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import { FaceTrackCard } from './face-track-card'
import type { FaceState, FaceTrack } from '@/contracts/types'

const EVENT_TYPE_LABELS: Record<string, string> = {
  track_started: '新追蹤',
  identity_stable: '身份確認',
  identity_changed: '身份變更',
  track_lost: '追蹤消失',
}

const PLACEHOLDER_SRC = "/mock/face-placeholder.svg"
const SHOW_PLACEHOLDER = false  // M2 時改 false，換成真實元件

export function FacePanel() {
  const faceState = useStateStore((s) => s.faceState) as FaceState | null
  const allEvents = useEventStore((s) => s.events)
  const faceEvents = useMemo(
    () => allEvents.filter((e) => e.source === 'face').slice(-10),
    [allEvents]
  )

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
      icon={<User className="h-4 w-4" />}
      status={status}
      count={faceState?.face_count}
    >
      <div className="flex flex-col gap-3">
        {/* Placeholder visual — M2 時改 SHOW_PLACEHOLDER = false，換成真實元件 */}
        {SHOW_PLACEHOLDER && (
          <div className="rounded-lg overflow-hidden border border-border/20">
            <img src={PLACEHOLDER_SRC} alt="face placeholder" className="w-full h-auto" />
          </div>
        )}

        {/* Track list */}
        {status === 'loading' ? (
          <div className="flex flex-col items-center justify-center py-6 gap-2 text-muted-foreground">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-warning border-t-transparent" />
            <span className="text-sm">正在連線...</span>
          </div>
        ) : allTracks.length > 0 ? (
          <div className="flex flex-col gap-2">
            {allTracks.map((t) => (
              <FaceTrackCard
                key={t.track_id}
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
