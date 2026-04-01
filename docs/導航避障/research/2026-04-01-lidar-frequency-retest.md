# LiDAR 頻率重測 — 2026-04-01

## 背景

之前的結論（2026-02-25 ~ 03-03）判定 Go2 Pro LiDAR 為 0.03-2Hz burst+gap，不可用。
本次重測推翻該結論。

## 測試環境

- Go2 Pro（韌體 v1.1.7）
- Jetson Orin Nano 8GB
- WebRTC 連線（Ethernet 192.168.123.161）
- go2_robot_sdk: enable_lidar=true, decode_lidar=true
- Topic: `/point_cloud2`（WASM voxel decoder）

## Step 1：純 driver（60 秒）

| 指標 | 數值 |
|------|------|
| 平均頻率 | **7.3 Hz** |
| Min interval | 0.114s |
| Max interval | 0.180s |
| Std dev | 0.005-0.017s |
| Gap > 1s | **0 次** |
| Burst+Gap 模式 | **無** |

## Step 3：+ camera + face + vision（60 秒）

| 指標 | 數值 |
|------|------|
| 平均頻率 | **7.3 Hz** |
| Min interval | 0.120s |
| Max interval | 0.181s |
| Gap > 1s | **0 次** |
| 頻率下降 | **無** |

## 與舊結論對比

| 指標 | 舊測量 (2026-02/03) | 新測量 (2026-04-01) |
|------|:-------------------:|:-------------------:|
| 平均頻率 | 0.03-2 Hz | **7.3 Hz** |
| gap_max | > 1.0s（常態） | **< 0.2s** |
| Burst+Gap | 有 | **無** |
| 加載後降頻 | 嚴重 | **無** |

## 差異原因（推測）

1. 7 輪優化的累積效果（stride、WASM backend、序列化路徑）最終生效
2. 之前測試可能有多 driver instance 殘留（已知陷阱）
3. Go2 韌體可能有背景更新
4. 環境更乾淨（clean session 紀律）

## 新判定

- ~~LiDAR 判死~~ → **LiDAR 復活（reactive/local safety 層級）**
- 穩定 7Hz 足以做反應式避障和 2D local costmap
- Full SLAM + AMCL + global planner 仍未驗證

## 深入測試：Full Stack 16 nodes（60 秒）

加了 pointcloud_to_laserscan + executive + ASR + TTS + LLM + foxglove（共 16 nodes）：

| Topic | 平均 Hz | Min interval | Max interval | Gap > 1s |
|-------|:-------:|:------------:|:------------:|:--------:|
| `/scan` | **12.8 Hz** | 0.000s | 0.229s | **0** |

**16 node 全跑仍然穩定。沒有頻率下降、沒有 burst+gap。**

注：`/scan` 頻率高於 `/point_cloud2` 是因為 pointcloud_to_laserscan 把一個 PointCloud2 拆成多個 LaserScan。實際 LiDAR 資料源頻率仍為 ~7.3Hz。

## 新結論

| 項目 | 舊判定 (2026-02/03) | 新判定 (2026-04-01) |
|------|:-------------------:|:-------------------:|
| LiDAR 頻率 | 0.03-2Hz, No-Go | **7.3Hz 穩定** |
| Burst+Gap | 有，常態 > 1s gap | **無** |
| 加載後降頻 | 嚴重 | **無（16 node 無影響）** |
| 整體判定 | ~~判死~~ | **復活（reactive/local safety）** |

## 待測

- [ ] Go2 行走中是否仍穩
- [ ] 連續 5 分鐘穩定性
- [ ] SLAM 建圖測試（slam_toolbox + LiDAR）
- [ ] Nav2 local planner 可行性
