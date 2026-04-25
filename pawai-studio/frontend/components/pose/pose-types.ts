export type PoseName =
  | 'standing'
  | 'sitting'
  | 'crouching'
  | 'bending'
  | 'hands_on_hips'
  | 'kneeling_one_knee'
  | 'fallen'
  | 'unknown'

export interface PoseInferenceDebug {
  hip?: number | null
  knee?: number | null
  trunk?: number | null
  elbow_l?: number | null
  elbow_r?: number | null
}

export interface PoseInferenceResult {
  id: string
  timestamp: string
  pose: string
  confidence: number
  track_id: number | null
  debug?: PoseInferenceDebug
  annotated_image_base64?: string | null
  source: 'python_inference'
}

export interface PoseFramePayload {
  frame_id: string
  timestamp: string
  image_base64: string
  width: number
  height: number
}

export interface PoseInferenceConfig {
  endpoint: string
  captureIntervalMs: number
  decisionIntervalMs: number
  jpegQuality: number
  maxImageWidth: number
  requestTimeoutMs: number
}

export const DEFAULT_POSE_INFERENCE_CONFIG: PoseInferenceConfig = {
  endpoint: process.env.NEXT_PUBLIC_POSE_INFER_ENDPOINT ?? 'http://127.0.0.1:8765/pose/infer',
  captureIntervalMs: 150,
  decisionIntervalMs: 1000,
  jpegQuality: 0.95,
  maxImageWidth: 1280,
  requestTimeoutMs: 2500,
}
