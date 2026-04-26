cmake_minimum_required(VERSION 3.8)
project(go2_interfaces)

# Fix for CMake policy CMP0148 warning
if(POLICY CMP0148)
  cmake_policy(SET CMP0148 OLD)
endif()

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

# find dependencies
find_package(ament_cmake REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(action_msgs REQUIRED)
find_package(rosidl_default_generators REQUIRED)
# uncomment the following section in order to fill in
# further dependencies manually.


rosidl_generate_interfaces(${PROJECT_NAME}
  # Original go2_interfaces messages
  "msg/Go2Cmd.msg"
  "msg/Go2State.msg"
  "msg/Go2Move.msg"
  "msg/Go2RpyCmd.msg"
  "msg/IMU.msg"
  
  # Merged from unitree_go
  "msg/AudioData.msg"
  "msg/BmsCmd.msg"
  "msg/BmsState.msg"
  "msg/Error.msg"
  "msg/Go2FrontVideoData.msg"
  "msg/HeightMap.msg"
  "msg/InterfaceConfig.msg"
  "msg/LidarState.msg"
  "msg/LowCmd.msg"
  "msg/LowState.msg"
  "msg/MotorCmd.msg"
  "msg/MotorCmds.msg"
  "msg/MotorState.msg"
  "msg/MotorStates.msg"
  "msg/PathPoint.msg"
  "msg/Req.msg"
  "msg/Res.msg"
  "msg/SportModeCmd.msg"
  "msg/SportModeState.msg"
  "msg/TimeSpec.msg"
  "msg/UwbState.msg"
  "msg/UwbSwitch.msg"
  "msg/VoxelMapCompressed.msg"
  "msg/VoxelHeightMapState.msg"
  "msg/WebRtcReq.msg"
  "msg/WirelessController.msg"

  # Custom services
  "srv/MoveForDuration.srv"
  "srv/Cancel.srv"

  # Custom actions (nav_capability platform)
  "action/GotoRelative.action"
  "action/GotoNamed.action"
  "action/RunRoute.action"
  "action/LogPose.action"
  DEPENDENCIES builtin_interfaces geometry_msgs action_msgs
)


ament_package()
