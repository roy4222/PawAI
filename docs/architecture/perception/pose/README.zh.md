# 姿勢辨識

[English](./README.md) | **中文**

> **Scope**：vision_perception 姿勢子系統設計真相（MediaPipe Pose + 角度/幾何分類）｜**Status**: active / source-of-truth (module)
> **Owner lane**: pawai-brain / perception ｜ **能力 claim 真相源**：[`docs/mission/2026-06-18-capability-claim-matrix.md`](../../../mission/2026-06-18-capability-claim-matrix.md) `pose.basic` / `pose.fall`
> **能力 grade 證據（最終事實）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（pose.basic / pose.fall = ⚪ **insufficient_data**，無 pose observer；caveats 凌駕本頁敘事）
> **維護子檔**：`CLAUDE.md`（工作規則）｜`AGENT.md`（topic 介面契約）｜`research/`（research-only，非真相）
> **這頁不是什麼**：不是能力 pass/fail 的裁定（看 baseline-evidence）。⚠️ **pose.basic = Studio-only / insufficient_data**（6/04 無 observer，未量）；**跌倒（pose.fall）是 future、非緊急行為**，demo 維持 `enable_fallen:=false`。**不得宣稱跌倒偵測可靠 / 防跌倒守護 / 緊急警報已 pass**。

> MediaPipe Pose 辨識人體姿勢。**pose.basic 本輪未量測（Studio-only）；跌倒是 future、非緊急行為**。

## 能力卡（canonical 8 欄位 → 連結 claim matrix，勿在本頁重複整份散文）

> 完整 8 欄位散文見 [claim matrix `pose.basic / pose.fall`](../../../mission/2026-06-18-capability-claim-matrix.md#posebasic--posefall)。本表為速查。

| 欄位 | 值 |
|---|---|
| **Current Claim** | 姿勢 / 跌倒有能力鏈路但本輪未量測；demo 不做、用應用場景影片帶過 |
| **Claim Level** | DO_NOT_CLAIM |
| **Evidence-Provenance** | [`baseline-evidence/2026-06-04-hitl/`](../../../runbook/baseline-evidence/2026-06-04-hitl/)（n=0, 無 pose observer, fall claim_level=future, `brain_allowed=false`） |
| **Pass/Degraded/Fail/Insufficient** | ⚪ insufficient_data（pose.basic = Studio-only）；跌倒是 **future**、非緊急行為 |
| **Fallback** | 鏡頭帶到 Studio fallen 紅標時旁白**絕不提跌倒**；demo 啟動維持 `enable_fallen:=false` |
| **Non-Claims** | 跌倒偵測可靠 / 防跌倒守護 / 坐下偵測已 pass / 緊急警報 / 把 pose 觀察當醫療判斷 |
| **Model Candidates** | FUTURE_RESEARCH（跌倒）；pose.basic 待建 observer |
| **Next Retest** | 建 pose observer 工具 + HITL 收 ground-truth 樣本才可談 pass；fall 本就 future 不進 demo |

## 狀態卡

> **狀態卡 caveat（6/04 收斂）**：下表「5/7 上機通過」是**開發期主觀上機觀察（無 observer 量化）**，**非 6/04 trusted baseline**。6/04 pose.basic / pose.fall = ⚪ insufficient_data（無 pose observer，n=0）。完成度為模組開發進度，非能力 pass。「fallen 穩定」**不構成跌倒偵測 pass**——跌倒是 future、非緊急。

| 項目 | 值 |
|------|---|
| 狀態 | **pose.basic = ⚪ Studio-only / insufficient（6/04 trusted）**；fallen = future 非緊急 |
| 版本/決策 | MediaPipe Pose (CPU 18.5 FPS) |
| 完成度 | 90%（模組開發進度，非能力 pass — 見上方 caveat） |
| 最後驗證 | 6/04 trusted 無 pose observer（insufficient_data）；5/7「上機通過」僅開發期主觀觀察 |
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
interaction_executive_node → fallen = EMERGENCY（內部 routing 標籤）
```

> ⚠️ **「EMERGENCY」是內部事件 routing 標籤，非已驗證的緊急守護能力**。跌倒（pose.fall）= future、非緊急行為（claim matrix `pose.fall` Non-Claims）。demo 維持 `enable_fallen:=false`、fallen TTS 兩條路徑皆 mute（5/8）；**不得對外宣稱跌倒守護 / 緊急警報已 pass**。

## 支援姿勢（MOC 7 種全部 Active，5/5 落地）

| 姿勢 | 判定邏輯 | 觸發 Skill | 台詞範本（demo bridge）| 狀態 |
|------|---------|---|---|:---:|
| standing | hip_angle > 155° + knee_angle > 155° | （預設，不觸發）| — | Active |
| akimbo | standing 變體；shoulder/elbow/hip vis ≥ 0.5；雙肘往外 > hip_width × 0.4；elbow y 在 shoulder 與 hip+0.5×hip_width 之間；wrist 可見時 elbow 角 60-140° | `akimbo_react` | 「你看起來很有架式喔！」（暫定）| **不穩**（5/6） |
| sitting | y-geometry：trunk < 35° + hip_y ≈ knee_y（< 0.12×torso）OR knee_y < hip_y + ankle_y - hip_y > 0.5×torso + knee_angle < 145° | `sit_along` | 「會不會太累？」 | Active |
| crouching | hip_angle < 145°, knee_angle < 145°, trunk > 10° | （互動 say）| 「我在這裡喔」 | Active |
| bending | trunk > 30°, knee_angle > 130°, hip_angle < 160°, bbox ≤ 1.0 | `careful_remind` | 「請小心喔」 | Active |
| knee_kneel | 兩膝 y 差 > 0.07×torso；hip/knee/stand_ankle vis ≥ 0.5；kneel ankle 隱藏 OR ankle_y ≈ knee_y（< 0.20×torso）OR kneel 角 < 130°；stand 角 > 130° OR sitting-like 支撐 | `knee_kneel_react` | 「需要我幫忙嗎？」（暫定）| **不穩**（5/6） |
| fallen | trunk > 60° AND 0 ≤ vertical_ratio < 0.4 AND torso vis ≥ 0.5；deep-bending guard：hip→ankle 與向下垂直夾角 < 30° 且 bbox ≤ 1.0 時跳過；bbox > 1.0 加 +0.05 confidence bonus（不再為硬條件）| `fallen_alert`（EMERGENCY）| 「{name}，偵測到跌倒，請注意安全！」 | Active（可關）|

> **5/6 演算法升級**（commits TBD，base on community-validated rules）：
> - `fallen` 解除「bbox_ratio > 1.0 必要條件」，改 vertical_ratio 為主守門 + torso visibility ≥ 0.5 拒掉 MediaPipe garbage frames（有時把 shoulder 標到 hip 下方）；新增 deep-bending guard 防止彎腰摸地誤判 fallen。
> - `sitting` 改用 y-geometry（hip≈knee y + ankle 明顯低於 hip）取代角度法，避免與 bending / crouching 重疊。
> - `akimbo` 主訊號改為 elbow-bowed-out（社群 BleedAI / MediaPipe issue #4462 的 wrist drift 坑），visibility 門檻從 0.2 提到 0.5。
> - `knee_kneel` 新增 kneel-side ankle.y ≈ knee.y 區分 kneel-vs-lunge（社群 yoga-pose 規則）；ankle 隱藏視為 kneel 訊號。
> - 順序：fallen → standing/akimbo → knee_kneel → sitting → crouching → bending → None。
> 26/26 unit tests 全綠（synthetic）；上機 5/7 動作 PASS，akimbo + knee_kneel 真實 MediaPipe 數據仍待調校。
> 完整 plan：`$HOME/.claude/plans/pose-validated-harp.md`。

## 操作限制與已知問題

- **有效範圍**：D435 前方約 **4-5m** 以內
- **僅支援單人追蹤**：多人時 MediaPipe 只追蹤一人
- RTMPose balanced mode GPU 91-99%（備援方案，主線用 MediaPipe CPU 0%）
- ~~正面站姿被誤判為 fallen~~ — **已修復（4/3）**：新增 `vertical_ratio` guard，用 shoulder-hip 垂直差 / torso 長度作為相對尺度（閾值 0.4），不受距離影響
- ~~彎腰摸地被吃成 fallen~~ — **已修復（5/6）**：fallen 主分支內加 deep-bending guard（hip→ankle 向量與向下垂直夾角 < 30° + bbox ≤ 1.0 → 跳過）。
- ~~MediaPipe garbage frame 觸發 fallen~~ — **已修復（5/6）**：trunk_angle 計算出 shoulder.y > hip.y（vertical_ratio 為負）的 frame 被拒；torso 4 點 visibility 平均 < 0.5 也拒。
- 跌倒偵測可能誤報（椅子上趴下）
- **akimbo / knee_kneel 上機不穩**（5/6 實測）：MediaPipe Pose 對手腕近髖、單膝跪地的 frame 經常 hallucinate landmark（trunk=160°+ 是常見訊號）。已套用社群實證的修法（elbow-bowed-out 主訊號、ankle.y ≈ knee.y 區分 kneel-vs-lunge），但實機仍偶有 miss。可能需要：(1) 拉視野到 1.5-3m（避免半身出框），(2) 改用 RTMPose-wholebody（GPU 路徑），(3) 加入 hand keypoint 訊號。
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
| fallen | **demo silence**（5/8）— TTS 兩條路徑都已 mute，Studio Trace 仍顯示紅 alert | **10s** | Scene 8（future，非緊急；用詞用「守望/回報」不用「守護」）|
| akimbo | demo bridge → 「你看起來很有架式喔！」（暫定）| 5s | 互動段（5/5 升 Active）|
| knee_kneel | demo bridge → 「需要我幫忙嗎？」（暫定）| 5s | 互動段（5/5 升 Active）|

> 站立 standing 不觸發任何 skill（純 baseline 狀態）。
> 全部走 `vision_perception/vision_perception/event_action_bridge.py` POSE_TTS_MAP 的 demo bridge — 只 publish `/tts`，不發 Go2 motion。長期路徑改為正規 Brain skill（`sit_along` / `careful_remind` / `fallen_alert` / `akimbo_react` / `knee_kneel_react`）走 `/brain/proposal` → `/skill_result`，列為 post-demo Stretch。

**5/8 fallen demo silence**（兩條 TTS 路徑都 mute，避免推車/椅子等 mid-frame 假跌倒打斷對話）：
1. `_on_fall_alert`（topic `/event/interaction/fall_alert`）→ `FALL_ALERT_TTS = ""` + `if FALL_ALERT_TTS:` guard（commit `9d8acb7`）
2. `_on_pose_event`（topic `/event/pose_detected`）→ `POSE_TTS_MAP` 移除 `"fallen"` key（commit `b224217`）

加 sync test `test_pose_tts_map_no_fallen_template_demo_silence` 鎖兩條路。Studio 仍顯示紅 alert chip — 視覺紀錄保留，只是不發語音。

**5/8 ankle-on-floor gate**（`pose_classifier.classify_pose` 加 `image_height` 參數）：當 `image_height` 提供時，要求 `ankle_y / image_height > 0.7`（人在畫面下半部 30% → 真的躺在地上）才認 fallen。`image_height=None` 維持原行為（既有 unit test 不破），mid-frame ankles（推車 / 椅子 / 彎腰物）擋下。`vision_perception_node.py:289` 在呼叫處傳 `image.shape[0]`。

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
- [x] **7 姿勢演算法升級**（5/6，社群實證規則：elbow-bowed-out / ankle ≈ knee y / vertical_ratio 守門 / deep-bending guard，26 unit tests 全綠）
- [x] **5/12 Sprint 5/7 上機驗證**：standing / sitting / crouching / bending / fallen 通過（5/6）
- [ ] **akimbo / knee_kneel 上機 miss 修復**（5/6 user 回報「基本完全測不出來」）— 候選：拉視野距離、切 RTMPose-wholebody、加 hand keypoint
- [ ] **5/12 Sprint Active 7 上機驗證**：sitting / crouching / bending / fallen-with-name / akimbo / knee_kneel / standing 各 3 次穩定觸發
- [ ] **demo bridge 退場路徑**：把 pose→/tts 改為正規 Brain skill（`sit_along` / `careful_remind` / `fallen_alert` 等）走 `/brain/proposal` → `/skill_result`（post-demo, Stretch P1）
- [ ] 跌倒偵測幻覺（無人時鎖定衣架）— 投票 buffer 改 30 幀 OR 改 movement-based filter

## 子資料夾

| 資料夾 | 內容 |
|--------|------|
| research/ | 選型過程（MediaPipe vs RTMPose vs DWPose）、benchmark 比較、跌倒偵測研究 |
