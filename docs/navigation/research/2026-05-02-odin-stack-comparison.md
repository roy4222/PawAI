# Odin Navigation Stack — 參考價值分析

> **Date**: 2026-05-02
> **Author**: Roy + Claude
> **Status**: reference-only(不替換現有 stack)
> **Purpose**: 評估留形科技 Odin Navigation Stack 對 PawAI 5/12 demo 與後續 `approach_person` skill 的可吸收概念

---

## 一句話結論

**Odin 是「參考工程樣板」等級,不是替代方案**。我們 5/12 demo 路線維持 Nav2 + AMCL + reactive_stop + capability gate;Odin 的價值在三個可小步吸收的局部策略 + 一條值得抄的語義導航 pipeline。

---

## Odin 是什麼

留形科技開源,基於 **ROS1 Noetic** 的 Unitree Go2 自主導航系統。整合高精度 SLAM、YOLO 語義偵測、神經網路規劃器(NeuPAN)、視覺語言模型。

- 原 GitHub: https://github.com/ManifoldTechLtd/Odin-Nav-Stack
- 官方 webpage: https://manifoldtechltd.github.io/Odin-Nav-Stack-Webpage/
- 中文筆記(Kwan Wai-Pang): https://kwanwaipang.github.io/Odin-Navigation-Stack/

### Odin 三層架構(對照組)

```
感知層: YOLO 偵測 + 3D 視覺定位 + 語義指令解析
規劃層: A* 全局 + DWA/NeuPAN 局部 + 局部代價地圖 + 目標狀態機
控制層: Unitree 運動控制器
```

### Odin 數據流關鍵 topic

| Odin topic | PawAI 對應 | 對齊狀況 |
|---|---|---|
| `/scan` | `/scan_rplidar` | 🟡 命名不同 |
| `/odin1/cloud` | (無,我們 2D-only) | — |
| `/camera/depth/image_rect` | `/camera/camera/aligned_depth_to_color/image_raw` | 🟡 雙重 namespace |
| `/detected_objects` | `/event/object_detected` | ✅ |
| `/localization_pose` | `/amcl_pose` | ✅ |
| `/initial_path` | (Nav2 BT 內部) | — |
| `/cmd_vel` + `/trajectory` | `/cmd_vel` | ✅ |
| `/move_base_simple/goal` | `/goal_pose` | 🟡 ROS1 → ROS2 等價 |

---

## 三條可吸收的概念

### 1. 資料流分層(我們已有,確認方向對)

Odin: 感知 → 規劃 → Unitree 控制器
PawAI: 感知拆得更細
- **RPLIDAR** → AMCL/Nav2 主導航
- **D435** → 近距離 safety gate (`/capability/depth_clear`)
- **`reactive_stop_node`** → 外層硬停車仲裁(priority 200 mux)

**Odin 沒有的我們有的**:
- Capability Gate(`/capability/nav_ready` + `/capability/depth_clear`)
- Brain Executive 三段 Pre-action Validate(NAV / high-risk MOTION / low-risk social MOTION)
- LLM AI Brain(Odin 只有規則式語義匹配)

→ 結論:架構分層方向一致,我們的 safety + brain 是上層加值。

### 2. 局部避障概念(可參考,不換核心)

⚠️ Odin 用 ROS1 Noetic;Custom Planner / Standard Navigation 在 Odin README 自己標 **Not recommended / TODO**。**5/12 前不該換 planner**。

可從 Odin 自製 DWA(`model_planner/src/local_planner/`)吸收三個小概念:

| Odin 概念 | 我們可借用之處 |
|---|---|
| **Obstacle Decay**(`decay_factor=0.95`,每幀代價值衰減) | 加到 `reactive_stop_node` buffer 處理走過的人/雷射噪點殘影 — Phase A 之後 |
| **Heading Alignment Boost**(朝向偏離大時加重對齊分量) | DWB controller `PathAlign.scale` 已部分覆蓋,但對 Go2 MIN_X=0.50 m/s 的轉向卡死有幫助 |
| **Bounded Recovery**(找不到路徑瞬時計算最優轉角,不靠 BT 狀態機跳 RotateRecovery) | quadruped MIN_X 限制下 RotateRecovery 無效,這個 inline recovery 邏輯比 BT spin 適合 Go2 |

**不抄的部分**:
- **NeuPAN(50Hz 神經網路規劃)** — 看起來香,5/12 risk 太大,DWB 已驗證可用
- **`move_base`** — ROS1 概念,我們已在 Nav2(新一代)
- **Bresenham 手寫 costmap** — Nav2 costmap_2d 在我們環境穩定,沒必要為了省 CPU 換掉

### 3. 語義導航 pipeline(`object_query_node.py`)— Scene 7 `approach_person` 直接抄

Odin 流程:
```
語音/文本
  → 正則解析(動作 / 物體 / 方位 / 索引)
  → 雙語詞庫匹配(中英 COCO 同義詞 + 長詞優先)
  → 找物體 (YOLO 偵測結果)
  → TF 變換(camera → map)
  → 機器人相對偏移(向量合成,不衝物體中心,算側方安全著陸點)
  → 發導航目標(/move_base_simple/goal)
```

對應到 PawAI Scene 7:
| Odin 步驟 | PawAI 現況 | 缺口 |
|---|---|---|
| 正則解析 | `stt_intent_node` intent_rules + LLM brain | ✅ 已有(LLM 更強) |
| 雙語詞庫匹配 | (無) | 🔴 缺 — RuleBrain fallback 升級點 |
| 找物體 | `object_perception` YOLO26 + `/event/object_detected` | ✅ |
| TF camera → map | (部分,object_perception 內) | 🟡 需驗證 frame 一致性 |
| **物體相對偏移(向量合成)** | (無) | 🔴 **`approach_person` 關鍵缺口** |
| 發 goal | `nav_capability/goto_relative` 只接絕對距離 | 🔴 需擴 `goto_object_offset` action |

**抄法**:重寫 `object_query_node.py` 三函式為 ROS2 + Nav2 action client:
- `parse_navigation_command()` — 解析「物體 + 方位 + 索引」
- `find_object()` — 查 `/event/object_detected` cache
- `calculate_target_position()` — TF + 旋轉矩陣算側方落點(防止撞物)

走 `nav_capability` action,**不**走 `/goal_pose` topic(避免 BEST_EFFORT race)。

---

## 行動清單

### 5/12 Demo 前(不動)
- 維持 Nav2 + AMCL + reactive_stop + capability gate 主線
- Phase A 兩個 capability node + 三段 Pre-action Validate
- `nav_demo_point` 5/5 PASS

### 5/12 Demo 後(可吸收)
- **P1**: 抄 Odin `object_query_node.py` 邏輯實作 `approach_person` skill 的 spatial grounding
  - 新增 `nav_capability/goto_object_offset` action
  - 新增雙語 COCO 詞庫(RuleBrain fallback 用)
- **P2**: `reactive_stop_node` buffer 加 obstacle decay(0.95 衰減)
- **P3**: DWB controller 調 `PathAlign.scale` 對應 heading alignment boost
- **P4**(評估): inline bounded recovery 取代 BT RotateRecovery

### 不做
- ❌ 換 NeuPAN(5/12 risk)
- ❌ 退回 ROS1 / move_base
- ❌ 換掉 Nav2 costmap

---

## 來源

- Kwan Wai-Pang Odin 中文筆記: https://kwanwaipang.github.io/Odin-Navigation-Stack/
- Odin 官方 GitHub: https://github.com/ManifoldTechLtd/Odin-Nav-Stack
- Odin local planner 目錄: https://github.com/ManifoldTechLtd/Odin-Nav-Stack/tree/main/ros_ws/src/model_planner/src/local_planner
- Odin yolo/object query 目錄: https://github.com/ManifoldTechLtd/Odin-Nav-Stack/tree/main/ros_ws/src/yolo_ros/scripts
- Odin 註解版(R-C-Group fork): https://github.com/R-C-Group/Odin-Navigation-Stack
- Odin 邏輯架構圖: https://github.com/R-C-Group/Odin-Navigation-Stack/raw/main/scripts/odin_logical_arch_cn_1767142123104.png
- Odin 數據流圖: https://github.com/R-C-Group/Odin-Navigation-Stack/raw/main/scripts/odin_data_flow_cn_1767142150666.png
