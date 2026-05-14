# PR #38 手勢辨識功能提取計畫

**日期**：2026-04-25
**來源 PR**：https://github.com/roy4222/PawAI/pull/38 (Yamikowu)
**整體 PR review 結論**：REQUEST_CHANGES（不能直接 merge）— 詳見 `docs/mission/meetings/2026-04-25.md`
**本檔目的**：列出 PR 內**值得提取**到本地程式碼的功能，以及實作時要注意的事

---

## 可提取的功能

### 1. 揮手偵測算法（最有價值）

**來源**：PR 內 `gesture-wu/gesture_recognition.py` 的 `_is_waving()` 函式

**提取要點**：
- 對手部位置做 smoothing（避免單幀抖動誤判）
- direction-change 計數（左右擺動次數）
- 三個閾值：
  - 範圍閾值：0.10（手部 x 軸移動範圍）
  - 轉折次數：3 次（左右轉換）
  - 開掌比例：70%（要求至少七成幀數是張開的手掌）
- `gesture_history = deque(maxlen=10)` 做時間窗

**整合到本地**：
- 目標檔案：`vision_perception/vision_perception/gesture_dynamic.py`（新建或補強現有 wave 偵測）
- 補強既有的 vision_perception_node 揮手偵測

### 2. gesture-panel UI 元件

**來源**：PR 內 `pawai-studio/frontend/components/gesture/gesture-panel.tsx`

**提取要點**：
- mode badge（顯示當前手勢模式）
- Go2 action badge（顯示對應觸發的動作）
- UI 設計乾淨可直接用

**整合到本地**：
- 整合到 `pawai-studio/frontend/components/gesture/`

---

## ❌ 不要的東西

- 整個 `gesture-wu/gesture_recognition.py` standalone 腳本
  - port 寫 `localhost:8080` 但 mock_server 是 `8001` → **永遠連不上**
  - 直接打 HTTP `mock/trigger` 繞過 ROS2 contract
- enum 違反 contract：原 PR 用 `Palm / Fist / OK`，但 contract 規定是
  `wave / stop / point / ok / thumbs_up`（小寫、特定字串）
  → **整合 UI 時 enum 必須改對齊 contract**
- `video_streamer_thread` 的 reconnect 迴圈（line 284-297）：
  - bare except 吞所有錯誤
  - daemon thread 永遠不會退出
  - frame 被丟掉但看起來正常
- `mock_server.py` video relay（line 469-484）：unbounded fan-out
  - 死掉的 client 留在 `video_clients[source]`，list 持續長大
  - `send_bytes` 失敗不會 raise，被 `except: pass` 吞掉
- gesture_history 用 `max(set(...), key=...count)` 是 O(n²)（n=10 還能接受但代碼味重）
- `Copyright (c) 2024, RoboVerse community` header（放錯專案）

---

## 實作優先級

| 優先級 | 項目 | 估時 |
|-------|------|------|
| P0 | `_is_waving()` 算法搬 `gesture_dynamic.py` | 30 min |
| P1 | gesture-panel UI 整合 + enum 對齊 contract | 1 hr |
| P2 | （無）—— 動態手勢只先做揮手，過來/轉圈下次再加 |

---

## 注意事項

- 提取時 enum 必須對齊 `docs/contracts/interaction_contract.md` v2.0
- 動態手勢的 contract 已凍結 v2.0，新增手勢需走 v2.1 流程（可參考 `docs/pawai-brain/perception/gesture/research/` 中
  v2.1 OK→Fist 提案的格式）
- 改完後 `colcon build --packages-select vision_perception` + 對 `scripts/run_vision_case.sh` 跑一次
