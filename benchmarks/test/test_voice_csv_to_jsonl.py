import importlib.util
from pathlib import Path


def _load_module():
    # benchmarks/scripts 不是 package，測試用檔案路徑直接載入。
    path = Path(__file__).resolve().parents[1] / "scripts" / "voice_csv_to_jsonl.py"
    spec = importlib.util.spec_from_file_location("voice_csv_to_jsonl", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


voice_csv_to_jsonl = _load_module()


def test_csv_row_to_record_voice_command_pass_with_latency():
    row = {
        "round_id": "1",
        "expected_intent": "sit",
        "intent": "sit",
        "e2e_latency_ms": "123.4",
        "match": "match",
        "status": "complete",
    }

    record = voice_csv_to_jsonl.csv_row_to_record(row, {"stop"}, "run-1", "abc123")

    assert record["capability_id"] == "voice.command"
    assert record["scenario_id"] == "voice_1"
    assert record["pass_fail"] == "pass"
    assert record["latency_ms"] == 123.4


def test_csv_row_to_record_voice_stop_miss_is_fail():
    row = {
        "round_id": "2",
        "expected_intent": "stop",
        "intent": "",
        "e2e_latency_ms": "200",
        "match": "miss",
        "status": "complete",
    }

    record = voice_csv_to_jsonl.csv_row_to_record(row, {"stop"}, "run-1", None)

    assert record["capability_id"] == "voice.stop"
    assert record["pass_fail"] == "fail"


def test_csv_row_to_record_skips_orphan_and_empty_expected_intent():
    orphan = {
        "round_id": "3",
        "expected_intent": "stop",
        "intent": "stop",
        "e2e_latency_ms": "100",
        "match": "match",
        "status": "orphan",
    }
    empty_expected = {
        "round_id": "4",
        "expected_intent": "",
        "intent": "stop",
        "e2e_latency_ms": "100",
        "match": "match",
        "status": "complete",
    }

    assert voice_csv_to_jsonl.csv_row_to_record(orphan, {"stop"}, "run-1", None) is None
    assert voice_csv_to_jsonl.csv_row_to_record(empty_expected, {"stop"}, "run-1", None) is None


def test_csv_row_to_record_invalid_or_zero_latency_is_none():
    base_row = {
        "round_id": "5",
        "expected_intent": "sit",
        "intent": "sit",
        "match": "match",
        "status": "complete",
    }
    zero_latency = {**base_row, "e2e_latency_ms": "0"}
    invalid_latency = {**base_row, "e2e_latency_ms": "not-a-number"}

    assert (
        voice_csv_to_jsonl.csv_row_to_record(zero_latency, {"stop"}, "run-1", None)[
            "latency_ms"
        ]
        is None
    )
    assert (
        voice_csv_to_jsonl.csv_row_to_record(invalid_latency, {"stop"}, "run-1", None)[
            "latency_ms"
        ]
        is None
    )
