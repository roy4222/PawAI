"""一鍵啟 nav_capability 4 個 node。

啟動：
  ros2 launch nav_capability nav_capability.launch.py
  ros2 launch nav_capability nav_capability.launch.py map_id:=classroom_5_13

Node 列表:
  nav_action_server_node — /nav/goto_relative + /nav/goto_named + /odom watchdog
  route_runner_node      — /nav/run_route + /nav/{pause,resume,cancel}
  log_pose_node          — /log_pose (write to named_poses or routes JSON)
  state_broadcaster_node — heartbeat + status + safety JSON @ 10Hz

註：本 launch 不啟 Nav2 / AMCL / map_server / driver / mux / reactive_stop。
   實機驗收用 scripts/start_nav_capability_demo_tmux.sh 把所有層一起起。
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory("nav_capability")
    default_named = os.path.join(pkg_share, "config", "named_poses", "sample.json")
    default_routes = os.path.join(pkg_share, "config", "routes")

    named_arg = DeclareLaunchArgument(
        "named_poses_file",
        default_value=default_named,
        description="Path to named_poses JSON; nav_action_server reads, log_pose writes here",
    )
    routes_arg = DeclareLaunchArgument(
        "routes_dir",
        default_value=default_routes,
        description="Directory of route JSONs; route_runner reads, log_pose appends here",
    )
    map_id_arg = DeclareLaunchArgument(
        "map_id",
        default_value="unknown_map",
        description="Map ID stamp written by log_pose when creating new JSONs",
    )

    nav_action = Node(
        package="nav_capability",
        executable="nav_action_server_node",
        name="nav_action_server_node",
        output="screen",
        parameters=[{
            "named_poses_file": LaunchConfiguration("named_poses_file"),
        }],
    )
    route_runner = Node(
        package="nav_capability",
        executable="route_runner_node",
        name="route_runner_node",
        output="screen",
        parameters=[{
            "routes_dir": LaunchConfiguration("routes_dir"),
        }],
    )
    log_pose = Node(
        package="nav_capability",
        executable="log_pose_node",
        name="log_pose_node",
        output="screen",
        parameters=[{
            "named_poses_file": LaunchConfiguration("named_poses_file"),
            "routes_dir": LaunchConfiguration("routes_dir"),
            "map_id": LaunchConfiguration("map_id"),
        }],
    )
    state_bcast = Node(
        package="nav_capability",
        executable="state_broadcaster_node",
        name="state_broadcaster_node",
        output="screen",
    )

    return LaunchDescription([
        named_arg, routes_arg, map_id_arg,
        nav_action, route_runner, log_pose, state_bcast,
    ])
