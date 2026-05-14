import type { PoseFramePayload, PoseInferenceResult } from './pose-types'

function clamp01(value: number): number {
  if (Number.isNaN(value)) return 0
  return Math.max(0, Math.min(1, value))
}

function toNumberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function toPoseString(payload: Record<string, unknown>): string {
  const raw = payload.pose ?? payload.current_pose ?? payload.label ?? payload.class_name ?? 'unknown'
  return typeof raw === 'string' && raw.trim() ? raw : 'unknown'
}

function toTrackId(payload: Record<string, unknown>): number | null {
  const value = payload.track_id
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  return null
}

export function coercePoseInferenceResult(payload: unknown, fallbackId: string): PoseInferenceResult {
  const obj = (payload ?? {}) as Record<string, unknown>
  const confidenceRaw = obj.confidence
  const confidence = typeof confidenceRaw === 'number' ? clamp01(confidenceRaw) : 0
  const annotated = typeof obj.annotated_image_base64 === 'string' ? obj.annotated_image_base64 : null

  return {
    id: typeof obj.id === 'string' && obj.id ? obj.id : fallbackId,
    timestamp:
      typeof obj.timestamp === 'string' && obj.timestamp
        ? obj.timestamp
        : new Date().toISOString(),
    pose: toPoseString(obj),
    confidence,
    track_id: toTrackId(obj),
    annotated_image_base64: annotated,
    debug: typeof obj.debug === 'object' && obj.debug !== null
      ? {
          hip: toNumberOrNull((obj.debug as Record<string, unknown>).hip),
          knee: toNumberOrNull((obj.debug as Record<string, unknown>).knee),
          trunk: toNumberOrNull((obj.debug as Record<string, unknown>).trunk),
          elbow_l: toNumberOrNull((obj.debug as Record<string, unknown>).elbow_l),
          elbow_r: toNumberOrNull((obj.debug as Record<string, unknown>).elbow_r),
        }
      : undefined,
    source: 'python_inference',
  }
}

export async function inferPoseByHttp(
  endpoint: string,
  frame: PoseFramePayload,
  timeoutMs: number
): Promise<PoseInferenceResult> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)

  try {
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(frame),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`Pose infer API failed (${response.status})`)
    }

    const payload = await response.json()
    return coercePoseInferenceResult(payload, frame.frame_id)
  } finally {
    clearTimeout(timeout)
  }
}
