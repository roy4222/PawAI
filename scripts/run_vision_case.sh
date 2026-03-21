#!/bin/bash
# scripts/run_vision_case.sh
# 半自動手勢/姿勢測試：你宣告 case，系統自動錄 event + 產生 log
#
# 用法：
#   bash scripts/run_vision_case.sh stop       # 測 stop 手勢
#   bash scripts/run_vision_case.sh fist       # 測 fist 手勢
#   bash scripts/run_vision_case.sh standing   # 測 standing 姿勢
#   bash scripts/run_vision_case.sh fallen     # 測 fallen 姿勢
#
# 前提：vision-debug tmux session 已在跑（start_vision_debug_tmux.sh）
set -euo pipefail

CASE="${1:?用法: bash run_vision_case.sh <case_name>  (stop|fist|point|standing|sitting|crouching|fallen)}"
DURATION="${2:-10}"  # 預設錄 10 秒
LOG_DIR="logs/vision_eval"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$LOG_DIR"

EVENT_LOG="$LOG_DIR/${TIMESTAMP}_${CASE}_events.log"
META_FILE="$LOG_DIR/${TIMESTAMP}_${CASE}_meta.json"
CSV_FILE="$LOG_DIR/results.csv"

# 取得當前參數（從 ROS2 param）
source /opt/ros/humble/setup.zsh 2>/dev/null || true

echo "========================================="
echo "  Vision Test Case: $CASE"
echo "  Duration: ${DURATION}s"
echo "  Log: $EVENT_LOG"
echo "========================================="
echo ""
echo ">>> 準備好後按 Enter 開始錄製... <<<"
echo ">>> 請在 ${DURATION} 秒內做出 '$CASE' 動作 <<<"
read -r

echo "開始錄製..."
START_TIME=$(date -Iseconds)

# 同時錄 gesture 和 pose events
{
  timeout "$DURATION" ros2 topic echo /event/gesture_detected 2>/dev/null &
  G_PID=$!
  timeout "$DURATION" ros2 topic echo /event/pose_detected 2>/dev/null &
  P_PID=$!
  wait $G_PID $P_PID 2>/dev/null
} > "$EVENT_LOG" 2>&1 || true

END_TIME=$(date -Iseconds)
echo "錄製完成。"

# 計算事件數
N_GESTURE=$(grep -c '"gesture_detected"' "$EVENT_LOG" 2>/dev/null || echo 0)
N_POSE=$(grep -c '"pose_detected"' "$EVENT_LOG" 2>/dev/null || echo 0)

# 取得事件明細
GESTURE_EVENTS=$(grep '"gesture":' "$EVENT_LOG" 2>/dev/null | sed 's/.*"gesture": "\([^"]*\)".*/\1/' | sort | uniq -c | awk '{printf "%s x%s", $2, $1}' | paste -sd ', ' || echo "none")
POSE_EVENTS=$(grep '"pose":' "$EVENT_LOG" 2>/dev/null | sed 's/.*"pose": "\([^"]*\)".*/\1/' | sort | uniq -c | awk '{printf "%s x%s", $2, $1}' | paste -sd ', ' || echo "none")

# 判定是否通過
PASS="false"
case "$CASE" in
  stop|fist|point|wave)
    # 手勢 case：預期的手勢事件 > 0
    EXPECTED_GESTURE="$CASE"
    [ "$CASE" = "fist" ] && EXPECTED_GESTURE="ok"  # fist→ok 映射
    if echo "$GESTURE_EVENTS" | grep -q "$EXPECTED_GESTURE"; then
      PASS="true"
    fi
    ;;
  standing|sitting|crouching|fallen)
    # 姿勢 case：預期的姿勢事件 > 0
    if echo "$POSE_EVENTS" | grep -q "$CASE"; then
      PASS="true"
    fi
    ;;
  none)
    # 無手勢 case：0 個手勢事件
    if [ "$N_GESTURE" = "0" ]; then
      PASS="true"
    fi
    ;;
esac

# 寫 meta.json
cat > "$META_FILE" << METAEOF
{
  "case_name": "$CASE",
  "start_time": "$START_TIME",
  "end_time": "$END_TIME",
  "duration_sec": $DURATION,
  "gesture_backend": "mediapipe",
  "pose_backend": "mediapipe",
  "n_gesture_events": $N_GESTURE,
  "n_pose_events": $N_POSE,
  "gesture_events": "$GESTURE_EVENTS",
  "pose_events": "$POSE_EVENTS",
  "pass": $PASS
}
METAEOF

# 追加 CSV（首次建立 header）
if [ ! -f "$CSV_FILE" ]; then
  echo "timestamp,case,duration,n_gesture,n_pose,gesture_events,pose_events,pass" > "$CSV_FILE"
fi
echo "$TIMESTAMP,$CASE,$DURATION,$N_GESTURE,$N_POSE,\"$GESTURE_EVENTS\",\"$POSE_EVENTS\",$PASS" >> "$CSV_FILE"

# 結果
echo ""
echo "========================================="
echo "  結果: $([ "$PASS" = "true" ] && echo "✅ PASS" || echo "❌ FAIL")"
echo "  手勢事件: $N_GESTURE ($GESTURE_EVENTS)"
echo "  姿勢事件: $N_POSE ($POSE_EVENTS)"
echo "  Log: $EVENT_LOG"
echo "  Meta: $META_FILE"
echo "========================================="
