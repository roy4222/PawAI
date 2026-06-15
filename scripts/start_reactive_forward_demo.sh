#!/usr/bin/env bash
# scripts/start_reactive_forward_demo.sh
# Act1 demo_forward — 短距直行 + 正前障礙安全停車（STANDALONE /cmd_vel 直連路徑）。
#
# ⚠️⚠️ NEEDS_ROY_ESTOP_TEST（6/15 重做，根因見下）：
#   上一版走「整合 mux」路徑（reactive → /cmd_vel_obstacle → twist_mux → driver）6/15 撞車。
#   根因（Cloud 唯讀調查）＝ twist_mux 4.x **沒有 output timer、純 event-driven**，每個 input
#   有 0.5s timeout：一旦 reactive 對 /cmd_vel_obstacle 的供給中斷 0.5s（enable=false 變沉默 /
#   node 被殺 / enable 開太久後才 force-stop），mux 完全停止輸出 → driver 收不到新 /cmd_vel →
#   Go2 繼續執行上一個 Move(0.6) 滑行 2-3s（sport timeout）→ 撞。standalone 直連沒有這層。
#
#   本版改回 **6/15 已實機驗過會停的 standalone /cmd_vel 直連**（reactive 每個 0 直達 driver →
#   StopMove）。但「這個 build」尚未經真機 motion 驗證 → **第一次 live 必須 Roy 手持實體
#   e-stop、且先確認 Go2 撞後無實體損壞**。不穩立刻走 fallback（遙控輔助 / 影片）。
#
# 定位（誠實 claim）：
#   ✅ 短距直行 + 正前方障礙安全停車（front-stop）
#   ❌ 不是自主避障導航 / 不是動態繞障 / 不是走到人面前
#
# 前提：先 `pawai demo start --with-lidar`（提供唯一 go2_driver + raw LiDAR /scan_rplidar）。
#
# ⚠️ /cmd_vel 唯一 publisher 鐵則：
#   brain demo 預設起 twist_mux + joy(teleop)，兩者也發 /cmd_vel → 與本版 standalone reactive
#   衝突（且 hot /cmd_vel_joy 是 5/11 撞牆源）。brain 本身**不用 /cmd_vel**（動作走 /webrtc_req），
#   所以殺 twist_mux/teleop/joy 不影響 face/object/gesture/safety/TTS。
#   - 預設：本腳本**只提醒不自動殺**，並在 verify window 印出 /cmd_vel publisher 數讓你確認。
#   - `ACT1_KILL_COMPETITORS=1 bash scripts/start_reactive_forward_demo.sh` → 自動 pkill 三者。
#   ⮕ 啟動後務必看 verify window：/cmd_vel 必須剛好 1 個 publisher（reactive），否則別觸發 motion。
#
# 觸發（三層共用同一條 act1_forward.sh，本腳本一併啟語音節點）：
#   - 語音 / Studio 文字「往前走」→ act1_voice_trigger.py（window "voice"）→ act1_forward.sh
#   - operator 手動：bash scripts/act1_forward.sh        # 短距前進 + 遇障停 + 鎖回
#                    bash scripts/act1_forward.sh hold   # 立即急停 + 鎖回
#
# demo_forward 參數＝6/15 實機驗證版（standalone 走 ~0.75m、正前障礙前 ~30cm 停）：
#   front_arc_deg=18 / danger=1.1 / slow=1.3 / slow_speed=0.6(=normal,跳過 slow 避 Go2 MIN_X)
#   normal_speed=0.6 / front_offset_rad=π(LiDAR 反裝補正)
set -euo pipefail

SESSION="act1react"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
# standalone 直連（已驗證會停）。改成 /cmd_vel_obstacle 會回到 6/15 撞過車的 mux 路徑 — 別改。
CMD_VEL_TOPIC="${ACT1_CMD_VEL_TOPIC:-/cmd_vel}"
FRONT_ARC="${ACT1_FRONT_ARC_DEG:-18.0}"
DANGER="${ACT1_DANGER_M:-1.1}"
SLOW="${ACT1_SLOW_M:-1.3}"
KILL_COMPETITORS="${ACT1_KILL_COMPETITORS:-1}"
VOICE_NODE="$HOME/elder_and_dog/scripts/act1_voice_trigger.py"

echo "=== Act1 demo_forward reactive_stop (STANDALONE /cmd_vel 直連) ==="
echo "    publish=${CMD_VEL_TOPIC}  arc=±${FRONT_ARC}°  danger=${DANGER}m  speed=0.6  enable=FALSE(locked)"

# --- /cmd_vel 唯一 publisher：fail-safe 預設殺競爭者（A-1 對抗複查修正：預設改 1）---
# brain demo 預設起 twist_mux + joy 也發 /cmd_vel → 與 standalone reactive 雙 publisher 打架、
# danger-stop 可能被打斷（撞狗）。brain 動作走 /webrtc_req，殺 mux/teleop/joy 不影響
# face/object/gesture/safety/TTS（C++ 子 node 不 respawn、launch parent 不因子 node 退出而死）。
if [ "$KILL_COMPETITORS" = "1" ]; then
  echo "[act1] 清掉 /cmd_vel 競爭 publisher（twist_mux/teleop/joy）— brain 走 /webrtc_req 不受影響"
  pkill -f twist_mux 2>/dev/null || true
  pkill -f teleop_twist 2>/dev/null || true
  pkill -f joy_node 2>/dev/null || true
  sleep 1
else
  echo "[act1] ⚠⚠ ACT1_KILL_COMPETITORS=0：你選擇不殺競爭者。若 brain demo 有 twist_mux/joy，"
  echo "       /cmd_vel 會雙 publisher 打架、danger-stop 可能失效（撞狗）。下方 verify 偵測到 >1 會拒絕。"
fi

tmux kill-session -t "$SESSION" 2>/dev/null || true
trap 'echo "Caught signal, killing tmux..."; tmux kill-session -t "$SESSION" 2>/dev/null || true' INT TERM

# window 0: reactive_stop standalone /cmd_vel（無 mode/safety_only → standalone 0/slow/normal）
tmux new-session -d -s "$SESSION" -n reactive
tmux send-keys -t "$SESSION:reactive" "$ROS_SETUP && ros2 run go2_robot_sdk reactive_stop_node --ros-args -p cmd_vel_topic:=${CMD_VEL_TOPIC} -p front_offset_rad:=3.14159 -p front_arc_deg:=${FRONT_ARC} -p danger_distance_m:=${DANGER} -p slow_distance_m:=${SLOW} -p slow_speed:=0.6 -p normal_speed:=0.6 -p enable:=false" Enter

# window 1: 語音 / Studio 文字 fast-path 觸發器（rule-based、scan-gated、NO LLM）
tmux new-window -t "$SESSION" -n voice
tmux send-keys -t "$SESSION:voice" "$ROS_SETUP && python3 ${VOICE_NODE}" Enter

# window 2: verify — /cmd_vel 唯一 publisher 確認 + reactive 狀態（每 2s 刷新）
tmux new-window -t "$SESSION" -n verify
tmux send-keys -t "$SESSION:verify" "$ROS_SETUP && watch -n 2 'echo \"=== /cmd_vel publishers (期望剛好 1 = reactive) ===\"; ros2 topic info ${CMD_VEL_TOPIC} | grep -i \"publisher count\"; echo; echo \"=== 競爭者 (期望空) ===\"; ros2 node list | grep -E \"twist_mux|teleop|joy_node\" || echo \"(none)\"; echo; echo \"=== reactive enable (期望 False 直到觸發) ===\"; ros2 param get /reactive_stop_node enable'" Enter

sleep 2

# --- A-1 fail-safe gate（對抗複查 blocker 2/3 修：fail-closed + 輪詢等就緒）---
# bash body source setup.bash 與 zsh panes 不同 process、不算混用。reactive 在 __init__ 建
# /cmd_vel publisher（enable=false 也算一個），故 LOCKED 狀態仍數得到。輪詢吸收 discovery 延遲；
# 偵測到 >1 立即拒絕；等不到「reactive 就緒且剛好 1 publisher」也 fail-closed 拒絕（不靠人/不放行）。
(
  source /opt/ros/humble/setup.bash 2>/dev/null || true
  source ~/elder_and_dog/install/setup.bash 2>/dev/null || true
  ready=0
  for _ in $(seq 1 12); do
    NODES=$(ros2 node list 2>/dev/null || true)
    REACTIVE_UP=$(printf '%s\n' "$NODES" | grep -c 'reactive_stop' || true)
    PUBCOUNT=$(ros2 topic info "$CMD_VEL_TOPIC" 2>/dev/null | grep -iE 'publisher count' | grep -oE '[0-9]+' | head -1)
    if [ -n "$PUBCOUNT" ] && [ "$PUBCOUNT" -gt 1 ] 2>/dev/null; then
      echo ""
      echo "🔴 拒絕：${CMD_VEL_TOPIC} 有 ${PUBCOUNT} 個 publisher（期望 1）= 雙 publisher 打架、danger-stop 會失效。"
      echo "   多半是 brain demo 的 twist_mux/joy 還在。處置：ACT1_KILL_COMPETITORS=1 重跑，或 brain demo 起時關 mux+joystick。"
      tmux kill-session -t "$SESSION" 2>/dev/null || true
      exit 1
    fi
    if [ "$REACTIVE_UP" -ge 1 ] 2>/dev/null && [ "$PUBCOUNT" = "1" ]; then
      ready=1; break
    fi
    sleep 1
  done
  if [ "$ready" != "1" ]; then
    echo ""
    echo "🔴 拒絕（fail-closed）：~12s 內無法確認 ${CMD_VEL_TOPIC} 剛好 1 個 publisher 且 reactive 已就緒。"
    echo "   可能 reactive 沒起、或 ros2 查詢卡住。不確定就不進 motion。看 tmux 'reactive' window 排除後重跑。"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
  fi
  echo "[act1] ✓ reactive 就緒、${CMD_VEL_TOPIC} publisher = 1（唯一）。"
) || exit 1

echo ""
echo "=== Started (LOCKED — 無 motion 直到觸發) ==="
echo "  ⮕ 先看 verify window：/cmd_vel publisher 必須=1、競爭者=none，才可進行 motion。"
echo "  驗證: tmux attach -t $SESSION   （window: reactive / voice / verify）"
echo "  觸發(語音/Studio): 說「往前走」/ Studio 文字「往前走一點」"
echo "  觸發(手動): bash ~/elder_and_dog/scripts/act1_forward.sh        # 前進+遇障停"
echo "            bash ~/elder_and_dog/scripts/act1_forward.sh hold   # 立即急停+鎖"
echo "  Kill: tmux kill-session -t $SESSION"
echo ""
echo "  ⚠️ 第一次 live = Roy 手持實體 e-stop + Go2 確認無損。不穩立刻 fallback。"
