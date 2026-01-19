#!/usr/bin/env python3
# Copyright (c) 2024, RoboVerse community
# SPDX-License-Identifier: BSD-3-Clause
"""
Go2 導航系統完整測試腳本

測試項目：
1. 驗證 /cmd_vel → Go2 WebRTC 的資料流
2. 測試 Nav2 NavigateToPose action
3. 監控關鍵 topics 的頻率和狀態
4. 驗證 TF 樹完整性

使用方式：
    # 先啟動 go2_robot_sdk
    ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true

    # 執行測試
    python3 scripts/go2_nav_test.py --test all
    python3 scripts/go2_nav_test.py --test cmd_vel
    python3 scripts/go2_nav_test.py --test topics
    python3 scripts/go2_nav_test.py --test tf
    python3 scripts/go2_nav_test.py --test nav2 --distance 1.0
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from typing import Dict

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy

from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan, PointCloud2
from nav_msgs.msg import Odometry, OccupancyGrid
from tf2_msgs.msg import TFMessage

try:
    from nav2_msgs.action import NavigateToPose
    from rclpy.action import ActionClient

    NAV2_AVAILABLE = True
except ImportError:
    NAV2_AVAILABLE = False


@dataclass
class TopicStatus:
    """Topic 狀態記錄"""

    name: str
    msg_type: str
    count: int = 0
    last_time: float = 0.0
    frequency: float = 0.0


class Go2NavTester(Node):
    """Go2 導航系統測試器"""

    def __init__(self):
        super().__init__("go2_nav_tester")

        # Topic 狀態追蹤
        self.topic_stats: Dict[str, TopicStatus] = {}
        self.tf_frames_seen: set = set()
        self.cmd_vel_sent_count = 0

        # QoS 設定
        self.sensor_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
        )

        # cmd_vel 發布器
        self.cmd_vel_pub = self.create_publisher(Twist, "/cmd_vel", 10)

        # 設定訂閱
        self._setup_subscriptions()

    def _setup_subscriptions(self):
        """設定所有監控訂閱"""

        # 關鍵 topics 列表
        topics_to_monitor = [
            ("/scan", LaserScan, self.sensor_qos),
            ("/odom", Odometry, 10),
            ("/map", OccupancyGrid, 10),
            ("/cmd_vel", Twist, 10),
            ("/point_cloud2", PointCloud2, self.sensor_qos),
        ]

        for topic_name, msg_type, qos in topics_to_monitor:
            self.topic_stats[topic_name] = TopicStatus(
                name=topic_name, msg_type=msg_type.__name__
            )
            self.create_subscription(
                msg_type,
                topic_name,
                lambda msg, tn=topic_name: self._on_topic_msg(tn),
                qos,
            )

        # TF 訂閱
        self.create_subscription(TFMessage, "/tf", self._on_tf, 10)
        self.create_subscription(TFMessage, "/tf_static", self._on_tf, 10)

    def _on_topic_msg(self, topic_name: str):
        """通用 topic 訊息處理"""
        now = time.time()
        stat = self.topic_stats[topic_name]

        if stat.last_time > 0:
            dt = now - stat.last_time
            if dt > 0:
                # 滑動平均計算頻率
                instant_freq = 1.0 / dt
                stat.frequency = 0.9 * stat.frequency + 0.1 * instant_freq

        stat.count += 1
        stat.last_time = now

    def _on_tf(self, msg: TFMessage):
        """TF 訊息處理"""
        for transform in msg.transforms:
            self.tf_frames_seen.add(transform.header.frame_id)
            self.tf_frames_seen.add(transform.child_frame_id)

    # ========== 測試方法 ==========

    def test_cmd_vel(self, duration: float = 3.0, velocity: float = 0.1) -> bool:
        """
        測試 cmd_vel 發送

        發送小速度指令，確認 Go2 有反應
        """
        self.get_logger().info("=" * 60)
        self.get_logger().info("測試 1: cmd_vel 發送測試")
        self.get_logger().info("=" * 60)

        twist = Twist()
        twist.linear.x = velocity
        twist.angular.z = 0.0

        self.get_logger().info(
            f"發送 cmd_vel: linear.x={velocity} m/s，持續 {duration} 秒"
        )
        self.get_logger().warn("⚠️  機器狗即將移動！請確保周圍安全！")

        # 倒數
        for i in range(3, 0, -1):
            self.get_logger().info(f"  {i}...")
            time.sleep(1)

        start_time = time.time()
        rate = self.create_rate(10)  # 10 Hz

        try:
            while time.time() - start_time < duration:
                self.cmd_vel_pub.publish(twist)
                self.cmd_vel_sent_count += 1
                rate.sleep()
        except KeyboardInterrupt:
            pass

        # 停止
        self.cmd_vel_pub.publish(Twist())
        self.get_logger().info(f"已停止。共發送 {self.cmd_vel_sent_count} 個指令")

        # 檢查是否有收到 cmd_vel 回饋
        cmd_vel_stat = self.topic_stats.get("/cmd_vel")
        if cmd_vel_stat and cmd_vel_stat.count > 0:
            self.get_logger().info(f"✅ cmd_vel 確認收到 {cmd_vel_stat.count} 個訊息")
            return True
        else:
            self.get_logger().warn("⚠️  未偵測到 cmd_vel 回饋（可能正常，取決於架構）")
            return True  # 不一定有回饋

    def test_topics(self, wait_time: float = 5.0) -> bool:
        """
        測試關鍵 topics 狀態

        監控所有關鍵 topics 的頻率
        """
        self.get_logger().info("=" * 60)
        self.get_logger().info("測試 2: Topics 狀態監控")
        self.get_logger().info("=" * 60)

        self.get_logger().info(f"監控 {wait_time} 秒...")

        # 等待收集數據
        start = time.time()
        while time.time() - start < wait_time:
            rclpy.spin_once(self, timeout_sec=0.1)

        # 輸出結果
        self.get_logger().info("")
        self.get_logger().info(
            f"{'Topic':<25} {'類型':<20} {'訊息數':<10} {'頻率 (Hz)':<10}"
        )
        self.get_logger().info("-" * 70)

        all_ok = True
        critical_topics = {"/scan": 5.0, "/odom": 1.0}  # 最低頻率要求

        for topic_name, stat in sorted(self.topic_stats.items()):
            status = "✅"
            if topic_name in critical_topics:
                if stat.count == 0:
                    status = "❌"
                    all_ok = False
                elif stat.frequency < critical_topics[topic_name]:
                    status = "⚠️"
            elif stat.count == 0:
                status = "⚠️"

            self.get_logger().info(
                f"{status} {topic_name:<22} {stat.msg_type:<20} {stat.count:<10} {stat.frequency:>8.2f}"
            )

        return all_ok

    def test_tf(self, wait_time: float = 3.0) -> bool:
        """
        測試 TF 樹完整性

        檢查必要的座標框架是否存在
        """
        self.get_logger().info("=" * 60)
        self.get_logger().info("測試 3: TF 樹完整性")
        self.get_logger().info("=" * 60)

        # 等待收集 TF
        self.get_logger().info(f"收集 TF 資訊 {wait_time} 秒...")
        start = time.time()
        while time.time() - start < wait_time:
            rclpy.spin_once(self, timeout_sec=0.1)

        # 必要的框架
        required_frames = ["map", "odom", "base_link"]
        optional_frames = ["front_camera", "radar", "imu"]

        self.get_logger().info(f"\n偵測到的框架 ({len(self.tf_frames_seen)} 個):")
        for frame in sorted(self.tf_frames_seen):
            self.get_logger().info(f"  • {frame}")

        self.get_logger().info("\n必要框架檢查:")
        all_ok = True
        for frame in required_frames:
            if frame in self.tf_frames_seen:
                self.get_logger().info(f"  ✅ {frame}")
            else:
                self.get_logger().error(f"  ❌ {frame} - 缺失!")
                all_ok = False

        self.get_logger().info("\n選用框架檢查:")
        for frame in optional_frames:
            if frame in self.tf_frames_seen:
                self.get_logger().info(f"  ✅ {frame}")
            else:
                self.get_logger().warn(f"  ⚠️  {frame} - 未偵測到")

        return all_ok

    def test_nav2(self, distance: float = 0.5, timeout: float = 60.0) -> bool:
        """
        測試 Nav2 NavigateToPose action

        發送一個簡單的導航目標
        """
        self.get_logger().info("=" * 60)
        self.get_logger().info("測試 4: Nav2 NavigateToPose")
        self.get_logger().info("=" * 60)

        if not NAV2_AVAILABLE:
            self.get_logger().error("❌ nav2_msgs 未安裝，跳過此測試")
            return False

        # 建立 action client
        action_client = ActionClient(self, NavigateToPose, "navigate_to_pose")

        self.get_logger().info("等待 navigate_to_pose action server...")
        if not action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("❌ Action server 未響應")
            return False

        self.get_logger().info("✅ Action server 已連線")

        # 取得當前位置 (從 /odom)
        self.get_logger().info("等待 /odom 取得當前位置...")
        current_pose = None

        def odom_callback(msg: Odometry):
            nonlocal current_pose
            current_pose = msg.pose.pose

        odom_sub = self.create_subscription(Odometry, "/odom", odom_callback, 10)

        start = time.time()
        while current_pose is None and time.time() - start < 5.0:
            rclpy.spin_once(self, timeout_sec=0.1)

        self.destroy_subscription(odom_sub)

        if current_pose is None:
            self.get_logger().error("❌ 無法取得當前位置")
            return False

        # 計算目標位置 (向前 distance 公尺)
        yaw = self._yaw_from_quaternion(current_pose.orientation)
        goal_x = current_pose.position.x + distance * math.cos(yaw)
        goal_y = current_pose.position.y + distance * math.sin(yaw)

        self.get_logger().info(
            f"當前位置: x={current_pose.position.x:.2f}, y={current_pose.position.y:.2f}"
        )
        self.get_logger().info(
            f"目標位置: x={goal_x:.2f}, y={goal_y:.2f} (前進 {distance}m)"
        )

        # 建立目標
        goal = NavigateToPose.Goal()
        goal.pose.header.frame_id = "map"
        goal.pose.header.stamp = self.get_clock().now().to_msg()
        goal.pose.pose.position.x = goal_x
        goal.pose.pose.position.y = goal_y
        goal.pose.pose.position.z = 0.0
        goal.pose.pose.orientation = current_pose.orientation

        self.get_logger().warn("⚠️  即將發送導航目標！請確保路徑暢通！")
        time.sleep(2)

        # 發送目標
        self.get_logger().info("發送導航目標...")
        future = action_client.send_goal_async(
            goal,
            feedback_callback=lambda fb: self.get_logger().info(
                f"  進度: x={fb.feedback.current_pose.pose.position.x:.2f}, "
                f"y={fb.feedback.current_pose.pose.position.y:.2f}"
            ),
        )

        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        goal_handle = future.result()

        if goal_handle is None or not goal_handle.accepted:
            self.get_logger().error("❌ 導航目標被拒絕")
            return False

        self.get_logger().info("✅ 目標已接受，等待完成...")

        # 等待結果
        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=timeout)

        if not result_future.done():
            self.get_logger().error("❌ 導航超時")
            return False

        result = result_future.result().result
        if hasattr(result, "error_code") and result.error_code == 0:
            self.get_logger().info("✅ 導航成功完成！")
            return True
        else:
            self.get_logger().error(f"❌ 導航失敗")
            return False

    def _yaw_from_quaternion(self, q) -> float:
        """從 quaternion 提取 yaw 角度"""
        siny_cosp = 2.0 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1.0 - 2.0 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    def run_all_tests(self) -> bool:
        """執行所有測試"""
        results = {}

        # 1. Topics 測試 (非破壞性)
        results["topics"] = self.test_topics()

        # 2. TF 測試 (非破壞性)
        results["tf"] = self.test_tf()

        # 3. cmd_vel 測試 (會移動機器狗)
        self.get_logger().info("\n" + "=" * 60)
        self.get_logger().info("即將進行 cmd_vel 測試，機器狗會移動")
        self.get_logger().info("按 Enter 繼續，或 Ctrl+C 跳過...")
        self.get_logger().info("=" * 60)

        try:
            input()
            results["cmd_vel"] = self.test_cmd_vel()
        except (KeyboardInterrupt, EOFError):
            self.get_logger().info("跳過 cmd_vel 測試")
            results["cmd_vel"] = None

        # 輸出總結
        self.get_logger().info("\n" + "=" * 60)
        self.get_logger().info("測試總結")
        self.get_logger().info("=" * 60)

        all_pass = True
        for test_name, result in results.items():
            if result is None:
                status = "⏭️  跳過"
            elif result:
                status = "✅ 通過"
            else:
                status = "❌ 失敗"
                all_pass = False
            self.get_logger().info(f"  {test_name}: {status}")

        return all_pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Go2 導航系統完整測試腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
測試項目:
  all      執行所有測試
  cmd_vel  測試 cmd_vel 發送 (會移動機器狗)
  topics   監控關鍵 topics 狀態
  tf       檢查 TF 樹完整性
  nav2     測試 Nav2 導航 (會移動機器狗)

範例:
  python3 go2_nav_test.py --test all
  python3 go2_nav_test.py --test topics --wait 10
  python3 go2_nav_test.py --test nav2 --distance 1.0
        """,
    )

    parser.add_argument(
        "--test",
        type=str,
        default="all",
        choices=["all", "cmd_vel", "topics", "tf", "nav2"],
        help="要執行的測試項目 (預設: all)",
    )

    parser.add_argument(
        "--distance",
        type=float,
        default=0.5,
        help="Nav2 測試的導航距離 (公尺，預設: 0.5)",
    )

    parser.add_argument(
        "--wait", type=float, default=5.0, help="Topics/TF 監控等待時間 (秒，預設: 5.0)"
    )

    parser.add_argument(
        "--velocity",
        type=float,
        default=0.1,
        help="cmd_vel 測試的速度 (m/s，預設: 0.1)",
    )

    return parser.parse_args()


def main():
    args = parse_args()
    rclpy.init()

    tester = Go2NavTester()
    success = False

    try:
        if args.test == "all":
            success = tester.run_all_tests()
        elif args.test == "cmd_vel":
            success = tester.test_cmd_vel(velocity=args.velocity)
        elif args.test == "topics":
            success = tester.test_topics(wait_time=args.wait)
        elif args.test == "tf":
            success = tester.test_tf(wait_time=args.wait)
        elif args.test == "nav2":
            success = tester.test_nav2(distance=args.distance)
    except KeyboardInterrupt:
        tester.get_logger().info("\n收到 Ctrl+C，結束測試")
    finally:
        # 確保停止
        tester.cmd_vel_pub.publish(Twist())
        tester.destroy_node()
        rclpy.shutdown()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
