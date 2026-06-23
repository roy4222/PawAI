# Roy HITL Queue — 六 lane 全部 HITL 單一隊列（2026-06-13）

> **日期**：2026-06-13　**狀態**：QUEUE — 彙整 [aggressive 套件](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md) 六份 lane plan 全部 HITL 項成單一隊列
> **這份是什麼**：把 [Lane 1](../archive/superpowers-legacy/plans/2026-06-13-lane1-brain-ism-staged-enable-plan.md)~[Lane 6](../archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) §8 的所有「Roy 在場才能做」的 HITL 項，按 **HITL#1 demo lane / HITL#2 demo lane / nav 場測 B-9 / vision 矩陣日 B-3** 分組，每項含 lane 來源、前置 PR、指令級步驟、預估時長、abort criteria、**空白結果欄**。
> **這份不是什麼**：① 不是逐行操作 SOP（最安全 operator runbook = [`2026-06-18-hitl-oneshot-runbook.md`](2026-06-18-hitl-oneshot-runbook.md)，nav DRY-RUN 段）；② 不是 plan 本體（各項細節以對應 lane plan §6/§8 為權威）；③ 不替代 [ladder](../navigation/2026-06-13-nav-capability-ladder.md) / [claim wording](../navigation/2026-06-13-nav-618-claim-wording.md)——結果回填那兩份。
> **時段預算**（[master §5](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md)）：固定兩晚 demo-lane HITL（**#1 / #2**，各 ~2h）＋兩個可選大時段（**B-3** vision 矩陣日、**B-9** nav 場測，各半天）。四天內兩大時段建議至多選一個提前、另一個 post-6/18。

---

## ⚠️ 全隊列共通安全護欄（先讀，不可違反）

- **8GB 互斥**：nav stack 與 brain demo stack **不能同跑**（6/7 實證）。demo-lane HITL（#1/#2 + B-3 brain 部分）走 demo stack；**B-9 nav 場測走 nav stack，需專屬時段、開場前先 `pawai demo stop`**。
- **Go2 motion 限定**：只有標「需 Go2 motion」的項才動狗；其餘 Jetson-only（deploy/smoke/瀏覽器走查/感知流）**Go2 不動**。
- **執行授權邊界**（[master §5 分類總表](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md)）：Roy 不在場一律不做本隊列任何項；不可預跑、不可「先試一下」。做完才能把 [ladder](../navigation/2026-06-13-nav-capability-ladder.md) proven table 對應格升級。
- **誠實底線**：AFK 軟體只能說「code merged + 單測綠，待真機驗證」；**本隊列的項過了才算 HITL 通過 / 功能驗證**。
- **e-stop 前置**：任何 Go2 motion 項，開始前口頭確認 `emergency_stop.py` engage 終端就位（見 §nav abort 條 6）。

---

## A. HITL #1（demo lane，6/14 晚，~2h）

> 走 demo stack（brain）。涵蓋 Lane 1 2a/2b、Lane 2 Evidence 走查、Lane 3 smoke family、Lane 5 face 驗證。開場：deploy → demo lane 跑起。

| # | 項 | lane 來源 | 前置 PR（merged + 單測綠） | 指令級步驟 | 需 Go2 motion | 預估 | abort / 中止手段 | 結果 |
|---|---|---|---|---|:---:|---|---|---|
| H1-0 | deploy + demo 起 | 共通 | — | `pawai jetson deploy --module brain`（或手動 rsync，CLI deploy 曾刪 .env 走查）→ demo lane 起 → `tmux ls` + `ros2 node list` 數 process（不只信 CLI 成功訊息，6/4 CRLF 假成功教訓） | 否 | 15 min | demo 沒起全綠 → 停，先修環境 | ☐ |
| H1-1 | Lane 1 stage 2a（demo_phase） | Lane 1 §8 | T1-0 + T1-1 | `ros2 param set /brain_node ism_enabled true` → `ism_stage_2a_demo_phase true`；`demo_phase` 切 `s3_object` → 比手勢 → trace `phase:s3_object:gesture` suppress；切回 `all` 放行 | 否（感知流） | 15 min | 該 suppress 沒 suppress / callback 例外 → `ism_stage_2a_demo_phase false` 退；該 stage 當日標未過 | ☐ |
| H1-2 | Lane 1 stage 2b（confirm 非黑洞） | Lane 1 §8 | T1-2pre + T1-2 | 開 `ism_stage_2b_confirm true`；thumbs_up → confirm 在飛 → 拿杯子 → cup suppress-with-trace 非黑洞 → 比 OK → wiggle 執行；第二輪不比 OK → 30s timeout 回 IDLE | **是**（wiggle） | 20 min | wiggle 非預期動作 / confirm 黑洞重現 → `ism_stage_2b_confirm false` 退；e-stop 待命 | ☐ |
| H1-3 | Lane 2 Evidence Center 走查 | Lane 2 §8 | T2-1~T2-5 | deploy gateway+frontend → demo lane 跑一段產真 trace → 瀏覽器開 `/studio/evidence`：session 列表含今晚 session、timeline 與動作對得上、suppressed 中文理由正確、detail 無 PII（人名 `[private]`）→ 下載 redacted JSONL + 報告 → 歷史模式選 6/12 舊 session | 否 | 20 min | 頁面炸/PII 洩漏 → 退回既有 Suppressed viewer；`PAWAI_TRACE_STORE_ENABLED=0` 可關落盤 | ☐ |
| H1-4 | Lane 3 smoke family + status | Lane 3 §8 | T3-1/2/4/6 | demo lane 跑著：`pawai smoke vision`（static 綠）、`pawai smoke object`（static 綠）、`pawai smoke full`（綠）、`pawai status` brain 區塊值正確（shadow/demo_phase/ism stage） | 否 | 15 min | smoke 誤判（只讀不傷系統）→ 修判定條件 | ☐ |
| H1-5 | Lane 3 face delete 一輪 | Lane 3 §8 | T3-5 | 對測試身份：`pawai face delete <test>` → rebuild → 重啟 face node 重訓 → `pawai face list` 確認幽靈警示 | 否 | 10 min | 刪錯人 → 重新 enroll（rm 路徑經消毒、不可能 face_db 外） | ☐ |
| H1-6 | Lane 5 face pickle→npz 驗證 | Lane 5 §8 | T5S-5 | rebuild 重訓（寫 npz）→ roy sim 分數不退化（對照 6/8 的 0.73-0.81 帶）→ list/delete 流程正常 | 否 | 10 min | sim 退化 → 不 rebuild 即回原狀（pickle fallback 在、舊 pkl 永遠可讀） | ☐ |
| H1-7 | evidence pull 收尾 | Lane 1/3 §8 | T3 evidence pull（已有） | `pawai evidence pull` 拉 trace + nav runtime（備份）→ 摘要 events/suppressed/shadow | 否 | 5 min | — | ☐ |
| H1-收尾 | stage flag 保持 | Lane 1 §8 | — | 過的 stage 保持 on 跑 10 min demo 動線，觀察無 callback 例外 / 無延遲回退才算過 | 否 | 10 min | 任何「該回應沒回應」且 trace 無法解釋 → 該 stage flag-off | ☐ |

**合計 ~2h**（H1-2 是唯一 Go2 motion 項，wiggle 小幅）。

---

## B. HITL #2（demo lane，6/15 晚，~2h）

> 走 demo stack。涵蓋 Lane 1 2c/2d、Lane 5 auth-on 彩排。

| # | 項 | lane 來源 | 前置 PR | 指令級步驟 | 需 Go2 motion | 預估 | abort / 中止手段 | 結果 |
|---|---|---|---|---|:---:|---|---|---|
| H2-1 | Lane 1 stage 2c（executing watchdog） | Lane 1 §8 | T1-3pre + T1-3 | `ism_enabled true` + `ism_stage_2c_executing true`；短暫開 `stranger_alert_enabled` 重演 6/9 卡死（或發不回終態的 mock skill_request）→ timeout_s 後 trace `watchdog_timeout` + cup/greet 恢復回應 | 建議是 | 20 min | 正常 skill 被誤殺 / watchdog 沒觸發 → `ism_stage_2c_executing false` 退 | ☐ |
| H2-2 | Lane 1 stage 2d（speaking chokepoint） | Lane 1 §8 | T1-4 | 開 `ism_stage_2d_speaking true`；觸發長 TTS（chat 長句）→ TTS 中拿杯子 → suppress `gate:speaking`；講完再拿 → 放行 | 否 | 15 min | tts 期間誤放/誤擋 → `ism_stage_2d_speaking false` 退 | ☐ |
| H2-3 | Lane 5 auth-on 彩排（六步第⑤步） | Lane 5 §8 | T5S-3（token wiring） | Jetson 開 auth-on（env）→ 跑 Studio 全流程（按鈕/push-to-talk/video/nav panel/Evidence 頁）+ `pawai status`/smoke + `security_smoke.sh`（無 token 401 / 偽 Origin 拒 / `redact=0` 無 token 403）→ 全綠 = B-6 可選發表日 on | 否（Go2 低度） | 30 min | 任何紅 → 記錄、發表日維持 default-off（翻回 default-off 一個 env，S0-2 已驗 byte-identical） | ☐ |
| H2-4 | Lane 5 whitelist-on 動作回歸 | Lane 5 §8 | T5S-1 | param 切 `webrtc_api_filter_mode=whitelist` → demo 動作全流程（wiggle/hello/sit/TTS Megaphone）不誤殺 → security smoke 的 banned 拒絕項過 → 切回 `off`（或 Roy 點頭留 `blacklist` 進發表） | **是** | 20 min | 動作被誤殺 → 切 `blacklist`（現狀+拒 3 條 banned）或 `off`（秒級 byte-identical）；e-stop 待命 | ☐ |
| H2-收尾 | stage flag 保持 | Lane 1 §8 | — | 過的 stage 保持 on 跑 demo 動線觀察 | 否 | 10 min | 同 H1-收尾 | ☐ |

**合計 ~1.5-2h**（H2-1/H2-4 涉 Go2 motion）。

---

## C. Nav 場測（B-9，nav stack，~半天 2.5-3h，與 demo lane 互斥）

> **走 nav stack**——開場前先 `pawai demo stop`（8GB 互斥）。場地：客廳 indoor_tight。開場儀式：`pawai smoke nav --static`（[Lane 3 T3-3](../archive/superpowers-legacy/plans/2026-06-13-lane3-cli-v2-completion-plan.md)）→ goto 0.3m 一發暖身。**Go2 全程需要（motion）**；abort criteria（§nav abort 六條）全程生效、逐條勾。

### C-abort：nav 場測硬性 abort criteria（[Lane 6 §8 六條](../archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)，任一觸發 = 當場中止該項，整段重新評估後才續）

1. **Go2 非預期加速 / 非命令方向移動 → abort**（`emergency_stop.py` engage，當日該能力標 FAIL）。
2. **reactive_stop 該觸發沒觸發**（障礙進 danger 區未停）→ **abort 全部後續 motion 項**，先用 [`lidar_front_sector.py`](../../scripts/lidar_front_sector.py) 診斷。
3. **AMCL covariance 在黃/紅區（>0.3）卻要送 >0.5m goal → 禁送**（先走 N2 covariance SOP 收斂進 green；黃區只准 ≤0.5m）。
4. **stop-resume 放開後衝速明顯過快（lunge 重現）→ abort**，resume 項當日不再試、退 operator-confirm only。
5. **狗與障礙/牆距離小於安全距離（機鼻 <0.3m）仍在動 → abort**。
6. **operator 的 e-stop（`emergency_stop.py` engage 終端）未就位 → 不開始任何 motion 項**；每項開始前口頭確認「e-stop ready」。

### C 隊列（依賴序：N1→N2→N3→N4→(stretch)N5→N6→N7→N8→還原）

| # | 項 | lane 來源 | 前置（PR / N 依賴） | 指令級步驟 | 預估 | 對應 ladder 升級 | 結果 |
|---|---|---|---|---|---|---|---|
| 開場 | smoke nav static + 暖身 | Lane 3 / Lane 6 §8 | T3-3 merged | `pawai demo stop` → 起 nav stack（`bash scripts/start_nav_capability_demo_tmux.sh`，`REACTIVE_PROFILE=indoor_tight`）→ 等 ~50s → Foxglove 設 `/initialpose` → `pawai smoke nav --static` 綠 → goto 0.3m 一發暖身 | 15 min | — | ☐ |
| N1 | poses/routes 重錄 | Lane 6 §8 | T6-2 | `ros2 action send_goal /log_pose go2_interfaces/action/LogPose "{name: alpha, log_target: named_poses}"` × 2-3 點 → 組 1 條短 route → `pawai evidence pull` 驗備份（拉回 `runtime/nav_capability/`） | 20 min | [C10](../navigation/2026-06-13-nav-capability-ladder.md) `NOT_DEMO_READY`→`NEEDS_RETEST` | ☐ |
| N2 | covariance SOP 實測 | Lane 6 §8 | T6-5 軟體 | `python3 scripts/nav_covariance_probe.py`（新）跑收斂曲線（靜置 vs 0.3m warmup 兩模式）→ 填黃帶決策表（該等 / 該推 0.3m / 該重設 pose） | 20 min | [C3/C7](../navigation/2026-06-13-nav-capability-ladder.md) covariance SOP 閉合 | ☐ |
| N3 | 短距可靠性 | Lane 6 §8 | N2 | `scripts/send_relative_goal.py` 0.3 / 0.5 / 1.0m × **n=3**（1.0m 先用 N2 SOP 進 green）；每發記 covariance/actual_distance/結果 → 填 ladder proven table | 30 min | [C1/C2](../navigation/2026-06-13-nav-capability-ladder.md)→`demo_ready` 候選；[C3](../navigation/2026-06-13-nav-capability-ladder.md) 視結果 | ☐ |
| N4 | rejection reason 驗證 | Lane 6 §8 | T6-5① | 故意黃帶發 1.0m → `ros2 action send_goal /nav/goto_relative ...` 回讀結構化 reason（`nav_not_ready:covariance=` / `yellow_band_limit:0.5m` 等） | 10 min | [claim wording S6](../navigation/2026-06-13-nav-618-claim-wording.md) 可講 | ☐ |
| N5 | demo route + patrol v0（stretch） | Lane 6 §8 | N1 | `ros2 action send_goal /nav/run_route go2_interfaces/action/RunRoute "{route_id: '<錄的>'}"` 單圈（操作員監督 + e-stop 待命）+ Studio 三層同框錄證據 | 30 min | [C9](../navigation/2026-06-13-nav-capability-ladder.md) `PROTOTYPE` 有展示物；[claim wording S7](../navigation/2026-06-13-nav-618-claim-wording.md) 解鎖 | ☐ |
| N6 | stop-resume operator-confirm（stretch） | Lane 6 §8 | N1 | route/goto 中置障 → danger 停 → Studio 按「繼續」→ 續走（**禁 auto-resume**） | 15 min | [C5](../navigation/2026-06-13-nav-capability-ladder.md) operator-confirm 驗 | ☐ |
| N7 | orphan 根治驗證 | Lane 6 §8 | T6-6 軟體 | goto 進行中 Ctrl-C → server log 有 cancel → 立刻可接下一筆 | 10 min | [C8](../navigation/2026-06-13-nav-capability-ladder.md) client 側升級 | ☐ |
| N8 | profile 矩陣重跑 | Lane 6 §8 | — | indoor_tight：danger 停 / clear 放行 / 無誤擋各一輪（`lidar_front_sector.py` 佐證） | 15 min | [C4/C6](../navigation/2026-06-13-nav-capability-ladder.md) 重驗 | ☐ |
| 收尾 | 還原 | Lane 6 §8 | — | nav stack 停 → `pawai demo start` + `pawai smoke full` 確認 brain lane 無恙 | 15 min | — | ☐ |

**合計 ~2.5-3h**（N5/N6 是 stretch，時間不夠先砍——[Lane 6 §8](../archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。結果回填 [ladder proven table](../navigation/2026-06-13-nav-capability-ladder.md) + [claim wording §2/§6](../navigation/2026-06-13-nav-618-claim-wording.md)；任一項 FAIL 不連坐（[Lane 6 §10](../archive/superpowers-legacy/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。

---

## D. Vision 矩陣日（B-3，~半天到全天，與發表準備搶時間故為可選）

> [Lane 4 §8](../archive/superpowers-legacy/plans/2026-06-13-lane4-vision-benchmark-model-ab-plan.md)。**建議與 B-9 至多選一個提前**（[master §5](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md)）。細部步驟/門檻以 [系統 Phase 3 plan](../archive/superpowers-legacy/plans/2026-06-11-phase3-vision-evidence-model-benchmark.md) 為權威。**runtime 6/18 前不換模型/參數**（B-4 預設不換）。

### D-abort：vision 矩陣日中止/還原 gate

- **RAM 違反先量再跑**：T4 RAM 先量（tegrastats），餘 <0.8GB 即棄該配置（不硬跑）。
- **TRT 預燒禁同跑 demo stack**（W6 前夜，否則互搶）。
- **當日結束必須還原 demo 現役配置**（`OBJECT_MODEL`/`OBJECT_INPUT_SIZE` env 切回 n@640、conf 0.35）+ 跑 `pawai smoke full` 綠；TRT cache 分目錄保證現役 engine 不被覆蓋。

| # | 項 | lane 來源 | 前置 | 指令級步驟 | 需 Go2 | 預估 | 結果 |
|---|---|---|---|---|:---:|---|---|
| D-0 | W1 末端 rsync 模型 | Lane 4 §8 | W1 spike 完 | rsync `yolo26s_640 / yolo26n_960 / yolo26s_960` ONNX → `/home/jetson/models/`（audited deploy，純檔案 additive） | Jetson（純檔案） | 5 min | ☐ |
| D-1 | W6 前夜 TRT 預燒 | Lane 4 §8 | D-0 | TRT engine 預燒（**不開 demo stack**）；現役 engine 分目錄不覆蓋 | Jetson | 30-75 min | ☐ |
| D-2 | 矩陣 T0 power mode 鎖定 | Lane 4 §8 | D-1 | `sudo bash benchmarks/scripts/prepare_env.sh`（nvpmodel + jetson_clocks） | Jetson | 10 min | ☐ |
| D-3 | 矩陣 T1-T5（A-E 配置） | Lane 4 §8 | D-2 | `pawai object matrix`（或 `scripts/obj_matrix_cap.py`）跑 cup recall@1.0/1.5/2.0m + Hz + RAM tegrastats + 溫度；**conf 改動必 kill 重啟**；四門檻（cup@1.5m ≥80% / ≥3Hz / RAM 餘 ≥0.8GB / 7 類 sanity） | **Go2（D435 機上視角）** + 場地 + 三光照 | 核心 ~3h | ☐ |
| D-4 | 矩陣 T6 色彩 54 格（必備 36） | Lane 4 §8 | D-3 | 9 件色彩物件 bag 錄製（Lab-LUT vs HSV12） | Go2 + 9 色彩物件 | ~1h | ☐ |
| D-5 | T7 收尾 + 還原 | Lane 4 §8 | D-4 | 還原現役配置（env 切回）+ `pawai smoke full` 綠 + TRT 分目錄斷言 | Jetson | 15 min | ☐ |

**合計**：核心 4.5-5h；含 T6 選配 ≈6h（排全天或砍 T6 選配排半天——[Lane 4 §8 三選一](../archive/superpowers-legacy/plans/2026-06-13-lane4-vision-benchmark-model-ab-plan.md)）。數據回填 research docs + scoreboard（有上機數據才更新 recall@distance）。

---

## E. 6/17 回穩日（硬 checkpoint，非 HITL motion）

> [master §5 回穩日鐵則](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md)：不開新刀。

| 項 | 內容 | 工具 | 結果 |
|---|---|---|---|
| E-1 | 全 flag 設「發表日狀態」寫入 checklist（shadow on / ism stages 視驗證 / auth 視 B-6 / nav profile） | `ros2 param set` + checklist | ☐ |
| E-2 | `pawai smoke full` 全綠（回穩主工具） | Lane 3 T3-4 | ☐ |
| E-3 | demo 全流程 smoke + 彩排一輪 | demo lane | ☐ |
| E-4 | tag `pre-618-checkpoint` | git | ☐ |
| E-5 | 未過驗證的刀 flag-off 或 revert（shadow 照常收數據） | runtime param / revert | ☐ |

**鐵則**：6/17 18:00 起 main 凍結至發表結束；任何 stage 在 6/17 尚未通過 HITL → 該 flag 維持 False 進發表，不硬上。

---

## F. 依賴與排程備忘

- **時段稀缺**：#1/#2 固定；**B-3 與 B-9 至多選一個提前 6/15-16**，另一個 post-6/18（[master §5](../archive/superpowers-legacy/plans/2026-06-13-aggressive-pre618-master-plan.md)）。**B-9 對 6/18 直接價值較高**（poses 不重錄則 route/goto_named 全空轉、nav 段只能影片 fallback）。
- **跨 lane 依賴**：Lane 3 T3-3（smoke nav --static）是 B-9 開場儀式；Lane 5 T5S-3（token wiring）是 H2-3 auth 彩排前置；Lane 1 各 stage 嚴格串行（前一 stage HITL 未過不開下一個 flag，但實作可先行）。
- **結果回填路徑**：nav 項 → [ladder](../navigation/2026-06-13-nav-capability-ladder.md) + [claim wording](../navigation/2026-06-13-nav-618-claim-wording.md)；brain stage → Lane 1 §11 done criteria；vision → research docs + scoreboard；security → Lane 5 §11（B-5/B-6 決策記錄）。
- **發表日 nav 形態 = B-10**（依 B-9 結果，6/17 定，[claim wording §5](../navigation/2026-06-13-nav-618-claim-wording.md)）。
