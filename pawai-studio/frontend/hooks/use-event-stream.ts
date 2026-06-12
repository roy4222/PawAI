"use client";

import { useCallback, useEffect } from "react";
import { useWebSocket } from "@/hooks/use-websocket";
import { useEventStore } from "@/stores/event-store";
import { useStateStore } from "@/stores/state-store";
import type { NavControl, NavControlState } from "@/stores/state-store";
import { useLayoutManager } from "@/hooks/use-layout-manager";
import { normalizeObjectState } from "@/lib/object-event";
import type {
  PawAIEvent,
  FaceState,
  SpeechState,
  GestureState,
  PoseState,
  BrainState,
  BrainTraceEvent,
  PawAIBrainState,
  SkillPlan,
  SkillResult,
  SystemHealth,
  ConversationTracePayload,
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
  const appendConversationTrace = useStateStore((s) => s.appendConversationTrace);
  const appendBrainTrace = useStateStore((s) => s.appendBrainTrace);
  const updateSystemHealth = useStateStore((s) => s.updateSystemHealth);
  const updateObjectState = useStateStore((s) => s.updateObjectState);
  const updateTts = useStateStore((s) => s.updateTts);
  const appendTtsMessage = useStateStore((s) => s.appendTtsMessage);
  const updateCapability = useStateStore((s) => s.updateCapability);
  const updateNav = useStateStore((s) => s.updateNav);
  const setNavControl = useStateStore((s) => s.setNavControl);
  const setGestureToggleEnabled = useStateStore((s) => s.setGestureToggleEnabled);
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
          } else if (
            event.event_type === "conversation_trace" ||
            event.event_type === "conversation_trace_shadow"
          ) {
            appendConversationTrace(data as unknown as ConversationTracePayload);
          } else if (event.event_type === "trace") {
            // Evidence Center first slice (T2B-3): /brain/trace decision-chain
            // events — answers「為什麼沒反應」(gate + reason per decision_id).
            if ("decision_id" in data && "verdict" in data) {
              appendBrainTrace(data as unknown as BrainTraceEvent);
            }
          } else if (event.event_type === "gesture_enabled") {
            // Demo-recording P0 手勢開關廣播（gateway /api/gesture_enabled）。
            if (typeof data.enabled === "boolean") {
              setGestureToggleEnabled(data.enabled);
            }
          } else if ("executive_state" in data) {
            updateBrainState(toPawAIBrainState(data as unknown as LegacyBrainLike));
          }
          break;
        case "object": {
          const objectState = normalizeObjectState(data);
          if (objectState) {
            updateObjectState(objectState);
          }
          break;
        }
        case "tts":
          if ("text" in data) {
            // 既有 updateTts 維持（其他 panel 用 lastTtsText）
            updateTts(data.text as string);

            // P1-1b：append 到 ttsMessages 讓 ChatPanel 全部顯示
            appendTtsMessage({
              id: event.id || `tts-${Date.now()}`,
              text: data.text as string,
              timestamp: Date.now(),
              origin: (data.origin as string) || "tts",
              source: data.source as string | undefined,
            });
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
        case "nav":
          // Task A nav panel — gateway sends short event_types pose / reactive_stop / paused.
          if (event.event_type === "pose") {
            if (typeof data.x === "number" && typeof data.y === "number") {
              updateNav({
                pose: {
                  x: data.x as number,
                  y: data.y as number,
                  yaw: typeof data.yaw === "number" ? (data.yaw as number) : 0,
                },
              });
            }
          } else if (event.event_type === "reactive_stop") {
            const z = data.zone;
            updateNav({
              reactiveStop: {
                zone: z === "danger" || z === "slow" ? z : "clear",
                front_distance_m:
                  typeof data.obstacle_distance === "number"
                    ? (data.obstacle_distance as number)
                    : null,
                nav_paused: Boolean(data.nav_paused),
              },
            });
          } else if (event.event_type === "paused") {
            updateNav({ paused: Boolean(data.paused) });
          } else if (event.event_type === "nav_control") {
            // Operator nav-driving state machine (demo S1 "move to scene").
            const s = data.state;
            const validState: NavControlState =
              s === "running" || s === "paused_confirm" || s === "done"
                ? s
                : "idle";
            const control: NavControl = {
              state: validState,
              target_m: typeof data.target_m === "number" ? (data.target_m as number) : 0,
              remaining_m:
                typeof data.remaining_m === "number" ? (data.remaining_m as number) : 0,
              reason: typeof data.reason === "string" ? (data.reason as string) : undefined,
            };
            setNavControl(control);
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
      appendConversationTrace,
      appendBrainTrace,
      updateSystemHealth,
      updateObjectState,
      updateTts,
      appendTtsMessage,
      updateCapability,
      updateNav,
      setNavControl,
      setGestureToggleEnabled,
      evaluateEvent,
    ]
  );

  const { isConnected } = useWebSocket({ onMessage });

  // P1-2: F5 hybrid auto-reset (dev-only — off by default in production)
  // beforeunload sets a sessionStorage flag so that when the page reconnects
  // within 5s we know it was a refresh and can auto-reset context.
  useEffect(() => {
    const handleBeforeUnload = () => {
      sessionStorage.setItem("paw_refresh_at", Date.now().toString());
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, []);

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
