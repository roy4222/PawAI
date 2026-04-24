"use client"

// local-camera.tsx — 📷 本機鏡頭 + bbox overlay
import { useState, useEffect, useRef, useCallback } from "react"
import { useStateStore } from "@/stores/state-store"
import type { ObjectState } from "@/contracts/types"
import { isWhitelisted, getObjectEntry, getLabel, YOLO_MODEL_W, YOLO_MODEL_H } from "./object-config"
import { cn } from "@/lib/utils"
import { getGatewayHttpUrl } from "@/lib/gateway-url"
import { MonitorPlay, Video } from "lucide-react"

interface DetectionBox {
  class_name: string
  confidence: number
  bbox: [number, number, number, number]
}

export function LocalCameraView() {
  const videoRef     = useRef<HTMLVideoElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const streamRef    = useRef<MediaStream | null>(null)
  const gatewayUrl = getGatewayHttpUrl()
  const yoloStreamUrl = process.env.NEXT_PUBLIC_LOCAL_YOLO_STREAM_URL || "http://127.0.0.1:8081/video_feed"
  
  // 鏡頭模式：硬體(網頁存取) 或 串流(Python 傳送)
  const [sourceMode, setSourceMode] = useState<"hardware" | "stream">("stream")
  const [camState, setCamState] = useState<"idle" | "requesting" | "active" | "denied">("idle")
  const [error, setError] = useState<string | null>(null)

  const objectState = useStateStore((s) => s.objectState) as ObjectState | null
  const boxes: DetectionBox[] = (objectState?.detected_objects ?? []) as DetectionBox[]

  // [硬體模式] 開啟本機鏡頭
  const startHardwareCamera = useCallback(async () => {
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
      setError(msg.includes("Permission") ? "鏡頭權限被拒絕，請改用 Python 串流" : msg)
      setCamState("denied")
    }
  }, [])

  // 關閉所有鏡頭/串流
  const stopCamera = useCallback(async () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (videoRef.current) videoRef.current.srcObject = null
    
    // 通知後端關閉 YOLO 串流腳本
    try {
      if (sourceMode === "stream") await fetch(`${gatewayUrl}/mock/yolo/stop`, { method: "POST" })
    } catch (e) { /* ignore */ }
    
    setCamState("idle")
    setError(null)
  }, [sourceMode, gatewayUrl])

  // [串流模式] 啟動
  const startStreamMode = useCallback(async () => {
    stopCamera()
    setSourceMode("stream")
    setCamState("requesting")
    setError("正在啟動 yolo26n.onnx 串流，請稍候...")
    
    try {
      // 呼叫 API 啟動 Python YOLO 腳本
      await fetch(`${gatewayUrl}/mock/yolo/start`, { method: "POST" })
      // 等待 3 秒鐘讓 Python 載入模型並開啟相機
      setTimeout(() => {
        setCamState("active")
        setError(null)
      }, 3000)
    } catch (err) {
      setError("無法呼叫伺服器啟動 YOLO，請確認 Mock Server 已啟動。")
      setCamState("denied")
    }
  }, [stopCamera, gatewayUrl])

  // 切換模式的按鈕行為
  const handleHardwareClick = () => {
    if (sourceMode === "hardware" && camState === "active") stopCamera()
    else { stopCamera(); setSourceMode("hardware"); startHardwareCamera() }
  }

  const handleStreamClick = () => {
    if (sourceMode === "stream" && (camState === "active" || camState === "requesting")) stopCamera()
    else startStreamMode()
  }

  useEffect(() => () => { stopCamera() }, [stopCamera])

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
      {/* ── 控制列 ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-sm">📷</span>
          <span className="text-sm font-medium text-foreground">攝影機來源</span>
          {camState === "active" && (
            <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-400/10 text-emerald-400 border border-emerald-400/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse inline-block" />
              {sourceMode === "stream" ? "接聽串流中" : "鏡頭開啟中"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 bg-surface/50 p-1 rounded-lg border border-border/20">
          <button
            onClick={handleStreamClick}
            className={cn(
              "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-all",
              sourceMode === "stream" && (camState === "active" || camState === "requesting")
                ? "bg-amber-400 text-black shadow-sm"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground"
            )}
          >
            <MonitorPlay className="w-3.5 h-3.5" /> Python YOLO 串流
          </button>
          <button
            onClick={handleHardwareClick}
            disabled={camState === "requesting"}
            className={cn(
              "flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-md font-medium transition-all",
              sourceMode === "hardware" && camState === "active"
                ? "bg-amber-400 text-black shadow-sm"
                : "text-muted-foreground hover:bg-surface-hover hover:text-foreground disabled:opacity-50"
            )}
          >
            <Video className="w-3.5 h-3.5" /> 網頁硬體鏡頭
          </button>
        </div>
      </div>

      {error && <div className="rounded-lg bg-rose-400/10 border border-rose-400/20 px-3 py-2 text-xs text-rose-400">⚠️ {error}</div>}

      {/* ── 影像框 ── */}
      <div ref={containerRef} className="relative w-full rounded-xl overflow-hidden bg-black border border-border/30 aspect-video">
        
        {/* 待機狀態 */}
        {(camState === "idle" || camState === "denied") && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <span className="text-5xl opacity-20 select-none">👀</span>
            <p className="text-sm">{camState === "denied" ? "存取被拒" : "請選擇上方的影像來源"}</p>
          </div>
        )}
        
        {/* 請求中 */}
        {camState === "requesting" && (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-2 border-amber-400 border-t-transparent" />
          </div>
        )}

        {/* 實際畫面 (根據模式切換 img 或 video) */}
        {camState === "active" && sourceMode === "stream" && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={yoloStreamUrl}
            className="w-full h-full object-contain pointer-events-none"
            alt="YOLO Stream"
            onError={() => {
              setError("無法連線到 Python 串流，請確認 local_yolo_mjpeg.py 正在運行")
            }}
          />
        )}
        <video
          ref={videoRef}
          className={cn("w-full h-full object-contain pointer-events-none", (sourceMode !== "hardware" || camState !== "active") && "hidden")}
          muted playsInline
        />

        {/* ── Bbox 疊加 ── */}
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

        {/* HUD 左上指標 */}
        {camState === "active" && (
          <div className="absolute top-2 left-2 flex flex-col gap-1">
            <span className="text-[9px] font-mono text-amber-400/70 bg-black/50 border border-amber-400/20 px-1.5 py-0.5 rounded">
              {sourceMode === "stream" ? "SOURCE: yolo26n.onnx" : "SOURCE: HARDWARE CAM"}
            </span>
            <span className="text-[9px] font-mono text-zinc-400/70 bg-black/50 border border-border/20 px-1.5 py-0.5 rounded">
              BBOX: WEBSOCKET ({boxes.length} obj)
            </span>
          </div>
        )}
      </div>

      <div className="rounded-lg bg-surface/40 border border-border/20 px-3 py-2.5 text-[11px] text-muted-foreground leading-relaxed">
        <p className="font-medium text-amber-400 mb-1">📌 如何測試模型？</p>
        <p>直接點選「Python YOLO 串流」，網頁會自動啟動背景的 <code>local_yolo_mjpeg.py</code> 與 <code>yolo26n.onnx</code> 進行偵測，不需手動開 Terminal 囉！</p>
      </div>
    </div>
  )
}
