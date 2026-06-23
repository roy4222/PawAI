#!/usr/bin/env python3
"""
Test Megaphone API with community-aligned payload format.

Differences from our old ab_test_audio.py:
- chunk_size = 4096 (not 16384)
- 4003 payload has current_block_size field
- Proper ENTER(4001) → UPLOAD(4003) → EXIT(4002) sequence

Usage:
    bash scripts/clean_all.sh
    source /opt/ros/humble/setup.zsh && source install/setup.zsh
    python3 scripts/test_megaphone_v2.py
"""

import asyncio
import base64
import io
import json
import logging
import math
import struct
import sys
import wave

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("megaphone_v2")

from go2_robot_sdk.infrastructure.webrtc.go2_connection import Go2Connection


def gen_beep_wav(freq=440, dur=2.0, sr=16000):
    """Generate 440Hz WAV: 16kHz mono 16bit (Go2 standard)."""
    samples = int(sr * dur)
    raw = b""
    for i in range(samples):
        val = int(32767 * 0.8 * math.sin(2 * math.pi * freq * i / sr))
        raw += struct.pack("<h", val)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw)
    return buf.getvalue()


async def main():
    robot_ip = "192.168.123.161"

    logger.info("=" * 50)
    logger.info("Megaphone V2 Test (community payload format)")
    logger.info("=" * 50)

    # Connect
    validated = asyncio.Event()
    def on_validated(rn):
        validated.set()

    conn = Go2Connection(
        robot_ip=robot_ip, robot_num=0, token="",
        on_validated=on_validated, on_message=lambda *a: None,
        enable_audio_track=False,  # No audio track for this test
        decode_lidar=False,
    )
    await conn.connect()
    try:
        await asyncio.wait_for(validated.wait(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("[FAIL] Validation timeout")
        await conn.pc.close()
        return
    logger.info("[OK] Connected and validated")

    # Generate beep
    wav_data = gen_beep_wav(freq=440, dur=2.0, sr=16000)
    b64_data = base64.b64encode(wav_data).decode("utf-8")
    logger.info(f"WAV: {len(wav_data)} bytes, b64: {len(b64_data)} chars")

    # Helper to send audiohub command
    async def send_audiohub(api_id, parameter=""):
        param_str = parameter if isinstance(parameter, str) else json.dumps(parameter)
        msg = json.dumps({
            "type": "req",
            "topic": "rt/api/audiohub/request",
            "data": {
                "header": {"identity": {"id": 0, "api_id": api_id}},
                "parameter": param_str,
            }
        })
        conn.data_channel.send(msg)
        logger.info(f"Sent api_id={api_id} param_len={len(param_str)}")

    # === Megaphone sequence: ENTER → UPLOAD chunks → EXIT ===

    # Step 1: Enter megaphone mode
    logger.info("[1/3] ENTER_MEGAPHONE (4001)")
    await send_audiohub(4001, json.dumps({}))
    await asyncio.sleep(0.3)

    # Step 2: Upload chunks (community format: 4096 byte chunks, with current_block_size)
    CHUNK_SIZE = 4096
    chunks = [b64_data[i:i + CHUNK_SIZE] for i in range(0, len(b64_data), CHUNK_SIZE)]
    total = len(chunks)
    logger.info(f"[2/3] UPLOAD_MEGAPHONE (4003) — {total} chunks of {CHUNK_SIZE}")

    for idx, chunk in enumerate(chunks, 1):
        param = {
            "current_block_size": len(chunk),
            "block_content": chunk,
            "current_block_index": idx,
            "total_block_number": total,
        }
        await send_audiohub(4003, json.dumps(param))
        await asyncio.sleep(0.05)

    logger.info("All chunks sent, waiting 3s for playback...")
    await asyncio.sleep(3.0)

    # Step 3: Exit megaphone mode
    logger.info("[3/3] EXIT_MEGAPHONE (4002)")
    await send_audiohub(4002, json.dumps({}))
    await asyncio.sleep(0.5)

    logger.info("[??] Did you hear the beep?")
    logger.info("=" * 50)

    await conn.pc.close()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
