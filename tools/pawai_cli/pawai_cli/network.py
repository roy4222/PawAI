from __future__ import annotations

import json
import re
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
