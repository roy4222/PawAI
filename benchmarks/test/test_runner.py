"""BenchmarkRunner tests."""
import glob
import pytest
from benchmarks.core.runner import BenchmarkRunner
from benchmarks.test.helpers import FakeAdapter


def test_run_single_model(tmp_path):
    adapter = FakeAdapter()
    config = {
        "name": "test_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 2, "n_measure": 5, "input_source": "."},
        "feasibility_gate": {"min_fps": 0.1, "must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(
        adapter=adapter,
        config=config,
        task="test",
        level=1,
        mode="headless",
    )
    assert result["task"] == "test"
    assert result["model"] == "test_model"
    assert result["feasibility"]["n_completed"] == 5
    assert result["feasibility"]["crashed"] is False
    assert result["feasibility"]["fps_mean"] > 0
    assert adapter.cleanup_count == 1


def test_run_load_failure(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_on_load = True
    config = {
        "name": "bad_model",
        "params": {},
        "benchmark": {"n_warmup": 1, "n_measure": 3, "input_source": "."},
        "feasibility_gate": {"must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(adapter=adapter, config=config, task="test",
                        level=1, mode="headless")
    assert result["feasibility"]["crashed"] is True
    assert result["feasibility"]["n_completed"] == 0
    assert result["feasibility"]["gate_pass"] is False


def test_run_infer_crash(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_on_infer_at = 3  # crash on 3rd infer (during measure)
    config = {
        "name": "crash_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 1, "n_measure": 5, "input_source": "."},
        "feasibility_gate": {"must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(adapter=adapter, config=config, task="test",
                        level=1, mode="headless")
    assert result["feasibility"]["crashed"] is True
    # Warmup consumed 1 infer, then measure: 1st success, 2nd = infer_count 3 = crash
    assert result["feasibility"]["n_completed"] == 1
    assert adapter.cleanup_count == 1


def test_result_saved_to_jsonl(tmp_path):
    adapter = FakeAdapter()
    config = {
        "name": "test_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 1, "n_measure": 3, "input_source": "."},
        "feasibility_gate": {"min_fps": 0.1, "must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    runner.run(adapter=adapter, config=config, task="test",
               level=1, mode="headless")
    files = glob.glob(str(tmp_path / "test_*.jsonl"))
    assert len(files) == 1
