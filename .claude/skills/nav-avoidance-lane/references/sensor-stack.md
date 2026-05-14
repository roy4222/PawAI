# Sensor Stack — Nav Avoidance Lane

LiDAR / D435 / TF 校正、安裝座標、udev rule、檢測指令。

## RPLIDAR A2M12

### 硬體規格
- 接口：USB（透過 USB-Serial 轉換板）
- Baud rate：256000
- 掃描頻率：10-15 Hz（Standard mode）
- 範圍：0.15 - 12 m
- 角度解析度：~0.9°
- 點數：每幀 1800 點（angle_compensate=true）

### 安裝座標（base_link 為 Go2 機身中心）
```
LiDAR 在 base_link 前 17.5cm，上方 18cm，反裝（yaw=π）
─────────────────
x = 0.175 m  (前)
y = 0      m
z = 0.18  m  (上)
yaw = 3.14159 (反裝補償)
```

對應 static TF launch：
```bash
ros2 run tf2_ros static_transform_publisher \
  --x 0.175 --y 0 --z 0.18 --yaw 3.14159 \
  --frame-id base_link --child-frame-id laser
```

### udev rule（`/dev/rplidar` symlink）

```
# /etc/udev/rules.d/99-rplidar.rules
KERNEL=="ttyUSB*", ATTRS{idVendor}=="10c4", ATTRS{idProduct}=="ea60", \
  MODE="0666", SYMLINK+="rplidar"
```

確認：
```bash
ls -la /dev/rplidar  # 應指向 /dev/ttyUSB0 或類似
ls /dev/serial/by-id/ | grep -i cp210  # CP210x USB-Serial chip
```

### 啟動驗證

```bash
# Hz
ros2 topic hz /scan_rplidar
# 應看到 average rate: ~10-12 Hz

# 點數
ros2 topic echo /scan_rplidar --once | grep -E "ranges:|count" | head
# 約 1800 點

# valid ratio（非 inf 點數）
ros2 topic echo /scan_rplidar --once | python3 -c "
import sys, ast
data = sys.stdin.read()
ranges = ast.literal_eval(data.split('ranges:')[1].split('intensities:')[0].strip())
valid = [r for r in ranges if 0.15 <= r <= 12.0]
print(f'valid: {len(valid)}/{len(ranges)} ({len(valid)/len(ranges)*100:.1f}%)')
"
# 5/11 baseline: 94% valid
```

## D435 RealSense

### 硬體規格
- 接口：USB 3.0
- 解析度：建議 640x480 @ 15 fps（USB 頻寬考量）
- 模式：color + aligned_depth_to_color

### 啟動 launch（capability mode 自動帶）

```bash
ros2 launch realsense2_camera rs_launch.py \
  enable_depth:=true \
  pointcloud.enable:=false \
  depth_module.depth_profile:=640x480x15 \
  rgb_camera.color_profile:=640x480x15 \
  align_depth.enable:=true
```

### 啟動驗證

```bash
# color Hz
ros2 topic hz /camera/camera/color/image_raw  # ~30 Hz

# aligned depth Hz
ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw  # ~30 Hz

# depth_safety ROI 中心距離
ros2 topic echo /capability/depth_clear --once
# 應有 data: true（中心 1.0m 內無物體時）
```

### USB 偵測

```bash
lsusb | grep -i 'realsense\|intel'
# Bus 002 Device 005: ID 8086:0b07 Intel Corp. RealSense Depth Camera 435
```

## TF 樹完整圖

```
map (mapping = cartographer 發；amcl/capability = AMCL 發)
 │
 │ AMCL or carto pose estimate
 ↓
odom (mapping = cartographer 發；其他 = go2_driver 發)
 │
 │ wheel/IMU odometry from Go2
 ↓
base_link  (Go2 機身中心)
 │
 ├── static ─→ laser   (RPLIDAR)
 │            x=0.175, z=0.18, yaw=π
 │
 ├── static ─→ camera_link  (D435)
 │            (位置依實際安裝校正)
 │
 └── (其他 perception sensors)
```

驗證 TF：
```bash
# 完整樹
ros2 run tf2_tools view_frames
evince frames.pdf

# 即時看
ros2 run tf2_ros tf2_echo base_link laser
ros2 run tf2_ros tf2_echo map base_link  # 需 amcl 收斂後才有
```

## GO2_PUBLISH_ODOM_TF env 切換

| Mode | env 設定 | 為什麼 |
|---|---|---|
| mapping | `GO2_PUBLISH_ODOM_TF=0` | cartographer 自己 own odom→base_link，driver 不能搶 |
| amcl/capability/fallback | 無 (預設 1) | AMCL 用 driver 發的 odom→base_link |
| brain (任何 mode) | 無 (預設 1) | 跟 nav 共用 |

⚠️ 切 mode 時要清乾淨 driver 重啟，否則 env 不生效。

## 已知陷阱

1. **`/scan_rplidar` vs `/scan` 雙 publisher**：sllidar_node 預設 publish 到 `/scan`；
   driver 也會 publish Go2 內建 LiDAR 到 `/scan`（如果 enable_lidar=true）→ 衝突。
   **解法**：sllidar 啟動時 remap `/scan:=/scan_rplidar`，driver 啟動時 enable_lidar=false。
   
2. **多個 driver instance 殘留**：`pkill python3` 只殺 launch parent，C++ 子 process 殘留 → 雙 odom publisher → AMCL 混亂。**解法**：用 cleanup.sh 的 `pkill -9 -f` 逐一清。

3. **D435 USB 頻寬爆**：640x480x30 color + depth 對某些 USB hub 太吃 → camera disconnect。**解法**：降到 15 fps。

4. **slam_toolbox 永久棄用**：ARM64 + Humble + RPLIDAR 已知 bug（Mapper FATAL ERROR）→ 只用 cartographer。
