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
    """Runs a single model benchmark: warmup -> measure -> report."""

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
        """Run benchmark for a single model. Returns the result dict."""
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
            input_data = input_ref

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
            return (total - available) / 1024  # kB -> MB
        except Exception:
            return 0.0
