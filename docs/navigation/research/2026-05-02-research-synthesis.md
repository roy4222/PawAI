# 2026-05-02 導航避障參考來源總彙整

> **Date**: 2026-05-02
> **Scope**: 8 份外部來源 (3 部落格 + 5 codebase) 的可吸收清單與優先序
> **Goal**: 把研究結果落到 Phase A (5/2-5/3) / 5/12 demo 後 P2 / 6 月 P3 三個時間箱

---

## 8 份來源一句話定位

| 來源 | 類型 | 一句話定位 |
|---|---|---|
| Odin (部落格) | 工程樣板 | 語義導航 pipeline + DWA 微創新 |
| Odin (codebase deepdive) | 工程樣板 | object_query_node 真實實作(修正部落格錯誤) |
| OM1 | 哲學樣板 | LLM-first runtime + skill lifecycle + AI gating |
| CSDN 論文 | 學術參考 | 3D LiDAR + IMU 融合,僅 IMU→cartographer 可吸收 |
| **NavDP / LoGoPlanner** | end-to-end | Sim2real diffusion policy,5/12 不採用 |
| **visualnav-transformer** | research | Image-goal nav,範式不符,backlog |
| **amigo_ros2** | 同硬體工程樣板 | Go2 + RPLIDAR + Nav2,teach-and-repeat 模式 |
| **DimOS** | runtime + skill framework | Go2 first-class、30+ sport mode skill、pydantic→LLM schema |

---

## 可吸收清單(按優先序)

### 🟢 Phase A 立刻吸收(5/2-5/3,low-risk 加值)

| # | 來源 | 動作 | 預估工 |
|---|---|---|---|
| A1 | OM1 | `world_state.py` 加 `is_executing_skill: bool`,brain 規則表在 true 時只允許 SAFETY/ABORT(避免使用者連說兩次「過來」造成 Go2 震盪) | 0.5 天 |
| A2 | OM1 | `nav_action_server` Timeout 區分「卡死 vs 進度中」— 有 AMCL pose 進展就 loop,無進展才 fail | 0.5 天 |
| A3 | DimOS | 把 30+ sport mode skill 對照表(api_id 1002-1027)補進 `interaction_executive/skills/`,擴充 SkillContract registry | 0.5 天 |
| A4 | amigo_ros2 | `nav_demo_point` 套 teach-and-repeat pattern + 6 次 retry + assistedTeleop fallback(我們已有 LogPose action,結構一致) | 1 天 |

### 🟡 5/12 Demo 後 P2(2-3 週內)

| # | 來源 | 動作 | 預估工 |
|---|---|---|---|
| P2-1 | Odin codebase | 抄 `object_query_node.py` 三函式做 `approach_person` spatial grounding (parse_navigation_command + find_object + calculate_target_position) — **必須加 costmap collision check**(原版沒有) | 2-3 天 |
| P2-2 | Odin codebase | 新增 `nav_capability/goto_object_offset` action(物體 + 方位 → 安全落點),走 Nav2 action 而非 `/goal_pose` topic | 1 天 |
| P2-3 | Odin codebase | RuleBrain 雙語 COCO 詞庫(中英同義詞 + 長詞優先匹配) | 1 天 |
| P2-4 | CSDN 論文 | Cartographer 加 `use_imu_data = true`,Go2 driver `/imu` 對齊 `imu_link`,重建 v9 map 對比 v8 邊界品質 | 1 天 |
| P2-5 | DimOS | 用 pydantic Field description → 自動產 LLM tool schema 重構 SkillContract(改善 brain LLM 對技能參數的理解) | 2 天 |
| P2-6 | DimOS | `visual_navigation_skills.FollowHuman` 視覺伺服邏輯參考,給 `approach_person` 加平滑跟隨段(Nav2 到 1.5m 後切換 visual servo) | 2 天 |
| P2-7 | amigo_ros2 | `RegionMap.srv` (cv2 connectedComponents 切地圖區域),用於「去廚房」自然語言指令 → region lookup → goto | 2 天 |

### 🔵 6 月後 P3(評估,不一定做)

| # | 來源 | 動作 |
|---|---|---|
| P3-1 | Odin codebase | DWA heading boost 概念 → Nav2 DWB controller `PathAlign.scale` 加重(對 Go2 MIN_X 卡住有幫助) |
| P3-2 | Odin codebase | **Obstacle decay 加在 Nav2 STVL layer**(修正:**不是** `reactive_stop_node` buffer — reactive_stop 是 stateless filter,加了不對) |
| P3-3 | Odin codebase | Inline bounded recovery(找不到路時瞬時計算最優轉角,不靠 BT spin)— quadruped MIN_X 限制下比 BT spin 適合 |
| P3-4 | OM1 | MENTOR LLM 層(30s 週期)做 session 級使用者偏好學習 |
| P3-5 | visualnav-transformer | NoMaD 預訓練 checkpoint 給 `follow_person` / room-to-room visual nav backlog,需 fine-tune 居家場景 |
| P3-6 | CSDN 論文 | TEB vs DWB benchmark,在 v8 map 上 A/B 看狹窄空間表現 |

### ❌ 明確不做

| 來源 | 不做的事 | 理由 |
|---|---|---|
| Odin C++ DWA | 移植到 Nav2 plugin | 1071 行 C++,Nav2 DWB PathAlign + STVL decay 已覆蓋概念,不值得 |
| Odin / amigo_ros2 / 論文 | 退回 ROS1 / 換 stack | ROS2 Humble 主線不動 |
| OM1 | NLDB / Zenoh / Cloud SLAM | 失去結構化 query 能力,debug 成本爆 |
| NavDP / LoGoPlanner | 整套採用 | end-to-end 要丟掉 Nav2/AMCL/cost map,Jetson 8GB 跑不動,無 Go2 quadruped checkpoint,zero-shot 遇 MIN_X 0.50 m/s 風險高,ROS2 整合需 1-2 週自寫 wrapper |
| visualnav-transformer | 5/12 前導入 | ROS1 only,port 1-2 天,且與 RTMPose 滿載 GPU 無法共存,訓練資料偏室外不適合居家 |
| amigo_ros2 | Isaac container + nvblox | Orin Nano 8GB 跑不動,他們是 AGX Orin |
| amigo_ros2 | slam_toolbox + MPPI | slam_toolbox 在 ARM64+Humble 永久棄用,MPPI 對我們 DWB calibrated 結果無增益 |
| DimOS | 整套整合 | DimOS Module/Blueprint runtime + LangGraph Agent + `dimos` CLI 會與 ROS2 launch + colcon + Brain Executive 雙 runtime 打架 |

---

## 重要修正(撤回先前文件錯誤)

1. **Odin DWA decay_factor 不是 0.95** — `local_costmap.cpp` default 0.95 會被 `local_planner.cpp` ROS param default 0.92 覆寫,**實跑值 0.92**。先前 `2026-05-02-odin-stack-comparison.md` 寫 0.95 已過時。
2. **Obstacle decay 不能加在 `reactive_stop_node` buffer** — reactive_stop 是 stateless filter,加 decay 在這層不對。**正確位置是 Nav2 STVL (Spatio-Temporal Voxel Layer)**。先前 Odin 文件要更正。
3. **Odin object_query_node 「物體右邊 1m」實作** — 是 `lookup_transform(map, base_link)` 拿 quaternion → 取 base_link x/y 軸投影到 map 平面 → **沿機器人當前朝向**偏移,不是相機側軸也不是 map 絕對軸。**完全沒有 collision check**,我們抄時必須加 costmap query(否則會送 Go2 撞牆)。

---

## 對 5/12 Demo 風險評估

**綠燈 — 維持原 Phase A 計畫不變**:
- Nav2 + AMCL + reactive_stop + capability gate 主線繼續
- 加 A1-A4 四項小加值(共 ~2.5 天工,在 5/2-5/3 可塞)
- 不引入任何外部 codebase,所有可借用點都是「概念移植」不是「程式碼整合」

**最大風險仍是供電**(XL4015 → 2464 升降壓已換,等 KREE DL241910)— 跟外部 research 無關。

---

## 8 份報告檔案索引

- `2026-05-02-odin-stack-comparison.md` — 部落格層級概覽
- `2026-05-02-odin-codebase-deepdive.md` — 真實程式碼驗證(本文修正錯誤)
- `2026-05-02-om1-stack-comparison.md` — LLM-first 哲學
- `2026-05-02-csdn-thesis-3d-lidar-comparison.md` — 3D LiDAR 路線(僅 IMU 可吸收)
- `2026-05-02-navdp-logoplanner-analysis.md` — sim2real diffusion,5/12 不採用
- `2026-05-02-visualnav-transformer-analysis.md` — image-goal,backlog
- `2026-05-02-amigo-ros2-analysis.md` — 同硬體 + Nav2,teach-and-repeat 可借
- `2026-05-02-dimos-analysis.md` — Go2 skill framework + pydantic→LLM schema
