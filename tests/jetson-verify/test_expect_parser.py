"""Expect parser unit tests — all 5 operators + edge cases."""
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.claude/skills/jetson-verify/scripts"))
from verify import evaluate_expect


class TestGreaterEqual:
    def test_pass(self):
        assert evaluate_expect("2400", ">= 800") is True

    def test_fail(self):
        assert evaluate_expect("500", ">= 800") is False

    def test_boundary(self):
        assert evaluate_expect("800", ">= 800") is True

    def test_float(self):
        assert evaluate_expect("800.5", ">= 800") is True

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError):
            evaluate_expect("abc", ">= 800")


class TestLessEqual:
    def test_pass(self):
        assert evaluate_expect("60", "<= 75") is True

    def test_fail(self):
        assert evaluate_expect("80", "<= 75") is False

    def test_boundary(self):
        assert evaluate_expect("75", "<= 75") is True


class TestEqual:
    def test_pass(self):
        assert evaluate_expect("1", "== 1") is True

    def test_fail(self):
        assert evaluate_expect("0", "== 1") is False

    def test_float_equal(self):
        assert evaluate_expect("1.0", "== 1") is True


class TestContains:
    def test_pass(self):
        assert evaluate_expect("daemon is running", "contains running") is True

    def test_fail(self):
        assert evaluate_expect("daemon stopped", "contains running") is False

    def test_multiline(self):
        assert evaluate_expect("line1\nrunning\nline3", "contains running") is True


class TestNonempty:
    def test_pass(self):
        assert evaluate_expect("some output", "nonempty") is True

    def test_fail_empty(self):
        assert evaluate_expect("", "nonempty") is False

    def test_fail_whitespace(self):
        assert evaluate_expect("   \n  ", "nonempty") is False


class TestInvalidOperator:
    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown expect"):
            evaluate_expect("42", "!= 42")
