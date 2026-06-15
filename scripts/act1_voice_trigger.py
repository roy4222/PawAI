#!/usr/bin/env python3
"""Act1 語音 fast-path 觸發器 — rule-based、窄 intent、safety-gated。NO LLM / NO LangGraph。

雙訂 /brain/text_input（Studio 收音，JSON envelope）＋ /asr_result（Jetson 麥 raw）→
命中固定中文關鍵字 → safety gate → 觸發 scripts/act1_forward.sh
（reactive demo_forward **standalone /cmd_vel 直連**：短距直行 + 正前障礙安全停車）。

⚠️ NEEDS_ROY_ESTOP_TEST（6/15）：底層 motion 已從撞過車的整合 mux 路徑改回 standalone
   /cmd_vel 直連（見 start_reactive_forward_demo.sh header）。第一次 live 必須 Roy 手持
   實體 e-stop + Go2 確認無損。本節點只是窄觸發 + 軟 safety gate，不是停車唯一來源。

設計約束（6/15 Roy 拍板）：
  - 不接 LLM 決策、不走自由對話、不解析任意距離、不走到人面前。
  - 固定短距：until obstacle / timeout（act1_forward.sh 內含 ~2.4s 上限）。
  - 不建圖、不 AMCL、不 Nav2、不 goto_relative。只做短距直行 + 正前方停障。

safety gate 直接訂 /scan_rplidar 自算前方最近距離（±18°、front_offset=π 補 LiDAR 反裝），
**不依賴 reactive 的 zone**（reactive locked 時 zone 卡在 "init"、抓不到 danger）。

三層觸發之「語音主線」；Studio hidden button / CLI 走同一個 act1_forward.sh。
安全：移動中最終急停永遠是實體 e-stop 遙控器。本節點只是窄觸發 + 軟 safety gate。
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

KEYWORDS = ("往前走", "往前移動", "往前一點", "前進", "走一點", "過來一點", "往前")
COOLDOWN_S = 8.0
SCAN_FRESH_S = 1.5            # /scan_rplidar 新鮮度（超過視為感知未就緒）
DANGER_M = 1.1               # 與 reactive demo_forward danger 一致
FRONT_ARC_RAD = math.radians(18.0)
FRONT_OFFSET_RAD = math.pi   # LiDAR 反裝 yaw=π 補正
RANGE_MIN_M, RANGE_MAX_M = 0.10, 8.0
ACT1_SCRIPT = os.path.expanduser("~/elder_and_dog/scripts/act1_forward.sh")


class Act1VoiceTrigger(Node):
    def __init__(self):
        super().__init__("act1_voice_trigger")
        self.tts_pub = self.create_publisher(String, "/tts", 10)
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

    def _on_asr(self, msg: String):
        self._handle_text((msg.data or "").strip(), "asr")

    def _on_text_input(self, msg: String):
        # Studio path: JSON envelope {"text": "...", "source": "studio_text"}
        try:
            text = str(json.loads(msg.data).get("text") or "").strip()
        except Exception:
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
        try:
            front = self._front_min
            # gate 1: 感知就緒？
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
            time.sleep(0.3)
            try:
                subprocess.run(["bash", ACT1_SCRIPT], timeout=15, check=False)
            except Exception as exc:  # noqa: BLE001
                self.get_logger().error(f"act1_forward.sh 失敗: {exc}")
        finally:
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
