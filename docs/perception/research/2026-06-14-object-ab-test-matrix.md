# Object A/B Test Matrix — n@640 baseline confusion harness + yolo26s feasibility

> **日期**：2026-06-14　**狀態**：HARNESS_READY / DATA_PENDING_CLIPS
> **上游**：[lane4 plan](../../archive/superpowers-legacy/plans/2026-06-13-lane4-vision-benchmark-model-ab-plan.md)（W1 export / 測試矩陣）、[objdet synthesis](2026-06-11-objdet-upgrade-synthesis-result.md)（矩陣 A-E、conf 0.35、imgsz-1280-superseded）、[5-20 benchmark protocol](../../archive/superpowers-legacy/specs/2026-05-20-object-perception-benchmark-protocol.md)（門檻 §5）
> **鐵律繼承**：demo 錄影**絕不餵 LLM**（量測輸入 ≠ 理解輸入）；supervision/cv2/onnxruntime **不進 Jetson runtime**；6/18 前**不換任何 runtime 模型/參數**；數據只進決策不進部署。

---

## 0. TL;DR

- **今晚可交付的 = n@640 baseline 混淆矩陣**：harness 已寫好、import-check + `--dry-run` 乾淨、22 個純邏輯 unit test 全綠、stub-ONNX e2e 跑通（cup→cell_phone confusion 正確捕捉）。
- **n-vs-s A/B = BLOCKED**：`yolo26s_640.onnx` 不在 repo（也不該在——它是 Jetson `/home/jetson/models/` 檔），且**尚未 export + TRT 預燒**。本文 §4 給出精確 unblock 步驟，在那之前任何「26s 已測」宣稱都是 forbidden claim。
- **痛點對焦**：baseline 真正要量的不是 recall（已高），而是 **cup ↔ cell_phone ↔ bottle 混淆**——harness 的核心輸出就是這張 per-(object) confusion 表。
- **等 Roy 的東西**：今晚錄製的 cup/bottle/phone/chair × 0.7/1.0/1.5m clips（image folder 或 mp4），加上一份 `yolo26n.onnx`（WSL 取得，ORT CPU 用，**不上 Jetson**）。

---

## 1. Harness

**檔案**：`benchmarks/scripts/object_confusion_matrix.py`（離線，WSL / benchmark venv only，**永不上 Jetson runtime**）
**測試**：`benchmarks/test/test_object_confusion_matrix.py`（22 tests，純 numpy，無 cv2/ort/rclpy 依賴）

### 1.1 它量什麼（per-(object, distance) cell）

| 指標 | 說明 |
|------|------|
| `frames` | 該 cell 處理的幀數 |
| `detection_count` | GT 物件被偵測到的幀數 |
| `recall` | `detection_count / frames`（同 protocol §5.1 detect rate 口徑） |
| `conf_min` / `conf_avg` / `conf_max` | GT 物件 confidence 統計（每幀取該物件最高 conf） |
| **class confusion matrix** | GT 物件為 X 時，模型實際吐出哪些 COCO label（cup 被誤標 phone/bottle 各幾幀）。frame-level：每幀每個 distinct label 計一次；空偵測進 `__none__` 桶 |
| `fps` | 離線 ORT CPU 吞吐（**不是 Jetson 數字**，僅供 harness 自身效能參考） |
| `verdict` | PASS≥0.80 / DEGRADED≥0.60 / FAIL（recall gate，§3 門檻） |

### 1.2 解碼口徑（與 runtime 一致）

harness 複製 `object_perception_node` 的後處理：YOLO26 `(1,300,6)` = `x1,y1,x2,y2,conf,class_id` → conf gate（預設 0.35）→ class whitelist → COCO-id 合法性 → 退化 bbox 丟棄 → letterbox 反算回原圖座標。COCO 80 表是**鏡像**（mirror，非 import）自 `object_perception/object_perception/coco_classes.py`，以保持 harness 不依賴任何 ROS package。

### 1.3 輸入路徑慣例

每個 leaf 是一個 image folder 或單一 video 檔；GT 物件 + 距離編在路徑裡：

```
clips/cup/0.7m/*.jpg          # 巢狀：<object>/<distance>m/（image folder）
clips/cup/1.0m.mp4            # 巢狀：<object>/<distance>m.<ext>（單一 clip）
clips/bottle__1.5m/*.png      # 扁平：<object>__<distance>m
```

物件名正規化為底線小寫（`cell phone` → `cell_phone`，對齊 COCO 表）。

### 1.4 用法

```bash
# 0) 列出會處理什麼（不載入模型，今晚先驗素材結構正確）
python3 benchmarks/scripts/object_confusion_matrix.py clips/ --dry-run

# 1) 跑 n@640 baseline（需 WSL 取得的 yolo26n.onnx，ORT CPU；conf 0.35 是現役基線）
python3 benchmarks/scripts/object_confusion_matrix.py clips/ \
  --model /path/to/yolo26n.onnx --conf 0.35 --imgsz 640 \
  --out benchmarks/results/raw/object_ab/2026-06-14-n640-confusion.json

# 2) 只看容器混淆組（cup/bottle/phone/bowl/wine_glass 等 COCO id）
python3 benchmarks/scripts/object_confusion_matrix.py clips/ \
  --model /path/to/yolo26n.onnx --whitelist 39,40,41,45,67
```

### 1.5 依賴政策（gate gracefully）

- **永遠需要**：stdlib + numpy（dev venv 已有）。
- **延遲匯入（lazy import）**：`cv2`（opencv-headless）、`onnxruntime`——只有真正解幀/推理時才載入；缺則 harness 印出 install 行、回非零，**不污染** repo dev venv。
- benchmark venv 安裝行（**這些絕不進 Jetson runtime**）：
  ```bash
  uv venv .tmp/obj_bench_venv
  .tmp/obj_bench_venv/bin/uv pip install onnxruntime opencv-python-headless numpy
  ```
- 本 repo dev venv 現況：cv2 4.13 + numpy 2.2.6 + onnxruntime 1.23.2 已在位 → harness e2e 可在開發機直接跑（已驗）。

---

## 2. 測試矩陣（objects × distances）

> 主軸：cup/bottle/phone/chair × 0.7/1.0/1.5m。每 cell 一段 clip（建議 ≥30s 靜置 + 末段輕轉，對齊 protocol §3.1）。

| object | 0.7m | 1.0m | 1.5m |
|--------|:----:|:----:|:----:|
| **cup** | ☐ | ☐ | ☐ |
| **bottle** | ☐ | ☐ | ☐ |
| **cell_phone** | ☐ | ☐ | ☐ |
| **chair** | ☐ | ☐ | ☐ |

每 cell 由 harness 自動填：`frames / detection_count / recall / conf_min / conf_avg / conf_max / confusions / verdict`。
**RAM / temp 欄位由 Roy 從 Jetson `tegrastats` 補**（harness 是 WSL 離線工具，量不到 Jetson 資源——見 §3 表的 Jetson-only 欄）。

### 2.1 容器混淆專欄（痛點）

baseline 的重點輸出。預期最常見混淆對：

| GT 物件 | 高機率被誤標為 | COCO id |
|---------|---------------|:-------:|
| cup (41) | cell_phone(67) / bottle(39) / wine_glass(40) / bowl(45) | — |
| bottle (39) | cup(41) / wine_glass(40) / vase(75) | — |
| cell_phone (67) | remote(65) / book(73) / cup(41) | — |
| chair (56) | couch(57) / bench(13) | — |

harness 的 `confusions(object)` 直接吐這張表的實測幀數。

---

## 3. 門檻（從 lane4 / synthesis / 5-20 protocol 繼承）

| 指標 | 門檻 | 出處 | 由誰量 |
|------|------|------|--------|
| **cup@1.5m recall** | ≥ 0.80（PASS）；≥0.60 hard floor | synthesis T2 / protocol §5.1 | **harness**（本工具，需 clips） |
| recall PASS/DEGRADED/FAIL | ≥0.80 / ≥0.60 / 其餘 | object_matrix gate | **harness** |
| avg_confidence | ≥ 0.35（必達物件正常光） | protocol §5.1 | **harness** |
| **confusion < n@640 baseline** | 候選配置的容器混淆幀數須 **低於** 本 baseline | synthesis W2 容器混淆 <30% 精神 | **harness**（baseline 先量；候選對比待 26s unblock） |
| **偵測迴圈 ≥ 3Hz** | full-stack ≥3Hz（object only ≥6/≥8） | protocol §5.4 | **Jetson only**（harness FPS≠Jetson FPS） |
| **RAM 餘 ≥ 0.8GB** | hard floor | protocol §5.5 / synthesis §4c | **Jetson only**（`tegrastats`） |
| **溫度 < 75°C** | <75 OK / 75-80 warn / >80 no-go | protocol §5.5 | **Jetson only**（`tegrastats` / thermal_zone） |

> **口徑澄清**：harness 的 `fps` 是 WSL ORT CPU 吞吐，**不可**拿來判 ≥3Hz 門檻——3Hz/RAM/temp 三項一律以 Jetson `tegrastats` 實測為準（上機矩陣日 T0-T7）。harness 只負責 recall / conf / confusion 三項可離線量的指標。

---

## 4. yolo26s feasibility determination

### 4.1 `yolo26s_640.onnx` 在 repo 嗎？

**不在，且不該在。** 全 repo `find -name "yolo26*.onnx"` 為空；`.tmp/yolo_export/out/`、`/home/jetson/models/` 本機皆無。它本質是 Jetson `/home/jetson/models/` 的執行期檔案（大模型檔不進 git——本 lane forbidden）。現役 runtime 配置（`object_perception/config/object_perception.yaml`）：`model_path: /home/jetson/models/yolo26n.onnx`、`input_size: 640`（yaml 註明「必須 640，改 960 直接 inference fail」=現 ONNX 為 fixed-shape 640）。

### 4.2 Verdict：**A/B BLOCKED until `yolo26s_640.onnx` exported + TRT-burned**

n-vs-s A/B **無法在今晚或任何尚未完成 export+預燒的時點宣稱已測**。今晚交付物 = **n@640 baseline harness 跑出的混淆矩陣**（只要拿到 clips + `yolo26n.onnx`）。26s 對比是後續、有前置的工作。**不得宣稱「26s 已測 / 26s 較好 / 混淆已改善」直到 §4.3 全部完成且實測數據在手。**

### 4.3 Unblock 步驟（精確，無含糊）

**Step A — WSL export（離線，獨立 venv，不碰 Jetson）**
```bash
uv venv .tmp/yolo_export_venv
.tmp/yolo_export_venv/bin/uv pip install ultralytics onnxruntime    # 禁令只限 Jetson runtime
# fixed-shape e2e ONNX，輸出 (1,300,6)（NMS-free，與現役 n 同型）
.tmp/yolo_export_venv/bin/python .tmp/yolo_export/export_models.py \
    --models yolo26s:640 --e2e --fixed-shape
# sanity：shape 必為 (1,300,6)、可被 object_perception adapter 接受
python3 benchmarks/scripts/onnx_sanity_check.py .tmp/yolo_export/out/yolo26s_640.onnx --imgsz 640 --json
python3 scripts/object_model_contract.py .tmp/yolo_export/out/yolo26s_640.onnx --json   # compatible 必須 true
```

**Step B — additive 部署到 Jetson（純檔案，不 `--delete`，不覆蓋 26n）**
```bash
rsync -av .tmp/yolo_export/out/yolo26s_640.onnx jetson-nano:/home/jetson/models/
```

**Step C — TRT 預燒（Jetson 上，前一晚，嚴禁同跑 demo stack）**
- 每顆 engine 首次 build **3-15 分鐘**；workspace 峰值 **~1GB** → **不可與 demo stack 並跑**（OOM 風險）。
- TRT cache 按 model stem 分目錄（`object_perception_node._init_onnx`：`trt_cache_dir/<stem>/`）→ 燒 26s 不會覆蓋現役 26n engine。
```bash
# Jetson 上，full demo stack 全關
OBJECT_MODEL=/home/jetson/models/yolo26s_640.onnx OBJECT_INPUT_SIZE=640 \
  ros2 launch object_perception object_perception.launch.py
# 等 cache 落 /home/jetson/trt_cache/yolo26s_640/ + 近距 cup sanity 通過才算燒好
# （F16 AGX mAP 異常前科 → 每顆 engine 必過已知場景 sanity）
```

**Step D — A/B 對比**
- 離線層：對同一批 clips 跑 `object_confusion_matrix.py --model .../yolo26s_640.onnx`，與 n@640 baseline 比 recall + confusion（harness 直接支援，換 `--model` 即可）。
- 上機層：synthesis §4b T2「主力刀」配置（`OBJECT_MODEL=yolo26s_640.onnx`），量 cup recall@1.0/1.5/2.0m + Hz + RAM + 近距 7 類 sanity。conf 非 runtime param，A0→A1 換 conf **必 kill 重啟 node**。

### 4.4 還原紀律（若上機日排在 6/18 前）

當日結束 `OBJECT_MODEL` env 一行切回現役 26n → 跑一輪 `pawai smoke full` 確認 demo 行為與已錄影片一致；TRT 現役 engine 因分目錄不受影響。

---

## 5. Done / Pending split

| 項目 | 狀態 |
|------|------|
| 混淆矩陣 harness（`object_confusion_matrix.py`） | **DONE**（import-check + dry-run 乾淨、22 tests 綠、stub e2e 跑通） |
| 純邏輯 unit test | **DONE** |
| flake8 max-line=100 | **DONE**（clean） |
| 測試矩陣 + 門檻文件（本檔） | **DONE** |
| yolo26s feasibility verdict | **DONE = BLOCKED**（unblock 步驟成文 §4.3） |
| n@640 baseline 實測混淆數據 | **PENDING** — 需 Roy 今晚錄的 clips + 一份 `yolo26n.onnx`（WSL，ORT CPU） |
| 26s export + TRT 預燒 + A/B | **PENDING / BLOCKED** — §4.3 Step A-D，需 Roy + Jetson |
| 上機 3Hz / RAM / temp 欄位 | **PENDING** — Jetson `tegrastats`（harness 量不到） |
```
