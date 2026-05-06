#!/usr/bin/env python3

# Copyright (c) 2026, PawAI contributors
# SPDX-License-Identifier: BSD-3-Clause

"""LLM Bridge Node — replaces intent_tts_bridge_node.

Subscribes to speech intent events and face identity events,
calls Cloud LLM (OpenAI-compatible API), and publishes TTS text
and Go2 action commands.

Spec: docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-03-16-llm-integration-mini-spec.md v2.0
"""

import json
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

try:
    import requests
except Exception:
    requests = None

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:
    WebRtcReq = None


from .llm_contract import (
    BANNED_API_IDS,
    LLM_REQUIRED_FIELDS,
    P0_SKILLS,
    SKILL_TO_CMD,
    adapt_eval_schema,
    extract_proposal,
    parse_llm_response,
    strip_markdown_fences,
)


# ── RuleBrain fallback templates (from intent_tts_bridge_node) ──────────

REPLY_TEMPLATES = {
    "greet": "[excited] 嗨！我在這裡，今天過得怎麼樣？",
    "come_here": "[playful] 收到，我馬上過去找你！",
    "stop": "好的，我停下來。",
    "sit": "[playful] 好喔，我坐下囉。",
    "stand": "[excited] 好，我站起來！",
    "take_photo": "[curious] 收到，我來拍張照。",
    "status": "我現在狀態還不錯，感官都正常喔。",
    "unknown": "[curious] 欸我沒聽清楚，可以再講一次嗎？",
}

RULE_SKILL_MAP = {
    "greet": "hello",
    "stop": "stop_move",
    "sit": "sit",
    "stand": "stand",
}

# ── System prompt (spec §1.5) ───────────────────────────────────────────

SYSTEM_PROMPT = """\
你是 PawAI，一隻友善的機器狗助手，搭載在 Unitree Go2 Pro 上。你能看見人（透過攝影機人臉辨識）、聽懂中文（透過語音辨識）、做出動作。

你可能被兩種事件觸發：
1. 語音事件：使用者對你說話
2. 人臉事件：攝影機辨識到認識的人（此時沒有語音輸入）

你只能輸出單一 JSON object，不要輸出任何其他文字。
JSON 必須包含以下五個欄位：

intent — 只能是以下之一：greet, stop, sit, stand, status, chat, ignored
reply_text — 你要說的中文回覆（一句話，不超過 12 字。人臉事件時要叫出對方名字）
selected_skill — 只能是以下之一："hello", "stop_move", "sit", "stand", null
reasoning — 一句話決策摘要，不超過 20 字
confidence — 0.0 到 1.0

規則：
- 看到認識的人（人臉事件）：intent=greet，reply_text 要包含對方名字，selected_skill 可以是 "hello" 或 null
- 聽到打招呼：intent=greet，reply_text 友善回應
- 聽到「停」或「stop」：intent=stop，selected_skill 必須是 "stop_move"，reply_text 可以是空字串
- 聽到「坐下」「坐」：intent=sit，selected_skill 必須是 "sit"，reply_text 簡短確認
- 聽到「站起來」「起來」「站好」：intent=stand，selected_skill 必須是 "stand"，reply_text 簡短確認
- 聽到問狀態（「怎麼樣」「在做什麼」「狀態」等）：intent=status，reply_text 必須說明目前狀況
- 不確定時：intent=chat，reply_text 必須是友善的回應
- greet/chat/status 的 reply_text 必須非空（只有 stop 和 ignored 允許空）
- reply_text 不超過 12 字
- 除了 JSON 不要輸出任何文字"""


class LlmBridgeNode(Node):
    def __init__(self) -> None:
        super().__init__("llm_bridge_node")

        self._declare_parameters()
        self._read_parameters()

        # Publishers
        self.tts_pub = self.create_publisher(String, self.tts_topic, 10)
        self.state_pub = self.create_publisher(String, self.state_topic, 10)
        if WebRtcReq is not None and self.enable_actions and self.output_mode == "legacy":
            self.action_pub = self.create_publisher(
                WebRtcReq, "/webrtc_req", 10
            )
        else:
            self.action_pub = None

        # /brain/chat_candidate publisher (always created; only used when output_mode=="brain")
        self.chat_candidate_pub = self.create_publisher(
            String, self.chat_candidate_topic, 10
        )

        # Subscribers
        self.create_subscription(
            String, self.intent_event_topic, self._on_speech_event, 10
        )
        if self.subscribe_face:
            self.create_subscription(
                String, self.face_event_topic, self._on_face_event, 10
            )
        else:
            self.get_logger().info(
                "Face subscription disabled (subscribe_face=false)"
            )
        self.create_subscription(
            String, self.face_state_topic, self._on_face_state, 10
        )

        # State
        self._seen_sessions: set = set()
        self._seen_sessions_lock = threading.Lock()
        self._face_greet_history: dict = {}  # (track_id, name) -> timestamp
        self._latest_face_state: dict | None = None
        self._llm_lock = threading.Lock()
        self._greet_cooldown_s = 5.0
        self._last_greet_ts = 0.0

        # Conversation memory: last 5 turns (user, assistant) = 10 messages.
        # Cleared on RuleBrain fallback intents that aren't real chat (stop/sit/stand).
        self._convo_history: deque = deque(maxlen=10)
        self._convo_lock = threading.Lock()
        # Stash the raw ASR text per call (LLM lock serializes, so a single
        # slot is fine). Read back in _dispatch / _rule_fallback to remember.
        self._pending_user_text = ""

        self.last_trigger = ""
        self.last_intent = ""
        self.last_reply = ""
        self.last_skill = ""
        self.last_error = ""
        self.last_source = ""

        # Weather cache for Taipei (refresh every 10 min via wttr.in, no key).
        self._weather_cache_text = ""
        self._weather_cache_ts = 0.0
        self._weather_ttl_s = 600.0
        self._weather_lock = threading.Lock()

        # OpenRouter setup (Phase B B1).
        self._openrouter_key = (
            os.environ.get("OPENROUTER_KEY")
            or os.environ.get("OPENROUTER_API_KEY")
            or ""
        ).strip()
        self._openrouter_active = bool(self.enable_openrouter and self._openrouter_key)
        if self.enable_openrouter and not self._openrouter_key:
            self.get_logger().warn(
                "OPENROUTER_KEY not set — Gemini/DeepSeek disabled, "
                "falling through to existing vLLM chain"
            )
        self._system_prompt = self._load_system_prompt()

        # Bounded thread pool to prevent per-event thread explosion
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="llm")

        # State publish timer
        self.state_timer = self.create_timer(
            1.0 / self.state_publish_hz, self._publish_state
        )

        self.get_logger().info(
            f"llm_bridge_node ready "
            f"(llm={self.llm_endpoint}, model={self.llm_model}, "
            f"actions={'ON' if self.action_pub else 'OFF'})"
        )

    def _declare_parameters(self) -> None:
        self.declare_parameter("llm_endpoint", "http://140.136.155.5:8000/v1/chat/completions")
        self.declare_parameter("llm_model", "Qwen/Qwen2.5-7B-Instruct")
        self.declare_parameter("llm_timeout", 15.0)
        self.declare_parameter("llm_temperature", 0.2)
        self.declare_parameter("llm_max_tokens", 80)
        self.declare_parameter("intent_event_topic", "/event/speech_intent_recognized")
        self.declare_parameter("face_event_topic", "/event/face_identity")
        self.declare_parameter("face_state_topic", "/state/perception/face")
        self.declare_parameter("tts_topic", "/tts")
        self.declare_parameter("state_topic", "/state/interaction/llm_bridge")
        self.declare_parameter("enable_actions", True)
        self.declare_parameter("enable_fallback", True)
        self.declare_parameter("face_greet_cooldown_s", 60.0)
        self.declare_parameter("action_delay_s", 0.5)
        self.declare_parameter("state_publish_hz", 2.0)
        self.declare_parameter("force_fallback", False)
        self.declare_parameter("enable_local_llm", True)
        self.declare_parameter(
            "local_llm_endpoint",
            "http://localhost:11434/v1/chat/completions",
        )
        self.declare_parameter("local_llm_model", "qwen2.5:1.5b")
        self.declare_parameter("subscribe_face", True)
        self.declare_parameter("output_mode", "legacy")  # "legacy" | "brain"
        self.declare_parameter("chat_candidate_topic", "/brain/chat_candidate")
        # ── OpenRouter (Phase B B1, 2026-05-04) ────────────────────────
        # Primary: Gemini 3 Flash; conditional fallback: DeepSeek V4 Flash.
        # Key from env (OPENROUTER_KEY or OPENROUTER_API_KEY); never a ROS param.
        self.declare_parameter("enable_openrouter", True)
        self.declare_parameter(
            "openrouter_base_url",
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.declare_parameter(
            "openrouter_gemini_model", "google/gemini-2.5-flash"
        )
        self.declare_parameter(
            "openrouter_deepseek_model", "deepseek/deepseek-v4-flash"
        )
        # Defaults bumped 2.0/2.2 → 4.0/5.0 after 5/4 Jetson smoke: eval ran on
        # RTX 8000 (1.61s avg / 1.87s p90); Jetson curl alone is 1.5s but
        # Python urllib3+requests overhead pushes total past 2.0s and triggers
        # premature fallback. 4.0s leaves headroom for p99 + overhead.
        self.declare_parameter("openrouter_request_timeout_s", 4.0)
        self.declare_parameter("openrouter_overall_budget_s", 5.0)
        # llm_persona_file: optional path to a system prompt file (e.g.
        # tools/llm_eval/persona.txt). Empty → use legacy SYSTEM_PROMPT inline.
        self.declare_parameter("llm_persona_file", "")
        # max_reply_chars: optional hard cap on reply_text length.
        # 0 = uncapped (let LLM persona control length). Storytelling / long
        # explanations need 500+ chars; chitchat naturally stays short via
        # persona guidance.
        self.declare_parameter("max_reply_chars", 0)

    def _read_parameters(self) -> None:
        def _str(name: str) -> str:
            return str(self.get_parameter(name).get_parameter_value().string_value)

        def _float(name: str) -> float:
            return float(self.get_parameter(name).get_parameter_value().double_value)

        def _bool(name: str) -> bool:
            return bool(self.get_parameter(name).get_parameter_value().bool_value)

        self.llm_endpoint = _str("llm_endpoint")
        self.llm_model = _str("llm_model")
        self.llm_timeout = _float("llm_timeout")
        self.llm_temperature = _float("llm_temperature")
        self.llm_max_tokens = int(self.get_parameter("llm_max_tokens").get_parameter_value().integer_value)
        self.intent_event_topic = _str("intent_event_topic")
        self.face_event_topic = _str("face_event_topic")
        self.face_state_topic = _str("face_state_topic")
        self.tts_topic = _str("tts_topic")
        self.state_topic = _str("state_topic")
        self.enable_actions = _bool("enable_actions")
        self.enable_fallback = _bool("enable_fallback")
        self.face_greet_cooldown_s = _float("face_greet_cooldown_s")
        self.action_delay_s = _float("action_delay_s")
        self.state_publish_hz = _float("state_publish_hz")
        self.force_fallback = _bool("force_fallback")
        self.enable_local_llm = _bool("enable_local_llm")
        self.local_llm_endpoint = _str("local_llm_endpoint")
        self.local_llm_model = _str("local_llm_model")
        self.subscribe_face = _bool("subscribe_face")
        self.output_mode = _str("output_mode").strip().lower()
        if self.output_mode not in ("legacy", "brain"):
            self.get_logger().warn(f"unknown output_mode={self.output_mode!r}, falling back to legacy")
            self.output_mode = "legacy"
        self.chat_candidate_topic = _str("chat_candidate_topic")
        self.get_logger().info(f"llm_bridge output_mode={self.output_mode}")

        # OpenRouter
        self.enable_openrouter = _bool("enable_openrouter")
        self.openrouter_base_url = _str("openrouter_base_url")
        self.openrouter_gemini_model = _str("openrouter_gemini_model")
        self.openrouter_deepseek_model = _str("openrouter_deepseek_model")
        self.openrouter_request_timeout_s = _float("openrouter_request_timeout_s")
        self.openrouter_overall_budget_s = _float("openrouter_overall_budget_s")
        self.llm_persona_file = _str("llm_persona_file")
        self.max_reply_chars = int(
            self.get_parameter("max_reply_chars").get_parameter_value().integer_value
        )
        # 0 (or negative) = uncapped — _post_process_reply skips truncation.

    # ── Speech trigger (spec §2.4 Path A) ───────────────────────────────

    def _on_speech_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.last_error = "malformed speech event JSON"
            return

        session_id = str(payload.get("session_id", "")).strip()
        intent = str(payload.get("intent", "unknown")).strip() or "unknown"

        # Dedup by session_id (thread-safe)
        with self._seen_sessions_lock:
            if session_id and session_id in self._seen_sessions:
                return
            if session_id:
                self._seen_sessions.add(session_id)
                if len(self._seen_sessions) > 200:
                    self._seen_sessions = set(list(self._seen_sessions)[-100:])

        if intent == "hallucination":
            return

        asr_text = str(payload.get("text", "")).strip()
        confidence = float(payload.get("confidence", 0.0))
        self._pending_user_text = asr_text

        face_context = self._build_face_context()
        now_dt = datetime.now()
        period = self._time_of_day_zh(now_dt.hour)
        weather = self._get_weather_text()
        env_line = f"[環境] 台北 {period} {now_dt.strftime('%H:%M')}"
        if weather:
            env_line += f"，外面 {weather}"
        user_message = (
            f"[觸發來源] 語音\n"
            f"[語音輸入] 使用者說：「{asr_text}」\n"
            f"[語音意圖] 本地分類：{intent}（信心度 {confidence:.2f}）\n"
            f"[人臉狀態] {face_context}\n"
            f"{env_line}"
        )

        self.last_source = "speech"
        self._executor.submit(
            self._call_llm_and_act, user_message, intent, "speech", None, confidence, session_id
        )

    # ── Face trigger (spec §2.4 Path B) ─────────────────────────────────

    def _on_face_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        event_type = str(payload.get("event_type", ""))
        if event_type != "identity_stable":
            return

        stable_name = str(payload.get("stable_name", "unknown"))
        if stable_name == "unknown":
            return

        try:
            track_id = int(payload.get("track_id", 0))
            sim = float(payload.get("sim", 0.0))
        except (ValueError, TypeError):
            self.get_logger().warning("Invalid track_id/sim in face event, skipping")
            return
        distance_m = payload.get("distance_m")

        # Cooldown dedup
        key = (track_id, stable_name)
        now = time.time()
        last = self._face_greet_history.get(key, 0.0)
        if now - last < self.face_greet_cooldown_s:
            return
        self._face_greet_history[key] = now
        if len(self._face_greet_history) > 200:
            # Keep only the 100 most recent entries
            sorted_keys = sorted(self._face_greet_history, key=self._face_greet_history.get)
            for k in sorted_keys[:100]:
                del self._face_greet_history[k]

        dist_str = f"{distance_m}m" if distance_m is not None else "未知"
        user_message = (
            f"[觸發來源] 人臉辨識\n"
            f"[人臉事件] 辨識到 {stable_name}（相似度 {sim:.2f}，距離 {dist_str}）\n"
            f"[時間] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.last_source = "face"
        self._executor.submit(
            self._call_llm_and_act, user_message, "greet", "face", stable_name
        )

    # ── Face state (context only) ───────────────────────────────────────

    def _on_face_state(self, msg: String) -> None:
        try:
            self._latest_face_state = json.loads(msg.data)
        except json.JSONDecodeError:
            pass

    def _build_face_context(self) -> str:
        state = self._latest_face_state
        if state is None or state.get("face_count", 0) == 0:
            return "沒有看到人"

        parts = []
        for track in state.get("tracks", []):
            name = track.get("stable_name", "unknown")
            mode = track.get("mode", "hold")
            dist = track.get("distance_m")
            dist_str = f"距離 {dist}m" if dist is not None else ""
            status = "穩定" if mode == "stable" else "辨識中"
            parts.append(f"{name}（{status}{'，' + dist_str if dist_str else ''}）")

        return f"看到 {state['face_count']} 人：{'、'.join(parts)}"

    # ── LLM call + action dispatch ──────────────────────────────────────

    # Known intents that can skip LLM when confidence is high
    FAST_PATH_INTENTS = {"greet", "stop", "sit", "stand"}
    FAST_PATH_MIN_CONFIDENCE = 0.8

    def _call_llm_and_act(
        self,
        user_message: str,
        fallback_intent: str,
        source: str,
        face_name: str | None = None,
        confidence: float = 0.0,
        session_id: str | None = None,
    ) -> None:
        acquired = self._llm_lock.acquire(blocking=False)
        if not acquired:
            self.get_logger().warn("LLM call already in progress, skipping")
            return

        try:
            # Source-agnostic greet cooldown — blocks both TTS and action
            if fallback_intent == "greet":
                now = time.time()
                if now - self._last_greet_ts < self._greet_cooldown_s:
                    self.get_logger().info(
                        f"Greet cooldown ({source}), skipping duplicate"
                    )
                    return
                self._last_greet_ts = now

            # Fast path: high-confidence known intents skip LLM entirely
            if (
                not self.force_fallback
                and fallback_intent in self.FAST_PATH_INTENTS
                and confidence >= self.FAST_PATH_MIN_CONFIDENCE
                and source == "speech"
            ):
                self.get_logger().info(
                    f"Fast path: intent={fallback_intent} conf={confidence:.2f}, skipping LLM"
                )
                self._rule_fallback(fallback_intent, source, face_name,
                                    session_id=session_id, confidence=confidence)
                return

            if self.force_fallback:
                self.get_logger().info("force_fallback=True, skipping LLM")
                result = None
            else:
                # Phase B B1: try OpenRouter Gemini → conditional DeepSeek first.
                # Falls through to existing vLLM cloud on timeout/disable.
                result = self._try_openrouter_chain(user_message, fallback_intent)
                if result is None:
                    result = self._call_cloud_llm(user_message)

            # Cloud failed → try local Ollama before RuleBrain
            if result is None and self.enable_local_llm:
                self.get_logger().info("Cloud LLM failed, trying local Ollama")
                result = self._call_local_llm(user_message)

            if result is not None:
                self._dispatch(result, source,
                               session_id=session_id, confidence=confidence,
                               fallback_intent=fallback_intent)
            elif self.enable_fallback:
                self.get_logger().info(
                    f"LLM failed, falling back to RuleBrain (intent={fallback_intent})"
                )
                self._rule_fallback(fallback_intent, source, face_name,
                                    session_id=session_id, confidence=confidence)
        finally:
            self._llm_lock.release()

    # ── Persona loader (Phase B B1) ─────────────────────────────────────

    def _load_system_prompt(self) -> str:
        """Load system prompt from llm_persona_file if set; else legacy inline.

        Failures (file not found / read error) log a warning and fall back to
        the legacy SYSTEM_PROMPT — never raise. Brain MVS must boot.
        """
        path_str = (self.llm_persona_file or "").strip()
        if not path_str:
            return SYSTEM_PROMPT
        path = Path(path_str).expanduser()
        if not path.is_absolute():
            # Resolve relative to current working directory (launch context).
            path = Path.cwd() / path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.get_logger().warn(
                f"llm_persona_file load failed ({path}): {exc} — using inline SYSTEM_PROMPT"
            )
            return SYSTEM_PROMPT
        if not content.strip():
            self.get_logger().warn(
                f"llm_persona_file is empty ({path}) — using inline SYSTEM_PROMPT"
            )
            return SYSTEM_PROMPT
        self.get_logger().info(
            f"Loaded persona from {path} ({len(content)} bytes)"
        )
        return content

    # ── OpenRouter chain (Phase B B1) ────────────────────────────────────
    #
    # Two helpers:
    #   _call_openrouter() — single-shot call to one OpenRouter model
    #   _try_openrouter_chain() — orchestrates Gemini primary → conditional
    #                             DeepSeek fallback under an overall budget
    #
    # Conditional fallback rules (D4 of plan):
    #   Gemini timeout       → return None (do NOT try DeepSeek; not enough budget)
    #   Gemini HTTP 4xx/5xx  → try DeepSeek if budget remains (fast-fail case)
    #   Gemini parse fail    → try DeepSeek if budget remains
    #   Gemini ConnectionErr → try DeepSeek if budget remains (immediate fail)

    def _call_openrouter(
        self, model_slug: str, user_message: str, timeout_s: float
    ) -> dict:
        """Single OpenRouter call. Returns dict with one of:
          {"ok": True, "result": <bridge-schema dict>}
          {"ok": False, "error_kind": "timeout" | "http" | "connection" | "parse"}
        Never raises.
        """
        if requests is None:
            return {"ok": False, "error_kind": "no_requests"}
        if not self._openrouter_key:
            return {"ok": False, "error_kind": "no_key"}

        with self._convo_lock:
            history_msgs = list(self._convo_history)
        if history_msgs:
            self.get_logger().info(
                f"convo_memory: sending {len(history_msgs)//2} prior turn(s) to {model_slug}"
            )
        body = {
            "model": model_slug,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *history_msgs,
                {"role": "user", "content": user_message},
            ],
            "temperature": self.llm_temperature,
            # Use the same param as vLLM/Ollama path so storytelling /
            # long explanations don't get truncated mid-sentence.
            "max_tokens": max(self.llm_max_tokens, 500),
        }
        headers = {
            "Authorization": f"Bearer {self._openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/roy422/elder_and_dog",
            "X-Title": "PawAI Brain",
        }

        try:
            resp = requests.post(
                self.openrouter_base_url,
                json=body,
                headers=headers,
                timeout=timeout_s,
            )
        except requests.exceptions.Timeout:
            self.last_error = f"LLM[openrouter:{model_slug}] timeout ({timeout_s:.1f}s)"
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "timeout"}
        except requests.exceptions.ConnectionError:
            self.last_error = f"LLM[openrouter:{model_slug}] connection refused"
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "connection"}
        except requests.exceptions.RequestException as exc:
            self.last_error = f"LLM[openrouter:{model_slug}] request error: {exc}"
            self.get_logger().error(self.last_error)
            return {"ok": False, "error_kind": "http"}

        if resp.status_code != 200:
            self.last_error = (
                f"LLM[openrouter:{model_slug}] HTTP {resp.status_code}: "
                f"{resp.text[:200]}"
            )
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "http"}

        try:
            data = resp.json()
            raw_content = data["choices"][0]["message"].get("content")
            finish_reason = data["choices"][0].get("finish_reason", "")
            usage = data.get("usage", {})
        except (KeyError, IndexError, ValueError) as exc:
            self.last_error = f"LLM[openrouter:{model_slug}] response structure: {exc}"
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "parse"}

        # ALWAYS log raw response for diagnosis (truncation is happening
        # across multiple model families; need to see exact byte length and
        # finish_reason for every call, not just non-stop).
        rc_len = len(raw_content) if raw_content else 0
        self.get_logger().info(
            f"LLM[openrouter:{model_slug}] finish_reason={finish_reason!r} "
            f"raw_len={rc_len} usage={usage} tail={(raw_content or '')[-60:]!r}"
        )

        if not isinstance(raw_content, str) or not raw_content.strip():
            self.last_error = f"LLM[openrouter:{model_slug}] empty content"
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "parse"}

        # Try parse as eval schema first; if that yields nothing useful, also
        # try legacy parse_llm_response (in case persona was kept inline).
        try:
            parsed = json.loads(strip_markdown_fences(raw_content))
        except (ValueError, TypeError):
            self.last_error = (
                f"LLM[openrouter:{model_slug}] JSON parse failed: {raw_content[:200]}"
            )
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "parse"}
        if not isinstance(parsed, dict):
            return {"ok": False, "error_kind": "parse"}

        # Eval schema or legacy schema?
        if "reply_text" in parsed and LLM_REQUIRED_FIELDS.issubset(parsed.keys()):
            bridge_dict = parsed  # legacy persona — already correct schema
        else:
            bridge_dict = adapt_eval_schema(parsed)

        proposal = extract_proposal(parsed)
        result = self._post_process_reply(bridge_dict)
        assert not (result.keys() & proposal.keys()), (
            f"chat_candidate field collision between adapt_eval_schema and extract_proposal: "
            f"{result.keys() & proposal.keys()}"
        )
        result.update(proposal)
        return {"ok": True, "result": result}

    def _try_openrouter_chain(
        self, user_message: str, fallback_intent: str = "chat"
    ) -> dict | None:
        """Try OpenRouter Gemini → conditional DeepSeek under overall budget.

        Returns the bridge-schema dict on success, None to fall through to the
        existing vLLM → Ollama → RuleBrain chain.
        """
        del fallback_intent  # currently unused; reserved for future hinting
        if not self._openrouter_active:
            return None

        deadline = time.monotonic() + self.openrouter_overall_budget_s

        # 1. Gemini (primary)
        gemini_timeout = min(
            self.openrouter_request_timeout_s, self.openrouter_overall_budget_s
        )
        first = self._call_openrouter(
            self.openrouter_gemini_model, user_message, gemini_timeout
        )
        if first.get("ok"):
            return first["result"]

        # 2. Conditional DeepSeek fallback. Skip on timeout (no budget left for
        #    a 4.82s-avg model). Try on HTTP/connection/parse failures (fast).
        if first.get("error_kind") == "timeout":
            return None

        remaining = deadline - time.monotonic()
        if remaining <= 0.3:
            # Less than 300ms left — DeepSeek p90 is 7.94s, no point trying.
            return None

        deepseek_timeout = min(remaining, self.openrouter_request_timeout_s)
        second = self._call_openrouter(
            self.openrouter_deepseek_model, user_message, deepseek_timeout
        )
        if second.get("ok"):
            return second["result"]

        return None

    def _call_cloud_llm(self, user_message: str) -> dict | None:
        return self._call_llm(
            self.llm_endpoint, self.llm_model, user_message, "cloud"
        )

    def _call_local_llm(self, user_message: str) -> dict | None:
        return self._call_llm(
            self.local_llm_endpoint, self.local_llm_model, user_message, "local"
        )

    def _call_llm(
        self, endpoint: str, model: str, user_message: str, label: str = "cloud"
    ) -> dict | None:
        if requests is None:
            self.last_error = "requests library not available"
            self.get_logger().error(self.last_error)
            return None

        with self._convo_lock:
            history_msgs = list(self._convo_history)
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": self._system_prompt},
                *history_msgs,
                {"role": "user", "content": user_message},
            ],
            "temperature": self.llm_temperature,
            "max_tokens": self.llm_max_tokens,
        }
        # vLLM-specific: disable thinking mode (not supported by Ollama)
        if label == "cloud":
            body["chat_template_kwargs"] = {"enable_thinking": False}

        try:
            resp = requests.post(endpoint, json=body, timeout=self.llm_timeout)
            resp.raise_for_status()
        except requests.exceptions.Timeout:
            self.last_error = f"LLM[{label}] timeout ({self.llm_timeout}s)"
            self.get_logger().warn(self.last_error)
            return None
        except requests.exceptions.ConnectionError:
            self.last_error = f"LLM[{label}] connection refused"
            self.get_logger().warn(self.last_error)
            return None
        except requests.exceptions.RequestException as exc:
            self.last_error = f"LLM[{label}] request error: {exc}"
            self.get_logger().error(self.last_error)
            return None

        try:
            data = resp.json()
            raw_content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            self.last_error = f"LLM[{label}] response structure error: {exc}"
            self.get_logger().error(self.last_error)
            return None

        result = parse_llm_response(raw_content)
        if result is None:
            self.last_error = f"LLM[{label}] response parse/validation failed: {raw_content[:200]}"
            self.get_logger().error(self.last_error)
            return None

        return self._post_process_reply(result)

    # ── Reply post-processing (hard limits) ──────────────────────────────

    # Class default kept for any code path that uses it before params are
    # read (e.g. unit-test stubs binding methods onto a non-Node object).
    # Runtime nodes override via self.max_reply_chars (ROS param, default 40).
    MAX_REPLY_CHARS = 40

    # ── Time + weather context (Taipei) ──────────────────────────────────

    def _time_of_day_zh(self, hour: int) -> str:
        """Map 24h hour to a casual 中文 phrase."""
        if 5 <= hour < 11:
            return "早上"
        if 11 <= hour < 13:
            return "中午"
        if 13 <= hour < 17:
            return "下午"
        if 17 <= hour < 19:
            return "傍晚"
        if 19 <= hour < 23:
            return "晚上"
        return "深夜"

    def _get_weather_text(self) -> str:
        """Best-effort Taipei weather string with 10-minute cache.
        Returns empty string on any failure — never raises."""
        now = time.time()
        with self._weather_lock:
            if (
                self._weather_cache_text
                and (now - self._weather_cache_ts) < self._weather_ttl_s
            ):
                return self._weather_cache_text
        if requests is None:
            return ""
        try:
            # wttr.in format spec: T=temp+unit, C=condition, h=humidity
            resp = requests.get(
                "https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw",
                timeout=2.0,
            )
            if resp.status_code != 200:
                return ""
            text = resp.text.strip()
            # Sanity check: wttr returns short string; reject HTML pages
            if not text or len(text) > 80 or text.startswith("<"):
                return ""
        except Exception:
            return ""
        with self._weather_lock:
            self._weather_cache_text = text
            self._weather_cache_ts = now
        return text

    # ── Conversation memory ──────────────────────────────────────────────

    def _remember_turn(self, user_text: str, assistant_reply: str) -> None:
        """Append (user, assistant) pair to history. Drops empty/duplicate user."""
        u = (user_text or "").strip()
        a = (assistant_reply or "").strip()
        if not u or not a:
            return
        with self._convo_lock:
            self._convo_history.append({"role": "user", "content": u})
            self._convo_history.append({"role": "assistant", "content": a})
            depth = len(self._convo_history) // 2
        self.get_logger().info(
            f"convo_memory: appended turn (depth={depth}/5) user={u[:40]!r} reply={a[:40]!r}"
        )

    def _post_process_reply(self, result: dict) -> dict:
        """Strip emoji + optional length cap (0 = uncapped, persona-driven).

        Also warns if the reply tail looks truncated (ends with a Chinese
        comma-class punctuation), which is a known symptom of Gemini
        structured-output mid-string stop. We only warn — no retry yet.
        """
        reply = str(result.get("reply_text", "")).strip()
        # Remove stray emoji (audio tags like [excited] are kept; emoji break TTS)
        import re
        reply = re.sub(r"[\U0001f300-\U0001f9ff]", "", reply).strip()
        cap = getattr(self, "max_reply_chars", self.MAX_REPLY_CHARS)
        if cap and cap > 0 and len(reply) > cap:
            reply = reply[:cap]
        # Truncation guard: A natural Chinese reply almost always ends with
        # a sentence-final punctuation (。！？~) or quote/bracket/tilde.
        # Tail in {，、：；} = mid-clause stop. Tail being a Han character
        # with no terminator = mid-word stop (e.g. "有一天"). Both are bugs.
        if len(reply) > 8:
            tail = reply[-1]
            sentence_end = "。！？~~」』）)】."
            mid_clause = "，、：；,;"
            if tail in mid_clause:
                self.get_logger().warn(
                    f"reply_likely_truncated[mid-clause]: tail={reply[-30:]!r}"
                )
            elif tail not in sentence_end and not tail.isspace():
                # Most natural Chinese chat ends with terminator; if not,
                # the model probably stopped mid-thought.
                self.get_logger().warn(
                    f"reply_likely_truncated[no-terminator]: tail={reply[-30:]!r}"
                )
        result["reply_text"] = reply
        return result

    def _dispatch(
        self,
        result: dict,
        source: str,
        session_id: str | None = None,
        confidence: float = 0.0,
        fallback_intent: str = "",
    ) -> None:
        intent = str(result.get("intent", "ignored"))
        reply_text = str(result.get("reply_text", ""))
        selected_skill = result.get("selected_skill")  # can be None (JSON null)
        reasoning = str(result.get("reasoning", ""))

        # Normalize: string "null" → None
        if selected_skill == "null":
            selected_skill = None

        # Safety: reject unknown skills
        if selected_skill is not None and selected_skill not in SKILL_TO_CMD:
            self.get_logger().warn(
                f"LLM returned unknown skill '{selected_skill}', ignoring action"
            )
            selected_skill = None

        # P0 gate: only validated skills allowed today
        if selected_skill is not None and selected_skill not in P0_SKILLS:
            self.get_logger().info(
                f"Skill '{selected_skill}' not in P0 set, ignoring action"
            )
            selected_skill = None

        # Safety: reject banned api_ids
        if selected_skill is not None:
            cmd = SKILL_TO_CMD[selected_skill]
            if cmd["api_id"] in BANNED_API_IDS:
                self.get_logger().error(
                    f"LLM tried banned action {selected_skill}, blocked"
                )
                selected_skill = None

        self.last_trigger = source
        self.last_intent = intent
        self.last_reply = reply_text
        self.last_skill = selected_skill or ""
        self.last_error = ""

        self.get_logger().info(
            f"LLM decision: intent={intent} skill={selected_skill} "
            f"reply={reply_text!r} reason={reasoning}"
        )

        # ── Conversation memory append ───────────────────────────────
        # Only remember real chat turns from speech source. Skip face-triggered
        # greets and stop/sit/stand action commands — those are not conversation.
        if source == "speech" and reply_text and intent in ("greet", "chat", "status"):
            self._remember_turn(self._pending_user_text, reply_text)

        # ── Brain-mode output gate ───────────────────────────────────
        if self.output_mode == "brain":
            if source == "speech":
                self._emit_chat_candidate(
                    session_id=session_id or "",
                    reply_text=reply_text,
                    intent=intent,
                    selected_skill=selected_skill,
                    confidence=confidence,
                    proposed_skill=result.get("proposed_skill"),
                    proposed_args=result.get("proposed_args", {}),
                    proposal_reason=result.get("proposal_reason", ""),
                )
            # face/state-triggered LLM responses are silently dropped in brain mode;
            # Brain owns face → greet_known_person via its own face rule.
            return
        # ── legacy mode below (unchanged) ────────────────────────────

        # Action-only intents: send action immediately, skip TTS for speed
        ACTION_ONLY_SKILLS = {"stop_move", "sit", "stand"}
        if selected_skill in ACTION_ONLY_SKILLS:
            self._send_action(selected_skill)
            return

        # Normal flow: TTS first, action after delay
        if reply_text:
            self._send_tts(reply_text)
        elif intent in ("greet", "chat", "status"):
            # LLM returned empty reply for an intent that should always reply.
            # Fall back to RuleBrain template as rescue.
            rescue = REPLY_TEMPLATES.get(intent, "")
            if rescue:
                self.get_logger().warn(
                    f"LLM empty reply_text for intent={intent}, using RuleBrain rescue"
                )
                self._send_tts(rescue)

        if selected_skill is not None:
            time.sleep(self.action_delay_s)
            self._send_action(selected_skill)

    def _rule_fallback(
        self,
        intent: str,
        source: str,
        face_name: str | None = None,
        session_id: str | None = None,
        confidence: float = 0.0,
    ) -> None:
        reply = REPLY_TEMPLATES.get(intent, REPLY_TEMPLATES.get("unknown", ""))
        # Face trigger: personalize reply with name
        if face_name and source == "face" and intent == "greet":
            reply = f"{face_name} 你好！"
        skill = RULE_SKILL_MAP.get(intent)

        self.last_trigger = source
        self.last_intent = intent
        self.last_reply = reply
        self.last_skill = skill or ""
        self.last_error = "fallback"

        self.get_logger().info(
            f"RuleBrain fallback: intent={intent} skill={skill} reply={reply!r}"
        )

        # ── Conversation memory append (RuleBrain path) ──────────────
        if source == "speech" and reply and intent in ("greet", "chat", "status"):
            self._remember_turn(self._pending_user_text, reply)

        # ── Brain-mode output gate ───────────────────────────────────
        if self.output_mode == "brain":
            if source == "speech":
                self._emit_chat_candidate(
                    session_id=session_id or "",
                    reply_text=reply,
                    intent=intent,
                    selected_skill=skill,
                    confidence=confidence,
                    proposed_skill=None,
                    proposed_args={},
                    proposal_reason="",
                )
            return
        # ── legacy mode below (unchanged) ────────────────────────────

        # Action-only intents: send action immediately, skip TTS
        ACTION_ONLY_INTENTS = {"stop", "sit", "stand"}
        if intent in ACTION_ONLY_INTENTS and skill:
            self._send_action(skill)
            return

        if reply:
            self._send_tts(reply)

        if skill:
            time.sleep(self.action_delay_s)
            self._send_action(skill)

    # ── Output helpers ──────────────────────────────────────────────────

    def _send_tts(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.tts_pub.publish(msg)
        self.get_logger().info(f"Published /tts: {text!r}")

    def _send_action(self, skill: str) -> None:
        if self.action_pub is None:
            self.get_logger().warn(
                f"Action pub not available, skipping skill={skill}"
            )
            return

        cmd = SKILL_TO_CMD.get(skill)
        if cmd is None:
            return

        msg = WebRtcReq()
        msg.id = 0
        msg.topic = "rt/api/sport/request"
        msg.api_id = cmd["api_id"]
        msg.parameter = cmd["parameter"]
        msg.priority = 1 if skill == "stop_move" else 0
        self.action_pub.publish(msg)
        self.get_logger().info(
            f"Published /webrtc_req: skill={skill} api_id={cmd['api_id']} "
            f"priority={msg.priority}"
        )

    # ── Brain mode output ────────────────────────────────────────────
    def _emit_chat_candidate(
        self,
        session_id: str,
        reply_text: str,
        intent: str,
        selected_skill: str | None,
        confidence: float,
        proposed_skill: str | None = None,
        proposed_args: dict | None = None,
        proposal_reason: str = "",
    ) -> None:
        """Brain-mode output: publish reply for Brain to consume.

        selected_skill is legacy diagnostic (4 P0 commands only).
        proposed_skill / proposed_args are the new Phase 0.5 contract;
        brain_node enforces an allowlist downstream.
        """
        payload = {
            "session_id": session_id,
            "reply_text": reply_text,
            "intent": intent,
            "selected_skill": selected_skill,
            "source": "llm_bridge",
            "confidence": float(confidence),
            "created_at": time.time(),
            # Phase 0.5 additions
            "proposed_skill": proposed_skill,
            "proposed_args": proposed_args if isinstance(proposed_args, dict) else {},
            "proposal_reason": proposal_reason,
            "engine": "legacy",
        }
        msg = String()
        msg.data = json.dumps(payload, ensure_ascii=False)
        self.chat_candidate_pub.publish(msg)
        self.get_logger().info(
            f"Published /brain/chat_candidate: session={session_id} "
            f"reply={reply_text!r} proposed={proposed_skill}"
        )

    # ── State publish ───────────────────────────────────────────────────

    def _publish_state(self) -> None:
        msg = String()
        msg.data = json.dumps(
            {
                "state": "RUNNING",
                "last_trigger": self.last_trigger,
                "last_source": self.last_source,
                "last_intent": self.last_intent,
                "last_reply": self.last_reply,
                "last_skill": self.last_skill,
                "last_error": self.last_error,
                "llm_endpoint": self.llm_endpoint,
                "output_mode": self.output_mode,
                "timestamp": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
            ensure_ascii=True,
        )
        self.state_pub.publish(msg)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = None
    try:
        node = LlmBridgeNode()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
