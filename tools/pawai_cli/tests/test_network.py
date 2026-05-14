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


# ─── pawai net wifi MVP ──────────────────────────────────────────────────

from pawai_cli.network import (
    wifi_list,
    wifi_status,
    wifi_connect,
    wifi_forget,
    WifiNetwork,
    WifiStatus,
)


def test_wifi_list_parses_nmcli_terse():
    stdout = (
        "*:LM306:87:WPA2\n"
        ":FJU-5GHz:65:WPA2 802.1X\n"
        ":eduroam:60:WPA2 802.1X\n"
        ":FJU-Guest:64:\n"
    )
    with patch("pawai_cli.network.shell.run_remote", return_value=_result(stdout, 0)):
        nets = wifi_list()
    assert nets is not None
    ssids = [n.ssid for n in nets]
    # in-use first, then by signal descending
    assert ssids[0] == "LM306"
    assert nets[0].in_use is True
    assert nets[0].signal == 87
    assert nets[0].security == "WPA2"
    # FJU-5GHz (65) before FJU-Guest (64) before eduroam (60)
    assert ssids[1:] == ["FJU-5GHz", "FJU-Guest", "eduroam"]
    # FJU-Guest empty SECURITY → "--"
    fju_guest = next(n for n in nets if n.ssid == "FJU-Guest")
    assert fju_guest.security == "--"


def test_wifi_list_handles_escaped_colon_in_ssid():
    stdout = ":Cafe\\:WiFi:42:WPA2\n"
    with patch("pawai_cli.network.shell.run_remote", return_value=_result(stdout, 0)):
        nets = wifi_list()
    assert nets is not None
    assert nets[0].ssid == "Cafe:WiFi"


def test_wifi_list_returns_none_on_ssh_fail():
    with patch("pawai_cli.network.shell.run_remote", return_value=_result("", 255)):
        assert wifi_list() is None


def test_wifi_status_composes_from_three_sources():
    conn_out = "LM306:wlp1s0:802-11-wireless\nWired connection 1:eno1:802-3-ethernet\n"
    addr_out = "    inet 192.168.0.113/24 brd 192.168.0.255 scope global wlp1s0\n"
    # ip route get 8.8.8.8 — kernel's actually-selected route, single line
    route_out = "8.8.8.8 via 192.168.0.1 dev wlp1s0 src 192.168.0.113 uid 1000\n"

    calls = []

    def fake_run_remote(cmd, timeout=None):
        calls.append(cmd)
        if "connection show --active" in cmd:
            return _result(conn_out, 0)
        if "ip -4 addr show" in cmd:
            return _result(addr_out, 0)
        if "ip route get 8.8.8.8" in cmd:
            return _result(route_out, 0)
        return _result("", 1)

    with patch("pawai_cli.network.shell.run_remote", side_effect=fake_run_remote):
        st = wifi_status()

    assert st is not None
    assert st.ssid == "LM306"
    assert st.iface == "wlp1s0"
    assert st.ip == "192.168.0.113"
    assert st.default_route_via_wifi is True
    assert len(calls) == 3


def test_wifi_status_route_via_ethernet_when_kernel_picks_eno1():
    """If `ip route get 8.8.8.8` picks eno1 even though wifi is up,
    default_route_via_wifi must be False (catches Go2 wired stealing default)."""
    conn_out = "LM306:wlp1s0:802-11-wireless\nWired connection 1:eno1:802-3-ethernet\n"
    addr_out = "    inet 192.168.0.113/24 brd 192.168.0.255 scope global wlp1s0\n"
    # Kernel picked eno1 despite Wi-Fi being up (lower metric on Go2 wired)
    route_out = "8.8.8.8 via 192.168.123.1 dev eno1 src 192.168.123.10 uid 1000\n"

    def fake_run_remote(cmd, timeout=None):
        if "connection show --active" in cmd:
            return _result(conn_out, 0)
        if "ip -4 addr show" in cmd:
            return _result(addr_out, 0)
        if "ip route get 8.8.8.8" in cmd:
            return _result(route_out, 0)
        return _result("", 1)

    with patch("pawai_cli.network.shell.run_remote", side_effect=fake_run_remote):
        st = wifi_status()

    assert st is not None
    assert st.ssid == "LM306"
    assert st.iface == "wlp1s0"
    assert st.default_route_via_wifi is False


def test_wifi_status_returns_no_wifi_when_no_wireless_active():
    conn_out = "Wired connection 1:eno1:802-3-ethernet\n"
    with patch("pawai_cli.network.shell.run_remote", return_value=_result(conn_out, 0)):
        st = wifi_status()
    assert st is not None
    assert st.ssid is None
    assert st.iface is None
    assert st.default_route_via_wifi is False


def test_wifi_connect_quotes_ssid_and_password():
    """Malicious-looking SSID / password must be shlex.quoted before SSH embed."""
    sent_cmds = []

    def fake_run_remote(cmd, timeout=None):
        sent_cmds.append(cmd)
        return _result("Device 'wlp1s0' successfully activated", 0)

    with patch("pawai_cli.network.shell.run_remote", side_effect=fake_run_remote):
        ok, msg = wifi_connect(ssid="A' B; rm -rf /", password="p$x'y")
    assert ok is True
    # shlex.quote produces single-quoted bash-safe form
    assert "'A'\"'\"' B; rm -rf /'" in sent_cmds[0]
    assert "'p$x'\"'\"'y'" in sent_cmds[0]


def test_wifi_connect_translates_secret_rejected():
    err = "Error: Connection activation failed: (4) Secrets were required, but not provided."
    with patch("pawai_cli.network.shell.run_remote",
               return_value=_result("", 4)) as _:
        # also need stderr — patch via Result
        pass
    with patch(
        "pawai_cli.network.shell.run_remote",
        return_value=Result(code=4, stdout="", stderr=err),
    ):
        ok, msg = wifi_connect("LM306", "wrong-password")
    assert ok is False
    assert "rejected" in msg.lower()


def test_wifi_connect_translates_nopasswd_missing():
    err = "sudo: a password is required\n"
    with patch(
        "pawai_cli.network.shell.run_remote",
        return_value=Result(code=1, stdout="", stderr=err),
    ):
        ok, msg = wifi_connect("LM306", "x")
    assert ok is False
    assert "NOPASSWD" in msg
    assert "sudoers.d/pawai-nmcli" in msg


def test_wifi_forget_success():
    with patch(
        "pawai_cli.network.shell.run_remote",
        return_value=_result("Connection 'LM306' (xxx) successfully deleted.", 0),
    ):
        ok, msg = wifi_forget("LM306")
    assert ok is True
    assert "LM306" in msg


def test_wifi_forget_unknown_connection():
    err = "Error: unknown connection 'NoSuchSSID'.\n"
    with patch(
        "pawai_cli.network.shell.run_remote",
        return_value=Result(code=10, stdout="", stderr=err),
    ):
        ok, msg = wifi_forget("NoSuchSSID")
    assert ok is False
    assert "No saved profile" in msg
