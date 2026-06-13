"""pawai evidence — read-only Evidence Center artifact pull (T2C-2).

Roy D5 ruling: trace 單一真相 = pawai_contracts schema + gateway JSONL；
CLI 只負責「讀取與匯出」。This command rsyncs the gateway trace store
(runtime/traces/*.jsonl on the Jetson, written by pawai-studio/gateway/
trace_store.py) back to local artifacts/evidence/traces/ and prints a short
summary. It never deletes on either side and never rewrites the JSONL.
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from . import shell
from .errors import structured_error

EVIDENCE_DEST_REL = Path("artifacts/evidence/traces")
NAV_CAPABILITY_DEST_NAME = "nav_capability"


def _remote_runtime_dir(name: str) -> str:
    return f"{shell.jetson_host()}:{shell.jetson_repo().rstrip('/')}/runtime/{name}/"


def _pull_read_only(src: str, dest: Path) -> None:
    # Read-only pull: -az, NO --delete (local extras stay; remote untouched).
    argv = ["rsync", "-az", src, f"{dest}/"]
    code = shell.stream(argv)
    if code == 127:
        raise structured_error(
            "rsync not found on this machine",
            ["install rsync: sudo apt install rsync (Linux/WSL) / "
             "brew install rsync (Mac)"],
        )
    if code != 0:
        raise structured_error(
            f"evidence pull failed (rsync exit {code})",
            [
                "SSH 不通？跑 `pawai doctor` 看 Network topology / Tailscale 區塊",
                f"確認 Jetson 端有 trace：ssh {shell.jetson_host()} "
                f"'ls {shell.jetson_repo()}/runtime/traces/'",
                "gateway 沒跑、或 store 被 PAWAI_TRACE_STORE_ENABLED=0 關掉時，"
                "Jetson 端不會有檔案",
            ],
        )


def summarize_jsonl_dir(directory: Path) -> dict:
    """Pure summary of pulled JSONL: file/event/suppressed counts.
    Garbage lines are skipped (same tolerance as the gateway export)."""
    files = sorted(Path(directory).glob("*.jsonl"))
    events = 0
    suppressed = 0
    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for raw in text.splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                ev = json.loads(raw)
            except (ValueError, TypeError):
                continue
            if not isinstance(ev, dict):
                continue
            events += 1
            if ev.get("verdict") == "suppressed":
                suppressed += 1
    return {"files": len(files), "events": events, "suppressed": suppressed}


@click.group("evidence")
def evidence() -> None:
    """Evidence Center artifacts（只讀，不改 Jetson 端任何東西）。"""


@evidence.command("pull")
@click.option("--dest", "dest_str", default=None,
              help="Local destination dir (default: artifacts/evidence/traces).")
def pull(dest_str: str | None) -> None:
    """Pull runtime/traces/*.jsonl from the Jetson gateway trace store."""
    root = shell.repo_root()
    dest = Path(dest_str).expanduser() if dest_str else root / EVIDENCE_DEST_REL
    nav_dest = dest.parent / NAV_CAPABILITY_DEST_NAME
    nav_dest.mkdir(parents=True, exist_ok=True)
    dest.mkdir(parents=True, exist_ok=True)
    _pull_read_only(_remote_runtime_dir("nav_capability"), nav_dest)
    _pull_read_only(_remote_runtime_dir("traces"), dest)
    summary = summarize_jsonl_dir(dest)
    click.echo(
        f"✓ pulled {summary['files']} file(s), {summary['events']} event(s), "
        f"{summary['suppressed']} suppressed → {dest}"
    )
