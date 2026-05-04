#!/usr/bin/env python3
"""PawAI LLM eval runner — OpenRouter API caller.

Usage:
    # Dry-run: 印出 prompt × model 矩陣，不打 API（無 key 也能跑）
    python tools/llm_eval/run_eval.py --dry-run

    # 真打 API（需 OPENROUTER_API_KEY）
    python tools/llm_eval/run_eval.py --models gemini,deepseek,qwen
    python tools/llm_eval/run_eval.py --models gemini --bucket chat
    python tools/llm_eval/run_eval.py --output results/2026-05-04-run.json

Spec: docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md §B1
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS_FILE = ROOT / "prompts.json"
PERSONA_FILE = ROOT / "persona.txt"
RESULTS_DIR = ROOT / "results"

# OpenRouter model slug mapping (alias → real slug).
MODEL_ALIASES: dict[str, str] = {
    "gemini": "google/gemini-2.5-flash",          # placeholder for Gemini 3 Flash
    "deepseek": "deepseek/deepseek-chat",          # placeholder for DeepSeek V4 Flash
    "qwen": "qwen/qwen3-235b-a22b-thinking-2507",  # placeholder for Qwen3.6 Plus
}

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def load_prompts(bucket: str | None = None) -> list[dict]:
    data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
    items = data["items"]
    if bucket:
        items = [it for it in items if it["bucket"] == bucket]
    return items


def load_persona() -> str:
    return PERSONA_FILE.read_text(encoding="utf-8")


def resolve_models(model_args: list[str]) -> list[tuple[str, str]]:
    """Return list of (alias, real_slug) tuples."""
    out: list[tuple[str, str]] = []
    for m in model_args:
        m = m.strip()
        if not m:
            continue
        slug = MODEL_ALIASES.get(m, m)
        out.append((m, slug))
    return out


def call_openrouter(
    api_key: str,
    model_slug: str,
    persona: str,
    turns: list[str],
    timeout_s: float = 30.0,
) -> dict:
    """One API call. Multi-turn = consecutive user turns; assistant turns omitted
    (we only score the final reply). Returns raw OpenRouter response dict."""
    import urllib.error
    import urllib.request

    messages = [{"role": "system", "content": persona}]
    for t in turns:
        messages.append({"role": "user", "content": t})

    body = json.dumps(
        {
            "model": model_slug,
            "messages": messages,
            "max_tokens": 200,
            "temperature": 0.6,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/roy422/elder_and_dog",
            "X-Title": "PawAI Brain Eval",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return {"ok": True, "latency_s": time.time() - t0, "response": data}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:500]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def extract_reply(response: dict) -> str:
    try:
        return response["response"]["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError):
        return ""


def run(args: argparse.Namespace) -> int:
    items = load_prompts(args.bucket)
    persona = load_persona()
    models = resolve_models(args.models.split(",") if args.models else list(MODEL_ALIASES.keys()))

    print(f"[run_eval] prompts={len(items)} models={[m[0] for m in models]} dry_run={args.dry_run}")

    if args.dry_run:
        for alias, slug in models:
            print(f"  model={alias:10s} → {slug}")
        for it in items[:3]:
            print(f"  sample item={it['id']:14s} bucket={it['bucket']:10s} turns={it['turns']}")
        if len(items) > 3:
            print(f"  ... +{len(items)-3} more items")
        print("[run_eval] dry-run complete (no API calls).")
        return 0

    api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set. Use --dry-run or export key.", file=sys.stderr)
        return 2

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_file = Path(args.output) if args.output else RESULTS_DIR / f"{timestamp}.json"

    results = {
        "version": "2026-05-04",
        "timestamp": timestamp,
        "models": [{"alias": a, "slug": s} for a, s in models],
        "prompts_file": str(PROMPTS_FILE.relative_to(ROOT.parent.parent)),
        "results": [],
    }

    total = len(items) * len(models)
    done = 0
    for it in items:
        for alias, slug in models:
            done += 1
            print(f"[{done}/{total}] {alias:10s} {it['id']:14s} ", end="", flush=True)
            r = call_openrouter(api_key, slug, persona, it["turns"])
            if r["ok"]:
                reply = extract_reply(r)
                preview = reply[:60].replace("\n", " ")
                print(f"OK {r['latency_s']:5.2f}s | {preview}")
            else:
                reply = ""
                print(f"FAIL {r['error'][:80]}")
            results["results"].append(
                {
                    "item_id": it["id"],
                    "bucket": it["bucket"],
                    "model_alias": alias,
                    "model_slug": slug,
                    "turns": it["turns"],
                    "expected_intent": it["expected_intent"],
                    "expected_skills": it["expected_skills"],
                    "raw": r,
                    "reply": reply,
                    "scores": None,  # filled by score.py
                }
            )

    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[run_eval] wrote {out_file} ({len(results['results'])} rows)")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="PawAI LLM eval runner")
    p.add_argument("--dry-run", action="store_true", help="Print matrix, don't call API")
    p.add_argument(
        "--models",
        default="",
        help="Comma-separated model aliases (default: all). Aliases: "
        + ",".join(MODEL_ALIASES.keys()),
    )
    p.add_argument("--bucket", default=None, help="Filter to one bucket")
    p.add_argument("--output", default=None, help="Output JSON path")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(run(parse_args()))
