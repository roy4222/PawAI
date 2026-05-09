# Navigation Roadmap — 設計規格

> **Status**: draft
> **Date**: 2026-05-10
> **Spec ID**: Spec 5 of 6（demo-quality roadmap）
> **Scope**: 從現有 SLAM/Nav2 基礎延伸到 6 項導航能力，按 demo 風險分級
> **執行視窗**：demo 後（5/13-14 LM307 場地測 + demo 後逐步啟用）
> **Owner**: Roy
> **依據**：
> - `docs/contracts/interaction_contract.md`（nav_capability 4 actions + 3 services）
> - `docs/navigation/research/2026-04-25-rplidar-a2m12-integration-log.md`
> - `scripts/start_nav_capability_demo_tmux.sh`

---

## 1. 範圍：6 項導航能力

| # | 能力 | 現況 | demo? | 風險 |
|---|---|---|---|---|
| 1 | **SLAM + Nav2 基本** | ✅ 已有（cartographer 建圖 + AMCL 定位）| 5/13 場地 | 中 |
| 2 | **動態避障**（D435 + RPLIDAR）| ⚠️ reactive_stop 已有，動態 detour 5/3 fail | 不 demo | 高 |
| 3 | **招手過來**（face + gesture + nav）| ❌ 未實作 | 不 demo | 高 |
| 4 | **指定物體尋物導航** | ❌ 未實作 | 不 demo | 高 |
| 5 | **自動巡邏** | ❌ 未實作 | 不 demo | 高 |
| 6 | **跟隨模式** | ❌ 未實作（disabled）| 不 demo | 極高 |

**demo 主軸**：只展示 #1（在 5/13 場地測通過後上 demo）；#2-6 都 demo 後做。

---

## 2. 非目標

❌ 不做：
- 多樓層導航
- 戶外導航
- 動態地圖更新（家具移動）
- 多機器狗協同
- 精確定位（< 5cm 誤差）

---

## 3. P0：SLAM + Nav2 基本（demo 主軸）

### 3.1 流程
```bash
# 建圖（一次性）
bash scripts/build_map.sh home_living_room

# Demo 啟動
bash scripts/start_nav_capability_demo_tmux.sh
```

### 3.2 demo 動作
- `goto_relative 1.0m`：前進 1 公尺
- 中途放紙箱 → reactive_stop 停
- 移走紙箱 → resume

### 3.3 已知陷阱（CLAUDE.md 已記錄）
- DWB `min_vel_x` 必須 ≥0.45（Go2 sport mode 門檻）
- `GO2_PUBLISH_ODOM_TF=0` 建圖階段；預設 1 demo 階段
- slam_toolbox 永久棄用（用 cartographer）
- `goal_pose` 必須 `-r 2 --times 5`（BEST_EFFORT race）

### 3.4 安全閘門
- `nav_safe` flag → brain world_state 隨時可中斷
- ALERT priority 進來立刻 cancel goal

---

## 4. P1：動態避障（demo 後）

### 4.1 現況
- reactive_stop 已 work（5/3 demo PASS）
- 動態 detour（繞開後繼續）5/3 L3 FAIL（max_speed 不 enforce + AMCL plateau）

### 4.2 改進方向
- nav_action_server max_speed enforce 修
- AMCL particle resample tuning
- D435 點雲 + RPLIDAR fusion

**工時**：3-5 天，需場地實測。

---

## 5. P2：招手過來（demo 後）

### 5.1 設計
```
ComeHere gesture detected
    ↓
brain_node._on_gesture("come_here")
    ↓
emit follow_person plan
    ↓
nav_action: goto person 位置（face state distance + bearing）
    ↓
到達後：face_keep_alive 模式（不丟失目標）
```

### 5.2 依賴
- Spec 2 動態手勢（ComeHere detection）
- Spec 4 person detection（D435 距離估計）
- nav_capability 新 action：`approach_person`

**工時**：5-7 天

---

## 6. P2：指定物體尋物（demo 後）

### 6.1 設計
```
使用者：「找我的杯子」
    ↓
LLM propose skill: find_object("cup")
    ↓
旋轉掃描（360° 慢轉）
    ↓
看到 cup（YOLO confidence ≥0.6）→ 走過去
    ↓
到達 → 「在這裡」
```

**工時**：5 天，需 Spec 4 的小物件 recall 改善先到位。

---

## 7. P3：自動巡邏（demo 後）

### 7.1 設計
- 預錄 N 個 named_poses（客廳/廚房/玄關）
- 排程：每 30 分鐘走一遍
- 看到 fallen / unknown_face → 中斷巡邏發 alert

**工時**：3-5 天

---

## 8. P3：跟隨模式（最複雜）

### 8.1 風險
- 撞牆 / 撞家具
- 樓梯（Go2 不能上樓梯）
- 跟丟（轉彎 / 過門）

**工時**：10+ 天，demo 後評估是否值得做。

---

## 9. 驗收

### P0（demo 主軸）
- 5/13 場地：goto_relative 1m 成功率 ≥80%
- reactive_stop：對紙箱 100% 觸發
- 30 分鐘連續運行不撞、不卡

### P1-P3（demo 後分階段）
每階段獨立驗收，看下個 sprint 預算。

---

## 10. 實作分階段

| Phase | 內容 | 何時 |
|---|---|---|
| **P0** | demo 主軸：5/13 場地測 + 5/16 demo | demo 前 |
| P1 | 動態 detour 修 | demo 後 sprint 1 |
| P2 | 招手過來 + 尋物 | demo 後 sprint 2 |
| P3 | 巡邏 + 跟隨 | 看預算 |

---

## 11. 後續 spec 銜接
- Spec 1：自我展示中「我會自己在房間裡走」對應本 spec P0
- Spec 2：ComeHere gesture → P2
- Spec 4：尋物導航依賴 P2
