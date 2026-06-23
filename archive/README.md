# Archive — 過期區 / Deprecated Zone

This directory holds code, packages and scripts that are **no longer part of the
active PawAI system** but are kept for historical reference and git-history
continuity. Nothing here is built or run by the main demo.

- `COLCON_IGNORE` marks this whole tree as invisible to `colcon build` / `colcon test`.
- Everything was moved here with `git mv`, so full history is preserved
  (`git log --follow archive/<path>`).
- Internal archived documentation is not included in the public tree.

## Contents

### `packages/`
ROS2 packages that were superseded or never used by any active demo.

| Package | Why archived |
|---------|--------------|
| `lidar_processor` | Python pipeline for the Go2 **built-in** voxel LiDAR (`/point_cloud2`). Off by default in `robot.launch.py` and bypassed by every SLAM/Nav demo, which use the external RPLIDAR (`sllidar` → `/scan_rplidar`). Inherited from the upstream `go2_ros2_sdk` fork. |
| `lidar_processor_cpp` | C++ (PCL) rewrite of the same built-in-LiDAR pipeline. Never launched, never referenced by any active package or script. |

> Restoring: `git mv archive/packages/<name> <name>` and re-add its launch wiring.
