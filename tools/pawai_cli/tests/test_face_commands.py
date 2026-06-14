"""T5-1 — CLI `face delete` / `face rebuild` must purge the `.npz` embedding cache.

B4 bug (plan5 §2.1): both commands only `rm -f .../model_sface.pkl`, but the
real embedding cache that can resurrect a deleted / ghost identity is the
sibling `.npz` (`face_identity_node._resolve_*` writes `model_path.with_suffix
(".npz")`). These tests assert the remote `rm` command string emitted by each
command includes BOTH `model_sface.pkl` AND `model_sface.npz`, and that the
behaviour stays idempotent (`rm -f` — safe whether the `.npz` exists or not).

All SSH is mocked via `shell.run_remote` — no real Jetson is contacted. The on-
Jetson real cache filename is confirmed by HITL `ls` (T5-2), not asserted here.
"""
from __future__ import annotations

from unittest.mock import Mock

from click.testing import CliRunner

from pawai_cli import shell
from pawai_cli.main import cli

_PKL = "model_sface.pkl"
_NPZ = "model_sface.npz"


def _rm_calls(run_remote):
    """Remote command strings that perform an `rm` on the face_db model cache."""
    return [
        call.args[0]
        for call in run_remote.call_args_list
        if "rm -f" in call.args[0] and "model_sface" in call.args[0]
    ]


def test_face_delete_cmd_contains_both_pkl_and_npz(monkeypatch):
    run_remote = Mock(return_value=shell.Result(code=0, stdout="deleted\n", stderr=""))
    monkeypatch.setattr(shell, "run_remote", run_remote)

    res = CliRunner().invoke(cli, ["face", "delete", "alice", "-y"])

    assert res.exit_code == 0
    rm_calls = _rm_calls(run_remote)
    assert rm_calls, "face delete emitted no model-cache rm command"
    cmd = rm_calls[-1]
    assert _PKL in cmd
    assert _NPZ in cmd


def test_face_rebuild_cmd_contains_both_pkl_and_npz(monkeypatch):
    run_remote = Mock(return_value=shell.Result(code=0, stdout="removed\n", stderr=""))
    monkeypatch.setattr(shell, "run_remote", run_remote)

    res = CliRunner().invoke(cli, ["face", "rebuild"])

    assert res.exit_code == 0
    rm_calls = _rm_calls(run_remote)
    assert rm_calls, "face rebuild emitted no model-cache rm command"
    cmd = rm_calls[-1]
    assert _PKL in cmd
    assert _NPZ in cmd


def test_face_delete_safe_when_npz_absent(monkeypatch):
    """Idempotent: the command still references `.npz` and `rm -f` does not fail
    when the cache is absent (mock SSH reports the `.npz` missing, exit 0)."""
    run_remote = Mock(
        return_value=shell.Result(code=0, stdout="deleted\n", stderr="")
    )
    monkeypatch.setattr(shell, "run_remote", run_remote)

    res = CliRunner().invoke(cli, ["face", "delete", "alice", "-y"])

    assert res.exit_code == 0
    rm_calls = _rm_calls(run_remote)
    assert rm_calls
    cmd = rm_calls[-1]
    # `.npz` is in the emitted command regardless of on-Jetson existence; the
    # `rm -f` form makes a missing cache a no-op (no hardcoded "must exist").
    assert _NPZ in cmd
    assert "rm -f" in cmd


def test_face_delete_removes_npz_when_present(monkeypatch):
    """When the `.npz` exists on the Jetson, the emitted command targets that
    exact path for removal (mock SSH stands in for a populated face_db)."""
    run_remote = Mock(
        return_value=shell.Result(code=0, stdout="deleted\n", stderr="")
    )
    monkeypatch.setattr(shell, "run_remote", run_remote)

    res = CliRunner().invoke(cli, ["face", "delete", "alice", "-y"])

    assert res.exit_code == 0
    rm_calls = _rm_calls(run_remote)
    assert rm_calls
    cmd = rm_calls[-1]
    assert "/home/jetson/face_db/model_sface.npz" in cmd
