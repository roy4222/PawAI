# 6/18 Demo 錄影 — 三 Task Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 6/18 demo 四段錄影需要的軟體面打通：Studio 導航地圖面板、手勢兩步確認、物體分開句 cup demo mode。

**Architecture:** 三個互相獨立的 task。Task A 動 Studio（gateway Python read-only 訂閱轉發 + 前端 Canvas2D 面板），Task B/C 動 brain（`interaction_executive` 的 config + 兩處台詞 + 一個 runtime gate）。全部 read-only / config / 台詞層級，**不碰 nav 控制權、不碰感知模型**。逐行 gateway/前端 code 在姊妹文件 [`2026-06-09-studio-nav-panel-buildspec.md`](2026-06-09-studio-nav-panel-buildspec.md)（本 plan 引用其章節，不重貼長段）。

**Tech Stack:** ROS2 Humble（rclpy、geometry_msgs、std_msgs）、FastAPI + websocket（gateway）、Next.js + Canvas2D + zustand（前端）、pytest（brain/gateway unit test）。Jetson zsh + colcon + `source install/setup.zsh`；pip 一律 `uv pip install`。

---

## File Structure

**Task A — Studio nav panel**
- Modify: `pawai-studio/gateway/studio_gateway.py` — 3 個 nav 訂閱 + latched QoS + envelope 轉發 + `/api/map_meta` + StaticFiles（buildspec §1A）
- Modify: `pawai-studio/frontend/stores/state-store.ts` — `navPose`/`navReactiveStop`/`navPaused` + `updateNav`
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts` — `case "nav"` 分流
- Create: `pawai-studio/frontend/components/navigation/nav-map-canvas.tsx` — Canvas2D 面板（buildspec §1B B）
- Modify: `pawai-studio/frontend/components/navigation/navigation-panel.tsx:86-94` — 換掉 placeholder Section 3
- Create: `pawai-studio/frontend/public/maps/home_living_room.png` — cp v8 PNG
- Test: `pawai-studio/gateway/test_gateway.py` — pose envelope + quat→yaw；前端用 buildspec §5 手動煙測

**Task B — gesture gate + two-step config**
- Modify: `interaction_executive/config/executive.yaml:20` — `thumbs_up_demo_ack: true → false`
- Modify: `interaction_executive/interaction_executive/brain_node.py` — 確認 prompt 特例（~:810-815）、`gesture_enabled` param + `_on_gesture` early-return + `add_on_set_parameters_callback`
- Test: `interaction_executive/test/test_brain_rules.py`

**Task C — object separate wording + cup demo mode**
- Modify: `interaction_executive/config/executive.yaml:24` — `demo_video_cup_compound: true → false`
- Modify: `interaction_executive/interaction_executive/brain_node.py:62` — cup suffix 加 weather 句
- Test: `interaction_executive/test/test_brain_rules.py`

> 建議 commit 順序：**C → B → A**（C/B 最小最低風險先綠，A 最大最後）。

---

## Task A: Studio Nav Panel

**Files:**
- Modify: `pawai-studio/gateway/studio_gateway.py`（插入點見 buildspec §1A 表）
- Modify: `pawai-studio/frontend/stores/state-store.ts`
- Modify: `pawai-studio/frontend/hooks/use-event-stream.ts`
- Create: `pawai-studio/frontend/components/navigation/nav-map-canvas.tsx`
- Modify: `pawai-studio/frontend/components/navigation/navigation-panel.tsx`
- Create: `pawai-studio/frontend/public/maps/home_living_room.png`
- Test: `pawai-studio/gateway/test_gateway.py`

- [ ] **A-Step 1: 放 v8 map PNG（否則底圖空白）**

```bash
mkdir -p /home/roy422/newLife/elder_and_dog/pawai-studio/frontend/public/maps
cp /home/roy422/newLife/elder_and_dog/docs/navigation/research/maps/home_living_room_v8.png \
   /home/roy422/newLife/elder_and_dog/pawai-studio/frontend/public/maps/home_living_room.png
```
Expected: `ls pawai-studio/frontend/public/maps/home_living_room.png` 存在（205×98）。若來源 `.png` 不存在，先 `python3 -c "from PIL import Image; Image.open('docs/navigation/research/maps/home_living_room_v8.pgm').save('docs/navigation/research/maps/home_living_room_v8.png')"`。

- [ ] **A-Step 2: gateway pose envelope 失敗測試**

在 `pawai-studio/gateway/test_gateway.py` 加（沿用該檔現有 `_make_envelope`/mock node 模式）：

```python
def test_quat_to_yaw_and_pose_envelope():
    from studio_gateway import StudioGateway  # 依該檔實際 class 名調整
    # yaw=0 的四元數 (qz=0,qw=1) → yaw≈0；yaw=90° (qz=0.7071,qw=0.7071) → ≈π/2
    assert abs(StudioGateway._quat_to_yaw(0.0, 1.0)) < 1e-6
    assert abs(StudioGateway._quat_to_yaw(0.70710678, 0.70710678) - 1.5707963) < 1e-4
```
> 若 `test_gateway.py` 現有測試是純函式風格、不實例化 node，就只測 `_quat_to_yaw`（staticmethod，無 ROS 依賴）。envelope 結構交給 A-Step 8 的手動煙測。

- [ ] **A-Step 3: 跑測試確認 fail**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py::test_quat_to_yaw_and_pose_envelope -v`
Expected: FAIL（`_quat_to_yaw` 尚未定義 / AttributeError）。

- [ ] **A-Step 4: gateway 實作（照 buildspec §1A 逐行貼）**

照 [`buildspec §1A`](2026-06-09-studio-nav-panel-buildspec.md) 的 A1–A5 + B1–B3 插入：
- A1 `from geometry_msgs.msg import PoseWithCovarianceStamped`（line 33 後）
- A2 `QOS_NAV_LATCHED`（RELIABLE + TRANSIENT_LOCAL + depth=1）+ `POSE_THROTTLE_S = 0.2`（line 69 後）
- A3 `self._last_pose_broadcast = 0.0`（line 164 後）
- A4 三個 `create_subscription`：`/amcl_pose`→`QOS_NAV_LATCHED`、`/state/reactive_stop/status`→`QOS_EVENT`、`/state/nav/paused`→`QOS_NAV_LATCHED`（line 210 後）
- A5 `_quat_to_yaw`/`_broadcast_nav`/`_on_amcl_pose`/`_on_reactive_stop_status`/`_on_nav_paused`（line 276 後），`source="nav"`、`event_type` 用短名 `pose`/`reactive_stop`/`paused`、pose throttle 5Hz
- B1 `MAP_YAML_PATH`（`PAWAI_MAP_YAML` override，line 60 後）
- B2 `/api/map_meta`（手解 yaml，line 467 後）
- B3 `app.mount("/map", StaticFiles(...))`（line 450 後）

**鐵律**：`/amcl_pose` 與 `/state/nav/paused` 是 latched（TRANSIENT_LOCAL），用 `QOS_EVENT`（VOLATILE）會**永遠收不到、且不報錯**。

> ⚠️ **B1–B3（map_meta + StaticFiles）是加分、非 blocker**：今天錄影真正需要的是「前端 public PNG 底圖 + live pose 三角形」。前端 A-Step 1 已把 PNG cp 進 `public/maps/`、A-Step 7 的 `DEMO_MAP` 已**硬寫 v8 origin/res/H** → canvas 不依賴 gateway 取 map。**A4/A5（3 個 nav 訂閱轉發）才是 Task A 的必做核心**；B1–B3 若卡住（手解 yaml / StaticFiles mount）**直接跳過**，用硬寫常數完成畫面，map_meta 留 fast-follow。

- [ ] **A-Step 5: 跑測試確認 pass + py_compile**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest pawai-studio/gateway/test_gateway.py -v && python3 -m py_compile pawai-studio/gateway/studio_gateway.py`
Expected: PASS + 無語法錯。

- [ ] **A-Step 6: 前端 store + event-stream（照 buildspec §1B A1–A7）**

- `stores/state-store.ts`：加 `NavPose`/`NavReactiveStop` 型別、`navPose`/`navReactiveStop`/`navPaused` 欄位 + 初始值、`updateNav(patch)` partial action。
- `hooks/use-event-stream.ts`：取 `updateNav`、加 `case "nav"`（`switch(event_type)` → `pose`/`reactive_stop`/`paused`，欄位對齊見 buildspec §1B A6）、`useCallback` deps 補 `updateNav`。

- [ ] **A-Step 7: 新建 canvas 元件 + 換 placeholder（照 buildspec §1B B/C）**

- Create `components/navigation/nav-map-canvas.tsx`：Canvas2D，`drawImage(map PNG)` → pose 三角形 → 固定 goal marker → current→goal 直線 → 狀態 chip。**不引 ros3djs**。
- `DEMO_MAP = { src:"/maps/home_living_room.png", resolution:0.05, originX:-2.41, originY:-2.81 }`（**v8！不是 v7 的 -7.79**），`H=98`。
- 座標換算（buildspec §2）：`col=(wx-ox)/res`、`py=(H-1)-(wy-oy)/res`（**y-flip 只出現一次**）、三角形朝向 `screenAngle = -yaw`。
- `navigation-panel.tsx:86-94`：import `NavMapCanvas` 換掉 Section 3 dashed placeholder。

- [ ] **A-Step 8: 前端手動煙測（buildspec §5 驗收 A，無需 gateway）**

Run: `cd /home/roy422/newLife/elder_and_dog && bash pawai-studio/start.sh` → 開 `http://localhost:3000/studio` → navigation sheet → browser console：

```js
useStateStore.getState().updateNav({ pose: { x: 0, y: 0, yaw: 0 } });
useStateStore.getState().updateNav({ pose: { x: 0, y: 0, yaw: Math.PI/2 } });
useStateStore.getState().updateNav({ reactiveStop: { zone: "danger", front_distance_m: 0.8, nav_paused: true } });
```
Expected：① 原點三角形落底圖 **canvas ~(48,41)** ② `yaw=0` 尖端**朝右**、`yaw=π/2` **朝上**（不是朝下 → 證明 `-yaw` 對）③ `x=1.0,y=0` 三角形往**右** ~20px 同列 ④ `zone=danger` 變紅。任一不符 → 回 buildspec §2 校準步驟排錯（y-flip 別做兩次、別多做 x 翻轉）。截圖存 `docs/navigation/research/maps/` 當回歸基準。

- [ ] **A-Step 9: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add pawai-studio/gateway/studio_gateway.py pawai-studio/gateway/test_gateway.py \
        pawai-studio/frontend/stores/state-store.ts pawai-studio/frontend/hooks/use-event-stream.ts \
        pawai-studio/frontend/components/navigation/nav-map-canvas.tsx \
        pawai-studio/frontend/components/navigation/navigation-panel.tsx \
        pawai-studio/frontend/public/maps/home_living_room.png
git commit -m "feat(studio): nav map panel — map+pose+goal+line+status (no move-button/depth/dynamic-goal)"
```

> **接 gateway 真資料的驗收 B**（pose 對到 Go2 真實位置）屬 HITL，列在「錄前 smoke」，不在本 task 的 commit gate。

---

## Task B: Gesture Gate + Two-Step Config

**Files:**
- Modify: `interaction_executive/config/executive.yaml:20`
- Modify: `interaction_executive/interaction_executive/brain_node.py`（確認 prompt ~:810-815、`gesture_enabled` param + `_on_gesture` early-return ~:732、param callback）
- Test: `interaction_executive/test/test_brain_rules.py`

- [ ] **B-Step 1: 失敗測試 — WeGo prompt + gesture_enabled gate**

在 `interaction_executive/test/test_brain_rules.py` 加（沿用該檔 `brain._on_gesture(_msg({...}))` 模式；參考既有 `_on_pose`/`_on_gesture` 測試）：

```python
def test_thumbs_up_two_step_wego_prompt(brain):
    # thumbs_up_demo_ack=False → 走兩步確認；prompt 用 WeGo 特例台詞
    brain.thumbs_up_demo_ack = False
    brain.gesture_enabled = True
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))
    texts = [p.args.get("text", "") for p in _emitted_plans(brain)]
    assert any("你要我 WeGo 一下嗎" in t for t in texts)
    assert all("比 OK 我就做 wiggle" not in t for t in texts)  # 不再吐英文 skill 名

def test_gesture_enabled_gate_suppresses(brain):
    brain.gesture_enabled = False
    brain._on_gesture(_msg({"gesture": "thumbs_up"}))
    assert _emitted_plans(brain) == []  # gate 關 → 完全不發
```
> `_emitted_plans`/`_msg`/`brain` fixture 依該測試檔現有 helper 命名調整；若無 `_emitted_plans`，用該檔既有的 emit 攔截方式（多半 mock `brain._emit`）。

- [ ] **B-Step 2: 跑測試確認 fail**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -k "wego or gesture_enabled" -v`
Expected: FAIL（`gesture_enabled` 屬性不存在 / prompt 仍是「比 OK 我就做 wiggle」）。

- [ ] **B-Step 3: 加 `gesture_enabled` param + callback + early-return**

`brain_node.py` `__init__` declare 區（與既有 `thumbs_up_demo_ack` 等並列，~:266）：
```python
self.declare_parameter("gesture_enabled", True)
self.gesture_enabled = bool(self.get_parameter("gesture_enabled").value)
```
`__init__` 尾端加 runtime callback（brain 目前**沒有** `add_on_set_parameters_callback`，新增）：
```python
self.add_on_set_parameters_callback(self._on_set_params)
```
新 method：
```python
def _on_set_params(self, params):
    from rcl_interfaces.msg import SetParametersResult
    for p in params:
        if p.name == "gesture_enabled":
            self.gesture_enabled = bool(p.value)
            self.get_logger().info(f"gesture_enabled set to {self.gesture_enabled}")
    return SetParametersResult(successful=True)
```
`_on_gesture` 開頭（~:726 `if not gesture: return` 之後）加：
```python
if not self.gesture_enabled:
    return
```

- [ ] **B-Step 4: 確認 prompt 改 WeGo 特例**

`brain_node.py` 的 `_GESTURE_CONFIRM` 區塊（~:802-817），把：
```python
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": f"[curious] 比 OK 我就做 {skill}"},
                    source="rule:confirm_request",
                    reason=f"awaiting_ok:{skill}",
                )
            )
```
改成（thumbs_up→wiggle 特例 WeGo，其餘維持原泛用句）：
```python
            confirm_text = (
                "[curious] 你要我 WeGo 一下嗎？比 OK 我就開始。"
                if gesture == "thumbs_up"
                else f"[curious] 比 OK 我就做 {skill}"
            )
            self._emit(
                build_plan(
                    "say_canned",
                    args={"text": confirm_text},
                    source="rule:confirm_request",
                    reason=f"awaiting_ok:{skill}",
                )
            )
```

- [ ] **B-Step 5: `executive.yaml` 切兩步**

`interaction_executive/config/executive.yaml:20`：`thumbs_up_demo_ack: true` → `thumbs_up_demo_ack: false`。
（`gesture_direct_disabled: true`（:13）保留 → wave/fist/index 仍 trace-only，不誤觸。）

- [ ] **B-Step 6: 跑測試確認 pass**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -v`
Expected: PASS（含既有測試不回歸）。

- [ ] **B-Step 7: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add interaction_executive/interaction_executive/brain_node.py \
        interaction_executive/config/executive.yaml \
        interaction_executive/test/test_brain_rules.py
git commit -m "feat(brain): gesture two-step (thumbs_up→OK→WeGo) + gesture_enabled runtime gate"
```

> Studio On/Off 按鈕 = **P1**，今天不做（操作員 `ros2 param set /brain_node gesture_enabled false/true` 即可前段關、手勢 take 開）。

---

## Task C: Object Separate Wording + Cup Demo Mode

**Files:**
- Modify: `interaction_executive/config/executive.yaml:24`
- Modify: `interaction_executive/interaction_executive/brain_node.py:62`
- Test: `interaction_executive/test/test_brain_rules.py`

- [ ] **C-Step 1: 失敗測試 — cup 台詞含 weather + compound off 走分開句**

在 `test_brain_rules.py` 加：
```python
def test_cup_tts_has_weather_reminder():
    from interaction_executive.brain_node import build_object_tts
    assert build_object_tts("cup", "Unknown") == "看到杯子了，你要喝水嗎？今天天氣很熱，要記得補充水分。"

def test_compound_off_uses_separate_cup_remark(brain):
    # demo_video_cup_compound=False → 即使 Roy+sitting，也走分開的簡單 cup remark，
    # 不吐合併句「我看到 Roy 坐著拿著杯子」
    brain.demo_video_cup_compound = False
    brain._enter_engaged_for_test()          # 依測試檔既有方式把 attention 設 ENGAGED
    brain._on_object(_msg({"objects": [{"class_name": "cup", "color": "Unknown"}]}))
    texts = [p.args.get("text", "") for p in _emitted_plans(brain)]
    assert all("坐著拿著杯子" not in t for t in texts)
    assert any("你要喝水嗎" in t for t in texts)
```
> 若測試檔沒有現成把 attention 設 ENGAGED 的 helper，用該檔既有方式（多半直接 set `brain._attention` state 或 mock `_attention_state_snapshot`）；object_remark 的 ENGAGED gate 見 `brain_node.py:1235`。

- [ ] **C-Step 2: 跑測試確認 fail**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -k "cup or compound" -v`
Expected: FAIL（cup 台詞還沒有 weather 句）。

- [ ] **C-Step 3: cup suffix 加 weather 句**

`brain_node.py:62`：
```python
    "cup": "，你要喝水嗎？",
```
改成：
```python
    "cup": "，你要喝水嗎？今天天氣很熱，要記得補充水分。",
```
> 產出 `build_object_tts("cup","Unknown") == "看到杯子了，你要喝水嗎？今天天氣很熱，要記得補充水分。"`。
> ⚠️ weather 是**腳本情境句，非即時查天氣** —— 旁白/字幕不可宣稱即時查。
> 若 Roy 要逐字「**我**看到杯子了」前綴：改 `:114` `f"看到{class_zh}了"` → `f"我看到{class_zh}了"`（影響所有物體，但 demo 是 cup-only，可接受）；本 plan 預設**不改前綴**。

- [ ] **C-Step 4: `executive.yaml` 關 compound**

`interaction_executive/config/executive.yaml:24`：`demo_video_cup_compound: true` → `demo_video_cup_compound: false`。
（greet 與 cup remark 從此**分開觸發**：S2「Roy，歡迎回來。我看到你坐下來了。」/ S3「看到杯子了，你要喝水嗎？今天天氣很熱…」。）

- [ ] **C-Step 5: 跑測試確認 pass**

Run: `cd /home/roy422/newLife/elder_and_dog && python3 -m pytest interaction_executive/test/test_brain_rules.py -v`
Expected: PASS（含既有不回歸）。

- [ ] **C-Step 6: Commit**

```bash
cd /home/roy422/newLife/elder_and_dog
git add interaction_executive/interaction_executive/brain_node.py \
        interaction_executive/config/executive.yaml \
        interaction_executive/test/test_brain_rules.py
git commit -m "feat(brain): cup demo wording + weather reminder + separate greet/cup (compound off)"
```

---

## 部署（兩套 stack 分開拍，**不假設 full stack 同跑** — 8GB nav/brain 互斥）

> ⚠️ S1 nav take 與 S2–S5 brain/vision take 是**兩套互斥 stack**。切 take 間必須 `pawai demo stop` + `ros2 node list` 歸零，再起另一套（兩套都開過 D435，防殘留）。**不要 `pawai demo start` 一次就想錄全部。**

- [ ] **D-Step 1: 同步源碼 + brain colcon build**

```bash
# rsync 只搬源碼，不會 rebuild install/ → brain 必 colcon build
ssh jetson-nano 'cd ~/elder_and_dog && source /opt/ros/humble/setup.zsh && \
  colcon build --packages-select interaction_executive && source install/setup.zsh'
```
Expected: `Finished <<< interaction_executive`。Studio gateway/前端非 colcon 包，rsync 即生效。

- [ ] **D-Step 2a: S2–S5 brain/vision take stack（vision 開、nav 關）**

```bash
~/.venv/bin/pawai demo stop
~/.venv/bin/pawai demo start          # brain-studio-lane：5 perception + brain + asr/tts/llm + gateway
```
Expected: `ros2 node list` 含 brain_node + studio_gateway_node + object/face/vision；`tmux ls` 有 demo session。用於 S2 認人坐姿 / S3 杯子 / S4 手勢 / S5 安全拒絕。**此 stack 不含 nav stack**（Studio nav 面板此時無 pose，正常）。

- [ ] **D-Step 2b: S1 nav take stack（nav 開、vision 關）+ Studio gateway/frontend**

```bash
~/.venv/bin/pawai demo stop && ssh jetson-nano 'ros2 node list'    # 確認歸零
# nav stack（窄場安全 profile）
ssh jetson-nano 'cd ~/elder_and_dog && REACTIVE_PROFILE=indoor_tight \
  MAP=/home/jetson/maps/home_living_room_v8.yaml bash scripts/start_nav_capability_demo_tmux.sh'
# 另起 Studio gateway（nav stack 不含 gateway）+ 本機 frontend
ssh jetson-nano 'cd ~/elder_and_dog && source install/setup.zsh && python3 pawai-studio/gateway/studio_gateway.py' &
bash pawai-studio/start.sh   # 或 frontend .env.local 指 Jetson gateway
```
Expected: AMCL active（`ros2 lifecycle get /amcl`）、`/capability/nav_ready`=true、Studio nav 面板出現 pose 三角形。用於 S1 移動進場。gateway 用 `QOS_NAV_LATCHED` 才吃得到 latched `/amcl_pose`。

---

## 錄前 HITL Smoke（需 Roy + Go2/Jetson，逐項過才錄對應 take）

- [ ] cup 0.7m re-confirm：手持杯子，`ros2 topic echo /event/object_detected` 連續出 cup（沿用 0.35 門檻，5 次 ≥4）
- [ ] thumbs_up → 「你要我 WeGo 一下嗎？」→ 比 OK → wiggle(1020) 真的扭
- [ ] greet：Roy 坐下 → 「Roy，歡迎回來。我看到你坐下來了。」（sitting 抖 → `ros2 param set /brain_node greet_require_sitting false`）
- [ ] Studio nav 驗收 B：起 nav stack（`REACTIVE_PROFILE=indoor_tight`）→ AMCL active → Studio 三角形對到 Go2 真實相對位置 + 朝向；推 0.3m 三角形同向移動；遮 LiDAR 變紅
- [ ] safety refusal：Studio text_input 打「翻跟斗」→ 紅 BLOCKED + 「這個動作不安全，我不能執行」+ Go2 不動
- [ ] gesture_enabled gate：`ros2 param set /brain_node gesture_enabled false` → 比讚無反應；設 true → 恢復

> nav stack 與 full demo **8GB 互斥**：S1 nav take 與 S2–S5 vision take **分開拍**，切 take 間 `pawai demo stop` + `ros2 node list` 歸零再起另一套。

---

## Backlog（不今天做，寫成後續票）

- **PawAI CLI 重構**：Typer + Rich + pipx（老師 laptop `pipx install`）；face CLI `list/enroll/delete(先 backup)/rebuild/test`（帶去學校讓老師/同學加臉）
- **Studio depth 小畫面**（P1，map panel 穩了再加；新 video bridge JPEG encode 壓在 8GB 最緊的 nav take）
- **Studio gesture On/Off 按鈕**（P1，比 depth 優先）
- **動態 goal**（fast-follow，需動 nav_action_server 加 resolved-goal publisher，風險高）
- **地面判斷**（P2，D435 depth + ground plane）
- **vision-driven person approach**（P2/P3，face/person bbox + depth + map transform + nav goal）

---

## Self-Review

**1. Spec coverage：**
- Studio nav panel（map+pose+goal+line+status）→ Task A ✓；不做 move-button/depth/dynamic-goal/3D → A 範圍 + Backlog ✓
- 手勢兩步確認 + gesture_enabled gate + 其他手勢 trace-only + WeGo 台詞 → Task B ✓；Studio toggle P1 → Backlog ✓
- 物體分開句（compound off）+ cup weather 台詞 + cup 0.7m 手持 + chair 備援 → Task C（chair 備援是錄影選擇，無 code，已在 demo flow 記憶）✓
- 錄前 smoke（cup/手勢/sitting/Studio pose/safety）→ HITL Smoke 段 ✓
- 不做 CLI/動態goal/地面/person-approach → Backlog ✓

**2. Placeholder scan：** 無 TBD/「類似 Task N」；大段 gateway/canvas code 引用 buildspec 章節（該文件已逐行）；小段 config/台詞/test code 內聯完整。✓

**3. Type consistency：** envelope `event_type` 全程短名 `pose`/`reactive_stop`/`paused`（gateway A5 ↔ 前端 A6 ↔ buildspec §1A 警示一致）；`DEMO_MAP` origin 全用 **v8 `[-2.41,-2.81]`**（非 v7）；`gesture_enabled`/`thumbs_up_demo_ack`/`demo_video_cup_compound` 屬性名與 yaml key 一致；y-flip 在 A7 與 buildspec §2 都強調「只一次」。✓
