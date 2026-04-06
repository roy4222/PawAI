#!/bin/bash
# scripts/stress_test_monitor.sh
# 壓力測試監控（被 start_stress_test_tmux.sh 呼叫）
# 用法: bash stress_test_monitor.sh [duration_sec]
set -o pipefail

DURATION="${1:-60}"
INTERVAL=5
PEAK_RAM=0
PEAK_TEMP=0
SAMPLES=0

source /opt/ros/humble/setup.bash
source ~/elder_and_dog/install/setup.bash 2>/dev/null || true

echo ""
echo "==================== STRESS TEST START ===================="
echo "Duration: ${DURATION}s | Interval: ${INTERVAL}s"
echo "==========================================================="
echo ""

for (( t=0; t<DURATION; t+=INTERVAL )); do
  SAMPLES=$((SAMPLES+1))
  echo "--- t=${t}s ---"

  # RAM
  RAM_USED=$(free -m | awk '/Mem:/{print $3}')
  RAM_AVAIL=$(free -m | awk '/Mem:/{print $7}')
  echo "RAM: used=${RAM_USED}MB avail=${RAM_AVAIL}MB"
  [ "$RAM_USED" -gt "$PEAK_RAM" ] && PEAK_RAM=$RAM_USED

  # CPU
  CPU=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}')
  echo "CPU: ${CPU}%"

  # Temperature
  MAX_T=0
  TEMPS=""
  for tz in /sys/devices/virtual/thermal/thermal_zone*/temp; do
    if [ -f "$tz" ]; then
      RAW=$(cat "$tz")
      T=$((RAW / 1000))
      if [ "$T" -gt 0 ]; then
        TEMPS="${TEMPS}${T}C "
        [ "$T" -gt "$MAX_T" ] && MAX_T=$T
      fi
    fi
  done
  echo "Temp: ${TEMPS}(max=${MAX_T}C)"
  [ "$MAX_T" -gt "$PEAK_TEMP" ] && PEAK_TEMP=$MAX_T

  # Topic Hz (3s sample each, sequential — rough observation only)
  echo -n "FPS: "
  for TOPIC in /face_identity/debug_image /vision_perception/debug_image /state/perception/face; do
    HZ=$(timeout 4 ros2 topic hz "$TOPIC" 2>/dev/null | grep "average rate" | tail -1 | awk '{print $3}') || true
    echo -n "${TOPIC##*/}=${HZ:-N/A}Hz  "
  done
  echo ""
  echo ""

  sleep "$INTERVAL"
done

echo "==================== SUMMARY ===================="
echo "Duration:   ${DURATION}s"
echo "Samples:    ${SAMPLES}"
echo "Peak RAM:   ${PEAK_RAM}MB"
echo "Peak Temp:  ${PEAK_TEMP}C"
echo "=================================================="
echo ""
echo "人工判讀要點:"
echo "  RAM 餘量 >= 500MB?"
echo "  溫度 < 85C?"
echo "  face debug_image > 3 Hz?"
echo "  vision debug_image > 5 Hz?"
