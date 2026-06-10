#!/usr/bin/env bash
# scripts/under_load_probe.sh — 全系統 under-load 量測（在 Jetson 上跑）
#
# 不負責啟動任何 stack。先把要量的組合自己起好（例如 nav stack + full demo），
# 再跑本腳本量 N 秒：RAM / CPU / GPU(tegrastats) / 溫度 / key topic Hz /
# Studio gateway HTTP 延遲 / dmesg OOM。
#
# 用法:
#   bash scripts/under_load_probe.sh                 # 預設 60s
#   bash scripts/under_load_probe.sh 120             # 指定秒數
#   TOPICS="/scan_rplidar /odom" bash scripts/under_load_probe.sh   # 自訂 topic 清單
#
# 結果落地: ~/elder_and_dog/test_results/under_load/<timestamp>/
#   summary.txt（人讀摘要 + PASS/WARN 判讀）、tegrastats.log、topic_hz/*.log
set -uo pipefail

DURATION="${1:-60}"
GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
REPO="${REPO:-$HOME/elder_and_dog}"
OUT_DIR="$REPO/test_results/under_load/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$OUT_DIR/topic_hz"

# 預設 topic 清單：vision + nav + driver 全開時的關鍵流
DEFAULT_TOPICS=(
  /camera/camera/color/image_raw
  /face_identity/debug_image
  /perception/object/debug_image
  /vision_perception/status_image
  /scan_rplidar
  /odom
  /cmd_vel
)
if [ -n "${TOPICS:-}" ]; then
  read -r -a TOPIC_LIST <<< "$TOPICS"
else
  TOPIC_LIST=("${DEFAULT_TOPICS[@]}")
fi

source /opt/ros/humble/setup.bash 2>/dev/null || source /opt/ros/humble/setup.zsh
source "$REPO/install/setup.bash" 2>/dev/null || true

echo "================ UNDER-LOAD PROBE ================"
echo "Duration: ${DURATION}s | Output: $OUT_DIR"
echo "Topics:   ${TOPIC_LIST[*]}"
echo "=================================================="

# 0) baseline: dmesg OOM 計數（結束後比對）
OOM_BEFORE=$(dmesg 2>/dev/null | grep -ciE "out of memory|oom-killer|killed process" || true)
OOM_BEFORE=${OOM_BEFORE:-0}

# 1) tegrastats 全程背景收（含 GPU GR3D / RAM / 溫度 / 功耗）
TEGRA_PID=""
if command -v tegrastats >/dev/null 2>&1; then
  tegrastats --interval 1000 > "$OUT_DIR/tegrastats.log" 2>/dev/null &
  TEGRA_PID=$!
fi

# 2) 每個 topic 各開一個 ros2 topic hz 背景收整段（--window 取整段平均）
HZ_PIDS=()
for TOPIC in "${TOPIC_LIST[@]}"; do
  SAFE_NAME=$(echo "$TOPIC" | tr '/' '_')
  timeout "$((DURATION + 5))" ros2 topic hz "$TOPIC" --window 1000 \
    > "$OUT_DIR/topic_hz/${SAFE_NAME}.log" 2>&1 &
  HZ_PIDS+=($!)
done

# 3) 主迴圈：每 5s 收 RAM/CPU/temp + gateway HTTP 延遲
INTERVAL=5
PEAK_RAM_USED=0
MIN_RAM_AVAIL=999999
PEAK_TEMP=0
GW_SAMPLES=()
for (( t=0; t<DURATION; t+=INTERVAL )); do
  RAM_USED=$(free -m | awk '/Mem:/{print $3}')
  RAM_AVAIL=$(free -m | awk '/Mem:/{print $7}')
  CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
  MAX_T=0
  for tz in /sys/devices/virtual/thermal/thermal_zone*/temp; do
    [ -f "$tz" ] || continue
    T=$(( $(cat "$tz") / 1000 ))
    [ "$T" -gt "$MAX_T" ] && MAX_T=$T
  done
  GW_MS="N/A"
  if curl -s -o /dev/null --max-time 2 "$GATEWAY_URL/health"; then
    GW_MS=$(curl -s -o /dev/null -w "%{time_total}" --max-time 2 "$GATEWAY_URL/health" | awk '{printf "%.0f", $1*1000}')
    GW_SAMPLES+=("$GW_MS")
  fi
  echo "t=${t}s RAM used=${RAM_USED}MB avail=${RAM_AVAIL}MB CPU=${CPU}% temp=${MAX_T}C gateway=${GW_MS}ms"
  [ "$RAM_USED" -gt "$PEAK_RAM_USED" ] && PEAK_RAM_USED=$RAM_USED
  [ "$RAM_AVAIL" -lt "$MIN_RAM_AVAIL" ] && MIN_RAM_AVAIL=$RAM_AVAIL
  [ "$MAX_T" -gt "$PEAK_TEMP" ] && PEAK_TEMP=$MAX_T
  sleep "$INTERVAL"
done

# 4) 收尾背景工作
for pid in "${HZ_PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done
[ -n "$TEGRA_PID" ] && kill "$TEGRA_PID" 2>/dev/null || true

OOM_AFTER=$(dmesg 2>/dev/null | grep -ciE "out of memory|oom-killer|killed process" || true)
OOM_AFTER=${OOM_AFTER:-0}
OOM_NEW=$((OOM_AFTER - OOM_BEFORE))

# 5) 摘要
GPU_AVG="N/A"; GPU_PEAK="N/A"
if [ -s "$OUT_DIR/tegrastats.log" ]; then
  GPU_STATS=$(grep -oE "GR3D_FREQ [0-9]+%" "$OUT_DIR/tegrastats.log" | grep -oE "[0-9]+" \
    | awk '{s+=$1; if($1>p)p=$1; n++} END{if(n>0) printf "%.0f %.0f", s/n, p}')
  GPU_AVG=$(echo "$GPU_STATS" | awk '{print $1}')
  GPU_PEAK=$(echo "$GPU_STATS" | awk '{print $2}')
fi
GW_AVG="N/A"
if [ "${#GW_SAMPLES[@]}" -gt 0 ]; then
  GW_AVG=$(printf '%s\n' "${GW_SAMPLES[@]}" | awk '{s+=$1; n++} END{printf "%.0f", s/n}')
fi

{
  echo "==================== UNDER-LOAD SUMMARY ===================="
  echo "Duration:        ${DURATION}s"
  echo "Peak RAM used:   ${PEAK_RAM_USED}MB"
  echo "Min RAM avail:   ${MIN_RAM_AVAIL}MB    $( [ "$MIN_RAM_AVAIL" -ge 500 ] && echo PASS || echo '⚠ WARN <500MB' )"
  echo "Peak temp:       ${PEAK_TEMP}C    $( [ "$PEAK_TEMP" -lt 85 ] && echo PASS || echo '⚠ WARN >=85C' )"
  echo "GPU GR3D:        avg=${GPU_AVG}% peak=${GPU_PEAK}%"
  echo "Gateway /health: avg=${GW_AVG}ms"
  echo "New OOM events:  ${OOM_NEW}    $( [ "$OOM_NEW" -eq 0 ] && echo PASS || echo '🔴 FAIL — dmesg 有新 OOM' )"
  echo ""
  echo "Topic Hz（整段平均）:"
  for TOPIC in "${TOPIC_LIST[@]}"; do
    SAFE_NAME=$(echo "$TOPIC" | tr '/' '_')
    HZ=$(grep "average rate" "$OUT_DIR/topic_hz/${SAFE_NAME}.log" 2>/dev/null | tail -1 | awk '{print $3}')
    echo "  ${TOPIC} = ${HZ:-NO_DATA} Hz"
  done
  echo ""
  echo "判讀: RAM avail>=500MB / temp<85C / OOM=0 / LiDAR>=8Hz / camera>=10Hz"
  echo "      / face debug>=3Hz / object debug>=4Hz / vision status>=4Hz"
  echo "全過 → 可考慮 nav+vision 同跑一鏡；任一 FAIL → 維持分 take。"
  echo "============================================================="
} | tee "$OUT_DIR/summary.txt"

echo ""
echo "結果目錄: $OUT_DIR"
