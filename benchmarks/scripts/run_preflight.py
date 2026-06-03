import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from jsonschema import validate
from jsonschema.exceptions import ValidationError


def classify_status(overall: str, warn_count: int) -> str:
    if overall == "PASS" and warn_count == 0:
        return "pass"
    if overall == "PASS" and warn_count > 0:
        return "pass_with_warnings"
    if overall in {"FAIL", "ERROR"}:
        return "fail"
    raise ValueError(f"未知的 verify overall：{overall!r}")


def build_preflight_result(report: dict, version_snapshot: str | None,
                           verify_report_path: str) -> dict:
    summary = report.get("summary", {})
    return {
        "status": classify_status(report["overall"], int(summary.get("warn", 0))),
        "checks": report.get("checks", []),
        "details": {
            "overall": report["overall"],
            "summary": summary,
            "version_snapshot": version_snapshot,
            "verify_report_path": verify_report_path,
        },
    }


def read_version_snapshot(repo: Path, manifest_arg: str | None) -> str | None:
    env_manifest = os.environ.get("PAWAI_DEPLOY_MANIFEST")
    if manifest_arg:
        candidates = [Path(manifest_arg).expanduser()]
    elif env_manifest:
        candidates = [Path(env_manifest).expanduser()]
    else:
        candidates = [Path("~/elder_and_dog/.pawai-last-deploy").expanduser(),
                      repo / ".pawai-last-deploy"]
    for path in candidates:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            pass
    return None


def parse_verify_stdout(stdout: str) -> dict:
    try:
        report = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"verify.py stdout 不是合法 JSON：{exc}") from exc
    overall = report.get("overall")
    if overall not in {"PASS", "FAIL", "ERROR"}:
        raise RuntimeError(f"verify.py report overall 不合法：{overall!r}")
    if not isinstance(report.get("summary"), dict) or not isinstance(report.get("checks"), list):
        raise RuntimeError("verify.py report 缺少 summary 或 checks")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="產生 PawAI baseline Layer-0 preflight 結果")
    parser.add_argument("--out", default="artifacts/baseline/preflight_result.json")
    parser.add_argument("--profile", default="demo")
    parser.add_argument("--skill-dir")
    parser.add_argument("--manifest")
    args = parser.parse_args()

    repo = Path(__file__).resolve().parents[2]
    skill_dir = Path(args.skill_dir).resolve() if args.skill_dir else repo / ".claude/skills/jetson-verify"
    verify_py = skill_dir / "scripts/verify.py"
    log_dir = Path("artifacts/baseline/logs")
    completed = subprocess.run(
        ["python3", str(verify_py), "--profile", args.profile, "--output-dir", str(log_dir)],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    if completed.stderr:
        sys.stderr.write(completed.stderr)

    try:
        result = build_preflight_result(
            parse_verify_stdout(completed.stdout),
            read_version_snapshot(repo, args.manifest),
            str(log_dir / "latest.json"),
        )
        schema_path = repo / ".claude/schemas/preflight_result.schema.json"
        validate(instance=result, schema=json.loads(schema_path.read_text(encoding="utf-8")))
    except (RuntimeError, ValidationError, OSError, ValueError) as exc:
        print(f"ERROR: preflight_result 驗證失敗：{exc}", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    out_path = out_path if out_path.is_absolute() else repo / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["status"] in {"pass", "pass_with_warnings"} else 1


if __name__ == "__main__":
    sys.exit(main())
