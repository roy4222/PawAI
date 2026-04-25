'use client'

import { useMemo, useRef, useState } from 'react'
import { Activity, History, X } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { getPoseEmoji, getPoseLabel, getPoseStyle, isFallenPose, normalizePoseKey } from './pose-mapper'
import { usePoseStream } from './use-pose-stream'

const PLACEHOLDER_SRC = '/mock/pose-placeholder.svg'
const MAX_HISTORY = 10

export function PosePanel() {
  const [cameraEnabled, setCameraEnabled] = useState(true)
  const [historyModalOpen, setHistoryModalOpen] = useState(false)

  const videoRef = useRef<HTMLVideoElement | null>(null)
  const {
    cameraReady,
    cameraError,
    inferenceError,
    isInferring,
    annotatedFrameDataUrl,
    lastResult,
    history,
  } = usePoseStream({
    enabled: cameraEnabled,
    videoRef,
    maxHistory: 300,
  })

  const recentPoseEvents = useMemo(
    () => history.slice(0, MAX_HISTORY),
    [history]
  )

  const status = !lastResult
    ? 'loading' as const
    : isFallenPose(lastResult.pose)
      ? 'error' as const
      : cameraEnabled
        ? 'active' as const
        : 'inactive' as const

  const pose = lastResult?.pose ?? null
  const poseKey = normalizePoseKey(pose)
  const poseLabel = getPoseLabel(pose)
  const poseEmoji = getPoseEmoji(pose)
  const confidence = Math.max(0, Math.min(100, Math.round((lastResult?.confidence ?? 0) * 100)))
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
              <>
                <video
                  ref={videoRef}
                  autoPlay
                  muted
                  playsInline
                  className="h-full w-full object-cover"
                />
                {cameraReady && annotatedFrameDataUrl && (
                  <img
                    src={annotatedFrameDataUrl}
                    alt="pose skeleton overlay"
                    className="pointer-events-none absolute inset-0 h-full w-full object-cover"
                  />
                )}
              </>
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
              {cameraEnabled && cameraReady ? (isInferring ? 'LIVE*' : 'LIVE') : '--'}
            </div>
            {(cameraError || inferenceError) && (
              <div className="absolute inset-x-2 bottom-2 rounded bg-red-500/20 px-2 py-1 text-[10px] text-red-200">
                {cameraError ?? inferenceError}
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
              {lastResult?.track_id != null && (
                <span className="mt-2 block text-[11px] text-muted-foreground">Track #{lastResult.track_id}</span>
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
                {history.length > 0 ? (
                  <div className="space-y-2 pb-2">
                    {history.map((event) => {
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