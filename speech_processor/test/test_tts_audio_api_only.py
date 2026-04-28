"""Source-level guard: tts_node may only emit WebRtcReq with audio api_ids.

If tts_node ever publishes a sport api_id, this test catches it before runtime.
Allowed audio api_ids: Megaphone enter (4001), upload (4003), exit (4002), cleanup (4004).
"""
import re
from pathlib import Path

ALLOWED_AUDIO_API_IDS = {4001, 4002, 4003, 4004}
TTS_NODE = Path(__file__).resolve().parents[1] / "speech_processor" / "tts_node.py"


def test_tts_node_only_uses_audio_api_ids():
    assert TTS_NODE.exists(), f"tts_node.py not found at {TTS_NODE}"
    src = TTS_NODE.read_text(encoding="utf-8")

    # Match patterns like "api_id = 4001", "api_id=4001", "api_id: 4001", "WebRtcReq(api_id=4001"
    pattern = re.compile(r"api_id\s*[:=]\s*(\d+)")
    found = {int(m.group(1)) for m in pattern.finditer(src)}

    if not found:
        # No literal api_id assignments — fine, tts_node may use named constants
        return

    illegal = found - ALLOWED_AUDIO_API_IDS
    assert not illegal, (
        f"tts_node.py uses non-audio api_id(s) {sorted(illegal)}; "
        f"only audio Megaphone api_ids {sorted(ALLOWED_AUDIO_API_IDS)} are allowed. "
        "Sport actions must be dispatched by interaction_executive_node."
    )
