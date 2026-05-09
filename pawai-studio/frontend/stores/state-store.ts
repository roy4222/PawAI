"use client";

// Rate-limit config for spontaneous TTS (P1-1 spam scroll prevention)
// Bypass: chat_reply (pending user reply) / skill_say (active skill SAY) / say_canned (LLM/OpenRouter fallback)
const RATE_LIMIT_BYPASS = new Set(["chat_reply", "skill_say", "say_canned"]);
const RATE_LIMIT_WINDOW_MS = 5000;

import { create } from "zustand";
import type {
  FaceState,
  SpeechState,
  GestureState,
  PoseState,
  BrainState,
  SkillPlan,
  SkillResult,
  SystemHealth,
  ObjectState,
  CapabilityState,
  CapabilityTriState,
  PlanMode,
  ConversationTracePayload,
} from "@/contracts/types";

export interface TtsMessage {
  id: string;
  text: string;
  timestamp: number;
  origin: string;
  source?: string; // skill_say | chat_reply | say_canned | undefined
}

interface StateStore {
  faceState: FaceState | null;
  speechState: SpeechState | null;
  gestureState: GestureState | null;
  poseState: PoseState | null;
  brainState: BrainState | null;
  brainProposals: SkillPlan[];
  brainResults: SkillResult[];
  conversationTraces: ConversationTracePayload[];
  systemHealth: SystemHealth | null;
  objectState: ObjectState | null;
  lastTtsText: string | null;
  lastTtsAt: number | null;
  ttsMessages: TtsMessage[];
  capability: CapabilityState;
  planMode: PlanMode;

  updateFaceState: (state: FaceState) => void;
  updateSpeechState: (state: SpeechState) => void;
  updateGestureState: (state: GestureState) => void;
  updatePoseState: (state: PoseState) => void;
  updateBrainState: (state: BrainState) => void;
  appendBrainProposal: (proposal: SkillPlan) => void;
  appendBrainResult: (result: SkillResult) => void;
  appendConversationTrace: (trace: ConversationTracePayload) => void;
  updateSystemHealth: (state: SystemHealth) => void;
  updateObjectState: (state: ObjectState) => void;
  updateTts: (text: string) => void;
  appendTtsMessage: (msg: TtsMessage) => void;
  updateCapability: (name: keyof CapabilityState, value: CapabilityTriState) => void;
  setPlanMode: (mode: PlanMode) => void;
}

export const useStateStore = create<StateStore>((set) => ({
  faceState: null,
  speechState: null,
  gestureState: null,
  poseState: null,
  brainState: null,
  brainProposals: [],
  brainResults: [],
  conversationTraces: [],
  systemHealth: null,
  objectState: null,
  lastTtsText: null,
  lastTtsAt: null,
  ttsMessages: [],
  capability: { nav_ready: "unknown", depth_clear: "unknown" },
  planMode: "A",

  updateFaceState: (state) => set({ faceState: state }),
  updateSpeechState: (state) => set({ speechState: state }),
  updateGestureState: (state) => set({ gestureState: state }),
  updatePoseState: (state) => set({ poseState: state }),
  updateBrainState: (state) => set({ brainState: state }),
  appendBrainProposal: (proposal) =>
    set((state) => ({
      brainProposals: [proposal, ...state.brainProposals].slice(0, 50),
    })),
  appendBrainResult: (result) =>
    set((state) => ({
      brainResults: [result, ...state.brainResults].slice(0, 200),
    })),
  appendConversationTrace: (trace) =>
    set((state) => ({
      conversationTraces: [trace, ...state.conversationTraces].slice(0, 50),
    })),
  updateSystemHealth: (state) => set({ systemHealth: state }),
  updateObjectState: (state) => set({ objectState: state }),
  updateTts: (text) => set({ lastTtsText: text, lastTtsAt: Date.now() }),
  appendTtsMessage: (msg) =>
    set((state) => {
      // dedup by id
      if (state.ttsMessages.some((m) => m.id === msg.id)) {
        return state;
      }

      // rate-limit: spontaneous (no source or unspecified spontaneous source)
      // bypass: chat_reply (pending reply) / skill_say (active skill SAY)
      const isBypass = msg.source != null && RATE_LIMIT_BYPASS.has(msg.source);
      if (!isBypass) {
        const sourceKey = msg.source ?? "spontaneous";
        // reverse loop: 找最後一個同 source 的 message
        let recentSame: TtsMessage | undefined;
        for (let i = state.ttsMessages.length - 1; i >= 0; i--) {
          const m = state.ttsMessages[i];
          if ((m.source ?? "spontaneous") === sourceKey) {
            recentSame = m;
            break;
          }
        }
        if (recentSame != null && msg.timestamp - recentSame.timestamp < RATE_LIMIT_WINDOW_MS) {
          // silently drop
          return state;
        }
      }

      // ring buffer max 200
      const next = [...state.ttsMessages, msg];
      if (next.length > 200) {
        return { ttsMessages: next.slice(next.length - 200) };
      }
      return { ttsMessages: next };
    }),
  updateCapability: (name, value) =>
    set((state) => ({ capability: { ...state.capability, [name]: value } })),
  setPlanMode: (mode) => set({ planMode: mode }),
}));
