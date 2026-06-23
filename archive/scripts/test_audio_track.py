#!/usr/bin/env python3
"""
Standalone WebRTC audio track test — bypasses ROS2/driver entirely.

Connects directly to Go2 via Go2Connection, sends a 440Hz beep
through TtsAudioTrack, and reports diagnostics.

Usage:
    bash scripts/clean_all.sh   # MUST kill existing driver first
    source /opt/ros/humble/setup.zsh
    source install/setup.zsh
    python3 scripts/test_audio_track.py [--robot-ip 192.168.123.161]
"""

import asyncio
import io
import math
import os
import struct
import sys
import time
import wave
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("test_audio_track")

# Reuse project code directly
from go2_robot_sdk.infrastructure.webrtc.go2_connection import Go2Connection


def generate_beep_wav(freq=440, duration=2.0, sample_rate=48000, amplitude=1.0):
    """Generate a WAV file with a sine wave beep."""
    samples = int(sample_rate * duration)
    raw = b""
    for i in range(samples):
        val = int(32767 * amplitude * math.sin(2 * math.pi * freq * i / sample_rate))
        raw += struct.pack("<h", val)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(raw)
    return buf.getvalue()


def check_sdp_audio():
    """Read saved SDP files and report audio status."""
    results = {}
    for name, path in [("offer", "/tmp/sdp_offer.txt"), ("answer", "/tmp/sdp_answer.txt")]:
        try:
            with open(path) as f:
                sdp = f.read()
            has_audio = "m=audio" in sdp
            has_opus = "opus/48000" in sdp
            results[name] = {"has_audio": has_audio, "has_opus": has_opus}
            logger.info(f"SDP {name}: m=audio={has_audio} opus/48000={has_opus}")
        except FileNotFoundError:
            results[name] = {"has_audio": False, "has_opus": False}
            logger.warning(f"SDP {name}: file not found at {path}")
    return results


async def main():
    robot_ip = "192.168.123.161"
    for arg in sys.argv[1:]:
        if arg.startswith("--robot-ip"):
            robot_ip = sys.argv[sys.argv.index(arg) + 1]

    logger.info("=" * 50)
    logger.info("WebRTC Audio Track Standalone Test")
    logger.info(f"Target: {robot_ip}")
    logger.info("=" * 50)

    # --- Step 1: Connect ---
    validated = asyncio.Event()

    def on_validated(robot_num):
        logger.info(f"[VALIDATED] Go2 connection validated (robot_num={robot_num})")
        validated.set()

    def on_message(robot_num, msg_type, data_decoded):
        pass  # ignore all DataChannel messages

    conn = Go2Connection(
        robot_ip=robot_ip,
        robot_num=0,
        token="",
        on_validated=on_validated,
        on_message=on_message,
        on_video_frame=None,
        decode_lidar=False,
        enable_audio_track=True,
    )

    logger.info("[1/6] Connecting to Go2...")
    await conn.connect()

    logger.info("[2/6] Waiting for validation (max 30s)...")
    try:
        await asyncio.wait_for(validated.wait(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("[FAIL] Validation timeout after 30s")
        await conn.pc.close()
        return

    logger.info("[OK] Connection validated")

    # --- Step 2: Check SDP ---
    logger.info("[3/6] Checking SDP audio negotiation...")
    sdp = check_sdp_audio()
    offer_ok = sdp.get("offer", {}).get("has_audio") and sdp.get("offer", {}).get("has_opus")
    answer_ok = sdp.get("answer", {}).get("has_audio") and sdp.get("answer", {}).get("has_opus")
    if not (offer_ok and answer_ok):
        logger.error("[FAIL] SDP audio negotiation incomplete")
        await conn.pc.close()
        return
    logger.info("[OK] SDP: both offer and answer have m=audio + opus/48000")

    # --- Step 3: Generate beep ---
    logger.info("[4/6] Generating 440Hz beep (48kHz, 2s, full amplitude)...")
    wav_bytes = generate_beep_wav(freq=440, duration=2.0, sample_rate=48000, amplitude=1.0)
    logger.info(f"  WAV size: {len(wav_bytes)} bytes")

    # --- Step 4: Send via audio track ---
    track = conn._tts_track
    if track is None:
        logger.error("[FAIL] TtsAudioTrack is None — audio track not initialized")
        await conn.pc.close()
        return

    logger.info("[5/6] Sending beep via TtsAudioTrack...")
    loop = asyncio.get_running_loop()
    track.enqueue_audio_threadsafe(wav_bytes, loop)

    # Wait for playback
    logger.info("  Waiting 4s for playback...")
    await asyncio.sleep(4)

    # --- Step 5: Report diagnostics ---
    logger.info("[6/6] Diagnostics:")
    logger.info(f"  play_id:     {track._play_id}")
    logger.info(f"  frames_sent: {track._frames_sent}")
    logger.info(f"  play_start:  {track._play_start_ts:.1f}")
    elapsed = time.time() - track._play_start_ts if track._play_start_ts > 0 else 0
    logger.info(f"  elapsed:     {elapsed:.1f}s")
    logger.info(f"  last_hash:   {track._last_hash}")

    # Connection health
    health = conn.health
    logger.info(f"  dc_state:    {health.dc_state}")
    logger.info(f"  conn_state:  {health.connection_state}")
    logger.info(f"  validated:   {health.validated}")
    logger.info(f"  audio_state: {health.last_audio_state}")

    # --- Summary ---
    logger.info("")
    logger.info("=" * 50)
    if track._frames_sent > 0:
        logger.info(f"[OK] {track._frames_sent} RTP frames sent")
        logger.info("[??] Did you hear the beep from Go2?")
        logger.info("  YES → audio track works standalone; problem is in ROS2/driver integration")
        logger.info("  NO  → Go2 audio reception issue; try power-cycling Go2")
    else:
        logger.info("[FAIL] 0 frames sent — enqueue_audio may have failed")
    logger.info("=" * 50)

    # --- Cleanup ---
    logger.info("Closing connection...")
    await conn.pc.close()
    logger.info("Done.")


if __name__ == "__main__":
    asyncio.run(main())
