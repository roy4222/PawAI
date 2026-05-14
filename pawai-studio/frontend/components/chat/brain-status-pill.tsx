"use client";

import { useStateStore } from "@/stores/state-store";

const MODE_LABEL: Record<string, string> = {
  idle: "待命",
  chat: "聊天中",
  skill: "執行中",
  sequence: "進行序列",
  alert: "警報",
  safety_stop: "安全停止",
};

/**
 * BrainStatusPill — thin centered pill at the top of the chat.
 *
 * Replaces the bulkier BrainStatusStrip from the legacy layout. Single line:
 *   Brain {mode} · obs:ok emg:ok fall:ok tts:idle
 *
 * Reads brainState from state-store. Renders nothing if no brain state has
 * arrived yet (avoids placeholder noise on first paint).
 */
export function BrainStatusPill() {
  const brain = useStateStore((s) => s.brainState);
  if (!brain) return null;

  const mode = MODE_LABEL[brain.mode] ?? brain.mode;
  const flags = brain.safety_flags;
  return (
    <div className="flex justify-center pt-2 pb-1">
      <div
        className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-[12px] font-mono"
        style={{
          backgroundColor: "var(--pill-bg)",
          borderColor: "var(--pill-border)",
          color: "var(--pill-fg)",
        }}
      >
        <span style={{ color: "var(--pill-fg-emphasis)" }}>Brain</span>
        <span>{mode}</span>
        {flags && (
          <>
            <span className="text-[var(--pill-fg)]/50">·</span>
            <span>obs:{flags.obstacle ? "alert" : "ok"}</span>
            <span>emg:{flags.emergency ? "alert" : "ok"}</span>
            <span>fall:{flags.fallen ? "alert" : "ok"}</span>
            <span>tts:{flags.tts_playing ? "play" : "idle"}</span>
          </>
        )}
      </div>
    </div>
  );
}
