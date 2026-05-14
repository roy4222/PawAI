"use client"

// local-camera.tsx — 📷 Camera tab
//
// Default: Jetson D435 + YOLO debug image via gateway `/ws/video/object`
//          (`/perception/object/debug_image` — bboxes already drawn server-side).
// Fallback: browser webcam preview with optional bbox overlay from gateway
//          `objectState.detected_objects`. The PR #40 "Python YOLO MJPEG +
//          /mock/yolo/start" path was dropped — those endpoints only exist
//          on the mock server, not on the real Jetson gateway.

import { useCallback, useEffect, useRef, useState } from "react"
import { Video } from "lucide-react"
import { LiveFeedCard } from "@/components/live/live-feed-card"
import { useStateStore } from "@/stores/state-store"
import type { ObjectState } from "@/contracts/types"
import { isWhitelisted, getObjectEntry, getLabel, COLOR_ZH, YOLO_MODEL_W, YOLO_MODEL_H } from "./object-config"
import { cn } from "@/lib/utils"

interface DetectionBox {
  class_name: string
  confidence: number
  bbox: [number, number, number, number]
  color?: string
}

function WebcamWithOverlay() {
  const videoRef = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<MediaStream | null>(null)

  const [camState, setCamState] = useState<"idle" | "requesting" | "active" | "denied">("idle")
  const [error, setError] = useState<string | null>(null)
  const [containerSize, setContainerSize] = useState<{ w: number; h: number }>({ w: 0, h: 0 })

  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const boxes: DetectionBox[] = (objectState?.detected_objects ?? []) as DetectionBox[]

  // Track container size via ResizeObserver so bboxStyle is a pure function
  // of state — avoids "cannot access refs during render" lint error.
  useEffect(() => {
    const el = containerRef.current
    if (!el || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect
      if (rect) setContainerSize({ w: rect.width, h: rect.height })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const startCamera = useCallback(async () => {
    setCamState("requesting")
    setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play()
      }
      setCamState("active")
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg.includes("Permission") ? "鏡頭權限被拒絕" : msg)
      setCamState("denied")
    }
  }, [])

  useEffect(() => {
    // Async camera init — startCamera updates camState/error internally.
    // Suppressed because the alternative (lifting init to a click handler)
    // breaks the "auto-prompt on mount" UX from PR #40.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void startCamera()
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
  }, [startCamera])

  function bboxStyle(bbox: [number, number, number, number]) {
    const { w: cw, h: ch } = containerSize
    if (cw === 0 || ch === 0) return { display: "none" }
    const scale = Math.min(cw / YOLO_MODEL_W, ch / YOLO_MODEL_H)
    const ox = (cw - YOLO_MODEL_W * scale) / 2
    const oy = (ch - YOLO_MODEL_H * scale) / 2
    const [x1, y1, x2, y2] = bbox
    return {
      left: `${ox + x1 * scale}px`,
      top: `${oy + y1 * scale}px`,
      width: `${(x2 - x1) * scale}px`,
      height: `${(y2 - y1) * scale}px`,
    }
  }

  return (
    <div ref={containerRef} className="relative w-full rounded-xl overflow-hidden bg-black border border-border/30 aspect-video">
      {camState === "denied" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
          <span className="text-5xl opacity-20 select-none">🚫</span>
          <p className="text-sm">{error ?? "相機被拒絕"}</p>
        </div>
      )}
      {camState === "requesting" && (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
        </div>
      )}
      <video
        ref={videoRef}
        className={cn("w-full h-full object-contain pointer-events-none", camState !== "active" && "hidden")}
        muted
        playsInline
      />
      {camState === "active" &&
        boxes.map((box, i) => {
          if (!box.bbox) return null
          const entry = getObjectEntry(box.class_name)
          const inWL = isWhitelisted(box.class_name)
          return (
            <div key={i} className="absolute pointer-events-none" style={bboxStyle(box.bbox)}>
              <div className={cn("absolute inset-0 rounded border-2", inWL ? "border-amber-400" : "border-zinc-500")} />
              <div
                className={cn(
                  "absolute -top-5 left-0 flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap",
                  inWL ? "bg-amber-400 text-black" : "bg-zinc-700 text-zinc-200",
                )}
              >
                <span>{entry?.emoji ?? "📦"}</span>
                <span>
                  {box.color && box.color !== "Unknown" ? `${COLOR_ZH[box.color] ?? box.color} ` : ""}
                  {getLabel(box.class_name)}
                </span>
                <span className="opacity-70">{Math.round(box.confidence * 100)}%</span>
              </div>
            </div>
          )
        })}
      {camState === "active" && (
        <div className="absolute top-2 left-2 flex flex-col gap-1">
          <span className="text-[9px] font-mono text-amber-400/70 bg-black/50 border border-amber-400/20 px-1.5 py-0.5 rounded">
            SOURCE: BROWSER WEBCAM
          </span>
          <span className="text-[9px] font-mono text-zinc-400/70 bg-black/50 border border-border/20 px-1.5 py-0.5 rounded">
            BBOX: GATEWAY WS ({boxes.length} obj)
          </span>
        </div>
      )}
    </div>
  )
}

export function LocalCameraView() {
  const [useWebcam, setUseWebcam] = useState(false)

  return (
    <div className="flex flex-col gap-3">
      {/* Source toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">📷</span>
          <span className="text-sm font-medium text-foreground">影像來源</span>
        </div>
        <div className="flex items-center gap-2 bg-surface/50 p-1 rounded-lg border border-border/20">
          <button
            type="button"
            onClick={() => setUseWebcam(false)}
            className={cn(
              "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-all",
              !useWebcam
                ? "bg-amber-400 text-black shadow-sm"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
            )}
          >
            🤖 Jetson Live Feed
          </button>
          <button
            type="button"
            onClick={() => setUseWebcam(true)}
            className={cn(
              "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-all",
              useWebcam
                ? "bg-amber-400 text-black shadow-sm"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground",
            )}
          >
            <Video className="w-3.5 h-3.5" /> 本機相機
          </button>
        </div>
      </div>

      {useWebcam ? (
        <WebcamWithOverlay />
      ) : (
        <LiveFeedCard
          source="object"
          title="Jetson YOLO Live"
          topicName="/perception/object/debug_image"
        />
      )}

      <div className="rounded-lg bg-surface/40 border border-border/20 px-3 py-2.5 text-[11px] text-muted-foreground leading-relaxed">
        <p className="font-medium text-amber-400 mb-1">📌 模式說明</p>
        <p>
          <strong>Jetson Live Feed</strong>（推薦）— 直接看 Jetson 的 D435 + YOLO debug image，bbox 由 server 端
          畫好。<strong>本機相機</strong> — 用瀏覽器 webcam 顯示影像，bbox 從 gateway 的 objectState 同步疊加（dev fallback）。
        </p>
      </div>
    </div>
  )
}
