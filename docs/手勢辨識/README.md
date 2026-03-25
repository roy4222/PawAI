# 手勢辨識系統

> Unitree Go2 Pro + Jetson Orin Nano 8GB + RealSense D435 + 5×RTX 8000

## 目標效果

- 用手勢指揮機器狗
- **靜態手勢**：停止 (stop)、確認 (thumbs_up)、同意 (ok)
- **4/13 Demo 目標**：stop / thumbs_up / ok 三種手勢，成功率 ≥ 70%

> **2026-03-25 更新**：point 已從主線手勢清單移除（Gesture Recognizer 辨識不穩定），wave 為動態手勢保留研究。主線手勢為 stop / thumbs_up / ok。

### 手勢可靠度分級（2026-03-17 社群調查）

| Tier | 手勢 | 可靠度 | 說明 |
|:----:|------|:------:|------|
| **1** | **Open Palm / Stop** ✋ | 極高 | 五指展開，特徵極度明顯，幾乎不混淆 |
| **1** | **Point** 👉 | 高 | 食指獨立伸展，其他握拳，特徵獨特 |
| **1** | **Closed Fist** ✊ | 極高 | 所有指尖靠近手掌，與任何「張開」手勢對比強烈 |
| 2 | Thumbs Up 👍 | 中高 | 拇指 keypoint 精度較差，側面角度易與 fist 混淆 |
| 2 | Victory / Peace ✌️ | 中 | 中指半伸展時與 point 混淆 |
| **3** | **~~OK~~ 👌** | **低** | 拇指食指精度要求高，DWPose 遮擋場景 AP 降到 45%，易與 fist/palm 混淆 |
| — | Wave 👋 | 需時序 | 靜態幀與 Open Palm 完全相同，必須靠動態來回運動區分 |

> **關鍵決策（2026-03-17）**：原方案的 OK 手勢替換為 **Closed Fist（握拳）**。OK 依賴拇指/食指尖距離判定，在 DWPose 遮擋場景下 hand AP 從 78% 降到 ~45%，Demo 場景不可靠。Closed Fist 是 Tier 1，MediaPipe / trt_pose_hand / NVIDIA 官方範例都將其列為首選手勢之一。

### 常見混淆組合

| 手勢 A | 手勢 B | 混淆原因 | 嚴重度 |
|--------|--------|---------|:------:|
| Victory (V) | Point (指) | 中指半伸展時分不清 | 高 |
| OK | Closed Fist | 三指未完全展開 | 中 |
| Open Palm | Wave | 靜態幀完全相同 | 高（需時序區分） |
| Thumbs Up | Closed Fist | 側面角度拇指不可見 | 中 |
| Stop | Open Palm | 語義不同但手型相同 | 高（需靠位置區分） |

---

## 技術選型結論（2026-03-25 更新）

### 主線方案：MediaPipe Gesture Recognizer

| 優先序 | 方案 | 理由 |
|:------:|------|------|
| **主線** | **MediaPipe Gesture Recognizer Task API** | CPU 7.2 FPS（Jetson 實測），7 種內建手勢，GPU 0%，RAM 友善，3/23 場景驗證通過 |
| 備援 | **MediaPipe Hands + gesture_classifier.py** | CPU 16.8 FPS，但只有 3 種手勢（缺 thumbs_up），point 規則過嚴 |
| 備援 | **rtmlib + RTMPose wholebody** | GPU 91-99% 滿載，3.8-7.5 FPS，手部 keypoints 不穩定，已降為備援 |
| **不推薦** | ~~MMPose + MMDeploy 全套~~ | JetPack 6 零社群驗證、MMCV 編譯 OOM、Issue 零回覆 |

> **決策變更紀錄（3/21）**：原推薦 RTMPose wholebody 為主線，但 Jetson 實測 GPU 91-99% 滿載、手部 keypoint 不穩定。3/21 決策改為全 MediaPipe CPU pipeline（GPU 0%），3/22 整合 Gesture Recognizer Task API，3/23 場景驗證通過後確定為主線。

### ⚠️ 重大發現：DWPose 45 FPS 數據可疑（2026-03-17 調查）

> **社群深度調查後的結論**：找不到任何人直接在 Jetson Orin Nano 上跑 DWPose wholebody 的公開成功記錄。

**實際數據**：
- DWPose wholebody (YOLOX-L + DWPose-l) 在 **RTX 4090** 上只有 **~19 FPS**
- Jetson Orin Nano 算力約 RTX 4090 的 **1/30**（1.28 vs 82.6 TFLOPS FP16）
- 推算 Jetson Orin Nano 上 DWPose wholebody：**3-5 FPS（不可用）**
- MMPose 在 JetPack 6 上的安裝 Issue ([#3133](https://github.com/open-mmlab/mmpose/issues/3133))：**零回覆**
- MMPose 社群 Discussion ([#2824](https://github.com/open-mmlab/mmpose/discussions/2824))：**零回覆**

**45 FPS 的來源**：社群文章數據可能是 RTMPose body-only (17 kp) 而非 wholebody (133 kp)，或是在更強的 GPU 上測的。

### rtmlib — 推薦的部署路徑

[rtmlib](https://github.com/Tau-J/rtmlib) 是 RTMPose 系列的**輕量封裝**，不需要 mmcv / mmpose / mmdet：

- 只依賴 `numpy + opencv + onnxruntime`
- `pip install rtmlib` 一行安裝
- 支援 RTMPose / DWPose / RTMO / RTMW 全系列
- 支援 onnxruntime / tensorrt / openvino backend
- 三種模式：`lightweight` / `balanced` / `performance`

```python
# Hand 21 keypoints
from rtmlib import Hand
hand = Hand(backend='onnxruntime', device='cuda')
keypoints, scores = hand(img)

# Wholebody 133 keypoints（手勢+姿勢共用）— 主路徑
from rtmlib import Wholebody
wholebody = Wholebody(mode='balanced', backend='onnxruntime', device='cuda')
keypoints, scores = wholebody(img)
```

**主路徑：RTMPose wholebody 單模型**，一次推理同時產出 body + hand keypoints，分別餵給 pose_classifier 和 gesture_classifier。備援為 hand-only + body-only 雙模型（wholebody 在 Jetson 上無法穩定達到展示需求時啟用）。DWPose 保留為後續精度升級選項。

**Jetson 上搭配 `onnxruntime-gpu`**（[Jetson Zoo](https://elinux.org/Jetson_Zoo) 有 pre-built wheel）即可用 GPU 加速，繞過 MMPose 在 Jetson 上的所有編譯地獄。

### DWPose vs RTMPose 差異

- **RTMPose**：MMPose 原版，提供 body-only (17) / hand-only (21) / whole-body 等多種 config，ONNX/TensorRT 匯出路徑較成熟。**本專案主路徑**
- **DWPose**：RTMPose 的蒸餾版，whole-body 133 keypoints，精度略優（尤其手部）。但 Jetson 上零成功記錄、推算 FPS 極低。**降為研究線 — 待 RTMPose 路徑穩定後再評估是否值得切換**

兩者**不是完全等價替換**：DWPose 蒸餾後精度略優，但 RTMPose 的社群資源、匯出文件、Jetson 可行性都明顯更好。

### MediaPipe 在 Jetson 上的狀況（3/16 調查 → 3/21 實測推翻）

> **2026-03-21 更新**：以下問題在實測中**已被推翻**。MediaPipe 在 Jetson ARM64 上可以正常運行（CPU-only），Gesture Recognizer 7.2 FPS、Hands 16.8 FPS，已確定為主線方案。原始調查結論保留供參考。

1. **無法 `pip install`**：PyPI 無 Linux ARM64 wheel，必須從 source build（需 Bazel，耗時 1-2 小時）
2. **GPU 加速不可用**：即使 build 成功，TFLite GPU delegate 在 Jetson 上無法正確初始化
3. **CPU-only 效能差**：有使用者回報 Jetson Orin Nano 上 <5 FPS（TFLite CPU delegate）
4. **社群 wheel 過舊**：PINTO0309/mediapipe-bin 停在 v0.8.5，不支援新版 Task API
5. **JetPack 6.x 建構困難**：CUDA 12.6 + 新 linker 導致編譯失敗

**原始結論（已推翻）**：~~MediaPipe 不適合 Jetson 部署~~。實測證明 CPU-only 模式可用，且 GPU 0% 的特性反而有利於多感知共存。

---

## 方案比較（Jetson Orin Nano 8GB — 2026-03-25 實測數據更新）

| 方案 | Keypoints | FPS (Orin Nano) | GPU 佔用 | 手勢分類 | 狀態 |
|------|-----------|:---------------:|:--------:|:--------:|:----:|
| **MediaPipe Gesture Recognizer** | 21 hand | **7.2 (CPU 實測)** | **0%** | **7 種內建** | **主線** |
| **MediaPipe Hands** | 21 hand | **16.8 (CPU 實測)** | **0%** | 需自建（3 種） | 備援 |
| rtmlib + RTMPose-l (wholebody) | 133 全身 | **3.8-7.5 (GPU 實測)** | 91-99% | 需自建 | 備援 |
| rtmlib + RTMPose-m (body) | 17 body | 推估 50-100 | — | 需自建 | 未測 |
| YOLO11n-pose-hands | 21 hand | 推估 40-60 | — | 需自建 | 未測 |
| DWPose wholebody (TensorRT) | 133 全身 | ⚠️ 推估 3-5 | — | 需自建 | 不可用 |
| trt_pose_hand (NVIDIA) | 21 hand | 推估 50-60 | — | 6 類內建 | 未測 |

> **2026-03-25 結論**：MediaPipe Gesture Recognizer 在 Jetson 上 CPU-only 7.2 FPS、GPU 0%、三感知壓測通過（RAM 1.2GB, temp 52°C）。RTMPose wholebody 因 GPU 滿載已降為備援。

### 推薦落地順序（2026-03-22 更新）

1. **Phase 1**（3/16-3/18）：✅ 完成 — mock mode + 23 unit tests + Jetson smoke test
2. **Phase 2**（3/18）：✅ 完成 — RTMPose wholebody on Jetson，GPU 91-99%
3. **Phase 2b**（3/21）：✅ 完成 — 決策：全 MediaPipe CPU（GPU 0%，16.8 FPS hands）
4. **Phase 3**（3/22）：✅ 完成 — FPS 優化 2.5→8.5、骨架可視化（火柴人）、型別安全、32 tests
5. **Phase 3b**（3/22）：✅ 完成 — Gesture Recognizer Task API 整合為 `gesture_backend=recognizer` 選項。7 種內建手勢（stop/fist/point/thumbs_up/victory/thumbs_down/i_love_you）。Jetson live 測通過（7.2 FPS、手勢辨識正確、手部骨架 overlay 正常）。38 tests pass
6. **Phase 4**（3/23）：✅ 完成 — 三感知壓測通過（face+pose+gesture 同跑 60s，RAM 1.2GB/7.4GB，temp 52°C，GPU 0%）。interaction_router 場景驗證通過（welcome/gesture_command/fall_alert）。**recognizer 確定為推薦後端**（mediapipe 後端缺 thumbs_up、point 規則太嚴）
7. **Phase 5**（4/6-4/13）：端到端測試 + Demo B 微調

> **三種 gesture backend**（3/23 更新）：
> - `recognizer`（**推薦**）：Gesture Recognizer Task API，7 種內建手勢，單模型一步到位，3/23 場景驗證 stop/point/thumbs_up 全通過
> - `mediapipe`：MediaPipe Hands + gesture_classifier.py 規則，只有 3 種手勢（無 thumbs_up），point 規則過嚴
> - `rtmpose`（已棄用）：RTMPose wholebody 手部 keypoints 不可靠
>
> 使用 recognizer：`gesture_backend:=recognizer`（launch override）

---

## 邊緣端 (Jetson 8GB) - 即時反應

### 手部關鍵點偵測與手勢辨識

#### MediaPipe Gesture Recognizer（主線，2026-03-25 確定）

- **Gesture Recognizer Task API**：單模型一步到位，內建 7 種手勢分類
- CPU-only 7.2 FPS，**GPU 0%**（與 face/pose 共存零衝突）
- 主線手勢：stop / thumbs_up / ok
- 啟動：`gesture_backend:=recognizer`（launch override）

#### MediaPipe Hands + gesture_classifier.py（備援）

- CPU-only 16.8 FPS，GPU 0%
- 只有 3 種手勢（stop/ok/fist），缺 thumbs_up，point 規則過嚴
- 啟動：`gesture_backend:=mediapipe`

#### rtmlib + RTMPose wholebody（備援，GPU 密集）

- GPU 91-99% 滿載，3.8-7.5 FPS
- 手部 keypoints 不穩定，已降為備援
- 啟動：`gesture_backend:=rtmpose`（已棄用標記）

### 靜態手勢分類

**常見做法**：Landmarks → 規則分類器

- Landmarks 角度/距離特徵
- 延遲低、可控、易加入自訂手勢
- 4 種手勢用**規則分類器**就足夠，不需要訓練模型

| 手勢 | 分類邏輯 | 關鍵 Landmarks | 可靠度 |
|------|---------|---------------|:------:|
| stop ✋ | 五指伸展 + 手腕在胸前 | 所有指尖 + 手腕 + 肩膀 | Tier 1 |
| point 👉 | 食指伸展 + 其他手指握拳 | 食指指尖/根部 + 其他指尖 | Tier 1 |
| fist ✊ | 所有指尖靠近手掌中心 | 所有指尖 + 手掌中心 | Tier 1 |
| wave 👋 | 手掌張開 + 五指伸展 + **來回運動** | 所有指尖 + 手腕 + 時序 buffer | 需時序 |

### gesture_classifier 虛擬碼

```python
# COCO-WholeBody hand keypoint indices (21 points per hand)
# 0: wrist, 1-4: thumb, 5-8: index, 9-12: middle, 13-16: ring, 17-20: pinky
# fingertip indices: [4, 8, 12, 16, 20]
# finger MCP indices: [2, 5, 9, 13, 17]  (proximal joints)

FINGERTIP = [4, 8, 12, 16, 20]
FINGER_MCP = [2, 5, 9, 13, 17]
INDEX_TIP, INDEX_MCP = 8, 5
THUMB_TIP = 4
WRIST = 0

def is_finger_extended(kp, tip_idx, mcp_idx, threshold=0.3):
    """指尖到手腕距離 > MCP 到手腕距離 × (1 + threshold)"""
    tip_dist = distance(kp[tip_idx], kp[WRIST])
    mcp_dist = distance(kp[mcp_idx], kp[WRIST])
    return tip_dist > mcp_dist * (1 + threshold)

def classify_gesture(hand_kp, hand_scores, body_kp, buffer, min_confidence=0.5):
    """
    hand_kp: (21, 2) hand keypoints
    hand_scores: (21,) per-keypoint confidence
    body_kp: (17, 2) body keypoints (for shoulder/wrist height check)
    buffer: deque(maxlen=10) for temporal voting
    """
    # --- Confidence gate: 手部 keypoint 平均 confidence 太低就跳過 ---
    if np.mean(hand_scores) < min_confidence:
        return None

    extended = [is_finger_extended(hand_kp, FINGERTIP[i], FINGER_MCP[i])
                for i in range(5)]
    n_extended = sum(extended)

    # 1. Closed Fist: 所有手指都沒伸展
    if n_extended == 0:
        buffer.append("fist")

    # 2. Point: 只有食指伸展
    elif extended[1] and n_extended == 1:
        buffer.append("point")

    # 3. Stop / Open Palm: 五指都伸展
    elif n_extended >= 4:
        # 檢查是否有來回運動 → wave
        if _detect_wave_motion(buffer):
            buffer.append("wave")
        else:
            buffer.append("stop")

    # --- 投票（5 幀 buffer，手勢需要比姿勢更快回應）---
    if len(buffer) >= 5:
        from collections import Counter
        vote = Counter(buffer).most_common(1)[0]
        if vote[1] >= 3:  # 5 幀中至少 3 幀一致
            return vote[0]
    return None

def _detect_wave_motion(buffer, min_reversals=2):
    """檢測手腕 x 座標在最近 15 幀是否有 >= 2 次方向反轉"""
    # 實作時從 buffer 中取 wrist x 軌跡
    # 計算方向變化次數
    # >= min_reversals 次反轉 = wave
    pass
```

**分類器穩定性提升技巧**：

1. **Kalman Filter 降抖動**：社群回報可降低 ~25% keypoint 抖動
2. **5 幀投票 buffer**（手勢比姿勢的 20 幀短，需更快回應）
3. **Hysteresis（遲滯）**：進入閾值和退出閾值不同（如進入 fist 需所有指尖距離 < 0.3，退出需 > 0.5）
4. **Confidence gate**：hand keypoint 平均 confidence < 0.5 時不做判定，避免遮擋場景的 false positive

### 動態手勢 (揮手辨別)

**方法**：追蹤 landmarks 時間序列

| 方法 | 特點 |
|------|------|
| **規則** | 軌跡方向/速度/來回偵測（10-20 幀 buffer） |
| **DTW/HMM** | 時間序列匹配 |
| **輕量 RNN/TCN** | 深度學習分類（overkill for 4 gestures） |

**限制**：
- 遮擋造成 landmarks 抖動
- 快速運動失真
- 相機視角改變

---

## D435 深度整合實戰（2026-03-17 社群調查）

### D435 在手勢辨識中的六大已知坑

#### 坑 1: `align` 在 ARM 上極慢 — **最高風險**

D435 的 RGB 和深度感測器 FOV 不同（RGB 69x42 vs Depth 87x58），需要 `rs2::align` 對齊。但此函式在 x86 上用 SSSE3 指令加速，ARM 完全無法受益。

| 環境 | Align FPS |
|------|:---------:|
| x86 桌面 | 30 FPS |
| Jetson ARM（apt 安裝） | **2-5 FPS** |
| Jetson ARM（CUDA 編譯） | 20-30 FPS |

**必做**：確保 Jetson 上的 librealsense 用 `BUILD_WITH_CUDA=ON` 編譯。如果不是，`align` 將吃掉整個運算預算。

**替代方案**：左 IR 相機與深度圖天生像素對齊，若不需要彩色，直接用左 IR 影像可跳過 align。

Sources: [librealsense#2257](https://github.com/IntelRealSense/librealsense/issues/2257), [realsense-ros#2168](https://github.com/IntelRealSense/realsense-ros/issues/2168)

#### 坑 2: 最小深度距離 (MinZ) ~17cm

D435 官方 MinZ ~10.5cm，但推薦的 848x480 解析度下實際 MinZ 約 **16.8cm**。MinZ 以內完全沒有深度資料。

**影響**：手在鏡頭前 15cm 以內比手勢時，深度圖出現黑洞。

**緩解**：本專案手勢工作距離 0.5-2m，在 D435 甜蜜點內，此問題**影響不大**。加 depth threshold filter (min=0.3m, max=3.0m) 即可。

#### 坑 3: Flying Pixels（手指邊緣假深度）

D435 深度圖在前景/背景邊界產生虛假深度值（flying pixels），手指細窄處特別嚴重。

**緩解**：
- 加 temporal filter + spatial filter（SDK 內建）
- **不要用深度值做手勢分類** — 用 RGB keypoints (DWPose)，深度只取手的 3D 位置和距離

#### 坑 4: 日光 / IR 干擾

D435 用 850nm IR structured light。強光（日光直射 ~100k lux）會淹沒 IR pattern，深度圖大面積失效。

**緩解**：4/13 展示在**室內可控環境**，準備手動曝光設定作為 fallback。若場地有落地窗，需遮光。

#### 坑 5: 深度雜訊（蛋殼紋抖動）

D435 近距離（0.15-1m）深度值有蛋殼紋起伏，深度誤差隨距離平方增長。

**緩解**：取 ROI 深度時用 5x5 median（不是 mean），過濾離群值。

#### 坑 6: USB 頻寬（與 HyperX 麥克風共享）

D435 + HyperX SoloCast 同時走 USB，要注意頻寬。

**緩解**：用 848x480@30fps（不要 1080p），短且品質好的 USB 3.0 線。

### 深度在手勢辨識的應用（更新版）

**策略：RGB-based keypoint 為主，深度為輔**

```
D435 RGB frame → RTMPose 推理 (rtmlib) → hand keypoints (21)
  ├── gesture_classifier（純 2D keypoint 規則）— 核心，不依賴 depth
  └── [可選] D435 aligned_depth → 取手腕 ROI 5x5 median depth
        ├── distance gate: 0.5-3m 才有效
        └── 3D pointing ray（point 手勢方向估計）
        └── ⚠️ 若 align FPS 不足 → 關閉 depth，改用 bbox 面積估距
```

1. **手勢分類完全基於 RGB keypoints**（不依賴深度）
2. **深度只做兩件事**：距離 gate + 指向方向估計
3. 這樣即使深度有雜訊/空洞，手勢辨識也不受影響

> **RGB-only 保底規則**：若 Jetson 上的 librealsense 不是 `BUILD_WITH_CUDA=ON` 編譯，或 depth align 導致整體 pipeline FPS 低於手勢辨識 gate（15 FPS），**Demo B 直接以 RGB-only keypoint gesture pipeline 落地**，depth integration 延後。距離 gate 改用 bbox 面積估計（近的人 bbox 大），不阻塞手勢主線。

---

## 多人場景策略（2026-03-17 新增）

### 問題

DWPose/YOLO 會偵測到所有人的 keypoints。需要決定「聽誰的手勢」。

### 五種策略比較

| 策略 | 複雜度 | 適合 Demo | 說明 |
|------|:------:|:---------:|------|
| **最大 Bbox** | 極低 | **推薦** | `max(detections, key=area)` — 最近的人通常 bbox 最大 |
| **最近距離 (D435)** | 低 | 好 | 取 bbox 中心 depth，選最小值 |
| **人臉 track_id 關聯** | 高 | 未來 | 與 `/state/perception/face` 的 track_id 對應 |
| **Confidence 最高** | 中 | 作為第二層 | 所有人都跑分類器，選最高 confidence |
| **注意力狀態** | 高 | 未來 | 判斷誰看著機器狗（需 head pose） |

### 4/13 Demo 推薦方案

```
YOLO / RTMDet 偵測所有人
  → 距離 gate: 只保留 0.5-3m 內的人（D435 depth，若 depth 可用）
  → 或 RGB-only fallback: 只取 bbox 面積最大者（無 depth 時）
  → 該人的 hand keypoints → gesture_classifier
```

理由：
1. 實作最快（Phase 2-3 時間緊張）
2. Demo 場景可控（操作者站前面、觀眾站後面）
3. **即使 depth 不可用，bbox 面積最大也能正確選人**（Demo 場景下等價於最近的人）
4. 未來可升級為 face track_id 關聯（「只聽認識的人的手勢」）

---

## 雲端端 (5×RTX 8000) - 精細理解

### 3D 手部姿態/網格重建

| 方案 | 功能 | 備註 |
|------|------|------|
| **FrankMocap** | 單目影像 → 身體/手/臉 3D pose | 開源 |
| **InterHand2.6M** | 雙手互動 3D dataset + baseline | 研究用 |
| **HaMeR** | Transformer 做 3D hand mesh recovery | 較新 |

### 是否需要上雲端？

| 需求 | 建議 |
|------|------|
| 基本指令 (停止/跟隨/指向/確認) | **邊緣端即可**，<100ms |
| 連續手語/複雜多模態 | 上雲端用更強模型 |

**分工策略**：
- 邊緣：手部偵測 → 低延遲指令
- 雲端：精細姿態/語義確認 (補充判斷)

---

## 機器人整合

### <100ms 延遲達成

1. 手勢辨識**必須在邊緣端完成**
2. 雲端只做「可選再確認」或「高階語義」
3. 使用 rtmlib + onnxruntime-gpu（推薦）或 TensorRT

### ROS2 控制串接

```
vision_perception_node → /event/gesture_detected (std_msgs/String JSON)
  ↓
event_action_bridge（3/18 新建）
  ↓
/webrtc_req (Go2 動作) + /tts (語音回覆)
```

### event_action_bridge 手勢→動作映射（2026-03-23 更新）

| 手勢 | Go2 動作 | TTS | Cooldown |
|------|---------|-----|:--------:|
| `stop` | api_id 1003（緊急停止） | — | **無**（安全優先） |
| `ok` | api_id 1020（回應動作） | — | 3s |
| `thumbs_up` | api_id 1020（回應動作） | "收到！" | 3s |

> **3/23 變更**：移除 wave→hello 映射（hello 統一由 llm_bridge 處理）。主線手勢為 stop / thumbs_up / ok。

> `event_action_bridge` 不觸及語音事件或人臉事件（由 `llm_bridge_node` 單獨處理），維持單一控制權。

### interaction_router 高層事件（2026-03-23 新增）

薄的事件融合層，訂閱 face + gesture + pose → 發布高層互動事件：

| 輸出 Topic | 觸發條件 | Schema |
|-----------|---------|--------|
| `/event/interaction/welcome` | `identity_stable` + 已知人臉 | `{stamp, event_type, track_id, name, sim, distance_m}` |
| `/event/interaction/gesture_command` | 白名單手勢（stop/point/thumbs_up） | `{stamp, event_type, gesture, confidence, hand, who, face_track_id}` |
| `/event/interaction/fall_alert` | `fallen` 持續 ≥ 2s | `{stamp, event_type, pose, confidence, persist_sec, who, face_track_id}` |

- 決策邏輯獨立為 `interaction_rules.py`（純函式，零 ROS2 依賴，14 tests）
- fallen 用 1Hz timer 檢查持續性，避免重複 timer
- stop 無 cooldown（安全優先）
- `welcomed_tracks`：`track_lost` 時移除，允許同一人 re-welcome
- 與 `event_action_bridge` 共存（各自訂閱原始事件，互不干擾）

**Event Schema**（對齊 `interaction_contract.md` v2.0）：
```json
{
  "stamp":       1710000000.123,
  "event_type":  "gesture_detected",
  "gesture":     "wave",
  "confidence":  0.87,
  "hand":        "right"
}
```

> **⚠️ Contract 邊界說明**：
> - `interaction_contract.md` v2.0 只凍結了 `/event/gesture_detected`。
> - **`/state/perception/gesture` 不在 v2.0 凍結範圍內**，屬 v2.1 擬新增項目，4/13 前可先作為內部 topic 使用，不納入凍結介面。正式納入需經 System Architect 核准。
> - `event-schema.md` v1.0 中的 `GestureState` 型別定義是**前端 store 用的資料結構**，與 ROS2 layer 的 topic 凍結是兩件事。
> - v2.0 契約中 gesture enum 仍為 `ok`。實作已改用 `fist`（見 §手勢可靠度分級），過渡期由 `GESTURE_COMPAT_MAP` 處理相容性，待 3/25 Phase 2 benchmark 後正式切換契約。

---

## 手勢定義與 Skill 對應（2026-03-25 更新）

| 手勢 | 類型 | 對應 Skill | 可靠度 | 優先序 |
|------|------|------------|:------:|:------:|
| stop | 靜態 | `stop()` | Tier 1 | P0 |
| thumbs_up | 靜態 | `confirm()` | Tier 2 | P1 |
| ok | 靜態 | `acknowledge()` | Tier 2 | P1 |

> **變更記錄**：
> - 3/17：OK → Fist（DWPose 遮擋場景 AP 低）
> - 3/23：主線切換為 Gesture Recognizer，支援 stop/thumbs_up/ok 三種。point 因辨識不穩定移除，wave 需時序分析保留研究。

### 多模態衝突處理

**問題**：語音說「停止」但手勢是「跟隨」

**建議策略**（4/13 Demo）：
- **stop 最高優先**（安全指令，不管來源都立即執行）
- 其他指令：最後指令優先（last-command-wins）
- 同一秒內的衝突：語音 > 手勢（語音更有明確意圖）

---

## 社群實戰回饋（2026-03-17 調查）

### DWPose / RTMPose 在 Jetson 上

| 發現 | 來源 | 影響 |
|------|------|------|
| **Jetson 上跑 DWPose wholebody 零成功記錄** | GitHub Issues、論壇搜尋 | 風險極高 |
| RTMPose-l wholebody 在 GTX 1660 Ti 上 7.7ms → **推算 Orin Nano ~32ms (~31 FPS)** | RTMPose 論文 Table 11 | 可用但偏慢 |
| RTMDet-nano + RTMPose-m (body) 推算 Orin Nano ~19ms (**~52 FPS**) | 同上 | body-only 快很多 |
| MMPose JetPack 6 安裝 Issue 零回覆 | [#3133](https://github.com/open-mmlab/mmpose/issues/3133), [#2824](https://github.com/open-mmlab/mmpose/discussions/2824) | 社群不支援 |
| MMCV 在 Jetson 上編譯 ~1h40m，4GB RAM 會 OOM | MMDeploy docs | 需 8GB+ swap |
| **rtmlib 繞過所有 MMPose 依賴** | [rtmlib](https://github.com/Tau-J/rtmlib) | 關鍵發現 |
| TensorRT engine 必須在目標裝置上建構（不能跨平台） | 多來源 | 需在 Jetson 上 build |

### D435 + 手勢辨識

| 發現 | 來源 | 影響 |
|------|------|------|
| **align 在 ARM 上 2-5 FPS**（無 CUDA 編譯） | [librealsense#2257](https://github.com/IntelRealSense/librealsense/issues/2257) | **致命瓶頸** |
| 深度雜訊隨距離平方增長 | Intel 官方文件 | 手部細節深度不可靠 |
| Flying pixels 在手指邊緣嚴重 | [librealsense#11327](https://github.com/IntelRealSense/librealsense/issues/11327) | 不影響 RGB keypoint 方案 |
| 日光直射深度完全失效 | [librealsense#2875](https://github.com/IntelRealSense/librealsense/issues/2875) | 展示場地需可控光線 |
| Jetson USB 頻寬與多裝置衝突 | NVIDIA 論壇 | 用 848x480@30fps 避開 |

### YOLO Pose 在 Jetson 上

| 發現 | 來源 | 影響 |
|------|------|------|
| YOLOv8n (C++ TensorRT FP16): 33.2 FPS | [Hackster.io 實測](https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267) | 參考值 |
| **Python post-processing 是真正瓶頸**（GPU 推理 82 FPS → 含後處理只有 10 FPS） | [NVIDIA 論壇](https://forums.developer.nvidia.com/t/slow-fps-on-orin-nano-8-gb-yolov8/280071) | 注意 Python overhead |
| 必須啟用效能模式：`sudo nvpmodel -m 0 && sudo jetson_clocks` | 多來源 | 部署時必做 |
| Ultralytics 有 [手部 keypoints 資料集](https://docs.ultralytics.com/datasets/pose/hand-keypoints/) + [YOLO11 Hand Pose Blog](https://www.ultralytics.com/blog/enhancing-hand-keypoints-estimation-with-ultralytics-yolo11) | Ultralytics 官方 | YOLO 手部方案已成熟 |

---

## 備取方案與切換條件（2026-03-17 新增）

### 方案對照表

| 方案 | 角色 | 切換成本 | FPS 預估 | 涵蓋 | 風險 |
|------|------|:--------:|:--------:|:----:|:----:|
| **rtmlib + RTMPose wholebody** | **主方案** | — | 15-31 | 手勢+姿勢 | 中（未實測） |
| **YOLO11n-pose-hands** | **備案 1** | 0.5-1 天 | 40-60 | 手勢 only | 低 |
| **PINTO0309 hand-onnx** | 備案 2 | 0.5-1 天 | 25-40 | 手勢 only | 低 |
| RTMPose hand-only (rtmlib) | 備案 3 | 0.5 天 | 60-100 | 手勢 only | 低 |
| trt_pose_hand | 備案 4 | 2-3 天 | 50-60 | 手勢 only (6 類) | 高 (JetPack 6) |

### 切換紅線（任一觸發 → 立即切備案）

在 Phase 2 前 2 天（**3/25 前**）必須驗證，以下任一條件成立即切換：

| # | 條件 | 檢測方式 | 切換對象 |
|---|------|---------|---------|
| 1 | **TensorRT/ONNX 匯出失敗** | rtmlib wholebody 在 JetPack 6 上無法載入模型 | 切 rtmlib hand-only 或 YOLO11n |
| 2 | **FPS < 15** | TensorRT FP16 / ONNX-GPU 推理含後處理 < 15 FPS | 切更輕模型 |
| 3 | **記憶體 > 1.5 GB** | 推理時統一記憶體佔用 > 1.5GB，擠壓其他常駐模組 | 切更輕模型 |
| 4 | **手部 keypoints 不可用** | 1.5-3m 距離下 hand keypoint 偵測率 < 50% | 切手部專用模型 |
| 5 | **Depth align 拖慢整體** | 加上 depth align 後 pipeline FPS 低於 15 | **關閉 depth，走 RGB-only**（不切模型） |

### 切換黃線（綜合評估）

| # | 條件 | 評估 |
|---|------|------|
| 5 | FPS 15-25 | 勉強可用，考慮是否值得切到更輕模型 |
| 6 | 手部只在 <1m 可用 | 互動距離不足，但 Demo 可讓操作者站近一點 |

### 推薦切換路徑

```
rtmlib wholebody 失敗
  ├── 模型載入/匯出問題 → 切 rtmlib hand-only（同框架，最快）
  ├── 整個 RTMPose 在 Jetson 不可行 → 切 YOLO11n-pose-hands（不同生態系）
  └── 只是手部精度不夠 → 切 PINTO0309 hand-onnx（手部專用）

注意：備案 1-3 都只有 hand keypoints，姿勢辨識需另外用 YOLO11n-pose (body) 或 rtmlib Body
```

### 關鍵時間節點

| 日期 | 里程碑 | 動作 |
|------|--------|------|
| **3/25** | Phase 2 第 3 天 | rtmlib + onnxruntime-gpu 跑通 + FPS benchmark 完成 |
| **3/27** | 紅線判斷 | 若紅線觸發，開始切備案（還有 ~17 天到 Demo） |
| **4/1** | Phase 3 開始 | 手勢推理必須跑通，進入 ROS2 整合 |
| **4/6** | Demo B 微調 | 閾值校正、投票 buffer 調整 |

---

## Demo B 驗收 SOP（2026-03-17 新增）

### 測試條件

| 項目 | 要求 |
|------|------|
| **場地** | 室內、可控光線（無強光直射）、背景簡潔 |
| **距離** | 操作者站在 D435 前方 1.0-2.0m |
| **角度** | 操作者正面面向攝影機（±30°） |
| **人數** | 單人操作、可有觀眾在背景 |
| **服裝** | 露出手掌和手指（不戴手套）、袖口不遮蓋手腕 |

### 測試流程

每種手勢測 **5 次**，共 20 次：

| 輪次 | 手勢 | 測試內容 |
|:----:|------|---------|
| 1-5 | stop ✋ | 手掌朝前，五指張開，維持 2 秒 |
| 6-10 | point 👉 | 食指指向一個方向，維持 2 秒 |
| 11-15 | fist ✊ | 握拳舉起，維持 2 秒 |
| 16-20 | wave 👋 | 手掌張開，左右揮動 3 次 |

### 通過門檻

| 指標 | 門檻 | 說明 |
|------|------|------|
| **單手勢辨識率** | ≥ 3/5 (60%) | 每種手勢至少 3 次成功 |
| **總辨識率** | ≥ 14/20 (70%) | Demo B 成功率目標 |
| **辨識延遲** | ≤ 2 秒 | 手勢做出到 `/event/gesture_detected` 發布 |
| **誤觸發率** | ≤ 2/20 (10%) | 非手勢動作（如搔頭）不應觸發事件 |
| **Jetson 記憶體增量** | < 300MB | 加上手勢模組後的增量 |

### 驗證命令

```bash
# 監聽手勢事件
ros2 topic echo /event/gesture_detected

# 確認 topic 存在
ros2 topic info /event/gesture_detected -v

# 記憶體確認
ssh jetson-nano "free -h"
```

---

## 記憶體預算（與現有模組共存）

| 模組 | 記憶體占用 | 狀態 |
|------|:--------:|:----:|
| Ubuntu + ROS2 | ~2.0 GB | 常駐 |
| D435 影像串流 | ~0.8 GB | 常駐 |
| YuNet 人臉偵測 | ~0.1 GB | 常駐 |
| Sherpa-onnx KWS | ~0.05 GB | 常駐 |
| faster-whisper (觸發式) | 0.4-1.0 GB | 觸發 |
| Piper TTS (觸發式) | 0.3-0.8 GB | 觸發 |
| **rtmlib 手勢+姿勢** | **~0.2 GB** | **常駐** |
| 安全餘量 | ≥ 0.8 GB | 必須 |
| **合計（全開）** | **~4.7-5.9 GB** | ✅ |

剩餘空間：8GB - 5.9GB = **~2.1GB**，充足。

> **注意**：若切到 YOLO11n-pose-hands + YOLO11n-pose (body) 備案，需跑兩個模型，預估增加到 ~0.3-0.4 GB。仍在預算內。

---

## 參考資源

### 推薦部署路徑
- [rtmlib — RTMPose 輕量封裝（不需 mmcv/mmpose）](https://github.com/Tau-J/rtmlib)
- [DWPose / RTMPose (MMPose)](https://github.com/open-mmlab/mmpose/tree/main/projects/rtmpose)
- [DWPose Wholebody on Jetson（社群文章）](https://johal.in/dwpose-wholebody-python-yolo-detect-2026-2/)

### 備案方案
- [YOLO11n-pose-hands (chrismuntean)](https://github.com/chrismuntean/YOLO11n-pose-hands)
- [Ultralytics Hand Keypoints Dataset](https://docs.ultralytics.com/datasets/pose/hand-keypoints/)
- [Ultralytics YOLO11 Hand Pose Blog](https://www.ultralytics.com/blog/enhancing-hand-keypoints-estimation-with-ultralytics-yolo11)
- [Ultralytics Jetson Quick Start](https://docs.ultralytics.com/guides/nvidia-jetson/)
- [PINTO0309/hand-gesture-recognition-using-onnx](https://github.com/PINTO0309/hand-gesture-recognition-using-onnx)
- [trt_pose_hand (NVIDIA)](https://github.com/NVIDIA-AI-IOT/trt_pose_hand)
- [ros2_trt_pose_hand (ROS2 wrapper)](https://github.com/NVIDIA-AI-IOT/ros2_trt_pose_hand)

### D435 深度整合
- [librealsense ARM align 效能問題 (#2257)](https://github.com/IntelRealSense/librealsense/issues/2257)
- [align_depth FPS drop on Jetson (realsense-ros#2168)](https://github.com/IntelRealSense/realsense-ros/issues/2168)
- [Tuning D435 for Best Performance](https://dev.intelrealsense.com/docs/tuning-depth-cameras-for-best-performance)
- [D435 Optical Filters](https://dev.intelrealsense.com/docs/optical-filters-for-intel-realsense-depth-cameras-d400)

### Jetson 部署經驗
- [MMPose JetPack 6 Installation (Issue #3133, 零回覆)](https://github.com/open-mmlab/mmpose/issues/3133)
- [MMDeploy Jetson Build Guide](https://mmdeploy.readthedocs.io/en/v0.14.0/01-how-to-build/jetsons.html)
- [YOLOv8 on Orin Nano FPS (NVIDIA Forum)](https://forums.developer.nvidia.com/t/slow-fps-on-orin-nano-8-gb-yolov8/280071)
- [YOLOv8 vs v26 on Orin Nano (Hackster.io)](https://www.hackster.io/qwe018931/pushing-limits-yolov8-vs-v26-on-jetson-orin-nano-b89267)
- [Multi-Model AI on Jetson (DEV.to)](https://dev.to/ankk98/multi-model-ai-resource-allocation-for-humanoid-robots-a-survey-on-jetson-orin-nano-super-310i)

### MediaPipe（僅限 x86 開發機 demo）
- [MediaPipe Hands](https://mediapipe-studio.webapps.google.com/studio/demo/hands)
- [MediaPipe Gesture Recognizer](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer)
- [MediaPipe Jetson 安裝問題](https://forums.developer.nvidia.com/t/does-jetson-orin-nano-support-mediapipe/290797)
- [MediaPipe ARM64 無 wheel (Issue #5965)](https://github.com/google-ai-edge/mediapipe/issues/5965)

### 雲端精細理解
- [FrankMocap](https://github.com/facebookresearch/frankmocap)
- [InterHand2.6M](https://github.com/facebookresearch/InterHand2.6M)
- [HaMeR](https://github.com/geopavlakos/hamer)

### RTMPose 效能基準
- [RTMPose 論文 (arxiv)](https://arxiv.org/html/2303.07399v2)
- [Dwpose-Tensorrt (TensorRT 轉換)](https://github.com/yuvraj108c/Dwpose-Tensorrt)
