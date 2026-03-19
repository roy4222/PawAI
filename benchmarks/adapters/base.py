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
