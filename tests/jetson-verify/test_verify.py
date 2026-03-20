"""verify.py integration tests — mock transport, test full pipeline."""
import pytest
from unittest.mock import patch

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.claude/skills/jetson-verify/scripts"))
from verify import run_single_check, STATUS_PASS, STATUS_WARN, STATUS_FAIL, STATUS_SKIP, STATUS_ERROR


def make_check(id="test.check", command="echo 42", expect=">= 1",
               blocking=True, timeout_sec=5, message_template="{value}",
               precondition=None):
    c = {"id": id, "command": command, "expect": expect,
         "blocking": blocking, "timeout_sec": timeout_sec,
         "message_template": message_template}
    if precondition:
        c["precondition"] = precondition
    return c


class TestRunSingleCheck:
    @patch("verify.exec_on_target", return_value=(0, "2400\n", ""))
    def test_pass(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800"), "local_jetson")
        assert result["status"] == STATUS_PASS
        assert result["value"] == "2400"

    @patch("verify.exec_on_target", return_value=(0, "500\n", ""))
    def test_fail_blocking(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800", blocking=True), "local_jetson")
        assert result["status"] == STATUS_FAIL

    @patch("verify.exec_on_target", return_value=(0, "500\n", ""))
    def test_warn_non_blocking(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800", blocking=False), "local_jetson")
        assert result["status"] == STATUS_WARN

    @patch("verify.exec_on_target", return_value=(-2, "", "timeout after 5s"))
    def test_timeout_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert result["value"] is None

    @patch("verify.exec_on_target", return_value=(-1, "", "SSH failed"))
    def test_transport_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR

    @patch("verify.exec_on_target", return_value=(127, "", "not found"))
    def test_nonzero_rc_error(self, mock_exec):
        result = run_single_check(make_check(), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert "rc=127" in result["message"]

    @patch("verify.exec_on_target", return_value=(0, "abc\n", ""))
    def test_parse_error_is_error(self, mock_exec):
        result = run_single_check(make_check(expect=">= 800"), "local_jetson")
        assert result["status"] == STATUS_ERROR
        assert "parse error" in result["message"]


class TestPrecondition:
    @patch("verify.exec_on_target")
    def test_precondition_pass_runs_check(self, mock_exec):
        mock_exec.side_effect = [(0, "", ""), (0, "42\n", "")]
        result = run_single_check(
            make_check(precondition="grep -q node", expect=">= 1"), "local_jetson"
        )
        assert result["status"] == STATUS_PASS
        assert mock_exec.call_count == 2

    @patch("verify.exec_on_target", return_value=(1, "", ""))
    def test_precondition_rc1_skip(self, mock_exec):
        result = run_single_check(
            make_check(precondition="grep -q missing"), "local_jetson"
        )
        assert result["status"] == STATUS_SKIP
        assert result["value"] is None

    @patch("verify.exec_on_target", return_value=(127, "", "command not found"))
    def test_precondition_rc_gt1_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="badcmd"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR
        assert "rc=127" in result["message"]

    @patch("verify.exec_on_target", return_value=(-1, "", "SSH down"))
    def test_precondition_transport_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="echo test"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR

    @patch("verify.exec_on_target", return_value=(-2, "", "timeout"))
    def test_precondition_timeout_error(self, mock_exec):
        result = run_single_check(
            make_check(precondition="slow_cmd"), "local_jetson"
        )
        assert result["status"] == STATUS_ERROR
        assert result["value"] is None


class TestOverallComputation:
    """Test overall priority: ERROR > blocking FAIL > PASS."""

    def _compute(self, statuses_and_blocking):
        results = [{"status": s, "blocking": b} for s, b in statuses_and_blocking]
        has_error = any(r["status"] == STATUS_ERROR for r in results)
        has_blocking_fail = any(r["status"] == STATUS_FAIL and r["blocking"] for r in results)
        if has_error:
            return "ERROR"
        if has_blocking_fail:
            return "FAIL"
        return "PASS"

    def test_all_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_PASS, False)]) == "PASS"

    def test_warn_still_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_WARN, False)]) == "PASS"

    def test_skip_still_pass(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_SKIP, False)]) == "PASS"

    def test_blocking_fail_is_fail(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_FAIL, True)]) == "FAIL"

    def test_error_beats_fail(self):
        assert self._compute([(STATUS_FAIL, True), (STATUS_ERROR, False)]) == "ERROR"

    def test_error_alone(self):
        assert self._compute([(STATUS_PASS, True), (STATUS_ERROR, True)]) == "ERROR"
