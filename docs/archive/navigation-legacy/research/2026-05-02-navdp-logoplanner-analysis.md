# NavDP / LoGoPlanner 對 PawAI 可吸收性分析

- **Source**: https://github.com/InternRobotics/NavDP
- **Commit**: `934cedd03ed5e2adf00ef798229d418ec45d2684` (Merge PR #87, 2026-05-02 clone)
- **Sub-path**: `baselines/logoplanner/`
- **論文**: NavDP arXiv:2505.08712 / LoGoPlanner arXiv:2512.19629

## 1. NavDP 整體定位

NavDP = **Navigation Diffusion Policy**，Shanghai AI Lab + 清華出品。**End-to-end mapless navigation**：走 sim-to-real，IsaacSim 大規模生資料 + privileged information guidance 訓 diffusion policy，**不需地圖、不需傳統 planner**。支援三種任務：NoGoal exploration、PointGoal、ImageGoal。屬於 InternVLA-N1 雙系統的 System-1（reactive 層）。整個 repo 用 **HTTP Flask server** 提供推理 API，跟 evaluator/host 解耦。

## 2. baselines/logoplanner

LoGoPlanner = **Localization-Grounded** 版 NavDP（NavDP 進化版，比 NavDP 多了顯式 metric-aware geometry backbone）。

**演算法**：
- Backbone：`Pi3` 視覺幾何模型（long-horizon visual geometry）+ DepthAnythingV2 ViT-S → 抽 RGBD token
- Geometry head：world points decoder + camera (extrinsic) head → 隱式 6DoF localization + 重建周圍場景幾何
- Policy：Transformer Decoder (8 層，384-dim, 8 heads) + **DDPM diffusion scheduler** (10 train steps)
- 同時輸出 action trajectory（24 步）+ critic value（trajectory ranking）

**輸入**：RGB (224×224) + Depth (640×480 → reshape) + goal (x,y) + memory_size=8 歷史幀；
**輸出**：24 步 (x,y,yaw) trajectory + 各 trajectory 的 critic value，外層接 **MPC controller** (`deployment/mpc_controller.py`) 跟蹤。

**感測器需求**：RGBD 相機（demo 用 RealSense D455，640×480@30fps）+ camera intrinsics。**不需 LiDAR、不需 odometry、不需地圖**（localization 內建在 backbone）。

**算力**：硬寫 `device='cuda:0'`。模型約 300-500M 參數（Pi3 + DAv2 + diffusion decoder），預估 **2-4 GB VRAM**。Server log 顯示 phase1-4 細分；real-world server FPS writer 設 **2 fps**（sim 端 7 fps），代表單次推理約 **150-500 ms**（含 10 步 DDPM denoise）。Lekiwi 部署是 **RPi5 採集 → 串流到 laptop GPU 推理**，不是 on-device。

## 3. vs 我們 Nav2+DWB+reactive_stop

**可吸收**：
- **HTTP server / planner 解耦** 架構值得借鑑 — 我們 Brain Executive 也可以用同模式接 perception。
- **Critic-ranked trajectory** 思路：產多條軌跡 + value head 排序，可啟發我們在 reactive_stop 之外加一層 trajectory scoring。
- **Pi3 + DepthAnythingV2** 對 D435 純 RGBD（無 LiDAR 場景）有參考價值，可為「LiDAR 故障 fallback」研究方向。

**不可吸收**：
- **完全 end-to-end，吃整個 stack**：要丟掉 Nav2/DWB/AMCL/cost map。我們 5/12 demo 用 nav_demo_point + approach_person 走 Nav2 action，不能換骨。
- **訓練資料全在 IsaacSim**，沒有 Go2 四足 embodiment 的 checkpoint（demo 都是 wheeled / Lekiwi holonomic）。zero-shot 上 Go2 sport mode（min_vel_x 0.5 m/s 門檻）風險極高。
- **無地圖** ≠ 我們的需求。客廳已建 cartographer map，AMCL 定位穩，丟掉是退步。

## 4. Jetson Orin Nano 8GB 跑得動嗎？

**結論：跑不動 / 不該跑**。
- Pi3 backbone + DAv2 + diffusion decoder 需 2-4 GB VRAM 純推理；Jetson 8GB **統一記憶體**已被 ROS2 + D435 + RTMPose + Whisper + Qwen2.5-0.5B 吃掉 ~5 GB（MEMORY.md 紀錄餘 2.4 GB）。
- 推理延遲 150-500 ms → 對應 2-7 Hz，落在我們 reactive_stop 20 Hz 安全層下方，不能取代避障。
- 官方 Lekiwi 範例本身就**不在 RPi 上推理**，採用「板上採集 + laptop GPU 推理」的 offload 架構，間接證明 SBC 不夠力。
- 若硬上，得走 `lekiwi_logoplanner_host.py` 模式 → 把推理丟給開發機 GPU、Jetson 只跑 streaming + MPC，違背 demo 邊緣自治原則。

## 5. ROS2 整合度

**接近零**。全 repo grep `rclpy/Twist/cmd_vel` = 0 hit。介面是 **Flask HTTP**（`/navigator_reset` `/pointgoal_step` `/nogoal_step` `/imagegoal_step`），輸出 trajectory list 由外部 MPC 跟蹤。要整進我們 Nav2 stack 需自寫 ROS2 wrapper：訂 `/camera/color` + `/camera/depth` → POST server → 收 trajectory → 轉 `nav_msgs/Path` 餵 controller_server，工程量約 1-2 週，且 Go2 control 介面（sport mode cmd_vel）跟 LeKiwi holonomic 差異需重新校。

## 建議

**5/12 demo 不採用**。可放 future work 章節（文件加分）：
1. NavDP 系列代表「mapless end-to-end nav」研究前沿，可在論文 Ch5 引用對比我們的 modular Nav2 路線；
2. 若未來 Jetson 升級到 Orin AGX 32GB 或加裝外接 GPU module，可重評 LoGoPlanner 作為 LiDAR 失效 fallback；
3. 「HTTP server + critic-ranked trajectory」設計模式可作為 Brain Executive 接下一代 perception backbone 的架構參考。
