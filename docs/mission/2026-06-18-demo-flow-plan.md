# 2026-06-18 實機 Demo 流程計畫（守望 POC 雙案）

> **一句話定位**：這份文件把「PawAI 6/18 實機 demo」收斂成一段**安全、可解釋、零 overclaim 的非接觸式室內守望互動小閉環**——主軸壓在有實機背書的互動 70% 主線（認人→看姿態→看物品→手勢互動→安全拒絕→Studio evidence），nav 移動段預設純顯示、不自走。
>
> **文件用途**：這是給 Roy 拍 6/18 demo 的**可執行流程腳本 + 誠實校正稿**。它做三件事：(1) 對 Roy 的 demo draft 逐段下可行性判決；(2) 把 draft 裡的 overclaim 句子逐條改成誠實替代句；(3) 給兩個可拍版本（初級保守 = 現在就能拍；進階誠實 = 需前置鎖 pass）的完整分鏡表、禁說/建議句清單、現場 fail fallback。
>
> **真相來源交叉引用**：本文所有判決與用詞紀律以 [`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md)（North Star v2，§5 禁說 / §7 nav 鐵律 / §9 scoreboard-first / §11 報告原則）為唯一權威；**能力分級的最終事實依據是** [`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（最新 trusted snapshot，SHA `78fbf36`，`run_trusted=true`，readiness=`not_ready`）；**每能力的 Current Claim / Claim Level / Pass-Fail / Non-Claims 一律以 [`2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md) 為 canonical 真相源**，本文不重複整份。`2026-06-03-first-trusted-face/` 已被 6/04 取代，僅作歷史。

---

## 1. 文件定位與用途（見上方引文）

本文涵蓋三個審查角色（Linus 技術審查 / 教授 QA 模擬 / Demo 風險稽核）對兩個 tier 提案的 must-fix，已全部收斂進下方的判決、校正表與分鏡。**baseline 情境（依 6/04 HITL trusted snapshot）**：互動主線有 **3 項窄版實測 pass**——`face.recognition`（n=9, recall=1.0, false-accept=0.0，但僅單一註冊者 Roy／idle=空景／真實陌生人未測）、`object.cup`（近距 ~1m cup-only，n=7, recall=1.0）、`voice.command`（n=24, success_rate=0.875，固定指令集意圖分類）；**2 項 fail**——`gesture.wave`（recall=0.0, wave_pub=False）、`voice.stop`（success_rate=0.667, FN=2，**不可當安全停車**）；pose / nav.* / brain.* / studio.evidence 皆 `insufficient_data`，readiness=`not_ready`（因 voice.stop/gesture.wave fail + nav/brain 未量，**非因 face**）。窄版 pass 一律維持會議 scope 保守邊界（不宣稱守護 / 拒絕陌生人 / 通用物體 / 安全停車）。每能力分級細節見 [`2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md)，本章不重複。若 6/18 前再跑出新 pass，再依 §7 升級規則放寬旁白（見第 7 章 checklist）。

---

## 2. TL;DR 可行性判決

把 Roy draft 的四段拆開逐段判決。**圖例**：✅ 可行（照拍） / ⚠️ 需改 framing（內容可拍但旁白/字幕要改） / ❌ 不可行（baseline 情境下整段砍或退純顯示）。

| Roy draft 段 | 判決 | 一句話理由（指向真相） |
|---|---|---|
| **第一段 移動到現場**（slam+nav2 自走 + 動態繞開障礙 + PawAI 從門口走向 Roy） | ❌ **不可行 → 退純顯示** | nav.safe_stop / no_auto_resume 全 insufficient_data，F7（goal accept 後 `/cmd_vel_nav` 無 publisher）至今未在 fresh stack 定位 → 違反 North Star §7 nav 鐵律「未 pass 不做任何真實自走」；draft 的「自主導航 / 動態繞開 / 走向 Roy」三個動作全在 §5 禁說清單。 |
| **第二段 視覺辨識**（認人問候 / 姿態 / 掉落物 / 手勢 / 安全拒絕） | ⚠️ **可行（需改 framing）** | 6/04 baseline：`face.recognition` / `object.cup` 為**窄版 pass**（可講「能認出已註冊 Roy」「~1m 近距能辨識杯子這一類」，但**不宣稱**拒絕陌生人 / 通用物體）；`gesture.wave` 為 **fail**（只顯示 / 退靜態手勢或 palm）；pose `insufficient_data`。每句宣稱同框 6/04 證據 chip，措辭一律綁窄版邊界。 |
| **安全拒絕**（翻跟斗被擋 + Studio blocked 畫面） | ✅ **可行（最硬主秀）** | 100% rule-based、不經 LLM、雙層 fail-closed、91 unit test 全綠、blocked badge 對得上 `chat-panel.tsx:543` → 是全 demo 證據力最強、overclaim 風險最低的一段（North Star §11 每句宣稱有 trace 背書）。 |
| **收尾**（字幕「5/27 單人巡檢小閉環 / 6/18 實機機構巡檢 demo」 + Studio evidence） | ⚠️ **需改 framing** | Studio evidence 全鏈可拍（langgraph 12-stage trace + Live View），但「巡檢」是 §5/§7 隱含自走的禁用框架，且 scoreboard pass/fail LED 前端無 UI consumer → 收尾改「守望互動小閉環」、用 repo JSON 證據而非承諾螢幕燈號。 |

**一句話總結**：第一段砍真實 motion 退純感知顯示、第二段照拍但全程「只顯示不宣稱」、安全拒絕當主秀、收尾改守望用詞。

---

## 3. 誠實校正表（honesty-diff）

對照 Roy draft 逐句抓 overclaim，給誠實替代句。**禁說依據全部指向 North Star §5/§7 + dossier cannot_claim。**

| # | Roy draft 原句 / 段落 | overclaim 性質（違反哪條） | 誠實替代句 |
|---|---|---|---|
| H1 | 字幕主軸「從遙控機器狗，到**具身 AI 巡檢助理**」 | 「巡檢助理」隱含自走巡邏（§5 禁「巡邏整個機構」） | 「從遙控機器狗，到**會誠實量測自己能力的守望互動機器狗**」 |
| H2 | 第一段「**slam+nav2 做導航避障，最好秀動態繞開障礙物**」 | §5 禁「動態繞障已完成」；架構本質 stop-only 不繞障，dynamic_avoidance 標 future | 「PawAI 在邊緣端用光達 + 深度相機**即時感知環境**並把感知送回 Studio——這是『系統在看』，不是『會自己繞』」 |
| H3 | 第一段「**PawAI 從門口走向 Roy**」 / 字幕「**PawAI 可以移動到現場進行巡檢**」 | §5 禁「自動找人 / 巡邏」；nav.short_move insufficient_data + F7 未定位 | 「（baseline 情境）移動段只做**邊緣感知純顯示**，不做真實自走；旁白：『PawAI 在邊緣端感知環境』」。若且僅若 R5 全綠才允許**操作員手動 override 短距 0.3m、全程旁站可停** |
| H4 | 第一段語音「前方有障礙物 **我往右繞開**」 | 繞障 overclaim（同 H2） | 「前方有人時，安全層會**讓它即時停下**（停下後障礙移開會恢復前進，這正是我們標 no_auto_resume 為 insufficient_data 待重設計的原因）」 |
| H5 | 第二段「**Roy，歡迎回來。我看到你坐下來了。**」（搭配 face/pose） | 「確認身份」是能力語言（會引申門禁級可靠）；pose 為 `insufficient_data`，不可同句宣稱「看到你坐下」 | 動詞從「確認」降為「**辨識**」：「PawAI 辨識靠近的人，認出是已註冊的 Roy 就打招呼——這項 6/04 量到**窄版 pass**（n=9, recall=1.0），所以 chip 標 pass，但僅 Roy 一人 / idle 空景，**不宣稱能拒絕陌生人、也不宣稱不會認錯人**」。pose 部分刪除「我看到你坐下」（pose `insufficient_data`，不入旁白） |
| H6 | 第二段「**我看到地上有水杯，請記得拿起來。**」 | 「地上水杯 / 請記得拿起來」延伸絆倒守護語言；object.cup 是 ~1m 近距 cup-only 窄版 pass，不是通用物體 | 保守版：「**我看到桌上有杯子**」（object.cup 6/04 窄版 pass：~1m 近距、單色杯子受控擺位，n=7）；不穩或距離拉遠時退「我看到桌上有物品」；旁白補「物件辨識**刻意只開杯子這一類、且僅在近距 ~1m 可靠，不是通用物體辨識，2m 未驗**」；**不把 LLM 口播『我看到杯子』當感知證據、不用物體觸發 Go2 移動** |
| H7 | 第二段安全拒絕「**這個動作不安全，我不能執行。**」（draft 已是保守句） | ✅ 本句 OK，但周邊旁白若說「機器人本來想翻被擋」即違反 cannot_claim | 保留台詞；旁白聚焦三層機制「規則層攔截 + LLM 無權生成 + 執行層二次擋」，**不說「機器人不可能真的翻」**（暗示 Go2 本來會翻）；明說「1301 是 demo-only 假動作，Go2 sport mode 本就沒翻跟斗」 |
| H8 | 收尾字幕「5/27 單人**巡檢**小閉環 / 6/18 實機**機構巡檢** demo」 | 「巡檢」= §7 隱含自走 | 「5/27 單人**守望互動**小閉環 / 6/18 機構**守望互動** demo」 |
| H9 | （draft 隱含）開場/收尾把 scoreboard 當主畫面、螢幕秀 pass/fail chip | 前端 0 元件 fetch `/api/scoreboard`，chip 牆 UI 不存在 | 主畫面改秀 **git-tracked baseline-evidence JSON + dev trace GateChip**；旁白「我們的量測證據**全程留痕在 repo**」，**不承諾螢幕有評分燈號** |
| H10 | （draft 隱含）把 readiness/量測機制講成「可信機制無條件成立」 | 6/04 readiness verdict=`not_ready`（正確 fail-closed）；第一個 blocker 實測是 `sha_mismatch`（**非** `schema_validator_unavailable`——後者是 6/03 舊現象，已被 6/04 取代）；snapshot `wsl_dirty`/`jetson_dirty=true` 是未追蹤檔（slide PDF / `.tmp/`）非追蹤碼變更，clean tracked commit = `78fbf36` | 旁白加 caveat：「這是我們**第一次跑出可信量測（非乾淨 release baseline）**，證據全程留痕」 |
| H11 | （draft 全程靠語音觸發，未列風險） | voice.command/voice.stop insufficient_data；mic boundary 未接通；ASR 對「翻跟斗」純字面比對無同音容錯 | demo 前**必須實測 ASR 對 5 組 unsafe keyword + 核心指令的辨識率**；不可把「說停」講成安全機制（真安全靠 reactive_stop + 物理 e-stop） |

> Roy 已自覺的禁說句（「旁邊有電腦 / 自主導航到 Roy 身邊 / 自動避障找到你 / 照顧老人 / 防止跌倒」）本文照單全收，不重複列。

---

## 4. 初級保守方案（現在就能拍，零 overclaim）

**定位**：完全錨在有實機背書的互動 70% 主線，nav 移動段**預設純 Studio/Foxglove 顯示零實機 motion**，被問可靠度一律指 scoreboard。全程旁站可停。

### 4.1 拍前硬前置（dry-run 清單）

- [ ] 跑的是 `scripts/start_full_demo_tmux.sh`（**launch override 才是真相來源**：`pose_backend:=mediapipe gesture_backend:=recognizer enable_fallen:=false`），**不是裸 ros2 launch 讀 `vision_perception.yaml`**（該檔是 `rtmpose`，會 config drift）。
- [ ] `object_perception/config/object_perception.yaml` 仍是 `class_whitelist=[41,999]`（cup-only）。
- [ ] **object_perception 真起且有 consumer**：`ros2 topic echo /event/object_detected` 拍前看得到 event（否則 segment 4 連鏈路都秀不出）。
- [ ] 確認啟的是**真 `studio_gateway`**（非 `mock_server.py`）；`ros2 topic echo /brain/skill_result` 佐證真鏈。
- [ ] 確認走 **langgraph 引擎**（`conversation_graph_node`，非 legacy brain_node），否則 12-stage trace 縮水。
- [ ] **ASR dry-run**：「PawAI 請翻跟斗」+ 核心固定指令在 demo 麥克風能可靠辨識（純字面比對無同音容錯，先測 5 組 unsafe keyword）。
- [ ] **手勢 dry-run**：確認**靜態 palm/舉手**在 1.5–2.5m 觸發；**camera 動態 wave 預期不觸發（6/04 fail），不排進主 take**，需要打招呼互動改走語音 `wave_hello`。
- [ ] **供電**：S0–S5 全模組同跑 + Go2 通電下量電壓/溫度餘量，專人監控，備援電源（供電是全 demo 最大單點失敗）。
- [ ] **強背書段預錄備援**：face / object / safety 都備好預錄影片/截圖，活鏈掛掉直接切預錄。

### 4.2 分鏡表

| 段 | 時間 | 動作 | 旁白（誠實版） | 觸發模組 | Studio evidence | 現場 fail fallback | 拍攝法 |
|---|---|---|---|---|---|---|---|
| **S0 開場** | 0:00–0:10 | 大螢幕開 Studio dev trace + 直接秀 git-tracked `baseline-evidence/` JSON；Go2 待機不動 | 「PawAI 的可靠度不是嘴上說的，是量出來的。這是我們**第一次跑出的可信量測（非乾淨 release baseline）**——有的項目我們誠實標 fail，這正是重點」 | studio_gateway dev trace GateChip / 量測鏈 | `readiness_output.json`(verdict=not_ready) + 3 筆 face record JSONL；**不秀螢幕 pass/fail LED chip（UI 不存在）** | 同上已是 fallback 版（不依賴 scoreboard UI） | 系統畫面螢幕錄，1–2s 定格 |
| **S1 移動（純顯示）** | 0:10–0:25 | Foxglove 蒙太奇：`/scan_rplidar` 點雲 + D435 depth + home map 同畫面；Go2 靜止 | 「PawAI 在邊緣端即時感知環境——光達掃出輪廓、深度相機看到前方距離，全送回 Studio。**我們展示的是『系統在看』，不宣稱它會自己走**」 | sllidar / D435 depth / map_server（**零 motion**） | Foxglove scan/depth/map；NavigationPanel tri-state GateChip（旁白只講「動作放行 gate」） | 純筆電無真影像 → 用既有錄製 Foxglove 截圖蒙太奇 | 系統畫面 1–2s；字幕**禁寫「自主導航」** |
| **S2 認人問候** | 0:25–0:37 | 註冊者走近到 ~1.5–1.7m 正對鏡頭停 1–2s；PawAI 守望語氣問候 | 「PawAI 辨識靠近的人，認出是已註冊的 Roy 就打招呼——這項 6/04 量到**窄版 pass**（n=9, recall=1.0, false-accept=0.0），所以 chip 標 pass，但僅 Roy 一人 / idle 空景，**不宣稱能拒絕陌生人、也不宣稱不會認錯人**」 | face_identity_node / interaction_executive greet_known_person / TTS | `/face_identity/debug_image`(bbox+名字+距離) + ChatPanel + face chip=pass(窄版) + 6/04 JSON | track 抖動/名字閃 → 退「看到有人靠近並打招呼」泛稱，或只秀 debug_image 證鏈路 | 第三人稱 Roy 走近 + debug_image；剪輯選名字穩定片段 |
| **S3 看姿態** | 0:37–0:48 | Roy 站直（不發 event）→ 坐下（sitting，~1s 觸發社交 TTS）；全身入鏡腿可見 | 「PawAI 對人的站 / 坐做**粗略觀察**並輕量社交回應——這項**本輪未量測（insufficient_data）、只在 Studio 顯示、不是醫療判斷、不做任何跌倒判斷**」 | vision_perception pose / interaction_executive `sit_along` / TTS | `/event/pose_detected`(sitting) + pose panel（Studio-only） | 拍前確認 sitting event 有觸發 `sit_along`(skill_contract.py:266 內建)；IE 未接 pose→dispatch 才退純 Studio 顯示 | 第三人稱坐下 + pose panel；**鏡頭帶到 Studio fallen 紅標時旁白絕不提跌倒**（`enable_fallen:=false`） |
| **S4 看物品** | 0:48–0:57 | 桌上/手舉單色杯子到 ~1–2m 中央停穩；問「你看到什麼？」 | 「PawAI 看到桌上的杯子，提醒一句。今天物件辨識**刻意只開杯子這一類——我們不宣稱通用物體辨識**，只示範驗證範圍內的物件」 | object_perception(cup-only) / Brain color gate / TTS(zh) | `/perception/object/debug_image`(中文「杯子」+顏色+conf) + object panel | 顏色亂跳 → 只講「杯子」不講顏色；node 沒真起 → 退秀 object panel | 第三人稱杯子入鏡 + debug_image；杯子離手離背景遠 |
| **S5 手勢互動** | 0:57–1:08 | 退**靜態手勢**（palm/舉手，正對鏡頭手抬胸口以上、1.5–2.5m）或語音 `wave_hello`；一次一個做完放下，給足 3–4s。**camera 動態 wave 預期不觸發，不排進主 take** | 「今天手勢只留**最穩定的靜態示意**——動態揮手這項 6/04 量到 **fail**（recall=0.0, wave_pub 全程未觸發），所以我們**不演 camera 揮手**，改用靜態手勢/語音示意，並在 Studio 誠實標 fail」 | vision_perception(recognizer) 靜態手勢 / 語音 `wave_hello(1016)` / TTS | `/event/gesture_detected`(靜態) + gesture trace chip(wave=fail) | camera 動態 wave 不觸發是**已知 fail，非現場故障** → 改靜態 palm/舉手或語音；都不穩 → 只在 gesture panel 顯示 event + 標 fail | 拍前 dry-run；第三人稱靜態手勢 + gesture trace；**手勢不接 Go2 真實 motion**（5/27 決議）；**區分：camera 動態 `gesture.wave`=fail；語音 `wave_hello` 是另一條路徑** |
| **S6 安全拒絕** | 1:08–1:18 | 語音「PawAI 請翻跟斗」→ TTS「這個動作不安全，我不能執行。」+ Studio 紅色 badge `request_backflip · blocked_by_safety · banned_api:1301`；Go2 不動 | 「我跟它說翻跟斗——危險動作。它用語音拒絕，同時 Studio 紅燈標被擋原因。**危險指令在規則層就被攔，LLM 從頭到尾沒機會生成，執行層再擋一次**。Go2 sport mode 本就沒翻跟斗，1301 是我們造的 demo-only 假動作走 reject 流程」 | brain_node `_on_speech_intent` / SafetyLayer unsafe_request+validate / studio_gateway / TTS | `/brain/skill_result`(blocked_by_safety, banned_api:1301) → 紅 badge；事前 `pytest test_safety_layer.py` 91 綠燈截圖 | ASR 聽錯 → 咬字重講 or 秀預錄 blocked badge + pytest 截圖；確認真 gateway 非 mock | 第三人稱說指令 + Go2 不動 + Studio 紅 badge 同步 |
| **S7 收尾** | 1:18–1:30 | 切 Studio：ChatPanel + BrainStatusPill → `?dev=1` 12-stage trace 色票流 → `/studio/live` 三欄影像牆 | 「每一步——認人、看姿態、看物品、互動、安全拒絕——都能在 Studio 看到證據。**這是我們跟一般 chatbot 的差別：每個判斷可解釋、可追溯。做得到的秀給你看，還沒驗證可靠的，誠實標在 scoreboard 上**」 | studio_gateway / conversation_graph_node(langgraph 12-stage) / Studio frontend | 12-stage 色票流(dev) + Live 三欄 + EventTicker | Jetson 8GB 三欄不穩 → Live 減單欄/關掉，保 ChatPanel + dev trace；trace 面板預先開好第二視窗 | 系統畫面螢幕錄；字幕收「**守望互動小閉環**」不寫「巡檢」 |

---

## 5. 進階誠實方案（需前置鎖 pass）

**定位**：互動主線實機背書 + scoreboard 誠實層為**敘事骨幹**；nav 三段全部前置鎖。每段明標 `requires` 前置鎖，沒 pass 就降級。**最安全形態 = S0–S5 + S6 nav 純顯示 + S7，完全不碰真實 nav motion 也成立完整故事。**

### 5.1 全域前置鎖（requires）

| 鎖 | 內容 | 沒滿足的降級 |
|---|---|---|
| **R0** | demo 當天先在 **WSL** 跑 `build_scoreboard` 產 frozen `baseline_snapshot.json`，sha 對得上 deploy code（readiness sha-gate） | scoreboard 段只口述機制、不秀數字燈號 |
| **R1** | **6/04 已滿足（face 窄版 pass, n=9）**；可選 #81 乾淨重跑（≥2 註冊者 + 多光照 + 真實陌生人樣本）擴張邊界 | 重跑前維持窄版邊界：只講「認出已註冊 Roy」，**不宣稱**拒絕陌生人 / 2m+ / 通用人臉辨識 |
| **R2** | **6/04 已滿足（object.cup 窄版 pass @~1m, n=7）**；可選多距離（1/1.5/2m）重跑擴張邊界 | 重跑前維持窄版邊界：只講「~1m 近距杯子」，**不宣稱** 2m 可靠 / 通用物體 |
| **R3** | gesture.wave 跑出 baseline 且標 pass（含 idle 誤觸 ground-truth）——**6/04 仍 fail（recall=0.0）** | wave 維持 fail：camera 動態 wave 不演、只在 Studio trace 顯示並標 fail，改靜態手勢/語音示意，措辭綁「示意」不綁「可靠」 |
| **R4**（§7 鐵律） | nav.safe_stop / no_auto_resume 標 pass（或人工 override 簽核）；子鎖：(a) **F7 root cause 在 fresh stack 定位**；(b) no_auto_resume 行為衝突（reactive_stop 離 danger auto-resume）已做 BD-8 重設計或明示「現行為 auto-resume」 | **nav 全段降純 Studio 顯示、零真實自走** |
| **R5** | 真實移動：只允許人工 override 單次 `goto_relative 0.3m` + 立即可停 + 操作員旁站手放 e-stop + fresh stack acid test 未復現 F7 + 供電穩（2464） | S6-ALT 砍掉退 S6；1.0m+/繞障/連續多 goal/連跑 30min+ 一律禁 |
| **R6** | blocked badge 跑真 `studio_gateway`；ASR 對 5 組 unsafe keyword 辨識率先實測 | 只能說「邏輯 + 91 test + Studio 即時顯示」，不說「實機端到端驗證過」 |
| **R7**（用詞） | 逐句改「守望/提醒/回報/非接觸」，剔除跌倒警報 + 陌生人警報 | —（無條件遵守） |
| **R8**（pose） | 維持 `enable_fallen:=false` + fallen TTS 雙路靜音 | —（無條件遵守）；鏡頭帶到 Studio fallen 紅標也不說「偵測到跌倒」 |

### 5.2 分鏡表

| 段 | 時間 | requires | 動作 | 旁白（誠實版） | Studio evidence | 沒 pass 的降級 | overclaim 風險 |
|---|---|---|---|---|---|---|---|
| **S0 開場（scoreboard 主角）** | 0:00–0:12 | R0 | 螢幕秀 frozen scoreboard chip（**若無 UI 則秀 JSON/Foxglove**）；停在 6/04 grade（face/object.cup/voice.command=pass 窄版、voice.stop/gesture.wave=fail、其餘 insufficient_data） | 「PawAI 是面向機構公共空間的非接觸守望互動四足機器人 POC。第一件事不是吹功能，是建一條可重現量測鏈：preflight→observer→scoreboard→readiness。**6/04 量到 3 項窄版 pass + 2 項 fail，其餘 insufficient_data 代表還沒量到；readiness 仍 not_ready（因 voice.stop/gesture.wave fail + nav/brain 未量）——拿真正的 fail 當例子，這就是誠實層**」 | 6/04 frozen snapshot grade/reason；**前端無 fetch /api/scoreboard，chip 牆需確認 UI consumer，否則秀 JSON** | R0 無 frozen → 純口述機制 + 秀 `2026-06-04-hitl/` JSON | 低（拿真正的 fail=voice.stop/gesture.wave 當誠實例子） |
| **S1 認人問候** | 0:12–0:24 | R1（6/04 已滿足：face 窄版 pass） | 註冊者走近 ~1.5–1.7m 停 1–2s；守望問候 | 「PawAI 辨識靠近的人，認出已註冊的 Roy 就打招呼。6/04 量到**窄版 pass**（n=9, recall=1.0, false-accept=0.0），所以 chip 標 pass，但僅 Roy 一人 / idle 空景，**不宣稱可靠拒絕陌生人、也不宣稱不會認錯人**」 | `/face_identity/debug_image`(含距離) + face chip=pass(窄版) + 6/04 JSON + BrainStatusPill | 若 #81 乾淨重跑前，仍只講窄版邊界，不擴張到「通用人臉辨識 / 2m+ 可靠」 | 中（每次提 face 同框窄版 caveat） |
| **S2 看姿態** | 0:24–0:33 | R8 | Roy 坐下；輕量社交回應 | 「PawAI 看得出人站/坐/彎，做輕量社交回應。**粗略的站坐彎，不做任何跌倒判斷**」 | pose panel sitting + `/event/pose_detected` + brain trace | pose TTS 路徑（**brain_node `_on_pose`→`sit_along`，非 event_action_bridge**）未 active → 只 Studio 顯示無語音 | 中（鏡頭帶 Studio fallen 紅標旁白不說跌倒） |
| **S3 看物品** | 0:33–0:42 | R2（6/04 已滿足：object.cup 窄版 pass @~1m） | 桌/手單色杯到 **~1m**（近距）；辨識提醒 | 「PawAI 看到桌上的杯子提醒一句。object.cup 6/04 量到**窄版 pass**（~1m 近距 cup-only, n=7, recall=1.0），**刻意只開杯子這一類、且僅近距可靠，不是通用物體辨識，2m 未驗**」 | `/perception/object/debug_image`(中文「杯子」) + object.cup chip=pass(窄版) | 距離拉遠/延遲（p90≈4.9s）尷尬 → 鎖 ~1m、不說「即時」、改「看到桌上有物品」；**不把 LLM 口播當感知證據** | 中（明說「只近距杯子」+ 顏色只在穩定時講） |
| **S4 手勢互動** | 0:42–0:51 | R3（**6/04 仍 fail，預設走 fallback**） | Take A 靜態手勢（palm/舉手）或語音 `wave_hello(1016)`；Take B 語音「PawAI 坐下」→坐下（**語音觸發 motion 非手勢**）。**camera 動態 wave 不排進 take** | 「只保留最穩定的靜態示意——動態揮手 6/04 量到 **fail**（recall=0.0），所以**不演 camera 揮手**、只在 Studio 思考紀錄顯示並誠實標 fail，**手勢不直接觸發機器狗動作**」 | `/event/gesture_detected`(靜態) + skill_gate trace + gesture chip(wave=fail) | R3 未 pass（6/04 即如此）→ camera 動態 wave 不演，措辭綁「示意」；wiggle 1033 firmware silent-ignore 不宣稱「搖屁股原生動作」 | 中（不吹「反應快」，刻意調慢防誤觸；camera wave=fail 誠實揭露） |
| **S5 安全拒絕（主秀）** | 0:51–0:58 | R6 | 語音「PawAI 請翻跟斗」→ TTS 拒絕 + Studio 紅 badge；Go2 不動 | 「叫它翻跟斗，它說『這個動作不安全，我不能執行』。這個拒絕是**規則層硬編碼比對，完全不經 LLM**——LLM 連產生這動作的能力都沒有，執行層再擋一次。Go2 本就沒翻跟斗，1301 是 demo-only 假動作走 reject 流程」 | `/brain/skill_result`(banned_api:1301) → `chat-panel.tsx:543` 紅 badge；91 test 全綠 | 只能開 mock → 口頭說清是 mock；ASR 聽錯 → 清楚發音 retake | 低–中（不暗示「本來想翻被擋」；這是 MOTION gate 不順帶宣稱「導航避障安全」） |
| **S6 邊緣感知蒙太奇（nav 零自走）** | 0:58–1:05 | R4（純顯示無條件可做） | Foxglove `/scan_rplidar` + depth + map 蒙太奇；Go2 靜止 | 「PawAI 在 Jetson 邊緣端即時感知環境——光達、深度、地圖——送回 Studio。**展示『系統在看』，不宣稱會自己走**」 | Foxglove 三畫面 + NavigationPanel tri-state GateChip | 這是 nav 最保險版（零 motion）；Live 走 BEST_EFFORT，cv_bridge 缺失 NO SIGNAL → 用既有截圖 | **高（若處理不當）**：任何「會自己走/避障/巡檢」字眼違反 §7+§5 |
| **S6-ALT 進階解鎖（DEFAULT 不做）** | 條件 ~10–15s | **R4+R5 全綠 + Roy 拍板** | 操作員手動 `goto_relative 0.3m` + 旁站手放 e-stop；接 standalone reactive_stop，人走前方 ~1m 展示 cmd_vel 歸零 | 「**操作員全程旁站、隨時可停**的前提下做一次短距移動——研究中的具身能力。前方有人安全層讓它停下。**不宣稱完整自主導航，也不宣稱安全停車已可靠；現行為是離開障礙會自動恢復（auto-resume），這正是我們標 insufficient_data 的原因**」 | goto_relative 軌跡 + reactive danger zone + `/cmd_vel` 歸零 trace + nav chip（pass 或 override 簽核） | 任一 R5 不滿足立即砍退 S6 | **極高**：F7 未驗 + no_auto_resume 是行為 bug；除非全綠 + Roy 拍板一律不做 |
| **S7 收尾** | 1:05–1:10 | — | 字幕「互動主線（實機背書）/ 移動守望（邊緣感知已通，安全自走待 scoreboard pass，研究中）」；回 chip 牆定格 | 「PawAI 的價值在 Jetson 邊緣端即時感知、ROS2 整合、安全 gate、可解釋 Studio 證據。**不是把現成 AI 裝進機器人，而是從零搭一套會誠實量測自己能力的守望互動系統**。做到的秀證據，沒做到的 scoreboard 告訴你」 | frozen chip 牆 / `readiness=not_ready` 收束 | 全段無 pass → 收尾以「誠實 scoreboard + 量測機制本身」為主敘事（**需先和老師對齊**） | 低（誠實層收束反向強化） |

---

## 6. 兩案共用清單

### 6.1 禁說句清單（demo / 旁白 / 報告一律不講）

- 我自主導航到 Roy 身邊 / PawAI 自己走過來找我 / 自動避障找到你 / 我會繞開障礙物繼續前進
- 我可以移動到現場進行**巡檢**（含「自主導航/巡檢助理」框架）
- 安全停車已完成 / safe_stop 已 pass / 停了不會自己暴衝恢復（no_auto_resume 現行為是 auto-resume，宣稱與行為相反）
- 我看到你旁邊有一台電腦 / 沙發旁邊有電腦
- 我可以照顧老人 / 防止跌倒 / 偵測到你跌倒了 / 跌倒偵測 / 我看到地上有跌倒的人
- 守護 / guardian / 守護犬 / 陌生人警報 / 保護長者 / 照護安全（一律改「守望」）
- 通用物體辨識 / 我什麼都認得 / 認得 80 種物件 / 這是什麼牌子
- 人臉辨識已可用 / 可靠 / 已 pass / 不會認錯人
- 揮手反應很快 / 手勢即時觸發（刻意調慢防誤觸）
- 跟隨你 / 自動找人 / 巡邏整個機構 / 導盲
- 斷網也能守望（目前只是設計意圖，current path 仍走 cloud）
- LLM 講得很自然所以系統很可靠（自然度 ≠ 可靠性）
- 系統本來想翻跟斗只是被禁止了（1301 是 demo-only 假動作）
- Go2 會搖屁股（wiggle 1033 firmware silent-ignore）
- Studio 顯示每個能力的 pass/degraded/fail 評分燈號（前端無 fetch /api/scoreboard 的 UI 元件）

### 6.2 建議保守句清單（有故事、站得住）

- 「PawAI 的可靠度不是嘴上說的，是量出來的——這是第一次跑出的可信量測（非乾淨 release baseline）」
- 「PawAI 在邊緣端即時感知環境並把證據送回 Studio——系統在看，不宣稱會自己走」
- 「PawAI 辨識靠近的人，認出已註冊的 Roy 就打招呼——6/04 量到窄版 pass，但僅 Roy 一人/空景，不宣稱拒絕陌生人、不宣稱不會認錯人」
- 「PawAI 看得出人站著還是坐下——這是粗略的姿勢觀察，本輪未量測（insufficient_data），不是醫療判斷、不做跌倒偵測」
- 「我看到桌上有杯子——物件辨識刻意只開杯子這一類、且僅近距 ~1m 可靠，不是通用物體辨識」
- 「只留最穩定的靜態手勢——動態揮手 6/04 量到 fail，所以不演 camera 揮手、誠實標 fail」
- 「這個動作不安全，我不能執行——危險指令在規則層就被攔，LLM 沒機會生成」
- 「做得到的秀給你看，還沒驗證可靠的，誠實標在 scoreboard 上」

### 6.3 Studio 必拍清單

| Studio 元件 | 對應段 | 註記 |
|---|---|---|
| `/face_identity/debug_image`（bbox+名字+距離） | S2 | 同框 face chip=pass(窄版) + 6/04 JSON；維持窄版 caveat |
| `/event/pose_detected` + pose panel | S3 | 鏡頭帶 fallen 紅標旁白不提跌倒 |
| `/perception/object/debug_image`（中文「杯子」） | S4 | 確認 yaml=[41,999] |
| `/event/gesture_detected` + gesture trace chip | S5 | 手勢不接 Go2 motion |
| `/brain/skill_result` blocked badge + pytest 91 綠燈截圖 | S6 安全拒絕 | 確認真 gateway 非 mock |
| 12-stage langgraph trace 色票流（`?dev=1`） | S7 | 確認走 langgraph 引擎 |
| `/studio/live` 三欄影像牆 + EventTicker | S7 | Jetson 8GB 三欄不穩可減單欄 |
| Foxglove `/scan_rplidar` + depth + map | S1 / S6 | 字幕禁寫「自主導航」 |
| `baseline-evidence/` JSON + `readiness_output.json` | S0 | 替代不存在的 scoreboard UI |

### 6.4 現場 fail fallback（跨段保險）

1. **供電斷電（最大單點失敗）**：降低同跑模組數 + 專人監控電壓溫度 + 備援電源；強背書段全部備預錄影片/截圖，活鏈掛掉直接切預錄。
2. **Jetson 8GB OOM / 三欄 NO SIGNAL**：Live View 減單欄或關掉，保 ChatPanel + dev trace。
3. **ASR 聽錯關鍵字**（純字面比對無同音容錯）：清楚發音 retake，或秀預錄 blocked badge + pytest 截圖。
4. **face track 抖動 / 名字閃**：退泛稱問候（不點名），或只秀 debug_image 證鏈路。
5. **object 顏色亂跳 / node 沒真起**：只講「杯子」不講顏色，或退 object panel。
6. **wave 正面失敗**：改側面 / 退 palm / 只 Studio 顯示 event。
7. **scoreboard UI 不存在**：S0/S7 改秀 git-tracked JSON + dev GateChip。
8. **mock vs live 混淆**：現場能 `ros2 topic echo /brain/skill_result` 佐證真鏈。

### 6.5 雙輪拍攝法

- **第一輪（第三人稱主畫面）**：Go2 待機/短距移動、Roy 走近/坐下/水杯入鏡/揮手/說翻跟斗 + Go2 不動 + e-stop 操作員入鏡（展示安全紀律）。
- **第二輪（系統畫面補強）**：Studio 對話 / face debug_image / pose panel / object debug_image / safety blocked badge / Foxglove scan+map+depth 當 1–2 秒蒙太奇。
- **剪輯紀律**：每個第三人稱鏡頭旁邊一定要有 Studio trace 或 debug image 對照（North Star §11 硬前提）；字幕禁寫「自主導航 / 巡檢」。

---

## 7. 升級前置條件 Checklist（初級 → 進階）

從初級保守升進階誠實的條件——**每一項都要有對應 chip grade=pass 背書才放寬旁白**：

- [ ] **R0**：WSL 跑出 frozen `baseline_snapshot.json`，sha 對得上 deploy code（消除 6/04 readiness 第一個 blocker `sha_mismatch`）；在 `/home/roy422/.venv` 跑 build+readiness 即不觸發 `schema_validator_unavailable`（jsonschema 已可 import，見 `docs/runbook/2026-06-18-hitl-oneshot-runbook.md`）。
- [ ] **R1（face 邊界擴張）**：6/04 已是窄版 pass；#81 乾淨重跑（≥2 註冊者 + 多光照 + 真實陌生人樣本）→ 才可從「窄版（僅 Roy/空景）」擴張到更廣 framing。**重跑前不得宣稱拒絕陌生人 / 2m+ / 通用人臉辨識。**
- [ ] **R2（object 邊界擴張）**：6/04 已是 ~1m 窄版 pass；多距離（1/1.5/2m）重跑 → 才可說「2m 也可靠」。**重跑前只講 ~1m 近距杯子。**
- [ ] **R3（gesture 升級）**：gesture.wave baseline **pass**（含 idle 誤觸 ground-truth）——**6/04 仍 fail（recall=0.0）** → 才可說「揮手互動可靠」；未 pass 前 camera 動態 wave 不演、誠實標 fail。
- [ ] **R4（nav 解鎖前置）**：F7 在 fresh stack 定位 + nav.safe_stop/no_auto_resume **pass** 或人工 override 簽核 → 才談任何 motion。
- [ ] **R5（真實移動）**：R4 綠 + acid test 0.3m 未復現 F7 + 供電穩 + Roy 旁站 e-stop → 才啟 S6-ALT。
- [ ] **R6（安全拒絕升級）**：真機 Go2+Jetson 端到端錄過一次語音→TTS 拒絕→紅 badge → 才可說「實機端到端驗證」。
- [ ] **語音輸入層**：ASR 對 5 組 unsafe keyword + 核心指令辨識率實測通過；mic boundary `/event/mic_boundary` 接通。

**升級原則**：沒勾的項目對應段一律走初級保守的「只顯示不宣稱」口徑。**任一段不可因「想要完整感」而順口升級成「已 pass」。**

---

## 8. 開放問題給 Roy

1. **下次 HITL session 排定了嗎？** face #81 重跑 + voice/gesture/object 跑出真數據是 6/18 能否有任何 pass 能力的關鍵前置。沒排 = 全程走「只顯示 + 誠實 fail」。
2. **F7 在學校 fresh stack 是否復現？** 這是 nav 能否做任何真實 motion 的唯一 gate。5/13 排定要驗但無結果落檔——S6-ALT 是否啟用全看這題。
3. **6/18 nav 走哪條路徑？** (a) 純 Studio 顯示蒙太奇（最安全，建議 default）；(b) 人工 override 0.3m + reactive 遇障停（需 F7 + 全程旁站）。需拍板。
4. **scoreboard 前端要不要補一個最小 Scoreboard 元件 fetch `/api/scoreboard`？** 不補 = S0/S7 只能秀 JSON，沒有「燈號 chip 牆」視覺。這屬未排程 scope。
5. **若 6/18 前所有重跑仍無 pass，收尾故事是否以「誠實 scoreboard + 量測機制本身」為主敘事？** 這個 fallback 需先和老師對齊（North Star §11 報告口徑）。
6. **pose 社交 TTS 路徑（brain_node `_on_pose`→`sit_along`）在 demo 配置下確實出聲嗎？** 與 langgraph 是否互搶 `chat_candidate` 需上機 smoke。
7. **mic_stop 訊號流（`/event/mic_boundary`）接通了嗎？** 這是 voice baseline 走 manual mic boundary 的 demo-blocking 前置。

---

## 交叉引用

- **誠實鐵律與用詞權威**：[`docs/mission/2026-06-18-demo-north-star.md`](2026-06-18-demo-north-star.md) — §5 禁說 / §7 nav 鐵律 / §9 scoreboard-first / §10 Edge AI / §11 報告原則。
- **能力分級證據（最新 trusted snapshot + readiness=not_ready）**：[`docs/runbook/baseline-evidence/2026-06-04-hitl/`](../runbook/baseline-evidence/2026-06-04-hitl/)（SHA `78fbf36`）。`2026-06-03-first-trusted-face/` 已被取代，僅作歷史。
- **canonical claim 真相源（每能力 Current Claim / Pass-Fail / Non-Claims）**：[`docs/mission/2026-06-18-capability-claim-matrix.md`](2026-06-18-capability-claim-matrix.md)。
- **能力 baseline 規格**：[`docs/pawai-brain/specs/2026-06-18-capability-baseline-spec.md`](../pawai-brain/specs/2026-06-18-capability-baseline-spec.md)。
- **收斂審計（6/05，evidence-hierarchy #2）**：[`docs/archive/pawai-brain-legacy/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md`](../pawai-brain/research/2026-06-05-618-demo-convergence-audit-and-model-tournament.md)。
- **canonical demo story 9 步**：North Star §6（本文 S1–S7 即其誠實落地版）。

> **底線**：6/18 demo 的可信度建立在「誠實本身就是可信度」。6/04 量到 3 項窄版 pass + 2 項 fail + 其餘 insufficient_data——**誠實揭露 fail 與窄版邊界**本身就是賣點，系統會揭露不足而非過度宣稱。做得到的（窄版內）秀給你看，量到 fail / 還沒驗證可靠的，scoreboard 會告訴你。
