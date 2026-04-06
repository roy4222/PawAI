"""ASR client — resample audio + call SenseVoice cloud API."""
from __future__ import annotations

import subprocess
import tempfile
import time
from pathlib import Path

import requests


def resample_to_wav16k(audio_bytes: bytes) -> bytes:
    """Convert any audio to 16kHz mono PCM16 WAV using ffmpeg.

    Accepts WAV, webm/opus, ogg, mp3, etc — anything ffmpeg can decode.
    """
    with tempfile.NamedTemporaryFile(suffix=".input", delete=False) as f_in:
        f_in.write(audio_bytes)
        in_path = f_in.name

    out_path = in_path + ".wav"
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", in_path,
                "-ar", "16000",
                "-ac", "1",
                "-sample_fmt", "s16",
                "-f", "wav",
                out_path,
            ],
            capture_output=True,
            timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()}")
        return Path(out_path).read_bytes()
    finally:
        Path(in_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)


def transcribe(
    wav16k_bytes: bytes,
    asr_url: str = "http://127.0.0.1:8001/v1/audio/transcriptions",
    model: str = "sensevoice",
    language: str = "zh",
    timeout: float = 5.0,
) -> dict:
    """POST WAV to SenseVoice ASR, return {"text": ..., "latency_ms": ...}."""
    started = time.monotonic()
    files = {"file": ("speech.wav", wav16k_bytes, "audio/wav")}
    data = {"model": model, "language": language, "sample_rate": "16000"}

    resp = requests.post(asr_url, data=data, files=files, timeout=timeout)
    resp.raise_for_status()

    latency_ms = (time.monotonic() - started) * 1000
    body = resp.json()
    text = body.get("text", "")
    return {"text": text, "latency_ms": round(latency_ms, 2)}
