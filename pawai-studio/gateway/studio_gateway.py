#!/usr/bin/env python3
"""Studio Gateway — ROS2 Bridge + Speech Bridge server.

Runs on Jetson. Subscribes to ROS2 perception topics, broadcasts to
browser via WebSocket. Also handles browser push-to-talk → ASR → ROS2.

Usage:
    source /opt/ros/humble/setup.zsh
    source install/setup.zsh
    python3 pawai-studio/gateway/studio_gateway.py
"""
from __future__ import annotations

import asyncio
import functools
import json
import math
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from std_msgs.msg import Bool, Empty, String
from geometry_msgs.msg import PoseWithCovarianceStamped

# Operator-controlled nav driving (S1 "move to scene"). go2_interfaces +
# rclpy.action are absent on WSL dev boxes — guard so py_compile / pytest
# still pass there. nav_start() fail-closes when GotoRelative is None.
try:
    from go2_interfaces.action import GotoRelative
    from rclpy.action import ActionClient
except ImportError:
    GotoRelative = None
    ActionClient = None

from asr_client import resample_to_wav16k, transcribe

# Lazy video imports — only needed on Jetson with cv2/cv_bridge
try:
    from video_bridge import encode_jpeg, FrameThrottle, VideoClients, VIDEO_TOPIC_MAP
    _VIDEO_AVAILABLE = True
except ImportError:
    _VIDEO_AVAILABLE = False
    VIDEO_TOPIC_MAP = {}  # type: ignore[assignment]

# Intent classifier — reuse from speech_processor (pure Python, no ROS2 dep)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".." / "speech_processor" / "speech_processor"))
from intent_classifier import IntentClassifier

# Access-control policy (S0 hardening) — pure module, env-gated, OFF by default.
from auth import (
    load_auth_config, requires_token, token_ok, token_query_ok, origin_ok,
)

# ── Config ───────────────────────────────────────────────────────
import os

PORT = int(os.getenv("GATEWAY_PORT", "8080"))
AUTH = load_auth_config()
# E.Mac/School pre-stage 2026-05-11: ASR_URL 改 env override 避免學校 Mac → Jetson
# 時 127.0.0.1 指 Mac 自己。沿用 PAWAI_ENABLE_S2TWP（line 57）env-aware pattern。
# 主環變 PAWAI_ASR_URL，向下相容 ASR_URL。
ASR_URL = os.getenv(
    "PAWAI_ASR_URL",
    os.getenv("ASR_URL", "http://127.0.0.1:8001/v1/audio/transcriptions"),
)
STATIC_DIR = Path(__file__).parent / "static"

# P1-3: ASR 簡→繁 — enable by default; set PAWAI_ENABLE_S2TWP=false to disable
ENABLE_S2TWP = os.getenv("PAWAI_ENABLE_S2TWP", "true").lower() == "true"

QOS_EVENT = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.VOLATILE,
    depth=10,
)

# Nav latched topics (/amcl_pose, /state/nav/paused) are published
# RELIABLE + TRANSIENT_LOCAL. Subscribing with QOS_EVENT (VOLATILE) is
# QoS-incompatible → the gateway would NEVER receive them (and rclpy does
# not warn). This profile is load-bearing — do not change to VOLATILE.
QOS_NAV_LATCHED = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    depth=1,
)
POSE_THROTTLE_S = 0.2  # /amcl_pose ~10Hz → throttle to 5Hz

# ROS2 topic → frontend source mapping
TOPIC_MAP: dict[str, str] = {
    "/state/perception/face":          "face",
    "/event/gesture_detected":         "gesture",
    "/event/pose_detected":            "pose",
    "/event/speech_intent_recognized": "speech",
    "/event/object_detected":          "object",
    "/state/pawai_brain":              "brain:state",
    "/brain/proposal":                 "brain:proposal",
    "/brain/skill_result":             "brain:skill_result",
    "/brain/conversation_trace":        "brain:conversation_trace",
    "/brain/conversation_trace_shadow": "brain:conversation_trace_shadow",
    # Plan E: decision-chain trace (bridge ONLY — persistence/export/panel
    # belong to the Studio Evidence Center plan, not here).
    "/brain/trace":                     "brain:trace",
}

FACE_THROTTLE_S = 0.5  # 10Hz → 2Hz
MAX_AUDIO_BYTES = 5 * 1024 * 1024  # 5MB payload cap for speech

# ── Operator-controlled nav driving (S1 "move to scene") ────────
# Conservative clamps for a REAL 12kg robot dog. distance ≥0.2 so a click
# never sends a sub-deadband micro-goal; ≤2.0 so one click never sends the
# dog across the room. yaw_offset ±π/2.
NAV_DISTANCE_MIN_M = 0.2
NAV_DISTANCE_MAX_M = 2.0
NAV_YAW_MAX_RAD = 1.57
NAV_DEFAULT_DISTANCE_M = 1.2
NAV_DANGER_ZONE = "danger"
NAV_SERVER_WAIT_S = 2.0
# rviz AMCL initial-pose default covariance diagonal (x, y var 0.25 m²;
# yaw var 0.06853 rad²). Off-diagonals zero.
NAV_INITIALPOSE_COV_X = 0.25
NAV_INITIALPOSE_COV_Y = 0.25
NAV_INITIALPOSE_COV_YAW = 0.06853892326654787


def _parse_tts_payload(raw: str) -> dict:
    """Parse /tts msg.data: JSON envelope {text, input_origin, source} or plain text.

    Returns dict with keys: text (str), origin (str, default 'tts'), source (str|None).
    """
    raw = (raw or "").strip()
    if not raw:
        return {"text": "", "origin": "tts", "source": None}

    # Try JSON envelope
    if raw.startswith("{"):
        try:
            envelope = json.loads(raw)
            if isinstance(envelope, dict) and isinstance(envelope.get("text"), str):
                return {
                    "text": envelope["text"],
                    "origin": envelope.get("input_origin") or "tts",
                    "source": envelope.get("source"),
                }
        except (json.JSONDecodeError, TypeError):
            pass  # fall through to plain text

    # Plain text fallback (backward compat with §5.2)
    return {"text": raw, "origin": "tts", "source": None}


def build_tts_event(text: str, origin: str = "tts", source: str | None = None) -> dict:
    """Wrap /tts message into PawAIEvent envelope."""
    data: dict = {
        "text": text,
        "phase": "speaking",
        "origin": origin,
    }
    if source:
        data["source"] = source
    return {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().astimezone().isoformat(),
        "source": "tts",
        "event_type": "tts_speaking",
        "data": data,
    }


# ── WebSocket Connection Manager ────────────────────────────────
class ConnectionManager:
    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, data: dict) -> None:
        for ws in list(self.active):
            try:
                await ws.send_json(data)
            except Exception:
                if ws in self.active:
                    self.active.remove(ws)


ws_manager = ConnectionManager()
video_clients = VideoClients() if _VIDEO_AVAILABLE else None


# ── ROS2 Node ────────────────────────────────────────────────────
class GatewayNode(Node):
    def __init__(self, loop: asyncio.AbstractEventLoop):
        super().__init__("studio_gateway_node")
        self._loop = loop
        self._last_face_broadcast = 0.0
        self._last_pose_broadcast = 0.0
        # Capability gate state — tri-state (true / false / unknown).
        # `None` = no message ever received (unknown). Once a Bool arrives we
        # store True / False and surface it via /api/capability + /ws/events.
        self._cap_state: dict[str, bool | None] = {
            "nav_ready": None,
            "depth_clear": None,
        }

        # Publisher — speech intent (browser → ROS2)
        self.speech_pub = self.create_publisher(
            String, "/event/speech_intent_recognized", QOS_EVENT
        )
        self.skill_request_pub = self.create_publisher(
            String, "/brain/skill_request", QOS_EVENT
        )
        self.text_input_pub = self.create_publisher(
            String, "/brain/text_input", QOS_EVENT
        )
        self._reset_pub = self.create_publisher(
            Empty, "/brain/reset_context", 10
        )
        # Demo-recording P0 (6/9 plan): Studio 手勢開關 → brain_node 的
        # /brain/gesture_enabled Bool subscriber（RELIABLE depth-10 VOLATILE，
        # rclpy depth=10 預設 QoS 即相容）。data=true → 手勢啟用。
        self._gesture_enabled_pub = self.create_publisher(
            Bool, "/brain/gesture_enabled", 10
        )
        # 最後一次發布值的 cache（None = 本 session 尚未有人切換過）。
        self._gesture_enabled_last: bool | None = None

        # ── Operator-controlled nav driving (S1) ────────────────────
        # /initialpose set from a frontend map click; /nav/goto_relative
        # action drives a short relative walk. The danger-cancel hook in
        # _on_reactive_stop_status CANCELS the goal on obstacle so the dog
        # STAYS stopped — operator must click 繼續 to re-send (6/9 HITL
        # lunge finding: NO auto-resume in tight space).
        self._initialpose_pub = self.create_publisher(
            PoseWithCovarianceStamped, "/initialpose", 10
        )
        self._nav_client = (
            ActionClient(self, GotoRelative, "/nav/goto_relative")
            if (ActionClient and GotoRelative)
            else None
        )
        # nav-control state — mutated from FastAPI handler threads AND the
        # reactive_stop ROS callback thread → ALL access under _nav_lock.
        # states: idle | running | paused_confirm | done
        # goal_handle holds the live ClientGoalHandle; goal_token is a fresh
        # object per goal so stale callbacks (late CANCELED after preempt)
        # can no-op via identity check.
        self._nav_lock = threading.Lock()
        self._nav_ctrl: dict = {
            "state": "idle",
            "goal_handle": None,
            "goal_token": None,
            "remaining_m": 0.0,
            "target_m": 0.0,
            "danger_cancel": False,
        }

        # Subscribers — ROS2 → browser
        for topic, source in TOPIC_MAP.items():
            self.create_subscription(
                String, topic,
                lambda msg, s=source: self._on_ros2_msg(s, msg),
                QOS_EVENT,
            )

        # /tts — plain text from llm_bridge_node / interaction_executive_node
        self.create_subscription(
            String, "/tts", self._on_tts_msg, QOS_EVENT
        )

        # Capability Bool subscribers (Phase B — Trace Drawer Nav/Depth Gate).
        self.create_subscription(
            Bool, "/capability/nav_ready",
            lambda msg: self._on_capability_msg("nav_ready", msg),
            QOS_EVENT,
        )
        self.create_subscription(
            Bool, "/capability/depth_clear",
            lambda msg: self._on_capability_msg("depth_clear", msg),
            QOS_EVENT,
        )

        # ── Nav panel subscribers (Task A — read-only, no publisher) ──
        # /amcl_pose & /state/nav/paused are latched → MUST use QOS_NAV_LATCHED.
        # /state/reactive_stop/status is VOLATILE depth=10 → QOS_EVENT is fine.
        self.create_subscription(
            PoseWithCovarianceStamped, "/amcl_pose",
            self._on_amcl_pose, QOS_NAV_LATCHED,
        )
        self.create_subscription(
            String, "/state/reactive_stop/status",
            self._on_reactive_stop_status, QOS_EVENT,
        )
        self.create_subscription(
            Bool, "/state/nav/paused",
            self._on_nav_paused, QOS_NAV_LATCHED,
        )

        # ── Video subscribers — ROS2 Image → JPEG → WebSocket binary ──
        self._video_throttles: dict = {}
        self._cv_bridge_ok = False

        if not _VIDEO_AVAILABLE:
            self.get_logger().info(
                "video_bridge not available (cv2 missing) — video endpoints disabled"
            )
        else:
            self._cv_bridge_ok = True
            try:
                from cv_bridge import CvBridge
                self._cv_bridge = CvBridge()
            except ImportError:
                self._cv_bridge = None
                self._cv_bridge_ok = False
                self.get_logger().warn(
                    "cv_bridge not available — video endpoints will show NO SIGNAL"
                )

            if self._cv_bridge_ok:
                from sensor_msgs.msg import Image as RosImage
                video_qos = QoSProfile(
                    reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                    depth=1,
                )
                for source, topic in VIDEO_TOPIC_MAP.items():
                    self._video_throttles[source] = FrameThrottle()
                    self.create_subscription(
                        RosImage, topic,
                        lambda msg, s=source: self._on_video_frame(s, msg),
                        video_qos,
                    )
                self.get_logger().info(
                    f"Video bridge ready — subscribed to {len(VIDEO_TOPIC_MAP)} image topics"
                )

        self.get_logger().info(
            f"Studio Gateway ROS2 node ready — subscribed to {len(TOPIC_MAP)} String topics "
            "+ /tts + 2 capability Bool topics"
        )

    def _on_capability_msg(self, name: str, msg: Bool) -> None:
        value = bool(msg.data)
        self._cap_state[name] = value
        # Push to browser via /ws/events as a synthetic event.
        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(),
            "source": "capability",
            "event_type": f"capability_{name}",
            "data": {"name": name, "value": value, "tri_state": "true" if value else "false"},
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(envelope), self._loop)

    def capability_snapshot(self) -> dict[str, str]:
        """Return tri-state snapshot of all capabilities for /api/capability."""
        out: dict[str, str] = {}
        for name, val in self._cap_state.items():
            if val is None:
                out[name] = "unknown"
            else:
                out[name] = "true" if val else "false"
        return out

    # ── Nav panel (Task A) ──────────────────────────────────────────
    @staticmethod
    def _quat_to_yaw(qz: float, qw: float, qx: float = 0.0, qy: float = 0.0) -> float:
        """Yaw (rad) from a quaternion. Pure math, no ROS dependency."""
        import math
        return math.atan2(2.0 * (qw * qz + qx * qy), 1.0 - 2.0 * (qy * qy + qz * qz))

    def _broadcast_nav(self, event_type: str, data: dict) -> None:
        """Wrap nav data in a synthetic event envelope and broadcast.

        source is always "nav"; event_type is a short name
        (pose / reactive_stop / paused) the frontend `case "nav"` keys off.
        """
        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(),
            "source": "nav",
            "event_type": event_type,
            "data": data,
        }
        asyncio.run_coroutine_threadsafe(ws_manager.broadcast(envelope), self._loop)

    def _on_amcl_pose(self, msg: PoseWithCovarianceStamped) -> None:
        now = time.monotonic()
        if now - self._last_pose_broadcast < POSE_THROTTLE_S:
            return
        self._last_pose_broadcast = now
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        c = msg.pose.covariance
        self._broadcast_nav("pose", {
            "x": round(float(p.x), 4),
            "y": round(float(p.y), 4),
            "yaw": round(self._quat_to_yaw(q.z, q.w, q.x, q.y), 4),
            "covariance_xy": round(float(c[0] + c[7]), 5),
        })

    def _on_reactive_stop_status(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError):
            return
        zone = payload.get("zone")
        obstacle_distance = payload.get("obstacle_distance")
        zone_str = zone if isinstance(zone, str) else "clear"
        self._broadcast_nav("reactive_stop", {
            "zone": zone_str,
            "obstacle_distance": (
                float(obstacle_distance)
                if isinstance(obstacle_distance, (int, float))
                else None
            ),
            "reactive_stop_active": bool(payload.get("reactive_stop_active", False)),
            "nav_paused": bool(payload.get("nav_paused", False)),
        })
        # ── DANGER auto-cancel hook (runs in ROS executor thread) ──
        # reactive_stop handles the PHYSICAL stop. We additionally CANCEL the
        # nav goal so the dog will NOT auto-resume when the obstacle clears.
        # Operator must click 繼續 → nav_resume() re-sends a fresh goto.
        if zone_str == NAV_DANGER_ZONE:
            self._nav_danger_cancel()

    def _nav_danger_cancel(self) -> None:
        """Obstacle entered danger zone while running → cancel + paused_confirm.

        cancel_goal_async is non-blocking (safe in the ROS callback thread).
        Holds _nav_lock; broadcasts outside? No — _broadcast_nav only schedules
        a coroutine on the loop, it does not touch _nav_ctrl, so calling it
        under the lock is fine and keeps the state snapshot consistent.
        """
        with self._nav_lock:
            if self._nav_ctrl["state"] != "running":
                return
            handle = self._nav_ctrl.get("goal_handle")
            # Invalidate token first so the (eventual) CANCELED result no-ops.
            self._nav_ctrl["goal_token"] = None
            self._nav_ctrl["goal_handle"] = None
            self._nav_ctrl["state"] = "paused_confirm"
            self._nav_ctrl["danger_cancel"] = True
            target = self._nav_ctrl["target_m"]
            remaining = self._nav_ctrl["remaining_m"]
        if handle is not None:
            try:
                handle.cancel_goal_async()
            except Exception as exc:  # pragma: no cover — best-effort cancel
                self.get_logger().warn(f"nav danger cancel failed: {exc}")
        self.get_logger().warn(
            "Nav DANGER → goal cancelled, paused_confirm (operator must resume)"
        )
        self._broadcast_nav("nav_control", {
            "state": "paused_confirm",
            "target_m": round(target, 3),
            "remaining_m": round(remaining, 3),
            "reason": "obstacle",
        })

    # ── Operator-controlled nav driving — public API (FastAPI threads) ──
    def publish_initialpose(self, x: float, y: float, yaw: float) -> dict:
        """Publish /initialpose for AMCL (from a frontend map click)."""
        msg = PoseWithCovarianceStamped()
        msg.header.frame_id = "map"
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.pose.pose.position.x = float(x)
        msg.pose.pose.position.y = float(y)
        msg.pose.pose.position.z = 0.0
        msg.pose.pose.orientation.z = math.sin(float(yaw) / 2.0)
        msg.pose.pose.orientation.w = math.cos(float(yaw) / 2.0)
        # rviz AMCL initial-pose default covariance: diag(x, y, 0,0,0, yaw).
        cov = [0.0] * 36
        cov[0] = NAV_INITIALPOSE_COV_X      # x var
        cov[7] = NAV_INITIALPOSE_COV_Y      # y var
        cov[35] = NAV_INITIALPOSE_COV_YAW   # yaw var
        msg.pose.covariance = cov
        self._initialpose_pub.publish(msg)
        self.get_logger().info(
            f"Published /initialpose x={x:.3f} y={y:.3f} yaw={yaw:.3f}"
        )
        return {"ok": True, "x": float(x), "y": float(y), "yaw": float(yaw)}

    def _nav_broadcast_ctrl(self, snapshot: dict, reason: str | None = None) -> None:
        data = {
            "state": snapshot["state"],
            "target_m": round(snapshot["target_m"], 3),
            "remaining_m": round(snapshot["remaining_m"], 3),
        }
        if reason:
            data["reason"] = reason
        self._broadcast_nav("nav_control", data)

    def _nav_send_goto(self, distance: float, yaw_offset: float) -> object:
        """Build + dispatch a GotoRelative goal; return the fresh goal_token.

        Caller must hold _nav_lock and have already set state="running".
        Non-blocking: callbacks bound to the token via functools.partial.
        """
        goal = GotoRelative.Goal()
        goal.distance = float(distance)
        goal.yaw_offset = float(yaw_offset)
        goal.max_speed = 0.0  # advisory — actual speed managed by nav stack
        token = object()
        self._nav_ctrl["goal_token"] = token
        self._nav_ctrl["goal_handle"] = None
        send_future = self._nav_client.send_goal_async(
            goal,
            feedback_callback=functools.partial(self._on_nav_feedback, token),
        )
        send_future.add_done_callback(
            functools.partial(self._on_nav_goal_response, token)
        )
        return token

    def nav_start(self, distance: float = NAV_DEFAULT_DISTANCE_M,
                  yaw_offset: float = 0.0) -> dict:
        """開始 — dispatch a short relative goto. Fail-closed if no server."""
        if self._nav_client is None:
            return {"ok": False, "error": "nav_server_unavailable"}
        if not self._nav_client.wait_for_server(timeout_sec=NAV_SERVER_WAIT_S):
            return {"ok": False, "error": "nav_server_unavailable"}
        distance = max(NAV_DISTANCE_MIN_M, min(NAV_DISTANCE_MAX_M, float(distance)))
        yaw_offset = max(-NAV_YAW_MAX_RAD, min(NAV_YAW_MAX_RAD, float(yaw_offset)))
        with self._nav_lock:
            self._nav_ctrl["state"] = "running"
            self._nav_ctrl["target_m"] = distance
            self._nav_ctrl["remaining_m"] = distance
            self._nav_ctrl["danger_cancel"] = False
            self._nav_send_goto(distance, yaw_offset)
            snapshot = dict(self._nav_ctrl)
        self.get_logger().info(
            f"Nav START distance={distance:.2f}m yaw={yaw_offset:.2f}rad"
        )
        self._nav_broadcast_ctrl(snapshot)
        return {"ok": True, "state": "running",
                "target_m": round(distance, 3), "remaining_m": round(distance, 3)}

    def nav_resume(self) -> dict:
        """繼續 — operator-confirmed resume. Re-send goto for remaining_m.

        Only valid from paused_confirm. If the obstacle is still in the danger
        zone, the danger hook will immediately re-pause — that is correct/safe.
        """
        if self._nav_client is None:
            return {"ok": False, "error": "nav_server_unavailable"}
        with self._nav_lock:
            if self._nav_ctrl["state"] != "paused_confirm":
                return {"ok": False, "error": "not_paused",
                        "state": self._nav_ctrl["state"]}
            remaining = self._nav_ctrl["remaining_m"]
            if remaining < NAV_DISTANCE_MIN_M:
                # Already effectively there — finish rather than send a
                # sub-deadband micro-goal the Go2 would silently ignore.
                self._nav_ctrl["state"] = "done"
                self._nav_ctrl["goal_token"] = None
                self._nav_ctrl["goal_handle"] = None
                snapshot = dict(self._nav_ctrl)
                self._nav_broadcast_ctrl(snapshot, reason="remaining_below_min")
                return {"ok": True, "state": "done",
                        "remaining_m": round(remaining, 3)}
            self._nav_ctrl["state"] = "running"
            self._nav_ctrl["danger_cancel"] = False
            self._nav_send_goto(remaining, 0.0)
            snapshot = dict(self._nav_ctrl)
        self.get_logger().info(f"Nav RESUME (operator) remaining={remaining:.2f}m")
        self._nav_broadcast_ctrl(snapshot, reason="operator_resume")
        return {"ok": True, "state": "running", "remaining_m": round(remaining, 3)}

    def nav_stop(self) -> dict:
        """停止 — cancel everything, back to idle."""
        with self._nav_lock:
            handle = self._nav_ctrl.get("goal_handle")
            self._nav_ctrl["goal_token"] = None
            self._nav_ctrl["goal_handle"] = None
            self._nav_ctrl["state"] = "idle"
            self._nav_ctrl["danger_cancel"] = False
            snapshot = dict(self._nav_ctrl)
        if handle is not None:
            try:
                handle.cancel_goal_async()
            except Exception as exc:  # pragma: no cover — best-effort cancel
                self.get_logger().warn(f"nav stop cancel failed: {exc}")
        self.get_logger().info("Nav STOP → idle")
        self._nav_broadcast_ctrl(snapshot, reason="operator_stop")
        return {"ok": True, "state": "idle"}

    def nav_control_snapshot(self) -> dict:
        with self._nav_lock:
            return {
                "state": self._nav_ctrl["state"],
                "target_m": round(self._nav_ctrl["target_m"], 3),
                "remaining_m": round(self._nav_ctrl["remaining_m"], 3),
                "danger_cancel": bool(self._nav_ctrl["danger_cancel"]),
            }

    # ── Nav action callbacks (run in ROS executor thread) ──────────
    def _on_nav_goal_response(self, token, future) -> None:
        # token identity guard — ignore if a newer goal / stop / danger-cancel
        # has superseded this one (stale callback after preempt).
        try:
            goal_handle = future.result()
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f"nav goal send error: {exc}")
            with self._nav_lock:
                if self._nav_ctrl["goal_token"] is token:
                    self._nav_ctrl["state"] = "idle"
                    self._nav_ctrl["goal_token"] = None
                    snapshot = dict(self._nav_ctrl)
                else:
                    return
            self._nav_broadcast_ctrl(snapshot, reason="send_error")
            return
        with self._nav_lock:
            if self._nav_ctrl["goal_token"] is not token:
                return  # superseded
            if not getattr(goal_handle, "accepted", False):
                self._nav_ctrl["state"] = "idle"
                self._nav_ctrl["goal_token"] = None
                self._nav_ctrl["goal_handle"] = None
                snapshot = dict(self._nav_ctrl)
                self.get_logger().warn("nav goal rejected by /nav/goto_relative")
                self._nav_broadcast_ctrl(snapshot, reason="rejected")
                return
            self._nav_ctrl["goal_handle"] = goal_handle
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(
            functools.partial(self._on_nav_result, token)
        )

    def _on_nav_feedback(self, token, feedback_msg) -> None:
        """Track remaining distance from feedback.distance_to_goal."""
        fb = getattr(feedback_msg, "feedback", None)
        if fb is None:
            return
        dist_to_goal = getattr(fb, "distance_to_goal", None)
        if dist_to_goal is None:
            return
        with self._nav_lock:
            if self._nav_ctrl["goal_token"] is not token:
                return
            self._nav_ctrl["remaining_m"] = max(0.0, float(dist_to_goal))

    def _on_nav_result(self, token, future) -> None:
        try:
            result = future.result().result
        except Exception as exc:  # noqa: BLE001
            self.get_logger().warn(f"nav result error: {exc}")
            return
        success = bool(getattr(result, "success", False))
        with self._nav_lock:
            # Stale-result guard: a danger-cancel / stop has already moved us
            # to paused_confirm / idle (token cleared). Do NOT flip that.
            if self._nav_ctrl["goal_token"] is not token:
                return
            if self._nav_ctrl["state"] != "running":
                return
            if success:
                self._nav_ctrl["state"] = "done"
                self._nav_ctrl["remaining_m"] = 0.0
                reason = "reached"
            else:
                self._nav_ctrl["state"] = "idle"
                reason = "failed"
            self._nav_ctrl["goal_token"] = None
            self._nav_ctrl["goal_handle"] = None
            snapshot = dict(self._nav_ctrl)
        self._nav_broadcast_ctrl(snapshot, reason=reason)

    def _on_nav_paused(self, msg: Bool) -> None:
        self._broadcast_nav("paused", {"paused": bool(msg.data)})

    def publish_speech_event(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        self.speech_pub.publish(msg)
        self.get_logger().info(
            f"Published speech event: intent={payload.get('intent')} "
            f"text={payload.get('text')!r}"
        )

    def _on_ros2_msg(self, source: str, msg: String) -> None:
        """Transform ROS2 JSON → PawAIEvent envelope and broadcast."""
        try:
            payload = json.loads(msg.data)
        except (json.JSONDecodeError, TypeError):
            return

        # Face throttle: 10Hz → 2Hz
        if source == "face":
            now = time.monotonic()
            if now - self._last_face_broadcast < FACE_THROTTLE_S:
                return
            self._last_face_broadcast = now

        data = dict(payload)
        if source.startswith("brain:"):
            event_source = "brain"
            event_type = source.split(":", 1)[1]
        else:
            event_source = source
            event_type = data.pop("event_type", f"{source}_update")

        # ── Field transforms for frontend dispatch rules ──
        # gesture: frontend checks "status" in data
        if source == "gesture" and "gesture" in data:
            data.setdefault("current_gesture", data.get("gesture"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        # pose: frontend checks "current_pose" or "status" in data
        if source == "pose" and "pose" in data:
            data.setdefault("current_pose", data.get("pose"))
            data.setdefault("active", True)
            data.setdefault("status", "active")

        # speech: frontend checks "phase" in data
        if source == "speech":
            data.setdefault("phase", "listening")

        # face: pass-through (already has face_count, tracks)
        # object: pass-through (P1 adds frontend dispatch)

        envelope = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now().astimezone().isoformat(),
            "source": event_source,
            "event_type": event_type,
            "data": data,
        }

        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(envelope), self._loop
        )

    def _on_tts_msg(self, msg: String) -> None:
        """Parse /tts msg (plain text or JSON envelope) and broadcast."""
        parsed = _parse_tts_payload(msg.data)
        if not parsed["text"]:
            return
        envelope = build_tts_event(
            text=parsed["text"],
            origin=parsed["origin"],
            source=parsed["source"],
        )
        asyncio.run_coroutine_threadsafe(
            ws_manager.broadcast(envelope), self._loop
        )

    def publish_skill_request(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.skill_request_pub.publish(msg)

    def publish_text_input(self, payload: dict) -> None:
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.text_input_pub.publish(msg)

    def publish_reset_context(self) -> None:
        """P1-2: Publish Empty to /brain/reset_context to clear conversation state."""
        self._reset_pub.publish(Empty())
        self.get_logger().info("Published reset_context to /brain/reset_context")

    def publish_gesture_enabled(self, enabled: bool) -> None:
        """Demo P0: publish Bool to /brain/gesture_enabled + cache last value."""
        msg = Bool()
        msg.data = bool(enabled)
        self._gesture_enabled_pub.publish(msg)
        self._gesture_enabled_last = bool(enabled)
        self.get_logger().info(
            f"Published gesture_enabled={enabled} to /brain/gesture_enabled"
        )

    def gesture_enabled_snapshot(self) -> bool | None:
        """Last value published via Studio this session (None = untouched)."""
        return self._gesture_enabled_last

    def _on_video_frame(self, source: str, msg) -> None:
        """ROS2 Image callback → JPEG encode → broadcast to video clients."""
        if video_clients is None:
            return

        throttle = self._video_throttles.get(source)
        if throttle and not throttle.should_send():
            return

        if not video_clients.get(source):
            return

        try:
            frame = self._cv_bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().warn(f"cv_bridge convert failed for {source}: {e}")
            return

        jpeg = encode_jpeg(frame)
        if jpeg is None:
            return

        asyncio.run_coroutine_threadsafe(
            video_clients.broadcast_bytes(source, jpeg), self._loop
        )


# ── FastAPI App ──────────────────────────────────────────────────
node: GatewayNode | None = None
classifier: IntentClassifier | None = None


class SkillRequestPayload(BaseModel):
    skill: str
    args: dict = {}
    request_id: str | None = None


class TextInputPayload(BaseModel):
    text: str
    request_id: str | None = None


class GestureEnabledPayload(BaseModel):
    enabled: bool


class NavInitialPosePayload(BaseModel):
    x: float
    y: float
    yaw: float


class NavStartPayload(BaseModel):
    distance: float = NAV_DEFAULT_DISTANCE_M
    yaw_offset: float = 0.0


def _spin_ros2(ros_node: Node) -> None:
    try:
        rclpy.spin(ros_node)
    except Exception:
        pass  # ExternalShutdownException on clean exit


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    global node, classifier
    rclpy.init()
    loop = asyncio.get_running_loop()
    node = GatewayNode(loop)
    classifier = IntentClassifier()
    spin_thread = threading.Thread(target=_spin_ros2, args=(node,), daemon=True)
    spin_thread.start()
    yield
    if node:
        node.destroy_node()
    rclpy.try_shutdown()


app = FastAPI(title="PawAI Studio Gateway", lifespan=lifespan)

# CORS — Studio frontend at laptop IP (e.g. 100.101.41.4:3000) POSTs to
# Gateway at Jetson IP (192.168.0.222:8080). WebSocket bypasses CORS so
# /ws/* worked, but /api/text_input was blocked by browser preflight.
# 5/7 night fix per Roy's "Brain 文字通道未連線" report.
# S0 hardening: allow_origins is the GATEWAY_ALLOWED_ORIGINS allowlist when set,
# else the legacy ["*"] (unchanged demo behaviour). See auth.py.
app.add_middleware(
    CORSMiddleware,
    allow_origins=AUTH.cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Access control (S0 hardening, env-gated — OFF unless env set) ──────────
@app.middleware("http")
async def _access_control(request, call_next):
    """Browser-Origin allowlist + Bearer token on state-changing methods.
    Both checks are no-ops unless GATEWAY_ALLOWED_ORIGINS / GATEWAY_AUTH_TOKEN
    are set, so default behaviour is byte-identical to the pre-hardening gateway.
    OPTIONS (CORS preflight) and GET/HEAD are never token-gated."""
    if AUTH.origin_check_enabled:
        if not origin_ok(request.headers.get("origin"), AUTH.allowed_origins):
            return JSONResponse({"error": "origin not allowed"}, status_code=403)
    if AUTH.auth_enabled and requires_token(request.method):
        if not token_ok(request.headers.get("authorization"), AUTH.token):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


async def _ws_authorized(websocket) -> bool:
    """WebSocket-handshake guard mirroring _access_control: Origin allowlist +
    `?token=` query param. No-op unless the matching env is set."""
    if AUTH.origin_check_enabled:
        if not origin_ok(websocket.headers.get("origin"), AUTH.allowed_origins):
            return False
    if AUTH.auth_enabled:
        if not token_query_ok(websocket.query_params.get("token"), AUTH.token):
            return False
    return True


# ── Static & Health ─────────────────────────────────────────────

@app.get("/speech")
async def speech_page():
    return FileResponse(STATIC_DIR / "speech.html")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "node": node is not None,
        "ws_clients": len(ws_manager.active),
        "subscriptions": list(TOPIC_MAP.keys()),
    }


@app.post("/api/skill_request")
async def post_skill_request(payload: SkillRequestPayload):
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    request_id = payload.request_id or f"req-{int(time.time() * 1000)}"
    msg = {
        "skill": payload.skill,
        "args": payload.args or {},
        "request_id": request_id,
        "source": "studio_button",
        "created_at": time.time(),
    }
    node.publish_skill_request(msg)
    return {"ok": True, "request_id": request_id}


# ── Skill Registry / Capability / Plan Mode (Phase B B5a) ──────

# In-memory plan mode flag. "A" = full skill stack, "B" = canned-script Demo.
# Studio toggles this; brain_node reads via REST or future ROS topic.
_PLAN_MODE: dict[str, str] = {"mode": "A"}


def _serialize_skill_registry() -> dict:
    """Read SKILL_REGISTRY from interaction_executive package and return JSON.

    Imported lazily so the gateway still boots if the ROS package is not on
    PYTHONPATH (e.g. during pytest of the gateway in isolation).
    """
    try:
        from interaction_executive.skill_contract import SKILL_REGISTRY
    except ImportError as exc:
        return {"ok": False, "error": f"interaction_executive import failed: {exc}"}

    skills = []
    for name, c in SKILL_REGISTRY.items():
        skills.append(
            {
                "name": name,
                "bucket": c.bucket,
                "static_enabled": c.static_enabled,
                "enabled_when_blocked": bool(c.enabled_when),
                "priority_class": int(c.priority_class),
                "cooldown_s": c.cooldown_s,
                "timeout_s": c.timeout_s,
                "safety_requirements": list(c.safety_requirements),
                "fallback_skill": c.fallback_skill,
                "requires_confirmation": c.requires_confirmation,
                "risk_level": c.risk_level,
                "ui_style": c.ui_style,
                "description": c.description,
                "args_schema": c.args_schema,
                "step_count": len(c.steps),
            }
        )
    by_bucket = {"active": 0, "hidden": 0, "disabled": 0, "retired": 0}
    for s in skills:
        by_bucket[s["bucket"]] = by_bucket.get(s["bucket"], 0) + 1
    return {"ok": True, "total": len(skills), "by_bucket": by_bucket, "skills": skills}


@app.get("/api/skill_registry")
async def get_skill_registry():
    return _serialize_skill_registry()


@app.get("/api/capability")
async def get_capability():
    """Return tri-state snapshot of capability gates (Nav / Depth)."""
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return {"ok": True, "capabilities": node.capability_snapshot()}


# ── Baseline Scoreboard (read-only frozen snapshot, issue #76) ──────
# Reads a frozen baseline_snapshot.json; NO live recompute, NO runtime
# Brain gate. Path from PAWAI_SCOREBOARD_PATH (env override) else the repo
# default artifacts/baseline/baseline_snapshot.json. Mirrors the resolution
# in tools/pawai_cli/pawai_cli/readiness.py.

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_SCOREBOARD_REL = Path("artifacts/baseline/baseline_snapshot.json")


def _scoreboard_path() -> Path:
    override = os.environ.get("PAWAI_SCOREBOARD_PATH")
    if override:
        p = Path(override).expanduser()
        return p if p.is_absolute() else _REPO_ROOT / p
    return _REPO_ROOT / _DEFAULT_SCOREBOARD_REL


def _read_scoreboard(path: Path) -> dict:
    """Return a UI-ready scoreboard payload with explicit provenance.

    provenance:
      - "missing": file absent or unreadable/invalid JSON
      - "frozen":  valid snapshot read from disk (always frozen — never live recompute)
    last_tested_at is the snapshot-level timestamp (no per-capability time exists).
    """
    if not path.exists():
        return {
            "provenance": "missing",
            "backend": "live",
            "source_path": str(path),
            "capabilities": [],
        }
    try:
        snap = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {
            "provenance": "missing",
            "backend": "live",
            "source_path": str(path),
            "capabilities": [],
        }

    timestamp = snap.get("timestamp")
    caps_in = snap.get("capabilities", {})
    capabilities = []
    for cap_id, cap in caps_in.items():
        capabilities.append({
            "capability_id": cap.get("capability_id", cap_id),
            "grade": cap.get("grade"),
            "failure_reason": cap.get("failure_reason", ""),
            "brain_allowed": cap.get("brain_allowed"),
            "last_tested_at": timestamp,
        })
    return {
        "provenance": "frozen",
        "backend": "live",
        "source_path": str(path),
        "schema_version": snap.get("schema_version"),
        "run_trusted": snap.get("run_trusted"),
        "version_mismatch": snap.get("version_mismatch"),
        "git_commit": snap.get("git_commit") or snap.get("wsl_commit"),
        "generated_at": timestamp,
        "capabilities": capabilities,
    }


@app.get("/api/scoreboard")
async def get_scoreboard():
    """Read-only frozen baseline_snapshot.json (issue #76). No live recompute."""
    return _read_scoreboard(_scoreboard_path())


class PlanModePayload(BaseModel):
    mode: str  # "A" or "B"


@app.get("/api/plan_mode")
async def get_plan_mode():
    return {"ok": True, "mode": _PLAN_MODE["mode"]}


@app.post("/api/plan_mode")
async def post_plan_mode(payload: PlanModePayload):
    mode = payload.mode.strip().upper()
    if mode not in {"A", "B"}:
        return {"ok": False, "error": "mode must be 'A' or 'B'"}
    _PLAN_MODE["mode"] = mode
    return {"ok": True, "mode": mode}


@app.post("/api/text_input")
async def post_text_input(payload: TextInputPayload):
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    request_id = payload.request_id or f"txt-{int(time.time() * 1000)}"
    text = payload.text
    # 5/9 review: Studio chat-panel typing path was missing s2twp normalization.
    # User typing is normally already 繁體, but pasted content / mobile keyboard /
    # mixed input can leak 簡體; normalize defensively for consistency with the
    # two ASR paths (stt_intent_node + /ws/speech).
    if ENABLE_S2TWP and text:
        try:
            from text_normalization import to_traditional_tw
            text = to_traditional_tw(text)
        except Exception:
            pass  # silent fallback to original text
    msg = {
        "text": text,
        "request_id": request_id,
        "source": "studio_text",
        "created_at": time.time(),
    }
    node.publish_text_input(msg)
    return {"ok": True, "request_id": request_id, "text": text}


@app.post("/api/reset")
async def post_reset():
    """P1-2: Clear conversation context — resets ConversationMemory + cancels PendingConfirm."""
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    node.publish_reset_context()
    return {"ok": True}


@app.post("/api/gesture_enabled")
async def post_gesture_enabled(payload: GestureEnabledPayload):
    """Demo-recording P0: Studio 手勢開關 → /brain/gesture_enabled Bool。

    publish + cache + 廣播 brain:gesture_enabled 事件到 /ws/events，
    讓所有開啟的 Studio 視窗同步 toggle 狀態。
    """
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    node.publish_gesture_enabled(payload.enabled)
    await ws_manager.broadcast({
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().astimezone().isoformat(),
        "source": "brain",
        "event_type": "gesture_enabled",
        "data": {"enabled": payload.enabled},
    })
    return {"ok": True, "enabled": payload.enabled}


@app.get("/api/gesture_enabled")
async def get_gesture_enabled():
    """回傳 gateway cache 的手勢開關值（null = 本 session 尚未切換過）。

    注意：這是 gateway 端 cache，不是 brain 端真值 — brain yaml 預設
    gesture_enabled: false，所以 null 應視為 OFF。
    """
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready", "enabled": None}
    return {"ok": True, "enabled": node.gesture_enabled_snapshot()}


# ── Operator-controlled nav driving (S1 "move to scene") ────────
# Workflow: /api/nav/initialpose (map click) → /api/nav/start (開始) →
# obstacle in danger zone auto-cancels → paused_confirm → /api/nav/resume
# (繼續, operator-confirmed) → /api/nav/stop (停止). NO auto-resume.

@app.post("/api/nav/initialpose")
async def post_nav_initialpose(payload: NavInitialPosePayload):
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return node.publish_initialpose(payload.x, payload.y, payload.yaw)


@app.post("/api/nav/start")
async def post_nav_start(payload: NavStartPayload):
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return node.nav_start(payload.distance, payload.yaw_offset)


@app.post("/api/nav/resume")
async def post_nav_resume():
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return node.nav_resume()


@app.post("/api/nav/stop")
async def post_nav_stop():
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return node.nav_stop()


@app.get("/api/nav/control")
async def get_nav_control():
    if node is None:
        return {"ok": False, "error": "ros_node_not_ready"}
    return {"ok": True, **node.nav_control_snapshot()}


# ── WebSocket: Event Broadcast (ROS2 → Browser) ────────────────

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    """Broadcast ROS2 perception events to all connected browsers."""
    if not await _ws_authorized(ws):
        await ws.close(code=1008)
        return
    await ws_manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ping
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ── WebSocket: Video Streams (ROS2 Image → Browser) ──────────

@app.websocket("/ws/video/{source}")
async def ws_video(ws: WebSocket, source: str):
    """Stream JPEG frames for a specific video source."""
    if not await _ws_authorized(ws):
        await ws.close(code=1008)
        return
    if not _VIDEO_AVAILABLE or video_clients is None:
        await ws.close(code=4003, reason="Video streaming not available")
        return
    if source not in VIDEO_TOPIC_MAP:
        await ws.close(code=4004, reason=f"Unknown source: {source}")
        return
    await ws.accept()
    video_clients.add(source, ws)
    try:
        while True:
            await ws.receive_text()  # keepalive / ping
    except WebSocketDisconnect:
        video_clients.remove(source, ws)


# ── WebSocket: Text Input (Browser → ROS2) ─────────────────────

@app.websocket("/ws/text")
async def ws_text(ws: WebSocket):
    """Text-only mode: receive text, classify intent, publish to ROS2."""
    if not await _ws_authorized(ws):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            text = await ws.receive_text()
            text = text.strip()
            if not text:
                await ws.send_json({"error": "empty_text", "published": False})
                continue
            if ENABLE_S2TWP:
                from text_normalization import to_traditional_tw
                text = to_traditional_tw(text)
            session_id = str(uuid.uuid4())[:8]
            started = time.monotonic()
            match = classifier.classify(text)
            intent = match.intent if match.intent != "unknown" else "chat"
            total_latency = (time.monotonic() - started) * 1000

            payload = {
                "stamp": time.time(),
                "event_type": "intent_recognized",
                "intent": intent,
                "text": text,
                "confidence": round(match.confidence, 3),
                "provider": "text_input",
                "source": "web_bridge",
                "session_id": session_id,
                "matched_keywords": match.matched_keywords,
                "latency_ms": round(total_latency, 2),
                "degraded": False,
                "timestamp": datetime.now().isoformat(),
            }
            node.publish_speech_event(payload)
            await ws.send_json({
                "asr": text,
                "intent": intent,
                "confidence": round(match.confidence, 3),
                "latency_ms": round(total_latency, 2),
                "published": True,
            })
    except WebSocketDisconnect:
        pass


# ── WebSocket: Speech Input (Browser → ROS2) ───────────────────

@app.websocket("/ws/speech")
async def ws_speech(ws: WebSocket):
    if not await _ws_authorized(ws):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            audio_bytes = await ws.receive_bytes()

            # Payload cap — reject oversized audio
            if len(audio_bytes) > MAX_AUDIO_BYTES:
                await ws.send_json({"error": "audio_too_large", "published": False})
                continue

            session_id = str(uuid.uuid4())[:8]
            started = time.monotonic()

            try:
                # 1. Resample to 16kHz mono WAV
                print(f"[gateway] Received audio: {len(audio_bytes)} bytes", flush=True)
                wav16k = await asyncio.to_thread(resample_to_wav16k, audio_bytes)
                print(f"[gateway] Resampled WAV: {len(wav16k)} bytes", flush=True)

                # 2. ASR
                asr_result = await asyncio.to_thread(transcribe, wav16k, ASR_URL)
                text = asr_result["text"].strip()
                if ENABLE_S2TWP:
                    from text_normalization import to_traditional_tw
                    text = to_traditional_tw(text)
                asr_latency = asr_result["latency_ms"]
                print(f"[gateway] ASR result: text={text!r} latency={asr_latency}ms", flush=True)

                if not text:
                    await ws.send_json({"error": "empty_asr", "published": False})
                    continue

                # 3. Intent classification
                match = classifier.classify(text)
                intent = match.intent if match.intent != "unknown" else "chat"
                total_latency = (time.monotonic() - started) * 1000

                # 4. Contract-compliant payload (interaction_contract.md v2.4 §4.2)
                payload = {
                    "stamp": time.time(),
                    "event_type": "intent_recognized",
                    "intent": intent,
                    "text": text,
                    "confidence": round(match.confidence, 3),
                    "provider": "sensevoice_cloud",
                    "source": "web_bridge",
                    "session_id": session_id,
                    "matched_keywords": match.matched_keywords,
                    "latency_ms": round(total_latency, 2),
                    "degraded": False,
                    "timestamp": datetime.now().isoformat(),
                }

                # 5. Publish to ROS2
                node.publish_speech_event(payload)

                # 6. Reply to browser
                await ws.send_json({
                    "asr": text,
                    "intent": intent,
                    "confidence": round(match.confidence, 3),
                    "latency_ms": round(total_latency, 2),
                    "published": True,
                })

            except Exception as e:
                print(f"[gateway] Speech error: {e}", flush=True)
                await ws.send_json({"error": "processing_failed", "published": False})

    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    # S0 hardening: bind host from GATEWAY_HOST (default 0.0.0.0 — unchanged).
    # Loud startup banner so an unauthenticated, all-interfaces gateway is never
    # a silent default (findings GW-01/EXP-01).
    if not AUTH.auth_enabled:
        print(
            f"[gateway] ⚠ SECURITY: no GATEWAY_AUTH_TOKEN — state-changing "
            f"endpoints are UNAUTHENTICATED (host={AUTH.host}). Set "
            f"GATEWAY_AUTH_TOKEN + GATEWAY_ALLOWED_ORIGINS to lock down.",
            flush=True,
        )
    else:
        print(f"[gateway] auth ON (token required on POST, host={AUTH.host}, "
              f"origins={list(AUTH.allowed_origins) or 'any'})", flush=True)
    uvicorn.run(app, host=AUTH.host, port=PORT, ws="wsproto")
