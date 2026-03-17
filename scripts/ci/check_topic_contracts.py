#!/usr/bin/env python3
"""Topic contract checker — report-only, v1.

Statically scans node source files for create_publisher / create_subscription
calls and cross-references them against the v2.0 frozen topic list from
docs/architecture/interaction_contract.md §2.

Exit code is always 0 (report-only).  Warnings are printed to stderr.
"""

import os
import re
import sys

# ── Parse contract topics from interaction_contract.md §2 ────────────────

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONTRACT_MD = os.path.join(REPO_ROOT, "docs", "architecture", "interaction_contract.md")

# Matches table rows like: | `/state/perception/face` | State | 10 Hz | ... |
_CONTRACT_TABLE_RE = re.compile(r'^\|\s*`(/[^`]+)`\s*\|', re.MULTILINE)


def _parse_contract_topics():
    """Extract topic names from interaction_contract.md §2 table only.

    Stops scanning at '## 3.' to avoid picking up reference/example topics
    from later sections (QoS tables, ASR params, camera topics, etc.).
    """
    try:
        with open(CONTRACT_MD, "r", encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        print(f"WARNING: {CONTRACT_MD} not found, falling back to empty set", file=sys.stderr)
        return set()
    # Extract only §2 — everything between "## 2." and "## 3."
    m_start = re.search(r'^## 2\.', content, re.MULTILINE)
    m_end = re.search(r'^## 3\.', content, re.MULTILINE)
    if m_start is None:
        print("WARNING: §2 header not found in interaction_contract.md", file=sys.stderr)
        return set()
    section2 = content[m_start.start():m_end.start() if m_end else len(content)]
    topics = set()
    for m in _CONTRACT_TABLE_RE.finditer(section2):
        topics.add(m.group(1))
    if not topics:
        print("WARNING: no topics parsed from interaction_contract.md §2", file=sys.stderr)
    return topics


CONTRACT_TOPICS = _parse_contract_topics()

# Internal / experimental topics that are OK to exist in code but not in
# the frozen contract.  Extend this list as needed.
INTERNAL_TOPICS = {
    "/tts_audio_raw",
    "/intent",
    "/asr_result",
    "/state/tts_playing",
    "/state/interaction/tts_bridge",
    "/state/interaction/llm_bridge",
    "/state/interaction/asr",
    "/state/interaction/intent",
    "/speech/text_input",
    "/event/speech_activity",
    "/audio/speech_segment",
    # ROS2 infrastructure topics
    "/cmd_vel",
    "/robot_state",
    "/joint_states",
    "/odom",
    "/imu",
    "/pointcloud2",
    "/joy",
    "/scan",
    "/tf",
    "/tf_static",
    # Camera topics
    "/camera/image_raw",
    "/camera/camera/color/image_raw",
    "/camera/camera/aligned_depth_to_color/image_raw",
    # LiDAR topics
    "/point_cloud2",
    "/pointcloud/aggregated",
    "/pointcloud/downsampled",
    "/pointcloud/filtered",
    "/utlidar/cloud",
    "/utlidar/robot_pose",
    # Face debug/enroll topics
    "/face_identity/compare_image",
    "/face_identity/debug_image",
    "/face_depth/compare_image",
    "/face_depth/debug_image",
    "/face_enroll/debug_image",
    # Search logic
    "/patrol_command",
    "/patrol_status",
    # Test observer internal
    "/speech_test_observer/round_meta_req",
    "/speech_test_observer/round_meta_ack",
    "/speech_test_observer/round_done_ack",
    "/speech_test_observer/generate_report_req",
    "/speech_test_observer/generate_report_ack",
}

# This script's own path — exclude from scanning to avoid self-matching
THIS_SCRIPT = os.path.abspath(__file__)

# ── Helpers ───────────────────────────────────────────────────────────────

# Patterns to find topic strings in create_publisher / create_subscription
# Direct string literal: create_publisher(Type, "/topic", ...)
PUB_RE = re.compile(r'create_publisher\([^,]+,\s*["\'](/[^"\']+)["\']')
SUB_RE = re.compile(r'create_subscription\([^,]+,\s*["\'](/[^"\']+)["\']')
# ROS2 parameter default: declare_parameter("xxx_topic", "/topic")
PARAM_TOPIC_RE = re.compile(r'declare_parameter\(\s*["\'][^"\']*topic[^"\']*["\']\s*,\s*["\'](/[^"\']+)["\']')
# Generic topic string: any "/event/..." or "/state/..." or "/tts" or "/webrtc_req" literal
TOPIC_LITERAL_RE = re.compile(r'["\'](/(event|state|tts|webrtc_req)\b[^"\']*)["\']')


def find_node_files():
    """Find all Python source files in ROS2 packages (excluding build/install)."""
    results = []
    # Scan both package dirs and scripts/
    scan_dirs = [
        os.path.join(REPO_ROOT, "go2_robot_sdk", "go2_robot_sdk"),
        os.path.join(REPO_ROOT, "speech_processor", "speech_processor"),
        os.path.join(REPO_ROOT, "coco_detector", "coco_detector"),
        os.path.join(REPO_ROOT, "lidar_processor", "lidar_processor"),
        os.path.join(REPO_ROOT, "src", "search_logic", "search_logic"),
        os.path.join(REPO_ROOT, "scripts"),
    ]
    for scan_dir in scan_dirs:
        if not os.path.isdir(scan_dir):
            continue
        for dirpath, dirnames, filenames in os.walk(scan_dir):
            dirnames[:] = [
                d for d in dirnames
                if d not in ("build", "install", "log", ".git", "node_modules",
                             "test", "__pycache__")
            ]
            for f in filenames:
                if f.endswith(".py"):
                    full = os.path.join(dirpath, f)
                    if os.path.abspath(full) != THIS_SCRIPT:
                        results.append(full)
    return results


def extract_topics(filepath):
    """Extract published and subscribed topic names from a Python file."""
    pubs = set()
    subs = set()
    all_topics = set()  # topics found via any pattern
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
    except (OSError, UnicodeDecodeError):
        return pubs, subs, all_topics

    for m in PUB_RE.finditer(content):
        pubs.add(m.group(1))
    for m in SUB_RE.finditer(content):
        subs.add(m.group(1))
    # Also pick up topics from declare_parameter defaults and literals
    for m in PARAM_TOPIC_RE.finditer(content):
        all_topics.add(m.group(1))
    for m in TOPIC_LITERAL_RE.finditer(content):
        all_topics.add(m.group(1))
    # Merge: if a topic appears in param defaults, count as both pub and sub candidate
    all_topics.update(pubs)
    all_topics.update(subs)
    return pubs, subs, all_topics


def main():
    node_files = find_node_files()
    all_pubs = {}       # topic -> list of files (from create_publisher)
    all_subs = {}       # topic -> list of files (from create_subscription)
    all_mentioned = {}  # topic -> list of files (from any pattern)

    for fp in sorted(node_files):
        pubs, subs, mentioned = extract_topics(fp)
        rel = os.path.relpath(fp, REPO_ROOT)
        for t in pubs:
            all_pubs.setdefault(t, []).append(rel)
        for t in subs:
            all_subs.setdefault(t, []).append(rel)
        for t in mentioned:
            all_mentioned.setdefault(t, []).append(rel)

    all_code_topics = set(all_mentioned.keys())
    warnings = 0

    # ── Check 1: contract topics present in code ─────────────────────
    print("=== Topic Contract Check (report-only) ===\n")
    print(f"Contract topics: {len(CONTRACT_TOPICS)}")
    print(f"Code topics found: {len(all_code_topics)}")
    print()

    for topic in sorted(CONTRACT_TOPICS):
        found = topic in all_mentioned
        if found:
            files = all_mentioned[topic]
            print(f"  [OK]   {topic}  files={files}")
        else:
            print(f"  [WARN] {topic}  — not found in code", file=sys.stderr)
            warnings += 1

    print()

    # ── Check 2: code topics not in contract or whitelist ────────────
    ghost_topics = all_code_topics - CONTRACT_TOPICS - INTERNAL_TOPICS
    if ghost_topics:
        print("Ghost topics (in code but not in contract or whitelist):")
        for t in sorted(ghost_topics):
            files = all_mentioned.get(t, [])
            print(f"  [INFO] {t}  files={files}", file=sys.stderr)
            warnings += 1
    else:
        print("No ghost topics found.")

    print()
    print(f"Total warnings: {warnings}")
    print("(report-only — exit 0 regardless)")

    # Always exit 0 — report-only mode
    sys.exit(0)


if __name__ == "__main__":
    main()
