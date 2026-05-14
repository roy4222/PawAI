# OM1 (Modular AI Runtime) — 參考價值分析

> **Date**: 2026-05-02
> **Author**: Roy + Claude
> **Status**: reference-only(哲學參考,不替換現有 stack)
> **Purpose**: 評估 OM1「LLM-first 機器人 runtime」對 PawAI Brain Executive 與 skill lifecycle 的可吸收概念

---

## 一句話結論

**OM1 是「LLM-first 哲學樣板」,不是工程實作樣板**。它的多 LLM 分層、skill lifecycle、AI mode gating 三個概念對 PawAI Brain Executive 有直接啟發;但底層用 Zenoh + 自製 NLDB,與我們純 ROS2 + 結構化 topic 路線不相容,不抄程式碼。

---

## OM1 是什麼

GitHub Trending 上的開源專案,「Modular AI runtime for robots」,以 Unitree Go2 為主要載體,核心特色是**用自然語言當感測器匯流排**(NLDB = Natural Language Data Bus)餵給 LLM 決策。

- GitCode 鏡像: https://gitcode.com/GitHub_Trending/om/OM1
- 中文解析(CSDN): https://blog.csdn.net/gitblog_00247/article/details/156330812

### OM1 系統架構(對照圖 1 — `om1-architecture.png`)

```
SENSORS:    VISION  SOUND  BATTERY/SYSTEM  LOCATION/GPS  LIDAR
              ↓       ↓        ↓               ↓            ↓
DATA →     VLM     ASR    PLATFORM        SPATIAL/NAV    3D ENV
NL                        STATE
              ↓       ↓        ↓               ↓            ↓
NLDB:      "VISION: You see Boyuan, a human. He looks happy and is smiling.
            He is pointing to a chair.
            SOUND: You just heard: Bits, run to the chair.
            ODOM: 1.3, 2.71, 0.32  POWER: 73%"
              ↓
DATA FUSER: 137.0270: 把所有感測器轉成一段自然語言敘述,加 timestamp
              ↓
MULTI-LLM:  FAST ACTION LLM (LOCAL, 300ms)
            + 2s CORE  + 30s MENTOR/REFEREE  (multi-agent)
              ↓
HAL:       MOVEMENT  SOUND  SPEECH  FACIAL EXPRESSION  WALLET
```

### OM1 Full Autonomy 分層(對照圖 4 — `full_autonomy_architecture.png`)

```
OM1 (Brain) ↔ Zenoh_Session ↔ Zenoh_Bridge → ros_sdk
                                              ├ Watchdog (sensor + health)
                                              ├ Orchestrator (SLAM/Nav/Map)
                                              └ OM1_Sensor (low-level driver)
              ├ EDGE PRIVACY (face detection + blurring)
              └ OM1-Video-Processor (RTSP)
              ↓
            Cloud
```

### OM1 Skill Lifecycle(對照圖 2 — `lifecycle.png`)

```
Startup → User → Trigger Mode Switch
              → [ Trigger Words → Mode Triggered → Entry Stage
                  → Mode Active ↔ Timeout Stage (loop back to Active)
                  → Exit Stage ← Timeout Stage (loop back to Exit)
                  → Shutdown ]
```

---

## 三個值得吸收的概念(哲學層級)

### 1. **Multi-LLM 分層決策(FAST / CORE / MENTOR-REFEREE)** ⭐ 最有啟發

OM1 把 LLM 分三層,每層 latency 不同、職責不同:
- **300ms FAST** (LOCAL): 即時 action 決策
- **2s CORE**: 主決策、技能選擇
- **30s MENTOR/REFEREE**: 長時 reasoning、行為修正、安全 referee

**對應到 PawAI**:
| OM1 層 | PawAI 對應 | 缺口 |
|---|---|---|
| 300ms FAST | RuleBrain fallback(< 1ms) | ✅ 已有 |
| 2s CORE | Qwen2.5-7B cloud (~1.5s) | ✅ 已有 |
| 30s MENTOR | (無) | 🟡 demo 後可加 — 對話 session 級的策略修正 |

**現在不做**,5/12 demo 後可考慮加 MENTOR 層做使用者偏好學習(誰今天比較沉默、誰需要安撫)。

### 2. **Skill Lifecycle 五階段 + Timeout Loop** ⭐ Phase A 直接受用

OM1 lifecycle 五階段:`Trigger Words → Entry → Active ↔ Timeout → Exit → Shutdown`

對應到 PawAI Phase A 的 `nav_demo_point` / `approach_person` skill:
| OM1 階段 | PawAI skill 對應 | 我們現況 |
|---|---|---|
| Trigger Words | brain_node 規則表(`speech_nav_demo` / `face_wave_approach`) | ✅ Phase A 規劃中 |
| Entry Stage | Pre-action Validate(三段 capability gate) | ✅ Phase A 規劃中 |
| Mode Active | Nav2 action 執行中 | ✅ 已有 |
| **Timeout Stage(loop back)** | (無 — 目前一次 timeout 就 fail) | 🔴 **缺口** |
| Exit Stage | action result + Brain reset | 🟡 部分 |
| Shutdown | (skill registry unregister) | — |

**關鍵啟發**:**Timeout 不一定是 fail**。OM1 的 Timeout Stage 會 loop back 到 Active(例如 nav 走太久但還在進度上),只有真的卡死才走 Exit。我們 `goto_relative` 目前 timeout 就直接 cancel,可以加一個「progress check」,有進度就 loop。

### 3. **AI Mode Gating(Nav 中關 AI、成功後重開)** ⭐ Safety Layer 受用

OM1 三層安全:
1. **Sensor level**: LiDAR < 1.1m 限制動作選項
2. **Navigation state level**: ROS2 Nav2 lifecycle 監控
3. **AI mode control**: **導航中自動 disable AI,成功後 re-enable**

對應到 PawAI:
| OM1 機制 | PawAI 對應 |
|---|---|
| LiDAR < 1.1m 限動 | `reactive_stop_node` priority 200 mux 強制停 |
| Nav2 lifecycle 監控 | `/capability/nav_ready` (Phase A 新增) |
| **Nav 中 disable AI** | (無) — 我們 brain 在 nav 中仍會收 event 觸發新 skill | 🔴 **缺口** |

**關鍵啟發**:**nav 進行中,brain 應該 mute 或降級**,只接 abort / safety 事件,不接「再走到 X」這種會 preempt 的指令。否則使用者連說兩次「過來」,brain 會 cancel 第一個 nav 重發第二個,Go2 會原地震盪。

→ Phase A 建議:`world_state.py` 加 `is_executing_skill: bool`,Brain 規則表在這個為 true 時只允許 high-priority(SAFETY/ABORT)規則觸發。

---

## 不抄的部分(明確劃線)

| OM1 設計 | 為什麼不抄 |
|---|---|
| **NLDB(自然語言匯流排)** | 把所有感測器轉成自然語言餵 LLM 是高 token 高 latency 賭注;我們 ROS2 結構化 topic + JSON event 可控性遠高 |
| **Zenoh 中介層 + Zenoh_Bridge** | 增加一層異質中介,debug 成本爆炸;我們 ROS2 DDS 已足夠 |
| **DATA FUSER 把多模態壓成一段敘述** | 同上,失去結構化 query 能力 |
| **Cloud-first 架構** | 我們是 hybrid(雲端 LLM + Jetson 感知 + Go2 actuation),不要把 SLAM/Nav 也丟雲 |

---

## Odin vs OM1 vs PawAI 三方對照

| 維度 | Odin | OM1 | PawAI |
|---|---|---|---|
| ROS 版本 | ROS1 Noetic | ROS2 + Zenoh bridge | ROS2 Humble (純) |
| 導航 stack | move_base + DWA/NeuPAN | Nav2 (cloud orchestrator) | Nav2 + AMCL + reactive_stop |
| Brain | 規則式 + Vosk ASR | Multi-LLM (FAST/CORE/MENTOR) | Qwen2.5-7B cloud + RuleBrain |
| 感測器表徵 | 結構化 topic | 自然語言 NLDB | 結構化 topic + JSON event |
| Skill lifecycle | move_base 狀態機 | 5 階段 + Timeout loop | Pre-action Validate(三段) |
| 我們學什麼 | 語義導航 + DWA decay | Multi-LLM + lifecycle + AI gating | — |

→ **Odin 給工程細節,OM1 給架構哲學**。兩個都不是替代品,都是養分。

---

## 行動清單

### Phase A 可立刻吸收(5/2-5/3,low-risk 加值)
1. **`world_state.py` 加 `is_executing_skill: bool`** — Brain 規則表在 skill 執行中只允許 SAFETY/ABORT(對應 OM1 AI mode gating)
2. **`nav_action_server` Timeout 區分「卡死」vs「進度中」** — 有 AMCL pose 進展就 loop,沒進展才 fail(對應 OM1 Timeout Stage loop back)

### 5/12 Demo 後(Phase B+)
3. **Skill Lifecycle 正式化為 5 階段** — Entry / Active / Timeout / Exit / Shutdown,寫成 base class
4. **MENTOR LLM 層**(P3) — session 級使用者偏好學習,30s 週期,跟 FAST + CORE 並行

### 不做
- ❌ NLDB / 自然語言感測器匯流排
- ❌ Zenoh 中介層
- ❌ Cloud SLAM

---

## 來源

- CSDN 解析: https://blog.csdn.net/gitblog_00247/article/details/156330812
- OM1 GitCode 鏡像: https://gitcode.com/GitHub_Trending/om/OM1
- OM1 系統架構圖: https://raw.gitcode.com/GitHub_Trending/om/OM1/raw/98fea18e8e152fded081eb1d2742bb979cd7839e/docs/assets/om1-architecture.png
- OM1 Lifecycle 圖: https://raw.gitcode.com/GitHub_Trending/om/OM1/raw/98fea18e8e152fded081eb1d2742bb979cd7839e/docs/assets/lifecycle.png
- OM1 SLAM 圖: https://raw.gitcode.com/GitHub_Trending/om/OM1/raw/98fea18e8e152fded081eb1d2742bb979cd7839e/docs/assets/full-autonomy-assets/slam_map.png
- OM1 Full Autonomy 架構圖: https://raw.gitcode.com/GitHub_Trending/om/OM1/raw/98fea18e8e152fded081eb1d2742bb979cd7839e/docs/assets/full-autonomy-assets/full_autonomy_architecture.png
