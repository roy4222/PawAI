# 物件偵測升級 — Benchmark Protocol

> 文件類型：可執行 protocol（場地設置 + 量測表 + A/B 步驟 + 通過門檻）
> 日期：2026-05-20
> 關聯：[研究 brief](2026-05-20-object-perception-research-brief.md) ／ [北極星 §2](2026-05-19-pawai-may-june-north-star-design.md)
> 適用：今晚 demo 結束、`nav-cap-demo` 停掉後在現場直接執行

---

## 1. 目的與範圍

回答研究 brief §7 的七個待驗證問題。具體做兩件事：

1. **量現況到底爛在哪**（baseline，Step 0）
2. **走 6 步 A/B**（Step 1–6），每步獨立、可中止

**硬規則（不可破）**：
- 不修 `main` 分支
- 不 deploy（不 `pawai jetson deploy --module object`）
- 不動 Jetson 既有 install
- 所有改動只走臨時 `ros2 run` 的 `--ros-args` 覆寫；Step 5/6 用離線 rosbag replay 腳本，**不入 node**
- 若要試 26s `.onnx`，只 `cp` 到 `/home/jetson/models/yolo26s.onnx`，**不覆蓋** 26n
- 不 `pip install ultralytics`

通過 / 失敗門檻對應到研究 brief §2 的成功標準，見本文件 §5。

---

## 2. 環境前置 checklist（Jetson 端）

依序確認，**全綠才開 Step 0**。

| # | 項目 | 指令 / 預期 |
|---|---|---|
| 1 | `nav-cap-demo` 已停 | `tmux ls` 無 `nav-cap-demo`；`ps aux \| grep -E "nav2\|amcl\|sllidar\|reactive_stop"` 無殘留 |
| 2 | Go2 driver 已停 | `pgrep -fa go2_driver` 無輸出（物件偵測不需 Go2 driver） |
| 3 | D435 已停或乾淨 | `pgrep -fa realsense2_camera` 無殘留；待會由本 protocol 啟動 |
| 4 | RAM / 溫度起點 | `free -h` available ≥ 4GB；`cat /sys/class/thermal/thermal_zone*/temp` < 60°C |
| 5 | 模型檔 | `ls -la /home/jetson/models/yolo26n.onnx`（必須存在）；26s 待 Step 3 才放 |
| 6 | TRT cache | `ls /home/jetson/trt_cache/` 有檔；若這次要清重建，先 `mv` 備份不 `rm` |
| 7 | Deploy metadata | `pawai status --short` ＋ `cat ~/elder_and_dog/.pawai-last-deploy` — 記下 install 對應的 branch / sha / dirty flag。**Jetson rsync tree 沒有 `.git`**，不要跑 `git status`。 |

**必查：TensorRT EP 是否真的 active**（研究 brief §3 假設 4 的前提）：
```bash
ros2 run object_perception object_perception_node --ros-args -p tick_period:=2.0 2>&1 | head -30
```
log 必須出現 `TensorrtExecutionProvider`；若只出現 `CPUExecutionProvider` 或 `CUDAExecutionProvider` 但沒 TRT，**全部 baseline 與 A/B 數據無效**，先修 provider 配置再回來。

---

## 3. Baseline 量測（Step 0）

### 3.1 場地設置

**物件清單**：
- 必達（5）：杯子、手機、書、椅子、背包
- 觀察（3）：瓶子、遙控器、時鐘

**變數矩陣**：
- 距離：1m / 1.5m / 2m（相機到物件中心）
- 光線：正常室內 / 偏暗（關主燈、留環境光）/ 背光（物件背對窗戶或燈）

**每組（物件 × 距離 × 光線）拍攝**：30 秒，物件靜止為主，最後 5 秒輕微旋轉以測 bbox 穩定度。

**rosbag 必須錄三個 topic**（離線 replay Step 5/6 會用到）：
```bash
ros2 bag record \
  /camera/camera/color/image_raw \
  /perception/object/debug_image \
  /event/object_detected \
  -o /home/jetson/bags/baseline_$(date +%Y%m%d_%H%M%S)
```

**為什麼三個都要**：
- `/camera/camera/color/image_raw` 是**唯一可機讀的原始來源**。Step 4/5/6 的離線分析都從這個 topic 重新跑 YOLO（離線 ONNX inference 腳本，與 node 隔離），產出每幀 raw detections（class + bbox + score），這份 raw detections 才是 voting / class threshold / 顏色處理的真正輸入。
- `/event/object_detected` 因 `class_cooldown_sec=5.0` cooldown，**不是** 每幀 raw — 只作 baseline 「目前 node 真實對外行為」的對照樣本。
- `/perception/object/debug_image` 是渲染後的視覺對照（PIL 中文標籤），**不是機讀資料**，僅供人眼看 baseline 表現。

換句話說：rosbag 錄的是「現場相機輸入 + 當前 node 對外行為」；Step 4–6 的離線比對都靠**離線重跑 YOLO** 生成 raw detections，不靠 rosbag 內的事件流。

### 3.2 啟動指令（baseline，不改任何參數）

```bash
# Terminal A: D435
ros2 launch realsense2_camera rs_launch.py enable_depth:=false pointcloud.enable:=false

# Terminal B: object_perception（預設參數）
ros2 launch object_perception object_perception.launch.py

# Terminal C: rosbag 錄影（依物件 × 距離 × 光線輪流）
ros2 bag record ... -o /home/jetson/bags/baseline_<物件>_<距離>_<光線>
```

### 3.3 量測指標表（每組填一列；空表，跑完回填）

| 物件 | 距離 | 光線 | detect rate (%) | avg conf | 漏檢次數 (/30s) | 誤檢類別 | bbox 抖動 (px std) | 事件閃爍 (DETECTED↔LOST /30s) | obj FPS | RAM avail (GB) | temp (°C) | TRT EP active? |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 杯子 | 1m | 正常 | | | | | | | | | | |
| 杯子 | 1m | 偏暗 | | | | | | | | | | |
| 杯子 | 1m | 背光 | | | | | | | | | | |
| 杯子 | 1.5m | 正常 | | | | | | | | | | |
| ... | ... | ... | | | | | | | | | | |

（共 8 物件 × 3 距離 × 3 光線 = 72 列。實務上可先跑 5 必達 × 1m+2m × 正常+偏暗 = 20 列作快速基線，背光 / 觀察集分批補。）

### 3.4 量測方式速查

- **detect rate**：30s rosbag 中 frame-by-frame 是否有 detection / 總 frame 數
- **avg conf**：所有 detection 的 `score` 平均
- **漏檢**：物件在畫面但無 detection 的連續 frame 段數
- **誤檢類別**：output 是否出現非該物件的 class label
- **bbox 抖動**：bbox center / size 在連續幀的標準差（離線分析 rosbag）
- **事件閃爍**：30s 內 `/event/object_detected` 對同一 class 的 DETECTED / LOST 次數
- **obj FPS**：`ros2 topic hz /perception/object/debug_image` 平均（量 30s）
- **RAM**：`free -h` `available` 欄
- **temp**：`cat /sys/class/thermal/thermal_zone0/temp`（除 1000 = °C）
- **TRT EP active**：node 啟動 log（已在 §2 確認）

---

## 4. A/B 順序（六步，每步獨立可中止）

每步流程相同：
1. 停舊 node（保 D435 不停）
2. 用新參數重啟 node
3. 跑同樣的物件 × 距離 × 光線組合（建議至少 5 必達 × 1m+2m × 正常光，~10 組）
4. 錄 rosbag
5. 填入下表 Δ 欄
6. 對照 baseline，寫一句「採用 / 不採用 / 待 Step N 一起評」

> 參數名是現有 node 實際宣告的：`confidence_threshold`（不是 `conf`）、`input_size`、`model_path`、`tick_period`、`publish_fps`、`class_cooldown_sec`、`class_whitelist`。

### Step 1: `confidence_threshold` 0.5 → 0.35 → 0.30

```bash
ros2 run object_perception object_perception_node --ros-args \
  -p confidence_threshold:=0.35
```

預期：召回上升，誤檢可能上升。觀察 P0 必達 detect rate 是否 ≥ 80%，誤檢類別是否爆。
若 0.35 仍漏多，再試 0.30；若 0.35 誤檢爆，回 0.40。

### Step 2: `input_size` 640 → 768

```bash
ros2 run object_perception object_perception_node --ros-args \
  -p confidence_threshold:=0.35 \
  -p input_size:=768
```

預期：小物（杯子 / 手機）召回上升，FPS 下降。**必查**：obj FPS 是否仍 ≥ 8。
若 FPS < 8 且改善大，可考慮鬆 `tick_period`（例如 0.067 → 0.1）；若 FPS < 5，回 640 或等 Step 3 26s 評估。

### Step 3: 模型 26n → 26s

前置：取得 `yolo26s.onnx` 並 `cp` 到 `/home/jetson/models/yolo26s.onnx`（**不覆蓋** 26n）。首次啟動會重建 TRT engine（3–10 分鐘），耐心等。

```bash
ros2 run object_perception object_perception_node --ros-args \
  -p model_path:=/home/jetson/models/yolo26s.onnx \
  -p confidence_threshold:=0.35 \
  -p input_size:=768
```

預期：召回顯著上升（特別是小物），FPS 進一步下降。
若 FPS < 5 single-run，26s 不適合常駐預設，記為「boost-only 候選」（見 §5 三情境量測）。

### 共同前置：離線 YOLO inference 產出（Step 4/5/6 共用）

Step 4 / 5 / 6 都需要「每幀 raw detections」，但 baseline rosbag 內沒有（見 §3.1 說明）。因此寫一支 **offline_yolo_replay.py**（不入 node，純獨立腳本），對所有 baseline rosbag 跑一次：

```
輸入：rosbag 內 /camera/camera/color/image_raw（每幀 BGR）
模型：YOLO26n（or 26s，Step 3 後）.onnx ＋ ONNX Runtime（TRT EP 若可用，否則 CUDA / CPU）
輸出：per-frame raw detections JSON / parquet — {timestamp, [(class_id, score, x1, y1, x2, y2), ...]}
       每張 frame 的 raw image path（給 Step 6 顏色處理）
```

**這份 offline raw detections 是 Step 4 / 5 / 6 的唯一輸入**。三個 Step 都從這裡讀，不重複跑 YOLO。

> 為什麼這樣：rosbag 只記了「相機輸入 + node 對外的 cooldowned 事件」，沒有每幀 raw detections；離線重跑 YOLO 是唯一能還原每幀 bbox / score 的方式。離線重跑同時把 inference 與 node runtime 隔離，量出來的「voting / threshold / color 改善」純粹是後處理貢獻，不被 ROS callback 抖動干擾。

### Step 4: Class-specific threshold（離線評估，不入 node）

目標：杯子 / 手機可設 0.25，椅子 / 背包設 0.40。本步不改 node 程式碼，**先寫 yaml 草稿**：

```yaml
# /tmp/object_class_thresholds.yaml（草稿，不 commit）
class_threshold_overrides:
  cup: 0.25
  cell phone: 0.25
  book: 0.30
  chair: 0.40
  backpack: 0.35
```

**驗證方式**：讀「共同前置」產出的 raw detections，套 per-class 門檻過濾，對比 Step 1 全域門檻的 detect rate / 誤檢。
若效果顯著，列為 6/18 前要 land 的 node patch；若邊際小，不採用。

### Step 5: Temporal voting 離線 prototype

目標：N 幀內 ≥ M 幀同 class 才算 stable；stable 才發 `/event/object_detected`。

**做法**：寫一支 voting 後處理腳本，輸入是「共同前置」的 per-frame raw detections，套以下參數做離線重放：

```
voting_window_frames: 5
voting_min_votes: 3
iou_match_threshold: 0.3
```

**輸出**：對比表 — baseline 事件閃爍率（rosbag 內 `/event/object_detected` 實測） vs voting 後事件閃爍率（離線推算同一物件 30s 內 DETECTED↔LOST 次數）。
**目標**：閃爍率降到 baseline 的 ≤ 30%。
若達標：列為 6/18 前 land；若不夠，調 N/M 或升級到 DimOS 兩層 memory（研究 brief §4.4 備案）。

### Step 6: 顏色 central crop + CLAHE + LAB/KMeans 離線 prototype

目標：取代 HSV 12 色 bucket，減少背景污染與光線差異。

**做法**：腳本（不入 node）讀「共同前置」的 per-frame raw detections（取 bbox）＋ 對應 raw frame BGR，跑：
1. bbox 內縮 30%（central crop）
2. CLAHE（clipLimit=2.0, tileGridSize=(8,8)）
3. 轉 LAB 色空間，K=3 KMeans，取最大 cluster 中心
4. 對照 LAB cluster 與 12 色 anchor 距離，輸出主色 + ratio
5. ratio < 0.4 → `Unknown`

**輸出**：對比表 — 主色一致性（同一物件 30s 內輸出主色的眾數比例）baseline vs new。
**目標**：必達物件主色一致性 ≥ 80%（無視光線變化）。

---

## 5. 通過 / 失敗門檻（target + hard floor）

對應研究 brief §2 成功標準 + §8 runtime budget 共同約束。

### 5.1 辨識率（per object × distance × lighting）

| 條件 | Target | Hard floor |
|---|---|---|
| 必達物件 × 1–2m × **正常光線** | detect rate ≥ 80%，avg conf ≥ 0.35 | 任一必達物件不得 < 60% |
| 必達物件 × 1–2m × **偏暗 / 背光** | 記錄為 stress test | 不作 P0 hard gate；但不得出現大量誤檢 |
| 觀察物件 | 記錄但不約束 | — |

### 5.2 穩定度

- 事件閃爍：temporal voting 後 ≤ baseline 的 30%，或 30s 內同一物件 DETECTED↔LOST ≤ 2 次
- bbox 抖動：center std ≤ 10 px（720p 影像下）

### 5.3 顏色

- 必達物件主色一致性（30s 眾數比例）≥ 80%
- 不確定時輸出 `Unknown`，不硬猜

### 5.4 Runtime budget（情境化三組量測，研究 brief §8）

| 情境 | 啟動範圍 | Target | Hard floor |
|---|---|---|---|
| **Object only** | D435 + object_perception | obj FPS ≥ 8 | ≥ 6 |
| **Full perception** | D435 + object + face + vision + brain + speech（無 nav） | obj FPS ≥ 5 | ≥ 3 |
| **Nav mode** | nav stack + object low-rate | obj FPS 1–2（可由 `tick_period` 調至 0.5s）；**nav `/cmd_vel_nav` 不可掉** | nav 不可掉是 hard gate |

### 5.5 系統指標（全情境）

- RAM available ≥ 0.8 GB（hard floor）
- 溫度 < 75°C OK，75–80°C warn，> 80°C no-go
- ROS topic latency：`/event/object_detected` end-to-end ≤ 1.5s（從 frame 到 event）
- Camera frame drop：`/camera/camera/color/image_raw` 平均 FPS 不可低於 15
- 若同跑 brain：TTS / ASR 延遲不可較單跑增加 > 30%
- 若同跑 nav：`/cmd_vel_nav` 必須持續發布，無 gap > 200ms

### 5.6 升級採用規則

**任何模型 / 參數升級**：
- 通過 5.1 + 5.2 + 5.4 「Object only」 → 可作為**升級候選**
- 加上通過 5.4 「Full perception」 → 可作為**常駐預設候選**
- 加上通過 5.4 「Nav mode」+ 5.5 系統指標 → 可作為**6/18 demo 預設**
- 通過部分但不全通過 → 列為 **boost-only**（由 Executive / Studio 在特定 mode 觸發）

---

## 6. 回填與決策

跑完 Step 0–6 後：

1. 把 §3.3 baseline 表、各 Step Δ 表填齊
2. 對照 §5 門檻，逐 Step 寫一段「採用 / 不採用 / boost-only / 待 Step N 一起評」
3. 寫一個總結段：本窗口的物件偵測升級採用清單 + 為什麼
4. **若所有 step 後 P0 必達仍未過 §5.1 hard floor** → 觸發研究 brief §6 的 fine-tune 條件，啟動下一階段資料蒐集計畫

決策需附原始數據（rosbag 路徑 + 表格）作為證據。

---

## 7. 已知陷阱

- **TRT cache 失效**：模型 / input size 一變要重建，首次 3–10 分鐘。耐心等，不要中斷。
- **`pip install ultralytics` 禁止**：會破 Jetson torch wheel，整個 perception 廢掉。模型只能換 `.onnx`。
- **`class_whitelist` 空 list 序列化**：若要過濾類別，用 ROS2 INTEGER_ARRAY 描述子，yaml 不可寫 `: []`。
- **rosbag 大小**：8 物件 × 3 距離 × 3 光線 × 30s × 三 topic，可能 ~30 GB。先確認 Jetson 磁碟。
- **Step 5/6 是離線 prototype**：不入 node、不影響 runtime；若效果好，6/18 前再決定要不要 land。
- **背光 / 偏暗不是 P0 hard gate**：只測不卡，避免決策被極端光線拖死。

---

## 變更紀錄
- 2026-05-20 草稿建立。
- 2026-05-20 reviewer 修正三項：
  - §2 row 7 改為 `pawai status --short` + `.pawai-last-deploy`（Jetson rsync tree 沒 `.git`）
  - §3.1 補「三 topic 各自用途」並澄清 raw detections 必須**離線重跑 YOLO** 才有
  - §4 新增「共同前置：離線 YOLO inference 產出」，Step 4/5/6 從這份輸出讀，不再誤指「rosbag 內 raw detections」
