"""TTS provider interface (Protocol).

Background:
    Stage 2 of the B1 TTS rewrite. Existing tts_node.py has 4 provider classes
    (ElevenLabs / MeloTTS / Piper / EdgeTTS) without a common base. To add
    Gemini TTS (which natively renders audio tags like `[excited]` `[laughs]`)
    we need a uniform interface so tts_node can: (1) decide whether to strip
    audio tags, (2) know each provider's native sample rate for the playback
    layer, (3) drive a fallback chain.

    Pure module — no ROS dependencies, importable in unit tests in isolation.

Note:
    `tts_node.TTSProvider` is an Enum (user-facing config). This Protocol is
    the runtime interface — different concept, different name.
"""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TTSProviderBase(Protocol):
    """Common interface every TTS provider class must satisfy.

    Implementations declare these as class attributes (not instance), so the
    tts_node can read `provider_class.supports_audio_tags` etc. without
    instantiation. Existing 4 classes use duck typing — Protocol matches by
    structure, no inheritance required.
    """

    # Stable provider identifier — matches the user-facing TTSProvider Enum
    # value so we can correlate logs and cache keys.
    name: str

    # Native PCM sample rate of the synthesized audio. 0 means dynamic/unknown
    # (e.g. MeloTTS reads from the model). Used by the playback layer to
    # decide whether to resample for Megaphone (16 kHz hard cap) or pass
    # straight to USB local speaker.
    sample_rate: int

    # True if the provider natively renders inline audio tags like
    # `[excited]`, `[laughs]`, `[sighs]` as emotion/SFX rather than reading
    # them as literal text. When False, tts_node strips tags before calling
    # synthesize() (see speech_processor.audio_tag.strip_audio_tags).
    supports_audio_tags: bool

    def synthesize(self, text: str) -> Optional[bytes]:
        """Generate audio bytes for `text`. Return None on failure.

        The returned bytes are whatever the provider produces natively
        (mp3, raw PCM, WAV). Format normalization happens in the playback
        layer via pydub. New providers SHOULD return WAV bytes when possible
        (with a proper RIFF header) for cleanest cache & playback.
        """
        ...
