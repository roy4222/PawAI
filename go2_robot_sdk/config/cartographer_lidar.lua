-- cartographer_lidar.lua
-- Target: Jetson Orin Nano + RPLIDAR A2M12, **完全不依賴 Go2 任何感測**
-- Use case: 4-6m 室內客廳, Go2 推走 ≤0.10 m/s, 2D mapping
-- Reference: Kabilankb 2024 Jetson Nano + RPLIDAR + Humble + Cartographer post
--
-- 關鍵變更（v2 → v3 切純 scan-matching）：
-- v2 用 use_odometry=true + Go2 odom，但 Go2 driver /odom 來源是內建 utlidar SLAM（5Hz/18%覆蓋
-- 爛雷達跑出來的 pose），noise 大導致 cartographer pose graph 拉壞 → starburst 失真
-- v3 改純 scan-matching：不訂閱外部 odom，cartographer 自己用 real_time_correlative_scan_matcher
-- 算 pose 變化，own 整條 map→odom→base_link TF chain，不需要任何外部 odom 訊號
--
-- ⚠️ 啟動時 Go2 driver 必須關閉，否則兩邊都發 odom→base_link 會 TF 衝突

include "map_builder.lua"
include "trajectory_builder.lua"

options = {
  map_builder = MAP_BUILDER,
  trajectory_builder = TRAJECTORY_BUILDER,

  -- ===== Frame / TF =====
  map_frame  = "map",
  tracking_frame   = "base_link",  -- 雷達掛在 base_link 上，沒獨立 imu_link
  published_frame  = "base_link",  -- cartographer 自己 own 整條 TF chain
  odom_frame = "odom",
  provide_odom_frame = true,       -- v3: cartographer 自己發 odom→base_link（純 scan-matching 估計）
  publish_frame_projected_to_2d = true,

  -- ===== Sensor inputs =====
  use_odometry = false,            -- v3: 不訂閱外部 odom，純 RPLIDAR scan-matching 自算 pose
  use_nav_sat  = false,
  use_landmarks = false,
  num_laser_scans = 1,             -- 一支 RPLIDAR A2M12，topic 預設 /scan，啟動命令 remap /scan_rplidar
  num_multi_echo_laser_scans = 0,
  num_subdivisions_per_laser_scan = 1,  -- A2M12 10Hz 720pt，掃描期短，不切片
  num_point_clouds = 0,

  -- ===== Timing =====
  lookup_transform_timeout_sec = 0.2,   -- TF buffer 容忍，Go2 odom 50Hz 算夠快
  submap_publish_period_sec = 0.3,
  pose_publish_period_sec = 5e-3,       -- 200 Hz pose
  trajectory_publish_period_sec = 30e-3,

  -- ===== Sampling ratios (全收) =====
  rangefinder_sampling_ratio = 1.,
  odometry_sampling_ratio = 1.,
  fixed_frame_pose_sampling_ratio = 1.,
  imu_sampling_ratio = 1.,
  landmarks_sampling_ratio = 1.,
}

-- ===== 2D mode =====
MAP_BUILDER.use_trajectory_builder_2d = true
MAP_BUILDER.num_background_threads = 4    -- Orin Nano 6 cores, 留 2 給 ROS2/驅動

-- ===== Trajectory builder 2D (RPLIDAR A2M12) =====
TRAJECTORY_BUILDER_2D.min_range = 0.20    -- Go2 機身/腳會在 <0.5m 出現，0.20 buffer 過濾掉腳邊雜訊
TRAJECTORY_BUILDER_2D.max_range = 8.0     -- A2M12 物理 16m，但室內 8m 之外噪聲多
TRAJECTORY_BUILDER_2D.missing_data_ray_length = 5.0  -- inf 的 ray 當 5m 空洞處理（A2M12 .inf 走這條）
TRAJECTORY_BUILDER_2D.use_imu_data = false
TRAJECTORY_BUILDER_2D.use_online_correlative_scan_matching = true   -- 純 scan-match 模式必開
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.linear_search_window = 0.1
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.angular_search_window = math.rad(20.)  -- v3: 20° 給轉彎時更大搜尋空間（無 odom prior 時必需）
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.translation_delta_cost_weight = 10.
TRAJECTORY_BUILDER_2D.real_time_correlative_scan_matcher.rotation_delta_cost_weight = 1e-1
TRAJECTORY_BUILDER_2D.motion_filter.max_angle_radians = math.rad(0.2)
TRAJECTORY_BUILDER_2D.num_accumulated_range_data = 1

-- ===== 小空間調參 =====
TRAJECTORY_BUILDER_2D.submaps.num_range_data = 90  -- 4-6m 客廳 9 秒一個 submap
TRAJECTORY_BUILDER_2D.submaps.grid_options_2d.resolution = 0.05  -- 5cm/cell

-- ===== Pose graph (loop closure) =====
POSE_GRAPH.optimize_every_n_nodes = 35
POSE_GRAPH.constraint_builder.min_score = 0.65
POSE_GRAPH.constraint_builder.global_localization_min_score = 0.65
POSE_GRAPH.optimization_problem.huber_scale = 1e2

return options
