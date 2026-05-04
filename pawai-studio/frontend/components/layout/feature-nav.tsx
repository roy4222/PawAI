"use client";

import {
  Box,
  Compass,
  Hand,
  Menu,
  Mic,
  PersonStanding,
  User,
  type LucideIcon,
} from "lucide-react";
import { useSheetStore, type SheetName } from "@/stores/sheet-store";
import { cn } from "@/lib/utils";

interface Feature {
  id: Exclude<SheetName, null | "dev" | "nav-menu">;
  icon: LucideIcon;
  label: string;
}

export const FEATURES: Feature[] = [
  { id: "face", icon: User, label: "人臉辨識" },
  { id: "speech", icon: Mic, label: "語音功能" },
  { id: "gesture", icon: Hand, label: "手勢辨識" },
  { id: "pose", icon: PersonStanding, label: "姿勢辨識" },
  { id: "object", icon: Box, label: "辨識物體" },
  { id: "navigation", icon: Compass, label: "導航避障" },
];

/**
 * FeatureNav — 6 icon-only buttons in the navbar.
 *
 * Desktop (≥ md): row of 6 buttons + tooltip via title attr.
 * Mobile (< md): single hamburger Menu icon → opens "nav-menu" Sheet which
 * lists the 6 features (rendered inline by FeatureSheet, not via PANELS map).
 */
export function FeatureNav() {
  const open = useSheetStore((s) => s.open);
  const openSheet = useSheetStore((s) => s.openSheet);

  return (
    <div className="flex items-center gap-1">
      {/* Mobile hamburger — visible < md */}
      <button
        type="button"
        onClick={() => openSheet("nav-menu")}
        title="功能選單"
        aria-label="Open feature menu"
        className={cn(
          "md:hidden inline-flex h-8 w-8 items-center justify-center rounded-md",
          "text-[var(--nav-icon-fg)] hover:text-[var(--nav-icon-hover-fg)]",
          "hover:bg-[var(--nav-icon-hover-bg)]",
          "transition-colors",
        )}
        style={{ transitionDuration: "var(--anim-bubble-hover)" }}
      >
        <Menu className="h-4 w-4" />
      </button>

      {/* Desktop icon row — visible ≥ md */}
      <div className="hidden md:flex items-center gap-1">
        {FEATURES.map(({ id, icon: Icon, label }) => {
          const active = open === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => openSheet(id)}
              title={label}
              aria-label={label}
              className={cn(
                "inline-flex h-8 w-8 items-center justify-center rounded-md",
                "transition-colors",
                "hover:bg-[var(--nav-icon-hover-bg)]",
                active
                  ? "text-[var(--nav-icon-active-fg)]"
                  : "text-[var(--nav-icon-fg)] hover:text-[var(--nav-icon-hover-fg)]",
              )}
              style={{ transitionDuration: "var(--anim-bubble-hover)" }}
            >
              <Icon className="h-4 w-4" />
            </button>
          );
        })}
      </div>
    </div>
  );
}
