---
name: demo-preflight
description: 在 PawAI 展示前，核對所選展示情境的設備、資料與功能證據。
---

# 展示前核對

按本次展示內容決定必要檢查，不先要求使用者選固定 quick／full 清單。從現有 `pawai doctor`、`pawai status` 或 `jetson-verify` 的可用 smoke profile 取得環境證據，再補相關 lane 的資料與功能檢查。CLI flags 與 profile 以當前實作為準。

本技能沒有獨立 `scripts/preflight.py`；不要呼叫不存在的 runner。啟動或修復操作依原授權與根 AGENTS 執行，檢查成功不增加動作權限。

分開判讀：網路可達、WebRTC 連線、有效 sensor frame、模組輸出、整合情境、實體動作。ping 成功不代表 WebRTC，topic 存在不代表有有效影像。只對有證據的展示範圍下結論；列出未驗、阻塞項與具體 artifact，不能把缺硬體證據標為 GO。
