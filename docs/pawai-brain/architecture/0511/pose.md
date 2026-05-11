# 姿勢辨識（pose）— 架構詳述

**版本**：2026-05-11 freeze 快照（N7 fallen 敏感度放寬）
**位置**：`vision_perception/`（與 gesture 同住）
**入口**：`vision_perception/vision_perception/pose_classifier.py`（純規則，~383 行）
**狀態**：5/7 上機 PASS（standing/sitting/crouching/bending/fallen），akimbo / knee_kneel 不穩

---

## 1. 模組定位

姿勢辨識是 PawAI 系統中**守護 30%** 的核心，也是「居家陪伴」narrative 的安全底層。它的工作是把鏡頭裡的人體骨架轉成 7 種離散姿勢狀態，其中 `fallen`（跌倒）是 SAFETY-CRITICAL 等級的觸發點。

**核心設計**：
- **規則引擎，無 ML**：383 行 Python，純幾何規則（trunk_angle / vertical_ratio / hip_angle / knee_angle）
- **單幀分類 + 時間投票**：classify_pose 是 stateless 純函式，pose_buffer maxlen=20 做穩定化
- **雙 backend**：MediaPipe Pose（CPU 主線）/ RTMPose lightweight（GPU 備援）
- **共用 orchestrator**：與 gesture / object 都在 `vision_perception_node`
- **效能**：18.5 FPS CPU（GPU 0%），三感知壓測 60s PASS（RAM 1.2GB, temp 52°C）

**對外介面**：
- 訂閱：D435 RGB
- 發佈：`/event/pose_detected`（事件觸發，state transition only）

---

## 2. Pipeline 全貌

```
┌──────────────────────────────────────────────────────────────────────┐
│              D435 RGB  (/camera/camera/color/image_raw)              │
└──────────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│        VisionPerceptionNode  (tick=0.05s = 20Hz)                     │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 1: 骨架抽取（雙 backend）                                  │ │
│  │  ┌────────────────────────┐   ┌────────────────────────┐        │ │
│  │  │ Path A: MediaPipe Pose │   │ Path B: RTMPose        │        │ │
│  │  │  (pose_backend=        │   │  (pose_backend=        │        │ │
│  │  │   mediapipe，主線)     │   │   rtmpose，備援)        │        │ │
│  │  │  CPU 18.5 FPS, GPU 0%  │   │  GPU ~90%, 9-17 FPS    │        │ │
│  │  │  pip pkg 內建模型       │   │  rtmlib wholebody.onnx │        │ │
│  │  │  33 pt → COCO 17       │   │  133 pt slice [0:17]   │        │ │
│  │  └────────────────────────┘   └────────────────────────┘        │ │
│  │           │                              │                      │ │
│  │           └──────────────┬───────────────┘                      │ │
│  │                          ▼                                      │ │
│  │       透過 InferenceAdapter 抽象 → InferenceResult              │ │
│  │       body_kps (17,2) + body_scores (17,) [COCO 標準索引]      │ │
│  │       (另含左右手 21pt，供 gesture 共用)                        │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 2: classify_pose() 規則引擎（單幀分類，純 Python）         │ │
│  │                                                                  │ │
│  │  優先序（first match wins）：                                    │ │
│  │   1. fallen      ← SAFETY，多重 gate（見第三節）                │ │
│  │   2. standing    ← hip+knee_angle > 155                          │ │
│  │   3. akimbo      ← standing + 手肘外撐（standing 變體）         │ │
│  │   4. knee_kneel  ← 雙膝 y 差 ≥ 0.07×torso（必須先於 sitting）  │ │
│  │   5. sitting     ← y-geometry（hip≈knee，ankle 遠下）           │ │
│  │   6. crouching   ← 雙腿都彎 + trunk > 10°                       │ │
│  │   7. bending     ← trunk > 30° + 腿直 + bbox 窄                 │ │
│  │   else → None                                                    │ │
│  │                                                                  │ │
│  │  輸出: (pose_name | None, avg_score)                             │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │ Stage 3: 時間投票 (pose_buffer maxlen=20，~1s @ 20Hz)            │ │
│  │   _majority() 取 deque 中最多出現的非 None label                │ │
│  │   confidence = vote_count / buffer_len（vote 比率）             │ │
│  │   發佈條件：pose_vote != last_pose（state transition only）     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
│                          │                                           │
│                          ▼                                           │
│  /event/pose_detected （事件觸發，非週期）                           │
└──────────────────────────────────────────────────────────────────────┘
```

### COCO 17-point Keypoint Layout

```
Index   Name              RTMPose  MediaPipe
0       NOSE              0        0
5,6     L/R_SHOULDER      11,12    11,12
7,8     L/R_ELBOW         13,14    13,14
9,10    L/R_WRIST         15,16    15,16
11,12   L/R_HIP           23,24    23,24
13,14   L/R_KNEE          25,26    25,26
15,16   L/R_ANKLE         27,28    27,28
```

兩 backend 輸出統一為 `body_kps (17,2) + body_scores (17,)`，給 `classify_pose` 用。

---

## 3. ★ Fallen 跌倒檢測（safety-critical 多重 gate）★

這是整個專案最重要的安全規則。完整邏輯：

```
classify_pose() 一開始就先檢查 fallen，全部 gate 都過才回 "fallen"
─────────────────────────────────────────────────────────────────

Gate 1: 軀幹角度 + 垂直比例
   trunk_angle > 60°
   AND  0.0 ≤ vertical_ratio < 0.45     ★N7 從 0.4 → 0.45★
   
   其中：
     vertical_ratio = (hip_y - shoulder_y) / torso_len
       ≈ 1.0  → 站立（hip 遠下於 shoulder）
       ≈ 0.0  → 完全平躺
       0.35–0.45 → 蜷縮跌倒（torso 縮短，y 差仍小）
     
   N7 動機：「身體接觸地面附近就要觸發跌倒」
            蜷縮跌倒 vertical_ratio 落在 0.35–0.45，
            原本 0.4 hard gate 會擋掉
            
Gate 2: 軀幹可見度
   avg(scores[L_shoulder, R_shoulder, L_hip, R_hip]) ≥ 0.5
   → 擋掉 MediaPipe 幻覺幀（akimbo / 半身入鏡 / 奇怪視角）

Gate 3: Deep-bending 防誤判
   IF bbox_ratio ≤ 1.0:                  ← 直立窄輪廓才需要查
       lower_body_angle (hip→ankle 與垂直夾角) < 30°
       → 腿仍指向下 → is_deep_bending=True → 跳過 fallen
   
   功能：彎腰摸地（軀幹平但腳直立）不算跌倒
   保留：bbox > 1.0（水平展開）就算腿直也判跌倒

Gate 4: 腳踝在地面（image height ratio）  
   IF image_height 提供:
       ankle_y / image_height > 0.6      ★N7 從 0.7 → 0.6★
       → 人在畫面下半部
   IF image_height = None: 跳過此 gate（legacy 相容）
   
   N7 動機：遠距離或上半身入鏡時，真實跌倒 ankle 落在 0.6–0.7，
            原本 0.7 太嚴格

最終判定:
   NOT is_deep_bending  AND  ankle_on_floor
   → return ("fallen", min(avg_score + bonus, 1.0))
   
   bonus = +0.05 IF bbox_ratio > 1.0（水平輪廓加分，非必要）
```

### N7 變動（5/11 commit `717a24a`）

| 參數 | 行號 | 之前 | 之後 | 目的 |
|------|:---:|:----:|:----:|------|
| `vertical_ratio` 上界 | 132 | 0.40 | **0.45** | 接受蜷縮跌倒 |
| `ankle_on_floor` Y 比例 | 174 | 0.70 | **0.60** | 接受遠距/上半身入鏡跌倒 |
| `pose_classifier.py` 註解 | 128-131, 168-170 | — | 新增 | 註明 N7 改動理由 |

**沒動的高風險 gate**：`trunk_angle > 60°`、`torso_visibility ≥ 0.5`、`is_deep_bending`（commit 訊息註明：要動需全套回歸測試）。

### 為什麼這樣設計（四層 gate 邏輯）

```
Gate 1（vertical_ratio）：尺度不變的「人是不是橫躺」判斷
                         → 處理不同距離、不同人體尺寸

Gate 2（torso_visibility）：MediaPipe 幻覺擋掉
                            → 處理奇怪視角、半身入鏡

Gate 3（deep-bending）：彎腰摸地 vs 真跌倒區分
                       → 用「腿是否仍朝下」判斷

Gate 4（ankle_on_floor）：人是否在畫面底部
                          → 處理椅子 / 推車 / 桌面平放物的誤判
```

四層並聯 AND，任一 fail 都拒絕判 fallen。

---

## 4. 其他 6 種姿勢的判定規則

| Pose | 關鍵點 | 規則 | 用途 |
|------|--------|------|------|
| **standing** | hip, knee, ankle | `hip_angle > 155° AND knee_angle > 155°` | baseline 不發 event |
| **akimbo**（叉腰）| shoulder, elbow, wrist, hip | standing + 手肘外撐 > 0.4×hip_width + elbow y 落在 shoulder-hip+0.5×hip_width 間 + (若 wrist 可見) elbow_angle 60-140° | 5/12 unstable |
| **knee_kneel**（單膝跪）| 雙膝、雙踝 | 雙膝 y 差 ≥ 0.07×torso + 跪側 ankle ≈ knee.y 或藏起 + 站側膝 > 130° 或 sitting-like | 5/12 unstable |
| **sitting** | shoulder, hip, knee, ankle | y-geometry：`hip ≈ knee y`（< 0.12×torso）OR `knee.y < hip.y` + `ankle 遠下 hip > 0.5×torso` + `trunk < 35°` + `knee_angle < 145°` | demo bridge TTS |
| **crouching** | hip, knee, ankle | `hip_angle < 145° AND knee_angle < 145° AND trunk_angle > 10°` | demo bridge TTS |
| **bending** | shoulder, hip, knee, ankle | `trunk > 30° + knee > 130° + hip < 160° + bbox ≤ 1.0` | demo bridge TTS |

**設計考量**：
- sitting 改用 y-geometry（5/6 升級），避開角度與 bending/crouching 重疊
- knee_kneel 必須先於 sitting 否則被吞掉（單膝會被誤判為坐）
- akimbo 是 standing 變體（必先過 standing gate 才檢查叉腰）

---

## 5. Topic Schema（v2.0 凍結）

### `/event/pose_detected`

```json
{
  "stamp": 1773561601.234,
  "event_type": "pose_detected",
  "pose": "fallen",          // contract 凍結 4 種: standing|sitting|crouching|fallen
                              // (內部分類器另含 bending/akimbo/knee_kneel)
  "confidence": 0.95,        // vote 比率 (count/20)，非原始分數
  "track_id": 0              // Phase 1 永遠 0（無人臉關聯）
}
```

**QoS**：Reliable, Volatile, depth=10
**頻率**：事件觸發（state transition only），非週期
**Builder**：`event_builder.build_pose_event()`

**注意**：contract v2.0 frozen enum 只列 4 種；classifier v3 內部支援 7 種，超出 contract 的 3 種（bending/akimbo/knee_kneel）是「延伸事件」，下游照常會收到。

---

## 6. 消費者拓撲

```
                       vision_perception_node
                                │
                                ▼
                     /event/pose_detected
                                │
   ┌────────────┬───────────────┼──────────────┬────────────┐
   │            │               │              │            │
   ▼            ▼               ▼              ▼            ▼
┌──────┐  ┌──────────┐  ┌────────────┐  ┌────────┐   ┌─────────┐
│Brain │  │Executive │  │interaction │  │event_  │   │Studio   │
│      │  │brain_node│  │_router     │  │action_ │   │gateway  │
└──────┘  └──────────┘  │(deprecated │  │bridge  │   └─────────┘
   │           │        │ v2.2)      │  │(demo)  │        │
   │           │        └────────────┘  └────────┘        ▼
   │           │               │              │      前端 PosePanel
   │           │               ▼              │      (current_pose
   │           │      /event/interaction/     │       active=true)
   │           │         fall_alert           │
   │           │      (deprecated, 舊路徑)     │
   │           │                              │
   │           │                              ▼
   │           │              POSE_TTS_MAP demo bridge:
   │           │                ├ sitting   → "會不會太累？"
   │           │                ├ crouching → "我在這裡喔"
   │           │                ├ bending   → "請小心喔"
   │           │                ├ akimbo    → "你看起來很有架式喔！"
   │           │                └ knee_kneel→ "需要我幫忙嗎？"
   │           │              ★ fallen 故意不在表內（5/8）★
   │           │              ★ FALL_ALERT_TTS = "" 故意空（5/12）★
   │           │              cooldown: 5s（fallen 設 10s 但停用）
   │           │
   │           │  ★ 生產主路徑 ★
   │           ├─ fallen: 累積 2.0s → cooldown 15s → 觸發 fallen_alert skill
   │           │   name 注入優先序：
   │           │     1) pose payload .name
   │           │     2) _last_stable_identity_name (≤30s 內)
   │           │     3) "有人" (fallback)
   │           │   skill steps:
   │           │     a) MOTION stop_move (Go2 先停)
   │           │     b) SAY "偵測到 {name} 跌倒，請注意安全"
   │           ├─ sitting: 累積 1.0s → sit_along（低風險社交）
   │           └─ bending: bending_react（受 confirm_pending 控）
   │
   ▼  pawai_brain._on_pose_detected
   ├─ payload["pose"] → self._recent_pose = (name, ts)
   ├─ world_state_builder：stale 門檻 10s（比 gesture 5s 寬，因為 pose 變動慢）
   └─ Prompt 注入 [最近姿勢] {zh}（{age} 秒前）
       透過 _POSE_ZH 翻譯：
         standing→站著, sitting→坐著, crouching→蹲著, fallen→跌倒
       scene_query 模式：與 face+gesture+objects 融合場景敘述
```

**重點分工**：
- **Brain 只取語境**（最近姿勢），不觸發動作
- **Executive `brain_node` 才是生產主路徑**（fallen_alert skill，含 stop_move + SAY）
- **router 的 `/event/interaction/fall_alert` 已 deprecated**（v2.2 起 Executive 內部處理）
- **bridge 的跌倒 TTS 已啞掉**（5/8 + 5/12 雙重決議避免 double-announce）

---

## 7. Fallen Demo Silence 決策（5/8 → 5/12 雙重關閉）

跌倒 TTS 走 **唯一一條路徑**：Executive 的 `fallen_alert` skill。其他兩條被故意關掉：

| 路徑 | 狀態 | 原因 |
|------|------|------|
| `event_action_bridge.FALL_ALERT_TTS` | `""`（空字串，5/12）| 避免與 brain skill 雙重播報；`if FALL_ALERT_TTS:` short-circuit |
| `event_action_bridge.POSE_TTS_MAP["fallen"]` | 故意不在表內（5/8）| pose event 本身也會誤觸（chairs/carts），demo 期 silent |
| `interaction_executive.skill_contract["fallen_alert"]` | **唯一活路徑** | stop_move + SAY，cooldown 15s，name 注入 |

註解上明寫：「Restore by re-adding `'fallen': '{name}，...'` once the pose classifier ankle filter and pose buffer reach acceptable false-positive rate.」

### fallen_alert skill 細節

```python
"fallen_alert": SkillContract(
    name="fallen_alert",
    steps=[
        SkillStep(ExecutorKind.MOTION, {"name": "stop_move"}),    # 1. Go2 先停
        SkillStep(
            ExecutorKind.SAY,
            {"text_template": "偵測到 {name} 跌倒，請注意安全"},  # 2. 廣播
        ),
    ],
    priority_class=PriorityClass.ALERT,
    cooldown_s=15.0,
    display_name="跌倒提醒",
    demo_status_baseline="explain_only",   # demo 期僅在 Studio 顯示
    demo_value="medium",
    demo_reason="關閉誤觸打斷對話；只在 Studio 顯示警示",
)
```

### Brain 端觸發邏輯（brain_node._on_pose）

```python
if pose == "fallen":
    if self._state.fallen_first_seen is None:
        self._state.fallen_first_seen = now
    elif (now - self._state.fallen_first_seen) >= self.fallen_accumulate_s:  # 2.0s
        if not self._in_cooldown("fallen_alert", 15.0):
            self._mark_cooldown("fallen_alert")
            self._world.set_fallen(True)
            # name 注入策略
            raw_name = payload.get("name") or payload.get("identity") or ""
            if not raw_name:
                if cached and cached_age <= 30.0:
                    raw_name = cached
            name = raw_name or "有人"
            self._emit(build_plan(
                "fallen_alert",
                args={"name": name},
                source="rule:pose_fallen_2s",
                reason="pose_fallen_stable_2s",
            ))
            self._state.fallen_first_seen = None
```

---

## 8. 模型選型（3/21 benchmark 決策）

| 模型 | FPS (Jetson) | GPU | 決策 | 原因 |
|------|:----:|:----:|:----:|------|
| **MediaPipe Pose** | **18.5** | **0%** | **主線** | CPU-only，三感知壓測 PASS（RAM 1.2GB, temp 52°C）|
| RTMPose lightweight | 17.6 | ~90% | 備援 | GPU 與 Whisper CUDA 競爭 |
| RTMPose balanced | 9.3 | 91-99% | 備援 | 精度最高但 GPU 滿載 |
| MoveNet | — | — | 拒用 | 只 17 點，無手，Jetson GPU delegate 有問題 |
| trt_pose | 15-16 | — | 拒用 | JetPack 6 相容性未驗 |
| YOLO11n-pose | — | — | P2 future | 標記未來候選 |

---

## 9. 關鍵設定（vision_perception.yaml）

```yaml
vision_perception_node:
  ros__parameters:
    # Pose 主線
    pose_backend: "rtmpose"           # 或 "mediapipe"（實機主線）
    pose_complexity: 0                # 0=lite, 1=full, 2=heavy（MP 用）
    pose_vote_frames: 20              # 投票視窗 (~1s @ 20Hz)
    
    # RTMPose 細部（pose_backend=rtmpose 時）
    rtmpose_mode: "balanced"          # 或 "lightweight"
    rtmpose_device: "cuda"            # 或 "cpu"
    
    # 共用 timing
    tick_period: 0.05                 # 20Hz 內部 loop
    publish_fps: 8.0                  # debug image 頻率
```

下游消費者參數：
```python
# interaction_router
fallen_persist_sec = 2.0
fall_alert_cooldown = 15.0

# event_action_bridge
POSE_TTS_COOLDOWN_DEFAULT_S = 5.0
POSE_TTS_COOLDOWN_FALLEN_S  = 10.0   # 設了但沒用（fallen 已從表移除）

# pawai_brain.world_state_builder
_POSE_STALE_S = 10.0                 # pose 變動慢，比 gesture 5s 寬

# interaction_executive.brain_node
fallen_accumulate_s = 2.0
fallen_alert_cooldown_s = 15.0
last_stable_identity_freshness_s = 30.0
```

---

## 10. 測試覆蓋

`test_pose_classifier.py`（26+ 測試，純 Python）：

### 主分類
- standing / sitting / crouching / bending / fallen 基本 happy path
- 優先序測試：`test_fallen_priority_over_standing`

### Fallen 多 gate 專屬
- `test_fallen_no_bbox_required` — 沒 bbox 也能判（靠 trunk+vertical_ratio）
- `test_fallen_curled_legs_bent` — 老人蜷縮（hip/knee 90°）
- `test_sitting_not_fallen_when_curled` — 坐著前傾不被誤判
- `test_fallen_with_image_height_when_ankle_on_floor` — ankle gate 過
- `test_fallen_blocked_when_ankle_mid_frame` — ankle 在畫面中間被擋
- `test_fallen_image_height_none_preserves_legacy` — 沒 image_height 用舊行為
- `test_fallen_rejected_when_shoulder_below_hip` — MediaPipe 幻覺（vertical_ratio < 0）擋掉
- `test_fallen_rejected_when_torso_visibility_low` — torso_vis < 0.5 擋掉
- `test_deep_bending_not_fallen` — 彎腰摸地（腿直）→ bending 不是 fallen

### 前向站立防誤判
- `test_frontal_standing_near_not_fallen` — 近距離寬肩 + bbox 1.25
- `test_frontal_standing_far_not_fallen` — 遠距離縮小
- `test_actual_fallen_still_detected` — 真實水平 bbox 2.5

### akimbo / knee_kneel
- 基本 case + 反例

`test_mediapipe_pose_mapping.py`：COCO ↔ MediaPipe 33pt mapping 完整性、無重複、關鍵點保留。

---

## 11. 已知問題（5/12 凍結項）

| # | 問題 | 處置 | 狀態 |
|---|------|------|:----:|
| 1 | Fallen 誤判（椅子/推車）| `vertical_ratio` + `ankle_on_floor` + `torso_visibility` + deep-bending 多 gate | MITIGATED（TTS demo silent）|
| 2 | sitting / crouching 混淆 | sitting 改 y-geometry，order: sitting → crouching | FIXED |
| 3 | bending vs fallen | deep-bending guard（hip→ankle 角度）| FIXED |
| 4 | akimbo 實機難認 | wrist drift；改用 elbow 外撐為主訊號 | PARTIAL（5/12 unstable）|
| 5 | knee_kneel 實機難認 | ankle 藏起當 kneel 訊號 | PARTIAL（5/12 unstable）|
| 6 | 無人時衣架幽靈跌倒 | 20-frame 投票 buffer | MITIGATED |
| 7 | 站立被誤判跌倒（早期）| 加 `vertical_ratio >= 0` 守衛 | FIXED |
| 8 | 蜷縮跌倒漏掉 | N7：vertical_ratio 0.4→0.45 | FIXED（5/11）|
| 9 | 遠距/上半身跌倒漏掉 | N7：ankle ratio 0.7→0.6 | FIXED（5/11）|

---

## 12. Elder-Care Narrative 定位

**任務分工**（`docs/mission/README.md`）：
- 互動 **70%**（手勢 / 姿勢 / 語音 / 物體）— Demo 主秀
- 守護 **30%**（陌生人警告 / 巡邏 / 跟隨）— pose **fallen 是守護 30% 的中心**

**為什麼 fallen 同時跨兩個 pillar**：
- 守護 30%：24/7 背景監控，是唯一觸發 EMERGENCY 級別的 pose 規則
- 互動 70%：Demo 流程含 fallen detection narrative（Scene 8 / 守護模式）

**5/12 Demo 策略**：interaction 70% 優先 → fallen TTS 啞掉（避免誤觸打斷對話），但 Studio trace 仍顯示紅色警示（保留守護敘事 + 可視化）。

---

## 13. 關鍵設計決策（給寫計畫書的參考）

1. **規則引擎而非 ML**：383 行純規則 / 純函式，可解釋、可測試、可調參。對 demo / 計畫書 narrative 友善
2. **雙 backend 策略**（MP CPU 主 / RTMPose GPU 備）：CPU 主線保護 GPU 預算（Whisper / vision GPU 競爭）
3. **Fallen 多重 gate**：四層 gate 並聯 AND，每層獨立守護不同 false positive
4. **N7 故事**（5/11 commit `717a24a`）：兩個門檻 0.4→0.45 / 0.7→0.6，回應使用者「身體靠地就要觸發跌倒」的回饋，同時保留高風險 gate 不動
5. **時間平滑**：20-frame 投票（~1s 滯後）換取穩定，state transition only 防止 topic flood
6. **Demo silence 雙重關閉**：bridge 兩路 + brain skill 一路，only 一條活路徑（fallen_alert skill），避免 double-announce
7. **enum 凍結 vs 內部擴展**：contract v2.0 凍結 4 種，內部 classifier v3 支援 7 種（bending/akimbo/knee_kneel 是「延伸事件」）
8. **與 face / gesture 融合**：在 brain prompt `[最近姿勢]` + scene_query 模式做 grounded scene reasoning

---

## 14. 索引：權威來源

| 主題 | 檔案 |
|------|------|
| 規則引擎 | `vision_perception/vision_perception/pose_classifier.py` |
| MediaPipe wrapper | `vision_perception/vision_perception/mediapipe_pose.py` |
| RTMPose adapter | `vision_perception/vision_perception/rtmpose_inference.py` |
| Adapter interface | `vision_perception/vision_perception/inference_adapter.py` |
| Event builder | `vision_perception/vision_perception/event_builder.py` |
| Demo bridge | `vision_perception/vision_perception/event_action_bridge.py` |
| Executive 路由 | `interaction_executive/interaction_executive/brain_node.py::_on_pose` |
| Brain handler | `pawai_brain/pawai_brain/conversation_graph_node.py::_on_pose_detected` |
| fallen_alert skill | `interaction_executive/interaction_executive/skill_contract.py::fallen_alert` |
| 設定 | `vision_perception/config/vision_perception.yaml` |
| Contract schema | `docs/contracts/interaction_contract.md` §4.4 / §4.5 |
| 模組文件 | `docs/pawai-brain/perception/pose/README.md` + `AGENT.md` + `CLAUDE.md` |
| Benchmark 決策 | `docs/pawai-brain/perception/pose/research/2026-03-21-benchmark-decision.md` |
| 任務分工 | `docs/mission/README.md` §5 |
