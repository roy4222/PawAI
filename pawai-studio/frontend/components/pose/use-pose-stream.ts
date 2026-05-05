import { RefObject, useEffect, useMemo, useRef, useState } from 'react'
import { DEFAULT_POSE_INFERENCE_CONFIG, type PoseInferenceConfig, type PoseFramePayload, type PoseInferenceResult } from './pose-types'
import { inferPoseByHttp } from './pose-client'

interface UsePoseStreamOptions {
  enabled: boolean
  videoRef: RefObject<HTMLVideoElement | null>
  config?: Partial<PoseInferenceConfig>
  maxHistory?: number
}

interface PoseStreamState {
  cameraReady: boolean
  cameraError: string | null
  inferenceError: string | null
  isInferring: boolean
  annotatedFrameDataUrl: string | null
  lastResult: PoseInferenceResult | null
  history: PoseInferenceResult[]
}

function makeId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }

  return `pose-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function pickCaptureSize(
  videoWidth: number,
  videoHeight: number,
  maxImageWidth: number
): { width: number; height: number } {
  if (videoWidth <= maxImageWidth) {
    return { width: videoWidth, height: videoHeight }
  }

  const ratio = maxImageWidth / videoWidth
  return {
    width: Math.round(videoWidth * ratio),
    height: Math.round(videoHeight * ratio),
  }
}

function frameFromCanvas(canvas: HTMLCanvasElement, quality: number): string | null {
  const dataUrl = canvas.toDataURL('image/jpeg', quality)
  const marker = 'base64,'
  const idx = dataUrl.indexOf(marker)
  if (idx === -1) return null
  return dataUrl.slice(idx + marker.length)
}

export function usePoseStream(options: UsePoseStreamOptions): PoseStreamState {
  const { enabled, videoRef, maxHistory = 200 } = options

  const config = useMemo(
    () => ({
      ...DEFAULT_POSE_INFERENCE_CONFIG,
      ...options.config,
    }),
    [options.config]
  )

  const [cameraReady, setCameraReady] = useState(false)
  const [cameraError, setCameraError] = useState<string | null>(null)
  const [inferenceError, setInferenceError] = useState<string | null>(null)
  const [isInferring, setIsInferring] = useState(false)
  const [annotatedFrameDataUrl, setAnnotatedFrameDataUrl] = useState<string | null>(null)
  const [lastResult, setLastResult] = useState<PoseInferenceResult | null>(null)
  const [history, setHistory] = useState<PoseInferenceResult[]>([])

  const localStreamRef = useRef<MediaStream | null>(null)
  const inFlightRef = useRef(false)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const lastDecisionUpdateAtRef = useRef(0)

  useEffect(() => {
    const stopLocalCamera = () => {
      localStreamRef.current?.getTracks().forEach((track) => track.stop())
      localStreamRef.current = null
      if (videoRef.current) {
        videoRef.current.srcObject = null
      }
      setCameraReady(false)
    }

    if (!enabled) {
      // Intentional state reset when camera toggles off. Calling setState
      // synchronously here is the cleanup contract — the alternative
      // (derived state) would re-run getUserMedia teardown on every render.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCameraError(null)
      setInferenceError(null)
      setAnnotatedFrameDataUrl(null)
      stopLocalCamera()
      return
    }

    let cancelled = false

    const startLocalCamera = async () => {
      try {
        setCameraError(null)

        if (
          typeof navigator === 'undefined' ||
          !navigator.mediaDevices ||
          typeof navigator.mediaDevices.getUserMedia !== 'function'
        ) {
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
  }, [enabled, videoRef])

  useEffect(() => {
    if (!enabled || !cameraReady) return

    const timer = window.setInterval(() => {
      if (document.hidden) return
      if (inFlightRef.current) return

      const video = videoRef.current
      if (!video) return
      if (video.videoWidth <= 0 || video.videoHeight <= 0) return

      if (!canvasRef.current) {
        canvasRef.current = document.createElement('canvas')
      }

      const canvas = canvasRef.current
      const size = pickCaptureSize(video.videoWidth, video.videoHeight, config.maxImageWidth)
      canvas.width = size.width
      canvas.height = size.height

      const ctx = canvas.getContext('2d', { alpha: false })
      if (!ctx) return

      ctx.drawImage(video, 0, 0, size.width, size.height)
      const imageBase64 = frameFromCanvas(canvas, config.jpegQuality)
      if (!imageBase64) return

      const frame: PoseFramePayload = {
        frame_id: makeId(),
        timestamp: new Date().toISOString(),
        image_base64: imageBase64,
        width: size.width,
        height: size.height,
      }

      inFlightRef.current = true
      setIsInferring(true)

      void inferPoseByHttp(config.endpoint, frame, config.requestTimeoutMs)
        .then((result) => {
          setInferenceError(null)
          setAnnotatedFrameDataUrl(
            result.annotated_image_base64
              ? `data:image/jpeg;base64,${result.annotated_image_base64}`
              : null
          )

          const now = Date.now()
          const shouldUpdateDecision =
            !lastResult ||
            now - lastDecisionUpdateAtRef.current >= config.decisionIntervalMs

          if (shouldUpdateDecision) {
            lastDecisionUpdateAtRef.current = now
            setLastResult(result)
            setHistory((prev) => [result, ...prev].slice(0, maxHistory))
          }
        })
        .catch((err) => {
          const msg = err instanceof Error ? err.message : '姿勢推論失敗'
          setInferenceError(msg)
        })
        .finally(() => {
          inFlightRef.current = false
          setIsInferring(false)
        })
    }, config.captureIntervalMs)

    return () => {
      window.clearInterval(timer)
      inFlightRef.current = false
      setIsInferring(false)
    }
  }, [cameraReady, config, enabled, lastResult, maxHistory, videoRef])

  return {
    cameraReady,
    cameraError,
    inferenceError,
    isInferring,
    annotatedFrameDataUrl,
    lastResult,
    history,
  }
}
