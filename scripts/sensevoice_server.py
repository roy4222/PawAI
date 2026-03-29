#!/usr/bin/env python3
"""SenseVoice ASR server — FastAPI wrapper for FunASR SenseVoiceSmall.

Deploy on RTX 8000 (or any CUDA GPU). Exposes an OpenAI-compatible
/v1/audio/transcriptions endpoint so Jetson's QwenASRProvider can
call it without any client-side code changes.

Usage:
    pip install funasr fastapi uvicorn python-multipart soundfile
    python sensevoice_server.py                    # default :8001
    python sensevoice_server.py --port 8002        # custom port
    python sensevoice_server.py --device cuda:1    # select GPU
"""
from __future__ import annotations

import argparse
import io
import logging
import time
from typing import Optional

import numpy as np
import soundfile as sf
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sensevoice_server")

app = FastAPI(title="SenseVoice ASR Server")

# Global model reference — loaded once at startup
_model = None


def load_model(device: str = "cuda:0"):
    """Load SenseVoiceSmall via FunASR. Called once at startup."""
    global _model
    from funasr import AutoModel

    logger.info(f"Loading SenseVoiceSmall on {device} ...")
    _model = AutoModel(
        model="iic/SenseVoiceSmall",
        device=device,
        vad_model="fsmn-vad",
        trust_remote_code=True,
    )
    logger.info("SenseVoiceSmall loaded.")


@app.post("/v1/audio/transcriptions")
async def transcribe(
    file: UploadFile = File(...),
    model: Optional[str] = Form(None),
    language: Optional[str] = Form("zh"),
    sample_rate: Optional[str] = Form("16000"),
):
    """Accept multipart/form-data with a WAV file, return {"text": ...}.

    Compatible with QwenASRProvider's request format:
    - file: WAV binary
    - model: ignored (always uses SenseVoice)
    - language: passed to model (default "zh")
    - sample_rate: informational, audio is resampled if needed
    """
    started = time.monotonic()

    raw_bytes = await file.read()
    if not raw_bytes:
        return JSONResponse(
            status_code=400,
            content={"error": "Empty audio file"},
        )

    # Decode WAV -> numpy array
    try:
        audio_np, sr = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    except Exception as e:
        return JSONResponse(
            status_code=400,
            content={"error": f"Failed to decode audio: {e}"},
        )

    # Stereo -> mono
    if audio_np.ndim == 2:
        audio_np = audio_np.mean(axis=1)

    # Resample to 16kHz if needed
    target_sr = 16000
    if sr != target_sr:
        try:
            import librosa
            audio_np = librosa.resample(audio_np, orig_sr=sr, target_sr=target_sr)
        except ImportError:
            logger.warning(f"librosa not installed, cannot resample {sr}->{target_sr}")

    # Run inference
    try:
        result = _model.generate(
            input=audio_np,
            language=language or "zh",
            use_itn=True,
        )
    except Exception as e:
        logger.error(f"SenseVoice inference failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": f"Inference failed: {e}"},
        )

    # Extract text from FunASR result
    text = ""
    if result and len(result) > 0:
        item = result[0]
        if isinstance(item, dict):
            text = item.get("text", "")
        elif isinstance(item, (list, tuple)) and len(item) > 0:
            text = str(item[0].get("text", "")) if isinstance(item[0], dict) else str(item[0])
        elif isinstance(item, str):
            text = item

    # Clean up SenseVoice tags like <|zh|><|NEUTRAL|><|Speech|><|woitn|>
    import re
    text = re.sub(r"<\|[^|]*\|>", "", text).strip()

    latency_ms = (time.monotonic() - started) * 1000.0
    logger.info(f"Transcribed: '{text}' ({latency_ms:.0f}ms)")

    return {"text": text, "latency_ms": round(latency_ms, 1)}


@app.get("/health")
async def health():
    return {"status": "ok", "model": "SenseVoiceSmall"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SenseVoice ASR Server")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--device", type=str, default="cuda:0")
    args = parser.parse_args()

    load_model(device=args.device)
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
