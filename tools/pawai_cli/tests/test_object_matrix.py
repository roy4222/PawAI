from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from pawai_cli.main import cli


def _invoke(args):
    return CliRunner().invoke(cli, args)


def test_object_matrix_passes_required_args_to_remote_capture_script():
    calls: list[str] = []

    def fake_stream_remote(cmd):
        calls.append(cmd)
        return 0

    with patch("pawai_cli.main.shell.stream_remote", side_effect=fake_stream_remote):
        result = _invoke([
            "object",
            "matrix",
            "--object",
            "cup",
            "--distance",
            "0.7",
            "--light",
            "normal",
        ])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    command = calls[0]
    assert "scripts/obj_matrix_cap.py" in command
    assert "--object cup" in command
    assert "--distance 0.7" in command
    assert "--light normal" in command
    assert "source /opt/ros/humble/setup.zsh" in command
    assert "source install/setup.zsh" in command
    assert "/home/jetson/elder_and_dog/artifacts/object_matrix/object_matrix.csv" in result.output


def test_object_matrix_requires_object():
    result = _invoke([
        "object",
        "matrix",
        "--distance",
        "0.7",
        "--light",
        "normal",
    ])

    assert result.exit_code != 0
    assert "--object" in result.output


def test_object_matrix_passes_auto_and_trials():
    calls: list[str] = []

    with patch(
        "pawai_cli.main.shell.stream_remote",
        side_effect=lambda cmd: calls.append(cmd) or 0,
    ):
        result = _invoke([
            "object",
            "matrix",
            "--object",
            "cup",
            "--distance",
            "0.7",
            "--light",
            "normal",
            "--auto",
            "--trials",
            "3",
        ])

    assert result.exit_code == 0, result.output
    assert "--auto" in calls[0]
    assert "--trials 3" in calls[0]


def test_object_matrix_stream_rc_propagates():
    with patch("pawai_cli.main.shell.stream_remote", return_value=2):
        result = _invoke([
            "object",
            "matrix",
            "--object",
            "cup",
            "--distance",
            "0.7",
            "--light",
            "normal",
        ])

    assert result.exit_code == 2
    assert "pawai demo start" in result.output


def test_object_matrix_custom_out_prints_remote_csv_hint():
    calls: list[str] = []

    with patch(
        "pawai_cli.main.shell.stream_remote",
        side_effect=lambda cmd: calls.append(cmd) or 0,
    ):
        result = _invoke([
            "object",
            "matrix",
            "--object",
            "cup",
            "--distance",
            "0.7",
            "--light",
            "normal",
            "--out",
            "artifacts/object_matrix/cup.csv",
        ])

    assert result.exit_code == 0, result.output
    assert "--out artifacts/object_matrix/cup.csv" in calls[0]
    assert "/home/jetson/elder_and_dog/artifacts/object_matrix/cup.csv" in result.output
    assert "pawai evidence pull" in result.output
