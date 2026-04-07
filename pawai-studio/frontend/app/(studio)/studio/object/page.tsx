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
        <div className="flex flex-col items-center justify-center h-full gap-6 px-6">
          <div className="w-full max-w-lg">
            <ObjectPanel />
          </div>
          <div className="text-sm text-muted-foreground text-center max-w-md space-y-2">
            <p>物件偵測面板開發頁</p>
            <p>
              修改 <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono">components/object/object-panel.tsx</code>
            </p>
          </div>
        </div>
      }
    />
  );
}
