# 外接 LiDAR 可行性研究

**日期**：2026-04-08
**背景**：Go2 Pro 內建 LiDAR 覆蓋率僅 18%（22/120 有效點），D435 避障因鏡頭角度限制上機測試全失敗（4/3）。4/8 會議老師同意嘗試外接 LiDAR，4/14 前定案。
**結論**：**技術上可行，RAM 安全，CPU 是唯一風險點。推薦 RPLIDAR A2M12。**

---

## 1. 為什麼外接 LiDAR 能解決問題

### 之前的痛苦鏈路（Go2 內建 LiDAR）

```
Go2 MCU voxel 編碼（18% 覆蓋率）
  → WebRTC 傳輸
  → Python decode（7 輪優化才達 5Hz）
  → PointCloud2 → LaserScan
  → SLAM: NO-GO（5Hz 品質差，業界最低門檻 7Hz）
  → Nav2: NO-GO（controller_freq 3Hz 不實用）
```

### 外接 LiDAR（直連 Jetson USB）

```
RPLIDAR USB serial
  → rplidar_ros2 driver（輕量 C++ 節點）
  → /scan（原生 LaserScan，10Hz+，360° 完整覆蓋）
  → SLAM: 可行（≥10Hz，標準方案）
  → Nav2: 可行（controller 可跑 10Hz+）
```

**核心差異**：完全繞過 Go2 WebRTC + voxel 解碼瓶頸。rplidar_ros2 是純 C++ driver，CPU 開銷極低。

---

## 2. Jetson Orin Nano 8GB 資源評估

### RAM 預算

| 項目 | RAM 估計 | 來源 |
|------|---------|------|
| **目前已佔用** | | |
| ROS2 runtime + Go2 driver | ~1.5-2.0 GB | 實測 |
| D435 camera | ~0.6-1.0 GB | 實測 |
| YuNet face (CPU) | ~0.1 GB | 實測 |
| MediaPipe Pose + Gesture (CPU) | ~0.3 GB | L3 壓測 |
| Edge-TTS / ASR (cloud) | ~0.1 GB | 估計 |
| **小計** | **~2.6-3.5 GB** | |
| **新增 SLAM + Nav2** | | |
| rplidar_ros2 driver | ~0.05 GB | C++ serial，極低 |
| slam_toolbox (online_async) | ~0.3 GB | MDPI Electronics 2024 論文：~293 MB |
| Nav2 (AMCL + controller, composed) | ~0.5-0.8 GB | Nav2 官方 composition mode |
| **小計** | **~0.85-1.15 GB** | |
| **總計** | **~3.5-4.7 GB / 8 GB** | |
| **剩餘** | **3.3-4.5 GB** | **✅ 安全** |

### CPU 評估

| 項目 | CPU 負載 | 備註 |
|------|---------|------|
| slam_toolbox (async) | ~70%（x86 基準，ARM 更高） | 2024 MDPI 論文數據 |
| Nav2 完整堆疊 | ~200% | Nav2 官方估計 |
| 目前感知模組 | ~100-200% | face + gesture + pose |
| **風險** | **⚠️ CPU 是唯一瓶頸** | 六核 ARM A78AE 總共 600% |

**緩解策略**：
- Demo 導航場景時暫時關閉 Gesture Recognizer（省 ~100% CPU）
- slam_toolbox 用 async mode（非 sync）
- Nav2 用 node composition（多節點合併單一 process）

### GPU

- slam_toolbox 純 CPU，**不搶 GPU** ✅
- 與 Whisper CUDA 無衝突

---

## 3. 三款 LiDAR 比較

| | RPLIDAR C1 | **RPLIDAR A2M12** | RPLIDAR S2 |
|--|:----------:|:-----------------:|:----------:|
| **價格** | $2,910 | **$7,530** | $13,230 |
| **測距** | 12m | 12m | 30m |
| **採樣率** | 5,000/s | **16,000/s** | 32,000/s |
| **10Hz 每圈點數** | ~500 | **~1,600** | ~3,200 |
| **技術** | DTOF | 光磁融合 | TOF |
| **SLAM 可行性** | ⚠️ 勉強（500 點太稀疏） | **✅ 標準配置** | ✅ 充裕（overkill） |
| **ROS2 生態** | 較新，案例少 | **最多案例** | 良好 |
| **功耗** | ~2W | ~3-5W | ~3-5W |

### 推薦：RPLIDAR A2M12（$7,530）

- C1 太弱：500 點/圈做 SLAM 品質差
- S2 太貴：室內 12m 夠用，30m + 32000/s 是浪費
- A2M12 是 ROS 社群最多人用的型號，教學豐富，1600 點/圈做 SLAM 是標準配置
- 光磁融合技術，無滑環，壽命長

---

## 4. 參考案例

### Waveshare UGV Beast

- **平台**：Jetson Orin Nano + RPLIDAR + ROS2 Humble
- **功能**：SLAM 建圖 + Nav2 自主導航
- **文件**：完整教學 wiki，證明硬體層面可行
- **來源**：waveshare.com/wiki/UGV_Beast_Jetson_Orin_ROS2_7._Navigation_and_SLAM_Mapping

### MDPI Electronics 2024 論文

- **標題**：SLAM Toolbox vs Cartographer 比較研究
- **數據**：slam_toolbox online_async — CPU ~70%、RAM ~293 MB、ATE 0.13m
- **結論**：slam_toolbox 精度優於 Cartographer，資源消耗可接受

---

## 5. 推薦 SLAM 配置

```yaml
# slam_toolbox (online_async)
slam_toolbox:
  ros__parameters:
    solver_plugin: solver_plugins::CeresSolver
    resolution: 0.15            # 降低計算量（預設 0.05）
    minimum_travel_distance: 0.5 # 減少更新頻率
    minimum_time_interval: 0.2
    map_update_interval: 2.0
    max_laser_range: 10.0       # 室內 10m 足夠
    throttle_scans: 2
    do_loop_closing: true

# Nav2 (composed mode)
# 使用 nav2_bringup composed launch 減少 process 數
# controller_frequency: 10.0
# AMCL max_particles: 1000
```

**swap 建議**：設定 4-8 GB swap 作為安全網。

---

## 6. 風險評估

| 風險 | 嚴重度 | 說明 | 緩解 |
|------|:------:|------|------|
| **供電** | 🔴 | LiDAR 馬達 +2-5W，XL4015 已在極限 | 固定電源模式（失去機動性） |
| **CPU 飽和** | 🟡 | SLAM + Nav2 + 感知同跑 | 導航時關手勢、async mode |
| **物理安裝** | 🟡 | Go2 行走震動 + LiDAR 不能被腿擋 | 需設計穩固支架 |
| **整合時程** | 🟡 | 4/14 決定 → 5/16 Demo 只剩 1 個月 | Gate A-C 驗證框架已有 |
| **Go2 摔倒** | 🟡 | 之前開導航多次摔倒 | 最小直線移動，不做複雜路徑 |

---

## 7. 時程

| 日期 | 動作 |
|------|------|
| 4/9 | 老師確認學校有無舊 LiDAR 可借 |
| 4/14 | 定案是否採購 + 型號 |
| 到貨後 Day 1 | USB 連接 + rplidar_ros2 driver 驗證 |
| Day 2-3 | slam_toolbox 建圖 + 參數調整 |
| Day 4-5 | Nav2 導航 + 防撞測試 |
| 5/16 前 | Demo 場景排練（直線短距移動） |

---

## 8. 決策

| 問題 | 答案 |
|------|------|
| Jetson 扛得住嗎？ | **RAM 安全，CPU 需管理** |
| 買哪台？ | **RPLIDAR A2M12（$7,530）** |
| 能做到什麼程度？ | **直線短距移動 + 基礎避障**（不做複雜路徑規劃） |
| 最大風險？ | **供電**（不是算力） |

---

*研究方法*：Claude Code subagent 搜尋 + MDPI 論文 + ROS Discourse + NVIDIA Forums + Waveshare Wiki
*研究者*：Roy
