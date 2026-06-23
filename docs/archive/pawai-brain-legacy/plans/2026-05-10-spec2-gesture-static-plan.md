# Spec 2 Lightweight Plan — Gesture Interaction Layer (P0 Static 6)

> **Status**: ready-to-execute
> **Date**: 2026-05-10
> **依據 spec**：[`2026-05-10-spec2-gesture-interaction-design.md`](../specs/2026-05-10-spec2-gesture-interaction-design.md)
> **範圍**：P0 靜態 6 手勢（Palm / Fist / Index / OK / Thumb / Peace）。**動態 3 種（Circle / Wave / ComeHere）不在這份 plan**。
> **總工時**：2 天
> **執行視窗**：Spec 1 完成後若 demo 前還有時間（5/14–15）。可砍。
> **依賴**：Spec 1 §6.3 `text_pool` 機制完成（gesture 觸發的 SAY 共用 pool）。
> **Plan 用途**：輕量任務清單。Spec 已寫得夠細，本 plan 只做執行序列 + 驗收 + 風險對策。

---

## 1. 任務清單（5 phase, 2 天）

| # | Task | 工時 | 驗證 | 必做？ |
|---|---|:---:|---|:---:|
| T1 | OK gesture keypoint rule 風險評估（5 場景測試） | 0.3d | 偽觸發率 ≤2/60s 自然動作 | Y（gate） |
| T2 | brain_node `GESTURE_TO_SKILL` 擴充 mapping | 0.3d | unit test：6 gesture 各對應正確 skill | Y |
| T3 | `enter_mute_mode` / `enter_listen_mode` 啟用（bucket: hidden → active） | 0.2d | smoke: fist/index 觸發成功 | Y |
| T4 | 誤觸抑制：confidence ≥0.8 + 持續 3 frames + Index 1.5s | 0.5d | 60s 自然動作偽觸發 ≤2 | Y |
| T5 | P0 6 gesture 驗收（Roy + grama 各 10×6） | 0.5d | ≥8/10 正確觸發 / gesture | Y |
| T6 | OK gesture demo fallback 文件化（語音 OK 確認備援） | 0.2d | runbook 落檔 | Y |

---

## 2. 執行細節

### T1：OK keypoint rule 風險評估（spec §3.1 review 6 fix）

**為什麼先做**：spec 把 OK 標為 high risk。如果 keypoint rule 偽觸發太高，**T2 之後的工作都不該做**，改成「demo 用語音 OK 確認」。

**測試**：
```bash
# Jetson 上
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe gesture_backend:=recognizer max_hands:=2

# 5 場景各做 60s，記偽觸發次數：
# A. 手放下休息（手指自然彎曲）
# B. 拿杯子 / 手機（拇指食指距離近）
# C. 揮手過渡（hand transit through OK shape）
# D. 距離 1.5m / 2.5m / 3m 各 60s
# E. 半遮擋（手部 50% 在鏡頭外）
```

**Gate**：
- ✅ 5 場景偽觸發加總 ≤10 → 繼續 T2-T5
- ❌ 偽觸發 >10 → **跳過 T2 OK mapping**、走 spec §3.1 demo fallback（語音 OK 確認）；其他 5 gesture 仍可做

### T2：brain_node mapping 擴充

檔案：`interaction_executive/interaction_executive/brain_node.py:541` 附近 `_GESTURE_CONFIRM`

```python
# 現有：thumbs_up → wiggle, peace → stretch（confirm 路徑）
# 新增：
GESTURE_TO_SKILL = {
    "palm": ("stop_move", "direct"),         # 安全優先，無需 confirm
    "fist": ("enter_mute_mode", "direct"),
    "index": ("enter_listen_mode", "direct"),
    "thumbs_up": ("wiggle", "confirm"),       # 沿用既有
    "peace": ("stretch", "confirm"),          # 沿用既有
    "ok": ("__confirm_pending__", "system"),  # 觸發 PendingConfirm 而非 mapping
}
```

注意：`wave_hello`（揮手）**不在 P0**（屬動態）。`wave` event 若由靜態 backend 誤發 → 視為雜訊 ignore。

### T3：啟用 hidden skills

檔案：`skill_contract.py`

- `enter_mute_mode`：bucket = `hidden` → `active`，並確認 SAY step（fist 觸發後說什麼）走 P3.1 `SAY_TEXT_POOLS`（Spec 1 完成後共用）。
- `enter_listen_mode`：同上。

### T4：誤觸抑制

`vision_perception_node` 或 `gesture_recognizer_backend` 端：
- 全 6 gesture：confidence ≥ 0.8 + 連續 3 frames 同 label 才 emit event
- Index：額外加 1.5s 持續時長 gate（容易與「指東西」衝突）

### T5：驗收（spec §6 P0）

```bash
# Foxglove 監看 /event/gesture_detected
# Roy 對鏡頭做每個手勢 10 次，記 confidence + 是否觸發 skill
# grama 同樣
```

通過條件：
- 每 gesture ≥8/10 正確觸發
- 60s 自然動作偽觸發 ≤2

### T6：demo fallback 文件化

`docs/runbook/gesture-demo-fallback.md`（新檔，1 段話）：
- 若 demo 當天 OK 偽觸發率高 → 改用語音「OK」確認（PendingConfirm 已有 voice path）

---

## 3. Rollback 條件

| 觸發 | 動作 |
|---|---|
| T1 OK 偽觸發 >10 | 跳 T2 OK mapping、整體仍可 demo（5 gesture） |
| T5 任一 gesture <6/10 | 該 gesture 從 demo 流程拿掉，記入 known issue |
| T4 誤觸抑制過嚴 → 真觸發率掉到 <6/10 | 放寬 frame gate（3→2），重做 T5 |

---

## 4. 不在這份 plan 的事

❌ 動態 3 gesture（Circle / Wave / ComeHere）— spec §4.4 demo 後做
❌ `dance` / `follow_person` skill 啟用 — disabled
❌ 自定義手勢註冊 — spec §2 已排除
❌ 跨手勢 sequence — spec §2 已排除

---

## 5. 與 Spec 1 / Spec 5 的銜接

- Spec 1 完成後 → fist / index 觸發 skill 的 SAY 走 `SAY_TEXT_POOLS`（共用，不重複實作）
- Spec 5 demo 後 → ComeHere（P1）才會跟導航整合

---

**End of Spec 2 Lightweight Plan**
