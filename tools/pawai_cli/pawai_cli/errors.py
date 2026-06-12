"""Structured CLI errors (system Phase 2 T2C-3).

Rule: every failure a teammate can hit names its fix — the error text carries
"↳" suggestion lines the user can paste/run (pawai doctor, deploy, env vars),
instead of a bare exit code they have to come ask Roy about.
"""
from __future__ import annotations

from collections.abc import Sequence

import click


def structured_error(message: str, hints: Sequence[str]) -> click.ClickException:
    """Build a ClickException whose text includes actionable fix lines."""
    lines = [message]
    lines.extend(f"  ↳ {hint}" for hint in hints)
    return click.ClickException("\n".join(lines))
