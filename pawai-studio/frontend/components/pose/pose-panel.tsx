'use client'

import { useMemo, useRef, useState } from 'react'
import { Activity, History, X } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { LiveFeedCard } from '@/components/live/live-feed-card'
import { useStateStore } from '@/stores/state-store'
import { useEventStore } from '@/stores/event-store'
import type { PoseState, PoseEvent } from '@/contracts/types'
import { cn } from '@/lib/utils'
import { getPoseEmoji, getPoseLabel, getPoseStyle, isFallenPose, normalizePoseKey } from './pose-mapper'
import { usePoseStream } from './use-pose-stream'
import { DEFAULT_POSE_INFERENCE_CONFIG, isPoseInferenceEnabled } from './pose-types'

const MAX_HISTORY = 10

/**
 * PosePanel — Demo path:
 *   • Left:  Live video from Jetson via gateway `/ws/video/vision`
 *            (`vision_perception/debug_image` — already includes skeleton).
 *   • Right: Pose card + confidence + history from gateway `/ws/events`
 *            (`useStateStore.poseState`).
 *
 * Dev-only fallback (when no Jetson available, e.g. local mock):
 *   • Toggle "本機相機" → use browser webcam preview instead of LiveFeedCard.
 *   • If `NEXT_PUBLIC_POSE_INFER_ENDPOINT` is set, run PR #41 HTTP inference
 *     against that endpoint and overlay the returned skeleton image.
 */
export function PosePanel() {
  const ros2Pose = useStateStore((s) => s.poseState) as PoseState | null
  const allEvents = useEventStore((s) => s.events)

  const ros2PoseEvents = useMemo(() => {
    return (allEvents.filter((e) => e.source === 'pose') as PoseEvent[]).slice(0, MAX_HISTORY)
  }, [allEvents])

  // Local webcam fallback (default OFF — Jetson live feed is primary).
  const [useLocalCam, setUseLocalCam] = useState(false)
  const [historyModalOpen, setHistoryModalOpen] = useState(false)
  const localInferenceAvailable = isPoseInferenceEnabled(DEFAULT_POSE_INFERENCE_CONFIG)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const stream = usePoseStream({
    enabled: useLocalCam && localInferenceAvailable,
    videoRef,
    maxHistory: 300,
  })

  // Pose data source: local inference takes over only when active AND returning
  // results. Otherwise always read from gateway poseState.
  const usingLocalData = useLocalCam && localInferenceAvailable && stream.lastResult !== null
  const pose: string | null = usingLocalData
    ? stream.lastResult?.pose ?? null
    : ros2Pose?.current_pose ?? null
  const confidence = usingLocalData
    ? Math.max(0, Math.min(100, Math.round((stream.lastResult?.confidence ?? 0) * 100)))
    : Math.max(0, Math.min(100, Math.round((ros2Pose?.confidence ?? 0) * 100)))
  const trackId = usingLocalData ? stream.lastResult?.track_id ?? null : ros2Pose?.track_id ?? null

  const status: 'loading' | 'active' | 'inactive' | 'error' = (() => {
    if (usingLocalData) {
      return isFallenPose(pose) ? 'error' : 'active'
    }
    if (ros2Pose === null) return 'loading'
    if (ros2Pose.status === 'loading') return 'loading'
    if (ros2Pose.status === 'error') return 'error'
    if (ros2Pose.current_pose === 'fallen') return 'error'
    return ros2Pose.active ? 'active' : 'inactive'
  })()

  const poseKey = normalizePoseKey(pose)
  const poseLabel = getPoseLabel(pose)
  const poseEmoji = getPoseEmoji(pose)
  const poseToneClass = getPoseStyle(pose)

  const recentEvents = usingLocalData
    ? stream.history.slice(0, MAX_HISTORY).map((e) => ({
        id: e.id,
        pose: e.pose,
        confidence: e.confidence,
        timestamp: e.timestamp,
      }))
    : ros2PoseEvents.map((e) => ({
        id: e.id,
        pose: e.data.pose,
        confidence: e.data.confidence,
        timestamp:
          typeof e.timestamp === 'number'
            ? new Date(e.timestamp * 1000).toISOString()
            : new Date(e.timestamp).toISOString(),
      }))

  const fullHistory = usingLocalData
    ? stream.history.map((e) => ({
        id: e.id,
        pose: e.pose,
        confidence: e.confidence,
        timestamp: e.timestamp,
      }))
    : recentEvents

  return (
    <PanelCard
      title="姿勢辨識"
      href="/studio/pose"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      <div className="space-y-3 p-3 pt-0">
        {/* Source toggle */}
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-border/20 bg-surface/30 p-2">
          <div className="flex flex-col gap-0.5">
            <div className="text-[11px] text-muted-foreground">
              畫面來源：
              <span className={cn('ml-1 font-medium', useLocalCam ? 'text-amber-300' : 'text-emerald-300')}>
                {useLocalCam ? '本機相機（dev fallback）' : 'Jetson Live Feed'}
              </span>
            </div>
            {useLocalCam && !localInferenceAvailable && (
              <div className="text-[10px] text-muted-foreground/70">
                未設定 <code>NEXT_PUBLIC_POSE_INFER_ENDPOINT</code>，僅顯示相機影像、無骨架疊加
              </div>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Button
              size="sm"
              variant={useLocalCam ? 'default' : 'secondary'}
              className="h-7 text-xs"
              onClick={() => setUseLocalCam((v) => !v)}
            >
              {useLocalCam ? '改用 Jetson Feed' : '本機相機（fallback）'}
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
          {/* LEFT — live video */}
          <div className="md:h-full">
            {useLocalCam ? (
              <div className="relative aspect-[4/3] overflow-hidden rounded-lg border border-zinc-800 bg-zinc-950 md:h-full md:aspect-auto md:self-stretch">
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  playsInline
                  className="h-full w-full object-cover"
                />
                {stream.cameraReady && stream.annotatedFrameDataUrl && (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={stream.annotatedFrameDataUrl}
                    alt="pose skeleton overlay"
                    className="pointer-events-none absolute inset-0 h-full w-full object-cover"
                  />
                )}
                {!stream.cameraReady && !stream.cameraError && (
                  <div className="absolute inset-0 flex items-center justify-center bg-black/35 text-xs text-muted-foreground">
                    正在啟用相機...
                  </div>
                )}
                <div className="absolute left-2 top-2 rounded bg-background/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  本機相機
                </div>
                <div className="absolute right-2 top-2 rounded bg-background/70 px-1.5 py-0.5 text-[10px] font-mono text-muted-foreground">
                  {stream.cameraReady ? (stream.isInferring ? 'LIVE*' : 'LIVE') : '--'}
                </div>
                {(stream.cameraError || stream.inferenceError) && (
                  <div className="absolute inset-x-2 bottom-2 rounded bg-red-500/20 px-2 py-1 text-[10px] text-red-200">
                    {stream.cameraError ?? stream.inferenceError}
                  </div>
                )}
              </div>
            ) : (
              <LiveFeedCard
                source="vision"
                title="Vision Live (Pose + Gesture)"
                topicName="/vision_perception/debug_image"
              />
            )}
          </div>

          {/* RIGHT — pose card + confidence + history */}
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
              {trackId != null && (
                <span className="mt-2 block text-[11px] text-muted-foreground">Track #{trackId}</span>
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

              {recentEvents.length > 0 ? (
                <div className="space-y-1.5">
                  {recentEvents.map((event) => {
                    const eventPose = normalizePoseKey(event.pose)
                    const eventLabel = getPoseLabel(event.pose)
                    const eventEmoji = getPoseEmoji(event.pose)
                    const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })

                    return (
                      <div
                        key={event.id}
                        className="flex h-7 items-center gap-2 rounded-md border border-border/20 bg-surface/60 px-2 py-1"
                      >
                        <span className="text-sm leading-none">{eventEmoji}</span>
                        <span className={cn('shrink-0 text-[11px] font-medium', getPoseStyle(eventPose))}>{eventLabel}</span>
                        <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{time}</span>
                        <span className="text-[10px] text-muted-foreground">{Math.round(event.confidence * 100)}%</span>
                      </div>
                    )
                  })}
                </div>
              ) : (
                <div className="py-3 text-center text-xs text-muted-foreground">
                  尚無歷史資料
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
          <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm">
            <div className="w-full max-w-3xl rounded-xl border border-border/40 bg-card shadow-2xl">
              <div className="flex items-center justify-between border-b border-border/30 px-4 py-3">
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <History className="h-4 w-4" />
                  姿勢完整歷史紀錄（{usingLocalData ? '本機推論' : 'Gateway'}）
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
                {fullHistory.length > 0 ? (
                  <div className="space-y-2 pb-2">
                    {fullHistory.map((event) => {
                      const eventPose = normalizePoseKey(event.pose)
                      const eventLabel = getPoseLabel(event.pose)
                      const eventEmoji = getPoseEmoji(event.pose)
                      const time = new Date(event.timestamp).toLocaleTimeString('zh-TW', { hour12: false })

                      return (
                        <div
                          key={`modal-${event.id}`}
                          className="flex items-center gap-2 rounded-md border border-border/20 bg-surface/60 px-2.5 py-1.5"
                        >
                          <span className="text-base leading-none">{eventEmoji}</span>
                          <span className={cn('text-xs font-medium', getPoseStyle(eventPose))}>{eventLabel}</span>
                          <span className="ml-auto text-[10px] text-muted-foreground tabular-nums">{time}</span>
                          <span className="text-[10px] text-muted-foreground">{Math.round(event.confidence * 100)}%</span>
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
