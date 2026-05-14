"""Audio tag handling for TTS pipeline.

LLM personas (eval / Gemini Flash) emit emotion tags like ``[excited]``,
``[curious]``, ``[laughs]`` inline with reply text. Current TTS providers
(edge-tts, Piper) read these literally — `[excited] 你好` becomes
"bracket excited bracket 你好" out of the speaker.

Until B1 TTS 換血 lands a provider that natively renders SSML-style tags
(Gemini 3.1 Flash TTS), strip them at the TTS boundary so synthesis sees
only the spoken text. The original tagged text continues to flow through
upstream channels (Studio trace, brain proposal logs).

Pure module — no ROS dependencies. Unit-testable in isolation.
"""

import re

# Match `[word]` or `[word_word]` plus optional trailing whitespace.
# Conservative: only ASCII letters/underscore inside the brackets, so we
# don't accidentally strip Chinese-bracketed annotations or numbers.
_AUDIO_TAG_RE = re.compile(r"\[[a-zA-Z_]+\]\s*")


def strip_audio_tags(text: str) -> str:
    """Remove inline audio/emotion tags from `text`.

    Examples:
        ``"[excited] 你好"`` → ``"你好"``
        ``"[curious] 我是 [laughs] PawAI"`` → ``"我是 PawAI"``
        ``"你好"`` → ``"你好"`` (unchanged)
        ``"[非tag]"`` → ``"[非tag]"`` (Chinese inside, untouched)
    """
    if not text:
        return text
    return _AUDIO_TAG_RE.sub("", text).strip()
