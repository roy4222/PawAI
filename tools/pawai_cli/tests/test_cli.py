from __future__ import annotations

import platform
from click.testing import CliRunner
from datetime import datetime, timezone, timedelta
from pathlib import Path

from unittest.mock import patch

from pawai_cli.main import _install_hint_map, _ssh_config_has_host, cli
from pawai_cli.modules import MODULES, get_module
from pawai_cli import shell


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


def test_doctor_treats_offline_tailscale_peer_as_fail(monkeypatch):
    """When Tailscale peer is matched but online=False, doctor must fail."""
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    offline_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": False}

    with patch("pawai_cli.network.find_jetson_peer", return_value=offline_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value=None), \
         patch("pawai_cli.network.jetson_go2_link", return_value=None), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=False), \
         patch("pawai_cli.network.gateway_8080_status", return_value="SKIP"), \
         patch("pawai_cli.shell.run") as mock_run:
        from pawai_cli.shell import Result

        mock_run.return_value = Result(code=0, stdout="git version 2.40", stderr="")
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--cache", "0"])

    assert result.exit_code != 0
    assert "offline" in result.output.lower()
    assert "tailscale up" in result.output or "internet route" in result.output.lower()


def test_doctor_gateway_fails_when_running_lock_and_8080_down(monkeypatch):
    """If a running lock exists and Gateway 8080 is down, severity is FAIL."""
    from pawai_cli.lock import Lock

    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    fake_lock = Lock(
        user="alice", host="alice-mac", branch="main", sha="abc1234",
        state="running",
        start_time="2026-05-13T10:00:00+00:00",
        demo_mode="full", tmux_session="demo", lane="brain",
    )
    online_peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.network.find_jetson_peer", return_value=online_peer), \
         patch("pawai_cli.network.jetson_internet_iface", return_value="wlan0"), \
         patch(
             "pawai_cli.network.jetson_go2_link",
             return_value={"iface": "eth0", "ip": "192.168.123.51/24"},
         ), \
         patch("pawai_cli.network.jetson_ping_go2", return_value=True), \
         patch("pawai_cli.lock.Lock.read", return_value=fake_lock), \
         patch("pawai_cli.network.gateway_8080_status", return_value="FAIL") as mock_gw, \
         patch("pawai_cli.shell.run") as mock_run:
        from pawai_cli.shell import Result

        mock_run.return_value = Result(code=0, stdout="git version 2.40\nOK", stderr="")
        runner = CliRunner()
        result = runner.invoke(cli, ["doctor", "--cache", "0"])

    assert result.exit_code != 0
    assert "Gateway 8080: FAIL" in result.output
    assert mock_gw.call_args.kwargs["lock_state"] == "running"


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
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0) as cleanup, \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True), \
         patch("pawai_cli.lock.Lock.acquire", return_value=other_lock), \
         patch("pawai_cli.main._invoke_start_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        runner = CliRunner()
        runner.invoke(cli, ["demo", "start", "--force"])

    assert cleanup.called
    # The take-over MUST target the OTHER user's lock, not our own — proves
    # we use release_if_owned(existing.user, existing.host).
    assert ("alice", "alice-mac") in released, \
        f"Expected release_if_owned to target alice's lock, got {released}"


def test_demo_start_force_cleans_old_nav_lane_before_takeover(monkeypatch):
    from pawai_cli.lock import Lock

    other_lock = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                      state="running",
                      start_time=datetime.now(timezone.utc).isoformat(),
                      lane="nav_capability", tmux_session="nav-cap-demo")
    new_lock = Lock(user="bob", host="bob-mac", branch="main", sha="b",
                    state="starting",
                    start_time=datetime.now(timezone.utc).isoformat())
    calls: list[str] = []

    monkeypatch.setenv("USER", "bob")
    with patch("pawai_cli.lock.Lock.read", return_value=other_lock), \
         patch("pawai_cli.main._invoke_nav_cleanup_sh",
               side_effect=lambda: calls.append("nav_cleanup") or 0), \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: calls.append("release") or True), \
         patch("pawai_cli.lock.Lock.acquire",
               side_effect=lambda **kwargs: calls.append("acquire") or new_lock), \
         patch("pawai_cli.main._invoke_start_sh",
               side_effect=lambda **kwargs: calls.append("brain_start") or 0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "start", "--force"])

    assert result.exit_code == 0
    assert calls[:3] == ["nav_cleanup", "release", "acquire"]


def test_demo_stop_refuses_other_users_lock(monkeypatch):
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True):
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
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True), \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0):
        runner = CliRunner()
        runner.invoke(cli, ["demo", "stop", "--force"])
    # Force takeover MUST target the other user's lock — never bob's own.
    assert released == [("alice", "alice-mac")]


def test_demo_stop_routes_nav_lock_to_nav_cleanup(monkeypatch):
    from pawai_cli.lock import Lock

    nav_lock = Lock(user="bob", host="bob-mac", branch="x", sha="a",
                    state="running",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    lane="nav_capability", tmux_session="nav-cap-demo")
    monkeypatch.setenv("USER", "bob")
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=nav_lock), \
         patch("pawai_cli.main.platform.node", return_value="bob-mac"), \
         patch("pawai_cli.main._invoke_nav_cleanup_sh", return_value=0) as nav_cleanup, \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0) as brain_cleanup, \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "stop"])
    assert result.exit_code == 0
    assert nav_cleanup.called
    assert not brain_cleanup.called
    assert released == [("bob", "bob-mac")]


def test_demo_stop_own_stale_lock_releases_without_force(monkeypatch):
    from pawai_cli.lock import Lock

    own_stale = Lock(
        user="lubaiyu", host="Roy422deMacBook-Pro.local",
        branch="main", sha="abc1234",
        state="running",
        start_time=(datetime.now(timezone.utc) - timedelta(hours=5)).isoformat(),
        demo_mode="full", tmux_session="demo", lane="brain",
    )

    with patch("pawai_cli.lock.Lock.read", return_value=own_stale), \
         patch("pawai_cli.lock.Lock.release_if_owned", return_value=True) as mock_rel, \
         patch("pawai_cli.main._cleanup_for_lock", return_value=0), \
         patch("pawai_cli.main.platform.node", return_value="Roy422deMacBook-Pro.local"):
        monkeypatch.setenv("USER", "lubaiyu")
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "stop"])

    assert result.exit_code == 0
    assert "Reclaiming your own stale" in result.output
    mock_rel.assert_called_once_with(user="lubaiyu", host="Roy422deMacBook-Pro.local")


def test_health_brain_passes_jetson_host_env():
    captured_env = {}

    def fake_stream(argv, cwd=None, env=None):
        captured_env.update(env or {})
        return 0

    with patch("pawai_cli.main.shell.stream", side_effect=fake_stream), \
         patch("pawai_cli.main.shell.jetson_host", return_value="jetson"), \
         patch("pawai_cli.network.find_jetson_peer",
               return_value={"hostname": "jetson", "ip": "100.83.109.89", "online": True}):
        runner = CliRunner()
        result = runner.invoke(cli, ["health", "brain"])

    assert result.exit_code == 0
    assert captured_env.get("JETSON_HOST") == "jetson"
    assert captured_env.get("JETSON_TAILSCALE_IP") == "100.83.109.89"


def _reachable_live_status():
    from pawai_cli.status import LiveStatus

    return LiveStatus(tmux="", ros_nodes="", git="", last_deploy="", reachable=True)


def test_status_shows_lock_state(monkeypatch):
    from pawai_cli.lock import Lock
    lk = Lock(user="alice", host="alice-mac", branch="feat/x", sha="abc",
              state="running",
              start_time=datetime.now(timezone.utc).isoformat())
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status.Lock.read", return_value=lk), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "alice" in result.output.lower()
    assert "running" in result.output.lower()


def test_status_shows_nav_capability_block(monkeypatch):
    from pawai_cli.lock import Lock
    from pawai_cli.status import NavCapabilityStatus

    lk = Lock(user="alice", host="alice-mac", branch="feat/nav", sha="abc",
              state="running",
              start_time=datetime.now(timezone.utc).isoformat(),
              lane="nav_capability", tmux_session="nav-cap-demo")
    nav = NavCapabilityStatus(
        tmux_running=True,
        scan_publishers="1",
        nav_ready="data: true",
        depth_clear="data: true",
        reactive_status="mode: progressive",
        cmd_vel_joy_publishers="0",
    )
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status.Lock.read", return_value=lk), \
         patch("pawai_cli.status.collect_nav_capability_status", return_value=nav), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]):
        runner = CliRunner()
        result = runner.invoke(cli, ["status", "--short"])
    assert "nav capability" in result.output.lower()
    assert "/cmd_vel_joy publishers: 0" in result.output


def test_status_shows_branch_mismatch(monkeypatch, tmp_path):
    last_deploy = {
        "deployed_by": "alice", "branch": "feat/old",
        "git_sha": "111", "git_sha_full": "1" * 40, "dirty": False,
        "module": "brain", "packages": ["pawai_brain"],
        "when": "2026-05-13T08:00:00+00:00", "sync_method": "rsync",
    }
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status._read_last_deploy_remote", return_value=last_deploy), \
         patch("pawai_cli.status._current_branch", return_value="feat/new"), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "mismatch" in result.output.lower() or "feat/old" in result.output


def test_status_shows_stale_running_warning(monkeypatch):
    from pawai_cli.lock import Lock
    from datetime import timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    lk = Lock(user="alice", host="h", branch="b", sha="s",
              state="running", start_time=old)
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status.Lock.read", return_value=lk), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "stale" in result.output.lower()


# ─── Go2 driver process detection (P0) ─────────────────────────────────────

def test_collect_go2_drivers_parses_ps_output():
    from pawai_cli.status import collect_go2_drivers
    from pawai_cli.shell import Result
    sample = (
        "12345 jetson   pts/0    Wed May 14 19:30:01 2026 /usr/bin/python3 "
        "/opt/ros/humble/lib/go2_robot_sdk/go2_driver_node\n"
        "12350 jetson   pts/0    Wed May 14 19:30:01 2026 "
        "ros2 launch go2_robot_sdk robot.launch.py\n"
    )
    with patch("pawai_cli.status.shell.run_remote",
               return_value=Result(code=0, stdout=sample, stderr="")):
        procs = collect_go2_drivers()
    assert len(procs) == 2
    assert procs[0].pid == 12345
    assert procs[0].user == "jetson"
    assert procs[0].tty == "pts/0"
    assert procs[0].started == "Wed May 14 19:30:01 2026"
    assert "go2_driver_node" in procs[0].cmd
    assert procs[1].pid == 12350


def test_collect_go2_drivers_empty_when_no_match():
    from pawai_cli.status import collect_go2_drivers
    from pawai_cli.shell import Result
    with patch("pawai_cli.status.shell.run_remote",
               return_value=Result(code=0, stdout="", stderr="")):
        assert collect_go2_drivers() == []


def test_status_warns_when_driver_running_without_lock():
    from pawai_cli.status import Go2DriverProcess
    procs = [Go2DriverProcess(
        pid=12345, user="kirk7", tty="pts/0",
        started="Wed May 14 19:30:01 2026",
        cmd="/usr/bin/python3 .../go2_driver_node",
    )]
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=procs):
        result = CliRunner().invoke(cli, ["status"])
    assert "pid=12345" in result.output
    assert "kirk7" in result.output
    assert "NO demo lock" in result.output


def test_status_does_not_warn_on_user_mismatch_when_lock_present():
    """proc.user is always the Jetson-side process owner (typically `jetson`)
    whereas lk.user is the laptop user. Comparing them produces false alarms,
    so we must NOT emit a mismatch warning when a lock is present."""
    from pawai_cli.lock import Lock
    from pawai_cli.status import Go2DriverProcess
    lk = Lock(user="alice", host="alice-mac", branch="main", sha="abc",
              state="running",
              start_time=datetime.now(timezone.utc).isoformat())
    procs = [Go2DriverProcess(
        pid=12345, user="jetson", tty="pts/0",
        started="Wed May 14 19:30:01 2026",
        cmd="/usr/bin/python3 .../go2_driver_node",
    )]
    with patch("pawai_cli.status.collect", return_value=_reachable_live_status()), \
         patch("pawai_cli.status.Lock.read", return_value=lk), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=procs):
        result = CliRunner().invoke(cli, ["status"])
    # Driver is listed but no mismatch warning is emitted.
    assert "pid=12345" in result.output
    assert "lock owner is" not in result.output
    assert "driver user(s)" not in result.output


def test_status_short_skips_ros_node_list_ssh_call():
    """status --short must not invoke `ros2 node list` over SSH."""
    from pawai_cli import status as status_mod
    from pawai_cli.shell import Result

    calls = []

    def fake_run_remote(cmd, timeout=None):
        calls.append(cmd)
        return Result(code=0, stdout="", stderr="")

    with patch("pawai_cli.status.shell.run_remote", side_effect=fake_run_remote), \
         patch("pawai_cli.status.Lock.read", return_value=None):
        status_mod.collect(short=True)

    ros_calls = [c for c in calls if "ros2 node list" in c]
    assert ros_calls == [], f"unexpected ros2 calls under --short: {ros_calls}"


def test_deploy_prompts_on_active_other_lock(monkeypatch):
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    monkeypatch.setenv("USER", "bob")
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.main._do_rsync_and_build", return_value=0):
        runner = CliRunner()
        result = runner.invoke(cli, ["jetson", "deploy", "--module", "brain"], input="c\n")
    assert "alice" in result.output.lower()


def test_jetson_deploy_rsync_excludes_env_and_ssh(tmp_path):
    """rsync invocation must include repo-relative excludes for secrets."""
    from pawai_cli import main as cli_main
    from pawai_cli.shell import Result

    captured_argv = []

    def fake_stream(argv, cwd=None, env=None):
        captured_argv.append(list(argv))
        return 0

    with patch("pawai_cli.main.shell.stream", side_effect=fake_stream), \
         patch("pawai_cli.main.shell.run_remote", return_value=Result(0, "", "")), \
         patch("pawai_cli.main.shell.jetson_host", return_value="jetson"), \
         patch("pawai_cli.main.shell.jetson_repo", return_value="/home/jetson/elder_and_dog"), \
         patch("pathlib.Path.home", return_value=tmp_path):
        code, method = cli_main._do_rsync_and_build(
            root=Path("/tmp/repo"),
            packages=[],
            no_sync=False,
            no_build=True,
            module_key="brain",
        )

    assert code == 0
    assert method == "rsync"
    rsync_argv = next((a for a in captured_argv if a and a[0] == "rsync"), None)
    assert rsync_argv is not None, f"no rsync invocation seen: {captured_argv}"
    excludes = [arg for arg in rsync_argv if arg.startswith("--exclude=")]
    required = {
        "--exclude=.env",
        "--exclude=.env.*",
        "--exclude=.env.local",
        "--exclude=.ssh/",
    }
    missing = required - set(excludes)
    assert not missing, f"missing rsync excludes: {missing}"


def test_invoke_start_sh_injects_jetson_tailscale_ip(monkeypatch):
    """demo start wrapper should pass JETSON_TAILSCALE_IP to start.sh env."""
    from pawai_cli import main as cli_main

    captured_env = {}

    def fake_stream(argv, cwd=None, env=None):
        captured_env.update(env or {})
        return 0

    monkeypatch.delenv("JETSON_TAILSCALE_IP", raising=False)
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "jetson")
    peer = {"hostname": "jetson", "ip": "100.83.109.89", "online": True}

    with patch("pawai_cli.main.shell.stream", side_effect=fake_stream), \
         patch("pawai_cli.network.find_jetson_peer", return_value=peer):
        assert cli_main._invoke_start_sh(no_studio=False, brain_only=False) == 0

    assert captured_env.get("JETSON_TAILSCALE_IP") == "100.83.109.89"


def test_demo_start_nav_capability_invokes_nav_start(monkeypatch):
    from pawai_cli.lock import Lock

    acquired = Lock(user="bob", host="bob-mac", branch="main", sha="abc",
                    state="starting",
                    start_time=datetime.now(timezone.utc).isoformat(),
                    lane="nav_capability", tmux_session="nav-cap-demo")
    acquire_kwargs: dict = {}

    def fake_acquire(**kwargs):
        acquire_kwargs.update(kwargs)
        return acquired

    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.lock.Lock.acquire", side_effect=fake_acquire), \
         patch("pawai_cli.main._invoke_nav_start_sh", return_value=0) as nav_start, \
         patch("pawai_cli.main._invoke_start_sh", return_value=0) as brain_start, \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        runner = CliRunner()
        result = runner.invoke(cli, ["demo", "start", "--nav", "capability"])

    assert result.exit_code == 0
    assert nav_start.called
    assert not brain_start.called
    assert acquire_kwargs["lane"] == "nav_capability"
    assert acquire_kwargs["tmux_session"] == "nav-cap-demo"


def test_demo_start_nav_capability_rejects_brain_only():
    runner = CliRunner()
    result = runner.invoke(cli, ["demo", "start", "--nav", "capability", "--brain-only"])
    assert result.exit_code == 2
    assert "brain-only" in result.output


def test_demo_start_rejects_invalid_nav_modes():
    runner = CliRunner()
    for mode in ["detour", "fallback", "amcl", "mapping", "bogus"]:
        result = runner.invoke(cli, ["demo", "start", "--nav", mode])
        assert result.exit_code == 2
        assert "--nav" in result.output


# ──────────────── L3 tests ────────────────

def test_pawai_docs_brain_resolves_path():
    runner = CliRunner()
    result = runner.invoke(cli, ["docs", "brain"])
    assert "architecture/0511" in result.output
    assert "brain" in result.output
    assert result.exit_code == 0


def test_pawai_docs_unknown_lists_valid():
    runner = CliRunner()
    result = runner.invoke(cli, ["docs", "zzz-not-a-module"])
    assert result.exit_code != 0
    assert "brain" in result.output and "face" in result.output  # the list


def test_pawai_docs_onboarding_alias():
    runner = CliRunner()
    result = runner.invoke(cli, ["docs", "onboarding"])
    assert "team-onboarding" in result.output


def test_contract_check_runs_local_when_script_exists(tmp_path, monkeypatch):
    # Stage a fake repo root with the contract script
    script = tmp_path / "scripts/ci/check_topic_contracts.py"
    script.parent.mkdir(parents=True)
    script.write_text("import sys; sys.exit(0)")
    monkeypatch.setenv("PAWAI_REPO_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["contract", "check"])
    assert result.exit_code == 0


def test_contract_check_explicit_fallback_when_script_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PAWAI_REPO_ROOT", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(cli, ["contract", "check"])
    assert result.exit_code != 0
    assert "check_topic_contracts.py" in result.output
    assert "interaction_contract.md" in result.output  # explicit fallback ref


def test_contract_check_jetson_uses_ssh(monkeypatch):
    monkeypatch.setenv("PAWAI_REPO_ROOT", "/nonexistent")  # force jetson path
    with patch("pawai_cli.main.shell.run_remote",
               return_value=shell.Result(code=0, stdout="ok", stderr="")) \
         as mocked:
        runner = CliRunner()
        runner.invoke(cli, ["contract", "check", "--jetson"])
    assert mocked.called


# ─── pawai net wifi MVP ──────────────────────────────────────────────────

def test_net_wifi_list_invokes_network_function():
    from pawai_cli.network import WifiNetwork

    fake_networks = [
        WifiNetwork(ssid="LM306", signal=87, security="WPA2", in_use=True),
        WifiNetwork(ssid="FJU-5GHz", signal=65, security="WPA2 802.1X", in_use=False),
    ]
    with patch("pawai_cli.network.wifi_list", return_value=fake_networks):
        runner = CliRunner()
        result = runner.invoke(cli, ["net", "wifi", "list"])
    assert result.exit_code == 0
    assert "LM306" in result.output
    assert "FJU-5GHz" in result.output
    assert "✓" in result.output  # in_use marker


def test_net_wifi_connect_shows_current_status_and_confirms():
    from pawai_cli.network import WifiStatus

    captured = {}

    def fake_connect(ssid, password):
        captured["ssid"] = ssid
        captured["password"] = password
        return True, f"✓ Connected to '{ssid}'."

    current = WifiStatus(ssid="OldNet", iface="wlp1s0", ip="10.0.0.5",
                         default_route_via_wifi=True)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_connect", side_effect=fake_connect):
        runner = CliRunner()
        # confirm "y" + password "secret-pw"
        result = runner.invoke(cli, ["net", "wifi", "connect", "LM306"],
                               input="y\nsecret-pw\n")
    assert result.exit_code == 0
    assert captured == {"ssid": "LM306", "password": "secret-pw"}
    # Current-state disclosure must appear
    assert "OldNet" in result.output
    assert "drop SSH" in result.output
    # Password must not appear in CLI output (hide_input=True)
    assert "secret-pw" not in result.output


def test_net_wifi_connect_aborts_on_no_confirm():
    from pawai_cli.network import WifiStatus

    current = WifiStatus(ssid="OldNet", iface="wlp1s0", ip="10.0.0.5",
                         default_route_via_wifi=True)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_connect") as mock_connect:
        runner = CliRunner()
        result = runner.invoke(cli, ["net", "wifi", "connect", "LM306"],
                               input="n\n")
    assert result.exit_code == 0
    assert "Aborted" in result.output
    mock_connect.assert_not_called()


def test_net_wifi_connect_yes_flag_skips_confirm():
    from pawai_cli.network import WifiStatus

    current = WifiStatus(ssid="OldNet", iface="wlp1s0", ip="10.0.0.5",
                         default_route_via_wifi=True)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_connect",
               return_value=(True, "✓ Connected to 'LM306'.")) as mock_connect:
        runner = CliRunner()
        result = runner.invoke(
            cli, ["net", "wifi", "connect", "LM306", "--yes"],
            input="secret-pw\n",
        )
    assert result.exit_code == 0
    mock_connect.assert_called_once()


def test_net_wifi_connect_propagates_failure_exit_code():
    from pawai_cli.network import WifiStatus

    current = WifiStatus(ssid=None, iface=None, ip=None,
                         default_route_via_wifi=False)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_connect",
               return_value=(False, "✗ Wi-Fi password rejected")):
        runner = CliRunner()
        result = runner.invoke(cli, ["net", "wifi", "connect", "LM306", "-y"],
                               input="bad\n")
    assert result.exit_code == 1
    assert "rejected" in result.output


def test_net_wifi_forget_warns_when_deleting_active_profile():
    from pawai_cli.network import WifiStatus

    current = WifiStatus(ssid="LM306", iface="wlp1s0", ip="192.168.0.113",
                         default_route_via_wifi=True)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_forget") as mock_forget:
        runner = CliRunner()
        result = runner.invoke(cli, ["net", "wifi", "forget", "LM306"],
                               input="n\n")
    assert result.exit_code == 0
    assert "CURRENTLY ACTIVE" in result.output
    assert "strand" in result.output.lower()
    mock_forget.assert_not_called()


def test_net_wifi_forget_proceeds_with_yes_flag():
    from pawai_cli.network import WifiStatus

    current = WifiStatus(ssid="LM306", iface="wlp1s0", ip="192.168.0.113",
                         default_route_via_wifi=True)
    with patch("pawai_cli.network.wifi_status", return_value=current), \
         patch("pawai_cli.network.wifi_forget",
               return_value=(True, "✓ Forgot Wi-Fi profile 'OldNet'.")) as mock_forget:
        runner = CliRunner()
        result = runner.invoke(cli, ["net", "wifi", "forget", "OldNet", "-y"])
    assert result.exit_code == 0
    mock_forget.assert_called_once_with("OldNet")



# ─── P1: orphan Go2 driver preflight on `demo start` ──────────────────────

def _orphan_proc(pid=12345, user="jetson"):
    from pawai_cli.status import Go2DriverProcess
    return Go2DriverProcess(
        pid=pid, user=user, tty="pts/0",
        started="Wed May 14 19:30:01 2026",
        cmd="/usr/bin/python3 .../go2_driver_node",
    )


def test_demo_start_orphan_driver_blocks_with_dash_y(monkeypatch):
    """`-y` must NOT auto-clean orphan drivers — that would let CI / new users
    silently kill someone else's manual session. Exit 2 with hint."""
    monkeypatch.setenv("USER", "bob")
    cleanup_called: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.main.collect_go2_drivers", return_value=[_orphan_proc()],
               create=True), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[_orphan_proc()]), \
         patch("pawai_cli.main._invoke_cleanup_sh",
               side_effect=lambda: cleanup_called.append(1) or 0), \
         patch("pawai_cli.lock.Lock.acquire") as acquire, \
         patch("pawai_cli.main._invoke_start_sh", return_value=0):
        result = CliRunner().invoke(cli, ["demo", "start", "-y"])
    assert result.exit_code == 2
    assert "orphan" in result.output.lower() or "-y" in result.output
    assert cleanup_called == []
    assert not acquire.called


def test_demo_start_orphan_driver_force_cleans_and_proceeds(monkeypatch):
    monkeypatch.setenv("USER", "bob")
    calls: list = []
    from pawai_cli.lock import Lock
    new_lock = Lock(user="bob", host="bob-mac", branch="main", sha="b",
                    state="starting",
                    start_time=datetime.now(timezone.utc).isoformat())
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[_orphan_proc()]), \
         patch("pawai_cli.main._invoke_cleanup_sh",
               side_effect=lambda: calls.append("cleanup") or 0), \
         patch("pawai_cli.lock.Lock.acquire",
               side_effect=lambda **kw: calls.append("acquire") or new_lock), \
         patch("pawai_cli.main._invoke_start_sh",
               side_effect=lambda **kw: calls.append("start") or 0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        result = CliRunner().invoke(cli, ["demo", "start", "--force"])
    assert result.exit_code == 0, result.output
    assert calls == ["cleanup", "acquire", "start"]


def test_demo_start_orphan_driver_interactive_yes_cleans(monkeypatch):
    monkeypatch.setenv("USER", "bob")
    calls: list = []
    from pawai_cli.lock import Lock
    new_lock = Lock(user="bob", host="bob-mac", branch="main", sha="b",
                    state="starting",
                    start_time=datetime.now(timezone.utc).isoformat())
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[_orphan_proc()]), \
         patch("pawai_cli.main._invoke_cleanup_sh",
               side_effect=lambda: calls.append("cleanup") or 0), \
         patch("pawai_cli.lock.Lock.acquire",
               side_effect=lambda **kw: calls.append("acquire") or new_lock), \
         patch("pawai_cli.main._invoke_start_sh",
               side_effect=lambda **kw: calls.append("start") or 0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        result = CliRunner().invoke(cli, ["demo", "start"], input="y\n")
    assert result.exit_code == 0, result.output
    assert calls == ["cleanup", "acquire", "start"]


def test_demo_start_orphan_driver_interactive_no_aborts(monkeypatch):
    monkeypatch.setenv("USER", "bob")
    calls: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[_orphan_proc()]), \
         patch("pawai_cli.main._invoke_cleanup_sh",
               side_effect=lambda: calls.append("cleanup") or 0), \
         patch("pawai_cli.lock.Lock.acquire") as acquire:
        result = CliRunner().invoke(cli, ["demo", "start"], input="n\n")
    assert result.exit_code == 0
    assert calls == []
    assert not acquire.called


def test_demo_start_no_orphan_check_when_lock_present(monkeypatch):
    """Spec: when a lock exists, do NOT run orphan check — we can't tell if the
    drivers belong to the lock owner without a tracked session id."""
    from pawai_cli.lock import Lock
    monkeypatch.setenv("USER", "bob")
    own_lock = Lock(user="bob", host=platform.node(), branch="main", sha="a",
                    state="running",
                    start_time=datetime.now(timezone.utc).isoformat())
    orphan_check_called: list = []

    def _track_orphans():
        orphan_check_called.append(1)
        return [_orphan_proc()]

    with patch("pawai_cli.lock.Lock.read", return_value=own_lock), \
         patch("pawai_cli.status.collect_go2_drivers", side_effect=_track_orphans), \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.release", return_value=True), \
         patch("pawai_cli.lock.Lock.acquire", return_value=own_lock), \
         patch("pawai_cli.main._invoke_start_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=True):
        result = CliRunner().invoke(cli, ["demo", "start"])
    assert result.exit_code == 0, result.output
    assert orphan_check_called == [], "orphan check must not run when lock present"


# ─── Race-fix tests for lock owner guard ──────────────────────────────────

def test_demo_start_failure_uses_release_if_owned_not_bare_release(monkeypatch):
    """If start.sh fails, we must NOT bare-release: a force-takeover may have
    replaced our lock during the start.sh window, and bare release would
    delete the new owner's lock."""
    from pawai_cli.lock import Lock
    monkeypatch.setenv("USER", "bob")
    lk = Lock(user="bob", host=platform.node(), branch="main", sha="b",
              state="starting",
              start_time=datetime.now(timezone.utc).isoformat())
    released: list = []
    bare_release_called: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]), \
         patch("pawai_cli.lock.Lock.acquire", return_value=lk), \
         patch("pawai_cli.main._invoke_start_sh", return_value=7), \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True), \
         patch("pawai_cli.lock.Lock.release",
               side_effect=lambda: bare_release_called.append(1) or True):
        result = CliRunner().invoke(cli, ["demo", "start"])
    assert result.exit_code == 7
    assert released == [("bob", platform.node())], \
        "start.sh failure must call release_if_owned(self), not bare release"
    assert bare_release_called == [], "bare Lock.release() must not be invoked"


def test_demo_start_transition_failure_does_not_corrupt_others_lock():
    """If our lock got force-taken during start.sh, transition_if_owned returns
    False; demo_start must surface this loudly (exit 2) rather than overwriting
    whoever's lock is currently present."""
    from pawai_cli.lock import Lock
    lk = Lock(user="bob", host="bob-mac", branch="main", sha="b",
              state="starting",
              start_time=datetime.now(timezone.utc).isoformat())
    with patch("pawai_cli.lock.Lock.read", return_value=None), \
         patch("pawai_cli.status.collect_go2_drivers", return_value=[]), \
         patch("pawai_cli.lock.Lock.acquire", return_value=lk), \
         patch("pawai_cli.main._invoke_start_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.transition_if_owned", return_value=False):
        result = CliRunner().invoke(cli, ["demo", "start"])
    assert result.exit_code == 2
    assert "taken over during startup" in result.output.lower() \
        or "not marking running" in result.output.lower()


def test_demo_stop_force_keeps_lock_when_cleanup_fails():
    """If cleanup fails, lock MUST remain on Jetson. Otherwise the team loses
    the only record of who was running, and ends up with 'no lock + tmux still
    alive' which is the worst state."""
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=3), \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True), \
         patch("pawai_cli.lock.Lock.release") as bare_release:
        result = CliRunner().invoke(cli, ["demo", "stop", "--force"])
    assert result.exit_code == 3
    assert released == [], "Cleanup failure must NOT release the lock"
    assert not bare_release.called
    assert "kept on Jetson" in result.output or "Cleanup failed" in result.output


def test_demo_stop_force_releases_lock_only_when_cleanup_succeeds():
    """Happy path: cleanup OK → release_if_owned(existing.user, existing.host)."""
    from pawai_cli.lock import Lock
    other = Lock(user="alice", host="alice-mac", branch="x", sha="a",
                 state="running",
                 start_time=datetime.now(timezone.utc).isoformat())
    released: list = []
    with patch("pawai_cli.lock.Lock.read", return_value=other), \
         patch("pawai_cli.main._invoke_cleanup_sh", return_value=0), \
         patch("pawai_cli.lock.Lock.release_if_owned",
               side_effect=lambda user, host: released.append((user, host)) or True):
        result = CliRunner().invoke(cli, ["demo", "stop", "--force"])
    assert result.exit_code == 0
    assert released == [("alice", "alice-mac")]
