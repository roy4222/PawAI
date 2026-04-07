"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { useStateStore } from "@/stores/state-store";
import { LiveFeedCard } from "@/components/live/live-feed-card";
import { EventTicker } from "@/components/live/event-ticker";
import { LiveIndicator } from "@/components/shared/live-indicator";
import Link from "next/link";
import { PawPrint, ArrowLeft } from "lucide-react";

// ── Overlay Components ───────────────────────────────────────

function FaceOverlay() {
  const face = useStateStore((s) => s.faceState);
  if (!face) return <p className="text-xs text-zinc-600">waiting...</p>;

  const top = face.tracks?.slice(0, 3) ?? [];
  return (
    <div className="space-y-0.5">
      {top.map((t) => (
        <div key={t.track_id} className="flex items-center gap-2 text-xs">
          <span className="text-zinc-200 font-medium">
            {t.stable_name || "unknown"}
          </span>
          <span className="text-emerald-400 font-mono">
            {Math.round(t.sim * 100)}%
          </span>
          {t.distance_m != null && (
            <span className="text-zinc-500 font-mono">
              {t.distance_m.toFixed(1)}m
            </span>
          )}
          <span className="text-zinc-600 text-[10px]">{t.mode}</span>
        </div>
      ))}
      <div className="text-[10px] text-zinc-500">
        {face.face_count} face{face.face_count !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

function VisionOverlay() {
  const pose = useStateStore((s) => s.poseState);
  const gesture = useStateStore((s) => s.gestureState);

  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-zinc-400">Pose:</span>
        <span className="text-zinc-200 font-medium">
          {pose?.current_pose ?? "\u2014"}
        </span>
        {pose?.confidence != null && (
          <span className="text-emerald-400 font-mono">
            {Math.round(pose.confidence * 100)}%
          </span>
        )}
        {pose?.current_pose === "fallen" && (
          <span className="text-red-400 font-bold animate-pulse">ALERT</span>
        )}
      </div>
      <div className="flex items-center gap-2 text-xs">
        <span className="text-zinc-400">Gesture:</span>
        <span className="text-zinc-200 font-medium">
          {gesture?.current_gesture ?? "\u2014"}
        </span>
        {gesture?.hand && (
          <span className="text-zinc-500 text-[10px]">{gesture.hand}</span>
        )}
      </div>
    </div>
  );
}

function ObjectOverlay() {
  const obj = useStateStore((s) => s.objectState);
  const items = obj?.detected_objects?.slice(0, 3) ?? [];

  if (items.length === 0)
    return <p className="text-xs text-zinc-600">no objects</p>;

  return (
    <div className="space-y-0.5">
      {items.map((d, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="text-zinc-200 font-medium">{d.class_name}</span>
          <span className="text-emerald-400 font-mono">
            {Math.round(d.confidence * 100)}%
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Main Page ────────────────────────────────────────────────

export default function LiveViewPage() {
  const { isConnected } = useEventStream();
  const systemHealth = useStateStore((s) => s.systemHealth);
  const temp = systemHealth?.jetson?.temperature_c;

  return (
    <div className="flex flex-col h-screen bg-[#0a0f1a] text-zinc-100">
      {/* Status Bar */}
      <header className="flex items-center justify-between h-11 px-4 border-b border-zinc-800/60 shrink-0">
        <div className="flex items-center gap-3">
          <Link
            href="/studio"
            className="flex items-center gap-1.5 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
          </Link>
          <PawPrint className="h-4 w-4 text-emerald-400" />
          <span className="text-sm font-semibold tracking-tight">
            PawAI Live View
          </span>
          <span className="text-[10px] font-mono text-zinc-600 uppercase tracking-widest">
            monitor
          </span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-zinc-500">Gateway</span>
            <LiveIndicator active={isConnected} />
          </div>
          {temp != null && (
            <span
              className={`text-[10px] font-mono ${
                temp > 75
                  ? "text-red-400"
                  : temp > 60
                    ? "text-amber-400"
                    : "text-zinc-500"
              }`}
            >
              Jetson {temp}&deg;C
            </span>
          )}
        </div>
      </header>

      {/* Three-Column Grid */}
      <main className="flex-1 grid grid-cols-1 lg:grid-cols-3 gap-4 p-4 min-h-0">
        <LiveFeedCard
          source="face"
          title="Face Identity"
          topicName="/face_identity/debug_image"
        >
          <FaceOverlay />
        </LiveFeedCard>

        <LiveFeedCard
          source="vision"
          title="Gesture + Pose"
          topicName="/vision_perception/debug_image"
        >
          <VisionOverlay />
        </LiveFeedCard>

        <LiveFeedCard
          source="object"
          title="Object Perception"
          topicName="/perception/object/debug_image"
        >
          <ObjectOverlay />
        </LiveFeedCard>
      </main>

      {/* Event Ticker */}
      <EventTicker />
    </div>
  );
}
