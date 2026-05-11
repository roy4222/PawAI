from __future__ import annotations

from click.testing import CliRunner

from pawai_cli.main import cli
from pawai_cli.modules import MODULES, get_module


def test_module_table_has_expected_modules() -> None:
    assert set(MODULES) == {
        "face",
        "speech",
        "gesture",
        "pose",
        "object",
        "nav",
        "brain",
        "studio",
    }


def test_module_aliases() -> None:
    assert get_module("vision").key == "gesture"
    assert get_module("pawai-brain").key == "brain"


def test_dev_info_gesture() -> None:
    result = CliRunner().invoke(cli, ["dev", "info", "gesture"])

    assert result.exit_code == 0
    assert "Module: gesture" in result.output
    assert "vision_perception" in result.output
    assert "pawai jetson deploy --module gesture" in result.output


def test_dev_info_nav_uses_reference_fallback() -> None:
    result = CliRunner().invoke(cli, ["dev", "info", "nav"])

    assert result.exit_code == 0
    assert "Module: nav" in result.output
    assert ".claude/skills/nav-avoidance-lane/SKILL.md" in result.output


def test_unknown_module_exits_nonzero() -> None:
    result = CliRunner().invoke(cli, ["dev", "info", "unknown"])

    assert result.exit_code != 0
    assert "unknown module" in result.output


def test_deploy_requires_module_unless_all() -> None:
    result = CliRunner().invoke(cli, ["jetson", "deploy", "--no-sync", "--no-build", "-y"])

    assert result.exit_code != 0
    assert "--module is required unless --all is set" in result.output
