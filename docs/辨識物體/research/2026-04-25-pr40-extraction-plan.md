# PR #40 物件辨識功能提取計畫

**日期**：2026-04-25
**來源 PR**：https://github.com/roy4222/PawAI/pull/40 (Capybara094 / Elio / 黃旭)
**整體 PR review 結論**：REQUEST_CHANGES（不能直接 merge — 有 ultralytics 違禁 + RCE 風險）— 詳見 `docs/mission/meetings/2026-04-25.md`
**本檔目的**：列出 PR 內**值得提取**到本地程式碼的功能，以及實作時要注意的事

---

## 可提取的功能

### 1. MJPEG stream 重連 retry 邏輯

**來源**：PR 內 `local_yolo_mjpeg.py` 的 stream loop

**提取要點**：
- `had_send_error` flag 追蹤連線狀態
- 5s 節流 log（不會 noisy log spam）
- 寫得乾淨

**整合到本地**：
- ⚠️ **必須重寫**：原檔用 `from ultralytics import YOLO` —
  CLAUDE.md 紅線（會破壞 Jetson torch wheel）
- 邏輯本身好，但要改成用 `onnxruntime` + TRT EP，對齊既有 `object_perception` 套件架構
- 既有套件已用 `yolo26n.onnx` + TRT FP16，retry 邏輯可加進去

### 2. 前端 hardware/stream 雙模式切換

**來源**：PR 內 `pawai-studio/frontend/components/object/local-camera.tsx`

**提取要點**：
- hardware（D435）vs stream（網頁 MJPEG）雙模式切換 UX
- `stopRemoteYolo` flag 控制清理路徑
- 有意識地處理 lifecycle

**整合到本地**：
- 整合到 `pawai-studio/frontend/components/object/`
- 注意去掉對 `mock_server.py /mock/yolo/start` endpoint 的呼叫
  （因為原 endpoint 有 RCE 風險不能保留）

---

## ❌ 不要的東西（嚴格禁止整合）

### 二進位檔污染
- **`pawai-studio/backend/yolo26n.onnx`（~12.8MB）** — 進 git
- **`pawai-studio/backend/yolov8n.onnx`（~12.8MB）** — 進 git，**且與 yolo26n.onnx SHA 完全相同**（同一個 blob 改名）
- **`pawai-studio/backend/yolov8n.pt`（~6.5MB）** — 進 git
- 共 ~32MB binary，repo size 永久膨脹
- 規範：模型走 release asset 或 Jetson 既有路徑 `/home/jetson/models/`，
  `.gitignore` 加 `*.onnx *.pt`

### 違禁套件
- `from ultralytics import YOLO`（line ~57 in `local_yolo_mjpeg.py`）
  — 踩到 `docs/辨識物體/CLAUDE.md` 紅線
- 既有 `object_perception` 套件已用 onnxruntime + TRT EP 跑 yolo26n
  → 用既有架構不要平行重做

### 安全 / RCE
- **`mock_server.py` `/mock/yolo/start` endpoint** —
  任意人可遠端 spawn process（`subprocess.Popen([sys.executable, script_path])`）
  - 無 auth、無 path 檢查
  - mock_server 預設 `0.0.0.0:8000`（line 415）
  - 同 LAN 任何人可反覆 spawn YOLO 進程把 Jetson 打爆
  - `yolo_process` 是 module-global，多 worker race
- `local-camera.tsx:107` 寫死 `setTimeout(…, 3000)` 假設 Python 3 秒能起來；
  模型冷啟動超過 3s 就誤判 active → 應該 poll `/video_feed` HEAD

### 雜訊
- 根目錄新增 `package.json` + `package-lock.json`（next/react/lucide）
  → 跟 `pawai-studio/frontend/` 重複，污染 repo root
- `mock_server.py:376` 殘留 `print(f"DEBUG INCOMING: {trigger.data}")`
- `mock_server.py` import `subprocess/os/sys` 寫在檔案中段（line ~385，不是 top）

---

## 實作優先級

| 優先級 | 項目 | 估時 |
|-------|------|------|
| P1 | retry 邏輯重寫到 `object_perception`（onnxruntime + TRT EP） | 1 hr |
| P1 | hardware/stream 雙模式 UX 整合 | 1 hr |
| P2 | （無）—— 物件辨識本身已驗收 OK，這次只是補 UX |

---

## 注意事項

- 物件辨識套件 `object_perception` 已 [USABLE] 狀態（YOLO26n + TRT FP16）
- 4/25 會議重點：
  - 教授質疑「為什麼 26 不是 12」→ 黃旭要查版本差異寫進 demo 說明
  - 大類別 vs 個別物品 fine-tune 的 demo 應對話術已定（見 meeting 紀錄）
  - Wi-Fi 鏡頭改有線
- 改完後測：
  - `colcon build --packages-select object_perception`
  - `ros2 launch object_perception object_perception.launch.py`
  - 確認 `/event/object_detected` 不變
