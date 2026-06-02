"""Capability baseline result schema + 靜態 capability metadata (v0.1)。

一筆 JSONL record = 一次 scenario-run。claim_level / risk_role 是 capability 的「靜態屬性」，
存 CAPABILITY_META，不進每筆 record（避免重複）。run-level meta 帶 version_snapshot 雙 sha
（Jetson 無 .git，dev commit != Jetson install）。
"""
from __future__ import annotations

import subprocess
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

SCHEMA_VERSION = "scoreboard-0.1"

# capability_id -> 靜態屬性（claim_level/risk_role/dependency_role 是作者標的，不是量出來的）
# dependency_role（2026-06-01 加）：fail 時依賴它的 demo skill 怎麼降級：
#   trigger -> 不觸發該 skill；content -> skill 觸發但內容降級；safety_guard -> 禁 motion；
#   actuation -> 禁該動作；evidence -> 只影響 Studio 顯示。與 risk_role 正交。
#   v0.1 不被 grader 消費（design-only）。
CAPABILITY_META: dict[str, dict[str, str]] = {
    "face.recognition": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "evidence_only",
        "dependency_role": "content",
    },
    "voice.command": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "convenience",
        "dependency_role": "trigger",
    },
    "voice.stop": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "convenience",
        "dependency_role": "trigger",
    },
    "gesture.wave": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "convenience",
        "dependency_role": "trigger",
    },
    "object.cup": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "evidence_only",
        "dependency_role": "content",
    },
    "nav.safe_stop": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "safety_critical",
        "dependency_role": "safety_guard",
    },
    "nav.no_auto_resume": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "safety_critical",
        "dependency_role": "safety_guard",
    },
    "nav.short_move": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "actuation",
        "dependency_role": "actuation",
    },
    "nav.dynamic_avoidance": {
        "depth": "future",
        "claim_level": "future",
        "risk_role": "actuation",
        "dependency_role": "actuation",
    },
    "pose.basic": {
        "depth": "thin",
        "claim_level": "studio_only",
        "risk_role": "evidence_only",
        "dependency_role": "content",
    },
    "pose.fall": {
        "depth": "future",
        "claim_level": "future",
        "risk_role": "evidence_only",
        "dependency_role": "evidence",
    },
    "brain.skill_gate": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "safety_critical",
        "dependency_role": "safety_guard",
    },
    "brain.trace": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "evidence_only",
        "dependency_role": "evidence",
    },
    "studio.evidence": {
        "depth": "deep",
        "claim_level": "mainline",
        "risk_role": "evidence_only",
        "dependency_role": "evidence",
    },
    "cli.readiness": {
        "depth": "thin",
        "claim_level": "not_claimed",
        "risk_role": "safety_support",
        "dependency_role": "evidence",
    },
}


@dataclass
class CapabilityResult:
    # --- 識別 ---
    capability_id: str
    scenario_id: str
    run_id: str
    timestamp: str
    git_commit: str
    # --- 判定 ---
    expected_label: str
    predicted_label: str
    pass_fail: str
    confidence: Optional[float] = None
    distance_m: Optional[float] = None
    distance_source: str = "manual_declared"
    latency_ms: Optional[float] = None
    frame_age_ms: Optional[float] = None
    fps: Optional[float] = None
    false_trigger: bool = False
    stable_time_ms: Optional[float] = None
    # --- 資源（reuse JetsonMonitor 後填；v0.1 可留 None）---
    cpu_pct: Optional[float] = None
    gpu_pct: Optional[float] = None
    ram_mb: Optional[float] = None
    failure_reason: str = ""

    def to_record(self) -> dict:
        rec = asdict(self)
        rec["schema_version"] = SCHEMA_VERSION
        return rec


def _git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except Exception:
        return "unknown"


def _git_short() -> str:
    return _git(["rev-parse", "--short", "HEAD"])


def _is_stale(when_iso: Optional[str], now_iso: Optional[str], stale_after_h: float) -> bool:
    """Return True when deploy manifest time is missing, invalid, or too old."""
    if not when_iso:
        return True
    try:
        now_source = now_iso or datetime.now(timezone.utc).isoformat()
        now = datetime.fromisoformat(now_source.replace("Z", "+00:00"))
        when = datetime.fromisoformat(when_iso.replace("Z", "+00:00"))
        return (now - when).total_seconds() > stale_after_h * 3600
    except Exception:
        return True


def current_run_meta(
    jetson_manifest: Optional[dict] = None,
    demo_profile_env: Optional[dict] = None,
    layer0_preflight: Optional[dict] = None,
    now_iso: Optional[str] = None,
    stale_after_h: float = 6.0,
) -> dict:
    """Return run-level metadata with WSL commit and Jetson install snapshot.

    無 manifest 或與 dev commit 不符 -> version_mismatch=True（fail-closed）。
    F2：Layer 0 preflight 非 pass/pass_with_warnings -> run_trusted=False。
    """
    manifest = jetson_manifest or {}
    wsl_commit = _git_short()
    wsl_dirty = bool(_git(["status", "--porcelain"]))
    branch = _git(["rev-parse", "--abbrev-ref", "HEAD"])
    jetson_sha = manifest.get("git_sha_full")
    manifest_exists = jetson_manifest is not None
    mismatch = (jetson_sha is None) or (
        not jetson_sha.startswith(wsl_commit) if wsl_commit != "unknown" else True
    )
    preflight_status = (layer0_preflight or {}).get("status", "unknown")
    run_trusted = preflight_status in ("pass", "pass_with_warnings")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "wsl_commit": wsl_commit,
        "wsl_dirty": wsl_dirty,
        "branch": branch,
        "jetson_install_sha": jetson_sha,
        "jetson_deploy_ts": manifest.get("when"),
        "jetson_sync_method": manifest.get("sync_method"),
        "jetson_dirty": bool(manifest.get("dirty")),
        "manifest_exists": manifest_exists,
        "version_mismatch": bool(mismatch),
        "version_stale": _is_stale(manifest.get("when"), now_iso, stale_after_h),
        "layer0_preflight_status": preflight_status,
        "run_trusted": run_trusted,
        "demo_profile_env": demo_profile_env or {},
    }
