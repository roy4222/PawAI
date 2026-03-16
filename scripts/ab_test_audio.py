#!/usr/bin/env python3
"""A/B test: send audio to Go2 with/without 4004, variable chunk interval."""
import rclpy
import json
import time
import base64
import io
import struct
import math
import wave
import sys
from rclpy.node import Node
from std_msgs.msg import String
from go2_interfaces.msg import WebRtcReq


class ABTestNode(Node):
    def __init__(self):
        super().__init__("ab_test_audio")
        self.pub = self.create_publisher(WebRtcReq, "/webrtc_req", 10)

    def send_cmd(self, api_id, parameter=""):
        req = WebRtcReq()
        req.api_id = api_id
        req.parameter = parameter
        req.topic = "rt/api/audiohub/request"
        req.priority = 0
        self.pub.publish(req)
        self.get_logger().info("Sent api_id=%d param_len=%d" % (api_id, len(parameter)))

    def generate_beep_wav(self):
        """440Hz beep, 1s, 16kHz 16bit mono WAV"""
        sr, dur = 16000, 1.0
        samples = int(sr * dur)
        raw = b""
        for i in range(samples):
            val = int(32767 * 0.8 * math.sin(2 * math.pi * 440 * i / sr))
            raw += struct.pack("<h", val)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(raw)
        return buf.getvalue()

    def run_test(self, send_4004, chunk_interval):
        label = "4004=YES" if send_4004 else "4004=NO"
        self.get_logger().info("=== AB TEST: %s interval=%.2fs ===" % (label, chunk_interval))

        wav = self.generate_beep_wav()
        b64 = base64.b64encode(wav).decode("utf-8")
        chunk_size = 16 * 1024
        chunks = [b64[i : i + chunk_size] for i in range(0, len(b64), chunk_size)]
        total = len(chunks)

        self.get_logger().info("WAV=%d bytes, b64=%d chars, chunks=%d" % (len(wav), len(b64), total))

        # Optional: send 4004 volume
        if send_4004:
            self.send_cmd(4004, "80")
            time.sleep(0.05)

        # 4001 start
        self.send_cmd(4001, "")
        time.sleep(0.1)

        # 4003 chunks
        for idx, chunk in enumerate(chunks, 1):
            block = json.dumps({
                "current_block_index": idx,
                "total_block_number": total,
                "block_content": chunk,
            })
            self.send_cmd(4003, block)
            time.sleep(chunk_interval)

        # Wait for playback
        self.get_logger().info("Waiting 2s for playback...")
        time.sleep(2.0)

        # 4002 stop
        self.send_cmd(4002, "")
        self.get_logger().info("=== TEST COMPLETE ===")


def main():
    rclpy.init()
    node = ABTestNode()
    time.sleep(0.5)  # let publisher connect

    # Parse args
    send_4004 = "--with-4004" in sys.argv
    interval = 0.02
    for arg in sys.argv:
        if arg.startswith("--interval="):
            interval = float(arg.split("=")[1])

    node.run_test(send_4004=send_4004, chunk_interval=interval)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
