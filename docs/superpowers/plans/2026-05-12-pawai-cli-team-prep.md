# PawAI CLI Team-Prep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `pawai_cli` safe for five-person concurrent Jetson use tomorrow morning: teammates self-onboard via Tailscale share + `pawai doctor`, no silent collisions, network problems are self-diagnosable.

**Architecture:** Three thin layers landed independently as commit groups. L1 strengthens `doctor` and ships first-half onboarding docs so teammates can connect. L2 adds a Jetson-side flock-protected demo lock + extended `.pawai-last-deploy` schema + second-half docs so teammates do not silently overwrite each other. L3 adds two small helper commands (`pawai docs`, `pawai contract check`).

**Tech Stack:** Python 3.10+, Click, `python-dotenv`, `pytest`, SSH (no new deps). Lock atomicity via remote `flock` over SSH. Tests use env-override + fake JSON fixtures (no real network mutation, no real `.env.local` mutation).

**Spec:** `docs/superpowers/specs/2026-05-12-pawai-cli-team-prep-design.md`

**Out of scope (do NOT add):** `pawai reset`, `--fast` flag (use `--cache` instead), distributed consensus, ROS2 DDS tunneling, mobile Studio UI.

---

## File Map

### New files

| Path | Purpose |
|---|---|
| `tools/pawai_cli/pawai_cli/network.py` | Tailscale auto-detect + network topology probes |
| `tools/pawai_cli/pawai_cli/cache.py` | TTL-based result cache for `doctor --cache 30` |
| `tools/pawai_cli/pawai_cli/lock.py` | Demo lock primitives (acquire, read, release, stale check) |
| `tools/pawai_cli/tests/test_network.py` | Unit tests for network helpers (mocked subprocess) |
| `tools/pawai_cli/tests/test_lock.py` | Unit tests for lock state machine |
| `docs/pawai_cli/team-onboarding.md` | 30-min onboarding for new teammates |

### Modified files

| Path | Change |
|---|---|
| `tools/pawai_cli/pawai_cli/main.py` | doctor flags / lock-aware demo+deploy / docs+contract commands |
| `tools/pawai_cli/pawai_cli/status.py` | lock display + branch mismatch + topology summary |
| `tools/pawai_cli/pawai_cli/modules.py` | architecture-doc path lookup for `pawai docs` |
| `tools/pawai_cli/tests/test_cli.py` | acceptance tests for new flags + behaviors |
| `.env.local.example` | remove hardcoded Tailscale IP + add `JETSON_HOSTNAME_HINT` |
| `docs/pawai_cli/README.md` | doctor flags, lock semantics, branch mismatch, network topology |
| `docs/pawai_cli/troubleshooting.md` | new chapters G (Jetson network), H (Tailscale Share), I (Go2 Ethernet), J (Gateway 8080) |
| `tools/pawai_cli/README.md` | brief sync + pointer to docs |

---

# Phase L1 — Connectivity + First-Half Docs

**Acceptance gate before moving to L2:**
- `pawai doctor` shows Network topology block at top of output
- Gateway 8080 shows `SKIP (no demo)` when no demo running (not red)
- `JETSON_HOSTNAME_HINT=not-a-real-host pawai doctor` correctly surfaces no-peer warning
- `JETSON_HOST=jetson-bad pawai doctor` correctly distinguishes Tailscale-OK / SSH-alias-bad
- `pawai doctor --cache 30` second invocation returns in <1s
- `pawai doctor --deep` makes exactly one OpenRouter API call; default makes zero
- `pawai doctor --fix` writes only after prompt
- `docs/pawai_cli/team-onboarding.md` exists and walks teammate through Tailscale share acceptance

---

### Task L1-1: Add `network.py` Tailscale helpers

**Files:**
- Create: `tools/pawai_cli/pawai_cli/network.py`
- Create: `tools/pawai_cli/tests/test_network.py`

- [ ] **Step 1: Write failing test for `tailscale_status_peers`**

```python
# tools/pawai_cli/tests/test_network.py
from unittest.mock import patch
from pawai_cli.network import tailscale_status_peers, find_jetson_peer


def _fake_status_json() -> str:
    return """{
      "Self": {"HostName": "Roy-MBP", "TailscaleIPs": ["100.64.0.5"]},
      "Peer": {
        "n1": {"HostName": "jetson", "TailscaleIPs": ["100.83.109.89"], "Online": true},
        "n2": {"HostName": "other", "TailscaleIPs": ["100.64.0.6"], "Online": false}
      }
    }"""


def test_tailscale_status_peers_parses_hostnames():
    with patch("pawai_cli.network._run_tailscale_status_json", return_value=_fake_status_json()):
        peers = tailscale_status_peers()
    assert {"jetson", "other"} <= {p["hostname"] for p in peers}


def test_find_jetson_peer_matches_hint():
    with patch("pawai_cli.network._run_tailscale_status_json", return_value=_fake_status_json()):
        peer = find_jetson_peer(hint="jetson")
    assert peer is not None
    assert peer["ip"] == "100.83.109.89"


def test_find_jetson_peer_returns_none_when_no_match():
    with patch("pawai_cli.network._run_tailscale_status_json", return_value=_fake_status_json()):
        peer = find_jetson_peer(hint="zzz-no-match")
    assert peer is None
```

- [ ] **Step 2: Run test and verify it fails**

Run: `python3 -m pytest tools/pawai_cli/tests/test_network.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'pawai_cli.network'`

- [ ] **Step 3: Implement `network.py` Tailscale helpers**

```python
# tools/pawai_cli/pawai_cli/network.py
from __future__ import annotations

import json
import shutil
from typing import Optional

from . import shell


def _run_tailscale_status_json() -> Optional[str]:
    """Return raw `tailscale status --json` stdout, or None if tailscale absent/offline."""
    if shutil.which("tailscale") is None:
        return None
    result = shell.run(["tailscale", "status", "--json"], timeout=5)
    if not result.ok:
        return None
    return result.stdout


def tailscale_status_peers() -> list[dict]:
    """List peers from `tailscale status --json` as [{hostname, ip, online}, ...]."""
    raw = _run_tailscale_status_json()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    out: list[dict] = []
    for _, peer in (data.get("Peer") or {}).items():
        ips = peer.get("TailscaleIPs") or []
        out.append({
            "hostname": peer.get("HostName", ""),
            "ip": ips[0] if ips else "",
            "online": bool(peer.get("Online")),
        })
    return out


def find_jetson_peer(hint: str) -> Optional[dict]:
    """Return the peer whose hostname contains `hint` (case-insensitive); None if no match."""
    needle = hint.lower()
    for peer in tailscale_status_peers():
        if needle in peer["hostname"].lower():
            return peer
    return None
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_network.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/network.py tools/pawai_cli/tests/test_network.py
git commit -m "feat(cli): add network.py Tailscale peer discovery helpers"
```

---

### Task L1-2: Add `network.py` topology probes (SSH-based)

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/network.py` (add functions)
- Modify: `tools/pawai_cli/tests/test_network.py` (add tests with mocked shell.run_remote)

- [ ] **Step 1: Write failing tests for topology probes**

Append to `tools/pawai_cli/tests/test_network.py`:

```python
from pawai_cli.network import (
    jetson_internet_iface,
    jetson_go2_link,
    jetson_ping_go2,
    gateway_8080_status,
)
from pawai_cli.shell import Result


def _result(stdout: str = "", code: int = 0) -> Result:
    return Result(code=code, stdout=stdout, stderr="")


def test_jetson_internet_iface_reads_default_route():
    with patch("pawai_cli.network.shell.run_remote",
               return_value=_result("8.8.8.8 dev wlan0 src 192.168.1.10\n")):
        iface = jetson_internet_iface()
    assert iface == "wlan0"


def test_jetson_internet_iface_returns_none_on_failure():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("", 1)):
        assert jetson_internet_iface() is None


def test_jetson_go2_link_finds_192_168_123():
    with patch("pawai_cli.network.shell.run_remote",
               return_value=_result("eth0 UP 192.168.123.51/24\nwlan0 UP 10.0.0.5/24\n")):
        link = jetson_go2_link()
    assert link == {"iface": "eth0", "ip": "192.168.123.51/24"}


def test_jetson_go2_link_returns_none_when_absent():
    with patch("pawai_cli.network.shell.run_remote",
               return_value=_result("wlan0 UP 10.0.0.5/24\n")):
        assert jetson_go2_link() is None


def test_jetson_ping_go2_success():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("ok", 0)):
        assert jetson_ping_go2("192.168.123.161") is True


def test_jetson_ping_go2_failure():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("", 1)):
        assert jetson_ping_go2("192.168.123.161") is False


def test_gateway_8080_status_with_no_demo_skip():
    # demo not running, --expect-demo False → SKIP regardless of curl result
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("", 7)):
        status = gateway_8080_status(expect_demo=False, lock_state=None)
    assert status == "SKIP"


def test_gateway_8080_status_with_active_lock_failed_curl():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("", 7)):
        status = gateway_8080_status(expect_demo=False, lock_state="running")
    assert status == "FAIL"


def test_gateway_8080_status_with_expect_demo_ok():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result('{"status":"ok"}', 0)):
        status = gateway_8080_status(expect_demo=True, lock_state=None)
    assert status == "OK"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_network.py -v`
Expected: 8 new tests FAIL (functions not defined)

- [ ] **Step 3: Implement topology probes**

Append to `tools/pawai_cli/pawai_cli/network.py`:

```python
import re


def jetson_internet_iface() -> Optional[str]:
    """Return interface name used for default route on Jetson, or None on failure.

    Parses `ip route get 8.8.8.8` output. The format is `8.8.8.8 dev <iface> src <ip>`.
    """
    result = shell.run_remote("ip route get 8.8.8.8", timeout=5)
    if not result.ok:
        return None
    m = re.search(r"\bdev\s+(\S+)", result.stdout)
    return m.group(1) if m else None


def jetson_go2_link() -> Optional[dict]:
    """Return {iface, ip} of the Jetson interface in 192.168.123.x range, or None.

    Parses `ip -br addr` output. Lines look like `eth0 UP 192.168.123.51/24`.
    """
    result = shell.run_remote("ip -br addr", timeout=5)
    if not result.ok:
        return None
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        iface, _, *addrs = parts
        for addr in addrs:
            if addr.startswith("192.168.123."):
                return {"iface": iface, "ip": addr}
    return None


def jetson_ping_go2(robot_ip: str) -> bool:
    """True if Jetson can ping the Go2 IP within 2 seconds."""
    result = shell.run_remote(f"ping -c 1 -W 2 {robot_ip}", timeout=5)
    return result.ok


def gateway_8080_status(expect_demo: bool, lock_state: Optional[str]) -> str:
    """Return SKIP / OK / FAIL for the Gateway 8080 health check.

    - SKIP: no demo expected and no active lock — gateway not running is normal.
    - OK:   curl returns 0.
    - FAIL: demo is expected (--expect-demo or active running lock) but curl failed.
    """
    demo_expected = expect_demo or lock_state == "running"
    result = shell.run_remote(
        "curl -fsS --max-time 3 http://127.0.0.1:8080/health",
        timeout=5,
    )
    if result.ok:
        return "OK"
    return "FAIL" if demo_expected else "SKIP"
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_network.py -v`
Expected: 11 tests PASS (3 from L1-1 + 8 new)

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/network.py tools/pawai_cli/tests/test_network.py
git commit -m "feat(cli): add Jetson network topology probes (route/Go2 link/ping/8080)"
```

---

### Task L1-3: Add `cache.py` TTL-based result cache

**Files:**
- Create: `tools/pawai_cli/pawai_cli/cache.py`
- Create: `tools/pawai_cli/tests/test_cache.py`

- [ ] **Step 1: Write failing test**

```python
# tools/pawai_cli/tests/test_cache.py
import time
from pathlib import Path
from pawai_cli.cache import DoctorCache


def test_cache_returns_none_when_no_file(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=30)
    assert c.read() is None


def test_cache_round_trip(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=30)
    c.write({"status": "green", "topology": ["row1", "row2"]})
    assert c.read() == {"status": "green", "topology": ["row1", "row2"]}


def test_cache_expires(tmp_path: Path):
    c = DoctorCache(tmp_path / "cache.json", ttl_seconds=0)  # immediate expiry
    c.write({"x": 1})
    time.sleep(0.05)
    assert c.read() is None
```

- [ ] **Step 2: Run test, verify failure**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cache.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `cache.py`**

```python
# tools/pawai_cli/pawai_cli/cache.py
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional


class DoctorCache:
    """File-backed JSON cache with a TTL — used to avoid 5x SSH probes from a team."""

    def __init__(self, path: Path, ttl_seconds: int):
        self.path = path
        self.ttl = ttl_seconds

    def read(self) -> Optional[dict]:
        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        written_at = payload.get("_cached_at", 0)
        if time.time() - written_at > self.ttl:
            return None
        # Strip metadata before returning
        return {k: v for k, v in payload.items() if k != "_cached_at"}

    def write(self, data: dict) -> None:
        payload = dict(data)
        payload["_cached_at"] = time.time()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload))
```

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cache.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/cache.py tools/pawai_cli/tests/test_cache.py
git commit -m "feat(cli): add DoctorCache TTL-backed JSON cache"
```

---

### Task L1-4: `.env.local.example` change + `JETSON_HOSTNAME_HINT` support

**Files:**
- Modify: `.env.local.example`
- Modify: `tools/pawai_cli/pawai_cli/shell.py` (add `jetson_hostname_hint` helper)
- Modify: `tools/pawai_cli/tests/test_cli.py` (add tests for env reading)

- [ ] **Step 1: Patch `.env.local.example`**

Find the line `JETSON_TAILSCALE_IP=100.83.109.89` and replace that block with:

```
# JETSON_TAILSCALE_IP=
# Leave blank — CLI auto-detects via `tailscale status` using JETSON_HOSTNAME_HINT
JETSON_HOSTNAME_HINT=jetson
```

- [ ] **Step 2: Add `jetson_hostname_hint` helper + test**

In `tools/pawai_cli/pawai_cli/shell.py` add (next to `jetson_repo`):

```python
def jetson_hostname_hint() -> str:
    return env("JETSON_HOSTNAME_HINT", "jetson")
```

In `tools/pawai_cli/tests/test_cli.py` append:

```python
def test_jetson_hostname_hint_env(monkeypatch):
    from pawai_cli import shell
    monkeypatch.setenv("JETSON_HOSTNAME_HINT", "orin")
    assert shell.jetson_hostname_hint() == "orin"


def test_jetson_hostname_hint_default(monkeypatch):
    from pawai_cli import shell
    monkeypatch.delenv("JETSON_HOSTNAME_HINT", raising=False)
    assert shell.jetson_hostname_hint() == "jetson"
```

- [ ] **Step 3: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k hostname_hint`
Expected: 2 tests PASS

- [ ] **Step 4: Commit**

```bash
git add .env.local.example tools/pawai_cli/pawai_cli/shell.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): JETSON_HOSTNAME_HINT env + .env.local.example IP unblocked"
```

---

### Task L1-5: Wire doctor — Tailscale auto-detect + IP consistency check

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (`doctor` function, lines 79-195)
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing acceptance test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
from click.testing import CliRunner
from unittest.mock import patch
from pawai_cli.main import cli


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
    assert "share link" in result.output.lower() or "tailscale" in result.output.lower()
```

- [ ] **Step 2: Run test, verify failure**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k doctor_warns`
Expected: FAIL (current doctor does not check Tailscale)

- [ ] **Step 3: Add Tailscale check section to `doctor` function**

In `tools/pawai_cli/pawai_cli/main.py`, inside `doctor()` function before existing SSH check, insert:

```python
    from . import network

    hint = shell.env("JETSON_HOSTNAME_HINT", "jetson")
    env_ip = os.environ.get("JETSON_TAILSCALE_IP", "").strip()

    click.echo("== Tailscale ==")
    peer = network.find_jetson_peer(hint=hint)
    if peer is None:
        click.echo(f"  ✗ no Tailscale peer hostname matches '{hint}'")
        click.echo(f"    → ask Roy for the share link and accept it in your Tailscale account")
        click.echo(f"    → or set JETSON_HOSTNAME_HINT in .env.local if your share node has a different hostname")
    else:
        detected_ip = peer["ip"]
        click.echo(f"  ✓ Tailscale peer '{peer['hostname']}' online={peer['online']} ip={detected_ip}")
        if env_ip and env_ip != detected_ip:
            click.echo(f"  ⚠ JETSON_TAILSCALE_IP={env_ip} but Tailscale reports {detected_ip} (mismatch)")
            click.echo(f"    → run `pawai doctor --fix` to update .env.local")
        elif not env_ip:
            click.echo(f"  ℹ JETSON_TAILSCALE_IP unset — CLI will use detected {detected_ip}")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k doctor_warns`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): doctor — Tailscale auto-detect + IP mismatch warning"
```

---

### Task L1-6: Wire doctor — Network topology block

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k topology`
Expected: FAIL

- [ ] **Step 3: Add `--expect-demo` flag + topology block**

In `tools/pawai_cli/pawai_cli/main.py`, change `doctor` decorator and signature:

```python
@cli.command()
@click.option("--verbose", is_flag=True, help="Print SSH stderr details on failure.")
@click.option("--expect-demo", is_flag=True, help="Treat Gateway 8080 down as FAIL (default: SKIP).")
@click.option("--fix", is_flag=True, help="Prompt to write detected IP into .env.local.")
@click.option("--deep", is_flag=True, help="Run live OpenRouter API call.")
@click.option("--cache", "cache_seconds", type=int, default=0,
              help="Cache result for N seconds.")
def doctor(verbose: bool, expect_demo: bool, fix: bool, deep: bool, cache_seconds: int) -> None:
```

Then inside the function, after the Tailscale block from L1-5, before the existing SSH check, add:

```python
    click.echo("\n== Network topology ==")

    if peer is None:
        click.echo("  ✗ local → Jetson Tailscale: no peer found (see Tailscale section above)")
    else:
        click.echo(f"  ✓ local → Jetson Tailscale: OK {peer['ip']}")

    iface = network.jetson_internet_iface()
    if iface is None:
        click.echo("  ✗ Jetson internet route: probe failed")
    elif iface == "eth0":
        click.echo(f"  ⚠ Jetson internet route: {iface} (Ethernet appears to be uplink — Go2 link may be lost)")
    else:
        click.echo(f"  ✓ Jetson internet route: {iface}")

    go2_link = network.jetson_go2_link()
    if go2_link is None:
        click.echo("  ✗ Jetson Go2 link: no 192.168.123.x interface (Ethernet to Go2 not connected)")
    else:
        click.echo(f"  ✓ Jetson Go2 link: {go2_link['iface']} {go2_link['ip']}")

    robot_ip = shell.env("ROBOT_IP", "192.168.123.161")
    if go2_link is None:
        click.echo(f"  ✗ Jetson → Go2 ping: skipped (no Go2 link)")
    elif network.jetson_ping_go2(robot_ip):
        click.echo(f"  ✓ Jetson → Go2 ping: OK {robot_ip}")
    else:
        click.echo(f"  ✗ Jetson → Go2 ping: FAIL {robot_ip}")

    lock_state = None  # L2 will populate this from lock module
    gw_status = network.gateway_8080_status(expect_demo=expect_demo, lock_state=lock_state)
    icon = {"OK": "✓", "SKIP": "ℹ", "FAIL": "✗"}.get(gw_status, "?")
    detail = "" if gw_status != "SKIP" else " (no demo running)"
    click.echo(f"  {icon} Gateway 8080: {gw_status}{detail}")
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k topology`
Expected: 2 tests PASS

- [ ] **Step 5: Manual full run**

Run: `pawai doctor`
Expected: full output prints, Network topology block appears, no crashes regardless of peer state.

- [ ] **Step 6: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): doctor — Network topology block + --expect-demo flag"
```

---

### Task L1-7: Add `--fix`, `--deep`, `--cache` flag behaviors

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run tests, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k "deep or cache or fix"`
Expected: FAIL

- [ ] **Step 3: Implement `--deep` OpenRouter live probe**

Add at top of `main.py` (stdlib only, no new dependency):

```python
import urllib.request
import urllib.error
```

In `doctor` function, after Tailscale block but **only inside `if deep:`** branch, add:

```python
    if deep:
        click.echo("\n== Deep checks (--deep) ==")
        key = os.environ.get("OPENROUTER_KEY") or os.environ.get("OPENROUTER_API_KEY")
        if not key:
            click.echo("  ✗ OPENROUTER_KEY not set")
        else:
            req = urllib.request.Request(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {key}"},
            )
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    if r.status == 200:
                        click.echo("  ✓ OpenRouter API reachable, key authorized")
                    else:
                        click.echo(f"  ✗ OpenRouter API returned status {r.status}")
            except urllib.error.HTTPError as exc:
                click.echo(f"  ✗ OpenRouter HTTP {exc.code}: {exc.reason}")
            except Exception as exc:
                click.echo(f"  ✗ OpenRouter API call failed: {exc}")
```

Tests in Step 1 already patch `pawai_cli.main.urllib.request.urlopen`. No further test changes needed.

- [ ] **Step 4: Implement `--cache` integration**

Near top of `doctor()`:

```python
    from .cache import DoctorCache

    cache = None
    if cache_seconds > 0:
        cache_dir = Path(os.environ.get("PAWAI_CACHE_DIR",
                                        os.path.expanduser("~/.cache/pawai")))
        cache = DoctorCache(cache_dir / "doctor.json", ttl_seconds=cache_seconds)
        cached = cache.read()
        if cached is not None:
            click.echo(cached.get("output", ""))
            click.echo(f"(cached result, age <{cache_seconds}s — run without --cache to refresh)")
            return
```

Then capture output for cache write. Wrap doctor body in:

```python
    import io
    buf = io.StringIO() if cache is not None else None

    def emit(line: str = "") -> None:
        click.echo(line)
        if buf is not None:
            buf.write(line + "\n")
```

Replace `click.echo(...)` calls in doctor with `emit(...)`. At end of function:

```python
    if cache is not None and buf is not None:
        cache.write({"output": buf.getvalue()})
```

- [ ] **Step 5: Implement `--fix` prompt-then-write**

After Tailscale block, if peer present and `env_ip` mismatches detected_ip:

```python
        elif fix and env_ip != detected_ip and env_ip:
            answer = click.prompt(
                f"\nUpdate JETSON_TAILSCALE_IP in .env.local from {env_ip} to {detected_ip}?",
                default="n", show_default=True,
            )
            if answer.lower().startswith("y"):
                _patch_env_local(Path(shell.repo_root()) / ".env.local",
                                 "JETSON_TAILSCALE_IP", detected_ip)
                emit(f"  ✓ wrote JETSON_TAILSCALE_IP={detected_ip} to .env.local")
```

And add helper at module level:

```python
def _patch_env_local(path: Path, key: str, value: str) -> None:
    """In-place replace or append `KEY=value` line in .env.local. Idempotent."""
    if not path.exists():
        path.write_text(f"{key}={value}\n")
        return
    lines = path.read_text().splitlines()
    found = False
    for i, line in enumerate(lines):
        stripped = line.lstrip("# ").strip()
        if stripped.startswith(f"{key}=") or stripped.startswith(f"# {key}="):
            lines[i] = f"{key}={value}"
            found = True
            break
    if not found:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n")
```

- [ ] **Step 6: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k "deep or cache or fix"`
Expected: 4 tests PASS

- [ ] **Step 7: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): doctor — --fix / --deep / --cache flags"
```

---

### Task L1-8: L1 docs (team-onboarding 1-4 + troubleshooting G/H + README doctor)

**Files:**
- Create: `docs/pawai_cli/team-onboarding.md`
- Modify: `docs/pawai_cli/troubleshooting.md` (append G + H chapters)
- Modify: `docs/pawai_cli/README.md` (add doctor flags section)

- [ ] **Step 1: Create `team-onboarding.md` steps 1-4**

```markdown
# PawAI 新隊友 30 分鐘上手

> Steps 5 + 規矩 在 L2 之後補。今天先到 doctor 全綠。

## 0. 你需要什麼

- macOS / Linux / WSL2
- GitHub repo 存取權
- Roy 在群組發的 Tailscale share link

## 1. 裝工具（5 min）

```bash
# macOS
brew install tmux node tailscale

# Linux / WSL
sudo apt install tmux nodejs npm
# Tailscale: https://tailscale.com/download/linux
```

## 2. 加入 Tailscale（5 min）

1. 打開 Roy 發的 share link
2. 用你自己**免費的** Tailscale 帳號登入（不需付費，不佔 Roy 配額）
3. 接受 share
4. 終端跑：
   ```bash
   tailscale status
   ```
   應該看到 `roy422` 的 jetson node（hostname 含 "jetson"）
5. 測延遲：
   ```bash
   tailscale ping jetson
   ```
   `< 50ms` 是好狀態

## 3. clone repo + 裝 CLI（10 min）

```bash
git clone <repo-url> elder_and_dog
cd elder_and_dog

# 建 venv（避免污染系統 Python）
python3 -m venv ~/.venv
source ~/.venv/bin/activate

# 裝 CLI
uv pip install -e tools/pawai_cli
pawai --version   # 應印 0.x.y

# 環境變數
cp .env.local.example .env.local
$EDITOR .env.local
```

`.env.local` 需要填的：
- `OPENROUTER_KEY` — 跟 Roy 拿
- `JETSON_TAILSCALE_IP` — **留空**（CLI 會自動從 tailscale status 偵測）
- `JETSON_HOSTNAME_HINT` — 預設 `jetson` 即可；如果你的 share node hostname 不同，改成符合的關鍵字

## 4. doctor 應該全綠（5 min）

```bash
pawai doctor
```

預期看到：
- `== Tailscale ==` 區塊：`✓ Tailscale peer 'jetson' online=true ip=100.83.109.89`
- `== Network topology ==` 區塊：
  - `✓ local → Jetson Tailscale: OK 100.83.109.89`
  - `✓ Jetson internet route: wlan0`（**不能是 eth0**，否則 Go2 線被搶用）
  - `✓ Jetson Go2 link: eth0 192.168.123.X/24`
  - `✓ Jetson → Go2 ping: OK 192.168.123.161`
  - `ℹ Gateway 8080: SKIP (no demo running)` ← 這是正常的，不是紅燈

紅燈時對照 `docs/pawai_cli/troubleshooting.md` B / G / H 章。

## 5. 第一個任務 — Coming in L2

L2 加完 lock 之後本節會補：自己 branch → deploy → demo start → 規矩。
```

- [ ] **Step 2: Append troubleshooting G + H chapters**

Append to `docs/pawai_cli/troubleshooting.md`:

```markdown
---

## G. Jetson 換網路

### G1. Jetson 從家裡搬到學校 — 我該擔心什麼？

短答：
- **Tailscale IP `100.83.109.89` 通常不變** — 跨網路一致
- **Jetson 本地 LAN/Wi-Fi IP 會變** — 但 CLI 不依賴它
- **Go2 IP 應該不變** — 還是 `192.168.123.161`，前提是 Jetson↔Go2 Ethernet 線還插著

最容易壞的事情：**Jetson 的 Ethernet 被拔去插學校網路**，導致 Go2 link 不見。

`pawai doctor` 的 Network topology 區塊會在這時翻紅：
- `Jetson internet route: eth0` ← ⚠ Ethernet 變成 uplink
- `Jetson Go2 link: no 192.168.123.x interface` ← ✗ Go2 線沒接

**修法**：學校用 **Wi-Fi 上網**，Ethernet 保留給 Go2。

### G2. Tailscale Reconnecting

開機/換網路後 30s-2min 內，doctor 可能短暫紅燈。等 60s 再跑：

```bash
sleep 60 && pawai doctor
```

### G3. 學校 Wi-Fi 擋 outbound

學校網路偶爾擋 SSH (22) 或 outbound HTTP — 表現是 SenseVoice tunnel / OpenRouter 連不到。
fallback：用 local ASR / local TTS（`ASR_PROVIDER_ORDER='["sensevoice_local","whisper_local"]'`）。

---

## H. Tailscale Sharing

### H1. 我接受 share link 後 `tailscale status` 看不到 Jetson

- 確認你接受 share 時用的是你自己的 Tailscale 帳號（不是 Roy 的）
- 跑 `tailscale up`
- 重新點 share link

### H2. 同一台筆電換 Tailscale 帳號

如果你先前裝 Tailscale 用了不同帳號：

```bash
sudo tailscale logout
sudo tailscale up   # 引導你登入新帳號
```

### H3. Tailscale free tier 上限

Free Personal tier 可以接受別人的 share node 不佔 user 配額。不需付費。
```

- [ ] **Step 3: Append README doctor flags section**

In `docs/pawai_cli/README.md`, find the `doctor` section and append:

```markdown
### doctor flags

| Flag | Effect |
|---|---|
| (none) | full check, no API calls, no file writes |
| `--fix` | prompt to write detected Tailscale IP into `.env.local` |
| `--deep` | one OpenRouter API call to verify key |
| `--cache 30` | cache result for 30s (avoids 5-person waiting on same SSH probes) |
| `--expect-demo` | treat Gateway 8080 down as FAIL instead of SKIP |
| `--verbose` | print SSH stderr on failure |

### Network topology block

`pawai doctor` now prints a topology summary near the top:

```
Network topology:
  local → Jetson Tailscale: OK 100.83.109.89 latency=Xms
  Jetson internet route:    OK wlan0
  Jetson Go2 link:          OK eth0 192.168.123.X
  Jetson → Go2 ping:        OK 192.168.123.161
  Gateway 8080:             SKIP (no demo running)
```

Reading guide:
- `Jetson internet route: eth0` → **warning** — Ethernet likely hijacked for school uplink, Go2 link lost
- `Jetson Go2 link: ✗` → Go2 Ethernet not connected to Jetson
- `Gateway 8080: SKIP` → expected when no demo running; only red if `--expect-demo` or active demo lock
```

- [ ] **Step 4: Commit**

```bash
git add docs/pawai_cli/team-onboarding.md docs/pawai_cli/troubleshooting.md docs/pawai_cli/README.md
git commit -m "docs(cli): L1 — team-onboarding 1-4, troubleshooting G/H, README doctor flags"
```

---

### L1 Acceptance Run

- [ ] **Manual verification on Roy's machine**

Run:

```bash
pawai doctor
pawai doctor --cache 30 && time pawai doctor --cache 30   # second should be <1s
JETSON_HOSTNAME_HINT=not-a-real-host pawai doctor          # surfaces no-peer
JETSON_HOST=jetson-bad pawai doctor                        # Tailscale OK, SSH alias bad
pawai doctor --deep                                        # one OpenRouter call
pawai doctor --fix                                         # prompts (you answer n)
python3 -m pytest tools/pawai_cli/tests/ -v                # all green
```

All boxes above checked → L1 done.

---

# Phase L2 — Coordination + Second-Half Docs

**Acceptance gate before moving to L3:**
- `pawai demo start` writes `starting → running` lock; collision prompt appears for another user; `--force` takes over; `-y` does not
- `pawai demo stop` defaults to own-lock-only; `--force` clears any
- `pawai jetson deploy` prompts on cross-user demo collision
- `pawai status` shows lock state + branch mismatch + dirty
- Stale `running` lock (>4hr) flagged but never auto-deleted
- `.pawai-last-deploy` has new fields (branch, sha_full, dirty, packages, deployed_by, deployed_from_host)
- docs/pawai_cli/troubleshooting.md has I + J chapters; team-onboarding.md has step 5 + rules

---

### Task L2-1: `lock.py` primitives + tests

**Files:**
- Create: `tools/pawai_cli/pawai_cli/lock.py`
- Create: `tools/pawai_cli/tests/test_lock.py`

- [ ] **Step 1: Write failing tests**

```python
# tools/pawai_cli/tests/test_lock.py
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
    payload = '{"user":"alice","state":"running","branch":"main","start_time":"2026-05-13T08:00:00+08:00"}'
    with patch("pawai_cli.lock.shell.run_remote", return_value=_ok(payload)):
        lk = Lock.read()
    assert lk is not None
    assert lk.user == "alice"
    assert lk.state == "running"


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
```

- [ ] **Step 2: Run, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_lock.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `lock.py`**

```python
# tools/pawai_cli/pawai_cli/lock.py
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

from . import shell


def _remote_lock_path() -> str:
    """Resolve full path locally to avoid depending on Jetson-side $JETSON_REPO env."""
    return f"{shell.jetson_repo()}/.pawai-demo-lock"


LOCK_FLOCK_PATH = "/tmp/pawai-demo-lock.flock"

STARTING_STALE_MINUTES = 10
RUNNING_STALE_HOURS = 4


@dataclass
class Lock:
    user: str
    host: str
    branch: str
    sha: str
    state: str  # "starting" | "running"
    start_time: str  # ISO 8601 with tz
    demo_mode: str = "full"
    tmux_session: str = "demo"

    @classmethod
    def read(cls) -> Optional["Lock"]:
        """Read lock from Jetson via SSH; return None if absent or malformed."""
        result = shell.run_remote(f"cat {_remote_lock_path()} 2>/dev/null", timeout=5)
        if not result.ok or not result.stdout.strip():
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        try:
            return cls(**data)
        except TypeError:
            return None

    @classmethod
    def acquire(cls, user: str, host: str, branch: str, sha: str,
                state: str = "starting") -> Optional["Lock"]:
        """Atomically write a lock if absent.

        Exit code semantics from the remote `flock` command:
        - 0  → wrote new lock (success)
        - 17 → lock file already exists (someone holds it; do NOT retry)
        - other non-zero → flock contention or transient SSH failure; retry up to 3× with 2s backoff
        """
        now = datetime.now(timezone.utc).isoformat()
        lk = cls(user=user, host=host, branch=branch, sha=sha,
                 state=state, start_time=now)
        payload = json.dumps(asdict(lk)).replace("'", "'\\''")
        cmd = (
            f"flock -n {LOCK_FLOCK_PATH} -c '"
            f"if [ -f {_remote_lock_path()} ]; then exit 17; fi; "
            f"printf %s '\\''{payload}'\\'' > {_remote_lock_path()}.tmp && "
            f"mv {_remote_lock_path()}.tmp {_remote_lock_path()}'"
        )
        for attempt in range(3):
            result = shell.run_remote(cmd, timeout=10)
            if result.code == 0:
                return lk
            if result.code == 17:
                return None  # someone owns the lock — do not retry
            # transient: flock contention or SSH hiccup → backoff and retry
            if attempt < 2:
                time.sleep(2)
        return None  # exhausted retries

    def transition_to(self, new_state: str) -> bool:
        """Update state field on existing lock. Caller must own it."""
        now = datetime.now(timezone.utc).isoformat()
        updated = asdict(self)
        updated["state"] = new_state
        updated["start_time"] = now  # bump for running TTL
        payload = json.dumps(updated).replace("'", "'\\''")
        cmd = (
            f"flock -n {LOCK_FLOCK_PATH} -c '"
            f"printf %s '\\''{payload}'\\'' > {_remote_lock_path()}.tmp && "
            f"mv {_remote_lock_path()}.tmp {_remote_lock_path()}'"
        )
        return shell.run_remote(cmd, timeout=10).ok

    @classmethod
    def release(cls) -> bool:
        result = shell.run_remote(f"rm -f {_remote_lock_path()}", timeout=5)
        return result.ok


def is_stale(lk: Lock) -> Optional[str]:
    """Return 'starting' / 'running' if stale, else None."""
    try:
        start = datetime.fromisoformat(lk.start_time)
    except ValueError:
        return None
    now = datetime.now(timezone.utc)
    age = now - start
    if lk.state == "starting" and age.total_seconds() > STARTING_STALE_MINUTES * 60:
        return "starting"
    if lk.state == "running" and age.total_seconds() > RUNNING_STALE_HOURS * 3600:
        return "running"
    return None


def is_own_lock(lk: Lock, user: str, host: str) -> bool:
    return lk.user == user and lk.host == host
```

- [ ] **Step 4: Run tests, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_lock.py -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/lock.py tools/pawai_cli/tests/test_lock.py
git commit -m "feat(cli): lock.py — Jetson-side flock demo lock primitives"
```

---

### Task L2-2: `.pawai-last-deploy` schema extension

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (deploy function around line 281)
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k last_deploy_payload`
Expected: FAIL — `_build_last_deploy_payload` does not exist

- [ ] **Step 3: Implement helper + integrate into deploy**

Add to `tools/pawai_cli/pawai_cli/main.py` (module level, near other helpers):

```python
def _build_last_deploy_payload(module: str, packages: list[str], sync_method: str) -> dict:
    """Construct the .pawai-last-deploy JSON payload with full provenance.

    Captures: who deployed, from which host, current branch, full+short SHA,
    dirty flag, module alias, resolved package list, sync method, timestamp.
    """
    root = shell.repo_root()
    branch_r = shell.run(["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    sha_r = shell.run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=5)
    porcelain = shell.run(["git", "-C", str(root), "status", "--porcelain"], timeout=5)

    branch = branch_r.stdout.strip() if branch_r.ok else "unknown"
    sha_full = sha_r.stdout.strip() if sha_r.ok else ""
    sha_short = sha_full[:7] if sha_full else ""
    dirty = bool(porcelain.stdout.strip()) if porcelain.ok else False

    return {
        "deployed_by": shell.local_identity().split("@")[0],
        "deployed_from_host": shell.local_identity().split("@")[-1] if "@" in shell.local_identity() else "",
        "branch": branch,
        "git_sha": sha_short,
        "git_sha_full": sha_full,
        "dirty": dirty,
        "module": module,
        "packages": packages,
        "when": datetime.now(timezone.utc).isoformat(),
        "sync_method": sync_method,
    }
```

In `deploy` function, find the existing code that writes `.pawai-last-deploy` and replace it with code that calls `_build_last_deploy_payload(...)`. If the current deploy already builds a dict, just merge the new fields in.

- [ ] **Step 4: Run test, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k last_deploy_payload`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): extend .pawai-last-deploy schema (branch, dirty, sha_full, packages, host)"
```

---

### Task L2-3: `pawai demo start` lock integration

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (`demo_start` function around line 380)
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Append to `tools/pawai_cli/tests/test_cli.py`:

```python
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k demo_start`
Expected: FAIL

- [ ] **Step 3: Implement lock-aware demo start**

Replace existing `demo_start` decorator + signature:

```python
@demo.command("start")
@click.option("--no-studio", is_flag=True)
@click.option("--brain-only", is_flag=True)
@click.option("-y", "yes", is_flag=True, help="Skip ordinary confirmation prompts (does NOT override another user's lock).")
@click.option("--force", "force", is_flag=True, help="Take over another user's demo lock.")
def demo_start(no_studio: bool, brain_only: bool, yes: bool, force: bool) -> None:
    from .lock import Lock, is_stale, is_own_lock

    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()
    branch = _current_branch()
    sha = _current_sha_short()

    existing = Lock.read()
    if existing is not None:
        if is_own_lock(existing, user, host):
            click.echo(f"Existing lock is yours ({existing.state}). Restarting demo.")
            Lock.release()
        else:
            stale = is_stale(existing)
            if stale:
                click.echo(f"⚠ Stale {stale} lock from {existing.user} (age exceeds threshold).")
            else:
                click.echo(f"Another user is in demo: {existing.user}@{existing.host} "
                           f"branch={existing.branch} state={existing.state}")
            if not force:
                if yes:
                    click.echo("`-y` does not override another user's lock. Use --force to take over.")
                    sys.exit(2)
                answer = click.prompt("Take over? [force/cancel]", default="cancel")
                if not answer.lower().startswith("f"):
                    sys.exit(0)
            click.echo(f"--force: clearing {existing.user}'s lock")
            Lock.release()

    # Acquire starting lock
    lk = Lock.acquire(user=user, host=host, branch=branch, sha=sha, state="starting")
    if lk is None:
        click.echo("Failed to acquire lock after 3 retries — flock held by another process or remote SSH issue. Investigate before retrying.")
        sys.exit(2)

    rc = _invoke_start_sh(no_studio=no_studio, brain_only=brain_only)
    if rc != 0:
        click.echo("Demo start failed — releasing lock.")
        Lock.release()
        sys.exit(rc)

    lk.transition_to("running")
    click.echo(f"✓ Demo running (lock owner: {user}@{host})")


def _invoke_start_sh(no_studio: bool, brain_only: bool) -> int:
    """Thin wrapper for tests — calls existing start.sh path."""
    args = ["bash", ".claude/skills/brain-studio-lane/scripts/start.sh"]
    if brain_only:
        args.append("minimal")
    elif no_studio:
        args.append("full")
    else:
        args.append("demo")
    return shell.stream(args, cwd=shell.repo_root())


def _current_branch() -> str:
    r = shell.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else "unknown"


def _current_sha_short() -> str:
    r = shell.run(["git", "rev-parse", "--short", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else ""
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k demo_start`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): demo start — lock acquire (starting→running) + collision prompt + --force"
```

---

### Task L2-4: `pawai demo stop` own-lock-only + `--force`

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, verify fail**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k demo_stop`

- [ ] **Step 3: Implement**

```python
@demo.command("stop")
@click.option("--force", is_flag=True, help="Stop another user's demo and release their lock.")
def demo_stop(force: bool) -> None:
    from .lock import Lock, is_own_lock
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    existing = Lock.read()
    if existing is None:
        click.echo("No demo lock present.")
        rc = _invoke_cleanup_sh()
        sys.exit(rc)

    if not is_own_lock(existing, user, host) and not force:
        click.echo(f"Lock is owned by {existing.user}@{existing.host}. "
                   f"Use --force to stop their demo.")
        sys.exit(2)

    rc = _invoke_cleanup_sh()
    Lock.release()
    sys.exit(rc)


def _invoke_cleanup_sh() -> int:
    return shell.stream(["bash", ".claude/skills/brain-studio-lane/scripts/cleanup.sh"],
                        cwd=shell.repo_root())
```

- [ ] **Step 4: Run, verify pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k demo_stop`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): demo stop — own-lock-only default + --force takeover"
```

---

### Task L2-5: `pawai jetson deploy` lock-aware collision prompt

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py` (`deploy` function around line 281)
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing test**

```python
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
```

- [ ] **Step 2: Run, fail**

- [ ] **Step 3: Add lock check to `deploy`**

In `deploy` function, near the top (after parsing arguments), insert:

```python
    from .lock import Lock, is_own_lock
    user = os.environ.get("USER") or shell.local_identity().split("@")[0]
    host = platform.node()

    existing = Lock.read()
    force = locals().get("force", False)
    yes = locals().get("yes", False)
    if existing is not None and existing.state == "running" \
            and not is_own_lock(existing, user, host) and not force:
        click.echo(f"⚠ {existing.user}@{existing.host} is running a demo on branch={existing.branch}.")
        click.echo("Deploying now may overwrite their install.")
        if yes:
            click.echo("`-y` does not override another user's demo. Use --force.")
            sys.exit(2)
        answer = click.prompt("Continue? [force/cancel]", default="cancel")
        if not answer.lower().startswith("f"):
            sys.exit(0)
```

Add `--force` to the `deploy` decorator:

```python
@click.option("--force", is_flag=True, help="Deploy even if another user is in active demo.")
```

And update the function signature accordingly.

Also extract the actual rsync+build body into `_do_rsync_and_build(...)` so the test can mock it.

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k deploy_prompts`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): jetson deploy — lock-aware collision prompt + --force"
```

---

### Task L2-6: `pawai status` lock display + branch mismatch + topology summary

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/status.py`
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
def test_status_shows_lock_state(monkeypatch):
    from pawai_cli.lock import Lock
    lk = Lock(user="alice", host="alice-mac", branch="feat/x", sha="abc",
              state="running",
              start_time=datetime.now(timezone.utc).isoformat())
    with patch("pawai_cli.status.Lock.read", return_value=lk):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "alice" in result.output.lower()
    assert "running" in result.output.lower()


def test_status_shows_branch_mismatch(monkeypatch, tmp_path):
    last_deploy = {
        "deployed_by": "alice", "branch": "feat/old",
        "git_sha": "111", "git_sha_full": "1" * 40, "dirty": False,
        "module": "brain", "packages": ["pawai_brain"],
        "when": "2026-05-13T08:00:00+00:00", "sync_method": "rsync",
    }
    with patch("pawai_cli.status._read_last_deploy_remote", return_value=last_deploy), \
         patch("pawai_cli.status._current_branch", return_value="feat/new"):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "mismatch" in result.output.lower() or "feat/old" in result.output


def test_status_shows_stale_running_warning(monkeypatch):
    from pawai_cli.lock import Lock
    from datetime import timedelta
    old = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    lk = Lock(user="alice", host="h", branch="b", sha="s",
              state="running", start_time=old)
    with patch("pawai_cli.status.Lock.read", return_value=lk):
        runner = CliRunner()
        result = runner.invoke(cli, ["status"])
    assert "stale" in result.output.lower()
```

- [ ] **Step 2: Run, fail**

- [ ] **Step 3: Implement in `status.py`**

Update `tools/pawai_cli/pawai_cli/status.py` to import `Lock`, `is_stale`, and read `.pawai-last-deploy` via SSH. Add a `_read_last_deploy_remote` function and `_current_branch` helper. Print sections:

```python
# Add to top of status.py
from .lock import Lock, is_stale


def _read_last_deploy_remote() -> dict | None:
    from . import shell
    remote_path = f"{shell.jetson_repo()}/.pawai-last-deploy"
    result = shell.run_remote(
        f"cat {remote_path} 2>/dev/null",
        timeout=5,
    )
    if not result.ok or not result.stdout.strip():
        return None
    import json
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _current_branch() -> str:
    from . import shell
    r = shell.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], timeout=5)
    return r.stdout.strip() if r.ok else "unknown"
```

Inside `print_status`, after existing sections, add:

```python
    # Demo lock
    lk = Lock.read()
    print("Demo lock:")
    if lk is None:
        print("  (none)")
    else:
        stale = is_stale(lk)
        suffix = f" [STALE {stale}]" if stale else ""
        print(f"  owner: {lk.user}@{lk.host}")
        print(f"  branch: {lk.branch}")
        print(f"  state: {lk.state}{suffix}")
        print(f"  started: {lk.start_time}")

    # Branch mismatch
    last = _read_last_deploy_remote()
    if last is not None:
        local_branch = _current_branch()
        install_branch = last.get("branch", "?")
        dirty_flag = " (dirty)" if last.get("dirty") else ""
        print("Branch state:")
        print(f"  local:   {local_branch}")
        print(f"  install: {install_branch}{dirty_flag}")
        if local_branch != install_branch:
            print(f"  ⚠ MISMATCH — running install is from {install_branch}, you have {local_branch} checked out")
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k status`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/status.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): status — lock display, branch mismatch, stale warning"
```

---

### Task L2-7: L2 docs (team-onboarding step 5 + rules + troubleshooting I/J + README lock)

**Files:**
- Modify: `docs/pawai_cli/team-onboarding.md`
- Modify: `docs/pawai_cli/troubleshooting.md` (append I + J)
- Modify: `docs/pawai_cli/README.md` (add lock + branch sections)

- [ ] **Step 1: Replace `team-onboarding.md` step 5 placeholder**

Replace the "Coming in L2" stub with:

```markdown
## 5. 第一個任務（5 min）

開自己的 branch：
```bash
git checkout -b feat/<yourname>-explore
```

部署你負責的模組：
```bash
pawai docs <module>             # 先看架構文件
pawai jetson deploy --module <module>
```

啟動 demo：
```bash
pawai demo start
```

如果看到「Another user is in demo」訊息 — 不要 `--force`，跟對方溝通。

完成後一定要停：
```bash
pawai demo stop
```

`pawai status` 隨時查看誰在 demo、用哪個 branch、跑了多久。

## 規矩（明天現場守住）

- **一次只能一個人 `pawai demo start`** — Jetson + Go2 是共用資源
- **`-y` ≠ `--force`**：`-y` 只跳自己的確認，**不能**蓋別人的 lock；要接手別人 demo 必須 `--force`
- **`pawai demo stop` 預設只清自己的 lock**；停別人的 demo 用 `--force` 並先告訴對方
- **deploy 中看到「someone is in demo」prompt → 先溝通**，不要直接 `--force`
- **stale lock（demo 跑超過 4hr）不會自動清** — `pawai status` 會標 STALE，要清也要確認對方真的不在用
```

- [ ] **Step 2: Append troubleshooting I + J**

Append to `docs/pawai_cli/troubleshooting.md`:

```markdown
---

## I. Go2 Ethernet 直連

### I1. `Jetson → Go2 ping: FAIL` 的三種可能

1. Jetson Ethernet 沒插 Go2（看 `Jetson Go2 link` 那行有沒有 `192.168.123.x`）
2. Jetson Ethernet 被誤拿去接學校網路（看 `Jetson internet route` 是不是 `eth0`）
3. Go2 沒開機 / cable 鬆脫

### I2. 不要把 Go2 插學校 Wi-Fi

Go2 連到有外網的 Wi-Fi 會自動 OTA 更新韌體。永遠 Ethernet 直連 Jetson 就好。

### I3. Jetson 換網路後 Go2 ping 突然失敗

最常見：Jetson 換 Wi-Fi 後，Ethernet driver 沒重新拿 192.168.123.x。重啟 Jetson 或 `sudo systemctl restart NetworkManager`。

---

## J. Gateway 8080 分流診斷

`pawai doctor` 的 Gateway 8080 行可能顯示：

- `SKIP (no demo running)` — 正常，demo 沒跑時 gateway 不在
- `OK` — gateway 正常
- `FAIL` — 只在 `--expect-demo` 或 lock 顯示 running 時才出現

判斷哪一段壞：

```bash
# 從 Jetson 本機 curl
ssh jetson 'curl -fsS http://127.0.0.1:8080/health'

# 從你筆電（Tailscale）curl
curl -fsS http://$JETSON_TAILSCALE_IP:8080/health
```

| Jetson 本機 | 你筆電 | 診斷 |
|---|---|---|
| OK | FAIL | Tailscale 路徑問題（檢查 share / firewall） |
| FAIL | FAIL | Gateway crashed（看 `pawai logs gateway`） |
| OK | OK / Browser FAIL | Studio frontend `.env.local` 指錯 host |
```

- [ ] **Step 3: Add README lock + branch sections**

In `docs/pawai_cli/README.md` find the `demo start/stop` and `jetson deploy` sections; insert lock semantics info. Also add a new top-level section:

```markdown
### Lock 機制（多人共用 Jetson）

`$JETSON_REPO/.pawai-demo-lock` 是共用 Jetson 的 single source of truth：

- `state: starting` — `pawai demo start` 已 acquire lock，正在啟動
- `state: running` — start.sh 跑完，demo 正常運行
- `pawai demo stop` / start 失敗 — lock 移除

**stale 規則**：
- `starting` > 10 min → 視為啟動失敗，會 prompt 清掉
- `running` > 4 hr → 標 `STALE` 在 `pawai status`，**不**自動刪

### `-y` vs `--force`

| Flag | 跳一般 prompt？ | 可以搶別人 lock？ |
|---|---|---|
| `-y` | ✅ | ❌ |
| `--force` | ✅ | ✅ |

`pawai demo start --force` / `pawai demo stop --force` / `pawai jetson deploy --force` 都會搶。
明天現場接手別人 demo 前**請先溝通**。

### Branch mismatch

`rsync` 不同步 `.git/`，Jetson 上 git 狀態不代表實際跑的 code。`.pawai-last-deploy` 才是 runtime provenance。

`pawai status` 比對：
- **local branch**（你 checkout 的）
- **install branch**（`.pawai-last-deploy` 記錄的 deploy 來源）
- **dirty**（deploy 當下 working tree 是否有未 commit 改動）

不一致時印 `⚠ MISMATCH`。要讓兩邊一致 → 切到對的 branch 再 `pawai jetson deploy --module X`。
```

- [ ] **Step 4: Commit**

```bash
git add docs/pawai_cli/team-onboarding.md docs/pawai_cli/troubleshooting.md docs/pawai_cli/README.md
git commit -m "docs(cli): L2 — onboarding step 5 + rules, troubleshooting I/J, README lock/branch"
```

---

### L2 Acceptance Run

- [ ] **Manual two-shell simulation**

Shell A:
```bash
pawai demo start
# expect: writes starting lock, runs start.sh, transitions to running
pawai status
# expect: "Demo lock: owner: <you>@<host>, state: running"
```

Shell B (simulate teammate):
```bash
USER=teammate1 pawai demo start
# expect: prompt about Shell A's lock; answer "cancel"

USER=teammate1 pawai demo start -y
# expect: error "-y does not override another user's lock"; exit 2

USER=teammate1 pawai demo start --force
# expect: clears Shell A's lock, takes over

USER=teammate1 pawai demo stop
# expect: works (now it's their lock)

# back in Shell A, fake a stale lock by editing on Jetson manually
ssh jetson "cat > .pawai-demo-lock <<'EOF'
{\"user\":\"ghost\",\"host\":\"h\",\"branch\":\"b\",\"sha\":\"s\",\"state\":\"running\",\"start_time\":\"2026-05-13T00:00:00+00:00\",\"demo_mode\":\"full\",\"tmux_session\":\"demo\"}
EOF"
pawai status
# expect: STALE running flag, no auto-delete

# branch mismatch
git checkout -b test-branch
pawai jetson deploy --module brain
git checkout main
pawai status
# expect: ⚠ MISMATCH local=main install=test-branch
```

All boxes above checked → L2 done.

---

# Phase L3 — Convenience Helpers

**Acceptance gate:**
- `pawai docs brain` opens / prints architecture/0511/brain/brain.md
- `pawai docs unknown` lists valid module names
- `pawai contract check` runs local script if present; prints explicit fallback if absent
- `pawai contract check --jetson` runs against Jetson copy

---

### Task L3-1: `pawai docs <module>` command

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/modules.py` (add `arch_doc_path`)
- Modify: `tools/pawai_cli/pawai_cli/main.py` (add `docs` command)
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, fail**

- [ ] **Step 3: Implement**

In `tools/pawai_cli/pawai_cli/modules.py`, after `existing_docs`, add:

```python
_DOC_ALIASES: dict[str, str] = {
    "onboarding": "docs/pawai_cli/team-onboarding.md",
    "contract": "docs/contracts/interaction_contract.md",
}


def arch_doc_path(name: str, root: Path) -> Path | None:
    """Map module name to its architecture/0511/<name>/<name>.md (or alias target)."""
    if name in _DOC_ALIASES:
        path = root / _DOC_ALIASES[name]
        return path if path.exists() else None

    # Module: try architecture/0511/<name>/<name>.md, then architecture/0511/<name>.md
    candidates = [
        root / f"docs/pawai-brain/architecture/0511/{name}/{name}.md",
        root / f"docs/pawai-brain/architecture/0511/{name}.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def all_doc_targets() -> list[str]:
    """Names accepted by `pawai docs`."""
    return list(MODULES.keys()) + list(_DOC_ALIASES.keys())
```

In `tools/pawai_cli/pawai_cli/main.py`, add new command:

```python
@cli.command("docs")
@click.argument("target")
@click.option("--open", "open_doc", is_flag=True, help="Open in $EDITOR.")
def docs(target: str, open_doc: bool) -> None:
    """Open architecture / onboarding / contract docs by short name."""
    from .modules import arch_doc_path, all_doc_targets
    path = arch_doc_path(target, shell.repo_root())
    if path is None:
        click.echo(f"Unknown doc target '{target}'.")
        click.echo(f"Valid: {' '.join(sorted(all_doc_targets()))}")
        sys.exit(2)

    click.echo(str(path))
    if open_doc:
        editor = os.environ.get("EDITOR", "vi")
        shell.stream([editor, str(path)])
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k docs`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/modules.py tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): add pawai docs <module> for architecture/0511 + aliases"
```

---

### Task L3-2: `pawai contract check` (local-first, `--jetson` optional)

**Files:**
- Modify: `tools/pawai_cli/pawai_cli/main.py`
- Modify: `tools/pawai_cli/tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run, fail**

- [ ] **Step 3: Implement**

In `tools/pawai_cli/pawai_cli/main.py`:

```python
@cli.group("contract")
def contract() -> None:
    """Contract / schema checks."""


@contract.command("check")
@click.option("--jetson", is_flag=True, help="Run against Jetson deployed copy instead of local.")
def contract_check(jetson: bool) -> None:
    script_rel = "scripts/ci/check_topic_contracts.py"
    spec_md = "docs/contracts/interaction_contract.md"

    if jetson:
        rc = shell.stream_remote(f"cd {shell.jetson_repo()} && python3 {script_rel}")
        sys.exit(rc)

    local_script = shell.repo_root() / script_rel
    if not local_script.exists():
        click.echo(f"✗ Local checker not found: {script_rel}")
        click.echo(f"  Spec reference: {spec_md}")
        click.echo(f"  Run on Jetson instead: pawai contract check --jetson")
        sys.exit(2)
    rc = shell.stream(["python3", str(local_script)], cwd=shell.repo_root())
    sys.exit(rc)
```

- [ ] **Step 4: Run, pass**

Run: `python3 -m pytest tools/pawai_cli/tests/test_cli.py -v -k contract`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tools/pawai_cli/pawai_cli/main.py tools/pawai_cli/tests/test_cli.py
git commit -m "feat(cli): pawai contract check — local-first + --jetson + explicit fallback"
```

---

### Task L3-3: L3 docs (README new commands + tools/pawai_cli/README sync)

**Files:**
- Modify: `docs/pawai_cli/README.md`
- Modify: `tools/pawai_cli/README.md`

- [ ] **Step 1: Add `pawai docs` + `pawai contract check` rows to README**

In `docs/pawai_cli/README.md` §3 「指令參考」 table, add:

```markdown
| [`pawai docs <target>`](#docs) | 開架構/onboarding/契約文件 |
| [`pawai contract check`](#contract) | 跑 topic schema 驗證（預設 local，--jetson 跑遠端） |
```

Add detail sections:

```markdown
### docs

```bash
pawai docs brain          # → docs/pawai-brain/architecture/0511/brain/brain.md
pawai docs face           # → architecture/0511/face.md
pawai docs gesture        # → architecture/0511/gesture/gesture.md
pawai docs onboarding     # → docs/pawai_cli/team-onboarding.md
pawai docs contract       # → docs/contracts/interaction_contract.md
pawai docs brain --open   # 用 $EDITOR 開
```

Unknown target → 印列表 + exit 2。

### contract

```bash
pawai contract check          # 本機 branch 跑 scripts/ci/check_topic_contracts.py
pawai contract check --jetson # 透過 SSH 在 Jetson deployed copy 跑
```

預設 local-first 是為了驗證**你目前 branch** 的契約一致性 — Jetson 上的 install 可能是別人的 stale sync。
```

- [ ] **Step 2: Sync `tools/pawai_cli/README.md`**

Replace the daily flow with up-to-date commands and add pointer:

```markdown
## Daily Flow

```bash
pawai doctor
pawai status
pawai docs <module>
pawai jetson deploy --module <module>
pawai demo start
pawai demo stop
pawai logs <module> --lines 200
```

## Modules

`face`, `speech`, `gesture`, `pose`, `object`, `nav`, `brain`, `studio`.

## Canonical Docs

Full manual: `docs/pawai_cli/README.md`
Troubleshooting: `docs/pawai_cli/troubleshooting.md`
Team onboarding: `docs/pawai_cli/team-onboarding.md`
```

- [ ] **Step 3: Commit**

```bash
git add docs/pawai_cli/README.md tools/pawai_cli/README.md
git commit -m "docs(cli): L3 — README pawai docs + contract sections + tools/README sync"
```

---

### L3 Acceptance Run

- [ ] **Manual**

```bash
pawai docs brain          # prints path
pawai docs onboarding     # prints docs/pawai_cli/team-onboarding.md
pawai docs zzz            # exit 2 + lists valid
pawai contract check      # runs local script if present, else explicit fallback
python3 -m pytest tools/pawai_cli/tests/ -v   # all green end-to-end
```

All boxes checked → L3 done.

---

# Final Cross-Cutting Check

- [ ] **Run full test suite**

```bash
python3 -m pytest tools/pawai_cli/tests/ -v
```

Expected: all tests green (test_cli + test_network + test_lock + test_cache).

- [ ] **Five-person dry run on Roy's machine**

Simulate via env override (no real teammates needed yet):

```bash
USER=alice pawai doctor
USER=bob pawai demo start
USER=alice pawai demo start          # should prompt
USER=alice pawai demo start --force  # should take over
USER=alice pawai demo stop
USER=bob pawai demo stop             # should refuse (lock is alice's now)
```

- [ ] **Skill verification**

After all CLI flags landed, AI agents using `pawai-cli` skill should now discover `--fix` / `--deep` / `--force` via `pawai --help`. No skill patch needed (self-discovery design).

Optional: update `.claude/skills/pawai-cli/references/command-reference.md` to mention the now-real flags. Nice-to-have, not blocking.

- [ ] **Final commit summarizing the team-prep effort**

If you made any final tweaks not captured in per-task commits:

```bash
git add -A
git commit -m "chore(cli): team-prep round complete (L1+L2+L3 + docs)"
```

---

# Self-Review (executor checks before final commit push)

- [ ] All new flags appear in `pawai <command> --help` output
- [ ] No real `.env.local` / `.ssh/config` / `tailscale` state was mutated during testing
- [ ] `pawai doctor` with no flags makes zero OpenRouter API calls
- [ ] Lock file format readable from Jetson with `ssh jetson 'cat $JETSON_REPO/.pawai-demo-lock'`
- [ ] `pawai status` shows lock + branch mismatch + topology summary
- [ ] All four troubleshooting chapters (G/H/I/J) are present
- [ ] `team-onboarding.md` covers steps 0-5 + rules
- [ ] `.env.local.example` no longer hardcodes `100.83.109.89`
