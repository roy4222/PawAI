from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click

from . import shell
from .status import _read_last_deploy_remote

DEFAULT_SNAPSHOT_REL = Path("artifacts/baseline/baseline_snapshot.json")
DEFAULT_SCHEMA_REL = Path(".claude/schemas/baseline_snapshot.schema.json")
FREEZE_ROOT_REL = Path("artifacts/baseline/frozen")


@click.group("readiness", invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Print machine-readable JSON.")
@click.option(
    "--accept-warnings",
    is_flag=True,
    help="Record operator acceptance for advisory warnings.",
)
@click.option(
    "--force-ready",
    is_flag=True,
    help="Record an override attempt; hard failures still return not_ready.",
)
@click.option("--operator", default="", help="Operator name for override trace.")
@click.option("--reason", default="", help="Human reason for override trace.")
@click.pass_context
def readiness(
    ctx: click.Context,
    as_json: bool,
    accept_warnings: bool,
    force_ready: bool,
    operator: str,
    reason: str,
) -> None:
    """Evaluate demo readiness from baseline snapshot and deploy manifest."""
    if ctx.invoked_subcommand is not None:
        return

    if (accept_warnings or force_ready) and (not operator.strip() or not reason.strip()):
        raise click.ClickException(
            "--operator and --reason are required with --accept-warnings or --force-ready"
        )

    now_iso = _now_iso()
    result = collect_readiness(
        now_iso=now_iso,
        overrides={
            "accept_warnings": accept_warnings,
            "force_ready": force_ready,
            "operator": operator,
            "reason": reason,
            "timestamp": now_iso,
        },
    )
    _print_result(result, as_json=as_json)
    sys.exit(0 if result["verdict"] == "ready" else 1)


@readiness.command("freeze")
@click.option(
    "--date",
    "date_str",
    envvar="PAWAI_FREEZE_DATE",
    required=True,
    help="Demo date folder, e.g. 2026-06-18. Can also use PAWAI_FREEZE_DATE.",
)
def freeze(date_str: str) -> None:
    """Copy the working baseline snapshot into a dated frozen folder."""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise click.ClickException("--date must use YYYY-MM-DD")

    source = _default_snapshot_path()
    if not source.exists():
        raise click.ClickException(f"snapshot not found: {source}")

    destination = (
        shell.repo_root() / FREEZE_ROOT_REL / date_str / "baseline_snapshot.json"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    click.echo(f"frozen: {destination}")


def collect_readiness(
    *,
    now_iso: str,
    overrides: dict[str, Any] | None = None,
    snapshot_path: Path | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    """Read local inputs and delegate verdict logic to benchmarks.core."""
    # benchmarks/ lives at the repo root, which is not on sys.path when the
    # pawai CLI runs standalone (installed pkg / different cwd). Add it lazily
    # so the verdict logic is importable at runtime and under pytest.
    repo_root = str(shell.repo_root())
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from benchmarks.core.readiness import evaluate_readiness

    snapshot = _read_json(snapshot_path or _default_snapshot_path())
    schema = _read_json(schema_path or _default_schema_path())
    manifest = _read_last_deploy_remote()
    deploy_sha = _deploy_sha(manifest)

    result = evaluate_readiness(
        snapshot,
        deploy_sha=deploy_sha,
        now_iso=now_iso,
        schema=schema,
        overrides=overrides,
    )
    if schema is None:
        result["verdict"] = "not_ready"
        result["reasons"].append("schema_missing")
    return result


def _default_snapshot_path() -> Path:
    return _resolve_repo_path(os.environ.get("PAWAI_SCOREBOARD_PATH"), DEFAULT_SNAPSHOT_REL)


def _default_schema_path() -> Path:
    return _resolve_repo_path(
        os.environ.get("PAWAI_BASELINE_SCHEMA_PATH"),
        DEFAULT_SCHEMA_REL,
    )


def _resolve_repo_path(value: str | None, default_rel: Path) -> Path:
    if value:
        path = Path(value).expanduser()
        return path if path.is_absolute() else shell.repo_root() / path
    return shell.repo_root() / default_rel


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _deploy_sha(manifest: dict[str, Any] | None) -> str | None:
    if not manifest:
        return None
    return manifest.get("git_sha") or manifest.get("git_sha_full")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _print_result(result: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(result, ensure_ascii=False, indent=2))
        return

    click.echo(f"verdict: {result['verdict']}")
    if result["reasons"]:
        click.echo("reasons:")
        for reason in result["reasons"]:
            click.echo(f"  - {reason}")
    if result["warnings"]:
        click.echo("warnings:")
        for warning in result["warnings"]:
            click.echo(f"  - {warning}")
    if result["override"]:
        click.echo("override:")
        click.echo(f"  operator: {result['override']['operator']}")
        click.echo(f"  reason: {result['override']['reason']}")
        click.echo(f"  timestamp: {result['override']['timestamp']}")
