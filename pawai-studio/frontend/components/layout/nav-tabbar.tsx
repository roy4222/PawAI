"use client";

import Link from "next/link";
import { Monitor, PawPrint } from "lucide-react";
import { LiveIndicator } from "@/components/shared/live-indicator";
import { FeatureNav } from "./feature-nav";

interface NavTabbarProps {
  isConnected: boolean;
}

/**
 * NavTabbar — top navigation for the chat-first redesign.
 *
 * Layout:
 *   [PawPrint logo + "PawAI Studio"]   [FeatureNav 6 icons]   [LIVE link · ●已連線]
 *
 * Replaces the legacy `Topbar` (which had no feature triggers, only logo +
 * LIVE link). The accent gradient line at the bottom is preserved from the
 * original design.
 */
export function NavTabbar({ isConnected }: NavTabbarProps) {
  return (
    <header
      className="relative flex items-center justify-between h-12 px-4 md:px-5 shrink-0 bg-[var(--nav-bg,var(--background))] border-b border-[var(--nav-border)]"
    >
      {/* Left — logo */}
      <Link
        href="/studio"
        className="flex items-center gap-2 hover:opacity-80 transition-opacity shrink-0"
      >
        <PawPrint className="h-5 w-5 text-primary" />
        <span className="text-sm font-semibold text-foreground tracking-tight">
          PawAI Studio
        </span>
      </Link>

      {/* Center — feature triggers */}
      <div className="flex-1 flex justify-center">
        <FeatureNav />
      </div>

      {/* Right — LIVE link + connection indicator */}
      <div className="flex items-center gap-2 shrink-0">
        <Link
          href="/studio/live"
          className={
            "hidden sm:flex items-center gap-1 px-2 py-1 rounded " +
            "text-[10px] font-mono text-zinc-400 hover:text-emerald-400 hover:bg-zinc-800/50 transition-colors " +
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 " +
            "focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--background)]"
          }
          aria-label="Live camera view"
        >
          <Monitor className="h-3 w-3" />
          LIVE
        </Link>
        <LiveIndicator active={isConnected} />
        <span className="hidden sm:inline text-xs text-muted-foreground">
          {isConnected ? "已連線" : "未連線"}
        </span>
      </div>

      {/* Accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-transparent via-sky-400/30 to-transparent" />
    </header>
  );
}
