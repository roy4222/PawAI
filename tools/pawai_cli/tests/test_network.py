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
