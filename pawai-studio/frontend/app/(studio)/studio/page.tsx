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
import type { PanelId } from "@/contracts/types";

// Sidebar panel registry — add new panels here
const SIDEBAR_PANELS: { id: PanelId; component: React.FC }[] = [
  { id: "face", component: FacePanel },
  { id: "speech", component: SpeechPanel },
  { id: "gesture", component: GesturePanel },
  { id: "pose", component: PosePanel },
];

export default function StudioPage() {
  const { isConnected } = useEventStream();
  const events = useEventStore((s) => s.events);
  const activePanels = useLayoutStore((s) => s.activePanels);

  // Build sidebar: show all registered panels that are in activePanels
  const sidebarPanels = SIDEBAR_PANELS
    .filter((p) => activePanels.has(p.id))
    .map((p) => <p.component key={p.id} />);

  // If preset has no matching sidebar panels, show all as fallback
  // so first-time users always see something
  const panels = sidebarPanels.length > 0
    ? sidebarPanels
    : SIDEBAR_PANELS.map((p) => <p.component key={p.id} />);

  return (
    <StudioLayout
      isConnected={isConnected}
      mainPanel={<ChatPanel events={events} />}
      sidebarPanels={panels}
    />
  );
}
