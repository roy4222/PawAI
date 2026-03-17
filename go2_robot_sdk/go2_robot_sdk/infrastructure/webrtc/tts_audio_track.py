"""
Custom AudioStreamTrack for TTS playback via WebRTC audio track.

Accepts WAV bytes, resamples to 48kHz mono, and streams via RTP to Go2.
When no audio is queued, sends silence to keep the RTP stream alive.

This is the replacement for the DataChannel Megaphone API (4001/4003/4002)
which stopped working on Go2 firmware v1.1.7+.
"""

import asyncio
import fractions
import hashlib
import io
import logging
import time as _time
import wave

import av
import numpy as np
from aiortc import MediaStreamTrack
from aiortc.mediastreams import MediaStreamError
from av import AudioFrame

logger = logging.getLogger(__name__)

AUDIO_PTIME = 0.02  # 20ms per frame — aiortc standard


class TtsAudioTrack(MediaStreamTrack):
    """
    Custom audio track: reads PCM from an asyncio.Queue,
    sends silence when queue is empty.

    Compatible with aiortc 1.3.0+ (uses MediaStreamTrack base).
    """

    kind = "audio"

    def __init__(self, sample_rate: int = 48000):
        super().__init__()
        self._sample_rate = sample_rate
        self._samples_per_frame = int(AUDIO_PTIME * sample_rate)  # 960 @ 48kHz

        # PCM buffer queue: stores numpy int16 arrays
        self._queue: asyncio.Queue = asyncio.Queue()

        # Current playback buffer and offset
        self._current_buffer = None
        self._buffer_offset: int = 0

        # PTS counter
        self._pts: int = 0

        # Observability
        self._play_id: int = 0
        self._current_play_id: int = 0
        self._frames_sent: int = 0
        self._play_start_ts: float = 0.0
        self._last_hash: str = ""

        logger.info(
            "TtsAudioTrack initialized: %dHz, %d samples/frame",
            sample_rate, self._samples_per_frame,
        )

    async def enqueue_audio(self, wav_bytes: bytes) -> None:
        """
        Parse WAV bytes, resample to 48kHz mono s16, and enqueue for playback.
        Can be called from any thread via enqueue_audio_threadsafe().
        """
        try:
            # Hash dedup: skip if same WAV within 1 second
            wav_hash = hashlib.md5(wav_bytes).hexdigest()[:12]
            now = _time.time()
            if wav_hash == self._last_hash and (now - self._play_start_ts) < 1.0:
                logger.info("[TTS TRACK] Dedup skip hash=%s", wav_hash)
                return
            self._last_hash = wav_hash

            # Assign play ID
            self._play_id += 1
            play_id = self._play_id

            container = av.open(io.BytesIO(wav_bytes), format="wav")
            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=self._sample_rate,
            )

            all_samples = []
            for frame in container.decode(audio=0):
                resampled = resampler.resample(frame)
                for rf in resampled:
                    arr = rf.to_ndarray().flatten().astype(np.int16)
                    all_samples.append(arr)

            # Flush resampler
            resampled = resampler.resample(None)
            for rf in resampled:
                arr = rf.to_ndarray().flatten().astype(np.int16)
                all_samples.append(arr)

            container.close()

            if all_samples:
                pcm = np.concatenate(all_samples)

                # Clear any previous audio (only play latest)
                while not self._queue.empty():
                    try:
                        self._queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                self._current_buffer = None
                self._buffer_offset = 0

                # Save debug WAV
                try:
                    dbg_path = f"/tmp/tts_debug_{play_id}.wav"
                    with wave.open(dbg_path, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self._sample_rate)
                        wf.writeframes(pcm.tobytes())
                    logger.info("[TTS TRACK] Debug WAV saved: %s", dbg_path)
                except Exception:
                    pass

                await self._queue.put(pcm)
                self._current_play_id = play_id
                self._frames_sent = 0
                self._play_start_ts = _time.time()
                duration_s = len(pcm) / self._sample_rate
                logger.info(
                    "[TTS TRACK] play_id=%d hash=%s enqueue %.1fs (%d samples)",
                    play_id, wav_hash, duration_s, len(pcm),
                )
            else:
                logger.warning("[TTS TRACK] No audio samples decoded from WAV")

        except Exception as e:
            logger.error("[TTS TRACK] Failed to enqueue audio: %s", e)

    def enqueue_audio_threadsafe(
        self, wav_bytes: bytes, loop: asyncio.AbstractEventLoop
    ) -> None:
        """
        Thread-safe entry point for ROS2 callbacks.
        Schedules enqueue_audio() on the asyncio event loop.
        """
        asyncio.run_coroutine_threadsafe(self.enqueue_audio(wav_bytes), loop)

    async def recv(self) -> AudioFrame:
        """
        Called by aiortc to get the next audio frame.
        Paces at AUDIO_PTIME (20ms) to match real-time RTP delivery.
        Without pacing, aiortc's _run_rtp loop drains all frames instantly,
        causing a burst that Go2's jitter buffer drops.
        """
        if self.readyState != "live":
            raise MediaStreamError

        # Pace: one frame every 20ms (real-time delivery)
        await asyncio.sleep(AUDIO_PTIME)

        samples = self._samples_per_frame
        output = np.zeros(samples, dtype=np.int16)
        filled = 0

        while filled < samples:
            if (
                self._current_buffer is None
                or self._buffer_offset >= len(self._current_buffer)
            ):
                try:
                    self._current_buffer = self._queue.get_nowait()
                    self._buffer_offset = 0
                except asyncio.QueueEmpty:
                    break

            remaining = len(self._current_buffer) - self._buffer_offset
            needed = samples - filled
            to_copy = min(remaining, needed)

            output[filled : filled + to_copy] = self._current_buffer[
                self._buffer_offset : self._buffer_offset + to_copy
            ]

            self._buffer_offset += to_copy
            filled += to_copy

        frame = AudioFrame.from_ndarray(
            output.reshape(1, -1), format="s16", layout="mono"
        )
        frame.sample_rate = self._sample_rate
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, self._sample_rate)

        self._pts += samples

        # Track frame count for active playback
        if filled > 0:
            self._frames_sent += 1
            # Log completion when buffer drains
            if (
                self._current_buffer is not None
                and self._buffer_offset >= len(self._current_buffer)
                and self._queue.empty()
            ):
                elapsed = _time.time() - self._play_start_ts
                logger.info(
                    "[TTS TRACK] play_id=%d DONE frames=%d elapsed=%.1fs",
                    self._current_play_id,
                    self._frames_sent,
                    elapsed,
                )

        return frame
