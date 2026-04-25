"use client";

import { useEffect, useRef, useState } from "react";
import { Camera } from "lucide-react";

interface LocalCameraCardProps {
  title?: string;
  children?: React.ReactNode;
}

export function LocalCameraCard({ title = "Local Camera (Mac)", children }: LocalCameraCardProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [hasPermission, setHasPermission] = useState<boolean | null>(null);

  useEffect(() => {
    let stream: MediaStream | null = null;

    async function startCamera() {
      try {
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

    startCamera();

    return () => {
      if (stream) {
        stream.getTracks().forEach((track) => track.stop());
      }
    };
  }, []);

  return (
    <div className="flex flex-col gap-1.5 min-w-0 w-full h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <div
            className={`h-1.5 w-1.5 rounded-full ${
              hasPermission ? "bg-emerald-400" : "bg-red-400"
            }`}
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
          className="absolute inset-0 w-full h-full object-cover scale-x-[-1]" // scale-x-[-1] for mirror effect
        />

        {/* NO SIGNAL overlay */}
        {hasPermission === false && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-lg font-bold text-zinc-400 tracking-widest text-center px-4">
              CAMERA ACCESS DENIED
            </span>
          </div>
        )}
      </div>

      {/* Overlay data — below image */}
      {children && (
        <div className="px-1 min-h-[2.5rem]">
          {children}
        </div>
      )}
    </div>
  );
}
