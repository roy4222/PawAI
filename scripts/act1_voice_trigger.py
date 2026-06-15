#!/usr/bin/env python3
"""Act1 語音 fast-path 觸發器 — rule-based、窄 intent、safety-gated。NO LLM / NO LangGraph。

雙訂 /brain/text_input（Studio 收音，JSON envelope）＋ /asr_result（Jetson 麥 raw）→
命中固定中文關鍵字 → safety gate → 觸發 scripts/act1_forward.sh
（reactive demo_forward **standalone /cmd_vel 直連**：短距直行 + 正前障礙安全停車）。

⚠️ NEEDS_ROY_ESTOP_TEST（6/15）：底層 motion 走 standalone /cmd_vel 直連
   （見 start_reactive_forward_demo.sh header）。第一次 live 必須 Roy 手持實體 e-stop + Go2 確認無損。

停車保證（6/15 對抗複查 A-2 修）：act1_forward.sh 被 subprocess.run timeout 觸發時是
**直接 SIGKILL bash（不可捕捉，bash 的 trap 不會跑）** → 故停車保證下放到本節點的
`_run_act1` finally：不論 act1_forward.sh 正常結束 / 例外 / 被 SIGKILL，Python 端都會
`_guarantee_stop()`（enable=false + 直發 0 到 /cmd_vel → driver StopMove）。bash 的 trap 仍
保留作 operator 手動執行路徑的保證。

設計約束（6/15 Roy 拍板）：
  - 不接 LLM 決策、不走自由對話、不解析任意距離、不走到人面前。
  - 固定短距：act1_forward.sh enable=true → FORWARD_S(預設 2.0s) → 自停；reactive 於 danger 自動停。
  - 不建圖、不 AMCL、不 Nav2、不 goto_relative。只做短距直行 + 正前方停障。

safety gate 直接訂 /scan_rplidar 自算前方最近距離（±18°、front_offset=π 補 LiDAR 反裝），
**不依賴 reactive 的 zone**。前錐無回波時 _front_min=None → _scan_ready()=False → 拒絕（fail-safe）。
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
COOLDOWN_S = 8.0
SCAN_FRESH_S = 1.5            # /scan_rplidar 新鮮度（超過視為感知未就緒）
DANGER_M = 1.1               # 與 reactive demo_forward danger 一致
FRONT_ARC_RAD = math.radians(18.0)
FRONT_OFFSET_RAD = math.pi   # LiDAR 反裝 yaw=π 補正
RANGE_MIN_M, RANGE_MAX_M = 0.10, 8.0
ACT1_SCRIPT = os.path.expanduser("~/elder_and_dog/scripts/act1_forward.sh")
REACTIVE_NODE = "/reactive_stop_node"
CMD_VEL_TOPIC = os.environ.get("ACT1_CMD_VEL_TOPIC", "/cmd_vel")
# bash 卡住的上限。逾時 subprocess.run 會 SIGKILL bash（bash trap 不跑）→ 故停車由本節點
# finally 的 _guarantee_stop 保證。設小一點以限制「bash 卡住時」clear-path 續走距離。
ACT1_TIMEOUT_S = 8.0


class Act1VoiceTrigger(Node):
    def __init__(self):
        super().__init__("act1_voice_trigger")
        self.tts_pub = self.create_publisher(String, "/tts", 10)
        # Python 端保證停車用（A-2）：直接發 0 到 /cmd_vel → driver StopMove。
        self.cmd_pub = self.create_publisher(Twist, CMD_VEL_TOPIC, 10)
        # demo 走 Studio 收音 → /brain/text_input（JSON envelope）；Jetson 麥 → /asr_result（raw）
        self.create_subscription(String, "/brain/text_input", self._on_text_input, 10)
        self.create_subscription(String, "/asr_result", self._on_asr, 10)
        self.create_subscription(LaserScan, "/scan_rplidar", self._on_scan, 10)
        self._front_min = None
        self._scan_ts = 0.0
        self._last_trigger = 0.0
        self._busy = False
        self.get_logger().info(
            f"act1_voice_trigger ready — keywords={KEYWORDS} danger={DANGER_M}m arc=±18°"
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

    def _guarantee_stop(self):
        """Python 端保證停車（A-2）。在 _run_act1 finally 跑，不論 act1_forward.sh 正常結束、
        例外、或被 subprocess.run timeout SIGKILL（bash trap 不會跑）。

        ⚠️ 真正讓狗停的是 enable=false（reactive 停止發 normal_speed 0.6）—— 那串 0 與
        reactive 殘留的 0.6 在 driver 是**交錯流**（每個 0.6 會 reset StopMove dedupe），
        不是覆蓋。所以 enable=false **必須成功**：重試 + log，不再靜默吞掉失敗（對抗複查 #3）。
        若多次失敗 → 大聲 log，靠 reactive 自身 scan danger-stop + 實體 e-stop 兜底。"""
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
        # enable=false 後 reactive 已閉嘴 → 這串 0 才能乾淨觸發 StopMove（discrete, 一次即停）。
        stop = Twist()
        for _ in range(10):
            try:
                self.cmd_pub.publish(stop)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(0.1)

    def _on_asr(self, msg: String):
        self._handle_text((msg.data or "").strip(), "asr")

    def _on_text_input(self, msg: String):
        # Studio path: JSON envelope {"text": "...", "source": "studio_text"}
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
        self._busy = True            # 立刻上鎖防 concurrent
        self._last_trigger = now
        self.get_logger().info(f"Act1 voice command matched [{src}]: {text!r}")
        threading.Thread(target=self._run_act1, daemon=True).start()

    def _run_act1(self):
        moved = False
        try:
            front = self._front_min
            # gate 1: 感知就緒？（前錐無回波 → _front_min=None → _scan_ready False → 拒絕）
            if not self._scan_ready():
                self._say("目前前方感知尚未就緒，我先不移動。")
                return
            # gate 2: 前方已是 danger？
            if front is not None and front < DANGER_M:
                self.get_logger().info(f"front={front:.2f}m < danger → refuse")
                self._say("前方有障礙，我先停在這裡。")
                return
            # clear → 放行短距前進
            self.get_logger().info(f"front={front:.2f}m clear → forward")
            self._say("好，我往前走一點。")
            moved = True
            time.sleep(0.3)
            subprocess.run(["bash", ACT1_SCRIPT], timeout=ACT1_TIMEOUT_S, check=False)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"act1_forward.sh 失敗: {exc}")
        finally:
            # A-2 保證：只要本次有放行 motion，不論上面如何結束（含 timeout SIGKILL bash），
            # Python 端一定 force-stop。沒放行（gate 擋下）則不碰 enable/cmd_vel。
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
