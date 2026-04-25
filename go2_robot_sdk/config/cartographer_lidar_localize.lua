-- cartographer_lidar_localize.lua
-- Pure localization mode: 載入既有 .pbstream + 不再建大 map，只跟舊 submap 做 constraint
-- 基底 = cartographer_lidar.lua + 加 pure_localization_trimmer
-- 啟動命令需帶 -load_state_filename /home/jetson/maps/home_living_room.pbstream

include "cartographer_lidar.lua"  -- 重用 mapping 配置（use_odometry=false, provide_odom_frame=true）

-- ===== Pure localization 觸發 =====
-- max_submaps_to_keep: 只保留 N 個新 submap，避免在 localization mode 持續成長
TRAJECTORY_BUILDER.pure_localization_trimmer = {
  max_submaps_to_keep = 3,
}

-- ===== 提高 loop closure 頻率 =====
-- pure-localization 需要快速跟舊 submap 做 constraint 才能收斂
POSE_GRAPH.optimize_every_n_nodes = 20
POSE_GRAPH.constraint_builder.sampling_ratio = 0.3

return options
