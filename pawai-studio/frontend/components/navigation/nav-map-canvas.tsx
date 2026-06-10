"use client";

import { useEffect, useRef, useState } from "react";
import { useStateStore } from "@/stores/state-store";
import type { NavPose, NavReactiveStop, NavZone } from "@/stores/state-store";
import { getGatewayHttpUrl } from "@/lib/gateway-url";

/**
 * NavMapCanvas — Canvas2D nav panel (Task A, 6/18 demo).
 *
 * Renders: static map PNG underlay → live AMCL pose triangle →
 * fixed goal marker → current→goal line → status chip. Read-only;
 * no ros3djs, no move button, no dynamic goal, no depth video, no 3D.
 *
 * Single source of truth = v8 map (home_living_room_v8). origin/res/H
 * are hardwired here so the canvas does NOT depend on the gateway
 * /api/map_meta endpoint (which is an optional fast-follow).
 */

// v8 map metadata — MUST match docs/navigation/research/maps/home_living_room_v8.yaml
// (origin [-2.41, -2.81, 0], resolution 0.05) and the cp'd PNG (205×98).
// ⚠️ NOT v7 (origin -7.79 / -2.46). If the demo map changes, update all three:
// this constant, public/maps PNG, and (if added) the gateway map.yaml.
export const DEMO_MAP = {
  src: "/maps/home_living_room.png",
  resolution: 0.05,
  originX: -2.41,
  originY: -2.81,
};

// PGM native pixel dimensions (W×H). H is load-bearing for the y-flip.
const MAP_W = 205;
const MAP_H = 98;

// Fixed demo goal in world metres (map frame). Calibrate to the venue.
export const DEMO_GOAL = { x: 1.2, y: 0.6 };

// CSS upscale factor for the native-resolution backing store.
const SCALE = 3;

const ZONE_COLOR: Record<NavZone, string> = {
  clear: "#34d399", // emerald-400
  slow: "#fbbf24", // amber-400
  danger: "#f87171", // red-400
};

// ── Forward / inverse map transform ────────────────────────────────
// FORWARD (world metres → native canvas px):
//   col       = (wx - originX) / res
//   rowBottom = (wy - originY) / res
//   px = col
//   py = (MAP_H - 1) - rowBottom        ← single y-flip (PGM rows top→down)
//
// INVERSE (native canvas px → world metres) — exact inverse of FORWARD:
//   wx        = px * res + originX
//   rowBottom = (MAP_H - 1) - py
//   wy        = rowBottom * res + originY
//
// NOTE: native px ≠ CSS px. The backing store is MAP_W×MAP_H and the
// element is CSS-upscaled by SCALE (with maxWidth:100% on small screens),
// so a click's CSS coords must be rescaled via getBoundingClientRect()
// to native px BEFORE applying the inverse (see canvasEventToWorld).

/** World metres → native canvas pixels. y-flip happens exactly once. */
function worldToCanvas(wx: number, wy: number): { px: number; py: number } {
  const col = (wx - DEMO_MAP.originX) / DEMO_MAP.resolution;
  const rowBottom = (wy - DEMO_MAP.originY) / DEMO_MAP.resolution;
  return { px: col, py: MAP_H - 1 - rowBottom };
}

/** Native canvas pixels → world metres. Exact inverse of worldToCanvas. */
function canvasToWorld(px: number, py: number): { wx: number; wy: number } {
  const wx = px * DEMO_MAP.resolution + DEMO_MAP.originX;
  const rowBottom = MAP_H - 1 - py;
  const wy = rowBottom * DEMO_MAP.resolution + DEMO_MAP.originY;
  return { wx, wy };
}

/** A pending initialpose being set on the canvas (native px + optional heading target). */
interface ProvisionalPose {
  px: number; // native canvas px of the chosen position
  py: number;
  yaw: number | null; // null = position picked, heading not yet set
}

function drawTriangle(
  ctx: CanvasRenderingContext2D,
  px: number,
  py: number,
  yaw: number,
  color: string,
) {
  // map +yaw is CCW; canvas y points down (screen CW), so negate.
  const screenAngle = -yaw;
  const size = 5; // native px (half-length of the pointer)
  ctx.save();
  ctx.translate(px, py);
  ctx.rotate(screenAngle);
  ctx.beginPath();
  ctx.moveTo(size, 0); // tip points along +x (= world heading) before rotate
  ctx.lineTo(-size * 0.7, size * 0.7);
  ctx.lineTo(-size * 0.7, -size * 0.7);
  ctx.closePath();
  ctx.fillStyle = color;
  ctx.strokeStyle = "rgba(0,0,0,0.55)";
  ctx.lineWidth = 0.6;
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

/** Draws the provisional initialpose being placed (white position dot + heading line/arrow). */
function drawProvisional(ctx: CanvasRenderingContext2D, prov: ProvisionalPose) {
  // position dot
  ctx.beginPath();
  ctx.arc(prov.px, prov.py, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = "#ffffff";
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.6)";
  ctx.lineWidth = 0.6;
  ctx.stroke();

  if (prov.yaw != null) {
    // heading arrow (white triangle pointing along chosen yaw)
    drawTriangle(ctx, prov.px, prov.py, prov.yaw, "#ffffff");
  }
}

function drawScene(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement | null,
  pose: NavPose | null,
  reactiveStop: NavReactiveStop | null,
  provisional: ProvisionalPose | null,
) {
  ctx.clearRect(0, 0, MAP_W, MAP_H);

  if (img && img.complete && img.naturalWidth > 0) {
    ctx.drawImage(img, 0, 0, MAP_W, MAP_H);
  } else {
    ctx.fillStyle = "#18181b"; // zinc-900 fallback
    ctx.fillRect(0, 0, MAP_W, MAP_H);
  }

  // Goal marker (fixed).
  const goal = worldToCanvas(DEMO_GOAL.x, DEMO_GOAL.y);
  ctx.beginPath();
  ctx.arc(goal.px, goal.py, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = "#60a5fa"; // blue-400
  ctx.fill();
  ctx.strokeStyle = "rgba(0,0,0,0.55)";
  ctx.lineWidth = 0.6;
  ctx.stroke();

  if (pose) {
    const cur = worldToCanvas(pose.x, pose.y);

    // current → goal line.
    ctx.beginPath();
    ctx.moveTo(cur.px, cur.py);
    ctx.lineTo(goal.px, goal.py);
    ctx.strokeStyle = "rgba(96,165,250,0.55)";
    ctx.lineWidth = 0.8;
    ctx.setLineDash([3, 2]);
    ctx.stroke();
    ctx.setLineDash([]);

    const zone: NavZone = reactiveStop?.zone ?? "clear";
    drawTriangle(ctx, cur.px, cur.py, pose.yaw, ZONE_COLOR[zone]);
  }

  if (provisional) {
    drawProvisional(ctx, provisional);
  }
}

/** Maps a pointer event (CSS coords) to native canvas px, accounting for SCALE + maxWidth clamp. */
function eventToNativePx(
  canvas: HTMLCanvasElement,
  e: { clientX: number; clientY: number },
): { px: number; py: number } {
  const rect = canvas.getBoundingClientRect();
  // rect is the *rendered* size (post-SCALE, post-maxWidth). Map back to the
  // native backing-store resolution (canvas.width × canvas.height).
  const scaleX = canvas.width / rect.width;
  const scaleY = canvas.height / rect.height;
  const px = (e.clientX - rect.left) * scaleX;
  const py = (e.clientY - rect.top) * scaleY;
  return { px, py };
}

export function NavMapCanvas() {
  const navPose = useStateStore((s) => s.navPose);
  const navReactiveStop = useStateStore((s) => s.navReactiveStop);
  const navPaused = useStateStore((s) => s.navPaused);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // ── Set-initialpose mode ──────────────────────────────────────────
  const [setMode, setSetMode] = useState(false);
  const [provisional, setProvisional] = useState<ProvisionalPose | null>(null);
  const [posting, setPosting] = useState(false);
  // numeric fallback inputs (typed pose) — strings so the field can be blanked.
  const [numX, setNumX] = useState("0");
  const [numY, setNumY] = useState("0");
  const [numYawDeg, setNumYawDeg] = useState("0");

  async function postInitialPose(x: number, y: number, yaw: number) {
    setPosting(true);
    try {
      const res = await fetch(`${getGatewayHttpUrl()}/api/nav/initialpose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ x, y, yaw }),
      });
      if (!res.ok) return false;
      const data = (await res.json().catch(() => null)) as { ok?: boolean } | null;
      return Boolean(data?.ok);
    } catch {
      return false;
    } finally {
      setPosting(false);
    }
  }

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!setMode || posting) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { px, py } = eventToNativePx(canvas, e);

    if (!provisional || provisional.yaw != null) {
      // First click (or a fresh restart): set position, heading pending.
      setProvisional({ px, py, yaw: null });
      return;
    }

    // Second click: yaw = heading from the position toward this click point.
    // In native px, py grows downward, so the world +yaw (CCW) angle is
    // atan2(-(dy), dx) to undo the canvas y-flip.
    const dx = px - provisional.px;
    const dy = py - provisional.py;
    const yaw = Math.atan2(-dy, dx);
    setProvisional({ px: provisional.px, py: provisional.py, yaw });
  }

  // Live preview: while dragging/moving after the first click, show heading.
  function handleCanvasMove(e: React.MouseEvent<HTMLCanvasElement>) {
    if (!setMode || !provisional || provisional.yaw != null) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const { px, py } = eventToNativePx(canvas, e);
    const dx = px - provisional.px;
    const dy = py - provisional.py;
    if (dx === 0 && dy === 0) return;
    const yaw = Math.atan2(-dy, dx);
    // Preview-only: don't lock yaw (keep null) but redraw an indicator by
    // temporarily drawing a previewing arrow via a transient provisional.
    const ctx = canvas.getContext("2d");
    if (ctx) {
      drawScene(ctx, imgRef.current, navPose, navReactiveStop, {
        px: provisional.px,
        py: provisional.py,
        yaw,
      });
    }
  }

  async function confirmCanvasPose() {
    if (!provisional || provisional.yaw == null) return;
    const { wx, wy } = canvasToWorld(provisional.px, provisional.py);
    const ok = await postInitialPose(wx, wy, provisional.yaw);
    if (ok) {
      setProvisional(null);
      setSetMode(false);
    }
  }

  function cancelSetMode() {
    setProvisional(null);
    setSetMode(false);
  }

  async function applyNumericPose() {
    const x = Number(numX);
    const y = Number(numY);
    const yawDeg = Number(numYawDeg);
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(yawDeg)) return;
    const yaw = (yawDeg * Math.PI) / 180;
    const ok = await postInitialPose(x, y, yaw);
    if (ok) {
      setProvisional(null);
      setSetMode(false);
    }
  }

  // Load the map image once.
  useEffect(() => {
    const img = new Image();
    img.src = DEMO_MAP.src;
    img.onload = () => {
      imgRef.current = img;
      const ctx = canvasRef.current?.getContext("2d");
      if (ctx) drawScene(ctx, img, navPose, navReactiveStop, provisional);
    };
    imgRef.current = img;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redraw on every nav state change or provisional pose change.
  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) drawScene(ctx, imgRef.current, navPose, navReactiveStop, provisional);
  }, [navPose, navReactiveStop, provisional]);

  const zone: NavZone = navReactiveStop?.zone ?? "clear";
  const zoneLabel =
    zone === "danger" ? "DANGER" : zone === "slow" ? "SLOW" : "CLEAR";
  const chipColor =
    zone === "danger"
      ? "bg-red-500/20 text-red-200 border-red-500/40"
      : zone === "slow"
        ? "bg-amber-500/20 text-amber-200 border-amber-500/40"
        : "bg-emerald-500/20 text-emerald-200 border-emerald-500/40";

  const front = navReactiveStop?.front_distance_m;
  const frontLabel = typeof front === "number" ? `${front.toFixed(2)} m` : "—";

  const provHint =
    provisional == null
      ? "點地圖選起點"
      : provisional.yaw == null
        ? "再點一下選朝向"
        : "已選好，按下方套用";

  return (
    <section className="flex flex-col gap-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Nav Map
        </h3>
        <button
          type="button"
          onClick={() => (setMode ? cancelSetMode() : setSetMode(true))}
          disabled={posting}
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider transition-colors disabled:opacity-50 ${
            setMode
              ? "border-sky-500/50 bg-sky-500/20 text-sky-200 hover:bg-sky-500/30"
              : "border-border/50 bg-zinc-500/10 text-zinc-300 hover:bg-zinc-500/20"
          }`}
          title="點地圖設定 AMCL 起點（initialpose）"
        >
          {setMode ? "取消設定起點" : "設定起點"}
        </button>
      </div>
      {setMode && (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-sky-500/30 bg-sky-500/5 px-2 py-1.5">
          <span className="font-mono text-[10px] text-sky-200">{provHint}</span>
          {provisional?.yaw != null && (
            <button
              type="button"
              onClick={confirmCanvasPose}
              disabled={posting}
              className="rounded-md border border-emerald-500/40 bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-emerald-200 transition-colors hover:bg-emerald-500/30 disabled:opacity-50"
            >
              套用起點
            </button>
          )}
          {provisional != null && (
            <button
              type="button"
              onClick={() => setProvisional(null)}
              disabled={posting}
              className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-zinc-300 transition-colors hover:bg-zinc-500/20 disabled:opacity-50"
            >
              重選
            </button>
          )}
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider ${chipColor}`}
        >
          {zoneLabel}
        </span>
        <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-300">
          front {frontLabel}
        </span>
        {navPaused && (
          <span className="rounded-md border border-amber-500/40 bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-amber-200">
            paused
          </span>
        )}
        {!navPose && (
          <span className="rounded-md border border-border/50 bg-zinc-500/10 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
            no pose
          </span>
        )}
      </div>
      <div className="overflow-hidden rounded-lg border border-border/50 bg-zinc-900">
        <canvas
          ref={canvasRef}
          width={MAP_W}
          height={MAP_H}
          onClick={handleCanvasClick}
          onMouseMove={handleCanvasMove}
          style={{
            width: MAP_W * SCALE,
            height: MAP_H * SCALE,
            maxWidth: "100%",
            imageRendering: "pixelated",
            display: "block",
            cursor: setMode ? "crosshair" : "default",
          }}
        />
      </div>

      {setMode && (
        <div className="flex flex-col gap-1 rounded-md border border-border/50 bg-zinc-500/5 px-2 py-1.5">
          <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            數值輸入（備援）
          </span>
          <div className="flex flex-wrap items-end gap-2">
            <label className="flex flex-col gap-0.5">
              <span className="font-mono text-[9px] text-muted-foreground/70">x (m)</span>
              <input
                type="number"
                step="0.1"
                value={numX}
                onChange={(e) => setNumX(e.target.value)}
                className="h-6 w-16 rounded border border-border/50 bg-zinc-900 px-1.5 font-mono text-[11px] text-zinc-200 outline-none focus:border-sky-500/50"
              />
            </label>
            <label className="flex flex-col gap-0.5">
              <span className="font-mono text-[9px] text-muted-foreground/70">y (m)</span>
              <input
                type="number"
                step="0.1"
                value={numY}
                onChange={(e) => setNumY(e.target.value)}
                className="h-6 w-16 rounded border border-border/50 bg-zinc-900 px-1.5 font-mono text-[11px] text-zinc-200 outline-none focus:border-sky-500/50"
              />
            </label>
            <label className="flex flex-col gap-0.5">
              <span className="font-mono text-[9px] text-muted-foreground/70">yaw (°)</span>
              <input
                type="number"
                step="5"
                value={numYawDeg}
                onChange={(e) => setNumYawDeg(e.target.value)}
                className="h-6 w-16 rounded border border-border/50 bg-zinc-900 px-1.5 font-mono text-[11px] text-zinc-200 outline-none focus:border-sky-500/50"
              />
            </label>
            <button
              type="button"
              onClick={applyNumericPose}
              disabled={posting}
              className="h-6 rounded-md border border-sky-500/40 bg-sky-500/20 px-2 font-mono text-[10px] uppercase tracking-wider text-sky-200 transition-colors hover:bg-sky-500/30 disabled:opacity-50"
            >
              套用
            </button>
          </div>
        </div>
      )}
      <p className="text-[11px] text-muted-foreground/60 leading-relaxed">
        AMCL pose（三角形）+ 固定 goal（藍點）+ current→goal 直線。顏色跟
        reactive_stop zone 走（綠 clear / 黃 slow / 紅 danger）。read-only，
        無移動按鈕。底圖 = home_living_room v8。
      </p>
    </section>
  );
}
