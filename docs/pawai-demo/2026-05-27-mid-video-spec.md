# 2026-05-27 中期 demo 影片 spec — 門口監控小閉環

> **Deadline**：2026-05-27（4 天）
> **影片長度**：~3 分鐘
> **主軸口號**：「PawAI 門口巡檢助理：看得見人、認得出身份、聽得懂指令、知道危險動作不能做」
> **狀態**：5/23 grill + codebase audit 後 lock，等同 ADR-pending 級決定
> **與 6/18 實機 demo 的關係**：5/27 是**唯一影片產出**（可剪輯）；6/18 是**實機 live demo**（不可剪），兩個 deadline scope 不同。詳 v2 spec §11 兩個 deadline 比較。
> **與 ADR 的關係**：本 spec 對齊 ADR-0001（非接觸式定位）/ ADR-0002（雙層敘事）/ ADR-0003（push-to-talk 取代 wake word）

---

## 1. 為什麼是這個 scope

5/23 grill 第二輪 + 三場 review synthesis 後的取捨：

- **5/27 deadline 真實 4 天**，不能塞「長照 8 mini-event 連拍」這種野心
- 呂奇傑 5/22 建議的 4 個情境（門口監控 / 環保撿垃圾 / 長照交誼廳 / 語音控制動作）中，**情境 1 + 情境 4 工程依賴最少**
- 情境 2（撿垃圾）需要穩定物件偵測 + 自主巡邏 — 不在 5/27 risk budget 內
- 情境 3（長照）需要多人 + 物件掉落 + 走丟邏輯 — 是 6/18 實機 demo 目標
- 「門口監控 + 語音動作 + 安全拒絕」剛好對應呂奇傑強訊號「Function 必須先有，再有更大場景」

### 對齊老師三場訊號

| 訊號 | 5/27 影片如何回應 |
|---|---|
| 葉 5/18「文件 40 頁太多、刪準確率、整合派該講踩坑」 | 段 0 硬體 Before/After 30 秒 = 整合挑戰視覺化 |
| 葉 5/18「20kg 拉手摔倒安全顧慮」 | 全片無物理接觸鏡頭（ADR-0001）+ 段 5 安全拒絕主動體現 |
| 雅文 5/20「為什麼是狗 / 蘿蔔水果湯」 | 4 個 function 串成「門口巡檢助理」一個情境，不是功能拼盤 |
| 呂奇傑 5/22「Before/After 必須是骨架」 | 段 0 + 全片旁白用 Before/After 句式 |
| 呂奇傑 5/22「指令式精準回應 + 安全機制」 | 段 4 + 段 5 直接體現他親自設計的劇本 |
| 呂奇傑 5/22「真正困難的硬體過程完全沒提」 | 段 0 補上 |

---

## 2. 6 步驟劇本（含每步驟對應功能 + LoC 估算）

### 段 0：硬體 Before/After（0:00-0:30，獨立預錄）

| 鏡頭 | 內容 | 旁白範式 |
|---|---|---|
| 0:00-0:05 | Go2 原廠開箱 + 遙控器特寫 | 「Go2 Pro 是家用版，原廠只給遙控器」 |
| 0:05-0:12 | Jetson 背載 + 走線 + 3D 列印外殼 | 「為了讓它聽得懂、看得到、自己思考，我們做了 3D 列印背包、降壓板、雙系統有線整合、第三方 SDK 破解」 |
| 0:12-0:20 | 降壓板特寫（燒過的舊版 vs 新版）| 「Go2 電壓會燒 Jetson，三顆降壓板才穩」 |
| 0:20-0:30 | NumPy 衝突 git log + 三模型同跑 GPU 監控 | 「軟體整合更難 — Edge AI 8 GB 共享記憶體跑五個感知模型」 |

**所需能力**：旁白 + 硬體素材，**0 LoC**。Roy 在家拍。

### 段 1：開場 Before/After 文字（0:30-0:45）

旁白配字幕：

> Before：Go2 只能被遙控
> After：PawAI 讓它具備視覺、語音、身份判斷、安全策略

**所需能力**：純剪輯字幕，0 LoC。

### 段 2：熟人辨識 + 主動打招呼（0:45-1:05）

| 步驟 | 行為 | 對應能力 |
|---|---|---|
| PawAI 待機坐門口 | 待機動作 | Go2 standby skill（已有） |
| Roy 走近 | face_identity 認到 | face_perception YuNet + SFace（已 USABLE，alice/grama 已 enroll） |
| PawAI TTS「Roy，歡迎回來」 | LLM persona greet | brain_node 既有 `greet_known_person` skill |

**所需能力**：全部已 USABLE，**0 LoC**。

**驗收**：5/5 通過率。

### 段 3：陌生人追問 + 警示（1:05-1:45）

| 步驟 | 行為 | 對應能力 |
|---|---|---|
| 陌生人（演員）走近 | face_identity 偵測 unknown（連續 3s）| 既有 `stranger_alert` 觸發路徑（brain_node.py:895-927） |
| PawAI TTS「請問你是哪位？」| 新陌生人 FSM `AWAITING_NAME` 狀態 + skill `stranger_question` | **新寫**：mini-FSM + skill_contract 兩條 + brain_node hook |
| 對方回答「我是來送貨的」/「我是 Roy 朋友」 | ASR + LLM 判斷「合理身份」 | 既有 stt_intent + 新 LLM zero-shot 判斷 prompt |
| PawAI TTS「好的，請進」（合理） or 「請告訴我你是誰」（亂答）| FSM 分支 | 同上 |
| 對方 retry 仍亂答 | 計數 3 次 | FSM `retry_count` |
| PawAI TTS「我無法確認身份，我準備報警」| 新 skill `stranger_warn` | 同上 |

**所需能力**：**~180-220 LoC**（陌生人 FSM + 2 skills + LLM 判斷器）

**Thin 版**（subagent 推薦）：3 輪固定問句 + LLM 判斷器，不做 retry 上限自適應、不做 multi-stranger 追蹤。

**砍項策略（5/25 PM smoke 不穩時）**：**首砍 retry loop** — 保留「1 問 1 答 + 任何回答都進入 stranger_warn TTS」，省 ~60 LoC + 整合風險。劇本仍能看：「unknown → 問名字 → 警告」雙鏡頭。

**驗收**：5/5 觸發 stranger_question + 3/5 LLM 正確判斷（thin 版可接受）。

### 段 4：語音指令精準執行（1:45-2:15）

| 步驟 | 行為 | 對應能力 |
|---|---|---|
| Roy 在 Studio PTT「PawAI，坐下」| Studio composer 已有 mic button（ADR-0003）→ ASR → intent_classifier keyword「坐下」→ skill_dispatcher `sit` → Go2 sit api_id=1009 | 全鏈路已存在（intent_classifier.py:102-106 + skill_contract.py `sit_along`）|
| PawAI 真的坐下 | Go2 sport mode | 已有 |
| Roy 在 Studio PTT「PawAI，舉手」| 同上 → intent_classifier 新 keyword「舉手」→ skill `hello`（api_id=1016 = Go2 Hello 揮手）| **新寫**：intent_classifier 加 keyword + LLM prompt example |
| PawAI 舉手揮手 | Go2 sport mode | 已有 |

**所需能力**：**~20 LoC**（intent_classifier.py 加「舉手」一行 + LLM prompt 加 example）

**LLM hijack 風險**：subagent 確認 LLM whitelist 只允許 `{"hello", "stop_move", "sit", "stand", null}`，**不會 free-form 回應**。低風險。

**驗收**：5/5 sit + 5/5 hello 精準執行（subagent 評估「完整可達」）。

### 段 5：安全機制拒絕翻跟斗 + Studio trace 紅色（2:15-2:35）

> **2026-05-23 evening 修正**：先前版本說「加 backflip 進 LLM 可生成 skill 白名單」會讓未來實作走到繞過 SafetyLayer 的執行路徑（即便當下 SafetyLayer 會擋）。**改成獨立 `unsafe_intent` 路徑，LLM whitelist 完全不動，不產生可執行 plan，只產生 reject 事件**。

| 步驟 | 行為 | 對應能力 |
|---|---|---|
| Roy 在 Studio PTT「PawAI，請翻跟斗」| ASR → intent_classifier 新 keyword「翻跟斗 / 後空翻」→ 標記為 `unsafe_intent=backflip`（**獨立 enum，與 selected_skill 分離**） | **新寫**：intent_classifier 加 keyword + 新 `unsafe_intent` 欄位 |
| brain 收到 `unsafe_intent` | **直接路由到 SafetyLayer reject path，不進入 skill_dispatcher、不產生任何可執行 plan** | **新寫**：brain reject path |
| SafetyLayer emit `BLOCKED_BY_SAFETY` + reason=`unsafe_intent:backflip` | interaction_executive_node.py:84-91 既有 emit 機制 | 既有 |
| Studio chat-panel.tsx:543 紅色 highlight 顯示「rejected by SafetyLayer」| bubble-safety.tsx 已有 amber 警示 + brain-status-strip.tsx safety flag | 已有 |
| brain 收到 blocked 事件 → safety TTS「這個動作不安全，我不能做」| **新寫**：conversation_graph_node.py 加 SkillResult subscribe → safety TTS path |

**所需能力**：**~60-80 LoC**（intent_classifier 新 unsafe_intent 欄位 + brain reject path + safety TTS）

**設計原則（不可違反）**：

> **危險動作永遠不進入可執行 skill 路徑**。intent 與 skill 是兩個獨立 enum：`unsafe_intent` 只能產生 `BLOCKED_BY_SAFETY` 事件，**不能、不應、不允許**產生任何送進 skill_dispatcher 的 plan。

| 層 | 5/27 spec 改動 | 安全意義 |
|---|---|---|
| intent classifier（語意層）| 加 `unsafe_intent` 欄位，識別「翻跟斗」→ 標 `unsafe_intent=backflip` | 讓 brain 看得到「使用者想做危險動作」這個請求 |
| LLM whitelist（plan 生成層）| **完全不動**，仍 `{"hello", "stop_move", "sit", "stand", null}` | LLM 不可能輸出 backflip plan |
| brain reject path | **新增**：unsafe_intent → 直接 emit BLOCKED_BY_SAFETY，跳過 skill_dispatcher | 危險動作物理上不可能進入執行層 |
| `BANNED_API_IDS`（execution 攔截層）| **不動**，仍 `{1030, 1031, 1301}` | 即使有任何路徑漏出 plan，execution 仍 100% 阻擋（雙重防線） |
| Studio trace | 顯示 `BLOCKED_BY_SAFETY` 紅色 | 視覺化「**拒絕**」這個 happy path |

**為什麼不能把 backflip 加進 LLM whitelist**：即便 SafetyLayer 當下能擋，把危險動作放進「可生成 skill 名單」會：
- 未來重構若移除 BANNED_API_IDS 檢查 → backflip 立刻變可執行
- LLM 任何意外輸出 backflip plan → execution path 不該成為防線之外的選擇
- 違反「危險動作不應流到 skill_dispatcher 入口」這條設計紀律

**驗收條款（必達，不可妥協）**：

1. **任何**「翻跟斗 / 後空翻 / backflip」輸入 → 必然產生 `BLOCKED_BY_SAFETY` 事件
2. **0 機率**走到 skill_dispatcher（unit test 5/5 + 整合 test 5/5 全綠）
3. **0 機率**產生包含 api_id=1030 的可執行 plan
4. LLM whitelist 維持 `{"hello", "stop_move", "sit", "stand", null}` 不變
5. Studio trace 5/5 顯示 `BLOCKED_BY_SAFETY` 紅色 highlight
6. safety TTS 「這個動作不安全，我不能做」5/5 觸發

**測試**：
- `test_intent_classifier_unsafe.py`：「翻跟斗」→ `unsafe_intent="backflip"`, `selected_skill=None`（5/5）
- `test_brain_unsafe_intent_reject.py`：收到 unsafe_intent → emit BLOCKED_BY_SAFETY，**不**呼叫 skill_dispatcher（5/5）
- `test_e2e_safety_reject.py`：端到端「翻跟斗」→ TTS + Studio trace（5/5）

**不可砍**：這條是 PawAI Brain 三層架構（Safety/Policy/Expression）唯一可視化證據 + 直接回應呂奇傑 5/22 親自指定鏡頭。**砍了等同沒做安全層敘事**。

### 段 6：結尾接三週方向 + 段 4 未來情境收尾（2:35-3:00）

旁白：

> 這些能力都是 function。接下來三週，我們會把身份辨識、物件偵測、移動巡檢、姿勢辨識、跌倒警示串成更完整的機構巡檢場景。

接著放 v2 spec §11 段 4 未來情境收尾（校園 → 導盲 → 救災）+ 黑屏標語「PawAI — Physical AI for Institutional Care」。

**所需能力**：旁白 + AI 生成補完（v2 §11 已規劃），**0 LoC**。

---

## 3. Nice-to-have（5/27 非 blocker）

### 口罩 / 帽子 遮擋 fallback

**劇本**：face_perception 偵測到「有人臉框但身份信心極低」→ TTS「請拿下帽子或口罩，否則我無法辨識」

**所需能力**：~80-110 LoC（face_identity_node 加 occlusion tracker dict + 新 event_type `occluded` + brain rule cooldown 15s）

**為什麼是 nice-to-have**：
- 易被現場光線 / 角度 / SFace 模型狀態搞爆
- 觀眾看不出「沒辨識成功」vs「遮擋」差異
- 若 5/24 寫完穩定 → 5/27 拍進去；若 5/25 smoke 不穩 → 剪掉，不影響主敘事
- 對「門口巡檢助理」主軸**加分有限**（已有陌生人追問替代）

**決策時機**：5/26 早上 review 5/25 smoke 結果決定要不要進影片。

---

## 4. 4 天工程量總和

| 能力 | LoC | 4 天可達深度 |
|---|---:|---|
| 段 2 熟人辨識 | 0 | ✓ 已 USABLE |
| 段 3 陌生人 FSM thin 版 | 180-220 | ✓ 完整 |
| 段 4 語音指令舉手 | 20 | ✓ 完整 |
| 段 5 安全拒絕 + Studio trace | 60-80 | ✓ 完整 |
| Nice-to-have：遮擋 fallback | 80-110 | △ 視 5/25 smoke 結果 |
| **總和** | **260-320（不含 nice-to-have）/ 340-430（含）** | Roy 4 天可達 |

---

## 5. 5/24-5/27 排程

**前提**：Roy own 功能；團隊接拍攝協調（場域 / 演員 / 收音 / 燈光 / 剪輯）。

### 5/24（Sat）— 寫代碼日

| 時段 | 任務 | Owner |
|---|---|---|
| AM | 段 3 陌生人 FSM thin 版 + skill_contract `stranger_question` / `stranger_warn` 註冊 + brain_node hook | Roy |
| AM | 段 4 intent_classifier 加「舉手」keyword + LLM prompt example | Roy |
| PM | 段 5 intent classifier 允許 unsafe_intent=backflip 流到 SafetyLayer（BANNED_API_IDS 不動）+ safety TTS 路徑（conversation_graph_node.py SkillResult subscribe）| Roy |
| PM | 本機 unit test 跑齊（pawai_brain + interaction_executive + speech_processor） | Roy |
| Optional PM | Nice-to-have：段 2.5 遮擋 fallback occlusion event | Roy（時間夠才做）|

### 5/25（Sun）— Jetson 實測日

| 時段 | 任務 | Owner |
|---|---|---|
| AM | jetson-deploy 4 條（或 5 條含 nice-to-have） | Roy |
| AM | 段 3 / 段 4 / 段 5 逐條 smoke（每條 3 輪） | Roy |
| PM | 段 2 熟人辨識 5/5 確認（face_db 確認 Roy 已 enroll） | Roy |
| PM | 全段串連 smoke 1 次（從段 2 走到段 5） | Roy |
| PM | 段 0 硬體 Before/After 素材拍攝（在家拍 Go2 + 3D 件 + 降壓板特寫） | Roy |
| Eve | review 結果 → 決定是否砍項（首砍 retry / 次砍遮擋） | Roy |

### 5/26（Mon）— 排練日，**不再加功能**

| 時段 | 任務 | Owner |
|---|---|---|
| AM | 排練 1：跑完劇本一次、記 bug、調整節奏 | Roy + 團隊（演員到位） |
| PM | bug fix（**只修不加新功能**） | Roy |
| PM | 排練 2：完整跑、錄備用素材 | Roy + 團隊 |

### 5/27（Tue）— 拍攝 + 交件

| 時段 | 任務 | Owner |
|---|---|---|
| AM | 最終排練 + demo-preflight 跑齊 | Roy |
| PM 14:00-17:00 | 正式錄影（光線+收音穩） | Roy 操作 PawAI + 團隊拍攝 |
| Eve | 剪輯 + 旁白配音 + 段 0 / 段 6 接合 | 團隊（黃 / 陳 owner） |
| 23:59 | 交件 | — |

---

## 6. Fallback：哪條功能爆掉怎麼剪

| 段 | 失敗時剪輯策略 |
|---|---|
| 段 0 硬體 Before/After | Roy 5/25 拍不完 → 5/26 補拍 → 5/27 上午仍不行 → 用既有照片 + 文字過場代替（v2 §11 fallback 已寫）|
| 段 2 熟人辨識 | face_identity 不穩 → 改剪「PawAI 走過去 + TTS 打招呼」（去掉 face highlight），改用 face cache 預存 |
| 段 3 陌生人 retry | LLM 判斷亂答失敗 → **砍 retry loop**，剪成「unknown → 問名字 → 警告」雙鏡頭（subagent 推薦首砍）|
| 段 4 語音指令 | sit 穩、舉手不穩 → 只拍 sit；都不穩 → 改鍵盤輸入「坐下」演示 |
| 段 5 安全拒絕 | LLM 不認「翻跟斗」keyword → **不可砍**，必須調 prompt + 加 keyword 直到能跑；前端紅色不顯示 → 改用 Studio trace JSON 截圖過場 |
| 段 6 結尾 | AI 生成未來情境素材不順 → 改用文字 + 既有照片過場 |
| Nice-to-have 遮擋 | 5/25 不穩 → **直接剪掉**，不影響主敘事 |

**核心原則**：段 2 + 段 4 + 段 5 是必達；段 3 thin 化可接受；段 0 + 段 6 用過場素材兜底。

---

## 7. 對外敘事禁用詞 / 必說句（5/27 旁白必過 audit）

詳見 [`docs/pawai-demo/2026-05-23-doc-and-report-guidelines.md`](2026-05-23-doc-and-report-guidelines.md)（即將寫）

**5/27 影片旁白快速 checklist**：

❌ 禁用：
- 「本來想做 X」
- 「現在還沒做到」
- 「比較差 / 不完整」
- 「期待不要太高」

✅ 必說：
- 開場「沒有 PawAI 之前，Go2 只能用遙控器；有了 PawAI 之後 …」
- 段 5 安全拒絕後「**我們設計了讓 LLM 不能直接控制機器人的安全層**，這個動作 Safety Layer 攔截了」
- 結尾「機構巡檢只是 6/18 POC 場景；PawAI 的平台能力可延伸到校園、導盲、救災」（ADR-0002 雙層敘事視覺化）
- 安全聲明「PawAI 設計為非接觸式機構巡檢助理」（ADR-0001）

---

## 8. 文件治理

- 本 spec lock 後 5/24 起 Roy 開始動工，不再修改 scope（避免「無限重排」）
- 失敗剪輯 / 砍項決策由 Roy 5/25 PM smoke 後決定，記到本 spec § 6 fallback 表
- 拍攝完成後加 § 9「實際拍攝與發生事項」記錄（5/27 evening 補）
- ADR-0004（demo 場景劇）等本 spec + 6/18 實機 demo 落地後寫
