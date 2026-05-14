"""Stage 2 refactor sanity check.

Verify each existing TTS provider class declares the TTSProviderBase
attributes (`name`, `sample_rate`, `supports_audio_tags`) and that all four
default to `supports_audio_tags=False` so the strip behavior in
tts_callback stays identical to before this commit.
"""

import pytest


def test_protocol_module_imports() -> None:
    """tts_provider module is ROS-free and importable in isolation."""
    from speech_processor.tts_provider import TTSProviderBase  # noqa: F401


PROVIDER_CLASS_NAMES = [
    "TTSProvider_ElevenLabs",
    "TTSProvider_MeloTTS",
    "TTSProvider_Piper",
    "TTSProvider_EdgeTTS",
]


@pytest.mark.parametrize("class_name", PROVIDER_CLASS_NAMES)
def test_existing_provider_declares_protocol_attrs(class_name: str) -> None:
    """Each existing provider class must expose name / sample_rate /
    supports_audio_tags as class attributes."""
    try:
        import speech_processor.tts_node as tts_node_module
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env (rclpy/std_msgs/go2_interfaces): {exc}")

    cls = getattr(tts_node_module, class_name)
    assert isinstance(cls.name, str) and cls.name
    assert isinstance(cls.sample_rate, int) and cls.sample_rate >= 0
    # All four legacy providers default to False — pre-existing behavior.
    assert cls.supports_audio_tags is False, (
        f"{class_name} must keep supports_audio_tags=False until "
        f"explicitly verified to render audio tags natively"
    )


def test_provider_names_are_unique() -> None:
    """Provider name is used for cache key and log correlation; collisions
    would silently mix caches across implementations."""
    try:
        import speech_processor.tts_node as tts_node_module
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"tts_node requires ROS env: {exc}")

    names = {
        getattr(tts_node_module, n).name for n in PROVIDER_CLASS_NAMES
    }
    assert len(names) == len(PROVIDER_CLASS_NAMES)
