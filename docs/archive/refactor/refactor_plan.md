# PawAI 專案重構計畫 (Nano Super v5.0) - 修正版

**日期**: 2026-02-10  
**目標**: 升級至 Nano Super 架構，整合 OpenClaw，重構 Skills 化架構  
**範圍**: 全專案結構重組、套件遷移、功能升級  
**狀態**: ⚠️ **待修正後執行** (原 plan 有前置條件未滿足)

---

## 0) 前置驗證條件 (執行前必須完成)

> ⚠️ **重要**: 以下 4 項為執行本計畫的前置條件，未驗證前不得執行對應步驟。

| # | 驗證項目 | 目前狀態 | 風險 | 驗證方法 |
|---|---------|---------|------|---------|
| 1 | **lidar_processor Python 可刪除性** | ❌ robot.launch.py 仍在引用 Python 版節點 | 🔴 **高** - 直接刪除會導致 launch 失敗 | 1. 先驗證 lidar_processor_cpp 功能完整<br>2. 更新 robot.launch.py 改用 C++ 版<br>3. 測試通過後才可刪除 Python 版 |
| 2 | **Obstacle.msg / ObstacleList.msg 存在性** | ❌ 尚未建立 | 🟡 **中** - plan 誤植為既有前提 | 1. 在 go2_interfaces 新增 msg 定義<br>2. 執行 colcon build 生成介面<br>3. 驗證其他套件可正常引用 |
| 3 | **Git 歷史重寫安全性** | ⚠️ repo 有 submodule + 大檔 | 🔴 **高** - filter-repo 可能破壞 submodule | 1. **先完整鏡像備份** (git clone --mirror)<br>2. 考慮改用 `git rm --cached` + .gitignore 而非重寫歷史<br>3. 如必須重寫，先在測試 repo 驗證 |
| 4 | **Nav2 Action via rosbridge 穩定性** | ⚠️ send_action_goal 存在但未實測 | 🟡 **中** - 不能假設穩定 | 1. 實測 `send_action_goal` 走 rosbridge 端到端<br>2. 驗證 feedback / result / cancel 流程<br>3. 測試失敗時規劃替代方案 (如走原生 ROS2) |

---

## 1) 專案現況總覽

### 1.1 專案結構問題

目前專案存在以下結構性問題：

| 問題 | 嚴重程度 | 影響 | 備註 |
|-----|---------|------|------|
| ROS2 套件散佈根目錄 | 🔴 高 | 違反 colcon 慣例 | **Phase 3** 執行 (低風險後移) |
| Git 倉庫髒亂 (二進制檔案) | 🔴 高 | 21.4MB 無用數據 | **Phase 4** 執行 (需先鏡像備份) |
| lidar_processor Python/C++ 冗餘 | 🔴 高 | 維護困難 | **前置條件 #1** 驗證後才可刪除 |
| coco_detector 過時 | 🟡 中 | 需升級 YOLO-World | **Phase 2** 執行 |
| MCP 工具過於通用 | 🟡 中 | 需 Skills 化 | **Phase 1** 優先執行 (最低風險) |

### 1.2 套件分布現況

**根目錄散落套件** (需遷移至 `src/`):
- `go2_robot_sdk/` - 主驅動套件
- `go2_interfaces/` - 自定義訊息
- `lidar_processor/` - Python LiDAR 處理 (標記刪除)
- `lidar_processor_cpp/` - C++ LiDAR 處理
- `coco_detector/` - COCO 偵測器 (標記替換)
- `speech_processor/` - TTS 語音

**已在正確位置**:
- `src/search_logic/` - Nav2 測試套件

**獨立 Python 套件** (不移動):
- `ros-mcp-server/` - MCP 伺服器

---

## 2) 各套件詳細分析

### 2.1 go2_robot_sdk (主驅動套件)

**位置**: `/go2_robot_sdk/` → 遷移至 `/src/go2_robot_sdk/`

**Clean Architecture 分層**:
```
go2_robot_sdk/go2_robot_sdk/
├── domain/                 # ✅ 無 ROS2 依賴
│   ├── entities/           # RobotConfig, RobotData
│   ├── interfaces/         # IRobotController, IRobotDataPublisher
│   ├── constants/          # RTC_TOPIC, ROBOT_CMD
│   └── math/               # Quaternion, Vector3
├── application/            # ✅ 無 ROS2 依賴
│   ├── services/           # RobotDataService, RobotControlService
│   └── utils/              # command_generator
├── infrastructure/         # ⚠️ ROS2 依賴
│   ├── webrtc/             # WebRTCAdapter, Go2Connection
│   ├── ros2/               # ROS2Publisher
│   └── sensors/            # LidarDecoder, CameraConfig
└── presentation/           # ⚠️ ROS2 節點
    └── go2_driver_node.py
```

**現有服務**:
| 服務 | 檔案 | 功能 |
|-----|------|------|
| go2_driver_node | `main.py` + `go2_driver_node.py` | 主驅動節點 |
| snapshot_service | `snapshot_service.py` | `/capture_snapshot` 相機截圖 |
| move_service | `move_service.py` | `/move_for_duration` 安全移動 |

**安全限制** (move_service):
- MAX_LINEAR = 0.3 m/s
- MAX_ANGULAR = 0.5 rad/s
- MAX_DURATION = 10.0 s
- 緊急停止: `/stop_movement`

**待補服務**:
- [ ] move_service 未在 robot.launch.py 中啟動
- [ ] Nav2 Action Service (`/navigate_to_pose_simple`)
- [ ] Sensor Gateway 節點

---

### 2.2 go2_interfaces (介面定義)

**位置**: `/go2_interfaces/` → 遷移至 `/src/go2_interfaces/`

**現有訊息 (以目錄為準；目前 31 個)**:

| 類別 | 訊息 | 用途 |
|-----|------|------|
| **機器人狀態** | Go2State | 運動狀態 (位置、速度、障礙物距離) |
| **感測器** | IMU, LidarState | IMU 數據、LiDAR 狀態 |
| **控制** | WebRtcReq | WebRTC 指令 (api_id, topic, parameter) |
| **底層** | LowState, LowCmd | 馬達、電池、腳力 |
| **特殊** | VoxelMapCompressed | 壓縮體素地圖 |

**現有服務**:
- `MoveForDuration.srv` - 安全移動請求/回應

**需新增訊息 (前置條件 #2)**:

⚠️ **注意**: 以下訊息目前**不存在**，需要在 go2_interfaces 新增：

```msg
# msg/ObstacleList.msg
std_msgs/Header header
Obstacle[] obstacles
float32 processing_time_ms
string algorithm_version

# msg/Obstacle.msg
int32 id
float64[3] center
float64[3] size
int32 point_count
float32 confidence
```

**新增流程**:
1. [ ] 建立 `msg/Obstacle.msg` 和 `msg/ObstacleList.msg`
2. [ ] 更新 `CMakeLists.txt` 加入新訊息
3. [ ] 執行 `colcon build --packages-select go2_interfaces`
4. [ ] 驗證其他套件可正常 `import go2_interfaces.msg`
5. [ ] 提交並測試通過後才可被 sensor_gateway 引用

---

### 2.3 lidar_processor (Python) - ⚠️ **禁止直接刪除**

**狀態**: 🔴 **前置條件 #1 未滿足 - 不可刪除**

> ⚠️ **警告**: robot.launch.py 目前仍引用 Python 版節點，直接刪除會導致 launch 失敗。

**檔案**:
- `lidar_to_pointcloud_node.py` - 點雲聚合與儲存
- `pointcloud_aggregator_node.py` - 點雲過濾

**Python 版本獨特功能** (需確認 C++ 有無):

| 功能 | Python 實現 | C++ 狀態 | 驗證方法 |
|-----|------------|---------|---------|
| Open3D 地圖儲存 | ✅ | ❓ | 檢查 C++ 版有無 .ply 輸出 |
| 統計離群值移除 | ✅ (自實現) | ✅ (PCL) | 檢查 PCL StatisticalOutlierRemoval |
| Range 過濾 (0.1-20m) | ✅ | ❓ | 檢查 C++ 版參數 |
| Height 過濾 (-2-3m) | ✅ | ❓ | 檢查 C++ 版參數 |
| 動態降取樣 | ✅ | ❓ | 檢查 C++ 版 voxel 設定 |

**啟動檔引用檢查**:
```bash
# 檢查哪些 launch 檔引用 lidar_processor
grep -R "lidar_processor" go2_robot_sdk/launch/
# 結果: go2_robot_sdk/launch/robot.launch.py 使用 lidar_processor (lidar_to_pointcloud/pointcloud_aggregator)
```

**安全刪除流程**:
1. [ ] 驗證 lidar_processor_cpp 功能完整 (見上表)
2. [ ] 更新 robot.launch.py 改用 C++ 版節點
3. [ ] colcon build 測試通過
4. [ ] 實機測試 LiDAR 流程正常
5. [ ] **才可刪除 Python 版**

---

### 2.4 lidar_processor_cpp (保留)

**位置**: `/lidar_processor_cpp/` → 遷移至 `/src/lidar_processor_cpp/`

**實現**:
- 基於 PCL (Point Cloud Library)
- C++17 標準
- 節點:
  - `lidar_to_pointcloud_node`
  - `pointcloud_aggregator_node`

**優勢**:
- Jetson 效能更好
- PCL 優化算法
- 記憶體效率更高

---

### 2.5 speech_processor (保留)

**位置**: `/speech_processor/` → 遷移至 `/src/speech_processor/`

**功能**:
- TTS (Text-to-Speech) 使用 ElevenLabs API
- 音訊快取 (MD5 hash)
- 機器狗播放 (WebRTC 分塊傳輸)

**參數**:
- provider: elevenlabs
- voice_name: XrExE9yKIg1WjnnlVkGX
- local_playback: false
- use_cache: true

**依賴**:
```python
install_requires=[
    'requests',
    'pydub',
]
```

**已知問題**:
⚠️ `setup.py` 引用了不存在的節點:
```python
'speech_synthesizer = speech_processor.speech_synthesizer_node:main',  # ❌
'audio_manager = speech_processor.audio_manager_node:main',          # ❌
```

---

### 2.6 coco_detector - 標記替換

**狀態**: 🔴 **開發 yolo_detector 完全替換**

**當前實現**:
- 模型: FasterRCNN_MobileNet_V3_Large_320_FPN
- 權重: COCO_V1 (80 類別)
- 輸入: `/camera/image_raw`
- 輸出: `/detected_objects` (Detection2DArray)
- 參數: device, detection_threshold (0.9), publish_annotated_image

**限制**:
- 僅 80 COCO 類別
- 無法零樣本偵測
- 速度較慢

**遷移目標 (YOLO-World)**:
- 模型: YOLO-Worldv2-S/M
- 零樣本偵測: 任意文字描述類別
- TensorRT 加速 (Jetson)
- 保持 Detection2DArray 輸出相容

**新介面**:
```python
# yolo_detector 參數
confidence_threshold: 0.5
nms_threshold: 0.45
classes: ["bottle", "glasses", "phone"]
model_size: "s"
```

---

## 3) 重構執行計畫 (修正順序)

> **新順序原則**: 低風險、高價值優先；高風險、結構性變更後移

### Phase 1: Skills MVP + 安全層強化 (Week 1-2) ⭐ 優先

**目標**: 建立 Skills 架構，強化安全邊界，不改變既有結構

**為何先做这个**:
- ✅ 最低風險：不改動套件結構，不影響既有功能
- ✅ 最高價值：立即提升安全性和 Agent 可控性
- ✅ 可獨立測試：Skills 可單獨驗證，不依賴其他變更

**任務清單**:

#### 1.1 建立 skills/ 目錄 (獨立於 ROS2 套件)
```
skills/                     # 新建，不影響既有套件
├── motion/
│   ├── safe_move/         # 包裝 /move_for_duration
│   └── emergency_stop/    # 包裝 /stop_movement
├── perception/
│   └── find_object/       # 整合 /capture_snapshot + VLM
├── action/
│   └── perform_action/    # go2_perform_action 封裝
└── system/
    └── status/            # 系統健康檢查
```

#### 1.2 實作 Safe Move Skill
- 強制速度限制 (MAX_LINEAR=0.3, MAX_ANGULAR=0.5)
- 強制時間限制 (MAX_DURATION=10.0)
- 失敗時自動呼叫 emergency-stop
- **參考**: `Ros2_Skills.md` 安全設計章節

#### 1.3 驗證 Skills 獨立運作
```bash
# 測試 safe-move（範例；repo 目前沒有提供 `skill_test` CLI）
# 建議用現有 ROS2 service 直接驗證：
# ros2 service call /move_for_duration go2_interfaces/srv/MoveForDuration "{linear_x: 0.2, angular_z: 0.0, duration: 2.0}"
✅ 速度已限制在 0.2 m/s (≤ 0.3)
✅ 時間已限制在 2.0 s (≤ 10.0)
✅ 執行成功

# 測試超限（範例；同上，建議改用 ros2 service call 驗證 clamp 行為）
# ros2 service call /move_for_duration go2_interfaces/srv/MoveForDuration "{linear_x: 0.5, angular_z: 0.0, duration: 15.0}"
⚠️ 速度已截斷至 0.3 m/s
⚠️ 時間已截斷至 10.0 s
✅ 安全限制生效
```

---

### Phase 2: Sensor Gateway + YOLO-World (Week 3-4)

**目標**: 新增功能，不依賴結構變更

**前置條件**: #2 (Obstacle.msg) 需在此 Phase 完成

#### 2.1 新增 go2_interfaces 訊息
- 建立 `msg/Obstacle.msg` 和 `msg/ObstacleList.msg`
- 更新 CMakeLists.txt
- colcon build 驗證

#### 2.2 Sensor Gateway 開發
**新套件**: `sensor_gateway/` (可暫時放在根目錄，Phase 3 再遷移)

**目標**: 實作 Fast Path (<200ms) 障礙物偵測

**新套件**: `sensor_gateway/`

```
sensor_gateway/
├── sensor_gateway/
│   ├── sensor_gateway_node.py
│   ├── ground_removal.py      # RANSAC
│   ├── clustering.py          # Euclidean Clustering
│   └── __init__.py
├── launch/
│   └── sensor_gateway.launch.py
├── package.xml
└── setup.py
```

**資料流**:
```
/point_cloud2 (10MB/s)
    ↓
[sensor_gateway]
    ├── RANSAC Ground Removal
    ├── Euclidean Clustering (PCL)
    └── JSON Serialization
    ↓
/obstacles_json (~1KB)
    {
      "obstacles": [
        {"id": 0, "center": [x,y,z], "size": [w,h,d], ...}
      ],
      "timestamp": 1234567890.0
    }
```

#### 2.3 YOLO-World 整合
**新套件**: `yolo_detector/` (可暫時放在根目錄，Phase 3 再遷移)

- 輸入: `/camera/image_raw` (Image)
- 輸出: `/detected_objects` (Detection2DArray)
- 保持與 coco_detector 相容的輸出格式

---

### Phase 3: 套件遷移至 src/ (Week 5-6)

**目標**: 重組專案結構，不改變功能

**為何此時才做**:
- Phase 1-2 已完成，Skills 和功能穩定
- 前置條件 #1 (lidar_processor) 已驗證完成
- 可獨立測試，不影響功能

**遷移清單**:
```bash
# 1. 備份當前狀態
git commit -m "backup: before package migration"

# 2. 逐步遷移 (一次一個套件，測試後再下一個)
mkdir -p src/
mv go2_interfaces src/
cd src/ && colcon build --packages-select go2_interfaces && cd ..
# 測試通過...

mv go2_robot_sdk src/
cd src/ && colcon build --packages-select go2_robot_sdk && cd ..
# 測試通過...

mv lidar_processor_cpp src/
mv speech_processor src/
mv coco_detector src/  # 或 yolo_detector
```

**注意**: lidar_processor Python 版需等到前置條件 #1 完成後才可刪除。

---

### Phase 4: Git 歷史清理 (Week 7-8) ⚠️ 最高風險

**目標**: 減少 repo 體積，清理二進制檔案

**前置條件**: #3 (備份) 必須完成

#### 4.1 備份策略 (必做)
```bash
# 1. 完整鏡像備份
git clone --mirror /path/to/elder_and_dog /backup/elder_and_dog_mirror.git

# 2. 驗證備份
cd /backup/elder_and_dog_mirror.git
git remote update
git fsck

# 3. 測試還原
git clone /backup/elder_and_dog_mirror.git /tmp/test_restore
```

#### 4.2 低風險清理 (推薦先做)
```bash
# 方案 A: 不重寫歷史，只清理工作目錄
git rm --cached *.ply *.pt *.pth
echo "*.ply" >> .gitignore
echo "*.pt" >> .gitignore
git commit -m "chore: remove binary files from tracking"

# 方案 B: 使用 BFG Repo-Cleaner (比 filter-repo 安全)
# 先在測試 repo 驗證
cd /tmp
git clone --mirror /backup/elder_and_dog_mirror.git test_clean.git
cd test_clean.git
java -jar bfg.jar --delete-files *.ply
java -jar bfg.jar --delete-files *.pt
git reflog expire --expire=now --all
git gc --prune=now --aggressive
# 驗證沒問題後再對正式 repo 執行
```

#### 4.3 高風險操作 (謹慎)
```bash
# 方案 C: git-filter-repo (僅在確認備份無誤後執行)
# ⚠️ 會改寫所有 commit hash，協作者需重新 clone
git filter-repo --strip-blobs-bigger-than 1M
```

**風險提醒**:
- Submodule 可能會被破壞，需重新初始化
- 所有協作者需要重新 clone
- CI/CD 可能需要更新

---

## 4) 相依關係與新順序

### 4.1 為何調整順序

| 原順序 | 新順序 | 調整原因 |
|--------|--------|---------|
| Phase 1: 基礎重組 | **Phase 3** | 結構變更風險高，後移至功能穩定後 |
| Phase 2: Sensor Gateway | **Phase 2** | 保持不變，但前置條件 #2 需先完成 |
| - | **Phase 1: Skills MVP** (新增) | 最低風險、最高價值，優先執行 |
| - | **Phase 4: Git 清理** (新增) | 最高風險，最後執行且需備份 |

### 4.2 前置條件檢查清單

執行各 Phase 前必須確認：

**執行 Phase 1 (Skills MVP)**:
- [x] 無前置條件，可直接開始

**執行 Phase 2 (Sensor Gateway)**:
- [ ] 前置條件 #2: Obstacle.msg 已建立
- [ ] `colcon build --packages-select go2_interfaces` 成功

**執行 Phase 3 (套件遷移)**:
- [ ] 前置條件 #1: lidar_processor_cpp 功能驗證完成
- [ ] robot.launch.py 已更新為 C++ 版
- [ ] Phase 1-2 功能測試穩定

**執行 Phase 4 (Git 清理)**:
- [ ] 前置條件 #3: 完整鏡像備份完成
- [ ] 備份已驗證可還原
- [ ] 團隊成員已通知

### 4.3 相依圖

```
前置條件 #2 (Obstacle.msg)
    ↓ (必須完成)
Phase 2 (Sensor Gateway)
    ↓ (建議完成)
Phase 1 (Skills MVP) ←──→ 可獨立並行
    ↓
前置條件 #1 (lidar_processor_cpp)
    ↓ (必須完成)
Phase 3 (套件遷移)
    ↓
前置條件 #3 (備份)
    ↓ (必須完成)
Phase 4 (Git 清理)
```

---

## 5) 風險與對策 (更新版)

| 風險 | 說明 | 對策 | 相關前置條件 |
|-----|------|------|-------------|
| lidar_processor 誤刪 | robot.launch.py 仍在引用 Python 版 | 驗證 C++ 版後更新 launch | #1 |
| 訊息不存在 | plan 誤植 Obstacle.msg 為既有 | 明確標記為需新建 | #2 |
| Git 歷史破壞 | filter-repo 破壞 submodule | 先鏡像備份，測試後執行 | #3 |
| Nav2 action 不穩 | rosbridge 端到端未實測 | 實測所有 action 流程 | #4 |
| 結構重組失敗 | 套件遷移後 build 失敗 | 分步遷移，每次驗證 | Phase 3 |
| YOLO-World 失敗 | TensorRT 轉換失敗 | 保留 CPU fallback | Phase 2 |

---

## 6) 完成定義 (Definition of Done) - 對應新順序

### Phase 1 Done (Skills MVP):
- [ ] `skills/` 目錄建立，獨立於 ROS2 套件
- [ ] `safe_move` Skill 實作完成，速度/時間限制生效
- [ ] `emergency_stop` Skill 實作完成，可中斷任意操作
- [ ] 安全限制可測試驗證 (超限會 clamp，異常會 stop)
- [ ] Skills 不依賴 MCP low-level tools

### Phase 2 Done (Sensor Gateway + YOLO):
- [ ] 前置條件 #2 完成: Obstacle.msg / ObstacleList.msg 建立
- [ ] `sensor_gateway` 節點可運行
- [ ] `/obstacles_json` 輸出正常，處理延遲 < 200ms
- [ ] `yolo_detector` 可偵測自定義類別
- [ ] Detection2DArray 輸出相容 coco_detector

### Phase 3 Done (套件遷移):
- [ ] 前置條件 #1 完成: lidar_processor_cpp 驗證通過
- [ ] 所有套件遷移至 src/ (go2_interfaces, go2_robot_sdk, ...)
- [ ] colcon build 全部成功
- [ ] robot.launch.py 已改用 C++ 版 lidar_processor
- [ ] 功能測試與遷移前一致

### Phase 4 Done (Git 清理):
- [ ] 前置條件 #3 完成: 完整鏡像備份已驗證
- [ ] 二進制檔案從 tracking 移除 (或歷史重寫完成)
- [ ] .gitignore 更新防止再次追蹤
- [ ] Submodule 功能正常 (如有破壞已修復)
- [ ] 團隊成員已同步

---

## 7) 參考文件

- `docs/refactor/Ros2_Skills.md` - Skills 化詳細計畫
- `go2_robot_sdk/AGENTS.md` - 驅動套件知識庫
- `go2_interfaces/AGENTS.md` - 介面定義知識庫
- `docs/01-guides/slam_nav/Jetson 8GB 快系統實作指南.md` - Jetson 優化

---

**文件版本**: v1.1 (修正版)  
**最後更新**: 2026-02-10  
**負責人**: Sisyphus Agent  
**修正內容**: 
- 新增 4 項前置驗證條件
- 調整 Phase 順序 (Skills MVP → Sensor Gateway → 套件遷移 → Git 清理)
- 強調 lidar_processor 不可直接刪除
- Git 清理改為 Phase 4 且需先備份
