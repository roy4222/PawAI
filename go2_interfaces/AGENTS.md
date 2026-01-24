# PROJECT KNOWLEDGE BASE

## OVERVIEW
Custom ROS2 interface definitions for Go2 (messages and services) built with ament_cmake + rosidl generators.

## STRUCTURE
```
go2_interfaces/
├── msg/            # .msg definitions
├── srv/            # .srv definitions
├── CMakeLists.txt  # rosidl generators + interface targets
└── package.xml
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Message schema | go2_interfaces/msg/ | Add/modify .msg files here
| Service schema | go2_interfaces/srv/ | Add/modify .srv files here
| Build wiring | go2_interfaces/CMakeLists.txt | rosidl_generate_interfaces
| Package deps | go2_interfaces/package.xml | ament + rosidl deps

## CONVENTIONS
- Keep interface file names stable once used by other packages.
- Update both CMakeLists.txt and package.xml when adding interfaces.

## ANTI-PATTERNS
- Do not add new interfaces without updating rosidl generation lists.
- Do not change message field types without checking downstream packages.
