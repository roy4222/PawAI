# PROJECT KNOWLEDGE BASE

## OVERVIEW
Isaac Sim digital twin integration for Go2/G1, including ROS2 bridge utilities and simulation launch scripts.

## STRUCTURE
```
go2_omniverse/
├── main.py            # Top-level entry
├── omniverse_sim.py   # Simulation driver
├── ros2.py            # ROS2 bridge/publishers
├── run_sim.sh         # Go2 sim launcher
├── run_sim_g1.sh      # G1 sim launcher
├── Isaac_sim/         # Assets/configs
└── robots/            # Robot definitions
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Sim entry | go2_omniverse/main.py | Primary entry script
| Sim runtime | go2_omniverse/omniverse_sim.py | Orchestration
| ROS2 bridge | go2_omniverse/ros2.py | ROS2 publishers
| Launch scripts | go2_omniverse/run_sim.sh | Shell entrypoints

## CONVENTIONS
- Shell launchers are the supported entry path for Isaac Sim runs.
- ROS2 node name defaults to `go2_driver_node` in the bridge.

## ANTI-PATTERNS
- Do not rename run scripts without updating README references.
