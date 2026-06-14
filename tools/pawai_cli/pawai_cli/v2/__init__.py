"""PawAI CLI v2 — parallel Typer + Rich front-end (entry point: ``pawai2``).

This is an ADDITIVE, parallel skeleton. The legacy Click CLI
(``pawai_cli.main:cli`` → console_script ``pawai``) is the authoritative,
byte-identical implementation kept as the rollback path. v2 NEVER reimplements
lock / deploy / cleanup core logic — every command here delegates to the proven
Click implementation in ``pawai_cli.main`` (and ``pawai_cli.evidence``).

The only NEW surface area v2 adds is presentation (Rich console framing, a
distinct ``pawai2`` help tree) and the platform gate re-use. Behaviour of the
underlying commands is unchanged because we call their original callbacks.
"""

from __future__ import annotations

__all__ = ["app"]


def __getattr__(name: str):  # pragma: no cover - thin lazy import
    # Lazy so that `import pawai_cli.v2` does not force-import typer when a
    # caller only wants the docstring / metadata.
    if name == "app":
        from .app import app

        return app
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
