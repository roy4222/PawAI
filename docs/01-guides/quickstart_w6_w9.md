# W6-W9 開發快速啟動指南

**目標讀者：** FJU Go2 專題組成員
**預計時長：** 4 週（W6-W9）
**最終目標：** 在 Isaac Sim 中完成端到端尋物 Demo

---

## ⚡ 快速導航 (依你的組別跳轉)

> **重要提示 (2025/11/23 更新):**
> - **A組 (Roy):** 環境已建好,不需從零開始!直接跳到 [W7: 座標轉換開發 I](#w7座標轉換-i)
> - **B組:** GPU 伺服器管理,優先閱讀 [Isaac Sim 整合指南](../02-design/isaac_sim_integration.md)
> - **C組:** VLM 開發,優先閱讀 [COCO VLM 開發指南](../02-design/coco_vlm_development.md)

### 📂 各組快速連結

| 組別 | 當前階段 | 推薦文件 | 跳轉章節 |
|------|---------|---------|---------|
| **A組 (Roy)** | ✅ 環境完成,開始座標轉換 | [座標轉換設計](../02-design/coordinate_transformation.md) | [W7 座標轉換](#w7座標轉換-i) |
| **B組** | 🔥 GPU 伺服器連線 | [Isaac Sim 整合](../02-design/isaac_sim_integration.md) | [W8 Isaac Sim](#w8座標轉換-ii--isaac-sim) |
| **C組** | 🔥 YOLO 本地測試 | [COCO VLM 開發](../02-design/coco_vlm_development.md) | [W6 VLM 雛形](#day-3-4gemini-vlm-節點) |

### 🎯 W6 任務重新定位 (2025/11/23 更新)

**原規劃:** W6 = 環境建置週
**當前實況:** A組環境已完成,W6 改為「核心算法開發週」

| 組別 | W6 實際任務 | 完成標準 |
|------|------------|---------|
| **A組** | Phase 1 測試 + 準備座標轉換 | Phase 1 七項檢查通過 |
| **B組** | GPU 伺服器連線突破 | VNC/NoMachine 遠端桌面可用 |
| **C組** | YOLO 本地測試 + 座標格式定案 | 能輸出 center [u,v] 座標 |

---

**專案結構假設：**
```
~/workspace/
└── fju-go2-sdk/              # 本專案（Git 倉庫根目錄）
    ├── src/                  # ROS2 套件目錄
    │   ├── go2_robot_sdk/
    │   ├── go2_interfaces/
    │   └── ...
    ├── requirements.txt      # Python 依賴（專案根目錄）
    ├── build/                # colcon build 輸出
    ├── install/              # colcon install 輸出
    └── log/                  # colcon 日誌
```

---

## 📅 週次概覽 (2025/11/23 更新)

| 週次 | 核心任務 | 驗收標準 | 預估工時 |
|------|---------|---------|----------|
| **W6** | 環境建置 + VLM 雛形 | ROS2 正常、VLM 節點訂閱影像 | 12-16 小時 |
| **W7** | 座標轉換 I | 圖像座標 → 本體座標（誤差 < 20cm） | 10-14 小時 |
| **W8** | 座標轉換 II + Isaac Sim | 世界座標轉換 + 模擬器運行 | 12-16 小時 |
| **W9** | 尋物 FSM + 測試 | 端到端成功率 > 70% | 14-18 小時 |

---

## 🚀 W6：環境突破週

### 目標
解決所有環境依賴問題，建立 VLM 節點基礎框架。

### Day 1-2：ROS2 環境配置

#### ✅ Checklist

**步驟 1：修復網路問題（WSL/VM）**
```bash
# 檢查 DNS
cat /etc/resolv.conf

# 若使用 WSL，設定 DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf
# 或編輯 /etc/wsl.conf 永久設定

# 測試網路
ping google.com
curl https://pypi.org
```

**步驟 2：安裝 ROS2 Humble**
```bash
# 快速安裝腳本
sudo apt update && sudo apt install -y curl gnupg lsb-release

sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  -o /usr/share/keyrings/ros-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] \
  http://packages.ros.org/ros2/ubuntu $(lsb_release -cs) main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null

sudo apt update
sudo apt install ros-humble-desktop-full python3-rosdep python3-colcon-common-extensions

# 設定環境
echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
source ~/.bashrc

# 初始化 rosdep
sudo rosdep init
rosdep update
```

**驗證**：
```bash
ros2 --version  # 應顯示 humble
ros2 topic list  # 應無錯誤
```

**步驟 3：編譯現有專案**
```bash
cd ~/workspace/fju-go2-sdk

# 安裝依賴
rosdep install --from-paths src --ignore-src -r -y
uv pip install -r requirements.txt --force-reinstall  # 專案根目錄的 requirements.txt

# 編譯
colcon build

# Source
source install/setup.bash

# 驗證
ros2 pkg list | grep go2
```

**🎯 Day 2 驗收**：`colcon build` 成功，無錯誤訊息。

---

### Day 3-4：Gemini VLM 節點

#### ✅ Checklist

**步驟 1：申請/取得 Gemini API Key**
```bash
# 設定環境變數
export GEMINI_API_KEY="your_api_key_here"
echo 'export GEMINI_API_KEY="your_key"' >> ~/.bashrc
```

**步驟 2：建立 vision_vlm 套件**
```bash
cd ~/workspace/fju-go2-sdk/src

ros2 pkg create --build-type ament_python vision_vlm \
  --dependencies rclpy sensor_msgs vision_msgs cv_bridge std_msgs

# 建立目錄結構
cd vision_vlm
mkdir -p config launch test
```

**步驟 3：複製範例程式碼**
```bash
# 從文件中複製以下檔案：
# - vision_vlm/gemini_api_client.py
# - vision_vlm/detection_converter.py
# - vision_vlm/gemini_vlm_node.py
# - config/vlm_params.yaml
# - launch/vlm_standalone.launch.py

# 參考：docs/02-design/gemini_vlm_backup.md
```

**步驟 4：安裝 Python 依賴**
```bash
uv pip install google-generativeai pillow numpy --force-reinstall
```

**步驟 5：編譯與測試**
```bash
cd ~/workspace/fju-go2-sdk
colcon build --packages-select vision_vlm
source install/setup.bash

# 測試 API（獨立測試）
python3 src/vision_vlm/vision_vlm/gemini_api_client.py

# 啟動節點（需相機 topic）
ros2 launch vision_vlm vlm_standalone.launch.py
```

**🎯 Day 4 驗收**：VLM 節點能訂閱 `camera/image_raw` 並輸出測試結果。

---

### Day 5：整合與除錯

```bash
# 啟動完整系統測試
export ROBOT_IP="192.168.1.100"  # 或使用模擬器
ros2 launch go2_robot_sdk robot.launch.py vlm:=true

# 監控
ros2 topic echo /detected_objects
ros2 topic hz camera/image_raw
```

**🎯 W6 結束驗收**：
- ✅ ROS2 環境完全正常
- ✅ VLM 節點能識別測試影像中的物體
- ✅ Gemini API 調用成功率 > 90%

---

## 🎯 W7：座標轉換 I

### 目標
實現 **2D 像素座標 → 3D 本體座標** 轉換。

### Day 1-2：建立套件與工具函數

```bash
# 建立套件
cd ~/workspace/fju-go2-sdk/src
ros2 pkg create --build-type ament_python coordinate_transformer \
  --dependencies rclpy sensor_msgs geometry_msgs vision_msgs tf2_ros cv_bridge message_filters

# 安裝依賴
uv pip install scipy --force-reinstall

# 複製程式碼
# - projection_utils.py
# - lidar_projection_node.py
# - config/transformer_params.yaml
# 參考：docs/02-design/coordinate_transformation.md
```

### Day 3-4：實作 LiDAR 投影

**關鍵步驟**：
1. 訂閱 `point_cloud2` 與 `camera_info`（同步）
2. 將點雲從 `base_link` 轉到 `camera_link`（TF2）
3. 投影 3D 點到 2D 圖像（內參矩陣）
4. 建立像素 → 3D 點的查找表

**除錯技巧**：
```bash
# 檢查 TF 樹
ros2 run tf2_tools view_frames
evince frames.pdf

# 檢查相機內參
ros2 topic echo camera/camera_info --once

# 可視化點雲
rviz2
# 新增 PointCloud2 顯示
```

### Day 5：校正與測試

**測試方法**：
1. 在地面放置已知位置的物體（如紙箱）
2. 使用捲尺測量真實座標
3. 讓 VLM 識別物體
4. 比較轉換後的座標與真實值

**記錄數據**：
```yaml
test_object_1:
  ground_truth: [2.5, 1.0, 0.0]  # 手動測量（m）
  estimated: [2.48, 1.05, 0.02]
  error_xy: 0.05m  # ✅ < 20cm
```

**🎯 W7 結束驗收**：
- ✅ 座標轉換節點正常運行
- ✅ 水平誤差 < 20cm（5 次測試平均）
- ✅ 在 RViz 中可視化轉換結果

---

## 🎮 W8：座標轉換 II + Isaac Sim

### 目標
1. 完成 **本體座標 → 世界座標** 轉換
2. 部署 Isaac Sim 環境

### Day 1-2：世界座標轉換

**修改 `lidar_projection_node.py`**：
```python
# 新增方法
def transform_to_map(self, point_base, timestamp):
    """將 base_link 座標轉換到 map"""
    transform = self.tf_buffer.lookup_transform(
        'map', 'base_link', timestamp,
        timeout=rclpy.duration.Duration(seconds=0.5)
    )
    # 使用 TF2 轉換...
    return point_world

# 發佈 PoseStamped
pose_msg = PoseStamped()
pose_msg.header.frame_id = 'map'
pose_msg.pose.position.x = point_world[0]
pose_msg.pose.position.y = point_world[1]
pose_msg.pose.position.z = point_world[2]
self.world_pose_pub.publish(pose_msg)
```

**測試**：
```bash
ros2 topic echo /object_pose_world
# 檢查 frame_id 是否為 'map'
```

### Day 3-5：Isaac Sim 部署

**快速安裝（本地）**：
```bash
# 1. 安裝 Miniconda（若未安裝）
wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh
conda config --set auto_activate_base false

# 2. 安裝 Isaac Sim（假設已有 Omniverse Launcher）
# 下載 Isaac Sim 2023.1.1

# 3. 設定環境變數
export ISAACSIM_PATH="${HOME}/.local/share/ov/pkg/isaac-sim-2023.1.1"
echo 'export ISAACSIM_PATH="${HOME}/.local/share/ov/pkg/isaac-sim-2023.1.1"' >> ~/.bashrc

# 4. 安裝 IsaacLab (Orbit)
cd ~/workspace
git clone https://github.com/isaac-sim/IsaacLab.git --branch v0.3.1
cd IsaacLab
ln -s ${ISAACSIM_PATH} _isaac_sim
./orbit.sh --conda
conda activate orbit
./orbit.sh --install --extra rsl_rl

# 5. 安裝 go2_omniverse
cd ~/workspace
git clone https://github.com/abizovnuralem/go2_omniverse.git --recurse-submodules
cd go2_omniverse

# 複製配置文件
mkdir -p ~/workspace/IsaacLab/source/data/sensors/lidar
cp Isaac_sim/Unitree/Unitree_L1.json \
   ~/workspace/IsaacLab/source/data/sensors/lidar/

# 6. 啟動測試
./run_sim.sh
# 應開啟 Isaac Sim 視窗，WASD 控制
```

**Docker 替代方案（若本地安裝失敗）**：
```bash
docker pull nvcr.io/nvidia/isaac-sim:2023.1.1
# 參考：docs/02-design/isaac_sim_integration.md 的 Docker 章節
```

**🎯 W8 結束驗收**：
- ✅ 座標轉換完整鏈路通暢（2D → world）
- ✅ Isaac Sim 正常運行（WASD 控制測試）
- ✅ 在模擬器中完成一次 SLAM 建圖

---

## 🏁 W9：尋物 FSM + 測試

### 目標
實現完整尋物流程，達成 70% 成功率。

### Day 1-2：狀態機開發

```bash
# 建立套件
cd ~/workspace/fju-go2-sdk/src
ros2 pkg create --build-type ament_python search_logic \
  --dependencies rclpy std_msgs geometry_msgs vision_msgs nav2_msgs action_msgs

# 複製程式碼
# - search_fsm_node.py
# - nav2_client.py
# - config/search_params.yaml
# 參考：docs/02-design/search_fsm_design.md

# 編譯
cd ~/workspace/fju-go2-sdk
colcon build --packages-select search_logic
```

### Day 3：整合測試

**啟動完整系統**：
```bash
# Terminal 1: Isaac Sim
cd ~/workspace/go2_omniverse
./run_sim.sh

# Terminal 2: ROS2 系統
cd ~/workspace/fju-go2-sdk
source install/setup.bash
export GEMINI_API_KEY="your_key"

ros2 launch go2_robot_sdk robot.launch.py \
  simulation:=true \
  vlm:=true \
  search:=true \
  slam:=true \
  nav2:=true

# Terminal 3: 發送指令
ros2 topic pub /search_command std_msgs/String "data: '找杯子'" --once

# Terminal 4: 監控結果
ros2 topic echo /search_result
```

### Day 4-5：20 次測試 + 數據分析

**測試腳本**：
```bash
# test_automation.sh
#!/bin/bash

for i in {1..20}; do
    echo "=== 測試 $i/20 ==="

    # 重置場景（手動或腳本）
    # ...

    # 發送指令
    ros2 topic pub /search_command std_msgs/String "data: '找杯子'" --once

    # 等待結果（最多 3 分鐘）
    timeout 180 ros2 topic echo /search_result --once

    # 記錄結果
    if [ $? -eq 0 ]; then
        echo "✅ 成功" >> test_results.log
    else
        echo "❌ 失敗" >> test_results.log
    fi

    sleep 10
done

# 統計
SUCCESS=$(grep -c "✅" test_results.log)
echo "成功率: $SUCCESS/20"
```

**數據記錄表格**：參考 `docs/03-testing/testing_plan.md` 測試矩陣。

**🎯 W9 結束驗收**：
- ✅ 端到端成功率 ≥ 70%（14/20）
- ✅ 平均尋物時間 < 3 分鐘
- ✅ 完整測試報告（含數據與改進建議）

---

## 🛠️ 常見問題與解決

### Q1: `colcon build` 失敗（找不到依賴）
```bash
# 重新安裝依賴
rosdep install --from-paths src --ignore-src -r -y --rosdistro humble

# 清理後重新編譯
rm -rf build/ install/ log/
colcon build
```

### Q2: Gemini API 超時
```bash
# 檢查網路
curl -v https://generativelanguage.googleapis.com

# 增加超時設定（在 gemini_api_client.py 中）
response = self.model.generate_content([prompt, image], request_timeout=30)
```

### Q3: Isaac Sim 黑屏/無法開啟
```bash
# 檢查 NVIDIA 驅動
nvidia-smi

# 檢查 Vulkan 支援
vulkaninfo | grep driver

# 若使用遠端（SSH），需 X11 forwarding
ssh -X user@remote
```

### Q4: TF2 查找失敗
```bash
# 檢查 TF 樹
ros2 run tf2_tools view_frames

# 檢查時間戳
ros2 topic echo /tf --field transforms[0].header.stamp
ros2 topic echo camera/image_raw --field header.stamp

# 增加容差
transform = tf_buffer.lookup_transform(
    'map', 'base_link', timestamp,
    timeout=rclpy.duration.Duration(seconds=1.0)  # 增加至 1 秒
)
```

### Q5: Nav2 導航卡住
```bash
# 調整 Nav2 參數（config/nav2_params.yaml）
inflation_radius: 0.15  # 從 0.25 降低
xy_goal_tolerance: 0.3  # 放寬目標容差

# 重新編譯
colcon build --packages-select go2_robot_sdk
```

---

## 📚 每日進度檢查表

### W6 Checklist
- [ ] Day 1: ROS2 Humble 安裝成功
- [ ] Day 2: 現有專案編譯通過
- [ ] Day 3: Gemini API 測試成功
- [ ] Day 4: VLM 節點訂閱影像正常
- [ ] Day 5: VLM 識別測試物體成功

### W7 Checklist
- [ ] Day 1: coordinate_transformer 套件建立
- [ ] Day 2: projection_utils.py 測試通過
- [ ] Day 3: LiDAR 投影邏輯實作完成
- [ ] Day 4: TF2 轉換測試成功
- [ ] Day 5: 校正誤差 < 20cm

### W8 Checklist
- [ ] Day 1: 世界座標轉換實作
- [ ] Day 2: 發佈 PoseStamped 到 /object_pose_world
- [ ] Day 3: Isaac Sim 安裝成功
- [ ] Day 4: go2_omniverse 啟動正常
- [ ] Day 5: 模擬器 SLAM 建圖成功

### W9 Checklist
- [ ] Day 1: search_logic 套件建立
- [ ] Day 2: 狀態機基本邏輯實作
- [ ] Day 3: 端到端測試首次成功
- [ ] Day 4: 完成 10 次測試
- [ ] Day 5: 完成 20 次測試 + 報告

---

## 🎯 成功的關鍵

1. **每天 Commit**：即使進度不完整，也要提交到 Git
2. **及早求助**：卡關超過 2 小時，立即詢問團隊/教授
3. **文檔優先**：先讀完對應的 docs/*.md，再寫程式
4. **測試驅動**：先寫測試，確保每個模組獨立可驗證
5. **Plan B 準備**：座標轉換、Isaac Sim 都有備用方案

---

## 📞 支援資源

- **技術文件**：`docs/` 目錄下的所有 .md 文件
- **範例程式碼**：每份文件都包含完整可執行的範例
- **測試腳本**：`docs/03-testing/testing_plan.md`
- **問題回報**：GitHub Issues（標籤：`help-wanted`）

---

**祝各位開發順利！W9 見！🚀**

**文件版本：** v1.0
**最後更新：** 2025/11/16
