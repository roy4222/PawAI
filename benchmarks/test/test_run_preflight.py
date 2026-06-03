import importlib.util
import json
from pathlib import Path

from jsonschema import validate


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "benchmarks/scripts/run_preflight.py"
SCHEMA_PATH = REPO_ROOT / ".claude/schemas/preflight_result.schema.json"


def _load_run_preflight():
    spec = importlib.util.spec_from_file_location("run_preflight", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_classify_status_all_branches():
    run_preflight = _load_run_preflight()
    assert run_preflight.classify_status("PASS", 0) == "pass"
    assert run_preflight.classify_status("PASS", 2) == "pass_with_warnings"
    assert run_preflight.classify_status("FAIL", 0) == "fail"
    assert run_preflight.classify_status("ERROR", 0) == "fail"


def test_mock_preflight_result_validates_against_schema():
    run_preflight = _load_run_preflight()
    report = {
        "overall": "PASS",
        "summary": {"pass": 2, "warn": 1, "fail": 0, "skip": 0, "error": 0},
        "checks": [
            {"id": "jetson.ssh_reachable", "status": "PASS", "blocking": True},
            {"id": "topic_contract_ok", "status": "WARN", "blocking": False},
        ],
    }
    result = run_preflight.build_preflight_result(
        report,
        version_snapshot='{"git_sha_full":"abc123"}',
        verify_report_path="artifacts/baseline/logs/latest.json",
    )
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    validate(instance=result, schema=schema)
