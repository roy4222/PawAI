# PROJECT KNOWLEDGE BASE

## OVERVIEW
Main Go2 ROS2 driver package implemented with Clean Architecture. Provides the driver node plus snapshot and move services, plus launch/config/URDF assets.

## STRUCTURE
```
go2_robot_sdk/
├── go2_robot_sdk/
│   ├── application/      # Use cases/services
│   ├── domain/           # Pure domain entities/interfaces
│   ├── infrastructure/   # WebRTC, ROS2 adapters
│   ├── presentation/     # ROS2 node entry points
│   ├── main.py            # Driver entry
│   ├── snapshot_service.py
│   └── move_service.py
├── launch/               # robot.launch.py and related
├── config/               # nav2/slam/twist_mux params
├── urdf/                 # Go2 URDF variants
└── setup.py
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Driver node entry | go2_robot_sdk/go2_robot_sdk/presentation/go2_driver_node.py | Main ROS2 Node class
| Async main | go2_robot_sdk/go2_robot_sdk/main.py | Starts ROS2 + robot loops
| Snapshot service | go2_robot_sdk/go2_robot_sdk/snapshot_service.py | /capture_snapshot service
| Move service | go2_robot_sdk/go2_robot_sdk/move_service.py | Timed motion service
| WebRTC adapter | go2_robot_sdk/go2_robot_sdk/infrastructure/webrtc/ | Robot connection stack
| ROS2 publishers | go2_robot_sdk/go2_robot_sdk/infrastructure/ros2/ | Publish bridge

## CONVENTIONS
- SPDX headers required in Python sources under this package.
- Entry points are defined in `go2_robot_sdk/setup.py` (console_scripts).
- Keep domain layer free of ROS2 imports.

## ANTI-PATTERNS
- Do not import rclpy/ROS2 types in `go2_robot_sdk/go2_robot_sdk/domain`.
- Do not bypass application services to call infrastructure directly from presentation.
