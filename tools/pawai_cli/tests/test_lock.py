from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from pawai_cli.lock import (
    Lock,
    is_stale,
)
from pawai_cli.shell import Result


def _ok(stdout: str = "") -> Result:
    return Result(code=0, stdout=stdout, stderr="")


def _fail() -> Result:
    return Result(code=1, stdout="", stderr="")


def test_lock_read_returns_none_when_absent():
    with patch("pawai_cli.lock.shell.run_remote", return_value=_fail()):
        assert Lock.read() is None


def test_lock_read_parses_json():
    payload = '{"user":"alice","state":"running","branch":"main","start_time":"2026-05-13T08:00:00+08:00","host":"alice-mac","sha":"abc","demo_mode":"full","tmux_session":"demo"}'
    with patch("pawai_cli.lock.shell.run_remote", return_value=_ok(payload)):
        lk = Lock.read()
    assert lk is not None
    assert lk.user == "alice"
    assert lk.state == "running"
    assert lk.lane == "brain"
    assert lk.tmux_session == "demo"


def test_lock_read_defaults_old_json_without_lane_or_tmux():
    payload = '{"user":"alice","state":"running","branch":"main","start_time":"2026-05-13T08:00:00+08:00","host":"alice-mac","sha":"abc"}'
    with patch("pawai_cli.lock.shell.run_remote", return_value=_ok(payload)):
        lk = Lock.read()
    assert lk is not None
    assert lk.lane == "brain"
    assert lk.tmux_session == "demo"


def test_is_stale_starting_over_10min():
    old = datetime.now(timezone.utc) - timedelta(minutes=11)
    lk = Lock(user="x", host="h", branch="b", sha="s", state="starting",
              start_time=old.isoformat(), demo_mode="full", tmux_session="demo")
    assert is_stale(lk) == "starting"


def test_is_stale_running_over_4hr():
    old = datetime.now(timezone.utc) - timedelta(hours=4, minutes=30)
    lk = Lock(user="x", host="h", branch="b", sha="s", state="running",
              start_time=old.isoformat(), demo_mode="full", tmux_session="demo")
    assert is_stale(lk) == "running"


def test_is_stale_fresh_running_not_stale():
    fresh = datetime.now(timezone.utc) - timedelta(minutes=30)
    lk = Lock(user="x", host="h", branch="b", sha="s", state="running",
              start_time=fresh.isoformat(), demo_mode="full", tmux_session="demo")
    assert is_stale(lk) is None


def test_acquire_no_retry_on_exit_17(monkeypatch):
    """exit 17 means lock exists; do not retry."""
    from pawai_cli.shell import Result
    calls: list = []
    def stub(cmd, timeout=None):
        calls.append(cmd)
        return Result(code=17, stdout="", stderr="")
    monkeypatch.setattr("pawai_cli.lock.shell.run_remote", stub)
    monkeypatch.setattr("pawai_cli.lock.time.sleep", lambda s: None)
    result = Lock.acquire(user="u", host="h", branch="b", sha="s")
    assert result is None
    assert len(calls) == 1, f"Expected 1 call (no retry on 17), got {len(calls)}"


def test_acquire_retries_on_transient_failure(monkeypatch):
    """Non-17 non-zero exit code → retry up to 3× total."""
    from pawai_cli.shell import Result
    calls: list = []
    def stub(cmd, timeout=None):
        calls.append(cmd)
        return Result(code=1, stdout="", stderr="flock contention")
    monkeypatch.setattr("pawai_cli.lock.shell.run_remote", stub)
    monkeypatch.setattr("pawai_cli.lock.time.sleep", lambda s: None)
    result = Lock.acquire(user="u", host="h", branch="b", sha="s")
    assert result is None
    assert len(calls) == 3, f"Expected 3 attempts on transient failure, got {len(calls)}"


def test_acquire_succeeds_on_second_try(monkeypatch):
    """If first attempt is transient failure, second succeeds → lock returned."""
    from pawai_cli.shell import Result
    sequence = [Result(code=1, stdout="", stderr=""), Result(code=0, stdout="", stderr="")]
    def stub(cmd, timeout=None):
        return sequence.pop(0)
    monkeypatch.setattr("pawai_cli.lock.shell.run_remote", stub)
    monkeypatch.setattr("pawai_cli.lock.time.sleep", lambda s: None)
    result = Lock.acquire(user="u", host="h", branch="b", sha="s")
    assert result is not None
    assert result.user == "u"


def test_acquire_accepts_nav_lane_metadata(monkeypatch):
    from pawai_cli.shell import Result

    commands: list[str] = []

    def stub(cmd, timeout=None):
        commands.append(cmd)
        return Result(code=0, stdout="", stderr="")

    monkeypatch.setattr("pawai_cli.lock.shell.run_remote", stub)
    result = Lock.acquire(
        user="u",
        host="h",
        branch="b",
        sha="s",
        demo_mode="nav_capability",
        tmux_session="nav-cap-demo",
        lane="nav_capability",
    )
    assert result is not None
    assert result.lane == "nav_capability"
    assert result.tmux_session == "nav-cap-demo"
    assert "nav_capability" in commands[0]
    assert "nav-cap-demo" in commands[0]
