"""Rich console base for PawAI CLI v2.

A single shared :class:`rich.console.Console` plus a thin set of output helpers
so every v2 command frames messages consistently. Stdout vs stderr is kept
honest: status/info/success go to stdout, warnings/errors go to stderr.

These helpers are deliberately small. v2 commands DELEGATE their real work to
the legacy Click implementation, which prints its own ``click.echo`` output;
these helpers are only for v2's own framing (banners, the platform-gate notice,
PowerShell guidance, and command-level headers).
"""

from __future__ import annotations

import os

from rich.console import Console

# NO_COLOR / non-tty CI: Rich auto-detects, but make it explicit and testable.
_FORCE_NO_COLOR = bool(os.environ.get("NO_COLOR"))

console = Console(stderr=False, no_color=_FORCE_NO_COLOR, highlight=False)
err_console = Console(stderr=True, no_color=_FORCE_NO_COLOR, highlight=False)


def info(message: str) -> None:
    """Neutral informational line (stdout)."""
    console.print(message)


def success(message: str) -> None:
    """Success line (stdout)."""
    console.print(f"[bold green]✓[/] {message}")


def warn(message: str) -> None:
    """Warning line (stderr)."""
    err_console.print(f"[bold yellow]⚠[/] {message}")


def error(message: str) -> None:
    """Error line (stderr)."""
    err_console.print(f"[bold red]✗[/] {message}")


def header(title: str) -> None:
    """Section header used at the top of a v2 command's own framing."""
    console.print(f"[bold cyan]{title}[/]")
