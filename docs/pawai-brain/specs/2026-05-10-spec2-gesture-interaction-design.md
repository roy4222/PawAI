# Gesture Interaction Layer — 設計規格

> **Status**: draft
> **Date**: 2026-05-10
> **Spec ID**: Spec 2 of 6（demo-quality roadmap）
> **Scope**: 把手勢辨識從現有 4 種（OK/thumbs_up/palm/peace）擴充為 9 種完整 mapping，並對應到 skill 觸發。
> **執行視窗**：demo 前若有時間做靜態 6 種；動態 3 種 demo 後做（加分）
> **Owner**: Roy
> **依據**：
> - `docs/contracts/interaction_contract.md`（v2.0 gesture enum）
> - `docs/pawai-brain/perception/gesture/README.md`
> - `vision_perception/vision_perception/gesture_recognizer_backend.py`

---

## 1. 範圍

### 1.1 9 種 gesture mapping（user 需求）

#### 系統與基礎控制（4）
| Gesture | 行為 | 對應 skill |
|---|---|---|
| 🖐️ Palm | 全面暫停 | `system_pause` / `stop_move` |
| 👊 Fist | 靜音模式（坐下 + 關聲）| `enter_mute_mode` |
| ☝️ Index | 監聽模式（站立 + 開 ASR）| `enter_listen_mode` |
| 👌 OK | 二次確認 | (現有 PendingConfirm 機制) |

#### 情感與趣味互動（3）
| Gesture | 行為 | 對應 skill |
|---|---|---|
| 👍 Thumb (Thumbs_up) | 開心 → 搖屁股 | `wiggle`（needs_confirm）|
| ✌️ Peace | 放鬆 → 伸懶腰 | `stretch`（needs_confirm）|
| 🔄 Circle | 跳舞（**動態手勢**）| `dance`（目前 disabled）|

#### 動態追蹤與感應（2）
| Gesture | 行為 | 對應 skill |
|---|---|---|
| 👋 Wave | 揮手回應 | `wave_hello` |
| 🫴 ComeHere | 召喚跟隨 | `follow_person`（目前 disabled）|

### 1.2 demo 前範圍（**P0**）：靜態 6 種

P0：**Palm / Fist / Index / OK / Thumb / Peace**
理由：MediaPipe Gesture Recognizer 原生支援，無需動態軌跡分析。

### 1.3 demo 後（**P1 加分**）：動態 3 種

**Circle / Wave / ComeHere** 需要時間軸分析（連續 N frames 軌跡判斷），現有 backend 不支援，需擴充。

---

## 2. 非目標

❌ 不做：
- LLM 自然度改善（→ Spec 1）
- 自定義手勢註冊（家屬訓練自己的手勢）
- 雙手手勢（一隻手 OK + 另一隻指向）
- gesture sequence（OK → Wave 視為連續指令）

---

## 3. 現況評估

### 3.1 已有 backend
`gesture_recognizer_backend.py:53` 已有 6 種 enum：`Closed_Fist / Open_Palm / Pointing_Up / Thumb_Up / Thumb_Down / Victory / ILoveYou` + `None`

對應到本 spec 9 種：
| Spec gesture | MediaPipe label | 狀態 |
|---|---|---|
| Palm | Open_Palm | ✅ |
| Fist | Closed_Fist | ✅ |
| Index | Pointing_Up | ✅ |
| OK | (無原生，需手部 keypoint 規則)| ⚠️ 需驗證 |
| Thumb | Thumb_Up | ✅ |
| Peace | Victory | ✅ |
| Circle | (無，需動態) | ❌ |
| Wave | (無，需動態) | ❌ |
| ComeHere | (無，需動態) | ❌ |

### 3.2 已有 skill mapping
`brain_node.py:541` `_GESTURE_CONFIRM`：`thumbs_up → wiggle` / `peace → stretch`

需新增 mapping：
- `palm → system_pause` / `stop_move`
- `fist → enter_mute_mode`
- `index → enter_listen_mode`
- `wave → wave_hello`（這條已有但走 PendingConfirm，要改成直接觸發）

---

## 4. 設計

### 4.1 Contract enum 擴充
`docs/contracts/interaction_contract.md` v2.1：gesture enum 從 7 個擴成 9 個（加 `circle`, `come_here`）。

### 4.2 brain_node gesture handler

```python
# brain_node._on_gesture
GESTURE_TO_SKILL = {
    # 直接觸發
    "palm": ("stop_move", "direct"),
    "fist": ("enter_mute_mode", "direct"),
    "index": ("enter_listen_mode", "direct"),
    "wave": ("wave_hello", "direct"),
    # PendingConfirm（已有）
    "thumbs_up": ("wiggle", "confirm"),
    "peace": ("stretch", "confirm"),
    # OK 不直接 mapping（是 confirm trigger）
    "ok": ("__confirm_pending__", "system"),
    # demo 後（disabled）
    "circle": ("dance", "disabled"),
    "come_here": ("follow_person", "disabled"),
}
```

### 4.3 SkillContract 啟用
- `enter_mute_mode` / `enter_listen_mode`：bucket=hidden → bucket=active
- `dance` / `follow_person`：保持 disabled（demo 不開）

### 4.4 動態手勢（P1）
新增 `dynamic_gesture_backend.py`：
- 滑動視窗 (1.5s, 30 frames @ 20fps)
- Wave：手腕水平振盪 ≥3 次
- Circle：手腕軌跡形成閉合迴圈
- ComeHere：手指彎曲 + 手腕內拉

**精度目標**：靜態 6 種 ≥80% (1.5-3m 距離)；動態 3 種 ≥60%（demo 後加分）

---

## 5. 誤觸抑制

| 場景 | 風險 | 對策 |
|---|---|---|
| 手過渡 → 偽 wave | 高 | confidence ≥0.8 + 持續 3 frames |
| Palm 跟攤手日常動作衝突 | 中 | 必須面向鏡頭（hand orientation 檢查）|
| Fist 跟握拳日常衝突 | 中 | 同上 |
| Index 跟指東西衝突 | 高 | 加 1.5s 持續時長 gate |

---

## 6. 驗收

### P0 靜態 6 種
- 每 gesture 跑 10 次（Roy + grama 各 5 次），≥8 次正確觸發 skill
- 誤觸率：60s 自然動作（聊天揮手、拿東西）→ 偽觸發 ≤2 次
- Foxglove `/event/gesture_detected` 確認 confidence + label 正確

### P1 動態 3 種
- Wave：對鏡頭振 3 次 → 觸發 wave_hello（≥60%）
- Circle：dance 仍 disabled，只看 event 是否發出
- ComeHere：follow_person 仍 disabled，只看 event

---

## 7. 實作分階段（demo 後啟動）

| Phase | 內容 | 工時 |
|---|---|---|
| 1 | OK gesture detection 驗證 + 加 keypoint rule fallback | 0.5d |
| 2 | brain_node mapping 擴充 + skill_contract 啟用 mute/listen | 0.5d |
| 3 | 誤觸抑制（confidence + 持續時長 gate）| 0.5d |
| 4 | P0 6 種驗收（Roy + grama 各跑 10×6）| 0.5d |
| 5 | (P1) 動態手勢 backend | 2d |
| 6 | (P1) Wave/Circle/ComeHere 驗收 | 1d |

**P0 總計**：2 天（demo 前可做）；**P1 總計**：3 天（demo 後）

---

## 8. 後續 spec 銜接

- Spec 1：自我展示中提到「我看得懂手勢」要對應到本 spec 落地的 9 種
- Spec 5：ComeHere → follow_person 跟導航整合
