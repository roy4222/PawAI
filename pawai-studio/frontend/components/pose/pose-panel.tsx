'use client'
import React from 'react'
import { Activity } from 'lucide-react'
import { PanelCard } from '@/components/shared/panel-card'
import { MetricChip } from '@/components/shared/metric-chip'
import { useStateStore } from '@/stores/state-store'
import type { PoseState } from '@/contracts/types'

const POSE_LABELS: Record<string, string> = {
  standing: '站立',
  sitting: '坐著',
  crouching: '蹲下',
  fallen: '跌倒',
}

const POSE_EMOJI: Record<string, string> = {
  standing: '🧍',
  sitting: '🪑',
  crouching: '🏋️',
  fallen: '⚠️',
}

const PLACEHOLDER_SRC = "/mock/pose-placeholder.svg"
const SHOW_PLACEHOLDER = true

export function PosePanel() {
  const poseState = useStateStore((s) => s.poseState) as PoseState | null

  const status = !poseState
    ? 'inactive' as const
    : poseState.current_pose === 'fallen'
      ? 'error' as const
      : poseState.active
        ? 'active' as const
        : 'inactive' as const

  const pose = poseState?.current_pose
  const poseLabel = pose ? (POSE_LABELS[pose] ?? pose) : null

  return (
    <PanelCard
      title="姿勢辨識"
      icon={<Activity className="h-4 w-4" />}
      status={status}
    >
      <div className="p-3 pt-0">
        {poseLabel ? (
          <div className="grid grid-cols-2 gap-3">
            
            {/* 左側：影像區塊 */}
            {SHOW_PLACEHOLDER && (
              <div className="relative aspect-square rounded-[var(--radius-sm)] overflow-hidden border border-border/20 bg-surface flex items-center justify-center">
                <img src={PLACEHOLDER_SRC} alt="pose placeholder" className="w-full h-full object-cover opacity-50" />
                <span className="absolute text-[10px] text-muted-foreground bg-background/80 px-2 py-0.5 rounded">
                  影像區
                </span>
              </div>
            )}

            {/* 右側：資料小卡區塊 
                🟢 修改重點：加上 h-full，並拿掉 justify-center */}
            <div className="flex flex-col gap-3 h-full">
              
              {/* 卡片 1：姿勢狀態 
                  🟢 修改重點：加上 flex-1 讓它垂直拉伸填滿，並用 justify-center 讓內容居中 */}
              <div className="flex-1 p-2 rounded-[var(--radius-sm)] border border-border/50 bg-surface flex flex-col justify-center gap-1 shadow-sm">
                <div className="flex items-center gap-2">
                  <span className="text-xl leading-none">{POSE_EMOJI[pose!] ?? '🧍'}</span>
                  <span className="text-sm font-bold text-foreground">{poseLabel}</span>
                </div>
                {poseState?.track_id != null && (
                  <span className="text-[10px] text-muted-foreground">
                    Track #{poseState.track_id}
                  </span>
                )}
              </div>

              {/* 卡片 2：信心度 
                  🟢 修改重點：加上 flex-1 讓它垂直拉伸填滿 */}
              <div className="flex-1 p-1.5 rounded-[var(--radius-sm)] border border-border/50 bg-surface flex items-center justify-center shadow-sm">
                <MetricChip label="信心度" value={Math.round((poseState?.confidence ?? 0) * 100)} unit="%" />
              </div>
              
            </div>
          </div>
        ) : (
          <div className="py-4 text-center text-muted-foreground text-sm">
            尚未偵測到姿勢
          </div>
        )}
      </div>
    </PanelCard>
  )
}