'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { Activity, History, X } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import { cn } from '@/lib/utils'
import type { PoseEvent, PoseState } from '@/contracts/types'

const POSE_LABELS: Record<string, string> = {
  standing: '站立',
  sitting: '坐著',
  crouching: '蹲下',
  bending: '彎腰',
  'hands on hips': '雙手叉腰',
  kneeling: '單膝跪地',
  'kneeling on one knee': '單膝跪地',
  fallen: '跌倒',
}

const POSE_EMOJI: Record<string, string> = {
  standing: '🧍',
  sitting: '🪑',
  crouching: '🏋️',
  bending: '🙇',
  'hands on hips': '🦸',
  kneeling: '🧎',
  'kneeling on one knee': '🧎',
  fallen: '⚠️',
}

const PLACEHOLDER_SRC = '/mock/pose-placeholder.svg'
const MAX_HISTORY = 10

function normalizePoseKey(pose: string | null | undefined): string {
  return (pose ?? '')
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
}

function getPoseLabel(pose: string | null | undefined): string {
  const key = normalizePoseKey(pose)
  if (!key) return '尚未偵測'
  const mapped = POSE_LABELS[key]
  if (mapped) return mapped

  const raw = (pose ?? '').trim()
  return raw ? `未知姿勢（${raw}）` : '尚未偵測'
}

function getEventPoseValue(event: PoseEvent): string | null {
  const data = event.data as unknown as Record<string, unknown>
  const raw = data.pose ?? data.current_pose ?? data.label ?? data.class_name
  return typeof raw === 'string' ? raw : null
}

function getPoseStyle(pose: string | null | undefined): string {
  const key = normalizePoseKey(pose)
  if (key === 'fallen') return 'text-red-400'
  if (key === 'crouching' || key === 'bending' || key === 'kneeling' || key === 'kneeling on one knee') {
    return 'text-amber-300'
  }
  return 'text-emerald-300'
}

export function PosePanel() {
  const [cameraEnabled, setCameraEnabled] = useState(true)
  const [historyModalOpen, setHistoryModalOpen] = useState(false)
  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [allPoseHistory, setAllPoseHistory] = useState<PoseEvent[]>([])

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const localStreamRef = useRef<MediaStream | null>(null)

  const poseState = useStateStore((s) => s.poseState) as PoseState | null
  const allEvents = useEventStore((s) => s.events)

  useEffect(() => {
    const stopLocalCamera = () => {
      localStreamRef.current?.getTracks().forEach((track) => track.stop())
      localStreamRef.current = null
      if (videoRef.current) {
        videoRef.current.srcObject = null
      }
      setCameraReady(false)
    }

    if (!cameraEnabled) {
      setCameraError(null)
      stopLocalCamera()
      return
    }

    let cancelled = false

    const startLocalCamera = async () => {
      try {
        setCameraError(null)

        if (typeof navigator === 'undefined' || !navigator.mediaDevices || typeof navigator.mediaDevices.getUserMedia !== 'function') {
          setCameraError('目前環境不支援相機存取（請使用瀏覽器並確認為 localhost 或 https）')
          return
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: 'user',
          },
          audio: false,
        })

        if (cancelled) {
          stream.getTracks().forEach((track) => track.stop())
          return
        }

        localStreamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          const p = videoRef.current.play()
          if (p) {
            void p.catch(() => {
              setCameraError('相機影像播放失敗，請重新啟用相機')
            })
          }
        }
        setCameraReady(true)
      } catch (err) {
        stopLocalCamera()
        setCameraError(err instanceof Error ? err.message : '無法存取筆電相機，請確認權限設定')
      }
    }

    void startLocalCamera()

    return () => {
      cancelled = true
      stopLocalCamera()
    }
  }, [cameraEnabled])

  const incomingPoseEvents = useMemo(
    () => allEvents
      .filter((e): e is PoseEvent => e.source === 'pose' && e.event_type === 'pose_detected'),
    [allEvents]
  )

  useEffect(() => {
    if (incomingPoseEvents.length === 0) return

    setAllPoseHistory((prev) => {
      const seen = new Set(prev.map((evt) => `${evt.id}-${evt.timestamp}`))
      const appended: PoseEvent[] = []

      for (const evt of incomingPoseEvents) {
        const key = `${evt.id}-${evt.timestamp}`
        if (!seen.has(key)) {
          seen.add(key)
          appended.push(evt)
        }
      }

      if (appended.length === 0) return prev
      return [...appended, ...prev]
    })
  }, [incomingPoseEvents])

  const recentPoseEvents = useMemo(
    () => allPoseHistory.slice(0, MAX_HISTORY),
    [allPoseHistory]
  )

  const status = !poseState || poseState.status === 'loading'
    ? 'loading' as const
    : poseState.current_pose === 'fallen'
      ? 'error' as const
      : poseState.active
        ? 'active' as const
        : 'inactive' as const

  const pose = poseState?.current_pose
  const poseKey = normalizePoseKey(pose)
  const poseLabel = getPoseLabel(pose)
  const poseEmoji = pose ? (POSE_EMOJI[poseKey] ?? '🧍') : '🧍'
  const confidence = Math.max(0, Math.min(100, Math.round((poseState?.confidence ?? 0) * 100)))
  const poseToneClass = getPoseStyle(pose)

  return (
    <PanelCard
      title="姿勢辨識"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      <div className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border/20 bg-surface/30 p-2">
          <div className="text-[11px] text-muted-foreground">姿勢即時監看控制</div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              size="sm"
              variant={cameraEnabled ? 'default' : 'secondary'}
              className="h-7 text-xs"
              onClick={() => setCameraEnabled((v) => !v)}
            >
              {cameraEnabled ? '停用相機' : '啟用相機'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="h-7 text-xs"
              onClick={() => setHistoryModalOpen(true)}
            >
              <History className="mr-1 h-3.5 w-3.5" />
              查看完整歷史
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)] md:items-stretch">
          <div className="relative aspect-4/3 overflow-hidden rounded-sm border border-border/30 bg-surface md:aspect-auto md:h-full md:self-stretch">
            {cameraEnabled ? (
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="h-full w-full object-cover"
              />
            ) : (
              <img src={PLACEHOLDER_SRC} alt="pose placeholder" className="h-full w-full object-cover opacity-45" />
            )}
            {cameraEnabled && !cameraReady && !cameraError && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/35 text-xs text-muted-foreground">
                正在啟用相機...
              </div>
            )}
            <div className="absolute left-2 top-2 rounded bg-background/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {!cameraEnabled
                ? '相機已停用'
                : cameraError
                  ? '相機啟用失敗'
                  : cameraReady
                    ? '筆電相機'
                    : '啟用中'}
            </div>
            <div className="absolute right-2 top-2 rounded bg-background/70 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
              {cameraEnabled && cameraReady ? 'LIVE' : '--'}
            </div>
            {cameraError && (
              <div className="absolute inset-x-2 bottom-2 rounded bg-red-500/20 px-2 py-1 text-[10px] text-red-200">
                {cameraError}
              </div>
            )}
          </div>

          <div className="flex h-full flex-col gap-3">
            <div className="rounded-sm border border-border/40 bg-surface p-3 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="text-2xl leading-none">{poseEmoji}</span>
                <div className="flex min-w-0 flex-col">
                  <span className="text-[11px] text-muted-foreground">目前姿勢</span>
                  <span className={cn('truncate text-sm font-semibold', poseToneClass)}>
                    {poseLabel}
                  </span>
                </div>
              </div>
              {poseState?.track_id != null && (
                <span className="mt-2 block text-[11px] text-muted-foreground">Track #{poseState.track_id}</span>
              )}
            </div>

            <div className="rounded-sm border border-border/40 bg-surface p-3 shadow-sm">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground">姿勢辨識信心度</span>
                <MetricChip label="信心度" value={confidence} unit="%" />
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted/70">
                <div
                  className={cn(
                    'h-full rounded-full transition-all duration-300',
                    confidence >= 80 ? 'bg-emerald-400/80' : confidence >= 50 ? 'bg-amber-400/80' : 'bg-rose-400/80'
                  )}
                  style={{ width: `${confidence}%` }}
                />
              </div>
            </div>

            <div className="rounded-sm border border-border/30 bg-surface/40 p-2.5">
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs font-medium text-foreground">辨識歷史</span>
                <span className="text-[10px] text-muted-foreground">最近 {MAX_HISTORY} 筆</span>
              </div>

              {recentPoseEvents.length > 0 ? (
                <div className="space-y-1.5">
                  {recentPoseEvents.map((event) => {
                    const rawEventPose = getEventPoseValue(event)
                    const eventPose = normalizePoseKey(rawEventPose)
                    const eventLabel = getPoseLabel(rawEventPose)
                    const eventEmoji = POSE_EMOJI[eventPose] ?? '🧍'
                    const eventConfidence = Math.round(event.data.confidence * 100)
                    const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })

                    return (
                      <div
                        key={event.id}
                        className="flex h-7 items-center gap-2 rounded-md border border-border/20 bg-surface/60 px-2 py-1"
                      >
                        <span className="text-sm leading-none">{eventEmoji}</span>
                        <span className={cn('shrink-0 text-[11px] font-medium', getPoseStyle(eventPose))}>{eventLabel}</span>
                        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{time}</span>
                        <span className="text-[10px] text-muted-foreground">{eventConfidence}%</span>
                      </div>
                    )
                  })}

                  {Array.from({ length: Math.max(0, MAX_HISTORY - recentPoseEvents.length) }).map((_, idx) => (
                    <div
                      key={`pose-placeholder-${idx}`}
                      className="h-7 rounded-md border border-border/10 bg-surface/20 opacity-0"
                      aria-hidden="true"
                    />
                  ))}
                </div>
              ) : (
                <div className="space-y-1.5">
                  <div className="py-3 text-center text-xs text-muted-foreground">
                    尚無歷史資料
                  </div>
                  {Array.from({ length: MAX_HISTORY }).map((_, idx) => (
                    <div
                      key={`pose-empty-placeholder-${idx}`}
                      className="h-7 rounded-md border border-border/10 bg-surface/20 opacity-0"
                      aria-hidden="true"
                    />
                  ))}
                </div>
              )}

              {status === 'error' && poseKey === 'fallen' && (
                <div className="mt-2 rounded-md border border-red-500/40 bg-red-500/10 px-2.5 py-1.5 text-xs font-semibold text-red-300">
                  偵測到跌倒，請立即確認現場狀況。
                </div>
              )}
            </div>
          </div>
        </div>

        {historyModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm">
            <div className="w-full max-w-3xl rounded-xl border border-border/40 bg-card shadow-2xl">
              <div className="flex items-center justify-between border-b border-border/30 px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <History className="h-4 w-4" />
                  姿勢完整歷史紀錄
                </div>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-7 w-7"
                  onClick={() => setHistoryModalOpen(false)}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>

              <ScrollArea className="h-[65vh] px-4 py-3">
                {allPoseHistory.length > 0 ? (
                  <div className="space-y-2 pb-2">
                    {allPoseHistory.map((event) => {
                      const rawEventPose = getEventPoseValue(event)
                      const eventPose = normalizePoseKey(rawEventPose)
                      const eventLabel = getPoseLabel(rawEventPose)
                      const eventEmoji = POSE_EMOJI[eventPose] ?? '🧍'
                      const eventConfidence = Math.round(event.data.confidence * 100)
                      const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })

                      return (
                        <div
                          key={`modal-${event.id}`}
                          className="flex items-center gap-2 rounded-md border border-border/20 bg-surface/60 px-2.5 py-1.5"
                        >
                          <span className="text-base leading-none">{eventEmoji}</span>
                          <span className={cn('text-xs font-medium', getPoseStyle(eventPose))}>{eventLabel}</span>
                          <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{time}</span>
                          <span className="text-[10px] text-muted-foreground">{eventConfidence}%</span>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="py-12 text-center text-sm text-muted-foreground">
                    目前沒有可顯示的姿勢歷史資料
                  </div>
                )}
              </ScrollArea>
            </div>
          </div>
        )}
      </div>
    </PanelCard>
  )
}