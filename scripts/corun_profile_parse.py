#!/usr/bin/env python3
"""corun_profile_parse.py — plan1 T1 co-run profiling parser (stdlib-only).

Reads a raw profiling log produced by corun_profile.sh, parses the
RAM / temperature / GPU-load / per-topic-Hz / node-list time series, applies the
plan1 §9.2 PASS / WARNING / FAIL thresholds, writes a per-metric CSV
(runtime/profiling/2026-06-13-config<X>.csv) and prints a per-metric verdict plus
the overall config stable / unstable judgement to stdout.

STDLIB ONLY. Importing supervision / cv2 / torch / numpy is forbidden here — this
keeps the parser CI-safe and off the Jetson runtime (master B-4 iron rule).

The OOM-risk abort decision is a *sustained* check, mirroring corun_profile.sh:
a single RAM spike above the threshold yields WARNING; only RAM used staying
above the OOM threshold for >= the sustained window (default 10s) is an ABORT.

NO-MOTION: this parser reads /state/nav/* topic Hz only; it never emits any
motion command.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys

# ── §9.2 thresholds (jetson-status budget) ──────────────────────────────────
RAM_PASS_GB = 5.5          # used < 5.5 GB -> PASS
RAM_WARN_GB = 6.5          # 5.5-6.5 GB -> WARNING; > 6.5 GB -> FAIL (OOM-risk)
RAM_TOTAL_GB = 7.4         # for headroom derivation
HEADROOM_PASS_GB = 1.9     # headroom >= 1.9 GB -> PASS
HEADROOM_FAIL_GB = 0.8     # headroom < 0.8 GB -> FAIL (0.9-1.9 -> WARNING)
GPU_PASS_PCT = 95.0        # < 95% PASS; 95-99% WARNING; 100% FAIL (throttle)
GPU_FAIL_PCT = 100.0
TEMP_PASS_C = 65.0         # < 65 PASS; 65-80 WARNING; > 80 FAIL
TEMP_FAIL_C = 80.0
HZ_PASS_BAND = 0.20        # within +-20% of expected -> PASS
HZ_WARN_BAND = 0.40        # +-20-40% -> WARNING; > 40% off or 0 -> FAIL

# OOM-risk abort: sustained, not instantaneous.
OOM_THRESHOLD_GB = 6.5
OOM_SUSTAIN_S = 10

PASS = "PASS"
WARNING = "WARNING"
FAIL = "FAIL"

# ── Log line patterns ───────────────────────────────────────────────────────
_RE_KV = re.compile(r"(\w+)=(\S+)")


def _parse_kv(line: str) -> dict:
    """Parse key=value tokens out of a raw log line into a dict."""
    return dict(_RE_KV.findall(line))


def parse_ram_used_gb_from_free(free_text: str) -> float:
    """Parse used RAM (GB) from a `free` block.

    Accepts either `free` (KiB) or `free -h` (human, e.g. '5.0Gi') output. The
    'Mem:' row's *used* column (3rd numeric/size field) is returned in GB.
    """
    for raw in free_text.splitlines():
        line = raw.strip()
        if not line.startswith("Mem:"):
            continue
        fields = line.split()[1:]  # drop the 'Mem:' label
        if len(fields) < 2:
            continue
        used = fields[1]  # total, used, free, ...
        return _size_to_gb(used)
    raise ValueError("no 'Mem:' row found in free block")


def _size_to_gb(token: str) -> float:
    """Convert a `free`/`free -h` size token to GB.

    Plain integers are treated as KiB (raw `free`); human suffixes
    (Ki/Mi/Gi/Ti, with or without trailing 'B') are scaled accordingly.
    """
    t = token.strip()
    m = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([KMGTkmgt]i?)?B?$", t)
    if not m:
        raise ValueError(f"unparseable size token: {token!r}")
    value = float(m.group(1))
    unit = (m.group(2) or "").lower().rstrip("i")
    if unit == "":
        # bare number from raw `free` -> KiB
        return value / 1024.0 / 1024.0
    if unit == "k":
        return value / 1024.0 / 1024.0
    if unit == "m":
        return value / 1024.0
    if unit == "g":
        return value
    if unit == "t":
        return value * 1024.0
    raise ValueError(f"unknown size unit in token: {token!r}")


def parse_max_temp_c(thermal_text: str) -> float:
    """Parse the max temperature (°C) across thermal_zone*/temp values.

    Accepts a block of raw milli-°C integers (one per line, as cat'd from
    /sys/.../thermal_zone*/temp). Returns the max in °C.
    """
    temps = []
    for raw in thermal_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        # tolerate "thermal_zoneN: 52000" or bare "52000"
        m = re.search(r"(\d+)\s*$", line)
        if not m:
            continue
        temps.append(int(m.group(1)) / 1000.0)
    if not temps:
        raise ValueError("no temperatures found in thermal block")
    return max(temps)


def parse_gpu_load_pct(load_text: str) -> float:
    """Parse GPU load percent from /sys/devices/gpu.0/load (raw / 10).

    e.g. '910' -> 91.0.
    """
    t = load_text.strip()
    if not t:
        raise ValueError("empty GPU load text")
    raw = int(t.split()[0])
    return raw / 10.0


# ── §9.2 per-metric band judgements ─────────────────────────────────────────
def judge_ram(used_gb: float) -> str:
    if used_gb < RAM_PASS_GB:
        return PASS
    if used_gb <= RAM_WARN_GB:
        return WARNING
    return FAIL


def judge_headroom(used_gb: float) -> str:
    headroom = RAM_TOTAL_GB - used_gb
    if headroom >= HEADROOM_PASS_GB:
        return PASS
    if headroom >= HEADROOM_FAIL_GB:
        return WARNING
    return FAIL


def judge_gpu(load_pct: float) -> str:
    if load_pct < GPU_PASS_PCT:
        return PASS
    if load_pct < GPU_FAIL_PCT:
        return WARNING
    return FAIL


def judge_temp(temp_c: float) -> str:
    if temp_c < TEMP_PASS_C:
        return PASS
    if temp_c <= TEMP_FAIL_C:
        return WARNING
    return FAIL


def judge_topic_hz(measured_hz, expected_hz) -> str:
    """Judge a measured topic Hz against the expected centre value (§9.2 band).

    `expected_hz` may be a float, an "~N" hint, "evt", or None. Event-driven /
    on-demand topics ("evt", "evt"/"on-demand") are not Hz-graded -> PASS when a
    measurement exists, FAIL only when nothing was seen at all.
    """
    if _is_event_topic(expected_hz):
        # event/on-demand: presence is the signal, not a rate band.
        if measured_hz is None:
            return FAIL
        return PASS
    exp = _coerce_hz(expected_hz)
    if exp is None:
        return WARNING  # expected unparseable -> can't grade strictly
    if measured_hz is None or measured_hz == 0:
        return FAIL
    deviation = abs(measured_hz - exp) / exp
    if deviation <= HZ_PASS_BAND:
        return PASS
    if deviation <= HZ_WARN_BAND:
        return WARNING
    return FAIL


def _is_event_topic(expected) -> bool:
    if expected is None:
        return False
    s = str(expected).strip().lower()
    return s in ("evt", "event", "on-demand", "ondemand")


def _coerce_hz(expected):
    """Coerce an expected-Hz token ('10', '~10', float) to a float, else None."""
    if expected is None:
        return None
    if isinstance(expected, (int, float)):
        return float(expected)
    s = str(expected).strip().lstrip("~")
    try:
        return float(s)
    except ValueError:
        return None


def judge_node_crash(baseline_nodes, observed_nodes) -> str:
    """FAIL if any baseline node is missing from the observed set."""
    missing = set(baseline_nodes) - set(observed_nodes)
    if missing:
        return FAIL
    return PASS


def oom_verdict(samples) -> str:
    """Classify RAM time series for OOM-risk.

    `samples` is a list of (epoch_seconds, ram_gb). Returns:
      - "ABORT"   if RAM stayed > OOM_THRESHOLD_GB sustained for >= OOM_SUSTAIN_S
      - "WARNING" if it touched > OOM_THRESHOLD_GB at least once (a spike) but
                  never sustained
      - "OK"      otherwise

    A lone spike that falls back below the threshold is WARNING, not ABORT.
    """
    over = [(t, r) for (t, r) in samples if r > OOM_THRESHOLD_GB]
    if not over:
        return "OK"
    # Find the longest run of consecutive over-threshold samples and check that
    # the run spans >= OOM_SUSTAIN_S seconds.
    longest_span = 0
    run_start_t = None
    prev_idx = None
    for idx, (t, r) in enumerate(samples):
        if r > OOM_THRESHOLD_GB:
            if run_start_t is None:
                run_start_t = t
            span = t - run_start_t
            if span > longest_span:
                longest_span = span
            prev_idx = idx
        else:
            run_start_t = None
            prev_idx = idx
    _ = prev_idx  # silence linters; index retained for clarity
    if longest_span >= OOM_SUSTAIN_S:
        return "ABORT"
    return "WARNING"


# ── Log parsing ─────────────────────────────────────────────────────────────
def parse_log(text: str) -> dict:
    """Parse a corun_profile.sh log into structured series.

    Returns a dict with keys:
      config, baseline_nodes (list), samples (list of dicts), oom_abort_seen.
    Each sample dict: idx, ram_gb, gpu_pct, temp_c, nodes (list), hz (dict).
    """
    config = None
    baseline_nodes = []
    samples_by_idx = {}
    oom_abort_seen = False

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        kind = line.split(None, 1)[0]
        kv = _parse_kv(line)

        if kind == "RUN":
            config = kv.get("config", config)
        elif kind == "BASELINE_NODES":
            baseline_nodes = _split_nodes(kv.get("nodes", ""))
            config = kv.get("config", config)
        elif kind == "SAMPLE":
            idx = int(kv["idx"])
            s = samples_by_idx.setdefault(idx, _blank_sample(idx))
            s["ram_gb"] = _opt_float(kv.get("ram_gb"))
            s["gpu_pct"] = _opt_float(kv.get("gpu_pct"))
            s["temp_c"] = _opt_float(kv.get("temp_c"))
            s["ts"] = kv.get("ts")
        elif kind == "NODES":
            idx = int(kv["idx"])
            s = samples_by_idx.setdefault(idx, _blank_sample(idx))
            s["nodes"] = _split_nodes(kv.get("nodes", ""))
        elif kind == "HZ":
            idx = int(kv["idx"])
            s = samples_by_idx.setdefault(idx, _blank_sample(idx))
            topic = kv.get("topic", "")
            s["hz"][topic] = {
                "expected": kv.get("expected"),
                "measured": _opt_float(kv.get("hz")),
            }
        elif kind == "OOM-RISK":
            # line form: "OOM-RISK ABORT config=... idx=..."
            oom_abort_seen = True

    samples = [samples_by_idx[i] for i in sorted(samples_by_idx)]
    return {
        "config": config,
        "baseline_nodes": baseline_nodes,
        "samples": samples,
        "oom_abort_seen": oom_abort_seen,
    }


def _blank_sample(idx: int) -> dict:
    return {
        "idx": idx,
        "ts": None,
        "ram_gb": None,
        "gpu_pct": None,
        "temp_c": None,
        "nodes": [],
        "hz": {},
    }


def _split_nodes(s: str):
    if not s or s == "NA":
        return []
    return [n for n in s.split(",") if n]


def _opt_float(token):
    if token is None or token == "NA":
        return None
    try:
        return float(token)
    except (TypeError, ValueError):
        return None


# ── Aggregation + verdict ───────────────────────────────────────────────────
def _worst(verdicts) -> str:
    """Reduce a list of verdicts to the worst (FAIL > WARNING > PASS)."""
    order = {PASS: 0, WARNING: 1, FAIL: 2}
    worst = PASS
    for v in verdicts:
        if order.get(v, 0) > order[worst]:
            worst = v
    return worst


def build_report(parsed: dict) -> dict:
    """Turn parsed series into a per-metric verdict report + overall stable flag."""
    samples = parsed["samples"]
    baseline = parsed["baseline_nodes"]
    rows = []

    # RAM used: judge the sustained peak (max over the run).
    ram_vals = [s["ram_gb"] for s in samples if s["ram_gb"] is not None]
    if ram_vals:
        peak_ram = max(ram_vals)
        rows.append(("ram_used_gb", round(peak_ram, 2), judge_ram(peak_ram)))
        rows.append(("ram_headroom_gb", round(RAM_TOTAL_GB - peak_ram, 2),
                     judge_headroom(peak_ram)))

    # GPU: judge the peak load.
    gpu_vals = [s["gpu_pct"] for s in samples if s["gpu_pct"] is not None]
    if gpu_vals:
        peak_gpu = max(gpu_vals)
        rows.append(("gpu_load_pct", round(peak_gpu, 1), judge_gpu(peak_gpu)))

    # Temp: judge the peak temperature.
    temp_vals = [s["temp_c"] for s in samples if s["temp_c"] is not None]
    if temp_vals:
        peak_temp = max(temp_vals)
        rows.append(("temp_max_c", round(peak_temp, 1), judge_temp(peak_temp)))

    # Per-topic Hz: judge the mean measured Hz against expected.
    topic_means = _topic_means(samples)
    for topic in sorted(topic_means):
        info = topic_means[topic]
        verdict = judge_topic_hz(info["mean"], info["expected"])
        value = "evt" if _is_event_topic(info["expected"]) else (
            round(info["mean"], 2) if info["mean"] is not None else "none")
        rows.append((f"hz:{topic}", value, verdict))

    # Node crash: any baseline node missing from any later sample -> FAIL.
    crash_verdict = PASS
    if baseline:
        for s in samples:
            if not s["nodes"]:
                continue
            if judge_node_crash(baseline, s["nodes"]) == FAIL:
                crash_verdict = FAIL
                break
    rows.append(("node_crash", "ok" if crash_verdict == PASS else "missing-node",
                 crash_verdict))

    # OOM verdict (sustained-only). ABORT -> FAIL on the metric line.
    ram_series = [(i, s["ram_gb"]) for i, s in enumerate(samples)
                  if s["ram_gb"] is not None]
    # Use epoch-like spacing of OOM_SUSTAIN_S-friendly seconds if timestamps
    # are not available; here index*assumed-interval is not reliable, so prefer
    # explicit (epoch, ram) when provided by oom_verdict callers in tests.
    oom = oom_verdict([(t, r) for t, r in ram_series])
    if parsed.get("oom_abort_seen"):
        oom = "ABORT"
    oom_metric_verdict = FAIL if oom == "ABORT" else (
        WARNING if oom == "WARNING" else PASS)
    rows.append(("oom_risk", oom, oom_metric_verdict))

    overall = _worst([v for (_, _, v) in rows])
    stable = overall != FAIL
    return {
        "config": parsed.get("config"),
        "rows": rows,
        "overall": overall,
        "stable": stable,
    }


def _topic_means(samples) -> dict:
    """Average each topic's measured Hz across samples, keeping the expected."""
    acc = {}
    for s in samples:
        for topic, info in s["hz"].items():
            entry = acc.setdefault(topic, {"vals": [], "expected": info.get("expected")})
            if info.get("expected") is not None:
                entry["expected"] = info.get("expected")
            m = info.get("measured")
            if m is not None:
                entry["vals"].append(m)
    out = {}
    for topic, entry in acc.items():
        vals = entry["vals"]
        out[topic] = {
            "mean": (sum(vals) / len(vals)) if vals else None,
            "expected": entry["expected"],
        }
    return out


# ── CSV + stdout ────────────────────────────────────────────────────────────
def write_csv(report: dict, csv_path: str) -> None:
    os.makedirs(os.path.dirname(csv_path) or ".", exist_ok=True)
    with open(csv_path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value", "verdict"])
        for metric, value, verdict in report["rows"]:
            writer.writerow([metric, value, verdict])
        writer.writerow(["__overall__", report["overall"],
                         "stable" if report["stable"] else "unstable"])


def print_report(report: dict) -> None:
    print(f"=== Co-run profiling verdict: config {report['config']} ===")
    for metric, value, verdict in report["rows"]:
        print(f"  [{verdict:7s}] {metric:24s} = {value}")
    state = "stable" if report["stable"] else "unstable"
    print(f"--- Overall: {report['overall']} -> config {report['config']} is {state} ---")


# ── CLI ─────────────────────────────────────────────────────────────────────
def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Parse a corun_profile.sh log and apply §9.2 thresholds.")
    parser.add_argument("--config", required=True,
                        help="Config label (A|B|C); required to avoid mixing results.")
    parser.add_argument("--log", help="Path to the raw profiling log "
                        "(default: runtime/profiling/2026-06-13-config<X>.log).")
    parser.add_argument("--csv", help="Output CSV path "
                        "(default: runtime/profiling/2026-06-13-config<X>.csv).")
    args = parser.parse_args(argv)

    config = args.config.strip().upper()
    if config not in ("A", "B", "C"):
        print(f"ERROR: --config must be one of A|B|C (got {args.config!r})",
              file=sys.stderr)
        return 2

    log_path = args.log or f"runtime/profiling/2026-06-13-config{config}.log"
    csv_path = args.csv or f"runtime/profiling/2026-06-13-config{config}.csv"

    if not os.path.isfile(log_path):
        print(f"ERROR: log file not found: {log_path}", file=sys.stderr)
        return 1

    with open(log_path, "r") as fh:
        text = fh.read()

    parsed = parse_log(text)
    parsed["config"] = parsed.get("config") or config
    report = build_report(parsed)
    report["config"] = config  # CLI label is authoritative
    write_csv(report, csv_path)
    print_report(report)
    print(f"CSV written to: {csv_path}")
    return 0 if report["stable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
