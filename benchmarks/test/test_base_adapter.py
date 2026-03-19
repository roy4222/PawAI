"""BenchAdapter ABC contract tests."""
import pytest
from benchmarks.adapters.base import BenchAdapter


class DummyAdapter(BenchAdapter):
    """Minimal concrete adapter for testing the ABC contract."""

    def __init__(self):
        self.loaded = False
        self.cleaned = False

    def load(self, config: dict) -> None:
        self.loaded = True
        self.model_name = config.get("name", "dummy")

    def prepare_input(self, input_ref: str):
        return f"prepared:{input_ref}"

    def infer(self, input_data) -> dict:
        return {"result": "ok", "input": input_data}

    def cleanup(self) -> None:
        self.cleaned = True


def test_adapter_lifecycle():
    adapter = DummyAdapter()
    adapter.load({"name": "test_model"})
    assert adapter.loaded
    inp = adapter.prepare_input("test.jpg")
    assert inp == "prepared:test.jpg"
    result = adapter.infer(inp)
    assert result["result"] == "ok"
    adapter.cleanup()
    assert adapter.cleaned


def test_evaluate_default_returns_empty_dict():
    adapter = DummyAdapter()
    adapter.load({})
    result = adapter.evaluate([], None)
    assert result == {}


def test_publish_debug_default_is_noop():
    adapter = DummyAdapter()
    adapter.load({})
    # Should not raise
    adapter.publish_debug("input", {"pred": 1}, {})


def test_cannot_instantiate_abc_directly():
    with pytest.raises(TypeError):
        BenchAdapter()


def test_missing_method_raises():
    class IncompleteAdapter(BenchAdapter):
        def load(self, config): ...
        def prepare_input(self, input_ref): ...
        # missing infer and cleanup

    with pytest.raises(TypeError):
        IncompleteAdapter()
