"""jetson-verify main executor.

Reads YAML profile -> runs checks via transport -> outputs JSON + summary.

Usage:
    python3 verify.py --profile smoke [--output-dir logs/jetson-verify/]

Exit codes: 0 = PASS, 1 = FAIL, 2 = ERROR/config
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from transport import detect_target_env, exec_on_target

# -- Expect parser -----------------------------------------------------------

def evaluate_expect(stdout_stripped: str, expect: str) -> bool:
    """Evaluate stdout against an expect expression.

    Supported operators (v0):
      ">= N", "<= N", "== N"  -- numeric comparison
      "contains TEXT"          -- substring match
      "nonempty"               -- non-empty after strip

    Returns True if expectation met, False if not.
    Raises ValueError on parse failure (non-numeric, unknown operator).
    """
    if expect == "nonempty":
        return len(stdout_stripped.strip()) > 0

    if expect.startswith("contains "):
        text = expect[len("contains "):]
        return text in stdout_stripped

    for op in (">=", "<=", "=="):
        if expect.startswith(op):
            threshold = float(expect[len(op):].strip())
            value = float(stdout_stripped.strip())
            if op == ">=":
                return value >= threshold
            elif op == "<=":
                return value <= threshold
            else:
                return value == threshold

    raise ValueError(f"Unknown expect operator: {expect!r}")


# -- Check runner ------------------------------------------------------------

STATUS_PASS = "PASS"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"
STATUS_ERROR = "ERROR"


def run_single_check(check: dict, env: str) -> dict:
    """Execute one check, return result record."""
    check_id = check["id"]
    blocking = check["blocking"]
    timeout = check.get("timeout_sec", 10)
    template = check.get("message_template", "")

    start = time.monotonic()

    # -- Precondition --
    if "precondition" in check:
        rc, _, _ = exec_on_target(check["precondition"], env, timeout_sec=timeout)
        if rc == -1 or rc == -2 or rc > 1:
            elapsed = int((time.monotonic() - start) * 1000)
            reason = ("transport failure" if rc == -1
                      else "timeout" if rc == -2
                      else f"precondition error (rc={rc})")
            return {
                "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
                "value": None, "message": f"precondition error: {reason}",
                "duration_ms": elapsed,
            }
        if rc == 1:
            elapsed = int((time.monotonic() - start) * 1000)
            return {
                "id": check_id, "status": STATUS_SKIP, "blocking": blocking,
                "value": None, "message": "precondition not met",
                "duration_ms": elapsed,
            }

    # -- Main command --
    rc, stdout, stderr = exec_on_target(check["command"], env, timeout_sec=timeout)
    elapsed = int((time.monotonic() - start) * 1000)

    if rc == -1:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": "transport failure",
            "duration_ms": elapsed,
        }
    if rc == -2:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"timeout after {timeout}s",
            "duration_ms": elapsed,
        }
    if rc > 0:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"command failed (rc={rc}): {stderr.strip()[:120]}",
            "duration_ms": elapsed,
        }

    # -- Evaluate expect --
    value = stdout.strip()
    try:
        passed = evaluate_expect(value, check["expect"])
    except ValueError as e:
        return {
            "id": check_id, "status": STATUS_ERROR, "blocking": blocking,
            "value": None, "message": f"expect parse error: {e}",
            "duration_ms": elapsed,
        }

    if passed:
        status = STATUS_PASS
    else:
        # FAIL only from blocking checks; non-blocking -> WARN
        status = STATUS_FAIL if blocking else STATUS_WARN

    message = template.replace("{value}", value) if value else template
    return {
        "id": check_id, "status": status, "blocking": blocking,
        "value": value, "message": message,
        "duration_ms": elapsed,
    }


# -- Profile loader ----------------------------------------------------------

def load_profile(profile_name: str, skill_dir: Path) -> dict:
    """Load and validate a YAML profile. Raises SystemExit on error."""
    profile_path = skill_dir / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        print(f"ERROR: profile not found: {profile_path}", file=sys.stderr)
        sys.exit(2)

    try:
        with open(profile_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: YAML parse error: {e}", file=sys.stderr)
        sys.exit(2)

    if not data or not isinstance(data.get("checks"), list):
        print(f"ERROR: profile '{profile_name}' has no checks (stub profile?)", file=sys.stderr)
        sys.exit(2)

    min_checks = data.get("min_checks", 1)
    if len(data["checks"]) < min_checks:
        print(f"ERROR: profile '{profile_name}' has {len(data['checks'])} checks, min {min_checks}",
              file=sys.stderr)
        sys.exit(2)

    return data


# -- Output ------------------------------------------------------------------

def print_summary(profile: str, target: str, results: list, overall: str, duration_ms: int):
    """Print human-readable summary to stderr."""
    W = sys.stderr.write
    W(f"jetson-verify | profile={profile} | target={target}\n")
    W("\u2500" * 50 + "\n")
    for r in results:
        tag = f"[{r['status']}]"
        msg = r.get("message", "")
        dur = f"  ({r['duration_ms']}ms)" if r["status"] != STATUS_SKIP else ""
        W(f"{tag} {r['id']} \u2014 {msg}{dur}\n")
    W("\u2500" * 50 + "\n")
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    parts = [f"{s}={counts.get(s, 0)}" for s in ["PASS", "WARN", "FAIL", "SKIP", "ERROR"]]
    W("  ".join(parts) + "\n")
    W(f"Overall: {overall} ({duration_ms}ms)\n")


def write_json_output(report: dict, output_dir: Path):
    """Write JSON to file + update latest.json symlink."""
    output_dir.mkdir(parents=True, exist_ok=True)
    ts = report["timestamp"].replace(":", "").replace("-", "").replace("T", "_").split("+")[0]
    filename = f"verify_{ts}.json"
    filepath = output_dir / filename
    with open(filepath, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    latest = output_dir / "latest.json"
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    latest.symlink_to(filename)


# -- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="jetson-verify: deployment health checks")
    parser.add_argument("--profile", required=True, help="Profile name (e.g., smoke)")
    parser.add_argument("--output-dir", default="logs/jetson-verify",
                        help="Directory for JSON output (default: logs/jetson-verify)")
    args = parser.parse_args()

    skill_dir = Path(__file__).resolve().parent.parent
    profile_data = load_profile(args.profile, skill_dir)
    env = detect_target_env()

    # SSH connectivity check for remote
    if env == "remote_jetson":
        rc, _, err = exec_on_target("echo ok", env, timeout_sec=5)
        if rc != 0:
            print(f"ERROR: cannot reach jetson-nano: {err}", file=sys.stderr)
            sys.exit(2)

    # Run checks
    total_start = time.monotonic()
    results = []
    for check in profile_data["checks"]:
        result = run_single_check(check, env)
        results.append(result)
    total_ms = int((time.monotonic() - total_start) * 1000)

    # Compute overall (priority: ERROR > blocking FAIL > PASS)
    has_error = any(r["status"] == STATUS_ERROR for r in results)
    has_blocking_fail = any(r["status"] == STATUS_FAIL and r["blocking"] for r in results)

    if has_error:
        overall = "ERROR"
        exit_code = 2
    elif has_blocking_fail:
        overall = "FAIL"
        exit_code = 1
    else:
        overall = "PASS"
        exit_code = 0

    # Build report
    summary = {}
    for s in ["PASS", "WARN", "FAIL", "SKIP", "ERROR"]:
        summary[s.lower()] = sum(1 for r in results if r["status"] == s)

    tz = timezone(timedelta(hours=8))
    report = {
        "profile": args.profile,
        "target": env,
        "timestamp": datetime.now(tz).isoformat(),
        "overall": overall,
        "exit_code": exit_code,
        "duration_ms": total_ms,
        "summary": summary,
        "checks": results,
    }

    # Output: JSON to stdout, summary to stderr, JSON to file
    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    print_summary(args.profile, env, results, overall, total_ms)
    write_json_output(report, Path(args.output_dir))

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
