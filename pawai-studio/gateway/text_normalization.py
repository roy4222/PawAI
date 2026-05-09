"""Lazy-import OpenCC s2twp; fallback 原文 on any error."""
_converter = None


def to_traditional_tw(text: str) -> str:
    """Convert Simplified Chinese to Traditional Chinese (Taiwan variant).

    Uses opencc-python-reimplemented with s2twp config (no .json suffix —
    the library appends .json automatically; passing "s2twp.json" silently
    breaks lookup as "s2twp.json.json" and the helper falls back to original).
    Lazily initialises the converter on first call.
    Falls back to returning the original text if OpenCC is unavailable or
    conversion raises an exception.
    """
    global _converter
    if not text:
        return text
    if _converter is None:
        try:
            from opencc import OpenCC
            _converter = OpenCC("s2twp")
        except Exception:
            _converter = False
            return text
    if _converter is False:
        return text
    try:
        return _converter.convert(text)
    except Exception:
        return text
