"use client";

import { create } from "zustand";
import type { LayoutPreset, PanelId } from "@/contracts/types";

// Panels active per preset
const PRESET_PANELS: Record<LayoutPreset, PanelId[]> = {
  chat_only: ["chat"],
  chat_camera: ["chat", "camera"],
  chat_speech: ["chat", "speech"],
  chat_camera_speech: ["chat", "camera", "speech"],
  chat_gesture: ["chat", "gesture"],
  chat_pose: ["chat", "pose"],
  chat_full: ["chat", "face", "speech", "gesture", "pose", "object"],
  demo: ["chat", "face", "speech", "gesture", "pose", "object"],
};

const MAX_PANELS = 4;

// Priority: lower number = higher priority (never evict)
const PANEL_PRIORITY: Record<PanelId, number> = {
  chat: 1,
  camera: 2,
  brain: 3,
  speech: 4,
  timeline: 5,
  health: 6,
  skills: 7,
  gesture: 8,
  pose: 8,
  face: 9,
  object: 10,
};

interface LayoutStore {
  currentPreset: LayoutPreset;
  activePanels: Set<PanelId>;
  dismissedPanels: Set<PanelId>;

  showPanel: (id: PanelId) => void;
  hidePanel: (id: PanelId) => void;
  dismissPanel: (id: PanelId) => void;
  resetDismissed: () => void;
  setPreset: (preset: LayoutPreset) => void;
}

function evictIfNeeded(panels: Set<PanelId>): Set<PanelId> {
  if (panels.size < MAX_PANELS) return panels;

  // Find the lowest-priority panel (highest priority number) to evict,
  // excluding chat which is always kept.
  let evictCandidate: PanelId | null = null;
  let worstPriority = -1;

  for (const id of panels) {
    if (id === "chat") continue;
    const p = PANEL_PRIORITY[id] ?? 99;
    if (p > worstPriority) {
      worstPriority = p;
      evictCandidate = id;
    }
  }

  if (evictCandidate === null) return panels;

  const next = new Set(panels);
  next.delete(evictCandidate);
  return next;
}

export const useLayoutStore = create<LayoutStore>((set) => ({
  currentPreset: "chat_full",
  activePanels: new Set<PanelId>(PRESET_PANELS["chat_full"]),
  dismissedPanels: new Set<PanelId>(),

  showPanel: (id) => {
    set((state) => {
      if (state.activePanels.has(id)) return state;
      const panels = evictIfNeeded(new Set(state.activePanels));
      panels.add(id);
      return { activePanels: panels };
    });
  },

  hidePanel: (id) => {
    set((state) => {
      if (!state.activePanels.has(id)) return state;
      const panels = new Set(state.activePanels);
      panels.delete(id);
      return { activePanels: panels };
    });
  },

  dismissPanel: (id) => {
    set((state) => {
      const activePanels = new Set(state.activePanels);
      activePanels.delete(id);
      const dismissedPanels = new Set(state.dismissedPanels);
      dismissedPanels.add(id);
      return { activePanels, dismissedPanels };
    });
  },

  resetDismissed: () => {
    set({ dismissedPanels: new Set<PanelId>() });
  },

  setPreset: (preset) => {
    set({
      currentPreset: preset,
      activePanels: new Set<PanelId>(PRESET_PANELS[preset]),
    });
  },
}));
