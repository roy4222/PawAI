"use client"

// local-camera.tsx — 📷 本機鏡頭 + bbox overlay
import { useState, useEffect, useRef, useCallback } from "react"
import { useStateStore } from "@/stores/state-store"
import type { ObjectState } from "@/contracts/types"
import { isWhitelisted, getObjectEntry, getLabel, YOLO_MODEL_W, YOLO_MODEL_H } from "./object-config"
import { cn } from "@/lib/utils"

interface DetectionBox {
  class_name: string
  confidence: number
  bbox: [number, number, number, number]
}

export function LocalCameraView() {
  const videoRef     = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const streamRef    = useRef<MediaStream | null>(null)
  const [camState, setCamState] = useState<"idle" | "requesting" | "active" | "denied">("idle")
  const [error,    setError   ] = useState<string | null>(null)

  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const boxes: DetectionBox[] = (objectState?.detected_objects ?? []) as DetectionBox[]

  const startCamera = useCallback(async () => {
    setCamState("requesting"); setError(null)
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      })
      streamRef.current = stream
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play() }
      setCamState("active")
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(msg.includes("Permission") ? "鏡頭權限被拒絕，請允許瀏覽器存取鏡頭" : msg)
      setCamState("denied")
    }
  }, [])

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setCamState("idle")
  }, [])

  useEffect(() => () => { streamRef.current?.getTracks().forEach((t) => t.stop()) }, [])

  function bboxStyle(bbox: [number, number, number, number]) {
    const el = containerRef.current; if (!el) return {}
    const { width: cw, height: ch } = el.getBoundingClientRect()
    const scale = Math.min(cw / YOLO_MODEL_W, ch / YOLO_MODEL_H)
    const ox = (cw - YOLO_MODEL_W * scale) / 2
    const oy = (ch - YOLO_MODEL_H * scale) / 2
    const [x1, y1, x2, y2] = bbox
    return { left: `${ox + x1 * scale}px`, top: `${oy + y1 * scale}px`, width: `${(x2 - x1) * scale}px`, height: `${(y2 - y1) * scale}px` }
  }

  return (
    <div className="flex flex-col gap-3">
      {/* 控制列 */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">📷</span>
          <span className="text-sm font-medium text-foreground">本機鏡頭</span>
          {camState === "active" && (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />直播中
            </span>
          )}
        </div>
        {camState !== "active"
          ? <button onClick={startCamera} disabled={camState === "requesting"} className={cn("text-xs px-3 py-1.5 rounded-lg font-medium transition-all bg-amber-400/10 text-amber-400 border border-amber-400/20 hover:bg-amber-400/20 disabled:opacity-50 disabled:cursor-not-allowed")}>
              {camState === "requesting" ? "開啟中..." : "開啟鏡頭"}
            </button>
          : <button onClick={stopCamera} className="text-xs px-3 py-1.5 rounded-lg font-medium bg-rose-400/10 text-rose-400 border border-rose-400/20 hover:bg-rose-400/20 transition-all">關閉鏡頭</button>
        }
      </div>

      {error && <div className="rounded-lg bg-rose-400/10 border border-rose-400/20 px-3 py-2 text-xs text-rose-400">⚠️ {error}</div>}

      {/* 影像框 */}
      <div ref={containerRef} className="relative w-full rounded-xl overflow-hidden bg-black border border-border/30 aspect-video">
        {(camState === "idle" || camState === "denied") && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <span className="text-5xl opacity-20 select-none">📷</span>
            <p className="text-sm">{camState === "denied" ? "鏡頭存取被拒" : "點擊「開啟鏡頭」開始"}</p>
          </div>
        )}
        {camState === "requesting" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
          </div>
        )}
        <video ref={videoRef} className={cn("w-full h-full object-contain", camState !== "active" && "opacity-0")} muted playsInline />

        {/* bbox */}
        {camState === "active" && boxes.map((box, i) => {
          if (!box.bbox) return null
          const entry = getObjectEntry(box.class_name)
          const inWL  = isWhitelisted(box.class_name)
          return (
            <div key={i} className="absolute pointer-events-none" style={bboxStyle(box.bbox)}>
              <div className={cn("absolute inset-0 rounded border-2", inWL ? "border-amber-400" : "border-zinc-500")} />
              <div className={cn("absolute -top-5 left-0 flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap", inWL ? "bg-amber-400 text-black" : "bg-zinc-700 text-zinc-200")}>
                <span>{entry?.emoji ?? "📦"}</span>
                <span>{getLabel(box.class_name)}</span>
                <span className="opacity-70">{Math.round(box.confidence * 100)}%</span>
              </div>
            </div>
          )
        })}

        {/* HUD */}
        {camState === "active" && (
          <div className="absolute top-2 left-2 flex flex-col gap-1">
            <span className="text-[9px] font-mono text-zinc-400/70 bg-black/50 px-1.5 py-0.5 rounded">LOCAL CAM · {boxes.length} obj</span>
            <span className="text-[9px] font-mono text-amber-400/70 bg-black/50 px-1.5 py-0.5 rounded">bbox src: WebSocket</span>
          </div>
        )}
      </div>

      <div className="rounded-lg bg-surface/40 border border-border/20 px-3 py-2.5 text-[11px] text-muted-foreground leading-relaxed">
        <p className="font-medium text-foreground mb-1">📌 使用說明</p>
        <ul className="space-y-0.5 list-disc list-inside">
          <li>框框來自 WebSocket，<span className="text-amber-400">金色</span> = 白名單，灰色 = 靜默</li>
          <li>Mock 模式 bbox 是隨機的，連接 Jetson 後才準確</li>
          <li>鏡頭高度 ~30cm 模擬 Go2 視角（參考 object-wu.md）</li>
        </ul>
      </div>
    </div>
  )
}
