from __future__ import annotations

from click.testing import CliRunner
from datetime import datetime, timezone, timedelta

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
    assert shell.jetson_hostname_hint() == "orin"


def test_doctor_warns_on_tailscale_ip_mismatch(monkeypatch, tmp_path):
    """If .env.local IP differs from auto-detected, doctor must surface mismatch."""
    monkeypatch.setenv("JETSON_TAILSCALE_IP", "100.99.99.99")  # wrong on purpose
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")

    fake_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}
    with patch("pawai_cli.network.find_jetson_peer", return_value=fake_peer):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])

    assert "mismatch" in result.output.lower() or "100.83.109.89" in result.output


def test_doctor_warns_when_no_jetson_peer(monkeypatch):
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "not-a-real-host")
    with patch("pawai_cli.network.find_jetson_peer", return_value=None):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])
    assert result.exit_code != 0
    assert "share link" in result.output.lower() or "tailscale" in result.output.lower()


def test_doctor_topology_block_printed(monkeypatch):
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    fake_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.network.find_jetson_peer", return_value=fake_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value="wlan0"), \
         patch("pawai_cli.network.jetson_go2_link",
               return_value={"iface": "eth0", "ip": "192.168.123.51/24"}), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=True), \
         patch("pawai_cli.network.gateway_8080_status", return_value="SKIP"):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])

    out = result.output
    assert "Network topology" in out
    assert "Jetson Tailscale" in out
    assert "Jetson internet route" in out and "wlan0" in out
    assert "Jetson Go2 link" in out and "eth0" in out
    assert "Jetson → Go2 ping" in out
    assert "Gateway 8080" in out and "SKIP" in out


def test_doctor_topology_flags_ethernet_hijack(monkeypatch):
    """If Jetson internet route uses eth0 (likely Go2 link stolen for uplink), warn."""
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    fake_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.network.find_jetson_peer", return_value=fake_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value="eth0"), \
         patch("pawai_cli.network.jetson_go2_link", return_value=None), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=False), \
         patch("pawai_cli.network.gateway_8080_status", return_value="SKIP"):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor"])

    assert "ethernet" in result.output.lower() or "go2" in result.output.lower()


def test_doctor_expect_demo_gateway_fail_is_blocking(monkeypatch):
    """When demo is expected, Gateway 8080 down must make doctor fail."""
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    fake_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.network.find_jetson_peer", return_value=fake_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value="wlan0"), \
         patch("pawai_cli.network.jetson_go2_link",
               return_value={"iface": "eth0", "ip": "192.168.123.51/24"}), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=True), \
         patch("pawai_cli.network.gateway_8080_status", return_value="FAIL"):
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--expect-demo"])

    assert result.exit_code != 0
    assert "Gateway 8080: FAIL" in result.output


import json as _json


def test_doctor_default_does_not_call_openrouter(monkeypatch):
    calls: list = []

    def fake_urlopen(req, **kwargs):
        calls.append(getattr(req, "full_url", str(req)))
        class R:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *a): return False
        return R()

    monkeypatch.setenv("OPENROUTER_KEY", "fake")
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    with patch("pawai_cli.network.find_jetson_peer", return_value=None), \
         patch("pawai_cli.main.urllib.request.urlopen", side_effect=fake_urlopen):
        runner = CliRunner()
        runner.invoke(cli, ["doctor"])
    assert calls == [], "Default doctor must not call OpenRouter API"


def test_doctor_deep_calls_openrouter(monkeypatch):
    posted: list = []

    class FakeResp:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def fake_urlopen(req, **kwargs):
        url = getattr(req, "full_url", str(req))
        posted.append(url)
        return FakeResp()

    monkeypatch.setenv("OPENROUTER_KEY", "fake")
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    with patch("pawai_cli.network.find_jetson_peer", return_value=None), \
         patch("pawai_cli.main.urllib.request.urlopen", side_effect=fake_urlopen):
        runner = CliRunner()
        runner.invoke(cli, ["doctor", "--deep"])
    assert any("openrouter" in u.lower() for u in posted)


def test_doctor_cache_second_invocation_fast(monkeypatch, tmp_path):
    monkeypatch.setenv("PAWAI_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")

    call_count: list = []

    def slow_find(hint):
        call_count.append(1)
        return None

    with patch("pawai_cli.network.find_jetson_peer", side_effect=slow_find):
        runner = CliRunner()
        runner.invoke(cli, ["doctor", "--cache", "30"])
        runner.invoke(cli, ["doctor", "--cache", "30"])

    # Second call should hit cache → only one real probe
    assert len(call_count) == 1, f"Expected 1 real call, got {len(call_count)}"


def test_last_deploy_payload_has_new_fields(monkeypatch, tmp_path):
    """Verify the JSON written to .pawai-last-deploy includes new schema fields."""
    from pawai_cli.main import _build_last_deploy_payload
    payload = _build_last_deploy_payload(module="brain", packages=["pawai_brain"],
                                          sync_method="rsync")
    assert "deployed_by" in payload
    assert "deployed_from_host" in payload
    assert "branch" in payload
    assert "git_sha" in payload
    assert "git_sha_full" in payload
    assert "dirty" in payload
    assert "module" in payload
    assert "packages" in payload
    assert isinstance(payload["dirty"], bool)


def test_doctor_fix_requires_prompt(monkeypatch, tmp_path):
    env_path = tmp_path / ".env.local"
    env_path.write_text("JETSON_TAILSCALE_IP=100.99.99.99\n")
    monkeypatch.setenv("PAWAI_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")

    fake_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}
    with patch("pawai_cli.network.find_jetson_peer", return_value=fake_peer):
        runner = CliRunner()
        # Default — should NOT mutate
        runner.invoke(cli, ["doctor"])
        assert "100.99.99.99" in env_path.read_text(), "Default doctor must not mutate .env.local"

        # --fix with 'n' answer — should not mutate
        runner.invoke(cli, ["doctor", "--fix"], input="n\n")
        assert "100.99.99.99" in env_path.read_text(), "Declined --fix must not mutate"

        # --fix with 'y' — should write detected IP
        runner.invoke(cli, ["doctor", "--fix"], input="y\n")
        assert "100.83.109.89" in env_path.read_text(), "--fix y must write detected IP"


# ──────────────── L2 tests ────────────────

def test_demo_start_prompts_on_cross_user_lock(monkeypatch):
    """If another user holds the lock, demo start prompts (does not silently override)."""
    from pawai_cli.lock import Lock
    other_lock = Lock(user="alice", host="alice-mac", branch="feat/x",
                      sha="abc", state="running",
                      start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    with patch("pawai_cli.lock.Lock.read", return_value=other_lock):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "start"], input="c\n")  # answer cancel
    assert "alice" in result.output.lower()
    assert "force" in result.output.lower() or "cancel" in result.output.lower()


def test_demo_start_y_does_not_take_over_other_lock(monkeypatch):
    """`-y` alone must not steal another user's lock."""
    from pawai_cli.lock import Lock
    other_lock = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                      state="running",
                      start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    with patch("pawai_cli.lock.Lock.read", return_value=other_lock):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "start", "-y"])
    # Should NOT proceed to starting demo
    assert result.exit_code != 0 or "alice" in result.output.lower()


def test_demo_start_force_takes_over(monkeypatch):
    """`--force` takes over another user's lock."""
    from pawai_cli.lock import Lock
    other_lock = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                      state="running",
                      start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    released: list = []

    with patch("pawai_cli.lock.Lock.read", return_value=other_lock), \
         patch("pawai_cli.lock.Lock.release", side_effect=lambda: released.append(1) or True), \
         patch("pawai_cli.lock.Lock.acquire", return_value=other_lock), \
         patch("pawai_cli.main._invoke_start_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.transition_to", return_value=True):
        runner = CliRunner()
        runner.invoke(cli, ["demo", "start", "--force"])

    assert released == [1], "Expected lock release on --force takeover"


def test_demo_stop_refuses_other_users_lock(monkeypatch):
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.lock.Lock.release", side_effect=lambda: released.append(1) or True):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "stop"])
    assert released == [], "demo stop must not release another user's lock by default"
    assert "alice" in result.output.lower()


def test_demo_stop_force_releases_other_lock(monkeypatch):
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.lock.Lock.release", side_effect=lambda: released.append(1) or True), \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0):
        runner = CliRunner()
        runner.invoke(cli, ["demo", "stop", "--force"])
    assert released == [1]
