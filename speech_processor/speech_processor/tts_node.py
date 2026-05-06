#!/usr/bin/env python3

# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

"""
Enhanced TTS Node

Improved Text-to-Speech functionality with better architecture,
caching, and multiple provider support.
"""

import base64
import concurrent.futures
import io
import importlib
import json
import os
import re
import shutil
import subprocess
import time
import hashlib
import tempfile
import wave
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging
import threading

import numpy as np

_logger = logging.getLogger(__name__)
from pydub import AudioSegment
from pydub.playback import play
import rclpy
from rclpy.node import Node
import requests
from std_msgs.msg import Bool, String, UInt8MultiArray
from go2_interfaces.msg import WebRtcReq

from speech_processor.audio_tag import strip_audio_tags


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value is not None else default


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class AudioFormat(Enum):
    """Supported audio formats"""

    MP3 = "mp3"
    WAV = "wav"
    OGG = "ogg"


class TTSProvider(Enum):
    """Supported TTS providers"""

    ELEVENLABS = "elevenlabs"
    MELOTTS = "melotts"
    PIPER = "piper"
    GOOGLE = "google"
    AMAZON = "amazon"
    OPENAI = "openai"
    EDGE_TTS = "edge_tts"
    OPENROUTER_GEMINI = "openrouter_gemini"


@dataclass
class TTSConfig:
    """Configuration for TTS functionality"""

    api_key: str
    provider: TTSProvider = TTSProvider.ELEVENLABS
    voice_name: str = "XrExE9yKIg1WjnnlVkGX"
    local_playback: bool = False
    local_output_device: str = ""  # ALSA device, e.g. "plughw:3,0"
    use_cache: bool = True
    cache_dir: str = "tts_cache"
    chunk_size: int = 16 * 1024
    robot_chunk_interval_sec: float = 0.02
    robot_playback_tail_sec: float = 0.5
    robot_volume: int = 80
    playback_method: str = "datachannel"  # "datachannel" (Megaphone) or "audio_track"
    audio_quality: str = "standard"  # standard, high
    language: str = "en"

    # ElevenLabs specific settings
    stability: float = 0.5
    similarity_boost: float = 0.5
    model_id: str = "eleven_turbo_v2_5"

    # MeloTTS specific settings
    melo_language: str = "ZH"
    melo_speaker: str = "ZH"
    melo_speed: float = 1.0
    melo_device: str = "auto"

    piper_model_path: str = ""
    piper_config_path: str = ""
    piper_speaker_id: int = 0
    piper_length_scale: float = 1.0
    piper_noise_scale: float = 0.667
    piper_noise_w: float = 0.8
    piper_use_cuda: bool = False

    # edge-tts specific settings
    edge_tts_voice: str = "zh-CN-XiaoxiaoNeural"

    # OpenRouter Gemini TTS settings (Stage 3 of B1 Plan D)
    # Voice "Despina" selected after Stage 1 listening test on Jetson 5/4.
    # Model is preview-stage; latency baseline 3.6-5.1s avg ~4.6s on Jetson
    # (timeout 6.0s = baseline + ~30% headroom).
    openrouter_gemini_voice: str = "Despina"
    openrouter_gemini_model: str = "google/gemini-3.1-flash-tts-preview"
    openrouter_gemini_timeout_s: float = 60.0


class AudioCache:
    """Thread-safe audio cache management"""

    def __init__(self, cache_dir: str, enabled: bool = True):
        self.cache_dir = cache_dir
        self.enabled = enabled
        self._lock = threading.Lock()

        if self.enabled:
            os.makedirs(self.cache_dir, exist_ok=True)

    def get_cache_path(self, text: str, voice_name: str, provider: str) -> str:
        """Generate cache file path"""
        cache_key = f"{text}_{voice_name}_{provider}"
        text_hash = hashlib.md5(cache_key.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{text_hash}.mp3")

    def get(self, text: str, voice_name: str, provider: str) -> Optional[bytes]:
        """Get cached audio data"""
        if not self.enabled:
            return None

        with self._lock:
            cache_path = self.get_cache_path(text, voice_name, provider)
            if os.path.exists(cache_path):
                with open(cache_path, "rb") as f:
                    return f.read()
        return None

    def put(self, text: str, voice_name: str, provider: str, audio_data: bytes) -> bool:
        """Cache audio data"""
        if not self.enabled or not audio_data:
            return False

        with self._lock:
            try:
                cache_path = self.get_cache_path(text, voice_name, provider)
                with open(cache_path, "wb") as f:
                    f.write(audio_data)
                return True
            except Exception as e:
                _logger.warning("AudioCache.put failed: %s", e)
                return False

    def clear(self) -> bool:
        """Clear all cached files"""
        if not self.enabled:
            return True

        with self._lock:
            try:
                for filename in os.listdir(self.cache_dir):
                    file_path = os.path.join(self.cache_dir, filename)
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                return True
            except Exception as e:
                _logger.warning("AudioCache.clear failed: %s", e)
                return False

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        if not self.enabled:
            return {"enabled": False}

        with self._lock:
            try:
                files = os.listdir(self.cache_dir)
                total_size = sum(
                    os.path.getsize(os.path.join(self.cache_dir, f))
                    for f in files
                    if os.path.isfile(os.path.join(self.cache_dir, f))
                )
                return {
                    "enabled": True,
                    "file_count": len(files),
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "cache_dir": self.cache_dir,
                }
            except Exception as e:
                _logger.warning("AudioCache.get_cache_stats failed: %s", e)
                return {"enabled": True, "error": "Unable to read cache stats"}


class TTSProvider_ElevenLabs:
    """ElevenLabs TTS provider implementation"""

    # TTSProviderBase protocol attributes (Stage 2 refactor)
    name: str = "elevenlabs"
    sample_rate: int = 22050  # mp3 typical; pydub re-derives on decode
    supports_audio_tags: bool = False

    def __init__(self, config: TTSConfig):
        self.config = config
        self.base_url = "https://api.elevenlabs.io/v1"

    def synthesize(self, text: str) -> Optional[bytes]:
        """Generate speech using ElevenLabs API"""
        url = f"{self.base_url}/text-to-speech/{self.config.voice_name}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.config.api_key,
        }

        data = {
            "text": text,
            "model_id": self.config.model_id,
            "voice_settings": {
                "stability": self.config.stability,
                "similarity_boost": self.config.similarity_boost,
            },
        }

        try:
            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException:
            return None

    def get_voices(self) -> List[Dict[str, Any]]:
        """Get available voices"""
        url = f"{self.base_url}/voices"
        headers = {"xi-api-key": self.config.api_key}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json().get("voices", [])
        except requests.exceptions.RequestException:
            return []


class TTSProvider_MeloTTS:
    # TTSProviderBase protocol attributes (Stage 2 refactor)
    name: str = "melotts"
    sample_rate: int = 0  # dynamic, read from self._model.hps.data.sampling_rate
    supports_audio_tags: bool = False

    def __init__(self, config: TTSConfig):
        self.config = config
        try:
            melo_api = importlib.import_module("melo.api")
            tts_class = getattr(melo_api, "TTS")
        except Exception as exc:
            raise RuntimeError(
                "MeloTTS is not installed. Install with: pip3 install --user melotts"
            ) from exc

        self._model = tts_class(
            language=self.config.melo_language, device=self.config.melo_device
        )

    def _wav_from_array(self, audio_array: np.ndarray, sample_rate: int) -> bytes:
        normalized = np.clip(audio_array, -1.0, 1.0)
        pcm = (normalized * 32767.0).astype(np.int16)

        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return wav_io.getvalue()

    def synthesize(self, text: str) -> Optional[bytes]:
        try:
            speakers = self._model.hps.data.spk2id
            speaker_id = speakers.get(self.config.melo_speaker)
            if speaker_id is None:
                speaker_id = next(iter(speakers.values()))

            audio_np = self._model.tts_to_file(
                text,
                speaker_id,
                output_path=None,
                speed=self.config.melo_speed,
                quiet=True,
            )
            if audio_np is None:
                return None

            sample_rate = int(self._model.hps.data.sampling_rate)
            wav_data = self._wav_from_array(audio_np, sample_rate)

            audio = AudioSegment.from_wav(io.BytesIO(wav_data))
            mp3_io = io.BytesIO()
            audio.export(mp3_io, format="mp3")
            return mp3_io.getvalue()
        except Exception as e:
            _logger.warning("MeloTTS synthesize failed: %s", e)
            return None


class TTSProvider_Piper:
    # TTSProviderBase protocol attributes (Stage 2 refactor)
    name: str = "piper"
    sample_rate: int = 22050  # zh_CN-huayan-medium native rate
    supports_audio_tags: bool = False

    def __init__(self, config: TTSConfig):
        self.config = config
        self._piper_bin = shutil.which("piper")
        if self._piper_bin is None:
            user_piper = os.path.expanduser("~/.local/bin/piper")
            if os.path.exists(user_piper):
                self._piper_bin = user_piper
        if self._piper_bin is None:
            raise RuntimeError(
                "Piper CLI not found. Install with: pip3 install --user piper-tts"
            )

        if not self.config.piper_model_path:
            raise RuntimeError(
                "Piper model path is empty. Set parameter: piper_model_path"
            )

        if not os.path.exists(self.config.piper_model_path):
            raise RuntimeError(f"Piper model not found: {self.config.piper_model_path}")

        if self.config.piper_config_path and not os.path.exists(
            self.config.piper_config_path
        ):
            raise RuntimeError(
                f"Piper config not found: {self.config.piper_config_path}"
            )

    def synthesize(self, text: str) -> Optional[bytes]:
        wav_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                wav_path = tmp_wav.name

            cmd = [
                self._piper_bin,
                "-m",
                self.config.piper_model_path,
                "-f",
                wav_path,
                "--length_scale",
                str(self.config.piper_length_scale),
                "--noise_scale",
                str(self.config.piper_noise_scale),
                "--noise-w-scale",
                str(self.config.piper_noise_w),
                "-s",
                str(self.config.piper_speaker_id),
            ]

            if self.config.piper_config_path:
                cmd.extend(["-c", self.config.piper_config_path])

            if self.config.piper_use_cuda:
                cmd.append("--cuda")

            subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
                timeout=60,
            )

            with open(wav_path, "rb") as f:
                wav_data = f.read()

            return wav_data
        except Exception as e:
            _logger.warning("Piper synthesize failed: %s", e)
            return None
        finally:
            try:
                if wav_path is not None and os.path.exists(wav_path):
                    os.unlink(wav_path)
            except Exception as e:
                _logger.debug("Piper tmp cleanup failed: %s", e)


class TTSProvider_EdgeTTS:
    # TTSProviderBase protocol attributes (Stage 2 refactor)
    name: str = "edge_tts"
    sample_rate: int = 24000  # mp3 24 kHz mono confirmed via `file` on output
    supports_audio_tags: bool = False

    """Microsoft Edge TTS (cloud, high quality, zh-TW/zh-CN support)"""

    def __init__(self, config: TTSConfig):
        self.voice = config.edge_tts_voice
        self.timeout = 10

    def synthesize(self, text: str) -> Optional[bytes]:
        try:
            import asyncio
            import edge_tts

            async def _gen():
                communicate = edge_tts.Communicate(text, self.voice, rate="+10%")
                chunks = []
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        chunks.append(chunk["data"])
                return b"".join(chunks)

            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    asyncio.wait_for(_gen(), timeout=self.timeout)
                ) or None
            finally:
                loop.close()
        except Exception as e:
            _logger.warning("edge-tts synthesize failed: %s", e)
            return None


class TTSProvider_OpenRouterGemini:
    """Gemini 3.1 Flash TTS Preview via OpenRouter `/api/v1/audio/speech`.

    Stage 1 listening test on Jetson 5/4: voice "Despina" selected by user.
    Native audio tag support — passes `[excited]` `[laughs]` etc. through
    to Gemini which renders them as emotion/SFX (verified by ear). Hence
    `supports_audio_tags=True` (gates strip in tts_node.tts_callback).

    Output: OpenRouter returns raw PCM (audio/pcm;rate=24000;channels=1)
    when response_format=pcm. We wrap a WAV header (24kHz/16-bit/mono) in
    Python so downstream cache + pydub treat the result like any other WAV.

    Auth: reads `OPENROUTER_KEY` from env at call time. Not stored in
    TTSConfig.api_key (already used by ElevenLabs). Tracked in `.env` only.
    """

    # TTSProviderBase protocol attributes
    name: str = "openrouter_gemini"
    sample_rate: int = 24000
    supports_audio_tags: bool = True

    OPENROUTER_TTS_URL = "https://openrouter.ai/api/v1/audio/speech"

    def __init__(self, config: TTSConfig):
        self.voice = config.openrouter_gemini_voice
        self.model = config.openrouter_gemini_model
        self.timeout = float(config.openrouter_gemini_timeout_s)
        self._api_key = os.getenv("OPENROUTER_KEY", "") or os.getenv(
            "OPENROUTER_API_KEY", ""
        )
        if not self._api_key:
            _logger.warning(
                "OPENROUTER_KEY not set — TTSProvider_OpenRouterGemini will "
                "fail every synthesize() call until env is configured"
            )

    # Gemini Flash TTS Preview drops tail randomly when input ≥ ~80 chars
    # (5/6 evening empirical: 95-char chunks lose 25% of audio). Stay well
    # under that threshold; rely on parallel synthesis to keep latency flat.
    CHUNK_MAX_CHARS: int = 40
    SENTENCE_PUNCT: str = "。！？!?\n"

    _AUDIO_TAG_RE = re.compile(r"^\s*(\[[a-zA-Z][a-zA-Z _-]*\])\s*")

    def _split_for_tts(self, text: str) -> list[str]:
        """Split text into chunks ≤ CHUNK_MAX_CHARS at sentence boundaries.

        If text starts with an audio tag like ``[whispers]``, prepend that tag
        to every subsequent chunk so Gemini keeps the same voice characteristics
        across the whole reply (otherwise chunks 2+ revert to default voice).
        """
        text = text.strip()
        if not text:
            return []

        m = self._AUDIO_TAG_RE.match(text)
        leading_tag = m.group(1) if m else ""
        body = text[m.end() :].strip() if m else text

        if len(text) <= self.CHUNK_MAX_CHARS:
            return [text]

        raw_chunks: list[str] = []
        buf = ""
        for ch in body:
            buf += ch
            if ch in self.SENTENCE_PUNCT and len(buf) >= self.CHUNK_MAX_CHARS // 2:
                raw_chunks.append(buf.strip())
                buf = ""
            elif len(buf) >= self.CHUNK_MAX_CHARS:
                cut = max(buf.rfind("，"), buf.rfind(","), buf.rfind(" "))
                if cut > self.CHUNK_MAX_CHARS // 2:
                    raw_chunks.append(buf[: cut + 1].strip())
                    buf = buf[cut + 1 :]
                else:
                    raw_chunks.append(buf.strip())
                    buf = ""
        if buf.strip():
            raw_chunks.append(buf.strip())

        if not leading_tag:
            return [c for c in raw_chunks if c]

        # First chunk already has the tag (it's at the start of `text`); only
        # prepend to subsequent chunks to keep voice consistent.
        out: list[str] = []
        for idx, chunk in enumerate(raw_chunks):
            if not chunk:
                continue
            if idx == 0:
                out.append(f"{leading_tag} {chunk}")
            else:
                out.append(f"{leading_tag} {chunk}")
        return out

    def _timed_chunk(self, text: str) -> tuple[Optional[bytes], float]:
        """Wrap _synthesize_chunk with wall-clock timing for parallel debug."""
        t0 = time.monotonic()
        pcm = self._synthesize_chunk(text)
        return pcm, time.monotonic() - t0

    def _synthesize_chunk(self, text: str) -> Optional[bytes]:
        """One OpenRouter TTS request → raw PCM bytes (no WAV header)."""
        try:
            response = requests.post(
                self.OPENROUTER_TTS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": text,
                    "voice": self.voice,
                    "response_format": "pcm",
                },
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            _logger.warning(
                "openrouter_gemini timeout (%.1fs) for text=%r",
                self.timeout,
                text[:40],
            )
            return None
        except requests.exceptions.RequestException as exc:
            _logger.warning("openrouter_gemini request error: %s", exc)
            return None

        if response.status_code != 200:
            _logger.warning(
                "openrouter_gemini HTTP %s: %s",
                response.status_code,
                response.text[:200],
            )
            return None

        pcm = response.content
        if not pcm or pcm.startswith(b"{"):
            _logger.warning("openrouter_gemini empty or JSON body, len=%d", len(pcm))
            return None
        return pcm

    def synthesize(self, text: str) -> Optional[bytes]:
        if not self._api_key:
            return None

        chunks = self._split_for_tts(text)
        if not chunks:
            return None

        if len(chunks) == 1:
            pcm = self._synthesize_chunk(chunks[0])
            if pcm is None:
                return None
            full_pcm = pcm
        else:
            t0 = time.monotonic()
            _logger.warning(
                "openrouter_gemini: %d chunks parallel, sizes=%s",
                len(chunks),
                [len(c) for c in chunks],
            )
            # Fire all chunks in parallel; preserve order via index map.
            results: list[Optional[bytes]] = [None] * len(chunks)
            timings: list[float] = [0.0] * len(chunks)
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(len(chunks), 8)
            ) as pool:
                future_to_idx = {}
                for idx, chunk in enumerate(chunks):
                    fut = pool.submit(self._timed_chunk, chunk)
                    future_to_idx[fut] = idx
                for fut in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[fut]
                    pcm, latency = fut.result()
                    results[idx] = pcm
                    timings[idx] = latency
                    if pcm is None:
                        _logger.warning(
                            "openrouter_gemini chunk[%d] FAILED (%.2fs) text=%r",
                            idx,
                            latency,
                            chunks[idx][:30],
                        )
                    else:
                        _logger.warning(
                            "openrouter_gemini chunk[%d] ok (%.2fs, %d bytes)",
                            idx,
                            latency,
                            len(pcm),
                        )

            # Concatenate in original order, skip failed chunks gracefully.
            ok_parts = [p for p in results if p is not None]
            if not ok_parts:
                _logger.warning("openrouter_gemini: all chunks failed")
                return None
            full_pcm = b"".join(ok_parts)
            wall = time.monotonic() - t0
            _logger.warning(
                "openrouter_gemini: %d/%d chunks ok in %.2fs wall (max single=%.2fs), %.1fs audio",
                sum(1 for p in results if p is not None),
                len(chunks),
                wall,
                max(timings),
                len(full_pcm) / (self.sample_rate * 2),
            )

        # Wrap raw PCM (24kHz / 16-bit / mono) in a WAV container.
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit
            wf.setframerate(self.sample_rate)
            wf.writeframes(full_pcm)
        return wav_io.getvalue()


class AudioProcessor:
    """Audio processing utilities"""

    @staticmethod
    def convert_to_wav(
        audio_data: bytes, input_format: AudioFormat = AudioFormat.MP3
    ) -> Optional[bytes]:
        """Convert audio data to WAV format (16kHz, 16bit, mono for Go2)"""
        try:
            if input_format == AudioFormat.MP3:
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            elif input_format == AudioFormat.OGG:
                audio = AudioSegment.from_ogg(io.BytesIO(audio_data))
            elif input_format == AudioFormat.WAV:
                audio = AudioSegment.from_wav(io.BytesIO(audio_data))
            else:
                return audio_data

            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)

            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            return wav_io.getvalue()
        except Exception as e:
            _logger.warning("convert_to_wav failed: %s", e)
            return None

    @staticmethod
    def get_duration(audio_data: bytes, format: AudioFormat = AudioFormat.WAV) -> float:
        """Get audio duration in seconds"""
        try:
            if format == AudioFormat.WAV:
                audio = AudioSegment.from_wav(io.BytesIO(audio_data))
            elif format == AudioFormat.MP3:
                audio = AudioSegment.from_mp3(io.BytesIO(audio_data))
            else:
                audio = AudioSegment.from_file(io.BytesIO(audio_data))

            return len(audio) / 1000.0  # Convert ms to seconds
        except Exception as e:
            _logger.warning("get_duration failed: %s", e)
            return 0.0

    @staticmethod
    def split_into_chunks(data: bytes, chunk_size: int) -> List[bytes]:
        """Split data into chunks"""
        return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


class EnhancedTTSNode(Node):
    """Enhanced TTS Node with improved architecture"""

    def __init__(self):
        super().__init__("tts_node")

        # Declare parameters
        self._declare_parameters()

        # Load configuration
        self.config = self._load_configuration()

        # Initialize components
        self.cache = AudioCache(self.config.cache_dir, self.config.use_cache)
        self.audio_processor = AudioProcessor()

        # Initialize TTS provider + fallback chain (Stage 4 of B1 Plan D)
        self.tts_provider = self._create_tts_provider()
        self._fallback_chain: List = []

        if not self.tts_provider:
            self.get_logger().error("Failed to initialize TTS provider!")
            return

        self._fallback_chain = self._build_fallback_chain()

        # Setup subscriptions and publishers
        self._setup_communication()

        self.RTC_TOPIC = {"AUDIO_HUB_REQ": "rt/api/audiohub/request"}

        # Log initialization
        self._log_initialization()

        # Cache warmup: pre-synthesize common template replies in background
        threading.Thread(target=self._warmup_cache, daemon=True).start()

    def _declare_parameters(self) -> None:
        """Declare all node parameters"""
        self.declare_parameter(
            "api_key", _env_str("TTS_API_KEY", _env_str("ELEVENLABS_API_KEY", ""))
        )
        self.declare_parameter("provider", _env_str("TTS_PROVIDER", "elevenlabs"))
        self.declare_parameter(
            "voice_name", _env_str("TTS_VOICE_NAME", "XrExE9yKIg1WjnnlVkGX")
        )
        self.declare_parameter("local_playback", False)
        self.declare_parameter("local_output_device", "")
        self.declare_parameter("use_cache", True)
        self.declare_parameter("cache_dir", "tts_cache")
        self.declare_parameter("chunk_size", 16384)
        self.declare_parameter("robot_chunk_interval_sec", 0.02)
        self.declare_parameter("robot_playback_tail_sec", 0.5)
        self.declare_parameter("robot_volume", 80)
        self.declare_parameter("playback_method", "datachannel")
        self.declare_parameter("audio_quality", "standard")
        self.declare_parameter("language", "en")
        self.declare_parameter("stability", 0.5)
        self.declare_parameter("similarity_boost", 0.5)
        self.declare_parameter("model_id", "eleven_turbo_v2_5")
        self.declare_parameter("melo_language", _env_str("MELO_LANGUAGE", "ZH"))
        self.declare_parameter("melo_speaker", _env_str("MELO_SPEAKER", "ZH"))
        self.declare_parameter("melo_speed", _env_float("MELO_SPEED", 1.0))
        self.declare_parameter("melo_device", _env_str("MELO_DEVICE", "auto"))
        self.declare_parameter("piper_model_path", _env_str("PIPER_MODEL_PATH", ""))
        self.declare_parameter("piper_config_path", _env_str("PIPER_CONFIG_PATH", ""))
        self.declare_parameter("piper_speaker_id", _env_int("PIPER_SPEAKER_ID", 0))
        self.declare_parameter(
            "piper_length_scale", _env_float("PIPER_LENGTH_SCALE", 1.0)
        )
        self.declare_parameter(
            "piper_noise_scale", _env_float("PIPER_NOISE_SCALE", 0.667)
        )
        self.declare_parameter("piper_noise_w", _env_float("PIPER_NOISE_W", 0.8))
        self.declare_parameter("piper_use_cuda", _env_bool("PIPER_USE_CUDA", False))
        self.declare_parameter(
            "edge_tts_voice", _env_str("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural")
        )
        self.declare_parameter(
            "openrouter_gemini_voice",
            _env_str("OPENROUTER_GEMINI_VOICE", "Despina"),
        )
        self.declare_parameter(
            "openrouter_gemini_model",
            _env_str(
                "OPENROUTER_GEMINI_MODEL", "google/gemini-3.1-flash-tts-preview"
            ),
        )
        self.declare_parameter(
            "openrouter_gemini_timeout_s",
            _env_float("OPENROUTER_GEMINI_TIMEOUT_S", 6.0),
        )

    def _load_configuration(self) -> TTSConfig:
        """Load configuration from parameters"""
        provider_str = self.get_parameter("provider").get_parameter_value().string_value
        try:
            provider = TTSProvider(provider_str)
        except ValueError:
            provider = TTSProvider.ELEVENLABS

        return TTSConfig(
            api_key=self.get_parameter("api_key").get_parameter_value().string_value,
            provider=provider,
            voice_name=self.get_parameter("voice_name")
            .get_parameter_value()
            .string_value,
            local_playback=self.get_parameter("local_playback")
            .get_parameter_value()
            .bool_value,
            local_output_device=self.get_parameter("local_output_device")
            .get_parameter_value()
            .string_value,
            use_cache=self.get_parameter("use_cache").get_parameter_value().bool_value,
            cache_dir=self.get_parameter("cache_dir")
            .get_parameter_value()
            .string_value,
            chunk_size=self.get_parameter("chunk_size")
            .get_parameter_value()
            .integer_value,
            robot_chunk_interval_sec=self.get_parameter("robot_chunk_interval_sec")
            .get_parameter_value()
            .double_value,
            robot_playback_tail_sec=self.get_parameter("robot_playback_tail_sec")
            .get_parameter_value()
            .double_value,
            robot_volume=self.get_parameter("robot_volume")
            .get_parameter_value()
            .integer_value,
            playback_method=self.get_parameter("playback_method")
            .get_parameter_value()
            .string_value,
            audio_quality=self.get_parameter("audio_quality")
            .get_parameter_value()
            .string_value,
            language=self.get_parameter("language").get_parameter_value().string_value,
            stability=self.get_parameter("stability")
            .get_parameter_value()
            .double_value,
            similarity_boost=self.get_parameter("similarity_boost")
            .get_parameter_value()
            .double_value,
            model_id=self.get_parameter("model_id").get_parameter_value().string_value,
            melo_language=self.get_parameter("melo_language")
            .get_parameter_value()
            .string_value,
            melo_speaker=self.get_parameter("melo_speaker")
            .get_parameter_value()
            .string_value,
            melo_speed=self.get_parameter("melo_speed")
            .get_parameter_value()
            .double_value,
            melo_device=self.get_parameter("melo_device")
            .get_parameter_value()
            .string_value,
            piper_model_path=self.get_parameter("piper_model_path")
            .get_parameter_value()
            .string_value,
            piper_config_path=self.get_parameter("piper_config_path")
            .get_parameter_value()
            .string_value,
            piper_speaker_id=self.get_parameter("piper_speaker_id")
            .get_parameter_value()
            .integer_value,
            piper_length_scale=self.get_parameter("piper_length_scale")
            .get_parameter_value()
            .double_value,
            piper_noise_scale=self.get_parameter("piper_noise_scale")
            .get_parameter_value()
            .double_value,
            piper_noise_w=self.get_parameter("piper_noise_w")
            .get_parameter_value()
            .double_value,
            piper_use_cuda=self.get_parameter("piper_use_cuda")
            .get_parameter_value()
            .bool_value,
            edge_tts_voice=self.get_parameter("edge_tts_voice")
            .get_parameter_value()
            .string_value,
            openrouter_gemini_voice=self.get_parameter("openrouter_gemini_voice")
            .get_parameter_value()
            .string_value,
            openrouter_gemini_model=self.get_parameter("openrouter_gemini_model")
            .get_parameter_value()
            .string_value,
            openrouter_gemini_timeout_s=self.get_parameter(
                "openrouter_gemini_timeout_s"
            )
            .get_parameter_value()
            .double_value,
        )

    def _create_tts_provider(self):
        """Create TTS provider based on configuration"""
        if self.config.provider == TTSProvider.ELEVENLABS:
            if not self.config.api_key:
                self.get_logger().error("ElevenLabs API key not provided!")
                return None
            return TTSProvider_ElevenLabs(self.config)
        elif self.config.provider == TTSProvider.MELOTTS:
            return TTSProvider_MeloTTS(self.config)
        elif self.config.provider == TTSProvider.PIPER:
            return TTSProvider_Piper(self.config)
        elif self.config.provider == TTSProvider.EDGE_TTS:
            return TTSProvider_EdgeTTS(self.config)
        elif self.config.provider == TTSProvider.OPENROUTER_GEMINI:
            return TTSProvider_OpenRouterGemini(self.config)
        else:
            self.get_logger().error(f"Unsupported TTS provider: {self.config.provider}")
            return None

    def _build_fallback_chain(self) -> List:
        """Build provider fallback chain based on main provider.

        Stage 4 of B1 Plan D: keeps demo audible when the cloud TTS path
        fails (timeout / 4xx / network). edge-tts is a quick cloud second;
        Piper is the offline last-line. Audio tag handling is per-provider
        — when a fallback runs, tts_callback strips tags first because
        edge-tts and Piper don't render them.

        Returns list of fallback provider instances (excluding the main
        one). Failures during instantiation are warned and skipped, not
        fatal — a chain with one fallback is still better than zero.
        """
        chain: List = []
        if self.config.provider == TTSProvider.OPENROUTER_GEMINI:
            for cls in (TTSProvider_EdgeTTS, TTSProvider_Piper):
                try:
                    chain.append(cls(self.config))
                except Exception as exc:
                    self.get_logger().warning(
                        f"Skipping fallback {cls.__name__}: {exc}"
                    )
        elif self.config.provider == TTSProvider.EDGE_TTS:
            try:
                chain.append(TTSProvider_Piper(self.config))
            except Exception as exc:
                self.get_logger().warning(f"Skipping Piper fallback: {exc}")
        return chain

    def _cache_voice_for(self, provider_name: str) -> str:
        """Resolve the voice identifier used in cache keys per provider.

        Each provider has its own voice space (Gemini "Despina" vs
        edge-tts "zh-CN-XiaoxiaoNeural" vs ElevenLabs voice ID), so cache
        keys must match the provider that produced the audio.
        """
        if provider_name == "edge_tts":
            return self.config.edge_tts_voice
        if provider_name == "openrouter_gemini":
            return self.config.openrouter_gemini_voice
        return self.config.voice_name

    def _setup_communication(self) -> None:
        """Setup ROS2 communication"""
        self.subscription = self.create_subscription(
            String, "/tts", self.tts_callback, 10
        )

        self.audio_pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)
        self.audio_raw_pub = self.create_publisher(UInt8MultiArray, "/tts_audio_raw", 10)
        # Latched (transient_local) so subscribers/echo always get the last value
        from rclpy.qos import QoSProfile, DurabilityPolicy
        tts_playing_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.tts_playing_pub = self.create_publisher(Bool, "/state/tts_playing", tts_playing_qos)
        # Publish initial idle state so latched topic has a valid value
        self._publish_tts_playing(False)

        # Service for cache management
        # self.cache_service = self.create_service(
        #     Empty, "clear_tts_cache", self.clear_cache_callback
        # )

    def tts_callback(self, msg: String) -> None:
        """Handle incoming TTS requests via main+fallback provider chain.

        Stage 4 of B1 Plan D: replaces the inline edge_tts→Piper fallback
        with a uniform chain iteration. Each provider in the chain:
        - resolves its own text (strip audio tags if !supports_audio_tags)
        - looks up its own provider-specific cache slot
        - synthesizes; on failure (None) we move to the next provider.
        """
        try:
            raw_text = msg.data.strip()
            if not raw_text:
                self.get_logger().warn("Received empty TTS request")
                return

            if self.tts_provider is None:
                self.get_logger().error("❌ TTS provider is not initialized")
                return

            # Activate echo gate IMMEDIATELY — before any synthesis attempt.
            # ASR otherwise records during the entire synth + playback window
            # (~8s), capturing Go2's own playback as input.
            self._publish_tts_playing(True)

            chain = [self.tts_provider] + list(self._fallback_chain)
            audio_data = None
            cache_hit = False
            served_by = ""

            for prov in chain:
                pname = getattr(prov, "name", prov.__class__.__name__)
                # Per-provider tag handling. Provider's supports_audio_tags
                # flag (see tts_provider.py TTSProviderBase) gates the strip:
                #   True  → pass tags through (Gemini renders [excited])
                #   False → strip tags (edge-tts/Piper read them literally)
                supports_tags = bool(getattr(prov, "supports_audio_tags", False))
                if supports_tags:
                    text = raw_text
                else:
                    text = strip_audio_tags(raw_text)
                    if not text:
                        self.get_logger().warn(
                            f"[{pname}] empty after tag strip: {raw_text!r}, "
                            f"trying next provider"
                        )
                        continue

                cache_voice = self._cache_voice_for(pname)

                # Per-provider log header (replaces the legacy single-line log
                # that always showed config.voice_name regardless of active
                # provider — cosmetic fix bundled with chain refactor)
                if text != raw_text:
                    self.get_logger().info(
                        f'🎤 [{pname}] "{raw_text}" → stripped "{text}" '
                        f"(voice: {cache_voice})"
                    )
                else:
                    self.get_logger().info(
                        f'🎤 [{pname}] "{text}" (voice: {cache_voice})'
                    )

                # Cache lookup (per-provider key)
                hit = self.cache.get(text, cache_voice, pname)
                if hit:
                    self.get_logger().info(f"💾 Cache hit [{pname}]")
                    audio_data = hit
                    cache_hit = True
                    served_by = pname
                    break

                # Synthesize
                self.get_logger().info(f"🔊 Generating [{pname}]...")
                try:
                    fresh = prov.synthesize(text)
                except Exception as exc:
                    self.get_logger().warning(
                        f"[{pname}] synthesize raised: {exc}, trying next"
                    )
                    continue

                if fresh:
                    if self.cache.put(text, cache_voice, pname, fresh):
                        self.get_logger().info(f"💾 Cached [{pname}]")
                    audio_data = fresh
                    served_by = pname
                    break
                else:
                    self.get_logger().warn(
                        f"[{pname}] returned no audio, trying next provider"
                    )

            if audio_data is None:
                self.get_logger().error(
                    "❌ Failed to generate speech (all providers exhausted)"
                )
                self._publish_tts_playing(False)
                return

            # Process and play audio
            if self.config.local_playback:
                self._play_locally(audio_data)
            else:
                self._play_on_robot(audio_data)

            # Log success
            status = "cached" if cache_hit else "generated"
            self.get_logger().info(
                f"✅ TTS completed [{served_by}] ({status})"
            )

        except Exception as e:
            self.get_logger().error(f"❌ TTS processing error: {str(e)}")
            self._publish_tts_playing(False)

    def _play_locally(self, audio_data: bytes) -> None:
        """Play audio locally via ALSA device or pydub fallback."""
        try:
            self._publish_tts_playing(True)
            audio = AudioSegment.from_file(io.BytesIO(audio_data))

            if self.config.local_output_device:
                # Use aplay with explicit ALSA device
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp_path = f.name
                    audio.export(f, format="wav")
                try:
                    subprocess.run(
                        ["aplay", "-D", self.config.local_output_device, tmp_path],
                        check=True,
                        capture_output=True,
                        timeout=max(30.0, audio.duration_seconds + 10.0),
                    )
                finally:
                    os.unlink(tmp_path)
            else:
                play(audio)

            self.get_logger().info("🔊 Local playback completed")
        except Exception as e:
            self.get_logger().error(f"❌ Local playback error: {str(e)}")
        finally:
            self._publish_tts_playing(False)

    def _publish_tts_playing(self, playing: bool) -> None:
        """Publish TTS playback state for echo gate."""
        msg = Bool()
        msg.data = playing
        self.tts_playing_pub.publish(msg)

    def _play_on_robot(self, audio_data: bytes) -> None:
        """Send audio to robot for playback"""
        try:
            if self.config.playback_method == "audio_track":
                # Audio track: convert to WAV without forcing 16kHz
                # (TtsAudioTrack handles resample to 48kHz internally)
                wav_data = self._convert_to_wav_native(audio_data)
                if not wav_data:
                    self.get_logger().error("Failed to convert audio to WAV")
                    return
                duration = self.audio_processor.get_duration(wav_data, AudioFormat.WAV)
                self._play_on_robot_audio_track(wav_data, duration)
            else:
                # DataChannel: needs 16kHz/16bit/mono for Go2 audiohub
                # Piper now returns WAV directly; other providers still return MP3
                src_fmt = AudioFormat.WAV if self.config.provider == TTSProvider.PIPER else AudioFormat.MP3
                wav_data = self.audio_processor.convert_to_wav(audio_data, src_fmt)
                if not wav_data:
                    self.get_logger().error("Failed to convert audio to WAV")
                    return
                duration = self.audio_processor.get_duration(wav_data, AudioFormat.WAV)
                self._play_on_robot_datachannel(wav_data, duration)

        except Exception as e:
            self._publish_tts_playing(False)
            self.get_logger().error(f"Robot playback error: {str(e)}")

    def _convert_to_wav_native(self, audio_data: bytes) -> bytes:
        """Convert MP3/audio to WAV keeping original sample rate (no 16kHz downsampling)."""
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(io.BytesIO(audio_data))
            # Only convert to mono, keep original sample rate
            audio = audio.set_channels(1).set_sample_width(2)
            buf = io.BytesIO()
            audio.export(buf, format="wav")
            return buf.getvalue()
        except Exception as e:
            self.get_logger().error(f"WAV conversion error: {e}")
            return b""

    def _play_on_robot_audio_track(self, wav_data: bytes, duration: float) -> None:
        """Send WAV via WebRTC audio track (new method)."""
        self.get_logger().info(
            f"Sending audio via audio_track: {duration:.1f}s, {len(wav_data)} bytes"
        )

        self._publish_tts_playing(True)

        msg = UInt8MultiArray()
        msg.data = list(wav_data)
        self.audio_raw_pub.publish(msg)

        # Wait for playback to complete
        self.get_logger().info(f"Waiting for playback ({duration:.1f}s)...")
        time.sleep(max(0.0, duration + self.config.robot_playback_tail_sec))

        self._publish_tts_playing(False)
        self.get_logger().info("Robot playback completed")

    def _play_on_robot_datachannel(self, wav_data: bytes, duration: float) -> None:
        """Send WAV via DataChannel Megaphone.

        Protocol (verified 2026-03-17, aligned with go2_webrtc_connect):
          ENTER_MEGAPHONE(4001) → UPLOAD_MEGAPHONE(4003) × N → EXIT_MEGAPHONE(4002)
          chunk_size = 4096 (base64 chars), payload must include current_block_size.
        """
        MEGAPHONE_CHUNK_SIZE = 4096
        MEGAPHONE_GAIN_DB = 16  # Boost speech volume (+16dB, ~26% clip OK for speech)

        # Boost WAV volume (Go2 Megaphone output is quiet)
        try:
            audio_seg = AudioSegment.from_file(io.BytesIO(wav_data))
            audio_seg = audio_seg.apply_gain(MEGAPHONE_GAIN_DB)
            buf = io.BytesIO()
            audio_seg.export(buf, format="wav")
            wav_data = buf.getvalue()
        except Exception as e:
            self.get_logger().warning(f"Gain boost failed: {e}")

        b64_encoded = base64.b64encode(wav_data).decode("utf-8")
        chunks = [b64_encoded[i:i + MEGAPHONE_CHUNK_SIZE]
                  for i in range(0, len(b64_encoded), MEGAPHONE_CHUNK_SIZE)]
        total_chunks = len(chunks)

        self.get_logger().info(
            f"Megaphone: {total_chunks} chunks, {duration:.1f}s"
        )

        self._publish_tts_playing(True)

        # Enter megaphone mode
        self._send_audio_command(4001, json.dumps({}))
        time.sleep(0.1)

        try:
            # Upload chunks
            for chunk_idx, chunk in enumerate(chunks, 1):
                audio_block = {
                    "current_block_size": len(chunk),
                    "block_content": chunk,
                    "current_block_index": chunk_idx,
                    "total_block_number": total_chunks,
                }
                self._send_audio_command(4003, json.dumps(audio_block))
                time.sleep(0.07)  # 70ms interval

            self.get_logger().info(f"Waiting for playback ({duration:.1f}s)...")
            time.sleep(max(0.0, duration + self.config.robot_playback_tail_sec))
        finally:
            # ALWAYS send EXIT — if skipped, Go2 stays in ENTER state and goes silent
            exit_ok = True
            try:
                self._send_audio_command(4002, json.dumps({}))
            except Exception as exc:
                exit_ok = False
                self.get_logger().error(f"Megaphone EXIT(4002) failed: {exc}")
            # Cooldown: let Go2 Megaphone state machine fully reset before next session.
            # Echo gate stays active during this 0.5s (_tts_playing still True).
            # Total echo gate closure = 0.5s cooldown + 1.0s echo_cooldown_ms = 1.5s.
            time.sleep(0.5)
            self._publish_tts_playing(False)
            if exit_ok:
                self.get_logger().info("Megaphone playback completed (cooldown 0.5s)")
            else:
                self.get_logger().warn("Megaphone playback finished but EXIT failed (cooldown 0.5s)")

    def _send_audio_command(self, api_id: int, parameter: str) -> None:
        """Send audio command to robot"""
        req = WebRtcReq()
        req.api_id = api_id
        req.priority = 0
        req.parameter = parameter
        req.topic = str(self.RTC_TOPIC["AUDIO_HUB_REQ"])
        self.audio_pub.publish(req)

    _WARMUP_PHRASES = [
        "哈囉，我在這裡。",
        "收到，我過去找你。",
        "收到，正在拍照。",
        "我目前狀態正常。",
        "請再說一次。",
    ]

    def _warmup_cache(self) -> None:
        """Pre-synthesize common replies into cache at startup."""
        if self.tts_provider is None:
            return
        cache_voice = (
            self.config.edge_tts_voice
            if self.config.provider == TTSProvider.EDGE_TTS
            else self.config.voice_name
        )
        count = 0
        for phrase in self._WARMUP_PHRASES:
            if self.cache.get(phrase, cache_voice, self.config.provider.value):
                continue  # already cached
            audio = self.tts_provider.synthesize(phrase)
            if audio:
                self.cache.put(phrase, cache_voice, self.config.provider.value, audio)
                count += 1
        if count:
            self.get_logger().info(f"🔥 Cache warmup: {count} phrases pre-synthesized")

    def _log_initialization(self) -> None:
        """Log initialization details"""
        cache_stats = self.cache.get_cache_stats()

        self.get_logger().info("🎤 Enhanced TTS Node Initialized")
        self.get_logger().info(f"   Provider: {self.config.provider.value}")
        self.get_logger().info(f"   Voice: {self.config.voice_name}")
        self.get_logger().info(
            f"   Playback: {'Local' if self.config.local_playback else 'Robot'}"
        )
        self.get_logger().info(f"   Language: {self.config.language}")
        self.get_logger().info(f"   Quality: {self.config.audio_quality}")

        if cache_stats["enabled"]:
            self.get_logger().info(
                f"   Cache: Enabled ({cache_stats.get('file_count', 0)} files, "
                f"{cache_stats.get('total_size_mb', 0)}MB)"
            )
        else:
            self.get_logger().info("   Cache: Disabled")


def main(args=None):
    """Main entry point"""
    rclpy.init(args=args)

    try:
        node = EnhancedTTSNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"TTS Node error: {e}")
    finally:
        try:
            node.destroy_node()
        except Exception:
            pass
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
