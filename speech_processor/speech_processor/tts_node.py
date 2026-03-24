#!/usr/bin/env python3

# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause

"""
Enhanced TTS Node

Improved Text-to-Speech functionality with better architecture,
caching, and multiple provider support.
"""

import base64
import io
import importlib
import json
import os
import shutil
import subprocess
import time
import hashlib
import tempfile
import wave
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import threading

import numpy as np
from pydub import AudioSegment
from pydub.playback import play
import rclpy
from rclpy.node import Node
import requests
from std_msgs.msg import Bool, String, UInt8MultiArray
from go2_interfaces.msg import WebRtcReq


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
            except Exception:
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
            except Exception:
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
            except Exception:
                return {"enabled": True, "error": "Unable to read cache stats"}


class TTSProvider_ElevenLabs:
    """ElevenLabs TTS provider implementation"""

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
        except Exception:
            return None


class TTSProvider_Piper:
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
        except Exception:
            return None
        finally:
            try:
                if wav_path is not None and os.path.exists(wav_path):
                    os.unlink(wav_path)
            except Exception:
                pass


class TTSProvider_EdgeTTS:
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
        except Exception:
            return None


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
        except Exception:
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
        except Exception:
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

        # Initialize TTS provider
        self.tts_provider = self._create_tts_provider()

        if not self.tts_provider:
            self.get_logger().error("Failed to initialize TTS provider!")
            return

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
        else:
            self.get_logger().error(f"Unsupported TTS provider: {self.config.provider}")
            return None

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
        """Handle incoming TTS requests"""
        try:
            text = msg.data.strip()
            if not text:
                self.get_logger().warn("Received empty TTS request")
                return

            self.get_logger().info(
                f'🎤 TTS Request: "{text}" (voice: {self.config.voice_name})'
            )

            # Activate echo gate IMMEDIATELY — before synthesis, not after.
            # Without this, ASR records during the entire TTS synthesis + LLM
            # processing window (~8s), picking up Go2's playback as input.
            self._publish_tts_playing(True)

            # Resolve cache voice identity (edge-tts uses its own voice param)
            cache_voice = (
                self.config.edge_tts_voice
                if self.config.provider == TTSProvider.EDGE_TTS
                else self.config.voice_name
            )

            # Check cache first
            cache_hit = False
            audio_data = self.cache.get(
                text, cache_voice, self.config.provider.value
            )

            if audio_data:
                self.get_logger().info("💾 Cache hit - using cached audio")
                cache_hit = True
            else:
                if self.tts_provider is None:
                    self.get_logger().error("❌ TTS provider is not initialized")
                    return

                # Generate new speech
                self.get_logger().info("🔊 Generating new speech...")
                audio_data = self.tts_provider.synthesize(text)

                # Piper fallback if edge-tts fails
                if audio_data is None and self.config.provider == TTSProvider.EDGE_TTS:
                    self.get_logger().warn("edge-tts failed, falling back to Piper")
                    try:
                        piper_fb = TTSProvider_Piper(self.config)
                        audio_data = piper_fb.synthesize(text)
                        if audio_data:
                            # Cache under piper key, not edge_tts
                            self.cache.put(text, cache_voice, "piper", audio_data)
                            self.get_logger().info("💾 Piper fallback cached")
                    except Exception:
                        pass

                if audio_data:
                    # Cache the result
                    if self.cache.put(
                        text,
                        cache_voice,
                        self.config.provider.value,
                        audio_data,
                    ):
                        self.get_logger().info("💾 Audio cached successfully")
                else:
                    self.get_logger().error("❌ Failed to generate speech")
                    return

            # Process and play audio
            if self.config.local_playback:
                self._play_locally(audio_data)
            else:
                self._play_on_robot(audio_data)

            # Log success
            status = "cached" if cache_hit else "generated"
            self.get_logger().info(f"✅ TTS completed successfully ({status})")

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
                        timeout=30,
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
        "好的，停止動作。",
        "好的，坐下。",
        "好的，站起來。",
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
        print(f"❌ TTS Node error: {e}")
    finally:
        try:
            rclpy.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
