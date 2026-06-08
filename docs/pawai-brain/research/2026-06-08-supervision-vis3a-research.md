# Supervision × VIS-3A Object-Eval Harness — 決策 + 設計

> 對象：Roy ｜ 主筆：視覺工具 lane ｜ 日期：2026-06-08
> 依據：3 份研究 JSON + 實機 code 驗證（`object_perception_node.py`、`benchmarks/` 既有框架）

---

## 1. 一句話結論

**Supervision 只當「離線/半離線分析庫」，不進 Jetson live ROS node、不進 `object_perception/setup.py`**；VIS-3A 正式 harness 採**「Layer A 輕量 rclpy live capture（零 Supervision、抄 `capture_baseline_round.py`）+ Layer B 離線 Supervision 聚合」**雙層，放 `benchmarks/object_eval/`；**6/18 前只做到 Layer A 收得到標準 CSV + 簡易 pass/degraded/fail 聚合腳本（夠餵 scoreboard gate），Supervision 的 annotators / metrics 全列 post-6/18**。今晚先用既有 `capture_baseline_round.py percep`（已隔離 topic）或臨時 `obj_matrix_cap.py` 收數據，正式 VIS-3A 明天再寫。

---

## 2. Supervision 能力對照表

| 功能 | 對 PawAI 用途 | 用不用 | 備註 |
|------|--------------|:------:|------|
| **`sv.Detections` 統一結構** | 把 `/event/object_detected` 的 `objects[]` 或 YOLO26n raw `(300,6)` 標準化成 box+conf+class+custom data | **用（Layer B）** | **能不靠 ultralytics 直接餵我們的輸出 ✓** — `sv.Detections(xyxy=, confidence=, class_id=, data={...})` 是純建構子，`from_ultralytics()` 只是其中一個 adapter，不是必經路徑。我們的 raw 是 `(300,6)=[x1,y1,x2,y2,conf,class_id]`（`object_perception_node.py:370`），`xyxy=raw[valid,:4]`、`confidence=raw[valid,4]`、`class_id=raw[valid,5]` 直接塞。**絕不 `pip install ultralytics`**（破 Jetson torch wheel，CLAUDE.md 硬規則）。 |
| **`CSVSink` / `JSONSink` + custom fields** | 結構化存 detections，`append()` 第二參數 dict 把 `distance/lux/light/angle/trial` 追加成 CSV 欄 | **可用，但非必須（Layer B）** | append 模式無截斷風險。**風險**：custom field 是陣列（多物件）時會被序列化成字串、讀回要反序列化 → 建議 **scalar custom field（單幀 cell 維度）用 CSVSink，逐物件明細用 JSONSink 或我們自己的 csv.DictWriter**。Layer A 的逐筆寫**不用 Supervision**（避免 Jetson 依賴），直接 `csv.DictWriter`。 |
| **`DetectionsSmoother`** | bbox/事件時序平滑 | **不用** | 需 upstream `tracker_id`（ByteTrack）才有意義；我們走 protocol §4.4 的 **temporal voting（N-of-M）離線版**，成本低、可逐幀審視。Smoother 留備案，若 voting 不夠再升。**絕不進 live node**（callback timing 複雜度爆增）。 |
| **annotators（Box/Label）** | 產 annotated debug image 給離線複審失敗 cell | **不用（沿用現有）** | live debug image 已有 PIL+cv2 中文+conf 混合繪製（`object_perception_node.py:449-499`），夠用、且支援中文（Supervision 的 LabelAnnotator 不畫 CJK）。離線複審若要批量標 100s 張才考慮 `sv.BoxAnnotator`，且**只標失敗 cell**（批量 annotate 很慢）。 |
| **metrics（mAP / F1 / confusion matrix）** | 模型升級 A/B 量化 | **不用（6/18 前）** | 全部要 ground truth COCO 標註，成本高。VIS-3A 的判定只需 **detect rate % + avg/min confidence + flicker count**，自寫 Python 迴圈即可。mAP 留到 post-6/18 真要 fine-tune 才建 GT。 |

**安裝結論**：Layer A（Jetson）= **零 Supervision**。Layer B（WSL/PC 或 Jetson 離線）= `uv pip install supervision`，衝突時 `uv pip install --no-deps supervision`（防拉 numpy 2.2.6 破 wheel）。

---

## 3. VIS-3A Harness 設計

### 3.1 架構選擇：live 訂閱 vs rosbag 離線 → **推薦 live capture（Layer A）+ 離線聚合（Layer B）**

| 方案 | 優 | 劣 | 判定 |
|------|----|----|------|
| **(a) live rclpy 訂閱 `/event/object_detected`** | 現場快速反覆、不等錄包回傳、Jetson 8GB 不被框架擠、抄現成 `capture_baseline_round.py` | 無逐幀 GT、distance 手填 | **採用為主線** |
| (b) rosbag 錄 → WSL 重播 + YOLO26n 重跑 | 可逐幀重分析、可換閾值重跑 | 8 obj×3 dist×3 light×30s×3 topic ≈ 30GB、要在 WSL 重建 ONNX preprocessing（一致性風險）、回傳慢 | **不做（6/18 前）**；列 post-demo 升級路線 |

**理由**：VIS-3A 是「單元層工具化」（committed plan：VIS-3 = code 層，VIS-8 = 場測硬體層），現場 5 trial/cell 即時判 pass/degraded/fail 餵 Brain gate 最重要。rosbag 重播是「換模型 A/B」才需要的能力 → post-6/18。

### 3.2 CSV schema（每行一筆觀測，Layer A 直接 `csv.DictWriter`）

```
object, distance_m, light_condition, angle_deg, trial,
detected, class_name, confidence,
bbox_x, bbox_y, bbox_w, bbox_h,
is_correct, misclassified_as,
debug_img_path, lux, timestamp_unix
```

- `object/distance_m/light_condition/angle_deg` = CLI arg 直填（複合 cell key）
- `is_correct` = `class_name == object`；`misclassified_as` = detected 但類別錯時填，否則 null
- idle/未偵測列：`detected=False`、`class_name/confidence` 空（聚合算誤觸 / FP 用）
- `lux` 可選（無光度計填 null）；`distance_m` 手填，誤差 ±0.2m（風險已知）

### 3.3 Core code sketch

**Layer A — `obj_eval_live_capture.py`（Jetson，零 Supervision，抄 `capture_baseline_round.py:114-157` 的 lazy-import rclpy 模式）**

```python
# rclpy 只在 run() 內 lazy import，module 載入維持 CI-safe
def run_capture(args):
    import rclpy
    from rclpy.node import Node
    from std_msgs.msg import String
    rows, lock = [], threading.Lock()
    rclpy.init()
    node = Node("obj_eval_capture")

    def cb_object(msg):
        ev = json.loads(msg.data)
        stamp = ev.get("stamp")
        objs = ev.get("objects") or []
        with lock:
            if not objs:                                   # 未偵測也記一筆（算誤觸/FP）
                rows.append(_row(args, detected=False, ts=stamp))
            for o in objs:                                 # schema 同 object_perception_node.py:424-432
                x1, y1, x2, y2 = o["bbox"]
                rows.append(_row(
                    args, detected=True, ts=stamp,
                    class_name=o["class_name"], confidence=o["confidence"],
                    bbox_x=x1, bbox_y=y1, bbox_w=x2 - x1, bbox_h=y2 - y1,
                    is_correct=(o["class_name"] == args.object),
                    misclassified_as=(None if o["class_name"] == args.object else o["class_name"]),
                ))

    node.create_subscription(String, args.object_topic, cb_object, 10)
    t = threading.Thread(target=rclpy.spin, args=(node,), daemon=True); t.start()
    time.sleep(args.duration)                              # 固定窗，同 capture_baseline_round._spin_collect
    node.destroy_node(); rclpy.shutdown()
    _write_csv(args.out, rows)
```

**Layer B — `core/supervision_helpers.py`（離線，event/raw → `sv.Detections`）**

```python
import numpy as np, supervision as sv
COCO_REV = {v: k for k, v in COCO_CLASSES.items()}

def event_to_detections(ev: dict) -> sv.Detections:
    objs = ev.get("objects", [])
    if not objs:
        return sv.Detections.empty()
    xyxy = np.array([o["bbox"] for o in objs], dtype=np.float32)   # 我們已是 [x1,y1,x2,y2]
    conf = np.array([o["confidence"] for o in objs], dtype=np.float32)
    cid  = np.array([COCO_REV.get(o["class_name"], -1) for o in objs], dtype=np.int32)
    return sv.Detections(xyxy=xyxy, confidence=conf, class_id=cid,
                         data={"class_name": [o["class_name"] for o in objs]})

def raw_yolo_to_detections(raw, conf_thr=0.25, **meta) -> sv.Detections:
    valid = raw[:, 4] > conf_thr                                   # raw=(300,6) object_perception_node.py:370
    return sv.Detections(xyxy=raw[valid, :4].astype(np.float32),
                         confidence=raw[valid, 4].astype(np.float32),
                         class_id=raw[valid, 5].astype(np.int32),
                         data=meta)
```

### 3.4 Cell CLI

```bash
python3 benchmarks/object_eval/scripts/obj_eval_live_capture.py \
  --object cup --distance 1.0 --light normal --angle 0 \
  --duration 60 \
  --object-topic /event/object_detected \
  --out benchmarks/object_eval/results/cup_1m_normal_0.csv
```

### 3.5 聚合判定腳本 — `obj_eval_offline_aggregate.py`

```python
import pandas as pd
def aggregate(csv_paths):
    df = pd.concat([pd.read_csv(p) for p in csv_paths])
    out = {}
    for key, g in df.groupby(["object", "distance_m", "light_condition", "angle_deg"]):
        det = int(g["detected"].sum())
        status = "PASS" if det >= 4 else ("DEGRADED" if det == 3 else "FAIL")
        out[key] = {
            "detected_count": det,
            "correct_count": int(g["is_correct"].sum()),
            "confidence_mean": float(g["confidence"].mean()),
            "confidence_min": float(g["confidence"].min()),
            "pass_status": status,                    # 對齊 scoreboard pass/degraded/fail gate
            "misclass": g.loc[g["misclassified_as"].notna(), "misclassified_as"].value_counts().to_dict(),
        }
    return out
```

判定門檻（對齊 capability matrix + scoreboard gate）：每 cell 5 trial 中 **detected ≥4 = PASS（主線）/ =3 = DEGRADED（備援）/ <3 = FAIL（不上台）**；`confidence < 0.45` 的小物不主秀。

### 3.6 放哪 → **`benchmarks/object_eval/`**（與既有 `adapters/configs/scripts/results/core/test` 命名同調）

```
benchmarks/object_eval/
├── configs/cell_definition.yaml          # object×distance×light×angle 矩陣
├── scripts/obj_eval_live_capture.py       # Layer A（Jetson，零 supervision）
├── scripts/obj_eval_offline_aggregate.py  # Layer B 聚合（純 pandas）
├── scripts/obj_eval_visualize.py          # post-6/18：supervision annotators
├── core/supervision_helpers.py            # event/raw → sv.Detections（離線）
├── test/test_live_capture.py              # mock String publisher → CI-safe
├── test/test_offline_aggregate.py         # fixture CSV → CI-safe
└── results/                               # .gitignore（images/ *.csv *.json）
```

**不放 `tools/`**：benchmarks/ 已有 reporter/monitor/observer 同類框架（`benchmarks/core/perception_baseline_observer.py`、`benchmarks/scripts/capture_baseline_round.py`），復用 `normalize_object_event`、JSONL reporter 慣例最省。

---

## 4. Jetson 安裝安全性 + 部署位置決策

| 環境 | 跑什麼 | Supervision | 安裝指令 |
|------|--------|:-----------:|----------|
| **Jetson live（主線，不變）** | `object_perception_node.py` + Layer A capture | **零** | 不動 `setup.py`（保持 `numpy/opencv-python`）；Layer A 只用 `rclpy`+`csv` 標準庫 |
| **WSL / PC 離線（Layer B 主場）** | 聚合 + annotators + metrics | 有 | `uv pip install supervision`，衝突時 `uv pip install --no-deps supervision` + 自備 `opencv-python numpy==1.26.4 pyyaml` |
| **Jetson 離線（非必要，只在沒 PC 時）** | Layer B 單機跑 | 有，**`--no-deps`** | `uv pip install --no-deps supervision`（**絕不裸 `pip install supervision`**） |

**會不會破 torch wheel**：Supervision 本體純 Python、無 torch 綁定，**風險在 transitive numpy** — 裸裝會把 numpy 拉到 2.2.6，ONNX/OpenCV ABI 崩。**安全裝法三條鐵律**：

1. Jetson live node **永不引入** Supervision（決策硬底線，寫進 `object_perception/CLAUDE.md` 防混淆）。
2. 真要在 Jetson import，**只用 `uv pip install --no-deps supervision`**（CLAUDE.md 既有 rtmlib `--no-deps` 同款保護）。
3. 落地前先煙測：開發機 `python3 -c "import supervision as sv; sv.Detections(xyxy=np.zeros((1,4),dtype='f4'), confidence=np.array([.9],'f4'), class_id=np.array([0]))"` 過了才搬。

---

## 5. PINTO_model_zoo — 候選 + 為何 6/18 前不換

**6/18 前主線維持 YOLO26n，不啟任何 PINTO spike**（committed plan Part 0：VIS-1→VIS-2→VIS-3→BRAIN-1 只改 `class_whitelist` 家用 7 類 + runtime callback + dedup 60s；research-brief §8：物體偵測定位 grounding 非 safety，允許降頻，模型升級必過三組 FPS gate）。原因：(a) PINTO 候選 ONNX 取得 / TRT EP 支援 / Nano 8GB FPS 全未實測；(b) 換模型必重建 TRT engine cache（3-10 分鐘，且 input 變大會重建）；(c) label set / post-process 轉換成本不可預期（風險已列）。

**候選（post-6/18，依排序）：**

| # | 候選 | 轉換成本 | 適配點 | go/no-go |
|---|------|----------|--------|----------|
| 1 | **YOLO26s / YOLOv8s**（VIS-6） | 低（同家族 ONNX→TRT FP16，cache 重建） | 小物件召回↑，與 26n 同 post-process | FPS 降幅 ≤20%（full perception ≥5 fps）+ mem 增幅 ≤500MB |
| 2 | **PINTO #464 YOLOv9-Wholebody28**（VIS-9 bonus） | 高（3-5d，object bbox + body keypoint 雙頭 post-proc、keypoint 轉 COCO） | 一模型同時餵物體 + fallen 判定 | FPS≥5 + 共存 ≤7.5GB + 確認 license（MIT 才碰，AGPL 直接棄） |
| 3 | **PINTO #481 WHC（揮手分類）** | 中（單純 classification 轉 ONNX） | gesture WaveDetector 補強，edge 友善 | label set 驗證（25-class vs 21-point）+ 效果達標當日內決定 |

**VIS-9 bonus 排序**（committed plan 之外，僅在物體效果驗收失敗時啟動）：
**VIS-6（YOLO26s A/B）最高 → VIS-11（80 類中文 label 美化）中、移 W4 buffer → VIS-10（object depth/bearing 統計）低，blocked on Object schema v2 spike → PINTO 換模型（#464/#481）最低，"僅在效果驗收失敗才動"。**

---

## 6. 執行切分

| 何時 | 做什麼 |
|------|--------|
| **今晚** | 用**既有工具先收數據**，不寫新 code：`benchmarks/scripts/capture_baseline_round.py percep --capability object.cup --object-topic /event/object_detected --gesture-topic /__no_gesture__ ...`（gesture topic 隔離，避免污染，CLAUDE.md 6/4 已記此坑）；或 Roy 既有 `/home/jetson/obj_matrix_cap.py` 收 conf 分布。先把 cup @1/1.5/2m 補上多距離數據（capability matrix 下次 retest 項）。 |
| **明天** | 寫 VIS-3A 正式版 **Layer A `obj_eval_live_capture.py` + Layer B `obj_eval_offline_aggregate.py`（純 pandas）+ 2 個 CI-safe unit test**（mock String publisher / fixture CSV）。**先不碰 Supervision**——Layer A 零依賴、Layer B 聚合用 pandas 就夠出 pass/degraded/fail 給 scoreboard gate。跑通一輪 cup 矩陣替換掉臨時腳本。 |
| **6/18 後** | (a) `core/supervision_helpers.py` + `obj_eval_visualize.py`（Supervision annotators 標失敗 cell）；(b) rosbag 重播能力（換模型 A/B）；(c) 視效果決定是否啟 VIS-6（YOLO26s）或 PINTO spike；(d) 需要 mAP 時才建 GT 標註。 |

**理由**：今晚不被新 code 卡住（既有工具能收數），明天的正式版刻意**不引入 Supervision**——VIS-3A 的 6/18 任務只是「標準 CSV + pass/degraded/fail 餵 gate」，pandas + csv 就達標，把 Supervision/annotators/metrics 全推到 post-demo，符合「不擴張 scope、Jetson live 不擴依賴」原則。

---

**關鍵引用（file:line / doc URL）：**
- YOLO26n raw `(300,6)` 格式 + raw→detections 構造點：`/home/roy422/newLife/elder_and_dog/object_perception/object_perception/object_perception_node.py:369-395`
- `/event/object_detected` JSON schema（`objects[]={class_name, confidence, bbox[x1,y1,x2,y2], color, color_confidence}`）：同檔 `:415-444`
- 現有 PIL+cv2 中文 debug overlay（沿用，不換 sv.annotators）：同檔 `:449-499`
- live capture 抄的 lazy-import rclpy 固定窗模式：`/home/roy422/newLife/elder_and_dog/benchmarks/scripts/capture_baseline_round.py:114-157`
- object event 正規化（聚合可復用）：`/home/roy422/newLife/elder_and_dog/benchmarks/core/perception_baseline_observer.py:47-74`
- 既有 reporter / scoreboard gate 慣例：`/home/roy422/newLife/elder_and_dog/benchmarks/core/reporter.py`、`benchmarks/core/scoreboard.py`
- 當前依賴（無 supervision，維持）：`/home/roy422/newLife/elder_and_dog/object_perception/setup.py`（`install_requires=["setuptools","numpy","opencv-python"]`）
- Jetson 硬規則（禁 ultralytics、TRT 參數、`--no-deps`）：`/home/roy422/newLife/elder_and_dog/CLAUDE.md`（物體 pipeline 段）+ `docs/pawai-brain/perception/object/CLAUDE.md`
- Supervision Detections 構造 / CSVSink：https://supervision.roboflow.com/latest/detection/core/ ｜ https://supervision.roboflow.com/latest/how_to/save_detections/
- Supervision Smoother（需 tracker_id）：https://supervision.roboflow.com/latest/detection/tools/smoother/
- 6/18 committed plan（VIS-1/2/3 + bonus VIS-6/9/11 不碰）：`/home/roy422/newLife/elder_and_dog/docs/superpowers/plans/2026-06-08-pawai-6-18-committed-plan.md`
- PINTO 不進 6/18 理由 + 三組 FPS gate：`/home/roy422/newLife/elder_and_dog/docs/superpowers/specs/2026-05-20-object-perception-research-brief.md` §8