# Nav 6/18 Claim Wording（對外措辭鎖定）

> **日期**：2026-06-13　**狀態**：DOC — Lane 6 T6-10（純文件；**Roy 過目鎖定**前為草案）
> **上游**：[Lane 6 plan §13 presentation impact](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)、[capability ladder](2026-06-13-nav-capability-ladder.md)
> **這份是什麼**：6/18 發表 nav 段的**台詞真相層**——每一句可講的話綁一個 [ladder](2026-06-13-nav-capability-ladder.md) 能力 + current label + 證據；不可講清單；fallback 三層；safe-stop≠繞障的標準說法。
> **權威關係**：對外宣稱以本檔 + [demo snapshot forbidden claims](../mission/2026-06-18-demo-north-star.md) 為準；台詞與 [convergence audit §B nav 行](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) 逐條對過、無放水。**未過 HITL 的能力一律取保守措辭**（[ladder §5](2026-06-13-nav-capability-ladder.md)：對外取 ladder 與 6/4 snapshot 較保守者）。

---

## 1. 一句話定位（開場用，最安全）

> **「PawAI 的移動能力是『在已知地圖上、由操作員下令、短距自主走、遇障安全停』——我們用能力階梯誠實管理每一項宣稱，不把單次成功講成可靠、不把停障講成繞障。」**

這句話本身不宣稱任何未驗證能力，且把「能力階梯 + 誠實」當作敘事主軸（呼應 [aggressive master §1 誠實的完成定義](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)：nav 是高風險項，必須用 capability ladder 管理，不承諾一次變成完整自主巡邏）。

---

## 2. 可講句（每句綁 ladder 能力 + label + 證據 + 前提）

> 規則：① 帶 `[需 N 過]` 的句子**必須對應 HITL 項 PASS 並回填 ladder 才能講**；② 每句的限制詞（單點/窄版/操作員監督/短距）**不可省略**。

| # | 可講句 | ladder 能力 | current label | 證據 | 講的前提 |
|---|---|---|---|---|---|
| S1 | 「室內已知地圖、操作員下令的短距自主移動（0.3-0.5m）」 | [C1/C2](2026-06-13-nav-capability-ladder.md) | C1 `HARDWARE_PROVEN_LOW_SAMPLE` / C2 `NEEDS_RETEST` | [trackB §1](research/2026-06-08-trackB-hitl-results.md) | 標「單點」；**n=3 重驗（N3）後才可加「可靠」二字** |
| S2 | 「正前方障礙物會安全停下、不碰撞——偵測到障礙會停下等待，不會繞行」 | [C4](2026-06-13-nav-capability-ladder.md) | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §1 NAV-2 / 6/9 §1.5](research/2026-06-08-trackB-hitl-results.md) | **明講 safe-stop 不是繞障**（§3 標準說法）；不講側向覆蓋 |
| S3 | 「停下後由操作員確認再續走」 | [C5](2026-06-13-nav-capability-ladder.md) | `NEEDS_FIX_OR_OPERATOR_CONFIRM` | [6/9 §1.6](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | operator-confirm；**禁講 auto-resume**（§4） |
| S4 | 「居家窄場用收窄安全錐（±18°）避免家具誤擋」 | [C6](2026-06-13-nav-capability-ladder.md) | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §4 / 6/9 §1.3](research/2026-06-08-trackB-hitl-results.md) | 標「窄錐綁低速 ≤0.2 m/s」 |
| S5 | 「client/SSH 掛掉約 10 秒內自動恢復、不需重啟」 | [C8](2026-06-13-nav-capability-ladder.md) | `HARDWARE_PROVEN_WITH_LIMIT` | [trackB §5-6 / 6/9 §orphan](research/2026-06-08-trackB-hitl-results.md) | **禁講「即時恢復」**（[6/9 §36](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)） |
| S6 | 「每次導航拒絕都有可讀理由（如定位不夠準、已有任務在跑、超出黃帶限距）」 | rejection reason | T6-5 後 | [Lane 6 T6-5](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) | **T6-5 merged 後才講**；message-only、不改判定邏輯 |
| S7 | 「固定路線單圈巡邏 prototype（操作員監督）」 | [C9](2026-06-13-nav-capability-ladder.md) | `PROTOTYPE` | [6/9 Phase 1.5](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md) | `[需 N5 過]` **僅在 run_route 單圈跑通後**；與「自由巡邏」嚴格區分 |
| S8 | 「D435+LiDAR 融合 / 自主找人：研究路線已有 spec，屬 research prototype」 | [C12](2026-06-13-nav-capability-ladder.md) | `DO_NOT_CLAIM`（spec only） | [fusion spec](research/2026-06-13-spec-d435-lidar-fusion.md) / [approach spec](research/2026-06-13-spec-approach-person.md) | 只講「有 spec、是研究」；**不可講已具備** |

> S1 的「可靠」與 S7 整句都是**條件句**：N3 / N5 未過則退保守版（S1 去掉「可靠」、S7 整句不講走影片 fallback）。

---

## 3. safe-stop ≠ 繞障（標準說法，最容易被戳的點）

這是 nav 段**最關鍵的誠實邊界**——觀眾/教授會問「會不會自己繞過去」。標準回答固定為：

> **「我們做的是 safe-stop：偵測到正前方障礙會在安全距離停下等待，由操作員確認後再重新下達或遙控輔助。它不會自己轉向繞過障礙——繞障需要轉向控制，而我們的反應式停障在設計上只停不轉（`angular.z=0`），這是刻意的安全選擇（硬轉曾導致四足失衡）。」**

- **技術依據**：reactive_stop `angular.z=0` 只停不轉（[ladder C4 限制](2026-06-13-nav-capability-ladder.md)）；硬轉摔狗（5/2，[trackB §7](research/2026-06-08-trackB-hitl-results.md)）。
- **為什麼這樣講站得住**：[trackB §7](research/2026-06-08-trackB-hitl-results.md) 把「遇障在安全距離前安全停下、不撞」列為能講項，把「動態繞障」列為不能講項——本說法精確落在能講側。
- **絕不**把 safe-stop 包裝成「智能避障」「自動繞開」——那是 [ladder C11 `DO_NOT_CLAIM`](2026-06-13-nav-capability-ladder.md)。

---

## 4. 不可講清單（forbidden claims，延續 demo snapshot + 更新）

> 任一條被講出 = 誠信破口；與 [north-star §7](../mission/2026-06-18-demo-north-star.md) + [convergence audit §B nav 行](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md) 一致。

| # | 不可講 | 為什麼 | 對應 ladder |
|---|---|---|---|
| F1 | 自由巡邏 / 自主巡檢 | 只有固定預錄 route（且 N5 未跑前連單圈都沒有） | [C9/C11](2026-06-13-nav-capability-ladder.md) |
| F2 | 動態繞障 / 繞行 / 自動繞開 | reactive_stop 只停不轉；硬轉摔狗 | [C11](2026-06-13-nav-capability-ladder.md) |
| F3 | D435 已融合進 costmap | 現在只有 `depth_clear` fail-closed gate，D435 未進 Nav2 costmap | [C12](2026-06-13-nav-capability-ladder.md) |
| F4 | 自動續走 / auto-resume / 「障礙移開會自己繼續」 | auto-resume 會 lunge 貼牆 0.21m，tight space 禁用 | [C5](2026-06-13-nav-capability-ladder.md) |
| F5 | 「停了不會再走」 | 實際現行為**會** auto-resume（只是不安全被禁），講「不會再走」是反向不實 | [C5](2026-06-13-nav-capability-ladder.md) |
| F6 | 「聽懂過來就走到 Roy 身邊」 | 感知與 nav goal 零連接、approach 需 4 層新開發 | [C12 / approach spec](research/2026-06-13-spec-approach-person.md) |
| F7 | 未經 n=3 重驗前的「可靠導航」 | C1/C2 仍 low-sample；單次 ≠ 可靠 | [C1/C2](2026-06-13-nav-capability-ladder.md) |
| F8 | 1.0m+ 乾淨連續導航 | AMCL 黃帶卡死、從未成功；「乾淨 0.5m+ 連續導航」trackB §7 明列不能講 | [C3](2026-06-13-nav-capability-ladder.md) |
| F9 | 三鏡頭/三陣攝影機參與導航 | 只有 2D RPLIDAR 進迴路 | [trackB §2](research/2026-06-08-trackB-hitl-results.md) |
| F10 | 即時恢復（orphan） | 是 ~10s 自癒、非即時 | [C8](2026-06-13-nav-capability-ladder.md) |

---

## 5. Fallback 三層（發表日 nav 段用哪層 = B-10 決策，依 B-9 結果）

> 與 [Lane 6 §13 fallback 三層](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) + [Lane 6 §10 rollback](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md) 一致。nav stack 與 brain demo stack **8GB 互斥**——nav 段是獨立鏡頭（[6/9 §499](../superpowers/plans/2026-06-09-nav-vision-hitl-execution.md)）。

| 層 | 內容 | 上場條件 | 可講句 |
|---|---|---|---|
| **① live 短距 / 短 route** | 現場 live 跑 goto 0.3-0.5m，或 run_route 單圈 | **B-9 場測 N3（短距）/ N5（route）驗過** | S1（+「可靠」若 N3 過）、S2、S3、S7（若 N5 過） |
| **② 遙控輔助 + Studio 證據** | 遙控/Studio 輔助定位，Studio map / LiDAR 點雲 / 狀態作為「邊緣端即時感知」操作證據 | live 不穩或場地不允許 | S2、S4、S6 + 「nav 在 Studio/Foxglove 顯示即時感知環境（非寫死）」 |
| **③ 純影片** | S1（nav 鏡）已錄影片（[demo-2026-06-snapshot tag](../mission/2026-06-18-demo-north-star.md)） | live + 遙控都不上 | 影片旁白用 S1-S5 的保守版；明標「錄影」 |

**鐵則**：① demo snapshot 影片是發表保底，任何 lane 不得使其失效（[master 附錄 A](../superpowers/plans/2026-06-13-aggressive-pre618-master-plan.md)）；② 三層任一層都能交付 nav 段——不存在「nav 整段開天窗」的情況（[Lane 6 §10](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)）。

---

## 6. OPEN 書記（鎖定前待補）

| 書記 | 內容 | 閉合條件 |
|---|---|---|
| **A-1（S1 簿記）** | 6/9 鎖過一版台詞，S1 錄成的方式待補記；poses 隨後遺失 → 本版需重鎖（[ladder §4](2026-06-13-nav-capability-ladder.md)、[Lane 6 §3 問題 7](../superpowers/plans/2026-06-13-lane6-navigation-obstacle-avoidance-v2-plan.md)） | Roy 過目本檔 + 確認 S1 影片內容對得上 S1-S5 措辭 |
| **B-9 結果回填** | N3/N5 PASS/FAIL → S1「可靠」、S7 整句的最終可講性 | B-9 場測後回填 ladder + 本表 §2 |
| **B-10 fallback 層** | 發表日用 §5 哪一層 | 6/17 回穩日依 B-9 結果定 |

---

## 7. 與簡報對齊的一頁（給 Roy 過目）

- **開場**：§1 一句話定位（能力階梯 + 誠實當主軸）。
- **能講**：S1（短距，標單點/視 N3 加可靠）→ S2（safe-stop，配 §3 標準說法）→ S3（operator-confirm）→ S4（窄場安全錐）→ S6（拒絕有理由，視 T6-5）→ S7（單圈 patrol prototype，視 N5）→ S8（fusion/approach 是研究 spec）。
- **絕口不提**：§4 F1-F10 全部。
- **被追問繞障**：固定用 §3 標準說法。
- **被追問「會不會自己找人/過來」**：S8 + F6——「研究路線有 spec，目前感知與移動還沒接起來，不在這次展示範圍」。
- **發表日形態**：§5 三層擇一（B-10 定），影片保底。
