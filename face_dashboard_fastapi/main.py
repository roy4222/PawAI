#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from collections import deque
from pathlib import Path
from typing import Deque, Optional
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class ProcState:
    def __init__(self, name: str):
        self.name = name
        self.proc: Optional[subprocess.Popen[str]] = None
        self.logs: Deque[str] = deque(maxlen=300)
        self.saved: int = 0
        self.total: int = 0
        self.lock = threading.Lock()

    def running(self) -> bool:
        proc = self.proc
        return proc is not None and proc.poll() is None

    def pid(self) -> Optional[int]:
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return None
        return proc.pid


class EnrollStartRequest(BaseModel):
    person_name: str = Field(min_length=1)
    samples: int = Field(default=30, gt=0, le=500)
    interval: float = Field(default=0.35, gt=0)
    profile_id: Optional[str] = None


class ProfileSelectRequest(BaseModel):
    profile_id: str = Field(min_length=1)


class InferStartRequest(BaseModel):
    profile_id: Optional[str] = None


class AppConfig(BaseModel):
    db_dir: str
    enroll_script: str
    infer_script: str
    stream_health_url: str


APP = FastAPI(title="Face Dashboard API", version="0.1.0")
APP.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ENROLL = ProcState("enroll")
INFER = ProcState("infer")
CONFIG = AppConfig(
    db_dir="/home/jetson/face_db",
    enroll_script="/home/jetson/elder_and_dog/scripts/face_identity_enroll_cv.py",
    infer_script="/home/jetson/elder_and_dog/scripts/face_identity_infer_cv.py",
    stream_health_url="http://127.0.0.1:8081/stream?topic=/camera/camera/color/image_raw",
)

MODEL_PROFILES = {
    "yunet_sface_fp32": {
        "label": "YuNet + SFace FP32",
        "description": "Default profile using fp32 ONNX models",
        "enroll_args": [
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
            "--det-score-threshold",
            "0.90",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
        ],
        "infer_args": [
            "--model-path",
            "/home/jetson/face_db/model_sface_fp32.pkl",
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
            "--det-score-threshold",
            "0.90",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
            "--sim-threshold-upper",
            "0.35",
            "--sim-threshold-lower",
            "0.25",
            "--stable-hits",
            "3",
            "--unknown-grace-s",
            "1.2",
            "--min-face-area-ratio",
            "0.02",
        ],
    },
    "yunet_sface_int8": {
        "label": "YuNet + SFace INT8BQ",
        "description": "Quantized ONNX variants for edge speed testing",
        "enroll_args": [
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar_int8bq.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec_int8bq.onnx",
            "--det-score-threshold",
            "0.90",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
        ],
        "infer_args": [
            "--model-path",
            "/home/jetson/face_db/model_sface_int8.pkl",
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar_int8bq.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec_int8bq.onnx",
            "--det-score-threshold",
            "0.90",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
            "--sim-threshold-upper",
            "0.35",
            "--sim-threshold-lower",
            "0.25",
            "--stable-hits",
            "3",
            "--unknown-grace-s",
            "1.2",
            "--min-face-area-ratio",
            "0.02",
        ],
    },
    "yunet_sface_strict": {
        "label": "YuNet + SFace Strict",
        "description": "Same models with stricter known/unknown thresholds",
        "enroll_args": [
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
            "--det-score-threshold",
            "0.92",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
        ],
        "infer_args": [
            "--model-path",
            "/home/jetson/face_db/model_sface_strict.pkl",
            "--yunet-model",
            "/home/jetson/face_models/face_detection_yunet_2023mar.onnx",
            "--sface-model",
            "/home/jetson/face_models/face_recognition_sface_2021dec.onnx",
            "--det-score-threshold",
            "0.92",
            "--det-nms-threshold",
            "0.30",
            "--det-top-k",
            "5000",
            "--sim-threshold-upper",
            "0.42",
            "--sim-threshold-lower",
            "0.30",
            "--stable-hits",
            "3",
            "--unknown-grace-s",
            "1.2",
            "--min-face-area-ratio",
            "0.02",
        ],
    },
}

SELECTED_PROFILE_ID = "yunet_sface_fp32"


def _spawn_reader(state: ProcState):
    if state.proc is None or state.proc.stdout is None:
        return

    for line in state.proc.stdout:
        text = line.rstrip("\n")
        with state.lock:
            state.logs.append(text)
            if "(" in text and "/" in text and ")" in text:
                try:
                    tail = text.split("(")[-1].split(")")[0]
                    left, right = tail.split("/")
                    state.saved = int(left)
                    state.total = int(right)
                except Exception:
                    pass


def _start_process(state: ProcState, cmd: list[str]) -> int:
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    state.proc = proc
    t = threading.Thread(target=_spawn_reader, args=(state,), daemon=True)
    t.start()
    return proc.pid


def _list_people(db_dir: Path):
    if not db_dir.exists():
        return []

    people = []
    for person_dir in sorted(db_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        count = len(list(person_dir.glob("*.png")))
        people.append({"name": person_dir.name, "samples": count})
    return people


def _guidance(saved: int, total: int) -> str:
    if total <= 0:
        return "Enter name, sample count, and interval, then press Start Scan."
    ratio = saved / total
    if ratio < 0.25:
        return "Keep your face centered and look straight."
    if ratio < 0.5:
        return "Slightly turn left and right."
    if ratio < 0.75:
        return "Move closer and farther a little."
    if ratio < 1.0:
        return "Great. Hold steady for final captures."
    return "Scan complete. You can add another person or run demo."


def _require_profile(profile_id: str):
    profile = MODEL_PROFILES.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"unknown profile: {profile_id}")
    return profile


def _iter_profile_model_paths(args: list[str]):
    i = 0
    while i < len(args) - 1:
        if args[i] in {"--yunet-model", "--sface-model"}:
            yield Path(args[i + 1])
            i += 2
            continue
        i += 1


def _validate_profile_models(profile: dict):
    missing = []
    for p in _iter_profile_model_paths(profile["enroll_args"] + profile["infer_args"]):
        if not p.exists():
            missing.append(str(p))
    if missing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "model files missing for selected profile",
                "missing": missing,
            },
        )


def _profile_summary(profile_id: str, profile: dict):
    return {
        "id": profile_id,
        "label": profile["label"],
        "description": profile["description"],
    }


def _check_stream_health(url: str):
    req = Request(url, method="HEAD")
    started = time.time()
    try:
        with urlopen(req, timeout=2) as resp:
            elapsed_ms = int((time.time() - started) * 1000)
            return {
                "status": "HEALTHY" if resp.status == 200 else "DEGRADED",
                "http_status": resp.status,
                "latency_ms": elapsed_ms,
            }
    except Exception as exc:
        return {
            "status": "DOWN",
            "http_status": 0,
            "latency_ms": None,
            "reason": str(exc),
        }


@APP.get("/api/status")
def get_status():
    selected_profile = _require_profile(SELECTED_PROFILE_ID)
    with ENROLL.lock:
        enroll = {
            "running": ENROLL.running(),
            "pid": ENROLL.pid(),
            "saved": ENROLL.saved,
            "total": ENROLL.total,
            "logs": list(ENROLL.logs)[-80:],
            "guidance": _guidance(ENROLL.saved, ENROLL.total),
        }
    with INFER.lock:
        infer = {
            "running": INFER.running(),
            "pid": INFER.pid(),
            "logs": list(INFER.logs)[-80:],
        }

    return {
        "enroll": enroll,
        "infer": infer,
        "people": _list_people(Path(CONFIG.db_dir)),
        "selected_profile": _profile_summary(SELECTED_PROFILE_ID, selected_profile),
        "profiles": [
            _profile_summary(profile_id, profile)
            for profile_id, profile in MODEL_PROFILES.items()
        ],
    }


@APP.get("/api/model/profiles")
def model_profiles():
    selected_profile = _require_profile(SELECTED_PROFILE_ID)
    return {
        "selected_profile": _profile_summary(SELECTED_PROFILE_ID, selected_profile),
        "profiles": [
            _profile_summary(profile_id, profile)
            for profile_id, profile in MODEL_PROFILES.items()
        ],
    }


@APP.post("/api/model/select")
def model_select(req: ProfileSelectRequest):
    global SELECTED_PROFILE_ID
    profile = _require_profile(req.profile_id)
    _validate_profile_models(profile)
    with ENROLL.lock, INFER.lock:
        if ENROLL.running() or INFER.running():
            raise HTTPException(
                status_code=409,
                detail="cannot switch profile while enroll/infer is running",
            )
    SELECTED_PROFILE_ID = req.profile_id
    return {
        "ok": True,
        "selected_profile": _profile_summary(SELECTED_PROFILE_ID, profile),
    }


@APP.get("/api/stream/health")
def stream_health():
    return _check_stream_health(CONFIG.stream_health_url)


@APP.post("/api/enroll/start")
def enroll_start(req: EnrollStartRequest):
    profile_id = req.profile_id or SELECTED_PROFILE_ID
    profile = _require_profile(profile_id)
    _validate_profile_models(profile)
    with ENROLL.lock:
        if ENROLL.running():
            raise HTTPException(status_code=409, detail="enroll already running")
        ENROLL.logs.clear()
        ENROLL.saved = 0
        ENROLL.total = req.samples
        cmd = [
            "python3",
            CONFIG.enroll_script,
            "--person-name",
            req.person_name.strip(),
            "--samples",
            str(req.samples),
            "--capture-interval",
            str(req.interval),
            "--output-dir",
            CONFIG.db_dir,
        ]
        cmd.extend(profile["enroll_args"])
        cmd.extend(
            [
                "--headless",
            ]
        )
        pid = _start_process(ENROLL, cmd)
    return {
        "ok": True,
        "pid": pid,
        "selected_profile": _profile_summary(profile_id, profile),
    }


@APP.post("/api/enroll/stop")
def enroll_stop():
    with ENROLL.lock:
        if ENROLL.running() and ENROLL.proc is not None:
            ENROLL.proc.terminate()
            return {"ok": True, "stopping": True}
    return {"ok": True, "stopping": False}


@APP.post("/api/infer/start")
def infer_start(req: Optional[InferStartRequest] = None):
    profile_id = req.profile_id if req and req.profile_id else SELECTED_PROFILE_ID
    profile = _require_profile(profile_id)
    _validate_profile_models(profile)
    with INFER.lock:
        if INFER.running():
            raise HTTPException(status_code=409, detail="infer already running")
        INFER.logs.clear()
        cmd = [
            "python3",
            CONFIG.infer_script,
            "--db-dir",
            CONFIG.db_dir,
        ]
        cmd.extend(profile["infer_args"])
        cmd.extend(
            [
                "--headless",
            ]
        )
        pid = _start_process(INFER, cmd)
    return {
        "ok": True,
        "pid": pid,
        "selected_profile": _profile_summary(profile_id, profile),
    }


@APP.post("/api/infer/stop")
def infer_stop():
    with INFER.lock:
        if INFER.running() and INFER.proc is not None:
            INFER.proc.terminate()
            return {"ok": True, "stopping": True}
    return {"ok": True, "stopping": False}


def parse_args():
    p = argparse.ArgumentParser(description="FastAPI backend for face dashboard")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--db-dir", default=CONFIG.db_dir)
    p.add_argument("--enroll-script", default=CONFIG.enroll_script)
    p.add_argument("--infer-script", default=CONFIG.infer_script)
    p.add_argument("--stream-health-url", default=CONFIG.stream_health_url)
    return p.parse_args()


def main():
    args = parse_args()
    CONFIG.db_dir = args.db_dir
    CONFIG.enroll_script = args.enroll_script
    CONFIG.infer_script = args.infer_script
    CONFIG.stream_health_url = args.stream_health_url

    Path(CONFIG.db_dir).mkdir(parents=True, exist_ok=True)
    if not Path(CONFIG.enroll_script).exists():
        raise SystemExit(f"Enroll script not found: {CONFIG.enroll_script}")
    if not Path(CONFIG.infer_script).exists():
        raise SystemExit(f"Infer script not found: {CONFIG.infer_script}")

    import uvicorn

    uvicorn.run(APP, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
