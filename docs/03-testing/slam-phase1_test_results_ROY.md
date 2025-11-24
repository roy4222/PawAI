# Roy Phase 1 測試結果記錄

**測試者:** Roy (A組)
**測試日期:** 2025/11/__ (待填入)
**測試環境:** Mac UTM (Ubuntu 22.04) + Go2 實機
**連線方式:** WebRTC (192.168.12.1)
**使用腳本:** phase1_test.sh

---

## 📋 測試前檢查清單

在執行測試前,請確認以下環境就緒:

- [ ] Mac 已連接 Go2 Wi-Fi (`Go2-xxxx`)
- [ ] UTM 虛擬機網卡配置完成 (enp0s2: 192.168.12.222)
- [ ] `ping 192.168.12.1` 成功 (延遲 < 50ms)
- [ ] `ping google.com` 成功 (驗證雙通)
- [ ] Windows Foxglove 可連線至 Mac (192.168.1.177:8765)
- [ ] 所有 ROS2 環境變數已載入

---

## 🎯 Phase 1 七項檢查清單

### ✅/❌ 1. Go2 驅動啟動成功

**測試指令:**
```bash
# Terminal 1
zsh phase1_test.sh t1
```

**檢查標準:**
- [ ] 看到 `[INFO] Video frame received for robot 0`
- [ ] 無紅色 ERROR 訊息
- [ ] `ros2 node list` 包含 `/go2_driver_node`

**實測結果:**
- 狀態: ✅ / ❌
- 啟動時間: ____ 秒
- 錯誤訊息 (若有):

---

### ✅/❌ 2. /scan 頻率測試 (目標 > 5 Hz)

**測試指令:**
```bash
# Terminal 2
zsh phase1_test.sh t2
# 或手動執行: ros2 topic hz /scan
```

**檢查標準:**
- [ ] 頻率 > 5 Hz
- [ ] 無 `WARNING: no messages received` 訊息
- [ ] 持續穩定 30 秒以上

**實測結果:**
- 狀態: ✅ / ❌
- 頻率: ____ Hz (平均值)
- 最高頻率: ____ Hz
- 最低頻率: ____ Hz
- 穩定性: 穩定 / 波動大 / 間歇性斷線

**問題記錄 (若有):**

---

### ✅/❌ 3. SLAM 與 /map 發布正常 (目標 ~1 Hz)

**測試指令:**
```bash
# Terminal 3
zsh phase1_test.sh t3

# Terminal 2 (新窗口)
ros2 topic hz /map
```

**檢查標準:**
- [ ] slam_toolbox 節點啟動無錯誤
- [ ] `/map` topic 正常發布 (~1 Hz)
- [ ] Nav2 節點全部啟動
- [ ] Foxglove Bridge 啟動成功

**實測結果:**
- 狀態: ✅ / ❌
- /map 頻率: ____ Hz
- slam_toolbox 狀態: 正常 / 有警告 / 失敗
- Nav2 啟動時間: ____ 秒
- Foxglove 連線: 成功 / 失敗

**錯誤訊息 (若有):**

---

### ✅/❌ 4. TF 樹完整性檢查

**測試指令:**
```bash
ros2 run tf2_tools view_frames
# 等待 5 秒後會生成 frames.pdf
open frames.pdf  # Mac
# 或在 Windows Foxglove 中查看 TF 面板
```

**檢查標準:**
- [ ] `map → odom → base_link` 鏈路完整
- [ ] `base_link → camera_link` 存在
- [ ] `base_link → lidar_link` 存在
- [ ] 無 `WARN: TF lookup timeout` 訊息

**實測結果:**
- 狀態: ✅ / ❌
- TF 樹狀態: 完整 / 有斷鏈 / 嚴重錯誤
- 斷鏈位置 (若有):
- frames.pdf 截圖: [附加截圖]

---

### ✅/❌ 5. Foxglove 連線與可視化

**測試步驟:**
1. 在 Windows 開啟 Foxglove Studio
2. 連線至 `ws://192.168.1.177:8765`
3. 設定以下面板:
   - 3D 視圖 (顯示 TF 與點雲)
   - Image (顯示 `/camera/image_raw`)
   - Map (顯示 `/map`)
   - LaserScan (顯示 `/scan`)

**檢查標準:**
- [ ] WebSocket 連線成功
- [ ] 3D 視圖正常顯示機器狗模型
- [ ] 影像串流流暢 (> 10 FPS)
- [ ] 地圖逐漸建立 (黑白網格)
- [ ] LiDAR 掃描線正常顯示

**實測結果:**
- 狀態: ✅ / ❌
- 連線延遲: ____ ms
- 影像 FPS: ____ (實測)
- 地圖顯示: 正常 / 花屏 / 未顯示
- 截圖: [附加 Foxglove 截圖]

**問題記錄:**

---

### ✅/❌ 6. 建圖與地圖存檔

**測試步驟:**
```bash
# Terminal 4
zsh phase1_test.sh t4
# 輸入: auto  (自動巡房 ~60 秒)

# 巡房完成後,儲存地圖
zsh phase1_test.sh save_map
```

**檢查標準:**
- [ ] 機器狗能正常移動 (前進/左轉/右轉)
- [ ] Foxglove 中地圖逐漸擴大
- [ ] 地圖涵蓋範圍 > 3x3 公尺
- [ ] 地圖檔案成功儲存

**實測結果:**
- 狀態: ✅ / ❌
- 移動距離: 約 ____ 公尺
- 建圖時間: ____ 秒
- 地圖檔案位置: `maps/phase1.yaml` + `maps/phase1.pgm`
- 檔案大小:
  - phase1.yaml: ____ KB
  - phase1.pgm: ____ KB
- 地圖品質: 清晰 / 模糊 / 有斷層

**地圖截圖:** [附加 Foxglove 地圖截圖]

---

### ✅/❌ 7. Nav2 自動導航測試

**測試指令:**
```bash
zsh phase1_test.sh nav_test
# 或在 Foxglove 中使用 2D Goal Pose 工具
```

**測試流程:**
1. 在 Foxglove 設定機器狗當前位置 (2D Pose Estimate)
2. 點擊地圖任意位置設定目標點 (2D Goal Pose)
3. 觀察機器狗是否自動導航過去

**檢查標準:**
- [ ] Nav2 接收目標點
- [ ] 規劃出路徑 (綠色/藍色軌跡)
- [ ] 機器狗開始移動
- [ ] 成功到達目標點 (誤差 < 30cm)

**實測結果:**
- 狀態: ✅ / ❌
- 測試次數: ____ 次
- 成功次數: ____ 次
- 成功率: ____ %
- 平均導航時間: ____ 秒
- 誤差距離: ____ cm (平均)

**失敗原因 (若有):**
- [ ] 路徑規劃失敗
- [ ] 碰撞偵測誤判
- [ ] 機器狗卡住
- [ ] Nav2 Timeout
- [ ] 其他:

**錯誤訊息:**

---

## 📊 測試總結

### 通過統計
- 通過項目: ____ / 7
- 及格標準: ≥ 6 項通過
- **測試結果:** ✅ 通過 / ❌ 未通過

### 整體評估

**✅ 優點:**
1.
2.
3.

**⚠️ 待改進:**
1.
2.
3.

**🔴 嚴重問題:**
1.
2.

---

## 🛠️ 問題排查記錄

### 問題 1: [標題]

**現象描述:**


**根本原因:**


**解決方案:**


**驗證結果:**


---

### 問題 2: [標題]

**現象描述:**


**根本原因:**


**解決方案:**


**驗證結果:**


---

## 📸 測試截圖

### 1. Foxglove 完整畫面
![Foxglove 主界面](截圖路徑)

### 2. SLAM 建圖過程
![地圖建立](截圖路徑)

### 3. Nav2 路徑規劃
![導航路徑](截圖路徑)

### 4. Terminal 輸出
![終端訊息](截圖路徑)

### 5. TF 樹狀圖
![frames.pdf](截圖路徑)

---

## 📝 系統資訊記錄

### 硬體環境
- Mac 型號: Apple M1 / M2 / M3
- RAM: ____ GB
- UTM 版本: ____
- 虛擬機 CPU: ____ 核心
- 虛擬機 RAM: ____ GB

### 軟體環境
- Ubuntu 版本: 22.04
- ROS2 版本: Humble
- Go2 韌體版本: v1.1.7 / 其他: ____
- 專案 Git Commit: `git rev-parse --short HEAD` → ________

### 網路環境
- Mac Wi-Fi IP: 192.168.12.____
- VM enp0s2 IP: 192.168.12.222
- Windows IP: 192.168.1.____
- Go2 IP: 192.168.12.1
- Ping 延遲 (Mac → Go2): ____ ms

---

## 🚀 下一步行動

### 若測試通過 (≥ 6/7)
- [ ] 更新 `docs/00-overview/conformance_check_plan.md` (完成度 → 65%)
- [ ] 更新 `TEAM_PROGRESS_TRACKER.md` (A組進度)
- [ ] 準備 Phase 2 測試環境 (4-5 坪空間)
- [ ] 開始 Phase 2: 座標轉換開發 (11/27)

### 若測試未通過 (< 6/7)
- [ ] 逐項排查失敗原因
- [ ] 參考 `docs/01-guides/slam_nav/phase1_execution_guide.md` 故障排查章節
- [ ] 若無法自行解決,在週會 (11/26) 提出討論
- [ ] 重新測試直到通過

---

## 📅 時間記錄

- 測試開始時間: ____:____
- 測試結束時間: ____:____
- 總耗時: ____ 分鐘
- 問題排查耗時: ____ 分鐘

---

**測試完成日期:** 2025/11/__
**簽名確認:** Roy
**審查者:** (週會後填入)
**審查日期:** 2025/11/26
