"use client";

import { useCallback } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { useEventStore } from "@/stores/event-store";
import { useStateStore } from "@/stores/state-store";
import { useLayoutManager } from "@/hooks/use-layout-manager";
import type {
  PawAIEvent,
  FaceState,
  SpeechState,
  GestureState,
  PoseState,
  BrainState,
  PawAIBrainState,
  SkillPlan,
  SkillResult,
  SystemHealth,
  ObjectState,
} from "@/contracts/types";

interface UseEventStreamResult {
  isConnected: boolean;
}

export function useEventStream(): UseEventStreamResult {
  const addEvent = useEventStore((s) => s.addEvent);
  const updateFaceState = useStateStore((s) => s.updateFaceState);
  const updateSpeechState = useStateStore((s) => s.updateSpeechState);
  const updateGestureState = useStateStore((s) => s.updateGestureState);
  const updatePoseState = useStateStore((s) => s.updatePoseState);
  const updateBrainState = useStateStore((s) => s.updateBrainState);
  const appendBrainProposal = useStateStore((s) => s.appendBrainProposal);
  const appendBrainResult = useStateStore((s) => s.appendBrainResult);
  const updateSystemHealth = useStateStore((s) => s.updateSystemHealth);
  const updateObjectState = useStateStore((s) => s.updateObjectState);
  const updateTts = useStateStore((s) => s.updateTts);
  const updateCapability = useStateStore((s) => s.updateCapability);
  const { evaluateEvent } = useLayoutManager();

  const onMessage = useCallback(
    (event: PawAIEvent) => {
      // 1. Persist to event history
      addEvent(event);

      // 2. Update state snapshot if event carries state data
      const data = event.data as Record<string, unknown>;

      switch (event.source) {
        case "face":
          if ("face_count" in data) {
            updateFaceState(data as unknown as FaceState);
          }
          break;
        case "speech":
          if ("phase" in data) {
            updateSpeechState(data as unknown as SpeechState);
          }
          break;
        case "gesture":
          if ("status" in data) {
            updateGestureState(data as unknown as GestureState);
          }
          break;
        case "pose":
          if ("current_pose" in data || "status" in data) {
            updatePoseState(data as unknown as PoseState);
          }
          break;
        case "brain":
          if (event.event_type === "state") {
            updateBrainState(data as unknown as PawAIBrainState);
          } else if (event.event_type === "proposal") {
            appendBrainProposal(data as unknown as SkillPlan);
          } else if (event.event_type === "skill_result") {
            appendBrainResult(data as unknown as SkillResult);
          } else if ("executive_state" in data) {
            updateBrainState(toPawAIBrainState(data as unknown as LegacyBrainLike));
          }
          break;
        case "object": {
          // Normalize: ROS2 sends `objects[]`, frontend state expects `detected_objects`
          const objData = { ...data } as Record<string, unknown>;
          if ("objects" in objData && !("detected_objects" in objData)) {
            objData.detected_objects = objData.objects;
          }
          if ("detected_objects" in objData || "objects" in objData) {
            const arr = (objData.detected_objects ?? objData.objects ?? []) as unknown[];
            objData.active = arr.length > 0;
            objData.status = arr.length > 0 ? "active" : "inactive";
            updateObjectState(objData as unknown as ObjectState);
          }
          break;
        }
        case "tts":
          if ("text" in data) {
            updateTts(data.text as string);
          }
          break;
        case "capability":
          // Tri-state capability gate (Phase B B5b).
          if ("name" in data && "tri_state" in data) {
            const name = data.name as "nav_ready" | "depth_clear";
            const tri = data.tri_state as "true" | "false" | "unknown";
            updateCapability(name, tri);
          }
          break;
        case "system":
          if ("jetson" in data) {
            updateSystemHealth(data as unknown as SystemHealth);
          }
          break;
        default:
          break;
      }

      // 3. Layout orchestration
      evaluateEvent(event);
    },
    [
      addEvent,
      updateFaceState,
      updateSpeechState,
      updateGestureState,
      updatePoseState,
      updateBrainState,
      appendBrainProposal,
      appendBrainResult,
      updateSystemHealth,
      updateObjectState,
      updateTts,
      updateCapability,
      evaluateEvent,
    ]
  );

  const { isConnected } = useWebSocket({ onMessage });

  return { isConnected };
}

interface LegacyBrainLike {
  stamp?: number;
  executive_state?: string;
  selected_skill?: string | null;
  last_decision_reason?: string;
}

function toPawAIBrainState(data: LegacyBrainLike): BrainState {
  const modeMap: Record<string, BrainState["mode"]> = {
    idle: "idle",
    observing: "idle",
    deciding: "skill",
    executing: "skill",
    speaking: "chat",
  };
  return {
    timestamp: data.stamp ?? Date.now() / 1000,
    mode: modeMap[data.executive_state ?? "idle"] ?? "idle",
    active_plan: data.selected_skill
      ? {
          plan_id: "legacy",
          selected_skill: data.selected_skill,
          step_index: 0,
          step_total: null,
          started_at: data.stamp ?? Date.now() / 1000,
          priority_class: 3,
        }
      : null,
    active_step: null,
    fallback_active: false,
    safety_flags: {
      obstacle: false,
      emergency: false,
      fallen: false,
      tts_playing: false,
      nav_safe: true,
    },
    cooldowns: {},
    last_plans: data.selected_skill
      ? [
          {
            plan_id: "legacy",
            selected_skill: data.selected_skill,
            source: "legacy",
            priority: 3,
            accepted: true,
            reason: data.last_decision_reason ?? "legacy brain event",
            created_at: data.stamp ?? Date.now() / 1000,
          },
        ]
      : [],
  };
}
