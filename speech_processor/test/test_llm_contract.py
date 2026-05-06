#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""LLM response contract validation tests.

Validates that SKILL_TO_CMD, BANNED_API_IDS, P0_SKILLS, and
the response-parsing logic in llm_bridge_node stay correct as
the codebase evolves.
"""

import json
import unittest

from speech_processor.llm_contract import (
    BANNED_API_IDS,
    LLM_REQUIRED_FIELDS,
    P0_SKILLS,
    SKILL_TO_CMD,
    adapt_eval_schema,
    extract_proposal,
    parse_llm_response,
    strip_markdown_fences,
)


# ---------------------------------------------------------------------------
# 1. SKILL_TO_CMD mapping completeness
# ---------------------------------------------------------------------------

class TestSkillToCmdMapping(unittest.TestCase):
    """Ensure SKILL_TO_CMD contains required skills with correct schema."""

    def test_hello_exists(self):
        self.assertIn("hello", SKILL_TO_CMD)

    def test_stop_move_exists(self):
        self.assertIn("stop_move", SKILL_TO_CMD)

    def test_each_skill_has_api_id_int(self):
        for skill, cmd in SKILL_TO_CMD.items():
            with self.subTest(skill=skill):
                self.assertIn("api_id", cmd, f"{skill} missing 'api_id'")
                self.assertIsInstance(
                    cmd["api_id"], int, f"{skill} api_id must be int")

    def test_each_skill_has_parameter_str(self):
        for skill, cmd in SKILL_TO_CMD.items():
            with self.subTest(skill=skill):
                self.assertIn("parameter", cmd, f"{skill} missing 'parameter'")
                self.assertIsInstance(
                    cmd["parameter"], str, f"{skill} parameter must be str")


# ---------------------------------------------------------------------------
# 2. BANNED_API_IDS safety
# ---------------------------------------------------------------------------

class TestBannedApiIds(unittest.TestCase):
    """Dangerous motions must stay banned; P0 skills must stay allowed."""

    def test_front_flip_banned(self):
        self.assertIn(1030, BANNED_API_IDS, "FrontFlip (1030) must be banned")

    def test_front_jump_banned(self):
        self.assertIn(1031, BANNED_API_IDS, "FrontJump (1031) must be banned")

    def test_handstand_banned(self):
        self.assertIn(1301, BANNED_API_IDS, "Handstand (1301) must be banned")

    def test_p0_skills_not_banned(self):
        for skill in P0_SKILLS:
            api_id = SKILL_TO_CMD[skill]["api_id"]
            with self.subTest(skill=skill, api_id=api_id):
                self.assertNotIn(api_id, BANNED_API_IDS,
                                 f"P0 skill '{skill}' (api_id={api_id}) must NOT be banned")


# ---------------------------------------------------------------------------
# 3. P0_SKILLS gate
# ---------------------------------------------------------------------------

class TestP0SkillsGate(unittest.TestCase):
    """P0_SKILLS must be a valid subset of SKILL_TO_CMD keys."""

    def test_hello_in_p0(self):
        self.assertIn("hello", P0_SKILLS)

    def test_stop_move_in_p0(self):
        self.assertIn("stop_move", P0_SKILLS)

    def test_p0_subset_of_skill_to_cmd(self):
        self.assertTrue(
            P0_SKILLS.issubset(SKILL_TO_CMD.keys()),
            f"P0_SKILLS has unknown skills: {P0_SKILLS - SKILL_TO_CMD.keys()}")


# ---------------------------------------------------------------------------
# 4. Markdown code fence stripping
# ---------------------------------------------------------------------------

class TestMarkdownFenceStripping(unittest.TestCase):
    """Validate the fence-stripping logic that mirrors lines 362-368."""

    VALID_JSON = '{"intent": "greet", "reply_text": "hi", ' \
                 '"selected_skill": "hello", "reasoning": "test", "confidence": 0.9}'

    def test_json_with_fences_stripped(self):
        raw = f"```json\n{self.VALID_JSON}\n```"
        self.assertEqual(strip_markdown_fences(raw), self.VALID_JSON)

    def test_plain_json_unchanged(self):
        self.assertEqual(strip_markdown_fences(self.VALID_JSON), self.VALID_JSON)

    def test_fences_only_at_start_and_end(self):
        raw = f"```\n{self.VALID_JSON}\n```"
        self.assertEqual(strip_markdown_fences(raw), self.VALID_JSON)

    def test_leading_trailing_whitespace(self):
        raw = f"  \n```json\n{self.VALID_JSON}\n```\n  "
        self.assertEqual(strip_markdown_fences(raw), self.VALID_JSON)


# ---------------------------------------------------------------------------
# 5. Required fields validation
# ---------------------------------------------------------------------------

class TestRequiredFieldsValidation(unittest.TestCase):
    """Validate that all five required fields must be present."""

    REQUIRED_FIELDS = LLM_REQUIRED_FIELDS

    VALID_RESPONSE = json.dumps({
        "intent": "greet",
        "reply_text": "Hello there!",
        "selected_skill": "hello",
        "reasoning": "User greeted the robot.",
        "confidence": 0.95,
    })

    def test_valid_response_passes(self):
        result = parse_llm_response(self.VALID_RESPONSE)
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "greet")

    def test_missing_each_required_field(self):
        base = json.loads(self.VALID_RESPONSE)
        for field in self.REQUIRED_FIELDS:
            with self.subTest(missing=field):
                incomplete = {k: v for k, v in base.items() if k != field}
                self.assertIsNone(parse_llm_response(json.dumps(incomplete)),
                                  f"Should reject response missing '{field}'")

    def test_extra_fields_still_pass(self):
        base = json.loads(self.VALID_RESPONSE)
        base["extra_field"] = "bonus"
        result = parse_llm_response(json.dumps(base))
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# 6. JSON parsing edge cases
# ---------------------------------------------------------------------------

class TestJsonParsingEdgeCases(unittest.TestCase):
    """Edge cases for the combined fence-strip + JSON-parse pipeline."""

    VALID_PAYLOAD = json.dumps({
        "intent": "idle",
        "reply_text": "OK",
        "selected_skill": "none",
        "reasoning": "nothing to do",
        "confidence": 0.5,
    })

    def test_valid_json_passes(self):
        result = parse_llm_response(self.VALID_PAYLOAD)
        self.assertIsNotNone(result)
        self.assertEqual(result["confidence"], 0.5)

    def test_invalid_json_returns_none(self):
        result = parse_llm_response("{not valid json at all")
        self.assertIsNone(result)

    def test_nested_markdown_fences(self):
        # Model wraps JSON in ```json ... ``` AND the content itself contains
        # a backtick sequence — stripping should still yield valid JSON.
        raw = f"```json\n{self.VALID_PAYLOAD}\n```"
        result = parse_llm_response(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result["intent"], "idle")

    def test_empty_string_returns_none(self):
        self.assertIsNone(parse_llm_response(""))

    def test_non_object_json_returns_none(self):
        # A valid JSON array is not a valid LLM response object.
        self.assertIsNone(parse_llm_response('[1, 2, 3]'))


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------------------
# 7. extract_proposal helpers (Phase 0.5, 2026-05-06)
# ---------------------------------------------------------------------------


def test_extract_proposal_returns_skill_and_args_when_present():
    eval_obj = {
        "reply": "汪，我是 PawAI",
        "skill": "self_introduce",
        "args": {},
    }
    proposal = extract_proposal(eval_obj)
    assert proposal == {
        "proposed_skill": "self_introduce",
        "proposed_args": {},
        "proposal_reason": "openrouter:eval_schema",
    }


def test_extract_proposal_returns_none_skill_when_missing():
    proposal = extract_proposal({"reply": "你好"})
    assert proposal["proposed_skill"] is None
    assert proposal["proposed_args"] == {}


def test_extract_proposal_handles_non_dict_args():
    proposal = extract_proposal({"reply": "...", "skill": "show_status", "args": "ignore"})
    assert proposal["proposed_skill"] == "show_status"
    assert proposal["proposed_args"] == {}


def test_extract_proposal_preserves_skill_outside_legacy_p0():
    """The whole point: persona skill that adapt_eval_schema would drop must survive here."""
    proposal = extract_proposal({"reply": "...", "skill": "show_status", "args": {}})
    assert proposal["proposed_skill"] == "show_status"


def test_adapt_eval_schema_unchanged_for_legacy_skill():
    """Regression guard: adapt_eval_schema behavior must not change."""
    bridge = adapt_eval_schema({"reply": "stop", "skill": "stop_move", "args": {}})
    assert bridge["selected_skill"] == "stop_move"
    assert bridge["reply_text"] == "stop"


def test_extract_proposal_treats_chat_reply_as_no_side_effect():
    """Persona returning skill='chat_reply' is redundant with reply_text — surface as None."""
    proposal = extract_proposal({"reply": "你好", "skill": "chat_reply", "args": {}})
    assert proposal["proposed_skill"] is None


def test_extract_proposal_treats_say_canned_as_no_side_effect():
    proposal = extract_proposal({"reply": "好的", "skill": "say_canned", "args": {}})
    assert proposal["proposed_skill"] is None


def test_extract_proposal_still_passes_through_real_side_effects():
    """show_status, self_introduce, dance, wiggle — all should pass through (brain gates them)."""
    for s in ("show_status", "self_introduce", "dance", "wiggle"):
        proposal = extract_proposal({"reply": "...", "skill": s, "args": {}})
        assert proposal["proposed_skill"] == s
