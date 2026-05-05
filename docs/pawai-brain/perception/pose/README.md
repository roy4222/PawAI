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

## 支援姿勢（MOC 7 種，Demo Active 5 + Hidden 2）

| 姿勢 | 判定邏輯 | 觸發 Skill | 台詞範本 | 狀態 |
|------|---------|---|---|:---:|
| standing | hip_angle > 155° | （預設，不觸發）| — | Active |
| sitting | 100° < hip < 150°, trunk < 35° | `sit_along` | 「會不會太累」（Go2 跟著坐下）| Active |
| crouching | hip < 145°, knee < 145°, trunk > 10° | （互動 say）| 「我在這裡喔」 | Active |
| bending | trunk > 35°, hip < 140°, knee > 130° | `careful_remind` | 「請小心喔」 | Active |
| fallen | bbox_ratio > 1.0 AND trunk > 60° AND vertical_ratio < 0.4 | `fallen_alert`（EMERGENCY）| 「{name}，偵測到跌倒，請注意安全」 | Active（可關）|
| akimbo | wrist 接近 hip，elbow 外展（待實作）| `akimbo_react` | TBD | **Hidden**（5/12 demo 不開）|
| knee_kneel | 一膝彎 < 90°（另膝伸直），膝低於髖 | `knee_kneel_react` | TBD | **Hidden**（5/12 demo 不開）|

> akimbo / knee_kneel 在 sprint design 列為 Hidden bucket（registry 內、Studio grayed-out）— 判定演算法 5/12 demo 後再做，現在 README 先佔位。

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
| sitting | `sit_along`（Go2 跟著坐 + say）| 5s | 互動段 |
| crouching | direct say（互動）| 5s | 互動段 |
| bending | `careful_remind`（say only）| 5s | 互動段 |
| fallen | `fallen_alert`（EMERGENCY: stop + alert say）| **10s** | Scene 8 / 守護 |
| akimbo | `akimbo_react`（Hidden）| — | 未開 |
| knee_kneel | `knee_kneel_react`（Hidden）| — | 未開 |

> 站立 standing 不觸發任何 skill（純 baseline 狀態）。

### `fallen_alert` 接 face name（5/5 對齊）

`fallen_alert` 的 say_template 引用 `{name}` 變數：「**{name}**，偵測到跌倒，請注意安全」。`{name}` 來源：

1. Brain 收 `pose_detected: fallen` 事件時，查 `/state/perception/face` 最近一次 `identity_stable` 的 `stable_name`
2. 若無人臉識別（unknown / 無人臉視野）→ fallback「偵測到跌倒，請注意安全」（無稱呼）
3. 同樣的 `{name}` 變數也用在 face/README.md 的 `greet_known_person`，模板 source 統一在 `interaction_executive` skill registry

> Detail: `docs/contracts/interaction_contract.md` v2.5 say_template 章節。

## 下一步

- [x] fallen → EMERGENCY 整合進 executive（已 4/4 PASS）
- [ ] **5/12 Sprint Active 5 上機驗證**：sitting → `sit_along` / bending → `careful_remind` / crouching say / fallen with `{name}` 各 3 次穩定觸發
- [ ] **B4-1 Sitting/Bending 規則聯動驗收**（sprint Phase B-4 高優先項）
- [ ] **B4-5 fallen_alert + {name} 全鏈路驗證**（pose → face name 取得 → say）
- [ ] akimbo / knee_kneel 判定演算法（post-demo, Hidden bucket）
- [ ] 跌倒偵測幻覺（無人時鎖定衣架）— 投票 buffer 改 30 幀 OR 改 movement-based filter

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs DWPose）、benchmark 比較、跌倒偵測研究 |
