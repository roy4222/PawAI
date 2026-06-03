"""Pure demo readiness verdict logic.

This module intentionally avoids Click, ROS, shell, and filesystem access so it
can run in the fast benchmark gate. It only evaluates a snapshot object against
the deploy manifest SHA and the published fail-closed truth table.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .scoreboard_schema import CAPABILITY_META

READY = "ready"
NOT_READY = "not_ready"

EXPECTED_CAPABILITY_COUNT = 15
AGE_WARNING_DAYS = 3
AGE_STRONG_WARNING_DAYS = 7

CANONICAL_CAPABILITY_IDS = tuple(CAPABILITY_META.keys())
MAINLINE_CAPABILITY_IDS = tuple(
    capability_id
    for capability_id, meta in CAPABILITY_META.items()
    if meta.get("claim_level") == "mainline"
)


def evaluate_readiness(
    snapshot: dict[str, Any] | None,
    *,
    deploy_sha: str | None,
    now_iso: str,
    schema: dict[str, Any] | None = None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate whether a baseline snapshot is trustworthy for demo use.

    Hard failures always produce ``not_ready`` and cannot be bypassed by
    overrides. Advisory conditions produce warnings only.
    """
    reasons: list[str] = []
    warnings: list[str] = []
    override_record = _override_record(overrides, now_iso)

    if snapshot is None:
        reasons.append("snapshot_missing")
        return _result(reasons, warnings, override_record)

    if schema is not None:
        schema_error = _schema_error(snapshot, schema)
        if schema_error:
            reasons.append(schema_error)

    if snapshot.get("run_trusted") is not True:
        reasons.append("run_untrusted")

    preflight_status = snapshot.get("layer0_preflight_status")
    if preflight_status == "pass_with_warnings":
        warnings.append("layer0_preflight_pass_with_warnings")
    elif preflight_status != "pass":
        if preflight_status == "fail":
            reasons.append("layer0_preflight_fail")
        else:
            reasons.append(f"layer0_preflight_invalid:{preflight_status or 'missing'}")

    _evaluate_sha(snapshot, deploy_sha, reasons)
    _evaluate_capabilities(snapshot, reasons)
    _evaluate_age(snapshot.get("timestamp"), now_iso, warnings)

    return _result(reasons, warnings, override_record)


def _result(
    reasons: list[str],
    warnings: list[str],
    override_record: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "verdict": NOT_READY if reasons else READY,
        "reasons": reasons,
        "warnings": warnings,
        "override": override_record,
    }


def _schema_error(snapshot: dict[str, Any], schema: dict[str, Any]) -> str | None:
    try:
        import jsonschema
    except Exception as exc:  # pragma: no cover - depends on runtime packaging.
        return f"schema_validator_unavailable:{exc.__class__.__name__}"

    try:
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(snapshot)
    except jsonschema.ValidationError as exc:
        path = ".".join(str(part) for part in exc.absolute_path) or "<root>"
        return f"schema_invalid:{path}:{exc.message}"
    except Exception as exc:  # Defensive fail-closed path for malformed schemas.
        return f"schema_invalid:<validator>:{exc.__class__.__name__}"
    return None


def _evaluate_sha(
    snapshot: dict[str, Any],
    deploy_sha: str | None,
    reasons: list[str],
) -> None:
    snapshot_sha = _clean_sha(snapshot.get("git_commit") or snapshot.get("wsl_commit"))
    deploy_sha_clean = _clean_sha(deploy_sha)

    if not deploy_sha_clean:
        reasons.append("deploy_sha_missing")
        return
    if not snapshot_sha:
        reasons.append("snapshot_sha_missing")
        return
    if not _sha_matches(snapshot_sha, deploy_sha_clean):
        reasons.append(f"sha_mismatch:snapshot={snapshot_sha}:deploy={deploy_sha_clean}")


def _clean_sha(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _sha_matches(snapshot_sha: str, deploy_sha: str) -> bool:
    return snapshot_sha.startswith(deploy_sha) or deploy_sha.startswith(snapshot_sha)


def _evaluate_capabilities(snapshot: dict[str, Any], reasons: list[str]) -> None:
    capabilities = snapshot.get("capabilities")
    if not isinstance(capabilities, dict):
        reasons.append("capabilities_missing")
        return

    if len(capabilities) < EXPECTED_CAPABILITY_COUNT:
        reasons.append(
            f"capability_list_incomplete:{len(capabilities)}/{EXPECTED_CAPABILITY_COUNT}"
        )

    missing = [
        capability_id
        for capability_id in CANONICAL_CAPABILITY_IDS
        if capability_id not in capabilities
    ]
    if missing:
        reasons.append("capability_list_missing:" + ",".join(missing))

    for capability_id in MAINLINE_CAPABILITY_IDS:
        capability = capabilities.get(capability_id)
        if not isinstance(capability, dict):
            reasons.append(f"mainline_capability_missing:{capability_id}")
            continue

        grade = capability.get("grade")
        if not grade:
            reasons.append(f"mainline_grade_missing:{capability_id}")
            continue
        if grade != "pass":
            # Hard fail-closed: a mainline capability that is not "pass" blocks
            # readiness outright. Previously only the failure_reason-missing case
            # was checked, so a documented non-pass grade leaked through as ready.
            reasons.append(f"mainline_capability_not_pass:{capability_id}:{grade}")
        if grade != "pass" and not str(capability.get("failure_reason", "")).strip():
            reasons.append(f"mainline_failure_reason_missing:{capability_id}")


def _evaluate_age(timestamp: Any, now_iso: str, warnings: list[str]) -> None:
    if not timestamp:
        warnings.append("snapshot_timestamp_missing")
        return

    timestamp_dt = _parse_iso(str(timestamp))
    now_dt = _parse_iso(now_iso)
    if timestamp_dt is None:
        warnings.append("snapshot_timestamp_invalid")
        return
    if now_dt is None:
        warnings.append("now_timestamp_invalid")
        return

    age_seconds = (now_dt - timestamp_dt).total_seconds()
    if age_seconds < 0:
        warnings.append("snapshot_timestamp_in_future")
        return

    age_days = age_seconds / 86400
    if age_days > AGE_STRONG_WARNING_DAYS:
        warnings.append(f"snapshot_age_strong_warning:{age_days:.1f}d")
    elif age_days > AGE_WARNING_DAYS:
        warnings.append(f"snapshot_age_warning:{age_days:.1f}d")


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _override_record(
    overrides: dict[str, Any] | None,
    now_iso: str,
) -> dict[str, Any] | None:
    if not overrides:
        return None
    if not (overrides.get("accept_warnings") or overrides.get("force_ready")):
        return None
    return {
        "override": True,
        "operator": str(overrides.get("operator") or ""),
        "reason": str(overrides.get("reason") or ""),
        "timestamp": str(overrides.get("timestamp") or now_iso),
    }
