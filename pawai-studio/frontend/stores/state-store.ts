"use client";

import { create } from "zustand";
import type {
  FaceState,
  SpeechState,
  GestureState,
  PoseState,
  BrainState,
  SystemHealth,
  ObjectState,
} from "@/contracts/types";

interface StateStore {
  faceState: FaceState | null;
  speechState: SpeechState | null;
  gestureState: GestureState | null;
  poseState: PoseState | null;
  brainState: BrainState | null;
  systemHealth: SystemHealth | null;
  objectState: ObjectState | null;

  updateFaceState: (state: FaceState) => void;
  updateSpeechState: (state: SpeechState) => void;
  updateGestureState: (state: GestureState) => void;
  updatePoseState: (state: PoseState) => void;
  updateBrainState: (state: BrainState) => void;
  updateSystemHealth: (state: SystemHealth) => void;
  updateObjectState: (state: ObjectState) => void;
}

export const useStateStore = create<StateStore>((set) => ({
  faceState: null,
  speechState: null,
  gestureState: null,
  poseState: null,
  brainState: null,
  systemHealth: null,
  objectState: null,

  updateFaceState: (state) => set({ faceState: state }),
  updateSpeechState: (state) => set({ speechState: state }),
  updateGestureState: (state) => set({ gestureState: state }),
  updatePoseState: (state) => set({ poseState: state }),
  updateBrainState: (state) => set({ brainState: state }),
  updateSystemHealth: (state) => set({ systemHealth: state }),
  updateObjectState: (state) => set({ objectState: state }),
}));
