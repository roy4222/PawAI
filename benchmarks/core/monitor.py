"""JetsonMonitor — background thread collecting hardware metrics via jtop."""
import logging
import threading
import time
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

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
        # Key names for jetson-stats >= 4.x on JetPack 6.x
        # Orin Nano has 6 CPU cores; we average all cores
        try:
            with jtop() as jetson:
                while jetson.ok() and not self._stop_event.is_set():
                    stats = jetson.stats
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
