# Embodied-AI-Guide 章節分析與深挖計畫

**分析日期：** 2025-12-16  
**專題：** 老人與狗 (Elder and Dog) - Go2 機器狗智慧尋物系統  
**文件版本：** v1.0

---

## 一、專題技術棧與當前進度對照

### 你的專題架構

```
當前進度：70%
├─ 層級 1: ROS2 基礎建設 ✅ 100%
│   ├─ SLAM + Nav2 導航堆疊
│   ├─ go2_robot_sdk 驅動
│   └─ 雙橋接網路架構
│
├─ 層級 2: 感知系統整合 🔄 80%
│   ├─ DA3 深度估計（校正完成，SCALE_FACTOR=0.60）
│   ├─ YOLO-World 物體檢測（Port 8050）
│   ├─ Perception API（FastAPI, 326ms 推論）
│   └─ 視覺閉環測試（手動驗證通過）
│
├─ 層級 3: MCP 控制鏈 🔄 60%
│   ├─ ros-mcp-server 整合 ✅
│   ├─ rosbridge WebSocket ✅
│   ├─ Kilo Code 測試（發現 Prompt 問題）
│   └─ 語意導航策略（LLM 多模態融合）
│
└─ 層級 4: 端到端尋物系統 ⏳ 30%
    ├─ autonomous_nav.py 腳本
    ├─ 備案影片錄製
    └─ Demo 準備（1/7 發表）
```

---

## 二、Embodied-AI-Guide 核心章節清單

### 📋 指南結構總覽

| 主類別 | 行數範圍 | 子章節數 | 對你的相關性 |
|-------|---------|---------|-------------|
| 1. Start From Here | 111-126 | 1 | ⭐⭐⭐⭐ |
| 2. Useful Info | 130-163 | 1 | ⭐⭐⭐⭐ |
| 3. Algorithm | 166-829 | 10 | ⭐⭐⭐⭐⭐ |
| 4. Control & Robotics | 846-931 | 3 | ⭐⭐⭐⭐ |
| 5. Hardware | 935-1061 | 6 | ⭐⭐ |
| 6. Software | 1063-1112 | 3 | ⭐⭐⭐ |
| 7. Paper Lists | 1117-1129 | 1 | ⭐⭐⭐⭐ |

**總計：** 1161 行，26 個子章節

---

## 三、優先級 S（必讀必實作）

### 🎯 3.5 Vision-Language-Action Models (第 356-461 行)

#### 為什麼最重要：
- 這是你專題的**終極架構藍圖**
- 涵蓋端到端多模態導航的所有前沿方法
- 2025 年最新趨勢：雙系統分層 VLA

#### 核心內容：

**A. VLA 定義與特點**
- 端到端：使用 LLM/VLM backbone
- 輸入：多模態（圖像 + 文本 + 3D）
- 輸出：機器人動作指令
- 無需重新設計架構，只需 tokenize 動作並微調

**B. 經典工作分類**

| 類別 | 代表性工作 | 適用場景 | 對你的價值 |
|-----|-----------|---------|-----------|
| 自回歸模型 | RT-2, OpenVLA (7B), RoboFlamingo | 操作任務 | ⭐⭐⭐ |
| 擴散模型 | π0 (3.3B), Octo (93M), RDT-1B | 軌跡生成 | ⭐⭐⭐⭐ |
| 3D 視覺 VLA | 3D-VLA, SpatialVLA | 空間推理 | ⭐⭐⭐⭐ |
| 雙系統分層 | Helix, GO-1, pi-0.5, GROOT-N1 | 導航 + 規劃 | ⭐⭐⭐⭐⭐ |
| 導航專用 | Mobility-VLA, NaVILA | 腿式機器人導航 | ⭐⭐⭐⭐⭐⭐ |

**C. 對你的具體建議**

**方案 1：輕量級雙系統（推薦用於 1/7 Demo）**

```
System 2 (高級規劃)
├─ Claude/GPT-4o via MCP
├─ 輸入：自然語言指令 + 環境圖像
├─ 輸出：語意目標（如「前方有紙箱，向左繞行」）
└─ 已有架構 ✅

System 1 (動作執行)
├─ 確定性腳本（autonomous_nav.py）
├─ 輸入：Perception API 建議
├─ 輸出：/cmd_vel 或 Nav2 目標點
└─ 已實作 ✅
```

**方案 2：完整 VLA 架構（寒假實驗）**

```
System 2 (高級規劃)
├─ VLM：Qwen-VL 或 LLaVA-1.5
├─ 輸入：RGB-D + 點雲 + 語言指令
├─ 輸出：高級規劃指令或潛在向量
└─ 需訓練/微調

System 1 (動作執行)
├─ VLA 模型：OpenVLA 7B 或 π0 3.3B
├─ 輸入：視覺特徵 + System 2 指令
├─ 輸出：直接動作序列
└─ 需微調（Open X-Embodiment 數據）
```

**重點論文清單（必讀）：**

1. **Mobility-VLA** (Google DeepMind, 2024.7)
   - 專為導航設計的 VLA
   - 適用於 Go2 腿式機器人
   - Paper + Code 都公開

2. **NaVILA** (UCSD, 2024.12)
   - 腿式機器人導航專用
   - 視覺-語言導航

3. **pi-0.5** (Physical Intelligence, 2025.4.22)
   - 雙系統分層架構最佳案例
   - System 2 (VLM) + System 1 (VLA)

4. **UniVLA** (港大+智元, 2025.5.9)
   - 多樣化數據泛化
   - 可能有中文文檔

5. **SpatialVLA** (上海 AI Lab, 2025)
   - 自適應動作網格
   - 空間推理能力

**深挖方向：**
- [ ] 下載 Mobility-VLA 論文與程式碼
- [ ] 研究 π0 擴散模型動作頭架構
- [ ] 閱讀 NaVILA 腿式機器人導航方法
- [ ] 查找 UniVLA 中文資源

---

### 🧭 3.9 機器人導航 (第 565-612 行)

#### 為什麼重要：
- 直接對應你的 SLAM + Nav2 系統
- 提供從傳統方法到零樣本 LLM 方法的完整演進

#### 核心內容：

**A. 任務分類**

| 任務類型 | 輸入 | 你的對應 |
|---------|------|---------|
| Object-Goal Nav | 物體描述（"水瓶"） | 你的核心任務 ✅ |
| Image-Goal Nav | 參考圖像 | 可擴展方向 |
| Vision-Language Nav | 自然語言路徑指令 | 已支援（MCP） |

**B. 架構分類**

**1. 端到端模型**
- 感測器 → 神經網路 → 動作
- 缺點：難以解釋、泛化性差
- 不推薦用於 Go2

**2. 模組化模型（推薦）⭐**

```
建圖模組
├─ 語義地圖 (Semantic Map)
├─ 佔有地圖 (Occupancy Map)
└─ 已有：slam_toolbox ✅
        ↓
全局策略 (Global Policy)
├─ 長期目標規劃
├─ A* / Dijkstra 路徑規劃
└─ 已有：Nav2 Planner ✅
        ↓
局部策略 (Local Policy)
├─ 避障與軌跡調整
├─ DWA / TEB Controller
└─ 已有：Nav2 Controller ✅
```

**3. 零樣本模型（最適合你）⭐⭐**
- CLIP + LLM 方法
- 無需訓練，直接部署
- 經典工作：
  - **CoWs on Pasture**：CLIP 語意導航
  - **L3MVN**：LLM 多模態導航
  - **ESC**：具身情境鏈
  - **SG-Nav**：場景圖導航

**你目前的架構對應：**
- ✅ 建圖：slam_toolbox
- ✅ 全局：Nav2 Planner
- ✅ 局部：Nav2 Controller + DWA
- 🔄 語意層：DA3 + YOLO-World (進行中)
- ⏳ 零樣本：LLM + CLIP (待整合)

**C. 常用數據集**

| 數據集 | 場景數 | 用途 |
|-------|-------|------|
| MatterPort3D (MP3D) | 90 | 真實室內場景 |
| HM3D | 1000+ | 大規模室內 |
| RoboTHOR | - | 機器人導航基準 |

**深挖方向：**
- [ ] 閱讀 L3MVN (LLM 多模態導航) 論文
- [ ] 研究 ESC (具身情境鏈) 的 Prompt 設計
- [ ] 下載 HM3D 數據集用於模擬器測試
- [ ] 對比零樣本方法與你的 MCP 架構

---

### 🤖 3.4 LLM for Robotics (第 328-353 行)

#### 為什麼重要：
- 直接對應你的 MCP 控制鏈
- 提供 LLM 控制機器人的經典方法論

#### 核心內容：

**A. 經典工作分類**

| 類別 | 代表性工作 | 你的對應 |
|-----|-----------|---------|
| High-Level 策略生成 | PaLM-E, DO AS I CAN | MCP 規劃層 ✅ |
| 統一 High-Low Level | RT-2 | VLA 方向 |
| LLM + 傳統規劃器 | LLM+P, AutoTAMP | **推薦架構** ⭐⭐⭐⭐⭐ |
| Code-based Control | Code as Policy | 可參考 |
| 3D 視覺 + LLM | VoxPoser | 座標轉換靈感 |
| 多機器人協同 | RoCo | 未來方向 |

**B. LLM+P 架構（最推薦）**

```
自然語言指令：「幫我找水瓶」
         ↓
LLM 推理（Claude API）
├─ 理解：尋找物體「水瓶」
├─ 分解：1.巡邏 2.檢測 3.導航 4.確認
└─ 轉換：PDDL 規劃語言
         ↓
傳統規劃器（Nav2）
├─ 路徑規劃
├─ 碰撞檢測
└─ 執行動作
         ↓
實際執行：Go2 移動
```

**關鍵優勢：**
- LLM 負責高級推理（擅長）
- 規劃器負責確定性執行（可靠）
- 兩者互補，成功率高

**你目前的實作：**
- ✅ LLM 層：Claude via MCP
- ✅ 規劃器：Nav2 + autonomous_nav.py
- ⏳ 介面：需強化 Prompt（mcp_system_prompt.md）

**C. 重點論文**

1. **LLM+P** (ICRA 2023)
   - LLM 生成 PDDL
   - 傳統規劃器執行
   - Code 已開源

2. **DO AS I CAN, NOT AS I SAY**
   - SayCan 方法
   - 可供性（Affordance）打分

3. **VoxPoser** (CoRL 2023)
   - 3D 視覺 + LLM
   - 可供性地圖生成

**深挖方向：**
- [ ] 閱讀 LLM+P 論文與程式碼
- [ ] 研究 SayCan 的 Affordance 打分機制
- [ ] 參考 VoxPoser 的 3D 空間推理方法
- [ ] 優化你的 mcp_system_prompt.md

---

### 👁️ 3.2 Vision Foundation Models (第 180-209 行)

#### 為什麼重要：
- 直接對應你的感知系統（DA3 + YOLO-World）
- 提供更多替代方案與優化方向

#### 核心內容：

**A. 模型清單與對應**

| 模型 | 功能 | 你的使用情況 |
|-----|------|-------------|
| Depth Anything v2 | 單目深度估計 | DA3 已部署 ✅ |
| YOLO-World | 開放詞彙檢測 | 已部署 ✅ |
| Grounding-DINO | 開放詞彙檢測 | 可替代 YOLO-World |
| SAM2 | 物件分割與追蹤 | 可整合 ⭐⭐⭐⭐ |
| Grounded-SAM-2 | 檢測 + 分割 | 精確定位 ⭐⭐⭐⭐⭐ |
| OmDet-Turbo | 快速檢測 (100+ FPS) | 可替代（若需加速） |
| CLIP | 圖像-語言相似度 | 語意導航 ⭐⭐⭐⭐ |
| DINO-v2 | 視覺特徵提取 | VLA 特徵提取 |
| FoundationPose | 物體姿態追蹤 | 精確操作（非必需） |

**B. 推薦整合方案**

**方案 1：輕量級（當前架構優化）**
```
相機圖像
    ↓
DA3 Metric (深度) + YOLO-World (檢測)
    ↓
Perception API 摘要
    ↓
LLM 決策
```
- 優點：已驗證，326ms 推論
- 缺點：無語意理解

**方案 2：加入 CLIP（推薦）⭐⭐⭐⭐⭐**
```
相機圖像
    ↓
DA3 + YOLO-World + CLIP
    ├─ DA3：深度
    ├─ YOLO：檢測
    └─ CLIP：語意匹配（「水瓶」vs 檢測框）
         ↓
增強版 Perception API
    ├─ 目標物信心分數
    ├─ 語意方位描述
    └─ 優先級排序
         ↓
LLM 決策（更準確）
```

**方案 3：終極版（寒假實驗）**
```
相機圖像
    ↓
Grounded-SAM-2 (檢測 + 分割)
    ├─ 精確物體邊界
    ├─ 追蹤 ID
    └─ 多幀關聯
         ↓
DA3 + CLIP
    ├─ 物體 3D 位置
    └─ 語意匹配
         ↓
3D 場景圖
    ↓
VLA 模型
```

**C. 重點技術細節**

**CLIP 整合範例：**
```python
import clip
import torch

# 載入模型
model, preprocess = clip.load("ViT-B/32", device="cuda")

# 語意匹配
text = clip.tokenize(["水瓶", "眼鏡", "紙箱"]).to(device)
image = preprocess(pil_image).unsqueeze(0).to(device)

with torch.no_grad():
    image_features = model.encode_image(image)
    text_features = model.encode_text(text)

    # 計算相似度
    similarity = (image_features @ text_features.T).softmax(dim=-1)
    # 結果：[0.85, 0.1, 0.05] → 85% 信心是水瓶
```

**Grounded-SAM-2 整合：**
- 論文：Grounding DINO + SAM2
- 功能：文字提示 → 檢測 → 分割
- 適用：精確物體定位（比 YOLO bounding box 更準）

**深挖方向：**
- [ ] 在 Perception Server 加入 CLIP 語意匹配
- [ ] 測試 Grounded-SAM-2 的精度 vs YOLO-World
- [ ] 評估 OmDet-Turbo 的實時性能
- [ ] 研究 DINO-v2 特徵用於 VLA 微調

---

## 四、優先級 A（強烈推薦）

### 📐 4.2.3 里程計與 SLAM (第 882-905 行)

#### 為什麼重要：
- 對應你的 slam_toolbox + Nav2 系統
- 提供更多 SLAM 方案與優化方向

#### 核心內容：

| 類別 | 代表性工作 | 與你的關聯 |
|-----|-----------|-----------|
| 視覺慣性里程計 (VIO) | VINS-Mono, VINS-Fusion | 可替代純 LiDAR |
| 激光慣性里程計 (LIO) | FAST-LIO, FAST-LIO2 | 高精度定位 ⭐⭐⭐⭐ |
| SLAM | ORB-SLAM3, FAST-LIVO | 視覺+LiDAR 融合 |
| 圖優化 | LOAM, LeGO-LOAM | 大場景建圖 |

**推薦方案：**
- **FAST-LIO2**：Go2 的 LiDAR + IMU 融合
- 優勢：比 slam_toolbox 更準、更快
- 缺點：需要重新建置

**深挖方向：**
- [ ] 研究 FAST-LIO2 vs slam_toolbox 精度差異
- [ ] 閱讀 VINS-Fusion 視覺融合方法
- [ ] 評估是否值得切換至 FAST-LIO2

---

### 🎨 3.6 計算機視覺 (第 465-534 行)

#### 核心內容：

**A. 可供性錨定 (Affordance Grounding)**

**什麼是 Affordance？**
- 物體的「可操作性」特徵
- 例如：杯子的把手、門的把手、椅子的坐面

**對你的價值：**
- 尋物系統的延伸：不只找到，還要知道「如何互動」
- 例如：找到水瓶後，知道從哪裡抓取

**經典工作：**
- **AffordanceLLM**：LLM 推理物體可供性
- **Where2Act**：3D 場景中的可操作點
- **OpenAD**：開放詞彙可供性

**深挖方向：**
- [ ] 閱讀 AffordanceLLM 論文
- [ ] 評估加入可供性對 Demo 的價值

---

### 🎮 6.1 仿真器 (第 1067-1085 行)

#### 為什麼重要：
- 對應你的 Isaac Sim + Orbit 計畫（當前 20%）

#### 核心內容：

| 仿真器 | 對應基準集 | Go2 支援 | 推薦度 |
|-------|-----------|---------|-------|
| IsaacSim | BEHAVIOR-1K, ARNOLD | ✅ 官方支援 | ⭐⭐⭐⭐⭐ |
| IsaacGym | legged-gym, parkour | ✅ 腿式專用 | ⭐⭐⭐⭐ |
| MuJoCo | robosuite | ⚠️ 需自訂 | ⭐⭐⭐ |
| Genesis | - | ❓ 新興 | ⭐⭐⭐ |
| Gazebo | - | ✅ ROS2 原生 | ⭐⭐⭐⭐ |

**推薦路徑：**

**短期（Demo 前）：Gazebo Classic**
- ROS2 原生支援
- Go2 URDF 已有
- 可快速驗證導航邏輯

**中期（寒假）：IsaacSim + Orbit**
- 更真實的物理模擬
- GPU 加速（RTX 4090）
- 官方 Go2 支援

**長期（下學期）：IsaacGym**
- 強化學習訓練（PPO/SAC）
- 大規模並行模擬
- 學習避障策略

**深挖方向：**
- [ ] 下載 IsaacSim Go2 範例
- [ ] 研究 Orbit 框架文檔
- [ ] 測試 Gazebo 中的 go2.urdf

---

## 五、優先級 B（推薦選讀）

### 🧠 3.3 機器人學習 (第 212-323 行)

**內容摘要：**
- 強化學習（PPO, SAC）
- 模仿學習
- 課程推薦（UC Berkeley CS285）

**對你的價值：**
- 寒假可用強化學習訓練避障策略
- 替代手動調 Nav2 參數

**深挖方向：**
- [ ] 學習 PPO 算法（Stable-Baselines3）
- [ ] 研究 Isaac Gym + legged-gym 範例

---

### 🚗 3.10.3 自動駕駛 (第 751-829 行)

#### 為什麼相關：
- 自動駕駛 = 大型移動機器人導航
- 模組化架構可參考

#### 核心內容：

**雙系統架構：**
- 快系統：VAD, SparseDrive（實時反應）
- 慢系統：DriveVLM, EMMA（推理規劃）

**對你的啟發：**
```
你的雙系統架構

快系統（System 1）
├─ autonomous_nav.py
├─ 確定性避障
└─ 響應時間：<100ms

慢系統（System 2）
├─ Claude API
├─ 語意推理
└─ 響應時間：2-5s
```

**深挖方向：**
- [ ] 閱讀 DriveVLM 論文（VLM 用於駕駛）
- [ ] 研究快慢系統的切換邏輯

---

## 六、具體行動計畫

### 🎯 第一週（12/16-12/22）：補強感知系統

**目標：** 1/7 Demo 前的最後衝刺

| 任務 | 對應章節 | 預計時間 |
|-----|---------|---------|
| 整合 CLIP 語意匹配 | 3.2 | 4 小時 |
| 優化 mcp_system_prompt.md | 3.4 | 2 小時 |
| 閱讀 Mobility-VLA 論文 | 3.5 | 3 小時 |
| 閱讀 L3MVN 零樣本導航 | 3.9 | 2 小時 |
| 錄製備案影片 | - | 2 小時 |

### 📚 第二週（12/23-12/29）：理論深化

**目標：** 建立 VLA 理論基礎

| 任務 | 對應章節 | 預計時間 |
|-----|---------|---------|
| 精讀 π0 擴散模型論文 | 3.5 | 4 小時 |
| 精讀 LLM+P 規劃器論文 | 3.4 | 3 小時 |
| 研究 Grounded-SAM-2 | 3.2 | 3 小時 |
| 整理文獻筆記 | - | 2 小時 |

### 🧪 第三週（12/30-1/5）：Demo 準備

**目標：** 穩定性測試與彩排

| 任務 | 對應章節 | 預計時間 |
|-----|---------|---------|
| 壓力測試（連續運行） | - | 3 小時 |
| Demo 腳本彩排 | - | 4 小時 |
| 簡報製作 | - | 4 小時 |
| 預演與調整 | - | 3 小時 |

### 🚀 寒假（1/10-2/28）：VLA 實驗

**目標：** 完整 VLA 架構實作

| 階段 | 對應章節 | 預計時間 |
|-----|---------|---------|
| IsaacSim 環境搭建 | 6.1 | 2 週 |
| OpenVLA 微調 | 3.5 | 3 週 |
| FAST-LIO2 整合 | 4.2.3 | 1 週 |
| 端到端測試 | - | 2 週 |

---

## 七、重點資源下載清單

### 📄 必讀論文（優先下載）

| 論文 | 會議/期刊 | 年份 | 下載優先級 |
|-----|----------|-----|-----------|
| Mobility-VLA | - | 2024 | ⭐⭐⭐⭐⭐ |
| NaVILA | - | 2024 | ⭐⭐⭐⭐⭐ |
| LLM+P | ICRA | 2023 | ⭐⭐⭐⭐⭐ |
| π0 | - | 2024 | ⭐⭐⭐⭐ |
| L3MVN | - | 2024 | ⭐⭐⭐⭐ |
| Grounded-SAM-2 | - | 2024 | ⭐⭐⭐⭐ |
| UniVLA | - | 2025 | ⭐⭐⭐ |
| SpatialVLA | - | 2025 | ⭐⭐⭐ |

### 💻 開源程式碼

| 項目 | 功能 | 優先級 |
|-----|------|-------|
| Mobility-VLA Code | 導航 VLA | ⭐⭐⭐⭐⭐ |
| OpenVLA | 通用 VLA (7B) | ⭐⭐⭐⭐ |
| LLM+P Code | LLM + 規劃器 | ⭐⭐⭐⭐ |
| Grounded-SAM-2 | 檢測 + 分割 | ⭐⭐⭐ |
| FAST-LIO2 | LiDAR SLAM | ⭐⭐⭐ |

### 📚 課程與教材

| 資源 | 類型 | 優先級 |
|-----|------|-------|
| 3.9 機器人導航章節 | 文檔 | ⭐⭐⭐⭐⭐ |
| 3.5 VLA 章節 | 文檔 | ⭐⭐⭐⭐⭐ |
| UC Berkeley CS285 | 影片課程 | ⭐⭐⭐ |
| Modern Robotics (Lynch) | 教科書 | ⭐⭐⭐ |

---

## 八、與你專題的技術對標

### 當前架構映射

```
你的系統層級               Embodied-AI-Guide 對應章節
┌─────────────────────────────────────────────┐
│ 感知層                                       │
│ ├─ DA3 深度估計         → 3.2 Depth Anything │
│ ├─ YOLO-World 檢測      → 3.2 開放詞彙檢測   │
│ └─ LiDAR 點雲           → 3.1 點雲工具       │
├─────────────────────────────────────────────┤
│ 決策層                                       │
│ ├─ MCP (System 2)       → 3.4 LLM Robotics   │
│ ├─ autonomous_nav.py    → 3.9 模組化架構     │
│ └─ Prompt Engineering   → 3.4 LLM+P          │
├─────────────────────────────────────────────┤
│ 執行層                                       │
│ ├─ slam_toolbox         → 4.2.3 SLAM        │
│ ├─ Nav2                 → 3.9 全局/局部策略  │
│ └─ go2_robot_sdk        → 5. 硬體            │
├─────────────────────────────────────────────┤
│ 未來擴展                                     │
│ ├─ VLA 微調             → 3.5 VLA 模型       │
│ ├─ Isaac Sim            → 6.1 仿真器         │
│ └─ 強化學習             → 3.3 機器人學習     │
└─────────────────────────────────────────────┘
```

### 升級路徑建議

**Phase 1：輕量級優化（本週完成）**
```diff
+ 加入 CLIP 語意匹配（3.2）
+ 優化 LLM Prompt（3.4 LLM+P）
+ 參考零樣本導航方法（3.9）
```

**Phase 2：中級架構（寒假）**
```diff
+ 替換為 FAST-LIO2（4.2.3）
+ 整合 Grounded-SAM-2（3.2）
+ 部署 IsaacSim（6.1）
```

**Phase 3：終極架構（下學期）**
```diff
+ 微調 OpenVLA 或 Mobility-VLA（3.5）
+ 強化學習訓練（3.3）
+ 多機器人協同（3.4）
```

---

## 九、總結與建議

### 🎯 核心建議

**立即開始（本週）**
1. 精讀 **3.5 VLA 模型** 中的 Mobility-VLA 和雙系統架構
2. 精讀 **3.9 機器人導航** 中的零樣本方法
3. 整合 **3.2** 中的 CLIP 語意匹配
4. 準備 1/7 Demo

**深化理論（下週）**
1. 研究 **3.4 LLM+P** 規劃器架構
2. 閱讀 π0 和 OpenVLA 論文

**實驗驗證（寒假）**
1. 部署 **6.1 IsaacSim**
2. 微調 VLA 模型（3.5）
3. 強化學習訓練（3.3）

### 📊 章節優先級總結

| 優先級 | 章節 | 對應你的模組 | 建議時程 |
|-------|------|-------------|---------|
| S | 3.5 VLA 模型 | 端到端架構 | 本週開始 |
| S | 3.9 機器人導航 | SLAM + Nav2 | 本週開始 |
| S | 3.4 LLM Robotics | MCP 決策層 | 本週開始 |
| S | 3.2 視覺模型 | 感知系統 | 本週開始 |
| A | 4.2.3 SLAM | 定位系統 | 下週 |
| A | 3.6 計算機視覺 | 視覺基礎 | 寒假 |
| A | 6.1 仿真器 | Isaac Sim | 寒假 |
| B | 3.3 機器人學習 | 強化學習 | 下學期 |
| B | 3.10.3 自動駕駛 | 架構參考 | 選讀 |

### 🚀 下一步行動

- [ ] 下載 Embodied-AI-Guide 完整倉庫
- [ ] 建立論文閱讀清單（上述 8 篇必讀）
- [ ] 整合 CLIP 至 Perception Server
- [ ] 優化 mcp_system_prompt.md
- [ ] 準備 1/7 Demo 材料

---

**文件完成時間：** 2025-12-16  
**下次更新：** 根據閱讀進度調整
