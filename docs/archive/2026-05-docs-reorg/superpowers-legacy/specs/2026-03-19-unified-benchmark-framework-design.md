# 統一模型選型 Benchmark Framework 設計規格

> 日期：2026-03-19
> 狀態：Approved
> 範圍：face / pose / gesture / stt（第一批），tts / object_search / navigation（未來擴充）

---

## 1. 設計目標

建立一套可重複使用的模型選型實驗制度，讓所有感知功能（人臉、姿勢、手勢、語音、未來的尋物/導航）都走同一套標準化流程：

- **先研究，再 shortlist，再 benchmark，再定案**
- 統一評估指標，統一記錄格式，統一決策標準
- 結果可累積、可比較、可回溯
- 不只解決「這次用哪個模型」，而是形成長期可運作的選型知識庫

### 核心原則

- Benchmark 框架**只負責測試、記錄、報表**
- 社群調查和選型決策是制度流程的一部分，但不寫進程式框架
- `headless mode` 為預設（純性能，不依賴 ROS2/Foxglove）
- `ros_debug mode` 給少數候選和爭議模型做可視化驗證
- 所有結果以觀測事實為主，決策由人做

---

## 2. 四階段制度流程

```
Stage 1: Research Brief              → docs/research/{task}.md
Stage 2: Candidate Shortlist         → benchmarks/configs/{task}_candidates.yaml
Stage 3: Benchmark Execution         → benchmarks/results/raw/{task}_{date}.jsonl
Stage 4: Decision + Archive          → 回寫 docs/research/{task}.md 決策段
```

### Stage 1: Research Brief

每個功能模組一份，放在 `docs/research/{task}.md`。內容固定：

1. **目標效果**：一句話描述 + 4/13 Demo 量化目標
2. **候選模型表**（見 §2.1 模板）
3. **排除清單**（見 §2.2 模板）
4. **社群調查摘要**：每個候選的部署路徑、已知坑、安裝方式、引用來源
5. **Jetson 資源約束**：RAM/GPU 預算上限、與其他模組共存的預留空間
6. **決策段**（Stage 4 回填）

#### §2.1 候選模型表

| # | 模型 | 框架 | 輸出 | Installability | Runtime viability | GPU 路徑 | 社群性能參考 | 納入原因 | 預期淘汰條件 |
|---|------|------|------|:-:|:-:|:-:|---|---|---|

- **Installability**：`verified` / `likely` / `unknown` / `failed`
- **Runtime viability**：`verified` / `likely` / `unknown` / `failed`
- **GPU 路徑**：`cuda` / `tensorrt` / `cpu_only` / `unknown`
- **社群性能參考**：不限 FPS，可以是 RTF、latency、warmup time 等

#### §2.2 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|

- **證據等級**：`community_only`（看別人失敗）/ `repo_issue`（Issue/論壇有記錄）/ `local_failed`（我們自己測過失敗）

#### §2.3 決策表（Stage 4 回填）

| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|

- **Decision Code**：`JETSON_LOCAL` / `CLOUD` / `HYBRID` / `REJECTED`
- **Placement**：`jetson` / `cloud` / `hybrid` / `rejected`

### Stage 2: Candidate Shortlist

從 Research Brief 收斂出要實測的模型，寫入 `benchmarks/configs/{task}_candidates.yaml`。每個候選必須附 entry criteria。詳見 §4 YAML 格式。

### Stage 3: Benchmark Execution

分兩類，必須依序：

1. **Feasibility Benchmark**（先跑）：能裝、能跑、穩不穩、資源吃多少
2. **Quality Benchmark**（後跑，限 feasibility pass 的模型）：效果、誤判、task-specific 精度

分 4 個 Level：

| Level | 目的 | concurrent_models | 持續時間 | 何時跑 |
|:-----:|------|-------------------|---------|--------|
| 1 | 單模型基線 | `[]` | N 次推理（預設 200） | 所有候選 |
| 2 | 兩兩組合 | 1 個伴跑 | N 次推理 | feasibility pass 的 |
| 3 | 全模型同時 | 全部常駐模型 | N 次推理 | 前 1-2 名 |
| 4 | 壓力測試 | 同 Level 3 | 30 分鐘 | 最終候選 |

### Stage 4: Decision + Archive

- 回寫 `docs/research/{task}.md` 的決策表
- Decision Code 由人決定，不由程式自動填
- benchmark 結果的 `decision_hint` 僅為程式推測，供參考

---

## 3. Benchmark Framework 程式架構

```
benchmarks/
├── core/
│   ├── runner.py          # BenchmarkRunner：編排 warmup → measure → report
│   ├── monitor.py         # JetsonMonitor：jtop 背景 thread 收集硬體指標
│   ├── reporter.py        # 輸出 JSON Lines + summary CSV/Markdown
│   └── criteria.py        # Gate 判定 + decision_hint 建議
│
├── adapters/
│   ├── base.py            # BenchAdapter ABC
│   └── {task}_{model}.py  # 每個候選模型一個 adapter
│
├── configs/
│   ├── {task}_candidates.yaml
│   └── coexist_profiles.yaml  # Level 2-4 共存測試配置
│
├── results/
│   ├── raw/               # .jsonl（保留規則見 §3.6）
│   ├── archive/           # 長期歸檔（per task per date）
│   └── summary/           # .md + .csv（進 git）
│
├── test_inputs/
│   ├── images/            # 640x480 D435 真實截圖（5-10 張）
│   ├── audio/             # 16kHz mono WAV 測試語音（5-10 段）
│   ├── annotations/       # ground truth（COCO JSON 等，quality 評估用）
│   └── README.md          # 素材來源與用途說明
│
├── scripts/
│   ├── bench_single.sh    # 跑單一模型
│   ├── bench_task.sh      # 跑某功能全部候選（逐一 + cooldown）
│   ├── bench_coexist.sh   # Level 2-4 多模型共存
│   └── prepare_env.sh     # nvpmodel + jetson_clocks（--drop-cache 可選 flag）
│
└── analysis/
    └── compare.py         # 讀 results/ → 比較表 + Pareto 圖
```

### §3.1 BenchAdapter ABC

```python
from abc import ABC, abstractmethod
from typing import Any

class BenchAdapter(ABC):
    """每個模型實作這四個方法，runner 不需要知道 task 細節"""

    @abstractmethod
    def load(self, config: dict) -> None:
        """載入模型。config 來自 candidates.yaml 的 params 段"""

    @abstractmethod
    def prepare_input(self, input_ref: str) -> Any:
        """把檔案路徑或 sample id 轉成模型可吃的 input。
        image task: str → np.ndarray (BGR)
        audio task: str → np.ndarray (16kHz mono float32)
        """

    @abstractmethod
    def infer(self, input_data: Any) -> dict:
        """單次推理。回傳 prediction + task-specific metadata。
        例如 face: {"boxes": [...], "scores": [...], "n_faces": 3}
        例如 stt: {"text": "你好", "language": "zh"}
        """

    def evaluate(self, predictions: list[dict], ground_truth: Any) -> dict:
        """可選。比對 predictions 與 ground truth，回傳 task-specific metrics。
        例如 face: {"mAP_0.5": 0.82, "recall": 0.77}
        例如 stt: {"wer": 0.15, "cer": 0.08}
        預設回傳空 dict（第一版只做 feasibility 時不需實作）。
        """
        return {}

    @abstractmethod
    def cleanup(self) -> None:
        """釋放模型資源（GPU memory 等）"""
```

**與現有 InferenceAdapter 的關係**：BenchAdapter 是 benchmark-only 的介面，與 `vision_perception/inference_adapter.py` 的 `InferenceAdapter` 完全獨立。benchmark adapter 可以在內部持有 production adapter instance（例如 `pose_rtmpose.py` 內部 import `RTMPoseInference`），但 BenchAdapter 的 `infer()` 回傳 `dict`，production adapter 的 `infer()` 回傳 `InferenceResult`，兩者不直接繼承。這樣 benchmark 程式碼不污染 production 程式碼。

### §3.2 JetsonMonitor

```python
class JetsonMonitor:
    """背景 thread，用 jtop API 每 interval 秒記錄一筆硬體指標"""

    def __init__(self, interval: float = 0.5): ...
    def start(self) -> None: ...
    def stop(self) -> list[dict]: ...
    # 回傳 list of {"timestamp", "gpu_util_pct", "cpu_util_pct",
    #               "ram_used_mb", "temp_gpu_c", "power_total_mw", ...}
```

依賴 `jetson-stats`（`sudo uv pip install -U jetson-stats`，或 `sudo pip3 install` — jetson-stats 需 system-wide 安裝，是 uv 規範的例外）。開發機上無 jtop 時應 graceful fallback（記錄空值，不 crash）。

### §3.3 BenchmarkRunner 執行協議

```
1. prepare_env.sh
   - sudo nvpmodel -m 0（MAXN）
   - sudo jetson_clocks
   - --drop-cache flag：可選，僅 cold-start 測試時啟用
   - 需事先設定 NOPASSWD，或在 runner 啟動前手動執行

2. 等待冷卻
   - 目標：GPU temp < 45°C 或最近 10s 溫升趨近平緩
   - 超時 5 分鐘則記錄 warning 並繼續
   - 無 jtop 時（開發機）：跳過溫度等待，記錄 warning

3. 記錄 RAM baseline（load 前的系統 RAM 使用量）

4. adapter.load(config)
   - 失敗（ImportError / FileNotFoundError / 其他）：
     記錄 crashed=true, gate_pass=false, n_completed=0
     寫入 .jsonl，跳到步驟 10（cooldown），繼續下一個模型

5. Warmup
   - 次數由 config.benchmark.n_warmup 決定（預設 50）
   - STT/TTS 可能需要不同次數
   - 不計入結果

6. 等待溫度穩定
   - 最近 10s 溫升趨近平緩（delta < 3°C/10s）
   - 無 jtop 時：跳過，記錄 warning

7. Measure
   - N 次推理（由 config.benchmark.n_measure 決定，預設 200）
   - JetsonMonitor 背景 0.5s 間隔記錄
   - 每次用 time.perf_counter() 計時
   - 中途 crash（CUDA OOM / SegFault / 其他）：
     記錄已完成的推理次數（n_completed）和部分統計
     crashed=true，寫入 .jsonl，執行 cleanup()

8. Quality evaluation（可選，限 feasibility pass 的模型）
   - 呼叫 adapter.evaluate(predictions, ground_truth)
   - 無 ground truth 時跳過，quality 記錄為 null

9. reporter.save()
   - 寫入 results/raw/{task}_{date}.jsonl（一行一筆 run）

10. adapter.cleanup()

11. Cooldown 30s → 下一個模型
```

### §3.4 Level 2-4 多模型共存協議

Level 2-4 需要伴跑模型模擬真實 GPU 競爭。啟動流程：

```
1. Runner load 所有伴跑模型的 adapter（依 concurrent_models 配置）
2. Warmup 所有伴跑模型（確保 GPU memory 已穩定佔用）
3. 啟動伴跑 thread：每個伴跑模型以固定 rate_hz 做推理
   - rate_hz = "match_publish": 模擬 ROS2 publish 頻率（如 face 8Hz）
   - rate_hz = "on_demand": 不主動推理，只佔 GPU memory
   - rate_hz = N (float): 每秒 N 次推理
4. 開始目標模型的 warmup → measure 流程（同 §3.3 步驟 5-9）
5. 停止伴跑 thread → cleanup 伴跑 adapters
```

伴跑模型的完整配置記錄在結果 schema 的 `device.concurrent_models` 中，確保可重現。

### §3.5 Reporter 輸出

- **Raw**：`results/raw/{task}_{date}.jsonl`（每行一筆 benchmark run，schema 見 §5）
- **Summary**：`results/summary/{task}_{date}.md`（比較表 + gate 結果 + decision_hint）
- **CSV**：`results/summary/{task}_{date}.csv`（平坦化數據，方便 Excel/Sheets 開啟）

### §3.6 Raw Results 保留規則

**目的**：保證 Stage 4 回寫決策時，原始數據仍可回溯查核。

```
results/
├── raw/                    # 工作區（.gitignore）
│   └── {task}_{date}.jsonl # 當前批次，跑完就在這裡
├── archive/                # 長期歸檔（進 git，per decision round）
│   └── {task}/
│       └── {date}/
│           ├── raw.jsonl           # 完整原始數據（從 raw/ 搬過來）
│           └── env_snapshot.txt    # nvpmodel -q + jetson_clocks --show 輸出
└── summary/                # 摘要（進 git）
    └── {task}_{date}.md
```

**規則**：
1. **跑完 benchmark 後**：raw `.jsonl` 留在 `results/raw/`，不進 git
2. **Stage 4 做決策時**：把相關的 `.jsonl` 搬到 `results/archive/{task}/{date}/`，連同 env snapshot 一起 commit
3. **archive 進 git**：因為這是決策的證據鏈，必須可回溯
4. **raw/ 工作區定期清理**：已歸檔的可刪，未歸檔的保留
5. 如果 `.jsonl` 太大（>10MB），可 gzip 後再 commit（`.jsonl.gz`）

---

## 4. candidates.yaml 格式

```yaml
task: face_detection
description: "人臉偵測模型選型"

models:
  - name: yunet_legacy
    adapter: face_yunet          # 對應 adapters/face_yunet.py
    params:
      model_path: /home/jetson/face_models/face_detection_yunet_legacy.onnx
      score_threshold: 0.35
      input_size: [320, 320]

    entry_criteria:
      installability: verified    # verified / likely / unknown / failed
      runtime_viability: verified
      gpu_path: cpu_only          # cuda / tensorrt / cpu_only / unknown
      rationale: "現有主線，已在 Jetson 上穩定運行"
      reject_if: null             # 預期淘汰條件，null 表示主線不淘汰

    benchmark:
      n_warmup: 50
      n_measure: 200
      input_source: test_inputs/images/

    feasibility_gate:
      min_fps: 5.0
      max_ram_mb: 500
      max_power_w: 10.0
      must_not_crash: true

    quality_gate:                 # feasibility pass 後才評估
      metrics:
        min_mAP_0.5: 0.70
      # 允許多個 metric，key 格式：min_{metric} 或 max_{metric}

  - name: scrfd_500m
    adapter: face_scrfd
    params:
      model_path: models/scrfd_500m.onnx
      providers: ["CUDAExecutionProvider", "CPUExecutionProvider"]
    entry_criteria:
      installability: likely
      runtime_viability: unknown
      gpu_path: cuda
      rationale: "InsightFace 推薦，比 YuNet 更快更準"
      reject_if: "安裝失敗 or FPS 無明顯提升 or RAM 超額"
    benchmark:
      n_warmup: 50
      n_measure: 200
      input_source: test_inputs/images/
    feasibility_gate:
      min_fps: 5.0
      max_ram_mb: 500
      max_power_w: 10.0
      must_not_crash: true
    quality_gate:
      metrics:
        min_mAP_0.5: 0.70
```

### coexist_profiles.yaml 格式

Level 2-4 的共存測試配置。唯一真相來源，`bench_coexist.sh` 和 runner 都從這裡讀取。

```yaml
profiles:
  # Level 2: 兩兩組合
  - name: face_with_pose
    level: 2
    target: face_candidates.yaml#yunet_legacy
    companions:
      - candidate_ref: pose_candidates.yaml#rtmpose_balanced
        rate_hz: 8.0            # 模擬 ROS2 publish 頻率
        input_source: test_inputs/images/

  - name: pose_with_whisper
    level: 2
    target: pose_candidates.yaml#rtmpose_balanced
    companions:
      - candidate_ref: stt_candidates.yaml#whisper_small
        rate_hz: on_demand      # 只佔 GPU memory，不主動推理
        input_source: test_inputs/audio/

  # Level 3: 全模型同時
  - name: full_demo_load
    level: 3
    target: pose_candidates.yaml#rtmpose_balanced
    companions:
      - candidate_ref: face_candidates.yaml#yunet_legacy
        rate_hz: 8.0
        input_source: test_inputs/images/
      - candidate_ref: stt_candidates.yaml#whisper_small
        rate_hz: on_demand
        input_source: test_inputs/audio/

  # Level 4: 壓力測試（同 Level 3 配置，duration 改為 30 分鐘）
  - name: full_demo_stress
    level: 4
    target: pose_candidates.yaml#rtmpose_balanced
    duration_minutes: 30
    companions:
      - candidate_ref: face_candidates.yaml#yunet_legacy
        rate_hz: 8.0
        input_source: test_inputs/images/
      - candidate_ref: stt_candidates.yaml#whisper_small
        rate_hz: on_demand
        input_source: test_inputs/audio/
```

**欄位說明**：
- `target`：被測模型，格式為 `{task}_candidates.yaml#{model_name}`
- `candidate_ref`：伴跑模型引用，同格式
- `rate_hz`：`on_demand`（只佔記憶體）/ `match_publish`（模擬 ROS2 發佈頻率）/ 數值（固定頻率）
- `duration_minutes`：Level 4 專用，覆蓋 n_measure

---

## 5. 結果 JSON Lines Schema

每次 benchmark run 寫一行到 `.jsonl`：

```json
{
  "schema_version": "1.0",
  "run_id": "uuid-v4",
  "timestamp": "2026-03-20T14:30:00+08:00",
  "git_commit": "abc1234",
  "env_fingerprint": {
    "python": "3.10.12",
    "cuda": "12.6",
    "tensorrt": "10.3.0",
    "onnxruntime": "1.23.0",
    "jetpack": "6.0",
    "rtmlib": "0.0.15",
    "adapter_version": "1.0"
  },

  "task": "face_detection",
  "model": "yunet_legacy",
  "level": 1,
  "mode": "headless",

  "device": {
    "name": "jetson-orin-nano-8gb",
    "power_mode": "MAXN",
    "concurrent_models": []
  },

  "config": {
    "n_warmup": 50,
    "n_measure": 200,
    "input": "test_inputs/images/office_640x480.jpg"
  },

  "feasibility": {
    "n_completed": 200,
    "fps_mean": 6.6,
    "fps_median": 6.7,
    "fps_p5": 5.9,
    "fps_std": 0.3,
    "latency_ms_mean": 151,
    "latency_ms_median": 149,
    "latency_ms_p99": 180,
    "gpu_util_pct_mean": 0,
    "ram_mb_baseline": 2700,
    "ram_mb_peak": 2800,
    "ram_mb_delta": 100,
    "temp_c_mean": 52,
    "temp_c_max": 55,
    "power_w_mean": 8.2,
    "crashed": false,
    "gate_pass": true,
    "task_specific": {}
  },

  "quality": {
    "metrics": {
      "mAP_0.5": 0.82,
      "recall": 0.77
    },
    "gate_pass": true
  },

  "decision_hint": null,
  "notes": ""
}
```

**Schema 規則**：
- `schema_version`：語義化版本號，欄位變更時遞增
- `quality`：允許 `null`（僅做 feasibility 時、或無 ground truth）
- `decision_hint`：程式推測（`JETSON_LOCAL` / `CLOUD` / `HYBRID` / `REJECTED`），非最終決策，最終決策在 research brief
- `concurrent_models`：Level 2-4 時為物件列表，記錄伴跑模型的 name / rate_hz / mode / adapter_config
- `env_fingerprint`：確保同一模型跨時間比較時環境可追溯
- `n_completed`：實際完成的推理次數（中途 crash 時 < n_measure）
- `ram_mb_baseline`：load 前的系統 RAM 使用量；`ram_mb_delta` = `ram_mb_peak` - `ram_mb_baseline`
- `feasibility_gate.max_ram_mb` 比對 `ram_mb_delta`（模型增量），不比對 `ram_mb_peak`（系統總量）
- `task_specific`：STT 的 RTF、face 的 per-face latency 等 task 專屬指標，dict 格式

**concurrent_models 物件格式**（Level 2-4）：
```json
{
  "name": "whisper_small",
  "rate_hz": "on_demand",
  "mode": "headless",
  "adapter_config": "stt_candidates.yaml#whisper_small"
}
```

---

## 6. ros_debug Mode

### §6.1 BenchAdapter debug 介面

BenchAdapter 提供一個可選的 `publish_debug()` hook，runner 在 ros_debug mode 時每次 `infer()` 後呼叫：

```python
class BenchAdapter(ABC):
    # ... load / prepare_input / infer / evaluate / cleanup ...

    def publish_debug(self, input_data: Any, prediction: dict, ros_publishers: dict) -> None:
        """可選。ros_debug mode 時由 runner 在每次 infer() 後呼叫。
        base class 提供 no-op 預設。adapter 實作時用 ros_publishers 發布 debug topics。
        ros_publishers 由 runner 根據 task 類型建立，key 為 topic 名稱。
        """
        pass
```

這樣 debug 發布邏輯集中在 adapter 內部，runner 不需要知道每個 task 該發什麼 topic，邊界乾淨。

### §6.2 最小 Topic 集合（按 task 類型）

**共通（所有 task）**：

| Topic | 型別 | 說明 |
|-------|------|------|
| `/benchmark/{task}/debug_image` | `sensor_msgs/Image` | 原始輸入 + overlay |
| `/benchmark/{task}/metrics` | `std_msgs/String` (JSON) | 即時 FPS、延遲、GPU% |

**Detection task（face）**：

| Topic | 型別 | 說明 |
|-------|------|------|
| `/benchmark/{task}/detections` | `std_msgs/String` (JSON) | `{"boxes": [...], "scores": [...], "identities": [...]}` |

**Keypoint task（pose / gesture）**：

| Topic | 型別 | 說明 |
|-------|------|------|
| `/benchmark/{task}/keypoints` | `std_msgs/String` (JSON) | `{"body_kps": [...], "hand_kps": [...], "scores": [...]}` |
| `/benchmark/{task}/state` | `std_msgs/String` (JSON) | `{"pose": "standing", "gesture": "wave", "confidence": 0.85}` |

**Audio task（stt / tts）**：

| Topic | 型別 | 說明 |
|-------|------|------|
| `/benchmark/{task}/transcript` | `std_msgs/String` (JSON) | `{"text": "你好", "language": "zh", "rtf": 0.45}` |

### §6.3 規則

- `publish_debug()` 是 no-op 預設，adapter 不實作就不發任何 topic
- runner 在 `headless` mode 時不呼叫 `publish_debug()`，零 ROS2 依賴
- ros_debug mode 的結果也記錄到 .jsonl（`"mode": "ros_debug"`）
- overlay 格式由各 adapter 自行決定，但 `debug_image` 必須是 BGR8 `sensor_msgs/Image`
- 擴充新 topic 類型需先在本 spec 登記

---

## 7. 第一版實作範圍

### 功能範圍

| 功能 | Stage 1 (Brief) | Stage 3 (Benchmark) | 優先序 |
|------|:---:|:---:|:---:|
| face | 需新建（YuNet 資料散在各處） | Level 1 + 2 | P1 |
| pose | 已有（姿勢 README） | Level 1 + 2 | P1 |
| gesture | 已有（手勢 README） | Level 1 + 2 | P1 |
| stt | 需新建 | Level 1 + 2 | P1 |
| tts | 延後 | — | P2 |
| object_search | 延後 | — | P3 |
| navigation | 延後 | — | P3 |

### 技術範圍

- headless mode 為主，ros_debug 只做少數候選
- Level 1（單模型基線）+ Level 2（兩兩組合）
- Level 3-4 在第一批候選收斂到前 1-2 名後才跑
- JetsonMonitor 在開發機上 graceful fallback（無 jtop 時記錄空值）

### 實作順序（分批計畫）

| 批次 | 內容 | 預估時間 |
|:----:|------|---------|
| **Batch 0** | core framework（runner / monitor / reporter / criteria / base adapter） | 2-3 天 |
| **Batch 1** | face task：research brief + 2 adapters（YuNet, SCRFD）+ Level 1 | 1-2 天 |
| **Batch 2** | pose + gesture task：research brief 整理 + 2-3 adapters + Level 1 | 2-3 天 |
| **Batch 3** | stt task：research brief + 2 adapters（Whisper small/tiny）+ Level 1 | 1-2 天 |
| **Batch 4** | Level 2 兩兩組合測試（全 task） | 1-2 天 |
| **Batch 5** | Level 3-4（最終候選收斂後） | 1 天 |

先做 Batch 0 + 1（core + face），驗證框架流程後再擴展其他 task。

### 初始候選模型清單（待 Research Brief 確認）

| 功能 | 主路徑（B 類） | 對照組（C 類） |
|------|-------------|--------------|
| face detection | YuNet（現有）, SCRFD-500M | RetinaFace-mobile |
| face recognition | SFace（現有） | ArcFace-r18 |
| pose | RTMPose wholebody balanced（現有）, lightweight | YOLO11n-pose |
| gesture | RTMPose hand（現有） | PINTO0309 hand-onnx |
| stt | Whisper small（現有）, Whisper tiny | Sherpa-onnx Whisper |

---

## 8. 與現有 Codebase 的關係

### 可重用的 Pattern

| 來源 | 重用內容 |
|------|---------|
| `speech_test_observer.py` | RoundRecord dataclass 模式、CSV 輸出、JSON 摘要報告、pass/fail criteria |
| `speech_30round.yaml` | YAML 測試定義結構 |
| `run_speech_test.sh` | 多階段 orchestration、ROS2 topic 健康檢查 |
| `rtmpose_inference.py` | 推理計時 pattern（time.time() + logger.info） |

### 不重複的邊界

- benchmark 框架**不取代**現有的 30 輪驗收測試（那是功能驗收，不是模型選型）
- benchmark 框架**不取代**各模組的 unit test
- benchmark 框架**不修改**現有 node 的程式碼 — adapter 是獨立的 benchmark-only 程式

### 檔案位置

- 程式碼：`benchmarks/`（repo 根目錄）
- Research Brief：`docs/research/`
- 結果 raw：`benchmarks/results/raw/`（不進 git）
- 結果 summary：`benchmarks/results/summary/`（進 git）
- 測試素材：`benchmarks/test_inputs/`（進 git，控制在 <50MB）

---

## 9. 依賴

### Jetson 端（benchmark 執行）

| 套件 | 用途 | 安裝 |
|------|------|------|
| jetson-stats | jtop Python API | `sudo pip3 install -U jetson-stats` |
| onnxruntime-gpu | ONNX 推理 | 已安裝（1.23.0, Jetson AI Lab wheel） |
| rtmlib | RTMPose 推理 | 已安裝（0.0.15, `--no-deps`） |
| opencv-python | YuNet / 影像處理 | 已安裝（Jetson 內建 4.5.4） |
| faster-whisper | STT 推理 | 已安裝 |
| numpy | 數值計算 | 已安裝 |

### 開發機（分析）

| 套件 | 用途 |
|------|------|
| matplotlib | Pareto 圖、比較圖表 |
| pandas | CSV/JSONL 分析 |

---

## 10. 參考來源

### 工具

- [jetson-stats / jtop](https://github.com/rbonghi/jetson_stats) — Jetson 硬體監控 Python API
- [trtexec](https://docs.nvidia.com/deeplearning/tensorrt/latest/performance/best-practices.html) — TensorRT 內建 benchmark
- [ONNX Runtime Profiling](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html)
- [OpenCV Zoo Benchmark](https://github.com/opencv/opencv_zoo) — YuNet 等模型的 benchmark 架構

### 方法論

- [Profiling Concurrent Vision Inference on Jetson](https://arxiv.org/html/2508.08430v1) — 多模型並行推理效能特徵
- [Multi-Model AI on Jetson Orin Nano](https://dev.to/ankk98/multi-model-ai-resource-allocation-for-humanoid-robots-a-survey-on-jetson-orin-nano-super-310i) — 人形機器人多模型資源分配
- [BetterBench (NeurIPS 2024)](https://betterbench.stanford.edu/) — AI Benchmark 最佳實踐評估框架
- [MLPerf Tiny](https://github.com/mlcommons/tiny) — 邊緣裝置標準化 benchmark 協議
- [Beyond Benchmarks: Economics of AI Inference](https://arxiv.org/html/2510.26136v1) — 成本-品質 Pareto 前沿方法
