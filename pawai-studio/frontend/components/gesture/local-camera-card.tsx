"use client";

import { useEffect, useRef, useState } from "react";
import { Camera } from "lucide-react";
import { cn } from "@/lib/utils";

interface LocalCameraCardProps {
  title?: string;
  /** Mirror the video horizontally (default true — friendlier for self-view). */
  mirror?: boolean;
  /** Optional overlay rendered below the video frame. */
  children?: React.ReactNode;
}

/**
 * LocalCameraCard — webcam preview tile for dev / demo use.
 *
 * Ported from PR #38 (Yamiko). Used inside `GesturePanel` as the top
 * section so users can confirm their hand is in frame before triggering
 * a gesture. No detection happens here — gesture inference still runs
 * via gateway events (see `useStateStore.gestureState`).
 */
export function LocalCameraCard({
  title = "Local Camera",
  mirror = true,
  children,
}: LocalCameraCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
        if (
          typeof navigator === "undefined" ||
          !navigator.mediaDevices ||
          typeof navigator.mediaDevices.getUserMedia !== "function"
        ) {
          setHasPermission(false);
          return;
        }
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: "user" },
        });
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
        }
        setHasPermission(true);
      } catch (err) {
        console.error("Failed to access camera:", err);
        setHasPermission(false);
      }
    }

    void startCamera();

    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return (
    <div className="flex flex-col gap-1.5 min-w-0 w-full">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <div
            className={cn(
              "h-1.5 w-1.5 rounded-full",
              hasPermission === true && "bg-emerald-400",
              hasPermission === false && "bg-red-400",
              hasPermission === null && "bg-amber-400 animate-pulse",
            )}
          />
          <span className="text-xs font-medium text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
            <Camera className="w-3.5 h-3.5" />
            {title}
          </span>
        </div>
      </div>

      {/* Video frame */}
      <div className="relative w-full aspect-[4/3] bg-zinc-950 rounded-lg border border-zinc-800 overflow-hidden">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className={cn(
            "absolute inset-0 w-full h-full object-cover",
            mirror && "scale-x-[-1]",
          )}
        />

        {hasPermission === false && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-sm font-bold text-zinc-400 tracking-widest text-center px-4">
              CAMERA ACCESS DENIED
            </span>
          </div>
        )}
        {hasPermission === null && (
          <div className="absolute inset-0 bg-black/45 flex items-center justify-center">
            <span className="text-xs text-zinc-400">啟用相機中…</span>
          </div>
        )}
      </div>

      {children && (
        <div className="px-1 min-h-[2.5rem]">
          {children}
        </div>
      )}
    </div>
  );
}
