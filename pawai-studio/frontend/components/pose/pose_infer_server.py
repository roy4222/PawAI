"""Pose inference HTTP server for PosePanel.

Run:
  uv pip install fastapi uvicorn opencv-python mediapipe numpy
  uvicorn pose_infer_server:app --host 127.0.0.1 --port 8765 --reload
"""

import base64
from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from test_pose import infer_pose_from_bgr


CANONICAL_POSE_MAP = {
    "standing": "standing",
    "sitting": "sitting",
    "crouching": "crouching",
    "bending": "bending",
    "hands on hips": "hands_on_hips",
    "hands_on_hips": "hands_on_hips",
    "kneeling one knee": "kneeling_one_knee",
    "kneeling_on_one_knee": "kneeling_one_knee",
    "kneeling_one_knee": "kneeling_one_knee",
    "fallen": "fallen",
    "unknown": "unknown",
}


def canonicalize_pose_name(raw_pose: Any) -> str:
    if not isinstance(raw_pose, str):
        return "unknown"

    key = " ".join(raw_pose.strip().lower().replace("-", " ").replace("_", " ").split())
    if key in CANONICAL_POSE_MAP:
        return CANONICAL_POSE_MAP[key]

    snake_key = key.replace(" ", "_")
    return CANONICAL_POSE_MAP.get(snake_key, "unknown")


class PoseInferRequest(BaseModel):
    frame_id: str
    timestamp: str
    image_base64: str
    width: int
    height: int


app = FastAPI(title="PawAI Pose Inference", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


def decode_b64_image(image_base64: str) -> np.ndarray:
    try:
        raw = base64.b64decode(image_base64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid base64 payload") from exc

    nparr = np.frombuffer(raw, dtype=np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=400, detail="Failed to decode image")

    return frame


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/pose/infer")
def infer_pose(payload: PoseInferRequest) -> dict[str, Any]:
    frame = decode_b64_image(payload.image_base64)
    result = infer_pose_from_bgr(frame, return_annotated=True)
    canonical_pose = canonicalize_pose_name(result.get("pose"))

    annotated_image_base64 = None
    annotated_bgr = result.get("annotated_bgr")
    if annotated_bgr is not None:
        ok, encoded = cv2.imencode(".jpg", annotated_bgr)
        if ok:
            annotated_image_base64 = base64.b64encode(encoded.tobytes()).decode("utf-8")

    return {
        "id": payload.frame_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "pose": canonical_pose,
        "confidence": float(result["confidence"]),
        "track_id": None,
        "debug": result.get("debug", {}),
        "annotated_image_base64": annotated_image_base64,
    }
