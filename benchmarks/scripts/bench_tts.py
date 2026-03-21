#!/usr/bin/env python3
"""Benchmark TTS: Piper vs edge-tts on Jetson."""
import json
import os
import subprocess
import time
import sys

TEXTS = [
    "你好呀！",
    "我叫PawAI，你的助手。",
    "好的，馬上過去。",
    "我在這裡等你哦。",
    "偵測到跌倒！請注意安全！",
    "現在是六點整。",
    "我很好，謝謝！",
    "不客氣，有什麼需要嗎？",
    "今天天氣不錯呢。",
    "再見，祝你有美好的一天！",
]

PIPER_MODEL = "/home/jetson/models/piper/zh_CN-huayan-medium.onnx"
OUT_DIR = "/tmp/tts_bench"


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


def bench_piper(n_runs=10):
    print(f"\n{'='*60}")
    print(f"Benchmarking: Piper huayan-medium ({n_runs} runs)")
    print(f"{'='*60}")

    os.makedirs(OUT_DIR, exist_ok=True)
    ram_before = get_ram_used_mb()
    results = []

    for i, text in enumerate(TEXTS[:n_runs]):
        out_wav = f"{OUT_DIR}/piper_{i}.wav"
        print(f"  [{i+1}/{n_runs}] '{text}' ... ", end="", flush=True)

        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                [os.path.expanduser("~/.local/bin/piper"), "--model", PIPER_MODEL, "--output_file", out_wav],
                input=text, capture_output=True, text=True, timeout=30,
            )
            elapsed = time.perf_counter() - t0
            wav_exists = os.path.exists(out_wav)
            wav_size = os.path.getsize(out_wav) if wav_exists else 0

            results.append({
                "text": text, "elapsed_s": round(elapsed, 2),
                "success": r.returncode == 0 and wav_exists and wav_size > 100,
                "wav_size_kb": round(wav_size / 1024, 1),
            })
            print(f"{elapsed:.2f}s | {wav_size/1024:.0f}KB")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results.append({"text": text, "elapsed_s": round(elapsed, 2),
                            "success": False, "wav_size_kb": 0})
            print(f"FAIL: {e}")

    ram_after = get_ram_used_mb()
    ok = [r for r in results if r["success"]]
    times = sorted(r["elapsed_s"] for r in ok) if ok else [0]
    p50 = times[len(times)//2]
    p95 = times[int(len(times)*0.95)] if len(times) > 1 else times[-1]

    summary = {
        "model": "piper_huayan_medium",
        "success_rate": f"{len(ok)}/{n_runs}",
        "p50_s": round(p50, 2), "p95_s": round(p95, 2),
        "ram_delta_mb": round(ram_after - ram_before, 0),
    }
    print(f"\n--- Piper Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary, results


def bench_edge_tts(n_runs=10):
    print(f"\n{'='*60}")
    print(f"Benchmarking: edge-tts (cloud, Microsoft Neural) ({n_runs} runs)")
    print(f"{'='*60}")

    # Check edge-tts is installed (do NOT auto-install during benchmark)
    edge_tts_path = os.path.expanduser("~/.local/bin/edge-tts")
    if not os.path.exists(edge_tts_path):
        print("  ERROR: edge-tts not found. Install first: uv pip install edge-tts")
        return {"model": "edge_tts_zh_TW", "success_rate": "0/0",
                "p50_s": 0, "p95_s": 0, "ram_delta_mb": 0}, []

    os.makedirs(OUT_DIR, exist_ok=True)
    ram_before = get_ram_used_mb()
    results = []

    for i, text in enumerate(TEXTS[:n_runs]):
        out_mp3 = f"{OUT_DIR}/edge_{i}.mp3"
        print(f"  [{i+1}/{n_runs}] '{text}' ... ", end="", flush=True)

        t0 = time.perf_counter()
        try:
            r = subprocess.run(
                [os.path.expanduser("~/.local/bin/edge-tts"), "--voice", "zh-TW-HsiaoChenNeural",
                 "--text", text, "--write-media", out_mp3],
                capture_output=True, text=True, timeout=30,
            )
            elapsed = time.perf_counter() - t0
            file_exists = os.path.exists(out_mp3)
            file_size = os.path.getsize(out_mp3) if file_exists else 0

            results.append({
                "text": text, "elapsed_s": round(elapsed, 2),
                "success": r.returncode == 0 and file_exists and file_size > 100,
                "file_size_kb": round(file_size / 1024, 1),
            })
            print(f"{elapsed:.2f}s | {file_size/1024:.0f}KB")
        except Exception as e:
            elapsed = time.perf_counter() - t0
            results.append({"text": text, "elapsed_s": round(elapsed, 2),
                            "success": False, "file_size_kb": 0})
            print(f"FAIL: {e}")

    ram_after = get_ram_used_mb()
    ok = [r for r in results if r["success"]]
    times = sorted(r["elapsed_s"] for r in ok) if ok else [0]
    p50 = times[len(times)//2]
    p95 = times[int(len(times)*0.95)] if len(times) > 1 else times[-1]

    summary = {
        "model": "edge_tts_zh_TW",
        "success_rate": f"{len(ok)}/{n_runs}",
        "p50_s": round(p50, 2), "p95_s": round(p95, 2),
        "ram_delta_mb": round(ram_after - ram_before, 0),
    }
    print(f"\n--- edge-tts Summary ---")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return summary, results


def main():
    all_summaries = []

    # Piper
    s1, r1 = bench_piper(10)
    all_summaries.append(s1)
    with open(f"{OUT_DIR}/piper_results.json", "w") as f:
        json.dump({"summary": s1, "results": r1}, f, ensure_ascii=False, indent=2)

    time.sleep(3)

    # edge-tts
    s2, r2 = bench_edge_tts(10)
    all_summaries.append(s2)
    with open(f"{OUT_DIR}/edge_tts_results.json", "w") as f:
        json.dump({"summary": s2, "results": r2}, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print("TTS COMPARISON")
    print(f"{'='*60}")
    for s in all_summaries:
        print(f"  {s['model']:25s} | P50={s['p50_s']:.2f}s P95={s['p95_s']:.2f}s | "
              f"RAM+={s['ram_delta_mb']:.0f}MB | {s['success_rate']}")


if __name__ == "__main__":
    main()
