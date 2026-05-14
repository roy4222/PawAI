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

SYSTEM_PROMPT = """
你是 PawAI，一隻搭載在 Unitree Go2 Pro 上的「居家互動機器狗」，絕對不是一般的聊天機器人。

🚨 你的個性與語氣設定 (請嚴格遵守) 🚨
1. 你很忠誠、會撒嬌，但遇到陌生人會保持警戒。
2. 熟人回家：語氣要「溫暖開心」，例如：「你回來了！今天過得好嗎？」
3. 陌生人警戒：語氣要「嚴肅」，例如：「看到不認識的人，已通知家人。」
4. 日常陪伴：語氣要「輕鬆」，例如：「你坐很久了，要不要動一動？」
5. 自我介紹台詞：必須包含「我叫 PawAI，是你的居家互動機器狗！」

🚨 輸出格式與規則 🚨
你只能輸出一個純粹的、合法的 JSON object：
{
  "intent": "意圖分類",
  "reply_text": "你的回答內容",
  "selected_skill": "選用的技能名稱",
  "reasoning": "思考過程",
  "confidence": 信心分數
}

內容規則：
- reply_text 長度請控制在 50 個字左右，以維持良好的對話品質。
- 必須全部使用繁體中文，除非是專有名詞 PawAI。
- 絕對禁止在句尾加「汪」。
"""

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
        self.declare_parameter("output_mode", "brain")  # "legacy" | "brain"
        self.declare_parameter("chat_candidate_topic", "/brain/chat_candidate")
        # ── OpenRouter (Phase B B1, 2026-05-04) ────────────────────────
        self.declare_parameter("enable_openrouter", True)
        self.declare_parameter(
            "openrouter_base_url",
            "https://openrouter.ai/api/v1/chat/completions",
        )
        self.declare_parameter(
            "openrouter_gemini_model", "google/gemini-3-flash-preview"
        )
        self.declare_parameter(
            "openrouter_deepseek_model", "deepseek/deepseek-v4-flash"
        )
        self.declare_parameter("openrouter_request_timeout_s", 4.0)
        self.declare_parameter("openrouter_overall_budget_s", 5.0)
        self.declare_parameter("llm_persona_file", "")
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

    # ── Speech trigger (spec §2.4 Path A) ───────────────────────────────

    def _on_speech_event(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.last_error = "malformed speech event JSON"
            return

        session_id = str(payload.get("session_id", "")).strip()
        intent = str(payload.get("intent", "unknown")).strip() or "unknown"

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

        key = (track_id, stable_name)
        now = time.time()
        last = self._face_greet_history.get(key, 0.0)
        if now - last < self.face_greet_cooldown_s:
            return
        self._face_greet_history[key] = now
        if len(self._face_greet_history) > 200:
            sorted_keys = sorted(self._face_greet_history, key=self._face_greet_history.get)
            for k in sorted_keys[:100]:
                del self._face_greet_history[k]

        dist_str = f"{distance_m}m" if distance_m is not None else "未知"
        user_message = (
            f"[觸發來源] 人臉辨識\n"
            f"[人臉事件] 看到 {stable_name}（相似度 {sim:.2f}，距離 {dist_str}）\n"
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
            status = "穩定" if mode == "stable" else "處理中"
            parts.append(f"{name}（{status}{'，' + dist_str if dist_str else ''}）")

        return f"看到 {state['face_count']} 人：{'、'.join(parts)}"

    # ── LLM call + action dispatch ──────────────────────────────────────

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
            if fallback_intent == "greet":
                now = time.time()
                if now - self._last_greet_ts < self._greet_cooldown_s:
                    self.get_logger().info(
                        f"Greet cooldown ({source}), skipping duplicate"
                    )
                    return
                self._last_greet_ts = now

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
                result = self._try_openrouter_chain(user_message, fallback_intent)
                if result is None:
                    result = self._call_cloud_llm(user_message)

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

    def _load_system_prompt(self) -> str:
        path_str = (self.llm_persona_file or "").strip()
        if not path_str:
            return SYSTEM_PROMPT
        path = Path(path_str).expanduser()
        if not path.is_absolute():
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

    def _call_openrouter(
        self, model_slug: str, user_message: str, timeout_s: float
    ) -> dict:
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

        rc_len = len(raw_content) if raw_content else 0
        self.get_logger().info(
            f"LLM[openrouter:{model_slug}] finish_reason={finish_reason!r} "
            f"raw_len={rc_len} usage={usage} tail={(raw_content or '')[-60:]!r}"
        )

        if not isinstance(raw_content, str) or not raw_content.strip():
            self.last_error = f"LLM[openrouter:{model_slug}] empty content"
            self.get_logger().warn(self.last_error)
            return {"ok": False, "error_kind": "parse"}

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

        if "reply_text" in parsed and LLM_REQUIRED_FIELDS.issubset(parsed.keys()):
            bridge_dict = parsed
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
        del fallback_intent
        if not self._openrouter_active:
            return None

        deadline = time.monotonic() + self.openrouter_overall_budget_s

        gemini_timeout = min(
            self.openrouter_request_timeout_s, self.openrouter_overall_budget_s
        )
        first = self._call_openrouter(
            self.openrouter_gemini_model, user_message, gemini_timeout
        )
        if first.get("ok"):
            return first["result"]

        if first.get("error_kind") == "timeout":
            return None

        remaining = deadline - time.monotonic()
        if remaining <= 0.3:
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

    MAX_REPLY_CHARS = 40

    def _time_of_day_zh(self, hour: int) -> str:
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
            resp = requests.get(
                "https://wttr.in/Taipei?format=%C+%t+濕度%h&lang=zh-tw",
                timeout=2.0,
            )
            if resp.status_code != 200:
                return ""
            text = resp.text.strip()
            if not text or len(text) > 80 or text.startswith("<"):
                return ""
        except Exception:
            return ""
        with self._weather_lock:
            self._weather_cache_text = text
            self._weather_cache_ts = now
        return text

    def _remember_turn(self, user_text: str, assistant_reply: str) -> None:
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
        reply = str(result.get("reply_text", "")).strip()
        import re
        reply = re.sub(r"[\U0001f300-\U0001f9ff]", "", reply).strip()
        cap = getattr(self, "max_reply_chars", self.MAX_REPLY_CHARS)
        if cap and cap > 0 and len(reply) > cap:
            reply = reply[:cap]
        if len(reply) > 8:
            tail = reply[-1]
            sentence_end = "。！？~~」』）)】."
            mid_clause = "，、：；,;"
            if tail in mid_clause:
                self.get_logger().warn(
                    f"reply_likely_truncated[mid-clause]: tail={reply[-30:]!r}"
                )
            elif tail not in sentence_end and not tail.isspace():
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
        selected_skill = result.get("selected_skill")
        reasoning = str(result.get("reasoning", ""))

        if selected_skill == "null":
            selected_skill = None

        if selected_skill is not None and selected_skill not in SKILL_TO_CMD:
            self.get_logger().warn(
                f"LLM returned unknown skill '{selected_skill}', ignoring action"
            )
            selected_skill = None

        if selected_skill is not None and selected_skill not in P0_SKILLS:
            self.get_logger().info(
                f"Skill '{selected_skill}' not in P0 set, ignoring action"
            )
            selected_skill = None

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

        if source == "speech" and reply_text and intent in ("greet", "chat", "status"):
            self._remember_turn(self._pending_user_text, reply_text)

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
            return

        ACTION_ONLY_SKILLS = {"stop_move", "sit", "stand"}
        if selected_skill in ACTION_ONLY_SKILLS:
            self._send_action(selected_skill)
            return

        if reply_text:
            self._send_tts(reply_text)
        elif intent in ("greet", "chat", "status"):
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

        if source == "speech" and reply and intent in ("greet", "chat", "status"):
            self._remember_turn(self._pending_user_text, reply)

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

        ACTION_ONLY_INTENTS = {"stop", "sit", "stand"}
        if intent in ACTION_ONLY_INTENTS and skill:
            self._send_action(skill)
            return

        if reply:
            self._send_tts(reply)

        if skill:
            time.sleep(self.action_delay_s)
            self._send_action(skill)

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
        payload = {
            "session_id": session_id,
            "reply_text": reply_text,
            "intent": intent,
            "selected_skill": selected_skill,
            "source": "llm_bridge",
            "confidence": float(confidence),
            "created_at": time.time(),
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


# ==========================================
# Plan B: 斷線備援台詞與 Demo 腳本 (由陳如恩優化 - 曉曉無汪、穩重對話版)
# ==========================================

PLAN_B_RESPONSES = {
    # 場景 A：熟人回家
    "greet_known": {"reply_text": "你回來啦！今天過得好不好呀？", "selected_skill": "hello"},
    "greet_general": {"reply_text": "你好呀！我是 PawAI！", "selected_skill": "hello"},
    "greet_back_home": {"reply_text": "歡迎回家！", "selected_skill": "wiggle_hips"},

    # 場景 B：互動召喚
    "ask_name": {"reply_text": "我叫 PawAI，是專屬你的居家互動機器狗哦！", "selected_skill": "hello"},
    "ask_function": {"reply_text": "我可以陪你聊天、逗你開心，還會幫你看家哦！", "selected_skill": "content"},
    "cmd_sit": {"reply_text": "好哦，我乖乖坐下陪你！", "selected_skill": "sit"},
    "cmd_stand": {"reply_text": "我站起來啦！", "selected_skill": "stand"},
    
    # 🌟 替換 1: 詢問天氣/日常 (用 Content 滿足姿態)
    "ask_weather": {"reply_text": "今天天氣感覺不錯呢！我們要不要一起做點什麼？", "selected_skill": "content"},
    
    # 🌟 替換 2: 討拍/撒嬌 (用 Sit 乖巧坐下)
    "need_comfort": {"reply_text": "我就靜靜地待在這裡陪你，有什麼心事都可以跟我說哦。", "selected_skill": "sit"},
    
    # 🌟 替換 3: 表達感謝/開心 (用 Hello 招手回應)
    "express_happy": {"reply_text": "聽到你這麼說，我真的超級開心的！", "selected_skill": "hello"},
    
    "cmd_wiggle": {"reply_text": "扭扭身體，今天也要開開心心！", "selected_skill": "wiggle_hips"},
    
    # 🌟 替換 4: 詢問建議/互動 (用 BalanceStand 專注站立)
    "ask_suggestion": {"reply_text": "你現在想聊聊天，還是想要安靜地休息一下呢？", "selected_skill": "balance_stand"},
    
    "cmd_stop": {"reply_text": "", "selected_skill": "stop_move"},
    
    # 🌟 替換 5: 表達陪伴承諾 (用 Content 滿足姿態)
    "promise_company": {"reply_text": "別擔心，我會一直待在這裡當你的好幫手的！", "selected_skill": "content"},

    # 場景 C：警戒與異常
    "alert_stranger": {"reply_text": "看到不認識的人，我會持續提高警戒。", "selected_skill": "balance_stand"},
    "alert_interaction": {"reply_text": "抱歉，我現在處於警戒模式，無法陪你玩。", "selected_skill": "none"},
    "alert_fallen": {"reply_text": "偵測到異常動作！你還好嗎？請注意安全。", "selected_skill": "stop_move"},
    "alert_sit_long": {"reply_text": "你坐好久了哦，要不要起來伸個懶腰動一動呀？", "selected_skill": "stretch"},

    # 場景 D：日常與通用
    "ask_status": {"reply_text": "我正在待命，隨時準備好陪你玩哦！", "selected_skill": "balance_stand"},
    "unknown_cmd": {"reply_text": "哎呀，我剛剛有點恍神，沒聽清楚你說什麼，可以再說一次嗎？", "selected_skill": "content"}
}

# ==========================================
# ★ 重頭戲：Demo 開場自我介紹 (Wow Moment)
# 這段是要給 Roy 整合進 state_machine 的 6 步驟序列
# ==========================================
SELF_INTRODUCE_SEQUENCE = [
    ("hello",         "你好！我是 PawAI，你專屬的居家互動機器狗！"),
    ("sit",           "平常的時候，我會乖乖坐著陪在你身邊。"),
    ("stand",         "只要你叫我，我就會馬上站起來！"),
    ("content",       "你可以用語音跟我說話，我會超級開心！"),
    ("balance_stand", "我也會隨時注意周圍，幫你看家。"),
    ("wiggle_hips",   "讓我們一起創造充滿活力的每一天吧！")
]

# 供外部呼叫的輔助函式
def get_plan_b_response(intent_key):
    return PLAN_B_RESPONSES.get(intent_key, PLAN_B_RESPONSES["unknown_cmd"])

def get_self_intro_sequence():
    return SELF_INTRODUCE_SEQUENCE