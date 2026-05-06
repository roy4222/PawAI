"use client";

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
  updateCapability: (name, value) =>
    set((state) => ({ capability: { ...state.capability, [name]: value } })),
  setPlanMode: (mode) => set({ planMode: mode }),
}));
