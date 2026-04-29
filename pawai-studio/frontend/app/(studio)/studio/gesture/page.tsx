"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { StudioLayout } from "@/components/layout/studio-layout";
import { GesturePanel } from "@/components/gesture/gesture-panel";
import { LiveFeedCard } from "@/components/live/live-feed-card";


export default function GesturePage() {
  const { isConnected } = useEventStream();

  return (
    <StudioLayout
      isConnected={isConnected}
      mainPanel={
        <div className="flex flex-col h-full px-6 py-6 overflow-hidden">
          {/* Header */}
          <div className="mb-6 flex flex-col gap-1">
            <h1 className="text-xl font-semibold tracking-tight text-foreground">手勢辨識與互動</h1>
            <p className="text-sm text-muted-foreground">
              左側為 Python 傳來的即時骨架畫面，右側為手勢偵測結果與對應的 Go2 動作。
            </p>
          </div>

          {/* Two-column layout */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-2 gap-8 min-h-0 items-start">
            {/* Left Column: Camera (LiveFeedCard) */}
            <div className="flex flex-col w-full h-full overflow-y-auto gap-3 pb-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
              <LiveFeedCard
                source="vision"
                title="即時骨架串流"
                topicName="/python/gesture_recognition"
              />
            </div>

            {/* Right Column: Gesture Panel & Hints */}
            <div className="flex flex-col w-full h-full overflow-y-auto pr-1 mt-6 gap-4 pb-4">
              <GesturePanel />
              
              <div className="text-[11px] text-muted-foreground bg-surface/50 p-2.5 rounded-lg border border-border/30 shrink-0">
                <p className="font-medium text-foreground mb-1">💡 測試提示：</p>
                <p>1. 畫面若顯示 NO SIGNAL，請確認 Python 手勢程式已啟動。</p>
                <p>2. 終端機執行：<code className="bg-muted px-1 py-0.5 rounded">python gesture-wu/gesture_recognition.py</code></p>
              </div>
            </div>
          </div>
        </div>
      }
    />
  );
}
