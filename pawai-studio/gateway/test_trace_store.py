"""Unit tests for the Evidence Center trace store (system Phase 2 T2B-1).

ROS-free: imports only trace_store.py, runs anywhere (CI fast-gate Invocation 8,
WSL). Covers JSONL persistence, rotation, retention, queue flush, the env
kill-switch, the T2B-0 PII redaction ruling and the export line iterator.
"""
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from trace_store import (  # noqa: E402
    PII_DETAIL_KEYS,
    TraceStore,
    iter_export_lines,
    redact_trace_event,
    store_enabled,
    trace_dir,
)


def _ev(ts: float = 100.0, **over) -> dict:
    ev = {
        "v": 1, "ts": ts, "decision_id": "face-abc123", "node": "brain_node",
        "kind": "policy_decision", "verdict": "suppressed",
        "gate": "greet_cooldown", "reason": "cooldown:greet:Roy",
        "detail": {
            "gate": "greet_cooldown", "reason": "cooldown:greet:Roy",
            "demo_phase": "all", "active_plan": "wiggle",
            "pending_confirm": "IDLE:", "cooldown_remaining_s": 12.5,
            "source_summary": "identity=Roy conf=0.93",
        },
    }
    ev.update(over)
    return ev


# ── env config ───────────────────────────────────────────────────────────────

def test_store_enabled_default_on_with_kill_switch():
    assert store_enabled({}) is True
    assert store_enabled({"PAWAI_TRACE_STORE_ENABLED": "0"}) is False
    assert store_enabled({"PAWAI_TRACE_STORE_ENABLED": "false"}) is False
    assert store_enabled({"PAWAI_TRACE_STORE_ENABLED": "1"}) is True


def test_trace_dir_env_override_and_default(tmp_path):
    assert trace_dir({"PAWAI_TRACE_DIR": str(tmp_path / "x")},
                     repo_root=tmp_path) == tmp_path / "x"
    assert trace_dir({}, repo_root=tmp_path) == tmp_path / "runtime" / "traces"


# ── append / flush / JSONL ───────────────────────────────────────────────────

def test_append_flush_writes_full_jsonl(tmp_path):
    store = TraceStore(tmp_path, session_id="s1", autostart=False)
    store.append(_ev(ts=1.0))
    store.append(_ev(ts=2.0, verdict="accepted"))
    store.flush()
    lines = (tmp_path / "s1.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    # Disk copy is FULL (local-only) — PII fields present verbatim (T2B-0).
    assert json.loads(lines[0])["detail"]["source_summary"] == "identity=Roy conf=0.93"
    assert json.loads(lines[1])["verdict"] == "accepted"


def test_append_is_enqueue_only_until_flush(tmp_path):
    store = TraceStore(tmp_path, session_id="s1", autostart=False)
    store.append(_ev())
    assert not (tmp_path / "s1.jsonl").exists()
    store.flush()
    assert (tmp_path / "s1.jsonl").exists()


def test_append_never_raises_on_garbage(tmp_path):
    store = TraceStore(tmp_path, session_id="s1", autostart=False)
    store.append({"ts": object()})       # not JSON-serializable
    store.flush()                        # must not raise; garbage dropped


def test_background_writer_thread_and_close(tmp_path):
    store = TraceStore(tmp_path, session_id="s1", autostart=True,
                       flush_interval_s=0.05)
    try:
        assert any(t.daemon for t in threading.enumerate()
                   if t.name == "trace-store-writer")
        store.append(_ev())
    finally:
        store.close()                     # close() flushes + joins
    assert (tmp_path / "s1.jsonl").exists()
    assert not any(t.name == "trace-store-writer" and t.is_alive()
                   for t in threading.enumerate())


# ── rotation / retention ─────────────────────────────────────────────────────

def test_rotation_when_file_exceeds_max_bytes(tmp_path):
    store = TraceStore(tmp_path, session_id="s1", autostart=False, max_bytes=200)
    for i in range(20):
        store.append(_ev(ts=float(i)))
        store.flush()
    files = sorted(p.name for p in tmp_path.glob("s1*.jsonl"))
    assert len(files) >= 2, files          # rotated past 200 bytes
    assert "s1.jsonl" in files


def test_retention_prunes_oldest_beyond_max_sessions(tmp_path):
    import os
    for i in range(25):
        p = tmp_path / f"old-{i:02d}.jsonl"
        p.write_text("{}\n", encoding="utf-8")
        os.utime(p, (1000 + i, 1000 + i))
    store = TraceStore(tmp_path, session_id="s-new", autostart=False,
                       max_sessions=20)
    store.append(_ev())
    store.flush()
    remaining = sorted(p.name for p in tmp_path.glob("*.jsonl"))
    assert len(remaining) == 20
    assert "s-new.jsonl" in remaining
    assert "old-00.jsonl" not in remaining     # oldest pruned
    assert "old-24.jsonl" in remaining


# ── PII redaction (T2B-0 Roy ruling 2026-06-12) ─────────────────────────────

def test_redact_masks_pii_detail_keys_and_keeps_safe_summary():
    out = redact_trace_event(_ev())
    assert out["detail"]["source_summary"] == "[private]"
    # Safe summary fields stay visible:
    assert out["detail"]["gate"] == "greet_cooldown"
    assert out["detail"]["demo_phase"] == "all"
    assert out["detail"]["cooldown_remaining_s"] == 12.5
    assert out["gate"] == "greet_cooldown"
    assert out["kind"] == "policy_decision" and out["verdict"] == "suppressed"


def test_redact_masks_name_in_reason_but_keeps_structure():
    out = redact_trace_event(_ev())
    assert out["reason"] == "cooldown:greet:[private]"
    assert out["detail"]["reason"] == "cooldown:greet:[private]"
    out2 = redact_trace_event(_ev(reason="identity:roy"))
    assert out2["reason"] == "identity:[private]"
    out3 = redact_trace_event(_ev(reason="gate:executing"))
    assert out3["reason"] == "gate:executing"          # structural reason untouched
    out4 = redact_trace_event(_ev(reason="phase:s3_object:gesture"))
    assert out4["reason"] == "phase:s3_object:gesture"


def test_redact_masks_transcript_like_keys():
    ev = _ev()
    ev["detail"].update({"transcript": "我想喝水", "text": "hello",
                         "name": "Roy", "image_path": "/data/x.jpg"})
    out = redact_trace_event(ev)
    for key in ("transcript", "text", "name", "image_path", "source_summary"):
        assert out["detail"][key] == "[private]", key


def test_redact_is_pure_and_shadow_fields_survive():
    ev = _ev()
    ev["detail"].update({"shadow": True, "ism_state": "executing",
                         "ism_verdict": "suppress", "ism_reason": "gate:executing"})
    before = json.dumps(ev, sort_keys=True)
    out = redact_trace_event(ev)
    assert json.dumps(ev, sort_keys=True) == before    # input not mutated
    assert out["detail"]["shadow"] is True
    assert out["detail"]["ism_reason"] == "gate:executing"


def test_pii_keys_constant_covers_roy_ruling():
    for key in ("source_summary", "transcript", "text", "name", "identity",
                "image_path", "image", "full_text"):
        assert key in PII_DETAIL_KEYS


# ── export iterator ──────────────────────────────────────────────────────────

def _write_session(tmp_path, name, events):
    store = TraceStore(tmp_path, session_id=name, autostart=False)
    for ev in events:
        store.append(ev)
    store.flush()


def test_iter_export_lines_since_and_redact(tmp_path):
    _write_session(tmp_path, "a", [_ev(ts=10.0), _ev(ts=20.0)])
    _write_session(tmp_path, "b", [_ev(ts=30.0)])
    all_lines = [json.loads(line) for line in iter_export_lines(tmp_path)]
    assert len(all_lines) == 3
    assert all(ev["detail"]["source_summary"] == "[private]" for ev in all_lines)

    since = [json.loads(line) for line in iter_export_lines(tmp_path, since=15.0)]
    assert sorted(ev["ts"] for ev in since) == [20.0, 30.0]

    full = [json.loads(line) for line in iter_export_lines(tmp_path, redact=False)]
    assert any(ev["detail"]["source_summary"].startswith("identity=") for ev in full)


def test_iter_export_lines_skips_garbage_and_missing_dir(tmp_path):
    (tmp_path / "bad.jsonl").write_text("not-json\n{\"ts\": 5}\n", encoding="utf-8")
    lines = [json.loads(line) for line in iter_export_lines(tmp_path)]
    assert len(lines) == 1 and lines[0]["ts"] == 5
    assert list(iter_export_lines(tmp_path / "nope")) == []
