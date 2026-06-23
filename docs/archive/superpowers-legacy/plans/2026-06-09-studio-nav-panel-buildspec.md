# PawAI Studio Nav 面板 — 今天 build-ready 規格

> 來源：workflow `wrcpdq62j`（4 agents）。Scope freeze：map 底圖 + pose 三角形 + 固定 goal + current→goal 直線 + 狀態 chip。三個新 sub 全 read-only、零 publisher，不碰 nav 控制權。
> **單一真相圖 = v8**（`start_nav_capability_demo_tmux.sh:23` 預設）：`home_living_room_v8.yaml`，PGM `205×98 px`、`resolution: 0.05`、`origin: [-2.41, -2.81, 0]`、`negate: 0`。
> ⚠️ 有一份 finding 用了 v7（`origin: [-7.79, -2.46]`、207×98）— **舊圖，全部以 v8 為準**（見 §4 風險 2）。

---

## 1. 今天 code checklist

### 1A. Gateway — `pawai-studio/gateway/studio_gateway.py`（829 行）

沿用既有 `_on_capability_msg` 的 synthetic-event envelope + `ws_manager.broadcast` + `asyncio.run_coroutine_threadsafe`。新 envelope 的 `source` 統一 `"nav"`。

**鐵律（最大的坑）**：`/amcl_pose` 與 `/state/nav/paused` 都是 **RELIABLE + TRANSIENT_LOCAL（latched）**。現有 `QOS_EVENT`（line 65-69）是 VOLATILE，直接訂 → QoS 不相容 → **永遠收不到**。必須自帶 latched profile。`/state/reactive_stop/status` 是普通 VOLATILE depth=10，用 `QOS_EVENT` 即可。

| 步 | 內容 | 插入於 line 之後 |
|---|---|---|
| A1 | `from geometry_msgs.msg import PoseWithCovarianceStamped` | 33 |
| A2 | `QOS_NAV_LATCHED` + `POSE_THROTTLE_S` 常數 | 69 |
| A3 | `self._last_pose_broadcast = 0.0` | 164 |
| A4 | 三個 `create_subscription` | 210 |
| A5 | 四個 method（`_quat_to_yaw`/`_broadcast_nav`/三 callback） | 276 |
| B1 | `MAP_YAML_PATH` config（`PAWAI_MAP_YAML` override） | 60 |
| B3 | `app.mount("/map", StaticFiles...)` | 450 |
| B2 | `/api/map_meta` REST + `_read_map_meta` | 467 |

**A2 — latched QoS（load-bearing）**
```python
QOS_NAV_LATCHED = QoSProfile(
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
    depth=1,
)
POSE_THROTTLE_S = 0.2  # /amcl_pose ~10Hz → 節流 5Hz
```

**A4 — 三個 sub（注意 QoS 配對）**
```python
self.create_subscription(PoseWithCovarianceStamped, "/amcl_pose",
                         self._on_amcl_pose, QOS_NAV_LATCHED)        # latched!
self.create_subscription(String, "/state/reactive_stop/status",
                         self._on_reactive_stop_status, QOS_EVENT)   # VOLATILE ok
self.create_subscription(Bool, "/state/nav/paused",
                         self._on_nav_paused, QOS_NAV_LATCHED)       # latched!
```

**A5 — pose callback（quaternion→yaw + throttle + envelope）**
```python
@staticmethod
def _quat_to_yaw(qz, qw, qx=0.0, qy=0.0):
    import math
    return math.atan2(2.0*(qw*qz + qx*qy), 1.0 - 2.0*(qy*qy + qz*qz))

def _broadcast_nav(self, event_type, data):
    envelope = {"id": str(uuid.uuid4()),
                "timestamp": datetime.now().astimezone().isoformat(),
                "source": "nav", "event_type": event_type, "data": data}
    asyncio.run_coroutine_threadsafe(ws_manager.broadcast(envelope), self._loop)

def _on_amcl_pose(self, msg):
    now = time.monotonic()
    if now - self._last_pose_broadcast < POSE_THROTTLE_S:
        return
    self._last_pose_broadcast = now
    p, q, c = msg.pose.pose.position, msg.pose.pose.orientation, msg.pose.covariance
    self._broadcast_nav("pose", {                       # ← event_type = "pose"
        "x": round(float(p.x), 4), "y": round(float(p.y), 4),
        "yaw": round(self._quat_to_yaw(q.z, q.w, q.x, q.y), 4),
        "covariance_xy": round(float(c[0] + c[7]), 5)})
```
reactive_stop callback 抽 `zone`(`clear/slow/danger/emergency`) / `obstacle_distance`(float|None) / `reactive_stop_active` / `nav_paused`，發 `event_type="reactive_stop"`；nav_paused callback 發 `event_type="paused"` `{"paused": bool(msg.data)}`。

> ⚠️ **event_type 命名鎖死**：gateway 發 `pose` / `reactive_stop` / `paused`（短名），前端 §1B 的 `switch (event_type)` 必須完全對齊。

**B2 — `/api/map_meta`**：純手解 yaml（不引 yaml dep），回 `{ok, resolution, origin:[x,y,θ], negate, image, image_url}`，`image_url = "/map/" + image`。
**B3 — StaticFiles**：`app.mount("/map", StaticFiles(directory=str(MAP_YAML_PATH.parent)))`。
**坑**：map.yaml 的 `image` 指向 `.pgm`，瀏覽器不認 → 前端把 `image_url` 的 `.pgm` replace 成 `.png`。今天不改 map 產線。

### 1B. 前端 — `pawai-studio/frontend/`

**前置（必做，否則底圖空白）**：`public/maps/` 目前**不存在**。
```bash
mkdir -p /home/roy422/newLife/elder_and_dog/pawai-studio/frontend/public/maps
cp /home/roy422/newLife/elder_and_dog/docs/archive/navigation-legacy/research/maps/home_living_room_v8.png \
   /home/roy422/newLife/elder_and_dog/pawai-studio/frontend/public/maps/home_living_room.png
```

| 步 | 檔案 | 內容 |
|---|---|---|
| A1-A4 | `stores/state-store.ts` | `NavPose`/`NavReactiveStop` 型別 + `navPose`/`navReactiveStop`/`navPaused` + 初始值 + `updateNav(patch)` |
| A5-A7 | `hooks/use-event-stream.ts` | 取 `updateNav` + `case "nav"` 分流（`switch` → `pose`/`reactive_stop`/`paused`）+ deps 補 `updateNav` |
| A8 | `contracts/types.ts` | `NavEvent`（可選） |
| B | `components/navigation/nav-map-canvas.tsx` | **新檔**，Canvas2D 自包含（不引 ros3djs） |
| C1-C2 | `components/navigation/navigation-panel.tsx` | import `NavMapCanvas` + 替換 Section 3 placeholder（原 86-94 行） |

**A6 — `case "nav"` 分流**
```ts
case "nav":
  if (event.event_type === "pose") {
    if (typeof data.x === "number" && typeof data.y === "number")
      updateNav({ pose: { x: data.x, y: data.y,
        yaw: typeof data.yaw === "number" ? data.yaw : 0 } });
  } else if (event.event_type === "reactive_stop") {
    const z = data.zone;
    updateNav({ reactiveStop: {
      zone: z === "danger" || z === "slow" ? z : "clear",
      front_distance_m: typeof data.obstacle_distance === "number" ? data.obstacle_distance : null,
      nav_paused: Boolean(data.nav_paused) } });
  } else if (event.event_type === "paused") {
    updateNav({ paused: Boolean(data.paused) });
  }
  break;
```

**B — `nav-map-canvas.tsx` demo 常數（v8）**
```ts
export const DEMO_MAP = {
  src: "/maps/home_living_room.png",
  resolution: 0.05,
  originX: -2.41,   // ← v8（不是 v7 的 -7.79）
  originY: -2.81,   // ← v8（不是 v7 的 -2.46）
};
export const DEMO_GOAL = { x: 1.2, y: 0.6 };  // 依場地校正
```
canvas backing store 設 PNG 原生像素（205×98），視覺縮放交 CSS + `imageRendering: "pixelated"`。三角形顏色跟 `navReactiveStop.zone` 走（綠 clear / 黃 slow / 紅 danger）。

---

## 2. map 座標換算公式 + 校準步驟

設 `res=0.05`、`(ox,oy)=(-2.41,-2.81)`、`H=98`（PGM height）。
```
col        = (world_x - ox) / res          # 螢幕 x（左→右，不翻）
row_bottom = (world_y - oy) / res          # grid 原生（下緣起算）
canvas_px  = col
canvas_py  = (H - 1) - row_bottom          # ← y 翻轉（只能出現一次）
```
反向（點圖發 goal 用）：
```
world_x = ox + canvas_px * res
world_y = oy + ((H - 1) - canvas_py) * res
```
縮放因子 `s` 最後乘：`canvas_px=col*s`、`canvas_py=((H-1)-row_bottom)*s`。

**三角形朝向**：`screenAngle = -yaw`。map +yaw 逆時針，影像 y 向下、螢幕變順時針，取負才畫對 —— **最容易畫反**。

**v8 驗算**：world `(0,0)` → `col=48.2`、`row_bottom=56.2`、`canvas_py=97-56.2=40.8` → canvas `(48, 41)`；canvas `(0,0)` → world `(-2.41, +2.09)`；圖左下角 = origin `(-2.41,-2.81)` ✓

**negate 不動座標**：`negate:0` = 深色牆/淺色空地。黑白顛倒是 negate 語意問題，**別碰 y-flip**。

### 校準步驟（鏡像/上下顛倒排錯）
1. 取 world ground-truth 點（map 原點 `(0,0)` 或已存 named pose），算 `(canvas_px,canvas_py)` 畫紅點。
2. **截圖**對照底圖牆線：左右相反→多做 x 翻轉(拿掉)；上下相反→y-flip 漏或做兩次(`(H-1)-row_bottom` 只能一次)；整體平移→origin sign 錯或用了 width(205) 當 height(98)。
3. 加第二方向點（如 `(1.0,0.0)` 應在原點右 +20px 同列）— 單點分不出對稱錯。
4. 鎖定後校準截圖存 `docs/archive/navigation-legacy/research/maps/` 當回歸基準。

### PGM→PNG（換圖時）
```bash
python3 -c "from PIL import Image; Image.open('home_living_room_v8.pgm').save('home_living_room_v8.png')"
```

---

## 3. 去學校 pre-scan SOP

> **鐵律 S1：絕不用即時 SLAM 當 demo 主線。** 圖必須在家離線掃好存靜態檔，當天只跑 AMCL 在靜態圖上定位（`slam:=false`，script 預設）。

### 階段 0：在家掃圖（去學校前，環境安靜）
1. **先備份舊圖**：
   ```bash
   ssh jetson-nano 'TS=$(date +%Y%m%d-%H%M%S); for e in yaml pgm pbstream; do s="/home/jetson/maps/home_living_room_v8.${e}"; [[ -f "$s" ]] && cp "$s" "${s}.bak.${TS}"; done; echo ok'
   ```
2. `bash scripts/build_map.sh school_demo`，等 ~10s（pure scan-matching，不啟 Go2 driver）。
3. **遙控 Go2 慢走整圈**：≤0.15 m/s、30–60s、**含閉環回原點**。TF `base_link→laser yaw=π`（雷達反裝）已內建，別改。物理錨定用「人站 Go2 鼻尖前 0.5m 看 angle bin」，別用物體放置法（v7 偽陽性教訓）。
4. **存圖三步驟（順序不可亂）**：
   ```bash
   ros2 service call /finish_trajectory cartographer_ros_msgs/srv/FinishTrajectory "{trajectory_id: 0}"
   ros2 service call /write_state cartographer_ros_msgs/srv/WriteState \
     "{filename: '/home/jetson/maps/school_demo.pbstream', include_unfinished_submaps: true}"
   ros2 run nav2_map_server map_saver_cli -f /home/jetson/maps/school_demo \
     --ros-args -p map_subscribe_transient_local:=true
   ```
   `tmux kill-session -t lidar-slam`。
5. **離線檢查圖品質**：牆連續無鬼影雙牆、閉環接上、`Image.open('school_demo.pgm').save('/tmp/school_demo.png')` 看一眼。破圖就重掃。

### 階段 1：在家存 demo 目標點（圖剛掃完、定位還準）
1. `REACTIVE_PROFILE=indoor_tight MAP=/home/jetson/maps/school_demo.yaml bash scripts/start_nav_capability_demo_tmux.sh`，等 ~50s。
2. Foxglove 設 `/initialpose` 到 Go2 真實位置+朝向，物理推 0.3m 幫 covariance 收斂。
3. 牽 Go2 到目標點站好，存 named pose：
   ```bash
   ros2 action send_goal /log_pose go2_interfaces/action/LogPose "{name: 'roy_demo_spot', log_target: 'named_poses'}"
   ```
   **存完馬上回讀**：`ssh jetson-nano 'cat ~/elder_and_dog/runtime/nav_capability/named_poses/main.json'`。
4. **整套帶去學校**：`school_demo.{pgm,yaml,pbstream}` + `named_poses/main.json`（座標綁這張圖，換圖即失效）+ `school_demo.png`（Studio 底圖）。

### 階段 2：當天在學校（同圖、現場重定位 + CLI 發 goal）
1. 起同一套指同一張圖（**不開 SLAM**）。
2. Foxglove 設 `/initialpose` 到學校真實起點+朝向。等 60–90s 或推 0.3m。確認 `ros2 lifecycle get /amcl`=active、`/capability/nav_ready`=true。
3. **CLI 發 goal**（走 action，**不要 `ros2 topic pub /goal_pose`**）：
   ```bash
   ros2 action send_goal /nav/goto_relative go2_interfaces/action/GotoRelative "{distance: 0.5}"
   ros2 action send_goal /nav/goto_named go2_interfaces/action/GotoNamed \
     "{name: 'roy_demo_spot', standoff: 0.0, align_yaw_to_target: true}"
   ```
   短目標接龍最穩（兩個 0.5m > 一個 1.0m）。

### 當天紀律
不開 SLAM；kill teleop；**窄場禁 auto-resume**（6/9 lunge，台詞退「操作員確認/遙控輔助」）；orphaned goal 靠 `no_progress_timeout`(~10s) 自癒、真卡死才重啟 navcap；Go2 用 Ethernet `192.168.123.161` 避 OTA；重啟前 `pkill -9 go2_driver; pkill -9 robot_state; pkill -9 pointcloud`。

---

## 4. 風險

1. **🔴 座標翻轉（最高頻 bug）**：y-flip 只做一次。三角形朝向忘了 `-yaw` → 看起來「倒退走」。§2 校準沒驗過不上場。
2. **🔴 v7/v8 origin 漂移**：`DEMO_MAP` 常數、`/api/map_meta` 的 yaml、`public/maps` PNG **三者必須同一張圖**。去學校換 `school_demo` 後三者一起換。
3. **🟠 gateway 必須跟 nav stack 一起起**：latched topic，AMCL 沒起 → 面板全空（不報錯）。順序：先 nav stack 等 lifecycle active，**再**起 gateway。
4. **🟠 QoS 不相容靜默失敗**：latched 配 VOLATILE 不報錯只收不到。debug 先 `ros2 topic echo /amcl_pose --once`。
5. **🟡 頻寬**：已 `POSE_THROTTLE_S=0.2` 節流 5Hz。**別拿掉 throttle**。
6. **🟡 map.pgm 瀏覽器不認**：`image_url` replace `.pgm`→`.png`，PNG 先 cp 進 `public/maps/`。
7. **🟡 event_type 命名**：gateway/前端都用短名 `pose`/`reactive_stop`/`paused`。

---

## 5. 驗收

**A — 無 gateway 純前端煙測**（先做）：`bash pawai-studio/start.sh` → console 灌 mock：
```js
useStateStore.getState().updateNav({ pose: { x: 0, y: 0, yaw: 0 } });          // 應落 canvas ~(48,41)
useStateStore.getState().updateNav({ pose: { x: 0, y: 0, yaw: Math.PI/2 } });  // 尖端朝上(非下)→證明 -yaw 對
useStateStore.getState().updateNav({ reactiveStop: { zone: "danger", front_distance_m: 0.8, nav_paused: true } });
```
通過：①原點落 ~(48,41) ②yaw=0 朝右、π/2 朝上 ③`x=1.0` 往右 ~20px 同列 ④danger 變紅。

**B — 接真 gateway + nav stack**：AMCL active → `ros2 topic echo /amcl_pose --once` 有資料 → 面板三角形出現 → 人肉對照 Go2 真實相對位置 + 朝向 → 推 0.3m 同向移動 → 遮 LiDAR 變紅 + paused chip 亮。

**回歸基準**：驗收 A 原點+方向點截圖存 `docs/archive/navigation-legacy/research/maps/`，換圖後重跑對照。

---

**改到的檔案**
- `pawai-studio/gateway/studio_gateway.py` — §1A A1-A5 + B1-B3
- `pawai-studio/frontend/stores/state-store.ts` — nav 欄位 + `updateNav`
- `pawai-studio/frontend/hooks/use-event-stream.ts` — `case "nav"`
- `pawai-studio/frontend/contracts/types.ts` — `NavEvent`（可選）
- `pawai-studio/frontend/components/navigation/nav-map-canvas.tsx` — 新檔（`DEMO_MAP` v8）
- `pawai-studio/frontend/components/navigation/navigation-panel.tsx` — Section 3 換掉
- `pawai-studio/frontend/public/maps/home_living_room.png` — **需先 cp**（v8，目前不存在）
