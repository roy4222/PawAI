# S1（nav 段）三層 Fallback 決策 + Claim Wording 鎖定

> **日期**：2026-06-13　**狀態**：DOC（決策草案；**S1 台詞最終版待 Roy 簽 D-1**，本檔用 LOCKED 佔位符）
> **task**：plan6 NS-6（[`docs/superpowers/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md`](../superpowers/plans/2026-06-13-plan6-navigation-safety-s1-fallback.md) §6 NS-6）
> **權威措辭來源**：[`2026-06-13-nav-618-claim-wording.md`](2026-06-13-nav-618-claim-wording.md)（S1-S8 可講 / F1-F10 禁講）——本檔每一句宣稱都綁回該檔的編號。
> **相關 SOP**：[診斷集 NS-D2](2026-06-13-no-motion-diagnostics-sop.md)、[initialpose 校正 NS-5](2026-06-13-initialpose-yaw-calibration-sop.md)。
> **這份是什麼**：6/18 發表「s1_nav 這一幕」要**演什麼、講什麼、在什麼條件下退到哪一層**的決策。三層 fallback + 每層可講句綁 S1-S8、禁句綁 F1-F10。

---

## 0. 硬前提（先講清楚，避免 overclaim）

1. **`goto_relative` = `NOT_DEMO_READY`，且不是 S1 live 主線。** 根因：R1（goto「前方」吃 AMCL map-frame yaw，yaw 錯就走歪）、R2（不 enforce max_speed → 0.5m goal 超衝到 1.04m）、T0（URDF 把 `map→odom`/`odom→base_link` 當 fixed joint 發 `/tf_static`，與 AMCL/driver 雙 authority 衝突）。**任何 S1 layer 都不依賴 `goto_relative`。**
2. **`DriveOnHeading` / full nav motion = Roy-returns HITL 選項，不是 6/18 live 主線。** 只有在 plan6 §8 全前置過（T0 修好 + D1-D5 全綠 + θ_error<5° + e-stop + Roy 明確授權 + NS-H3 n=3 全達）才升級到 fallback① live；否則 S1 走 fallback② 或 ③。
3. **S1 主線預設 = fallback②（遙控 + Foxglove LiDAR 證據）**；fallback③（純影片）永遠保底。
4. **不可宣稱**（綁 [§4 F1-F10](2026-06-13-nav-618-claim-wording.md)）：自主導航 / 自由巡邏（F1）、動態繞障（F2）、D435+LiDAR 已融合（F3）、auto-resume / 自動續走（F4/F5）、「聽懂過來就走到 Roy 身邊」（F6）、未 n=3 重驗的「可靠導航」（F7）、1.0m+ 連續乾淨導航（F8）、即時恢復（F10）。**「靜態檢查通過 = 可安全移動」也不可講**（靜態閘 yaw-blind，R5）。

---

## 1. 三層 Fallback 決策表

> 上場條件依 plan1 profiling（nav stack 能否與 brain 共存/分時）+ NS-H1→H3 HITL 結果；6/17 回穩日由 Roy 定 B-10。三層任一層都能交付 nav 段——**不存在「nav 整段開天窗」**。

| 層 | 演什麼 | 上場條件 | 可講句（綁 S 編號） |
|---|---|---|---|
| **① live 短距（DriveOnHeading）** | 現場 live 跑短距 0.3-0.5m（**DriveOnHeading body-frame，不用 goto_relative**） | **全部**：T0 修好 + D1-D5 全綠 + θ_error<5° + e-stop 就位 + Roy 授權 + NS-H3 n=3 全達零撞零超衝 + plan1 profiling 允許 nav stack 共存/分時 | [S1](2026-06-13-nav-618-claim-wording.md)（標「單點」；**n=3 過才可加「可靠」**）、S2、S3 |
| **② 遙控 + Foxglove LiDAR 證據**（**預設主線**） | 遙控 / Studio 輔助移動；Studio map + `/scan_rplidar` 點雲 + reactive zone 狀態作「邊緣端即時感知」證據 | live 不穩 / 場地不允許 / 任一 ① 前提未過 | [S2](2026-06-13-nav-618-claim-wording.md)（safe-stop，配 §3 標準說法）、S4（窄場安全錐 ±18°）、S6（拒絕有理由，T6-5 merged 後）+「nav 在 Studio/Foxglove 顯示即時感知環境（非寫死）」 |
| **③ 純影片**（保底） | S1（nav 鏡）已錄影片，旁白用保守版 | live + 遙控都不上 | 影片旁白用 [S1-S5](2026-06-13-nav-618-claim-wording.md) 的**保守版**，明標「錄影」 |

**鐵則**：① demo snapshot 影片是發表保底，任何 lane 不得使其失效；② covariance 門檻值零變動（0.30/0.50/0.20 硬鎖）。

---

## 2. S1 台詞 LOCKED 佔位符（Roy 未簽 D-1，**禁硬寫最終句**）

> ⚠ **本節全部是佔位符**。最終 15 句 canned 台詞**待 Roy 簽核**（D-1），簽核前**不得**把任何一句當定稿寫進 demo 腳本 / executive.yaml / conductor。每個佔位符標明「綁哪個 S 編號 + 限制詞」，Roy 簽核時照 [§2 可講句表](2026-06-13-nav-618-claim-wording.md) 的限制詞填。

| 佔位 ID | 用途 | 綁定 | 必含限制詞（不可省） | 句子 |
|---|---|---|---|---|
| `<S1_OPENING_LOCKED>` | 開場一句話定位 | [§1 一句話定位](2026-06-13-nav-618-claim-wording.md) | 「已知地圖 / 操作員下令 / 短距 / 遇障安全停」+「能力階梯誠實管理」 | **【LOCKED — 待 Roy D-1】** |
| `<S1_MOVE_LOCKED>` | 短距移動旁白 | S1（C1/C2） | 「單點」；**未過 N3 不得加「可靠」** | **【LOCKED — 待 Roy D-1】** |
| `<S1_SAFESTOP_LOCKED>` | safe-stop 說明 | S2（C4）+ [§3 標準說法](2026-06-13-nav-618-claim-wording.md) | 「偵測到障礙停下等待，不會繞行」；**明講 safe-stop 不是繞障** | **【LOCKED — 待 Roy D-1】** |
| `<S1_CONFIRM_LOCKED>` | 停後續走 | S3（C5） | 「由操作員確認再續走」；**禁講 auto-resume** | **【LOCKED — 待 Roy D-1】** |
| `<S1_NARROW_LOCKED>` | 窄場安全錐 | S4（C6） | 「±18° 窄錐綁低速 ≤0.2 m/s」 | **【LOCKED — 待 Roy D-1】** |
| `<S1_REJECT_LOCKED>` | 拒絕有理由 | S6 | 「定位不夠準 / 已有任務 / 超出黃帶限距」；**T6-5 merged 後才講** | **【LOCKED — 待 Roy D-1】** |
| `<S1_FUSION_QA_LOCKED>` | 被問融合/找人 | S8 + F6 | 「研究路線有 spec、屬 research，目前感知與移動還沒接起來」 | **【LOCKED — 待 Roy D-1】** |

> **佔位符規則**：① 簽核前 demo 腳本引用這些 ID，不引用具體句；② 簽核後由 conductor/台詞 lane（plan2/plan3）落地，**不由本 nav-static lane 寫死**；③ 任一句若加了限制詞以外的宣稱（如「自動繞開」「走到 Roy 身邊」）= overclaim，駁回。

---

## 3. safe-stop ≠ 繞障（最易被戳；標準說法綁 §3）

對外固定用 [`nav-618-claim-wording.md` §3 標準說法](2026-06-13-nav-618-claim-wording.md)：

> safe-stop = 偵測到正前方障礙在安全距離**停下等待**，操作員確認後再下達 / 遙控輔助；**它不會自己轉向繞過障礙**——reactive_stop 設計上只停不轉（`angular.z=0`），這是刻意的安全選擇（硬轉曾導致四足失衡）。

- **絕不**把 safe-stop 包裝成「智能避障 / 自動繞開」（= [F2](2026-06-13-nav-618-claim-wording.md)）。
- 被問「會不會自己繞過去」→ 上述標準說法，落在能講側（S2），不碰 F2。

---

## 4. 禁句速查（綁 F1-F10；任一講出 = 誠信破口）

| 禁句 | 綁定 | 為什麼 |
|---|---|---|
| 自由巡邏 / 自主巡檢 / 自主導航 | [F1](2026-06-13-nav-618-claim-wording.md) | 只有固定預錄 route，N5 未跑前連單圈都沒有 |
| 動態繞障 / 繞行 / 自動繞開 | F2 | reactive_stop 只停不轉；硬轉摔狗 |
| D435 已融合進 costmap | F3 | 現在只有 `depth_clear` fail-closed gate，D435 未進 Nav2 costmap（fusion = research-only spec） |
| 自動續走 / auto-resume / 「障礙移開會自己繼續」 | F4 | auto-resume 會 lunge 貼牆 0.21m，tight space 禁用 |
| 「停了不會再走」 | F5 | 現行為**會** auto-resume（只是不安全被禁），反向不實 |
| 「聽懂過來就走到 Roy 身邊」 | F6 | 感知與 nav goal 零連接、approach 需多層新開發 |
| 未 n=3 重驗的「可靠導航」 | F7 | C1/C2 仍 low-sample；單次 ≠ 可靠 |
| 1.0m+ 乾淨連續導航 | F8 | AMCL 黃帶卡死、從未成功 |
| 三鏡頭/三陣攝影機參與導航 | F9 | 只有 2D RPLIDAR 進迴路 |
| 即時恢復（orphan） | F10 | 是 ~10s 自癒、非即時 |
| 「靜態檢查通過 = 可安全移動」 | （R5 yaw-blind） | 靜態閘只看 position covariance，不查 yaw（c[35]）；過了不代表朝向對 |
| 「goto 0.3m 就走 0.3m」 | （R2 超衝） | goto 不 enforce max_speed，0.5m goal 實測超衝到 1.04m |

---

## 5. Done / 簽核狀態

- **本檔交付 = 三層 fallback 決策表 + 每句綁 S1-S8/F1-F10 + LOCKED 台詞佔位符**（plan6 FLOOR 第 5 項）。
- **未閉合**：S1 台詞最終 15 句待 Roy 簽 D-1（[`nav-618-claim-wording.md` §6 OPEN A-1](2026-06-13-nav-618-claim-wording.md)）；B-10 發表日用哪層待 6/17 回穩日定。
- **S1 主線預設 = fallback②**，影片③ 保底就緒；nav motion 維持 `NOT_DEMO_READY`。
- 本檔純文件，刪檔即回退，無 runtime / param / 門檻值 / URDF 變動。
