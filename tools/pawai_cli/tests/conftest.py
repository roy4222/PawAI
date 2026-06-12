"""Shared CLI test isolation (system Phase 2 T2C-0 — the #150 lesson).

Issue #150: a CLI test escaped to the real repo root, loaded the developer's
.env.local (real JETSON_HOST), and an un-mocked shell call did a REAL ssh that
hung ~300s. The same class resurfaced 2026-06-12: doctor tests that mock only
find_jetson_peer let the topology probes run real `ssh` — 27s per test with
the Jetson off, indefinitely with a black-holing resolver. Structural fixes:

1. PAWAI_REPO_ROOT always points at an isolated tmp dir; JETSON_HOST /
   JETSON_REPO pinned to deterministic test values. Tests needing a custom
   root monkeypatch.setenv on top (wins over the autouse fixture).
2. Remote/stream shell entry points are REFUSED by default: an un-mocked call
   returns instantly (255 / 127) with a loud "blocked-by-conftest" marker
   instead of touching the network. Tests that legitimately exercise these
   paths already `patch()` them per-test — an inner patch overrides the stub
   and restores it on exit. shell.run stays real: it only ever runs fast
   local commands (git / tailscale) in this suite.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pawai_cli import shell

# readiness delegates verdict logic to benchmarks.core — that package lives at
# the REAL repo root, which PAWAI_REPO_ROOT isolation (below) hides. Imports
# resolve against the real tree; filesystem reads stay isolated in tmp_path.
_REAL_REPO_ROOT = str(Path(__file__).resolve().parents[3])
if _REAL_REPO_ROOT not in sys.path:
    sys.path.insert(0, _REAL_REPO_ROOT)


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "real_repo: test reads real repo files (docs/scripts/schemas) — skips the "
        "PAWAI_REPO_ROOT tmp isolation; remote refusal stubs stay active.",
    )


@pytest.fixture(autouse=True)
def _isolated_cli_env(request, tmp_path, monkeypatch):
    if request.node.get_closest_marker("real_repo"):
        # Real repo files, but NEVER the developer's .env/.env.local — that is
        # machine-specific pollution (the #150 class: a real JETSON_TAILSCALE_IP
        # in .env.local silently overwrites the values these tests simulate via
        # monkeypatch.setenv). CI has no .env.local; this makes local == CI.
        from pawai_cli import main as _main
        monkeypatch.setattr(_main, "_load_env", lambda root: None)
        yield
        return
    monkeypatch.setenv("PAWAI_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("JETSON_HOST", "jetson-test")
    monkeypatch.setenv("JETSON_REPO", "/home/jetson/elder_and_dog")
    yield


_NETWORK_BINARIES = ("ssh", "rsync", "scp")


@pytest.fixture(autouse=True)
def _no_real_remote(monkeypatch):
    real_run = shell.run
    real_stream = shell.stream

    def _refuse_run_remote(command, timeout=None):
        return shell.Result(
            255, "", f"blocked-by-conftest: un-mocked run_remote({command!r}) — "
            "tests must patch shell.run_remote explicitly (T2C-0 / #150)")

    def _refuse_stream_remote(command):
        return 255

    def _guarded_run(argv, cwd=None, timeout=None):
        # doctor probes ssh via shell.run(shell.ssh_args(...)) — that is still
        # the network. Local tools (git / tailscale / bash) stay real and fast.
        argv = list(argv)
        if argv and argv[0] in _NETWORK_BINARIES:
            return shell.Result(
                255, "", f"blocked-by-conftest: un-mocked {argv[0]} call — "
                "patch shell.run / mock the probe explicitly (T2C-0 / #150)")
        return real_run(argv, cwd=cwd, timeout=timeout)

    def _guarded_stream(argv, cwd=None, env=None):
        # Same rule for the streaming runner: local scripts (contract check,
        # healthcheck wrappers under test) run for real; ssh/rsync never do.
        argv = list(argv)
        if argv and argv[0] in _NETWORK_BINARIES:
            return 127
        return real_stream(argv, cwd=cwd, env=env)

    monkeypatch.setattr(shell, "run_remote", _refuse_run_remote)
    monkeypatch.setattr(shell, "stream_remote", _refuse_stream_remote)
    monkeypatch.setattr(shell, "stream", _guarded_stream)
    monkeypatch.setattr(shell, "run", _guarded_run)
    yield
