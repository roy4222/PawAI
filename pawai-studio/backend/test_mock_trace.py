#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Tests for mock Evidence Center trace endpoints.

The mock server must let the Studio frontend develop against the trace session,
export, and report APIs without a running gateway.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi.testclient import TestClient
from httpx import Request, Response

sys.path.insert(0, str(Path(__file__).resolve().parent))


def _patch_testclient_for_sandbox() -> None:
    """Run TestClient requests in-process when AnyIO's portal is unavailable.

    The local sandbox currently hangs in anyio.from_thread.start_blocking_portal()
    even for a minimal FastAPI app. The tests still instantiate FastAPI's
    TestClient; this swaps only the request transport used during pytest.
    """
    if getattr(TestClient, "_pawai_direct_asgi_patch", False):
        return

    def direct_request(self, method: str, url, **kwargs):
        target = str(url)
        if target.startswith("http://") or target.startswith("https://"):
            split = urlsplit(target)
            path = split.path or "/"
            raw_query = split.query
        else:
            path, _, raw_query = target.partition("?")
            path = path or "/"

        params = kwargs.get("params")
        if params:
            param_query = urlencode(params, doseq=True)
            raw_query = "&".join(part for part in (raw_query, param_query) if part)

        headers = [(b"host", b"testserver")]
        for key, value in (kwargs.get("headers") or {}).items():
            headers.append((str(key).lower().encode(), str(value).encode()))

        body = b""
        if "json" in kwargs:
            body = json.dumps(kwargs["json"]).encode("utf-8")
            if not any(key == b"content-type" for key, _ in headers):
                headers.append((b"content-type", b"application/json"))
            headers.append((b"content-length", str(len(body)).encode()))

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": raw_query.encode(),
            "root_path": getattr(self, "root_path", ""),
            "headers": headers,
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "state": getattr(self, "app_state", {}).copy(),
        }

        sent = False
        status_code = 500
        response_headers = []
        chunks = []

        async def receive():
            nonlocal sent
            if sent:
                return {"type": "http.disconnect"}
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}

        async def send(message):
            nonlocal status_code, response_headers
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = [
                    (key.decode(), value.decode()) for key, value in message.get("headers", [])
                ]
            elif message["type"] == "http.response.body":
                chunks.append(message.get("body", b""))

        import asyncio

        asyncio.run(self.app(scope, receive, send))
        request = Request(method.upper(), f"http://testserver{path}")
        return Response(
            status_code=status_code,
            headers=response_headers,
            content=b"".join(chunks),
            request=request,
        )

    TestClient.request = direct_request
    TestClient._pawai_direct_asgi_patch = True


_patch_testclient_for_sandbox()


def _patch_asyncio_to_thread_for_sandbox() -> None:
    import asyncio

    if getattr(asyncio, "_pawai_direct_to_thread_patch", False):
        return

    async def direct_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    asyncio.to_thread = direct_to_thread
    asyncio._pawai_direct_to_thread_patch = True


_patch_asyncio_to_thread_for_sandbox()


def _reload_mock_server():
    """Reload mock_server with current module-level fixtures."""
    if "mock_server" in sys.modules:
        del sys.modules["mock_server"]
    import mock_server  # noqa: F401

    return sys.modules["mock_server"]


def _walk_values(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)
    else:
        yield value


class TestMockTraceEndpoints(unittest.TestCase):
    def setUp(self):
        self.ms = _reload_mock_server()
        self.client = TestClient(self.ms.app)

    def _first_session_id(self) -> str:
        resp = self.client.get("/api/trace/sessions")
        self.assertEqual(resp.status_code, 200)
        sessions = resp.json()["sessions"]
        self.assertTrue(sessions)
        return sessions[0]["session_id"]

    def test_trace_sessions_returns_required_metadata(self):
        resp = self.client.get("/api/trace/sessions")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["sessions"])

        required = {"session_id", "started_ts", "line_count", "file_size", "parts"}
        for session in body["sessions"]:
            self.assertTrue(required.issubset(session.keys()))

    def test_trace_export_streams_valid_ndjson_with_all_verdicts(self):
        session_id = self._first_session_id()
        resp = self.client.get("/api/trace/export", params={"session": session_id})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers["content-type"], "application/x-ndjson")

        events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]
        self.assertTrue(events)
        for event in events:
            self.assertTrue("verdict" in event or "kind" in event)

        verdicts = {event.get("verdict") for event in events}
        self.assertTrue({"accepted", "suppressed", "blocked"}.issubset(verdicts))

    def test_trace_export_rejects_invalid_session_id(self):
        resp = self.client.get("/api/trace/export", params={"session": "../bad"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json(), {"error": "invalid_session"})

    def test_trace_report_json_and_markdown_shapes(self):
        session_id = self._first_session_id()
        resp = self.client.get("/api/trace/report", params={"session": session_id})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()

        required = {
            "session_id",
            "event_count",
            "time_range",
            "verdict_distribution",
            "top_suppressed_gates",
            "shadow_divergence",
        }
        self.assertTrue(required.issubset(body.keys()))
        self.assertEqual(body["session_id"], session_id)
        self.assertIsInstance(body["verdict_distribution"], dict)
        self.assertIsInstance(body["shadow_divergence"]["total"], int)

        md_resp = self.client.get(
            "/api/trace/report",
            params={"session": session_id, "format": "md"},
        )
        self.assertEqual(md_resp.status_code, 200)
        self.assertTrue(md_resp.headers["content-type"].startswith("text/markdown"))
        self.assertIn(session_id, md_resp.text)

    def test_trace_export_does_not_leak_raw_real_names(self):
        session_id = self._first_session_id()
        resp = self.client.get("/api/trace/export", params={"session": session_id})
        self.assertEqual(resp.status_code, 200)
        events = [json.loads(line) for line in resp.text.splitlines() if line.strip()]

        banned_names = {"Roy", "小明", "小華", "Alice", "Bob"}
        leaked = [
            value
            for event in events
            for value in _walk_values(event)
            if isinstance(value, str) and value in banned_names
        ]
        self.assertEqual(leaked, [])


if __name__ == "__main__":
    unittest.main()
