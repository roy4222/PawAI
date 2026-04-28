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
} from "@/contracts/types";

interface StateStore {
  faceState: FaceState | null;
  speechState: SpeechState | null;
  gestureState: GestureState | null;
  poseState: PoseState | null;
  brainState: BrainState | null;
  brainProposals: SkillPlan[];
  brainResults: SkillResult[];
  systemHealth: SystemHealth | null;
  objectState: ObjectState | null;
  lastTtsText: string | null;
  lastTtsAt: number | null;

  updateFaceState: (state: FaceState) => void;
  updateSpeechState: (state: SpeechState) => void;
  updateGestureState: (state: GestureState) => void;
  updatePoseState: (state: PoseState) => void;
  updateBrainState: (state: BrainState) => void;
  appendBrainProposal: (proposal: SkillPlan) => void;
  appendBrainResult: (result: SkillResult) => void;
  updateSystemHealth: (state: SystemHealth) => void;
  updateObjectState: (state: ObjectState) => void;
  updateTts: (text: string) => void;
}

export const useStateStore = create<StateStore>((set) => ({
  faceState: null,
  speechState: null,
  gestureState: null,
  poseState: null,
  brainState: null,
  brainProposals: [],
  brainResults: [],
  systemHealth: null,
  objectState: null,
  lastTtsText: null,
  lastTtsAt: null,

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
  updateSystemHealth: (state) => set({ systemHealth: state }),
  updateObjectState: (state) => set({ objectState: state }),
  updateTts: (text) => set({ lastTtsText: text, lastTtsAt: Date.now() }),
}));
