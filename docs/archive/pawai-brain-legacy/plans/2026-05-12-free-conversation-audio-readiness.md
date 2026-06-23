# Free Conversation Audio Readiness — 5/12 移交前

> **Status**: ready-to-execute
> **Date**: 2026-05-10 night
> **Owner**: Roy
> **目的**：確認 demo 不依賴 Studio button、能用語音直接持續自由對話 3-5 分鐘。並評估 AirPods 是否值得納入 demo。

---

## 1. 為什麼做

Demo 的氛圍是「PawAI 主持」，如果每次對話都要按按鈕觸發，會像在操作 chatbot，破壞角色感。Roy 希望像跟雪寶/BDX 那樣，**自然開口就回應**。

但在家裡從未真正測過 3-5 分鐘自由對話穩定性 — 只測過單句來回。風險集中在：
- VAD 斷句閾值（已知是最大延遲瓶頸 2-10s）
- ASR 連續識別累積錯誤
- TTS 排隊塞車
- 麥克風背景噪音
- AirPods 藍牙延遲（未測）

---

## 2. 三條測試線

### D1. USB 麥（已驗 baseline）

**設備**：USB UACDemoV1.0（device 24, mono, 48kHz）
**喇叭**：USB CD002-AUDIO（plughw 動態，跑 `device_detect.sh`）

**測試**：
```bash
source scripts/device_detect.sh
# 確認 $DETECTED_MIC_INDEX, $DETECTED_SPK_DEVICE
bash scripts/start_llm_e2e_tmux.sh
```

**5 分鐘自由對話劇本**：
1. 「你好 PawAI」
2. 「自我介紹一下」
3. 「你能做什麼」
4. 「展示一個動作」
5. 「你看到什麼」
6. 「你認得我嗎」
7. 「跟我講你的限制」
8. 「停下來」
9. 「再聊一會」
10. 「結束」

**Pass criteria**：
- [ ] 10 句裡 ≥8 句正確 ASR
- [ ] LLM 平均回應 < 4s
- [ ] TTS 不卡、不重疊
- [ ] 不需要按任何按鈕，全程語音
- [ ] 5 分鐘後不掉 ASR、不 crash

---

### D2. AirPods（評估）

**目的**：評估 demo 是否要用 AirPods（Roy 戴著與 PawAI 對話）

**測試**：
```bash
# Mac 連 AirPods → Mac 跑 Studio with audio passthrough?
# 或：直接接 AirPods 到 Jetson（USB-C 不接 BLE，需要藍牙 dongle）
```

**現實檢查**：
- Jetson Orin Nano 內建藍牙不穩，AirPods 配對麻煩
- Mac 接 AirPods 後，要把音訊傳到 Jetson ASR pipeline 不直接（要走 audio over network）
- **可能不值得**：demo 風險高、收益不明顯

**Pass criteria（高標）**：
- [ ] AirPods 配對 < 30s
- [ ] ASR 延遲 < 1.5s
- [ ] TTS 從 AirPods 出來、不從 Go2 喇叭

**Fail 動作**：直接砍 AirPods，demo 用 USB 麥 + Go2 喇叭

**建議**：先花 30 分鐘試，沒進展直接砍。不要為 AirPods 拖垮 demo readiness。

---

### D3. 自由對話模式（不靠 Studio button）

**檢查現況**：
- `stt_intent_node` 是否預設 always-on listening？還是要按按鈕？
- VAD 閾值是否合理（已知 2-10s 是最大瓶頸）

**測試**（5/12 PM）：
```bash
# 啟動全 stack
bash scripts/start_full_demo_tmux.sh

# 不要碰 Studio，純語音對話 5 分鐘
# 觀察：
# - 講完 → 多久才開始 ASR？
# - ASR 完 → 多久才 LLM？
# - 中間有沒有 dead air？
# - 連續講多句會不會塞車？
```

**Pass criteria**：
- [ ] 全程不按 Studio button
- [ ] 對話節奏 < 6s/輪（speech_end → audible reply start）
- [ ] 連續 5 輪不漏
- [ ] 環境噪音不誤觸（背景說話聲不被 ASR 抓）

**若 VAD 太慢（>6s）**：
- 降 `vad.silence_timeout` from default → 0.5s
- 但太短會切詞 → 折衷 1.0s
- demo 期不調過頭，保穩定

---

## 3. 5/12 PM 任務排程

| 時段 | 任務 |
|---|---|
| 15:30-16:00 | D1 USB 麥 5 分鐘自由對話 |
| 16:00-16:30 | D2 AirPods 30 分鐘評估（不行就砍）|
| 16:30-17:00 | D3 自由對話模式（VAD 觀察 + 微調）|

---

## 4. Demo 設備決策（5/12 17:00）

| 場景 | 麥 | 喇叭 |
|---|---|---|
| **Plan A（推薦）** | USB UACDemoV1.0 | USB CD002-AUDIO |
| Plan B | USB | Go2 Megaphone（demo 場有 PA 輔助時）|
| Plan C（風險高）| AirPods | AirPods |

**Plan A 鎖定**，除非 D2 評估 AirPods 出乎意料穩。

---

## 5. 結論表（5/12 17:00 必填）

| 項 | 結論 |
|---|---|
| D1 USB 麥 5 分鐘 | ☐ pass / ☐ partial / ☐ fail |
| D2 AirPods | ☐ 採用 / ☐ 棄用 |
| D3 自由對話節奏 | 平均 ___s / 輪 |
| Demo 設備鎖定 | ☐ Plan A / ☐ B / ☐ C |
| VAD 閾值最終值 | silence_timeout = ___ s |

---

## 6. 與其他 plan 的關係

- **A.Brain** 的 canned 自介在 D1 自由對話劇本內測
- **C.Runtime** Mode 1 / Mode 3 都會用到本 plan 的麥/喇叭設定
- **E.Mac/Network** 不影響本 plan（ASR 走 Jetson 本機）

---

## 7. 不在這份 plan 的事

❌ 自訓 wake word
❌ Speaker diarization（誰在講）
❌ 雙人對話 routing
❌ 自由對話 + nav 同跑壓測（demo 後）

---

**End of Free Conversation Audio Readiness**
