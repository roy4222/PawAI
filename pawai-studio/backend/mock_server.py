"""PawAI Studio — Gateway + Mock Event Server

啟動: uvicorn mock_server:app --host 0.0.0.0 --port 8001 --reload
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

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
    PoseData,
    PoseState,
    SkillCommand,
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
    # ── 只使用前端白名單內的物品 ───────────────────────────────────────
    # 對應 object-panel.tsx 的 OBJECT_WHITELIST（6 個 class）
    # bottle(39)/chair(56)/person(0)/dog(16) 已排除：
    #   bottle: 已驗證偵測率極低；chair: 太常見不觸發；
    #   person: 由人臉模組處理；dog: 不在白名單
    objects_pool = [
        ("cup", 41),        # ✅ 杯子 — 已驗證穩定
        ("cell phone", 67), # ✅ 手機 — 已驗證可偵測
        ("book", 73),       # ⚠️ 書本 — 翻開才偵測得到
        ("laptop", 63),     # ✅ 筆電
        ("backpack", 24),   # ✅ 背包
        ("clock", 74),      # ✅ 時鐘
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
            "active": len(objects) > 0,
            "status": "active" if len(objects) > 0 else "inactive",
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

# ── App ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(periodic_mock_push())
    yield
    task.cancel()

app = FastAPI(title="PawAI Studio Gateway + Mock", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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

@app.get("/api/brain")
async def get_brain():
    return current_brain_state.model_dump()

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

# ── REST: Mock 控制端點 ─────────────────────────────────────────────

@app.post("/mock/trigger")
async def mock_trigger(trigger: MockTrigger):
    print(f"DEBUG INCOMING: {trigger.data}")
    event = PawAIEvent(
        id=_uid(), timestamp=_ts(),
        source=trigger.event_source,
        event_type=trigger.event_type,
        data=trigger.data,
    ).model_dump()
    await manager.broadcast(event)
    return {"status": "ok", "event_id": event["id"]}

import subprocess
import os
import sys

yolo_process = None

@app.post("/mock/yolo/start")
async def start_yolo():
    """模擬：從網頁端一鍵啟動 YOLO 腳本"""
    global yolo_process
    if yolo_process is None or yolo_process.poll() is not None:
        script_path = os.path.join(os.path.dirname(__file__), "local_yolo_mjpeg.py")
        yolo_process = subprocess.Popen([sys.executable, script_path])
        return {"status": "started", "msg": "YOLO 串流已由網頁啟動"}
    return {"status": "already_running"}

@app.post("/mock/yolo/stop")
async def stop_yolo():
    """模擬：從網頁端關閉 YOLO 腳本"""
    global yolo_process
    if yolo_process is not None and yolo_process.poll() is None:
        yolo_process.terminate()
        yolo_process = None
        return {"status": "stopped", "msg": "YOLO 串流已關閉"}
    return {"status": "not_running"}

@app.post("/mock/scenario/demo_a")
async def mock_demo_a():
    asyncio.create_task(run_demo_a())
    return {"status": "started", "scenario": "demo_a", "steps": len(DEMO_A_SEQUENCE)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("mock_server:app", host="0.0.0.0", port=8000, ws="wsproto", reload=True)
