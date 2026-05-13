from __future__ import annotations

import json
import re
import shlex
import shutil
from dataclasses import dataclass
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


@dataclass
class WifiNetwork:
    ssid: str
    signal: int       # 0-100
    security: str     # "WPA2" / "WPA2 802.1X" / "--"
    in_use: bool


@dataclass
class WifiStatus:
    ssid: Optional[str]               # None if no Wi-Fi connection active
    iface: Optional[str]              # "wlp1s0" etc.
    ip: Optional[str]                 # "192.168.0.113"
    default_route_via_wifi: bool


def _unescape_nmcli_terse(field: str) -> str:
    """nmcli -t escapes `:` and `\\` in field values. Reverse those."""
    return field.replace("\\:", ":").replace("\\\\", "\\")


def wifi_list() -> Optional[list[WifiNetwork]]:
    """Scan Jetson Wi-Fi networks via `nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list`.

    Returns None on SSH/nmcli failure. Empty list on no-networks-visible
    (rare but legal). SSIDs containing `:` are decoded back from nmcli's
    `\\:` escape form.
    """
    result = shell.run_remote(
        "nmcli -t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list 2>/dev/null",
        timeout=10,
    )
    if not result.ok:
        return None
    networks: list[WifiNetwork] = []
    for raw in result.stdout.splitlines():
        if not raw.strip():
            continue
        # Split on unescaped `:`. nmcli escapes embedded `:` as `\:`.
        parts = re.split(r"(?<!\\):", raw, maxsplit=3)
        if len(parts) != 4:
            continue
        in_use, ssid, signal, security = parts
        ssid = _unescape_nmcli_terse(ssid)
        security = _unescape_nmcli_terse(security) or "--"
        try:
            signal_int = int(signal)
        except ValueError:
            signal_int = 0
        if not ssid:
            continue  # skip hidden / empty-SSID rows
        networks.append(WifiNetwork(
            ssid=ssid, signal=signal_int, security=security,
            in_use=in_use.strip() == "*",
        ))
    # Sort: in-use first, then by signal descending
    networks.sort(key=lambda n: (not n.in_use, -n.signal))
    return networks


def wifi_status() -> Optional[WifiStatus]:
    """Compose Jetson Wi-Fi status from three SSH probes.

    Returns None on SSH failure of the first probe; partial-None fields if
    later probes fail (Wi-Fi may be associated but not yet have an IP).
    """
    conn = shell.run_remote(
        "nmcli -t -f NAME,DEVICE,TYPE connection show --active 2>/dev/null",
        timeout=8,
    )
    if not conn.ok:
        return None

    ssid: Optional[str] = None
    iface: Optional[str] = None
    for raw in conn.stdout.splitlines():
        parts = re.split(r"(?<!\\):", raw, maxsplit=2)
        if len(parts) != 3:
            continue
        name, device, ctype = parts
        if ctype == "802-11-wireless":
            ssid = _unescape_nmcli_terse(name)
            iface = device
            break

    if iface is None:
        return WifiStatus(ssid=None, iface=None, ip=None,
                          default_route_via_wifi=False)

    addr = shell.run_remote(f"ip -4 addr show {shlex.quote(iface)}", timeout=5)
    ip: Optional[str] = None
    if addr.ok:
        m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)", addr.stdout)
        ip = m.group(1) if m else None

    # Use the actual kernel-selected route to 8.8.8.8 instead of grepping the
    # default-route table — multiple defaults with different metrics can lie.
    route = shell.run_remote("ip route get 8.8.8.8", timeout=5)
    default_via_wifi = False
    if route.ok:
        m = re.search(r"\bdev\s+(\S+)", route.stdout)
        default_via_wifi = bool(m and m.group(1) == iface)

    return WifiStatus(ssid=ssid, iface=iface, ip=ip,
                      default_route_via_wifi=default_via_wifi)


def wifi_connect(ssid: str, password: str) -> tuple[bool, str]:
    """Connect Jetson to `ssid` with `password` via `sudo nmcli`.

    Returns (ok, user-actionable message). SSID + password are
    `shlex.quote`-protected before embedding into the SSH command string.

    Known nmcli failure modes are translated to plain messages:
      - Missing NOPASSWD sudo → setup guidance
      - Wrong password (rc=4 with "Secrets were required") → password rejected
      - Device missing → "Wi-Fi device not present"
    """
    safe_ssid = shlex.quote(ssid)
    safe_pw = shlex.quote(password)
    cmd = f"sudo -n nmcli device wifi connect {safe_ssid} password {safe_pw}"
    result = shell.run_remote(cmd, timeout=30)

    if result.ok:
        return True, f"✓ Connected to '{ssid}'."

    stderr_low = (result.stderr or "").lower()
    stdout_low = (result.stdout or "").lower()
    combined = stderr_low + " " + stdout_low

    # NOPASSWD missing — `sudo -n` fails immediately if password required.
    # Setup must happen at the Jetson local terminal (HDMI / console / serial)
    # — the same sudo failure that brought us here makes `ssh jetson "sudo …"`
    # equally unable to write the sudoers drop-in.
    if "sudo: a password is required" in combined \
            or "a terminal is required" in combined \
            or "password is required" in combined:
        return False, (
            "✗ sudo nmcli needs NOPASSWD on Jetson. One-time setup —\n"
            "  run this **on the Jetson local terminal** (HDMI / console / serial,\n"
            "  NOT via this CLI; the SSH non-TTY path is what just failed):\n"
            "\n"
            "    sudo bash -c \"echo 'jetson ALL=(ALL) NOPASSWD: /usr/bin/nmcli' \\\n"
            "      > /etc/sudoers.d/pawai-nmcli && chmod 440 /etc/sudoers.d/pawai-nmcli\"\n"
            "\n"
            "  Then retry: pawai net wifi connect <SSID>"
        )

    if "secrets were required" in combined \
            or "passwords or encryption keys are required" in combined \
            or "no network with ssid" in combined and "found" in combined:
        # Wrong password or no signal — both surface as nmcli rc=4
        if "secrets were required" in combined or "encryption keys" in combined:
            return False, (
                f"✗ Wi-Fi password for '{ssid}' was rejected. Double-check, "
                "then retry: pawai net wifi connect <SSID>"
            )

    if "not a wi-fi device" in combined or "no wi-fi device" in combined:
        return False, "✗ Jetson has no Wi-Fi device available (wlp1s0 missing?)."

    if "no network with ssid" in combined:
        return False, (
            f"✗ SSID '{ssid}' not visible. Run `pawai net wifi list` to see "
            "what's in range."
        )

    # Catch-all: surface raw stderr so users can copy-paste to troubleshoot
    msg = (result.stderr or result.stdout or "unknown nmcli error").strip()
    return False, f"✗ nmcli connect failed: {msg}"


def wifi_forget(ssid: str) -> tuple[bool, str]:
    """Delete saved Wi-Fi profile by SSID/connection name on Jetson.

    `nmcli connection delete <name>` matches by connection name, which for
    `nmcli device wifi connect <SSID>` flow is the SSID itself.
    """
    safe_ssid = shlex.quote(ssid)
    cmd = f"sudo -n nmcli connection delete {safe_ssid}"
    result = shell.run_remote(cmd, timeout=10)

    if result.ok:
        return True, f"✓ Forgot Wi-Fi profile '{ssid}'."

    combined = ((result.stderr or "") + " " + (result.stdout or "")).lower()
    if "sudo: a password is required" in combined \
            or "a terminal is required" in combined \
            or "password is required" in combined:
        return False, (
            "✗ sudo nmcli needs NOPASSWD on Jetson. Run setup on the Jetson "
            "local terminal first; see `pawai net wifi connect` error for the "
            "exact `/etc/sudoers.d/pawai-nmcli` command."
        )
    if "unknown connection" in combined or "no such" in combined:
        return False, f"✗ No saved profile named '{ssid}'."

    msg = (result.stderr or result.stdout or "unknown nmcli error").strip()
    return False, f"✗ nmcli delete failed: {msg}"


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
