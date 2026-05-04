"use client";

import { NavTabbar } from "./nav-tabbar";
import { FeatureSheet } from "@/components/sheet/feature-sheet";

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
 */
export function StudioLayout({ mainPanel, isConnected }: StudioLayoutProps) {
  return (
    <div className="flex flex-col h-screen bg-background">
      <NavTabbar isConnected={isConnected} />
      <main className="flex-1 overflow-hidden transition-all duration-300 ease-out">
        {mainPanel}
      </main>
      <FeatureSheet />
    </div>
  );
}
