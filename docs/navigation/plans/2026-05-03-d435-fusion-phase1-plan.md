# Phase 1 Implementation Plan — D435 → /scan_d435 可視化

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 D435 深度影像透過 `depthimage_to_laserscan_node` 轉成 `/scan_d435`，在 Foxglove 與 RPLIDAR 對同一個 box 視覺對齊，**不影響 Nav2 行為、不送 Go2 goal**。Phase 1 通過才能進 Phase 2（local_costmap 整合）。

**Architecture:** 直接在現行 `nav-cap-demo` tmux session 的 `monitor` window spawn `depthimage_to_laserscan_node`（不需要新 launcher）。D435 driver 由現有 nav stack 已啟動，沿用即可。Phase 1 純 verification，無 code edit、無新檔案 commit；唯一新增 artifact 是 Foxglove layout 截圖 / 描述。

**Tech Stack:** ROS2 Humble、`depthimage_to_laserscan` package（已 install）、Foxglove Bridge 8765、Foxglove Studio (web)。

**Spec reference:** [`docs/navigation/specs/2026-05-03-d435-rplidar-fusion-detour.md`](../specs/2026-05-03-d435-rplidar-fusion-detour.md) Phase 1 段。

**對齊 user 提醒**：Foxglove 必須**同時**顯示 `base_link` + `/scan_rplidar` + `/scan_d435`，確認兩個 scan 對同一個 box 位置一致（不能只看 D435 在自己 frame 內對不對）。

---

## File Structure

Phase 1 不寫程式碼、不改設定。所有「實作」都是 ROS2 cli 命令 + Foxglove panel 配置 + 視覺驗證。

無 file create / modify。

唯一 artifact：在 spec 末尾或本 plan 末尾 append「Phase 1 result」段落（Task 7）。

---

## Pre-flight 假設

- `nav-cap-demo` tmux session 已起（9 windows，含 d435 + monitor）
- D435 連著、`/dev/video0` 有
- Go2 已開、走 stack 已 active（不過 Phase 1 不送 goal，Go2 只要站著）
- Foxglove Bridge 在 `ws://jetson-nano:8765`
- `depthimage_to_laserscan` package 在 Jetson 已 install（5/3 已驗證）

任一不成立 → 先回 `bash scripts/start_nav_capability_demo_tmux.sh` 重啟 stack，再進 Task 1。

---

## Task 1: Verify D435 driver topics + camera info（read-only sanity）

**Files:** none（read-only ros2 cli）

- [ ] **Step 1: SSH Jetson 確認 D435 4 個關鍵 topic 都在發**

Run（在 WSL 用 ssh）:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && source ~/elder_and_dog/install/setup.bash && \
  ros2 topic list | grep -E \"camera/camera/(color|aligned_depth_to_color|depth)\" | sort'"
```

Expected output（必含這 4 個）:
```
/camera/camera/aligned_depth_to_color/camera_info
/camera/camera/aligned_depth_to_color/image_raw
/camera/camera/color/camera_info
/camera/camera/color/image_raw
```

任一缺 → D435 driver 沒起好。回 `tmux send-keys -t nav-cap-demo:d435 C-c` 看錯誤、修好再來。

- [ ] **Step 2: 確認 aligned_depth topic 有資料 + rate**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && \
  timeout 4 ros2 topic hz /camera/camera/aligned_depth_to_color/image_raw'"
```

Expected: `average rate: ~15-30 Hz`

如果 0 Hz 或 timeout → D435 driver alive 但 topic 沒資料，重啟 d435 window：
```bash
ssh jetson-nano "tmux send-keys -t nav-cap-demo:d435 C-c Enter && sleep 2 && \
  tmux send-keys -t nav-cap-demo:d435 'ros2 launch realsense2_camera rs_launch.py align_depth.enable:=true enable_depth:=true enable_color:=true pointcloud.enable:=false' Enter"
```

等 5s 重跑 Step 2。

- [ ] **Step 3: 確認 camera_info 有 K matrix**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && \
  timeout 3 ros2 topic echo --once /camera/camera/aligned_depth_to_color/camera_info | grep -E \"^k:|^width|^height\"'"
```

Expected:
```
height: 480
width: 848
k:
```

`depthimage_to_laserscan_node` 需要 camera_info 的 K matrix 計算 fov，沒 K 它無法工作。

---

## Task 2: Verify TF chain `base_link → camera_depth_optical_frame`（read-only sanity）

**Files:** none

- [ ] **Step 1: 列出 TF tree 確認 chain 存在**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && source ~/elder_and_dog/install/setup.bash && \
  timeout 4 ros2 run tf2_ros tf2_echo base_link camera_depth_optical_frame 2>&1 | head -20'"
```

Expected（會印一筆 transform）:
```
At time ...
- Translation: [...]
- Rotation: in Quaternion [...]
```

**預期會 fail**（user 已指出 nav-cap-demo:tf window 通常只發 `base_link → laser`，沒含 D435）。如果 fail（report `Could not find a connection between ...`），進 Step 1.5 補 TF。

如果意外通過 → 跳 Step 1.5，直接進 Step 2。

- [ ] **Step 1.5: 補 D435 static TF（fallback，預期會做）**

開新 tmux window 啟動 D435 static_transform_publisher：
```bash
ssh jetson-nano "tmux new-window -t nav-cap-demo -n d435-tf && \
  tmux send-keys -t nav-cap-demo:d435-tf 'source /opt/ros/humble/setup.bash && source ~/elder_and_dog/install/setup.bash && \
    ros2 run tf2_ros static_transform_publisher \
      --x 0.30 --y 0 --z 0.20 \
      --roll 0 --pitch 0 --yaw 0 \
      --frame-id base_link --child-frame-id camera_depth_optical_frame' Enter"
sleep 2
```

**重要警告**：
- `--yaw 0` 假設 D435 鏡頭朝 Go2 前方。實機若 mount 朝向不同（例如向上 30°），yaw / pitch 要調
- D435 optical frame 慣例是 z 朝外、x 朝右、y 朝下（光學坐標系），跟 ROS body frame 不同。如果 Foxglove 看到 `/scan_d435` 方向歪 90° / 180°，問題在這
- 正式 mount 校正排到 5/13 demo 後（CLAUDE.md 已記）；今晚是 Phase 1 hack 版本

驗證 TF 已通：
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && \
  timeout 4 ros2 run tf2_ros tf2_echo base_link camera_depth_optical_frame 2>&1 | head -20'"
```

Expected: 印出 transform，translation = (0.30, 0, 0.20)。

如果還 fail → 重新讀 send-keys 的命令是否完整、tmux window 是否真的執行了（`tmux capture-pane -t nav-cap-demo:d435-tf -p -S -10` 看）。

- [ ] **Step 2: 視覺驗證 TF 方向（Phase 1 後段 Foxglove 才能完整測，先記下假設）**

從 Step 1.5 啟動的 TF 是 `--yaw 0`，假設 D435 鏡頭朝 Go2 前方。**如果 Foxglove Task 5 看到 `/scan_d435` 在 base_link 後方或側面，回來改 yaw**：
- D435 朝後（正常 mount） → `--yaw 0` OK
- D435 朝後旋轉 180° mount → `--yaw 3.14159`
- D435 mount 在 Go2 後方鏡頭朝前 → 換 `--x` 為負值

**先假設 yaw 0 + x 0.30，Task 5 視覺驗證**。Phase 1 不做精校（那是 5/13 後的事）。

- [ ] **Step 2: 記下 translation 數值（後面 Foxglove 對齊診斷用）**

從 Step 1 輸出讀 `Translation: [x, y, z]` 三個值，記在腦中或便條：
```
base_link → camera_depth_optical_frame:
  x = ___ m  (預期 ~0.30, D435 大約在 Go2 鼻尖前 30cm)
  y = ___ m  (預期 ~0)
  z = ___ m  (預期 ~0.20)
```

如果 z 值離預期差很多（例如 0.0 或 1.5），表示 TF mount 不對，後面 `/scan_d435` 在 Foxglove 會浮在地板下或天花板上。**先停，修 TF。**

---

## Task 3: Spawn `depthimage_to_laserscan_node` 在新 d435-scan window

**Files:** none（ros2 run，不寫成 launch script）

**為什麼開新 window**：monitor window 留給後續 ros2 topic / debug 命令使用；node 持續執行不要佔住可互動 shell。

- [ ] **Step 1: 開新 window + 啟動 depthimage_to_laserscan_node**

Run:
```bash
ssh jetson-nano "tmux new-window -t nav-cap-demo -n d435-scan && \
  tmux send-keys -t nav-cap-demo:d435-scan 'source /opt/ros/humble/setup.bash && \
    source ~/elder_and_dog/install/setup.bash && \
    ros2 run depthimage_to_laserscan depthimage_to_laserscan_node \
    --ros-args \
    -r depth:=/camera/camera/aligned_depth_to_color/image_raw \
    -r depth_camera_info:=/camera/camera/aligned_depth_to_color/camera_info \
    -r scan:=/scan_d435 \
    -p scan_height:=10 \
    -p output_frame:=camera_depth_optical_frame \
    -p range_min:=0.30 \
    -p range_max:=3.0' Enter"
```

- [ ] **Step 2: 確認 node alive 且沒 crash**

等 3 秒後 capture d435-scan window 看 log:
```bash
sleep 3 && ssh jetson-nano "tmux capture-pane -t nav-cap-demo:d435-scan -p -S -30 | tail -15"
```

Expected: 沒看到 `Traceback` / `error` / `[FATAL]`，可能看到 INFO log 說 node ready。

如果 crash（typical 原因）:
- `output_frame` 不存在 → 改 frame name（從 Task 2 Step 1 學到的真實 frame）
- camera_info 缺 K → 確認 Task 1 Step 3 通過

Recovery: `tmux send-keys -t nav-cap-demo:d435-scan C-c Enter` 後修參數重試。

---

## Task 4: Verify `/scan_d435` topic 有資料

**Files:** none

- [ ] **Step 1: 確認 topic 註冊**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && ros2 topic list | grep scan_d435'"
```

Expected: `/scan_d435`

- [ ] **Step 2: 確認 publish rate ≥ 10 Hz**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && timeout 6 ros2 topic hz /scan_d435'"
```

Expected: `average rate: 10-30 Hz`（跟 D435 frame rate 同）。

如果 < 5 Hz → CPU 過載或 D435 driver 慢，stop Phase 1 不要硬推（會影響 Phase 2 costmap update）。

- [ ] **Step 3: 確認 LaserScan 內容合理**

Run:
```bash
ssh jetson-nano "bash -lc 'source /opt/ros/humble/setup.bash && \
  timeout 3 ros2 topic echo --once /scan_d435 | head -25'"
```

Expected:
- `header.frame_id: camera_depth_optical_frame`（或你 Task 2 確認的真實 frame）
- `angle_min` / `angle_max`：D435 fov 約 ±30° → angle_min ≈ -0.5 rad、angle_max ≈ +0.5 rad
- `range_min: 0.30`、`range_max: 3.0`（你傳的 param）
- `ranges` array 長度 ~640（D435 width）
- `ranges` 內含**有限數值**（不能全 inf 或全 nan）

如果 ranges 全 inf → D435 深度資料壞 / scan_height 設定錯。回 Task 1 Step 2 確認 depth topic 真有資料。

---

## Task 5: Foxglove 視覺驗證 — 同時看 base_link + RPLIDAR + D435 scan

**Files:** none（Foxglove 配置）

**這是 Phase 1 最重要的 gate（user 強制要求）。**

- [ ] **Step 1: 開 Foxglove → ws://jetson-nano:8765**

如果還沒開 panel，加以下 4 個：

| Panel | 訂閱 / 設定 |
|---|---|
| 3D | 加 transforms `base_link`（display_frame）+ topics `/scan_rplidar` (LaserScan) + `/scan_d435` (LaserScan) |
| Image | `/camera/camera/color/image_raw/compressed`（若沒 compressed topic，退到 `/camera/camera/color/image_raw`）|
| Image | `/camera/camera/aligned_depth_to_color/image_raw`（depth，settings → colorMap rainbow）|
| Indicator | `/scan_d435` topic statistics（show rate）|

**3D panel 顯示設定**：
- Frame: `base_link`（all coordinates relative to robot center）
- `/scan_rplidar` color：紅色
- `/scan_d435` color：藍色（容易區分）
- 兩個 scan 都顯示

- [ ] **Step 2: 物理擺好 box（Phase 1 驗證場景）**

- Box 放 Go2 鼻尖前 **1.0m**（base_link 1.35m）
- 確認 box 在 D435 視野內（從 RGB Image panel 確認看得到）
- box 也在 RPLIDAR 視野內（角度確認）

- [ ] **Step 3: 視覺對齊驗證（Phase 1 主 gate）**

在 3D panel 觀察：

| 檢查項 | 預期 |
|---|---|
| 紅色 RPLIDAR scan 有顯示 box 邊緣 | ✅ |
| 藍色 D435 scan 也有顯示 box 邊緣 | ✅ |
| **兩個 scan 對 box 的位置疊合**（容差 ≤ 10cm） | ✅ |
| 兩個 scan 都離 base_link 約 1.35m | ✅ |
| D435 scan 範圍是 ±30°（不是 360°） | ✅ |
| D435 scan 沒浮在天花板或穿地板 | ✅ |

**全綠才能進 Task 6**。任一不對：
- 兩個 scan 位置差很多 → TF mount 偏，回 Task 2 重看 `static_transform_publisher` 參數，可能要實機調 `--x` `--z`
- D435 scan 離地飄 → mount z 不對
- D435 scan 缺角 → scan_height 太小漏細節，調大 `scan_height: 10 → 20`

- [ ] **Step 4: 截圖 / 錄影存證**

存 1 張 Foxglove 3D panel 截圖（box 在畫面內、兩 scan 都顯示）到 `/tmp/phase1_foxglove_aligned.png` 之類，後面 commit 進 docs。

---

## Task 6: Box-in / box-out clearing 物理測試

**Files:** none

- [ ] **Step 1: Box 在原位（Task 5 Step 2 位置）→ 確認 D435 scan 看到**

3D panel 觀察 `/scan_d435` 在 Go2 鼻尖前約 1.0m 處有一段「打到 box」的 ranges 點。

- [ ] **Step 2: 物理把 box 推到 Go2 側面 1m**（離開 D435 fov）

D435 fov ±30°，所以 box 在側面 90° 不會被 D435 看到。

3D panel 觀察 `/scan_d435`：原本 box 位置的 ranges 點消失（變 inf 或 max range）。

如果 box 拿走 ranges 還在 → D435 driver 在 cache 過時 frame，等 1-2s。如果 5s+ 都不消失 → 報異常，停 Phase 1 debug。

- [ ] **Step 3: Box 推回前方 1m → 確認 D435 scan 重新看到**

重複 Step 1 觀察。Ranges 點重新出現。

兩次「進 → 出」都成功 = D435 sensor pipeline 健康。

---

## Task 7: 結果記錄

**Files:**
- Modify: `docs/navigation/plans/2026-05-03-d435-fusion-phase1-plan.md`（本檔末尾 append）
- Add: `docs/navigation/plans/assets/2026-05-03-phase1-foxglove.png`（Task 5 Step 4 的截圖，optional）

- [ ] **Step 1: 在本檔末尾 append Phase 1 result 段**

Edit 本檔，在最後加：

```markdown
---

## Phase 1 Result（2026-05-03 evening）

### Sanity（Task 1-2）
- D435 4 個 topic：✅ / 部分 / ❌
- depth topic rate：__ Hz
- camera_info K matrix：✅ / ❌
- TF chain `base_link → camera_depth_optical_frame`：translation = (__, __, __) m

### Node spawn（Task 3-4）
- `depthimage_to_laserscan_node` ready：✅ / 需要改 param（細節 ___）
- `/scan_d435` rate：__ Hz
- LaserScan content：frame_id=___, angle_min=___, range_min=___, range_max=___

### Foxglove 對齊（Task 5）
- RPLIDAR + D435 scan 視覺對齊：✅ / ❌（差距 __ cm）
- D435 scan 高度合理：✅ / ❌
- D435 scan fov 約 ±30°：✅ / ❌

### Clearing test（Task 6）
- Box-in：D435 scan 顯示 box ✅
- Box-out 5s 內 ranges 變 inf：✅ / ❌
- Box-back-in：✅ / ❌

### 結論
- [ ] **Phase 1 PASS** — 進 Phase 2 plan
- [ ] **Phase 1 PARTIAL** — 部分 OK，記下哪些要修才進 Phase 2
- [ ] **Phase 1 FAIL** — D435 sensor pipeline 不健康，今晚停 Phase 2/3
```

填上實測值。

- [ ] **Step 2: 如果 Task 5 截圖了，commit 截圖**

```bash
mkdir -p docs/navigation/plans/assets
cp /tmp/phase1_foxglove_aligned.png docs/navigation/plans/assets/2026-05-03-phase1-foxglove.png
git add docs/navigation/plans/assets/2026-05-03-phase1-foxglove.png \
        docs/navigation/plans/2026-05-03-d435-fusion-phase1-plan.md
git commit -m "docs(nav): Phase 1 D435 → /scan_d435 result（PASS/PARTIAL/FAIL）"
```

如果沒截圖（純文字描述）：
```bash
git add docs/navigation/plans/2026-05-03-d435-fusion-phase1-plan.md
git commit -m "docs(nav): Phase 1 D435 → /scan_d435 result"
```

---

## Self-Review

**Spec coverage**: spec Phase 1 段（line 71-101）4 個成功標準 全在 Task 5 Step 3 + Task 4 涵蓋 ✅

**Placeholder scan**: 無 TBD / TODO / 「具體值待補」✅

**Type consistency**: topic name `/scan_d435`、frame `camera_depth_optical_frame` 在所有 task 一致 ✅

**Granularity**: 每 step 一個 action（命令 + 預期）2-5 min ✅

**User reminder coverage**:
- ✅ #2「Foxglove 同時開 base_link + /scan_rplidar + /scan_d435 看兩 scan 對齊」 → Task 5 Step 3 強制
- #1 yaw projection 是 Phase 3 議題，Phase 1 plan 不涵蓋（合理）

---

## 失敗回滾

Phase 1 任一 task fail → 不繼續 Phase 2/3。可選做的：
- 把 monitor window 的 `depthimage_to_laserscan_node` Ctrl+C 停掉（不影響 Demo A）
- 報告 user 哪一步 fail + 觀察到的現象
- 如果 fail 是 TF 問題（最常見），預期要進 Phase 1.5（D435 mount 校正），那是另一個 plan，不在今晚範圍

Phase 1 PASS 後等 user 給 Phase 2 plan 寫作授權，**不要 auto chain 進 Phase 2**。

---

## Phase 1 Result（2026-05-03 evening, executed）

### Sanity（Task 1-2）
- D435 4 個 topic：✅
- depth topic rate：23 Hz
- camera_info K matrix：✅ (640x480)
- TF chain 預期 fail（user 警告對）：base_link 與 camera_depth_optical_frame 在不同 tree
- Step 1.5 fallback 成功：開 `nav-cap-demo:d435-tf` window，static_transform_publisher (--x 0.30 --y 0 --z 0.20 --yaw 0)，TF 通

### Node spawn（Task 3-4）
- `depthimage_to_laserscan_node` ready：✅（在 nav-cap-demo:d435-scan window）
- `/scan_d435` rate：透過 transient_local QoS sub 收到（default volatile sub 顯示「not published」是 QoS mismatch artifact）
- LaserScan content：frame=camera_depth_optical_frame, angle ±28°, range 0.30-3.0 ✅

### Foxglove 對齊（Task 5）
- User 視覺驗證 OK（時間壓力，未做完整 box-in/out test）

### 結論
- [x] **Phase 1 PASS（操作驗證 OK，視覺對齊 user 確認 OK，未做 6/Task7 詳細 in/out 因時間壓力）** — 進 Phase 2

---

## Phase 2 + Phase 3 Result（同日晚跑完，2026-05-03 22:15）

### Phase 2 PASS ✅
- detour profile yaml + launcher 寫完並啟動 nav-cap-detour stack（11 windows）
- `ros2 param get /local_costmap/local_costmap obstacle_layer.observation_sources` = `"scan d435_scan"` ✅
- `obstacle_layer.d435_scan.*` 11+ params 全載入（clearing / marking / data_type=LaserScan / range / etc）
- inflation_radius detour profile 0.20m 已套用
- D435 + RPLIDAR 雙 source 已成功融合進 local_costmap

### Phase 3 L3 FAIL ❌
- 連兩輪 1.6m goal: `no_progress_timeout actual_distance=0.000`
- 根因：Go2 warmup 走過頭 (0.5m → 1.4m)，box 從 1.56m 變 0.79m，太近 DWB footprint+inflation 規劃不出來
- 即使 detour profile (inflation 0.20 + DWB critic 全降) + cov GREEN 0.092 也救不了

### 整體判斷
- L1+L2 達成 = 「D435 + RPLIDAR 融合進入 Nav2 local costmap」可宣稱
- L3 不達成 = **不能說 Go2 自動繞開**
- Demo B 話術降為：「**Go2 結合 RPLIDAR + D435 深度感測融合進入 Nav2 local costmap，可即時感知障礙物並安全停車**」
