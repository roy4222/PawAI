# Navigation

> **Status**: current(5/12 sprint 主線)
> **Date**: 2026-05-01
> **Scope**: PawAI 「怎麼定位、建圖、避障、移動」的單一真相層

---

## 一句話

**Navigation 是 PawAI 的移動能力 — RPLIDAR-A2M12 負責 2D `/scan` + SLAM(離線建圖)+ AMCL(runtime 定位)+ Nav2(規劃),D435 depth 負責近距離 safety gate;兩個 Capability Bool(`/capability/nav_ready` + `/capability/depth_clear`)餵給 Brain Executive 的 Pre-action Validate。**

---

## 5/2 進度更新

Phase A Step 1+2+3 完成(commit `a3bdd2e`):BUG #2 已修(`nav_action_server` 訂 `/state/nav/paused` + 10s pose-progress timeout、K1 3/3 + K-pause 實機過)、`/capability/depth_clear` fail-closed 上線、`/capability/nav_ready` v0.5 basic 上線。
Phase A Step 4(Executive 接線)同日完成:WorldState 訂三個 capability(fail-closed)+ SafetyLayer 加 nav_paused / NAV / MOTION 三段 gate(27 cases 過 + 92/92 regression)。
**day 2 待做**:接 launch / Brain rules / Studio LED / `nav_ready` 升級 lifecycle+TF+costmap。

## 目前主線(5/12 衝刺週)

- **建圖層**:cartographer(離線,已產出 `home_living_room_v8.pbstream + .yaml`;slam_toolbox 在本硬體永久棄用)
- **定位層**:AMCL(載入既有 map,K1 baseline 5/5 PASS @ 5/1)
- **規劃層**:Nav2 BT navigator + DWB controller(`min_vel_x ≥ 0.45` 對應 Go2 sport mode 0.50 m/s 門檻)
- **動態避障**:`reactive_stop_node`(D435+LiDAR 兩源,Phase 4 v0)+ `/state/nav/paused` global pause state(Phase A 新增)
- **Capability Gate**(Phase A 新增):
  - `/capability/nav_ready` — Nav2 active + AMCL covariance < 0.20 + local costmap healthy
  - `/capability/depth_clear` — D435 ROI 前方 1m 內 / 障礙 < 0.4m
- **nav_capability 平台層**:`goto_relative` action(Phase A 修 BUG #2)+ `run_route` + `log_pose`

---

## 5/12 Demo 必做

- RPLIDAR `/scan` 10 Hz 穩定
- AMCL covariance < 0.20(/initialpose 設好後 30s 內)
- `/capability/nav_ready` true
- `/capability/depth_clear` true(D435 ROI 無近物時)
- **`nav_demo_point` skill 上機 5/5 PASS**(對應 Storyboard Scene 2 ★Wow A)
- **`approach_person` skill 上機 1 PASS**(對應 Storyboard Scene 7 ★★Wow C,進階,可砍)
- 30 分鐘供電連續測試 0 次斷電

---

## 文件導覽

| 檔案 / 路徑 | 內容 |
|---|---|
| **入口頁(本檔)** | `docs/navigation/README.md` |
| **Phase A Implementation Plan**(5/2-5/3 attack) | `docs/navigation/plans/2026-05-01-phase-a-nav-attack.md` |
| **Sprint design 主線**(包含 §5 D435+RPLIDAR 整合 / §6 兩層 Capability Gate / §7 Phase A) | `docs/pawai-brain/specs/2026-05-01-pawai-11day-sprint-design.md` |
| **既有設計 specs** | `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`<br/>`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-26-nav-capability-s2-design.md` |
| **介面契約**(nav 相關 topic + action) | `docs/contracts/interaction_contract.md` |
| **Nav 既有權威 README** | `docs/navigation/legacy-readme-from-導航避障.md` |
| **Nav CLAUDE.md**(模組工作規則) | `docs/navigation/CLAUDE.md` |

---

## 5/2 外部 Stack 研究(8 份)

對 8 個開源專案(Odin / OM1 / NavDP / visualnav-transformer / amigo_ros2 / DimOS + 1 篇論文)做了可吸收性分析。
**總彙整與優先序**:`research/2026-05-02-research-synthesis.md` — 列出 Phase A 立即可吸收 4 項(A1-A4)、5/12 後 P2 七項、6 月後 P3 六項、明確不做的事。

## Legacy / Archive

歷史紀錄 / 研究 / 5/1 之前的 daily log 仍在原位:
- `docs/navigation/research/` — 4/27-5/1 LiDAR mount yaw / AMCL 180° / K1 baseline / Phase 4-7 critical bugs
- `docs/navigation/research/lidar-dev/` — 4/27 lidar dev roadmap
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-{24,26}-*.md` — Phase 1-4 設計

本資料夾**只**維護 5/12 Demo 衝刺期 + 之後的主線版本;舊文件保留作歷史與引用,不重複維護。

---

## 已知陷阱(摘要,完整見 `docs/navigation/CLAUDE.md`)

- **Go2 sport mode `cmd_vel` 門檻 MIN_X = 0.50 m/s** — DWB `min_vel_x` 必須 ≥ 0.45,否則 Go2 拒抬腳
- **slam_toolbox 在 ARM64 + Humble + RPLIDAR 永久棄用**(Mapper FATAL ERROR known bug)
- **不要 `ros2 topic pub --once /goal_pose`** — bt_navigator subscriber 是 BEST_EFFORT,改 `-r 2 --times 5`
- **D435 RGB-D topic 用 double namespace** `/camera/camera/aligned_depth_to_color/image_raw`
- **XL4015 供電不穩** — 4/27 起 8+ 次 Go2 運行中 Jetson 斷電,Demo 最大風險,等 KREE DL241910
