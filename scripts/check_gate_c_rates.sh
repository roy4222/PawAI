#!/usr/bin/env zsh

set -euo pipefail

if [ -z "${ZSH_VERSION:-}" ]; then
  exec /usr/bin/env zsh "$0" "$@"
fi

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

WARMUP_SEC="${1:-5}"
MEASURE_SEC="${2:-10}"

measure_rate_best_effort() {
  local topic="$1"
  local duration="$2"
  local sample_file

  sample_file=$(mktemp)
  timeout "${duration}" zsh "$SCRIPT_DIR/ros2w.sh" topic echo "$topic" --qos-profile sensor_data --field header.stamp > "$sample_file" 2>/dev/null || true

  python3 - "$sample_file" "$duration" "$topic" <<'PY'
import sys

sample_file, duration_str, topic = sys.argv[1], sys.argv[2], sys.argv[3]
duration = float(duration_str)
count = 0

with open(sample_file, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip().startswith("sec:"):
            count += 1

if count == 0:
    print(f"[WARN] {topic}: no samples in {duration:.1f}s")
else:
    print(f"[INFO] {topic}: samples={count}, approx_rate={count / duration:.2f} Hz")
PY

  rm -f "$sample_file"
}

echo "[Gate C rate check] warmup=${WARMUP_SEC}s measure=${MEASURE_SEC}s"
echo "[1/4] Wait for first /point_cloud2 message"
timeout "$((WARMUP_SEC + 10))" zsh "$SCRIPT_DIR/ros2w.sh" topic echo /point_cloud2 --qos-profile sensor_data --once > /dev/null

echo "[2/4] Measure /point_cloud2"
measure_rate_best_effort /point_cloud2 "${MEASURE_SEC}"

echo "[3/4] Wait for first /scan message"
timeout "$((WARMUP_SEC + 10))" zsh "$SCRIPT_DIR/ros2w.sh" topic echo /scan --qos-profile sensor_data --once > /dev/null

echo "[4/4] Measure /scan"
measure_rate_best_effort /scan "${MEASURE_SEC}"
