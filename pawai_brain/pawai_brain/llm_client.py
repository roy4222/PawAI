"""OpenRouterClient — Gemini → DeepSeek conditional fallback chain.

Mirrors llm_bridge_node._call_openrouter + _try_openrouter_chain
(speech_processor/speech_processor/llm_bridge_node.py:542-701) so behaviour
is identical between primary (pawai_brain) and fallback (llm_bridge_node).

Pure module: no ROS, no node lifecycle. Logging via the provided logger
callback (default: print to stderr) so unit tests don't need a Node.
"""
from __future__ import annotations
import os
import sys
import time
from dataclasses import dataclass
from typing import Callable

try:
    import requests
except Exception:  # pragma: no cover
    requests = None  # type: ignore


def _stderr_logger(msg: str) -> None:
    print(f"[OpenRouterClient] {msg}", file=sys.stderr)


def resolve_openrouter_key(enable_openrouter: bool, env: dict) -> str:
    """Gate the OpenRouter API key by the `enable_openrouter` ROS param.

    Pure helper — no rclpy dependency, fully unit-testable. Returns empty
    string when disabled so OpenRouterClient.active becomes False; the graph
    then exhausts the LLM chain on every turn and output_builder routes to
    RuleBrain say_canned via response_repair / repair_failed.

    Args:
        enable_openrouter: ROS param value (mirrors llm_bridge_node).
        env: os.environ-shaped mapping (so tests can inject fakes).

    Returns:
        Empty string when disabled or no key configured; otherwise the
        stripped key from OPENROUTER_KEY / OPENROUTER_API_KEY (in that order).
    """
    if not enable_openrouter:
        return ""
    return (env.get("OPENROUTER_KEY") or env.get("OPENROUTER_API_KEY") or "").strip()


@dataclass
class OpenRouterConfig:
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    gemini_model: str = "google/gemini-3-flash-preview"
    deepseek_model: str = "deepseek/deepseek-v4-flash"
    request_timeout_s: float = 4.0
    overall_budget_s: float = 5.0
    temperature: float = 0.2
    max_tokens: int = 500
    referer: str = "https://github.com/roy422/elder_and_dog"
    title: str = "PawAI Brain"


class OpenRouterClient:
    """OpenRouter chat client with Gemini → DeepSeek conditional fallback.

    Conditional fallback rules (mirrors llm_bridge):
      timeout        → return None (no budget for second model)
      HTTP 4xx/5xx   → try DeepSeek if budget remains
      ConnectionErr  → try DeepSeek if budget remains
      parse fail     → try DeepSeek if budget remains
    """

    def __init__(
        self,
        config: OpenRouterConfig | None = None,
        api_key: str | None = None,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config or OpenRouterConfig()
        self.api_key = (api_key or os.environ.get("OPENROUTER_KEY")
                        or os.environ.get("OPENROUTER_API_KEY") or "").strip()
        self.log = logger or _stderr_logger
        self.last_error: str = ""

    @property
    def active(self) -> bool:
        return bool(self.api_key) and requests is not None

    def chat(
        self,
        system_prompt: str,
        history: list[dict],
        user_message: str,
    ) -> dict | None:
        """Run Gemini primary → conditional DeepSeek fallback.

        Returns:
            {"raw": <str>, "model": <slug>}  on success (caller parses raw)
            None                              on chain exhaustion / not active
        """
        if not self.active:
            self.last_error = "openrouter inactive (no key or no requests)"
            return None

        deadline = time.monotonic() + self.config.overall_budget_s

        first_timeout = min(self.config.request_timeout_s, self.config.overall_budget_s)
        first = self._single_call(
            self.config.gemini_model, system_prompt, history, user_message, first_timeout
        )
        if first.get("ok"):
            return {"raw": first["raw"], "model": self.config.gemini_model}

        if first.get("error_kind") == "timeout":
            return None  # no budget for the slower fallback

        remaining = deadline - time.monotonic()
        if remaining <= 0.3:
            return None

        second_timeout = min(remaining, self.config.request_timeout_s)
        second = self._single_call(
            self.config.deepseek_model, system_prompt, history, user_message, second_timeout
        )
        if second.get("ok"):
            return {"raw": second["raw"], "model": self.config.deepseek_model}
        return None

    # ── internals ──────────────────────────────────────────────────────

    def _single_call(
        self,
        model_slug: str,
        system_prompt: str,
        history: list[dict],
        user_message: str,
        timeout_s: float,
    ) -> dict:
        """One-shot call. Returns:
          {"ok": True, "raw": <str>}
          {"ok": False, "error_kind": "timeout|http|connection|parse"}
        Never raises.
        """
        body = {
            "model": model_slug,
            "messages": [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": user_message},
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.referer,
            "X-Title": self.config.title,
        }
        try:
            resp = requests.post(
                self.config.base_url, json=body, headers=headers, timeout=timeout_s
            )
        except requests.exceptions.Timeout:
            self.last_error = f"openrouter:{model_slug} timeout {timeout_s:.1f}s"
            self.log(self.last_error)
            return {"ok": False, "error_kind": "timeout"}
        except requests.exceptions.ConnectionError:
            self.last_error = f"openrouter:{model_slug} connection refused"
            self.log(self.last_error)
            return {"ok": False, "error_kind": "connection"}
        except requests.exceptions.RequestException as exc:
            self.last_error = f"openrouter:{model_slug} request error: {exc}"
            self.log(self.last_error)
            return {"ok": False, "error_kind": "http"}

        if resp.status_code != 200:
            self.last_error = (
                f"openrouter:{model_slug} HTTP {resp.status_code}: {resp.text[:200]}"
            )
            self.log(self.last_error)
            return {"ok": False, "error_kind": "http"}

        try:
            data = resp.json()
            raw_content = data["choices"][0]["message"].get("content")
        except (KeyError, IndexError, ValueError) as exc:
            self.last_error = f"openrouter:{model_slug} parse: {exc}"
            self.log(self.last_error)
            return {"ok": False, "error_kind": "parse"}

        if not isinstance(raw_content, str) or not raw_content.strip():
            self.last_error = f"openrouter:{model_slug} empty content"
            self.log(self.last_error)
            return {"ok": False, "error_kind": "parse"}

        return {"ok": True, "raw": raw_content}
