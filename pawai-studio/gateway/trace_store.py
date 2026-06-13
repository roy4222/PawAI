"""Evidence Center trace store — ROS-free, unit-testable (system Phase 2 T2B-1).

Roy D5 ruling (2026-06-10): trace 的單一真相 = pawai_contracts schema + gateway
JSONL。Brain 只發射、gateway 只落盤呈現、CLI 只讀取匯出。This module is the
gateway's "落盤" half: studio_gateway.py wires it to the /brain/trace bridge.

T2B-0 rulings (Roy 2026-06-12, AFK instruction):
  - PII conservative default: safe summary fields stay visible; name /
    transcript / image path / full text are PRIVATE by default. The on-disk
    JSONL keeps the FULL event (local-only evidence); everything that leaves
    the machine through the WS bridge or the default export is run through
    redact_trace_event() first.
  - Export auth: see auth.export_access() — token required even on GET when
    auth is on; full (unredacted) export refuses unless the token system is on.

Threading: the gateway's ROS executor thread calls append() — that is enqueue
ONLY (no file I/O on the hot path). A daemon writer thread flushes every
flush_interval_s; close() joins it. Nothing here ever raises into the caller.

Env:
  PAWAI_TRACE_STORE_ENABLED=0|false   kill-switch (default on; off = pure
                                      bridge, byte-identical to pre-T2B gateway)
  PAWAI_TRACE_DIR=<path>              override the default <repo>/runtime/traces
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import Counter, deque
from collections.abc import Iterator
from pathlib import Path

DEFAULT_MAX_BYTES = 20 * 1024 * 1024     # ~20MB per file (Roy: 20MB × 20 sessions)
DEFAULT_MAX_SESSIONS = 20                # newest N .jsonl files kept
PRIVATE = "[private]"

# detail keys that may carry PII (T2B-0). Masked — key kept so analysts can see
# the field existed without seeing the value.
PII_DETAIL_KEYS = frozenset({
    "source_summary", "transcript", "text", "name", "identity",
    "image_path", "image", "full_text",
})

# Names ride inside reason strings as "identity:roy" / "identity=roy" /
# "cooldown:greet:Roy". Mask the value segment, keep the structural prefix.
# Structural reasons ("gate:executing", "phase:s3_object:gesture") never match.
_PII_REASON_RE = re.compile(r"((?:identity|name|greet)[:=])[^:,\s]+")
_SESSION_PART_RE = re.compile(r"^(?P<session>[A-Za-z0-9_-]+)(?:\.(?P<part>[2-9]\d*|1\d+))?\.jsonl$")


def store_enabled(env: dict | None = None) -> bool:
    """Kill-switch (default ON — persistence is additive observability; the
    rollback story is env-off = pure bridge)."""
    e = os.environ if env is None else env
    return str(e.get("PAWAI_TRACE_STORE_ENABLED", "1")).strip().lower() \
        not in ("0", "false", "no", "off")


def trace_dir(env: dict | None = None, repo_root: Path | None = None) -> Path:
    """Trace directory: PAWAI_TRACE_DIR override, else <repo>/runtime/traces
    (the established Jetson runtime-data convention — never install/share)."""
    e = os.environ if env is None else env
    override = str(e.get("PAWAI_TRACE_DIR") or "").strip()
    if override:
        return Path(override).expanduser()
    root = repo_root if repo_root is not None else Path(__file__).resolve().parents[2]
    return root / "runtime" / "traces"


def redact_trace_event(ev: dict) -> dict:
    """Pure, conservative redaction (T2B-0): returns a new dict, never mutates.

    - detail keys in PII_DETAIL_KEYS → "[private]"
    - reason / detail.reason: name-bearing segments masked via _PII_REASON_RE
    - everything else (gate, kind, verdict, decision_id, ism_* shadow fields,
      demo_phase, cooldown_remaining_s, …) passes through — that is the "safe
      summary" Roy ruled visible.
    """
    out = dict(ev)
    reason = out.get("reason")
    if isinstance(reason, str):
        out["reason"] = _PII_REASON_RE.sub(r"\g<1>" + PRIVATE, reason)
    detail = out.get("detail")
    if isinstance(detail, dict):
        d = dict(detail)
        for key in d:
            if key in PII_DETAIL_KEYS:
                d[key] = PRIVATE
        d_reason = d.get("reason")
        if isinstance(d_reason, str):
            d["reason"] = _PII_REASON_RE.sub(r"\g<1>" + PRIVATE, d_reason)
        out["detail"] = d
    return out


class TraceStore:
    """Append-only JSONL store: runtime/traces/{session_id}.jsonl with size
    rotation ({session_id}.2.jsonl, …) and newest-N retention pruning."""

    def __init__(self, directory: Path | str, *, session_id: str | None = None,
                 max_bytes: int = DEFAULT_MAX_BYTES,
                 max_sessions: int = DEFAULT_MAX_SESSIONS,
                 flush_interval_s: float = 1.0, autostart: bool = True) -> None:
        self._dir = Path(directory)
        self._session_id = session_id or time.strftime("%Y%m%d-%H%M%S")
        self._max_bytes = int(max_bytes)
        self._max_sessions = int(max_sessions)
        self._flush_interval_s = float(flush_interval_s)
        self._queue: deque[str] = deque()
        self._q_lock = threading.Lock()
        self._io_lock = threading.Lock()
        self._part = 1
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if autostart:
            self._thread = threading.Thread(
                target=self._writer_loop, name="trace-store-writer", daemon=True
            )
            self._thread.start()

    # ── hot path (ROS executor thread) ────────────────────────────────────

    def append(self, event: dict) -> None:
        """Enqueue one event. No file I/O here; never raises."""
        try:
            line = json.dumps(event, ensure_ascii=False)
        except (TypeError, ValueError):
            return  # non-serializable garbage — drop, never break the bridge
        with self._q_lock:
            self._queue.append(line)

    # ── writer side ───────────────────────────────────────────────────────

    @property
    def current_path(self) -> Path:
        name = f"{self._session_id}.jsonl" if self._part == 1 \
            else f"{self._session_id}.{self._part}.jsonl"
        return self._dir / name

    def flush(self) -> None:
        """Drain the queue to disk now (writer thread or caller). Never raises."""
        with self._io_lock:
            with self._q_lock:
                if not self._queue:
                    return
                lines = list(self._queue)
                self._queue.clear()
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                path = self.current_path
                with path.open("a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                if path.stat().st_size >= self._max_bytes:
                    self._part += 1
                self._prune()
            except OSError:
                return  # disk trouble must never bubble into the gateway

    def close(self) -> None:
        """Stop the writer thread (if any) and do a final flush."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        self.flush()

    def _writer_loop(self) -> None:
        while not self._stop.wait(self._flush_interval_s):
            self.flush()
        self.flush()

    def _prune(self) -> None:
        """Keep the newest max_sessions .jsonl files, delete the rest."""
        files = sorted(self._dir.glob("*.jsonl"),
                       key=lambda p: p.stat().st_mtime, reverse=True)
        for stale in files[self._max_sessions:]:
            try:
                stale.unlink()
            except OSError:
                continue


def _iter_file_events(path: Path) -> Iterator[dict]:
    """Parse one JSONL file defensively: garbage lines / unreadable files skip."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            ev = json.loads(raw)
        except (ValueError, TypeError):
            continue
        if isinstance(ev, dict):
            yield ev


def _session_part(path: Path) -> tuple[str, int] | None:
    m = _SESSION_PART_RE.match(path.name)
    if not m:
        return None
    part = int(m.group("part") or "1")
    return m.group("session"), part


def valid_session_id(session_id: str) -> bool:
    """True when session_id matches the persisted trace filename session group."""
    return bool(session_id and _SESSION_PART_RE.fullmatch(f"{session_id}.jsonl"))


def _file_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def list_sessions(directory: Path | str) -> list[dict]:
    """Return redaction-free session stats for runtime/traces/*.jsonl.

    This endpoint needs only non-PII metadata: session_id, earliest event ts,
    valid event count, aggregate file size and the rotation part filenames.
    Raw trace payloads never leave this function.
    """
    d = Path(directory)
    if not d.is_dir():
        return []

    grouped: dict[str, list[tuple[int, Path]]] = {}
    for path in d.glob("*.jsonl"):
        parsed = _session_part(path)
        if parsed is None:
            continue
        session_id, part = parsed
        grouped.setdefault(session_id, []).append((part, path))

    sessions: list[dict] = []
    for session_id, part_paths in grouped.items():
        part_paths.sort(key=lambda item: item[0])
        started_ts: float | None = None
        line_count = 0
        file_size = 0
        parts: list[str] = []
        fallback_started = min((_file_mtime(path) for _, path in part_paths), default=0.0)

        for _, path in part_paths:
            parts.append(path.name)
            try:
                file_size += path.stat().st_size
            except OSError:
                continue
            for ev in _iter_file_events(path):
                line_count += 1
                ts = ev.get("ts")
                if isinstance(ts, (int, float)):
                    started_ts = float(ts) if started_ts is None else min(started_ts, float(ts))

        sessions.append({
            "session_id": session_id,
            "started_ts": started_ts if started_ts is not None else fallback_started,
            "line_count": line_count,
            "file_size": file_size,
            "parts": parts,
        })

    return sorted(sessions, key=lambda s: (s["started_ts"], s["session_id"]), reverse=True)


def iter_export_lines(directory: Path | str, since: float | None = None,
                      redact: bool = True) -> Iterator[str]:
    """Yield JSONL lines ("...json...\\n") for the export endpoint.

    Reads session files oldest-first (mtime), filters by event ts >= since,
    applies redact_trace_event unless redact=False (auth-gated by the caller —
    see auth.export_access).
    """
    d = Path(directory)
    if not d.is_dir():
        return
    for path in sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime):
        for ev in _iter_file_events(path):
            if since is not None:
                ts = ev.get("ts")
                if not isinstance(ts, (int, float)) or ts < since:
                    continue
            if redact:
                ev = redact_trace_event(ev)
            yield json.dumps(ev, ensure_ascii=False) + "\n"


def iter_session_lines(directory: Path | str, session_id: str,
                       since: float | None = None,
                       redact: bool = True) -> Iterator[str]:
    """Yield JSONL lines for one persisted session, in rotation part order."""
    if not valid_session_id(session_id):
        return
    d = Path(directory)
    if not d.is_dir():
        return

    part_paths: list[tuple[int, Path]] = []
    for path in d.glob("*.jsonl"):
        parsed = _session_part(path)
        if parsed is None:
            continue
        parsed_session, part = parsed
        if parsed_session == session_id:
            part_paths.append((part, path))

    for _, path in sorted(part_paths, key=lambda item: item[0]):
        for ev in _iter_file_events(path):
            if since is not None:
                ts = ev.get("ts")
                if not isinstance(ts, (int, float)) or ts < since:
                    continue
            if redact:
                ev = redact_trace_event(ev)
            yield json.dumps(ev, ensure_ascii=False) + "\n"


def _empty_session_summary(session_id: str) -> dict:
    return {
        "session_id": session_id,
        "event_count": 0,
        "time_range": {"start": None, "end": None},
        "verdict_distribution": {},
        "top_suppressed_gates": [],
        "shadow_divergence": {"total": 0, "by_gate": []},
    }


def summarize_session(directory: Path | str, session_id: str) -> dict:
    """Return a compact report summary for one persisted session.

    The read path intentionally consumes iter_session_lines(redact=True), then
    parses that redacted JSONL. Do not read fields from raw on-disk events here:
    this report feeds operators and Lane 1 analysis, so it must inherit the
    gateway redaction single source.
    """
    summary = _empty_session_summary(session_id)
    if not valid_session_id(session_id):
        return summary
    d = Path(directory)
    if not d.is_dir():
        return summary

    verdicts: Counter[str] = Counter()
    suppressed_gates: Counter[str] = Counter()
    divergence_by_gate: Counter[str] = Counter()
    start_ts: float | None = None
    end_ts: float | None = None

    for line in iter_session_lines(d, session_id, redact=True):
        try:
            redacted_ev = json.loads(line)
        except (TypeError, ValueError):
            continue
        if not isinstance(redacted_ev, dict):
            continue

        summary["event_count"] += 1

        ts = redacted_ev.get("ts")
        if isinstance(ts, (int, float)) and not isinstance(ts, bool):
            ts_f = float(ts)
            start_ts = ts_f if start_ts is None else min(start_ts, ts_f)
            end_ts = ts_f if end_ts is None else max(end_ts, ts_f)

        verdict = redacted_ev.get("verdict")
        if isinstance(verdict, str) and verdict:
            verdicts[verdict] += 1
            if verdict == "suppressed":
                gate = redacted_ev.get("gate")
                if isinstance(gate, str) and gate:
                    suppressed_gates[gate] += 1

        if redacted_ev.get("kind") != "candidate" or redacted_ev.get("gate") != "ism_shadow":
            continue
        detail = redacted_ev.get("detail")
        if not isinstance(detail, dict) or detail.get("shadow") is not True:
            continue
        ism_verdict = detail.get("ism_verdict")
        if not isinstance(ism_verdict, str) or not ism_verdict:
            continue

        would_act = ism_verdict in {"accept", "preempt"}
        legacy_action = detail.get("legacy_action")
        acted = isinstance(legacy_action, str) and (
            legacy_action.startswith("emitted")
            or legacy_action.startswith("confirm_requested")
        )
        if would_act == acted:
            continue
        legacy_gate = detail.get("legacy_gate")
        gate_key = legacy_gate if isinstance(legacy_gate, str) and legacy_gate else "(none)"
        divergence_by_gate[gate_key] += 1

    summary["time_range"] = {"start": start_ts, "end": end_ts}
    summary["verdict_distribution"] = dict(sorted(verdicts.items()))
    summary["top_suppressed_gates"] = [
        {"gate": gate, "count": count}
        for gate, count in sorted(suppressed_gates.items(), key=lambda item: (-item[1], item[0]))
    ]
    divergence_rows = [
        {"gate": gate, "count": count}
        for gate, count in sorted(divergence_by_gate.items(), key=lambda item: (-item[1], item[0]))
    ]
    summary["shadow_divergence"] = {
        "total": sum(divergence_by_gate.values()),
        "by_gate": divergence_rows,
    }
    return summary


def render_session_report_md(summary: dict) -> str:
    """Render summarize_session() output as compact Markdown. Pure, no I/O."""
    session_id = summary.get("session_id") or ""
    event_count = summary.get("event_count", 0)
    time_range = summary.get("time_range")
    if not isinstance(time_range, dict):
        time_range = {}
    start_ts = time_range.get("start")
    end_ts = time_range.get("end")

    lines = [
        "# Trace Session Report",
        "",
        f"- Session: `{session_id}`",
        f"- Event count / 事件數: {event_count}",
        f"- Time range / 時間範圍: {start_ts if start_ts is not None else 'n/a'} "
        f"to {end_ts if end_ts is not None else 'n/a'}",
        "",
        "## Verdict Distribution",
        "",
        "| Verdict | Count |",
        "|---|---:|",
    ]

    verdict_distribution = summary.get("verdict_distribution")
    if isinstance(verdict_distribution, dict) and verdict_distribution:
        for verdict, count in sorted(verdict_distribution.items()):
            lines.append(f"| `{verdict}` | {count} |")
    else:
        lines.append("| (none) | 0 |")

    lines.extend([
        "",
        "## Top Suppressed Gates",
        "",
        "| Gate | Count |",
        "|---|---:|",
    ])
    top_suppressed_gates = summary.get("top_suppressed_gates")
    if isinstance(top_suppressed_gates, list) and top_suppressed_gates:
        for row in top_suppressed_gates:
            if not isinstance(row, dict):
                continue
            lines.append(f"| `{row.get('gate', '')}` | {row.get('count', 0)} |")
    else:
        lines.append("| (none) | 0 |")

    shadow_divergence = summary.get("shadow_divergence")
    if not isinstance(shadow_divergence, dict):
        shadow_divergence = {}
    lines.extend([
        "",
        "## Shadow Divergence",
        "",
        f"- Total / 總數: {shadow_divergence.get('total', 0)}",
        "",
        "| Legacy gate | Count |",
        "|---|---:|",
    ])
    by_gate = shadow_divergence.get("by_gate")
    if isinstance(by_gate, list) and by_gate:
        for row in by_gate:
            if not isinstance(row, dict):
                continue
            lines.append(f"| `{row.get('gate', '')}` | {row.get('count', 0)} |")
    else:
        lines.append("| (none) | 0 |")

    return "\n".join(lines) + "\n"
