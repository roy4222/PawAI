> **⚠️ ARCHIVED** — 早期大規模技術路線圖，非 4/13 展示主線。當前主線架構見 [mission/README.md](./README.md) v2.0。

# PawAI Agentic Embodied AI 實作路線圖

**文件版本**: v1.0  
**建立日期**: 2026-03-05  
**硬體配置**: Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000  
**專案方向**: Agentic Embodied AI with 多模態融合 (人臉 + 語音 + 手勢)，非導航優化

---

## 1. 架構決策總覽

### 1.1 核心設計原則

| 決策項目 | 選擇 | 理由 |
|---------|------|------|
| **運算分層** | 邊緣-雲端雙層架構 | Jetson 8GB 無法同時跑 LLM + VLM + 多模態感知 |
| **控制權分離** | 快系統 (邊緣) 保留最終控制權 | 安全優先，雲端僅提供「建議」而非直接下達 cmd_vel |
| **多模態融合層級** | 語義層融合，非特徵層 | 降低頻寬需求，避免原始 sensor 資料上雲 |
| **開源策略** | 借概念不搬整套 | Nav2 主線穩定，僅採納 Odin/OM1 的安全外圈與可觀測性概念 |
| **模型部署** | Triton + vLLM 服務化 | 避免各自起 Python process 導致顯存碎片化 |

### 1.2 雙層架構詳細分工

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           慢系統 (Slow System)                               │
│                     5×RTX 8000 (48GB VRAM per card)                         │
│                         延遲容忍: 500ms - 2s                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│  卡 1: 人臉識別管線          卡 2: 視覺屬性/情緒              卡 3: ASR/NLU  │
│  - InsightFace 偵測/對齊     - 頭部朝向 (6DRepNet)           - Whisper Large │
│  - ArcFace embedding         - 視線估計                    - vLLM 70B       │
│  - Faiss GPU 向量檢索        - 情緒分類                      - 意圖解析      │
├─────────────────────────────────────────────────────────────────────────────┤
│  卡 4: TTS/語音合成          卡 5: VLM/多模態融合                           │
│  - MeloTTS / Bark            - Qwen2.5-VL / LLaVA                          │
│  - 情感韻律控制              - 視覺問答 + 場景理解                          │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑↓ 語義摘要 (JSON, <10KB/請求)
┌─────────────────────────────────────────────────────────────────────────────┐
│                           快系統 (Fast System)                               │
│                Jetson Orin Nano 8GB + Go2 原生感測器                        │
│                         延遲目標: <100ms                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│  感知層                                                                      │
│  - BlazeFace / MediaPipe (人臉偵測)      - ros2_trt_pose_hand (手勢 21點)    │
│  - YOLOv8-nano TensorRT (物件偵測)       - Silero VAD (語音活動檢測)        │
│  - RealSense D435 (深度前處理)           - L2 LiDAR (障礙感知)              │
├─────────────────────────────────────────────────────────────────────────────┤
│  決策層                                                                      │
│  - 手勢→Skill 直接映射 (規則式)            - 緊急停止 (硬體中斷優先)         │
│  - 簡單語音指令 (Whisper Tiny)            - 基礎跟隨 (視覺伺服)             │
├─────────────────────────────────────────────────────────────────────────────┤
│  執行層                                                                      │
│  - Go2 Sport Service (步態/動作)           - Safety Layer (限速/限時)       │
│  - Nav2 Action (僅供雲端規劃結果使用)      - ros-mcp-server (MCP 橋接)      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.3 資料流設計

**邊緣端預處理 (Jetson)**:
```
D435 RGB-D → 人臉 crop / 手勢 landmarks / 物件 bbox
                ↓
         只傳「語義摘要」上雲 (JSON):
         {
           "timestamp": 1712345678.123,
           "face_detected": true,
           "face_crop": "[base64_jpeg]",
           "gesture": "pointing",
           "pointing_direction": {"azimuth": 45, "elevation": -10},
           "depth_to_gesture": 1.2,
           "scene_objects": [{"label": "bottle", "bbox": [...], "distance": 0.8}]
         }
```

**雲端處理 (RTX 8000)**:
```
語義摘要 + 歷史上下文 → LLM/VLM 推理 → 行為腳本/參數更新 → 下發邊緣
```

**關鍵設計**: 原始影像不上雲，僅傳 crop 後的 ROI 或 embedding，大幅降低頻寬需求。

---

## 2. Phase 1-3 目標與里程碑

### Phase 1: Skills MVP + 多模態基礎 (Week 1-2)

**核心目標**: 建立可獨立運作的 Skill 架構，完成基礎感知-決策-執行閉環

| Week | 任務 | 驗收標準 | 負責硬體 |
|------|------|----------|----------|
| W1-D1 | 建立 `skills/` 目錄結構 | 目錄存在，獨立於 ROS2 套件 | - |
| W1-D2 | 實作 `safe_move` Skill | 速度/時間限制生效，超限會 clamp | Jetson |
| W1-D3 | 實作 `emergency_stop` Skill | 任意時刻可中斷，自動觸發 | Jetson |
| W1-D4 | MediaPipe Hands 整合 | 21 點關鍵點輸出穩定，延遲 <50ms | Jetson |
| W1-D5 | 手勢→Skill 映射驗證 | 手掌張開→stop，招手→follow 可觸發 | Jetson |
| W2-D1 | BlazeFace 人臉偵測 | 偵測率 >90%，延遲 <30ms | Jetson |
| W2-D2 | 雲端 InsightFace 部署 | embedding 輸出正常，單卡可跑 10 路 | RTX 8000 卡 1 |
| W2-D3 | 邊緣-雲端人臉管線 | ROI crop 上傳 → 身份回傳 <500ms | Jetson + 卡 1 |
| W2-D4 | Silero VAD 整合 | 語音活動檢測，sub-ms 延遲 | Jetson |
| W2-D5 | Phase 1 整合測試 | 手勢 + 人臉 + 語音喚醒可同時運作 | 全系統 |

**Phase 1 完成定義 (Definition of Done)**:
- [ ] `skills/` 目錄建立，含 motion/perception/action/system 四個子目錄
- [ ] `safe_move` 速度限制 0.3m/s，時間限制 10s，超限自動 clamp
- [ ] `emergency_stop` 可於任意時刻中斷當前動作
- [ ] MediaPipe Hands 輸出 21 點，靜態手勢識別率 >95%
- [ ] BlazeFace 人臉偵測，輸出 crop 後的 ROI
- [ ] 雲端 InsightFace 單卡支援至少 5 路並行
- [ ] 邊緣-雲端人臉管線端到端延遲 <1s

---

### Phase 2: 多模態融合 + 語音互動 (Week 3-4)

**核心目標**: 實現「語音 + 手勢 + 人臉」多模態融合理解，建立基礎對話能力

| Week | 任務 | 驗收標準 | 負責硬體 |
|------|------|----------|----------|
| W3-D1 | Whisper Large 雲端部署 | 中文 CER <8%，延遲 <500ms | RTX 8000 卡 3 |
| W3-D2 | vLLM 對話引擎部署 | 70B 量化版可跑，TTFT <2s | RTX 8000 卡 3 |
| W3-D3 | MeloTTS 部署 | 中文語音輸出自然，RTF <0.5 | RTX 8000 卡 4 |
| W3-D4 | 語音喚醒詞訓練 | 「Go2」「夥伴」喚醒率 >95% | Jetson (Tiny) |
| W3-D5 | 基礎對話閉環 | 喚醒 → ASR → LLM → TTS → 播報，總延遲 <3s | 全系統 |
| W4-D1 | 多模態對齊 | 語音「那個」+ 指向手勢 → 指向目標識別 | Jetson + 卡 5 |
| W4-D2 | 情緒識別管線 | 人臉表情 → 7 類情緒分類 | RTX 8000 卡 2 |
| W4-D3 | 情緒-行為映射 | 偵測快樂→興奮步態，疲勞→降低打擾 | Jetson |
| W4-D4 | 上下文記憶 | 記得「上次看到的水瓶在哪」 | RTX 8000 (向量 DB) |
| W4-D5 | Phase 2 整合測試 | 完整多模態互動場景 5 個可演示 | 全系統 |

**Phase 2 完成定義**:
- [ ] 中文 ASR 延遲 <500ms，CER <8%
- [ ] LLM 對話延遲 TTFT <2s，回應品質主觀評分 >4/5
- [ ] TTS 輸出自然，支援語速調整
- [ ] 語音喚醒率 >95%，誤喚醒率 <5%/小時
- [ ] 多模態對齊: 「那個」+ 指向 → 正確物件識別率 >80%
- [ ] 情緒識別準確率 >75%
- [ ] 記憶系統可回答「上次在哪看到 XX」類問題

---

### Phase 3: Agentic 能力 + 長期記憶 (Week 5-6)

**核心目標**: 實現主動行為、複雜任務規劃、持續學習適應

| Week | 任務 | 驗收標準 | 負責硬體 |
|------|------|----------|----------|
| W5-D1 | VLM 部署 (Qwen2.5-VL) | 視覺問答準確，開放詞彙檢測 | RTX 8000 卡 5 |
| W5-D2 | 主動行為狀態機 | 定時巡邏、異常提醒、陪伴模式 | Jetson |
| W5-D3 | 複雜指令分解 | 「去廚房拿水瓶」→ 子目標序列 | RTX 8000 (LLM) |
| W5-D4 | 環境語義地圖 | 房間功能標註、物品位置記憶 | Jetson + 卡 5 |
| W5-D5 | 失敗恢復策略 | 任務失敗 → 報告原因 → 請求確認 | 全系統 |
| W6-D1 | 使用者習慣學習 | 記錄偏好路徑、互動頻率 | RTX 8000 (LoRA) |
| W6-D2 | 個性化適應 | 語音風格、主動性參數動態調整 | RTX 8000 |
| W6-D3 | 離線降級 | 網路中斷時本地 Whisper Tiny + 規則 NLU | Jetson |
| W6-D4 | 壓力測試 | 連續運行 2 小時無異常 | 全系統 |
| W6-D5 | Phase 3 驗收 | 完整場景 Demo 成功率 >80% | 全系統 |

**Phase 3 完成定義**:
- [ ] VLM 開放詞彙檢測準確率 >75%
- [ ] 主動行為 3 種以上可運作 (巡邏/提醒/陪伴)
- [ ] 複雜指令分解成功率 >80%
- [ ] 環境語義地圖可標註 5+ 房間、10+ 物品位置
- [ ] 離線降級時基礎功能可用 (喚醒/簡單指令/跟隨)
- [ ] 連續運行 2 小時無當機、無記憶體洩漏

---

## 3. Jetson vs 5×RTX 8000 分工矩陣

### 3.1 詳細分工表

| 功能模組 | Jetson (邊緣) | 5×RTX 8000 (雲端) | 溝通內容 |
|---------|--------------|------------------|----------|
| **人臉** | BlazeFace 偵測、ROI crop | InsightFace embedding、身份比對 | crop JPEG + 位置 |
| **手勢** | MediaPipe Hands 21點、靜態分類 | 動態手勢精細解析、3D 重建 | landmarks + 類別 |
| **語音** | VAD、喚醒詞、Whisper Tiny | Whisper Large、NLU LLM、TTS | audio chunk / text |
| **視覺** | YOLOv8-nano、關鍵幀提取 | VLM、Grounding DINO、SAM | CLIP embedding |
| **導航** | Nvblox、MPPI、緊急避障 | 高階路徑規劃、語義目標 | waypoints |
| **行為** | 步態參數即時調整、動作執行 | 情緒-行為策略生成 | gait_params |
| **記憶** | 短期工作記憶 (<5min) | 長期記憶、向量檢索、LoRA | 摘要 + 更新 |

### 3.2 硬體資源分配

**Jetson Orin Nano 8GB (25W MAXN)**:
```
記憶體分配:
- 系統保留: 1GB
- ROS2 + Nav2: 2GB
- 感知模型 (TensorRT): 2GB
  - BlazeFace: ~100MB
  - MediaPipe Hands: ~50MB
  - YOLOv8-nano: ~100MB
  - Silero VAD: ~20MB
- 應用邏輯: 2GB
- 緩衝: 1GB

CPU 分配:
- ROS2 節點: 4 cores
- 感知前處理: 2 cores
- 主程式: 2 cores
```

**5×RTX 8000 (每卡 48GB VRAM)**:
```
卡 1 (人臉管線):
- InsightFace 偵測 + ArcFace: ~6GB
- Faiss GPU: ~2GB
- 批次處理 10 路並行

卡 2 (視覺屬性):
- 6DRepNet (頭部朝向): ~2GB
- 情緒分類: ~1GB
- OpenFace (備援): ~4GB

卡 3 (ASR + NLU):
- Whisper Large: ~10GB
- vLLM 70B AWQ: ~40GB

卡 4 (TTS):
- MeloTTS: ~1GB
- Bark: ~4GB
- XTTS-v2: ~3GB

卡 5 (VLM):
- Qwen2.5-VL 72B: ~42GB
- 或 LLaVA-1.6: ~8GB
```

### 3.3 頻寬與延遲預算

| 資料類型 | 大小 | 頻率 | 頻寬需求 | 延遲目標 |
|---------|------|------|----------|----------|
| 人臉 ROI crop | ~50KB | 5 Hz | 250 KB/s | <100ms |
| 手勢 landmarks | ~1KB | 10 Hz | 10 KB/s | <50ms |
| 語音 chunk | ~16KB | 20 Hz | 320 KB/s | <20ms |
| 語義摘要 | ~5KB | 2 Hz | 10 KB/s | <500ms |
| 行為腳本 | ~2KB | 按需 | - | <100ms |

**網路要求**: 穩定 10Mbps+，延遲 <20ms (LAN) 或 <50ms (5G)

---

## 4. 風險控制措施

### 4.1 技術風險

| 風險 | 嚴重度 | 對策 | 監控指標 |
|------|--------|------|----------|
| 雲端斷線 | 🔴 高 | 快系統自主降級運行，保留緊急停止 + 基礎跟隨 | 網路心跳包 1Hz |
| Jetson 過熱 | 🔴 高 | 動態降頻，關閉非關鍵模型，溫度 >85°C 告警 | tegrastats 溫度 |
| 顯存不足 | 🟠 中 | Triton 動態批次管理，模型按需載入/卸載 | nvidia-smi |
| 多模態對齊失敗 | 🟠 中 | 單一模態 fallback，語音優先於手勢 | 對齊置信度分數 |
| LLM 幻覺 | 🟠 中 | Safety Layer 過濾危險指令，限速限範圍 | 指令合法性檢查 |
| 人臉誤識別 | 🟡 低 | 置信度門檻 0.8，連續 3 幀確認 | 識別置信度 |
| 手勢抖動 | 🟡 低 | 時間濾波，穩定 0.5s 才觸發 | 手勢穩定性分數 |

### 4.2 安全機制

**硬體安全層** (Jetson，不可繞過):
```python
# Safety Layer 偽代碼
if cmd_vel.linear.x > MAX_LINEAR:
    cmd_vel.linear.x = MAX_LINEAR  # 強制截斷
if no_heartbeat_from_cloud > 3s:
    enter_local_mode()  # 斷線降級
if lidar_obstacle_distance < 0.5m:
    emergency_stop()  # 緊急停止優先
```

**行為約束**:
- 最大線速度: 0.3 m/s (雲端建議值僅供參考，邊緣強制限速)
- 最大角速度: 0.5 rad/s
- 最大執行時間: 10s (需重新確認才繼續)
- 最小障礙距離: 0.5m (LiDAR 硬體中斷)

### 4.3 降級策略

| 層級 | 觸發條件 | 可用功能 |
|------|----------|----------|
| **完整模式** | 全系統正常 | 所有功能 |
| **降級模式 1** | 雲端延遲 >2s | 本地 Whisper Tiny + 規則 NLU，基礎手勢 |
| **降級模式 2** | 雲端斷線 | 緊急停止、基礎跟隨、簡單手勢 (停/跟隨) |
| **安全模式** | Jetson 過熱/記憶體不足 | 僅緊急停止 + 緩慢移動至充電座 |

---

## 5. 可量化 KPI

### 5.1 性能指標

| 指標 | Phase 1 目標 | Phase 2 目標 | Phase 3 目標 | 測量方法 |
|------|-------------|-------------|-------------|----------|
| 端到端手勢延遲 | <100ms | <100ms | <100ms | 手勢完成 → Skill 觸發 |
| 人臉偵測率 | >90% | >95% | >98% | 測試集 100 張 |
| 身份識別準確率 | - | >90% | >95% | 已知人員 10 人 |
| 語音喚醒率 | - | >95% | >98% | 100 次喚醒測試 |
| ASR 字錯率 (CER) | - | <8% | <5% | 標準中文測試集 |
| LLM 回應延遲 (TTFT) | - | <2s | <1.5s | 首次 token 時間 |
| 多模態對齊準確率 | - | >80% | >90% | 「那個」+ 指向測試 |
| 連續運行時間 | 30min | 1h | 2h | 無當機、無洩漏 |

### 5.2 功能指標

| 指標 | Phase 1 | Phase 2 | Phase 3 |
|------|---------|---------|---------|
| 可用 Skills 數量 | 4 | 8 | 15+ |
| 支援手勢種類 | 3 | 5 | 8+ |
| 對話輪次記憶 | - | 5 輪 | 20 輪 |
| 主動行為種類 | - | - | 3+ |
| 環境記憶物品數 | - | - | 10+ |

### 5.3 體驗指標

| 指標 | 目標 | 測量方式 |
|------|------|----------|
| 互動自然度 | >4/5 | 使用者主觀問卷 |
| 反應即時感 | <2s 感知延遲 | 語音總延遲 |
| 錯誤恢復 graceful | >80% 優雅處理 | 故障注入測試 |
| 學習適應效果 | 使用者滿意度提升 | 長期使用追蹤 |

---

## 6. 立即執行清單 (未來 7 天)

### Day 1 (本日)

- [ ] **建立 `skills/` 目錄結構**
  ```bash
  mkdir -p skills/{motion,perception,action,system}
  touch skills/README.md
  ```

- [ ] **確認 Jetson 環境**
  - JetPack 版本檢查: `dpkg -l | grep jetpack`
  - TensorRT 安裝確認
  - ROS2 Humble 運作正常

- [ ] **安裝 MediaPipe Python**
  ```bash
  pip install mediapipe
  # 測試基本人臉偵測
  ```

### Day 2

- [ ] **實作 `safe_move` Skill**
  - 包裝 `/move_for_duration` service
  - 加入速度限制 (MAX_LINEAR=0.3)
  - 加入時間限制 (MAX_DURATION=10.0)

- [ ] **驗證安全限制**
  ```bash
  # 測試超限應被截斷
  ros2 service call /move_for_duration go2_interfaces/srv/MoveForDuration \
    "{linear_x: 0.5, duration: 15.0}"
  # 預期: 速度截斷至 0.3，時間截斷至 10.0
  ```

- [ ] **安裝 ros2_trt_pose_hand**
  ```bash
  # 參考: https://github.com/NVIDIA-AI-IOT/ros2_trt_pose_hand
  ```

### Day 3

- [ ] **實作 `emergency_stop` Skill**
  - 訂閱 `/stop_movement` topic
  - 可於任意時刻中斷當前動作
  - 測試與 `safe_move` 的互動

- [ ] **MediaPipe Hands 整合測試**
  - 讀取 D435 影像流
  - 輸出 21 點 landmarks
  - 延遲測量 (<50ms 目標)

- [ ] **定義手勢-Skill 映射**
  | 手勢 | Skill |
  |------|-------|
  | 手掌張開 | emergency_stop |
  | 招手 | follow_person |
  | 雙手下壓 | sit_down |

### Day 4

- [ ] **手勢識別驗證**
  - 靜態手勢分類 (3 種)
  - 規則式 landmarks 幾何判斷
  - 連續 3 幀穩定才觸發

- [ ] **安裝 BlazeFace (TensorRT)**
  ```bash
  # 下載 ONNX → TensorRT 轉換
  # 或使用 TensorFlow Lite → TRT
  ```

- [ ] **人臉偵測測試**
  - D435 影像輸入
  - 輸出 bbox + confidence
  - 測量延遲 (<30ms 目標)

### Day 5

- [ ] **雲端環境確認 (5×RTX 8000)**
  - CUDA 版本檢查
  - Docker + NVIDIA Container Toolkit
  - Triton Inference Server 安裝

- [ ] **部署 InsightFace (卡 1)**
  ```bash
  # Docker 化部署
  docker run --gpus '"device=0"' -d --name insightface \
    -p 8001:8001 insightface-triton:latest
  ```

- [ ] **測試人臉 embedding API**
  ```bash
  curl -X POST http://rtx8000-server:8001/embed \
    -F "image=@face_crop.jpg"
  # 預期: 512-dim 向量
  ```

### Day 6

- [ ] **邊緣-雲端人臉管線**
  - Jetson: ROI crop → base64 → HTTP POST
  - 雲端: embedding → Faiss 檢索
  - 回傳身份標籤
  - 測量端到端延遲

- [ ] **安裝 Silero VAD**
  ```bash
  pip install silero-vad
  ```

- [ ] **VAD 測試**
  - 麥克風輸入 → VAD → 語音段落輸出
  - 延遲測量 (sub-ms 目標)

### Day 7

- [ ] **Phase 1 整合測試**
  - 手勢 + 人臉 + VAD 同時運作
  - tegrastats 監控資源使用
  - 記錄所有延遲數據

- [ ] **撰寫測試報告**
  - 各項 KPI 實際數值
  - 發現的問題與解決方案
  - Phase 2 調整建議

- [ ] **Phase 1 驗收會議**
  - Demo 展示
  - 團隊回饋
  - Phase 2 計畫確認

---

## 附錄: 關鍵指令速查

### Jetson 監控
```bash
# 即時監控
watch -n 1 tegrastats

# 溫度檢查
cat /sys/class/thermal/thermal_zone*/temp

# GPU 使用率
sudo apt install jtop
jtop
```

### 雲端 (RTX 8000) 監控
```bash
# GPU 狀態
nvidia-smi -l 1

# Docker GPU 容器
docker run --gpus all --rm nvidia/cuda:12.0-base nvidia-smi
```

### 測試指令
```bash
# ROS2 topic 檢查
ros2 topic hz /camera/image_raw
ros2 topic echo /gesture_cmd

# 服務呼叫測試
ros2 service call /move_for_duration go2_interfaces/srv/MoveForDuration \
  "{linear_x: 0.2, angular_z: 0.0, duration: 2.0}"
```

---

**維護者**: FJU PawAI 專題組  
**相關文件**:
- `docs/人臉辨識/README.md`
- `docs/手勢辨識/README.md`
- `docs/語音功能/README.md`
- `docs/mission/roadmap.md`
- `docs/refactor/refactor_plan.md`
