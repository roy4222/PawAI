import json

from benchmarks.core.build_scoreboard import DEFAULT_CRITERIA, build_scoreboard


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def test_build_scoreboard_preflight_pass_produces_snapshot(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(
        jsonl,
        [
            {
                "capability_id": "gesture.wave",
                "pass_fail": "pass",
                "false_trigger": False,
                "latency_ms": 100,
                "scenario_kind": "positive",
            }
            for _ in range(3)
        ],
    )
    preflight = tmp_path / "preflight.json"
    preflight.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=str(preflight), out_path=str(out))
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["run_trusted"] is True
    assert len(snap["capabilities"]) == 15
    assert snap["capabilities"]["gesture.wave"]["grade"] == "pass"


def test_build_scoreboard_missing_preflight_is_failclosed(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(
        jsonl,
        [
            {
                "capability_id": "gesture.wave",
                "pass_fail": "pass",
                "false_trigger": False,
                "latency_ms": 100,
                "scenario_kind": "positive",
            }
            for _ in range(3)
        ],
    )
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=None, out_path=str(out))
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["run_trusted"] is False
    assert snap["capabilities"]["gesture.wave"]["grade"] == "insufficient_data"
