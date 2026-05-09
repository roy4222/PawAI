# Pose Interaction Layer — 設計規格

> **Status**: draft
> **Date**: 2026-05-10
> **Spec ID**: Spec 3 of 6（demo-quality roadmap）
> **Scope**: 把姿勢辨識從現有 3 種（standing / sitting / fallen）擴充為 7 種，並對應到 skill 觸發 + 安全處理。
> **執行視窗**：demo 後（pose 誤觸風險高，demo 前不擴）
> **Owner**: Roy
> **依據**：
> - `docs/contracts/interaction_contract.md`（v2.0 pose enum）
> - `docs/pawai-brain/perception/pose/README.md`
> - `vision_perception/vision_perception/pose_classifier.py`

---

## 1. 範圍：7 種姿勢 + 對應行為

| 姿勢 | TTS 反應（多變體）| 對應 skill | 安全處理 |
|---|---|---|---|
| 1. 站著 | 無（ambient state）| — | — |
| 2. 坐下 | 「會不會太累」+ 變體池 | `sit_along`（Go2 一起趴下）| — |
| 3. 蹲下 | 「我在這裡喔」+ 變體池 | 可綁互動動作 | — |
| 4. 彎腰 | 「請小心喔」+ 變體池 | 可綁互動動作 | depth 監控 |
| 5. 跌倒 | **「{name} 跌倒，請注意安全」**（人臉融合）| `fallen_alert` | **stop_move 立刻 + 30s cooldown** |
| 6. 雙手叉腰 | 「喔～你叉腰啦」+ 變體池 | `akimbo_react`（已 hidden）| — |
| 7. 單膝跪地 | 「你跪下做什麼？」+ 變體池 | `knee_kneel_react`（已 hidden）| — |

---

## 2. 非目標

❌ 不做：
- pose sequence（站 → 蹲 → 跌倒 視為連續事件）
- 多人同時 pose 偵測（demo 一人主角即可）
- pose-driven nav（蹲下 → 狗自動靠近）
- 床上 / 沙發上的躺平偵測（angle / context 太複雜）

---

## 3. 跌倒人臉融合（核心設計）

### 3.1 問題
現況跌倒只說「偵測到跌倒」，不知道是誰。Roy 訴求「擴大辨識範圍」，要說「{name} 跌倒」。

### 3.2 設計
```
fallen_event 進來
    ↓
brain_node._on_pose_fallen
    ↓
查 _recent_face_identity（5s 內最近一次人臉識別）
    ↓
分支：
  a. 有 identity（roy/grama）→ TTS = f"{name} 跌倒，請注意安全"
  b. 無 identity → TTS = "有人跌倒，請注意安全"
    ↓
emit fallen_alert plan（priority=ALERT）
    ↓
Executive：clear queue → push_front(stop_move) → SAY
```

### 3.3 風險：人臉誤識別會讓 TTS 喊錯人
**對策**：face confidence ≥0.7 才注入名字；否則用通用 fallback。

---

## 4. 誤觸抑制（pose 比 gesture 更危險）

| 風險 | 場景 | 對策 |
|---|---|---|
| 推車 / 椅子被當跌倒 | demo 場地常有 | 5s ankle-on-floor gate（已實作 `pose_classifier.py:165-167`）|
| 蹲下被當跌倒 | crouching → fallen 切換太敏感 | 加角度差 30° + 持續 2s |
| 彎腰被當跌倒 | 撿東西、繫鞋帶 | hip angle ≥60° → 仍是 standing |
| 對話中跌倒誤觸 | TTS 被打斷 | 對話中 fallen 偵測仍發 plan，但 priority=ALERT 中斷 |

---

## 5. 多變體 TTS 池（沿用 Spec 1 機制）

每個 pose 的 TTS 走變體池（不是 hardcoded）：

| Pose | text_pool 範例（5-8 條/組）|
|---|---|
| sitting | 「會不會太累」/「累了喔」/「坐下來休息一下也好」/「我也趴下來陪你」... |
| crouching | 「我在這裡喔」/「你在看什麼」/「也讓我看看」... |
| bending | 「請小心喔」/「東西掉了嗎」/「我幫你看看」... |
| akimbo | 「喔～你叉腰啦」/「在生氣嗎」/「想做什麼呢」... |
| knee_kneel | 「你跪下做什麼」/「在幹嘛」/「需要幫忙嗎」... |

**選擇邏輯**：跟 Spec 1 共用 `_text_pool_history` deque，避免最近 3 次重複。

---

## 6. 安全閘門（Critical）

```
pose_fallen → ALERT priority → 中斷任何進行中的 plan + stop_move
其他 pose → SKILL priority → 排隊執行
```

**絕對不能**：跌倒 plan 跟其他 plan 並行。

---

## 7. 驗收

| 項目 | 標準 |
|---|---|
| 7 種 pose 各跑 10 次 | ≥7/10 正確 classify |
| 跌倒人臉融合 | Roy 跌倒 → 「Roy 跌倒，請注意安全」≥80% |
| 推車誤觸 | 場地推 1 圈 → 偽 fallen ≤1 次 |
| TTS 不重複 | sitting 連續 5 次入鏡 → 5 句不同 |
| 跌倒中斷對話 | 講長故事中跌倒 → 立刻 stop + ALERT |

---

## 8. 實作分階段（demo 後）

| Phase | 內容 | 工時 |
|---|---|---|
| 1 | pose_classifier 擴 4 新姿勢（蹲/彎/叉腰/跪）| 1d |
| 2 | brain_node pose handler + 變體池 | 0.5d |
| 3 | 跌倒人臉融合（_recent_face_identity 查詢）| 0.5d |
| 4 | 誤觸抑制 gate 調參 | 1d（含場地測）|
| 5 | 7 種驗收 | 0.5d |

**總計**：3.5 天（demo 後做）

---

## 9. 後續 spec 銜接

- Spec 1：自我展示中「我看得懂姿勢」對應本 spec
- Spec 5：跌倒可整合 nav（自動靠近確認）但不做（demo 不開 nav）
