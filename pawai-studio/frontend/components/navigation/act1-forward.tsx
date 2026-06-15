"use client";

import { useState } from "react";
import { ArrowUp, Square } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import { authHeaders } from "@/lib/gateway-auth";
import { getGatewayHttpUrl } from "@/lib/gateway-url";

/**
 * Act1Forward — 短距直行 / 無地圖避障（demo 主線）。
 *
 * **不走 GotoRelative / Nav2 / map。** 按鈕 → gateway POST /api/act1/forward
 * {distance_m} → act1 controller → reactive_stop（standalone /cmd_vel，demo_forward
 * profile）。距離是時間估算（distance ÷ 0.6 m/s），非精準 odom。前方 danger 時禁止
 * 前進、reactive 自動停。STOP → /api/act1/stop（立刻停車並鎖回）。
 *
 * 對外 claim：「不依賴地圖的短距直行 + 正前方 LiDAR 障礙安全停車」。
 * 不可講：自主導航 / 走到人面前 / 完整避障 / 動態路徑規劃。
 */

const DISTANCES = [0.5, 1.0, 1.5] as const;

export function Act1Forward() {
  const navReactiveStop = useStateStore((s) => s.navReactiveStop);
  const [busy, setBusy] = useState(false);
  const [last, setLast] = useState<string | null>(null);

  const zone = navReactiveStop?.zone ?? null;
  const front = navReactiveStop?.front_distance_m ?? null;
  const ready = navReactiveStop != null;
  const danger = zone === "danger";

  async function post(path: string, body: unknown, label: string) {
    if (busy) return;
    setBusy(true);
    try {
      const res = await fetch(`${getGatewayHttpUrl()}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: body != null ? JSON.stringify(body) : undefined,
      });
      setLast(res.ok ? label : `失敗 (${res.status})`);
    } catch {
      setLast("gateway 未連線");
    } finally {
      setBusy(false);
    }
  }

  const zoneChip =
    zone === "danger"
      ? "border-red-500/50 bg-red-500/20 text-red-200"
      : zone === "slow"
        ? "border-amber-500/40 bg-amber-500/20 text-amber-200"
        : zone === "clear"
          ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
          : "border-border/50 bg-zinc-500/10 text-zinc-300";

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        短距直行 / 無地圖避障
      </h3>
      <p className="text-[11px] leading-relaxed text-muted-foreground/70">
        不需地圖。短距前進，正前方 LiDAR 障礙自動停。距離為時間估算（~0.6 m/s）。
        <span className="block text-amber-300/70">操作員 e-stop 在手、前方淨空再按。</span>
      </p>

      {/* 前進按鈕 */}
      <div className="flex flex-wrap items-center gap-2">
        {DISTANCES.map((d) => (
          <button
            key={d}
            type="button"
            onClick={() => void post("/api/act1/forward", { distance_m: d }, `已送出：前進 ${d}m`)}
            disabled={busy || danger || !ready}
            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-1.5 text-sm font-semibold text-sky-200 transition-colors hover:bg-sky-500/25 disabled:pointer-events-none disabled:opacity-40"
          >
            <ArrowUp className="h-3.5 w-3.5" />
            前進 {d}m
          </button>
        ))}
        <button
          type="button"
          onClick={() => void post("/api/act1/stop", undefined, "已停止並鎖回")}
          disabled={busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-500/15 px-3 py-1.5 text-sm font-semibold text-red-200 transition-colors hover:bg-red-500/25 disabled:pointer-events-none disabled:opacity-40"
        >
          <Square className="h-3.5 w-3.5" />
          STOP
        </button>
      </div>

      {/* 狀態列 */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${zoneChip}`}
        >
          zone: {zone ?? "—"}
        </span>
        <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
          前方 {front != null ? `${front.toFixed(2)} m` : "—"}
        </span>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] ${
            ready
              ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
              : "border-red-500/40 bg-red-500/15 text-red-200"
          }`}
        >
          {ready ? "reactive ready" : "reactive 無資料"}
        </span>
        {last && (
          <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
            {last}
          </span>
        )}
      </div>

      {danger && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1.5 text-[11px] text-red-200">
          前方偵測到障礙（danger），已禁止前進。移開障礙或調整朝向後再試。
        </p>
      )}
    </section>
  );
}
