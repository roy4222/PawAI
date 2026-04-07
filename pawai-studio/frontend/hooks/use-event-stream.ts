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
  const updateSystemHealth = useStateStore((s) => s.updateSystemHealth);
  const updateObjectState = useStateStore((s) => s.updateObjectState);
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
          if ("executive_state" in data) {
            updateBrainState(data as unknown as BrainState);
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
      updateSystemHealth,
      updateObjectState,
      evaluateEvent,
    ]
  );

  const { isConnected } = useWebSocket({ onMessage });

  return { isConnected };
}
