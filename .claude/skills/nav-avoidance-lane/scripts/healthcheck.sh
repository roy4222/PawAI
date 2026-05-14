#!/usr/bin/env bash
# nav-avoidance-lane healthcheck
set -uo pipefail

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
FAILS=0

ros() { ssh $SSH_OPTS "$JETSON_HOST" "source /opt/ros/humble/setup.zsh && source ~/elder_and_dog/install/setup.zsh && $1" 2>/dev/null; }

echo "═══ nav-avoidance-lane healthcheck ═══"

# ── /scan_rplidar Hz ───────────────────────────────────────
echo -n "[1] /scan_rplidar Hz ≥ 10 ... "
HZ=$(ros "timeout 4 ros2 topic hz /scan_rplidar 2>&1 | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+'" || echo "0")
if [ -n "$HZ" ] && (( $(echo "$HZ >= 10" | bc -l 2>/dev/null || echo 0) )); then
  echo "✅ $HZ Hz"
else
  echo "❌ ${HZ:-無} Hz → sllidar_node 沒跑或 USB 斷"
  FAILS=$((FAILS+1))
fi

# ── /tf base_link→laser ────────────────────────────────────
echo -n "[2] /tf base_link→laser ... "
if ros "timeout 3 ros2 run tf2_ros tf2_echo base_link laser 2>&1 | grep -q 'Translation'"; then
  echo "✅"
else
  echo "❌ static TF 沒發 → 確認 tf window 在跑"
  FAILS=$((FAILS+1))
fi

# ── /odom（amcl/capability/fallback）───────────────────────
echo -n "[3] /odom Hz ≥ 5 ... "
ODOM_HZ=$(ros "timeout 4 ros2 topic hz /odom 2>&1 | grep -oE 'average rate: [0-9.]+' | head -1 | grep -oE '[0-9.]+'" || echo "0")
if [ -n "$ODOM_HZ" ] && (( $(echo "$ODOM_HZ >= 5" | bc -l 2>/dev/null || echo 0) )); then
  echo "✅ $ODOM_HZ Hz"
else
  echo "—  ${ODOM_HZ:-無} Hz（mapping mode 預期沒有）"
fi

# ── /amcl_pose（amcl/capability）───────────────────────────
echo -n "[4] /amcl_pose 有 publisher ... "
if ros "ros2 topic info /amcl_pose 2>/dev/null | grep -q 'Publisher count: [1-9]'"; then
  echo "✅ — 確認 Foxglove 已設 /initialpose 讓 AMCL 收斂"
else
  echo "—  沒有（mapping/fallback mode 預期沒有）"
fi

# ── /cmd_vel_obstacle（capability/fallback）────────────────
echo -n "[5] reactive_stop_node 在跑 ... "
if ros "ros2 node list 2>/dev/null | grep -q 'reactive_stop_node'"; then
  echo "✅"
else
  echo "—  沒起（mapping/amcl mode 預期沒有）"
fi

# ── /capability/nav_ready（capability）─────────────────────
echo -n "[6] /capability/nav_ready ... "
NAV_READY=$(ros "timeout 3 ros2 topic echo /capability/nav_ready --once 2>/dev/null | grep -oE 'data: (true|false)' | head -1" || echo "")
if echo "$NAV_READY" | grep -q "data: true"; then
  echo "✅ true"
elif echo "$NAV_READY" | grep -q "data: false"; then
  echo "⚠️  false → AMCL 還沒收斂或 covariance 太高"
else
  echo "—  topic 不存在（非 capability mode 預期）"
fi

# ── /cmd_vel_joy hot publisher（capability safety）─────────
echo -n "[6b] /cmd_vel_joy publisher count = 0 ... "
JOY_PUBS=$(ros "ros2 topic info /cmd_vel_joy 2>/dev/null | grep -oE 'Publisher count: [0-9]+' | grep -oE '[0-9]+' | head -1" || echo "")
JOY_PUBS="${JOY_PUBS:-0}"
if [ "$JOY_PUBS" = "0" ]; then
  echo "✅"
else
  echo "❌ $JOY_PUBS publisher(s) → teleop hot publisher 會蓋過 Nav2 /cmd_vel_nav"
  FAILS=$((FAILS+1))
fi

# ── /cartographer_node（mapping）───────────────────────────
echo -n "[7] cartographer_node alive ... "
if ros "ros2 node list 2>/dev/null | grep -q 'cartographer_node'"; then
  echo "✅"
else
  echo "—  沒起（非 mapping mode 預期）"
fi

# ── go2_driver alive（非 mapping）──────────────────────────
echo -n "[8] go2_driver_node alive ... "
if ros "ros2 node list 2>/dev/null | grep -q 'go2_driver_node'"; then
  echo "✅"
else
  echo "—  沒起（mapping mode 預期沒有）"
fi

# ── 總結 ───────────────────────────────────────────────────
echo "═══ healthcheck 結果 ═══"
if [ "$FAILS" = "0" ]; then
  echo "✅ 全綠（— 標示為非該 mode 預期）"
  exit 0
else
  echo "❌ $FAILS 項 fail"
  exit 1
fi
