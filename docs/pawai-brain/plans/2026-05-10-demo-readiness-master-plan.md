# Demo Readiness Master Plan — 5/11→5/18

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **Demo**: 5/18 final（5/16 dry-run，5/12 晚移交學校）
> **取代**：先前 `2026-05-10-spec1-llm-naturalness-plan.md` §3-§7（Spec 1 縮成 Brain Minimum，其他工作流獨立成 plan）
> **Owner**: Roy
> **Plan 用途**：5 條工作流 orchestration + 逐日排程 + Go/No-Go gate

---

## 0. 戰略基線（鎖死，不再回頭討論）

| 維度 | 決定 |
|---|---|
| Demo 形式 | **A-led hybrid**：60s PawAI 自介 → Roy 帶 3-4 段穩定互動 → PawAI 接續對話 |
| 雙支柱 | **PawAI Brain**（Spec 1 minimum）+ **導航避障**（Spec 5 P0） |
| 尋物策略 | **X+**：物體辨識 + nav 分段展示 + PawAI 講敘事，不真做閉環 |
| 模型 | 不盲換，5/12 中午 eval ≥8/10 鎖；<8/10 才考慮（demo 10 題 A/B）|
| 移交日 | **5/12 晚** Go2 + Jetson 帶去學校 |
| Brain Freeze | **5/12 中午** `git tag brain-freeze-v1` |
| Demo 話術 | nav 不穩 → PawAI 自己說「場測中」；功能未完 → PawAI 誠實說「正在開發」 |

呼應專題名稱：**「PawAI 基於多模態感知融合之自主尋物與具身互動」** — Brain（具身互動）+ Nav（自主尋物前置）兩支柱要在 demo 同時亮相。

---

## 1. 五條工作流

| 代號 | Plan | 主題 | 視窗 | 阻塞移交？ |
|:---:|---|---|---|:---:|
| **A** | [`brain-minimum-checklist`](./2026-05-10-brain-minimum-checklist.md) | persona 6 檔 + 10-prompt eval + 60s 自介 freeze | 5/11–5/12 中 | ✅ |
| **B** | [`nav-root-cause-burndown`](./2026-05-11-nav-root-cause-burndown.md) | 家裡逐項排除：LiDAR / D435 / TF / mux / AMCL / goto 0.3-0.5m | 5/11 晚–5/12 晚 | ✅ |
| **C** | [`runtime-fallback-readiness`](./2026-05-12-runtime-fallback-readiness.md) | 三種啟動模式：Normal / No-AI / Mac-as-operator | 5/12 中–晚 | ✅ |
| **D** | [`free-conversation-audio-readiness`](./2026-05-12-free-conversation-audio-readiness.md) | USB 麥 + AirPods + 自由對話 3-5 min（不靠 Studio button） | 5/12 中–晚 | ✅ |
| **E** | [`mac-school-network-readiness`](./2026-05-12-mac-school-network-readiness.md) | `config/school_demo.env` + 寫死 IP/host/port 集中 + Mac wrapper | 5/12 晚 移交前 | ✅ |

**全部 5 條都是移交前 P0**。任一條沒過 → 帶去學校會炸。

---

## 2. 依賴與並行

```
5/11           A.Brain  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
               B.Nav-diag (家裡 LiDAR/D435/TF/mux 等)  ━━━┫
                                                          ┃
5/12 AM        A.Brain (修 + freeze)  ━━━━━━━━━━━━━━━━━━━┫
               B.Nav-diag (AMCL + goto 0.3/0.5m)  ━━━━━━━┫
                                                          ┃
5/12 PM        C.Runtime fallback (三模式 smoke)  ━━━━━━━┫
               D.Audio (USB 麥 + AirPods 自由對話)  ━━━━━┫
               E.Mac/Network (env file + 寫死 IP 抓出)  ━┫
                                                          ┃
5/12 19:00     ━━━━━━━━━━━ ALL FREEZE ━━━━━━━━━━━━━━━━━━━┛
5/12 20:00     Go2 + Jetson + 配件 → 學校
5/13–5/15      Nav Sprint @ 學校（驗證「只剩空間假設」是否成立）
5/16           Dry-run / 預演
5/17           Only bug fix
5/18           FINAL DEMO
```

並行說明：
- A & B **必須**並行（Brain 無法等到 Nav 做完才開始；Nav 也不能等 Brain freeze）
- C, D, E 在 5/12 PM 並行，三條彼此沒強依賴
- E 抓出寫死 ref 後 **C 和 D 的測試指令會用到**（一律走 `school_demo.env`）

---

## 3. 5/11–5/18 逐日排程

### Day 1｜5/11 Sun
- AM-PM：**A.Brain Minimum** day 1（baseline → MISSION → persona 改 → load test）
- 晚：**B.Nav-diag** 第一波（LiDAR + D435 + TF + cmd_vel/mux + reactive_stop 各 30 分鐘）

**Gate**：6 檔 persona 載入綠 + Nav 5 項感測/控制鏈 pass/fail 寫進 burndown 表。

### Day 2｜5/12 Mon — 移交日（最緊）
- 早 AM：A.Brain 修 eval 看到的 persona 問題（≤1.5h）
- AM 中：A.Brain 自介 smoke × 5
- **中午**：A.Brain 最終 10-prompt eval ≥8/10 → `git tag brain-freeze-v1`
- 中午：A demo fallback 話術文件落檔
- PM：**並行 4 條**
  - B.Nav-diag：AMCL + `goto_relative 0.3m × 5` + `0.5m × 5`
  - C.Runtime fallback：三模式 smoke
  - D.Audio：USB 麥 + AirPods 自由對話 5 min
  - E.Mac/Network：建 `config/school_demo.env`、改腳本只讀 env、Mac wrapper、6 項連通驗證
- 18:00：B–E 結論表凍結，所有「fail」項標記 demo 降級方案
- 19:00：**ALL FREEZE**
- 20:00：Go2 + Jetson + RPLIDAR + D435 + 喇叭 + USB 麥 + XL4015 + 充電線 + e-stop + 紙箱 + 地圖檔備份 → 移交

### Day 3｜5/13 Tue — Nav Sprint Day 1（學校）
- AM：場勘 6 項（C1-C6）+ 學校 Wi-Fi 走 `config/school_demo.env` 切換
- PM：建圖（cartographer）+ Foxglove 看 .pgm
- 晚：第一輪 dry-run `goto_relative 0.5m × 5`

**Gate**：地圖檔落地 + AMCL particles < 30s 收斂 + 0.5m ≥3/5。

### Day 4｜5/14 Wed — Nav Sprint Day 2
- AM：goto 0.5/1.0/1.5m 各 ×10、調 DWB
- PM：reactive_stop 紙箱 ×10、30s 連續
- 晚：物體辨識 + nav + brain 同跑壓測

**Gate**：1.0m ≥4/5 + reactive_stop 100% + 三系統同跑 30s 穩。

### Day 5｜5/15 Thu — Nav Sprint Day 3
- AM：全 stack dry-run + A-led hybrid 第一次完整跑
- PM：降級路徑驗證 ×3
- 晚：**demo go/no-go 決定**（Go / Soft Go / No-Go）

### Day 6｜5/16 Fri — Dry-run
- AM：A-led hybrid × 2（含教授假提問 5 題）
- PM：修 dry-run bug
- 晚：定稿一次

**Gate**：< 5 min 流暢 + Q&A 全 hit。

### Day 7｜5/17 Sat — Bug fix only
- AM：bug fix、XL4015 電源最終檢查
- PM：整場計時 ×3，誤差 <30s
- 晚：彩排、e-stop 觀察員 brief

### Day 8｜5/18 Sun — **FINAL DEMO**
- 前 30 分：D1-D10 設備 checklist
- 上場
- Demo 後 retrospective

---

## 4. Go/No-Go Gates（每日定稿時刻）

| 日 | 時刻 | Gate | 失敗動作 |
|---|---|---|---|
| 5/11 晚 | 22:00 | A & B 各自第 1 波過 | A 卡 → 5/12 直走簡化 freeze；B 卡 → 5/12 主攻 B |
| **5/12 中** | **12:00** | **A eval ≥8/10** | <8/10 仍 freeze，靠話術補；不延期 |
| **5/12 晚** | **19:00** | **B/C/D/E 全結論表填完** | 任一 fail 必須有降級方案，否則重做 |
| 5/14 晚 | 22:00 | Nav 1.0m ≥4/5 + reactive_stop 100% | 走 Spec 5 plan §5 降級 |
| 5/15 晚 | 22:00 | Demo go/no-go 鎖 | No-Go 切純 brain demo |
| 5/16 晚 | 22:00 | <5 min 流暢 | 砍最不穩段落 |

---

## 5. 砍 / 留紅線（最終版）

### ❌ 砍（demo 後再說）
- Spec 1 SAY 解綁完整版（round-trip + `_resolve_say_text` + 三分支）
- `SAY_TEXT_POOLS` 變體池
- 6 skill 全 SAY 解綁
- `self_introduce` 雙 SAY + 4 motion 重構
- 換模型（除非 5/12 中午 <5/10）
- OpenClaw 9 層
- 動態手勢、姿勢 7 種、顏色辨識、室內 dataset
- Nav P1 動態避障 / P2 招手 / P3 巡邏 / 跟隨
- Spec 6 P1/P2、待機動作

### ✅ 留
- A.Brain Minimum 全做
- B.Nav diagnostic 7 項全驗
- C.Runtime fallback 三模式
- D.Audio USB 麥（AirPods 看 5/12 PM 結果）
- E.school_demo.env + Mac wrapper
- Spec 5 P0：goto 1m + reactive_stop（學校場測）
- 物體辨識：YOLO26n 80 類預設跑著
- 人臉：alice/grama/roy（既有）
- 靜態手勢 3 個：palm/thumbs_up/peace（既有）

---

## 5.5 v2 Demo 目標對齊表

這張表是把「PawAI Demo 測試功能清單 v2」對到本 sprint 的實際處理方式。原則是：**P0 保 demo 體驗與移交存活；P1 只做能穩定展示的切片；其餘明確標 demo 後，避免現場誇大。**

| v2 目標 | Demo 前處理 | 狀態 |
|---|---|---|
| LLM 自然自介、知道專案目標、能引導教授互動 | A.Brain Minimum：MISSION + persona 6 檔 + 10-prompt eval + 60s 自介 smoke | **P0** |
| 語音自由對話、降低延遲、不依賴 Studio button | D.Audio Readiness：USB 麥 3-5 min 自由對話；AirPods 只做可行性評估 | **P0** |
| Mac 操作端、學校網路、No-AI 啟動 | C.Runtime + E.Mac/Network：Normal / No-AI / Mac-as-operator 三模式 smoke | **P0** |
| 導航避障確認是不是空間問題 | B.Nav diagnostic：LiDAR / D435 / TF / mux / AMCL / goto 0.3-0.5m 逐項排除 | **P0** |
| SLAM / Nav2 基本展示、遇障停下 | 5/13-5/15 學校場測：goto 1m + reactive_stop；不穩就降級 | **P0** |
| 人臉辨識打招呼 | 使用既有 alice / grama / roy 流程；不新增人臉功能 | **P1** |
| 手勢辨識靜態 6 種 | Demo 前只保 palm / thumbs_up / peace；fist / index 視時間；OK 改走語音確認，避免誤觸 | **P1 / 部分砍** |
| 姿勢辨識站、坐、跌倒 | 只做 smoke / 展示判斷；若時間不足，至少保留跌倒作 safety story | **P1** |
| 物體辨識 | YOLO26n 80 類預設跑著，展示 cup / chair / bottle 等常見物；不做模型 A/B、顏色、dataset | **P1** |
| 自主尋物 | X+：物體辨識與 nav 分段展示，PawAI 誠實說明閉環正在場測 | **敘事保留** |
| Skill 自由組合 | 只驗 2-3 個 demo prompt，例如「站起來並打招呼」；不做新 planner | **P1** |
| 雪寶式動作、待機動作、高感情 TTS | demo 前不做，避免拖垮 Brain/Nav 主線 | **SKIP→demo 後** |

---

## 6. 風險矩陣

| 風險 | 觸發日 | 對策 |
|---|---|---|
| Brain 5/12 中午仍 <8/10 | 5/12 | 不延期；用最佳版本 freeze + 話術補 |
| 學校 Wi-Fi 不穩 / IP 換 | 5/12+ | E.school_demo.env + Mac 熱點備援 |
| Mac 連不上 Jetson | 5/13+ | E 必須 5/12 PM smoke 過 |
| LLM tunnel 學校網路打不開 | 5/13+ | C.No-AI 模式：canned 自介 + manual skill |
| AirPods 延遲 >800ms | 5/12 PM | D：直接砍 AirPods，用 USB 麥 + Go2 喇叭 |
| Nav 0.5m 在家就 fail | 5/12 PM | B：找出根因，可能不是空間問題；學校重驗 |
| Nav 0.5m 在家 pass、學校 fail | 5/13+ | 確認真為空間問題，調 footprint / DWB |
| XL4015 斷電 | 任何 | 帶備援充電線；demo 用 Ethernet 直連 |
| Brain freeze 後嚴重 bug | 5/13+ | hotfix tag `brain-hotfix-Nx`，不重構 |

---

## 7. 同步要更新的既有文件

5/11 開工前一併改掉，避免 stale 文件誤導：

| 文件 | 動作 |
|---|---|
| `docs/pawai-brain/specs/2026-05-10-demo-quality-roadmap-index.md` | demo 改 5/18 final + 5/16 dry-run；Spec 1 範圍標 superseded by Brain Minimum |
| `docs/pawai-brain/plans/2026-05-10-spec1-llm-naturalness-plan.md` | 加 banner：5/12 移交，本 plan §3-§7 superseded by Brain Minimum + master plan |
| `references/project-status.md` | 寫進 5/11–5/18 v2 倒數 |
| `CLAUDE.md` | 修「Studio start.sh port 8001 → 8080」過時項；補 `config/school_demo.env` 用法 |

---

## 8. 給後續 sprint 的指針（demo 後）

A+ persona 改動可保留；SAY 解綁、變體池、6 skill 解綁、Spec 2/3/4 完整版都留 demo 後 retrospective 後決定要不要做。
Nav P1 動態避障靠這次學校場測拿到的 baseline 數據再規劃。

---

**End of Master Plan**
