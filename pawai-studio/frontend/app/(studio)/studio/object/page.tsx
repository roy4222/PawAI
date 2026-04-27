"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { StudioLayout } from "@/components/layout/studio-layout";
import { ObjectPanel } from "@/components/object/object-panel";

export default function ObjectPage() {
  const { isConnected } = useEventStream();

  return (
    <StudioLayout
      isConnected={isConnected}
      mainPanel={
        <div className="flex flex-col h-full px-4 py-4 max-w-4xl mx-auto w-full">
          <ObjectPanel fullPage />
        </div>
      }
    />
  );
}
