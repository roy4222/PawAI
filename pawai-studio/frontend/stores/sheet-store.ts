"use client";

import { create } from "zustand";

// Names that can be opened as a Sheet via the NavTabbar / DevButton.
//
// - "face" / "speech" / "gesture" / "pose" / "object" / "navigation"
//     → 6 feature panels (one per nav icon)
// - "dev"
//     → developer tools (skill console + trace), shown via ?dev=1 ⚙ button
// - "nav-menu"
//     → mobile hamburger menu listing the 6 features (special variant; not a
//       feature panel — rendered inline in FeatureSheet, not via PANELS map)
export type SheetName =
  | "face"
  | "speech"
  | "gesture"
  | "pose"
  | "object"
  | "navigation"
  | "dev"
  | "nav-menu"
  | null;

interface SheetStore {
  open: SheetName;
  openSheet: (name: SheetName) => void;
  closeSheet: () => void;
}

// Single source of truth for "which sheet is open?". Mutually exclusive —
// opening a new sheet implicitly closes any other (the Sheet primitive reads
// `open === <its name>` for visibility).
export const useSheetStore = create<SheetStore>((set) => ({
  open: null,
  openSheet: (name) => set({ open: name }),
  closeSheet: () => set({ open: null }),
}));
