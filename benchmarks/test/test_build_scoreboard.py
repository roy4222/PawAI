import json

from benchmarks.core.build_scoreboard import DEFAULT_CRITERIA, build_scoreboard


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _positive_round(capability_id, latency_ms=100):
    return {
        "capability_id": capability_id,
        "pass_fail": "pass",
        "false_trigger": False,
        "latency_ms": latency_ms,
        "scenario_kind": "positive",
    }


def _idle_round(capability_id, false_trigger=False):
    return {
        "capability_id": capability_id,
        "pass_fail": "pass",
        "false_trigger": false_trigger,
        "latency_ms": None,
        "scenario_kind": "idle",
    }


def _trusted_preflight(path):
    preflight = path / "preflight.json"
    preflight.write_text(json.dumps({"status": "pass"}), encoding="utf-8")
    return preflight


def test_build_scoreboard_preflight_pass_produces_snapshot(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(
        jsonl,
        [_positive_round("gesture.wave") for _ in range(3)]
        + [_idle_round("gesture.wave") for _ in range(2)],
    )
    preflight = _trusted_preflight(tmp_path)
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
        [_positive_round("gesture.wave") for _ in range(3)]
        + [_idle_round("gesture.wave") for _ in range(2)],
    )
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=None, out_path=str(out))
    snap = json.loads(out.read_text(encoding="utf-8"))
    assert snap["run_trusted"] is False
    assert snap["capabilities"]["gesture.wave"]["grade"] == "insufficient_data"


def test_gesture_wave_false_accept_gate_uses_idle_only_metric(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(
        jsonl,
        [_positive_round("gesture.wave") for _ in range(10)]
        + [_idle_round("gesture.wave", false_trigger=True), _idle_round("gesture.wave")],
    )
    preflight = _trusted_preflight(tmp_path)
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=str(preflight), out_path=str(out))

    cap = json.loads(out.read_text(encoding="utf-8"))["capabilities"]["gesture.wave"]
    assert cap["success_rate"] == 1.0
    assert cap["false_trigger_rate"] <= DEFAULT_CRITERIA["gesture.wave"][1].pass_min
    assert cap["unknown_false_accept_rate"] == 0.5
    assert cap["grade"] == "fail"


def test_voice_stop_requires_zero_false_negatives(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    missed_stop = _positive_round("voice.stop")
    missed_stop["pass_fail"] = "fail"
    _write_jsonl(
        jsonl,
        [_positive_round("voice.stop"), _positive_round("voice.stop"), missed_stop],
    )
    preflight = _trusted_preflight(tmp_path)
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=str(preflight), out_path=str(out))

    cap = json.loads(out.read_text(encoding="utf-8"))["capabilities"]["voice.stop"]
    assert cap["success_rate"] < DEFAULT_CRITERIA["voice.stop"][0].pass_min
    assert cap["grade"] != "pass"


def test_object_cup_false_accept_gate_uses_idle_only_metric(tmp_path):
    jsonl = tmp_path / "baseline_result.jsonl"
    _write_jsonl(
        jsonl,
        [_positive_round("object.cup") for _ in range(98)]
        + [_idle_round("object.cup", false_trigger=True), _idle_round("object.cup")],
    )
    preflight = _trusted_preflight(tmp_path)
    out = tmp_path / "snap.json"
    build_scoreboard(str(jsonl), preflight_path=str(preflight), out_path=str(out))

    cap = json.loads(out.read_text(encoding="utf-8"))["capabilities"]["object.cup"]
    assert cap["success_rate"] == 1.0
    assert cap["false_trigger_rate"] <= DEFAULT_CRITERIA["object.cup"][1].pass_min
    assert cap["unknown_false_accept_rate"] == 0.5
    assert cap["grade"] == "fail"
