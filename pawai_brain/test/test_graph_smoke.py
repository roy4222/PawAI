"""End-to-end smoke test for the LangGraph 11-node primary graph.

We exercise three paths:
  1. safety hit → bypass LLM, output stop_move
  2. happy path with mocked OpenRouter → reply + proposed_skill
  3. LLM chain exhausted → RuleBrain fallback
"""
from __future__ import annotations
from unittest.mock import patch

from pawai_brain.graph import build_graph
from pawai_brain.llm_client import OpenRouterClient, OpenRouterConfig
from pawai_brain.memory import ConversationMemory
from pawai_brain.nodes import llm_decision as llm_node
from pawai_brain.nodes import memory_builder as memory_node


def _wire_for_test(persona_response: dict | None):
    """Configure the module-level hooks the wrapper would set in production."""
    client = OpenRouterClient(
        config=OpenRouterConfig(),
        api_key="test-key",
        logger=lambda _: None,
    )

    if persona_response is None:
        # Force chain exhaustion: every call is a connection error.
        import requests as real_requests

        def post_side_effect(*_args, **_kwargs):
            raise real_requests.exceptions.ConnectionError()

        patcher = patch("pawai_brain.llm_client.requests.post", side_effect=post_side_effect)
    else:
        import json as _json

        def good_resp(*_args, **_kwargs):
            from unittest.mock import MagicMock

            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "choices": [{"message": {"content": _json.dumps(persona_response)}}]
            }
            resp.text = "ok"
            return resp

        patcher = patch("pawai_brain.llm_client.requests.post", side_effect=good_resp)

    llm_node.configure(
        client=client,
        system_prompt="(test persona)",
        user_message_builder=lambda s: s.get("user_text", ""),
    )
    mem = ConversationMemory()
    memory_node.set_history_provider(mem.recent)
    return patcher, mem


def test_safety_hit_short_circuits():
    patcher, _ = _wire_for_test(persona_response={"reply": "should not appear", "skill": None})
    with patcher:
        graph = build_graph()
        result = graph.invoke(
            {"session_id": "s-safety", "user_text": "停！", "source": "speech"}
        )

    assert result["selected_skill"] == "stop_move"
    assert result["intent"] == "stop"
    stages = [t["stage"] for t in result["trace"]]
    # Must NOT touch llm-related stages
    assert "llm_decision" not in stages
    assert "json_validate" not in stages
    # Must include safety_gate hit + output
    assert any(t["stage"] == "safety_gate" and t["status"] == "hit" for t in result["trace"])
    assert any(t["stage"] == "output" and t["detail"] == "safety_path" for t in result["trace"])


def test_happy_path_with_proposed_skill():
    patcher, mem = _wire_for_test(
        persona_response={
            "reply": "我是 PawAI，一隻機器狗。",
            "skill": "self_introduce",
            "args": {},
        }
    )
    with patcher:
        graph = build_graph()
        result = graph.invoke(
            {"session_id": "s-happy", "user_text": "你是誰", "source": "speech"}
        )

    assert "PawAI" in result["reply_text"]
    assert result["proposed_skill"] == "self_introduce"
    assert result["proposed_args"] == {}
    stages = [t["stage"] for t in result["trace"]]
    for required in ("input", "safety_gate", "context", "env", "memory",
                     "llm_decision", "json_validate", "repair", "skill_gate",
                     "output"):
        assert required in stages, f"missing stage {required}"
    # skill_gate should be 'proposed' for an allowlisted skill
    skill_gate_entries = [t for t in result["trace"] if t["stage"] == "skill_gate"]
    assert skill_gate_entries[-1]["status"] == "proposed"


def test_llm_failure_falls_back_to_rulebrain():
    patcher, _ = _wire_for_test(persona_response=None)  # all chain calls fail
    with patcher:
        graph = build_graph()
        result = graph.invoke(
            {"session_id": "s-fallback", "user_text": "你好啊", "source": "speech"}
        )

    # RuleBrain canned reply for greet keyword
    assert result["reply_text"]
    assert result["intent"] in ("greet", "unknown", "chat")
    assert result["reasoning"] == "rule_fallback"
    # repair stage should have flagged fallback
    repair_entries = [t for t in result["trace"] if t["stage"] == "repair"]
    assert repair_entries and repair_entries[-1]["status"] == "fallback"


def test_truncated_reply_routes_to_rulebrain_fallback():
    """Bug repro: validator's truncation guard MUST flip validation_error so
    response_repair flags repair_failed and output_builder falls back to
    RuleBrain. Otherwise truncated replies are silently shipped.
    """
    truncated = "今天天氣真的很好我們可以一起去散步，"  # ends with mid-clause '，'
    patcher, _ = _wire_for_test(
        persona_response={"reply": truncated, "skill": None, "args": {}}
    )
    with patcher:
        graph = build_graph()
        result = graph.invoke(
            {"session_id": "s-trunc", "user_text": "你好啊", "source": "speech"}
        )

    # output_builder must have taken the fallback path
    assert result["reasoning"] == "rule_fallback"
    # The truncated reply must NOT leak through
    assert result["reply_text"] != truncated
    # Trace evidence
    validate_entries = [t for t in result["trace"] if t["stage"] == "json_validate"]
    assert validate_entries and validate_entries[-1]["status"] == "retry"
    repair_entries = [t for t in result["trace"] if t["stage"] == "repair"]
    assert repair_entries and repair_entries[-1]["status"] == "fallback"
    output_entries = [t for t in result["trace"] if t["stage"] == "output"]
    assert output_entries and output_entries[-1]["status"] == "fallback"


def test_disallowed_skill_kept_with_rejected_trace():
    patcher, _ = _wire_for_test(
        persona_response={
            "reply": "好啊",
            "skill": "dance_wildly",
            "args": {},
        }
    )
    with patcher:
        graph = build_graph()
        result = graph.invoke(
            {"session_id": "s-reject", "user_text": "亂跳一下", "source": "speech"}
        )

    # Per Plan §3 contract: keep the offending skill so brain_node sees & rejects.
    assert result["proposed_skill"] == "dance_wildly"
    skill_gate_entries = [t for t in result["trace"] if t["stage"] == "skill_gate"]
    assert skill_gate_entries[-1]["status"] == "rejected_not_allowed"
