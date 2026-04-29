"use client";

import { useVideoStream } from "@/hooks/use-video-stream";

type VideoSource = "face" | "vision" | "object";
type StreamStatus = "connected" | "no_signal" | "disconnected";

interface LiveFeedCardProps {
  source: VideoSource;
  title: string;
  topicName: string;
  children?: React.ReactNode;
}

const STATUS_LABEL: Record<StreamStatus, string> = {
  connected: "",
  no_signal: "NO SIGNAL",
  disconnected: "DISCONNECTED",
};

function FpsBadge({ fps }: { fps: number }) {
  const color =
    fps >= 2
      ? "text-emerald-400"
      : fps > 0
        ? "text-amber-400"
        : "text-red-400";
  return (
    <span className={`font-mono text-[10px] ${color}`}>
      {fps.toFixed(1)} fps
    </span>
  );
}

export function LiveFeedCard({ source, title, topicName, children }: LiveFeedCardProps) {
  const { imageUrl, fps, status } = useVideoStream({ source });
  const showOverlay = status !== "connected";

  return (
    <div className="flex flex-col gap-1.5 min-w-0">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              status === "connected" ? "bg-emerald-400" : "bg-zinc-600"
            }`}
          />
          <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider">
            {title}
          </span>
        </div>
        <FpsBadge fps={fps} />
      </div>

      {/* Video frame */}
      <div className="relative aspect-[4/3] bg-zinc-950 rounded-lg border border-zinc-800 overflow-hidden">
        {imageUrl && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={imageUrl}
            alt={`${source} feed`}
            className="absolute inset-0 w-full h-full object-contain"
          />
        )}

        {/* Topic name — top left */}
        <div className="absolute top-2 left-2">
          <span className="text-[9px] font-mono text-zinc-500">
            {topicName}
          </span>
        </div>

        {/* NO SIGNAL / DISCONNECTED overlay */}
        {showOverlay && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-2xl font-bold text-zinc-400 tracking-widest">
              {STATUS_LABEL[status]}
            </span>
          </div>
        )}
      </div>

      {/* Overlay data — below image */}
      <div className="px-1 min-h-[2.5rem]">
        {children}
      </div>
    </div>
  );
}
