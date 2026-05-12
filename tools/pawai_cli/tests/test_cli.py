from __future__ import annotations

from click.testing import CliRunner

from unittest.mock import patch

from pawai_cli.main import _install_hint_map, _ssh_config_has_host, cli
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


def test_ssh_config_matches_exact_alias() -> None:
    cfg = "Host jetson-nano\n    HostName 100.83.109.89\n"
    assert _ssh_config_has_host(cfg, "jetson-nano")
    # substring should NOT match — this was the original bug
    assert not _ssh_config_has_host(cfg, "jetson")


def test_ssh_config_matches_multi_host_line() -> None:
    cfg = "Host alpha beta gamma\n    HostName 10.0.0.1\n"
    assert _ssh_config_has_host(cfg, "alpha")
    assert _ssh_config_has_host(cfg, "beta")
    assert _ssh_config_has_host(cfg, "gamma")
    assert not _ssh_config_has_host(cfg, "delta")


def test_ssh_config_ignores_comments_and_case() -> None:
    cfg = "# Host jetson\nhost JETSON\n    HostName 10.0.0.1\n"
    # case-insensitive Host keyword, but host name match is case-sensitive
    assert _ssh_config_has_host(cfg, "JETSON")
    # commented-out line should not count
    assert not _ssh_config_has_host(cfg, "jetson")


def test_install_hint_linux_uses_nodejs_npm() -> None:
    # Ubuntu/Debian: `apt install node` lands on Amateur Packet Radio, not Node.js.
    with patch("pawai_cli.main.platform.system", return_value="Linux"):
        hints = _install_hint_map()
    assert hints["node"] == "sudo apt install nodejs npm"
    assert hints["npm"] == "sudo apt install nodejs npm"
    assert hints["tmux"] == "sudo apt install tmux"


def test_install_hint_darwin_uses_brew() -> None:
    with patch("pawai_cli.main.platform.system", return_value="Darwin"):
        hints = _install_hint_map()
    assert hints["node"] == "brew install node"
    assert hints["tmux"] == "brew install tmux"


def test_ssh_config_no_wildcard_match() -> None:
    cfg = "Host *\n    User foo\n"
    # wildcard should not be treated as matching a specific alias
    assert not _ssh_config_has_host(cfg, "jetson")


def test_deploy_requires_module_unless_all() -> None:
    result = CliRunner().invoke(cli, ["jetson", "deploy", "--no-sync", "--no-build", "-y"])

    assert result.exit_code != 0
    assert "--module is required unless --all is set" in result.output


def test_jetson_hostname_hint_env(monkeypatch):
    from pawai_cli import shell
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "orin")
    assert shell.jetson_hostname_hint() == "orin"


def test_jetson_hostname_hint_default(monkeypatch):
    from pawai_cli import shell
    monkeypatch.delenv("JETSON_HOSTNAME_HINT", raising=False)
    assert shell.jetson_hostname_hint() == "jetson"
