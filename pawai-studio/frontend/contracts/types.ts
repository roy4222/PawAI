/**
 * PawAI Studio TypeScript Contracts
 *
 * 真相來源：docs/pawai-brain/studio/specs/event-schema.md
 * 本檔案是 event-schema.md 的 TypeScript 鏡像，若有衝突以 event-schema.md 為準。
 */

// ══════════════════════════════════════════════════════════════════
// Event 信封
// ══════════════════════════════════════════════════════════════════

export interface PawAIEvent {
  id: string;
  timestamp: string; // ISO 8601
  source: string;
  event_type: string;
  data: Record<string, unknown>;
}

// ══════════════════════════════════════════════════════════════════
// Face
// ══════════════════════════════════════════════════════════════════

export interface FaceIdentityEvent extends PawAIEvent {
  source: "face";
  event_type:
    | "track_started"
    | "identity_stable"
    | "identity_changed"
    | "track_lost";
  data: {
    track_id: number;
    stable_name: string;
    sim: number;
    distance_m: number | null;
  };
}

export interface FaceTrack {
  track_id: number;
  stable_name: string;
  sim: number;
  distance_m: number | null;
  bbox: [number, number, number, number];
  mode: "stable" | "hold";
}

export interface FaceState {
  stamp: number;
  face_count: number;
  tracks: FaceTrack[];
}

// ══════════════════════════════════════════════════════════════════
// Speech
// ══════════════════════════════════════════════════════════════════

export interface SpeechIntentEvent extends PawAIEvent {
  source: "speech";
  event_type: "intent_recognized" | "asr_result" | "wake_word";
  data: {
    intent?: string;
    text: string;
    confidence: number;
    provider: string;
  };
}

export type SpeechPhase =
  | "idle_wakeword"
  | "wake_ack"
  | "loading_local_stack"
  | "listening"
  | "transcribing"
  | "local_asr_done"
  | "cloud_brain_pending"
  | "speaking"
  | "keep_alive"
  | "unloading";

export interface SpeechState {
  stamp: number;
  phase: SpeechPhase;
  last_asr_text: string;
  last_intent: string;
  last_tts_text: string;
  models_loaded: string[];
}

// ══════════════════════════════════════════════════════════════════
// Gesture
// ══════════════════════════════════════════════════════════════════

export interface GestureEvent extends PawAIEvent {
  source: "gesture";
  event_type: "gesture_detected";
  data: {
    gesture: string;
    confidence: number;
    hand: "left" | "right";
  };
}

export interface GestureState {
  stamp: number;
  active: boolean;
  current_gesture: string | null;
  confidence: number;
  hand: "left" | "right" | null;
  status: "active" | "inactive" | "loading";
}

// ══════════════════════════════════════════════════════════════════
// Pose
// ══════════════════════════════════════════════════════════════════

export interface PoseEvent extends PawAIEvent {
  source: "pose";
  event_type: "pose_detected";
  data: {
    pose: string;
    confidence: number;
    track_id: number;
  };
}

export interface PoseState {
  stamp: number;
  active: boolean;
  current_pose: string | null;
  confidence: number;
  track_id: number | null;
  status: "active" | "inactive" | "loading" | "error";
}

// ══════════════════════════════════════════════════════════════════
// Object
// ══════════════════════════════════════════════════════════════════

export interface ObjectDetection {
  class_name: string;
  /** Optional COCO class id (5/5 PR #40 port — not all backends emit). */
  class_id?: number;
  confidence: number;
  bbox: [number, number, number, number];
  /**
   * Optional HSV color label from object_perception_node post-NMS step
   * (5/5 sprint B4-4). Possible values include "red" / "yellow" / "blue" /
   * "green" / "Unknown". Absent for backends that haven't shipped color yet.
   */
  color?: string;
}

export interface ObjectEvent extends PawAIEvent {
  source: "object";
  event_type: "object_detected";
  data: {
    /** ROS2 stamp (seconds since epoch). */
    stamp?: number;
    /** Whether any detection in this frame. */
    active?: boolean;
    /** State machine status, derived if absent. */
    status?: "active" | "inactive" | "loading";
    /**
     * ROS2 emits `objects[]`; some legacy paths emit `detected_objects[]`.
     * Frontend `normalizeObjectState()` (lib/object-event.ts) merges them.
     */
    objects?: ObjectDetection[];
    detected_objects?: ObjectDetection[];
  };
}

export interface ObjectState {
  stamp: number;
  active: boolean;
  detected_objects: ObjectDetection[];
  status: "active" | "inactive" | "loading";
}

// ══════════════════════════════════════════════════════════════════
// Brain
// ══════════════════════════════════════════════════════════════════

export interface BrainEvent extends PawAIEvent {
  source: "brain";
  event_type:
    | "decision_made"
    | "skill_dispatched"
    | "skill_completed"
    | "fallback_triggered";
  data: {
    intent: string;
    selected_skill: string;
    reason: string;
    degradation_level: 0 | 1 | 2 | 3;
  };
}

export type ExecutorKind = "say" | "motion" | "nav";
export type PriorityClass = 0 | 1 | 2 | 3 | 4;
export type SkillResultStatus =
  | "accepted"
  | "started"
  | "step_started"
  | "step_success"
  | "step_failed"
  | "completed"
  | "aborted"
  | "blocked_by_safety";
export type BrainMode = "idle" | "chat" | "skill" | "sequence" | "alert" | "safety_stop";

export interface SkillStep {
  executor: ExecutorKind;
  args: Record<string, unknown>;
}

export interface SkillPlan {
  plan_id: string;
  selected_skill: string;
  steps: SkillStep[];
  reason: string;
  source: string;
  priority_class: PriorityClass;
  session_id?: string | null;
  created_at: number;
}

export interface SkillResult {
  plan_id: string;
  step_index: number | null;
  status: SkillResultStatus;
  detail: string;
  selected_skill: string;
  priority_class: PriorityClass;
  step_total: number;
  step_args?: Record<string, unknown>;
  timestamp: number;
}

export interface BrainActivePlan {
  plan_id: string;
  selected_skill: string;
  step_index: number;
  step_total: number | null;
  started_at: number;
  priority_class: PriorityClass;
}

export interface BrainSafetyFlags {
  obstacle: boolean;
  emergency: boolean;
  fallen: boolean;
  tts_playing: boolean;
  nav_safe: boolean;
}

export interface BrainPlanRecord {
  plan_id: string;
  selected_skill: string;
  source: string;
  priority: number;
  accepted: boolean;
  reason: string;
  created_at: number;
}

export interface PawAIBrainState {
  timestamp: number;
  mode: BrainMode;
  active_plan: BrainActivePlan | null;
  active_step: SkillStep | null;
  fallback_active: boolean;
  safety_flags: BrainSafetyFlags;
  cooldowns: Record<string, number>;
  last_plans: BrainPlanRecord[];
}

export interface SkillRequestBody {
  skill: string;
  args?: Record<string, unknown>;
  request_id?: string;
}

export interface TextInputBody {
  text: string;
  request_id?: string;
}

export interface LegacyBrainState {
  stamp: number;
  executive_state: "idle" | "observing" | "deciding" | "executing" | "speaking";
  current_intent: string | null;
  selected_skill: string | null;
  degradation_level: 0 | 1 | 2 | 3;
  active_tracks: number;
  cloud_connected: boolean;
  last_decision_reason: string;
}

export type BrainState = PawAIBrainState;

// ── Phase B B5b: Skill registry / Capability gates / Plan mode ─────

export type SkillBucket = "active" | "hidden" | "disabled" | "retired";

export interface SkillRegistryEntry {
  name: string;
  bucket: SkillBucket;
  static_enabled: boolean;
  enabled_when_blocked: boolean;
  priority_class: PriorityClass;
  cooldown_s: number;
  timeout_s: number;
  safety_requirements: string[];
  fallback_skill: string | null;
  requires_confirmation: boolean;
  risk_level: "low" | "medium" | "high";
  ui_style: "normal" | "alert" | "safety";
  description: string;
  args_schema: Record<string, unknown>;
  step_count: number;
}

export interface SkillRegistryResponse {
  ok: boolean;
  total: number;
  by_bucket: Record<SkillBucket, number>;
  skills: SkillRegistryEntry[];
}

// Tri-state — "true" / "false" = explicit Bool received; "unknown" = no
// /capability/* message has arrived yet.
export type CapabilityTriState = "true" | "false" | "unknown";

export interface CapabilityState {
  nav_ready: CapabilityTriState;
  depth_clear: CapabilityTriState;
}

export type PlanMode = "A" | "B";

// ══════════════════════════════════════════════════════════════════
// System
// ══════════════════════════════════════════════════════════════════

export interface SystemEvent extends PawAIEvent {
  source: "system";
  event_type: "module_online" | "module_offline" | "degradation_change" | "error";
  data: {
    module: string;
    message: string;
    level: "info" | "warning" | "error";
  };
}

export interface ModuleHealth {
  name: string;
  status: "active" | "inactive" | "loading" | "error";
  latency_ms: number | null;
  last_heartbeat: number;
}

export interface SystemHealth {
  stamp: number;
  jetson: {
    cpu_percent: number;
    gpu_percent: number;
    ram_used_mb: number;
    ram_total_mb: number;
    temperature_c: number;
  };
  modules: ModuleHealth[];
}

// ══════════════════════════════════════════════════════════════════
// Commands
// ══════════════════════════════════════════════════════════════════

export interface SkillCommand {
  command_type: "skill";
  skill_id: string;
  priority: 0 | 1;
  source: "studio_button" | "studio_chat" | "brain";
}

export interface ChatCommand {
  command_type: "chat";
  text: string;
  session_id: string;
}

export interface MockTrigger {
  event_source: string;
  event_type: string;
  data: Record<string, unknown>;
}

// ══════════════════════════════════════════════════════════════════
// Layout
// ══════════════════════════════════════════════════════════════════

export type LayoutPreset =
  | "chat_only"
  | "chat_camera"
  | "chat_speech"
  | "chat_camera_speech"
  | "chat_gesture"
  | "chat_pose"
  | "chat_full"
  | "demo";

export type PanelId =
  | "chat"
  | "camera"
  | "face"
  | "speech"
  | "brain"
  | "timeline"
  | "health"
  | "skills"
  | "gesture"
  | "pose"
  | "object";

export type PanelPosition = "main" | "sidebar" | "bottom" | "overlay";
