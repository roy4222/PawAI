# Phase 2 執行指南書 - SLAM + Nav2 大空間完整評估

**日期：** 2025/11/21（Phase 1 通過後）
**目標：** 評估迴圈閉合、多點導航、避障、巡邏在大環境中的表現
**環境需求：** 4-5 坪或更大的連續空間
**總耗時：** 約 60-90 分鐘
**預期成果：** 確認系統性能數據，為 VLM + 尋物 FSM 開發做準備

---

## 前置條件

確認以下項已完成：

- [x] Phase 1 已全部通過
- [ ] 環境已擴大到 4-5 坪或更大
- [ ] 清除了測試區域的障礙物（除了預設的）
- [ ] 標記了起點位置（便於驗證迴圈閉合）
- [ ] WiFi 訊號良好
- [ ] 機器狗電池充滿

---

## 🚀 Phase 2 快速開始

### 環境準備

```bash
# 1. 清空 4-5 坪的連續區域
# 2. 放置 3-5 個障礙物（椅子、盒子、書架等）
# 3. 用膠帶或粉筆標記起點位置（便於後續驗證迴圈閉合）
```

### 啟動與頻寬控制（複用 Phase 1）

```bash
# Terminal 1：驅動
cd /home/roy422/elder_and_dog
bash start_go2_simple.sh

# Terminal 2：ROS2 環境 + 監控
source /opt/ros/humble/setup.bash
cd /home/roy422/elder_and_dog && source install/setup.bash
export ROBOT_IP="192.168.12.1"
ros2 topic hz /scan   # 應 > 5 Hz

# Terminal 3：啟動 SLAM + Nav2
export ROBOT_IP="192.168.12.1"
ros2 launch go2_robot_sdk robot.launch.py slam:=true nav2:=true rviz2:=true

# 【關鍵】RViz 開啟後立刻取消勾選 Image 和 PointCloud
```

---

## Step 1：詳細建圖（15-20 分鐘）

### 建圖策略

為了驗證迴圈閉合，機器狗需要：
1. **探索整個環境**（走 Z 字形或圓形）
2. **走回起點附近**（驗證地圖對齐）
3. **耗時 10-15 分鐘**（確保 SLAM 有充分時間配準）

### RViz 準備

```
1. SlamToolboxPlugin → "Start At Dock"（記住起點位置）
2. 確認 Fixed Frame = "map"
3. 觀察地圖視窗，監督地圖在逐漸填充
```

### 移動操作

**選項 A：Z 字形移動（推薦）**
```bash
# Terminal 4 或用搖桿手動控制
# Z 字形運動覆蓋整個環境，然後走回起點

bash TEST.sh forward    # 1 秒（走 ~30cm）
sleep 0.5
bash TEST.sh left       # 2 秒（轉向）
sleep 0.5
bash TEST.sh forward    # 走到另一邊
sleep 0.5
bash TEST.sh right      # 轉向
sleep 0.5
bash TEST.sh forward    # 繼續

# ... 重複 10-15 分鐘，最後確保走回起點附近
```

**選項 B：自由移動**
```bash
# 使用搖桿或遠端 app 自由移動
# 目標：覆蓋整個 4-5 坪區域，然後回到起點
```

### 迴圈閉合驗證

**關鍵時刻：機器狗回到起點附近時**

```
1. 觀察 RViz 地圖
2. 起點區域（標記位置）是否「對齐」？
   - ✓ 完美對齁：無明顯偏移（< 1 cm）
   - ⚠️ 良好：1-3 cm 偏移
   - ⚠️ 可接受：3-5 cm 偏移
   - ❌ 失敗：> 5 cm 偏移或明顯重疊

3. 如果偏移大，可試試：
   - 再走一圈（SLAM 會逐漸改善）
   - 檢查是否有鏡面/玻璃反射（見故障排查）
```

### 記錄建圖耗時

```bash
# 記下起始時間和結束時間
# 計算建圖耗時（通常 10-20 分鐘）
```

---

## Step 2：地圖存檔（2 分鐘）

```bash
# Terminal 2（分離視窗）
mkdir -p /home/roy422/elder_and_dog/src/go2_robot_sdk/maps

ros2 run nav2_map_server map_saver_cli -f /home/roy422/elder_and_dog/src/go2_robot_sdk/maps/phase2_large

# 驗證
ls -lh /home/roy422/elder_and_dog/src/go2_robot_sdk/maps/phase2_large*
# 應看到：phase2_large.yaml 和 phase2_large.pgm
```

---

## Step 3：多點導航測試（20 分鐘）

### 座標選擇方法

**【重要】不要寫死坐標，要根據當前地圖選擇安全點。**

```bash
# Terminal 2（分離視窗）
# 使用 RViz 的 "Publish Point" 工具
# 1. Navigation2 Plugin → "Publish Point" 按鈕
# 2. 在地圖上點擊白色區域（安全區）
# 3. Terminal 輸出：Point: x: 2.34, y: 1.56, z: 0.0
# 4. 複製這個座標

# 記錄下 5 個安全座標：
# Point 1: (x1, y1)
# Point 2: (x2, y2)
# Point 3: (x3, y3)
# Point 4: (x4, y4)
# Point 5: (x5, y5)
```

### 逐點導航測試

**對每個座標重複以下步驟：**

```bash
# 第 1 點測試
bash TEST.sh stand              # 起身準備
sleep 1

# RViz：Navigation2 Plugin → "2D Goal" → 點擊 Point 1 座標 → 拖曳設定朝向

# 監控導航
ros2 topic echo /amcl_pose      # 看位置逐漸接近目標

# 記錄：
# - 路徑規劃是否成功？(看地圖是否有綠色路線)
# - 導航是否成功？(機器狗到達或超時)
# - 耗時多少秒？

# 待機器狗完成或超時（> 2 分鐘算失敗），進行下一點
```

### 成功率統計

**填寫到 20251121_slam_test.md：**

| 點號 | 座標 | 成功/失敗 | 耗時 | 備註 |
|------|------|---------|------|------|
| 1 | (x1, y1) | ✓/❌ | ___ 秒 | |
| 2 | (x2, y2) | ✓/❌ | ___ 秒 | |
| 3 | (x3, y3) | ✓/❌ | ___ 秒 | |
| 4 | (x4, y4) | ✓/❌ | ___ 秒 | |
| 5 | (x5, y5) | ✓/❌ | ___ 秒 | |

**預期成功率：** >= 80% (4/5)

---

## Step 4：避障動態測試（10 分鐘）

### 測試設置

```bash
# 第一次測試：
# 1. RViz "2D Goal" 設定一個從 A 到 B 的長距離導航
# 2. 機器狗開始移動後（5 秒左右），在 A-B 路線中點放置一個盒子或椅子
# 3. 觀察機器狗是否避開並繼續導航

# 記錄：
# - 避障反應時間：___ 秒（應 < 3 秒）
# - 是否成功避開並繼續：✓ 成功 / ❌ 卡死 / ❌ 無反應
```

### 多次重複

```bash
# 至少測試 2-3 次，不同位置和類型的障礙物
# 例如：
#   - 測試 1：盒子（硬障礙）
#   - 測試 2：椅子（較大障礙）
#   - 測試 3：人靠近（動態障礙）

# 記錄避障反應時間和成功率
```

---

## Step 5：完整巡邏迴圈測試（15-20 分鐘）

### 編輯巡邏點

```bash
# Terminal 2（分離視窗）
nano src/search_logic/config/patrol_params.yaml

# 編輯 patrol_points，使用 Step 3 選出的「安全座標」
# 例如：
```

```yaml
simple_patrol_node:
  ros__parameters:
    # 基於 Step 3 的安全座標
    patrol_points: [
      [0.5, 0.0],      # 起點
      [2.0, 0.0],      # 右前
      [2.0, 2.0],      # 右後
      [0.0, 2.0],      # 左後
      [-1.0, 1.0],     # 左側
      [0.5, 1.0],      # 中間回起點
    ]

    loop_patrol: true   # 啟用迴圈巡邏
    auto_start: false   # 手動啟動
```

```bash
# 保存（Ctrl+O, Enter, Ctrl+X）
```

### 啟動巡邏節點

```bash
# Terminal 4
ros2 run search_logic simple_patrol_node \
  --ros-args -p auto_start:=true -p loop_patrol:=true
```

### 監控與記錄

```bash
# Terminal 2（分離視窗）：實時監控狀態
ros2 topic echo /patrol_status

# 預期輸出：
# "前往巡邏點 1/6: (0.50, 0.00)"
# "到達巡邏點 1"
# "前往巡邏點 2/6: (2.00, 0.00)"
# ...
```

### 成功指標

**巡邏完成 2 個完整迴圈，記錄：**

```
迴圈 1：
- 完整迴圈耗時：___ 分鐘
- 失敗點（若有）：___
- 評分：✓ 完美 / ⚠️ 有 1-2 失敗 / ❌ > 2 失敗

迴圈 2：
- 完整迴圈耗時：___ 分鐘
- 失敗點（若有）：___
- 評分：✓ 完美 / ⚠️ 有 1-2 失敗 / ❌ > 2 失敗

整體穩定性：___ % (0-100%)
```

**預期穩定性：** >= 90% (無失敗或極少失敗)

---

## Phase 2 檢查清單

```
□ 建圖耗時：___ 分鐘（應 10-20 分鐘）
□ 迴圈閉合偏移：___ cm（應 < 5 cm）
□ 5 點導航成功率：___ % （應 >= 80%）
□ 避障反應時間：___ 秒（應 < 3 秒）
□ 避障成功率：___ % （應 >= 80%）
□ 2 圈巡邏穩定性：___ % （應 >= 90%）

✓ 所有項都達標 → Phase 2 通過！
❌ 某些項未達標 → 見故障排查或參數調整
```

---

## 🔴 故障排查 - Phase 2 特定問題

### 問題 1：迴圈閉合失敗（偏移 > 5 cm）

**原因：**
- 環境特徵不足（牆太直、沒轉角）
- LiDAR 頻率不穩定（被人擋住或 WiFi 干擾）
- SLAM 參數不適合當前環境

**解決方案：**

```bash
# 短期：增加環境特徵
# 1. 放置更多障礙物（轉角、高度變化）
# 2. 再走一圈（SLAM 會逐漸改善）
# 3. 檢查機器狗 LiDAR 是否被擋住

# 長期：調整 SLAM 參數
# 編輯 go2_robot_sdk/config/mapper_params_online_async.yaml
# 調整 loop_match_minimum_response_fine: 0.45 → 0.40 或 0.35
# （更敏感的迴圈檢測，但可能誤檢）
```

---

### 問題 2：多點導航成功率低（< 80%）

**原因：**
- 地圖品質差（迴圈閉合失敗導致）
- 座標選擇不當（離牆太近或在障礙物上）
- Nav2 參數不適合（速度太快、轉向不夠激進）

**解決方案：**

```bash
# 短期：重新選擇座標
# 1. 使用 "Publish Point" 工具，只選 Costmap 中心的白色區域
# 2. 避免靠近黑色（障礙物）或邊界

# 長期：調整 Nav2 速度參數
# 編輯 go2_robot_sdk/config/nav2_params.yaml
# 調整 max_vel_x: 3.0 → 1.0 或 0.5
# （速度越低越穩定，但耗時更長）
```

---

### 問題 3：避障失效或反應慢

**原因：**
- Costmap 初始化不完整
- inflation_radius 設置過小（無法提前預警）
- DWB Local Planner 參數不當

**解決方案：**

```bash
# 短期：重新啟動 Nav2
# Terminal 3：Ctrl+C
# 等待 5 秒
# 重新執行 ros2 launch

# 長期：調整避障參數
# 編輯 nav2_params.yaml
# 找到 inflation_layer
# 增加 inflation_radius: 0.5 → 1.0 或 1.5
# （機器人「感知」的安全距離增加）
```

---

### 問題 4：巡邏節點找不到或發佈失敗

**症狀：** `ros2 run search_logic simple_patrol_node` 出錯

**解決方案：**

```bash
# 確認編譯完成
cd /home/roy422/elder_and_dog
colcon build --packages-select search_logic

# 重新 source
source install/setup.bash

# 再試
ros2 run search_logic simple_patrol_node --ros-args -p auto_start:=true
```

---

## 📝 完成後的動作

1. **填寫測試日誌：**
   ```bash
   # 打開 20251121_slam_test.md
   # 填寫所有 Phase 2 的欄位
   ```

2. **參數調整建議：**
   ```markdown
   根據測試結果，記錄以下調整：

   SLAM 參數調整：
   - loop_match_minimum_response_fine: 0.45 → ___ (若迴圈失敗)

   Nav2 參數調整：
   - max_vel_x: 3.0 → ___ (根據實際速度)
   - inflation_radius: 0.5 → ___ (根據避障需求)
   ```

3. **為 VLM + 尋物 FSM 做準備：**
   - 確認系統穩定性 >= 90%
   - 記下常用的導航座標（未來用於自動尋物）
   - 評估是否需要進一步調參

---

**祝 Phase 2 測試順利！完成後可以進行 VLM 物體偵測整合。** 🚀

