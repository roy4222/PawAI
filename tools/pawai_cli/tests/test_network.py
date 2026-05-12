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
