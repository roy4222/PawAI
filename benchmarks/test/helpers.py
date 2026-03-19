"""Shared test helpers (not conftest — direct import is cleaner)."""
import time
from benchmarks.adapters.base import BenchAdapter


class FakeAdapter(BenchAdapter):
    """Adapter that simulates inference with configurable delay."""

    def __init__(self):
        self.load_count = 0
        self.infer_count = 0
        self.cleanup_count = 0
        self.fail_on_load = False
        self.fail_on_infer_at = -1
        self.delay = 0.001

    def load(self, config: dict) -> None:
        if self.fail_on_load:
            raise RuntimeError("simulated load failure")
        self.load_count += 1
        self.delay = config.get("delay_ms", 1) / 1000.0

    def prepare_input(self, input_ref: str):
        return f"fake:{input_ref}"

    def infer(self, input_data) -> dict:
        self.infer_count += 1
        if self.infer_count == self.fail_on_infer_at:
            raise RuntimeError("simulated CUDA OOM")
        time.sleep(self.delay)
        return {"boxes": [[10, 20, 50, 60]], "scores": [0.95]}

    def cleanup(self) -> None:
        self.cleanup_count += 1
