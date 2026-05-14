# N5 Scene Perception Design

**Date**: 2026-05-11
**Target**: 5/18 demo
**Status**: **Implemented** — see commits `631b98b` (N5) + `0f13d98` (N5.1). This document is the after-the-fact design record; the in-repo behaviour matches §Implementation. Use this spec to understand *why* perception layers split the way they do when revisiting trade-offs.

**一句話**：把 pose / gesture 加進 brain 的 perception cache，讓 PawAI 能回答「我看到什麼」「我在幹嘛」這類**整合多模態**的問題；不重構 graph、不加大 loop。

---

## Context

5/11 night live demo 後 Roy 反饋：

> 我問他看到什麼 其實是希望他可以更加詳細描述她看到什麼 畢竟他有手勢 姿勢 辨識物體 人臉的功能阿
>
> 我剛剛其實坐在電腦桌前用電腦 但她完全沒猜出來

根因：N3 只 inject `[最近看到]`（物體 only）+ `[眼前的人]`（face）。`/event/pose_detected` / `/event/gesture_detected` brain 沒訂 → LLM 無法看到姿勢手勢做 scene reasoning。同時 N3 把 `person` class 灌進 `[最近看到]` 產生「黑色的人」這種怪句子，HSV color 偶爾誤判（藍色電視）拉低整體準確度。

對齊 demo 目標 v2 `LLM 行為目標` 第 8 條：「可以根據上下文延伸對話」+ §[1:30] §[3:30] 兩段需要交叉融合。

---

## Three Perception Layers — 不同 cache 語意

| 層 | 語意 | Cache 策略 | 過期 |
|---|---|---|---|
| **Object** | recent evidence（持續觀察） | recent_window 30s + class-dedup | 過期丟 |
| **Pose** | last known state（身體姿勢） | last_known 一筆 + age_s | **永不過期** |
| **Gesture** | short-lived event（剛剛做的） | recent_window 8s + dedup by (gesture, hand) within 5s | 過期丟 |

**設計依據**：pose 是「持續狀態」（坐著就一直坐著），event 卻 sparse（vision_perception 只在 pose 改變時發），不能用 30s window 否則 5 分鐘沒新事件就失憶。gesture 反之是「事件性」（揮手就揮一次），舊事件當前狀態會誤導。

---

## Implementation

### File 1: `pawai_brain/pawai_brain/capability/world_snapshot.py`

新增屬性：
```python
self._last_pose: dict | None = None   # {"pose": str, "confidence": float, "ts": float}
self._recent_gestures: deque = deque(maxlen=4)  # 8s window at read time
```

新增方法：
- `apply_pose_event_json(raw)` — parse `{pose, confidence, stamp/timestamp}`, 用 `time.time()` 當 cache ts（不信上游時鐘），overwrite `_last_pose`
- `apply_gesture_event_json(raw)` — parse `{gesture, confidence, hand}`, dedup by `(gesture, hand or "")` 5s 內視為同筆只更新 ts
- `get_last_pose() -> dict | None` — return `{pose, age_s, confidence}` or None
- `get_recent_gestures(window_s=8.0) -> list[dict]` — `[{gesture, age_s, hand, confidence}, ...]` 過期丟

修改既有 `apply_object_detected_json`：
- **person filter**：`class_name == "person"` skip（人由 face 處理）
- **color confidence gate**：`color_confidence < 0.6 → color = None`（不講顏色 > 講錯顏色）

`to_dict()` 加：
```python
"last_pose": {...} | None
"recent_gestures": [...]
```

### File 2: `pawai_brain/pawai_brain/nodes/world_state_builder.py`

`snap.to_dict()` 已含新欄位 → 自動流到 `state["world_state"]`。trace detail 擴：
```
"detail": f"{period} {time_str} objs={no} pose={p} gst={ng} spk={s}"
```

### File 3: `pawai_brain/pawai_brain/conversation_graph_node.py`

**新 module-level dicts**：
```python
_POSE_ZH = {"standing":"站著","sitting":"坐著","fallen":"跌倒",
            "crouching":"蹲著","bending":"彎腰",
            "akimbo":"雙手叉腰","knee_kneel":"單膝跪地"}
_GESTURE_ZH = {"palm":"手掌","fist":"握拳","index":"食指","ok":"OK",
               "thumbs_up":"比讚","peace":"比 V","wave":"揮手",
               "circle":"畫圈","come_here":"勾手"}
```

**新 helper（age-gated wording for pose）**：
```python
def _format_pose_line(last_pose) -> str | None:
    if not last_pose: return None
    zh = _POSE_ZH.get(last_pose["pose"], last_pose["pose"])
    age = last_pose["age_s"]
    if age < 15:
        return f"[目前姿勢] 你現在看起來是{zh}"
    if age < 120:
        return f"[最近姿勢] 我最近看到你是{zh}（{int(age)} 秒前）"
    return f"[歷史姿勢] 我最後一次看到你是{zh}（{int(age)} 秒前），需要再確認"

def _format_gesture_line(gestures) -> str | None:
    # 取前 3 個，翻譯、age 顯示，unknown enum skip
    ...
```

**`_SCENE_HINT` 常數**（正向 framing）：
```
[scene_hint] 使用者在問你現場狀況或自己正在做什麼。
請整合 [眼前的人]、姿勢、手勢、最近看到的物體，做 1-3 句場景描述。
可以做合理推論，例如看到鍵盤、滑鼠、螢幕或筆電，加上使用者坐著，
可以推測他可能正在用電腦。不確定時用「看起來像」；沒看到的不要硬猜。
```

**Subscribe 2 個新 topic**：`/event/pose_detected` + `/event/gesture_detected`，callback 呼叫 snapshot 對應 apply 方法。

**`_on_reset_context` 清**：`_last_pose = None`、`_recent_gestures.clear()`、object cache 也 reset（新對話乾淨開始）。

**`_build_user_message` 插入順序**：
```
[語音/文字] / [環境] / [眼前的人] / [目前/最近/歷史姿勢] / [剛剛手勢] / [最近看到] / [scene_hint] / [能力 runtime] / [intro_scaffold] / [mode_hint]
```

scene_hint 注入條件：`mode == "scene_query"` 才出。

**Trace `model` 欄位**（順手加，#6 部分需求）：
- `_publish_traces` payload 加 `"model": self.openrouter_gemini_model`
- frontend Trace Drawer 已可吃 `model` 欄位（檢查 `pawai-studio/frontend/contracts/types.ts`，加進 `ConversationTracePayload` interface）

### File 4: `pawai_brain/pawai_brain/nodes/mode_classifier.py`

加 `scene_query` mode（**在 capability_question 之前**）：
```python
"scene_query",
r"看到(什麼|啥|哪些東西|哪些物品)"
r"|看見(什麼|啥|哪些東西|哪些物品)"
r"|我現在在(做什麼|做啥|幹嘛|幹什麼)"
r"|我現在是(站著|坐著|蹲著|躺著)"
r"|我.*看起來.*(怎樣|如何|像在做什麼)"
r"|(猜|猜猜).*我.*(做什麼|做啥|幹嘛)"   # 「猜猜我在做什麼」也命中（user review 修正）
r"|(現場|這邊|這裡).*(怎麼樣|怎樣|有什麼|什麼樣)"
```

注意：**避免裸「哪些」**（會誤吃「你想看到哪些功能」→ capability_question）。

---

## Tests（28 個 new tests）

| 檔案 | 數量 | 範圍 |
|---|---|---|
| `test_world_snapshot.py` | +8 | pose overwrite / never expire / gesture dedup / 8s window / person filter / color conf gate (drop & keep) / to_dict |
| `test_user_message_builder.py` | +9 | pose age 三段措辭 / gesture inject / gesture unknown enum skip / person filter / color drop / scene_hint inject / no scene_hint when not scene_query |
| `test_mode_classifier.py` | +8 | 6 正例（含「猜猜我在做什麼」）+ 2 反例（「你想看到哪些功能」→ capability_question / 「你覺得我還可以」→ chat） |
| `test_conversation_graph_node.py` | +3 | _on_pose_event / _on_gesture_event / reset_context 清 |

---

## Verification（Jetson smoke）

```bash
~/sync once
ssh jetson-nano 'cd ~/elder_and_dog && colcon build --packages-select pawai_brain --symlink-install'
bash .claude/skills/brain-studio-lane/scripts/cleanup.sh
bash .claude/skills/brain-studio-lane/scripts/start.sh demo
```

3 個 Studio chat 句測：
1. **`你現在看到什麼？`** → mode=`scene_query`，reply 整合姿勢 + 物體 + 人（不講「人」當物體）
2. **`我現在在幹嘛？`** → 拉 `[目前姿勢] 坐著` + 推論 keyboard/laptop → 「你看起來在用電腦」
3. **`猜猜我在做什麼？`** → 同上路徑

**Go criteria**：
- ✅ 三句都觸發 `scene_query` mode（trace `mode_classify` detail）
- ✅ reply 包含至少 2 種 perception（姿勢 + 物體 OR 物體 + 手勢）
- ✅ 不再出現「黑色的人」這種把 person 當物體的句子
- ✅ Color 低 confidence 時不講顏色（trace `world_state` detail `objs=N` 確認 inject）

**TTS Piper fallback smoke**（順手做，#7 需求）：
- 拔網路或 `LLM_ENDPOINT=http://127.0.0.1:1/` → 確認 edge-tts 死後 piper 接得起來
- 不改代碼，純驗證 `tts_node.py:1064-1091` 既有 chain 真的 work

---

## Out of Scope（凍結，5/18 後解鎖）

- **OK confirm bypass bug**（user 已標低優先）
- **Model switcher UI 按鈕**（demo 前用 env override `PAWAI_LLM_MODEL=...`，UI 凍結）
- **Idle / 待機聊天 skill**
- **HSV 顏色調參**（屬 object_perception，本 spec 不動）
- **Pose enum 擴張**（vision_perception 已 freeze）
- **跟隨 / 自主巡邏 / 動態繞行**（已 frozen-backlog）

---

## References

- 5/11 live demo log（user 5/11 14:00-15:00 訊息）
- `docs/runbook/demo-frozen-backlog.md` — Hotfix 紀律
- `docs/runbook/demo_script.md` §[2:30] §[3:30] — 劇本反推
- `pawai_brain/pawai_brain/capability/world_snapshot.py` N3 既有 `_recent_objects` pattern
- 五月 N3-N4 commits（561d6ab → afd3fcd → f9988bd）
