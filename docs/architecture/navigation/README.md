# Navigation

> **Scope**：PawAI 移動能力（定位 / 建圖 / 避障 / 短距移動）的**架構真相層** — 「stack 怎麼組、哪條 action path 是真的、哪些是 historical/research」。
> **Status**：active（架構真相層）。本檔**不再**充當「當前能力 claim」真相 — 任何 nav 能力是否 pass / 可否走真實 motion，一律以 §「nav 能力 claim」的 canonical claim matrix nav 行為準。
> **Owner lane**：nav（搭配 `docs/architecture/navigation/CLAUDE.md` 模組工作規則）。
> **Source-of-truth 優先序**（高→低）：程式碼 / topic schema ＞ `docs/runbook/baseline-evidence/2026-06-04-hitl/`（實測，nav 全 `insufficient_data`）＞ `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §4（收斂審計：nav 降級為純 Studio 顯示、零實機自走）＞ `docs/mission/2026-06-18-demo-north-star.md` §7（戰略邊界）＞ 本檔（架構）＞ `docs/contracts/interaction_contract.md`（nav topic/action schema）。
> **Maintained child files**：`CLAUDE.md`（工作規則）、`legacy-readme-from-導航避障.md`（既有權威 README）、`2026-05-11-architecture-deep-audit-and-fix-roadmap.md`（4-mode reactive stop / B-burndown 架構真相）。
> **Archived / historical 邊界**：`plans/*.md`（5/1–5/4 sprint plan）、`research/*.md`、`legacy-archive/` 一律 **historical / research-only**，不重複維護、不得當「現在能跑什麼」的依據。
> **本 README 不是**：能力 claim 真相（→ canonical claim matrix）、操作手冊（→ runbook，最安全 = `docs/runbook/2026-06-18-hitl-oneshot-runbook.md`）、門檻定義（→ `docs/architecture/specs/2026-06-18-capability-baseline-spec.md`）。

---

## nav 能力 claim（引用 canonical，勿在此重複整份）

> **權威**：`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B Capability Claim Matrix nav 行 + §4，基準為 `docs/runbook/baseline-evidence/2026-06-04-hitl/`。下面只是入口摘要。

- **Current Claim**：nav 四能力（`nav.short_move` / `nav.safe_stop` / `nav.no_auto_resume` / `nav.dynamic_avoidance`）6/4 trusted snapshot 全 **`insufficient_data`**。
- **Pass / Degraded / Fail / Insufficient**：**Insufficient_data**（無 trusted motion record）。
- **真實 action path**：手動短距 goto 走 `/nav/goto_relative`（action），由 `scripts/send_relative_goal.py` 觸發；觀測值是該 script 印出的 action Result（`success` / `message` / `actual_distance`）。**`/event/nav/mission` topic 全 source 不存在** — 不要 echo（會永久 hang），詳 `docs/runbook/2026-06-18-baseline-runbook.md` 的 doc-bug 註記。
- **Fallback / 安全規則**：nav 一律 **dry-run / fail-closed**，除非 explicit override **且** safety gate（`nav.safe_stop` + `nav.no_auto_resume`）pass。dry-run 只證 fail-closed + action 鏈路通（AMCL 未定位 → `amcl_lost` abort、Go2 全程不動），**非真實移動、非動態避障/自走**。
- **Non-Claims（禁說）**：不得宣稱 6/18 動態避障 / 自主繞障 / 自走；nav 預設純 Studio / Foxglove 顯示零實機自走（北極星 §7 + 收斂審計 §4）。
- **Next Retest**：HITL 上機定位 F7（goal accept 後 `/cmd_vel_nav` 無 publisher）+ safety 兩項 recorder/行為重設計後，才談真實 motion。最安全 operator runbook = `docs/runbook/2026-06-18-hitl-oneshot-runbook.md`（nav = 純 DRY-RUN 段）。

---

## 一句話（架構真相層，非當前能力 claim）

**Navigation 是 PawAI 的移動能力 — RPLIDAR-A2M12 負責 2D `/scan` + SLAM(離線建圖)+ AMCL(runtime 定位)+ Nav2(規劃),D435 depth 負責近距離 safety gate;兩個 Capability Bool(`/capability/nav_ready` + `/capability/depth_clear`)餵給 Brain Executive 的 Pre-action Validate。**

---

> **以下 5/2–5/12 sprint 段落為 historical sprint 紀錄（保留作引用）。** 其中「動態避障 / detour / Wow」等語言屬 5/12 sprint 目標，**已被 6/5 收斂審計 §4 + 北極星 §7 降級為純 Studio 顯示、零實機自走**。當前 nav 能力一律以上方「nav 能力 claim」（canonical claim matrix）為準，不要把這些 sprint 段當作「現在能跑什麼」。

## 5/2 進度更新（historical）

Phase A Step 1+2+3 完成(commit `a3bdd2e`):BUG #2 已修(`nav_action_server` 訂 `/state/nav/paused` + 10s pose-progress timeout、K1 3/3 + K-pause 實機過)、`/capability/depth_clear` fail-closed 上線、`/capability/nav_ready` v0.5 basic 上線。
Phase A Step 4(Executive 接線)同日完成:WorldState 訂三個 capability(fail-closed)+ SafetyLayer 加 nav_paused / NAV / MOTION 三段 gate(27 cases 過 + 92/92 regression)。
**day 2 待做**:接 launch / Brain rules / Studio LED / `nav_ready` 升級 lifecycle+TF+costmap。

## 5/4 Scope Freeze 與 Bug 診斷

5/3 夜間拆解確認 detour 反覆失敗的根因是 **B1**(`nav_action_server` 不 enforce max_speed,0.5m goal 走 1.04m)+ **B2**(AMCL `update_min_d=0.10` 靜止不收斂)兩 bug 串連,**不是 DWB 設計問題、不是場地、不是感測器**。

詳見 `plans/2026-05-04-demo-scope-freeze.md` — 含戰略 framing、完整 bug backlog(B1-B5)、環境陷阱(E1-E10)、操作教訓(O1-O4)、物理極限(P1-P4)、驗收 V1-V9、答辯 framing。

Phase 2 code 改動將拆獨立小 PR(PR 1-7),**不在本 scope freeze 之內**。

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

## 5/12 Demo 必做(5 項生死線)

> Scope Freeze 詳見 `plans/2026-05-04-demo-scope-freeze.md`

1. **`nav_demo_point` 5/5 PASS** — 對應 Storyboard Scene 2 ★Wow A
   *條件*:B1(`nav_action_server` max_speed enforce)+ B2(AMCL plateau)修完
2. **D435 + LiDAR 雙源 reactive stop** — 障礙 < 0.6m 強制停車
3. **Pause-Resume 或 safe abort** — 障礙清除 resume / 10s 無進度 abort
4. **`/capability/nav_ready` 升級**(lifecycle + TF + scan freshness 三項;**只做這三項,不再加**)
5. **30 分鐘供電連測 0 斷電**(2464 升降壓恒壓恒流模組驗收)

### Wow 加分(條件達成才做)

- `approach_person` 1 PASS — 對應 Scene 7 ★★Wow C(可砍)
- **Detour profile** — ★ Wow,**條件:B1+B2 修完後**,失敗就回 stop+resume
- Studio / Foxglove 顯示 `nav_ready` level + reasons

---

## 文件導覽

| 檔案 / 路徑 | 內容 |
|---|---|
| **入口頁(本檔)** | `docs/architecture/navigation/README.md` |
| **Phase A Implementation Plan**(5/2-5/3 attack) | `docs/archive/navigation-legacy/plans/2026-05-01-phase-a-nav-attack.md` |
| **Sprint design 主線**(包含 §5 D435+RPLIDAR 整合 / §6 兩層 Capability Gate / §7 Phase A) | `docs/architecture/specs/2026-05-01-pawai-11day-sprint-design.md` |
| **既有設計 specs** | `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-24-p0-nav-obstacle-avoidance-design.md`<br/>`docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-26-nav-capability-s2-design.md` |
| **介面契約**(nav 相關 topic + action) | `docs/contracts/interaction_contract.md` |
| **最安全 operator runbook**（nav = 純 DRY-RUN 段、fail-closed） | `docs/runbook/2026-06-18-hitl-oneshot-runbook.md` |
| **baseline 量測 runbook**（含 `/event/nav/mission` doc-bug 註記） | `docs/runbook/2026-06-18-baseline-runbook.md` |
| **能力 claim canonical matrix**（nav 行） | `docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md` §B/§4 |
| **Nav 既有權威 README**（historical） | `docs/architecture/navigation/legacy-readme-from-導航避障.md` |
| **Nav CLAUDE.md**(模組工作規則) | `docs/architecture/navigation/CLAUDE.md` |

---

## 5/2 外部 Stack 研究(8 份) — research-only

> **`docs/archive/navigation-legacy/research/*` 一律 research-not-truth**：是吸收性分析 / daily 探測紀錄，**不覆寫 baseline-evidence 或 contracts**，也不得當作「已實作 / 已驗證」的依據。模型/stack 研究分層 = BASELINE_NOW / STUDIO_ONLY_NOW / SPIKE_AFTER_FAIL / FUTURE_RESEARCH，不要預設變成實作 backlog。

對 8 個開源專案(Odin / OM1 / NavDP / visualnav-transformer / amigo_ros2 / DimOS + 1 篇論文)做了可吸收性分析。
**總彙整與優先序**:`research/2026-05-02-research-synthesis.md` — 列出 Phase A 立即可吸收 4 項(A1-A4)、5/12 後 P2 七項、6 月後 P3 六項、明確不做的事。

## Legacy / Archive（historical）

歷史紀錄 / 研究 / 5/1 之前的 daily log 仍在原位:
- `docs/archive/navigation-legacy/research/` — 4/27-5/1 LiDAR mount yaw / AMCL 180° / K1 baseline / Phase 4-7 critical bugs
- `docs/archive/navigation-legacy/research/lidar-dev/` — 4/27 lidar dev roadmap
- `docs/archive/2026-05-docs-reorg/superpowers-legacy/specs/2026-04-{24,26}-*.md` — Phase 1-4 設計

本資料夾**只**維護 5/12 Demo 衝刺期 + 之後的主線版本;舊文件保留作歷史與引用,不重複維護。

---

## 已知陷阱(摘要,完整見 `docs/architecture/navigation/CLAUDE.md`)

- **Go2 sport mode `cmd_vel` 門檻 MIN_X = 0.50 m/s** — DWB `min_vel_x` 必須 ≥ 0.45,否則 Go2 拒抬腳
- **slam_toolbox 在 ARM64 + Humble + RPLIDAR 永久棄用**(Mapper FATAL ERROR known bug)
- **不要 `ros2 topic pub --once /goal_pose`** — bt_navigator subscriber 是 BEST_EFFORT,改 `-r 2 --times 5`
- **D435 RGB-D topic 用 double namespace** `/camera/camera/aligned_depth_to_color/image_raw`
- **XL4015 供電不穩** — 4/27 起 8+ 次 Go2 運行中 Jetson 斷電,Demo 最大風險,等 KREE DL241910
