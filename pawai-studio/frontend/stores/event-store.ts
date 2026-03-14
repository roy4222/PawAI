"use client";

import { create } from "zustand";
import type { PawAIEvent } from "@/contracts/types";

const MAX_EVENTS = 200;

interface EventStore {
  events: PawAIEvent[];
  addEvent: (event: PawAIEvent) => void;
  getEventsBySource: (source: string) => PawAIEvent[];
  clearEvents: () => void;
}

export const useEventStore = create<EventStore>((set, get) => ({
  events: [],

  addEvent: (event) => {
    set((state) => {
      const updated = [event, ...state.events];
      return { events: updated.length > MAX_EVENTS ? updated.slice(0, MAX_EVENTS) : updated };
    });
  },

  getEventsBySource: (source) => {
    return get().events.filter((e) => e.source === source);
  },

  clearEvents: () => {
    set({ events: [] });
  },
}));
