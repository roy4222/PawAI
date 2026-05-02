# Dynamic Obstacle Avoidance v0 — 5/2 試跑紀錄與下一步

**日期**：2026-05-02 evening + late-night
**結果**：K-STATIC-AVOID-CONTROLLED **PARTIAL**（1 輪 PASS、1 輪 no-op、未做 R3）
**事故**：v3 試 detour 時 Go2 摔倒一次（Damp 1001 用錯）；v4 改用 emergency_stop engage + StopMove 1003，後續沒摔
**剩餘工作**：明天做 R3 + 第二階段 D435 低矮物 detection

---

## 三階段框架（5/2 拍板）

| 階段 | 範圍 | 今晚狀態 |
|------|------|:------:|
| **第一階段** | 定點障礙物繞開（LiDAR + DWB）：能繞或可控停 | 🟡 PARTIAL（R1 PASS、R2 no-op）|
| **第二階段** | 低矮障礙物補盲（D435 stop only，不進 costmap）| ⏳ 明天 |
| **第三階段** | 人類動態經過 | ❌ 不做 |

---

## 今晚 yaml 改動（保留，不 revert）

`go2_robot_sdk/config/nav2_params.yaml` 三行：

```yaml
# DWB controller_server.FollowPath
BaseObstacle.scale: 0.40 → 0.80   # 障礙真的有成本但不爆衝逃離
PathAlign.scale:    16.0 → 12.0   # 給 DWB 偏離原路徑 25% 空間
# local_costmap.inflation_layer
inflation_radius:   0.25 → 0.30   # 多 5cm 緩衝
```

意圖：「讓它**開始**避，但**不要爆衝**」。**不開 lateral**（max_vel_y=0 維持），**不動** sim_time / samples / min_vel_x / recovery / xy_goal_tolerance。

---

## v3 摔倒事故（已分析、已修）

### 事故鏈
```text
DWB 發 vx=0.5 + az=-0.32（曲線繞行）
→ 前方距離進 0.6m → reactive_stop 進 danger zone
→ /cmd_vel_obstacle priority 200 立刻蓋台 /cmd_vel_nav（priority 10）
→ twist_mux 輸出瞬間從 0.5 → 0（沒 velocity_smoother 也救不到 mux 切換）
→ Go2 在 trot gait 中急停
→ watchdog 等到 DANGER_6s 才送 Damp (api_id=1001) ← 錯誤指令
→ Damp = 馬達軟鬆弛 → Go2 倒
```

### 三個錯
1. **Damp 不能當移動中 emergency stop**（軟鬆弛馬達 → 站不穩）
2. **danger zone entry 5-6s 才 abort 太晚**（detour 進到 0.6m 就已失敗，應 ≤ 1s 即停）
3. **velocity_smoother 不解此 bug**（mux pri 200 切換 bypass smoother）

### v4 修正（今晚已套用，後續未再摔）
- abort 不送 Damp。改 5 步止血：cancel → `emergency_stop.py engage`（mux pri 255 + lock）→ StopMove (1003) → 等 cmd_vel=0 持續 ≥ 2s → 收機才考慮 Damp
- danger watchdog 改成 1s 觸發
- velocity_smoother 不在今晚 scope

### StopMove 指令格式（重要 — 不是只填 api_id）

`go2_interfaces/msg/WebRtcReq` 有 5 欄：`id / topic / api_id / parameter / priority`。**`api_id=1003` 在不同 topic 下意義完全不同**：

| topic | api_id=1003 含義 |
|-------|-----------------|
| `rt/api/sport/request` | **StopMove**（保持站姿取消當前 move）✅ |
| `rt/api/obstacles_avoid/request` | obstacle-avoidance 的 Move 命令（不是停車！）❌ |

來源：`go2_robot_sdk/application/utils/command_generator.py:113-128` + `domain/constants/robot_commands.py:13`。

正確 publish：
```bash
ros2 topic pub --once /webrtc_req go2_interfaces/msg/WebRtcReq \
  '{api_id: 1003, topic: "rt/api/sport/request", parameter: "", priority: 0}'
```

---

## v4 試跑結果

### Round 1（DWB 試繞 → 急停）

| 指標 | 值 |
|------|----|
| 起點 / 終點 | (-0.125, 0.168) → (0.541, -0.089) |
| 走 | 0.67m forward / 0.18m sideways drift |
| Nav2 結果 | ABORTED（recovery 失敗自然結束）|
| cmd_vel 序列開頭 | linear.x ramp 0.125 → 0.5、angular.z -0.16 → -0.57 ← **DWB 真的試右轉繞** |
| 後段 | 全 0（reactive 進 danger 蓋 0）|
| 撞 / 摔 | **沒有** |

**結論**：K-STATIC-AVOID-CONTROLLED ✅，K-STATIC-DETOUR ❌。  
DWB 開始繞但繞弧半徑不夠，0.49m 處進 reactive danger zone → cmd_vel=0 → BT recovery 失敗。

### Round 2（DWB 一開始就放棄）

| 指標 | 值 |
|------|----|
| 起點 / 終點 | (-0.089, 0.137) → 沒動 |
| cmd_vel 序列 | 84 樣本，**只 3 筆非零角速度（0.16/0.25/0.09）然後全 0** |
| Nav2 結果 | ABORTED（很快）|
| RPLIDAR 距離 | 1.25m（清楚可見 box）|
| 撞 / 摔 | 沒有 |

**結論**：planner 在小幅旋轉後直接放棄推進。可能原因：progress checker 20s timeout / BT recovery 提早判定無解 / costmap inflation 把 Go2 框死 / box 位置略偏。**不是 reproducible 行為**——R1 跟 R2 行為差很多，需要 R3 + 場景重新校準才能下定論。

### 兩輪聚合判斷
- 連續 2 輪都**不撞、不摔、不大甩** → v4 abort 流程設計正確
- 但 detour 行為**不可重現** → DWB 對這個場景（box 1.0-1.2m / 兩側 0.7m）**繞行能力處於邊緣**
- 還沒到「定點障礙物可控避障 v0」的可宣稱門檻

---

## 5 步止血（abort 流程，本日驗證）

```bash
# 1. cancel 當前 Nav2 goal
ros2 action send_goal --cancel /navigate_to_pose nav2_msgs/action/NavigateToPose \
  "{pose: {header: {frame_id: 'map'}}}"

# 2. mux 鎖死所有 cmd_vel（priority 255 + /lock/emergency）
python3 ~/elder_and_dog/nav_capability/scripts/emergency_stop.py engage

# 3. StopMove（保持站姿、取消 active move）— 注意 topic 必填
ros2 topic pub --once /webrtc_req go2_interfaces/msg/WebRtcReq \
  '{api_id: 1003, topic: "rt/api/sport/request", parameter: "", priority: 0}'

# 4. 等 cmd_vel = 0 持續 ≥ 2s 確認 Go2 站穩
# （ros2 topic echo /cmd_vel 觀察）

# 5. 收機才送 Damp（測試中永遠不送）
# 下一輪測試前要 release lock：
python3 ~/elder_and_dog/nav_capability/scripts/emergency_stop.py release
```

---

## 明天的工作（R3 + 第二階段）

### 先：場景校準
R1 / R2 行為差太多，先排除場地變因：
1. 標記 box 物理位置（地板貼膠帶）
2. 標記 Go2 起點 + 朝向
3. 量左右淨空（目標 ≥ 0.8m）
4. 確認 RPLIDAR 看到的 obstacle_distance 在 R3 開始時與 R1/R2 一致

### R3：能不能重現 R1 行為？
- 同 yaml（不再改）
- 同場景（box 1.0-1.2m 中央 / 兩側 0.7-0.8m）
- 同 watchdog（danger > 1s / side > 0.4 / vx > 1）
- 期望：類似 R1 — 嘗試繞但停在 box 前

如果 R3 又像 R2 一樣 no-op，先**放寬場景**（box 1.5m / goal 2.5m / 左右 1m）給 DWB 更多反應距離，再跑 1 輪。

### 第一階段判分（R1 + R3 之後）
- 兩輪都類似 R1（試繞、停止、不撞）→ K-STATIC-AVOID-CONTROLLED ✅
- 任何輪嚴重 fail → 回 K1 stable revert yaml，stage 1 不過

### 第二階段（K-LOW-OBSTACLE-DETECT/GATE）
第一階段 ≥ 2/3 PASS 才做：
1. 切 Emergency Mode：`ros2 param set /reactive_stop_node enable_nav_pause true`
2. 收緊 D435 閾值：`ros2 param set /depth_safety_node stop_distance_m 0.35`
3. 把低矮物（拖鞋 / 紙袋）放 D435 ROI 0.3-0.5m
4. 看 `/capability/depth_clear` 是否 ≤ 1s 翻 false
5. （選做）驗 Executive SafetyLayer 在 depth_clear=false 時拒新 NAV/MOTION plan

---

## 已知限制（v0）

- **DWB 繞行不可靠**：1.0-1.2m 中央 box / 兩側 0.7m 場景，DWB 行為不穩定（R1 試繞 vs R2 放棄）
- **不繞行成功時靠 reactive 兜底**：障礙在路徑上 → cmd_vel mux 蓋 0 → Go2 停 → BT abort
- **min_vel_x = 0.45 m/s 硬限**（Go2 sport mode MIN_X = 0.50 calibration），DWB 沒有低速貼邊修正能力
- **lateral 沒開**（`max_vel_y = 0`）：DWB 只能用弧線繞，不能側移
- **D435 不在 costmap**：低矮物只能停車不能繞（明天第二階段測 detection）
- **WebRtcReq 必填 topic**：`api_id` 在不同 topic 下含義不同，hand-write 必須完整

---

## 不做（demo 後 v1）

- velocity_smoother（mux 切換 bypass，今晚改不解問題）
- D435 → reactive_stop 主動停 active goal
- depthimage_to_laserscan / voxel_layer
- BT XML 客製 spin/backup velocity
- max_vel_y 開啟（已知四足狗在小空間風險高）
- AMCL initial_cov 重設
