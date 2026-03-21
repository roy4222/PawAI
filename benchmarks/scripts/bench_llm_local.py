#!/usr/bin/env python3
"""Benchmark local LLM (Ollama HTTP API) on Jetson."""
import json
import time
import sys
import urllib.request
import urllib.error

OLLAMA_URL = "http://localhost:11434/api/generate"

PROMPTS = [
    "你好",
    "你叫什麼名字？",
    "現在幾點了？",
    "今天天氣怎麼樣？",
    "過來這裡",
    "你在做什麼？",
    "幫我拍照",
    "停下來",
    "我很開心",
    "謝謝你",
]

SYSTEM = "你是一隻叫 PawAI 的機器狗助手。用繁體中文回答，每次回覆不超過25個字。只回覆純文字，不要JSON。"


def ollama_generate(model: str, prompt: str, timeout: float = 30) -> dict:
    """Call Ollama generate API, return timing + response."""
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "system": SYSTEM,
        "stream": False,
        "options": {"num_predict": 64, "temperature": 0.7},
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
        elapsed = time.perf_counter() - t0

        reply = data.get("response", "").strip()
        # Ollama API returns timing in nanoseconds
        total_ns = data.get("total_duration", 0)
        load_ns = data.get("load_duration", 0)
        prompt_ns = data.get("prompt_eval_duration", 0)
        eval_ns = data.get("eval_duration", 0)
        eval_count = data.get("eval_count", 0)

        tok_per_sec = (eval_count / (eval_ns / 1e9)) if eval_ns > 0 else 0

        return {
            "success": True,
            "reply": reply,
            "char_count": len(reply),
            "elapsed_s": round(elapsed, 2),
            "total_s": round(total_ns / 1e9, 2),
            "load_s": round(load_ns / 1e9, 2),
            "prompt_eval_s": round(prompt_ns / 1e9, 2),
            "eval_s": round(eval_ns / 1e9, 2),
            "eval_tokens": eval_count,
            "tok_per_sec": round(tok_per_sec, 1),
        }
    except Exception as e:
        elapsed = time.perf_counter() - t0
        return {
            "success": False, "reply": str(e), "char_count": 0,
            "elapsed_s": round(elapsed, 2), "total_s": 0, "load_s": 0,
            "prompt_eval_s": 0, "eval_s": 0, "eval_tokens": 0, "tok_per_sec": 0,
        }


def bench_model(model_name: str, n_runs: int = 10):
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_name} ({n_runs} runs, Ollama API)")
    print(f"{'='*60}")

    ram_before = get_ram_used_mb()
    results = []

    for i, prompt in enumerate(PROMPTS[:n_runs]):
        print(f"  [{i+1}/{n_runs}] '{prompt}' ... ", end="", flush=True)
        r = ollama_generate(model_name, prompt)
        results.append({**r, "prompt": prompt})
        if r["success"]:
            print(f"{r['elapsed_s']:.1f}s | {r['tok_per_sec']:.0f} tok/s | '{r['reply'][:30]}'")
        else:
            print(f"FAIL: {r['reply'][:50]}")

    ram_after = get_ram_used_mb()

    ok = [r for r in results if r["success"]]
    if ok:
        times = sorted(r["elapsed_s"] for r in ok)
        eval_times = sorted(r["eval_s"] for r in ok)
        tps = [r["tok_per_sec"] for r in ok if r["tok_per_sec"] > 0]
        p50 = times[len(times)//2]
        p95 = times[int(len(times)*0.95)] if len(times) > 1 else times[-1]
        eval_p50 = eval_times[len(eval_times)//2]
        avg_chars = sum(r["char_count"] for r in ok) / len(ok)
        avg_tps = sum(tps) / len(tps) if tps else 0
    else:
        p50 = p95 = eval_p50 = avg_chars = avg_tps = 0

    summary = {
        "model": model_name,
        "n_runs": n_runs,
        "success_rate": f"{len(ok)}/{n_runs}",
        "e2e_p50_s": round(p50, 2),
        "e2e_p95_s": round(p95, 2),
        "eval_p50_s": round(eval_p50, 2),
        "avg_tok_per_sec": round(avg_tps, 1),
        "avg_char_count": round(avg_chars, 1),
        "ram_before_mb": round(ram_before, 0),
        "ram_after_mb": round(ram_after, 0),
        "ram_delta_mb": round(ram_after - ram_before, 0),
    }

    print(f"\n--- Summary: {model_name} ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary, results


def get_ram_used_mb():
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    info[parts[0].rstrip(":")] = int(parts[1])
        return (info.get("MemTotal", 0) - info.get("MemAvailable", 0)) / 1024
    except:
        return 0


def main():
    models = ["qwen2.5:0.5b", "qwen2.5:1.5b"]
    all_summaries = []

    for model in models:
        summary, results = bench_model(model, n_runs=10)
        all_summaries.append(summary)
        out = f"/tmp/llm_bench_{model.replace(':', '_')}.json"
        with open(out, "w") as f:
            json.dump({"summary": summary, "results": results}, f, ensure_ascii=False, indent=2)
        print(f"  Saved: {out}")
        # Unload
        try:
            urllib.request.urlopen(urllib.request.Request(
                "http://localhost:11434/api/generate",
                data=json.dumps({"model": model, "keep_alive": 0}).encode(),
                headers={"Content-Type": "application/json"},
            ), timeout=10)
        except:
            pass
        time.sleep(5)

    print(f"\n{'='*60}")
    print("COMPARISON")
    print(f"{'='*60}")
    for s in all_summaries:
        print(f"  {s['model']:20s} | E2E P50={s['e2e_p50_s']:.1f}s P95={s['e2e_p95_s']:.1f}s | "
              f"{s['avg_tok_per_sec']:.0f} tok/s | RAM+={s['ram_delta_mb']:.0f}MB | {s['success_rate']}")


if __name__ == "__main__":
    main()
