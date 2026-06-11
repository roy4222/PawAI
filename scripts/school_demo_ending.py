#!/usr/bin/env python3
"""School-demo ending publisher — 2026-05-16 招生活動產物（活動已過，CLI 命令已退役）.

保留原因：wait-for-subscriber-then-publish pattern 解的是真實 DDS one-shot-pub
race — 一次性 `ros2 topic pub`（即使 `-w 1`）在 publish() 返回瞬間就拆掉
publisher，DDS 未必已把訊息 flush 上線，/tts 約 1/3 機率被靜默丟棄
（2026-05-15 實機觀測）。本 pattern：等兩個 subscription 被 DDS discovery
發現 → publish → spin 1.5s 讓 RELIABLE QoS 寫入真正落地後才退出。
任何需要可靠 one-shot publish 的場合都可重用。

Run ON the Jetson (needs rclpy + go2_interfaces):
    source /opt/ros/humble/setup.zsh && source install/setup.zsh
    python3 scripts/school_demo_ending.py
"""
import sys
import time

import rclpy
from go2_interfaces.msg import WebRtcReq
from std_msgs.msg import String

SCHOOL_DEMO_ENDING_TEXT = "最後~祝各位考生面試順利！請記得，輔大資管系填寫第一志願喔！"
FINGER_HEART_API_ID = 1036  # Go2 sport action「比愛心」


def main() -> int:
    rclpy.init()
    n = rclpy.create_node("pawai_school_ending")
    heart = n.create_publisher(WebRtcReq, "/webrtc_req", 10)
    tts = n.create_publisher(String, "/tts", 10)

    # Wait (≤15s) until DDS discovery sees both subscribers — publishing
    # before discovery is the exact failure mode this script exists to avoid.
    deadline = time.time() + 15.0
    while time.time() < deadline and (
        heart.get_subscription_count() == 0 or tts.get_subscription_count() == 0
    ):
        rclpy.spin_once(n, timeout_sec=0.1)

    tts_subs = tts.get_subscription_count()
    heart_subs = heart.get_subscription_count()
    if tts_subs == 0:
        print("ERROR: no /tts subscriber discovered after 15s; not publishing",
              file=sys.stderr)
        n.destroy_node()
        rclpy.shutdown()
        return 20
    if heart_subs == 0:
        print("WARN: no /webrtc_req subscriber discovered; publishing speech only",
              file=sys.stderr)

    heart.publish(WebRtcReq(id=0, topic="rt/api/sport/request",
                            api_id=FINGER_HEART_API_ID, parameter="", priority=0))
    msg = String()
    msg.data = SCHOOL_DEMO_ENDING_TEXT
    tts.publish(msg)

    # Spin past publish so the RELIABLE-QoS write actually lands on the wire
    # before the process (and its DDS participant) disappears.
    flush = time.time() + 1.5
    while time.time() < flush:
        rclpy.spin_once(n, timeout_sec=0.1)

    n.destroy_node()
    rclpy.shutdown()
    print(f"school ending published (tts_subs={tts_subs}, heart_subs={heart_subs})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
