"use client";

import { useEventStream } from "@/hooks/use-event-stream";
import { StudioLayout } from "@/components/layout/studio-layout";
import { ChatPanel } from "@/components/chat/chat-panel";

export default function StudioPage() {
  const { isConnected } = useEventStream();
  return <StudioLayout isConnected={isConnected} mainPanel={<ChatPanel />} />;
}
