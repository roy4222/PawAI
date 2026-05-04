"""PawAI Studio — Gateway + Mock Event Server

啟動（推薦）: bash pawai-studio/start-live.sh --mock     # port 8080
直接啟: uvicorn mock_server:app --host 0.0.0.0 --port 8080 --reload
"""
from __future__ import annotations

import asyncio
import random
import sys
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the real SKILL_REGISTRY (pure-Python dataclass module, no ROS deps)
# so the mock skill_registry endpoint auto-syncs with brain_node's source of
# truth. Path: <repo>/interaction_executive/interaction_executive/skill_contract.py
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "interaction_executive"))
try:
    from interaction_executive.skill_contract import SKILL_REGISTRY  # noqa: E402
except ImportError as _exc:
    SKILL_REGISTRY = {}
    print(f"[mock_server] WARN: SKILL_REGISTRY import failed: {_exc}")

from schemas import (
    BrainState,
    ChatCommand,
    FaceIdentityData,
    FaceState,
    FaceTrack,
    GestureData,
    GestureState,
    MockTrigger,
    PawAIEvent,
    PawAIBrainState,
    PoseData,
    PoseState,
    SkillRequestPayload,
    SkillCommand,
    TextInputPayload,
    SpeechIntentData,
    SpeechState,
    SystemHealth,
)

# ── WebSocket 連線管理 ──────────────────────────────────────────────

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

manager = ConnectionManager()

# ── Mock 資料產生器 ──────────────────────────────────────────────────

def _ts() -> str:
    return datetime.now().astimezone().isoformat()

def _uid() -> str:
    return str(uuid.uuid4())

def mock_face_event() -> dict:
    """Push both a face identity event AND a face state snapshot."""
    names = ["小明", "小華", "Roy"]
    tracks = []
    n = random.randint(1, 3)
    for i in range(n):
        tracks.append(FaceTrack(
            track_id=i + 1,
            stable_name=random.choice(names) if random.random() > 0.3 else "unknown",
            sim=round(random.uniform(0.2, 0.95), 2),
            distance_m=round(random.uniform(0.5, 3.0), 1),
            bbox=(100 + i * 150, 100, 200 + i * 150, 280),
            mode=random.choice(["stable", "hold"]),
        ))
    # Push as face state (has face_count → triggers faceState update in frontend)
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="face",
        event_type=random.choice(["track_started", "identity_stable", "track_lost"]),
        data=FaceState(
            stamp=time.time(),
            face_count=len(tracks),
            tracks=tracks,
        ).model_dump(),
    ).model_dump()

def mock_speech_event() -> dict:
    phases = ["idle_wakeword", "listening", "transcribing", "speaking", "keep_alive"]
    intents = ["greet", "stop", "status", "come_here"]
    texts = ["你好", "停止", "你好嗎", "過來"]
    idx = random.randint(0, len(intents) - 1)
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="speech",
        event_type="intent_recognized",
        data=SpeechState(
            stamp=time.time(),
            phase=random.choice(phases),
            last_asr_text=texts[idx],
            last_intent=intents[idx],
            last_tts_text=f"收到，{texts[idx]}",
            models_loaded=["kws", "asr", "tts"],
        ).model_dump(),
    ).model_dump()

def mock_gesture_event() -> dict:
    gesture = random.choice(["wave", "stop", "point", "ok"])
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="gesture",
        event_type="gesture_detected",
        data=GestureState(
            stamp=time.time(),
            active=True,
            current_gesture=gesture,
            confidence=round(random.uniform(0.7, 0.95), 2),
            hand=random.choice(["left", "right"]),
            status="active",
        ).model_dump(),
    ).model_dump()

def mock_pose_event() -> dict:
    pose = random.choice(["standing", "sitting", "crouching", "fallen"])
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="pose",
        event_type="pose_detected",
        data=PoseState(
            stamp=time.time(),
            active=True,
            current_pose=pose,
            confidence=round(random.uniform(0.75, 0.98), 2),
            track_id=random.randint(1, 5),
            status="active",
        ).model_dump(),
    ).model_dump()

def mock_object_event() -> dict:
    objects_pool = [
        ("cup", 41), ("bottle", 39), ("chair", 56),
        ("person", 0), ("dog", 16), ("book", 73),
    ]
    n = random.randint(1, 2)
    picks = random.sample(objects_pool, min(n, len(objects_pool)))
    objects = [
        {
            "class_name": name,
            "class_id": cid,
            "confidence": round(random.uniform(0.5, 0.95), 3),
            "bbox": [random.randint(50, 200), random.randint(50, 200),
                     random.randint(300, 500), random.randint(300, 500)],
        }
        for name, cid in picks
    ]
    return PawAIEvent(
        id=_uid(), timestamp=_ts(), source="object",
        event_type="object_detected",
        data={
            "stamp": time.time(),
            "objects": objects,
            "detected_objects": objects,
            "active": True,
            "status": "active",
        },
    ).model_dump()


MOCK_GENERATORS = {
    "face": mock_face_event,
    "speech": mock_speech_event,
    "gesture": mock_gesture_event,
    "pose": mock_pose_event,
    "object": mock_object_event,
}

# ── 背景推送任務 ────────────────────────────────────────────────────

async def periodic_mock_push() -> None:
    """每 2 秒推送一個隨機事件"""
    while True:
        await asyncio.sleep(2)
        if manager.active:
            try:
                source = random.choice(list(MOCK_GENERATORS.keys()))
                event = MOCK_GENERATORS[source]()
                await manager.broadcast(event)
            except Exception as e:
                print(f"[mock] Error generating {source} event: {e}", flush=True)

# ── Demo A 場景 ─────────────────────────────────────────────────────

DEMO_A_SEQUENCE = [
    ("face", "track_started", lambda: FaceIdentityData(
        track_id=1, stable_name="unknown", sim=0.15, distance_m=2.5
    ).model_dump()),
    ("face", "identity_stable", lambda: FaceIdentityData(
        track_id=1, stable_name="小明", sim=0.92, distance_m=1.2
    ).model_dump()),
    ("speech", "wake_word", lambda: SpeechIntentData(
        text="", confidence=0.95, provider="sherpa_kws"
    ).model_dump()),
    ("speech", "intent_recognized", lambda: SpeechIntentData(
        intent="greet", text="你好", confidence=0.95, provider="whisper_local"
    ).model_dump()),
    ("brain", "decision_made", lambda: {
        "intent": "greet", "selected_skill": "hello",
        "reason": "identity_stable + greet intent", "degradation_level": 0,
    }),
    ("brain", "skill_dispatched", lambda: {
        "intent": "greet", "selected_skill": "hello",
        "reason": "executing wave greeting", "degradation_level": 0,
    }),
]

async def run_demo_a() -> None:
    for source, event_type, data_fn in DEMO_A_SEQUENCE:
        event = PawAIEvent(
            id=_uid(), timestamp=_ts(),
            source=source, event_type=event_type, data=data_fn(),
        ).model_dump()
        await manager.broadcast(event)
        await asyncio.sleep(1.5)

# ── State 快照 ──────────────────────────────────────────────────────

current_brain_state = BrainState(stamp=time.time(), executive_state="idle")

current_pawai_brain_state = PawAIBrainState(
    timestamp=time.time(),
    mode="idle",
    active_plan=None,
    active_step=None,
    fallback_active=False,
    safety_flags={
        "obstacle": False,
        "emergency": False,
        "fallen": False,
        "tts_playing": False,
        "nav_safe": True,
    },
    cooldowns={},
    last_plans=[],
)


async def broadcast_brain_event(event_type: str, data: dict) -> None:
    event = PawAIEvent(
        id=_uid(),
        timestamp=_ts(),
        source="brain",
        event_type=event_type,
        data=data,
    ).model_dump()
    await manager.broadcast(event)

# ── App ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_mock_push())
    yield
    task.cancel()

app = FastAPI(title="PawAI Studio Gateway + Mock", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── WebSocket ───────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def ws_events(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        manager.disconnect(ws)


# Mock ASR responses for dev testing
MOCK_ASR_RESPONSES = [
    ("你好", "greet", 0.95),
    ("停止", "stop", 0.92),
    ("過來", "come_here", 0.88),
    ("你好嗎", "greet", 0.90),
    ("坐下", "sit", 0.85),
]


MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10MB cap


@app.websocket("/ws/speech")
async def ws_speech(ws: WebSocket):
    """Mock speech endpoint — accepts audio, returns fake ASR result."""
    await ws.accept()
    try:
        while True:
            audio_bytes = await ws.receive_bytes()
            if len(audio_bytes) > MAX_AUDIO_BYTES:
                await ws.send_json({"error": "audio_too_large", "published": False})
                continue
            # Simulate ASR processing delay
            await asyncio.sleep(0.5)
            text, intent, conf = random.choice(MOCK_ASR_RESPONSES)
            await ws.send_json({
                "asr": text,
                "intent": intent,
                "confidence": conf,
                "latency_ms": round(random.uniform(300, 800), 1),
                "published": True,
            })
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/text")
async def ws_text(ws: WebSocket):
    """Mock text endpoint — accepts text, returns fake intent result."""
    await ws.accept()
    try:
        while True:
            text = await ws.receive_text()
            text = text.strip()
            if not text:
                await ws.send_json({"error": "empty_text", "published": False})
                continue
            await ws.send_json({
                "asr": text,
                "intent": "chat",
                "confidence": 0.8,
                "latency_ms": round(random.uniform(50, 200), 1),
                "published": True,
            })
            # Broadcast mock TTS event so ChatPanel shows AI reply
            mock_reply = f"收到「{text[:20]}」，這是模擬回覆。"
            tts_event = PawAIEvent(
                id=_uid(), timestamp=_ts(), source="tts",
                event_type="tts_speaking",
                data={"text": mock_reply, "phase": "speaking", "origin": "mock"},
            ).model_dump()
            await asyncio.sleep(0.5)  # simulate LLM latency
            await manager.broadcast(tts_event)
    except WebSocketDisconnect:
        pass

# ── REST: Gateway 端點 ──────────────────────────────────────────────

@app.post("/api/command")
async def post_command(cmd: SkillCommand):
    event = PawAIEvent(
        id=_uid(), timestamp=_ts(), source="brain",
        event_type="skill_dispatched",
        data={"intent": "manual", "selected_skill": cmd.skill_id,
              "reason": f"studio {cmd.source}", "degradation_level": 0},
    ).model_dump()
    await manager.broadcast(event)
    return {"status": "ok", "skill_id": cmd.skill_id}

@app.post("/api/chat")
async def post_chat(cmd: ChatCommand):
    reply = f"收到你的訊息：「{cmd.text}」（這是 Mock 回覆）"
    return {"status": "ok", "reply": reply, "session_id": cmd.session_id}

@app.post("/api/skill_request")
async def post_skill_request(payload: SkillRequestPayload):
    """Mock skill_request — emits a proposal + success/blocked-by-safety result
    based on the real SKILL_REGISTRY shape, so Studio Trace Drawer gets
    feedback on every button click.
    """
    request_id = payload.request_id or f"req-{int(time.time() * 1000)}"
    skill = payload.skill
    plan_id = f"p-mock-{int(time.time() * 1000)}"
    contract = SKILL_REGISTRY.get(skill)

    # Unknown skill — no event, just ack.
    if contract is None:
        return {"ok": False, "mock": True, "error": f"unknown skill {skill!r}"}

    # Disabled-bucket or enabled_when-blocked → blocked_by_safety
    if not contract.static_enabled or contract.enabled_when:
        await broadcast_brain_event("skill_result", {
            "plan_id": plan_id,
            "step_index": None,
            "status": "blocked_by_safety",
            "detail": "skill statically disabled or gated"
                if not contract.static_enabled
                else (contract.enabled_when[0][1] if contract.enabled_when else "blocked"),
            "selected_skill": skill,
            "priority_class": int(contract.priority_class),
            "step_total": len(contract.steps),
            "step_args": {},
            "timestamp": time.time(),
        })
        return {"ok": True, "mock": True, "request_id": request_id}

    # Active path — emit proposal then completed result.
    steps_payload = [
        {"executor": s.executor.value, "args": dict(s.args)}
        for s in contract.steps
    ]
    await broadcast_brain_event("proposal", {
        "plan_id": plan_id,
        "selected_skill": skill,
        "steps": steps_payload,
        "reason": f"studio_button:{skill}",
        "source": "studio_button",
        "priority_class": int(contract.priority_class),
        "session_id": request_id,
        "created_at": time.time(),
    })
    await broadcast_brain_event("skill_result", {
        "plan_id": plan_id,
        "step_index": None,
        "status": "completed",
        "detail": skill,
        "selected_skill": skill,
        "priority_class": int(contract.priority_class),
        "step_total": len(contract.steps),
        "step_args": {},
        "timestamp": time.time(),
    })
    return {"ok": True, "mock": True, "request_id": request_id}

@app.post("/api/text_input")
async def post_text_input(payload: TextInputPayload):
    request_id = payload.request_id or f"txt-{int(time.time() * 1000)}"
    plan_id = f"p-text-{int(time.time() * 1000)}"
    await broadcast_brain_event("proposal", {
        "plan_id": plan_id,
        "selected_skill": "say_canned",
        "steps": [{"executor": "say", "args": {"text": "我聽不太懂"}}],
        "reason": "mock_text_input",
        "source": "mock",
        "priority_class": 4,
        "session_id": request_id,
        "created_at": time.time(),
    })
    await broadcast_brain_event("skill_result", {
        "plan_id": plan_id,
        "step_index": None,
        "status": "completed",
        "detail": "我聽不太懂",
        "selected_skill": "say_canned",
        "priority_class": 4,
        "step_total": 1,
        "step_args": {},
        "timestamp": time.time(),
    })
    return {"ok": True, "mock": True, "request_id": request_id}

@app.get("/api/brain")
async def get_brain():
    return current_pawai_brain_state.model_dump()

@app.get("/api/health")
async def get_health():
    return SystemHealth(
        stamp=time.time(),
        jetson={"cpu_percent": 45.2, "gpu_percent": 30.1,
                "ram_used_mb": 5120, "ram_total_mb": 8192, "temperature_c": 52.3},
        modules=[
            {"name": "face", "status": "active", "latency_ms": 12, "last_heartbeat": time.time()},
            {"name": "speech", "status": "active", "latency_ms": 8, "last_heartbeat": time.time()},
            {"name": "brain", "status": "active", "latency_ms": 150, "last_heartbeat": time.time()},
        ],
    ).model_dump()

# ── Phase B B5a: skill_registry / capability / plan_mode ────────────
#
# Real gateway equivalents live in pawai-studio/gateway/studio_gateway.py.
# This mock mirrors the same JSON shape so the Studio frontend can be tested
# in browser without a running ROS / Jetson environment.

# Mutable mock state for capability gates and plan mode.
_mock_capability: dict[str, str] = {"nav_ready": "true", "depth_clear": "true"}
_mock_plan_mode: dict[str, str] = {"mode": "A"}


@app.get("/api/skill_registry")
async def get_skill_registry():
    """Mock /api/skill_registry — returns 27 skills synced with the real
    interaction_executive.skill_contract.SKILL_REGISTRY.
    """
    skills = []
    for name, c in SKILL_REGISTRY.items():
        skills.append({
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
        })
    by_bucket: dict[str, int] = {"active": 0, "hidden": 0, "disabled": 0, "retired": 0}
    for s in skills:
        by_bucket[s["bucket"]] = by_bucket.get(s["bucket"], 0) + 1
    return {"ok": True, "total": len(skills), "by_bucket": by_bucket, "skills": skills}


@app.get("/api/capability")
async def get_capability():
    """Tri-state snapshot. Defaults: both green so nav-gated buttons can be tested."""
    return {"ok": True, "capabilities": dict(_mock_capability)}


class _CapabilityPayload(BaseModel):
    name: str  # "nav_ready" | "depth_clear"
    state: str  # "true" | "false" | "unknown"


@app.post("/api/capability")
async def post_capability(payload: _CapabilityPayload):
    """Mock-only endpoint to flip a gate (so Studio Trace Drawer chips can be
    visually verified in all 3 colours without a real perception pipeline).
    """
    if payload.name not in _mock_capability:
        return {"ok": False, "error": f"unknown capability {payload.name!r}"}
    if payload.state not in ("true", "false", "unknown"):
        return {"ok": False, "error": "state must be true/false/unknown"}
    _mock_capability[payload.name] = payload.state
    # Broadcast the change as a synthetic event so /ws/events listeners update.
    await manager.broadcast({
        "id": _uid(),
        "timestamp": _ts(),
        "source": "capability",
        "event_type": f"capability_{payload.name}",
        "data": {
            "name": payload.name,
            "value": payload.state == "true",
            "tri_state": payload.state,
        },
    })
    return {"ok": True, "name": payload.name, "state": payload.state}


@app.get("/api/plan_mode")
async def get_plan_mode():
    return {"ok": True, "mode": _mock_plan_mode["mode"]}


class _PlanModePayload(BaseModel):
    mode: str  # "A" | "B"


@app.post("/api/plan_mode")
async def post_plan_mode(payload: _PlanModePayload):
    mode = payload.mode.strip().upper()
    if mode not in {"A", "B"}:
        return {"ok": False, "error": "mode must be 'A' or 'B'"}
    _mock_plan_mode["mode"] = mode
    return {"ok": True, "mode": mode}


# ── REST: Mock 控制端點 ─────────────────────────────────────────────

@app.post("/mock/trigger")
async def mock_trigger(trigger: MockTrigger):
    event = PawAIEvent(
        id=_uid(), timestamp=_ts(),
        source=trigger.event_source,
        event_type=trigger.event_type,
        data=trigger.data,
    ).model_dump()
    await manager.broadcast(event)
    return {"status": "ok", "event_id": event["id"]}

@app.post("/mock/scenario/demo_a")
async def mock_demo_a():
    asyncio.create_task(run_demo_a())
    return {"status": "started", "scenario": "demo_a", "steps": len(DEMO_A_SEQUENCE)}

@app.post("/mock/scenario/self_introduce")
async def mock_scenario_self_introduce():
    async def run() -> None:
        plan_id = f"p-mock-{int(time.time() * 1000)}"
        steps = [
            ("say", {"text": "我是 PawAI，你的居家互動機器狗"}),
            ("motion", {"name": "hello"}),
            ("say", {"text": "平常我會待在你身邊，等你叫我"}),
            ("motion", {"name": "sit"}),
            ("say", {"text": "你可以用聲音、手勢，或直接跟我互動"}),
            ("motion", {"name": "content"}),
            ("say", {"text": "我也會注意周圍發生的事情"}),
            ("motion", {"name": "stand"}),
            ("say", {"text": "如果看到陌生人，我會提醒你提高注意"}),
            ("motion", {"name": "balance_stand"}),
        ]
        await broadcast_brain_event("state", {
            **current_pawai_brain_state.model_dump(),
            "timestamp": time.time(),
            "mode": "sequence",
            "active_plan": {
                "plan_id": plan_id,
                "selected_skill": "self_introduce",
                "step_index": 0,
                "step_total": len(steps),
                "started_at": time.time(),
                "priority_class": 2,
            },
        })
        await broadcast_brain_event("proposal", {
            "plan_id": plan_id,
            "selected_skill": "self_introduce",
            "steps": [{"executor": executor, "args": args} for executor, args in steps],
            "reason": "mock_scenario",
            "source": "mock",
            "priority_class": 2,
            "session_id": None,
            "created_at": time.time(),
        })
        for status in ("accepted", "started"):
            await broadcast_brain_event("skill_result", {
                "plan_id": plan_id,
                "step_index": None,
                "status": status,
                "detail": "self_introduce",
                "selected_skill": "self_introduce",
                "priority_class": 2,
                "step_total": len(steps),
                "step_args": {},
                "timestamp": time.time(),
            })
        for idx, (executor, args) in enumerate(steps):
            await asyncio.sleep(0.15)
            for status in ("step_started", "step_success"):
                await broadcast_brain_event("skill_result", {
                    "plan_id": plan_id,
                    "step_index": idx,
                    "status": status,
                    "detail": executor,
                    "selected_skill": "self_introduce",
                    "priority_class": 2,
                    "step_total": len(steps),
                    "step_args": args,
                    "timestamp": time.time(),
                })
        await broadcast_brain_event("skill_result", {
            "plan_id": plan_id,
            "step_index": None,
            "status": "completed",
            "detail": "",
            "selected_skill": "self_introduce",
            "priority_class": 2,
            "step_total": len(steps),
            "step_args": {},
            "timestamp": time.time(),
        })
        await broadcast_brain_event("state", {
            **current_pawai_brain_state.model_dump(),
            "timestamp": time.time(),
            "mode": "idle",
            "active_plan": None,
        })

    asyncio.create_task(run())
    return {"ok": True, "scenario": "self_introduce"}
