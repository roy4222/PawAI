#!/usr/bin/env bash
# nav-avoidance-lane preflight
# Usage: bash preflight.sh <mapping|amcl|capability|fallback>
set -uo pipefail

MODE="${1:-}"
if [[ ! "$MODE" =~ ^(mapping|amcl|capability|fallback)$ ]]; then
  echo "❌ usage: preflight.sh <mapping|amcl|capability|fallback>"
  exit 1
fi

JETSON_HOST="${JETSON_HOST:-jetson-nano}"
SSH_OPTS="-o ConnectTimeout=8 -o ServerAliveInterval=5 -o ServerAliveCountMax=2"
JETSON_REPO="${JETSON_REPO:-/home/jetson/elder_and_dog}"
ROBOT_IP="${ROBOT_IP:-192.168.123.161}"
MAP_YAML="${MAP_YAML:-/home/jetson/maps/home_living_room_v8.yaml}"
P0_FAIL=0
P1_WARN=0

echo "═══ nav-avoidance-lane preflight (mode=$MODE) ═══"

# ── P0: SSH ────────────────────────────────────────────────
echo -n "[P0] SSH to $JETSON_HOST ... "
if ssh $SSH_OPTS -o BatchMode=yes "$JETSON_HOST" "echo ok" >/dev/null 2>&1; then
  echo "✅"
else
  echo "❌"; P0_FAIL=1
fi

# ── P0: /dev/rplidar ───────────────────────────────────────
echo -n "[P0] /dev/rplidar 存在 ... "
if ssh $SSH_OPTS "$JETSON_HOST" "[ -e /dev/rplidar ]" 2>/dev/null; then
  echo "✅"
else
  echo "❌ USB LiDAR 沒接 / udev rule 沒 load (檢查 /etc/udev/rules.d/)"
  P0_FAIL=1
fi

# ── P0: rplidar_ws overlay ─────────────────────────────────
echo -n "[P0] ~/rplidar_ws/install/setup.zsh 存在 ... "
if ssh $SSH_OPTS "$JETSON_HOST" "[ -f ~/rplidar_ws/install/setup.zsh ]" 2>/dev/null; then
  echo "✅"
else
  echo "❌ sllidar_ros2 沒裝在 overlay → 要 colcon build rplidar_ws"
  P0_FAIL=1
fi

# ── P0: ROBOT_IP ping（非 mapping）─────────────────────────
if [ "$MODE" != "mapping" ]; then
  echo -n "[P0] Go2 $ROBOT_IP ping 通 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "ping -c 1 -W 2 $ROBOT_IP > /dev/null 2>&1"; then
    echo "✅"
  else
    echo "❌ Go2 沒接 Ethernet / 沒開機"
    P0_FAIL=1
  fi
fi

# ── P0: MAP_YAML（amcl/capability）─────────────────────────
if [[ "$MODE" =~ ^(amcl|capability)$ ]]; then
  echo -n "[P0] MAP_YAML=$MAP_YAML 存在 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "[ -f $MAP_YAML ]" 2>/dev/null; then
    echo "✅"
  else
    echo "❌ map 檔不存在 → 先跑 mapping mode 建圖"
    P0_FAIL=1
  fi
fi

# ── P0: nav_capability runtime dirs ────────────────────────
if [ "$MODE" = "capability" ]; then
  echo -n "[P0] runtime/nav_capability/{named_poses,routes}/ 存在 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "[ -d $JETSON_REPO/runtime/nav_capability/named_poses ] && [ -d $JETSON_REPO/runtime/nav_capability/routes ]" 2>/dev/null; then
    echo "✅"
  else
    echo "⚠️  目錄不存在，自動建立"
    ssh $SSH_OPTS "$JETSON_HOST" "mkdir -p $JETSON_REPO/runtime/nav_capability/named_poses $JETSON_REPO/runtime/nav_capability/routes"
  fi
fi

# ── P0: 沒有殘留 driver instance ───────────────────────────
# nav start 內部都會自啟 go2_driver（mapping 除外），所以啟動前必須 0 個
# 殘留，否則會雙 driver / 雙 publisher。mapping mode 不啟 driver，所以不檢。
if [ "$MODE" != "mapping" ]; then
  echo -n "[P0] 沒有殘留 go2_driver process ... "
  DRIVER_COUNT=$(ssh $SSH_OPTS "$JETSON_HOST" "ps aux | grep -E 'go2_driver_node' | grep -v grep | wc -l" 2>/dev/null || echo 0)
  if [ "$DRIVER_COUNT" = "0" ]; then
    echo "✅"
  else
    echo "❌ $DRIVER_COUNT 個 driver 殘留 → 先跑 brain/nav cleanup（兩 lane cleanup 都會清 driver）"
    P0_FAIL=1
  fi
fi

# ── P1: 沒有 pawai_brain session ───────────────────────────
echo -n "[P1] 沒有 pawai_brain tmux session ... "
if ssh $SSH_OPTS "$JETSON_HOST" "tmux ls 2>/dev/null | grep -q '^pawai_brain'"; then
  echo "⚠️  brain session 在跑 → 建議先 brain-studio-lane cleanup --handoff nav"
  P1_WARN=1
else
  echo "✅"
fi

# ── P1: D435 USB（capability）──────────────────────────────
if [ "$MODE" = "capability" ]; then
  echo -n "[P1] D435 USB 偵測 ... "
  if ssh $SSH_OPTS "$JETSON_HOST" "lsusb | grep -qi 'realsense\\|intel'" 2>/dev/null; then
    echo "✅"
  else
    echo "⚠️  D435 沒偵測到 → depth_safety_node 會 fail，nav 仍可跑"
    P1_WARN=1
  fi
fi

# ── 總結 ───────────────────────────────────────────────────
echo "═══ preflight 結果 ═══"
if [ "$P0_FAIL" = "1" ]; then
  echo "❌ P0 FAIL — 不可啟動"
  exit 1
fi
if [ "$P1_WARN" = "1" ]; then
  echo "⚠️  P1 warning（可啟動）"
fi
echo "✅ Preflight pass — 可啟動 mode=$MODE"
exit 0
