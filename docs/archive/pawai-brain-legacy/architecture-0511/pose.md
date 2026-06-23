# 姿勢辨識（pose）

姿勢辨識文件已拆到 [`pose/`](pose/) 目錄。這一段比 gesture 更麻煩，因為它同時牽涉骨架規則、fallen 安全路徑、demo bridge、Brain world state。

- [pose/pose.md](pose/pose.md)：5/11 freeze 原始總覽與拆分文件索引。
- [pose/pose-runtime-flow.md](pose/pose-runtime-flow.md)：runtime 架構、topic、backend、事件生命週期。
- [pose/pose-classifier-rules.md](pose/pose-classifier-rules.md)：7 種姿勢的幾何規則、fallen gate、最容易不穩的原因。
- [pose/pose-executive-brain-integration.md](pose/pose-executive-brain-integration.md)：Executive / Brain / demo bridge 如何消費 pose event。
- [pose/pose-debug-runbook.md](pose/pose-debug-runbook.md)：明天到學校現場 debug checklist。
