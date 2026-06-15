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
# ⚠️ /cmd_vel 無競爭 driver 鐵則：
#   brain demo 預設起 twist_mux + joy(teleop)，兩者也發 /cmd_vel → 與 standalone reactive 搶、
#   danger-stop 失效（且 hot /cmd_vel_joy 是 5/11 撞牆源）。brain 本身**不用 /cmd_vel**（動作走
#   /webrtc_req），所以殺 twist_mux/teleop/joy 不影響 face/object/gesture/safety/TTS。
#   - **預設 ACT1_KILL_COMPETITORS=1**：自動 pkill twist_mux/teleop/joy。設 0 才不殺（不建議）。
#   - 啟動後 gate 自動驗「無競爭 node + reactive 就緒」，否則 fail-closed 拒絕。
#   注意：/cmd_vel **正常會有 2 個 publisher**（reactive + voice node 的 stop-pub，A-2 保證停車用、
#   只在 enable=false 後發 0、彼此協調不打架），這是設計；關鍵看「競爭 node 是否為空」非 raw count。
#
# 觸發（三層共用同一條 act1_forward.sh，本腳本一併啟語音節點）：
#   - 語音 / Studio 文字「往前走」→ act1_voice_trigger.py（window "voice"）→ act1_forward.sh
#   - operator 手動：bash scripts/act1_forward.sh        # 短距前進 + 遇障停 + 鎖回
#                    bash scripts/act1_forward.sh hold   # 立即急停 + 鎖回
#
# demo_forward 參數（6/15 撞車後加大停障餘裕，Roy「danger 提高到 1.5m 左右」）：
#   front_arc_deg=18 / danger=1.5 / slow=1.8 / slow_speed=0.6(=normal,跳過 slow 避 Go2 MIN_X)
#   normal_speed=0.6 / front_offset_rad=π(LiDAR 反裝補正)
#   ⚠ 為何 danger 1.1→1.5：Go2 sport 速度地板 0.5（無法更慢），0.6m/s + WebRTC/sport 煞停延遲
#   + LiDAR 裝在機鼻後 ~0.32m → danger=1.1 時「LiDAR 看到 1.1m」到「機鼻真的停」常只剩 ~30cm，
#   一遇延遲尖峰或側前盲區就撞（6/15 實機）。1.5m 多 ~0.4m 緩衝、把停點推離邊緣。
#   想要更早停: ACT1_DANGER_M=1.8；想回舊調校: ACT1_DANGER_M=1.1（不建議，撞過）。
# ⚠️ NO `set -u`：ROS setup.bash 不是 nounset-clean，gate subshell source 它在 -u 下會致命
# exit → `|| exit 1` 誤觸發（gate 假死，6/15 抓到）。變數都 ${VAR:-default} 防呆，不需 -u。
set -eo pipefail

SESSION="act1react"
ROS_SETUP="source /opt/ros/humble/setup.zsh && source ~/rplidar_ws/install/setup.zsh && source ~/elder_and_dog/install/setup.zsh"
# standalone 直連（已驗證會停）。改成 /cmd_vel_obstacle 會回到 6/15 撞過車的 mux 路徑 — 別改。
CMD_VEL_TOPIC="${ACT1_CMD_VEL_TOPIC:-/cmd_vel}"
FRONT_ARC="${ACT1_FRONT_ARC_DEG:-18.0}"
DANGER="${ACT1_DANGER_M:-1.5}"   # 6/15 撞車後 1.1→1.5（多 ~0.4m 停障餘裕；env 可覆蓋）
SLOW="${ACT1_SLOW_M:-1.8}"       # 須 > danger（slow_speed=normal 故 slow 區功能性無作用，僅保序）
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
tmux send-keys -t "$SESSION:verify" "$ROS_SETUP && watch -n 2 'echo \"=== /cmd_vel publishers (期望 ≤2 = reactive+voice；下方競爭者才是關鍵) ===\"; ros2 topic info ${CMD_VEL_TOPIC} | grep -i \"publisher count\"; echo; echo \"=== 競爭者 (期望空) ===\"; ros2 node list | grep -E \"twist_mux|teleop|joy_node\" || echo \"(none)\"; echo; echo \"=== reactive enable (期望 False 直到觸發) ===\"; ros2 param get /reactive_stop_node enable'" Enter

sleep 2

# --- fail-safe gate（fail-closed + 輪詢等就緒）---
# 安全不變式＝「**無不協調競爭 driver**」(twist_mux/teleop/joy/nav 直發 /cmd_vel)，**不是** raw
# count==1：voice node 自己也在 /cmd_vel 開了 cmd_pub（A-2 保證停車用、只在 enable=false 後發 0），
# 所以正常情況 /cmd_vel 有 2 個 publisher（reactive + voice）且彼此協調、不打架。故 gate 改檢查
# 競爭 node 是否存在 + reactive 是否就緒；偵測競爭 node 或 publisher>2(未知 driver) → fail-closed 拒絕。
(
  source /opt/ros/humble/setup.bash 2>/dev/null || true
  source ~/elder_and_dog/install/setup.bash 2>/dev/null || true
  ready=0
  for _ in $(seq 1 12); do
    NODES=$(ros2 node list 2>/dev/null || true)
    COMP=$(printf '%s\n' "$NODES" | grep -cE 'twist_mux|teleop|joy_node' || true)
    REACTIVE_UP=$(printf '%s\n' "$NODES" | grep -c 'reactive_stop' || true)
    PUBCOUNT=$(ros2 topic info "$CMD_VEL_TOPIC" 2>/dev/null | grep -iE 'publisher count' | grep -oE '[0-9]+' | head -1)
    if [ "${COMP:-0}" -ge 1 ] 2>/dev/null; then
      echo ""
      echo "🔴 拒絕：偵測到競爭 node（twist_mux/teleop/joy）還在 → 會與 reactive 搶 /cmd_vel、danger-stop 失效。"
      echo "   處置：ACT1_KILL_COMPETITORS=1 重跑，或確認 brain demo 起時關 mux+joystick。"
      tmux kill-session -t "$SESSION" 2>/dev/null || true
      exit 1
    fi
    if [ -n "$PUBCOUNT" ] && [ "$PUBCOUNT" -gt 2 ] 2>/dev/null; then
      echo ""
      echo "🔴 拒絕：${CMD_VEL_TOPIC} 有 ${PUBCOUNT} 個 publisher（預期 ≤2＝reactive+voice）→ 有未知 driver 在發 /cmd_vel。"
      tmux kill-session -t "$SESSION" 2>/dev/null || true
      exit 1
    fi
    if [ "${REACTIVE_UP:-0}" -ge 1 ] 2>/dev/null && [ -n "$PUBCOUNT" ]; then
      ready=1; break
    fi
    sleep 1
  done
  if [ "$ready" != "1" ]; then
    echo ""
    echo "🔴 拒絕（fail-closed）：~12s 內無法確認 reactive 就緒 + 無競爭 node。看 tmux 'reactive' window 排除後重跑。"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    exit 1
  fi
  echo "[act1] ✓ reactive 就緒、無競爭 node、${CMD_VEL_TOPIC} publisher=${PUBCOUNT}（reactive + voice stop-pub，正常）。"
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
