"""test_corun_profile_parse.py — plan1 T1 parser unit tests (stdlib-only, ROS-free).

Eight cases, all with inline fixtures; no hardware, no ROS, no heavy deps. Run:

    cd /home/roy422/newLife/elder_and_dog && \
        python3 -m pytest scripts/test_corun_profile_parse.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import corun_profile_parse as cpp  # noqa: E402


# ── 1. RAM from free block ──────────────────────────────────────────────────
def test_parse_ram_from_free_block():
    # raw `free` (KiB): total, used, free, shared, buff/cache, available
    free_text = (
        "              total        used        free      shared  buff/cache   available\n"
        "Mem:        7654321     5242880     1048576       12345      999999     2000000\n"
        "Swap:             0           0           0\n"
    )
    used_gb = cpp.parse_ram_used_gb_from_free(free_text)
    # 5242880 KiB / 1024 / 1024 = 5.0 GB
    assert used_gb == pytest.approx(5.0, abs=0.01)


# ── 2. Max temp across multiple thermal zones ───────────────────────────────
def test_parse_temp_max():
    thermal_text = (
        "thermal_zone0: 48000\n"
        "thermal_zone1: 66000\n"
        "thermal_zone2: 52000\n"
        "thermal_zone3: 61500\n"
    )
    assert cpp.parse_max_temp_c(thermal_text) == pytest.approx(66.0, abs=0.01)


# ── 3. GPU load 910 -> 91.0 ─────────────────────────────────────────────────
def test_parse_gpu_load():
    assert cpp.parse_gpu_load_pct("910\n") == pytest.approx(91.0, abs=0.001)
    assert cpp.parse_gpu_load_pct("0") == pytest.approx(0.0, abs=0.001)
    assert cpp.parse_gpu_load_pct("1000") == pytest.approx(100.0, abs=0.001)


# ── 4. RAM PASS/WARNING/FAIL bands ──────────────────────────────────────────
def test_passfail_ram_headroom():
    # 5.0 GB -> PASS (< 5.5)
    assert cpp.judge_ram(5.0) == cpp.PASS
    # 6.0 GB -> WARNING (5.5-6.5)
    assert cpp.judge_ram(6.0) == cpp.WARNING
    # 6.7 GB -> FAIL (> 6.5, OOM-risk)
    assert cpp.judge_ram(6.7) == cpp.FAIL
    # headroom: 7.4 - 6.7 = 0.7 GB < 0.8 -> FAIL
    assert cpp.judge_headroom(6.7) == cpp.FAIL
    # headroom: 7.4 - 5.0 = 2.4 GB >= 1.9 -> PASS
    assert cpp.judge_headroom(5.0) == cpp.PASS


# ── 5. OOM sustained-only (spike -> WARNING, sustained -> ABORT) ─────────────
def test_oom_abort_sustained_only():
    # A single 6.6 GB spike at t=30 that falls back -> WARNING, not ABORT.
    spike_series = [
        (0, 5.0), (15, 5.2), (30, 6.6), (45, 5.3), (60, 5.1),
    ]
    assert cpp.oom_verdict(spike_series) == "WARNING"

    # Sustained > 6.5 GB across >= 10s (three consecutive 5s samples) -> ABORT.
    sustained_series = [
        (0, 5.0), (5, 6.6), (10, 6.7), (15, 6.8), (20, 5.0),
    ]
    assert cpp.oom_verdict(sustained_series) == "ABORT"

    # All clear -> OK.
    clear_series = [(0, 5.0), (15, 5.2), (30, 5.1)]
    assert cpp.oom_verdict(clear_series) == "OK"


# ── 6. Topic Hz band ────────────────────────────────────────────────────────
def test_passfail_topic_hz_band():
    # /scan_rplidar expected ~10; 9.6 is within +-20% -> PASS
    assert cpp.judge_topic_hz(9.6, "~10") == cpp.PASS
    # 3 Hz against ~10 is > 40% off -> FAIL
    assert cpp.judge_topic_hz(3.0, "~10") == cpp.FAIL
    # 7.5 against 10 is 25% off -> WARNING band
    assert cpp.judge_topic_hz(7.5, "10") == cpp.WARNING
    # event-driven topic: presence -> PASS, absence -> FAIL
    assert cpp.judge_topic_hz(0.5, "evt") == cpp.PASS
    assert cpp.judge_topic_hz(None, "evt") == cpp.FAIL
    # zero measured on a rate topic -> FAIL
    assert cpp.judge_topic_hz(0.0, "10") == cpp.FAIL


# ── 7. Node crash detection ─────────────────────────────────────────────────
def test_passfail_node_crash():
    baseline = ["/brain_node", "/face_identity_node", "/object_perception_node",
                "/tts_node"]
    # all present -> PASS
    observed_ok = ["/brain_node", "/face_identity_node",
                   "/object_perception_node", "/tts_node", "/extra_node"]
    assert cpp.judge_node_crash(baseline, observed_ok) == cpp.PASS
    # object node missing -> FAIL
    observed_crash = ["/brain_node", "/face_identity_node", "/tts_node"]
    assert cpp.judge_node_crash(baseline, observed_crash) == cpp.FAIL


# ── 8. Config label required ─────────────────────────────────────────────────
def test_config_label_required():
    # main() must reject a missing/invalid config label.
    rc = cpp.main(["--config", "Z", "--log", "/nonexistent.log"])
    assert rc == 2  # invalid label rejected before touching the log

    # argparse enforces --config presence (SystemExit, not a clean return).
    with pytest.raises(SystemExit):
        cpp.main(["--log", "/nonexistent.log"])


# ── Bonus: end-to-end parse_log + build_report on a synthetic log ────────────
def test_parse_log_and_report_roundtrip(tmp_path):
    log = (
        "RUN config=A start_ts=2026-06-13T10:00:00 duration=30 interval=15 hz_window=6\n"
        "BASELINE_NODES config=A nodes=/brain_node,/face_identity_node,/tts_node\n"
        "SAMPLE config=A idx=0 ts=10:00:00 ram_gb=5.0 gpu_pct=42.0 temp_c=52.0\n"
        "PROC config=A idx=0 proc_count=8\n"
        "NODES config=A idx=0 nodes=/brain_node,/face_identity_node,/tts_node\n"
        "HZ config=A idx=0 topic=/state/perception/face expected=10 hz=9.8\n"
        "HZ config=A idx=0 topic=/tts expected=evt hz=NA\n"
        "SAMPLE config=A idx=1 ts=10:00:15 ram_gb=5.1 gpu_pct=44.0 temp_c=53.0\n"
        "NODES config=A idx=1 nodes=/brain_node,/face_identity_node,/tts_node\n"
        "HZ config=A idx=1 topic=/state/perception/face expected=10 hz=10.1\n"
        "HZ config=A idx=1 topic=/tts expected=evt hz=NA\n"
        "RUN_END config=A samples=2 end_ts=2026-06-13T10:00:30\n"
    )
    parsed = cpp.parse_log(log)
    assert parsed["config"] == "A"
    assert parsed["baseline_nodes"] == [
        "/brain_node", "/face_identity_node", "/tts_node"]
    assert len(parsed["samples"]) == 2

    report = cpp.build_report(parsed)
    # face Hz ~10 -> PASS; tts evt without a measurement -> FAIL by presence rule
    metrics = {m: v for (m, v, _) in report["rows"]}
    verdicts = {m: vd for (m, _, vd) in report["rows"]}
    assert verdicts["ram_used_gb"] == cpp.PASS
    assert verdicts["hz:/state/perception/face"] == cpp.PASS
    assert verdicts["hz:/tts"] == cpp.FAIL  # never observed in this fixture
    assert "node_crash" in metrics

    # CSV write works and is readable.
    csv_path = tmp_path / "out.csv"
    cpp.write_csv(report, str(csv_path))
    content = csv_path.read_text()
    assert "metric,value,verdict" in content
    assert "__overall__" in content
