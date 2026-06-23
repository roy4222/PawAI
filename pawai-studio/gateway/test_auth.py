"""Unit tests for gateway access-control primitives (S0 hardening).

ROS-free: imports only auth.py, runs anywhere (CI fast-gate, WSL).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from auth import (  # noqa: E402
    AuthConfig,
    export_access,
    load_auth_config,
    origin_ok,
    requires_token,
    token_ok,
    token_query_ok,
)

TOKEN = "s3cret-shared"


# ── load_auth_config: defaults preserve today's open behaviour ──────────────
def test_defaults_are_open():
    cfg = load_auth_config({})
    assert cfg.host == "0.0.0.0"
    assert cfg.token == ""
    assert cfg.allowed_origins == ()
    assert cfg.auth_enabled is False
    assert cfg.origin_check_enabled is False
    assert cfg.cors_origins == ["*"]


def test_env_overrides():
    cfg = load_auth_config({
        "GATEWAY_HOST": "127.0.0.1",
        "GATEWAY_AUTH_TOKEN": TOKEN,
        "GATEWAY_ALLOWED_ORIGINS": "http://localhost:3001, http://203.0.113.1:3001 ",
    })
    assert cfg.host == "127.0.0.1"
    assert cfg.auth_enabled is True
    assert cfg.origin_check_enabled is True
    assert cfg.allowed_origins == ("http://localhost:3001", "http://203.0.113.1:3001")
    assert cfg.cors_origins == ["http://localhost:3001", "http://203.0.113.1:3001"]


def test_blank_env_values_treated_as_unset():
    cfg = load_auth_config({"GATEWAY_HOST": "  ", "GATEWAY_AUTH_TOKEN": "  ",
                            "GATEWAY_ALLOWED_ORIGINS": " , ,"})
    assert cfg.host == "0.0.0.0"
    assert cfg.auth_enabled is False
    assert cfg.allowed_origins == ()


# ── requires_token: only state-changing methods ─────────────────────────────
def test_requires_token_by_method():
    assert requires_token("POST") is True
    assert requires_token("put") is True
    assert requires_token("DELETE") is True
    assert requires_token("PATCH") is True
    assert requires_token("GET") is False
    assert requires_token("HEAD") is False
    assert requires_token("OPTIONS") is False   # CORS preflight must pass


# ── token_ok: Bearer header validation ──────────────────────────────────────
def test_token_disabled_allows_everything():
    assert token_ok(None, "") is True
    assert token_ok("garbage", "") is True


def test_token_valid_bearer():
    assert token_ok(f"Bearer {TOKEN}", TOKEN) is True
    assert token_ok(f"bearer {TOKEN}", TOKEN) is True   # case-insensitive scheme


def test_token_rejects_bad():
    assert token_ok(None, TOKEN) is False
    assert token_ok("", TOKEN) is False
    assert token_ok(f"Bearer {TOKEN}x", TOKEN) is False
    assert token_ok(TOKEN, TOKEN) is False              # missing "Bearer "
    assert token_ok(f"Basic {TOKEN}", TOKEN) is False
    assert token_ok("Bearer", TOKEN) is False           # no value


# ── token_query_ok: WebSocket ?token= ───────────────────────────────────────
def test_token_query():
    assert token_query_ok(None, "") is True             # disabled
    assert token_query_ok(TOKEN, TOKEN) is True
    assert token_query_ok(" " + TOKEN + " ", TOKEN) is True
    assert token_query_ok(None, TOKEN) is False
    assert token_query_ok("wrong", TOKEN) is False


# ── origin_ok: browser Origin allowlist ─────────────────────────────────────
def test_origin_disabled_allows_any():
    assert origin_ok("http://evil.example", ()) is True
    assert origin_ok(None, ()) is True


def test_origin_allowlist():
    allowed = ("http://localhost:3001", "http://203.0.113.1:3001")
    assert origin_ok("http://localhost:3001", allowed) is True
    assert origin_ok("http://203.0.113.1:3001", allowed) is True
    assert origin_ok("http://evil.example", allowed) is False
    assert origin_ok(None, allowed) is True             # curl/probe (no Origin) allowed


# ── export_access: trace-export gate (A-11 + T2B-0 PII ruling, 2026-06-12) ──
def test_export_access_auth_on_requires_token_even_for_get():
    # A-11: export has NO safe-method bypass — auth on + bad/missing token = 401.
    assert export_access(auth_enabled=True, header_token_ok=False, want_full=False) == 401
    assert export_access(auth_enabled=True, header_token_ok=False, want_full=True) == 401
    assert export_access(auth_enabled=True, header_token_ok=True, want_full=False) == 0
    assert export_access(auth_enabled=True, header_token_ok=True, want_full=True) == 0


def test_export_access_full_export_requires_auth_system_on():
    # T2B-0: full (unredacted) export ALWAYS needs an authenticated caller —
    # with the token system off nobody can authenticate → 403, PII stays redacted.
    assert export_access(auth_enabled=False, header_token_ok=True, want_full=True) == 403
    assert export_access(auth_enabled=False, header_token_ok=False, want_full=True) == 403


def test_export_access_default_open_posture_redacted_only():
    # S0-2 default-off posture: redacted export stays reachable without a token.
    assert export_access(auth_enabled=False, header_token_ok=False, want_full=False) == 0


def test_authconfig_is_frozen():
    cfg = AuthConfig(host="0.0.0.0", token="", allowed_origins=())
    try:
        cfg.host = "x"  # type: ignore[misc]
    except Exception:
        return
    raise AssertionError("AuthConfig should be immutable")
