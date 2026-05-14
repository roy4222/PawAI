# CSDN 論文筆記:Fast_LIO2 + 改 Cartographer + ICP 路線 — 參考價值分析

> **Date**: 2026-05-02
> **Author**: Roy + Claude
> **Status**: reference-only(技術線不同,僅 1 點直接可吸收)
> **Purpose**: 評估「3D LiDAR (Mid-360) + IMU + Fast_LIO2 + ICP」路線對 PawAI 2D RPLIDAR + AMCL stack 的可吸收概念
> **Source**: https://blog.csdn.net/m0_61620976/article/details/140587071(碩士論文泛讀筆記)

---

## 一句話結論

**技術線不同,參考價值有限**。論文用 3D LiDAR (覽沃 Mid-360) + Fast_LIO2 + ICP 純定位,走「3D 點雲 → 地面分割 → 轉 2D scan → 改進 Cartographer」路線;我們是 2D RPLIDAR-A2M12 + AMCL,從一開始就是 2D。**唯一直接可吸收**:**EKF 融合 IMU + 輪式 odom 餵 cartographer / AMCL**,可改善 Go2 快速轉向時的漂移。

---

## 論文 stack(對照組)

```
3D LiDAR (Mid-360) + IMU
       ↓
Fast_LIO2(增量 kd-tree 雷射慣性里程計)
       ↓
3D 點雲地圖 → 地面提取分割 → PointCloud 轉 2D scan
       ↓
改進 Cartographer(IMU + 輪式 odom EKF 融合餵入)
       ↓
2D 柵格地圖
       ↓
ICP 點雲配準(純定位,取代 AMCL)
       ↓
A* 全局 + TEB 局部
       ↓
/cmd_vel → 機器人控制器
```

### 論文四個選型對比

| 項目 | 方案 A | 方案 B | 論文選擇 |
|---|---|---|---|
| 建圖 | Gmapping | 改進 Cartographer | B |
| 定位 | AMCL | ICP | B |
| 全局規劃 | Dijkstra | A* | B |
| 局部規劃 | DWA | TEB | B |

---

## PawAI 對照

| 維度 | 論文 | PawAI |
|---|---|---|
| LiDAR | Mid-360 (3D, 16 線) | RPLIDAR-A2M12 (2D, 360°) |
| 里程計 | 輪式 odom + GY95T IMU + EKF | Go2 內建 odom(driver `_publish_transform`) |
| 建圖 | 改進 Cartographer(IMU+odom 融合) | Cartographer(只用 lidar + odom,**沒餵 IMU**) |
| 定位 | ICP 純定位 | AMCL(K1 baseline 5/5 PASS) |
| 全局 | A* | Nav2 NavFn(類 A*) |
| 局部 | TEB | DWB(`min_vel_x:=0.45` 對應 Go2 MIN_X 0.50) |

---

## 一個直接可吸收的點 ⭐

### **Cartographer 加 IMU 輸入** — 改善 Go2 快速轉向漂移

論文核心改進:**車輪 odom + IMU 用 EKF 融合,輸出 `odom` 餵 Cartographer**,結果「對小物品、牆角、牆面建圖效果優於改進前,邊界更清晰」。

對應到我們:
- Go2 內建 IMU 已透過 driver publish `/imu` topic(待確認)
- 我們現在 `cartographer_2d.lua` config 應該**沒有 `use_imu_data = true`**(或只當 trajectory builder 輔助)
- Phase 7 5/1 `home_living_room_v8` 建圖是「走得很慢」才避開漂移 — 如果加 IMU,可能允許快速轉身建圖

**驗證指令**(Jetson):
```bash
ros2 topic list | grep imu
ros2 topic echo /imu --once         # 確認有資料、frame_id、QoS
grep -i "use_imu" go2_robot_sdk/config/cartographer_2d.lua
```

**動作**(P2,5/12 demo 後):
1. 確認 Go2 driver 有 publish `/imu`,frame_id 對齊 `imu_link`
2. `cartographer_2d.lua` 設 `TRAJECTORY_BUILDER_2D.use_imu_data = true`
3. 重建 v9 map,對比 v8 邊界品質

⚠️ **5/12 前不動** — v8 已驗證 K1 baseline 5/5 PASS,動 cartographer config 是 risk。

---

## 兩個哲學參考(不抄,僅紀錄)

### 1. **TEB vs DWB**(局部規劃器)

論文選 TEB 理由:多目標優化、考量速度/加速度約束、避障效果更好。

**為什麼我們不換**:
- DWB 已對 Go2 MIN_X=0.50 m/s 校準完成(`min_vel_x:=0.45`)
- TEB 對 quadruped 的 holonomic 假設不一定吻合(Go2 sport mode 是 omni-direction 但 MIN_X 強制)
- 5/12 demo risk 太大

**P3 評估**(demo 後可比較):TEB 對狹窄空間 + 動態障礙的處理是否真的優於 DWB + reactive_stop 雙層?

### 2. **ICP 純定位 vs AMCL**

論文選 ICP 理由:點雲配準精度高於 AMCL 粒子濾波。

**為什麼我們不換**:
- ICP 在 2D LiDAR 上精度遠不如 3D 點雲(我們是 2D-only)
- AMCL 已通過 K1 baseline,covariance < 0.20 達標
- ICP 對「初始位置已知」要求高,我們需要 `/initialpose` 自由設定

→ **3D LiDAR 場景 ICP 才有意義**,我們不適用。

---

## 不抄的部分

| 論文設計 | 為什麼不抄 |
|---|---|
| **Mid-360 3D LiDAR** | $5000+,5/12 demo 前無法採購;且改變整個感測器 stack |
| **Fast_LIO2** | 3D 雷射慣性里程計,2D LiDAR 不適用 |
| **地面提取分割** | 3D 點雲專用流程,2D LiDAR 直接是 ground-plane scan |
| **ICP 純定位** | 2D LiDAR 精度不足 |
| **TEB 局部規劃** | DWB 已校準,5/12 risk |

---

## 三方比較更新(Odin / OM1 / 本論文 / PawAI)

| 維度 | Odin | OM1 | CSDN 論文 | PawAI |
|---|---|---|---|---|
| 載體 | Unitree Go2 | Unitree Go2 | 通用輪式機器人 | Unitree Go2 |
| LiDAR | 2D | RPLidar A1M8 | Mid-360 (3D) | RPLIDAR-A2M12 (2D) |
| ROS | ROS1 | ROS2 + Zenoh | ROS2 | ROS2 Humble |
| 建圖 | (依賴 ros nav) | SLAM Orchestrator | Fast_LIO2 + 改 Cartographer | Cartographer (2D) |
| 定位 | AMCL | (未明) | ICP | AMCL |
| 全局 | A* | Nav2 | A* | Nav2 NavFn |
| 局部 | DWA / NeuPAN | Nav2 default | TEB | DWB |
| 我們學什麼 | 語義導航 + DWA decay | Multi-LLM + lifecycle + AI gating | **IMU 餵 cartographer** | — |

---

## 行動清單

### Phase A 可立刻吸收
- (無 — 此論文最有價值的點是 P2)

### 5/12 Demo 後(P2)
1. **Cartographer 加 IMU 輸入** — 確認 Go2 `/imu` topic + 改 `cartographer_2d.lua` 的 `use_imu_data = true`,重建 v9 map 對比

### 評估(P3,demo 後)
2. **TEB vs DWB benchmark** — 在已驗證 v8 map 上做 A/B,看狹窄空間表現

### 不做
- ❌ 換 3D LiDAR
- ❌ 換 ICP 定位
- ❌ 換 Fast_LIO2

---

## 來源

- CSDN 原文(碩士論文泛讀筆記): https://blog.csdn.net/m0_61620976/article/details/140587071
- 系統架構圖: https://i-blog.csdnimg.cn/direct/52ecc1f579124650b4dedda3b0e30d32.png
- IMU+odom EKF 融合流程: https://i-blog.csdnimg.cn/direct/086c0f0cb2004a70a4063d0404bb64ae.png
- ICP 原理圖: https://i-blog.csdnimg.cn/direct/0178026dc286485b960892b49897a12f.png
- 原論文(CNKI): https://kns.cnki.net/kcms2/article/abstract?v=FqYZq-Q0wRQ9PDUlUWwfn9pxvQNda6HlGlCAHfZLc4JjUnWZFgUQcvAQZRAyY63QhUFianpKrYUfWW5NwuPNB2OZWHm95_mbQy4PzlWoMqw37uEdR-VbHmg2EWq_FXH08XX1kNB0qC8E900TH7lkhdtusx9hWVp_0n9sAEV4VRR2e8sSYqsaJikedows8XKmJQnf35Wmm-c=
