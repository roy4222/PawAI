"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { StudioLayout } from "@/components/layout/studio-layout";
import { PosePanel } from "@/components/pose/pose-panel";

export default function PosePage() {
  const { isConnected } = useEventStream();

  return (
    <StudioLayout
      isConnected={isConnected}
      mainPanel={
        <div className="flex h-full flex-col items-center justify-center gap-4 px-4 py-4 md:px-8">
          <div className="w-full max-w-5xl">
            <PosePanel />
          </div>
          <div className="w-full max-w-5xl text-center text-xs text-muted-foreground/80">
            <p>姿勢辨識面板開發頁</p>
          </div>
        </div>
      }
    />
  );
}
