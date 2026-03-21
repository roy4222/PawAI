"""Whisper STT benchmark adapter.
Uses faster-whisper (CTranslate2) for benchmarking ASR inference.
Reference: speech_processor/speech_processor/stt_intent_node.py
"""
import logging
import os
import time
from typing import Any, Optional

import numpy as np

from benchmarks.adapters.base import BenchAdapter

logger = logging.getLogger(__name__)


class STTWhisperAdapter(BenchAdapter):
    """Benchmark adapter for Whisper via faster-whisper."""

    def __init__(self):
        self._model = None
        self._model_size = "small"

    def load(self, config: dict) -> None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "faster-whisper not installed. "
                "Run: uv pip install faster-whisper"
            )

        self._model_size = config.get("model_size", "small")
        device = config.get("device", "cuda")
        compute_type = config.get("compute_type", "float16")

        logger.info(f"Loading Whisper {self._model_size} "
                     f"(device={device}, compute_type={compute_type})...")
        t0 = time.time()
        self._model = WhisperModel(
            self._model_size,
            device=device,
            compute_type=compute_type,
        )
        elapsed = time.time() - t0
        logger.info(f"Whisper {self._model_size} loaded in {elapsed:.1f}s")

    def prepare_input(self, input_ref: str) -> np.ndarray:
        """Load audio file. Use input_ref='synthetic' for noise-based feasibility test."""
        if input_ref == "synthetic":
            # Explicit synthetic mode — 3s random noise for feasibility-only
            return np.random.randn(int(3.0 * 16000)).astype(np.float32) * 0.01

        if not os.path.isfile(input_ref):
            raise FileNotFoundError(
                f"Audio file not found: {input_ref}. "
                f"Use 'synthetic' for noise-based feasibility test."
            )

        try:
            import soundfile as sf
        except ImportError:
            raise ImportError(
                "soundfile not installed. Run: uv pip install soundfile"
            )

        audio, sr = sf.read(input_ref, dtype="float32")
        if sr != 16000:
            from scipy.signal import resample
            audio = resample(audio, int(len(audio) * 16000 / sr))
        return audio

    def infer(self, input_data: np.ndarray) -> dict:
        if self._model is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        segments, info = self._model.transcribe(
            input_data,
            language="zh",
            beam_size=1,
            vad_filter=False,
        )
        # Consume the generator to force actual inference
        text_parts = []
        for seg in segments:
            text_parts.append(seg.text)

        text = "".join(text_parts)
        duration_sec = len(input_data) / 16000
        return {
            "text": text,
            "language": info.language,
            "duration_sec": round(duration_sec, 2),
            "model_size": self._model_size,
        }

    def cleanup(self) -> None:
        self._model = None
