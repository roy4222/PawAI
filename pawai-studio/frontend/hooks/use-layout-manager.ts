"use client";

import { useCallback, useRef } from "react";
import { useLayoutStore } from "@/stores/layout-store";
import type { PawAIEvent, PanelId } from "@/contracts/types";

const HIDE_DELAY_MS = 5000;

// Critical events bypass the dismissed-panels filter
function isCriticalEvent(event: PawAIEvent): boolean {
  if (event.source === "system") {
    const et = event.event_type;
    if (et === "error" || et === "degradation_change") return true;
  }
  if (event.source === "pose" && event.event_type === "pose_detected") {
    const data = event.data as Record<string, unknown>;
    if (data.pose === "fallen") return true;
  }
  return false;
}

interface UseLayoutManagerResult {
  evaluateEvent: (event: PawAIEvent) => void;
}

export function useLayoutManager(): UseLayoutManagerResult {
  const showPanel = useLayoutStore((s) => s.showPanel);
  const hidePanel = useLayoutStore((s) => s.hidePanel);
  const dismissedPanels = useLayoutStore((s) => s.dismissedPanels);

  // Track pending hide timers so we can cancel them on re-appearance
  const hideTimers = useRef<Map<PanelId, ReturnType<typeof setTimeout>>>(new Map());

  const scheduleHide = useCallback(
    (id: PanelId, delayMs: number) => {
      const existing = hideTimers.current.get(id);
      if (existing !== undefined) clearTimeout(existing);
      const timer = setTimeout(() => {
        hideTimers.current.delete(id);
        hidePanel(id);
      }, delayMs);
      hideTimers.current.set(id, timer);
    },
    [hidePanel]
  );

  const cancelHide = useCallback((id: PanelId) => {
    const existing = hideTimers.current.get(id);
    if (existing !== undefined) {
      clearTimeout(existing);
      hideTimers.current.delete(id);
    }
  }, []);

  const tryShow = useCallback(
    (id: PanelId, event: PawAIEvent) => {
      if (dismissedPanels.has(id) && !isCriticalEvent(event)) return;
      cancelHide(id);
      showPanel(id);
    },
    [dismissedPanels, showPanel, cancelHide]
  );

  const evaluateEvent = useCallback(
    (event: PawAIEvent) => {
      const { source, event_type } = event;

      if (source === "face") {
        if (event_type === "track_started" || event_type === "identity_stable") {
          tryShow("face", event);
        } else if (event_type === "track_lost") {
          scheduleHide("face", HIDE_DELAY_MS);
        }
        return;
      }

      if (source === "speech") {
        if (event_type === "wake_word" || event_type === "intent_recognized") {
          tryShow("speech", event);
        }
        return;
      }

      if (source === "gesture" && event_type === "gesture_detected") {
        tryShow("gesture", event);
        return;
      }

      if (source === "pose" && event_type === "pose_detected") {
        tryShow("pose", event);
        return;
      }

      if (source === "brain" && event_type === "skill_dispatched") {
        tryShow("brain", event);
        return;
      }
    },
    [tryShow, scheduleHide]
  );

  return { evaluateEvent };
}
