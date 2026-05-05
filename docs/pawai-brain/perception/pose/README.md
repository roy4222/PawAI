# 姿勢辨識

> Status: current

> MediaPipe Pose 辨識人體姿勢，跌倒偵測觸發緊急警報。

## 狀態卡

| 項目 | 值 |
|------|---|
| 狀態 | **上機驗收 4/4 PASS**，fallen 可關閉 |
| 版本/決策 | MediaPipe Pose (CPU 18.5 FPS) |
| 完成度 | 95% |
| 最後驗證 | 2026-04-04（standing/sitting/fallen→EMERGENCY/恢復→IDLE 全 PASS） |
| 入口檔案 | `vision_perception/vision_perception/pose_classifier.py` |
| 測試 | `python3 -m pytest vision_perception/test/test_pose_classifier.py -v` |

## 啟動方式

```bash
ros2 launch vision_perception vision_perception.launch.py \
  inference_backend:=rtmpose use_camera:=true \
  pose_backend:=mediapipe
```

## 核心流程

```
D435 RGB → vision_perception_node
    ↓
MediaPipe Pose（CPU, COCO 17-point）
    ↓
pose_classifier.py（hip/knee/trunk 角度判定）
    ↓
/event/pose_detected（JSON: pose, confidence）
    ↓
interaction_executive_node → fallen = EMERGENCY
```

## 支援姿勢（MOC 7 種全部 Active，5/5 落地）

| 姿勢 | 判定邏輯 | 觸發 Skill | 台詞範本（demo bridge）| 狀態 |
|------|---------|---|---|:---:|
| standing | hip_angle > 155° + knee_angle > 155° | （預設，不觸發）| — | Active |
| akimbo ✨ | standing + 雙手腕近髖（< hip_width × 0.6）+ 雙肘 60-135° | `akimbo_react` | 「你看起來很有架式喔！」（暫定）| **Active** (5/5) |
| sitting | 100° < hip_angle < 150°, trunk < 35° | `sit_along` | 「會不會太累？」 | Active |
| crouching | hip_angle < 145°, knee_angle < 145°, trunk > 10° | （互動 say）| 「我在這裡喔」 | Active |
| bending | trunk > 35°, hip_angle < 140°, knee_angle > 130° | `careful_remind` | 「請小心喔」 | Active |
| knee_kneel ✨ | 一膝 y ≥ 髖 y + 該膝 < 100° + 另膝 > 130° | `knee_kneel_react` | 「需要我幫忙嗎？」（暫定）| **Active** (5/5) |
| fallen | bbox_ratio > 1.0 AND trunk > 60° AND vertical_ratio < 0.4 | `fallen_alert`（EMERGENCY）| 「{name}，偵測到跌倒，請注意安全！」 | Active（可關）|

> 5/5 變更：akimbo 與 knee_kneel 從 Hidden TBD 升級為 Active，幾何規則已落地在 `vision_perception/vision_perception/pose_classifier.py:_is_akimbo` / `_is_knee_kneel`。
> akimbo 在 standing 之後檢測（standing 變體）；knee_kneel 在 crouching 之前檢測（避免被「兩膝彎曲」吃掉）。
> 5/5 實機初測：分類效果整體仍待 tune（threshold / vote / scale-invariant ratio），詳見 `~/.claude/projects/.../memory/project_pose_classifier_tuning_0505.md`。

## 操作限制與已知問題

- **有效範圍**：D435 前方約 **4-5m** 以內
- **僅支援單人追蹤**：多人時 MediaPipe 只追蹤一人
- RTMPose balanced mode GPU 91-99%（備援方案，主線用 MediaPipe CPU 0%）
- ~~正面站姿被誤判為 fallen~~ — **已修復（4/3）**：新增 `vertical_ratio` guard，用 shoulder-hip 垂直差 / torso 長度作為相對尺度（閾值 0.4），不受距離影響
- 跌倒偵測可能誤報（椅子上趴下）
- 幽靈跌倒偵測：投票 buffer（20 幀多數決）已大幅降低誤報，但未完全消除。**4/8 會議確認幻覺仍頻繁**（無人時鎖定衣架等物體判為 fallen）
- **`enable_fallen` 已參數化**（4/6）：Demo 可關閉跌倒偵測避免誤報
- 因專題已不以老人照護為主題，**跌倒偵測功能可考慮弱化**
- 側面坐姿 hip_angle 和 trunk_angle 計算偏差，Demo 時建議正面面向攝影機

## Event Schema（v2.0 凍結）

```json
{
  "stamp":       1710000000.123,
  "event_type":  "pose_detected",
  "pose":        "standing",
  "confidence":  0.92,
  "track_id":    1
}
```

## Pose → Skill Mapping（5/12 Sprint）

| 姿勢 | Brain 觸發 | Cooldown | Demo Scene |
|---|---|:---:|---|
| sitting | demo bridge → 「會不會太累？」TTS（say only）| 5s | 互動段 |
| crouching | demo bridge → 「我在這裡喔」TTS | 5s | 互動段 |
| bending | demo bridge → 「請小心喔」TTS | 5s | 互動段 |
| fallen | demo bridge → 「{name}，偵測到跌倒，請注意安全！」（high priority）| **10s** | Scene 8 / 守護 |
| akimbo | demo bridge → 「你看起來很有架式喔！」（暫定）| 5s | 互動段（5/5 升 Active）|
| knee_kneel | demo bridge → 「需要我幫忙嗎？」（暫定）| 5s | 互動段（5/5 升 Active）|

> 站立 standing 不觸發任何 skill（純 baseline 狀態）。
> 全部走 `vision_perception/vision_perception/event_action_bridge.py` POSE_TTS_MAP 的 demo bridge — 只 publish `/tts`，不發 Go2 motion。長期路徑改為正規 Brain skill（`sit_along` / `careful_remind` / `fallen_alert` / `akimbo_react` / `knee_kneel_react`）走 `/brain/proposal` → `/skill_result`，列為 post-demo Stretch。

### `fallen_alert` 接 face name（5/5 對齊）

`fallen_alert` 的 say_template 引用 `{name}` 變數：「**{name}**，偵測到跌倒，請注意安全」。`{name}` 來源：

1. Brain 收 `pose_detected: fallen` 事件時，查 `/state/perception/face` 最近一次 `identity_stable` 的 `stable_name`
2. 若無人臉識別（unknown / 無人臉視野）→ fallback「偵測到跌倒，請注意安全」（無稱呼）
3. 同樣的 `{name}` 變數也用在 face/README.md 的 `greet_known_person`，模板 source 統一在 `interaction_executive` skill registry

> Detail: `docs/contracts/interaction_contract.md` v2.5 say_template 章節。

## 下一步

- [x] fallen → EMERGENCY 整合進 executive（已 4/4 PASS）
- [x] **akimbo / knee_kneel 判定演算法**（5/5 commit `ca32655`，`pose_classifier._is_akimbo` / `_is_knee_kneel` + demo bridge TTS template）
- [x] **B4-5 fallen_alert + {name} 全鏈路**（5/5 commit `4f638ae`，event_action_bridge demo bridge 訂閱 `/state/perception/face` cache 最近 stable name + format("{name}")）
- [ ] **7 姿勢實機 tuning**（5/5 user 回報分類效果不穩；threshold / vote / scale-invariant ratio 三方向）— 詳見 `~/.claude/projects/-home-roy422-newLife-elder-and-dog/memory/project_pose_classifier_tuning_0505.md`
- [ ] **5/12 Sprint Active 7 上機驗證**：sitting / crouching / bending / fallen-with-name / akimbo / knee_kneel / standing 各 3 次穩定觸發
- [ ] **demo bridge 退場路徑**：把 pose→/tts 改為正規 Brain skill（`sit_along` / `careful_remind` / `fallen_alert` 等）走 `/brain/proposal` → `/skill_result`（post-demo, Stretch P1）
- [ ] 跌倒偵測幻覺（無人時鎖定衣架）— 投票 buffer 改 30 幀 OR 改 movement-based filter

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs DWPose）、benchmark 比較、跌倒偵測研究 |
