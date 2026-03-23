#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""Intent classification logic — pure Python, no ROS2 dependency.

Extracted from stt_intent_node.py to allow standalone testing in CI.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


SUPPORTED_INTENTS = (
    "greet",
    "come_here",
    "stop",
    "sit",
    "stand",
    "take_photo",
    "status",
)


@dataclass
class IntentMatch:
    intent: str
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)


class IntentClassifier:
    def __init__(self) -> None:
        self.intent_rules: Dict[str, List[Tuple[str, float]]] = {
            "greet": [
                ("你好", 1.0),
                ("哈囉", 1.0),
                ("嗨", 0.8),
                ("早安", 0.9),
                ("午安", 0.9),
                ("晚安", 0.9),
                ("hello", 0.8),
                ("hi", 0.6),
                ("打招呼", 1.0),
                # 簡體 / Whisper 誤辨
                ("妳好", 1.0),
                ("您好", 1.0),
                ("哈嘍", 0.9),
                ("哈摟", 0.9),
                ("哈啰", 0.9),
                ("哈喽", 0.9),
                ("嗨嗨", 0.8),
                ("打擾", 0.7),
            ],
            "come_here": [
                ("過來", 1.0),
                ("來這裡", 1.0),
                ("來我這", 1.0),
                ("靠近", 0.8),
                ("跟我來", 0.8),
                ("come here", 1.0),
                ("come", 0.6),
                ("這邊", 0.7),
                ("你來一下", 1.0),
                # 簡體 / Whisper 誤辨
                ("过来", 1.0),
                ("来这里", 1.0),
                ("来我这", 1.0),
                ("跟我来", 0.8),
                ("这边", 0.7),
                ("靠近我", 0.8),
                ("國來", 0.7),
                ("郭來", 0.7),
                ("你来一下", 1.0),
                ("来一下", 0.9),
                ("來一下", 0.9),
                ("來", 0.9),
                ("来", 0.9),
            ],
            "stop": [
                ("停止", 1.0),
                ("停下", 1.0),
                ("不要動", 0.9),
                ("停住", 0.9),
                ("stop", 1.0),
                ("freeze", 0.8),
                ("中止", 0.8),
                # 簡體 / Whisper 誤辨
                ("不要动", 0.9),
                ("停視", 0.8),
                ("聽下", 0.8),
                ("請停", 0.9),
                ("请停", 0.9),
                ("別動", 0.9),
                ("别动", 0.9),
                ("停", 0.5),
                # Whisper 短音誤辨為英文
                ("king", 0.9),
            ],
            "sit": [
                ("坐下", 1.0),
                ("坐", 0.8),
                ("坐好", 0.9),
                ("sit", 0.8),
                ("sit down", 1.0),
            ],
            "stand": [
                ("站起來", 1.0),
                ("起來", 0.9),
                ("站好", 0.9),
                ("站起", 0.9),
                ("stand", 0.8),
                ("stand up", 1.0),
                # 簡體 / Whisper 誤辨
                ("站起来", 1.0),
            ],
            "take_photo": [
                ("拍照", 1.0),
                ("拍張照", 1.0),
                ("照相", 1.0),
                ("拍一張", 0.9),
                ("take photo", 1.0),
                ("take a photo", 1.0),
                ("photo", 0.7),
                ("camera", 0.6),
                # 簡體 / Whisper 誤辨
                ("拍张照", 1.0),
                ("拍一张", 0.9),
                ("拍個照", 0.9),
                ("拍个照", 0.9),
                ("拍攝", 0.9),
                ("拍摄", 0.9),
                ("照片", 0.7),
                ("拍上", 0.7),
                ("派上", 0.6),
                ("拍找", 0.8),
                ("拍招", 0.8),
            ],
            "status": [
                ("狀態", 1.0),
                ("你還好嗎", 0.8),
                ("現在怎麼樣", 0.8),
                ("目前情況", 0.8),
                ("電量", 0.8),
                ("status", 1.0),
                ("how are you", 0.7),
                ("battery", 0.6),
                # 簡體 / Whisper 誤辨
                ("状态", 1.0),
                ("你还好吗", 0.8),
                ("现在怎么样", 0.8),
                ("目前情况", 0.8),
                ("电量", 0.8),
                ("回覆", 0.7),
                ("回復", 0.7),
                ("回复", 0.7),
                ("撞態", 0.7),
            ],
        }

    @staticmethod
    def _normalize(text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"\s+", "", text)
        return text

    def classify(self, text: str) -> IntentMatch:
        normalized = self._normalize(text)
        if not normalized:
            return IntentMatch(intent="unknown", confidence=0.0, matched_keywords=[])

        best_intent = "unknown"
        best_score = 0.0
        best_keywords: List[str] = []

        for intent, rules in self.intent_rules.items():
            score = 0.0
            matched: List[str] = []
            for keyword, weight in rules:
                if keyword in normalized:
                    score += weight
                    matched.append(keyword)

            if matched:
                normalized_score = min(1.0, score / max(1.0, len(matched)))
                if normalized_score > best_score:
                    best_intent = intent
                    best_score = normalized_score
                    best_keywords = matched

        return IntentMatch(
            intent=best_intent, confidence=best_score, matched_keywords=best_keywords
        )
