"""Gateway access-control primitives — ROS-free, unit-testable (S0 hardening).

Addresses findings GW-01..05 / EXP-01/05 / SEC-02 / GW-04 (CSWSH): the Studio
gateway today binds 0.0.0.0 with no auth and `CORS=*`, exposing every
state-changing endpoint (skill_request / text_input / nav/*) to the whole
LAN/tailnet and any browser origin.

Design constraint — the 6/18 demo freeze: the live demo's browser reaches the
gateway cross-host via a Tailscale IP, and the gateway is launched from a frozen
skill script. So enforcement is **env-gated and OFF by default** — with no env
set, behaviour is byte-identical to today (host 0.0.0.0, no token, CORS *).
Operators turn protection on post-freeze by setting:

    GATEWAY_HOST=127.0.0.1                  # or a specific iface; default 0.0.0.0
    GATEWAY_AUTH_TOKEN=<shared-secret>      # unset = no token required
    GATEWAY_ALLOWED_ORIGINS=http://a,http://b   # unset = allow any origin / CORS *

This module is the single source of that policy; studio_gateway.py only wires it.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass

# Methods that never mutate state — never require a token. OPTIONS must stay
# open or CORS preflight for browser POSTs breaks.
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class AuthConfig:
    host: str
    token: str                       # "" → auth disabled
    allowed_origins: tuple[str, ...]  # () → origin/CORS check disabled

    @property
    def auth_enabled(self) -> bool:
        return bool(self.token)

    @property
    def origin_check_enabled(self) -> bool:
        return bool(self.allowed_origins)

    @property
    def cors_origins(self) -> list[str]:
        """Value for CORSMiddleware allow_origins: the allowlist when set,
        else the legacy wildcard (preserves current demo behaviour)."""
        return list(self.allowed_origins) if self.allowed_origins else ["*"]


def load_auth_config(env: dict | None = None) -> AuthConfig:
    """Build AuthConfig from environment (defaults = today's open behaviour)."""
    import os
    e = os.environ if env is None else env
    host = (e.get("GATEWAY_HOST") or "").strip() or "0.0.0.0"
    token = (e.get("GATEWAY_AUTH_TOKEN") or "").strip()
    raw = (e.get("GATEWAY_ALLOWED_ORIGINS") or "").strip()
    origins = tuple(o.strip() for o in raw.split(",") if o.strip())
    return AuthConfig(host=host, token=token, allowed_origins=origins)


def requires_token(method: str) -> bool:
    """True if this HTTP method mutates state and must carry a token (when
    auth is enabled). GET/HEAD/OPTIONS are exempt."""
    return method.upper() not in _SAFE_METHODS


def token_ok(authorization_header: str | None, token: str) -> bool:
    """Validate an `Authorization: Bearer <token>` header (constant-time).
    token=="" means auth disabled → always True."""
    if not token:
        return True
    if not authorization_header:
        return False
    parts = authorization_header.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return secrets.compare_digest(parts[1].strip(), token)


def token_query_ok(token_param: str | None, token: str) -> bool:
    """Validate a WebSocket `?token=` query param (browsers can't set the
    Authorization header on a WS handshake). token=="" → auth disabled."""
    if not token:
        return True
    if not token_param:
        return False
    return secrets.compare_digest(token_param.strip(), token)


def origin_ok(origin: str | None, allowed: tuple[str, ...]) -> bool:
    """Validate a browser Origin header against the allowlist.
    - allowed==() → check disabled, always True.
    - origin is None → non-browser client (curl/probe sends no Origin) → allow;
      browsers always send Origin on cross-origin requests, so this only ever
      lets through same-host tooling, not a cross-site attacker page."""
    if not allowed:
        return True
    if origin is None:
        return True
    return origin in allowed
