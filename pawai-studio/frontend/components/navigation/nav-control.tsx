"use client";

import { useEffect, useState } from "react";
import { Play, Pause, Square } from "lucide-react";
import { useStateStore } from "@/stores/state-store";
import type { NavControl, NavControlState } from "@/stores/state-store";
import { getGatewayHttpUrl } from "@/lib/gateway-url";

/**
 * NavControl — operator nav-driving controls for demo S1「移動進場」。
 *
 * 三顆按鈕走 gateway 的 nav-driving 狀態機（idle → running →
 * paused_confirm → resume → done）：
 *   開始 — POST /api/nav/start {distance, yaw_offset:0}（idle/done/null 才可）
 *   繼續 — POST /api/nav/resume（只在 paused_confirm，操作員確認前方淨空）
 *   停止 — POST /api/nav/stop（running/paused 期間隨時可按）
 *
 * 不會自動發任何移動指令；一律靠操作員明確點擊。狀態真相 =
 * gateway WS 廣播（nav_control event_type）+ 掛載時 GET /api/nav/control。
 * 對齊 6/9 HITL 結論：tight space 禁 auto-resume，靠人按「繼續」。
 */

const DEFAULT_DISTANCE = 1.2;
const MIN_DISTANCE = 0.2;
const MAX_DISTANCE = 2.0;

function stateLabel(state: NavControlState): string {
  switch (state) {
    case "running":
      return "移動中";
    case "paused_confirm":
      return "已停止（待確認）";
    case "done":
      return "已完成";
    case "idle":
    default:
      return "待命";
  }
}

export function NavControl() {
  const navControl = useStateStore((s) => s.navControl);
  const setNavControl = useStateStore((s) => s.setNavControl);
  const [distance, setDistance] = useState(String(DEFAULT_DISTANCE));
  const [busy, setBusy] = useState(false);

  // 掛載時讀 gateway 現況初始化。
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${getGatewayHttpUrl()}/api/nav/control`);
        if (!res.ok) return;
        const data = (await res.json().catch(() => null)) as
          | Partial<NavControl>
          | null;
        if (cancelled || !data) return;
        const s = data.state;
        const validState: NavControlState =
          s === "running" || s === "paused_confirm" || s === "done"
            ? s
            : "idle";
        setNavControl({
          state: validState,
          target_m: typeof data.target_m === "number" ? data.target_m : 0,
          remaining_m: typeof data.remaining_m === "number" ? data.remaining_m : 0,
          reason: typeof data.reason === "string" ? data.reason : undefined,
        });
      } catch {
        // gateway 未啟動 — navControl 保持 null
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setNavControl]);

  async function post(path: string, body?: unknown) {
    if (busy) return;
    setBusy(true);
    try {
      await fetch(`${getGatewayHttpUrl()}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: body != null ? JSON.stringify(body) : undefined,
      });
      // 不做 optimistic state — 一律等 gateway 的 nav_control WS 廣播更新。
    } catch {
      // gateway 不在線 — 不改 state
    } finally {
      setBusy(false);
    }
  }

  function handleStart() {
    const d = clampDistance(Number(distance));
    void post("/api/nav/start", { distance: d, yaw_offset: 0 });
  }

  function handleResume() {
    void post("/api/nav/resume");
  }

  function handleStop() {
    void post("/api/nav/stop");
  }

  const state: NavControlState = navControl?.state ?? "idle";
  const canStart = state === "idle" || state === "done";
  const isPausedConfirm = state === "paused_confirm";
  const isActive = state === "running" || state === "paused_confirm";

  const remaining =
    navControl != null ? `${navControl.remaining_m.toFixed(2)} m` : "—";
  const target = navControl != null ? `${navControl.target_m.toFixed(2)} m` : "—";

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        移動控制
      </h3>

      {/* 距離輸入 */}
      <label className="flex items-center gap-2">
        <span className="font-mono text-[11px] text-muted-foreground">距離 (m)</span>
        <input
          type="number"
          step="0.1"
          min={MIN_DISTANCE}
          max={MAX_DISTANCE}
          value={distance}
          onChange={(e) => setDistance(e.target.value)}
          disabled={!canStart || busy}
          className="h-7 w-20 rounded border border-border/50 bg-zinc-900 px-2 font-mono text-[12px] text-zinc-200 outline-none focus:border-sky-500/50 disabled:opacity-50"
        />
        <span className="font-mono text-[10px] text-muted-foreground/60">
          {MIN_DISTANCE}–{MAX_DISTANCE}
        </span>
      </label>

      {/* 按鈕列 */}
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={handleStart}
          disabled={!canStart || busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/40 bg-emerald-500/15 px-3 py-1.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/25 disabled:pointer-events-none disabled:opacity-40"
        >
          <Play className="h-3.5 w-3.5" />
          開始
        </button>

        {isPausedConfirm && (
          <button
            type="button"
            onClick={handleResume}
            disabled={busy}
            className="inline-flex animate-pulse items-center gap-1.5 rounded-lg border border-amber-400/60 bg-amber-500/25 px-3 py-1.5 text-sm font-semibold text-amber-100 shadow-[0_0_12px_rgba(251,191,36,0.35)] transition-colors hover:bg-amber-500/35 disabled:pointer-events-none disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            前方淨空後按繼續
          </button>
        )}

        <button
          type="button"
          onClick={handleStop}
          disabled={!isActive || busy}
          className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-500/15 px-3 py-1.5 text-sm font-semibold text-red-200 transition-colors hover:bg-red-500/25 disabled:pointer-events-none disabled:opacity-40"
        >
          <Square className="h-3.5 w-3.5" />
          停止
        </button>
      </div>

      {/* 狀態列 */}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${
            isPausedConfirm
              ? "border-amber-500/40 bg-amber-500/20 text-amber-200"
              : state === "running"
                ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                : "border-border/50 bg-zinc-500/10 text-zinc-300"
          }`}
        >
          {isPausedConfirm && <Pause className="h-3 w-3" />}
          {stateLabel(state)}
        </span>
        <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
          剩餘 {remaining}
        </span>
        <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
          目標 {target}
        </span>
      </div>

      {/* paused_confirm 原因 */}
      {isPausedConfirm && (
        <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[11px] leading-relaxed text-amber-200">
          {navControl?.reason ?? "偵測到障礙，已停止"}
          <span className="block text-[10px] text-amber-300/70">
            確認前方淨空後，按「繼續」恢復移動（不會自動恢復）。
          </span>
        </p>
      )}
    </section>
  );
}

function clampDistance(value: number): number {
  if (!Number.isFinite(value)) return DEFAULT_DISTANCE;
  return Math.min(MAX_DISTANCE, Math.max(MIN_DISTANCE, value));
}
