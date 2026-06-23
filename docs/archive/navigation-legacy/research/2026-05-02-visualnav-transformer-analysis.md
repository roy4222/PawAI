# VisualNav-Transformer (GNM/ViNT/NoMaD) 對 PawAI 的分析

- **Source**: https://github.com/robodhruv/visualnav-transformer
- **Commit**: `dca79815b704e5aa9c6bdc3082351f9e3b2848c2`
- **Date**: 2026-05-02

## 1. 模型定位 vs PawAI

GNM/ViNT/NoMaD 是 Berkeley 的 **General Navigation Models** 家族:

- **GNM** (ICRA 2023): 第一代 cross-embodiment 視覺導航 backbone
- **ViNT** (CoRL 2023): Transformer-based foundation model, 增加 image goal 條件
- **NoMaD** (2023): 用 diffusion policy 統一 goal-conditioned navigation + undirected exploration, 並用 goal masking 切換兩種模式

**Goal type 對比 PawAI**:
- 三者皆為 **image goal navigation** (subgoal 是「目標位置的 RGB 照片」), **不是** point-goal (Nav2 的 `/goal_pose` x,y), 也不是 language-goal
- 部署仰賴 **topological map** (人工 teleop 走一圈錄 rosbag → 每秒抽一張 keyframe 當 node) 而非 metric occupancy grid
- PawAI 主線 (Nav2 + AMCL + RPLIDAR + occupancy grid) 是 **metric point-goal**, 範式不同

## 2. 輸入 / 輸出 / 感測器

- **輸入**: 單目 RGB (96×96, fisheye 廣角佳), context_size=3~5 frames + goal image
- **輸出**: `len_traj_pred=8` 個未來 waypoints (x,y), 由 `pd_controller.py` 轉 `/cmd_vel`; NoMaD 也輸出 distance estimate
- **感測器需求**: **僅需 RGB**。不用 depth、不用 LiDAR。我們的 D435 RGB stream 完全夠 (depth/RPLIDAR 用不到)

## 3. 推理需求 (Jetson Orin Nano)

- 模型: NoMaD ≈ EfficientNet-B0 vision encoder + 4-layer MHA + 1D conv U-Net diffusion (10 denoise steps), checkpoint 數十 MB
- 官方 README 明確列 **Jetson Orin Nano (LoCoBot)** 為部署平台 → 8GB RAM 跑得動
- 預期 latency: 4 Hz `frame_rate` (見 `robot.yaml`), 即每張 ~250ms 推理預算
- 與我們現有 RTMPose (GPU 91-99% 滿) **無法共存**, 需要時間切片或關掉 vision_perception

## 4. 訓練資料 / 預訓練模型

- 官方提供 GNM / ViNT / late_fusion / NoMaD 四個 `.pth` checkpoint (Google Drive)
- 訓練資料: RECON, TartanDrive, SCAND, GoStanford2, SACSoN/HuRoN — 多為 **室外/走廊/校園**, 室內居家覆蓋有限
- **Zero-shot 可用**, 但居家場景可能需要 fine-tune 或補錄 demo bag。Topomap 本身就是「demo 一條路徑」, 等同 few-shot 化

## 5. ROS2 整合度

- **ROS1 Noetic only** (`rospy`, `roslaunch`, `usb_cam`, `kobuki`)。`navigate.py` import `rospy`, 無 ROS2 wrapper
- 若要上 ROS2 Humble 須 port: `rospy` → `rclpy`、`/cmd_vel_mux/input/navi` 改接我們的 `cmd_vel_mux`、`pd_controller.py` 改成 ROS2 node
- 工程量約 1-2 天 (純 IO 層改寫, 模型推理本身與 ROS 解耦)
- 已知社群 fork 有 ROS2 移植 (NoMaD-ROS2), 可參考但非官方

## 6. 對 `approach_person` 的可吸收/啟發點

**直接吸收 (5/12 demo 不建議)**: ROS1 移植 + topomap 錄製 + Jetson GPU 共存 + 居家 fine-tune, 對 5/12 timeline 風險過高。

**啟發點 (中長期值得抄)**:
1. **Image-goal as approach target**: `approach_person` 可借鏡「把 D435 偵測到的人臉 bbox crop 當 goal image」概念, 走 visual servoing 收斂, 比純 Nav2 point-goal 更自然 (人會動)
2. **Context window of frames**: NoMaD 用過去 3-5 frames 做 temporal context, 對動態目標 (走動的人) 比 single-frame 更穩
3. **Diffusion policy for action sampling**: 多模態 trajectory 預測能避免 mode collapse, 但對 5/12 過度設計
4. **Topological map 思路**: 未來「room-to-room 居家導航」可考慮 keyframe topomap 取代純 metric map, 對居家半結構化環境更 robust

**結論**: 5/12 demo 沿用 Nav2 + reactive_stop + D435 偵測人 → 算 approach goal pose 餵 Nav2 的方案。NoMaD/ViNT 列入 **6 月後 R&D backlog**, 用於 `follow_person` 或 `room_navigation` 進階 skill。
