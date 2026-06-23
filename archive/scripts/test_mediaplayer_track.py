#!/usr/bin/env python3
"""
Test audio track using aiortc MediaPlayer (community pattern).

This replicates exactly what go2_webrtc_connect/play_mp3.py does:
  1. Connect to Go2
  2. MediaPlayer(wav_file).audio → addTrack AFTER connect
  3. Wait for playback

Usage:
    bash scripts/clean_all.sh
    source /opt/ros/humble/setup.zsh && source install/setup.zsh
    python3 scripts/test_mediaplayer_track.py
"""

import asyncio
import io
import logging
import math
import struct
import sys
import wave
import tempfile

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("mediaplayer_track")

from go2_robot_sdk.infrastructure.webrtc.go2_connection import Go2Connection


def gen_beep_wav_file(freq=440, dur=2.0, sr=48000):
    """Generate 440Hz WAV file, return path."""
    samples = int(sr * dur)
    raw = b""
    for i in range(samples):
        val = int(32767 * math.sin(2 * math.pi * freq * i / sr))
        raw += struct.pack("<h", val)
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    with wave.open(tmp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(raw)
    return tmp.name


async def main():
    robot_ip = "192.168.123.161"

    logger.info("=" * 50)
    logger.info("MediaPlayer Audio Track Test (community pattern)")
    logger.info("=" * 50)

    # NOTE: Community pattern adds track AFTER connect.
    # But our Go2Connection adds audio track in __init__.
    # So we connect WITHOUT audio track, then add MediaPlayer track after.

    validated = asyncio.Event()
    def on_validated(rn):
        validated.set()

    conn = Go2Connection(
        robot_ip=robot_ip, robot_num=0, token="",
        on_validated=on_validated, on_message=lambda *a: None,
        enable_audio_track=False,  # Don't add our TtsAudioTrack
        decode_lidar=False,
    )

    logger.info("[1/4] Connecting...")
    await conn.connect()
    try:
        await asyncio.wait_for(validated.wait(), timeout=30)
    except asyncio.TimeoutError:
        logger.error("[FAIL] Validation timeout")
        await conn.pc.close()
        return
    logger.info("[OK] Connected and validated")

    # Step 2: Generate beep WAV file
    logger.info("[2/4] Generating 440Hz beep WAV (48kHz, 2s)...")
    wav_path = gen_beep_wav_file(freq=440, dur=2.0, sr=48000)
    logger.info(f"  WAV file: {wav_path}")

    # Step 3: Use MediaPlayer to create audio track (community pattern)
    logger.info("[3/4] Creating MediaPlayer and adding track...")
    try:
        from aiortc.contrib.media import MediaPlayer
        player = MediaPlayer(wav_path)
        audio_track = player.audio
        if audio_track is None:
            logger.error("[FAIL] MediaPlayer returned no audio track")
            await conn.pc.close()
            return
        conn.pc.addTrack(audio_track)
        logger.info(f"  Track added: {audio_track}")
    except Exception as e:
        logger.error(f"[FAIL] MediaPlayer error: {e}")
        await conn.pc.close()
        return

    # Step 4: Wait for playback
    logger.info("[4/4] Waiting 5s for playback...")
    await asyncio.sleep(5)

    logger.info("[??] Did you hear the beep from Go2?")
    logger.info("  YES → MediaPlayer+addTrack works; our TtsAudioTrack needs to match")
    logger.info("  NO  → audio track path doesn't work on this Go2; use Megaphone instead")
    logger.info("=" * 50)

    await conn.pc.close()
    logger.info("Done.")

    # Cleanup temp file
    import os
    os.unlink(wav_path)


if __name__ == "__main__":
    asyncio.run(main())
