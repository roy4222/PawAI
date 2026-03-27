"""PawAI Studio schemas — 對齊 docs/Pawai-studio/specs/event-schema.md"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime
import uuid

# === Event 信封 ===

class PawAIEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat())
    source: str
    event_type: str
    data: dict

# === Face ===

class FaceIdentityData(BaseModel):
    track_id: int
    stable_name: str
    sim: float
    distance_m: float | None = None

class FaceTrack(BaseModel):
    track_id: int
    stable_name: str
    sim: float
    distance_m: float | None = None
    bbox: tuple[int, int, int, int]
    mode: Literal["stable", "hold"]

class FaceState(BaseModel):
    stamp: float
    face_count: int
    tracks: list[FaceTrack]

# === Speech ===

class SpeechIntentData(BaseModel):
    intent: str | None = None
    text: str
    confidence: float
    provider: str

class SpeechState(BaseModel):
    stamp: float
    phase: Literal[
        "idle_wakeword", "wake_ack", "loading_local_stack", "listening",
        "transcribing", "local_asr_done", "cloud_brain_pending",
        "speaking", "keep_alive", "unloading"
    ]
    last_asr_text: str = ""
    last_intent: str = ""
    last_tts_text: str = ""
    models_loaded: list[str] = []

# === Gesture ===

class GestureData(BaseModel):
    gesture: str
    confidence: float
    hand: Literal["left", "right"]

class GestureState(BaseModel):
    stamp: float
    active: bool
    current_gesture: str | None = None
    confidence: float = 0.0
    hand: Literal["left", "right"] | None = None
    status: Literal["active", "inactive", "loading"]

# === Pose ===

class PoseData(BaseModel):
    pose: str
    confidence: float
    track_id: int

class PoseState(BaseModel):
    stamp: float
    active: bool
    current_pose: str | None = None
    confidence: float = 0.0
    track_id: int | None = None
    status: Literal["active", "inactive", "loading"]

# === Brain ===

class BrainState(BaseModel):
    stamp: float
    executive_state: Literal["idle", "observing", "deciding", "executing", "speaking"]
    current_intent: str | None = None
    selected_skill: str | None = None
    degradation_level: Literal[0, 1, 2, 3] = 0
    active_tracks: int = 0
    cloud_connected: bool = True
    last_decision_reason: str = ""

# === System ===

class SystemHealth(BaseModel):
    stamp: float
    jetson: dict
    modules: list[dict]

# === Commands ===

class SkillCommand(BaseModel):
    command_type: Literal["skill"] = "skill"
    skill_id: str
    priority: Literal[0, 1] = 0
    source: str = "studio_button"

class ChatCommand(BaseModel):
    command_type: Literal["chat"] = "chat"
    text: str
    session_id: str

class MockTrigger(BaseModel):
    event_source: str
    event_type: str
    data: dict = {}
