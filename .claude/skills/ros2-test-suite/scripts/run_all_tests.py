#!/usr/bin/env python3
"""PawAI ROS2 Test Suite — run all package tests with summary."""

import argparse
import os
import re
import subprocess
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))))

PACKAGES = {
    "speech_processor": {
        "test_dir": "speech_processor/test",
        "quick": True,
    },
    "face_perception": {
        "test_dir": "face_perception/test",
        "quick": True,
    },
    "vision_perception": {
        "test_dir": "vision_perception/test",
        "quick": False,
    },
    "go2_robot_sdk": {
        "test_dir": "go2_robot_sdk/test",
        "quick": False,
    },
}


def run_tests(pkg_name: str, test_dir: str) -> dict:
    """Run pytest for a package and return results."""
    full_path = os.path.join(REPO_ROOT, test_dir)
    if not os.path.isdir(full_path):
        return {"status": "skipped", "reason": "no test directory", "passed": 0, "failed": 0, "errors": []}

    test_files = [f for f in os.listdir(full_path) if f.startswith("test_") and f.endswith(".py")]
    if not test_files:
        return {"status": "skipped", "reason": "no test files", "passed": 0, "failed": 0, "errors": []}

    start = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "pytest", full_path, "-q", "--tb=line", "--no-header"],
        capture_output=True, text=True, cwd=REPO_ROOT, timeout=60
    )
    elapsed = time.time() - start

    output = result.stdout + result.stderr
    passed = failed = 0

    # Parse pytest summary line: "X passed, Y failed in Z.ZZs"
    summary_match = re.search(r"(\d+) passed", output)
    if summary_match:
        passed = int(summary_match.group(1))
    fail_match = re.search(r"(\d+) failed", output)
    if fail_match:
        failed = int(fail_match.group(1))

    # Analyze failure reasons
    errors = []
    if failed > 0:
        if "ModuleNotFoundError" in output:
            mod_match = re.search(r"No module named '([^']+)'", output)
            mod_name = mod_match.group(1) if mod_match else "unknown"
            errors.append(f"ModuleNotFoundError: {mod_name} — needs colcon build")
        elif "AssertionError" in output or "assert " in output:
            errors.append("AssertionError — real test failure, needs bug fix")
        elif "ImportError" in output:
            errors.append("ImportError — API change or missing dependency")
        elif "FileNotFoundError" in output:
            errors.append("FileNotFoundError — missing model or data file")
        else:
            # Extract first failure line
            fail_lines = [l for l in output.split("\n") if "FAILED" in l]
            if fail_lines:
                errors.append(fail_lines[0].strip()[:120])

    status = "passed" if failed == 0 and passed > 0 else "failed" if failed > 0 else "skipped"
    return {
        "status": status,
        "passed": passed,
        "failed": failed,
        "elapsed": round(elapsed, 2),
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="PawAI ROS2 Test Suite")
    parser.add_argument("--quick", action="store_true", help="Only run quick packages (speech + face)")
    parser.add_argument("--packages", nargs="+", help="Specific packages to test")
    args = parser.parse_args()

    # Determine which packages to run
    if args.packages:
        targets = {k: v for k, v in PACKAGES.items() if k in args.packages}
    elif args.quick:
        targets = {k: v for k, v in PACKAGES.items() if v.get("quick")}
    else:
        targets = PACKAGES

    print("=" * 42)
    print("  PawAI Test Suite")
    print("=" * 42)

    total_passed = 0
    total_failed = 0
    results = {}

    for pkg_name, pkg_info in targets.items():
        print(f"\n  Running {pkg_name}...", end="", flush=True)
        r = run_tests(pkg_name, pkg_info["test_dir"])
        results[pkg_name] = r
        total_passed += r["passed"]
        total_failed += r["failed"]

        if r["status"] == "passed":
            print(f"\r  {pkg_name:<22} {r['passed']:>3} passed, {r['failed']:>3} failed  ({r['elapsed']}s)  \u2705")
        elif r["status"] == "failed":
            print(f"\r  {pkg_name:<22} {r['passed']:>3} passed, {r['failed']:>3} failed  ({r['elapsed']}s)  \u274c")
            for err in r["errors"]:
                print(f"    \u2514\u2500 {err}")
        else:
            print(f"\r  {pkg_name:<22}   \u2014 skipped ({r['reason']})  \u23ed\ufe0f")

    print("\n" + "=" * 42)
    print(f"  Total: {total_passed} passed, {total_failed} failed")

    if total_failed == 0 and total_passed > 0:
        print("  Result: ALL PASS \u2705")
    elif total_failed > 0:
        # Check if all failures are import errors
        all_import = all(
            any("colcon build" in e for e in r["errors"])
            for r in results.values() if r["status"] == "failed"
        )
        if all_import:
            print("  Result: PARTIAL PASS \u2014 some packages need colcon build")
        else:
            print("  Result: FAIL \u274c \u2014 real test failures found")
    else:
        print("  Result: NO TESTS RAN")

    print("=" * 42)
    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()
