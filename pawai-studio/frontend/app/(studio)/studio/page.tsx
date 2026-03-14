"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { useEventStore } from "@/stores/event-store";
import { useLayoutStore } from "@/stores/layout-store";
import { StudioLayout } from "@/components/layout/studio-layout";
import { ChatPanel } from "@/components/chat/chat-panel";
import { FacePanel } from "@/components/face/face-panel";
import { SpeechPanel } from "@/components/speech/speech-panel";
import { GesturePanel } from "@/components/gesture/gesture-panel";
import { PosePanel } from "@/components/pose/pose-panel";

export default function StudioPage() {
  const { isConnected } = useEventStream();
  const events = useEventStore((s) => s.events);
  const activePanels = useLayoutStore((s) => s.activePanels);

  // Build sidebar panels based on active layout
  const sidebarPanels: React.ReactNode[] = [];
  if (activePanels.has("face")) {
    sidebarPanels.push(<FacePanel key="face" />);
  }
  if (activePanels.has("speech")) {
    sidebarPanels.push(<SpeechPanel key="speech" />);
  }
  if (activePanels.has("gesture")) {
    sidebarPanels.push(<GesturePanel key="gesture" />);
  }
  if (activePanels.has("pose")) {
    sidebarPanels.push(<PosePanel key="pose" />);
  }

  return (
    <StudioLayout
      isConnected={isConnected}
      mainPanel={<ChatPanel events={events} />}
      sidebarPanels={sidebarPanels.length > 0 ? sidebarPanels : undefined}
    />
  );
}
