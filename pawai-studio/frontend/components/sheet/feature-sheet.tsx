"use client";

import type { ComponentType } from "react";
import { Sheet } from "@/components/ui/sheet";
import { useSheetStore, type SheetName } from "@/stores/sheet-store";
import { FacePanel } from "@/components/face/face-panel";
import { SpeechPanel } from "@/components/speech/speech-panel";
import { GesturePanel } from "@/components/gesture/gesture-panel";
import { PosePanel } from "@/components/pose/pose-panel";
import { ObjectPanel } from "@/components/object/object-panel";
import { NavigationPanel } from "@/components/navigation/navigation-panel";
import { DevPanel } from "@/components/sheet/dev-panel";
import { FEATURES } from "@/components/layout/feature-nav";

// nav-menu is the mobile hamburger variant — rendered inline below, NOT in
// the PANELS map (it isn't a feature panel).
type FeaturePanelKey = Exclude<SheetName, null | "nav-menu">;

const PANELS: Record<FeaturePanelKey, ComponentType> = {
  face: FacePanel,
  speech: SpeechPanel,
  gesture: GesturePanel,
  pose: PosePanel,
  object: ObjectPanel,
  navigation: NavigationPanel,
  dev: DevPanel,
};

const SHEET_TITLES: Record<FeaturePanelKey | "nav-menu", string> = {
  face: "人臉辨識",
  speech: "語音功能",
  gesture: "手勢辨識",
  pose: "姿勢辨識",
  object: "辨識物體",
  navigation: "導航避障",
  dev: "Dev 工具",
  "nav-menu": "功能選單",
};

/**
 * NavMenuList — mobile hamburger content. Tapping a row closes the menu and
 * opens the corresponding feature sheet immediately.
 */
function NavMenuList() {
  const openSheet = useSheetStore((s) => s.openSheet);
  return (
    <ul className="divide-y divide-[var(--sheet-border)]">
      {FEATURES.map(({ id, icon: Icon, label }) => (
        <li key={id}>
          <button
            type="button"
            onClick={() => openSheet(id)}
            className="flex items-center gap-3 w-full px-4 py-3 text-left text-sm hover:bg-[var(--nav-icon-hover-bg)] transition-colors"
          >
            <Icon className="h-4 w-4 text-[var(--nav-icon-fg)]" />
            <span className="text-foreground">{label}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * FeatureSheet — single Sheet element driven by sheet-store. Renders the
 * panel component matching `open`, or NavMenuList for the mobile hamburger
 * variant. Mounted once at the studio-layout root so any feature button or
 * `?dev=1` trigger can target it.
 */
export function FeatureSheet() {
  const open = useSheetStore((s) => s.open);
  const closeSheet = useSheetStore((s) => s.closeSheet);
  const isOpen = open !== null;
  const title = open ? SHEET_TITLES[open] : undefined;

  return (
    <Sheet
      open={isOpen}
      onOpenChange={(v) => {
        if (!v) closeSheet();
      }}
      title={title}
    >
      {open === "nav-menu" ? (
        <NavMenuList />
      ) : open ? (
        // open is a FeaturePanelKey here.
        (() => {
          const Panel = PANELS[open];
          return <Panel />;
        })()
      ) : null}
    </Sheet>
  );
}
