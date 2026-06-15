#!/usr/bin/env python3
"""Act1 controller — 短距直行 / 無地圖避障 觸發器。rule-based、safety-gated。NO LLM / NO Nav2。

**6/18 demo 主線 = Studio 按鈕**（不過 ASR/LLM）：
  Studio「短距前進 0.5/1.0/1.5m」按鈕 → gateway /api/act1/forward {distance_m}
  → 本節點訂 **/act1/forward_cmd** → gate → scripts/act1_forward.sh（reactive demo_forward
  **standalone /cmd_vel 直連**：短距直行 + 正前障礙安全停車）；STOP → /act1/stop → force-stop。

語音是**加分、非主線**：訂 /event/speech_intent_recognized（Studio 麥克風/ws/speech+ws/text）、
/brain/text_input（Studio 打字）、/asr_result（Jetson 麥）→ 命中固定關鍵字 → 同一條 _run_act1。

⚠️ NEEDS_ROY_ESTOP_TEST：底層 motion 走 standalone /cmd_vel 直連，第一次 live 必須 Roy 手持
   實體 e-stop + Go2 確認無損。停車保證放在 finally 的 _guarantee_stop（不靠 bash trap，因 voice/
   subprocess timeout 會 SIGKILL bash）。距離是**時間估算**（distance/0.6m/s），非精準 odom。

設計約束（6/15 Roy 拍板）：不接 LLM 決策、不解析任意距離、不走到人面前、不建圖、不 AMCL、
不 Nav2、不碰 GotoRelative；只做短距直行 + 正前方停障。reactive 預設 locked，按鈕才短暫放行。
"""
import json
import math
import os
import subprocess
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist

KEYWORDS = ("往前走", "往前移動", "往前一點", "前進", "走一點", "過來一點", "往前")
COOLDOWN_S = 8.0            # 語音路徑防 ASR echo 連發
SCAN_FRESH_S = 1.5          # /scan_rplidar 新鮮度（超過視為感知未就緒）
DANGER_M = 1.1             # 與 reactive demo_forward danger 一致
FRONT_ARC_RAD = math.radians(18.0)
FRONT_OFFSET_RAD = math.pi  # LiDAR 反裝 yaw=π 補正
RANGE_MIN_M, RANGE_MAX_M = 0.10, 8.0
ACT1_SCRIPT = os.path.expanduser("~/elder_and_dog/scripts/act1_forward.sh")
REACTIVE_NODE = "/reactive_stop_node"
CMD_VEL_TOPIC = os.environ.get("ACT1_CMD_VEL_TOPIC", "/cmd_vel")
ACT1_TIMEOUT_S = 8.0       # bash 卡住上限；逾時 SIGKILL bash → finally 的 _guarantee_stop 兜底
# 距離→時間估算（無 odom）：time = distance / SPEED。距離夾在 [0.3, 1.5]m。
SPEED_MPS = 0.6
DIST_MIN_M, DIST_MAX_M = 0.3, 1.5
DEFAULT_DIST_M = 1.0       # 語音/未指定距離時的預設


class Act1VoiceTrigger(Node):
    def __init__(self):
        super().__init__("act1_voice_trigger")
        self.tts_pub = self.create_publisher(String, "/tts", 10)
        # Python 端保證停車用（A-2）：直接發 0 到 /cmd_vel → driver StopMove。
        self.cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        # === demo 主線：Studio 按鈕 → gateway → /act1/forward_cmd {distance_m} / /act1/stop ===
        self.create_subscription(String, "/act1/forward_cmd", self._on_forward_cmd, 10)
        self.create_subscription(String, "/act1/stop", self._on_stop_cmd, 10)
        # === 加分：語音/文字（Studio 麥/打字、Jetson 麥）===
        self.create_subscription(
            String, "/event/speech_intent_recognized", self._on_speech_intent, 10
        )
        self.create_subscription(String, "/brain/text_input", self._on_text_input, 10)
        self.create_subscription(String, "/asr_result", self._on_asr, 10)
        self.create_subscription(LaserScan, "/scan_rplidar", self._on_scan, 10)
        self._front_min = None
        self._scan_ts = 0.0
        self._last_trigger = 0.0
        self._busy = False
        self.get_logger().info(
            f"act1 controller ready — button(/act1/forward_cmd)+voice; "
            f"danger={DANGER_M}m arc=±18° speed={SPEED_MPS}m/s dist[{DIST_MIN_M},{DIST_MAX_M}]"
        )

    def _on_scan(self, msg: LaserScan):
        best = float("inf")
        ang = msg.angle_min
        inc = msg.angle_increment
        for r in msg.ranges:
            if RANGE_MIN_M <= r <= RANGE_MAX_M:
                rel = math.atan2(math.sin(ang - FRONT_OFFSET_RAD), math.cos(ang - FRONT_OFFSET_RAD))
                if abs(rel) <= FRONT_ARC_RAD and r < best:
                    best = r
            ang += inc
        self._front_min = best if best != float("inf") else None
        self._scan_ts = time.monotonic()

    def _say(self, text: str):
        m = String()
        m.data = text
        self.tts_pub.publish(m)
        self.get_logger().info(f"TTS: {text}")

    def _scan_ready(self) -> bool:
        return self._front_min is not None and (time.monotonic() - self._scan_ts) < SCAN_FRESH_S

    def _distance_to_seconds(self, distance_m) -> float:
        """距離(m) → 放行時間(s)，夾在合理範圍。無 odom，純時間估算。"""
        try:
            d = float(distance_m)
        except (TypeError, ValueError):
            d = DEFAULT_DIST_M
        d = max(DIST_MIN_M, min(DIST_MAX_M, d))
        return round(d / SPEED_MPS, 2)

    def _guarantee_stop(self):
        """Python 端保證停車（A-2）。在 _run_act1 finally + STOP 按鈕跑，不論 act1_forward.sh
        正常結束/例外/被 SIGKILL（bash trap 不會跑）。enable=false 是真正讓 reactive 停發 0.6 的
        關鍵（那串 0 與殘留 0.6 在 driver 交錯非覆蓋）→ retry + log、不靜默吞；再發 0 觸發 StopMove。"""
        disabled = False
        for attempt in range(3):
            try:
                r = subprocess.run(
                    ["ros2", "param", "set", REACTIVE_NODE, "enable", "false"],
                    timeout=6, check=False, capture_output=True, text=True,
                )
                if r.returncode == 0:
                    disabled = True
                    break
                self.get_logger().warn(
                    f"enable=false 第 {attempt + 1} 次未成功 rc={r.returncode} "
                    f"out={(r.stdout or '').strip()!r} err={(r.stderr or '').strip()!r}"
                )
            except Exception as exc:  # noqa: BLE001
                self.get_logger().warn(f"enable=false 第 {attempt + 1} 次例外: {exc}")
            time.sleep(0.2)
        if not disabled:
            self.get_logger().error(
                "⚠ enable=false 多次失敗 — reactive 可能仍 enable、續發 0.6；"
                "靠 reactive danger-stop + 實體 e-stop 兜底！"
            )
        stop = Twist()
        for _ in range(10):
            try:
                self.cmd_pub.publish(stop)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)

    # ── Studio 按鈕路徑（demo 主線）──────────────────────────────────
    def _on_forward_cmd(self, msg: String):
        """Studio 按鈕 → /act1/forward_cmd {distance_m}。無關鍵字、直接帶距離觸發。"""
        try:
            d = float(json.loads(msg.data).get("distance_m"))
        except Exception:  # noqa: BLE001
            d = DEFAULT_DIST_M
        if self._busy:
            self.get_logger().info(f"forward_cmd ignored (busy) d={d}")
            return
        self._busy = True
        self._last_trigger = time.monotonic()
        self.get_logger().info(f"Act1 forward_cmd (Studio button) distance={d}m")
        threading.Thread(target=self._run_act1, kwargs={"distance_m": d}, daemon=True).start()

    def _on_stop_cmd(self, msg: String):
        """Studio STOP/HOLD → 立刻 force-stop（不過 busy 鎖）。"""
        self.get_logger().info("Act1 STOP/HOLD (Studio button)")
        threading.Thread(target=self._guarantee_stop, daemon=True).start()

    # ── 語音/文字路徑（加分、非主線）────────────────────────────────
    def _on_speech_intent(self, msg: String):
        # /event/speech_intent_recognized：Studio 麥克風 + /ws/text（契約 v2.4 §4.2，欄位 text）。
        try:
            p = json.loads(msg.data)
            text = str(p.get("transcript") or p.get("text") or "").strip()
        except Exception:  # noqa: BLE001
            text = (msg.data or "").strip()
        self._handle_text(text, "speech")

    def _on_asr(self, msg: String):
        self._handle_text((msg.data or "").strip(), "asr")

    def _on_text_input(self, msg: String):
        try:
            text = str(json.loads(msg.data).get("text") or "").strip()
        except Exception:  # noqa: BLE001
            text = (msg.data or "").strip()  # tolerate raw string
        self._handle_text(text, "studio")

    def _handle_text(self, text: str, src: str):
        if not text or not any(k in text for k in KEYWORDS):
            return
        now = time.monotonic()
        if self._busy or (now - self._last_trigger) < COOLDOWN_S:
            self.get_logger().info(f"ignored (busy/cooldown) [{src}]: {text!r}")
            return
        self._busy = True
        self._last_trigger = now
        self.get_logger().info(f"Act1 voice command matched [{src}]: {text!r}")
        threading.Thread(target=self._run_act1, daemon=True).start()

    # ── 共用執行（按鈕 + 語音 都走這）───────────────────────────────
    def _run_act1(self, distance_m=None):
        moved = False
        try:
            front = self._front_min
            # gate 1: 感知就緒？（前錐無回波 → _front_min=None → 拒絕，fail-safe）
            if not self._scan_ready():
                self._say("目前前方感知尚未就緒，我先不移動。")
                return
            # gate 2: 前方已是 danger？
            if front is not None and front < DANGER_M:
                self.get_logger().info(f"front={front:.2f}m < danger → refuse")
                self._say("前方有障礙，我先停在這裡。")
                return
            # clear → 放行短距前進（時間 = 距離/速度）
            forward_s = self._distance_to_seconds(distance_m)
            dist = distance_m if distance_m is not None else DEFAULT_DIST_M
            self.get_logger().info(f"front={front:.2f}m clear → forward {forward_s}s (~{dist}m)")
            self._say("好，我往前走一點。")
            moved = True
            time.sleep(0.3)
            env = dict(os.environ)
            env["ACT1_FORWARD_S"] = str(forward_s)
            subprocess.run(["bash", ACT1_SCRIPT], env=env, timeout=ACT1_TIMEOUT_S, check=False)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"act1_forward.sh 失敗: {exc}")
        finally:
            # A-2 保證：只要有放行 motion，不論如何結束（含 timeout SIGKILL bash）都 force-stop。
            if moved:
                self._guarantee_stop()
            self._busy = False


def main():
    rclpy.init()
    node = Act1VoiceTrigger()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
