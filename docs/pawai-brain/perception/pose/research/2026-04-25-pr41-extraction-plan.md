# PR #41 姿勢辨識功能提取計畫

**日期**：2026-04-25
**來源 PR**：https://github.com/roy4222/PawAI/pull/41 (GuaGua0216 / 瓜瓜)
**整體 PR review 結論**：REQUEST_CHANGES（不能直接 merge）— 詳見 `docs/mission/meetings/2026-04-25.md`
**本檔目的**：列出 PR 內**值得提取**到本地程式碼的功能，以及實作時要注意的事

---

## 可提取的功能

### 1. 姿勢分類細則（最有價值）

**來源**：PR 內 `pawai-studio/frontend/components/pose/test_pose.py` 的 `classify_pose()` 函式

**提取要點**：
- 用 hip / knee / trunk 三個關節角度組合判斷
- 加 visibility gating（landmark 信心度低時不分類）
- 用 `deque` 做時間平滑（避免單幀抖動跳變）
- 優先序判斷邏輯（fallen > sitting > crouching > standing）

**整合到本地**：
- 目標檔案：`vision_perception/vision_perception/pose_classifier.py`（新建或補強現有）
- 現有節點 `vision_perception_node` 可直接吃，不影響 contract
- **改名**：原檔名 `test_pose.py` 會被 pytest 收進去執行 → 改 `pose_classifier.py`
- **lazy init**：原 module 底部 `mp_pose.Pose(...)` 是 import 副作用，要包進 `_get_pose()` lazy 函式
  避免多 worker 重複載模型

### 2. 前後端 pose canonical schema

**來源**：PR 內 `pose-client.ts` + `pose_infer_server.py` 之間的 wire format

**提取要點**：
- track_id 跨幀追蹤
- keypoints 統一座標系（normalized 0-1 vs pixel）
- base64 annotated image 回傳（debug 用）

**整合到本地**：
- 對齊 `docs/contracts/interaction_contract.md` 的 `/event/pose_detected` schema
- **檢查**：v2.0 contract 是否已有對應欄位？沒有的話評估是否要 v2.1 增訂

### 3. PosePanel UI 元件

**來源**：PR 內 `frontend/components/pose/*.tsx`

**整合到本地**：
- 整合到 `pawai-studio/frontend/components/pose/`
- UI 元件設計乾淨可用

---

## ❌ 不要的東西

- repo 根空殼 `package-lock.json`（誤導 CI/Vercel）
- 原檔 `test_pose.py` 的 import-time 副作用（`mp_pose.Pose(...)` 寫在 module 底部）
- `use-pose-stream.ts:191` 的 `useEffect` 把 `lastResult` 放 deps —
  會導致 setInterval 每幀 tear-down 重建。**要改用 ref 讀取 lastResult**
- `decisionIntervalMs: 1000` + `captureIntervalMs: 150` → ~85% 推論被丟掉，
  浪費 Python server CPU。可考慮前端拿到 result 再決定畫不畫
- `pawai-studio/frontend/components/pose/` 混搭 .py 檔（monorepo 邊界破壞），
  Python 應搬到 `services/pose_infer/` 或類似位置

---

## 實作優先級

| 優先級 | 項目 | 估時 |
|-------|------|------|
| P0 | 姿勢分類細則搬 `pose_classifier.py`（lazy init + 改名） | 30 min |
| P1 | UI PosePanel 整合 | 1 hr |
| P2 | wire format 對齊 contract | 30 min（需 review contract） |

---

## 注意事項

- 提取時不要改現有節點的 topic 名稱
- 改完後跑 `colcon build --packages-select vision_perception` + `bash scripts/clean_speech_env.sh`
