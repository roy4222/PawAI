# PROJECT KNOWLEDGE BASE

**Generated:** 2026-01-24 08:04:25Z
**Commit:** ec525f4
**Branch:** main

## OVERVIEW
ROS2 Humble workspace for Unitree Go2 with Clean Architecture driver, perception, Nav2/SLAM tooling, and MCP-based robot control. Primary languages are Python (ROS2 nodes) and C++ (msg defs + LiDAR processor).

## STRUCTURE
```
./
├── go2_robot_sdk/          # Main Go2 driver + launch/config/URDF
├── go2_interfaces/         # Custom ROS2 msg/srv/action definitions
├── lidar_processor/        # Python LiDAR aggregation/filters
├── lidar_processor_cpp/    # C++ LiDAR processor (PCL)
├── coco_detector/          # TorchVision COCO detector node
├── speech_processor/       # TTS + audio services
├── src/search_logic/       # Simple patrol/Nav2 test package
├── ros-mcp-server/         # MCP server (standalone Python package)
├── go2_omniverse/           # Isaac Sim / digital twin integration
├── docs/                   # Project docs and plans
└── scripts/                # Test/diagnostic scripts
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Go2 driver node | go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py | Clean Architecture entry point
| Driver entry script | go2_robot_sdk/go2_robot_sdk/main.py | Async spin + robot connections
| Launch & runtime config | go2_robot_sdk/launch, go2_robot_sdk/config | launch changes require restart only
| Custom ROS2 msgs | go2_interfaces/msg, go2_interfaces/srv | CMake + rosidl generators
| LiDAR processing | lidar_processor/ or lidar_processor_cpp/ | Python vs C++ implementations
| Patrol/Nav2 tests | src/search_logic/search_logic | simple_patrol_node + nav2_client
| MCP server | ros-mcp-server/server.py | Console script entry point
| Simulation (Isaac) | go2_omniverse/ | External sim tooling

## CONVENTIONS
- Python line length 100; flake8 is used in ROS2 packages; ruff in `ros-mcp-server`.
- SPDX license header required in Go2 ROS2 Python/C++ sources.
- Clean Architecture boundaries in `go2_robot_sdk` (domain has no ROS2 deps).
- Package installs use `uv pip install`, not `pip install`.

## ANTI-PATTERNS (THIS PROJECT)
- Do not add ROS2 dependencies to `go2_robot_sdk/go2_robot_sdk/domain`.
- Do not suppress exceptions silently; log with ROS2 logger or re-raise.
- Do not use `pip install` directly; use `uv pip install`.

## UNIQUE STYLES
- Multi-robot mode uses comma-separated `ROBOT_IP` env var and namespaced topics.
- Default camera frame in URDF is `front_camera` (not `camera_link`).

## COMMANDS
```bash
# Source ROS2 environment
source /opt/ros/humble/setup.bash
source install/setup.bash

# Build
colcon build
colcon build --packages-select go2_robot_sdk
colcon build --packages-select lidar_processor_cpp

# Test
colcon test --packages-select search_logic
colcon test-result --verbose

# Lint/format
flake8 --max-line-length=100 go2_robot_sdk/
ament_uncrustify --check lidar_processor_cpp/src/
cd ros-mcp-server && ruff check . && ruff format --check .
```

## NOTES
- Launch file changes do not require rebuild; just restart launch.
- `ROBOT_IP` and `CONN_TYPE` are required for runtime.



## AI INTERACTION GUIDELINES

### Requirement-First Questioning Pattern (需求導向提問模式)

When gathering research requirements from users, follow this **non-assumptive approach** :

**DON'T:**
- Prescribe specific models, libraries, or technologies
- Assume implementation details
- Ask questions that require local testing or code review

**DO:**
- Ask for the **desired outcome** in plain language
- Ask what exists in **open-source communities**
- Ask for **common practices** and **recommendations**
- Focus on **what's possible** rather than **how to implement**

**Good Examples:**
```
❌ "Use MediaPipe for face detection" (prescribes solution)
✅ "What open-source options exist for real-time face detection on edge devices?"

❌ "Check if D435 depth sync works on Jetson" (requires local testing)
✅ "What are common issues when using D435 with Jetson in ROS2 projects?"

❌ "Implement Whisper Tiny for ASR" (prescribes implementation)
✅ "What ASR models do robot projects commonly use for Chinese speech recognition?"
```

**Template Structure for Research Questions:**
1. **Desired effect** (想要的效果): What should the system achieve?
2. **Community practices** (業界做法): How do others solve this?
3. **Available options** (開源選擇): What open-source solutions exist?
4. **Common pitfalls** (常見問題): What issues should be aware of?

This pattern ensures research questions are **actionable by external AI/tools** rather than requiring local codebase inspection.