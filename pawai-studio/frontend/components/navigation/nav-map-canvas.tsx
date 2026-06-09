"use client";

import { useEffect, useRef } from "react";
import { useStateStore } from "@/stores/state-store";
import type { NavPose, NavReactiveStop, NavZone } from "@/stores/state-store";

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

/** World metres → canvas pixels. y-flip happens exactly once. */
function worldToCanvas(wx: number, wy: number): { px: number; py: number } {
  const col = (wx - DEMO_MAP.originX) / DEMO_MAP.resolution;
  const rowBottom = (wy - DEMO_MAP.originY) / DEMO_MAP.resolution;
  return { px: col, py: MAP_H - 1 - rowBottom };
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

function drawScene(
  ctx: CanvasRenderingContext2D,
  img: HTMLImageElement | null,
  pose: NavPose | null,
  reactiveStop: NavReactiveStop | null,
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
}

export function NavMapCanvas() {
  const navPose = useStateStore((s) => s.navPose);
  const navReactiveStop = useStateStore((s) => s.navReactiveStop);
  const navPaused = useStateStore((s) => s.navPaused);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Load the map image once.
  useEffect(() => {
    const img = new Image();
    img.src = DEMO_MAP.src;
    img.onload = () => {
      imgRef.current = img;
      const ctx = canvasRef.current?.getContext("2d");
      if (ctx) drawScene(ctx, img, navPose, navReactiveStop);
    };
    imgRef.current = img;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Redraw on every nav state change.
  useEffect(() => {
    const ctx = canvasRef.current?.getContext("2d");
    if (ctx) drawScene(ctx, imgRef.current, navPose, navReactiveStop);
  }, [navPose, navReactiveStop]);

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

  return (
    <section className="flex flex-col gap-2">
      <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Nav Map
      </h3>
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
          style={{
            width: MAP_W * SCALE,
            height: MAP_H * SCALE,
            maxWidth: "100%",
            imageRendering: "pixelated",
            display: "block",
          }}
        />
      </div>
      <p className="text-[11px] text-muted-foreground/60 leading-relaxed">
        AMCL pose（三角形）+ 固定 goal（藍點）+ current→goal 直線。顏色跟
        reactive_stop zone 走（綠 clear / 黃 slow / 紅 danger）。read-only，
        無移動按鈕。底圖 = home_living_room v8。
      </p>
    </section>
  );
}
