#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

import base64
import importlib
import json
from datetime import datetime
from typing import Any, Optional

import numpy as np
import rclpy
from rclpy.node import Node
from std_msgs.msg import String


class AsrNode(Node):
    def __init__(self) -> None:
        super().__init__("asr_node")

        self._declare_parameters()

        self.segment_topic = str(
            self.get_parameter("segment_topic").get_parameter_value().string_value
        )
        self.asr_result_topic = str(
            self.get_parameter("asr_result_topic").get_parameter_value().string_value
        )
        self.asr_status_topic = str(
            self.get_parameter("asr_status_topic").get_parameter_value().string_value
        )
        self.model_name = str(
            self.get_parameter("model_name").get_parameter_value().string_value
        )
        self.language = str(
            self.get_parameter("language").get_parameter_value().string_value
        )
        self.compute_type = str(
            self.get_parameter("compute_type").get_parameter_value().string_value
        )
        self.device = str(
            self.get_parameter("device").get_parameter_value().string_value
        )

        self.result_pub = self.create_publisher(String, self.asr_result_topic, 10)
        self.status_pub = self.create_publisher(String, self.asr_status_topic, 10)
        self.segment_sub = self.create_subscription(
            String,
            self.segment_topic,
            self._on_segment,
            10,
        )

        self._backend = "none"
        self._faster_whisper_model: Optional[Any] = None
        self._whisper_module: Optional[Any] = None
        self._whisper_model: Optional[Any] = None

        self._load_backend()
        self.get_logger().info(
            f"asr_node ready (backend={self._backend}, model={self.model_name}, language={self.language})"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("segment_topic", "/audio/speech_segment")
        self.declare_parameter("asr_result_topic", "/asr_result")
        self.declare_parameter("asr_status_topic", "/state/interaction/asr")
        self.declare_parameter("model_name", "tiny")
        self.declare_parameter("language", "zh")
        self.declare_parameter("compute_type", "int8")
        self.declare_parameter("device", "cpu")

    def _load_backend(self) -> None:
        try:
            fw_module = importlib.import_module("faster_whisper")
            whisper_model_cls = getattr(fw_module, "WhisperModel")
            self._faster_whisper_model = whisper_model_cls(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._backend = "faster_whisper"
            return
        except Exception as exc:
            self.get_logger().warn(
                f"faster_whisper unavailable, fallback to openai-whisper: {exc}"
            )

        try:
            self._whisper_module = importlib.import_module("whisper")
            self._whisper_model = self._whisper_module.load_model(self.model_name)
            self._backend = "openai_whisper"
            return
        except Exception as exc:
            self.get_logger().error(f"No ASR backend available: {exc}")

    def _publish_status(
        self, status: str, session_id: Optional[str], detail: str = ""
    ) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "status": status,
                "session_id": session_id,
                "detail": detail,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "node": "asr_node",
            },
            ensure_ascii=True,
        )
        self.status_pub.publish(msg)

    def _on_segment(self, msg: String) -> None:
        payload = json.loads(msg.data)
        session_id = payload.get("session_id")
        sample_rate = int(payload.get("sample_rate", 16000))
        encoded = payload.get("audio_base64", "")

        if self._backend == "none":
            self._publish_status("error", session_id, "asr backend not available")
            return
        if not encoded:
            self._publish_status("error", session_id, "empty audio payload")
            return

        self._publish_status("processing", session_id)
        audio_bytes = base64.b64decode(encoded)
        pcm_i16 = np.frombuffer(audio_bytes, dtype=np.int16)
        audio_f32 = pcm_i16.astype(np.float32) / 32768.0

        text = self._transcribe(audio_f32, sample_rate)
        result = String()
        result.data = json.dumps(
            {
                "session_id": session_id,
                "text": text,
                "language": self.language,
                "sample_rate": sample_rate,
                "duration_sec": float(audio_f32.shape[0]) / float(sample_rate),
                "backend": self._backend,
                "timestamp": datetime.utcnow().isoformat() + "Z",
            },
            ensure_ascii=True,
        )
        self.result_pub.publish(result)
        self._publish_status("done", session_id)

    def _transcribe(self, audio_f32: np.ndarray, sample_rate: int) -> str:
        if self._backend == "faster_whisper":
            model = self._faster_whisper_model
            if model is None:
                raise RuntimeError(
                    "faster_whisper backend selected but model is not loaded"
                )

            segments, _ = model.transcribe(
                audio_f32,
                language=self.language,
                vad_filter=False,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()

        if self._backend == "openai_whisper":
            whisper_module = self._whisper_module
            whisper_model = self._whisper_model
            if whisper_module is None or whisper_model is None:
                raise RuntimeError(
                    "openai_whisper backend selected but model is not loaded"
                )

            if sample_rate != 16000:
                audio_f32 = whisper_module.audio.resample(audio_f32, sample_rate, 16000)

            result = whisper_model.transcribe(
                audio_f32,
                language=self.language,
                fp16=False,
            )
            return str(result.get("text", "")).strip()

        return ""


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = AsrNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
