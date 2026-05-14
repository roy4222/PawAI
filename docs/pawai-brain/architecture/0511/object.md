# 物體辨識（object_perception）

物體辨識文件已拆到 [`object/`](object/) 目錄。這段重點不是只有 YOLO，而是 YOLO 事件、HSV 顏色、Brain recent object cache、Executive object_remark 四層如何互相保護。

- [object/object.md](object/object.md)：5/11 freeze 原始總覽與拆分文件索引。
- [object/object-runtime-flow.md](object/object-runtime-flow.md)：runtime 架構、topic、ONNX/TensorRT、event schema。
- [object/object-color-and-detection.md](object/object-color-and-detection.md)：YOLO26n 後處理、COCO 80、HSV 12 色、常見誤判。
- [object/object-brain-executive-integration.md](object/object-brain-executive-integration.md)：Brain recent_objects、Executive object_remark、person filter、去重策略。
- [object/object-debug-runbook.md](object/object-debug-runbook.md)：明天到學校現場 debug checklist。
