#!/usr/bin/env bash
# corun_profile.sh — plan1 T1 co-run profiling orchestrator (NO-MOTION).
#
# Runs N sample intervals over --duration. Each interval captures a Jetson
# resource snapshot (RAM via `free -h`, GPU load via /sys/devices/gpu.0/load,
# max thermal-zone temp, `ps aux`) plus a `ros2 topic hz` window for each topic
# in scripts/corun_topics.txt that matches the chosen config. One raw,
# parseable line per metric is appended to runtime/profiling/2026-06-13-config<X>.log.
#
# This is a READ-ONLY attach: it does not start/stop/modify any demo stack.
# It emits ZERO motion commands. Parsing + PASS/WARNING/FAIL judgement lives in
# corun_profile_parse.py (stdlib-only).
#
# OOM brake: if RAM used stays > 6.5 GB sustained for >= 10s (sliding window over
# the recent samples, NOT a single instantaneous spike), emit "OOM-RISK ABORT"
# and break the sample loop. It does NOT kill the stack — Roy decides clean-up.
#
# Usage:
#   bash scripts/corun_profile.sh --config A|B|C --duration <seconds> --interval <seconds>
#
# Run via `bash` (no zsh assumptions).
set -euo pipefail

# ── Resolve script + repo paths ─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TOPICS_FILE="${SCRIPT_DIR}/corun_topics.txt"
OUT_DIR="${REPO_ROOT}/runtime/profiling"

# ── Defaults ────────────────────────────────────────────────────────────────
CONFIG=""
DURATION=300
INTERVAL=15
HZ_WINDOW=6           # seconds per `ros2 topic hz` sample window
RAM_FAIL_GB="6.5"     # OOM-risk threshold (jetson-status: critical > 6.5 GB of 7.4)
OOM_SUSTAIN_S=10      # sustained-over seconds required before ABORT

# ── Arg parsing ─────────────────────────────────────────────────────────────
usage() {
  echo "Usage: bash scripts/corun_profile.sh --config A|B|C --duration <s> --interval <s>" >&2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      CONFIG="${2:-}"; shift 2 ;;
    --duration)
      DURATION="${2:-}"; shift 2 ;;
    --interval)
      INTERVAL="${2:-}"; shift 2 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

case "${CONFIG}" in
  A|B|C) ;;
  *) echo "ERROR: --config must be one of A|B|C (got '${CONFIG}')" >&2; usage; exit 2 ;;
esac

if ! [ -f "${TOPICS_FILE}" ]; then
  echo "ERROR: topics file not found: ${TOPICS_FILE}" >&2; exit 1
fi

mkdir -p "${OUT_DIR}"
LOG_FILE="${OUT_DIR}/2026-06-13-config${CONFIG}.log"

# ── Helpers ─────────────────────────────────────────────────────────────────

# Emit a raw line to both the log file and stdout (key=value, pipe-separated).
emit() {
  local line="$1"
  echo "${line}" | tee -a "${LOG_FILE}"
}

# RAM used in GB (one decimal) parsed from `free` (KiB → GB).
read_ram_used_gb() {
  free | awk '/^Mem:/ { printf "%.1f", $3/1024/1024 }'
}

# GPU load percent: raw /10 (e.g. 910 -> 91.0). N/A if file missing.
read_gpu_load_pct() {
  if [ -r /sys/devices/gpu.0/load ]; then
    awk '{ printf "%.1f", $1/10 }' /sys/devices/gpu.0/load
  else
    echo "NA"
  fi
}

# Max temperature across all thermal zones in °C (raw /1000).
read_max_temp_c() {
  local max=""
  local f
  for f in /sys/devices/virtual/thermal/thermal_zone*/temp; do
    [ -r "${f}" ] || continue
    local raw
    raw="$(cat "${f}" 2>/dev/null || echo "")"
    [ -n "${raw}" ] || continue
    if [ -z "${max}" ] || [ "${raw}" -gt "${max}" ] 2>/dev/null; then
      max="${raw}"
    fi
  done
  if [ -z "${max}" ]; then
    echo "NA"
  else
    awk -v r="${max}" 'BEGIN { printf "%.1f", r/1000 }'
  fi
}

# Parse the mean Hz out of `ros2 topic hz` output (the "average rate:" line).
parse_hz_from_output() {
  # reads stdin; prints a numeric mean or "NA"
  awk '
    /average rate:/ { val=$3 }
    END { if (val == "") print "NA"; else print val }
  '
}

# Capture one topic Hz sample (bounded by timeout; never blocks the loop).
sample_topic_hz() {
  local topic="$1"
  local out
  out="$(timeout "${HZ_WINDOW}" ros2 topic hz "${topic}" 2>/dev/null || true)"
  printf '%s' "${out}" | parse_hz_from_output
}

# Snapshot the active ROS2 node list as a comma-joined single field.
snapshot_node_list() {
  local nodes
  nodes="$(ros2 node list 2>/dev/null | sort | tr '\n' ',' || true)"
  if [ -z "${nodes}" ]; then
    echo "NA"
  else
    echo "${nodes%,}"
  fi
}

# Float comparison: returns 0 (true) if $1 > $2.
gt() {
  awk -v a="$1" -v b="$2" 'BEGIN { exit !(a > b) }'
}

# ── Header ──────────────────────────────────────────────────────────────────
RUN_TS="$(date +%Y-%m-%dT%H:%M:%S)"
emit "RUN config=${CONFIG} start_ts=${RUN_TS} duration=${DURATION} interval=${INTERVAL} hz_window=${HZ_WINDOW}"

# Baseline node list (snapshot 0) — parser uses this to detect later crashes.
BASELINE_NODES="$(snapshot_node_list)"
emit "BASELINE_NODES config=${CONFIG} nodes=${BASELINE_NODES}"

# ── Sliding window for sustained-OOM detection ──────────────────────────────
# Track recent (timestamp,ram_gb) samples; ABORT only if every sample inside the
# last OOM_SUSTAIN_S seconds is above RAM_FAIL_GB. A lone spike that falls back
# below the threshold breaks the streak and does NOT abort.
declare -a OOM_TS=()
declare -a OOM_RAM=()

elapsed=0
sample_idx=0

while [ "${elapsed}" -lt "${DURATION}" ]; do
  NOW_EPOCH="$(date +%s)"
  NOW_TS="$(date +%H:%M:%S)"

  # --- Resource snapshot ---
  RAM_GB="$(read_ram_used_gb)"
  GPU_PCT="$(read_gpu_load_pct)"
  TEMP_C="$(read_max_temp_c)"
  emit "SAMPLE config=${CONFIG} idx=${sample_idx} ts=${NOW_TS} ram_gb=${RAM_GB} gpu_pct=${GPU_PCT} temp_c=${TEMP_C}"

  # --- ps aux snapshot (count of profiled model processes, for the raw record) ---
  PROC_COUNT="$(ps aux | grep -E '(realsense|face_identity|vision_perception|speech_processor|foxglove|object_perception|nav_capability|reactive_stop|sllidar|tts_node)' | grep -v grep | wc -l | tr -d ' ')"
  emit "PROC config=${CONFIG} idx=${sample_idx} proc_count=${PROC_COUNT}"

  # --- Node list snapshot ---
  NODE_LIST="$(snapshot_node_list)"
  emit "NODES config=${CONFIG} idx=${sample_idx} nodes=${NODE_LIST}"

  # --- Per-topic Hz (only topics whose config column contains this CONFIG) ---
  while IFS=',' read -r topic expected_hz configs || [ -n "${topic}" ]; do
    case "${topic}" in
      ''|'#'*) continue ;;
    esac
    case "${configs}" in
      *"${CONFIG}"*) ;;
      *) continue ;;
    esac
    HZ="$(sample_topic_hz "${topic}")"
    emit "HZ config=${CONFIG} idx=${sample_idx} topic=${topic} expected=${expected_hz} hz=${HZ}"
  done < "${TOPICS_FILE}"

  # --- Sustained-OOM sliding window ---
  OOM_TS+=("${NOW_EPOCH}")
  OOM_RAM+=("${RAM_GB}")
  # Drop entries older than OOM_SUSTAIN_S seconds.
  WINDOW_START=$(( NOW_EPOCH - OOM_SUSTAIN_S ))
  declare -a NEW_TS=()
  declare -a NEW_RAM=()
  i=0
  while [ "${i}" -lt "${#OOM_TS[@]}" ]; do
    if [ "${OOM_TS[$i]}" -ge "${WINDOW_START}" ]; then
      NEW_TS+=("${OOM_TS[$i]}")
      NEW_RAM+=("${OOM_RAM[$i]}")
    fi
    i=$(( i + 1 ))
  done
  OOM_TS=("${NEW_TS[@]}")
  OOM_RAM=("${NEW_RAM[@]}")

  # ABORT only if the window truly spans >= OOM_SUSTAIN_S AND every sample in it
  # is above RAM_FAIL_GB (so a single spike that fell back cannot trigger it).
  WINDOW_SPAN=$(( NOW_EPOCH - OOM_TS[0] ))
  if [ "${WINDOW_SPAN}" -ge "${OOM_SUSTAIN_S}" ] && [ "${#OOM_RAM[@]}" -ge 2 ]; then
    all_over=1
    j=0
    while [ "${j}" -lt "${#OOM_RAM[@]}" ]; do
      if ! gt "${OOM_RAM[$j]}" "${RAM_FAIL_GB}"; then
        all_over=0
        break
      fi
      j=$(( j + 1 ))
    done
    if [ "${all_over}" -eq 1 ]; then
      emit "OOM-RISK ABORT config=${CONFIG} idx=${sample_idx} ram_gb=${RAM_GB} sustained_s=${WINDOW_SPAN} note=stack-NOT-killed"
      break
    fi
  fi

  sample_idx=$(( sample_idx + 1 ))
  sleep "${INTERVAL}"
  elapsed=$(( elapsed + INTERVAL ))
done

emit "RUN_END config=${CONFIG} samples=${sample_idx} end_ts=$(date +%Y-%m-%dT%H:%M:%S)"
echo "Profiling log written to: ${LOG_FILE}"
