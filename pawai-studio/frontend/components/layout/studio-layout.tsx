"use client";

import { NavTabbar } from "./nav-tabbar";
import { FeatureSheet } from "@/components/sheet/feature-sheet";
import { DevButton } from "@/components/chat/brain/dev-button";

interface StudioLayoutProps {
  mainPanel: React.ReactNode;
  isConnected: boolean;
}

/**
 * StudioLayout — chat-first redesign root layout.
 *
 * Replaces the prior sidebar-driven layout. All feature panels are now
 * Sheet-based (slide in from right on desktop, bottom on mobile) and share
 * a single <FeatureSheet /> mount point at the layout root.
 *
 * DevButton is also mounted here (single instance) so `?dev=1` works on
 * any /studio/* route, not just the chat panel. The button itself
 * self-guards against `/studio/dev` (avoids redundant entry).
 */
export function StudioLayout({ mainPanel, isConnected }: StudioLayoutProps) {
  return (
    <div className="flex flex-col h-screen bg-background">
      <NavTabbar isConnected={isConnected} />
      <main className="flex-1 overflow-hidden transition-all duration-300 ease-out">
        {mainPanel}
      </main>
      <FeatureSheet />
      <DevButton />
    </div>
  );
}
