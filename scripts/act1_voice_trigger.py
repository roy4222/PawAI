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

try:
    from go2_interfaces.msg import WebRtcReq
except ImportError:  # pragma: no cover — degrade loudly, never silently
    WebRtcReq = None

KEYWORDS = ("往前走", "往前移動", "往前一點", "前進", "走一點", "過來一點", "往前")
COOLDOWN_S = 8.0            # 語音路徑防 ASR echo 連發
SCAN_FRESH_S = 1.5          # /scan_rplidar 新鮮度（超過視為感知未就緒）
DANGER_M = 1.5             # 與 reactive demo_forward danger 一致（6/15 撞車後 1.1→1.5 加大餘裕）
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
# 硬 STOP：直送 StopMove 給 driver（不經 reactive/cmd_vel，sport 立即 halt 仍站立）。
# 形狀對齊 vision_perception/event_action_bridge.py（不發明 API）。
SPORT_TOPIC = "rt/api/sport/request"
STOP_MOVE_API_ID = 1003     # StopMove（halt 但維持平衡；**不可**用 Damp 1001 會癱倒）
STOP_REFRESH_COUNT = 3      # 立即 1 次 + 之後 refresh；防 DataChannel 丟包
STOP_REFRESH_INTERVAL_S = 1.0  # ≤1Hz；勿 10Hz spam（會把 DataChannel bufferedAmount 撐爆）
FORWARD_DANGER_POLL_S = 0.05   # 前進中主動 LiDAR 防撞閘輪詢間隔（20Hz）


class Act1VoiceTrigger(Node):
    def __init__(self):
        super().__init__("act1_voice_trigger")
        self.tts_pub = self.create_publisher(String, "/tts", 10)
        # 硬 STOP 直送 driver 的 sport 指令通道（StopMove 1003）。reactive enable=false 只是
        # 軟解除、不會煞車；真正讓 Go2 立即 halt 的是這條 /webrtc_req。
        self._pub_webrtc = (
            self.create_publisher(WebRtcReq, "/webrtc_req", 10)
            if WebRtcReq is not None else None
        )
        if self._pub_webrtc is None:
            self.get_logger().error(
                "go2_interfaces.WebRtcReq import 失敗 → STOP 無法直送 StopMove，"
                "只剩 enable=false 軟解除（不安全）。檢查 go2_interfaces 是否 build/source。"
            )
        # ⚠️ 本節點**不**開 /cmd_vel publisher（6/15 真機抓到：voice cmd_pub 發 0 會與 reactive
        # 的 0.6 在 /cmd_vel 交錯 → driver 在 Move/StopMove 間反覆 → 狗原地抖不前進）。
        # /cmd_vel 的唯一 driver 是 reactive_stop_node；停車靠 enable=false + act1_forward.sh
        # 的 topic-pub（在 reactive 停發後、單一 publisher）+ reactive 自身 danger-stop。
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
        self._forward_proc = None       # 正在跑的 act1_forward.sh handle（STOP 要能 kill 它）
        self.get_logger().info(
            f"act1 controller ready — button(/act1/forward_cmd)+voice; "
            f"danger={DANGER_M}m arc=±18° speed={SPEED_MPS}m/s dist[{DIST_MIN_M},{DIST_MAX_M}]; "
            f"hard-stop=StopMove({STOP_MOVE_API_ID}) via /webrtc_req"
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
        """保證 reactive 停下來（A-2）。在 _run_act1 finally + STOP 按鈕跑，不論 act1_forward.sh
        正常結束/例外/被 SIGKILL（bash trap 不會跑）。**只設 enable=false**（retry + log、不靜默吞）
        —— 不在此發 /cmd_vel 0（那會讓本節點變第二個 /cmd_vel publisher、與 reactive 的 0.6 交錯
        → driver 在 Move/StopMove 間反覆 → 狗原地抖不前進，6/15 真機抓到）。StopMove 由
        act1_forward.sh 的 topic-pub 在 reactive 停發後送（單一 publisher）；danger 則 reactive 自己發 0。"""
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
                "靠 reactive danger-stop + act1_forward topic-pub + 實體 e-stop 兜底！"
            )

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
        """Studio STOP/HOLD → 立刻硬停（不過 busy 鎖）。

        三件事（順序重要）：① 立刻直送 StopMove 1003 給 driver（Go2 立即 halt 仍站立）；
        ② kill 正在跑的 act1_forward.sh，避免它續放 enable=true 讓 reactive 再灌 Move 蓋掉
        StopMove；③ daemon thread 低頻 refresh StopMove + enable=false 軟解除收尾。"""
        self.get_logger().info("Act1 STOP/HOLD (Studio button) → StopMove 1003")
        self._send_stopmove()           # ① 立即硬停（同步、第一優先）
        self._cancel_forward()          # ② 砍 forward subprocess（其 TERM trap 也會 force_stop）
        threading.Thread(target=self._hard_stop_sequence, daemon=True).start()  # ③ refresh + 鎖回

    def _send_stopmove(self):
        """直送一筆 StopMove(1003) 到 /webrtc_req。形狀對齊 event_action_bridge.py。"""
        if self._pub_webrtc is None or WebRtcReq is None:
            self.get_logger().error("無 WebRtcReq publisher → 無法送 StopMove！靠實體 e-stop。")
            return
        req = WebRtcReq()
        req.id = 0
        req.topic = SPORT_TOPIC
        req.api_id = STOP_MOVE_API_ID
        req.parameter = ""
        req.priority = 0
        self._pub_webrtc.publish(req)

    def _hard_stop_sequence(self):
        """低頻 refresh StopMove（防 DataChannel 丟包）+ enable=false 軟解除收尾。"""
        # 第一筆已在 _on_stop_cmd 同步送出；這裡補 refresh（共 STOP_REFRESH_COUNT 筆）。
        for _ in range(max(0, STOP_REFRESH_COUNT - 1)):
            time.sleep(STOP_REFRESH_INTERVAL_S)
            self._send_stopmove()
        self._guarantee_stop()          # reactive enable=false（停其續發 Move）

    def _cancel_forward(self):
        """kill 正在跑的 act1_forward.sh（SIGTERM → bash TERM/EXIT trap → 自身 force_stop）。"""
        p = self._forward_proc
        if p is not None and p.poll() is None:
            try:
                p.terminate()
                self.get_logger().info("已 terminate act1_forward.sh（觸發其 force_stop trap）")
            except Exception as exc:  # noqa: BLE001
                self.get_logger().warn(f"terminate forward subprocess 失敗: {exc}")

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
            self._forward_proc = subprocess.Popen(["bash", ACT1_SCRIPT], env=env)
            deadline = time.monotonic() + ACT1_TIMEOUT_S
            # 前進中主動 LiDAR 防撞閘：自己持續看 /scan，一進 danger zone 直接送 StopMove 1003
            # + kill forward（獨立於 reactive 的 cmd_vel danger-stop，雙保險，不靠單一路徑）。
            while self._forward_proc.poll() is None:
                if time.monotonic() > deadline:
                    self.get_logger().warn("act1_forward.sh 逾時 → kill + StopMove")
                    self._send_stopmove()
                    self._cancel_forward()
                    break
                # 感知失效 fail-safe：前進中 /scan 變 stale（無新鮮回波）= 失去防撞能力，
                # 立即硬停，不繼續盲走到時間到。
                if not self._scan_ready():
                    self.get_logger().warn("前進中 /scan_rplidar stale → fail-safe 硬停")
                    self._send_stopmove()
                    self._cancel_forward()
                    break
                if (self._front_min is not None and self._front_min < DANGER_M):
                    self.get_logger().warn(
                        f"前進中 front={self._front_min:.2f}m < danger({DANGER_M}m) → 硬停"
                    )
                    self._send_stopmove()
                    self._cancel_forward()
                    break
                time.sleep(FORWARD_DANGER_POLL_S)
        except Exception as exc:  # noqa: BLE001
            self.get_logger().error(f"act1_forward.sh 失敗: {exc}")
        finally:
            self._forward_proc = None
            # A-2 保證：只要有放行 motion，不論如何結束（含 timeout / danger / 例外）都 force-stop。
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
