"""Unit tests for IntentClassifier and IntentMatch.

Covers canonical matches, whitespace tolerance (Whisper quirks),
empty input, simplified Chinese variants, Whisper misrecognition,
30-round YAML boundary vectors, confidence scoring, and matched_keywords.
"""

import pytest

from speech_processor.stt_intent_node import IntentClassifier, IntentMatch


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def classifier() -> IntentClassifier:
    return IntentClassifier()


# ---------------------------------------------------------------------------
# 1. Canonical matches -- primary keyword per intent
# ---------------------------------------------------------------------------

class TestCanonicalMatches:
    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("你好", "greet"),
            ("哈囉", "greet"),
            ("過來", "come_here"),
            ("來這裡", "come_here"),
            ("停止", "stop"),
            ("不要動", "stop"),
            ("拍照", "take_photo"),
            ("拍張照", "take_photo"),
            ("狀態", "status"),
            ("目前情況", "status"),
        ],
    )
    def test_primary_keywords(self, classifier: IntentClassifier, text: str, expected_intent: str):
        result = classifier.classify(text)
        assert result.intent == expected_intent
        assert result.confidence > 0.0


# ---------------------------------------------------------------------------
# 2. Whitespace tolerance -- Whisper inserts spaces between Chinese chars
# ---------------------------------------------------------------------------

class TestWhitespaceTolerance:
    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("你 好", "greet"),
            ("你  好", "greet"),
            (" 你好 ", "greet"),
            ("過 來", "come_here"),
            ("停 止", "stop"),
            ("拍 照", "take_photo"),
            ("狀 態", "status"),
            ("來 這 裡", "come_here"),
            ("不 要 動", "stop"),
        ],
    )
    def test_spaces_between_chars(self, classifier: IntentClassifier, text: str, expected_intent: str):
        result = classifier.classify(text)
        assert result.intent == expected_intent, (
            f"'{text}' should map to '{expected_intent}', got '{result.intent}'"
        )


# ---------------------------------------------------------------------------
# 3. Empty / blank strings
# ---------------------------------------------------------------------------

class TestEmptyInput:
    @pytest.mark.parametrize("text", ["", "   ", "\t", "\n", "  \n  "])
    def test_empty_or_blank(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert result.intent == "unknown"
        assert result.confidence == 0.0
        assert result.matched_keywords == []


# ---------------------------------------------------------------------------
# 4. Simplified Chinese variants
# ---------------------------------------------------------------------------

class TestSimplifiedChinese:
    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("过来", "come_here"),
            ("来这里", "come_here"),
            ("来我这", "come_here"),
            ("不要动", "stop"),
            ("别动", "stop"),
            ("请停", "stop"),
            ("拍张照", "take_photo"),
            ("拍个照", "take_photo"),
            ("拍摄", "take_photo"),
            ("状态", "status"),
            ("你还好吗", "status"),
            ("现在怎么样", "status"),
            ("目前情况", "status"),
            ("电量", "status"),
        ],
    )
    def test_simplified_keywords(self, classifier: IntentClassifier, text: str, expected_intent: str):
        result = classifier.classify(text)
        assert result.intent == expected_intent


# ---------------------------------------------------------------------------
# 5. Whisper misrecognition variants
# ---------------------------------------------------------------------------

class TestWhisperMisrecognition:
    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("哈嘍", "greet"),
            ("哈摟", "greet"),
            ("哈啰", "greet"),
            ("哈喽", "greet"),
            ("國來", "come_here"),
            ("郭來", "come_here"),
            ("停視", "stop"),
            ("聽下", "stop"),
            ("拍找", "take_photo"),
            ("拍招", "take_photo"),
            ("派上", "take_photo"),
            ("撞態", "status"),
            ("回覆", "status"),
            ("回復", "status"),
            ("回复", "status"),
        ],
    )
    def test_misrecognition_variants(self, classifier: IntentClassifier, text: str, expected_intent: str):
        result = classifier.classify(text)
        assert result.intent == expected_intent, (
            f"Whisper misrecognition '{text}' should map to '{expected_intent}', got '{result.intent}'"
        )


# ---------------------------------------------------------------------------
# 6. Boundary test vectors from 30-round YAML
# ---------------------------------------------------------------------------

class TestBoundaryVectors:
    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("嘿你好嗎", "greet"),
            ("你可以過來這邊嗎", "come_here"),
            ("別動別動別動", "stop"),
            ("拍個照片好不好", "take_photo"),
            ("報告一下你目前情況", "status"),
        ],
    )
    def test_30round_vectors(self, classifier: IntentClassifier, text: str, expected_intent: str):
        result = classifier.classify(text)
        assert result.intent == expected_intent, (
            f"30-round vector '{text}' should map to '{expected_intent}', got '{result.intent}'"
        )


# ---------------------------------------------------------------------------
# 7. Confidence scoring -- always in [0.0, 1.0]
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    @pytest.mark.parametrize(
        "text",
        [
            "你好",
            "哈嘍你好嗎",
            "過來這邊",
            "停止不要動",
            "幫我拍張照",
            "報告狀態",
            "隨便說一句不相關的話題",
            "",
        ],
    )
    def test_confidence_in_range(self, classifier: IntentClassifier, text: str):
        result = classifier.classify(text)
        assert 0.0 <= result.confidence <= 1.0, (
            f"Confidence {result.confidence} out of [0.0, 1.0] for '{text}'"
        )

    def test_higher_confidence_for_exact_keyword(self, classifier: IntentClassifier):
        """A single exact keyword should yield high confidence."""
        result = classifier.classify("你好")
        assert result.confidence >= 0.8

    def test_unknown_has_zero_confidence(self, classifier: IntentClassifier):
        result = classifier.classify("今天天氣真不錯呢")
        assert result.intent == "unknown"
        assert result.confidence == 0.0


# ---------------------------------------------------------------------------
# 8. matched_keywords is populated for matches
# ---------------------------------------------------------------------------

class TestMatchedKeywords:
    def test_matched_keywords_nonempty_on_match(self, classifier: IntentClassifier):
        result = classifier.classify("你好")
        assert result.intent == "greet"
        assert len(result.matched_keywords) > 0
        assert "你好" in result.matched_keywords

    def test_matched_keywords_empty_on_unknown(self, classifier: IntentClassifier):
        result = classifier.classify("完全無關的句子")
        assert result.intent == "unknown"
        assert result.matched_keywords == []

    def test_multiple_keywords_matched(self, classifier: IntentClassifier):
        """When input contains multiple keywords for the same intent,
        matched_keywords should list all of them."""
        result = classifier.classify("別動停止不要動")
        assert result.intent == "stop"
        assert len(result.matched_keywords) >= 2

    @pytest.mark.parametrize(
        "text, expected_intent",
        [
            ("過來", "come_here"),
            ("拍照", "take_photo"),
            ("狀態", "status"),
        ],
    )
    def test_matched_keywords_contains_trigger(
        self, classifier: IntentClassifier, text: str, expected_intent: str
    ):
        result = classifier.classify(text)
        assert result.intent == expected_intent
        assert len(result.matched_keywords) > 0


# ---------------------------------------------------------------------------
# IntentMatch dataclass sanity
# ---------------------------------------------------------------------------

class TestIntentMatchDataclass:
    def test_default_matched_keywords(self):
        m = IntentMatch(intent="test", confidence=0.5)
        assert m.matched_keywords == []

    def test_fields(self):
        m = IntentMatch(intent="greet", confidence=0.9, matched_keywords=["你好"])
        assert m.intent == "greet"
        assert m.confidence == 0.9
        assert m.matched_keywords == ["你好"]
