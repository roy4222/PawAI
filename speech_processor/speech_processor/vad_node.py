#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

import json
import importlib
import queue
import base64
from datetime import datetime
from secrets import token_hex
from typing import Any, Optional

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class VadNode(Node):
    def __init__(self) -> None:
        super().__init__("vad_node")

        self._declare_parameters()

        self.sample_rate = int(
            self.get_parameter("sample_rate").get_parameter_value().integer_value
        )
        self.capture_sample_rate = int(
            self.get_parameter("capture_sample_rate")
            .get_parameter_value()
            .integer_value
        )
        self.frame_samples = int(
            self.get_parameter("frame_samples").get_parameter_value().integer_value
        )
        self.channels = int(
            self.get_parameter("channels").get_parameter_value().integer_value
        )
        self.device = int(
            self.get_parameter("input_device").get_parameter_value().integer_value
        )
        self.alsa_device = str(
            self.get_parameter("alsa_device").get_parameter_value().string_value
        )
        self.threshold = float(
            self.get_parameter("vad_threshold").get_parameter_value().double_value
        )
        self.min_silence_ms = int(
            self.get_parameter("min_silence_ms").get_parameter_value().integer_value
        )
        self.speech_pad_ms = int(
            self.get_parameter("speech_pad_ms").get_parameter_value().integer_value
        )
        self.state_publish_hz = float(
            self.get_parameter("state_publish_hz").get_parameter_value().double_value
        )

        self.state_topic = str(
            self.get_parameter("state_topic").get_parameter_value().string_value
        )
        self.event_topic = str(
            self.get_parameter("event_topic").get_parameter_value().string_value
        )
        self.segment_topic = str(
            self.get_parameter("segment_topic").get_parameter_value().string_value
        )

        self.state_pub = self.create_publisher(String, self.state_topic, 10)
        self.event_pub = self.create_publisher(String, self.event_topic, 10)
        self.segment_pub = self.create_publisher(String, self.segment_topic, 10)

        self.current_state = "INITIALIZING"
        self.active_session_id: Optional[str] = None
        self.frames_dropped = 0
        self.last_error: Optional[str] = None

        self._audio_queue: "queue.Queue" = queue.Queue(maxsize=256)
        self._vad_buffer = np.array([], dtype=np.float32)
        self._active_segment_chunks = []
        self._stream: Optional[Any] = None
        self._sd: Optional[Any] = None
        self._torch: Optional[Any] = None
        self._active_capture_rate = self.sample_rate

        self._load_dependencies()
        self._start_audio_stream()

        self.current_state = "LISTENING"
        self.process_timer = self.create_timer(0.02, self._process_audio_queue)
        self.state_timer = self.create_timer(
            1.0 / self.state_publish_hz, self._publish_state
        )

        self.get_logger().info(
            f"vad_node started (sr={self.sample_rate}, frame={self.frame_samples}, "
            f"threshold={self.threshold})"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("sample_rate", 16000)
        self.declare_parameter("capture_sample_rate", 0)
        self.declare_parameter("frame_samples", 512)
        self.declare_parameter("channels", 1)
        self.declare_parameter("input_device", -1)
        self.declare_parameter("alsa_device", "")  # e.g., "plughw:0,0" for resampling
        self.declare_parameter("vad_threshold", 0.5)
        self.declare_parameter("min_silence_ms", 400)
        self.declare_parameter("speech_pad_ms", 120)
        self.declare_parameter("state_publish_hz", 5.0)
        self.declare_parameter("state_topic", "/state/interaction/speech")
        self.declare_parameter("event_topic", "/event/speech_activity")
        self.declare_parameter("segment_topic", "/audio/speech_segment")

    def _load_dependencies(self) -> None:
        try:
            self._sd = importlib.import_module("sounddevice")
            self._torch = importlib.import_module("torch")
            silero_vad_module = importlib.import_module("silero_vad")
            load_silero_vad = getattr(silero_vad_module, "load_silero_vad")
            vad_iterator_cls = getattr(silero_vad_module, "VADIterator")
        except Exception as exc:
            raise RuntimeError(
                "Missing runtime dependency for vad_node (sounddevice/torch/silero-vad). "
                f"Import error: {exc}"
            ) from exc

        self.vad_model = load_silero_vad()
        self.vad_iterator = vad_iterator_cls(
            self.vad_model,
            threshold=self.threshold,
            sampling_rate=self.sample_rate,
            min_silence_duration_ms=self.min_silence_ms,
            speech_pad_ms=self.speech_pad_ms,
        )

    def _start_audio_stream(self) -> None:
        if self._sd is None:
            raise RuntimeError("sounddevice module not loaded")

        desired_capture_rate = self.capture_sample_rate
        if desired_capture_rate <= 0:
            if self.device >= 0:
                dev_info = self._sd.query_devices(self.device)
            else:
                dev_info = self._sd.query_devices(kind="input")
            desired_capture_rate = int(dev_info["default_samplerate"])
        self._active_capture_rate = desired_capture_rate

        import os

        # Set ALSA device via environment if specified (e.g., plughw:0,0 for resampling)
        if self.alsa_device:
            os.environ["ALSA_DEFAULT"] = self.alsa_device
            self.get_logger().info(f"Using ALSA device: {self.alsa_device}")

        stream_kwargs = {
            "samplerate": self._active_capture_rate,
            "channels": self.channels,
            "dtype": "float32",
            "blocksize": self.frame_samples,
            "callback": self._audio_callback,
        }

        # Use default device (respects ALSA_DEFAULT env var)
        # or use numeric device index if specified and no alsa_device
        if self.device >= 0 and not self.alsa_device:
            stream_kwargs["device"] = self.device

        sd_module = self._sd

        # Query actual device being used
        default_device = sd_module.query_devices(kind="input")
        self.get_logger().info(f"Opening audio stream: {default_device['name']}")

        stream = sd_module.InputStream(**stream_kwargs)
        stream.start()
        self._stream = stream
        self.get_logger().info(
            f"Audio capture started (capture_sr={self._active_capture_rate}, vad_sr={self.sample_rate})"
        )

    def _resample_if_needed(self, frame: np.ndarray) -> np.ndarray:
        if self._active_capture_rate == self.sample_rate:
            return frame
        if frame.size == 0:
            return frame

        in_len = frame.shape[0]
        out_len = max(
            1, int(round(in_len * self.sample_rate / self._active_capture_rate))
        )
        x_old = np.linspace(0.0, 1.0, num=in_len, endpoint=False)
        x_new = np.linspace(0.0, 1.0, num=out_len, endpoint=False)
        out = np.interp(x_new, x_old, frame)
        return out.astype(np.float32)

    def _audio_callback(self, indata, frames, time_info, status) -> None:
        del frames, time_info
        if status:
            self.last_error = str(status)

        mono = np.asarray(indata, dtype=np.float32).reshape(-1)
        try:
            self._audio_queue.put_nowait(mono)
        except queue.Full:
            self.frames_dropped += 1

    def _process_audio_queue(self) -> None:
        if self._torch is None:
            raise RuntimeError("torch module not loaded")

        processed = 0
        while processed < 50 and not self._audio_queue.empty():
            frame = self._audio_queue.get_nowait()
            processed += 1

            resampled = self._resample_if_needed(frame)
            if resampled.size == 0:
                continue

            self._vad_buffer = np.concatenate((self._vad_buffer, resampled))
            while self._vad_buffer.shape[0] >= self.frame_samples:
                vad_frame = self._vad_buffer[: self.frame_samples]
                self._vad_buffer = self._vad_buffer[self.frame_samples :]

                event = self.vad_iterator(
                    self._torch.from_numpy(vad_frame),
                    return_seconds=False,
                )
                if event:
                    if "start" in event:
                        self._on_speech_start()
                    if "end" in event:
                        self._on_speech_end()

                if self.current_state == "SPEAKING":
                    self._active_segment_chunks.append(vad_frame.copy())

    def _new_session_id(self) -> str:
        now = datetime.now().strftime("%Y%m%d-%H%M%S")
        return f"sp-{now}-{token_hex(2)}"

    def _on_speech_start(self) -> None:
        if self.current_state == "SPEAKING":
            return
        self.active_session_id = self._new_session_id()
        self._active_segment_chunks = []
        self.current_state = "SPEAKING"
        self._publish_event("speech_start")

    def _on_speech_end(self) -> None:
        if self.current_state != "SPEAKING":
            return
        self._publish_segment()
        self._publish_event("speech_end")
        self.current_state = "LISTENING"
        self.active_session_id = None
        self._active_segment_chunks = []

    def _publish_segment(self) -> None:
        if not self._active_segment_chunks:
            return

        segment = np.concatenate(self._active_segment_chunks)
        pcm = np.clip(segment, -1.0, 1.0)
        pcm_i16 = (pcm * 32767.0).astype(np.int16)
        encoded = base64.b64encode(pcm_i16.tobytes()).decode("ascii")

        msg = String()
        msg.data = json.dumps(
            {
                "session_id": self.active_session_id,
                "sample_rate": self.sample_rate,
                "format": "pcm_s16le",
                "num_samples": int(pcm_i16.shape[0]),
                "audio_base64": encoded,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=True,
        )
        self.segment_pub.publish(msg)

    def _publish_event(self, event_name: str) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "event": event_name,
                "session_id": self.active_session_id,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "node": "vad_node",
            },
            ensure_ascii=True,
        )
        self.event_pub.publish(msg)
        self.get_logger().info(
            f"VAD event={event_name} session_id={self.active_session_id}"
        )

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": self.current_state,
                "session_id": self.active_session_id,
                "queue_size": self._audio_queue.qsize(),
                "frames_dropped": self.frames_dropped,
                "last_error": self.last_error,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=True,
        )
        self.state_pub.publish(msg)

    def destroy_node(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                self.get_logger().warn(f"Failed to close audio stream cleanly: {exc}")
        super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = VadNode()
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
