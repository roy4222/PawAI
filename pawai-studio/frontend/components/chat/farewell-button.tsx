"use client";

import { useState } from "react";
import { Heart } from "lucide-react";
import { authHeaders } from "@/lib/gateway-auth";
import { getGatewayHttpUrl } from "@/lib/gateway-url";
import { cn } from "@/lib/utils";

/**
 * FarewellButton — 學校招生 demo (2026-06-22) 結尾「道別」鈕。
 *
 * 按下 → POST /api/farewell_action：gateway 直接 publish 結尾口號（管理學院版
 * 「輔大管院填寫第一志願」）到 /tts + 比愛心 WebRtcReq(api_id=1036) 到
 * /webrtc_req，繞過 brain、不入對話歷史、口號原文保證播出。
 * 一次性 action（無 toggle state）。沿用 ChatPanel 新對話鈕的 window.confirm
 * 防誤觸 —— demo 中途誤按會打斷流程。SSH 備援為 scripts/school_demo_ending.py
 * --college。
 */

/** Pure helper — the request shape handleFarewell POSTs (testable without DOM). */
export function buildFarewellRequest(): { url: string } {
  return { url: `${getGatewayHttpUrl()}/api/farewell_action` };
}

export function FarewellButton() {
  const [busy, setBusy] = useState(false);

  async function handleFarewell() {
    if (busy) return;
    const ok = window.confirm(
      "觸發結尾：播放「輔大管院填寫第一志願」並比愛心。確定？"
    );
    if (!ok) return;
    setBusy(true);
    try {
      const { url } = buildFarewellRequest();
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
      });
    } catch {
      // gateway 不在線 — 靜默（操作員可改跑 SSH 備援腳本）
    } finally {
      setBusy(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleFarewell}
      disabled={busy}
      title="結尾道別：輔大管院填第一志願 + 比愛心（學校 demo）"
      aria-label="道別"
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px]",
        "border-pink-500/40 bg-pink-500/10 text-pink-300",
        "transition-colors hover:bg-pink-500/20 disabled:opacity-50",
      )}
    >
      <Heart className="h-3 w-3" />
      <span>道別</span>
    </button>
  );
}
