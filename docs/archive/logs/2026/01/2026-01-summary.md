# 2026 年 1 月開發摘要

**月份：** 2026/01  
**期間：** W3-W7 (1/1-1/31)  
**撰寫日期：** 2026-02-11

---

## 📊 本月統計

| 指標 | 數值 |
|------|------|
| **開發日誌數** | 13 篇 |
| **週報數** | 1 篇 (W03) |
| **會議紀錄** | 1 篇 (1/17 會議) |
| **關鍵里程碑** | Jetson 架構確定、有線連線測試、文件重構規劃 |

---

## 🎯 本月重點

### 1. 架構大轉向：從雲端到邊緣運算

**1/10 晚間會議**確定了重大架構調整：

| 調整項目 | 原方案 | 新方案 | 原因 |
|---------|--------|--------|------|
| **運算位置** | GPU Server 雲端為主 | **Jetson Orin Nano 本地為主** | 延遲問題 |
| **深度估計** | Depth Anything V2 | **RealSense D435 硬體深度** | 更準確、即時 |
| **SLAM 方案** | WebRTC + slam_toolbox | **USB RealSense + slam_toolbox** | 頻率穩定 |
| **連線方式** | WiFi WebRTC | **有線 USB + WiFi 混合** | 降低延遲 |

**影響：**
- 需採購 Jetson Orin Nano SUPER 8GB
- 需採購 Intel RealSense D435 深度攝影機
- 所有開發方向調整為本地優先

### 2. 有線連線測試 (1/10)

Roy 成功建立 Mac VM 與 Go2 的有線連線：

**網路拓樸：**
```
Mac VM (192.168.123.100) ←有線→ Go2 MCU (192.168.123.161)
```

**測試結果：**
- ✅ Mac → Go2 MCU ping: 0.5-0.8ms
- ✅ VM → Go2 MCU ping: 0.5-1.3ms
- ❌ **重大發現**：Go2 Pro 有線模式無法取得 ROS2 Topics

**結論：**
Go2 Pro (一般版) 的有線僅能到達 MCU，無法像 EDU 版一樣取得完整 ROS2 資料。必須回到 WiFi WebRTC 模式，或升級到 EDU 版。

### 3. SLAM 問題診斷 (1/19)

**發現嚴重問題：**
- `/point_cloud2` 頻率僅 **0.30-0.8 Hz**（目標 ≥10 Hz）
- `/scan` 頻率 **0.1-2 Hz**（目標 ≥5 Hz）
- SLAM 無法正常建圖 (`/map` 幾乎全 -1)

**根因：**
WebRTC 網路傳輸瓶頸，Go2 Pro 的 LiDAR 資料無法穩定傳輸。

**解決方案：**
必須切換到 Jetson 本地架構，讓 LiDAR/相機直接連接 Jetson (USB)，繞過 WebRTC 瓶頸。

### 4. Jetson SLAM 方案文獻調研 (1/24)

Roy 針對 Jetson Orin Nano SUPER 8GB 進行詳細技術調研：

**四個關鍵問題：**

| 問題 | 結論 |
|------|------|
| Isaac ROS cuVSLAM 可行性 | ⚠️ 可用但不推薦，佔用 20-30% GPU |
| slam_toolbox + RTAB-Map 融合 | ❌ 不建議，會有 TF 衝突 |
| RealSense D435 可用性 | ✅ 完全支援，但需 JetPack 6.0+ |
| 雙層架構任務分配 | 本地 SLAM + 雲端 LLM |

**推薦方案：**
- **SLAM**: slam_toolbox (CPU 模式)，為其他 AI 任務保留 GPU
- **深度**: RealSense D435 硬體深度，不再使用 Depth Anything
- **物件偵測**: YOLO-World (本地執行)

### 5. 團隊任務分配 (1/10 會議)

| 組員 | 研究方向 | 目標 |
|------|---------|------|
| **A (Roy)** | LLM 本地部署 | Qwen、Mistral、Nvidia Nano 系列評估 |
| **B (如恩)** | 語音轉文字 | FunASR、Whisper 中文支援評估 |
| **C (佩蓁)** | VLA 模型 | Vision-Language-Action 架構研究 |
| **D (雨彤)** | 硬體擴展 | 深度相機 + Nvidia Jetson 運算板 |

---

## 📁 本月產出文件

| 日期 | 文件 | 說明 |
|------|------|------|
| 1/1 | 2026-01-01-dev.md | 新年首日開發 |
| 1/2 | 2026-01-02-dev.md | 週報整理 |
| 1/7 | 2026-01-07-dev.md | 1/7 評審後規劃 |
| 1/9 | 2026-01-09-dev.md | 架構調整討論 |
| 1/10 | 2026-01-10-dev.md | 有線連線測試 + 晚間會議 |
| 1/12 | 2026-01-12-dev.md | Jetson 研究啟動 |
| 1/13 | 2026-01-13-dev.md | 技術調研 |
| 1/16 | 2026-01-16-dev.md | SLAM 問題初步 |
| 1/17 | 2026-01-17-meeting.md | 專題會議紀錄 |
| 1/17 | 2026-01-17-dev.md | STT/LLM/VLA 研究 |
| 1/19 | 2026-01-19-dev.md | SLAM 診斷清單 |
| 1/24 | 2026-01-24-dev.md | Jetson SLAM 文獻調研 |

---

## ✅ 本月完成項目

- [x] 確定 Jetson Orin Nano SUPER 8GB 為主要運算平台
- [x] 完成有線連線測試，發現 Go2 Pro 有線限制
- [x] 診斷 SLAM 問題，確認 WebRTC 瓶頸
- [x] 完成 Jetson SLAM 方案文獻調研
- [x] 確定 FunASR 為 STT 首選、Qwen2.5-3B 為 LLM 首選
- [x] 團隊分工確認 (STT/LLM/VLA/硬體)

---

## 🚧 進行中項目

- [ ] Jetson Orin Nano 環境建置
- [ ] RealSense D435 SDK 安裝
- [ ] slam_toolbox CPU 模式調校
- [ ] YOLO-World Jetson 優化

---

## 💡 本月學習

### 關鍵技術發現

1. **Go2 Pro vs EDU**: 有線模式無法取得 ROS2 Topics，僅能控制 MCU
2. **WebRTC 瓶頸**: LiDAR 資料傳輸頻率嚴重不足 (0.3Hz vs 目標 10Hz)
3. **Jetson 記憶體**: 8GB 必須謹慎分配，cuVSLAM 會佔用 1.5-2GB RAM
4. **FunASR 優勢**: 中文優化、流式輸出、適合即時互動

### 架構教訓

- ❌ 純雲端方案：延遲過高、網路依賴
- ✅ 本地優先方案：即時反應、離線可用
- ⚠️ 必須在效能與功能間取捨 (8GB 限制)

---

## 📅 下月 (2月) 計畫

| 週次 | 重點 |
|------|------|
| W8 | Jetson 環境建置、RealSense 整合 |
| W9 | Skills 架構設計、文件重構 |
| W10 | Sensor Gateway 開發 |
| W11 | YOLO-World 整合 |

---

**記錄者：** Roy  
**審閱：** 微風老師
