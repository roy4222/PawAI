"""PawAI CLI v2 Typer application (entry point: ``pawai2``).

Parity contract
---------------
Every command below is a THIN wrapper. It collects options, then delegates to
the *exact* legacy implementation by calling the original Click command's
``.callback`` (the undecorated function) with explicit keyword arguments. We do
NOT reimplement lock / deploy / cleanup / smoke / evidence logic — those live
once, in ``pawai_cli.main`` and ``pawai_cli.evidence``, and the legacy ``pawai``
binary keeps running them byte-identically.

Because the legacy callbacks signal completion with ``sys.exit()`` /
``raise SystemExit`` and surface failures with ``click.ClickException``, the
delegation boundary (:func:`_delegate`) translates those into the same process
exit codes Click itself would produce, so ``pawai2 X`` exits the same way
``pawai X`` does.
"""

from __future__ import annotations

from typing import Callable, Optional

import click
import typer

from .. import __version__, shell
from .. import platform as _plat
from ..main import _load_env
from . import console as c

app = typer.Typer(
    name="pawai2",
    help=(
        "PawAI CLI v2 (Typer + Rich) — parallel front-end. "
        "Delegates to the proven `pawai` implementation; the legacy `pawai` "
        "binary remains the byte-identical rollback path."
    ),
    add_completion=True,
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

smoke_app = typer.Typer(name="smoke", help="End-to-end smoke runs (wraps existing scripts).",
                        no_args_is_help=True)
evidence_app = typer.Typer(name="evidence", help="Evidence Center artifacts (read-only).",
                           no_args_is_help=True)
demo_app = typer.Typer(name="demo", help="Demo lane controls (lock-aware; delegates to legacy).",
                       no_args_is_help=True)
app.add_typer(smoke_app, name="smoke")
app.add_typer(evidence_app, name="evidence")
app.add_typer(demo_app, name="demo")


# ── delegation boundary ──────────────────────────────────────────────────────

def _delegate(callback: Callable, **kwargs) -> None:
    """Run a legacy Click command's raw callback and mirror Click's exit codes.

    The legacy callbacks either return normally, ``sys.exit(code)`` /
    ``raise SystemExit(code)``, or ``raise click.ClickException``. Map each to
    the process exit Click would have produced so ``pawai2`` parity holds:

      * normal return        → exit 0
      * SystemExit(code)     → exit code (None/str handled like CPython)
      * ClickException       → render to stderr + exit ``exc.exit_code`` (1)
      * click.Abort          → "Aborted!" + exit 1 (Click's convention)
    """
    try:
        callback(**kwargs)
    except SystemExit as exc:
        code = exc.code
        if code is None:
            raise typer.Exit(code=0) from None
        if isinstance(code, int):
            raise typer.Exit(code=code) from None
        # Non-int exit payload (a message): print + exit 1, mirroring CPython.
        c.error(str(code))
        raise typer.Exit(code=1) from None
    except click.exceptions.Abort:
        c.error("Aborted!")
        raise typer.Exit(code=1) from None
    except click.ClickException as exc:
        # Click prints "Error: <message>" to stderr; keep that wording so logs
        # and muscle-memory match the legacy binary.
        c.err_console.print(f"Error: {exc.format_message()}")
        raise typer.Exit(code=exc.exit_code) from None
    else:
        raise typer.Exit(code=0)


def _legacy_callback(name: str) -> Callable:
    """Resolve a top-level legacy Click command's raw callback by command name."""
    from ..main import cli as _legacy_cli

    return _legacy_cli.commands[name].callback


def _legacy_group_callback(group: str, sub: str) -> Callable:
    """Resolve a legacy Click sub-command callback (e.g. smoke→brain)."""
    from ..main import cli as _legacy_cli

    return _legacy_cli.commands[group].commands[sub].callback


# ── root callback: platform gate + env load (parity with legacy cli()) ───────

def _version_callback(value: bool) -> None:
    if value:
        c.info(f"pawai2 {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", callback=_version_callback, is_eager=True,
        help="Show pawai2 version and exit.",
    ),
) -> None:
    """Root: enforce the same platform gate the legacy ``pawai`` enforces.

    ``platform.assert_supported`` exits 10 on Windows-native / WSL1 / a repo
    under /mnt/c — identical gate to ``pawai_cli.main.cli``. On Windows native
    the gate's own message already points users at WSL2 (``wsl --install``); we
    do not "soft-support" PowerShell here.
    """
    root = shell.repo_root()
    _plat.assert_supported(root)
    _load_env(root)


# ── doctor / status / logs (top-level legacy commands) ───────────────────────

@app.command()
def doctor(
    verbose: bool = typer.Option(False, "--verbose", help="Print SSH stderr details on failure."),
    expect_demo: bool = typer.Option(False, "--expect-demo",
                                     help="Treat Gateway 8080 down as FAIL (default: SKIP)."),
    fix: bool = typer.Option(False, "--fix",
                             help="Prompt to write detected Tailscale IP into .env.local."),
    deep: bool = typer.Option(False, "--deep", help="Run live OpenRouter API call."),
    cache: int = typer.Option(0, "--cache", help="Cache result for N seconds."),
) -> None:
    """Validate local environment and Jetson reachability (delegates to legacy)."""
    _delegate(_legacy_callback("doctor"), verbose=verbose, expect_demo=expect_demo,
              fix=fix, deep=deep, cache_seconds=cache)


@app.command()
def status(
    short: bool = typer.Option(False, "--short", help="Skip ROS node detail."),
) -> None:
    """Show Jetson tmux/ROS/git state (delegates to legacy)."""
    _delegate(_legacy_callback("status"), short=short)


@app.command()
def logs(
    module: str = typer.Argument(..., help="Module name, or 'all'."),
    lines: int = typer.Option(500, "--lines", help="Lines to capture from tmux pane."),
) -> None:
    """Capture Jetson tmux logs for a module (delegates to legacy)."""
    _delegate(_legacy_callback("logs"), module=module, lines=lines)


# ── smoke brain / object / nav-static (subset; vision/full deferred) ─────────

@smoke_app.command("brain")
def smoke_brain(
    rounds: int = typer.Option(5, "--rounds", min=1, max=30,
                               help="E2E rounds (smoke_test_e2e.sh argument)."),
) -> None:
    """Run the speech E2E smoke on the Jetson (delegates to legacy)."""
    _delegate(_legacy_group_callback("smoke", "brain"), rounds=rounds)


@smoke_app.command("object")
def smoke_object(
    with_cup: bool = typer.Option(False, "--with-cup",
                                  help="After static checks, wait up to 60s for a cup event."),
) -> None:
    """Run the object smoke on the Jetson (delegates to legacy)."""
    _delegate(_legacy_group_callback("smoke", "object"), with_cup=with_cup)


@smoke_app.command("nav-static")
def smoke_nav_static() -> None:
    """Run the nav STATIC smoke on the Jetson (read-only; delegates to legacy).

    Hard-wires the legacy ``smoke nav --static`` contract: motion regression is
    HITL and intentionally never exposed through v2.
    """
    _delegate(_legacy_group_callback("smoke", "nav"), static_only=True)


# ── evidence pull (read-only) ────────────────────────────────────────────────

@evidence_app.command("pull")
def evidence_pull(
    dest: Optional[str] = typer.Option(
        None, "--dest",
        help="Local destination dir (default: artifacts/evidence/traces)."),
) -> None:
    """Pull runtime/traces/*.jsonl from the Jetson gateway store (delegates)."""
    from ..evidence import evidence as _evidence_group

    _delegate(_evidence_group.commands["pull"].callback, dest_str=dest)


# ── demo start / stop (lock/deploy/cleanup core untouched — delegated) ───────

@demo_app.command("start")
def demo_start(
    no_studio: bool = typer.Option(False, "--no-studio",
                                   help="Start full mode without local Studio overlay."),
    brain_only: bool = typer.Option(False, "--brain-only",
                                    help="Start minimal brain stack only."),
    nav: Optional[str] = typer.Option(None, "--nav", metavar="MODE",
                                      help="Start nav capability lane. First version: capability."),
    yes: bool = typer.Option(False, "-y", "--yes",
                             help="Skip ordinary prompts (does NOT override another user's lock)."),
    force: bool = typer.Option(False, "--force", help="Take over another user's demo lock."),
    skip_healthcheck: bool = typer.Option(False, "--skip-healthcheck",
                                          help="Escape hatch: skip the post-start healthcheck."),
    with_shadow: bool = typer.Option(False, "--with-shadow",
                                     help="After a healthy brain demo, enable ism_shadow_enabled."),
    with_lidar: bool = typer.Option(False, "--with-lidar",
                                    help="After a healthy brain demo, also start a raw LiDAR "
                                         "monitor + Act1 reactive forward controller (LOCKED). "
                                         "NO nav2/amcl/2nd driver/motion. Same as "
                                         "PAWAI_DEMO_WITH_LIDAR=1."),
) -> None:
    """Start brain demo or nav capability lane (delegates to legacy demo start).

    The lock acquisition, start.sh invocation, post-start healthcheck gate, and
    shadow-soak handling all run inside the legacy callback — v2 adds nothing.
    """
    _delegate(_legacy_group_callback("demo", "start"),
              no_studio=no_studio, brain_only=brain_only, nav_mode=nav,
              yes=yes, force=force, skip_healthcheck=skip_healthcheck,
              with_shadow=with_shadow, with_lidar=with_lidar)


@demo_app.command("stop")
def demo_stop(
    force: bool = typer.Option(False, "--force",
                               help="Stop another user's demo and release their lock."),
) -> None:
    """Stop the running lane (lock-lane-routed cleanup; delegates to legacy)."""
    _delegate(_legacy_group_callback("demo", "stop"), force=force)


# Pre-resolve the demo-start parameter name set once, for the parity test to
# assert v2's kwargs are a faithful 1:1 of the legacy callback signature.
def _legacy_demo_start_params() -> set[str]:
    import inspect

    from ..main import cli as _legacy_cli

    sig = inspect.signature(_legacy_cli.commands["demo"].commands["start"].callback)
    return set(sig.parameters)


if __name__ == "__main__":  # pragma: no cover
    app()
