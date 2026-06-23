# Co-run Profiling 程序文件（plan1 T1 骨幹）

> 日期：2026-06-13　狀態：T1 骨幹（pure-software，已單測綠）；T5/T6 數據待 Roy 真機回填
> 權威計畫：[2026-06-13-plan1-runtime-layout-corun-profiling.md](../superpowers/plans/2026-06-13-plan1-runtime-layout-corun-profiling.md)
> 全程 **NO-MOTION**：本程序只量資源 + topic 健康，不發 `goto_relative` / `cmd_vel` / 任何 motion。

本文件配合三支腳本使用：

- `scripts/corun_topics.txt` — 每配置要 watch 的 topic 清單（§9.1）。
- `scripts/corun_profile.sh` — profiling orchestrator（每 interval 抓資源 snapshot + `ros2 topic hz`）。
- `scripts/corun_profile_parse.py` — log → CSV + PASS/WARNING/FAIL 判定（§9.2）。

執行範例（Jetson，唯讀 attach，另開 ssh session 跑，不動既有 demo 腳本）：

```bash
# 配置 A：brain-full baseline（等 ASR warmup ~60s 後）
bash scripts/corun_profile.sh --config A --duration 300 --interval 15
python3 scripts/corun_profile_parse.py --config A
```

> ⚠️ T2–T6（真機跑 + cold-start）需 Roy 在場、Jetson 真機，**T1 不代跑、不假裝跑過**。
> 本文件的決策表 / 8GB 互斥表 / cold-start 表目前為**空白模板**，待真機 CSV 出來後由 T5/T6 回填。

---

## §9 — 量測規格

### §9.1 Watch-topic 清單

對映 `scripts/corun_topics.txt`（格式 `topic,expected_hz,configs`）。「期望 Hz」是中心值，判定一律走 §9.2 的單一頻帶（不另立容差數字）。`evt` = event-driven / on-demand，判定看「有沒有量到」而非速率帶。

| Topic | 期望 Hz | 出現於配置 | 來源 |
|-------|:------:|:----------:|------|
| `/state/perception/face` | ~10 | A,B,C | CLAUDE.md 人臉主線 |
| `/face_identity/debug_image` | ~7 | A,B,C | MEMORY 3/18 smoke |
| `/perception/object/debug_image` | ~7 | A,B,C | CLAUDE.md object §驗證 |
| `/event/object_detected` | evt | A,B,C | CLAUDE.md object |
| `/tts` | evt | A,B,C | CLAUDE.md 快速驗證 TTS |
| `/capability/depth_clear` | 5 | A,B,C | `depth_safety_node` |
| `/vision_perception/status_image` | 8 | A,B,C | CLAUDE.md 視覺儀表板 |
| `/scan_rplidar` | ~10 | B,C | nav 腳本 `:78` |
| `/state/nav/heartbeat` | 1 | C | nav monitor block |
| `/state/nav/status` | 10 | C | nav monitor block |
| `/state/nav/safety` | 10 | C | nav monitor block |
| `/capability/nav_ready` | ~1 | C | nav monitor block |

> `ros2 topic hz` 跑法：每 sample interval 對清單每個 config-match topic 跑 `timeout 6 ros2 topic hz <topic>` 取平均（6s 視窗）。`/tts` 延遲量法另記（發 `ros2 topic pub --once /tts ...` 記到喇叭出聲牆鐘），不影響量資源。

### §9.2 Pass thresholds（parser 判定）

對映 `corun_profile_parse.py` 的 band 函式（`judge_ram` / `judge_headroom` / `judge_gpu` / `judge_temp` / `judge_topic_hz` / `judge_node_crash` / `oom_verdict`）。

| 指標 | PASS | WARNING | FAIL | 來源 |
|------|:----:|:-------:|:----:|------|
| RAM used（of 7.4 GB） | < 5.5 GB | 5.5–6.5 GB | > 6.5 GB（OOM-risk） | jetson-status budget |
| RAM headroom | ≥ 1.9 GB | 0.9–1.9 GB | < 0.8 GB | jetson-status budget + 記憶體預算 §≥0.8GB |
| GPU load | < 95% | 95–99% | 100%（throttle） | jetson-status budget |
| 溫度（max zone） | < 65°C | 65–80°C | > 80°C | jetson-status budget |
| 功耗 | < 12W | 12–15W | > 15W（MAXN limit） | jetson-status budget |
| topic Hz（每 watch topic） | 期望 ±20% | ±20–40% | 偏離 > 40% 或 0 | §9.1 期望值 |
| node crash | `ros2 node list` 與 baseline 一致 | — | 少任一 node | crash 偵測 |
| `/tts` 延遲 | 與 A baseline 比 ≤ +30% | +30–60% | > +60% 或無聲 | 相對 baseline |
| gateway(8080) | curl `/health` 200 | — | 連線 refused / 逾時 | Foxglove 不壓垮 gateway |

> **配置 pass = 全列 PASS 或最多 WARNING 且無 FAIL**。任一 FAIL ⟹ 該配置判 unstable。
>
> **OOM-risk abort（現場安全煞車，非配置自動判 FAIL）**：`corun_profile.sh` 維持 10s 滑動視窗，**只有 RAM used 連續 > 6.5GB 達 ≥10s** 才 emit `OOM-RISK ABORT` 並停止 sample loop（**不殺 stack**，由 Roy 決定清場）。瞬時觸頂（touch 6.6GB 一次後回落 < 6.5GB）只記 WARNING、不 abort。parser `oom_verdict` 以同一 sustained 規則重判：spike → WARNING、sustained → ABORT、全清 → OK。

---

## §11.1 — 4-branch 決策樹（Q2 鎖定，本計畫核心交付）

> **stable / unstable 精確定義**：一個配置 `stable` = §9.2 每一指標都是 PASS，或最多 WARNING 且零 FAIL；`unstable` = 任一指標 FAIL。FAIL 門檻直接引 §9.2，判讀者不得自行加減門檻。

```
量完 A/B/C（NO-MOTION）後，自上而下取第一個 match 的 branch：

┌─ branch 4 "BRAIN-FIRST"：A（brain baseline）unstable
│     觸發 = A 配置任一 §9.2 指標 FAIL（RAM used >6.5GB / 溫度 >80°C /
│            brain topic（face/object/tts）任一 crash 或 Hz 偏離 >40%）。
│     → 先修 brain demo，nav 完全不談。S1 退第三人稱 + Studio brain only，
│       map/LiDAR 走影片/截圖。（A unstable 時 B/C 不必再判，直接此 branch。）
│
├─ branch 1 "C-CORESIDENT"：A stable 且 C（brain + full-nav-stack）stable
│     觸發 = C 配置全指標 PASS。
│     → S1 可避免換 stack（brain + nav 同跑）。
│       ★ 仍不發 goto_relative ★ — map/LiDAR/pose 只當「視覺證據」。
│       S1 形態交 plan6 決定 live 證據呈現。
│
├─ branch 2 "B-RESIDENT-LIDAR"：A stable、C unstable、B stable
│     觸發 = C 任一指標 FAIL，但 B 全指標 PASS。
│     → brain 駐留 + raw LiDAR/Foxglove 當視覺證據 + operator-assisted。
│       不跑 nav2/amcl（省 RAM）。
│
└─ branch 3 "A-ONLY-VIDEO"：A stable、B 也 unstable
      觸發 = B 任一指標 FAIL，但 A 全指標 PASS（或最多 WARNING）。
      → S1 live = 第三人稱 + Studio brain only；map/LiDAR 走影片/截圖。
```

> **無論落哪個 branch，S1 都不啟 `goto_relative` 當主線**（nav NOT_DEMO_READY）。live-motion 選項（若有）= plan6 的 DriveOnHeading，且須 T0 fix + D1–D5 + θ_error<5° + e-stop + n=3，**不在本計畫**。

---

## S1 runtime layout 決策表（空白模板 — 待 T5 回填）

> 待 T2–T4 真機 CSV 出來後填；每格話術須過 [claim-wording](2026-06-13-nav-618-claim-wording.md) S1–S8 / F1–F10 掃描（不得出現 autonomous navigation / 即時 SLAM / 動態繞障 / D435 已融合 / fallen / 2m 物體 / 可靠顏色 / 19 色）。數字須等於 CSV，不得自編。

| 項目 | 內容（待填） |
|------|--------------|
| Branch 落點（1/2/3/4） | _（待 T5 + Roy 6/17 拍板）_ |
| S1 runtime layout | _（待填）_ |
| 對外可講話術（過 claim-wording） | _（待填）_ |
| 引用的 CSV 數字（RAM / 溫度 / Hz） | _（待填，須 = CSV）_ |
| Roy 6/17 彩排簽註 | _（待填）_ |

---

## 8GB 互斥事實表（空白模板 — 待 T4/T6 回填）

> master plan §2.2「nav stack 與 brain demo stack 8GB 互斥（不能同跑）」由 C 配置量化驗證。下表待真機數據回填。

| 配置 | RAM used 峰值 | headroom | 溫度峰值 | OOM verdict | D435 在線 | 判定 |
|------|:------------:|:--------:|:--------:|:-----------:|:--------:|:----:|
| A（brain-full） | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ |
| B（brain + raw-LiDAR + Foxglove） | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ |
| C（brain + full-nav-stack 同跑） | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ | _（待填）_ |

---

## Cold-start 成本 + 交接時間表（空白模板 — 待 T6 回填）

> 量 `clean_full_demo.sh` → `start_full_demo_tmux.sh` 到 `/tts` 可發 / face 出圖 / ASR warmup done 的牆鐘時間；同量 nav stack stop→start 到 `/state/nav/heartbeat` 1Hz 的時間。推出 S1(nav)→S2(brain) 8GB 交接最短間隔（master open question：1 分鐘 gap 是否需旁白）。數字寫入 `runtime/profiling/2026-06-13-coldstart.csv`。

| 量測項 | 牆鐘時間（待填） |
|--------|:----------------:|
| brain cold-start（clean → `/tts` 可發 + face 出圖 + ASR warmup done） | _（待填，s）_ |
| nav cold-start（stop → `/state/nav/heartbeat` 1Hz） | _（待填，s）_ |
| S1(nav) → S2(brain) 8GB 交接最短間隔 | _（待填，s）_ |
| 交接是否需旁白解釋（master open question） | _（待填）_ |
