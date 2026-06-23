# 2026-06-07 NAV + OBJECT 深度研究行動報告（deep research 產出）

> **產出方式**：13-agent workflow（調查 → 對抗式查證 → 綜整）。13 agents。
> **focus**：6/18 兩大核心 = 導航避障 + 物體辨識加強。建立在現有 docs（PINTO 482 模型分析 / nav 研究史）上加深、只用現成模型、所有結論已對當前分支核對 file:line。
> **誠實鐵律**：能做到才說能；物理限制（cup 像素預算 / Go2 MIN_X / 8GB 互斥 / D435 4/3 教訓）照實納入。
> **狀態**：研究結論，未實機驗證的項目標 stretch；NAV 現場驗證待 HITL。

---

所有關鍵 file:line 證據在當前分支核對通過:`MAX_LINEAR_X = 0.5` 硬 clamp（robot_control_service.py:16,50）、最大地圖 v3=234×178=41,652 cells、danger/slow init-only。查證結果與當前工作樹一致。以下產出報告。

---

# PawAI 6/18 Demo 決定報告 — NAV + OBJ 兩大核心

> 今天 6/7,剩 11 天。下面全是查證後 confirmed/corrected 的版本,不是開放探索。每項都標可行性 + effort + 誰能做。
> 證據已對當前分支 (`docs/2026-06-05-architecture-refresh`) 重新核對,以下 file:line 全部成立。

---

## TL;DR — 兩大核心最終決定

**導航避障 (NAV):整體 6/18 可行性 = low。能宣稱的只有 `nav.safe_stop`(障礙進場→Go2 停車→TTS),不能宣稱「Go2 自走/繞障」。** F7「goto 零位移 ABORT」的根因**不是 Nav2 stack bug**(5/27 已證 stack healthy),而是 **safety 層 `reactive_stop_node` 預設 danger=1.1m 在窄場常態誤判**,把 nav 輸出經 twist_mux(obstacle 200 > nav 10)壓成 0 → 10s no_progress ABORT。唯一有實證的可展示鏈路是 5/12 的「0.81m 進 danger 停、未撞」(project-status.md:275)。動態繞障在 11 天內**做不到可重現**(物理層 reactive_stop `angular.z` 寫死 0、controller 層 DWB 5/3 不可重現 + MPPI 從零 tuning + MIN_X 衝突),列為 future work。地圖/光達視覺化**走 Foxglove-web(0 code)**,不要塞進 Studio。

**物體辨識 (OBJ):整體 6/18 可行性 = medium(換模型) / 但預設決定 = 維持現狀 KEEP_CURRENT(零風險過 cup 段)。** 「沒換模型」不是失誤,是 6/05 主動收斂的決策(demo-production-plan:138)。小物偵測的瓶頸是**像素物理不是模型**:9cm 杯 @2m 在 640 input 下只有 21px,換骨幹(26s/RF-DETR)補的是「同 21px 下判別力」,補不了「只有 21px 資訊量」。真正對症的是提高輸入解析度(960 把像素翻倍到 32px),但這會推翻已收斂決策、且能否過 gate 完全未量測,需 Roy 拍板。**coco_detector(torchvision FasterRCNN)明確不採用**(mAP 22.8 vs YOLO26n 40.1、會破壞 Jetson torch wheel)。掉落物地面判定 = 加分項 low,主推維持「桌上有杯子」純 2D 口白。

---

## 🎯 優先行動清單 (P0 → P2,跨兩 track 排序)

| # | 行動 | effort | 6/18 可行性 | 誰可做 |
|---|------|--------|:-----------:|--------|
| **P0-1** | **鎖定 demo 敘事:主秀押 brain 互動(70%),nav 段只宣稱 `safe_stop`+TTS,OBJ 鎖 cup-only ~1m「桌上有杯子」** | 0.5 天 | high | Roy 拍板(決策) |
| **P0-2** | **OBJ 預設決定:維持 YOLO26n@640 不動,擴 `class_whitelist` 認更多近距大物撐「看懂環境」敘事** | ~30 分 | high | Codex AFK(改 config/launch) |
| **P0-3** | **NAV 現場 30 分驗證(無需改 code):起 nav-capability stack,發 goto_relative 0.5m,同步 echo `/state/reactive_stop/status` + `ros2 topic hz /cmd_vel_unsmoothed` /cmd_vel_nav** | 0.5 天(含進場) | — | **需 HITL**(Roy + Go2 + Jetson) |
| **P1-1** | **NAV safe_stop 鏡頭:現場重啟 `reactive_stop_node` 帶 `-p danger_distance_m:=0.85 -p slow_distance_m:=1.30 -p front_arc_deg:=30`(danger/slow 是 init-only,param set 無效),寬場放椅子驗 0.8m 停** | 1–1.5 天 | medium | **需 HITL** |
| **P1-2** | **供電 go/no-go:demo 前跑 60min 連續供電壓測,用 2464/KREE 獨立電源不靠 XL4015** | 含在 P1-1 | — | **需 HITL** |
| **P1-3** | **Foxglove-web 地圖/光達分鏡:Mac 開 app.foxglove.dev → ws://jetson:8765,存 layout .json(Map+LaserScan+pose)+SOP** | 0.5 天 | high | Codex AFK(存 layout/寫 SOP) + 1 次連線測 |
| **P2-1** | **(僅 Roy 批准 B 案才做)OBJ 960 重匯:WSL export imgsz=960 → scp → 量測判 gate** | 0.5–1 天 | medium | Codex(WSL export) + HITL(量測) |
| **P2-2** | **(僅主 demo 排練完有餘力)NAV 動態繞障嘗試 — 必先修 F7,goto 1.0m 通才有資格談** | +4–5 天,成功率低 | low/stretch | **需 HITL** |
| **P2-3** | **(加分,有餘力)OBJ 掉落物地面判定:抄 face_identity median depth + deproject + 高度閾值** | 1–1.5 天 | low | Codex(寫 node)+ HITL(量測) |

> **Codex AFK 可做**:P0-2 改 config、P1-3 存 layout/SOP、P2-1 WSL export、P2-3 寫 node 框架。
> **必須 HITL(上機)**:所有 NAV 現場驗證/重啟(P0-3/P1-1/P1-2/P2-2)、所有需量 RAM 共存與 Go2 motion 的項。

---

## Part A — 導航避障

### A1 — F7 根因與修復路徑

**既有結論摘要**:F7 = `goto_relative 1.0m` → goal accepted 但 10s no_progress ABORTED、actual_distance=0.0。5/27 已證 Nav2 stack healthy。

**修正後的根因鏈(high confidence,證據紮實)**:
- `reactive_stop_node` 預設 `danger_distance_m=1.1`(reactive_stop_node.py:74)、`slow_distance_m=1.7`(:75)是 **LiDAR 視距**,窄場常態誤判 danger → 發 `/cmd_vel_obstacle=0`。
- twist_mux obstacle priority **200** > nav **10**(twist_mux.yaml:26–36)→ 壓掉 nav 輸出 → Go2 不動 → `nav_action_server_node.py:235–282` 落入 no_progress 判定 → `PROGRESS_TIMEOUT_S=10.0` → ABORT。
- project-status.md:277 實證「1.1m danger 在 0.81m 觸發停車」= 常態早停。

**降級修正(避免誤導團隊)**:
- ❌ **Finding #3「缺 velocity_smoother section 是 F7 根因」是誇大,降為 config 顯式化建議**。理由:Go2 driver 本身已硬 clamp x 到 `MAX_LINEAR_X = 0.5`(robot_control_service.py:16,50),補 velocity_smoother `max=0.70` **無法把實際速度拉過 driver 的 0.5 clamp**;缺 config section 也**不會害 lifecycle activate 失敗**(node 用內建預設仍正常 activate)。它是 config 衛生,不是 F7 zero-displacement 根因。
- ❌ **「`/cmd_vel_nav` 無 publisher」原診斷誤記**。正確鏈路:controller_server → `/cmd_vel_unsmoothed` → velocity_smoother → `/cmd_vel_nav`(navigation_remap.launch.py:20–36/147/213–215)。**正確驗證 topic 是 `/cmd_vel_unsmoothed`**。

**怎麼驗(現場第一件事,30 分,無需改 code)**:
1. 起 nav-capability stack,發 `ros2 action send_goal /nav/goto_relative ... distance:0.5`。
2. 同步看三個東西:
   - `ros2 topic echo /state/reactive_stop/status` — zone 一啟動就 = `danger`? → 確診根因 #1。
   - `ros2 topic hz /cmd_vel_unsmoothed` 與 `/cmd_vel_nav` — `/cmd_vel_unsmoothed` 有值但 `/cmd_vel_nav` 空 → velocity_smoother 異常(Finding #2 驗證點)。

**怎麼修(若要做 safe_stop 鏡頭)**:現場直接重啟 `reactive_stop_node`:
```bash
ros2 run go2_robot_sdk reactive_stop_node --ros-args \
  -p danger_distance_m:=0.85 -p slow_distance_m:=1.30 -p front_arc_deg:=30
```
⚠️ **danger/slow 是 init-only**,`ros2 param set` 無效(`_on_param_change` 只認 `enable_nav_pause`/`safety_only`,reactive_stop_node.py:175/180),**必須重啟 node**。
⚠️ **不要依賴 `start_nav_capability_narrow_field_tmux.sh` / `REACTIVE_DANGER_M` env** — 已核實:這些 BD-7D blessed wrapper **不在 main、不在當前分支**(只在 `feat/nav-metrics-ladder`)。當前 scripts/ 只有 `start_nav_capability_demo_tmux.sh`(預設 danger=1.1)+ `_detour`。要用要先 cherry-pick(額外 git + colcon build + rsync,風險非零),不如現場手動帶 param。

**不要踩的死路**:
- ❌ 不要靠 `enable_nav_pause=false` 救 F7:它只拿掉 pause/cancel/re-send,danger zone 內 obstacle=0 仍經 mux 壓停 → no_progress 10s ABORT 照樣觸發(pause-check 在 progress-check 之前,nav_action_server_node.py:259 < :268)。**真正解是降 danger 讓窄場不誤判。**
- ❌ 不要把 F7 當 Nav2 stack bug 去 debug controller_server(5/27 已證 healthy)。
- ❌ `danger < 0.75m` 不可降(5/11 撞牆教訓:LiDAR 0.6m 時 Go2 機鼻只剩 0.2m,CLAUDE.md:486)。

### A2 — 動態繞障 6/18 可行性 + fallback

**結論:low/stretch,維持 future work。** 三層收斂全部站得住:
- **物理層**:`reactive_stop_node._publish()` 只發 `linear.x`、`angular.z=0.0` 寫死(:264–268),`decide_velocity` 全鏈無任何 angular 計算 → **物理上不可能繞**。
- **controller 層**:RPP 只停不繞(官方確認);MPPI 是唯一真會繞的 controller,但 — **修正:MPPI Orin 性能數據誇大**。investigation 寫的「Orin NX ~6.7ms/~500MB」無來源,discourse 36652 的 6.8ms 是「未揭露平台」CPU/AVX2 benchmark,Jetson Orin 在原文只是「could enable use on platforms like Jetson Orin」的展望,**無任何 Orin Nano 8GB MPPI 實測**。配 Go2 MIN_X 0.5 + GitHub #5375(MPPI diff-drive 近距收尾差)→ 從零 tuning 在 11 天內 = stretch。
- **阻斷層**:DWB 5/3 多輪實測繞行**不可重現**(R1 試繞、R2 直接放棄/no-op,dynamic-obstacle-demo.md:96–106/172/243–244)= 調參玄學,非工程確定性。F7 未解,任何繞障計畫立即停。

**事故史(根因已修但邏輯仍在)**:5/2 試 detour 時 DWB 繞弧進 reactive danger zone 被 mux 切 0 → trot gait 急停 + 誤送 Damp(1001) → Go2 摔倒。v4 已改 emergency_stop engage + StopMove(1003)後 0 摔,但「繞行軌跡天然逼近障礙易踩雷」論點仍成立。

**修正:供電風險用了過時最壞數據。** investigation 引 4/26 斷電 + 4/29 3 次跳電,但同 repo CLAUDE.md:146 記載 4/29 night 已升級 2464 模組後穩定、project-status 多次連續動態測試沒跳電。**等級從「反覆斷電」降為「需獨立電源 + 60min 壓測驗證」**(仍是 demo-day footgun)。

**Fallback(由穩到險,強推 A)**:
- **(A)** 停障 + TTS「前面有東西我先停下」,包成守護犬安全意識故事。**這是唯一工程確定性高的路線。**
- **(B)** 預放椅子固定位 + SmacPlanner 一次性規劃繞過已知椅子的弧線(不依賴即時 replan),誠實標「規劃示範」。
- **(C)** teleop 繞行 + 旁白。
- ❌ **完全不要嘗試「人即時推椅子進路徑 + Go2 即時 replan 繞開」**(5/2 已因此摔狗)。

### A3 — Studio 網頁地圖/光達:選哪個方案

**決定:走 Foxglove-web 分鏡(0 code),不要塞進 Studio。**

**硬牆(本案最關鍵正確判斷,file:line 全核實)**:map/scan 只存在於 **nav stack**,`studio_gateway` 只在 **brain stack** 啟動(start_full_demo_tmux.sh:285,且該 stack `enable_lidar:=false nav2:=false slam:=false`,:135–136)。兩者 **8GB/lock/cmd_vel 三重互斥**。地圖卡放 brain 主鏡只會 **NO SIGNAL**。issue #130 本身也明文「LiDAR/map 視覺一律走 Foxglove,不在本 issue 範圍」。

**最小步驟(0 code,0.5 天)**:
1. Mac 開 `app.foxglove.dev` → Open connection → Foxglove WebSocket → `ws://<jetson-tailscale-ip>:8765`(nav stack 已內建 8765,start_nav2_amcl_demo_tmux.sh:73 / start_nav_capability_demo_tmux.sh:106)。
2. 存 layout `.json` 含三 panel:Map(`/map`)、LaserScan(`/scan_rplidar`,**非 Go2 driver 的 /scan 120 點**)、pose(`/amcl_pose` 或 TF map→base_link 箭頭)。存進 `docs/navigation/foxglove_layouts/nav_demo.json` + 一頁 SOP。
3. **這已滿足「不在 Mac 裝桌面 Foxglove」**(web 版免裝)。
4. **分鏡硬規矩**:map/lidar 視覺只放 nav 場測那一鏡,brain 互動主鏡不擺地圖卡。

**修正(不改變結論)**:
- 「全部 <25K cells / ~60KB」誇大 → 實測最大 `home_living_room_v3.pgm` = **234×178 = 41,652 cells(>40K)**、JSON 可達 ~160KB,仍屬一次性小量。
- rosbridge「對高頻/大訊息有效能問題(正好是 scan)」是合理推論非官方原文;但「no longer recommended」確認。
- **不選 Option B**(rosbridge + ros2djs/nav2djs):ros2djs 停更於 2022-05、無 Humble 聲明。若日後真要前端直連 ROS,改用 `tier4/roslibjs-foxglove`(over 現役 8765)。
- **原生 Studio 同頁卡 = low/stretch**(1.5–2.5 天,受 nav session 再塞 gateway 的 RAM 與互斥限制),只有團隊明確要「一個面板看全部」的敘事價值才付。

---

## Part B — 物體辨識加強

### B1 — 換不換模型(誠實:像素物理 vs 模型)

**像素物理(獨立重算嚴格成立)**:D435 HFOV 69.4° → focal ≈ 924px(原圖);9cm 杯換算:
| 距離 | 原圖 | @640(現役) | @960 | @1280 |
|------|:----:|:----------:|:----:|:-----:|
| 1m | — | 42px | — | — |
| 1.5m | — | 28px | — | — |
| 2m | 41.6px | **21px** | 32px | 43px |

現役 pipeline letterbox 到 640(object_perception_node.py:331–333),9cm 杯 @2m → 21px = 踩 YOLO26n nano 下限。**換骨幹(26s/RF-DETR)補的是「同 21px 下的判別力」,補不了「只有 21px 資訊量」** → 提高輸入解析度比換模型對症。

**「為什麼一直沒換」的誠實版**:不是失誤。6/05 demo-production-plan:138 已**主動**收斂「不換任何感知模型(cup 鎖 ≤1.5m,KEEP_CURRENT)」+ object/CLAUDE.md:51 明寫「demo 期不改 input_size」。5/20 protocol Step 2 的 640→768 A/B 確實「研究過卻從未實跑回填」(§3.3 量測表至今全空白),但這是**主動 KEEP_CURRENT 決策的結果**,不是純粹遺漏。

**決定:預設走零風險 A,960 重匯當加分支線(需 Roy 批准)。**
- **(A 預設)** 維持 YOLO26n@640,demo claim 鎖 ~1m(=6/05 窄版 pass,已有 5/5@1m conf 0.83–0.88 證據)。
- **(B 需 Roy 拍板,因推翻已收斂決策)** WSL 重匯 imgsz=960 → scp 到 `/home/jetson/models/yolo26n_960.onnx`(**不覆蓋現役 640 檔**)。`input_size` 參數必須 = 960 與 ONNX imgsz 嚴格一致(否則 shape mismatch silent crash,object/CLAUDE.md trap#6)。**啟動先確認 log 見 `TensorrtExecutionProvider`**(只見 CUDA/CPU → 960 數據全無效)。然後按 benchmark-protocol §3 量 gate:2m cup detect rate、obj FPS ≥6(Object only floor)/ ≥3(Full perception floor)、與 brain 共存 RAM ≥0.8GB。**任一不過 → 回 A。**

**class 擴充(零風險,~30 分,可獨立做)**:現役已支援 80 類,只擴 `class_whitelist`(config/launch override,不換模型)。建議 demo 用 `[0,41,39,67,73,56,57,60,63,58,77,24,999]`(person/cup/bottle/cell_phone/book/chair/couch/dining_table/laptop/potted_plant/teddy_bear/backpack + 999 強制 INTEGER_ARRAY)。**避雷**:bottle 透明反光(4/6 未偵測)、平放 book/cell_phone 難 → demo 時立起 + 開燈 + 拉 ~1m;家裡無真狗(玩偶會被當 teddy_bear)。

**26s 旁支(僅 960 過了還想再救 2m,~1hr)**:`cp yolo26s.onnx`(不覆蓋 26n)、TRT 重建、走 boost-only(Scene mode 才開);obj FPS<6 或 RAM<0.8GB 直接放棄(26s params×4,共存風險高於 960)。

### B2 — coco_detector verdict

**決定:不採用,維持 YOLO26n。effort=0,risk=0。**

go2_ros2_sdk 的 coco_detector(torchvision `fasterrcnn_mobilenet_v3_large_320_fpn`)在每一軸都輸:
- **準度**:獨立查 torchvision model card,真實 COCO val2017 box mAP = **22.8**(舊 doc §11.1 誤估 37% 是假設 ResNet-50-FPN)vs YOLO26n **40.1**。
- **小物**:FasterRCNN-320 對小物更差,正中唯一 object claim(object.cup ~1m)。
- **Jetson 適配**:純 PyTorch,會強制把 torch/torchvision 裝上 Jetson = **重觸 4/4 torch-wheel breakage**(object/CLAUDE.md:15)。現役 object_perception 是 **torch-free**(grep 確認只依賴 rclpy/std_msgs/sensor_msgs/cv_bridge + onnxruntime;yolo26n.onnx 在 WSL 用 ultralytics 匯出、只搬 .onnx 上 Jetson,無矛盾)。
- **契約**:coco_detector 發 `Detection2DArray` 到 `/detected_objects`,專案發 `std_msgs/String` JSON 到 **凍結的** `/event/object_detected`(contract **v2.5**,非報告誤寫的 v2.4;§4.8 active/frozen,80 類)。換 = 破契約 + 重接 brain/_on_object + Studio panel。
- 「效果不錯」的印象來自作者 RTX2070 桌機 demo,不轉移到 8GB 共享記憶體 Jetson。

**若團隊堅持要看**:只在 cloud RTX8000 用 conda 跑上游 repo 比 gut-feel(~1–2h,零 Jetson 風險),但 mAP 22.8 < 40.1,不會改變結論。

> FYI(與此 verdict 無關):`pawai-studio/backend/yolo26n.onnx` 與 `yolov8n.onnx` 有相同 SHA(同 blob 改名),不影響 ROS2 object_perception node,需要時另跟 Studio owner 講。

### B3 — 掉落物(地面判定 depth)可行性

**決定:保守版 high(主推),地面加分版 low(僅餘力時)。**

**保守版(主推,~0.5h,零風險)**:不碰程式碼。維持 `class_whitelist=[41,999]` cup-only;口白照 demo-flow-plan:43(H6)用「我看到桌上有杯子」(**不講地上**),不穩退「桌上有物品」;旁白照 :78/:110 明說「刻意只開杯子、僅近距 ~1m 可靠、非通用物體辨識、2m 未驗」;不接 depth、不觸發 Go2 移動、不把 LLM 口播當感知證據。這是 6/04 已收斂的零新風險窄版 pass。

**加分版(僅有餘力,~1–1.5 天,low)**:在 object_perception_node 加 optional depth sub(param default off,topic `/camera/camera/aligned_depth_to_color/image_raw`,該 topic demo 已開:start_full_demo_tmux.sh:147 `align_depth.enable:=true`、:146 `pointcloud.enable:=false`)。抄 `face_identity_node.py:550–554` 的 median+valid-mask:取 bbox 底邊中央 ROI median 深度 → camera_info K 做 deproject → 套 base_link→camera 外參算離地高度,閾值 h<0.08m=地面、h>0.35m=桌面。`/event/object_detected` 只加 optional `on_floor`+`height_m`,不進 dedup/TTS key(照 contract v2.5 optional 先例)。

**加分版必修的兩個 corrected 風險**:
- 🔧 **REFUTED:相機 TF 不是「5/2 hardcoded (0.30,0,0.20)」。** demo 實跑的是 start_full_demo_tmux.sh:258 的 `0.15 0 0.1 0 0 0 base_link camera_link`(零旋轉,連 URDF 的 +0.05rad pitch 都沒帶)。(0.30,0,0.20) 來自 nav 繞路腳本非 brain demo。**零 pitch 反而使離地高度系統性偏估**(把朝上 2.9° 當水平)→ 加分版若做必須先在程式補回 pitch 或重設 static TF 帶 0.05。
- 🔧 **「地面最近可見 1.2m 物理牆」OVERSTATED。** 那是 RGB FOV + 0.40m 估高的悲觀值;on_floor 走 depth 串流(垂直 FOV ≈58°,寬於 RGB)→ 最近可見地面約 **0.8–1.0m**。cam_h=0.40m 本身亦為估值(URDF 鏈不含 Go2 站姿高)。
- 上 Jetson 前先跑 jetson-status 量 RAM baseline(13-window 近 8GB 上限,confirm ≥0.8GB 餘量才同框開 depth sub);先在 WSL 用單幀 D435 bag 驗 deproject 數字。

---

## 誠實邊界 / 風險

**物理上做不到 / 不該宣稱的(硬牆)**:
- ❌ **NAV「Go2 自走一小段 / 動態繞椅子」** — reactive_stop `angular.z=0` 寫死、DWB 5/3 不可重現、MPPI 從零 tuning + MIN_X 衝突。維持 future work,claim matrix「nav 零自走」不翻。
- ❌ **OBJ「2m 穩定偵測 / 即時 / 通用 80 類」** — 即使 960,9cm 杯 @2m=32px 仍是小目標,detect rate 可能改善但不保證「穩定」。2m 能不能講看實測,**不先承諾**。
- ❌ **掉落物「地上水杯」** — 地面近處不在 D435 FOV(<0.8–1.0m 看不到)、地上 cup 易破洞低召回、深色/水杯吸 IR depth 破洞。退「桌上有杯子」。

**stretch(賭得起才碰,不排進關鍵路徑)**:
- NAV 動態繞障(P2-2,+4–5 天成功率低,最壞 11 天全耗在 F7 上仍黑)。
- OBJ 960 重匯能否過 2m gate(P2-1,medium 但 outcome 完全未量測)。
- Studio 同頁原生地圖卡(1.5–2.5 天,RAM 互斥)。

**鐵約束守則(全部已正確套用,無扭曲)**:
- nav 與 brain **8GB/lock/cmd_vel 三重互斥** → 一鏡到底 nav 段必須 `pawai demo stop` 清 brain lock 後**獨立單鏡**(twist_mux 單一 cmd_vel 出口)。
- Go2 sport mode MIN_X≈0.5(driver 已硬 clamp `MAX_LINEAR_X=0.5`,robot_control_service.py:16,50);cmd_vel=0 走 StopMove(1003)。
- **不 fine-tune**(全程只談 off-the-shelf 模型/套件切換 + 調參 + WSL 重匯 ONNX,Jetson 純 onnxruntime runtime)。
- D435 不回 Nav2 costmap(4/3 上機避障全失敗,屬 nav 域;OBJ/掉落物純感知不受此安裝角度影響,未誤套)。
- Go2 自帶 sport obstacle-avoid 非捷徑(內建 LiDAR 2Hz/覆蓋率低)。

**effort 誠實修正**:NAV investigation 估「~0.5 天 + 1 次 HITL」偏樂觀;現實要加 BD-7D 不在分支(現場手動 param +0.5–1h)、AMCL YELLOW cov plateau 收斂不穩(現場可能吃 0.5–1h)→ 建議 **NAV 現場排 1 個 HITL 全天 buffer**,short_move 自走當 nice-to-have 不排進關鍵路徑。

---

## 參考來源

**內部 file:line(當前分支已核對)**:
1. `go2_robot_sdk/go2_robot_sdk/reactive_stop_node.py:74–75`(danger=1.1/slow=1.7 預設)、:175/:180(`_on_param_change` 只認 enable_nav_pause/safety_only → danger/slow init-only)、:264–268(angular.z=0.0 寫死)
2. `go2_robot_sdk/go2_robot_sdk/application/services/robot_control_service.py:16,50`(MAX_LINEAR_X=0.5 硬 clamp)
3. `go2_robot_sdk/config/twist_mux.yaml:26–36`(obstacle 200 > nav 10)
4. `go2_robot_sdk/.../nav_action_server_node.py:235–282`(pause-cancel+no_progress)、:259<:268(pause-check 在 progress-check 前)、:340–363(cov gating)
5. `go2_robot_sdk/launch/navigation_remap.launch.py:20–36/147/213–215`(cmd_vel 鏈路)
6. `go2_robot_sdk/config/nav2_params.yaml:35`(OmniMotionModel)、:155/:159/:161/:311/:319/:324(DWB/SmacPlannerHybrid/REEDS_SHEPP/min_vel_x 0.45/max 0.70)、:157(0.50 走 86cm 實證)
7. `face_perception/face_perception/face_identity_node.py:550–554`(median depth 抄寫點)、:94–95/:210(depth topic/sub)
8. `object_perception/object_perception/object_perception_node.py:331–333`(letterbox 640)、:145(color_topic)、:216(event_pub)、:213(唯一 subscription,無 depth)
9. `object_perception/config/object_perception.yaml:20`(class_whitelist=[41,999])
10. `scripts/start_full_demo_tmux.sh:146–147`(pointcloud false/align_depth true)、:258(camera TF 0.15 0 0.1 零 pitch)、:272/:285(foxglove 8765 / studio_gateway)、:135–136(brain stack nav2/slam false)
11. `pawai-studio/gateway/studio_gateway.py:72–83/287/370/383`(TOPIC_MAP/_on_ros2_msg/_on_video_frame/bgr8)
12. `pawai-studio/frontend/.../navigation-panel.tsx:86–94`(placeholder)
13. `docs/contracts/interaction_contract.md` §4.8(凍結 v2.5,80 類)、:1108(depth topic)
14. `docs/mission/2026-06-18-demo-production-plan.md:138`(KEEP_CURRENT)、`2026-06-18-demo-flow-plan.md:43/78/110`(H6/S4/S3 口白)
15. `docs/pawai-brain/perception/object/CLAUDE.md:15/17/47–51`(torch-wheel/凍結契約/input_size trap#6)
16. `docs/.../research/2026-03-25-object-detection-feasibility.md §3.1/§11.1(line 730/737)/§11.2–11.3`(mAP/coco 棄用/YOLOE 雲端)
17. `docs/.../thesis/背景知識/4-8-Navigation.md:7`(4/3 避障失敗根因)、`4-10-D435.md:69/80`(深色吸 IR/感知不受安裝角度影響)
18. `docs/.../2026-04-26-nav2-dynamic-obstacle-log.md:38–52/96–106/172/243–244/250`(5/2 摔狗/DWB 不可重現/淨空)
19. `project-status.md:46/275/277/303–304/322`(nav 零自走/0.81m 停實證/早停/F7 reframe/F7 P0)
20. maps:`docs/navigation/research/maps/home_living_room_v3.pgm` = 234×178 = 41,652 cells

**外部(external_refs)**:
21. torchvision FasterRCNN-MobileNet-V3-Large-320-FPN model card(box mAP 22.8 / 19.4M params / 0.72 GFLOPS) — https://pytorch.org/vision/stable/models/faster_rcnn.html
22. Ultralytics YOLO26 docs(26n 40.1 / 26s 47–48.6 mAP) — https://docs.ultralytics.com/models/
23. Ultralytics discussion #15888(1280 input 救小物) — https://github.com/ultralytics/ultralytics/discussions/15888
24. Nav2 velocity_smoother 預設 max=[0.5,0,2.5]/OPEN_LOOP/lifecycle — https://docs.nav2.org/configuration/packages/configuring-velocity-smoother.html
25. Nav2 MPPI controller(critic 繞行/diff-drive) — https://docs.nav2.org/configuration/packages/configuring-mppic.html
26. Nav2 GitHub issue #5375(MPPI diff-drive 近距收尾差) — https://github.com/ros-navigation/navigation2/issues/5375
27. Nav2 RPP(只 slow 不繞) — https://docs.nav2.org/configuration/packages/configuring-regulated-pp.html
28. Nav2 collision_monitor — https://docs.nav2.org/configuration/packages/collision_monitor/index.html
29. Foxglove「we no longer recommend rosbridge / use foxglove_bridge」 — https://foxglove.dev/blog/using-rosbridge-with-ros2
30. Foxglove web app — https://app.foxglove.dev
31. tier4/roslibjs-foxglove(v0.0.4 2024-09) — https://github.com/tier4/roslibjs-foxglove
32. RobotWebTools/ros2djs(停更 2022-05) — https://github.com/RobotWebTools/ros2djs
33. jfrancis71 coco_detector(RTX2070 桌機/simplicity-only/Isaac more sophisticated) — https://github.com/jfrancis71/ros2_coco_detector
34. RF-DETR Jetson 慢(GitHub #340「twice slower than YOLOv11 on Jetson」)+ Roboflow blog(cloud 勝/edge 輸)
35. Intel D435 HFOV 69.4° 官方規格 — https://www.intelrealsense.com/depth-camera-d435/