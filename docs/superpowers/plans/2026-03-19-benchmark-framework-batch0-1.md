# Benchmark Framework Batch 0+1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the core benchmark framework and validate it end-to-end with the face detection task (YuNet baseline).

**Architecture:** Modular framework with adapter pattern. `BenchAdapter` ABC defines the model interface (`load/prepare_input/infer/cleanup`). `BenchmarkRunner` orchestrates warmup → measure → report. `JetsonMonitor` runs in a background thread collecting GPU/CPU/RAM/temp/power via jtop (graceful fallback on dev machines). Results stored as JSON Lines.

**Tech Stack:** Python 3.10+, pytest, jtop (jetson-stats), OpenCV (YuNet), PyYAML, numpy

**Spec:** `docs/superpowers/specs/2026-03-19-unified-benchmark-framework-design.md`

---

## File Structure

```
benchmarks/                          # NEW directory at repo root
├── __init__.py                      # empty
├── core/
│   ├── __init__.py                  # empty
│   ├── runner.py                    # BenchmarkRunner class
│   ├── monitor.py                   # JetsonMonitor class (jtop wrapper)
│   ├── reporter.py                  # JSONLReporter + SummaryReporter
│   └── criteria.py                  # GateEvaluator (feasibility + quality gates)
├── adapters/
│   ├── __init__.py                  # empty
│   ├── base.py                     # BenchAdapter ABC
│   └── face_yunet.py              # YuNet face detection adapter
├── configs/
│   └── face_candidates.yaml       # YuNet candidate config
├── results/
│   ├── raw/.gitkeep               # working area (gitignored)
│   ├── archive/.gitkeep           # decision evidence (git tracked)
│   └── summary/.gitkeep           # markdown + csv (git tracked)
├── test_inputs/
│   ├── images/.gitkeep            # D435 test images (added later)
│   └── README.md                  # test input provenance
├── test/
│   ├── __init__.py                # empty
│   ├── helpers.py                 # FakeAdapter + shared test utilities
│   ├── test_base_adapter.py       # BenchAdapter contract tests
│   ├── test_monitor.py            # JetsonMonitor tests
│   ├── test_runner.py             # BenchmarkRunner tests
│   ├── test_reporter.py           # Reporter tests
│   ├── test_criteria.py           # GateEvaluator tests
│   └── test_face_yunet.py         # YuNet adapter tests
├── scripts/
│   ├── prepare_env.sh             # nvpmodel + jetson_clocks
│   └── bench_single.py            # CLI entry point: python bench_single.py --config ...
└── .gitignore                     # raw results, __pycache__, profiling dumps
```

**Existing files modified:** `.gitignore` (repo root — add `benchmarks/results/raw/`)

---

### Task 1: Project Scaffold

**Files:**
- Create: `benchmarks/__init__.py`, `benchmarks/core/__init__.py`, `benchmarks/adapters/__init__.py`, `benchmarks/test/__init__.py`
- Create: `benchmarks/.gitignore`
- Create: `benchmarks/results/raw/.gitkeep`, `benchmarks/results/archive/.gitkeep`, `benchmarks/results/summary/.gitkeep`
- Create: `benchmarks/test_inputs/images/.gitkeep`, `benchmarks/test_inputs/README.md`
- Modify: `.gitignore` (repo root)

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p benchmarks/{core,adapters,configs,results/{raw,archive,summary},test_inputs/images,test,scripts}
touch benchmarks/__init__.py benchmarks/core/__init__.py benchmarks/adapters/__init__.py benchmarks/test/__init__.py
touch benchmarks/results/raw/.gitkeep benchmarks/results/archive/.gitkeep benchmarks/results/summary/.gitkeep
touch benchmarks/test_inputs/images/.gitkeep
```

- [ ] **Step 2: Create benchmarks/.gitignore**

```gitignore
# Benchmark working files
results/raw/*.jsonl
__pycache__/
*.pyc
*.prof
*.nsys-rep
.pytest_cache/
```

- [ ] **Step 3: Create test_inputs/README.md**

```markdown
# Benchmark Test Inputs

固定測試素材，確保 benchmark 結果可重現。

## images/
- 來源：D435 640x480 RGB 真實截圖
- 用途：face / pose / gesture benchmark
- 新增圖片時附上拍攝條件（距離、光線、人數）

## audio/（未來新增）
- 來源：HyperX SoloCast 16kHz mono 錄音
- 用途：STT benchmark
```

- [ ] **Step 4: Update repo root .gitignore**

在 `.gitignore` 末尾加：

```gitignore
# Benchmark raw results (working area)
benchmarks/results/raw/*.jsonl
```

- [ ] **Step 5: Commit scaffold**

```bash
git add benchmarks/ .gitignore
git commit -m "feat(bench): create benchmark framework scaffold"
```

---

### Task 2: BenchAdapter ABC

**Files:**
- Create: `benchmarks/adapters/base.py`
- Create: `benchmarks/test/test_base_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# benchmarks/test/test_base_adapter.py
"""BenchAdapter ABC contract tests."""
import pytest
from benchmarks.adapters.base import BenchAdapter


class DummyAdapter(BenchAdapter):
    """Minimal concrete adapter for testing the ABC contract."""

    def __init__(self):
        self.loaded = False
        self.cleaned = False

    def load(self, config: dict) -> None:
        self.loaded = True
        self.model_name = config.get("name", "dummy")

    def prepare_input(self, input_ref: str):
        return f"prepared:{input_ref}"

    def infer(self, input_data) -> dict:
        return {"result": "ok", "input": input_data}

    def cleanup(self) -> None:
        self.cleaned = True


def test_adapter_lifecycle():
    adapter = DummyAdapter()
    adapter.load({"name": "test_model"})
    assert adapter.loaded
    inp = adapter.prepare_input("test.jpg")
    assert inp == "prepared:test.jpg"
    result = adapter.infer(inp)
    assert result["result"] == "ok"
    adapter.cleanup()
    assert adapter.cleaned


def test_evaluate_default_returns_empty_dict():
    adapter = DummyAdapter()
    adapter.load({})
    result = adapter.evaluate([], None)
    assert result == {}


def test_publish_debug_default_is_noop():
    adapter = DummyAdapter()
    adapter.load({})
    # Should not raise
    adapter.publish_debug("input", {"pred": 1}, {})


def test_cannot_instantiate_abc_directly():
    with pytest.raises(TypeError):
        BenchAdapter()


def test_missing_method_raises():
    class IncompleteAdapter(BenchAdapter):
        def load(self, config): ...
        def prepare_input(self, input_ref): ...
        # missing infer and cleanup

    with pytest.raises(TypeError):
        IncompleteAdapter()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/roy422/newLife/elder_and_dog
python -m pytest benchmarks/test/test_base_adapter.py -v
```

Expected: `ModuleNotFoundError: No module named 'benchmarks.adapters.base'`

- [ ] **Step 3: Write implementation**

```python
# benchmarks/adapters/base.py
"""BenchAdapter ABC — the interface every benchmark model adapter implements."""
from abc import ABC, abstractmethod
from typing import Any


class BenchAdapter(ABC):
    """每個模型實作 load/prepare_input/infer/cleanup。
    Runner 不需要知道 task 細節。
    """

    @abstractmethod
    def load(self, config: dict) -> None:
        """載入模型。config 來自 candidates.yaml 的 params 段。"""

    @abstractmethod
    def prepare_input(self, input_ref: str) -> Any:
        """把檔案路徑轉成模型可吃的 input。"""

    @abstractmethod
    def infer(self, input_data: Any) -> dict:
        """單次推理。回傳 prediction dict。"""

    def evaluate(self, predictions: list[dict], ground_truth: Any) -> dict:
        """可選。比對 predictions 與 ground truth，回傳 metrics dict。"""
        return {}

    def publish_debug(self, input_data: Any, prediction: dict,
                      ros_publishers: dict) -> None:
        """可選。ros_debug mode 時由 runner 呼叫。No-op 預設。"""
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """釋放模型資源。"""
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_base_adapter.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/adapters/base.py benchmarks/test/test_base_adapter.py
git commit -m "feat(bench): add BenchAdapter ABC with contract tests"
```

---

### Task 3: JetsonMonitor

**Files:**
- Create: `benchmarks/core/monitor.py`
- Create: `benchmarks/test/test_monitor.py`

- [ ] **Step 1: Write the failing test**

```python
# benchmarks/test/test_monitor.py
"""JetsonMonitor tests — must work without jtop (graceful fallback)."""
import time
import pytest
from benchmarks.core.monitor import JetsonMonitor


def test_monitor_fallback_no_jtop():
    """On dev machine without jtop, monitor should still work with empty stats."""
    mon = JetsonMonitor(interval=0.1)
    mon.start()
    time.sleep(0.35)
    records = mon.stop()
    # Should have collected ~3 records (0.35s / 0.1s interval)
    assert len(records) >= 2
    # Each record has timestamp
    for r in records:
        assert "timestamp" in r


def test_monitor_records_have_expected_keys():
    mon = JetsonMonitor(interval=0.1)
    mon.start()
    time.sleep(0.15)
    records = mon.stop()
    assert len(records) >= 1
    expected_keys = {"timestamp", "gpu_util_pct", "cpu_util_pct",
                     "ram_used_mb", "temp_gpu_c", "power_total_mw"}
    for r in records:
        assert expected_keys.issubset(r.keys())


def test_monitor_not_started_returns_empty():
    mon = JetsonMonitor(interval=0.1)
    records = mon.stop()
    assert records == []


def test_monitor_double_stop():
    mon = JetsonMonitor(interval=0.1)
    mon.start()
    time.sleep(0.15)
    r1 = mon.stop()
    r2 = mon.stop()
    assert len(r1) >= 1
    assert r2 == []


def test_aggregate_stats():
    mon = JetsonMonitor(interval=0.1)
    stats = mon.aggregate([
        {"gpu_util_pct": 50, "cpu_util_pct": 30, "ram_used_mb": 2000,
         "temp_gpu_c": 55, "power_total_mw": 8000, "timestamp": 1.0},
        {"gpu_util_pct": 60, "cpu_util_pct": 40, "ram_used_mb": 2200,
         "temp_gpu_c": 58, "power_total_mw": 9000, "timestamp": 1.5},
    ])
    assert stats["gpu_util_pct_mean"] == 55.0
    assert stats["ram_mb_peak"] == 2200
    assert stats["temp_c_max"] == 58
    assert stats["power_w_mean"] == pytest.approx(8.5)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest benchmarks/test/test_monitor.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# benchmarks/core/monitor.py
"""JetsonMonitor — background thread collecting hardware metrics via jtop."""
import logging
import threading
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Try to import jtop; graceful fallback if unavailable
try:
    from jtop import jtop
    JTOP_AVAILABLE = True
except ImportError:
    JTOP_AVAILABLE = False
    logger.info("jtop not available — JetsonMonitor will record empty stats")


class JetsonMonitor:
    """Background thread that collects GPU/CPU/RAM/temp/power at fixed interval."""

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._records: list[dict] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._started = False

    def start(self) -> None:
        self._records = []
        self._stop_event.clear()
        self._started = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> list[dict]:
        if not self._started:
            return []
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5.0)
        self._started = False
        result = list(self._records)
        self._records = []
        return result

    def _run(self) -> None:
        if JTOP_AVAILABLE:
            self._run_jtop()
        else:
            self._run_fallback()

    def _run_jtop(self) -> None:
        # Note: key names are for jetson-stats >= 4.x on JetPack 6.x
        # Orin Nano has 6 CPU cores; we average all cores for cpu_util_pct
        try:
            with jtop() as jetson:
                while jetson.ok() and not self._stop_event.is_set():
                    stats = jetson.stats
                    # Average all CPU cores (CPU1..CPU6 on Orin Nano)
                    cpu_vals = [v for k, v in stats.items()
                                if k.startswith("CPU") and isinstance(v, (int, float))]
                    cpu_avg = sum(cpu_vals) / len(cpu_vals) if cpu_vals else 0
                    self._records.append({
                        "timestamp": time.time(),
                        "gpu_util_pct": stats.get("GPU", 0),
                        "cpu_util_pct": round(cpu_avg, 1),
                        "ram_used_mb": stats.get("RAM", 0),
                        "temp_gpu_c": stats.get("Temp GPU", 0),
                        "power_total_mw": stats.get("Power TOT", 0),
                    })
                    time.sleep(self.interval)
        except Exception as e:
            logger.warning(f"jtop error, falling back: {e}")
            self._run_fallback()

    def _run_fallback(self) -> None:
        """Fallback when jtop is not available — record nulls."""
        while not self._stop_event.is_set():
            self._records.append({
                "timestamp": time.time(),
                "gpu_util_pct": None,
                "cpu_util_pct": None,
                "ram_used_mb": None,
                "temp_gpu_c": None,
                "power_total_mw": None,
            })
            time.sleep(self.interval)

    @staticmethod
    def aggregate(records: list[dict]) -> dict:
        """Aggregate a list of monitor records into summary stats."""
        if not records:
            return {}

        def _safe_mean(key):
            vals = [r[key] for r in records if r.get(key) is not None]
            return float(np.mean(vals)) if vals else None

        def _safe_max(key):
            vals = [r[key] for r in records if r.get(key) is not None]
            return float(np.max(vals)) if vals else None

        power_vals = [r["power_total_mw"] for r in records
                      if r.get("power_total_mw") is not None]

        return {
            "gpu_util_pct_mean": _safe_mean("gpu_util_pct"),
            "cpu_util_pct_mean": _safe_mean("cpu_util_pct"),
            "ram_mb_peak": _safe_max("ram_used_mb"),
            "temp_c_mean": _safe_mean("temp_gpu_c"),
            "temp_c_max": _safe_max("temp_gpu_c"),
            "power_w_mean": float(np.mean(power_vals)) / 1000.0 if power_vals else None,
        }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_monitor.py -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/core/monitor.py benchmarks/test/test_monitor.py
git commit -m "feat(bench): add JetsonMonitor with jtop fallback"
```

---

### Task 4: Reporter

**Files:**
- Create: `benchmarks/core/reporter.py`
- Create: `benchmarks/test/test_reporter.py`

- [ ] **Step 1: Write the failing test**

```python
# benchmarks/test/test_reporter.py
"""Reporter tests — JSON Lines output + summary."""
import json
import os
import tempfile
import pytest
from benchmarks.core.reporter import JSONLReporter


@pytest.fixture
def tmp_results_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d


def test_save_creates_jsonl_file(tmp_results_dir):
    reporter = JSONLReporter(output_dir=tmp_results_dir)
    result = {
        "schema_version": "1.0",
        "run_id": "test-001",
        "task": "face_detection",
        "model": "yunet",
    }
    path = reporter.save(result, task="face_detection")
    assert os.path.exists(path)
    assert path.endswith(".jsonl")


def test_save_appends_to_existing(tmp_results_dir):
    reporter = JSONLReporter(output_dir=tmp_results_dir)
    r1 = {"schema_version": "1.0", "run_id": "001", "task": "face"}
    r2 = {"schema_version": "1.0", "run_id": "002", "task": "face"}
    p1 = reporter.save(r1, task="face")
    p2 = reporter.save(r2, task="face")
    assert p1 == p2  # same file
    with open(p1) as f:
        lines = f.readlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["run_id"] == "001"
    assert json.loads(lines[1])["run_id"] == "002"


def test_each_line_is_valid_json(tmp_results_dir):
    reporter = JSONLReporter(output_dir=tmp_results_dir)
    result = {"schema_version": "1.0", "run_id": "001", "task": "t",
              "nested": {"a": 1, "b": [2, 3]}}
    path = reporter.save(result, task="t")
    with open(path) as f:
        for line in f:
            parsed = json.loads(line)
            assert parsed["nested"]["a"] == 1


def test_build_result_dict():
    reporter = JSONLReporter(output_dir="/tmp")
    result = reporter.build_result(
        task="face_detection",
        model="yunet",
        level=1,
        mode="headless",
        config={"n_warmup": 50, "n_measure": 200},
        latencies_ms=[10.0, 12.0, 11.0, 10.5, 11.5],
        hw_stats={"gpu_util_pct_mean": 0, "ram_mb_peak": 2800,
                  "temp_c_mean": 52, "temp_c_max": 55, "power_w_mean": 8.2},
        ram_baseline_mb=2700,
        crashed=False,
    )
    assert result["schema_version"] == "1.0"
    assert result["task"] == "face_detection"
    assert result["model"] == "yunet"
    assert result["feasibility"]["n_completed"] == 5
    assert result["feasibility"]["fps_mean"] > 0
    assert result["feasibility"]["ram_mb_baseline"] == 2700
    assert result["feasibility"]["ram_mb_delta"] == 100  # 2800 - 2700
    assert result["feasibility"]["crashed"] is False
    assert result["quality"] is None  # not provided
    assert "git_commit" in result
    assert "env_fingerprint" in result
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest benchmarks/test/test_reporter.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# benchmarks/core/reporter.py
"""Reporter — saves benchmark results as JSON Lines and generates summaries."""
import json
import logging
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


def _get_git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _get_env_fingerprint() -> dict:
    fp = {"python": sys.version.split()[0], "adapter_version": "1.0"}
    try:
        import cv2
        fp["opencv"] = cv2.__version__
    except ImportError:
        pass
    try:
        import onnxruntime
        fp["onnxruntime"] = onnxruntime.__version__
    except ImportError:
        pass
    try:
        import rtmlib
        fp["rtmlib"] = getattr(rtmlib, "__version__", "unknown")
    except ImportError:
        pass
    return fp


class JSONLReporter:
    """Saves each benchmark run as one JSON line in a .jsonl file."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def save(self, result: dict, task: str) -> str:
        """Append result to today's JSONL file. Returns file path."""
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"{task}_{date_str}.jsonl"
        path = os.path.join(self.output_dir, filename)
        with open(path, "a") as f:
            f.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")
        logger.info(f"Result saved to {path}")
        return path

    def build_result(
        self,
        task: str,
        model: str,
        level: int,
        mode: str,
        config: dict,
        latencies_ms: list[float],
        hw_stats: dict,
        ram_baseline_mb: float,
        crashed: bool,
        quality_metrics: Optional[dict] = None,
        concurrent_models: Optional[list] = None,
        notes: str = "",
    ) -> dict:
        """Build a complete result dict conforming to schema v1.0."""
        n_completed = len(latencies_ms)

        ram_peak = hw_stats.get("ram_mb_peak")
        ram_delta = (ram_peak - ram_baseline_mb) if ram_peak is not None else None

        # Safe FPS/latency calculation — guard against empty or zero latencies
        if n_completed > 0:
            lat = np.array(latencies_ms)
            lat_safe = lat[lat > 0]  # filter out zero/negative latencies
            if len(lat_safe) > 0:
                fps_vals = 1000.0 / lat_safe
                fps_mean = round(float(np.mean(fps_vals)), 2)
                fps_median = round(float(np.median(fps_vals)), 2)
                fps_p5 = round(float(np.percentile(fps_vals, 5)), 2)
                fps_std = round(float(np.std(fps_vals)), 2) if len(lat_safe) > 1 else 0.0
            else:
                fps_mean = fps_median = fps_p5 = fps_std = 0.0
            latency_ms_mean = round(float(np.mean(lat)), 2)
            latency_ms_median = round(float(np.median(lat)), 2)
            latency_ms_p99 = round(float(np.percentile(lat, 99)), 2)
        else:
            fps_mean = fps_median = fps_p5 = fps_std = 0.0
            latency_ms_mean = latency_ms_median = latency_ms_p99 = 0.0

        feasibility = {
            "n_completed": n_completed,
            "fps_mean": fps_mean,
            "fps_median": fps_median,
            "fps_p5": fps_p5,
            "fps_std": fps_std,
            "latency_ms_mean": latency_ms_mean,
            "latency_ms_median": latency_ms_median,
            "latency_ms_p99": latency_ms_p99,
            "gpu_util_pct_mean": hw_stats.get("gpu_util_pct_mean"),
            "ram_mb_baseline": ram_baseline_mb,
            "ram_mb_peak": ram_peak,
            "ram_mb_delta": round(ram_delta, 1) if ram_delta is not None else None,
            "temp_c_mean": hw_stats.get("temp_c_mean"),
            "temp_c_max": hw_stats.get("temp_c_max"),
            "power_w_mean": hw_stats.get("power_w_mean"),
            "crashed": crashed,
            "gate_pass": None,  # filled by criteria.py
            "task_specific": {},
        }

        quality = None
        if quality_metrics is not None:
            quality = {
                "metrics": quality_metrics,
                "gate_pass": None,  # filled by criteria.py
            }

        return {
            "schema_version": "1.0",
            "run_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": _get_git_commit(),
            "env_fingerprint": _get_env_fingerprint(),
            "task": task,
            "model": model,
            "level": level,
            "mode": mode,
            "device": {
                "name": "jetson-orin-nano-8gb",
                "power_mode": "MAXN",
                "concurrent_models": concurrent_models or [],
            },
            "config": config,
            "feasibility": feasibility,
            "quality": quality,
            "decision_hint": None,
            "notes": notes,
        }
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_reporter.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Add SummaryReporter to reporter.py**

Append to `benchmarks/core/reporter.py`:

```python
class SummaryReporter:
    """Generate comparison summary from multiple JSONL results."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def generate(self, jsonl_path: str, task: str) -> tuple[str, str]:
        """Read a JSONL file, generate markdown + CSV summaries.
        Returns (md_path, csv_path).
        """
        results = []
        with open(jsonl_path) as f:
            for line in f:
                if line.strip():
                    results.append(json.loads(line))

        if not results:
            logger.warning(f"No results in {jsonl_path}")
            return "", ""

        date_str = datetime.now().strftime("%Y%m%d")
        md_path = os.path.join(self.output_dir, f"{task}_{date_str}.md")
        csv_path = os.path.join(self.output_dir, f"{task}_{date_str}.csv")

        self._write_markdown(results, md_path, task)
        self._write_csv(results, csv_path)
        return md_path, csv_path

    def _write_markdown(self, results: list[dict], path: str, task: str):
        lines = [f"# {task} Benchmark Summary\n",
                 f"> Generated: {datetime.now().isoformat()}\n",
                 "",
                 "| Model | FPS | Latency (ms) | GPU% | RAM delta (MB) | Power (W) | Gate | Hint |",
                 "|-------|:---:|:------------:|:----:|:--------------:|:---------:|:----:|:----:|"]
        for r in results:
            f = r.get("feasibility", {})
            lines.append(
                f"| {r.get('model', '?')} "
                f"| {f.get('fps_mean', '?')} "
                f"| {f.get('latency_ms_mean', '?')} "
                f"| {f.get('gpu_util_pct_mean', '?')} "
                f"| {f.get('ram_mb_delta', '?')} "
                f"| {f.get('power_w_mean', '?')} "
                f"| {'PASS' if f.get('gate_pass') else 'FAIL'} "
                f"| {r.get('decision_hint', '?')} |"
            )
        with open(path, "w") as f:
            f.write("\n".join(lines) + "\n")
        logger.info(f"Summary written to {path}")

    def _write_csv(self, results: list[dict], path: str):
        import csv as csv_mod
        fields = ["model", "fps_mean", "fps_median", "latency_ms_mean",
                   "latency_ms_p99", "gpu_util_pct_mean", "ram_mb_delta",
                   "power_w_mean", "temp_c_max", "crashed", "gate_pass",
                   "decision_hint"]
        with open(path, "w", newline="") as f:
            writer = csv_mod.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                feas = r.get("feasibility", {})
                row = {
                    "model": r.get("model", ""),
                    "decision_hint": r.get("decision_hint", ""),
                }
                for k in fields:
                    if k not in row:
                        row[k] = feas.get(k, "")
                writer.writerow(row)
        logger.info(f"CSV written to {path}")
```

- [ ] **Step 6: Commit**

```bash
git add benchmarks/core/reporter.py benchmarks/test/test_reporter.py
git commit -m "feat(bench): add JSONLReporter + SummaryReporter with schema v1.0"
```

---

### Task 5: GateEvaluator

**Files:**
- Create: `benchmarks/core/criteria.py`
- Create: `benchmarks/test/test_criteria.py`

- [ ] **Step 1: Write the failing test**

```python
# benchmarks/test/test_criteria.py
"""GateEvaluator tests."""
import pytest
from benchmarks.core.criteria import GateEvaluator


def test_feasibility_pass():
    gate_config = {"min_fps": 5.0, "max_ram_mb": 500, "must_not_crash": True}
    feasibility = {
        "fps_mean": 6.6, "ram_mb_delta": 100, "crashed": False,
        "n_completed": 200,
    }
    result = GateEvaluator.check_feasibility(feasibility, gate_config)
    assert result["gate_pass"] is True
    assert len(result["checks"]) == 3


def test_feasibility_fail_fps():
    gate_config = {"min_fps": 10.0, "max_ram_mb": 500, "must_not_crash": True}
    feasibility = {
        "fps_mean": 6.6, "ram_mb_delta": 100, "crashed": False,
        "n_completed": 200,
    }
    result = GateEvaluator.check_feasibility(feasibility, gate_config)
    assert result["gate_pass"] is False


def test_feasibility_fail_crash():
    gate_config = {"min_fps": 1.0, "max_ram_mb": 5000, "must_not_crash": True}
    feasibility = {
        "fps_mean": 6.6, "ram_mb_delta": 100, "crashed": True,
        "n_completed": 50,
    }
    result = GateEvaluator.check_feasibility(feasibility, gate_config)
    assert result["gate_pass"] is False


def test_quality_pass():
    gate_config = {"metrics": {"min_mAP_0.5": 0.70}}
    quality_metrics = {"mAP_0.5": 0.82}
    result = GateEvaluator.check_quality(quality_metrics, gate_config)
    assert result["gate_pass"] is True


def test_quality_fail():
    gate_config = {"metrics": {"min_mAP_0.5": 0.90}}
    quality_metrics = {"mAP_0.5": 0.82}
    result = GateEvaluator.check_quality(quality_metrics, gate_config)
    assert result["gate_pass"] is False


def test_quality_with_max_metric():
    gate_config = {"metrics": {"max_wer": 0.20}}
    quality_metrics = {"wer": 0.15}
    result = GateEvaluator.check_quality(quality_metrics, gate_config)
    assert result["gate_pass"] is True


def test_decision_hint():
    feasibility = {"gate_pass": True, "gpu_util_pct_mean": 95}
    quality = {"gate_pass": True}
    hint = GateEvaluator.suggest_decision(feasibility, quality)
    assert hint in ("JETSON_LOCAL", "CLOUD", "HYBRID", "REJECTED")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest benchmarks/test/test_criteria.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# benchmarks/core/criteria.py
"""GateEvaluator — check feasibility and quality gates, suggest decision."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GateEvaluator:
    """Stateless evaluator for benchmark gate criteria."""

    @staticmethod
    def check_feasibility(feasibility: dict, gate_config: dict) -> dict:
        """Check feasibility metrics against gate thresholds.
        gate_config keys: min_fps, max_ram_mb, max_power_w, must_not_crash.
        Uses ram_mb_delta (model increment) for max_ram_mb comparison.
        """
        checks = []
        all_pass = True

        if "min_fps" in gate_config:
            ok = feasibility.get("fps_mean", 0) >= gate_config["min_fps"]
            checks.append({"metric": "fps_mean", "threshold": gate_config["min_fps"],
                           "actual": feasibility.get("fps_mean"), "pass": ok})
            all_pass &= ok

        if "max_ram_mb" in gate_config:
            delta = feasibility.get("ram_mb_delta", 0) or 0
            ok = delta <= gate_config["max_ram_mb"]
            checks.append({"metric": "ram_mb_delta", "threshold": gate_config["max_ram_mb"],
                           "actual": delta, "pass": ok})
            all_pass &= ok

        if "max_power_w" in gate_config:
            power = feasibility.get("power_w_mean") or 0
            ok = power <= gate_config["max_power_w"]
            checks.append({"metric": "power_w_mean", "threshold": gate_config["max_power_w"],
                           "actual": power, "pass": ok})
            all_pass &= ok

        if gate_config.get("must_not_crash", False):
            ok = not feasibility.get("crashed", True)
            checks.append({"metric": "crashed", "threshold": False,
                           "actual": feasibility.get("crashed"), "pass": ok})
            all_pass &= ok

        return {"gate_pass": all_pass, "checks": checks}

    @staticmethod
    def check_quality(quality_metrics: dict, gate_config: dict) -> dict:
        """Check quality metrics against gate thresholds.
        gate_config.metrics keys: min_{name} or max_{name}.
        """
        checks = []
        all_pass = True

        for key, threshold in gate_config.get("metrics", {}).items():
            if key.startswith("min_"):
                metric_name = key[4:]
                actual = quality_metrics.get(metric_name, 0)
                ok = actual >= threshold
            elif key.startswith("max_"):
                metric_name = key[4:]
                actual = quality_metrics.get(metric_name, float("inf"))
                ok = actual <= threshold
            else:
                continue
            checks.append({"metric": metric_name, "threshold": threshold,
                           "actual": actual, "pass": ok})
            all_pass &= ok

        return {"gate_pass": all_pass, "checks": checks}

    @staticmethod
    def suggest_decision(feasibility: dict,
                         quality: Optional[dict] = None) -> str:
        """Suggest a decision code based on gate results. Advisory only."""
        if not feasibility.get("gate_pass", False):
            return "REJECTED"
        if quality is not None and not quality.get("gate_pass", False):
            return "REJECTED"
        gpu = feasibility.get("gpu_util_pct_mean")
        if gpu is not None and gpu > 90:
            return "HYBRID"
        return "JETSON_LOCAL"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_criteria.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add benchmarks/core/criteria.py benchmarks/test/test_criteria.py
git commit -m "feat(bench): add GateEvaluator for feasibility + quality gates"
```

---

### Task 6: BenchmarkRunner

**Files:**
- Create: `benchmarks/core/runner.py`
- Create: `benchmarks/test/test_runner.py`
- Create: `benchmarks/test/helpers.py`

- [ ] **Step 1: Write shared test fixtures**

```python
# benchmarks/test/helpers.py
"""Shared test helpers (not conftest — direct import is cleaner)."""
import time
import pytest
from benchmarks.adapters.base import BenchAdapter


class FakeAdapter(BenchAdapter):
    """Adapter that simulates inference with configurable delay."""

    def __init__(self):
        self.load_count = 0
        self.infer_count = 0
        self.cleanup_count = 0
        self.fail_on_load = False
        self.fail_on_infer_at = -1  # crash at Nth infer

    def load(self, config: dict) -> None:
        if self.fail_on_load:
            raise RuntimeError("simulated load failure")
        self.load_count += 1
        self.delay = config.get("delay_ms", 1) / 1000.0

    def prepare_input(self, input_ref: str):
        return f"fake:{input_ref}"

    def infer(self, input_data) -> dict:
        self.infer_count += 1
        if self.infer_count == self.fail_on_infer_at:
            raise RuntimeError("simulated CUDA OOM")
        time.sleep(self.delay)
        return {"boxes": [[10, 20, 50, 60]], "scores": [0.95]}

    def cleanup(self) -> None:
        self.cleanup_count += 1


@pytest.fixture
def fake_adapter():
    return FakeAdapter()
```

- [ ] **Step 2: Write the failing test**

```python
# benchmarks/test/test_runner.py
"""BenchmarkRunner tests."""
import tempfile
import pytest
from benchmarks.core.runner import BenchmarkRunner
from benchmarks.test.helpers import FakeAdapter


def test_run_single_model(tmp_path):
    adapter = FakeAdapter()
    config = {
        "name": "test_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 2, "n_measure": 5, "input_source": "."},
        "feasibility_gate": {"min_fps": 0.1, "must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(
        adapter=adapter,
        config=config,
        task="test",
        level=1,
        mode="headless",
    )
    assert result["task"] == "test"
    assert result["model"] == "test_model"
    assert result["feasibility"]["n_completed"] == 5
    assert result["feasibility"]["crashed"] is False
    assert result["feasibility"]["fps_mean"] > 0
    assert adapter.cleanup_count == 1


def test_run_load_failure(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_on_load = True
    config = {
        "name": "bad_model",
        "params": {},
        "benchmark": {"n_warmup": 1, "n_measure": 3, "input_source": "."},
        "feasibility_gate": {"must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(adapter=adapter, config=config, task="test",
                        level=1, mode="headless")
    assert result["feasibility"]["crashed"] is True
    assert result["feasibility"]["n_completed"] == 0
    assert result["feasibility"]["gate_pass"] is False


def test_run_infer_crash(tmp_path):
    adapter = FakeAdapter()
    adapter.fail_on_infer_at = 3  # crash on 3rd infer (during measure)
    config = {
        "name": "crash_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 1, "n_measure": 5, "input_source": "."},
        "feasibility_gate": {"must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(adapter=adapter, config=config, task="test",
                        level=1, mode="headless")
    assert result["feasibility"]["crashed"] is True
    # Warmup consumed 1 infer, then measure: 1st success, 2nd = infer_count 3 = crash
    assert result["feasibility"]["n_completed"] == 1
    assert adapter.cleanup_count == 1


def test_result_saved_to_jsonl(tmp_path):
    adapter = FakeAdapter()
    config = {
        "name": "test_model",
        "params": {"delay_ms": 1},
        "benchmark": {"n_warmup": 1, "n_measure": 3, "input_source": "."},
        "feasibility_gate": {"min_fps": 0.1, "must_not_crash": True},
    }
    runner = BenchmarkRunner(results_dir=str(tmp_path))
    result = runner.run(adapter=adapter, config=config, task="test",
                        level=1, mode="headless")
    # Check jsonl file was created
    import glob
    files = glob.glob(str(tmp_path / "test_*.jsonl"))
    assert len(files) == 1
```

- [ ] **Step 3: Run test to verify it fails**

```bash
python -m pytest benchmarks/test/test_runner.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 4: Write implementation**

```python
# benchmarks/core/runner.py
"""BenchmarkRunner — orchestrates warmup, measure, and report."""
import logging
import os
import time
from typing import Any, Optional

from benchmarks.adapters.base import BenchAdapter
from benchmarks.core.criteria import GateEvaluator
from benchmarks.core.monitor import JetsonMonitor
from benchmarks.core.reporter import JSONLReporter

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Runs a single model benchmark: warmup → measure → report."""

    def __init__(self, results_dir: str, monitor_interval: float = 0.5):
        self.reporter = JSONLReporter(output_dir=results_dir)
        self.monitor_interval = monitor_interval

    def run(
        self,
        adapter: BenchAdapter,
        config: dict,
        task: str,
        level: int = 1,
        mode: str = "headless",
        concurrent_models: Optional[list] = None,
        test_input_ref: Optional[str] = None,
    ) -> dict:
        """Run benchmark for a single model.
        test_input_ref overrides config's input_source. If None, auto-resolve
        from input_source directory (picks first matching file).
        """
        model_name = config["name"]
        bench_cfg = config.get("benchmark", {})
        n_warmup = bench_cfg.get("n_warmup", 50)
        n_measure = bench_cfg.get("n_measure", 200)

        logger.info(f"=== Benchmark: {model_name} (task={task}, level={level}) ===")

        # Record RAM baseline
        ram_baseline = self._get_ram_mb()

        # Step 1: Load
        try:
            adapter.load(config.get("params", {}))
            logger.info(f"Model {model_name} loaded successfully")
        except Exception as e:
            logger.error(f"Load failed for {model_name}: {e}")
            result = self._build_crash_result(
                task, model_name, level, mode, bench_cfg,
                ram_baseline, concurrent_models, str(e),
            )
            self._evaluate_and_save(result, config, task)
            return result

        # Step 2: Resolve and prepare input
        input_ref = self._resolve_input(bench_cfg, test_input_ref)
        try:
            input_data = adapter.prepare_input(input_ref)
        except Exception as e:
            logger.warning(f"prepare_input failed for '{input_ref}': {e}")
            input_data = input_ref  # let adapter handle raw ref

        # Step 3: Warmup
        logger.info(f"Warmup: {n_warmup} runs")
        for i in range(n_warmup):
            try:
                adapter.infer(input_data)
            except Exception as e:
                logger.warning(f"Warmup infer {i} failed: {e}")

        # Step 4: Measure
        monitor = JetsonMonitor(interval=self.monitor_interval)
        monitor.start()
        latencies_ms = []
        crashed = False

        logger.info(f"Measure: {n_measure} runs")
        for i in range(n_measure):
            try:
                t0 = time.perf_counter()
                adapter.infer(input_data)
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                latencies_ms.append(elapsed_ms)
            except Exception as e:
                logger.error(f"Infer crashed at run {i}: {e}")
                crashed = True
                break

        hw_records = monitor.stop()
        hw_stats = JetsonMonitor.aggregate(hw_records)

        # Step 5: Cleanup
        try:
            adapter.cleanup()
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}")

        # Step 6: Build result
        result = self.reporter.build_result(
            task=task,
            model=model_name,
            level=level,
            mode=mode,
            config=bench_cfg,
            latencies_ms=latencies_ms,
            hw_stats=hw_stats,
            ram_baseline_mb=ram_baseline,
            crashed=crashed,
            concurrent_models=concurrent_models,
        )

        self._evaluate_and_save(result, config, task)
        return result

    def _evaluate_and_save(self, result: dict, config: dict, task: str):
        """Evaluate gates and save result."""
        feas_gate = config.get("feasibility_gate", {})
        if feas_gate:
            gate_result = GateEvaluator.check_feasibility(
                result["feasibility"], feas_gate)
            result["feasibility"]["gate_pass"] = gate_result["gate_pass"]

        hint = GateEvaluator.suggest_decision(
            result["feasibility"], result.get("quality"))
        result["decision_hint"] = hint

        self.reporter.save(result, task=task)
        logger.info(f"Result: fps={result['feasibility'].get('fps_mean', '?')}, "
                     f"gate={'PASS' if result['feasibility'].get('gate_pass') else 'FAIL'}, "
                     f"hint={hint}")

    def _build_crash_result(self, task, model, level, mode, config,
                            ram_baseline, concurrent_models, error_msg):
        """Build a result dict for a model that failed to load."""
        return self.reporter.build_result(
            task=task, model=model, level=level, mode=mode,
            config=config, latencies_ms=[], hw_stats={},
            ram_baseline_mb=ram_baseline, crashed=True,
            concurrent_models=concurrent_models,
            notes=f"Load failed: {error_msg}",
        )

    @staticmethod
    def _resolve_input(bench_cfg: dict, override: Optional[str] = None) -> str:
        """Resolve test input: explicit override > first file from input_source dir."""
        if override is not None:
            return override
        input_source = bench_cfg.get("input_source", ".")
        if os.path.isfile(input_source):
            return input_source
        if os.path.isdir(input_source):
            exts = (".jpg", ".jpeg", ".png", ".bmp", ".wav", ".mp3")
            for fname in sorted(os.listdir(input_source)):
                if fname.lower().endswith(exts):
                    return os.path.join(input_source, fname)
        logger.warning(f"No input files found in {input_source}, using raw ref")
        return input_source

    @staticmethod
    def _get_ram_mb() -> float:
        """Get current system RAM usage in MB via /proc/meminfo (no extra deps)."""
        try:
            with open("/proc/meminfo") as f:
                info = {}
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        info[parts[0].rstrip(":")] = int(parts[1])
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable", 0)
            return (total - available) / 1024  # kB → MB
        except Exception:
            return 0.0
```

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_runner.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add benchmarks/core/runner.py benchmarks/test/test_runner.py benchmarks/test/helpers.py
git commit -m "feat(bench): add BenchmarkRunner with crash recovery"
```

---

### Task 7: Face YuNet Adapter (Batch 1)

**Files:**
- Create: `benchmarks/adapters/face_yunet.py`
- Create: `benchmarks/test/test_face_yunet.py`
- Reference: `face_perception/face_perception/face_identity_node.py:147-157` (YuNet loading pattern)

- [ ] **Step 1: Write the failing test**

```python
# benchmarks/test/test_face_yunet.py
"""YuNet face detection adapter tests.
Uses a synthetic test image since real D435 images may not be available.
"""
import numpy as np
import pytest

import os

try:
    import cv2
    HAS_OPENCV_FACE = hasattr(cv2, "FaceDetectorYN")
except ImportError:
    HAS_OPENCV_FACE = False

# Default model path — only exists on Jetson
YUNET_MODEL = os.environ.get(
    "YUNET_MODEL_PATH",
    "/home/jetson/face_models/face_detection_yunet_legacy.onnx",
)
HAS_MODEL_FILE = os.path.isfile(YUNET_MODEL)

from benchmarks.adapters.face_yunet import FaceYuNetAdapter


def test_adapter_is_bench_adapter():
    from benchmarks.adapters.base import BenchAdapter
    assert issubclass(FaceYuNetAdapter, BenchAdapter)


@pytest.mark.skipif(not HAS_OPENCV_FACE,
                    reason="OpenCV not available")
def test_prepare_input_returns_ndarray(tmp_path):
    # Create a dummy image file
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.imwrite(str(tmp_path / "test.jpg"), img)
    path = str(tmp_path / "test.jpg")

    adapter = FaceYuNetAdapter()
    result = adapter.prepare_input(path)
    assert isinstance(result, np.ndarray)
    assert result.shape == (480, 640, 3)


@pytest.mark.skipif(not HAS_OPENCV_FACE or not HAS_MODEL_FILE,
                    reason="OpenCV face module or YuNet model file not available")
def test_load_and_infer_synthetic():
    """Test with a synthetic image — may detect 0 faces, that's OK.
    Requires model file on disk. Set YUNET_MODEL_PATH env var to override.
    """
    adapter = FaceYuNetAdapter()
    adapter.load({
        "model_path": YUNET_MODEL,
        "score_threshold": 0.5,
        "input_size": [320, 320],
    })
    # Synthetic image with a rough face-like pattern
    img = np.random.randint(100, 200, (480, 640, 3), dtype=np.uint8)
    result = adapter.infer(img)
    assert "boxes" in result
    assert "scores" in result
    assert "n_faces" in result
    assert isinstance(result["n_faces"], int)
    adapter.cleanup()


def test_cleanup_safe_when_not_loaded():
    adapter = FaceYuNetAdapter()
    adapter.cleanup()  # Should not raise
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest benchmarks/test/test_face_yunet.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Write implementation**

```python
# benchmarks/adapters/face_yunet.py
"""YuNet face detection benchmark adapter.
Wraps OpenCV's FaceDetectorYN for benchmarking.
Reference: face_perception/face_perception/face_identity_node.py:147-157
"""
import logging
from typing import Any, Optional

import cv2
import numpy as np

from benchmarks.adapters.base import BenchAdapter

logger = logging.getLogger(__name__)


class FaceYuNetAdapter(BenchAdapter):
    """Benchmark adapter for YuNet face detection via OpenCV."""

    def __init__(self):
        self._detector: Optional[cv2.FaceDetectorYN] = None

    def load(self, config: dict) -> None:
        model_path = config.get(
            "model_path",
            "/home/jetson/face_models/face_detection_yunet_legacy.onnx",
        )
        score_threshold = config.get("score_threshold", 0.35)
        nms_threshold = config.get("nms_threshold", 0.3)
        top_k = config.get("top_k", 5000)
        input_size = tuple(config.get("input_size", [320, 320]))

        if not hasattr(cv2, "FaceDetectorYN"):
            raise ImportError(
                "OpenCV face module not available. "
                "Need OpenCV >= 4.8 with contrib (face module)."
            )

        self._detector = cv2.FaceDetectorYN.create(
            str(model_path), "", input_size,
            score_threshold, nms_threshold, top_k,
        )
        self._input_size = input_size
        logger.info(f"YuNet loaded: {model_path} (input={input_size})")

    def prepare_input(self, input_ref: str) -> np.ndarray:
        img = cv2.imread(input_ref)
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {input_ref}")
        return img

    def infer(self, input_data: np.ndarray) -> dict:
        if self._detector is None:
            raise RuntimeError("Model not loaded. Call load() first.")

        h, w = input_data.shape[:2]
        self._detector.setInputSize((w, h))
        retval, faces = self._detector.detect(input_data)

        n_faces = faces.shape[0] if faces is not None else 0
        boxes = []
        scores = []
        if faces is not None:
            for face in faces:
                x, y, fw, fh = face[:4].astype(int).tolist()
                score = float(face[14]) if face.shape[0] > 14 else 0.0
                boxes.append([x, y, fw, fh])
                scores.append(score)

        return {"boxes": boxes, "scores": scores, "n_faces": n_faces}

    def cleanup(self) -> None:
        self._detector = None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python -m pytest benchmarks/test/test_face_yunet.py -v
```

Expected: 4 tests PASS (or 3 PASS + 1 SKIP if OpenCV face module unavailable on dev machine)

- [ ] **Step 5: Commit**

```bash
git add benchmarks/adapters/face_yunet.py benchmarks/test/test_face_yunet.py
git commit -m "feat(bench): add YuNet face detection adapter"
```

---

### Task 7.5: Face Research Brief (Stage 1 — 制度流程前置)

**Files:**
- Create: `docs/research/face.md`

制度流程要求 `Research Brief → Candidate Shortlist → Benchmark`。face 的候選 config 必須從 brief 收斂出來，不能直接憑直覺填。

- [ ] **Step 1: Create minimal face research brief**

```markdown
# 人臉辨識模型選型調查

> 最後更新：2026-03-19

## 目標效果
- 偵測 + 識別 D435 視野內的人臉，距離 0.5-3m
- 4/13 Demo 目標：已知人臉識別成功率 ≥ 80%，偵測延遲 < 200ms

## 候選模型

| # | 模型 | 框架 | 輸出 | Installability | Runtime viability | GPU 路徑 | 社群性能參考 | 納入原因 | 預期淘汰條件 |
|---|------|------|------|:-:|:-:|:-:|---|---|---|
| 1 | YuNet (legacy) | OpenCV DNN | bbox + 5-point | verified | verified | cpu_only | ~6.6 Hz (Jetson 3/18 實測) | 現有主線，穩定 | — |
| 2 | SCRFD-500M | ONNX Runtime | bbox + 5-point | likely | unknown | cuda | 推估 15+ Hz | InsightFace 推薦，更快更準 | 安裝失敗 or FPS 無明顯提升 |
| 3 | SFace (recognition) | OpenCV DNN | 128-d embedding | verified | verified | cpu_only | 已驗證 | 現有主線 | — |

### 排除清單

| 模型 | 排除原因 | 證據等級 |
|------|---------|:-------:|
| MediaPipe Face Detection | Jetson ARM64 無 wheel，GPU delegate 不可用 | community_only |
| RetinaFace-R50 | 模型太大 (~100MB)，Jetson 記憶體預算不足 | community_only |

## 社群調查摘要
- **YuNet**：OpenCV Zoo 內建，`cv2.FaceDetectorYN`，無額外依賴。Jetson 上走 CPU（OpenCV DNN 的 CUDA backend 不支援 FaceDetectorYN）。~6.6 Hz 已在 3/18 實測。
- **SCRFD-500M**：InsightFace 系列輕量偵測器。ONNX 格式，可走 CUDAExecutionProvider。社群在 Jetson 上有部署案例但需驗證。
- **SFace**：OpenCV Zoo 內建識別模型，128 維 embedding，餘弦相似度匹配。已驗證可用。

## Jetson 資源約束
- 人臉偵測+識別合計 RAM 增量目標：< 500MB
- GPU 預算：盡量 0%（CPU-only 最佳），允許最多 10%
- 與 RTMPose 共存時 GPU 已 91-99%，人臉模組不應再吃 GPU

## 決策（Stage 4 回填）
| 模型 | Decision Code | Placement | 依據 |
|------|:---:|---|---|
| | | | |
```

- [ ] **Step 2: Commit**

```bash
mkdir -p docs/research
git add docs/research/face.md
git commit -m "docs(research): face detection research brief — Stage 1"
```

---

### Task 8: Face Candidates Config + CLI Entry Point

**Files:**
- Create: `benchmarks/configs/face_candidates.yaml`
- Create: `benchmarks/scripts/bench_single.py`
- Create: `benchmarks/scripts/prepare_env.sh`

- [ ] **Step 1: Create face_candidates.yaml**

```yaml
# benchmarks/configs/face_candidates.yaml
task: face_detection
description: "人臉偵測模型選型 — Batch 1"

models:
  - name: yunet_legacy
    adapter: face_yunet
    params:
      model_path: /home/jetson/face_models/face_detection_yunet_legacy.onnx
      score_threshold: 0.35
      input_size: [320, 320]

    entry_criteria:
      installability: verified
      runtime_viability: verified
      gpu_path: cpu_only
      rationale: "現有主線，已在 Jetson 上穩定運行 ~6.6 Hz"
      reject_if: null

    benchmark:
      n_warmup: 50
      n_measure: 200
      input_source: test_inputs/images/

    feasibility_gate:
      min_fps: 3.0
      max_ram_mb: 500
      must_not_crash: true

    quality_gate:
      metrics:
        min_mAP_0.5: 0.60
```

- [ ] **Step 2: Create prepare_env.sh**

```bash
#!/bin/bash
# benchmarks/scripts/prepare_env.sh
# Lock Jetson to MAXN mode for reproducible benchmarks.
# Usage: sudo bash prepare_env.sh [--drop-cache]
set -euo pipefail

echo "=== Setting MAXN power mode ==="
nvpmodel -m 0
echo "=== Locking clocks ==="
jetson_clocks

if [[ "${1:-}" == "--drop-cache" ]]; then
    echo "=== Dropping page cache ==="
    sync
    echo 3 > /proc/sys/vm/drop_caches
fi

echo "=== Environment ready ==="
nvpmodel -q
jetson_clocks --show
```

- [ ] **Step 3: Create bench_single.py CLI**

```python
#!/usr/bin/env python3
# benchmarks/scripts/bench_single.py
"""CLI entry point: benchmark a single model from a candidates config.

Usage:
    python benchmarks/scripts/bench_single.py \
        --config benchmarks/configs/face_candidates.yaml \
        --model yunet_legacy \
        --level 1
"""
import argparse
import importlib
import logging
import sys
import yaml

# Add repo root to path so 'benchmarks' package is importable
sys.path.insert(0, ".")

from benchmarks.core.runner import BenchmarkRunner

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("bench_single")

# Adapter registry: adapter name -> module.Class
ADAPTER_REGISTRY = {
    "face_yunet": "benchmarks.adapters.face_yunet:FaceYuNetAdapter",
}


def load_adapter(adapter_name: str):
    """Dynamically load an adapter class by name."""
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"Unknown adapter: {adapter_name}. "
                         f"Known: {list(ADAPTER_REGISTRY.keys())}")
    module_path, class_name = ADAPTER_REGISTRY[adapter_name].rsplit(":", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)()


def main():
    parser = argparse.ArgumentParser(description="Run benchmark for a single model")
    parser.add_argument("--config", required=True, help="Path to candidates YAML")
    parser.add_argument("--model", required=True, help="Model name from config")
    parser.add_argument("--level", type=int, default=1, help="Benchmark level (1-4)")
    parser.add_argument("--mode", default="headless", choices=["headless", "ros_debug"])
    parser.add_argument("--results-dir", default="benchmarks/results/raw")
    parser.add_argument("--input", default="default", help="Test input reference")
    args = parser.parse_args()

    with open(args.config) as f:
        candidates = yaml.safe_load(f)

    task = candidates["task"]
    model_config = None
    for m in candidates["models"]:
        if m["name"] == args.model:
            model_config = m
            break

    if model_config is None:
        logger.error(f"Model '{args.model}' not found in {args.config}")
        sys.exit(1)

    adapter = load_adapter(model_config["adapter"])
    runner = BenchmarkRunner(results_dir=args.results_dir)
    result = runner.run(
        adapter=adapter,
        config=model_config,
        task=task,
        level=args.level,
        mode=args.mode,
        test_input_ref=args.input,
    )

    gate = "PASS" if result["feasibility"].get("gate_pass") else "FAIL"
    fps = result["feasibility"].get("fps_mean", "?")
    logger.info(f"\n{'='*50}")
    logger.info(f"Model: {args.model}")
    logger.info(f"FPS: {fps}")
    logger.info(f"Gate: {gate}")
    logger.info(f"Hint: {result.get('decision_hint', '?')}")
    logger.info(f"{'='*50}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Test CLI smoke test (dev machine, no real model)**

```bash
cd /home/roy422/newLife/elder_and_dog
python benchmarks/scripts/bench_single.py \
    --config benchmarks/configs/face_candidates.yaml \
    --model yunet_legacy --level 1
```

Expected: Error about model file not found (expected on dev machine without model file). Verifies the CLI loads config, finds the model entry, instantiates the adapter, and fails gracefully at load.

- [ ] **Step 5: Commit**

```bash
git add benchmarks/configs/face_candidates.yaml benchmarks/scripts/
git commit -m "feat(bench): add face config + CLI entry point + prepare_env script"
```

---

### Task 9: Run All Tests + Final Validation

**Files:** None (validation only)

- [ ] **Step 1: Run all benchmark tests**

```bash
cd /home/roy422/newLife/elder_and_dog
python -m pytest benchmarks/test/ -v --tb=short
```

Expected: All tests PASS (some may SKIP on dev machine due to missing OpenCV face module)

- [ ] **Step 2: Verify .gitignore works**

```bash
# Create a fake raw result to verify it's ignored
echo '{"test": true}' > benchmarks/results/raw/test_20260319.jsonl
git status
# Should show the .jsonl as untracked but NOT in staged
git check-ignore benchmarks/results/raw/test_20260319.jsonl
# Should output the path (confirming it's ignored)
rm benchmarks/results/raw/test_20260319.jsonl
```

- [ ] **Step 3: Verify project structure**

```bash
find benchmarks -type f | sort | head -40
```

Expected output should match the file structure in this plan.

- [ ] **Step 4: Final commit (if any remaining changes)**

```bash
git status
# If clean: nothing to do
# If changes: git add -A benchmarks/ && git commit -m "chore(bench): batch 0+1 cleanup"
```

---

## Summary

| Task | Description | Files | Tests |
|:----:|-------------|:-----:|:-----:|
| 1 | Scaffold | 12 | 0 |
| 2 | BenchAdapter ABC | 1 | 5 |
| 3 | JetsonMonitor | 1 | 5 |
| 4 | Reporter (JSONL + Summary) | 1 | 4 |
| 5 | GateEvaluator | 1 | 7 |
| 6 | BenchmarkRunner | 2 | 4 |
| 7 | YuNet Adapter | 1 | 4 |
| 7.5 | Face Research Brief (Stage 1) | 1 | 0 |
| 8 | Config + CLI | 3 | 0 |
| 9 | Validation | 0 | 0 |
| **Total** | | **23** | **29** |

After this plan is complete, the framework is validated on dev machine. Next steps:
1. rsync to Jetson, add real D435 test images to `benchmarks/test_inputs/images/`
2. Run first real benchmark on Jetson: `python benchmarks/scripts/bench_single.py --config benchmarks/configs/face_candidates.yaml --model yunet_legacy`
3. Proceed to Batch 2 (pose + gesture research briefs + adapters)
