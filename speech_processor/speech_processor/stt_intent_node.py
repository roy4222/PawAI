#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

import io
import json
import queue
import re
import threading
import time
import wave
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from secrets import token_hex
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

try:
    import requests
except Exception:  # pragma: no cover - optional runtime dependency error handled later
    requests = None


from .intent_classifier import SUPPORTED_INTENTS, IntentClassifier, IntentMatch


@dataclass
class ASRResult:
    text: str
    provider: str
    latency_ms: float
    degraded: bool = False
    raw: Optional[Dict[str, Any]] = None


class ASRProvider(ABC):
    def __init__(self, provider_name: str, timeout_sec: float) -> None:
        self.provider_name = provider_name
        self.timeout_sec = timeout_sec

    @abstractmethod
    def transcribe(
        self, audio_bytes: bytes, sample_rate: int, language: str
    ) -> ASRResult:
        raise NotImplementedError


class QwenASRProvider(ASRProvider):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_sec: float,
        model_name: str,
        response_text_field: str,
    ) -> None:
        super().__init__(provider_name="qwen_cloud", timeout_sec=timeout_sec)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_name = model_name
        self.response_text_field = response_text_field

    def transcribe(
        self, audio_bytes: bytes, sample_rate: int, language: str
    ) -> ASRResult:
        if requests is None:
            raise RuntimeError("requests is required for QwenASRProvider")
        if not self.base_url:
            raise RuntimeError("qwen_asr.base_url is empty")

        started = time.monotonic()
        files = {"file": ("speech.wav", audio_bytes, "audio/wav")}
        data = {
            "model": self.model_name,
            "language": language,
            "sample_rate": str(sample_rate),
        }
        headers: Dict[str, str] = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(
            self.base_url,
            data=data,
            files=files,
            headers=headers,
            timeout=self.timeout_sec,
        )
        response.raise_for_status()
        payload = response.json()

        text = self._extract_text(payload)
        latency_ms = (time.monotonic() - started) * 1000.0
        return ASRResult(
            text=text,
            provider=self.provider_name,
            latency_ms=latency_ms,
            raw=payload,
        )

    def _extract_text(self, payload: Dict[str, Any]) -> str:
        if self.response_text_field and self.response_text_field in payload:
            value = payload[self.response_text_field]
            if isinstance(value, str):
                return value.strip()

        for key in ("text", "transcript", "result"):
            value = payload.get(key)
            if isinstance(value, str):
                return value.strip()

        data = payload.get("data")
        if isinstance(data, dict):
            for key in (self.response_text_field, "text", "transcript", "result"):
                value = data.get(key)
                if isinstance(value, str):
                    return value.strip()

        raise RuntimeError(
            f"Unable to extract transcript from Qwen response keys={list(payload.keys())}"
        )


class WhisperLocalProvider(ASRProvider):
    def __init__(
        self,
        model_name: str,
        timeout_sec: float,
        language: str,
        device: str,
        compute_type: str,
        cpu_threads: int,
    ) -> None:
        super().__init__(provider_name="whisper_local", timeout_sec=timeout_sec)
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.cpu_threads = max(1, cpu_threads)
        self._backend = None
        self._model = None
        self._lock = threading.Lock()

    def _ensure_model_unlocked(self) -> None:
        """Load model if not yet loaded. Caller must hold self._lock."""
        if self._model is not None:
            return

        try:
            from faster_whisper import WhisperModel

            self._backend = "faster_whisper"
            self._model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=self.cpu_threads,
            )
            return
        except Exception:
            pass

        try:
            import whisper

            self._backend = "openai_whisper"
            self._model = whisper.load_model(self.model_name)
            return
        except Exception as exc:
            raise RuntimeError(
                "Whisper local backend not available. Install faster-whisper or openai-whisper."
            ) from exc

    def transcribe(
        self, audio_bytes: bytes, sample_rate: int, language: str
    ) -> ASRResult:
        with self._lock:
            self._ensure_model_unlocked()
            started = time.monotonic()

            if self._backend == "faster_whisper":
                return self._transcribe_faster_whisper(
                    audio_bytes, sample_rate, language, started
                )
            return self._transcribe_openai_whisper(
                audio_bytes, sample_rate, language, started
            )

    def _transcribe_faster_whisper(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str,
        started: float,
    ) -> ASRResult:
        with io.BytesIO(audio_bytes) as audio_io:
            segments, info = self._model.transcribe(
                audio_io,
                language=language or self.language,
                vad_filter=False,
                beam_size=1,
            )
            text = "".join(segment.text for segment in segments).strip()

        latency_ms = (time.monotonic() - started) * 1000.0
        return ASRResult(
            text=text,
            provider=self.provider_name,
            latency_ms=latency_ms,
            raw={
                "backend": self._backend,
                "language": getattr(info, "language", language),
            },
            degraded=True,
        )

    def _transcribe_openai_whisper(
        self,
        audio_bytes: bytes,
        sample_rate: int,
        language: str,
        started: float,
    ) -> ASRResult:
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as temp_file:
            temp_file.write(audio_bytes)
            temp_file.flush()
            result = self._model.transcribe(
                temp_file.name, language=language or self.language
            )

        text = str(result.get("text", "")).strip()
        latency_ms = (time.monotonic() - started) * 1000.0
        return ASRResult(
            text=text,
            provider=self.provider_name,
            latency_ms=latency_ms,
            raw={"backend": self._backend},
            degraded=True,
        )


@dataclass
class RecorderState:
    is_recording: bool = False
    session_id: Optional[str] = None
    start_monotonic: float = 0.0
    chunks: List[np.ndarray] = field(default_factory=list)


class SttIntentNode(Node):
    # Known Whisper Small hallucination patterns (substrings, checked after normalization)
    HALLUCINATION_BLACKLIST = (
        "字幕by",
        "字幕制作",
        "字幕製作",
        "zither",
        "索兰娅",
        "索蘭婭",
    )

    def __init__(self) -> None:
        super().__init__("stt_intent_node")

        self._declare_parameters()
        self._load_parameters()

        self.classifier = IntentClassifier()
        self.providers = self._build_providers()
        self.provider_order = self._build_provider_order()

        self.intent_event_pub = self.create_publisher(
            String, self.intent_event_topic, 10
        )
        self.intent_pub = self.create_publisher(String, self.intent_topic, 10)
        self.asr_pub = self.create_publisher(String, self.asr_result_topic, 10)
        self.state_pub = self.create_publisher(String, self.state_topic, 10)

        self.vad_sub = self.create_subscription(
            String, self.vad_event_topic, self._on_vad_event, 10
        )
        self.text_sub = self.create_subscription(
            String, self.text_input_topic, self._on_text_input, 10
        )

        # Echo gate: mute mic while TTS is playing on Go2 speaker
        self._tts_playing = False
        self._tts_gate_open_time = 0.0  # monotonic time when gate lifts (after cooldown)
        from rclpy.qos import QoSProfile, DurabilityPolicy
        tts_playing_qos = QoSProfile(depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.tts_playing_sub = self.create_subscription(
            Bool, "/state/tts_playing", self._on_tts_playing, tts_playing_qos
        )

        self._sounddevice = None
        self._stream = None
        self._audio_queue: "queue.Queue[np.ndarray]" = queue.Queue(maxsize=512)
        self._record_lock = threading.Lock()
        self._pre_roll_frames: Deque[np.ndarray] = deque(
            maxlen=self.pre_roll_frame_count
        )
        self._recorder_state = RecorderState()
        self._active_capture_rate = self.capture_sample_rate or self.sample_rate
        self._processing_lock = threading.Lock()
        self._last_error = ""
        self._last_provider = ""
        self._last_intent = ""
        self._last_transcript = ""
        self._state = "INITIALIZING"
        self._speech_end_deadline = 0.0
        self._energy_vad_speaking = False
        self._energy_vad_silence_start = 0.0
        self._energy_vad_speech_start = 0.0

        self._load_sounddevice()
        self._start_audio_stream()

        self.process_timer = self.create_timer(0.02, self._drain_audio_queue)
        self.timeout_timer = self.create_timer(0.1, self._check_recording_timeout)
        self.state_timer = self.create_timer(
            1.0 / self.state_publish_hz, self._publish_state
        )

        self._state = "LISTENING"
        self.get_logger().info(
            "stt_intent_node started "
            f"(providers={','.join(self.provider_order)}, sample_rate={self.sample_rate}, "
            f"energy_vad={self.energy_vad_enabled}, "
            f"echo_gate_cooldown={self.tts_echo_cooldown_ms}ms, "
            f"text_fallback_topic={self.text_input_topic})"
        )

        # ASR warmup: preload Whisper model + trigger CUDA JIT in background.
        # Until warmup completes, first real ASR may block on transcribe() lock.
        # State topic publishes warmup_done=false/true for observability.
        self._warmup_done = False
        threading.Thread(target=self._do_warmup, daemon=True).start()

    def _do_warmup(self) -> None:
        """ASR warmup in background thread: preload Whisper model + trigger CUDA JIT.

        Runs in daemon thread to avoid blocking ROS2 executor callbacks.
        Uses self._lock in transcribe() to serialize with first real ASR call.
        """
        whisper = self.providers.get("whisper_local")
        if whisper is None:
            self._warmup_done = True
            return

        self.get_logger().info("ASR warmup started")
        try:
            t0 = time.monotonic()
            silent_pcm = np.zeros(self.sample_rate, dtype=np.float32)
            wav_bytes = self._encode_wav(silent_pcm)
            whisper.transcribe(wav_bytes, self.sample_rate, self.language)
            elapsed = time.monotonic() - t0
            self.get_logger().info(
                f"ASR warmup completed in {elapsed:.1f}s (warmup_done=true)"
            )
        except Exception as e:
            self.get_logger().warn(f"ASR warmup failed (non-fatal): {e}")
        self._warmup_done = True

    def _declare_parameters(self) -> None:
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("capture_sample_rate", 16000)
        self.declare_parameter("frame_samples", 512)
        self.declare_parameter("channels", 2)  # HyperX SoloCast is stereo-only; downmix in callback
        self.declare_parameter("input_device", -1)
        self.declare_parameter("alsa_device", "")
        self.declare_parameter("max_record_seconds", 6.0)
        self.declare_parameter("speech_end_grace_ms", 250)
        self.declare_parameter("pre_roll_ms", 300)
        self.declare_parameter("state_publish_hz", 5.0)
        self.declare_parameter("language", "zh")
        self.declare_parameter("provider_order", ["qwen_cloud", "whisper_local"])

        self.declare_parameter("vad_event_topic", "/event/speech_activity")
        self.declare_parameter("state_topic", "/state/interaction/speech")
        self.declare_parameter("intent_event_topic", "/event/speech_intent_recognized")
        self.declare_parameter("intent_topic", "/intent")
        self.declare_parameter("asr_result_topic", "/asr_result")
        self.declare_parameter("text_input_topic", "/speech/text_input")

        self.declare_parameter("qwen_asr.base_url", "")
        self.declare_parameter("qwen_asr.api_key", "")
        self.declare_parameter("qwen_asr.timeout_sec", 2.0)
        self.declare_parameter("qwen_asr.model_name", "qwen-asr")
        self.declare_parameter("qwen_asr.response_text_field", "text")

        self.declare_parameter("whisper_local.model_name", "tiny")
        self.declare_parameter("whisper_local.timeout_sec", 4.0)
        self.declare_parameter("whisper_local.device", "cpu")
        self.declare_parameter("whisper_local.compute_type", "int8")
        self.declare_parameter("whisper_local.cpu_threads", 4)

        self.declare_parameter("tts_echo_cooldown_ms", 1000)

        self.declare_parameter("energy_vad.enabled", True)
        self.declare_parameter("energy_vad.start_threshold", 0.015)
        self.declare_parameter("energy_vad.stop_threshold", 0.01)
        self.declare_parameter("energy_vad.silence_duration_ms", 800)
        self.declare_parameter("energy_vad.min_speech_ms", 300)

    def _load_parameters(self) -> None:
        self.sample_rate = int(self.get_parameter("sample_rate").value)
        self.capture_sample_rate = int(self.get_parameter("capture_sample_rate").value)
        self.frame_samples = int(self.get_parameter("frame_samples").value)
        self.channels = int(self.get_parameter("channels").value)
        self.input_device = int(self.get_parameter("input_device").value)
        self.alsa_device = str(self.get_parameter("alsa_device").value)
        self.max_record_seconds = float(self.get_parameter("max_record_seconds").value)
        self.speech_end_grace_ms = int(self.get_parameter("speech_end_grace_ms").value)
        self.pre_roll_ms = int(self.get_parameter("pre_roll_ms").value)
        self.state_publish_hz = float(self.get_parameter("state_publish_hz").value)
        self.language = str(self.get_parameter("language").value)
        self.provider_order_param = list(self.get_parameter("provider_order").value)

        self.vad_event_topic = str(self.get_parameter("vad_event_topic").value)
        self.state_topic = str(self.get_parameter("state_topic").value)
        self.intent_event_topic = str(self.get_parameter("intent_event_topic").value)
        self.intent_topic = str(self.get_parameter("intent_topic").value)
        self.asr_result_topic = str(self.get_parameter("asr_result_topic").value)
        self.text_input_topic = str(self.get_parameter("text_input_topic").value)

        self.qwen_base_url = str(self.get_parameter("qwen_asr.base_url").value)
        self.qwen_api_key = str(self.get_parameter("qwen_asr.api_key").value)
        self.qwen_timeout_sec = float(self.get_parameter("qwen_asr.timeout_sec").value)
        self.qwen_model_name = str(self.get_parameter("qwen_asr.model_name").value)
        self.qwen_response_text_field = str(
            self.get_parameter("qwen_asr.response_text_field").value
        )

        self.whisper_model_name = str(
            self.get_parameter("whisper_local.model_name").value
        )
        self.whisper_timeout_sec = float(
            self.get_parameter("whisper_local.timeout_sec").value
        )
        self.whisper_device = str(self.get_parameter("whisper_local.device").value)
        self.whisper_compute_type = str(
            self.get_parameter("whisper_local.compute_type").value
        )
        self.whisper_cpu_threads = int(
            self.get_parameter("whisper_local.cpu_threads").value
        )

        self.tts_echo_cooldown_ms = int(
            self.get_parameter("tts_echo_cooldown_ms").value
        )

        self.energy_vad_enabled = bool(self.get_parameter("energy_vad.enabled").value)
        self.energy_vad_start_threshold = float(
            self.get_parameter("energy_vad.start_threshold").value
        )
        self.energy_vad_stop_threshold = float(
            self.get_parameter("energy_vad.stop_threshold").value
        )
        self.energy_vad_silence_duration_ms = int(
            self.get_parameter("energy_vad.silence_duration_ms").value
        )
        self.energy_vad_min_speech_ms = int(
            self.get_parameter("energy_vad.min_speech_ms").value
        )

        pre_roll_samples = int(self.sample_rate * (self.pre_roll_ms / 1000.0))
        self.pre_roll_frame_count = max(
            1, pre_roll_samples // max(1, self.frame_samples)
        )

    def _build_providers(self) -> Dict[str, ASRProvider]:
        providers: Dict[str, ASRProvider] = {}
        providers["qwen_cloud"] = QwenASRProvider(
            base_url=self.qwen_base_url,
            api_key=self.qwen_api_key,
            timeout_sec=self.qwen_timeout_sec,
            model_name=self.qwen_model_name,
            response_text_field=self.qwen_response_text_field,
        )
        providers["whisper_local"] = WhisperLocalProvider(
            model_name=self.whisper_model_name,
            timeout_sec=self.whisper_timeout_sec,
            language=self.language,
            device=self.whisper_device,
            compute_type=self.whisper_compute_type,
            cpu_threads=self.whisper_cpu_threads,
        )
        return providers

    def _build_provider_order(self) -> List[str]:
        order = [
            str(item).strip() for item in self.provider_order_param if str(item).strip()
        ]
        valid_order = [name for name in order if name in self.providers]
        if not valid_order:
            valid_order = ["qwen_cloud", "whisper_local"]
        return valid_order

    def _on_tts_playing(self, msg: Bool) -> None:
        """Handle TTS playback state changes for echo gate."""
        if msg.data:
            self._tts_playing = True
            self._tts_gate_open_time = 0.0
            self.get_logger().debug("Echo gate: CLOSED (TTS playing)")
        else:
            # TTS stopped — start cooldown before reopening the gate
            self._tts_playing = False
            self._tts_gate_open_time = (
                time.monotonic() + self.tts_echo_cooldown_ms / 1000.0
            )
            self.get_logger().debug(
                f"Echo gate: cooldown {self.tts_echo_cooldown_ms}ms"
            )

    def _is_echo_gated(self) -> bool:
        """Return True if audio should be discarded (TTS playing or cooldown)."""
        if self._tts_playing:
            return True
        if self._tts_gate_open_time > 0.0:
            if time.monotonic() < self._tts_gate_open_time:
                return True
            # Cooldown elapsed — gate fully open
            self._tts_gate_open_time = 0.0
            self.get_logger().debug("Echo gate: OPEN (cooldown elapsed)")
        return False

    def _load_sounddevice(self) -> None:
        try:
            import importlib

            self._sounddevice = importlib.import_module("sounddevice")
        except Exception as exc:
            raise RuntimeError(
                "Missing runtime dependency for stt_intent_node: sounddevice"
            ) from exc

    def _start_audio_stream(self) -> None:
        if self._sounddevice is None:
            raise RuntimeError("sounddevice module not loaded")

        desired_capture_rate = self.capture_sample_rate
        if desired_capture_rate <= 0:
            if self.input_device >= 0:
                dev_info = self._sounddevice.query_devices(self.input_device)
            else:
                dev_info = self._sounddevice.query_devices(kind="input")
            desired_capture_rate = int(dev_info["default_samplerate"])
        self._active_capture_rate = desired_capture_rate

        if self.alsa_device:
            import os

            os.environ["ALSA_DEFAULT"] = self.alsa_device
            self.get_logger().info(f"Using ALSA device for STT: {self.alsa_device}")

        selected_device_desc = "default"
        stream_kwargs = {
            "samplerate": self._active_capture_rate,
            "channels": self.channels,
            "dtype": "float32",
            "blocksize": self.frame_samples,
            "callback": self._audio_callback,
        }
        if self.input_device >= 0 and not self.alsa_device:
            stream_kwargs["device"] = self.input_device
            try:
                dev_info = self._sounddevice.query_devices(self.input_device)
                selected_device_desc = (
                    f"{self.input_device} ({dev_info.get('name', 'unknown')})"
                )
            except Exception:
                selected_device_desc = f"{self.input_device}"
        elif self.alsa_device:
            selected_device_desc = f"alsa:{self.alsa_device}"
        else:
            default_device = self._sounddevice.query_devices(kind="input")
            selected_device_desc = str(default_device.get("name", "default"))

        self.get_logger().info(f"Opening STT audio stream: {selected_device_desc}")
        self._stream = self._sounddevice.InputStream(**stream_kwargs)
        self._stream.start()

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info
        if status:
            self._last_error = str(status)

        # Echo gate: discard audio while TTS is playing (or during cooldown)
        if self._is_echo_gated():
            return

        audio = np.asarray(indata, dtype=np.float32)
        # Stereo→mono downmix: take left channel (more reliable than PortAudio auto-downmix)
        if audio.ndim == 2 and audio.shape[1] > 1:
            mono = audio[:, 0].copy()
        else:
            mono = audio.reshape(-1)
        try:
            self._audio_queue.put_nowait(mono)
        except queue.Full:
            self._last_error = "audio queue full"

    def _resample_if_needed(self, frame: np.ndarray) -> np.ndarray:
        if self._active_capture_rate == self.sample_rate:
            return frame.astype(np.float32)
        if frame.size == 0:
            return frame.astype(np.float32)

        in_len = frame.shape[0]
        out_len = max(
            1, int(round(in_len * self.sample_rate / self._active_capture_rate))
        )
        x_old = np.linspace(0.0, 1.0, num=in_len, endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=out_len, endpoint=False)
        return np.interp(x_new, x_old, frame).astype(np.float32)

    def _drain_audio_queue(self) -> None:
        processed = 0
        while processed < 50 and not self._audio_queue.empty():
            frame = self._audio_queue.get_nowait()
            processed += 1
            resampled = self._resample_if_needed(frame)
            if resampled.size == 0:
                continue

            self._pre_roll_frames.append(resampled)
            with self._record_lock:
                if self._recorder_state.is_recording:
                    self._recorder_state.chunks.append(resampled)

            if self.energy_vad_enabled:
                self._energy_vad_process(resampled)

    def _energy_vad_process(self, frame: np.ndarray) -> None:
        rms = float(np.sqrt(np.mean(frame**2)))
        now = time.monotonic()

        if not self._energy_vad_speaking:
            if rms >= self.energy_vad_start_threshold:
                with self._record_lock:
                    if self._recorder_state.is_recording:
                        return
                self._energy_vad_speaking = True
                self._energy_vad_silence_start = 0.0
                self._energy_vad_speech_start = now
                session_id = self._new_session_id(prefix="ev")
                self._handle_speech_start(session_id)
                self.get_logger().info(f"Energy VAD: speech start (rms={rms:.4f})")
        else:
            if rms < self.energy_vad_stop_threshold:
                if self._energy_vad_silence_start == 0.0:
                    self._energy_vad_silence_start = now
                elif (
                    now - self._energy_vad_silence_start
                ) * 1000.0 >= self.energy_vad_silence_duration_ms:
                    speech_dur = now - self._energy_vad_speech_start
                    if speech_dur * 1000.0 >= self.energy_vad_min_speech_ms:
                        self._handle_speech_end()
                        self.get_logger().info(
                            f"Energy VAD: speech end (duration={speech_dur:.2f}s)"
                        )
                    else:
                        with self._record_lock:
                            self._recorder_state = RecorderState()
                            self._speech_end_deadline = 0.0
                        self.get_logger().debug("Energy VAD: too short, discarded")
                    self._energy_vad_speaking = False
                    self._energy_vad_silence_start = 0.0
            else:
                self._energy_vad_silence_start = 0.0

    def _check_recording_timeout(self) -> None:
        with self._record_lock:
            if not self._recorder_state.is_recording:
                return

            now = time.monotonic()
            started = self._recorder_state.start_monotonic
            if now - started >= self.max_record_seconds:
                session_id = self._recorder_state.session_id
                self.get_logger().warn(
                    f"Speech capture timeout for session={session_id}"
                )
                self._finalize_recording_locked(reason="capture_timeout")
                return

            if self._speech_end_deadline > 0.0 and now >= self._speech_end_deadline:
                self._finalize_recording_locked(reason="speech_end")

    def _on_vad_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn("Ignoring malformed VAD event payload")
            return

        event_name = payload.get("event", "")
        session_id = payload.get("session_id") or self._new_session_id()

        if event_name == "speech_start":
            self._handle_speech_start(session_id)
        elif event_name == "speech_end":
            self._handle_speech_end()

    def _handle_speech_start(self, session_id: str) -> None:
        with self._record_lock:
            if self._recorder_state.is_recording:
                self.get_logger().warn(
                    "Received speech_start while recording; resetting session"
                )
                self._recorder_state = RecorderState()

            initial_chunks = list(self._pre_roll_frames)
            self._recorder_state = RecorderState(
                is_recording=True,
                session_id=session_id,
                start_monotonic=time.monotonic(),
                chunks=initial_chunks,
            )
            self._speech_end_deadline = 0.0
            self._state = "RECORDING"

        self.get_logger().info(f"Speech start detected, recording session={session_id}")

    def _handle_speech_end(self) -> None:
        with self._record_lock:
            if not self._recorder_state.is_recording:
                return
            self._speech_end_deadline = time.monotonic() + (
                self.speech_end_grace_ms / 1000.0
            )

    def _finalize_recording_locked(self, reason: str) -> None:
        state = self._recorder_state
        self._recorder_state = RecorderState()
        self._speech_end_deadline = 0.0

        if not state.chunks:
            self._state = "LISTENING"
            self.get_logger().warn(f"Recording finished with no audio, reason={reason}")
            return

        audio = np.concatenate(state.chunks)
        audio_bytes = self._encode_wav(audio)
        session_id = state.session_id or self._new_session_id()
        self._state = "TRANSCRIBING"
        threading.Thread(
            target=self._process_audio_session,
            args=(session_id, audio_bytes, reason),
            daemon=True,
        ).start()

    def _encode_wav(self, audio: np.ndarray) -> bytes:
        clipped = np.clip(audio, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        wav_io = io.BytesIO()
        with wave.open(wav_io, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm.tobytes())
        return wav_io.getvalue()

    def _process_audio_session(
        self, session_id: str, audio_bytes: bytes, reason: str
    ) -> None:
        if not self._processing_lock.acquire(blocking=False):
            self.get_logger().warn(
                "ASR processing busy; dropping overlapped speech segment"
            )
            self._last_error = "processing busy"
            self._state = "LISTENING"
            return

        try:
            transcript_result, errors = self._transcribe_with_fallback(audio_bytes)
            if transcript_result is None:
                self._last_error = (
                    "; ".join(errors) if errors else "all providers failed"
                )
                self.get_logger().error(
                    f"ASR failed for session={session_id}: {self._last_error}"
                )
                self._publish_asr_result(session_id, "", "none", 0.0, True, reason)
                self._state = "DEGRADED"
                return

            transcript = transcript_result.text.strip()
            self._last_provider = transcript_result.provider
            self._last_transcript = transcript
            self._publish_asr_result(
                session_id,
                transcript,
                transcript_result.provider,
                transcript_result.latency_ms,
                transcript_result.degraded,
                reason,
            )

            # Whisper hallucination filter — publish as hallucination intent so
            # the observer records a miss instead of the round vanishing.
            normalized_for_check = IntentClassifier._normalize(transcript)
            is_hallucination = any(
                pattern in normalized_for_check
                for pattern in self.HALLUCINATION_BLACKLIST
            )
            if is_hallucination:
                self.get_logger().warn(
                    f"Whisper hallucination detected: {transcript!r}"
                )
                intent_match = IntentMatch(
                    intent="hallucination", confidence=0.0, matched_keywords=[]
                )
                self._publish_intent(
                    session_id=session_id,
                    transcript=transcript,
                    source="audio",
                    provider=transcript_result.provider,
                    latency_ms=transcript_result.latency_ms,
                    degraded=True,
                    match=intent_match,
                )
                self._state = "LISTENING"
                return

            intent_match = self.classifier.classify(transcript)
            self._publish_intent(
                session_id=session_id,
                transcript=transcript,
                source="audio",
                provider=transcript_result.provider,
                latency_ms=transcript_result.latency_ms,
                degraded=transcript_result.degraded,
                match=intent_match,
            )
            self._state = "LISTENING"
        except Exception as exc:
            self._last_error = str(exc)
            self._state = "ERROR"
            self.get_logger().error(
                f"Audio processing failed for session={session_id}: {exc}"
            )
        finally:
            self._processing_lock.release()

    def _transcribe_with_fallback(
        self, audio_bytes: bytes
    ) -> Tuple[Optional[ASRResult], List[str]]:
        errors: List[str] = []
        for provider_name in self.provider_order:
            provider = self.providers.get(provider_name)
            if provider is None:
                continue
            try:
                result = provider.transcribe(
                    audio_bytes, self.sample_rate, self.language
                )
                if result.text.strip():
                    if provider_name != self.provider_order[0]:
                        result.degraded = True
                    return result, errors
                errors.append(f"{provider_name}: empty transcript")
            except Exception as exc:
                errors.append(f"{provider_name}: {exc}")
                self.get_logger().warn(f"ASR provider {provider_name} failed: {exc}")
        return None, errors

    def _on_text_input(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return

        session_id = self._new_session_id(prefix="txt")
        self._last_provider = "text_fallback"
        self._last_transcript = text
        self._publish_asr_result(session_id, text, "text_fallback", 0.0, False, "text")
        intent_match = self.classifier.classify(text)
        self._publish_intent(
            session_id=session_id,
            transcript=text,
            source="text",
            provider="text_fallback",
            latency_ms=0.0,
            degraded=False,
            match=intent_match,
        )

    def _publish_asr_result(
        self,
        session_id: str,
        transcript: str,
        provider: str,
        latency_ms: float,
        degraded: bool,
        reason: str,
    ) -> None:
        payload = {
            "session_id": session_id,
            "text": transcript,
            "provider": provider,
            "latency_ms": round(latency_ms, 2),
            "degraded": degraded,
            "reason": reason,
            "timestamp": self._timestamp(),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        self.asr_pub.publish(msg)

    def _publish_intent(
        self,
        session_id: str,
        transcript: str,
        source: str,
        provider: str,
        latency_ms: float,
        degraded: bool,
        match: IntentMatch,
    ) -> None:
        intent_label = match.intent if match.intent in SUPPORTED_INTENTS or match.intent == "hallucination" else "unknown"
        self._last_intent = intent_label

        intent_msg = String()
        intent_msg.data = intent_label
        self.intent_pub.publish(intent_msg)

        payload = {
            "event": "speech_intent_recognized",
            "session_id": session_id,
            "intent": intent_label,
            "confidence": round(match.confidence, 3),
            "matched_keywords": match.matched_keywords,
            "text": transcript,
            "source": source,
            "provider": provider,
            "latency_ms": round(latency_ms, 2),
            "degraded": degraded,
            "timestamp": self._timestamp(),
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=True)
        self.intent_event_pub.publish(msg)
        self.get_logger().info(
            f"Intent published session={session_id} intent={intent_label} "
            f"provider={provider} source={source} degraded={degraded} text={transcript!r}"
        )

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": self._state,
                "last_intent": self._last_intent,
                "last_provider": self._last_provider,
                "last_transcript": self._last_transcript,
                "last_error": self._last_error,
                "recording": self._recorder_state.is_recording,
                "warmup_done": self._warmup_done,
                "timestamp": self._timestamp(),
            },
            ensure_ascii=True,
        )
        self.state_pub.publish(msg)

    def _new_session_id(self, prefix: str = "sp") -> str:
        now = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"{prefix}-{now}-{token_hex(2)}"

    @staticmethod
    def _timestamp() -> str:
        return datetime.utcnow().isoformat() + "Z"

    def destroy_node(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                self.get_logger().warn(
                    f"Failed to close STT audio stream cleanly: {exc}"
                )
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = SttIntentNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
